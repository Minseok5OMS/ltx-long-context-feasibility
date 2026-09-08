"""Check FineVideo access and extract a bounded, unreviewed candidate sample."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".deps"))

from huggingface_hub import HfApi, get_token, hf_hub_download  # noqa: E402

REPO = "HuggingFaceFV/finevideo"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def decode_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, (str, bytes)):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object in the FineVideo json column")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-access", action="store_true", help="Do not download dataset files")
    parser.add_argument("--revision", help="Dataset commit/tag; omit to resolve the current revision")
    parser.add_argument("--max-videos", type=int, default=5)
    parser.add_argument("--max-shards", type=int, default=1)
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--max-shard-mib", type=float, default=700,
                        help="Maximum sum of selected shard file sizes, including cached files")
    parser.add_argument("--min-duration", type=float, default=60)
    parser.add_argument("--max-duration", type=float, default=600)
    args = parser.parse_args()
    if min(args.max_videos, args.max_shards, args.max_shard_mib) <= 0 or args.start_shard < 0:
        parser.error("Limits must be positive and start-shard must be nonnegative")
    if not 0 <= args.min_duration <= args.max_duration:
        parser.error("Expected 0 <= min-duration <= max-duration")

    report: dict[str, Any] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_id": REPO,
        "command": shlex.join([sys.executable, *sys.argv]),
        "token_available": bool(get_token()),
        "status": "checking",
    }
    access_path = ROOT / "reports" / "finevideo_access.json"
    api = HfApi()
    try:
        info = api.dataset_info(REPO, revision=args.revision, files_metadata=True, timeout=30)
        shards = sorted((f for f in info.siblings if f.rfilename.endswith(".parquet")),
                        key=lambda f: f.rfilename)
        report.update(revision=info.sha, gated=info.gated, parquet_count=len(shards),
                      first_shard={"path": shards[0].rfilename, "bytes": shards[0].size} if shards else None)
        api.auth_check(REPO, repo_type="dataset")
    except Exception as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        report.update(status="access_denied" if status_code in (401, 403) else "connection_or_api_error",
                      error_type=type(exc).__name__, http_status=status_code)
        # Server error text only: never log tokens, request headers, or signed download URLs.
        if response is not None:
            message = response.headers.get("X-Error-Message")
            if message:
                report["server_message"] = message[:1000]
        write_json(access_path, report)
        print(f"FineVideo access failed: {report['error_type']} (HTTP {status_code}).", flush=True)
        print(f"Report: {access_path}", flush=True)
        return 2

    report["status"] = "allowed"
    write_json(access_path, report)
    print(f"FineVideo access allowed. Revision: {info.sha}", flush=True)
    if args.check_access:
        return 0

    try:
        import pyarrow.parquet as pq
        import av
    except ImportError:
        print("Missing pyarrow or av. See README.md for the isolated dependency setup.")
        return 3

    output = ROOT / "data" / "finevideo_candidates"
    manifest: dict[str, Any] = {
        "repo_id": REPO, "revision": info.sha, "command": report["command"],
        "status": "collecting_unreviewed_candidates", "limits": vars(args),
        "selection": "First rows with metadata duration in range; no oracle labels inferred",
        "shards": [], "candidates": [], "rejected_rows": [],
    }
    total_bytes = 0
    selected_shards = shards[args.start_shard:args.start_shard + args.max_shards]
    if not selected_shards:
        print("No shards at the requested start index.")
        return 4

    for shard_index, shard in enumerate(selected_shards, start=args.start_shard):
        if shard.size is None or total_bytes + shard.size > args.max_shard_mib * 2**20:
            manifest["stop_reason"] = "shard_size_unknown_or_budget_exceeded"
            break
        total_bytes += shard.size
        print(f"Fetching {shard.rfilename} ({shard.size / 2**20:.1f} MiB).", flush=True)
        local_file = hf_hub_download(REPO, shard.rfilename, repo_type="dataset", revision=info.sha,
                                     local_dir=ROOT / ".cache" / "finevideo" / info.sha)
        manifest["shards"].append({"path": shard.rfilename, "bytes": shard.size})
        parquet = pq.ParquetFile(local_file)
        if not {"json", "mp4"}.issubset(parquet.schema_arrow.names):
            raise ValueError(f"Unexpected FineVideo columns: {parquet.schema_arrow.names}")
        for row_index, batch in enumerate(parquet.iter_batches(batch_size=1, columns=["json", "mp4"])):
            row = batch.to_pylist()[0]
            metadata = decode_metadata(row["json"])
            try:
                duration = float(metadata.get("duration_seconds", 0))
            except (ValueError, TypeError):
                continue
            if not args.min_duration <= duration <= args.max_duration:
                continue
            payload = row["mp4"]
            if isinstance(payload, dict):
                payload = payload.get("bytes")
            if not isinstance(payload, bytes) or not payload:
                raise ValueError("Expected nonempty MP4 bytes in the FineVideo mp4 column")
            sample_id = f"fv_{info.sha[:8]}_{shard_index:04d}_{row_index:05d}"
            sample_dir = output / sample_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            video_path = sample_dir / "source.mp4"
            checksum = hashlib.sha256(payload).hexdigest()
            if video_path.exists():
                if hashlib.sha256(video_path.read_bytes()).hexdigest() != checksum:
                    raise ValueError(f"Existing source differs; refusing overwrite: {video_path}")
            else:
                temporary = sample_dir / "source.mp4.part"
                temporary.write_bytes(payload)
                temporary.replace(video_path)
            try:
                with av.open(str(video_path)) as container:
                    stream = container.streams.video[0]
                    frame = next(container.decode(stream))
                    probe = {"width": frame.width, "height": frame.height,
                             "fps": float(stream.average_rate) if stream.average_rate else None,
                             "duration_seconds": container.duration / av.time_base if container.duration else None}
            except Exception as exc:
                manifest["rejected_rows"].append({"id": sample_id, "reason": type(exc).__name__})
                continue
            provenance = {"repo_id": REPO, "revision": info.sha, "shard": shard.rfilename,
                          "row_index": row_index, "sha256": checksum, "source_bytes": len(payload),
                          "original_json_filename": metadata.get("original_json_filename"),
                          "youtube_title": metadata.get("youtube_title"), "video_probe": probe,
                          "review_status": "unreviewed", "is_validated_feasibility_example": False}
            write_json(sample_dir / "finevideo_metadata.json", metadata)
            write_json(sample_dir / "provenance.json", provenance)
            manifest["candidates"].append({"id": sample_id, "path": str(sample_dir), **provenance})
            write_json(output / "manifest.json", manifest)
            print(f"Saved {sample_id}: {duration:.1f}s, {probe['width']}x{probe['height']}", flush=True)
            if len(manifest["candidates"]) >= args.max_videos:
                break
        if len(manifest["candidates"]) >= args.max_videos:
            break
    manifest["status"] = "candidates_ready_for_visual_review" if manifest["candidates"] else "no_candidates"
    manifest["selected_shard_bytes"] = total_bytes
    write_json(output / "manifest.json", manifest)
    print(f"Saved {len(manifest['candidates'])} unreviewed candidates. Manifest: {output / 'manifest.json'}")
    return 0 if manifest["candidates"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
