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
| Task 2: deterministic call-budget accounting | Complete | `scripts/summarize_call_budget.py`, `data/output/statistics/ral_call_budget_summary.md`, `data/output/statistics/ral_call_budget_summary.csv`; commits `a4c51d0`, `112b6a1`, `55f97ee`, `2380663`, plus follow-up regression coverage for all fail-closed cases. |
| Task 3: S0 budget-control feasibility | Complete as read-only feasibility check | No paid run was launched. Existing code does not contain a pure S0 two-call vote policy; the evaluation/debug plumbing is now committed in `4d24674`, so the budget-control policy should be implemented in a separate, explicit experiment pass. |
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
| Syntax | Passed: `.venv/bin/python -m py_compile scripts/summarize_call_budget.py evaluate_all.py evaluate_common.py reasoning_eval.py test_evidence_router_entrypoints.py test_reasoning_resume.py test_summarize_call_budget.py`. |
| Unit tests | Passed: `.venv/bin/python -m unittest test_summarize_call_budget test_evaluate_all_summary test_reasoning_resume test_evaluate_mimo_full_protocol test_evaluate_entrypoints test_evidence_router_entrypoints` (`48` tests). |
| Call-budget regeneration | Passed: regenerated `data/output/statistics/ral_call_budget_summary.md` and `.csv` with unchanged S0/EGHC values. |
| Fail-closed validation | Passed: missing, non-integral, boolean, and negative call-count fields are rejected. |
| LaTeX compile | Passed: `pdflatex -interaction=nonstopmode main.tex` twice in `paper/`, producing `paper/main.pdf`. |

## Final Fix Added In This Pass

The call-budget script now rejects missing, boolean, non-integral, and negative
call-count fields. This pass expands `test_summarize_call_budget.py` so those
manual validation cases are protected by repeatable regression tests, including
missing metric fields and malformed `n` values.

## Current Workspace Boundary

The evaluation/debugging lane has been committed in `4d24674`, and the working
tree should be clean after this report/test cleanup is committed. The following
paths are now reviewed as part of that committed lane, but they should still not
be mixed with the future S0 budget-control policy implementation:

| Path | Current role |
|---|---|
| `evaluate_all.py` | Contains subset/max-row debug plumbing and Molmo reuse summary metadata. |
| `evaluate_common.py` | Checks or regenerates Molmo only for selected rows, including debug subsets. |
| `reasoning_eval.py` | Uses normalized resume keys and records prediction errors instead of crashing. |
| `test_reasoning_resume.py` | Covers resume/error-recording behavior. |
| `test_evidence_router_entrypoints.py` | Covers selected-row Molmo cache checks. |

## Recommended Next Step

Do not start paid S0 budget-control inference until the policy itself exists
and passes a no-inference smoke test. The next dedicated pass should add a
tested `original_protocol_budget2_vote` policy, verify it on a tiny dry run, and
launch split 0 only after explicit approval.
