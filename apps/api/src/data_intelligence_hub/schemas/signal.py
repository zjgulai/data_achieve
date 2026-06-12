from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from data_intelligence_hub.models.entity import EntitySnapshot
from data_intelligence_hub.models.signal import Signal


class SignalResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    entity_id: uuid.UUID
    signal_type: str
    previous_snapshot_id: uuid.UUID
    current_snapshot_id: uuid.UUID
    current_value: float | None
    previous_value: float | None
    delta: float | None
    delta_ratio: float | None
    confidence: float
    severity: str
    metadata: dict[str, Any]
    detected_at: datetime

    @classmethod
    def from_model(cls, signal: Signal) -> SignalResponse:
        return cls(
            id=signal.id,
            workspace_id=signal.workspace_id,
            project_id=signal.project_id,
            entity_id=signal.entity_id,
            signal_type=signal.signal_type,
            previous_snapshot_id=signal.previous_snapshot_id,
            current_snapshot_id=signal.current_snapshot_id,
            current_value=signal.current_value,
            previous_value=signal.previous_value,
            delta=signal.delta,
            delta_ratio=signal.delta_ratio,
            confidence=signal.confidence,
            severity=signal.severity,
            metadata=signal.metadata_json,
            detected_at=signal.detected_at,
        )


class SnapshotMetricDiff(BaseModel):
    metric: str
    previous_value: Any | None
    current_value: Any | None
    delta: float | None
    delta_ratio: float | None


class SnapshotCompareItem(BaseModel):
    id: uuid.UUID
    raw_record_id: uuid.UUID
    metrics: dict[str, Any]
    snapshot_data: dict[str, Any]
    captured_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, snapshot: EntitySnapshot) -> SnapshotCompareItem:
        return cls(
            id=snapshot.id,
            raw_record_id=snapshot.raw_record_id,
            metrics=snapshot.metrics,
            snapshot_data=snapshot.snapshot_data,
            captured_at=snapshot.captured_at,
            created_at=snapshot.created_at,
        )


class SignalSnapshotCompareResponse(BaseModel):
    signal_id: uuid.UUID
    entity_id: uuid.UUID
    signal_type: str
    previous_snapshot: SnapshotCompareItem
    current_snapshot: SnapshotCompareItem
    metrics_diff: list[SnapshotMetricDiff]
