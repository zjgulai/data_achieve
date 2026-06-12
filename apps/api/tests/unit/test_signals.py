from __future__ import annotations

import uuid
from datetime import UTC, datetime

from data_intelligence_hub.models.entity import EntitySnapshot
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.services.intelligence_service import (
    _intelligence_type,
    _score_signal,
)
from data_intelligence_hub.services.signal_service import (
    _consecutive_failures,
    _data_quality_severity,
    _detect_page_changed,
    _detect_star_growth,
)


def make_snapshot(metrics: dict[str, object], snapshot_data: dict[str, object]) -> EntitySnapshot:
    now = datetime.now(UTC)
    return EntitySnapshot(
        id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        raw_record_id=uuid.uuid4(),
        snapshot_data=snapshot_data,
        metrics=metrics,
        captured_at=now,
        created_at=now,
    )


def test_detect_star_growth_signal_from_two_snapshots() -> None:
    previous = make_snapshot({"stars": 100}, {})
    current = make_snapshot({"stars": 260}, {})

    draft = _detect_star_growth("github_repo", previous, current)

    assert draft is not None
    assert draft.signal_type == "star_growth"
    assert draft.previous_value == 100
    assert draft.current_value == 260
    assert draft.delta == 160
    assert draft.severity == "medium"


def test_detect_page_changed_signal_from_content_hash_change() -> None:
    previous = make_snapshot(
        {"content_hash": "old"},
        {"html_content": "<html><body>old hero</body></html>"},
    )
    current = make_snapshot(
        {"content_hash": "new"},
        {"html_content": "<html><body>new hero and pricing</body></html>"},
    )

    draft = _detect_page_changed("web_page", previous, current)

    assert draft is not None
    assert draft.signal_type == "page_changed"
    assert draft.delta_ratio is not None
    assert draft.delta_ratio > 0
    assert draft.metadata["previous_content_hash"] == "old"


def test_data_quality_failure_helpers() -> None:
    now = datetime.now(UTC)
    runs = [
        TaskRun(
            task_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            status="failed",
            started_at=now,
            finished_at=now,
            records_count=0,
            entities_count=0,
            error_message="failed",
            error_traceback=None,
            logs=[],
            created_at=now,
        ),
        TaskRun(
            task_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            status="failed",
            started_at=now,
            finished_at=now,
            records_count=0,
            entities_count=0,
            error_message="failed",
            error_traceback=None,
            logs=[],
            created_at=now,
        ),
        TaskRun(
            task_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            status="success",
            started_at=now,
            finished_at=now,
            records_count=1,
            entities_count=1,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=now,
        ),
    ]

    assert _consecutive_failures(runs) == 2
    assert _data_quality_severity(0.6, 2) == "medium"
    assert _data_quality_severity(0.4, 3) == "high"


def test_intelligence_scoring_uses_prd_weights() -> None:
    now = datetime.now(UTC)
    signal = _make_signal(
        signal_type="star_growth",
        delta=160,
        delta_ratio=1.6,
        confidence=90,
        severity="medium",
        detected_at=now,
    )

    scores = _score_signal(signal, [signal])

    assert _intelligence_type(signal) == "trend"
    assert scores.impact_score == 96
    assert scores.confidence_score == 90
    assert scores.novelty_score == 100
    assert scores.final_score == 87.7


def _make_signal(
    signal_type: str,
    delta: float | None,
    delta_ratio: float | None,
    confidence: float,
    severity: str,
    detected_at: datetime,
) -> Signal:
    entity_id = uuid.uuid4()
    return Signal(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        entity_id=entity_id,
        signal_type=signal_type,
        previous_snapshot_id=uuid.uuid4(),
        current_snapshot_id=uuid.uuid4(),
        current_value=260,
        previous_value=100,
        delta=delta,
        delta_ratio=delta_ratio,
        confidence=confidence,
        severity=severity,
        metadata_json={"metric": "stars"},
        detected_at=detected_at,
    )
