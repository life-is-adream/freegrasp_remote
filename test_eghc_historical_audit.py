"""Tests for EGHC historical run audit."""

import unittest

from audit_historical_runs import classify_run


class HistoricalRunAuditTest(unittest.TestCase):
    def test_classifies_uhs1_like_rows_as_oracle_assisted(self):
        manifest = {"feature_source": "none", "subset_policy": "unified_hard_safe_v1"}
        sample = {
            "reasoning": {
                "semantic_source": "instances_semantic",
                "geometry_source": "instances_objects",
                "molmo_to_gt_map_used": True,
            }
        }
        result = classify_run(manifest, [sample])
        self.assertEqual(result["provenance_class"], "oracle_assisted")

    def test_classifies_plain_s0_like_rows_as_clean_no_gt(self):
        manifest = {"feature_source": "none", "subset_policy": "original_protocol"}
        sample = {"reasoning": {"semantic_source": "molmo_text", "geometry_source": None}}
        result = classify_run(manifest, [sample])
        self.assertEqual(result["provenance_class"], "clean_no_gt")

    def test_oracle_feature_source_is_oracle_assisted(self):
        manifest = {"feature_source": "oracle_feature"}
        sample = {"reasoning": {}}
        result = classify_run(manifest, [sample])
        self.assertEqual(result["provenance_class"], "oracle_assisted")


if __name__ == "__main__":
    unittest.main()
