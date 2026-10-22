from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from data_intelligence_hub.agents.shusuo.router import router as shusuo_router
from data_intelligence_hub.agents.tiktok_cdo.router import router as tiktok_cdo_router
from data_intelligence_hub.api.routes.alerts import (
    alert_events_router,
    alert_rules_router,
)
from data_intelligence_hub.api.routes.answer import router as answer_router
from data_intelligence_hub.api.routes.auth import router as auth_router
from data_intelligence_hub.api.routes.automation import router as automation_router
from data_intelligence_hub.api.routes.capabilities import router as capabilities_router
from data_intelligence_hub.api.routes.capability_discovery import (
    router as capability_discovery_router,
)
from data_intelligence_hub.api.routes.capability_governance import (
    router as capability_governance_router,
)
from data_intelligence_hub.api.routes.collectors import router as collectors_router
from data_intelligence_hub.api.routes.dashboard import router as dashboard_router
from data_intelligence_hub.api.routes.enrichment import router as enrichment_router
from data_intelligence_hub.api.routes.entities import router as entities_router
from data_intelligence_hub.api.routes.health import router as health_router
from data_intelligence_hub.api.routes.intelligence import router as intelligence_router
from data_intelligence_hub.api.routes.monitors import router as monitors_router
from data_intelligence_hub.api.routes.notifications import router as notifications_router
from data_intelligence_hub.api.routes.platform_credentials import (
    router as platform_credentials_router,
)
from data_intelligence_hub.api.routes.platform_packages import (
    router as platform_packages_router,
)
from data_intelligence_hub.api.routes.project_api_keys import (
    router as project_api_keys_router,
)
from data_intelligence_hub.api.routes.projects import router as projects_router
from data_intelligence_hub.api.routes.quick_collect import router as quick_collect_router
from data_intelligence_hub.api.routes.raw_records import router as raw_records_router
from data_intelligence_hub.api.routes.reports import router as reports_router
from data_intelligence_hub.api.routes.research import router as research_router
from data_intelligence_hub.api.routes.runs import router as runs_router
from data_intelligence_hub.api.routes.signals import router as signals_router
from data_intelligence_hub.api.routes.social_provider import router as social_provider_router
from data_intelligence_hub.api.routes.sources import router as sources_router
from data_intelligence_hub.api.routes.tasks import router as tasks_router
from data_intelligence_hub.api.routes.tiktok_tools import (
    router as tiktok_tools_router,
)
from data_intelligence_hub.api.routes.tool_catalog import router as tool_catalog_router
from data_intelligence_hub.api.routes.toolkit import router as toolkit_router
from data_intelligence_hub.api.routes.tools import router as tools_router
from data_intelligence_hub.api.routes.usage import router as usage_router
from data_intelligence_hub.api.routes.webhooks import router as webhooks_router
from data_intelligence_hub.api.routes.workflow_plans import (
    router as workflow_plans_router,
)
from data_intelligence_hub.api.routes.workflow_runs import (
    router as workflow_runs_router,
)
from data_intelligence_hub.api.routes.workspaces import router as workspaces_router
from data_intelligence_hub.collectors.outbound_policy import (
    validate_collection_http_grants,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.core.logging import configure_logging
from data_intelligence_hub.mcp_runtime import (
    BearerTokenMiddleware,
    mcp_app,
    mcp_server,
)
from data_intelligence_hub.scheduler import CollectionScheduler
from data_intelligence_hub.services.enrichment_worker import EnrichmentWorkerRuntime
from data_intelligence_hub.services.run_worker_runtime import RunWorkerRuntime
from data_intelligence_hub.services.webhook_worker import WebhookWorkerRuntime

logger = structlog.get_logger(__name__)


def warn_on_invalid_http_grants(grants: list[dict[str, Any]]) -> None:
    """启动时校验域名授权配置。

    配置有问题时记录一条 warning，并列出全部问题。
    配置问题不阻断启动：生产环境可能暂时没有授权。
    """
    issues = validate_collection_http_grants(grants)
    if not issues:
        return
    logger.warning(
        "collection_http_grants_invalid",
        issue_count=len(issues),
        issues=issues,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler: CollectionScheduler | None = None
    run_worker: RunWorkerRuntime | None = None
    enrichment_worker = EnrichmentWorkerRuntime(session_factory=async_session_factory)
    webhook_worker = WebhookWorkerRuntime(session_factory=async_session_factory)
    async with mcp_server.session_manager.run():
        # 富集与 Webhook 投递都使用持久表。启动后由 worker 扫描待处理行。
        recovered = await enrichment_worker.recover_interrupted()
        app.state.enrichment_worker = enrichment_worker
        app.state.webhook_worker = webhook_worker
        enrichment_worker.start()
        webhook_worker.start()
        if recovered:
            logger.info("enrichment_jobs_recovered", count=recovered)
        if settings.scheduler_enabled:
            scheduler = CollectionScheduler(
                session_factory=async_session_factory,
                poll_interval_seconds=settings.scheduler_poll_interval_seconds,
            )
            app.state.collection_scheduler = scheduler
            scheduler.start()
        # 运行队列 worker 默认关闭。测试与本地开发不启动后台循环。
        if settings.run_worker_enabled:
            run_worker = RunWorkerRuntime(session_factory=async_session_factory)
            app.state.run_worker = run_worker
            run_worker.start()
        try:
            yield
        finally:
            await webhook_worker.stop()
            await enrichment_worker.stop()
            if run_worker is not None:
                await run_worker.stop()
            if scheduler is not None:
                await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    # 关掉异常回溯里的局部变量渲染。默认配置会把密钥等取值打进日志，
    # 详见 core/logging.py 的说明。
    configure_logging()
    # 域名授权配置有问题时只告警，不阻断启动。
    warn_on_invalid_http_grants(settings.collection_http_grants)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 这一条路径的 request 校验失败必须返回固定且不含输入的 422。
    # 契约 docs/api/api-contract-data-intelligence-hub-stable.md:943/973 要求
    # detail 固定为 youtube_read_plan_request_invalid，且不回显输入——
    # 该请求体里可能带 api_key 或 credential_reference。
    # 其他路径继续走 FastAPI 默认处理器，全局错误合同不变。
    _sanitized_422_paths = {
        "/api/automation/social-provider-youtube-read-plan",
    }

    @app.exception_handler(RequestValidationError)
    async def _sanitize_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if request.url.path in _sanitized_422_paths:
            return JSONResponse(
                status_code=422,
                content={"detail": "youtube_read_plan_request_invalid"},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    app.include_router(health_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(workspaces_router, prefix="/api/workspaces")
    app.include_router(dashboard_router, prefix="/api/dashboard")
    app.include_router(collectors_router, prefix="/api/collectors")
    app.include_router(quick_collect_router, prefix="/api/quick-collect")
    app.include_router(projects_router, prefix="/api/projects")
    app.include_router(project_api_keys_router, prefix="/api/projects")
    app.include_router(workflow_plans_router, prefix="/api/projects")
    # 这三个模块早已实现并有集成测试覆盖，但从未挂载，
    # 于是它们的端点一律返回 404——测试断言 404 != 201 的根因。
    # 2026-10-16 归因发现，随 b339f45 批量入库时漏了接线。
    app.include_router(workflow_runs_router, prefix="/api/projects")
    app.include_router(capabilities_router, prefix="/api/capabilities")
    app.include_router(capability_discovery_router, prefix="/api/capabilities")
    # governance 的路径自带前缀段（/candidates、/imports 等），
    # 而它的对外契约是 /api/capabilities/governance/*，故此处补齐该段。
    app.include_router(capability_governance_router, prefix="/api/capabilities/governance")
    app.include_router(sources_router, prefix="/api/sources")
    app.include_router(tasks_router, prefix="/api/tasks")
    app.include_router(raw_records_router, prefix="/api/raw-records")
    app.include_router(entities_router, prefix="/api/entities")
    app.include_router(signals_router, prefix="/api/signals")
    app.include_router(intelligence_router, prefix="/api/intelligence")
    app.include_router(automation_router, prefix="/api/automation")
    app.include_router(social_provider_router, prefix="/api/automation")
    app.include_router(toolkit_router, prefix="/api/toolkit")
    app.include_router(reports_router, prefix="/api/reports")
    app.include_router(runs_router, prefix="/api/runs")
    app.include_router(alert_rules_router, prefix="/api/alert-rules")
    app.include_router(alert_events_router, prefix="/api/alert-events")
    app.include_router(notifications_router, prefix="/api/notifications")
    app.include_router(platform_credentials_router, prefix="/api/settings")
    app.include_router(platform_packages_router, prefix="/api/platform-packages")
    app.include_router(monitors_router, prefix="/api/monitors")
    app.include_router(webhooks_router, prefix="/api/webhooks")
    app.include_router(answer_router, prefix="/api/answer")
    app.include_router(research_router, prefix="/api/research")
    app.include_router(enrichment_router, prefix="/api/enrichments")
    app.include_router(tools_router, prefix="/api/tools")
    app.include_router(usage_router, prefix="/api/usage")
    app.include_router(tool_catalog_router, prefix="/api/tool-catalog")
    app.include_router(shusuo_router, prefix="/api/agents/shusuo")
    app.include_router(tiktok_cdo_router, prefix="/api/agents/tiktok-cdo")
    app.include_router(tiktok_tools_router, prefix="/api/tiktok/tools")
    app.mount("/mcp", BearerTokenMiddleware(mcp_app))
    return app


app = create_app()
