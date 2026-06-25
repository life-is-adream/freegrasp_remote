"""Tests for EGHC GT isolation."""

import unittest

from utils.gt_access_guard import assert_payload_has_no_forbidden_gt_keys


class GTIsolationTest(unittest.TestCase):
    def test_forbidden_gt_key_raises(self):
        with self.assertRaisesRegex(RuntimeError, "instances_objects"):
            assert_payload_has_no_forbidden_gt_keys({"instances_objects": "forbidden"})

    def test_sanitized_bundle_allows_depth_and_intrinsics(self):
        payload = {
            "rgb_path": "scene1.png",
            "depth_path": "scene1_depth.npy",
            "camera_intrinsics": [1.0] * 9,
            "visible_points": [{"object_id": 3, "x": 10, "y": 12}],
        }
        assert_payload_has_no_forbidden_gt_keys(payload)

    def test_nested_forbidden_key_raises(self):
        payload = {"outer": {"inner": {"difficulty": "Easy"}}}
        with self.assertRaisesRegex(RuntimeError, "difficulty"):
            assert_payload_has_no_forbidden_gt_keys(payload)


if __name__ == "__main__":
    unittest.main()
