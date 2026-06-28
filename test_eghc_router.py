"""Tests for EGHC deterministic guard router."""

import unittest

from utils.eghc_router import select_route


class EGHCRouterTest(unittest.TestCase):
    def test_strong_direct_requires_free_visible_and_no_blockers(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "identity_score": 0.92}],
            "target_visibility": "free_visible",
            "blocking_relations": [],
            "recommended_route": "direct",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "direct")

    def test_unsupported_blocker_first_downgrades_to_target_first(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "identity_score": 0.81}],
            "target_visibility": "mostly_hidden",
            "blocking_relations": [],
            "recommended_route": "blocker_first",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "target_first")

    def test_blocker_first_with_relations_stays_blocker_first(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3}],
            "target_visibility": "visible_but_blocked",
            "blocking_relations": [{"blocker_id": 5}],
            "recommended_route": "blocker_first",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "blocker_first")

    def test_consensus_policy_protects_easy_direct(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "valid": True}],
            "target_visibility": "visible_but_blocked",
            "blocking_relations": [{"blocker_id": 5}],
            "recommended_route": "blocker_first",
        }

        decision = select_route(
            packet,
            assessment,
            challenger=None,
            evaluation_subset="easy_no_ambi",
            route_guard_variant="eghc_consensus_v1",
        )

        self.assertEqual(decision["selected_route"], "direct")
        self.assertIn("easy_direct_protection", decision["guard_reasons"])

    def test_consensus_policy_requires_strong_hard_yes_blocker_evidence(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "valid": True}],
            "target_visibility": "mostly_hidden",
            "blocking_relations": [{"blocker_id": 5, "relation": "near"}],
            "recommended_route": "blocker_first",
            "route_confidence": 0.61,
        }

        decision = select_route(
            packet,
            assessment,
            challenger=None,
            evaluation_subset="hard_yes_ambi",
            route_guard_variant="eghc_consensus_v1",
        )

        self.assertEqual(decision["selected_route"], "target_first")
        self.assertIn("hard_yes_weak_blocker_evidence", decision["guard_reasons"])

    def test_consensus_policy_allows_strong_hard_yes_blocker_evidence(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "valid": True}],
            "target_visibility": "mostly_hidden",
            "blocking_relations": [
                {
                    "blocker_id": 5,
                    "relation": "coverage",
                    "evidence": "object 5 visibly covers the target",
                    "confidence": 0.82,
                }
            ],
            "recommended_route": "blocker_first",
            "route_confidence": 0.83,
        }

        decision = select_route(
            packet,
            assessment,
            challenger=None,
            evaluation_subset="hard_yes_ambi",
            route_guard_variant="eghc_consensus_v1",
        )

        self.assertEqual(decision["selected_route"], "blocker_first")

    def test_direct_with_blockers_downgrades(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3}],
            "target_visibility": "free_visible",
            "blocking_relations": [{"blocker_id": 5}],
            "recommended_route": "direct",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "target_first")


if __name__ == "__main__":
    unittest.main()
