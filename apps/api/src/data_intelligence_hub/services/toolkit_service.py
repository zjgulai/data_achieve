from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.schemas.toolkit import (
    ToolkitIntelligenceResponse,
    ToolkitMethodResponse,
    ToolkitMetricsResponse,
    ToolkitOverviewResponse,
    ToolkitToolResponse,
)

DATASET = "curated_training"
TRAINING_SUMMARY_MARKER = "培训讲解："


async def get_toolkit_overview(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> ToolkitOverviewResponse:
    records = await _list_training_records(session, workspace_id)
    intelligence_items = await _list_training_intelligence(session, workspace_id)
    evidence_count = await _count_training_evidence(session, intelligence_items)
    tools = _build_tools(records)
    methods = _build_methods(records)
    last_collected_at = max((record.collected_at for record in records), default=None)
    latest_intelligence_at = max(
        (item.updated_at for item in intelligence_items),
        default=None,
    )
    generated_at = max(
        (value for value in (last_collected_at, latest_intelligence_at) if value is not None),
        default=None,
    )

    return ToolkitOverviewResponse(
        dataset=DATASET,
        generated_at=generated_at,
        metrics=ToolkitMetricsResponse(
            source_count=len(records),
            tool_count=len(tools),
            method_count=len(methods),
            intelligence_count=len(intelligence_items),
            evidence_count=evidence_count,
            last_collected_at=last_collected_at,
        ),
        tools=tools,
        methods=methods,
        intelligence_items=[
            ToolkitIntelligenceResponse(
                id=item.id,
                title=item.title,
                summary=item.summary,
                domain=item.domain,
                intelligence_type=item.intelligence_type,
                final_score=item.final_score,
                evidence_count=item.evidence_count,
                updated_at=item.updated_at,
            )
            for item in intelligence_items
        ],
    )


async def _list_training_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[RawRecord]:
    result = await session.execute(
        select(RawRecord)
        .where(RawRecord.workspace_id == workspace_id)
        .order_by(RawRecord.collected_at.desc())
        .limit(500)
    )
    return [
        record
        for record in result.scalars().all()
        if _is_training_record(record.content)
    ]


class _TrainingIntelligence:
    def __init__(self, item: IntelligenceItem, evidence_count: int) -> None:
        self.id = item.id
        self.title = item.title
        self.summary = item.summary
        self.domain = item.domain
        self.intelligence_type = item.intelligence_type
        self.final_score = item.final_score
        self.evidence_count = evidence_count
        self.updated_at = item.updated_at


async def _list_training_intelligence(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[_TrainingIntelligence]:
    evidence_counts = (
        select(Evidence.intelligence_id, func.count(Evidence.id).label("evidence_count"))
        .group_by(Evidence.intelligence_id)
        .subquery()
    )
    result = await session.execute(
        select(IntelligenceItem, func.coalesce(evidence_counts.c.evidence_count, 0))
        .outerjoin(evidence_counts, evidence_counts.c.intelligence_id == IntelligenceItem.id)
        .where(
            IntelligenceItem.workspace_id == workspace_id,
            IntelligenceItem.summary.contains(TRAINING_SUMMARY_MARKER),
        )
        .order_by(IntelligenceItem.final_score.desc(), IntelligenceItem.updated_at.desc())
        .limit(24)
    )
    return [
        _TrainingIntelligence(item=item, evidence_count=int(evidence_count))
        for item, evidence_count in result.all()
    ]


async def _count_training_evidence(
    session: AsyncSession,
    intelligence_items: list[_TrainingIntelligence],
) -> int:
    ids = [item.id for item in intelligence_items]
    if not ids:
        return 0
    result = await session.execute(
        select(func.count(Evidence.id)).where(Evidence.intelligence_id.in_(ids))
    )
    return int(result.scalar_one())


def _build_tools(records: list[RawRecord]) -> list[ToolkitToolResponse]:
    tools: list[ToolkitToolResponse] = []
    for record in records:
        wrapper = _record_wrapper(record.content)
        if wrapper.get("collector_type") != "github_repo":
            continue
        content = _content(wrapper)
        full_name = _optional_text(content.get("full_name")) or _optional_text(
            wrapper.get("source_id"),
        )
        if full_name is None:
            continue
        tools.append(
            ToolkitToolResponse(
                id=str(wrapper["source_id"]),
                name=full_name,
                category=str(wrapper.get("category") or "crawler_framework"),
                risk_level=str(wrapper.get("risk_level") or "low"),
                collector_type=str(wrapper.get("collector_type") or "github_repo"),
                source_title=str(wrapper.get("source_title") or full_name),
                source_url=_optional_text(wrapper.get("source_url"))
                or _optional_text(content.get("html_url")),
                description=_optional_text(content.get("description")),
                language=_optional_text(content.get("language")),
                license=_optional_text(content.get("license")),
                stars=_optional_int(content.get("stargazers_count")),
                forks=_optional_int(content.get("forks_count")),
                open_issues=_optional_int(content.get("open_issues_count")),
                updated_at=_optional_datetime(content.get("updated_at")),
                collected_at=record.collected_at,
            )
        )
    return sorted(tools, key=lambda tool: tool.stars or 0, reverse=True)


def _build_methods(records: list[RawRecord]) -> list[ToolkitMethodResponse]:
    methods: list[ToolkitMethodResponse] = []
    for record in records:
        wrapper = _record_wrapper(record.content)
        if wrapper.get("collector_type") != "manual_json":
            continue
        content = _content(wrapper)
        payload = _dict_value(content.get("payload"))
        if payload.get("method_id") is None:
            continue
        method_id = str(payload["method_id"])
        platform = _optional_text(payload.get("platform"))
        methods.append(
            ToolkitMethodResponse(
                id=str(wrapper.get("source_id") or method_id),
                title=str(wrapper.get("source_title") or method_id),
                category=str(wrapper.get("category") or "platform_method"),
                risk_level=str(wrapper.get("risk_level") or "medium"),
                collector_type=str(wrapper.get("collector_type") or "manual_json"),
                source_url=_optional_text(wrapper.get("source_url")),
                platform=platform,
                recommended_collector=_optional_text(payload.get("recommended_collector")),
                data_types=_string_list(payload.get("data_types")),
                boundary=_optional_text(payload.get("boundary")),
                training_takeaway=_optional_text(payload.get("training_takeaway")),
                collected_at=record.collected_at,
            )
        )
    risk_order = {"low": 0, "medium": 1, "high": 2}
    return sorted(methods, key=lambda method: (risk_order.get(method.risk_level, 9), method.title))


def _is_training_record(value: dict[str, Any] | list[Any]) -> bool:
    wrapper = _record_wrapper(value)
    provenance = _dict_value(wrapper.get("provenance"))
    return provenance.get("dataset") == DATASET


def _record_wrapper(value: dict[str, Any] | list[Any]) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _content(value: dict[str, Any]) -> dict[str, Any]:
    return _dict_value(value.get("content"))


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
