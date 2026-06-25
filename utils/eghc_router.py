"""EGHC-v1 deterministic guard router.

Implements the route state machine with guard rules.
"""


def select_route(packet, assessment, challenger=None):
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

    # Blocker first: only if blocking relations exist
    if assessment.get("recommended_route") == "blocker_first" and assessment.get("blocking_relations"):
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
