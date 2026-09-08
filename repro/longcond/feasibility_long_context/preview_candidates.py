"""Make timestamped contact sheets from downloaded videos, without model inference."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shlex
import sys

import av
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent


def preview(source: Path, times: list[float], destination: Path) -> list[dict]:
    cell_w, cell_h, columns = 288, 190, 4
    sheet = Image.new("RGB", (columns * cell_w, ((len(times) + columns - 1) // columns) * cell_h), "#171b22")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)
    records = []
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        origin = float(stream.start_time * stream.time_base) if stream.start_time else 0.0
        for index, requested in enumerate(times):
            container.seek(int((requested + origin) / stream.time_base), stream=stream, backward=True)
            selected = None
            actual = None
            for frame in container.decode(stream):
                if frame.time is None:
                    continue
                actual = float(frame.time) - origin
                if actual + 1e-6 >= requested:
                    selected = frame.to_image()
                    break
            if selected is None:
                raise ValueError(f"No frame at or after {requested:.3f}s in {source}")
            tile = ImageOps.contain(selected, (cell_w - 8, cell_h - 30))
            x, y = (index % columns) * cell_w, (index // columns) * cell_h
            sheet.paste(tile, (x + (cell_w - tile.width) // 2, y + 3))
            draw.text((x + 6, y + cell_h - 24), f"{actual:.3f}s", fill="white", font=font)
            records.append({"requested_seconds": requested, "decoded_seconds": actual})
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=88)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", help="Optional candidate ID; default: all manifest candidates")
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--end", type=float)
    args = parser.parse_args()
    if not 2 <= args.frames <= 120 or args.start < 0:
        parser.error("Expected 2 <= frames <= 120 and start >= 0")
    manifest = json.loads((ROOT / "data/finevideo_candidates/manifest.json").read_text())
    candidates = [c for c in manifest["candidates"] if not args.candidate or c["id"] == args.candidate]
    if not candidates:
        parser.error("No matching candidate")
    report_dir = ROOT / "reports/candidates"
    report_dir.mkdir(parents=True, exist_ok=True)
    sections = []
    review_log = {"command": shlex.join([sys.executable, *sys.argv]),
                  "scope": "Sparse decoded frames only; no oracle validation or model output", "videos": []}
    suffix = "overview" if args.start == 0 and args.end is None else f"{args.start:g}-{args.end if args.end is not None else 'end'}"
    for candidate in candidates:
        sample_id = candidate["id"]
        sample_dir = ROOT / "data/finevideo_candidates" / sample_id
        duration = candidate["video_probe"]["duration_seconds"]
        end = min(args.end if args.end is not None else duration - 0.25, duration - 0.1)
        if end <= args.start:
            raise ValueError(f"Invalid preview interval for {sample_id}")
        times = [args.start + (end - args.start) * i / (args.frames - 1) for i in range(args.frames)]
        sheet_name = f"{sample_id}_{suffix}.jpg"
        frames = preview(sample_dir / "source.mp4", times, report_dir / sheet_name)
        title = candidate.get("youtube_title") or sample_id
        metadata = json.loads((sample_dir / "finevideo_metadata.json").read_text())
        details = {key: metadata.get(key) for key in ("content_parent_category", "content_fine_category", "content_metadata")}
        sections.append(f'<article><h2>{html.escape(title)}</h2><p>{sample_id} | {duration:.2f}s | Unreviewed candidate</p>'
                        f'<a href="{sheet_name}"><img src="{sheet_name}" alt="Timestamped source frames"></a>'
                        f'<video controls preload="none" src="../../data/finevideo_candidates/{sample_id}/source.mp4"></video>'
                        '<details><summary>Automatic source metadata (selection only)</summary><pre>'
                        + html.escape(json.dumps(details, ensure_ascii=False, indent=2)) + '</pre></details></article>')
        review_log["videos"].append({"id": sample_id, "contact_sheet": sheet_name, "frames": frames})
        print(f"Created {report_dir / sheet_name}", flush=True)
    page_name = "index" if not args.candidate else args.candidate
    page_name += f"_{suffix}"
    page = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>FineVideo candidate review</title>'
            '<style>body{max-width:1180px;margin:30px auto;font:16px sans-serif;background:#10141b;color:#eee}'
            'article{margin:32px 0;padding:16px;border:1px solid #526174}img{width:100%}'
            'video{width:640px;max-width:100%}pre{white-space:pre-wrap}summary{cursor:pointer}</style>'
            '<h1>FineVideo candidate review</h1><p>Source frames and automatic metadata. '
            'Sparse previews do not establish long-range dependence. No generation results.</p>' + ''.join(sections) + '</html>')
    (report_dir / f"{page_name}.html").write_text(page, encoding="utf-8")
    (report_dir / f"{page_name}.json").write_text(json.dumps(review_log, indent=2) + "\n")


if __name__ == "__main__":
    main()
