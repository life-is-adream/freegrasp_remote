# Unified Hard-Safe Result Governance Design

Date: 2026-06-26

Branch: `experiment/routing-v2`

Status: approved direction for design writing.

## 1. Decision

Add a result-governance layer for all `unified_hard_safe_*` runs.

The layer has three responsibilities:

1. Make UHS run artifacts auditable enough to support failure analysis.
2. Support zero-paid offline analysis and frozen ablation setup.
3. Support targeted reruns of retryable MiMo API `500` rows and allow those
   rerun rows to replace the main result view, but only through an explicit,
   auditable merge step that preserves the original raw run intact.

This design applies to:

- `unified_hard_safe_v1`
- `unified_hard_safe_no_hard_fallback`
- `unified_hard_safe_no_ranked_candidates`
- `unified_hard_safe_no_point_repair`
- `unified_hard_safe_no_id_repair`

This design does not authorize changes to `/home/public/zb/FreeGrasp_code-main`.

## 2. Problem

The paid split-0 UHS1 run and the preceding hard-only smoke runs produced two
distinct issues:

1. The protocol itself is still weak on hard subsets.
2. The saved artifacts are not reliable enough to audit why.

The split-0 run produced:

- overall: `RSR 61%`, `SSR 53%`
- hard combined: `RSR 39%`, `SSR 31%`
- hard raw `grasp_target`: `3/24` reasoning success
- hard raw `remove_blocker`: `36/76` reasoning success

The current saved detail rows have two important audit gaps:

1. They do not persist post-repair fields such as:
   - `hard_fallback_applied`
   - repaired `action`
   - repaired `target_status`
   - `pre_repair_action`
2. They record `reasoning.feature_source == "oracle_feature"` in UHS rows even
   when the run manifest records `feature_source == "none"`.

The same experiment sequence also produced transient MiMo API `500` rows.
Those `500` rows changed across smoke and full runs, which strongly suggests
service-side instability rather than deterministic corruption of those samples.

Therefore the next step is not another protocol change first. It is a result
governance layer that makes future UHS runs auditable, replay-safe, and robust
to retryable service faults.

## 3. Goals

1. Preserve one immutable raw evidence view for every UHS run.
2. Persist enough decision metadata to audit raw, parsed, and repaired
   decisions without rerunning paid inference.
3. Distinguish service failures from model/protocol failures.
4. Support deterministic, zero-paid offline analysis over frozen UHS outputs.
5. Support targeted reruns for retryable API `500` rows only.
6. Allow a `resolved` result view to replace the main reported result, but only
   when the replacement rows are auditably equivalent to the original run
   configuration.
7. Make the same mechanism reusable across all `unified_hard_safe_*` ablations.

## 4. Non-Goals

- Designing a new reasoning protocol.
- Retuning the hard fallback threshold.
- Replacing the MiMo provider.
- Backfilling all historical non-UHS runs into the same format.
- Claiming rerun-improved results are the same as a clean first-pass run.
- Modifying benchmark data or Molmo outputs.

## 5. High-Level Architecture

Each UHS run has three artifact layers:

```text
raw run -> audit view -> resolved view
```

### 5.1 Raw Run

The raw run is the first paid execution. It is immutable evidence.

It contains:

- `out_*.json`
- `details_*.json`
- `run_manifest.json`
- `full_protocol_summary.json`

This view is never overwritten in place.

### 5.2 Audit View

The audit view is offline only.

It reads the frozen raw run and produces:

- normalized audit rows
- failure attribution summaries
- hard direct vs blocker summaries
- API `500` retry candidate lists
- frozen ablation index files

It must make no model or network calls.

### 5.3 Resolved View

The resolved view is derived from:

- one raw run; plus
- zero or more approved API `500` patch rows

This view may become the main reported result, but only after an explicit merge
manifest is written. The raw run remains preserved.

## 6. Sample Identity

Every UHS row must be addressable by one complete key:

```text
(run_id, split, subset, row_index, scene_id, object_id, annotation)
```

Required fields:

- `run_id`
- `split`
- `subset`
- `row_index`
- `scene_id`
- `object_id`
- `annotation`

Rules:

- raw runs must reject duplicate complete keys
- patch rows must target exactly one existing complete key
- audit and merge steps must fail on missing or duplicate keys

`row_index` is mandatory because `(scene_id, object_id, annotation)` is not
guaranteed to remain unique across every evaluation context.

## 7. Raw Run Data Contract

### 7.1 Detail Row Contract

Each `details_*.json` row must persist:

- sample identity:
  - `split`
  - `subset`
  - `row_index`
  - `scene_id`
  - `object_id`
  - `annotation`
- outcome:
  - `rsr_correct`
  - `ssr_correct`
  - `iou`
  - `failure_reason`
- run config:
  - `prompt_variant`
  - `model_name`
  - `max_output_tokens`
  - `mimo_retry_mode`
  - `segmentation_variant`
  - `subset_policy`
  - `protocol_ablation`
  - `routing_variant`
  - `route_guard_variant`
- feature provenance:
  - `feature_source_requested`
  - `feature_source_effective`
  - `uses_gt_features`
  - `uses_benchmark_difficulty`
- model raw output:
  - `raw_output`
  - `raw_outputs`
  - `retry_count`
  - `retry_reason`
  - `router_call_count`
- normalized parsing/repair state:
  - `parse_status`
  - `reasoning_json`
  - `parsed_decision`
  - `repaired_decision`
  - `hard_fallback_applied`
  - `pre_repair_action`
  - `pre_repair_target_status`
  - `pre_repair_first_grasp_object_id`
  - `repaired_action`
  - `repaired_target_status`
  - `repaired_first_grasp_object_id`
  - `ranked_first_grasp_candidates`
- segmentation trace:
  - `mask_query`
  - `langsam_queries`
  - `langsam_attempts`
  - `langsam_selected_query`
  - `langsam_selected_mask_index`
  - `langsam_mask_contains_point`
  - `langsam_failure_reason`
  - `selected_object_id`
  - `selected_gt_id`
  - `molmo_point`
- error classification:
  - `error`
  - `api_error_class`
  - `api_error_retryable`

### 7.2 Raw/Parsed/Repaired Separation

The persisted row must distinguish three layers:

1. `reasoning_json`: exact parsed model JSON when a model response exists.
2. `parsed_decision`: normalized direct interpretation of that response.
3. `repaired_decision`: deterministic post-processing after hard fallback, ID
   repair, and related repair steps.

The audit layer must not infer repaired behavior by reimplementing parser logic
after the fact. The repaired state must already be persisted in the raw run.

### 7.3 API Error Rows

If a row ends in a retryable MiMo API error before a valid reasoning response is
produced:

- `reasoning_json` must be `null`
- `parsed_decision` must be `null`
- `repaired_decision` must be `null`
- `parse_status` must be `api_error`
- `api_error_class` must be populated
- `api_error_retryable` must be explicit

`parse_status == None` is not allowed for a finalized row.

## 8. Manifest Contract

`run_manifest.json` must contain both the user-facing config and the equivalence
fields needed for future patch merges.

Required fields:

- `manifest_id`
- `run_id`
- `timestamp`
- `model`
- `model_name`
- `max_output_tokens`
- `subset_policy`
- `prompt_variant`
- `mimo_retry_mode`
- `segmentation_variant`
- `protocol_ablation`
- `routing_variant`
- `route_guard_variant`
- `feature_source_requested`
- `feature_source_effective`
- `uses_gt_features`
- `uses_benchmark_difficulty`
- `cache_sha256`
- `git_commit`
- `dirty_worktree`
- `artifact_schema_version`
- `behavior_equivalence_hash`

`behavior_equivalence_hash` is the canonical gate for whether a rerun patch may
merge into an existing raw run.

It must be derived from behavior-affecting inputs, not from purely logging-only
implementation changes.

At minimum it must include:

- model
- token limit
- subset policy
- prompt variant
- retry mode
- segmentation variant
- protocol ablation
- routing variant
- route guard variant
- feature-source intent/effective value
- split selection
- cache hash

## 9. Audit View

The audit view must be generated by an offline CLI.

Suggested outputs under the run root:

```text
analysis/
  audit_rows.jsonl
  failure_summary.json
  failure_summary.md
  api500_candidates.json
  hard_failure_examples.json
  frozen_ablation_index.json
```

### 9.1 Audit Row Content

Each audit row must include:

- complete sample identity
- raw outcome (`RSR`, `SSR`, `IoU`)
- raw status/action from `reasoning_json`
- repaired status/action from `repaired_decision`
- `hard_fallback_applied`
- `api_error_class`
- segmentation failure fields
- audit-only annotations:
  - hard/easy/medium group
  - `RSR-only`
  - `SSR-only`
  - `both_fail`

### 9.2 Audit Reports

The offline audit must report:

- subset metrics and totals
- difficulty-grouped metrics
- hard raw `grasp_target` vs `remove_blocker`
- hard `free_visible` vs `visible_but_blocked` vs `uncertain`
- `RSR-only` / `SSR-only` / `both_fail`
- API `500` counts and sample keys
- point-to-mask failure counts
- failure examples by category

### 9.3 Frozen Ablation Index

The audit layer must also generate a stable index for later no-paid analysis.

Each frozen row should expose enough to analyze:

- whether the hard direct call looked unsupported
- whether the blocker-first call succeeded
- whether segmentation alone failed after a correct reasoning choice
- whether the row is ineligible because of API `500`

This index is analysis-only. It does not claim new end-to-end metrics.

## 10. API 500 Retry Policy

### 10.1 Eligible Rows

A row is eligible for targeted retry only when all are true:

- it belongs to a `unified_hard_safe_*` run
- `api_error_retryable == true`
- the saved failure is a MiMo service/API error, not a parsing or logic error
- the row never received a valid reasoning response in the raw run

Rows with valid model responses but bad reasoning or bad segmentation are not
retry candidates.

### 10.2 Retry Isolation

Retry execution must write a separate patch artifact, not edit the raw files.

Suggested patch outputs:

```text
retries/
  api500_patch_manifest.json
  api500_patch_rows.jsonl
  api500_patch_summary.json
```

Each patch row must include:

- the full sample key
- original raw run manifest ID
- retry manifest ID
- original error string
- resolved outcome row
- resolved detail row

### 10.3 Merge Gate

A patch row may merge into a raw run only if:

- sample key matches exactly
- original row is still an eligible API `500` row
- `behavior_equivalence_hash` matches
- cache hash matches
- subset policy matches
- split matches
- the original raw row has not already been replaced by another approved patch

Git commit may differ only if the new manifest still has the same
`behavior_equivalence_hash`. Logging-only changes are therefore allowed, but
behavioral changes are not.

### 10.4 Resolved View

When the patch manifest passes validation, produce:

```text
resolved/
  out_*.json
  details_*.json
  resolved_summary.json
  resolved_merge_manifest.json
```

The resolved view replaces only the approved API `500` rows and leaves every
other row unchanged.

The merge manifest must record:

- raw manifest ID
- patch manifest ID
- replaced sample keys
- counts before/after replacement
- API `500` counts before/after replacement
- summary deltas

Because the user explicitly chose replacement behavior, the resolved summary may
be used as the main result summary after merge. However, the raw summary must
remain preserved and citeable.

## 11. Reporting Rules

For any UHS run that uses patch replacement:

1. Keep the raw run as immutable evidence.
2. Mark the resolved run as derived from the raw run plus API `500` patch rows.
3. Report how many rows were replaced.
4. Do not describe the resolved result as a clean single-pass run.
5. Keep the raw and resolved summaries both accessible to later paper writing
   and internal review.

## 12. Error Handling

- Duplicate sample keys fail raw run validation.
- Missing required decision fields fail artifact validation.
- `feature_source_requested != feature_source_effective` must be explicit, not
  silently inferred.
- `parse_status == None` is invalid for finalized rows.
- Non-API failures are rejected from retry patch generation.
- Patch merge fails on equivalence mismatch.
- Patch merge fails if the target row is not still an unresolved retryable API
  `500`.
- Resolved view generation fails if raw counts do not equal expected counts.

## 13. Tests

### 13.1 Artifact Tests

- UHS detail rows persist repaired decision fields.
- UHS detail rows persist both requested and effective feature source.
- API `500` rows persist `api_error_class`, `api_error_retryable`, and
  `parse_status="api_error"`.
- Manifest writes both `model` and `model_name`.
- Manifest writes `behavior_equivalence_hash`.

### 13.2 Audit Tests

- Offline audit makes no model or network calls.
- Audit row count equals raw row count.
- `RSR-only`, `SSR-only`, and `both_fail` totals match the source run exactly.
- Hard raw action/status buckets match saved raw `reasoning_json`.
- Frozen ablation index is deterministic.

### 13.3 Retry Tests

- Only retryable API `500` rows are emitted into the patch candidate set.
- Patch generation rejects rows that already have valid reasoning outputs.
- Patch merge rejects equivalence mismatches.
- Patch merge replaces only targeted rows.
- Raw run artifacts remain unchanged after patch generation and merge.

### 13.4 Integration Tests

- One synthetic UHS subset run with injected API `500` rows produces:
  - complete raw row counts
  - complete audit rows
  - valid patch artifact
  - valid resolved artifact
- Resolved summary equals raw summary except at replaced rows.

## 14. Success Criteria

This design is implemented successfully when:

- all UHS raw runs persist repaired-decision and provenance fields
- the false `oracle_feature` provenance is eliminated or made explicit as
  requested/effective divergence
- offline audit can reproduce the split-0 findings without new paid calls
- retryable API `500` rows can be rerun and merged through a strict equivalence
  gate
- raw evidence remains immutable after retries
- resolved views can be reported without losing the original raw record

## 15. Immediate Interpretation For The Current UHS1 Run

Once this design is implemented, the current split-0 run should be treated as:

- a valid raw evidence run for the main protocol behavior
- a run with known provenance gaps in saved detail rows
- a run whose `5` API `500` rows are eligible for targeted retry analysis
- a run whose hard failure story is already clear enough to prioritize:
  - suppress unsupported hard direct calls
  - improve blocker selection and ranking
  - keep segmentation improvements secondary
