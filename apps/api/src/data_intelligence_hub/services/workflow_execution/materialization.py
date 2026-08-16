from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest as MaterializationLedger,
)
from data_intelligence_hub.repositories.datasets import (
    get_dataset_by_name,
    get_latest_dataset_version,
)
from data_intelligence_hub.repositories.workflow_execution import (
    get_project_for_update,
    get_workflow_run,
    list_step_runs,
)
from data_intelligence_hub.repositories.workflow_lineage import (
    add_dataset_version,
    add_materialization_request,
    add_raw_records,
    get_completed_materialization_request,
    get_dataset_version_for_materialization_replay,
    get_materialization_request_by_run,
    get_workflow_run_for_update,
    list_raw_records_by_ids,
    lock_workspace,
)
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunResponse,
    WorkflowStepRunResponse,
    normalize_workflow_execution_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowLineageMaterializationRequest,
    WorkflowLineageMaterializationResponse,
    WorkflowProviderPayloadRecord,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixtureContractInvalidError,
    WorkflowFixturePayloadUnboundError,
    load_workflow_fixture_payload,
    load_workflow_fixture_profile,
)
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id


class WorkflowMaterializationProjectNotFoundError(LookupError):
    pass


class WorkflowMaterializationRunNotFoundError(LookupError):
    pass


class WorkflowMaterializationProjectNotActiveError(ValueError):
    pass


class WorkflowMaterializationRunNotCompletedError(ValueError):
    pass


class WorkflowMaterializationIdempotencyConflictError(ValueError):
    pass


class WorkflowRunAlreadyMaterializedError(ValueError):
    pass


class WorkflowMaterializationLineageDigestConflictError(ValueError):
    pass


class WorkflowMaterializationDatasetConflictError(ValueError):
    pass


class WorkflowMaterializationTransactionStateError(ValueError):
    pass


class WorkflowMaterializationPayloadInvalidError(ValueError):
    pass


class WorkflowMaterializationLedgerInvalidError(ValueError):
    pass


MATERIALIZATION_DATASET_CONFLICT_CODES = frozenset(
    {
        "dataset_not_active",
        "dataset_project_lineage_conflict",
        "dataset_type_conflict",
    }
)


MATERIALIZATION_RACE_CONSTRAINTS = frozenset(
    {
        "uq_workflow_lineage_materializations_idempotency",
        "uq_workflow_lineage_materializations_run",
        "uq_dataset_versions_source_workflow_run",
    }
)


def materialization_unique_violation_constraint(
    exc: IntegrityError,
) -> str | None:
    origin = exc.orig
    if origin is None:
        return None
    cause = origin.__cause__
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if sqlstate is None and cause is not None:
        sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    if sqlstate != "23505":
        return None
    constraint_name = getattr(origin, "constraint_name", None)
    if constraint_name is None:
        diagnostic = getattr(origin, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name is None and cause is not None:
        constraint_name = getattr(cause, "constraint_name", None)
        if constraint_name is None:
            diagnostic = getattr(cause, "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
    return constraint_name if constraint_name in MATERIALIZATION_RACE_CONSTRAINTS else None


def _scope(project_id: uuid.UUID, workflow_run_id: uuid.UUID) -> str:
    return f"POST:/api/projects/{project_id}/workflow-runs/{workflow_run_id}/materializations"


def _request_hash(
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    payload: WorkflowLineageMaterializationRequest,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "method": "POST",
                "project_id": str(project_id),
                "workflow_run_id": str(workflow_run_id),
                "body": payload.model_dump(mode="json"),
            },
        )
    )


def _key_hash(idempotency_key: str) -> str:
    normalized = normalize_workflow_execution_idempotency_key(idempotency_key)
    return sha256_id(cast(JsonValue, normalized))


def _timestamps_match(persisted: datetime, expected: datetime) -> bool:
    if persisted.utcoffset() is None:
        persisted = persisted.replace(tzinfo=UTC)
    return persisted.astimezone(UTC) == expected.astimezone(UTC)


async def _prepare_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise WorkflowMaterializationTransactionStateError(
            "workflow_materialization_transaction_state_invalid"
        )
    if session.in_transaction():
        await session.rollback()


async def _replay(
    session: AsyncSession,
    ledger: MaterializationLedger,
    *,
    request_hash: str,
    payload: WorkflowLineageMaterializationRequest,
) -> WorkflowLineageMaterializationResponse:
    if ledger.request_hash != request_hash:
        raise WorkflowMaterializationIdempotencyConflictError("idempotency_conflict")
    try:
        original = WorkflowLineageMaterializationResponse.model_validate(ledger.response_payload)
    except ValidationError as exc:
        raise WorkflowMaterializationLedgerInvalidError(
            "workflow_materialization_ledger_invalid"
        ) from exc
    version = None
    if ledger.dataset_id is not None and ledger.dataset_version_id is not None:
        version = await get_dataset_version_for_materialization_replay(
            session,
            workspace_id=ledger.workspace_id,
            project_id=ledger.project_id,
            workflow_run_id=ledger.workflow_run_id,
            dataset_id=ledger.dataset_id,
            dataset_version_id=ledger.dataset_version_id,
        )
    expected_raw_record_ids = [str(item) for item in original.raw_record_ids]
    records: list[RawRecord] = []
    if version is not None:
        records = await list_raw_records_by_ids(
            session,
            workspace_id=ledger.workspace_id,
            project_id=ledger.project_id,
            raw_record_ids=original.raw_record_ids,
        )
    steps = await list_step_runs(
        session,
        ledger.workspace_id,
        ledger.project_id,
        ledger.workflow_run_id,
    )
    run = await get_workflow_run(
        session,
        ledger.workspace_id,
        ledger.project_id,
        ledger.workflow_run_id,
    )
    expected_records: list[WorkflowProviderPayloadRecord] = []
    try:
        if run is not None:
            loaded = load_workflow_fixture_profile(run.fixture_profile_id)
            if loaded.profile_hash != run.fixture_profile_hash:
                raise WorkflowFixtureContractInvalidError(
                    "workflow_fixture_contract_invalid:profile_hash_mismatch"
                )
            expected_records = [
                record
                for step in steps
                for record in load_workflow_fixture_payload(
                    loaded,
                    fixture_case_id=step.fixture_case_id,
                    implementation_id=step.implementation_id,
                    platform=PlatformId(step.platform),
                    resource_type=ResourceType(step.resource_type),
                    operation=CapabilityOperation(step.operation),
                    evidence_refs=list(step.evidence_refs),
                    expected_fixture_content_hash=step.fixture_content_hash,
                    expected_records_count=step.records_count,
                    expected_output_digest=step.output_digest,
                ).records
            ]
    except ValueError as exc:
        raise WorkflowMaterializationLedgerInvalidError(
            "workflow_materialization_ledger_invalid"
        ) from exc
    source_step_ids = [str(step.id) for step in steps]
    expected_record_step_ids = [
        str(step.id) for step in steps for _ in range(step.records_count)
    ]
    raw_records_valid = False
    if (
        version is not None
        and len(records) == len(original.raw_record_ids)
        and len(version.rows) == len(original.raw_record_ids)
        and len(expected_record_step_ids) == len(original.raw_record_ids)
        and len(expected_records) == len(original.raw_record_ids)
    ):
        raw_records_valid = all(
            record.id == record_id
            and record.workflow_run_id == ledger.workflow_run_id
            and str(record.workflow_step_run_id) == expected_step_id
            and record.workflow_lineage_contract_version == "workflow_raw_record.v1"
            and record.record_type == expected_record.record_type
            and record.source_url == expected_record.source_url
            and _timestamps_match(record.collected_at, expected_record.collected_at)
            and isinstance(record.content, dict)
            and record.content == row
            and record.content_hash
            == sha256_id(cast(JsonValue, record.content)).removeprefix("sha256:")
            for record, record_id, row, expected_step_id, expected_record in zip(
                records,
                original.raw_record_ids,
                version.rows,
                expected_record_step_ids,
                expected_records,
                strict=True,
            )
        )
    if (
        ledger.outcome != "completed"
        or ledger.response_status != 201
        or original.materialization_id != ledger.id
        or original.workflow_run_id != ledger.workflow_run_id
        or original.dataset_id != ledger.dataset_id
        or original.dataset_version_id != ledger.dataset_version_id
        or original.lineage_digest != payload.expected_lineage_digest
        or not original.database_write
        or original.idempotent_replay
        or not original.raw_record_write
        or not original.dataset_write
        or version is None
        or version.lineage_contract_version != "workflow_dataset_version.v1"
        or version.source_workflow_step_run_ids != source_step_ids
        or version.version_number != original.dataset_version_number
        or version.source_raw_record_ids != expected_raw_record_ids
        or version.row_count != original.records_count
        or original.records_count != len(original.raw_record_ids)
        or not raw_records_valid
    ):
        raise WorkflowMaterializationLedgerInvalidError("workflow_materialization_ledger_invalid")
    return original.model_copy(
        update={
            "database_write": False,
            "idempotent_replay": True,
            "raw_record_write": False,
            "dataset_write": False,
        },
        deep=True,
    )


def _selected_fields(rows: list[dict[str, JsonValue]]) -> list[str]:
    return sorted({key for row in rows for key in row})


def _average_completeness(
    rows: list[dict[str, JsonValue]],
    selected_fields: list[str],
) -> int:
    if not rows or not selected_fields:
        return 0
    present = sum(
        1 for row in rows for field in selected_fields if row.get(field) not in (None, "", [], {})
    )
    return round(100 * present / (len(rows) * len(selected_fields)))


async def _materialize_workflow_lineage_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowLineageMaterializationRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowLineageMaterializationResponse:
    del request_id
    timestamp = generated_at or datetime.now(UTC)
    scope = _scope(project_id, workflow_run_id)
    key_hash = _key_hash(idempotency_key)
    request_hash = _request_hash(project_id, workflow_run_id, payload)
    await _prepare_transaction(session)

    async with session.begin():
        completed = await get_completed_materialization_request(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=scope,
            idempotency_key_hash=key_hash,
        )
        if completed is not None:
            return await _replay(
                session,
                completed,
                request_hash=request_hash,
                payload=payload,
            )

        if await lock_workspace(session, workspace_id) is None:
            raise WorkflowMaterializationProjectNotFoundError("project_not_found")
        project = await get_project_for_update(session, workspace_id, project_id)
        if project is None:
            raise WorkflowMaterializationProjectNotFoundError("project_not_found")
        if project.status != "active":
            raise WorkflowMaterializationProjectNotActiveError("project_not_active")
        run = await get_workflow_run_for_update(
            session,
            workspace_id,
            project_id,
            workflow_run_id,
        )
        if run is None:
            raise WorkflowMaterializationRunNotFoundError("workflow_run_not_found")

        completed = await get_completed_materialization_request(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=scope,
            idempotency_key_hash=key_hash,
        )
        if completed is not None:
            return await _replay(
                session,
                completed,
                request_hash=request_hash,
                payload=payload,
            )
        if (
            await get_materialization_request_by_run(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=workflow_run_id,
            )
            is not None
        ):
            raise WorkflowRunAlreadyMaterializedError("workflow_run_already_materialized")
        if run.status != "completed":
            raise WorkflowMaterializationRunNotCompletedError("workflow_run_not_completed")

        steps = await list_step_runs(session, workspace_id, project_id, workflow_run_id)
        try:
            if any(step.status != "completed" for step in steps):
                raise WorkflowFixtureContractInvalidError(
                    "workflow_fixture_contract_invalid:step_status"
                )
            loaded = load_workflow_fixture_profile(run.fixture_profile_id)
            if loaded.profile_hash != run.fixture_profile_hash:
                raise WorkflowFixtureContractInvalidError(
                    "workflow_fixture_contract_invalid:profile_hash_mismatch"
                )
            envelopes = [
                load_workflow_fixture_payload(
                    loaded,
                    fixture_case_id=step.fixture_case_id,
                    implementation_id=step.implementation_id,
                    platform=PlatformId(step.platform),
                    resource_type=ResourceType(step.resource_type),
                    operation=CapabilityOperation(step.operation),
                    evidence_refs=list(step.evidence_refs),
                    expected_fixture_content_hash=step.fixture_content_hash,
                    expected_records_count=step.records_count,
                    expected_output_digest=step.output_digest,
                )
                for step in steps
            ]
            if sum(item.records_count for item in envelopes) != run.records_count:
                raise WorkflowFixtureContractInvalidError(
                    "workflow_fixture_contract_invalid:run_records_count"
                )
            run_response = WorkflowRunResponse.model_validate(run)
            step_responses = [WorkflowStepRunResponse.model_validate(item) for item in steps]
            preview = build_workflow_lineage_preview(
                run_response,
                step_responses,
                payload_bound=True,
            )
        except WorkflowFixturePayloadUnboundError:
            raise
        except ValueError as exc:
            raise WorkflowMaterializationPayloadInvalidError(
                "workflow_materialization_payload_invalid"
            ) from exc
        if preview.lineage_digest != payload.expected_lineage_digest:
            raise WorkflowMaterializationLineageDigestConflictError(
                "workflow_lineage_digest_conflict"
            )

        dataset = await get_dataset_by_name(session, workspace_id, payload.dataset_name)
        if dataset is None:
            dataset = Dataset(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                name=payload.dataset_name,
                dataset_type="workflow_materialized",
                status="active",
                description="Materialized from a payload-bound fixture WorkflowRun.",
            )
            session.add(dataset)
            await session.flush()
        elif dataset.project_id != project_id:
            raise WorkflowMaterializationDatasetConflictError("dataset_project_lineage_conflict")
        elif dataset.dataset_type != "workflow_materialized":
            raise WorkflowMaterializationDatasetConflictError("dataset_type_conflict")
        elif dataset.status != "active":
            raise WorkflowMaterializationDatasetConflictError("dataset_not_active")

        raw_records: list[RawRecord] = []
        rows: list[dict[str, JsonValue]] = []
        for step, envelope in zip(steps, envelopes, strict=True):
            for record in envelope.records:
                content = dict(record.content)
                rows.append(content)
                raw_records.append(
                    RawRecord(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        project_id=project_id,
                        source_id=None,
                        task_run_id=None,
                        workflow_run_id=workflow_run_id,
                        workflow_step_run_id=step.id,
                        workflow_lineage_contract_version="workflow_raw_record.v1",
                        record_type=record.record_type,
                        source_url=record.source_url,
                        content=content,
                        content_hash=sha256_id(cast(JsonValue, content)).removeprefix("sha256:"),
                        screenshot_url=None,
                        collected_at=record.collected_at,
                        created_at=timestamp,
                    )
                )
        await add_raw_records(session, raw_records)
        latest = await get_latest_dataset_version(session, dataset.id)
        version_number = 1 if latest is None else latest.version_number + 1
        selected_fields = _selected_fields(rows)
        version = DatasetVersion(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            cleaning_plan_id=None,
            source_workflow_run_id=workflow_run_id,
            source_workflow_step_run_ids=[str(item.id) for item in steps],
            source_raw_record_ids=[str(item.id) for item in raw_records],
            lineage_contract_version="workflow_dataset_version.v1",
            version_number=version_number,
            source_task_run_ids=[],
            selected_fields=selected_fields,
            cleaning_script=[],
            rows=rows,
            export_preview={
                "schema_version": "workflow_dataset_export_preview.v1",
                "row_count": len(rows),
            },
            row_count=len(rows),
            average_completeness_percent=_average_completeness(rows, selected_fields),
            status="saved",
            created_at=timestamp,
        )
        await add_dataset_version(session, version)
        materialization_id = uuid.uuid4()
        response = WorkflowLineageMaterializationResponse(
            contract_version="workflow_lineage_materialization.v1",
            materialization_id=materialization_id,
            workflow_run_id=workflow_run_id,
            dataset_id=dataset.id,
            dataset_version_id=version.id,
            dataset_version_number=version.version_number,
            raw_record_ids=[item.id for item in raw_records],
            records_count=len(raw_records),
            lineage_digest=preview.lineage_digest,
            database_write=True,
            idempotent_replay=False,
            raw_record_write=True,
            dataset_write=True,
        )
        await add_materialization_request(
            session,
            MaterializationLedger(
                id=materialization_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                workflow_run_id=workflow_run_id,
                dataset_id=dataset.id,
                dataset_version_id=version.id,
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                outcome="completed",
                response_status=201,
                response_payload=response.model_dump(mode="json"),
                created_at=timestamp,
            ),
        )
        return response


async def materialize_workflow_lineage(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowLineageMaterializationRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowLineageMaterializationResponse:
    try:
        return await _materialize_workflow_lineage_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
            generated_at=generated_at,
        )
    except IntegrityError as exc:
        constraint_name = materialization_unique_violation_constraint(exc)
        if constraint_name is None:
            raise
        await session.rollback()
        scope = _scope(project_id, workflow_run_id)
        key_hash = _key_hash(idempotency_key)
        request_hash = _request_hash(project_id, workflow_run_id, payload)
        async with session.begin():
            completed = await get_completed_materialization_request(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
            )
            if completed is not None:
                return await _replay(
                    session,
                    completed,
                    request_hash=request_hash,
                    payload=payload,
                )
            existing = await get_materialization_request_by_run(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=workflow_run_id,
            )
            if existing is not None:
                raise WorkflowRunAlreadyMaterializedError(
                    "workflow_run_already_materialized"
                ) from exc
        raise


__all__ = [
    "MATERIALIZATION_DATASET_CONFLICT_CODES",
    "WorkflowMaterializationDatasetConflictError",
    "WorkflowMaterializationIdempotencyConflictError",
    "WorkflowMaterializationLineageDigestConflictError",
    "WorkflowMaterializationLedgerInvalidError",
    "WorkflowMaterializationPayloadInvalidError",
    "WorkflowMaterializationProjectNotActiveError",
    "WorkflowMaterializationProjectNotFoundError",
    "WorkflowMaterializationRunNotCompletedError",
    "WorkflowMaterializationRunNotFoundError",
    "WorkflowMaterializationTransactionStateError",
    "WorkflowRunAlreadyMaterializedError",
    "materialization_unique_violation_constraint",
    "materialize_workflow_lineage",
]
