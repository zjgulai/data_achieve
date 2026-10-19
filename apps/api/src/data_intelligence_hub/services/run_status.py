"""Run status vocabulary for collection runs.

`empty` is a terminal state for a clean run that returned zero raw records.
It is not a success and not a failure.
"""

from __future__ import annotations

RUNNING = "running"
SUCCESS = "success"
PARTIAL_SUCCESS = "partial_success"
EMPTY = "empty"
FAILED = "failed"

# Statuses that count as productive success for counters and triggers.
SUCCESSFUL_STATUSES = frozenset({SUCCESS, PARTIAL_SUCCESS})

# Statuses that end a run.
COMPLETED_STATUSES = frozenset({SUCCESS, PARTIAL_SUCCESS, EMPTY, FAILED})


def run_status(
    *,
    result_errors: list[str],
    collected_records: int,
    created_records: int,
) -> str:
    """Return the terminal status for a finished collection attempt.

    `collected_records` is the number of raw records returned by the
    collector. Deduplicated records still count here, so a run whose records
    were all stored by an earlier run stays successful.
    """
    if result_errors and created_records > 0:
        return PARTIAL_SUCCESS
    if result_errors:
        return FAILED
    if collected_records == 0:
        return EMPTY
    return SUCCESS
