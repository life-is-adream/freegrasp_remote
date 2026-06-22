from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PointMaskSelection:
    index: int
    score: float
    contains_point: bool
    area_ratio: float


def _contains(mask, point):
    x, y = point
    return (
        0 <= y < mask.shape[0]
        and 0 <= x < mask.shape[1]
        and bool(mask[y, x])
    )


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
