import unittest
from unittest.mock import patch
import importlib
import sys
import types

import numpy as np
from PIL import Image

from utils.budget2_vote import select_budget2_vote_result


class Budget2VoteSelectionTest(unittest.TestCase):
    def test_prefers_second_output_only_when_first_is_invalid(self) -> None:
        first = {"class_name": "target"}
        second = {"selected_object_id": 2, "class_name": "blue cup"}

        selected, metadata = select_budget2_vote_result(
            first,
            second,
            visible_object_ids=[1, 2, 3],
        )

        self.assertIs(selected, second)
        self.assertEqual(metadata["selected_raw_output_index"], 1)
        self.assertEqual(metadata["selection_reason"], "second_valid_first_invalid")
        self.assertFalse(metadata["first_valid"])
        self.assertTrue(metadata["second_valid"])

    def test_valid_disagreement_keeps_first_output_as_deterministic_tie_break(self) -> None:
        first = {"selected_object_id": 1, "class_name": "red block"}
        second = {"selected_object_id": 2, "class_name": "blue cup"}

        selected, metadata = select_budget2_vote_result(
            first,
            second,
            visible_object_ids=[1, 2, 3],
        )

        self.assertIs(selected, first)
        self.assertEqual(metadata["selected_raw_output_index"], 0)
        self.assertEqual(metadata["selection_reason"], "valid_disagreement_keep_first")
        self.assertTrue(metadata["first_valid"])
        self.assertTrue(metadata["second_valid"])

    def test_both_invalid_keeps_first_output_for_original_protocol_parity(self) -> None:
        first = {"class_name": "target"}
        second = {"selected_object_id": 9, "class_name": "missing object"}

        selected, metadata = select_budget2_vote_result(
            first,
            second,
            visible_object_ids=[1, 2, 3],
        )

        self.assertIs(selected, first)
        self.assertEqual(metadata["selected_raw_output_index"], 0)
        self.assertEqual(metadata["selection_reason"], "both_invalid_keep_first")
        self.assertFalse(metadata["first_valid"])
        self.assertFalse(metadata["second_valid"])


class Budget2VotePipelineTest(unittest.TestCase):
    def test_get_prediction_result_records_two_reasoning_calls_without_repair_count(self) -> None:
        old_config = sys.modules.get("utils.config")
        old_utils = sys.modules.get("utils.utils")
        config_stub = types.ModuleType("utils.config")
        config_stub.client = types.SimpleNamespace()
        config_stub.langsam_actor = types.SimpleNamespace(sam=None)
        config_stub.api_key = "test"
        sys.modules["utils.config"] = config_stub
        sys.modules.pop("utils.utils", None)
        try:
            freegrasp_utils = importlib.import_module("utils.utils")

            with (
                patch.object(freegrasp_utils, "load_image_as_base64", return_value="image64"),
                patch.object(
                    freegrasp_utils,
                    "parse_points_with_id",
                    return_value=(
                        [(1, 10, 10, 1), (2, 20, 20, 2)],
                        {1: 1, 2: 2},
                        ["Molmo_ID X Y GT_ID\n", "1 10 10 1\n", "2 20 20 2\n"],
                    ),
                ),
                patch.object(freegrasp_utils, "_build_reasoning_input_text", return_value="input"),
                patch.object(freegrasp_utils, "get_reasoning_system_prompt", return_value="prompt"),
                patch.object(freegrasp_utils, "_make_reasoning_messages", return_value=[{"role": "user"}]),
                patch.object(
                    freegrasp_utils,
                    "_call_reasoning_model",
                    side_effect=["invalid answer", "[2, blue cup]"],
                ) as call_reasoning_model,
                patch.object(
                    freegrasp_utils,
                    "_predict_langsam_mask",
                    return_value=(np.ones((2, 2), dtype=bool), None, {"mask_source": "stub"}),
                ),
            ):
                result = freegrasp_utils.get_prediction_result(
                    image=Image.new("RGB", (2, 2)),
                    path="/tmp/freegrasp-test-scene",
                    scene_number=101,
                    text="blue cup",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="budget2_vote",
                    segmentation_variant="baseline",
                    routing_variant="none",
                    feature_source="none",
                )
        finally:
            if old_config is None:
                sys.modules.pop("utils.config", None)
            else:
                sys.modules["utils.config"] = old_config
            if old_utils is None:
                sys.modules.pop("utils.utils", None)
            else:
                sys.modules["utils.utils"] = old_utils

        self.assertNotIn("error", result)
        self.assertEqual(result["mask"].shape, (2, 2))
        reasoning = result["reasoning"]
        self.assertEqual(call_reasoning_model.call_count, 2)
        self.assertEqual(reasoning["raw_outputs"], ["invalid answer", "[2, blue cup]"])
        self.assertEqual(reasoning["retry_count"], 0)
        self.assertEqual(reasoning["selected_object_id"], 2)
        self.assertEqual(reasoning["selected_raw_output_index"], 1)
        self.assertEqual(
            reasoning["budget2_vote"]["selection_reason"],
            "second_valid_first_invalid",
        )
        self.assertEqual(reasoning["raw_output"], "[2, blue cup]")


if __name__ == "__main__":
    unittest.main()
