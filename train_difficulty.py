"""Quick training script - reads pre-extracted GT features CSV."""
import json
import sys
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from joblib import dump

csv_path = "data/gt_difficulty_features.csv"
if not os.path.exists(csv_path):
    print(f"ERROR: {csv_path} not found. Run gt_mask_difficulty_router.py first.")
    sys.exit(1)

df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} samples from {csv_path}")

# Prepare X, y
feature_cols = [c for c in df.columns if c not in (
    "scene_id", "query_obj_id", "difficulty", "label", "split"
)]
X = df[feature_cols].values
y = df["label"].values.astype(int)
print(f"Features: {len(feature_cols)} columns")
print(f"Label distribution: Easy={sum(y==0)}, Medium={sum(y==1)}, Hard={sum(y==2)}")

# 5-fold CV
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

# Classification report
print("\nClassification report:")
print(classification_report(y, fold_preds, target_names=["Easy", "Medium", "Hard"]))

# Final model on all data
final_model = RandomForestClassifier(
    n_estimators=300, max_depth=10,
    min_samples_leaf=2, random_state=42, n_jobs=-1
)
final_model.fit(X, y)

# Feature importance
importances = final_model.feature_importances_
sorted_idx = np.argsort(importances)[::-1]
print("Top 10 feature importances:")
for i in sorted_idx[:10]:
    print(f"  {feature_cols[i]}: {importances[i]:.4f}")

# Save model
dump(final_model, "models/difficulty_rf_v1.joblib")
print(f"\nSaved model to models/difficulty_rf_v1.joblib")

# Build scene route lookup
route_map = {0: "direct", 1: "target_first", 2: "blocker_first"}
preds_all = final_model.predict(X)
lookup = {}
for i, row in df.iterrows():
    scene_id = str(int(row["scene_id"]))
    predicted_route = route_map[preds_all[i]]
    if scene_id not in lookup:
        lookup[scene_id] = predicted_route
    else:
        order = {"direct": 0, "target_first": 1, "blocker_first": 2}
        if order[predicted_route] > order[lookup[scene_id]]:
            lookup[scene_id] = predicted_route
with open("data/scene_route_lookup.json", "w") as f:
    json.dump(lookup, f, indent=2)
print(f"Saved route lookup ({len(lookup)} scenes) to data/scene_route_lookup.json")

# Scene-level accuracy (oracle match on scenes)
scene_true = df.groupby("scene_id")["label"].first().values
scene_preds = []
for scene_id in df["scene_id"].unique():
    scene_rows = df[df["scene_id"] == scene_id]
    scene_X = scene_rows[feature_cols].values
    scene_pred_routes = final_model.predict(scene_X)
    order = {"direct": 0, "target_first": 1, "blocker_first": 2}
    route_pred = route_map[max(scene_pred_routes, key=lambda r: order[route_map[r]] if isinstance(r, int) else order[r])]
    scene_preds.append(lookup[str(int(scene_id))])

scene_preds_ids = [order.get(r, 0) for r in scene_preds]
scene_acc = accuracy_score(scene_true, scene_preds_ids)
print(f"\nScene-level accuracy: {scene_acc:.4f}")

print(f"\n{'='*60}")
print(f"RESULT: GT-mask RF oracle match rate = {overall_acc:.2%}")
print(f"RESULT: Scene-level oracle match rate = {scene_acc:.2%}")
print(f"{'='*60}")
