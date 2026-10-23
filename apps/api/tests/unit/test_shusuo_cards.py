"""数说确认卡与结果卡的契约测试。

卡片是纯数据 JSON（飞书 schema 2.0），构造函数不做 IO；
按钮 value 只允许 action + token，完整参数只保存在服务端。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import cards, lark_client
from data_intelligence_hub.agents.shusuo.intents import Proposal
from data_intelligence_hub.agents.shusuo.proposal_store import (
    ProposalLookup,
    replace_pending,
)
from data_intelligence_hub.agents.shusuo.proposal_store import (
    clear_all as clear_proposal_store,
)


def _proposal(**overrides: Any) -> Proposal:
    values: dict[str, Any] = {
        "endpoint_type": "tikhub_reddit_search",
        "params": {"keyword": "AI", "max_items": 10},
        "title": "Reddit 关键词搜索：AI",
        "note": "",
        "estimated_items": 10,
        "cost_notice": "费用未知，按上游实际计费",
    }
    values.update(overrides)
    return Proposal(**values)


def _pending(proposal: Proposal):
    clear_proposal_store()
    return replace_pending("chat-c", "ou-c", proposal)


def _preflight(**overrides: Any):
    values: dict[str, Any] = {
        "allowed": True,
        "availability": "verified",
        "normalized_params": {"keyword": "AI", "max_items": 10},
        "errors": (),
        "warnings": ("费用未知，按上游实际计费。",),
        "cost_notice": "费用未知，按上游实际计费",
    }
    values.update(overrides)
    return shusuo_capabilities.PreflightResult(**values)


def _outcome(**overrides: Any):
    values: dict[str, Any] = {
        "ok": True,
        "text": "",
        "endpoint_type": "tikhub_reddit_search",
        "task_run_id": "run-cards-1",
        "records_count": 10,
        "duration_ms": 1234,
        "total_cost_usd": None,
        "records": (),
        "error_message": None,
    }
    values.update(overrides)
    return shusuo_capabilities.CollectOutcome(**values)


def _card_text(card: dict[str, Any]) -> str:
    """把卡片正文压成一个文本串，便于断言字段出现。"""
    parts: list[str] = []
    header = card.get("header") or {}
    title = header.get("title")
    if isinstance(title, dict):
        parts.append(str(title.get("content", "")))
    body = card.get("body") or {}
    for element in body.get("elements", []):
        content = element.get("content")
        if isinstance(content, str):
            parts.append(content)
        text = element.get("text")
        if isinstance(text, dict):
            parts.append(str(text.get("content", "")))
    return "\n".join(parts)


def _buttons(card: dict[str, Any]) -> list[dict[str, Any]]:
    """从卡片正文里取全部按钮（2.0：按钮直接放 elements，用 behaviors 回调）。"""
    body = card.get("body") or {}
    return [el for el in body.get("elements", []) if el.get("tag") == "button"]


def _action_values(card: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for button in _buttons(card):
        for behavior in button.get("behaviors", []):
            value = behavior.get("value")
            if isinstance(value, dict):
                values.append(value)
    return values


# ---------- proposal_card ----------


def test_proposal_card_has_confirm_cancel_and_no_params() -> None:
    pending = _pending(_proposal())
    preflight = _preflight()
    card = cards.proposal_card(pending, preflight)
    values = _action_values(card)
    assert values == [
        {"action": "confirm", "token": pending.token},
        {"action": "cancel", "token": pending.token},
    ]
    serialized = json.dumps(card, ensure_ascii=False)
    assert "费用未知，按上游实际计费" in serialized
    assert json.dumps(pending.proposal.params, ensure_ascii=False) not in serialized


def test_proposal_card_is_schema_2_with_expected_fields() -> None:
    pending = _pending(_proposal())
    card = cards.proposal_card(pending, _preflight())
    assert card["schema"] == "2.0"
    text = _card_text(card)
    assert "Reddit 关键词搜索：AI" in text
    assert "tikhub_reddit_search" in text
    assert "keyword=AI" in text
    assert "max_items=10" in text
    assert "预计记录数：10" in text
    assert "费用未知，按上游实际计费" in text
    assert pending.token in text


def test_proposal_card_summary_uses_normalized_params_and_hides_secret() -> None:
    pending = _pending(
        _proposal(params={"query": "AI", "api_key": "sk-live-888"})
    )
    card = cards.proposal_card(
        pending,
        _preflight(
            normalized_params={"query": "AI", "api_key": "sk-live-888"},
        ),
    )
    serialized = json.dumps(card, ensure_ascii=False)
    assert "sk-live-888" not in serialized
    assert "[redacted]" in serialized
    assert "query=AI" in serialized


def test_proposal_card_marks_unknown_cost_warning() -> None:
    pending = _pending(_proposal())
    card = cards.proposal_card(pending, _preflight())
    assert "⚠️ 费用未知" in _card_text(card)


def test_proposal_card_shows_known_cost_without_warning_mark() -> None:
    pending = _pending(_proposal())
    card = cards.proposal_card(
        pending, _preflight(cost_notice="费用约 $0.01/条", warnings=())
    )
    text = _card_text(card)
    assert "费用约 $0.01/条" in text
    assert "⚠️ 费用未知" not in text


def test_proposal_card_shows_expiry_and_confirmation_hint() -> None:
    pending = _pending(_proposal())
    card = cards.proposal_card(pending, _preflight())
    text = _card_text(card)
    assert "确认" in text
    assert "取消" in text
    ttl_minutes = int(pending.expires_at - pending.created_at) // 60
    assert f"{ttl_minutes} 分钟内有效" in text


# ---------- processing / success / failure / cancelled / expired ----------


def test_processing_card_has_no_buttons_and_states_running() -> None:
    pending = _pending(_proposal())
    card = cards.processing_card(pending)
    assert _buttons(card) == []
    assert card["schema"] == "2.0"
    text = _card_text(card)
    assert "正在采集" in text
    assert "Reddit 关键词搜索：AI" in text


def test_card_titles_redact_secret_from_proposal_title() -> None:
    """标题类卡片：proposal.title 里的密钥片段必须先脱敏再进卡（含 header.title）。"""
    proposal = _proposal(title="搜 api_key=sk-live-999 的新品")
    secret = "sk-live-999"
    card = cards.proposal_card(_pending(proposal), _preflight())
    serialized = json.dumps(card, ensure_ascii=False)
    assert secret not in serialized
    assert "[redacted]" in serialized
    header_title = card["header"]["title"]["content"]
    assert secret not in header_title
    for card in (
        cards.processing_card(_pending(proposal)),
        cards.cancelled_card(_pending(proposal)),
    ):
        serialized = json.dumps(card, ensure_ascii=False)
        assert secret not in serialized
        assert "[redacted]" in serialized
    # success/failure 卡不渲染 proposal.title，密钥同样不得出现
    for card in (
        cards.success_card(_pending(proposal), _outcome()),
        cards.failure_card(_pending(proposal), "x"),
    ):
        assert secret not in json.dumps(card, ensure_ascii=False)


def test_success_card_shows_records_and_run_link() -> None:
    pending = _pending(_proposal())
    outcome = _outcome(
        records=({"content": {"title": "row 1", "url": "https://example.com/1"}},),
    )
    card = cards.success_card(pending, outcome)
    text = _card_text(card)
    assert "采集完成" in text
    assert "tikhub_reddit_search" in text
    assert "记录数：10" in text
    assert "1.2 秒" in text
    assert "row 1" in text
    assert "/runs/run-cards-1" in text
    assert _buttons(card) == []


def test_success_card_omits_cost_line_when_unknown_total() -> None:
    pending = _pending(_proposal())
    card = cards.success_card(pending, _outcome(total_cost_usd=None))
    assert "费用" not in _card_text(card)


def test_success_card_keeps_secret_out_of_previews() -> None:
    pending = _pending(_proposal())
    outcome = _outcome(
        records=({"content": {"title": "token=leaky-secret"}},),
    )
    serialized = json.dumps(cards.success_card(pending, outcome), ensure_ascii=False)
    assert "leaky-secret" not in serialized


def test_failure_card_shows_message_without_buttons() -> None:
    pending = _pending(_proposal())
    card = cards.failure_card(pending, "原因：token=abc 已脱敏")
    text = _card_text(card)
    assert "采集未返回数据" in text
    assert "已脱敏" in text
    assert _buttons(card) == []


def test_failure_card_fit_text_caps_and_redacts() -> None:
    pending = _pending(_proposal())
    card = cards.failure_card(pending, "x" * 7000 + " token=leaky")
    text = _card_text(card)
    assert "leaky" not in text
    # 失败原因截断提示在正文里，正文总长不超过 6000 + 结构开销。
    assert len(text) <= 6200


def test_cancelled_and_expired_cards_state_their_status() -> None:
    pending = _pending(_proposal())
    cancelled = cards.cancelled_card(pending)
    expired = cards.expired_card()
    assert "已取消" in _card_text(cancelled)
    assert "已过期" in _card_text(expired)
    assert _buttons(cancelled) == []
    assert _buttons(expired) == []
    assert cancelled["schema"] == "2.0"
    assert expired["schema"] == "2.0"


# ---------- reply_card ----------


@pytest.mark.asyncio
async def test_reply_card_posts_interactive_reply(monkeypatch) -> None:
    request = AsyncMock(return_value={"message_id": "card-message"})
    monkeypatch.setattr(lark_client, "_request", request)
    message_id = await lark_client.reply_card("source-message", {"schema": "2.0"})
    assert message_id == "card-message"
    request.assert_awaited_once()
    method, path = request.await_args.args
    assert method == "POST"
    assert path == "/im/v1/messages/source-message/reply"
    payload = request.await_args.kwargs["payload"]
    assert payload["msg_type"] == "interactive"
    assert json.loads(payload["content"]) == {"schema": "2.0"}


def test_expired_card_uses_pending_status_copy() -> None:
    """过期卡与 pending_status_text(EXPIRED) 的文案保持一致口径。"""
    from data_intelligence_hub.agents.shusuo import replies

    assert "已过期" in replies.pending_status_text(ProposalLookup.EXPIRED)
    assert "已过期" in _card_text(cards.expired_card())


def test_card_text_never_exceeds_feishu_card_budget() -> None:
    pending = _pending(
        _proposal(title="长" * 300, note="备注" * 300, params={"keyword": "词" * 300})
    )
    card = cards.proposal_card(
        pending,
        _preflight(normalized_params={"keyword": "词" * 300}),
    )
    assert len(json.dumps(card, ensure_ascii=False)) <= 6000


def test_card_titles_and_notes_are_redacted_before_build() -> None:
    """Task 5 遗留：标题/说明等动态文本进入卡片前必须脱敏。

    意图层标题来自用户输入（例如「搜 token=leaky-key」），卡片构造函数
    不能假设上游已脱敏——动态文本必须在卡片边界再过一次 redact。
    """
    secret = "token=leaky-key"
    pending_with_secret = _pending(
        _proposal(title=f"关键词搜索：{secret}", note=f"备注 {secret}")
    )
    outcome_secret = _outcome(
        records=({"content": {"title": f"标题 {secret}"}},),
    )
    serialized = json.dumps(
        [
            cards.proposal_card(pending_with_secret, _preflight()),
            cards.processing_card(pending_with_secret),
            cards.cancelled_card(pending_with_secret),
            cards.failure_card(pending_with_secret, f"原因：{secret}"),
            cards.success_card(pending_with_secret, outcome_secret),
        ],
        ensure_ascii=False,
    )
    assert "leaky-key" not in serialized
