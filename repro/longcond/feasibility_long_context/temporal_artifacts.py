"""Explicit cell provenance and audits for the temporal-position factorial experiment."""

import json
from pathlib import Path

import torch

from reference_controls import tensor_hash
from run_generation import ROOT, sha256

EXAMPLE = "pilot_001_interview_return"
KINDS = ("image", "video")
POSITIONS = ("past", "target")
CELLS = tuple(f"{kind}_{position}" for kind in KINDS for position in POSITIONS)
COMMON_KEYS = (
    "example_id", "models", "ltx_commit", "controls_sha256", "environment",
    "prompt", "prompt_enhancement", "fps", "width", "height", "prefix_frames", "target_frames", "total_frames",
    "target_decoded_slice", "base_video_tokens", "prefix_tokens", "common_time_shift_seconds", "target_model_time_range",
    "common_inputs_sha256", "local_latent_sha256", "prompt_context_hashes", "sigmas", "sampler", "eta", "s_noise",
    "precision", "guidance", "audio", "noise_policy", "base_video_positions_sha256", "audio_positions_sha256",
    "reference_source", "source_dependency_gap_seconds",
)
PAIRED_KEYS = ("seed", "initial_noise_seed", "step_noise_seed", "decoder_seed", "noise_audit")


def cell_path(seed, cell):
    root = ROOT / "outputs" / EXAMPLE
    if seed == 42 and cell in ("image_target", "video_past"):
        layout = "target_guide" if cell == "image_target" else "past"
        return root / f"reference_{layout}_seed42/oracle"
    return root / f"temporal_position_seed{seed}" / cell


def audit_cells(seeds):
    cache = ROOT / "outputs" / EXAMPLE / "reference_inputs_512x288"
    cache_info = json.loads((cache / "inputs.json").read_text())
    if sha256(cache / "inputs.pt") != cache_info["inputs_sha256"]:
        raise ValueError("Input cache changed")
    tensors = torch.load(cache / "inputs.pt", map_location="cpu", weights_only=True)
    if {k: tensor_hash(v) for k, v in tensors.items()} != cache_info["tensor_hashes"]:
        raise ValueError("Input tensors changed")
    base_cfg = json.loads((cell_path(42, "video_past") / "config.json").read_text())
    if base_cfg["models"] != cache_info["fingerprint"]["models"]:
        raise ValueError("Input/model provenance mismatch")
    configs, provenance, position_pairs = {}, [], []
    for seed in seeds:
        configs[seed], coords, noises = {}, {}, {}
        paired = None
        for cell in CELLS:
            kind, position = cell.split("_")
            directory = cell_path(seed, cell)
            cfg = json.loads((directory / "config.json").read_text())
            if cfg["status"] != "completed" or cfg["gt_video_opened"] or cfg["final_frozen_max_abs_error"] != 0:
                raise ValueError(f"Invalid run: {directory}")
            if len(cfg["denoising_trace"]) != 8 or any(r["frozen_max_abs_error"] != 0 for r in cfg["denoising_trace"]):
                raise ValueError("Frozen conditions changed")
            for key in COMMON_KEYS:
                if cfg[key] != base_cfg[key]:
                    raise ValueError(f"Uncontrolled common field {key}: {directory}")
            if cfg["seed"] != seed or cfg["common_inputs_sha256"] != cache_info["inputs_sha256"]:
                raise ValueError("Seed or input mismatch")
            if sha256(ROOT / "reference_controls.py") != cfg["controls_sha256"]:
                raise ValueError("Original controls source changed")
            if paired is None:
                paired = cfg
            for key in PAIRED_KEYS:
                if cfg[key] != paired[key]:
                    raise ValueError(f"Unpaired {key}: {directory}")
            reused = seed == 42 and cell in ("image_target", "video_past")
            source = ROOT / ("run_reference_comparison.py" if reused else "run_temporal_position.py")
            if sha256(source) != cfg["script_sha256"]:
                source = ROOT / "outputs/source_snapshots" / cfg["script_sha256"] / source.name
            if not source.exists() or sha256(source) != cfg["script_sha256"]:
                raise ValueError("Missing original runner source")
            ref_key = "oracle_still" if kind == "image" else "oracle"
            if not reused:
                if cfg["temporal_controls_sha256"] != sha256(ROOT / "temporal_controls.py"):
                    raise ValueError("Temporal controls source changed")
                if cfg["reference_input_tensor_sha256"] != cache_info["tensor_hashes"][ref_key]:
                    raise ValueError("Reference tensor changed")
                expected_clean = tensors[ref_key].permute(0, 2, 3, 4, 1).flatten(1, 3)
                if cfg["reference_translation_audit"]["reference_clean_latent_sha256"] != tensor_hash(expected_clean):
                    raise ValueError("Actual appended reference differs from cache")
            if cfg["reference_tokens"] != (144 if kind == "image" else 1440) or cfg["reference_frames"] != (1 if kind == "image" else 73):
                raise ValueError("Wrong reference format or token budget")
            for artifact in cfg["outputs"].values():
                if sha256(Path(artifact["path"])) != artifact["sha256"]:
                    raise ValueError("Generated artifact changed")
            noise = torch.load(directory / "target_initial_noise.pt", map_location="cpu", weights_only=True)
            steps = torch.load(directory / "target_step_noises.pt", map_location="cpu", weights_only=True)
            hashes = [tensor_hash(noise), *[tensor_hash(n) for n in steps]]
            expected = [cfg["noise_audit"]["initial"][0]["target_sha256"], *[
                r["target_sha256"] for r in cfg["noise_audit"]["ancestral"] if r["modality"] == "video"]]
            if len(steps) != 7 or hashes != expected:
                raise ValueError("Actual saved noise differs from audit")
            # Check seeds against actual tensor bytes, independently of the audit.
            for step, noise_tensor in enumerate([noise, *steps]):
                noise_seed = seed if step == 0 else seed + 10000 + 2 * (step - 1)
                expected_noise = torch.randn((1, 2304, 128), generator=torch.Generator().manual_seed(noise_seed), dtype=noise_tensor.dtype)[:, 1008:]
                if not torch.equal(expected_noise, noise_tensor):
                    raise ValueError("Stored target noise is not the declared seed")
            noises[cell] = hashes
            coords[cell] = torch.load(directory / "video_positions.pt", map_location="cpu", weights_only=True)
            if tensor_hash(coords[cell][:, :, :2304]) != cfg["base_video_positions_sha256"]:
                raise ValueError("Actual base positions differ from audit")
            if not reused:
                before = torch.load(directory / "video_positions_before_translation.pt", map_location="cpu", weights_only=True)
                translated = before.clone()
                translated[:, 0, 2304:] += cfg["reference_time_offset_seconds"]
                if not torch.equal(translated, coords[cell]):
                    raise ValueError("Actual coordinates are not a pure time translation")
            latent = torch.load(directory / "generated_latent.pt", map_location="cpu", weights_only=True)
            if tuple(latent.shape) != (1, 128, 16, 9, 16) or not torch.isfinite(latent).all() or not torch.equal(latent[:, :, :7], tensors["local"]):
                raise ValueError("Decoded base latent / frozen local invalid")
            configs[seed][cell] = cfg
            provenance.append({"seed": seed, "cell": cell, "reused": reused,
                               "config_path": str(directory / "config.json"), "config_sha256": sha256(directory / "config.json"),
                               "runner_source": str(source), "runner_sha256": cfg["script_sha256"],
                               "reference_input_tensor_sha256": cache_info["tensor_hashes"][ref_key],
                               "positions_tensor_sha256": tensor_hash(coords[cell]),
                               "generated_latent_tensor_sha256": tensor_hash(latent)})
        if any(v != noises[CELLS[0]] for v in noises.values()):
            raise ValueError("Actual initial or ancestral noise differs across factorial cells")
        for kind in KINDS:
            past, target = coords[f"{kind}_past"], coords[f"{kind}_target"]
            expected = past.clone()
            expected[:, 0, 2304:] += 146 / 24
            if not torch.equal(expected, target):
                raise ValueError(f"Paired {kind} coordinates differ beyond the intended shift")
            position_pairs.append({"seed": seed, "reference_kind": kind, "exact_translated_positions_equal": True,
                                   "past_range": [past[:, 0, 2304:].min().item(), past[:, 0, 2304:].max().item()],
                                   "target_range": [target[:, 0, 2304:].min().item(), target[:, 0, 2304:].max().item()]})
    return configs, {"status": "passed", "common_fields": list(COMMON_KEYS), "paired_fields": list(PAIRED_KEYS),
                     "actual_initial_and_seven_step_noise_equal_within_seed": True,
                     "declared_seed_reproduces_saved_target_noise": True,
                     "reference_pairs": position_pairs, "provenance": provenance}
