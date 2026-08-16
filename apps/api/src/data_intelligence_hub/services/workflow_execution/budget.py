from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_execution import (
    WorkflowBudgetAccount,
    WorkflowBudgetLedgerEntry,
    WorkflowStepCheckpoint,
)
from data_intelligence_hub.repositories.workflow_execution import (
    add_workflow_budget_account,
    add_workflow_budget_ledger_entry,
    get_workflow_budget_account,
    get_workflow_budget_account_for_update,
    list_workflow_budget_ledger_entries,
    list_workflow_step_checkpoints,
)
from data_intelligence_hub.schemas.workflow_budget import (
    WorkflowBudgetAccountResponse,
    WorkflowBudgetBlockerCode,
    WorkflowBudgetCharge,
    WorkflowBudgetedStepResult,
    WorkflowBudgetLedgerEntryResponse,
    WorkflowBudgetPolicy,
)
from data_intelligence_hub.schemas.workflow_resume import (
    WorkflowCheckpointPageResult,
    WorkflowStepResumeIdentity,
)
from data_intelligence_hub.services.workflow_execution.resume import (
    WorkflowCheckpointClock,
    WorkflowCheckpointPageExecutor,
    resume_fixture_step_pages,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

WorkflowBudgetChargeResolver = Callable[[str | None, int], WorkflowBudgetCharge]


class WorkflowBudgetContractError(RuntimeError):
    """The durable budget account or ledger failed closed validation."""


class WorkflowBudgetTransactionStateError(RuntimeError):
    """The caller supplied a session with pending mutations."""


@dataclass(frozen=True, slots=True)
class WorkflowBudgetReservation:
    entry: WorkflowBudgetLedgerEntry
    replay: bool

    @property
    def allowed(self) -> bool:
        return self.entry.status == "reserved"


class _WorkflowBudgetHeldSignal(RuntimeError):
    def __init__(
        self,
        *,
        entry: WorkflowBudgetLedgerEntry,
        replay: bool,
        page_number: int,
        cursor: str | None,
    ) -> None:
        self.entry = entry
        self.replay = replay
        self.page_number = page_number
        self.cursor = cursor
        super().__init__(entry.blocker_code or "workflow_budget_held")


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


def _policy_payload(policy: WorkflowBudgetPolicy) -> dict[str, JsonValue]:
    return {
        "max_requests": policy.max_requests,
        "max_items": policy.max_items,
        "quota_ceilings": cast(JsonValue, dict(sorted(policy.quota_ceilings.items()))),
        "max_cost_usd": _decimal_text(policy.max_cost_usd),
        "max_time_ms": policy.max_time_ms,
        "evidence_refs": cast(JsonValue, list(policy.evidence_refs)),
    }


def _policy_digest(policy: WorkflowBudgetPolicy) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "workflow_budget_account.v1",
                "policy": _policy_payload(policy),
            },
        )
    )


def _charge_payload(charge: WorkflowBudgetCharge) -> dict[str, JsonValue]:
    return {
        "request_count": charge.request_count,
        "item_count": charge.item_count,
        "quota_units": cast(JsonValue, dict(sorted(charge.quota_units.items()))),
        "estimated_cost_usd": _decimal_text(charge.estimated_cost_usd),
        "reserved_time_ms": charge.reserved_time_ms,
    }


def _account_matches(
    account: WorkflowBudgetAccount,
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
    *,
    policy_digest: str,
) -> bool:
    return (
        account.execution_session_id == identity.execution_session_id
        and account.workspace_id == identity.workspace_id
        and account.project_id == identity.project_id
        and account.workflow_plan_id == identity.workflow_plan_id
        and account.workflow_version_id == identity.workflow_version_id
        and account.contract_version == "workflow_budget_account.v1"
        and account.policy_digest == policy_digest
        and account.max_requests == policy.max_requests
        and account.max_items == policy.max_items
        and account.quota_ceilings == policy.quota_ceilings
        and account.max_cost_usd == policy.max_cost_usd
        and account.max_time_ms == policy.max_time_ms
        and account.evidence_refs == policy.evidence_refs
    )


def _new_budget_account(
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
    *,
    policy_digest: str,
    timestamp: datetime,
) -> WorkflowBudgetAccount:
    return WorkflowBudgetAccount(
        id=uuid.uuid4(),
        execution_session_id=identity.execution_session_id,
        workspace_id=identity.workspace_id,
        project_id=identity.project_id,
        workflow_plan_id=identity.workflow_plan_id,
        workflow_version_id=identity.workflow_version_id,
        contract_version="workflow_budget_account.v1",
        policy_digest=policy_digest,
        max_requests=policy.max_requests,
        max_items=policy.max_items,
        quota_ceilings=dict(policy.quota_ceilings),
        max_cost_usd=policy.max_cost_usd,
        max_time_ms=policy.max_time_ms,
        evidence_refs=list(policy.evidence_refs),
        provider_call_attempted=False,
        credential_read_attempted=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        raw_record_write=False,
        dataset_write=False,
        production_write_allowed=False,
        created_at=timestamp,
    )


async def _prepare_session(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise WorkflowBudgetTransactionStateError("workflow_budget_transaction_state_invalid")
    if session.in_transaction():
        await session.rollback()


async def ensure_workflow_budget_account(
    session: AsyncSession,
    *,
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
    clock: WorkflowCheckpointClock | None = None,
) -> tuple[WorkflowBudgetAccount, bool]:
    await _prepare_session(session)
    policy_digest = _policy_digest(policy)
    try:
        async with session.begin():
            existing = await get_workflow_budget_account(
                session,
                identity.execution_session_id,
            )
            if existing is not None:
                if not _account_matches(
                    existing,
                    identity,
                    policy,
                    policy_digest=policy_digest,
                ):
                    raise WorkflowBudgetContractError("workflow_budget_account_conflict")
                return existing, False

            account = _new_budget_account(
                identity,
                policy,
                policy_digest=policy_digest,
                timestamp=(clock or (lambda: datetime.now(UTC)))(),
            )
            await add_workflow_budget_account(session, account)
            return account, True
    except IntegrityError as conflict:
        await session.rollback()
        async with session.begin():
            raced = await get_workflow_budget_account(
                session,
                identity.execution_session_id,
            )
        if raced is None:
            raise conflict
        if not _account_matches(
            raced,
            identity,
            policy,
            policy_digest=policy_digest,
        ):
            raise WorkflowBudgetContractError("workflow_budget_account_conflict") from None
        return raced, False


def _next_cumulative_quota(
    previous: dict[str, int],
    increment: dict[str, int],
) -> dict[str, int]:
    return {
        key: previous.get(key, 0) + increment.get(key, 0)
        for key in sorted(set(previous) | set(increment))
    }


def _select_blocker(
    policy: WorkflowBudgetPolicy,
    *,
    requests: int,
    items: int,
    quotas: dict[str, int],
    cost: Decimal,
    time_ms: int,
) -> WorkflowBudgetBlockerCode | None:
    if requests > policy.max_requests:
        return "workflow_request_budget_exceeded"
    if items > policy.max_items:
        return "workflow_item_budget_exceeded"
    if any(quotas[key] > policy.quota_ceilings[key] for key in quotas):
        return "workflow_quota_budget_exceeded"
    if cost > policy.max_cost_usd:
        return "workflow_cost_budget_exceeded"
    if time_ms > policy.max_time_ms:
        return "workflow_time_budget_exceeded"
    return None


def _ledger_digest(
    *,
    account: WorkflowBudgetAccount,
    entry_number: int,
    step_ref: str,
    page_number: int,
    side_effect_key_hash: str,
    status: str,
    blocker_code: str | None,
    charge: WorkflowBudgetCharge,
    cumulative_request_count: int,
    cumulative_item_count: int,
    cumulative_quota_units: dict[str, int],
    cumulative_cost_usd: Decimal,
    cumulative_time_ms: int,
    previous_ledger_digest: str | None,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "contract_version": "workflow_budget_ledger.v1",
                "budget_account_id": str(account.id),
                "execution_session_id": str(account.execution_session_id),
                "policy_digest": account.policy_digest,
                "entry_number": entry_number,
                "step_ref": step_ref,
                "page_number": page_number,
                "side_effect_key_hash": side_effect_key_hash,
                "status": status,
                "blocker_code": blocker_code,
                "charge": _charge_payload(charge),
                "cumulative_request_count": cumulative_request_count,
                "cumulative_item_count": cumulative_item_count,
                "cumulative_quota_units": cast(
                    JsonValue,
                    dict(sorted(cumulative_quota_units.items())),
                ),
                "cumulative_cost_usd": _decimal_text(cumulative_cost_usd),
                "cumulative_time_ms": cumulative_time_ms,
                "previous_ledger_digest": previous_ledger_digest,
            },
        )
    )


def _entry_charge(entry: WorkflowBudgetLedgerEntry) -> WorkflowBudgetCharge:
    return WorkflowBudgetCharge(
        request_count=entry.request_count,
        item_count=entry.item_count,
        quota_units=entry.quota_units,
        estimated_cost_usd=entry.estimated_cost_usd,
        reserved_time_ms=entry.reserved_time_ms,
    )


def _validate_ledger(
    account: WorkflowBudgetAccount,
    policy: WorkflowBudgetPolicy,
    entries: Sequence[WorkflowBudgetLedgerEntry],
) -> tuple[WorkflowBudgetLedgerEntry, ...]:
    previous_digest: str | None = None
    requests = 0
    items = 0
    quotas = {key: 0 for key in policy.quota_ceilings}
    cost = Decimal("0")
    time_ms = 0
    frozen = tuple(entries)
    for expected_number, entry in enumerate(frozen, start=1):
        if (
            entry.budget_account_id != account.id
            or entry.execution_session_id != account.execution_session_id
            or entry.workspace_id != account.workspace_id
            or entry.project_id != account.project_id
            or entry.contract_version != "workflow_budget_ledger.v1"
            or entry.policy_digest != account.policy_digest
            or entry.entry_number != expected_number
            or entry.previous_ledger_digest != previous_digest
        ):
            raise WorkflowBudgetContractError("workflow_budget_ledger_chain_invalid")
        charge = _entry_charge(entry)
        if not set(charge.quota_units).issubset(policy.quota_ceilings):
            raise WorkflowBudgetContractError("workflow_budget_quota_bucket_unknown")
        proposed_requests = requests + charge.request_count
        proposed_items = items + charge.item_count
        proposed_quotas = _next_cumulative_quota(quotas, charge.quota_units)
        proposed_cost = cost + charge.estimated_cost_usd
        proposed_time = time_ms + charge.reserved_time_ms
        expected_blocker = _select_blocker(
            policy,
            requests=proposed_requests,
            items=proposed_items,
            quotas=proposed_quotas,
            cost=proposed_cost,
            time_ms=proposed_time,
        )
        if entry.status == "reserved":
            if expected_blocker is not None:
                raise WorkflowBudgetContractError("workflow_budget_reservation_exceeds_limit")
            requests = proposed_requests
            items = proposed_items
            quotas = proposed_quotas
            cost = proposed_cost
            time_ms = proposed_time
        elif entry.status == "blocked":
            if entry.blocker_code != expected_blocker or expected_blocker is None:
                raise WorkflowBudgetContractError("workflow_budget_blocker_invalid")
            if expected_number != len(frozen):
                raise WorkflowBudgetContractError("workflow_budget_entry_after_hold")
        else:
            raise WorkflowBudgetContractError("workflow_budget_entry_status_invalid")
        expected_digest = _ledger_digest(
            account=account,
            entry_number=entry.entry_number,
            step_ref=entry.step_ref,
            page_number=entry.page_number,
            side_effect_key_hash=entry.side_effect_key_hash,
            status=entry.status,
            blocker_code=entry.blocker_code,
            charge=charge,
            cumulative_request_count=requests,
            cumulative_item_count=items,
            cumulative_quota_units=quotas,
            cumulative_cost_usd=cost,
            cumulative_time_ms=time_ms,
            previous_ledger_digest=previous_digest,
        )
        if (
            entry.cumulative_request_count != requests
            or entry.cumulative_item_count != items
            or entry.cumulative_quota_units != quotas
            or entry.cumulative_cost_usd != cost
            or entry.cumulative_time_ms != time_ms
            or entry.ledger_digest != expected_digest
        ):
            raise WorkflowBudgetContractError("workflow_budget_ledger_digest_invalid")
        previous_digest = entry.ledger_digest
    return frozen


def _reservation_matches(
    entry: WorkflowBudgetLedgerEntry,
    *,
    step_ref: str,
    page_number: int,
    side_effect_key_hash: str,
    charge: WorkflowBudgetCharge,
) -> bool:
    return (
        entry.step_ref == step_ref
        and entry.page_number == page_number
        and entry.side_effect_key_hash == side_effect_key_hash
        and _entry_charge(entry) == charge
    )


async def reserve_workflow_budget(
    session: AsyncSession,
    *,
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
    charge: WorkflowBudgetCharge,
    page_number: int,
    side_effect_key_hash: str,
    clock: WorkflowCheckpointClock | None = None,
) -> WorkflowBudgetReservation:
    await _prepare_session(session)
    if not set(charge.quota_units).issubset(policy.quota_ceilings):
        raise WorkflowBudgetContractError("workflow_budget_quota_bucket_unknown")
    timestamp = (clock or (lambda: datetime.now(UTC)))()
    async with session.begin():
        account = await get_workflow_budget_account_for_update(
            session,
            identity.execution_session_id,
        )
        if account is None:
            raise WorkflowBudgetContractError("workflow_budget_account_missing")
        if not _account_matches(
            account,
            identity,
            policy,
            policy_digest=_policy_digest(policy),
        ):
            raise WorkflowBudgetContractError("workflow_budget_account_conflict")
        entries = _validate_ledger(
            account,
            policy,
            await list_workflow_budget_ledger_entries(session, account.id),
        )
        existing = next(
            (item for item in entries if item.side_effect_key_hash == side_effect_key_hash),
            None,
        )
        if existing is not None:
            if not _reservation_matches(
                existing,
                step_ref=identity.step_ref,
                page_number=page_number,
                side_effect_key_hash=side_effect_key_hash,
                charge=charge,
            ):
                raise WorkflowBudgetContractError("workflow_budget_reservation_conflict")
            return WorkflowBudgetReservation(entry=existing, replay=True)
        if entries and entries[-1].status == "blocked":
            return WorkflowBudgetReservation(entry=entries[-1], replay=True)

        previous = entries[-1] if entries else None
        requests = previous.cumulative_request_count if previous is not None else 0
        items = previous.cumulative_item_count if previous is not None else 0
        quotas = (
            dict(previous.cumulative_quota_units)
            if previous is not None
            else {key: 0 for key in policy.quota_ceilings}
        )
        cost = previous.cumulative_cost_usd if previous is not None else Decimal("0")
        time_ms = previous.cumulative_time_ms if previous is not None else 0
        proposed_requests = requests + charge.request_count
        proposed_items = items + charge.item_count
        proposed_quotas = _next_cumulative_quota(quotas, charge.quota_units)
        proposed_cost = cost + charge.estimated_cost_usd
        proposed_time = time_ms + charge.reserved_time_ms
        blocker = _select_blocker(
            policy,
            requests=proposed_requests,
            items=proposed_items,
            quotas=proposed_quotas,
            cost=proposed_cost,
            time_ms=proposed_time,
        )
        if blocker is None:
            status = "reserved"
            requests = proposed_requests
            items = proposed_items
            quotas = proposed_quotas
            cost = proposed_cost
            time_ms = proposed_time
        else:
            status = "blocked"
        entry_number = len(entries) + 1
        previous_digest = previous.ledger_digest if previous is not None else None
        ledger_digest = _ledger_digest(
            account=account,
            entry_number=entry_number,
            step_ref=identity.step_ref,
            page_number=page_number,
            side_effect_key_hash=side_effect_key_hash,
            status=status,
            blocker_code=blocker,
            charge=charge,
            cumulative_request_count=requests,
            cumulative_item_count=items,
            cumulative_quota_units=quotas,
            cumulative_cost_usd=cost,
            cumulative_time_ms=time_ms,
            previous_ledger_digest=previous_digest,
        )
        entry = WorkflowBudgetLedgerEntry(
            id=uuid.uuid4(),
            budget_account_id=account.id,
            execution_session_id=account.execution_session_id,
            workspace_id=account.workspace_id,
            project_id=account.project_id,
            contract_version="workflow_budget_ledger.v1",
            policy_digest=account.policy_digest,
            entry_number=entry_number,
            step_ref=identity.step_ref,
            page_number=page_number,
            side_effect_key_hash=side_effect_key_hash,
            status=status,
            blocker_code=blocker,
            request_count=charge.request_count,
            item_count=charge.item_count,
            quota_units=dict(charge.quota_units),
            estimated_cost_usd=charge.estimated_cost_usd,
            reserved_time_ms=charge.reserved_time_ms,
            cumulative_request_count=requests,
            cumulative_item_count=items,
            cumulative_quota_units=quotas,
            cumulative_cost_usd=cost,
            cumulative_time_ms=time_ms,
            previous_ledger_digest=previous_digest,
            ledger_digest=ledger_digest,
            provider_call_attempted=False,
            credential_read_attempted=False,
            actor_run=False,
            browser_run=False,
            llm_call=False,
            raw_record_write=False,
            dataset_write=False,
            production_write_allowed=False,
            created_at=timestamp,
        )
        await add_workflow_budget_ledger_entry(session, entry)
        return WorkflowBudgetReservation(entry=entry, replay=False)


def _validate_checkpoint_budget_coverage(
    checkpoints: Sequence[WorkflowStepCheckpoint],
    entries: Sequence[WorkflowBudgetLedgerEntry],
) -> None:
    reservations = {
        (entry.step_ref, entry.page_number, entry.side_effect_key_hash)
        for entry in entries
        if entry.status == "reserved"
    }
    for checkpoint in checkpoints:
        key = (
            checkpoint.step_ref,
            checkpoint.page_number,
            checkpoint.side_effect_key_hash,
        )
        if key not in reservations:
            raise WorkflowBudgetContractError("workflow_checkpoint_budget_reservation_missing")


async def _read_budget_state(
    session: AsyncSession,
    *,
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
) -> tuple[
    WorkflowBudgetAccount,
    tuple[WorkflowBudgetLedgerEntry, ...],
    tuple[WorkflowStepCheckpoint, ...],
]:
    async with session.begin():
        account = await get_workflow_budget_account(
            session,
            identity.execution_session_id,
        )
        if account is None:
            raise WorkflowBudgetContractError("workflow_budget_account_missing")
        entries = _validate_ledger(
            account,
            policy,
            await list_workflow_budget_ledger_entries(session, account.id),
        )
        checkpoints = await list_workflow_step_checkpoints(
            session,
            identity.execution_session_id,
            identity.step_ref,
        )
    _validate_checkpoint_budget_coverage(checkpoints, entries)
    return account, entries, checkpoints


async def execute_budgeted_fixture_step_pages(
    session: AsyncSession,
    *,
    identity: WorkflowStepResumeIdentity,
    policy: WorkflowBudgetPolicy,
    charge_for_page: WorkflowBudgetChargeResolver,
    executor: WorkflowCheckpointPageExecutor,
    max_pages: int = 100,
    clock: WorkflowCheckpointClock | None = None,
) -> WorkflowBudgetedStepResult:
    account, account_created = await ensure_workflow_budget_account(
        session,
        identity=identity,
        policy=policy,
        clock=clock,
    )
    budget_entries_written = 0
    reservation_replays = 0
    executor_calls = 0

    async def budgeted_executor(
        cursor: str | None,
        page_number: int,
        side_effect_key_hash: str,
    ) -> WorkflowCheckpointPageResult:
        nonlocal budget_entries_written, reservation_replays, executor_calls
        charge = charge_for_page(cursor, page_number)
        reservation = await reserve_workflow_budget(
            session,
            identity=identity,
            policy=policy,
            charge=charge,
            page_number=page_number,
            side_effect_key_hash=side_effect_key_hash,
            clock=clock,
        )
        if reservation.replay:
            reservation_replays += 1
        else:
            budget_entries_written += 1
        if not reservation.allowed:
            raise _WorkflowBudgetHeldSignal(
                entry=reservation.entry,
                replay=reservation.replay,
                page_number=page_number,
                cursor=cursor,
            )
        executor_calls += 1
        return await executor(cursor, page_number, side_effect_key_hash)

    held: _WorkflowBudgetHeldSignal | None = None
    checkpoint_result = None
    try:
        checkpoint_result = await resume_fixture_step_pages(
            session,
            identity=identity,
            executor=budgeted_executor,
            max_pages=max_pages,
            clock=clock,
        )
    except _WorkflowBudgetHeldSignal as exc:
        held = exc

    account, entries, checkpoints = await _read_budget_state(
        session,
        identity=identity,
        policy=policy,
    )
    if held is not None:
        status = "held"
        held_reason_code = cast(WorkflowBudgetBlockerCode, held.entry.blocker_code)
        next_page_number = held.page_number
        next_cursor = held.cursor
    else:
        if checkpoint_result is None:
            raise WorkflowBudgetContractError("workflow_budget_checkpoint_result_missing")
        status = "completed" if checkpoint_result.terminal else "in_progress"
        held_reason_code = None
        next_page_number = len(checkpoints) + 1
        next_cursor = checkpoint_result.next_cursor

    return WorkflowBudgetedStepResult(
        execution_session_id=identity.execution_session_id,
        step_ref=identity.step_ref,
        status=status,
        held_reason_code=held_reason_code,
        next_page_number=next_page_number,
        next_cursor=next_cursor,
        confirmed_pages=len(checkpoints),
        account_created=account_created,
        budget_entries_written=budget_entries_written,
        reservation_replays=reservation_replays,
        executor_calls=executor_calls,
        held_before_executor=held is not None,
        account=WorkflowBudgetAccountResponse.model_validate(account),
        entries=[WorkflowBudgetLedgerEntryResponse.model_validate(item) for item in entries],
        checkpoint_result=checkpoint_result,
    )


__all__ = [
    "WorkflowBudgetChargeResolver",
    "WorkflowBudgetContractError",
    "WorkflowBudgetReservation",
    "WorkflowBudgetTransactionStateError",
    "ensure_workflow_budget_account",
    "execute_budgeted_fixture_step_pages",
    "reserve_workflow_budget",
]
