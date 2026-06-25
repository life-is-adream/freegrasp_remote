"""Tests for EGHC challenger eligibility."""

import unittest

from train_eghc_challenger import evaluate_training_eligibility


class EGHCChallengerTest(unittest.TestCase):
    def test_ineligible_without_clean_route_coverage(self):
        registry_rows = [
            {"provenance_class": "oracle_assisted", "route_executed": "direct"},
            {"provenance_class": "clean_no_gt", "route_executed": None},
        ]
        report = evaluate_training_eligibility(registry_rows)
        self.assertFalse(report["eligible"])
        self.assertEqual(report["selected_router"], "guard_only")

    def test_eligible_with_all_routes_covered(self):
        registry_rows = [
            {"provenance_class": "clean_no_gt", "route_executed": "direct"},
            {"provenance_class": "clean_no_gt", "route_executed": "target_first"},
            {"provenance_class": "clean_no_gt", "route_executed": "blocker_first"},
        ]
        report = evaluate_training_eligibility(registry_rows)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["selected_router"], "hybrid_guard_plus_challenger")

    def test_oracle_assisted_rows_ignored(self):
        registry_rows = [
            {"provenance_class": "oracle_assisted", "route_executed": "direct"},
            {"provenance_class": "oracle_assisted", "route_executed": "target_first"},
            {"provenance_class": "oracle_assisted", "route_executed": "blocker_first"},
        ]
        report = evaluate_training_eligibility(registry_rows)
        self.assertFalse(report["eligible"])


if __name__ == "__main__":
    unittest.main()
