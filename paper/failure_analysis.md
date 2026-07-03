# EGHC3_v3 Failure Analysis

Date: 2026-07-04

Status: paper-facing standalone analysis for T6. This note is based only on existing artifacts; no new evaluation, paid API call, cache refresh, or output regeneration was run.

## Scope and source boundary

This analysis covers the frozen deployable EGHC3_v3 run over all 900 FreeGraspData instructions. The method configuration is recorded as `feature_source=deployable_predicted`, `uses_gt_features=false`, `uses_benchmark_difficulty=false`, `routing_variant=evidence_gated_cascade`, route guard `eghc_consensus_v1`, segmentation `eghc_mask_repair_v1`, and reused Molmo cache SHA-256 prefix `705d0883` in `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json` and `run_manifest.json`.

The failure taxonomy table below is the existing paper taxonomy from `paper/sections/experiments.tex`. I treat it as the authoritative category assignment for T6. I independently re-counted only the metric-level outcome modes from the existing `details_*.json` files: joint success, RSR-only, SSR-only, and both-fail. Those mode counts support the taxonomy totals but do not independently reconstruct every semantic category such as "wrong blocker" versus "direct, blocker needed".

## Metric outcome modes

A sample is a joint success only when both first-grasp reasoning and mask segmentation are correct. Using the existing detail rows under `data/output/ablation_matrix/EGHC3_v3_qwen35_full/split_*/details_*.json`, the 900 samples separate as follows:

| Difficulty | N | Joint success | RSR-only | SSR-only | Both-fail | Non-joint-success total |
|---|---:|---:|---:|---:|---:|---:|
| Easy | 300 | 224 | 40 | 10 | 26 | 76 |
| Medium | 300 | 169 | 16 | 10 | 105 | 131 |
| Hard | 300 | 76 | 23 | 8 | 193 | 224 |
| **Overall** | **900** | **469** | **79** | **28** | **324** | **431** |

Definitions used here follow the project metric contract: RSR-only means `rsr_correct == 1` and `ssr_correct == 0`; both-fail means `rsr_correct == 0` and `ssr_correct == 0`. SSR-only means the mask IoU crossed the SSR threshold even though the selected first-grasp ID was not acceptable, so it is not a valid task success and is included in the non-joint-success pool.

The aggregate performance source is `full_protocol_summary.json`: EGHC3_v3 reaches 548/900 RSR successes (60.89%) and 497/900 SSR successes (55.22%). The lower joint-success count, 469/900, shows why RSR and SSR must be reported together: some samples have correct first-grasp reasoning but fail mask extraction, while others have an acceptable mask overlap without an acceptable first-grasp decision.

## Failure taxonomy

The following mutually exclusive taxonomy is reproduced from the manuscript failure-analysis table in `paper/sections/experiments.tex`. Counts are over the 431 samples that were not jointly correct in both RSR and SSR.

| Error type | Easy | Medium | Hard | Total | Interpretation |
|---|---:|---:|---:|---:|---|
| Correct ID, failed mask | 7 | 8 | 10 | 25 | The first-grasp object is acceptable, but the selected mask does not reach the IoU threshold. |
| Wrong target instance | 36 | 0 | 0 | 36 | The language target is confused with a same-class or visually similar instance. |
| Wrong blocker | 0 | 38 | 125 | 163 | The system chooses a blocker-first action, but the blocker identity does not match the acceptable first-grasp set. |
| Direct, blocker needed | 0 | 77 | 76 | 153 | The system attempts the target directly when an occluding/supporting object should be removed first. |
| Blocker, direct possible | 0 | 0 | 0 | 0 | The conservative gate did not measurably invent blocker-first actions for directly graspable targets in this taxonomy. |
| No usable mask | 33 | 8 | 13 | 54 | The segmentation backend does not provide a usable point-consistent mask for the selected object. |
| **Total failures** | **76** | **131** | **224** | **431** | 900 total samples minus 469 joint successes. |

Two important readings follow from this table. First, easy failures are mostly not blocker-reasoning failures. Easy scenes account for 76 non-joint successes: 36 wrong-target-instance cases plus 40 mask-related cases (`Correct ID, failed mask` + `No usable mask`). This matches the high easy-scene RSR in `full_protocol_summary.json` and the manuscript stratum table: easy/no-ambiguity RSR is 140/150 (93.33%) and easy/ambiguity RSR is 124/150 (82.67%).

Second, medium and hard failures move upstream into the decision process. In medium scenes, wrong blocker plus direct-when-blocker-needed account for 115/131 failures. In hard scenes, the same two categories account for 201/224 failures. This is the main evidence that EGHC3_v3 improved the auditability of the decision process but did not solve occlusion-aware blocker visibility.

## Typical easy, medium, and hard failures

The examples below are representative inspection anchors from existing `details_*.json` rows. They are not a new quantitative taxonomy; they illustrate the categories above using scene IDs, query object IDs, annotations, route decisions, and observed RSR/SSR outcomes.

### Easy failures

Easy failures usually occur after the route guard protects a direct action. The remaining problem is either same-class target identity or mask usability.

| Split/subset | Scene | Query object | Annotation | Outcome | Route evidence |
|---|---:|---:|---|---|---|
| split 0 / easy_no_ambi | 564 | 5 | `the yellow thing on the bottom` | RSR=0, SSR=0, IoU=0.0 | Direct route retained by `easy_direct_protection`, but the predicted target evidence points to object 2 while the acceptable set is object 5. |
| split 0 / easy_no_ambi | 646 | 4 | `the elmex box` | RSR=1, SSR=0, IoU=0.0002 | Direct/free-visible route; the ID is acceptable but the mask effectively misses the object. |
| split 0 / easy_no_ambi | 1527 | 1 | `the big red box` | RSR=1, SSR=0, IoU=0.3971 | Correct first-grasp decision but sub-threshold mask, showing why RSR alone overstates deployability. |

These cases explain why mask repair mainly affects SSR rather than RSR. The split-0 no-mask-repair ablation in `docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md` keeps RSR essentially unchanged relative to full EGHC3_v3 (+0.67 percentage points) but drops SSR by 5.33 percentage points. The failure table is consistent with that ablation: many easy errors already have plausible or correct first-grasp choices, but the final mask does not remain point-consistent enough to pass IoU.

### Medium failures

Medium scenes are the transition regime. Some rows still look like mask misses after plausible reasoning, but blocker decisions become the dominant source of non-joint success.

| Split/subset | Scene | Query object | Annotation | Outcome | Route evidence |
|---|---:|---:|---|---|---|
| split 0 / medium_no_ambi | 206 | 6 | `the domino sugar box` | RSR=0, SSR=0, IoU=0.0822 | The route is direct/free-visible, but the acceptable first-grasp set is object 3, indicating a missed blocker or wrong first-grasp target. |
| split 0 / medium_no_ambi | 390 | 7 | `the elmex package` | RSR=0, SSR=0, IoU=0.0 | Blocker-first route with a blocker relation, but the selected/acceptable first-grasp object does not match. |
| split 0 / medium_no_ambi | 944 | 4 | `the red drill` | RSR=1, SSR=0, IoU=0.2244 | Blocker-first reasoning reaches an acceptable first-grasp ID, but segmentation remains below threshold. |

The medium taxonomy counts make the pattern quantitative: 38 wrong-blocker failures and 77 direct-when-blocker-needed failures, compared with only 16 mask-only RSR-only rows in the metric-mode count. Thus, medium scenes already require better blocker grounding, not only stronger mask post-processing.

### Hard failures

Hard failures are dominated by occlusion and blocker visibility. The system often either declares a target free-visible when a blocker-first action is needed, or chooses a plausible but wrong blocker.

| Split/subset | Scene | Query object | Annotation | Outcome | Route evidence |
|---|---:|---:|---|---|---|
| split 0 / hard_no_ambi | 1318 | 1 | `the small blue box` | RSR=0, SSR=0, IoU=0.0 | Blocker-first route with predicted blocker 5 for predicted target 4, but acceptable first-grasp set is [5, 6]. |
| split 0 / hard_no_ambi | 1733 | 3 | `the extra box` | RSR=0, SSR=0, IoU=0.0 | Target marked `mostly_hidden`; route is blocker-first, but blocker/target identity is wrong. |
| split 0 / hard_no_ambi | 1784 | 7 | `the small plastic box underneath a knife` | RSR=0, SSR=0, IoU=0.0001 | Correct qualitative need for blocker reasoning, but the chosen blocked object and acceptable first-grasp set diverge. |
| split 0 / hard_no_ambi | 2274 | 3 | `the wire cutter` | RSR=0, SSR=0, IoU=0.0 | The route is direct/free-visible although the acceptable first-grasp object is a blocker. |
| split 0 / hard_no_ambi | 3125 | 5 | `the screwdriver` | RSR=0, SSR=0, IoU=0.0 | Another direct/free-visible decision in a hard scene with a different acceptable first-grasp object. |
| split 0 / hard_no_ambi | 827 | 7 | `the cable` | RSR=1, SSR=0, IoU=0.3195 | Blocker-first decision reaches an acceptable first-grasp ID, but the mask is still below threshold. |

The hard-mode counts are severe: only 76/300 hard samples are jointly correct, while 193/300 are both-fail and 23/300 are RSR-only. The taxonomy attributes 125 hard failures to wrong blockers and 76 to direct-when-blocker-needed, for 201/224 hard non-joint successes. This supports the paper's main limitation claim: the remaining hard-scene bottleneck is not generic parsing or added-call budget, but visual grounding of which object blocks which target under occlusion.

## Meaning of RSR-only and both-fail for the method

RSR-only cases are useful because they isolate segmentation after a correct first-grasp decision. They are the closest offline analogue of "the high-level plan was right, but the robot would still receive a poor mask." EGHC3_v3 has 79 RSR-only samples overall: 40 easy, 16 medium, and 23 hard. In the taxonomy, these correspond to `Correct ID, failed mask` and `No usable mask` categories. These are the cases that motivate point-constrained mask repair and explain why the no-mask-repair ablation mainly hurts SSR.

Both-fail cases are more fundamental. EGHC3_v3 has 324 both-fail samples overall: 26 easy, 105 medium, and 193 hard. In both-fail rows, a downstream mask improvement alone is not enough because the first-grasp object is already wrong. The concentration in medium and hard scenes explains why the next improvement should target blocker visibility, target/blocker relation evidence, and route selection rather than only segmentation.

SSR-only cases should be interpreted cautiously. The 28 SSR-only samples pass the mask threshold while failing RSR, which usually means the mask overlaps an acceptable region even though the selected first-grasp object is not acceptable under the benchmark first-grasp annotation. They are non-joint successes, not evidence of correct task execution.

## Honest limitations

1. The failure taxonomy is derived from offline FreeGraspData labels and existing saved rows. It does not prove real-robot grasp success, contact stability, or closed-loop recovery.
2. The semantic taxonomy table is currently sourced from `paper/sections/experiments.tex`; this note did not locate a standalone classifier artifact that regenerates the six category counts from raw rows. The table is therefore paper-authoritative but should be backed by a script before final submission if reviewers ask for reproducibility.
3. Hard-scene explanation is partly inferential. Existing detail rows record route mode, visibility strings, blocker relations, IoU, and RSR/SSR outcomes, but they do not always provide a normalized final target ID or final blocker ID field across all rows. Some representative examples therefore use available route/visibility/blocker evidence rather than a fully normalized causal trace.
4. EGHC3_v3 increases the offline call budget. The run manifest records 1889 reasoning calls, 900 router calls, and 59 repair calls for 900 samples, or 3.16 recorded calls per sample when router and repair calls are included. This is acceptable as an offline protocol result, but it is not a real-time robot latency measurement.
5. The current strongest controlled improvement is SSR, not RSR. Against S0, the master plan records +7.67 percentage points SSR and +3.00 percentage points RSR, with the RSR bootstrap lower bound reaching 0.00 percentage points. The discussion should keep the RSR claim cautious.

## Follow-up experiments and artifact improvements

1. Add a reproducible failure-taxonomy script that reads the existing EGHC3_v3 detail rows and benchmark first-grasp sets, then emits the six-category table with scene IDs. This would remove the current source caveat around the manuscript-only taxonomy table.
2. Run a blocker-ranking audit on existing hard and medium both-fail rows without calling any model: compare predicted blocker candidates against acceptable first-grasp sets and summarize the most common relation errors (`on-top`, `overlap`, same-class target confusion, missing blocker).
3. Add a hard-scene direct-suppression ablation only after explicit approval for new experiments. The UHS1 split-0 analysis in `docs/superpowers/analysis/2026-06-25-uhs1-split0-failure-analysis.md` showed that bad hard direct calls can be high-confidence, so a simple confidence threshold is unlikely to be sufficient.
4. Improve artifact logging for future runs: persist normalized final target ID, final blocker ID, pre-guard route, post-guard route, repair action, mask-repair source, and adjudication reason. This would make representative-case analysis auditable without parsing heterogeneous raw JSON strings.
5. Decide the real-validation path before making any embodied claim. If UR5 access is not available, the manuscript should label the next evidence as real-image offline validation rather than real-robot grasp success.

## Paper insertion block

EGHC3_v3 improves the transparency of FreeGrasp's first-grasp decision, but the failure distribution shows a clear residual bottleneck. Over 900 instructions, 431 samples are not jointly correct in both RSR and SSR. Easy-scene failures are mostly target-instance or mask-usability errors: 36 wrong-target-instance cases and 40 mask-related cases. In contrast, medium and hard scenes fail mainly before segmentation. Wrong-blocker selection and direct grasping when blocker removal is required account for 115/131 medium failures and 201/224 hard failures. Thus, the remaining challenge is not merely producing a better mask after a selected point; it is grounding the target--blocker relation under occlusion. This also explains the split-0 mask-repair ablation: removing point-constrained mask repair reduces SSR by 5.33 percentage points while leaving RSR essentially unchanged, indicating that mask repair improves segmentation consistency after the first-grasp choice, whereas blocker visibility remains the main unresolved reasoning bottleneck.

For discussion, the honest claim is that EGHC3_v3 converts direct VLM answering into an auditable routing process and yields the strongest controlled gain in SSR, but it does not yet solve hard-scene occlusion reasoning or establish real-robot success. Future work should prioritize blocker-relation evidence, normalized failure logging, and real-image or UR5 validation rather than only increasing the number of VLM calls.

## Sources used

- `docs/superpowers/plans/2026-07-04-ral-master-plan.md`: current T6 requirements, main claim boundary, EGHC3_v3 headline numbers, and planned failure-analysis content.
- `paper/sections/experiments.tex`: existing manuscript taxonomy table and per-stratum interpretation.
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/full_protocol_summary.json`: 900-sample RSR/SSR totals, per-stratum counts, call counts, manifest ID, cache SHA, and no-GT/deployable provenance.
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/run_manifest.json`: run configuration, commit, model, route guard, segmentation variant, and no-GT flags.
- `data/output/ablation_matrix/EGHC3_v3_qwen35_full/split_*/details_*.json`: metric-mode counts and representative examples.
- `docs/experiments/2026-07-02-eghc-no-mask-repair-split0.md`: no-mask-repair ablation and SSR-vs-RSR interpretation.
- `docs/experiments/2026-07-02-offline-inference-cost-summary.md`: offline call-budget framing and caveat that per-sample wall-clock latency is unavailable.
- `docs/superpowers/analysis/2026-06-25-uhs1-split0-failure-analysis.md`: prior hard-scene analysis supporting the blocker/visibility bottleneck and warning against simple confidence-threshold fixes.
