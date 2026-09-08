"""Audit and evaluate A–E using the same cached DINOv2 recipe as earlier runs."""

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


def export_comparisons(report, videos, local):
    font = ImageFont.load_default(size=18)
    labels = {"gt": "GT", "A": "A: image x1 / one time", "B": "B: image x10 / one time",
              "C": "C: image x10 / spread", "D": "D: video / one time", "E": "E: video / spread"}
    # The right four panels form B,C / D,E. GT and A are the left column.
    grid = ["gt", "B", "C", "A", "D", "E"]
    frames = []
    sequences = {key: np.concatenate([local, video]) for key, video in videos.items()}
    for index in range(120):
        canvas = Image.new("RGB", (1536, 640), "#141923")
        draw = ImageDraw.Draw(canvas)
        for slot, key in enumerate(grid):
            x, y = slot % 3 * 512, slot // 3 * 320
            canvas.paste(Image.fromarray(sequences[key][index]), (x, y + 32))
            phase = "local" if index < 48 else "target"
            t = index / 24 if index < 48 else (index - 48) / 24
            draw.text((x + 6, y + 6), f"{labels[key]} | {phase} {t:.2f}s", fill="white", font=font)
        frames.append(np.asarray(canvas))
    artifact = write_video(report / "comparison.mp4", np.stack(frames), 24)
    Image.fromarray(frames[48 + 28]).save(report / "comparison_poster.jpg", quality=94)
    keys = ["gt", "A", "B", "C", "D", "E"]
    sheet = Image.new("RGB", (6 * 288, 6 * 190), "#141923")
    draw = ImageDraw.Draw(sheet)
    indices = np.linspace(0, 71, 6).round().astype(int)
    for row, frame in enumerate(indices):
        for col, key in enumerate(keys):
            x, y = col * 288, row * 190
            sheet.paste(Image.fromarray(videos[key][frame]).resize((288, 162)), (x, y + 28))
            draw.text((x + 5, y + 4), f"{key.upper()} | target {frame / 24:.2f}s", fill="white", font=font)
    sheet.save(report / "comparison_frames.jpg", quality=94)
    # Extra early-transition samples allow review of delayed cuts, not just mean scores.
    early_indices = [0, 2, 4, 6, 8, 12, 16, 20]
    early = Image.new("RGB", (6 * 256, len(early_indices) * 168), "#141923")
    draw = ImageDraw.Draw(early)
    for row, frame in enumerate(early_indices):
        for col, key in enumerate(keys):
            x, y = col * 256, row * 168
            early.paste(Image.fromarray(videos[key][frame]).resize((256, 144)), (x, y + 24))
            draw.text((x + 5, y + 3), f"{key.upper()} | {frame / 24:.3f}s", fill="white", font=font)
    early.save(report / "transition_frames.jpg", quality=94)
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], default=2)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["XFORMERS_DISABLED"] = "1"
    import torch
    from format_artifacts import audit_format
    from format_controls import EXAMPLE, CASES

    torch.set_num_threads(8)
    configs, audit = audit_format()
    report = ROOT / "reports/reference_format/seed42"
    report.mkdir(parents=True, exist_ok=True)
    write_json(report / "artifact_verification.json", audit)
    example = ROOT / "data" / EXAMPLE
    metadata = json.loads((example / "metadata.json").read_text())
    if sha256(example / "gt_target.mp4") != metadata["clips"]["target"]["sha256"]:
        raise ValueError("GT changed")
    videos = {"gt": read_rgb(example / "gt_target.mp4", 512, 288)}
    videos.update({case: read_rgb(Path(cfg["outputs"]["target"]["path"]), 512, 288) for case, cfg in configs.items()})
    if any(len(video) != 72 for video in videos.values()):
        raise ValueError("Target lengths differ")
    local = read_rgb(example / "local_context.mp4", 512, 288)
    oracle = read_rgb(example / "oracle_context.mp4", 512, 288)
    comparison = export_comparisons(report, videos, local)
    if not torch.cuda.is_available():
        raise RuntimeError("DINO evaluation requires GPU access")
    repo = Path("/home/minseok/.cache/torch/hub/facebookresearch_dinov2_main")
    weights = Path("/home/minseok/.cache/torch/hub/checkpoints/dinov2_vitb14_pretrain.pth")
    sys.path.insert(0, str(repo))
    from dinov2.hub.backbones import dinov2_vitb14

    model = dinov2_vitb14(pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model = model.eval().cuda()
    indices = np.linspace(0, 71, 12).round().astype(int)
    after_one_second = torch.tensor(indices >= 24)
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

    embeddings = {key: features(video[indices]) for key, video in videos.items()}
    embeddings["oracle_reference"] = features(oracle[indices])
    torch.save(embeddings, report / "dino_features.pt")
    ref_small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in oracle]).astype(np.float32)
    rows, diagnostics = [], {}
    for case in CASES:
        scores = (embeddings[case] * embeddings["gt"]).sum(dim=-1)
        rgb = videos[case].astype(np.float32)
        adjacent = np.abs(np.diff(rgb, axis=0)).mean(axis=(1, 2, 3))
        small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in videos[case][indices]]).astype(np.float32)
        nearest = [float(np.abs(ref_small - f).mean(axis=(1, 2, 3)).min()) for f in small]
        diagnostics[case] = {"dino_gt_frame_cosines": scores.tolist(), "adjacent_pixel_mae_0_255": float(adjacent.mean()),
                             "near_static_pair_fraction_mae_below_0_1": float((adjacent < 0.1).mean()),
                             "boundary_pixel_mae_0_255": float(np.abs(local[-1].astype(np.float32) - rgb[0]).mean()),
                             "oracle_nearest_frame_pixel_mae_128x72_mean": float(np.mean(nearest)),
                             "oracle_max_feature_cosine_mean": float((embeddings[case] @ embeddings["oracle_reference"].T).max(dim=1).values.mean())}
        rows.append({"case": case, "name": CASES[case]["name"], "seed": 42, "reference_tokens": CASES[case]["tokens"],
                     "reference_time_layout": CASES[case]["layout"], "reused": case in ("A", "E"),
                     "dino_gt_cosine": float(scores.mean()), "dino_gt_cosine_after_1s": float(scores[after_one_second].mean()),
                     "adjacent_pixel_mae_0_255": float(adjacent.mean())})
    previous = json.loads((ROOT / "reports/temporal_position/summary.json").read_text())
    anchor_checks = {}
    for case, cell in [("A", "image_past"), ("E", "video_past")]:
        before = previous["aggregate_scores"][cell]["values_by_seed"]["42"]
        current = next(r for r in rows if r["case"] == case)["dino_gt_cosine"]
        if abs(before - current) > 1e-6:
            raise ValueError("Reused anchor metric changed")
        anchor_checks[case] = {"previous": before, "current": current}
    by_case = {r["case"]: r for r in rows}
    contrasts = {f"{right}_minus_{left}": {metric: by_case[right][metric] - by_case[left][metric]
                                           for metric in ("dino_gt_cosine", "dino_gt_cosine_after_1s")}
                 for left, right in [("A", "B"), ("B", "C"), ("D", "E"), ("B", "D"), ("C", "E")]}
    summary = {"example_id": EXAMPLE, "seed": 42, "new_generations": 3, "reused_generations": 2,
               "command": shlex.join([sys.executable, *sys.argv]), "evaluation_script_sha256": sha256(Path(__file__)),
               "audit_script_sha256": sha256(ROOT / "format_artifacts.py"),
               "metric": {"name": "dinov2_vitb14_mean_aligned_frame_cls_cosine", "sample_frame_indices": indices.tolist(),
                          "after_1s_sample_indices": indices[indices >= 24].tolist(),
                          "after_1s_scope": "Supplementary fixed window selected before inspecting B/C/D outputs; not automatic transition detection",
                          "preprocessing": previous["metric"]["preprocessing"], "weights_sha256": sha256(weights),
                          "backbone_source_sha256": sha256(repo / "dinov2/hub/backbones.py")},
               "rows": rows, "contrasts": contrasts, "pixel_diagnostics": diagnostics, "anchor_metric_checks": anchor_checks,
               "comparison_video": comparison, "artifact_audit": "artifact_verification.json",
               "scope": "Single scene and seed; artificial duplication/coordinate collapse diagnosis; no training or IC-LoRA",
               "review_status": "See review.json for assistant sample-frame review; user review is separate"}
    write_json(report / "summary.json", summary)
    with (report / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"audit": "passed", "rows": rows, "contrasts": contrasts, "report": str(report)}, indent=2))


if __name__ == "__main__":
    main()
