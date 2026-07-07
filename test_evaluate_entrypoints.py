import ast
import pathlib
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent


EXPECTED_SUBSETS = {
    "evaluate1.py": "easy_no_ambi",
    "evaluate2.py": "easy_yes_ambi",
    "evaluate3.py": "medium_no_ambi",
    "evaluate4.py": "medium_yes_ambi",
    "evaluate5.py": "hard_no_ambi",
    "evaluate6.py": "hard_yes_ambi",
}


def get_subset_name(script_path: pathlib.Path) -> str | None:
    tree = ast.parse(script_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "subset_name":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    return None


class EvaluateEntrypointsTest(unittest.TestCase):
    def test_subset_entrypoints_exist_and_pin_expected_subset(self) -> None:
        for filename, expected_subset in EXPECTED_SUBSETS.items():
            script_path = PROJECT_ROOT / filename
            self.assertTrue(script_path.exists(), f"{filename} should exist")
            self.assertEqual(get_subset_name(script_path), expected_subset)

    def test_evaluate_all_exists_and_lists_all_subsets_in_order(self) -> None:
        script_path = PROJECT_ROOT / "evaluate_all.py"
        self.assertTrue(script_path.exists(), "evaluate_all.py should exist")

        tree = ast.parse(script_path.read_text())
        subset_values = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "subset_names":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    subset_values.append(elt.value)

        self.assertEqual(subset_values, list(EXPECTED_SUBSETS.values()))

    def test_evaluate_all_exposes_controlled_ablation_arguments(self) -> None:
        tree = ast.parse((PROJECT_ROOT / "evaluate_all.py").read_text())
        string_constants = {
            node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        evaluate_pipeline = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evaluate_pipeline"
        )
        pipeline_args = {arg.arg for arg in evaluate_pipeline.args.args}

        self.assertIn("--model-name", string_constants)
        self.assertIn("--prompt-variant", string_constants)
        self.assertIn("legacy_old", string_constants)
        self.assertIn("--reuse-molmo", string_constants)
        self.assertIn("--regenerate-molmo", string_constants)
        self.assertIn("--resume", string_constants)
        self.assertIn("--run-dir", string_constants)
        self.assertIn("--max-output-tokens", string_constants)
        self.assertIn("--mimo-retry-mode", string_constants)
        self.assertIn("--segmentation-variant", string_constants)
        self.assertIn("--subset-policy", string_constants)
        self.assertIn("direct_target", string_constants)
        self.assertIn("hard_occlusion", string_constants)
        self.assertIn("hard_review", string_constants)
        self.assertIn("observed_best_v1", string_constants)
        self.assertIn("easy_direct_v1", string_constants)
        self.assertIn("easy_direct_hard_occlusion_v1", string_constants)
        self.assertIn("best_known_v1", string_constants)
        self.assertIn("target_first_grasp_planner_json", string_constants)
        self.assertIn("target_first_grasp_planner_v6", string_constants)
        self.assertIn("target_first_grasp_planner_v7_json", string_constants)
        self.assertIn("target_first_grasp_planner_v7", string_constants)
        self.assertIn("planner_consistency_repair", string_constants)
        self.assertIn("target_first_grasp_geometry_v8_json", string_constants)
        self.assertIn("target_first_grasp_geometry_v8", string_constants)
        self.assertIn("target_first_evidence_gate_v9_json", string_constants)
        self.assertIn("target_first_evidence_gate_v9", string_constants)
        self.assertIn("hard_blocker_first_v10_json", string_constants)
        self.assertIn("hard_blocker_first_v10", string_constants)
        self.assertIn("geometry_consistency_repair", string_constants)
        self.assertIn("model_name", pipeline_args)
        self.assertIn("prompt_variant", pipeline_args)
        self.assertIn("reuse_molmo", pipeline_args)
        self.assertIn("resume", pipeline_args)
        self.assertIn("run_dir", pipeline_args)
        self.assertIn("max_output_tokens", pipeline_args)
        self.assertIn("mimo_retry_mode", pipeline_args)
        self.assertIn("segmentation_variant", pipeline_args)
        self.assertIn("subset_policy", pipeline_args)

    def test_evaluate_all_defaults_to_reusing_molmo_cache(self) -> None:
        tree = ast.parse((PROJECT_ROOT / "evaluate_all.py").read_text())
        parse_args = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "parse_args")

        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "set_defaults"
                and any(
                    keyword.arg == "reuse_molmo"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                )
                for node in ast.walk(parse_args)
            ),
            "evaluate_all.py should reuse data/output/molmo_output unless --regenerate-molmo is explicit",
        )

    def test_no_verifier_ablation_is_exposed_end_to_end(self) -> None:
        evaluate_all_tree = ast.parse((PROJECT_ROOT / "evaluate_all.py").read_text())
        full_protocol_tree = ast.parse((PROJECT_ROOT / "evaluate_mimo_full_protocol.py").read_text())
        utils_tree = ast.parse((PROJECT_ROOT / "utils" / "utils.py").read_text())

        evaluate_all_strings = {
            node.value
            for node in ast.walk(evaluate_all_tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        full_protocol_strings = {
            node.value
            for node in ast.walk(full_protocol_tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        utils_strings = {
            node.value
            for node in ast.walk(utils_tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

        self.assertIn("eghc_consensus_no_verifier_v1", evaluate_all_strings)
        self.assertIn("eghc_consensus_no_verifier_v1", full_protocol_strings)
        self.assertIn("no_verifier", utils_strings)
        self.assertIn("skipped_no_verifier_ablation", utils_strings)


if __name__ == "__main__":
    unittest.main()
