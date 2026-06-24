import importlib
import sys
import unittest
from unittest.mock import patch

import numpy as np

import test_utils_output_limit as support


class SegmentationConsistencyIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support._install_import_stubs()
        sys.modules.pop("utils.utils", None)
        cls.utils = importlib.import_module("utils.utils")

    def test_geometric_consistency_compares_all_queries(self):
        wrong = np.zeros((8, 8), dtype=np.uint8)
        wrong[:3, :3] = 1
        right = np.zeros((8, 8), dtype=np.uint8)
        right[3:7, 3:7] = 1
        outputs = [
            ([wrong], [support._FakeBox()], ["wrong"], [0.99]),
            ([right], [support._FakeBox()], ["right"], [0.70]),
        ]

        with patch.object(
            self.utils.langsam_actor,
            "predict",
            side_effect=outputs,
        ):
            mask, _bbox, metadata = self.utils._predict_langsam_mask(
                image_pil=object(),
                query_candidates=["wrong query", "right query"],
                goal_coor=(5, 5),
                segmentation_variant="geometric_consistency",
            )

        np.testing.assert_array_equal(mask, right)
        self.assertEqual(metadata["langsam_selected_query"], "right query")
        self.assertTrue(metadata["langsam_mask_contains_point"])
        self.assertIn("langsam_consistency_score", metadata)

    def test_geometric_consistency_receives_all_query_candidates(self):
        candidates = ["long semantic query", "short object name"]

        selected = self.utils._queries_for_segmentation(
            candidates,
            "geometric_consistency",
        )

        self.assertEqual(selected, candidates)
        self.assertEqual(
            self.utils._queries_for_segmentation(candidates, "baseline"),
            candidates[:1],
        )


if __name__ == "__main__":
    unittest.main()
