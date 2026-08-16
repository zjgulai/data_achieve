from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_execution import WorkflowStepCheckpoint
from data_intelligence_hub.repositories.workflow_execution import (
    add_workflow_step_checkpoint,
    list_workflow_step_checkpoints,
)
from data_intelligence_hub.schemas.workflow_resume import (
    WorkflowCheckpointPageResult,
    WorkflowStepCheckpointResponse,
    WorkflowStepResumeIdentity,
    WorkflowStepResumeResult,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

WorkflowCheckpointPageExecutor = Callable[
    [str | None, int, str],
    Awaitable[WorkflowCheckpointPageResult],
]
WorkflowCheckpointClock = Callable[[], datetime]


class WorkflowCheckpointTransactionStateError(RuntimeError):
    """The caller supplied a session with pending mutations."""


class WorkflowCheckpointChainInvalidError(RuntimeError):
    """Persisted checkpoint evidence is inconsistent or does not match the request."""


def _cursor_digest(cursor: str | None) -> str:
    return sha256_id(cast(JsonValue, {"cursor": cursor}))


def _side_effect_key_hash(
    identity: WorkflowStepResumeIdentity,
    *,
    page_number: int,
    cursor_before_digest: str,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "workflow_step_side_effect_key.v1",
                "execution_session_id": str(identity.execution_session_id),
                "workflow_version_id": str(identity.workflow_version_id),
                "step_ref": identity.step_ref,
                "implementation_id": identity.implementation_id,
                "step_input_digest": identity.step_input_digest,
                "page_number": page_number,
                "cursor_before_digest": cursor_before_digest,
            },
        )
    )


def _checkpoint_digest(
    identity: WorkflowStepResumeIdentity,
    *,
    page_number: int,
    cursor_before_digest: str,
    cursor_after_digest: str | None,
    side_effect_key_hash: str,
    result: WorkflowCheckpointPageResult,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "workflow_step_checkpoint.v1",
                "execution_session_id": str(identity.execution_session_id),
                "workspace_id": str(identity.workspace_id),
                "project_id": str(identity.project_id),
                "workflow_plan_id": str(identity.workflow_plan_id),
                "workflow_version_id": str(identity.workflow_version_id),
                "step_ref": identity.step_ref,
                "requirement_ref": identity.requirement_ref,
                "implementation_id": identity.implementation_id,
                "fixture_profile_id": identity.fixture_profile_id,
                "fixture_profile_hash": identity.fixture_profile_hash,
                "step_input_digest": identity.step_input_digest,
                "page_number": page_number,
                "cursor_before_digest": cursor_before_digest,
                "cursor_after_digest": cursor_after_digest,
                "side_effect_key_hash": side_effect_key_hash,
                "page_output_digest": result.output_digest,
                "records_count": result.records_count,
                "terminal": result.terminal,
                "evidence_refs": result.evidence_refs,
            },
        )
    )


def _identity_payload(identity: WorkflowStepResumeIdentity) -> dict[str, object]:
    return identity.model_dump(mode="python")


def _checkpoint_identity(checkpoint: WorkflowStepCheckpoint) -> dict[str, object]:
    return {
        "execution_session_id": checkpoint.execution_session_id,
        "workspace_id": checkpoint.workspace_id,
        "project_id": checkpoint.project_id,
        "workflow_plan_id": checkpoint.workflow_plan_id,
        "workflow_version_id": checkpoint.workflow_version_id,
        "step_ref": checkpoint.step_ref,
        "requirement_ref": checkpoint.requirement_ref,
        "implementation_id": checkpoint.implementation_id,
        "fixture_profile_id": checkpoint.fixture_profile_id,
        "fixture_profile_hash": checkpoint.fixture_profile_hash,
        "step_input_digest": checkpoint.step_input_digest,
    }


def _validate_checkpoint_chain(
    identity: WorkflowStepResumeIdentity,
    checkpoints: Sequence[WorkflowStepCheckpoint],
) -> tuple[WorkflowStepCheckpoint, ...]:
    frozen = tuple(checkpoints)
    previous: WorkflowStepCheckpoint | None = None
    expected_identity = _identity_payload(identity)
    for expected_page, checkpoint in enumerate(frozen, start=1):
        if _checkpoint_identity(checkpoint) != expected_identity:
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_identity_conflict")
        if checkpoint.contract_version != "workflow_step_checkpoint.v1":
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_contract_invalid")
        if checkpoint.page_number != expected_page:
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_page_gap")
        expected_before = previous.cursor_after if previous is not None else None
        if checkpoint.cursor_before != expected_before:
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_cursor_chain_invalid")
        if checkpoint.cursor_before_digest != _cursor_digest(checkpoint.cursor_before):
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_cursor_digest_invalid")
        expected_after_digest = (
            None if checkpoint.cursor_after is None else _cursor_digest(checkpoint.cursor_after)
        )
        if checkpoint.cursor_after_digest != expected_after_digest:
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_cursor_digest_invalid")
        if previous is not None and previous.terminal:
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_after_terminal")
        result = WorkflowCheckpointPageResult(
            records_count=checkpoint.records_count,
            next_cursor=checkpoint.cursor_after,
            output_digest=checkpoint.page_output_digest,
            terminal=checkpoint.terminal,
            evidence_refs=list(checkpoint.evidence_refs),
        )
        expected_side_effect_key = _side_effect_key_hash(
            identity,
            page_number=checkpoint.page_number,
            cursor_before_digest=checkpoint.cursor_before_digest,
        )
        expected_checkpoint_digest = _checkpoint_digest(
            identity,
            page_number=checkpoint.page_number,
            cursor_before_digest=checkpoint.cursor_before_digest,
            cursor_after_digest=checkpoint.cursor_after_digest,
            side_effect_key_hash=expected_side_effect_key,
            result=result,
        )
        if (
            checkpoint.side_effect_key_hash != expected_side_effect_key
            or checkpoint.checkpoint_digest != expected_checkpoint_digest
        ):
            raise WorkflowCheckpointChainInvalidError("workflow_checkpoint_digest_invalid")
        previous = checkpoint
    return frozen


async def _read_chain(
    session: AsyncSession,
    identity: WorkflowStepResumeIdentity,
) -> tuple[WorkflowStepCheckpoint, ...]:
    async with session.begin():
        checkpoints = await list_workflow_step_checkpoints(
            session,
            identity.execution_session_id,
            identity.step_ref,
        )
    return _validate_checkpoint_chain(identity, checkpoints)


def _build_checkpoint(
    identity: WorkflowStepResumeIdentity,
    *,
    page_number: int,
    cursor_before: str | None,
    side_effect_key_hash: str,
    result: WorkflowCheckpointPageResult,
    timestamp: datetime,
) -> WorkflowStepCheckpoint:
    cursor_before_digest = _cursor_digest(cursor_before)
    cursor_after_digest = None if result.next_cursor is None else _cursor_digest(result.next_cursor)
    return WorkflowStepCheckpoint(
        id=uuid.uuid4(),
        execution_session_id=identity.execution_session_id,
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        workflow_plan_id=identity.workflow_plan_id,
        workflow_version_id=identity.workflow_version_id,
        step_ref=identity.step_ref,
        requirement_ref=identity.requirement_ref,
        implementation_id=identity.implementation_id,
        contract_version="workflow_step_checkpoint.v1",
        fixture_profile_id=identity.fixture_profile_id,
        fixture_profile_hash=identity.fixture_profile_hash,
        step_input_digest=identity.step_input_digest,
        page_number=page_number,
        cursor_before=cursor_before,
        cursor_before_digest=cursor_before_digest,
        cursor_after=result.next_cursor,
        cursor_after_digest=cursor_after_digest,
        side_effect_key_hash=side_effect_key_hash,
        page_output_digest=result.output_digest,
        checkpoint_digest=_checkpoint_digest(
            identity,
            page_number=page_number,
            cursor_before_digest=cursor_before_digest,
            cursor_after_digest=cursor_after_digest,
            side_effect_key_hash=side_effect_key_hash,
            result=result,
        ),
        records_count=result.records_count,
        terminal=result.terminal,
        evidence_refs=list(result.evidence_refs),
        provider_call_attempted=False,
        credential_read_attempted=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        raw_record_write=False,
        dataset_write=False,
        production_write_allowed=False,
        confirmed_at=timestamp,
        created_at=timestamp,
    )


def _response(
    identity: WorkflowStepResumeIdentity,
    checkpoints: Sequence[WorkflowStepCheckpoint],
    *,
    resumed_from_page: int,
    pages_executed: int,
    checkpoint_replay: bool,
) -> WorkflowStepResumeResult:
    frozen = tuple(checkpoints)
    latest = frozen[-1] if frozen else None
    return WorkflowStepResumeResult(
        execution_session_id=identity.execution_session_id,
        step_ref=identity.step_ref,
        resumed_from_page=resumed_from_page,
        pages_executed=pages_executed,
        database_writes=pages_executed,
        checkpoint_replay=checkpoint_replay,
        terminal=bool(latest and latest.terminal),
        next_cursor=(latest.cursor_after if latest is not None else None),
        records_count=sum(item.records_count for item in frozen),
        checkpoints=[WorkflowStepCheckpointResponse.model_validate(item) for item in frozen],
    )


async def resume_fixture_step_pages(
    session: AsyncSession,
    *,
    identity: WorkflowStepResumeIdentity,
    executor: WorkflowCheckpointPageExecutor,
    max_pages: int = 100,
    clock: WorkflowCheckpointClock | None = None,
) -> WorkflowStepResumeResult:
    if not 1 <= max_pages <= 100:
        raise ValueError("workflow_checkpoint_max_pages_invalid")
    if session.new or session.dirty or session.deleted:
        raise WorkflowCheckpointTransactionStateError(
            "workflow_checkpoint_transaction_state_invalid"
        )
    if session.in_transaction():
        await session.rollback()

    checkpoints = list(await _read_chain(session, identity))
    resumed_from_page = len(checkpoints)
    if checkpoints and checkpoints[-1].terminal:
        return _response(
            identity,
            checkpoints,
            resumed_from_page=resumed_from_page,
            pages_executed=0,
            checkpoint_replay=True,
        )

    now = clock or (lambda: datetime.now(UTC))
    pages_executed = 0
    page_attempts = 0
    while page_attempts < max_pages:
        page_attempts += 1
        page_number = len(checkpoints) + 1
        cursor_before = checkpoints[-1].cursor_after if checkpoints else None
        cursor_before_digest = _cursor_digest(cursor_before)
        side_effect_key_hash = _side_effect_key_hash(
            identity,
            page_number=page_number,
            cursor_before_digest=cursor_before_digest,
        )
        result = await executor(cursor_before, page_number, side_effect_key_hash)
        checkpoint = _build_checkpoint(
            identity,
            page_number=page_number,
            cursor_before=cursor_before,
            side_effect_key_hash=side_effect_key_hash,
            result=result,
            timestamp=now(),
        )
        try:
            async with session.begin():
                await add_workflow_step_checkpoint(session, checkpoint)
        except IntegrityError:
            await session.rollback()
            raced = await _read_chain(session, identity)
            if len(raced) < page_number:
                raise
            persisted = raced[page_number - 1]
            if persisted.checkpoint_digest != checkpoint.checkpoint_digest:
                raise WorkflowCheckpointChainInvalidError(
                    "workflow_checkpoint_concurrent_conflict"
                ) from None
            checkpoints = list(raced)
        else:
            checkpoints.append(checkpoint)
            pages_executed += 1
        if checkpoints[-1].terminal:
            break

    return _response(
        identity,
        checkpoints,
        resumed_from_page=resumed_from_page,
        pages_executed=pages_executed,
        checkpoint_replay=False,
    )


__all__ = [
    "WorkflowCheckpointChainInvalidError",
    "WorkflowCheckpointPageExecutor",
    "WorkflowCheckpointTransactionStateError",
    "resume_fixture_step_pages",
]
