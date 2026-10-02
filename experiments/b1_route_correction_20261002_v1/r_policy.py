"""R selector: constrained route correction on the frozen B1 baseline.

Implements design v1.1 (FreeGrasp_B1_选择性路由纠错_实验设计与执行交接_20261002),
section 3. Self-contained: no import from the b1_v6_repair package.

Deployable evidence only. No GT, no difficulty, no subset, no scene identity,
no historical scores enter this module.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any

VERSION = "b1-route-correction-r-v1"
DIRECT_CONFIDENCE = 0.75  # fixed B1 threshold; no split0 score tuning

BLOCKED_VISIBILITIES = ("visible_but_blocked", "mostly_hidden")

# Relation-strength semantics mirror the frozen repo's eghc_router
# STRONG_RELATION_TERMS: only occlusion-supporting types count.
STRONG_TERMS = ("cover", "occlud", "overlap", "contact", "on top", "on-top")

# Direction vocabulary for subject/object style relations. The subject is the
# blocker only when the relation text says the subject is the occluding /
# on-top party; reversed forms flip it; anything else is unknown (design 3.2:
# never guess endpoints).
SUBJECT_IS_BLOCKER_TERMS = (
    "cover", "occlud", "overlap", "on top", "on-top", "resting on",
    "above", "over", "positioned on", "sitting on", "on-top-of",
)
SUBJECT_IS_TARGET_TERMS = (
    "under", "below", "beneath", "covered by", "blocked by", "underneath",
)


def numeric_id(value: Any) -> int | None:
    """Legal visible integer ID or None. Booleans and floats are not IDs."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def coerce_confidence(value: Any) -> float | None:
    """Finite confidence in [0,1] or None (unknown). NaN/out-of-range -> None.

    Design 3.3: missing/NaN/out-of-bounds confidence is unknown, never
    interpreted as low or zero.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    if not (0.0 <= number <= 1.0):
        return None
    return number


def relation_text(relation: Any) -> str:
    if isinstance(relation, Mapping):
        return " ".join(
            str(relation.get(key, "")) for key in
            ("relation", "type", "evidence", "description", "relation_type")
        ).lower()
    return str(relation).lower()


def relation_strength(relation: Any) -> int:
    """B1 strong-evidence semantics: endpoint presence + strong term + conf."""
    if not isinstance(relation, Mapping):
        text = str(relation).lower()
        return int(any(term in text for term in STRONG_TERMS))
    score = 0
    for key in ("blocker_id", "object_id", "subject_id", "blocking_object_id",
                "source_id", "blocked_by"):
        if numeric_id(relation.get(key)) is not None:
            score += 1
            break
    if any(term in relation_text(relation) for term in STRONG_TERMS):
        score += 1
    try:
        confidence = float(relation.get("confidence", relation.get("score", 0.0)))
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None and confidence >= DIRECT_CONFIDENCE:
        score += 1
    return score


def normalize_relation(relation: Any) -> dict[str, Any]:
    """Normalize one relation to blocker_id -> target_id or mark unknown.

    Schema families actually observed in the 300 split0 router outputs
    (enumerated 2026-10-02, see phase0 reachability output):
      blocker_id+target_id; object_id+blocked_id;
      blocking_object_id+blocked_object_id; subject_id+object_id (semantic
      direction check); object_id+target_id; source_id+target_id;
      blocked_by+object_id; blocker_ids(list)+target_id; name-only and
      evidence-only forms (unknown endpoints, kept for evidence counts).
    """
    if not isinstance(relation, Mapping):
        return {"relation": relation, "blocker_id": None, "target_id": None,
                "status": "unknown", "schema": "non_dict"}

    raw = dict(relation)

    def pair(blocker, target, schema, status="explicit"):
        return {"relation": raw, "blocker_id": blocker, "target_id": target,
                "status": status, "schema": schema}

    blocker = numeric_id(raw.get("blocker_id"))
    target = numeric_id(raw.get("target_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "blocker_id+target_id")

    blocker = numeric_id(raw.get("blocking_object_id"))
    target = numeric_id(raw.get("blocked_object_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "blocking_object_id+blocked_object_id")

    blocker = numeric_id(raw.get("object_id"))
    target = numeric_id(raw.get("blocked_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "object_id+blocked_id")

    subject = numeric_id(raw.get("subject_id"))
    obj = numeric_id(raw.get("object_id"))
    if subject is not None and obj is not None:
        text = relation_text(raw)
        if any(term in text for term in SUBJECT_IS_BLOCKER_TERMS):
            return pair(subject, obj, "subject_id+object_id", "semantic")
        if any(term in text for term in SUBJECT_IS_TARGET_TERMS):
            return pair(obj, subject, "subject_id+object_id_reversed", "semantic")
        return {"relation": raw, "blocker_id": None, "target_id": None,
                "status": "unknown", "schema": "subject_id+object_id_direction_unclear"}

    blocker = numeric_id(raw.get("object_id"))
    target = numeric_id(raw.get("target_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "object_id+target_id")

    blocker = numeric_id(raw.get("source_id"))
    target = numeric_id(raw.get("target_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "source_id+target_id")

    blocker = numeric_id(raw.get("blocked_by"))
    target = numeric_id(raw.get("object_id"))
    if blocker is not None and target is not None:
        return pair(blocker, target, "blocked_by+object_id")

    blockers_raw = raw.get("blocker_ids")
    target = numeric_id(raw.get("target_id"))
    if isinstance(blockers_raw, list) and target is not None and blockers_raw:
        legal = [numeric_id(x) for x in blockers_raw if numeric_id(x) is not None]
        if legal:
            return pair(legal[0], target, "blocker_ids0+target_id")

    if isinstance(raw.get("evidence"), (str, int)) or "type" in raw or "description" in raw:
        return {"relation": raw, "blocker_id": None, "target_id": None,
                "status": "unknown", "schema": "no_numeric_endpoints"}
    return {"relation": raw, "blocker_id": None, "target_id": None,
            "status": "unknown", "schema": "unrecognized"}


def normalize_assessment(assessment: Mapping[str, Any],
                         visible_ids: list[int]) -> dict[str, Any]:
    """Deduplicate candidates by legal visible ID; normalize relations.

    Design 3.3: candidates dedup by legal visible ID; target uniqueness means
    unique ID. Confidence unknown stays unknown.
    """
    visible = set(visible_ids)
    seen: set[int] = set()
    candidates: list[dict[str, Any]] = []
    invalid_candidates: list[dict[str, Any]] = []
    for candidate in assessment.get("target_candidates", []) or []:
        if not isinstance(candidate, Mapping):
            invalid_candidates.append({"reason": "non_object_candidate"})
            continue
        ident = numeric_id(candidate.get("object_id", candidate.get("id")))
        if ident is None or ident not in visible or not candidate.get("valid", True):
            invalid_candidates.append(dict(candidate))
            continue
        if ident in seen:
            continue  # duplicate entry for the same legal ID
        seen.add(ident)
        item = dict(candidate)
        item["object_id"] = ident
        candidates.append(item)

    relations_raw = assessment.get("blocking_relations") or []
    relations = [normalize_relation(r) for r in relations_raw]
    return {
        "target_candidates": candidates,
        "unique_target_ids": sorted(seen),
        "invalid_candidates": invalid_candidates,
        "relations": relations,
        "raw_relation_count": len(relations_raw),
        "visibility": assessment.get("target_visibility"),
        "confidence": coerce_confidence(assessment.get("route_confidence")),
        "recommended_route": assessment.get("recommended_route"),
    }


def select_r(packet: Mapping[str, Any], assessment: Mapping[str, Any],
             a_route: str) -> dict[str, Any]:
    """Constrained route-correction decision on top of frozen A.

    Trigger rules v1 (design 3.3, fixed threshold 0.75):
      A=blocker_first            -> keep B1 final prediction (any evidence)
      A=direct, evidence risk    -> target_first identity verification
      A=direct, unique+free+safe -> keep B1 final prediction
      A=target_first, unique target + blocked + confident + strong legal
         relation pointing at that target -> blocker_first planning
      A=target_first otherwise   -> keep B1 final prediction
    """
    visible = [int(c["id"]) for c in packet["candidates"]]
    norm = normalize_assessment(assessment, visible)
    unique_ids = norm["unique_target_ids"]
    confidence = norm["confidence"]

    decision = {
        "policy_version": VERSION,
        "a_route": a_route,
        "selected_route": a_route,
        "branch": None,
        "guard_reasons": [],
        "evidence": {
            "unique_target_ids": unique_ids,
            "valid_candidate_count": len(norm["target_candidates"]),
            "invalid_candidate_count": len(norm["invalid_candidates"]),
            "visibility": norm["visibility"],
            "confidence": confidence,
            "raw_relation_count": norm["raw_relation_count"],
            "normalized_relations": [
                {"schema": r["schema"], "status": r["status"],
                 "blocker_id": r["blocker_id"], "target_id": r["target_id"],
                 "strength": relation_strength(r["relation"])}
                for r in norm["relations"]
            ],
        },
    }

    if a_route == "blocker_first":
        decision["guard_reasons"] = ["R_preserve_blocker_first"]
        return decision

    if a_route == "direct":
        reasons = []
        if len(unique_ids) > 1:
            reasons.append("R_multiple_legal_target_candidates")
        elif len(unique_ids) == 0:
            reasons.append("R_missing_legal_target_candidate")
        elif norm["visibility"] != "free_visible":
            reasons.append("R_target_not_free_visible")
        elif norm["raw_relation_count"] > 0:
            reasons.append("R_blocking_relation_present")
        elif bool(packet.get("duplicate_mask_conflict")):
            reasons.append("R_duplicate_mask_conflict")
        elif confidence is not None and confidence < DIRECT_CONFIDENCE:
            reasons.append("R_route_confidence_below_threshold")
        elif confidence is None:
            reasons.append("R_route_confidence_unknown")
        if reasons:
            decision["selected_route"] = "target_first"
            decision["branch"] = "I"
            decision["guard_reasons"] = reasons
        else:
            decision["guard_reasons"] = ["R_unique_free_target_keep_A"]
        return decision

    if a_route == "target_first":
        if len(unique_ids) != 1:
            decision["guard_reasons"] = ["R_target_not_unique_keep_A"]
            return decision
        target_id = unique_ids[0]
        if norm["visibility"] not in BLOCKED_VISIBILITIES:
            decision["guard_reasons"] = ["R_target_not_predicted_blocked_keep_A"]
            return decision
        if confidence is None or confidence < DIRECT_CONFIDENCE:
            decision["guard_reasons"] = [
                "R_confidence_unknown_or_below_threshold_keep_A"]
            return decision
        supporting = []
        for relation in norm["relations"]:
            if relation["status"] == "unknown":
                continue
            blocker = relation["blocker_id"]
            endpoint_target = relation["target_id"]
            if (blocker in visible and endpoint_target == target_id
                    and blocker != target_id
                    and relation_strength(relation["relation"]) >= 2):
                supporting.append(relation)
        if supporting:
            decision["selected_route"] = "blocker_first"
            decision["branch"] = "O"
            decision["guard_reasons"] = ["R_strong_legal_occlusion_to_unique_target"]
            decision["evidence"]["supporting_relations"] = [
                {"schema": r["schema"], "blocker_id": r["blocker_id"],
                 "target_id": r["target_id"],
                 "strength": relation_strength(r["relation"])}
                for r in supporting
            ]
        else:
            decision["guard_reasons"] = ["R_no_strong_legal_relation_to_target_keep_A"]
        return decision

    raise ValueError(f"unknown A route: {a_route}")


def funnel(packet: Mapping[str, Any], assessment: Mapping[str, Any],
           a_route: str) -> list[str]:
    """Layer-by-layer funnel labels for reachability reporting (design 3.3)."""
    visible = [int(c["id"]) for c in packet["candidates"]]
    norm = normalize_assessment(assessment, visible)
    labels = [f"A={a_route}"]
    if a_route == "target_first":
        labels.append(f"unique_target={len(norm['unique_target_ids'])==1}")
        labels.append(f"blocked_visibility={norm['visibility'] in BLOCKED_VISIBILITIES}")
        conf = norm["confidence"]
        labels.append(f"confidence_ok={conf is not None and conf >= DIRECT_CONFIDENCE}")
        decision = select_r(packet, assessment, a_route)
        labels.append(f"triggered={decision['branch'] == 'O'}")
    elif a_route == "direct":
        labels.append(f"unique_target={len(norm['unique_target_ids'])==1}")
        decision = select_r(packet, assessment, a_route)
        labels.append(f"triggered={decision['branch'] == 'I'}")
    else:
        labels.append("no_intervention_by_design")
    return labels
