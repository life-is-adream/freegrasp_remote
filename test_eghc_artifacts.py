"""Tests for EGHC sealed artifacts."""

import unittest

from utils.eghc_artifacts import seal_prediction, build_scorer_payload


class EGHCArtifactsTest(unittest.TestCase):
    def test_sealed_prediction_keeps_sample_identity(self):
        sealed = seal_prediction(
            sample_key={"scene_id": 12, "query_target_id": 3, "annotation": "red cup"},
            reasoning={"selected_object_id": 5},
            mask_path="mask.npy",
        )
        self.assertEqual(sealed["sample_key"]["scene_id"], 12)
        self.assertEqual(sealed["reasoning"]["selected_object_id"], 5)
        self.assertEqual(sealed["mask_path"], "mask.npy")

    def test_build_scorer_payload(self):
        sealed = seal_prediction(
            sample_key={"scene_id": 1},
            reasoning={"selected_object_id": 3},
            mask_path="pred.npy",
        )
        payload = build_scorer_payload(sealed, gt_mask_path="gt.npy")
        self.assertEqual(payload["predicted_mask_path"], "pred.npy")
        self.assertEqual(payload["gt_mask_path"], "gt.npy")


if __name__ == "__main__":
    unittest.main()
