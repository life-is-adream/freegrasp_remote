# EGHC3 RA-L Paper Revision Design

Date: 2026-06-29

Status: execute Scheme 1. Freeze `EGHC3_v3_qwen35_full` as the main method and
switch the manuscript from the old v10/S1 diagnostic story to a deployable
evidence-gated routing story.

## 1. Central Claim

English claim for the manuscript:

> Evidence-Gated Hierarchical Consensus Routing converts FreeGrasp from a
> direct VLM answer into an auditable target/blocker decision process, improving
> free-form language grasp reasoning under the same 900-sample FreeGraspData
> protocol without using ground-truth features or benchmark difficulty labels.

One-sentence argument:

> In free-form language-guided grasping in clutter, we show that
> evidence-gated hierarchical consensus routing improves first-grasp reasoning
> and segmentation over the original FreeGrasp decision contract, supported by
> 900-sample FreeGraspData results and bounded by an oracle S1 upper-bound
> analysis.

## 2. Frozen Evidence

Main method is frozen as:

`FreeGrasp_code-freegrasp_codex/data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json`

Key provenance:

| Field | Value |
|---|---|
| Method label | EGHC3_v3 full |
| Paper method name | Evidence-Gated Hierarchical Consensus Routing |
| Model | MiMo-v2.5 with Qwen adjudication path, as recorded by the run manifest |
| Samples | 900, splits 0/1/2 |
| Molmo cache | reused, SHA-256 `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed` |
| Feature source | `deployable_predicted` |
| Routing variant | `evidence_gated_cascade` |
| Route guard | `eghc_consensus_v1` |
| Segmentation variant | `eghc_mask_repair_v1` |
| Uses GT features | false |
| Uses benchmark difficulty | false |
| Overall RSR / SSR | 60.89% / 55.22% |
| Calls | 1889 reasoning calls + 900 router calls + 59 repair calls |

The result is strong enough for the main RA-L table because it is a clean
no-GT 900-sample result. It should replace all claims that treat v10/S1 as the
main method.

## 3. Main Tables

### Table I: Main comparison

This is the paper's headline table.

| Method | Status | GT features? | Difficulty label? | N | RSR | SSR | Paper role |
|---|---:|---:|---:|---:|---:|---:|---|
| FreeGrasp + GPT-4o, original paper Table I | reported baseline | no | no | as reported | about 47.3 | about 38.2 | primary published baseline |
| S0 original FreeGrasp protocol + MiMo-v2.5 | controlled internal baseline | no | no | 900 | 57.89 | 47.56 | same-cache/protocol control |
| EGHC3_v3 full | main method | no | no | 900 | 60.89 | 55.22 | proposed method |

The original FreeGrasp values must be copied exactly from the paper's Table I
in the final manuscript. The current deltas imply approximately 47.3% RSR and
38.2% SSR, matching the stated `+13.6 pp RSR / +17.0 pp SSR` improvement.

### Table II: Oracle upper bound

This table must be separated from the main deployable table.

| Method | Status | GT features? | Difficulty label? | N | RSR | SSR | Paper role |
|---|---:|---:|---:|---:|---:|---:|---|
| EGHC3_v3 full | deployable predicted evidence | no | no | 900 | 60.89 | 55.22 | main method |
| S1 oracle v10 | oracle diagnostic | yes | yes | 900 | 67.44 | 60.11 | upper bound/headroom |

Interpretation: the gap from EGHC3_v3 to S1 is +6.55 pp RSR and +4.89 pp SSR.
This supports the claim that better target visibility and blocker evidence
could still improve the method, but it must not be written as deployable
performance.

### Table III: Failure analysis

Use the existing per-subset aggregate as the skeleton.

| Subset | N | EGHC3_v3 RSR | EGHC3_v3 SSR | Main interpretation |
|---|---:|---:|---:|---|
| Easy, no ambiguity | 150 | 93.33 | 79.33 | strong target resolution; remaining gap mostly mask/instance quality |
| Easy, ambiguity | 150 | 82.67 | 76.67 | ambiguity reduces target binding before mask evaluation |
| Medium, no ambiguity | 150 | 60.00 | 56.67 | target/blocker decision begins to dominate |
| Medium, ambiguity | 150 | 63.33 | 62.67 | consensus routing holds SSR close to RSR |
| Hard, no ambiguity | 150 | 32.00 | 29.33 | blocker/visibility estimation is the main bottleneck |
| Hard, ambiguity | 150 | 34.00 | 26.67 | blocker reasoning plus instance ambiguity remains unsolved |

The final paper should add a row-level error taxonomy if available:

- correct reasoning, failed mask;
- wrong target instance;
- wrong blocker;
- direct grasp when blocker removal was needed;
- blocker removal when direct target grasp was possible;
- no usable mask.

## 4. Manuscript Repositioning

### New method name

Use:

`Evidence-Gated Hierarchical Consensus Routing (EGHC)`

Avoid:

- `FreeGrasp++` as the main title unless the paper needs a system name.
- `Unified Hard-Safe Protocol` as the central contribution.
- `v10`, `S1`, or `oracle` in the main method name.

### New contribution bullets

1. An evidence-gated routing protocol that separates target resolution, blocker
   assessment, and first-grasp planning under deployment-available evidence.
2. A hierarchical consensus mechanism that triggers route-specific planning and
   adjudication only when the evidence contract is uncertain or inconsistent.
3. A point- and evidence-constrained segmentation repair stage that keeps
   mask selection tied to the selected Molmo candidate.
4. A 900-sample FreeGraspData evaluation showing 60.89% RSR and 55.22% SSR for
   the no-GT method, plus a clearly separated S1 oracle upper bound.

## 5. What Moves To Appendix Or Diagnostic

| Item | New role |
|---|---|
| v10 annotation-assisted blocker-first | historical diagnostic / appendix |
| S1 hard-blocker oracle | oracle upper bound table only |
| UHS1 / unified hard-safe protocol | predecessor design, not main method |
| depth-router v2 designs | future work or appendix if not part of EGHC3_v3 |
| Qwen 235B / Qwen 37 split-0 attempts | model sensitivity appendix only |
| prompt-only self-repair failures | negative ablation / discussion |

## 6. Statistical Verification Still Required

Before submission, add paired uncertainty estimates:

1. Pair each run by complete sample key:
   `(split, subset, row_index, scene_id, object_id, annotation)`.
2. Report paired bootstrap 95% confidence intervals for:
   - EGHC3_v3 vs original FreeGrasp reported baseline if row-level pairing is
     impossible, use descriptive comparison only;
   - EGHC3_v3 vs S0 on the same 900 samples;
   - EGHC3_v3 vs S1 oracle on the same 900 samples.
3. Use scene-clustered bootstrap as the preferred method because repeated
   instructions can share visual scene evidence.
4. Report deltas in percentage points, not only absolute values.
5. Add a short note that the main method was selected before this paper
   revision and that S1 is not used as an inference component.

Minimum table cells needed:

| Comparison | Metric | Delta | 95% CI | p or bootstrap tail probability |
|---|---|---:|---:|---:|
| EGHC3_v3 - S0 | RSR | +3.00 pp | to compute | to compute |
| EGHC3_v3 - S0 | SSR | +7.67 pp | to compute | to compute |
| S1 - EGHC3_v3 | RSR | +6.55 pp | to compute | to compute |
| S1 - EGHC3_v3 | SSR | +4.89 pp | to compute | to compute |

## 7. Claims That Are Safe

- EGHC3_v3 improves the published FreeGrasp GPT-4o baseline by about
  +13.6 pp RSR and +17.0 pp SSR under the paper's reported benchmark numbers.
- EGHC3_v3 improves the controlled S0 same-cache MiMo baseline by +3.00 pp RSR
  and +7.67 pp SSR.
- The main method uses predicted/deployable evidence and does not use GT
  features or benchmark difficulty labels.
- S1 shows measurable headroom from oracle evidence and difficulty routing.
- Hard-scene performance remains limited, so blocker visibility is still an
  open problem rather than solved.

## 8. Claims That Must Not Be Written

- Do not call S1 or v10 the main method.
- Do not claim oracle routing is deployable.
- Do not claim EGHC solves occlusion reasoning; it improves the decision
  contract and exposes the remaining visibility bottleneck.
- Do not claim a same-environment comparison with GPT-4o unless the original
  FreeGrasp protocol is rerun under the same cache and scoring code.
- Do not present the original-paper baseline as paired with EGHC3_v3 unless
  row-level original predictions are available.
- Do not claim significance until paired bootstrap/CI is computed.
- Do not imply that higher RSR automatically proves real-robot grasp success;
  the present evidence is benchmark reasoning and mask IoU.

## 9. Draft Revision Checklist

### Title and abstract

- Replace `FreeGrasp++` title with EGHC routing title.
- Lead with the problem: direct VLM answers entangle target identity, blocker
  visibility, and segmentation.
- State the method as evidence-gated hierarchical consensus routing.
- Put the main result `60.89 / 55.22` in the abstract.
- Mention the S1 oracle only as upper bound/headroom.

### Introduction

- Paragraph 1: free-form language grasping needs target and blocker decisions.
- Paragraph 2: FreeGrasp is strong but its direct answer contract is brittle.
- Paragraph 3: evidence-gated routing and consensus turn the task into an
  auditable decision process.
- Contribution bullets must match the new method, not v10.

### Method

- Define inputs and outputs.
- Define evidence packet from deployment-available sources.
- Define evidence gate.
- Define hierarchical consensus routing.
- Define route-specific first-grasp planning.
- Define point/evidence constrained mask repair.
- Include provenance boundary: no GT features, no benchmark difficulty.

### Experiments

- Table I: published FreeGrasp baseline, S0, EGHC3_v3.
- Table II: S1 oracle upper bound.
- Table III: per-subset failure analysis.
- Add paired bootstrap/CI when computed.
- Move old v10/S1 diagnostic narrative into a subsection named `Oracle headroom`.

### Discussion/conclusion

- Emphasize that the contribution is a decision contract plus evidence routing,
  not prompt length.
- Explain easy vs hard failures.
- Name the next technical need: predicted visibility/blocker evidence and
  stronger mask-instance disambiguation.

## 10. Immediate Execution Order

1. Save this design document.
2. Revise the RAL LaTeX draft in `paper/`.
3. Keep current result numbers fixed.
4. Add bootstrap/CI as the next statistics task before final submission.
5. After CI is available, update the abstract and table captions with deltas
   and confidence intervals.

