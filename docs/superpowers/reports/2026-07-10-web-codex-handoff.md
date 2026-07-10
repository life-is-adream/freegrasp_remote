# Web Codex Handoff: FreeGrasp EGHC RA-L

Date: 2026-07-10

Purpose: give a fresh Codex conversation enough context to continue the RA-L
paper work without re-discovering the project history or accidentally starting
new paid experiments.

## 1. Repository And Branch

Use this repository and branch:

```text
repo: https://github.com/life-is-adream/freegrasp_remote.git
branch: experiment/routing-v2
latest pushed commit: fe4b668 docs: update RAL paper progress
local path on server: /home/public/zb/FreeGrasp_code-freegrasp_codex
```

Current known local caveat:

- The local server checkout has a modified submodule marker at
  `models/langsam/GroundingDINO`.
- Do not revert or include that submodule change unless the user explicitly asks
  for reproducibility/package cleanup.

## 2. First Files To Read

Read these in order:

1. `docs/superpowers/plans/daily_report_2026-07-10.md`
2. `docs/superpowers/plans/2026-07-04-ral-master-plan.md`
3. `paper/main.pdf`
4. `paper/main.tex`
5. `paper/sections/introduction.tex`
6. `paper/sections/method.tex`
7. `paper/sections/experiments.tex`
8. `paper/sections/related_work.tex`
9. `paper/sections/conclusion.tex`
10. `paper/results_main_table.md`
11. `paper/ablation_table.md`
12. `paper/failure_analysis.md`
13. `paper/citation_claim_audit.md`
14. `paper/internal_review_report.md`
15. `paper/double_blind_package_check.md`

Only after these are understood should the next agent inspect older design
history under `docs/superpowers/specs/`.

## 3. Current Paper State

The paper is now an EGHC paper, not the old protocol-calibration story.

Current title:

```text
Evidence-Gated Hierarchical Consensus Routing for Free-Form Language-Guided Grasping
```

Main claim:

EGHC converts FreeGrasp from a direct VLM answer into an auditable
target/blocker decision process. The frozen deployable EGHC3_v3 configuration
improves segmentation success under the same 900-sample FreeGraspData protocol
without using ground-truth features or benchmark difficulty labels.

Main numbers:

| Method | N | RSR | SSR | Role |
|---|---:|---:|---:|---|
| S0 original protocol | 900 | 57.89% | 47.56% | Controlled same-cache baseline |
| EGHC3_v3 | 900 | 60.89% | 55.22% | Main deployable method |
| S1 oracle | 900 | 67.44% | 60.11% | Diagnostic upper bound only |

Controlled deltas:

- EGHC3_v3 - S0 RSR: +3.00 pp, 95% CI [0.00, 5.95] pp.
- EGHC3_v3 - S0 SSR: +7.67 pp, 95% CI [4.19, 11.33] pp.
- Strongest controlled empirical claim is SSR.
- RSR must be written cautiously.

## 4. Work Already Completed

Completed or substantially completed:

- T4 main experiment closeout:
  - `paper/results_main_table.md`
  - `paper/main_experiment_provenance_run_log.md`
- T5 ablations:
  - `paper/ablation_table.md`
  - budget-2 vote, no consensus, no mask repair, no verifier, full EGHC3_v3,
    and S1 split-0 oracle rows.
- T6 failure analysis:
  - `paper/failure_analysis.md`
  - `scripts/audit_failure_outcomes.py`
- T10 citation/claim audit:
  - `paper/citation_claim_audit.md`
- T11 internal review:
  - `paper/internal_review_report.md`
- T12 first local double-blind/package audit:
  - `paper/double_blind_package_check.md`
  - `scripts/audit_submission_package.py`
- Current manuscript:
  - `paper/main.pdf`, 6 pages as of 2026-07-07.
  - Local package audit returned `AUDIT_OK` on 2026-07-10.

## 5. Current Blocker

The live blocker is T7 real validation.

No current artifact exists for:

- `paper/real_validation.md`
- `paper/video/`
- UR5 execution trials
- real-image offline validation set

Therefore:

- Do not claim real-robot success.
- Do not imply RSR/SSR proves physical grasp execution.
- Decide between UR5 validation and real-image offline validation before adding
  any real-world claim.

Recommended T7 paths:

1. UR5 path:
   - 30 trials total.
   - 10 easy, 10 medium, 10 hard.
   - Record RGB/depth, instruction, chosen ID, mask, grasp pose, execution
     success, and failure reason.
2. Conservative real-image path:
   - At least 30 real RGB-D or RGB scenes.
   - Run object selection and segmentation offline.
   - Label as real-image offline validation, not real-robot execution success.

## 6. Commands To Recheck Current State

Use these before claiming anything is current:

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
git status -sb
python scripts/audit_failure_outcomes.py \
  --details-root data/output/ablation_matrix/EGHC3_v3_qwen35_full \
  --expect-total 900 \
  --expect-non-joint 431
python scripts/audit_submission_package.py --root .
pdfinfo paper/main.pdf | sed -n '1,80p'
pdffonts paper/main.pdf | sed -n '1,80p'
```

Expected as of 2026-07-10:

- Failure audit: `total_rows=900`, `non_joint_success=431`.
- Submission package audit: `AUDIT_OK`.
- PDF: 6 pages.
- Current local working tree may show only the modified
  `models/langsam/GroundingDINO` submodule if no new edits were made.

## 7. Claim Boundary Rules

Safe:

- EGHC3_v3 is the main deployable no-GT method.
- EGHC3_v3 improves controlled SSR over S0 by +7.67 pp.
- EGHC3_v3 has a smaller positive RSR delta over S0, interpreted cautiously.
- Budget-2 original-protocol voting does not reproduce EGHC's split-0 gains.
- Mask repair mainly improves SSR.
- Hard-scene failures remain dominated by blocker/visibility errors.

Unsafe:

- Do not say EGHC solves occlusion.
- Do not call S1 deployable.
- Do not claim the original GPT-4o comparison is paired.
- Do not claim real-robot success.
- Do not make qwen3.7-plus, qwen3.7-max, or any newer VLM the paper's main
  evidence.
- Do not start new paid VLM experiments unless the user explicitly asks.

## 8. Best Next Tasks For The New Conversation

Recommended order:

1. Choose the T7 validation route with the user.
2. Draft `paper/real_validation.md` as a protocol before collecting data.
3. If no T7 evidence will be collected, revise the manuscript to explicitly
   remain an offline FreeGraspData benchmark paper.
4. Manually inspect `paper/main.pdf` for table/figure readability.
5. Decide how to handle the modified `models/langsam/GroundingDINO` submodule
   before archival or final push.
6. Re-run `scripts/audit_submission_package.py --root .` after any manuscript
   or figure edits.

## 9. Paste This Prompt Into The Other Codex Conversation

```text
You are taking over the FreeGrasp EGHC RA-L paper work.

Repository:
https://github.com/life-is-adream/freegrasp_remote.git
Branch:
experiment/routing-v2

First read:
docs/superpowers/reports/2026-07-10-web-codex-handoff.md
docs/superpowers/plans/daily_report_2026-07-10.md
docs/superpowers/plans/2026-07-04-ral-master-plan.md
paper/main.pdf
paper/results_main_table.md
paper/ablation_table.md
paper/failure_analysis.md
paper/citation_claim_audit.md
paper/internal_review_report.md
paper/double_blind_package_check.md

Current paper state:
Main method is EGHC3_v3, not v10/S1 and not a model-replacement story.
Main result is 900-sample FreeGraspData: 60.89% RSR / 55.22% SSR.
Controlled S0 delta: +3.00 pp RSR and +7.67 pp SSR.
SSR is the strongest controlled empirical gain; RSR must be cautious.
S1 is oracle diagnostic only.
No real-robot success is currently supported.

Before doing any work, run:
git status -sb
python scripts/audit_failure_outcomes.py --details-root data/output/ablation_matrix/EGHC3_v3_qwen35_full --expect-total 900 --expect-non-joint 431
python scripts/audit_submission_package.py --root .

Your likely next task is T7:
help decide and draft paper/real_validation.md for either UR5 validation or clearly bounded real-image offline validation.
Do not start paid VLM experiments unless I explicitly ask.
Do not revert the modified models/langsam/GroundingDINO submodule unless I explicitly ask.
```

