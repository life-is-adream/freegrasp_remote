import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_call_budget import summarize_run


class SummarizeCallBudgetTest(unittest.TestCase):
    def _base_summary(self):
        return {
            "overall": {"n": 1, "rsr": 1.0, "ssr": 1.0},
            "reasoning_calls": 1,
            "router_calls": 0,
            "repair_calls": 0,
        }

    def _write_summary(self, summary):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name)
        (run_dir / "full_protocol_summary.json").write_text(json.dumps(summary))
        return run_dir

    def test_negative_call_counts_are_rejected(self):
        for field in ("reasoning_calls", "router_calls", "repair_calls"):
            with self.subTest(field=field):
                summary = self._base_summary()
                summary[field] = -1

                with self.assertRaisesRegex(ValueError, "negative call-count"):
                    summarize_run(self._write_summary(summary))

    def test_missing_call_counts_are_rejected(self):
        for field in ("reasoning_calls", "router_calls", "repair_calls"):
            with self.subTest(field=field):
                summary = self._base_summary()
                del summary[field]

                with self.assertRaisesRegex(ValueError, f"missing call-count field: {field}"):
                    summarize_run(self._write_summary(summary))

    def test_malformed_call_counts_are_rejected(self):
        cases = {
            "reasoning_calls": 1.9,
            "router_calls": True,
            "repair_calls": "1.5",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                summary = self._base_summary()
                summary[field] = value

                with self.assertRaisesRegex(ValueError, f"invalid call-count field {field}"):
                    summarize_run(self._write_summary(summary))

    def test_missing_metric_fields_are_rejected(self):
        for field in ("n", "rsr", "ssr"):
            with self.subTest(field=field):
                summary = self._base_summary()
                del summary["overall"][field]

                with self.assertRaisesRegex(ValueError, f"missing metric field: {field}"):
                    summarize_run(self._write_summary(summary))

    def test_malformed_n_is_rejected(self):
        summary = self._base_summary()
        summary["overall"]["n"] = False

        with self.assertRaisesRegex(ValueError, "invalid metric field n"):
            summarize_run(self._write_summary(summary))


if __name__ == "__main__":
    unittest.main()
