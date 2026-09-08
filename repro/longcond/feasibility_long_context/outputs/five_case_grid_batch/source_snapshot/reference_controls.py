"""Condition positions and paired noise for controlled reference experiments."""

from dataclasses import replace
import hashlib

import torch

from ltx_core.components.noisers import GaussianNoiser
from ltx_core.conditioning.item import ConditioningItem


def tensor_hash(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


class ShiftTime(ConditioningItem):
    """Shift current video/audio token times, leaving any later appended reference alone."""

    def __init__(self, seconds: float):
        self.seconds = seconds

    def apply_to(self, latent_state, latent_tools):
        positions = latent_state.positions.clone()
        positions[:, 0] += self.seconds
        return replace(latent_state, positions=positions)


class PairedNoise:
    """Generate common base-video/audio noise on CPU; appended clean tokens get zeros.

    Each invocation must alternate video then audio, matching the upstream AV loop.
    Separate deterministic seeds per step/modality prevent reference-count RNG drift.
    """

    def __init__(self, seed: int, base_video_tokens: int, prefix_tokens: int):
        self.seed = seed
        self.base_video_tokens = base_video_tokens
        self.prefix_tokens = prefix_tokens
        self.calls = 0
        self.audit = []
        self.target_tensors = []

    def __call__(self, tensor: torch.Tensor, generator=None):
        role, step = self.calls % 2, self.calls // 2
        shape = list(tensor.shape)
        if role == 0:
            if shape[1] < self.base_video_tokens:
                raise ValueError("Video state is smaller than the fixed generation grid")
            shape[1] = self.base_video_tokens
        noise = torch.randn(shape, generator=torch.Generator(device="cpu").manual_seed(self.seed + 2 * step + role),
                            dtype=tensor.dtype, device="cpu")
        record = {"step": step, "modality": "video" if role == 0 else "audio",
                  "seed": self.seed + 2 * step + role, "base_shape": shape, "base_sha256": tensor_hash(noise)}
        if role == 0:
            target = noise[:, self.prefix_tokens:].clone()
            record["target_sha256"] = tensor_hash(target)
            self.target_tensors.append(target)
            extra_tokens = tensor.shape[1] - self.base_video_tokens
            if extra_tokens:
                noise = torch.cat([noise, torch.zeros((shape[0], extra_tokens, shape[2]), dtype=noise.dtype)], dim=1)
        self.audit.append(record)
        self.calls += 1
        return noise.to(tensor.device)


class PairedNoiser(GaussianNoiser):
    def __init__(self, noise: PairedNoise):
        super().__init__(torch.Generator(device="cpu"))
        self.noise = noise

    def _sample_noise(self, latent_state):
        return self.noise(latent_state.latent)
