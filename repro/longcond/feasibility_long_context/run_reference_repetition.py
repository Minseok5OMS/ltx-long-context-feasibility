"""Run one image repetition count, preserving the original inference recipe."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

import numpy as np

from run_generation import LTX_ROOT, ROOT, read_rgb, sha256, write_json, write_video


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--example", type=Path, default=ROOT / "data/pilot_001_interview_return")
    p.add_argument("--gpu", type=int, choices=[0, 1, 2], default=0)
    p.add_argument("--seed", type=int, choices=[42], default=42)
    p.add_argument("--case", choices=["N2", "N4"], required=True)
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--height", type=int, default=288)
    args = p.parse_args()
    if min(args.width, args.height) <= 0 or args.width % 32 or args.height % 32:
        p.error("Resolution must be positive multiples of 32")
    args.layout = args.case
    return args


def main():
    args = parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    for name, folder in [("TORCHINDUCTOR_CACHE_DIR", "inductor"), ("TRITON_CACHE_DIR", "triton"),
                         ("CUDA_CACHE_PATH", "cuda"), ("TORCH_EXTENSIONS_DIR", "torch_extensions")]:
        path = ROOT / ".cache" / folder
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    import torch
    from ltx_core.components.diffusion_steps import EulerAncestralDiffusionStep
    from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
    from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
    from ltx_core.loader.registry import DummyRegistry
    from ltx_core.model.transformer.attention import PytorchAttention
    from ltx_core.model.video_vae.transformer import DiffVAEMode
    from ltx_pipelines.utils.blocks import DiffusionStage, VideoDecoder
    from ltx_pipelines.utils.constants import DISTILLED_SIGMAS
    from ltx_pipelines.utils.denoisers import SimpleDenoiser
    from ltx_pipelines.utils.model_paths import ModelPaths
    from ltx_pipelines.utils.samplers import euler_ancestral_denoising_loop
    from ltx_pipelines.utils.types import ModalitySpec
    from reference_controls import PairedNoise, PairedNoiser, ShiftTime, tensor_hash

    from repetition_controls import CASES, EXAMPLE, ReferenceTimeLayout, case_path, reference_tensor
    from format_controls import case_path as anchor_path
    spec = CASES[args.case]

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("reference_repetition")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA access is required")
    torch.set_num_threads(8)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device, dtype = torch.device("cuda:0"), torch.bfloat16
    torch.cuda.set_device(device)
    model_dir = LTX_ROOT / "models/ltx-2.5"
    paths = ModelPaths.from_split(
        transformer_path=str(model_dir / "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors"),
        video_vae_path=str(model_dir / "vae/ltx-2.5-video-vae-bf16.safetensors"),
        text_encoder_path=str(model_dir / "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"))
    models = {name: {"path": path, "bytes": Path(path).stat().st_size, "mtime_ns": Path(path).stat().st_mtime_ns}
              for name, path in [("transformer", paths.transformer()), ("video_vae", paths.video_vae()), ("text_encoder", paths.text_encoder())]}
    example = args.example.resolve()
    if example.name != EXAMPLE or (args.width, args.height) != (512, 288):
        raise ValueError("This diagnosis uses the fixed pilot 001 input and coordinate anchors")
    metadata = json.loads((example / "metadata.json").read_text())
    fps = metadata["clip_fps"]
    if metadata["local_end"] != metadata["target_start"]:
        raise ValueError("Local must immediately precede target")
    cache = ROOT / "outputs" / example.name / f"reference_inputs_{args.width}x{args.height}"
    cache.mkdir(parents=True, exist_ok=True)
    fingerprint = {"recipe": "reference_inputs_v1", "metadata_sha256": sha256(example / "metadata.json"),
                   "width": args.width, "height": args.height, "models": models}
    clips = {}
    for kind in ["local", "random", "oracle"]:
        info = metadata["clips"][kind]
        path = example / info["file"]
        if sha256(path) != info["sha256"]:
            raise ValueError(f"Changed source clip: {kind}")
        start, end = metadata[kind + "_start"], metadata[kind + "_end"]
        if not all(start <= t < end <= metadata["target_start"] for t in info["source_frame_seconds"]):
            raise ValueError(f"Source time leakage: {kind}")
        if kind != "local" and end > metadata["local_start"]:
            raise ValueError("Distant reference overlaps local")
        clips[kind] = read_rgb(path, args.width, args.height)
        if len(clips[kind]) != info["frames"] or len(clips[kind]) % 8:
            raise ValueError("Unexpected clip length")
    if len(clips["random"]) != len(clips["oracle"]):
        raise ValueError("Reference lengths differ")
    target_frames = round((metadata["target_end"] - metadata["target_start"]) * fps)
    prefix_frames = len(clips["local"]) + 1
    reference_frames = len(clips["oracle"]) + 1
    total_frames = prefix_frames + target_frames
    if target_frames <= 0 or target_frames % 8:
        raise ValueError("Target must be a positive multiple of 8 frames")
    base_tokens = ((total_frames - 1) // 8 + 1) * (args.height // 32) * (args.width // 32)
    prefix_latent_frames = (prefix_frames - 1) // 8 + 1
    prefix_tokens = prefix_latent_frames * (args.height // 32) * (args.width // 32)
    common_shift_frames = reference_frames + fps  # 1 second empty time between reference and local
    common_shift = common_shift_frames / fps
    registry = DummyRegistry()

    with torch.inference_mode():
        cache_info = json.loads((cache / "inputs.json").read_text()) if (cache / "inputs.json").exists() else None
        if cache_info is None or cache_info["fingerprint"] != fingerprint:
            raise ValueError("This experiment requires the original, unchanged input cache")
        if sha256(cache / "inputs.pt") != cache_info["inputs_sha256"]:
            raise ValueError("Common cache checksum mismatch")
        tensors = torch.load(cache / "inputs.pt", map_location=device, weights_only=True)
        local_latent = tensors["local"]
        expected_local_shape = (1, 128, prefix_latent_frames, args.height // 32, args.width // 32)
        if tuple(local_latent.shape) != expected_local_shape:
            raise ValueError("Local latent shape mismatch")

        anchors = {case: torch.load(anchor_path(case) / "video_positions.pt", map_location=device, weights_only=True)
                   for case in ("A", "E")}
        prior_audit = json.loads((ROOT / "reports/temporal_position/artifact_verification.json").read_text())
        for case, cell in [("A", "image_past"), ("E", "video_past")]:
            record = next(r for r in prior_audit["provenance"] if r["seed"] == 42 and r["cell"] == cell)
            if tensor_hash(anchors[case]) != record["positions_tensor_sha256"] or sha256(anchor_path(case) / "config.json") != record["config_sha256"]:
                raise ValueError("Original coordinate/config anchor changed")
        template_case = "A" if spec["layout"] == "same" else "E"
        for mode in ["oracle"]:
            if mode not in metadata["allowed_modes"]:
                raise ValueError("Mode disallowed by example metadata")
            output = case_path(args.case, args.seed)
            output.mkdir(parents=True, exist_ok=True)
            config_path = output / "config.json"
            if config_path.exists() and json.loads(config_path.read_text()).get("status") == "completed":
                old = json.loads(config_path.read_text())
                if old["common_inputs_sha256"] != cache_info["inputs_sha256"] or old["script_sha256"] != sha256(Path(__file__)) or old["format_controls_sha256"] != sha256(ROOT / "format_controls.py") or old["repetition_controls_sha256"] != sha256(ROOT / "repetition_controls.py"):
                    raise ValueError(f"Completed run has different inputs/code: {output}")
                log.info("Skipping already completed %s", output)
                continue
            if config_path.exists():
                raise ValueError("Archive an incomplete prior attempt before rerunning this condition")
            snapshot = ROOT / "outputs/source_snapshots" / sha256(Path(__file__))
            snapshot.mkdir(parents=True, exist_ok=True)
            for filename in [Path(__file__).name, "run_generation.py", "reference_controls.py", "format_controls.py", "repetition_controls.py"]:
                src, dst = ROOT / filename, snapshot / filename
                if dst.exists() and sha256(dst) != sha256(src):
                    raise ValueError("Existing source snapshot differs")
                if not dst.exists():
                    shutil.copy2(src, dst)
            handler = logging.FileHandler(output / "run.log")
            logging.getLogger().addHandler(handler)
            torch.manual_seed(args.seed)
            torch.cuda.reset_peak_memory_stats(device)
            started = time.monotonic()
            ref_frames = 1 if spec["key"] == "oracle_still" else reference_frames
            cfg = {"status": "running", "example": str(example), "example_id": example.name, "mode": mode,
                   "layout": args.layout, "seed": args.seed, "physical_gpu": args.gpu, "cuda_visible_devices": str(args.gpu),
                   "command": shlex.join([sys.executable, *sys.argv]), "cwd": str(Path.cwd()),
                   "script_sha256": sha256(Path(__file__)), "controls_sha256": sha256(ROOT / "reference_controls.py"),
                   "format_controls_sha256": sha256(ROOT / "format_controls.py"),
                   "repetition_controls_sha256": sha256(ROOT / "repetition_controls.py"),
                   "case": args.case, "reference_spec": spec, "reference_latent_temporal_frames": spec["repeats"],
                   "reference_grid_rule": "Append causal video grid; copy both reference time bounds from audited A/E anchor",
                   "coordinate_template_case": template_case,
                   "coordinate_anchor_config_hashes": {k: sha256(anchor_path(k) / "config.json") for k in ("A", "E")},
                   "ltx_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LTX_ROOT, text=True).strip(),
                   "started_at_utc": datetime.now(timezone.utc).isoformat(), "models": models,
                   "environment": {"torch": torch.__version__, "cuda": torch.version.cuda, "gpu_name": torch.cuda.get_device_name(device)},
                   "prompt": metadata["prompt"], "prompt_enhancement": False, "fps": fps, "width": args.width, "height": args.height,
                   "prefix_frames": prefix_frames, "target_frames": target_frames, "total_frames": total_frames,
                   "target_decoded_slice": [prefix_frames, total_frames], "base_video_tokens": base_tokens,
                   "prefix_tokens": prefix_tokens, "common_time_shift_seconds": common_shift,
                   "reference_model_time_range": [0, (1 if spec["layout"] == "same" else 73) / fps],
                   "target_model_time_range": [(common_shift_frames + prefix_frames) / fps, (common_shift_frames + total_frames) / fps],
                   "source_dependency_gap_seconds": metadata["target_start"] - metadata["oracle_end"],
                   "reference_frames": ref_frames,
                   "reference_source": None if mode == "local" else {"kind": mode, "start": metadata[mode + "_start"], "end": metadata[mode + "_end"]},
                   "input_cache": str(cache), "common_inputs_sha256": cache_info["inputs_sha256"],
                   "local_latent_sha256": cache_info["tensor_hashes"]["local"],
                   "prompt_context_hashes": {k: cache_info["tensor_hashes"][k] for k in ["video_context", "audio_context"]},
                   "sigmas": DISTILLED_SIGMAS.tolist(), "sampler": "Euler ancestral", "eta": 1.0, "s_noise": 1.0,
                   "precision": "bfloat16", "guidance": "SimpleDenoiser; no CFG/STG", "audio": "Jointly generated, no input audio or output audio decode",
                   "initial_noise_seed": args.seed, "step_noise_seed": args.seed + 10000, "decoder_seed": args.seed + 20000,
                   "noise_policy": "CPU base grid with independent seed per modality/step, appended clean references get zero noise",
                   "gt_video_opened": False, "outputs": {}}
            write_json(config_path, cfg)
            try:
                conditions = [ShiftTime(common_shift), VideoConditionByLatentIndex(local_latent, 1.0, 0)]
                reference = reference_tensor(tensors, args.case)
                cfg["reference_source_tensor_sha256"] = tensor_hash(tensors[spec["key"]])
                cfg["reference_input_tensor_sha256"] = tensor_hash(reference)
                conditions.append(VideoConditionByKeyframeIndex(reference, frame_idx=0, strength=1.0,
                                                                num_pixel_frames=(spec["repeats"] - 1) * 8 + 1))
                reference_layout = ReferenceTimeLayout(base_tokens, anchors[template_case][:, :, base_tokens:])
                conditions.append(reference_layout)
                initial_noise = PairedNoise(args.seed, base_tokens, prefix_tokens)
                step_noise = PairedNoise(args.seed + 10000, base_tokens, prefix_tokens)
                trace = []
                simple = SimpleDenoiser(tensors["video_context"], tensors["audio_context"])

                def check_frozen(state):
                    mask = (state.denoise_mask == 0).expand_as(state.latent)
                    error = (state.latent - state.clean_latent).abs()[mask].max().item()
                    if error != 0 or not torch.isfinite(state.latent).all():
                        raise ValueError("Frozen condition changed or non-finite state")
                    expected_free = base_tokens - prefix_tokens
                    if int(state.denoise_mask.count_nonzero()) != expected_free:
                        raise ValueError("Generated token mask differs from fixed target grid")
                    return error

                def denoise(transformer, video_state, audio_state, sigmas, step_index):
                    error = check_frozen(video_state)
                    if step_index == 0:
                        expected = torch.cat([anchors["A"][:, :, :base_tokens],
                                              anchors["A"][:, :, base_tokens:].repeat(1, 1, spec["repeats"], 1)], dim=2)
                        if not torch.equal(video_state.positions, expected):
                            raise ValueError("Actual coordinates differ from the specified A/E template")
                        cfg["reference_layout_audit"] = reference_layout.audit
                        torch.save(reference_layout.before_positions, output / "video_positions_before_layout.pt")
                        torch.save(video_state.clean_latent[:, base_tokens:].cpu(), output / "reference_clean_tokens.pt")
                        torch.save(video_state.positions.cpu(), output / "video_positions.pt")
                        cfg["base_video_positions_sha256"] = tensor_hash(video_state.positions[:, :, :base_tokens])
                        cfg["audio_positions_sha256"] = tensor_hash(audio_state.positions)
                        cfg["reference_tokens"] = video_state.latent.shape[1] - base_tokens
                    result = simple(transformer, video_state, audio_state, sigmas, step_index)
                    if not torch.isfinite(result[0].denoised).all():
                        raise ValueError("Non-finite denoiser prediction")
                    trace.append({"step": step_index, "frozen_max_abs_error": error})
                    log.info("%s/%s step %d/8: frozen error=%.1f", args.layout, mode, step_index + 1, error)
                    return result

                def loop(**kwargs):
                    video_state, audio_state = euler_ancestral_denoising_loop(**kwargs, noise_seed=args.seed + 10000,
                                                                            new_noise_fn=step_noise, model_dtype=dtype)
                    cfg["final_frozen_max_abs_error"] = check_frozen(video_state)
                    return video_state, audio_state

                stage = DiffusionStage.from_checkpoint(paths.transformer(), dtype, device, registry=registry).with_attention(PytorchAttention())
                state, audio = stage(denoiser=denoise, sigmas=DISTILLED_SIGMAS.to(device), noiser=PairedNoiser(initial_noise),
                                     width=args.width, height=args.height, frames=total_frames, fps=fps,
                                     video=ModalitySpec(context=tensors["video_context"], conditionings=conditions),
                                     audio=ModalitySpec(context=tensors["audio_context"], conditionings=[ShiftTime(common_shift)]),
                                     stepper=EulerAncestralDiffusionStep(eta=1.0, s_noise=1.0), loop=loop)
                if initial_noise.calls != 2 or step_noise.calls != 14:
                    raise ValueError("Unexpected AV noise call order/count")
                if not torch.equal(state.latent[:, :, :prefix_latent_frames], local_latent):
                    raise ValueError("Final local latent mismatch")
                torch.save(initial_noise.target_tensors[0], output / "target_initial_noise.pt")
                torch.save(step_noise.target_tensors, output / "target_step_noises.pt")
                torch.save(state.latent.cpu(), output / "generated_latent.pt")
                cfg["noise_audit"] = {"initial": initial_noise.audit, "ancestral": step_noise.audit}
                cfg["denoising_trace"] = trace
                cfg["diffusion_seconds_including_load"] = time.monotonic() - started
                decoder = VideoDecoder(paths.video_vae(), dtype, device, registry=registry, diffvae_optimization=DiffVAEMode.CHUNKED_EAGER)
                chunks = []
                for chunk in decoder(state.latent, tiling_config=None, generator=torch.Generator(device=device).manual_seed(args.seed + 20000)):
                    if not torch.isfinite(chunk).all():
                        raise ValueError("Non-finite decoder output")
                    chunks.append((chunk.clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy())
                rgb = np.concatenate(chunks)
                if rgb.shape != (total_frames, args.height, args.width, 3):
                    raise ValueError("Unexpected decoded shape")
                cfg["outputs"]["target"] = write_video(output / "target.mp4", rgb[prefix_frames:], fps)
                cfg["outputs"]["continuation"] = write_video(output / "local_then_generated.mp4", np.concatenate([clips["local"], rgb[prefix_frames:]]), fps)
                cfg["outputs"]["decoded_full"] = write_video(output / "decoded_model_sequence.mp4", rgb, fps)
                cfg.update(status="completed", total_seconds=time.monotonic() - started,
                           peak_gpu_allocated_gib=torch.cuda.max_memory_allocated(device) / 2**30,
                           finished_at_utc=datetime.now(timezone.utc).isoformat())
                write_json(config_path, cfg)
                del state, audio
                log.info("Completed %s: %.1fs", output, cfg["total_seconds"])
            except Exception as exc:
                cfg.update(status="failed", error=str(exc), error_type=type(exc).__name__)
                write_json(config_path, cfg)
                log.exception("Reference comparison failed")
                raise
            finally:
                logging.getLogger().removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    main()
