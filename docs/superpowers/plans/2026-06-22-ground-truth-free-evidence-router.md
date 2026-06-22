# Ground-Truth-Free Evidence Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic first-grasp router that uses Molmo points, SAM-predicted geometry, and VLM evidence without reading benchmark difficulty, semantic, or instance annotations.

**Architecture:** Add a pure `utils/scene_evidence.py` module for candidate-mask selection, geometry extraction, and routing records. `utils/utils.py` will acquire point-prompted SAM masks and orchestrate either count-only, pure-VLM, or predicted-geometry routing before invoking the existing direct, target-first, or blocker-first prompts. Oracle v10 remains available only under explicit `oracle_feature` metadata.

**Tech Stack:** Python 3.10, NumPy, Segment Anything `SamPredictor`, existing MiMo OpenAI-compatible client, `unittest`.

---

## File Structure

- Create `utils/scene_evidence.py`: pure mask selection, bbox/relation extraction, route records, and provenance validation.
- Create `test_scene_evidence.py`: CPU-only unit tests for predicted evidence.
- Modify `utils/utils.py`: point-prompt SAM adapter, router prompt/parser, and automatic routing orchestration.
- Modify `evaluate_common.py`: pass routing and feature-source options into per-sample inference.
- Modify `evaluate_all.py`: register automatic routing policies without mapping from subset names.
- Modify `evaluate_mimo.py`: expose routing CLI choices.
- Modify `evaluate_mimo_full_protocol.py`: forward routing configuration across all splits.
- Modify `test_utils_output_limit.py`, `test_evaluate_all_summary.py`, `test_evaluate_mimo.py`, and `test_evaluate_mimo_full_protocol.py`: integration and provenance regression tests.

### Task 1: Pure Predicted-Geometry Evidence

**Files:**
- Create: `utils/scene_evidence.py`
- Create: `test_scene_evidence.py`

- [ ] **Step 1: Write failing mask-selection and geometry tests**

```python
class SceneEvidenceTest(unittest.TestCase):
    def test_select_point_mask_prefers_small_consistent_candidate(self):
        large = np.ones((10, 10), dtype=bool)
        small = np.zeros((10, 10), dtype=bool)
        small[3:7, 3:7] = True
        result = select_point_mask([large, small], [0.95, 0.80], (5, 5))
        self.assertEqual(result.index, 1)
        self.assertTrue(result.contains_point)

    def test_build_predicted_geometry_never_copies_gt_id(self):
        parsed = [(7, 5, 5, 999)]
        mask = np.zeros((10, 10), dtype=bool)
        mask[2:8, 2:8] = True
        evidence = build_predicted_geometry(parsed, {7: mask})
        self.assertNotIn("gt_id", json.dumps(evidence))
        self.assertEqual(evidence["candidates"][7]["bbox"], (2, 2, 7, 7))
```

- [ ] **Step 2: Run the tests and verify missing-module failure**

Run: `.venv/bin/python -m unittest test_scene_evidence -v`

Expected: `ModuleNotFoundError: No module named 'utils.scene_evidence'`.

- [ ] **Step 3: Implement pure selection and geometry functions**

```python
from dataclasses import asdict, dataclass
import numpy as np


@dataclass(frozen=True)
class PointMaskSelection:
    index: int
    score: float
    contains_point: bool
    area_ratio: float


def _contains(mask, point):
    x, y = point
    return 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and bool(mask[y, x])


def select_point_mask(masks, scores, point, area_weight=0.25):
    ranked = []
    for index, mask in enumerate(masks):
        mask = np.asarray(mask, dtype=bool)
        area_ratio = float(mask.mean()) if mask.size else 1.0
        contains = _contains(mask, point)
        score = (2.0 if contains else 0.0) + float(scores[index]) - area_weight * area_ratio
        ranked.append(PointMaskSelection(index, score, contains, area_ratio))
    if not ranked:
        raise ValueError("SAM returned no point-mask candidates")
    return max(ranked, key=lambda item: item.score)


def build_predicted_geometry(parsed_data, masks_by_id):
    candidates = {}
    for object_id, x, y, _ignored_gt_id in parsed_data:
        mask = np.asarray(masks_by_id[object_id], dtype=bool)
        ys, xs = np.where(mask)
        if not xs.size:
            continue
        candidates[object_id] = {
            "point": (int(x), int(y)),
            "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
            "area": int(mask.sum()),
            "center": (int(round(xs.mean())), int(round(ys.mean()))),
        }
    return {"source": "predicted_sam_point_masks", "candidates": candidates, "relations": []}
```

- [ ] **Step 4: Add pairwise overlap and vertical-order relations**

Implement `add_pairwise_relations(evidence)` with intersection-over-smaller-box overlap, `above`/`below` vertical order, and relation names `overlaps` or `near`. Do not emit `contact` or `coverage` unless predicted masks overlap.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m unittest test_scene_evidence -v`

Expected: all tests pass without importing Torch, LangSAM, or dataset files.

- [ ] **Step 6: Commit**

```bash
git add utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: derive scene evidence from predicted point masks"
```

### Task 2: Point-Prompt SAM Adapter

**Files:**
- Modify: `utils/utils.py:20-150`
- Test: `test_utils_output_limit.py`

- [ ] **Step 1: Write a failing adapter test with a fake `SamPredictor`**

The test must assert one `set_image` call, one `predict` call per Molmo point,
and that the fourth tuple field is never passed to the predictor.

```python
evidence = self.utils._predict_geometry_from_molmo_points(
    image_pil=np.zeros((20, 20, 3), dtype=np.uint8),
    parsed_data=[(3, 4, 5, 900), (8, 10, 11, 901)],
    predictor=fake_predictor,
)
self.assertEqual(fake_predictor.points, [(4, 5), (10, 11)])
self.assertEqual(evidence["source"], "predicted_sam_point_masks")
```

- [ ] **Step 2: Verify the test fails**

Run: `.venv/bin/python -m unittest test_utils_output_limit.UtilsOutputLimitTest.test_predict_geometry_uses_only_molmo_points -v`

Expected: failure because `_predict_geometry_from_molmo_points` is undefined.

- [ ] **Step 3: Implement the adapter**

```python
def _predict_geometry_from_molmo_points(image_pil, parsed_data, predictor=None):
    predictor = predictor or langsam_actor.sam
    predictor.set_image(np.asarray(image_pil))
    masks_by_id = {}
    selections = {}
    for object_id, x, y, _ignored_gt_id in parsed_data:
        masks, scores, _logits = predictor.predict(
            point_coords=np.asarray([[x, y]], dtype=np.float32),
            point_labels=np.asarray([1], dtype=np.int32),
            multimask_output=True,
        )
        selected = select_point_mask(masks, scores, (x, y))
        masks_by_id[object_id] = np.asarray(masks[selected.index], dtype=bool)
        selections[object_id] = asdict(selected)
    evidence = build_predicted_geometry(parsed_data, masks_by_id)
    evidence["point_mask_selections"] = selections
    return add_pairwise_relations(evidence)
```

- [ ] **Step 4: Run adapter and import-path tests**

Run: `.venv/bin/python -m unittest test_utils_output_limit.UtilsOutputLimitTest.test_predict_geometry_uses_only_molmo_points test_langsam_import_paths -v`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add utils/utils.py test_utils_output_limit.py
git commit -m "feat: prompt SAM from Molmo points"
```

### Task 3: Router Schema, Prompt, and Parser

**Files:**
- Modify: `utils/utils.py:400-650, 850-1150`
- Test: `test_utils_output_limit.py`

- [ ] **Step 1: Write failing prompt and parser tests**

Require JSON keys `route_mode`, `route_confidence`, `target_object_id`,
`ambiguity_evidence`, and `blocker_evidence`. Require the prompt to state that
`near` alone cannot select `blocker_first`.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m unittest test_utils_output_limit.UtilsOutputLimitTest.test_evidence_router_prompt_has_bounded_schema test_utils_output_limit.UtilsOutputLimitTest.test_parse_route_assessment_rejects_unknown_mode -v`

Expected: failures for missing router functions.

- [ ] **Step 3: Implement the route assessment contract**

```python
VALID_ROUTE_MODES = {"direct", "target_first", "blocker_first"}


def parse_route_assessment(output, visible_object_ids):
    data = json.loads(re.search(r"\{.*\}", output, flags=re.DOTALL).group(0))
    mode = data["route_mode"]
    if mode not in VALID_ROUTE_MODES:
        raise ValueError(f"Unknown route mode: {mode}")
    target_id = data.get("target_object_id")
    if target_id is not None and int(target_id) not in visible_object_ids:
        target_id = None
    return {
        "route_mode": mode,
        "route_confidence": float(data.get("route_confidence", 0.0)),
        "target_object_id": int(target_id) if target_id is not None else None,
        "target_label": str(data.get("target_label", "target")),
        "ambiguity_evidence": list(data.get("ambiguity_evidence", [])),
        "blocker_evidence": list(data.get("blocker_evidence", [])),
    }
```

- [ ] **Step 4: Add `evidence_router_json` to `get_reasoning_system_prompt` and input formatting**

The input must include visible IDs, Molmo points, predicted boxes/relations only
when `include_predicted_geometry=True`, and `visible_object_count`. It must not
contain `GT_ID`, `instances_objects`, or `instances_semantic`.

- [ ] **Step 5: Run focused prompt/parser tests**

Run: `.venv/bin/python -m unittest test_utils_output_limit -v`

Expected: existing prompt variants and new router tests pass.

- [ ] **Step 6: Commit**

```bash
git add utils/utils.py test_utils_output_limit.py
git commit -m "feat: add evidence-adaptive routing contract"
```

### Task 4: Automatic Routing Orchestration and Provenance

**Files:**
- Modify: `utils/utils.py:1498-1785`
- Modify: `reasoning_eval.py:134-330`
- Test: `test_utils_output_limit.py`
- Test: `test_reasoning_resume.py`

- [ ] **Step 1: Write failing routing-flow tests**

Cover these exact flows:

- count-only with 3 IDs invokes `direct_target` once;
- pure VLM router omits predicted geometry;
- predicted-geometry router includes `source=predicted_sam_point_masks`;
- `direct` uses the router's valid target without a second VLM call;
- `target_first` invokes `target_first_evidence_gate_v9_json`;
- `blocker_first` invokes `hard_blocker_first_v10_json`;
- no automatic variant calls `_load_semantic_labels_for_candidates` or
  `_load_geometry_features_for_candidates`.

- [ ] **Step 2: Verify the focused tests fail**

Run: `.venv/bin/python -m unittest test_utils_output_limit.UtilsOutputLimitTest.test_predicted_router_never_loads_gt_features test_utils_output_limit.UtilsOutputLimitTest.test_router_direct_path_uses_one_model_call -v`

Expected: failure because routing options are not accepted.

- [ ] **Step 3: Add routing parameters and metadata**

Extend `get_prediction_result` and `process_dataset` with:

```python
routing_variant="none"  # none, count_only, vlm_two_stage, predicted_geometry
feature_source="none"   # none, predicted, oracle_feature
```

Record `route_mode`, `route_confidence`, `routing_variant`, `feature_source`,
`router_raw_output`, and `router_call_count` in `reasoning`.

- [ ] **Step 4: Implement specialized prompt dispatch**

Use a helper that returns `(system_prompt, reasoning_input_text)` for the chosen
mode. `target_first` receives predicted relations; `blocker_first` receives the
same relations but no benchmark difficulty. Low-confidence or malformed router
output falls back to `target_first`, never `blocker_first`.

- [ ] **Step 5: Enforce provenance**

Raise `ValueError` when `routing_variant != "none"` and
`feature_source == "oracle_feature"`. Preserve explicit oracle policies only
when `routing_variant == "none"`.

- [ ] **Step 6: Run inference-unit tests**

Run: `.venv/bin/python -m unittest test_utils_output_limit test_reasoning_resume -v`

Expected: all tests pass and fake-client call counts match the selected route.

- [ ] **Step 7: Commit**

```bash
git add utils/utils.py reasoning_eval.py test_utils_output_limit.py test_reasoning_resume.py
git commit -m "feat: route first-grasp reasoning from predicted evidence"
```

### Task 5: CLI and Full-Protocol Wiring

**Files:**
- Modify: `evaluate_common.py:71-118`
- Modify: `evaluate_all.py:1-440`
- Modify: `evaluate_mimo.py:180-350`
- Modify: `evaluate_mimo_full_protocol.py:20-196`
- Test: `test_evaluate_all_summary.py`
- Test: `test_evaluate_mimo.py`
- Test: `test_evaluate_mimo_full_protocol.py`

- [ ] **Step 1: Write failing CLI and policy tests**

Require `--routing-variant` choices `none`, `count_only`, `vlm_two_stage`, and
`predicted_geometry`. Add subset policy `automatic_evidence_v1`. Assert that its
configuration is identical for all six subset names and contains no difficulty-
specific prompt selection.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m unittest test_evaluate_all_summary test_evaluate_mimo test_evaluate_mimo_full_protocol -v`

Expected: new choice/policy assertions fail.

- [ ] **Step 3: Thread routing options through every evaluation entry point**

Add `routing_variant` and `feature_source` to `evaluate_subset`,
`evaluate_pipeline`, `evaluate_mimo_pipeline`, and `run_full_protocol`. For
`automatic_evidence_v1`, use a neutral initial prompt and
`routing_variant="predicted_geometry"`, `feature_source="predicted"` for every
subset.

- [ ] **Step 4: Add summary provenance fields**

Persist `routing_variant`, `feature_source`, `uses_benchmark_difficulty`, and
`uses_gt_features` in `summary.json` and `full_protocol_summary.json`.

- [ ] **Step 5: Run CLI/full-protocol tests**

Run: `.venv/bin/python -m unittest test_evaluate_all_summary test_evaluate_mimo test_evaluate_mimo_full_protocol test_evaluate_entrypoints -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add evaluate_common.py evaluate_all.py evaluate_mimo.py evaluate_mimo_full_protocol.py test_evaluate_all_summary.py test_evaluate_mimo.py test_evaluate_mimo_full_protocol.py test_evaluate_entrypoints.py
git commit -m "feat: expose automatic evidence routing in evaluations"
```

### Task 6: Router Verification Gate

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the non-paid regression suite**

Run: `.venv/bin/python -m unittest test_scene_evidence test_utils_output_limit test_reasoning_resume test_evaluate_all_summary test_evaluate_mimo test_evaluate_mimo_full_protocol test_evaluate_entrypoints -v`

Expected: all tests pass; no API call occurs because every model client is fake.

- [ ] **Step 2: Run provenance search**

Run: `rg -n "instances_objects|instances_semantic|evaluation_subset" utils/scene_evidence.py`

Expected: no matches.

- [ ] **Step 3: Document commands without executing inference**

Add a README example using `--routing-variant predicted_geometry --reuse-molmo`
and label it as a paid MiMo command requiring explicit approval.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document ground-truth-free routing"
```

