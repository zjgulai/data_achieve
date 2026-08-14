from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import Settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.services import notification_service
from data_intelligence_hub.services.notification_service import EmailDeliveryResult


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

    acknowledge_response = await client.patch(
        f"/api/alert-events/{events[0]['id']}/status",
        json={"status": "acknowledged"},
    )
    assert acknowledge_response.status_code == 200
    assert acknowledge_response.json()["status"] == "acknowledged"

    resolve_response = await client.patch(
        f"/api/alert-events/{events[0]['id']}/status",
        json={"status": "resolved"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"

    resolved_events_response = await client.get("/api/alert-events?status=resolved")
    assert resolved_events_response.status_code == 200
    assert [event["id"] for event in resolved_events_response.json()] == [events[0]["id"]]

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

    unconfirmed_send_response = await client.post(
        f"/api/reports/{report['id']}/send",
        json={"authorized": True, "confirm_send": False, "channels": ["in_app"]},
    )
    assert unconfirmed_send_response.status_code == 400
    assert unconfirmed_send_response.json()["detail"] == "report_send_confirmation_required"

    send_response = await client.post(
        f"/api/reports/{report['id']}/send",
        headers={"Idempotency-Key": "report-send-replay-001"},
        json={"authorized": True, "confirm_send": True, "channels": ["in_app"]},
    )
    assert send_response.status_code == 200
    sent_report = send_response.json()
    assert sent_report["status"] == "sent"
    assert sent_report["delivered_channels"] == ["in_app"]
    assert sent_report["skipped_channels"] == {}
    assert sent_report["idempotency_replayed"] is False
    assert sent_report["idempotency_scope"] == "report_send"
    send_key_hash = sent_report["idempotency_key_hash"]
    assert isinstance(send_key_hash, str)
    assert len(send_key_hash) == 64

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
        "idempotency_key_recorded",
        "share_link_copied",
    ]
    sent_event = audit_after_send[1]
    assert sent_event["from_status"] == "generated"
    assert sent_event["to_status"] == "sent"
    idempotency_event = audit_after_send[2]
    assert idempotency_event["metadata"]["scope"] == "report_send"
    assert idempotency_event["metadata"]["idempotency_key_hash"] == send_key_hash
    assert idempotency_event["metadata"]["raw_key_stored"] == "false"
    assert idempotency_event["metadata"]["delivered_channels"] == "in_app"
    assert "report-send-replay-001" not in str(idempotency_event["metadata"])

    notifications_response = await client.get("/api/notifications?is_read=false")
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert len(notifications) == 1
    assert notifications[0]["notification_type"] == "report_ready"
    assert notifications[0]["reference_type"] == "report"
    assert notifications[0]["reference_id"] == report["id"]

    second_send_response = await client.post(
        f"/api/reports/{report['id']}/send",
        headers={"Idempotency-Key": "report-send-replay-001"},
        json={"authorized": True, "confirm_send": True, "channels": ["in_app"]},
    )
    assert second_send_response.status_code == 200
    second_sent_report = second_send_response.json()
    assert second_sent_report["idempotency_replayed"] is True
    assert second_sent_report["idempotency_key_hash"] == send_key_hash
    assert second_sent_report["delivered_channels"] == ["in_app"]

    notifications_response = await client.get("/api/notifications?is_read=false")
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert len(notifications) == 1

    read_response = await client.patch(f"/api/notifications/{notifications[0]['id']}/read")
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True

    read_bulk_response = await client.post(
        "/api/notifications/read-bulk",
        json={"notification_ids": [notification["id"] for notification in notifications]},
    )
    assert read_bulk_response.status_code == 200
    assert read_bulk_response.json()["updated_count"] == 0

    read_all_response = await client.post("/api/notifications/read-all")
    assert read_all_response.status_code == 200
    assert read_all_response.json()["updated_count"] == 0


@pytest.mark.asyncio
async def test_email_channel_status_and_test_flow(client: AsyncClient) -> None:
    await register_and_create_project(client)

    status_response = await client.get("/api/notifications/email-channel")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "not_configured"
    assert status_payload["configured"] is False
    assert status_payload["reason"] == "smtp_not_configured"
    assert "SMTP_HOST" in status_payload["missing_settings"]
    assert status_payload["tls_mode"] == "starttls"

    unconfirmed_test_response = await client.post(
        "/api/notifications/email-channel/test",
        json={"authorized": True, "confirm_send": False},
    )
    assert unconfirmed_test_response.status_code == 400
    assert (
        unconfirmed_test_response.json()["detail"]
        == "email_channel_test_confirmation_required"
    )

    test_response = await client.post(
        "/api/notifications/email-channel/test",
        headers={"Idempotency-Key": "email-channel-test-replay-001"},
        json={"authorized": True, "confirm_send": True},
    )
    assert test_response.status_code == 200
    test_payload = test_response.json()
    assert test_payload["delivered"] is False
    assert test_payload["recipient_email"] == "owner@example.com"
    assert test_payload["reason"] == "smtp_not_configured"
    assert test_payload["status"]["configured"] is False
    assert test_payload["provider_call_attempted"] is False
    assert test_payload["idempotency_replayed"] is False
    assert test_payload["idempotency_scope"] == "email_channel_test"
    test_key_hash = test_payload["idempotency_key_hash"]
    assert isinstance(test_key_hash, str)
    assert len(test_key_hash) == 64
    assert "email-channel-test-replay-001" not in str(test_payload)

    replay_response = await client.post(
        "/api/notifications/email-channel/test",
        headers={"Idempotency-Key": "email-channel-test-replay-001"},
        json={"authorized": True, "confirm_send": True},
    )
    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["delivered"] is False
    assert replay_payload["recipient_email"] == "owner@example.com"
    assert replay_payload["tested_at"] == test_payload["tested_at"]
    assert replay_payload["provider_call_attempted"] is False
    assert replay_payload["idempotency_replayed"] is True
    assert replay_payload["idempotency_key_hash"] == test_key_hash


@pytest.mark.asyncio
async def test_email_provider_live_gate_preflight_is_fail_closed(
    client: AsyncClient,
) -> None:
    await register_and_create_project(client)

    unconfirmed_response = await client.post(
        "/api/notifications/email-channel/provider-live-gate",
        json={
            "authorized": True,
            "confirm_prepare": False,
            "operation": "email_channel_test",
        },
    )
    assert unconfirmed_response.status_code == 400
    assert (
        unconfirmed_response.json()["detail"]
        == "email_provider_live_gate_confirmation_required"
    )

    gate_response = await client.post(
        "/api/notifications/email-channel/provider-live-gate",
        headers={"Idempotency-Key": "email-provider-live-gate-replay-001"},
        json={
            "authorized": True,
            "confirm_prepare": True,
            "operation": "email_channel_test",
            "max_provider_calls": 1,
        },
    )
    assert gate_response.status_code == 200
    gate_payload = gate_response.json()
    assert gate_payload["operation"] == "email_channel_test"
    assert gate_payload["status"] == "blocked"
    assert gate_payload["recipient_email"] == "owner@example.com"
    assert gate_payload["channel_status"]["configured"] is False
    assert gate_payload["blocked_reasons"] == ["smtp_not_configured"]
    assert gate_payload["provider_call_allowed"] is False
    assert gate_payload["email_send_allowed"] is False
    assert gate_payload["production_write_allowed"] is False
    assert gate_payload["provider_call_attempted"] is False
    assert gate_payload["max_provider_calls"] == 1
    assert gate_payload["next_required_authorization"] == "L4_authorized_live_email_send"
    assert gate_payload["idempotency_replayed"] is False
    assert gate_payload["idempotency_scope"] == "email_provider_live_gate"
    gate_key_hash = gate_payload["idempotency_key_hash"]
    assert isinstance(gate_key_hash, str)
    assert len(gate_key_hash) == 64
    assert "email-provider-live-gate-replay-001" not in str(gate_payload)

    replay_response = await client.post(
        "/api/notifications/email-channel/provider-live-gate",
        headers={"Idempotency-Key": "email-provider-live-gate-replay-001"},
        json={
            "authorized": True,
            "confirm_prepare": True,
            "operation": "email_channel_test",
            "max_provider_calls": 1,
        },
    )
    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["id"] == gate_payload["id"]
    assert replay_payload["prepared_at"] == gate_payload["prepared_at"]
    assert replay_payload["provider_call_attempted"] is False
    assert replay_payload["idempotency_replayed"] is True
    assert replay_payload["idempotency_key_hash"] == gate_key_hash


@pytest.mark.asyncio
async def test_email_provider_live_send_gate_defaults_to_deny(
    client: AsyncClient,
) -> None:
    await register_and_create_project(client)

    readiness_response = await client.get(
        "/api/notifications/email-channel/live-send-readiness"
    )
    assert readiness_response.status_code == 200
    readiness_payload = readiness_response.json()
    assert readiness_payload["status"] == "blocked"
    assert readiness_payload["send_enabled"] is False
    assert readiness_payload["live_approval_required"] is True
    assert readiness_payload["recipient_allowlist_configured"] is False
    assert readiness_payload["recipient_allowlist_count"] == 0
    assert readiness_payload["provider_call_allowed"] is False
    assert readiness_payload["email_send_allowed"] is False
    assert readiness_payload["production_write_allowed"] is False
    assert readiness_payload["provider_call_attempted"] is False
    assert readiness_payload["required_authorization"] == "L4_authorized_live_email_send"
    assert "email_live_send_disabled" in readiness_payload["blocked_reasons"]
    assert "recipient_allowlist_empty" in readiness_payload["blocked_reasons"]
    assert "smtp_not_configured" in readiness_payload["blocked_reasons"]
    assert "Idempotency-Key" in readiness_payload["required_request_fields"]

    gate_response = await client.post(
        "/api/notifications/email-channel/provider-live-gate",
        headers={"Idempotency-Key": "email-live-send-default-gate-001"},
        json={
            "authorized": True,
            "confirm_prepare": True,
            "operation": "email_channel_test",
            "max_provider_calls": 1,
        },
    )
    assert gate_response.status_code == 200
    gate_payload = gate_response.json()

    missing_key_response = await client.post(
        "/api/notifications/email-channel/live-send",
        json={
            "authorized": True,
            "confirm_send": True,
            "gate_run_id": gate_payload["id"],
            "approval_id": "manual-approval-local-001",
            "operation": "email_channel_test",
        },
    )
    assert missing_key_response.status_code == 400
    assert (
        missing_key_response.json()["detail"]
        == "email_provider_live_send_idempotency_key_required"
    )

    send_response = await client.post(
        "/api/notifications/email-channel/live-send",
        headers={"Idempotency-Key": "email-live-send-default-replay-001"},
        json={
            "authorized": True,
            "confirm_send": True,
            "gate_run_id": gate_payload["id"],
            "approval_id": "manual-approval-local-001",
            "operation": "email_channel_test",
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["gate_run_id"] == gate_payload["id"]
    assert send_payload["approval_id"] == "manual-approval-local-001"
    assert send_payload["status"] == "blocked"
    assert send_payload["delivered"] is False
    assert send_payload["send_enabled"] is False
    assert send_payload["live_approval_required"] is True
    assert send_payload["recipient_allowlisted"] is False
    assert send_payload["provider_call_allowed"] is False
    assert send_payload["email_send_allowed"] is False
    assert send_payload["production_write_allowed"] is False
    assert send_payload["provider_call_attempted"] is False
    assert "email_live_send_disabled" in send_payload["blocked_reasons"]
    assert "recipient_not_allowlisted" in send_payload["blocked_reasons"]
    assert "smtp_not_configured" in send_payload["blocked_reasons"]
    assert "provider_live_gate_not_ready" in send_payload["blocked_reasons"]
    assert send_payload["idempotency_replayed"] is False
    assert send_payload["idempotency_scope"] == "email_provider_live_send"
    send_key_hash = send_payload["idempotency_key_hash"]
    assert isinstance(send_key_hash, str)
    assert len(send_key_hash) == 64
    assert "email-live-send-default-replay-001" not in str(send_payload)

    replay_response = await client.post(
        "/api/notifications/email-channel/live-send",
        headers={"Idempotency-Key": "email-live-send-default-replay-001"},
        json={
            "authorized": True,
            "confirm_send": True,
            "gate_run_id": gate_payload["id"],
            "approval_id": "manual-approval-local-001",
            "operation": "email_channel_test",
        },
    )
    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["id"] == send_payload["id"]
    assert replay_payload["sent_at"] == send_payload["sent_at"]
    assert replay_payload["provider_call_attempted"] is False
    assert replay_payload["idempotency_replayed"] is True
    assert replay_payload["idempotency_key_hash"] == send_key_hash


@pytest.mark.asyncio
async def test_email_provider_live_send_gate_fake_sender_replays_without_provider_call(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        smtp_host="smtp.example.test",
        smtp_from="noreply@example.test",
        email_live_send_enabled=True,
        email_live_recipient_allowlist=["owner@example.com"],
        email_live_approval_required=True,
    )
    monkeypatch.setattr(notification_service, "get_settings", lambda: settings)
    send_calls: list[tuple[str, str, str]] = []

    async def fake_sender(
        recipient_email: str,
        subject: str,
        body: str,
    ) -> EmailDeliveryResult:
        send_calls.append((recipient_email, subject, body))
        return EmailDeliveryResult(delivered=True)

    monkeypatch.setattr(notification_service, "send_email_notification", fake_sender)

    await register_and_create_project(client)
    readiness_response = await client.get(
        "/api/notifications/email-channel/live-send-readiness"
    )
    assert readiness_response.status_code == 200
    readiness_payload = readiness_response.json()
    assert readiness_payload["status"] == "ready_pending_l4_authorization"
    assert readiness_payload["blocked_reasons"] == []
    assert readiness_payload["send_enabled"] is True
    assert readiness_payload["live_approval_required"] is True
    assert readiness_payload["recipient_allowlist_configured"] is True
    assert readiness_payload["recipient_allowlist_count"] == 1
    assert readiness_payload["channel_status"]["configured"] is True
    assert readiness_payload["provider_call_allowed"] is False
    assert readiness_payload["email_send_allowed"] is False
    assert readiness_payload["production_write_allowed"] is False
    assert readiness_payload["provider_call_attempted"] is False

    gate_response = await client.post(
        "/api/notifications/email-channel/provider-live-gate",
        headers={"Idempotency-Key": "email-live-send-fake-gate-001"},
        json={
            "authorized": True,
            "confirm_prepare": True,
            "operation": "email_channel_test",
            "max_provider_calls": 1,
        },
    )
    assert gate_response.status_code == 200
    gate_payload = gate_response.json()
    assert gate_payload["status"] == "ready_pending_live_authorization"

    send_response = await client.post(
        "/api/notifications/email-channel/live-send",
        headers={"Idempotency-Key": "email-live-send-fake-replay-001"},
        json={
            "authorized": True,
            "confirm_send": True,
            "gate_run_id": gate_payload["id"],
            "approval_id": "manual-approval-local-002",
            "operation": "email_channel_test",
        },
    )
    assert send_response.status_code == 200
    send_payload = send_response.json()
    assert send_payload["status"] == "sent"
    assert send_payload["delivered"] is True
    assert send_payload["blocked_reasons"] == []
    assert send_payload["send_enabled"] is True
    assert send_payload["recipient_allowlisted"] is True
    assert send_payload["provider_call_allowed"] is True
    assert send_payload["email_send_allowed"] is True
    assert send_payload["production_write_allowed"] is False
    assert send_payload["provider_call_attempted"] is True
    assert len(send_calls) == 1
    assert send_calls[0][0] == "owner@example.com"

    replay_response = await client.post(
        "/api/notifications/email-channel/live-send",
        headers={"Idempotency-Key": "email-live-send-fake-replay-001"},
        json={
            "authorized": True,
            "confirm_send": True,
            "gate_run_id": gate_payload["id"],
            "approval_id": "manual-approval-local-002",
            "operation": "email_channel_test",
        },
    )
    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["id"] == send_payload["id"]
    assert replay_payload["provider_call_attempted"] is False
    assert replay_payload["idempotency_replayed"] is True
    assert len(send_calls) == 1


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

    unconfirmed_run_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/run",
        json={"authorized": True, "confirm_run": False},
    )
    assert unconfirmed_run_response.status_code == 400
    assert (
        unconfirmed_run_response.json()["detail"]
        == "report_subscription_run_confirmation_required"
    )

    run_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/run",
        headers={"Idempotency-Key": "report-subscription-run-replay-001"},
        json={"authorized": True, "confirm_run": True},
    )
    assert run_response.status_code == 200
    executed = run_response.json()
    assert executed["id"] == created["id"]
    assert executed["last_sent_at"] is not None
    assert executed["latest_run"]["trigger_type"] == "manual"
    assert executed["latest_run"]["status"] == "partial_success"
    assert executed["latest_run"]["delivered_channels"] == ["in_app"]
    assert executed["latest_run"]["skipped_channels"] == {"email": "smtp_not_configured"}
    assert executed["latest_run"]["report_id"] is not None
    assert executed["latest_run"]["idempotency_replayed"] is False
    assert executed["latest_run"]["idempotency_scope"] == "report_subscription_run"
    run_key_hash = executed["latest_run"]["idempotency_key_hash"]
    assert isinstance(run_key_hash, str)
    assert len(run_key_hash) == 64

    replay_run_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/run",
        headers={"Idempotency-Key": "report-subscription-run-replay-001"},
        json={"authorized": True, "confirm_run": True},
    )
    assert replay_run_response.status_code == 200
    replayed_run = replay_run_response.json()
    assert replayed_run["latest_run"]["id"] == executed["latest_run"]["id"]
    assert replayed_run["latest_run"]["idempotency_replayed"] is True
    assert replayed_run["latest_run"]["idempotency_key_hash"] == run_key_hash

    run_audit_response = await client.get(
        f"/api/reports/{executed['latest_run']['report_id']}/audit-events"
    )
    assert run_audit_response.status_code == 200
    run_audit_events = run_audit_response.json()
    assert "report-subscription-run-replay-001" not in str(run_audit_events)
    run_idempotency_events = [
        event
        for event in run_audit_events
        if event["event_type"] == "idempotency_key_recorded"
        and event["metadata"]["scope"] == "report_subscription_run"
    ]
    assert len(run_idempotency_events) == 1
    assert run_idempotency_events[0]["metadata"]["idempotency_key_hash"] == run_key_hash
    assert run_idempotency_events[0]["metadata"]["raw_key_stored"] == "false"

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
        f"/api/reports/subscriptions/{created['id']}/runs/{executed['latest_run']['id']}/retry",
        headers={"Idempotency-Key": "report-subscription-retry-replay-001"},
        json={"authorized": True, "confirm_retry": True},
    )
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["latest_run"]["id"] != executed["latest_run"]["id"]
    assert retried["latest_run"]["trigger_type"] == "retry"
    assert retried["latest_run"]["status"] == "failed"
    assert retried["latest_run"]["delivered_channels"] == []
    assert retried["latest_run"]["skipped_channels"] == {"email": "smtp_not_configured"}
    assert retried["latest_run"]["report_id"] == executed["latest_run"]["report_id"]
    assert retried["latest_run"]["idempotency_replayed"] is False
    assert retried["latest_run"]["idempotency_scope"] == "report_subscription_retry"
    retry_key_hash = retried["latest_run"]["idempotency_key_hash"]
    assert isinstance(retry_key_hash, str)
    assert len(retry_key_hash) == 64

    replay_retry_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/runs/{executed['latest_run']['id']}/retry",
        headers={"Idempotency-Key": "report-subscription-retry-replay-001"},
        json={"authorized": True, "confirm_retry": True},
    )
    assert replay_retry_response.status_code == 200
    replayed_retry = replay_retry_response.json()
    assert replayed_retry["latest_run"]["id"] == retried["latest_run"]["id"]
    assert replayed_retry["latest_run"]["idempotency_replayed"] is True
    assert replayed_retry["latest_run"]["idempotency_key_hash"] == retry_key_hash

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
        f"/api/reports/subscriptions/{success_subscription['id']}/run",
        json={"authorized": True, "confirm_run": True},
    )
    assert success_run_response.status_code == 200
    success_run = success_run_response.json()["latest_run"]
    assert success_run["status"] == "success"
    retry_success_response = await client.post(
        f"/api/reports/subscriptions/{success_subscription['id']}/runs/{success_run['id']}/retry",
        json={"authorized": True, "confirm_retry": True},
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
        "/api/reports/subscriptions/00000000-0000-0000-0000-000000000000/run",
        json={"authorized": True, "confirm_run": True},
    )
    assert invalid_run_response.status_code == 404

    missing_history_response = await client.get(
        "/api/reports/subscriptions/00000000-0000-0000-0000-000000000000/runs"
    )
    assert missing_history_response.status_code == 404

    missing_retry_response = await client.post(
        f"/api/reports/subscriptions/{created['id']}/runs/"
        "00000000-0000-0000-0000-000000000000/retry",
        json={"authorized": True, "confirm_retry": True},
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
