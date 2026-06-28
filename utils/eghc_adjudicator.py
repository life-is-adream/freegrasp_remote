"""EGHC-v1 adjudication logic.

Determines when to trigger Qwen adjudication based on
assessment, route decision, plan, and visible IDs.
"""

import json
import os
import re


QWEN_ADJUDICATOR_MODEL = "qwen3.5-plus-2026-04-20"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MIMO_DASHSCOPE_PLACEHOLDER = "unused-by-evaluate-mimo"
CONSENSUS_ROUTE_GUARD = "eghc_consensus_v1"


def should_trigger_adjudication(assessment, route_decision, plan, visible_ids):
    """Check if Qwen adjudication should be triggered.

    Parameters
    ----------
    assessment : dict
        Call 1 assessment.
    route_decision : dict
        Route decision from eghc_router.
    plan : dict
        Call 2 plan with first_grasp_object_id.
    visible_ids : set or list
        Set of visible object IDs.

    Returns
    -------
    bool
        True if adjudication should be triggered.
    """
    if isinstance(visible_ids, list):
        visible_ids = set(visible_ids)

    consensus_mode = route_decision.get("route_guard_variant") == CONSENSUS_ROUTE_GUARD
    evaluation_subset = str(route_decision.get("evaluation_subset") or "")
    if (
        consensus_mode
        and evaluation_subset.startswith("easy_")
        and route_decision.get("selected_route") == "direct"
    ):
        return False

    # Invalid object ID
    if plan.get("first_grasp_object_id") not in visible_ids:
        return True

    # Direct route but blocking relations exist
    if route_decision.get("selected_route") == "direct" and assessment.get("blocking_relations"):
        return True

    # Blocker-first is the highest-risk branch: a valid ID can still be the
    # wrong blocker, so the heterogeneous verifier reviews it.
    if route_decision.get("selected_route") == "blocker_first":
        return True

    # Low confidence
    if plan.get("confidence", 1.0) < 0.60:
        return True

    return False


def adjudication_prompt(route_guard_variant="none"):
    if route_guard_variant == CONSENSUS_ROUTE_GUARD:
        return (
            "You are the EGHC consensus/veto adjudicator. Review the proposed "
            "first-grasp plan using only the labeled RGB image, visible object "
            "IDs, the target description, and supplied MiMo reasoning. Default "
            "to keep. You may only replace when vetoing a blocker-first plan "
            "back to the known target candidate, or repairing an invalid ID to "
            "the known target candidate. Do not choose a new third object. "
            "Return exactly one compact JSON object with keys: decision, "
            "first_grasp_object_id, first_grasp_label, mask_query, confidence, "
            "reason. decision must be keep or replace."
        )
    return (
        "You are the heterogeneous EGHC adjudicator. Review the proposed "
        "first-grasp plan using only the labeled RGB image, visible object IDs, "
        "the target description, and the supplied MiMo reasoning. You may keep "
        "the plan or replace it with another visible object ID. You must not "
        "invent IDs. Return exactly one compact JSON object with keys: "
        "decision, first_grasp_object_id, first_grasp_label, mask_query, "
        "confidence, reason. decision must be keep or replace."
    )


def format_adjudication_input(
    input_text,
    assessment,
    route_decision,
    plan,
    visible_ids,
    route_guard_variant="none",
):
    visible = ", ".join(str(item) for item in sorted(set(visible_ids)))
    consensus_note = ""
    if route_guard_variant == CONSENSUS_ROUTE_GUARD:
        consensus_note = (
            "\nConsensus/veto rule: keep unless replacement is the known target "
            "candidate ID. Do not replace with a new blocker or unrelated ID."
        )
    return (
        f"{input_text}\n\n"
        f"Visible object IDs: {visible}\n"
        f"EGHC assessment: {json.dumps(assessment, sort_keys=True, default=str)}\n"
        f"Route decision: {json.dumps(route_decision, sort_keys=True, default=str)}\n"
        f"MiMo first-grasp plan: {json.dumps(plan, sort_keys=True, default=str)}\n"
        "If replacing, choose one visible ID and provide a complete mask_query."
        f"{consensus_note}"
    )


def _extract_json_object(output):
    match = re.search(r"\{.*\}", str(output or ""), flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reject_replacement(data, current_plan, reason, decision="reject_non_consensus_replacement"):
    return {
        "accepted": False,
        "decision": decision,
        "plan": dict(current_plan),
        "reason": reason,
        "raw_adjudication": data,
    }


def parse_adjudication_output(
    output,
    current_plan,
    visible_ids,
    route_decision=None,
    assessment=None,
):
    """Parse Qwen output and apply strict replacement acceptance rules."""
    visible = set(visible_ids)
    data = _extract_json_object(output)
    decision = str(data.get("decision", "keep")).lower()
    if decision != "replace":
        return {
            "accepted": False,
            "decision": "keep",
            "plan": dict(current_plan),
            "reason": str(data.get("reason", "qwen_kept_current_plan")),
            "raw_adjudication": data,
        }

    object_id = _coerce_int(data.get("first_grasp_object_id"))
    if object_id not in visible:
        return {
            "accepted": False,
            "decision": "reject_invalid_replacement",
            "plan": dict(current_plan),
            "reason": f"invalid_replacement_id:{object_id}",
            "raw_adjudication": data,
        }

    label = str(data.get("first_grasp_label") or data.get("mask_query") or "")
    mask_query = str(data.get("mask_query") or label)
    if not mask_query.strip():
        return {
            "accepted": False,
            "decision": "reject_incomplete_replacement",
            "plan": dict(current_plan),
            "reason": "invalid_replacement_missing_mask_query",
            "raw_adjudication": data,
        }

    route_decision = route_decision or {}
    assessment = assessment or {}
    consensus_mode = route_decision.get("route_guard_variant") == CONSENSUS_ROUTE_GUARD
    if consensus_mode:
        current_id = _coerce_int(current_plan.get("first_grasp_object_id"))
        target_id = _coerce_int(assessment.get("target_object_id"))
        confidence = _coerce_float(data.get("confidence", 0.0))

        if object_id == current_id:
            return _reject_replacement(
                data,
                current_plan,
                "qwen_consensus_keep_current_plan",
                decision="consensus_keep",
            )

        if object_id != target_id:
            return _reject_replacement(
                data,
                current_plan,
                f"non_consensus_replacement_id:{object_id}",
            )

        current_invalid = current_id not in visible
        if current_invalid and confidence >= 0.70:
            consensus_decision = "repair_invalid_to_target"
        elif (
            route_decision.get("selected_route") == "blocker_first"
            and confidence >= 0.80
        ):
            consensus_decision = "veto_to_target"
        else:
            return _reject_replacement(
                data,
                current_plan,
                f"non_consensus_low_confidence:{confidence:.2f}",
            )
    else:
        consensus_decision = "replace"

    replacement = dict(current_plan)
    replacement.update(
        {
            "first_grasp_object_id": object_id,
            "first_grasp_label": label or mask_query,
            "mask_query": mask_query,
            "confidence": _coerce_float(data.get("confidence", 0.0)),
        }
    )
    return {
        "accepted": True,
        "decision": consensus_decision,
        "plan": replacement,
        "reason": str(data.get("reason", "qwen_replacement_accepted")),
        "raw_adjudication": data,
    }


def resolve_qwen_api_key(env=None):
    env = env or os.environ
    qwen_key = env.get("QWEN_API_KEY")
    if qwen_key:
        return qwen_key
    dashscope_key = env.get("DASHSCOPE_API_KEY")
    if dashscope_key and dashscope_key != MIMO_DASHSCOPE_PLACEHOLDER:
        return dashscope_key
    return None


def call_qwen_adjudicator(
    messages,
    *,
    model=QWEN_ADJUDICATOR_MODEL,
    max_output_tokens=512,
    client=None,
):
    """Call Qwen with an independent DashScope client.

    Tests should mock this function. Live use requires separate paid approval
    and a DASHSCOPE_API_KEY or QWEN_API_KEY.
    """
    if client is None:
        api_key = resolve_qwen_api_key()
        if not api_key:
            raise RuntimeError(
                "Qwen adjudication requires DASHSCOPE_API_KEY or QWEN_API_KEY"
            )
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=QWEN_BASE_URL)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=max_output_tokens,
        top_p=1,
    )
    return response.choices[0].message.content or ""
