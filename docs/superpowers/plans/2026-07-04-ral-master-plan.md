# FreeGrasp EGHC RA-L Updated Master Plan

Date: 2026-07-04

Status update: 2026-07-10. The file remains the merged master plan, but the
task board below has been updated with the post-2026-07-07 manuscript/package
state. See `docs/superpowers/plans/daily_report_2026-07-10.md` for the latest
daily snapshot.

This plan merges:

- `docs/superpowers/plans/2026-06-18-ral-submission-plan.md`
- `docs/superpowers/plans/daily_report_2026-07-03.md`

Use this file as the current execution master plan. The 2026-06-18 plan remains
the long-range submission roadmap, and the 2026-07-03 daily report remains the
latest server-state snapshot. This merged plan resolves the conflict between
the old "Protocol-Calibrated OVL" framing and the current EGHC3_v3 manuscript
state.

## 1. Current Thesis

The paper should now be framed as:

> Evidence-Gated Hierarchical Consensus Routing (EGHC) converts FreeGrasp from
> a direct VLM answer into an auditable target/blocker decision process. The
> frozen deployable EGHC3_v3 configuration improves segmentation success under
> the same 900-sample FreeGraspData protocol without using ground-truth
> features or benchmark difficulty labels, while exposing blocker/visibility as
> the remaining hard-scene bottleneck.

Use this boundary:

- Main method: `EGHC3_v3`.
- Main result: 900 samples, RSR 60.89%, SSR 55.22%.
- Controlled baseline: S0 original FreeGrasp protocol with MiMo-v2.5 and same
  Molmo cache.
- Strongest controlled empirical claim: SSR improves by +7.67 pp over S0.
- Cautious controlled claim: RSR improves by +3.00 pp over S0, but the 95% CI
  lower bound reaches 0.00 pp.
- Descriptive-only comparison: original FreeGrasp GPT-4o reported baseline.
- Diagnostic-only result: S1 oracle upper bound.
- No claim yet: real-robot grasp success.

## 2. Submission Target

| Item | Current decision |
|---|---|
| Venue | IEEE Robotics and Automation Letters (RA-L) |
| Target submission window | 2026-09-01 to 2026-09-05 |
| Ideal submission date | 2026-09-03 |
| Internal content freeze | 2026-08-25 |
| Internal format freeze | 2026-08-30 |
| Page target | RA-L double-column, 6 pages preferred, 8 pages maximum |
| Paper title | Evidence-Gated Hierarchical Consensus Routing for Free-Form Language-Guided Grasping |
| Main evidence type | Offline FreeGraspData RSR/SSR, ablations, bootstrap CI, failure taxonomy |
| Real-world evidence status | Not started as of 2026-07-10; UR5 or real-image offline validation must be decided by 2026-07-27 |

## 3. Updated Task Board

| Task | Deadline | Current status | Required next action |
|---|---:|---|---|
| T1 Story line | 2026-06-21 | Complete | Keep EGHC framing; do not revive v10/S1 as main method. |
| T2 RA-L outline | 2026-06-24 | Substantially complete | Treat existing LaTeX five-section draft as the working outline. |
| T3 Experiment protocol | 2026-06-28 | Frozen in practice | Keep EGHC3_v3 manifest and no-GT provenance as source of truth. |
| T4 Main experiment | 2026-07-05 | Complete with reconstructed provenance | `paper/results_main_table.md` and `paper/main_experiment_provenance_run_log.md` exist. Raw console `run_log.txt` is absent and should not be invented. |
| T5 Ablations | 2026-07-19 | Complete for current paper claims | `paper/ablation_table.md` exists and includes budget-2, no consensus, no mask repair, no verifier, EGHC3_v3, and S1 split-0 rows. |
| T6 Failure analysis | 2026-07-26 | Complete for current paper package | `paper/failure_analysis.md` exists; `scripts/audit_failure_outcomes.py` verifies 900 rows and 431 non-joint-success samples. |
| T7 UR5 or real-image validation | 2026-08-09 | Not started | Decide by 2026-07-27; draft protocol first. |
| T8 Figures | 2026-08-12 | Strong draft | Figure PDFs exist and pass local metadata/font audit; final human readability check remains. |
| T9 English RA-L draft | 2026-08-16 | Strong draft | `paper/main.pdf` compiles to 6 pages as of 2026-07-07. |
| T10 Citation and claim audit | 2026-08-20 | First pass complete; metadata polish substantially advanced | `paper/citation_claim_audit.md` exists; current citation scan reports 22 cites and 22 bibitems with no missing or uncited keys. |
| T11 Internal review | 2026-08-23 | Complete first pass and no-verifier re-review | `paper/internal_review_report.md` exists. |
| T12 Double-blind/package check | 2026-08-30 | Local audit passes current draft; final package not frozen | `paper/double_blind_package_check.md` exists; `scripts/audit_submission_package.py --root .` returns `AUDIT_OK`. |
| T13 Final submission | 2026-09-03 | Not started | Submit through PaperCept after T12 passes. |

## 4. Evidence Inventory

### Frozen main method

| Evidence | Path / source |
|---|---|
| Main run summary | `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json` |
| Method provenance | `feature_source=deployable_predicted`, `uses_gt_features=false`, `uses_benchmark_difficulty=false` |
| Molmo cache | reused cache, SHA prefix `705d0883` |
| Main performance | RSR 60.89%, SSR 55.22%, N=900 |
| Call budget | 1889 reasoning calls + 900 router calls + 59 repair calls |

### Controlled comparisons

| Comparison | Metric | Delta | Interpretation |
|---|---|---:|---|
| EGHC3_v3 - S0 | RSR | +3.00 pp | Positive but cautious; CI lower bound reaches 0.00 pp. |
| EGHC3_v3 - S0 | SSR | +7.67 pp | Strongest controlled gain. |
| S1 oracle - EGHC3_v3 | RSR | +6.56 pp | Oracle headroom, not deployable. |
| S1 oracle - EGHC3_v3 | SSR | +4.89 pp | Oracle headroom, not deployable. |
| EGHC3_v3 vs original FreeGrasp GPT-4o | RSR/SSR | about +13.6/+17.0 pp | Descriptive only; not paired. |

### Completed supporting evidence

| Evidence | Status | Notes |
|---|---|---|
| Scene-clustered bootstrap | Complete | 900 aligned rows, 291 scene clusters. |
| Budget-2 vote ablation | Complete | Shows extra original-protocol calls do not explain EGHC. |
| No-mask-repair ablation | Complete | Shows mask repair primarily supports SSR. |
| No-consensus routing ablation | Complete | Helps isolate routing/consensus contribution. |
| Offline call-budget table | Complete | Responds to hidden-overhead critique. |
| Failure taxonomy table | Paper-facing analysis complete | `paper/failure_analysis.md` exists; metric denominator is script-audited. |
| No-verifier ablation | Complete | `paper/no_verifier_ablation_run_log.md`; split-0 row added to `paper/ablation_table.md`. |
| Citation/claim audit | Complete first pass | `paper/citation_claim_audit.md`; remaining work is final DOI/page/proceedings polish if references change. |
| Double-blind package audit | Current draft passes local audit | `scripts/audit_submission_package.py --root .` returned `AUDIT_OK` on 2026-07-10. |
| PPT plan | Drafted | `docs/superpowers/reports/2026-07-03-eghc-ral-ppt-plan.md` |

## 5. Immediate Execution Plan

2026-07-10 update: P0, P1, P2, and first-pass P5 audit work have largely been
completed for the current offline manuscript package. The next live blocker is
P3 real validation.

### P0: File safety and Go Node 1 closeout

Target date: 2026-07-04 to 2026-07-05

Status on 2026-07-10: complete with caveat. The repository contains
`paper/results_main_table.md` and `paper/main_experiment_provenance_run_log.md`.
The provenance note is intentionally reconstructed from artifacts because the
raw console `run_log.txt` was absent.

1. Commit or otherwise protect current untracked planning documents:
   - `docs/superpowers/plans/2026-06-18-ral-submission-plan.md`
   - `docs/superpowers/plans/daily_report_2026-07-03.md`
   - `docs/superpowers/reports/2026-07-03-eghc-ral-ppt-plan.md`
   - this updated master plan.
2. Create `paper/results_main_table.md` from the frozen EGHC3_v3/S0/S1 evidence.
3. Add `data/output/ablation_matrix/EGHC3_v3_qwen35_full/run_log.txt` if a real
   run log exists; if not, create a clearly labeled provenance note instead of
   pretending to have raw console output.
4. Mark Go Node 1 as passed only after the summary table and run-log/provenance
   artifacts exist.

Success condition:

- Go Node 1 has data, summary table, split-file integrity, and provenance
  artifacts.

### P1: Align ablation documentation

Target date: 2026-07-04 to 2026-07-08

Status on 2026-07-10: complete for current claims. `paper/ablation_table.md`
exists and is the paper-facing table source.

1. Keep `docs/experiments/ablation_table.md` as the detailed experiment log.
2. Add `paper/ablation_table.md` as the paper-facing summary, or explicitly
   update the master plan to use `docs/experiments/ablation_table.md`.
3. Ensure S2--S7 historical labels are not confused with current EGHC ablations.
4. Ensure Table/caption wording says split-0 ablations are mechanism checks, not
   full 900-sample claims.

Success condition:

- There is one unambiguous paper-facing ablation table source.

### P2: Standalone failure analysis

Target date: 2026-07-06 to 2026-07-14

Status on 2026-07-10: complete for current manuscript package.
`paper/failure_analysis.md` exists, and `scripts/audit_failure_outcomes.py`
validates 900 total rows and 431 non-joint-success samples. Semantic categories
remain partly author-labeled and should not be overstated as fully regenerated.

Create `paper/failure_analysis.md` with:

1. Failure taxonomy table over 431 non-joint-success EGHC3_v3 samples:
   - correct ID, failed mask;
   - wrong target instance;
   - wrong blocker;
   - direct when blocker needed;
   - blocker when direct possible;
   - no usable mask.
2. Per-difficulty interpretation:
   - Easy: target instance ambiguity and mask usability dominate.
   - Medium: blocker decision begins to dominate.
   - Hard: wrong blocker and direct-when-blocker-needed dominate.
3. At least a small representative-case list:
   - 3 easy failures;
   - 3 medium failures;
   - 6 hard failures.
4. A paragraph explaining why mask repair mainly improves SSR.
5. A paragraph explaining why blocker visibility remains the main bottleneck.
6. A "paper insertion" block with polished text suitable for Discussion or
   Experiments.

Success condition:

- The paper can answer: "What did EGHC fix, and what remains broken?"

### P3: Real validation decision

Target date: 2026-07-15 to 2026-07-27

Decision gate:

- If UR5 access is feasible: run 30 trials, 10 easy / 10 medium / 10 hard.
- If UR5 access is not feasible: run at least 30 real RGB-D or RGB scenes
  offline and label the section as real-image offline validation.

For either path, write `paper/real_validation.md` before starting data
collection. The protocol must define:

- scene setup;
- instruction set;
- image/depth capture;
- object ID and mask outputs;
- grasp pose output if available;
- success/failure labels;
- claim boundary.

Success condition:

- By 2026-07-27, the project has chosen UR5 or real-image offline validation.
- By 2026-08-09, the chosen validation evidence exists or the manuscript
  explicitly lowers its real-world claim.

### P4: Manuscript tightening

Target date: 2026-07-20 to 2026-08-16

1. Keep the paper title as EGHC, not the old protocol-calibration title.
2. Rewrite abstract last, after T6/T7 evidence is fixed.
3. Keep SSR as the strongest controlled gain.
4. Keep RSR cautious because the bootstrap CI lower bound touches 0.00 pp.
5. Keep S1 oracle separated from deployable results.
6. Keep original GPT-4o comparison descriptive only.
7. Compile and page-check regularly against the 8-page hard limit.

Success condition:

- `paper/main.pdf` is readable, bounded, and claim-consistent.

### P5: Submission package

Target date: 2026-08-17 to 2026-09-03

1. `paper/citation_claim_audit.md`: every citation maps to a claim.
2. `paper/internal_review_report.md`: strict RA-L reviewer simulation.
3. Double-blind audit:
   - remove author names, affiliations, acknowledgments, self-identifying paths;
   - anonymize repository links if used;
   - check figure readability and embedded fonts.
4. Multimedia/readme:
   - video if UR5 or real-image validation is available;
   - code/data README explaining how tables trace to artifacts.
5. Final PaperCept metadata.

Success condition:

- Submission package is ready by 2026-09-03.

## 6. Updated Go/No-Go Gates

| Gate | Date | Status as of 2026-07-04 | Pass condition |
|---|---:|---|---|
| Go 1: main experiment | 2026-07-05 | Passed with provenance caveat | `full_protocol_summary.json`, split integrity, results table, and reconstructed provenance note exist. |
| Go 2: core ablations | 2026-07-19 | Passed early for current claims | Paper-facing ablation table and mechanism interpretation complete. |
| Go 3: real validation | 2026-08-09 | Not started | UR5 trials or clearly bounded real-image offline validation. |
| Go 4: draft/page budget | 2026-08-20 | On track | Current manuscript compiles to 6 pages; final evidence framing still depends on T7. |
| Go 5: submission package | 2026-08-30 | Partially on track | Local anonymous package audit passes current draft; supplement/video/readme remains blocked by T7. |

No-go rules:

- If Go 1 lacks provenance artifacts, do not call the main experiment package
  complete.
- If Go 2 lacks ablation interpretation, do not claim mechanism isolation.
- If Go 3 lacks UR5 execution, do not claim real-robot grasp success.
- If final paper exceeds 8 pages, cut scope rather than exceed RA-L limits.

## 7. Claim Boundary Rules

Safe claims:

- EGHC3_v3 uses deployment-available predicted evidence and no benchmark
  difficulty labels.
- EGHC3_v3 improves controlled SSR over S0 by +7.67 pp.
- EGHC3_v3 yields a smaller positive RSR delta over S0, interpreted cautiously.
- Budget-2 original-protocol voting does not reproduce EGHC's split-0 gains.
- Mask repair mainly improves SSR rather than first-grasp ID selection.
- Failure taxonomy shows easy-scene mask/instance ambiguity and hard-scene
  blocker/visibility bottlenecks.

Forbidden claims:

- Do not say EGHC solves occlusion.
- Do not say S1 is deployable.
- Do not say original GPT-4o comparison is paired.
- Do not say higher RSR proves real-robot grasp success.
- Do not say qwen3.7-plus or any model replacement is the main paper claim.

## 8. Working File Map

| Purpose | Current path |
|---|---|
| Main LaTeX | `paper/main.tex` |
| Sections | `paper/sections/` |
| Figures | `paper/figures/` |
| Main PDF | `paper/main.pdf` |
| Main run | `data/output/ablation_matrix/EGHC3_v3_qwen35_full/` |
| Experiment docs | `docs/experiments/` |
| Statistics outputs | `data/output/statistics/` |
| Master plans | `docs/superpowers/plans/` |
| Design specs | `docs/superpowers/specs/` |
| Review/readiness reports | `docs/superpowers/reports/` |

## 9. Next 72 Hours

Recommended order:

1. Decide the T7 validation route: UR5 or real-image offline validation.
2. Draft `paper/real_validation.md` protocol before collecting or claiming
   real-world evidence.
3. If validation cannot be collected soon, explicitly keep the manuscript as an
   offline benchmark paper and remove any real-world implication.
4. Manually inspect `paper/main.pdf` for table/figure readability after the
   2026-07-07 figure additions.
5. Resolve or document the modified `models/langsam/GroundingDINO` submodule
   before the next push/archive.

Do not start another paid VLM experiment until T7 is decided.

## 10. Owner Notes For Future Agents

- Treat this file as the current plan unless the user supersedes it.
- Do not revert user edits or untracked documents.
- Do not overwrite historical plans; append new dated plans instead.
- Keep EGHC3_v3 frozen unless the user explicitly starts a new paper version.
- If asked "what next?", default to T4 closeout, then T6 failure analysis, then
  T7 validation protocol.
