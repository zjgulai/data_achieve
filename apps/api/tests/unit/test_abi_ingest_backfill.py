"""Pin the multi-day scan backfill window.

A worker that missed 02:15 used to skip the day forever. The backfill fills
every missing T-1 date from ``schedule_state.last_target_date``, capped at
seven days, and a brand-new account starts with only the latest T-1.
"""

from __future__ import annotations

from datetime import date

from data_intelligence_hub.abi.ingest import backfill_dates

LATEST = date(2026, 11, 1)


def test_new_account_only_gets_latest() -> None:
    assert backfill_dates(None, LATEST) == [LATEST]


def test_current_account_gets_nothing() -> None:
    assert backfill_dates(LATEST, LATEST) == []


def test_future_state_gets_nothing() -> None:
    assert backfill_dates(date(2026, 11, 2), LATEST) == []


def test_gap_is_filled_in_order() -> None:
    assert backfill_dates(date(2026, 10, 29), LATEST) == [
        date(2026, 10, 30),
        date(2026, 10, 31),
        LATEST,
    ]


def test_gap_is_capped_at_max_days() -> None:
    dates = backfill_dates(date(2026, 10, 1), LATEST, max_days=7)
    assert len(dates) == 7
    assert dates[0] == date(2026, 10, 26)
    assert dates[-1] == LATEST
