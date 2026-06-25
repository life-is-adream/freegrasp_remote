"""Build replay table from existing experiment outputs.

Each row: (sample_key, scene_id, query_object_id, annotation,
            candidate_protocol, protocol_source_run, rsr_success, ssr_success,
            features)

Read-only offline step. Never calls MiMo.
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.scene_router import extract_depth_route_features


# Map run_id -> (routing_variant, protocol dispatch info)
RUN_PROTocols = {
    "S0": {"routing": "none", "protocol_source": "S0_original"},
    "S1": {"routing": "none", "protocol_source": "S1_oracle_v10"},
    "S4": {"routing": "predicted_geometry", "protocol_source": "S4_predicted_geometry"},
    "S5": {"routing": "predicted_geometry", "protocol_source": "S5_no_blocker_first"},
    "S6": {"routing": "predicted_geometry", "protocol_source": "S6_no_geometry_repair"},
    "S7": {"routing": "predicted_geometry", "protocol_source": "S7_no_id_repair"},
    "D1": {"routing": "depth_classifier", "protocol_source": "D1_depth_classifier"},
}


def load_molmo_cache(molmo_dir):
    """Load all Molmo caches."""
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
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) == 4:
                    molmo_id, x, y, gt_id = parts
                    parsed.append((str(molmo_id), int(x), int(y), str(gt_id)))
        if parsed:
            cache[scene_name] = parsed
    return cache


def load_run_outputs(run_dir, run_id):
    """Load all subset outputs and details for a run."""
    split_dir = os.path.join(run_dir, "split_0")
    if not os.path.isdir(split_dir):
        return []

    rows = []
    for fname in sorted(os.listdir(split_dir)):
        if not fname.startswith("out_") or not fname.endswith(".json"):
            continue
        subset = fname.replace("out_", "").replace(".json", "")
        out_path = os.path.join(split_dir, fname)
        details_path = os.path.join(split_dir, f"details_{subset}.json")

        with open(out_path) as f:
            outputs = json.load(f)

        details = []
        if os.path.exists(details_path):
            with open(details_path) as f:
                details = json.load(f)

        # Build detail lookup by (scene_id, object_id)
        detail_map = {}
        for d in details:
            key = (d.get("scene_id"), d.get("object_id"))
            detail_map[key] = d

        for row in outputs:
            if not isinstance(row, list) or len(row) < 5:
                continue
            scene_id, obj_id, annotation, ssr_correct, rsr_correct = row[:5]

            detail = detail_map.get((scene_id, obj_id), {})
            reasoning = detail.get("reasoning", {})

            # Extract protocol info from reasoning
            routing_variant = reasoning.get("routing_variant", "none")
            route_mode = reasoning.get("route_mode", None)
            scene_sc = reasoning.get("scene_complexity_features", {})
            if scene_sc and isinstance(scene_sc, dict):
                route_mode = route_mode or scene_sc.get("route_mode", None)

            rows.append({
                "sample_key": f"{scene_id}_{obj_id}_{annotation}",
                "scene_id": scene_id,
                "query_object_id": obj_id,
                "annotation": annotation,
                "subset": subset,
                "protocol_source_run": run_id,
                "rsr_success": rsr_correct,
                "ssr_success": ssr_correct,
                "routing_variant": routing_variant,
                "route_mode": route_mode,
            })

    return rows


def compute_query_features(parsed_data, scene_id, query_obj_id):
    """Compute query-conditioned features for a sample."""
    query_target_id = query_obj_id + 1  # 1-indexed

    features = extract_depth_route_features(
        parsed_data, scene_id,
        query_target_id=query_target_id,
    )

    if features is None:
        return {
            "feature_target_valid": False,
            "num_objects": 0,
            "n_depth_valid": 0,
            "target_depth_mean": 0.0,
            "target_depth_std": 0.0,
            "target_depth_range": 0.0,
            "scene_depth_mean": 0.0,
            "scene_depth_std": 0.0,
            "target_vs_scene_depth": 0.0,
            "n_objects_in_front": 0,
            "n_objects_behind": 0,
            "depth_rank_ratio": 0.0,
            "mean_depth_diff": 0.0,
            "std_depth_diff": 0.0,
            "min_depth_diff": 0.0,
            "max_depth_diff": 0.0,
            "scene_bbox_ratio": 0.0,
            "target_nearest_dist": 0.0,
            "target_bbox_ratio": 0.0,
            "mean_nn_ratio": 0.0,
            "median_nn_ratio": 0.0,
            "n_close_in_front": 0,
        }

    features["feature_target_valid"] = True
    return features


def main():
    parser = argparse.ArgumentParser(description="Build outcome policy replay table")
    parser.add_argument("--runs", nargs="+", required=True,
                        help="Run specs like S0=path/to/S0 S1=path/to/S1")
    parser.add_argument("--molmo-root", default="data/output/molmo_output")
    parser.add_argument("--npz-root", default="data/npz_file")
    parser.add_argument("--output", default="data/output/outcome_policy_selector_v1/replay_table.csv")
    parser.add_argument("--report", default="data/output/outcome_policy_selector_v1/replay_manifest.json")
    args = parser.parse_args()

    # Parse run specs
    run_specs = {}
    for spec in args.runs:
        run_id, run_path = spec.split("=", 1)
        run_specs[run_id] = run_path

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print("=" * 70)
    print("Building Outcome Policy Replay Table")
    print("=" * 70)

    # Load Molmo cache
    print(f"\n[1/4] Loading Molmo cache...")
    molmo_cache = load_molmo_cache(args.molmo_root)
    print(f"  Loaded {len(molmo_cache)} scenes")

    # Load all run outputs
    print(f"\n[2/4] Loading run outputs...")
    all_rows = []
    run_stats = {}
    for run_id, run_path in run_specs.items():
        rows = load_run_outputs(run_path, run_id)
        run_stats[run_id] = len(rows)
        all_rows.extend(rows)
        print(f"  {run_id}: {len(rows)} samples")

    print(f"  Total: {len(all_rows)} rows")

    # Compute query-conditioned features
    print(f"\n[3/4] Computing query-conditioned features...")
    t0 = time.time()
    feature_rows = []
    for i, row in enumerate(all_rows):
        scene_id = row["scene_id"]
        obj_id = row["query_object_id"]
        scene_name = str(scene_id)

        if scene_name in molmo_cache:
            parsed_data = molmo_cache[scene_name]
            features = compute_query_features(parsed_data, scene_id, obj_id)
        else:
            features = {"feature_target_valid": False}

        row.update(features)
        feature_rows.append(row)

        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  Processed {i+1}/{len(all_rows)} ({elapsed:.1f}s)")

    elapsed = time.time() - t0
    print(f"  Done: {len(feature_rows)} rows ({elapsed:.1f}s)")

    # Save replay table
    print(f"\n[4/4] Saving replay table...")
    df = pd.DataFrame(feature_rows)
    df.to_csv(args.output, index=False)
    print(f"  Saved to {args.output}")

    # Save manifest
    manifest = {
        "total_rows": len(df),
        "run_stats": run_stats,
        "unique_scenes": df["scene_id"].nunique(),
        "unique_samples": df["sample_key"].nunique(),
        "feature_coverage": df["feature_target_valid"].mean(),
        "rsr_by_run": df.groupby("protocol_source_run")["rsr_success"].mean().to_dict(),
        "ssr_by_run": df.groupby("protocol_source_run")["ssr_success"].mean().to_dict(),
    }
    with open(args.report, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest saved to {args.report}")

    # Summary
    print(f"\n{'='*70}")
    print(f"REPLAY TABLE SUMMARY")
    print(f"{'='*70}")
    print(f"  Total rows: {len(df)}")
    print(f"  Unique scenes: {df['scene_id'].nunique()}")
    print(f"  Unique samples: {df['sample_key'].nunique()}")
    print(f"  Feature coverage: {df['feature_target_valid'].mean():.1%}")
    print(f"\n  RSR by run:")
    for run_id in sorted(run_stats.keys()):
        rsr = df[df["protocol_source_run"] == run_id]["rsr_success"].mean()
        print(f"    {run_id}: {rsr:.4f}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
