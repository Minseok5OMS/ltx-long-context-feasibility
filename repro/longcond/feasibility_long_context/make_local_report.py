"""Compare a completed local-only run with GT, loading GT only after generation."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import shlex
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from run_generation import read_rgb, sha256, write_json, write_video

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "outputs/pilot_000_local_cooking/local_seed42")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    config = json.loads((run / "config.json").read_text())
    if config["status"] != "completed":
        raise ValueError("Generation must complete before reading GT")
    example = Path(config["example"])
    metadata = json.loads((example / "metadata.json").read_text())
    gt_info = metadata["clips"]["target"]
    gt_path = example / gt_info["file"]
    if sha256(gt_path) != gt_info["sha256"]:
        raise ValueError("GT differs from prepared clip checksum")
    width, height, fps = config["width"], config["height"], config["fps"]
    local = read_rgb(example / metadata["clips"]["local"]["file"], width, height)
    gt = read_rgb(gt_path, width, height)
    generated = read_rgb(run / "local_only.mp4", width, height)
    if len(gt) != config["target_frames"] or gt.shape != generated.shape:
        raise ValueError("GT and generated target dimensions/frame counts differ")
    gt_output = write_video(run / "gt_target.mp4", gt, fps)

    left, right = np.concatenate([local, gt]), np.concatenate([local, generated])
    font = ImageFont.load_default(size=18)
    comparison = []
    for index, (a, b) in enumerate(zip(left, right, strict=True)):
        canvas = Image.new("RGB", (width * 2, height + 32), "#121823")
        canvas.paste(Image.fromarray(a), (0, 32))
        canvas.paste(Image.fromarray(b), (width, 32))
        draw = ImageDraw.Draw(canvas)
        phase = "LOCAL INPUT" if index < len(local) else "GT TARGET"
        right_phase = "LOCAL INPUT" if index < len(local) else "GENERATED TARGET"
        draw.text((8, 6), f"{phase} | {index / fps:.2f}s", font=font, fill="white")
        draw.text((width + 8, 6), f"{right_phase} | seed {config['seed']}", font=font, fill="white")
        comparison.append(np.asarray(canvas))
    comparison_output = write_video(run / "comparison.mp4", np.stack(comparison), fps)

    report_dir = ROOT / "reports/local_smoke"
    report_dir.mkdir(parents=True, exist_ok=True)
    indices = np.linspace(0, len(gt) - 1, 6).round().astype(int)
    tile_w, tile_h = 256, 172
    sheet = Image.new("RGB", (tile_w * len(indices), tile_h * 2), "#121823")
    draw = ImageDraw.Draw(sheet)
    for row, (label, video) in enumerate([("GT", gt), ("Generated", generated)]):
        for col, index in enumerate(indices):
            frame = Image.fromarray(video[index])
            frame.thumbnail((tile_w, tile_h - 28))
            x, y = col * tile_w, row * tile_h
            sheet.paste(frame, (x + (tile_w - frame.width) // 2, y))
            draw.text((x + 5, y + tile_h - 24), f"{label} {index / fps:.3f}s", font=font, fill="white")
    sheet.save(report_dir / "target_comparison.jpg", quality=93)
    local_sheet = Image.new("RGB", (tile_w * 3, tile_h), "#121823")
    draw = ImageDraw.Draw(local_sheet)
    for col, (label, frame) in enumerate([("Last local", local[-1]), ("First GT", gt[0]), ("First generated", generated[0])]):
        tile = Image.fromarray(frame)
        tile.thumbnail((tile_w, tile_h - 28))
        local_sheet.paste(tile, (col * tile_w + (tile_w - tile.width) // 2, 0))
        draw.text((col * tile_w + 5, tile_h - 24), label, font=font, fill="white")
    local_sheet.save(report_dir / "boundary.jpg", quality=93)

    def adjacent_mad(video):
        return np.abs(np.diff(video.astype(np.float32), axis=0)).mean(axis=(1, 2, 3))

    g_motion, t_motion = adjacent_mad(generated), adjacent_mad(gt)
    summary = {
        "scope": "Local continuation smoke test; no oracle comparison or learned perceptual metric",
        "command": shlex.join([sys.executable, *sys.argv]), "run_directory": str(run),
        "run_config_sha256": sha256(run / "config.json"),
        "generation_completed": True, "gt_loaded_after_generation": True,
        "generated_frames": len(generated), "target_seconds": len(generated) / fps,
        "local_latent_max_abs_error": config["final_local_latent_max_abs_error"],
        "generation_seconds": config["total_seconds"], "peak_gpu_allocated_gib": config["peak_gpu_allocated_gib"],
        "pixel_diagnostics_0_255_not_benchmark_scores": {
            "generated_vs_gt_mae": float(np.abs(generated.astype(np.float32) - gt.astype(np.float32)).mean()),
            "generated_adjacent_frame_mae": float(g_motion.mean()),
            "gt_adjacent_frame_mae": float(t_motion.mean()),
            "last_local_to_first_generated_mae": float(np.abs(local[-1].astype(np.float32) - generated[0].astype(np.float32)).mean()),
            "last_local_to_first_gt_mae": float(np.abs(local[-1].astype(np.float32) - gt[0].astype(np.float32)).mean()),
            "generated_near_static_pair_fraction_mae_below_0_1": float((g_motion < 0.1).mean())},
        "derived_outputs": {"gt_target": gt_output, "comparison": comparison_output},
        "visual_review": "See LOCAL_SMOKE_RESULT.md; automatic motion differences alone do not establish plausible motion"}
    write_json(report_dir / "summary.json", summary)
    run_relative = Path(os.path.relpath(run, report_dir))
    cards = ''.join(f'<h2>{label}</h2><video controls preload="metadata" src="{run_relative / filename}"></video>'
                    for label, filename in [("GT versus local-only, including local boundary", "comparison.mp4"),
                                            ("Generated target only", "local_only.mp4"),
                                            ("GT target", "gt_target.mp4")])
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Local-only generation diagnostic</title>'
            '<style>body{max-width:1500px;margin:25px auto;font:16px sans-serif;background:#121823;color:#eee}'
            'video{max-width:100%;width:1024px}img{max-width:100%}pre{white-space:pre-wrap}a{color:#9ad2ff}</style>'
            '<h1>Local-only generation diagnostic</h1>'
            f'<p>{html.escape(config["prompt"])}</p>'
            '<p>One seed, 8-step distilled stage 1, 512x288 by default. '
            'No long-range evidence comparison has run.</p><p><a href="../../LOCAL_SMOKE_RESULT.md">Review notes</a></p>'
            + cards + '<h2>Boundary</h2><img src="boundary.jpg" alt="Last local and first target frames">'
            '<h2>Target timeline</h2><img src="target_comparison.jpg" alt="GT and generated target frames">'
            '<h2>Recorded checks</h2><pre>' + html.escape(json.dumps(summary, indent=2)) + '</pre></html>')
    (report_dir / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
