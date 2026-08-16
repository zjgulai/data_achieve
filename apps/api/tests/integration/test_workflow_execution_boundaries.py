from __future__ import annotations

import importlib
import json
import socket
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest as MaterializationLedger,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories import datasets, raw_records
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowLineageMaterializationRequest,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services import (
    browser_structure_diagnostic,
    llm_service,
    social_provider,
    task_service,
)
from data_intelligence_hub.services.workflow_execution import execution
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    LoadedWorkflowFixtureProfile,
    WorkflowFixtureStepReceipt,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    execute_workflow_fixture_step as execute_registered_fixture_step,
)
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_execution.materialization import (
    materialize_workflow_lineage,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
NOW = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BoundaryContext:
    session: AsyncSession
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    preview_fingerprint: str


def _planning_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def _catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
    )


@pytest_asyncio.fixture()
async def boundary_context() -> AsyncIterator[BoundaryContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=_planning_input(),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-execution-boundary",
    )
    preview = result.preview
    plan = WorkflowPlan(
        id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        name="Workflow Execution Boundary",
        flow_mode=preview.flow_mode.value,
        status="active",
        current_version_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    version = WorkflowVersion(
        id=version_id,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        created_by_user_id=user_id,
        version_number=1,
        planning_status=preview.planning_status.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions={key.value: value for key, value in preview.query_versions.items()},
        fingerprint_payload=result.fingerprint_payload.model_dump(mode="json"),
        normalized_input=preview.normalized_input.model_dump(mode="json"),
        plan_payload=serialize_preview_snapshot(preview),
        preview_fingerprint=preview.preview_fingerprint,
        created_at=NOW,
    )
    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email="workflow-execution-boundary@example.com",
                    password_hash="not-used",
                    name="Workflow Execution Boundary",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Workflow Execution Boundary",
                    slug=f"workflow-execution-boundary-{workspace_id.hex[:8]}",
                    owner_id=user_id,
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    owner_id=user_id,
                    name="Workflow Execution Boundary",
                    description=None,
                    domain="social",
                    status="active",
                ),
                plan,
                version,
            ]
        )
        await session.flush()
        plan.current_version_id = version_id
        await session.commit()
        yield BoundaryContext(
            session=session,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            preview_fingerprint=preview.preview_fingerprint,
        )
    await engine.dispose()


def _forbidden_call(
    calls: list[str],
    label: str,
) -> Callable[..., Any]:
    def fail(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        calls.append(label)
        raise AssertionError(f"forbidden_boundary_called:{label}")

    return fail


def _install_external_guards(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[str],
) -> None:
    guarded_functions = (
        (social_provider, "prepare_social_provider_gate"),
        (social_provider, "prepare_social_execution_dry_run"),
        (social_provider, "prepare_social_task_run_approval_template"),
        (task_service, "run_task_now"),
        (browser_structure_diagnostic, "build_browser_structure_diagnostic"),
        (raw_records, "list_raw_records"),
        (raw_records, "get_raw_record"),
        (datasets, "create_dataset_drift_event"),
        (datasets, "create_dataset_export_job"),
    )
    for module, name in guarded_functions:
        monkeypatch.setattr(module, name, _forbidden_call(calls, name))
    monkeypatch.setattr(
        llm_service.LLMService,
        "summarize_intelligence",
        _forbidden_call(calls, "summarize_intelligence"),
    )
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        _forbidden_call(calls, "httpx.AsyncClient"),
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        _forbidden_call(calls, "socket.create_connection"),
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _forbidden_call(calls, "socket.getaddrinfo"),
    )
    for name in (
        "resolve_credentials",
        "run_actor",
        "run_browser",
        "call_llm",
        "write_raw_record",
        "write_dataset",
        "execute_workflow_fixture_fallback",
        "execute_workflow_fixture_shadow",
    ):
        monkeypatch.setattr(
            execution,
            name,
            _forbidden_call(calls, name),
            raising=False,
        )

    original_import_module = importlib.import_module
    guarded_roots = {
        "apify_client",
        "googleapiclient",
        "openai",
        "playwright",
        "praw",
    }

    def guarded_import_module(name: str, package: str | None = None) -> Any:
        if name.split(".", 1)[0] in guarded_roots:
            calls.append(f"import:{name}")
            raise AssertionError(f"forbidden_optional_sdk_import:{name}")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import_module)


async def _legacy_row_counts(session: AsyncSession) -> dict[str, int]:
    models = (Source, CollectionTask, TaskRun, RawRecord, Dataset)
    counts: dict[str, int] = {}
    for model in models:
        result = await session.execute(select(func.count()).select_from(model))
        counts[model.__tablename__] = int(result.scalar_one())
    return counts


@pytest.mark.asyncio
async def test_create_and_replay_call_only_primary_and_leave_legacy_tables_zero(
    boundary_context: BoundaryContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = boundary_context
    forbidden_calls: list[str] = []
    primary_calls: list[str] = []
    _install_external_guards(monkeypatch, forbidden_calls)
    original_primary = execute_registered_fixture_step

    def measured_primary(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        primary_calls.append(contract.step.step_ref)
        return original_primary(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", measured_primary)
    before = await _legacy_row_counts(context.session)
    payload = WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=context.preview_fingerprint,
        fixture_profile_id="fixture-primary-v1",
    )
    created = await execution.create_workflow_fixture_run(
        context.session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_plan_id=context.plan_id,
        workflow_version_id=context.version_id,
        created_by_user_id=context.user_id,
        payload=payload,
        idempotency_key="workflow-boundary-key-0001",
        request_id="workflow-boundary-create",
        generated_at=NOW,
    )
    calls_after_create = tuple(primary_calls)
    replayed = await execution.create_workflow_fixture_run(
        context.session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_plan_id=context.plan_id,
        workflow_version_id=context.version_id,
        created_by_user_id=context.user_id,
        payload=payload,
        idempotency_key="workflow-boundary-key-0001",
        request_id="workflow-boundary-replay",
        generated_at=NOW,
    )
    after = await _legacy_row_counts(context.session)

    assert (
        before
        == after
        == {
            "sources": 0,
            "collection_tasks": 0,
            "task_runs": 0,
            "raw_records": 0,
            "datasets": 0,
        }
    )
    assert len(calls_after_create) == created.run.total_steps == 3
    assert len(set(calls_after_create)) == 3
    assert tuple(primary_calls) == calls_after_create
    assert replayed.idempotent_replay is True
    assert replayed.database_write is False
    assert replayed.run.id == created.run.id
    assert all(item.route_plan_snapshot.fallback_implementations for item in created.steps)
    assert forbidden_calls == []
    for response in (created, replayed):
        assert response.provider_call is False
        assert response.provider_call_attempted is False
        assert response.credential_read_attempted is False
        assert response.actor_run is False
        assert response.browser_run is False
        assert response.llm_call is False
        assert response.raw_record_write is False
        assert response.dataset_write is False


@pytest.mark.asyncio
async def test_materialization_writes_only_v2_assets_and_calls_no_external_boundary(
    boundary_context: BoundaryContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = boundary_context
    forbidden_calls: list[str] = []
    _install_external_guards(monkeypatch, forbidden_calls)
    created = await execution.create_workflow_fixture_run(
        context.session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_plan_id=context.plan_id,
        workflow_version_id=context.version_id,
        created_by_user_id=context.user_id,
        payload=WorkflowFixtureRunCreateRequest(
            expected_preview_fingerprint=context.preview_fingerprint,
            fixture_profile_id="fixture-primary-payload-v1",
        ),
        idempotency_key="workflow-boundary-payload-run-0001",
        request_id="workflow-boundary-payload-run",
        generated_at=NOW,
    )
    preview = build_workflow_lineage_preview(
        created.run,
        created.steps,
        payload_bound=True,
    )
    result = await materialize_workflow_lineage(
        context.session,
        workspace_id=context.workspace_id,
        project_id=context.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=context.user_id,
        payload=WorkflowLineageMaterializationRequest(
            dataset_name="boundary-materialized-dataset",
            expected_lineage_digest=preview.lineage_digest,
        ),
        idempotency_key="workflow-boundary-materialization-0001",
        request_id="workflow-boundary-materialization",
        generated_at=NOW,
    )

    assert result.provider_call is False
    assert result.credential_read_attempted is False
    assert forbidden_calls == []
    for model in (Source, CollectionTask, TaskRun):
        count = await context.session.execute(select(func.count()).select_from(model))
        assert int(count.scalar_one()) == 0
    counts = []
    for materialized_model in (RawRecord, Dataset, DatasetVersion, MaterializationLedger):
        count = await context.session.execute(select(func.count()).select_from(materialized_model))
        counts.append(int(count.scalar_one()))
    assert counts == [created.run.records_count, 1, 1, 1]


def test_execution_import_graph_excludes_live_and_legacy_lanes() -> None:
    execution_source = Path(execution.__file__).read_text(encoding="utf-8")
    forbidden_dependencies = (
        "httpx",
        "socket",
        "social_provider",
        "collector_service",
        "task_service",
        "llm_service",
        "repositories.raw_records",
        "repositories.datasets",
        "CredentialResolver",
        "apify_client",
        "googleapiclient",
        "playwright",
        "praw",
    )
    assert all(item not in execution_source for item in forbidden_dependencies)
    assert "execute_workflow_fixture_fallback" not in execution_source
    assert "execute_workflow_fixture_shadow" not in execution_source
