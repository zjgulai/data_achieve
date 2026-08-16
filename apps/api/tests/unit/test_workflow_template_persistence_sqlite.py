from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    WorkflowPlan,
    WorkflowVersion,
)
from data_intelligence_hub.models.workflow_template import (
    WorkflowTemplate,
    WorkflowTemplateMutationRequest,
    WorkflowTemplateRevision,
)
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.schemas.workflow_template_persistence import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateInstantiateRequest,
    WorkflowTemplateMetadataUpdateRequest,
    WorkflowTemplateRevisionCreateRequest,
)
from data_intelligence_hub.services.exceptions import (
    WorkflowPlanIdempotencyConflictError,
    WorkflowTemplateNotEditableError,
    WorkflowTemplateNotFoundError,
    WorkflowTemplateRevisionConflictError,
    WorkflowTemplateRevisionInvalidError,
)
from data_intelligence_hub.services.workflow_planner import persistence, template_persistence
from data_intelligence_hub.services.workflow_planner.template_persistence import (
    append_workflow_template_revision,
    create_workflow_template,
    get_workflow_template_detail,
    instantiate_workflow_plan_from_template,
    list_workflow_templates_for_project,
    update_workflow_template_metadata,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "periodic_monitoring_request_v1.json"
)
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _definition() -> PlanningInput:
    return PlanningInput.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


class _Database:
    def __init__(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.project_id = project_id
        self.user_id = user_id


@pytest_asyncio.fixture()
async def database(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[_Database]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        project_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"template-{user_id}@example.com",
                    password_hash="not-a-real-secret",
                    name="Template User",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Template Workspace",
                    slug=f"template-{workspace_id}",
                    owner_id=user_id,
                ),
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role="member",
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    owner_id=user_id,
                    name="Template Project",
                    description=None,
                    domain="social",
                    status="active",
                ),
                CapabilityCatalogHead(
                    singleton_key="global",
                    current_revision_id=None,
                    head_version=0,
                ),
            ]
        )
        await session.commit()

        async def sqlite_scope_insert(
            scoped_session: AsyncSession,
            values: dict[str, object],
        ) -> uuid.UUID | None:
            existing = (
                await scoped_session.execute(
                    select(MonitoringScope).where(
                        MonitoringScope.project_id == values["project_id"],
                        MonitoringScope.scope_key == values["scope_key"],
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return None
            scope = MonitoringScope(**values)
            scoped_session.add(scope)
            await scoped_session.flush()
            return scope.id

        monkeypatch.setattr(
            persistence,
            "insert_monitoring_scope_on_conflict",
            sqlite_scope_insert,
        )
        yield _Database(session, workspace_id, project_id, user_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_template_create_revision_append_and_stale_conflict(database: _Database) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Acme",
            template_key="acme",
            definition=_definition(),
        ),
        idempotency_key="template-create-key-0001",
        request_id="template-create-request",
        generated_at=NOW,
    )
    assert created.database_write is True
    assert created.revision is not None
    current_revision = created.revision.id

    replay = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Acme",
            template_key="acme",
            definition=_definition(),
        ),
        idempotency_key="template-create-key-0001",
        request_id="template-create-request-replay",
        generated_at=NOW,
    )
    assert replay.idempotent_replay is True
    assert replay.database_write is False

    with pytest.raises(WorkflowPlanIdempotencyConflictError):
        await create_workflow_template(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateCreateRequest(
                name="Different",
                template_key="different",
                definition=_definition(),
            ),
            idempotency_key="template-create-key-0001",
            request_id="template-create-request-conflict",
            generated_at=NOW,
        )

    with pytest.raises(WorkflowTemplateRevisionConflictError):
        await append_workflow_template_revision(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            workflow_template_id=created.template.id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateRevisionCreateRequest(
                expected_revision_id=uuid.uuid4(),
                definition=_definition(),
            ),
            idempotency_key="template-revision-key-0001",
            request_id="template-revision-request",
            generated_at=NOW,
        )

    appended = await append_workflow_template_revision(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateRevisionCreateRequest(
            expected_revision_id=current_revision,
            definition=_definition(),
        ),
        idempotency_key="template-revision-key-0002",
        request_id="template-revision-request-2",
        generated_at=NOW,
    )
    assert appended.revision is not None
    assert appended.revision.revision_number == 2
    assert (
        await database.session.scalar(
            select(func.count()).select_from(WorkflowTemplateRevision)
        )
        == 2
    )
    assert (
        await database.session.scalar(
            select(func.count()).select_from(WorkflowTemplateMutationRequest)
        )
        == 2
    )


@pytest.mark.asyncio
async def test_template_metadata_and_instantiation_bind_selected_revision(
    database: _Database,
) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Acme",
            template_key="acme-metadata",
            description="initial",
            definition=_definition(),
        ),
        idempotency_key="template-create-key-0002",
        request_id="template-create-request-2",
        generated_at=NOW,
    )
    assert created.revision is not None
    updated = await update_workflow_template_metadata(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateMetadataUpdateRequest(
            expected_revision_id=created.revision.id,
            name="Acme renamed",
        ),
        idempotency_key="template-metadata-key-0001",
        request_id="template-metadata-request",
        generated_at=NOW,
    )
    assert updated.template.name == "Acme renamed"
    assert updated.revision is None

    cleared = await update_workflow_template_metadata(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateMetadataUpdateRequest(
            expected_revision_id=created.revision.id,
            description=None,
        ),
        idempotency_key="template-metadata-key-0002",
        request_id="template-metadata-clear-request",
        generated_at=NOW,
    )
    assert cleared.template.description is None
    assert cleared.revision is None

    instantiated = await instantiate_workflow_plan_from_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateInstantiateRequest(
            revision_id=created.revision.id,
            name="Plan from Acme",
        ),
        idempotency_key="template-instantiate-key-0001",
        request_id="template-instantiate-request",
        generated_at=NOW,
    )
    assert instantiated.plan.workflow_template_id == created.template.id
    assert instantiated.plan.workflow_template_revision_id == created.revision.id
    assert instantiated.version.workflow_template_id == created.template.id
    assert instantiated.version.workflow_template_revision_id == created.revision.id
    assert await database.session.scalar(select(func.count()).select_from(WorkflowPlan)) == 1
    assert await database.session.scalar(select(func.count()).select_from(WorkflowVersion)) == 1

    listed = await list_workflow_templates_for_project(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
    )
    assert listed.total == 1
    assert listed.items[0].current_revision_id == created.revision.id


@pytest.mark.asyncio
async def test_template_instantiation_same_key_different_revision_conflicts(
    database: _Database,
) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Revision idempotency",
            template_key="revision-idempotency",
            definition=_definition(),
        ),
        idempotency_key="template-idempotency-create-0001",
        request_id="template-idempotency-create",
        generated_at=NOW,
    )
    assert created.revision is not None
    appended = await append_workflow_template_revision(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateRevisionCreateRequest(
            expected_revision_id=created.revision.id,
            definition=_definition(),
        ),
        idempotency_key="template-idempotency-revision-0001",
        request_id="template-idempotency-revision",
        generated_at=NOW,
    )
    assert appended.revision is not None

    await instantiate_workflow_plan_from_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateInstantiateRequest(
            revision_id=created.revision.id,
            name="Plan from revision one",
        ),
        idempotency_key="template-idempotency-instantiate-0001",
        request_id="template-idempotency-instantiate-one",
        generated_at=NOW,
    )

    with pytest.raises(WorkflowPlanIdempotencyConflictError):
        await instantiate_workflow_plan_from_template(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            workflow_template_id=created.template.id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateInstantiateRequest(
                revision_id=appended.revision.id,
                name="Plan from revision two",
            ),
            idempotency_key="template-idempotency-instantiate-0001",
            request_id="template-idempotency-instantiate-two",
            generated_at=NOW,
        )

    assert await database.session.scalar(select(func.count()).select_from(WorkflowPlan)) == 1


@pytest.mark.asyncio
async def test_template_instantiation_replays_after_template_is_archived(
    database: _Database,
) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Replay",
            template_key="replay-after-archive",
            definition=_definition(),
        ),
        idempotency_key="template-replay-create-0001",
        request_id="template-replay-create-request",
        generated_at=NOW,
    )
    assert created.revision is not None
    payload = WorkflowTemplateInstantiateRequest(
        revision_id=created.revision.id,
        name="Replay plan",
    )
    first = await instantiate_workflow_plan_from_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=payload,
        idempotency_key="template-replay-instantiate-0001",
        request_id="template-replay-instantiate-request",
        generated_at=NOW,
    )
    template = await database.session.get(WorkflowTemplate, created.template.id)
    assert template is not None
    template.status = "archived"
    await database.session.commit()

    replay = await instantiate_workflow_plan_from_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        workflow_template_id=created.template.id,
        created_by_user_id=database.user_id,
        payload=payload,
        idempotency_key="template-replay-instantiate-0001",
        request_id="template-replay-instantiate-request",
        generated_at=NOW,
    )

    assert replay.idempotent_replay is True
    assert replay.database_write is False
    assert replay.plan.id == first.plan.id
    assert await database.session.scalar(select(func.count()).select_from(WorkflowPlan)) == 1


@pytest.mark.asyncio
async def test_template_create_rolls_back_header_revision_and_ledger(
    database: _Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_ledger(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("injected_template_ledger_failure")

    monkeypatch.setattr(
        template_persistence,
        "add_workflow_template_mutation_request",
        fail_ledger,
    )
    with pytest.raises(RuntimeError, match="injected_template_ledger_failure"):
        await create_workflow_template(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateCreateRequest(
                name="Rollback",
                template_key="rollback",
                definition=_definition(),
            ),
            idempotency_key="template-rollback-key-0001",
            request_id="template-rollback-request",
            generated_at=NOW,
        )

    assert (
        await database.session.scalar(
            select(func.count()).select_from(WorkflowTemplateRevision)
        )
        == 0
    )
    assert (
        await database.session.scalar(
            select(func.count()).select_from(WorkflowTemplateMutationRequest)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_template_rejects_archived_mutations_and_cross_project_lookup(
    database: _Database,
) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Archived",
            template_key="archived",
            definition=_definition(),
        ),
        idempotency_key="template-archived-key-0001",
        request_id="template-archived-request",
        generated_at=NOW,
    )
    assert created.revision is not None
    template = await database.session.get(WorkflowTemplate, created.template.id)
    assert template is not None
    template.status = "archived"
    await database.session.commit()

    with pytest.raises(WorkflowTemplateNotEditableError):
        await append_workflow_template_revision(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            workflow_template_id=created.template.id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateRevisionCreateRequest(
                expected_revision_id=created.revision.id,
                definition=_definition(),
            ),
            idempotency_key="template-archived-revision-0001",
            request_id="template-archived-revision-request",
            generated_at=NOW,
        )

    with pytest.raises(WorkflowTemplateNotEditableError):
        await instantiate_workflow_plan_from_template(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            workflow_template_id=created.template.id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateInstantiateRequest(
                revision_id=created.revision.id,
                name="Archived plan",
            ),
            idempotency_key="template-archived-instantiate-0001",
            request_id="template-archived-instantiate-request",
            generated_at=NOW,
        )

    other_project_id = uuid.uuid4()
    database.session.add(
        Project(
            id=other_project_id,
            workspace_id=database.workspace_id,
            owner_id=database.user_id,
            name="Other Template Project",
            description=None,
            domain="social",
            status="active",
        )
    )
    await database.session.commit()
    with pytest.raises(WorkflowTemplateNotFoundError):
        await get_workflow_template_detail(
            database.session,
            workspace_id=database.workspace_id,
            project_id=other_project_id,
            workflow_template_id=created.template.id,
        )


@pytest.mark.asyncio
async def test_template_instantiation_rejects_corrupt_revision_definition(
    database: _Database,
) -> None:
    created = await create_workflow_template(
        database.session,
        workspace_id=database.workspace_id,
        project_id=database.project_id,
        created_by_user_id=database.user_id,
        payload=WorkflowTemplateCreateRequest(
            name="Corrupt",
            template_key="corrupt",
            definition=_definition(),
        ),
        idempotency_key="template-corrupt-key-0001",
        request_id="template-corrupt-request",
        generated_at=NOW,
    )
    assert created.revision is not None
    revision = await database.session.get(WorkflowTemplateRevision, created.revision.id)
    assert revision is not None
    revision.definition = {"not": "a PlanningInput"}
    await database.session.commit()

    with pytest.raises(WorkflowTemplateRevisionInvalidError):
        await instantiate_workflow_plan_from_template(
            database.session,
            workspace_id=database.workspace_id,
            project_id=database.project_id,
            workflow_template_id=created.template.id,
            created_by_user_id=database.user_id,
            payload=WorkflowTemplateInstantiateRequest(
                revision_id=created.revision.id,
                name="Corrupt plan",
            ),
            idempotency_key="template-corrupt-instantiate-0001",
            request_id="template-corrupt-instantiate-request",
            generated_at=NOW,
        )

    assert await database.session.scalar(select(func.count()).select_from(WorkflowPlan)) == 0
