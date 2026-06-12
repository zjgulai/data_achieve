from __future__ import annotations

import json
import uuid
from typing import Any

from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.intelligence import Evidence
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal


def build_evidences_for_signal(
    intelligence_id: uuid.UUID,
    signal: Signal,
    entity: Entity,
    current_snapshot: EntitySnapshot | None,
    raw_record: RawRecord | None,
) -> list[Evidence]:
    evidences = [
        Evidence(
            intelligence_id=intelligence_id,
            signal_id=signal.id,
            entity_id=signal.entity_id,
            raw_record_id=raw_record.id if raw_record is not None else None,
            evidence_type="signal",
            title=f"Signal {signal.signal_type}",
            url=entity.canonical_url,
            excerpt=_signal_excerpt(signal),
            highlighted_text=_signal_highlight(signal),
        )
    ]

    if current_snapshot is not None:
        evidences.append(
            Evidence(
                intelligence_id=intelligence_id,
                signal_id=signal.id,
                entity_id=signal.entity_id,
                raw_record_id=current_snapshot.raw_record_id,
                evidence_type="snapshot",
                title="Current entity snapshot",
                url=entity.canonical_url,
                excerpt=_snapshot_excerpt(current_snapshot),
                highlighted_text=_json_excerpt(current_snapshot.metrics),
            )
        )

    if raw_record is not None:
        evidences.append(
            Evidence(
                intelligence_id=intelligence_id,
                signal_id=signal.id,
                entity_id=signal.entity_id,
                raw_record_id=raw_record.id,
                evidence_type="raw_record",
                title=f"Raw record {raw_record.record_type}",
                url=raw_record.source_url,
                excerpt=_json_excerpt(raw_record.content),
                highlighted_text=_raw_record_highlight(raw_record),
            )
        )

    source_url = raw_record.source_url if raw_record is not None else entity.canonical_url
    if source_url:
        evidences.append(
            Evidence(
                intelligence_id=intelligence_id,
                signal_id=signal.id,
                entity_id=signal.entity_id,
                raw_record_id=raw_record.id if raw_record is not None else None,
                evidence_type="url",
                title="Source URL",
                url=source_url,
                excerpt=source_url,
                highlighted_text=source_url,
            )
        )

    return evidences


def _signal_excerpt(signal: Signal) -> str:
    metric = signal.metadata_json.get("metric")
    metric_text = f" on {metric}" if isinstance(metric, str) else ""
    return (
        f"{signal.signal_type}{metric_text}: previous={signal.previous_value}, "
        f"current={signal.current_value}, delta={signal.delta}, severity={signal.severity}."
    )


def _signal_highlight(signal: Signal) -> str:
    return (
        f"confidence={signal.confidence}; delta_ratio={signal.delta_ratio}; "
        f"previous_snapshot={signal.previous_snapshot_id}; "
        f"current_snapshot={signal.current_snapshot_id}"
    )


def _snapshot_excerpt(snapshot: EntitySnapshot) -> str:
    return f"snapshot={snapshot.id}; metrics={_json_excerpt(snapshot.metrics, limit=320)}"


def _raw_record_highlight(raw_record: RawRecord) -> str:
    if raw_record.screenshot_url:
        excerpt = _json_excerpt(raw_record.content)
        return f"screenshot={raw_record.screenshot_url}; content={excerpt}"
    return _json_excerpt(raw_record.content)


def _json_excerpt(value: dict[str, Any] | list[Any], limit: int = 600) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) <= limit:
        return encoded
    return f"{encoded[: limit - 1]}..."
