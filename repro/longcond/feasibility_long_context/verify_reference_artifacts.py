"""Verify the published diagnostic groups, source snapshots, and report links on CPU."""

import ast
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path

import av
import torch

from reference_controls import tensor_hash
from run_generation import ROOT, sha256, write_json


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(value for key, value in attrs if key in {"src", "href"} and value)


def main():
    groups, sources, times, memory = [], {}, [], []
    count, frames_checked = 0, 0
    for path in sorted((ROOT / "reports/reference").glob("*/*/summary.json")):
        summary = json.loads(path.read_text())
        group = Path(summary["group_directory"])
        assert summary["paired_controls"]["status"] == "passed"
        assert summary["review_sha256"] == sha256(path.with_name("review.json"))
        initial_hashes, step_hashes = [], []
        for mode in ["local", "random", "oracle"]:
            cfg_path = group / mode / "config.json"
            cfg = json.loads(cfg_path.read_text())
            assert summary["config_sha256"][mode] == sha256(cfg_path)
            assert cfg["status"] == "completed" and not cfg["gt_video_opened"]
            assert cfg["physical_gpu"] in {0, 1, 2}
            assert cfg["final_frozen_max_abs_error"] == 0
            source = ROOT / "run_reference_comparison.py"
            if sha256(source) != cfg["script_sha256"]:
                source = ROOT / "outputs/source_snapshots" / cfg["script_sha256"] / source.name
            assert sha256(source) == cfg["script_sha256"]
            assert sha256(source.with_name("reference_controls.py")) == cfg["controls_sha256"]
            sources[cfg["script_sha256"]] = str(source)
            positions = torch.load(group / mode / "video_positions.pt", map_location="cpu", weights_only=True)
            slices = {"local": (slice(0, 1008), [97 / 24, 146 / 24]),
                      "target": (slice(1008, 2304), [146 / 24, 218 / 24])}
            if mode != "local":
                slices["reference"] = (slice(2304, None), cfg["reference_model_time_range"])
            for label, (indices, expected) in slices.items():
                time_positions = positions[:, 0, indices]
                actual = [float(time_positions.min()), float(time_positions.max())]
                assert all(abs(a - e) < 1e-5 for a, e in zip(actual, expected)), (group, mode, label, actual, expected)
            for artifact in cfg["outputs"].values():
                assert sha256(Path(artifact["path"])) == artifact["sha256"]
            target = cfg["outputs"]["target"]
            with av.open(target["path"]) as container:
                pts = [float(frame.time) for frame in container.decode(video=0)]
            assert len(pts) == 72
            assert all(abs(t - i / 24) < 1e-5 for i, t in enumerate(pts))
            frames_checked += len(pts)
            noise = torch.load(group / mode / "target_initial_noise.pt", map_location="cpu", weights_only=True)
            steps = torch.load(group / mode / "target_step_noises.pt", map_location="cpu", weights_only=True)
            assert len(steps) == 7
            initial_hashes.append(tensor_hash(noise))
            step_hashes.append([tensor_hash(t) for t in steps])
            count += 1
            times.append(cfg["total_seconds"])
            memory.append(cfg["peak_gpu_allocated_gib"])
        assert len(set(initial_hashes)) == 1 and step_hashes[0] == step_hashes[1] == step_hashes[2]
        groups.append(str(path.parent.relative_to(ROOT)))

    base = ROOT / "outputs/pilot_001_interview_return"
    past, guide = base / "reference_past_seed42/local", base / "reference_target_guide_seed42/local"
    a = torch.load(past / "generated_latent.pt", map_location="cpu", weights_only=True)
    b = torch.load(guide / "generated_latent.pt", map_location="cpu", weights_only=True)
    assert torch.equal(a, b)
    assert sha256(past / "local_only.mp4") == sha256(guide / "local_only.mp4")
    links_checked = 0
    pages = [ROOT / "report.html", *[ROOT / group / "index.html" for group in groups]]
    for path in pages:
        parser = Links(); parser.feed(path.read_text())
        for target in parser.targets:
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (path.parent / target).exists(), (path, target)
            links_checked += 1
    previews_checked = 0
    for manifest in sorted((ROOT / "reports/reference/inputs").glob("*/inputs.json")):
        data = json.loads(manifest.read_text())
        for clip in data["clips"].values():
            assert sha256(ROOT / clip["file"]) == clip["sha256"]
            assert sha256(ROOT / clip["middle_png"]) == clip["middle_png_sha256"]
            previews_checked += 1
    for name in ["run_reference_comparison.py", "reference_controls.py", "evaluate_reference.py", "make_reference_inputs.py",
                 "make_reference_report.py", "test_reference_controls.py", "verify_reference_artifacts.py"]:
        ast.parse((ROOT / name).read_text())
    result = {"status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "evaluated_groups": groups, "completed_runs_checked": count, "target_frames_decoded": frames_checked,
              "target_frame_count_and_pts": "72 at 24 FPS in each run",
              "saved_initial_and_seven_step_noise_pairing": "passed in all groups",
              "generation_and_review_artifact_hashes": "passed", "source_snapshots": sources,
              "past_vs_target_guide_local_latent_exact_equal": True,
              "past_vs_target_guide_local_target_mp4_sha256_equal": True,
              "html_local_links_checked": links_checked, "python_syntax": "passed",
              "documented_local_target_reference_positions": "match saved tensors in all nine runs",
              "input_preview_and_source_clip_hashes_checked": previews_checked,
              "generation_seconds_range": [min(times), max(times)],
              "peak_gpu_allocated_gib_range": [min(memory), max(memory)],
              "excluded": "reference_target_guide_seed42_attempt1; interrupted preliminary attempt"}
    write_json(ROOT / "reports/reference/artifact_verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
