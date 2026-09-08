"""Audit the five reference-format conditions against the original seed-42 evidence."""

from fractions import Fraction
import json
from pathlib import Path

import av
import torch

from format_controls import CASES, EXAMPLE, case_path, reference_tensor
from reference_controls import tensor_hash
from run_generation import ROOT, sha256
from temporal_artifacts import COMMON_KEYS, PAIRED_KEYS


def audit_format():
    cache = ROOT / "outputs" / EXAMPLE / "reference_inputs_512x288"
    info = json.loads((cache / "inputs.json").read_text())
    if sha256(cache / "inputs.pt") != info["inputs_sha256"]:
        raise ValueError("Input cache changed")
    tensors = torch.load(cache / "inputs.pt", map_location="cpu", weights_only=True)
    if {k: tensor_hash(v) for k, v in tensors.items()} != info["tensor_hashes"]:
        raise ValueError("Cached tensors changed")
    configs = {case: json.loads((case_path(case) / "config.json").read_text()) for case in CASES}
    common = configs["A"]
    prior = json.loads((ROOT / "reports/temporal_position/artifact_verification.json").read_text())
    coords = {case: torch.load(case_path(case) / "video_positions.pt", map_location="cpu", weights_only=True) for case in CASES}
    for case, cell in [("A", "image_past"), ("E", "video_past")]:
        row = next(r for r in prior["provenance"] if r["seed"] == 42 and r["cell"] == cell)
        if sha256(case_path(case) / "config.json") != row["config_sha256"] or tensor_hash(coords[case]) != row["positions_tensor_sha256"]:
            raise ValueError("Reused anchor differs from prior audit")
    provenance, noise_hashes = [], {}
    for case, cfg in configs.items():
        directory = case_path(case)
        spec = CASES[case]
        if cfg["status"] != "completed" or cfg["gt_video_opened"] or cfg["seed"] != 42:
            raise ValueError(f"Invalid condition {case}")
        if cfg["final_frozen_max_abs_error"] != 0 or len(cfg["denoising_trace"]) != 8 or any(r["frozen_max_abs_error"] != 0 for r in cfg["denoising_trace"]):
            raise ValueError("Frozen conditioning changed")
        for key in (*COMMON_KEYS, *PAIRED_KEYS):
            if cfg[key] != common[key]:
                raise ValueError(f"Uncontrolled field {key}: {case}")
        if cfg["common_inputs_sha256"] != info["inputs_sha256"] or cfg["reference_tokens"] != spec["tokens"]:
            raise ValueError("Input or token count mismatch")
        if cfg["models"] != info["fingerprint"]["models"]:
            raise ValueError("Checkpoint fingerprint mismatch")
        runner_name = {"A": "run_temporal_position.py", "E": "run_reference_comparison.py"}.get(case, "run_reference_format.py")
        source = ROOT / runner_name
        if sha256(source) != cfg["script_sha256"]:
            source = ROOT / "outputs/source_snapshots" / cfg["script_sha256"] / runner_name
        if not source.exists() or sha256(source) != cfg["script_sha256"] or sha256(ROOT / "reference_controls.py") != cfg["controls_sha256"]:
            raise ValueError("Original code provenance missing")
        expected_ref = reference_tensor(tensors, case)
        expected_tokens = expected_ref.permute(0, 2, 3, 4, 1).flatten(1, 3)
        expected_coords = coords["A"].clone() if case == "A" else coords["E"].clone()
        if case in ("B", "D"):
            expected_coords[:, 0, 2304:] = coords["A"][:, 0, 2304:].repeat(1, 10, 1)
        if not torch.equal(coords[case], expected_coords):
            raise ValueError(f"Coordinates outside planned intervention: {case}")
        if tensor_hash(coords[case][:, :, :2304]) != cfg["base_video_positions_sha256"]:
            raise ValueError("Actual base positions differ from audit")
        if case in ("B", "C", "D"):
            actual_tokens = torch.load(directory / "reference_clean_tokens.pt", map_location="cpu", weights_only=True)
            before = torch.load(directory / "video_positions_before_layout.pt", map_location="cpu", weights_only=True)
            if not torch.equal(actual_tokens, expected_tokens):
                raise ValueError("Actual appended reference differs from intended content")
            if cfg["format_controls_sha256"] != sha256(ROOT / "format_controls.py") or cfg["reference_input_tensor_sha256"] != tensor_hash(expected_ref):
                raise ValueError("Changed format source or reference tensor")
            if cfg["reference_spec"] != spec or cfg["reference_source_tensor_sha256"] != info["tensor_hashes"][spec["key"]]:
                raise ValueError("Reference duplication recipe differs")
            if not torch.equal(before, coords["E"]):
                raise ValueError("Initial reference grid differs from the original video grid")
            actual_audit = cfg["reference_layout_audit"]
            if tensor_hash(actual_tokens) != actual_audit["reference_clean_latent_sha256"] or tensor_hash(coords[case]) != actual_audit["after_positions_sha256"]:
                raise ValueError("Reference content/coordinate audit mismatch")
        initial = torch.load(directory / "target_initial_noise.pt", map_location="cpu", weights_only=True)
        steps = torch.load(directory / "target_step_noises.pt", map_location="cpu", weights_only=True)
        noise_hashes[case] = [tensor_hash(n) for n in [initial, *steps]]
        expected_hashes = [cfg["noise_audit"]["initial"][0]["target_sha256"], *[
            r["target_sha256"] for r in cfg["noise_audit"]["ancestral"] if r["modality"] == "video"]]
        if len(steps) != 7 or noise_hashes[case] != expected_hashes:
            raise ValueError("Actual initial/step noises differ from audit")
        for step, n in enumerate([initial, *steps]):
            seed = 42 if step == 0 else 10042 + 2 * (step - 1)
            expected_noise = torch.randn((1, 2304, 128), generator=torch.Generator().manual_seed(seed), dtype=n.dtype)[:, 1008:]
            if not torch.equal(n, expected_noise):
                raise ValueError("Declared seed does not reproduce saved target noise")
        latent = torch.load(directory / "generated_latent.pt", map_location="cpu", weights_only=True)
        if tuple(latent.shape) != (1, 128, 16, 9, 16) or not torch.isfinite(latent).all() or not torch.equal(latent[:, :, :7], tensors["local"]):
            raise ValueError("Final base latent/local invalid")
        for artifact in cfg["outputs"].values():
            if sha256(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Generated video file changed")
        with av.open(cfg["outputs"]["target"]["path"]) as container:
            frames = list(container.decode(video=0))
        if len(frames) != 72 or any(f.pts * f.time_base != Fraction(i, 24) for i, f in enumerate(frames)):
            raise ValueError("Target frame count / timestamps invalid")
        provenance.append({"case": case, "reused": case in ("A", "E"), "config_path": str(directory / "config.json"),
                           "config_sha256": sha256(directory / "config.json"), "runner_source": str(source), "runner_sha256": cfg["script_sha256"],
                           "reference_tensor_sha256": tensor_hash(expected_ref), "reference_clean_tokens_sha256": tensor_hash(expected_tokens),
                           "positions_tensor_sha256": tensor_hash(coords[case]), "generated_latent_tensor_sha256": tensor_hash(latent),
                           "unique_temporal_bounds": torch.unique(coords[case][0, 0, 2304:], dim=0).tolist(),
                           "reference_tokens": cfg["reference_tokens"], "target_frames_and_pts_verified": True})
    if any(n != noise_hashes["A"] for n in noise_hashes.values()):
        raise ValueError("Actual noise differs across conditions")
    return configs, {"status": "passed", "seed": 42, "new_generations": 3, "reused_generations": 2,
                     "common_and_paired_fields": [*COMMON_KEYS, *PAIRED_KEYS],
                     "actual_initial_and_seven_step_noise_equal": True, "target_frames_fully_decoded": 360,
                     "B_C_reference_content_equal": True, "D_E_reference_content_equal": True,
                     "B_D_positions_equal": True, "C_E_positions_equal": True,
                     "B_reference_content_and_grid_are_ten_exact_A_copies": True,
                     "provenance": provenance}
