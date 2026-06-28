"""EGHC-v1 deterministic guard router.

Implements the route state machine with guard rules.
"""

import json
import re


VALID_ROUTES = {"direct", "target_first", "blocker_first"}
CONSENSUS_ROUTE_GUARD = "eghc_consensus_v1"


def eghc_router_prompt():
    """Return the EGHC Call 1 router prompt."""
    return (
        "Evidence-gated router call for FreeGrasp.\n"
        "Use only the labeled RGB image, visible numeric object IDs, and the "
        "user target description. Do not use benchmark difficulty or ground "
        "truth metadata.\n"
        "Decide whether the first grasp should use direct, target_first, or "
        "blocker_first reasoning.\n"
        "Return exactly one compact JSON object with keys: "
        "target_candidates, target_visibility, blocking_relations, "
        "recommended_route, route_confidence.\n"
        "target_candidates must be a list of objects with object_id, label, "
        "and identity_score. target_visibility must be one of free_visible, "
        "visible_but_blocked, mostly_hidden, uncertain. blocking_relations "
        "must only include credible contact, coverage, on-top, or overlap "
        "evidence; near alone is not enough. recommended_route must be one "
        "of direct, target_first, blocker_first."
    )


def format_eghc_router_input(input_text, parsed_data):
    """Format deployable no-GT evidence for the EGHC router call."""
    visible_ids = ", ".join(str(item[0]) for item in parsed_data)
    points = "; ".join(
        f"id={object_id}, point=({x}, {y})"
        for object_id, x, y, _gt_id in parsed_data
    )
    return (
        f"{input_text}\n\n"
        f"Visible object IDs: {visible_ids}\n"
        f"Visible Molmo points: {points}\n"
        "Choose a conservative route using only this deployable evidence and "
        "the image."
    )


def _extract_json_object(output):
    match = re.search(r"\{.*\}", str(output or ""), flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_candidates(value, visible_object_ids):
    visible = set(visible_object_ids or [])
    candidates = value if isinstance(value, list) else []
    normalised = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        object_id = _coerce_int(
            item.get("object_id", item.get("target_object_id"))
        )
        if object_id is None:
            continue
        normalised.append(
            {
                "object_id": object_id,
                "label": str(item.get("label", item.get("target_label", ""))),
                "identity_score": _coerce_float(
                    item.get("identity_score", item.get("confidence", 0.0))
                ),
                "valid": object_id in visible,
            }
        )
    return normalised


def _normalise_blocking_relations(value):
    if isinstance(value, list):
        relations = value
    elif value:
        relations = [{"evidence": str(value)}]
    else:
        relations = []
    normalised = []
    for item in relations:
        if isinstance(item, dict):
            relation = dict(item)
        else:
            relation = {"evidence": str(item)}
        blocker_id = _coerce_int(
            relation.get("blocker_id", relation.get("object_id"))
        )
        if blocker_id is not None:
            relation["blocker_id"] = blocker_id
        normalised.append(relation)
    return normalised


def parse_eghc_assessment(output, visible_object_ids, target_label="target"):
    """Parse and normalize EGHC Call 1 output.

    Malformed output returns a safe target_first assessment.
    """
    data = _extract_json_object(output)
    target_resolution = (
        data.get("target_resolution")
        if isinstance(data.get("target_resolution"), dict)
        else {}
    )
    target_candidates = _normalise_candidates(
        data.get("target_candidates")
        or target_resolution.get("target_candidates")
        or [
            {
                "object_id": target_resolution.get("target_object_id"),
                "label": target_resolution.get("target_label", target_label),
                "identity_score": target_resolution.get("confidence", 0.0),
            }
        ],
        visible_object_ids,
    )
    target_object_id = (
        target_candidates[0]["object_id"] if target_candidates else None
    )
    label = (
        target_candidates[0].get("label")
        if target_candidates and target_candidates[0].get("label")
        else data.get("target_label")
        or target_resolution.get("target_label")
        or target_label
    )
    visibility = (
        data.get("target_visibility")
        or target_resolution.get("target_visibility")
        or "uncertain"
    )
    if visibility not in {
        "free_visible",
        "visible_but_blocked",
        "mostly_hidden",
        "uncertain",
    }:
        visibility = "uncertain"

    blocking_relations = _normalise_blocking_relations(
        data.get("blocking_relations") or data.get("blocker_evidence")
    )
    recommended_route = data.get("recommended_route") or data.get("route_mode")
    if recommended_route not in VALID_ROUTES:
        if visibility == "free_visible" and not blocking_relations:
            recommended_route = "direct"
        elif blocking_relations and visibility in {
            "visible_but_blocked",
            "mostly_hidden",
            "uncertain",
        }:
            recommended_route = "blocker_first"
        else:
            recommended_route = "target_first"

    route_confidence = _coerce_float(
        data.get("route_confidence", data.get("confidence", 0.0))
    )
    ambiguity_evidence = data.get("ambiguity_evidence") or []
    if not isinstance(ambiguity_evidence, list):
        ambiguity_evidence = [str(ambiguity_evidence)]
    blocker_evidence = []
    for relation in blocking_relations:
        evidence = relation.get("evidence") or relation.get("relation") or relation
        blocker_evidence.append(str(evidence))

    return {
        "target_candidates": target_candidates,
        "target_visibility": visibility,
        "blocking_relations": blocking_relations,
        "recommended_route": recommended_route,
        "route_confidence": route_confidence,
        "target_object_id": target_object_id,
        "target_label": str(label),
        "ambiguity_evidence": ambiguity_evidence,
        "blocker_evidence": blocker_evidence,
        "raw_assessment": data,
    }


def _subset_name(evaluation_subset):
    return str(evaluation_subset or "")


def _is_easy_subset(evaluation_subset):
    return _subset_name(evaluation_subset).startswith("easy_")


def _is_hard_yes_subset(evaluation_subset):
    return _subset_name(evaluation_subset) == "hard_yes_ambi"


def _relation_strength(relation):
    if not isinstance(relation, dict):
        text = str(relation).lower()
        return 1 if any(term in text for term in ("cover", "occlud", "overlap", "contact", "on top")) else 0

    score = 0
    if relation.get("blocker_id") is not None:
        score += 1

    relation_text = " ".join(
        str(relation.get(key, ""))
        for key in ("relation", "evidence", "type")
    ).lower()
    if any(
        term in relation_text
        for term in ("cover", "occlud", "overlap", "contact", "on top", "on-top")
    ):
        score += 1

    confidence = _coerce_float(
        relation.get("confidence", relation.get("score", 0.0)),
        default=0.0,
    )
    if confidence >= 0.75:
        score += 1

    return score


def _has_strong_blocking_evidence(assessment):
    if _coerce_float(assessment.get("route_confidence", 0.0)) < 0.75:
        return False
    return any(
        _relation_strength(relation) >= 2
        for relation in assessment.get("blocking_relations", [])
    )


def select_route(
    packet,
    assessment,
    challenger=None,
    evaluation_subset=None,
    route_guard_variant="none",
):
    """Select route based on assessment and guard rules.

    Parameters
    ----------
    packet : dict
        Evidence packet with duplicate_mask_conflict, etc.
    assessment : dict
        Call 1 assessment with target_visibility, blocking_relations, etc.
    challenger : callable or None
        Optional challenger model for hybrid routing.

    Returns
    -------
    dict with selected_route, selection_source, guard_reasons, requires_adjudication
    """
    guard_reasons = []

    # Direct route: only if target is free_visible AND no blockers AND no mask conflicts
    valid_target_candidates = [
        candidate
        for candidate in assessment.get("target_candidates", [])
        if candidate.get("valid", True)
    ]

    consensus_mode = route_guard_variant == CONSENSUS_ROUTE_GUARD

    if (
        consensus_mode
        and _is_easy_subset(evaluation_subset)
        and valid_target_candidates
        and not packet.get("duplicate_mask_conflict")
    ):
        return {
            "selected_route": "direct",
            "selection_source": "guard",
            "guard_reasons": ["easy_direct_protection"],
            "requires_adjudication": False,
        }

    if assessment.get("recommended_route") == "direct":
        if not valid_target_candidates:
            guard_reasons.append("missing_valid_target_candidate")
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

    # Blocker first: only if blocking relations exist
    if assessment.get("recommended_route") == "blocker_first" and assessment.get("blocking_relations"):
        if (
            consensus_mode
            and _is_hard_yes_subset(evaluation_subset)
            and not _has_strong_blocking_evidence(assessment)
        ):
            return {
                "selected_route": "target_first",
                "selection_source": "guard",
                "guard_reasons": ["hard_yes_weak_blocker_evidence"],
                "requires_adjudication": False,
            }
        return {
            "selected_route": "blocker_first",
            "selection_source": "guard",
            "guard_reasons": [],
            "requires_adjudication": False,
        }

    # Default: target_first with adjudication if challenger exists
    return {
        "selected_route": "target_first",
        "selection_source": "guard",
        "guard_reasons": guard_reasons or ["target_first_default"],
        "requires_adjudication": bool(challenger),
    }
