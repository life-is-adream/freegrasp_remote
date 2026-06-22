import json
import unittest

import numpy as np

from utils.scene_evidence import (
    add_pairwise_relations,
    build_predicted_geometry,
    evidence_router_prompt,
    format_router_input,
    parse_route_assessment,
    predict_geometry_from_molmo_points,
    select_consistent_mask,
    select_point_mask,
)


class _FakePredictor:
    def __init__(self):
        self.images = []
        self.points = []

    def set_image(self, image):
        self.images.append(np.asarray(image))

    def predict(self, *, point_coords, point_labels, multimask_output):
        point = tuple(int(value) for value in point_coords[0])
        self.points.append(point)
        mask = np.zeros((20, 20), dtype=bool)
        x, y = point
        mask[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = True
        return np.stack([np.ones((20, 20), dtype=bool), mask]), np.array([0.9, 0.8]), None


class SceneEvidenceTest(unittest.TestCase):
    def test_select_point_mask_prefers_small_consistent_candidate(self):
        large = np.ones((10, 10), dtype=bool)
        small = np.zeros((10, 10), dtype=bool)
        small[3:7, 3:7] = True

        result = select_point_mask([large, small], [0.95, 0.80], (5, 5))

        self.assertEqual(result.index, 1)
        self.assertTrue(result.contains_point)

    def test_build_predicted_geometry_never_copies_gt_id(self):
        parsed = [(7, 5, 5, 999)]
        mask = np.zeros((10, 10), dtype=bool)
        mask[2:8, 2:8] = True

        evidence = build_predicted_geometry(parsed, {7: mask})

        self.assertNotIn("gt_id", json.dumps(evidence))
        self.assertEqual(evidence["candidates"][7]["bbox"], (2, 2, 7, 7))

    def test_pairwise_relations_require_overlap_for_overlap_evidence(self):
        evidence = {
            "source": "predicted_sam_point_masks",
            "candidates": {
                1: {"bbox": (0, 0, 5, 5), "center": (2, 2), "area": 36},
                2: {"bbox": (3, 3, 8, 8), "center": (5, 5), "area": 36},
                3: {"bbox": (9, 0, 12, 3), "center": (10, 1), "area": 16},
            },
            "relations": [],
        }

        related = add_pairwise_relations(evidence)

        by_pair = {
            (item["source_id"], item["target_id"]): item
            for item in related["relations"]
        }
        self.assertEqual(by_pair[(1, 2)]["relation"], "overlaps")
        self.assertGreater(by_pair[(1, 2)]["overlap"], 0)
        self.assertEqual(by_pair[(1, 3)]["relation"], "near")
        self.assertEqual(by_pair[(1, 3)]["overlap"], 0)

    def test_predict_geometry_uses_only_molmo_points(self):
        predictor = _FakePredictor()

        evidence = predict_geometry_from_molmo_points(
            image=np.zeros((20, 20, 3), dtype=np.uint8),
            parsed_data=[(3, 4, 5, 900), (8, 10, 11, 901)],
            predictor=predictor,
        )

        self.assertEqual(len(predictor.images), 1)
        self.assertEqual(predictor.points, [(4, 5), (10, 11)])
        self.assertEqual(evidence["source"], "predicted_sam_point_masks")
        self.assertNotIn("900", json.dumps(evidence))
        self.assertNotIn("901", json.dumps(evidence))

    def test_evidence_router_prompt_has_bounded_schema(self):
        prompt = evidence_router_prompt()

        self.assertIn('"route_mode"', prompt)
        self.assertIn('"route_confidence"', prompt)
        self.assertIn('"target_object_id"', prompt)
        self.assertIn('"ambiguity_evidence"', prompt)
        self.assertIn('"blocker_evidence"', prompt)
        self.assertIn("near alone", prompt)

    def test_parse_route_assessment_rejects_unknown_mode(self):
        output = json.dumps(
            {
                "route_mode": "hard",
                "route_confidence": 0.9,
                "target_object_id": 3,
            }
        )

        with self.assertRaisesRegex(ValueError, "Unknown route mode"):
            parse_route_assessment(output, [3, 4])

    def test_router_input_uses_predicted_evidence_without_gt_fields(self):
        evidence = {
            "source": "predicted_sam_point_masks",
            "candidates": {
                3: {"point": (4, 5), "bbox": (2, 3, 6, 7), "area": 25},
            },
            "relations": [],
        }

        text = format_router_input(
            instruction="Grasp the red block",
            parsed_data=[(3, 4, 5, 999)],
            predicted_geometry=evidence,
        )

        self.assertIn("visible_object_count=1", text)
        self.assertIn("source=predicted_sam_point_masks", text)
        self.assertNotIn("999", text)
        self.assertNotIn("GT_ID", text)

    def test_consistent_mask_beats_higher_confidence_wrong_instance(self):
        wrong = np.zeros((8, 8), dtype=bool)
        wrong[:3, :3] = True
        right = np.zeros((8, 8), dtype=bool)
        right[3:7, 3:7] = True

        selected = select_consistent_mask(
            masks=[wrong, right],
            confidences=[0.99, 0.70],
            point=(5, 5),
        )

        self.assertEqual(selected.index, 1)
        self.assertIsNone(selected.fallback_reason)

    def test_nearest_mask_fallback_is_explicit(self):
        left = np.zeros((8, 8), dtype=bool)
        left[1:3, 1:3] = True
        right = np.zeros((8, 8), dtype=bool)
        right[5:7, 5:7] = True

        selected = select_consistent_mask(
            masks=[left, right],
            confidences=[0.5, 0.5],
            point=(4, 4),
        )

        self.assertFalse(selected.contains_point)
        self.assertEqual(selected.index, 1)
        self.assertEqual(
            selected.fallback_reason,
            "no_candidate_contains_point",
        )


if __name__ == "__main__":
    unittest.main()
