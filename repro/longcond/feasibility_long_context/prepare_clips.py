"""Extract bounded pilot clips and retain a per-frame map to original source time."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import shlex
import sys

import av

from download_finevideo import write_json
from preview_candidates import preview

ROOT = Path(__file__).resolve().parent
CLIPS = {"local": "local_context", "target": "gt_target", "oracle": "oracle_context", "random": "random_context"}


def extract(source: Path, destination: Path, start: float, end: float, fps: int) -> dict:
    """Sample the most recent in-window source frame; never use a frame outside [start,end)."""
    times, frames = [], []
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        origin = float(stream.start_time * stream.time_base) if stream.start_time else 0.0
        container.seek(int((start + origin) / stream.time_base), stream=stream, backward=True)
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            time = float(frame.time) - origin
            if time >= end:
                break
            if time >= start:
                times.append(time)
                frames.append(frame.to_ndarray(format="rgb24"))
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f"Missing or nonmonotonic source timestamps: {source}, {start}, {end}")
    count = round((end - start) * fps)
    if count < 1 or abs(count / fps - (end - start)) > 1e-6:
        raise ValueError("Clip duration must be a positive integer number of output frames")
    requested = [start + i / fps for i in range(count)]
    indices = [max(0, bisect_right(times, time) - 1) for time in requested]
    selected = [times[i] for i in indices]
    temporary = destination.with_suffix(".tmp.mp4")
    with av.open(str(temporary), mode="w") as output:
        stream = output.add_stream("libx264", rate=fps)
        stream.width, stream.height = frames[0].shape[1], frames[0].shape[0]
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "18", "preset": "fast"}
        for index, source_index in enumerate(indices):
            frame = av.VideoFrame.from_ndarray(frames[source_index], format="rgb24")
            frame.pts, frame.time_base = index, Fraction(1, fps)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    with av.open(str(temporary)) as container:
        decoded = [float(frame.time) for frame in container.decode(video=0)]
        actual_duration = float(container.streams.video[0].duration * container.streams.video[0].time_base)
    if len(decoded) != count or any(abs(t - i / fps) > 1e-5 for i, t in enumerate(decoded)):
        raise ValueError(f"Encoded frame count/timestamps mismatch: {destination}")
    if abs(actual_duration - count / fps) > 1 / fps:
        raise ValueError(f"Encoded duration mismatch: {destination}")
    temporary.replace(destination)
    return {"file": destination.name, "source_interval_seconds": [start, end],
            "interval_convention": "start inclusive, end exclusive", "fps": fps,
            "frames": count, "duration_seconds": actual_duration,
            "width": frames[0].shape[1], "height": frames[0].shape[0], "audio_included": False,
            "sampling": "Most recent in-window frame, clamped to first frame at the left boundary",
            "source_frame_seconds": selected,
            "max_sampling_error_seconds": max(abs(a - b) for a, b in zip(requested, selected)),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "full_clip_decode_passed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/pilot_examples.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    fps = config["clip_fps"]
    report = {"command": shlex.join([sys.executable, *sys.argv]), "config": str(args.config.resolve()),
              "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
              "scope": config["purpose"], "examples": []}
    report_dir = ROOT / "reports/pilot"
    report_dir.mkdir(parents=True, exist_ok=True)
    sections = []
    for example in config["examples"]:
        sample = ROOT / "data/finevideo_candidates" / example["candidate_id"]
        provenance = json.loads((sample / "provenance.json").read_text())
        if provenance["revision"] != config["dataset_revision"]:
            raise ValueError("Source revision differs from pilot config")
        source = sample / "source.mp4"
        if hashlib.sha256(source.read_bytes()).hexdigest() != provenance["sha256"]:
            raise ValueError("Source checksum differs from recorded provenance")
        if example["local_end"] != example["target_start"]:
            raise ValueError("Local and target must be adjacent")
        intervals = {kind: (example[kind + "_start"], example[kind + "_end"])
                     for kind in CLIPS if kind + "_start" in example}
        for kind, (start, end) in intervals.items():
            if not 0 <= start < end <= provenance["video_probe"]["duration_seconds"]:
                raise ValueError(f"Out of bounds: {kind}")
            if kind in ("oracle", "random") and end > example["local_start"]:
                raise ValueError("Distant evidence must precede local context")
        if "oracle" in intervals:
            if "random" not in intervals or abs((intervals["oracle"][1] - intervals["oracle"][0]) -
                                               (intervals["random"][1] - intervals["random"][0])) > 1e-6:
                raise ValueError("Oracle and random evidence duration must match")
            if max(intervals["oracle"][0], intervals["random"][0]) < min(intervals["oracle"][1], intervals["random"][1]):
                raise ValueError("Oracle and random intervals must not overlap")
        directory = ROOT / "data" / example["example_id"]
        directory.mkdir(parents=True, exist_ok=True)
        link = directory / "source.mp4"
        if not link.exists() and not link.is_symlink():
            link.symlink_to(Path("../finevideo_candidates") / example["candidate_id"] / "source.mp4")
        if link.resolve() != source.resolve():
            raise ValueError(f"Existing source link differs: {link}")
        metadata = {**example, "source_provenance": provenance, "clip_fps": fps,
                    "generation_completed": False, "clips": {}}
        if "oracle" in intervals:
            metadata["dependency_gap_seconds"] = example["target_start"] - example["oracle_end"]
            metadata["dependency_gap_definition"] = "target_start minus oracle_end in original source time"
        cards = []
        for kind, (start, end) in intervals.items():
            basename = CLIPS[kind]
            metadata["clips"][kind] = extract(source, directory / f"{basename}.mp4", start, end, fps)
            sheet_name = f'{example["example_id"]}_{kind}.jpg'
            preview(directory / f"{basename}.mp4", [i * (end - start - 1 / fps) / 11 for i in range(12)], report_dir / sheet_name)
            rel = f'../../data/{example["example_id"]}/{basename}.mp4'
            cards.append(f'<h3>{kind}: [{start:.6f}, {end:.6f}) source seconds</h3><img src="{sheet_name}" alt="{kind} source clip frames">'
                         f'<video controls preload="none" src="{rel}"></video>')
        write_json(directory / "metadata.json", metadata)
        report["examples"].append(metadata)
        sections.append(f'<article><h2>{example["example_id"]}</h2><p>{html.escape(example["task_type"])}</p>'
                        f'<p>Prompt: {html.escape(example["prompt"])}</p>' + ''.join(cards) + '<pre>'
                        + html.escape(json.dumps(example["review"], ensure_ascii=False, indent=2)) + '</pre></article>')
        print(f'Prepared {example["example_id"]}: {len(intervals)} clips; full clip decode passed', flush=True)
    write_json(report_dir / "preparation.json", report)
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Stage 1 pilot inputs</title>'
            '<style>body{max-width:1180px;margin:30px auto;font:16px sans-serif}article{border-top:2px solid #444;padding:20px 0}'
            'img{width:100%}video{width:640px;max-width:100%}pre{white-space:pre-wrap}</style>'
            '<h1>Stage 1 pilot inputs</h1><p>Source clips only. No generated outputs. '
            'Evaluation attributes are reviewer annotations and must not enter generation prompts.</p>' + ''.join(sections) + '</html>')
    (report_dir / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
