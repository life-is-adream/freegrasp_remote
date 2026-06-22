from dataclasses import asdict, dataclass
import json
import re

import numpy as np


VALID_ROUTE_MODES = {"direct", "target_first", "blocker_first"}


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


def build_predicted_geometry(parsed_data, masks_by_id):
    candidates = {}
    for object_id, x, y, _ignored_gt_id in parsed_data:
        mask = np.asarray(masks_by_id[object_id], dtype=bool)
        ys, xs = np.where(mask)
        if not xs.size:
            continue
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
        }

    return {
        "source": "predicted_sam_point_masks",
        "candidates": candidates,
        "relations": [],
    }


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


def add_pairwise_relations(evidence):
    candidates = evidence.get("candidates", {})
    relations = []
    for source_id, source in candidates.items():
        for target_id, target in candidates.items():
            if source_id == target_id:
                continue
            source_bbox = source["bbox"]
            target_bbox = target["bbox"]
            intersection = _bbox_intersection(source_bbox, target_bbox)
            smaller_area = max(
                1,
                min(_bbox_area(source_bbox), _bbox_area(target_bbox)),
            )
            overlap = float(intersection) / float(smaller_area)
            source_y = source["center"][1]
            target_y = target["center"][1]
            vertical_order = "above" if source_y < target_y else "below"
            relations.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": "overlaps" if intersection else "near",
                    "overlap": overlap,
                    "vertical_order": vertical_order,
                }
            )

    return {
        **evidence,
        "relations": relations,
    }


def predict_geometry_from_molmo_points(image, parsed_data, predictor):
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

    evidence = build_predicted_geometry(parsed_data, masks_by_id)
    evidence["point_mask_selections"] = selections
    return add_pairwise_relations(evidence)


def evidence_router_prompt():
    return (
        "You route one bin-picking observation to a first-grasp reasoning mode. "
        "Use the RGB image, instruction, visible Molmo IDs, and any predicted "
        "geometry supplied by the user. Object count is only a clutter prior. "
        "Choose direct when a credible target is visible and unblocked; "
        "target_first when target identity or geometry is uncertain; and "
        "blocker_first only when the target is missing or direct physical "
        "coverage/contact/overlap evidence exists. The relation near alone cannot "
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
        for relation in predicted_geometry.get("relations", []):
            lines.append(
                f"- relation id={relation['source_id']}->{relation['target_id']}, "
                f"type={relation['relation']}, overlap={relation['overlap']:.3f}, "
                f"vertical_order={relation['vertical_order']}"
            )
    return "\n".join(lines)
