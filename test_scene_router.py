"""Tests for scene complexity router."""

import os
import sys
import unittest

import numpy as np

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.scene_router import (
    SceneComplexityFeatures,
    compute_scene_features,
    route_scene,
    route_scene_vlm,
    vlm_scene_complexity_prompt,
    parse_vlm_route,
    needs_vlm_fallback,
    SCENE_ROUTER_VERSION,
)


def _make_parsed_data(points):
    """Helper: list of (molmo_id, x, y, gt_id) tuples.

    molmo_id must be integer string for bbox sorting.
    """
    return [(str(i), x, y, f"gt{i}") for i, (x, y) in enumerate(points)]


class TestSceneRouterVersion(unittest.TestCase):
    def test_version_string(self):
        self.assertIn("v4", SCENE_ROUTER_VERSION)


class TestComputeSceneFeatures(unittest.TestCase):
    def test_single_object(self):
        parsed = _make_parsed_data([(100, 100)])
        features = compute_scene_features(parsed)
        self.assertEqual(features.object_count, 1)
        self.assertEqual(features.route_mode, "direct")
        self.assertFalse(features.depth_available)

    def test_two_objects_spread(self):
        parsed = _make_parsed_data([(50, 50), (350, 350)])
        features = compute_scene_features(parsed, image_shape=(400, 400))
        self.assertEqual(features.object_count, 2)
        self.assertGreater(features.spatial_extent, 0.5)

    def test_many_objects_clustered(self):
        parsed = _make_parsed_data([(100, 100), (110, 105), (105, 110), (115, 95)])
        features = compute_scene_features(parsed, image_shape=(400, 400))
        self.assertEqual(features.object_count, 4)
        self.assertLess(features.nn_cluster_ratio, 0.10)

    def test_high_count_triggers_blocker_first(self):
        points = [(i * 20, i * 20) for i in range(12)]
        parsed = _make_parsed_data(points)
        features = compute_scene_features(parsed, image_shape=(400, 400))
        self.assertGreaterEqual(features.object_count, 9)
        self.assertIn(features.route_mode, ("target_first", "blocker_first"))

    def test_depth_map_hook(self):
        parsed = _make_parsed_data([(50, 50), (150, 150), (250, 250)])
        depth_map = np.array([[1.0 + i * 0.1 for i in range(400)] for _ in range(400)])
        features = compute_scene_features(parsed, image_shape=(400, 400), depth_map=depth_map)
        self.assertTrue(features.depth_available)
        self.assertGreater(features.depth_occlusion_score, 0.0)

    def test_no_depth_map(self):
        parsed = _make_parsed_data([(50, 50), (150, 150)])
        features = compute_scene_features(parsed, image_shape=(400, 400))
        self.assertFalse(features.depth_available)
        self.assertEqual(features.depth_occlusion_score, 0.0)


class TestRouteScene(unittest.TestCase):
    def test_returns_route_assessment(self):
        parsed = _make_parsed_data([(100, 100), (200, 200)])
        assessment = route_scene(parsed, image_shape=(400, 400))
        self.assertIn("route_mode", assessment)
        self.assertIn("route_confidence", assessment)
        self.assertEqual(assessment["route_confidence"], 1.0)
        self.assertIn("scene_complexity", assessment)
        self.assertIn("scene_router_version", assessment)

    def test_route_mode_in_scene_complexity(self):
        parsed = _make_parsed_data([(100, 100)])
        assessment = route_scene(parsed)
        self.assertIn("route_mode", assessment["scene_complexity"])

    def test_depth_fields_in_output(self):
        parsed = _make_parsed_data([(50, 50), (150, 150)])
        depth_map = np.ones((400, 400)) * 2.0
        assessment = route_scene(parsed, image_shape=(400, 400), depth_map=depth_map)
        sc = assessment["scene_complexity"]
        self.assertIn("depth_available", sc)
        self.assertIn("depth_occlusion_score", sc)


class TestSceneComplexityFeatures(unittest.TestCase):
    def test_dataclass_fields(self):
        features = SceneComplexityFeatures(
            object_count=5,
            median_nn_dist=10.0,
            nn_cluster_ratio=0.05,
            spatial_extent=0.3,
            density_score=1.0,
            cluster_score=1.5,
            extent_score=0.5,
            composite_score=1.0,
            route_mode="target_first",
        )
        self.assertEqual(features.object_count, 5)
        self.assertEqual(features.depth_occlusion_score, 0.0)
        self.assertFalse(features.depth_available)


class TestVLMRouter(unittest.TestCase):
    def test_vlm_prompt_returns_string(self):
        prompt = vlm_scene_complexity_prompt()
        self.assertIn("occlusion", prompt.lower())
        self.assertIn("JSON", prompt)

    def test_parse_vlm_route_heavy(self):
        vlm_output = '{"occlusion_level": "heavy", "confidence": 0.9, "reason": "objects hidden"}'
        result = parse_vlm_route(vlm_output)
        self.assertEqual(result["route_mode"], "blocker_first")
        self.assertEqual(result["occlusion_level"], "heavy")
        self.assertAlmostEqual(result["confidence"], 0.9)

    def test_parse_vlm_route_light(self):
        vlm_output = '{"occlusion_level": "light", "confidence": 0.7, "reason": "partial overlap"}'
        result = parse_vlm_route(vlm_output)
        self.assertEqual(result["route_mode"], "target_first")
        self.assertEqual(result["occlusion_level"], "light")

    def test_parse_vlm_route_none(self):
        vlm_output = '{"occlusion_level": "none", "confidence": 0.8, "reason": "all visible"}'
        result = parse_vlm_route(vlm_output)
        self.assertEqual(result["route_mode"], "direct")
        self.assertEqual(result["occlusion_level"], "none")

    def test_parse_vlm_route_markdown_block(self):
        vlm_output = '```json\n{"occlusion_level": "heavy", "confidence": 0.85}\n```'
        result = parse_vlm_route(vlm_output)
        self.assertEqual(result["route_mode"], "blocker_first")

    def test_parse_vlm_route_fallback_keyword(self):
        vlm_output = "The scene has significant occlusion with objects hidden behind others."
        result = parse_vlm_route(vlm_output)
        self.assertEqual(result["route_mode"], "blocker_first")

    def test_needs_vlm_fallback(self):
        self.assertFalse(needs_vlm_fallback(0.3))   # confident direct
        self.assertTrue(needs_vlm_fallback(0.8))    # uncertain
        self.assertTrue(needs_vlm_fallback(1.2))    # uncertain
        self.assertFalse(needs_vlm_fallback(1.8))   # confident blocker_first

    def test_route_scene_vlm_without_vlm(self):
        parsed = _make_parsed_data([(100, 100), (200, 200)])
        assessment = route_scene_vlm(parsed, image_shape=(400, 400))
        self.assertIn("vlm_stage", assessment)
        self.assertIn("route_mode", assessment)

    def test_route_scene_vlm_with_vlm_override(self):
        parsed = _make_parsed_data([(100, 100), (150, 150), (200, 200)])
        vlm_output = '{"occlusion_level": "heavy", "confidence": 0.9, "reason": "test"}'
        assessment = route_scene_vlm(
            parsed, image_shape=(400, 400), vlm_output=vlm_output
        )
        # If VLM was needed and used, route should be overridden
        vlm_stage = assessment["vlm_stage"]
        if vlm_stage["needed"] and vlm_stage["used"]:
            self.assertEqual(assessment["route_mode"], "blocker_first")


if __name__ == "__main__":
    unittest.main()
