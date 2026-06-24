# Target-Conditioned Evidence Handoff V2 Design

## Status

Approved direction: repair the evidence handoff between the automatic router
and the existing FreeGrasp v10 expert protocols before introducing depth.

This design does not authorize paid inference. Implementation, unit tests, and
the offline evidence audit must complete before requesting approval for a
paired pilot.

## Problem

The strongest confirmed FreeGrasp configuration is the subset-conditioned
`hard_blocker_first_v10` policy:

- RSR: 67.67% (609/900)
- SSR: 60.33% (543/900)
- model: `mimo-v2.5`
- maximum output tokens: 1024
- Molmo policy: reuse the existing cache

That result is an oracle-routed reference. It knows whether each benchmark
sample is easy, medium, or hard and uses annotation-derived semantic and
geometric features. The deployable automatic method must instead infer the
route from predicted evidence without benchmark difficulty or ground-truth
features.

The first conservative automatic pilot showed that simply suppressing risky
`direct` decisions is insufficient. A subsequent 25-sample paired pilot
changed overlap-triggered `target_first` decisions to the existing v10
`blocker_first` protocol:

- target-first: 7/25 RSR and 7/25 SSR
- blocker-first: 9/25 RSR and 9/25 SSR
- paired changes: two wins, zero losses
- medium: 7/17 to 9/17 RSR
- hard: 0/8 to 0/8 RSR

The target proposed by the router was correct for 24/25 samples. The dominant
failure was therefore not target localization. The predicted overlap
shortlist contained an acceptable first-grasp object in only 12/25 samples and
in only 1/8 hard samples.

The current evidence path has four concrete defects:

1. Pairwise relations are emitted in both directions, so the same pair appears
   once as `above` and once as `below`.
2. The prompt includes only the first 24 global relations, which can omit all
   relations involving the routed target.
3. Different Molmo points can produce nearly identical SAM masks, causing a
   duplicate instance or mask swap to appear as overlap evidence.
4. The route assessment records target and blocker metadata, but the
   specialized reasoning prompt does not receive a compact, explicit,
   target-conditioned evidence packet.

The next iteration must fix this evidence representation and transfer rather
than add another prompt-only verifier or tune the overlap threshold.

## Goals

1. Preserve the existing v10 expert protocols as the reasoning backbone.
2. Construct a deterministic evidence packet centered on the router's target
   hypothesis.
3. Remove symmetric duplicates and ambiguous relation wording.
4. Detect duplicate-mask evidence and prevent it from proving obstruction.
5. Ensure target-related candidates are always visible to the specialized
   prompt and are never lost through global relation truncation.
6. Separate geometric risk from verified physical blocker evidence.
7. Validate blocker-candidate recall offline before any paid inference.
8. Keep the automatic path free of benchmark difficulty and ground-truth
   features.

## Non-Goals

- Adding RGB-D depth in this iteration.
- Training a learned router or blocker classifier.
- Replacing the v9 medium or v10 hard prompt schemas.
- Treating 2D bounding-box or mask overlap as proof of physical contact.
- Improving Molmo candidate generation.
- Running a new 900-sample experiment before the small paired pilot passes.
- Modifying `/home/public/zb/FreeGrasp_code-main`.

## Considered Approaches

### Selected: Target-Conditioned Evidence Handoff

Keep the current target proposal and v10 expert protocols, but normalize
predicted geometry into a compact target-centered packet. The packet presents
ranked obstruction-risk candidates, explicit reliability flags, and image
coordinates to the reasoning model.

This approach directly addresses the observed failure, retains compatibility
with the highest-performing protocol, and can be audited without model calls.

### Rejected: Continue Tuning Route Thresholds

Changing the confidence or overlap threshold can alter how often a route is
used, but it cannot repair a blocker shortlist whose hard-scene recall is
1/8. Threshold tuning would optimize the frequency of consuming unreliable
evidence rather than improve the evidence itself.

### Deferred: Add Depth-Aware Occlusion

Depth is the most plausible next extension if 2D predicted evidence remains
insufficient. It can represent front-to-back ordering that image-space
vertical position cannot. It is deferred so that existing relation
duplication, truncation, and handoff bugs are not hidden inside a larger RGB-D
method change.

## Architecture

V2 adds four bounded components:

1. `normalize_candidate_relations`: canonicalizes pairwise predicted geometry.
2. `detect_duplicate_mask_candidates`: labels unreliable same-instance mask
   pairs.
3. `build_target_evidence_packet`: ranks candidates relative to one routed
   target.
4. `format_target_evidence_packet`: injects the packet into target-first and
   blocker-first reasoning input.

The inference flow becomes:

```text
RGB + instruction
  -> Molmo IDs and points
  -> point-prompted SAM candidate masks
  -> normalized candidate geometry
  -> automatic target hypothesis
  -> target-conditioned evidence packet
  -> conservative route guard
  -> existing v10 expert protocol
  -> point-constrained LangSAM segmentation
```

The packet is computed once per sample and stored in reasoning metadata. The
router consumes the normalized scene-level candidate summary. After it
proposes a target, the route guard and specialized reasoner consume the same
target-conditioned packet derived from that summary.

## Canonical Relation Representation

Raw directed relations are replaced by one canonical record for each unordered
candidate pair. When a target is known, the record is rendered from the
target's perspective:

```json
{
  "target_id": 9,
  "candidate_id": 5,
  "bbox_overlap_smaller": 0.252,
  "bbox_target_coverage": 0.131,
  "mask_iou": 0.041,
  "point_distance_normalized": 0.218,
  "candidate_image_position": "upper_left",
  "duplicate_mask_suspect": false
}
```

`candidate_image_position` describes only 2D image position. Terms such as
`on_top`, `above_target`, or `physical_contact` must not be generated from the
image y-coordinate. This prevents an image-coordinate relation from being
misread as depth or support order.

The canonical relation list must be deterministic:

- candidate IDs are unique;
- numeric fields use stable rounding only when formatted for the prompt;
- ties are resolved by candidate ID;
- no pair can appear twice with opposite direction labels.

## Duplicate-Mask Detection

Point-prompted SAM can return the same physical instance for different Molmo
points. Such pairs are evidence of candidate uncertainty, not obstruction.

A pair is marked `duplicate_mask_suspect` when either condition holds:

- mask IoU is at least 0.85; or
- bounding-box overlap over the smaller box is at least 0.95 and both masks
  contain both Molmo points.

The exact thresholds are explicit configuration constants. The offline audit
must report nearby threshold sensitivity, but end-to-end RSR must not be used
as an inference-time feature.

A duplicate suspect:

- cannot by itself promote `blocker_first`;
- cannot be described as a physical blocker;
- is retained in metadata as an ambiguity warning;
- can force `direct` to fall back to `target_first`.

## Target-Conditioned Evidence Packet

The packet API is a pure function:

```python
build_target_evidence_packet(
    *,
    target_id,
    visible_object_ids,
    predicted_geometry,
    max_candidates=3,
)
```

It returns:

```json
{
  "target_id": 9,
  "target_valid": true,
  "target_point": [736, 890],
  "target_bbox": [596, 774, 838, 946],
  "risk_candidates": [],
  "duplicate_mask_candidates": [],
  "evidence_reliability": "usable",
  "warnings": []
}
```

Candidates are ranked using predicted, target-relative quantities:

1. non-duplicate candidates before duplicate suspects;
2. greater target-box coverage;
3. greater overlap over the smaller box;
4. smaller normalized point distance;
5. lower candidate ID as a deterministic tie-break.

The shortlist contains at most three candidates. It is a list of
`obstruction-risk candidates`, not asserted blockers. The RGB image remains
the source used by the VLM to decide whether a candidate physically covers or
blocks access to the target.

If no overlap candidate is available, the packet may include the nearest
non-duplicate candidates so that thin objects, cables, and partial masks are
not silently omitted. Every candidate states why it was included:
`target_coverage`, `bbox_overlap`, or `nearest_fallback`.

## Prompt Handoff

The specialized reasoning input receives a dedicated section before the
general candidate table:

```text
Router target hypothesis:
- target_id=9
- target_point=(736, 890)
- treat this as a hypothesis to verify against the RGB image

Target-conditioned obstruction-risk candidates:
- id=5, included_by=target_coverage, target_coverage=0.131,
  overlap=0.252, image_position=upper_left, duplicate_mask=false

Reliability warnings:
- 1 and 3 may be duplicate masks of one physical instance
```

The prompt rules must state:

- the routed target is a strong hypothesis, not an unquestionable label;
- risk candidates are not automatically blockers;
- a blocker requires visible image support for coverage, contact, or access
  obstruction;
- duplicate-mask suspects cannot be selected solely because of overlap;
- candidates outside the shortlist remain legal when the RGB image clearly
  supports them;
- `near` and image-space vertical position alone are insufficient.

The full global pairwise relation list is removed from the reasoning prompt.
Every shortlisted target-conditioned record is included, and shortlist
construction processes all target relations before applying the three-item
cap. Evidence quality therefore no longer depends on the target's numeric ID
or position in a global relation list.

## Route Guard V2

The guard remains conservative:

- a valid, confident, unambiguous target with no target risk may remain
  `direct`;
- duplicate-mask uncertainty or weak target risk downgrades `direct` to
  `target_first`;
- `blocker_first` is retained only when the router reports explicit physical
  blocker evidence and the packet contains at least one non-duplicate risk
  candidate;
- predicted 2D overlap alone never upgrades a route to `blocker_first`;
- unsupported or conflicting evidence defaults to `target_first`.

The first implementation must not use object count as a hard route boundary.

## Metadata

Every detail row records:

- raw predicted geometry;
- normalized canonical relations;
- target evidence packet;
- packet configuration thresholds;
- pre-guard and final route;
- route-guard reasons;
- packet reliability and warnings;
- prompt variant and selected first-grasp ID;
- router, reasoning, and repair call counts.

The run manifest adds:

- `route_guard_variant: target_evidence_v2`
- `target_evidence_max_candidates: 3`
- duplicate-mask thresholds;
- evidence formatter version;
- cache hash, model, token limit, commit, and dirty-worktree state.

## Offline Audit

The first audit replays the frozen 25 overlap-triggered samples without API,
MiMo, LangSAM, or paid calls. Ground-truth first-grasp IDs are used only after
packet construction to measure candidate recall.

Report:

- routed-target accuracy;
- top-1 and top-3 acceptable blocker recall;
- recall by medium and hard difficulty for diagnosis;
- duplicate-mask suspect frequency;
- nearest-fallback frequency;
- candidate inclusion reasons;
- examples where the acceptable blocker is absent;
- proof that no evaluation-only field enters packet construction.

The audit also runs over all 900 frozen S4 rows to report packet availability
and route-transition counts. It must not estimate new RSR or SSR.

## Offline Acceptance Gate

The 25-sample audit must satisfy all of the following before requesting paid
inference:

- exactly 25 complete, unique sample keys;
- routed-target accuracy remains at least 24/25;
- top-3 acceptable first-grasp recall is at least 17/25 overall;
- hard top-3 recall is at least 4/8;
- no target relation is omitted because of a global list limit;
- every duplicate-mask suspect is excluded as standalone blocker proof;
- packet construction reads no benchmark subset, GT ID, ground-truth instance
  mask, ground-truth semantic mask, or occlusion annotation.

If hard recall remains below 4/8, the RGB-only evidence path is considered
insufficient and the next design should evaluate depth-aware occlusion rather
than continue prompt or threshold tuning.

## Paid Pilot Gate

A paid pilot requires a new explicit approval after the offline gate passes.
It reuses the same 25 sample identities and Molmo cache for a paired comparison:

- P0: existing target-first outcomes;
- P1: target-conditioned evidence handoff with conservative routing and the
  existing v10 expert prompts.

Pilot continuation criteria:

- P1 improves RSR by at least two samples over P0;
- P1 produces at least two hard-scene reasoning successes;
- P1 does not turn more than one P0 reasoning success into a failure;
- no GT feature or benchmark difficulty is consumed during inference;
- cache hash, model, token limit, and sample keys match;
- failed API calls are recorded and retried only through an explicit
  sample-level recovery artifact.

Passing the pilot authorizes only a larger confirmation proposal, not an
automatic 900-sample run.

## Error Handling

- Invalid or missing target ID yields an empty packet and `target_first`.
- Missing predicted geometry yields `target_first` with
  `missing_predicted_geometry`.
- An all-duplicate shortlist yields `target_first` with
  `duplicate_only_evidence`.
- Non-finite geometry values are rejected rather than silently ranked.
- More than one canonical record for a target-candidate pair fails validation.
- Manifest or cache mismatch stops execution before model calls.
- Resume must not issue a second paid request for a completed sample.

## Testing

### Relation Tests

- A directed pair produces exactly one canonical record.
- Reversing input relation order produces identical output.
- Image y-position is never formatted as physical `on_top` evidence.
- Target-related records are not lost when the raw list exceeds 24 entries.

### Duplicate Tests

- High mask IoU marks a duplicate suspect.
- High bbox overlap without cross-point containment does not automatically
  mark a duplicate.
- Duplicate suspects cannot support `blocker_first`.
- Duplicate uncertainty can downgrade `direct` to `target_first`.

### Packet Tests

- The packet contains only valid visible IDs.
- Ranking is deterministic.
- The shortlist is capped at three.
- Nearest fallback is labeled explicitly.
- GT-like keys in any input are rejected.
- Invalid target and missing geometry produce auditable empty packets.

### Prompt Tests

- Target-first and blocker-first prompts contain the full packet.
- General relations are not truncated into a misleading subset.
- Risk candidates are described as hypotheses, not verified blockers.
- Existing v9/v10 JSON parsers remain compatible.

### Integration Tests

- Automatic inference records the packet and final route.
- Frozen-route replay bypasses the router but uses the same packet formatter.
- Direct, target-first, and blocker-first still dispatch their existing expert
  protocols.
- Offline audit makes zero network calls.
- Paid execution remains protected by the existing literal confirmation gate.

## Paper Interpretation

Until the automatic method passes the offline and paid gates:

- historical v10 remains the strongest oracle-routed, oracle-feature result;
- the automatic router remains a failed or preliminary deployable variant;
- the two-win 25-sample blocker pilot is diagnostic evidence, not a method
  result;
- target-conditioned 2D evidence must not be described as depth-aware
  obstruction reasoning.

If V2 succeeds, the method claim is that structured v10 expert protocols can
be selected and supplied with auditable target-conditioned predicted evidence
without benchmark routing. If it fails the hard recall gate, the justified
next contribution is depth-aware target visibility, not further prompt
elaboration.
