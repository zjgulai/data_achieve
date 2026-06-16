from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.raw_records import get_raw_record_by_hash
from data_intelligence_hub.schemas.toolkit import (
    ToolkitMethodCardDraftRequest,
    ToolkitMethodCardDraftResponse,
    ToolkitPreflightReportResponse,
)

SYSTEM_PROJECT_NAME = "工具箱授权预检草稿"
SYSTEM_SOURCE_NAME = "授权 URL 预检方法卡草稿箱"
SYSTEM_SOURCE_URL = "toolkit://authorized-url-preflight-method-card-drafts"
SYSTEM_TASK_NAME = "授权 URL 预检方法卡草稿保存"
SYSTEM_DATASET = "toolkit_method_card_drafts"
RECORD_TYPE = "toolkit_method_card_draft"


async def list_method_card_drafts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int = 30,
) -> list[ToolkitMethodCardDraftResponse]:
    result = await session.execute(
        select(RawRecord)
        .where(
            RawRecord.workspace_id == workspace_id,
            RawRecord.record_type == RECORD_TYPE,
        )
        .order_by(RawRecord.collected_at.desc())
        .limit(limit)
    )
    return [
        _raw_record_to_draft(record)
        for record in result.scalars().all()
        if _is_method_card_draft(record.content)
    ]


async def save_method_card_draft(
    session: AsyncSession,
    workspace: Workspace,
    payload: ToolkitMethodCardDraftRequest,
) -> ToolkitMethodCardDraftResponse:
    project, source, task = await _ensure_system_context(session, workspace)
    now = datetime.now(UTC)
    content_hash = _stable_draft_hash(payload.preflight_report.final_url)
    content = _draft_content(payload, now)
    existing = await get_raw_record_by_hash(
        session=session,
        workspace_id=workspace.id,
        source_id=source.id,
        content_hash=content_hash,
    )
    if existing is not None:
        existing.source_url = payload.preflight_report.final_url
        existing.content = content
        existing.collected_at = now
        await session.commit()
        await session.refresh(existing)
        return _raw_record_to_draft(existing)

    run = TaskRun(
        task_id=task.id,
        workspace_id=workspace.id,
        status="success",
        started_at=now,
        finished_at=now,
        records_count=1,
        entities_count=0,
        error_message=None,
        error_traceback=None,
        logs=[
            {
                "step": "toolkit_method_card_draft_saved",
                "source_url": payload.preflight_report.final_url,
                "status": payload.status,
            }
        ],
        created_at=now,
    )
    session.add(run)
    await session.flush()

    record = RawRecord(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        task_run_id=run.id,
        record_type=RECORD_TYPE,
        source_url=payload.preflight_report.final_url,
        content=content,
        content_hash=content_hash,
        screenshot_url=None,
        collected_at=now,
        created_at=now,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return _raw_record_to_draft(record)


async def _ensure_system_context(
    session: AsyncSession,
    workspace: Workspace,
) -> tuple[Project, Source, CollectionTask]:
    project = await session.scalar(
        select(Project)
        .where(
            Project.workspace_id == workspace.id,
            Project.name == SYSTEM_PROJECT_NAME,
        )
        .order_by(Project.created_at.asc())
    )
    if project is None:
        project = Project(
            workspace_id=workspace.id,
            name=SYSTEM_PROJECT_NAME,
            description="用于保存授权 URL 预检后生成的待人工确认方法卡草稿。",
            domain="training",
            status="active",
            owner_id=workspace.owner_id,
        )
        session.add(project)
        await session.flush()

    source = await session.scalar(
        select(Source)
        .where(
            Source.workspace_id == workspace.id,
            Source.url == SYSTEM_SOURCE_URL,
        )
        .order_by(Source.created_at.asc())
    )
    if source is None:
        source = Source(
            workspace_id=workspace.id,
            project_id=project.id,
            name=SYSTEM_SOURCE_NAME,
            type="manual_json",
            url=SYSTEM_SOURCE_URL,
            config={"kind": RECORD_TYPE, "dataset": SYSTEM_DATASET},
            schedule_cron=None,
            enabled=False,
        )
        session.add(source)
        await session.flush()

    task = await session.scalar(
        select(CollectionTask).where(CollectionTask.source_id == source.id)
    )
    if task is None:
        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=source.project_id,
            source_id=source.id,
            collector_type="manual_json",
            name=SYSTEM_TASK_NAME,
            schedule_cron=None,
            status="draft",
            config={"kind": RECORD_TYPE, "dataset": SYSTEM_DATASET},
        )
        session.add(task)
        await session.flush()
    return project, source, task


def _draft_content(
    payload: ToolkitMethodCardDraftRequest,
    saved_at: datetime,
) -> dict[str, Any]:
    report = payload.preflight_report
    method_id = _method_id(report.final_url)
    title = _draft_title(report)
    return {
        "kind": RECORD_TYPE,
        "dataset": SYSTEM_DATASET,
        "source_title": title,
        "source_url": report.final_url,
        "collector_type": "manual_json",
        "category": "platform_method",
        "risk_level": report.authorization_gate.risk_level,
        "manual_confirm_state": payload.status,
        "provenance": {
            "dataset": SYSTEM_DATASET,
            "source": "toolkit_authorized_url_preflight",
            "saved_at": saved_at.isoformat(),
        },
        "content": {
            "payload": {
                "method_id": method_id,
                "platform": _hostname(report.final_url),
                "status": payload.status,
                "recommended_collector": _recommended_collector(report),
                "data_types": _data_types(report),
                "boundary": _boundary(report),
                "training_takeaway": _training_takeaway(report),
                "review_note": payload.review_note.strip()
                if payload.review_note and payload.review_note.strip()
                else None,
                "preflight_report": report.model_dump(mode="json"),
            }
        },
    }


def _raw_record_to_draft(record: RawRecord) -> ToolkitMethodCardDraftResponse:
    wrapper = _dict_value(record.content)
    content = _dict_value(wrapper.get("content"))
    payload = _dict_value(content.get("payload"))
    status = _status_value(payload.get("status") or wrapper.get("manual_confirm_state"))
    return ToolkitMethodCardDraftResponse(
        id=record.id,
        title=str(wrapper.get("source_title") or payload.get("method_id") or "授权预检方法卡"),
        method_id=str(payload.get("method_id") or _method_id(record.source_url or "")),
        source_url=str(wrapper.get("source_url") or record.source_url or ""),
        status=status,
        manual_confirm_state=status,
        risk_level=str(wrapper.get("risk_level") or "medium"),
        recommended_collector=str(payload.get("recommended_collector") or "manual_review"),
        data_types=_string_list(payload.get("data_types")),
        boundary=str(payload.get("boundary") or ""),
        training_takeaway=str(payload.get("training_takeaway") or ""),
        review_note=_optional_text(payload.get("review_note")),
        created_at=record.created_at,
        last_saved_at=record.collected_at,
    )


def _is_method_card_draft(value: dict[str, Any] | list[Any]) -> bool:
    wrapper = _dict_value(value)
    provenance = _dict_value(wrapper.get("provenance"))
    return (
        wrapper.get("kind") == RECORD_TYPE
        and provenance.get("dataset") == SYSTEM_DATASET
    )


def _stable_draft_hash(final_url: str) -> str:
    normalized = final_url.strip().rstrip("/")
    return hashlib.sha256(f"{RECORD_TYPE}:{normalized}".encode()).hexdigest()


def _draft_title(report: ToolkitPreflightReportResponse) -> str:
    title = report.dom.title or _hostname(report.final_url) or report.final_url
    return f"授权预检方法卡：{title[:80]}"


def _method_id(final_url: str) -> str:
    host = _hostname(final_url) or "unknown-url"
    slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return f"preflight-{slug or 'unknown-url'}"


def _hostname(url: str) -> str | None:
    return urlparse(url).hostname


def _recommended_collector(report: ToolkitPreflightReportResponse) -> str:
    content_type = (report.network.final_content_type or "").lower()
    if not report.authorization_gate.allowed_to_continue:
        return "manual_review"
    if "html" not in content_type:
        return "official_api_or_file_download"
    if report.network.form_count > 0 or report.network.script_count > 10:
        return "playwright_authorized_preflight"
    if report.sitemap.available or report.network.same_origin_links > 0:
        return "generic_web"
    return "manual_json"


def _data_types(report: ToolkitPreflightReportResponse) -> list[str]:
    data_types = ["headers", "robots", "dom", "network"]
    if report.sitemap.available:
        data_types.append("sitemap")
    if report.security_txt.available:
        data_types.append("security_txt")
    if report.redirects:
        data_types.append("redirects")
    return data_types


def _boundary(report: ToolkitPreflightReportResponse) -> str:
    if report.authorization_gate.blocked_reasons:
        return "阻断： " + "；".join(report.authorization_gate.blocked_reasons)
    return "仅限已授权公开页面预检；不处理登录、验证码、风控绕过、账号态数据或个人敏感信息。"


def _training_takeaway(report: ToolkitPreflightReportResponse) -> str:
    collector = _recommended_collector(report)
    return (
        f"先用授权预检判断 robots、headers、DOM 和 network，再选择 {collector}；"
        "未完成人工确认前只作为方法卡草稿，不进入正式 SOP。"
    )


def _status_value(value: Any) -> Literal["draft", "review"]:
    return value if value in {"draft", "review"} else "draft"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
