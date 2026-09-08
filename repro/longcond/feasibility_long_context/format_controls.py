"""Controlled reference duplication and reassignment of reference temporal bounds."""

from dataclasses import fields, replace

import torch
from ltx_core.conditioning.item import ConditioningItem

from reference_controls import tensor_hash
from run_generation import ROOT


EXAMPLE = "pilot_001_interview_return"
CASES = {
    "A": {"name": "image_single", "key": "oracle_still", "repeats": 1, "layout": "same", "tokens": 144},
    "B": {"name": "repeat_same", "key": "oracle_still", "repeats": 10, "layout": "same", "tokens": 1440},
    "C": {"name": "repeat_spread", "key": "oracle_still", "repeats": 10, "layout": "spread", "tokens": 1440},
    "D": {"name": "video_same", "key": "oracle", "repeats": 1, "layout": "same", "tokens": 1440},
    "E": {"name": "video_spread", "key": "oracle", "repeats": 1, "layout": "spread", "tokens": 1440},
}


def case_path(case, seed=42):
    parent = ROOT / "outputs" / EXAMPLE
    if case == "A":
        return parent / f"temporal_position_seed{seed}/image_past"
    if case == "E":
        if seed == 42:
            return parent / "reference_past_seed42/oracle"
        return parent / f"temporal_position_seed{seed}/video_past"
    return parent / f"reference_format_seed{seed}" / f"{case}_{CASES[case]['name']}"


def reference_tensor(tensors, case):
    spec = CASES[case]
    source = tensors[spec["key"]]
    return source if spec["repeats"] == 1 else source.repeat(1, 1, spec["repeats"], 1, 1)


class ReferenceTimeLayout(ConditioningItem):
    """Keep all non-temporal state intact; take exact bounds from an audited anchor.

    The A template has 144 tokens, E has 1440. Repetition preserves spatial order.
    Both temporal endpoints are copied: coincident means the exact [0, 1/24) grid.
    """

    def __init__(self, base_tokens, reference_positions):
        self.base_tokens = base_tokens
        self.template = reference_positions
        self.audit = None
        self.before_positions = None

    def apply_to(self, latent_state, latent_tools):
        state = latent_state
        count = state.positions.shape[2] - self.base_tokens
        if count <= 0 or count % self.template.shape[2]:
            raise ValueError("Reference template does not divide the appended token count")
        template = self.template.to(device=state.positions.device, dtype=state.positions.dtype)
        template = template.repeat(1, 1, count // template.shape[2], 1)
        if not torch.equal(state.positions[:, 1:, self.base_tokens:], template[:, 1:]):
            raise ValueError("Reference spatial grid differs from the template")
        before = state.positions
        positions = before.clone()
        positions[:, 0, self.base_tokens:] = template[:, 0]
        result = replace(state, positions=positions)
        untouched = [f.name for f in fields(state) if f.name != "positions"]
        if not all(getattr(result, name) is getattr(state, name) for name in untouched):
            raise ValueError("Non-position state changed")
        if not torch.equal(before[:, :, :self.base_tokens], positions[:, :, :self.base_tokens]):
            raise ValueError("Base coordinates changed")
        if not torch.equal(before[:, 1:], positions[:, 1:]):
            raise ValueError("Spatial coordinates changed")
        self.before_positions = before.detach().cpu().clone()
        self.audit = {
            "base_coordinates_unchanged": True, "spatial_coordinates_unchanged": True,
            "same_non_position_state_objects": untouched,
            "reference_clean_latent_sha256": tensor_hash(result.clean_latent[:, self.base_tokens:]),
            "reference_denoise_mask_sha256": tensor_hash(result.denoise_mask[:, self.base_tokens:]),
            "reference_positions_sha256": tensor_hash(positions[:, :, self.base_tokens:]),
            "before_positions_sha256": tensor_hash(before), "after_positions_sha256": tensor_hash(positions),
            "before_time_range": [before[:, 0, self.base_tokens:].min().item(), before[:, 0, self.base_tokens:].max().item()],
            "after_time_range": [positions[:, 0, self.base_tokens:].min().item(), positions[:, 0, self.base_tokens:].max().item()],
            "unique_temporal_bounds": torch.unique(positions[0, 0, self.base_tokens:], dim=0).cpu().tolist(),
        }
        return result
