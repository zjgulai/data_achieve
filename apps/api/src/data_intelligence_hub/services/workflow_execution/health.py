from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.provider_health import (
    ProviderHealthRouteFeedback,
    ProviderHealthSnapshot,
)
from data_intelligence_hub.repositories.provider_health import (
    add_provider_health_feedback,
    add_provider_health_snapshot,
    get_provider_health_feedback_by_key,
    get_provider_health_snapshot_by_aggregation_key,
    list_provider_health_feedbacks_for_route,
    list_provider_health_snapshots_for_candidates,
    list_provider_health_snapshots_for_scope,
)
from data_intelligence_hub.schemas.provider_health import (
    ProviderHealthAggregationPolicy,
    ProviderHealthObservation,
    ProviderHealthRouteFeedbackRequest,
    ProviderHealthRouteFeedbackResponse,
    ProviderHealthRouteFeedbackResult,
    ProviderHealthRoutingPolicy,
    ProviderHealthSnapshotRequest,
    ProviderHealthSnapshotResponse,
    ProviderHealthSnapshotResult,
    ProviderHealthStatus,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

ProviderHealthClock = Callable[[], datetime]


class ProviderHealthContractError(RuntimeError):
    """Persisted Provider health evidence failed closed validation."""


class ProviderHealthTransactionStateError(RuntimeError):
    """The caller supplied a session with pending mutations."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


async def _prepare_session(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise ProviderHealthTransactionStateError("provider_health_transaction_state_invalid")
    if session.in_transaction():
        await session.rollback()


def _scope_key(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    platform_id: str,
    implementation_id: str,
    resource_type: str,
    operation: str,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "provider_health_scope.v1",
                "workspace_id": str(workspace_id),
                "project_id": str(project_id),
                "platform_id": platform_id,
                "implementation_id": implementation_id,
                "resource_type": resource_type,
                "operation": operation,
            },
        )
    )


def _observation_manifest(
    observations: Sequence[ProviderHealthObservation],
) -> list[dict[str, JsonValue]]:
    manifest: list[dict[str, JsonValue]] = []
    for observation in sorted(
        observations,
        key=lambda item: (_utc(item.observed_at), item.observation_id),
    ):
        basis = cast(
            JsonValue,
            {
                "observation_id": observation.observation_id,
                "observed_at": _timestamp(observation.observed_at),
                "outcome": observation.outcome,
                "latency_ms": observation.latency_ms,
                "evidence_refs": sorted(observation.evidence_refs),
            },
        )
        manifest.append(
            cast(
                dict[str, JsonValue],
                {
                    **cast(dict[str, JsonValue], basis),
                    "observation_digest": sha256_id(basis),
                },
            )
        )
    return manifest


def _policy_snapshot(policy: ProviderHealthAggregationPolicy) -> dict[str, int]:
    return cast(dict[str, int], policy.model_dump(mode="python"))


def _snapshot_metrics(
    observation_manifest: Sequence[dict[str, Any]],
    policy: ProviderHealthAggregationPolicy,
) -> tuple[dict[str, int], ProviderHealthStatus, list[str]]:
    outcomes = Counter(cast(str, item.get("outcome")) for item in observation_manifest)
    latencies = sorted(cast(int, item.get("latency_ms")) for item in observation_manifest)
    sample_count = len(observation_manifest)
    success_count = outcomes["succeeded"]
    success_rate_bps = success_count * 10_000 // sample_count
    p95_latency_ms = latencies[max(0, math.ceil(sample_count * 0.95) - 1)]
    metrics = {
        "sample_count": sample_count,
        "success_count": success_count,
        "timeout_count": outcomes["timeout"],
        "rate_limited_count": outcomes["rate_limited"],
        "transient_error_count": outcomes["transient_error"],
        "terminal_error_count": outcomes["terminal_error"],
        "success_rate_bps": success_rate_bps,
        "p95_latency_ms": p95_latency_ms,
    }
    if sample_count < policy.min_sample_size:
        return metrics, "unknown", ["provider_health_insufficient_samples"]
    unhealthy_reasons: list[str] = []
    if success_rate_bps < policy.unhealthy_success_rate_bps:
        unhealthy_reasons.append("provider_health_success_rate_unhealthy")
    if p95_latency_ms >= policy.unhealthy_p95_latency_ms:
        unhealthy_reasons.append("provider_health_latency_unhealthy")
    if unhealthy_reasons:
        return metrics, "unhealthy", unhealthy_reasons
    degraded_reasons: list[str] = []
    if success_rate_bps < policy.degraded_success_rate_bps:
        degraded_reasons.append("provider_health_success_rate_degraded")
    if p95_latency_ms >= policy.degraded_p95_latency_ms:
        degraded_reasons.append("provider_health_latency_degraded")
    if degraded_reasons:
        return metrics, "degraded", degraded_reasons
    return metrics, "healthy", ["provider_health_healthy"]


def _aggregation_key(
    *,
    scope_key: str,
    window_started_at: datetime,
    window_ended_at: datetime,
    policy_snapshot: dict[str, int],
    observation_manifest: Sequence[dict[str, Any]],
    evidence_refs: Sequence[str],
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "provider_health_aggregation.v1",
                "scope_key": scope_key,
                "window_started_at": _timestamp(window_started_at),
                "window_ended_at": _timestamp(window_ended_at),
                "policy_snapshot": policy_snapshot,
                "observation_manifest": list(observation_manifest),
                "evidence_refs": sorted(evidence_refs),
            },
        )
    )


def _snapshot_digest(
    *,
    aggregation_key: str,
    snapshot_version: int,
    status: str,
    metrics: dict[str, int],
    reason_codes: Sequence[str],
    evaluated_at: datetime,
    routing_valid_until: datetime,
    evidence_retain_until: datetime,
    previous_snapshot_digest: str | None,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "provider_health_snapshot.v1",
                "aggregation_key": aggregation_key,
                "snapshot_version": snapshot_version,
                "status": status,
                "metrics": metrics,
                "reason_codes": list(reason_codes),
                "evaluated_at": _timestamp(evaluated_at),
                "routing_valid_until": _timestamp(routing_valid_until),
                "evidence_retain_until": _timestamp(evidence_retain_until),
                "previous_snapshot_digest": previous_snapshot_digest,
                "health_probe_attempted": False,
                "provider_call_attempted": False,
            },
        )
    )


def _snapshot_metrics_from_model(snapshot: ProviderHealthSnapshot) -> dict[str, int]:
    return {
        "sample_count": snapshot.sample_count,
        "success_count": snapshot.success_count,
        "timeout_count": snapshot.timeout_count,
        "rate_limited_count": snapshot.rate_limited_count,
        "transient_error_count": snapshot.transient_error_count,
        "terminal_error_count": snapshot.terminal_error_count,
        "success_rate_bps": snapshot.success_rate_bps,
        "p95_latency_ms": snapshot.p95_latency_ms,
    }


def _validate_snapshot_chain(
    snapshots: Sequence[ProviderHealthSnapshot],
) -> tuple[ProviderHealthSnapshot, ...]:
    frozen = tuple(snapshots)
    previous_digest: str | None = None
    for expected_version, snapshot in enumerate(frozen, start=1):
        policy = ProviderHealthAggregationPolicy.model_validate(snapshot.policy_snapshot)
        metrics, status, reason_codes = _snapshot_metrics(
            snapshot.observation_manifest,
            policy,
        )
        expected_aggregation_key = _aggregation_key(
            scope_key=snapshot.scope_key,
            window_started_at=snapshot.window_started_at,
            window_ended_at=snapshot.window_ended_at,
            policy_snapshot=snapshot.policy_snapshot,
            observation_manifest=snapshot.observation_manifest,
            evidence_refs=snapshot.evidence_refs,
        )
        expected_digest = _snapshot_digest(
            aggregation_key=expected_aggregation_key,
            snapshot_version=expected_version,
            status=status,
            metrics=metrics,
            reason_codes=reason_codes,
            evaluated_at=snapshot.evaluated_at,
            routing_valid_until=snapshot.routing_valid_until,
            evidence_retain_until=snapshot.evidence_retain_until,
            previous_snapshot_digest=previous_digest,
        )
        if (
            snapshot.contract_version != "provider_health_snapshot.v1"
            or snapshot.snapshot_version != expected_version
            or snapshot.previous_snapshot_digest != previous_digest
            or snapshot.aggregation_key != expected_aggregation_key
            or snapshot.status != status
            or snapshot.reason_codes != reason_codes
            or _snapshot_metrics_from_model(snapshot) != metrics
            or snapshot.snapshot_digest != expected_digest
            or snapshot.health_probe_attempted
            or snapshot.provider_call_attempted
            or snapshot.credential_read_attempted
            or snapshot.actor_run
            or snapshot.browser_run
            or snapshot.llm_call
            or snapshot.raw_record_write
            or snapshot.dataset_write
            or snapshot.production_write_allowed
        ):
            raise ProviderHealthContractError("provider_health_snapshot_chain_invalid")
        previous_digest = snapshot.snapshot_digest
    return frozen


def _snapshot_response(snapshot: ProviderHealthSnapshot) -> ProviderHealthSnapshotResponse:
    return ProviderHealthSnapshotResponse.model_validate(snapshot)


async def record_provider_health_snapshot(
    session: AsyncSession,
    *,
    request: ProviderHealthSnapshotRequest,
    policy: ProviderHealthAggregationPolicy,
    clock: ProviderHealthClock | None = None,
) -> ProviderHealthSnapshotResult:
    await _prepare_session(session)
    evaluated_at = _utc((clock or (lambda: datetime.now(UTC)))())
    if _utc(request.window_ended_at) > evaluated_at:
        raise ProviderHealthContractError("provider_health_future_window_forbidden")
    scope_key = _scope_key(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        platform_id=request.platform_id,
        implementation_id=request.implementation_id,
        resource_type=request.resource_type,
        operation=request.operation,
    )
    observation_manifest = _observation_manifest(request.observations)
    evidence_refs = sorted(
        set(request.evidence_refs).union(
            *(observation.evidence_refs for observation in request.observations)
        )
    )
    policy_snapshot = _policy_snapshot(policy)
    aggregation_key = _aggregation_key(
        scope_key=scope_key,
        window_started_at=request.window_started_at,
        window_ended_at=request.window_ended_at,
        policy_snapshot=policy_snapshot,
        observation_manifest=observation_manifest,
        evidence_refs=evidence_refs,
    )
    metrics, status, reason_codes = _snapshot_metrics(observation_manifest, policy)

    try:
        async with session.begin():
            existing = await get_provider_health_snapshot_by_aggregation_key(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                aggregation_key=aggregation_key,
            )
            snapshots = _validate_snapshot_chain(
                await list_provider_health_snapshots_for_scope(
                    session,
                    workspace_id=request.workspace_id,
                    project_id=request.project_id,
                    scope_key=scope_key,
                    for_update=True,
                )
            )
            if existing is not None:
                if existing not in snapshots:
                    raise ProviderHealthContractError("provider_health_snapshot_scope_conflict")
                return ProviderHealthSnapshotResult(
                    snapshot=_snapshot_response(existing),
                    snapshot_written=False,
                    snapshot_replay=True,
                )
            previous = snapshots[-1] if snapshots else None
            snapshot_version = len(snapshots) + 1
            routing_valid_until = evaluated_at + timedelta(hours=policy.routing_ttl_hours)
            evidence_retain_until = evaluated_at + timedelta(days=policy.evidence_retention_days)
            previous_digest = previous.snapshot_digest if previous is not None else None
            snapshot = ProviderHealthSnapshot(
                id=uuid.uuid4(),
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                contract_version="provider_health_snapshot.v1",
                scope_key=scope_key,
                aggregation_key=aggregation_key,
                snapshot_version=snapshot_version,
                platform_id=request.platform_id,
                implementation_id=request.implementation_id,
                resource_type=request.resource_type,
                operation=request.operation,
                window_started_at=_utc(request.window_started_at),
                window_ended_at=_utc(request.window_ended_at),
                evaluated_at=evaluated_at,
                status=status,
                reason_codes=reason_codes,
                policy_snapshot=policy_snapshot,
                observation_manifest=observation_manifest,
                evidence_refs=evidence_refs,
                previous_snapshot_digest=previous_digest,
                snapshot_digest=_snapshot_digest(
                    aggregation_key=aggregation_key,
                    snapshot_version=snapshot_version,
                    status=status,
                    metrics=metrics,
                    reason_codes=reason_codes,
                    evaluated_at=evaluated_at,
                    routing_valid_until=routing_valid_until,
                    evidence_retain_until=evidence_retain_until,
                    previous_snapshot_digest=previous_digest,
                ),
                routing_valid_until=routing_valid_until,
                evidence_retain_until=evidence_retain_until,
                health_probe_attempted=False,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                raw_record_write=False,
                dataset_write=False,
                production_write_allowed=False,
                **metrics,
            )
            await add_provider_health_snapshot(session, snapshot)
            return ProviderHealthSnapshotResult(
                snapshot=_snapshot_response(snapshot),
                snapshot_written=True,
                snapshot_replay=False,
            )
    except IntegrityError as conflict:
        await session.rollback()
        async with session.begin():
            raced = await get_provider_health_snapshot_by_aggregation_key(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                aggregation_key=aggregation_key,
            )
            snapshots = await list_provider_health_snapshots_for_scope(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                scope_key=scope_key,
            )
        _validate_snapshot_chain(snapshots)
        if raced is None:
            raise conflict
        return ProviderHealthSnapshotResult(
            snapshot=_snapshot_response(raced),
            snapshot_written=False,
            snapshot_replay=True,
        )


def _feedback_key(
    *,
    route_key: str,
    platform_id: str,
    resource_type: str,
    operation: str,
    original_candidate_order: Sequence[str],
    adjusted_candidate_order: Sequence[str],
    candidate_score_manifest: Sequence[dict[str, Any]],
    source_snapshot_manifest: Sequence[dict[str, Any]],
    reason_codes: Sequence[str],
    evidence_refs: Sequence[str],
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "provider_health_route_feedback_input.v1",
                "route_key": route_key,
                "platform_id": platform_id,
                "resource_type": resource_type,
                "operation": operation,
                "original_candidate_order": list(original_candidate_order),
                "adjusted_candidate_order": list(adjusted_candidate_order),
                "candidate_score_manifest": list(candidate_score_manifest),
                "source_snapshot_manifest": list(source_snapshot_manifest),
                "reason_codes": list(reason_codes),
                "evidence_refs": sorted(evidence_refs),
            },
        )
    )


def _feedback_digest(
    *,
    feedback_key: str,
    feedback_version: int,
    ranking_changed: bool,
    evaluated_at: datetime,
    evidence_retain_until: datetime,
    previous_feedback_digest: str | None,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "provider_health_route_feedback.v1",
                "feedback_key": feedback_key,
                "feedback_version": feedback_version,
                "ranking_changed": ranking_changed,
                "evaluated_at": _timestamp(evaluated_at),
                "evidence_retain_until": _timestamp(evidence_retain_until),
                "previous_feedback_digest": previous_feedback_digest,
                "health_probe_attempted": False,
                "catalog_mutation_applied": False,
                "automatic_route_switch_executed": False,
            },
        )
    )


def _validate_feedback_chain(
    feedbacks: Sequence[ProviderHealthRouteFeedback],
) -> tuple[ProviderHealthRouteFeedback, ...]:
    frozen = tuple(feedbacks)
    previous_digest: str | None = None
    for expected_version, feedback in enumerate(frozen, start=1):
        expected_key = _feedback_key(
            route_key=feedback.route_key,
            platform_id=feedback.platform_id,
            resource_type=feedback.resource_type,
            operation=feedback.operation,
            original_candidate_order=feedback.original_candidate_order,
            adjusted_candidate_order=feedback.adjusted_candidate_order,
            candidate_score_manifest=feedback.candidate_score_manifest,
            source_snapshot_manifest=feedback.source_snapshot_manifest,
            reason_codes=feedback.reason_codes,
            evidence_refs=feedback.evidence_refs,
        )
        expected_digest = _feedback_digest(
            feedback_key=expected_key,
            feedback_version=expected_version,
            ranking_changed=feedback.ranking_changed,
            evaluated_at=feedback.evaluated_at,
            evidence_retain_until=feedback.evidence_retain_until,
            previous_feedback_digest=previous_digest,
        )
        if (
            feedback.contract_version != "provider_health_route_feedback.v1"
            or feedback.feedback_version != expected_version
            or feedback.previous_feedback_digest != previous_digest
            or feedback.feedback_key != expected_key
            or feedback.feedback_digest != expected_digest
            or feedback.ranking_changed
            != (feedback.original_candidate_order != feedback.adjusted_candidate_order)
            or feedback.health_probe_attempted
            or feedback.catalog_mutation_applied
            or feedback.automatic_route_switch_executed
            or feedback.provider_call_attempted
            or feedback.credential_read_attempted
            or feedback.actor_run
            or feedback.browser_run
            or feedback.llm_call
            or feedback.raw_record_write
            or feedback.dataset_write
            or feedback.production_write_allowed
        ):
            raise ProviderHealthContractError("provider_health_feedback_chain_invalid")
        previous_digest = feedback.feedback_digest
    return frozen


def _latest_snapshots_by_implementation(
    snapshots: Sequence[ProviderHealthSnapshot],
) -> dict[str, ProviderHealthSnapshot]:
    grouped: dict[str, list[ProviderHealthSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[snapshot.implementation_id].append(snapshot)
    latest: dict[str, ProviderHealthSnapshot] = {}
    for implementation_id, items in grouped.items():
        validated = _validate_snapshot_chain(items)
        latest[implementation_id] = validated[-1]
    return latest


def _routing_manifests(
    request: ProviderHealthRouteFeedbackRequest,
    policy: ProviderHealthRoutingPolicy,
    snapshots: dict[str, ProviderHealthSnapshot],
    *,
    evaluated_at: datetime,
) -> tuple[
    list[str],
    list[dict[str, JsonValue]],
    list[dict[str, JsonValue]],
    list[str],
    list[str],
    datetime,
]:
    original_order = [item.implementation_id for item in request.candidates]
    source_manifest: list[dict[str, JsonValue]] = []
    score_manifest: list[dict[str, JsonValue]] = []
    reason_codes: list[str] = []
    evidence_refs = set(request.evidence_refs)
    evidence_retain_until = evaluated_at + timedelta(days=policy.feedback_retention_days)
    for original_index, candidate in enumerate(request.candidates):
        evidence_refs.update(candidate.evidence_refs)
        snapshot = snapshots.get(candidate.implementation_id)
        penalty_bps = 0
        health_status = "unknown"
        snapshot_digest: str | None = None
        routing_applied = False
        routing_valid_until: str | None = None
        snapshot_evidence: list[str] = []
        if snapshot is None:
            reason_codes.append(f"provider_health_snapshot_missing:{candidate.implementation_id}")
        else:
            snapshot_digest = snapshot.snapshot_digest
            health_status = snapshot.status
            snapshot_evidence = list(snapshot.evidence_refs)
            evidence_refs.update(snapshot_evidence)
            evidence_retain_until = max(
                evidence_retain_until,
                _utc(snapshot.evidence_retain_until),
            )
            routing_valid_until = _timestamp(snapshot.routing_valid_until)
            if evaluated_at >= _utc(snapshot.routing_valid_until):
                reason_codes.append(
                    f"provider_health_snapshot_expired:{candidate.implementation_id}"
                )
            else:
                routing_applied = True
                if snapshot.status == "degraded":
                    penalty_bps = policy.degraded_penalty_bps
                    reason_codes.append(f"provider_health_degraded:{candidate.implementation_id}")
                elif snapshot.status == "unhealthy":
                    penalty_bps = policy.unhealthy_penalty_bps
                    reason_codes.append(f"provider_health_unhealthy:{candidate.implementation_id}")
                elif snapshot.status == "unknown":
                    reason_codes.append(f"provider_health_unknown:{candidate.implementation_id}")
                else:
                    reason_codes.append(f"provider_health_healthy:{candidate.implementation_id}")
        adjusted_score = max(0, candidate.baseline_score_bps - penalty_bps)
        source_manifest.append(
            {
                "implementation_id": candidate.implementation_id,
                "snapshot_digest": snapshot_digest,
                "health_status": health_status,
                "routing_applied": routing_applied,
                "routing_valid_until": routing_valid_until,
                "evidence_refs": cast(JsonValue, snapshot_evidence),
            }
        )
        score_manifest.append(
            {
                "implementation_id": candidate.implementation_id,
                "original_index": original_index,
                "baseline_score_bps": candidate.baseline_score_bps,
                "health_penalty_bps": penalty_bps,
                "adjusted_score_bps": adjusted_score,
                "snapshot_digest": snapshot_digest,
            }
        )
    adjusted_order = [
        cast(str, item["implementation_id"])
        for item in sorted(
            score_manifest,
            key=lambda item: (
                -cast(int, item["adjusted_score_bps"]),
                cast(int, item["original_index"]),
            ),
        )
    ]
    reason_codes.append(
        "provider_health_ranking_reordered"
        if original_order != adjusted_order
        else "provider_health_ranking_unchanged"
    )
    return (
        original_order,
        score_manifest,
        source_manifest,
        adjusted_order,
        sorted(set(reason_codes)),
        evidence_retain_until,
    )


def _feedback_response(
    feedback: ProviderHealthRouteFeedback,
) -> ProviderHealthRouteFeedbackResponse:
    return ProviderHealthRouteFeedbackResponse.model_validate(feedback)


async def compile_provider_health_route_feedback(
    session: AsyncSession,
    *,
    request: ProviderHealthRouteFeedbackRequest,
    policy: ProviderHealthRoutingPolicy,
    clock: ProviderHealthClock | None = None,
) -> ProviderHealthRouteFeedbackResult:
    await _prepare_session(session)
    evaluated_at = _utc((clock or (lambda: datetime.now(UTC)))())
    async with session.begin():
        candidate_snapshots = await list_provider_health_snapshots_for_candidates(
            session,
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            platform_id=request.platform_id,
            resource_type=request.resource_type,
            operation=request.operation,
            implementation_ids=[item.implementation_id for item in request.candidates],
        )
    latest_snapshots = _latest_snapshots_by_implementation(candidate_snapshots)
    (
        original_order,
        score_manifest,
        source_manifest,
        adjusted_order,
        reason_codes,
        evidence_retain_until,
    ) = _routing_manifests(
        request,
        policy,
        latest_snapshots,
        evaluated_at=evaluated_at,
    )
    evidence_refs = sorted(
        set(request.evidence_refs).union(
            *(candidate.evidence_refs for candidate in request.candidates),
            *(snapshot.evidence_refs for snapshot in latest_snapshots.values()),
        )
    )
    feedback_key = _feedback_key(
        route_key=request.route_key,
        platform_id=request.platform_id,
        resource_type=request.resource_type,
        operation=request.operation,
        original_candidate_order=original_order,
        adjusted_candidate_order=adjusted_order,
        candidate_score_manifest=score_manifest,
        source_snapshot_manifest=source_manifest,
        reason_codes=reason_codes,
        evidence_refs=evidence_refs,
    )
    try:
        async with session.begin():
            existing = await get_provider_health_feedback_by_key(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                feedback_key=feedback_key,
            )
            feedbacks = _validate_feedback_chain(
                await list_provider_health_feedbacks_for_route(
                    session,
                    workspace_id=request.workspace_id,
                    project_id=request.project_id,
                    route_key=request.route_key,
                    for_update=True,
                )
            )
            if existing is not None:
                if existing not in feedbacks:
                    raise ProviderHealthContractError("provider_health_feedback_route_conflict")
                return ProviderHealthRouteFeedbackResult(
                    feedback=_feedback_response(existing),
                    feedback_written=False,
                    feedback_replay=True,
                )
            previous = feedbacks[-1] if feedbacks else None
            feedback_version = len(feedbacks) + 1
            previous_digest = previous.feedback_digest if previous is not None else None
            ranking_changed = original_order != adjusted_order
            feedback = ProviderHealthRouteFeedback(
                id=uuid.uuid4(),
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                contract_version="provider_health_route_feedback.v1",
                route_key=request.route_key,
                feedback_key=feedback_key,
                feedback_version=feedback_version,
                platform_id=request.platform_id,
                resource_type=request.resource_type,
                operation=request.operation,
                original_candidate_order=original_order,
                adjusted_candidate_order=adjusted_order,
                candidate_score_manifest=score_manifest,
                source_snapshot_manifest=source_manifest,
                ranking_changed=ranking_changed,
                reason_codes=reason_codes,
                evidence_refs=evidence_refs,
                previous_feedback_digest=previous_digest,
                feedback_digest=_feedback_digest(
                    feedback_key=feedback_key,
                    feedback_version=feedback_version,
                    ranking_changed=ranking_changed,
                    evaluated_at=evaluated_at,
                    evidence_retain_until=evidence_retain_until,
                    previous_feedback_digest=previous_digest,
                ),
                evaluated_at=evaluated_at,
                evidence_retain_until=evidence_retain_until,
                health_probe_attempted=False,
                catalog_mutation_applied=False,
                automatic_route_switch_executed=False,
                provider_call_attempted=False,
                credential_read_attempted=False,
                actor_run=False,
                browser_run=False,
                llm_call=False,
                raw_record_write=False,
                dataset_write=False,
                production_write_allowed=False,
            )
            await add_provider_health_feedback(session, feedback)
            return ProviderHealthRouteFeedbackResult(
                feedback=_feedback_response(feedback),
                feedback_written=True,
                feedback_replay=False,
            )
    except IntegrityError as conflict:
        await session.rollback()
        async with session.begin():
            raced = await get_provider_health_feedback_by_key(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                feedback_key=feedback_key,
            )
            feedbacks = await list_provider_health_feedbacks_for_route(
                session,
                workspace_id=request.workspace_id,
                project_id=request.project_id,
                route_key=request.route_key,
            )
        _validate_feedback_chain(feedbacks)
        if raced is None:
            raise conflict
        return ProviderHealthRouteFeedbackResult(
            feedback=_feedback_response(raced),
            feedback_written=False,
            feedback_replay=True,
        )


__all__ = [
    "ProviderHealthClock",
    "ProviderHealthContractError",
    "ProviderHealthTransactionStateError",
    "compile_provider_health_route_feedback",
    "record_provider_health_snapshot",
]
