"""One-click quick collect: create ephemeral Source + Task, run immediately."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.repositories.collectors import get_collector_by_type
from data_intelligence_hub.services.collector_catalog import (
    ensure_collectors_seeded,
    validate_collector_config,
)
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import (
    CollectorConfigError,
    CollectorNotFoundError,
)

router = APIRouter(tags=["quick-collect"])

_ENDPOINT_TO_COLLECTOR: dict[str, str] = {
    "tikhub_tiktok_video_search": "tikhub_social",
    "tikhub_tiktok_user_posts": "tikhub_social",
    "tikhub_tiktok_hashtag_posts": "tikhub_social",
    "tikhub_instagram_search": "tikhub_social",
    "tikhub_instagram_user_posts": "tikhub_social",
    "tikhub_xiaohongshu_search": "tikhub_social",
    "apify_tiktok": "apify_actor",
    "apify_instagram": "apify_actor",
    "apify_youtube": "apify_actor",
    "github_repo": "github_repo",
    "github_topic": "github_topic",
    "public_feed": "public_feed",
    "generic_web": "generic_web",
}

# Apify endpoint → (actor_id, actor_input_builder)
_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {
    "apify_tiktok": (
        "clockworks/free-tiktok-scraper",
        {},
    ),
    "apify_instagram": (
        "apify/instagram-scraper",
        {},
    ),
    "apify_youtube": (
        "streamers/youtube-scraper",
        {},
    ),
}


class QuickCollectRequest(BaseModel):
    project_id: uuid.UUID
    endpoint_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=200)


class QuickCollectResponse(BaseModel):
    task_run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    records_count: int
    error_message: str | None


@router.post("", response_model=QuickCollectResponse, status_code=status.HTTP_201_CREATED)
async def quick_collect(
    body: QuickCollectRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> QuickCollectResponse:
    """Create an ephemeral Source + Task and run one collection immediately.

    Returns the completed (or failed) TaskRun synchronously.
    Suitable for small quick-collect requests (up to ~30 s) from the console UI.
    """
    collector_type = _ENDPOINT_TO_COLLECTOR.get(body.endpoint_type)
    if collector_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown endpoint_type: {body.endpoint_type!r}",
        )

    await ensure_collectors_seeded(session)
    collector_db = await get_collector_by_type(session, collector_type)
    if collector_db is None or not collector_db.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collector {collector_type!r} is not available",
        )

    config: dict[str, Any] = {"endpoint_type": body.endpoint_type, **body.params}

    apify_defaults = _APIFY_ENDPOINT_DEFAULTS.get(body.endpoint_type)
    if apify_defaults is not None:
        actor_id, base_input = apify_defaults
        actor_input = {**base_input, **body.params}
        config = {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": body.params.get("maxItems", 10),
            "max_total_charge_usd": body.params.get("max_total_charge_usd", 1.0),
        }

    try:
        validated = validate_collector_config(collector_type, config)
    except (CollectorConfigError, CollectorNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collector config: {exc}",
        ) from exc

    label = (body.label or body.endpoint_type).strip()[:200]

    source = Source(
        workspace_id=context.workspace.id,
        project_id=body.project_id,
        name=f"[quick] {label}",
        type=collector_type,
        url=None,
        config=validated,
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=context.workspace.id,
        project_id=body.project_id,
        source_id=source.id,
        collector_type=collector_type,
        name=f"[quick] {label}",
        schedule_cron=None,
        status="enabled",
        config=validated,
    )
    session.add(task)
    await session.flush()
    source_id = source.id
    task_id = task.id
    await session.commit()

    try:
        run: TaskRun = await execute_collection_task(session, context.workspace, task)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collection failed: {exc}",
        ) from exc

    return QuickCollectResponse(
        task_run_id=run.id,
        task_id=task_id,
        source_id=source_id,
        status=run.status,
        records_count=run.records_count,
        error_message=run.error_message,
    )
