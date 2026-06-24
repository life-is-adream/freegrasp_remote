import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np


def canonical_geometry(target_id=3, candidate_id=4):
    return {
        "source": "predicted_sam_point_masks",
        "candidates": {
            target_id: {
                "point": (1, 1),
                "bbox": (0, 0, 4, 4),
                "center": (2, 2),
                "area": 25,
            },
            candidate_id: {
                "point": (3, 3),
                "bbox": (2, 2, 6, 6),
                "center": (4, 4),
                "area": 25,
            },
        },
        "relations": [
            {
                "object_a_id": target_id,
                "object_b_id": candidate_id,
                "relation": "overlaps",
                "bbox_overlap_smaller": 9 / 25,
                "bbox_a_coverage": 9 / 25,
                "bbox_b_coverage": 9 / 25,
                "mask_iou": 0.1,
                "a_contains_b_point": True,
                "b_contains_a_point": True,
                "a_image_position_from_b": "upper_left",
                "b_image_position_from_a": "lower_right",
                "duplicate_mask_suspect": False,
            }
        ],
    }


def make_gate_rows():
    rows = []
    for index in range(25):
        is_hard = index < 8
        recalled = index < 4 or 8 <= index < 21
        rows.append(
            {
                "sample_key": [
                    "0",
                    "hard_no_ambi" if is_hard else "medium_no_ambi",
                    index,
                    1000 + index,
                    1,
                    "sample",
                ],
                "subset": (
                    "hard_no_ambi" if is_hard else "medium_no_ambi"
                ),
                "evaluation_only": {
                    "target_correct": index < 24,
                    "top3_recall": recalled,
                },
            }
        )
    return rows


class TargetEvidenceAuditTest(unittest.TestCase):
    def _audit(self):
        spec = importlib.util.find_spec("audit_target_evidence_v2")
        self.assertIsNotNone(spec)
        return importlib.import_module("audit_target_evidence_v2")

    def test_audit_builds_packet_before_using_evaluation_mapping(self):
        audit = self._audit()
        sample = {
            "split": "0",
            "subset": "hard_no_ambi",
            "source_row_index": 0,
            "scene_id": 7,
            "object_id": 2,
            "annotation": "the box",
            "frozen_route_assessment": {"target_object_id": 3},
        }
        detail = {"gt_ids": [5], "rsr_correct": 0, "ssr_correct": 0}

        row = audit.audit_pilot_sample(
            sample,
            detail,
            canonical_geometry(),
            molmo_to_gt={3: 2, 4: 5},
        )

        self.assertTrue(row["evaluation_only"]["target_correct"])
        self.assertTrue(row["evaluation_only"]["top3_recall"])
        self.assertNotIn("gt_ids", json.dumps(row["packet"]))

    def test_gate_requires_exact_counts_and_hard_recall(self):
        audit = self._audit()
        rows = make_gate_rows()

        self.assertTrue(audit.evaluate_gate(rows)["passed"])
        recalled_medium = next(
            row
            for row in rows
            if row["subset"].startswith("medium_")
            and row["evaluation_only"]["top3_recall"]
        )
        recalled_medium["evaluation_only"]["top3_recall"] = False
        self.assertFalse(audit.evaluate_gate(rows)["passed"])

    def test_geometry_cache_runs_once_per_scene(self):
        audit = self._audit()
        calls = []

        cache = audit.build_geometry_cache(
            scene_ids=[7, 7, 8],
            geometry_provider=lambda scene_id: (
                calls.append(scene_id) or {"scene": scene_id}
            ),
        )

        self.assertEqual(calls, [7, 8])
        self.assertEqual(set(cache), {7, 8})

    def test_load_depth_map_ignores_occlusion_labels(self):
        audit = self._audit()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "7.npz"
            np.savez_compressed(
                path,
                depth=np.ones((3, 3), dtype=np.float32),
                occlusion=np.full((3, 3), 9, dtype=np.uint8),
            )

            depth = audit._load_depth_map(tmpdir, 7)

        self.assertEqual(depth.shape, (3, 3))
        self.assertTrue(np.all(depth == 1.0))


if __name__ == "__main__":
    unittest.main()
