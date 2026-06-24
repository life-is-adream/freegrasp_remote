import json
import tempfile
import unittest
from pathlib import Path

from calculate_SR import calculate_accuracy, calculate_reasoning_accuracy


class RsrMetricsTest(unittest.TestCase):
    def test_calculates_ssr_and_rsr_from_result_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "out_subset.json"
            output_path.write_text(
                json.dumps(
                    [
                        [1, 1, "a", 1, 0],
                        [2, 1, "b", 0, 1],
                        [3, 1, "c", 1, 1],
                    ]
                )
            )

            self.assertEqual(calculate_accuracy(output_path), 2 / 3)
            self.assertEqual(calculate_reasoning_accuracy(output_path), 2 / 3)


if __name__ == "__main__":
    unittest.main()
