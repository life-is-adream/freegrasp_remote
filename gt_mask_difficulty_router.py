"""GT-mask occlusion feature extractor + RandomForest difficulty classifier.

Fast version: uses bbox overlap + depth instead of pixel-level IoU.
Validates that GT mask features can predict difficulty at 90%+ oracle match.
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Fast feature extraction from GT NPZ
# ---------------------------------------------------------------------------

def _bbox_of_mask(mask):
    """Return (y_min, x_min, y_max, x_max) of a boolean mask, or None."""
    coords = np.argwhere(mask)
    if len(coords) == 0:
        return None
    return (int(coords[:, 0].min()), int(coords[:, 1].min()),
            int(coords[:, 0].max()), int(coords[:, 1].max()))


def _bbox_iou(a, b):
    """IoU of two (y0,x0,y1,x1) bboxes."""
    y0 = max(a[0], b[0]); x0 = max(a[1], b[1])
    y1 = min(a[2], b[2]); x1 = min(a[3], b[3])
    inter = max(0, y1 - y0 + 1) * max(0, x1 - x0 + 1)
    area_a = (a[2] - a[0] + 1) * (a[3] - a[1] + 1)
    area_b = (b[2] - b[0] + 1) * (b[3] - b[1] + 1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def extract_gt_features(scene_id, query_obj_id, npz_dir="data/npz_file"):
    """Extract occlusion features from GT NPZ (fast bbox-based version)."""
    npz_path = os.path.join(npz_dir, f"{scene_id}.npz")
    if not os.path.exists(npz_path):
        return None

    gt = np.load(npz_path, allow_pickle=True)
    instances = gt["instances_objects"].astype(int)
    depth = gt["depth"]
    occ_obj = gt["occlusion_objects"]  # (N_objects, H, W)
    sem = gt["instances_semantic"].astype(int)

    target_id = query_obj_id + 1  # 1-indexed
    all_ids = [i for i in np.unique(instances) if i > 0]
    num_objects = len(all_ids)

    # --- Target mask ---
    target_mask = (instances == target_id)
    target_pixels = int(target_mask.sum())
    if target_pixels == 0:
        return None

    features = {}
    features["num_objects"] = num_objects
    features["target_pixels"] = target_pixels

    # --- Target depth stats ---
    target_depth = depth[target_mask]
    target_depth_mean = float(target_depth.mean())
    features["target_depth_mean"] = target_depth_mean
    features["target_depth_std"] = float(target_depth.std())
    features["target_depth_median"] = float(np.median(target_depth))

    # --- Scene depth stats ---
    all_obj_mask = instances > 0
    scene_depth_mean = float(depth[all_obj_mask].mean())
    features["scene_depth_mean"] = scene_depth_mean
    features["target_vs_scene_depth"] = target_depth_mean - scene_depth_mean

    # --- Objects in front of target (by depth) ---
    n_in_front = 0
    for oid in all_ids:
        if oid == target_id:
            continue
        oid_mask = (instances == oid)
        oid_depth_mean = float(depth[oid_mask].mean())
        if oid_depth_mean < target_depth_mean:
            n_in_front += 1
    features["n_objects_in_front"] = n_in_front
    features["depth_rank_ratio"] = n_in_front / max(1, num_objects - 1)

    # --- Occlusion mask features (fast: use occ_obj directly) ---
    # occ_obj[i] = occlusion mask for instance (i+1)
    target_id_idx = target_id - 1
    if target_id_idx < occ_obj.shape[0]:
        target_occl = occ_obj[target_id_idx] > 0.5
        features["target_self_occl_pixels"] = int((target_occl & target_mask).sum())
        features["target_self_occl_ratio"] = features["target_self_occl_pixels"] / target_pixels
    else:
        features["target_self_occl_pixels"] = 0
        features["target_self_occl_ratio"] = 0.0

    # --- Target visibility (union of all occlusion masks intersected with target) ---
    all_occluded = np.zeros_like(target_mask, dtype=bool)
    for i in range(min(occ_obj.shape[0], num_objects)):
        all_occluded |= (occ_obj[i] > 0.5)
    occluded_on_target = int((all_occluded & target_mask).sum())
    features["target_visibility"] = 1.0 - occluded_on_target / target_pixels

    # --- Bounding boxes for all objects (fast) ---
    bboxes = {}
    for oid in all_ids:
        mask = (instances == oid)
        bb = _bbox_of_mask(mask)
        if bb is not None:
            bboxes[oid] = bb

    # --- Pairwise bbox IoU (fast) ---
    max_iou = 0.0
    total_iou = 0.0
    n_pairs = 0
    n_overlap_pairs = 0
    target_iou_max = 0.0
    target_iou_sum = 0.0
    n_target_overlaps = 0

    for a, b in zip(all_ids[:-1], all_ids[1:]):
        if a not in bboxes or b not in bboxes:
            continue
        iou = _bbox_iou(bboxes[a], bboxes[b])
        n_pairs += 1
        total_iou += iou
        if iou > max_iou:
            max_iou = iou
        if iou > 0.01:
            n_overlap_pairs += 1
        # Target-specific overlap
        if a == target_id or b == target_id:
            if iou > target_iou_max:
                target_iou_max = iou
            target_iou_sum += iou
            if iou > 0.01:
                n_target_overlaps += 1

    features["max_bbox_iou"] = max_iou
    features["mean_bbox_iou"] = total_iou / max(1, n_pairs)
    features["n_overlap_pairs"] = n_overlap_pairs
    features["target_max_bbox_iou"] = target_iou_max
    features["target_n_overlaps"] = n_target_overlaps

    # --- Scene bounding box ratio ---
    if bboxes:
        all_y0 = min(bb[0] for bb in bboxes.values())
        all_x0 = min(bb[1] for bb in bboxes.values())
        all_y1 = max(bb[2] for bb in bboxes.values())
        all_x1 = max(bb[3] for bb in bboxes.values())
        scene_area = (all_y1 - all_y0 + 1) * (all_x1 - all_x0 + 1)
        total_area = instances.shape[0] * instances.shape[1]
        features["scene_bbox_ratio"] = scene_area / total_area
    else:
        features["scene_bbox_ratio"] = 0.0

    # --- Target bbox ratio ---
    if target_id in bboxes:
        tb = bboxes[target_id]
        target_area = (tb[2] - tb[0] + 1) * (tb[3] - tb[1] + 1)
        features["target_bbox_ratio"] = target_area / (instances.shape[0] * instances.shape[1])
    else:
        features["target_bbox_ratio"] = 0.0

    # --- Same-class count ---
    target_sem = int(sem[target_mask].min()) if target_mask.any() else 0
    same_class = sum(
        1 for oid in all_ids
        if oid != target_id and int(sem[(instances == oid)].min()) == target_sem
        if (instances == oid).any()
    )
    features["same_class_count"] = same_class

    # --- BFS hop distance (fast, using bbox IoU > 0.01 as edges) ---
    overlap_adj = {i: [] for i in range(num_objects)}
    id_to_idx = {oid: i for i, oid in enumerate(all_ids)}
    for a, b in zip(all_ids[:-1], all_ids[1:]):
        if a in bboxes and b in bboxes:
            iou = _bbox_iou(bboxes[a], bboxes[b])
            if iou > 0.01:
                overlap_adj[id_to_idx[a]].append(id_to_idx[b])
                overlap_adj[id_to_idx[b]].append(id_to_idx[a])

    if target_id in id_to_idx:
        t_idx = id_to_idx[target_id]
        visited = {t_idx}
        queue = [t_idx]
        hops = {t_idx: 0}
        while queue:
            curr = queue.pop(0)
            for nb in overlap_adj[curr]:
                if nb not in visited:
                    visited.add(nb)
                    hops[nb] = hops[curr] + 1
                    queue.append(nb)
        hop_vals = list(hops.values())
        features["max_hop"] = max(hop_vals) if hop_vals else 0
        features["mean_hop"] = float(np.mean(hop_vals)) if hop_vals else 0.0
        features["n_connected"] = len(hops) - 1
    else:
        features["max_hop"] = 0
        features["mean_hop"] = 0.0
        features["n_connected"] = 0

    return features


# ---------------------------------------------------------------------------
# Build dataset
# ---------------------------------------------------------------------------

def build_dataset(npz_dir="data/npz_file"):
    """Build feature matrix + labels from parquet + NPZ."""
    df1 = pd.read_parquet("data/train-00000-of-00002.parquet")
    df2 = pd.read_parquet("data/train-00001-of-00002.parquet")
    df = pd.concat([df1, df2], ignore_index=True)

    label_map = {"Easy": 0, "Medium": 1, "Hard": 2}

    rows = []
    skipped = 0
    t0 = time.time()

    for idx, row in df.iterrows():
        scene_id = int(row["sceneId"])
        query_obj_id = int(row["queryObjId"])
        difficulty = row["difficulty"]
        split = int(row["split"])

        features = extract_gt_features(scene_id, query_obj_id, npz_dir)
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
# Train + evaluate RandomForest
# ---------------------------------------------------------------------------

def train_and_evaluate(df):
    """Train RandomForest and evaluate with 5-fold CV."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, confusion_matrix

    feature_cols = [c for c in df.columns if c not in (
        "scene_id", "query_obj_id", "difficulty", "label", "split"
    )]
    X = df[feature_cols].values
    y = df["label"].values

    print(f"\nFeatures ({len(feature_cols)}): {feature_cols}")
    print(f"X shape: {X.shape}")

    # --- 5-fold CV ---
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
    print(f"\n5-fold CV accuracy: {overall_acc:.4f}")
    print(f"Per-fold: {[f'{a:.4f}' for a in fold_accs]}")

    # Per-difficulty accuracy
    for diff_name, diff_id in [("Easy", 0), ("Medium", 1), ("Hard", 2)]:
        mask = y == diff_id
        if mask.sum() > 0:
            diff_acc = accuracy_score(y[mask], fold_preds[mask])
            print(f"  {diff_name}: {diff_acc:.4f} ({mask.sum()} samples)")

    # Confusion matrix
    print("\nConfusion matrix (rows=true, cols=pred):")
    cm = confusion_matrix(y, fold_preds)
    for i, name in enumerate(["Easy", "Medium", "Hard"]):
        print(f"  {name}: {cm[i]}")

    # --- Final model on all data ---
    final_model = RandomForestClassifier(
        n_estimators=300, max_depth=10,
        min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    final_model.fit(X, y)

    # Feature importance
    importances = final_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\nTop 10 feature importances:")
    for i in sorted_idx[:10]:
        print(f"  {feature_cols[i]}: {importances[i]:.4f}")

    return final_model, feature_cols, overall_acc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("GT Mask Difficulty Router - Phase 1 Validation")
    print("=" * 60)

    # Build dataset
    df = build_dataset()

    # Save dataset
    df.to_csv("data/gt_difficulty_features.csv", index=False)
    print(f"\nSaved features to data/gt_difficulty_features.csv")

    # Train + evaluate
    model, feature_cols, acc = train_and_evaluate(df)

    # Save model
    from joblib import dump
    dump(model, "models/difficulty_rf_v1.joblib")
    print(f"\nSaved model to models/difficulty_rf_v1.joblib")

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
    with open("data/scene_route_lookup.json", "w") as f:
        json.dump(lookup, f, indent=2)
    print(f"Saved route lookup ({len(lookup)} scenes) to data/scene_route_lookup.json")

    print("\n" + "=" * 60)
    print(f"RESULT: GT-mask oracle match rate = {acc:.2%}")
    print("=" * 60)
