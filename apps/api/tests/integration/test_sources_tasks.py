from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.collectors import registry as collector_registry
from data_intelligence_hub.collectors.base import (
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
)
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
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
    assert collector_types == {
        "github_repo",
        "github_topic",
        "generic_web",
        "manual_json",
        "ecommerce_product_discovery",
        "ecommerce_product_page",
    }


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

    tasks_response = await client.get("/api/tasks?status=enabled")
    assert tasks_response.status_code == 200
    listed_task = tasks_response.json()[0]
    assert listed_task["id"] == task["id"]
    assert listed_task["project_name"] == "AI Scrapy Tools"
    assert listed_task["project_domain"] == "osint"
    assert listed_task["source_name"] == "Manual Product JSON"
    assert listed_task["source_url"] is None
    assert listed_task["schedule_policy"] == "manual_refresh_only"
    assert listed_task["freshness_target_hours"] == 24
    assert listed_task["freshness_status"] == "fresh"
    assert listed_task["stale_hours"] == 0
    assert listed_task["next_run_at"] is not None
    assert listed_task["retry_after_at"] is None
    assert listed_task["retry_delay_minutes"] == 15
    assert listed_task["latest_run_status"] == duplicate_run["status"]
    assert listed_task["latest_run_error_message"] is None
    assert listed_task["latest_run_records_count"] == duplicate_run["records_count"]
    assert listed_task["latest_run_entities_count"] == duplicate_run["entities_count"]
    assert listed_task["latest_run_started_at"] == duplicate_run["started_at"]
    assert listed_task["latest_run_finished_at"] == duplicate_run["finished_at"]
    assert listed_task["latest_run_created_at"] == duplicate_run["created_at"]

    runs_response = await client.get(f"/api/tasks/{task['id']}/runs")
    assert runs_response.status_code == 200
    assert [item["id"] for item in runs_response.json()] == [
        duplicate_run["id"],
        run["id"],
    ]

    scheduler_response = await client.get("/api/tasks/scheduler/overview")
    assert scheduler_response.status_code == 200
    scheduler_overview = scheduler_response.json()
    assert scheduler_overview["enabled"] is False
    assert scheduler_overview["latest_tick"] is None

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
async def test_ecommerce_product_page_source_runs_into_product_entity(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureEcommerceCollector(EcommerceProductPageCollector):
        async def collect(self) -> CollectionResult:
            return CollectionResult(
                raw_records=[
                    CollectorRawRecord(
                        record_type="ecommerce_product_page",
                        source_url="https://shop.example/products/demo-bag",
                        content={
                            "provider": "ecommerce",
                            "kind": "product_page",
                            "url": "https://shop.example/products/demo-bag",
                            "extracted_fields": {
                                "title": "Demo Carry Bag",
                                "price": 129.9,
                                "currency": "USD",
                                "sku": "BAG-001",
                                "canonical_url": "https://shop.example/products/demo-bag",
                            },
                            "field_schema": [],
                            "cleaning_plan": [],
                            "platform_profile": {"platform_type": "shopify"},
                            "page_structure": {"page_type": "product_detail"},
                        },
                    )
                ],
                logs=[],
                errors=[],
            )

    monkeypatch.setitem(
        collector_registry.COLLECTOR_REGISTRY,
        "ecommerce_product_page",
        FixtureEcommerceCollector,
    )
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Demo Product Page",
            "type": "ecommerce_product_page",
            "config": {
                "url": "https://shop.example/products/demo-bag",
                "fields": ["title", "price", "currency", "sku", "canonical_url"],
                "platform_hint": "shopify",
            },
            "schedule_cron": None,
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()
    assert source["url"] == "https://shop.example/products/demo-bag"

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()
    assert task["collector_type"] == "ecommerce_product_page"

    run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "success"
    assert run["records_count"] == 1
    assert run["entities_count"] == 1

    raw_records_response = await client.get("/api/raw-records")
    assert raw_records_response.status_code == 200
    raw_record = raw_records_response.json()[0]
    assert raw_record["record_type"] == "ecommerce_product_page"
    assert raw_record["content"]["extracted_fields"]["sku"] == "BAG-001"

    entities_response = await client.get("/api/entities")
    assert entities_response.status_code == 200
    entity = entities_response.json()[0]
    assert entity["entity_type"] == "product"
    assert entity["external_id"] == "BAG-001"

    snapshots_response = await client.get(f"/api/entities/{entity['id']}/snapshots")
    assert snapshots_response.status_code == 200
    snapshot = snapshots_response.json()[0]
    assert snapshot["metrics"]["price"] == 129.9
    assert snapshot["snapshot_data"]["extracted_fields"]["title"] == "Demo Carry Bag"


@pytest.mark.asyncio
async def test_ecommerce_product_discovery_source_runs_into_product_catalog_entity(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureEcommerceDiscoveryCollector(EcommerceProductDiscoveryCollector):
        async def collect(self) -> CollectionResult:
            return CollectionResult(
                raw_records=[
                    CollectorRawRecord(
                        record_type="ecommerce_product_discovery",
                        source_url="https://shop.example/collections/summer-bags",
                        content={
                            "provider": "ecommerce",
                            "kind": "product_discovery",
                            "url": "https://shop.example/collections/summer-bags",
                            "platform_profile": {
                                "platform_type": "shopify",
                                "confidence": 0.89,
                                "indicators": ["product URL pattern"],
                                "risk_level": "low",
                            },
                            "page_structure": {
                                "page_type": "collection_listing",
                                "title": "Summer Bags",
                                "canonical_url": "https://shop.example/collections/summer-bags",
                                "link_count": 12,
                                "product_link_count": 2,
                                "jsonld_url_count": 1,
                                "sitemap_url_count": 0,
                                "script_count": 4,
                                "text_sample": "Summer Bags Demo Carry Bag Weekend Tote",
                            },
                            "product_candidates": [
                                {
                                    "url": "https://shop.example/products/demo-bag",
                                    "title": "Demo Carry Bag",
                                    "source": "json_ld",
                                    "confidence": 0.9,
                                },
                                {
                                    "url": "https://shop.example/products/weekend-tote",
                                    "title": "Weekend Tote",
                                    "source": "anchor",
                                    "confidence": 0.86,
                                },
                            ],
                            "tool_recommendations": [],
                            "discovery_plan": {
                                "next_collector_type": "ecommerce_product_page",
                                "candidate_count": 2,
                                "max_products": 50,
                                "fan_out_requires_review": True,
                            },
                        },
                    )
                ],
                logs=[],
                errors=[],
            )

    monkeypatch.setitem(
        collector_registry.COLLECTOR_REGISTRY,
        "ecommerce_product_discovery",
        FixtureEcommerceDiscoveryCollector,
    )
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Summer Bags Discovery",
            "type": "ecommerce_product_discovery",
            "config": {
                "url": "https://shop.example/collections/summer-bags",
                "max_products": 50,
                "platform_hint": "auto",
            },
            "schedule_cron": None,
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()
    assert source["url"] == "https://shop.example/collections/summer-bags"

    enable_response = await client.post(f"/api/sources/{source['id']}/enable")
    assert enable_response.status_code == 200
    task = enable_response.json()
    assert task["collector_type"] == "ecommerce_product_discovery"

    run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "success"
    assert run["records_count"] == 1
    assert run["entities_count"] == 1

    raw_records_response = await client.get("/api/raw-records")
    assert raw_records_response.status_code == 200
    raw_record = raw_records_response.json()[0]
    assert raw_record["record_type"] == "ecommerce_product_discovery"
    assert len(raw_record["content"]["product_candidates"]) == 2

    entities_response = await client.get("/api/entities")
    assert entities_response.status_code == 200
    entity = entities_response.json()[0]
    assert entity["entity_type"] == "product_catalog"
    assert entity["external_id"] == "https://shop.example/collections/summer-bags"

    snapshots_response = await client.get(f"/api/entities/{entity['id']}/snapshots")
    assert snapshots_response.status_code == 200
    snapshot = snapshots_response.json()[0]
    assert snapshot["metrics"]["candidate_count"] == 2
    assert snapshot["metrics"]["product_link_count"] == 2
    assert snapshot["snapshot_data"]["discovery_plan"]["next_collector_type"] == (
        "ecommerce_product_page"
    )


@pytest.mark.asyncio
async def test_automation_product_fanout_create_is_idempotent(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)
    payload = {
        "project_id": project_id,
        "parent_url": "https://shop.example/collections/summer-bags",
        "authorized": True,
        "max_sources": 10,
        "enable_tasks": True,
        "fields": ["title", "price", "canonical_url"],
        "candidates": [
            {
                "url": "https://shop.example/products/demo-bag",
                "title": "Demo Carry Bag",
                "source": "json_ld",
                "confidence": 0.9,
            },
            {
                "url": "https://shop.example/products/weekend-tote",
                "title": "Weekend Tote",
                "source": "anchor",
                "confidence": 0.86,
            },
            {
                "url": "https://other.example/products/external",
                "title": "External Product",
                "source": "anchor",
                "confidence": 0.86,
            },
        ],
    }

    first_response = await client.post("/api/automation/product-fanout-create", json=payload)
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["summary"] == {
        "created_sources": 2,
        "reused_sources": 0,
        "enabled_tasks": 2,
        "blocked_candidates": 1,
        "run_started": False,
    }
    assert [item["action"] for item in first["persisted_sources"]] == ["created", "created"]
    assert all(item["source"]["enabled"] is True for item in first["persisted_sources"])
    assert all(item["task"]["status"] == "enabled" for item in first["persisted_sources"])
    assert {status["reason"] for status in first["candidate_statuses"] if status["reason"]} == {
        "candidate_url_cross_origin"
    }
    assert any(event["event"] == "fanout_source_persisted" for event in first["audit_events"])

    sources_response = await client.get("/api/sources?type=ecommerce_product_page")
    assert sources_response.status_code == 200
    sources = sources_response.json()
    assert len(sources) == 2

    tasks_response = await client.get("/api/tasks")
    assert tasks_response.status_code == 200
    tasks = [
        task
        for task in tasks_response.json()
        if task["collector_type"] == "ecommerce_product_page"
    ]
    assert len(tasks) == 2
    assert all(task["latest_run_status"] is None for task in tasks)

    second_response = await client.post("/api/automation/product-fanout-create", json=payload)
    assert second_response.status_code == 200
    second = second_response.json()
    assert second["summary"]["created_sources"] == 0
    assert second["summary"]["reused_sources"] == 2
    assert [item["action"] for item in second["persisted_sources"]] == ["reused", "reused"]
    assert [item["source"]["id"] for item in second["persisted_sources"]] == [
        item["source"]["id"] for item in first["persisted_sources"]
    ]

    sources_after_response = await client.get("/api/sources?type=ecommerce_product_page")
    assert sources_after_response.status_code == 200
    assert len(sources_after_response.json()) == 2


@pytest.mark.asyncio
async def test_automation_product_batch_run_returns_field_completeness(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureEcommerceCollector(EcommerceProductPageCollector):
        async def collect(self) -> CollectionResult:
            url = str(self.config["url"])
            if "weekend-tote" in url:
                extracted_fields = {
                    "title": "Weekend Tote",
                    "canonical_url": url,
                }
            else:
                extracted_fields = {
                    "title": "Demo Carry Bag",
                    "price": 129.9,
                    "sku": "BAG-001",
                    "canonical_url": url,
                }
            return CollectionResult(
                raw_records=[
                    CollectorRawRecord(
                        record_type="ecommerce_product_page",
                        source_url=url,
                        content={
                            "provider": "ecommerce",
                            "kind": "product_page",
                            "url": url,
                            "extracted_fields": extracted_fields,
                            "field_schema": [],
                            "cleaning_plan": [],
                            "platform_profile": {"platform_type": "shopify"},
                            "page_structure": {"page_type": "product_detail"},
                        },
                    )
                ],
                logs=[],
                errors=[],
            )

    monkeypatch.setitem(
        collector_registry.COLLECTOR_REGISTRY,
        "ecommerce_product_page",
        FixtureEcommerceCollector,
    )
    project_id = await register_and_create_project(client)
    create_payload = {
        "project_id": project_id,
        "parent_url": "https://shop.example/collections/summer-bags",
        "authorized": True,
        "max_sources": 10,
        "enable_tasks": True,
        "fields": ["title", "price", "sku", "canonical_url"],
        "candidates": [
            {
                "url": "https://shop.example/products/demo-bag",
                "title": "Demo Carry Bag",
                "source": "json_ld",
                "confidence": 0.9,
            },
            {
                "url": "https://shop.example/products/weekend-tote",
                "title": "Weekend Tote",
                "source": "anchor",
                "confidence": 0.86,
            },
        ],
    }
    create_response = await client.post(
        "/api/automation/product-fanout-create",
        json=create_payload,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    product_task_ids = [item["task"]["id"] for item in created["persisted_sources"]]

    manual_source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "Manual JSON Guard",
            "type": "manual_json",
            "config": {"entity_type": "product", "json_data": {"name": "Guard"}},
            "schedule_cron": None,
        },
    )
    assert manual_source_response.status_code == 201
    manual_enable_response = await client.post(
        f"/api/sources/{manual_source_response.json()['id']}/enable"
    )
    assert manual_enable_response.status_code == 200
    manual_task_id = manual_enable_response.json()["id"]

    batch_response = await client.post(
        "/api/automation/product-batch-run",
        json={
            "authorized": True,
            "max_tasks": 5,
            "task_ids": [*product_task_ids, manual_task_id, product_task_ids[0]],
        },
    )
    assert batch_response.status_code == 200
    batch = batch_response.json()
    assert batch["summary"] == {
        "requested_tasks": 4,
        "run_tasks": 2,
        "blocked_tasks": 2,
        "successful_runs": 2,
        "failed_runs": 0,
        "records_count": 2,
        "entities_count": 2,
        "average_completeness_percent": 75,
        "run_started": True,
    }

    run_items = [item for item in batch["items"] if item["status"] == "run_completed"]
    assert len(run_items) == 2
    assert run_items[0]["field_completeness"]["completeness_percent"] == 100
    assert run_items[0]["field_completeness"]["missing_fields"] == []
    assert run_items[1]["field_completeness"]["completeness_percent"] == 50
    assert run_items[1]["field_completeness"]["missing_fields"] == ["price", "sku"]
    blocked_reasons = {
        item["blocked_reason"] for item in batch["items"] if item["status"] == "blocked"
    }
    assert blocked_reasons == {"unsupported_collector_type", "duplicate_task_id"}
    assert any(
        event["event"] == "product_batch_task_run_completed"
        for event in batch["audit_events"]
    )

    tasks_response = await client.get("/api/tasks?status=enabled")
    assert tasks_response.status_code == 200
    ecommerce_tasks = [
        task
        for task in tasks_response.json()
        if task["collector_type"] == "ecommerce_product_page"
    ]
    assert {task["latest_run_status"] for task in ecommerce_tasks} == {"success"}

    dataset_response = await client.post(
        "/api/automation/product-dataset-preview",
        json={
            "authorized": True,
            "task_run_ids": [item["run"]["id"] for item in run_items],
            "fields": ["title", "price", "sku", "canonical_url"],
            "max_rows": 10,
        },
    )
    assert dataset_response.status_code == 200
    dataset = dataset_response.json()
    assert dataset["summary"] == {
        "requested_runs": 2,
        "matched_runs": 2,
        "rows_count": 2,
        "selected_fields": ["title", "price", "sku", "canonical_url"],
        "average_completeness_percent": 75,
        "export_format": "json",
        "export_ready": True,
    }
    assert dataset["rows"][0]["values"]["title"] == "Demo Carry Bag"
    assert dataset["rows"][0]["missing_fields"] == []
    assert dataset["rows"][1]["values"]["title"] == "Weekend Tote"
    assert dataset["rows"][1]["missing_fields"] == ["price", "sku"]
    assert "cast price to decimal when present" in dataset["cleaning_script_draft"]
    assert dataset["export_preview"]["schema"]["primary_key"] == "canonical_url"
    assert dataset["export_preview"]["rows"][1]["price"] is None
    assert "尚未保存 Dataset" in dataset["blocked_reasons"][-1]

    save_payload = {
        "authorized": True,
        "name": "Summer Bags Product Dataset",
        "description": "Reviewed product dataset from small batch QA.",
        "task_run_ids": [item["run"]["id"] for item in run_items],
        "fields": ["title", "price", "sku", "canonical_url"],
        "max_rows": 10,
    }
    first_save_response = await client.post(
        "/api/automation/product-dataset-save",
        json=save_payload,
    )
    assert first_save_response.status_code == 200
    first_save = first_save_response.json()
    assert first_save["dataset"]["name"] == "Summer Bags Product Dataset"
    assert first_save["dataset"]["dataset_type"] == "ecommerce_product"
    assert first_save["dataset"]["description"] == "Reviewed product dataset from small batch QA."
    assert first_save["version"]["version_number"] == 1
    assert first_save["version"]["row_count"] == 2
    assert first_save["version"]["average_completeness_percent"] == 75
    assert first_save["version"]["selected_fields"] == ["title", "price", "sku", "canonical_url"]
    assert first_save["version"]["export_preview"]["rows"][0]["title"] == "Demo Carry Bag"
    assert any(
        event["event"] == "product_dataset_version_saved"
        for event in first_save["audit_events"]
    )
    assert "尚未写出文件" in first_save["blocked_reasons"][-1]

    second_save_response = await client.post(
        "/api/automation/product-dataset-save",
        json=save_payload,
    )
    assert second_save_response.status_code == 200
    second_save = second_save_response.json()
    assert second_save["dataset"]["id"] == first_save["dataset"]["id"]
    assert second_save["version"]["version_number"] == 2

    quality_gate_response = await client.post(
        "/api/automation/product-schedule-approve",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "task_ids": [item["task_id"] for item in run_items],
            "schedule_policy": "auto_freshness",
            "freshness_target_hours": 6,
            "minimum_completeness_percent": 90,
        },
    )
    assert quality_gate_response.status_code == 400
    assert quality_gate_response.json()["detail"] == "dataset_quality_gate_failed"

    schedule_response = await client.post(
        "/api/automation/product-schedule-approve",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "task_ids": [item["task_id"] for item in run_items],
            "schedule_policy": "auto_freshness",
            "freshness_target_hours": 6,
            "minimum_completeness_percent": 70,
            "note": "Approved after small batch QA.",
        },
    )
    assert schedule_response.status_code == 200
    schedule = schedule_response.json()
    assert schedule["summary"] == {
        "requested_tasks": 2,
        "approved_tasks": 2,
        "blocked_tasks": 0,
        "run_started": False,
    }
    assert {task["schedule_policy"] for task in schedule["approved_tasks"]} == {
        "auto_freshness"
    }
    assert {task["freshness_target_hours"] for task in schedule["approved_tasks"]} == {6}
    assert {task["schedule_cron"] for task in schedule["approved_tasks"]} == {None}
    assert schedule["blocked_tasks"] == []
    assert any(
        event["event"] == "product_schedule_approved"
        and event["run_started"] is False
        for event in schedule["audit_events"]
    )
    assert "不会立即启动采集运行" in schedule["blocked_reasons"][0]

    approved_task_id = run_items[0]["task_id"]
    approved_task_response = await client.get(f"/api/tasks/{approved_task_id}")
    assert approved_task_response.status_code == 200
    approved_task = approved_task_response.json()
    assert approved_task["schedule_policy"] == "auto_freshness"
    assert approved_task["freshness_target_hours"] == 6
    assert approved_task["schedule_cron"] is None
    assert approved_task["config"]["approved_dataset_id"] == first_save["dataset"]["id"]
    assert approved_task["config"]["approved_dataset_version_id"] == first_save["version"]["id"]
    assert approved_task["config"]["schedule_boundary"] == "approved_no_immediate_run"
    assert approved_task["config"]["schedule_quality_gate"] == {
        "minimum_completeness_percent": 70,
        "actual_completeness_percent": 75,
        "row_count": 2,
        "selected_fields": ["title", "price", "sku", "canonical_url"],
    }

    task_runs_after_schedule_response = await client.get(f"/api/tasks/{approved_task_id}/runs")
    assert task_runs_after_schedule_response.status_code == 200
    assert len(task_runs_after_schedule_response.json()) == 1

    drift_response = await client.post(
        "/api/automation/product-drift-check",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "task_ids": [item["task_id"] for item in run_items],
            "completeness_drop_threshold_percent": 10,
            "freshness_grace_hours": 24,
        },
    )
    assert drift_response.status_code == 200
    drift = drift_response.json()
    assert drift["summary"] == {
        "requested_tasks": 2,
        "checked_tasks": 2,
        "blocked_tasks": 0,
        "warning_tasks": 0,
        "critical_tasks": 1,
        "stale_tasks": 0,
        "missing_field_tasks": 1,
        "run_started": False,
        "alert_created": False,
    }
    drift_items_by_task_id = {item["task_id"]: item for item in drift["items"]}
    first_drift = drift_items_by_task_id[run_items[0]["task_id"]]
    second_drift = drift_items_by_task_id[run_items[1]["task_id"]]
    assert first_drift["status"] == "ok"
    assert first_drift["latest_completeness_percent"] == 100
    assert first_drift["completeness_drop_percent"] == 0
    assert first_drift["issues"] == []
    assert second_drift["status"] == "critical"
    assert second_drift["latest_completeness_percent"] == 50
    assert second_drift["completeness_drop_percent"] == 25
    assert second_drift["new_missing_fields"] == ["price", "sku"]
    assert second_drift["issues"] == [
        "completeness_drift_exceeded",
        "approved_fields_missing",
    ]
    assert any(
        event["event"] == "product_drift_task_checked"
        and event["run_started"] is False
        and event["alert_created"] is False
        for event in drift["audit_events"]
    )
    assert "不会启动采集" in drift["blocked_reasons"][0]

    drift_history_before_response = await client.get(
        "/api/automation/product-drift-events",
        params={
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
        },
    )
    assert drift_history_before_response.status_code == 200
    assert drift_history_before_response.json() == {
        "items": [],
        "total": 0,
        "run_started": False,
        "alert_created": False,
    }

    drift_event_response = await client.post(
        "/api/automation/product-drift-events",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "task_ids": [item["task_id"] for item in run_items],
            "completeness_drop_threshold_percent": 10,
            "freshness_grace_hours": 24,
            "note": "Saved from integration drift check.",
        },
    )
    assert drift_event_response.status_code == 200
    drift_event = drift_event_response.json()
    assert drift_event["status"] == "critical"
    assert drift_event["event_type"] == "ecommerce_product_drift"
    assert drift_event["summary"] == drift["summary"]
    assert drift_event["thresholds"] == {
        "completeness_drop_threshold_percent": 10,
        "freshness_grace_hours": 24,
    }
    assert drift_event["note"] == "Saved from integration drift check."
    assert drift_event["run_started"] is False
    assert drift_event["alert_created"] is False
    assert len(drift_event["items"]) == 2
    assert any(
        event["event"] == "product_drift_event_saved"
        and event["run_started"] is False
        and event["alert_created"] is False
        for event in drift_event["audit_events"]
    )

    drift_history_after_response = await client.get(
        "/api/automation/product-drift-events",
        params={
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
        },
    )
    assert drift_history_after_response.status_code == 200
    drift_history = drift_history_after_response.json()
    assert drift_history["total"] == 1
    assert drift_history["run_started"] is False
    assert drift_history["alert_created"] is False
    assert drift_history["items"][0]["id"] == drift_event["id"]
    assert drift_history["items"][0]["status"] == "critical"

    dataset_list_response = await client.get("/api/automation/product-datasets")
    assert dataset_list_response.status_code == 200
    dataset_list = dataset_list_response.json()
    assert dataset_list["total"] == 1
    assert dataset_list["run_started"] is False
    assert dataset_list["alert_created"] is False
    dataset_item = dataset_list["items"][0]
    assert dataset_item["dataset"]["id"] == first_save["dataset"]["id"]
    assert dataset_item["dataset"]["name"] == "Summer Bags Product Dataset"
    assert dataset_item["latest_version"]["id"] == second_save["version"]["id"]
    assert dataset_item["latest_version"]["version_number"] == 2
    assert dataset_item["version_count"] == 2
    assert dataset_item["latest_drift_event"]["id"] == drift_event["id"]
    assert dataset_item["latest_drift_event"]["status"] == "critical"
    assert dataset_item["drift_event_count"] == 1

    project_filtered_dataset_list_response = await client.get(
        "/api/automation/product-datasets",
        params={"project_id": project_id},
    )
    assert project_filtered_dataset_list_response.status_code == 200
    assert project_filtered_dataset_list_response.json()["total"] == 1

    dataset_versions_response = await client.get(
        f"/api/automation/product-datasets/{first_save['dataset']['id']}/versions"
    )
    assert dataset_versions_response.status_code == 200
    dataset_versions = dataset_versions_response.json()
    assert dataset_versions["dataset"]["id"] == first_save["dataset"]["id"]
    assert dataset_versions["total"] == 2
    assert dataset_versions["run_started"] is False
    assert dataset_versions["alert_created"] is False
    assert [item["version_number"] for item in dataset_versions["versions"]] == [2, 1]
    assert dataset_versions["versions"][1]["id"] == first_save["version"]["id"]

    drift_alert_preview_response = await client.post(
        "/api/automation/product-drift-alert-preview",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "min_status": "critical",
            "channel": "in_app",
            "enabled": True,
        },
    )
    assert drift_alert_preview_response.status_code == 200
    drift_alert_preview = drift_alert_preview_response.json()
    assert drift_alert_preview["rule_draft"]["signal_type"] == "dataset_drift"
    assert drift_alert_preview["rule_draft"]["project_id"] == project_id
    assert drift_alert_preview["rule_draft"]["condition"]["dataset_id"] == (
        first_save["dataset"]["id"]
    )
    assert drift_alert_preview["rule_draft"]["condition"]["dataset_version_id"] == (
        first_save["version"]["id"]
    )
    assert drift_alert_preview["rule_draft"]["condition"]["drift_statuses"] == ["critical"]
    assert drift_alert_preview["summary"] == {
        "matched_events": 1,
        "critical_events": 1,
        "warning_events": 0,
        "alert_rule_created": False,
        "signal_created": False,
        "alert_event_created": False,
        "notification_created": False,
        "run_started": False,
    }
    assert drift_alert_preview["matched_events"][0]["id"] == drift_event["id"]
    assert "不会创建 AlertRule" in drift_alert_preview["blocked_reasons"][0]

    alert_rules_after_preview_response = await client.get("/api/alert-rules")
    assert alert_rules_after_preview_response.status_code == 200
    assert alert_rules_after_preview_response.json() == []

    unconfirmed_alert_rule_response = await client.post(
        "/api/automation/product-drift-alert-rules",
        json={
            "authorized": True,
            "confirm_create": False,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "min_status": "critical",
            "channel": "in_app",
            "enabled": True,
        },
    )
    assert unconfirmed_alert_rule_response.status_code == 400
    assert unconfirmed_alert_rule_response.json()["detail"] == (
        "drift_alert_rule_confirmation_required"
    )

    drift_alert_rule_response = await client.post(
        "/api/automation/product-drift-alert-rules",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "min_status": "critical",
            "channel": "in_app",
            "enabled": True,
            "name": "Critical product drift policy",
        },
    )
    assert drift_alert_rule_response.status_code == 200
    drift_alert_rule = drift_alert_rule_response.json()
    assert drift_alert_rule["alert_rule"]["name"] == "Critical product drift policy"
    assert drift_alert_rule["alert_rule"]["signal_type"] == "dataset_drift"
    assert drift_alert_rule["alert_rule"]["condition"]["source"] == "dataset_drift_event"
    assert drift_alert_rule["alert_rule"]["condition"]["value"] == ["high"]
    assert drift_alert_rule["summary"]["alert_rule_created"] is True
    assert drift_alert_rule["summary"]["signal_created"] is False
    assert drift_alert_rule["summary"]["alert_event_created"] is False
    assert drift_alert_rule["summary"]["notification_created"] is False
    assert "不会回放历史事件" in drift_alert_rule["blocked_reasons"][0]

    alert_rules_after_create_response = await client.get("/api/alert-rules")
    assert alert_rules_after_create_response.status_code == 200
    alert_rules_after_create = alert_rules_after_create_response.json()
    assert len(alert_rules_after_create) == 1
    assert alert_rules_after_create[0]["id"] == drift_alert_rule["alert_rule"]["id"]

    alert_events_after_create_response = await client.get("/api/alert-events")
    assert alert_events_after_create_response.status_code == 200
    assert alert_events_after_create_response.json() == []

    scoped_nonmatching_rule_response = await client.post(
        "/api/alert-rules",
        json={
            "name": "Different dataset drift policy",
            "project_id": project_id,
            "signal_type": "dataset_drift",
            "condition": {
                "field": "severity",
                "op": "in",
                "value": ["high"],
                "source": "dataset_drift_event",
                "dataset_id": "00000000-0000-0000-0000-000000000001",
                "dataset_version_id": first_save["version"]["id"],
                "event_type": "ecommerce_product_drift",
            },
            "channel": "in_app",
            "enabled": True,
        },
    )
    assert scoped_nonmatching_rule_response.status_code == 201

    unconfirmed_alert_event_response = await client.post(
        "/api/automation/product-drift-alert-events",
        json={
            "authorized": True,
            "confirm_create": False,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
        },
    )
    assert unconfirmed_alert_event_response.status_code == 400
    assert unconfirmed_alert_event_response.json()["detail"] == (
        "drift_alert_event_confirmation_required"
    )

    drift_alert_event_response = await client.post(
        "/api/automation/product-drift-alert-events",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
        },
    )
    assert drift_alert_event_response.status_code == 200
    drift_alert_event = drift_alert_event_response.json()
    assert drift_alert_event["signal"]["signal_type"] == "dataset_drift"
    assert drift_alert_event["signal"]["severity"] == "high"
    assert drift_alert_event["signal"]["metadata"]["source"] == "dataset_drift_event"
    assert drift_alert_event["signal"]["metadata"]["dataset_id"] == first_save["dataset"]["id"]
    assert drift_alert_event["signal"]["metadata"]["dataset_version_id"] == (
        first_save["version"]["id"]
    )
    assert drift_alert_event["signal"]["metadata"]["drift_event_id"] == drift_event["id"]
    assert len(drift_alert_event["alert_events"]) == 1
    assert drift_alert_event["alert_events"][0]["rule_id"] == drift_alert_rule["alert_rule"]["id"]
    assert drift_alert_event["alert_events"][0]["status"] == "triggered"
    assert drift_alert_event["alert_events"][0]["sent_at"] is None
    assert drift_alert_event["summary"] == {
        "matched_events": 1,
        "critical_events": 1,
        "warning_events": 0,
        "alert_rule_created": False,
        "signal_created": True,
        "alert_event_created": True,
        "notification_created": False,
        "run_started": False,
    }
    assert "不会启动采集" in drift_alert_event["blocked_reasons"][0]

    alert_events_after_bridge_response = await client.get("/api/alert-events")
    assert alert_events_after_bridge_response.status_code == 200
    alert_events_after_bridge = alert_events_after_bridge_response.json()
    assert len(alert_events_after_bridge) == 1
    assert alert_events_after_bridge[0]["rule_id"] == drift_alert_rule["alert_rule"]["id"]
    bridged_alert_event_id = drift_alert_event["alert_events"][0]["id"]

    unconfirmed_notification_response = await client.post(
        "/api/automation/product-drift-alert-notifications",
        json={
            "authorized": True,
            "confirm_send": False,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [bridged_alert_event_id],
        },
    )
    assert unconfirmed_notification_response.status_code == 400
    assert unconfirmed_notification_response.json()["detail"] == (
        "drift_alert_notification_confirmation_required"
    )

    drift_alert_notification_response = await client.post(
        "/api/automation/product-drift-alert-notifications",
        json={
            "authorized": True,
            "confirm_send": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [bridged_alert_event_id],
        },
    )
    assert drift_alert_notification_response.status_code == 200
    drift_alert_notification = drift_alert_notification_response.json()
    assert len(drift_alert_notification["alert_events"]) == 1
    assert drift_alert_notification["alert_events"][0]["id"] == bridged_alert_event_id
    assert drift_alert_notification["alert_events"][0]["status"] == "sent"
    assert drift_alert_notification["alert_events"][0]["sent_at"] is not None
    assert len(drift_alert_notification["notifications"]) == 1
    assert drift_alert_notification["notifications"][0]["notification_type"] == "alert"
    assert drift_alert_notification["notifications"][0]["reference_type"] == "alert_event"
    assert drift_alert_notification["notifications"][0]["reference_id"] == bridged_alert_event_id
    assert drift_alert_notification["summary"] == {
        "matched_events": 1,
        "critical_events": 1,
        "warning_events": 0,
        "alert_rule_created": False,
        "signal_created": False,
        "alert_event_created": False,
        "notification_created": True,
        "run_started": False,
    }
    assert "发送邮件" in drift_alert_notification["blocked_reasons"][0]

    channel_mismatch_email_response = await client.post(
        "/api/automation/product-drift-alert-emails",
        json={
            "authorized": True,
            "confirm_send": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [bridged_alert_event_id],
            "recipient_email": "owner@example.com",
        },
    )
    assert channel_mismatch_email_response.status_code == 400
    assert channel_mismatch_email_response.json()["detail"] == (
        "alert_event_channel_not_email"
    )

    unconfirmed_email_send_response = await client.post(
        "/api/automation/product-drift-alert-emails",
        json={
            "authorized": True,
            "confirm_send": False,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [bridged_alert_event_id],
        },
    )
    assert unconfirmed_email_send_response.status_code == 400
    assert unconfirmed_email_send_response.json()["detail"] == (
        "drift_alert_email_confirmation_required"
    )

    email_rule_preview_response = await client.post(
        "/api/automation/product-drift-alert-preview",
        json={
            "authorized": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "min_status": "critical",
            "channel": "email",
            "enabled": True,
        },
    )
    assert email_rule_preview_response.status_code == 200

    email_rule_response = await client.post(
        "/api/automation/product-drift-alert-rules",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "min_status": "critical",
            "channel": "email",
            "enabled": True,
            "name": "Critical product drift email policy",
        },
    )
    assert email_rule_response.status_code == 200
    email_rule = email_rule_response.json()
    assert email_rule["alert_rule"]["channel"] == "email"
    assert email_rule["summary"]["alert_rule_created"] is True

    email_alert_event_response = await client.post(
        "/api/automation/product-drift-alert-events",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
        },
    )
    assert email_alert_event_response.status_code == 200
    email_alert_events = email_alert_event_response.json()
    assert len(email_alert_events["alert_events"]) == 1
    email_alert_event_id = email_alert_events["alert_events"][0]["id"]

    drift_alert_email_send_response = await client.post(
        "/api/automation/product-drift-alert-emails",
        json={
            "authorized": True,
            "confirm_send": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [email_alert_event_id],
            "recipient_email": "owner@example.com",
        },
    )
    assert drift_alert_email_send_response.status_code == 200
    drift_alert_email_send = drift_alert_email_send_response.json()
    assert len(drift_alert_email_send["email_deliveries"]) == 1
    assert drift_alert_email_send["email_deliveries"][0]["alert_event_id"] == email_alert_event_id
    assert drift_alert_email_send["email_deliveries"][0]["recipient_email"] == "owner@example.com"
    assert isinstance(drift_alert_email_send["email_deliveries"][0]["delivered"], bool)
    assert drift_alert_email_send["summary"] == {
        "matched_events": 1,
        "critical_events": 1,
        "warning_events": 0,
        "alert_rule_created": False,
        "signal_created": False,
        "alert_event_created": False,
        "notification_created": False,
        "run_started": False,
    }
    assert "发送站内通知" in drift_alert_email_send["blocked_reasons"][0]

    notifications_after_send_response = await client.get("/api/notifications?is_read=false")
    assert notifications_after_send_response.status_code == 200
    drift_notifications = [
        item
        for item in notifications_after_send_response.json()
        if item["reference_id"] == bridged_alert_event_id
    ]
    assert len(drift_notifications) == 1

    repeated_notification_response = await client.post(
        "/api/automation/product-drift-alert-notifications",
        json={
            "authorized": True,
            "confirm_send": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
            "alert_event_ids": [bridged_alert_event_id],
        },
    )
    assert repeated_notification_response.status_code == 200
    repeated_notification = repeated_notification_response.json()
    assert repeated_notification["summary"]["notification_created"] is False
    assert repeated_notification["notifications"][0]["id"] == drift_notifications[0]["id"]

    repeated_alert_event_response = await client.post(
        "/api/automation/product-drift-alert-events",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "drift_event_id": drift_event["id"],
        },
    )
    assert repeated_alert_event_response.status_code == 200
    repeated_alert_event = repeated_alert_event_response.json()
    assert repeated_alert_event["signal"]["id"] == drift_alert_event["signal"]["id"]
    assert repeated_alert_event["summary"]["signal_created"] is False
    assert repeated_alert_event["summary"]["alert_event_created"] is False
    assert repeated_alert_event["alert_events"] == []

    alert_events_after_repeat_response = await client.get("/api/alert-events")
    assert alert_events_after_repeat_response.status_code == 200
    alert_events_after_repeat = alert_events_after_repeat_response.json()
    assert len(alert_events_after_repeat) == 2
    assert len([item for item in alert_events_after_repeat if item["status"] == "sent"]) == 1
    drift_alert_rule_events = [
        item
        for item in alert_events_after_repeat
        if item["rule_id"] == drift_alert_rule["alert_rule"]["id"]
    ]
    email_alert_rule_events = [
        item
        for item in alert_events_after_repeat
        if item["rule_id"] == email_rule["alert_rule"]["id"]
    ]
    assert len(drift_alert_rule_events) == 1
    assert len(email_alert_rule_events) == 1

    task_runs_after_drift_response = await client.get(f"/api/tasks/{approved_task_id}/runs")
    assert task_runs_after_drift_response.status_code == 200
    assert len(task_runs_after_drift_response.json()) == 1


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
    assert dashboard["freshness"]["generated_at"] is not None
    assert dashboard["freshness"]["latest_collection_at"] == run["finished_at"]
    assert dashboard["freshness"]["stale_enabled_tasks"] == 0


@pytest.mark.asyncio
async def test_multiple_sources_reuse_existing_entity_by_external_id(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)

    source_ids: list[str] = []
    for index, price in enumerate((99, 120), start=1):
        source_response = await client.post(
            "/api/sources",
            json={
                "project_id": project_id,
                "name": f"Duplicate Entity Source {index}",
                "type": "manual_json",
                "config": {
                    "entity_type": "product",
                    "json_data": {"name": "Shared Product", "price": price},
                },
                "schedule_cron": None,
            },
        )
        assert source_response.status_code == 201
        source_ids.append(source_response.json()["id"])

    for source_id in source_ids:
        enable_response = await client.post(f"/api/sources/{source_id}/enable")
        assert enable_response.status_code == 200
        task = enable_response.json()
        run_response = await client.post(f"/api/tasks/{task['id']}/run")
        assert run_response.status_code == 201
        assert run_response.json()["status"] == "success"

    entities_response = await client.get("/api/entities")
    assert entities_response.status_code == 200
    entities = entities_response.json()
    assert len(entities) == 1
    assert entities[0]["external_id"] == "Shared Product"

    snapshots_response = await client.get(f"/api/entities/{entities[0]['id']}/snapshots")
    assert snapshots_response.status_code == 200
    snapshots = snapshots_response.json()
    assert len(snapshots) == 2
    assert {snapshot["metrics"]["price"] for snapshot in snapshots} == {99, 120}


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
    assert dashboard["top_intelligence"][0]["updated_at"] is not None
    assert dashboard["freshness"]["generated_at"] is not None
    assert dashboard["freshness"]["latest_collection_at"] == second_run["finished_at"]
    assert dashboard["freshness"]["stale_enabled_tasks"] == 0
