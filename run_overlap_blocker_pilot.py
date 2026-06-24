"""Run frozen blocker-first reasoning on overlap-triggered pilot samples."""

import argparse
import json
from pathlib import Path

from experiment_manifest import build_manifest, hash_directory, write_manifest


def _find_dataset_row(dataset, sample):
    query_ids = dataset["queryObjId"].astype(int) + 1
    matches = dataset[
        (dataset["split"].astype(str) == str(sample["split"]))
        & (dataset["sceneId"].astype(int) == int(sample["scene_id"]))
        & (query_ids == int(sample["object_id"]))
        & (dataset["annotation"].astype(str) == str(sample["annotation"]))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one dataset row for {sample['scene_id']}/"
            f"{sample['object_id']}, got {len(matches)}"
        )
    return matches.copy()


def _summary(run_root):
    rows = []
    for path in sorted(Path(run_root).glob("split_*/details_*.json")):
        rows.extend(json.loads(path.read_text()))
    n = len(rows)
    return {
        "n": n,
        "rsr_count": sum(int(row.get("rsr_correct", 0)) for row in rows),
        "ssr_count": sum(int(row.get("ssr_correct", 0)) for row in rows),
        "reasoning_calls": sum(
            len(row.get("reasoning", {}).get("raw_outputs", [])) for row in rows
        ),
        "router_calls": sum(
            int(row.get("reasoning", {}).get("router_call_count", 0))
            for row in rows
        ),
        "repair_calls": sum(
            int(row.get("reasoning", {}).get("retry_count", 0)) for row in rows
        ),
    }


def run(args):
    if args.confirm_paid_inference != "RUN_PAID_INFERENCE":
        raise ValueError("Paid inference confirmation is required")
    from evaluate_common import MOLMO_OUTPUT_DIR, NPZ_DIR, ensure_molmo_cache_exists, load_dataset
    from evaluate_mimo import create_mimo_client, patch_freegrasp_client, validate_mimo_supports_image_input
    from reasoning_eval import process_dataset

    pilot = json.loads(Path(args.pilot_manifest).read_text())
    cache_sha256 = hash_directory(MOLMO_OUTPUT_DIR)
    if cache_sha256 != pilot["cache_sha256"]:
        raise RuntimeError("Molmo cache hash mismatch")
    if pilot.get("variant") != "overlap_blocker_v1":
        raise ValueError("Wrong pilot variant")

    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        {
            "model": "mimo-v2.5",
            "max_output_tokens": 1024,
            "routing_variant": "frozen_overlap_blocker",
            "route_guard_variant": "overlap_blocker_v1",
            "feature_source": "predicted",
            "segmentation_variant": "geometric_consistency",
            "cache_sha256": cache_sha256,
            "pilot_n": pilot["n_samples"],
            "uses_gt_features": False,
            "uses_benchmark_difficulty": False,
        },
        command="run_overlap_blocker_pilot.py",
    )
    write_manifest(run_root / "run_manifest.json", manifest, resume=True)

    client = create_mimo_client(api_key=args.mimo_api_key, base_url=args.mimo_base_url)
    if not args.skip_preflight:
        validate_mimo_supports_image_input(client, "mimo-v2.5")
    patch_freegrasp_client(client, mimo_api_key=args.mimo_api_key)
    dataset = load_dataset()

    for sample in pilot["samples"]:
        selected = _find_dataset_row(dataset, sample)
        ensure_molmo_cache_exists(selected, MOLMO_OUTPUT_DIR)
        output_dir = run_root / f"split_{sample['split']}"
        output_dir.mkdir(parents=True, exist_ok=True)
        process_dataset(
            selected,
            NPZ_DIR,
            MOLMO_OUTPUT_DIR,
            output_dir / f"out_{sample['subset']}.json",
            prompt_variant="legacy",
            model_name="mimo-v2.5",
            max_output_tokens=1024,
            resume=True,
            mimo_retry_mode="none",
            segmentation_variant="geometric_consistency",
            routing_variant="predicted_geometry",
            feature_source="predicted",
            protocol_ablation="full",
            route_guard_variant="none",
            frozen_route_assessment=sample["frozen_route_assessment"],
            evaluation_subset=sample["subset"],
            details_json_path=output_dir / f"details_{sample['subset']}.json",
        )

    summary = _summary(run_root)
    summary.update(
        {
            "expected_n": pilot["n_samples"],
            "baseline_target_first_rsr_count": pilot["baseline_rsr_count"],
            "baseline_target_first_ssr_count": pilot["baseline_ssr_count"],
            "manifest_id": manifest["manifest_id"],
            "variant": "overlap_blocker_v1",
        }
    )
    summary["rsr"] = summary["rsr_count"] / summary["n"] if summary["n"] else 0
    summary["ssr"] = summary["ssr_count"] / summary["n"] if summary["n"] else 0
    (run_root / "pilot_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
    if summary["n"] != pilot["n_samples"]:
        raise RuntimeError(
            f"Incomplete pilot: {summary['n']}/{pilot['n_samples']}"
        )
    print(json.dumps(summary, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-manifest", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--mimo-api-key", default=None)
    parser.add_argument("--mimo-base-url", default=None)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--confirm-paid-inference", required=True)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
