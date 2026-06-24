import unittest

import pandas as pd

from run_conservative_pilot import group_samples, select_rows


class ConservativePilotRunnerTest(unittest.TestCase):
    def test_group_and_select_rows_follow_frozen_indices(self):
        manifest = {
            "samples": [
                {"split": "0", "subset": "easy_no_ambi", "row_index": 1},
                {"split": "0", "subset": "easy_no_ambi", "row_index": 3},
            ]
        }
        grouped = group_samples(manifest)
        frame = pd.DataFrame({"value": [10, 11, 12, 13, 14]})
        selected = select_rows(frame, grouped[("0", "easy_no_ambi")])
        self.assertEqual(selected["value"].tolist(), [11, 13])

    def test_select_rows_rejects_out_of_range_index(self):
        frame = pd.DataFrame({"value": [10]})
        with self.assertRaisesRegex(ValueError, "out of range"):
            select_rows(frame, [2])


if __name__ == "__main__":
    unittest.main()
