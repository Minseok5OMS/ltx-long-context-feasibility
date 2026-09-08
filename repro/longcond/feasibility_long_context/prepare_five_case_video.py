"""Add independently encoded Oracle video to the unchanged five-case image caches."""

import argparse
import json
import os
from pathlib import Path
import shlex
import sys

import numpy as np

from run_generation import ROOT, read_rgb, sha256, write_json, write_video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--gpu", type=int, choices=[0, 1, 2], required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
    os.environ["HF_HUB_OFFLINE"] = "1"
    for key, folder in (("TORCHINDUCTOR_CACHE_DIR", "inductor"), ("TRITON_CACHE_DIR", "triton"), ("CUDA_CACHE_PATH", "cuda")):
        os.environ[key] = str(ROOT / ".cache" / folder)
    import torch
    from ltx_core.loader.registry import DummyRegistry
    from ltx_pipelines.utils.blocks import ImageConditioner
    from reference_controls import tensor_hash

    torch.set_num_threads(8)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    data = args.example.resolve()
    metadata = json.loads((data / "metadata.json").read_text())
    old_cache = ROOT / "outputs" / data.name / "five_case_inputs_512x288"
    old_info = json.loads((old_cache / "inputs.json").read_text())
    assert sha256(old_cache / "inputs.pt") == old_info["inputs_sha256"]
    assert sha256(data / "metadata.json") == old_info["fingerprint"]["metadata_sha256"]
    clip = metadata["clips"]["oracle"]
    assert sha256(data / clip["file"]) == clip["sha256"]
    assert all(metadata["oracle_start"] <= t < metadata["oracle_end"] <= metadata["local_start"] for t in clip["source_frame_seconds"])
    directory = ROOT / "outputs" / data.name / "five_case_video_inputs_512x288"
    directory.mkdir(parents=True, exist_ok=True)
    fingerprint = {"recipe": "five_case_oracle_video_v1", "metadata_sha256": sha256(data / "metadata.json"),
                   "parent_cache_sha256": old_info["inputs_sha256"], "source_clip_sha256": clip["sha256"],
                   "vae": old_info["fingerprint"]["models"]["video_vae"], "script_sha256": sha256(Path(__file__))}
    if (directory / "inputs.json").exists():
        previous = json.loads((directory / "inputs.json").read_text())
        assert previous["fingerprint"] == fingerprint and sha256(directory / "inputs.pt") == previous["inputs_sha256"]
        print(f"Verified existing video cache: {data.name}")
        return
    rgb = read_rgb(data / clip["file"], 512, 288)
    assert rgb.shape == (72, 288, 512, 3)
    padded = np.concatenate([rgb[:1], rgb])
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
    torch.manual_seed(0)
    with torch.inference_mode():
        encoder = ImageConditioner(fingerprint["vae"]["path"], torch.bfloat16, device, registry=DummyRegistry())
        def encode(enc):
            tensor = torch.from_numpy(padded.copy()).permute(3, 0, 1, 2).unsqueeze(0).to(device=device, dtype=torch.bfloat16)
            return enc((tensor / 127.5 - 1).contiguous()).cpu()
        latent = encoder(encode)
    assert tuple(latent.shape) == (1, 128, 10, 9, 16) and torch.isfinite(latent).all()
    torch.save({"oracle_video": latent}, directory / "inputs.pt")
    preview = write_video(directory / "oracle_padded_input.mp4", padded, 24)
    write_json(directory / "inputs.json", {"fingerprint": fingerprint, "inputs_sha256": sha256(directory / "inputs.pt"),
               "tensor_hashes": {"oracle_video": tensor_hash(latent)}, "shapes": {"oracle_video": list(latent.shape)},
               "source_frame_seconds": [clip["source_frame_seconds"][0], *clip["source_frame_seconds"]],
               "preprocessing": "Same original 72-frame Oracle selection clip; centered Lanczos 512x288; prepend first frame to 73; independent BF16 VAE RGB/127.5-1 encoding",
               "padded_input_rgb_sha256": tensor_hash(torch.from_numpy(padded)), "input_video_preview": preview,
               "gt_video_opened": False, "physical_gpu": args.gpu, "command": shlex.join([sys.executable, *sys.argv])})
    print(f"Prepared video cache: {data.name}, {tuple(latent.shape)}, 1440 tokens", flush=True)


if __name__ == "__main__":
    main()
