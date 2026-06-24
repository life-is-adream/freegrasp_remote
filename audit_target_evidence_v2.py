"""Audit target-conditioned predicted evidence without paid inference."""

import argparse
from collections import Counter
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from experiment_manifest import hash_directory
from summarize_ablation_matrix import load_detail_rows, sample_key
from utils.scene_evidence import (
    apply_target_evidence_route_guard,
    build_target_evidence_packet,
)


def build_geometry_cache(scene_ids, geometry_provider):
    return {
        scene_id: geometry_provider(scene_id)
        for scene_id in sorted({int(value) for value in scene_ids})
    }


def audit_pilot_sample(sample, detail, geometry, molmo_to_gt):
    target_id = int(
        sample["frozen_route_assessment"]["target_object_id"]
    )
    packet = build_target_evidence_packet(
        target_id=target_id,
        visible_object_ids=sorted(int(value) for value in molmo_to_gt),
        predicted_geometry=geometry,
    )
    acceptable = {int(value) for value in detail["gt_ids"]}
    candidate_gt_ids = [
        molmo_to_gt.get(int(row["candidate_id"]))
        for row in packet["risk_candidates"]
    ]
    return {
        "sample_key": [
            str(sample["split"]),
            sample["subset"],
            int(sample["source_row_index"]),
            int(sample["scene_id"]),
            int(sample["object_id"]),
            sample["annotation"],
        ],
        "split": str(sample["split"]),
        "subset": sample["subset"],
        "scene_id": int(sample["scene_id"]),
        "object_id": int(sample["object_id"]),
        "annotation": sample["annotation"],
        "packet": packet,
        "evaluation_only": {
            "target_correct": (
                molmo_to_gt.get(target_id) == int(sample["object_id"])
            ),
            "top1_recall": bool(
                candidate_gt_ids
                and candidate_gt_ids[0] in acceptable
            ),
            "top3_recall": any(
                value in acceptable for value in candidate_gt_ids
            ),
            "acceptable_gt_ids": sorted(acceptable),
            "candidate_gt_ids": candidate_gt_ids,
        },
    }


def evaluate_gate(rows):
    keys = [tuple(row["sample_key"]) for row in rows]
    hard = [
        row for row in rows if row["subset"].startswith("hard_")
    ]
    counts = {
        "n": len(rows),
        "unique": len(set(keys)),
        "target_correct": sum(
            bool(row["evaluation_only"]["target_correct"])
            for row in rows
        ),
        "top3_recall": sum(
            bool(row["evaluation_only"]["top3_recall"])
            for row in rows
        ),
        "hard_n": len(hard),
        "hard_top3_recall": sum(
            bool(row["evaluation_only"]["top3_recall"])
            for row in hard
        ),
    }
    checks = {
        "exact_25_unique": (
            counts["n"] == 25 and counts["unique"] == 25
        ),
        "target_24_of_25": counts["target_correct"] >= 24,
        "top3_17_of_25": counts["top3_recall"] >= 17,
        "hard_4_of_8": (
            counts["hard_n"] == 8
            and counts["hard_top3_recall"] >= 4
        ),
    }
    return {
        "passed": all(checks.values()),
        "counts": counts,
        "checks": checks,
    }


def _read_molmo_id_file(path):
    parsed_data = []
    molmo_to_gt = {}
    lines = Path(path).read_text().strip().splitlines()
    for line in lines[1:]:
        object_id, x, y, gt_id = (int(value) for value in line.split())
        parsed_data.append((object_id, x, y, 0))
        molmo_to_gt[object_id] = gt_id
    return parsed_data, molmo_to_gt


def _load_depth_map(depth_root, scene_id):
    if not depth_root:
        return None
    path = Path(depth_root) / f"{scene_id}.npz"
    if not path.exists():
        return None
    with np.load(path, allow_pickle=True) as data:
        if "depth" not in data:
            return None
        return np.asarray(data["depth"])


def _json_safe(value):
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _detail_for_sample(source_run, sample):
    path = (
        Path(source_run)
        / f"split_{sample['split']}"
        / f"details_{sample['subset']}.json"
    )
    details = json.loads(path.read_text())
    index = int(sample["source_row_index"])
    if not 0 <= index < len(details):
        raise IndexError(f"Pilot source row out of range: {path}:{index}")
    detail = details[index]
    identity = (
        int(detail["scene_id"]),
        int(detail["object_id"]),
        detail["annotation"],
    )
    expected = (
        int(sample["scene_id"]),
        int(sample["object_id"]),
        sample["annotation"],
    )
    if identity != expected:
        raise ValueError(
            f"Pilot source identity mismatch: {identity} != {expected}"
        )
    return detail


def _route_assessment(detail):
    reasoning = detail.get("reasoning", {})
    pre_guard = reasoning.get("pre_guard_route_assessment")
    if isinstance(pre_guard, dict):
        return {
            "route_mode": pre_guard.get(
                "route_mode",
                reasoning.get("route_mode", "target_first"),
            ),
            "route_confidence": float(
                pre_guard.get(
                    "route_confidence",
                    reasoning.get("route_confidence", 0.0),
                )
            ),
            "target_object_id": pre_guard.get(
                "target_object_id",
                reasoning.get("target_object_id"),
            ),
            "target_label": pre_guard.get(
                "target_label",
                reasoning.get("target_label", detail["annotation"]),
            ),
            "ambiguity_evidence": list(
                pre_guard.get(
                    "ambiguity_evidence",
                    reasoning.get("ambiguity_evidence", []),
                )
            ),
            "blocker_evidence": list(
                pre_guard.get(
                    "blocker_evidence",
                    reasoning.get("blocker_evidence", []),
                )
            ),
        }
    return {
        "route_mode": reasoning.get("route_mode", "target_first"),
        "route_confidence": float(
            reasoning.get("route_confidence", 0.0)
        ),
        "target_object_id": reasoning.get("target_object_id"),
        "target_label": reasoning.get(
            "target_label",
            detail["annotation"],
        ),
        "ambiguity_evidence": list(
            reasoning.get("ambiguity_evidence", [])
        ),
        "blocker_evidence": list(
            reasoning.get("blocker_evidence", [])
        ),
    }


def summarize_pilot(rows):
    hard = [
        row for row in rows if row["subset"].startswith("hard_")
    ]
    medium = [
        row for row in rows if row["subset"].startswith("medium_")
    ]
    inclusion_reasons = Counter(
        candidate["included_by"]
        for row in rows
        for candidate in row["packet"]["risk_candidates"]
    )
    return {
        "n": len(rows),
        "target_correct": sum(
            row["evaluation_only"]["target_correct"] for row in rows
        ),
        "top1_recall": sum(
            row["evaluation_only"]["top1_recall"] for row in rows
        ),
        "top3_recall": sum(
            row["evaluation_only"]["top3_recall"] for row in rows
        ),
        "medium_n": len(medium),
        "medium_top3_recall": sum(
            row["evaluation_only"]["top3_recall"]
            for row in medium
        ),
        "hard_n": len(hard),
        "hard_top3_recall": sum(
            row["evaluation_only"]["top3_recall"] for row in hard
        ),
        "duplicate_mask_sample_count": sum(
            bool(row["packet"]["duplicate_mask_candidates"])
            for row in rows
        ),
        "nearest_fallback_sample_count": sum(
            any(
                candidate["included_by"] == "nearest_fallback"
                for candidate in row["packet"]["risk_candidates"]
            )
            for row in rows
        ),
        "candidate_inclusion_reasons": dict(
            sorted(inclusion_reasons.items())
        ),
    }


def audit_full_rows(details, geometry_cache, mappings):
    rows = []
    for detail in details:
        reasoning = detail.get("reasoning", {})
        target_id = reasoning.get("target_object_id")
        scene_id = int(detail["scene_id"])
        geometry = geometry_cache[scene_id]
        visible_ids = sorted(mappings[scene_id])
        packet = build_target_evidence_packet(
            target_id=target_id,
            visible_object_ids=visible_ids,
            predicted_geometry=geometry,
        )
        assessment = _route_assessment(detail)
        guarded = apply_target_evidence_route_guard(
            assessment,
            visible_object_ids=visible_ids,
            object_count=len(visible_ids),
            target_evidence_packet=packet,
        )
        rows.append(
            {
                "sample_key": list(sample_key(detail)),
                "split": detail["split"],
                "subset": detail["subset"],
                "scene_id": scene_id,
                "original_route": assessment["route_mode"],
                "guarded_route": guarded["route_mode"],
                "packet_reliability": packet[
                    "evidence_reliability"
                ],
                "depth_source": geometry.get("depth_source", "unknown"),
                "depth_occlusion_candidate_count": sum(
                    bool(row.get("depth_occlusion_suspect"))
                    for row in packet["risk_candidates"]
                ),
                "risk_candidate_count": len(
                    packet["risk_candidates"]
                ),
                "duplicate_mask_count": len(
                    packet["duplicate_mask_candidates"]
                ),
            }
        )
    return rows


def summarize_full(rows):
    keys = [tuple(row["sample_key"]) for row in rows]
    transitions = Counter(
        f"{row['original_route']}->{row['guarded_route']}"
        for row in rows
    )
    reliability = Counter(
        row["packet_reliability"] for row in rows
    )
    depth_sources = Counter(row["depth_source"] for row in rows)
    return {
        "n": len(rows),
        "unique_samples": len(set(keys)),
        "transitions": dict(sorted(transitions.items())),
        "packet_reliability": dict(sorted(reliability.items())),
        "depth_sources": dict(sorted(depth_sources.items())),
        "samples_with_depth_occlusion_candidates": sum(
            row["depth_occlusion_candidate_count"] > 0 for row in rows
        ),
        "samples_with_risk_candidates": sum(
            row["risk_candidate_count"] > 0 for row in rows
        ),
        "samples_with_duplicate_masks": sum(
            row["duplicate_mask_count"] > 0 for row in rows
        ),
    }


def _load_or_build_geometry(
    *,
    scene_ids,
    dataset,
    molmo_root,
    depth_root,
    geometry_cache_dir,
):
    from utils.utils import langsam_actor
    from utils.scene_evidence import predict_geometry_from_molmo_points

    geometry_cache_dir.mkdir(parents=True, exist_ok=True)
    image_by_scene = {}
    for _, row in dataset.iterrows():
        scene_id = int(row["sceneId"])
        if scene_id not in image_by_scene:
            image_by_scene[scene_id] = row["image"]["bytes"]

    mappings = {}

    def provider(scene_id):
        id_path = (
            Path(molmo_root)
            / f"scene{scene_id}"
            / f"{scene_id}_id.txt"
        )
        parsed_data, molmo_to_gt = _read_molmo_id_file(id_path)
        mappings[scene_id] = molmo_to_gt
        cache_path = geometry_cache_dir / f"scene{scene_id}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())
        image = Image.open(
            io.BytesIO(image_by_scene[scene_id])
        ).convert("RGB")
        depth_map = _load_depth_map(depth_root, scene_id)
        predictor = getattr(langsam_actor, "sam", None)
        if predictor is None:
            raise RuntimeError("LangSAM SAM predictor is unavailable")
        geometry = predict_geometry_from_molmo_points(
            image,
            parsed_data,
            predictor=predictor,
            depth_map=depth_map,
        )
        cache_path.write_text(
            json.dumps(
                _json_safe(geometry),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return geometry

    geometry = build_geometry_cache(scene_ids, provider)
    for scene_id in geometry:
        if scene_id not in mappings:
            id_path = (
                Path(molmo_root)
                / f"scene{scene_id}"
                / f"{scene_id}_id.txt"
            )
            _parsed, mappings[scene_id] = _read_molmo_id_file(
                id_path
            )
    return geometry, mappings


def _write_report(
    path,
    *,
    command,
    cache_sha256,
    pilot_summary,
    full_summary,
    gate,
):
    next_action = (
        "Prepare the frozen 25-sample paid pilot, but do not run it "
        "without new approval."
        if gate["passed"]
        else "Stop RGB-only development and design depth-aware occlusion."
    )
    lines = [
        "# Target Evidence V2 Offline Audit",
        "",
        "## Command",
        "",
        "```bash",
        command,
        "```",
        "",
        "## Provenance",
        "",
        f"- Molmo cache SHA-256: `{cache_sha256}`",
        "- Paid inference: none",
        "- Geometry source: point-prompted SAM masks",
        "",
        "## Pilot Recall",
        "",
        f"- Target accuracy: {pilot_summary['target_correct']}/"
        f"{pilot_summary['n']}",
        f"- Top-1 blocker recall: {pilot_summary['top1_recall']}/"
        f"{pilot_summary['n']}",
        f"- Top-3 blocker recall: {pilot_summary['top3_recall']}/"
        f"{pilot_summary['n']}",
        f"- Medium top-3 recall: "
        f"{pilot_summary['medium_top3_recall']}/"
        f"{pilot_summary['medium_n']}",
        f"- Hard top-3 recall: {pilot_summary['hard_top3_recall']}/"
        f"{pilot_summary['hard_n']}",
        f"- Samples with duplicate-mask warnings: "
        f"{pilot_summary['duplicate_mask_sample_count']}",
        f"- Samples using nearest fallback: "
        f"{pilot_summary['nearest_fallback_sample_count']}",
        "",
        "## Full S4 Coverage",
        "",
        f"- Rows: {full_summary['n']}",
        f"- Unique samples: {full_summary['unique_samples']}",
        f"- Samples with risk candidates: "
        f"{full_summary['samples_with_risk_candidates']}",
        f"- Depth sources: `{json.dumps(full_summary['depth_sources'], sort_keys=True)}`",
        f"- Samples with depth-occlusion candidates: "
        f"{full_summary['samples_with_depth_occlusion_candidates']}",
        f"- Samples with duplicate masks: "
        f"{full_summary['samples_with_duplicate_masks']}",
        f"- Route transitions: `{json.dumps(full_summary['transitions'], sort_keys=True)}`",
        "",
        "## Gate",
        "",
        f"- Passed: `{str(gate['passed']).lower()}`",
    ]
    for name, passed in gate["checks"].items():
        lines.append(f"- {name}: `{str(passed).lower()}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "This audit measures only whether predicted evidence "
                "contains acceptable first-grasp candidates. It does not "
                "estimate new RSR or SSR."
            ),
            "",
            "## Next Action",
            "",
            next_action,
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def run_audit(args):
    from evaluate_common import load_dataset

    pilot = json.loads(Path(args.pilot_manifest).read_text())
    pilot_samples = pilot["samples"]
    full_details = load_detail_rows(args.full_source_run)
    scene_ids = [
        int(sample["scene_id"]) for sample in pilot_samples
    ] + [int(detail["scene_id"]) for detail in full_details]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    geometry_cache, mappings = _load_or_build_geometry(
        scene_ids=scene_ids,
        dataset=load_dataset(),
        molmo_root=args.molmo_root,
        depth_root=args.depth_root,
        geometry_cache_dir=output_dir / "geometry_cache",
    )

    pilot_rows = []
    for sample in pilot_samples:
        scene_id = int(sample["scene_id"])
        detail = _detail_for_sample(
            args.pilot_source_run,
            sample,
        )
        pilot_rows.append(
            audit_pilot_sample(
                sample,
                detail,
                geometry_cache[scene_id],
                mappings[scene_id],
            )
        )
    pilot_summary = summarize_pilot(pilot_rows)
    gate = evaluate_gate(pilot_rows)
    full_rows = audit_full_rows(
        full_details,
        geometry_cache,
        mappings,
    )
    full_summary = summarize_full(full_rows)

    if full_summary["n"] != 900:
        raise RuntimeError(
            f"Expected 900 full rows, got {full_summary['n']}"
        )
    if full_summary["unique_samples"] != 900:
        raise RuntimeError(
            "Full audit does not contain 900 unique samples"
        )

    (output_dir / "pilot_rows.json").write_text(
        json.dumps(pilot_rows, indent=2, sort_keys=True)
    )
    (output_dir / "pilot_summary.json").write_text(
        json.dumps(pilot_summary, indent=2, sort_keys=True)
    )
    (output_dir / "full_coverage.json").write_text(
        json.dumps(full_summary, indent=2, sort_keys=True)
    )
    (output_dir / "gate.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True)
    )
    cache_sha256 = hash_directory(args.molmo_root)
    command = (
        "CUDA_VISIBLE_DEVICES=0 .venv/bin/python "
        "audit_target_evidence_v2.py "
        f"--pilot-manifest {args.pilot_manifest} "
        f"--pilot-source-run {args.pilot_source_run} "
        f"--full-source-run {args.full_source_run} "
        f"--molmo-root {args.molmo_root} "
        f"--depth-root {args.depth_root} "
        f"--output-dir {args.output_dir} "
        f"--report {args.report}"
    )
    _write_report(
        Path(args.report),
        command=command,
        cache_sha256=cache_sha256,
        pilot_summary=pilot_summary,
        full_summary=full_summary,
        gate=gate,
    )
    return {
        "pilot_summary": pilot_summary,
        "full_summary": full_summary,
        "gate": gate,
        "cache_sha256": cache_sha256,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-manifest", required=True)
    parser.add_argument("--pilot-source-run", required=True)
    parser.add_argument("--full-source-run", required=True)
    parser.add_argument("--molmo-root", required=True)
    parser.add_argument("--depth-root", default="data/npz_file")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run_audit(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
