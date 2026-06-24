# Conservative Evidence Router Design

## Status

Approved direction: Option 1, conservative deterministic post-processing of
the existing predicted-geometry VLM router.

This design does not authorize paid inference. Implementation and offline
analysis must complete before requesting approval for a pilot run.

## Problem

Stage 1 showed that the structured reasoning protocols work when routing is
correct, but the deployable automatic router does not reliably select those
protocols.

The controlled original-protocol baseline S0 achieved 57.89% RSR and 47.56%
SSR. The oracle-routed diagnostic S1 achieved 67.44% RSR and 60.11% SSR.
However, the predicted-geometry automatic method S4 achieved only 45.33% RSR
and 40.56% SSR.

The principal failure is systematic overuse of the `direct` route:

- Easy scenes: 258/300 routed to `direct`, where direct grasping is usually
  appropriate.
- Medium scenes: 188/300 routed to `direct`, where direct-route RSR was only
  about 2-6%.
- Hard scenes: 155/300 routed to `direct`, where direct-route RSR was only
  about 2-8%.

The router therefore needs a conservative safety layer that prevents weak
evidence from bypassing structured target-first or blocker-first reasoning.

## Goals

1. Make route post-processing deterministic and auditable.
2. Preserve strong easy-scene direct decisions.
3. Downgrade uncertain direct decisions to `target_first`.
4. Permit `blocker_first` only when explicit physical blocking evidence is
   available.
5. Repair paired statistical analysis so all 900 evaluation rows are retained.
6. Freeze route decisions for valid single-variable reasoning ablations.
7. Evaluate candidate guards offline before requesting any paid pilot.

## Non-Goals

- Training a new router model.
- Using benchmark difficulty, ground-truth object IDs, semantic labels, or
  instance masks at inference time.
- Claiming offline replay produces new end-to-end RSR or SSR.
- Running Stage 2 fresh-cache experiments before the automatic method passes
  the pilot acceptance criteria.
- Modifying `/home/public/zb/FreeGrasp_code-main`.

## Considered Approaches

### Selected: Conservative Guard on the Existing Router

Keep the VLM router and predicted geometry, then pass its parsed decision
through a deterministic pure function. This retains image-language target
identification while preventing unsupported direct or blocker-first routes.

Advantages:

- Small implementation surface.
- Directly addresses the Stage 1 failure.
- Preserves existing manifests and route metadata.
- Can be unit-tested without API or model initialization.
- Allows raw and guarded route decisions to be compared.

### Rejected for the First Iteration: Fully Rule-Based Routing

A router based only on object count and predicted overlap would be cheap and
deterministic, but Stage 1 S2 showed that object count alone badly misroutes
easy scenes. Predicted bounding-box overlap is also noisy and cannot identify
the instructed target reliably by itself.

### Deferred: Learned Router Calibration

Training or fitting a classifier on Stage 1 decisions could improve routing,
but it introduces data-splitting, overfitting, and reporting requirements that
are unnecessary until the conservative guard has been tested.

## Architecture

The design adds four focused components:

1. A complete sample identity used by summaries and paired statistics.
2. A pure conservative route guard.
3. A frozen route audit artifact and offline analysis CLI.
4. A pilot configuration that uses the same guard in live inference.

The existing VLM router remains responsible for proposing:

- `route_mode`
- `route_confidence`
- `target_object_id`
- `target_label`
- `ambiguity_evidence`
- `blocker_evidence`

The guard receives this parsed assessment, visible Molmo IDs, object count,
and predicted geometry. It returns a guarded assessment plus structured audit
reasons. It does not call a model and does not read benchmark annotations.

## Complete Sample Identity

The current summary key `(scene_id, object_id, annotation)` collapses 900 rows
into 822 unique keys because the same semantic sample can occur in multiple
evaluation contexts.

Every loaded detail row must be enriched with:

- `split`
- `subset`
- `row_index`

The complete key is:

```text
(split, subset, row_index, scene_id, object_id, annotation)
```

Pairing must reject:

- duplicate complete keys;
- mismatched key sets;
- runs with fewer or more than 900 rows.

Scene-clustered bootstrap confidence intervals continue to resample by
`scene_id`, but pairing uses the complete key.

## Conservative Route Guard

The guard API is a pure function:

```python
apply_conservative_route_guard(
    route_assessment,
    *,
    visible_object_ids,
    object_count,
    predicted_geometry,
)
```

It returns:

```python
{
    **route_assessment,
    "route_mode": guarded_mode,
    "pre_guard_route_mode": original_mode,
    "route_guard_applied": bool,
    "route_guard_reasons": list[str],
}
```

### Valid Target Requirement

A direct decision requires `target_object_id` to be present in
`visible_object_ids`. A missing or invalid target ID always downgrades to
`target_first`.

### Confidence Requirement

A direct decision requires `route_confidence >= 0.90`.

The threshold is intentionally conservative and must remain an explicit
constant. Offline analysis may compare nearby thresholds, but changing the
selected threshold requires recording the comparison and must not use
end-to-end ground-truth success as an inference-time input.

### Ambiguity Requirement

A direct decision requires an empty `ambiguity_evidence` list. Any stated
identity, visibility, or geometric uncertainty downgrades to `target_first`.

### Blocking Requirement

A direct decision is rejected when either source contains credible physical
blocking evidence:

- router `blocker_evidence`; or
- predicted geometry involving the proposed target.

Credible evidence is limited to contact, coverage, on-top, or overlap. The
relation `near` alone is never blocking evidence.

Predicted bounding-box overlap is treated as risk evidence, not proof of the
correct blocker identity. It can prevent `direct`, but it cannot by itself
promote a route to `blocker_first`.

### Clutter Prior

Object count remains audit metadata but is not a hard direct-route threshold.
Offline Stage 1 analysis showed that easy, medium, and hard scenes have heavily
overlapping object-count distributions, so a four-object cutoff suppressed
98.8% of easy direct decisions. Object count never directly promotes
`blocker_first`.

The first pilot instead rejects `direct` when predicted target-related overlap
exceeds 0.15. On frozen S4 outputs this retains 69.8% of easy direct decisions
while suppressing 56.3% of medium/hard direct decisions.

### Blocker-First Requirement

An original `blocker_first` proposal is retained only when:

- `target_object_id` is valid;
- `blocker_evidence` is non-empty;
- at least one evidence item expresses contact, coverage, on-top, or overlap;
  and
- the evidence is not based only on `near`.

Otherwise it downgrades to `target_first`.

### Target-First Default

`target_first` is the default for:

- malformed or low-confidence router output;
- invalid target IDs;
- ambiguous target identity;
- cluttered scenes;
- unsupported direct proposals;
- unsupported blocker-first proposals.

The guard never upgrades a `target_first` proposal to another route.

## Metadata and Provenance

Each automatic detail row must preserve:

- raw router output;
- parsed pre-guard route assessment;
- guarded route assessment;
- guard threshold values;
- guard reasons;
- predicted geometry source;
- final prompt variant;
- router, reasoning, and repair call counts.

The run manifest must add:

- `route_guard_variant: conservative_v1`
- `direct_confidence_threshold: 0.90`
- `direct_max_object_count: null`
- `target_overlap_threshold: 0.15`
- `guard_code_version`

The existing cache hash, model name, token limit, git commit, and dirty
worktree fields remain mandatory.

## Frozen Route Audit

Add an offline CLI that reads an existing run such as S4 and writes one row
per complete sample key containing:

- sample identity;
- benchmark subset, for evaluation only;
- original route;
- guarded route;
- route confidence;
- target ID validity;
- ambiguity and blocker evidence;
- object count;
- relevant predicted target relations;
- guard reasons;
- original RSR and SSR.

This artifact must clearly mark benchmark subset and original RSR/SSR as
evaluation-only fields. They must not be passed into the guard.

The audit reports:

- route distribution by benchmark subset;
- original-to-guarded route transition matrix;
- direct retention rate on easy scenes;
- direct suppression rate on medium and hard scenes;
- oracle-route agreement for diagnosis;
- original S4 performance grouped by original and guarded routes.

The audit does not report guarded end-to-end RSR as if the specialized second
reasoning call had already occurred. For a downgraded direct sample, the new
first-grasp decision is unknown until a live pilot runs.

## Offline Candidate Comparison

The offline CLI compares three deterministic policies on the same frozen S4
router outputs:

1. `raw`: no guard.
2. `downgrade_all_risky_direct`: downgrade every direct proposal with four or
   more objects, ambiguity evidence, blocking evidence, low confidence, or an
   invalid target ID.
3. `conservative_v1`: the selected guard, including blocker-first validation.

Candidate selection prioritizes:

1. Medium/hard direct suppression.
2. Easy direct retention.
3. Low unsupported blocker-first rate.
4. Low additional expected reasoning-call overhead.

The selected policy must be fixed before any pilot results are inspected.

## Frozen Ablation Support

Reasoning-module ablations must share the same frozen guarded routes.

The frozen-route artifact provides the route and router assessment for every
sample. Subsequent runs may change only one of:

- blocker-first protocol availability;
- geometry consistency repair;
- invalid-ID repair.

The router must not be called again during these paired ablations. If route
keys differ, the comparison is invalid.

This replay still requires paid specialized reasoning calls when the frozen
route is `target_first` or `blocker_first`; it only removes router
nondeterminism and router-call cost.

## Pilot Design

No pilot begins without a separate paid-inference approval.

The first pilot uses 20 samples from each of the six subsets, for 120 samples
total. Samples are selected deterministically and recorded before execution.
The same fixed Molmo cache, MiMo v2.5 model, 1024-token limit, and segmentation
variant are used.

The pilot compares:

- S0 original protocol on the selected rows, replayed from existing results;
- frozen S4 raw automatic outcomes on the selected rows;
- conservative-v1 live guarded routing on the selected rows.

Acceptance criteria:

- overall guarded RSR is not below the matched S0 subset by more than 2 pp;
- medium combined RSR improves by at least 15 pp over raw S4;
- hard combined RSR improves by at least 8 pp over raw S4;
- easy combined RSR decreases by no more than 3 pp from raw S4;
- no GT feature or benchmark difficulty is used in inference;
- every selected sample has a complete audit row;
- no duplicate paid sample is issued during resume.

If these criteria are not met, Stage 2 remains blocked and the failure is
analyzed before changing thresholds.

## Error Handling

- Malformed router output defaults to `target_first`.
- Missing predicted geometry prevents `direct` in scenes with four or more
  objects but does not force `blocker_first`.
- Missing audit metadata fails offline analysis instead of silently dropping a
  row.
- Duplicate complete sample keys fail validation.
- Frozen-route key mismatch fails paired ablation execution.
- Cache or manifest mismatch stops the run before paid inference.

## Testing

### Statistical Tests

- Two rows with the same scene/object/annotation but different split or subset
  remain distinct.
- Duplicate complete keys are rejected.
- Paired bootstrap sees all 900 rows and clusters by scene.

### Guard Unit Tests

- High-confidence, valid, unambiguous, low-clutter direct remains direct.
- Low-confidence direct downgrades to target-first.
- Invalid-target direct downgrades to target-first.
- Ambiguous direct downgrades to target-first.
- Four-object direct downgrades to target-first.
- Target overlap evidence downgrades direct to target-first.
- `near` alone does not count as blocking evidence.
- Unsupported blocker-first downgrades to target-first.
- Supported blocker-first remains blocker-first.
- Target-first is never upgraded.
- The guard rejects accidental GT fields in its inputs.

### Audit Tests

- S4 produces exactly 900 audit rows.
- Offline analysis makes no network or model calls.
- Transition totals equal 900.
- Evaluation-only fields are never passed into the guard.
- Candidate comparison is deterministic.

### Integration Tests

- Live automatic routing records both pre-guard and guarded modes.
- Guarded direct still uses one VLM call.
- Downgraded direct dispatches the target-first prompt.
- Guarded blocker-first dispatches the blocker-first prompt.
- Resume preserves existing rows and does not duplicate API calls.

## Success Criteria

Implementation is ready for pilot approval when:

- all existing non-paid tests pass;
- all new guard, audit, statistics, and frozen-route tests pass;
- the S4 offline audit contains exactly 900 rows;
- the selected guard suppresses most medium/hard direct routes while retaining
  most easy direct routes;
- the route policy and pilot sample list are frozen in auditable artifacts;
- no paid inference has been triggered.

## Paper Interpretation

Until the pilot succeeds:

- S1 remains an oracle-routed diagnostic upper bound.
- S4 remains a failed automatic-router result and is not the proposed method.
- S5-S7 do not establish individual module contributions.

If the pilot succeeds and is later confirmed on all 900 samples with a fresh
cache, the method may be presented as conservative evidence-gated structured
reasoning. The oracle result should remain separately labeled.
