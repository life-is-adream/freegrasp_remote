import unittest

import run_ablation_matrix as matrix


class AblationMatrixTest(unittest.TestCase):
    def test_registry_contains_predeclared_stages(self):
        specs = matrix.experiment_registry()
        self.assertEqual(
            [spec.run_id for spec in specs if spec.stage == 1],
            [f"S{index}" for index in range(8)],
        )
        self.assertEqual(
            [spec.run_id for spec in specs if spec.stage == 2],
            [f"F{index}" for index in range(4)],
        )
        by_id = {spec.run_id: spec for spec in specs}
        self.assertEqual(by_id["S0"].subset_policy, "original_protocol")
        self.assertEqual(by_id["S0"].segmentation_variant, "baseline")
        self.assertEqual(by_id["S1"].feature_source, "oracle_feature")
        self.assertEqual(by_id["F2"].feature_source, "oracle_feature")
        self.assertEqual(by_id["S4"].routing_variant, "predicted_geometry")
        self.assertEqual(by_id["F1"].routing_variant, "predicted_geometry")
        self.assertIsNotNone(by_id["F3"].replay_source)
        self.assertTrue(by_id["F0"].fresh_molmo)
        self.assertEqual(by_id["F0"].subset_policy, "original_protocol")
        self.assertFalse(by_id["F1"].fresh_molmo)
        self.assertFalse(by_id["F2"].fresh_molmo)

    def test_replay_command_has_no_reasoning_entrypoint(self):
        spec = next(
            item for item in matrix.experiment_registry() if item.run_id == "F3"
        )
        command = matrix.command_for(spec, "runs/F3", "cache-sha")
        self.assertIn("replay_segmentation.py", command)
        self.assertNotIn("evaluate_mimo", command)

    def test_execution_requires_literal_confirmation(self):
        with self.assertRaisesRegex(ValueError, "RUN_PAID_INFERENCE"):
            matrix.validate_execution_gate(True, "yes")


if __name__ == "__main__":
    unittest.main()
