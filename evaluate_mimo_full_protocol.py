import argparse
import json
import os
import shutil
from pathlib import Path

from experiment_manifest import (
    build_manifest,
    guard_provenance,
    hash_directory,
    write_manifest,
)


DEFAULT_SUBSETS = [
    "easy_no_ambi",
    "easy_yes_ambi",
    "medium_no_ambi",
    "medium_yes_ambi",
    "hard_no_ambi",
    "hard_yes_ambi",
]
DEFAULT_SPLITS = ["0", "1", "2"]
DEFAULT_RUN_ROOT = "data/output/mimo-v2.5_full_protocol_best_known_v1"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run MiMo v2.5 on all FreeGrasp synthetic splits.")
    parser.add_argument("--model-name", default="mimo-v2.5")
    parser.add_argument("--max-output-tokens", type=int, default=713)
    parser.add_argument("--subset-policy", default="best_known_v1")
    parser.add_argument(
        "--segmentation-variant",
        choices=["baseline", "point_retry", "geometric_consistency"],
        default="point_retry",
    )
    parser.add_argument(
        "--routing-variant",
        choices=["none", "count_only", "vlm_two_stage", "predicted_geometry", "scene_complexity"],
        default="none",
    )
    parser.add_argument(
        "--feature-source",
        choices=["none", "predicted", "oracle_feature"],
        default="none",
    )
    parser.add_argument(
        "--route-guard-variant",
        choices=["none", "conservative_v1", "target_evidence_v2"],
        default="none",
    )
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--expected-cache-sha256", default=None)
    parser.add_argument("--splits", nargs="+", default=list(DEFAULT_SPLITS))
    parser.add_argument("--resume", action="store_true", help="Resume existing out_*.json rows.")
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    parser.add_argument(
        "--reuse-molmo",
        action="store_true",
        dest="reuse_molmo",
        help="Reuse data/output/molmo_output and fail if required scenes are missing.",
    )
    parser.add_argument(
        "--regenerate-molmo",
        action="store_false",
        dest="reuse_molmo",
        help="Regenerate Molmo cache inside each subset run. This is expensive and not recommended.",
    )
    parser.add_argument(
        "--fresh-molmo",
        action="store_true",
        help="Clear data/output/molmo_output and regenerate Molmo once before running all splits.",
    )
    parser.add_argument(
        "--skip-mimo-preflight",
        action="store_false",
        dest="mimo_preflight",
        help="Skip the startup MiMo image-input check.",
    )
    parser.add_argument("--mimo-api-key", default=None)
    parser.add_argument("--mimo-base-url", default=None)
    parser.set_defaults(resume=True, reuse_molmo=True, fresh_molmo=False, mimo_preflight=True)
    return parser.parse_args(argv)


def aggregate_run_results(
    *,
    run_root,
    splits,
    subsets,
    model_name,
    max_output_tokens,
    subset_policy,
    molmo_cache_policy,
    scores_by_split,
    manifest=None,
):
    run_root = Path(run_root)
    aggregate = {}
    total_n = total_ssr = total_rsr = 0
    reasoning_calls = router_calls = repair_calls = 0

    for subset_name in subsets:
        subset_n = subset_ssr = subset_rsr = 0
        for selected_split in splits:
            path = run_root / f"split_{selected_split}" / f"out_{subset_name}.json"
            rows = json.loads(path.read_text())
            details_path = (
                run_root / f"split_{selected_split}" / f"details_{subset_name}.json"
            )
            details = (
                json.loads(details_path.read_text()) if details_path.exists() else []
            )
            for detail in details:
                reasoning = detail.get("reasoning", {})
                reasoning_calls += len(reasoning.get("raw_outputs", []))
                router_calls += int(reasoning.get("router_call_count", 0))
                repair_calls += int(reasoning.get("retry_count", 0))
            subset_n += len(rows)
            subset_ssr += sum(1 for row in rows if len(row) > 3 and row[3] == 1)
            subset_rsr += sum(1 for row in rows if len(row) > 4 and row[4] == 1)

        aggregate[subset_name] = {
            "n": subset_n,
            "ssr": subset_ssr / subset_n if subset_n else 0,
            "rsr": subset_rsr / subset_n if subset_n else 0,
            "ssr_count": subset_ssr,
            "rsr_count": subset_rsr,
        }
        total_n += subset_n
        total_ssr += subset_ssr
        total_rsr += subset_rsr
        if set(splits) == {"0", "1", "2"} and subset_n != 150:
            raise RuntimeError(
                f"Incomplete full run for {subset_name}: expected 150, got {subset_n}"
            )

    summary = {
        "model": model_name,
        "max_output_tokens": max_output_tokens,
        "subset_policy": subset_policy,
        "splits": list(splits),
        "molmo_cache_policy": molmo_cache_policy,
        "scores_by_split": scores_by_split,
        "aggregate": aggregate,
        "overall": {
            "n": total_n,
            "ssr": total_ssr / total_n if total_n else 0,
            "rsr": total_rsr / total_n if total_n else 0,
            "ssr_count": total_ssr,
            "rsr_count": total_rsr,
        },
        "reasoning_calls": reasoning_calls,
        "router_calls": router_calls,
        "repair_calls": repair_calls,
        "calls_per_sample": reasoning_calls / total_n if total_n else 0.0,
    }
    if manifest:
        for key in (
            "manifest_id",
            "cache_sha256",
            "feature_source",
            "routing_variant",
            "uses_gt_features",
            "uses_benchmark_difficulty",
            "route_guard_variant",
            "direct_confidence_threshold",
            "direct_max_object_count",
            "target_overlap_threshold",
            "target_evidence_max_candidates",
            "duplicate_mask_iou_threshold",
            "duplicate_bbox_overlap_threshold",
            "guard_code_version",
        ):
            summary[key] = manifest.get(key)
    return summary


def print_summary(summary):
    print("=" * 60)
    for subset_name, score in summary["aggregate"].items():
        print(f"{subset_name:25s}: RSR {score['rsr']:.2%} | SSR {score['ssr']:.2%} | n={score['n']}")
    print("-" * 60)
    overall = summary["overall"]
    print(f"OVERALL                  : RSR {overall['rsr']:.2%} | SSR {overall['ssr']:.2%} | n={overall['n']}")
    print("=" * 60)


def prepare_fresh_molmo_cache():
    from evaluate_common import MOLMO_OUTPUT_DIR, NPZ_DIR, load_dataset
    from molmo_eval import batch_process_molmo

    if os.path.exists(MOLMO_OUTPUT_DIR):
        print(f"Clearing old Molmo output: {MOLMO_OUTPUT_DIR}")
        shutil.rmtree(MOLMO_OUTPUT_DIR)
    os.makedirs(MOLMO_OUTPUT_DIR, exist_ok=True)

    df = load_dataset()
    batch_process_molmo(df, NPZ_DIR, MOLMO_OUTPUT_DIR)


def run_full_protocol(args):
    from evaluate_all import _subset_config
    from evaluate_common import MOLMO_OUTPUT_DIR, evaluate_subset
    from evaluate_mimo import create_mimo_client, patch_freegrasp_client, validate_mimo_supports_image_input

    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    if args.fresh_molmo:
        prepare_fresh_molmo_cache()

    cache_sha256 = hash_directory(MOLMO_OUTPUT_DIR)
    if (
        args.expected_cache_sha256
        and args.expected_cache_sha256 != cache_sha256
    ):
        raise RuntimeError(
            "Molmo cache hash mismatch: "
            f"expected {args.expected_cache_sha256}, got {cache_sha256}"
        )

    uses_benchmark_difficulty = args.subset_policy not in {
        "none",
        "original_protocol",
        "automatic_evidence_v1",
        "automatic_no_blocker_first",
        "automatic_no_geometry_repair",
        "automatic_no_id_repair",
        "scene_complexity_auto",
        "scene_complexity_no_blocker_first",
        "scene_complexity_no_geometry_repair",
        "scene_complexity_no_id_repair",
    }
    manifest = build_manifest(
        {
            "model": args.model_name,
            "max_output_tokens": args.max_output_tokens,
            "splits": list(args.splits),
            "subsets": list(DEFAULT_SUBSETS),
            "subset_policy": args.subset_policy,
            "routing_variant": args.routing_variant,
            "segmentation_variant": args.segmentation_variant,
            "feature_source": args.feature_source,
            "cache_sha256": cache_sha256,
            "uses_gt_features": args.feature_source == "oracle_feature",
            "uses_benchmark_difficulty": uses_benchmark_difficulty,
            **guard_provenance(args.route_guard_variant),
        },
        command="evaluate_mimo_full_protocol.py",
    )
    manifest = write_manifest(
        run_root / "run_manifest.json",
        manifest,
        resume=args.resume,
    )

    mimo_client = create_mimo_client(api_key=args.mimo_api_key, base_url=args.mimo_base_url)
    if args.mimo_preflight:
        validate_mimo_supports_image_input(mimo_client, args.model_name)
    patch_freegrasp_client(mimo_client, mimo_api_key=args.mimo_api_key)

    molmo_cache_policy = "fresh_once" if args.fresh_molmo else "reuse_existing"
    if not args.reuse_molmo and not args.fresh_molmo:
        molmo_cache_policy = "regenerate_per_subset"

    scores_by_split = {}
    for selected_split in args.splits:
        split_dir = run_root / f"split_{selected_split}"
        split_dir.mkdir(parents=True, exist_ok=True)
        split_scores = {}

        for subset_name in DEFAULT_SUBSETS:
            config = _subset_config(
                subset_name,
                prompt_variant="legacy_old",
                mimo_retry_mode="id_repair",
                segmentation_variant=args.segmentation_variant,
                subset_policy=args.subset_policy,
                routing_variant=args.routing_variant,
                feature_source=args.feature_source,
            )
            split_scores[subset_name] = evaluate_subset(
                subset_name,
                selected_split=selected_split,
                output_dir=str(split_dir),
                prepare_molmo=not args.reuse_molmo and not args.fresh_molmo,
                model_name=args.model_name,
                prompt_variant=config["prompt_variant"],
                max_output_tokens=args.max_output_tokens,
                resume=args.resume,
                mimo_retry_mode=config["mimo_retry_mode"],
                segmentation_variant=config["segmentation_variant"],
                routing_variant=config.get("routing_variant", "none"),
                feature_source=config.get("feature_source", "none"),
                protocol_ablation=config.get("protocol_ablation", "full"),
                route_guard_variant=args.route_guard_variant,
            )

        scores_by_split[selected_split] = split_scores

    summary = aggregate_run_results(
        run_root=run_root,
        splits=args.splits,
        subsets=DEFAULT_SUBSETS,
        model_name=args.model_name,
        max_output_tokens=args.max_output_tokens,
        subset_policy=args.subset_policy,
        molmo_cache_policy=molmo_cache_policy,
        scores_by_split=scores_by_split,
        manifest=manifest,
    )
    with open(run_root / "full_protocol_summary.json", "w") as f:
        json.dump(summary, f, indent=4)
    print_summary(summary)
    return summary


if __name__ == "__main__":
    run_full_protocol(parse_args())
