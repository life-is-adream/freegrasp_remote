"""Deployable evidence builder for EGHC-v1.

Loads sanitized bundles and builds no-GT evidence packets.
"""

from utils.gt_access_guard import assert_payload_has_no_forbidden_gt_keys


def build_evidence_packet(bundle):
    """Build a no-GT evidence packet from a sanitized bundle.

    Parameters
    ----------
    bundle : dict
        Sanitized inference bundle with scene_id, query_target_id,
        visible_points, depth_path, predicted_masks.

    Returns
    -------
    dict with scene_id, query_target_id, visible_ids, depth_available, mask_candidates
    """
    assert_payload_has_no_forbidden_gt_keys(bundle)
    return {
        "scene_id": bundle["scene_id"],
        "query_target_id": bundle["query_target_id"],
        "visible_ids": [item["object_id"] for item in bundle["visible_points"]],
        "depth_available": bool(bundle.get("depth_path")),
        "mask_candidates": bundle.get("predicted_masks", []),
    }
