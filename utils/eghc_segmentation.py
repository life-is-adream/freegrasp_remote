"""EGHC-v1 segmentation repair and ranked-candidate fallback.

No-GT mask repair and ranked-candidate fallback logic.
"""


def score_candidate_mask(candidate, point):
    """Score a mask candidate based on point containment and SAM score.

    Parameters
    ----------
    candidate : dict
        Mask candidate with contains_point, sam_score, duplicate_penalty.
    point : tuple
        (x, y) point coordinates.

    Returns
    -------
    float
        Score for this candidate.
    """
    contains_point = bool(candidate.get("contains_point", False))
    duplicate_penalty = float(candidate.get("duplicate_penalty", 0.0))
    sam_score = float(candidate.get("sam_score", 0.0))
    return (2.0 if contains_point else 0.0) + sam_score - duplicate_penalty


def select_best_mask(candidates, point):
    """Select the best mask from candidates.

    Parameters
    ----------
    candidates : list of dict
        Mask candidates with contains_point, sam_score, duplicate_penalty.
    point : tuple
        (x, y) point coordinates.

    Returns
    -------
    dict or None
        Best candidate, or None if no candidates.
    """
    if not candidates:
        return None
    scored = [(score_candidate_mask(c, point), c) for c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
