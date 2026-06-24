## FreeGrasp Agent Templates

This directory stores reusable prompt templates for working with Codex on this
repository.

Use them by opening a file, copying the prompt, and pasting it into a Codex
chat along with your concrete command, script, plan, or question.

Templates:

- `01-project-scout.md`: map the repo before making changes
- `02-experiment-designer.md`: design ablations and evaluation plans
- `03-cost-cache-guardian.md`: check cost, cache, API, and rerun risk
- `04-results-auditor.md`: compare runs and analyze regressions
- `05-regression-test-guardian.md`: choose the smallest useful test coverage

FreeGrasp-specific reminders:

- `data/output/molmo_output/` is a valuable cache; do not clear it casually.
- `evaluate_all.py`, `evaluate.py`, `evaluate_mimo.py`, `run.py`, and
  `test_qwen_api.py` can trigger heavy compute or real API calls.
- Prefer `--reuse-molmo` and `--resume` unless you explicitly need a fresh run.
- Start with lightweight tests such as
  `python -m unittest test_evaluate_entrypoints.py test_rsr_metrics.py`.
