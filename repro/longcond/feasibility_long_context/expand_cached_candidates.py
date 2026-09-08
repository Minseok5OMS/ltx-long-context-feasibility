"""Extract explicitly selected rows from the already downloaded FineVideo shard."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys

from download_finevideo import ROOT, REPO, decode_metadata, write_json
from preview_candidates import preview
import av
import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", required=True)
    args = parser.parse_args()
    revision = "84c74091e1c6ee7a5dffabfafb5c9033e4718883"
    relative_shard = "data/train-00000-of-01357.parquet"
    shard = ROOT / ".cache/finevideo" / revision / relative_shard
    report_dir = ROOT / "reports/five_case_selection"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"command": shlex.join([sys.executable, *sys.argv]), "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "revision": revision, "shard": relative_shard, "network_bytes": 0,
              "selection": "Explicit rows chosen by source metadata for visual inspection; not based on generation results",
              "candidates": []}
    wanted = set(args.rows)
    for row_index, batch in enumerate(pq.ParquetFile(shard).iter_batches(batch_size=1, columns=["json", "mp4"])):
        if row_index not in wanted:
            continue
        row = batch.to_pylist()[0]
        metadata = decode_metadata(row["json"])
        payload = row["mp4"]
        if isinstance(payload, dict): payload = payload["bytes"]
        sample_id = f"fv_{revision[:8]}_0000_{row_index:05d}"
        directory = ROOT / "data/finevideo_candidates" / sample_id
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / "source.mp4"
        digest = hashlib.sha256(payload).hexdigest()
        if source.exists():
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError("Existing source differs")
        else:
            source.write_bytes(payload)
        with av.open(source) as container:
            stream = container.streams.video[0]
            frame = next(container.decode(stream))
            probe = {"width": frame.width, "height": frame.height, "fps": float(stream.average_rate),
                     "duration_seconds": container.duration / av.time_base}
        provenance = {"repo_id": REPO, "revision": revision, "shard": relative_shard, "row_index": row_index,
                      "sha256": digest, "source_bytes": len(payload), "original_json_filename": metadata.get("original_json_filename"),
                      "youtube_title": metadata.get("youtube_title"), "video_probe": probe,
                      "review_status": "unreviewed", "is_validated_feasibility_example": False}
        for name, value in [("provenance.json", provenance), ("finevideo_metadata.json", metadata)]:
            path = directory / name
            if not path.exists(): write_json(path, value)
        end = probe["duration_seconds"] - 0.25
        frames = preview(source, [end * i / 35 for i in range(36)], report_dir / f"{sample_id}_overview.jpg")
        report["candidates"].append({"id": sample_id, **provenance, "preview_frames": frames})
        print(f"Prepared row {row_index}: {metadata.get('youtube_title')} ({len(payload)/2**20:.1f} MiB)", flush=True)
    if len(report["candidates"]) != len(wanted):
        raise ValueError("Missing requested rows")
    report["extracted_bytes"] = sum(c["source_bytes"] for c in report["candidates"])
    write_json(report_dir / "selection_manifest.json", report)


if __name__ == "__main__":
    main()
