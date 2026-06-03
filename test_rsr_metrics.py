import unittest

from calculate_SR import calculate_reasoning_accuracy
from rsr_metrics import is_reasoning_success


class RSRMetricsTest(unittest.TestCase):
    def test_reasoning_succeeds_when_selected_molmo_id_maps_to_gt_object(self) -> None:
        molmo_to_gt_map = {1: 4, 2: 8}

        self.assertTrue(is_reasoning_success(2, molmo_to_gt_map, [8]))

    def test_reasoning_fails_when_selected_molmo_id_maps_to_wrong_object(self) -> None:
        molmo_to_gt_map = {1: 4, 2: 8}

        self.assertFalse(is_reasoning_success(1, molmo_to_gt_map, [8]))

    def test_reasoning_accuracy_reads_optional_fifth_result_column(self) -> None:
        results = [
            [0, 1, "target", 1, 1],
            [1, 2, "target", 1, 0],
            [2, 3, "target", 0, 1],
        ]

        self.assertEqual(calculate_reasoning_accuracy(results), 2 / 3)


if __name__ == "__main__":
    unittest.main()
