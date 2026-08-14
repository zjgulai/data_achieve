from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data_intelligence_hub.api.routes.alerts import (
    alert_events_router,
    alert_rules_router,
)
from data_intelligence_hub.api.routes.auth import router as auth_router
from data_intelligence_hub.api.routes.automation import router as automation_router
from data_intelligence_hub.api.routes.capabilities import router as capabilities_router
from data_intelligence_hub.api.routes.collectors import router as collectors_router
from data_intelligence_hub.api.routes.quick_collect import router as quick_collect_router
from data_intelligence_hub.api.routes.dashboard import router as dashboard_router
from data_intelligence_hub.api.routes.entities import router as entities_router
from data_intelligence_hub.api.routes.health import router as health_router
from data_intelligence_hub.api.routes.intelligence import router as intelligence_router
from data_intelligence_hub.api.routes.notifications import router as notifications_router
from data_intelligence_hub.api.routes.projects import router as projects_router
from data_intelligence_hub.api.routes.raw_records import router as raw_records_router
from data_intelligence_hub.api.routes.reports import router as reports_router
from data_intelligence_hub.api.routes.signals import router as signals_router
from data_intelligence_hub.api.routes.social_provider import router as social_provider_router
from data_intelligence_hub.api.routes.sources import router as sources_router
from data_intelligence_hub.api.routes.tasks import router as tasks_router
from data_intelligence_hub.api.routes.toolkit import router as toolkit_router
from data_intelligence_hub.api.routes.workflow_plans import (
    router as workflow_plans_router,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.scheduler import CollectionScheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler: CollectionScheduler | None = None
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

    app.include_router(health_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(dashboard_router, prefix="/api/dashboard")
    app.include_router(collectors_router, prefix="/api/collectors")
    app.include_router(quick_collect_router, prefix="/api/quick-collect")
    app.include_router(projects_router, prefix="/api/projects")
    app.include_router(workflow_plans_router, prefix="/api/projects")
    app.include_router(capabilities_router, prefix="/api/capabilities")
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
    return app


app = create_app()
