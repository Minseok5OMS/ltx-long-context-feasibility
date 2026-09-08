"""Run the frozen five-source Local/Oracle past-image protocol in isolated processes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import numpy as np
from PIL import Image

from run_generation import LTX_ROOT, ROOT, read_rgb, sha256, write_json, write_video


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--example", type=Path, required=True)
    p.add_argument("--gpu", type=int, choices=[0, 1, 2], default=0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--mode", choices=["local", "oracle"], default="local")
    p.add_argument("--all-modes", action="store_true")
    p.add_argument("--prepare-inputs", action="store_true")
    p.add_argument("--layout", choices=["image_past"], default="image_past")
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--height", type=int, default=288)
    args = p.parse_args()
    if min(args.width, args.height) <= 0 or args.width % 32 or args.height % 32:
        p.error("Resolution must be positive multiples of 32")
    return args


def main():
    args = parse_args()
    if args.all_modes and not args.prepare_inputs:
        # The diffusion VAE can retain invalid device state across repeated loads.
        # Isolate each complete inference in a fresh process, as in individual runs.
        child_args = [arg for arg in sys.argv[1:] if arg != "--all-modes"]
        for mode in ["local", "oracle"]:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), *child_args, "--mode", mode], check=True)
        return
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
    from ltx_pipelines.utils.blocks import DiffusionStage, ImageConditioner, PromptEncoder, VideoDecoder
    from ltx_pipelines.utils.constants import DISTILLED_SIGMAS
    from ltx_pipelines.utils.denoisers import SimpleDenoiser
    from ltx_pipelines.utils.model_paths import ModelPaths
    from ltx_pipelines.utils.samplers import euler_ancestral_denoising_loop
    from ltx_pipelines.utils.types import ModalitySpec
    from reference_controls import PairedNoise, PairedNoiser, ShiftTime, tensor_hash

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("reference_comparison")
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
    metadata = json.loads((example / "metadata.json").read_text())
    fps = metadata["clip_fps"]
    cohort_path = ROOT / "configs/five_case_examples.json"
    cohort = json.loads(cohort_path.read_text())
    entry = next(e for e in cohort["examples"] if e["example_id"] == example.name)
    if any(metadata[k] != v for k, v in entry.items()) or metadata["cohort_config_sha256"] != sha256(cohort_path):
        raise ValueError("Prepared metadata differs from frozen cohort")
    if (args.seed, args.width, args.height, fps) != (42, 512, 288, 24):
        raise ValueError("This cohort fixes seed 42, 512x288 and 24 FPS")
    if metadata["local_end"] != metadata["target_start"]:
        raise ValueError("Local must immediately precede target")
    cache = ROOT / "outputs" / example.name / f"five_case_inputs_{args.width}x{args.height}"
    cache.mkdir(parents=True, exist_ok=True)
    fingerprint = {"recipe": "five_case_image_past_v1", "cohort_config_sha256": sha256(cohort_path), "metadata_sha256": sha256(example / "metadata.json"),
                   "width": args.width, "height": args.height, "models": models}
    clips = {}
    for kind in ["local", "oracle"]:
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
    target_frames = round((metadata["target_end"] - metadata["target_start"]) * fps)
    prefix_frames = len(clips["local"]) + 1
    reference_frames = len(clips["oracle"]) + 1
    total_frames = prefix_frames + target_frames
    if target_frames <= 0 or target_frames % 8:
        raise ValueError("Target must be a positive multiple of 8 frames")
    base_tokens = ((total_frames - 1) // 8 + 1) * (args.height // 32) * (args.width // 32)
    prefix_latent_frames = (prefix_frames - 1) // 8 + 1
    prefix_tokens = prefix_latent_frames * (args.height // 32) * (args.width // 32)
    common_shift_frames = 97  # Match the successful N1 image/past protocol exactly
    common_shift = common_shift_frames / fps
    registry = DummyRegistry()

    with torch.inference_mode():
        cache_info = json.loads((cache / "inputs.json").read_text()) if (cache / "inputs.json").exists() else None
        if cache_info is None or cache_info["fingerprint"] != fingerprint:
            log.info("Preparing common local, reference and prompt tensors on GPU %d", args.gpu)
            torch.manual_seed(0)
            encoder = ImageConditioner(paths.video_vae(), dtype, device, registry=registry)

            def encode_all(enc):
                result = {}
                for kind, rgb in clips.items():
                    if kind == "local":
                        padded = np.concatenate([rgb[:1], rgb])
                        tensor = torch.from_numpy(padded.copy()).permute(3, 0, 1, 2).unsqueeze(0).to(device=device, dtype=dtype)
                        result[kind] = enc((tensor / 127.5 - 1).contiguous()).cpu()
                    else:
                        # Exactly one past RGB image is independently VAE-encoded.
                        still = torch.from_numpy(rgb[len(rgb) // 2].copy()).permute(2, 0, 1)[None, :, None].to(device=device, dtype=dtype)
                        result[kind + "_still"] = enc((still / 127.5 - 1).contiguous()).cpu()
                return result

            tensors = encoder(encode_all)
            (context,) = PromptEncoder(paths, dtype, device, registry=registry)([metadata["prompt"]], enhance_first_prompt=False)
            tensors.update(video_context=context.video_encoding.cpu(), audio_context=context.audio_encoding.cpu())
            if any(not torch.isfinite(t).all() for t in tensors.values()):
                raise ValueError("Non-finite prepared tensors")
            torch.save(tensors, cache / "inputs.pt")
            cache_info = {"fingerprint": fingerprint, "inputs_sha256": sha256(cache / "inputs.pt"),
                          "tensor_hashes": {k: tensor_hash(v) for k, v in tensors.items()},
                          "shapes": {k: list(v.shape) for k, v in tensors.items()},
                          "preprocessing": "Local 48 frames prepended to 49; oracle clip frame 36 encoded independently as one RGB image; centered Lanczos crop/resize; RGB/127.5-1",
                          "reference_still_clip_frame_index": len(clips["oracle"]) // 2,
                          "gt_video_opened": False,
                          "command": shlex.join([sys.executable, *sys.argv])}
            Image.fromarray(clips["oracle"][36]).save(cache / "oracle_image.png")
            cache_info["oracle_image_sha256"] = sha256(cache / "oracle_image.png")
            cache_info["oracle_image_source_seconds"] = metadata["oracle_image_source_seconds"]
            write_json(cache / "inputs.json", cache_info)
            for kind, rgb in clips.items():
                write_video(cache / f"{kind}_context.mp4", rgb, fps)
            log.info("Common input cache complete: %s", cache)
        elif sha256(cache / "inputs.pt") != cache_info["inputs_sha256"]:
            raise ValueError("Common cache checksum mismatch")
        if args.prepare_inputs:
            return
        tensors = torch.load(cache / "inputs.pt", map_location=device, weights_only=True)
        local_latent = tensors["local"]
        expected_local_shape = (1, 128, prefix_latent_frames, args.height // 32, args.width // 32)
        if tuple(local_latent.shape) != expected_local_shape:
            raise ValueError("Local latent shape mismatch")

        for mode in (["local", "oracle"] if args.all_modes else [args.mode]):
            if mode not in metadata["allowed_modes"]:
                raise ValueError("Mode disallowed by example metadata")
            output = ROOT / "outputs" / example.name / f"{args.layout}_seed{args.seed}" / mode
            output.mkdir(parents=True, exist_ok=True)
            config_path = output / "config.json"
            if config_path.exists() and json.loads(config_path.read_text()).get("status") == "completed":
                old = json.loads(config_path.read_text())
                if old["common_inputs_sha256"] != cache_info["inputs_sha256"] or old["script_sha256"] != sha256(Path(__file__)):
                    raise ValueError(f"Completed run has different inputs/code: {output}")
                log.info("Skipping already completed %s", output)
                continue
            handler = logging.FileHandler(output / "run.log")
            logging.getLogger().addHandler(handler)
            torch.manual_seed(args.seed)
            torch.cuda.reset_peak_memory_stats(device)
            started = time.monotonic()
            cfg = {"status": "running", "example": str(example), "example_id": example.name, "mode": mode,
                   "layout": args.layout, "seed": args.seed, "physical_gpu": args.gpu, "cuda_visible_devices": str(args.gpu),
                   "command": shlex.join([sys.executable, *sys.argv]), "cwd": str(Path.cwd()),
                   "script_sha256": sha256(Path(__file__)), "cohort_config_sha256": sha256(cohort_path), "controls_sha256": sha256(ROOT / "reference_controls.py"),
                   "ltx_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LTX_ROOT, text=True).strip(),
                   "started_at_utc": datetime.now(timezone.utc).isoformat(), "models": models,
                   "environment": {"torch": torch.__version__, "cuda": torch.version.cuda, "gpu_name": torch.cuda.get_device_name(device)},
                   "prompt": metadata["prompt"], "prompt_enhancement": False, "fps": fps, "width": args.width, "height": args.height,
                   "prefix_frames": prefix_frames, "target_frames": target_frames, "total_frames": total_frames,
                   "target_decoded_slice": [prefix_frames, total_frames], "base_video_tokens": base_tokens,
                   "prefix_tokens": prefix_tokens, "common_time_shift_seconds": common_shift,
                   "reference_model_time_range": [0, 1 / fps],
                   "target_model_time_range": [(common_shift_frames + prefix_frames) / fps, (common_shift_frames + total_frames) / fps],
                   "source_dependency_gap_seconds": metadata["target_start"] - metadata["oracle_end"],
                   "reference_frames": 0 if mode == "local" else 1,
                   "reference_source": None if mode == "local" else {"kind": mode, "selection_interval": [metadata[mode + "_start"], metadata[mode + "_end"]], "clip_frame_index": 36, "source_seconds": metadata["oracle_image_source_seconds"], "image_sha256": cache_info["oracle_image_sha256"]},
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
                if mode != "local":
                    reference = tensors["oracle_still"]
                    reference_index = 0
                    conditions.append(VideoConditionByKeyframeIndex(reference, frame_idx=reference_index, strength=1.0,
                                                                    num_pixel_frames=1))
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
                        torch.save(video_state.positions.cpu(), output / "video_positions.pt")
                        torch.save(video_state.clean_latent[:, base_tokens:].cpu(), output / "reference_clean_tokens.pt")
                        torch.save(audio_state.positions.cpu(), output / "audio_positions.pt")
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
                cfg.update(status="denoised", decoder_execution="fresh_cuda_process",
                           decoder_script_sha256=sha256(ROOT / "decode_five_case_latent.py"))
                write_json(config_path, cfg)
                subprocess.run([sys.executable, str(ROOT / "decode_five_case_latent.py"), "--config", str(config_path),
                                "--output-dir", str(output)], check=True)
                decoded = json.loads((output / "decoder_result.json").read_text())
                if decoded["input_latent_file_sha256"] != sha256(output / "generated_latent.pt"):
                    raise ValueError("Decoder input does not match saved generation")
                cfg["outputs"] = decoded["outputs"]
                cfg["decoder_seconds"] = decoded["seconds"]
                cfg["decoder_peak_gpu_allocated_gib"] = decoded["peak_gpu_allocated_gib"]
                cfg["decoder_result_sha256"] = sha256(output / "decoder_result.json")
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
