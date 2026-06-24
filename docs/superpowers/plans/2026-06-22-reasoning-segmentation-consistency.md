# Reasoning-Segmentation Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace first-containing-point mask selection with an auditable geometric-consistency score and provide a fixed-reasoning replay path for segmentation ablations.

**Architecture:** Extend the pure scene-evidence module with mask scoring and nearest-mask fallback. Update `_predict_langsam_mask` to compare candidates across all semantic queries for the new `geometric_consistency` variant. Add a replay CLI that reads frozen reasoning decisions and reruns only segmentation, guaranteeing identical RSR across G0-G3.

**Tech Stack:** Python 3.10, NumPy, LangSAM, pandas/parquet, JSON, `unittest`.

---

## File Structure

- Modify `utils/scene_evidence.py`: mask consistency score and selection result.
- Modify `utils/utils.py`: multi-query candidate collection and metadata.
- Create `replay_segmentation.py`: no-VLM segmentation replay CLI.
- Create `test_replay_segmentation.py`: frozen-ID and metric invariants.
- Modify `test_scene_evidence.py` and `test_utils_output_limit.py`: scoring and integration tests.

### Task 1: Geometric-Consistency Mask Score

**Files:**
- Modify: `utils/scene_evidence.py`
- Modify: `test_scene_evidence.py`

- [ ] **Step 1: Write failing score tests**

```python
def test_consistent_mask_beats_higher_logit_wrong_instance(self):
    wrong = np.zeros((8, 8), dtype=bool)
    wrong[:3, :3] = True
    right = np.zeros((8, 8), dtype=bool)
    right[3:7, 3:7] = True
    selected = select_consistent_mask(
        masks=[wrong, right], confidences=[0.99, 0.70], point=(5, 5)
    )
    self.assertEqual(selected.index, 1)
    self.assertEqual(selected.fallback_reason, None)

def test_nearest_mask_fallback_is_explicit(self):
    selected = select_consistent_mask(
        masks=[self.left_mask, self.right_mask], confidences=[0.5, 0.5], point=(4, 4)
    )
    self.assertFalse(selected.contains_point)
    self.assertEqual(selected.fallback_reason, "no_candidate_contains_point")
```

- [ ] **Step 2: Verify missing-function failure**

Run: `.venv/bin/python -m unittest test_scene_evidence.SceneEvidenceTest.test_consistent_mask_beats_higher_logit_wrong_instance -v`

Expected: failure because `select_consistent_mask` is undefined.

- [ ] **Step 3: Implement the score and nearest fallback**

```python
@dataclass(frozen=True)
class ConsistentMaskSelection:
    index: int
    total_score: float
    contains_point: bool
    confidence: float
    area_ratio: float
    point_distance: float
    fallback_reason: str | None


def consistency_score(mask, confidence, point, confidence_weight=0.25, area_weight=0.15):
    mask = np.asarray(mask, dtype=bool)
    contains = _contains(mask, point)
    area_ratio = float(mask.mean()) if mask.size else 1.0
    distance = _distance_to_mask(mask, point)
    total = (2.0 if contains else 0.0) + confidence_weight * float(confidence) - area_weight * area_ratio
    return total, contains, area_ratio, distance
```

Select the highest score among point-containing masks. If none contains the
point, select minimum distance, then higher confidence, and set the fallback
reason.

- [ ] **Step 4: Run pure tests**

Run: `.venv/bin/python -m unittest test_scene_evidence -v`

Expected: all score, tie-break, empty-mask, and out-of-bounds tests pass.

- [ ] **Step 5: Commit**

```bash
git add utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: score reasoning-segmentation consistency"
```

### Task 2: Multi-Query Global Candidate Selection

**Files:**
- Modify: `utils/utils.py:1390-1495`
- Modify: `test_utils_output_limit.py`

- [ ] **Step 1: Write failing global-selection tests**

The fake LangSAM actor returns a high-logit point-inconsistent mask for query 1
and a lower-logit point-consistent mask for query 2. Assert that
`geometric_consistency` selects query 2 while `baseline` preserves query 1.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_utils_output_limit.UtilsOutputLimitTest.test_geometric_consistency_compares_all_queries -v`

Expected: `Unknown segmentation_variant: geometric_consistency`.

- [ ] **Step 3: Register the new variant and collect candidates globally**

Add `geometric_consistency` to `VALID_SEGMENTATION_VARIANTS`. In
`_predict_langsam_mask`, collect records containing query, query index, mask
index, confidence, mask, and box for every query before selecting. Do not return
after the first point-containing mask for this variant.

- [ ] **Step 4: Persist auditable metadata**

Return:

```python
{
    "langsam_selected_query": selected.query,
    "langsam_selected_mask_index": selected.mask_index,
    "langsam_mask_contains_point": selected.contains_point,
    "langsam_consistency_score": selected.total_score,
    "langsam_confidence": selected.confidence,
    "langsam_area_ratio": selected.area_ratio,
    "langsam_point_distance": selected.point_distance,
    "langsam_failure_reason": selected.fallback_reason,
}
```

- [ ] **Step 5: Run segmentation-unit tests**

Run: `.venv/bin/python -m unittest test_utils_output_limit -v`

Expected: all baseline, point-retry, and geometric-consistency behaviors pass.

- [ ] **Step 6: Commit**

```bash
git add utils/utils.py test_utils_output_limit.py
git commit -m "feat: select LangSAM masks by cross-query consistency"
```

### Task 3: Frozen-Reasoning Replay CLI

**Files:**
- Create: `replay_segmentation.py`
- Create: `test_replay_segmentation.py`

- [ ] **Step 1: Write failing manifest and invariant tests**

Test that replay rejects a details row without `selected_object_id` or
`molmo_point`, never imports or calls the reasoning client, and copies the
source row's `rsr_correct` unchanged.

- [ ] **Step 2: Verify missing-script failure**

Run: `.venv/bin/python -m unittest test_replay_segmentation -v`

Expected: `ModuleNotFoundError: No module named 'replay_segmentation'`.

- [ ] **Step 3: Implement replay input validation**

```python
def frozen_decision(detail):
    reasoning = detail.get("reasoning", {})
    selected_id = reasoning.get("selected_object_id")
    point = reasoning.get("molmo_point")
    if selected_id is None or point is None:
        raise ValueError("Replay requires selected_object_id and molmo_point")
    return {
        "selected_object_id": int(selected_id),
        "molmo_point": tuple(point),
        "mask_query": reasoning.get("mask_query") or reasoning.get("class_name"),
        "rsr_correct": int(detail["rsr_correct"]),
    }
```

- [ ] **Step 4: Implement replay evaluation**

Accept `--source-run`, `--output-run`, `--segmentation-variant`, `--splits`, and
`--subsets`. Load the matching parquet image and GT mask only after the frozen
decision is loaded. Run `_predict_langsam_mask`, compute IoU, write replay
details, and preserve `rsr_correct` exactly.

- [ ] **Step 5: Add a no-paid-inference guard**

The script must not import `evaluate_mimo`, patch the OpenAI client, or call
`_call_reasoning_model`. A unit test patches `_call_reasoning_model` to raise and
asserts replay still succeeds.

- [ ] **Step 6: Run replay tests**

Run: `.venv/bin/python -m unittest test_replay_segmentation -v`

Expected: all tests pass on temporary images and masks.

- [ ] **Step 7: Commit**

```bash
git add replay_segmentation.py test_replay_segmentation.py
git commit -m "feat: replay segmentation with frozen reasoning"
```

### Task 4: Replay Summary and RSR Invariant

**Files:**
- Modify: `replay_segmentation.py`
- Modify: `test_replay_segmentation.py`

- [ ] **Step 1: Write failing summary tests**

Require `n`, `rsr`, `ssr`, `mean_iou`, `rsr_only`,
`point_consistency_failures`, `recovery_successes`, and `same_class_mask_swaps`.
Require replay RSR counts to equal source RSR counts or raise an error.

- [ ] **Step 2: Verify failure**

Run: `.venv/bin/python -m unittest test_replay_segmentation.ReplaySegmentationTest.test_summary_enforces_source_rsr -v`

Expected: failure because summary validation is missing.

- [ ] **Step 3: Implement summary aggregation and validation**

```python
if replay_summary["rsr_count"] != source_summary["rsr_count"]:
    raise RuntimeError("Segmentation replay changed frozen reasoning outcomes")
```

Write `segmentation_replay_summary.json` with per-split, per-subset, and overall
metrics.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m unittest test_replay_segmentation test_scene_evidence test_utils_output_limit -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add replay_segmentation.py test_replay_segmentation.py
git commit -m "feat: audit fixed-reasoning segmentation replay"
```

### Task 5: Segmentation Verification Gate

**Files:**
- No file changes.

- [ ] **Step 1: Run the complete non-paid segmentation suite**

Run: `.venv/bin/python -m unittest test_scene_evidence test_utils_output_limit test_replay_segmentation test_reasoning_resume -v`

Expected: all tests pass.

- [ ] **Step 2: Verify replay CLI help without model initialization**

Run: `.venv/bin/python replay_segmentation.py --help`

Expected: exit 0 and list source/output/variant arguments without loading GPU weights.

- [ ] **Step 3: Confirm no reasoning API path**

Run: `rg -n "_call_reasoning_model|create_mimo_client|OpenAI" replay_segmentation.py`

Expected: no matches.

