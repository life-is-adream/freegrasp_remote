"""Paid worker for the R route-correction branches (design v1.1, phase 1/2).

Processes ONLY the pre-frozen triggered rows from plan.json. Every triggered
row runs the frozen repo's get_prediction_result with the corrected route
injected via frozen_route_assessment, on the ORIGINAL parquet RGB (1200x1200)
for segmentation and the existing Molmo folder for the VLM image and points.

Submission rules (design 3.4, pre-registered in frozen_protocol.json):
  - new final ID == A final ID            -> keep A outputs byte-identical
  - new final ID valid and different      -> submit the new atomic prediction
  - new plan ID invalid/missing           -> keep A, record candidate_invalid_keep_A
  - valid plan but segmentation produced no mask -> official protocol failure
  - transport/auth/unknown status         -> hard stop (never silently retried)

One structural retry (fresh downstream calls) when a prediction returns no
usable mask; mirrors the resume8 worker. Untriggered rows are never executed
here; compose.py shares the frozen A for them.

Run:
  python worker.py --root <dir> --phase 1   # 2 branch-I + 1 branch-O rows
  python worker.py --root <dir> --phase 2   # remaining rows (skips completed)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import time
import traceback
from typing import Any

O = pathlib.Path(__file__).resolve().parent
FUSION = pathlib.Path("/home/public/zb/freegrasp_unograsp_fusion_20260922_v1")
SOURCE = FUSION / "b1_v6_routing_split0_20260930_resume8_repaired"
REPO = pathlib.Path("/home/public/zb/FreeGrasp_code-freegrasp_codex")

MODEL = "mimo-v2.5"
QWEN_MODEL = "qwen3.6-plus"
MAX_EXTERNAL_REQUESTS = 130
MAX_QWEN_COST_CNY = 6.0
MAX_SECONDS = 10800.0

os.environ.update(
    HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
    CUDA_VISIBLE_DEVICES="3", TOKENIZERS_PARALLELISM="false",
    MPLCONFIGDIR=str(O / "mplconfig"), TMPDIR=str(O / "tmp"),
    TEMP=str(O / "tmp"), TMP=str(O / "tmp"), PYTHONDONTWRITEBYTECODE="1",
)
sys.dont_write_bytecode = True
import tempfile  # noqa: E402

(O / "tmp").mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(O / "tmp")


class Stop(BaseException):
    """Fail-closed hard stop for the paid batch."""


def assert_target() -> None:
    if O.name != "b1_route_correction_20261002_v1" or O.resolve() != O or O.is_symlink():
        raise Stop("TARGET_PATH_CHANGED")


def _audit(event: str, args: tuple[Any, ...]) -> None:
    """Confine all writes to this experiment directory."""
    if event in {"open", "os.open"} and args:
        raw = args[0]
        if isinstance(raw, (str, bytes, os.PathLike)):
            path = pathlib.Path(os.fsdecode(raw)).resolve(strict=False)
            mode = args[1] if len(args) > 1 and isinstance(args[1], str) else ""
            flags = args[1] if len(args) > 1 and isinstance(args[1], int) else 0
            writing = any(c in mode for c in "wax+") or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and path != O and O not in path.parents:
                raise Stop("WRITE_OUTSIDE_EXPERIMENT")
    elif event in {"os.mkdir", "os.makedirs"} and args:
        path = pathlib.Path(os.fsdecode(args[0])).resolve(strict=False)
        if path != O and O not in path.parents:
            raise Stop("MKDIR_OUTSIDE_EXPERIMENT")
    elif event in {"os.remove", "os.unlink", "os.rmdir"} and args:
        path = pathlib.Path(os.fsdecode(args[0])).resolve(strict=False)
        if path != O and O not in path.parents:
            raise Stop("DELETE_OUTSIDE_EXPERIMENT")
    elif event in {"os.rename", "os.replace", "os.link", "os.symlink"} and args:
        for raw in args[:2]:
            if isinstance(raw, (str, bytes, os.PathLike)):
                path = pathlib.Path(os.fsdecode(raw)).resolve(strict=False)
                if path != O and O not in path.parents:
                    raise Stop("MOVE_OUTSIDE_EXPERIMENT")


sys.addaudithook(_audit)
sys.path.insert(0, str(O))
sys.path.insert(0, str(REPO))

import r_policy  # noqa: E402

FORBIDDEN_KEYS = {
    "difficulty", "evaluation_subset", "subset", "scene_id", "row_id",
    "gt_id", "gt_ids", "ground_truth", "groundtruth", "target_gt_id",
    "mapped_id", "selected_gt_id", "ssr", "rsr", "iou", "historical_score",
    "historical_route", "score",
}


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_write_json(path: pathlib.Path, value: Any) -> None:
    assert_target()
    path = path.resolve(strict=False)
    if O not in path.parents:
        raise Stop("WRITE_OUTSIDE_EXPERIMENT")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_mask(path: pathlib.Path, mask: Any, np: Any) -> None:
    assert_target()
    path = path.resolve(strict=False)
    if O not in path.parents or path.exists():
        raise Stop("PREDICTION_DESTINATION_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(tmp, mask=mask.astype(bool))
    os.replace(tmp, path)
    with np.load(path, allow_pickle=False) as data:
        if "mask" not in data:
            raise Stop("PREDICTION_WRITE_VERIFY_FAILED")


def walk_forbidden(value: Any, path: str = "") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).strip().lower()
            child_path = f"{path}.{key}" if path else str(key)
            if key_norm in FORBIDDEN_KEYS:
                hits.append({"path": child_path, "key": key_norm})
            hits.extend(walk_forbidden(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            hits.extend(walk_forbidden(child, f"{path}[{index}]"))
    return hits


def parse_json(value: Any) -> dict[str, Any]:
    import re
    text = str(value or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def assert_model_messages(messages: Any) -> None:
    hits = walk_forbidden(messages, "messages")
    if isinstance(messages, list):
        for index, message in enumerate(messages):
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    hits.extend(walk_forbidden(parse_json(content), f"messages[{index}].content_json"))
                elif isinstance(content, list):
                    for part_index, part in enumerate(content):
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            hits.extend(walk_forbidden(
                                parse_json(part["text"]), f"messages[{index}].content[{part_index}].text_json"))
    if hits:
        raise Stop("FORBIDDEN_MODEL_PAYLOAD_FIELD")


def stable_key(case_text: str) -> str:
    return hashlib.sha256(str(case_text).encode("utf-8")).hexdigest()[:24]


class Runtime:
    def __init__(self) -> None:
        self.started = time.time()
        self.api_attempts = 0
        self.mimo_attempts = 0
        self.qwen_attempts = 0
        self.qwen_cost_cny = 0.0
        self.mimo_equivalent_cny = 0.0
        self.http_500_retries = 0
        self.tokens: dict[str, int] = {}
        self.current: dict[str, Any] = {"arm": "R", "case": "", "case_id": "", "phase": ""}

    def elapsed(self) -> float:
        return time.time() - self.started

    def check_budget(self) -> None:
        if self.elapsed() >= MAX_SECONDS:
            raise Stop("TIME_BUDGET")
        if self.api_attempts >= MAX_EXTERNAL_REQUESTS:
            raise Stop("CALL_BUDGET")

    def event(self, value: dict[str, Any]) -> None:
        assert_target()
        with (O / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            handle.flush()

    def api(self, provider: str, messages: Any, max_tokens: int, model: str,
            client: Any, M: Any, A: Any) -> str:
        assert_target()
        self.check_budget()
        assert_model_messages(messages)
        text_bytes = sum(
            len(str(part.get("text", "")).encode("utf-8"))
            for message in messages
            for part in (message["content"] if isinstance(message.get("content"), list)
                         else [{"text": message.get("content", "")}]))
        if text_bytes > 32000:
            raise Stop("INPUT_SIZE_BUDGET")
        if provider == "qwen":
            reserve = (text_bytes + 16384) * 2 / 1e6 + max_tokens * 12 / 1e6
            if self.qwen_cost_cny + reserve > MAX_QWEN_COST_CNY:
                raise Stop("QWEN_COST_BUDGET")
        request_id = f"r{self.api_attempts + 1:04d}"
        self.api_attempts += 1
        if provider == "mimo":
            self.mimo_attempts += 1
            url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
            headers = {"api-key": os.environ["MIMO_API_KEY"]}
            payload = M.build_mimo_payload(model=model, messages=messages,
                                           max_tokens=max_tokens, temperature=0,
                                           top_p=1, frequency_penalty=0,
                                           presence_penalty=0, seed=0)
        else:
            self.qwen_attempts += 1
            url = A.QWEN_BASE_URL.rstrip("/") + "/chat/completions"
            headers = {"Authorization": "Bearer " + A.resolve_qwen_api_key()}
            payload = {"model": model, "messages": messages, "temperature": 0,
                       "top_p": 1, "max_tokens": max_tokens}
        request_hash = hashlib.sha256(
            json.dumps(messages, sort_keys=True, default=str).encode()).hexdigest()
        self.event({"event": "dispatch", "request": request_id,
                    "phase": self.current["phase"], "arm": self.current["arm"],
                    "case": self.current["case"], "provider": provider,
                    "model": model, "request_sha256": request_hash})
        try:
            response = client.post(url, headers=headers, json=payload)
        except Exception as exc:
            self.event({"event": "transport_error", "request": request_id,
                        "error_type": type(exc).__name__})
            raise Stop("API_TRANSPORT_" + type(exc).__name__) from exc
        if response.status_code == 500:
            if self.http_500_retries >= 3:
                self.event({"event": "http_retry_exhausted", "request": request_id,
                            "provider": provider, "status": 500})
                raise Stop("HTTP_500")
            self.http_500_retries += 1
            self.check_budget()
            retry_request_id = f"r{self.api_attempts + 1:04d}"
            self.api_attempts += 1
            if provider == "mimo":
                self.mimo_attempts += 1
            else:
                self.qwen_attempts += 1
            self.event({"event": "http_retry", "request": request_id,
                        "retry_request": retry_request_id, "provider": provider,
                        "status": 500, "retry_index": self.http_500_retries})
            try:
                response = client.post(url, headers=headers, json=payload)
            except Exception as exc:
                self.event({"event": "transport_error", "request": retry_request_id,
                            "error_type": type(exc).__name__})
                raise Stop("API_TRANSPORT_" + type(exc).__name__) from exc
        if response.status_code != 200:
            self.event({"event": "http_error", "request": request_id,
                        "status": response.status_code})
            raise Stop("HTTP_" + str(response.status_code))
        try:
            data = response.json()
        except Exception as exc:
            raise Stop("INVALID_RESPONSE_JSON") from exc
        if data.get("model") != model:
            raise Stop("MODEL_IDENTITY_MISMATCH")
        usage = data.get("usage", {})
        pin, pout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if pin is None or pout is None:
            raise Stop("MISSING_USAGE")
        self.tokens[provider] = self.tokens.get(provider, 0) + int(pin) + int(pout)
        if provider == "qwen":
            self.qwen_cost_cny += (int(pin) * 2 + int(pout) * 12) / 1e6
        else:
            self.mimo_equivalent_cny += (int(pin) + int(pout) * 2) / 1e6
        if self.qwen_cost_cny > MAX_QWEN_COST_CNY:
            self.event({"event": "budget_error", "request": request_id,
                        "reason": "QWEN_COST_BUDGET",
                        "qwen_cost_cny": self.qwen_cost_cny})
            raise Stop("QWEN_COST_BUDGET")
        choices = data.get("choices") or [{}]
        message = choices[0].get("message", {})
        content = message.get("content") or message.get("reasoning_content") or ""
        if not content:
            raise Stop("EMPTY_CONTENT")
        self.event({"event": "response", "request": request_id, "usage": usage,
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest()})
        return content


def load_cases_and_a() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases = load_json(SOURCE / "cases.json")
    by_id = {}
    for case in cases:
        by_id[stable_key(case["case"])] = case
    if len(by_id) != 300:
        raise Stop("CASE_COUNT_INVALID")
    a_rows = {}
    for key in by_id:
        row = load_json(SOURCE / "rows" / "A" / f"{key}.json")
        if row.get("case") != by_id[key]["case"]:
            raise Stop("A_ROW_IDENTITY_MISMATCH")
        a_rows[key] = row
    return by_id, a_rows


def load_original_images(cases: dict[str, dict[str, Any]]) -> dict[tuple[int, int, str], bytes]:
    """Parquet original RGB; only join columns, never GT/difficulty."""
    import pandas as pd
    wanted = {(int(c["scene"]), int(c["object"]) - 1, c["annotation"]) for c in cases.values()}
    images: dict[tuple[int, int, str], bytes] = {}
    for name in ("train-00000-of-00002.parquet", "train-00001-of-00002.parquet"):
        frame = pd.read_parquet(REPO / "data" / name,
                                columns=["sceneId", "queryObjId", "annotation", "image"])
        for _, row in frame.iterrows():
            key = (int(row["sceneId"]), int(row["queryObjId"]), row["annotation"])
            if key in wanted:
                value = row["image"]["bytes"]
                if key in images and images[key] != value:
                    raise Stop("AMBIGUOUS_ORIGINAL_IMAGE")
                images[key] = value
    if set(images) != wanted:
        raise Stop("MISSING_ORIGINAL_IMAGES")
    return images


def frozen_assessment_r(assessment: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Same frozen shape the historical B1 flow and resume8 worker used."""
    route = decision["selected_route"]
    return {
        "route_mode": route,
        "pre_guard_route_mode": assessment.get("recommended_route"),
        "route_confidence": assessment.get("route_confidence", 0.0),
        "target_object_id": assessment.get("target_object_id"),
        "target_label": assessment.get("target_label"),
        "ambiguity_evidence": assessment.get("ambiguity_evidence", []),
        "blocker_evidence": assessment.get("blocker_evidence", []),
        "route_guard_applied": route != assessment.get("recommended_route"),
        "route_guard_reasons": decision["guard_reasons"],
        "route_guard_variant": "pathb_blk_arb_v1",
        "scene_router_version": "pathb_blk_arb_v1",
        "scene_complexity": {
            "model": "pathb_blk_arb_v1",
            "route_mode": route,
            "recommended_route": assessment.get("recommended_route"),
            "target_visibility": assessment.get("target_visibility"),
            "blocking_relations": assessment.get("blocking_relations", []),
            "target_candidates": assessment.get("target_candidates", []),
            "selection_source": decision["policy_version"],
            "guard_reasons": decision["guard_reasons"],
            "requires_adjudication": False,
        },
    }


def classify_outcome(prediction: Any, a_final_id: Any, visible_ids: list[int]) -> dict[str, Any]:
    has_mask = isinstance(prediction, dict) and prediction.get("mask") is not None
    reasoning = prediction.get("reasoning", {}) if isinstance(prediction, dict) else {}
    new_id = reasoning.get("selected_object_id")
    valid = isinstance(new_id, int) and new_id in visible_ids
    if valid and has_mask and new_id == a_final_id:
        outcome = "same_id_keep_A_outputs"
    elif valid and has_mask:
        outcome = "id_changed_new_prediction"
    elif not valid:
        outcome = "candidate_invalid_keep_A"
    else:
        outcome = "segmentation_failure_official_failure"
    return {"outcome": outcome, "new_final_id": new_id, "valid_new_id": valid,
            "has_mask": has_mask}


def main() -> None:
    assert_target()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--phase", required=True, choices=["1", "2"])
    args = parser.parse_args()
    if pathlib.Path(args.root).resolve() != O:
        raise Stop("ROOT_ARGUMENT_MISMATCH")

    protocol = load_json(O / "frozen_protocol.json")
    plan = load_json(O / "plan.json")
    if plan.get("status") != "frozen" or not plan["work_items"]:
        raise Stop("PLAN_NOT_FROZEN")
    if protocol.get("experiment_id") != O.name:
        raise Stop("PROTOCOL_IDENTITY_MISMATCH")
    for name, expected in protocol.get("code_sha256", {}).items():
        if sha(O / name) != expected:
            raise Stop(f"CODE_HASH_DRIFT:{name}")

    work_items = plan["work_items"]
    if args.phase == "1":
        first_i = [i for i in work_items if i["branch"] == "I"][:2]
        first_o = [i for i in work_items if i["branch"] == "O"][:1]
        selected = first_i + first_o
    else:
        phase1 = load_json(O / "phase1_result.json") if (O / "phase1_result.json").exists() else None
        done = set()
        if phase1:
            done = {item["case_id"] for item in phase1.get("items", [])}
        selected = [i for i in work_items if i["case_id"] not in done]

    cases, a_rows = load_cases_and_a()
    runtime = Runtime()
    state: dict[str, Any] = {
        "experiment_id": O.name,
        "phase": f"paid_phase_{args.phase}",
        "status": "running",
        "planned_new": len(selected),
        "items": [],
        "api_attempts": 0, "mimo_attempts": 0, "qwen_attempts": 0,
        "qwen_cost_cny": 0.0, "mimo_equivalent_cny": 0.0,
        "http_500_retries": 0, "tokens": {},
    }
    # Resume accounting from a prior stopped run of the same phase.
    if args.phase == "2" and (O / "progress.json").exists():
        prior = load_json(O / "progress.json")
        if prior.get("phase") == state["phase"] and prior.get("status") in {"running", "stopped"}:
            done_keys = {item["case_id"] for item in prior.get("items", [])}
            selected = [i for i in selected if i["case_id"] not in done_keys]
            state["items"] = prior.get("items", [])
            state["api_attempts"] = prior.get("api_attempts", 0)
            state["mimo_attempts"] = prior.get("mimo_attempts", 0)
            state["qwen_attempts"] = prior.get("qwen_attempts", 0)
            state["qwen_cost_cny"] = prior.get("qwen_cost_cny", 0.0)
            state["mimo_equivalent_cny"] = prior.get("mimo_equivalent_cny", 0.0)
            state["http_500_retries"] = prior.get("http_500_retries", 0)
            state["tokens"] = prior.get("tokens", {})
            runtime.api_attempts = state["api_attempts"]
            runtime.mimo_attempts = state["mimo_attempts"]
            runtime.qwen_attempts = state["qwen_attempts"]
            runtime.qwen_cost_cny = state["qwen_cost_cny"]
            runtime.mimo_equivalent_cny = state["mimo_equivalent_cny"]
            runtime.http_500_retries = state["http_500_retries"]
            runtime.tokens = dict(state["tokens"])

    client = None
    try:
        import numpy as np
        import torch
        import httpx
        from PIL import Image
        import io as _io
        import evaluate_mimo as M
        import utils.eghc_adjudicator as A
        import utils.eghc_router as G
        import utils.utils as U
        from models.langsam.langsam_actor import LangSAM

        M.ensure_unused_dashscope_key_for_import()
        if not os.environ.get("MIMO_API_KEY", "").startswith("tp-"):
            raise Stop("MIMO_API_KEY_MISSING")
        if not A.resolve_qwen_api_key():
            raise Stop("QWEN_API_KEY_MISSING")

        actor = LangSAM(sam_type="vit_h",
                        ckpt_path="/home/wyl/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth",
                        use_gpu=True, sam_backend="sam1")
        U.get_langsam_actor = lambda **kwargs: actor
        original_predict = actor.predict
        target_cache = O / "mask_cache"

        def load_cache(root: pathlib.Path, key: str):
            data_path, meta_path = root / (key + ".npz"), root / (key + ".json")
            if not data_path.is_file() and not meta_path.is_file():
                return None
            if not data_path.is_file() or not meta_path.is_file():
                raise Stop("MASK_CACHE_PARTIAL")
            z = np.load(data_path, allow_pickle=False)
            meta = load_json(meta_path)
            return (torch.from_numpy(z["masks"]), torch.from_numpy(z["boxes"]),
                    meta["phrases"], torch.from_numpy(z["logits"]))

        def cached_predict(image: Any, query: str, *call_args: Any, **call_kwargs: Any):
            image_hash = hashlib.sha256(np.asarray(image).tobytes()).hexdigest()
            identity = [image_hash, query, call_args, call_kwargs,
                        sha(REPO / "models/langsam/langsam_actor.py"), torch.__version__]
            key = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()
            cached = load_cache(target_cache, key)
            if cached is not None:
                return cached
            assert_target()
            with torch.inference_mode():
                masks, boxes, phrases, logits = original_predict(image, query, *call_args, **call_kwargs)
            target_cache.mkdir(parents=True, exist_ok=True)
            write_mask(target_cache / (key + ".npz"), masks.cpu().numpy(), np)
            safe_write_json(target_cache / (key + ".json"), {"phrases": phrases, "query": query})
            return masks, boxes, phrases, logits

        actor.predict = cached_predict
        client = httpx.Client(timeout=httpx.Timeout(connect=20.0, read=300.0, write=60.0, pool=60.0),
                              trust_env=False)

        def mimo_call(messages: Any, model: str, max_tokens: int) -> str:
            return runtime.api("mimo", messages, max_tokens, model, client, M, A)

        def qwen_call(messages: Any, **kwargs: Any) -> str:
            return runtime.api("qwen", messages, kwargs.get("max_output_tokens", 512),
                               QWEN_MODEL, client, M, A)

        U._call_reasoning_model = mimo_call
        A.call_qwen_adjudicator = qwen_call

        images = load_original_images(cases)

        for index, item in enumerate(selected):
            assert_target()
            runtime.check_budget()
            key = item["case_id"]
            case = cases[key]
            a_row = a_rows[key]
            out_json = O / "branch_predictions" / f"{key}.json"
            if out_json.exists():
                continue
            packet = case["packet"]
            visible = [int(c["id"]) for c in packet["candidates"]]
            assessment = G.parse_eghc_assessment(
                case["router_output"], visible, target_label=case["annotation"])
            decision = r_policy.select_r(packet, assessment, item["a_route"])
            if decision["branch"] != item["branch"] or decision["selected_route"] != item["r_route"]:
                raise Stop("PLAN_DECISION_MISMATCH")
            runtime.current = {"phase": f"phase{args.phase}", "arm": "R",
                               "case": case["case"], "case_id": key, "index": index}
            frozen = frozen_assessment_r(assessment, decision)
            image = Image.open(_io.BytesIO(images[(int(case["scene"]), int(case["object"]) - 1,
                                                   case["annotation"])])).convert("RGB")
            before = (runtime.api_attempts, runtime.mimo_attempts, runtime.qwen_attempts,
                      runtime.qwen_cost_cny)
            gpu_started = time.time()

            def run_prediction():
                return U.get_prediction_result(
                    image, case["point_dir"], int(case["scene"]), case["annotation"],
                    return_metadata=True, prompt_variant="legacy", model_name=MODEL,
                    max_output_tokens=1024, mimo_retry_mode="none",
                    segmentation_variant="eghc_mask_repair_v1",
                    routing_variant="evidence_gated_cascade",
                    feature_source="deployable_predicted", protocol_ablation="full",
                    route_guard_variant="pathb_blk_arb_v1",
                    frozen_route_assessment=frozen, sam_backend="sam1")

            prediction = run_prediction()
            # One pre-registered structural retry when no usable mask exists.
            if not isinstance(prediction, dict) or prediction.get("mask") is None:
                runtime.event({"event": "structural_retry", "case": case["case"],
                               "case_id": key, "reason": "no_usable_mask"})
                prediction = run_prediction()

            gpu_seconds = time.time() - gpu_started
            verdict = classify_outcome(prediction, item["a_final_id"], visible)
            reasoning = prediction.get("reasoning", {}) if isinstance(prediction, dict) else {}
            if walk_forbidden(reasoning, "reasoning"):
                raise Stop("FORBIDDEN_REASONING_FIELD")

            record: dict[str, Any] = {
                "case_id": key, "case": case["case"],
                "scene": int(case["scene"]), "object": int(case["object"]),
                "annotation": case["annotation"], "audit_subset": case["audit_subset"],
                "branch": item["branch"], "a_route": item["a_route"],
                "r_route": item["r_route"], "guard_reasons": decision["guard_reasons"],
                "a_final_id": item["a_final_id"], "new_final_id": verdict["new_final_id"],
                "valid_new_id": verdict["valid_new_id"], "outcome": verdict["outcome"],
                "phase": int(args.phase),
                "external_calls": runtime.api_attempts - before[0],
                "mimo_calls": runtime.mimo_attempts - before[1],
                "qwen_calls": runtime.qwen_attempts - before[2],
                "qwen_cost_cny": round(runtime.qwen_cost_cny - before[3], 6),
                "gpu_seconds": round(gpu_seconds, 2),
                "prediction_reasoning": reasoning,
                "a_mask_path": str(a_row["mask_path"]),
                "a_mask_sha256": sha(SOURCE / a_row["mask_path"]),
            }
            if verdict["outcome"] == "id_changed_new_prediction":
                mask = prediction["mask"]
                if hasattr(mask, "cpu"):
                    mask = mask.cpu().numpy()
                mask = np.asarray(mask)
                if tuple(mask.shape) != (image.height, image.width):
                    raise Stop("MASK_SHAPE_MISMATCH")
                new_pred_path = O / "predictions" / "new" / f"{key}.npz"
                write_mask(new_pred_path, mask, np)
                record["new_mask_path"] = str(new_pred_path.relative_to(O))
                record["new_mask_sha256"] = sha(new_pred_path)
                record["submitted"] = {
                    "source": "new",
                    "selected_object_id": verdict["new_final_id"],
                    "mask_query": reasoning.get("mask_query"),
                    "class_name": reasoning.get("class_name"),
                    "mask_path": record["new_mask_path"],
                    "mask_sha256": record["new_mask_sha256"],
                }
            elif verdict["outcome"] == "segmentation_failure_official_failure":
                record["submitted"] = {
                    "source": "official_failure", "selected_object_id": verdict["new_final_id"],
                    "mask_path": None, "mask_sha256": None,
                    "failure_reason": reasoning.get("failure_reason") or prediction.get("error"),
                }
            else:
                record["submitted"] = {
                    "source": "A",
                    "selected_object_id": item["a_final_id"],
                    "mask_query": a_row["reasoning"].get("mask_query"),
                    "class_name": a_row["reasoning"].get("class_name"),
                    "mask_path": record["a_mask_path"],
                    "mask_sha256": record["a_mask_sha256"],
                }
            safe_write_json(out_json, record)
            state["items"].append({
                "case_id": key, "branch": item["branch"], "outcome": verdict["outcome"],
                "external_calls": record["external_calls"]})
            state["api_attempts"] = runtime.api_attempts
            state["mimo_attempts"] = runtime.mimo_attempts
            state["qwen_attempts"] = runtime.qwen_attempts
            state["qwen_cost_cny"] = runtime.qwen_cost_cny
            state["mimo_equivalent_cny"] = runtime.mimo_equivalent_cny
            state["http_500_retries"] = runtime.http_500_retries
            state["tokens"] = runtime.tokens
            state["elapsed_seconds"] = runtime.elapsed()
            state["last_completed"] = key
            safe_write_json(O / "progress.json", {**state, "status": "running",
                                                  "completed_count": len(state["items"]),
                                                  "remaining_count": len(selected) - (index + 1)})
            print(json.dumps({"status": "progress", "phase": args.phase,
                              "completed": len(state["items"]), "planned": len(selected),
                              "last": key, "outcome": verdict["outcome"],
                              "api_attempts": runtime.api_attempts,
                              "qwen_cost_cny": round(runtime.qwen_cost_cny, 4)},
                             ensure_ascii=False), flush=True)

        state["status"] = "complete"
    except BaseException as exc:
        state["status"] = "stopped"
        state["error_type"] = type(exc).__name__
        state["reason"] = str(exc)[:240]
        state["traceback_locations"] = [
            {"file": frame.filename, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)]
        print(json.dumps({"status": "stopped", "reason": state["reason"],
                          "error_type": state["error_type"],
                          "completed": len(state.get("items", []))},
                         ensure_ascii=False), flush=True)
    finally:
        state["elapsed_seconds"] = runtime.elapsed()
        state["api_attempts"] = runtime.api_attempts
        state["mimo_attempts"] = runtime.mimo_attempts
        state["qwen_attempts"] = runtime.qwen_attempts
        state["qwen_cost_cny"] = runtime.qwen_cost_cny
        state["mimo_equivalent_cny"] = runtime.mimo_equivalent_cny
        state["http_500_retries"] = runtime.http_500_retries
        state["tokens"] = runtime.tokens
        try:
            assert_target()
            safe_write_json(O / "progress.json", state)
            if args.phase == "1":
                safe_write_json(O / "phase1_result.json", state)
            else:
                safe_write_json(O / "phase2_result.json", state)
        except BaseException as seal_exc:
            print(json.dumps({"status": "seal_write_failed",
                              "error_type": type(seal_exc).__name__,
                              "reason": str(seal_exc)}, ensure_ascii=False), flush=True)
        if client is not None:
            client.close()
    if state["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
