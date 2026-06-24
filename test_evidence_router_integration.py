import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from PIL import Image

import test_utils_output_limit as support


class EvidenceRouterIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support._install_import_stubs()
        sys.modules.pop("utils.utils", None)
        cls.utils = importlib.import_module("utils.utils")

    @staticmethod
    def _canonical_overlap_geometry():
        return {
            "source": "predicted_sam_point_masks",
            "candidates": {
                3: {
                    "point": (0, 0),
                    "bbox": (0, 0, 2, 2),
                    "center": (1, 1),
                    "area": 9,
                },
                4: {
                    "point": (1, 1),
                    "bbox": (1, 1, 3, 3),
                    "center": (2, 2),
                    "area": 9,
                },
            },
            "relations": [
                {
                    "object_a_id": 3,
                    "object_b_id": 4,
                    "relation": "overlaps",
                    "bbox_overlap_smaller": 4 / 9,
                    "bbox_a_coverage": 4 / 9,
                    "bbox_b_coverage": 4 / 9,
                    "mask_iou": 0.2,
                    "a_contains_b_point": True,
                    "b_contains_a_point": True,
                    "a_image_position_from_b": "upper_left",
                    "b_image_position_from_a": "lower_right",
                    "duplicate_mask_suspect": False,
                }
            ],
        }

    def _run_prediction(
        self,
        router_output,
        reasoning_output=None,
        protocol_ablation="full",
        route_guard_variant="none",
        parsed_rows=None,
        predicted_geometry=None,
        frozen_route_assessment=None,
    ):
        outputs = [router_output]
        if reasoning_output is not None:
            outputs.append(reasoning_output)
        fake_client = support._FakeClient(outputs=outputs)
        evidence = {
            "source": "predicted_sam_point_masks",
            "candidates": {
                3: {"point": (0, 0), "bbox": (0, 0, 1, 1), "area": 4},
                4: {"point": (1, 1), "bbox": (1, 1, 2, 2), "area": 4},
            },
            "relations": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_dir = Path(tmpdir)
            (scene_dir / "10_id.txt").write_text(
                "id x y gt\n"
                + (
                    parsed_rows
                    or "3 0 0 101\n4 1 1 102\n"
                )
            )
            with patch.object(self.utils, "client", fake_client), patch.object(
                self.utils,
                "load_image_as_base64",
                return_value="image-bytes",
            ), patch.object(
                self.utils,
                "predict_geometry_from_molmo_points",
                return_value=predicted_geometry or evidence,
            ), patch.object(
                self.utils,
                "_load_semantic_labels_for_candidates",
                side_effect=AssertionError("GT semantic loader called"),
            ), patch.object(
                self.utils,
                "_load_geometry_features_for_candidates",
                side_effect=AssertionError("GT geometry loader called"),
            ), patch.object(
                self.utils.langsam_actor,
                "predict",
                return_value=(
                    [np.ones((2, 2), dtype=np.uint8)],
                    [support._FakeBox()],
                    ["red block"],
                    [1.0],
                ),
            ):
                result = self.utils.get_prediction_result(
                    image=np.zeros((2, 2, 3), dtype=np.uint8),
                    path=scene_dir,
                    scene_number=10,
                    text="red block",
                    return_metadata=True,
                    model_name="mimo-v2.5",
                    max_output_tokens=1024,
                    routing_variant="predicted_geometry",
                    feature_source="predicted",
                    protocol_ablation=protocol_ablation,
                    route_guard_variant=route_guard_variant,
                    frozen_route_assessment=frozen_route_assessment,
                )
        return result, fake_client.chat.completions.calls

    def test_frozen_blocker_route_bypasses_router_call(self):
        reasoning_output = json.dumps(
            {
                "target_resolution": {"target_object_id": 3},
                "first_grasp_planning": {
                    "first_grasp_object_id": 4,
                    "first_grasp_label": "blue block",
                    "mask_query": "blue block",
                },
            }
        )
        frozen = {
            "route_mode": "blocker_first",
            "route_confidence": 0.95,
            "target_object_id": 3,
            "target_label": "red block",
            "ambiguity_evidence": [],
            "blocker_evidence": ["predicted overlap with object 4"],
            "pre_guard_route_mode": "direct",
            "route_guard_applied": True,
            "route_guard_reasons": ["predicted_target_overlap"],
            "route_guard_variant": "overlap_blocker_v1",
        }
        result, calls = self._run_prediction(
            reasoning_output,
            frozen_route_assessment=frozen,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["reasoning"]["route_mode"], "blocker_first")
        self.assertEqual(result["reasoning"]["router_call_count"], 0)
        self.assertTrue(result["reasoning"]["frozen_route_used"])
        self.assertIn("blocker-first", calls[0]["messages"][0]["content"].lower())

    def test_guarded_direct_still_uses_one_model_call(self):
        router_output = json.dumps(
            {
                "route_mode": "direct",
                "route_confidence": 0.95,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": [],
                "blocker_evidence": [],
            }
        )
        result, calls = self._run_prediction(
            router_output,
            route_guard_variant="conservative_v1",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["reasoning"]["pre_guard_route_mode"], "direct")
        self.assertEqual(result["reasoning"]["route_mode"], "direct")

    def test_risky_direct_dispatches_target_first(self):
        router_output = json.dumps(
            {
                "route_mode": "direct",
                "route_confidence": 0.95,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": [],
                "blocker_evidence": [],
            }
        )
        reasoning_output = json.dumps(
            {
                "target_resolution": {"target_object_id": 3},
                "first_grasp_planning": {
                    "first_grasp_object_id": 3,
                    "first_grasp_label": "red block",
                    "mask_query": "red block",
                },
            }
        )
        result, calls = self._run_prediction(
            router_output,
            reasoning_output,
            route_guard_variant="conservative_v1",
            predicted_geometry={
                **{
                    "source": "predicted_sam_point_masks",
                    "candidates": {
                        3: {
                            "point": (0, 0),
                            "bbox": (0, 0, 1, 1),
                            "area": 4,
                            "center": (0, 0),
                        },
                        4: {
                            "point": (1, 1),
                            "bbox": (0, 0, 2, 2),
                            "area": 9,
                            "center": (1, 1),
                        },
                    },
                },
                "relations": [
                    {
                        "source_id": 3,
                        "target_id": 4,
                        "relation": "overlaps",
                        "overlap": 0.2,
                        "vertical_order": "above",
                    }
                ],
            },
        )
        self.assertEqual(result["reasoning"]["pre_guard_route_mode"], "direct")
        self.assertEqual(result["reasoning"]["route_mode"], "target_first")
        self.assertIn(
            "predicted_target_overlap",
            result["reasoning"]["route_guard_reasons"],
        )
        self.assertIn("target-first", calls[1]["messages"][0]["content"].lower())

    def test_target_packet_reaches_main_and_repair_prompts(self):
        router_output = json.dumps(
            {
                "route_mode": "direct",
                "route_confidence": 0.95,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": [],
                "blocker_evidence": [],
            }
        )
        reasoning_output = json.dumps(
            {
                "target_resolution": {"target_object_id": 3},
                "first_grasp_planning": {
                    "first_grasp_object_id": 3,
                    "first_grasp_label": "red block",
                    "mask_query": "red block",
                },
            }
        )

        try:
            result, calls = self._run_prediction(
                router_output,
                reasoning_output,
                route_guard_variant="target_evidence_v2",
                predicted_geometry=self._canonical_overlap_geometry(),
            )
        except ValueError as error:
            self.fail(str(error))

        main_text = calls[1]["messages"][1]["content"][0]["text"]
        repair_text = calls[2]["messages"][1]["content"][0]["text"]
        self.assertIn("Router target hypothesis", main_text)
        self.assertIn(
            "id=4, included_by=target_coverage",
            main_text,
        )
        self.assertIn("Router target hypothesis", repair_text)
        self.assertNotIn("vertical_order", main_text)
        self.assertEqual(
            result["reasoning"]["target_evidence_packet"]["target_id"],
            3,
        )

    def test_frozen_target_route_rebuilds_packet_without_router_call(self):
        reasoning_output = json.dumps(
            {
                "target_resolution": {"target_object_id": 3},
                "first_grasp_planning": {
                    "first_grasp_object_id": 4,
                    "first_grasp_label": "blue block",
                    "mask_query": "blue block",
                },
            }
        )
        frozen = {
            "route_mode": "target_first",
            "route_confidence": 0.95,
            "target_object_id": 3,
            "target_label": "red block",
            "ambiguity_evidence": [],
            "blocker_evidence": [],
            "pre_guard_route_mode": "direct",
            "route_guard_applied": True,
            "route_guard_reasons": ["target_risk_present"],
            "route_guard_variant": "target_evidence_v2",
        }

        result, calls = self._run_prediction(
            reasoning_output,
            frozen_route_assessment=frozen,
            predicted_geometry=self._canonical_overlap_geometry(),
        )

        self.assertEqual(result["reasoning"]["router_call_count"], 0)
        self.assertTrue(result["reasoning"]["frozen_route_used"])
        self.assertIn(
            "target_evidence_packet",
            result["reasoning"],
        )
        self.assertEqual(
            result["reasoning"]["target_evidence_packet"]["target_id"],
            3,
        )
        self.assertIn(
            "Router target hypothesis",
            calls[0]["messages"][1]["content"][0]["text"],
        )

    def test_predicted_router_rejects_oracle_features(self):
        with self.assertRaisesRegex(ValueError, "oracle_feature"):
            self.utils.get_prediction_result(
                image=object(),
                path="unused",
                scene_number=1,
                text="target",
                routing_variant="predicted_geometry",
                feature_source="oracle_feature",
            )

    def test_router_direct_path_uses_one_model_call_without_gt_loaders(self):
        router_output = json.dumps(
            {
                "route_mode": "direct",
                "route_confidence": 0.95,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": [],
                "blocker_evidence": [],
            }
        )

        result, calls = self._run_prediction(router_output)

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["route_mode"], "direct")
        self.assertEqual(result["reasoning"]["feature_source"], "predicted")

    def test_router_target_first_dispatches_specialized_second_call(self):
        router_output = json.dumps(
            {
                "route_mode": "target_first",
                "route_confidence": 0.75,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": ["same class"],
                "blocker_evidence": [],
            }
        )
        reasoning_output = json.dumps(
            {
                "target_resolution": {
                    "target_object_id": 3,
                    "target_label": "red block",
                    "target_visibility": "free_visible",
                },
                "first_grasp_planning": {
                    "should_grasp_target_directly": True,
                    "blocking_candidates": [],
                    "first_grasp_object_id": 3,
                    "first_grasp_label": "red block",
                    "mask_query": "red block",
                    "decision_rule": "pick_target",
                },
            }
        )

        result, calls = self._run_prediction(router_output, reasoning_output)

        self.assertEqual(len(calls), 3)
        self.assertEqual(result["reasoning"]["selected_object_id"], 3)
        self.assertEqual(result["reasoning"]["route_mode"], "target_first")
        self.assertIn(
            "target-first",
            calls[1]["messages"][0]["content"].lower(),
        )
        self.assertIn(
            "geometry",
            calls[2]["messages"][1]["content"][0]["text"].lower(),
        )

    def test_no_blocker_ablation_maps_blocker_route_to_target_first(self):
        router_output = json.dumps(
            {
                "route_mode": "blocker_first",
                "route_confidence": 0.8,
                "target_object_id": 3,
                "target_label": "red block",
                "ambiguity_evidence": [],
                "blocker_evidence": ["overlap"],
            }
        )
        reasoning_output = json.dumps(
            {
                "target_resolution": {"target_object_id": 3},
                "first_grasp_planning": {
                    "first_grasp_object_id": 3,
                    "first_grasp_label": "red block",
                    "mask_query": "red block",
                },
            }
        )

        result, calls = self._run_prediction(
            router_output,
            reasoning_output,
            protocol_ablation="no_blocker_first",
        )

        self.assertEqual(result["reasoning"]["route_mode"], "target_first")
        self.assertEqual(
            result["reasoning"]["pre_ablation_route_mode"],
            "blocker_first",
        )
        self.assertIn("target-first", calls[1]["messages"][0]["content"].lower())

    def test_automatic_retry_policy_is_single_factor_ablatable(self):
        choose = self.utils._automatic_retry_mode
        self.assertEqual(choose("target_first", "full"), "geometry_consistency_repair")
        self.assertEqual(choose("blocker_first", "full"), "id_repair")
        self.assertEqual(choose("target_first", "no_geometry_repair"), "id_repair")
        self.assertEqual(choose("blocker_first", "no_id_repair"), "none")

    def test_process_dataset_forwards_routing_to_prediction(self):
        reasoning_eval = importlib.import_module("reasoning_eval")
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
        frame = pd.DataFrame(
            [
                {
                    "sceneId": 303,
                    "queryObjId": 0,
                    "annotation": "pick the block",
                    "groundTruthObjIds": "0",
                    "image": {"bytes": buffer.getvalue()},
                }
            ]
        )
        prediction = {
            "mask": np.ones((2, 2), dtype=np.uint8),
            "reasoning": {"selected_object_id": 1, "selected_gt_id": 1},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            npz_dir = root / "npz"
            molmo_dir = root / "molmo"
            npz_dir.mkdir()
            molmo_dir.mkdir()
            np.savez(
                npz_dir / "303.npz",
                instances_objects=np.ones((1, 2, 2), dtype=np.uint8),
            )
            with patch.object(
                reasoning_eval,
                "get_prediction_result",
                return_value=prediction,
            ) as mocked_prediction:
                reasoning_eval.process_dataset(
                    frame,
                    npz_dir,
                    molmo_dir,
                    root / "out.json",
                    routing_variant="predicted_geometry",
                    feature_source="predicted",
                )

        kwargs = mocked_prediction.call_args.kwargs
        self.assertEqual(kwargs["routing_variant"], "predicted_geometry")
        self.assertEqual(kwargs["feature_source"], "predicted")


if __name__ == "__main__":
    unittest.main()
