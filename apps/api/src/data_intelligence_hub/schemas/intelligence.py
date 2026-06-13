from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.entity import Entity
from data_intelligence_hub.models.intelligence import (
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
)
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import TaskRun

IntelligenceStatus = Literal["new", "reviewed", "following", "dismissed", "converted"]
FeedbackType = Literal["useful", "not_useful", "false_positive"]


class IntelligenceResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    summary: str
    intelligence_type: str
    status: str
    impact_score: float
    confidence_score: float
    novelty_score: float
    urgency_score: float
    final_score: float
    generated_by: str
    domain: str
    evidence_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, item: IntelligenceItem, evidence_count: int) -> IntelligenceResponse:
        return cls(
            id=item.id,
            workspace_id=item.workspace_id,
            project_id=item.project_id,
            title=item.title,
            summary=item.summary,
            intelligence_type=item.intelligence_type,
            status=item.status,
            impact_score=item.impact_score,
            confidence_score=item.confidence_score,
            novelty_score=item.novelty_score,
            urgency_score=item.urgency_score,
            final_score=item.final_score,
            generated_by=item.generated_by,
            domain=item.domain,
            evidence_count=evidence_count,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class EvidenceSignalContext(BaseModel):
    id: uuid.UUID
    signal_type: str
    severity: str
    previous_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID
    current_value: float | None
    previous_value: float | None
    delta: float | None
    delta_ratio: float | None
    confidence: float
    metadata: dict[str, Any]
    detected_at: datetime

    @classmethod
    def from_model(cls, signal: Signal) -> EvidenceSignalContext:
        return cls(
            id=signal.id,
            signal_type=signal.signal_type,
            severity=signal.severity,
            previous_snapshot_id=signal.previous_snapshot_id,
            current_snapshot_id=signal.current_snapshot_id,
            current_value=signal.current_value,
            previous_value=signal.previous_value,
            delta=signal.delta,
            delta_ratio=signal.delta_ratio,
            confidence=signal.confidence,
            metadata=signal.metadata_json,
            detected_at=signal.detected_at,
        )


class EvidenceEntityContext(BaseModel):
    id: uuid.UUID
    entity_type: str
    external_id: str
    canonical_url: str | None
    name: str
    domain: str
    latest_snapshot_id: uuid.UUID | None

    @classmethod
    def from_model(cls, entity: Entity) -> EvidenceEntityContext:
        return cls(
            id=entity.id,
            entity_type=entity.entity_type,
            external_id=entity.external_id,
            canonical_url=entity.canonical_url,
            name=entity.name,
            domain=entity.domain,
            latest_snapshot_id=entity.latest_snapshot_id,
        )


class EvidenceRawRecordContext(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    task_run_id: uuid.UUID
    record_type: str
    source_url: str | None
    content_hash: str
    screenshot_url: str | None
    content_preview: dict[str, Any] | list[Any] | str
    collected_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, raw_record: RawRecord) -> EvidenceRawRecordContext:
        return cls(
            id=raw_record.id,
            source_id=raw_record.source_id,
            task_run_id=raw_record.task_run_id,
            record_type=raw_record.record_type,
            source_url=raw_record.source_url,
            content_hash=raw_record.content_hash,
            screenshot_url=raw_record.screenshot_url,
            content_preview=_bounded_json_preview(raw_record.content),
            collected_at=raw_record.collected_at,
            created_at=raw_record.created_at,
        )


class EvidenceTaskRunContext(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    records_count: int
    entities_count: int
    error_message: str | None

    @classmethod
    def from_model(cls, task_run: TaskRun) -> EvidenceTaskRunContext:
        return cls(
            id=task_run.id,
            task_id=task_run.task_id,
            status=task_run.status,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            records_count=task_run.records_count,
            entities_count=task_run.entities_count,
            error_message=task_run.error_message,
        )


class EvidenceSourceContext(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    url: str | None
    enabled: bool

    @classmethod
    def from_model(cls, source: Source) -> EvidenceSourceContext:
        return cls(
            id=source.id,
            name=source.name,
            type=source.type,
            url=source.url,
            enabled=source.enabled,
        )


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    intelligence_id: uuid.UUID
    signal_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    raw_record_id: uuid.UUID | None
    evidence_type: str
    title: str
    url: str | None
    excerpt: str | None
    highlighted_text: str | None
    screenshot_url: str | None
    signal: EvidenceSignalContext | None
    entity: EvidenceEntityContext | None
    raw_record: EvidenceRawRecordContext | None
    task_run: EvidenceTaskRunContext | None
    source: EvidenceSourceContext | None
    created_at: datetime

    @classmethod
    def from_model(
        cls,
        evidence: Evidence,
        screenshot_url: str | None = None,
        signal: Signal | None = None,
        entity: Entity | None = None,
        raw_record: RawRecord | None = None,
        task_run: TaskRun | None = None,
        source: Source | None = None,
    ) -> EvidenceResponse:
        return cls(
            id=evidence.id,
            intelligence_id=evidence.intelligence_id,
            signal_id=evidence.signal_id,
            entity_id=evidence.entity_id,
            raw_record_id=evidence.raw_record_id,
            evidence_type=evidence.evidence_type,
            title=evidence.title,
            url=evidence.url,
            excerpt=evidence.excerpt,
            highlighted_text=evidence.highlighted_text,
            screenshot_url=screenshot_url,
            signal=EvidenceSignalContext.from_model(signal) if signal is not None else None,
            entity=EvidenceEntityContext.from_model(entity) if entity is not None else None,
            raw_record=(
                EvidenceRawRecordContext.from_model(raw_record)
                if raw_record is not None
                else None
            ),
            task_run=(
                EvidenceTaskRunContext.from_model(task_run) if task_run is not None else None
            ),
            source=EvidenceSourceContext.from_model(source) if source is not None else None,
            created_at=evidence.created_at,
        )


class IntelligenceStatusUpdateRequest(BaseModel):
    status: IntelligenceStatus


class IntelligenceFeedbackRequest(BaseModel):
    feedback_type: FeedbackType
    comment: str | None = None


class IntelligenceFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intelligence_id: uuid.UUID
    user_id: uuid.UUID
    feedback_type: str
    comment: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, feedback: IntelligenceFeedback) -> IntelligenceFeedbackResponse:
        return cls.model_validate(feedback)


def _bounded_json_preview(content: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any] | str:
    encoded = json.dumps(content, ensure_ascii=False, default=str)
    if len(encoded) <= 1200:
        return content
    return f"{encoded[:1200]}...[truncated]"
