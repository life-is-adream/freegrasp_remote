import json
import unittest

import numpy as np
import utils.scene_evidence as scene_evidence
from utils.scene_evidence import (
    add_pairwise_relations,
    apply_conservative_route_guard,
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
    @staticmethod
    def _canonical_geometry(target_id=1, candidate_ids=(2,)):
        candidates = {
            target_id: {
                "point": (0, 0),
                "bbox": (0, 0, 2, 2),
                "center": (1, 1),
                "area": 9,
            }
        }
        relations = []
        for offset, candidate_id in enumerate(candidate_ids, start=1):
            candidates[candidate_id] = {
                "point": (4 * offset, 0),
                "bbox": (4 * offset, 0, 4 * offset + 2, 2),
                "center": (4 * offset + 1, 1),
                "area": 9,
            }
            relations.append(
                {
                    "object_a_id": target_id,
                    "object_b_id": candidate_id,
                    "relation": "separate",
                    "bbox_overlap_smaller": 0.0,
                    "bbox_a_coverage": 0.0,
                    "bbox_b_coverage": 0.0,
                    "mask_iou": 0.0,
                    "a_contains_b_point": False,
                    "b_contains_a_point": False,
                    "a_image_position_from_b": "level_left",
                    "b_image_position_from_a": "level_right",
                    "duplicate_mask_suspect": False,
                }
            )
        return {
            "source": "predicted_sam_point_masks",
            "candidates": candidates,
            "relations": relations,
        }

    @staticmethod
    def _assessment(mode="direct", **updates):
        value = {
            "route_mode": mode,
            "route_confidence": 0.95,
            "target_object_id": 3,
            "target_label": "red block",
            "ambiguity_evidence": [],
            "blocker_evidence": [],
        }
        value.update(updates)
        return value

    def test_conservative_guard_keeps_safe_direct(self):
        guarded = apply_conservative_route_guard(
            self._assessment(),
            visible_object_ids=[3, 4, 5],
            object_count=3,
            predicted_geometry={"candidates": {}, "relations": []},
        )
        self.assertEqual(guarded["route_mode"], "direct")
        self.assertFalse(guarded["route_guard_applied"])

    def test_conservative_guard_downgrades_risky_direct(self):
        cases = [
            (self._assessment(route_confidence=0.89), 3, {}, "low_confidence"),
            (self._assessment(target_object_id=9), 3, {}, "invalid_target_id"),
            (self._assessment(ambiguity_evidence=["same class"]), 3, {}, "ambiguity_present"),
            (
                self._assessment(),
                3,
                {
                    "relations": [
                        {
                            "source_id": 3,
                            "target_id": 4,
                            "relation": "overlaps",
                            "overlap": 0.2,
                        }
                    ]
                },
                "predicted_target_overlap",
            ),
        ]
        for assessment, count, geometry, reason in cases:
            with self.subTest(reason=reason):
                guarded = apply_conservative_route_guard(
                    assessment,
                    visible_object_ids=[3, 4, 5],
                    object_count=count,
                    predicted_geometry=geometry,
                )
                self.assertEqual(guarded["route_mode"], "target_first")
                self.assertIn(reason, guarded["route_guard_reasons"])

    def test_conservative_guard_validates_blocker_first(self):
        near = apply_conservative_route_guard(
            self._assessment("blocker_first", blocker_evidence=["near object 4"]),
            visible_object_ids=[3, 4],
            object_count=2,
            predicted_geometry={"relations": []},
        )
        overlap = apply_conservative_route_guard(
            self._assessment(
                "blocker_first",
                blocker_evidence=["physical overlap with object 4"],
            ),
            visible_object_ids=[3, 4],
            object_count=2,
            predicted_geometry={"relations": []},
        )
        target_first = apply_conservative_route_guard(
            self._assessment("target_first"),
            visible_object_ids=[3, 4],
            object_count=2,
            predicted_geometry={"relations": []},
        )
        self.assertEqual(near["route_mode"], "target_first")
        self.assertEqual(overlap["route_mode"], "blocker_first")
        self.assertEqual(target_first["route_mode"], "target_first")

    def test_conservative_guard_rejects_gt_fields(self):
        with self.assertRaisesRegex(ValueError, "ground-truth"):
            apply_conservative_route_guard(
                self._assessment(),
                visible_object_ids=[3],
                object_count=1,
                predicted_geometry={"candidates": {3: {"gt_id": 9}}},
            )

    def test_target_evidence_guard_downgrades_duplicate_and_risky_direct(self):
        guard = getattr(
            scene_evidence,
            "apply_target_evidence_route_guard",
            None,
        )
        self.assertTrue(callable(guard))
        duplicate = {
            "target_valid": True,
            "risk_candidates": [],
            "duplicate_mask_candidates": [4],
            "evidence_reliability": "duplicate_only",
        }
        risk = {
            "target_valid": True,
            "risk_candidates": [{"candidate_id": 4}],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "usable",
        }
        for packet, reason in [
            (duplicate, "duplicate_mask_uncertainty"),
            (risk, "target_risk_present"),
        ]:
            with self.subTest(reason=reason):
                guarded = guard(
                    self._assessment(),
                    visible_object_ids=[3, 4],
                    object_count=2,
                    target_evidence_packet=packet,
                )
                self.assertEqual(guarded["route_mode"], "target_first")
                self.assertIn(reason, guarded["route_guard_reasons"])

    def test_target_evidence_guard_requires_text_and_nonduplicate_candidate(self):
        guard = getattr(
            scene_evidence,
            "apply_target_evidence_route_guard",
            None,
        )
        self.assertTrue(callable(guard))
        packet = {
            "target_valid": True,
            "risk_candidates": [{"candidate_id": 4}],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "usable",
        }
        supported = guard(
            self._assessment(
                "blocker_first",
                blocker_evidence=["object 4 physically covers the target"],
            ),
            visible_object_ids=[3, 4],
            object_count=2,
            target_evidence_packet=packet,
        )
        unsupported = guard(
            self._assessment(
                "blocker_first",
                blocker_evidence=["near object 4"],
            ),
            visible_object_ids=[3, 4],
            object_count=2,
            target_evidence_packet=packet,
        )
        self.assertEqual(supported["route_mode"], "blocker_first")
        self.assertEqual(unsupported["route_mode"], "target_first")

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

    def test_pairwise_relations_are_canonical_and_order_independent(self):
        masks = {
            1: np.pad(np.ones((5, 5), dtype=bool), ((0, 5), (0, 5))),
            2: np.pad(np.ones((5, 5), dtype=bool), ((3, 2), (3, 2))),
        }
        parsed = [(1, 1, 1, 900), (2, 7, 7, 901)]

        first = build_predicted_geometry(parsed, masks)
        second = build_predicted_geometry(list(reversed(parsed)), masks)

        self.assertEqual(first["relations"], second["relations"])
        self.assertEqual(len(first["relations"]), 1)
        relation = first["relations"][0]
        self.assertEqual(
            (relation["object_a_id"], relation["object_b_id"]),
            (1, 2),
        )
        self.assertIn("bbox_overlap_smaller", relation)
        self.assertIn("mask_iou", relation)
        self.assertNotIn("vertical_order", relation)

    def test_depth_relation_marks_front_contact_blocker(self):
        target = np.zeros((12, 12), dtype=bool)
        target[2:8, 2:8] = True
        blocker = np.zeros((12, 12), dtype=bool)
        blocker[5:10, 5:10] = True
        depth = np.full((12, 12), 100.0)
        depth[target] = 120.0
        depth[blocker] = 70.0

        geometry = build_predicted_geometry(
            [(3, 4, 4, 900), (4, 6, 6, 901)],
            {3: target, 4: blocker},
            depth_map=depth,
        )
        relation = geometry["relations"][0]

        self.assertEqual(geometry["depth_source"], "depth_map")
        self.assertEqual(relation["depth_order"], "b_in_front")
        self.assertEqual(relation["depth_front_object_id"], 4)
        self.assertTrue(relation["depth_occlusion_suspect"])

    def test_target_packet_prioritizes_depth_occlusion_without_gt(self):
        target = np.zeros((16, 16), dtype=bool)
        target[2:8, 2:8] = True
        front = np.zeros((16, 16), dtype=bool)
        front[5:10, 5:10] = True
        nearby = np.zeros((16, 16), dtype=bool)
        nearby[10:14, 10:14] = True
        depth = np.full((16, 16), 100.0)
        depth[target] = 130.0
        depth[front] = 60.0
        depth[nearby] = 140.0
        geometry = build_predicted_geometry(
            [(3, 4, 4, 900), (4, 6, 6, 901), (5, 11, 11, 902)],
            {3: target, 4: front, 5: nearby},
            depth_map=depth,
        )

        packet = scene_evidence.build_target_evidence_packet(
            target_id=3,
            visible_object_ids=[3, 4, 5],
            predicted_geometry=geometry,
            max_candidates=3,
        )

        self.assertEqual(packet["risk_candidates"][0]["candidate_id"], 4)
        self.assertEqual(
            packet["risk_candidates"][0]["included_by"],
            "depth_occlusion",
        )
        self.assertEqual(
            packet["risk_candidates"][0]["candidate_depth_order"],
            "candidate_in_front",
        )
        self.assertNotIn("900", json.dumps(packet))

    def test_duplicate_mask_suspect_requires_mask_or_cross_point_evidence(self):
        same = np.zeros((12, 12), dtype=bool)
        same[2:10, 2:10] = True
        distinct = np.zeros((12, 12), dtype=bool)
        distinct[7:11, 7:11] = True

        duplicate_geometry = build_predicted_geometry(
            [(1, 4, 4, 900), (2, 8, 8, 901)],
            {1: same, 2: same.copy()},
        )
        separate_geometry = build_predicted_geometry(
            [(1, 4, 4, 900), (2, 8, 8, 901)],
            {1: same, 2: distinct},
        )
        self.assertEqual(len(duplicate_geometry["relations"]), 1)
        self.assertEqual(len(separate_geometry["relations"]), 1)
        duplicate = duplicate_geometry["relations"][0]
        separate = separate_geometry["relations"][0]

        self.assertTrue(duplicate["duplicate_mask_suspect"])
        self.assertGreaterEqual(
            duplicate["mask_iou"],
            0.85,
        )
        self.assertFalse(separate["duplicate_mask_suspect"])

    def test_target_packet_ranks_non_duplicate_risk_candidates(self):
        geometry = {
            "source": "predicted_sam_point_masks",
            "candidates": {
                3: {
                    "point": (5, 5),
                    "bbox": (2, 2, 8, 8),
                    "center": (5, 5),
                    "area": 49,
                },
                4: {
                    "point": (6, 4),
                    "bbox": (3, 1, 7, 6),
                    "center": (5, 3),
                    "area": 30,
                },
                5: {
                    "point": (9, 9),
                    "bbox": (8, 8, 10, 10),
                    "center": (9, 9),
                    "area": 9,
                },
            },
            "relations": [
                {
                    "object_a_id": 3,
                    "object_b_id": 4,
                    "relation": "overlaps",
                    "bbox_overlap_smaller": 0.8,
                    "bbox_a_coverage": 0.4,
                    "bbox_b_coverage": 0.8,
                    "mask_iou": 0.2,
                    "a_contains_b_point": True,
                    "b_contains_a_point": True,
                    "a_image_position_from_b": "lower_center",
                    "b_image_position_from_a": "upper_center",
                    "duplicate_mask_suspect": False,
                },
                {
                    "object_a_id": 3,
                    "object_b_id": 5,
                    "relation": "overlaps",
                    "bbox_overlap_smaller": 1.0,
                    "bbox_a_coverage": 0.1,
                    "bbox_b_coverage": 1.0,
                    "mask_iou": 0.9,
                    "a_contains_b_point": True,
                    "b_contains_a_point": True,
                    "a_image_position_from_b": "upper_left",
                    "b_image_position_from_a": "lower_right",
                    "duplicate_mask_suspect": True,
                },
            ],
        }
        builder = getattr(
            scene_evidence,
            "build_target_evidence_packet",
            None,
        )
        self.assertTrue(callable(builder))

        packet = builder(
            target_id=3,
            visible_object_ids=[3, 4, 5],
            predicted_geometry=geometry,
            max_candidates=3,
        )

        self.assertEqual(
            [row["candidate_id"] for row in packet["risk_candidates"]],
            [4],
        )
        self.assertEqual(packet["duplicate_mask_candidates"], [5])
        self.assertEqual(
            packet["risk_candidates"][0]["candidate_image_position"],
            "upper_center",
        )
        self.assertEqual(packet["evidence_reliability"], "usable")

    def test_target_packet_uses_labeled_nearest_fallback_and_rejects_gt(self):
        builder = getattr(
            scene_evidence,
            "build_target_evidence_packet",
            None,
        )
        self.assertTrue(callable(builder))
        geometry = self._canonical_geometry(target_id=1, candidate_ids=(2,))

        packet = builder(
            target_id=1,
            visible_object_ids=[1, 2],
            predicted_geometry=geometry,
        )
        self.assertEqual(
            packet["risk_candidates"][0]["included_by"],
            "nearest_fallback",
        )

        with self.assertRaisesRegex(ValueError, "ground-truth"):
            builder(
                target_id=1,
                visible_object_ids=[1],
                predicted_geometry={"gt_id": 4},
            )

    def test_target_packet_rejects_duplicate_pairs_and_nonfinite_values(self):
        builder = getattr(
            scene_evidence,
            "build_target_evidence_packet",
            None,
        )
        self.assertTrue(callable(builder))
        geometry = self._canonical_geometry(target_id=1, candidate_ids=(2,))
        duplicate = {
            **geometry,
            "relations": geometry["relations"] * 2,
        }
        with self.assertRaisesRegex(ValueError, "Duplicate canonical pair"):
            builder(
                target_id=1,
                visible_object_ids=[1, 2],
                predicted_geometry=duplicate,
            )

        geometry["relations"][0]["mask_iou"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            builder(
                target_id=1,
                visible_object_ids=[1, 2],
                predicted_geometry=geometry,
            )

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
