"""结构化脱敏：dict/list 里的密钥必须按结构抹掉，不能只靠文本正则。

`采集 <端点> key=value` 允许传 JSON，`parse_params` 会把 `{"token": "..."}`
解析成嵌套 dict。文本正则在 `- key={'token': 'abc'}` 这种 repr 形态上
不一定命中，卡片一旦渲染就泄漏。本文件锁定结构脱敏。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import cards, commands, replies
from data_intelligence_hub.agents.shusuo.intents import Proposal
from data_intelligence_hub.agents.shusuo.proposal_store import (
    clear_all as clear_proposal_store,
)
from data_intelligence_hub.agents.shusuo.proposal_store import replace_pending

SECRETS = (
    "leakvalue-one",
    "leaktoken-alpha",
    "leaktoken-bravo",
    "leaktoken-charlie",
    "leakvalue-five",
    "leakvalue-six",
)


def _preflight(params: dict[str, Any]):
    return shusuo_capabilities.PreflightResult(
        allowed=True,
        availability="verified",
        normalized_params=params,
        errors=(),
        warnings=("费用未知，按上游实际计费。",),
        cost_notice="费用未知，按上游实际计费",
    )


def _pending(params: dict[str, Any]):
    clear_proposal_store()
    return replace_pending(
        "chat-s",
        "ou-s",
        Proposal(
            endpoint_type="demo_endpoint",
            params=params,
            title="结构化脱敏",
            estimated_items=10,
        ),
    )


NESTED_PARAMS: dict[str, Any] = {
    "query": "AI",
    "headers": [
        {"name": "Authorization", "value": "Bearer leakvalue-one"},
        {"token": "leaktoken-alpha"},
    ],
    "auth": {
        "api_key": "leaktoken-bravo",
        "nested": {"password": "leaktoken-charlie", "region": "us"},
    },
    "extra": [{"cookie": "session=leakvalue-five"}],
    "session": {"id": "leakvalue-six"},
}


def _assert_no_secrets(serialized: str) -> None:
    for secret in SECRETS:
        assert secret not in serialized, f"密钥泄漏: {secret}"


def test_parse_params_produces_nested_structure() -> None:
    """前提：显式采集能把 JSON 传成嵌套 dict（脱敏必须面对它）。"""
    params = commands.parse_params(
        ['headers=[{"token": "leaktoken-alpha"}]', 'auth={"api_key": "leaktoken-bravo"}']
    )
    assert isinstance(params["headers"], list)
    assert isinstance(params["auth"], dict)
    assert params["auth"]["api_key"] == "leaktoken-bravo"


def test_redact_structure_removes_nested_secret_values() -> None:
    redacted = replies.redact_structure(NESTED_PARAMS)
    _assert_no_secrets(json.dumps(redacted, ensure_ascii=False))
    # 非敏感字段必须保留：脱敏不能把整棵结构清空。
    assert redacted["query"] == "AI"
    assert redacted["auth"]["nested"]["region"] == "us"


def test_redact_structure_does_not_mutate_input() -> None:
    before = json.dumps(NESTED_PARAMS, ensure_ascii=False)
    replies.redact_structure(NESTED_PARAMS)
    assert json.dumps(NESTED_PARAMS, ensure_ascii=False) == before


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "secret",
        "password",
        "passwd",
        "cookie",
        "api_key",
        "apikey",
        "access_key",
        "access_token",
        "credential",
        "private_key",
        "session",
        "authorization",
        "Authorization",
        "API_KEY",
        "AccessToken",
    ],
)
def test_redact_structure_matches_secret_key_variants(key: str) -> None:
    redacted = replies.redact_structure({key: "leakvalue-key"})
    assert redacted == {key: replies.REDACTED}


def test_redact_structure_covers_json_rendered_text() -> None:
    """JSON 形态也要脱敏：`{"api_key": "..."}` 的键后带引号。"""
    rendered = json.dumps({"error": {"api_key": "leakvalue-json"}}, ensure_ascii=False)
    assert "leakvalue-json" not in replies.structured_text({"error": {"api_key": "leakvalue-json"}})
    assert "leakvalue-json" not in replies.fit_text(rendered)


def test_proposal_card_hides_nested_secrets() -> None:
    pending = _pending(NESTED_PARAMS)
    card = cards.proposal_card(pending, _preflight(NESTED_PARAMS))
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))


def test_proposal_text_hides_nested_secrets() -> None:
    pending = _pending(NESTED_PARAMS)
    text = replies.proposal_text(pending, _preflight(NESTED_PARAMS))
    _assert_no_secrets(text)


def test_confirm_preflight_error_card_hides_nested_secrets() -> None:
    pending = _pending(NESTED_PARAMS)
    result = shusuo_capabilities.PreflightResult(
        allowed=False,
        availability="verified",
        normalized_params=NESTED_PARAMS,
        errors=("未知参数：headers",),
        warnings=(),
        cost_notice="费用未知，按上游实际计费",
    )
    card = cards.retryable_preflight_card(pending, result)
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))


def test_failure_card_hides_nested_secret_in_message() -> None:
    pending = _pending({"query": "AI"})
    message = json.dumps({"error": {"api_key": "leaktoken-bravo"}}, ensure_ascii=False)
    card = cards.failure_card(pending, message)
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))


def test_record_preview_hides_nested_secrets() -> None:
    """记录预览：content 是嵌套 dict/list 时也要结构脱敏。"""
    pending = _pending({"query": "AI"})
    outcome = shusuo_capabilities.CollectOutcome(
        ok=True,
        text="采集完成",
        endpoint_type="demo_endpoint",
        task_run_id="run-nested",
        records_count=2,
        records=(
            {
                "id": 1,
                "content": {
                    "headers": {"authorization": "Bearer leakvalue-one"},
                    "auth": [{"api_key": "leaktoken-bravo"}],
                },
            },
            {
                "id": 2,
                "content": {"token": "leaktoken-alpha", "password": "leaktoken-charlie"},
            },
        ),
    )
    card = cards.success_card(pending, outcome)
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))
    _assert_no_secrets(replies.collect_success_text(outcome))


def test_record_preview_keeps_human_title() -> None:
    pending = _pending({"query": "AI"})
    outcome = shusuo_capabilities.CollectOutcome(
        ok=True,
        text="",
        endpoint_type="demo_endpoint",
        task_run_id="run-title",
        records_count=1,
        records=(
            {
                "id": 1,
                "content": {"title": "正常标题", "token": "leaktoken-alpha"},
            },
        ),
    )
    serialized = json.dumps(cards.success_card(pending, outcome), ensure_ascii=False)
    assert "正常标题" in serialized
    assert "leaktoken-alpha" not in serialized


def test_record_preview_does_not_render_python_repr_for_dict_content() -> None:
    """content 是 dict/None 时用脱敏后的 JSON，不能是 Python repr（单引号/None）。"""
    preview_dict = replies._record_preview({"content": {"a": 1, "b": 2}})
    assert preview_dict is not None
    assert preview_dict.title == '{"a": 1, "b": 2}'
    assert "'" not in preview_dict.title
    preview_none = replies._record_preview({"content": None})
    assert preview_none is None


def test_nested_structure_in_title_and_note_is_redacted() -> None:
    clear_proposal_store()
    pending = replace_pending(
        "chat-s",
        "ou-s",
        Proposal(
            endpoint_type="demo_endpoint",
            params={"query": "AI"},
            title='搜索 {"api_key": "leaktoken-bravo"}',
            note='说明 {"token": "leaktoken-alpha"}',
            estimated_items=10,
        ),
    )
    card = cards.proposal_card(pending, _preflight({"query": "AI"}))
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))
