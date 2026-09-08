"""Translate appended reference times without changing the causal time grid."""

from dataclasses import fields, replace

import torch
from ltx_core.conditioning.item import ConditioningItem

from reference_controls import tensor_hash


class ShiftReferenceTime(ConditioningItem):
    def __init__(self, base_tokens: int, seconds: float):
        self.base_tokens = base_tokens
        self.seconds = seconds
        self.audit = None
        self.before_positions = None

    def apply_to(self, latent_state, latent_tools):
        before = latent_state.positions
        if before.shape[2] <= self.base_tokens:
            raise ValueError("Expected appended reference tokens")
        positions = before.clone()
        positions[:, 0, self.base_tokens:] += self.seconds
        result = replace(latent_state, positions=positions)
        # Everything other than positions must remain the very same object.
        unchanged = [f.name for f in fields(latent_state) if f.name != "positions"]
        if not all(getattr(result, k) is getattr(latent_state, k) for k in unchanged):
            raise ValueError("Non-position state changed")
        if not torch.equal(before[:, :, :self.base_tokens], positions[:, :, :self.base_tokens]):
            raise ValueError("Base coordinates changed")
        if not torch.equal(before[:, 1:], positions[:, 1:]):
            raise ValueError("Spatial coordinates changed")
        ref_before, ref_after = before[:, 0, self.base_tokens:], positions[:, 0, self.base_tokens:]
        residual = (ref_after - ref_before - self.seconds).abs().max().item()
        if residual > 1e-6:
            raise ValueError("Reference times are not a uniform translation")
        self.before_positions = before.detach().cpu().clone()
        self.audit = {
            "offset_seconds": self.seconds,
            "max_translation_residual_seconds": residual,
            "base_coordinates_unchanged": True, "spatial_coordinates_unchanged": True,
            "same_non_position_state_objects": unchanged,
            "reference_clean_latent_sha256": tensor_hash(result.clean_latent[:, self.base_tokens:]),
            "before_positions_sha256": tensor_hash(before), "after_positions_sha256": tensor_hash(positions),
            "before_time_range": [ref_before.min().item(), ref_before.max().item()],
            "after_time_range": [ref_after.min().item(), ref_after.max().item()],
        }
        return result
