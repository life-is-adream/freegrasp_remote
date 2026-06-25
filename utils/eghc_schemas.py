"""EGHC-v1 dataclasses and schema helpers."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RouteDecision:
    """Result of the deterministic guard router."""
    selected_route: str  # "direct", "target_first", "blocker_first"
    selection_source: str  # "guard", "challenger", "adjudicator"
    guard_reasons: list = field(default_factory=list)
    requires_adjudication: bool = False


@dataclass(frozen=True)
class Call1Assessment:
    """MiMo Call 1 output: target visibility and blocking analysis."""
    target_candidates: list = field(default_factory=list)
    target_visibility: str = "uncertain"  # free_visible, visible_but_blocked, mostly_hidden, uncertain
    blocking_relations: list = field(default_factory=list)
    recommended_route: str = "target_first"
    confidence: float = 0.0


@dataclass(frozen=True)
class Call2Plan:
    """MiMo Call 2 output: first grasp plan."""
    first_grasp_object_id: Optional[int] = None
    action: str = "grasp_target"  # grasp_target, remove_blocker
    mask_query: str = ""
    confidence: float = 0.0
    ranked_candidates: list = field(default_factory=list)


@dataclass(frozen=True)
class SealedPrediction:
    """Immutable prediction artifact for scoring."""
    sample_key: dict = field(default_factory=dict)
    reasoning: dict = field(default_factory=dict)
    mask_path: str = ""
