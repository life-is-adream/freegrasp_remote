"""EGHC-v1 challenger eligibility logic.

Scene-disjoint challenger training and promotion report.
"""


def evaluate_training_eligibility(registry_rows):
    """Evaluate if challenger training is eligible.

    Parameters
    ----------
    registry_rows : list of dict
        Registry rows with provenance_class and route_executed.

    Returns
    -------
    dict with eligible, covered_routes, selected_router
    """
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
