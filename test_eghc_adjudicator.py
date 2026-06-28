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

    def test_consensus_policy_rejects_freeform_qwen_replacement(self):
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
                "confidence": 0.92,
                "reason": "looks better",
            }
        )

        parsed = parse_adjudication_output(
            output,
            current_plan,
            visible_ids={3, 5, 7},
            route_decision={
                "selected_route": "blocker_first",
                "route_guard_variant": "eghc_consensus_v1",
            },
            assessment={"target_object_id": 3},
        )

        self.assertFalse(parsed["accepted"])
        self.assertEqual(parsed["plan"]["first_grasp_object_id"], 5)
        self.assertIn("non_consensus", parsed["reason"])

    def test_consensus_policy_accepts_blocker_veto_to_target(self):
        current_plan = {
            "first_grasp_object_id": 5,
            "first_grasp_label": "white box",
            "mask_query": "white box",
        }
        output = json.dumps(
            {
                "decision": "replace",
                "first_grasp_object_id": 3,
                "first_grasp_label": "target mug",
                "mask_query": "target mug",
                "confidence": 0.86,
                "reason": "blocker evidence is weak; grasp target first",
            }
        )

        parsed = parse_adjudication_output(
            output,
            current_plan,
            visible_ids={3, 5, 7},
            route_decision={
                "selected_route": "blocker_first",
                "route_guard_variant": "eghc_consensus_v1",
            },
            assessment={"target_object_id": 3},
        )

        self.assertTrue(parsed["accepted"])
        self.assertEqual(parsed["decision"], "veto_to_target")
        self.assertEqual(parsed["plan"]["first_grasp_object_id"], 3)

    def test_consensus_policy_does_not_adjudicate_easy_direct(self):
        self.assertFalse(
            should_trigger_adjudication(
                assessment={"blocking_relations": [{"blocker_id": 5}]},
                route_decision={
                    "selected_route": "direct",
                    "evaluation_subset": "easy_yes_ambi",
                    "route_guard_variant": "eghc_consensus_v1",
                },
                plan={"first_grasp_object_id": 3, "confidence": 0.9},
                visible_ids={3, 5, 7},
            )
        )

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
