import unittest
from collections import Counter

from select_router_pilot import DEFAULT_SUBSETS, select_pilot_rows


class RouterPilotSelectionTest(unittest.TestCase):
    def test_selection_is_balanced_and_deterministic(self):
        rows = []
        for subset in DEFAULT_SUBSETS:
            for index in range(25):
                rows.append(
                    {
                        "subset": subset,
                        "sample_key": ["0", subset, index, index, 1, "a"],
                    }
                )
        first = select_pilot_rows(rows, per_subset=20, seed=20260624)
        second = select_pilot_rows(rows, per_subset=20, seed=20260624)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 120)
        self.assertEqual(
            Counter(row["subset"] for row in first),
            Counter({subset: 20 for subset in DEFAULT_SUBSETS}),
        )

    def test_selection_rejects_duplicate_keys(self):
        row = {
            "subset": "easy_no_ambi",
            "sample_key": ["0", "easy_no_ambi", 0, 1, 1, "a"],
        }
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            select_pilot_rows([row, dict(row)], per_subset=1, seed=1)


if __name__ == "__main__":
    unittest.main()
