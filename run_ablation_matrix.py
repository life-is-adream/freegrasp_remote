"""Generate approval-gated FreeGrasp ablation commands."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess


@dataclass(frozen=True)
class ExperimentSpec:
    run_id: str
    stage: int
    subset_policy: str
    routing_variant: str
    segmentation_variant: str
    feature_source: str
    max_output_tokens: int = 1024
    replay_source: str | None = None
    fresh_molmo: bool = False


def experiment_registry():
    return [
        ExperimentSpec("S0", 1, "original_protocol", "none", "baseline", "none"),
        ExperimentSpec("S1", 1, "hard_blocker_first_v10", "none", "point_retry", "oracle_feature"),
        ExperimentSpec("S2", 1, "automatic_evidence_v1", "count_only", "point_retry", "none"),
        ExperimentSpec("S3", 1, "automatic_evidence_v1", "vlm_two_stage", "point_retry", "none"),
        ExperimentSpec("S4", 1, "automatic_evidence_v1", "predicted_geometry", "geometric_consistency", "predicted"),
        ExperimentSpec("S5", 1, "automatic_no_blocker_first", "predicted_geometry", "geometric_consistency", "predicted"),
        ExperimentSpec("S6", 1, "automatic_no_geometry_repair", "predicted_geometry", "geometric_consistency", "predicted"),
        ExperimentSpec("S7", 1, "automatic_no_id_repair", "predicted_geometry", "geometric_consistency", "predicted"),
        ExperimentSpec("S8", 1, "scene_complexity_auto", "scene_complexity", "point_retry", "none"),
        ExperimentSpec("S9", 1, "scene_complexity_no_blocker_first", "scene_complexity", "point_retry", "none"),
        ExperimentSpec("S10", 1, "scene_complexity_no_geometry_repair", "scene_complexity", "point_retry", "none"),
        ExperimentSpec("S11", 1, "scene_complexity_no_id_repair", "scene_complexity", "point_retry", "none"),
        # VLM two-stage router experiments (paid inference)
        ExperimentSpec("V1", 1, "scene_complexity_vlm_auto", "scene_complexity_vlm", "point_retry", "none"),
        ExperimentSpec("V2", 1, "scene_complexity_vlm_no_blocker_first", "scene_complexity_vlm", "point_retry", "none"),
        ExperimentSpec("V3", 1, "scene_complexity_vlm_no_geometry_repair", "scene_complexity_vlm", "point_retry", "none"),
        ExperimentSpec("V4", 1, "scene_complexity_vlm_no_id_repair", "scene_complexity_vlm", "point_retry", "none"),
        ExperimentSpec("F0", 2, "original_protocol", "none", "baseline", "none", fresh_molmo=True),
        ExperimentSpec("F1", 2, "automatic_evidence_v1", "predicted_geometry", "geometric_consistency", "predicted"),
        ExperimentSpec("F2", 2, "hard_blocker_first_v10", "none", "point_retry", "oracle_feature"),
        ExperimentSpec("F3", 2, "frozen_reasoning_replay", "none", "geometric_consistency", "none", replay_source="F1"),
    ]


def command_for(spec, run_root, cache_sha256):
    run_root = Path(run_root)
    if spec.replay_source:
        source = run_root.parent / spec.replay_source
        commands = []
        for variant in ("baseline", "geometric_consistency"):
            output = run_root / variant
            command = [
                "python",
                "replay_segmentation.py",
                "--source-run",
                str(source),
                "--output-run",
                str(output),
                "--segmentation-variant",
                variant,
            ]
            commands.append(shlex.join(command))
        return " && ".join(commands)

    command = [
        "python",
        "evaluate_mimo_full_protocol.py",
        "--model-name",
        "mimo-v2.5",
        "--max-output-tokens",
        str(spec.max_output_tokens),
        "--subset-policy",
        spec.subset_policy,
        "--routing-variant",
        spec.routing_variant,
        "--feature-source",
        spec.feature_source,
        "--segmentation-variant",
        spec.segmentation_variant,
        "--run-root",
        str(run_root),
        "--splits",
        "0",
        "1",
        "2",
    ]
    if spec.fresh_molmo:
        command.append("--fresh-molmo")
    else:
        command.extend(["--expected-cache-sha256", cache_sha256, "--reuse-molmo"])
    return shlex.join(command)


def validate_execution_gate(execute, confirmation):
    if execute and confirmation != "RUN_PAID_INFERENCE":
        raise ValueError(
            "--execute requires --confirm-paid-inference RUN_PAID_INFERENCE"
        )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=[1, 2], required=True)
    parser.add_argument("--run-root", default="data/output/ablation_matrix")
    parser.add_argument("--cache-sha256", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-paid-inference")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        validate_execution_gate(args.execute, args.confirm_paid_inference)
    except ValueError as error:
        build_parser().error(str(error))

    specs = [spec for spec in experiment_registry() if spec.stage == args.stage]
    commands = [
        command_for(
            spec,
            Path(args.run_root) / spec.run_id,
            args.cache_sha256,
        )
        for spec in specs
    ]
    for spec, command in zip(specs, commands):
        print(f"[{spec.run_id}] {command}")

    if args.execute:
        for command in commands:
            subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    main()
