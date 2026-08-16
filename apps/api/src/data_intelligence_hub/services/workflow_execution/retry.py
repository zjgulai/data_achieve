from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

RETRYABLE_ERROR_CODES = frozenset(
    {
        "step_network_unavailable",
        "step_rate_limited",
    }
)
TERMINAL_ERROR_CODES = frozenset(
    {
        "step_contract_invalid",
        "step_request_rejected",
    }
)


class WorkflowStepRetryableError(Exception):
    def __init__(self, code: str) -> None:
        if code not in RETRYABLE_ERROR_CODES:
            raise ValueError("workflow_step_retryable_code_invalid")
        self.code = code
        super().__init__(code)


class WorkflowStepTerminalError(Exception):
    def __init__(self, code: str) -> None:
        if code not in TERMINAL_ERROR_CODES:
            raise ValueError("workflow_step_terminal_code_invalid")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkflowStepRetryPolicy:
    max_attempts: int
    attempt_timeout_seconds: float
    base_backoff_ms: int
    max_backoff_ms: int

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 4:
            raise ValueError("workflow_step_retry_attempts_invalid")
        if not 0 < self.attempt_timeout_seconds <= 120:
            raise ValueError("workflow_step_retry_timeout_invalid")
        if not 0 <= self.base_backoff_ms <= self.max_backoff_ms <= 60_000:
            raise ValueError("workflow_step_retry_backoff_invalid")


WorkflowStepAttemptStatus = Literal[
    "succeeded",
    "retryable_error",
    "timeout",
    "terminal_error",
]


@dataclass(frozen=True, slots=True)
class WorkflowStepAttemptReceipt:
    attempt_number: int
    attempt_key_hash: str
    status: WorkflowStepAttemptStatus
    error_code: str | None
    backoff_ms: int
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowStepRetryResult[T]:
    status: Literal["succeeded", "failed"]
    value: T | None
    attempts: tuple[WorkflowStepAttemptReceipt, ...]
    error_code: str | None


def _attempt_key_hash(step_idempotency_key_hash: str, attempt_number: int) -> str:
    digest = hashlib.sha256(
        f"workflow-step-attempt.v1\n{step_idempotency_key_hash}\n{attempt_number}".encode()
    ).hexdigest()
    return f"sha256:{digest}"


def _backoff_ms(policy: WorkflowStepRetryPolicy, attempt_number: int) -> int:
    return min(
        policy.base_backoff_ms * (1 << (attempt_number - 1)),
        policy.max_backoff_ms,
    )


async def execute_workflow_step_with_retry[T](
    *,
    step_idempotency_key_hash: str,
    policy: WorkflowStepRetryPolicy,
    executor: Callable[[int, str], Awaitable[T]],
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> WorkflowStepRetryResult[T]:
    attempts: list[WorkflowStepAttemptReceipt] = []

    for attempt_number in range(1, policy.max_attempts + 1):
        attempt_key_hash = _attempt_key_hash(
            step_idempotency_key_hash,
            attempt_number,
        )
        started_at = clock()
        status: WorkflowStepAttemptStatus
        error_code: str | None
        value: T | None = None

        try:
            value = await asyncio.wait_for(
                executor(attempt_number, attempt_key_hash),
                timeout=policy.attempt_timeout_seconds,
            )
        except TimeoutError:
            status = "timeout"
            error_code = "step_timeout"
        except WorkflowStepRetryableError as exc:
            status = "retryable_error"
            error_code = exc.code
        except WorkflowStepTerminalError as exc:
            attempts.append(
                WorkflowStepAttemptReceipt(
                    attempt_number=attempt_number,
                    attempt_key_hash=attempt_key_hash,
                    status="terminal_error",
                    error_code=exc.code,
                    backoff_ms=0,
                    started_at=started_at,
                    finished_at=clock(),
                )
            )
            return WorkflowStepRetryResult(
                status="failed",
                value=None,
                attempts=tuple(attempts),
                error_code=exc.code,
            )
        else:
            attempts.append(
                WorkflowStepAttemptReceipt(
                    attempt_number=attempt_number,
                    attempt_key_hash=attempt_key_hash,
                    status="succeeded",
                    error_code=None,
                    backoff_ms=0,
                    started_at=started_at,
                    finished_at=clock(),
                )
            )
            return WorkflowStepRetryResult(
                status="succeeded",
                value=value,
                attempts=tuple(attempts),
                error_code=None,
            )

        has_next_attempt = attempt_number < policy.max_attempts
        backoff_ms = _backoff_ms(policy, attempt_number) if has_next_attempt else 0
        attempts.append(
            WorkflowStepAttemptReceipt(
                attempt_number=attempt_number,
                attempt_key_hash=attempt_key_hash,
                status=status,
                error_code=error_code,
                backoff_ms=backoff_ms,
                started_at=started_at,
                finished_at=clock(),
            )
        )
        if has_next_attempt:
            await sleeper(backoff_ms / 1_000)

    return WorkflowStepRetryResult(
        status="failed",
        value=None,
        attempts=tuple(attempts),
        error_code="workflow_step_retry_exhausted",
    )


__all__ = [
    "WorkflowStepAttemptReceipt",
    "WorkflowStepRetryPolicy",
    "WorkflowStepRetryResult",
    "WorkflowStepRetryableError",
    "WorkflowStepTerminalError",
    "execute_workflow_step_with_retry",
]
