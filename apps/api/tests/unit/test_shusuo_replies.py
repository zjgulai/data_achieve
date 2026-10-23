"""数说统一回复模板的契约测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import commands, replies
from data_intelligence_hub.agents.shusuo.intents import Proposal
from data_intelligence_hub.agents.shusuo.proposal_store import (
    ProposalLookup,
    replace_pending,
)
from data_intelligence_hub.agents.shusuo.proposal_store import (
    clear_all as clear_proposal_store,
)


def _pending(proposal: Proposal):
    clear_proposal_store()
    return replace_pending("chat-r", "ou-r", proposal)


def _preflight(**overrides):
    values = {
        "allowed": True,
        "availability": "verified",
        "normalized_params": {"keyword": "AI", "max_items": 10},
        "errors": (),
        "warnings": ("费用未知，按上游实际计费。",),
        "cost_notice": "费用未知，按上游实际计费",
    }
    values.update(overrides)
    return shusuo_capabilities.PreflightResult(**values)


def _outcome(**overrides):
    values: dict = {
        "ok": True,
        "text": "",
        "endpoint_type": "tikhub_reddit_search",
        "task_run_id": "run-id",
        "records_count": 10,
        "duration_ms": 1234,
        "total_cost_usd": None,
        "records": (),
        "error_message": None,
    }
    values.update(overrides)
    return shusuo_capabilities.CollectOutcome(**values)


def test_fit_text_caps_to_6000_and_redacts_secret() -> None:
    text = "token=secret-value " + "x" * 7000
    result = replies.fit_text(text)
    assert len(result) <= 6000
    assert "secret-value" not in result


def test_fit_text_short_circuit_keeps_text() -> None:
    assert replies.fit_text("正常文本") == "正常文本"


def test_fit_text_redacts_bearer_and_api_key() -> None:
    text = "Authorization: Bearer sk-secret123 api_key=k9x-88ff"
    result = replies.fit_text(text)
    assert "sk-secret123" not in result
    assert "SECRET_tive2oq5" not in result
    assert "[redacted]" in result


def _success_outcome_with_records(count: int):
    records = tuple(
        {"content": {"title": f"row {i}", "url": f"https://example.com/{i}"}}
        for i in range(count)
    )
    return _outcome(records=records)


def test_success_template_returns_at_most_three_records() -> None:
    outcome = _success_outcome_with_records(5)
    result = replies.collect_success_text(outcome)
    assert "row 0" in result
    assert "row 2" in result
    assert "row 3" not in result
    assert len(result) <= 6000


def test_success_template_includes_run_link_and_usage() -> None:
    outcome = _outcome(
        task_run_id="abc-123",
        duration_ms=1500,
        total_cost_usd="0.42",
    )
    result = replies.collect_success_text(outcome)
    assert "/runs/abc-123" in result
    assert "/collect/" not in result
    assert "1.5 秒" in result
    assert "$0.42" in result


def test_success_template_without_cost_omits_line() -> None:
    outcome = _outcome(total_cost_usd=None)
    result = replies.collect_success_text(outcome)
    assert "费用" not in result


def test_error_template_does_not_render_exception_class() -> None:
    outcome = _outcome(ok=False, error_message="RuntimeError: token=abc")
    result = replies.collect_failure_text(outcome)
    assert "RuntimeError" not in result
    assert "abc" not in result


def test_error_template_strips_non_error_exception_class() -> None:
    """异常类名不以 Error 结尾（如 HTTPException）也要剥掉。"""
    outcome = _outcome(ok=False, error_message="HTTPException: upstream 502 token=abc")
    result = replies.collect_failure_text(outcome)
    assert "HTTPException" not in result
    assert "abc" not in result
    assert "upstream 502" in result


def test_error_template_defaults_reason_without_error_message() -> None:
    """error_message 为空时用固定兜底文案，而不是显示异常细节。"""
    outcome = _outcome(ok=False, error_message=None)
    result = replies.collect_failure_text(outcome)
    assert "上游没有返回记录" in result


def test_error_template_rejection_reason_beats_default() -> None:
    """预执行拒绝路径必须显示真实原因，不得落到"上游没有返回记录"兜底。"""
    outcome = _outcome(
        ok=False,
        endpoint_type="no_such_endpoint",
        error_message="没有找到端点：no_such_endpoint",
    )
    result = replies.collect_failure_text(outcome)
    assert "没有找到端点：no_such_endpoint" in result
    assert "上游没有返回记录" not in result


def test_error_template_policy_reason_not_leaked() -> None:
    """collect() 的拒绝路径只携带固定安全文案，原文绝不进回复。"""
    policy_secret = "collection_policy_denied TOPSECRET-REASON"

    class _Live:
        availability = "config-gated"
        policy_block_reason = policy_secret
        missing_configuration = ()

    outcome = shusuo_capabilities.CollectOutcome(
        ok=False,
        text="",
        endpoint_type="demo_endpoint",
        error_message=shusuo_capabilities._POLICY_BLOCK_TEXT,
    )
    result = replies.collect_failure_text(outcome)
    assert "TOPSECRET-REASON" not in result
    assert "collection_policy_denied" not in result
    assert "当前受安全策略限制" in result


def _endpoint(
    *,
    status: str = "verified",
    policy_block_reason: str | None = None,
):
    from data_intelligence_hub.platform_packages.models import PackageEndpoint

    return PackageEndpoint(
        capability_id="demo_endpoint",
        canonical_capability_id="demo_endpoint",
        is_alias_view=False,
        endpoint_type="demo_endpoint",
        label="demo",
        platform="test",
        description="test",
        status=status,
        required_params=(),
        optional_params=(),
        cost_hint=None,
        provider="test",
        provider_group="test",
        provider_label="test",
        content_type="post",
        method="GET",
        param_fields={},
        policy_block_reason=policy_block_reason,
    )


def _availability(
    *, availability: str = "verified", policy_block_reason: str | None = None
):
    from data_intelligence_hub.platform_packages.status import EndpointAvailability

    return EndpointAvailability(
        endpoint_type="demo_endpoint",
        availability=availability,
        missing_configuration=(),
        last_test_status=None,
        last_test_at=None,
        last_records_count=None,
        last_error_message=None,
        policy_block_reason=policy_block_reason,
    )


@pytest.mark.parametrize(
    ("blocked_case", "expected_reason"),
    [
        ("not_found", "没有找到端点：demo_endpoint"),
        ("disabled", "demo_endpoint 已下线，不能调用。"),
        ("policy", "当前受安全策略限制，无法执行该端点。"),
        ("bad_project_id", "服务端默认 project_id 配置无效。"),
    ],
)
async def test_collect_rejection_paths_carry_safe_reason(
    monkeypatch, blocked_case: str, expected_reason: str
) -> None:
    """预执行拒绝必须带安全 error_message，collect_failure_text 不得落到采集兜底。"""
    if blocked_case == "not_found":
        monkeypatch.setattr(
            shusuo_capabilities,
            "get_capability",
            AsyncMock(side_effect=shusuo_capabilities.CapabilityNotFoundError("demo_endpoint")),
        )
        monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    elif blocked_case == "disabled":
        monkeypatch.setattr(
            shusuo_capabilities,
            "get_capability",
            AsyncMock(return_value=_endpoint(status="disabled")),
        )
        monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    elif blocked_case == "policy":
        monkeypatch.setattr(
            shusuo_capabilities,
            "get_capability",
            AsyncMock(return_value=_endpoint(status="config-gated")),
        )
        monkeypatch.setattr(
            shusuo_capabilities,
            "live_status",
            AsyncMock(
                return_value={
                    "demo_endpoint": _availability(
                        availability="config-gated",
                        policy_block_reason="collection_policy_denied TOPSECRET-REASON",
                    )
                }
            ),
        )
    else:  # bad_project_id
        from data_intelligence_hub.agents.shusuo.config import get_shushuo_config

        monkeypatch.setattr(
            shusuo_capabilities, "get_capability", AsyncMock(return_value=_endpoint())
        )
        monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
        monkeypatch.setenv("SHUSUO_DEFAULT_PROJECT_ID", "not-a-uuid")
        get_shushuo_config.cache_clear()

    try:
        outcome = await shusuo_capabilities.collect("demo_endpoint", {})
    finally:
        from data_intelligence_hub.agents.shusuo.config import get_shushuo_config

        get_shushuo_config.cache_clear()

    assert outcome.ok is False
    assert outcome.error_message == expected_reason
    assert "TOPSECRET-REASON" not in (outcome.error_message or "")

    result = commands._collect_reply_text(outcome)
    assert expected_reason in result
    assert "上游没有返回记录" not in result
    assert "TOPSECRET-REASON" not in result


async def test_collect_exception_path_carries_message_without_class_name(
    monkeypatch,
) -> None:
    """异常路径：类名只进日志，error_message 只带 str(exc)，回复不再出现类名。"""
    from data_intelligence_hub.platform_packages.models import PackageEndpoint

    endpoint = PackageEndpoint(
        capability_id="demo_endpoint",
        canonical_capability_id="demo_endpoint",
        is_alias_view=False,
        endpoint_type="demo_endpoint",
        label="demo",
        platform="test",
        description="test",
        status="verified",
        required_params=(),
        optional_params=(),
        cost_hint=None,
        provider="test",
        provider_group="test",
        provider_label="test",
        content_type="post",
        method="GET",
        param_fields={},
        policy_block_reason=None,
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))

    async def raise_exc(endpoint_type, project_id, params):
        raise RuntimeError("token=abc upstream exploded")

    monkeypatch.setattr(
        shusuo_capabilities, "collect_capability", AsyncMock(side_effect=raise_exc)
    )
    outcome = await shusuo_capabilities.collect("demo_endpoint", {})
    assert outcome.ok is False
    assert outcome.error_message == "token=abc upstream exploded"
    assert "RuntimeError" not in outcome.error_message

    result = commands._collect_reply_text(outcome)
    assert "RuntimeError" not in result
    assert "abc" not in result
    assert "upstream exploded" not in result or "exploded" in result


def test_error_template_redacts_secrets_in_records_and_message() -> None:
    outcome = _outcome(
        ok=False,
        records=({"content": {"text": "password=hunter2"}},),
        error_message="token=leaky",
    )
    result = replies.collect_failure_text(outcome)
    assert "hunter2" not in result
    assert "leaky" not in result


def test_collect_success_text_is_fit_through_redaction() -> None:
    """记录正文携带密钥时也必须先脱敏再输出。"""
    leaked = _outcome(
        records=({"content": {"title": "token=very-secret-value"}},),
    )
    result = replies.collect_success_text(leaked)
    assert "very-secret-value" not in result


def test_proposal_text_shows_summary_and_confirmation() -> None:
    proposal = Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"keyword": "AI", "max_items": 10},
        title="Reddit 关键词搜索：AI",
        estimated_items=10,
        cost_notice="费用未知，按上游实际计费",
    )
    pending = _pending(proposal)
    result = replies.proposal_text(pending, _preflight())
    assert "Reddit 关键词搜索：AI" in result
    assert "tikhub_reddit_search" in result
    assert "keyword=AI" in result
    assert "费用未知，按上游实际计费" in result
    assert "确认" in result
    assert len(result) <= 6000


def test_proposal_text_redacts_secret_param_values() -> None:
    proposal = Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI", "api_key": "sk-live-999"},
        title="带密钥参数",
    )
    pending = _pending(proposal)
    result = replies.proposal_text(
        pending,
        _preflight(
            normalized_params={"query": "AI", "api_key": "sk-live-999"},
        ),
    )
    assert "SECRET_5zwjkfhe" not in result
    assert "[redacted]" in result


def test_preflight_error_text_joins_errors_and_warnings() -> None:
    result = replies.preflight_error_text(
        _preflight(
            allowed=False,
            errors=("缺少必填参数：query", "未知参数：foo"),
            warnings=(),
        )
    )
    assert "缺少必填参数：query" in result
    assert "未知参数：foo" in result


def test_preflight_error_text_keeps_cost_unknown_warning() -> None:
    result = replies.preflight_error_text(
        _preflight(
            allowed=False,
            errors=("端点当前不可执行（最近失败）。",),
        )
    )
    assert "费用未知，按上游实际计费" in result


def test_pending_status_text_covers_all_lookups() -> None:
    assert "没有" in replies.pending_status_text(ProposalLookup.MISSING)
    assert "过期" in replies.pending_status_text(ProposalLookup.EXPIRED)
    assert "新提案" in replies.pending_status_text(ProposalLookup.REPLACED)
    assert "无法" in replies.pending_status_text(ProposalLookup.FORBIDDEN)
    assert replies.pending_status_text(ProposalLookup.ACTIVE) == ""


@pytest.mark.parametrize(
    ("error_message", "sentinel"),
    [
        ("没有找到端点：no_such_endpoint", "no_such_endpoint"),
        ("demo_endpoint 已下线，不能调用。", "已下线"),
        ("当前受安全策略限制，无法执行该端点。", "安全策略"),
        ("服务端默认 project_id 配置无效。", "project_id"),
    ],
)
def test_collect_reply_text_surfaces_rejection_reason(
    error_message: str, sentinel: str
) -> None:
    """预执行拒绝路径的 outcome 必须把真实原因带给用户，不落到采集兜底文案。"""
    outcome = shusuo_capabilities.CollectOutcome(
        ok=False,
        text="",
        endpoint_type="demo_endpoint",
        error_message=error_message,
    )
    result = commands._collect_reply_text(outcome)
    assert sentinel in result
    assert "上游没有返回记录" not in result


def test_collect_reply_text_hides_exception_class_and_redacts() -> None:
    """异常类名（含非 Error 结尾）不出现在回复，密钥被脱敏，细节进日志不在回复。"""
    outcome = shusuo_capabilities.CollectOutcome(
        ok=False,
        text="",
        endpoint_type="demo_endpoint",
        error_message="HTTPException upstream 502 api_key={{SECRET_fixround1}}",
    )
    result = commands._collect_reply_text(outcome)
    assert "HTTPException" not in result
    assert "SECRET_fixround1" not in result
    assert "upstream 502" in result
