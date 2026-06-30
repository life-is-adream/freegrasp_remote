#!/usr/bin/env python3
"""Summarize recorded call budgets from FreeGrasp full-protocol runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "run",
    "n",
    "rsr",
    "ssr",
    "reasoning_calls",
    "router_calls",
    "repair_calls",
    "reasoning_calls_per_sample",
    "total_recorded_calls_per_sample",
]


def load_summary(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "full_protocol_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing full_protocol_summary.json in {run_dir}")
    return json.loads(summary_path.read_text())


def metric_block(summary: dict[str, Any]) -> dict[str, Any]:
    block = summary.get("overall") or summary.get("aggregate")
    if not isinstance(block, dict):
        raise ValueError("Summary must contain an 'overall' or 'aggregate' object")
    return block


def as_int(summary: dict[str, Any], key: str, default: int | None = None) -> int:
    value = summary.get(key, default)
    if value is None:
        raise ValueError(f"Missing required numeric field: {key}")
    return int(value)


def as_percentage(value: Any) -> float:
    number = float(value)
    if 0.0 <= number <= 1.0:
        return number * 100.0
    return number


def summarize_run(run_dir: Path) -> dict[str, str]:
    summary = load_summary(run_dir)
    metrics = metric_block(summary)
    n = int(metrics["n"])
    if n <= 0:
        raise ValueError(f"Run {run_dir} has non-positive n: {n}")

    reasoning_calls = as_int(summary, "reasoning_calls", 0)
    router_calls = as_int(summary, "router_calls", 0)
    repair_calls = as_int(summary, "repair_calls", 0)
    total_calls = reasoning_calls + router_calls + repair_calls

    return {
        "run": run_dir.name,
        "n": str(n),
        "rsr": f"{as_percentage(metrics['rsr']):.2f}",
        "ssr": f"{as_percentage(metrics['ssr']):.2f}",
        "reasoning_calls": str(reasoning_calls),
        "router_calls": str(router_calls),
        "repair_calls": str(repair_calls),
        "reasoning_calls_per_sample": f"{reasoning_calls / n:.2f}",
        "total_recorded_calls_per_sample": f"{total_calls / n:.2f}",
    }


def format_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# RAL Call-Budget Summary",
        "",
        "Recorded call counts from full-protocol summaries. These values are call-budget "
        "accounting only; they do not infer wall-clock latency.",
        "",
        "| Run | N | RSR | SSR | Reasoning calls | Router calls | Repair calls | "
        "Reasoning calls/sample | Total recorded calls/sample |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {run} | {n} | {rsr} | {ssr} | {reasoning_calls} | {router_calls} | "
            "{repair_calls} | {reasoning_calls_per_sample} | "
            "{total_recorded_calls_per_sample} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help="Run directories containing full_protocol_summary.json",
    )
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="Output prefix. The script writes <prefix>.md and <prefix>.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [summarize_run(Path(run_dir)) for run_dir in args.runs]

    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    markdown = format_markdown(rows)
    output_prefix.with_suffix(".md").write_text(markdown)
    write_csv(output_prefix.with_suffix(".csv"), rows)
    print(markdown)


if __name__ == "__main__":
    main()
