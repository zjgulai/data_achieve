from __future__ import annotations

import uuid

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.workflow_template import (
    WorkflowTemplate,
    WorkflowTemplateMutationRequest,
    WorkflowTemplateRevision,
)


def workflow_template_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
) -> Select[tuple[WorkflowTemplate]]:
    return (
        select(WorkflowTemplate)
        .where(
            WorkflowTemplate.workspace_id == workspace_id,
            WorkflowTemplate.project_id == project_id,
            WorkflowTemplate.id == workflow_template_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_project_for_workflow_template_mutation(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project | None:
    result = await session.execute(
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_workflow_template_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
) -> WorkflowTemplate | None:
    result = await session.execute(
        workflow_template_lock_statement(workspace_id, project_id, workflow_template_id)
    )
    return result.scalar_one_or_none()


async def get_workflow_template(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
) -> WorkflowTemplate | None:
    result = await session.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.workspace_id == workspace_id,
            WorkflowTemplate.project_id == project_id,
            WorkflowTemplate.id == workflow_template_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_template_by_key(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    template_key: str,
) -> WorkflowTemplate | None:
    result = await session.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.workspace_id == workspace_id,
            WorkflowTemplate.project_id == project_id,
            WorkflowTemplate.template_key == template_key,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_templates(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[WorkflowTemplate]:
    result = await session.execute(
        select(WorkflowTemplate)
        .where(
            WorkflowTemplate.workspace_id == workspace_id,
            WorkflowTemplate.project_id == project_id,
        )
        .order_by(desc(WorkflowTemplate.updated_at), desc(WorkflowTemplate.id))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_workflow_templates(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WorkflowTemplate)
        .where(
            WorkflowTemplate.workspace_id == workspace_id,
            WorkflowTemplate.project_id == project_id,
        )
    )
    return int(result.scalar_one())


async def get_workflow_template_revision(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> WorkflowTemplateRevision | None:
    result = await session.execute(
        select(WorkflowTemplateRevision).where(
            WorkflowTemplateRevision.workspace_id == workspace_id,
            WorkflowTemplateRevision.project_id == project_id,
            WorkflowTemplateRevision.workflow_template_id == workflow_template_id,
            WorkflowTemplateRevision.id == revision_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_template_revisions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[WorkflowTemplateRevision]:
    result = await session.execute(
        select(WorkflowTemplateRevision)
        .where(
            WorkflowTemplateRevision.workspace_id == workspace_id,
            WorkflowTemplateRevision.project_id == project_id,
            WorkflowTemplateRevision.workflow_template_id == workflow_template_id,
        )
        .order_by(
            desc(WorkflowTemplateRevision.revision_number),
            desc(WorkflowTemplateRevision.id),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_workflow_template_revisions(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WorkflowTemplateRevision)
        .where(
            WorkflowTemplateRevision.workspace_id == workspace_id,
            WorkflowTemplateRevision.project_id == project_id,
            WorkflowTemplateRevision.workflow_template_id == workflow_template_id,
        )
    )
    return int(result.scalar_one())


async def get_workflow_template_mutation_request(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowTemplateMutationRequest | None:
    result = await session.execute(
        select(WorkflowTemplateMutationRequest).where(
            WorkflowTemplateMutationRequest.workspace_id == workspace_id,
            WorkflowTemplateMutationRequest.created_by_user_id == created_by_user_id,
            WorkflowTemplateMutationRequest.idempotency_scope == idempotency_scope,
            WorkflowTemplateMutationRequest.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def add_workflow_template(
    session: AsyncSession,
    template: WorkflowTemplate,
) -> WorkflowTemplate:
    session.add(template)
    await session.flush()
    return template


async def add_workflow_template_revision(
    session: AsyncSession,
    revision: WorkflowTemplateRevision,
) -> WorkflowTemplateRevision:
    session.add(revision)
    await session.flush()
    return revision


async def add_workflow_template_mutation_request(
    session: AsyncSession,
    mutation: WorkflowTemplateMutationRequest,
) -> WorkflowTemplateMutationRequest:
    session.add(mutation)
    await session.flush()
    return mutation


__all__ = [
    "add_workflow_template",
    "add_workflow_template_mutation_request",
    "add_workflow_template_revision",
    "count_workflow_template_revisions",
    "count_workflow_templates",
    "get_workflow_template",
    "get_workflow_template_by_key",
    "get_workflow_template_for_update",
    "get_workflow_template_mutation_request",
    "get_workflow_template_revision",
    "list_workflow_template_revisions",
    "list_workflow_templates",
    "lock_project_for_workflow_template_mutation",
    "workflow_template_lock_statement",
]
