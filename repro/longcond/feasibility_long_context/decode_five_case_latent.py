"""Decode saved latent in a fresh CUDA process to isolate diffusion-VAE device state."""

import argparse
import json
import os
from pathlib import Path
import time

import numpy as np

from run_generation import ROOT, read_rgb, sha256, write_json, write_video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    os.environ["CUDA_VISIBLE_DEVICES"] = str(cfg["physical_gpu"])
    os.environ["HF_HUB_OFFLINE"] = "1"
    for key, folder in (("TORCHINDUCTOR_CACHE_DIR", "inductor"), ("TRITON_CACHE_DIR", "triton"), ("CUDA_CACHE_PATH", "cuda")):
        os.environ[key] = str(ROOT / ".cache" / folder)
    import torch
    from ltx_core.loader.registry import DummyRegistry
    from ltx_core.model.video_vae.transformer import DiffVAEMode
    from ltx_pipelines.utils.blocks import VideoDecoder

    torch.set_num_threads(8)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    torch.manual_seed(cfg["seed"])
    started = time.monotonic()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    latent_path = args.config.parent / "generated_latent.pt"
    with torch.inference_mode():
        latent = torch.load(latent_path, map_location="cpu", weights_only=True).to(device)
        assert tuple(latent.shape) == (1, 128, 16, 9, 16) and torch.isfinite(latent).all()
        decoder = VideoDecoder(cfg["models"]["video_vae"]["path"], torch.bfloat16, device,
                               registry=DummyRegistry(), diffvae_optimization=DiffVAEMode.CHUNKED_EAGER)
        chunks = []
        for chunk in decoder(latent, tiling_config=None, generator=torch.Generator(device=device).manual_seed(cfg["decoder_seed"])):
            assert torch.isfinite(chunk).all()
            chunks.append((chunk.clamp(0, 1)*255).round().to(torch.uint8).cpu().numpy())
        rgb = np.concatenate(chunks)
    assert rgb.shape == (121, 288, 512, 3)
    local = read_rgb(Path(cfg["example"]) / "local_context.mp4", 512, 288)
    target_name = "local_only.mp4" if cfg["mode"] == "local" else "local_oracle.mp4"
    outputs = {"target": write_video(output / target_name, rgb[49:], 24),
               "continuation": write_video(output / "local_then_generated.mp4", np.concatenate([local, rgb[49:]]), 24),
               "decoded_full": write_video(output / "decoded_model_sequence.mp4", rgb, 24)}
    write_json(output / "decoder_result.json", {"outputs": outputs, "decoder_script_sha256": sha256(Path(__file__)),
               "input_latent_file_sha256": sha256(latent_path), "decoder_seed": cfg["decoder_seed"],
               "optimization": "CHUNKED_EAGER", "fresh_cuda_process": True, "seconds": time.monotonic()-started,
               "peak_gpu_allocated_gib": torch.cuda.max_memory_allocated(device)/2**30})


if __name__ == "__main__":
    main()
