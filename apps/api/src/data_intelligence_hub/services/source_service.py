from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.sources import get_source, list_sources
from data_intelligence_hub.repositories.tasks import get_task_by_source
from data_intelligence_hub.schemas.source import SourceCreateRequest, SourceUpdateRequest
from data_intelligence_hub.services.collector_catalog import (
    require_collector,
    validate_collector_config,
)
from data_intelligence_hub.services.exceptions import ProjectNotFoundError, SourceNotFoundError


async def get_sources(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    source_type: str | None,
) -> list[Source]:
    return await list_sources(
        session,
        workspace.id,
        project_id=project_id,
        source_type=source_type,
    )


async def create_source(
    session: AsyncSession,
    workspace: Workspace,
    payload: SourceCreateRequest,
) -> Source:
    project = await get_project(session, workspace.id, payload.project_id)
    if project is None:
        raise ProjectNotFoundError

    await require_collector(session, payload.type)
    config = validate_collector_config(payload.type, payload.config)
    source = Source(
        workspace_id=workspace.id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        type=payload.type,
        url=payload.url or _source_url_from_config(payload.type, config),
        config=config,
        schedule_cron=payload.schedule_cron,
        enabled=False,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def get_source_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID,
) -> Source:
    source = await get_source(session, workspace.id, source_id)
    if source is None:
        raise SourceNotFoundError
    return source


async def update_source(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID,
    payload: SourceUpdateRequest,
) -> Source:
    source = await get_source_or_raise(session, workspace, source_id)
    updates = payload.model_dump(exclude_unset=True)
    config_changed = "config" in updates and updates["config"] is not None
    url_was_provided = "url" in updates
    if config_changed:
        updates["config"] = validate_collector_config(source.type, updates["config"])
        if not url_was_provided:
            updates["url"] = _source_url_from_config(source.type, updates["config"])
    if "name" in updates and isinstance(updates["name"], str):
        updates["name"] = updates["name"].strip()

    for field, value in updates.items():
        setattr(source, field, value)

    task = await get_task_by_source(session, source.id)
    if task is not None:
        task.name = source.name
        task.schedule_cron = source.schedule_cron
        task.config = source.config

    await session.commit()
    await session.refresh(source)
    return source


async def test_source_config(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID,
) -> Source:
    source = await get_source_or_raise(session, workspace, source_id)
    await require_collector(session, source.type)
    source.config = validate_collector_config(source.type, source.config)
    await session.commit()
    await session.refresh(source)
    return source


async def enable_source(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID,
) -> tuple[Source, CollectionTask]:
    source = await test_source_config(session, workspace, source_id)
    task = await get_task_by_source(session, source.id)
    if task is None:
        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=source.project_id,
            source_id=source.id,
            collector_type=source.type,
            name=source.name,
            schedule_cron=source.schedule_cron,
            status="enabled",
            config=source.config,
        )
        session.add(task)
    else:
        task.status = "enabled"
        task.name = source.name
        task.schedule_cron = source.schedule_cron
        task.config = source.config

    source.enabled = True
    await session.commit()
    await session.refresh(source)
    await session.refresh(task)
    return source, task


async def disable_source(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID,
) -> tuple[Source, CollectionTask | None]:
    source = await get_source_or_raise(session, workspace, source_id)
    task = await get_task_by_source(session, source.id)
    source.enabled = False
    if task is not None:
        task.status = "disabled"
    await session.commit()
    await session.refresh(source)
    if task is not None:
        await session.refresh(task)
    return source, task


def _source_url_from_config(source_type: str, config: dict[str, object]) -> str | None:
    if source_type == "github_repo":
        return f"https://github.com/{config['owner']}/{config['repo']}"
    if source_type == "generic_web":
        return str(config["url"])
    if source_type in {"ecommerce_product_discovery", "ecommerce_product_page"}:
        return str(config["url"])
    return None
