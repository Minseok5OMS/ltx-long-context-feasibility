"""Verify the actual five-case inputs, denoising controls and decoded artifacts."""

from fractions import Fraction
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image
import torch

from reference_controls import tensor_hash
from run_generation import ROOT, read_rgb, sha256


def audit_five_cases():
    protocol_path = ROOT / "configs/five_case_examples.json"
    protocol = json.loads(protocol_path.read_text())
    snapshot = ROOT / "outputs/five_case_batch/source_snapshot"
    assert sha256(snapshot / protocol_path.name) == sha256(protocol_path)
    for name in ("run_five_case_batch.py", "run_five_case_comparison.py", "prepare_five_cases.py", "reference_controls.py", "run_generation.py", "decode_five_case_latent.py"):
        assert sha256(snapshot / name) == sha256(ROOT / name), name
    # Independently compare actual coordinates to the already audited successful image/past N1.
    old = json.loads((ROOT / "reports/reference_repetition/seed42/artifact_verification.json").read_text())
    assert old["status"] == "passed"
    anchor = next(p for p in old["provenance"] if p["case"] == "N1")
    anchor_path = Path(anchor["config_path"]).parent
    n1_positions = torch.load(anchor_path / "video_positions.pt", map_location="cpu", weights_only=True)
    assert tensor_hash(n1_positions) == anchor["positions_tensor_sha256"]
    all_configs, provenance, all_noises = {}, [], []
    exclusions = {"mode", "reference_frames", "reference_source", "reference_tokens", "command", "outputs",
                  "started_at_utc", "finished_at_utc", "total_seconds", "diffusion_seconds_including_load", "peak_gpu_allocated_gib",
                  "decoder_seconds", "decoder_peak_gpu_allocated_gib", "decoder_result_sha256"}
    paired_fields = None
    for example in protocol["examples"]:
        name = example["example_id"]
        data = ROOT / "data" / name
        metadata = json.loads((data / "metadata.json").read_text())
        assert all(metadata[k] == v for k, v in example.items())
        assert metadata["cohort_config_sha256"] == sha256(protocol_path)
        assert sha256(data / "source.mp4") == metadata["source_provenance"]["sha256"]
        for kind, clip in metadata["clips"].items():
            assert sha256(data / clip["file"]) == clip["sha256"]
            assert all(metadata[kind + "_start"] <= t < metadata[kind + "_end"] for t in clip["source_frame_seconds"])
        assert max(metadata["clips"]["local"]["source_frame_seconds"]) < min(metadata["clips"]["target"]["source_frame_seconds"])
        assert metadata["oracle_end"] <= metadata["local_start"]
        cache = ROOT / "outputs" / name / "five_case_inputs_512x288"
        info = json.loads((cache / "inputs.json").read_text())
        assert sha256(cache / "inputs.pt") == info["inputs_sha256"]
        assert sha256(data / "metadata.json") == info["fingerprint"]["metadata_sha256"]
        assert info["fingerprint"]["cohort_config_sha256"] == sha256(protocol_path)
        tensors = torch.load(cache / "inputs.pt", map_location="cpu", weights_only=True)
        assert set(tensors) == {"local", "oracle_still", "video_context", "audio_context"}
        assert {k: tensor_hash(v) for k, v in tensors.items()} == info["tensor_hashes"]
        assert tuple(tensors["oracle_still"].shape) == (1, 128, 1, 9, 16)
        assert tuple(tensors["local"].shape) == (1, 128, 7, 9, 16)
        assert np.array_equal(np.asarray(Image.open(cache / "oracle_image.png")), read_rgb(data / "oracle_context.mp4", 512, 288)[36])
        assert sha256(cache / "oracle_image.png") == info["oracle_image_sha256"]
        assert info["oracle_image_source_seconds"] == metadata["clips"]["oracle"]["source_frame_seconds"][36]
        configs = {mode: json.loads((ROOT / "outputs" / name / "image_past_seed42" / mode / "config.json").read_text())
                   for mode in ("local", "oracle")}
        fields = sorted(set(configs["local"]) - exclusions)
        assert set(configs["local"]) == set(configs["oracle"])
        assert paired_fields is None or paired_fields == fields
        paired_fields = fields
        for key in fields:
            assert configs["local"][key] == configs["oracle"][key], (name, key)
        for mode, cfg in configs.items():
            directory = ROOT / "outputs" / name / "image_past_seed42" / mode
            assert cfg["status"] == "completed" and not cfg["gt_video_opened"] and not info["gt_video_opened"]
            assert cfg["seed"] == 42 and cfg["physical_gpu"] in (0, 1, 2)
            assert cfg["script_sha256"] == sha256(snapshot / "run_five_case_comparison.py")
            assert cfg["controls_sha256"] == sha256(snapshot / "reference_controls.py")
            assert cfg["models"] == info["fingerprint"]["models"]
            for model in cfg["models"].values():
                stat = Path(model["path"]).stat()
                assert (stat.st_size, stat.st_mtime_ns) == (model["bytes"], model["mtime_ns"])
            assert cfg["common_inputs_sha256"] == info["inputs_sha256"]
            assert cfg["final_frozen_max_abs_error"] == 0
            assert len(cfg["denoising_trace"]) == 8 and all(t["frozen_max_abs_error"] == 0 for t in cfg["denoising_trace"])
            count = 0 if mode == "local" else 144
            assert cfg["reference_tokens"] == count and cfg["reference_frames"] == (mode == "oracle")
            if mode == "oracle":
                assert cfg["reference_source"]["image_sha256"] == info["oracle_image_sha256"]
                assert cfg["reference_source"]["source_seconds"] == info["oracle_image_source_seconds"]
            else:
                assert cfg["reference_source"] is None
            positions = torch.load(directory / "video_positions.pt", map_location="cpu", weights_only=True)
            expected_positions = n1_positions[:, :, :2304 + count]
            assert torch.equal(positions, expected_positions), (name, mode, "N1 positions")
            assert tensor_hash(positions[:, :, :2304]) == cfg["base_video_positions_sha256"]
            audio = torch.load(directory / "audio_positions.pt", map_location="cpu", weights_only=True)
            assert tensor_hash(audio) == cfg["audio_positions_sha256"]
            ref = torch.load(directory / "reference_clean_tokens.pt", map_location="cpu", weights_only=True)
            expected_ref = tensors["oracle_still"].permute(0, 2, 3, 4, 1).flatten(1, 3)[:, :count]
            assert torch.equal(ref, expected_ref), "Actual appended content must equal the one-image cache"
            initial = torch.load(directory / "target_initial_noise.pt", map_location="cpu", weights_only=True)
            steps = torch.load(directory / "target_step_noises.pt", map_location="cpu", weights_only=True)
            assert len(steps) == 7
            hashes = [tensor_hash(n) for n in [initial, *steps]]
            declared = [cfg["noise_audit"]["initial"][0]["target_sha256"],
                        *[r["target_sha256"] for r in cfg["noise_audit"]["ancestral"] if r["modality"] == "video"]]
            assert hashes == declared
            for index, noise in enumerate([initial, *steps]):
                seed = 42 if index == 0 else 10042 + 2 * (index - 1)
                expected = torch.randn((1, 2304, 128), generator=torch.Generator().manual_seed(seed), dtype=noise.dtype)[:, 1008:]
                assert torch.equal(noise, expected)
            all_noises.append(hashes)
            latent = torch.load(directory / "generated_latent.pt", map_location="cpu", weights_only=True)
            assert tuple(latent.shape) == (1, 128, 16, 9, 16) and torch.isfinite(latent).all()
            assert torch.equal(latent[:, :, :7], tensors["local"])
            decoder = json.loads((directory / "decoder_result.json").read_text())
            assert cfg["decoder_execution"] == "fresh_cuda_process" and decoder["fresh_cuda_process"]
            assert cfg["decoder_script_sha256"] == decoder["decoder_script_sha256"] == sha256(snapshot / "decode_five_case_latent.py")
            assert cfg["decoder_result_sha256"] == sha256(directory / "decoder_result.json")
            assert decoder["input_latent_file_sha256"] == sha256(directory / "generated_latent.pt")
            assert decoder["decoder_seed"] == 20042 and decoder["outputs"] == cfg["outputs"]
            decoded_counts = {}
            for kind, artifact in cfg["outputs"].items():
                assert sha256(Path(artifact["path"])) == artifact["sha256"]
                with av.open(artifact["path"]) as container:
                    frames = list(container.decode(video=0))
                expected_count = {"target": 72, "continuation": 120, "decoded_full": 121}[kind]
                assert len(frames) == expected_count
                assert all(f.pts * f.time_base == Fraction(i, 24) and (f.width, f.height) == (512, 288) for i, f in enumerate(frames))
                decoded_counts[kind] = len(frames)
            provenance.append({"example_id": name, "mode": mode, "config_sha256": sha256(directory / "config.json"),
                               "input_cache_sha256": info["inputs_sha256"], "oracle_image_sha256": info["oracle_image_sha256"],
                               "positions_tensor_sha256": tensor_hash(positions),
                               "reference_clean_tokens_sha256": tensor_hash(ref) if ref.numel() else hashlib.sha256(b"").hexdigest(),
                               "generated_latent_tensor_sha256": tensor_hash(latent), "reference_tokens": count,
                               "full_decoded_frames_and_pts": decoded_counts})
        all_configs[name] = configs
    assert all(noises == all_noises[0] for noises in all_noises)
    return all_configs, {"status": "passed", "examples": 5, "new_generations": 10, "seed": 42,
                         "paired_equal_fields": paired_fields, "cohort_config_sha256": sha256(protocol_path),
                         "actual_initial_and_seven_step_noise_equal_all_ten": True,
                         "declared_seed_reproduces_actual_target_noise": True,
                         "actual_base_and_reference_positions_match_prior_N1": True,
                         "actual_oracle_is_one_independently_encoded_past_image": True,
                         "all_steps_and_final_frozen_error": 0,
                         "target_frames_fully_decoded": 720, "all_output_frames_fully_decoded": 3130,
                         "model_provenance": "Local path, size and mtime checked; full checkpoint hashes not newly computed",
                         "provenance": provenance}
