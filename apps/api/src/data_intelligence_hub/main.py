from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
from data_intelligence_hub.api.routes.entities import router as entities_router
from data_intelligence_hub.api.routes.health import router as health_router
from data_intelligence_hub.api.routes.intelligence import router as intelligence_router
from data_intelligence_hub.api.routes.notifications import router as notifications_router
from data_intelligence_hub.api.routes.platform_credentials import (
    router as platform_credentials_router,
)
from data_intelligence_hub.api.routes.platform_packages import (
    router as platform_packages_router,
)
from data_intelligence_hub.api.routes.projects import router as projects_router
from data_intelligence_hub.api.routes.quick_collect import router as quick_collect_router
from data_intelligence_hub.api.routes.raw_records import router as raw_records_router
from data_intelligence_hub.api.routes.reports import router as reports_router
from data_intelligence_hub.api.routes.signals import router as signals_router
from data_intelligence_hub.api.routes.social_provider import router as social_provider_router
from data_intelligence_hub.api.routes.sources import router as sources_router
from data_intelligence_hub.api.routes.tasks import router as tasks_router
from data_intelligence_hub.api.routes.tiktok_tools import (
    router as tiktok_tools_router,
)
from data_intelligence_hub.api.routes.toolkit import router as toolkit_router
from data_intelligence_hub.api.routes.tool_catalog import router as tool_catalog_router
from data_intelligence_hub.api.routes.tools import router as tools_router
from data_intelligence_hub.api.routes.workflow_plans import (
    router as workflow_plans_router,
)
from data_intelligence_hub.api.routes.workflow_runs import (
    router as workflow_runs_router,
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler: CollectionScheduler | None = None
    async with mcp_server.session_manager.run():
        if settings.scheduler_enabled:
            scheduler = CollectionScheduler(
                session_factory=async_session_factory,
                poll_interval_seconds=settings.scheduler_poll_interval_seconds,
            )
            app.state.collection_scheduler = scheduler
            scheduler.start()
        yield
        if scheduler is not None:
            await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    # 关掉异常回溯里的局部变量渲染。默认配置会把密钥等取值打进日志，
    # 详见 core/logging.py 的说明。
    configure_logging()
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
    app.include_router(dashboard_router, prefix="/api/dashboard")
    app.include_router(collectors_router, prefix="/api/collectors")
    app.include_router(quick_collect_router, prefix="/api/quick-collect")
    app.include_router(projects_router, prefix="/api/projects")
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
    app.include_router(alert_rules_router, prefix="/api/alert-rules")
    app.include_router(alert_events_router, prefix="/api/alert-events")
    app.include_router(notifications_router, prefix="/api/notifications")
    app.include_router(platform_credentials_router, prefix="/api/settings")
    app.include_router(platform_packages_router, prefix="/api/platform-packages")
    app.include_router(tools_router, prefix="/api/tools")
    app.include_router(tool_catalog_router, prefix="/api/tool-catalog")
    app.include_router(shusuo_router, prefix="/api/agents/shusuo")
    app.include_router(tiktok_cdo_router, prefix="/api/agents/tiktok-cdo")
    app.include_router(tiktok_tools_router, prefix="/api/tiktok/tools")
    app.mount("/mcp", BearerTokenMiddleware(mcp_app))
    return app


app = create_app()
