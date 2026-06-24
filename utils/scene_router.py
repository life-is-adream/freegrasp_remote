"""Geometry-aware scene complexity router for FreeGrasp protocol selection.

Computes a scene complexity score from Molmo point annotations and
maps the score to one of three route modes:
  direct       → easy-like  → direct_target + id_repair
  target_first → medium-like → target_first_evidence_gate_v9 + geometry_repair
  blocker_first → hard-like  → hard_blocker_first_v10 + id_repair

No VLM call is needed — the router uses only geometric features
already available as intermediate products of the pipeline.

Version: scene-complexity-v3 (depth-aware hook added)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

# ---------------------------------------------------------------------------
# Configuration — tuned by offline audit (v2)
# ---------------------------------------------------------------------------

SCENE_ROUTER_VERSION = "scene-complexity-v3"

# Object count thresholds
COUNT_LOW_MAX = 5       # ≤ 5 → low density score
COUNT_HIGH_MIN = 9      # ≥ 9 → high density score

# Nearest-neighbor clustering ratio thresholds
# ratio = median_nn_dist / image_diag;  lower = more clustered
CLUSTER_LOW_MIN = 0.10  # ratio ≥ 0.10 → well spread
CLUSTER_HIGH_MAX = 0.06 # ratio ≤ 0.06 → very clustered

# Spatial extent thresholds (fraction of image diagonal)
EXTENT_LOW_MAX = 0.55   # ≤ 55% → compact
EXTENT_HIGH_MIN = 0.80  # ≥ 80% → wide

# Composite score thresholds
SCORE_MEDIUM_CEIL = 0.7  # score < 0.7 → direct
SCORE_HARD_CEIL = 1.2    # score < 1.2 → target_first; ≥ 1.2 → blocker_first


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SceneComplexityFeatures:
    object_count: int
    median_nn_dist: float
    nn_cluster_ratio: float
    spatial_extent: float
    density_score: float
    cluster_score: float
    extent_score: float
    composite_score: float
    route_mode: str
    depth_occlusion_score: float = 0.0  # 0.0 when no depth available
    depth_available: bool = False


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _pairwise_distances(parsed_data):
    """Return Nx2 array of (x, y) coords and pairwise distance matrix."""
    coords = np.array([(item[1], item[2]) for item in parsed_data], dtype=float)
    n = len(coords)
    if n < 2:
        return coords, np.zeros((n, n))
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=-1))
    return coords, dist


def _nearest_neighbor_stats(coords, dist_matrix):
    """Compute median nearest-neighbor distance."""
    n = len(coords)
    if n < 2:
        return 0.0, 0.0
    np.fill_diagonal(dist_matrix, np.inf)
    nn_dists = dist_matrix.min(axis=1)
    return float(np.median(nn_dists)), float(nn_dists.mean())


def _spatial_extent(coords, image_diag):
    """Fraction of image diagonal covered by the point cloud bbox."""
    if len(coords) < 2:
        return 0.0
    xs, ys = coords[:, 0], coords[:, 1]
    bbox_diag = float(np.hypot(xs.max() - xs.min(), ys.max() - ys.min()))
    if image_diag and image_diag > 0:
        return bbox_diag / image_diag
    return 0.0


def _bbox_overlap_stats(parsed_data, predicted_geometry=None):
    """Compute pairwise bbox overlap.

    Uses SAM-predicted bboxes if available, otherwise builds
    Voronoi-radius bboxes around each Molmo point.
    """
    if predicted_geometry and predicted_geometry.get("candidates"):
        candidates = predicted_geometry["candidates"]
        ids = sorted(candidates.keys(), key=lambda k: int(k))
        bboxes = {oid: candidates[oid]["bbox"] for oid in ids}
    else:
        # Use half the nearest-neighbor distance as bbox radius
        coords = np.array([(item[1], item[2]) for item in parsed_data], dtype=float)
        if len(coords) < 2:
            return 0.0, 0.0, 0
        _, dist_matrix = _pairwise_distances(parsed_data)
        np.fill_diagonal(dist_matrix, np.inf)
        nn_dists = dist_matrix.min(axis=1)
        bboxes = {}
        for i, (molmo_id, x, y, _) in enumerate(parsed_data):
            r = max(10, int(nn_dists[i] * 0.4))
            bboxes[molmo_id] = (x - r, y - r, x + r, y + r)

    max_overlap = 0.0
    total_overlap = 0.0
    overlap_pairs = 0
    n_pairs = 0
    for a_id, b_id in combinations(sorted(bboxes.keys(), key=lambda k: int(k)), 2):
        n_pairs += 1
        a = bboxes[a_id]
        b = bboxes[b_id]
        x1 = max(a[0], b[0])
        y1 = max(a[1], b[1])
        x2 = min(a[2], b[2])
        y2 = min(a[3], b[3])
        inter = max(0, x2 - x1 + 1) * max(0, y2 - y1 + 1)
        area_a = max(1, (a[2] - a[0] + 1) * (a[3] - a[1] + 1))
        area_b = max(1, (b[2] - b[0] + 1) * (b[3] - b[1] + 1))
        overlap_smaller = float(inter) / float(min(area_a, area_b))
        total_overlap += overlap_smaller
        if overlap_smaller > max_overlap:
            max_overlap = overlap_smaller
        if overlap_smaller > 0.10:
            overlap_pairs += 1

    avg_overlap = total_overlap / n_pairs if n_pairs else 0.0
    return max_overlap, avg_overlap, overlap_pairs


def _depth_occlusion_features(parsed_data, depth_map):
    """Compute depth-based occlusion features.

    Parameters
    ----------
    parsed_data : list of (molmo_id, x, y, gt_id)
    depth_map : numpy array (H, W)

    Returns
    -------
    dict with depth features and occlusion_score in [0, 2]
    """
    if depth_map is None or len(parsed_data) < 2:
        return {"depth_occlusion_score": 0.0, "depth_available": False}

    h, w = depth_map.shape
    coords = np.array([(item[1], item[2]) for item in parsed_data], dtype=int)
    coords[:, 0] = np.clip(coords[:, 0], 0, w - 1)
    coords[:, 1] = np.clip(coords[:, 1], 0, h - 1)

    depths = depth_map[coords[:, 1], coords[:, 0]]
    median_depth = float(np.median(depths))
    depth_std = float(np.std(depths))
    foreground_ratio = float(np.mean(depths < median_depth))

    # High depth variance + many foreground objects → higher occlusion likelihood
    depth_norm_std = min(1.0, depth_std / (median_depth + 1e-6))
    occlusion_score = min(2.0, depth_norm_std * 1.5 + abs(foreground_ratio - 0.5) * 1.0)

    return {
        "depth_median": round(median_depth, 3),
        "depth_std": round(depth_std, 3),
        "foreground_ratio": round(foreground_ratio, 3),
        "depth_occlusion_score": round(occlusion_score, 4),
        "depth_available": True,
    }


def compute_scene_features(parsed_data, predicted_geometry=None, image_shape=None, depth_map=None):
    """Compute scene complexity features from Molmo points.

    Parameters
    ----------
    parsed_data : list of (molmo_id, x, y, gt_id)
    predicted_geometry : dict, optional
    image_shape : tuple of (H, W), optional
    depth_map : numpy array (H, W), optional
        Depth map for occlusion estimation. If None, depth features are skipped.
        Hook for future depth-aware routing improvements.

    Returns
    -------
    SceneComplexityFeatures
    """
    object_count = len(parsed_data)
    image_diag = None
    if image_shape:
        image_diag = float(np.hypot(image_shape[0], image_shape[1]))

    coords, dist_matrix = _pairwise_distances(parsed_data)
    median_nn, mean_nn = _nearest_neighbor_stats(coords, dist_matrix)
    extent = _spatial_extent(coords, image_diag)

    nn_ratio = median_nn / image_diag if image_diag and image_diag > 0 else 0.0

    max_overlap, avg_overlap, overlap_pairs = _bbox_overlap_stats(
        parsed_data, predicted_geometry
    )

    # --- Component scores (each in [0, 2]) ---

    # Density: based on object count
    if object_count <= COUNT_LOW_MAX:
        density_score = max(0.0, (object_count - 1) / (COUNT_LOW_MAX - 1))
    elif object_count >= COUNT_HIGH_MIN:
        density_score = 2.0
    else:
        density_score = 1.0 + (object_count - COUNT_LOW_MAX) / (
            COUNT_HIGH_MIN - COUNT_LOW_MAX
        )

    # Cluster: lower nn_ratio = more clustered = higher score
    if nn_ratio >= CLUSTER_LOW_MIN:
        cluster_score = 0.0
    elif nn_ratio <= CLUSTER_HIGH_MAX:
        cluster_score = 2.0
    else:
        cluster_score = 2.0 * (CLUSTER_LOW_MIN - nn_ratio) / (
            CLUSTER_LOW_MIN - CLUSTER_HIGH_MAX
        )

    # Overlap bonus: add to cluster score
    overlap_bonus = min(1.0, max_overlap / 0.30) * 0.5
    cluster_score = min(2.0, cluster_score + overlap_bonus)

    # Extent: wider spread = lower complexity
    if extent >= EXTENT_LOW_MAX:
        extent_score = 0.0
    elif extent <= 0.20:
        extent_score = 2.0
    else:
        extent_score = 2.0 * (EXTENT_LOW_MAX - extent) / (EXTENT_LOW_MAX - 0.20)

    # --- Depth-aware occlusion (optional hook) ---
    depth_features = _depth_occlusion_features(parsed_data, depth_map)
    depth_occlusion_score = depth_features.get("depth_occlusion_score", 0.0)
    depth_available = depth_features.get("depth_available", False)

    # --- Composite (weighted) ---
    # When depth is available, blend it in with 0.20 weight
    if depth_available:
        composite = (
            0.28 * density_score
            + 0.32 * cluster_score
            + 0.20 * extent_score
            + 0.20 * depth_occlusion_score
        )
    else:
        composite = (
            0.35 * density_score
            + 0.40 * cluster_score
            + 0.25 * extent_score
        )

    # --- Route decision ---
    # Single object is always direct (no ambiguity possible)
    if object_count <= 1:
        route_mode = "direct"
    elif composite < SCORE_MEDIUM_CEIL:
        route_mode = "direct"
    elif composite < SCORE_HARD_CEIL:
        route_mode = "target_first"
    else:
        route_mode = "blocker_first"

    return SceneComplexityFeatures(
        object_count=object_count,
        median_nn_dist=round(median_nn, 2),
        nn_cluster_ratio=round(nn_ratio, 4),
        spatial_extent=round(extent, 4),
        density_score=round(density_score, 4),
        cluster_score=round(cluster_score, 4),
        extent_score=round(extent_score, 4),
        composite_score=round(composite, 4),
        route_mode=route_mode,
        depth_occlusion_score=round(depth_occlusion_score, 4),
        depth_available=depth_available,
    )


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

def route_scene(parsed_data, predicted_geometry=None, image_shape=None, depth_map=None):
    """Return a ``route_assessment`` dict compatible with the existing pipeline."""
    features = compute_scene_features(
        parsed_data,
        predicted_geometry=predicted_geometry,
        image_shape=image_shape,
        depth_map=depth_map,
    )
    return {
        "route_mode": features.route_mode,
        "route_confidence": 1.0,
        "target_object_id": None,
        "target_label": "target",
        "ambiguity_evidence": [],
        "blocker_evidence": [],
        "scene_router_version": SCENE_ROUTER_VERSION,
        "scene_complexity": {
            "object_count": features.object_count,
            "median_nn_dist": features.median_nn_dist,
            "nn_cluster_ratio": features.nn_cluster_ratio,
            "spatial_extent": features.spatial_extent,
            "density_score": features.density_score,
            "cluster_score": features.cluster_score,
            "extent_score": features.extent_score,
            "composite_score": features.composite_score,
            "route_mode": features.route_mode,
            "depth_occlusion_score": features.depth_occlusion_score,
            "depth_available": features.depth_available,
        },
    }
