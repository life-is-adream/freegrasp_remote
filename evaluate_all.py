import os
import sys
import shutil
import json
from datetime import datetime
from evaluate_common import evaluate_subset, MOLMO_OUTPUT_DIR


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run all FreeGrasp synthetic evaluation subsets.")
    parser.add_argument("--model-name", default="qwen3.6-flash")
    parser.add_argument(
        "--prompt-variant",
        choices=[
            "legacy",
            "legacy_old",
            "json",
            "direct_target",
            "hard_occlusion",
            "roborefer_json",
            "visible_id_guard",
            "candidate_reasoning_json",
            "candidate_grasp_json",
            "candidate_grasp_fewshot_json",
            "candidate_grasp_spatial_json",
            "candidate_grasp_semantic_json",
        ],
        default="legacy",
    )
    parser.add_argument("--max-output-tokens", type=int, default=64)
    parser.add_argument(
        "--mimo-retry-mode",
        choices=[
            "none",
            "id_repair",
            "hard_review",
            "target_review",
            "roborefer_verify",
            "candidate_verify",
            "first_grasp_verify",
        ],
        default="none",
    )
    parser.add_argument("--segmentation-variant", choices=["baseline", "point_retry"], default="baseline")
    parser.add_argument(
        "--subset-policy",
        choices=[
            "none",
            "observed_best_v1",
            "easy_direct_v1",
            "easy_direct_hard_occlusion_v1",
            "best_known_v1",
            "best_known_v2",
            "roborefer_v1",
            "light_review_v1",
            "candidate_v1",
            "candidate_grasp_v2",
            "candidate_grasp_fewshot_v3",
            "candidate_grasp_spatial_v4",
            "candidate_grasp_semantic_v5",
        ],
        default="none",
    )
    parser.add_argument("--run-dir", default=None, help="Existing or new run directory.")
    parser.add_argument("--resume", action="store_true", help="Resume from existing out_*.json rows.")
    parser.add_argument("--no-resume", action="store_false", dest="resume")

    molmo_group = parser.add_mutually_exclusive_group()
    molmo_group.add_argument(
        "--reuse-molmo",
        action="store_true",
        dest="reuse_molmo",
        help="Reuse data/output/molmo_output and fail if required scenes are missing.",
    )
    molmo_group.add_argument(
        "--regenerate-molmo",
        action="store_false",
        dest="reuse_molmo",
        help="Clear and regenerate data/output/molmo_output before evaluation.",
    )
    parser.set_defaults(reuse_molmo=True, resume=True)
    return parser.parse_args(argv)


def _print_score_summary(scores, subset_names):
    print("=" * 60)
    for subset_name in subset_names:
        score = scores[subset_name]
        print(f"  {subset_name:25s}: RSR {score['rsr']:.2%} | SSR {score['ssr']:.2%}")
    print("=" * 60)


def _subset_config(
    subset_name,
    prompt_variant,
    mimo_retry_mode,
    segmentation_variant,
    subset_policy,
):
    config = {
        "prompt_variant": prompt_variant,
        "mimo_retry_mode": mimo_retry_mode,
        "segmentation_variant": segmentation_variant,
    }
    if subset_policy == "none":
        return config

    if subset_policy not in {
        "observed_best_v1",
        "easy_direct_v1",
        "easy_direct_hard_occlusion_v1",
        "best_known_v1",
        "best_known_v2",
        "roborefer_v1",
        "light_review_v1",
        "candidate_v1",
        "candidate_grasp_v2",
        "candidate_grasp_fewshot_v3",
        "candidate_grasp_spatial_v4",
        "candidate_grasp_semantic_v5",
    }:
        raise ValueError(f"Unknown subset_policy: {subset_policy}")

    config.update(
        {
            "prompt_variant": "legacy_old",
            "mimo_retry_mode": "id_repair",
            "segmentation_variant": "point_retry",
        }
    )

    if subset_name == "hard_no_ambi":
        config["mimo_retry_mode"] = "none"
        config["segmentation_variant"] = "baseline"

    if subset_policy in {
        "easy_direct_v1",
        "easy_direct_hard_occlusion_v1",
        "best_known_v1",
        "best_known_v2",
        "roborefer_v1",
        "light_review_v1",
    } and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"

    if subset_policy == "candidate_v1" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_v1" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "candidate_reasoning_json"
        config["mimo_retry_mode"] = "candidate_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_v1" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "candidate_reasoning_json"
        config["mimo_retry_mode"] = "candidate_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_v2" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_v2" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "candidate_grasp_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_v2" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "candidate_grasp_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_fewshot_v3" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_fewshot_v3" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "candidate_grasp_fewshot_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_fewshot_v3" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "candidate_grasp_fewshot_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_spatial_v4" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_spatial_v4" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "candidate_grasp_spatial_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_spatial_v4" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "candidate_grasp_spatial_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_semantic_v5" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_semantic_v5" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "candidate_grasp_semantic_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "candidate_grasp_semantic_v5" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "candidate_grasp_semantic_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "easy_direct_hard_occlusion_v1" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "hard_occlusion"
        config["mimo_retry_mode"] = "id_repair"
        if subset_name == "hard_no_ambi":
            config["segmentation_variant"] = "baseline"
        else:
            config["segmentation_variant"] = "point_retry"

    if subset_policy == "best_known_v1" and subset_name == "hard_no_ambi":
        config["prompt_variant"] = "legacy_old"
        config["mimo_retry_mode"] = "hard_review"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "best_known_v2" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "legacy_old"
        config["mimo_retry_mode"] = "target_review"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "roborefer_v1" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "roborefer_json"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "roborefer_v1" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "roborefer_json"
        config["mimo_retry_mode"] = "roborefer_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "light_review_v1" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "visible_id_guard"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "light_review_v1" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "visible_id_guard"
        config["mimo_retry_mode"] = "target_review"
        config["segmentation_variant"] = "point_retry"

    return config


def evaluate_pipeline(
    model_name="qwen3.6-flash",
    prompt_variant="legacy",
    max_output_tokens=64,
    mimo_retry_mode="none",
    segmentation_variant="baseline",
    subset_policy="none",
    reuse_molmo=True,
    resume=True,
    run_dir=None,
):
    from evaluate_common import MOLMO_OUTPUT_DIR, evaluate_subset

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = os.path.join("data/output", f"{model_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    # Always force rerun: clear old Molmo output so all scenes are re-processed
    if os.path.exists(MOLMO_OUTPUT_DIR):
        print(f"🗑️  Clearing old Molmo output: {MOLMO_OUTPUT_DIR}")
        shutil.rmtree(MOLMO_OUTPUT_DIR)
    os.makedirs(MOLMO_OUTPUT_DIR, exist_ok=True)

    subset_names = [
        "easy_no_ambi",
        "easy_yes_ambi",
        "medium_no_ambi",
        "medium_yes_ambi",
        "hard_no_ambi",
        "hard_yes_ambi",
    ]

    scores = {}
    subset_configs = {}
    for subset_name in subset_names:
        config = _subset_config(
            subset_name,
            prompt_variant,
            mimo_retry_mode,
            segmentation_variant,
            subset_policy,
        )
        subset_configs[subset_name] = config
        scores[subset_name] = evaluate_subset(
            subset_name,
            output_dir=run_dir,
            prepare_molmo=not reuse_molmo,
            model_name=model_name,
            prompt_variant=config["prompt_variant"],
            max_output_tokens=max_output_tokens,
            mimo_retry_mode=config["mimo_retry_mode"],
            segmentation_variant=config["segmentation_variant"],
            resume=resume,
        )

    summary = {
        "model": model_name,
        "prompt_variant": prompt_variant,
        "max_output_tokens": max_output_tokens,
        "mimo_retry_mode": mimo_retry_mode,
        "segmentation_variant": segmentation_variant,
        "subset_policy": subset_policy,
        "subset_configs": subset_configs,
        "molmo_cache_policy": molmo_cache_policy,
        "resume": resume,
        "timestamp": timestamp,
        "scores": scores,
    }
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=4)

    print(f"\n📊 Results saved to: {run_dir}")
    print(f"📄 Summary table: {summary_path}")
    print("\n" + "=" * 60)
    for k, v in scores.items():
        print(f"  {k:25s}: RSR {v['rsr']:.2%} | SSR {v['ssr']:.2%}")
    print("=" * 60)

    return scores


if __name__ == "__main__":
    args = parse_args()
    evaluate_pipeline(
        model_name=args.model_name,
        prompt_variant=args.prompt_variant,
        max_output_tokens=args.max_output_tokens,
        mimo_retry_mode=args.mimo_retry_mode,
        segmentation_variant=args.segmentation_variant,
        subset_policy=args.subset_policy,
        reuse_molmo=args.reuse_molmo,
        resume=args.resume,
        run_dir=args.run_dir,
    )
