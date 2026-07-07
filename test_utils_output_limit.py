import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


def _install_import_stubs():
    class _LangsamStub:
        def predict(self, *args, **kwargs):
            return None

    config_stub = types.ModuleType("utils.config")
    config_stub.client = None
    config_stub.langsam_actor = _LangsamStub()
    config_stub.api_key = "test"
    sys.modules["utils.config"] = config_stub

    data_utils_stub = types.ModuleType("models.FGC_graspnet.utils.data_utils")
    data_utils_stub.create_point_cloud_from_depth_image = lambda *args, **kwargs: None
    models_stub = sys.modules.setdefault("models", types.ModuleType("models"))
    models_stub.__path__ = [str(Path(__file__).resolve().parent / "models")]
    sys.modules.setdefault("models.FGC_graspnet", types.ModuleType("models.FGC_graspnet"))
    sys.modules.setdefault("models.FGC_graspnet.utils", types.ModuleType("models.FGC_graspnet.utils"))
    sys.modules["models.FGC_graspnet.utils.data_utils"] = data_utils_stub


class _FakeMessage:
    def __init__(self, content="[3, blue screwdriver]"):
        self.content = content


class _FakeChoice:
    def __init__(self, content="[3, blue screwdriver]"):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content="[3, blue screwdriver]"):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, outputs=None):
        self.kwargs = None
        self.calls = []
        self.outputs = list(outputs or ["[3, blue screwdriver]"])

    def create(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append(kwargs)
        output = self.outputs.pop(0) if self.outputs else "[3, blue screwdriver]"
        return _FakeResponse(output)


class _FakeChat:
    def __init__(self, outputs=None):
        self.completions = _FakeCompletions(outputs)


class _FakeClient:
    def __init__(self, outputs=None):
        self.chat = _FakeChat(outputs)


class _FakeBox:
    def cpu(self):
        return self

    def numpy(self):
        return [0, 0, 1, 1]


class _FakeMask:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=np.uint8)

    def cpu(self):
        return self

    def numpy(self):
        return self.array

    def __array__(self, dtype=None):
        return np.asarray(self.array, dtype=dtype)


class UtilsOutputLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_import_stubs()
        sys.modules.pop("utils.utils", None)
        cls.utils = importlib.import_module("utils.utils")

    def test_legacy_prompt_requires_short_bracket_output(self):
        prompt = self.utils.get_reasoning_system_prompt("legacy")

        self.assertIn("Do not explain", prompt)
        self.assertIn("Do not include markdown", prompt)
        self.assertIn("one line", prompt)
        self.assertIn("[object_id, color class_name]", prompt)

    def test_legacy_old_prompt_keeps_original_unrestricted_wording(self):
        prompt = self.utils.get_reasoning_system_prompt("legacy_old")

        self.assertIn("The output should only be the object ID", prompt)
        self.assertIn("must formatted as: [object_id, color class_name]", prompt)
        self.assertNotIn("Do not explain", prompt)

    def test_hard_occlusion_prompt_restricts_answer_to_visible_object_ids(self):
        prompt = self.utils.get_reasoning_system_prompt("hard_occlusion")

        self.assertIn("visible numeric object IDs", prompt)
        self.assertIn("fully occluded", prompt)
        self.assertIn("[object_id, color class_name]", prompt)

    def test_roborefer_json_prompt_requires_structured_candidate_reasoning(self):
        prompt = self.utils.get_reasoning_system_prompt("roborefer_json")

        self.assertIn("Return exactly one JSON object", prompt)
        self.assertIn("target_parse", prompt)
        self.assertIn("candidate_analysis", prompt)
        self.assertIn("occlusion_role", prompt)
        self.assertIn("decision", prompt)
        self.assertIn("mask_query", prompt)

    def test_candidate_grasp_json_prompt_separates_target_from_first_grasp_object(self):
        prompt = self.utils.get_reasoning_system_prompt("candidate_grasp_json")

        self.assertIn("first visible object to grasp", prompt)
        self.assertIn("requested_target", prompt)
        self.assertIn("target_candidate_id", prompt)
        self.assertIn("first_grasp_decision", prompt)
        self.assertIn("first_grasp_object_id", prompt)
        self.assertIn("direct_obstructor", prompt)
        self.assertIn("mask_query", prompt)
        self.assertIn("compact JSON", prompt)
        self.assertIn("Do not include location words", prompt)

    def test_candidate_grasp_fewshot_prompt_includes_hard_first_grasp_examples(self):
        prompt = self.utils.get_reasoning_system_prompt("candidate_grasp_fewshot_json")

        self.assertIn("Examples are not the current image", prompt)
        self.assertIn("the white box in the middle under the toothpaste and screwdriver", prompt)
        self.assertIn("orange toothpaste box", prompt)
        self.assertIn("the cable", prompt)
        self.assertIn("yellow pliers", prompt)
        self.assertIn("the white box on the right-hand side under the chewing gum box", prompt)
        self.assertIn("blue chewing gum box", prompt)
        self.assertIn("first_grasp_object_id", prompt)

    def test_candidate_grasp_fewshot_input_adds_first_grasp_rule_reminder(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the white box",
            [(1, 10, 20, 2), (2, 30, 40, 4)],
            "candidate_grasp_fewshot_json",
        )

        self.assertIn("Visible object candidates", text)
        self.assertIn("id=1, point=(10, 20)", text)
        self.assertIn("First-grasp rule reminder", text)
        self.assertIn("requested_target_id", text)
        self.assertIn("first_grasp_object_id", text)

    def test_candidate_grasp_spatial_input_adds_region_and_rank_features(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the orange nearest to the image bottom",
            [(1, 10, 10, 2), (2, 50, 50, 4), (3, 90, 90, 5)],
            "candidate_grasp_spatial_json",
        )

        self.assertIn("Visible object candidates", text)
        self.assertIn("id=1, point=(10, 10), region=top-left", text)
        self.assertIn("id=2, point=(50, 50), region=center", text)
        self.assertIn("id=3, point=(90, 90), region=bottom-right", text)
        self.assertIn("x_rank=1/3", text)
        self.assertIn("y_rank=3/3", text)
        self.assertIn("bottom_rank=1/3", text)
        self.assertIn("center_rank=1/3", text)
        self.assertIn("Spatial rank reminder", text)

    def test_candidate_grasp_semantic_prompt_uses_short_candidate_labels(self):
        prompt = self.utils.get_reasoning_system_prompt("candidate_grasp_semantic_json")

        self.assertIn("semantic label", prompt)
        self.assertIn("label=", prompt)
        self.assertIn("Color words may describe appearance", prompt)
        self.assertIn("first_grasp_object_id", prompt)

    def test_target_first_grasp_planner_prompt_forces_two_stage_decision(self):
        prompt = self.utils.get_reasoning_system_prompt("target_first_grasp_planner_json")

        self.assertIn("target_resolution", prompt)
        self.assertIn("first_grasp_planning", prompt)
        self.assertIn("target_object_id", prompt)
        self.assertIn("first_grasp_object_id", prompt)
        self.assertIn("If target_object_id equals first_grasp_object_id", prompt)
        self.assertIn("do not pick the requested target", prompt)
        self.assertIn("direct blocker", prompt)
        self.assertIn("label=", prompt)

    def test_target_first_grasp_planner_v7_prompt_downweights_noisy_semantic_labels(self):
        prompt = self.utils.get_reasoning_system_prompt("target_first_grasp_planner_v7_json")

        self.assertIn("target_resolution", prompt)
        self.assertIn("first_grasp_planning", prompt)
        self.assertIn("semantic labels are weak hints", prompt)
        self.assertIn("unknown labels", prompt)
        self.assertIn("planner consistency", prompt)

    def test_target_first_grasp_geometry_v8_prompt_requires_geometry_checks(self):
        prompt = self.utils.get_reasoning_system_prompt("target_first_grasp_geometry_v8_json")

        self.assertIn("target_resolution", prompt)
        self.assertIn("first_grasp_planning", prompt)
        self.assertIn("geometry evidence", prompt)
        self.assertIn("bbox", prompt)
        self.assertIn("bottom_edge_rank", prompt)
        self.assertIn("same-category instance confusion", prompt)

    def test_target_first_evidence_gate_v9_prompt_requires_relation_backed_blockers(self):
        prompt = self.utils.get_reasoning_system_prompt("target_first_evidence_gate_v9_json")

        self.assertIn("target_resolution", prompt)
        self.assertIn("first_grasp_planning", prompt)
        self.assertIn("blocker_evidence", prompt)
        self.assertIn("Spatial words locate the target", prompt)
        self.assertIn("direct relation evidence", prompt)
        self.assertIn("default to grasping the target", prompt)

    def test_target_first_evidence_gate_v9_input_adds_geometry_relations_and_reminder(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the pear under the other pear",
            [(4, 619, 315, 2), (5, 830, 442, 1)],
            "target_first_evidence_gate_v9_json",
            semantic_labels={4: "pear", 5: "pear"},
            geometry_features={
                "candidates": {
                    4: {
                        "bbox": (600, 260, 900, 500),
                        "area": 8100,
                        "area_rank": 1,
                        "bottom_edge_rank": 2,
                        "center": (750, 380),
                    },
                    5: {
                        "bbox": (760, 350, 1080, 620),
                        "area": 7800,
                        "area_rank": 2,
                        "bottom_edge_rank": 1,
                        "center": (920, 485),
                    },
                },
                "relations": [
                    {
                        "source_id": 4,
                        "target_id": 5,
                        "relation": "overlaps",
                        "overlap": 0.26,
                        "vertical_order": "above",
                    }
                ],
            },
        )

        self.assertIn("Candidate geometry relations", text)
        self.assertIn("relation id=4->5", text)
        self.assertIn("V9 evidence gate reminder", text)
        self.assertIn("blocker requires overlap/near relation evidence", text)

    def test_hard_blocker_first_v10_prompt_forbids_direct_target_selection(self):
        prompt = self.utils.get_reasoning_system_prompt("hard_blocker_first_v10_json")

        self.assertIn("hard-scene blocker-first", prompt)
        self.assertIn('"should_grasp_target_directly":false', prompt)
        self.assertIn("Never return the requested target as the first grasp", prompt)
        self.assertIn("near alone is not sufficient", prompt)
        self.assertIn("visible direct blocker", prompt)

    def test_hard_blocker_first_v10_input_adds_geometry_and_blocker_reminder(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the pear under the other pear",
            [(4, 619, 315, 2), (5, 830, 442, 1)],
            "hard_blocker_first_v10_json",
            semantic_labels={4: "pear", 5: "pear"},
            geometry_features={
                "candidates": {
                    4: {
                        "bbox": (600, 260, 900, 500),
                        "area": 8100,
                        "area_rank": 1,
                        "bottom_edge_rank": 2,
                        "center": (750, 380),
                    },
                    5: {
                        "bbox": (760, 350, 1080, 620),
                        "area": 7800,
                        "area_rank": 2,
                        "bottom_edge_rank": 1,
                        "center": (920, 485),
                    },
                },
                "relations": [
                    {
                        "source_id": 4,
                        "target_id": 5,
                        "relation": "overlaps",
                        "overlap": 0.26,
                        "vertical_order": "above",
                    }
                ],
            },
        )

        self.assertIn("Candidate geometry relations", text)
        self.assertIn("relation id=4->5", text)
        self.assertIn("V10 hard blocker-first reminder", text)
        self.assertIn("never choose the requested target directly", text)
        self.assertIn("near alone cannot prove blocking", text)

    def test_candidate_grasp_semantic_input_adds_labels_without_gt_ids(self):
        text = self.utils._format_visible_object_candidates(
            [(1, 10, 10, 6), (2, 90, 90, 1)],
            include_spatial=True,
            include_semantic=True,
            semantic_labels={1: "box_7", 2: "orange"},
        )

        self.assertIn("id=1, label=box_7, point=(10, 10)", text)
        self.assertIn("id=2, label=orange, point=(90, 90)", text)
        self.assertIn("region=bottom-right", text)
        self.assertNotIn("GT_ID", text)
        self.assertNotIn("gt_id", text)

    def test_target_first_grasp_planner_input_uses_spatial_labels_and_reminders(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the strawberry under the white box",
            [(2, 10, 10, 7), (5, 90, 90, 1)],
            "target_first_grasp_planner_json",
            semantic_labels={2: "box_7", 5: "strawberry"},
        )

        self.assertIn("Visible object candidates", text)
        self.assertIn("id=2, label=box_7, point=(10, 10)", text)
        self.assertIn("id=5, label=strawberry, point=(90, 90)", text)
        self.assertIn("First-grasp rule reminder", text)
        self.assertIn("Spatial rank reminder", text)
        self.assertIn("V6 planner reminder", text)
        self.assertNotIn("GT_ID", text)
        self.assertNotIn("gt_id", text)

    def test_target_first_grasp_planner_v7_input_hides_semantic_placeholders(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the orange nearest to the image bottom",
            [(1, 10, 10, 6), (2, 90, 90, 1)],
            "target_first_grasp_planner_v7_json",
            semantic_labels={1: "semantic_62", 2: "power_drill"},
        )

        self.assertIn("id=1, label=unknown, point=(10, 10)", text)
        self.assertIn("id=2, label=power_drill, point=(90, 90)", text)
        self.assertIn("V7 planner reminder", text)
        self.assertNotIn("semantic_62", text)

    def test_target_first_grasp_geometry_v8_input_adds_bbox_and_relations(self):
        text = self.utils._build_reasoning_input_text(
            "Grasp the pear under the other pear",
            [(4, 619, 315, 2), (5, 830, 442, 1)],
            "target_first_grasp_geometry_v8_json",
            semantic_labels={4: "peach", 5: "peach"},
            geometry_features={
                "candidates": {
                    4: {
                        "bbox": (600, 260, 900, 500),
                        "area": 8100,
                        "area_rank": 1,
                        "bottom_edge_rank": 2,
                        "center": (750, 380),
                    },
                    5: {
                        "bbox": (760, 350, 1080, 620),
                        "area": 7800,
                        "area_rank": 2,
                        "bottom_edge_rank": 1,
                        "center": (920, 485),
                    },
                },
                "relations": [
                    {
                        "source_id": 4,
                        "target_id": 5,
                        "relation": "overlaps",
                        "overlap": 0.26,
                        "vertical_order": "above",
                    }
                ],
            },
        )

        self.assertIn("id=4, label=peach, point=(619, 315)", text)
        self.assertIn("bbox=(600,260,900,500)", text)
        self.assertIn("area_rank=1/2", text)
        self.assertIn("bottom_edge_rank=1/2", text)
        self.assertIn("Candidate geometry relations", text)
        self.assertIn("relation id=4->5", text)
        self.assertIn("overlap=0.26", text)
        self.assertIn("V8 geometry reminder", text)

    def test_direct_target_prompt_avoids_obstacle_removal_for_easy_scenes(self):
        prompt = self.utils.get_reasoning_system_prompt("direct_target")

        self.assertIn("best matches the requested target", prompt)
        self.assertIn("Do not choose an obstacle", prompt)
        self.assertIn("[object_id, color class_name]", prompt)

    def test_visible_id_guard_prompt_keeps_bracket_format_but_restricts_ids(self):
        prompt = self.utils.get_reasoning_system_prompt("visible_id_guard")

        self.assertIn("visible numeric object IDs", prompt)
        self.assertIn("The object_id must be one of the visible numeric object IDs", prompt)
        self.assertIn("[object_id, color class_name]", prompt)

    def test_eghc_qwen_native_prompt_uses_strict_first_grasp_json(self):
        prompt = self.utils.get_reasoning_system_prompt("eghc_qwen_native_json")

        self.assertIn('"first_grasp_object_id"', prompt)
        self.assertIn('"mask_query"', prompt)
        self.assertIn('"blocker_first"', prompt)
        self.assertIn("Return exactly one JSON object", prompt)
        self.assertIn("Do not return target_candidates", prompt)
        self.assertNotIn("[object_id, color class_name]", prompt)

    def test_process_grasping_result_accepts_supported_formats(self):
        self.assertEqual(
            self.utils.process_grasping_result("[3, blue screwdriver]", "target"),
            {"selected_object_id": 3, "class_name": "blue screwdriver"},
        )
        self.assertEqual(
            self.utils.process_grasping_result("[pick object, 3, blue screwdriver]", "target"),
            {"selected_object_id": 3, "class_name": "blue screwdriver"},
        )
        self.assertEqual(
            self.utils.process_grasping_result('{"object_id": 3, "class_name": "blue screwdriver"}', "target"),
            {"selected_object_id": 3, "class_name": "blue screwdriver"},
        )

    def test_process_grasping_result_accepts_top_level_first_grasp_json(self):
        output = (
            '{"first_grasp_object_id":2,"first_grasp_label":"white box",'
            '"mask_query":"white box","route":"blocker_first","confidence":0.91}'
        )

        self.assertEqual(
            self.utils.process_grasping_result(output, "the strawberry under a white box"),
            {
                "selected_object_id": 2,
                "class_name": "white box",
                "mask_query": "white box",
                "route": "blocker_first",
                "confidence": 0.91,
            },
        )

    def test_process_grasping_result_accepts_roborefer_decision_json(self):
        output = (
            '{"target_parse":{"category":"screwdriver"},'
            '"candidate_analysis":[{"object_id":3,"target_match":"yes"}],'
            '"decision":{"object_id":3,"class_name":"blue screwdriver",'
            '"mask_query":"blue screwdriver","action":"pick_target"}}'
        )

        self.assertEqual(
            self.utils.process_grasping_result(output, "target"),
            {
                "selected_object_id": 3,
                "class_name": "blue screwdriver",
                "mask_query": "blue screwdriver",
                "reasoning_json": {
                    "target_parse": {"category": "screwdriver"},
                    "candidate_analysis": [{"object_id": 3, "target_match": "yes"}],
                    "decision": {
                        "object_id": 3,
                        "class_name": "blue screwdriver",
                        "mask_query": "blue screwdriver",
                        "action": "pick_target",
                    },
                },
            },
        )

    def test_process_grasping_result_accepts_first_grasp_decision_json(self):
        output = (
            '{"requested_target":{"category":"strawberry","target_candidate_id":5},'
            '"candidate_analysis":[{"object_id":2,"role":"direct_obstructor"},'
            '{"object_id":5,"role":"requested_target"}],'
            '"first_grasp_decision":{"action":"remove_obstructor",'
            '"first_grasp_object_id":2,"class_name":"white box",'
            '"mask_query":"white box","role":"direct_obstructor","confidence":0.71}}'
        )

        self.assertEqual(
            self.utils.process_grasping_result(output, "the strawberry under a white box"),
            {
                "selected_object_id": 2,
                "class_name": "white box",
                "mask_query": "white box",
                "confidence": 0.71,
                "reasoning_json": {
                    "requested_target": {"category": "strawberry", "target_candidate_id": 5},
                    "candidate_analysis": [
                        {"object_id": 2, "role": "direct_obstructor"},
                        {"object_id": 5, "role": "requested_target"},
                    ],
                    "first_grasp_decision": {
                        "action": "remove_obstructor",
                        "first_grasp_object_id": 2,
                        "class_name": "white box",
                        "mask_query": "white box",
                        "role": "direct_obstructor",
                        "confidence": 0.71,
                    },
                },
            },
        )

    def test_process_grasping_result_accepts_target_first_grasp_planner_json(self):
        output = (
            '{"target_resolution":{"target_object_id":5,"target_label":"strawberry",'
            '"target_visibility":"visible_but_blocked"},'
            '"first_grasp_planning":{"should_grasp_target_directly":false,'
            '"blocking_candidates":[{"object_id":2,"label":"box_7","priority":1}],'
            '"first_grasp_object_id":2,"first_grasp_label":"white box",'
            '"mask_query":"white box","decision_rule":"remove_direct_blocker"}}'
        )

        self.assertEqual(
            self.utils.process_grasping_result(output, "the strawberry under a white box"),
            {
                "selected_object_id": 2,
                "class_name": "white box",
                "mask_query": "white box",
                "reasoning_json": {
                    "target_resolution": {
                        "target_object_id": 5,
                        "target_label": "strawberry",
                        "target_visibility": "visible_but_blocked",
                    },
                    "first_grasp_planning": {
                        "should_grasp_target_directly": False,
                        "blocking_candidates": [{"object_id": 2, "label": "box_7", "priority": 1}],
                        "first_grasp_object_id": 2,
                        "first_grasp_label": "white box",
                        "mask_query": "white box",
                        "decision_rule": "remove_direct_blocker",
                    },
                },
            },
        )

    def test_process_grasping_result_repairs_direct_target_null_first_grasp_from_target_resolution(self):
        output = (
            '{"target_resolution":{"target_object_id":4,"target_label":"bandage",'
            '"target_visibility":"free_visible"},'
            '"first_grasp_planning":{"should_grasp_target_directly":true,'
            '"blocking_candidates":[],"first_grasp_object_id":null,'
            '"first_grasp_label":"bandage","mask_query":"bandage",'
            '"confidence":0.88}}'
        )

        result = self.utils.process_grasping_result(output, "the bandage")

        self.assertEqual(result["selected_object_id"], 4)
        self.assertEqual(result["class_name"], "bandage")
        self.assertEqual(result["mask_query"], "bandage")
        self.assertEqual(result["repair_source"], "target_resolution_direct_target")

    def test_get_prediction_result_passes_max_output_tokens_to_qwen(self):
        fake_client = _FakeClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy",
                    model_name="qwen3.6-flash",
                    max_output_tokens=64,
                )

        self.assertEqual(result["mask"], "mask")
        self.assertEqual(fake_client.chat.completions.kwargs["max_tokens"], 64)

    def test_get_prediction_result_id_repair_retries_invalid_visible_id(self):
        fake_client = _FakeClient(outputs=["[9, red block]", "[3, blue screwdriver]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="id_repair",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["retry_count"], 1)
        self.assertEqual(result["reasoning"]["raw_outputs"], ["[9, red block]", "[3, blue screwdriver]"])
        repair_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("Visible object IDs: 3, 4", repair_text)

    def test_get_prediction_result_id_repair_retries_parse_failure(self):
        fake_client = _FakeClient(outputs=["I cannot determine it.", "[3, blue screwdriver]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="id_repair",
                )

        self.assertEqual(len(fake_client.chat.completions.calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["retry_count"], 1)

    def test_get_prediction_result_id_repair_does_not_retry_valid_visible_id(self):
        fake_client = _FakeClient(outputs=["[3, blue screwdriver]", "[4, red block]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="id_repair",
                )

        self.assertEqual(len(fake_client.chat.completions.calls), 1)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["retry_count"], 0)

    def test_get_prediction_result_hard_review_retries_valid_id_for_hard_subset(self):
        fake_client = _FakeClient(outputs=["[3, blue screwdriver]", "[4, red block]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["red block"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver under the red block",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="hard_review",
                    evaluation_subset="hard_no_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 4)
        self.assertEqual(result["reasoning"]["retry_count"], 1)
        self.assertEqual(result["reasoning"]["retry_reason"], "hard_review")
        review_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("Review the previous answer", review_text)
        self.assertIn("Visible object IDs: 3, 4", review_text)

    def test_get_prediction_result_hard_review_does_not_retry_valid_id_for_easy_subset(self):
        fake_client = _FakeClient(outputs=["[3, blue screwdriver]", "[4, red block]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="hard_review",
                    evaluation_subset="easy_no_ambi",
                )

        self.assertEqual(len(fake_client.chat.completions.calls), 1)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["retry_count"], 0)

    def test_get_prediction_result_target_review_retries_valid_id_for_hard_subset(self):
        fake_client = _FakeClient(outputs=["[3, blue screwdriver]", "[4, red block]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["red block"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver near the red block",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="target_review",
                    evaluation_subset="hard_yes_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 4)
        self.assertEqual(result["reasoning"]["retry_count"], 1)
        self.assertEqual(result["reasoning"]["retry_reason"], "target_review")
        review_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("Re-evaluate the target identity", review_text)
        self.assertIn("Visible object IDs: 3, 4", review_text)

    def test_get_prediction_result_target_review_keeps_initial_valid_id_when_retry_is_invalid(self):
        fake_client = _FakeClient(outputs=["[3, blue screwdriver]", "[9, red block]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                    mimo_retry_mode="target_review",
                    evaluation_subset="hard_no_ambi",
                )

        self.assertEqual(len(fake_client.chat.completions.calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["retry_count"], 1)
        self.assertEqual(result["reasoning"]["retry_discarded"], "invalid_retry_id")

    def test_get_prediction_result_roborefer_json_includes_visible_candidate_table(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"target_parse":{"category":"screwdriver"},'
                    '"candidate_analysis":[{"object_id":3,"target_match":"yes"}],'
                    '"decision":{"object_id":3,"class_name":"blue screwdriver",'
                    '"mask_query":"blue screwdriver","action":"pick_target"}}'
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 5 6 1\n4 7 8 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)) as mocked_mask, \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["blue screwdriver"], [1.0]),
                ) as mocked_predict:
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="roborefer_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=384,
                )

        user_text = fake_client.chat.completions.calls[0]["messages"][1]["content"][0]["text"]
        self.assertIn("Visible object candidates", user_text)
        self.assertIn("id=3, point=(5, 6)", user_text)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["mask_query"], "blue screwdriver")
        mocked_predict.assert_called_once()
        self.assertEqual(mocked_predict.call_args.args[1], "blue screwdriver")
        mocked_mask.assert_called_once()

    def test_get_prediction_result_roborefer_verify_retries_hard_subset(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"target_parse":{"category":"screwdriver"},'
                    '"candidate_analysis":[{"object_id":3,"target_match":"yes"}],'
                    '"decision":{"object_id":3,"class_name":"blue screwdriver",'
                    '"mask_query":"blue screwdriver","action":"pick_target"}}'
                ),
                (
                    '{"target_parse":{"category":"screwdriver"},'
                    '"candidate_analysis":[{"object_id":4,"occlusion_role":"obstructor"}],'
                    '"decision":{"object_id":4,"class_name":"red block",'
                    '"mask_query":"red block","action":"remove_obstructor"}}'
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 5 6 1\n4 7 8 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["red block"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver under the red block",
                    return_metadata=True,
                    prompt_variant="roborefer_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=384,
                    mimo_retry_mode="roborefer_verify",
                    evaluation_subset="hard_yes_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 4)
        self.assertEqual(result["reasoning"]["retry_count"], 1)
        self.assertEqual(result["reasoning"]["retry_reason"], "roborefer_verify")
        verify_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("Verify the previous RoboRefer-style JSON", verify_text)
        self.assertIn("Visible object candidates", verify_text)

    def test_get_prediction_result_first_grasp_verify_reviews_first_grasp_decision(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"requested_target":{"category":"strawberry","target_candidate_id":5},'
                    '"candidate_analysis":[{"object_id":5,"role":"requested_target"}],'
                    '"first_grasp_decision":{"action":"pick_target",'
                    '"first_grasp_object_id":5,"class_name":"red strawberry",'
                    '"mask_query":"red strawberry","role":"requested_target"}}'
                ),
                (
                    '{"requested_target":{"category":"strawberry","target_candidate_id":5},'
                    '"candidate_analysis":[{"object_id":2,"role":"direct_obstructor"},'
                    '{"object_id":5,"role":"requested_target"}],'
                    '"first_grasp_decision":{"action":"remove_obstructor",'
                    '"first_grasp_object_id":2,"class_name":"white box",'
                    '"mask_query":"white box","role":"direct_obstructor"}}'
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n2 2 3 7\n5 5 6 1\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["white box"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="the strawberry under a white box",
                    return_metadata=True,
                    prompt_variant="candidate_grasp_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=512,
                    mimo_retry_mode="first_grasp_verify",
                    evaluation_subset="hard_no_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 2)
        self.assertEqual(result["reasoning"]["mask_query"], "white box")
        self.assertEqual(result["reasoning"]["retry_reason"], "first_grasp_verify")
        verify_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("first visible object to grasp", verify_text)
        self.assertIn("not merely the requested target", verify_text)

    def test_get_prediction_result_v6_verify_preserves_v6_system_prompt(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"target_resolution":{"target_object_id":5,"target_label":"strawberry",'
                    '"target_visibility":"visible_but_blocked"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":true,'
                    '"first_grasp_object_id":5,"first_grasp_label":"red strawberry",'
                    '"mask_query":"red strawberry","decision_rule":"pick_target"}}'
                ),
                (
                    '{"target_resolution":{"target_object_id":5,"target_label":"strawberry",'
                    '"target_visibility":"visible_but_blocked"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":false,'
                    '"blocking_candidates":[{"object_id":2,"label":"box_7","priority":1}],'
                    '"first_grasp_object_id":2,"first_grasp_label":"white box",'
                    '"mask_query":"white box","decision_rule":"remove_direct_blocker"}}'
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n2 2 3 7\n5 5 6 1\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["white box"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="the strawberry under a white box",
                    return_metadata=True,
                    prompt_variant="target_first_grasp_planner_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=1024,
                    mimo_retry_mode="first_grasp_verify",
                    evaluation_subset="hard_no_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 2)
        self.assertEqual(result["reasoning"]["mask_query"], "white box")
        self.assertEqual(result["reasoning"]["retry_reason"], "first_grasp_verify")
        first_prompt = calls[0]["messages"][0]["content"]
        retry_prompt = calls[1]["messages"][0]["content"]
        self.assertIn("target_resolution", first_prompt)
        self.assertIn("target_resolution", retry_prompt)
        verify_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("Previous target-first grasp planner JSON", verify_text)
        self.assertIn("target_object_id equals first_grasp_object_id", verify_text)

    def test_get_prediction_result_v7_uses_planner_consistency_repair(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"target_resolution":{"target_object_id":5,"target_label":"strawberry",'
                    '"target_visibility":"visible_but_blocked"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":true,'
                    '"first_grasp_object_id":5,"first_grasp_label":"red strawberry",'
                    '"mask_query":"red strawberry","decision_rule":"pick_target"}}'
                ),
                (
                    '{"target_resolution":{"target_object_id":5,"target_label":"strawberry",'
                    '"target_visibility":"visible_but_blocked"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":false,'
                    '"blocking_candidates":[{"object_id":2,"label":"box_7","priority":1}],'
                    '"first_grasp_object_id":2,"first_grasp_label":"white box",'
                    '"mask_query":"white box","decision_rule":"remove_direct_blocker"}}'
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n2 2 3 7\n5 5 6 1\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["white box"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="the strawberry under a white box",
                    return_metadata=True,
                    prompt_variant="target_first_grasp_planner_v7_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=1024,
                    mimo_retry_mode="planner_consistency_repair",
                    evaluation_subset="hard_no_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 2)
        self.assertEqual(result["reasoning"]["retry_reason"], "planner_consistency_repair")
        self.assertIn("planner consistency repair", calls[1]["messages"][1]["content"][0]["text"])
        self.assertIn("target_visibility is blocked", calls[1]["messages"][1]["content"][0]["text"])
        self.assertIn("target_first_grasp_planner_v7_json", calls[1]["messages"][1]["content"][0]["text"])

    def test_get_prediction_result_v8_uses_geometry_consistency_repair(self):
        fake_client = _FakeClient(
            outputs=[
                (
                    '{"target_resolution":{"target_object_id":4,"target_label":"orange",'
                    '"target_visibility":"free_visible"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":true,'
                    '"first_grasp_object_id":4,"first_grasp_label":"orange",'
                    '"mask_query":"orange fruit","decision_rule":"pick_target"}}'
                ),
                (
                    '{"target_resolution":{"target_object_id":5,"target_label":"orange",'
                    '"target_visibility":"visible_but_blocked"},'
                    '"first_grasp_planning":{"should_grasp_target_directly":false,'
                    '"blocking_candidates":[{"object_id":5,"label":"orange","priority":1}],'
                    '"first_grasp_object_id":5,"first_grasp_label":"orange",'
                    '"mask_query":"orange fruit","decision_rule":"pick_target"}}'
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n4 670 964 1\n5 677 341 3\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(self.utils, "get_goal_mask_with_index", return_value=("mask", 0)), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["orange"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="the orange nearest to the image bottom",
                    return_metadata=True,
                    prompt_variant="target_first_grasp_geometry_v8_json",
                    model_name="mimo-v2.5",
                    max_output_tokens=1024,
                    mimo_retry_mode="geometry_consistency_repair",
                    evaluation_subset="hard_yes_ambi",
                )

        calls = fake_client.chat.completions.calls
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["reasoning"]["selected_object_id"], 5)
        self.assertEqual(result["reasoning"]["retry_reason"], "geometry_consistency_repair")
        repair_text = calls[1]["messages"][1]["content"][0]["text"]
        self.assertIn("geometry consistency repair", repair_text)
        self.assertIn("bottom-edge rank", repair_text)
        self.assertIn("same-category instance confusion", repair_text)
        self.assertIn("target_first_grasp_geometry_v8_json", repair_text)

    def test_get_prediction_result_baseline_does_not_retry_invalid_visible_id(self):
        fake_client = _FakeClient(outputs=["[9, red block]", "[3, blue screwdriver]"])

        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text("id x y gt\n3 0 0 1\n4 1 1 2\n")

            with patch.object(self.utils, "client", fake_client), \
                patch.object(self.utils, "load_image_as_base64", return_value="image-bytes"), \
                patch.object(
                    self.utils.langsam_actor,
                    "predict",
                    return_value=(["mask"], [_FakeBox()], ["red block"], [1.0]),
                ):
                result = self.utils.get_prediction_result(
                    image=object(),
                    path=scene_dir,
                    scene_number=10,
                    text="blue screwdriver",
                    return_metadata=True,
                    prompt_variant="legacy_old",
                    model_name="mimo-v2.5",
                    max_output_tokens=713,
                )

        self.assertEqual(len(fake_client.chat.completions.calls), 1)
        self.assertEqual(result["reasoning"]["retry_count"], 0)

    def test_point_retry_mask_selection_prefers_smaller_mask_containing_molmo_point(self):
        huge = _FakeMask(np.ones((5, 5), dtype=np.uint8))
        focused = _FakeMask(
            [
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0],
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0],
            ]
        )

        selected, index = self.utils.get_goal_mask_with_index(
            [huge, focused],
            (2, 2),
            prefer_small_containing=True,
            max_area_ratio=0.80,
        )

        self.assertIs(selected, focused)
        self.assertEqual(index, 1)

    def test_short_langsam_query_candidates_keep_original_then_shortened_name(self):
        candidates = self.utils.get_langsam_query_candidates("small white box under the screwdriver")

        self.assertEqual(candidates[0], "small white box under the screwdriver")
        self.assertIn("small white box", candidates)


if __name__ == "__main__":
    unittest.main()
