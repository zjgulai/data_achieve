from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.intelligence import (
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
)

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
    created_at: datetime

    @classmethod
    def from_model(
        cls,
        evidence: Evidence,
        screenshot_url: str | None = None,
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
