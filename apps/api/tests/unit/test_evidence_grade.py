"""B2-03 + B2-04：证据阈值表与证据等级纯函数。

L0 与 L1 不由 run 等级函数产生。

- ``L0_unverified`` 属于工具合同：工具有定义但未实测。
  ``MAX_EVIDENCE_GRADE_BY_EXECUTION_KIND["unsupported"]`` 就是 L0。
- ``L1_contract`` 属于合同校验阶段：契约已校验但未调用。
  此时还没有 run，所以没有 run 等级。
- run 从夹具回放开始。``live_call=False`` 得到 ``L2_fixture_local``。

因此 ``compute_run_evidence_grade`` 只产出 L2、L3、L4。
"""

from __future__ import annotations

import builtins
import socket
import time
import uuid
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import data_intelligence_hub.tool_catalog.evidence_grade as evidence_grade_module
from data_intelligence_hub.tool_catalog.evidence_grade import (
    GRADE_ORDER,
    MAX_EVIDENCE_GRADE_BY_EXECUTION_KIND,
    EvidenceGrade,
    RunEvidenceGrade,
    authorization_is_usable,
    compute_run_evidence_grade,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    EVIDENCE_THRESHOLDS,
    threshold_for,
)

RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
AUTH_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _inputs(**overrides: Any) -> dict[str, Any]:
    """全满足的输入。用例只覆盖需要变化的字段。"""
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "live_call": True,
        "authorization_id": AUTH_ID,
        "sample_n": 30,
        "required_n": 30,
        "window_days": 60,
        "required_window_days": 60,
        "source_count": 2,
        "required_source_count": 2,
    }
    values.update(overrides)
    return values


# ---------- 阈值表 ----------


@pytest.mark.parametrize(
    ("template_id", "required_n", "required_window_days", "required_source_count"),
    [
        ("t1_voc", 30, 60, 2),
        ("t2_competitor", 20, 30, 2),
        ("t3_selection", 50, 90, 2),
        ("t4_creator", 20, 30, 2),
        ("t5_compliance", 0, 365, 2),
    ],
)
def test_thresholds_match_prd_5_4_2(
    template_id: str,
    required_n: int,
    required_window_days: int,
    required_source_count: int,
) -> None:
    threshold = threshold_for(template_id)
    assert threshold.template_id == template_id
    assert threshold.required_n == required_n
    assert threshold.required_window_days == required_window_days
    assert threshold.required_source_count == required_source_count
    assert threshold.n_basis


def test_t1_threshold_counts_frame_members_per_layer() -> None:
    threshold = threshold_for("t1_voc")
    assert "帧成员数" in threshold.n_basis
    assert "每层 30 条" in threshold.n_basis


def test_t2_threshold_counts_normalized_records_per_brand_market() -> None:
    threshold = threshold_for("t2_competitor")
    assert "规范记录数" in threshold.n_basis
    assert "每 brand×market 20 条商品" in threshold.n_basis


def test_t3_threshold_counts_normalized_records_per_price_band() -> None:
    threshold = threshold_for("t3_selection")
    assert "规范记录数" in threshold.n_basis
    assert "每价格带 50 条商品" in threshold.n_basis


def test_t4_threshold_keeps_both_prd_conditions() -> None:
    """PRD 原文是「20 个达人，每人 20 条评论」。这是两个条件。

    required_n 是每个达人的评论数，required_entity_count 是达人数。
    合成一个 400 会放过「400 条全来自 1 个达人」，因此不允许。
    """
    threshold = threshold_for("t4_creator")
    assert threshold.required_n == 20
    assert threshold.required_entity_count == 20
    assert "可用评论数" in threshold.n_basis
    assert "20 个达人" in threshold.n_basis


def test_only_t4_requires_entity_count() -> None:
    for template_id in ("t1_voc", "t2_competitor", "t3_selection", "t5_compliance"):
        assert threshold_for(template_id).required_entity_count == 0, template_id


def test_t4_comments_from_too_few_creators_is_l3() -> None:
    """评论数达标但达人不足，只能是 L3。"""
    threshold = threshold_for("t4_creator")
    result = compute_run_evidence_grade(
        run_id=uuid.uuid4(),
        live_call=True,
        authorization_id=uuid.uuid4(),
        sample_n=400,  # 单个达人 400 条
        required_n=threshold.required_n,
        window_days=30,
        required_window_days=threshold.required_window_days,
        source_count=2,
        required_source_count=threshold.required_source_count,
        entity_count=1,
        required_entity_count=threshold.required_entity_count,
    )
    assert result.grade == EvidenceGrade.L3_LIVE_SINGLE


def test_t4_all_creators_meet_threshold_is_l4() -> None:
    threshold = threshold_for("t4_creator")
    result = compute_run_evidence_grade(
        run_id=uuid.uuid4(),
        live_call=True,
        authorization_id=uuid.uuid4(),
        sample_n=20,  # 最少那位达人的评论数
        required_n=threshold.required_n,
        window_days=30,
        required_window_days=threshold.required_window_days,
        source_count=2,
        required_source_count=threshold.required_source_count,
        entity_count=20,
        required_entity_count=threshold.required_entity_count,
    )
    assert result.grade == EvidenceGrade.L4_AUTHORIZED_LIVE
    assert result.entity_count == 20


def test_t5_has_no_sample_threshold_and_requires_twelve_month_window() -> None:
    """T5 只规定时间窗，没有样本条数阈值。所以 required_n 取 0。"""
    threshold = threshold_for("t5_compliance")
    assert threshold.required_n == 0
    assert threshold.required_window_days == 365
    assert "12 个月窗" in threshold.n_basis


def test_threshold_for_unknown_template_raises_key_error() -> None:
    with pytest.raises(KeyError):
        threshold_for("t9_unknown")


def test_threshold_table_is_read_only_and_entries_are_frozen() -> None:
    assert set(EVIDENCE_THRESHOLDS) == {
        "t1_voc",
        "t2_competitor",
        "t3_selection",
        "t4_creator",
        "t5_compliance",
    }
    with pytest.raises(TypeError):
        EVIDENCE_THRESHOLDS["t1_voc"] = threshold_for("t2_competitor")  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        threshold_for("t1_voc").required_n = 1  # type: ignore[misc]


# ---------- 等级计算 ----------


def test_not_live_call_is_l2_and_earlier_branch_wins() -> None:
    result = compute_run_evidence_grade(
        **_inputs(
            live_call=False,
            authorization_id=None,
            sample_n=0,
            window_days=0,
            source_count=0,
        )
    )
    assert result.grade is EvidenceGrade.L2_FIXTURE_LOCAL


def test_missing_authorization_is_l3() -> None:
    result = compute_run_evidence_grade(**_inputs(authorization_id=None))
    assert result.grade is EvidenceGrade.L3_LIVE_SINGLE


def test_sample_below_threshold_is_l3() -> None:
    result = compute_run_evidence_grade(**_inputs(sample_n=29, required_n=30))
    assert result.grade is EvidenceGrade.L3_LIVE_SINGLE


def test_window_below_threshold_is_l3() -> None:
    result = compute_run_evidence_grade(
        **_inputs(window_days=59, required_window_days=60)
    )
    assert result.grade is EvidenceGrade.L3_LIVE_SINGLE


def test_source_count_below_threshold_is_l3() -> None:
    result = compute_run_evidence_grade(
        **_inputs(source_count=1, required_source_count=2)
    )
    assert result.grade is EvidenceGrade.L3_LIVE_SINGLE


def test_all_conditions_met_is_l4_at_equal_boundaries() -> None:
    result = compute_run_evidence_grade(**_inputs())
    assert result.grade is EvidenceGrade.L4_AUTHORIZED_LIVE


def test_compute_only_returns_l2_l3_l4() -> None:
    """固定运行函数的产出范围。L0/L1 不属于 run 等级。"""
    grades: set[EvidenceGrade] = set()
    for live_call in (False, True):
        for authorization_id in (None, AUTH_ID):
            for sample_n in (0, 30):
                for window_days in (0, 60):
                    for source_count in (0, 2):
                        result = compute_run_evidence_grade(
                            **_inputs(
                                live_call=live_call,
                                authorization_id=authorization_id,
                                sample_n=sample_n,
                                window_days=window_days,
                                source_count=source_count,
                            )
                        )
                        grades.add(result.grade)
    assert grades == {
        EvidenceGrade.L2_FIXTURE_LOCAL,
        EvidenceGrade.L3_LIVE_SINGLE,
        EvidenceGrade.L4_AUTHORIZED_LIVE,
    }
    assert EvidenceGrade.L0_UNVERIFIED not in grades
    assert EvidenceGrade.L1_CONTRACT not in grades


def test_run_evidence_grade_fields_match_prd_table() -> None:
    """PRD 5.4.2 的字段必须在前，顺序一致。

    entity_count 与 required_entity_count 是 T4 复合阈值的补充字段，
    PRD 表里没有。它们只能追加在末尾，不得插进 PRD 字段之间。
    """
    prd_fields = (
        "run_id",
        "live_call",
        "authorization_id",
        "sample_n",
        "required_n",
        "window_days",
        "required_window_days",
        "source_count",
        "required_source_count",
        "grade",
    )
    actual = tuple(RunEvidenceGrade.__dataclass_fields__)
    assert actual[: len(prd_fields)] == prd_fields
    assert actual[len(prd_fields):] == ("entity_count", "required_entity_count")


def test_grade_values_match_contract_freeze_v1() -> None:
    assert {grade.value for grade in EvidenceGrade} == {
        "L0_unverified",
        "L1_contract",
        "L2_fixture_local",
        "L3_live_single",
        "L4_authorized_live",
    }
    assert [GRADE_ORDER[grade] for grade in EvidenceGrade] == [0, 1, 2, 3, 4]


def test_execution_kind_max_grade_mapping_matches_architecture_rule() -> None:
    """L0 来自 unsupported 工具的上限。映射里没有 L1。"""
    assert MAX_EVIDENCE_GRADE_BY_EXECUTION_KIND == {
        "offline": EvidenceGrade.L2_FIXTURE_LOCAL,
        "guarded_http": EvidenceGrade.L4_AUTHORIZED_LIVE,
        "provider_api": EvidenceGrade.L4_AUTHORIZED_LIVE,
        "unsupported": EvidenceGrade.L0_UNVERIFIED,
    }
    assert EvidenceGrade.L1_CONTRACT not in MAX_EVIDENCE_GRADE_BY_EXECUTION_KIND.values()


def test_t1_threshold_feeds_the_grade_function() -> None:
    threshold = threshold_for("t1_voc")
    result = compute_run_evidence_grade(
        run_id=RUN_ID,
        live_call=True,
        authorization_id=AUTH_ID,
        sample_n=threshold.required_n,
        required_n=threshold.required_n,
        window_days=threshold.required_window_days,
        required_window_days=threshold.required_window_days,
        source_count=threshold.required_source_count,
        required_source_count=threshold.required_source_count,
    )
    assert result.grade is EvidenceGrade.L4_AUTHORIZED_LIVE


# ---------- 授权过期 ----------


@dataclass(frozen=True)
class _Authorization:
    expires_at: datetime


NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def test_authorization_is_usable_before_expiry() -> None:
    authorization = _Authorization(expires_at=NOW + timedelta(seconds=1))
    assert authorization_is_usable(authorization, NOW) is True


def test_authorization_is_expired_at_and_after_expiry() -> None:
    at_expiry = _Authorization(expires_at=NOW)
    after_expiry = _Authorization(expires_at=NOW - timedelta(seconds=1))
    assert authorization_is_usable(at_expiry, NOW) is False
    assert authorization_is_usable(after_expiry, NOW) is False


def test_missing_authorization_is_not_usable() -> None:
    assert authorization_is_usable(None, NOW) is False


def test_authorization_timezone_awareness_must_match() -> None:
    aware = _Authorization(expires_at=NOW)
    naive_now = datetime(2026, 10, 21, 12, 0)
    with pytest.raises(ValueError):
        authorization_is_usable(aware, naive_now)


# ---------- 纯函数性 ----------


def test_compute_is_pure_and_does_no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("纯函数不得发起 I/O")

    class _NoClock:
        @classmethod
        def now(cls, tz: object = None) -> None:
            raise AssertionError("纯函数不得读取时钟")

    monkeypatch.setattr(builtins, "open", fail_io)
    monkeypatch.setattr(socket, "socket", fail_io)
    monkeypatch.setattr(socket, "create_connection", fail_io)
    monkeypatch.setattr(time, "time", fail_io)
    monkeypatch.setattr(evidence_grade_module, "datetime", _NoClock)

    first = compute_run_evidence_grade(**_inputs())
    second = compute_run_evidence_grade(**_inputs())

    assert first == second
    assert authorization_is_usable(_Authorization(NOW), NOW) is False
