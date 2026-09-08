"""Protect the causal grid and exact compatibility with the two existing anchors."""

import unittest

import torch
from ltx_core.components.patchifiers import VideoLatentPatchifier
from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
from ltx_core.tools import VideoLatentTools
from ltx_core.types import VideoLatentShape

from reference_controls import ShiftTime
from temporal_controls import ShiftReferenceTime
from run_generation import ROOT


class TemporalControlsTest(unittest.TestCase):
    def test_only_reference_time_changes_and_video_width_is_preserved(self):
        tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 2, 2), 24)
        state = ShiftTime(97 / 24).apply_to(tools.create_initial_state("cpu", torch.bfloat16), tools)
        for frames, pixels in [(1, 1), (10, 73)]:
            ref = torch.ones(1, 128, frames, 2, 2, dtype=torch.bfloat16)
            past = VideoConditionByKeyframeIndex(ref, frame_idx=0, strength=1, num_pixel_frames=pixels).apply_to(state, tools)
            shift = ShiftReferenceTime(64, 146 / 24)
            target = shift.apply_to(past, tools)
            self.assertTrue(torch.equal(target.positions[:, :, :64], past.positions[:, :, :64]))
            self.assertTrue(torch.equal(target.positions[:, 1:], past.positions[:, 1:]))
            self.assertIs(target.clean_latent, past.clean_latent)
            self.assertIs(target.denoise_mask, past.denoise_mask)
            self.assertTrue(torch.allclose(target.positions[:, 0, 64:].diff(dim=-1),
                                           past.positions[:, 0, 64:].diff(dim=-1), atol=1e-6, rtol=0))
            self.assertAlmostEqual(target.positions[:, 0, 64:].max().item(), (146 + pixels) / 24, places=5)
            naive = VideoConditionByKeyframeIndex(ref, frame_idx=146, strength=1, num_pixel_frames=pixels).apply_to(state, tools)
            if frames == 1:
                self.assertTrue(torch.equal(target.positions, naive.positions))
            else:
                self.assertFalse(torch.equal(target.positions, naive.positions))
                self.assertAlmostEqual(naive.positions[:, 0, 64:].max().item(), (146 + 80) / 24, places=5)

    def test_actual_cached_inputs_reproduce_existing_anchor_positions(self):
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        root = ROOT / "outputs/pilot_001_interview_return"
        tensors = torch.load(root / "reference_inputs_512x288/inputs.pt", map_location=device, weights_only=True)
        tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 9, 16), 24)
        state = ShiftTime(97 / 24).apply_to(tools.create_initial_state(device, torch.bfloat16), tools)
        state = VideoConditionByLatentIndex(tensors["local"], 1, 0).apply_to(state, tools)
        for key, pixels, seconds, layout in [("oracle", 73, 0, "past"), ("oracle_still", 1, 146 / 24, "target_guide")]:
            ref = VideoConditionByKeyframeIndex(tensors[key], frame_idx=0, strength=1, num_pixel_frames=pixels).apply_to(state, tools)
            result = ShiftReferenceTime(2304, seconds).apply_to(ref, tools)
            saved = torch.load(root / f"reference_{layout}_seed42/oracle/video_positions.pt", map_location="cpu", weights_only=True)
            actual = result.positions.cpu()
            if device == "cpu":
                # CUDA division uses reciprocal multiplication; CPU can differ by 1 ULP.
                self.assertTrue(torch.allclose(actual, saved, atol=1e-6, rtol=0), layout)
            else:
                self.assertTrue(torch.equal(actual, saved), layout)


if __name__ == "__main__":
    unittest.main()
