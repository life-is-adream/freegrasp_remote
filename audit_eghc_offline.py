"""EGHC-v1 offline audit.

Fixed-cache offline audit for evidence, router, and segmentation replay.
"""

import json
import os


def load_run_details(run_dir, subset):
    """Load details for a specific subset from a run directory.

    Parameters
    ----------
    run_dir : str
        Path to run directory (e.g., data/output/ablation_matrix/S0/split_0).
    subset : str
        Subset name (e.g., easy_no_ambi).

    Returns
    -------
    list of dict or None
    """
    details_path = os.path.join(run_dir, f"details_{subset}.json")
    if not os.path.exists(details_path):
        return None
    with open(details_path) as f:
        return json.load(f)


def audit_router_decisions(details_rows):
    """Audit router decisions from detail rows.

    Parameters
    ----------
    details_rows : list of dict
        Detail rows with reasoning metadata.

    Returns
    -------
    dict with route_counts, guard_reasons_distribution, adjudication_rate
    """
    route_counts = {"direct": 0, "target_first": 0, "blocker_first": 0}
    guard_reasons = {}
    adjudication_count = 0

    for row in details_rows:
        reasoning = row.get("reasoning", {})
        route_mode = reasoning.get("route_mode", "unknown")
        route_counts[route_mode] = route_counts.get(route_mode, 0) + 1

        sc = reasoning.get("scene_complexity_features", {})
        for reason in sc.get("guard_reasons", []):
            guard_reasons[reason] = guard_reasons.get(reason, 0) + 1

        if sc.get("requires_adjudication", False):
            adjudication_count += 1

    total = len(details_rows) or 1
    return {
        "route_counts": route_counts,
        "guard_reasons_distribution": guard_reasons,
        "adjudication_rate": adjudication_count / total,
    }
