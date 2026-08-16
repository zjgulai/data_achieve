from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from data_intelligence_hub.services.workflow_execution.retry import (
    WorkflowStepRetryableError,
    WorkflowStepRetryPolicy,
    WorkflowStepTerminalError,
    execute_workflow_step_with_retry,
)


def _clock() -> datetime:
    return datetime(2026, 7, 22, 8, 0, tzinfo=UTC)


async def test_retryable_failure_uses_bounded_backoff_and_stable_attempt_keys() -> None:
    calls: list[tuple[int, str]] = []
    sleeps: list[float] = []

    async def executor(attempt_number: int, attempt_key_hash: str) -> str:
        calls.append((attempt_number, attempt_key_hash))
        if attempt_number < 3:
            raise WorkflowStepRetryableError("step_network_unavailable")
        return "fixture-receipt"

    result = await execute_workflow_step_with_retry(
        step_idempotency_key_hash="sha256:" + "a" * 64,
        policy=WorkflowStepRetryPolicy(
            max_attempts=3,
            attempt_timeout_seconds=1,
            base_backoff_ms=100,
            max_backoff_ms=150,
        ),
        executor=executor,
        sleeper=lambda seconds: _record_sleep(sleeps, seconds),
        clock=_clock,
    )

    assert result.status == "succeeded"
    assert result.value == "fixture-receipt"
    assert [item.status for item in result.attempts] == [
        "retryable_error",
        "retryable_error",
        "succeeded",
    ]
    assert [item.backoff_ms for item in result.attempts] == [100, 150, 0]
    assert sleeps == [0.1, 0.15]
    assert [item.attempt_key_hash for item in result.attempts] == [key for _, key in calls]
    assert len(set(key for _, key in calls)) == 3

    replay = await execute_workflow_step_with_retry(
        step_idempotency_key_hash="sha256:" + "a" * 64,
        policy=WorkflowStepRetryPolicy(
            max_attempts=1,
            attempt_timeout_seconds=1,
            base_backoff_ms=0,
            max_backoff_ms=0,
        ),
        executor=lambda attempt_number, attempt_key_hash: _return_value(
            (attempt_number, attempt_key_hash)
        ),
        sleeper=lambda seconds: _record_sleep([], seconds),
        clock=_clock,
    )
    assert replay.value == calls[0]


async def _record_sleep(target: list[float], seconds: float) -> None:
    target.append(seconds)


async def _return_value[T](value: T) -> T:
    return value


async def test_timeout_retries_only_to_the_frozen_attempt_limit() -> None:
    calls = 0

    async def executor(attempt_number: int, attempt_key_hash: str) -> str:
        nonlocal calls
        _ = (attempt_number, attempt_key_hash)
        calls += 1
        await asyncio.sleep(0.02)
        return "late"

    result = await execute_workflow_step_with_retry(
        step_idempotency_key_hash="sha256:" + "b" * 64,
        policy=WorkflowStepRetryPolicy(
            max_attempts=2,
            attempt_timeout_seconds=0.001,
            base_backoff_ms=1,
            max_backoff_ms=1,
        ),
        executor=executor,
        sleeper=lambda seconds: _record_sleep([], seconds),
        clock=_clock,
    )

    assert result.status == "failed"
    assert result.error_code == "workflow_step_retry_exhausted"
    assert [item.status for item in result.attempts] == ["timeout", "timeout"]
    assert [item.backoff_ms for item in result.attempts] == [1, 0]
    assert calls == 2


async def test_terminal_and_unexpected_failures_never_retry() -> None:
    terminal_calls = 0

    async def terminal(attempt_number: int, attempt_key_hash: str) -> str:
        nonlocal terminal_calls
        _ = (attempt_number, attempt_key_hash)
        terminal_calls += 1
        raise WorkflowStepTerminalError("step_request_rejected")

    terminal_result = await execute_workflow_step_with_retry(
        step_idempotency_key_hash="sha256:" + "c" * 64,
        policy=WorkflowStepRetryPolicy(
            max_attempts=3,
            attempt_timeout_seconds=1,
            base_backoff_ms=10,
            max_backoff_ms=20,
        ),
        executor=terminal,
        sleeper=lambda seconds: _record_sleep([], seconds),
        clock=_clock,
    )

    assert terminal_result.status == "failed"
    assert terminal_result.error_code == "step_request_rejected"
    assert [item.status for item in terminal_result.attempts] == ["terminal_error"]
    assert terminal_calls == 1

    async def unexpected(attempt_number: int, attempt_key_hash: str) -> str:
        _ = (attempt_number, attempt_key_hash)
        raise RuntimeError("unexpected fixture bug")

    with pytest.raises(RuntimeError, match="unexpected fixture bug"):
        await execute_workflow_step_with_retry(
            step_idempotency_key_hash="sha256:" + "d" * 64,
            policy=WorkflowStepRetryPolicy(
                max_attempts=3,
                attempt_timeout_seconds=1,
                base_backoff_ms=10,
                max_backoff_ms=20,
            ),
            executor=unexpected,
            sleeper=lambda seconds: _record_sleep([], seconds),
            clock=_clock,
        )


def test_retry_policy_and_error_codes_fail_closed() -> None:
    with pytest.raises(ValueError, match="workflow_step_retry_attempts_invalid"):
        WorkflowStepRetryPolicy(
            max_attempts=0,
            attempt_timeout_seconds=1,
            base_backoff_ms=0,
            max_backoff_ms=0,
        )
    with pytest.raises(ValueError, match="workflow_step_retry_backoff_invalid"):
        WorkflowStepRetryPolicy(
            max_attempts=2,
            attempt_timeout_seconds=1,
            base_backoff_ms=20,
            max_backoff_ms=10,
        )
    with pytest.raises(ValueError, match="workflow_step_retryable_code_invalid"):
        WorkflowStepRetryableError("arbitrary_error")
    with pytest.raises(ValueError, match="workflow_step_terminal_code_invalid"):
        WorkflowStepTerminalError("arbitrary_error")
