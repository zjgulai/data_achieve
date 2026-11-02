"""Pin the ABI PII input contract.

Before 2026-11-02, ``AbiColumnCreate`` had no ``pii_class`` field and Pydantic's
default ``extra="ignore"`` silently dropped it. A caller could pass
``pii_class="direct"`` and believe the policy was set, while every column landed
as ``unknown``. The 2026-11-02 decision is to reject unknown fields at the
request boundary instead of guessing.

These tests fail if the models go back to silently ignoring ``pii_class``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.abi import AbiColumnCreate, AbiDatasetCreateRequest


def test_column_accepts_known_fields() -> None:
    column = AbiColumnCreate(column_name="post_id", data_type="text")
    assert column.column_name == "post_id"
    assert column.data_type == "text"


def test_column_rejects_pii_class_instead_of_dropping_it() -> None:
    with pytest.raises(ValidationError):
        AbiColumnCreate(  # type: ignore[call-arg]
            column_name="author_email", data_type="text", pii_class="direct"
        )


def test_dataset_rejects_pii_class_instead_of_dropping_it() -> None:
    with pytest.raises(ValidationError):
        AbiDatasetCreateRequest(  # type: ignore[call-arg]
            slug="pii-probe",
            name="PII 探针",
            source_kind="upload",
            pii_class="direct",
        )


def test_nested_column_rejects_pii_class() -> None:
    with pytest.raises(ValidationError):
        AbiDatasetCreateRequest(
            slug="pii-probe",
            name="PII 探针",
            source_kind="upload",
            columns=[{"column_name": "author_email", "pii_class": "direct"}],
        )
