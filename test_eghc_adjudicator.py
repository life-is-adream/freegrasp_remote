"""Tests for EGHC adjudication."""

import json
import unittest

from utils.eghc_adjudicator import (
    parse_adjudication_output,
    resolve_qwen_api_key,
    should_trigger_adjudication,
)


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

    def test_blocker_first_triggers_qwen_even_with_valid_id(self):
        self.assertTrue(
            should_trigger_adjudication(
                assessment={"target_candidates": [{"object_id": 3}]},
                route_decision={"selected_route": "blocker_first"},
                plan={"first_grasp_object_id": 5, "confidence": 0.9},
                visible_ids={3, 5, 7},
            )
        )

    def test_valid_qwen_replacement_plan_is_accepted(self):
        current_plan = {
            "first_grasp_object_id": 5,
            "first_grasp_label": "white box",
            "mask_query": "white box",
        }
        output = json.dumps(
            {
                "decision": "replace",
                "first_grasp_object_id": 7,
                "first_grasp_label": "blue cup",
                "mask_query": "blue cup",
                "confidence": 0.84,
                "reason": "object 7 covers the target more directly",
            }
        )

        parsed = parse_adjudication_output(output, current_plan, visible_ids={3, 5, 7})

        self.assertTrue(parsed["accepted"])
        self.assertEqual(parsed["plan"]["first_grasp_object_id"], 7)
        self.assertEqual(parsed["plan"]["mask_query"], "blue cup")

    def test_invalid_qwen_replacement_keeps_current_plan(self):
        current_plan = {
            "first_grasp_object_id": 5,
            "first_grasp_label": "white box",
            "mask_query": "white box",
        }
        output = json.dumps(
            {
                "decision": "replace",
                "first_grasp_object_id": 99,
                "first_grasp_label": "invented object",
                "mask_query": "invented object",
            }
        )

        parsed = parse_adjudication_output(output, current_plan, visible_ids={3, 5, 7})

        self.assertFalse(parsed["accepted"])
        self.assertEqual(parsed["plan"]["first_grasp_object_id"], 5)
        self.assertIn("invalid", parsed["reason"])

    def test_qwen_key_preferred_over_mimo_dashscope_placeholder(self):
        env = {
            "DASHSCOPE_API_KEY": "unused-by-evaluate-mimo",
            "QWEN_API_KEY": "real-qwen-key",
        }

        self.assertEqual(resolve_qwen_api_key(env), "real-qwen-key")

    def test_dashscope_key_used_when_not_placeholder(self):
        env = {"DASHSCOPE_API_KEY": "real-dashscope-key"}

        self.assertEqual(resolve_qwen_api_key(env), "real-dashscope-key")


if __name__ == "__main__":
    unittest.main()
