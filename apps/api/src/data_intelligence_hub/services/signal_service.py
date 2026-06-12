from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import EntitySnapshot
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.entities import get_entity, get_entity_snapshot
from data_intelligence_hub.repositories.signals import (
    get_signal,
    get_signal_by_snapshot_pair,
    list_recent_snapshots_for_entity,
    list_recent_snapshots_for_source,
    list_signals,
)
from data_intelligence_hub.repositories.tasks import list_task_runs
from data_intelligence_hub.services.exceptions import (
    SignalNotFoundError,
    SignalSnapshotCompareNotAvailableError,
)


@dataclass(frozen=True)
class SignalDraft:
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


class MetricDiff(NamedTuple):
    metric: str
    previous_value: Any | None
    current_value: Any | None
    delta: float | None
    delta_ratio: float | None


class SignalSnapshotCompare(NamedTuple):
    signal: Signal
    previous_snapshot: EntitySnapshot
    current_snapshot: EntitySnapshot
    metrics_diff: list[MetricDiff]


async def get_signals(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    entity_id: uuid.UUID | None,
    signal_type: str | None,
    severity: str | None,
) -> list[Signal]:
    return await list_signals(
        session,
        workspace.id,
        project_id=project_id,
        entity_id=entity_id,
        signal_type=signal_type,
        severity=severity,
    )


async def get_signal_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    signal_id: uuid.UUID,
) -> Signal:
    signal = await get_signal(session, workspace.id, signal_id)
    if signal is None:
        raise SignalNotFoundError
    return signal


async def get_signals_for_entity(
    session: AsyncSession,
    workspace: Workspace,
    entity_id: uuid.UUID,
) -> list[Signal]:
    entity = await get_entity(session, workspace.id, entity_id)
    if entity is None:
        from data_intelligence_hub.services.exceptions import EntityNotFoundError

        raise EntityNotFoundError
    return await list_signals(session, workspace.id, entity_id=entity_id)


async def get_signal_snapshot_compare(
    session: AsyncSession,
    workspace: Workspace,
    signal_id: uuid.UUID,
) -> SignalSnapshotCompare:
    signal = await get_signal_or_raise(session, workspace, signal_id)
    previous_snapshot = await get_entity_snapshot(session, signal.previous_snapshot_id)
    current_snapshot = await get_entity_snapshot(session, signal.current_snapshot_id)
    if previous_snapshot is None or current_snapshot is None:
        raise SignalSnapshotCompareNotAvailableError
    return SignalSnapshotCompare(
        signal=signal,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        metrics_diff=_metrics_diff(previous_snapshot.metrics, current_snapshot.metrics),
    )


async def detect_signals_for_snapshots(
    session: AsyncSession,
    workspace: Workspace,
    snapshots: list[EntitySnapshot],
) -> list[Signal]:
    detected: list[Signal] = []
    for snapshot in snapshots:
        entity = await get_entity(session, workspace.id, snapshot.entity_id)
        if entity is None:
            continue
        recent = await list_recent_snapshots_for_entity(session, entity.id, limit=2)
        if len(recent) < 2 or recent[0].id != snapshot.id:
            continue
        current_snapshot, previous_snapshot = recent[0], recent[1]
        drafts = [
            draft
            for draft in (
                _detect_star_growth(entity.entity_type, previous_snapshot, current_snapshot),
                _detect_page_changed(entity.entity_type, previous_snapshot, current_snapshot),
            )
            if draft is not None
        ]
        for draft in drafts:
            signal = await _create_signal_if_new(
                session=session,
                workspace=workspace,
                project_id=entity.project_id,
                entity_id=entity.id,
                draft=draft,
            )
            if signal is not None:
                detected.append(signal)
    return detected


async def detect_data_quality_anomaly(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
    run: TaskRun,
) -> Signal | None:
    if run.status != "failed":
        return None

    runs = await list_task_runs(session, workspace.id, task.id)
    recent_runs = runs[:10]
    if not recent_runs:
        return None
    failure_count = sum(1 for item in recent_runs if item.status == "failed")
    failure_rate = failure_count / len(recent_runs)
    consecutive_failures = _consecutive_failures(recent_runs)
    if failure_rate <= 0.3 and consecutive_failures < 3:
        return None

    snapshots = await list_recent_snapshots_for_source(session, task.source_id, limit=2)
    if not snapshots:
        return None
    current_snapshot = snapshots[0]
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else current_snapshot
    entity = await get_entity(session, workspace.id, current_snapshot.entity_id)
    if entity is None:
        return None

    severity = _data_quality_severity(failure_rate, consecutive_failures)
    draft = SignalDraft(
        signal_type="data_quality_anomaly",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=failure_rate,
        previous_value=None,
        delta=None,
        delta_ratio=None,
        confidence=80.0,
        severity=severity,
        metadata={
            "task_id": str(task.id),
            "task_run_id": str(run.id),
            "recent_failure_rate": failure_rate,
            "consecutive_failures": consecutive_failures,
        },
    )
    return await _create_signal_if_new(
        session=session,
        workspace=workspace,
        project_id=task.project_id,
        entity_id=entity.id,
        draft=draft,
    )


async def _create_signal_if_new(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    draft: SignalDraft,
) -> Signal | None:
    existing = await get_signal_by_snapshot_pair(
        session,
        draft.signal_type,
        draft.previous_snapshot_id,
        draft.current_snapshot_id,
    )
    if existing is not None:
        return None
    signal = Signal(
        workspace_id=workspace.id,
        project_id=project_id,
        entity_id=entity_id,
        signal_type=draft.signal_type,
        previous_snapshot_id=draft.previous_snapshot_id,
        current_snapshot_id=draft.current_snapshot_id,
        current_value=draft.current_value,
        previous_value=draft.previous_value,
        delta=draft.delta,
        delta_ratio=draft.delta_ratio,
        confidence=draft.confidence,
        severity=draft.severity,
        metadata_json=draft.metadata,
        detected_at=datetime.now(UTC),
    )
    session.add(signal)
    await session.flush()
    from data_intelligence_hub.services.intelligence_service import (
        generate_intelligence_for_signal,
    )

    intelligence = await generate_intelligence_for_signal(session, workspace, signal)
    from data_intelligence_hub.services.alert_service import match_alert_rules_for_signal

    await match_alert_rules_for_signal(session, workspace, signal, intelligence)
    return signal


def _detect_star_growth(
    entity_type: str,
    previous_snapshot: EntitySnapshot,
    current_snapshot: EntitySnapshot,
) -> SignalDraft | None:
    if entity_type != "github_repo":
        return None
    previous_value = _metric_number(previous_snapshot.metrics, "stars")
    current_value = _metric_number(current_snapshot.metrics, "stars")
    if previous_value is None or current_value is None:
        return None
    delta = current_value - previous_value
    if delta <= 0:
        return None
    delta_ratio = delta / previous_value if previous_value > 0 else delta
    if delta <= 100 and delta_ratio <= 2.0:
        return None
    severity = _star_growth_severity(delta, delta_ratio)
    return SignalDraft(
        signal_type="star_growth",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=current_value,
        previous_value=previous_value,
        delta=delta,
        delta_ratio=delta_ratio,
        confidence=90.0,
        severity=severity,
        metadata={"metric": "stars"},
    )


def _detect_page_changed(
    entity_type: str,
    previous_snapshot: EntitySnapshot,
    current_snapshot: EntitySnapshot,
) -> SignalDraft | None:
    if entity_type != "web_page":
        return None
    previous_hash = _metric_text(previous_snapshot.metrics, "content_hash")
    current_hash = _metric_text(current_snapshot.metrics, "content_hash")
    if previous_hash is None or current_hash is None or previous_hash == current_hash:
        return None
    previous_html = _snapshot_text(previous_snapshot.snapshot_data, "html_content")
    current_html = _snapshot_text(current_snapshot.snapshot_data, "html_content")
    change_ratio = _change_ratio(previous_html, current_html)
    severity = _page_changed_severity(change_ratio)
    return SignalDraft(
        signal_type="page_changed",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=change_ratio,
        previous_value=None,
        delta=None,
        delta_ratio=change_ratio,
        confidence=85.0,
        severity=severity,
        metadata={
            "previous_content_hash": previous_hash,
            "current_content_hash": current_hash,
            "change_ratio": change_ratio,
        },
    )


def _star_growth_severity(delta: float, delta_ratio: float) -> str:
    if delta_ratio > 5.0 or delta > 500:
        return "critical"
    if delta_ratio > 2.0 or delta > 200:
        return "high"
    if delta_ratio > 1.0 or delta > 50:
        return "medium"
    return "low"


def _page_changed_severity(change_ratio: float) -> str:
    if change_ratio > 0.3:
        return "high"
    if change_ratio > 0.1:
        return "medium"
    return "low"


def _data_quality_severity(failure_rate: float, consecutive_failures: int) -> str:
    if consecutive_failures >= 5:
        return "critical"
    if consecutive_failures >= 3:
        return "high"
    if failure_rate > 0.5:
        return "medium"
    return "low"


def _consecutive_failures(runs: list[TaskRun]) -> int:
    count = 0
    for run in runs:
        if run.status != "failed":
            break
        count += 1
    return count


def _metric_number(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _metric_text(metrics: dict[str, Any], key: str) -> str | None:
    value = metrics.get(key)
    if not isinstance(value, str):
        return None
    return value


def _metrics_diff(
    previous_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
) -> list[MetricDiff]:
    metrics = sorted(set(previous_metrics) | set(current_metrics))
    diffs: list[MetricDiff] = []
    for metric in metrics:
        previous_value = previous_metrics.get(metric)
        current_value = current_metrics.get(metric)
        delta = _number_delta(previous_value, current_value)
        delta_ratio = None
        if delta is not None and isinstance(previous_value, int | float) and previous_value != 0:
            delta_ratio = delta / float(previous_value)
        diffs.append(
            MetricDiff(
                metric=metric,
                previous_value=previous_value,
                current_value=current_value,
                delta=delta,
                delta_ratio=delta_ratio,
            )
        )
    return diffs


def _number_delta(previous_value: Any, current_value: Any) -> float | None:
    if isinstance(previous_value, bool) or isinstance(current_value, bool):
        return None
    if isinstance(previous_value, int | float) and isinstance(current_value, int | float):
        return float(current_value) - float(previous_value)
    return None


def _snapshot_text(snapshot_data: dict[str, Any], key: str) -> str:
    value = snapshot_data.get(key)
    return value if isinstance(value, str) else ""


def _change_ratio(previous: str, current: str) -> float:
    if previous == current:
        return 0.0
    longest = max(len(previous), len(current), 1)
    return _levenshtein_distance(previous[:5000], current[:5000]) / min(longest, 5000)


def _levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index_left, char_left in enumerate(left, start=1):
        current = [index_left]
        for index_right, char_right in enumerate(right, start=1):
            insertion = current[index_right - 1] + 1
            deletion = previous[index_right] + 1
            substitution = previous[index_right - 1] + (char_left != char_right)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]
