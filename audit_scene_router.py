"""Offline audit of scene_complexity router against oracle difficulty labels.

No paid MiMo calls.  Reads Molmo cache + dataset parquet to compute
what the router *would* have decided for every one of the 900 samples,
then compares against the oracle protocol assignment.

Usage:
    python audit_scene_router.py
    python audit_scene_router.py --molmo-root data/output/molmo_output
    python audit_scene_router.py --tune   # grid-search thresholds
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from utils.scene_router import (
    CLUSTER_HIGH_MAX,
    CLUSTER_LOW_MIN,
    COUNT_HIGH_MIN,
    COUNT_LOW_MAX,
    EXTENT_HIGH_MIN,
    EXTENT_LOW_MAX,
    SCORE_HARD_CEIL,
    SCORE_MEDIUM_CEIL,
    SceneComplexityFeatures,
    compute_scene_features,
)

PARQUET_FILES = [
    "data/train-00000-of-00002.parquet",
    "data/train-00001-of-00002.parquet",
]
DEFAULT_MOLMO_ROOT = "data/output/molmo_output"
NPZ_DIR = "data/npz_file"

DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]
ORACLE_ROUTE = {"Easy": "direct", "Medium": "target_first", "Hard": "blocker_first"}


def _parse_id_file(path):
    """Parse a Molmo id.txt file → list of (molmo_id, x, y, gt_id)."""
    parsed = []
    with open(path) as fh:
        next(fh)  # skip header
        for line in fh:
            parts = line.split()
            if len(parts) == 4:
                parsed.append(tuple(int(p) for p in parts))
    return parsed


def _load_dataset():
    return pd.concat([pd.read_parquet(p) for p in PARQUET_FILES])


def _image_shape_for_scene(scene_id, npz_dir):
    npz_path = os.path.join(npz_dir, f"{scene_id}.npz")
    if not os.path.exists(npz_path):
        return None
    gt = np.load(npz_path, allow_pickle=True)
    masks = gt["instances_objects.npy"] if "instances_objects.npy" in gt else gt["instances_objects"]
    if masks.ndim == 3:
        return (masks.shape[1], masks.shape[2])
    return (masks.shape[0], masks.shape[1])


def audit(molmo_root, npz_dir=NPZ_DIR, threshold_overrides=None):
    """Run the offline audit.  Returns a dict with per-sample and aggregate results."""
    molmo_root = Path(molmo_root)
    df = _load_dataset()

    if threshold_overrides:
        _apply_threshold_overrides(threshold_overrides)

    rows = []
    for _, sample in df.iterrows():
        scene_id = int(sample["sceneId"])
        difficulty = sample["difficulty"]
        ambiguous = sample["ambiguious"]
        split = str(sample["split"])
        subset = f"{difficulty.lower()}_{'yes' if ambiguous else 'no'}_ambi"

        id_file = molmo_root / f"scene{scene_id}" / f"{scene_id}_id.txt"
        if not id_file.exists():
            continue
        parsed_data = _parse_id_file(id_file)
        image_shape = _image_shape_for_scene(scene_id, npz_dir)

        features = compute_scene_features(parsed_data, image_shape=image_shape)
        oracle_route = ORACLE_ROUTE[difficulty]
        route_match = features.route_mode == oracle_route

        rows.append({
            "scene_id": scene_id,
            "split": split,
            "subset": subset,
            "difficulty": difficulty,
            "ambiguous": ambiguous,
            "oracle_route": oracle_route,
            "predicted_route": features.route_mode,
            "route_match": route_match,
            "object_count": features.object_count,
            "median_nn_dist": features.median_nn_dist,
            "nn_cluster_ratio": features.nn_cluster_ratio,
            "spatial_extent": features.spatial_extent,
            "composite_score": features.composite_score,
            "density_score": features.density_score,
            "cluster_score": features.cluster_score,
            "extent_score": features.extent_score,
        })

    _reset_thresholds()
    result_df = pd.DataFrame(rows)
    return _build_report(result_df)


def _build_report(result_df):
    total = len(result_df)
    overall_match = result_df["route_match"].mean()

    per_difficulty = {}
    for diff in DIFFICULTY_ORDER:
        sub = result_df[result_df["difficulty"] == diff]
        per_difficulty[diff] = {
            "n": len(sub),
            "match_rate": round(sub["route_match"].mean(), 4) if len(sub) else 0,
            "route_distribution": dict(Counter(sub["predicted_route"])),
        }

    confusion = defaultdict(lambda: defaultdict(int))
    for _, row in result_df.iterrows():
        confusion[row["oracle_route"]][row["predicted_route"]] += 1

    per_subset = {}
    for subset_name, sub in result_df.groupby("subset"):
        per_subset[subset_name] = {
            "n": len(sub),
            "match_rate": round(sub["route_match"].mean(), 4),
            "route_distribution": dict(Counter(sub["predicted_route"])),
        }

    score_stats = {
        "mean": round(result_df["composite_score"].mean(), 4),
        "median": round(result_df["composite_score"].median(), 4),
        "std": round(result_df["composite_score"].std(), 4),
        "min": round(result_df["composite_score"].min(), 4),
        "max": round(result_df["composite_score"].max(), 4),
    }

    return {
        "total_samples": total,
        "overall_match_rate": round(overall_match, 4),
        "overall_match_pct": f"{overall_match * 100:.1f}%",
        "per_difficulty": per_difficulty,
        "per_subset": per_subset,
        "confusion_matrix": {
            oracle: dict(predicted)
            for oracle, predicted in confusion.items()
        },
        "composite_score_stats": score_stats,
        "object_count_stats": {
            "mean": round(result_df["object_count"].mean(), 2),
            "median": round(result_df["object_count"].median(), 1),
        },
    }


def _apply_threshold_overrides(overrides):
    """Temporarily override module-level threshold constants."""
    import utils.scene_router as sr
    for key, value in overrides.items():
        if hasattr(sr, key):
            setattr(sr, key, value)


def _reset_thresholds():
    """Restore defaults after override (re-import resets)."""
    import importlib
    import utils.scene_router as sr
    importlib.reload(sr)


def tune_thresholds(molmo_root, npz_dir=NPZ_DIR):
    """Grid-search threshold combinations and report the best match rate."""
    import utils.scene_router as sr

    best_rate = 0
    best_config = {}
    results = []

    density_options = [(4, 8), (5, 9), (5, 10), (6, 10), (6, 12)]
    cluster_options = [(0.06, 0.02), (0.08, 0.03), (0.10, 0.04), (0.08, 0.02)]
    extent_options = [(0.40, 0.70), (0.50, 0.80), (0.45, 0.75)]
    score_options = [(0.8, 1.6), (1.0, 1.8), (1.0, 2.0), (1.2, 2.2), (0.8, 1.8)]

    for d_low, d_high in density_options:
        for c_low, c_high in cluster_options:
            for e_low, e_high in extent_options:
                for sc_med, sc_hard in score_options:
                    overrides = {
                        "COUNT_LOW_MAX": d_low,
                        "COUNT_HIGH_MIN": d_high,
                        "CLUSTER_LOW_MIN": c_low,
                        "CLUSTER_HIGH_MAX": c_high,
                        "EXTENT_LOW_MAX": e_low,
                        "EXTENT_HIGH_MIN": e_high,
                        "SCORE_MEDIUM_CEIL": sc_med,
                        "SCORE_HARD_CEIL": sc_hard,
                    }
                    report = audit(molmo_root, npz_dir, threshold_overrides=overrides)
                    rate = report["overall_match_rate"]
                    entry = {**overrides, "match_rate": rate}
                    results.append(entry)
                    if rate > best_rate:
                        best_rate = rate
                        best_config = overrides.copy()

    results.sort(key=lambda r: -r["match_rate"])
    return {
        "best_match_rate": round(best_rate, 4),
        "best_config": best_config,
        "top_10": results[:10],
        "total_configs_tested": len(results),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--molmo-root", default=DEFAULT_MOLMO_ROOT)
    parser.add_argument("--npz-dir", default=NPZ_DIR)
    parser.add_argument("--tune", action="store_true", help="Grid-search thresholds")
    parser.add_argument("--output", default=None, help="Write JSON report to this path")
    args = parser.parse_args(argv)

    if args.tune:
        print("Grid-searching threshold combinations...")
        result = tune_thresholds(args.molmo_root, args.npz_dir)
        print(f"\nBest match rate: {result['best_match_rate'] * 100:.1f}%")
        print(f"Best config: {json.dumps(result['best_config'], indent=2)}")
        print(f"\nTop 10 configs:")
        for i, entry in enumerate(result["top_10"]):
            print(f"  {i+1}. match={entry['match_rate']*100:.1f}%")
    else:
        report = audit(args.molmo_root, args.npz_dir)
        print(f"\n{'='*60}")
        print(f"Scene Router Offline Audit")
        print(f"{'='*60}")
        print(f"Total samples: {report['total_samples']}")
        print(f"Overall match rate: {report['overall_match_pct']}")
        print(f"\nPer difficulty:")
        for diff in DIFFICULTY_ORDER:
            info = report["per_difficulty"][diff]
            dist = info["route_distribution"]
            print(f"  {diff:8s}: match={info['match_rate']*100:.1f}% (n={info['n']}) "
                  f"→ direct={dist.get('direct',0)}, "
                  f"target_first={dist.get('target_first',0)}, "
                  f"blocker_first={dist.get('blocker_first',0)}")
        print(f"\nConfusion matrix (rows=oracle, cols=predicted):")
        for oracle in ["direct", "target_first", "blocker_first"]:
            pred = report["confusion_matrix"].get(oracle, {})
            print(f"  {oracle:15s}: direct={pred.get('direct',0):4d}, "
                  f"target_first={pred.get('target_first',0):4d}, "
                  f"blocker_first={pred.get('blocker_first',0):4d}")
        print(f"\nComposite score stats: {json.dumps(report['composite_score_stats'], indent=2)}")
        print(f"Object count: mean={report['object_count_stats']['mean']}, "
              f"median={report['object_count_stats']['median']}")

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    main()
