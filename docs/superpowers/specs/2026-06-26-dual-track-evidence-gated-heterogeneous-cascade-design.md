# Dual-Track Evidence-Gated Heterogeneous Cascade Design

Date: 2026-06-26

Branch: `experiment/routing-v2`

Status: Approved design direction.

Primary method name: `Evidence-Gated Heterogeneous Cascade v1`

Short name: `EGHC-v1`

## 1. Executive Decision

Build and evaluate two rigorously separated tracks:

1. A strict no-ground-truth main method optimized for end-to-end segmentation
   success rate (`SSR`).
2. An oracle-assisted diagnostic track used only to measure headroom and
   localize remaining errors.

The no-GT main method may use:

- RGB images;
- deployment-available depth and camera parameters;
- sanitized Molmo visible IDs and point coordinates;
- Molmo raw language output that contains no GT mapping;
- predicted SAM masks;
- predicted bounding boxes, overlaps, contact proxies, and depth order;
- at most three semantic VLM calls per sample:
  - MiMo call 1 for target and scene assessment;
  - MiMo call 2 for route-specific first-grasp planning;
  - conditional `qwen3-vl-plus-2025-12-19` call 3 for heterogeneous
    adjudication.

The main method may jointly improve:

- route selection;
- route-specific reasoning protocols;
- conflict detection and adjudication;
- ID repair;
- segmentation candidate generation;
- mask consistency checking and repair.

The primary optimization metric is end-to-end `SSR`. `RSR` remains a mandatory
diagnostic and safety constraint.

Development uses one fixed Molmo cache for paired comparisons. The final
confirmation must use a newly generated Molmo cache and all 900 evaluation
rows.

This design supersedes the main-method interpretation of:

- `2026-06-25-unified-hard-safe-protocol-v1-design.md`;
- `2026-06-26-unified-hard-safe-result-governance-design.md`;
- any claim that the existing UHS1 result is a deployable no-GT method.

It does not erase those runs. It reclassifies them according to their actual
inputs.

## 2. Critical Scientific Correction

The existing UHS1 implementation loads semantic labels and geometry from
benchmark NPZ files:

- semantic labels are derived from `instances_semantic`;
- candidate bounding boxes and overlap relations are derived from
  `instances_objects`;
- Molmo candidate parsing exposes a Molmo-to-GT mapping.

These are ground-truth-assisted features.

Therefore:

- UHS1 is an `oracle_assisted_diagnostic`, not a deployable main method;
- S1 remains an oracle diagnostic upper-bound-style experiment;
- UHS1 and S1 must not be used as the no-GT main baseline;
- the existing UHS1 `61% RSR / 53% SSR` split-0 result may be reported only
  with an explicit oracle-assisted label;
- the old `feature_source="none"` manifest entry is incorrect provenance.

Before any new routing claim, every historical run used for comparison must be
classified as one of:

```text
clean_no_gt
oracle_assisted
provenance_unknown
invalid_or_incomplete
```

Only `clean_no_gt` runs may participate in main-method selection.

## 3. Research Objective

Maximize end-to-end grasp segmentation success under deployable inference
constraints.

The main scientific question is:

```text
Can query-conditioned, no-GT evidence plus a heterogeneous three-call cascade
select and execute a better first-grasp strategy than a clean S0 baseline?
```

The primary split-0 acceptance thresholds, selected before inspecting EGHC-v1
pilot results, are:

- overall SSR improves by at least `5 percentage points` over matched clean S0;
- hard-combined SSR improves by at least `8 percentage points`;
- easy-combined SSR decreases by no more than `3 percentage points`;
- no GT feature or benchmark difficulty enters inference;
- no sample exceeds three semantic VLM calls.

These are pilot continuation gates, not final statistical claims.

## 4. Goals

1. Establish a trustworthy clean no-GT baseline.
2. Enforce a hard runtime boundary between inference evidence and scoring GT.
3. Build a query-conditioned evidence packet from deployment-available inputs.
4. Use MiMo for assessment and route-specific planning.
5. Use Qwen only for high-value conflict adjudication.
6. Compare deterministic and learned route selectors on identical frozen
   evidence.
7. Optimize final mask success, not route-label agreement alone.
8. Preserve complete raw, parsed, guarded, planned, adjudicated, and
   segmentation metadata.
9. Use paired, scene-aware validation and confidence intervals.
10. Confirm the selected method on a fresh Molmo cache and all 900 rows.

## 5. Non-Goals

- Using benchmark difficulty as an inference feature.
- Using GT object IDs, instance masks, semantic masks, or oracle object mapping
  in the main method.
- Treating offline replay as new end-to-end performance.
- Training a deep end-to-end router before simple selectors are validated.
- Allowing post-hoc threshold tuning on the final test set.
- Repeatedly rerunning failures until they succeed.
- Modifying `/home/public/zb/FreeGrasp_code-main`.

## 6. Dual-Track Architecture

### 6.1 Main Track: Strict No-GT EGHC-v1

```text
sanitized inference inputs
  -> predicted evidence builder
  -> MiMo assessment
  -> deterministic guard + learned challenger
  -> route selection
  -> MiMo route-specific planning
  -> conditional Qwen adjudication
  -> candidate mask generation
  -> no-GT mask consistency scoring
  -> final first-grasp mask
  -> isolated GT scorer
```

### 6.2 Diagnostic Track: Oracle-Assisted Upper Bound

```text
GT semantic/instance evidence
  -> oracle target and geometry diagnostics
  -> route/protocol diagnostic
  -> score and headroom analysis
```

The tracks must have:

- different subset-policy names;
- different output roots;
- different manifests;
- different feature-source enums;
- different paper table labels.

No artifact from the oracle track may be imported by the main inference
process.

## 7. Trust Boundary And GT Isolation

### 7.1 Separate Inference And Scoring Processes

The inference process must not open files containing:

- `instances_objects`;
- `instances_semantic`;
- `groundTruthObjIds`;
- GT masks;
- benchmark difficulty labels;
- Molmo-to-GT mappings.

The scorer process may read GT only after the prediction artifact is sealed.

The scorer receives:

- immutable sample identity;
- selected Molmo ID;
- predicted mask;
- prediction metadata.

The scorer returns:

- RSR;
- SSR;
- IoU;
- evaluation-only diagnostic fields.

### 7.2 Sanitized Inference Bundle

Create or validate an inference-only bundle containing:

- RGB;
- raw depth;
- camera intrinsics;
- sanitized Molmo labeled image;
- visible Molmo ID and `(x, y)` point table;
- optional raw Molmo textual description.

The sanitized point table must contain only:

```json
{
  "object_id": 3,
  "x": 512,
  "y": 384
}
```

It must not contain a GT instance ID, semantic ID, or GT-derived label.

### 7.3 Runtime GT Access Guard

Main-track entrypoints must activate a guard that rejects:

- reads from known GT NPZ roots;
- access to forbidden NPZ keys;
- feature packets containing forbidden fields;
- automatic routing with `feature_source=oracle_feature`;
- benchmark subset/difficulty passed into any inference function.

Tests must prove that accidental GT access fails loudly.

### 7.4 Feature Provenance

Every evidence field must record:

- field name;
- source type;
- source artifact hash;
- generation method;
- whether it is deployment-available;
- whether it is passed to a VLM;
- missing/error status.

Allowed main-track source types:

```text
rgb
depth
camera
molmo_visible_id
molmo_point
molmo_raw_text
predicted_sam_mask
predicted_geometry
vlm_assessment
```

Forbidden main-track source types:

```text
gt_instance
gt_semantic
gt_object_id
oracle_mapping
benchmark_difficulty
```

## 8. Complete Sample Identity

Use a stable source sample key:

```text
(split, subset, row_index, scene_id, object_id, annotation)
```

Do not include a run ID in the source sample key.

Run-specific identity is stored separately:

```text
run_id
manifest_id
attempt_id
```

All paired comparisons must:

- reject duplicate source sample keys;
- reject mismatched key sets;
- retain all expected rows;
- cluster statistical resampling by scene ID.

## 9. No-GT Evidence Packet

The evidence builder is a pure, offline-testable component.

Suggested API:

```python
build_deployable_evidence_packet(
    *,
    rgb,
    depth,
    camera,
    target_text,
    molmo_candidates,
    sam_predictor,
)
```

### 9.1 Packet Schema

```json
{
  "target_text": "the red box under the cup",
  "image_size": [1024, 1200],
  "candidates": [
    {
      "object_id": 1,
      "point": [420, 380],
      "point_valid": true,
      "mask_candidates": [],
      "selected_predicted_mask": {},
      "bbox": [100, 200, 500, 700],
      "area_ratio": 0.12,
      "depth_median": 0.73,
      "depth_spread": 0.04,
      "image_region": "center_left",
      "quality_flags": []
    }
  ],
  "relations": [
    {
      "source_id": 1,
      "target_id": 2,
      "bbox_overlap": 0.24,
      "mask_iou": 0.10,
      "contact_proxy": true,
      "coverage_proxy": 0.18,
      "depth_order": "source_in_front",
      "relation_confidence": 0.71
    }
  ],
  "scene_quality": {
    "object_count": 5,
    "missing_depth_fraction": 0.02,
    "duplicate_mask_pairs": [],
    "invalid_points": [],
    "evidence_complete": true
  },
  "provenance": {}
}
```

### 9.2 Predicted Mask Generation

For each visible Molmo point:

1. Generate point-prompted SAM masks.
2. Keep top candidates by SAM confidence.
3. Reject empty masks.
4. Mark masks with implausible area rather than silently deleting all options.
5. Detect near-duplicate masks across IDs.
6. Compute depth and geometry only from predicted masks.

No semantic class name is required to produce the initial geometric packet.

### 9.3 Relation Features

Allowed predicted relations include:

- bounding-box overlap;
- mask overlap;
- contact proxy;
- coverage proxy;
- depth front/behind order;
- center distance;
- vertical and horizontal order;
- point-to-mask containment;
- duplicate-mask suspicion.

`near` alone is never blocking evidence.

Predicted overlap may veto direct grasping but cannot by itself identify the
correct blocker.

## 10. Three-Call Heterogeneous Cascade

### 10.1 Call Budget

Each sample may use at most:

- MiMo call 1;
- MiMo call 2;
- Qwen call 3.

The third call is conditional.

Transport retries are governed separately and must not create additional
semantic decisions.

### 10.2 MiMo Call 1: Target And Scene Assessment

Input:

- RGB;
- target text;
- sanitized visible ID table;
- compact no-GT evidence packet.

Output schema:

```json
{
  "target_candidates": [
    {
      "object_id": 3,
      "identity_score": 0.82,
      "evidence": ["red appearance", "left of id 4"]
    }
  ],
  "target_visibility": "free_visible",
  "visibility_confidence": 0.78,
  "blocking_relations": [
    {
      "blocker_id": 5,
      "target_id": 3,
      "relation": "partially_covers",
      "confidence": 0.66
    }
  ],
  "blocker_candidates": [5, 2],
  "ambiguity_evidence": [],
  "recommended_route": "target_first",
  "route_confidence": 0.74
}
```

Call 1 must not:

- output a final mask;
- read GT features;
- see benchmark subset/difficulty;
- be treated as the final route without guard evaluation.

### 10.3 Route Selection Between Calls

The route selector receives:

- no-GT evidence packet;
- Call 1 assessment;
- deterministic guard result;
- optional learned challenger scores.

Candidate routes:

```text
direct
target_first
blocker_first
```

The selector returns:

```json
{
  "selected_route": "blocker_first",
  "selection_source": "guard",
  "route_scores": {},
  "guard_reasons": [],
  "challenger_disagrees": false,
  "requires_adjudication": false
}
```

### 10.4 MiMo Call 2: Route-Specific First-Grasp Planning

Call 2 receives:

- same sanitized evidence;
- Call 1 structured assessment;
- selected route;
- route-specific instructions.

Output schema:

```json
{
  "route": "blocker_first",
  "action": "remove_blocker",
  "target_object_id": 3,
  "first_grasp_object_id": 5,
  "ranked_first_grasp_candidates": [5, 2, 3],
  "mask_queries": ["yellow cup", "cup"],
  "confidence": 0.81,
  "physical_evidence": [
    "id 5 covers the top-left part of target candidate id 3"
  ],
  "uncertainty": []
}
```

Call 2 must produce:

- a valid visible ID or explicit abstention;
- a complete final plan candidate;
- short mask queries;
- evidence tied to visible IDs.

### 10.5 Qwen Call 3: Conditional Heterogeneous Adjudication

Model:

```text
qwen3-vl-plus-2025-12-19
```

Trigger if any are true:

- guard and learned challenger disagree;
- Call 1 and Call 2 disagree on target ID;
- Call 1 and Call 2 disagree on route;
- direct route fails any strong-direct condition;
- top-two target margin is below a frozen threshold;
- top-two blocker margin is below a frozen threshold;
- selected point is not contained in the selected predicted mask;
- duplicate masks make identity unstable;
- key evidence is missing;
- Call 2 emits an invalid ID;
- Call 2 confidence or consistency is below a frozen threshold.

Qwen receives:

- RGB;
- sanitized evidence packet;
- Call 1 assessment;
- route-selector result;
- Call 2 plan.

Qwen must choose one:

```text
accept_call2
replace_with_existing_candidate
downgrade_route
abstain
```

It cannot create a new object ID.

If it changes route, it must output a complete replacement plan so no fourth
VLM call is required.

## 11. Route State Machine

```text
ASSESS
  -> DIRECT_CANDIDATE
  -> TARGET_FIRST_CANDIDATE
  -> BLOCKER_FIRST_CANDIDATE
  -> PLAN
  -> ADJUDICATE_IF_NEEDED
  -> PLAN_CONFIRMED
  -> SEGMENT
  -> MASK_REPAIR
  -> FINAL
```

### 11.1 Strong Direct Requirement

Direct is allowed only when all are true:

- target identity is valid;
- target candidate is sufficiently unique;
- Call 1 says free-visible;
- no credible contact, coverage, or foreground-blocking evidence exists;
- selected target mask contains its Molmo point;
- no duplicate-mask conflict exists;
- deterministic guard permits direct;
- Call 2 selects the target itself;
- no adjudication trigger remains unresolved.

Failure of any condition prevents automatic direct.

### 11.2 Blocker-First Requirement

Blocker-first requires:

- valid target candidate;
- valid visible blocker candidate;
- at least two independent support types, for example:
  - VLM physical relation;
  - predicted contact/coverage;
  - predicted depth order;
- blocker evidence stronger than `near`;
- a segmentable blocker candidate.

If blocker evidence is insufficient, route to `target_first`.

### 11.3 Target-First Default

Target-first is the safe default for:

- ambiguous target identity without a supported blocker;
- missing or low-quality geometry;
- malformed route output;
- unsupported blocker-first proposals;
- direct proposals that fail the strong-direct gate.

### 11.4 Abstention

If no route produces a valid visible first-grasp ID:

- mark the plan as abstained;
- use a predeclared deterministic fallback;
- record failure explicitly;
- do not fabricate an ID.

The fallback policy must be frozen before paid validation.

## 12. Deterministic Guard Baseline

The deterministic guard is the required baseline and safety layer.

It must:

- validate IDs;
- reject unsupported direct;
- reject unsupported blocker-first;
- detect Call 1/Call 2 contradictions;
- request Qwen adjudication when needed;
- never read GT;
- expose structured reason codes.

Example reason codes:

```text
invalid_target_id
low_identity_margin
target_mask_point_mismatch
credible_blocking_evidence
duplicate_mask_conflict
unsupported_blocker
assessment_plan_disagreement
evidence_incomplete
```

All thresholds must be explicit constants stored in the manifest.

## 13. Learned Route Challenger

The learned selector is a challenger, not an assumed improvement.

### 13.1 Prediction Target

For each candidate route, predict:

```text
P(SSR success | no-GT evidence, Call 1 assessment, candidate route)
```

Also predict auxiliary:

```text
P(RSR success | ...)
```

SSR is the primary selection score.

### 13.2 Candidate Models

Compare:

- calibrated logistic regression;
- gradient-boosted trees;
- random forest as a robustness baseline.

Do not use a deep selector in v1.

### 13.3 Training Data Eligibility

Training rows must come only from:

- clean no-GT runs;
- exact source sample keys;
- fixed-cache protocol executions with known manifests;
- routes whose actual executed protocol is known.

Exclude:

- S1;
- UHS1;
- any oracle-assisted run;
- provenance-unknown rows;
- mixed-cache comparisons;
- duplicate scene leakage across folds.

### 13.4 Protocol Coverage Requirement

A route-outcome training table is valid only if enough samples have comparable
outcomes for candidate protocols.

If historical clean runs do not provide adequate route coverage:

- do not synthesize missing labels;
- do not use oracle outcomes as labels;
- keep the deterministic guard as the selected router;
- propose a separately approved clean protocol-calibration experiment.

### 13.5 Splitting And Leakage Control

All selector evaluation must be scene-grouped.

Required views:

- scene-grouped cross-validation;
- held-out benchmark split;
- out-of-distribution diagnostics;
- row-random CV only as a leakage diagnostic.

No scene may appear in both training and validation folds.

### 13.6 Calibration And Abstention

Report:

- Brier score;
- expected calibration error;
- route accuracy only as a secondary metric;
- SSR regret against the clean replay oracle;
- abstention/adjudication rate.

The learned selector must defer to the deterministic guard when:

- out of distribution;
- prediction confidence is low;
- top-two route margin is small;
- required features are missing.

### 13.7 Challenger Promotion Gate

Promote the learned challenger only if, on frozen scene-held-out data:

- estimated selected SSR exceeds deterministic guard SSR by at least `2 pp`;
- hard-combined estimated SSR does not decrease;
- easy-combined estimated SSR does not decrease by more than `2 pp`;
- calibration is acceptable under predeclared limits;
- no forbidden feature has nonzero importance or appears in input data;
- results are stable across scene-grouped folds.

Otherwise EGHC-v1 uses the deterministic guard.

## 14. Candidate Comparison

Compare three router candidates on identical frozen evidence:

1. `guard_only`
2. `learned_only_with_abstention`
3. `hybrid_guard_plus_challenger`

Selection priority:

1. held-out SSR;
2. hard SSR;
3. easy non-regression;
4. calibration;
5. Qwen adjudication rate;
6. total call cost.

The selected router must be frozen before live pilot outcomes are inspected.

## 15. Segmentation And Mask Repair

### 15.1 Candidate Query Set

Generate segmentation candidates from:

- Call 2/Qwen short mask queries;
- selected Molmo point;
- generic object fallback phrase only when necessary.

Do not use GT semantic labels.

### 15.2 Candidate Mask Score

Score masks using no-GT criteria:

- contains selected Molmo point;
- SAM confidence;
- area plausibility;
- depth compactness;
- depth boundary agreement;
- consistency with predicted bbox;
- duplicate-mask penalty;
- consistency across query variants;
- consistency with selected candidate ID.

### 15.3 Repair Sequence

1. Segment the selected first-grasp candidate.
2. Try all frozen query variants.
3. Prefer masks containing the selected point.
4. Reject or penalize implausibly large and duplicate masks.
5. If selected candidate remains unsegmentable, try the next ranked candidate
   only when the plan explicitly permits candidate fallback.
6. Stop after a frozen maximum number of local segmentation attempts.

Local segmentation attempts do not consume VLM calls.

### 15.4 Segmentation Challenger

Compare:

- existing `point_retry`;
- point plus depth consistency;
- multi-query consensus;
- ranked-candidate mask repair.

Use frozen route and plan artifacts so segmentation ablations do not rerun VLMs.

## 16. Oracle Diagnostic Track

The oracle track may use:

- GT semantic labels;
- GT instance masks;
- Molmo-to-GT mappings;
- benchmark difficulty;
- oracle route labels.

Required diagnostic outputs:

- oracle target identification upper bound;
- oracle route upper bound;
- oracle blocker-selection upper bound;
- oracle segmentation upper bound;
- gap decomposition:
  - perception/evidence gap;
  - routing gap;
  - planning gap;
  - segmentation gap.

Oracle results must never:

- train the main selector;
- set main thresholds;
- select the final main candidate;
- appear in the main-method row without an oracle label.

## 17. Historical Run Audit

Before building a baseline registry, audit every candidate historical run.

For each run record:

- source path;
- row count;
- model;
- prompt;
- cache hash;
- actual feature-source code path;
- GT access evidence;
- route implementation;
- split coverage;
- API error count;
- classification:
  - `clean_no_gt`;
  - `oracle_assisted`;
  - `provenance_unknown`;
  - `invalid_or_incomplete`.

At minimum audit:

- S0;
- S1;
- S4;
- S5-S7;
- depth-classifier experiments;
- UHS1;
- prior scene-complexity routers.

Do not trust manifest labels without code-path verification.

## 18. Clean S0 Baseline

S0 is the comparison baseline only if it passes:

- no forbidden GT reads;
- sanitized Molmo input;
- complete 900-row identity;
- fixed cache hash;
- valid manifest;
- clean commit;
- reproducible command.

If historical S0 fails any item, rerun a clean S0.

Clean S0 must use:

- same MiMo model and endpoint as EGHC-v1 where applicable;
- same maximum output tokens;
- same fixed Molmo cache;
- same segmentation baseline selected for the comparison definition;
- same API retry policy.

## 19. Artifact And Provenance Contract

Each main-track detail row must preserve:

- source sample key;
- inference bundle hash;
- raw evidence packet;
- Call 1 raw and parsed output;
- guard decision;
- learned challenger scores;
- selected route;
- Call 2 raw and parsed output;
- Qwen trigger reasons;
- Qwen raw and parsed output, when called;
- final plan;
- segmentation attempts;
- selected mask metadata;
- semantic VLM call count;
- transport attempt count;
- API errors;
- RSR/SSR only in scorer-owned evaluation fields.

The run manifest must include:

- clean Git commit;
- `dirty_worktree=false`;
- environment lock hash;
- model endpoints;
- exact model names;
- prompt text hashes;
- parser/guard/planner/segmenter source hashes;
- SAM and other checkpoint hashes;
- cache hash;
- dataset identity hash;
- threshold configuration;
- random seeds;
- route candidate selected;
- maximum VLM calls;
- Qwen trigger policy version.

Main experimental runs must not execute from a dirty worktree.

## 20. Raw Artifact Sealing

After inference:

1. Write prediction artifacts atomically.
2. Compute file hashes.
3. Write a seal manifest.
4. Prevent resume from changing completed rows.
5. Run scoring only against sealed predictions.

Raw predictions must remain immutable.

Derived audit and summary artifacts go into separate directories.

## 21. API Failure And Retry Policy

### 21.1 Predeclared In-Run Retry

For retryable transport or provider `5xx` errors:

- freeze a maximum attempt count before the run;
- use the same policy for S0 and EGHC-v1;
- accept the first valid response;
- never inspect RSR/SSR before deciding to retry;
- record every attempt.

Recommended initial policy:

```text
one initial request + one transport retry per logical call
```

The semantic VLM call budget remains three logical calls.

### 21.2 Exhausted Errors

If the predeclared retry policy is exhausted:

- record an API failure row;
- count it as failure in the primary intention-to-treat result;
- do not repeatedly rerun it into success.

### 21.3 Post-Hoc Sensitivity Reruns

Post-hoc reruns may be reported as a separate service-reliability sensitivity
analysis.

They must not replace the primary paper result.

## 22. Development And Validation Data Discipline

### 22.1 Fixed Cache Development

Use one sealed Molmo cache for:

- evidence builder development;
- offline threshold comparison;
- route candidate comparison;
- paired split-0 pilot;
- frozen-plan segmentation ablations.

### 22.2 Scene-Disjoint Selector Evaluation

Construct scene-disjoint folds across available clean rows.

Record:

- scene IDs per fold;
- benchmark split per row;
- duplicate semantic sample audit;
- train/validation/test membership.

### 22.3 Final Test Protection

The final held-out set must not be used for:

- threshold tuning;
- model selection;
- prompt editing;
- Qwen trigger tuning;
- segmentation scoring-weight tuning.

Fresh-cache 900 evaluation is a robustness confirmation over all rows, not a
substitute for the scene-held-out selector test.

## 23. Offline Validation Phases

No paid reasoning experiment begins until Phases 0-4 pass.

### Phase 0: Provenance Triage

Deliver:

- historical run registry;
- GT leak report;
- corrected labels for UHS1/S1;
- clean S0 decision.

Gate:

- every comparison run classified;
- no unknown provenance in main comparisons.

### Phase 1: GT Isolation Tests

Deliver:

- sanitized inference bundle;
- runtime GT access guard;
- forbidden-field scanner.

Gate:

- all deliberate GT-access tests fail;
- scorer still computes RSR/SSR from sealed predictions.

### Phase 2: Evidence Builder Audit

Deliver:

- evidence packets for all fixed-cache rows;
- completeness and quality report;
- runtime and storage report.

Gate:

- exactly expected row count;
- deterministic regeneration;
- no GT-derived fields;
- missing evidence rate below a frozen tolerance.

### Phase 3: Router Offline Comparison

Compare guard-only, learned-only, and hybrid on frozen evidence.

Report:

- selected route distribution;
- route transitions;
- estimated replay SSR/RSR only where comparable labels exist;
- hard direct suppression;
- easy direct retention;
- calibration;
- OOD and abstention rate;
- expected Qwen call rate.

Gate:

- selected candidate fixed before live outcomes;
- learned candidate promoted only if challenger gate passes.

### Phase 4: Local Segmentation Replay

Using frozen selected IDs and plans:

- compare mask repair candidates;
- report no-GT mask diagnostics;
- never claim new reasoning success.

Gate:

- selected segmentation policy frozen before live pilot.

## 24. Paid Experiment Sequence

Every paid phase requires separate user approval.

### Phase A: Model And Endpoint Preflight

Run one non-benchmark image-input preflight per model:

- MiMo model;
- `qwen3-vl-plus-2025-12-19`.

Confirm:

- vision input support;
- response schema;
- endpoint;
- token parameter;
- thinking configuration;
- error handling.

### Phase B: Deterministic Hard/Easy Smoke

Select and freeze a small diagnostic list before execution:

- easy control samples;
- medium transition samples;
- hard no-ambiguity samples;
- hard ambiguity samples.

The smoke checks:

- no GT access;
- Call 1 schema;
- route guard behavior;
- Call 2 schema;
- Qwen trigger behavior;
- call budget;
- metadata completeness;
- segmentation trace.

Smoke is operational validation, not performance evidence.

### Phase C: Fixed-Cache Split-0 Pilot

Run matched:

- clean S0;
- EGHC-v1 selected router;
- oracle diagnostic separately.

Use all 300 split-0 rows.

Continuation gates:

- overall SSR: EGHC-v1 at least S0 `+5 pp`;
- hard-combined SSR: at least S0 `+8 pp`;
- easy-combined SSR: no worse than S0 `-3 pp`;
- no GT access;
- complete 300-row audit;
- maximum three semantic VLM calls per sample;
- API retry policy identical between S0 and EGHC-v1.

If any gate fails:

- stop;
- analyze;
- do not tune on the same pilot outcomes without declaring a new method
  version and a new validation boundary.

### Phase D: Frozen-Plan Ablations

Only after Phase C passes.

Candidate ablations:

- no Qwen adjudication;
- no learned challenger;
- no deterministic guard;
- no depth evidence;
- no predicted geometry;
- no mask repair;
- one-call assessment/planning;
- MiMo-only third call instead of Qwen;
- no blocker-first route.

Where possible, freeze upstream artifacts so each ablation changes one
component.

### Phase E: Held-Out Fixed-Cache Validation

Run the frozen final candidate on the predeclared held-out scene set.

No prompt, threshold, model, or segmentation changes after inspection.

### Phase F: Fresh-Cache Full 900 Confirmation

Generate one new Molmo cache.

Seal and hash it before reasoning.

Run matched:

- clean S0;
- frozen EGHC-v1;
- optional oracle diagnostics in a separate namespace.

Required final reporting:

- paired SSR and RSR over 900 rows;
- per-subset results;
- easy/medium/hard combined results;
- scene-clustered confidence intervals;
- API failure rate;
- average and percentile VLM call count;
- Qwen adjudication rate;
- latency and cost;
- raw and sealed manifests.

## 25. Statistical Analysis

Primary outcome:

```text
paired SSR difference: EGHC-v1 - clean S0
```

Secondary outcomes:

- paired RSR difference;
- hard SSR and RSR;
- easy non-regression;
- per-subset results;
- Qwen-triggered vs non-triggered outcomes;
- route-conditioned outcomes;
- failure attribution.

Use:

- complete source sample keys for pairing;
- scene-clustered bootstrap confidence intervals;
- paired binary tests as secondary diagnostics;
- no row-random uncertainty estimate.

Report both:

- absolute percentage-point difference;
- 95% confidence interval.

Do not use oracle results in the main statistical comparison.

## 26. Failure Attribution

Every failed sample receives exactly one primary category:

```text
F0_api_or_incomplete
F1_target_identity
F2_route_selection
F3_blocker_selection
F4_plan_invalid_or_inconsistent
F5_segmentation
F6_gt_scoring_or_mapping_anomaly
```

Auxiliary tags may include:

- duplicate predicted masks;
- missing depth;
- low target margin;
- low blocker margin;
- Qwen disagreement;
- point not in mask;
- API retry exhausted.

Primary categories must be mutually exclusive.

## 27. Required Tests

### 27.1 GT Isolation

- Main inference rejects GT NPZ roots.
- Main inference rejects `instances_objects`.
- Main inference rejects `instances_semantic`.
- Main inference rejects Molmo-to-GT mappings.
- Benchmark subset/difficulty never enters route or plan functions.
- Oracle entrypoint remains available only under an explicit oracle policy.

### 27.2 Evidence Builder

- Deterministic packet from fixed inputs.
- Point-prompted masks use no GT.
- Duplicate-mask detection works.
- Depth features handle missing and invalid pixels.
- `near` alone is not blocker evidence.
- Packet provenance covers every field.

### 27.3 VLM Schemas

- Call 1 valid schema.
- Call 1 malformed output fails safely.
- Call 2 uses only visible IDs.
- Call 2 outputs complete replacement candidates.
- Qwen cannot create a new ID.
- Qwen route change includes a complete final plan.

### 27.4 Route State Machine

- Strong direct remains direct.
- Weak direct is downgraded.
- Supported blocker-first remains blocker-first.
- Unsupported blocker-first becomes target-first.
- Conflict triggers Qwen.
- Non-conflict skips Qwen.
- No path exceeds three semantic VLM calls.
- Abstention is explicit.

### 27.5 Learned Challenger

- Forbidden features are rejected.
- Scene grouping prevents leakage.
- Missing protocol labels are not synthesized.
- Calibration metrics are deterministic.
- Promotion gate is enforced.
- Guard overrides low-confidence/OOD challenger output.

### 27.6 Segmentation

- Selected point containment is preferred.
- Huge-mask penalty works.
- Duplicate-mask penalty works.
- Depth consistency affects ranking as specified.
- Ranked-candidate fallback obeys the plan.
- Frozen local attempts are bounded.

### 27.7 Artifacts And Resume

- Complete sample keys remain distinct.
- Duplicate keys fail.
- Completed rows are immutable.
- Resume does not issue duplicate paid calls.
- Raw artifacts are atomically written and sealed.
- Scoring cannot modify predictions.
- Manifest rejects dirty main runs.

### 27.8 API Reliability

- Predeclared 5xx retry accepts first valid response.
- Retry exhaustion remains a failure.
- Post-hoc rerun cannot alter primary results.
- S0 and EGHC use identical retry policy.

### 27.9 Integration

- Synthetic end-to-end sample exercises all three VLM stages with mocked
  clients.
- Direct path uses two calls when no Qwen trigger exists.
- Adjudicated path uses exactly three calls.
- Scorer computes metrics only after prediction sealing.
- Offline audits make no network calls.

## 28. Implementation Boundaries

Recommended focused modules:

```text
deployable_evidence.py
gt_access_guard.py
eghc_router.py
eghc_schemas.py
eghc_adjudicator.py
eghc_segmentation.py
eghc_artifacts.py
audit_historical_runs.py
audit_eghc_offline.py
train_eghc_challenger.py
run_eghc_pilot.py
score_sealed_predictions.py
```

Avoid placing the full cascade in `utils/utils.py`.

Existing entrypoints may call these modules, but the core decision logic should
be pure and independently testable.

## 29. Suggested Policy And Variant Names

Main:

```text
subset_policy=eghc_v1
routing_variant=evidence_gated_cascade
feature_source=deployable_predicted
segmentation_variant=eghc_mask_repair_v1
```

Rule baseline:

```text
subset_policy=eghc_guard_only_v1
```

Learned challenger:

```text
subset_policy=eghc_hybrid_v1
```

Oracle:

```text
subset_policy=eghc_oracle_diagnostic_v1
feature_source=oracle_feature
```

## 30. Stop Conditions For The Implementing Agent

Stop immediately and report if:

- any main-track code reads GT instance or semantic data;
- sanitized Molmo inputs still contain GT mapping;
- S0 provenance cannot be established;
- route training data mixes oracle and clean rows;
- scene groups overlap across train/validation folds;
- offline analysis silently drops rows;
- a paid command is about to run without explicit approval;
- a main run is launched from a dirty worktree;
- a sample can exceed three semantic VLM calls;
- post-hoc retries would alter primary results;
- final test outcomes are used to retune the method.

## 31. Success Criteria

Implementation is ready for a paid split-0 pilot when:

- historical runs are classified;
- clean S0 is established;
- GT isolation tests pass;
- evidence packets exist for every fixed-cache pilot row;
- router candidate is frozen;
- segmentation policy is frozen;
- all local tests pass;
- no paid inference has been triggered.

EGHC-v1 advances beyond split 0 only when:

- overall SSR is at least clean S0 `+5 pp`;
- hard SSR is at least clean S0 `+8 pp`;
- easy SSR is no worse than clean S0 `-3 pp`;
- no GT leakage occurs;
- artifacts are complete and sealed.

The final method is reportable only after:

- held-out scene validation;
- fresh-cache matched S0 comparison;
- all 900 rows complete;
- paired scene-clustered analysis;
- oracle and main tracks remain clearly separated.

## 32. Paper Interpretation

Until fresh-cache confirmation:

- EGHC-v1 is an experimental no-GT candidate.
- UHS1 is an oracle-assisted diagnostic.
- S1 is an oracle diagnostic.
- old automatic routers remain failed or preliminary baselines.

After successful confirmation:

- EGHC-v1 may be presented as the main deployable method;
- oracle diagnostics may be shown as upper bounds;
- every table must identify cache policy, feature source, and call budget;
- service-reliability sensitivity analyses remain secondary.

## 33. Required Handoff Execution Order

The implementing agent must follow this order:

1. Confirm branch and dirty-worktree state.
2. Audit historical run provenance.
3. Reclassify UHS1 and S1 as oracle-assisted diagnostics.
4. Establish or rerun clean S0.
5. Implement GT isolation and sanitized inference inputs.
6. Implement and test the no-GT evidence builder.
7. Implement Call 1 and its schema parser.
8. Implement deterministic guard and route state machine.
9. Implement Call 2 route-specific planners.
10. Implement conditional Qwen adjudication.
11. Implement no-GT segmentation repair.
12. Implement sealed artifacts and isolated scoring.
13. Build frozen evidence and offline audits.
14. Train and evaluate the learned challenger only if eligible clean labels
    exist.
15. Freeze router, thresholds, Qwen triggers, prompts, and segmentation policy.
16. Run the complete local test suite.
17. Stop and request paid approval for model preflight and smoke.
18. Stop after each paid phase and report its gate result.

The agent must not reorder steps 2-5. A router built before GT isolation and a
clean baseline would optimize against invalid evidence.

## 34. Required Deliverables

Before paid approval:

```text
docs/experiments/eghc_v1_historical_run_audit.md
data/output/eghc_v1/historical_run_registry.json
data/output/eghc_v1/clean_s0_manifest.json
data/output/eghc_v1/fixed_cache_manifest.json
data/output/eghc_v1/evidence_manifest.json
data/output/eghc_v1/offline_router_audit.json
data/output/eghc_v1/offline_segmentation_audit.json
data/output/eghc_v1/frozen_policy.json
```

The frozen policy must include:

- selected router candidate;
- all guard thresholds;
- learned model hash if promoted;
- Call 1 and Call 2 prompt hashes;
- Qwen prompt and trigger policy hash;
- segmentation scoring weights;
- maximum local mask attempts;
- API retry policy;
- pilot sample or split definition.

After split-0 pilot:

```text
data/output/eghc_v1_split0/run_manifest.json
data/output/eghc_v1_split0/prediction_seal.json
data/output/eghc_v1_split0/paired_summary.json
docs/experiments/eghc_v1_split0_report.md
```

After fresh-cache 900 confirmation:

```text
data/output/eghc_v1_fresh900/cache_manifest.json
data/output/eghc_v1_fresh900/s0/run_manifest.json
data/output/eghc_v1_fresh900/eghc/run_manifest.json
data/output/eghc_v1_fresh900/paired_statistics.json
docs/experiments/eghc_v1_fresh900_final_report.md
```

Every report must state:

- whether inference was clean no-GT or oracle-assisted;
- model names and call budget;
- cache policy;
- API failure policy;
- exact row count;
- matched baseline;
- acceptance gate pass/fail;
- whether further paid execution remains blocked.
