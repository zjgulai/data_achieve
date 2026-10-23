"""数说统一回复模板的契约测试。"""

from __future__ import annotations

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import replies
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
    assert "k9x-88ff" not in result
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
    assert "sk-live-999" not in result
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
