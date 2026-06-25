import importlib
import json
import sys
import types
import unittest

import evaluate_all
import evaluate_mimo


def load_utils_module_with_fake_config():
    fake_config = types.ModuleType("utils.config")
    fake_config.client = None
    fake_config.langsam_actor = None
    fake_config.api_key = ""

    original_config = sys.modules.get("utils.config")
    original_utils = sys.modules.get("utils.utils")

    sys.modules["utils.config"] = fake_config
    sys.modules.pop("utils.utils", None)
    try:
        return importlib.import_module("utils.utils")
    finally:
        sys.modules.pop("utils.utils", None)
        if original_utils is not None:
            sys.modules["utils.utils"] = original_utils
        if original_config is not None:
            sys.modules["utils.config"] = original_config
        else:
            sys.modules.pop("utils.config", None)


class UnifiedHardSafeSubsetPolicyTest(unittest.TestCase):
    def test_subset_config_maps_unified_hard_safe_variants(self):
        base = {
            "subset_name": "hard_yes_ambi",
            "prompt_variant": "legacy_old",
            "mimo_retry_mode": "id_repair",
            "segmentation_variant": "point_retry",
        }
        cases = {
            "unified_hard_safe_v1": ("full", "point_retry"),
            "unified_hard_safe_no_hard_fallback": ("no_hard_fallback", "point_retry"),
            "unified_hard_safe_no_ranked_candidates": ("no_ranked_candidates", "point_retry"),
            "unified_hard_safe_no_point_repair": ("no_point_repair", "baseline"),
            "unified_hard_safe_no_id_repair": ("no_id_repair", "point_retry"),
        }

        for subset_policy, (protocol_ablation, segmentation_variant) in cases.items():
            with self.subTest(subset_policy=subset_policy):
                config = evaluate_all._subset_config(**base, subset_policy=subset_policy)

                self.assertEqual(config["prompt_variant"], "unified_hard_safe_v1_json")
                self.assertEqual(config["mimo_retry_mode"], "id_repair")
                self.assertEqual(config["segmentation_variant"], segmentation_variant)
                self.assertEqual(config["protocol_ablation"], protocol_ablation)
                self.assertEqual(config["routing_variant"], "none")
                self.assertEqual(config["feature_source"], "none")
                self.assertFalse(config["uses_benchmark_difficulty"])
                self.assertFalse(config["uses_gt_features"])


class UnifiedHardSafeCliTest(unittest.TestCase):
    def test_evaluate_mimo_accepts_unified_hard_safe_subset_policies(self):
        policies = [
            "unified_hard_safe_v1",
            "unified_hard_safe_no_hard_fallback",
            "unified_hard_safe_no_ranked_candidates",
            "unified_hard_safe_no_point_repair",
            "unified_hard_safe_no_id_repair",
        ]

        for subset_policy in policies:
            with self.subTest(subset_policy=subset_policy):
                args = evaluate_mimo.parse_args(["--subset-policy", subset_policy])
                self.assertEqual(args.subset_policy, subset_policy)


class UnifiedHardSafeParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.utils_module = load_utils_module_with_fake_config()

    def test_valid_protocol_ablations_include_unified_hard_safe_controls(self):
        self.assertTrue(
            {
                "no_hard_fallback",
                "no_ranked_candidates",
                "no_point_repair",
            }.issubset(self.utils_module.VALID_PROTOCOL_ABLATIONS)
        )

    def test_process_grasping_result_applies_hard_fallback_and_uses_ranked_candidate(self):
        result = self.utils_module.process_grasping_result(
            self._hard_scene_output(),
            "target mug",
            protocol_ablation="full",
        )

        self.assertTrue(result["hard_fallback_applied"])
        self.assertEqual(result["pre_repair_action"], "grasp_target")
        self.assertEqual(result["action"], "remove_blocker")
        self.assertEqual(result["pre_repair_first_grasp_object_id"], 2)
        self.assertEqual(result["selected_object_id"], 5)
        self.assertEqual(result["ranked_first_grasp_candidates"], [5, 2, 7])

    def test_process_grasping_result_no_hard_fallback_preserves_direct_grasp(self):
        result = self.utils_module.process_grasping_result(
            self._hard_scene_output(),
            "target mug",
            protocol_ablation="no_hard_fallback",
        )

        self.assertFalse(result["hard_fallback_applied"])
        self.assertEqual(result["action"], "grasp_target")
        self.assertEqual(result["selected_object_id"], 2)
        self.assertEqual(result["pre_repair_first_grasp_object_id"], 2)
        self.assertEqual(result["ranked_first_grasp_candidates"], [5, 2, 7])

    def test_process_grasping_result_no_ranked_candidates_invalidates_selected_id(self):
        result = self.utils_module.process_grasping_result(
            self._hard_scene_output(),
            "target mug",
            protocol_ablation="no_ranked_candidates",
        )

        self.assertTrue(result["hard_fallback_applied"])
        self.assertEqual(result["action"], "remove_blocker")
        self.assertIsNone(result["selected_object_id"])
        self.assertEqual(result["pre_repair_first_grasp_object_id"], 2)
        self.assertEqual(result["ranked_first_grasp_candidates"], [5, 2, 7])

    @staticmethod
    def _hard_scene_output():
        return json.dumps(
            {
                "target_status": "visible_but_blocked",
                "confidence": 0.95,
                "action": "grasp_target",
                "first_grasp_object_id": 2,
                "mask_query": "target mug",
                "ranked_first_grasp_candidates": [5, 2, 7],
                "evidence": {
                    "blocker_evidence": "contact on top of target",
                    "uncertainty": [],
                },
            }
        )


if __name__ == "__main__":
    unittest.main()
