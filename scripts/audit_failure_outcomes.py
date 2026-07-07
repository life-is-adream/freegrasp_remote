#!/usr/bin/env python3
"""Regenerate metric-level EGHC failure outcome counts from saved detail rows.

This script is read-only: it parses existing ``details_*.json`` files and
computes joint-success / RSR-only / SSR-only / both-fail counts by difficulty.
It does not call any model, refresh any cache, or rewrite experiment outputs.

The semantic categories in the manuscript (wrong blocker, direct-when-blocker-
needed, etc.) still require human/semantic labels. This script verifies the
auditable metric denominator used by that taxonomy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DIFFICULTIES = ("easy", "medium", "hard")
MODES = ("joint_success", "rsr_only", "ssr_only", "both_fail")


def difficulty_from_name(path: Path) -> str:
    name = path.name
    for difficulty in DIFFICULTIES:
        if name.startswith(f"details_{difficulty}_"):
            return difficulty.capitalize()
    raise ValueError(f"Cannot infer difficulty from {path}")


def load_rows(details_root: Path) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    files = sorted(details_root.glob("split_*/details_*.json"))
    if not files:
        files = sorted(details_root.glob("details_*.json"))
    if not files:
        raise FileNotFoundError(f"No details_*.json files found under {details_root}")

    for path in files:
        difficulty = difficulty_from_name(path)
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            raise TypeError(f"{path} must contain a JSON list")
        for row in data:
            if not isinstance(row, dict):
                raise TypeError(f"{path} contains a non-object row")
            rows.append((difficulty, row))
    return rows


def mode_for_row(row: dict[str, Any]) -> str:
    rsr = int(row.get("rsr_correct") or 0) == 1
    ssr = int(row.get("ssr_correct") or 0) == 1
    if rsr and ssr:
        return "joint_success"
    if rsr and not ssr:
        return "rsr_only"
    if ssr and not rsr:
        return "ssr_only"
    return "both_fail"


def summarize(rows: list[tuple[str, dict[str, Any]]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {
        d.capitalize(): {mode: 0 for mode in MODES} | {"n": 0}
        for d in DIFFICULTIES
    }
    counts["Overall"] = {mode: 0 for mode in MODES} | {"n": 0}

    for difficulty, row in rows:
        mode = mode_for_row(row)
        counts[difficulty]["n"] += 1
        counts[difficulty][mode] += 1
        counts["Overall"]["n"] += 1
        counts["Overall"][mode] += 1
    return counts


def render_markdown(counts: dict[str, dict[str, int]]) -> str:
    lines = [
        "| Difficulty | N | Joint success | RSR-only | SSR-only | Both-fail | Non-joint-success total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for difficulty in ("Easy", "Medium", "Hard", "Overall"):
        c = counts[difficulty]
        non_joint = c["rsr_only"] + c["ssr_only"] + c["both_fail"]
        label = f"**{difficulty}**" if difficulty == "Overall" else difficulty
        lines.append(
            f"| {label} | {c['n']} | {c['joint_success']} | {c['rsr_only']} | "
            f"{c['ssr_only']} | {c['both_fail']} | {non_joint} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--details-root",
        default="data/output/ablation_matrix/EGHC3_v3_qwen35_full",
        help="Directory containing split_*/details_*.json or details_*.json files.",
    )
    parser.add_argument("--expect-total", type=int, default=900)
    parser.add_argument("--expect-non-joint", type=int, default=431)
    args = parser.parse_args()

    rows = load_rows(Path(args.details_root))
    counts = summarize(rows)
    non_joint = (
        counts["Overall"]["rsr_only"]
        + counts["Overall"]["ssr_only"]
        + counts["Overall"]["both_fail"]
    )

    print(render_markdown(counts))
    print()
    print(f"total_rows={counts['Overall']['n']}")
    print(f"non_joint_success={non_joint}")

    if counts["Overall"]["n"] != args.expect_total:
        raise SystemExit(
            f"Expected {args.expect_total} rows, got {counts['Overall']['n']}"
        )
    if non_joint != args.expect_non_joint:
        raise SystemExit(
            f"Expected {args.expect_non_joint} non-joint successes, got {non_joint}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
