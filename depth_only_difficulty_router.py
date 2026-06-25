"""Depth-only feature extractor + RandomForest difficulty classifier.

Uses ONLY depth map + Molmo point coordinates (no GT masks, no SAM).
This is the zero-cost routing approach: depth maps are already in NPZ files.

Features:
- Per-object depth statistics from depth map around each Molmo point
- Pairwise depth ordering (which objects are in front/behind)
- Scene depth distribution features
- Target-specific depth features
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)


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


def extract_depth_features(scene_id, query_obj_id, parsed_data, npz_dir="data/npz_file"):
    """Extract depth-only features from Molmo points + depth map.

    Parameters
    ----------
    scene_id : int
    query_obj_id : int (0-indexed)
    parsed_data : list of (molmo_id, x, y, gt_id) from Molmo cache
    npz_dir : str

    Returns
    -------
    dict of features, or None
    """
    npz_path = os.path.join(npz_dir, f"{scene_id}.npz")
    if not os.path.exists(npz_path):
        return None

    gt = np.load(npz_path, allow_pickle=True)
    depth = gt["depth"]

    target_id = query_obj_id + 1  # 1-indexed
    num_objects = len(parsed_data)

    # Get depth for each object (sample around Molmo point)
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

    if target_id not in obj_depths:
        return None

    features = {}
    features["num_objects"] = num_objects
    features["n_depth_valid"] = len(obj_depths)

    # --- Target depth stats ---
    td = obj_depths[target_id]
    features["target_depth_mean"] = td["mean"]
    features["target_depth_std"] = td["std"]
    features["target_depth_range"] = td["max"] - td["min"]

    # --- Scene depth stats ---
    all_depth_means = [d["mean"] for d in obj_depths.values()]
    scene_depth_mean = float(np.mean(all_depth_means))
    scene_depth_std = float(np.std(all_depth_means))
    features["scene_depth_mean"] = scene_depth_mean
    features["scene_depth_std"] = scene_depth_std
    features["target_vs_scene_depth"] = td["mean"] - scene_depth_mean

    # --- Depth ordering: objects in front/behind target ---
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

    # --- Spatial features (from Molmo point coordinates) ---
    coords = np.array([(obj_coords[oid][0], obj_coords[oid][1])
                        for oid in obj_depths], dtype=float)

    # Bounding box
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)
    bbox_area = (x_max - x_min + 1) * (y_max - y_min + 1)
    total_area = depth.shape[0] * depth.shape[1]
    features["scene_bbox_ratio"] = bbox_area / total_area

    # Target bbox (single point → use distance to nearest as radius)
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

    # Nearest neighbor clustering
    if len(coords) >= 2:
        from scipy.spatial.distance import cdist
        dist_matrix = cdist(coords, coords)
        np.fill_diagonal(dist_matrix, np.inf)
        nn_dists = dist_matrix.min(axis=1)
        image_diag = float(np.hypot(depth.shape[0], depth.shape[1]))
        features["mean_nn_ratio"] = float(np.mean(nn_dists)) / image_diag
        features["median_nn_ratio"] = float(np.median(nn_dists)) / image_diag
    else:
        features["mean_nn_ratio"] = 0.0
        features["median_nn_ratio"] = 0.0

    # --- Depth-based occlusion estimate ---
    # Count how many objects are both spatially close AND in front of target
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


# ---------------------------------------------------------------------------
# Build dataset from Molmo cache + NPZ depth
# ---------------------------------------------------------------------------

def load_molmo_cache(molmo_dir):
    """Load all Molmo caches. Returns dict: scene_name -> list of (molmo_id, x, y, gt_id)."""
    cache = {}
    if not os.path.exists(molmo_dir):
        return cache
    for scene_dir in sorted(os.listdir(molmo_dir)):
        scene_path = os.path.join(molmo_dir, scene_dir)
        if not os.path.isdir(scene_path):
            continue
        scene_name = scene_dir.replace("scene", "")
        id_file = os.path.join(scene_path, f"{scene_name}_id.txt")
        if not os.path.exists(id_file):
            continue
        parsed = []
        with open(id_file) as f:
            next(f, None)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) == 4:
                    molmo_id, x, y, gt_id = parts
                    parsed.append((str(molmo_id), int(x), int(y), str(gt_id)))
        if parsed:
            cache[scene_name] = parsed
    return cache


def build_depth_dataset(molmo_dir="data/output/molmo_output", npz_dir="data/npz_file"):
    """Build feature matrix from Molmo points + depth maps."""
    df1 = pd.read_parquet("data/train-00000-of-00002.parquet")
    df2 = pd.read_parquet("data/train-00001-of-00002.parquet")
    df = pd.concat([df1, df2], ignore_index=True)

    molmo_cache = load_molmo_cache(molmo_dir)
    print(f"Loaded Molmo cache: {len(molmo_cache)} scenes")

    label_map = {"Easy": 0, "Medium": 1, "Hard": 2}
    rows = []
    skipped = 0
    t0 = time.time()

    for idx, row in df.iterrows():
        scene_id = int(row["sceneId"])
        query_obj_id = int(row["queryObjId"])
        difficulty = row["difficulty"]
        split = int(row["split"])
        scene_name = str(scene_id)

        if scene_name not in molmo_cache:
            skipped += 1
            continue

        parsed_data = molmo_cache[scene_name]
        features = extract_depth_features(scene_id, query_obj_id, parsed_data, npz_dir)
        if features is None:
            skipped += 1
            continue

        features["scene_id"] = scene_id
        features["query_obj_id"] = query_obj_id
        features["difficulty"] = difficulty
        features["label"] = label_map[difficulty]
        features["split"] = split
        rows.append(features)

        if (idx + 1) % 100 == 0:
            elapsed = time.time() - t0
            print(f"  Processed {idx+1}/900 ({elapsed:.1f}s, {skipped} skipped)")

    elapsed = time.time() - t0
    print(f"Built dataset: {len(rows)} samples, {skipped} skipped ({elapsed:.1f}s)")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Train + evaluate
# ---------------------------------------------------------------------------

def train_and_evaluate(df):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

    feature_cols = [c for c in df.columns if c not in (
        "scene_id", "query_obj_id", "difficulty", "label", "split"
    )]
    X = df[feature_cols].values
    y = df["label"].values.astype(int)

    print(f"\nFeatures ({len(feature_cols)}): {feature_cols}")
    print(f"X shape: {X.shape}")

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_accs = []
    fold_preds = np.full(len(y), -1, dtype=int)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        model = RandomForestClassifier(
            n_estimators=300, max_depth=10,
            min_samples_leaf=2, random_state=42, n_jobs=-1
        )
        model.fit(X_train, y_train)
        preds = model.predict(X_val)
        acc = accuracy_score(y_val, preds)
        fold_accs.append(acc)
        fold_preds[val_idx] = preds
        print(f"  Fold {fold+1}: acc={acc:.4f} (n_val={len(val_idx)})")

    overall_acc = accuracy_score(y, fold_preds)
    print(f"\n{'='*60}")
    print(f"5-fold CV accuracy: {overall_acc:.4f}")
    print(f"Per-fold: {[f'{a:.4f}' for a in fold_accs]}")
    print(f"{'='*60}")

    for diff_name, diff_id in [("Easy", 0), ("Medium", 1), ("Hard", 2)]:
        mask = y == diff_id
        if mask.sum() > 0:
            diff_acc = accuracy_score(y[mask], fold_preds[mask])
            print(f"  {diff_name}: {diff_acc:.4f} ({mask.sum()} samples)")

    print("\nConfusion matrix (rows=true, cols=pred):")
    cm = confusion_matrix(y, fold_preds)
    for i, name in enumerate(["Easy", "Medium", "Hard"]):
        print(f"  {name}: {cm[i]}")

    print("\nClassification report:")
    print(classification_report(y, fold_preds, target_names=["Easy", "Medium", "Hard"]))

    # Final model
    final_model = RandomForestClassifier(
        n_estimators=300, max_depth=10,
        min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    final_model.fit(X, y)

    importances = final_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("Top 10 feature importances:")
    for i in sorted_idx[:10]:
        print(f"  {feature_cols[i]}: {importances[i]:.4f}")

    return final_model, feature_cols, overall_acc


if __name__ == "__main__":
    print("=" * 60)
    print("Depth-Only Difficulty Router - Phase 2 Validation")
    print("=" * 60)

    df = build_depth_dataset()
    df.to_csv("data/depth_difficulty_features.csv", index=False)
    print(f"\nSaved features to data/depth_difficulty_features.csv")

    model, feature_cols, acc = train_and_evaluate(df)

    from joblib import dump
    dump(model, "models/difficulty_depth_rf_v1.joblib")
    print(f"\nSaved model to models/difficulty_depth_rf_v1.joblib")

    # Build route lookup
    route_map = {0: "direct", 1: "target_first", 2: "blocker_first"}
    feature_cols_list = [c for c in df.columns if c not in (
        "scene_id", "query_obj_id", "difficulty", "label", "split"
    )]
    X = df[feature_cols_list].values
    preds = model.predict(X)
    lookup = {}
    for i, row in df.iterrows():
        scene_id = str(int(row["scene_id"]))
        predicted_route = route_map[preds[i]]
        if scene_id not in lookup:
            lookup[scene_id] = predicted_route
        else:
            order = {"direct": 0, "target_first": 1, "blocker_first": 2}
            if order[predicted_route] > order[lookup[scene_id]]:
                lookup[scene_id] = predicted_route
    with open("data/scene_route_depth_lookup.json", "w") as f:
        json.dump(lookup, f, indent=2)
    print(f"Saved route lookup ({len(lookup)} scenes)")

    print(f"\n{'='*60}")
    print(f"RESULT: Depth-only oracle match rate = {acc:.2%}")
    print(f"{'='*60}")
