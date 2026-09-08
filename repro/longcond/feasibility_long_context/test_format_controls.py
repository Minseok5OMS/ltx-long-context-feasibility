"""Verify the actual cached content, duplicate ordering and A/E coordinate templates."""

import unittest

import torch
from ltx_core.components.patchifiers import VideoLatentPatchifier
from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
from ltx_core.tools import VideoLatentTools
from ltx_core.types import VideoLatentShape
from ltx_pipelines.utils.helpers import state_with_conditionings

from format_controls import EXAMPLE, ReferenceTimeLayout, case_path, reference_tensor
from reference_controls import ShiftTime
from run_generation import ROOT


class FormatControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        cls.tensors = torch.load(ROOT / "outputs" / EXAMPLE / "reference_inputs_512x288/inputs.pt",
                                 map_location=cls.device, weights_only=True)
        cls.anchors = {case: torch.load(case_path(case) / "video_positions.pt", map_location=cls.device, weights_only=True)
                       for case in ("A", "E")}

    def test_repetition_preserves_each_spatial_block_and_video_is_untouched(self):
        repeated = reference_tensor(self.tensors, "B")
        self.assertTrue(torch.equal(repeated, reference_tensor(self.tensors, "C")))
        self.assertEqual(tuple(repeated.shape), (1, 128, 10, 9, 16))
        for frame in range(10):
            self.assertTrue(torch.equal(repeated[:, :, frame:frame+1], self.tensors["oracle_still"]))
        self.assertIs(reference_tensor(self.tensors, "D"), self.tensors["oracle"])

    def test_same_and_spread_time_are_exact_and_leave_all_other_state_unchanged(self):
        tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 9, 16), 24)
        base = ShiftTime(97 / 24).apply_to(tools.create_initial_state(self.device, torch.bfloat16), tools)
        base = VideoConditionByLatentIndex(self.tensors["local"], 1, 0).apply_to(base, tools)
        results = {}
        for case, anchor in [("B", "A"), ("C", "E"), ("D", "A")]:
            ref = reference_tensor(self.tensors, case)
            before = VideoConditionByKeyframeIndex(ref, frame_idx=0, strength=1, num_pixel_frames=73).apply_to(base, tools)
            layout = ReferenceTimeLayout(2304, self.anchors[anchor][:, :, 2304:])
            after = state_with_conditionings(before, [layout], tools)
            self.assertIs(after.latent, before.latent)
            self.assertIs(after.clean_latent, before.clean_latent)
            self.assertIs(after.denoise_mask, before.denoise_mask)
            self.assertIs(after.attention_mask, before.attention_mask)
            self.assertTrue(torch.equal(after.positions[:, :, :2304], base.positions))
            self.assertEqual(after.denoise_mask.count_nonzero().item(), 1296)
            self.assertEqual(after.denoise_mask[:, 2304:].count_nonzero().item(), 0)
            results[case] = after
        self.assertTrue(torch.equal(results["B"].positions, results["D"].positions))
        self.assertTrue(torch.equal(results["C"].positions[:, :, 2304:], self.anchors["E"][:, :, 2304:]))
        self.assertTrue(torch.equal(results["B"].clean_latent, results["C"].clean_latent))
        self.assertTrue(torch.equal(results["B"].positions[:, :, 2304:], self.anchors["A"][:, :, 2304:].repeat(1, 1, 10, 1)))
        if self.device != "cpu":
            self.assertTrue(torch.equal(results["C"].positions, self.anchors["E"]))


if __name__ == "__main__":
    unittest.main()
