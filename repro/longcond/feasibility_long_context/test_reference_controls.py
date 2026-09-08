"""Checks for scientific controls that would invalidate the reference comparison if broken."""

import unittest

import torch
from ltx_core.components.patchifiers import VideoLatentPatchifier
from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
from ltx_core.tools import VideoLatentTools
from ltx_core.types import VideoLatentShape

from reference_controls import PairedNoise, PairedNoiser, ShiftTime


class ReferenceControlsTest(unittest.TestCase):
    def test_reference_count_cannot_change_initial_or_step_noise(self):
        base = torch.zeros(1, 64, 128, dtype=torch.bfloat16)
        extended = torch.zeros(1, 104, 128, dtype=torch.bfloat16)
        audio = torch.zeros(1, 125, 128, dtype=torch.bfloat16)
        for seed, steps in [(42, 1), (10042, 7)]:
            a, b = PairedNoise(seed, 64, 28), PairedNoise(seed, 64, 28)
            for _ in range(steps):
                v1, v2 = a(base), b(extended)
                self.assertTrue(torch.equal(v1, v2[:, :64]))
                self.assertEqual(v2[:, 64:].count_nonzero().item(), 0)
                self.assertTrue(torch.equal(a(audio), b(audio)))
            self.assertEqual(a.audit, b.audit)
            self.assertEqual(len(a.target_tensors), steps)

    def test_past_reference_does_not_move_local_or_target_positions(self):
        tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 2, 2), 24)
        raw = tools.create_initial_state("cpu", torch.bfloat16)
        shifted = ShiftTime(97 / 24).apply_to(raw, tools)
        local_latent = torch.ones(1, 128, 7, 2, 2, dtype=torch.bfloat16)
        local = VideoConditionByLatentIndex(local_latent, 1, 0).apply_to(shifted, tools)
        reference = torch.full((1, 128, 10, 2, 2), 2, dtype=torch.bfloat16)
        combined = VideoConditionByKeyframeIndex(reference, frame_idx=0, strength=1, num_pixel_frames=73).apply_to(local, tools)
        self.assertTrue(torch.equal(local.positions, combined.positions[:, :, :64]))
        self.assertTrue(torch.equal(local.clean_latent, combined.clean_latent[:, :64]))
        self.assertEqual(combined.denoise_mask[:, :28].count_nonzero().item(), 0)
        self.assertEqual(combined.denoise_mask[:, 64:].count_nonzero().item(), 0)
        self.assertEqual(combined.denoise_mask.count_nonzero().item(), 36)
        self.assertAlmostEqual(combined.positions[:, 0, 64:].min().item(), 0)
        self.assertAlmostEqual(combined.positions[:, 0, 64:].max().item(), 73 / 24, places=5)
        self.assertAlmostEqual(local.positions[:, 0].min().item(), 97 / 24, places=5)
        self.assertEqual(combined.keyframes_mask.shape[1], 104)
        noised = PairedNoiser(PairedNoise(42, 64, 28))(combined, 1)
        self.assertTrue(torch.equal(noised.latent[:, :28], combined.clean_latent[:, :28]))
        self.assertTrue(torch.equal(noised.latent[:, 64:], combined.clean_latent[:, 64:]))
        self.assertEqual(tools.clear_conditioning(noised).latent.shape[1], 64)

    def test_target_guidance_is_appended_without_replacing_generated_tokens(self):
        tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 2, 2), 24)
        raw = ShiftTime(97 / 24).apply_to(tools.create_initial_state("cpu", torch.bfloat16), tools)
        still = torch.ones(1, 128, 1, 2, 2, dtype=torch.bfloat16)
        state = VideoConditionByKeyframeIndex(still, frame_idx=146, strength=1).apply_to(raw, tools)
        self.assertTrue(torch.equal(state.latent[:, :64], raw.latent))
        self.assertEqual(state.denoise_mask[:, :64].count_nonzero().item(), 64)
        self.assertAlmostEqual(state.positions[:, 0, 64:].min().item(), 146 / 24, places=5)
        self.assertAlmostEqual(state.positions[:, 0, 64:].max().item(), 147 / 24, places=5)


if __name__ == "__main__":
    unittest.main()
