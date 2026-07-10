# FreeGrasp RA-L Daily Progress Report

Date: 2026-07-10 (Friday)

Current week: Week 4 / early Week 5 transition (2026-07-06 to 2026-07-12)

Current focus: post-main-experiment closeout, manuscript/package readiness, and
real-validation decision.

---

## 1. Executive Status

The project has moved beyond the 2026-07-04 master plan's immediate closeout
items. T4, T5, T6, T10, T11, and the first T12 local package audit now have
paper-facing artifacts. The main remaining blocker is T7: no UR5 or real-image
validation artifact exists yet, so the manuscript must still avoid real-robot
success claims.

Current headline:

- Main method remains frozen as EGHC3_v3.
- Main result remains 900 samples, RSR 60.89%, SSR 55.22%.
- Strongest controlled claim remains the +7.67 pp SSR gain over S0.
- RSR remains a cautious +3.00 pp gain because the bootstrap lower bound reaches
  0.00 pp.
- The current PDF is 6 pages and passes the local anonymous package audit.

---

## 2. Verified Checks Run Today

### Failure-outcome audit

Command:

```bash
python scripts/audit_failure_outcomes.py \
  --details-root data/output/ablation_matrix/EGHC3_v3_qwen35_full \
  --expect-total 900 \
  --expect-non-joint 431
```

Result:

| Difficulty | N | Joint success | RSR-only | SSR-only | Both-fail | Non-joint-success |
|---|---:|---:|---:|---:|---:|---:|
| Easy | 300 | 224 | 40 | 10 | 26 | 76 |
| Medium | 300 | 169 | 16 | 10 | 105 | 131 |
| Hard | 300 | 76 | 23 | 8 | 193 | 224 |
| **Overall** | **900** | **469** | **79** | **28** | **324** | **431** |

Status: passed. Total rows and non-joint-success denominator match expectations.

### Submission package audit

Command:

```bash
python scripts/audit_submission_package.py --root .
```

Result:

- 22 cited keys and 22 bibliography items.
- Missing citations: none.
- Uncited bibliography items: none.
- Main PDF metadata: no bad fields, no XMP metadata, no Type 3 fonts.
- Figure PDFs: no bad fields, no XMP metadata, no Type 3 fonts.
- Main PDF text scan: no unexpected identity hits.
- Source scan: no absolute-path, repo/URL, email, or API-key-like hits in the
  checked manuscript/package sources.

Status: `AUDIT_OK`.

### PDF status

Current `paper/main.pdf`:

- Pages: 6.
- File size: 222586 bytes.
- Creation time: 2026-07-07 14:16 CST.
- Fonts: embedded; no Type 3 fonts observed in the checked font listing.

---

## 3. Updated Task Board

| Task | Deadline | Status on 2026-07-10 | Evidence / note |
|---|---:|---|---|
| T1 Story line | 2026-06-21 | Complete | EGHC framing is fixed. |
| T2 RA-L outline | 2026-06-24 | Complete in practice | LaTeX five-section draft exists. |
| T3 Experiment protocol | 2026-06-28 | Frozen in practice | EGHC3_v3 provenance and no-GT boundary fixed. |
| T4 Main experiment closeout | 2026-07-05 | Complete with reconstructed provenance | `paper/results_main_table.md`; `paper/main_experiment_provenance_run_log.md`. Raw console `run_log.txt` was absent and should not be invented. |
| T5 Ablations | 2026-07-19 | Complete for current paper package | `paper/ablation_table.md`; includes budget-2, no consensus, no mask repair, no verifier, and S1 split-0 oracle row. |
| T6 Failure analysis | 2026-07-26 | Complete for current paper package | `paper/failure_analysis.md`; `scripts/audit_failure_outcomes.py` validates metric-mode denominator. |
| T7 UR5 / real-image validation | 2026-08-09 | Not started / blocking | No `paper/real_validation.md`, no video directory, no validation media found. |
| T8 Figures | 2026-08-12 | Strong draft | Figures exist and pass local metadata/font audit; readability still needs final human check. |
| T9 English RA-L draft | 2026-08-16 | Strong draft | `paper/main.pdf` compiles to 6 pages; claim boundary mostly aligned. |
| T10 Citation and claim audit | 2026-08-20 | First pass complete; metadata polish substantially advanced | `paper/citation_claim_audit.md`; citation scan reports 22/22, no missing or uncited keys. |
| T11 Internal review | 2026-08-23 | Complete first pass + no-verifier re-review | `paper/internal_review_report.md`. |
| T12 Double-blind/package check | 2026-08-30 | Local audit passes current draft; final package not frozen | `paper/double_blind_package_check.md`; `scripts/audit_submission_package.py --root .` returns `AUDIT_OK`. |
| T13 Final submission | 2026-09-03 | Not started | Blocked by T7 decision and final freeze. |

---

## 4. Go/No-Go Status

| Gate | Date | Status | Current decision |
|---|---:|---|---|
| Go 1: main experiment | 2026-07-05 | Passed with caveat | Data, split integrity, results table, and reconstructed provenance exist. Raw console log is absent. |
| Go 2: core ablations | 2026-07-19 | Passed early for current claims | Paper-facing ablation table exists; no paid experiment needed before T7. |
| Go 3: real validation | 2026-08-09 | Open / current blocker | Must choose UR5 or real-image offline validation. |
| Go 4: draft and page budget | 2026-08-20 | On track | Current PDF is 6 pages. |
| Go 5: double-blind package | 2026-08-30 | Partially on track | Local audit passes, but final source/video/readme package is not frozen. |

---

## 5. Manuscript Evidence Now In Place

### Main experimental evidence

- `paper/results_main_table.md`
- `paper/main_experiment_provenance_run_log.md`
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json`
- `data/output/statistics/eghc3_bootstrap_ci.*`

### Ablation and cost evidence

- `paper/ablation_table.md`
- `paper/no_verifier_ablation_run_log.md`
- `docs/experiments/2026-07-01-original-protocol-budget2-vote-split0.md`
- `docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md`
- `docs/experiments/2026-07-02-eghc-routing-ablation-split0.md`
- `data/output/statistics/ral_ablation_call_budget_with_routing.*`

### Failure and submission evidence

- `paper/failure_analysis.md`
- `scripts/audit_failure_outcomes.py`
- `paper/citation_claim_audit.md`
- `paper/internal_review_report.md`
- `paper/double_blind_package_check.md`
- `paper/submission_readiness_audit.md`
- `paper/submission_package_manifest.md`
- `scripts/audit_submission_package.py`

---

## 6. Current Risks

### P0 risk: real validation is missing

There is no current `paper/real_validation.md`, no `paper/video/`, and no
validation media file found under `paper/`. Unless this changes, the manuscript
must remain strictly offline-benchmark in its claims.

Required decision:

- UR5 path: 30 trials, 10 easy / 10 medium / 10 hard, with execution outcomes.
- Conservative path: at least 30 real RGB-D or RGB scenes, clearly labeled as
  real-image offline validation rather than robot execution.

### P1 risk: main-run provenance remains reconstructed

The raw console log for the original full run is absent. This is now honestly
handled by `paper/main_experiment_provenance_run_log.md`, but it remains a
reproducibility caveat. Do not rename that file as a raw run log.

### P1 risk: semantic failure taxonomy is still partially author-labeled

The metric denominator is script-audited, but the six semantic categories
(`wrong blocker`, `direct when blocker needed`, etc.) are still described as
paper-authoritative labels. This is acceptable for current manuscript use but
should not be overstated as fully regenerated from raw rows.

### P2 risk: branch/submodule state

Current git status shows the branch is ahead of remote and the
`models/langsam/GroundingDINO` submodule is modified. This is not necessarily a
paper blocker, but it must be accounted for before pushing, archiving, or
building a reproducibility package.

---

## 7. Recommended Next 72 Hours

1. Decide the T7 validation route: UR5 or real-image offline validation.
2. Draft `paper/real_validation.md` protocol before collecting or claiming any
   real-world evidence.
3. If no validation can be collected soon, explicitly update the manuscript and
   submission package to say the current evidence is offline benchmark only.
4. Review `paper/main.pdf` manually for table/figure readability after the new
   figures added on 2026-07-07.
5. Resolve or document the modified `models/langsam/GroundingDINO` submodule
   before the next push/archive.

Do not start new paid VLM experiments until T7 is decided.

---

## 8. Current Git Snapshot

- Branch: `experiment/routing-v2`.
- Ahead of remote: 22 commits.
- Working tree signal: modified submodule `models/langsam/GroundingDINO`.
- Latest commit: `00ec7ba docs: update paper sections, audit reports, and add ablation figures`.

---

## 9. One-Line Status For Advisor Update

The offline RA-L package is now much stronger than on 2026-07-04: main results,
ablations, failure analysis, citation audit, internal review, figures, and
double-blind package audit are in place; the remaining decision is whether to
add UR5/real-image validation or submit with strictly bounded offline
FreeGraspData evidence.

