import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate_all
import evaluate_mimo
import evaluate_mimo_full_protocol


class EvidenceRouterEntrypointsTest(unittest.TestCase):
    def test_automatic_policy_is_identical_for_every_benchmark_subset(self):
        configs = []
        for subset_name in [
            "easy_no_ambi",
            "easy_yes_ambi",
            "medium_no_ambi",
            "medium_yes_ambi",
            "hard_no_ambi",
            "hard_yes_ambi",
        ]:
            configs.append(
                evaluate_all._subset_config(
                    subset_name,
                    prompt_variant="legacy",
                    mimo_retry_mode="none",
                    segmentation_variant="point_retry",
                    subset_policy="automatic_evidence_v1",
                )
            )

        self.assertTrue(all(config == configs[0] for config in configs))
        self.assertEqual(configs[0]["routing_variant"], "predicted_geometry")
        self.assertEqual(configs[0]["feature_source"], "predicted")
        self.assertFalse(configs[0]["uses_benchmark_difficulty"])
        self.assertFalse(configs[0]["uses_gt_features"])

    def test_automatic_policy_preserves_declared_ablation_inputs(self):
        count_only = evaluate_all._subset_config(
            "hard_yes_ambi",
            prompt_variant="legacy",
            mimo_retry_mode="none",
            segmentation_variant="geometric_consistency",
            subset_policy="automatic_no_geometry_repair",
            routing_variant="count_only",
            feature_source="none",
        )

        self.assertEqual(count_only["routing_variant"], "count_only")
        self.assertEqual(
            count_only["segmentation_variant"],
            "geometric_consistency",
        )
        self.assertEqual(
            count_only["protocol_ablation"],
            "no_geometry_repair",
        )

    def test_original_protocol_has_no_boosts_or_oracle_features(self):
        config = evaluate_all._subset_config(
            "hard_yes_ambi",
            prompt_variant="legacy",
            mimo_retry_mode="id_repair",
            segmentation_variant="point_retry",
            subset_policy="original_protocol",
        )

        self.assertEqual(config["prompt_variant"], "legacy_old")
        self.assertEqual(config["mimo_retry_mode"], "none")
        self.assertEqual(config["segmentation_variant"], "baseline")
        self.assertFalse(config["uses_gt_features"])

    def test_mimo_cli_accepts_automatic_routing_options(self):
        args = evaluate_mimo.parse_args(
            [
                "--subset-policy",
                "automatic_evidence_v1",
                "--routing-variant",
                "predicted_geometry",
                "--feature-source",
                "predicted",
                "--route-guard-variant",
                "conservative_v1",
            ]
        )

        self.assertEqual(args.subset_policy, "automatic_evidence_v1")
        self.assertEqual(args.routing_variant, "predicted_geometry")
        self.assertEqual(args.feature_source, "predicted")
        self.assertEqual(args.route_guard_variant, "conservative_v1")

    def test_evaluate_pipeline_forwards_automatic_routing_to_every_subset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            calls = []
            evaluate_common_stub = types.ModuleType("evaluate_common")
            evaluate_common_stub.MOLMO_OUTPUT_DIR = str(root / "molmo")

            def fake_evaluate_subset(subset_name, **kwargs):
                calls.append((subset_name, kwargs))
                return {"rsr": 0.0, "ssr": 0.0}

            evaluate_common_stub.evaluate_subset = fake_evaluate_subset
            with patch.dict(sys.modules, {"evaluate_common": evaluate_common_stub}):
                evaluate_all.evaluate_pipeline(
                    model_name="mimo-v2.5",
                    max_output_tokens=1024,
                    subset_policy="automatic_evidence_v1",
                    reuse_molmo=True,
                    resume=False,
                    run_dir=str(root / "run"),
                    route_guard_variant="conservative_v1",
                )

        self.assertEqual(len(calls), 6)
        for _subset_name, kwargs in calls:
            self.assertEqual(kwargs["routing_variant"], "predicted_geometry")
            self.assertEqual(kwargs["feature_source"], "predicted")
            self.assertEqual(kwargs["route_guard_variant"], "conservative_v1")

    def test_evaluate_subset_forwards_routing_to_process_dataset(self):
        calls = []

        molmo_eval_stub = types.ModuleType("molmo_eval")
        molmo_eval_stub.batch_process_molmo = lambda *args, **kwargs: None
        reasoning_eval_stub = types.ModuleType("reasoning_eval")
        reasoning_eval_stub.process_dataset = lambda *args, **kwargs: None
        with patch.dict(
            sys.modules,
            {
                "molmo_eval": molmo_eval_stub,
                "reasoning_eval": reasoning_eval_stub,
            },
        ):
            sys.modules.pop("evaluate_common", None)
            evaluate_common = importlib.import_module("evaluate_common")

        def fake_process_dataset(*args, **kwargs):
            calls.append((args, kwargs))

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            evaluate_common,
            "load_dataset",
            return_value=object(),
        ), patch.object(
            evaluate_common,
            "prepare_subset",
            return_value=[object()],
        ), patch.object(
            evaluate_common,
            "ensure_molmo_cache_exists",
        ), patch.object(
            evaluate_common,
            "process_dataset",
            side_effect=fake_process_dataset,
        ), patch.object(
            evaluate_common,
            "calculate_accuracy",
            return_value=0.0,
        ), patch.object(
            evaluate_common,
            "calculate_reasoning_accuracy",
            return_value=0.0,
        ):
            evaluate_common.evaluate_subset(
                "easy_no_ambi",
                output_dir=tmpdir,
                prepare_molmo=False,
                routing_variant="predicted_geometry",
                feature_source="predicted",
                route_guard_variant="conservative_v1",
            )

        self.assertEqual(calls[0][1]["routing_variant"], "predicted_geometry")
        self.assertEqual(calls[0][1]["feature_source"], "predicted")
        self.assertEqual(calls[0][1]["route_guard_variant"], "conservative_v1")

    def test_evaluate_subset_checks_only_selected_rows_for_reused_molmo(self):
        checked = []
        processed = []

        molmo_eval_stub = types.ModuleType("molmo_eval")
        molmo_eval_stub.batch_process_molmo = lambda *args, **kwargs: None
        reasoning_eval_stub = types.ModuleType("reasoning_eval")
        reasoning_eval_stub.process_dataset = lambda *args, **kwargs: processed.append(args)
        with patch.dict(
            sys.modules,
            {
                "molmo_eval": molmo_eval_stub,
                "reasoning_eval": reasoning_eval_stub,
            },
        ):
            sys.modules.pop("evaluate_common", None)
            evaluate_common = importlib.import_module("evaluate_common")

        class FakeSubset:
            def __init__(self, rows):
                self.rows = list(rows)

            def __len__(self):
                return len(self.rows)

            def head(self, n):
                return FakeSubset(self.rows[:n])

        full_df = FakeSubset(["scene_a", "scene_b", "scene_c"])
        selected_df = FakeSubset(["scene_a", "scene_b"])

        def fake_ensure(df, _molmo_dir):
            checked.append(df.rows)

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            evaluate_common,
            "load_dataset",
            return_value=full_df,
        ), patch.object(
            evaluate_common,
            "prepare_subset",
            return_value=selected_df,
        ), patch.object(
            evaluate_common,
            "ensure_molmo_cache_exists",
            side_effect=fake_ensure,
        ), patch.object(
            evaluate_common,
            "process_dataset",
            side_effect=lambda *args, **kwargs: processed.append(args),
        ), patch.object(
            evaluate_common,
            "calculate_accuracy",
            return_value=0.0,
        ), patch.object(
            evaluate_common,
            "calculate_reasoning_accuracy",
            return_value=0.0,
        ):
            evaluate_common.evaluate_subset(
                "easy_no_ambi",
                output_dir=tmpdir,
                prepare_molmo=False,
                max_rows=1,
            )

        self.assertEqual(checked, [["scene_a"]])
        self.assertEqual(processed[0][0].rows, ["scene_a"])

    def test_mimo_pipeline_forwards_routing_to_evaluate_all(self):
        forwarded = []
        fake_client = types.SimpleNamespace(base_url="https://example.invalid")

        def fake_evaluate_pipeline(**kwargs):
            forwarded.append(kwargs)
            return {}

        with patch.dict(
            sys.modules,
            {"evaluate_all": evaluate_all},
        ), patch.object(
            evaluate_mimo,
            "create_mimo_client",
            return_value=fake_client,
        ), patch.object(
            evaluate_mimo,
            "patch_freegrasp_client",
        ), patch.object(
            evaluate_mimo,
            "validate_mimo_supports_image_input",
        ), patch.object(
            evaluate_all,
            "evaluate_pipeline",
            side_effect=fake_evaluate_pipeline,
        ):
            evaluate_mimo.evaluate_mimo_pipeline(
                mimo_preflight=False,
                routing_variant="predicted_geometry",
                feature_source="predicted",
                route_guard_variant="conservative_v1",
            )

        self.assertEqual(forwarded[0]["routing_variant"], "predicted_geometry")
        self.assertEqual(forwarded[0]["feature_source"], "predicted")
        self.assertEqual(forwarded[0]["route_guard_variant"], "conservative_v1")

    def test_full_protocol_cli_accepts_routing_options(self):
        args = evaluate_mimo_full_protocol.parse_args(
            [
                "--subset-policy",
                "automatic_evidence_v1",
                "--routing-variant",
                "predicted_geometry",
                "--feature-source",
                "predicted",
                "--route-guard-variant",
                "conservative_v1",
            ]
        )

        self.assertEqual(args.routing_variant, "predicted_geometry")
        self.assertEqual(args.feature_source, "predicted")
        self.assertEqual(args.route_guard_variant, "conservative_v1")

    def test_mimo_clis_accept_target_evidence_v2(self):
        mimo_args = evaluate_mimo.parse_args(
            [
                "--route-guard-variant",
                "target_evidence_v2",
            ]
        )
        full_args = evaluate_mimo_full_protocol.parse_args(
            [
                "--route-guard-variant",
                "target_evidence_v2",
            ]
        )

        self.assertEqual(
            mimo_args.route_guard_variant,
            "target_evidence_v2",
        )
        self.assertEqual(
            full_args.route_guard_variant,
            "target_evidence_v2",
        )


if __name__ == "__main__":
    unittest.main()
