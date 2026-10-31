"""``/api/insight`` 四个只读端点的路由级测试。

覆盖三类主路径：

1. 正常返回：分析类型、列表、详情、正文与下载。
2. 记录不存在：未知 ID、跨工作区、已下架。
3. 数据源不可用：生成声明恒为不可用；正文缺失与哈希失败 fail-closed。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from typing import NamedTuple

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.insight_report import (
    InsightReport,
    InsightReportContent,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

REPORT_HTML = (
    "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<title>测试报告</title></head><body><h1>报告正文</h1></body></html>"
)
REPORT_SHA256 = hashlib.sha256(REPORT_HTML.encode("utf-8")).hexdigest()

DATA_SCOPE = {
    "window_label": "2026-10",
    "window_end": "2026-10-28",
    "sample_size": 288,
    "sampling": "392 个 hashtag × 43 天，每个 tag 取榜单 top20",
    "source": {
        "environment": "local docker / abi_migtest",
        "database": "abitest",
        "last_write_at": "2026-10-28",
        "tables": [
            {"schema": "raw", "name": "si_tiktok_video", "rows": 31366},
        ],
    },
}


class SeededReport(NamedTuple):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    ready_report_id: uuid.UUID
    missing_content_report_id: uuid.UUID
    withdrawn_report_id: uuid.UUID
    other_workspace_report_id: uuid.UUID


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        http_client.session_factory = session_factory  # type: ignore[attr-defined]
        yield http_client
    app.dependency_overrides.clear()
    await engine.dispose()


def _make_report(
    *,
    report_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID,
    version: str,
    status: str = "ready",
    generated_at: datetime | None = None,
    title: str = "下周拍什么：288 条母婴爆款的选题报告",
) -> InsightReport:
    return InsightReport(
        id=report_id or uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=None,
        analysis_type="tiktok_viral_topic",
        title=title,
        summary="下周优先拍产品清单、教程、身份共鸣三类常青内容。",
        status=status,
        version=version,
        data_scope=DATA_SCOPE,
        source_status="snapshot_only",
        source_note="报告基于本地 abi_migtest 快照生成；生产环境未接入该数据源。",
        generated_at=generated_at or datetime(2026, 10, 31, tzinfo=UTC),
        imported_at=datetime(2026, 10, 31, 10, tzinfo=UTC),
        created_by=None,
    )


def _make_content(report_id: uuid.UUID, html: str = REPORT_HTML) -> InsightReportContent:
    payload = html.encode("utf-8")
    return InsightReportContent(
        report_id=report_id,
        content_format="html",
        content_html=html,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        content_bytes=len(payload),
    )


async def _seed(client: AsyncClient) -> SeededReport:
    session_factory = client.session_factory  # type: ignore[attr-defined]
    workspace_id = uuid.uuid4()
    other_workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    ready_id = uuid.uuid4()
    missing_id = uuid.uuid4()
    withdrawn_id = uuid.uuid4()
    other_report_id = uuid.uuid4()

    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email="insight-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Insight WS",
                    slug="insight-ws",
                    owner_id=user_id,
                ),
                WorkspaceMember(
                    workspace_id=workspace_id, user_id=user_id, role="owner"
                ),
                User(
                    id=other_user_id,
                    email="insight-other@example.com",
                    password_hash="x",
                    name="Other",
                    status="active",
                ),
                Workspace(
                    id=other_workspace_id,
                    name="Other WS",
                    slug="insight-other-ws",
                    owner_id=other_user_id,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                _make_report(
                    report_id=ready_id,
                    workspace_id=workspace_id,
                    version="2026-10-31",
                ),
                _make_report(
                    report_id=missing_id,
                    workspace_id=workspace_id,
                    version="2026-10-30",
                    generated_at=datetime(2026, 10, 30, tzinfo=UTC),
                ),
                _make_report(
                    report_id=withdrawn_id,
                    workspace_id=workspace_id,
                    version="2026-10-29",
                    status="withdrawn",
                    generated_at=datetime(2026, 10, 29, tzinfo=UTC),
                ),
                _make_report(
                    report_id=other_report_id,
                    workspace_id=other_workspace_id,
                    version="2026-10-31",
                ),
            ]
        )
        await session.flush()
        session.add(_make_content(ready_id))
        await session.commit()

    client.cookies.set("access_token", create_access_token(user_id))
    return SeededReport(
        workspace_id=workspace_id,
        user_id=user_id,
        ready_report_id=ready_id,
        missing_content_report_id=missing_id,
        withdrawn_report_id=withdrawn_id,
        other_workspace_report_id=other_report_id,
    )


async def test_analysis_types_reports_source_unavailable(client: AsyncClient) -> None:
    await _seed(client)

    response = await client.get("/api/insight/analysis-types")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["key"] == "tiktok_viral_topic"
    assert item["name"] == "TikTok 爆款选题分析"
    # withdrawn 不计入；ready + content_missing 共 2 条。
    assert item["report_count"] == 2
    assert item["latest_report_at"] == "2026-10-31T00:00:00Z"
    # 数据源未连接是产品声明，不是实时探测。
    assert item["generation"]["available"] is False
    assert item["generation"]["reason_code"] == "source_not_connected"
    assert "数据源未连接" in item["generation"]["reason"]
    assert response.headers["x-request-id"]


async def test_list_reports_returns_metadata_without_content(client: AsyncClient) -> None:
    seeded = await _seed(client)

    response = await client.get("/api/insight/reports")

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    assert len(body["items"]) == 2
    assert all("content_html" not in item for item in body["items"])
    ready = next(item for item in body["items"] if item["id"] == str(seeded.ready_report_id))
    assert ready["status"] == "ready"
    assert ready["has_content"] is True
    assert ready["content_format"] == "html"
    assert ready["content_bytes"] == len(REPORT_HTML.encode("utf-8"))
    assert ready["content_sha256"] == REPORT_SHA256
    assert ready["data_scope"]["sample_size"] == 288
    assert ready["data_scope"]["source"]["tables"][0]["schema"] == "raw"
    missing = next(
        item
        for item in body["items"]
        if item["id"] == str(seeded.missing_content_report_id)
    )
    assert missing["status"] == "content_missing"
    assert missing["has_content"] is False
    assert missing["content_sha256"] is None


async def test_list_reports_unknown_analysis_type_returns_empty(
    client: AsyncClient,
) -> None:
    await _seed(client)

    response = await client.get(
        "/api/insight/reports", params={"analysis_type": "not_registered"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


async def test_list_reports_cursor_pagination_and_invalid_cursor(
    client: AsyncClient,
) -> None:
    seeded = await _seed(client)
    # 再加两条 ready 报告，保证分页有下一页。
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        for index, version in enumerate(("2026-10-28", "2026-10-27"), start=1):
            report = _make_report(
                workspace_id=seeded.workspace_id,
                version=version,
                generated_at=datetime(2026, 10, 28 - index, tzinfo=UTC),
            )
            session.add(report)
            await session.flush()
            session.add(_make_content(report.id))
        await session.commit()

    first = await client.get("/api/insight/reports", params={"limit": 2})
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second = await client.get(
        "/api/insight/reports",
        params={"limit": 2, "cursor": first_body["next_cursor"]},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 2
    first_ids = {item["id"] for item in first_body["items"]}
    second_ids = {item["id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)

    invalid = await client.get(
        "/api/insight/reports", params={"cursor": "not-a-cursor"}
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"

    non_ascii = await client.get(
        "/api/insight/reports", params={"cursor": "游标"}
    )
    assert non_ascii.status_code == 422
    assert non_ascii.json()["code"] == "validation_error"

    invalid_limit = await client.get("/api/insight/reports", params={"limit": 51})
    assert invalid_limit.status_code == 422


async def test_get_report_returns_metadata(client: AsyncClient) -> None:
    seeded = await _seed(client)

    response = await client.get(f"/api/insight/reports/{seeded.ready_report_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(seeded.ready_report_id)
    assert body["title"] == "下周拍什么：288 条母婴爆款的选题报告"
    assert body["version"] == "2026-10-31"
    assert body["source_status"] == "snapshot_only"
    assert "content_html" not in body


async def test_get_report_not_found_for_unknown_cross_workspace_and_withdrawn(
    client: AsyncClient,
) -> None:
    seeded = await _seed(client)

    cases = (
        uuid.uuid4(),
        seeded.other_workspace_report_id,
        seeded.withdrawn_report_id,
    )
    for report_id in cases:
        response = await client.get(f"/api/insight/reports/{report_id}")
        assert response.status_code == 404
        assert response.json()["code"] == "insight_report_not_found"

    invalid = await client.get("/api/insight/reports/not-a-uuid")
    assert invalid.status_code == 422


async def test_content_returns_html_with_security_headers(client: AsyncClient) -> None:
    seeded = await _seed(client)

    response = await client.get(f"/api/insight/reports/{seeded.ready_report_id}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.text == REPORT_HTML
    assert response.headers["content-length"] == str(len(REPORT_HTML.encode("utf-8")))
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["content-security-policy"] == (
        "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "script-src 'none'; base-uri 'none'; form-action 'none'"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.headers["etag"] == f'"{REPORT_SHA256}"'
    assert response.headers["content-disposition"].startswith("inline;")
    assert "tiktok-viral-topic-2026-10-31.html" in response.headers[
        "content-disposition"
    ]


async def test_content_download_and_conditional_etag(client: AsyncClient) -> None:
    seeded = await _seed(client)

    download = await client.get(
        f"/api/insight/reports/{seeded.ready_report_id}/content",
        params={"download": 1},
    )
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")

    not_modified = await client.get(
        f"/api/insight/reports/{seeded.ready_report_id}/content",
        headers={"If-None-Match": f'"{REPORT_SHA256}"'},
    )
    assert not_modified.status_code == 304
    assert not_modified.content == b""


async def test_content_missing_returns_409(client: AsyncClient) -> None:
    seeded = await _seed(client)

    response = await client.get(
        f"/api/insight/reports/{seeded.missing_content_report_id}/content"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "报告正文未导入。",
        "code": "insight_report_content_missing",
    }


async def test_content_integrity_failure_returns_409_without_actual_hash(
    client: AsyncClient,
) -> None:
    seeded = await _seed(client)
    session_factory = client.session_factory  # type: ignore[attr-defined]
    tampered = "<!DOCTYPE html><html><body>tampered</body></html>"
    async with session_factory() as session:
        await session.execute(
            update(InsightReportContent)
            .where(InsightReportContent.report_id == seeded.ready_report_id)
            .values(content_html=tampered)
        )
        await session.commit()

    response = await client.get(f"/api/insight/reports/{seeded.ready_report_id}/content")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "insight_report_integrity_failed"
    assert body["detail"] == "报告正文校验失败。"
    actual_hash = hashlib.sha256(tampered.encode("utf-8")).hexdigest()
    assert actual_hash not in response.text
    assert REPORT_SHA256 not in response.text


async def test_insight_requires_auth_when_demo_mode_disabled(
    client: AsyncClient,
) -> None:
    await _seed(client)
    client.cookies.clear()
    settings = get_settings()
    original = settings.demo_mode
    settings.demo_mode = False
    try:
        response = await client.get("/api/insight/reports")
    finally:
        settings.demo_mode = original

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


async def test_post_reports_returns_405(client: AsyncClient) -> None:
    await _seed(client)

    response = await client.post("/api/insight/reports", json={})

    assert response.status_code == 405
