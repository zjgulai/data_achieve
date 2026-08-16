from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.provider_health import (
    ProviderHealthRouteFeedback,
    ProviderHealthSnapshot,
)
from data_intelligence_hub.schemas.provider_health import (
    ProviderHealthAggregationPolicy,
    ProviderHealthObservation,
    ProviderHealthRouteCandidate,
    ProviderHealthRouteFeedbackRequest,
    ProviderHealthRoutingPolicy,
    ProviderHealthSnapshotRequest,
)
from data_intelligence_hub.services.workflow_execution.health import (
    ProviderHealthContractError,
    compile_provider_health_route_feedback,
    record_provider_health_snapshot,
)

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
PROJECT_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
DIGEST_C = "sha256:" + "c" * 64


@pytest_asyncio.fixture()
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _observations(
    implementation_id: str,
    outcomes: Sequence[str],
    latencies: Sequence[int],
    *,
    start: datetime = NOW - timedelta(hours=2),
) -> list[ProviderHealthObservation]:
    assert len(outcomes) == len(latencies)
    return [
        ProviderHealthObservation(
            observation_id=f"{implementation_id}-observation-{index}",
            observed_at=start + timedelta(minutes=index + 1),
            outcome=outcome,
            latency_ms=latency,
            evidence_refs=[f"fixture://health/{implementation_id}/{index}"],
        )
        for index, (outcome, latency) in enumerate(zip(outcomes, latencies, strict=True))
    ]


def _snapshot_request(
    implementation_id: str,
    outcomes: Sequence[str],
    latencies: Sequence[int],
    *,
    window_started_at: datetime = NOW - timedelta(hours=2),
    window_ended_at: datetime = NOW - timedelta(hours=1),
) -> ProviderHealthSnapshotRequest:
    return ProviderHealthSnapshotRequest(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        platform_id="youtube",
        implementation_id=implementation_id,
        resource_type="video",
        operation="search_discover",
        window_started_at=window_started_at,
        window_ended_at=window_ended_at,
        observations=_observations(
            implementation_id,
            outcomes,
            latencies,
            start=window_started_at,
        ),
        evidence_refs=[f"fixture://health/{implementation_id}/window"],
    )


def _feedback_request() -> ProviderHealthRouteFeedbackRequest:
    return ProviderHealthRouteFeedbackRequest(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        route_key="route://youtube/video/search",
        platform_id="youtube",
        resource_type="video",
        operation="search_discover",
        candidates=[
            ProviderHealthRouteCandidate(
                implementation_id="provider-primary",
                baseline_score_bps=9_000,
                evidence_refs=["catalog://provider-primary"],
            ),
            ProviderHealthRouteCandidate(
                implementation_id="provider-fallback",
                baseline_score_bps=8_500,
                evidence_refs=["catalog://provider-fallback"],
            ),
        ],
        evidence_refs=["route-plan://youtube/video/search"],
    )


@pytest.mark.asyncio
async def test_snapshot_aggregates_metrics_retains_observation_basis_and_replays(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    request = _snapshot_request(
        "provider-primary",
        ["succeeded", "timeout", "rate_limited", "transient_error", "terminal_error"],
        [100, 200, 300, 400, 500],
    )
    async with sessions() as first_session:
        first = await record_provider_health_snapshot(
            first_session,
            request=request,
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )
    assert first.snapshot_written and not first.snapshot_replay
    assert first.snapshot.status == "unhealthy"
    assert first.snapshot.sample_count == 5
    assert first.snapshot.success_count == 1
    assert first.snapshot.timeout_count == 1
    assert first.snapshot.rate_limited_count == 1
    assert first.snapshot.transient_error_count == 1
    assert first.snapshot.terminal_error_count == 1
    assert first.snapshot.success_rate_bps == 2_000
    assert first.snapshot.p95_latency_ms == 500
    assert len(first.snapshot.observation_manifest) == 5
    assert all("observation_digest" in item for item in first.snapshot.observation_manifest)
    assert first.snapshot.routing_valid_until == NOW + timedelta(hours=24)
    assert first.snapshot.evidence_retain_until == NOW + timedelta(days=90)
    assert not first.snapshot.health_probe_attempted
    assert not first.snapshot.provider_call_attempted

    async with sessions() as replay_session:
        replay = await record_provider_health_snapshot(
            replay_session,
            request=request,
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW + timedelta(minutes=5),
        )
    assert replay.snapshot_replay and not replay.snapshot_written
    assert replay.snapshot.id == first.snapshot.id
    async with sessions() as count_session:
        count = await count_session.scalar(select(func.count(ProviderHealthSnapshot.id)))
    assert count == 1


@pytest.mark.parametrize(
    ("outcomes", "latencies", "policy", "expected_status", "expected_reason"),
    [
        (
            ["succeeded"],
            [100],
            ProviderHealthAggregationPolicy(min_sample_size=2),
            "unknown",
            "provider_health_insufficient_samples",
        ),
        (
            ["succeeded", "succeeded", "succeeded"],
            [100, 200, 300],
            ProviderHealthAggregationPolicy(),
            "healthy",
            "provider_health_healthy",
        ),
        (
            ["succeeded", "succeeded", "succeeded"],
            [2_500, 2_500, 2_500],
            ProviderHealthAggregationPolicy(),
            "degraded",
            "provider_health_latency_degraded",
        ),
        (
            ["succeeded", "succeeded", "succeeded"],
            [6_000, 6_000, 6_000],
            ProviderHealthAggregationPolicy(),
            "unhealthy",
            "provider_health_latency_unhealthy",
        ),
    ],
)
@pytest.mark.asyncio
async def test_snapshot_status_thresholds_are_deterministic(
    sessions: async_sessionmaker[AsyncSession],
    outcomes: list[str],
    latencies: list[int],
    policy: ProviderHealthAggregationPolicy,
    expected_status: str,
    expected_reason: str,
) -> None:
    async with sessions() as session:
        result = await record_provider_health_snapshot(
            session,
            request=_snapshot_request("provider-primary", outcomes, latencies),
            policy=policy,
            clock=lambda: NOW,
        )
    assert result.snapshot.status == expected_status
    assert expected_reason in result.snapshot.reason_codes


@pytest.mark.asyncio
async def test_health_feedback_reorders_candidates_and_versions_original_basis(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as snapshot_session:
        unhealthy = await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-primary",
                ["succeeded", "succeeded", "succeeded"],
                [6_000, 6_000, 6_000],
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )
        healthy = await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-fallback",
                ["succeeded", "succeeded", "succeeded"],
                [100, 100, 100],
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )

    async with sessions() as feedback_session:
        feedback = await compile_provider_health_route_feedback(
            feedback_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW + timedelta(minutes=30),
        )
    assert feedback.feedback_written and not feedback.feedback_replay
    assert feedback.feedback.feedback_version == 1
    assert feedback.feedback.original_candidate_order == [
        "provider-primary",
        "provider-fallback",
    ]
    assert feedback.feedback.adjusted_candidate_order == [
        "provider-fallback",
        "provider-primary",
    ]
    assert feedback.feedback.ranking_changed
    assert "provider_health_unhealthy:provider-primary" in feedback.feedback.reason_codes
    assert "provider_health_ranking_reordered" in feedback.feedback.reason_codes
    source_digests = {
        item["snapshot_digest"] for item in feedback.feedback.source_snapshot_manifest
    }
    assert source_digests == {
        unhealthy.snapshot.snapshot_digest,
        healthy.snapshot.snapshot_digest,
    }
    assert set(feedback.feedback.evidence_refs) >= {
        "fixture://health/provider-primary/window",
        "fixture://health/provider-fallback/window",
        "route-plan://youtube/video/search",
    }
    assert not feedback.feedback.catalog_mutation_applied
    assert not feedback.feedback.automatic_route_switch_executed

    async with sessions() as replay_session:
        replay = await compile_provider_health_route_feedback(
            replay_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW + timedelta(minutes=35),
        )
    assert replay.feedback_replay and not replay.feedback_written
    assert replay.feedback.id == feedback.feedback.id


@pytest.mark.asyncio
async def test_new_snapshot_creates_chained_feedback_version(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as snapshot_session:
        await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-primary",
                ["succeeded", "succeeded", "succeeded"],
                [6_000, 6_000, 6_000],
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )
        await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-fallback",
                ["succeeded", "succeeded", "succeeded"],
                [100, 100, 100],
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )
    async with sessions() as first_feedback_session:
        first = await compile_provider_health_route_feedback(
            first_feedback_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW + timedelta(minutes=30),
        )

    second_window_start = NOW
    second_window_end = NOW + timedelta(minutes=30)
    async with sessions() as recovery_session:
        recovered = await record_provider_health_snapshot(
            recovery_session,
            request=_snapshot_request(
                "provider-primary",
                ["succeeded", "succeeded", "succeeded"],
                [100, 100, 100],
                window_started_at=second_window_start,
                window_ended_at=second_window_end,
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW + timedelta(hours=1),
        )
    assert recovered.snapshot.snapshot_version == 2

    async with sessions() as second_feedback_session:
        second = await compile_provider_health_route_feedback(
            second_feedback_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW + timedelta(hours=1, minutes=30),
        )
    assert second.feedback.feedback_version == 2
    assert second.feedback.previous_feedback_digest == first.feedback.feedback_digest
    assert second.feedback.adjusted_candidate_order == [
        "provider-primary",
        "provider-fallback",
    ]
    assert not second.feedback.ranking_changed
    assert "provider_health_ranking_unchanged" in second.feedback.reason_codes


@pytest.mark.asyncio
async def test_expired_snapshot_stops_affecting_ranking_but_retains_evidence(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as snapshot_session:
        snapshot = await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-primary",
                ["succeeded", "succeeded", "succeeded"],
                [6_000, 6_000, 6_000],
            ),
            policy=ProviderHealthAggregationPolicy(
                routing_ttl_hours=1,
                evidence_retention_days=30,
            ),
            clock=lambda: NOW,
        )

    async with sessions() as feedback_session:
        feedback = await compile_provider_health_route_feedback(
            feedback_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW + timedelta(hours=2),
        )
    assert feedback.feedback.adjusted_candidate_order == feedback.feedback.original_candidate_order
    assert "provider_health_snapshot_expired:provider-primary" in feedback.feedback.reason_codes
    primary_source = feedback.feedback.source_snapshot_manifest[0]
    assert primary_source["snapshot_digest"] == snapshot.snapshot.snapshot_digest
    assert primary_source["routing_applied"] is False
    assert primary_source["evidence_refs"]
    async with sessions() as persisted_session:
        persisted = await persisted_session.scalar(
            select(ProviderHealthSnapshot).where(ProviderHealthSnapshot.id == snapshot.snapshot.id)
        )
    assert persisted is not None
    assert persisted.snapshot_digest == snapshot.snapshot.snapshot_digest


@pytest.mark.asyncio
async def test_snapshot_tampering_fails_closed_before_route_feedback(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as snapshot_session:
        await record_provider_health_snapshot(
            snapshot_session,
            request=_snapshot_request(
                "provider-primary",
                ["succeeded", "succeeded", "succeeded"],
                [100, 100, 100],
            ),
            policy=ProviderHealthAggregationPolicy(),
            clock=lambda: NOW,
        )
    async with sessions() as mutation_session, mutation_session.begin():
        await mutation_session.execute(
            update(ProviderHealthSnapshot).values(snapshot_digest=DIGEST_C)
        )
    async with sessions() as feedback_session:
        with pytest.raises(
            ProviderHealthContractError,
            match="provider_health_snapshot_chain_invalid",
        ):
            await compile_provider_health_route_feedback(
                feedback_session,
                request=_feedback_request(),
                policy=ProviderHealthRoutingPolicy(),
                clock=lambda: NOW + timedelta(minutes=30),
            )


def test_health_contract_rejects_invalid_retention_and_duplicate_candidates() -> None:
    with pytest.raises(ValidationError, match="provider_health_retention_window_invalid"):
        ProviderHealthAggregationPolicy(
            routing_ttl_hours=24,
            evidence_retention_days=1,
        )
    request = _feedback_request().model_dump(mode="python")
    request["candidates"] = [request["candidates"][0], request["candidates"][0]]
    with pytest.raises(ValidationError, match="provider_health_route_candidate_duplicate"):
        ProviderHealthRouteFeedbackRequest.model_validate(request)


@pytest.mark.asyncio
async def test_feedback_rows_remain_append_only(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as feedback_session:
        result = await compile_provider_health_route_feedback(
            feedback_session,
            request=_feedback_request(),
            policy=ProviderHealthRoutingPolicy(),
            clock=lambda: NOW,
        )
    assert result.feedback.feedback_version == 1
    async with sessions() as count_session:
        count = await count_session.scalar(select(func.count(ProviderHealthRouteFeedback.id)))
    assert count == 1
