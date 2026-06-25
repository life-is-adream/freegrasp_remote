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
