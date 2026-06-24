"""Audit conservative routing on frozen Stage 1 router outputs."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from summarize_ablation_matrix import load_detail_rows, sample_key
from utils.scene_evidence import apply_conservative_route_guard


POLICIES = ("raw", "downgrade_all_risky_direct", "conservative_v1")


def _assessment(detail):
    reasoning = detail.get("reasoning", {})
    return {
        "route_mode": reasoning.get("route_mode", "target_first"),
        "route_confidence": float(reasoning.get("route_confidence", 0.0)),
        "target_object_id": reasoning.get("target_object_id"),
        "target_label": reasoning.get("target_label", detail.get("annotation", "target")),
        "ambiguity_evidence": list(reasoning.get("ambiguity_evidence", [])),
        "blocker_evidence": list(reasoning.get("blocker_evidence", [])),
    }


def _apply_policy(assessment, visible_ids, geometry, policy):
    if policy == "raw":
        return {
            **assessment,
            "pre_guard_route_mode": assessment["route_mode"],
            "route_guard_applied": False,
            "route_guard_reasons": [],
            "route_guard_variant": "none",
        }
    guarded = apply_conservative_route_guard(
        assessment,
        visible_object_ids=visible_ids,
        object_count=len(visible_ids),
        predicted_geometry=geometry,
    )
    if policy == "downgrade_all_risky_direct" and assessment["route_mode"] != "direct":
        return {
            **assessment,
            "pre_guard_route_mode": assessment["route_mode"],
            "route_guard_applied": False,
            "route_guard_reasons": [],
            "route_guard_variant": policy,
        }
    return {**guarded, "route_guard_variant": policy}


def audit_detail(detail, policy="conservative_v1"):
    reasoning = detail.get("reasoning", {})
    visible_ids = [int(value) for value in reasoning.get("visible_object_ids", [])]
    geometry = reasoning.get("candidate_geometry_features", {}) or {}
    original = _assessment(detail)
    guarded = _apply_policy(original, visible_ids, geometry, policy)
    target_id = original.get("target_object_id")
    target_relations = [
        relation
        for relation in geometry.get("relations", [])
        if target_id in {relation.get("source_id"), relation.get("target_id")}
    ]
    safe_fields = (
        "route_mode",
        "route_confidence",
        "target_object_id",
        "target_label",
        "ambiguity_evidence",
        "blocker_evidence",
        "pre_guard_route_mode",
        "route_guard_applied",
        "route_guard_reasons",
        "route_guard_variant",
        "direct_confidence_threshold",
        "direct_max_object_count",
        "target_overlap_threshold",
        "guard_code_version",
    )
    return {
        "sample_key": list(sample_key(detail)),
        "split": detail["split"],
        "subset": detail["subset"],
        "row_index": detail["row_index"],
        "scene_id": int(detail["scene_id"]),
        "object_id": int(detail["object_id"]),
        "annotation": detail.get("annotation", ""),
        "original_route": original["route_mode"],
        "guarded_route": guarded["route_mode"],
        "guarded_assessment": {
            key: guarded[key] for key in safe_fields if key in guarded
        },
        "route_confidence": original["route_confidence"],
        "target_object_id": target_id,
        "target_id_valid": target_id in visible_ids,
        "object_count": len(visible_ids),
        "ambiguity_evidence": original["ambiguity_evidence"],
        "blocker_evidence": original["blocker_evidence"],
        "target_relations": target_relations,
        "guard_reasons": guarded.get("route_guard_reasons", []),
        "evaluation_only": {
            "expected_route": {
                "easy": "direct",
                "medium": "target_first",
                "hard": "blocker_first",
            }[detail["subset"].split("_", 1)[0]],
            "rsr_correct": int(detail.get("rsr_correct", 0)),
            "ssr_correct": int(detail.get("ssr_correct", 0)),
        },
    }


def summarize_audit(rows):
    transitions = Counter(
        f"{row['original_route']}->{row['guarded_route']}" for row in rows
    )
    by_subset = defaultdict(Counter)
    for row in rows:
        by_subset[row["subset"]][row["guarded_route"]] += 1
    easy_direct = [row for row in rows if row["subset"].startswith("easy_") and row["original_route"] == "direct"]
    complex_direct = [row for row in rows if not row["subset"].startswith("easy_") and row["original_route"] == "direct"]
    return {
        "n_rows": len(rows),
        "transitions": dict(sorted(transitions.items())),
        "guarded_routes_by_subset": {
            key: dict(sorted(value.items())) for key, value in sorted(by_subset.items())
        },
        "easy_direct_retention": (
            sum(row["guarded_route"] == "direct" for row in easy_direct) / len(easy_direct)
            if easy_direct else 0.0
        ),
        "medium_hard_direct_suppression": (
            sum(row["guarded_route"] != "direct" for row in complex_direct) / len(complex_direct)
            if complex_direct else 0.0
        ),
        "expected_additional_reasoning_calls": sum(
            row["original_route"] == "direct" and row["guarded_route"] != "direct"
            for row in rows
        ),
    }


def run_audit(source_run, output_dir):
    source_run = Path(source_run)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    details = load_detail_rows(source_run)
    policies = {}
    selected_rows = None
    for policy in POLICIES:
        rows = [audit_detail(detail, policy=policy) for detail in details]
        policies[policy] = summarize_audit(rows)
        if policy == "conservative_v1":
            selected_rows = rows
    manifest = json.loads((source_run / "run_manifest.json").read_text())
    (output_dir / "audit_rows.json").write_text(
        json.dumps(selected_rows, indent=2, sort_keys=True)
    )
    (output_dir / "candidate_comparison.json").write_text(
        json.dumps({"policies": policies}, indent=2, sort_keys=True)
    )
    (output_dir / "selected_policy.json").write_text(
        json.dumps(
            {
                "policy": "conservative_v1",
                "source_manifest_id": manifest["manifest_id"],
                "cache_sha256": manifest["cache_sha256"],
                "n_rows": len(selected_rows),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return policies


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run_audit(args.source_run, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
