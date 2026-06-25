"""GT access guard for EGHC-v1.

Scans payloads for forbidden GT fields and raises RuntimeError if found.
Ensures inference code never accesses ground-truth data.
"""

FORBIDDEN_GT_KEYS = {
    "instances_objects",
    "instances_semantic",
    "groundTruthObjIds",
    "gt_masks",
    "molmo_to_gt_map",
    "difficulty",
}


def assert_payload_has_no_forbidden_gt_keys(payload, path="root"):
    """Recursively scan payload for forbidden GT keys.

    Parameters
    ----------
    payload : dict or list
        Payload to scan.
    path : str
        Current path for error messages.

    Raises
    ------
    RuntimeError
        If any forbidden GT key is found.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_GT_KEYS:
                raise RuntimeError(f"Forbidden GT field detected at {path}.{key}")
            assert_payload_has_no_forbidden_gt_keys(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_payload_has_no_forbidden_gt_keys(value, f"{path}[{index}]")
