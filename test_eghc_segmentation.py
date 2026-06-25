"""Tests for EGHC segmentation."""

import unittest

from utils.eghc_segmentation import score_candidate_mask, select_best_mask


class EGHCSegmentationTest(unittest.TestCase):
    def test_contains_point_gets_bonus(self):
        candidate = {"contains_point": True, "sam_score": 0.8, "duplicate_penalty": 0.0}
        score = score_candidate_mask(candidate, (100, 200))
        self.assertAlmostEqual(score, 2.8)

    def test_no_contains_point_no_bonus(self):
        candidate = {"contains_point": False, "sam_score": 0.8, "duplicate_penalty": 0.0}
        score = score_candidate_mask(candidate, (100, 200))
        self.assertAlmostEqual(score, 0.8)

    def test_select_best_mask_prefers_contains_point(self):
        candidates = [
            {"contains_point": False, "sam_score": 0.9, "duplicate_penalty": 0.0},
            {"contains_point": True, "sam_score": 0.7, "duplicate_penalty": 0.0},
        ]
        best = select_best_mask(candidates, (100, 200))
        self.assertTrue(best["contains_point"])

    def test_select_best_mask_returns_none_for_empty(self):
        self.assertIsNone(select_best_mask([], (100, 200)))


if __name__ == "__main__":
    unittest.main()
