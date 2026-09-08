"""Audit reused baselines and the fifteen new factorial cells from actual tensors."""

from fractions import Fraction
import json
from pathlib import Path

import av
import numpy as np
import torch

from five_case_artifacts import audit_five_cases
from reference_controls import tensor_hash
from run_generation import ROOT, read_rgb, sha256

CELLS = ("image_past", "image_target", "video_past", "video_target")


def cell_path(name, cell):
    if cell == "local":
        return ROOT / "outputs" / name / "image_past_seed42/local"
    if cell == "image_past":
        return ROOT / "outputs" / name / "image_past_seed42/oracle"
    return ROOT / "outputs" / name / "reference_grid_seed42" / cell


def audit_grid():
    grid_path = ROOT / "configs/five_case_grid.json"
    grid = json.loads(grid_path.read_text())
    prior_path = ROOT / "reports/five_cases/seed42/artifact_verification.json"
    assert sha256(prior_path) == grid["prior_artifact_audit_sha256"]
    prior = json.loads(prior_path.read_text())
    assert grid["reused_provenance"] == prior["provenance"]
    old_configs, current_old_audit = audit_five_cases()
    assert current_old_audit == prior, "Reused runs no longer reproduce the previous audit"
    snapshot = ROOT / "outputs/five_case_grid_batch/source_snapshot"
    for name in ("run_five_case_grid.py", "run_five_case_grid_batch.py", "prepare_five_case_video.py",
                 "reference_controls.py", "temporal_controls.py", "run_generation.py", "decode_five_case_latent.py"):
        assert sha256(snapshot / name) == sha256(ROOT / name)
    assert sha256(snapshot / grid_path.name) == sha256(grid_path)
    fields = [key for key in prior["paired_equal_fields"] if key not in {"script_sha256", "layout", "reference_model_time_range"}]
    prior_video = ROOT / "outputs/pilot_001_interview_return/reference_past_seed42/oracle/video_positions.pt"
    video_past_coords = torch.load(prior_video, map_location="cpu", weights_only=True)
    configs, provenance = {}, []
    for name in grid["examples"]:
        data = ROOT / "data" / name
        metadata = json.loads((data / "metadata.json").read_text())
        cache = ROOT / "outputs" / name / "five_case_inputs_512x288"
        tensors = torch.load(cache / "inputs.pt", map_location="cpu", weights_only=True)
        video_cache = ROOT / "outputs" / name / "five_case_video_inputs_512x288"
        info = json.loads((video_cache / "inputs.json").read_text())
        assert sha256(video_cache / "inputs.pt") == info["inputs_sha256"]
        assert info["fingerprint"]["script_sha256"] == sha256(ROOT / "prepare_five_case_video.py")
        assert info["fingerprint"]["metadata_sha256"] == sha256(data / "metadata.json")
        assert info["fingerprint"]["source_clip_sha256"] == sha256(data / "oracle_context.mp4")
        assert info["fingerprint"]["parent_cache_sha256"] == old_configs[name]["oracle"]["common_inputs_sha256"]
        video = torch.load(video_cache / "inputs.pt", map_location="cpu", weights_only=True)["oracle_video"]
        assert tuple(video.shape) == (1, 128, 10, 9, 16) and torch.isfinite(video).all()
        assert tensor_hash(video) == info["tensor_hashes"]["oracle_video"]
        rgb = read_rgb(data / "oracle_context.mp4", 512, 288)
        padded = np.concatenate([rgb[:1], rgb])
        assert tensor_hash(torch.from_numpy(padded)) == info["padded_input_rgb_sha256"]
        source_times = metadata["clips"]["oracle"]["source_frame_seconds"]
        assert info["source_frame_seconds"] == [source_times[0], *source_times]
        assert all(metadata["oracle_start"] <= t < metadata["oracle_end"] <= metadata["local_start"] for t in info["source_frame_seconds"])
        assert sha256(Path(info["input_video_preview"]["path"])) == info["input_video_preview"]["sha256"]
        image_past_coords = torch.load(cell_path(name, "image_past") / "video_positions.pt", map_location="cpu", weights_only=True)
        common = old_configs[name]["oracle"]
        result = {"local": old_configs[name]["local"], "image_past": common}
        baseline_initial = torch.load(cell_path(name, "image_past") / "target_initial_noise.pt", map_location="cpu", weights_only=True)
        baseline_steps = torch.load(cell_path(name, "image_past") / "target_step_noises.pt", map_location="cpu", weights_only=True)
        for cell in grid["new_cells"]:
            directory = cell_path(name, cell)
            cfg = json.loads((directory / "config.json").read_text())
            assert cfg["status"] == "completed" and not cfg["gt_video_opened"]
            assert cfg["script_sha256"] == sha256(snapshot / "run_five_case_grid.py")
            assert cfg["temporal_controls_sha256"] == sha256(snapshot / "temporal_controls.py")
            assert cfg["grid_config_sha256"] == sha256(grid_path)
            assert cfg["video_inputs_sha256"] == info["inputs_sha256"]
            for key in fields:
                assert cfg[key] == common[key], (name, cell, key)
            kind, position = cell.split("_")
            count, pixels = (144, 1) if kind == "image" else (1440, 73)
            offset = 0.0 if position == "past" else 146/24
            assert cfg["reference_tokens"] == count and cfg["reference_frames"] == pixels
            assert cfg["reference_kind"] == kind and cfg["reference_position"] == position
            assert cfg["reference_model_time_range"] == [offset, offset+pixels/24]
            ref = tensors["oracle_still"] if kind == "image" else video
            assert cfg["reference_input_tensor_sha256"] == tensor_hash(ref)
            actual_ref = torch.load(directory / "reference_clean_tokens.pt", map_location="cpu", weights_only=True)
            assert torch.equal(actual_ref, ref.permute(0, 2, 3, 4, 1).flatten(1, 3))
            before = torch.load(directory / "video_positions_before_translation.pt", map_location="cpu", weights_only=True)
            positions = torch.load(directory / "video_positions.pt", map_location="cpu", weights_only=True)
            template = image_past_coords if kind == "image" else video_past_coords
            assert torch.equal(before, template), (name, cell, "past template")
            expected = template.clone()
            expected[:, 0, 2304:] += offset
            assert torch.equal(positions, expected), (name, cell, "pure translation")
            assert torch.equal(positions[:, :, :2304], image_past_coords[:, :, :2304])
            assert torch.equal(positions[:, 1:], before[:, 1:])
            translation = cfg["reference_translation_audit"]
            assert translation["before_positions_sha256"] == tensor_hash(before)
            assert translation["after_positions_sha256"] == tensor_hash(positions)
            assert translation["reference_clean_latent_sha256"] == tensor_hash(actual_ref)
            assert translation["max_translation_residual_seconds"] <= 1e-6
            assert tensor_hash(positions[:, :, :2304]) == cfg["base_video_positions_sha256"]
            audio = torch.load(directory / "audio_positions.pt", map_location="cpu", weights_only=True)
            assert tensor_hash(audio) == common["audio_positions_sha256"]
            initial = torch.load(directory / "target_initial_noise.pt", map_location="cpu", weights_only=True)
            steps = torch.load(directory / "target_step_noises.pt", map_location="cpu", weights_only=True)
            assert torch.equal(initial, baseline_initial) and len(steps) == 7
            assert all(torch.equal(a, b) for a, b in zip(steps, baseline_steps))
            assert cfg["final_frozen_max_abs_error"] == 0 and len(cfg["denoising_trace"]) == 8
            assert all(row["frozen_max_abs_error"] == 0 for row in cfg["denoising_trace"])
            latent = torch.load(directory / "generated_latent.pt", map_location="cpu", weights_only=True)
            assert tuple(latent.shape) == (1, 128, 16, 9, 16) and torch.isfinite(latent).all()
            assert torch.equal(latent[:, :, :7], tensors["local"])
            decoder = json.loads((directory / "decoder_result.json").read_text())
            assert cfg["decoder_result_sha256"] == sha256(directory / "decoder_result.json")
            assert decoder["input_latent_file_sha256"] == sha256(directory / "generated_latent.pt")
            assert decoder["outputs"] == cfg["outputs"] and decoder["decoder_seed"] == 20042
            assert decoder["decoder_script_sha256"] == cfg["decoder_script_sha256"] == sha256(snapshot / "decode_five_case_latent.py")
            counts = {}
            for key, artifact in cfg["outputs"].items():
                assert sha256(Path(artifact["path"])) == artifact["sha256"]
                with av.open(artifact["path"]) as container:
                    frames = list(container.decode(video=0))
                assert len(frames) == {"target": 72, "continuation": 120, "decoded_full": 121}[key]
                assert all(f.pts*f.time_base == Fraction(i, 24) and (f.width, f.height) == (512, 288) for i, f in enumerate(frames))
                counts[key] = len(frames)
            provenance.append({"example_id": name, "cell": cell, "config_sha256": sha256(directory / "config.json"),
                               "reference_clean_tokens_sha256": tensor_hash(actual_ref), "positions_tensor_sha256": tensor_hash(positions),
                               "generated_latent_tensor_sha256": tensor_hash(latent), "full_decoded_frames_and_pts": counts})
            result[cell] = cfg
        configs[name] = result
    return configs, {"status": "passed", "new_generations": 15, "reused_reference_generations": 5, "reused_local_generations": 5,
                     "common_fields_checked_against_reused_image_past": fields,
                     "reused_artifact_audit_identical": True, "actual_initial_and_seven_step_noise_equal_all_25": True,
                     "reference_content_fixed_within_each_image_or_video_pair": True,
                     "only_appended_time_coordinates_translated": True, "all_frozen_errors": 0,
                     "target_frames_fully_decoded": 1800, "all_output_frames_fully_decoded": 7825,
                     "provenance": provenance, "reused_provenance": prior["provenance"]}
