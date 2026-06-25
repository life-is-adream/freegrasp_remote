# Unified Hard-Safe Protocol V1 Design

Date: 2026-06-25

Branch: `freegrasp_codex`

Purpose: replace the failed depth/router direction with one robust query-level
protocol. The protocol should be conservative under uncertainty, repair common
ID and mask failures, and target the dominant observed failure mode:
`iou_below_threshold`.

## 1. Decision

Cancel the depth-classifier and learned routing direction for the next
experiment.

Do not run D2-D4, D1-v2, V5-V8, or any outcome-selector paid experiment unless
the user explicitly restarts that direction.

The next experiment should improve the protocol itself:

```text
Unified hard-safe reasoning + ranked candidates + ID repair + point-constrained mask repair
```

## 2. Why This Is the Right Next Move

The route-selection line failed for two independent reasons:

- Difficulty routing is not the same problem as selecting a successful
  first-grasp protocol for a specific query target.
- Outcome selector replay also failed to generalize under scene-grouped
  validation.

The existing experiment summaries point to a more useful target:

- S1, the oracle-feature hard-blocker-first reference, is much stronger than S0.
- Most remaining failures across S0/S1/S4/D1 are `iou_below_threshold`.
- Hard subsets remain weak even when the protocol is helped by oracle-like
  routing, which indicates that ID/mask/first-grasp grounding is the practical
  bottleneck.

Therefore the next unit of progress should be a single robust protocol with
explicit repair hooks, not another selector.

## 3. Core Principle

Use one protocol for every query:

```text
When confident the target is free and visible, grasp target.
When blocked, hidden, ambiguous, or uncertain, remove a visible direct blocker.
If still uncertain, choose the hard-safe action: remove blocker.
```

The protocol should be conservative because the cost of a hard scene routed to
direct target is larger than the cost of an easy scene routed through one
blocker-safe check.

## 4. Proposed Hook Names

Add these names after implementation:

- prompt variant: `unified_hard_safe_v1_json`
- subset policy: `unified_hard_safe_v1`
- optional segmentation variant: `ranked_point_repair`
- optional ablation policies:
  - `unified_hard_safe_no_hard_fallback`
  - `unified_hard_safe_no_ranked_candidates`
  - `unified_hard_safe_no_point_repair`
  - `unified_hard_safe_no_id_repair`

The first implementation may keep `routing_variant="none"`. This is not a
router experiment.

## 5. Reasoning Output Schema

The new prompt must require strict JSON:

```json
{
  "target_object_id": 3,
  "target_status": "free_visible",
  "first_grasp_object_id": 3,
  "action": "grasp_target",
  "ranked_first_grasp_candidates": [3, 5, 7],
  "mask_query": "red box",
  "confidence": 0.82,
  "evidence": {
    "target_evidence": "id 3 matches the requested red box",
    "blocker_evidence": "none",
    "uncertainty": []
  }
}
```

Allowed `target_status` values:

- `free_visible`
- `visible_but_blocked`
- `mostly_hidden`
- `uncertain`

Allowed `action` values:

- `grasp_target`
- `remove_blocker`

Schema rules:

- `first_grasp_object_id` must be visible in the Molmo ID table.
- `ranked_first_grasp_candidates` must contain visible Molmo IDs only.
- If `action="remove_blocker"`, `first_grasp_object_id` must be the visible
  blocker to remove first.
- `mask_query` must be a short object phrase, not a relation sentence.
- `mask_query` must not include location-only words such as left, right, top,
  bottom, nearest, behind, or under.

## 6. Hard-Safe Decision Repair

After parsing the model output, apply deterministic repair before segmentation.

### 6.1 Valid direct target

Allow `grasp_target` only when all are true:

- `target_status == "free_visible"`;
- `first_grasp_object_id == target_object_id`;
- confidence is at least `0.70`;
- no blocker evidence is present;
- no uncertainty evidence is present.

### 6.2 Hard-safe fallback

Force `remove_blocker` when any are true:

- `target_status` is `visible_but_blocked`, `mostly_hidden`, or `uncertain`;
- confidence is below `0.70`;
- blocker evidence is non-empty;
- ranked candidates disagree with `first_grasp_object_id`;
- `target_object_id` is invalid or missing;
- parser output is incomplete but a ranked blocker candidate exists.

If no reliable blocker exists, use the first valid visible ID in
`ranked_first_grasp_candidates`. If ranked candidates are empty, fall back to the
legacy parsed ID behavior and record `fallback_reason`.

This rule implements the user preference:

```text
uncertain -> hardest safe protocol
```

## 7. ID Repair

Before segmentation, repair object identity:

1. Check whether `first_grasp_object_id` is a visible Molmo ID.
2. If invalid, replace it with the first visible ID in
   `ranked_first_grasp_candidates`.
3. If `action="grasp_target"` but target is invalid or uncertain, switch to
   `remove_blocker` and use the first valid ranked candidate.
4. Record:
   - `pre_repair_first_grasp_object_id`
   - `selected_first_grasp_object_id`
   - `id_repair_applied`
   - `id_repair_reason`

No ground-truth IDs may be used in this repair.

## 8. Point-Constrained Mask Repair

The current dominant failure mode is `iou_below_threshold`, so segmentation
must not rely on only one free-form phrase.

Use the selected Molmo ID and its point coordinate as the primary segmentation
anchor.

Mask selection priority:

1. SAM/LangSAM mask contains the selected Molmo point.
2. Mask area is not implausibly large.
3. Mask is not near-duplicate with another candidate mask unless the selected
   point is contained and the area is smaller.
4. If multiple masks contain the point, choose the smallest high-confidence
   mask.
5. If no mask contains the point, choose nearest mask and record
   `fallback_reason="no_candidate_contains_point"`.

Ranked candidate retry:

1. Segment `first_grasp_object_id`.
2. If mask is empty, huge, or duplicate-suspect, try the next ID in
   `ranked_first_grasp_candidates`.
3. Stop after top 3 candidates.
4. Record all attempts in reasoning metadata.

This can improve SSR and RSR because the first-grasp object is evaluated by
mask IoU.

## 9. Metadata Contract

Every detail row should include:

- `prompt_variant`
- `protocol_version`: `unified_hard_safe_v1`
- `raw_model_json`
- `parsed_decision`
- `pre_repair_decision`
- `post_repair_decision`
- `id_repair_applied`
- `hard_fallback_applied`
- `ranked_first_grasp_candidates`
- `segmentation_attempts`
- `selected_gt_id` if derivable from Molmo mapping without using it for
  decision-making
- `failure_reason`

The metadata is required so failed cases can be audited without rerunning paid
inference.

## 10. Offline Tests Before Paid Runs

Do not run MiMo until all cheap tests pass.

Required tests:

- Parser accepts the strict JSON schema.
- Parser rejects or repairs invalid visible IDs.
- Hard fallback fires on low confidence, blocked/hidden/uncertain target, or
  blocker evidence.
- Direct target is preserved only when target is free, visible, high-confidence,
  and unblocked.
- Ranked candidate retry tries valid IDs in order.
- Point-constrained mask selector prefers a mask containing the selected Molmo
  point.
- Duplicate masks do not silently select a huge wrong mask.
- CLI accepts `unified_hard_safe_v1_json`,
  `unified_hard_safe_v1`, and ablation policy names.

Expected command:

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
.venv/bin/python -m unittest \
  test_utils_output_limit.py \
  test_scene_evidence.py \
  test_evaluate_entrypoints.py \
  test_evaluate_all_summary.py \
  test_evaluate_mimo_full_protocol.py
```

Then run:

```bash
.venv/bin/python -m unittest discover -v
```

## 11. Paid Experiment Gates

Only run paid inference after unit tests pass.

Use reuse Molmo cache first. Do not clear Molmo cache.

Stop after each phase and report before continuing.

### Phase A: hard smoke

Run a small hard-only smoke first. The supervising agent should choose a small,
fixed, representative set from hard split 0.

Required pass criteria:

- no parser failures;
- no invalid visible ID failures;
- no API/corrupted-image failures beyond existing transient behavior;
- hard fallback appears in metadata;
- segmentation attempts are recorded.

If the smoke fails, do not run split 0.

### Phase B: split 0 full 300

Run all six split-0 subsets only.

Pass criteria:

- overall split-0 RSR must beat S0 split-0 RSR;
- hard split-0 RSR must not drop below S1 hard split-0 by more than 5
  percentage points;
- SSR must not collapse below S0 split-0 SSR by more than 3 percentage points;
- parser failure rate must be below 1%.

If Phase B fails, stop and analyze. Do not run full 900.

### Phase C: ablations

Only after Phase B passes:

- no hard fallback;
- no ranked candidates;
- no point repair;
- no ID repair.

The goal is to isolate which repair actually helps.

### Phase D: full 900

Only after Phase B and C support the method, run splits 0, 1, and 2.

## 12. Suggested Run IDs

- `UHS1`: unified hard-safe v1 main, split 0.
- `UHS2`: no hard fallback.
- `UHS3`: no ranked candidates.
- `UHS4`: no point-constrained mask repair.
- `UHS5`: no ID repair.
- `UHSF1`: full 900 main run if split 0 passes.

## 13. Implementation Targets

Likely files to edit:

- `utils/utils.py`: prompt, parser, decision repair, segmentation retry
  integration.
- `utils/scene_evidence.py`: point-constrained mask scoring and duplicate-mask
  safeguards if not already sufficient.
- `reasoning_eval.py`: preserve metadata in detail rows if needed.
- `evaluate_all.py`: subset policy registration.
- `evaluate_mimo.py`: CLI registration.
- `evaluate_mimo_full_protocol.py`: CLI registration.
- tests:
  - `test_utils_output_limit.py`
  - `test_scene_evidence.py`
  - `test_evaluate_entrypoints.py`
  - `test_evaluate_all_summary.py`
  - `test_evaluate_mimo_full_protocol.py`

Do not modify `/home/public/zb/FreeGrasp_code-main`.

## 14. Execution Instructions for Supervising Agent

### 14.1 Confirm workspace

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
git status --short --branch
```

Expected branch:

```text
freegrasp_codex
```

### 14.2 Confirm no paid process is already running

```bash
ps -ef | grep -E "evaluate_mimo|reasoning_eval|mimo|qwen|dashscope" | grep -v grep || true
```

If a paid run is active, stop and ask the user.

### 14.3 Implement UHS1 hooks

Add:

- `prompt_variant="unified_hard_safe_v1_json"`
- `subset_policy="unified_hard_safe_v1"`
- `segmentation_variant="ranked_point_repair"` if implemented separately
- metadata fields listed in this document

### 14.4 Run tests

```bash
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
.venv/bin/python -m unittest \
  test_utils_output_limit.py \
  test_scene_evidence.py \
  test_evaluate_entrypoints.py \
  test_evaluate_all_summary.py \
  test_evaluate_mimo_full_protocol.py

.venv/bin/python -m unittest discover -v
```

If tests fail, stop.

### 14.5 Hard smoke command

Use a dedicated output directory. Do not overwrite S0/S1/S4/D1.

If a hard-smoke helper exists, use it. If not, implement one before running a
paid smoke. Command shape:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python run_unified_hard_safe_smoke.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_v1 \
  --prompt-variant unified_hard_safe_v1_json \
  --segmentation-variant ranked_point_repair \
  --run-root data/output/ablation_matrix/UHS1_smoke \
  --split 0 \
  --subsets hard_no_ambi hard_yes_ambi \
  --samples-per-subset 10 \
  --reuse-molmo
```

If no helper is implemented, do not improvise by editing full-protocol scripts
in a risky way. Add a small tested helper first.

### 14.6 Split 0 command

Only after smoke passes:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_v1 \
  --segmentation-variant ranked_point_repair \
  --run-root data/output/ablation_matrix/UHS1 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

After completion, compare with S0/S1 split 0 before any ablation.

### 14.7 Ablation commands

Only after UHS1 split 0 passes:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_no_hard_fallback \
  --segmentation-variant ranked_point_repair \
  --run-root data/output/ablation_matrix/UHS2 \
  --splits 0 \
  --reuse-molmo \
  --resume
```

Repeat with:

- `unified_hard_safe_no_ranked_candidates` -> `UHS3`
- `unified_hard_safe_no_point_repair` -> `UHS4`
- `unified_hard_safe_no_id_repair` -> `UHS5`

### 14.8 Full 900 command

Only after UHS1 and ablations justify full evaluation:

```bash
PYTHONPATH=/home/wyl/miniconda3/lib/python3.13/site-packages \
.venv/bin/python evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy unified_hard_safe_v1 \
  --segmentation-variant ranked_point_repair \
  --run-root data/output/ablation_matrix/UHSF1 \
  --splits 0 1 2 \
  --reuse-molmo \
  --resume
```

## 15. Stop Conditions

Stop immediately if:

- any command would overwrite S0/S1/S4/D1/D1-v2 outputs;
- hard fallback is removed from the main protocol;
- parser outputs are not strict JSON;
- `ranked_first_grasp_candidates` are not recorded;
- segmentation attempts are not recorded;
- split-0 UHS1 does not beat S0 split-0 RSR;
- hard subset RSR collapses;
- paid inference would start before tests pass.

## 16. Expected Outcome

This experiment should answer a focused question:

```text
Can a single hard-safe protocol plus deterministic repair beat the original
protocol without needing a learned router?
```

If yes, proceed to ablations and full 900.

If no, the next target is segmentation quality, not route selection.

