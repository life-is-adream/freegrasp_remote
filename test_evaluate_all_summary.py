import contextlib
import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


class EvaluateAllSummaryTest(unittest.TestCase):
    def test_evaluate_pipeline_prints_rsr_ssr_summary(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.78, "ssr": 0.50},
            "easy_yes_ambi": {"rsr": 0.66, "ssr": 0.56},
            "medium_no_ambi": {"rsr": 0.42, "ssr": 0.34},
            "medium_yes_ambi": {"rsr": 0.44, "ssr": 0.28},
            "hard_no_ambi": {"rsr": 0.30, "ssr": 0.24},
            "hard_yes_ambi": {"rsr": 0.20, "ssr": 0.16},
        }

        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = []

        def fake_evaluate_subset(subset_name, **kwargs):
            calls.append((subset_name, kwargs))
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                scores = evaluate_all.evaluate_pipeline(
                    model_name="qwen3.6-flash",
                    prompt_variant="legacy",
                    reuse_molmo=True,
                    resume=True,
                    run_dir=run_dir,
                    max_output_tokens=64,
                    mimo_retry_mode="id_repair",
                    segmentation_variant="point_retry",
                )

            self.assertEqual(scores, subset_scores)
            self.assertEqual(calls[0][1]["model_name"], "qwen3.6-flash")
            self.assertEqual(calls[0][1]["prompt_variant"], "legacy")
            self.assertEqual(calls[0][1]["max_output_tokens"], 64)
            self.assertEqual(calls[0][1]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls[0][1]["segmentation_variant"], "point_retry")
            self.assertFalse(calls[0][1]["prepare_molmo"])
            self.assertTrue(calls[0][1]["resume"])
            self.assertEqual(calls[0][1]["output_dir"], run_dir)
            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["max_output_tokens"], 64)
            self.assertEqual(summary["mimo_retry_mode"], "id_repair")
            self.assertEqual(summary["segmentation_variant"], "point_retry")
            output = stdout.getvalue()
        self.assertIn("easy_no_ambi", output)
        self.assertIn("RSR 78.00% | SSR 50.00%", output)
        self.assertIn("hard_yes_ambi", output)
        self.assertIn("RSR 20.00% | SSR 16.00%", output)

    def test_observed_best_subset_policy_overrides_only_hard_no_to_baseline(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                prompt_variant="legacy_old",
                max_output_tokens=713,
                mimo_retry_mode="hard_review",
                segmentation_variant="point_retry",
                subset_policy="observed_best_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "none")
            self.assertEqual(calls["hard_no_ambi"]["segmentation_variant"], "baseline")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_yes_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["segmentation_variant"], "point_retry")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "observed_best_v1")
            self.assertEqual(summary["subset_configs"]["hard_no_ambi"]["segmentation_variant"], "baseline")

    def test_easy_direct_subset_policy_uses_direct_prompt_only_for_easy_subsets(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                prompt_variant="legacy_old",
                max_output_tokens=713,
                subset_policy="easy_direct_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=Path(tmpdir),
            )

        self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
        self.assertEqual(calls["easy_yes_ambi"]["prompt_variant"], "direct_target")
        self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "legacy_old")
        self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "legacy_old")

    def test_easy_direct_hard_occlusion_policy_targets_hard_subsets_only(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                prompt_variant="legacy_old",
                max_output_tokens=713,
                subset_policy="easy_direct_hard_occlusion_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_yes_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "hard_occlusion")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_no_ambi"]["segmentation_variant"], "baseline")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "hard_occlusion")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_yes_ambi"]["segmentation_variant"], "point_retry")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "easy_direct_hard_occlusion_v1")
            self.assertEqual(summary["subset_configs"]["hard_yes_ambi"]["prompt_variant"], "hard_occlusion")

    def test_best_known_policy_combines_best_observed_subset_configs(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                prompt_variant="legacy_old",
                max_output_tokens=713,
                subset_policy="best_known_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["easy_no_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "hard_review")
            self.assertEqual(calls["hard_no_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_yes_ambi"]["segmentation_variant"], "point_retry")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "best_known_v1")
            self.assertEqual(summary["subset_configs"]["hard_no_ambi"]["mimo_retry_mode"], "hard_review")

    def test_best_known_v2_policy_reviews_hard_subsets_without_changing_easy_medium(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                prompt_variant="legacy_old",
                max_output_tokens=713,
                subset_policy="best_known_v2",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "target_review")
            self.assertEqual(calls["hard_no_ambi"]["segmentation_variant"], "point_retry")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "legacy_old")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "target_review")
            self.assertEqual(calls["hard_yes_ambi"]["segmentation_variant"], "point_retry")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "best_known_v2")
            self.assertEqual(summary["subset_configs"]["hard_yes_ambi"]["mimo_retry_mode"], "target_review")

    def test_roborefer_policy_enables_structured_prompt_for_medium_and_hard(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=384,
                subset_policy="roborefer_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "roborefer_json")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "roborefer_json")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "roborefer_verify")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "roborefer_json")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "roborefer_verify")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "roborefer_v1")
            self.assertEqual(summary["subset_configs"]["hard_yes_ambi"]["prompt_variant"], "roborefer_json")

    def test_light_review_policy_uses_visible_id_guard_and_target_review(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=384,
                subset_policy="light_review_v1",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "visible_id_guard")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_yes_ambi"]["prompt_variant"], "visible_id_guard")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "visible_id_guard")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "target_review")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "visible_id_guard")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "target_review")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "light_review_v1")
            self.assertEqual(summary["subset_configs"]["medium_no_ambi"]["prompt_variant"], "visible_id_guard")
            self.assertEqual(summary["subset_configs"]["hard_yes_ambi"]["mimo_retry_mode"], "target_review")

    def test_candidate_grasp_policy_uses_first_grasp_json_for_medium_and_hard(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=512,
                subset_policy="candidate_grasp_v2",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "candidate_grasp_json")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["medium_yes_ambi"]["prompt_variant"], "candidate_grasp_json")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "candidate_grasp_json")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "candidate_grasp_json")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "first_grasp_verify")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "candidate_grasp_v2")
            self.assertEqual(summary["subset_configs"]["medium_no_ambi"]["prompt_variant"], "candidate_grasp_json")
            self.assertEqual(summary["subset_configs"]["hard_yes_ambi"]["mimo_retry_mode"], "first_grasp_verify")

    def test_candidate_grasp_fewshot_policy_uses_fewshot_json_for_medium_and_hard(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=1024,
                subset_policy="candidate_grasp_fewshot_v3",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "candidate_grasp_fewshot_json")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["medium_yes_ambi"]["prompt_variant"], "candidate_grasp_fewshot_json")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "candidate_grasp_fewshot_json")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "candidate_grasp_fewshot_json")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "first_grasp_verify")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "candidate_grasp_fewshot_v3")
            self.assertEqual(
                summary["subset_configs"]["hard_yes_ambi"]["prompt_variant"],
                "candidate_grasp_fewshot_json",
            )

    def test_candidate_grasp_spatial_policy_uses_spatial_json_for_medium_and_hard(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=1024,
                subset_policy="candidate_grasp_spatial_v4",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "candidate_grasp_spatial_json")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["medium_yes_ambi"]["prompt_variant"], "candidate_grasp_spatial_json")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "candidate_grasp_spatial_json")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "candidate_grasp_spatial_json")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "first_grasp_verify")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "candidate_grasp_spatial_v4")
            self.assertEqual(
                summary["subset_configs"]["hard_yes_ambi"]["prompt_variant"],
                "candidate_grasp_spatial_json",
            )

    def test_candidate_grasp_semantic_policy_uses_semantic_json_for_medium_and_hard(self) -> None:
        subset_scores = {
            "easy_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "easy_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "medium_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_no_ambi": {"rsr": 0.1, "ssr": 0.1},
            "hard_yes_ambi": {"rsr": 0.1, "ssr": 0.1},
        }
        evaluate_common_stub = types.ModuleType("evaluate_common")
        calls = {}

        def fake_evaluate_subset(subset_name, **kwargs):
            calls[subset_name] = kwargs
            return subset_scores[subset_name]

        evaluate_common_stub.evaluate_subset = fake_evaluate_subset
        evaluate_common_stub.MOLMO_OUTPUT_DIR = "data/output/molmo_output"
        sys.modules["evaluate_common"] = evaluate_common_stub
        sys.modules.pop("evaluate_all", None)
        evaluate_all = importlib.import_module("evaluate_all")

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            evaluate_all.evaluate_pipeline(
                model_name="mimo-v2.5",
                max_output_tokens=1024,
                subset_policy="candidate_grasp_semantic_v5",
                reuse_molmo=True,
                resume=False,
                run_dir=run_dir,
            )

            self.assertEqual(calls["easy_no_ambi"]["prompt_variant"], "direct_target")
            self.assertEqual(calls["easy_no_ambi"]["mimo_retry_mode"], "id_repair")
            self.assertEqual(calls["medium_no_ambi"]["prompt_variant"], "candidate_grasp_semantic_json")
            self.assertEqual(calls["medium_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["medium_yes_ambi"]["prompt_variant"], "candidate_grasp_semantic_json")
            self.assertEqual(calls["hard_no_ambi"]["prompt_variant"], "candidate_grasp_semantic_json")
            self.assertEqual(calls["hard_no_ambi"]["mimo_retry_mode"], "first_grasp_verify")
            self.assertEqual(calls["hard_yes_ambi"]["prompt_variant"], "candidate_grasp_semantic_json")
            self.assertEqual(calls["hard_yes_ambi"]["mimo_retry_mode"], "first_grasp_verify")

            summary = json.loads((run_dir / "summary.json").read_text())
            self.assertEqual(summary["subset_policy"], "candidate_grasp_semantic_v5")
            self.assertEqual(
                summary["subset_configs"]["hard_yes_ambi"]["prompt_variant"],
                "candidate_grasp_semantic_json",
            )


if __name__ == "__main__":
    unittest.main()
