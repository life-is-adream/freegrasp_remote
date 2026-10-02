"""Independent post-prediction scorer for the route-correction experiment.

Reads frozen GT only at this scoring stage. Fail-closed: incomplete or
unsealed batches are never scored. Fixed denominator = 300 split0 rows.

Run: python score.py --root <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

O = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path("/home/public/zb/FreeGrasp_code-freegrasp_codex")
SOURCE = pathlib.Path(
    "/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/"
    "b1_v6_routing_split0_20260930_resume8_repaired")
DERIVED_SEAL = pathlib.Path(
    "/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/"
    "b1_v6_repair_20261002/validation/derived_integrity.json")
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 20261002
ARMS = ("A", "R", "RI", "RO")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_key(case_text: str) -> str:
    return hashlib.sha256(str(case_text).encode("utf-8")).hexdigest()[:24]


def iou(pred: np.ndarray, gt: np.ndarray) -> float:
    pred = np.asarray(pred).astype(bool)
    gt = np.asarray(gt).astype(bool)
    union = np.logical_or(pred, gt).sum()
    return float(np.logical_and(pred, gt).sum() / union) if union else 0.0


def load_gt_rows() -> dict[tuple[int, int, str], list[int]]:
    df = pd.concat([
        pd.read_parquet(REPO / "data/train-00000-of-00002.parquet"),
        pd.read_parquet(REPO / "data/train-00001-of-00002.parquet"),
    ], ignore_index=True)
    result: dict[tuple[int, int, str], list[int]] = {}
    for _, row in df[df["split"] == "0"].iterrows():
        result[(int(row["sceneId"]), int(row["queryObjId"]) + 1, str(row["annotation"]))] = [
            int(x) + 1 for x in str(row["groundTruthObjIds"]).split(",")]
    if len(result) != 300:
        raise RuntimeError(f"expected 300 scoring rows, got {len(result)}")
    return result


def identity_map(scene: int) -> dict[int, int]:
    path = REPO / "data/output/molmo_output" / f"scene{scene}" / f"{scene}_id.txt"
    lines = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = lines[0]
    mi, gi = header.index("Molmo_ID"), header.index("GT_ID")
    return {int(row[mi]): int(row[gi]) for row in lines[1:]}


def score_row(row: dict, case: dict, gt_ids: list[int], gt_masks: np.ndarray) -> dict:
    reasoning = row.get("reasoning") or {}
    mask_ref = row.get("mask")
    ssr = 0
    best_iou = 0.0
    if mask_ref is not None:
        path = pathlib.Path(mask_ref["root"]) / mask_ref["path"]
        if not path.is_file() or sha(path) != mask_ref["sha256"]:
            raise RuntimeError(f"mask hash mismatch: {row.get('case_id')}")
        with np.load(path, allow_pickle=False) as data:
            pred = data["mask"]
        gt_spatial = gt_masks.shape if gt_masks.ndim == 2 else gt_masks.shape[1:]
        if pred.ndim == 2 and pred.shape == gt_spatial:
            for gt_id in gt_ids:
                if gt_masks.ndim == 3 and 0 < gt_id <= len(gt_masks):
                    best_iou = max(best_iou, iou(pred, gt_masks[gt_id - 1] > 0))
                elif gt_masks.ndim == 2:
                    best_iou = max(best_iou, iou(pred, gt_masks == gt_id))
        ssr = int(best_iou >= 0.5)
    selected = reasoning.get("selected_object_id")
    try:
        selected_int = int(selected) if selected is not None else None
    except (TypeError, ValueError):
        selected_int = None
    mapped = identity_map(int(case["scene"])).get(selected_int) if selected_int is not None else None
    rsr = int(mapped in gt_ids) if mapped is not None else 0
    return {
        "case_id": stable_key(case["case"]),
        "scene": int(case["scene"]),
        "subset": case["audit_subset"],
        "ssr": ssr,
        "rsr": rsr,
        "iou": best_iou,
        "selected_id": selected_int,
        "mapped_id": mapped,
        "route": row.get("selected_route"),
        "a_route": row.get("a_route"),
        "route_changed": bool(row.get("route_changed")),
        "branch": row.get("branch"),
        "outcome": row.get("outcome"),
        "external_calls": int(row.get("external_calls", 0)),
    }


def load_arm_a(cases: list[dict], derived: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for case in cases:
        key = stable_key(case["case"])
        rel = f"rows/A/{key}.json"
        expected = derived["files"].get(rel)
        if expected is None or sha(SOURCE / rel) != expected:
            raise RuntimeError(f"A row hash drift: {key}")
        row = json.loads((SOURCE / rel).read_text())
        mask_rel = row["mask_path"]
        if derived["files"].get(mask_rel) != sha(SOURCE / mask_rel):
            raise RuntimeError(f"A mask hash drift: {key}")
        row = dict(row)
        row["mask"] = {"root": str(SOURCE), "path": mask_rel,
                       "sha256": derived["files"][mask_rel]}
        rows[key] = row
    return rows


def load_arm(arm: str, cases: list[dict]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for case in cases:
        key = stable_key(case["case"])
        row = json.loads((O / "rows" / arm / f"{key}.json").read_text())
        if row.get("case") != case["case"] or row.get("arm") != arm:
            raise RuntimeError(f"row identity mismatch: {arm}:{key}")
        rows[key] = row
    if len(rows) != 300:
        raise RuntimeError(f"arm {arm} has {len(rows)} rows")
    return rows


def cluster_ci(base: dict[str, dict], new: dict[str, dict], metric: str) -> list[float]:
    clusters: dict[int, list[str]] = defaultdict(list)
    for key in base:
        clusters[base[key]["scene"]].append(key)
    names = list(clusters)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sampled = rng.choice(names, size=len(names), replace=True)
        diffs = [new[key][metric] - base[key][metric]
                 for scene in sampled for key in clusters[int(scene)]]
        values.append(100.0 * sum(diffs) / len(diffs))
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def paired(base: dict[str, dict], new: dict[str, dict]) -> dict:
    if set(base) != set(new):
        raise RuntimeError("paired arms do not have identical case coverage")
    out = {}
    for metric in ("ssr", "rsr"):
        gain = sum(base[k][metric] == 0 and new[k][metric] == 1 for k in base)
        loss = sum(base[k][metric] == 1 and new[k][metric] == 0 for k in base)
        out[metric] = {"gain": gain, "loss": loss, "net": gain - loss,
                       "new_minus_base_pp": 100.0 * (sum(new[k][metric] for k in new)
                                                      - sum(base[k][metric] for k in base)) / len(base),
                       "scene_cluster_95ci_pp": cluster_ci(base, new, metric)}
    migrations = {}
    for field in ("route", "selected_id"):
        mapping = Counter(
            f"{base[k].get(field)}->{new[k].get(field)}" for k in base)
        migrations[field] = {"changed": sum(base[k].get(field) != new[k].get(field) for k in base),
                             "mapping": dict(sorted(mapping.items()))}
    out["migrations"] = migrations
    return out


def summarize(arm: str, rows: dict[str, dict]) -> dict:
    n = len(rows)
    ssr = sum(r["ssr"] for r in rows.values())
    rsr = sum(r["rsr"] for r in rows.values())
    return {
        "arm": arm, "n": n,
        "ssr": ssr, "rsr": rsr,
        "ssr_pct": 100.0 * ssr / n, "rsr_pct": 100.0 * rsr / n,
        "route_counts": dict(sorted(Counter(r["route"] for r in rows.values()).items())),
        "outcome_counts": dict(sorted(Counter(r["outcome"] for r in rows.values()).items())),
        "external_calls": sum(r["external_calls"] for r in rows.values()),
        "coverage": {"rows": n, "expected": 300, "complete": n == 300},
    }


def cost_report() -> dict:
    cost: dict = {}
    for phase in ("phase1_result.json", "phase2_result.json"):
        path = O / phase
        if path.is_file():
            data = json.loads(path.read_text())
            cost[phase.split("_result")[0]] = {
                "status": data.get("status"),
                "api_attempts": data.get("api_attempts"),
                "mimo_attempts": data.get("mimo_attempts"),
                "qwen_attempts": data.get("qwen_attempts"),
                "qwen_cost_cny": round(data.get("qwen_cost_cny", 0.0), 6),
                "mimo_equivalent_cny": round(data.get("mimo_equivalent_cny", 0.0), 6),
                "tokens": data.get("tokens", {}),
            }
    # Historical A acquisition cost chain (read-only reference).
    chain = {}
    for name, rel in (("run2", "b1_v6_routing_split0_20260930_run2"),
                      ("resume8", "b1_v6_routing_split0_20260930_resume8")):
        path = pathlib.Path("/home/public/zb/freegrasp_unograsp_fusion_20260922_v1") / rel / "seal.json"
        if path.is_file():
            seal = json.loads(path.read_text())
            chain[name] = {"api_attempts": seal.get("api_attempts"),
                           "qwen_cost_cny": seal.get("qwen_cost_cny"),
                           "mimo_equivalent_cny": seal.get("mimo_equivalent_cny")}
    cost["historical_A_acquisition_reference"] = chain
    cost["notes"] = [
        "mimo_equivalent_cny is a pay-as-you-go equivalence estimate only; the MiMo Token Plan actual deduction must be confirmed from account records",
        "R deployment cost must include the full A acquisition chain, not only the new calls",
        "qwen_cost_cny is derived from token usage at 2 CNY/M input and 12 CNY/M output",
    ]
    return cost


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    if pathlib.Path(args.root).resolve() != O:
        raise SystemExit("root mismatch")

    derived = json.loads(DERIVED_SEAL.read_text())
    cases = json.loads((SOURCE / "cases.json").read_text())
    if len(cases) != 300:
        raise SystemExit("case count != 300")

    for phase in ("phase1_result.json", "phase2_result.json"):
        if not (O / phase).is_file() or json.loads((O / phase).read_text()).get("status") != "complete":
            raise SystemExit(f"batch not complete: {phase}")

    gt = load_gt_rows()
    gt_cache: dict[int, np.ndarray] = {}

    def gt_masks(scene: int) -> np.ndarray:
        if scene not in gt_cache:
            data = np.load(REPO / "data/npz_file" / f"{scene}.npz", allow_pickle=True)
            gt_cache[scene] = (data["instances_objects.npy"] if "instances_objects.npy" in data
                               else data["instances_objects"])
        return gt_cache[scene]

    scored: dict[str, dict[str, dict]] = {}
    arm_rows = {"A": load_arm_a(cases, derived)}
    for arm in ("R", "RI", "RO"):
        arm_rows[arm] = load_arm(arm, cases)
    for arm in ARMS:
        scored[arm] = {}
        for case in cases:
            key = stable_key(case["case"])
            gt_key = (int(case["scene"]), int(case["object"]), str(case["annotation"]))
            scored[arm][key] = score_row(arm_rows[arm][key], case, gt[gt_key], gt_masks(int(case["scene"])))
            scored[arm][key]["case"] = case["case"]

    # Self-check: recomputed A must reproduce the audited frozen repaired A.
    a_ssr = sum(r["ssr"] for r in scored["A"].values())
    a_rsr = sum(r["rsr"] for r in scored["A"].values())
    if (a_ssr, a_rsr) != (161, 171):
        raise SystemExit(f"A self-check failed: SSR {a_ssr} RSR {a_rsr}, expected 161/171")

    comparisons = {
        "A_vs_R": paired(scored["A"], scored["R"]),
        "A_vs_RI": paired(scored["A"], scored["RI"]),
        "A_vs_RO": paired(scored["A"], scored["RO"]),
        "RI_vs_RO": paired(scored["RI"], scored["RO"]),
    }

    # Post-hoc stratification (analysis only, never used by the policy).
    strat: dict[str, dict] = {}
    for arm in ARMS:
        by_subset = defaultdict(lambda: {"n": 0, "ssr": 0, "rsr": 0})
        for row in scored[arm].values():
            bucket = by_subset[row["subset"]]
            bucket["n"] += 1
            bucket["ssr"] += row["ssr"]
            bucket["rsr"] += row["rsr"]
        strat[arm] = dict(by_subset)
    by_branch = defaultdict(lambda: {"n": 0, "a_ssr": 0, "r_ssr": 0, "a_rsr": 0, "r_rsr": 0})
    for key, row in scored["R"].items():
        branch = row["branch"]
        bucket = by_branch[branch or "none"]
        bucket["n"] += 1
        bucket["a_ssr"] += scored["A"][key]["ssr"]
        bucket["r_ssr"] += row["ssr"]
        bucket["a_rsr"] += scored["A"][key]["rsr"]
        bucket["r_rsr"] += row["rsr"]

    result = {
        "status": "complete",
        "experiment_id": O.name,
        "denominator": 300,
        "arms": {arm: summarize(arm, scored[arm]) for arm in ARMS},
        "comparisons": comparisons,
        "branch_stratification": dict(by_branch),
        "subset_stratification_post_hoc": strat,
        "cost": cost_report(),
        "decision_rules": {
            "primary": "R-A paired SSR difference, scene-cluster bootstrap 95% CI",
            "improvement": "CI lower bound > 0; small gain = 'slight improvement'; +2pp is the engineering target, not a prediction",
            "rsr_protection": "one-sided 95% lower bound of R-A RSR above -1pp; insufficient sample -> 'insufficient evidence'",
            "verdicts": ["improved", "slight_improvement", "not_demonstrated", "failed"],
        },
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
                      "cluster": "scene"},
        "claim_boundary": [
            "split0 is exposed development data; results are exploratory, not unseen-test evidence",
            "300 cases x arms are paired, not independent full-900 samples",
            "simulation SSR is not physical robot grasp success",
            "R-A differences include execution-chain variance; CI does not eliminate it",
        ],
    }
    ssr_ci = comparisons["A_vs_R"]["ssr"]["scene_cluster_95ci_pp"]
    rsr_ci = comparisons["A_vs_R"]["rsr"]["scene_cluster_95ci_pp"]
    net = comparisons["A_vs_R"]["ssr"]["net"]
    if ssr_ci[0] > 0:
        verdict = "slight_improvement" if net < 6 else "improved"
    elif net < 0 and ssr_ci[1] < 0:
        verdict = "failed"
    else:
        verdict = "not_demonstrated"
    result["verdict"] = verdict

    out = O / "score.json"
    if out.exists():
        raise SystemExit("score.json already exists; refusing to overwrite")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "A": [sum(r['ssr'] for r in scored['A'].values()), sum(r['rsr'] for r in scored['A'].values())],
        "R": [sum(r['ssr'] for r in scored['R'].values()), sum(r['rsr'] for r in scored['R'].values())],
        "RI": [sum(r['ssr'] for r in scored['RI'].values()), sum(r['rsr'] for r in scored['RI'].values())],
        "RO": [sum(r['ssr'] for r in scored['RO'].values()), sum(r['rsr'] for r in scored['RO'].values())],
        "A_vs_R": comparisons["A_vs_R"],
        "verdict": verdict,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
