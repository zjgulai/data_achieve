from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base


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

    async def override_session() -> AsyncGenerator[object, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def register_and_create_project(client: AsyncClient) -> str:
    register_response = await client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "strong-password", "name": "Owner"},
    )
    assert register_response.status_code == 201

    project_response = await client.post(
        "/api/projects",
        json={
            "name": "AI Scrapy Tools",
            "description": "Track open-source scraping tools.",
            "domain": "osint",
        },
    )
    assert project_response.status_code == 201
    return str(project_response.json()["id"])


async def trigger_star_growth_intelligence(client: AsyncClient, project_id: str) -> str:
    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Manual Repo Metrics",
            "type": "manual_json",
            "config": {
                "entity_type": "github_repo",
                "json_data": {"full_name": "example/repo", "stars": 100},
            },
            "schedule_cron": None,
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()

    first_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert first_run_response.status_code == 201

    update_response = await client.patch(
        f"/api/sources/{source['id']}",
        json={
            "config": {
                "entity_type": "github_repo",
                "json_data": {"full_name": "example/repo", "stars": 360},
            }
        },
    )
    assert update_response.status_code == 200

    second_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert second_run_response.status_code == 201

    intelligence_response = await client.get("/api/intelligence")
    assert intelligence_response.status_code == 200
    intelligence_items = intelligence_response.json()
    assert len(intelligence_items) == 1
    return str(intelligence_items[0]["id"])


@pytest.mark.asyncio
async def test_alert_rule_matches_signal_and_creates_notification(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)

    rule_response = await client.post(
        "/api/alert-rules",
        json={
            "name": "High growth signal",
            "project_id": project_id,
            "signal_type": "*",
            "condition": {"field": "severity", "op": "in", "value": ["high", "critical"]},
            "channel": "in_app",
            "enabled": True,
        },
    )
    assert rule_response.status_code == 201
    rule = rule_response.json()

    intelligence_id = await trigger_star_growth_intelligence(client, project_id)

    events_response = await client.get(f"/api/alert-events?rule_id={rule['id']}")
    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 1
    assert events[0]["status"] == "sent"
    assert events[0]["payload"]["severity"] == "high"
    assert events[0]["payload"]["signal_type"] == "star_growth"

    notifications_response = await client.get("/api/notifications?is_read=false")
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert len(notifications) == 1
    assert notifications[0]["notification_type"] == "alert"
    assert notifications[0]["reference_type"] == "alert_event"
    assert notifications[0]["reference_id"] == events[0]["id"]

    dashboard_response = await client.get("/api/dashboard/overview")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["active_alerts"] == 1

    intelligence_detail_response = await client.get(f"/api/intelligence/{intelligence_id}")
    assert intelligence_detail_response.status_code == 200


@pytest.mark.asyncio
async def test_report_generation_send_and_notification_read_flow(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)
    intelligence_id = await trigger_star_growth_intelligence(client, project_id)

    report_response = await client.post(
        "/api/reports/generate",
        json={"project_id": project_id, "report_type": "daily"},
    )
    assert report_response.status_code == 201
    report = report_response.json()
    assert report["status"] == "generated"
    assert report["project_id"] == project_id
    assert "AI Scrapy Tools 日报" in report["title"]
    assert "example/repo" in report["content"]
    assert "证据数" in report["content"]
    assert intelligence_id in report["content"]

    list_response = await client.get(f"/api/reports?project_id={project_id}")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [report["id"]]

    references_response = await client.get(f"/api/reports/{report['id']}/evidence-references")
    assert references_response.status_code == 200
    references = references_response.json()
    assert [item["intelligence"]["id"] for item in references] == [intelligence_id]
    assert references[0]["intelligence"]["evidence_count"] >= 3
    evidence_types = {evidence["evidence_type"] for evidence in references[0]["evidences"]}
    assert {"signal", "snapshot", "raw_record"} <= evidence_types
    raw_evidence = next(
        evidence
        for evidence in references[0]["evidences"]
        if evidence["evidence_type"] == "raw_record"
    )
    assert raw_evidence["raw_record"]["content_preview"]["payload"]["stars"] == 360
    assert raw_evidence["task_run"]["status"] == "success"
    assert raw_evidence["source"]["name"] == "Manual Repo Metrics"

    send_response = await client.post(f"/api/reports/{report['id']}/send")
    assert send_response.status_code == 200
    sent_report = send_response.json()
    assert sent_report["status"] == "sent"

    notifications_response = await client.get("/api/notifications?is_read=false")
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert len(notifications) == 1
    assert notifications[0]["notification_type"] == "report_ready"
    assert notifications[0]["reference_type"] == "report"
    assert notifications[0]["reference_id"] == report["id"]

    read_response = await client.patch(f"/api/notifications/{notifications[0]['id']}/read")
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True

    read_all_response = await client.post("/api/notifications/read-all")
    assert read_all_response.status_code == 200
    assert read_all_response.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_report_includes_alert_events_from_same_period(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

    rule_response = await client.post(
        "/api/alert-rules",
        json={
            "name": "High growth signal",
            "project_id": project_id,
            "signal_type": "*",
            "condition": {"field": "severity", "op": "in", "value": ["high", "critical"]},
            "channel": "in_app",
            "enabled": True,
        },
    )
    assert rule_response.status_code == 201

    await trigger_star_growth_intelligence(client, project_id)

    report_response = await client.post(
        "/api/reports/generate",
        json={"project_id": project_id, "report_type": "daily"},
    )
    assert report_response.status_code == 201
    content = report_response.json()["content"]
    assert "## 预警区" in content
    assert "High growth signal" in content
    assert "star_growth" in content
    assert "severity=high" in content
