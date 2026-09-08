"""Audit paired conditions, score with cached DINOv2, and render reference comparison reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import shlex
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from run_generation import ROOT, read_rgb, sha256, write_json, write_video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, default=ROOT / "data/pilot_001_interview_return")
    parser.add_argument("--layout", choices=["past", "target_guide"], default="past")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], default=0)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["XFORMERS_DISABLED"] = "1"
    import torch
    from reference_controls import tensor_hash

    if not torch.cuda.is_available():
        raise RuntimeError("Evaluation requires GPU access")
    torch.set_num_threads(8)
    example = args.example.resolve()
    group = ROOT / "outputs" / example.name / f"reference_{args.layout}_seed{args.seed}"
    configs = {m: json.loads((group / m / "config.json").read_text()) for m in ["local", "random", "oracle"]}
    common = configs["local"]
    equality_keys = ["example_id", "layout", "seed", "models", "ltx_commit", "script_sha256", "controls_sha256",
                     "prompt", "prompt_enhancement", "fps", "width", "height", "prefix_frames", "target_frames", "total_frames",
                     "base_video_tokens", "prefix_tokens", "common_time_shift_seconds", "target_model_time_range",
                     "common_inputs_sha256", "local_latent_sha256", "prompt_context_hashes", "sigmas", "sampler", "eta", "s_noise",
                     "precision", "guidance", "audio", "initial_noise_seed", "step_noise_seed", "decoder_seed", "noise_policy",
                     "base_video_positions_sha256", "audio_positions_sha256", "noise_audit"]
    for mode, cfg in configs.items():
        if cfg["status"] != "completed" or cfg["final_frozen_max_abs_error"] != 0 or cfg["gt_video_opened"]:
            raise ValueError(f"Incomplete or invalid run: {mode}")
        for key in equality_keys:
            if cfg[key] != common[key]:
                raise ValueError(f"Uncontrolled difference in {key}: {mode}")
        if len(cfg["denoising_trace"]) != 8 or any(t["frozen_max_abs_error"] != 0 for t in cfg["denoising_trace"]):
            raise ValueError("Denoising condition check failed")
        for artifact in cfg["outputs"].values():
            if sha256(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Generated artifact changed")
        noise = torch.load(group / mode / "target_initial_noise.pt", map_location="cpu", weights_only=True)
        steps = torch.load(group / mode / "target_step_noises.pt", map_location="cpu", weights_only=True)
        if tensor_hash(noise) != cfg["noise_audit"]["initial"][0]["target_sha256"]:
            raise ValueError("Saved initial noise does not match audit")
        if [tensor_hash(n) for n in steps] != [r["target_sha256"] for r in cfg["noise_audit"]["ancestral"] if r["modality"] == "video"]:
            raise ValueError("Saved ancestral noise does not match audit")
    if common["reference_tokens"] != 0 or configs["random"]["reference_tokens"] != configs["oracle"]["reference_tokens"]:
        raise ValueError("Reference token budget mismatch")
    metadata = json.loads((example / "metadata.json").read_text())
    if sha256(example / "gt_target.mp4") != metadata["clips"]["target"]["sha256"]:
        raise ValueError("GT clip changed")
    width, height, fps = common["width"], common["height"], common["fps"]
    videos = {"gt": read_rgb(example / "gt_target.mp4", width, height)}
    videos.update({mode: read_rgb(Path(cfg["outputs"]["target"]["path"]), width, height) for mode, cfg in configs.items()})
    if any(len(v) != common["target_frames"] for v in videos.values()):
        raise ValueError("Target lengths differ")
    local = read_rgb(example / "local_context.mp4", width, height)
    references = {kind: read_rgb(example / f"{kind}_context.mp4", width, height) for kind in ["random", "oracle"]}
    report = ROOT / "reports/reference" / example.name / f"{args.layout}_seed{args.seed}"
    report.mkdir(parents=True, exist_ok=True)
    dino_repo = Path("/home/minseok/.cache/torch/hub/facebookresearch_dinov2_main")
    weights = Path("/home/minseok/.cache/torch/hub/checkpoints/dinov2_vitb14_pretrain.pth")
    sys.path.insert(0, str(dino_repo))
    from dinov2.hub.backbones import dinov2_vitb14

    model = dinov2_vitb14(pretrained=False)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    model = model.eval().to("cuda:0")
    indices = np.linspace(0, len(videos["gt"]) - 1, 12).round().astype(int)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda()
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()

    def features(frames):
        # Standard aspect-preserving short-edge 256, center crop 224; all modes share it.
        arrays = []
        for rgb in frames:
            img = Image.fromarray(rgb)
            ratio = 256 / min(img.size)
            img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.Resampling.BICUBIC)
            img = ImageOps.crop(img, border=0)
            x, y = (img.width - 224) // 2, (img.height - 224) // 2
            arrays.append(np.asarray(img.crop((x, y, x + 224, y + 224))))
        batch = torch.from_numpy(np.stack(arrays).copy()).permute(0, 3, 1, 2).cuda().float() / 255
        with torch.inference_mode():
            encoded = model((batch - mean) / std)
        return torch.nn.functional.normalize(encoded.float(), dim=-1).cpu()

    embeddings = {name: features(video[indices]) for name, video in videos.items()}
    embeddings.update({name + "_reference": features(video[np.linspace(0, len(video) - 1, 12).round().astype(int)]) for name, video in references.items()})
    torch.save(embeddings, report / "dino_features.pt")
    scores, diagnostics = {}, {}
    for mode in configs:
        frame_scores = (embeddings[mode] * embeddings["gt"]).sum(dim=-1)
        scores[mode] = float(frame_scores.mean())
        rgb = videos[mode].astype(np.float32)
        adjacent = np.abs(np.diff(rgb, axis=0)).mean(axis=(1, 2, 3))
        small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in videos[mode][indices]]).astype(np.float32)
        ref_small = np.stack([np.asarray(Image.fromarray(f).resize((128, 72))) for f in references["oracle"]]).astype(np.float32)
        nearest_mae = [float(np.abs(ref_small - frame).mean(axis=(1, 2, 3)).min()) for frame in small]
        diagnostics[mode] = {"dino_gt_frame_cosines": frame_scores.tolist(),
                             "adjacent_pixel_mae_0_255": float(adjacent.mean()),
                             "near_static_pair_fraction_mae_below_0_1": float((adjacent < 0.1).mean()),
                             "boundary_pixel_mae_0_255": float(np.abs(local[-1].astype(np.float32) - rgb[0]).mean()),
                             "oracle_nearest_frame_pixel_mae_128x72_mean": float(np.mean(nearest_mae)),
                             "oracle_max_feature_cosine_mean": float((embeddings[mode] @ embeddings["oracle_reference"].T).max(dim=1).values.mean())}
    summary = {"example_id": example.name, "layout": args.layout, "seed": args.seed, "scope": "Prompted-cut reference utilization diagnostic",
               "command": shlex.join([sys.executable, *sys.argv]), "group_directory": str(group),
               "paired_controls": {"status": "passed", "equal_fields": equality_keys,
                                   "saved_initial_and_all_7_step_noises_match": True,
                                   "reference_tokens": {m: c["reference_tokens"] for m, c in configs.items()}},
               "metric": {"name": "dinov2_vitb14_mean_aligned_frame_cls_cosine", "sample_frame_indices": indices.tolist(),
                          "preprocessing": "RGB, short edge 256 bicubic, center crop 224, ImageNet normalization, FP32",
                          "weights_path": str(weights), "weights_sha256": sha256(weights), "local_model_repo": str(dino_repo),
                          "backbone_source_sha256": sha256(dino_repo / "dinov2/hub/backbones.py"),
                          "interpretation": "Auxiliary whole-frame similarity, not identity correctness or causal memory evidence"},
               "scores": scores, "oracle_minus_local": scores["oracle"] - scores["local"],
               "oracle_minus_random": scores["oracle"] - scores["random"], "pixel_diagnostics": diagnostics,
               "source_dependency_gap_seconds": common["source_dependency_gap_seconds"],
               "config_sha256": {m: sha256(group / m / "config.json") for m in configs},
               "review_status": "Requires visual review; see group review.json and REFERENCE_RESULT.md"}
    write_json(report / "summary.json", summary)

    font = ImageFont.load_default(size=18)
    labels = ["GT", "Local only", "Local + Random", "Local + Oracle"]
    sequences = [np.concatenate([local, videos[k]]) for k in ["gt", "local", "random", "oracle"]]
    comparison = []
    for i in range(len(sequences[0])):
        canvas = Image.new("RGB", (width * 4, height + 32), "#141923")
        draw = ImageDraw.Draw(canvas)
        for j, (label, sequence) in enumerate(zip(labels, sequences)):
            canvas.paste(Image.fromarray(sequence[i]), (j * width, 32))
            phase = "local" if i < len(local) else "target"
            draw.text((j * width + 6, 6), f"{label} | {phase} {i / fps:.2f}s", fill="white", font=font)
        comparison.append(np.asarray(canvas))
    write_video(group / "comparison.mp4", np.stack(comparison), fps)
    write_video(group / "gt_target.mp4", videos["gt"], fps)
    tile_w, tile_h = 288, 190
    sheet = Image.new("RGB", (4 * tile_w, 6 * tile_h), "#141923")
    draw = ImageDraw.Draw(sheet)
    for row, frame_index in enumerate(np.linspace(0, len(videos["gt"]) - 1, 6).round().astype(int)):
        for col, (label, key) in enumerate(zip(labels, ["gt", "local", "random", "oracle"])):
            tile = Image.fromarray(videos[key][frame_index]); tile.thumbnail((tile_w, tile_h - 28))
            x, y = col * tile_w, row * tile_h
            sheet.paste(tile, (x + (tile_w - tile.width) // 2, y))
            draw.text((x + 5, y + tile_h - 24), f"{label} {frame_index / fps:.2f}s", fill="white", font=font)
    sheet.save(report / "comparison.jpg", quality=92)
    rel = lambda path: os.path.relpath(path, report)
    cells = ''.join(f'<td>{scores[m]:.4f}</td>' for m in ["local", "random", "oracle"])
    references_html = ''.join(f'<h3>{kind} context</h3><video controls preload="none" src="{rel(example / (kind + "_context.mp4"))}"></video>' for kind in ["local", "random", "oracle"])
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Reference comparison</title>'
            '<style>body{max-width:1500px;margin:25px auto;font:16px sans-serif;background:#141923;color:#eee}video,img{max-width:100%}'
            'video{width:1152px}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{padding:12px;border:1px solid #888}</style>'
            f'<h1>{example.name} / {args.layout} / seed {args.seed}</h1><p>{html.escape(common["prompt"])}</p>'
            '<p>Paired noise, prompt, local latent and target positions verified. DINO is auxiliary similarity.</p>'
            f'<table><tr><th>Local</th><th>Random</th><th>Oracle</th></tr><tr>{cells}</tr></table>'
            f'<h2>GT | Local | Random | Oracle</h2><video controls preload="metadata" src="{rel(group / "comparison.mp4")}"></video>'
            '<img src="comparison.jpg" alt="Generated target timeline">' + references_html + '<h2>Audit</h2><pre>'
            + html.escape(json.dumps(summary, indent=2)) + '</pre></html>')
    (report / "index.html").write_text(page, encoding="utf-8")
    # Rebuild the table from completed evaluations, keeping diagnostic layouts separate.
    rows = []
    for path in sorted((ROOT / "reports/reference").glob("*/*/summary.json")):
        s = json.loads(path.read_text())
        rows.append({"example_id": s["example_id"], "layout": s["layout"], "seed": s["seed"], "dependency_type": "character",
                     "dependency_gap_seconds": s["source_dependency_gap_seconds"], "score_name": s["metric"]["name"],
                     "local_only_score": s["scores"]["local"], "random_score": s["scores"]["random"], "oracle_score": s["scores"]["oracle"],
                     "hard_negative_score": "", "oracle_minus_local": s["oracle_minus_local"], "oracle_minus_random": s["oracle_minus_random"]})
    with (ROOT / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"report": str(report / "index.html"), "scores": scores,
                      "oracle_minus_local": summary["oracle_minus_local"], "oracle_minus_random": summary["oracle_minus_random"],
                      "paired_controls": "passed"}, indent=2))


if __name__ == "__main__":
    main()
