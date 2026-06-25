"""Tests for EGHC evidence builder."""

import unittest

from utils.deployable_evidence import build_evidence_packet


class EvidenceBuilderTest(unittest.TestCase):
    def test_builds_packet_from_sanitized_bundle(self):
        bundle = {
            "scene_id": 42,
            "query_target_id": 3,
            "visible_points": [
                {"object_id": 3, "x": 100, "y": 200},
                {"object_id": 5, "x": 300, "y": 400},
            ],
            "depth_path": "scene42_depth.npy",
            "predicted_masks": [{"object_id": 3, "mask_path": "mask_3.npy"}],
        }
        packet = build_evidence_packet(bundle)
        self.assertEqual(packet["scene_id"], 42)
        self.assertEqual(packet["query_target_id"], 3)
        self.assertEqual(packet["visible_ids"], [3, 5])
        self.assertTrue(packet["depth_available"])
        self.assertEqual(len(packet["mask_candidates"]), 1)

    def test_forbidden_gt_key_in_bundle_raises(self):
        bundle = {
            "scene_id": 1,
            "query_target_id": 1,
            "visible_points": [],
            "difficulty": "Easy",  # forbidden!
        }
        with self.assertRaisesRegex(RuntimeError, "difficulty"):
            build_evidence_packet(bundle)


if __name__ == "__main__":
    unittest.main()
