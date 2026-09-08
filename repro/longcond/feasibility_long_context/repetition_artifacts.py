"""Audit N1/N2/N4/N10 without changing any earlier experiment artifacts."""

from fractions import Fraction
import json
from pathlib import Path

import av
import torch

from repetition_controls import CASES, EXAMPLE, case_path, reference_tensor
from reference_controls import tensor_hash
from run_generation import ROOT, sha256
from temporal_artifacts import COMMON_KEYS, PAIRED_KEYS


def audit_repetition():
    cache = ROOT / "outputs" / EXAMPLE / "reference_inputs_512x288"
    info = json.loads((cache / "inputs.json").read_text())
    if sha256(cache / "inputs.pt") != info["inputs_sha256"]:
        raise ValueError("Input cache changed")
    tensors = torch.load(cache / "inputs.pt", map_location="cpu", weights_only=True)
    if {k: tensor_hash(v) for k, v in tensors.items()} != info["tensor_hashes"]:
        raise ValueError("Cached tensors changed")
    configs = {case: json.loads((case_path(case) / "config.json").read_text()) for case in CASES}
    coords = {case: torch.load(case_path(case) / "video_positions.pt", map_location="cpu", weights_only=True) for case in CASES}
    prior = json.loads((ROOT / "reports/reference_format/seed42/artifact_verification.json").read_text())
    if prior["status"] != "passed":
        raise ValueError("Earlier A/B audit is incomplete")
    anchors = {case: next(r for r in prior["provenance"] if r["case"] == old)
               for case, old in [("N1", "A"), ("N10", "B")]}
    provenance, noises = [], {}
    common = configs["N1"]
    for case, cfg in configs.items():
        directory, spec = case_path(case), CASES[case]
        reused = case in anchors
        if cfg["status"] != "completed" or cfg["gt_video_opened"] or cfg["seed"] != 42:
            raise ValueError(f"Invalid completed condition: {case}")
        if cfg["final_frozen_max_abs_error"] != 0 or len(cfg["denoising_trace"]) != 8 or any(r["frozen_max_abs_error"] != 0 for r in cfg["denoising_trace"]):
            raise ValueError("Frozen condition changed")
        for key in (*COMMON_KEYS, *PAIRED_KEYS):
            if cfg[key] != common[key]:
                raise ValueError(f"Uncontrolled field {key}: {case}")
        if cfg["common_inputs_sha256"] != info["inputs_sha256"] or cfg["models"] != info["fingerprint"]["models"]:
            raise ValueError("Input/model provenance mismatch")
        if cfg["reference_tokens"] != spec["tokens"] or cfg["reference_frames"] != 1:
            raise ValueError("Reference size differs from planned repetition")
        runner_name = {"N1": "run_temporal_position.py", "N10": "run_reference_format.py"}.get(case, "run_reference_repetition.py")
        source = ROOT / runner_name
        if sha256(source) != cfg["script_sha256"]:
            source = ROOT / "outputs/source_snapshots" / cfg["script_sha256"] / runner_name
        if not source.exists() or sha256(source) != cfg["script_sha256"] or sha256(ROOT / "reference_controls.py") != cfg["controls_sha256"]:
            raise ValueError("Original source provenance missing")
        expected_ref = reference_tensor(tensors, case)
        expected_tokens = tensors["oracle_still"].permute(0, 2, 3, 4, 1).flatten(1, 3).repeat(1, spec["repeats"], 1)
        expected_coords = torch.cat([coords["N1"][:, :, :2304], coords["N1"][:, :, 2304:].repeat(1, 1, spec["repeats"], 1)], dim=2)
        if not torch.equal(coords[case], expected_coords) or tensor_hash(coords[case][:, :, :2304]) != cfg["base_video_positions_sha256"]:
            raise ValueError("Actual coordinates differ from exact copies of N1")
        if cfg["reference_input_tensor_sha256"] != tensor_hash(expected_ref):
            raise ValueError("Reference latent is not the specified number of image copies")
        if case == "N1":
            if cfg["reference_translation_audit"]["reference_clean_latent_sha256"] != tensor_hash(expected_tokens):
                raise ValueError("Original image's actual reference audit differs")
        else:
            actual = torch.load(directory / "reference_clean_tokens.pt", map_location="cpu", weights_only=True)
            before = torch.load(directory / "video_positions_before_layout.pt", map_location="cpu", weights_only=True)
            if not torch.equal(actual, expected_tokens):
                raise ValueError("Actual appended reference is not exact image repetition")
            if not torch.equal(before[:, :, :2304], coords[case][:, :, :2304]) or not torch.equal(before[:, 1:], coords[case][:, 1:]):
                raise ValueError("Layout changed base or spatial positions")
            actual_audit = cfg["reference_layout_audit"]
            if tensor_hash(actual) != actual_audit["reference_clean_latent_sha256"] or tensor_hash(coords[case]) != actual_audit["after_positions_sha256"] or tensor_hash(before) != actual_audit["before_positions_sha256"]:
                raise ValueError("Actual tensors differ from layout audit")
            if cfg["format_controls_sha256"] != sha256(ROOT / "format_controls.py"):
                raise ValueError("Shared layout implementation changed")
        if not reused:
            if cfg["reference_spec"] != spec or cfg["reference_source_tensor_sha256"] != info["tensor_hashes"]["oracle_still"] or cfg["reference_latent_temporal_frames"] != spec["repeats"]:
                raise ValueError("Repetition recipe changed")
            if cfg["repetition_controls_sha256"] != sha256(ROOT / "repetition_controls.py"):
                raise ValueError("Repetition source changed")
        initial = torch.load(directory / "target_initial_noise.pt", map_location="cpu", weights_only=True)
        steps = torch.load(directory / "target_step_noises.pt", map_location="cpu", weights_only=True)
        noises[case] = [tensor_hash(n) for n in [initial, *steps]]
        declared = [cfg["noise_audit"]["initial"][0]["target_sha256"], *[r["target_sha256"] for r in cfg["noise_audit"]["ancestral"] if r["modality"] == "video"]]
        if len(steps) != 7 or noises[case] != declared:
            raise ValueError("Saved noise differs from denoiser audit")
        for step, n in enumerate([initial, *steps]):
            seed = 42 if step == 0 else 10042 + 2 * (step - 1)
            expected = torch.randn((1, 2304, 128), generator=torch.Generator().manual_seed(seed), dtype=n.dtype)[:, 1008:]
            if not torch.equal(n, expected):
                raise ValueError("Seed does not reproduce actual target noise")
        latent = torch.load(directory / "generated_latent.pt", map_location="cpu", weights_only=True)
        if tuple(latent.shape) != (1, 128, 16, 9, 16) or not torch.isfinite(latent).all() or not torch.equal(latent[:, :, :7], tensors["local"]):
            raise ValueError("Final latent or frozen local invalid")
        if reused:
            old = anchors[case]
            if sha256(directory / "config.json") != old["config_sha256"] or tensor_hash(coords[case]) != old["positions_tensor_sha256"] or tensor_hash(latent) != old["generated_latent_tensor_sha256"] or tensor_hash(expected_ref) != old["reference_tensor_sha256"]:
                raise ValueError("Reused result differs from prior audit")
        for artifact in cfg["outputs"].values():
            if sha256(Path(artifact["path"])) != artifact["sha256"]:
                raise ValueError("Generated video changed")
        with av.open(cfg["outputs"]["target"]["path"]) as container:
            frames = list(container.decode(video=0))
        if len(frames) != 72 or any(f.pts * f.time_base != Fraction(i, 24) for i, f in enumerate(frames)):
            raise ValueError("Target length or timestamps invalid")
        provenance.append({"case": case, "repeats": spec["repeats"], "reused": reused,
                           "config_path": str(directory / "config.json"), "config_sha256": sha256(directory / "config.json"),
                           "runner_source": str(source), "runner_sha256": cfg["script_sha256"],
                           "reference_tensor_sha256": tensor_hash(expected_ref), "reference_clean_tokens_sha256": tensor_hash(expected_tokens),
                           "positions_tensor_sha256": tensor_hash(coords[case]), "generated_latent_tensor_sha256": tensor_hash(latent),
                           "unique_temporal_bounds": torch.unique(coords[case][0, 0, 2304:], dim=0).tolist(),
                           "reference_tokens": spec["tokens"], "target_frames_and_pts_verified": True})
    if any(value != noises["N1"] for value in noises.values()):
        raise ValueError("Actual noise differs across reference counts")
    return configs, {"status": "passed", "seed": 42, "new_generations": 2, "reused_generations": 2,
                     "common_and_paired_fields": [*COMMON_KEYS, *PAIRED_KEYS],
                     "actual_initial_and_seven_step_noise_equal": True, "declared_seed_reproduces_saved_target_noise": True,
                     "exact_image_content_and_coordinates_repeated": True, "target_frames_fully_decoded": 288,
                     "provenance": provenance}
