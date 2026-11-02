"""Pin the INSERT batching against asyncpg's parameter limit.

A 4,856-row x 12-column upload built a 58k-parameter statement and failed with
``the number of query arguments cannot exceed 32767``. The 99-row smoke did not
catch it because 1,188 parameters fit.

The limit is 30,000, not 60,000. Leave margin below asyncpg's 32,767.
"""

from __future__ import annotations

from data_intelligence_hub.services.abi_upload import (
    MAX_BIND_PARAMETERS,
    _value_batches,
)


def test_bind_parameter_limit_has_margin() -> None:
    assert MAX_BIND_PARAMETERS <= 32_000


def test_batches_stay_under_the_limit_for_wide_rows() -> None:
    values: list[dict[str, object]] = [
        {f"c{index}": index for index in range(12)} for _ in range(5_000)
    ]
    batches = _value_batches(values)
    assert sum(len(batch) for batch in batches) == 5_000
    assert max(len(batch) for batch in batches) * 12 <= MAX_BIND_PARAMETERS


def test_batches_cover_every_row() -> None:
    values: list[dict[str, object]] = [{"c": index} for index in range(10)]
    batches = _value_batches(values)
    assert [row for batch in batches for row in batch] == values
