"""Paired statistics and paper-table exports for FreeGrasp ablations."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def load_detail_rows(run_root):
    rows = []
    for path in sorted(Path(run_root).glob("split_*/details_*.json")):
        split = path.parent.name.removeprefix("split_")
        subset = path.stem.removeprefix("details_")
        for row_index, row in enumerate(json.loads(path.read_text())):
            rows.append(
                {
                    **row,
                    "split": str(split),
                    "subset": subset,
                    "row_index": row_index,
                }
            )
    return rows


def sample_key(row):
    return (
        str(row["split"]),
        str(row["subset"]),
        int(row["row_index"]),
        int(row["scene_id"]),
        int(row["object_id"]),
        str(row.get("annotation", "")),
    )


def _index_unique(rows):
    indexed = {}
    for row in rows:
        key = sample_key(row)
        if key in indexed:
            raise ValueError(f"Duplicate sample key: {key}")
        indexed[key] = row
    return indexed


def pair_by_sample_key(rows_a, rows_b):
    indexed_a = _index_unique(rows_a)
    indexed_b = _index_unique(rows_b)
    if set(indexed_a) != set(indexed_b):
        missing_a = sorted(set(indexed_b) - set(indexed_a))
        missing_b = sorted(set(indexed_a) - set(indexed_b))
        raise ValueError(
            "Mismatched sample keys: "
            f"missing_from_a={missing_a[:5]}, missing_from_b={missing_b[:5]}"
        )
    return [
        {
            "scene_id": int(indexed_a[key]["scene_id"]),
            "sample_key": key,
            "a": indexed_a[key],
            "b": indexed_b[key],
        }
        for key in sorted(indexed_a)
    ]


def clustered_delta_ci(rows_a, rows_b, metric, seed=0, draws=10000):
    paired = pair_by_sample_key(rows_a, rows_b)
    scenes = sorted({row["scene_id"] for row in paired})
    if not scenes:
        raise ValueError("Cannot bootstrap an empty comparison")
    by_scene = {
        scene: [row for row in paired if row["scene_id"] == scene]
        for scene in scenes
    }
    observed = np.mean(
        [float(row["b"][metric]) - float(row["a"][metric]) for row in paired]
    )
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(draws):
        sampled_scenes = rng.choice(scenes, size=len(scenes), replace=True)
        values = [
            float(row["b"][metric]) - float(row["a"][metric])
            for scene in sampled_scenes
            for row in by_scene[int(scene)]
        ]
        deltas.append(float(np.mean(values)))
    return {
        "delta": float(observed),
        "ci95": np.quantile(deltas, [0.025, 0.975]).tolist(),
        "cluster_unit": "scene_id",
        "n_scenes": len(scenes),
        "n_rows": len(paired),
        "seed": seed,
        "draws": draws,
    }


def failure_categories(rows):
    categories = {
        "target_resolution_error": 0,
        "wrong_blocker": 0,
        "routing_error": 0,
        "rsr_only_segmentation_error": 0,
        "same_class_mask_swap": 0,
        "no_mask_failure": 0,
        "invalid_id": 0,
        "api_error": 0,
        "invalid_or_incomplete": 0,
    }
    for row in rows:
        reason = str(row.get("failure_reason") or "").lower()
        error = str(row.get("error") or "").lower()
        if row.get("rsr_correct") and not row.get("ssr_correct"):
            categories["rsr_only_segmentation_error"] += 1
        if "target" in reason and "resolution" in reason:
            categories["target_resolution_error"] += 1
        if "blocker" in reason:
            categories["wrong_blocker"] += 1
        if "route" in reason:
            categories["routing_error"] += 1
        if "same_class" in reason or "mask_swap" in reason:
            categories["same_class_mask_swap"] += 1
        if "no_mask" in reason or "no masks" in reason:
            categories["no_mask_failure"] += 1
        if "invalid_id" in reason or "invalid id" in reason:
            categories["invalid_id"] += 1
        if "api" in error or "timeout" in error:
            categories["api_error"] += 1
        if "rsr_correct" not in row or "ssr_correct" not in row:
            categories["invalid_or_incomplete"] += 1
    return categories


def _method_label(row):
    suffix = {
        "reported": " (reported)",
        "oracle_feature": " (oracle feature)",
    }.get(row.get("status"), "")
    return f"{row['method']}{suffix}"


def export_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["method", "rsr", "ssr", "status"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_latex(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Method & RSR (\%) & SSR (\%) \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{_method_label(row)} & {100 * row['rsr']:.2f} & "
            f"{100 * row['ssr']:.2f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path.write_text("\n".join(lines) + "\n")


def export_paper_tables(tables, output_dir):
    required = (
        "main_results",
        "routing_ablation",
        "reasoning_ablation",
        "segmentation_ablation",
    )
    missing = [name for name in required if name not in tables]
    if missing:
        raise ValueError(f"Missing paper tables: {', '.join(missing)}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in required:
        export_csv(tables[name], output_dir / f"{name}.csv")
        export_latex(tables[name], output_dir / f"{name}.tex")


def validate_run(run_root, expected_n=900):
    rows = load_detail_rows(run_root)
    keys = [sample_key(row) for row in rows]
    if len(rows) != expected_n or len(set(keys)) != expected_n:
        raise RuntimeError(
            f"Expected {expected_n} unique samples, got {len(rows)} rows and "
            f"{len(set(keys))} unique keys"
        )
    return {"n": len(rows), "unique_samples": len(set(keys))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("run_root")
    validate.add_argument("--expected-n", type=int, default=900)
    args = parser.parse_args(argv)
    if args.command == "validate":
        print(json.dumps(validate_run(args.run_root, args.expected_n), indent=2))


if __name__ == "__main__":
    main()
