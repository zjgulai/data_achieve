"""Status semantics for /api/collectors/docs."""

from __future__ import annotations

from data_intelligence_hub.api.routes.collectors import (
    EndpointTestResult,
    _counts_as_success,
)


def _result(status: str | None, records: int | None) -> EndpointTestResult:
    return EndpointTestResult(
        endpoint_type="example",
        last_run_id="run-1",
        last_run_status=status,
        last_run_at="2026-10-21T00:00:00Z",
        last_records_count=records,
        last_error_message=None,
    )


def test_success_with_records_counts() -> None:
    assert _counts_as_success(_result("success", 3)) is True


def test_success_with_zero_records_is_not_success() -> None:
    assert _counts_as_success(_result("success", 0)) is False


def test_success_with_missing_count_is_not_success() -> None:
    assert _counts_as_success(_result("success", None)) is False


def test_failed_or_missing_result_does_not_count() -> None:
    assert _counts_as_success(_result("failed", 3)) is False
    assert _counts_as_success(None) is False
