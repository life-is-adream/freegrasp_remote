"""B1 v6 routing-only policy and deployable input boundary.

This module is CPU-only.  It does not import a model, segmentation backend,
or scoring code.  A/D/E use deployable evidence; O is an explicitly isolated
diagnostic path and must never be used by the deployment runner.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence


VALID_ROUTES = ("direct", "target_first", "blocker_first")
VALID_DIFFICULTIES = ("easy", "medium", "hard")
DIRECT_CONFIDENCE = 0.75
STRONG_RELATION_TERMS = ("cover", "occlud", "overlap", "contact", "on top", "on-top")
OBSTRUCTION_TERMS = ("under", "behind", "covered", "blocked", "occluded", "on top", "on-top")
SPATIAL_TERMS = ("left", "right", "top", "bottom", "center", "middle", "nearest", "farthest", "above", "below")

FIXED_PLANNER_PROMPTS = {
    "direct": "direct_bypass",
    "target_first": "target_first_evidence_gate_v9_json",
    "blocker_first": "hard_blocker_first_v10_json",
}

# Keys that must never reach A/D/E model payloads or policy selection.
FORBIDDEN_KEYS = {
    "difficulty",
    "evaluation_subset",
    "subset",
    "scene_id",
    "scene",
    "row_id",
    "gt_id",
    "gt_ids",
    "ground_truth",
    "groundtruth",
    "target_gt_id",
    "mapped_id",
    "selected_gt_id",
    "ssr",
    "rsr",
    "ssr_correct",
    "rsr_correct",
    "iou",
    "historical_score",
    "historical_route",
    "label_source",
}

ALLOWED_PACKET_KEYS = {
    "image",
    "image_sha256",
    "instruction",
    "candidates",
    "candidate_geometry",
    "duplicate_mask_conflict",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normal_key(key: Any) -> str:
    return str(key).strip().lower()


def _walk_forbidden(value: Any, path: str = "") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_norm = _normal_key(key)
            child_path = f"{path}.{key}" if path else str(key)
            if key_norm in FORBIDDEN_KEYS:
                found.append({"path": child_path, "key": key_norm})
            found.extend(_walk_forbidden(child, child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_walk_forbidden(child, f"{path}[{index}]"))
    return found


def assert_deployable_packet(packet: Mapping[str, Any], *, allow_oracle: bool = False) -> None:
    """Fail closed if inference input includes identity, difficulty, or score leakage."""

    if not isinstance(packet, Mapping):
        raise TypeError("inference packet must be a mapping")
    unknown = sorted(set(packet) - ALLOWED_PACKET_KEYS)
    if unknown:
        raise ValueError(f"unknown inference keys: {unknown}")
    forbidden = _walk_forbidden(packet)
    if forbidden:
        raise ValueError(f"forbidden inference fields: {forbidden}")
    if not isinstance(packet.get("instruction"), str) or not packet["instruction"].strip():
        raise ValueError("instruction is required")
    candidates = packet.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("candidates must be a sequence")
    seen: set[int] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise ValueError(f"candidate {index} is not a mapping")
        candidate_forbidden = _walk_forbidden(candidate, f"candidates[{index}]")
        if candidate_forbidden:
            raise ValueError(f"forbidden candidate fields: {candidate_forbidden}")
        object_id = candidate.get("id", candidate.get("object_id"))
        if not isinstance(object_id, int) or isinstance(object_id, bool):
            raise ValueError(f"candidate {index} has no integer visible id")
        if object_id in seen:
            raise ValueError(f"duplicate visible candidate id: {object_id}")
        seen.add(object_id)


def sanitize_deployable_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact allowlisted shape sent to an inference stage."""

    assert_deployable_packet(packet)
    candidates = []
    for candidate in packet["candidates"]:
        item = {"id": candidate.get("id", candidate.get("object_id"))}
        for key in ("label", "point", "bbox", "center", "relations", "rank", "geometry"):
            if key in candidate:
                item[key] = copy.deepcopy(candidate[key])
        candidates.append(item)
    result: dict[str, Any] = {
        "instruction": str(packet["instruction"]),
        "candidates": candidates,
    }
    for key in ("image", "image_sha256", "candidate_geometry", "duplicate_mask_conflict"):
        if key in packet:
            result[key] = copy.deepcopy(packet[key])
    return result


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _valid_candidates(assessment: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        candidate
        for candidate in assessment.get("target_candidates", [])
        if isinstance(candidate, Mapping) and candidate.get("valid", True)
    ]


def _relation_strength(relation: Any) -> int:
    if not isinstance(relation, Mapping):
        text = str(relation).lower()
        return int(any(term in text for term in STRONG_RELATION_TERMS))
    score = int(relation.get("blocker_id", relation.get("object_id")) is not None)
    text = " ".join(str(relation.get(key, "")) for key in ("relation", "evidence", "type")).lower()
    score += int(any(term in text for term in STRONG_RELATION_TERMS))
    score += int(_coerce_float(relation.get("confidence", relation.get("score", 0.0))) >= DIRECT_CONFIDENCE)
    return score


def _has_strong_blocking_evidence(assessment: Mapping[str, Any]) -> bool:
    if _coerce_float(assessment.get("route_confidence", 0.0)) < DIRECT_CONFIDENCE:
        return False
    return any(_relation_strength(relation) >= 2 for relation in assessment.get("blocking_relations", []))


def _clean_route(assessment: Mapping[str, Any], *, route_guard_variant: str = "pathb_blk_arb_v1") -> dict[str, Any]:
    """Mirror the current clean B1 guard semantics without benchmark fields."""

    valid_target_candidates = _valid_candidates(assessment)
    relations = assessment.get("blocking_relations") or []
    consensus_mode = route_guard_variant in {
        "eghc_consensus_v1",
        "pathb_blk_arb_v1",
        "pathb_blk_clut_v1",
        "pathb_disamb_v1",
    }
    clean_direct = (
        bool(valid_target_candidates)
        and assessment.get("target_visibility") == "free_visible"
        and not relations
        and not assessment.get("duplicate_mask_conflict")
        and _coerce_float(assessment.get("route_confidence", 0.0)) >= DIRECT_CONFIDENCE
    )
    if consensus_mode and clean_direct:
        return {
            "selected_route": "direct",
            "selection_source": "guard",
            "guard_reasons": ["clean_direct_evidence"],
            "requires_adjudication": False,
        }
    guard_reasons: list[str] = []
    if assessment.get("recommended_route") == "direct":
        if not valid_target_candidates:
            guard_reasons.append("missing_valid_target_candidate")
        if assessment.get("target_visibility") != "free_visible":
            guard_reasons.append("target_not_free_visible")
        if relations:
            guard_reasons.append("credible_blocking_evidence")
        if assessment.get("duplicate_mask_conflict"):
            guard_reasons.append("duplicate_mask_conflict")
        if not guard_reasons:
            return {
                "selected_route": "direct",
                "selection_source": "guard",
                "guard_reasons": [],
                "requires_adjudication": False,
            }
    if assessment.get("recommended_route") == "blocker_first" and relations:
        if consensus_mode and not _has_strong_blocking_evidence(assessment):
            return {
                "selected_route": "target_first",
                "selection_source": "guard",
                "guard_reasons": ["weak_blocker_evidence"],
                "requires_adjudication": True,
            }
        return {
            "selected_route": "blocker_first",
            "selection_source": "guard",
            "guard_reasons": [],
            "requires_adjudication": False,
        }
    return {
        "selected_route": "target_first",
        "selection_source": "guard",
        "guard_reasons": guard_reasons or ["target_first_default"],
        "requires_adjudication": False,
    }


def build_e_router_prompt(base_prompt: str) -> str:
    """Build E's evidence-first router prompt while preserving the B1 schema."""

    supplement = (
        "\n\nE routing evidence contract (deployable evidence only):\n"
        "Before selecting a route, resolve the requested target among visible numeric IDs. "
        "Then record whether the target is free_visible, visible_but_blocked, mostly_hidden, or uncertain. "
        "Treat target identity, first-grasp identity, and blocker identity as separate decisions. "
        "A blocker relation must connect a visible blocker to the target and be supported by image evidence "
        "such as coverage, contact, on-top, or a credible overlap; proximity alone is insufficient. "
        "If the image evidence and the proposed visibility/route conflict, preserve the conflict in the existing "
        "evidence fields and choose the route supported by the strongest visible evidence. "
        "Use a numeric route_confidence in [0,1]. Do not use benchmark difficulty, subset names, scene identifiers, "
        "ground truth IDs, historical scores, or row identity.\n"
        "Keep exactly the original output keys and JSON schema: target_candidates, target_visibility, "
        "blocking_relations, recommended_route, route_confidence."
    )
    return str(base_prompt) + supplement


def build_a_router_prompt(base_prompt: str) -> str:
    return str(base_prompt)


def build_d_router_prompt(base_prompt: str) -> str:
    # D changes the post-router policy; its upstream router prompt remains fixed.
    return str(base_prompt)


def _assessment_features(packet: Mapping[str, Any], assessment: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(packet.get("candidates", []))
    labels = [str(c.get("label", "")).strip().lower() for c in candidates]
    labels = [label for label in labels if label and label != "unknown"]
    counts = Counter(labels)
    duplicate_groups = sum(1 for count in counts.values() if count > 1)
    relations = assessment.get("blocking_relations") or []
    text = str(packet.get("instruction", "")).lower()
    obstruction_terms = sum(text.count(term) for term in OBSTRUCTION_TERMS)
    spatial_terms = sum(text.count(term) for term in SPATIAL_TERMS)
    visibility = assessment.get("target_visibility", "uncertain")
    conflict = bool(relations) and visibility == "free_visible"
    return {
        "candidate_count": len(candidates),
        "duplicate_label_groups": duplicate_groups,
        "max_same_label": max(counts.values(), default=0),
        "relation_count": len(relations),
        "strong_relation_count": sum(_relation_strength(relation) >= 2 for relation in relations),
        "obstruction_term_count": obstruction_terms,
        "spatial_term_count": spatial_terms,
        "visibility": visibility,
        "conflict": conflict,
    }


def predict_task_evidence(packet: Mapping[str, Any], assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Convert router output into route-relevant evidence; no difficulty input."""

    assert_deployable_packet(packet)
    features = _assessment_features(packet, assessment)
    valid = _valid_candidates(assessment)
    target_id = assessment.get("target_object_id")
    ambiguity = len(valid) != 1 or bool(assessment.get("ambiguity_evidence"))
    relation_supported = any(
        isinstance(relation, Mapping)
        and relation.get("blocker_id", relation.get("object_id")) is not None
        and relation.get("target_id", relation.get("blocked_id")) is not None
        and _relation_strength(relation) >= 2
        for relation in assessment.get("blocking_relations", [])
    )
    if target_id is None and len(valid) == 1:
        target_id = valid[0].get("object_id", valid[0].get("id"))
    return {
        "target_id": target_id,
        "target_candidate_count": len(valid),
        "ambiguity": ambiguity,
        "visibility": assessment.get("target_visibility", "uncertain"),
        "relation_count": features["relation_count"],
        "relation_supported": relation_supported,
        "conflict": features["conflict"],
        "features": features,
    }


def select_e_route(packet: Mapping[str, Any], assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Select route from predicted task evidence using a frozen, auditable rule."""

    evidence = predict_task_evidence(packet, assessment)
    valid = _valid_candidates(assessment)
    visibility = evidence["visibility"]
    recommended = assessment.get("recommended_route")
    if (
        len(valid) == 1
        and visibility == "free_visible"
        and evidence["relation_count"] == 0
        and not evidence["conflict"]
    ):
        route = "direct"
        reasons = ["E_unique_free_target_no_relation"]
    elif (
        evidence["relation_supported"]
        and visibility in {"visible_but_blocked", "mostly_hidden", "uncertain"}
        and not evidence["ambiguity"]
    ):
        route = "blocker_first"
        reasons = ["E_supported_blocker_target_relation"]
    else:
        route = "target_first"
        reasons = []
        if evidence["ambiguity"]:
            reasons.append("E_target_ambiguity_or_missing_candidate")
        if evidence["conflict"]:
            reasons.append("E_visibility_relation_conflict")
        if not reasons:
            reasons.append("E_conservative_target_first_fallback")
    return {
        "selected_route": route,
        "pre_guard_route": recommended,
        "selection_source": "E_task_evidence_rule",
        "guard_reasons": reasons,
        "requires_adjudication": False,
        "task_evidence": evidence,
    }


def compute_difficulty_features(packet: Mapping[str, Any]) -> dict[str, float]:
    """Compute a deployable structural feature vector without an assessment label."""

    assert_deployable_packet(packet)
    candidates = list(packet.get("candidates", []))
    labels = [str(c.get("label", "")).strip().lower() for c in candidates]
    known_labels = [label for label in labels if label and label != "unknown"]
    counts = Counter(known_labels)
    duplicate_groups = sum(1 for count in counts.values() if count > 1)
    text = str(packet["instruction"]).lower()
    obstruction_terms = sum(text.count(term) for term in OBSTRUCTION_TERMS)
    spatial_terms = sum(text.count(term) for term in SPATIAL_TERMS)
    geometry = packet.get("candidate_geometry")
    relation_count = 0
    if isinstance(geometry, Mapping):
        relation_count = len(geometry.get("relations", []) or [])
    elif isinstance(geometry, Sequence) and not isinstance(geometry, (str, bytes)):
        relation_count = len(geometry)
    unknown_fraction = 1.0 - (len(known_labels) / max(1, len(labels)))
    complexity_score = (
        max(0, len(candidates) - 1)
        + 1.5 * duplicate_groups
        + 2.0 * relation_count
        + 1.5 * obstruction_terms
        + 0.5 * spatial_terms
        + 0.5 * unknown_fraction
    )
    return {
        "candidate_count": float(len(candidates)),
        "duplicate_label_groups": float(duplicate_groups),
        "relation_count": float(relation_count),
        "obstruction_term_count": float(obstruction_terms),
        "spatial_term_count": float(spatial_terms),
        "unknown_label_fraction": float(unknown_fraction),
        "complexity_score": float(complexity_score),
    }


def fit_difficulty_artifact(dev_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Freeze D's predictor and route map from scene-grouped development data.

    The route map reproduces the observed development route distribution.  It
    is deliberately not an oracle: no counterfactual route outcomes are used
    or fabricated, and SSR/RSR fields are rejected from the fitting records.
    """

    if not dev_records:
        raise ValueError("development records are required")
    by_difficulty: dict[str, list[float]] = defaultdict(list)
    training_scores: list[tuple[str, float]] = []
    route_counts: dict[str, Counter[str]] = defaultdict(Counter)
    scene_to_split: dict[str, str] = {}
    fit_groups: list[str] = []
    for record in dev_records:
        if any(key in record for key in ("ssr", "rsr", "iou", "gt_ids", "scene_id", "subset")):
            raise ValueError("development fitting cannot use score, GT, subset, or scene_id fields")
        difficulty = str(record.get("difficulty", ""))
        if difficulty not in VALID_DIFFICULTIES:
            raise ValueError(f"invalid development difficulty: {difficulty}")
        group = str(record.get("scene_group", ""))
        split = str(record.get("split", "dev"))
        observed_route = str(record.get("observed_route", ""))
        if not group or observed_route not in VALID_ROUTES:
            raise ValueError("scene_group and observed_route are required")
        prior_split = scene_to_split.setdefault(group, split)
        if prior_split != split:
            raise ValueError(f"scene group crosses splits: {group}")
        packet = record.get("packet")
        assert_deployable_packet(packet)
        features = compute_difficulty_features(packet)
        by_difficulty[difficulty].append(features["complexity_score"])
        training_scores.append((difficulty, features["complexity_score"]))
        route_counts[difficulty][observed_route] += 1
        fit_groups.append(group)
    centroids = {
        difficulty: sum(scores) / len(scores)
        for difficulty, scores in by_difficulty.items()
    }
    missing = sorted(set(VALID_DIFFICULTIES) - set(centroids))
    if missing:
        raise ValueError(f"development data missing difficulty classes: {missing}")
    training_distances = sorted(abs(score - centroids[difficulty]) for difficulty, score in training_scores)
    # This is a development-only uncertainty gate.  The quantile is frozen
    # before split0 execution; uncertain predictions fall back to clean A.
    quantile = 0.35
    q_index = min(len(training_distances) - 1, max(0, int(quantile * len(training_distances)) - 1))
    fallback_distance = training_distances[q_index]
    route_map: dict[str, str] = {}
    for difficulty in VALID_DIFFICULTIES:
        counts = route_counts[difficulty]
        route_map[difficulty] = sorted(VALID_ROUTES, key=lambda route: (-counts[route], VALID_ROUTES.index(route)))[0]
    return {
        "artifact_version": "b1-v6-difficulty-route-v1",
        "frozen": True,
        "predictor": "nearest_complexity_centroid",
        "centroids": centroids,
        "route_map": route_map,
        "route_counts": {difficulty: dict(route_counts[difficulty]) for difficulty in VALID_DIFFICULTIES},
        "mapping_source": "development_observed_route_frequency",
        "fallback_policy": "clean_A_when_centroid_distance_exceeds_frozen_dev_quantile",
        "fallback_distance_quantile": quantile,
        "fallback_distance": fallback_distance,
        "counterfactual_missing": True,
        "fit_scene_groups_sha256": canonical_hash(sorted(set(fit_groups))),
    }


def predict_difficulty(packet: Mapping[str, Any], artifact: Mapping[str, Any]) -> dict[str, Any]:
    assert_deployable_packet(packet)
    if not artifact.get("frozen"):
        raise ValueError("D artifact must be frozen before inference")
    features = compute_difficulty_features(packet)
    centroids = artifact.get("centroids", {})
    if set(centroids) != set(VALID_DIFFICULTIES):
        raise ValueError("D artifact must contain all three difficulty centroids")
    difficulty = min(VALID_DIFFICULTIES, key=lambda label: (abs(features["complexity_score"] - float(centroids[label])), VALID_DIFFICULTIES.index(label)))
    return {
        "predicted_difficulty": difficulty,
        "complexity_score": features["complexity_score"],
        "centroid_distance": abs(features["complexity_score"] - float(centroids[difficulty])),
        "features": features,
        "mapping_sha256": canonical_hash(artifact),
    }


def select_d_route(packet: Mapping[str, Any], assessment: Mapping[str, Any], artifact: Mapping[str, Any]) -> dict[str, Any]:
    prediction = predict_difficulty(packet, artifact)
    route = artifact.get("route_map", {}).get(prediction["predicted_difficulty"])
    if route not in VALID_ROUTES:
        raise ValueError("frozen D route map has no valid route")
    if (
        artifact.get("fallback_distance") is not None
        and prediction["centroid_distance"] > float(artifact["fallback_distance"])
    ):
        clean = _clean_route(assessment)
        clean.update({
            "selection_source": "D_uncertain_fallback_to_A_clean_route",
            "difficulty_prediction": prediction,
            "counterfactual_missing": True,
        })
        return clean
    return {
        "selected_route": route,
        "pre_guard_route": assessment.get("recommended_route"),
        "selection_source": "D_predicted_difficulty_mapping",
        "guard_reasons": [f"D_predicted_{prediction['predicted_difficulty']}"],
        "requires_adjudication": False,
        "difficulty_prediction": prediction,
        "counterfactual_missing": True,
    }


def select_o_route(
    packet: Mapping[str, Any],
    assessment: Mapping[str, Any],
    *,
    true_difficulty: str,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Isolated O diagnostic.  The true label is a separate non-deployment input."""

    assert_deployable_packet(packet)
    if true_difficulty not in VALID_DIFFICULTIES:
        raise ValueError("invalid oracle diagnostic difficulty")
    route = artifact.get("route_map", {}).get(true_difficulty)
    if route not in VALID_ROUTES:
        raise ValueError("O requires the same frozen route map used by D")
    return {
        "selected_route": route,
        "pre_guard_route": assessment.get("recommended_route"),
        "selection_source": "O_isolated_true_difficulty_diagnostic",
        "guard_reasons": [f"O_true_{true_difficulty}"],
        "requires_adjudication": False,
        "oracle_diagnostic": True,
        "counterfactual_missing": True,
    }


def select_route(
    arm: str,
    packet: Mapping[str, Any],
    assessment: Mapping[str, Any],
    *,
    difficulty_artifact: Mapping[str, Any] | None = None,
    true_difficulty: str | None = None,
    route_guard_variant: str = "pathb_blk_arb_v1",
) -> dict[str, Any]:
    if arm == "A":
        result = _clean_route(assessment, route_guard_variant=route_guard_variant)
        result["selection_source"] = "A_clean_route_guard"
        result["counterfactual_missing"] = True
        return result
    if arm == "D":
        if difficulty_artifact is None:
            raise ValueError("D requires a frozen difficulty artifact")
        return select_d_route(packet, assessment, difficulty_artifact)
    if arm == "E":
        result = select_e_route(packet, assessment)
        result["counterfactual_missing"] = True
        return result
    if arm == "O":
        if true_difficulty is None or difficulty_artifact is None:
            raise ValueError("O requires explicit isolated true_difficulty and a frozen artifact")
        return select_o_route(packet, assessment, true_difficulty=true_difficulty, artifact=difficulty_artifact)
    raise ValueError(f"unknown arm: {arm}")


def route_to_prompt_variant(route: str) -> str:
    if route not in FIXED_PLANNER_PROMPTS:
        raise ValueError(f"unknown route: {route}")
    return FIXED_PLANNER_PROMPTS[route]
