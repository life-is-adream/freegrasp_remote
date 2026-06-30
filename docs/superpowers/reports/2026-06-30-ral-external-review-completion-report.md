# RA-L External Review Revision Completion Report

Date: 2026-06-30

## One-Sentence Paper Argument

For free-form language-conditioned grasping in cluttered synthetic scenes, the
paper positions EGHC3_v3 as a deployable no-GT evidence-gated hierarchical
consensus routing method, supported by frozen 900-sample RSR/SSR comparisons
against S0 and bounded by an oracle diagnostic upper bound.

## Completion Status

| Task | Status | Evidence |
|---|---|---|
| Task 1: external-review triage | Complete | `docs/superpowers/reports/2026-06-30-ral-external-review-triage.md`; commits `4a2c339` and `b4b54ea`. |
| Task 2: deterministic call-budget accounting | Complete | `scripts/summarize_call_budget.py`, `data/output/statistics/ral_call_budget_summary.md`, `data/output/statistics/ral_call_budget_summary.csv`; commits `a4c51d0`, `112b6a1`, `55f97ee`, plus the final negative-call-count guard added in this pass. |
| Task 3: S0 budget-control feasibility | Complete as read-only feasibility check | No paid run was launched. Existing code does not contain a pure S0 two-call vote policy; adding it would touch the currently dirty evaluation path and should be done in a separate, explicit experiment pass. |
| Final verification and state summary | Complete | This report records the final no-paid verification commands and remaining boundaries. |

## Call-Budget Evidence Freeze

The current regenerated call-budget table is:

| Run | N | RSR | SSR | Reasoning calls | Router calls | Repair calls | Reasoning calls/sample | Total recorded calls/sample |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 900 | 57.89 | 47.56 | 900 | 0 | 0 | 1.00 | 1.00 |
| EGHC3_v3_qwen35_full | 900 | 60.89 | 55.22 | 1889 | 900 | 59 | 2.10 | 3.16 |

Interpretation boundary: these are recorded call counts from
`full_protocol_summary.json`, not wall-clock latency or monetary cost estimates.

## Final Verification

All verification below was run without MiMo, Qwen, Molmo regeneration, or paid
inference.

| Check | Result |
|---|---|
| Syntax | Passed: `python -m py_compile scripts/summarize_call_budget.py evaluate_all.py`. |
| Unit tests | Passed: `python -m unittest test_summarize_call_budget test_evaluate_all_summary test_reasoning_resume test_evaluate_mimo_full_protocol test_evaluate_entrypoints` (`34` tests). |
| Call-budget regeneration | Passed: regenerated `data/output/statistics/ral_call_budget_summary.md` and `.csv` with unchanged S0/EGHC values. |
| Fail-closed validation | Passed: missing, non-integral, boolean, and negative call-count fields are rejected. |
| LaTeX compile | Passed: `pdflatex -interaction=nonstopmode main.tex` twice in `paper/`, producing `paper/main.pdf`. |

## Final Fix Added In This Pass

The call-budget script previously rejected missing, boolean, and non-integral
fields but still accepted negative call counts. This pass adds a regression test
(`test_summarize_call_budget.py`) and updates `call_count()` so negative
`reasoning_calls`, `router_calls`, or `repair_calls` fail closed.

## Current Workspace Boundary

The repository is intentionally not fully clean. The following files were
already dirty in the evaluation/debugging lane and should not be mixed into the
call-budget/report commits without a separate review:

| Path | Current role |
|---|---|
| `evaluate_all.py` | Contains subset/max-row debug plumbing; this pass only restored the explicit `subset_names = [...]` assignment so entrypoint tests can still audit the fixed six-subset order. |
| `evaluate_common.py` | Existing evaluation/resume/debugging lane changes. |
| `reasoning_eval.py` | Existing evaluation/resume/debugging lane changes. |
| `test_reasoning_resume.py` | Existing tests for the evaluation/resume/debugging lane. |
| `models/langsam/GroundingDINO` | Existing submodule dirty marker. |

## Recommended Next Step

Do not start paid S0 budget-control inference from this mixed worktree. First
isolate or commit the evaluation/debugging lane, then add a tested
`original_protocol_budget2_vote` policy in a dedicated pass and launch only
split 0 after explicit approval.

