# RA-L Submission Readiness Design

Date: 2026-06-30

Status: approved design, pending implementation plan.

## 1. Purpose

Prepare the EGHC3 RA-L manuscript for internal review and submission readiness
without mixing paper work with the separate Qwen3.7-plus debugging thread.

The work has three coupled goals:

1. Polish the manuscript into a clear RA-L internal-review draft.
2. Audit the evidence chain for statistical, baseline, oracle, and no-GT
   boundary risks.
3. Organize the Git/package state so paper deliverables, statistics scripts,
   review reports, and Qwen debugging changes can be reviewed separately.

## 2. First-Principles Execution Rule

Every manuscript claim must trace to one of four evidence classes:

| Evidence class | Allowed claim strength |
|---|---|
| Frozen EGHC3_v3 900-sample run | Main method performance and failure analysis |
| Controlled same-cache S0 comparison | Controlled EGHC-vs-FreeGrasp-protocol deltas |
| Scene-clustered paired bootstrap | Uncertainty and cautious statistical interpretation |
| S1 oracle diagnostic | Upper-bound/headroom only, not deployable performance |

If a claim does not trace to one of these classes, it must be weakened, moved to
future work, or removed.

## 3. Scope

### In scope

- `paper/main.tex`
- `paper/sections/introduction.tex`
- `paper/sections/method.tex`
- `paper/sections/experiments.tex`
- `paper/sections/conclusion.tex`
- paper figures and captions only when needed for clarity
- `docs/superpowers/reports/*ral*`
- `docs/superpowers/specs/2026-06-29-eghc3-ral-paper-revision-design.md`
- `scripts/paired_bootstrap_ci.py`
- generated statistics summaries under `data/output/statistics/`

### Out of scope

- Qwen3.7-plus model-performance debugging
- changing EGHC3_v3 frozen result numbers
- rerunning paid model inference
- changing Molmo cache provenance
- adding new baselines not already available locally
- real-robot execution claims

Existing Qwen-related dirty files should be classified and left untouched unless
the user explicitly switches to the Qwen debugging track.

## 4. Canonical Terminology

| Canonical term | Use |
|---|---|
| Evidence-Gated Hierarchical Consensus Routing (EGHC) | Paper method name |
| EGHC3_v3 | Frozen implementation/run label |
| S0 | Controlled same-cache original FreeGrasp-protocol baseline |
| S1 oracle diagnostic | Oracle upper-bound run using GT-derived evidence and difficulty labels |
| RSR | Reasoning success rate |
| SSR | Segmentation success rate |
| no-GT / no difficulty | Deployment boundary for EGHC3_v3 inference |

Avoid using `FreeGrasp++`, `v10`, or `S1` as the main method name.

## 5. Phase A: Manuscript Polishing

### Goal

Make the RA-L draft readable, bounded, and reviewer-facing.

### Checks

1. Abstract states the problem, method, main 900-sample result, controlled S0
   comparison, and oracle headroom without overclaiming.
2. Introduction frames EGHC as a decision contract, not as a larger-model result.
3. Method defines inputs, outputs, evidence packet, evidence gate,
   hierarchical consensus, and point-constrained mask repair.
4. Experiments separate reported baseline, controlled baseline, main method,
   oracle headroom, failure taxonomy, and bootstrap uncertainty.
5. Conclusion emphasizes SSR gain and auditable routing, while treating RSR and
   hard-scene blocker reasoning cautiously.

### Output

An updated `paper/main.pdf` that compiles cleanly with no fatal LaTeX errors and
no severe table overflows.

## 6. Phase B: Integrity And Claim Audit

### Goal

Find reviewer-blocking logic issues before external review.

### Audit matrix

| Risk | Required treatment |
|---|---|
| Original FreeGrasp GPT-4o comparison is unpaired | Always label as reported/descriptive |
| S0 comparison is controlled | Always mention same 900 samples and reused Molmo cache |
| S1 is oracle | Never present as deployable method performance |
| RSR gain has CI lower bound 0.00 pp | Describe cautiously; do not overstate significance |
| SSR gain has stronger CI | Use as the strongest controlled empirical claim |
| Hard-scene performance remains low | Frame as open blocker/visibility bottleneck |
| RSR/SSR are benchmark metrics | Do not imply real-robot sequence success |

### Output

An updated review report that external reviewers can use directly. The report
should lead with blocking risks, then minor issues, then suggested revision
actions.

## 7. Phase C: Git And Package Hygiene

### Goal

Make the work reviewable without conflating manuscript revision and Qwen model
debugging.

### Classification

| Group | Examples | Commit policy |
|---|---|---|
| Paper manuscript | `paper/main.tex`, section files, figures | paper revision commit |
| Statistical support | `scripts/paired_bootstrap_ci.py`, statistics outputs | stats/support commit |
| Review package | `docs/superpowers/reports/*ral*` | review-docs commit |
| Revision design/specs | design docs under `docs/superpowers/specs/` | docs commit |
| Qwen debugging | `evaluate_all.py`, `evaluate_common.py`, `reasoning_eval.py`, tests | separate debug commit or leave uncommitted |

Before committing paper work, inspect `git status --short` and stage only the
intended group. Do not stage unrelated Qwen debugging files into the paper
submission commit.

## 8. Success Criteria

The readiness pass is complete when:

1. `paper/main.pdf` compiles successfully.
2. The abstract and conclusion include bootstrap-aware wording.
3. The failure taxonomy is present and tied to discussion.
4. The review package states claim/evidence/status and external review prompts.
5. A Git grouping report identifies which dirty files belong to paper, stats,
   review docs, specs, and Qwen debugging.
6. No implementation changes are made to model inference code during this pass.

## 9. Implementation Plan Boundary

After this design is reviewed and approved, the next step is to create an
implementation plan using the writing-plans workflow. That plan should break
the work into concrete steps for manuscript polishing, integrity audit,
verification, and Git grouping.

