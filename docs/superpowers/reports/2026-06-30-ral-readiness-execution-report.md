# RA-L Readiness Execution Report

Date: 2026-06-30

## Scope Executed

This pass completed the approved A/B/C readiness flow:

1. Manuscript polishing for claim strength and RA-L readability.
2. Integrity-oriented claim audit for baseline, oracle, no-GT, and statistical
   interpretation risks.
3. Git/package grouping so paper deliverables stay separate from Qwen debugging
   changes.

Qwen3.7-plus debugging, paid inference reruns, Molmo cache changes, and model
inference code edits were treated as out of scope.

## Manuscript Changes

| Area | Change |
|---|---|
| Abstract | Marked original FreeGrasp GPT-4o comparison as descriptive and added paired CI for controlled S0 deltas. |
| Introduction | Added controlled S0 RSR/SSR deltas, bootstrap-aware RSR caution, and descriptive wording for the original FreeGrasp comparison. |
| Experiments | Separated reported baseline, controlled S0 baseline, main EGHC3_v3 result, S1 oracle headroom, failure taxonomy, and bootstrap uncertainty. |
| Experiments tables | Shortened table labels to avoid severe IEEE column overflow. |
| Conclusion | Reordered evidence around the controlled S0 comparison, stated stronger SSR support, and kept real-robot claims bounded. |
| Revision design | Updated statistical verification from pending to completed and replaced stale CI checklist text. |

## Integrity Audit Results

| Risk | Current status |
|---|---|
| Original FreeGrasp GPT-4o is unpaired | Labeled as reported/descriptive in abstract, introduction, experiments, and reports. |
| S0 comparison is controlled | Described as same 900 rows and reused Molmo cache. |
| S1 may be mistaken for deployable | Labeled as oracle diagnostic/headroom only. |
| RSR gain may be overstated | Text now states RSR is positive but more cautious because CI lower bound is 0.00 pp. |
| SSR gain needs emphasis | Text now treats SSR as the stronger controlled empirical gain. |
| Hard-scene performance is low | Framed as remaining blocker/visibility bottleneck, not solved occlusion reasoning. |
| Real-robot success overclaim | Text states RSR/SSR are benchmark reasoning and mask metrics, not full real-robot execution. |

## Verification Results

| Check | Result |
|---|---|
| Python syntax check | Passed: `python -m py_compile scripts/paired_bootstrap_ci.py`. |
| Bootstrap reproduction | Passed: 20k scene-clustered bootstrap reproduced all four manuscript deltas and intervals. |
| LaTeX compile | Passed: `pdflatex` ran successfully twice and generated `paper/main.pdf`. |
| Sensitive-term scan | Passed after manual review of current paper/reports/specs; risky terms are bounded by surrounding text. |
| Plan placeholder self-check | Passed after skipping fenced command blocks. |
| Stale-placeholder scan | Passed after this report was updated; no stale placeholders or obsolete CI markers remain in the current paper/readiness docs. |

## Git Grouping

### Paper-readiness group

These files belong in the paper-readiness commit:

- `paper/main.tex`
- `paper/sections/introduction.tex`
- `paper/sections/experiments.tex`
- `paper/sections/conclusion.tex`
- `docs/superpowers/specs/2026-06-29-eghc3-ral-paper-revision-design.md`
- `docs/superpowers/reports/2026-06-30-ral-internal-review-memo.md`
- `docs/superpowers/reports/2026-06-30-ral-pre-review.md`
- `docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md`
- `scripts/paired_bootstrap_ci.py`

### Already committed readiness docs

- `docs/superpowers/specs/2026-06-30-ral-submission-readiness-design.md`
- `docs/superpowers/plans/2026-06-30-ral-submission-readiness.md`

### Qwen/debugging group, not part of paper-readiness commit

- `evaluate_all.py`
- `evaluate_common.py`
- `reasoning_eval.py`
- `test_reasoning_resume.py`
- `models/langsam/GroundingDINO`

These files should be committed separately only if the Qwen debugging track is
resumed and verified.

## Remaining Risks For External Review

1. Absolute hard-scene performance remains low, so the contribution should stay
   framed as an improved decision contract and evidence audit, not solved
   occlusion reasoning.
2. The original FreeGrasp GPT-4o comparison is useful but descriptive because
   row-level original predictions are unavailable.
3. Reviewers may ask whether the extra call count is worth the gain; the paper
   should answer this as an auditability and SSR-consistency benefit, not only
   raw RSR.
4. Real-robot execution evidence is absent; keep all physical-execution claims
   as future work.

## External Review Hand-Off

Recommended files to send to Gemini/GLM5.2:

1. `paper/main.pdf`
2. `docs/superpowers/reports/2026-06-30-ral-internal-review-memo.md`
3. `docs/superpowers/reports/2026-06-30-ral-pre-review.md`
4. `docs/superpowers/reports/2026-06-30-ral-readiness-execution-report.md`

Ask the reviewers to return blocking issues first, then minor writing issues,
then suggested table/figure changes.
