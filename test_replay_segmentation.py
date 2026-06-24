import unittest

import replay_segmentation as replay


class ReplaySegmentationTest(unittest.TestCase):
    def test_frozen_decision_requires_id_and_point(self):
        with self.assertRaisesRegex(
            ValueError,
            "selected_object_id and molmo_point",
        ):
            replay.frozen_decision({"reasoning": {}, "rsr_correct": 0})

    def test_replay_row_preserves_reasoning_outcome(self):
        detail = {
            "scene_id": 7,
            "object_id": 3,
            "rsr_correct": 1,
            "reasoning": {
                "selected_object_id": 4,
                "molmo_point": [12, 15],
                "class_name": "white bandage",
            },
        }

        row = replay.replay_row(
            detail,
            segment=lambda decision: {
                "iou": 0.75,
                "contains_point": True,
                "failure_reason": None,
            },
        )

        self.assertEqual(row["rsr_correct"], 1)
        self.assertEqual(row["ssr_correct"], 1)
        self.assertEqual(row["selected_object_id"], 4)

    def test_summary_enforces_source_rsr(self):
        rows = [
            {
                "rsr_correct": 1,
                "ssr_correct": 1,
                "iou": 0.8,
                "contains_point": True,
                "failure_reason": None,
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "changed frozen reasoning"):
            replay.summarize_replay(rows, source_rsr_count=0)

    def test_summary_reports_audit_metrics(self):
        rows = [
            {
                "rsr_correct": 1,
                "ssr_correct": 1,
                "iou": 0.8,
                "contains_point": True,
                "failure_reason": None,
                "source_ssr_correct": 0,
            },
            {
                "rsr_correct": 1,
                "ssr_correct": 0,
                "iou": 0.1,
                "contains_point": False,
                "failure_reason": "no_candidate_contains_point",
                "source_ssr_correct": 1,
            },
        ]

        summary = replay.summarize_replay(rows, source_rsr_count=2)

        self.assertEqual(summary["n"], 2)
        self.assertEqual(summary["rsr_count"], 2)
        self.assertEqual(summary["ssr_count"], 1)
        self.assertEqual(summary["point_consistency_failures"], 1)
        self.assertEqual(summary["recovery_successes"], 1)
        self.assertEqual(summary["same_class_mask_swaps"], 1)
        self.assertAlmostEqual(summary["mean_iou"], 0.45)


if __name__ == "__main__":
    unittest.main()
