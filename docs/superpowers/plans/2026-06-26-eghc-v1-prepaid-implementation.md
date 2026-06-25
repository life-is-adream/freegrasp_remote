# EGHC-v1 Pre-Paid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the no-GT `EGHC-v1` stack through the pre-paid freeze boundary, including provenance audit, GT isolation, deterministic cascade, optional challenger training, and sealed offline artifacts, without launching any paid reasoning call.

**Architecture:** The work is split into independently testable work packages because the approved spec spans multiple subsystems. The main path is: historical provenance and clean S0 first, then sanitized inference inputs and GT guards, then the deterministic no-GT cascade, then segmentation and artifact sealing, and only then offline challenger training and frozen-policy outputs.

**Tech Stack:** Python, `unittest`, existing FreeGrasp entrypoints, MiMo/Qwen patch helpers, NumPy, JSON artifacts, Conda `freegrasp`

---

## File Structure

- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_historical_runs.py`
  - Build the run registry, classify historical runs, and emit the clean-S0 decision.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/build_sanitized_inference_bundle.py`
  - Precompute allowed inference-only scene bundles so runtime never opens GT-bearing benchmark NPZ files.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/gt_access_guard.py`
  - Central forbidden-field scanner and runtime guard helpers.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/deployable_evidence.py`
  - Load sanitized bundles and build no-GT evidence packets.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_schemas.py`
  - Dataclasses and parser helpers for Call 1, route selection, Call 2, adjudication, and sealed artifacts.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_router.py`
  - Deterministic guard, route state machine, and optional challenger hook.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_adjudicator.py`
  - Conditional Qwen trigger policy and decision acceptance/replacement rules.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_segmentation.py`
  - No-GT mask repair and ranked-candidate fallback.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_artifacts.py`
  - Sealed prediction artifacts and scorer handoff payloads.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_eghc_offline.py`
  - Fixed-cache offline audit for evidence, router, and segmentation replay.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/train_eghc_challenger.py`
  - Scene-disjoint challenger training and promotion report.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/score_sealed_predictions.py`
  - Isolated scorer that reads only sealed predictions plus GT.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/utils.py`
  - Add a single delegation hook only; do not embed the full EGHC cascade here.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_all.py`
  - Register `eghc_*` subset policies and map them to the new modules.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo.py`
  - Accept the new subset policies for single-subset smoke and future paid approvals.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo_full_protocol.py`
  - Accept the new subset policies for future split/full execution.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_common.py`
  - Route evaluation through the sanitized inference bundle and sealed scoring flow.
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/reasoning_eval.py`
  - Preserve immutable sample identity and pass EGHC metadata into the scorer boundary.
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_historical_audit.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_gt_isolation.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_evidence_builder.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_router.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_adjudicator.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_segmentation.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_artifacts.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_challenger.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_all_summary.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo_full_protocol.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_entrypoints.py`

### Task 1: Historical Provenance Registry And Clean S0 Decision

**Files:**
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_historical_runs.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_historical_audit.py`

- [ ] **Step 1: Write the failing audit tests**

```python
import unittest

from audit_historical_runs import classify_run


class HistoricalRunAuditTest(unittest.TestCase):
    def test_classifies_uhs1_like_rows_as_oracle_assisted(self):
        manifest = {"feature_source": "none", "subset_policy": "unified_hard_safe_v1"}
        sample = {
            "reasoning": {
                "semantic_source": "instances_semantic",
                "geometry_source": "instances_objects",
                "molmo_to_gt_map_used": True,
            }
        }
        result = classify_run(manifest, [sample])
        self.assertEqual(result["provenance_class"], "oracle_assisted")

    def test_classifies_plain_s0_like_rows_as_clean_no_gt(self):
        manifest = {"feature_source": "none", "subset_policy": "original_protocol"}
        sample = {"reasoning": {"semantic_source": "molmo_text", "geometry_source": None}}
        result = classify_run(manifest, [sample])
        self.assertEqual(result["provenance_class"], "clean_no_gt")
```

- [ ] **Step 2: Run the audit test to verify it fails**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_historical_audit.py -v
```

Expected: `FAIL` because `audit_historical_runs.py` does not exist yet.

- [ ] **Step 3: Write the minimal audit implementation**

```python
ORACLE_MARKERS = {
    "instances_semantic",
    "instances_objects",
    "oracle_feature",
}


def classify_run(manifest, details_rows):
    feature_source = manifest.get("feature_source")
    reasoning_rows = [row.get("reasoning", {}) for row in details_rows]
    semantic_sources = {row.get("semantic_source") for row in reasoning_rows}
    geometry_sources = {row.get("geometry_source") for row in reasoning_rows}
    used_gt_map = any(bool(row.get("molmo_to_gt_map_used")) for row in reasoning_rows)

    if feature_source == "oracle_feature" or used_gt_map:
        provenance_class = "oracle_assisted"
    elif ORACLE_MARKERS & semantic_sources or ORACLE_MARKERS & geometry_sources:
        provenance_class = "oracle_assisted"
    else:
        provenance_class = "clean_no_gt"

    return {
        "provenance_class": provenance_class,
        "feature_source": feature_source,
        "semantic_sources": sorted(x for x in semantic_sources if x is not None),
        "geometry_sources": sorted(x for x in geometry_sources if x is not None),
    }
```

- [ ] **Step 4: Re-run the audit test**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_historical_audit.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the provenance audit scaffold**

```bash
git add audit_historical_runs.py test_eghc_historical_audit.py
git commit -m "feat: add eghc historical run audit scaffold"
```

### Task 2: Build A Sanitized Inference Bundle And GT Access Guard

**Files:**
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/build_sanitized_inference_bundle.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/gt_access_guard.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/deployable_evidence.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_gt_isolation.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_evidence_builder.py`

- [ ] **Step 1: Write the failing GT-isolation tests**

```python
import unittest

from utils.gt_access_guard import assert_payload_has_no_forbidden_gt_keys


class GTIsolationTest(unittest.TestCase):
    def test_forbidden_gt_key_raises(self):
        with self.assertRaisesRegex(RuntimeError, "instances_objects"):
            assert_payload_has_no_forbidden_gt_keys({"instances_objects": "forbidden"})

    def test_sanitized_bundle_allows_depth_and_intrinsics(self):
        payload = {
            "rgb_path": "scene1.png",
            "depth_path": "scene1_depth.npy",
            "camera_intrinsics": [1.0] * 9,
            "visible_points": [{"object_id": 3, "x": 10, "y": 12}],
        }
        assert_payload_has_no_forbidden_gt_keys(payload)
```

- [ ] **Step 2: Run the GT-isolation tests and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_gt_isolation.py test_eghc_evidence_builder.py -v
```

Expected: `FAIL` because the guard and bundle builder do not exist yet.

- [ ] **Step 3: Write the minimal bundle and guard implementation**

```python
FORBIDDEN_GT_KEYS = {
    "instances_objects",
    "instances_semantic",
    "groundTruthObjIds",
    "gt_masks",
    "molmo_to_gt_map",
    "difficulty",
}


def assert_payload_has_no_forbidden_gt_keys(payload, path="root"):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_GT_KEYS:
                raise RuntimeError(f"Forbidden GT field detected at {path}.{key}")
            assert_payload_has_no_forbidden_gt_keys(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_payload_has_no_forbidden_gt_keys(value, f"{path}[{index}]")


def build_evidence_packet(bundle):
    assert_payload_has_no_forbidden_gt_keys(bundle)
    return {
        "scene_id": bundle["scene_id"],
        "query_target_id": bundle["query_target_id"],
        "visible_ids": [item["object_id"] for item in bundle["visible_points"]],
        "depth_available": bool(bundle.get("depth_path")),
        "mask_candidates": bundle.get("predicted_masks", []),
    }
```

- [ ] **Step 4: Re-run the GT-isolation tests**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_gt_isolation.py test_eghc_evidence_builder.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the GT-isolation scaffold**

```bash
git add build_sanitized_inference_bundle.py utils/gt_access_guard.py utils/deployable_evidence.py test_eghc_gt_isolation.py test_eghc_evidence_builder.py
git commit -m "feat: add eghc sanitized inference bundle scaffold"
```

### Task 3: Add EGHC Schemas And Deterministic Guard Router

**Files:**
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_schemas.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_router.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_router.py`

- [ ] **Step 1: Write the failing router tests**

```python
import unittest

from utils.eghc_router import select_route


class EGHCRouterTest(unittest.TestCase):
    def test_strong_direct_requires_free_visible_and_no_blockers(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "identity_score": 0.92}],
            "target_visibility": "free_visible",
            "blocking_relations": [],
            "recommended_route": "direct",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "direct")

    def test_unsupported_blocker_first_downgrades_to_target_first(self):
        packet = {"duplicate_mask_conflict": False}
        assessment = {
            "target_candidates": [{"object_id": 3, "identity_score": 0.81}],
            "target_visibility": "mostly_hidden",
            "blocking_relations": [],
            "recommended_route": "blocker_first",
        }
        decision = select_route(packet, assessment, challenger=None)
        self.assertEqual(decision["selected_route"], "target_first")
```

- [ ] **Step 2: Run the router tests and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_router.py -v
```

Expected: `FAIL`

- [ ] **Step 3: Write the minimal schema and router implementation**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    selected_route: str
    selection_source: str
    guard_reasons: list[str]
    requires_adjudication: bool


def select_route(packet, assessment, challenger=None):
    guard_reasons = []
    if assessment.get("recommended_route") == "direct":
        if assessment.get("target_visibility") != "free_visible":
            guard_reasons.append("target_not_free_visible")
        if assessment.get("blocking_relations"):
            guard_reasons.append("credible_blocking_evidence")
        if packet.get("duplicate_mask_conflict"):
            guard_reasons.append("duplicate_mask_conflict")
        if not guard_reasons:
            return {
                "selected_route": "direct",
                "selection_source": "guard",
                "guard_reasons": [],
                "requires_adjudication": False,
            }
    if assessment.get("recommended_route") == "blocker_first" and assessment.get("blocking_relations"):
        return {
            "selected_route": "blocker_first",
            "selection_source": "guard",
            "guard_reasons": [],
            "requires_adjudication": False,
        }
    return {
        "selected_route": "target_first",
        "selection_source": "guard",
        "guard_reasons": guard_reasons or ["target_first_default"],
        "requires_adjudication": bool(challenger),
    }
```

- [ ] **Step 4: Re-run the router tests**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_router.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the router scaffold**

```bash
git add utils/eghc_schemas.py utils/eghc_router.py test_eghc_router.py
git commit -m "feat: add eghc router scaffold"
```

### Task 4: Plumb EGHC Through Existing Entry Points

**Files:**
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_all.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_mimo_full_protocol.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/evaluate_common.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/reasoning_eval.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/utils.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_all_summary.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_mimo_full_protocol.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_evaluate_entrypoints.py`

- [ ] **Step 1: Write the failing entrypoint tests**

```python
def test_subset_config_maps_eghc_guard_only():
    config = evaluate_all._subset_config(
        "hard_yes_ambi",
        "legacy_old",
        "id_repair",
        "point_retry",
        "eghc_guard_only_v1",
    )
    assert config["routing_variant"] == "evidence_gated_cascade"
    assert config["feature_source"] == "deployable_predicted"
    assert config["segmentation_variant"] == "eghc_mask_repair_v1"


def test_evaluate_mimo_accepts_eghc_subset_policy():
    args = evaluate_mimo.parse_args(["--subset-policy", "eghc_guard_only_v1"])
    assert args.subset_policy == "eghc_guard_only_v1"
```

- [ ] **Step 2: Run the entrypoint tests and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_all_summary.py test_evaluate_mimo.py test_evaluate_mimo_full_protocol.py test_evaluate_entrypoints.py -v
```

Expected: `FAIL`

- [ ] **Step 3: Write the minimal entrypoint delegation**

```python
# evaluate_all.py
if subset_policy == "eghc_guard_only_v1":
    return {
        "prompt_variant": "legacy",
        "mimo_retry_mode": "none",
        "segmentation_variant": "eghc_mask_repair_v1",
        "routing_variant": "evidence_gated_cascade",
        "feature_source": "deployable_predicted",
        "uses_benchmark_difficulty": False,
        "uses_gt_features": False,
        "protocol_ablation": "full",
    }

# utils/utils.py
if routing_variant == "evidence_gated_cascade":
    from utils.eghc_router import run_eghc_prediction
    return run_eghc_prediction(
        image=image_pil,
        molmo_scene_path=scene_path,
        scene_id=scene_number,
        text=text,
        query_target_id=query_target_id,
        return_metadata=return_metadata,
    )
```

- [ ] **Step 4: Re-run the entrypoint tests**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_evaluate_all_summary.py test_evaluate_mimo.py test_evaluate_mimo_full_protocol.py test_evaluate_entrypoints.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the entrypoint plumbing**

```bash
git add evaluate_all.py evaluate_mimo.py evaluate_mimo_full_protocol.py evaluate_common.py reasoning_eval.py utils/utils.py test_evaluate_all_summary.py test_evaluate_mimo.py test_evaluate_mimo_full_protocol.py test_evaluate_entrypoints.py
git commit -m "feat: add eghc entrypoint plumbing"
```

### Task 5: Implement Adjudication, Segmentation Repair, And Sealed Artifacts

**Files:**
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_adjudicator.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_segmentation.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/utils/eghc_artifacts.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/score_sealed_predictions.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_adjudicator.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_segmentation.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_artifacts.py`

- [ ] **Step 1: Write the failing adjudication and sealing tests**

```python
import unittest

from utils.eghc_adjudicator import should_trigger_adjudication
from utils.eghc_artifacts import seal_prediction


class EGHCAdjudicationTest(unittest.TestCase):
    def test_invalid_call2_id_triggers_qwen(self):
        self.assertTrue(
            should_trigger_adjudication(
                assessment={"target_candidates": [{"object_id": 3}]},
                route_decision={"selected_route": "direct"},
                plan={"first_grasp_object_id": 99},
                visible_ids={3, 5, 7},
            )
        )

    def test_sealed_prediction_keeps_sample_identity(self):
        sealed = seal_prediction(
            sample_key={"scene_id": 12, "query_target_id": 3, "annotation": "red cup"},
            reasoning={"selected_object_id": 5},
            mask_path="mask.npy",
        )
        self.assertEqual(sealed["sample_key"]["scene_id"], 12)
        self.assertEqual(sealed["reasoning"]["selected_object_id"], 5)
```

- [ ] **Step 2: Run the adjudication/sealing tests and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_adjudicator.py test_eghc_segmentation.py test_eghc_artifacts.py -v
```

Expected: `FAIL`

- [ ] **Step 3: Write the minimal adjudication, segmentation, and sealing implementation**

```python
def should_trigger_adjudication(assessment, route_decision, plan, visible_ids):
    if plan.get("first_grasp_object_id") not in visible_ids:
        return True
    if route_decision.get("selected_route") == "direct" and assessment.get("blocking_relations"):
        return True
    if plan.get("confidence", 1.0) < 0.60:
        return True
    return False


def score_candidate_mask(candidate, point):
    contains_point = bool(candidate["contains_point"])
    duplicate_penalty = float(candidate.get("duplicate_penalty", 0.0))
    return (2.0 if contains_point else 0.0) + float(candidate["sam_score"]) - duplicate_penalty


def seal_prediction(sample_key, reasoning, mask_path):
    return {
        "sample_key": sample_key,
        "reasoning": reasoning,
        "mask_path": mask_path,
    }
```

- [ ] **Step 4: Re-run the adjudication/sealing tests**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_adjudicator.py test_eghc_segmentation.py test_eghc_artifacts.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the adjudication and sealing scaffold**

```bash
git add utils/eghc_adjudicator.py utils/eghc_segmentation.py utils/eghc_artifacts.py score_sealed_predictions.py test_eghc_adjudicator.py test_eghc_segmentation.py test_eghc_artifacts.py
git commit -m "feat: add eghc adjudication and sealing scaffold"
```

### Task 6: Build Offline Audit And Challenger Eligibility Logic

**Files:**
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_eghc_offline.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/train_eghc_challenger.py`
- Create: `/home/public/zb/FreeGrasp_code-freegrasp_codex/test_eghc_challenger.py`

- [ ] **Step 1: Write the failing challenger eligibility test**

```python
import unittest

from train_eghc_challenger import evaluate_training_eligibility


class EGHCChallengerTest(unittest.TestCase):
    def test_ineligible_without_clean_route_coverage(self):
        registry_rows = [
            {"provenance_class": "oracle_assisted", "route_executed": "direct"},
            {"provenance_class": "clean_no_gt", "route_executed": None},
        ]
        report = evaluate_training_eligibility(registry_rows)
        self.assertFalse(report["eligible"])
        self.assertEqual(report["selected_router"], "guard_only")
```

- [ ] **Step 2: Run the challenger test and confirm failure**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_challenger.py -v
```

Expected: `FAIL`

- [ ] **Step 3: Write the minimal offline audit and challenger implementation**

```python
def evaluate_training_eligibility(registry_rows):
    clean_rows = [row for row in registry_rows if row["provenance_class"] == "clean_no_gt"]
    covered_routes = {
        row["route_executed"]
        for row in clean_rows
        if row.get("route_executed") in {"direct", "target_first", "blocker_first"}
    }
    eligible = covered_routes == {"direct", "target_first", "blocker_first"}
    return {
        "eligible": eligible,
        "covered_routes": sorted(covered_routes),
        "selected_router": "hybrid_guard_plus_challenger" if eligible else "guard_only",
    }
```

- [ ] **Step 4: Re-run the challenger test**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest test_eghc_challenger.py -v
```

Expected: `PASS`

- [ ] **Step 5: Commit the offline audit scaffold**

```bash
git add audit_eghc_offline.py train_eghc_challenger.py test_eghc_challenger.py
git commit -m "feat: add eghc offline challenger scaffold"
```

### Task 7: Freeze Pre-Paid Outputs And Run The Local Verification Suite

**Files:**
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_historical_runs.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/audit_eghc_offline.py`
- Modify: `/home/public/zb/FreeGrasp_code-freegrasp_codex/train_eghc_challenger.py`
- No new tests required beyond the suite below

- [ ] **Step 1: Emit the frozen pre-paid artifact set**

Required output paths:

```text
data/output/eghc_v1/historical_run_registry.json
data/output/eghc_v1/clean_s0_manifest.json
data/output/eghc_v1/fixed_cache_manifest.json
data/output/eghc_v1/evidence_manifest.json
data/output/eghc_v1/offline_router_audit.json
data/output/eghc_v1/offline_segmentation_audit.json
data/output/eghc_v1/frozen_policy.json
docs/experiments/eghc_v1_historical_run_audit.md
```

- [ ] **Step 2: Run the focused EGHC test suite**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest \
  test_eghc_historical_audit.py \
  test_eghc_gt_isolation.py \
  test_eghc_evidence_builder.py \
  test_eghc_router.py \
  test_eghc_adjudicator.py \
  test_eghc_segmentation.py \
  test_eghc_artifacts.py \
  test_eghc_challenger.py -v
```

Expected: `PASS`

- [ ] **Step 3: Run the regression suite that protects current entrypoints**

Run:

```bash
source /home/wyl/miniconda3/etc/profile.d/conda.sh
conda activate freegrasp
cd /home/public/zb/FreeGrasp_code-freegrasp_codex
python -m unittest \
  test_evaluate_all_summary.py \
  test_evaluate_mimo.py \
  test_evaluate_mimo_full_protocol.py \
  test_evaluate_entrypoints.py \
  test_reasoning_resume.py \
  test_scene_evidence.py \
  test_unified_hard_safe_protocol.py -v
```

Expected: `PASS`

- [ ] **Step 4: Record the stop boundary instead of launching paid runs**

Write a short note in `docs/experiments/eghc_v1_historical_run_audit.md` that:

```text
All local pre-paid gates passed.
No paid reasoning experiment has been launched.
Separate user approval is required for:
- MiMo preflight
- Qwen preflight
- Phase B smoke
- Phase C split-0 pilot
```

- [ ] **Step 5: Commit the frozen pre-paid outputs and stop**

```bash
git add data/output/eghc_v1 docs/experiments/eghc_v1_historical_run_audit.md
git commit -m "docs: freeze eghc pre-paid artifacts"
```

## Spec Coverage Check

- Historical run reclassification: covered by Task 1.
- GT isolation and sanitized inference bundle: covered by Task 2.
- No-GT evidence builder: covered by Task 2.
- MiMo Call 1, deterministic guard, route state machine: covered by Task 3 and Task 4.
- Call 2 / Qwen adjudication / segmentation repair / sealed scoring: covered by Task 5.
- Scene-disjoint challenger eligibility and offline audit: covered by Task 6.
- Fixed-cache freeze boundary and no-paid stop condition: covered by Task 7.

## Paid Execution Handoff

This plan intentionally stops before any paid model call. Once Task 7 is complete, the next approved execution packet should contain only:

1. MiMo and Qwen image-input preflight commands.
2. Phase B hard/easy smoke commands.
3. Phase C split-0 matched commands.
4. The exact gates to stop on after each paid phase.
