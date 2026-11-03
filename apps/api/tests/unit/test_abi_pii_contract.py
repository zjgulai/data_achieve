"""Pin the ABI PII input contract.

History:

- Before 2026-11-02 ``AbiColumnCreate`` had no ``pii_class`` field and Pydantic's
  default ``extra="ignore"`` silently dropped it. A caller could pass
  ``pii_class="direct"`` and believe the policy was set, while every column
  landed as ``unknown``.
- 2026-11-02 fixed that by rejecting unknown fields at the request boundary.
  Better than silent loss, but the caller still could not declare a class at
  dataset creation — they had to create first, then ``PUT /policy``.
- 2026-11-03 made ``pii_class`` a real field, persisted in the same
  transaction as the dataset.

These tests pin all three properties that must hold together:
1. ``pii_class`` is accepted and carried on the model.
2. Omitted ``pii_class`` means "not yet judged" — never silently defaulted
   to ``none``.
3. Misspelled fields still 422 (``extra="forbid"`` is retained), and a
   ``mask_rule`` without a class is rejected.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.abi import AbiColumnCreate, AbiDatasetCreateRequest


def test_column_accepts_known_fields() -> None:
    column = AbiColumnCreate(column_name="post_id", data_type="text")
    assert column.column_name == "post_id"
    assert column.data_type == "text"


def test_column_accepts_pii_class() -> None:
    """声明分类现在是合法输入，不再 422。"""
    column = AbiColumnCreate(
        column_name="author_email", data_type="text", pii_class="direct"
    )
    assert column.pii_class == "direct"


def test_omitted_pii_class_stays_none_not_none_class() -> None:
    """不传 != 传 none。

    ``None`` 表示「还没判定」，落库时不写策略行，字段按 unknown 处理，
    查询与导出都会拒绝。若被默认成 ``"none"``，就等于凭空判定「没有 PII」，
    是 fail-open。
    """
    column = AbiColumnCreate(column_name="mystery", data_type="text")
    assert column.pii_class is None
    assert column.mask_rule is None


def test_column_accepts_mask_rule_with_class() -> None:
    column = AbiColumnCreate(
        column_name="phone", data_type="text", pii_class="direct", mask_rule="last4"
    )
    assert column.mask_rule == "last4"


def test_mask_rule_without_class_is_rejected() -> None:
    """没有分类的遮罩规则没有意义：它挂不到任何策略行上。"""
    with pytest.raises(ValidationError):
        AbiColumnCreate(column_name="phone", data_type="text", mask_rule="last4")


def test_misspelled_field_is_still_rejected() -> None:
    """``extra="forbid"`` 保留：它挡的是拼错的字段名，不是 pii_class。

    这条防止「支持 pii_class」被误做成「放开未知字段」，那样
    ``pii_clas`` 这类拼写错误会重新变成静默丢弃。
    """
    with pytest.raises(ValidationError):
        AbiColumnCreate(  # type: ignore[call-arg]
            column_name="author_email", data_type="text", pii_clas="direct"
        )


def test_dataset_rejects_pii_class_at_top_level() -> None:
    """分类属于列，不属于数据集。顶层传 pii_class 仍是错误。"""
    with pytest.raises(ValidationError):
        AbiDatasetCreateRequest(  # type: ignore[call-arg]
            slug="pii-probe",
            name="PII 探针",
            source_kind="upload",
            pii_class="direct",
        )


def test_nested_column_carries_pii_class() -> None:
    request = AbiDatasetCreateRequest(
        slug="pii-probe",
        name="PII 探针",
        source_kind="upload",
        columns=[{"column_name": "author_email", "pii_class": "direct"}],
    )
    assert request.columns is not None
    assert request.columns[0].pii_class == "direct"


def test_invalid_pii_class_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AbiColumnCreate(column_name="x", data_type="text", pii_class="pii")
