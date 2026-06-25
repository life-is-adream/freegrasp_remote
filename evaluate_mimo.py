import argparse
import os
from datetime import datetime
from types import SimpleNamespace

import httpx


PROXY_ENV_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")

PAY_AS_YOU_GO_BASE_URL = "https://api.xiaomimimo.com/v1"
TOKEN_PLAN_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

DEFAULT_MODEL_NAME = "mimo-v2.5"
VISION_MODEL_HINT = "mimo-v2.5 or mimo-v2-omni"
UNSUPPORTED_OPENAI_PARAMS = {"frequency_penalty", "presence_penalty", "seed"}
ONE_PIXEL_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class MiMoAPIError(RuntimeError):
    pass


def clear_proxy_environment():
    for key in PROXY_ENV_VARS:
        os.environ.pop(key, None)


def ensure_unused_dashscope_key_for_import():
    # utils.config constructs a DashScope/OpenAI client at import time. MiMo runs patch
    # that client immediately after import, so this placeholder is never used for calls.
    os.environ.setdefault("DASHSCOPE_API_KEY", "unused-by-evaluate-mimo")


def default_mimo_base_url(api_key: str) -> str:
    if api_key.startswith("tp-"):
        return TOKEN_PLAN_BASE_URL
    return PAY_AS_YOU_GO_BASE_URL


def resolve_mimo_api_key(api_key: str | None = None) -> str:
    key = api_key or os.environ.get("MIMO_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("MiMo API key not provided. Set MIMO_API_KEY or pass --mimo-api-key.")
    return key


def build_mimo_payload(
    *,
    model,
    messages,
    max_tokens=None,
    max_completion_tokens=None,
    temperature=None,
    top_p=None,
    **kwargs,
):
    token_limit = max_completion_tokens if max_completion_tokens is not None else max_tokens
    payload = {
        "model": model,
        "messages": messages,
    }
    if token_limit is not None:
        payload["max_completion_tokens"] = token_limit
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p

    for key, value in kwargs.items():
        if key in UNSUPPORTED_OPENAI_PARAMS or value is None:
            continue
        payload[key] = value

    # MiMo often writes visible answers into reasoning_content when thinking is on.
    # FreeGrasp expects a terse "[id, class]" string in message.content.
    payload.setdefault("chat_template_kwargs", {"enable_thinking": False})
    return payload


def parse_mimo_response(data):
    choices = []
    for choice in data.get("choices", []):
        message = choice.get("message", {}) or {}
        content = message.get("content") or ""
        reasoning_content = message.get("reasoning_content")
        if not content and reasoning_content:
            content = reasoning_content
        choices.append(
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning_content,
                )
            )
        )
    if not choices:
        raise MiMoAPIError(f"MiMo response did not contain choices: {data}")
    return SimpleNamespace(choices=choices, raw_response=data)


class MiMoCompletions:
    def __init__(self, client):
        self._client = client

    def create(self, **kwargs):
        payload = build_mimo_payload(**kwargs)
        response = self._client.http_client.post(
            f"{self._client.base_url}/chat/completions",
            headers={
                "api-key": self._client.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise MiMoAPIError(f"MiMo API error {response.status_code}: {detail}")
        return parse_mimo_response(response.json())


class MiMoChat:
    def __init__(self, client):
        self.completions = MiMoCompletions(client)


class MiMoClient:
    def __init__(self, api_key, base_url, http_client=None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=120, trust_env=False)
        self.chat = MiMoChat(self)


def create_mimo_client(api_key: str | None = None, base_url: str | None = None, http_client=None):
    clear_proxy_environment()
    resolved_key = resolve_mimo_api_key(api_key)
    resolved_base_url = base_url or os.environ.get("MIMO_BASE_URL") or default_mimo_base_url(resolved_key)
    return MiMoClient(api_key=resolved_key, base_url=resolved_base_url, http_client=http_client)


def validate_mimo_supports_image_input(client, model_name: str) -> None:
    try:
        client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": ONE_PIXEL_PNG_DATA_URL}},
                        {"type": "text", "text": "Reply with OK."},
                    ],
                }
            ],
            max_completion_tokens=16,
            temperature=0,
        )
    except MiMoAPIError as exc:
        message = str(exc)
        if "support image input" in message:
            raise RuntimeError(
                f"MiMo model/base URL does not support image input: model={model_name}, "
                f"base_url={client.base_url}. FreeGrasp requires image input. "
                f"Use a vision-capable model such as {VISION_MODEL_HINT}."
            ) from exc
        raise


def patch_freegrasp_client(mimo_client, mimo_api_key: str | None = None):
    ensure_unused_dashscope_key_for_import()

    import utils.config as config
    import utils.utils as utils_module

    config.client = mimo_client
    utils_module.client = mimo_client
    config.api_key = mimo_api_key or os.environ.get("MIMO_API_KEY") or os.environ.get("OPENAI_API_KEY", "")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run FreeGrasp evaluation using MiMo vision model.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help=f"MiMo vision model name (default: {DEFAULT_MODEL_NAME})")
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
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument(
        "--mimo-retry-mode",
        choices=[
            "none",
            "original_protocol",
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
            "unified_hard_safe_v1",
            "unified_hard_safe_no_hard_fallback",
            "unified_hard_safe_no_ranked_candidates",
            "unified_hard_safe_no_point_repair",
            "unified_hard_safe_no_id_repair",
        ],
        default="none",
    )
    parser.add_argument(
        "--routing-variant",
        choices=["none", "count_only", "vlm_two_stage", "predicted_geometry", "scene_complexity", "scene_complexity_vlm"],
        default="none",
    )
    parser.add_argument(
        "--feature-source",
        choices=["none", "predicted", "oracle_feature"],
        default="none",
    )
    parser.add_argument(
        "--route-guard-variant",
        choices=["none", "conservative_v1", "target_evidence_v2"],
        default="none",
    )
    parser.add_argument("--run-dir", default=None, help="Existing or new run directory.")
    parser.add_argument("--resume", action="store_true", help="Resume from existing out_*.json rows.")
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    parser.add_argument(
        "--skip-mimo-preflight",
        action="store_false",
        dest="mimo_preflight",
        help="Skip the small startup check that verifies MiMo image input support.",
    )
    parser.add_argument("--mimo-api-key", default=None, help="MiMo API key (env MIMO_API_KEY used if not provided)")
    parser.add_argument(
        "--mimo-base-url",
        default=None,
        help=(
            "MiMo API base URL. For tp-* Token Plan keys, use the subscription URL, "
            f"for example {TOKEN_PLAN_BASE_URL}."
        ),
    )

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
    parser.set_defaults(reuse_molmo=True, resume=True, mimo_preflight=True)
    return parser.parse_args(argv)


def evaluate_mimo_pipeline(
    model_name: str = DEFAULT_MODEL_NAME,
    prompt_variant: str = "legacy",
    max_output_tokens: int = 256,
    reuse_molmo: bool = True,
    resume: bool = True,
    run_dir: str | None = None,
    mimo_api_key: str | None = None,
    mimo_base_url: str | None = None,
    mimo_preflight: bool = True,
    mimo_retry_mode: str = "none",
    segmentation_variant: str = "baseline",
    subset_policy: str = "none",
    routing_variant: str = "none",
    feature_source: str = "none",
    route_guard_variant: str = "none",
):
    mimo_client = create_mimo_client(api_key=mimo_api_key, base_url=mimo_base_url)
    if mimo_preflight:
        validate_mimo_supports_image_input(mimo_client, model_name)

    patch_freegrasp_client(mimo_client, mimo_api_key=mimo_api_key)

    from evaluate_all import evaluate_pipeline

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    if run_dir is None:
        run_dir = os.path.join("data/output", f"{model_name}_{timestamp}")

    print(f"Using MiMo model: {model_name}")
    print(f"Using MiMo base URL: {mimo_client.base_url}")
    return evaluate_pipeline(
        model_name=model_name,
        prompt_variant=prompt_variant,
        max_output_tokens=max_output_tokens,
        mimo_retry_mode=mimo_retry_mode,
        segmentation_variant=segmentation_variant,
        subset_policy=subset_policy,
        routing_variant=routing_variant,
        feature_source=feature_source,
        route_guard_variant=route_guard_variant,
        reuse_molmo=reuse_molmo,
        resume=resume,
        run_dir=run_dir,
    )


if __name__ == "__main__":
    args = parse_args()
    evaluate_mimo_pipeline(
        model_name=args.model_name,
        prompt_variant=args.prompt_variant,
        max_output_tokens=args.max_output_tokens,
        reuse_molmo=args.reuse_molmo,
        resume=args.resume,
        run_dir=args.run_dir,
        mimo_api_key=args.mimo_api_key,
        mimo_base_url=args.mimo_base_url,
        mimo_preflight=args.mimo_preflight,
        mimo_retry_mode=args.mimo_retry_mode,
        segmentation_variant=args.segmentation_variant,
        subset_policy=args.subset_policy,
        routing_variant=args.routing_variant,
        feature_source=args.feature_source,
        route_guard_variant=args.route_guard_variant,
    )
