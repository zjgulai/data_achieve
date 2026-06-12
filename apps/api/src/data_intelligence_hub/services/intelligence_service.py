from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.intelligence import (
    IntelligenceFeedback,
    IntelligenceItem,
)
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.entities import get_entity, get_entity_snapshot
from data_intelligence_hub.repositories.intelligence import (
    EvidenceWithAsset,
    count_evidences,
    count_evidences_for_items,
    create_feedback,
    get_intelligence_item,
    get_intelligence_item_for_signal,
    list_evidences_with_assets,
    list_intelligence_items,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.raw_records import get_raw_record
from data_intelligence_hub.repositories.signals import list_signals
from data_intelligence_hub.services.evidence_service import build_evidences_for_signal
from data_intelligence_hub.services.exceptions import IntelligenceNotFoundError
from data_intelligence_hub.services.llm_service import LLMService


class IntelligenceWithCount(NamedTuple):
    item: IntelligenceItem
    evidence_count: int


class IntelligenceScores(NamedTuple):
    impact_score: float
    confidence_score: float
    novelty_score: float
    urgency_score: float
    final_score: float


async def get_intelligence_items(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    intelligence_type: str | None,
    status: str | None,
    domain: str | None,
    sort: str | None,
) -> list[IntelligenceWithCount]:
    items = await list_intelligence_items(
        session,
        workspace.id,
        project_id=project_id,
        intelligence_type=intelligence_type,
        status=status,
        domain=domain,
        sort=sort,
    )
    counts = await count_evidences_for_items(session, [item.id for item in items])
    return [
        IntelligenceWithCount(item=item, evidence_count=counts.get(item.id, 0))
        for item in items
    ]


async def get_intelligence_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    intelligence_id: uuid.UUID,
) -> IntelligenceWithCount:
    item = await get_intelligence_item(session, workspace.id, intelligence_id)
    if item is None:
        raise IntelligenceNotFoundError
    evidence_count = await count_evidences(session, item.id)
    return IntelligenceWithCount(item=item, evidence_count=evidence_count)


async def get_evidences_for_intelligence(
    session: AsyncSession,
    workspace: Workspace,
    intelligence_id: uuid.UUID,
) -> list[EvidenceWithAsset]:
    await get_intelligence_or_raise(session, workspace, intelligence_id)
    return await list_evidences_with_assets(session, intelligence_id)


async def update_intelligence_status(
    session: AsyncSession,
    workspace: Workspace,
    intelligence_id: uuid.UUID,
    status: str,
) -> IntelligenceWithCount:
    result = await get_intelligence_or_raise(session, workspace, intelligence_id)
    result.item.status = status
    await session.commit()
    await session.refresh(result.item)
    evidence_count = await count_evidences(session, result.item.id)
    return IntelligenceWithCount(item=result.item, evidence_count=evidence_count)


async def submit_intelligence_feedback(
    session: AsyncSession,
    workspace: Workspace,
    intelligence_id: uuid.UUID,
    user_id: uuid.UUID,
    feedback_type: str,
    comment: str | None,
) -> IntelligenceFeedback:
    await get_intelligence_or_raise(session, workspace, intelligence_id)
    feedback = await create_feedback(
        session,
        intelligence_id=intelligence_id,
        user_id=user_id,
        feedback_type=feedback_type,
        comment=comment,
    )
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def generate_intelligence_for_signal(
    session: AsyncSession,
    workspace: Workspace,
    signal: Signal,
    llm_service: LLMService | None = None,
) -> IntelligenceItem | None:
    existing = await get_intelligence_item_for_signal(session, workspace.id, signal.id)
    if existing is not None:
        return None

    entity = await get_entity(session, workspace.id, signal.entity_id)
    project = await get_project(session, workspace.id, signal.project_id)
    if entity is None or project is None:
        return None

    current_snapshot = await get_entity_snapshot(session, signal.current_snapshot_id)
    raw_record = None
    if current_snapshot is not None:
        raw_record = await get_raw_record(session, workspace.id, current_snapshot.raw_record_id)

    recent_signals = await list_signals(session, workspace.id, project_id=signal.project_id)
    intelligence_type = _intelligence_type(signal)
    scores = _score_signal(signal, recent_signals)
    item = IntelligenceItem(
        workspace_id=workspace.id,
        project_id=signal.project_id,
        title="Pending intelligence summary",
        summary="Pending intelligence summary.",
        intelligence_type=intelligence_type,
        status="new",
        impact_score=scores.impact_score,
        confidence_score=scores.confidence_score,
        novelty_score=scores.novelty_score,
        urgency_score=scores.urgency_score,
        final_score=scores.final_score,
        generated_by="hybrid",
        domain=project.domain,
    )
    session.add(item)
    await session.flush()

    evidences = build_evidences_for_signal(
        intelligence_id=item.id,
        signal=signal,
        entity=entity,
        current_snapshot=current_snapshot,
        raw_record=raw_record,
    )
    for evidence in evidences:
        session.add(evidence)
    await session.flush()

    llm = llm_service or LLMService()
    copy = await llm.summarize_intelligence(
        {
            "entity_name": entity.name,
            "signal_type": signal.signal_type,
            "intelligence_type": intelligence_type,
            "severity": signal.severity,
            "delta": signal.delta,
            "delta_ratio": signal.delta_ratio,
            "metric": signal.metadata_json.get("metric"),
            "final_score": scores.final_score,
            "evidence_count": len(evidences),
        }
    )
    item.title = copy.title
    item.summary = copy.summary
    await session.flush()
    return item


def _intelligence_type(signal: Signal) -> str:
    if signal.signal_type == "data_quality_anomaly":
        return "anomaly"
    if signal.severity in {"critical", "high"}:
        return "risk"
    if signal.signal_type == "page_changed":
        return "competitor"
    if signal.signal_type == "star_growth":
        return "trend"
    return "opportunity"


def _score_signal(signal: Signal, recent_signals: list[Signal]) -> IntelligenceScores:
    impact_score = _impact_score(signal)
    confidence_score = _clamp_score(signal.confidence)
    novelty_score = _novelty_score(signal, recent_signals)
    urgency_score = _urgency_score(signal)
    final_score = _clamp_score(
        impact_score * 0.35
        + confidence_score * 0.25
        + novelty_score * 0.20
        + urgency_score * 0.20
    )
    return IntelligenceScores(
        impact_score=impact_score,
        confidence_score=confidence_score,
        novelty_score=novelty_score,
        urgency_score=urgency_score,
        final_score=final_score,
    )


def _impact_score(signal: Signal) -> float:
    ratio_component = abs(signal.delta_ratio or 0.0) * 60.0
    delta_component = abs(signal.delta or 0.0) / 5.0
    severity_floor = {
        "critical": 90.0,
        "high": 75.0,
        "medium": 55.0,
        "low": 25.0,
    }.get(signal.severity, 25.0)
    return _clamp_score(max(ratio_component, delta_component, severity_floor))


def _novelty_score(signal: Signal, recent_signals: list[Signal]) -> float:
    similar_count = sum(
        1
        for recent_signal in recent_signals
        if recent_signal.entity_id == signal.entity_id
        and recent_signal.signal_type == signal.signal_type
    )
    if similar_count <= 1:
        return 100.0
    if similar_count <= 3:
        return 70.0
    return 40.0


def _urgency_score(signal: Signal) -> float:
    severity_score = {
        "critical": 100.0,
        "high": 70.0,
        "medium": 40.0,
        "low": 10.0,
    }.get(signal.severity, 10.0)
    age_seconds = max((datetime.now(UTC) - signal.detected_at).total_seconds(), 0.0)
    freshness_score = _clamp_score(100.0 - (age_seconds / 86_400.0) * 15.0)
    return _clamp_score(severity_score * 0.7 + freshness_score * 0.3)


def _clamp_score(value: float) -> float:
    return round(min(max(value, 0.0), 100.0), 2)
