"""EGHC-v1 sealed prediction artifacts.

Immutable prediction artifacts and scorer handoff payloads.
"""


def seal_prediction(sample_key, reasoning, mask_path):
    """Create a sealed prediction artifact.

    Parameters
    ----------
    sample_key : dict
        Sample identity with scene_id, query_target_id, annotation.
    reasoning : dict
        Reasoning metadata with selected_object_id, etc.
    mask_path : str
        Path to the predicted mask file.

    Returns
    -------
    dict
        Sealed prediction artifact.
    """
    return {
        "sample_key": sample_key,
        "reasoning": reasoning,
        "mask_path": mask_path,
    }


def build_scorer_payload(sealed_prediction, gt_mask_path=None):
    """Build a payload for the isolated scorer.

    Parameters
    ----------
    sealed_prediction : dict
        Sealed prediction artifact.
    gt_mask_path : str, optional
        Path to the ground-truth mask for scoring.

    Returns
    -------
    dict
        Scorer payload with sample_key, reasoning, predicted_mask_path, gt_mask_path.
    """
    return {
        "sample_key": sealed_prediction["sample_key"],
        "reasoning": sealed_prediction["reasoning"],
        "predicted_mask_path": sealed_prediction["mask_path"],
        "gt_mask_path": gt_mask_path,
    }
