"""Train outcome policy selector from replay table.

Learns: (sample_features, candidate_protocol) -> P(RSR success)
At inference: score all 3 protocols, pick best. If uncertain, use blocker_first.
"""

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV
from joblib import dump

warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROTOCOLS = ["direct", "target_first", "blocker_first"]
PROTOCOL_INT = {p: i for i, p in enumerate(PROTOCOLS)}


def prepare_training_data(df):
    """Prepare (features, protocol, success) tuples for training.

    Each row in the replay table becomes one training example:
    - Features: query-conditioned depth features
    - Protocol: which protocol was used (as integer)
    - Label: RSR success (0 or 1)
    """
    feature_cols = [c for c in df.columns if c not in (
        "sample_key", "scene_id", "query_object_id", "annotation", "subset",
        "protocol_source_run", "rsr_success", "ssr_success",
        "routing_variant", "route_mode", "feature_target_valid",
    )]

    # Filter to rows with valid features
    valid_df = df[df["feature_target_valid"] == True].copy()
    print(f"  Valid rows: {len(valid_df)}/{len(df)} ({len(valid_df)/len(df)*100:.1f}%)")

    # Encode protocol
    valid_df["protocol_int"] = valid_df["route_mode"].map(PROTOCOL_INT)
    # Some rows may not have route_mode; try to infer from protocol_source_run
    mask_missing = valid_df["protocol_int"].isna()
    if mask_missing.any():
        print(f"  WARNING: {mask_missing.sum()} rows missing route_mode, filling with direct")
        valid_df.loc[mask_missing, "protocol_int"] = 0

    X = valid_df[feature_cols].values.astype(float)
    y = valid_df["rsr_success"].values.astype(int)
    protocol = valid_df["protocol_int"].values.astype(int)
    groups = valid_df["scene_id"].values

    # Add protocol as a one-hot feature
    protocol_onehot = np.zeros((len(protocol), 3))
    protocol_onehot[np.arange(len(protocol)), protocol] = 1
    X_with_protocol = np.hstack([X, protocol_onehot])

    print(f"  Feature columns: {len(feature_cols)} + 3 protocol one-hot = {X_with_protocol.shape[1]}")
    print(f"  Positive rate (RSR success): {y.mean():.4f}")

    return X_with_protocol, y, groups, feature_cols, valid_df


def train_scene_grouped_cv(X, y, groups, n_splits=5):
    """Scene-grouped cross-validation."""
    gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
    fold_aucs = []
    fold_preds = np.full(len(y), -1, dtype=int)
    fold_probs = np.full(len(y), 0.0)

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
        model = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            random_state=42
        )
        model.fit(X[train_idx], y[train_idx])
        probs = model.predict_proba(X[val_idx])[:, 1]
        preds = (probs > 0.5).astype(int)
        fold_preds[val_idx] = preds
        fold_probs[val_idx] = probs

        try:
            auc = roc_auc_score(y[val_idx], probs)
        except ValueError:
            auc = 0.5
        fold_aucs.append(auc)
        acc = accuracy_score(y[val_idx], preds)
        print(f"    Fold {fold+1}: AUC={auc:.4f}, Acc={acc:.4f} (n_val={len(val_idx)})")

    overall_auc = roc_auc_score(y, fold_probs)
    overall_acc = accuracy_score(y, fold_preds)
    print(f"  Scene-grouped CV: AUC={overall_auc:.4f}, Acc={overall_acc:.4f}")
    return overall_auc, fold_probs


def train_row_random_cv(X, y, n_splits=5):
    """Row-random cross-validation (diagnostic only)."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    fold_probs = np.full(len(y), 0.0)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        model = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            random_state=42
        )
        model.fit(X[train_idx], y[train_idx])
        probs = model.predict_proba(X[val_idx])[:, 1]
        fold_probs[val_idx] = probs

    overall_auc = roc_auc_score(y, fold_probs)
    print(f"  Row-random CV AUC: {overall_auc:.4f} (diagnostic only)")
    return overall_auc, fold_probs


def simulate_selection(valid_df, fold_probs, groups):
    """Simulate protocol selection and compute replay RSR."""
    valid_df = valid_df.copy()
    valid_df["success_prob"] = fold_probs

    # For each sample, the selector picks the protocol with highest success prob
    # But we only have ONE observation per (sample, run), not all 3 protocols
    # So we simulate: for each sample, look at all runs and pick the best protocol

    sample_results = {}
    for _, row in valid_df.iterrows():
        key = row["sample_key"]
        if key not in sample_results:
            sample_results[key] = []
        sample_results[key].append({
            "route_mode": row["route_mode"],
            "rsr_success": row["rsr_success"],
            "success_prob": row["success_prob"],
            "protocol_source_run": row["protocol_source_run"],
        })

    # For each sample, find the best protocol from available data
    selected_rsr = []
    oracle_rsr = []
    for key, observations in sample_results.items():
        # Oracle: pick the protocol that actually succeeded (if any)
        oracle_success = max(obs["rsr_success"] for obs in observations)
        oracle_rsr.append(oracle_success)

        # Selector: pick the protocol with highest predicted success prob
        # Group by route_mode and average the predicted probs
        protocol_probs = {}
        protocol_success = {}
        for obs in observations:
            pm = obs["route_mode"]
            if pm not in protocol_probs:
                protocol_probs[pm] = []
                protocol_success[pm] = []
            protocol_probs[pm].append(obs["success_prob"])
            protocol_success[pm].append(obs["rsr_success"])

        # Average prob per protocol
        avg_probs = {pm: np.mean(probs) for pm, probs in protocol_probs.items()}
        best_protocol = max(avg_probs, key=avg_probs.get)
        best_prob = avg_probs[best_protocol]

        # Use the actual success rate for that protocol
        if best_prob < 0.55:
            # Uncertain: fallback to blocker_first
            if "blocker_first" in protocol_success:
                selected_rsr.append(np.mean(protocol_success["blocker_first"]))
            else:
                selected_rsr.append(0.0)
        else:
            selected_rsr.append(np.mean(protocol_success[best_protocol]))

    selected_rsr = np.array(selected_rsr)
    oracle_rsr = np.array(oracle_rsr)

    return selected_rsr.mean(), oracle_rsr.mean(), selected_rsr, oracle_rsr


def main():
    parser = argparse.ArgumentParser(description="Train outcome policy selector")
    parser.add_argument("--replay-table", default="data/output/outcome_policy_selector_v1/replay_table.csv")
    parser.add_argument("--model-output", default="models/outcome_policy_selector_v1.joblib")
    parser.add_argument("--audit-output", default="data/output/outcome_policy_selector_v1/offline_audit.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.model_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.audit_output), exist_ok=True)

    print("=" * 70)
    print("Training Outcome Policy Selector V1")
    print("=" * 70)

    # Load replay table
    print(f"\n[1/5] Loading replay table...")
    df = pd.read_csv(args.replay_table)
    print(f"  Loaded {len(df)} rows")

    # Prepare training data
    print(f"\n[2/5] Preparing training data...")
    X, y, groups, feature_cols, valid_df = prepare_training_data(df)

    # Row-random CV (diagnostic)
    print(f"\n[3/5] Row-random 5-fold CV (diagnostic)...")
    row_random_auc, _ = train_row_random_cv(X, y)

    # Scene-grouped CV (primary)
    print(f"\n[4/5] Scene-grouped CV (primary no-leak metric)...")
    scene_grouped_auc, fold_probs = train_scene_grouped_cv(X, y, groups)

    # Simulate selection
    print(f"\n[5/5] Simulating protocol selection...")
    selected_rsr, oracle_rsr, _, _ = simulate_selection(valid_df, fold_probs, groups)
    regret = oracle_rsr - selected_rsr
    print(f"  Selected replay RSR: {selected_rsr:.4f}")
    print(f"  Oracle replay RSR: {oracle_rsr:.4f}")
    print(f"  Oracle regret: {regret:.4f}")

    # Train final model
    print(f"\nTraining final model on all data...")
    from sklearn.calibration import CalibratedClassifierCV
    base_model = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        random_state=42
    )
    base_model.fit(X, y)
    final_model = CalibratedClassifierCV(base_model, cv=3)
    final_model.fit(X, y)

    dump(final_model, args.model_output)
    print(f"  Saved model to {args.model_output}")

    # Feature importance (from base model)
    importances = base_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    all_cols = feature_cols + ["protocol_direct", "protocol_target_first", "protocol_blocker_first"]
    print(f"\n  Top 10 feature importances:")
    for i in sorted_idx[:10]:
        print(f"    {all_cols[i]}: {importances[i]:.4f}")

    # Save audit
    audit = {
        "row_random_auc": row_random_auc,
        "scene_grouped_auc": scene_grouped_auc,
        "selected_replay_rsr": selected_rsr,
        "oracle_replay_rsr": oracle_rsr,
        "oracle_regret": regret,
        "n_samples": len(valid_df),
        "n_unique_samples": valid_df["sample_key"].nunique(),
    }
    with open(args.audit_output, "w") as f:
        json.dump(audit, f, indent=2)
    print(f"\n  Audit saved to {args.audit_output}")

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"  Row-random AUC:       {row_random_auc:.4f}")
    print(f"  Scene-grouped AUC:    {scene_grouped_auc:.4f}")
    print(f"  Selected replay RSR:  {selected_rsr:.4f}")
    print(f"  Oracle replay RSR:    {oracle_rsr:.4f}")
    print(f"  Oracle regret:        {regret:.4f}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
