from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.collectors import registry as collector_registry
from data_intelligence_hub.collectors.base import CollectionResult, CollectorError
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector
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


@pytest.mark.asyncio
async def test_collectors_are_available(client: AsyncClient) -> None:
    response = await client.get("/api/collectors")

    assert response.status_code == 200
    collector_types = {collector["type"] for collector in response.json()}
    assert collector_types == {"github_repo", "github_topic", "generic_web", "manual_json"}


@pytest.mark.asyncio
async def test_source_rejects_invalid_config(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

    response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Broken repo",
            "type": "github_repo",
            "config": {"owner": "openai"},
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_source_update_syncs_derived_url_and_task_config(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "OpenAI Codex",
            "type": "github_repo",
            "config": {"owner": "openai", "repo": "codex"},
            "schedule_cron": "0 8 * * *",
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()

    update_response = await client.patch(
        f"/api/sources/{source['id']}",
        json={
            "name": "MCP Python SDK",
            "config": {"owner": "modelcontextprotocol", "repo": "python-sdk"},
            "schedule_cron": "0 */1 * * *",
        },
    )
    assert update_response.status_code == 200
    updated_source = update_response.json()
    assert updated_source["name"] == "MCP Python SDK"
    assert updated_source["url"] == "https://github.com/modelcontextprotocol/python-sdk"
    assert updated_source["config"] == {
        "owner": "modelcontextprotocol",
        "repo": "python-sdk",
    }

    task_response = await client.get(f"/api/tasks/{task['id']}")
    assert task_response.status_code == 200
    updated_task = task_response.json()
    assert updated_task["name"] == "MCP Python SDK"
    assert updated_task["schedule_cron"] == "0 */1 * * *"
    assert updated_task["config"] == {
        "owner": "modelcontextprotocol",
        "repo": "python-sdk",
    }


@pytest.mark.asyncio
async def test_source_enable_disable_manual_task_run_and_raw_record_listing(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Manual Product JSON",
            "type": "manual_json",
            "config": {
                "entity_type": "product",
                "json_data": {"name": "Demo Product", "price": 99},
            },
            "schedule_cron": "0 8 * * *",
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()
    assert source["enabled"] is False
    assert source["url"] is None

    test_response = await client.post(f"/api/sources/{source['id']}/test")
    assert test_response.status_code == 200
    assert test_response.json()["status"] == "config_valid"

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()
    assert task["status"] == "enabled"
    assert task["source_id"] == source["id"]

    run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "success"
    assert run["records_count"] == 1
    assert run["entities_count"] == 1
    assert run["error_message"] is None
    assert {log["step"] for log in run["logs"]} >= {
        "manual_json_collected",
        "raw_records_stored",
    }

    raw_records_response = await client.get("/api/raw-records")
    assert raw_records_response.status_code == 200
    raw_records = raw_records_response.json()
    assert len(raw_records) == 1
    assert raw_records[0]["task_run_id"] == run["id"]
    assert raw_records[0]["record_type"] == "manual_json"
    assert raw_records[0]["content"]["payload"]["name"] == "Demo Product"

    entities_response = await client.get("/api/entities")
    assert entities_response.status_code == 200
    entities = entities_response.json()
    assert len(entities) == 1
    entity = entities[0]
    assert entity["entity_type"] == "product"
    assert entity["external_id"] == "Demo Product"
    assert entity["latest_snapshot_id"] is not None

    snapshots_response = await client.get(f"/api/entities/{entity['id']}/snapshots")
    assert snapshots_response.status_code == 200
    snapshots = snapshots_response.json()
    assert len(snapshots) == 1
    assert snapshots[0]["raw_record_id"] == raw_records[0]["id"]
    assert snapshots[0]["metrics"]["price"] == 99
    assert snapshots[0]["snapshot_data"]["name"] == "Demo Product"

    duplicate_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert duplicate_run_response.status_code == 201
    duplicate_run = duplicate_run_response.json()
    assert duplicate_run["status"] == "success"
    assert duplicate_run["records_count"] == 0
    assert duplicate_run["entities_count"] == 0
    assert "raw_record_deduplicated" in {log["step"] for log in duplicate_run["logs"]}
    assert "task_status_running" in {log["step"] for log in duplicate_run["logs"]}
    assert "task_status_restored" in {log["step"] for log in duplicate_run["logs"]}

    task_response = await client.get(f"/api/tasks/{task['id']}")
    assert task_response.status_code == 200
    assert task_response.json()["status"] == "enabled"

    runs_response = await client.get(f"/api/tasks/{task['id']}/runs")
    assert runs_response.status_code == 200
    assert [item["id"] for item in runs_response.json()] == [
        duplicate_run["id"],
        run["id"],
    ]

    pause_response = await client.post(f"/api/tasks/{task['id']}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    blocked_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert blocked_run_response.status_code == 409
    assert blocked_run_response.json()["detail"] == "Task is not enabled"

    resume_response = await client.post(f"/api/tasks/{task['id']}/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "enabled"

    disable_response = await client.post(f"/api/sources/{source['id']}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    tasks_response = await client.get("/api/tasks?status=disabled")
    assert tasks_response.status_code == 200
    assert [item["id"] for item in tasks_response.json()] == [task["id"]]


@pytest.mark.asyncio
async def test_collector_exception_persists_failed_task_run(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingManualJsonCollector(ManualJsonCollector):
        async def collect(self) -> CollectionResult:
            raise CollectorError("fixture_collector_failure")

    monkeypatch.setitem(
        collector_registry.COLLECTOR_REGISTRY,
        "manual_json",
        FailingManualJsonCollector,
    )
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Failing Manual JSON",
            "type": "manual_json",
            "config": {"entity_type": "product", "json_data": {"name": "Demo"}},
            "schedule_cron": None,
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()

    run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "failed"
    assert run["error_message"] == "fixture_collector_failure"
    assert "collector_failed" in {log["step"] for log in run["logs"]}

    runs_response = await client.get(f"/api/tasks/{task['id']}/runs")
    assert runs_response.status_code == 200
    assert [item["id"] for item in runs_response.json()] == [run["id"]]

    dashboard_response = await client.get("/api/dashboard/overview")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["source_count"] == 1
    assert dashboard["recent_runs"] == 1
    assert dashboard["task_success_rate"] == 0
    assert dashboard["failed_tasks"] == 1
    assert dashboard["task_health"]["recent_failures"][0]["task_id"] == task["id"]


@pytest.mark.asyncio
async def test_star_growth_signal_is_created_from_snapshot_delta(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

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
    assert first_run_response.json()["entities_count"] == 1

    update_response = await client.patch(
        f"/api/sources/{source['id']}",
        json={
            "config": {
                "entity_type": "github_repo",
                "json_data": {"full_name": "example/repo", "stars": 260},
            }
        },
    )
    assert update_response.status_code == 200

    second_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert second_run_response.status_code == 201
    second_run = second_run_response.json()
    assert second_run["entities_count"] == 1
    assert "signals_detected" in {log["step"] for log in second_run["logs"]}

    signals_response = await client.get("/api/signals?type=star_growth")
    assert signals_response.status_code == 200
    signals = signals_response.json()
    assert len(signals) == 1
    signal = signals[0]
    assert signal["signal_type"] == "star_growth"
    assert signal["previous_value"] == 100
    assert signal["current_value"] == 260
    assert signal["delta"] == 160
    assert signal["previous_snapshot_id"] != signal["current_snapshot_id"]

    entity_signals_response = await client.get(f"/api/entities/{signal['entity_id']}/signals")
    assert entity_signals_response.status_code == 200
    assert [item["id"] for item in entity_signals_response.json()] == [signal["id"]]

    snapshot_compare_response = await client.get(
        f"/api/signals/{signal['id']}/snapshot-compare"
    )
    assert snapshot_compare_response.status_code == 200
    snapshot_compare = snapshot_compare_response.json()
    assert snapshot_compare["signal_id"] == signal["id"]
    assert snapshot_compare["previous_snapshot"]["metrics"]["stars"] == 100
    assert snapshot_compare["current_snapshot"]["metrics"]["stars"] == 260
    stars_diff = next(
        item for item in snapshot_compare["metrics_diff"] if item["metric"] == "stars"
    )
    assert stars_diff["delta"] == 160
    assert stars_diff["delta_ratio"] == 1.6

    intelligence_response = await client.get("/api/intelligence?type=trend")
    assert intelligence_response.status_code == 200
    intelligence_items = intelligence_response.json()
    assert len(intelligence_items) == 1
    intelligence = intelligence_items[0]
    assert intelligence["intelligence_type"] == "trend"
    assert intelligence["status"] == "new"
    assert intelligence["final_score"] > 0
    assert intelligence["evidence_count"] >= 3
    assert "example/repo" in intelligence["title"]

    evidences_response = await client.get(f"/api/intelligence/{intelligence['id']}/evidences")
    assert evidences_response.status_code == 200
    evidences = evidences_response.json()
    evidence_types = {evidence["evidence_type"] for evidence in evidences}
    assert {"signal", "snapshot", "raw_record"} <= evidence_types
    assert any(evidence["signal_id"] == signal["id"] for evidence in evidences)
    assert all("screenshot_url" in evidence for evidence in evidences)
    signal_evidence = next(evidence for evidence in evidences if evidence["signal"] is not None)
    assert signal_evidence["signal"]["id"] == signal["id"]
    assert signal_evidence["signal"]["current_value"] == 260
    assert signal_evidence["entity"]["name"] == "example/repo"
    raw_evidence = next(
        evidence for evidence in evidences if evidence["evidence_type"] == "raw_record"
    )
    assert raw_evidence["raw_record"]["task_run_id"] == second_run["id"]
    assert raw_evidence["raw_record"]["content_preview"]["payload"]["stars"] == 260
    reference_metadata = raw_evidence["reference_metadata"]
    assert reference_metadata["content_hash"] == raw_evidence["raw_record"]["content_hash"]
    assert "$.content.payload.full_name" in raw_evidence["reference_metadata"]["json_paths"]
    assert reference_metadata["text_reference"]["path"] == "$.content.payload.full_name"
    assert reference_metadata["text_reference"]["quote"] == "example/repo"
    assert raw_evidence["task_run"]["id"] == second_run["id"]
    assert raw_evidence["task_run"]["status"] == "success"
    assert raw_evidence["source"]["name"] == "Manual Repo Metrics"

    status_response = await client.patch(
        f"/api/intelligence/{intelligence['id']}/status",
        json={"status": "reviewed"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "reviewed"

    feedback_response = await client.post(
        f"/api/intelligence/{intelligence['id']}/feedback",
        json={"feedback_type": "useful", "comment": "Validated from raw record."},
    )
    assert feedback_response.status_code == 201
    assert feedback_response.json()["feedback_type"] == "useful"

    dashboard_response = await client.get("/api/dashboard/overview?domain=osint&limit=5")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["intelligence_count"] == 1
    assert dashboard["task_success_rate"] == 100
    assert dashboard["field_completeness"] == 100
    assert dashboard["source_count"] == 1
    assert dashboard["recent_runs"] == 2
    assert dashboard["failed_tasks"] == 0
    assert dashboard["type_breakdown"][0]["type"] == "trend"
    assert dashboard["type_breakdown"][0]["count"] == 1
    assert dashboard["domain_breakdown"][0]["domain"] == "osint"
    assert dashboard["domain_breakdown"][0]["intelligence_count"] == 1
    assert dashboard["domain_breakdown"][0]["signal_count"] == 1
    assert dashboard["top_intelligence"][0]["id"] == intelligence["id"]
