from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import timedelta
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy import func, null, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
)
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest as MaterializationLedger,
)
from data_intelligence_hub.repositories.workflow_lineage import (
    add_dataset_version,
    add_materialization_request,
    add_raw_records,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
)
from data_intelligence_hub.schemas.workflow_lineage import WorkflowLineageMaterializationRequest
from data_intelligence_hub.services.workflow_execution import materialization
from data_intelligence_hub.services.workflow_execution.execution import (
    create_workflow_fixture_run,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixturePayloadUnboundError,
)
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_execution.materialization import (
    WorkflowMaterializationDatasetConflictError,
    WorkflowMaterializationIdempotencyConflictError,
    WorkflowMaterializationLedgerInvalidError,
    WorkflowMaterializationLineageDigestConflictError,
    WorkflowMaterializationPayloadInvalidError,
    WorkflowMaterializationProjectNotActiveError,
    WorkflowRunAlreadyMaterializedError,
    materialize_workflow_lineage,
)
from tests.integration.test_workflow_execution_service import (
    NOW,
    SeededVersion,
    _seed_resolved_version,
)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _prepare(
    session: AsyncSession,
    *,
    profile_id: str = "fixture-primary-payload-v1",
) -> tuple[
    SeededVersion,
    WorkflowFixtureRunCreateResponse,
    WorkflowLineageMaterializationRequest,
]:
    seed = await _seed_resolved_version(session)
    created = await create_workflow_fixture_run(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_plan_id=seed.plan_id,
        workflow_version_id=seed.version_id,
        created_by_user_id=seed.user_id,
        payload=WorkflowFixtureRunCreateRequest(
            expected_preview_fingerprint=seed.version.preview_fingerprint,
            fixture_profile_id=profile_id,
        ),
        idempotency_key=f"payload-bound-run-{profile_id}-0001",
        request_id="payload-bound-run",
        generated_at=NOW,
    )
    preview = build_workflow_lineage_preview(
        created.run,
        created.steps,
        payload_bound=profile_id == "fixture-primary-payload-v1",
    )
    request = WorkflowLineageMaterializationRequest(
        dataset_name="workflow-market-monitoring",
        expected_lineage_digest=preview.lineage_digest,
    )
    return seed, created, request


@pytest.mark.asyncio
async def test_payload_bound_run_materializes_atomically_and_replays_without_writes(
    session: AsyncSession,
) -> None:
    seed = await _seed_resolved_version(session)
    created = await create_workflow_fixture_run(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_plan_id=seed.plan_id,
        workflow_version_id=seed.version_id,
        created_by_user_id=seed.user_id,
        payload=WorkflowFixtureRunCreateRequest(
            expected_preview_fingerprint=seed.version.preview_fingerprint,
            fixture_profile_id="fixture-primary-payload-v1",
        ),
        idempotency_key="payload-bound-run-key-0001",
        request_id="payload-bound-run",
        generated_at=NOW,
    )
    preview = build_workflow_lineage_preview(
        created.run,
        created.steps,
        payload_bound=True,
    )
    request = WorkflowLineageMaterializationRequest(
        dataset_name="workflow-market-monitoring",
        expected_lineage_digest=preview.lineage_digest,
    )

    first = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="workflow-materialization-key-0001",
        request_id="materialization-first",
        generated_at=NOW,
    )
    replay = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="workflow-materialization-key-0001",
        request_id="materialization-replay",
        generated_at=NOW,
    )

    assert first.database_write is True
    assert replay.database_write is False
    assert replay.idempotent_replay is True
    assert replay.dataset_version_id == first.dataset_version_id
    assert len(first.raw_record_ids) == created.run.records_count
    assert await _count(session, Dataset) == 1
    assert await _count(session, DatasetVersion) == 1
    assert await _count(session, RawRecord) == created.run.records_count
    assert await _count(session, MaterializationLedger) == 1

    with pytest.raises(WorkflowRunAlreadyMaterializedError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="workflow-materialization-key-0002",
            request_id="materialization-conflict",
            generated_at=NOW,
        )


@pytest.mark.parametrize(
    "phase",
    ["before_raw", "after_raw", "after_version", "after_ledger"],
)
@pytest.mark.asyncio
async def test_injected_failure_rolls_back_all_materialized_assets(
    phase: str,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, created, request = await _prepare(session)
    original_raw = add_raw_records
    original_version = add_dataset_version
    original_ledger = add_materialization_request

    async def raw_failure(
        target: AsyncSession,
        records: Sequence[RawRecord],
    ) -> tuple[RawRecord, ...]:
        if phase == "before_raw":
            raise RuntimeError(phase)
        result = await original_raw(target, records)
        if phase == "after_raw":
            raise RuntimeError(phase)
        return result

    async def version_failure(
        target: AsyncSession,
        version: DatasetVersion,
    ) -> DatasetVersion:
        result = await original_version(target, version)
        if phase == "after_version":
            raise RuntimeError(phase)
        return result

    async def ledger_failure(
        target: AsyncSession,
        ledger: MaterializationLedger,
    ) -> MaterializationLedger:
        result = await original_ledger(target, ledger)
        if phase == "after_ledger":
            raise RuntimeError(phase)
        return result

    monkeypatch.setattr(materialization, "add_raw_records", raw_failure)
    monkeypatch.setattr(materialization, "add_dataset_version", version_failure)
    monkeypatch.setattr(materialization, "add_materialization_request", ledger_failure)

    with pytest.raises(RuntimeError, match=phase):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="workflow-materialization-rollback-key-0001",
            request_id="materialization-rollback",
            generated_at=NOW,
        )

    assert await _count(session, Dataset) == 0
    assert await _count(session, DatasetVersion) == 0
    assert await _count(session, RawRecord) == 0
    assert await _count(session, MaterializationLedger) == 0


@pytest.mark.parametrize(
    "tamper",
    ["step_and_run_count", "fixture_content_hash", "step_status", "run_count"],
)
@pytest.mark.asyncio
async def test_tampered_step_receipt_fails_before_any_asset_write(
    tamper: str,
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    run = await session.get(WorkflowRun, created.run.id)
    step = (
        (
            await session.execute(
                select(StepRun)
                .where(StepRun.workflow_run_id == created.run.id)
                .order_by(StepRun.sequence)
            )
        )
        .scalars()
        .first()
    )
    assert run is not None and step is not None
    if tamper == "step_and_run_count":
        step.records_count += 1
        run.records_count += 1
    elif tamper == "fixture_content_hash":
        step.fixture_content_hash = "sha256:" + "f" * 64
    elif tamper == "step_status":
        step.status = "pending"
    else:
        run.records_count += 1
    if tamper == "step_status":
        with pytest.raises(IntegrityError, match="ck_step_runs_state_snapshot"):
            await session.commit()
        await session.rollback()
    else:
        await session.commit()

        with pytest.raises(WorkflowMaterializationPayloadInvalidError):
            await materialize_workflow_lineage(
                session,
                workspace_id=seed.workspace_id,
                project_id=seed.project_id,
                workflow_run_id=created.run.id,
                created_by_user_id=seed.user_id,
                payload=request,
                idempotency_key=f"tampered-receipt-{tamper}-key-0001",
                request_id="tampered-receipt",
                generated_at=NOW,
            )

    assert await _count(session, Dataset) == 0
    assert await _count(session, DatasetVersion) == 0
    assert await _count(session, RawRecord) == 0
    assert await _count(session, MaterializationLedger) == 0


@pytest.mark.asyncio
async def test_existing_dataset_history_is_unchanged_when_new_version_rolls_back(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, created, request = await _prepare(session)
    dataset = Dataset(
        id=uuid.uuid4(),
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        name=request.dataset_name,
        dataset_type="workflow_materialized",
        status="active",
        description="existing history",
    )
    session.add(dataset)
    await session.flush()
    historical_version = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        created_by_user_id=seed.user_id,
        cleaning_plan_id=None,
        source_workflow_run_id=None,
        source_workflow_step_run_ids=null(),
        source_raw_record_ids=null(),
        lineage_contract_version=None,
        version_number=1,
        source_task_run_ids=[],
        selected_fields=["historical"],
        cleaning_script=[],
        rows=[{"historical": True}],
        export_preview={"row_count": 1},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=NOW,
    )
    session.add(historical_version)
    await session.commit()
    original_ledger = add_materialization_request

    async def fail_after_ledger(
        target: AsyncSession,
        ledger: MaterializationLedger,
    ) -> MaterializationLedger:
        await original_ledger(target, ledger)
        raise RuntimeError("existing_dataset_failure")

    monkeypatch.setattr(materialization, "add_materialization_request", fail_after_ledger)
    with pytest.raises(RuntimeError, match="existing_dataset_failure"):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="existing-dataset-rollback-key-0001",
            request_id="existing-dataset-rollback",
            generated_at=NOW,
        )

    await session.refresh(dataset)
    remaining_versions = (
        (
            await session.execute(
                select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
            )
        )
        .scalars()
        .all()
    )
    assert dataset.description == "existing history"
    assert dataset.status == "active"
    assert [item.id for item in remaining_versions] == [historical_version.id]
    assert await _count(session, RawRecord) == 0
    assert await _count(session, MaterializationLedger) == 0


@pytest.mark.parametrize(
    ("payload_field", "payload_value", "response_status"),
    [
        ("materialization_id", "random_uuid", 201),
        ("workflow_run_id", "random_uuid", 201),
        ("dataset_id", "random_uuid", 201),
        ("dataset_version_id", "random_uuid", 201),
        ("raw_record_ids", "random_uuid_list", 201),
        ("records_count", "increment", 201),
        ("dataset_version_number", "increment", 201),
        ("lineage_digest", "sha256:" + "f" * 64, 201),
        ("database_write", False, 201),
        (None, None, 200),
    ],
)
@pytest.mark.asyncio
async def test_replay_fails_closed_on_tampered_ledger_response(
    payload_field: str | None,
    payload_value: object,
    response_status: int,
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    first = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="tampered-ledger-replay-key-0001",
        request_id="tampered-ledger-first",
        generated_at=NOW,
    )
    ledger = (await session.execute(select(MaterializationLedger))).scalar_one()
    response_payload = dict(ledger.response_payload)
    if payload_field is not None:
        if payload_value == "random_uuid":
            response_payload[payload_field] = str(uuid.uuid4())
        elif payload_value == "random_uuid_list":
            raw_record_ids = list(response_payload["raw_record_ids"])
            raw_record_ids[0] = str(uuid.uuid4())
            response_payload[payload_field] = raw_record_ids
        elif payload_value == "increment":
            response_payload[payload_field] = int(response_payload[payload_field]) + 1
        else:
            response_payload[payload_field] = payload_value
        if payload_field == "database_write":
            response_payload.update(
                {
                    "idempotent_replay": True,
                    "raw_record_write": False,
                    "dataset_write": False,
                }
            )
    ledger.response_payload = response_payload
    ledger.response_status = response_status
    await session.commit()

    with pytest.raises(WorkflowMaterializationLedgerInvalidError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="tampered-ledger-replay-key-0001",
            request_id="tampered-ledger-replay",
            generated_at=NOW,
        )
    assert await _count(session, DatasetVersion) == 1
    assert await _count(session, RawRecord) == first.records_count
    assert await _count(session, MaterializationLedger) == 1


@pytest.mark.parametrize("tamper", ["missing", "source_raw_record_ids"])
@pytest.mark.asyncio
async def test_replay_fails_closed_when_dataset_version_is_missing_or_mismatched(
    tamper: str,
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="dataset-version-replay-key-0001",
        request_id="dataset-version-first",
        generated_at=NOW,
    )
    version = (await session.execute(select(DatasetVersion))).scalar_one()
    if tamper == "missing":
        await session.delete(version)
    else:
        version.source_raw_record_ids = [str(uuid.uuid4())]
    await session.commit()

    with pytest.raises(WorkflowMaterializationLedgerInvalidError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="dataset-version-replay-key-0001",
            request_id="dataset-version-replay",
            generated_at=NOW,
        )


@pytest.mark.parametrize("tamper", ["missing", "content"])
@pytest.mark.asyncio
async def test_replay_fails_closed_when_raw_record_is_missing_or_mismatched(
    tamper: str,
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="raw-record-replay-key-0001",
        request_id="raw-record-first",
        generated_at=NOW,
    )
    record = (await session.execute(select(RawRecord).limit(1))).scalar_one()
    if tamper == "missing":
        await session.delete(record)
    else:
        record.content = cast(dict[str, object], {"tampered": True})
    await session.commit()

    with pytest.raises(WorkflowMaterializationLedgerInvalidError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="raw-record-replay-key-0001",
            request_id="raw-record-replay",
            generated_at=NOW,
        )


@pytest.mark.parametrize("tamper", ["record_type", "source_url", "collected_at"])
@pytest.mark.asyncio
async def test_replay_fails_closed_when_raw_record_metadata_is_mismatched(
    tamper: str,
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="raw-record-metadata-replay-key-0001",
        request_id="raw-record-metadata-first",
        generated_at=NOW,
    )
    record = (await session.execute(select(RawRecord).limit(1))).scalar_one()
    if tamper == "record_type":
        record.record_type = "tampered_record"
    elif tamper == "source_url":
        record.source_url = "https://example.invalid/tampered"
    else:
        record.collected_at += timedelta(seconds=1)
    await session.commit()

    with pytest.raises(WorkflowMaterializationLedgerInvalidError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="raw-record-metadata-replay-key-0001",
            request_id="raw-record-metadata-replay",
            generated_at=NOW,
        )


@pytest.mark.asyncio
async def test_replay_fails_closed_when_raw_record_is_reassigned_to_another_step(
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    first = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="raw-record-step-replay-key-0001",
        request_id="raw-record-step-first",
        generated_at=NOW,
    )
    records = (
        await session.execute(
            select(RawRecord).where(RawRecord.id.in_(first.raw_record_ids))
        )
    ).scalars().all()
    target = records[0]
    replacement_step_id = next(
        record.workflow_step_run_id
        for record in records
        if record.workflow_step_run_id != target.workflow_step_run_id
    )
    target.workflow_step_run_id = replacement_step_id
    await session.commit()

    with pytest.raises(WorkflowMaterializationLedgerInvalidError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="raw-record-step-replay-key-0001",
            request_id="raw-record-step-replay",
            generated_at=NOW,
        )


@pytest.mark.asyncio
async def test_unbound_profile_and_wrong_digest_fail_before_asset_write(
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session, profile_id="fixture-primary-v1")
    with pytest.raises(WorkflowFixturePayloadUnboundError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="workflow-materialization-unbound-key-0001",
            request_id="materialization-unbound",
            generated_at=NOW,
        )
    assert await _count(session, DatasetVersion) == 0
    assert await _count(session, RawRecord) == 0


@pytest.mark.asyncio
async def test_wrong_lineage_digest_and_same_key_different_body_conflict(
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    wrong = request.model_copy(update={"expected_lineage_digest": "sha256:" + "f" * 64})
    with pytest.raises(WorkflowMaterializationLineageDigestConflictError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=wrong,
            idempotency_key="workflow-materialization-digest-key-0001",
            request_id="materialization-digest",
            generated_at=NOW,
        )
    assert await _count(session, DatasetVersion) == 0

    await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="workflow-materialization-key-0003",
        request_id="materialization-create",
        generated_at=NOW,
    )
    with pytest.raises(WorkflowMaterializationIdempotencyConflictError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request.model_copy(update={"dataset_name": "different-dataset"}),
            idempotency_key="workflow-materialization-key-0003",
            request_id="materialization-idempotency-conflict",
            generated_at=NOW,
        )


@pytest.mark.asyncio
async def test_dataset_conflict_preserves_existing_dataset_and_archived_replay(
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    session.add(
        Dataset(
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            name=request.dataset_name,
            dataset_type="different_type",
            status="active",
            description=None,
        )
    )
    await session.commit()
    with pytest.raises(
        WorkflowMaterializationDatasetConflictError,
        match="^dataset_type_conflict$",
    ):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="workflow-materialization-dataset-key-0001",
            request_id="materialization-dataset-conflict",
            generated_at=NOW,
        )
    assert await _count(session, Dataset) == 1
    assert await _count(session, DatasetVersion) == 0


@pytest.mark.asyncio
async def test_archived_project_allows_exact_replay_but_rejects_new_key(
    session: AsyncSession,
) -> None:
    seed, created, request = await _prepare(session)
    first = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="workflow-materialization-archive-key-0001",
        request_id="materialization-before-archive",
        generated_at=NOW,
    )
    project = await session.get(Project, seed.project_id)
    assert project is not None
    project.status = "archived"
    await session.commit()
    replay = await materialize_workflow_lineage(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=created.run.id,
        created_by_user_id=seed.user_id,
        payload=request,
        idempotency_key="workflow-materialization-archive-key-0001",
        request_id="materialization-archive-replay",
        generated_at=NOW,
    )
    assert replay.dataset_version_id == first.dataset_version_id
    assert replay.database_write is False
    with pytest.raises(WorkflowMaterializationProjectNotActiveError):
        await materialize_workflow_lineage(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=created.run.id,
            created_by_user_id=seed.user_id,
            payload=request,
            idempotency_key="workflow-materialization-archive-key-0002",
            request_id="materialization-after-archive",
            generated_at=NOW,
        )
