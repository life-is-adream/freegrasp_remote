"""Freeze overlap-triggered medium/hard samples for blocker-first replay."""

import argparse
import json
from pathlib import Path


def _blocker_evidence(reasoning):
    target_id = reasoning["target_object_id"]
    evidence = []
    for relation in reasoning["candidate_geometry_features"].get("relations", []):
        if target_id not in {relation.get("source_id"), relation.get("target_id")}:
            continue
        overlap = float(relation.get("overlap", 0.0))
        if relation.get("relation") != "overlaps" or overlap <= 0.15:
            continue
        other_id = (
            relation.get("target_id")
            if relation.get("source_id") == target_id
            else relation.get("source_id")
        )
        evidence.append(
            f"predicted overlap target id={target_id} with candidate id={other_id} "
            f"overlap={overlap:.3f} vertical_order={relation.get('vertical_order')}"
        )
    return sorted(set(evidence))


def select_rows(source_run):
    source_run = Path(source_run)
    selected = []
    for path in sorted(source_run.glob("split_*/details_*.json")):
        split = path.parent.name.removeprefix("split_")
        subset = path.stem.removeprefix("details_")
        if not subset.startswith(("medium_", "hard_")):
            continue
        for row_index, detail in enumerate(json.loads(path.read_text())):
            reasoning = detail.get("reasoning", {})
            if not (
                reasoning.get("pre_guard_route_mode") == "direct"
                and reasoning.get("route_mode") == "target_first"
                and "predicted_target_overlap"
                in reasoning.get("route_guard_reasons", [])
            ):
                continue
            evidence = _blocker_evidence(reasoning)
            if not evidence:
                raise ValueError(
                    f"Missing overlap blocker evidence for {split}/{subset}/{row_index}"
                )
            selected.append(
                {
                    "split": split,
                    "subset": subset,
                    "source_row_index": row_index,
                    "scene_id": int(detail["scene_id"]),
                    "object_id": int(detail["object_id"]),
                    "annotation": detail["annotation"],
                    "frozen_route_assessment": {
                        "route_mode": "blocker_first",
                        "route_confidence": float(
                            reasoning.get("route_confidence", 0.0)
                        ),
                        "target_object_id": int(reasoning["target_object_id"]),
                        "target_label": reasoning.get(
                            "target_label",
                            detail["annotation"],
                        ),
                        "ambiguity_evidence": list(
                            reasoning.get("ambiguity_evidence", [])
                        ),
                        "blocker_evidence": evidence,
                        "pre_guard_route_mode": "direct",
                        "route_guard_applied": True,
                        "route_guard_reasons": ["predicted_target_overlap"],
                        "route_guard_variant": "overlap_blocker_v1",
                    },
                    "baseline_target_first": {
                        "rsr_correct": int(detail["rsr_correct"]),
                        "ssr_correct": int(detail["ssr_correct"]),
                    },
                }
            )
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    rows = select_rows(args.source_run)
    manifest = json.loads(Path(args.source_manifest).read_text())
    output = {
        "variant": "overlap_blocker_v1",
        "source_run": args.source_run,
        "source_manifest_id": manifest["manifest_id"],
        "cache_sha256": manifest["cache_sha256"],
        "n_samples": len(rows),
        "baseline_rsr_count": sum(
            row["baseline_target_first"]["rsr_correct"] for row in rows
        ),
        "baseline_ssr_count": sum(
            row["baseline_target_first"]["ssr_correct"] for row in rows
        ),
        "samples": rows,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(json.dumps({k: output[k] for k in ("n_samples", "baseline_rsr_count", "baseline_ssr_count")}, indent=2))


if __name__ == "__main__":
    main()
