"""Zero-API composition of arms R / RI / RO from frozen A and branch predictions.

Branches are disjoint under the A route, so the pre-registered ablations are
composed from the same frozen A plus each branch's saved predictions (design
section 4). Untriggered rows reuse the frozen A final result byte-identically
(hash-verified references, no re-dispatch).

Run: python compose.py --root <dir>   (after worker phases complete)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

O = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path(
    "/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/"
    "b1_v6_routing_split0_20260930_resume8_repaired")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_key(case_text: str) -> str:
    return hashlib.sha256(str(case_text).encode("utf-8")).hexdigest()[:24]


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    if root != O:
        raise SystemExit("root mismatch")

    cases = json.loads((SOURCE / "cases.json").read_text())
    plan = json.loads((O / "plan.json").read_text())
    triggered = {item["case_id"]: item for item in plan["work_items"]}

    missing = [k for k in triggered if not (O / "branch_predictions" / f"{k}.json").is_file()]
    if missing:
        raise SystemExit(f"branch predictions incomplete: {len(missing)} missing, "
                         f"first={missing[:3]}")

    predictions = {}
    for key in triggered:
        predictions[key] = json.loads((O / "branch_predictions" / f"{key}.json").read_text())

    counts = {arm: {"shared_frozen_A": 0, "new_prediction": 0, "official_failure": 0}
              for arm in ("R", "RI", "RO")}
    outcomes = {arm: {} for arm in ("R", "RI", "RO")}

    for case in cases:
        key = stable_key(case["case"])
        a_row = json.loads((SOURCE / "rows" / "A" / f"{key}.json").read_text())
        a_reasoning = a_row["reasoning"]
        a_mask = {"root": str(SOURCE), "path": a_row["mask_path"],
                  "sha256": sha(SOURCE / a_row["mask_path"])}

        for arm in ("R", "RI", "RO"):
            item = triggered.get(key)
            record = predictions.get(key)
            active = (
                record is not None
                and ((arm == "R") or (arm == "RI" and record["branch"] == "I")
                     or (arm == "RO" and record["branch"] == "O"))
            )
            if active:
                submitted = record["submitted"]
                # The arm's submitted reasoning is A's when we keep A's outputs
                # (same-ID or invalid-candidate rules); otherwise it is the new
                # prediction's reasoning (full verification trace stays in
                # branch_predictions/<key>.json).
                if submitted["source"] == "A":
                    row_reasoning = a_reasoning
                else:
                    row_reasoning = record["prediction_reasoning"]
                row = {
                    "arm": arm,
                    "case": case["case"],
                    "case_id": key,
                    "selected_route": record["r_route"],
                    "a_route": record["a_route"],
                    "route_changed": record["r_route"] != record["a_route"],
                    "branch": record["branch"],
                    "outcome": record["outcome"],
                    "provenance": ("new_prediction" if submitted["source"] == "new"
                                   else "official_failure" if submitted["source"] == "official_failure"
                                   else "shared_frozen_A_keep_A_rule"),
                    "external_calls": record["external_calls"],
                    "reasoning": row_reasoning,
                    "mask": ({"root": str(O), "path": submitted["mask_path"],
                              "sha256": submitted["mask_sha256"]}
                             if submitted["source"] == "new" else a_mask),
                    "a_final_id": record["a_final_id"],
                    "new_final_id": record["new_final_id"],
                    "submitted_selected_object_id": submitted.get("selected_object_id"),
                    "submitted_mask_query": submitted.get("mask_query"),
                    "submitted_class_name": submitted.get("class_name"),
                    "guard_reasons": record["guard_reasons"],
                }
                if submitted["source"] == "official_failure":
                    row["mask"] = None
                    row["failure_reason"] = submitted.get("failure_reason")
                counts[arm]["official_failure" if submitted["source"] == "official_failure"
                            else "new_prediction" if submitted["source"] == "new"
                            else "shared_frozen_A"] += 1
                outcomes[arm][record["outcome"]] = outcomes[arm].get(record["outcome"], 0) + 1
            else:
                row = {
                    "arm": arm,
                    "case": case["case"],
                    "case_id": key,
                    "selected_route": a_row["selected_route"],
                    "a_route": a_row["selected_route"],
                    "route_changed": False,
                    "branch": None,
                    "outcome": "not_triggered_shared_A",
                    "provenance": "shared_frozen_A",
                    "external_calls": 0,
                    "reasoning": a_reasoning,
                    "mask": a_mask,
                    "a_final_id": a_reasoning.get("selected_object_id"),
                }
                counts[arm]["shared_frozen_A"] += 1
            write_json(O / "rows" / arm / f"{key}.json", row)

    summary = {
        "status": "composed",
        "arms": counts,
        "outcomes": outcomes,
        "cases": len(cases),
        "triggered": len(triggered),
        "source": str(SOURCE),
    }
    write_json(O / "composition.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
