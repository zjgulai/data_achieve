from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.entities import get_entity_by_external_id
from data_intelligence_hub.repositories.projects import get_project


@dataclass(frozen=True)
class NormalizedSnapshotDraft:
    entity_type: str
    external_id: str
    canonical_url: str | None
    name: str
    domain: str
    snapshot_data: dict[str, Any]
    metrics: dict[str, Any]
    captured_at: datetime


async def normalize_raw_record(
    session: AsyncSession,
    workspace: Workspace,
    raw_record: RawRecord,
) -> list[EntitySnapshot]:
    project = await get_project(session, workspace.id, raw_record.project_id)
    if project is None:
        return []

    drafts = build_snapshot_drafts(raw_record, project.domain)
    snapshots: list[EntitySnapshot] = []
    for draft in drafts:
        entity = await _upsert_entity(session, workspace, raw_record, draft)
        snapshot = EntitySnapshot(
            entity_id=entity.id,
            raw_record_id=raw_record.id,
            snapshot_data=draft.snapshot_data,
            metrics=draft.metrics,
            captured_at=draft.captured_at,
            created_at=datetime.now(UTC),
        )
        session.add(snapshot)
        await session.flush()
        entity.latest_snapshot_id = snapshot.id
        entity.last_seen_at = draft.captured_at
        entity.name = draft.name
        entity.canonical_url = draft.canonical_url
        entity.domain = draft.domain
        snapshots.append(snapshot)
    return snapshots


def build_snapshot_drafts(
    raw_record: RawRecord,
    project_domain: str,
) -> list[NormalizedSnapshotDraft]:
    content = raw_record.content
    if not isinstance(content, dict):
        return []

    record_type = raw_record.record_type
    if record_type == "github_repo":
        return [_github_repo_snapshot(content, raw_record, project_domain)]
    if record_type == "github_topic":
        return _github_topic_snapshots(content, raw_record, project_domain)
    if record_type == "generic_web":
        return [_generic_web_snapshot(content, raw_record, project_domain)]
    if record_type == "manual_json":
        return _manual_json_snapshots(content, raw_record, project_domain)
    return []


async def _upsert_entity(
    session: AsyncSession,
    workspace: Workspace,
    raw_record: RawRecord,
    draft: NormalizedSnapshotDraft,
) -> Entity:
    entity = await get_entity_by_external_id(
        session,
        workspace.id,
        draft.entity_type,
        draft.external_id,
    )
    if entity is not None:
        return entity

    entity = Entity(
        workspace_id=workspace.id,
        project_id=raw_record.project_id,
        entity_type=draft.entity_type,
        external_id=draft.external_id,
        canonical_url=draft.canonical_url,
        name=draft.name,
        domain=draft.domain,
        latest_snapshot_id=None,
        first_seen_at=draft.captured_at,
        last_seen_at=draft.captured_at,
    )
    try:
        async with session.begin_nested():
            session.add(entity)
            await session.flush()
    except IntegrityError:
        entity = await get_entity_by_external_id(
            session,
            workspace.id,
            draft.entity_type,
            draft.external_id,
        )
        if entity is None:
            raise
    return entity


def _github_repo_snapshot(
    content: dict[str, Any],
    raw_record: RawRecord,
    project_domain: str,
) -> NormalizedSnapshotDraft:
    full_name = _text(content.get("full_name")) or _text(content.get("name")) or raw_record.id.hex
    name = full_name
    canonical_url = _text(content.get("html_url")) or raw_record.source_url
    return NormalizedSnapshotDraft(
        entity_type="github_repo",
        external_id=full_name,
        canonical_url=canonical_url,
        name=name,
        domain=project_domain,
        snapshot_data=_clean_snapshot(content),
        metrics={
            "stars": _number(content.get("stargazers_count")),
            "forks": _number(content.get("forks_count")),
            "open_issues": _number(content.get("open_issues_count")),
            "watchers": _number(content.get("watchers_count")),
        },
        captured_at=raw_record.collected_at,
    )


def _github_topic_snapshots(
    content: dict[str, Any],
    raw_record: RawRecord,
    project_domain: str,
) -> list[NormalizedSnapshotDraft]:
    repositories = content.get("repositories")
    if not isinstance(repositories, list):
        return []
    topic = _text(content.get("topic"))
    drafts: list[NormalizedSnapshotDraft] = []
    for repository in repositories:
        if not isinstance(repository, dict):
            continue
        full_name = _text(repository.get("full_name"))
        if full_name is None:
            continue
        snapshot_data = {"topic": topic, **repository}
        drafts.append(
            NormalizedSnapshotDraft(
                entity_type="github_repo",
                external_id=full_name,
                canonical_url=_text(repository.get("html_url")),
                name=full_name,
                domain=project_domain,
                snapshot_data=_clean_snapshot(snapshot_data),
                metrics={
                    "stars": _number(repository.get("stargazers_count")),
                    "forks": _number(repository.get("forks_count")),
                },
                captured_at=raw_record.collected_at,
            )
        )
    return drafts


def _generic_web_snapshot(
    content: dict[str, Any],
    raw_record: RawRecord,
    project_domain: str,
) -> NormalizedSnapshotDraft:
    url = _text(content.get("url")) or raw_record.source_url or raw_record.id.hex
    title = _text(content.get("title")) or url
    text_content = _text(content.get("text_content")) or ""
    html_content = _text(content.get("html_content")) or ""
    return NormalizedSnapshotDraft(
        entity_type="web_page",
        external_id=url,
        canonical_url=url,
        name=title,
        domain=project_domain,
        snapshot_data=_clean_snapshot(content),
        metrics={
            "text_length": len(text_content),
            "html_length": len(html_content),
            "content_hash": raw_record.content_hash,
        },
        captured_at=raw_record.collected_at,
    )


def _manual_json_snapshots(
    content: dict[str, Any],
    raw_record: RawRecord,
    project_domain: str,
) -> list[NormalizedSnapshotDraft]:
    entity_type = _text(content.get("entity_type")) or "manual_entity"
    payload = content.get("payload")
    if isinstance(payload, list):
        return [
            _manual_payload_snapshot(entity_type, item, raw_record, project_domain, index)
            for index, item in enumerate(payload)
        ]
    return [_manual_payload_snapshot(entity_type, payload, raw_record, project_domain, 0)]


def _manual_payload_snapshot(
    entity_type: str,
    payload: object,
    raw_record: RawRecord,
    project_domain: str,
    index: int,
) -> NormalizedSnapshotDraft:
    payload_data = payload if isinstance(payload, dict) else {"value": payload}
    external_id = _manual_external_id(payload_data, raw_record.id, index)
    canonical_url = _text(payload_data.get("url")) if isinstance(payload_data, dict) else None
    name = _manual_name(payload_data, external_id)
    return NormalizedSnapshotDraft(
        entity_type=entity_type,
        external_id=external_id,
        canonical_url=canonical_url,
        name=name,
        domain=project_domain,
        snapshot_data=_clean_snapshot(payload_data),
        metrics=_extract_numeric_metrics(payload_data),
        captured_at=raw_record.collected_at,
    )


def _manual_external_id(payload: dict[str, Any], raw_record_id: uuid.UUID, index: int) -> str:
    for key in ("external_id", "id", "sku", "url", "name", "title", "full_name"):
        value = _text(payload.get(key))
        if value is not None:
            return value
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return f"{raw_record_id.hex}:{index}:{hashlib.sha256(encoded).hexdigest()[:16]}"


def _manual_name(payload: dict[str, Any], fallback: str) -> str:
    for key in ("name", "title", "full_name", "sku", "id", "external_id"):
        value = _text(payload.get(key))
        if value is not None:
            return value
    return fallback


def _extract_numeric_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            metrics[key] = value
    return metrics


def _clean_snapshot(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _number(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    return None
