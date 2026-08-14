from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from data_intelligence_hub.schemas.capability_catalog import CapabilityScoreProfile
from data_intelligence_hub.schemas.workflow_planner import (
    BudgetCeiling,
    PolicyProfile,
    ScoreBreakdown,
)

MARKET_MONITORING_BALANCED_WEIGHTS = {
    "coverage": 15,
    "freshness": 15,
    "history": 5,
    "reliability": 20,
    "schema_stability": 15,
    "cost_efficiency": 10,
    "maintainability": 5,
    "evidence_confidence": 15,
}

assert sum(MARKET_MONITORING_BALANCED_WEIGHTS.values()) == 100


@dataclass(frozen=True)
class RoutingPolicy:
    profile: PolicyProfile
    version: str
    weights: Mapping[str, int]
    allow_partial_proposals: bool
    shadow_sample_rate: float
    shadow_max_items: int


_MARKET_MONITORING_BALANCED = RoutingPolicy(
    profile=PolicyProfile.MARKET_MONITORING_BALANCED,
    version="market_monitoring_balanced.v1",
    weights=MappingProxyType(MARKET_MONITORING_BALANCED_WEIGHTS),
    allow_partial_proposals=True,
    shadow_sample_rate=0.05,
    shadow_max_items=10,
)


def get_routing_policy(profile: PolicyProfile) -> RoutingPolicy:
    if profile is PolicyProfile.MARKET_MONITORING_BALANCED:
        return _MARKET_MONITORING_BALANCED
    raise ValueError(f"unsupported_policy_profile:{profile}")


def calculate_weighted_score(
    score_profile: CapabilityScoreProfile,
    *,
    unit_cost_usd: object | None,
    budget_ceiling: BudgetCeiling | None,
    policy: RoutingPolicy,
) -> ScoreBreakdown:
    raw_dimensions = {
        "coverage": score_profile.coverage,
        "freshness": score_profile.freshness,
        "history": score_profile.history,
        "reliability": score_profile.reliability,
        "schema_stability": score_profile.schema_stability,
        "cost_efficiency": score_profile.cost_efficiency,
        "maintainability": score_profile.maintainability,
        "evidence_confidence": score_profile.evidence_confidence,
    }
    effective_dimensions = dict(raw_dimensions)
    trace_codes: list[str] = []
    if unit_cost_usd is None:
        effective_dimensions["cost_efficiency"] = 1
        trace_codes.append("cost_score_capped_unknown")

    weights = dict(policy.weights)
    weighted_score = sum(
        effective_dimensions[dimension] * weight
        for dimension, weight in weights.items()
    )
    return ScoreBreakdown(
        raw_dimensions=raw_dimensions,
        effective_dimensions=effective_dimensions,
        weights=weights,
        weighted_score=weighted_score,
        trace_codes=trace_codes,
    )
