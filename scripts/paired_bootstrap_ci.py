#!/usr/bin/env python3
"""Compute paired scene-clustered bootstrap intervals for FreeGrasp runs."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


SUBSETS = [
    "easy_no_ambi",
    "easy_yes_ambi",
    "medium_no_ambi",
    "medium_yes_ambi",
    "hard_no_ambi",
    "hard_yes_ambi",
]
SPLITS = ["0", "1", "2"]
METRIC_INDEX = {"SSR": 3, "RSR": 4}


def sample_key(split: str, subset: str, row_index: int, row: list) -> tuple:
    return (split, subset, row_index, row[0], row[1], row[2])


def load_run(run_root: Path) -> dict[tuple, dict]:
    rows = {}
    for split in SPLITS:
        for subset in SUBSETS:
            path = run_root / f"split_{split}" / f"out_{subset}.json"
            data = json.loads(path.read_text())
            for row_index, row in enumerate(data):
                rows[sample_key(split, subset, row_index, row)] = {
                    "split": split,
                    "subset": subset,
                    "row_index": row_index,
                    "scene_id": row[0],
                    "object_id": row[1],
                    "annotation": row[2],
                    "SSR": int(row[METRIC_INDEX["SSR"]]),
                    "RSR": int(row[METRIC_INDEX["RSR"]]),
                }
    return rows


def require_same_keys(left: dict, right: dict, left_name: str, right_name: str) -> list[tuple]:
    left_keys = set(left)
    right_keys = set(right)
    if left_keys != right_keys:
        missing_left = sorted(right_keys - left_keys)[:5]
        missing_right = sorted(left_keys - right_keys)[:5]
        raise RuntimeError(
            f"Run keys differ for {left_name} vs {right_name}. "
            f"Missing in {left_name}: {missing_left}; missing in {right_name}: {missing_right}"
        )
    return sorted(left_keys)


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def paired_delta(left: dict, right: dict, keys: list[tuple], metric: str) -> float:
    return sum(left[key][metric] - right[key][metric] for key in keys) / len(keys)


def cluster_keys(keys: list[tuple]) -> dict[int, list[tuple]]:
    clusters = defaultdict(list)
    for key in keys:
        scene_id = key[3]
        clusters[scene_id].append(key)
    return dict(clusters)


def bootstrap_comparison(
    left: dict,
    right: dict,
    keys: list[tuple],
    metric: str,
    iterations: int,
    seed: int,
) -> dict:
    observed = paired_delta(left, right, keys, metric)
    clusters = cluster_keys(keys)
    cluster_ids = sorted(clusters)
    rng = random.Random(seed)
    deltas = []
    for _ in range(iterations):
        sampled_keys = []
        for _cluster_id in cluster_ids:
            sampled_cluster_id = rng.choice(cluster_ids)
            sampled_keys.extend(clusters[sampled_cluster_id])
        deltas.append(paired_delta(left, right, sampled_keys, metric))
    tail_probability = sum(delta <= 0 for delta in deltas) / len(deltas)
    return {
        "metric": metric,
        "n": len(keys),
        "clusters": len(cluster_ids),
        "delta": observed,
        "delta_pp": observed * 100,
        "ci_low": percentile(deltas, 0.025),
        "ci_high": percentile(deltas, 0.975),
        "ci_low_pp": percentile(deltas, 0.025) * 100,
        "ci_high_pp": percentile(deltas, 0.975) * 100,
        "tail_probability_delta_le_0": tail_probability,
        "bootstrap_iterations": iterations,
        "seed": seed,
    }


def format_markdown(results: list[dict]) -> str:
    lines = [
        "# EGHC3 Bootstrap Confidence Intervals",
        "",
        "Scene-clustered paired bootstrap over the 900 aligned FreeGraspData rows. "
        "Deltas are percentage points. Tail probability is the one-sided bootstrap "
        "probability that the paired delta is less than or equal to zero.",
        "",
        "| Comparison | Metric | N | Scene clusters | Delta | 95% CI | Tail P(delta <= 0) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            "| {comparison} | {metric} | {n} | {clusters} | {delta_pp:+.2f} | "
            "[{ci_low_pp:+.2f}, {ci_high_pp:+.2f}] | {tail:.4f} |".format(
                comparison=result["comparison"],
                metric=result["metric"],
                n=result["n"],
                clusters=result["clusters"],
                delta_pp=result["delta_pp"],
                ci_low_pp=result["ci_low_pp"],
                ci_high_pp=result["ci_high_pp"],
                tail=result["tail_probability_delta_le_0"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, results: list[dict]) -> None:
    fields = [
        "comparison",
        "metric",
        "n",
        "clusters",
        "delta_pp",
        "ci_low_pp",
        "ci_high_pp",
        "tail_probability_delta_le_0",
        "bootstrap_iterations",
        "seed",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow({field: result[field] for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", default="data/output/ablation_matrix")
    parser.add_argument("--output-dir", default="data/output/statistics")
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260630)
    args = parser.parse_args()

    matrix_root = Path(args.matrix_root)
    runs = {
        "S0": load_run(matrix_root / "S0"),
        "EGHC3_v3": load_run(matrix_root / "EGHC3_v3_qwen35_full"),
        "S1": load_run(matrix_root / "S1"),
    }
    comparisons = [
        ("EGHC3_v3 - S0", "EGHC3_v3", "S0"),
        ("S1 - EGHC3_v3", "S1", "EGHC3_v3"),
    ]

    results = []
    for comparison_name, left_name, right_name in comparisons:
        keys = require_same_keys(runs[left_name], runs[right_name], left_name, right_name)
        for metric in ["RSR", "SSR"]:
            result = bootstrap_comparison(
                runs[left_name],
                runs[right_name],
                keys,
                metric,
                iterations=args.iterations,
                seed=args.seed + len(results),
            )
            result["comparison"] = comparison_name
            result["left_run"] = left_name
            result["right_run"] = right_name
            results.append(result)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "eghc3_bootstrap_ci.json").write_text(json.dumps(results, indent=2))
    (output_dir / "eghc3_bootstrap_ci.md").write_text(format_markdown(results))
    write_csv(output_dir / "eghc3_bootstrap_ci.csv", results)
    print(format_markdown(results))


if __name__ == "__main__":
    main()
