"""Geometry-aware scene complexity router for FreeGrasp protocol selection.

Computes a scene complexity score from Molmo point annotations and
maps the score to one of three route modes:
  direct       → easy-like  → direct_target + id_repair
  target_first → medium-like → target_first_evidence_gate_v9 + geometry_repair
  blocker_first → hard-like  → hard_blocker_first_v10 + id_repair

v4: Two-stage router with VLM fallback for uncertain cases.

Version: scene-complexity-v4 (VLM two-stage)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import combinations

import numpy as np

# ---------------------------------------------------------------------------
# Configuration — tuned by offline audit (v2)
# ---------------------------------------------------------------------------

SCENE_ROUTER_VERSION = "scene-complexity-v4"

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

# VLM two-stage thresholds
VLM_UNCERTAIN_LOW = 0.5   # score < 0.5 → confident direct, skip VLM
VLM_UNCERTAIN_HIGH = 1.5  # score > 1.5 → confident blocker_first, skip VLM
# Between 0.5 and 1.5 → uncertain → call VLM


# ---------------------------------------------------------------------------
# VLM two-stage router (v4)
# ---------------------------------------------------------------------------

def vlm_scene_complexity_prompt():
    """System prompt for the VLM scene complexity assessment."""
    return (
        "You are a scene complexity assessor for a robotic grasping system.\n"
        "Analyze the image and determine the occlusion level of objects.\n"
        "\n"
        "Rules:\n"
        "- 'none': All objects are clearly visible with no occlusion.\n"
        "- 'light': Some objects are partially occluded or overlapping.\n"
        "- 'heavy': Significant occlusion; objects are hidden behind others.\n"
        "\n"
        "Respond in JSON only:\n"
        '{"occlusion_level": "none" | "light" | "heavy", "confidence": 0.0-1.0, "reason": "brief explanation"}'
    )


def parse_vlm_route(vlm_output):
    """Parse VLM occlusion assessment into a route_mode.

    Returns
    -------
    dict with route_mode, confidence, occlusion_level, reason
    """
    import json
    try:
        # Try to extract JSON from the output
        text = vlm_output.strip()
        # Handle markdown code blocks
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
        data = json.loads(text)
        occlusion = data.get("occlusion_level", "none").lower()
        confidence = float(data.get("confidence", 0.5))
        reason = data.get("reason", "")
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: try keyword matching
        text_lower = vlm_output.lower()
        if "heavy" in text_lower or "significant" in text_lower or "hidden" in text_lower:
            occlusion = "heavy"
            confidence = 0.6
        elif "light" in text_lower or "partial" in text_lower or "overlap" in text_lower:
            occlusion = "light"
            confidence = 0.5
        else:
            occlusion = "none"
            confidence = 0.4
        reason = f"keyword_fallback: {vlm_output[:80]}"

    if occlusion == "heavy":
        route_mode = "blocker_first"
    elif occlusion == "light":
        route_mode = "target_first"
    else:
        route_mode = "direct"

    return {
        "route_mode": route_mode,
        "confidence": round(confidence, 3),
        "occlusion_level": occlusion,
        "reason": reason,
    }


def needs_vlm_fallback(composite_score):
    """Return True if the geometric score is in the uncertain zone."""
    return VLM_UNCERTAIN_LOW <= composite_score <= VLM_UNCERTAIN_HIGH


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


def route_scene_vlm(parsed_data, predicted_geometry=None, image_shape=None,
                    depth_map=None, vlm_output=None):
    """Two-stage router: geometric features + VLM fallback.

    Parameters
    ----------
    parsed_data : list of (molmo_id, x, y, gt_id)
    predicted_geometry : dict, optional
    image_shape : tuple of (H, W), optional
    depth_map : numpy array, optional
    vlm_output : str or None
        Pre-computed VLM response. If None and VLM is needed,
        caller must provide it via the pipeline.

    Returns
    -------
    dict with route_assessment + vlm_stage info
    """
    features = compute_scene_features(
        parsed_data,
        predicted_geometry=predicted_geometry,
        image_shape=image_shape,
        depth_map=depth_map,
    )

    assessment = route_scene(
        parsed_data,
        predicted_geometry=predicted_geometry,
        image_shape=image_shape,
        depth_map=depth_map,
    )

    # Determine if VLM fallback is needed
    vlm_needed = needs_vlm_fallback(features.composite_score)
    vlm_used = False
    vlm_route = None

    if vlm_needed and vlm_output is not None:
        vlm_route = parse_vlm_route(vlm_output)
        # Override the geometric route with VLM decision
        assessment["route_mode"] = vlm_route["route_mode"]
        assessment["route_confidence"] = vlm_route["confidence"]
        assessment["scene_complexity"]["route_mode"] = vlm_route["route_mode"]
        vlm_used = True

    assessment["vlm_stage"] = {
        "needed": vlm_needed,
        "used": vlm_used,
        "composite_score": features.composite_score,
        "uncertain_low": VLM_UNCERTAIN_LOW,
        "uncertain_high": VLM_UNCERTAIN_HIGH,
    }
    if vlm_route:
        assessment["vlm_stage"]["occlusion_level"] = vlm_route["occlusion_level"]
        assessment["vlm_stage"]["vlm_confidence"] = vlm_route["confidence"]
        assessment["vlm_stage"]["vlm_reason"] = vlm_route["reason"]

    return assessment


# ---------------------------------------------------------------------------
# Depth-based learned classifier router (v5)
# ---------------------------------------------------------------------------

_DEPTH_MODEL = None  # lazy-loaded
_DEPTH_FEATURE_COLS = None


def _sample_depth_region(depth_map, x, y, radius=15):
    """Sample depth values in a region around (x, y)."""
    h, w = depth_map.shape
    y_min = max(0, y - radius)
    y_max = min(h, y + radius + 1)
    x_min = max(0, x - radius)
    x_max = min(w, x + radius + 1)
    region = depth_map[y_min:y_max, x_min:x_max]
    valid = region[region > 0]
    if len(valid) == 0:
        return None
    return valid


def extract_depth_route_features(parsed_data, scene_number, npz_dir=None, query_target_id=None):
    """Extract depth-only features for routing.

    Uses depth map from NPZ + Molmo point coordinates.
    No GT masks or SAM inference needed.

    Parameters
    ----------
    parsed_data : list of (molmo_id, x, y, gt_id)
    scene_number : int or str
    npz_dir : str, optional
    query_target_id : int or None
        1-indexed target object id from the dataset queryObjId.
        If None, router falls back to geometric routing.

    Returns
    -------
    dict of feature_name -> float, or None
    """
    if npz_dir is None:
        npz_dir = os.path.join(os.path.dirname(__file__), "..", "data", "npz_file")
    npz_path = os.path.join(npz_dir, f"{scene_number}.npz")
    if not os.path.exists(npz_path):
        return None

    gt = np.load(npz_path, allow_pickle=True)
    depth = gt["depth"]

    # Use the provided query_target_id (1-indexed)
    if query_target_id is None:
        return None  # refuse to guess; caller should fallback

    target_id = int(query_target_id)
    num_objects = len(parsed_data)
    if num_objects == 0:
        return None

    # Get depth for each object
    obj_depths = {}
    obj_coords = {}
    for molmo_id, px, py, _gt_id in parsed_data:
        oid = int(molmo_id)
        valid_depths = _sample_depth_region(depth, px, py, radius=20)
        if valid_depths is not None and len(valid_depths) > 0:
            obj_depths[oid] = {
                "mean": float(np.mean(valid_depths)),
                "std": float(np.std(valid_depths)),
                "median": float(np.median(valid_depths)),
                "min": float(np.min(valid_depths)),
                "max": float(np.max(valid_depths)),
            }
            obj_coords[oid] = (px, py)

    if len(obj_depths) < 2:
        return None

    # Default target is the first object (molmo_id=0)
    if target_id not in obj_depths:
        target_id = min(obj_depths.keys())

    features = {}
    features["num_objects"] = num_objects
    features["n_depth_valid"] = len(obj_depths)

    td = obj_depths[target_id]
    features["target_depth_mean"] = td["mean"]
    features["target_depth_std"] = td["std"]
    features["target_depth_range"] = td["max"] - td["min"]

    all_depth_means = [d["mean"] for d in obj_depths.values()]
    scene_depth_mean = float(np.mean(all_depth_means))
    scene_depth_std = float(np.std(all_depth_means))
    features["scene_depth_mean"] = scene_depth_mean
    features["scene_depth_std"] = scene_depth_std
    features["target_vs_scene_depth"] = td["mean"] - scene_depth_mean

    n_in_front = 0
    n_behind = 0
    depth_diffs = []
    for oid, d in obj_depths.items():
        if oid == target_id:
            continue
        diff = d["mean"] - td["mean"]
        depth_diffs.append(diff)
        if d["mean"] < td["mean"] - 0.5:
            n_in_front += 1
        elif d["mean"] > td["mean"] + 0.5:
            n_behind += 1

    features["n_objects_in_front"] = n_in_front
    features["n_objects_behind"] = n_behind
    features["depth_rank_ratio"] = n_in_front / max(1, num_objects - 1)

    if depth_diffs:
        features["mean_depth_diff"] = float(np.mean(depth_diffs))
        features["std_depth_diff"] = float(np.std(depth_diffs))
        features["min_depth_diff"] = float(np.min(depth_diffs))
        features["max_depth_diff"] = float(np.max(depth_diffs))
    else:
        features["mean_depth_diff"] = 0.0
        features["std_depth_diff"] = 0.0
        features["min_depth_diff"] = 0.0
        features["max_depth_diff"] = 0.0

    # Spatial features
    coords = np.array([(obj_coords[oid][0], obj_coords[oid][1])
                        for oid in obj_depths], dtype=float)
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)
    bbox_area = (x_max - x_min + 1) * (y_max - y_min + 1)
    total_area = depth.shape[0] * depth.shape[1]
    features["scene_bbox_ratio"] = bbox_area / total_area

    tx, ty = obj_coords[target_id]
    dists_to_target = np.sqrt(((coords - np.array([tx, ty])) ** 2).sum(axis=1))
    dists_to_target = dists_to_target[dists_to_target > 0]
    if len(dists_to_target) > 0:
        nearest_dist = float(dists_to_target.min())
        features["target_nearest_dist"] = nearest_dist
        features["target_bbox_ratio"] = (nearest_dist * 2) ** 2 / total_area
    else:
        features["target_nearest_dist"] = 0.0
        features["target_bbox_ratio"] = 0.0

    if len(coords) >= 2:
        diff = coords[:, None, :] - coords[None, :, :]
        dist_matrix = np.sqrt((diff ** 2).sum(axis=-1))
        np.fill_diagonal(dist_matrix, np.inf)
        nn_dists = dist_matrix.min(axis=1)
        image_diag = float(np.hypot(depth.shape[0], depth.shape[1]))
        features["mean_nn_ratio"] = float(np.mean(nn_dists)) / image_diag
        features["median_nn_ratio"] = float(np.median(nn_dists)) / image_diag
    else:
        features["mean_nn_ratio"] = 0.0
        features["median_nn_ratio"] = 0.0

    n_close_and_in_front = 0
    for oid, d in obj_depths.items():
        if oid == target_id:
            continue
        ox, oy = obj_coords[oid]
        spatial_dist = np.sqrt((tx - ox) ** 2 + (ty - oy) ** 2)
        if spatial_dist < 100 and d["mean"] < td["mean"]:
            n_close_and_in_front += 1
    features["n_close_in_front"] = n_close_and_in_front

    return features


def _load_depth_model():
    """Lazy-load the trained depth classifier."""
    global _DEPTH_MODEL, _DEPTH_FEATURE_COLS
    if _DEPTH_MODEL is not None:
        return
    try:
        from joblib import load as joblib_load
        model_path = os.path.join(
            os.path.dirname(__file__), "..", "models", "difficulty_depth_rf_v1.joblib"
        )
        if os.path.exists(model_path):
            _DEPTH_MODEL = joblib_load(model_path)
            _DEPTH_FEATURE_COLS = [
                "num_objects", "n_depth_valid", "target_depth_mean", "target_depth_std",
                "target_depth_range", "scene_depth_mean", "scene_depth_std",
                "target_vs_scene_depth", "n_objects_in_front", "n_objects_behind",
                "depth_rank_ratio", "mean_depth_diff", "std_depth_diff",
                "min_depth_diff", "max_depth_diff", "scene_bbox_ratio",
                "target_nearest_dist", "target_bbox_ratio", "mean_nn_ratio",
                "median_nn_ratio", "n_close_in_front",
            ]
    except Exception:
        _DEPTH_MODEL = None


def route_scene_depth_classifier(parsed_data, scene_number, npz_dir=None, query_target_id=None):
    """Route using the depth-based learned classifier (v2: target-aware).

    Parameters
    ----------
    parsed_data : list of (molmo_id, x, y, gt_id)
    scene_number : int or str
    npz_dir : str, optional
    query_target_id : int or None
        1-indexed target object id from the dataset queryObjId.
        If None, falls back to geometric router with provenance.

    Returns
    -------
    dict route_assessment with provenance
    """
    _load_depth_model()

    route_map_int = {0: "direct", 1: "target_first", 2: "blocker_first"}

    feature_target_valid = False
    fallback_reason = None

    if query_target_id is None:
        fallback_reason = "no_query_target_id"
    else:
        features = extract_depth_route_features(
            parsed_data, int(scene_number), npz_dir=npz_dir,
            query_target_id=query_target_id,
        )
        if features is None:
            fallback_reason = "feature_extraction_failed"
        elif _DEPTH_MODEL is None:
            fallback_reason = "model_not_loaded"
        else:
            feature_target_valid = True

    if feature_target_valid:
        X = np.array([[features.get(c, 0.0) for c in _DEPTH_FEATURE_COLS]], dtype=float)
        pred = int(_DEPTH_MODEL.predict(X)[0])
        route_mode = route_map_int.get(pred, "direct")
    else:
        # Fallback to geometric router
        assessment = route_scene(parsed_data)
        assessment["scene_complexity"]["model"] = "depth_rf_v2_geometric_fallback"
        assessment["scene_complexity"]["fallback_reason"] = fallback_reason
        assessment["scene_complexity"]["query_target_id"] = query_target_id
        assessment["scene_complexity"]["feature_target_valid"] = False
        return assessment

    return {
        "route_mode": route_mode,
        "route_confidence": 1.0,
        "target_object_id": None,
        "target_label": "target",
        "ambiguity_evidence": [],
        "blocker_evidence": [],
        "scene_router_version": "depth-classifier-v2",
        "scene_complexity": {
            "model": "depth_rf_v2",
            "route_mode": route_mode,
            "query_target_id": query_target_id,
            "feature_target_valid": True,
            "fallback_reason": None,
            "num_objects": features.get("num_objects", 0),
            "n_depth_valid": features.get("n_depth_valid", 0),
            "target_vs_scene_depth": features.get("target_vs_scene_depth", 0.0),
            "n_objects_in_front": features.get("n_objects_in_front", 0),
            "depth_rank_ratio": features.get("depth_rank_ratio", 0.0),
            "n_close_in_front": features.get("n_close_in_front", 0),
        },
    }
