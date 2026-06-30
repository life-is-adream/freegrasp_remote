import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_call_budget import summarize_run


class SummarizeCallBudgetTest(unittest.TestCase):
    def _write_summary(self, summary):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run_dir = Path(tmp.name)
        (run_dir / "full_protocol_summary.json").write_text(json.dumps(summary))
        return run_dir

    def test_negative_call_counts_are_rejected(self):
        base_summary = {
            "overall": {"n": 1, "rsr": 1.0, "ssr": 1.0},
            "reasoning_calls": 1,
            "router_calls": 0,
            "repair_calls": 0,
        }

        for field in ("reasoning_calls", "router_calls", "repair_calls"):
            with self.subTest(field=field):
                summary = json.loads(json.dumps(base_summary))
                summary[field] = -1

                with self.assertRaisesRegex(ValueError, "negative call-count"):
                    summarize_run(self._write_summary(summary))


if __name__ == "__main__":
    unittest.main()
