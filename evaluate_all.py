import argparse
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
            "target_first_grasp_planner_json",
            "target_first_grasp_planner_v7_json",
            "target_first_grasp_geometry_v8_json",
            "target_first_evidence_gate_v9_json",
            "hard_blocker_first_v10_json",
        ],
        default="legacy",
    )
    parser.add_argument("--max-output-tokens", type=int, default=64)
    parser.add_argument(
        "--mimo-retry-mode",
        choices=[
            "none",
            "original_protocol",
            "budget2_vote",
            "id_repair",
            "hard_review",
            "target_review",
            "roborefer_verify",
            "candidate_verify",
            "first_grasp_verify",
            "planner_consistency_repair",
            "geometry_consistency_repair",
        ],
        default="none",
    )
    parser.add_argument(
        "--segmentation-variant",
        choices=["baseline", "point_retry", "geometric_consistency"],
        default="baseline",
    )
    parser.add_argument(
        "--subset-policy",
        choices=[
            "none",
            "original_protocol_budget2_vote",
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
            "target_first_grasp_planner_v6",
            "target_first_grasp_planner_v7",
            "target_first_grasp_geometry_v8",
            "target_first_evidence_gate_v9",
            "hard_blocker_first_v10",
            "automatic_evidence_v1",
            "automatic_no_blocker_first",
            "automatic_no_geometry_repair",
            "automatic_no_id_repair",
            "scene_complexity_auto",
            "scene_complexity_no_blocker_first",
            "scene_complexity_no_geometry_repair",
            "scene_complexity_no_id_repair",
            "scene_complexity_vlm_auto",
            "scene_complexity_vlm_no_blocker_first",
            "scene_complexity_vlm_no_geometry_repair",
            "scene_complexity_vlm_no_id_repair",
            "depth_classifier_auto",
            "depth_classifier_no_blocker_first",
            "depth_classifier_no_geometry_repair",
            "depth_classifier_no_id_repair",
            "depth_classifier_v2_auto",
            "depth_classifier_v2_no_blocker_first",
            "depth_classifier_v2_no_geometry_repair",
            "depth_classifier_v2_no_id_repair",
            "unified_hard_safe_v1",
            "unified_hard_safe_no_hard_fallback",
            "unified_hard_safe_no_ranked_candidates",
            "unified_hard_safe_no_point_repair",
            "unified_hard_safe_no_id_repair",
            "eghc_guard_only_v1",
            "eghc_consensus_v1",
            "eghc_consensus_no_mask_repair_v1",
            "eghc_consensus_no_verifier_v1",
            "eghc_no_consensus_v1",
            "eghc_consensus_no_blocker_first_v1",
            "eghc_consensus_qwen_native_v1",
        ],
        default="none",
    )
    parser.add_argument(
        "--routing-variant",
        choices=["none", "count_only", "vlm_two_stage", "predicted_geometry", "scene_complexity", "scene_complexity_vlm", "depth_classifier", "depth_classifier_v2"],
        default="none",
    )
    parser.add_argument(
        "--feature-source",
        choices=["none", "predicted", "oracle_feature"],
        default="none",
    )
    parser.add_argument("--run-dir", default=None, help="Existing or new run directory.")
    parser.add_argument(
        "--subsets",
        nargs="+",
        choices=[
            "easy_no_ambi",
            "easy_yes_ambi",
            "medium_no_ambi",
            "medium_yes_ambi",
            "hard_no_ambi",
            "hard_yes_ambi",
        ],
        default=None,
        help="Subset names to evaluate. Defaults to all six split-0 subsets.",
    )
    parser.add_argument(
        "--max-rows-per-subset",
        type=int,
        default=None,
        help="Debug only: evaluate at most this many rows from each selected subset.",
    )
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
    routing_variant="none",
    feature_source="none",
    route_guard_variant="none",
):
    config = {
        "prompt_variant": prompt_variant,
        "mimo_retry_mode": mimo_retry_mode,
        "segmentation_variant": segmentation_variant,
        "routing_variant": routing_variant,
        "feature_source": feature_source,
        "uses_benchmark_difficulty": False,
        "uses_gt_features": False,
        "protocol_ablation": "full",
    }
    if subset_policy == "none":
        return config

    if subset_policy == "original_protocol":
        return {
            "prompt_variant": "legacy_old",
            "mimo_retry_mode": "none",
            "segmentation_variant": "baseline",
            "routing_variant": "none",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    if subset_policy == "original_protocol_budget2_vote":
        return {
            "prompt_variant": "legacy_old",
            "mimo_retry_mode": "budget2_vote",
            "segmentation_variant": "baseline",
            "routing_variant": "none",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    automatic_policies = {
        "automatic_evidence_v1": "full",
        "automatic_no_blocker_first": "no_blocker_first",
        "automatic_no_geometry_repair": "no_geometry_repair",
        "automatic_no_id_repair": "no_id_repair",
    }
    if subset_policy in automatic_policies:
        automatic_routing = (
            routing_variant if routing_variant != "none" else "predicted_geometry"
        )
        automatic_feature_source = feature_source
        if automatic_routing == "predicted_geometry" and feature_source == "none":
            automatic_feature_source = "predicted"
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": automatic_routing,
            "feature_source": automatic_feature_source,
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": automatic_policies[subset_policy],
        }

    if subset_policy == "scene_complexity_auto":
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "scene_complexity",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    scene_complexity_ablation_policies = {
        "scene_complexity_no_blocker_first": "no_blocker_first",
        "scene_complexity_no_geometry_repair": "no_geometry_repair",
        "scene_complexity_no_id_repair": "no_id_repair",
    }
    if subset_policy in scene_complexity_ablation_policies:
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "scene_complexity",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": scene_complexity_ablation_policies[subset_policy],
        }

    # VLM two-stage router policies
    if subset_policy == "scene_complexity_vlm_auto":
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "scene_complexity_vlm",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    scene_complexity_vlm_ablation_policies = {
        "scene_complexity_vlm_no_blocker_first": "no_blocker_first",
        "scene_complexity_vlm_no_geometry_repair": "no_geometry_repair",
        "scene_complexity_vlm_no_id_repair": "no_id_repair",
    }
    if subset_policy in scene_complexity_vlm_ablation_policies:
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "scene_complexity_vlm",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": scene_complexity_vlm_ablation_policies[subset_policy],
        }

    # Depth classifier router policies
    if subset_policy == "depth_classifier_auto":
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "depth_classifier",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    depth_classifier_ablation_policies = {
        "depth_classifier_no_blocker_first": "no_blocker_first",
        "depth_classifier_no_geometry_repair": "no_geometry_repair",
        "depth_classifier_no_id_repair": "no_id_repair",
    }
    if subset_policy in depth_classifier_ablation_policies:
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "depth_classifier",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": depth_classifier_ablation_policies[subset_policy],
        }

    # Depth classifier v2 router policies (target-aware)
    if subset_policy == "depth_classifier_v2_auto":
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "depth_classifier_v2",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    depth_classifier_v2_ablation_policies = {
        "depth_classifier_v2_no_blocker_first": "no_blocker_first",
        "depth_classifier_v2_no_geometry_repair": "no_geometry_repair",
        "depth_classifier_v2_no_id_repair": "no_id_repair",
    }
    if subset_policy in depth_classifier_v2_ablation_policies:
        return {
            "prompt_variant": "legacy",
            "mimo_retry_mode": "none",
            "segmentation_variant": segmentation_variant,
            "routing_variant": "depth_classifier_v2",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": depth_classifier_v2_ablation_policies[subset_policy],
        }

    # Unified hard-safe v1 policies
    if subset_policy == "unified_hard_safe_v1":
        return {
            "prompt_variant": "unified_hard_safe_v1_json",
            "mimo_retry_mode": "id_repair",
            "segmentation_variant": "point_retry",
            "routing_variant": "none",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": "full",
        }

    unified_hard_safe_ablation_policies = {
        "unified_hard_safe_no_hard_fallback": "no_hard_fallback",
        "unified_hard_safe_no_ranked_candidates": "no_ranked_candidates",
        "unified_hard_safe_no_point_repair": "no_point_repair",
        "unified_hard_safe_no_id_repair": "no_id_repair",
    }
    if subset_policy in unified_hard_safe_ablation_policies:
        ablation = unified_hard_safe_ablation_policies[subset_policy]
        return {
            "prompt_variant": "unified_hard_safe_v1_json",
            "mimo_retry_mode": "id_repair",
            "segmentation_variant": "baseline" if ablation == "no_point_repair" else "point_retry",
            "routing_variant": "none",
            "feature_source": "none",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": ablation,
        }

    # EGHC guard-only policy
    if subset_policy in {
        "eghc_guard_only_v1",
        "eghc_consensus_v1",
        "eghc_consensus_no_mask_repair_v1",
        "eghc_consensus_no_verifier_v1",
        "eghc_no_consensus_v1",
        "eghc_consensus_no_blocker_first_v1",
        "eghc_consensus_qwen_native_v1",
    }:
        no_mask_repair = subset_policy == "eghc_consensus_no_mask_repair_v1"
        no_verifier = subset_policy == "eghc_consensus_no_verifier_v1"
        no_consensus = subset_policy == "eghc_no_consensus_v1"
        no_blocker_first = subset_policy == "eghc_consensus_no_blocker_first_v1"
        return {
            "prompt_variant": (
                "eghc_qwen_native_json"
                if subset_policy == "eghc_consensus_qwen_native_v1"
                else "legacy"
            ),
            "mimo_retry_mode": "none",
            "segmentation_variant": "baseline" if no_mask_repair else "eghc_mask_repair_v1",
            "routing_variant": "evidence_gated_cascade",
            "feature_source": "deployable_predicted",
            "uses_benchmark_difficulty": False,
            "uses_gt_features": False,
            "protocol_ablation": (
                "no_mask_repair"
                if no_mask_repair
                else "no_verifier"
                if no_verifier
                else "no_consensus"
                if no_consensus
                else "no_blocker_first"
                if no_blocker_first
                else "full"
            ),
            "route_guard_variant": (
                "eghc_consensus_v1"
                if subset_policy in {
                    "eghc_consensus_v1",
                    "eghc_consensus_no_mask_repair_v1",
                    "eghc_consensus_no_verifier_v1",
                    "eghc_consensus_no_blocker_first_v1",
                    "eghc_consensus_qwen_native_v1",
                }
                else "none"
            ),
        }

    if subset_policy not in {
        "observed_best_v1",
        "original_protocol",
        "original_protocol_budget2_vote",
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
        "target_first_grasp_planner_v6",
        "target_first_grasp_planner_v7",
        "target_first_grasp_geometry_v8",
        "target_first_evidence_gate_v9",
        "hard_blocker_first_v10",
        "automatic_evidence_v1",
        "automatic_no_blocker_first",
        "automatic_no_geometry_repair",
        "automatic_no_id_repair",
        "scene_complexity_auto",
        "scene_complexity_no_blocker_first",
        "scene_complexity_no_geometry_repair",
        "scene_complexity_no_id_repair",
        "scene_complexity_vlm_auto",
        "scene_complexity_vlm_no_blocker_first",
        "scene_complexity_vlm_no_geometry_repair",
        "scene_complexity_vlm_no_id_repair",
        "depth_classifier_auto",
        "depth_classifier_no_blocker_first",
        "depth_classifier_no_geometry_repair",
        "depth_classifier_no_id_repair",
        "depth_classifier_v2_auto",
        "depth_classifier_v2_no_blocker_first",
        "depth_classifier_v2_no_geometry_repair",
        "depth_classifier_v2_no_id_repair",
        "unified_hard_safe_v1",
        "unified_hard_safe_no_hard_fallback",
        "unified_hard_safe_no_ranked_candidates",
        "unified_hard_safe_no_point_repair",
        "unified_hard_safe_no_id_repair",
        "eghc_guard_only_v1",
        "eghc_consensus_v1",
        "eghc_consensus_no_mask_repair_v1",
        "eghc_consensus_no_verifier_v1",
        "eghc_no_consensus_v1",
        "eghc_consensus_no_blocker_first_v1",
        "eghc_consensus_qwen_native_v1",
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

    if subset_policy == "target_first_grasp_planner_v6" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_planner_v6" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "target_first_grasp_planner_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_planner_v6" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "target_first_grasp_planner_json"
        config["mimo_retry_mode"] = "first_grasp_verify"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_planner_v7" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_planner_v7" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "target_first_grasp_planner_v7_json"
        config["mimo_retry_mode"] = "planner_consistency_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_planner_v7" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "target_first_grasp_planner_v7_json"
        config["mimo_retry_mode"] = "planner_consistency_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_geometry_v8" and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_geometry_v8" and subset_name.startswith("medium_"):
        config["prompt_variant"] = "target_first_grasp_geometry_v8_json"
        config["mimo_retry_mode"] = "geometry_consistency_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_grasp_geometry_v8" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "target_first_grasp_geometry_v8_json"
        config["mimo_retry_mode"] = "geometry_consistency_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy in {
        "target_first_evidence_gate_v9",
        "hard_blocker_first_v10",
    } and subset_name.startswith("easy_"):
        config["prompt_variant"] = "direct_target"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy in {
        "target_first_evidence_gate_v9",
        "hard_blocker_first_v10",
    } and subset_name.startswith("medium_"):
        config["prompt_variant"] = "target_first_evidence_gate_v9_json"
        config["mimo_retry_mode"] = "geometry_consistency_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "target_first_evidence_gate_v9" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "target_first_evidence_gate_v9_json"
        config["mimo_retry_mode"] = "id_repair"
        config["segmentation_variant"] = "point_retry"

    if subset_policy == "hard_blocker_first_v10" and subset_name.startswith("hard_"):
        config["prompt_variant"] = "hard_blocker_first_v10_json"
        config["mimo_retry_mode"] = "id_repair"
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
    routing_variant="none",
    feature_source="none",
    route_guard_variant="none",
    reuse_molmo=True,
    resume=True,
    run_dir=None,
    subsets=None,
    max_rows_per_subset=None,
):
    from evaluate_common import MOLMO_OUTPUT_DIR, evaluate_subset

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    if run_dir is None:
        run_dir = os.path.join("data/output", f"{model_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    if reuse_molmo:
        molmo_cache_policy = "reuse_existing"
    else:
        molmo_cache_policy = "regenerate_once"
        if os.path.exists(MOLMO_OUTPUT_DIR):
            print(f"Clearing old Molmo output: {MOLMO_OUTPUT_DIR}")
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
    if subsets:
        subset_names = list(subsets)

    scores = {}
    subset_configs = {}
    for subset_name in subset_names:
        config = _subset_config(
            subset_name,
            prompt_variant,
            mimo_retry_mode,
            segmentation_variant,
            subset_policy,
            routing_variant,
            feature_source,
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
            routing_variant=config["routing_variant"],
            feature_source=config["feature_source"],
            protocol_ablation=config.get("protocol_ablation", "full"),
            route_guard_variant=config.get("route_guard_variant", route_guard_variant),
            resume=resume,
            max_rows=max_rows_per_subset,
        )

    resolved_route_guard_variants = {
        config.get("route_guard_variant", route_guard_variant)
        for config in subset_configs.values()
    }
    summary_route_guard_variant = (
        next(iter(resolved_route_guard_variants))
        if len(resolved_route_guard_variants) == 1
        else route_guard_variant
    )
    def common_config_value(key, default):
        values = {
            config.get(key)
            for config in subset_configs.values()
            if config.get(key) is not None
        }
        return next(iter(values)) if len(values) == 1 else default

    summary = {
        "model": model_name,
        "prompt_variant": common_config_value("prompt_variant", prompt_variant),
        "max_output_tokens": max_output_tokens,
        "mimo_retry_mode": common_config_value("mimo_retry_mode", mimo_retry_mode),
        "segmentation_variant": common_config_value("segmentation_variant", segmentation_variant),
        "subset_policy": subset_policy,
        "routing_variant": common_config_value("routing_variant", routing_variant),
        "feature_source": common_config_value("feature_source", feature_source),
        "protocol_ablation": common_config_value("protocol_ablation", "full"),
        "route_guard_variant": summary_route_guard_variant,
        "uses_benchmark_difficulty": any(
            config["uses_benchmark_difficulty"]
            for config in subset_configs.values()
        ),
        "uses_gt_features": any(
            config["uses_gt_features"]
            for config in subset_configs.values()
        ),
        "subset_configs": subset_configs,
        "molmo_cache_policy": molmo_cache_policy,
        "resume": resume,
        "subsets": subset_names,
        "max_rows_per_subset": max_rows_per_subset,
        "timestamp": timestamp,
        "scores": scores,
    }
    summary_path = os.path.join(run_dir, "summary.json")
    with open(summary_path, "w") as f:
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
        routing_variant=args.routing_variant,
        feature_source=args.feature_source,
        reuse_molmo=args.reuse_molmo,
        resume=args.resume,
        run_dir=args.run_dir,
        subsets=args.subsets,
        max_rows_per_subset=args.max_rows_per_subset,
    )
