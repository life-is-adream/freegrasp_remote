import unittest

import audit_conservative_router as audit


class ConservativeRouterAuditTest(unittest.TestCase):
    def test_audit_detail_separates_evaluation_fields(self):
        detail = {
            "split": "0",
            "subset": "medium_no_ambi",
            "row_index": 0,
            "scene_id": 7,
            "object_id": 2,
            "annotation": "the cup",
            "rsr_correct": 0,
            "ssr_correct": 0,
            "reasoning": {
                "route_mode": "direct",
                "route_confidence": 0.95,
                "target_object_id": 3,
                "target_label": "cup",
                "ambiguity_evidence": [],
                "blocker_evidence": [],
                "visible_object_ids": [1, 2, 3, 4],
                "candidate_geometry_features": {
                    "candidates": {},
                    "relations": [
                        {
                            "source_id": 3,
                            "target_id": 4,
                            "relation": "overlaps",
                            "overlap": 0.2,
                        }
                    ],
                },
            },
        }
        row = audit.audit_detail(detail, policy="conservative_v1")
        self.assertEqual(row["original_route"], "direct")
        self.assertEqual(row["guarded_route"], "target_first")
        self.assertIn("predicted_target_overlap", row["guard_reasons"])
        self.assertEqual(row["evaluation_only"]["rsr_correct"], 0)
        self.assertNotIn("rsr_correct", row["guarded_assessment"])

    def test_summarize_audit_preserves_transition_total(self):
        rows = [
            {"subset": "easy_no_ambi", "original_route": "direct", "guarded_route": "direct"},
            {"subset": "hard_no_ambi", "original_route": "direct", "guarded_route": "target_first"},
        ]
        summary = audit.summarize_audit(rows)
        self.assertEqual(summary["n_rows"], 2)
        self.assertEqual(sum(summary["transitions"].values()), 2)


if __name__ == "__main__":
    unittest.main()
