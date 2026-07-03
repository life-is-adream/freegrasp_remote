# EGHC RA-L Progress PPT Plan

Date: 2026-07-03

Purpose: summarize the work from the routing-protocol pivot to the current
RA-L manuscript state, and provide a slide-by-slide plan for a 15--20 minute
research progress presentation. The emphasis is on the already written Method
and Experiments sections.

## 1. One-Sentence Talk Argument

Evidence-Gated Hierarchical Consensus Routing (EGHC) changes FreeGrasp from a
single direct VLM answer into an auditable target/blocker routing process; on
900 FreeGraspData samples, the frozen no-GT EGHC3_v3 method improves controlled
segmentation success over the same-cache S0 baseline while exposing the
remaining hard-scene blocker and visibility bottleneck.

Use this exact framing in the PPT:

- Strong claim: EGHC improves the decision contract and SSR under a controlled
  no-GT protocol.
- Cautious claim: RSR moves positively but should be described with bootstrap
  uncertainty.
- Boundary: this is offline benchmark reasoning and mask-IoU evidence, not yet
  real-robot success evidence.

## 2. Terminology Ledger

| Canonical term | Meaning in the PPT | Notes |
|---|---|---|
| FreeGrasp | Original direct-answer language-guided grasping pipeline | Do not call EGHC "FreeGrasp++" unless discussing system lineage. |
| EGHC | Evidence-Gated Hierarchical Consensus Routing | Main method name in the presentation. |
| EGHC3_v3 | Frozen deployable no-GT implementation | Main RA-L result: 60.89% RSR / 55.22% SSR. |
| S0 | Controlled original FreeGrasp protocol with MiMo-v2.5 | Same Molmo cache/protocol control. |
| S1 oracle | Diagnostic upper bound using GT-derived evidence/difficulty | Not deployable; keep in oracle/headroom slide. |
| RSR | Reasoning Success Rate | Correct first-grasp object decision. |
| SSR | Segmentation Success Rate | First-grasp mask IoU success. |
| Molmo cache | Reused marked-candidate evidence | SHA prefix `705d0883`; candidate marking is a hard upstream boundary. |
| route guard | `eghc_consensus_v1` | Consensus/adjudication policy. |
| mask repair | `eghc_mask_repair_v1` | Point/evidence-constrained segmentation selection. |

## 3. Half-Month Work Summary

### Stage A: Routing-Protocol Pivot

The project moved away from presenting v10/S1 as the main story. That older
line was useful diagnostically, but it relied on oracle-style or annotation
assistance and was therefore unsafe as a deployable RA-L claim. The new story
freezes EGHC3_v3 as the main method and treats S1 only as an upper-bound
diagnostic.

Main output:

- Central claim rewritten around deployable evidence-gated routing.
- Method name fixed as Evidence-Gated Hierarchical Consensus Routing.
- Provenance boundary defined: no GT semantic features, no GT geometry, no
  benchmark difficulty labels at inference time.

### Stage B: EGHC Method Definition

The Method section now defines the task as a first-grasp decision process rather
than a direct class prediction. Given an RGB image, a free-form instruction, and
Molmo marked candidates, EGHC must output a first-grasp object ID and mask.

The main method was decomposed into:

- deployment-available evidence packet;
- evidence gate;
- direct / target-first / blocker-first route choices;
- hierarchical consensus and adjudication;
- route-specific first-grasp planning;
- point- and evidence-constrained mask repair.

### Stage C: Full 900-Sample Evidence

The main result was frozen on all 900 FreeGraspData instructions:

- EGHC3_v3: 60.89% RSR / 55.22% SSR.
- S0 controlled baseline: 57.89% RSR / 47.56% SSR.
- Controlled delta: +3.00 pp RSR / +7.67 pp SSR.
- Published original FreeGrasp GPT-4o comparison remains descriptive only:
  about +13.6 pp RSR / +17.0 pp SSR.

### Stage D: Statistical and Reviewer-Driven Additions

External review feedback exposed four necessary additions: uncertainty,
failure causes, ablation evidence, and compute overhead. These have now been
added to the paper and experiment docs.

Completed additions:

- scene-clustered paired bootstrap over 900 aligned rows and 291 scene clusters;
- failure taxonomy over 431 non-joint-success samples;
- split-0 budget-2 vote ablation;
- split-0 no-mask-repair ablation;
- split-0 no-consensus routing ablation;
- offline inference cost/call-budget table;
- ablation table documentation with S2--S7 historical mapping.

### Stage E: Real-World Preparation

The real-world pipeline has been smoke-tested offline on example scenes, but it
is not yet used as manuscript evidence. For the PPT, present it only as the
next validation stage before UR5 execution.

## 4. Current Paper Story

### Problem

Free-form language-guided grasping in clutter is not just target classification.
The system must decide whether the named target is visible and graspable, which
instance is intended, whether a blocker must be removed first, and which mask
corresponds to the first grasp. A direct VLM answer entangles all of these
decisions and makes failures difficult to audit.

### Method Claim

EGHC converts the direct-answer contract into a structured and auditable
routing contract. It uses deployment-available evidence to decide whether the
first grasp should be direct, target-first, or blocker-first, and invokes
route-specific planning plus mask repair only under the selected route.

### Experiment Claim

The strongest controlled evidence is SSR: EGHC3_v3 improves S0 by +7.67 pp
with a 95% CI of [4.19, 11.33] pp. RSR improves by +3.00 pp, but the 95% CI is
[0.00, 5.95] pp, so the PPT should describe RSR as positive but statistically
more cautious.

### Limitation Claim

EGHC exposes rather than solves hard-scene occlusion. Hard failures are
dominated by wrong blocker selection and direct grasping when blocker removal
was needed. If Molmo does not mark a critical target or blocker, the evidence
packet has no object ID for that instance and the router cannot recover it.

## 5. Recommended PPT Structure

Target length: 18 slides for 15--20 minutes.

Visual rule: use workflow diagrams and tables as evidence, not decoration. The
method block should use the existing architecture figures; the experiment block
should use editable tables rebuilt from the manuscript numbers.

| Slide | Title | Purpose | Main visual | Key message |
|---:|---|---|---|---|
| 1 | EGHC for Free-Form Language-Guided Grasping | Opening | Title + one-line claim | The work is about making first-grasp reasoning auditable. |
| 2 | Direct VLM Answers Hide Multiple Decisions | Motivation | Failure decomposition diagram | Target, blocker, and mask decisions are collapsed in the old contract. |
| 3 | The Last-Half-Month Pivot | Progress timeline | Timeline from routing protocol to ablations | The paper moved from oracle diagnostics to deployable EGHC. |
| 4 | Task Formulation | Define problem | Input/output schematic | Input is image, instruction, candidates; output is first-grasp ID and mask. |
| 5 | Deployment Evidence Boundary | Establish credibility | Evidence boundary table | EGHC3_v3 uses predicted/deployable evidence, not GT or difficulty labels. |
| 6 | EGHC System Overview | Method overview | `system_overview.pdf` | The pipeline separates evidence extraction, routing, planning, and mask repair. |
| 7 | Evidence-Gated Routing | Explain core route logic | Direct / target-first / blocker-first flow | Physical blocker evidence is required for blocker-first routing. |
| 8 | Hierarchical Consensus | Explain why routing is auditable | Consensus/adjudication diagram | The guard checks validity and route consistency before finalizing the decision. |
| 9 | Route-Specific Planning | Show technical detail | Structured decision schema | Each route returns target resolution, blocker evidence, and first-grasp choice. |
| 10 | Point-Constrained Mask Repair | Show segmentation contribution | Mask selection scoring cartoon/table | The selected mask must stay tied to the selected Molmo candidate. |
| 11 | Evaluation Protocol | Set up evidence | Dataset/baseline/metric table | 900 samples, six strata, S0 control, S1 oracle, RSR/SSR. |
| 12 | Main 900-Sample Result | Headline result | Main comparison table | EGHC3_v3 achieves 60.89% RSR and 55.22% SSR. |
| 13 | Paired Bootstrap: What Is Strong? | Statistical calibration | Bootstrap CI table | SSR gain is strong; RSR gain is positive but cautious. |
| 14 | Ablations: Not Just More Calls | Mechanism test | Split-0 ablation table | Budget-2 vote fails; routing/mask repair explain the SSR gain. |
| 15 | Offline Cost and Call Budget | Reviewer response | Call-budget table | EGHC costs 3.16 recorded calls/sample; wall-clock latency is not yet measured. |
| 16 | Failure Taxonomy | Explain what remains broken | Failure category stacked/table | Easy failures are instance/mask; hard failures are blocker/visibility. |
| 17 | Oracle Headroom and Boundaries | Prevent overclaiming | EGHC vs S1 oracle table | S1 shows headroom but is not deployable. |
| 18 | Submission Readiness and Next Step | Close | Checklist | Paper is ready for pre-real-robot stage; next evidence is UR5 validation. |

## 6. Method Slides: Detailed Content

### Slide 4: Task Formulation

On-slide bullets:

- Input: RGB image, free-form instruction, Molmo marked candidates.
- Output: first-grasp object ID and segmentation mask.
- Success: RSR checks first-grasp reasoning; SSR checks mask IoU.

Speaker note:

The key shift is that the task is not "name the object." The first grasp may
be the target or a blocker. Therefore the output contract must include both an
object decision and a mask decision.

### Slide 5: Deployment Evidence Boundary

On-slide bullets:

- Allowed: Molmo IDs/points, predicted masks/boxes, predicted spatial
  relations, route consistency.
- Not allowed: GT semantic labels, GT masks, GT geometry, benchmark difficulty.
- Main run: feature source `deployable_predicted`.

Speaker note:

This slide protects the central claim. It tells reviewers that the main number
is not an oracle result. S1 belongs later as a diagnostic ceiling.

### Slide 7: Evidence-Gated Routing

On-slide bullets:

- `direct`: visible target, no blocker or ambiguity evidence.
- `target_first`: target is plausible but evidence is uncertain or incomplete.
- `blocker_first`: requires explicit physical blocker evidence.

Speaker note:

The conservative design matters. Proximity alone is not enough to route to
blocker-first; the router needs evidence such as contact, coverage, on-top, or
overlap. Ambiguous cases are routed into target-first rather than overclaiming
blocker evidence.

### Slide 8: Hierarchical Consensus

On-slide bullets:

- Route proposal from evidence packet.
- Route-specific plan from VLM reasoning.
- Repair/adjudication when ID validity or route consistency fails.

Speaker note:

Consensus is the audit layer. It does not simply lengthen the prompt; it checks
whether the selected first-grasp object is valid under the evidence contract.

### Slide 10: Point-Constrained Mask Repair

On-slide bullets:

- Keep mask tied to selected Molmo point.
- Prefer masks containing the selected point after area filtering.
- Retry simplified phrases/ranked candidates when no usable mask appears.

Speaker note:

This is why the no-mask-repair ablation matters. Removing repair keeps RSR
similar but drops SSR from 56.00% to 50.67% on split 0, showing that the repair
stage mainly improves segmentation consistency.

## 7. Experiment Slides: Detailed Content

### Slide 11: Evaluation Protocol

Must include:

- FreeGraspData: 900 instructions, splits 0/1/2.
- Six strata: easy/medium/hard crossed with ambiguity/no ambiguity.
- Baselines: original FreeGrasp GPT-4o reported baseline, S0 controlled
  same-cache baseline, S1 oracle upper bound.
- Metrics: RSR and SSR.

Important wording:

- "The original GPT-4o comparison is descriptive because row-level historical
  predictions are unavailable."
- "S0 is the controlled paired comparison."

### Slide 12: Main Result

Use table:

| Method | N | GT? | Difficulty? | RSR | SSR | Role |
|---|---:|---|---|---:|---:|---|
| Original FreeGrasp + GPT-4o | as reported | no | no | about 47.3 | about 38.2 | published baseline |
| S0 original protocol + MiMo-v2.5 | 900 | no | no | 57.89 | 47.56 | controlled baseline |
| EGHC3_v3 | 900 | no | no | 60.89 | 55.22 | proposed method |

Speaker note:

The manuscript should sell the controlled S0 comparison first. The original
FreeGrasp comparison is useful for context, but not the statistical anchor.

### Slide 13: Bootstrap

Use table:

| Comparison | Metric | Delta | 95% CI | Tail probability |
|---|---|---:|---:|---:|
| EGHC3_v3 - S0 | RSR | +3.00 pp | [0.00, 5.95] | 0.0266 |
| EGHC3_v3 - S0 | SSR | +7.67 pp | [4.19, 11.33] | <0.0001 |
| S1 - EGHC3_v3 | RSR | +6.56 pp | [3.41, 9.80] | 0.0001 |
| S1 - EGHC3_v3 | SSR | +4.89 pp | [1.86, 7.95] | 0.0009 |

Speaker note:

This slide directly answers reviewer pressure. The honest story is that EGHC
has a strong controlled SSR gain and a smaller, directionally positive RSR
gain.

### Slide 14: Ablation Evidence

Use split-0 table:

| Variant | RSR | SSR | Calls/sample | Interpretation |
|---|---:|---:|---:|---|
| S0 split 0 | 58.33 | 47.67 | 1.00 | original contract |
| Original + budget-2 vote | 56.67 | 46.33 | 2.00 | more calls alone fail |
| EGHC no consensus | 59.00 | 56.00 | 3.32 | routing still helps, consensus not sole source |
| EGHC no mask repair | 61.67 | 50.67 | 3.19 | mask repair drives SSR |
| EGHC3_v3 split 0 | 61.00 | 56.00 | 3.16 | full deployable method |

Speaker note:

This slide is the mechanism evidence. The key negative control is budget-2
vote: simply asking the old prompt twice does not reproduce EGHC.

### Slide 15: Offline Cost

Use current call-budget table:

- S0: 1.00 recorded calls/sample.
- EGHC3_v3: 2.10 reasoning + 1.00 router + 0.07 repair = 3.16 recorded
  calls/sample.
- Wall-clock latency: not reconstructable from current logs.

Speaker note:

Do not hide overhead. The paper now reports call budget explicitly, which
answers the hidden-compute critique. Real-time robot latency remains future
validation.

### Slide 16: Failure Taxonomy

Use table over 431 non-joint-success samples:

| Error type | Easy | Medium | Hard | Total |
|---|---:|---:|---:|---:|
| Correct ID, failed mask | 7 | 8 | 10 | 25 |
| Wrong target instance | 36 | 0 | 0 | 36 |
| Wrong blocker | 0 | 38 | 125 | 163 |
| Direct, blocker needed | 0 | 77 | 76 | 153 |
| Blocker, direct possible | 0 | 0 | 0 | 0 |
| No usable mask | 33 | 8 | 13 | 54 |

Speaker note:

This is the Discussion bridge. Easy scenes are mostly instance/mask problems.
Hard scenes fail earlier, at blocker and visibility reasoning. That is why the
next technical need is better predicted visibility and blocker evidence.

## 8. Figures and Tables To Reuse

Primary assets:

- `paper/figures/system_overview.pdf`
- `paper/figures/eghc_architecture.pdf`
- `paper/sections/experiments.tex`
- `docs/experiments/ablation_table.md`
- `docs/experiments/2026-07-02-offline-inference-cost-summary.md`
- `docs/superpowers/specs/2026-06-29-eghc3-ral-paper-revision-design.md`
- `docs/superpowers/specs/2026-06-30-ral-submission-readiness-design.md`

Recommended redraws:

- One simple "old direct contract vs EGHC routed contract" diagram.
- One timeline graphic from routing protocol to ablation completion.
- One stacked bar or grouped table for failure taxonomy.

## 9. Claims To Use and Avoid

Use:

- "EGHC improves controlled SSR by +7.67 pp over S0."
- "EGHC yields a smaller positive RSR delta, interpreted cautiously because
  the CI lower bound reaches 0.00 pp."
- "The original FreeGrasp GPT-4o comparison is descriptive."
- "S1 is an oracle upper bound and reveals remaining headroom."
- "Hard scenes remain limited by blocker visibility and candidate evidence."

Avoid:

- "EGHC solves occlusion reasoning."
- "S1 is deployable."
- "The original GPT-4o baseline is paired with EGHC."
- "Higher RSR proves real-robot grasp success."
- "The gain is just from a better/larger VLM."

## 10. PPT Production Checklist

1. Build slides 1--3 as progress/context slides.
2. Build slides 4--10 from the Method section.
3. Build slides 11--17 from the Experiments section and ablation docs.
4. Build slide 18 as submission/readiness and next-step slide.
5. Rebuild all tables as editable PPT tables.
6. Add speaker notes for slides 5, 7, 10, 13, 15, and 16.
7. Run a claim-boundary audit: every number must trace to the frozen run,
   controlled S0, bootstrap table, ablation docs, or S1 oracle.
8. Run a terminology audit: keep EGHC, EGHC3_v3, S0, S1, RSR, SSR consistent.

## 11. Suggested Closing Slide

Three takeaways:

1. EGHC is a deployable decision-contract contribution, not an oracle result.
2. The strongest controlled empirical gain is segmentation success, supported
   by bootstrap and mask-repair ablation.
3. The failure taxonomy gives a clear next step: improve predicted blocker and
   visibility evidence, then validate on UR5.

