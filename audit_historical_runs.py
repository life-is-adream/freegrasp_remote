"""Historical run provenance audit for EGHC-v1.

Classifies historical runs as oracle_assisted or clean_no_gt
based on manifest and reasoning metadata.
"""

ORACLE_MARKERS = {
    "instances_semantic",
    "instances_objects",
    "oracle_feature",
}


def classify_run(manifest, details_rows):
    """Classify a historical run's provenance.

    Parameters
    ----------
    manifest : dict
        Run manifest with feature_source, subset_policy, etc.
    details_rows : list of dict
        Detail rows with reasoning metadata.

    Returns
    -------
    dict with provenance_class, feature_source, semantic_sources, geometry_sources
    """
    feature_source = manifest.get("feature_source")
    reasoning_rows = [row.get("reasoning", {}) for row in details_rows]
    semantic_sources = {row.get("semantic_source") for row in reasoning_rows}
    geometry_sources = {row.get("geometry_source") for row in reasoning_rows}
    used_gt_map = any(bool(row.get("molmo_to_gt_map_used")) for row in reasoning_rows)

    if feature_source == "oracle_feature" or used_gt_map:
        provenance_class = "oracle_assisted"
    elif ORACLE_MARKERS & semantic_sources or ORACLE_MARKERS & geometry_sources:
        provenance_class = "oracle_assisted"
    else:
        provenance_class = "clean_no_gt"

    return {
        "provenance_class": provenance_class,
        "feature_source": feature_source,
        "semantic_sources": sorted(x for x in semantic_sources if x is not None),
        "geometry_sources": sorted(x for x in geometry_sources if x is not None),
    }
