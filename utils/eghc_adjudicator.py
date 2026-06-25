"""EGHC-v1 adjudication logic.

Determines when to trigger Qwen adjudication based on
assessment, route decision, plan, and visible IDs.
"""


def should_trigger_adjudication(assessment, route_decision, plan, visible_ids):
    """Check if Qwen adjudication should be triggered.

    Parameters
    ----------
    assessment : dict
        Call 1 assessment.
    route_decision : dict
        Route decision from eghc_router.
    plan : dict
        Call 2 plan with first_grasp_object_id.
    visible_ids : set or list
        Set of visible object IDs.

    Returns
    -------
    bool
        True if adjudication should be triggered.
    """
    if isinstance(visible_ids, list):
        visible_ids = set(visible_ids)

    # Invalid object ID
    if plan.get("first_grasp_object_id") not in visible_ids:
        return True

    # Direct route but blocking relations exist
    if route_decision.get("selected_route") == "direct" and assessment.get("blocking_relations"):
        return True

    # Low confidence
    if plan.get("confidence", 1.0) < 0.60:
        return True

    return False
