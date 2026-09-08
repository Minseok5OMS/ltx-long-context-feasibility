"""Check variable-length conditioning through the installed pipeline and paired RNG."""

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import unittest
import torch
from ltx_core.components.patchifiers import VideoLatentPatchifier
from ltx_core.conditioning.types.keyframe_cond import VideoConditionByKeyframeIndex
from ltx_core.conditioning.types.latent_cond import VideoConditionByLatentIndex
from ltx_core.tools import VideoLatentTools
from ltx_core.types import VideoLatentShape
from ltx_pipelines.utils.helpers import state_with_conditionings

from reference_controls import PairedNoise, ShiftTime
from repetition_controls import CASES, EXAMPLE, ReferenceTimeLayout, case_path, reference_tensor
from run_generation import ROOT


class RepetitionControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        cls.tensors = torch.load(ROOT / "outputs" / EXAMPLE / "reference_inputs_512x288/inputs.pt",
                                 map_location=cls.device, weights_only=True)
        cls.anchor = torch.load(case_path("N1") / "video_positions.pt", map_location=cls.device, weights_only=True)
        cls.tools = VideoLatentTools(VideoLatentPatchifier(1), VideoLatentShape(1, 128, 16, 9, 16), 24)

    def state_for(self, case):
        ref = reference_tensor(self.tensors, case)
        layout = ReferenceTimeLayout(2304, self.anchor[:, :, 2304:])
        base = self.tools.create_initial_state(self.device, torch.bfloat16)
        conditions = [ShiftTime(97 / 24), VideoConditionByLatentIndex(self.tensors["local"], 1, 0),
                      VideoConditionByKeyframeIndex(ref, frame_idx=0, strength=1,
                                                    num_pixel_frames=(CASES[case]["repeats"] - 1) * 8 + 1), layout]
        return state_with_conditionings(base, conditions, self.tools)

    def test_actual_appended_content_bounds_and_frozen_mask(self):
        for case, spec in CASES.items():
            with self.subTest(case=case, device=self.device):
                state = self.state_for(case)
                expected_tokens = self.tensors["oracle_still"].permute(0, 2, 3, 4, 1).flatten(1, 3).repeat(1, spec["repeats"], 1)
                self.assertTrue(torch.equal(state.clean_latent[:, 2304:], expected_tokens))
                self.assertTrue(torch.equal(state.positions[:, :, 2304:], self.anchor[:, :, 2304:].repeat(1, 1, spec["repeats"], 1)))
                torch.testing.assert_close(state.positions[:, :, :2304], self.anchor[:, :, :2304], rtol=0, atol=1e-6 if self.device == "cpu" else 0)
                self.assertEqual(state.latent.shape[1], 2304 + spec["tokens"])
                self.assertEqual(state.denoise_mask.count_nonzero().item(), 1296)
                self.assertEqual(state.denoise_mask[:, :1008].count_nonzero().item(), 0)
                self.assertEqual(state.denoise_mask[:, 2304:].count_nonzero().item(), 0)

    def test_variable_reference_count_preserves_actual_saved_noise(self):
        saved = [torch.load(case_path("N1") / "target_initial_noise.pt", weights_only=True),
                 *torch.load(case_path("N1") / "target_step_noises.pt", weights_only=True)]
        for case in CASES:
            state = self.state_for(case)
            for seed, count, expected in [(42, 1, saved[:1]), (10042, 7, saved[1:])]:
                noise = PairedNoise(seed, 2304, 1008)
                for i in range(count):
                    video_noise = noise(state.latent)
                    self.assertTrue(torch.equal(video_noise[:, 1008:2304].cpu(), expected[i]))
                    self.assertEqual(video_noise[:, 2304:].count_nonzero().item(), 0)
                    noise(torch.zeros((1, 125, 128), dtype=state.latent.dtype, device=self.device))


if __name__ == "__main__":
    unittest.main()
