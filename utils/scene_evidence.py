from dataclasses import asdict, dataclass
from itertools import combinations
import json
import re

import numpy as np

from route_guard_config import (
    CONSERVATIVE_GUARD_VERSION,
    DEPTH_CONTACT_DILATION,
    DEPTH_FRONT_MARGIN,
    DEPTH_MIN_VALID_PIXELS,
    DEPTH_OCCLUSION_VERSION,
    DIRECT_CONFIDENCE_THRESHOLD,
    DIRECT_MAX_OBJECT_COUNT,
    DUPLICATE_BBOX_OVERLAP_THRESHOLD,
    DUPLICATE_MASK_IOU_THRESHOLD,
    TARGET_EVIDENCE_GUARD_VERSION,
    TARGET_EVIDENCE_MAX_CANDIDATES,
    TARGET_OVERLAP_THRESHOLD,
)

VALID_ROUTE_MODES = {"direct", "target_first", "blocker_first"}
BLOCKING_TERMS = (
    "contact",
    "coverage",
    "covered",
    "covers",
    "blocks",
    "on-top",
    "on top",
    "overlap",
)


@dataclass(frozen=True)
class PointMaskSelection:
    index: int
    score: float
    contains_point: bool
    area_ratio: float


@dataclass(frozen=True)
class ConsistentMaskSelection:
    index: int
    total_score: float
    contains_point: bool
    confidence: float
    area_ratio: float
    point_distance: float
    fallback_reason: str | None


def _valid_depth_values(depth_map, mask):
    if depth_map is None:
        return np.asarray([], dtype=float)
    depth = np.asarray(depth_map)
    mask = np.asarray(mask, dtype=bool)
    if depth.shape != mask.shape:
        raise ValueError(
            f"Depth shape {depth.shape} does not match mask shape {mask.shape}"
        )
    values = depth[mask]
    return values[np.isfinite(values) & (values > 0)].astype(float)


def _depth_stats(depth_map, mask):
    values = _valid_depth_values(depth_map, mask)
    if values.size < DEPTH_MIN_VALID_PIXELS:
        return {
            "depth_valid_pixels": int(values.size),
            "depth_median": None,
            "depth_p25": None,
            "depth_p75": None,
        }
    return {
        "depth_valid_pixels": int(values.size),
        "depth_median": float(np.median(values)),
        "depth_p25": float(np.percentile(values, 25)),
        "depth_p75": float(np.percentile(values, 75)),
    }


def _dilate_mask(mask, radius=DEPTH_CONTACT_DILATION):
    mask = np.asarray(mask, dtype=bool)
    if radius <= 0:
        return mask.copy()
    padded = np.pad(mask, radius, mode="constant", constant_values=False)
    dilated = np.zeros_like(mask, dtype=bool)
    size = 2 * radius + 1
    for dy in range(size):
        for dx in range(size):
            dilated |= padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return dilated


def _contact_pixels(first, second):
    first = np.asarray(first, dtype=bool)
    second = np.asarray(second, dtype=bool)
    if first.shape != second.shape:
        raise ValueError(
            f"Mask shapes do not match: {first.shape} != {second.shape}"
        )
    overlap = np.logical_and(first, second)
    contact = np.logical_and(_dilate_mask(first), second) | np.logical_and(
        _dilate_mask(second),
        first,
    )
    return int(np.logical_or(overlap, contact).sum())


def _depth_front_relation(object_a, object_b):
    a_depth = object_a.get("depth_median")
    b_depth = object_b.get("depth_median")
    if a_depth is None or b_depth is None:
        return {
            "depth_order": "unknown",
            "depth_median_delta_b_minus_a": None,
            "depth_front_object_id": None,
        }
    delta = float(b_depth) - float(a_depth)
    if abs(delta) < DEPTH_FRONT_MARGIN:
        return {
            "depth_order": "similar",
            "depth_median_delta_b_minus_a": delta,
            "depth_front_object_id": None,
        }
    if delta > 0:
        return {
            "depth_order": "a_in_front",
            "depth_median_delta_b_minus_a": delta,
            "depth_front_object_id": None,
        }
    return {
        "depth_order": "b_in_front",
        "depth_median_delta_b_minus_a": delta,
        "depth_front_object_id": None,
    }


def _depth_order_from_delta(delta):
    if delta is None:
        return "unknown"
    delta = float(delta)
    if abs(delta) < DEPTH_FRONT_MARGIN:
        return "similar"
    return "a_in_front" if delta > 0 else "b_in_front"


def _contains(mask, point):
    x, y = point
    return (
        0 <= y < mask.shape[0]
        and 0 <= x < mask.shape[1]
        and bool(mask[y, x])
    )


def _distance_to_mask(mask, point):
    x, y = point
    indices = np.column_stack(np.where(mask))
    if not indices.size:
        return float("inf")
    distances = np.linalg.norm(indices - np.asarray([y, x]), axis=1)
    return float(distances.min())


def select_point_mask(masks, scores, point, area_weight=0.25):
    ranked = []
    for index, mask in enumerate(masks):
        mask = np.asarray(mask, dtype=bool)
        area_ratio = float(mask.mean()) if mask.size else 1.0
        contains_point = _contains(mask, point)
        score = (
            (2.0 if contains_point else 0.0)
            + float(scores[index])
            - area_weight * area_ratio
        )
        ranked.append(
            PointMaskSelection(
                index=index,
                score=score,
                contains_point=contains_point,
                area_ratio=area_ratio,
            )
        )

    if not ranked:
        raise ValueError("SAM returned no point-mask candidates")
    return max(ranked, key=lambda item: item.score)


def select_consistent_mask(
    masks,
    confidences,
    point,
    confidence_weight=0.25,
    area_weight=0.15,
):
    candidates = []
    for index, mask in enumerate(masks):
        mask = np.asarray(mask, dtype=bool)
        contains_point = _contains(mask, point)
        area_ratio = float(mask.mean()) if mask.size else 1.0
        confidence = float(confidences[index])
        point_distance = _distance_to_mask(mask, point)
        total_score = (
            (2.0 if contains_point else 0.0)
            + confidence_weight * confidence
            - area_weight * area_ratio
        )
        candidates.append(
            ConsistentMaskSelection(
                index=index,
                total_score=total_score,
                contains_point=contains_point,
                confidence=confidence,
                area_ratio=area_ratio,
                point_distance=point_distance,
                fallback_reason=None,
            )
        )

    if not candidates:
        raise ValueError("No segmentation masks to score")

    containing = [item for item in candidates if item.contains_point]
    if containing:
        return max(containing, key=lambda item: item.total_score)

    nearest = min(
        candidates,
        key=lambda item: (
            item.point_distance,
            -item.confidence,
            item.area_ratio,
        ),
    )
    return ConsistentMaskSelection(
        **{
            **asdict(nearest),
            "fallback_reason": "no_candidate_contains_point",
        }
    )


def build_predicted_geometry(parsed_data, masks_by_id, depth_map=None):
    candidates = {}
    for object_id, x, y, _ignored_gt_id in parsed_data:
        mask = np.asarray(masks_by_id[object_id], dtype=bool)
        ys, xs = np.where(mask)
        if not xs.size:
            continue
        depth_stats = _depth_stats(depth_map, mask)
        candidates[object_id] = {
            "point": (int(x), int(y)),
            "bbox": (
                int(xs.min()),
                int(ys.min()),
                int(xs.max()),
                int(ys.max()),
            ),
            "area": int(mask.sum()),
            "center": (int(round(xs.mean())), int(round(ys.mean()))),
            **depth_stats,
        }

    evidence = {
        "source": (
            "predicted_sam_point_masks_depth"
            if depth_map is not None
            else "predicted_sam_point_masks"
        ),
        "depth_source": "depth_map" if depth_map is not None else "none",
        "depth_occlusion_version": DEPTH_OCCLUSION_VERSION,
        "candidates": candidates,
        "relations": [],
    }
    return add_pairwise_relations(evidence, masks_by_id, depth_map=depth_map)


def _bbox_area(bbox):
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1 + 1) * max(0, y2 - y1 + 1)


def _bbox_intersection(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    if x2 < x1 or y2 < y1:
        return 0
    return (x2 - x1 + 1) * (y2 - y1 + 1)


def _mask_iou(first, second):
    first = np.asarray(first, dtype=bool)
    second = np.asarray(second, dtype=bool)
    union = np.logical_or(first, second).sum()
    if not union:
        return 0.0
    return float(np.logical_and(first, second).sum()) / float(union)


def _point_in_mask(mask, point):
    x, y = point
    mask = np.asarray(mask, dtype=bool)
    return (
        0 <= y < mask.shape[0]
        and 0 <= x < mask.shape[1]
        and bool(mask[y, x])
    )


def _relative_image_position(target_center, candidate_center):
    dx = candidate_center[0] - target_center[0]
    dy = candidate_center[1] - target_center[1]
    horizontal = "left" if dx < 0 else "right" if dx > 0 else "center"
    vertical = "upper" if dy < 0 else "lower" if dy > 0 else "level"
    return f"{vertical}_{horizontal}"


def add_pairwise_relations(evidence, masks_by_id, depth_map=None):
    candidates = evidence.get("candidates", {})
    relations = []
    for object_a_id, object_b_id in combinations(sorted(candidates), 2):
        object_a = candidates[object_a_id]
        object_b = candidates[object_b_id]
        intersection = _bbox_intersection(
            object_a["bbox"],
            object_b["bbox"],
        )
        area_a = max(1, _bbox_area(object_a["bbox"]))
        area_b = max(1, _bbox_area(object_b["bbox"]))
        overlap_smaller = float(intersection) / float(min(area_a, area_b))
        a_mask = np.asarray(masks_by_id[object_a_id], dtype=bool)
        b_mask = np.asarray(masks_by_id[object_b_id], dtype=bool)
        mask_iou = _mask_iou(a_mask, b_mask)
        contact_pixels = _contact_pixels(a_mask, b_mask)
        a_contains_b_point = _point_in_mask(a_mask, object_b["point"])
        b_contains_a_point = _point_in_mask(b_mask, object_a["point"])
        depth_relation = _depth_front_relation(object_a, object_b)
        if depth_relation["depth_front_object_id"] is None:
            if depth_relation["depth_order"] == "a_in_front":
                depth_relation["depth_front_object_id"] = int(object_a_id)
            elif depth_relation["depth_order"] == "b_in_front":
                depth_relation["depth_front_object_id"] = int(object_b_id)
        depth_occlusion = (
            depth_relation["depth_order"] in {"a_in_front", "b_in_front"}
            and contact_pixels > 0
        )
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
                "contact_pixels": contact_pixels,
                "a_contains_b_point": a_contains_b_point,
                "b_contains_a_point": b_contains_a_point,
                **depth_relation,
                "depth_occlusion_suspect": depth_occlusion,
                "a_image_position_from_b": _relative_image_position(
                    object_b["center"],
                    object_a["center"],
                ),
                "b_image_position_from_a": _relative_image_position(
                    object_a["center"],
                    object_b["center"],
                ),
                "duplicate_mask_suspect": duplicate,
            }
        )

    return {
        **evidence,
        "relations": relations,
    }


def predict_geometry_from_molmo_points(
    image,
    parsed_data,
    predictor,
    depth_map=None,
):
    predictor.set_image(np.asarray(image))
    masks_by_id = {}
    selections = {}
    for object_id, x, y, _ignored_gt_id in parsed_data:
        masks, scores, _logits = predictor.predict(
            point_coords=np.asarray([[x, y]], dtype=np.float32),
            point_labels=np.asarray([1], dtype=np.int32),
            multimask_output=True,
        )
        selected = select_point_mask(masks, scores, (x, y))
        masks_by_id[object_id] = np.asarray(
            masks[selected.index],
            dtype=bool,
        )
        selections[object_id] = asdict(selected)

    evidence = build_predicted_geometry(
        parsed_data,
        masks_by_id,
        depth_map=depth_map,
    )
    evidence["point_mask_selections"] = selections
    return evidence


def _candidate(predicted_geometry, object_id):
    candidates = predicted_geometry.get("candidates", {})
    return candidates.get(object_id) or candidates.get(str(object_id))


def _target_relation(relation, target_id):
    depth_order = _depth_order_from_delta(
        relation.get("depth_median_delta_b_minus_a")
    )
    if int(relation.get("object_a_id")) == target_id:
        return {
            "candidate_id": int(relation["object_b_id"]),
            "bbox_target_coverage": float(relation["bbox_a_coverage"]),
            "candidate_image_position": relation["b_image_position_from_a"],
            "candidate_depth_order": (
                "candidate_in_front"
                if depth_order == "b_in_front"
                else "target_in_front"
                if depth_order == "a_in_front"
                else depth_order
            ),
        }
    if int(relation.get("object_b_id")) == target_id:
        return {
            "candidate_id": int(relation["object_a_id"]),
            "bbox_target_coverage": float(relation["bbox_b_coverage"]),
            "candidate_image_position": relation["a_image_position_from_b"],
            "candidate_depth_order": (
                "candidate_in_front"
                if depth_order == "a_in_front"
                else "target_in_front"
                if depth_order == "b_in_front"
                else depth_order
            ),
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
    try:
        normalized_target_id = int(target_id)
    except (TypeError, ValueError):
        normalized_target_id = target_id
    target = _candidate(predicted_geometry, normalized_target_id)
    if normalized_target_id not in visible or target is None:
        return {
            "target_id": normalized_target_id,
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
        pair = tuple(
            sorted(
                (
                    int(relation["object_a_id"]),
                    int(relation["object_b_id"]),
                )
            )
        )
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
        depth_delta = relation.get("depth_median_delta_b_minus_a")
        if depth_delta is not None and not np.isfinite(float(depth_delta)):
            raise ValueError("Non-finite geometry field: depth_median_delta_b_minus_a")

        oriented = _target_relation(relation, normalized_target_id)
        if oriented is None or oriented["candidate_id"] not in visible:
            continue
        candidate = _candidate(
            predicted_geometry,
            oriented["candidate_id"],
        )
        if candidate is None:
            continue
        distance = float(
            np.hypot(
                candidate["center"][0] - target["center"][0],
                candidate["center"][1] - target["center"][1],
            )
        )
        target_diag = max(
            1.0,
            float(
                np.hypot(
                    target["bbox"][2] - target["bbox"][0],
                    target["bbox"][3] - target["bbox"][1],
                )
            ),
        )
        row = {
            **oriented,
            "bbox_overlap_smaller": float(
                relation["bbox_overlap_smaller"]
            ),
            "mask_iou": float(relation.get("mask_iou", 0.0)),
            "contact_pixels": int(relation.get("contact_pixels", 0)),
            "candidate_depth_order": oriented["candidate_depth_order"],
            "depth_median_delta_b_minus_a": (
                None
                if relation.get("depth_median_delta_b_minus_a") is None
                else float(relation["depth_median_delta_b_minus_a"])
            ),
            "depth_occlusion_suspect": bool(
                oriented["candidate_depth_order"] == "candidate_in_front"
                and int(relation.get("contact_pixels", 0)) > 0
            ),
            "point_distance_normalized": distance / target_diag,
            "duplicate_mask_suspect": bool(
                relation.get("duplicate_mask_suspect", False)
            ),
        }
        if row["duplicate_mask_suspect"]:
            duplicates.append(row["candidate_id"])
            continue
        if row["depth_occlusion_suspect"]:
            row["included_by"] = "depth_occlusion"
        elif row["bbox_target_coverage"] > 0:
            row["included_by"] = "target_coverage"
        else:
            row["included_by"] = "nearest_fallback"
        rows.append(row)

    overlapping = [
        row for row in rows if row["bbox_target_coverage"] > 0
    ]
    depth_blockers = [
        row for row in rows if row.get("depth_occlusion_suspect")
    ]
    pool = rows if depth_blockers else overlapping if overlapping else rows
    pool.sort(
        key=lambda row: (
            not bool(row.get("depth_occlusion_suspect")),
            -row["bbox_target_coverage"],
            -row["bbox_overlap_smaller"],
            -row["contact_pixels"],
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
        "target_id": normalized_target_id,
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


def format_target_evidence_packet(packet):
    lines = [
        "Router target hypothesis:",
        f"- target_id={packet.get('target_id')}",
        (
            "- target_point="
            f"{tuple(packet['target_point']) if packet.get('target_point') else None}"
        ),
        "- treat this as a hypothesis to verify against the RGB image",
        "",
        "Target-conditioned obstruction-risk candidates:",
    ]
    if not packet.get("risk_candidates"):
        lines.append("- none")
    for row in packet.get("risk_candidates", []):
        lines.append(
            f"- id={row['candidate_id']}, "
            f"included_by={row['included_by']}, "
            f"target_coverage={row['bbox_target_coverage']:.3f}, "
            f"overlap={row['bbox_overlap_smaller']:.3f}, "
            f"depth_order={row.get('candidate_depth_order', 'unknown')}, "
            "depth_occlusion="
            f"{str(bool(row.get('depth_occlusion_suspect'))).lower()}, "
            f"image_position={row['candidate_image_position']}, "
            "duplicate_mask="
            f"{str(row['duplicate_mask_suspect']).lower()}"
        )
    if packet.get("warnings") or packet.get("duplicate_mask_candidates"):
        lines.extend(["", "Reliability warnings:"])
        for warning in packet.get("warnings", []):
            lines.append(f"- {warning}")
        if packet.get("duplicate_mask_candidates"):
            lines.append(
                "- duplicate-mask candidate IDs="
                + ",".join(
                    str(value)
                    for value in packet["duplicate_mask_candidates"]
                )
            )
    return "\n".join(lines)


def evidence_router_prompt():
    return (
        "You route one bin-picking observation to a first-grasp reasoning mode. "
        "Use the RGB image, instruction, visible Molmo IDs, and any predicted "
        "geometry supplied by the user. Object count is only a clutter prior. "
        "Choose direct when a credible target is visible and unblocked; "
        "target_first when target identity or geometry is uncertain; and "
        "blocker_first only when the target is missing or direct physical "
        "coverage/contact/overlap evidence exists. When depth evidence is "
        "present, prefer blockers that are closer to the camera than the target "
        "at contact or overlap boundaries. The relation near alone cannot "
        "prove blocking. Return JSON only with this schema: "
        '{"route_mode":"direct|target_first|blocker_first",'
        '"route_confidence":0.0,'
        '"target_object_id":1,'
        '"target_label":"object",'
        '"ambiguity_evidence":[],'
        '"blocker_evidence":[]}'
    )


def parse_route_assessment(output, visible_object_ids):
    match = re.search(r"\{.*\}", str(output), flags=re.DOTALL)
    if not match:
        raise ValueError("Router output does not contain JSON")
    data = json.loads(match.group(0))
    mode = data["route_mode"]
    if mode not in VALID_ROUTE_MODES:
        raise ValueError(f"Unknown route mode: {mode}")

    target_id = data.get("target_object_id")
    if target_id is not None:
        target_id = int(target_id)
        if target_id not in visible_object_ids:
            target_id = None

    return {
        "route_mode": mode,
        "route_confidence": float(data.get("route_confidence", 0.0)),
        "target_object_id": target_id,
        "target_label": str(data.get("target_label", "target")),
        "ambiguity_evidence": list(data.get("ambiguity_evidence", [])),
        "blocker_evidence": list(data.get("blocker_evidence", [])),
    }


def _reject_ground_truth_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if (
                normalized.startswith("gt_")
                or "ground_truth" in normalized
                or "benchmark" in normalized
            ):
                raise ValueError(
                    f"Conservative route guard received ground-truth field: {key}"
                )
            _reject_ground_truth_fields(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_ground_truth_fields(item)


def _has_blocking_text(items):
    text = " ".join(str(item).lower() for item in items)
    return any(term in text for term in BLOCKING_TERMS)


def _target_has_predicted_overlap(predicted_geometry, target_id):
    for relation in predicted_geometry.get("relations", []):
        if target_id not in {
            relation.get("source_id"),
            relation.get("target_id"),
        }:
            continue
        if (
            relation.get("relation") == "overlaps"
            and float(relation.get("overlap", 0.0)) > TARGET_OVERLAP_THRESHOLD
        ):
            return True
    return False


def apply_conservative_route_guard(
    route_assessment,
    *,
    visible_object_ids,
    object_count,
    predicted_geometry,
):
    _reject_ground_truth_fields(route_assessment)
    _reject_ground_truth_fields(predicted_geometry)

    original_mode = route_assessment["route_mode"]
    guarded_mode = original_mode
    reasons = []
    target_id = route_assessment.get("target_object_id")
    target_is_valid = target_id in set(visible_object_ids)

    if original_mode == "direct":
        if not target_is_valid:
            reasons.append("invalid_target_id")
        if float(route_assessment.get("route_confidence", 0.0)) < DIRECT_CONFIDENCE_THRESHOLD:
            reasons.append("low_confidence")
        if route_assessment.get("ambiguity_evidence"):
            reasons.append("ambiguity_present")
        if (
            DIRECT_MAX_OBJECT_COUNT is not None
            and int(object_count) > DIRECT_MAX_OBJECT_COUNT
        ):
            reasons.append("clutter_prior")
        if _has_blocking_text(route_assessment.get("blocker_evidence", [])):
            reasons.append("router_blocking_evidence")
        if target_is_valid and _target_has_predicted_overlap(
            predicted_geometry,
            target_id,
        ):
            reasons.append("predicted_target_overlap")
        if reasons:
            guarded_mode = "target_first"
    elif original_mode == "blocker_first":
        supported = (
            target_is_valid
            and bool(route_assessment.get("blocker_evidence"))
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
        "route_guard_variant": "conservative_v1",
        "direct_confidence_threshold": DIRECT_CONFIDENCE_THRESHOLD,
        "direct_max_object_count": DIRECT_MAX_OBJECT_COUNT,
        "target_overlap_threshold": TARGET_OVERLAP_THRESHOLD,
        "guard_code_version": CONSERVATIVE_GUARD_VERSION,
    }


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
        "duplicate_mask_candidates",
        [],
    )

    if original_mode == "direct":
        if not target_is_valid:
            reasons.append("invalid_target_id")
        if (
            float(route_assessment.get("route_confidence", 0.0))
            < DIRECT_CONFIDENCE_THRESHOLD
        ):
            reasons.append("low_confidence")
        if route_assessment.get("ambiguity_evidence"):
            reasons.append("ambiguity_present")
        if duplicate_candidates:
            reasons.append("duplicate_mask_uncertainty")
        if risk_candidates:
            reasons.append("target_risk_present")
        if _has_blocking_text(
            route_assessment.get("blocker_evidence", [])
        ):
            reasons.append("router_blocking_evidence")
        if reasons:
            guarded_mode = "target_first"
    elif original_mode == "blocker_first":
        supported = (
            target_is_valid
            and bool(risk_candidates)
            and _has_blocking_text(
                route_assessment.get("blocker_evidence", [])
            )
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
        "duplicate_bbox_overlap_threshold": (
            DUPLICATE_BBOX_OVERLAP_THRESHOLD
        ),
        "guard_code_version": TARGET_EVIDENCE_GUARD_VERSION,
    }


def format_router_input(instruction, parsed_data, predicted_geometry=None):
    lines = [
        f"Instruction: {instruction}",
        f"visible_object_count={len(parsed_data)}",
        "Visible Molmo candidates:",
    ]
    for object_id, x, y, _ignored_gt_id in parsed_data:
        lines.append(f"- id={object_id}, point=({x},{y})")

    if predicted_geometry:
        lines.append(
            f"Predicted geometry source={predicted_geometry.get('source', 'unknown')}:"
        )
        for object_id, item in predicted_geometry.get("candidates", {}).items():
            lines.append(
                f"- id={object_id}, bbox={tuple(item['bbox'])}, "
                f"area={int(item['area'])}"
            )
        canonical_relations = [
            relation
            for relation in predicted_geometry.get("relations", [])
            if "object_a_id" in relation
        ]
        if canonical_relations:
            lines.append("Predicted 2D candidate-pair geometry:")
            canonical_relations.sort(
                key=lambda row: (
                    -float(row.get("bbox_overlap_smaller", 0.0)),
                    int(row.get("object_a_id", 0)),
                    int(row.get("object_b_id", 0)),
                )
            )
            for relation in canonical_relations[:24]:
                lines.append(
                    f"- pair id={relation['object_a_id']}<->"
                    f"{relation['object_b_id']}, "
                    "bbox_overlap="
                    f"{relation['bbox_overlap_smaller']:.3f}, "
                    f"mask_iou={relation.get('mask_iou', 0.0):.3f}, "
                    f"depth_order={relation.get('depth_order', 'unknown')}, "
                    "depth_occlusion="
                    f"{str(bool(relation.get('depth_occlusion_suspect'))).lower()}, "
                    "duplicate_mask="
                    f"{str(bool(relation.get('duplicate_mask_suspect'))).lower()}"
                )
        else:
            for relation in predicted_geometry.get("relations", []):
                lines.append(
                    f"- relation id={relation['source_id']}->"
                    f"{relation['target_id']}, "
                    f"type={relation['relation']}, "
                    f"overlap={relation['overlap']:.3f}, "
                    f"vertical_order={relation['vertical_order']}"
                )
    return "\n".join(lines)
