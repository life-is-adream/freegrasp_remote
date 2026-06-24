# Target-Conditioned Evidence Handoff V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply the existing FreeGrasp v9/v10 expert prompts with deterministic, target-conditioned predicted geometry, reject duplicate point-SAM masks as blocker proof, and pass an offline blocker-recall gate before any paid inference.

**Architecture:** Point-prompted SAM geometry is normalized into one compact record per candidate pair, including mask IoU and cross-point containment computed in memory. After the automatic router proposes a target, a pure packet builder ranks at most three non-duplicate obstruction-risk candidates; the V2 guard and existing v9/v10 prompts consume that same packet. An offline audit recomputes geometry once per scene, measures candidate recall only after packet construction, and prevents pilot preparation when the approved gate fails.

**Tech Stack:** Python 3.13 project `.venv`, `unittest`, NumPy, pandas, Pillow, SAM predictor already loaded by FreeGrasp, JSON experiment artifacts, existing MiMo/FreeGrasp evaluation entry points.

---

## File Structure

- Modify `route_guard_config.py`: V2 thresholds and versioned provenance constants.
- Modify `utils/scene_evidence.py`: canonical geometry, duplicate-mask statistics, target packet construction/formatting, and V2 guard.
- Modify `utils/utils.py`: router formatting, packet lifecycle, v9/v10 prompt handoff, repair handoff, and metadata.
- Modify `experiment_manifest.py`: V2 manifest fields.
- Modify `evaluate_mimo.py`: accept the V2 guard at the single-run CLI.
- Modify `evaluate_mimo_full_protocol.py`: accept and summarize V2 provenance.
- Modify `test_scene_evidence.py`: pure geometry, packet, and guard tests.
- Modify `test_evidence_router_integration.py`: end-to-end prompt handoff tests with no real model calls.
- Modify `test_evidence_router_entrypoints.py`: CLI and forwarding tests.
- Modify `test_experiment_manifest.py`: immutable V2 provenance test.
- Modify `test_evaluate_mimo_full_protocol.py`: V2 summary fields.
- Create `audit_target_evidence_v2.py`: offline geometry cache, 25-sample recall audit, 900-row coverage audit, and gate report.
- Create `test_audit_target_evidence_v2.py`: audit isolation, recall, uniqueness, and gate tests.
- Create `prepare_target_evidence_pilot.py`: produce a frozen, approval-gated 25-sample pilot manifest only after the offline gate passes.
- Create `test_prepare_target_evidence_pilot.py`: reject failed gates and preserve sample identities.
- Create `run_target_evidence_pilot.py`: paid runner with immutable cache/manifest checks; do not execute during this plan.
- Create `test_run_target_evidence_pilot.py`: literal paid-confirmation and variant checks.
- Generate `docs/experiments/2026-06-24-target-evidence-v2-offline.md`: durable report generated from actual audit results.

### Task 1: Canonical Predicted Geometry and Duplicate Statistics

**Files:**
- Modify: `route_guard_config.py`
- Modify: `utils/scene_evidence.py:141-235`
- Modify: `test_scene_evidence.py:137-183`

- [ ] **Step 1: Write failing tests for one-record-per-pair geometry**

Add imports for `DUPLICATE_BBOX_OVERLAP_THRESHOLD` and
`DUPLICATE_MASK_IOU_THRESHOLD`, then replace the directed-pair assertion with:

```python
def test_pairwise_relations_are_canonical_and_order_independent(self):
    masks = {
        1: np.pad(np.ones((5, 5), dtype=bool), ((0, 5), (0, 5))),
        2: np.pad(np.ones((5, 5), dtype=bool), ((3, 2), (3, 2))),
    }
    parsed = [(1, 1, 1, 900), (2, 7, 7, 901)]

    first = build_predicted_geometry(parsed, masks)
    second = build_predicted_geometry(list(reversed(parsed)), masks)

    self.assertEqual(first["relations"], second["relations"])
    self.assertEqual(len(first["relations"]), 1)
    relation = first["relations"][0]
    self.assertEqual((relation["object_a_id"], relation["object_b_id"]), (1, 2))
    self.assertIn("bbox_overlap_smaller", relation)
    self.assertIn("mask_iou", relation)
    self.assertNotIn("vertical_order", relation)
```

Add duplicate and non-duplicate cases:

```python
def test_duplicate_mask_suspect_requires_mask_or_cross_point_evidence(self):
    same = np.zeros((12, 12), dtype=bool)
    same[2:10, 2:10] = True
    distinct = np.zeros((12, 12), dtype=bool)
    distinct[7:11, 7:11] = True

    duplicate = build_predicted_geometry(
        [(1, 4, 4, 900), (2, 8, 8, 901)],
        {1: same, 2: same.copy()},
    )["relations"][0]
    separate = build_predicted_geometry(
        [(1, 4, 4, 900), (2, 8, 8, 901)],
        {1: same, 2: distinct},
    )["relations"][0]

    self.assertTrue(duplicate["duplicate_mask_suspect"])
    self.assertGreaterEqual(duplicate["mask_iou"], DUPLICATE_MASK_IOU_THRESHOLD)
    self.assertFalse(separate["duplicate_mask_suspect"])
```

- [ ] **Step 2: Run the tests and verify the old directed representation fails**

Run:

```bash
.venv/bin/python -m unittest \
  test_scene_evidence.SceneEvidenceTest.test_pairwise_relations_are_canonical_and_order_independent \
  test_scene_evidence.SceneEvidenceTest.test_duplicate_mask_suspect_requires_mask_or_cross_point_evidence -v
```

Expected: FAIL because the current code emits two directed records and does
not compute `mask_iou` or `duplicate_mask_suspect`.

- [ ] **Step 3: Add versioned V2 constants**

Append to `route_guard_config.py`:

```python
TARGET_EVIDENCE_GUARD_VERSION = "target-evidence-v2"
TARGET_EVIDENCE_MAX_CANDIDATES = 3
DUPLICATE_MASK_IOU_THRESHOLD = 0.85
DUPLICATE_BBOX_OVERLAP_THRESHOLD = 0.95
```

Keep the existing conservative-v1 constants unchanged so historical manifests
remain interpretable.

- [ ] **Step 4: Implement compact canonical relation statistics**

In `utils/scene_evidence.py`, import the new constants and replace
`add_pairwise_relations` with helpers following this complete interface:

```python
def _mask_iou(first, second):
    first = np.asarray(first, dtype=bool)
    second = np.asarray(second, dtype=bool)
    union = np.logical_or(first, second).sum()
    return float(np.logical_and(first, second).sum()) / float(union) if union else 0.0


def _point_in_mask(mask, point):
    x, y = point
    mask = np.asarray(mask, dtype=bool)
    return 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and bool(mask[y, x])


def _relative_image_position(target_center, candidate_center):
    dx = candidate_center[0] - target_center[0]
    dy = candidate_center[1] - target_center[1]
    horizontal = "left" if dx < 0 else "right" if dx > 0 else "center"
    vertical = "upper" if dy < 0 else "lower" if dy > 0 else "level"
    return f"{vertical}_{horizontal}"


def add_pairwise_relations(evidence, masks_by_id):
    candidates = evidence.get("candidates", {})
    relations = []
    for object_a_id, object_b_id in combinations(sorted(candidates), 2):
        object_a = candidates[object_a_id]
        object_b = candidates[object_b_id]
        intersection = _bbox_intersection(object_a["bbox"], object_b["bbox"])
        area_a = max(1, _bbox_area(object_a["bbox"]))
        area_b = max(1, _bbox_area(object_b["bbox"]))
        overlap_smaller = float(intersection) / float(min(area_a, area_b))
        a_mask = np.asarray(masks_by_id[object_a_id], dtype=bool)
        b_mask = np.asarray(masks_by_id[object_b_id], dtype=bool)
        mask_iou = _mask_iou(a_mask, b_mask)
        a_contains_b_point = _point_in_mask(a_mask, object_b["point"])
        b_contains_a_point = _point_in_mask(b_mask, object_a["point"])
        duplicate = (
            mask_iou >= DUPLICATE_MASK_IOU_THRESHOLD
            or (
                overlap_smaller >= DUPLICATE_BBOX_OVERLAP_THRESHOLD
                and a_contains_b_point
                and b_contains_a_point
            )
        )
        relations.append(
            {
                "object_a_id": int(object_a_id),
                "object_b_id": int(object_b_id),
                "relation": "overlaps" if intersection else "separate",
                "bbox_overlap_smaller": overlap_smaller,
                "bbox_a_coverage": float(intersection) / float(area_a),
                "bbox_b_coverage": float(intersection) / float(area_b),
                "mask_iou": mask_iou,
                "a_contains_b_point": a_contains_b_point,
                "b_contains_a_point": b_contains_a_point,
                "a_image_position_from_b": _relative_image_position(
                    object_b["center"], object_a["center"]
                ),
                "b_image_position_from_a": _relative_image_position(
                    object_a["center"], object_b["center"]
                ),
                "duplicate_mask_suspect": duplicate,
            }
        )
    return {**evidence, "relations": relations}
```

Add `from itertools import combinations`. Change
`build_predicted_geometry(parsed_data, masks_by_id)` to return
`add_pairwise_relations(evidence, masks_by_id)` and change
`predict_geometry_from_molmo_points` to avoid a second relation pass:

```python
evidence = build_predicted_geometry(parsed_data, masks_by_id)
evidence["point_mask_selections"] = selections
return evidence
```

Do not serialize masks into `evidence`.

- [ ] **Step 5: Run scene-evidence tests**

Run:

```bash
.venv/bin/python -m unittest test_scene_evidence -v
```

Expected: PASS. Update any old test fixture that calls
`add_pairwise_relations(evidence)` so it supplies explicit masks.

- [ ] **Step 6: Commit canonical geometry**

```bash
git add route_guard_config.py utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: canonicalize predicted candidate geometry"
```

### Task 2: Target-Conditioned Evidence Packet

**Files:**
- Modify: `utils/scene_evidence.py`
- Modify: `test_scene_evidence.py`

- [ ] **Step 1: Write failing packet construction tests**

Add this helper to `SceneEvidenceTest`:

```python
@staticmethod
def _canonical_geometry(target_id=1, candidate_ids=(2,)):
    candidates = {
        target_id: {
            "point": (0, 0),
            "bbox": (0, 0, 2, 2),
            "center": (1, 1),
            "area": 9,
        }
    }
    relations = []
    for offset, candidate_id in enumerate(candidate_ids, start=1):
        candidates[candidate_id] = {
            "point": (4 * offset, 0),
            "bbox": (4 * offset, 0, 4 * offset + 2, 2),
            "center": (4 * offset + 1, 1),
            "area": 9,
        }
        relations.append(
            {
                "object_a_id": target_id,
                "object_b_id": candidate_id,
                "relation": "separate",
                "bbox_overlap_smaller": 0.0,
                "bbox_a_coverage": 0.0,
                "bbox_b_coverage": 0.0,
                "mask_iou": 0.0,
                "a_contains_b_point": False,
                "b_contains_a_point": False,
                "a_image_position_from_b": "level_left",
                "b_image_position_from_a": "level_right",
                "duplicate_mask_suspect": False,
            }
        )
    return {
        "source": "predicted_sam_point_masks",
        "candidates": candidates,
        "relations": relations,
    }
```

Add:

```python
def test_target_packet_ranks_non_duplicate_risk_candidates(self):
    geometry = {
        "source": "predicted_sam_point_masks",
        "candidates": {
            3: {"point": (5, 5), "bbox": (2, 2, 8, 8), "center": (5, 5), "area": 49},
            4: {"point": (6, 4), "bbox": (3, 1, 7, 6), "center": (5, 3), "area": 30},
            5: {"point": (9, 9), "bbox": (8, 8, 10, 10), "center": (9, 9), "area": 9},
        },
        "relations": [
            {
                "object_a_id": 3,
                "object_b_id": 4,
                "relation": "overlaps",
                "bbox_overlap_smaller": 0.8,
                "bbox_a_coverage": 0.4,
                "bbox_b_coverage": 0.8,
                "mask_iou": 0.2,
                "a_contains_b_point": True,
                "b_contains_a_point": True,
                "a_image_position_from_b": "lower_center",
                "b_image_position_from_a": "upper_center",
                "duplicate_mask_suspect": False,
            },
            {
                "object_a_id": 3,
                "object_b_id": 5,
                "relation": "overlaps",
                "bbox_overlap_smaller": 1.0,
                "bbox_a_coverage": 0.1,
                "bbox_b_coverage": 1.0,
                "mask_iou": 0.9,
                "a_contains_b_point": True,
                "b_contains_a_point": True,
                "a_image_position_from_b": "upper_left",
                "b_image_position_from_a": "lower_right",
                "duplicate_mask_suspect": True,
            },
        ],
    }

    packet = build_target_evidence_packet(
        target_id=3,
        visible_object_ids=[3, 4, 5],
        predicted_geometry=geometry,
        max_candidates=3,
    )

    self.assertEqual([row["candidate_id"] for row in packet["risk_candidates"]], [4])
    self.assertEqual(packet["duplicate_mask_candidates"], [5])
    self.assertEqual(packet["risk_candidates"][0]["candidate_image_position"], "upper_center")
    self.assertEqual(packet["evidence_reliability"], "usable")
```

Add deterministic fallback and GT rejection:

```python
def test_target_packet_uses_labeled_nearest_fallback_and_rejects_gt(self):
    geometry = {
        "candidates": {
            1: {"point": (0, 0), "bbox": (0, 0, 1, 1), "center": (0, 0), "area": 4},
            2: {"point": (4, 0), "bbox": (4, 0, 5, 1), "center": (4, 0), "area": 4},
        },
        "relations": [
            {
                "object_a_id": 1,
                "object_b_id": 2,
                "relation": "separate",
                "bbox_overlap_smaller": 0.0,
                "bbox_a_coverage": 0.0,
                "bbox_b_coverage": 0.0,
                "mask_iou": 0.0,
                "duplicate_mask_suspect": False,
                "a_image_position_from_b": "level_left",
                "b_image_position_from_a": "level_right",
            }
        ],
    }
    packet = build_target_evidence_packet(
        target_id=1,
        visible_object_ids=[1, 2],
        predicted_geometry=geometry,
    )
    self.assertEqual(packet["risk_candidates"][0]["included_by"], "nearest_fallback")

    with self.assertRaisesRegex(ValueError, "ground-truth"):
        build_target_evidence_packet(
            target_id=1,
            visible_object_ids=[1],
            predicted_geometry={"gt_id": 4},
        )
```

Add malformed relation validation:

```python
def test_target_packet_rejects_duplicate_pairs_and_nonfinite_values(self):
    geometry = self._canonical_geometry(target_id=1, candidate_ids=[2])
    duplicate = {
        **geometry,
        "relations": geometry["relations"] * 2,
    }
    with self.assertRaisesRegex(ValueError, "Duplicate canonical pair"):
        build_target_evidence_packet(
            target_id=1,
            visible_object_ids=[1, 2],
            predicted_geometry=duplicate,
        )

    geometry["relations"][0]["mask_iou"] = float("nan")
    with self.assertRaisesRegex(ValueError, "Non-finite"):
        build_target_evidence_packet(
            target_id=1,
            visible_object_ids=[1, 2],
            predicted_geometry=geometry,
        )
```

- [ ] **Step 2: Run tests and verify packet functions are missing**

Run:

```bash
.venv/bin/python -m unittest \
  test_scene_evidence.SceneEvidenceTest.test_target_packet_ranks_non_duplicate_risk_candidates \
  test_scene_evidence.SceneEvidenceTest.test_target_packet_uses_labeled_nearest_fallback_and_rejects_gt -v
```

Expected: FAIL with import/name errors for the packet builder.

- [ ] **Step 3: Implement packet orientation and ranking**

Add to `utils/scene_evidence.py`:

```python
def _candidate(geometry, object_id):
    candidates = geometry.get("candidates", {})
    return candidates.get(object_id) or candidates.get(str(object_id))


def _target_relation(relation, target_id):
    if relation.get("object_a_id") == target_id:
        return {
            "candidate_id": int(relation["object_b_id"]),
            "bbox_target_coverage": float(relation["bbox_a_coverage"]),
            "candidate_image_position": relation["b_image_position_from_a"],
        }
    if relation.get("object_b_id") == target_id:
        return {
            "candidate_id": int(relation["object_a_id"]),
            "bbox_target_coverage": float(relation["bbox_b_coverage"]),
            "candidate_image_position": relation["a_image_position_from_b"],
        }
    return None


def build_target_evidence_packet(
    *,
    target_id,
    visible_object_ids,
    predicted_geometry,
    max_candidates=TARGET_EVIDENCE_MAX_CANDIDATES,
):
    _reject_ground_truth_fields(predicted_geometry)
    visible = {int(value) for value in visible_object_ids}
    target = _candidate(predicted_geometry, target_id)
    if target_id not in visible or target is None:
        return {
            "target_id": target_id,
            "target_valid": False,
            "target_point": None,
            "target_bbox": None,
            "risk_candidates": [],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "invalid_target",
            "warnings": ["invalid_target_id"],
        }

    rows = []
    duplicates = []
    seen_pairs = set()
    for relation in predicted_geometry.get("relations", []):
        pair = tuple(sorted((
            int(relation["object_a_id"]),
            int(relation["object_b_id"]),
        )))
        if pair in seen_pairs:
            raise ValueError(f"Duplicate canonical pair: {pair}")
        seen_pairs.add(pair)
        for field in (
            "bbox_overlap_smaller",
            "bbox_a_coverage",
            "bbox_b_coverage",
            "mask_iou",
        ):
            if not np.isfinite(float(relation.get(field, 0.0))):
                raise ValueError(f"Non-finite geometry field: {field}")
        oriented = _target_relation(relation, int(target_id))
        if oriented is None or oriented["candidate_id"] not in visible:
            continue
        candidate = _candidate(predicted_geometry, oriented["candidate_id"])
        distance = float(
            np.hypot(
                candidate["center"][0] - target["center"][0],
                candidate["center"][1] - target["center"][1],
            )
        )
        target_diag = max(
            1.0,
            float(np.hypot(
                target["bbox"][2] - target["bbox"][0],
                target["bbox"][3] - target["bbox"][1],
            )),
        )
        row = {
            **oriented,
            "bbox_overlap_smaller": float(relation["bbox_overlap_smaller"]),
            "mask_iou": float(relation.get("mask_iou", 0.0)),
            "point_distance_normalized": distance / target_diag,
            "duplicate_mask_suspect": bool(
                relation.get("duplicate_mask_suspect", False)
            ),
        }
        if row["duplicate_mask_suspect"]:
            duplicates.append(row["candidate_id"])
            continue
        row["included_by"] = (
            "target_coverage"
            if row["bbox_target_coverage"] > 0
            else "nearest_fallback"
        )
        rows.append(row)

    overlapping = [row for row in rows if row["bbox_target_coverage"] > 0]
    pool = overlapping if overlapping else rows
    pool.sort(
        key=lambda row: (
            -row["bbox_target_coverage"],
            -row["bbox_overlap_smaller"],
            row["point_distance_normalized"],
            row["candidate_id"],
        )
    )
    selected = pool[: int(max_candidates)]
    reliability = (
        "usable"
        if selected
        else "duplicate_only"
        if duplicates
        else "no_risk_candidates"
    )
    return {
        "target_id": int(target_id),
        "target_valid": True,
        "target_point": list(target["point"]),
        "target_bbox": list(target["bbox"]),
        "risk_candidates": selected,
        "duplicate_mask_candidates": sorted(set(duplicates)),
        "evidence_reliability": reliability,
        "warnings": (
            ["duplicate_mask_uncertainty"] if duplicates else []
        ),
    }
```

This processes every target relation before applying the three-candidate cap.

- [ ] **Step 4: Implement the prompt formatter**

Add:

```python
def format_target_evidence_packet(packet):
    lines = [
        "Router target hypothesis:",
        f"- target_id={packet.get('target_id')}",
        f"- target_point={tuple(packet['target_point']) if packet.get('target_point') else None}",
        "- treat this as a hypothesis to verify against the RGB image",
        "",
        "Target-conditioned obstruction-risk candidates:",
    ]
    if not packet.get("risk_candidates"):
        lines.append("- none")
    for row in packet.get("risk_candidates", []):
        lines.append(
            f"- id={row['candidate_id']}, included_by={row['included_by']}, "
            f"target_coverage={row['bbox_target_coverage']:.3f}, "
            f"overlap={row['bbox_overlap_smaller']:.3f}, "
            f"image_position={row['candidate_image_position']}, "
            f"duplicate_mask={str(row['duplicate_mask_suspect']).lower()}"
        )
    if packet.get("warnings") or packet.get("duplicate_mask_candidates"):
        lines.extend(["", "Reliability warnings:"])
        for warning in packet.get("warnings", []):
            lines.append(f"- {warning}")
        if packet.get("duplicate_mask_candidates"):
            lines.append(
                "- duplicate-mask candidate IDs="
                + ",".join(str(value) for value in packet["duplicate_mask_candidates"])
            )
    return "\n".join(lines)
```

- [ ] **Step 5: Run packet and existing scene-evidence tests**

```bash
.venv/bin/python -m unittest test_scene_evidence -v
```

Expected: PASS.

- [ ] **Step 6: Commit the target packet**

```bash
git add utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: build target-conditioned evidence packets"
```

### Task 3: Conservative Route Guard V2

**Files:**
- Modify: `utils/scene_evidence.py`
- Modify: `test_scene_evidence.py`

- [ ] **Step 1: Write failing guard-v2 tests**

Add:

```python
def test_target_evidence_guard_downgrades_duplicate_and_risky_direct(self):
    duplicate = {
        "target_valid": True,
        "risk_candidates": [],
        "duplicate_mask_candidates": [4],
        "evidence_reliability": "duplicate_only",
    }
    risk = {
        "target_valid": True,
        "risk_candidates": [{"candidate_id": 4}],
        "duplicate_mask_candidates": [],
        "evidence_reliability": "usable",
    }
    for packet, reason in [
        (duplicate, "duplicate_mask_uncertainty"),
        (risk, "target_risk_present"),
    ]:
        guarded = apply_target_evidence_route_guard(
            self._assessment(),
            visible_object_ids=[3, 4],
            object_count=2,
            target_evidence_packet=packet,
        )
        self.assertEqual(guarded["route_mode"], "target_first")
        self.assertIn(reason, guarded["route_guard_reasons"])
```

Add blocker validation:

```python
def test_target_evidence_guard_requires_text_and_nonduplicate_candidate(self):
    supported = apply_target_evidence_route_guard(
        self._assessment(
            "blocker_first",
            blocker_evidence=["object 4 physically covers the target"],
        ),
        visible_object_ids=[3, 4],
        object_count=2,
        target_evidence_packet={
            "target_valid": True,
            "risk_candidates": [{"candidate_id": 4}],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "usable",
        },
    )
    unsupported = apply_target_evidence_route_guard(
        self._assessment("blocker_first", blocker_evidence=["near object 4"]),
        visible_object_ids=[3, 4],
        object_count=2,
        target_evidence_packet={
            "target_valid": True,
            "risk_candidates": [{"candidate_id": 4}],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "usable",
        },
    )
    self.assertEqual(supported["route_mode"], "blocker_first")
    self.assertEqual(unsupported["route_mode"], "target_first")
```

- [ ] **Step 2: Verify the new guard is absent**

```bash
.venv/bin/python -m unittest \
  test_scene_evidence.SceneEvidenceTest.test_target_evidence_guard_downgrades_duplicate_and_risky_direct \
  test_scene_evidence.SceneEvidenceTest.test_target_evidence_guard_requires_text_and_nonduplicate_candidate -v
```

Expected: FAIL with an import/name error.

- [ ] **Step 3: Implement the V2 guard without changing V1**

Add:

```python
def apply_target_evidence_route_guard(
    route_assessment,
    *,
    visible_object_ids,
    object_count,
    target_evidence_packet,
):
    _reject_ground_truth_fields(route_assessment)
    _reject_ground_truth_fields(target_evidence_packet)
    original_mode = route_assessment["route_mode"]
    guarded_mode = original_mode
    reasons = []
    target_id = route_assessment.get("target_object_id")
    target_is_valid = (
        target_id in {int(value) for value in visible_object_ids}
        and bool(target_evidence_packet.get("target_valid"))
    )
    risk_candidates = target_evidence_packet.get("risk_candidates", [])
    duplicate_candidates = target_evidence_packet.get(
        "duplicate_mask_candidates", []
    )

    if original_mode == "direct":
        if not target_is_valid:
            reasons.append("invalid_target_id")
        if float(route_assessment.get("route_confidence", 0.0)) < DIRECT_CONFIDENCE_THRESHOLD:
            reasons.append("low_confidence")
        if route_assessment.get("ambiguity_evidence"):
            reasons.append("ambiguity_present")
        if duplicate_candidates:
            reasons.append("duplicate_mask_uncertainty")
        if risk_candidates:
            reasons.append("target_risk_present")
        if _has_blocking_text(route_assessment.get("blocker_evidence", [])):
            reasons.append("router_blocking_evidence")
        if reasons:
            guarded_mode = "target_first"
    elif original_mode == "blocker_first":
        supported = (
            target_is_valid
            and bool(risk_candidates)
            and _has_blocking_text(route_assessment.get("blocker_evidence", []))
        )
        if not supported:
            reasons.append("unsupported_blocker_evidence")
            guarded_mode = "target_first"

    return {
        **route_assessment,
        "route_mode": guarded_mode,
        "pre_guard_route_mode": original_mode,
        "route_guard_applied": guarded_mode != original_mode,
        "route_guard_reasons": reasons,
        "route_guard_variant": "target_evidence_v2",
        "target_evidence_max_candidates": TARGET_EVIDENCE_MAX_CANDIDATES,
        "duplicate_mask_iou_threshold": DUPLICATE_MASK_IOU_THRESHOLD,
        "duplicate_bbox_overlap_threshold": DUPLICATE_BBOX_OVERLAP_THRESHOLD,
        "guard_code_version": TARGET_EVIDENCE_GUARD_VERSION,
    }
```

Do not use object count as a hard route boundary.

- [ ] **Step 4: Run all guard tests**

```bash
.venv/bin/python -m unittest test_scene_evidence -v
```

Expected: PASS for both V1 regression tests and V2 tests.

- [ ] **Step 5: Commit guard V2**

```bash
git add utils/scene_evidence.py test_scene_evidence.py
git commit -m "feat: add target evidence route guard"
```

### Task 4: Prompt and Repair Handoff

**Files:**
- Modify: `utils/utils.py:1-70, 1060-1267, 1380-1421, 1637-2029`
- Modify: `test_evidence_router_integration.py`
- Modify: `test_utils_output_limit.py`

- [ ] **Step 1: Extend the integration fixture with canonical geometry**

Change `_run_prediction` so its default geometry contains canonical relations.
Add this helper to `EvidenceRouterIntegrationTest`:

```python
@staticmethod
def _canonical_overlap_geometry():
    return {
        "source": "predicted_sam_point_masks",
        "candidates": {
            3: {
                "point": (0, 0),
                "bbox": (0, 0, 2, 2),
                "center": (1, 1),
                "area": 9,
            },
            4: {
                "point": (1, 1),
                "bbox": (1, 1, 3, 3),
                "center": (2, 2),
                "area": 9,
            },
        },
        "relations": [
            {
                "object_a_id": 3,
                "object_b_id": 4,
                "relation": "overlaps",
                "bbox_overlap_smaller": 4 / 9,
                "bbox_a_coverage": 4 / 9,
                "bbox_b_coverage": 4 / 9,
                "mask_iou": 0.2,
                "a_contains_b_point": True,
                "b_contains_a_point": True,
                "a_image_position_from_b": "upper_left",
                "b_image_position_from_a": "lower_right",
                "duplicate_mask_suspect": False,
            }
        ],
    }
```

Add a test that inspects both the main specialized call and repair call:

```python
def test_target_packet_reaches_main_and_repair_prompts(self):
    router_output = json.dumps(
        {
            "route_mode": "direct",
            "route_confidence": 0.95,
            "target_object_id": 3,
            "target_label": "red block",
            "ambiguity_evidence": [],
            "blocker_evidence": [],
        }
    )
    reasoning_output = json.dumps(
        {
            "target_resolution": {"target_object_id": 3},
            "first_grasp_planning": {
                "first_grasp_object_id": 3,
                "first_grasp_label": "red block",
                "mask_query": "red block",
            },
        }
    )
    result, calls = self._run_prediction(
        router_output,
        reasoning_output,
        route_guard_variant="target_evidence_v2",
        predicted_geometry=self._canonical_overlap_geometry(),
    )
    main_text = calls[1]["messages"][1]["content"][0]["text"]
    repair_text = calls[2]["messages"][1]["content"][0]["text"]
    self.assertIn("Router target hypothesis", main_text)
    self.assertIn("id=4, included_by=target_coverage", main_text)
    self.assertIn("Router target hypothesis", repair_text)
    self.assertNotIn("vertical_order", main_text)
    self.assertEqual(result["reasoning"]["target_evidence_packet"]["target_id"], 3)
```

Add a frozen-route test asserting the packet is rebuilt from predicted
geometry while `router_call_count == 0`.

- [ ] **Step 2: Run the new integration test and verify failure**

```bash
.venv/bin/python -m unittest \
  test_evidence_router_integration.EvidenceRouterIntegrationTest.test_target_packet_reaches_main_and_repair_prompts -v
```

Expected: FAIL because V2 is not a valid guard and prompts do not accept a
packet.

- [ ] **Step 3: Register V2 imports and validation**

In `utils/utils.py`, import:

```python
from utils.scene_evidence import (
    apply_conservative_route_guard,
    apply_target_evidence_route_guard,
    build_target_evidence_packet,
    evidence_router_prompt,
    format_router_input,
    format_target_evidence_packet,
    parse_route_assessment,
    predict_geometry_from_molmo_points,
)
```

Change:

```python
VALID_ROUTE_GUARD_VARIANTS = {"none", "conservative_v1", "target_evidence_v2"}
```

- [ ] **Step 4: Stop printing global relations in specialized prompts**

Add `include_pairwise_relations=True` to
`_format_visible_object_candidates`. Guard the current relation block with:

```python
if (
    include_geometry
    and include_pairwise_relations
    and geometry_features.get("relations")
):
```

Preserve historical oracle-feature formatting by supporting both schemas:

```python
def _format_geometry_relation(relation):
    if "object_a_id" in relation:
        return (
            f"- pair id={relation['object_a_id']}<->{relation['object_b_id']}, "
            f"type={relation.get('relation', 'separate')}, "
            f"bbox_overlap={_format_float(relation.get('bbox_overlap_smaller', 0.0))}, "
            f"mask_iou={_format_float(relation.get('mask_iou', 0.0))}, "
            f"duplicate_mask={str(bool(relation.get('duplicate_mask_suspect'))).lower()}"
        )
    return (
        f"- relation id={relation['source_id']}->{relation['target_id']}, "
        f"type={relation.get('relation', 'near')}, "
        f"overlap={_format_float(relation.get('overlap', 0.0))}, "
        f"vertical_order={relation.get('vertical_order', 'unknown')}"
    )
```

Use that helper in `_format_visible_object_candidates`.

Update `format_router_input` in `utils/scene_evidence.py` so predicted
canonical relations are overlap-sorted and explicitly described as 2D:

```python
relations = sorted(
    predicted_geometry.get("relations", []),
    key=lambda row: (
        -float(row.get("bbox_overlap_smaller", 0.0)),
        int(row.get("object_a_id", 0)),
        int(row.get("object_b_id", 0)),
    ),
)
lines.append("Predicted 2D candidate-pair geometry:")
for relation in relations[:24]:
    lines.append(
        f"- pair id={relation['object_a_id']}<->{relation['object_b_id']}, "
        f"bbox_overlap={relation['bbox_overlap_smaller']:.3f}, "
        f"mask_iou={relation.get('mask_iou', 0.0):.3f}, "
        f"duplicate_mask={str(bool(relation.get('duplicate_mask_suspect'))).lower()}"
    )
```

The router text must never emit `vertical_order`, `on_top`, or
physical-contact claims for predicted geometry.

- [ ] **Step 5: Add the packet parameter to main and repair builders**

Change the signatures:

```python
def _build_reasoning_input_text(
    input_text,
    parsed_data,
    prompt_variant,
    semantic_labels=None,
    geometry_features=None,
    target_evidence_packet=None,
):
```

For v9/v10 prompts call `_format_visible_object_candidates` with
`include_pairwise_relations=target_evidence_packet is None`. Before returning,
prepend:

```python
if (
    target_evidence_packet is not None
    and prompt_variant
    in {"target_first_evidence_gate_v9_json", "hard_blocker_first_v10_json"}
):
    candidate_text = (
        f"{format_target_evidence_packet(target_evidence_packet)}\n\n"
        f"{candidate_text}"
    )
```

Add `target_evidence_packet=None` to
`_build_geometry_consistency_repair_text` and
`_build_target_first_grasp_id_repair_text`. Format the packet before the
candidate table in both functions.

The geometry repair builder begins with:

```python
packet_text = (
    f"{format_target_evidence_packet(target_evidence_packet)}\n\n"
    if target_evidence_packet is not None
    else ""
)
```

Then replace its existing `f"{candidate_text}\n\n"` interpolation with
`f"{packet_text}{candidate_text}\n\n"`. Use the same `packet_text`
construction and interpolation replacement in the target-first ID repair
builder; leave the existing repair rules unchanged.

- [ ] **Step 6: Build the packet after target resolution and before guarding**

In `get_prediction_result`, initialize `target_evidence_packet = None`. After
the router/frozen assessment is available, add:

```python
if route_assessment is not None and geometry_features:
    target_evidence_packet = build_target_evidence_packet(
        target_id=route_assessment.get("target_object_id"),
        visible_object_ids=visible_object_ids,
        predicted_geometry=geometry_features,
    )
    reasoning["target_evidence_packet"] = target_evidence_packet
```

Replace the guard branch with:

```python
if frozen_route_assessment is None and route_guard_variant == "conservative_v1":
    route_assessment = apply_conservative_route_guard(
        route_assessment,
        visible_object_ids=visible_object_ids,
        object_count=len(parsed_data),
        predicted_geometry=geometry_features,
    )
elif frozen_route_assessment is None and route_guard_variant == "target_evidence_v2":
    route_assessment = apply_target_evidence_route_guard(
        route_assessment,
        visible_object_ids=visible_object_ids,
        object_count=len(parsed_data),
        target_evidence_packet=target_evidence_packet or {
            "target_valid": False,
            "risk_candidates": [],
            "duplicate_mask_candidates": [],
            "evidence_reliability": "missing_predicted_geometry",
        },
    )
```

Pass `target_evidence_packet` to the main reasoning builder, geometry repair,
and target-first ID repair. Frozen routes skip the router and guard exactly as
before, but still rebuild and inject the packet.

- [ ] **Step 7: Tighten v9/v10 reminder wording**

Replace statements that imply bbox overlap proves blocking with:

```text
- Target-conditioned candidates are obstruction-risk hypotheses, not verified blockers.
- Select a blocker only when the RGB image visibly supports coverage, contact, or blocked access.
- Duplicate-mask warnings and 2D image position cannot prove physical obstruction.
```

Keep the JSON schemas and parser unchanged.

- [ ] **Step 8: Run integration and output-limit tests**

```bash
.venv/bin/python -m unittest \
  test_evidence_router_integration \
  test_utils_output_limit -v
```

Expected: PASS with zero real network calls.

- [ ] **Step 9: Commit prompt handoff**

```bash
git add utils/utils.py test_evidence_router_integration.py test_utils_output_limit.py
git commit -m "feat: hand target evidence to v10 expert prompts"
```

### Task 5: CLI and Provenance Contracts

**Files:**
- Modify: `experiment_manifest.py:11-29`
- Modify: `evaluate_mimo.py:262-276`
- Modify: `evaluate_mimo_full_protocol.py:42-52, 115-151`
- Modify: `test_experiment_manifest.py`
- Modify: `test_evidence_router_entrypoints.py`
- Modify: `test_evaluate_mimo_full_protocol.py`

- [ ] **Step 1: Write failing V2 provenance tests**

Add:

```python
def test_target_evidence_provenance_is_stable(self):
    self.assertEqual(
        guard_provenance("target_evidence_v2"),
        {
            "route_guard_variant": "target_evidence_v2",
            "target_evidence_max_candidates": 3,
            "duplicate_mask_iou_threshold": 0.85,
            "duplicate_bbox_overlap_threshold": 0.95,
            "guard_code_version": "target-evidence-v2",
        },
    )
```

Extend CLI tests to parse `--route-guard-variant target_evidence_v2` in both
MiMo entry points. Extend the full-protocol summary fixture with the five V2
fields and assert they survive aggregation.

- [ ] **Step 2: Verify CLI/provenance tests fail**

```bash
.venv/bin/python -m unittest \
  test_experiment_manifest \
  test_evidence_router_entrypoints \
  test_evaluate_mimo_full_protocol -v
```

Expected: FAIL because choices and provenance only recognize V1.

- [ ] **Step 3: Extend `guard_provenance`**

Implement:

```python
def guard_provenance(route_guard_variant):
    if route_guard_variant == "none":
        return {"route_guard_variant": "none"}
    if route_guard_variant == "conservative_v1":
        from route_guard_config import (
            CONSERVATIVE_GUARD_VERSION,
            DIRECT_CONFIDENCE_THRESHOLD,
            DIRECT_MAX_OBJECT_COUNT,
            TARGET_OVERLAP_THRESHOLD,
        )
        return {
            "route_guard_variant": route_guard_variant,
            "direct_confidence_threshold": DIRECT_CONFIDENCE_THRESHOLD,
            "direct_max_object_count": DIRECT_MAX_OBJECT_COUNT,
            "target_overlap_threshold": TARGET_OVERLAP_THRESHOLD,
            "guard_code_version": CONSERVATIVE_GUARD_VERSION,
        }
    if route_guard_variant == "target_evidence_v2":
        from route_guard_config import (
            DUPLICATE_BBOX_OVERLAP_THRESHOLD,
            DUPLICATE_MASK_IOU_THRESHOLD,
            TARGET_EVIDENCE_GUARD_VERSION,
            TARGET_EVIDENCE_MAX_CANDIDATES,
        )
        return {
            "route_guard_variant": route_guard_variant,
            "target_evidence_max_candidates": TARGET_EVIDENCE_MAX_CANDIDATES,
            "duplicate_mask_iou_threshold": DUPLICATE_MASK_IOU_THRESHOLD,
            "duplicate_bbox_overlap_threshold": DUPLICATE_BBOX_OVERLAP_THRESHOLD,
            "guard_code_version": TARGET_EVIDENCE_GUARD_VERSION,
        }
    raise ValueError(f"Unknown route guard: {route_guard_variant}")
```

- [ ] **Step 4: Register the V2 CLI choice and summary keys**

Change both parser choices to:

```python
choices=["none", "conservative_v1", "target_evidence_v2"]
```

Add these keys to `aggregate_run_results` manifest propagation:

```python
"target_evidence_max_candidates",
"duplicate_mask_iou_threshold",
"duplicate_bbox_overlap_threshold",
```

No subset policy changes are needed; V2 remains an automatic,
difficulty-free route guard.

- [ ] **Step 5: Run provenance and entry-point tests**

```bash
.venv/bin/python -m unittest \
  test_experiment_manifest \
  test_evidence_router_entrypoints \
  test_evaluate_mimo_full_protocol \
  test_evaluate_mimo -v
```

Expected: PASS.

- [ ] **Step 6: Commit provenance support**

```bash
git add \
  experiment_manifest.py \
  evaluate_mimo.py \
  evaluate_mimo_full_protocol.py \
  test_experiment_manifest.py \
  test_evidence_router_entrypoints.py \
  test_evaluate_mimo_full_protocol.py
git commit -m "feat: record target evidence provenance"
```

### Task 6: Offline Evidence Audit and Hard Stop

**Files:**
- Create: `audit_target_evidence_v2.py`
- Create: `test_audit_target_evidence_v2.py`
- Generate: `docs/experiments/2026-06-24-target-evidence-v2-offline.md`

- [ ] **Step 1: Write audit tests before the script**

Create these test helpers:

```python
def canonical_geometry(target_id, candidate_ids):
    return SceneEvidenceTest._canonical_geometry(
        target_id=target_id,
        candidate_ids=tuple(candidate_ids),
    )


def make_rows(*, n, target_correct, top3_recall, hard_n, hard_recall):
    rows = []
    for index in range(n):
        is_hard = index < hard_n
        rows.append(
            {
                "sample_key": [
                    "0",
                    "hard_no_ambi" if is_hard else "medium_no_ambi",
                    index,
                    index,
                    1,
                    "sample",
                ],
                "subset": "hard_no_ambi" if is_hard else "medium_no_ambi",
                "evaluation_only": {
                    "target_correct": index < target_correct,
                    "top3_recall": (
                        index < hard_recall
                        if is_hard
                        else index < top3_recall
                    ),
                },
            }
        )
    current = sum(row["evaluation_only"]["top3_recall"] for row in rows)
    for row in rows[hard_n:]:
        if current >= top3_recall:
            break
        row["evaluation_only"]["top3_recall"] = True
        current += 1
    return rows
```

Import `SceneEvidenceTest` from `test_scene_evidence` only in the test module;
production audit code must not import tests.

Create tests for three pure functions:

```python
def test_audit_builds_packet_before_using_evaluation_mapping(self):
    sample = {
        "split": "0",
        "subset": "hard_no_ambi",
        "source_row_index": 0,
        "scene_id": 7,
        "object_id": 2,
        "annotation": "the box",
        "frozen_route_assessment": {"target_object_id": 3},
    }
    detail = {"gt_ids": [5], "rsr_correct": 0, "ssr_correct": 0}
    geometry = canonical_geometry(target_id=3, candidate_ids=[4])
    row = audit.audit_pilot_sample(
        sample,
        detail,
        geometry,
        molmo_to_gt={3: 2, 4: 5},
    )
    self.assertTrue(row["evaluation_only"]["target_correct"])
    self.assertTrue(row["evaluation_only"]["top3_recall"])
    self.assertNotIn("gt_ids", json.dumps(row["packet"]))
```

```python
def test_gate_requires_exact_counts_and_hard_recall(self):
    rows = make_rows(n=25, target_correct=24, top3_recall=17, hard_n=8, hard_recall=4)
    self.assertTrue(audit.evaluate_gate(rows)["passed"])
    first_recalled = next(
        row for row in rows if row["evaluation_only"]["top3_recall"]
    )
    first_recalled["evaluation_only"]["top3_recall"] = False
    self.assertFalse(audit.evaluate_gate(rows)["passed"])
```

```python
def test_geometry_cache_runs_once_per_scene(self):
    calls = []
    cache = audit.build_geometry_cache(
        scene_ids=[7, 7, 8],
        geometry_provider=lambda scene_id: calls.append(scene_id) or {"scene": scene_id},
    )
    self.assertEqual(calls, [7, 8])
    self.assertEqual(set(cache), {7, 8})
```

- [ ] **Step 2: Run tests and verify the audit module is absent**

```bash
.venv/bin/python -m unittest test_audit_target_evidence_v2 -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement pure audit and gate functions**

Create `audit_target_evidence_v2.py` with:

```python
def audit_pilot_sample(sample, detail, geometry, molmo_to_gt):
    target_id = int(sample["frozen_route_assessment"]["target_object_id"])
    packet = build_target_evidence_packet(
        target_id=target_id,
        visible_object_ids=sorted(int(value) for value in molmo_to_gt),
        predicted_geometry=geometry,
    )
    acceptable = {int(value) for value in detail["gt_ids"]}
    candidate_gt_ids = [
        molmo_to_gt.get(int(row["candidate_id"]))
        for row in packet["risk_candidates"]
    ]
    return {
        "sample_key": [
            str(sample["split"]),
            sample["subset"],
            int(sample["source_row_index"]),
            int(sample["scene_id"]),
            int(sample["object_id"]),
            sample["annotation"],
        ],
        "split": str(sample["split"]),
        "subset": sample["subset"],
        "scene_id": int(sample["scene_id"]),
        "packet": packet,
        "evaluation_only": {
            "target_correct": molmo_to_gt.get(target_id) == int(sample["object_id"]),
            "top1_recall": bool(candidate_gt_ids and candidate_gt_ids[0] in acceptable),
            "top3_recall": any(value in acceptable for value in candidate_gt_ids),
            "acceptable_gt_ids": sorted(acceptable),
            "candidate_gt_ids": candidate_gt_ids,
        },
    }


def evaluate_gate(rows):
    keys = [tuple(row["sample_key"]) for row in rows]
    hard = [row for row in rows if row["subset"].startswith("hard_")]
    counts = {
        "n": len(rows),
        "unique": len(set(keys)),
        "target_correct": sum(
            row["evaluation_only"]["target_correct"] for row in rows
        ),
        "top3_recall": sum(
            row["evaluation_only"]["top3_recall"] for row in rows
        ),
        "hard_n": len(hard),
        "hard_top3_recall": sum(
            row["evaluation_only"]["top3_recall"] for row in hard
        ),
    }
    checks = {
        "exact_25_unique": counts["n"] == 25 and counts["unique"] == 25,
        "target_24_of_25": counts["target_correct"] >= 24,
        "top3_17_of_25": counts["top3_recall"] >= 17,
        "hard_4_of_8": counts["hard_n"] == 8 and counts["hard_top3_recall"] >= 4,
    }
    return {"passed": all(checks.values()), "counts": counts, "checks": checks}
```

Add `build_geometry_cache` that sorts unique scene IDs and calls an injected
provider once per scene.

- [ ] **Step 4: Implement the real offline geometry provider**

The CLI must lazily import project-heavy modules only inside execution:

```python
from evaluate_common import MOLMO_OUTPUT_DIR, load_dataset
from utils.utils import langsam_actor
```

For each needed scene:

1. Read the original RGB bytes from the dataframe and construct a PIL image.
2. Read only `Molmo_ID`, `X`, and `Y` from
   `data/output/molmo_output/scene<ID>/<ID>_id.txt` into packet input.
3. Read the fourth column into a separate `molmo_to_gt` evaluation mapping
   that is never passed to `predict_geometry_from_molmo_points` or the packet
   builder.
4. Call `predict_geometry_from_molmo_points` once per unique scene.
5. Write compact geometry JSON to
   `<output-dir>/geometry_cache/scene<ID>.json`; never write masks.

Reject non-finite values before writing JSON.

- [ ] **Step 5: Implement pilot and full-run reports**

CLI:

```text
audit_target_evidence_v2.py
  --pilot-manifest data/output/overlap_blocker_pilot_v1_artifacts/pilot_manifest.json
  --pilot-source-run data/output/conservative_router_pilot_v1_20260624
  --full-source-run data/output/ablation_matrix/S4
  --molmo-root data/output/molmo_output
  --output-dir data/output/target_evidence_v2_offline_20260624
  --report docs/experiments/2026-06-24-target-evidence-v2-offline.md
```

Write:

- `pilot_rows.json`
- `pilot_summary.json`
- `full_coverage.json`
- `gate.json`
- the Markdown report containing the exact command, cache hash, thresholds,
  overall/hard recall, duplicate frequency, fallback frequency, gate checks,
  interpretation, and next action.

The full 900-row audit uses each S4 row's recorded target ID and reports packet
availability and V1-to-V2 route transitions. It must not calculate hypothetical
RSR or SSR.

- [ ] **Step 6: Run unit tests for the audit**

```bash
.venv/bin/python -m unittest test_audit_target_evidence_v2 -v
```

Expected: PASS without initializing SAM or making network calls.

- [ ] **Step 7: Run the real offline audit**

```bash
CUDA_VISIBLE_DEVICES=0 .venv/bin/python audit_target_evidence_v2.py \
  --pilot-manifest data/output/overlap_blocker_pilot_v1_artifacts/pilot_manifest.json \
  --pilot-source-run data/output/conservative_router_pilot_v1_20260624 \
  --full-source-run data/output/ablation_matrix/S4 \
  --molmo-root data/output/molmo_output \
  --output-dir data/output/target_evidence_v2_offline_20260624 \
  --report docs/experiments/2026-06-24-target-evidence-v2-offline.md
```

Expected:

- 25 unique pilot rows;
- 900 unique full rows;
- zero HTTP POST calls;
- `gate.json` contains an explicit boolean `passed`.

- [ ] **Step 8: Apply the hard decision gate**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
gate = json.loads(
    Path("data/output/target_evidence_v2_offline_20260624/gate.json").read_text()
)
print(json.dumps(gate, indent=2))
raise SystemExit(0 if gate["passed"] else 2)
PY
```

Expected:

- exit `0`: continue to Task 7;
- exit `2`: stop implementation, commit the offline report, and start a new
  depth-aware occlusion design. Do not create or run a paid pilot.

- [ ] **Step 9: Commit the audit and actual report**

```bash
git add \
  audit_target_evidence_v2.py \
  test_audit_target_evidence_v2.py \
  docs/experiments/2026-06-24-target-evidence-v2-offline.md
git commit -m "feat: audit target evidence recall offline"
```

### Task 7: Prepare, but Do Not Run, the Paid Pilot

**Condition:** Perform this task only when
`data/output/target_evidence_v2_offline_20260624/gate.json` has
`"passed": true`.

**Files:**
- Create: `prepare_target_evidence_pilot.py`
- Create: `test_prepare_target_evidence_pilot.py`
- Create: `run_target_evidence_pilot.py`
- Create: `test_run_target_evidence_pilot.py`

- [ ] **Step 1: Write failing manifest-preparation tests**

Add:

```python
def sample(index):
    return {
        "split": str(index % 3),
        "subset": "medium_no_ambi" if index < 17 else "hard_no_ambi",
        "source_row_index": index,
        "scene_id": 1000 + index,
        "object_id": 1,
        "annotation": f"sample {index}",
        "frozen_route_assessment": {
            "route_mode": "blocker_first",
            "route_confidence": 0.95,
            "target_object_id": 2,
            "target_label": "box",
            "ambiguity_evidence": [],
            "blocker_evidence": [],
        },
        "baseline_target_first": {"rsr_correct": 0, "ssr_correct": 0},
    }
```

```python
def test_prepare_refuses_failed_gate(self):
    with self.assertRaisesRegex(RuntimeError, "offline gate failed"):
        prepare.build_manifest(
            gate={"passed": False},
            pilot={"samples": []},
            cache_sha256="cache",
        )


def test_prepare_preserves_all_25_sample_identities(self):
    samples = [sample(index) for index in range(25)]
    manifest = prepare.build_manifest(
        gate={"passed": True, "counts": {"n": 25}},
        pilot={"samples": samples},
        cache_sha256="cache",
    )
    self.assertEqual(len(manifest["samples"]), 25)
    self.assertEqual(manifest["variant"], "target_evidence_v2")
    self.assertEqual(manifest["route_guard_variant"], "target_evidence_v2")
```

- [ ] **Step 2: Write failing paid-confirmation test**

```python
def test_runner_requires_literal_paid_confirmation(self):
    args = SimpleNamespace(confirm_paid_inference="yes")
    with self.assertRaisesRegex(ValueError, "RUN_PAID_INFERENCE"):
        runner.validate_paid_confirmation(args)
```

- [ ] **Step 3: Run tests and verify modules are absent**

```bash
.venv/bin/python -m unittest \
  test_prepare_target_evidence_pilot \
  test_run_target_evidence_pilot -v
```

Expected: FAIL with module import errors.

- [ ] **Step 4: Implement immutable pilot preparation**

`prepare_target_evidence_pilot.py` must:

- load `gate.json` and refuse `passed=false`;
- load the existing 25-sample pilot manifest;
- preserve split, subset, row index, scene, object, annotation, target ID, and
  matched target-first baseline outcomes;
- replace the earlier experimental `blocker_first` frozen assessment with the
  V2 final `target_first` assessment shown below;
- record cache SHA-256
  `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed`;
- set `variant`, `route_guard_variant`, and `evidence_formatter_version` to
  `target_evidence_v2`;
- write with exclusive creation and refuse overwrite.

For each sample, construct:

```python
source = sample["frozen_route_assessment"]
frozen_route_assessment = {
    "route_mode": "target_first",
    "route_confidence": float(source.get("route_confidence", 0.0)),
    "target_object_id": int(source["target_object_id"]),
    "target_label": source.get("target_label", sample["annotation"]),
    "ambiguity_evidence": list(source.get("ambiguity_evidence", [])),
    "blocker_evidence": list(source.get("blocker_evidence", [])),
    "pre_guard_route_mode": "direct",
    "route_guard_applied": True,
    "route_guard_reasons": ["target_risk_present"],
    "route_guard_variant": "target_evidence_v2",
}
```

This keeps the target and sample identities fixed while testing whether the
new packet improves the existing target-first expert decision. It does not
reuse the previous pilot's forced blocker-first route.

- [ ] **Step 5: Implement the guarded runner**

Adapt the structure of `run_overlap_blocker_pilot.py`, but:

- require `--confirm-paid-inference RUN_PAID_INFERENCE`;
- verify the current Molmo cache hash before creating the MiMo client;
- use `mimo-v2.5`, 1024 tokens, predicted geometry, and the existing v9/v10
  expert prompts;
- pass frozen final route assessments so the router is not called;
- set `route_guard_variant="target_evidence_v2"` so provenance and packet
  formatting are recorded;
- use `resume=True` and reject manifest mismatch;
- summarize RSR/SSR, router/reasoning/repair calls, paired wins/losses, and
  medium/hard results;
- never retry a completed sample automatically.

Do not execute the runner in this task.

- [ ] **Step 6: Run preparation/runner unit tests**

```bash
.venv/bin/python -m unittest \
  test_prepare_target_evidence_pilot \
  test_run_target_evidence_pilot -v
```

Expected: PASS without a model or network call.

- [ ] **Step 7: Generate the frozen pilot manifest**

```bash
.venv/bin/python prepare_target_evidence_pilot.py \
  --gate data/output/target_evidence_v2_offline_20260624/gate.json \
  --source-pilot data/output/overlap_blocker_pilot_v1_artifacts/pilot_manifest.json \
  --output data/output/target_evidence_v2_pilot_artifacts/pilot_manifest.json
```

Expected: a 25-sample manifest and no paid inference.

- [ ] **Step 8: Commit pilot tooling**

```bash
git add \
  prepare_target_evidence_pilot.py \
  test_prepare_target_evidence_pilot.py \
  run_target_evidence_pilot.py \
  test_run_target_evidence_pilot.py
git commit -m "feat: prepare target evidence pilot"
```

### Task 8: Final Verification and Approval Stop

**Files:**
- Verify all changed files.
- Do not modify `/home/public/zb/FreeGrasp_code-main`.

- [ ] **Step 1: Run focused tests**

```bash
.venv/bin/python -m unittest \
  test_scene_evidence \
  test_evidence_router_integration \
  test_evidence_router_entrypoints \
  test_experiment_manifest \
  test_evaluate_mimo_full_protocol \
  test_audit_target_evidence_v2 \
  test_prepare_target_evidence_pilot \
  test_run_target_evidence_pilot -v
```

Expected: PASS.

- [ ] **Step 2: Run the complete repository test suite**

```bash
.venv/bin/python -m unittest discover -p 'test_*.py' -v
```

Expected: all tests PASS. Record the exact test count in the final report.

- [ ] **Step 3: Verify no paid process or HTTP POST was launched**

```bash
pgrep -af 'run_target_evidence_pilot|evaluate_mimo_full_protocol|chat/completions' || true
```

Expected: no active paid-inference process.

- [ ] **Step 4: Verify artifacts and provenance**

```bash
.venv/bin/python summarize_ablation_matrix.py validate \
  data/output/ablation_matrix/S4 --expected-n 900
.venv/bin/python experiment_manifest.py hash-cache data/output/molmo_output
git diff --check
git status --short
```

Expected:

- S4: 900 unique rows;
- cache: 291 scene pairs and SHA-256
  `705d0883bbab9ff1db87eb55ba6815fd2cc5d202524082f97286d316572e26ed`;
- no whitespace errors;
- unrelated pre-existing worktree changes remain untouched.

- [ ] **Step 5: Stop for explicit paid-inference approval**

Report:

- offline overall and hard top-3 recall;
- whether the gate passed;
- duplicate/fallback frequencies;
- tests run and exact count;
- pilot manifest path if created;
- statement that no paid inference ran.

Do not invoke `run_target_evidence_pilot.py`. The next command requires the
user to explicitly authorize paid inference again.
