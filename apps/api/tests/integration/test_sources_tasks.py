from __future__ import annotations

import subprocess
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import automation as automation_routes
from data_intelligence_hub.collectors import registry as collector_registry
from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
)
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.schemas.automation import (
    AutomationCleaningStepResponse,
    AutomationFieldCandidateResponse,
    AutomationPageStructureResponse,
    AutomationPlatformProfileResponse,
    AutomationSiteAnalysisResponse,
    AutomationSourceDraftResponse,
    AutomationToolRecommendationResponse,
)


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
async def test_automation_platform_packages_expose_collection_contract(
    client: AsyncClient,
) -> None:
    await register_and_create_project(client)

    list_response = await client.get("/api/automation/platform-packages")
    assert list_response.status_code == 200
    package_list = list_response.json()
    assert package_list["total"] >= 3
    assert package_list["run_started"] is False

    packages_by_id = {item["id"]: item for item in package_list["items"]}
    assert "shopify-independent-ecommerce" in packages_by_id
    assert "github-api-first" in packages_by_id
    assert "public-page-structure-preflight" in packages_by_id

    ecommerce_package = packages_by_id["shopify-independent-ecommerce"]
    assert ecommerce_package["category"] == "ecommerce"
    assert ecommerce_package["execution_boundary"] == "executable"
    assert ecommerce_package["collector_types"] == [
        "ecommerce_product_discovery",
        "ecommerce_product_page",
    ]
    assert ecommerce_package["supported_targets"] == [
        "ecommerce_product",
        "ecommerce_product_collection",
    ]
    assert {field["key"] for field in ecommerce_package["field_schema"]} >= {
        "title",
        "price",
        "sku",
        "canonical_url",
    }
    assert ecommerce_package["default_entrypoint"] == "product-discovery"
    assert {
        sample["entrypoint"] for sample in ecommerce_package["sample_urls"]
    } >= {"product-discovery", "site-analysis"}
    assert any(
        rule["field"] == "sku"
        and rule["operation"] == "fill_default"
        and rule["value"] == "UNKNOWN-SKU"
        for rule in ecommerce_package["cleaning_rules"]
    )
    assert any("清洗计划" in item for item in ecommerce_package["operator_checklist"])
    assert any(
        strategy["entrypoint"] == "product-discovery"
        and strategy["collector_type"] == "ecommerce_product_discovery"
        and strategy["can_start_from_automation"] is True
        for strategy in ecommerce_package["strategy_matrix"]
    )
    assert ecommerce_package["sample_fixture"]["fixture_type"] == "deterministic_html"
    assert ecommerce_package["sample_fixture"]["available"] is True
    assert ecommerce_package["sop_links"][0]["href"].startswith("/toolkit")

    github_package = packages_by_id["github-api-first"]
    assert github_package["category"] == "developer_platform"
    assert github_package["execution_boundary"] == "executable"
    assert "github_topic" in github_package["collector_types"]
    assert github_package["default_entrypoint"] == "source-create"
    assert github_package["sample_urls"][0]["url"].startswith("https://github.com/topics/")
    assert any(
        boundary["severity"] == "warning"
        and "github token" in boundary["condition"].lower()
        for boundary in github_package["risk_boundaries"]
    )
    assert any(
        strategy["entrypoint"] == "source-create"
        and strategy["collector_type"] == "github_topic"
        and strategy["can_start_from_automation"] is True
        for strategy in github_package["strategy_matrix"]
    )

    preflight_package = packages_by_id["public-page-structure-preflight"]
    assert preflight_package["category"] == "browser_preflight"
    assert preflight_package["execution_boundary"] == "executable"
    assert preflight_package["default_entrypoint"] == "preflight"
    assert preflight_package["collector_types"] == ["toolkit_preflight", "generic_web"]
    assert {field["key"] for field in preflight_package["field_schema"]} >= {
        "page_title",
        "canonical_url",
        "headings",
        "text_sample",
    }
    assert any(
        strategy["entrypoint"] == "preflight"
        and strategy["collector_type"] == "toolkit_preflight"
        and strategy["can_start_from_automation"] is True
        for strategy in preflight_package["strategy_matrix"]
    )
    assert any(
        strategy["entrypoint"] == "source-create"
        and strategy["collector_type"] == "generic_web"
        and strategy["can_start_from_automation"] is True
        for strategy in preflight_package["strategy_matrix"]
    )
    assert any(
        boundary["severity"] == "blocked" and "验证码" in boundary["condition"]
        for boundary in preflight_package["risk_boundaries"]
    )

    detail_response = await client.get(
        "/api/automation/platform-packages/shopify-independent-ecommerce"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == ecommerce_package["id"]
    assert detail["run_started"] is False

    missing_response = await client.get("/api/automation/platform-packages/missing")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "platform_package_not_found"


@pytest.mark.asyncio
async def test_automation_capability_probes_fail_closed_when_agent_reach_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_create_project(client)

    monkeypatch.setattr(
        "data_intelligence_hub.services.automation_service.shutil.which",
        lambda command: None,
    )

    response = await client.get("/api/automation/capability-probes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "capability_probe_list.v1"
    assert payload["run_started"] is False
    assert payload["collection_resources_written"] is False
    assert payload["total"] >= 6

    probes_by_id = {item["platform_id"]: item for item in payload["items"]}
    github_probe = probes_by_id["github"]
    assert github_probe["schema_version"] == "capability_probe.v1"
    assert github_probe["execution_boundary"] == "executable"
    assert github_probe["run_started"] is False
    assert github_probe["collection_resources_written"] is False
    assert github_probe["agent_reach"]["installed"] is False
    assert github_probe["agent_reach"]["doctor_status"] == "missing_tool"
    assert github_probe["agent_reach"]["blocked_reason"] == "agent_reach_not_installed"
    assert github_probe["agent_reach"]["read_invoked"] is False
    assert github_probe["agent_reach"]["search_invoked"] is False
    assert any(
        candidate["backend_id"] == "official_github_api"
        and candidate["status"] == "available"
        for candidate in github_probe["backend_candidates"]
    )
    assert any(
        candidate["backend_id"] == "agent_reach_channel"
        and candidate["status"] == "missing_tool"
        for candidate in github_probe["backend_candidates"]
    )

    browser_probe = probes_by_id["browser_preflight"]
    assert browser_probe["doctor_status"] == "missing_tool"
    assert browser_probe["agent_reach"] is None
    assert browser_probe["allowed_outputs"] == ["BrowserDiagnosticJobRun"]

    social_probe = probes_by_id["social_sop_import_only"]
    assert social_probe["execution_boundary"] == "sop_only"
    assert "cookie_export" in social_probe["forbidden_actions"]
    assert "personal_profile_enrichment" in social_probe["forbidden_actions"]

    missing_response = await client.get(
        "/api/automation/capability-probes",
        params={"platform_id": "missing"},
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "capability_probe_platform_not_found"


@pytest.mark.asyncio
async def test_automation_capability_probes_use_agent_reach_doctor_only(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_create_project(client)
    calls: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        if command == "agent-reach":
            return "/usr/local/bin/agent-reach"
        if command == "browser-harness":
            return "/usr/local/bin/browser-harness"
        return None

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert args == ["/usr/local/bin/agent-reach", "doctor", "--json"]
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        assert kwargs["text"] is True
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                '{"platforms":["github","web"],'
                '"channels":{"github":{"active_backend":"gh"}}}'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "data_intelligence_hub.services.automation_service.shutil.which",
        fake_which,
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.automation_service.subprocess.run",
        fake_run,
    )

    response = await client.get(
        "/api/automation/capability-probes",
        params={"platform_id": "github"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert calls == [["/usr/local/bin/agent-reach", "doctor", "--json"]]

    github_probe = payload["items"][0]
    assert github_probe["platform_id"] == "github"
    assert github_probe["agent_reach"]["installed"] is True
    assert github_probe["agent_reach"]["doctor_status"] == "available"
    assert github_probe["agent_reach"]["active_backend"] == "gh"
    assert github_probe["agent_reach"]["platforms"] == ["github", "web"]
    assert github_probe["agent_reach"]["read_invoked"] is False
    assert github_probe["agent_reach"]["search_invoked"] is False
    assert any(
        candidate["backend_id"] == "agent_reach_channel"
        and candidate["status"] == "available"
        and "doctor --json" in " ".join(candidate["notes"])
        for candidate in github_probe["backend_candidates"]
    )
    assert payload["run_started"] is False
    assert payload["collection_resources_written"] is False


@pytest.mark.asyncio
async def test_automation_site_analysis_persists_history_and_extraction_plan(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_analyze_site_for_collection(
        payload: object,
    ) -> AutomationSiteAnalysisResponse:
        del payload
        return AutomationSiteAnalysisResponse(
            requested_url="https://shop.example/products/demo-bag",
            analyzed_at="2026-06-19T00:00:00Z",
            authorization_confirmed=True,
            platform_profile=AutomationPlatformProfileResponse(
                platform_type="independent_ecommerce",
                confidence=0.92,
                indicators=["json_ld_product"],
                risk_level="low",
            ),
            page_structure=AutomationPageStructureResponse(
                page_type="product_detail",
                title="Demo Carry Bag",
                canonical_url="https://shop.example/products/demo-bag",
                script_count=3,
                form_count=0,
                image_count=4,
                product_schema_count=1,
                same_origin_link_count=12,
                text_sample="Demo Carry Bag USD 129.90",
            ),
            field_candidates=[
                AutomationFieldCandidateResponse(
                    key="title",
                    label="Title",
                    value="Demo Carry Bag",
                    data_type="string",
                    source="json_ld",
                    confidence=0.95,
                    selected=True,
                    cleaning_rule="trim",
                ),
                AutomationFieldCandidateResponse(
                    key="price",
                    label="Price",
                    value=129.9,
                    data_type="number",
                    source="json_ld",
                    confidence=0.9,
                    selected=True,
                    cleaning_rule="decimal",
                ),
                AutomationFieldCandidateResponse(
                    key="sku",
                    label="SKU",
                    value="BAG-001",
                    data_type="string",
                    source="json_ld",
                    confidence=0.88,
                    selected=True,
                    cleaning_rule="trim",
                ),
            ],
            tool_recommendations=[
                AutomationToolRecommendationResponse(
                    tool="Built-in ecommerce product parser",
                    collector_type="ecommerce_product_page",
                    fit="high",
                    risk_level="low",
                    reason="JSON-LD product schema is available.",
                )
            ],
            cleaning_plan=[
                AutomationCleaningStepResponse(
                    field="price",
                    operation="cast_decimal",
                    description="Cast price to decimal.",
                )
            ],
            source_draft=AutomationSourceDraftResponse(
                type="ecommerce_product_page",
                config={
                    "url": "https://shop.example/products/demo-bag",
                    "fields": ["title", "price", "sku"],
                    "platform_hint": "independent_ecommerce",
                },
                suggested_name="商品页采集：Demo Carry Bag",
                schedule_cron=None,
            ),
            blocked_reasons=[],
        )

    monkeypatch.setattr(
        automation_routes,
        "analyze_site_for_collection",
        fake_analyze_site_for_collection,
    )
    project_id = await register_and_create_project(client)

    analysis_response = await client.post(
        "/api/automation/site-analysis",
        json={
            "project_id": project_id,
            "url": "https://shop.example/products/demo-bag",
            "authorized": True,
            "target": "ecommerce_product",
            "fields": ["title", "price", "sku"],
        },
    )

    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert analysis["site_analysis_created"] is True
    assert analysis["extraction_plan_created"] is True
    assert analysis["run_started"] is False
    assert analysis["site_analysis"]["project_id"] == project_id
    assert analysis["site_analysis"]["requested_url"] == "https://shop.example/products/demo-bag"
    assert analysis["site_analysis"]["platform_type"] == "independent_ecommerce"
    assert analysis["site_analysis"]["page_type"] == "product_detail"
    assert analysis["extraction_plan"]["version_number"] == 1
    assert analysis["extraction_plan"]["collector_type"] == "ecommerce_product_page"
    assert analysis["extraction_plan"]["selected_fields"] == ["title", "price", "sku"]

    history_response = await client.get(
        "/api/automation/site-analyses",
        params={"project_id": project_id},
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] == 1
    assert history["items"][0]["id"] == analysis["site_analysis"]["id"]
    assert history["items"][0]["latest_plan"]["id"] == analysis["extraction_plan"]["id"]
    assert history["run_started"] is False

    detail_response = await client.get(
        f"/api/automation/site-analyses/{analysis['site_analysis']['id']}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["site_analysis"]["id"] == analysis["site_analysis"]["id"]
    assert detail["field_candidates"][0]["key"] == "title"
    assert detail["extraction_plans"][0]["id"] == analysis["extraction_plan"]["id"]

    copied_plan_response = await client.post(
        f"/api/automation/site-analyses/{analysis['site_analysis']['id']}/extraction-plans",
        json={
            "authorized": True,
            "name": "SKU focused plan",
            "fields": ["title", "sku"],
            "schedule_cron": "0 8 * * *",
        },
    )
    assert copied_plan_response.status_code == 200
    copied_plan = copied_plan_response.json()
    assert copied_plan["version_number"] == 2
    assert copied_plan["name"] == "SKU focused plan"
    assert copied_plan["selected_fields"] == ["title", "sku"]
    assert copied_plan["source_draft"]["config"]["fields"] == ["title", "sku"]
    assert copied_plan["run_started"] is False


@pytest.mark.asyncio
async def test_browser_automation_plan_persists_read_only_draft(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    project_id = await register_and_create_project(client)
    payload = {
        "project_id": project_id,
        "requested_url": "https://example.com/products/dynamic-bag",
        "authorized": True,
        "name": "Browser Automation: dynamic-bag",
        "runner": "browser_harness",
        "execution_mode": "read_only_browser_harness",
        "risk_level": "medium",
        "field_contract": {
            "fields": [
                {
                    "key": "page_title",
                    "label": "页面标题",
                    "source": "browser_text",
                    "required": True,
                    "selected": True,
                    "selector_hint": "h1",
                },
                {
                    "key": "price",
                    "label": "价格",
                    "source": "browser_text",
                    "required": True,
                    "selected": True,
                    "selector_hint": "[data-price]",
                },
                {
                    "key": "api_candidate",
                    "label": "API 候选",
                    "source": "network",
                    "required": False,
                    "selected": True,
                    "selector_hint": "xhr:/api/products",
                },
            ],
            "cleaning_rules": [
                {
                    "field": "page_title",
                    "operation": "strip_text",
                    "description": "去除标题前后空白。",
                }
            ],
        },
        "browser_diagnostic": {
            "schema_version": "browser_structure_diagnostic.v1",
            "final_url": "https://example.com/products/dynamic-bag",
            "recommended_path": "browser_automation",
            "confidence": 86,
            "field_stability": "medium",
            "evidence_source": "browser-harness",
            "screenshot_path": "/tmp/browser-diagnostic/dynamic-bag.png",
        },
        "diagnostic_payload": {
            "schema_version": "browser_structure_diagnostic.v1",
            "generated_at": "2026-06-21T00:00:00Z",
            "requested_url": "https://example.com/products/dynamic-bag",
            "final_url": "https://example.com/products/dynamic-bag",
            "run_policy": {
                "authorization_confirmed": True,
                "execution_mode": "read_only_browser_harness",
                "production_write": False,
                "login_or_private_page_allowed": False,
                "cookies_exported": False,
            },
            "visible_text": {
                "length": 120,
                "line_count": 5,
                "sample": "Dynamic Bag\n$129",
            },
            "dom_counters": {
                "links": 20,
                "forms": 0,
                "scripts": 18,
            },
            "risk_flags": ["dynamic_content"],
            "extraction_strategy": {
                "recommended_path": "browser_automation",
                "fit": "medium",
                "confidence": 86,
                "field_stability": "medium",
                "reasons": ["关键字段由前端渲染。"],
            },
            "network_summary": {
                "resource_count": 42,
                "api_candidate_count": 1,
                "api_candidates": [
                    {
                        "url": "https://example.com/api/products/dynamic-bag",
                        "initiator_type": "fetch",
                    }
                ],
            },
            "accessibility_summary": {"heading_count": 2},
            "evidence": {
                "source": "browser-harness",
                "screenshot_path": "/tmp/browser-diagnostic/dynamic-bag.png",
                "errors": [],
            },
        },
        "api_candidates": ["https://example.com/api/products/dynamic-bag"],
        "guardrails": [
            "只读执行，不提交表单、不点击购买或发布类按钮。",
            "保留诊断 JSON、截图路径和最终 URL 作为审计证据。",
        ],
    }

    unauthorized_response = await client.post(
        "/api/automation/browser-automation-plans",
        json={**payload, "authorized": False},
    )
    assert unauthorized_response.status_code == 400
    assert unauthorized_response.json()["detail"] == "automation_authorization_required"

    response = await client.post("/api/automation/browser-automation-plans", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["run_started"] is False
    assert result["site_analysis_created"] is True
    assert result["extraction_plan_created"] is True
    assert result["browser_diagnostic_created"] is True
    assert result["site_analysis"]["project_id"] == project_id
    assert result["site_analysis"]["target"] == "browser_automation"
    assert result["site_analysis"]["status"] == "draft"
    assert result["site_analysis"]["requested_url"] == payload["requested_url"]
    assert result["site_analysis"]["platform_type"] == "dynamic_browser_page"
    assert result["site_analysis"]["page_type"] == "browser_runtime"

    plan = result["extraction_plan"]
    assert plan["collector_type"] == "browser_automation"
    assert plan["status"] == "draft"
    assert plan["risk_level"] == "medium"
    assert plan["selected_fields"] == ["page_title", "price", "api_candidate"]
    assert plan["run_started"] is False
    assert plan["audit_events"][0]["event"] == "browser_automation_plan_saved"
    assert plan["audit_events"][0]["run_started"] is False

    source_draft = plan["source_draft"]
    assert source_draft["type"] == "browser_automation"
    assert source_draft["suggested_name"] == "Browser Automation: dynamic-bag"
    config = source_draft["config"]
    assert config["runner"] == "browser_harness"
    assert config["execution_mode"] == "read_only_browser_harness"
    assert config["start_url"] == "https://example.com/products/dynamic-bag"
    assert config["fields"] == ["page_title", "price", "api_candidate"]
    assert config["run_started"] is False
    assert config["browser_diagnostic_run_id"] == result["browser_diagnostic"]["id"]
    assert config["browser_diagnostic"]["evidence_source"] == "browser-harness"
    assert config["field_contract"]["fields"][0]["selector_hint"] == "h1"
    assert config["api_candidates"] == ["https://example.com/api/products/dynamic-bag"]
    assert "只读执行" in config["guardrails"][0]
    assert config["executable_spec"]["schema_version"] == "browser_automation_executable_spec.v1"
    assert config["executable_spec"]["manual_review_required"] is True
    assert config["executable_spec"]["selector_contract"][0]["field"] == "page_title"
    assert config["executable_spec"]["wait_conditions"][0]["type"] == "domcontentloaded"
    assert config["executable_spec"]["dry_run_limits"]["write_allowed"] is False

    diagnostic = result["browser_diagnostic"]
    assert diagnostic["site_analysis_id"] == result["site_analysis"]["id"]
    assert diagnostic["recommended_path"] == "browser_automation"
    assert diagnostic["field_stability"] == "medium"
    assert diagnostic["run_policy"]["read_only"] is True
    assert diagnostic["run_policy"]["run_started"] is False
    assert diagnostic["page_summary"]["visible_text"]["sample"] == "Dynamic Bag\n$129"
    assert diagnostic["network_summary"]["api_candidate_count"] == 1
    assert diagnostic["risk_flags"] == [{"flag": "dynamic_content", "severity": "review"}]
    assert diagnostic["run_started"] is False

    history_response = await client.get(
        "/api/automation/site-analyses",
        params={"project_id": project_id, "target": "browser_automation"},
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] == 1
    assert history["items"][0]["id"] == result["site_analysis"]["id"]
    assert history["items"][0]["latest_plan"]["id"] == plan["id"]
    assert history["run_started"] is False

    detail_response = await client.get(
        f"/api/automation/site-analyses/{result['site_analysis']['id']}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["source_draft"]["config"]["runner"] == "browser_harness"
    assert detail["field_candidates"][0]["key"] == "page_title"
    assert detail["tool_recommendations"][0]["collector_type"] == "browser_automation"

    diagnostics_response = await client.get(
        "/api/automation/browser-diagnostics",
        params={"project_id": project_id},
    )
    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()
    assert diagnostics["total"] == 1
    assert diagnostics["items"][0]["id"] == diagnostic["id"]
    assert diagnostics["items"][0]["run_started"] is False

    unconfirmed_dry_run_response = await client.post(
        "/api/automation/browser-automation-spec-dry-run",
        json={
            "authorized": True,
            "confirm_review": False,
            "site_analysis_id": result["site_analysis"]["id"],
            "extraction_plan_id": plan["id"],
            "browser_diagnostic_run_id": diagnostic["id"],
        },
    )
    assert unconfirmed_dry_run_response.status_code == 400
    assert (
        unconfirmed_dry_run_response.json()["detail"]
        == "browser_spec_review_confirmation_required"
    )

    dry_run_response = await client.post(
        "/api/automation/browser-automation-spec-dry-run",
        json={
            "authorized": True,
            "confirm_review": True,
            "site_analysis_id": result["site_analysis"]["id"],
            "extraction_plan_id": plan["id"],
            "browser_diagnostic_run_id": diagnostic["id"],
        },
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["run_started"] is False
    assert dry_run["summary"]["status"] == "review"
    assert dry_run["summary"]["blocked_checks"] == 0
    assert dry_run["summary"]["review_checks"] >= 1
    assert dry_run["summary"]["selector_count"] == 3
    assert dry_run["summary"]["wait_condition_count"] == 2
    assert dry_run["summary"]["api_candidate_count"] == 1
    assert dry_run["summary"]["write_allowed"] is False
    assert dry_run["summary"]["can_dry_run_after_review"] is True
    assert dry_run["extraction_plan"]["id"] == plan["id"]
    assert dry_run["browser_diagnostic"]["id"] == diagnostic["id"]
    checks_by_key = {check["key"]: check for check in dry_run["checks"]}
    assert checks_by_key["diagnostic-lineage"]["status"] == "passed"
    assert checks_by_key["dry-run-limits"]["status"] == "passed"
    assert checks_by_key["manual-review"]["status"] == "review"
    assert dry_run["blocked_reasons"] == []
    assert dry_run["audit_events"][0]["event"] == "browser_automation_spec_dry_run_validated"
    assert dry_run["audit_events"][0]["run_started"] is False

    unconfirmed_job_response = await client.post(
        "/api/automation/browser-diagnostic-jobs",
        json={
            "authorized": True,
            "confirm_create": False,
            "site_analysis_id": result["site_analysis"]["id"],
            "extraction_plan_id": plan["id"],
            "browser_diagnostic_run_id": diagnostic["id"],
        },
    )
    assert unconfirmed_job_response.status_code == 400
    assert (
        unconfirmed_job_response.json()["detail"]
        == "browser_diagnostic_job_confirmation_required"
    )

    job_response = await client.post(
        "/api/automation/browser-diagnostic-jobs",
        json={
            "authorized": True,
            "confirm_create": True,
            "site_analysis_id": result["site_analysis"]["id"],
            "extraction_plan_id": plan["id"],
            "browser_diagnostic_run_id": diagnostic["id"],
            "network_observation_mode": "same_origin_api_candidates",
            "artifact_mode": "screenshot_reference_only",
            "note": "Queue reviewed browser diagnostic job.",
        },
    )
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "ready_for_manual_execution"
    assert job["run_started"] is False
    assert job["site_analysis_id"] == result["site_analysis"]["id"]
    assert job["extraction_plan_id"] == plan["id"]
    assert job["browser_diagnostic_run_id"] == diagnostic["id"]
    assert job["requested_url"] == payload["requested_url"]
    assert job["final_url"] == "https://example.com/products/dynamic-bag"
    assert job["runner"] == "browser_harness"
    assert job["execution_mode"] == "read_only_browser_harness"
    assert [item["field"] for item in job["selector_scope"]] == [
        "page_title",
        "price",
        "api_candidate",
    ]
    assert job["wait_policy"][0]["type"] == "domcontentloaded"
    assert job["network_observation_policy"] == {
        "mode": "same_origin_api_candidates",
        "same_origin_only": True,
        "capture_body": False,
        "capture_headers": False,
        "write_allowed": False,
        "api_candidates": ["https://example.com/api/products/dynamic-bag"],
    }
    assert job["artifact_policy"]["mode"] == "screenshot_reference_only"
    assert (
        job["artifact_policy"]["retain_screenshot_path"]
        == "/tmp/browser-diagnostic/dynamic-bag.png"
    )
    assert "no_source_task_taskrun_creation" in job["safety_flags"]
    assert job["dry_run_summary"]["status"] == "review"
    assert job["dry_run_summary"]["write_allowed"] is False
    assert "browser_diagnostic_job_created_no_runner" in job["blocked_reasons"]
    assert job["audit_events"][0]["event"] == "browser_diagnostic_job_created"
    assert job["audit_events"][0]["run_started"] is False

    duplicate_job_response = await client.post(
        "/api/automation/browser-diagnostic-jobs",
        json={
            "authorized": True,
            "confirm_create": True,
            "site_analysis_id": result["site_analysis"]["id"],
            "extraction_plan_id": plan["id"],
            "browser_diagnostic_run_id": diagnostic["id"],
            "network_observation_mode": "same_origin_api_candidates",
            "artifact_mode": "screenshot_reference_only",
        },
    )
    assert duplicate_job_response.status_code == 200
    assert duplicate_job_response.json()["id"] == job["id"]

    job_list_response = await client.get(
        "/api/automation/browser-diagnostic-jobs",
        params={"project_id": project_id, "status": "ready_for_manual_execution"},
    )
    assert job_list_response.status_code == 200
    job_list = job_list_response.json()
    assert job_list["total"] == 1
    assert job_list["run_started"] is False
    assert job_list["items"][0]["id"] == job["id"]

    job_detail_response = await client.get(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}"
    )
    assert job_detail_response.status_code == 200
    assert job_detail_response.json()["id"] == job["id"]

    unconfirmed_contract_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/executor-contract",
        json={
            "authorized": True,
            "confirm_review": False,
        },
    )
    assert unconfirmed_contract_response.status_code == 400
    assert (
        unconfirmed_contract_response.json()["detail"]
        == "browser_executor_contract_review_required"
    )

    contract_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/executor-contract",
        json={
            "authorized": True,
            "confirm_review": True,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Build local runner contract only.",
        },
    )
    assert contract_response.status_code == 200
    contract = contract_response.json()
    assert contract["job"]["id"] == job["id"]
    assert contract["adapter"]["schema_version"] == "browser_executor_adapter_contract.v1"
    assert contract["adapter"]["adapter_name"] == "browser_harness_read_only_local"
    assert contract["adapter"]["execution_policy"] == {
        "manual_operator_required": True,
        "automatic_api_worker_start": False,
        "production_enabled": False,
        "write_allowed": False,
        "run_started": False,
    }
    assert contract["runtime_isolation"]["mode"] == "local_ephemeral_browser_context"
    assert contract["runtime_isolation"]["reuse_user_profile"] is False
    assert contract["runtime_isolation"]["cookie_export_allowed"] is False
    assert contract["artifact_retention_policy"]["write_files_now"] is False
    assert contract["artifact_retention_policy"]["retention_days"] == 5
    assert contract["artifact_retention_policy"]["max_preview_rows"] == 12
    assert contract["artifact_retention_policy"]["har_summary"]["capture_body"] is False
    assert "evaluate_declared_selectors" in contract["allowed_actions"]
    assert "reuse_user_chrome_profile" in contract["denied_actions"]
    readiness_by_key = {item["key"]: item for item in contract["readiness_checks"]}
    assert readiness_by_key["job-status"]["status"] == "passed"
    assert readiness_by_key["no-run-started"]["status"] == "passed"
    assert readiness_by_key["network-policy"]["status"] == "passed"
    assert readiness_by_key["artifact-policy"]["status"] == "passed"
    assert contract["blocked_reasons"] == []
    assert contract["run_started"] is False
    assert contract["execution_started"] is False
    assert contract["audit_events"][0]["event"] == "browser_executor_contract_built"
    assert contract["audit_events"][0]["run_started"] is False

    unconfirmed_local_run_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": False,
        },
    )
    assert unconfirmed_local_run_response.status_code == 400
    assert (
        unconfirmed_local_run_response.json()["detail"]
        == "browser_local_runner_confirmation_required"
    )

    local_run_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Replay diagnostic snapshot locally.",
        },
    )
    assert local_run_response.status_code == 200
    local_run = local_run_response.json()
    assert local_run["job"]["id"] == job["id"]
    assert local_run["status"] == "completed_snapshot_replay"
    assert local_run["runner"] == "browser_harness_read_only_local"
    assert local_run["run_mode"] == "diagnostic_snapshot_replay"
    assert local_run["execution_started"] is True
    assert local_run["browser_started"] is False
    assert local_run["files_written"] is False
    assert local_run["collection_resources_written"] is False
    assert (
        local_run["contract_snapshot"]["adapter"]["adapter_name"]
        == "browser_harness_read_only_local"
    )
    assert local_run["artifact_manifest"]["schema_version"] == (
        "browser_local_runner_artifact_manifest.v1"
    )
    assert local_run["artifact_manifest"]["files_written"] is False
    assert local_run["artifact_manifest"]["preview_rows_count"] == 1
    assert (
        local_run["artifact_manifest"]["screenshot"]["referenced_path"]
        == "/tmp/browser-diagnostic/dynamic-bag.png"
    )
    selector_results = {item["field"]: item for item in local_run["selector_results"]}
    assert selector_results["page_title"]["status"] == "observed_from_diagnostic_snapshot"
    assert selector_results["page_title"]["value"] == "Dynamic Bag"
    assert selector_results["price"]["status"] == "not_observed_in_diagnostic_snapshot"
    assert selector_results["price"]["value"] is None
    assert selector_results["api_candidate"]["value"] == (
        "https://example.com/api/products/dynamic-bag"
    )
    selector_evaluations = {
        item["field"]: item for item in local_run["selector_evaluations"]
    }
    assert selector_evaluations["page_title"]["schema_version"] == (
        "browser_selector_evaluation.v1"
    )
    assert selector_evaluations["page_title"]["match_count"] == 1
    assert selector_evaluations["page_title"]["sample_text"] == "Dynamic Bag"
    assert selector_evaluations["price"]["match_count"] == 0
    assert selector_evaluations["price"]["missing_reason"] == (
        "not_observed_in_diagnostic_snapshot"
    )
    assert selector_evaluations["price"]["required"] is True
    assert selector_evaluations["api_candidate"]["sample_text"] == (
        "https://example.com/api/products/dynamic-bag"
    )
    assert local_run["preview_rows"][0]["values"] == {
        "page_title": "Dynamic Bag",
        "api_candidate": "https://example.com/api/products/dynamic-bag",
    }
    assert local_run["network_observation_summary"]["browser_started"] is False
    assert local_run["network_observation_summary"]["api_candidate_count"] == 1
    assert local_run["network_metadata_summary"]["schema_version"] == (
        "browser_network_metadata_summary.v1"
    )
    assert local_run["network_metadata_summary"]["metadata_only"] is True
    assert local_run["network_metadata_summary"]["capture_headers"] is False
    assert local_run["network_metadata_summary"]["capture_body"] is False
    assert local_run["network_metadata_summary"]["api_candidate_count"] == 1
    assert local_run["error_summary"]["error_count"] == 0
    assert local_run["promotion_gate"]["schema_version"] == "browser_promotion_gate.v1"
    assert local_run["promotion_gate"]["can_create_collection_resources"] is False
    assert "m2_read_only_contract_no_direct_promotion" in (
        local_run["promotion_gate"]["reasons"]
    )
    assert "required_selector_missing" in local_run["promotion_gate"]["reasons"]
    assert local_run["promotion_gate"]["required_missing_fields"] == ["price"]
    assert local_run["redaction_summary"] == {
        "schema_version": "browser_local_runner_redaction_summary.v1",
        "cookies_captured": False,
        "headers_captured": False,
        "bodies_captured": False,
        "query_parameters_retained": False,
        "url_query_fragment_removed": True,
        "stdout_stderr_tail_redacted": True,
        "sample_text_max_chars": 180,
        "files_written": False,
        "collection_resources_written": False,
    }
    assert "browser_local_runner_snapshot_replay_only" in local_run["blocked_reasons"]
    assert (
        local_run["audit_events"][0]["event"]
        == "browser_local_runner_snapshot_replay_completed"
    )
    assert local_run["audit_events"][0]["browser_started"] is False
    assert local_run["audit_events"][0]["collection_resources_written"] is False

    local_run_list_response = await client.get(
        "/api/automation/browser-diagnostic-job-runs",
        params={"project_id": project_id, "diagnostic_job_id": job["id"]},
    )
    assert local_run_list_response.status_code == 200
    local_run_list = local_run_list_response.json()
    assert local_run_list["total"] == 1
    assert local_run_list["browser_started"] is False
    assert local_run_list["files_written"] is False
    assert local_run_list["collection_resources_written"] is False
    assert local_run_list["items"][0]["id"] == local_run["id"]

    unconfirmed_probe_run_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "run_mode": "ephemeral_browser_harness_probe",
        },
    )
    assert unconfirmed_probe_run_response.status_code == 400
    assert (
        unconfirmed_probe_run_response.json()["detail"]
        == "browser_harness_probe_confirmation_required"
    )

    fake_harness = tmp_path / "browser-harness"
    fake_harness.write_text(
        """#!/usr/bin/env python3
import json
import sys

sys.stdin.read()
print(json.dumps({
    "ok": True,
    "page_info": {
        "url": "https://example.com/products/dynamic-bag?token=secret#frag",
        "title": "Dynamic Bag",
        "w": 1280,
        "h": 720,
        "sx": 0,
        "sy": 0,
        "pw": 1280,
        "ph": 1800,
    },
    "target_tab_closed": False,
}))
print(json.dumps({"target_tab_closed": True}))
""",
    )
    fake_harness.chmod(0o755)
    probe_run_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "run_mode": "ephemeral_browser_harness_probe",
            "confirm_real_browser_probe": True,
            "browser_harness_binary": str(fake_harness),
            "probe_timeout_seconds": 3,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Run fake browser-harness probe locally.",
        },
    )
    assert probe_run_response.status_code == 200
    probe_run = probe_run_response.json()
    assert probe_run["status"] == "completed_ephemeral_probe"
    assert probe_run["run_mode"] == "ephemeral_browser_harness_probe"
    assert probe_run["execution_started"] is True
    assert probe_run["browser_started"] is True
    assert probe_run["files_written"] is False
    assert probe_run["collection_resources_written"] is False
    assert probe_run["artifact_manifest"]["ephemeral_probe"] == {
        "schema_version": "browser_harness_ephemeral_probe.v1",
        "status": "completed",
        "binary": str(fake_harness),
        "exit_code": 0,
        "files_written": False,
        "object_storage_write": False,
        "target_tab_closed": True,
    }
    assert probe_run["network_observation_summary"]["browser_started"] is True
    assert probe_run["network_observation_summary"]["ephemeral_probe"]["page_info"][
        "url"
    ] == "https://example.com/products/dynamic-bag"
    assert (
        probe_run["network_observation_summary"]["ephemeral_probe"]["target_tab_closed"]
        is True
    )
    assert probe_run["network_metadata_summary"]["browser_started"] is True
    assert probe_run["network_metadata_summary"]["capture_headers"] is False
    assert probe_run["network_metadata_summary"]["capture_body"] is False
    assert probe_run["network_metadata_summary"]["ephemeral_probe"]["page_info"][
        "url"
    ] == "https://example.com/products/dynamic-bag"
    assert probe_run["error_summary"]["error_count"] == 0
    assert probe_run["promotion_gate"]["can_create_collection_resources"] is False
    assert "m2_read_only_contract_no_direct_promotion" in (
        probe_run["promotion_gate"]["reasons"]
    )
    assert "required_selector_missing" in probe_run["promotion_gate"]["reasons"]
    assert probe_run["promotion_gate"]["required_missing_fields"] == ["price"]
    assert probe_run["redaction_summary"]["cookies_captured"] is False
    assert probe_run["redaction_summary"]["headers_captured"] is False
    assert probe_run["redaction_summary"]["bodies_captured"] is False
    assert "browser_harness_ephemeral_probe_only" in probe_run["blocked_reasons"]
    assert (
        probe_run["audit_events"][0]["event"]
        == "browser_harness_ephemeral_probe_completed"
    )
    assert probe_run["audit_events"][0]["browser_started"] is True

    blocked_probe_run_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "run_mode": "ephemeral_browser_harness_probe",
            "confirm_real_browser_probe": True,
            "browser_harness_binary": str(tmp_path / "missing-browser-harness"),
            "probe_timeout_seconds": 3,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Run unavailable browser-harness probe locally.",
        },
    )
    assert blocked_probe_run_response.status_code == 200
    blocked_probe_run = blocked_probe_run_response.json()
    assert blocked_probe_run["status"] == "blocked_ephemeral_probe"
    assert blocked_probe_run["execution_started"] is True
    assert blocked_probe_run["browser_started"] is False
    assert blocked_probe_run["files_written"] is False
    assert blocked_probe_run["collection_resources_written"] is False
    assert blocked_probe_run["artifact_manifest"]["ephemeral_probe"]["status"] == "blocked"
    assert blocked_probe_run["network_metadata_summary"]["ephemeral_probe"]["status"] == (
        "blocked"
    )
    assert blocked_probe_run["promotion_gate"]["can_create_collection_resources"] is False
    assert blocked_probe_run["redaction_summary"]["cookies_captured"] is False
    assert "browser_harness_binary_unavailable" in blocked_probe_run["blocked_reasons"]

    redaction_case_harness = tmp_path / "browser-harness-redaction-case"
    redaction_case_harness.write_text(
        """#!/usr/bin/env python3
import sys

sys.stdin.read()
print("Authorization header observed during local probe")
print("Cookie header observed during local probe", file=sys.stderr)
raise SystemExit(2)
""",
    )
    redaction_case_harness.chmod(0o755)
    redaction_case_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "run_mode": "ephemeral_browser_harness_probe",
            "confirm_real_browser_probe": True,
            "browser_harness_binary": str(redaction_case_harness),
            "probe_timeout_seconds": 3,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Run redaction-case browser-harness probe locally.",
        },
    )
    assert redaction_case_response.status_code == 200
    redaction_case_run = redaction_case_response.json()
    assert redaction_case_run["status"] == "failed_ephemeral_probe"
    assert redaction_case_run["browser_started"] is False
    assert redaction_case_run["files_written"] is False
    assert redaction_case_run["collection_resources_written"] is False
    assert redaction_case_run["error_summary"]["errors"] == [
        "browser_harness_probe_nonzero_exit"
    ]
    redaction_probe = redaction_case_run["network_observation_summary"][
        "ephemeral_probe"
    ]
    assert redaction_probe["status"] == "failed"
    assert "[redacted-header]" in redaction_probe["stdout_tail"]
    assert "Authorization" not in redaction_probe["stdout_tail"]
    assert redaction_case_run["redaction_summary"]["headers_captured"] is False
    assert "browser_harness_probe_failed" in redaction_case_run["blocked_reasons"]

    timeout_case_harness = tmp_path / "browser-harness-timeout-case"
    timeout_case_harness.write_text(
        """#!/usr/bin/env python3
import sys
import time

sys.stdin.read()
print("probe still running", flush=True)
time.sleep(10)
""",
    )
    timeout_case_harness.chmod(0o755)
    timeout_case_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/local-run",
        json={
            "authorized": True,
            "confirm_execute": True,
            "run_mode": "ephemeral_browser_harness_probe",
            "confirm_real_browser_probe": True,
            "browser_harness_binary": str(timeout_case_harness),
            "probe_timeout_seconds": 3,
            "artifact_retention_days": 5,
            "max_preview_rows": 12,
            "include_screenshot": True,
            "include_trace_summary": False,
            "include_har_summary": True,
            "note": "Run timeout-case browser-harness probe locally.",
        },
    )
    assert timeout_case_response.status_code == 200
    timeout_case_run = timeout_case_response.json()
    assert timeout_case_run["status"] == "failed_ephemeral_probe"
    assert timeout_case_run["browser_started"] is False
    assert timeout_case_run["files_written"] is False
    assert timeout_case_run["collection_resources_written"] is False
    assert timeout_case_run["error_summary"]["errors"] == [
        "browser_harness_probe_timeout"
    ]
    assert timeout_case_run["network_metadata_summary"]["ephemeral_probe"]["status"] == (
        "failed"
    )
    assert timeout_case_run["promotion_gate"]["can_create_collection_resources"] is False
    assert timeout_case_run["redaction_summary"]["bodies_captured"] is False
    assert "browser_harness_probe_failed" in timeout_case_run["blocked_reasons"]

    post_probe_list_response = await client.get(
        "/api/automation/browser-diagnostic-job-runs",
        params={"project_id": project_id, "diagnostic_job_id": job["id"]},
    )
    assert post_probe_list_response.status_code == 200
    post_probe_list = post_probe_list_response.json()
    assert post_probe_list["total"] == 5
    assert post_probe_list["browser_started"] is True
    assert post_probe_list["files_written"] is False
    assert post_probe_list["collection_resources_written"] is False
    assert {item["id"] for item in post_probe_list["items"]} == {
        local_run["id"],
        probe_run["id"],
        blocked_probe_run["id"],
        redaction_case_run["id"],
        timeout_case_run["id"],
    }

    post_run_job_detail_response = await client.get(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}"
    )
    assert post_run_job_detail_response.status_code == 200
    assert post_run_job_detail_response.json()["run_started"] is False

    cancelled_job_response = await client.post(
        f"/api/automation/browser-diagnostic-jobs/{job['id']}/cancel"
    )
    assert cancelled_job_response.status_code == 200
    cancelled_job = cancelled_job_response.json()
    assert cancelled_job["status"] == "cancelled"
    assert cancelled_job["cancelled_at"] is not None
    assert cancelled_job["run_started"] is False
    assert any(
        event["event"] == "browser_diagnostic_job_cancelled"
        and event["run_started"] is False
        for event in cancelled_job["audit_events"]
    )

    sources_response = await client.get("/api/sources")
    assert sources_response.status_code == 200
    assert all(item["type"] != "browser_automation" for item in sources_response.json())


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
async def test_github_topic_source_derives_traceable_url(client: AsyncClient) -> None:
    project_id = await register_and_create_project(client)

    response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "GitHub Topic Radar: web-scraping",
            "type": "github_topic",
            "config": {"topic": "web-scraping", "max_results": 20},
        },
    )

    assert response.status_code == 201
    source = response.json()
    assert source["type"] == "github_topic"
    assert source["url"] == "https://github.com/topics/web-scraping"


@pytest.mark.asyncio
async def test_github_topic_radar_saves_tool_dataset_and_export(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureGitHubTopicCollector(BaseCollector):
        collector_type = "github_topic"
        collect_calls = 0

        def validate_config(self) -> dict[str, object]:
            return {
                "topic": self.config.get("topic", "web-scraping"),
                "max_results": self.config.get("max_results", 2),
            }

        async def test(self) -> CollectorTestResult:
            return CollectorTestResult(status="ok", message="ok", logs=[])

        async def collect(self) -> CollectionResult:
            self.__class__.collect_calls += 1
            if self.__class__.collect_calls == 1:
                repositories = [
                    {
                        "full_name": "browser-use/browser-use",
                        "html_url": "https://github.com/browser-use/browser-use",
                        "description": "Make websites accessible for AI agents",
                        "stargazers_count": 72000,
                        "forks_count": 8400,
                        "open_issues_count": 120,
                        "watchers_count": 72000,
                        "language": "Python",
                        "topics": ["browser-automation", "ai-agent"],
                        "license_spdx_id": "MIT",
                        "default_branch": "main",
                        "latest_release_tag": "v0.4.0",
                        "latest_release_published_at": "2026-06-18T02:00:00Z",
                        "readme_detected": True,
                        "readme_html_url": "https://github.com/browser-use/browser-use/blob/main/README.md",
                        "readme_size": 12000,
                        "issue_activity_open_count": 120,
                        "issue_activity_status": "active",
                        "commit_freshness_days": 1,
                        "commit_freshness_status": "fresh",
                        "archived": False,
                        "fork": False,
                        "pushed_at": "2026-06-18T00:00:00Z",
                        "updated_at": "2026-06-18T01:00:00Z",
                    },
                    {
                        "full_name": "scrapy/scrapy",
                        "html_url": "https://github.com/scrapy/scrapy",
                        "description": "A fast high-level web crawling framework",
                        "stargazers_count": 56000,
                        "forks_count": 11000,
                        "open_issues_count": 400,
                        "watchers_count": 56000,
                        "language": "Python",
                        "topics": ["crawler", "scraping"],
                        "license_spdx_id": "BSD-3-Clause",
                        "default_branch": "master",
                        "latest_release_tag": "2.12.0",
                        "latest_release_published_at": "2026-06-17T02:00:00Z",
                        "readme_detected": True,
                        "readme_html_url": "https://github.com/scrapy/scrapy/blob/master/README.rst",
                        "readme_size": 18000,
                        "issue_activity_open_count": 400,
                        "issue_activity_status": "active",
                        "commit_freshness_days": 2,
                        "commit_freshness_status": "fresh",
                        "archived": False,
                        "fork": False,
                        "pushed_at": "2026-06-17T00:00:00Z",
                        "updated_at": "2026-06-17T01:00:00Z",
                    },
                ]
            else:
                repositories = [
                    {
                        "full_name": "browser-use/browser-use",
                        "html_url": "https://github.com/browser-use/browser-use",
                        "description": "Make websites accessible for AI agents",
                        "stargazers_count": 72000,
                        "forks_count": 8500,
                        "open_issues_count": 135,
                        "watchers_count": 72000,
                        "language": "Python",
                        "topics": [],
                        "license_spdx_id": "MIT",
                        "default_branch": "main",
                        "latest_release_tag": "v0.4.0",
                        "latest_release_published_at": "2025-01-01T02:00:00Z",
                        "readme_detected": True,
                        "readme_html_url": None,
                        "readme_size": 12000,
                        "issue_activity_open_count": 135,
                        "issue_activity_status": "active",
                        "commit_freshness_days": 300,
                        "commit_freshness_status": "stale",
                        "archived": False,
                        "fork": False,
                        "pushed_at": "2026-06-18T00:00:00Z",
                        "updated_at": None,
                    }
                ]
            return CollectionResult(
                raw_records=[
                    CollectorRawRecord(
                        record_type="github_topic",
                        source_url="https://github.com/topics/web-scraping",
                        content={
                            "provider": "github",
                            "kind": "topic_search",
                            "topic": "web-scraping",
                            "total_count": len(repositories),
                            "repositories": repositories,
                        },
                    )
                ],
                logs=[],
                errors=[],
            )

    monkeypatch.setitem(
        collector_registry.COLLECTOR_REGISTRY,
        "github_topic",
        FixtureGitHubTopicCollector,
    )
    project_id = await register_and_create_project(client)

    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": project_id,
            "name": "GitHub Topic Radar: web-scraping",
            "type": "github_topic",
            "config": {"topic": "web-scraping", "max_results": 2},
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
    assert run["status"] == "success"

    preview_response = await client.post(
        "/api/automation/github-tool-dataset-preview",
        json={
            "authorized": True,
            "task_run_ids": [run["id"]],
            "fields": [
                "repo_full_name",
                "stars",
                "forks",
                "open_issues",
                "html_url",
                "language",
                "topics",
                "updated_at",
                "license_spdx_id",
                "default_branch",
                "latest_release_tag",
                "latest_release_published_at",
                "readme_detected",
                "readme_html_url",
                "issue_activity_open_count",
                "issue_activity_status",
                "commit_freshness_status",
            ],
            "max_rows": 10,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["summary"]["rows_count"] == 2
    assert preview["summary"]["matched_runs"] == 1
    assert preview["summary"]["selected_fields"] == [
        "repo_full_name",
        "stars",
        "forks",
        "open_issues",
        "html_url",
        "language",
        "topics",
        "updated_at",
        "license_spdx_id",
        "default_branch",
        "latest_release_tag",
        "latest_release_published_at",
        "readme_detected",
        "readme_html_url",
        "issue_activity_open_count",
        "issue_activity_status",
        "commit_freshness_status",
    ]
    assert preview["rows"][0]["values"]["repo_full_name"] == "browser-use/browser-use"
    assert preview["rows"][0]["values"]["stars"] == 72000
    assert preview["rows"][0]["values"]["license_spdx_id"] == "MIT"
    assert preview["rows"][0]["values"]["latest_release_tag"] == "v0.4.0"
    assert preview["rows"][0]["values"]["readme_detected"] is True
    assert preview["rows"][0]["values"]["issue_activity_open_count"] == 120
    assert preview["rows"][0]["values"]["commit_freshness_status"] == "fresh"
    assert preview["export_preview"]["schema"]["primary_key"] == "html_url"
    assert preview["export_preview"]["schema"]["schema_version"] == "github_tool_radar.v2"
    assert preview["export_preview"]["schema"]["field_sources"]["readme_detected"] == (
        "github.repository.readme.exists"
    )

    save_response = await client.post(
        "/api/automation/github-tool-dataset-save",
        json={
            "authorized": True,
            "name": "GitHub Tool Radar web-scraping",
            "description": "Tool radar dataset from GitHub topic.",
            "task_run_ids": [run["id"]],
            "fields": [
                "repo_full_name",
                "stars",
                "forks",
                "open_issues",
                "html_url",
                "language",
                "topics",
                "updated_at",
                "license_spdx_id",
                "default_branch",
                "latest_release_tag",
                "latest_release_published_at",
                "readme_detected",
                "readme_html_url",
                "issue_activity_open_count",
                "issue_activity_status",
                "commit_freshness_status",
            ],
            "max_rows": 10,
        },
    )
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["dataset"]["dataset_type"] == "github_tool_radar"
    assert saved["version"]["row_count"] == 2
    assert saved["version"]["selected_fields"] == [
        "repo_full_name",
        "stars",
        "forks",
        "open_issues",
        "html_url",
        "language",
        "topics",
        "updated_at",
        "license_spdx_id",
        "default_branch",
        "latest_release_tag",
        "latest_release_published_at",
        "readme_detected",
        "readme_html_url",
        "issue_activity_open_count",
        "issue_activity_status",
        "commit_freshness_status",
    ]
    assert saved["version"]["export_preview"]["schema"]["schema_version"] == (
        "github_tool_radar.v2"
    )
    assert saved["version"]["export_preview"]["schema"]["collector_schema_versions"] == [
        "github_repo.v3",
        "github_topic.v3",
    ]

    export_response = await client.post(
        "/api/automation/product-dataset-exports",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": saved["dataset"]["id"],
            "dataset_version_id": saved["version"]["id"],
            "export_format": "csv",
        },
    )
    assert export_response.status_code == 200
    export_job = export_response.json()
    assert export_job["row_count"] == 2
    assert export_job["download_url"]

    download_response = await client.get(export_job["download_url"])
    assert download_response.status_code == 200
    assert "repo_full_name" in download_response.text
    assert "browser-use/browser-use" in download_response.text

    second_run_response = await client.post(f"/api/tasks/{task['id']}/run")
    assert second_run_response.status_code == 201
    second_run = second_run_response.json()
    assert second_run["status"] == "success"

    drift_response = await client.post(
        "/api/automation/github-tool-drift-check",
        json={
            "authorized": True,
            "dataset_id": saved["dataset"]["id"],
            "dataset_version_id": saved["version"]["id"],
            "task_ids": [task["id"]],
            "completeness_drop_threshold_percent": 10,
            "freshness_grace_hours": 24,
        },
    )
    assert drift_response.status_code == 200
    drift = drift_response.json()
    assert drift["dataset"]["dataset_type"] == "github_tool_radar"
    assert drift["summary"] == {
        "requested_tasks": 1,
        "checked_tasks": 1,
        "blocked_tasks": 0,
        "warning_tasks": 0,
        "critical_tasks": 1,
        "stale_tasks": 0,
        "missing_field_tasks": 1,
        "drift_layers": {
            "completeness": 1,
            "field_missingness": 1,
            "forks": 1,
            "issue_activity": 1,
            "release_freshness": 1,
        },
        "run_started": False,
        "alert_created": False,
    }
    assert drift["items"][0]["latest_run_id"] == second_run["id"]
    assert drift["items"][0]["latest_completeness_percent"] == 82
    assert drift["items"][0]["completeness_drop_percent"] == 18
    assert drift["items"][0]["new_missing_fields"] == [
        "topics",
        "updated_at",
        "readme_html_url",
    ]
    assert drift["items"][0]["issues"] == [
        "completeness_drift_exceeded",
        "approved_fields_missing",
        "forks_changed",
        "issue_activity_changed",
        "release_freshness_stale",
    ]
    assert any(
        event["event"] == "github_tool_drift_task_checked"
        and event["run_started"] is False
        and event["alert_created"] is False
        and event["drift_layers"] == drift["summary"]["drift_layers"]
        for event in drift["audit_events"]
    )
    assert "不会启动采集" in drift["blocked_reasons"][0]

    drift_event_response = await client.post(
        "/api/automation/github-tool-drift-events",
        json={
            "authorized": True,
            "dataset_id": saved["dataset"]["id"],
            "dataset_version_id": saved["version"]["id"],
            "task_ids": [task["id"]],
            "completeness_drop_threshold_percent": 10,
            "freshness_grace_hours": 24,
            "note": "Saved from GitHub tool radar review.",
        },
    )
    assert drift_event_response.status_code == 200
    drift_event = drift_event_response.json()
    assert drift_event["event_type"] == "github_tool_radar_drift"
    assert drift_event["status"] == "critical"
    assert drift_event["summary"] == drift["summary"]
    assert drift_event["note"] == "Saved from GitHub tool radar review."
    assert any(
        event["event"] == "github_tool_drift_event_saved"
        and event["run_started"] is False
        and event["alert_created"] is False
        for event in drift_event["audit_events"]
    )

    report_response = await client.post(
        "/api/automation/github-tool-report",
        json={
            "authorized": True,
            "dataset_id": saved["dataset"]["id"],
            "dataset_version_id": saved["version"]["id"],
            "min_stars": 10000,
            "top_limit": 5,
        },
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["summary"] == {
        "repository_count": 2,
        "total_stars": 128000,
        "high_value_repositories": 2,
        "licensed_repositories": 2,
        "release_tagged_repositories": 2,
        "readme_documented_repositories": 2,
        "issue_active_repositories": 2,
        "fresh_commit_repositories": 2,
        "archived_repositories": 0,
        "fork_repositories": 0,
        "languages": {"Python": 2},
        "top_topics": {
            "ai-agent": 1,
            "browser-automation": 1,
            "crawler": 1,
            "scraping": 1,
        },
        "report_created": False,
        "run_started": False,
    }
    assert report["top_repositories"][0]["repo_full_name"] == "browser-use/browser-use"
    assert report["top_repositories"][0]["license_spdx_id"] == "MIT"
    assert report["top_repositories"][0]["latest_release_tag"] == "v0.4.0"
    assert report["top_repositories"][0]["readme_detected"] is True
    assert report["top_repositories"][0]["issue_activity_open_count"] == 120
    assert report["top_repositories"][0]["commit_freshness_status"] == "fresh"
    assert "browser-use/browser-use" in report["recommendations"][0]
    assert "MIT" in report["recommendations"][0]
    assert "README 已识别" in report["recommendations"][0]

    report_asset_response = await client.post(
        "/api/automation/github-tool-report-assets",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": saved["dataset"]["id"],
            "dataset_version_id": saved["version"]["id"],
            "min_stars": 10000,
            "top_limit": 5,
        },
    )
    assert report_asset_response.status_code == 201
    report_asset = report_asset_response.json()
    assert report_asset["summary"]["report_created"] is True
    assert report_asset["summary"]["run_started"] is False
    assert report_asset["notification_created"] is False
    assert report_asset["report"]["report_type"] == "github_tool_radar"
    assert report_asset["report"]["status"] == "generated"
    assert "GitHub Tool Radar web-scraping" in report_asset["report"]["title"]
    assert "browser-use/browser-use" in report_asset["report"]["content"]
    assert "v0.4.0" in report_asset["report"]["content"]
    assert "readme_documented_repositories" in report_asset["report"]["content"]
    assert "fresh_commit_repositories" in report_asset["report"]["content"]
    assert "github_tool_radar" in report_asset["report"]["content"]
    assert any(
        event["event"] == "github_tool_report_asset_created"
        and event["report_created"] is True
        and event["run_started"] is False
        and event["notification_created"] is False
        for event in report_asset["audit_events"]
    )
    assert "不会启动采集" in report_asset["blocked_reasons"][0]

    stored_report_response = await client.get(f"/api/reports/{report_asset['report']['id']}")
    assert stored_report_response.status_code == 200
    assert stored_report_response.json()["content"] == report_asset["report"]["content"]

    report_list_response = await client.get("/api/reports")
    assert report_list_response.status_code == 200
    assert any(
        item["id"] == report_asset["report"]["id"]
        and item["report_type"] == "github_tool_radar"
        for item in report_list_response.json()
    )


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
async def test_automation_product_fanout_reuses_one_source_when_duplicates_exist(
    client: AsyncClient,
) -> None:
    project_id = await register_and_create_project(client)
    for index in range(2):
        source_response = await client.post(
            "/api/sources",
            json={
                "project_id": project_id,
                "name": f"Duplicate Demo Carry Bag {index}",
                "type": "ecommerce_product_page",
                "url": "https://shop.example/products/demo-bag",
                "config": {
                    "url": "https://shop.example/products/demo-bag",
                    "fields": ["title", "price", "canonical_url"],
                    "platform_hint": "auto",
                },
                "schedule_cron": None,
            },
        )
        assert source_response.status_code == 201

    response = await client.post(
        "/api/automation/product-fanout-create",
        json={
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
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["created_sources"] == 0
    assert body["summary"]["reused_sources"] == 1
    assert body["persisted_sources"][0]["action"] == "reused"
    assert body["persisted_sources"][0]["task"]["status"] == "enabled"


@pytest.mark.asyncio
async def test_automation_product_batch_run_returns_field_completeness(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureEcommerceCollector(EcommerceProductPageCollector):
        async def collect(self) -> CollectionResult:
            url = str(self.config["url"])
            extracted_fields: dict[str, object]
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

    cleaning_rules = [
        {
            "field": "title",
            "operation": "strip_text",
            "description": "Trim product title whitespace.",
        },
        {
            "field": "price",
            "operation": "parse_decimal",
            "description": "Parse product price into a decimal number.",
        },
        {
            "field": "sku",
            "operation": "fill_default",
            "value": "UNKNOWN-SKU",
            "description": "Fill missing SKU values before export.",
        },
    ]
    dry_run_response = await client.post(
        "/api/automation/cleaning-plan-dry-run",
        json={
            "authorized": True,
            "task_run_ids": [item["run"]["id"] for item in run_items],
            "fields": ["title", "price", "sku", "canonical_url"],
            "rules": cleaning_rules,
            "max_rows": 10,
        },
    )
    assert dry_run_response.status_code == 200
    dry_run = dry_run_response.json()
    assert dry_run["summary"] == {
        "rows_count": 2,
        "rows_changed": 1,
        "rules_count": 3,
        "selected_fields": ["title", "price", "sku", "canonical_url"],
        "dataset_version_created": False,
        "cleaning_plan_created": False,
        "run_started": False,
    }
    assert dry_run["rows"][1]["before_values"]["sku"] is None
    assert dry_run["rows"][1]["after_values"]["sku"] == "UNKNOWN-SKU"
    assert dry_run["rows"][1]["missing_fields_after"] == ["price"]
    assert dry_run["cleaning_script"][-1] == "fill sku with default value UNKNOWN-SKU"
    assert "dry-run" in dry_run["audit_events"][0]["event"]

    datasets_after_dry_run_response = await client.get("/api/automation/product-datasets")
    assert datasets_after_dry_run_response.status_code == 200
    assert datasets_after_dry_run_response.json()["total"] == 0

    cleaning_plan_response = await client.post(
        "/api/automation/cleaning-plans",
        json={
            "authorized": True,
            "name": "SKU fallback cleaning plan",
            "task_run_ids": [item["run"]["id"] for item in run_items],
            "fields": ["title", "price", "sku", "canonical_url"],
            "rules": cleaning_rules,
            "max_rows": 10,
        },
    )
    assert cleaning_plan_response.status_code == 200
    cleaning_plan_result = cleaning_plan_response.json()
    assert cleaning_plan_result["cleaning_plan_created"] is True
    assert cleaning_plan_result["dataset_version_created"] is False
    assert cleaning_plan_result["run_started"] is False
    assert cleaning_plan_result["cleaning_plan"]["name"] == "SKU fallback cleaning plan"
    assert cleaning_plan_result["cleaning_plan"]["version_number"] == 1
    assert cleaning_plan_result["cleaning_plan"]["selected_fields"] == [
        "title",
        "price",
        "sku",
        "canonical_url",
    ]
    assert cleaning_plan_result["dry_run"]["summary"]["rows_changed"] == 1

    cleaning_plan_list_response = await client.get(
        "/api/automation/cleaning-plans",
        params={"project_id": project_id},
    )
    assert cleaning_plan_list_response.status_code == 200
    cleaning_plan_list = cleaning_plan_list_response.json()
    assert cleaning_plan_list["total"] == 1
    assert cleaning_plan_list["items"][0]["id"] == cleaning_plan_result["cleaning_plan"]["id"]

    deduped_batch_response = await client.post(
        "/api/automation/product-batch-run",
        json={
            "authorized": True,
            "max_tasks": 5,
            "task_ids": product_task_ids,
        },
    )
    assert deduped_batch_response.status_code == 200
    deduped_batch = deduped_batch_response.json()
    assert deduped_batch["summary"]["records_count"] == 2
    assert deduped_batch["summary"]["average_completeness_percent"] == 75
    assert all(
        event["deduplicated_source_records_reused"] is True
        for event in deduped_batch["audit_events"]
        if event["event"] == "product_batch_task_run_completed"
    )

    deduped_run_items = [
        item for item in deduped_batch["items"] if item["status"] == "run_completed"
    ]
    deduped_dataset_response = await client.post(
        "/api/automation/product-dataset-preview",
        json={
            "authorized": True,
            "task_run_ids": [item["run"]["id"] for item in deduped_run_items],
            "fields": ["title", "price", "sku", "canonical_url"],
            "max_rows": 10,
        },
    )
    assert deduped_dataset_response.status_code == 200
    deduped_dataset = deduped_dataset_response.json()
    assert deduped_dataset["summary"]["matched_runs"] == 2
    assert deduped_dataset["summary"]["rows_count"] == 2
    assert [row["values"]["title"] for row in deduped_dataset["rows"]] == [
        "Demo Carry Bag",
        "Weekend Tote",
    ]
    assert any(
        event["event"] == "product_dataset_run_reused_deduplicated_source_records"
        for event in deduped_dataset["audit_events"]
    )

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

    task_runs_before_schedule_response = await client.get(
        f"/api/tasks/{run_items[0]['task_id']}/runs"
    )
    assert task_runs_before_schedule_response.status_code == 200
    task_runs_before_schedule_count = len(task_runs_before_schedule_response.json())

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
    assert len(task_runs_after_schedule_response.json()) == task_runs_before_schedule_count

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
        "drift_layers": {
            "completeness": 1,
            "field_missingness": 1,
        },
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

    repeated_drift_event_response = await client.post(
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
    assert repeated_drift_event_response.status_code == 200
    repeated_drift_event = repeated_drift_event_response.json()
    assert repeated_drift_event["id"] == drift_event["id"]
    assert repeated_drift_event["run_started"] is False
    assert repeated_drift_event["alert_created"] is False
    assert any(
        event["event"] == "product_drift_event_reused"
        for event in repeated_drift_event["audit_events"]
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

    unconfirmed_export_response = await client.post(
        "/api/automation/product-dataset-exports",
        json={
            "authorized": True,
            "confirm_create": False,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "export_format": "csv",
        },
    )
    assert unconfirmed_export_response.status_code == 400
    assert unconfirmed_export_response.json()["detail"] == "dataset_export_confirmation_required"

    export_response = await client.post(
        "/api/automation/product-dataset-exports",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": first_save["dataset"]["id"],
            "dataset_version_id": first_save["version"]["id"],
            "export_format": "csv",
        },
    )
    assert export_response.status_code == 200
    export_job = export_response.json()
    assert export_job["dataset"]["id"] == first_save["dataset"]["id"]
    assert export_job["version"]["id"] == first_save["version"]["id"]
    assert export_job["export_format"] == "csv"
    assert export_job["status"] == "success"
    assert export_job["filename"].endswith(".csv")
    assert export_job["artifact_size_bytes"] > 0
    assert export_job["row_count"] == 2
    assert len(export_job["checksum_sha256"]) == 64
    assert export_job["download_url"].endswith(f"/exports/{export_job['id']}/download")
    assert any(
        event["event"] == "product_dataset_export_file_written"
        for event in export_job["audit_events"]
    )
    assert "下载接口" in export_job["blocked_reasons"][0]

    export_history_response = await client.get(
        f"/api/automation/product-datasets/{first_save['dataset']['id']}/exports",
        params={"dataset_version_id": first_save["version"]["id"]},
    )
    assert export_history_response.status_code == 200
    export_history = export_history_response.json()
    assert export_history["total"] == 1
    assert export_history["export_created"] is False
    assert export_history["run_started"] is False
    assert export_history["items"][0]["id"] == export_job["id"]

    export_download_response = await client.get(export_job["download_url"])
    assert export_download_response.status_code == 200
    assert export_download_response.headers["content-type"].startswith("text/csv")
    exported_csv = export_download_response.text
    assert "title,price,sku,canonical_url" in exported_csv
    assert "Demo Carry Bag" in exported_csv
    assert "Weekend Tote" in exported_csv

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

    repeated_drift_alert_rule_response = await client.post(
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
    assert repeated_drift_alert_rule_response.status_code == 200
    repeated_drift_alert_rule = repeated_drift_alert_rule_response.json()
    assert repeated_drift_alert_rule["alert_rule"]["id"] == drift_alert_rule["alert_rule"]["id"]
    assert repeated_drift_alert_rule["summary"]["alert_rule_created"] is False
    assert repeated_drift_alert_rule["summary"]["signal_created"] is False
    assert repeated_drift_alert_rule["summary"]["alert_event_created"] is False
    assert repeated_drift_alert_rule["summary"]["notification_created"] is False
    assert "已存在匹配的 DriftEvent 告警策略" in (
        repeated_drift_alert_rule["blocked_reasons"][0]
    )

    alert_rules_after_repeat_response = await client.get("/api/alert-rules")
    assert alert_rules_after_repeat_response.status_code == 200
    alert_rules_after_repeat = alert_rules_after_repeat_response.json()
    assert len(alert_rules_after_repeat) == 1
    assert alert_rules_after_repeat[0]["id"] == drift_alert_rule["alert_rule"]["id"]

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
    assert len(task_runs_after_drift_response.json()) == task_runs_before_schedule_count

    cleaned_save_response = await client.post(
        "/api/automation/product-dataset-save",
        json={
            "authorized": True,
            "name": "Cleaned Summer Bags Product Dataset",
            "description": "Dataset saved with reusable cleaning plan.",
            "task_run_ids": [item["run"]["id"] for item in run_items],
            "fields": ["title", "price", "sku", "canonical_url"],
            "max_rows": 10,
            "cleaning_plan_id": cleaning_plan_result["cleaning_plan"]["id"],
        },
    )
    assert cleaned_save_response.status_code == 200
    cleaned_save = cleaned_save_response.json()
    assert cleaned_save["version"]["version_number"] == 1
    assert cleaned_save["version"]["cleaning_plan_id"] == (
        cleaning_plan_result["cleaning_plan"]["id"]
    )
    assert cleaned_save["version"]["cleaning_script"][-1] == (
        "fill sku with default value UNKNOWN-SKU"
    )
    assert cleaned_save["version"]["export_preview"]["rows"][1]["sku"] == "UNKNOWN-SKU"
    assert cleaned_save["version"]["average_completeness_percent"] == 88
    assert any(
        event["event"] == "product_dataset_version_saved"
        and event["cleaning_plan_id"] == cleaning_plan_result["cleaning_plan"]["id"]
        for event in cleaned_save["audit_events"]
    )


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
    failed_logs = [log for log in run["logs"] if log["step"] == "collector_failed"]
    assert failed_logs[0]["failure_reason"] == "collector_failed"

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
