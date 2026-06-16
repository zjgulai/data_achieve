from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ToolkitMetricsResponse(BaseModel):
    source_count: int
    tool_count: int
    method_count: int
    intelligence_count: int
    evidence_count: int
    last_collected_at: datetime | None


class ToolkitToolResponse(BaseModel):
    id: str
    name: str
    category: str
    risk_level: str
    collector_type: str
    source_title: str
    source_url: str | None
    description: str | None
    language: str | None
    license: str | None
    stars: int | None
    forks: int | None
    open_issues: int | None
    updated_at: datetime | None
    collected_at: datetime


class ToolkitMethodResponse(BaseModel):
    id: str
    title: str
    category: str
    risk_level: str
    collector_type: str
    source_url: str | None
    platform: str | None
    recommended_collector: str | None
    data_types: list[str]
    boundary: str | None
    training_takeaway: str | None
    collected_at: datetime


class ToolkitIntelligenceResponse(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    domain: str
    intelligence_type: str
    final_score: float
    evidence_count: int
    updated_at: datetime


class ToolkitLearningPathResponse(BaseModel):
    id: str
    title: str
    stage: str
    focus: str
    risk_level: str
    tool_count: int
    method_count: int
    intelligence_count: int
    evidence_count: int
    tools: list[str]
    methods: list[str]
    acceptance_criteria: list[str]
    source_urls: list[str]


class ToolkitLecturePlaybookResponse(BaseModel):
    id: str
    intelligence_id: uuid.UUID
    title: str
    audience: str
    level: str
    duration_minutes: int
    claim: str
    teaching_sequence: list[str]
    hands_on_steps: list[str]
    verification_steps: list[str]
    risk_boundaries: list[str]
    classroom_exercise: str
    evidence_urls: list[str]
    evidence_count: int
    final_score: float


class ToolkitOverviewResponse(BaseModel):
    dataset: str
    generated_at: datetime | None
    metrics: ToolkitMetricsResponse
    learning_paths: list[ToolkitLearningPathResponse]
    lecture_playbooks: list[ToolkitLecturePlaybookResponse]
    tools: list[ToolkitToolResponse]
    methods: list[ToolkitMethodResponse]
    intelligence_items: list[ToolkitIntelligenceResponse]
