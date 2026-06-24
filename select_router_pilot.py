"""Select a deterministic balanced conservative-router pilot."""

import argparse
from collections import Counter
import json
from pathlib import Path
import random


DEFAULT_SUBSETS = [
    "easy_no_ambi",
    "easy_yes_ambi",
    "medium_no_ambi",
    "medium_yes_ambi",
    "hard_no_ambi",
    "hard_yes_ambi",
]


def select_pilot_rows(rows, per_subset=20, seed=20260624):
    keys = [tuple(row["sample_key"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate sample key in audit rows")
    grouped = {subset: [] for subset in DEFAULT_SUBSETS}
    for row in rows:
        if row["subset"] in grouped:
            grouped[row["subset"]].append(row)
    selected = []
    for offset, subset in enumerate(DEFAULT_SUBSETS):
        candidates = sorted(grouped[subset], key=lambda row: tuple(row["sample_key"]))
        if len(candidates) < per_subset:
            raise ValueError(f"Subset {subset} has only {len(candidates)} rows")
        rng = random.Random(seed + offset)
        rng.shuffle(candidates)
        selected.extend(candidates[:per_subset])
    return sorted(selected, key=lambda row: (row["subset"], tuple(row["sample_key"])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-rows", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-subset", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260624)
    args = parser.parse_args(argv)
    rows = json.loads(Path(args.audit_rows).read_text())
    manifest = json.loads(Path(args.source_manifest).read_text())
    selected = select_pilot_rows(rows, args.per_subset, args.seed)
    output = {
        "selection_seed": args.seed,
        "per_subset": args.per_subset,
        "n_samples": len(selected),
        "source_manifest_id": manifest["manifest_id"],
        "cache_sha256": manifest["cache_sha256"],
        "route_guard_variant": "conservative_v1",
        "subset_counts": dict(Counter(row["subset"] for row in selected)),
        "samples": [
            {
                "sample_key": row["sample_key"],
                "split": row["split"],
                "subset": row["subset"],
                "row_index": row["row_index"],
            }
            for row in selected
        ],
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(json.dumps({"n_samples": len(selected), "subset_counts": output["subset_counts"]}, indent=2))


if __name__ == "__main__":
    main()
