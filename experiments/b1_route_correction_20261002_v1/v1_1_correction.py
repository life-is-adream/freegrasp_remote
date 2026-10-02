"""v1.1 derived correction: protocol-faithful same-ID rule application.

Root cause found during post-batch diagnosis (2026-10-02), affecting exactly
one row (easy_yes_ambi:976:1:10, branch I):

1. Worker infrastructure bug: the mask-cache adapter wrote npz key 'mask' but
   load_cache read 'masks'; a duplicate identical segmentation query re-read
   the just-written cache file and raised KeyError('masks is not a file in the
   archive'). This is an infrastructure error, not an official algorithm
   segmentation failure.
2. Rule-application deviation: the pre-registered same_final_id rule (design
   3.4, frozen_protocol.json) is UNCONDITIONAL - when the new plan's final ID
   equals A's final ID, A's mask_query/class_name/mask outputs are kept
   entirely. The worker classifier additionally required a usable new mask
   before applying the same-ID rule, which deviates from the frozen rule.

Correction (derived version; sealed v1.0 artifacts are NOT modified, no
prediction is re-run, no score is recomputed from new calls):
- rows_v1_1/ mirrors rows/ with the affected row re-classified under the
  pre-registered same-ID rule (R and RI; RO does not contain branch I).
- score_v1_1.json re-scores the corrected composition with the same frozen
  scorer functions.
- Per-row scoring files for BOTH versions are exported (design section 9
  deliverable: per-row and summary scoring files).

Run: python v1_1_correction.py --root <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/home/public/zb/FreeGrasp_code-freegrasp_codex")

import score as SC  # noqa: E402  (frozen scorer functions)

AFFECTED_CASE_PREFIX = "easy_yes_ambi:976:1:10"


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    if pathlib.Path(args.root).resolve() != ROOT:
        raise SystemExit("root mismatch")

    cases = json.loads((SC.SOURCE / "cases.json").read_text())
    derived = json.loads(SC.DERIVED_SEAL.read_text())
    sealed_score = json.loads((ROOT / "score.json").read_text())
    if sealed_score.get("status") != "complete":
        raise SystemExit("sealed score not complete")

    def key(case_text: str) -> str:
        return SC.stable_key(case_text)

    case_by_key = {key(c["case"]): c for c in cases}

    # Locate the affected branch prediction and its frozen A row.
    affected_key = None
    bp = None
    for path in (ROOT / "branch_predictions").glob("*.json"):
        record = json.loads(path.read_text())
        if record["case"] == AFFECTED_CASE_PREFIX:
            affected_key, bp = record["case_id"], record
            break
    if affected_key is None:
        raise SystemExit("affected case not found in branch predictions")
    if bp["valid_new_id"] is not True or bp["new_final_id"] != bp["a_final_id"]:
        raise SystemExit("affected row does not satisfy the same-ID condition")

    a_row = json.loads((SC.SOURCE / "rows" / "A" / f"{affected_key}.json").read_text())
    mask_rel = a_row["mask_path"]
    a_mask = {"root": str(SC.SOURCE), "path": mask_rel,
              "sha256": derived["files"][mask_rel]}

    # ---- Build rows_v1_1: verbatim copy + corrected affected row ----
    diff_rows = []
    for arm in ("R", "RI", "RO"):
        for case in cases:
            k = key(case["case"])
            src = ROOT / "rows" / arm / f"{k}.json"
            row = json.loads(src.read_text())
            if k == affected_key and arm in ("R", "RI"):
                if row.get("outcome") != "segmentation_failure_official_failure":
                    raise SystemExit("unexpected v1.0 outcome for affected row")
                row = dict(row)
                row["outcome"] = "same_id_keep_A_outputs"
                row["provenance"] = "shared_frozen_A_keep_A_rule"
                row["reasoning"] = a_row["reasoning"]
                row["mask"] = a_mask
                row.pop("failure_reason", None)
                row["submitted_selected_object_id"] = a_row["reasoning"].get("selected_object_id")
                row["submitted_mask_query"] = a_row["reasoning"].get("mask_query")
                row["submitted_class_name"] = a_row["reasoning"].get("class_name")
                row["v1_1_correction"] = {
                    "v1_0_outcome": "segmentation_failure_official_failure",
                    "rule": "pre-registered same_final_id rule (design 3.4) is unconditional: new plan final ID == A final ID -> keep A outputs entirely",
                    "new_plan_final_id": bp["new_final_id"],
                    "new_segmentation_error": bp["prediction_reasoning"].get("failure_reason"),
                    "root_cause": "worker mask-cache adapter schema mismatch (wrote 'mask', read 'masks'); duplicate identical segmentation query re-read the just-written cache and raised KeyError; infrastructure error, not an official algorithm failure",
                    "re_run": False,
                }
                diff_rows.append(f"{arm}:{k}")
            write_json(ROOT / "rows_v1_1" / arm / f"{k}.json", row)

    # ---- Score both versions with the frozen scorer functions ----
    gt = SC.load_gt_rows()
    gt_cache: dict[int, np.ndarray] = {}

    def gt_masks(scene: int) -> np.ndarray:
        if scene not in gt_cache:
            data = np.load(SC.REPO / "data/npz_file" / f"{scene}.npz", allow_pickle=True)
            gt_cache[scene] = (data["instances_objects.npy"] if "instances_objects.npy" in data
                               else data["instances_objects"])
        return gt_cache[scene]

    def load_rows(subdir: str, arm: str) -> dict:
        return {key(c["case"]): json.loads((ROOT / subdir / arm / f"{key(c['case'])}.json").read_text())
                for c in cases}

    def score_arm(rows: dict) -> dict:
        out = {}
        for case in cases:
            k = key(case["case"])
            gk = (int(case["scene"]), int(case["object"]), str(case["annotation"]))
            out[k] = SC.score_row(rows[k], case, gt[gk], gt_masks(int(case["scene"])))
        return out

    a_rows = SC.load_arm_a(cases, derived)
    scored_a = score_arm(a_rows)
    a_ssr = sum(r["ssr"] for r in scored_a.values())
    a_rsr = sum(r["rsr"] for r in scored_a.values())
    if (a_ssr, a_rsr) != (161, 171):
        raise SystemExit(f"A self-check failed: {a_ssr}/{a_rsr}")

    scored_v10 = {arm: score_arm(load_rows("rows", arm)) for arm in ("R", "RI", "RO")}
    scored_v11 = {arm: score_arm(load_rows("rows_v1_1", arm)) for arm in ("R", "RI", "RO")}

    # v1.0 reproduction check against the sealed summary.
    for arm, (ssr, rsr) in {"R": (162, 173), "RI": (162, 173), "RO": (161, 171)}.items():
        got = (sum(r["ssr"] for r in scored_v10[arm].values()),
               sum(r["rsr"] for r in scored_v10[arm].values()))
        if got != (ssr, rsr):
            raise SystemExit(f"v1.0 reproduction mismatch for {arm}: {got}")

    # v1.0 -> v1.1 diff must be exactly the affected row in R and RI.
    for arm in ("R", "RI", "RO"):
        changed = {k for k in scored_v10[arm]
                   if scored_v10[arm][k]["ssr"] != scored_v11[arm][k]["ssr"]
                   or scored_v10[arm][k]["rsr"] != scored_v11[arm][k]["rsr"]}
        expected = {affected_key} if arm in ("R", "RI") else set()
        if changed != expected:
            raise SystemExit(f"unexpected v1.1 diff for {arm}: {sorted(changed)}")

    # ---- Per-row scoring exports (design section 9) ----
    def export_line(arm: str, row: dict, sr: dict, case: dict) -> dict:
        reasoning = row.get("reasoning") or {}
        mask = row.get("mask") or {}
        return {
            "arm": arm, "case_id": sr["case_id"], "case": case["case"],
            "scene": int(case["scene"]), "object": int(case["object"]),
            "annotation": case["annotation"], "subset": case["audit_subset"],
            "a_route": row.get("a_route") or row.get("selected_route"),
            "route": row.get("selected_route"),
            "prompt_variant": reasoning.get("prompt_variant"),
            "branch": row.get("branch"), "outcome": row.get("outcome"),
            "a_final_id": row.get("a_final_id"),
            "submitted_id": sr["selected_id"], "mapped_id": sr["mapped_id"],
            "mask_query": reasoning.get("mask_query"),
            "class_name": reasoning.get("class_name"),
            "mask_sha256": mask.get("sha256"),
            "iou": round(sr["iou"], 6), "ssr": sr["ssr"], "rsr": sr["rsr"],
            "external_calls": int(row.get("external_calls", 0)),
        }

    for name, scored_map in (("score_rows.jsonl", scored_v10), ("score_rows_v1_1.jsonl", scored_v11)):
        with (ROOT / name).open("w", encoding="utf-8") as handle:
            for case in cases:
                k = key(case["case"])
                handle.write(json.dumps(export_line("A", a_rows[k], scored_a[k], case),
                                        ensure_ascii=False) + "\n")
                for arm in ("R", "RI", "RO"):
                    rows_src = load_rows("rows" if name.startswith("score_rows.jsonl") else "rows_v1_1", arm)
                    handle.write(json.dumps(export_line(arm, rows_src[k], scored_map[arm][k], case),
                                            ensure_ascii=False) + "\n")

    # ---- v1.1 score summary ----
    arms_summary = {"A": SC.summarize("A", scored_a)}
    for arm in ("R", "RI", "RO"):
        arms_summary[arm] = SC.summarize(arm, scored_v11[arm])
    comparisons = {
        "A_vs_R": SC.paired(scored_a, scored_v11["R"]),
        "A_vs_RI": SC.paired(scored_a, scored_v11["RI"]),
        "A_vs_RO": SC.paired(scored_a, scored_v11["RO"]),
    }
    ssr_ci = comparisons["A_vs_R"]["ssr"]["scene_cluster_95ci_pp"]
    net = comparisons["A_vs_R"]["ssr"]["net"]
    if ssr_ci[0] > 0:
        verdict = "slight_improvement" if net < 6 else "improved"
    elif net < 0 and ssr_ci[1] < 0:
        verdict = "failed"
    else:
        verdict = "not_demonstrated"

    by_branch: dict = {}
    for branch_label in ("I", "O", None):
        label = branch_label or "none"
        bucket = {"n": 0, "a_ssr": 0, "r_ssr": 0, "a_rsr": 0, "r_rsr": 0}
        for k, row in scored_v11["R"].items():
            if row["branch"] == branch_label:
                bucket["n"] += 1
                bucket["a_ssr"] += scored_a[k]["ssr"]
                bucket["r_ssr"] += row["ssr"]
                bucket["a_rsr"] += scored_a[k]["rsr"]
                bucket["r_rsr"] += row["rsr"]
        by_branch[label] = bucket

    result = {
        "status": "complete",
        "experiment_id": ROOT.name,
        "version": "v1.1 (derived correction; sealed v1.0 untouched)",
        "correction": {
            "affected_case": AFFECTED_CASE_PREFIX,
            "affected_arms": ["R", "RI"],
            "v1_0_outcome": "segmentation_failure_official_failure",
            "v1_1_outcome": "same_id_keep_A_outputs",
            "rule": "pre-registered same_final_id rule applied unconditionally (design 3.4)",
            "root_cause": "worker mask-cache adapter schema mismatch (wrote 'mask', read 'masks'); infrastructure error, not an official algorithm failure",
            "re_run": False,
            "sealed_files_modified": False,
            "v1_0_reference": {
                "R": {"ssr": sealed_score["arms"]["R"]["ssr"], "rsr": sealed_score["arms"]["R"]["rsr"]},
                "RI": {"ssr": sealed_score["arms"]["RI"]["ssr"], "rsr": sealed_score["arms"]["RI"]["rsr"]},
                "RO": {"ssr": sealed_score["arms"]["RO"]["ssr"], "rsr": sealed_score["arms"]["RO"]["rsr"]},
            },
        },
        "denominator": 300,
        "arms": arms_summary,
        "comparisons": comparisons,
        "branch_stratification": by_branch,
        "cost": sealed_score["cost"],
        "decision_rules": sealed_score["decision_rules"],
        "bootstrap": sealed_score["bootstrap"],
        "claim_boundary": sealed_score["claim_boundary"],
        "verdict": verdict,
    }
    write_json(ROOT / "score_v1_1.json", result)

    print(json.dumps({
        "correction_rows": diff_rows,
        "v1_0": {arm: [sum(r["ssr"] for r in scored_v10[arm].values()),
                       sum(r["rsr"] for r in scored_v10[arm].values())] for arm in ("R", "RI", "RO")},
        "v1_1": {arm: [sum(r["ssr"] for r in scored_v11[arm].values()),
                       sum(r["rsr"] for r in scored_v11[arm].values())] for arm in ("R", "RI", "RO")},
        "A": [a_ssr, a_rsr],
        "A_vs_R_v1_1_ssr": comparisons["A_vs_R"]["ssr"],
        "A_vs_R_v1_1_rsr": comparisons["A_vs_R"]["rsr"],
        "verdict_v1_1": verdict,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
