"""Prepare a frozen, five-source Local/Oracle cohort without changing pilot inputs."""

import json
from pathlib import Path
import shlex
import sys

from prepare_clips import extract, CLIPS
from preview_candidates import preview
from run_generation import ROOT, sha256, write_json


def main():
    config_path = ROOT / "configs/five_case_examples.json"
    config = json.loads(config_path.read_text())
    report_dir = ROOT / "reports/five_case_selection"
    report_dir.mkdir(parents=True, exist_ok=True)
    records = []
    assert len(config["examples"]) == len({e["candidate_id"] for e in config["examples"]}) == 5
    for example in config["examples"]:
        sample = ROOT / "data/finevideo_candidates" / example["candidate_id"]
        source = sample / "source.mp4"
        provenance = json.loads((sample / "provenance.json").read_text())
        assert sha256(source) == provenance["sha256"]
        assert provenance["revision"] == config["dataset_revision"]
        assert example["allowed_modes"] == ["local", "oracle"]
        assert example["local_end"] == example["target_start"]
        assert example["oracle_end"] <= example["local_start"]
        directory = ROOT / "data" / example["example_id"]
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / "metadata.json").exists():
            raise ValueError(f"Refusing to overwrite prepared inputs: {directory}")
        (directory / "source.mp4").symlink_to(Path("../finevideo_candidates") / example["candidate_id"] / "source.mp4")
        metadata = {**example, "source_provenance": provenance, "clip_fps": config["clip_fps"],
                    "cohort_config_sha256": sha256(config_path), "clips": {},
                    "dependency_gap_seconds": example["target_start"] - example["oracle_end"],
                    "dependency_gap_definition": "target_start minus oracle_end in original source time; not model RoPE distance"}
        for kind in ("local", "target", "oracle"):
            start, end = example[kind + "_start"], example[kind + "_end"]
            assert 0 <= start < end <= provenance["video_probe"]["duration_seconds"]
            clip = directory / f"{CLIPS[kind]}.mp4"
            info = extract(source, clip, start, end, config["clip_fps"])
            metadata["clips"][kind] = info
            assert all(start <= t < end for t in info["source_frame_seconds"])
            preview(clip, [i * (end-start-1/24) / 11 for i in range(12)],
                    report_dir / f'{example["example_id"]}_{kind}.jpg')
        assert set(metadata["clips"]["local"]["source_frame_seconds"]).isdisjoint(metadata["clips"]["target"]["source_frame_seconds"])
        metadata["oracle_image_source_seconds"] = metadata["clips"]["oracle"]["source_frame_seconds"][36]
        write_json(directory / "metadata.json", metadata)
        records.append({"example_id": example["example_id"], "metadata_sha256": sha256(directory / "metadata.json"),
                        "oracle_image_source_seconds": metadata["oracle_image_source_seconds"],
                        "clip_frames": {k: v["frames"] for k, v in metadata["clips"].items()},
                        "source_intervals_and_full_decode": "passed"})
        print(f'Prepared {example["example_id"]}: 48 Local + 72 GT + 72 selection-only Oracle frames', flush=True)
    write_json(report_dir / "preparation.json", {"command": shlex.join([sys.executable, *sys.argv]),
               "config_sha256": sha256(config_path), "script_sha256": sha256(Path(__file__)), "examples": records})


if __name__ == "__main__":
    main()
