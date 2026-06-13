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
            reference_metadata=_signal_reference_metadata(signal),
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
                reference_metadata=_snapshot_reference_metadata(current_snapshot),
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
                reference_metadata=_raw_record_reference_metadata(raw_record),
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
                reference_metadata=_url_reference_metadata(source_url, raw_record),
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


def _signal_reference_metadata(signal: Signal) -> dict[str, Any]:
    metric = signal.metadata_json.get("metric")
    json_paths = [
        "$.signal_type",
        "$.severity",
        "$.previous_value",
        "$.current_value",
        "$.delta",
        "$.delta_ratio",
        "$.confidence",
        "$.metadata_json",
    ]
    return {
        "claim_type": signal.signal_type,
        "source_layer": "signal",
        "metric": metric if isinstance(metric, str) else None,
        "json_paths": json_paths,
        "snapshot_ids": {
            "previous": str(signal.previous_snapshot_id),
            "current": str(signal.current_snapshot_id),
        },
    }


def _snapshot_reference_metadata(snapshot: EntitySnapshot) -> dict[str, Any]:
    return {
        "claim_type": "current_snapshot_state",
        "source_layer": "entity_snapshot",
        "snapshot_id": str(snapshot.id),
        "raw_record_id": str(snapshot.raw_record_id),
        "json_paths": _json_leaf_paths("$.metrics", snapshot.metrics, limit=16),
        "snapshot_strategy": "entity_snapshots.metrics + entity_snapshots.snapshot_data",
    }


def _raw_record_reference_metadata(raw_record: RawRecord) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "claim_type": "raw_record_content",
        "source_layer": "raw_record",
        "raw_record_id": str(raw_record.id),
        "content_hash": raw_record.content_hash,
        "json_paths": _json_leaf_paths("$.content", raw_record.content, limit=20),
        "snapshot_strategy": _raw_record_snapshot_strategy(raw_record.content),
    }
    text_reference = _raw_text_reference(raw_record.content)
    if text_reference is not None:
        metadata["text_reference"] = text_reference
    return metadata


def _url_reference_metadata(
    source_url: str,
    raw_record: RawRecord | None,
) -> dict[str, Any]:
    return {
        "claim_type": "source_url",
        "source_layer": "source",
        "url": source_url,
        "raw_record_id": str(raw_record.id) if raw_record is not None else None,
        "content_hash": raw_record.content_hash if raw_record is not None else None,
    }


def _raw_record_snapshot_strategy(content: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(content, dict) and isinstance(content.get("html_content"), str):
        return {
            "storage": "raw_records.content.html_content",
            "text_path": "$.content.text_content",
            "html_path": "$.content.html_content",
            "html_available": True,
        }
    return {
        "storage": "raw_records.content",
        "html_available": False,
    }


def _raw_text_reference(content: dict[str, Any] | list[Any]) -> dict[str, Any] | None:
    reference = _first_text_leaf("$.content", content)
    if reference is None:
        return None
    path, text = reference
    normalized = " ".join(text.split())
    if normalized == "":
        return None
    quote = normalized[:280]
    return {
        "path": path,
        "start": 0,
        "end": len(quote),
        "quote": quote,
    }


def _first_text_leaf(prefix: str, value: Any) -> tuple[str, str] | None:
    if isinstance(value, str):
        return (prefix, value)
    if isinstance(value, dict):
        preferred_keys = (
            "text_content",
            "description",
            "title",
            "full_name",
            "name",
            "html_url",
            "source_url",
        )
        for key in preferred_keys:
            child = value.get(key)
            if isinstance(child, str) and child.strip():
                return (_json_child_path(prefix, key), child)
        for key in ("payload", "raw", "repositories", "items"):
            if key in value:
                nested = _first_text_leaf(_json_child_path(prefix, key), value[key])
                if nested is not None:
                    return nested
        for key, child in value.items():
            nested = _first_text_leaf(_json_child_path(prefix, str(key)), child)
            if nested is not None:
                return nested
    if isinstance(value, list):
        for index, child in enumerate(value):
            nested = _first_text_leaf(f"{prefix}[{index}]", child)
            if nested is not None:
                return nested
    return None


def _json_leaf_paths(prefix: str, value: Any, limit: int) -> list[str]:
    paths: list[str] = []

    def walk(path: str, node: Any) -> None:
        if len(paths) >= limit:
            return
        if isinstance(node, dict):
            if not node:
                paths.append(path)
                return
            for key, child in node.items():
                walk(_json_child_path(path, str(key)), child)
            return
        if isinstance(node, list):
            if not node:
                paths.append(path)
                return
            for index, child in enumerate(node):
                walk(f"{path}[{index}]", child)
            return
        paths.append(path)

    walk(prefix, value)
    return paths


def _json_child_path(prefix: str, key: str) -> str:
    if key.replace("_", "").isalnum():
        return f"{prefix}.{key}"
    escaped = key.replace('"', '\\"')
    return f'{prefix}["{escaped}"]'


def _json_excerpt(value: dict[str, Any] | list[Any], limit: int = 600) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) <= limit:
        return encoded
    return f"{encoded[: limit - 1]}..."
