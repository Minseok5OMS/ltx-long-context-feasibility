"""Audit all factorial cells, score cached DINOv2, and export synchronized comparisons."""

import argparse
import csv
import json
import os
from pathlib import Path
import shlex
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from run_generation import ROOT, read_rgb, sha256, write_json, write_video


def export_comparisons(report, seeds, configs, videos, local):
    from temporal_artifacts import CELLS
    font = ImageFont.load_default(size=18)
    artifacts = {}
    for seed in seeds:
        sequences = {cell: np.concatenate([local, videos[f"{seed}_{cell}"]]) for cell in CELLS}
        comparison = []
        for frame in range(120):
            canvas = Image.new("RGB", (1024, 640), "#141923")
            draw = ImageDraw.Draw(canvas)
            for index, cell in enumerate(CELLS):
                x, y = index % 2 * 512, index // 2 * 320
                canvas.paste(Image.fromarray(sequences[cell][frame]), (x, y + 32))
                phase = "local" if frame < 48 else "target"
                draw.text((x + 6, y + 6), f"{cell} | seed {seed} | {phase} {frame / 24:.2f}s", fill="white", font=font)
            comparison.append(np.asarray(canvas))
        artifacts[f"seed{seed}_comparison"] = write_video(report / f"seed{seed}_comparison.mp4", np.stack(comparison), 24)
        # GT plus all four cells at six target times; full-size labels remain readable.
        keys = ["gt", *[f"{seed}_{c}" for c in CELLS]]
        sheet = Image.new("RGB", (5 * 288, 6 * 190), "#141923")
        draw = ImageDraw.Draw(sheet)
        indices = np.linspace(0, 71, 6).round().astype(int)
        for row, frame in enumerate(indices):
            for col, key in enumerate(keys):
                x, y = col * 288, row * 190
                tile = Image.fromarray(videos[key][frame]).resize((288, 162))
                sheet.paste(tile, (x, y + 28))
                label = "GT" if key == "gt" else key.split("_", 1)[1]
                draw.text((x + 3, y + 4), f"{label} {frame / 24:.2f}s", fill="white", font=font)
        sheet.save(report / f"seed{seed}_frames.jpg", quality=94)
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, choices=[42, 43, 44], default=[42, 43, 44])
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], default=2)
    parser.add_argument("--preview-only", action="store_true", help="CPU audit and comparison export, no metrics")
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["XFORMERS_DISABLED"] = "1"
    import torch
    from temporal_artifacts import EXAMPLE, CELLS, audit_cells

    torch.set_num_threads(8)
    seeds = sorted(set(args.seeds))
    configs, audit = audit_cells(seeds)
    report = ROOT / "reports/temporal_position"
    report.mkdir(parents=True, exist_ok=True)
    write_json(report / ("preview_audit.json" if args.preview_only else "artifact_verification.json"), audit)
    example = ROOT / "data" / EXAMPLE
    metadata = json.loads((example / "metadata.json").read_text())
    if sha256(example / "gt_target.mp4") != metadata["clips"]["target"]["sha256"]:
        raise ValueError("GT clip changed")
    videos = {"gt": read_rgb(example / "gt_target.mp4", 512, 288)}
    videos.update({f"{seed}_{cell}": read_rgb(Path(cfg["outputs"]["target"]["path"]), 512, 288)
                   for seed, group in configs.items() for cell, cfg in group.items()})
    if any(len(v) != 72 for v in videos.values()):
        raise ValueError("Target frame count mismatch")
    local = read_rgb(example / "local_context.mp4", 512, 288)
    oracle = read_rgb(example / "oracle_context.mp4", 512, 288)
    artifacts = export_comparisons(report, seeds, configs, videos, local)
    if args.preview_only:
        print(json.dumps({"audit": "passed", "preview_directory": str(report), "seeds": seeds}))
        return
    if not torch.cuda.is_available():
        raise RuntimeError("Evaluation requires GPU access")
    dino_repo = Path("/home/minseok/.cache/torch/hub/facebookresearch_dinov2_main")
    weights = Path("/home/minseok/.cache/torch/hub/checkpoints/dinov2_vitb14_pretrain.pth")
    sys.path.insert(0, str(dino_repo))
    from dinov2.hub.backbones import dinov2_vitb14

    model = dinov2_vitb14(pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model = model.eval().to("cuda:0")
    indices = np.linspace(0, 71, 12).round().astype(int)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda()
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()

    def features(frames):
        arrays = []
        for rgb in frames:
            img = Image.fromarray(rgb)
            ratio = 256 / min(img.size)
            img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.Resampling.BICUBIC)
            x, y = (img.width - 224) // 2, (img.height - 224) // 2
            arrays.append(np.asarray(img.crop((x, y, x + 224, y + 224))))
        batch = torch.from_numpy(np.stack(arrays).copy()).permute(0, 3, 1, 2).cuda().float() / 255
        with torch.inference_mode():
            encoded = model((batch - mean) / std)
        return torch.nn.functional.normalize(encoded.float(), dim=-1).cpu()

    embeddings = {name: features(video[indices]) for name, video in videos.items()}
    embeddings["oracle_reference"] = features(oracle[indices])
    torch.save(embeddings, report / "dino_features.pt")
    ref_small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in oracle]).astype(np.float32)
    rows, effects = [], []
    diagnostics = {}
    for seed in seeds:
        scores = {}
        for cell in CELLS:
            key = f"{seed}_{cell}"
            frame_scores = (embeddings[key] * embeddings["gt"]).sum(dim=-1)
            scores[cell] = float(frame_scores.mean())
            rgb = videos[key].astype(np.float32)
            adjacent = np.abs(np.diff(rgb, axis=0)).mean(axis=(1, 2, 3))
            small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in videos[key][indices]]).astype(np.float32)
            nearest = [float(np.abs(ref_small - f).mean(axis=(1, 2, 3)).min()) for f in small]
            diagnostics[key] = {"dino_gt_frame_cosines": frame_scores.tolist(),
                                "adjacent_pixel_mae_0_255": float(adjacent.mean()),
                                "near_static_pair_fraction_mae_below_0_1": float((adjacent < 0.1).mean()),
                                "boundary_pixel_mae_0_255": float(np.abs(local[-1].astype(np.float32) - rgb[0]).mean()),
                                "oracle_nearest_frame_pixel_mae_128x72_mean": float(np.mean(nearest)),
                                "oracle_max_feature_cosine_mean": float((embeddings[key] @ embeddings["oracle_reference"].T).max(dim=1).values.mean())}
            kind, position = cell.split("_")
            cfg = configs[seed][cell]
            rows.append({"example_id": EXAMPLE, "seed": seed, "reference_kind": kind, "reference_position": position,
                         "reference_tokens": cfg["reference_tokens"], "dino_gt_cosine": scores[cell],
                         "adjacent_pixel_mae_0_255": diagnostics[key]["adjacent_pixel_mae_0_255"],
                         "reused": seed == 42 and cell in ("image_target", "video_past")})
        image_delta = scores["image_target"] - scores["image_past"]
        video_delta = scores["video_target"] - scores["video_past"]
        effects.append({"seed": seed, "image_target_minus_past": image_delta, "video_target_minus_past": video_delta,
                        "video_minus_image_at_past": scores["video_past"] - scores["image_past"],
                        "video_minus_image_at_target": scores["video_target"] - scores["image_target"],
                        "interaction_video_delta_minus_image_delta": video_delta - image_delta})
    aggregates = {cell: {"mean": float(np.mean([r["dino_gt_cosine"] for r in rows if f'{r["reference_kind"]}_{r["reference_position"]}' == cell])),
                         "values_by_seed": {str(r["seed"]): r["dino_gt_cosine"] for r in rows if f'{r["reference_kind"]}_{r["reference_position"]}' == cell}}
                  for cell in CELLS}
    mean_effects = {key: float(np.mean([r[key] for r in effects])) for key in effects[0] if key != "seed"}
    anchor_checks = {}
    if 42 in seeds:
        for cell, layout in [("image_target", "target_guide"), ("video_past", "past")]:
            previous = json.loads((ROOT / "reports/reference" / EXAMPLE / f"{layout}_seed42/summary.json").read_text())
            actual = aggregates[cell]["values_by_seed"]["42"]
            difference = abs(actual - previous["scores"]["oracle"])
            if difference > 1e-6:
                raise ValueError("Reused anchor DINO score changed")
            anchor_checks[cell] = {"previous": previous["scores"]["oracle"], "current": actual, "absolute_difference": difference}
    summary = {"example_id": EXAMPLE, "seeds": seeds, "new_generations": sum(not r["reused"] for r in rows),
               "reused_generations": sum(r["reused"] for r in rows), "command": shlex.join([sys.executable, *sys.argv]),
               "evaluation_script_sha256": sha256(Path(__file__)), "audit_script_sha256": sha256(ROOT / "temporal_artifacts.py"),
               "metric": {"name": "dinov2_vitb14_mean_aligned_frame_cls_cosine", "sample_frame_indices": indices.tolist(),
                          "preprocessing": "RGB, short edge 256 bicubic, center crop 224, ImageNet normalization, FP32",
                          "weights_sha256": sha256(weights), "backbone_source_sha256": sha256(dino_repo / "dinov2/hub/backbones.py"),
                          "interpretation": "Auxiliary whole-frame similarity; not identity correctness"},
               "rows": rows, "aggregate_scores": aggregates, "paired_effects": effects, "mean_effects": mean_effects,
               "pixel_diagnostics": diagnostics, "reused_anchor_metric_checks": anchor_checks,
               "artifact_audit": "artifact_verification.json", "comparison_videos": artifacts,
               "review_status": "See review.json for assistant visual inspection; user review remains separate",
               "scope": "One source example, three paired seeds; Oracle only; no memory training or IC-LoRA"}
    write_json(report / "summary.json", summary)
    for filename, data in [("results.csv", rows), ("paired_effects.csv", effects)]:
        with (report / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)
    print(json.dumps({"scores": aggregates, "mean_effects": mean_effects, "audit": "passed", "report": str(report)}, indent=2))


if __name__ == "__main__":
    main()
