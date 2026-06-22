import json
import unittest

import numpy as np

from utils.scene_evidence import (
    add_pairwise_relations,
    build_predicted_geometry,
    select_point_mask,
)


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


if __name__ == "__main__":
    unittest.main()
