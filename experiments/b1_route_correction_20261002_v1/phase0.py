"""Phase 0: zero-API engineering acceptance and branch reachability.

Verifies the frozen A baseline integrity (hashes), reproduces the B1 guard
from cached deployable router evidence, computes the R trigger funnel, and
freezes the protocol. No API, no GPU, no writes outside this experiment dir.

Run: python phase0.py --root <this dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path("/home/public/zb/FreeGrasp_code-freegrasp_codex")
SOURCE = pathlib.Path(
    "/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/"
    "b1_v6_routing_split0_20260930_resume8_repaired")
DERIVED_SEAL = pathlib.Path(
    "/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/"
    "b1_v6_repair_20261002/validation/derived_integrity.json")

sys.path.insert(0, str(REPO))
from utils.eghc_router import parse_eghc_assessment, select_route  # noqa: E402

import r_policy  # noqa: E402


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_key(case_text: str) -> str:
    return hashlib.sha256(str(case_text).encode("utf-8")).hexdigest()[:24]


def write_json(path: pathlib.Path, value) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    if root.name != "b1_route_correction_20261002_v1":
        raise SystemExit("unexpected experiment root name")

    # ---- 1. Baseline integrity: every A row/mask against the repair seal ----
    derived = json.loads(DERIVED_SEAL.read_text())
    if derived.get("status") != "complete":
        raise SystemExit("derived seal not complete")
    cases = json.loads((SOURCE / "cases.json").read_text())
    if len(cases) != 300:
        raise SystemExit("case count != 300")

    hash_failures = []
    for case in cases:
        key = stable_key(case["case"])
        for rel in (f"rows/A/{key}.json", f"predictions/A/{key}.npz"):
            expected = derived["files"].get(rel)
            if expected is None or sha(SOURCE / rel) != expected:
                hash_failures.append(rel)
    if hash_failures:
        raise SystemExit(f"baseline hash failures: {hash_failures[:5]} ...")

    a_rows = {}
    for case in cases:
        key = stable_key(case["case"])
        row = json.loads((SOURCE / "rows" / "A" / f"{key}.json").read_text())
        if row.get("case") != case["case"] or row.get("arm") != "A":
            raise SystemExit(f"A row identity mismatch: {key}")
        a_rows[key] = row

    # ---- 2. Guard reproduction from cached deployable router evidence ----
    guard_mismatches = []
    plan_items = []
    funnel_I = Counter()
    funnel_O = Counter()
    for case in cases:
        key = stable_key(case["case"])
        packet = case["packet"]
        visible = [int(c["id"]) for c in packet["candidates"]]
        assessment = parse_eghc_assessment(
            case["router_output"], visible, target_label=case["annotation"])
        guard = select_route({"duplicate_mask_conflict": False}, assessment,
                             route_guard_variant="pathb_blk_arb_v1")
        a_route = a_rows[key]["selected_route"]
        if guard["selected_route"] != a_route:
            guard_mismatches.append(key)

        decision = r_policy.select_r(packet, assessment, a_route)
        if a_route == "direct":
            funnel_I[f"A=direct"] += 1
            norm = r_policy.normalize_assessment(assessment, visible)
            if len(norm["unique_target_ids"]) > 1:
                funnel_I["multiple_legal_target_ids"] += 1
            elif len(norm["unique_target_ids"]) == 0:
                funnel_I["missing_legal_target"] += 1
            elif norm["visibility"] != "free_visible":
                funnel_I["not_free_visible"] += 1
            elif norm["raw_relation_count"] > 0:
                funnel_I["relation_present"] += 1
            elif norm["confidence"] is None:
                funnel_I["confidence_unknown"] += 1
            elif norm["confidence"] < r_policy.DIRECT_CONFIDENCE:
                funnel_I["confidence_below_threshold"] += 1
            else:
                funnel_I["unique_free_safe_keep_A"] += 1
            if decision["branch"] == "I":
                funnel_I["TRIGGER_branch_I"] += 1
        elif a_route == "target_first":
            funnel_O["A=target_first"] += 1
            norm = r_policy.normalize_assessment(assessment, visible)
            if len(norm["unique_target_ids"]) != 1:
                funnel_O["reject:not_unique_target"] += 1
                continue
            funnel_O["unique_target"] += 1
            if norm["visibility"] not in r_policy.BLOCKED_VISIBILITIES:
                funnel_O["reject:not_blocked_visibility"] += 1
                continue
            funnel_O["blocked_visibility"] += 1
            conf = norm["confidence"]
            if conf is None or conf < r_policy.DIRECT_CONFIDENCE:
                funnel_O["reject:confidence_unknown_or_below"] += 1
                continue
            funnel_O["confidence_ok"] += 1
            if decision["branch"] == "O":
                funnel_O["TRIGGER_branch_O"] += 1
            else:
                funnel_O["reject:no_strong_legal_relation_to_target"] += 1
        else:
            funnel_O[f"A={a_route}_no_intervention"] += 1

        if decision["branch"] is not None:
            plan_items.append({
                "case_id": key,
                "case": case["case"],
                "scene": int(case["scene"]),
                "object": int(case["object"]),
                "annotation": case["annotation"],
                "audit_subset": case["audit_subset"],
                "a_route": a_route,
                "r_route": decision["selected_route"],
                "branch": decision["branch"],
                "guard_reasons": decision["guard_reasons"],
                "a_final_id": a_rows[key]["reasoning"].get("selected_object_id"),
                "decision_evidence": decision["evidence"],
            })

    # ---- 3. Parity report ----
    route_dist = Counter(row["selected_route"] for row in a_rows.values())
    baseline_parity = {
        "status": "PASS" if not guard_mismatches and not hash_failures else "FAIL",
        "baseline_kind": "explicit_frozen_repaired_A",
        "historical_clean_equivalent": False,
        "historical_clean_reference": {
            "ssr": "162/300 (not this baseline)", "rsr": "172/300 (not this baseline)"},
        "frozen_A_scores_reference": "161/300 SSR, 171/300 RSR (repaired, from audit 2026-10-02)",
        "cases": len(cases),
        "a_rows_verified": len(a_rows),
        "a_masks_hash_verified": len(a_rows),
        "derived_seal_source": str(DERIVED_SEAL),
        "guard_reproduction": {
            "matches": 300 - len(guard_mismatches),
            "mismatches": guard_mismatches,
            "note": "repo select_route(pathb_blk_arb_v1) on cached router_output reproduces the frozen A route for every case",
        },
        "route_distribution": dict(route_dist),
    }
    write_json(root / "baseline_parity.json", baseline_parity)

    reachability = {
        "status": "PASS",
        "method": "zero-API reachability from actual B1 guard outputs (design 3.3)",
        "branch_I_funnel": dict(funnel_I),
        "branch_O_funnel": dict(funnel_O),
        "branch_I_triggers": int(funnel_I["TRIGGER_branch_I"]),
        "branch_O_triggers": int(funnel_O["TRIGGER_branch_O"]),
        "total_interventions": len(plan_items),
        "coverage_of_300": round(len(plan_items) / 300.0, 4),
        "schema_families_seen": sorted({
            rel["schema"]
            for item in plan_items
            for rel in item["decision_evidence"]["normalized_relations"]
        }),
    }
    write_json(root / "reachability.json", reachability)
    plan_items.sort(key=lambda x: (x["branch"], x["case_id"]))
    write_json(root / "plan.json", {"status": "frozen",
                                    "work_items": plan_items,
                                    "total": len(plan_items)})

    # ---- 4. Frozen protocol ----
    code_files = ["r_policy.py", "phase0.py", "worker.py", "compose.py", "score.py"]
    protocol = {
        "experiment_id": root.name,
        "protocol_version": "route_correction_v1",
        "design_source": "FreeGrasp_B1_选择性路由纠错_实验设计与执行交接_20261002.md (design v1.1)",
        "date": "2026-10-02",
        "method": {
            "name": "constrained route correction R on frozen B1",
            "branches": {
                "I": "A=direct with identity/direct-grasp evidence risk -> target_first verification",
                "O": "A=target_first, unique target, predicted blocked, confidence>=0.75, strong legal relation to that target -> blocker_first planning",
            },
            "no_intervention": "A=blocker_first always keeps B1 final prediction; no route is ever demoted to direct",
            "threshold": 0.75,
            "policy_version": r_policy.VERSION,
        },
        "baseline": {
            "kind": "frozen repaired A from b1_v6_routing_split0_20260930_resume8_repaired",
            "historical_clean_equivalent": False,
            "verification": "baseline_parity.json",
        },
        "data": {
            "split": "split0 (300 cases, exposed development data; exploratory conclusions only)",
            "pairing_key": "sceneId + queryObjId + annotation via cases.json case text",
            "subset_usage": "audit_subset only for stratified reporting, never in policy",
        },
        "reachability": {
            "branch_I": int(funnel_I["TRIGGER_branch_I"]),
            "branch_O": int(funnel_O["TRIGGER_branch_O"]),
            "file": "reachability.json",
        },
        "models": {
            "planner": "mimo-v2.5 via token-plan endpoint",
            "adjudicator": "qwen3.6-plus via dashscope compatible-mode",
            "segmentation": "LangSAM sam1 vit_h (frozen repo settings, eghc_mask_repair_v1)",
            "prompts": "frozen repo route prompts: target_first_evidence_gate_v9_json, hard_blocker_first_v10_json; unchanged",
        },
        "arms": {
            "A": "frozen repaired A (byte-identical reuse, 0 new calls)",
            "R": "both branches + same-ID keep-A-output rule",
            "RI": "branch I only (development ablation)",
            "RO": "branch O only (development ablation)",
        },
        "submission_rules": {
            "untriggered": "byte-identical reuse of frozen A final result (hash-verified)",
            "same_final_id": "keep A mask_query/class_name/mask entirely; new reasoning recorded as verification trace",
            "different_valid_id": "submit new ID with its own new segmentation text and mask (atomic: ID+text+mask from one output)",
            "invalid_candidate": "keep A, record candidate_invalid_keep_A",
            "segmentation_failure_after_valid_plan": "official protocol failure for that row; no post-score fallback to A",
            "technical_failures": "transport/auth/unknown-status -> batch stop gate; never silently retried",
            "structural_retry": "one pre-registered fresh retry when the prediction returns no usable mask (mirrors resume8 worker)",
        },
        "budget": {
            "max_external_requests": 130,
            "max_qwen_cost_cny": 6.0,
            "max_seconds": 10800.0,
            "theoretical_call_ceiling": "31*2 + 7*3 = 83 calls (from real call graph of prior paid batches)",
            "mimo_cost_reporting": "token-plan equivalent estimate only; actual plan deduction must be confirmed by user from account records",
        },
        "metrics": {
            "primary": "R-A paired SSR difference",
            "rsr_protection": "one-sided 95% lower bound above -1pp",
            "engineering_target": "+2pp SSR net gain (target, not a prediction)",
            "bootstrap": "scene-cluster bootstrap, 10000 resamples, seed 20261002",
            "iou_threshold": 0.5,
            "iou_threshold_note": "official fixed threshold; first-step acceptable GT may include blockers",
        },
        "code_sha256": {name: sha(root / name) for name in code_files
                        if (root / name).is_file()},
        "source_sha256": {
            "cases.json": sha(SOURCE / "cases.json"),
            "derived_integrity.json": sha(DERIVED_SEAL),
            "repo/utils/eghc_router.py": sha(REPO / "utils/eghc_router.py"),
            "repo/utils/utils.py": sha(REPO / "utils/utils.py"),
            "repo/utils/eghc_adjudicator.py": sha(REPO / "utils/eghc_adjudicator.py"),
        },
    }
    write_json(root / "frozen_protocol.json", protocol)

    print(json.dumps({
        "baseline_parity": baseline_parity["status"],
        "guard_reproduction": baseline_parity["guard_reproduction"]["matches"],
        "branch_I_triggers": reachability["branch_I_triggers"],
        "branch_O_triggers": reachability["branch_O_triggers"],
        "total_interventions": reachability["total_interventions"],
        "funnel_I": reachability["branch_I_funnel"],
        "funnel_O": reachability["branch_O_funnel"],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
