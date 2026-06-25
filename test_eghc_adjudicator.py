"""Tests for EGHC adjudication."""

import unittest

from utils.eghc_adjudicator import should_trigger_adjudication


class EGHCAdjudicationTest(unittest.TestCase):
    def test_invalid_call2_id_triggers_qwen(self):
        self.assertTrue(
            should_trigger_adjudication(
                assessment={"target_candidates": [{"object_id": 3}]},
                route_decision={"selected_route": "direct"},
                plan={"first_grasp_object_id": 99},
                visible_ids={3, 5, 7},
            )
        )

    def test_valid_id_no_adjudication(self):
        self.assertFalse(
            should_trigger_adjudication(
                assessment={"target_candidates": [{"object_id": 3}]},
                route_decision={"selected_route": "direct"},
                plan={"first_grasp_object_id": 3, "confidence": 0.9},
                visible_ids={3, 5, 7},
            )
        )

    def test_low_confidence_triggers_adjudication(self):
        self.assertTrue(
            should_trigger_adjudication(
                assessment={"target_candidates": [{"object_id": 3}]},
                route_decision={"selected_route": "target_first"},
                plan={"first_grasp_object_id": 3, "confidence": 0.5},
                visible_ids={3, 5, 7},
            )
        )


if __name__ == "__main__":
    unittest.main()
