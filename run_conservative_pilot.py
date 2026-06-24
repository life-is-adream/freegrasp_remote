"""Run the approved conservative-router pilot on a frozen sample manifest."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from experiment_manifest import build_manifest, guard_provenance, hash_directory, write_manifest


def group_samples(pilot_manifest):
    grouped = defaultdict(list)
    for sample in pilot_manifest["samples"]:
        grouped[(str(sample["split"]), sample["subset"])].append(
            int(sample["row_index"])
        )
    return {key: sorted(indices) for key, indices in grouped.items()}


def select_rows(frame, row_indices):
    if any(index < 0 or index >= len(frame) for index in row_indices):
        raise ValueError("Pilot row index is out of range")
    return frame.iloc[list(row_indices)].copy()


def _file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _summarize(run_root):
    details = []
    for path in sorted(Path(run_root).glob("split_*/details_*.json")):
        details.extend(json.loads(path.read_text()))
    n = len(details)
    rsr = sum(int(row.get("rsr_correct", 0)) for row in details)
    ssr = sum(int(row.get("ssr_correct", 0)) for row in details)
    route_counts = defaultdict(int)
    calls = repairs = routers = 0
    for row in details:
        reasoning = row.get("reasoning", {})
        route_counts[str(reasoning.get("route_mode"))] += 1
        calls += len(reasoning.get("raw_outputs", []))
        repairs += int(reasoning.get("retry_count", 0))
        routers += int(reasoning.get("router_call_count", 0))
    return {
        "n": n,
        "rsr_count": rsr,
        "ssr_count": ssr,
        "rsr": rsr / n if n else 0.0,
        "ssr": ssr / n if n else 0.0,
        "route_counts": dict(sorted(route_counts.items())),
        "reasoning_calls": calls,
        "router_calls": routers,
        "repair_calls": repairs,
    }


def run(args):
    if args.confirm_paid_inference != "RUN_PAID_INFERENCE":
        raise ValueError(
            "--confirm-paid-inference must equal RUN_PAID_INFERENCE"
        )

    from evaluate_common import (
        MOLMO_OUTPUT_DIR,
        NPZ_DIR,
        ensure_molmo_cache_exists,
        load_dataset,
        prepare_subset,
    )
    from evaluate_mimo import (
        create_mimo_client,
        patch_freegrasp_client,
        validate_mimo_supports_image_input,
    )
    from reasoning_eval import process_dataset

    pilot = json.loads(Path(args.pilot_manifest).read_text())
    if pilot.get("route_guard_variant") != "conservative_v1":
        raise ValueError("Pilot manifest is not conservative_v1")
    if int(pilot.get("n_samples", 0)) != 120:
        raise ValueError("Pilot manifest must contain exactly 120 samples")
    cache_sha256 = hash_directory(MOLMO_OUTPUT_DIR)
    if cache_sha256 != pilot["cache_sha256"]:
        raise RuntimeError(
            f"Molmo cache mismatch: expected {pilot['cache_sha256']}, got {cache_sha256}"
        )

    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        {
            "model": "mimo-v2.5",
            "max_output_tokens": 1024,
            "routing_variant": "predicted_geometry",
            "feature_source": "predicted",
            "segmentation_variant": "geometric_consistency",
            "subset_policy": "automatic_evidence_v1",
            "cache_sha256": cache_sha256,
            "pilot_manifest_sha256": _file_sha256(args.pilot_manifest),
            "pilot_n": 120,
            "uses_gt_features": False,
            "uses_benchmark_difficulty": False,
            **guard_provenance("conservative_v1"),
        },
        command="run_conservative_pilot.py",
    )
    write_manifest(run_root / "run_manifest.json", manifest, resume=args.resume)

    client = create_mimo_client(
        api_key=args.mimo_api_key,
        base_url=args.mimo_base_url,
    )
    if not args.skip_preflight:
        validate_mimo_supports_image_input(client, "mimo-v2.5")
    patch_freegrasp_client(client, mimo_api_key=args.mimo_api_key)

    dataset = load_dataset()
    grouped = group_samples(pilot)
    processed = 0
    for (split, subset), indices in sorted(grouped.items()):
        full_subset = prepare_subset(dataset, subset, split).reset_index(drop=True)
        selected = select_rows(full_subset, indices)
        ensure_molmo_cache_exists(selected, MOLMO_OUTPUT_DIR)
        split_dir = run_root / f"split_{split}"
        split_dir.mkdir(parents=True, exist_ok=True)
        process_dataset(
            selected,
            NPZ_DIR,
            MOLMO_OUTPUT_DIR,
            split_dir / f"out_{subset}.json",
            prompt_variant="legacy",
            model_name="mimo-v2.5",
            max_output_tokens=1024,
            resume=args.resume,
            mimo_retry_mode="none",
            segmentation_variant="geometric_consistency",
            routing_variant="predicted_geometry",
            feature_source="predicted",
            protocol_ablation="full",
            route_guard_variant="conservative_v1",
            evaluation_subset=subset,
            details_json_path=split_dir / f"details_{subset}.json",
        )
        processed += len(selected)

    summary = {
        **_summarize(run_root),
        "expected_n": 120,
        "selected_rows": processed,
        "manifest_id": manifest["manifest_id"],
        "cache_sha256": cache_sha256,
        **guard_provenance("conservative_v1"),
    }
    (run_root / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
    if summary["n"] != 120:
        raise RuntimeError(
            f"Incomplete pilot: expected 120 result rows, got {summary['n']}"
        )
    print(json.dumps(summary, indent=2))
    return summary


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-manifest", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    parser.add_argument("--mimo-api-key", default=None)
    parser.add_argument("--mimo-base-url", default=None)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--confirm-paid-inference", required=True)
    return parser


def main(argv=None):
    run(build_parser().parse_args(argv))


if __name__ == "__main__":
    main()
