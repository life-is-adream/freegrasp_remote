import tempfile
import unittest
from pathlib import Path

import summarize_ablation_matrix as summary


class AblationSummaryTest(unittest.TestCase):
    @staticmethod
    def _detail(split, subset, row_index, *, rsr):
        return {
            "split": split,
            "subset": subset,
            "row_index": row_index,
            "scene_id": 7,
            "object_id": 2,
            "annotation": "the cup",
            "rsr_correct": rsr,
        }

    def test_complete_key_keeps_repeated_semantic_samples_distinct(self):
        first = [
            self._detail("0", "easy_no_ambi", 0, rsr=0),
            self._detail("1", "easy_no_ambi", 0, rsr=0),
        ]
        second = [
            self._detail("0", "easy_no_ambi", 0, rsr=1),
            self._detail("1", "easy_no_ambi", 0, rsr=1),
        ]

        paired = summary.pair_by_sample_key(first, second)

        self.assertEqual(len(paired), 2)

    def test_pairing_rejects_duplicate_complete_keys(self):
        row = self._detail("0", "easy_no_ambi", 0, rsr=0)
        with self.assertRaisesRegex(ValueError, "Duplicate sample key"):
            summary.pair_by_sample_key([row, dict(row)], [row])

    def test_load_detail_rows_adds_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "split_2"
            path.mkdir()
            (path / "details_hard_yes_ambi.json").write_text(
                '[{"scene_id": 7, "object_id": 2, "annotation": "the cup"}]'
            )

            rows = summary.load_detail_rows(tmpdir)

        self.assertEqual(rows[0]["split"], "2")
        self.assertEqual(rows[0]["subset"], "hard_yes_ambi")
        self.assertEqual(rows[0]["row_index"], 0)

    def test_pairing_rejects_mismatched_sample_keys(self):
        first = [
            {
                "split": "0",
                "subset": "easy_no_ambi",
                "row_index": 0,
                "scene_id": 1,
                "object_id": 1,
                "annotation": "a",
                "rsr_correct": 0,
            }
        ]
        second = [
            {
                "split": "0",
                "subset": "easy_no_ambi",
                "row_index": 0,
                "scene_id": 2,
                "object_id": 1,
                "annotation": "a",
                "rsr_correct": 1,
            }
        ]
        with self.assertRaisesRegex(ValueError, "sample keys"):
            summary.pair_by_sample_key(first, second)

    def test_clustered_delta_resamples_scenes(self):
        first = [
            {"split": "0", "subset": "easy_no_ambi", "row_index": 0, "scene_id": 1, "object_id": 1, "annotation": "a", "rsr_correct": 0},
            {"split": "0", "subset": "easy_no_ambi", "row_index": 1, "scene_id": 1, "object_id": 2, "annotation": "b", "rsr_correct": 0},
            {"split": "0", "subset": "easy_no_ambi", "row_index": 2, "scene_id": 2, "object_id": 1, "annotation": "c", "rsr_correct": 1},
        ]
        second = [
            {"split": "0", "subset": "easy_no_ambi", "row_index": 0, "scene_id": 1, "object_id": 1, "annotation": "a", "rsr_correct": 1},
            {"split": "0", "subset": "easy_no_ambi", "row_index": 1, "scene_id": 1, "object_id": 2, "annotation": "b", "rsr_correct": 1},
            {"split": "0", "subset": "easy_no_ambi", "row_index": 2, "scene_id": 2, "object_id": 1, "annotation": "c", "rsr_correct": 0},
        ]
        result = summary.clustered_delta_ci(
            first,
            second,
            "rsr_correct",
            seed=4,
            draws=200,
        )
        self.assertEqual(result["cluster_unit"], "scene_id")
        self.assertEqual(result["n_scenes"], 2)
        self.assertEqual(result["n_rows"], 3)

    def test_failure_categories_cover_required_modes(self):
        rows = [
            {"rsr_correct": 1, "ssr_correct": 0, "failure_reason": "iou_below_threshold"},
            {"rsr_correct": 0, "ssr_correct": 0, "failure_reason": "invalid_id"},
            {"rsr_correct": 0, "ssr_correct": 0, "error": "API timeout"},
        ]
        counts = summary.failure_categories(rows)
        self.assertEqual(counts["rsr_only_segmentation_error"], 1)
        self.assertEqual(counts["invalid_id"], 1)
        self.assertEqual(counts["api_error"], 1)

    def test_latex_labels_reported_and_oracle_rows(self):
        rows = [
            {"method": "FreeGrasp + GPT-4o", "rsr": 0.8, "ssr": 0.7, "status": "reported"},
            {"method": "S1", "rsr": 0.7, "ssr": 0.6, "status": "oracle_feature"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "table.tex"
            summary.export_latex(rows, path)
            content = path.read_text()
        self.assertIn("(reported)", content)
        self.assertIn("(oracle feature)", content)
        self.assertIn("80.00", content)

    def test_export_writes_all_paper_table_fragments(self):
        tables = {
            name: [{"method": "S0", "rsr": 0.6, "ssr": 0.5, "status": "controlled"}]
            for name in (
                "main_results",
                "routing_ablation",
                "reasoning_ablation",
                "segmentation_ablation",
            )
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            summary.export_paper_tables(tables, tmpdir)
            files = {path.name for path in Path(tmpdir).iterdir()}
        for name in tables:
            self.assertIn(f"{name}.csv", files)
            self.assertIn(f"{name}.tex", files)


if __name__ == "__main__":
    unittest.main()
