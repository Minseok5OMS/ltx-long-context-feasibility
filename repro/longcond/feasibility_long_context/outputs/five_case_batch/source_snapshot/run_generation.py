"""Run an isolated LTX local-prefix continuation diagnostic with recorded noise and checks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
from functools import partial
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import av
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
LTX_ROOT = ROOT.parent.parent


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rgb(path: Path, width: int, height: int) -> np.ndarray:
    with av.open(str(path)) as container:
        frames = [np.asarray(ImageOps.fit(frame.to_image(), (width, height), method=Image.Resampling.LANCZOS))
                  for frame in container.decode(video=0)]
    if not frames:
        raise ValueError(f"No decoded frames: {path}")
    return np.stack(frames)


def write_video(path: Path, frames: np.ndarray, fps: int) -> dict:
    temporary = path.with_suffix(".tmp.mp4")
    with av.open(str(temporary), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height = frames.shape[2], frames.shape[1]
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "18", "preset": "fast"}
        for index, rgb in enumerate(frames):
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
            frame.pts, frame.time_base = index, Fraction(1, fps)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(temporary)) as container:
        times = [float(frame.time) for frame in container.decode(video=0)]
    if len(times) != len(frames) or any(abs(t - i / fps) > 1e-5 for i, t in enumerate(times)):
        raise ValueError(f"Encoded frame count or timestamps mismatch: {path}")
    temporary.replace(path)
    return {"path": str(path), "frames": len(frames), "fps": fps, "duration_seconds": len(frames) / fps,
            "sha256": sha256(path), "full_decode_passed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, default=ROOT / "data/pilot_000_local_cooking")
    parser.add_argument("--mode", choices=["local"], default="local")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], default=0)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=288)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--prepare-only", action="store_true", help="CPU input checks only; no model loading")
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0 or args.width % 32 or args.height % 32:
        parser.error("Width and height must be positive multiples of 32")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    for name, folder in [("TORCHINDUCTOR_CACHE_DIR", "inductor"), ("TRITON_CACHE_DIR", "triton"),
                         ("CUDA_CACHE_PATH", "cuda"), ("TORCH_EXTENSIONS_DIR", "torch_extensions")]:
        cache = ROOT / ".cache" / folder
        cache.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(cache)

    example = args.example.resolve()
    output = (args.output_dir or ROOT / "outputs" / example.name / f"local_seed{args.seed}").resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / "config.json"
    if config_path.exists():
        old = json.loads(config_path.read_text())
        if old.get("status") == "completed":
            raise FileExistsError(f"Completed output already exists. Choose a new --output-dir: {output}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(output / "run.log")])
    log = logging.getLogger("local_diagnostic")
    started = time.monotonic()
    config = {"status": "preparing", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "command": shlex.join([sys.executable, *sys.argv]), "cwd": str(Path.cwd()),
              "script_sha256": sha256(Path(__file__)), "mode": args.mode, "seed": args.seed,
              "physical_gpu": args.gpu, "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
              "width": args.width, "height": args.height, "example": str(example),
              "outputs": {}, "timings_seconds": {}}
    write_json(config_path, config)
    try:
        metadata = json.loads((example / "metadata.json").read_text())
        if args.mode not in metadata["allowed_modes"]:
            raise ValueError("Mode is not allowed for this example")
        local_info = metadata["clips"]["local"]
        local_path = example / local_info["file"]
        if sha256(local_path) != local_info["sha256"]:
            raise ValueError("Local clip differs from recorded preparation checksum")
        if metadata["local_end"] != metadata["target_start"]:
            raise ValueError("Local/target intervals must be adjacent")
        source_times = local_info["source_frame_seconds"]
        if not all(metadata["local_start"] <= t < metadata["target_start"] for t in source_times):
            raise ValueError("A conditioning frame is outside the local interval")
        fps = metadata["clip_fps"]
        local = read_rgb(local_path, args.width, args.height)
        if len(local) != local_info["frames"] or len(local) != len(source_times):
            raise ValueError("Local frame count differs from preparation metadata")
        target_frames = round((metadata["target_end"] - metadata["target_start"]) * fps)
        if len(local) % 8 or target_frames <= 0 or target_frames % 8:
            raise ValueError("This pilot adapter expects local and target frame counts divisible by 8")
        prefix = np.concatenate([local[:1], local], axis=0)
        prefix_frames = len(prefix)
        total_frames = prefix_frames + target_frames
        config.update(prompt=metadata["prompt"], prompt_enhancement=False, fps=fps,
                      local_frames=len(local), prefix_frames=prefix_frames, target_frames=target_frames,
                      total_frames=total_frames, target_decoded_slice=[prefix_frames, total_frames],
                      local_clip_sha256=local_info["sha256"], metadata_sha256=sha256(example / "metadata.json"),
                      preprocessing={"spatial": "Pillow ImageOps.fit, centered crop, Lanczos resize",
                                     "temporal": "Prepend exactly one copy of the first local frame",
                                     "prefix_source_frame_seconds": [source_times[0], *source_times],
                                     "first_frame_is_alignment_padding": True,
                                     "virtual_model_origin_source_seconds": metadata["local_start"] - 1 / fps,
                                     "normalization": "uint8 RGB / 127.5 - 1",
                                     "gt_video_opened_by_generation": False},
                      model_recipe="LTX 2.5 distilled stage 1 only; joint AV denoising, video output only",
                      guidance="SimpleDenoiser; no CFG/STG", audio_conditioning=False,
                      sampler="Euler ancestral", ancestral_eta=1.0, ancestral_s_noise=1.0,
                      ancestral_seed=args.seed + 10000, decoder_seed=args.seed + 20000,
                      stage_2_refinement=False, quantization=None, precision="bfloat16", compilation=False)
        config["outputs"]["local_context"] = write_video(output / "local_context.mp4", local, fps)
        config["outputs"]["model_prefix"] = write_video(output / "model_prefix.mp4", prefix, fps)
        if args.prepare_only:
            config["status"] = "inputs_validated"
            write_json(config_path, config)
            log.info("Input checks passed: %d prefix + %d target = %d model frames", prefix_frames, target_frames, total_frames)
            return

        import torch
        from ltx_core.components.diffusion_steps import EulerAncestralDiffusionStep
        from ltx_core.components.noisers import GaussianNoiser
        from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
        from ltx_core.loader.registry import DummyRegistry
        from ltx_core.model.transformer.attention import PytorchAttention
        from ltx_core.model.video_vae.transformer import DiffVAEMode
        from ltx_pipelines.utils.blocks import DiffusionStage, ImageConditioner, PromptEncoder, VideoDecoder
        from ltx_pipelines.utils.constants import DISTILLED_SIGMAS, detect_model_version
        from ltx_pipelines.utils.denoisers import SimpleDenoiser
        from ltx_pipelines.utils.model_paths import ModelPaths
        from ltx_pipelines.utils.samplers import euler_ancestral_denoising_loop
        from ltx_pipelines.utils.types import ModalitySpec

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in this process; run with GPU device access")
        torch.set_num_threads(8)
        torch.manual_seed(args.seed)
        device, dtype = torch.device("cuda:0"), torch.bfloat16
        torch.cuda.set_device(device)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        model_dir = LTX_ROOT / "models/ltx-2.5"
        paths = ModelPaths.from_split(
            transformer_path=str(model_dir / "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors"),
            text_encoder_path=str(model_dir / "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"),
            video_vae_path=str(model_dir / "vae/ltx-2.5-video-vae-bf16.safetensors"))
        config["models"] = {name: {"path": path, "size_bytes": Path(path).stat().st_size,
                                    "mtime_ns": Path(path).stat().st_mtime_ns}
                            for name, path in [("transformer", paths.transformer()), ("video_vae", paths.video_vae()),
                                               ("text_encoder", paths.text_encoder())]}
        config["ltx_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LTX_ROOT, text=True).strip()
        config["environment"] = {"torch": torch.__version__, "cuda_runtime": torch.version.cuda,
                                 "gpu_name": torch.cuda.get_device_name(device), "python": sys.version}
        config["model_version"] = list(detect_model_version(paths.transformer()))
        config["sigmas"] = DISTILLED_SIGMAS.tolist()
        attention = PytorchAttention()
        config["attention"] = attention.label
        registry = DummyRegistry()
        config["status"] = "running"
        write_json(config_path, config)

        def tensor_digest(value):
            return hashlib.sha256(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()

        with torch.inference_mode():
            tick = time.monotonic()
            encoder = ImageConditioner(paths.video_vae(), dtype, device, registry=registry)
            prefix_tensor = torch.from_numpy(prefix.copy()).permute(3, 0, 1, 2).unsqueeze(0)
            prefix_tensor = (prefix_tensor.to(device=device, dtype=dtype) / 127.5 - 1).contiguous()
            local_latent = encoder(lambda enc: enc(prefix_tensor))
            del prefix_tensor
            prefix_latent_frames = (prefix_frames - 1) // 8 + 1
            expected_shape = (1, 128, prefix_latent_frames, args.height // 32, args.width // 32)
            if tuple(local_latent.shape) != expected_shape or not torch.isfinite(local_latent).all():
                raise ValueError(f"Invalid local latent: {local_latent.shape}")
            torch.save(local_latent.cpu(), output / "local_latent.pt")
            config["local_latent_shape"] = list(local_latent.shape)
            config["local_latent_sha256"] = tensor_digest(local_latent)
            config["timings_seconds"]["local_encode"] = time.monotonic() - tick
            log.info("Local encoded: %s; only past source frames used", tuple(local_latent.shape))

            tick = time.monotonic()
            (context,) = PromptEncoder(paths, dtype, device, registry=registry)([metadata["prompt"]], enhance_first_prompt=False)
            torch.save({"video": context.video_encoding.cpu(), "audio": context.audio_encoding.cpu()}, output / "prompt_context.pt")
            config["timings_seconds"]["prompt_encode"] = time.monotonic() - tick
            token_offset = prefix_latent_frames * (args.height // 32) * (args.width // 32)

            class RecordedNoiser(GaussianNoiser):
                def __init__(self):
                    super().__init__(torch.Generator(device=device).manual_seed(args.seed))
                    self.calls = 0

                def _sample_noise(self, latent_state):
                    noise = super()._sample_noise(latent_state)
                    if self.calls == 0:
                        target_noise = noise[:, token_offset:].detach().cpu()
                        torch.save(target_noise, output / "target_initial_noise.pt")
                        config["target_noise_sha256"] = tensor_digest(target_noise)
                        config["target_noise_shape"] = list(target_noise.shape)
                    self.calls += 1
                    return noise

            trace = []
            simple = SimpleDenoiser(context.video_encoding, context.audio_encoding)

            def checked_denoiser(transformer, video_state, audio_state, sigmas, step_index):
                frozen_error = (video_state.latent[:, :token_offset] - video_state.clean_latent[:, :token_offset]).abs().max().item()
                if frozen_error != 0 or video_state.denoise_mask[:, :token_offset].count_nonzero().item():
                    raise ValueError("Local latent conditioning changed during denoising")
                if not torch.isfinite(video_state.latent).all():
                    raise ValueError("Non-finite video state")
                tick = time.monotonic()
                result = simple(transformer, video_state, audio_state, sigmas, step_index)
                torch.cuda.synchronize(device)
                if not torch.isfinite(result[0].denoised).all():
                    raise ValueError("Non-finite denoiser output")
                trace.append({"step": step_index, "sigma": float(sigmas[step_index]),
                              "local_latent_max_abs_error": frozen_error, "seconds": time.monotonic() - tick})
                write_json(output / "denoising_trace.json", {"steps": trace})
                log.info("Denoising step %d/%d complete; local latent error %.1f", step_index + 1, len(sigmas) - 1, frozen_error)
                return result

            stage = DiffusionStage.from_checkpoint(paths.transformer(), dtype, device, registry=registry).with_attention(attention)
            tick = time.monotonic()
            state, audio_state = stage(
                denoiser=checked_denoiser, sigmas=DISTILLED_SIGMAS.to(device=device, dtype=torch.float32),
                noiser=RecordedNoiser(), width=args.width, height=args.height, frames=total_frames, fps=fps,
                video=ModalitySpec(context=context.video_encoding,
                                   conditionings=[VideoConditionByLatentIndex(local_latent, strength=1.0, latent_idx=0)]),
                audio=ModalitySpec(context=context.audio_encoding),
                stepper=EulerAncestralDiffusionStep(eta=1.0, s_noise=1.0),
                loop=partial(euler_ancestral_denoising_loop, noise_seed=args.seed + 10000, model_dtype=dtype))
            torch.cuda.synchronize(device)
            config["timings_seconds"]["diffusion_including_load"] = time.monotonic() - tick
            final_error = (state.latent[:, :, :prefix_latent_frames] - local_latent).abs().max().item()
            if final_error != 0 or not torch.isfinite(state.latent).all():
                raise ValueError("Invalid final latent or modified local prefix")
            config["final_local_latent_max_abs_error"] = final_error
            config["generated_latent_shape"] = list(state.latent.shape)
            torch.save(state.latent.cpu(), output / "generated_latent.pt")
            del audio_state, context, local_latent
            write_json(config_path, config)

            tick = time.monotonic()
            decoder = VideoDecoder(paths.video_vae(), dtype, device, registry=registry,
                                   diffvae_optimization=DiffVAEMode.CHUNKED_EAGER)
            decoded = []
            for chunk in decoder(state.latent, tiling_config=None,
                                 generator=torch.Generator(device=device).manual_seed(args.seed + 20000)):
                if not torch.isfinite(chunk).all():
                    raise ValueError("Non-finite decoded pixels")
                decoded.append((chunk.clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy())
            rgb = np.concatenate(decoded)
            if rgb.shape != (total_frames, args.height, args.width, 3):
                raise ValueError(f"Unexpected decoded video shape: {rgb.shape}")
            config["timings_seconds"]["video_decode"] = time.monotonic() - tick
            config["peak_gpu_allocated_gib"] = torch.cuda.max_memory_allocated(device) / 2**30
            config["peak_gpu_reserved_gib"] = torch.cuda.max_memory_reserved(device) / 2**30

        generated = rgb[prefix_frames:]
        config["outputs"]["local_only"] = write_video(output / "local_only.mp4", generated, fps)
        config["outputs"]["decoded_model_sequence"] = write_video(output / "decoded_model_sequence.mp4", rgb, fps)
        config["outputs"]["local_then_generated"] = write_video(output / "local_then_generated.mp4", np.concatenate([local, generated]), fps)
        config["decoded_prefix_rgb_mae_0_255"] = float(np.abs(rgb[1:prefix_frames].astype(np.float32) - local.astype(np.float32)).mean())
        config["status"] = "completed"
        config["total_seconds"] = time.monotonic() - started
        config["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(config_path, config)
        log.info("Completed: %s; target %d frames; %.1fs total", output / "local_only.mp4", len(generated), config["total_seconds"])
    except Exception as exc:
        config.update(status="failed", error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
        write_json(config_path, config)
        log.exception("Local diagnostic failed")
        raise


if __name__ == "__main__":
    main()
