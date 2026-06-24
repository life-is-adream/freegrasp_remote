# Conservative Evidence Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic conservative guard to the predicted-geometry VLM router, repair 900-row paired statistics, produce a frozen offline route audit, and prepare a reproducible 120-sample pilot without triggering paid inference.

**Architecture:** Keep the existing VLM router as a proposal generator and add a pure guard in `utils/scene_evidence.py`. Thread an explicit `route_guard_variant` through the evaluation stack, preserve both proposed and guarded routes in detail rows, and add standalone offline tools for route auditing, pilot selection, and frozen-route execution. Statistical pairing uses loader-enriched split/subset/row context so all 900 rows remain distinct.

**Tech Stack:** Python 3.13 project `.venv`, `unittest`, NumPy, JSON manifests, existing FreeGrasp evaluation utilities, MiMo-compatible evaluation entrypoints.

---

## Scope and File Map

- Modify `summarize_ablation_matrix.py`: contextual detail loading, complete sample keys, duplicate detection, and corrected paired bootstrap.
- Modify `test_summarize_ablation_matrix.py`: regression tests for the 900-to-822 key collapse.
- Modify `utils/scene_evidence.py`: pure conservative guard and guard constants.
- Modify `test_scene_evidence.py`: guard unit tests and no-GT contract.
- Modify `utils/utils.py`: apply the guard after parsing router output and record audit metadata.
- Modify `test_evidence_router_integration.py`: guarded direct, downgraded direct, and blocker-first dispatch tests.
- Modify `reasoning_eval.py`: forward the guard variant and optional frozen route.
- Modify `evaluate_common.py`: forward the guard variant and optional frozen route map.
- Modify `evaluate_all.py`: configure conservative automatic policies.
- Modify `evaluate_mimo.py`: expose guard and frozen-route CLI arguments.
- Modify `evaluate_mimo_full_protocol.py`: expose guard and frozen-route CLI arguments and record guard provenance.
- Modify `experiment_manifest.py`: add a stable code-version helper for guard provenance.
- Modify `test_evidence_router_entrypoints.py`: entrypoint forwarding tests.
- Modify `test_evaluate_mimo_full_protocol.py`: manifest and summary guard metadata tests.
- Modify `test_experiment_manifest.py`: guard version stability test.
- Create `audit_conservative_router.py`: no-network S4 route audit and candidate comparison CLI.
- Create `test_audit_conservative_router.py`: audit row, transition, determinism, and no-evaluation-input leakage tests.
- Create `select_router_pilot.py`: deterministic 20-per-subset pilot selector.
- Create `test_select_router_pilot.py`: balanced selection and reproducibility tests.
- Create `frozen_route.py`: frozen-route artifact validation and lookup.
- Create `test_frozen_route.py`: key, duplicate, and mismatch tests.
- Update `docs/experiments/2026-06-22-stage1-readiness.md`: append Stage 1 outcome and guard follow-up status.

No task modifies `/home/public/zb/FreeGrasp_code-main`. No task authorizes paid inference.

### Task 1: Repair Complete Sample Identity and Paired Statistics

**Files:**
- Modify: `summarize_ablation_matrix.py:11-70`
- Modify: `summarize_ablation_matrix.py:162-184`
- Test: `test_summarize_ablation_matrix.py`

- [ ] **Step 1: Write failing tests for contextual sample identity**

Add fixtures with identical `scene_id`, `object_id`, and `annotation`, but different `split` and `subset`. Require both rows to survive pairing:

```python
def _detail(split, subset, row_index, *, rsr):
    return {
        "split": split,
        "subset": subset,
        "row_index": row_index,
        "scene_id": 7,
        "object_id": 2,
        "annotation": "the cup",
        "rsr_correct": rsr,
    }


def test_complete_key_keeps_repeated_semantic_samples_distinct(self):
    first = [
        _detail("0", "easy_no_ambi", 0, rsr=0),
        _detail("1", "easy_no_ambi", 0, rsr=0),
    ]
    second = [
        _detail("0", "easy_no_ambi", 0, rsr=1),
        _detail("1", "easy_no_ambi", 0, rsr=1),
    ]
    paired = summary.pair_by_sample_key(first, second)
    self.assertEqual(len(paired), 2)
```

Add a duplicate-key rejection test:

```python
def test_pairing_rejects_duplicate_complete_keys(self):
    row = _detail("0", "easy_no_ambi", 0, rsr=0)
    with self.assertRaisesRegex(ValueError, "Duplicate sample key"):
        summary.pair_by_sample_key([row, dict(row)], [row])
```

Add a temporary run-tree test that writes two `details_*.json` files and verifies `load_detail_rows()` enriches `split`, `subset`, and `row_index`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_summarize_ablation_matrix.AblationSummaryTest.test_complete_key_keeps_repeated_semantic_samples_distinct \
  test_summarize_ablation_matrix.AblationSummaryTest.test_pairing_rejects_duplicate_complete_keys \
  test_summarize_ablation_matrix.AblationSummaryTest.test_load_detail_rows_adds_context -v
```

Expected: FAIL because the current key ignores split/subset/index and `load_detail_rows` does not exist.

- [ ] **Step 3: Implement contextual loading and strict indexing**

Add:

```python
def load_detail_rows(run_root):
    rows = []
    for path in sorted(Path(run_root).glob("split_*/details_*.json")):
        split = path.parent.name.removeprefix("split_")
        subset = path.stem.removeprefix("details_")
        for row_index, row in enumerate(json.loads(path.read_text())):
            rows.append(
                {
                    **row,
                    "split": str(split),
                    "subset": subset,
                    "row_index": row_index,
                }
            )
    return rows


def sample_key(row):
    return (
        str(row["split"]),
        str(row["subset"]),
        int(row["row_index"]),
        int(row["scene_id"]),
        int(row["object_id"]),
        str(row.get("annotation", "")),
    )


def _index_unique(rows):
    indexed = {}
    for row in rows:
        key = sample_key(row)
        if key in indexed:
            raise ValueError(f"Duplicate sample key: {key}")
        indexed[key] = row
    return indexed
```

Use `_index_unique()` in `pair_by_sample_key()`. Preserve `scene_id` from each paired row rather than reading `key[0]`. Change `validate_run()` to call `load_detail_rows()` and require exactly `expected_n` complete keys.

- [ ] **Step 4: Update existing small fixtures**

Add `split`, `subset`, and `row_index` to existing pairing/bootstrap test rows. Do not weaken the new complete-key requirement with fallback defaults.

- [ ] **Step 5: Run the statistical tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_summarize_ablation_matrix -v
```

Expected: all tests PASS.

- [ ] **Step 6: Validate all Stage 1 runs**

Run:

```bash
for run in data/output/ablation_matrix/S{0..7}; do
  .venv/bin/python summarize_ablation_matrix.py validate "$run"
done
```

Expected: every run reports:

```json
{"n": 900, "unique_samples": 900}
```

- [ ] **Step 7: Commit**

```bash
git add summarize_ablation_matrix.py test_summarize_ablation_matrix.py
git commit -m "fix: preserve complete ablation sample identity"
```

### Task 2: Implement the Pure Conservative Route Guard

**Files:**
- Modify: `utils/scene_evidence.py:8`
- Modify: `utils/scene_evidence.py:243-292`
- Test: `test_scene_evidence.py`

- [ ] **Step 1: Write failing tests for direct-route guard rules**

Import `apply_conservative_route_guard` and add a common assessment helper:

```python
def _assessment(mode="direct", **updates):
    value = {
        "route_mode": mode,
        "route_confidence": 0.95,
        "target_object_id": 3,
        "target_label": "red block",
        "ambiguity_evidence": [],
        "blocker_evidence": [],
    }
    value.update(updates)
    return value
```

Add separate tests proving:

```python
guarded = apply_conservative_route_guard(
    _assessment(),
    visible_object_ids=[3, 4, 5],
    object_count=3,
    predicted_geometry={"candidates": {}, "relations": []},
)
self.assertEqual(guarded["route_mode"], "direct")
self.assertFalse(guarded["route_guard_applied"])
```

and that low confidence, invalid target, non-empty ambiguity, four objects, and a target overlap relation each downgrade `direct` to `target_first` with a specific reason.

- [ ] **Step 2: Write failing tests for blocker and no-GT rules**

Add tests proving:

- `near` alone does not count as blocking evidence;
- `blocker_first` with `["near object 4"]` downgrades;
- `blocker_first` with `["physical overlap with object 4"]` remains;
- `target_first` is never upgraded;
- a predicted-geometry dictionary containing `gt_id` raises `ValueError`.

- [ ] **Step 3: Run guard tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_scene_evidence.SceneEvidenceTest.test_conservative_guard_keeps_safe_direct \
  test_scene_evidence.SceneEvidenceTest.test_conservative_guard_downgrades_risky_direct \
  test_scene_evidence.SceneEvidenceTest.test_conservative_guard_validates_blocker_first \
  test_scene_evidence.SceneEvidenceTest.test_conservative_guard_rejects_gt_fields -v
```

Expected: import failure because the guard is not implemented.

- [ ] **Step 4: Implement constants and evidence helpers**

Add:

```python
CONSERVATIVE_GUARD_VERSION = "conservative-v1"
DIRECT_CONFIDENCE_THRESHOLD = 0.90
DIRECT_MAX_OBJECT_COUNT = None
TARGET_OVERLAP_THRESHOLD = 0.15
BLOCKING_TERMS = ("contact", "coverage", "covered", "on-top", "on top", "overlap")
```

Add helpers that:

- recursively reject dictionary keys containing `gt`, `ground_truth`, or `benchmark`;
- normalize router evidence text to lowercase;
- detect only the permitted blocking terms;
- find `overlaps` relations where either `source_id` or `target_id` equals the proposed target and `overlap > 0`.

- [ ] **Step 5: Implement the pure guard**

Implement:

```python
def apply_conservative_route_guard(
    route_assessment,
    *,
    visible_object_ids,
    object_count,
    predicted_geometry,
):
    original_mode = route_assessment["route_mode"]
    guarded_mode = original_mode
    reasons = []

    # direct checks append stable machine-readable reasons:
    # invalid_target_id, low_confidence, ambiguity_present,
    # router_blocking_evidence, predicted_target_overlap
    # blocker checks append unsupported_blocker_evidence.

    return {
        **route_assessment,
        "route_mode": guarded_mode,
        "pre_guard_route_mode": original_mode,
        "route_guard_applied": guarded_mode != original_mode,
        "route_guard_reasons": reasons,
        "route_guard_variant": "conservative_v1",
        "direct_confidence_threshold": DIRECT_CONFIDENCE_THRESHOLD,
        "direct_max_object_count": DIRECT_MAX_OBJECT_COUNT,
        "guard_code_version": CONSERVATIVE_GUARD_VERSION,
    }
```

The function must not inspect benchmark subset, RSR, SSR, GT IDs, or masks.

- [ ] **Step 6: Run scene-evidence tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_scene_evidence -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: add conservative evidence route guard"
```

### Task 3: Integrate the Guard into Online Reasoning

**Files:**
- Modify: `utils/utils.py:1635-1840`
- Modify: `test_evidence_router_integration.py`

- [ ] **Step 1: Extend the integration-test helper**

Change `_run_prediction()` to accept:

```python
route_guard_variant="conservative_v1",
parsed_rows=None,
predicted_geometry=None,
```

Use `parsed_rows` when writing `10_id.txt`, and pass
`route_guard_variant=route_guard_variant` into `get_prediction_result()`.

- [ ] **Step 2: Write failing dispatch tests**

Add:

```python
def test_guarded_direct_still_uses_one_model_call(self):
    # Three objects, confidence .95, no ambiguity/overlap.
    result, calls = self._run_prediction(safe_direct_json)
    self.assertEqual(len(calls), 1)
    self.assertEqual(result["reasoning"]["pre_guard_route_mode"], "direct")
    self.assertEqual(result["reasoning"]["route_mode"], "direct")


def test_risky_direct_dispatches_target_first(self):
    # Four visible objects make direct ineligible.
    result, calls = self._run_prediction(
        direct_json,
        target_first_result_json,
        parsed_rows=[...four visible rows...],
    )
    self.assertEqual(result["reasoning"]["pre_guard_route_mode"], "direct")
    self.assertEqual(result["reasoning"]["route_mode"], "target_first")
    self.assertIn("clutter_prior", result["reasoning"]["route_guard_reasons"])
    self.assertIn("target-first", calls[1]["messages"][0]["content"].lower())
```

Add a supported blocker-first dispatch test and an unsupported blocker-first downgrade test.

- [ ] **Step 3: Run integration tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_evidence_router_integration.EvidenceRouterIntegrationTest.test_guarded_direct_still_uses_one_model_call \
  test_evidence_router_integration.EvidenceRouterIntegrationTest.test_risky_direct_dispatches_target_first \
  test_evidence_router_integration.EvidenceRouterIntegrationTest.test_supported_blocker_dispatches_blocker_prompt -v
```

Expected: FAIL because `get_prediction_result()` has no guard argument or metadata.

- [ ] **Step 4: Add the guard argument and validation**

Add to `get_prediction_result()`:

```python
route_guard_variant="none",
```

Validate against:

```python
VALID_ROUTE_GUARD_VARIANTS = {"none", "conservative_v1"}
```

Record the variant in the initial `reasoning` dictionary.

- [ ] **Step 5: Apply the guard before protocol ablation**

After parsing or constructing `route_assessment`, preserve:

```python
reasoning["pre_guard_route_assessment"] = dict(route_assessment)
```

For `route_guard_variant == "conservative_v1"` call:

```python
route_assessment = apply_conservative_route_guard(
    route_assessment,
    visible_object_ids=visible_object_ids,
    object_count=len(parsed_data),
    predicted_geometry=geometry_features,
)
```

Then apply `no_blocker_first` to the guarded route, preserving a separate
`pre_ablation_route_mode`. Never overwrite `pre_guard_route_mode`.

- [ ] **Step 6: Keep retry selection tied to the guarded route**

Ensure `_automatic_retry_mode()` receives the final guarded/ablated
`route_mode`. A downgraded direct must receive target-first geometry repair;
a retained blocker-first receives ID repair.

- [ ] **Step 7: Run integration tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_evidence_router_integration -v
```

Expected: all tests PASS, with no real API or model initialization.

- [ ] **Step 8: Commit**

```bash
git add utils/utils.py test_evidence_router_integration.py
git commit -m "feat: guard automatic routing before reasoning dispatch"
```

### Task 4: Thread Guard Configuration and Provenance Through Entrypoints

**Files:**
- Modify: `reasoning_eval.py`
- Modify: `evaluate_common.py`
- Modify: `evaluate_all.py`
- Modify: `evaluate_mimo.py`
- Modify: `evaluate_mimo_full_protocol.py`
- Modify: `experiment_manifest.py`
- Modify: `test_evidence_router_entrypoints.py`
- Modify: `test_evaluate_mimo_full_protocol.py`
- Modify: `test_experiment_manifest.py`

- [ ] **Step 1: Write failing entrypoint-forwarding tests**

Require `route_guard_variant="conservative_v1"` to flow through:

```text
evaluate_mimo_full_protocol
  -> evaluate_common.evaluate_subset
  -> reasoning_eval.process_dataset
  -> utils.utils.get_prediction_result
```

Add assertions to the existing mocked-forwarding tests:

```python
self.assertEqual(kwargs["route_guard_variant"], "conservative_v1")
```

- [ ] **Step 2: Write failing manifest tests**

Add a test that a conservative run summary and manifest contain:

```python
{
    "route_guard_variant": "conservative_v1",
    "direct_confidence_threshold": 0.90,
    "direct_max_object_count": None,
    "target_overlap_threshold": 0.15,
    "guard_code_version": "conservative-v1",
}
```

Add a stable helper test:

```python
self.assertEqual(guard_provenance()["guard_code_version"], "conservative-v1")
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_evidence_router_entrypoints \
  test_evaluate_mimo_full_protocol \
  test_experiment_manifest -v
```

Expected: FAIL on missing guard arguments and provenance.

- [ ] **Step 4: Add guard provenance helper**

In `experiment_manifest.py`, import guard constants lazily and return:

```python
def guard_provenance(route_guard_variant):
    if route_guard_variant == "none":
        return {"route_guard_variant": "none"}
    if route_guard_variant != "conservative_v1":
        raise ValueError(f"Unknown route guard: {route_guard_variant}")
    from utils.scene_evidence import (
        CONSERVATIVE_GUARD_VERSION,
        DIRECT_CONFIDENCE_THRESHOLD,
        DIRECT_MAX_OBJECT_COUNT,
    )
    return {
        "route_guard_variant": route_guard_variant,
        "direct_confidence_threshold": DIRECT_CONFIDENCE_THRESHOLD,
        "direct_max_object_count": DIRECT_MAX_OBJECT_COUNT,
        "guard_code_version": CONSERVATIVE_GUARD_VERSION,
    }
```

- [ ] **Step 5: Add CLI and function arguments**

Expose:

```text
--route-guard-variant {none,conservative_v1}
```

Default to `none` for backward compatibility. Set the next automatic pilot
configuration explicitly to `conservative_v1`; do not silently change S0-S7.

Thread the value through all listed functions and include
`guard_provenance()` in the full-protocol manifest and aggregate summary.

- [ ] **Step 6: Run entrypoint and manifest tests**

Run:

```bash
.venv/bin/python -m unittest \
  test_evidence_router_entrypoints \
  test_evaluate_mimo_full_protocol \
  test_experiment_manifest \
  test_evaluate_entrypoints \
  test_reasoning_resume -v
```

Expected: all tests PASS.

- [ ] **Step 7: Verify CLI help without API calls**

Run:

```bash
.venv/bin/python evaluate_mimo_full_protocol.py --help | rg "route-guard-variant"
.venv/bin/python evaluate_mimo.py --help | rg "route-guard-variant"
```

Expected: both commands list `none` and `conservative_v1`.

- [ ] **Step 8: Commit**

```bash
git add \
  reasoning_eval.py evaluate_common.py evaluate_all.py evaluate_mimo.py \
  evaluate_mimo_full_protocol.py experiment_manifest.py \
  test_evidence_router_entrypoints.py test_evaluate_mimo_full_protocol.py \
  test_experiment_manifest.py
git commit -m "feat: record conservative route guard provenance"
```

### Task 5: Build the Offline S4 Route Audit

**Files:**
- Create: `audit_conservative_router.py`
- Create: `test_audit_conservative_router.py`

- [ ] **Step 1: Write failing audit-row tests**

Create a detail fixture containing S4-style `reasoning` metadata and require:

```python
row = audit.audit_detail(
    detail,
    split="0",
    subset="medium_no_ambi",
    row_index=0,
    policy="conservative_v1",
)
self.assertEqual(row["sample_key"][0:3], ["0", "medium_no_ambi", 0])
self.assertEqual(row["original_route"], "direct")
self.assertEqual(row["guarded_route"], "target_first")
self.assertIn("clutter_prior", row["guard_reasons"])
self.assertTrue(row["evaluation_only"]["rsr_correct"] in (0, 1))
```

Patch the guard and assert only route assessment, visible IDs, object count,
and predicted geometry are passed. Benchmark subset and RSR/SSR must not be
guard inputs.

- [ ] **Step 2: Write failing summary and determinism tests**

Require:

- transition counts sum to the number of audit rows;
- per-subset route totals match input totals;
- identical input produces byte-identical JSON with `sort_keys=True`;
- `raw`, `downgrade_all_risky_direct`, and `conservative_v1` are all reported;
- no function imports or calls MiMo/OpenAI clients.

- [ ] **Step 3: Run audit tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest test_audit_conservative_router -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement contextual audit loading**

Reuse `summarize_ablation_matrix.load_detail_rows()`. Build an audit row with:

```python
{
    "sample_key": list(sample_key(detail)),
    "split": detail["split"],
    "subset": detail["subset"],
    "scene_id": detail["scene_id"],
    "object_id": detail["object_id"],
    "annotation": detail.get("annotation", ""),
    "original_route": pre_guard["route_mode"],
    "guarded_route": guarded["route_mode"],
    "guarded_assessment": {
        key: guarded[key]
        for key in (
            "route_mode",
            "route_confidence",
            "target_object_id",
            "target_label",
            "ambiguity_evidence",
            "blocker_evidence",
            "pre_guard_route_mode",
            "route_guard_applied",
            "route_guard_reasons",
            "route_guard_variant",
            "direct_confidence_threshold",
            "direct_max_object_count",
            "guard_code_version",
        )
    },
    "route_confidence": pre_guard["route_confidence"],
    "target_object_id": pre_guard["target_object_id"],
    "target_id_valid": pre_guard["target_object_id"] in visible_ids,
    "object_count": len(visible_ids),
    "ambiguity_evidence": pre_guard["ambiguity_evidence"],
    "blocker_evidence": pre_guard["blocker_evidence"],
    "target_relations": target_relations,
    "guard_reasons": guarded["route_guard_reasons"],
    "evaluation_only": {
        "expected_route": expected_route_from_subset(detail["subset"]),
        "rsr_correct": int(detail["rsr_correct"]),
        "ssr_correct": int(detail["ssr_correct"]),
    },
}
```

For historical S4 rows, use `reasoning["route_mode"]` as the original route
and reconstruct the pre-guard assessment from stored router fields.

- [ ] **Step 5: Implement candidate policies**

Implement:

```python
POLICIES = ("raw", "downgrade_all_risky_direct", "conservative_v1")
```

`raw` returns the parsed assessment unchanged. The risky-direct policy applies
only direct checks. `conservative_v1` calls the production guard and also
validates blocker-first.

- [ ] **Step 6: Implement audit summaries**

Report:

- `n_rows`;
- per-subset original and guarded route distributions;
- transition matrix;
- expected-route agreement;
- easy direct retention;
- medium/hard direct suppression;
- unsupported blocker-first count;
- expected additional specialized-reasoning calls;
- original S4 RSR/SSR grouped by original and guarded route, labeled
  `evaluation_only`.

Do not calculate a synthetic guarded RSR.

- [ ] **Step 7: Implement CLI**

Support:

```bash
.venv/bin/python audit_conservative_router.py \
  --source-run data/output/ablation_matrix/S4 \
  --output-dir data/output/ablation_matrix/conservative_router_audit
```

Write:

```text
audit_rows.json
candidate_comparison.json
selected_policy.json
```

`selected_policy.json` must select `conservative_v1` before pilot inference and
record the constants and source manifest ID.

- [ ] **Step 8: Run audit tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_audit_conservative_router -v
```

Expected: all tests PASS.

- [ ] **Step 9: Verify the script contains no model calls**

Run:

```bash
rg -n "_call_reasoning_model|create_mimo_client|OpenAI|chat\\.completions" \
  audit_conservative_router.py
```

Expected: no matches.

- [ ] **Step 10: Commit**

```bash
git add audit_conservative_router.py test_audit_conservative_router.py
git commit -m "feat: audit conservative routes offline"
```

### Task 6: Generate a Deterministic 120-Sample Pilot Manifest

**Files:**
- Create: `select_router_pilot.py`
- Create: `test_select_router_pilot.py`

- [ ] **Step 1: Write failing balanced-selection tests**

Create synthetic audit rows for all six subsets and require:

```python
selected = select_pilot_rows(rows, per_subset=20, seed=20260624)
self.assertEqual(len(selected), 120)
self.assertEqual(
    Counter(row["subset"] for row in selected),
    {subset: 20 for subset in DEFAULT_SUBSETS},
)
```

Require identical seed/input to produce identical keys and reject duplicate
sample keys or subsets with fewer than 20 rows.

- [ ] **Step 2: Run selection tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest test_select_router_pilot -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement deterministic stratified selection**

Use `random.Random(seed)` on rows sorted by complete sample key. Shuffle each
subset independently and take exactly `per_subset` rows. Return rows sorted by
`(subset, sample_key)` for stable serialization.

- [ ] **Step 4: Implement pilot manifest output**

The CLI:

```bash
.venv/bin/python select_router_pilot.py \
  --audit-rows data/output/ablation_matrix/conservative_router_audit/audit_rows.json \
  --source-manifest data/output/ablation_matrix/S4/run_manifest.json \
  --output data/output/ablation_matrix/conservative_router_audit/pilot_manifest.json \
  --per-subset 20 \
  --seed 20260624
```

must write:

```python
{
    "selection_seed": 20260624,
    "per_subset": 20,
    "n_samples": 120,
    "source_manifest_id": "...",
    "cache_sha256": "...",
    "route_guard_variant": "conservative_v1",
    "samples": [...complete keys...],
}
```

- [ ] **Step 5: Run selection tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_select_router_pilot -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add select_router_pilot.py test_select_router_pilot.py
git commit -m "feat: freeze conservative router pilot samples"
```

### Task 7: Add a Frozen-Route Artifact Contract

**Files:**
- Create: `frozen_route.py`
- Create: `test_frozen_route.py`

- [ ] **Step 1: Write failing validation tests**

Require `load_frozen_routes(path)` to:

- return a dictionary keyed by complete sample key;
- require exactly the expected number of rows when requested;
- reject duplicate keys;
- reject unknown route modes;
- reject missing guarded route assessments;
- reject source manifest/cache mismatches.

Example:

```python
with self.assertRaisesRegex(ValueError, "Duplicate frozen route"):
    frozen.load_frozen_routes(path_with_duplicate_rows)
```

- [ ] **Step 2: Run frozen-route tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest test_frozen_route -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement artifact schema and lookup**

Implement:

```python
def complete_key(split, subset, row_index, detail):
    return (
        str(split),
        str(subset),
        int(row_index),
        int(detail["scene_id"]),
        int(detail["object_id"]),
        str(detail.get("annotation", "")),
    )


def load_frozen_routes(
    path,
    *,
    expected_manifest_id=None,
    expected_cache_sha256=None,
    expected_n=None,
):
    ...
```

Each stored value must contain the parsed guarded assessment and guard
metadata. `load_frozen_routes()` must construct its lookup exclusively from
`guarded_assessment` and must never copy the sibling `evaluation_only` object
into an inference value.

- [ ] **Step 4: Run frozen-route tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest test_frozen_route -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frozen_route.py test_frozen_route.py
git commit -m "feat: validate frozen automatic routes"
```

### Task 8: Support Frozen Routes Without Recalling the Router

**Files:**
- Modify: `utils/utils.py`
- Modify: `reasoning_eval.py`
- Modify: `evaluate_common.py`
- Modify: `evaluate_mimo.py`
- Modify: `evaluate_mimo_full_protocol.py`
- Modify: `test_evidence_router_integration.py`
- Modify: `test_evidence_router_entrypoints.py`
- Modify: `test_reasoning_resume.py`

- [ ] **Step 1: Write failing router-bypass integration test**

Pass a frozen assessment directly:

```python
frozen_assessment = {
    "route_mode": "target_first",
    "route_confidence": 0.95,
    "target_object_id": 3,
    "target_label": "red block",
    "ambiguity_evidence": [],
    "blocker_evidence": [],
    "pre_guard_route_mode": "direct",
    "route_guard_applied": True,
    "route_guard_reasons": ["clutter_prior"],
    "route_guard_variant": "conservative_v1",
}
```

Assert the fake client receives the specialized reasoning call but no router
prompt:

```python
self.assertNotIn("route one bin-picking", calls[0]["messages"][0]["content"].lower())
self.assertIn("target-first", calls[0]["messages"][0]["content"].lower())
self.assertEqual(result["reasoning"]["router_call_count"], 0)
self.assertTrue(result["reasoning"]["frozen_route_used"])
```

- [ ] **Step 2: Write failing entrypoint tests**

Require:

```text
--frozen-route-file PATH
```

to be loaded once in the entrypoint and forwarded as a lookup, not repeatedly
read for every sample. Require a manifest mismatch to fail before client
creation.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  test_evidence_router_integration.EvidenceRouterIntegrationTest.test_frozen_route_bypasses_router_call \
  test_evidence_router_entrypoints \
  test_reasoning_resume -v
```

Expected: FAIL because frozen routes are unsupported.

- [ ] **Step 4: Add optional frozen assessment to prediction**

Add:

```python
frozen_route_assessment=None,
```

When provided:

- validate it contains a legal final route;
- skip router-message construction and `_call_reasoning_model()` for routing;
- set `route_assessment` from the frozen value;
- record `frozen_route_used=True` and `router_call_count=0`;
- still run target-first or blocker-first specialized reasoning and configured
  repair;
- reject `route_guard_variant` disagreement.

- [ ] **Step 5: Thread complete sample context through dataset processing**

In `process_dataset()`, enumerate each subset dataframe row and construct the
same complete key used by the audit:

```python
(split, subset, row_index, scene_id, object_id, annotation)
```

Look up the frozen assessment and pass it to `get_prediction_result()`. Missing
keys must fail before issuing a model request.

- [ ] **Step 6: Add CLI loading and provenance**

Load the artifact once with `load_frozen_routes()`. Record:

- frozen route file hash;
- source manifest ID;
- source cache hash;
- number of frozen routes;
- `router_calls_expected=0`.

Reject `--frozen-route-file` with `routing_variant=count_only`.

- [ ] **Step 7: Run frozen-route integration tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest \
  test_frozen_route \
  test_evidence_router_integration \
  test_evidence_router_entrypoints \
  test_reasoning_resume \
  test_evaluate_mimo_full_protocol -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  utils/utils.py reasoning_eval.py evaluate_common.py evaluate_mimo.py \
  evaluate_mimo_full_protocol.py test_evidence_router_integration.py \
  test_evidence_router_entrypoints.py test_reasoning_resume.py
git commit -m "feat: replay frozen routes without router calls"
```

### Task 9: Produce Offline Artifacts and Run the Non-Paid Verification Gate

**Files:**
- Modify: `docs/experiments/2026-06-22-stage1-readiness.md`
- Generate: `data/output/ablation_matrix/conservative_router_audit/audit_rows.json`
- Generate: `data/output/ablation_matrix/conservative_router_audit/candidate_comparison.json`
- Generate: `data/output/ablation_matrix/conservative_router_audit/selected_policy.json`
- Generate: `data/output/ablation_matrix/conservative_router_audit/pilot_manifest.json`

- [ ] **Step 1: Run the complete non-paid test suite**

Run:

```bash
.venv/bin/python -m unittest \
  test_scene_evidence \
  test_summarize_ablation_matrix \
  test_audit_conservative_router \
  test_select_router_pilot \
  test_frozen_route \
  test_evidence_router_integration \
  test_evidence_router_entrypoints \
  test_experiment_manifest \
  test_evaluate_mimo_full_protocol \
  test_evaluate_entrypoints \
  test_reasoning_resume \
  test_replay_segmentation \
  test_segmentation_consistency_integration -v
```

Expected: all tests PASS with no HTTP requests.

- [ ] **Step 2: Compile changed Python files**

Run:

```bash
.venv/bin/python -m py_compile \
  summarize_ablation_matrix.py audit_conservative_router.py \
  select_router_pilot.py frozen_route.py experiment_manifest.py \
  evaluate_mimo_full_protocol.py evaluate_mimo.py evaluate_all.py \
  evaluate_common.py reasoning_eval.py utils/scene_evidence.py utils/utils.py
```

Expected: exit code 0.

- [ ] **Step 3: Generate the S4 offline audit**

Run:

```bash
.venv/bin/python audit_conservative_router.py \
  --source-run data/output/ablation_matrix/S4 \
  --output-dir data/output/ablation_matrix/conservative_router_audit
```

Expected:

- 900 audit rows;
- no network calls;
- candidate transition totals of 900;
- selected policy `conservative_v1`;
- no synthetic guarded RSR field.

- [ ] **Step 4: Generate the fixed pilot manifest**

Run:

```bash
.venv/bin/python select_router_pilot.py \
  --audit-rows data/output/ablation_matrix/conservative_router_audit/audit_rows.json \
  --source-manifest data/output/ablation_matrix/S4/run_manifest.json \
  --output data/output/ablation_matrix/conservative_router_audit/pilot_manifest.json \
  --per-subset 20 \
  --seed 20260624
```

Expected: 120 unique rows, exactly 20 from each subset.

- [ ] **Step 5: Audit the artifacts**

Run:

```bash
jq 'length' \
  data/output/ablation_matrix/conservative_router_audit/audit_rows.json
jq '.n_samples, (.samples | length)' \
  data/output/ablation_matrix/conservative_router_audit/pilot_manifest.json
jq '.policies.conservative_v1 | {
  easy_direct_retention,
  medium_hard_direct_suppression,
  expected_additional_reasoning_calls
}' \
  data/output/ablation_matrix/conservative_router_audit/candidate_comparison.json
```

Expected:

- audit length `900`;
- pilot counts `120` and `120`;
- metrics present and internally consistent.

- [ ] **Step 6: Confirm no paid process was started**

Run:

```bash
pgrep -af 'evaluate_mimo_full_protocol.py|run_ablation_matrix.py' || true
```

Expected: no matching experiment process.

- [ ] **Step 7: Append the experiment record**

Add a dated section to `docs/experiments/2026-06-22-stage1-readiness.md`:

```markdown
## 2026-06-24 Conservative Router Follow-Up

Stage 1 conclusion:
- S1 is an oracle diagnostic upper bound.
- S4 failed because medium/hard scenes were over-routed to direct.

Offline guard:
- Variant: conservative_v1
- Confidence threshold: 0.90
- Direct maximum object count: 3
- Audit rows: 900
- Pilot rows frozen: 120, 20 per subset

Paid status:
- No pilot inference has been run.
- A separate RUN_PAID_INFERENCE approval is required.
```

Fill in the actual audit distribution and artifact paths after generation.

- [ ] **Step 8: Review the final diff**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only scoped implementation, tests, docs, and
generated audit artifacts appear.

- [ ] **Step 9: Commit the offline gate**

Do not commit large generated JSON unless repository policy already tracks
experiment outputs. Commit the experiment log and code:

```bash
git add docs/experiments/2026-06-22-stage1-readiness.md
git commit -m "docs: record conservative router offline gate"
```

## Paid Pilot Gate

Stop after Task 9 and report:

- selected policy and thresholds;
- S4 route transitions under the guard;
- easy direct retention;
- medium/hard direct suppression;
- expected pilot call count;
- exact pilot command;
- confirmation that no paid inference has run.

Do not execute the 120-sample pilot until the user separately provides the
literal approval `RUN_PAID_INFERENCE`.
