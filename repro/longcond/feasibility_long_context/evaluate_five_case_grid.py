"""Audit the five-case factorial grid and evaluate all 25 new/reused outputs."""

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
    font = ImageFont.load_default(size=19)
    small_font = ImageFont.load_default(size=15)
    keys = ["gt", "local", "image_past", "image_target", "video_past", "video_target"]
    labels = {"gt": "GT (evaluation only)", "local": "Local-only", "image_past": "Image / Past",
              "image_target": "Image / Target", "video_past": "Video / Past", "video_target": "Video / Target"}
    sequences = {k: np.concatenate([local, video]) for k, video in videos.items()}
    frames = []
    for index in range(120):
        canvas = Image.new("RGB", (1024, 936), "#141923")
        draw = ImageDraw.Draw(canvas)
        phase, t = ("local", index/24) if index < 48 else ("target", (index-48)/24)
        for slot, key in enumerate(keys):
            x, y = (slot % 2)*512, (slot//2)*312
            canvas.paste(Image.fromarray(sequences[key][index]), (x, y+24))
            draw.text((x+5, y+1), f"{labels[key]} | {phase} {t:.2f}s", fill="white", font=font)
        frames.append(np.asarray(canvas))
    artifact = write_video(report / "comparison.mp4", np.stack(frames), 24)
    Image.fromarray(frames[48+32]).save(report / "comparison_poster.jpg", quality=95)
    indices = [0, 8, 16, 24, 40, 56, 71]
    sheet = Image.new("RGB", (1536, len(indices)*170), "#141923")
    draw = ImageDraw.Draw(sheet)
    for row, index in enumerate(indices):
        for col, key in enumerate(keys):
            x, y = col*256, row*170
            sheet.paste(Image.fromarray(videos[key][index]).resize((256,144)), (x,y+26))
            draw.text((x+4,y+3),f"{labels[key]} | {index/24:.2f}s",fill="white",font=small_font)
    sheet.save(report / "comparison_frames.jpg", quality=96)
    for key in keys:
        Image.fromarray(videos[key][32]).save(report / f"{key}_poster.jpg", quality=95)
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], default=2)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["XFORMERS_DISABLED"] = "1"
    import torch
    from five_case_grid_artifacts import audit_grid

    torch.set_num_threads(8)
    report = ROOT / "reports/five_case_grid/seed42"
    report.mkdir(parents=True, exist_ok=True)
    configs, audit = audit_grid()
    write_json(report / "artifact_verification.json", audit)
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
    after = torch.tensor(indices >= 24)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda()
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()

    def features(frames):
        arrays = []
        for rgb in frames:
            img = Image.fromarray(rgb)
            ratio = 256/min(img.size)
            img = img.resize((round(img.width*ratio), round(img.height*ratio)), Image.Resampling.BICUBIC)
            x, y = (img.width-224)//2, (img.height-224)//2
            arrays.append(np.asarray(img.crop((x, y, x+224, y+224))))
        batch = torch.from_numpy(np.stack(arrays).copy()).permute(0, 3, 1, 2).cuda().float()/255
        with torch.inference_mode():
            encoded = model((batch-mean)/std)
        return torch.nn.functional.normalize(encoded.float(), dim=-1).cpu()

    rows, diagnostics, embeddings, comparisons = [], {}, {}, {}
    protocol = json.loads((ROOT / "configs/five_case_examples.json").read_text())
    for example in protocol["examples"]:
        name = example["example_id"]
        directory = ROOT / "data" / name
        case_report = report / name
        case_report.mkdir(exist_ok=True)
        local = read_rgb(directory / "local_context.mp4", 512, 288)
        videos = {"gt": read_rgb(directory / "gt_target.mp4", 512, 288)}
        videos.update({mode: read_rgb(Path(cfg["outputs"]["target"]["path"]), 512, 288) for mode, cfg in configs[name].items()})
        assert all(len(v) == 72 for v in videos.values())
        ref = np.asarray(Image.open(ROOT / "outputs" / name / "five_case_inputs_512x288/oracle_image.png"))
        comparisons[name] = export_comparisons(case_report, videos, local)
        em = {key: features(video[indices]) for key, video in videos.items()}
        em["reference"] = features([ref])
        reference_video = read_rgb(directory / "oracle_context.mp4", 512, 288)
        em["reference_video"] = features(reference_video[indices])
        ref_video_small = np.stack([np.asarray(Image.fromarray(f).resize((128,72))) for f in reference_video]).astype(np.float32)
        embeddings[name] = em
        ref_small = np.asarray(Image.fromarray(ref).resize((128, 72))).astype(np.float32)
        diagnostics[name] = {}
        for mode in videos:
            rgb = videos[mode].astype(np.float32)
            adjacent = np.abs(np.diff(rgb, axis=0)).mean(axis=(1, 2, 3))
            small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in videos[mode][indices]]).astype(np.float32)
            scores = (em[mode]*em["gt"]).sum(dim=-1)
            diagnostics[name][mode] = {
                "dino_gt_frame_cosines": scores.tolist(),
                "adjacent_pixel_mae_0_255": float(adjacent.mean()),
                "near_static_pair_fraction_mae_below_0_1": float((adjacent < 0.1).mean()),
                "boundary_pixel_mae_0_255": float(np.abs(local[-1].astype(np.float32)-rgb[0]).mean()),
                "oracle_image_pixel_mae_128x72": np.abs(small-ref_small).mean(axis=(1, 2, 3)).tolist(),
                "oracle_image_feature_cosines": (em[mode] @ em["reference"].T).flatten().tolist(),
                "oracle_video_max_feature_cosine_mean": float((em[mode] @ em["reference_video"].T).max(dim=1).values.mean()),
                "oracle_video_nearest_pixel_mae_128x72_mean": float(np.mean([np.abs(ref_video_small-f).mean(axis=(1,2,3)).min() for f in small]))}
            if mode != "gt":
                cfg = configs[name][mode]
                rows.append({"example_id": name, "title_ko": example["title_ko"], "mode": mode, "seed": 42,
                             "reference_kind": "none" if mode == "local" else mode.split("_")[0],
                             "reference_position": "none" if mode == "local" else mode.split("_")[1],
                             "reused": mode in ("local", "image_past"),
                             "reference_tokens": cfg["reference_tokens"],
                             "source_dependency_gap_seconds": cfg["source_dependency_gap_seconds"],
                             "dino_gt_cosine": float(scores.mean()), "dino_gt_cosine_after_1s": float(scores[after].mean()),
                             "adjacent_pixel_mae_0_255": float(adjacent.mean()),
                             "generation_seconds_including_load": cfg["total_seconds"],
                             "peak_gpu_allocated_gib": cfg["peak_gpu_allocated_gib"]})
        print(f"Evaluated {name}", flush=True)
    torch.save(embeddings, report / "dino_features.pt")
    contrasts, anchor_checks = {}, []
    previous = json.loads((ROOT / "reports/five_cases/seed42/summary.json").read_text())
    for name in configs:
        pair = {r["mode"]: r for r in rows if r["example_id"] == name}
        contrasts[name] = {}
        for metric in ("dino_gt_cosine", "dino_gt_cosine_after_1s"):
            image_effect = pair["image_target"][metric]-pair["image_past"][metric]
            video_effect = pair["video_target"][metric]-pair["video_past"][metric]
            contrasts[name][metric] = {"image_target_minus_past": image_effect, "video_target_minus_past": video_effect,
                                      "interaction_video_effect_minus_image_effect": video_effect-image_effect,
                                      "oracle_minus_local": {cell:pair[cell][metric]-pair["local"][metric] for cell in ("image_past","image_target","video_past","video_target")}}
        for cell, old_mode in (("local","local"),("image_past","oracle")):
            old_row = next(r for r in previous["rows"] if r["example_id"]==name and r["mode"]==old_mode)
            for metric in ("dino_gt_cosine","dino_gt_cosine_after_1s"):
                difference = pair[cell][metric]-old_row[metric]
                assert abs(difference) < 1e-6, (name,cell,metric,difference)
                anchor_checks.append({"example_id":name,"cell":cell,"metric":metric,"difference":difference})
    condition_means = {cell: {metric: float(np.mean([r[metric] for r in rows if r["mode"]==cell]))
                              for metric in ("dino_gt_cosine","dino_gt_cosine_after_1s")}
                       for cell in ("local","image_past","image_target","video_past","video_target")}
    summary = {"seed": 42, "examples": 5, "new_generations": 15, "reused_generations": 10, "reference_cells": 20,
               "command": shlex.join([sys.executable, *sys.argv]),
               "evaluation_script_sha256": sha256(Path(__file__)), "audit_script_sha256": sha256(ROOT / "five_case_grid_artifacts.py"),
               "metric": {"name": "dinov2_vitb14_mean_aligned_frame_cls_cosine", "precision": "float32",
                          "sample_frame_indices": indices.tolist(), "after_1s_sample_indices": indices[indices>=24].tolist(),
                          "preprocessing": "RGB; resize short edge 256 bicubic; center crop 224; ImageNet normalization; normalized CLS",
                          "weights_sha256": sha256(weights), "backbone_source_sha256": sha256(repo / "dinov2/hub/backbones.py"),
                          "meaning": "Auxiliary whole-frame similarity, not identity accuracy; after-1s is a common fixed window, not transition detection"},
               "rows": rows, "contrasts": contrasts, "condition_means": condition_means, "anchor_metric_checks": anchor_checks, "pixel_diagnostics": diagnostics,
               "comparison_videos": comparisons, "artifact_audit": "artifact_verification.json",
               "scope": "Five original examples; image/video x past/target; fixed seed42 and unchanged prompts; selected past evidence utilization, not learned memory or a state/event benchmark", "qualitative_review": "review.json"}
    write_json(report / "summary.json", summary)
    with (report / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"audit":"passed", "condition_means":condition_means, "contrasts":contrasts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
