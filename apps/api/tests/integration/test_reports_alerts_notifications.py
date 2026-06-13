from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta

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

    audit_response = await client.get(f"/api/reports/{report['id']}/audit-events")
    assert audit_response.status_code == 200
    audit_events = audit_response.json()
    assert [event["event_type"] for event in audit_events] == ["generated"]
    assert audit_events[0]["from_status"] is None
    assert audit_events[0]["to_status"] == "generated"
    assert audit_events[0]["metadata"]["project_id"] == project_id

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

    share_response = await client.post(
        f"/api/reports/{report['id']}/audit-events",
        json={"event_type": "share_link_copied", "metadata": {"origin": "test"}},
    )
    assert share_response.status_code == 201
    assert share_response.json()["event_type"] == "share_link_copied"

    audit_after_send_response = await client.get(f"/api/reports/{report['id']}/audit-events")
    assert audit_after_send_response.status_code == 200
    audit_after_send = audit_after_send_response.json()
    assert [event["event_type"] for event in audit_after_send] == [
        "generated",
        "sent",
        "share_link_copied",
    ]
    sent_event = audit_after_send[1]
    assert sent_event["from_status"] == "generated"
    assert sent_event["to_status"] == "sent"

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
async def test_report_subscription_upsert_flow(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

    empty_response = await client.get("/api/reports/subscriptions")
    assert empty_response.status_code == 200
    assert empty_response.json() == []

    create_response = await client.put(
        "/api/reports/subscriptions",
        json={
            "project_id": project_id,
            "report_type": "daily",
            "schedule_time": "09:00",
            "timezone": "Asia/Shanghai",
            "channels": ["in_app", "email"],
            "enabled": True,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["project_id"] == project_id
    assert created["schedule_time"] == "09:00"
    assert created["channels"] == ["in_app", "email"]
    assert created["enabled"] is True
    assert created["next_run_at"] is not None
    assert created["last_sent_at"] is None
    assert created["latest_run"] is None

    run_response = await client.post(f"/api/reports/subscriptions/{created['id']}/run")
    assert run_response.status_code == 200
    executed = run_response.json()
    assert executed["id"] == created["id"]
    assert executed["last_sent_at"] is not None
    assert executed["latest_run"]["trigger_type"] == "manual"
    assert executed["latest_run"]["status"] == "partial_success"
    assert executed["latest_run"]["delivered_channels"] == ["in_app"]
    assert executed["latest_run"]["skipped_channels"] == {"email": "smtp_not_configured"}
    assert executed["latest_run"]["report_id"] is not None

    history_response = await client.get(f"/api/reports/subscriptions/{created['id']}/runs")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["id"] == executed["latest_run"]["id"]

    reports_response = await client.get(f"/api/reports?project_id={project_id}")
    assert reports_response.status_code == 200
    reports = reports_response.json()
    assert len(reports) == 1
    assert reports[0]["id"] == executed["latest_run"]["report_id"]

    retry_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/runs/{executed['latest_run']['id']}/retry"
    )
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["latest_run"]["id"] != executed["latest_run"]["id"]
    assert retried["latest_run"]["trigger_type"] == "retry"
    assert retried["latest_run"]["status"] == "failed"
    assert retried["latest_run"]["delivered_channels"] == []
    assert retried["latest_run"]["skipped_channels"] == {"email": "smtp_not_configured"}
    assert retried["latest_run"]["report_id"] == executed["latest_run"]["report_id"]

    history_after_retry_response = await client.get(
        f"/api/reports/subscriptions/{created['id']}/runs?limit=2"
    )
    assert history_after_retry_response.status_code == 200
    history_after_retry = history_after_retry_response.json()
    assert [item["id"] for item in history_after_retry] == [
        retried["latest_run"]["id"],
        executed["latest_run"]["id"],
    ]

    update_response = await client.put(
        "/api/reports/subscriptions",
        json={
            "project_id": project_id,
            "report_type": "daily",
            "schedule_time": "10:30",
            "timezone": "Asia/Shanghai",
            "channels": ["email"],
            "enabled": False,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["id"] == created["id"]
    assert updated["schedule_time"] == "10:30"
    assert updated["channels"] == ["email"]
    assert updated["enabled"] is False
    assert updated["next_run_at"] is None

    list_response = await client.get("/api/reports/subscriptions")
    assert list_response.status_code == 200
    subscriptions = list_response.json()
    assert len(subscriptions) == 1
    assert subscriptions[0]["id"] == created["id"]
    assert subscriptions[0]["latest_run"]["id"] == retried["latest_run"]["id"]

    success_subscription_response = await client.put(
        "/api/reports/subscriptions",
        json={
            "project_id": None,
            "report_type": "daily",
            "schedule_time": "08:15",
            "timezone": "Asia/Shanghai",
            "channels": ["in_app"],
            "enabled": True,
        },
    )
    assert success_subscription_response.status_code == 200
    success_subscription = success_subscription_response.json()
    success_run_response = await client.post(
        f"/api/reports/subscriptions/{success_subscription['id']}/run"
    )
    assert success_run_response.status_code == 200
    success_run = success_run_response.json()["latest_run"]
    assert success_run["status"] == "success"
    retry_success_response = await client.post(
        f"/api/reports/subscriptions/{success_subscription['id']}/runs/{success_run['id']}/retry"
    )
    assert retry_success_response.status_code == 409

    invalid_project_response = await client.put(
        "/api/reports/subscriptions",
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "report_type": "daily",
            "schedule_time": "09:00",
            "timezone": "Asia/Shanghai",
            "channels": ["in_app"],
            "enabled": True,
        },
    )
    assert invalid_project_response.status_code == 404

    invalid_run_response = await client.post(
        "/api/reports/subscriptions/00000000-0000-0000-0000-000000000000/run"
    )
    assert invalid_run_response.status_code == 404

    missing_history_response = await client.get(
        "/api/reports/subscriptions/00000000-0000-0000-0000-000000000000/runs"
    )
    assert missing_history_response.status_code == 404

    missing_retry_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/runs/"
        "00000000-0000-0000-0000-000000000000/retry"
    )
    assert missing_retry_response.status_code == 404


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


@pytest.mark.asyncio
async def test_report_generation_respects_custom_period(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)
    await trigger_star_growth_intelligence(client, project_id)

    now = datetime.now(UTC)
    empty_period_start = now - timedelta(days=3)
    empty_period_end = now - timedelta(days=2)
    report_response = await client.post(
        "/api/reports/generate",
        json={
            "project_id": project_id,
            "report_type": "daily",
            "period_start": empty_period_start.isoformat(),
            "period_end": empty_period_end.isoformat(),
        },
    )
    assert report_response.status_code == 201
    report = report_response.json()
    assert report["project_id"] == project_id
    assert report["period_start"] == empty_period_start.replace(tzinfo=None).isoformat()
    assert report["period_end"] == empty_period_end.replace(tzinfo=None).isoformat()
    assert "当前周期没有新增情报" in report["content"]

    invalid_response = await client.post(
        "/api/reports/generate",
        json={
            "project_id": project_id,
            "report_type": "daily",
            "period_start": now.isoformat(),
            "period_end": (now - timedelta(hours=1)).isoformat(),
        },
    )
    assert invalid_response.status_code == 422
