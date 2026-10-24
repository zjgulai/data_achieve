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


# ---------------------------------------------------------------------------
# 复合键名：client_secret / refresh_token / id_token / user_session / jwt …
# ---------------------------------------------------------------------------

# 复合形态的密钥键（常见于 OAuth / 快手 / 小红书等上游的凭据字段）。
COMPOUND_SECRET_KEYS = (
    "client_secret",
    "refresh_token",
    "auth_token",
    "id_token",
    "api_secret",
    "secret_key",
    "user_session",
    "bearer",
    "jwt",
    "clientSecret",
    "refreshToken",
    "X-Api-Secret",
)

# 形似「key/token」但不是凭据的键：脱敏不能把它们也抹掉。
NON_SECRET_KEYS = ("monkey", "hockey", "keyboard", "keynote", "sort_order")


@pytest.mark.parametrize("key", COMPOUND_SECRET_KEYS)
def test_compound_secret_key_is_redacted(key: str) -> None:
    redacted = replies.redact_structure({key: "leakvalue-compound"})
    assert redacted == {key: replies.REDACTED}


@pytest.mark.parametrize("key", NON_SECRET_KEYS)
def test_non_secret_key_survives_redaction(key: str) -> None:
    """`monkey` / `hockey` / `keyboard` / `keynote` 不是凭据，值必须留下来。"""
    redacted = replies.redact_structure({key: "ordinary-value"})
    assert redacted == {key: "ordinary-value"}


def _compound_params() -> dict[str, Any]:
    return {
        "query": "AI",
        "oauth": {
            "client_secret": "leakvalue-compound",
            "refresh_token": "leakvalue-compound",
            "client_id": "public-client-id",
        },
        "cookies": [{"user_session": "leakvalue-compound"}, {"monkey": "apples"}],
        "signed": {
            "jwt": "leakvalue-compound",
            "bearer": "leakvalue-compound",
            "payload": {"note": "ok"},
        },
        "headers": [{"X-Api-Secret": "leakvalue-compound", "X-Trace-Id": "t-1"}],
    }


def test_compound_secrets_are_redacted_in_nested_json() -> None:
    redacted = replies.redact_structure(_compound_params())
    rendered = json.dumps(redacted, ensure_ascii=False)
    assert "leakvalue-compound" not in rendered
    # 非凭据字段一个都不能丢：脱敏不等于清空。
    assert redacted["oauth"]["client_id"] == "public-client-id"
    assert redacted["cookies"][1]["monkey"] == "apples"
    assert redacted["signed"]["payload"]["note"] == "ok"
    assert redacted["headers"][0]["X-Trace-Id"] == "t-1"


def test_compound_secrets_are_absent_from_proposal_text() -> None:
    params = _compound_params()
    pending = _pending(params)
    text = replies.proposal_text(pending, _preflight(params))
    assert "leakvalue-compound" not in text
    assert "public-client-id" in text


def test_compound_secrets_are_absent_from_card_json() -> None:
    params = _compound_params()
    pending = _pending(params)
    card = cards.proposal_card(pending, _preflight(params))
    _assert_no_secrets(json.dumps(card, ensure_ascii=False))
    assert "leakvalue-compound" not in json.dumps(card, ensure_ascii=False)
    assert "public-client-id" in json.dumps(card, ensure_ascii=False)


@pytest.mark.parametrize(
    "line",
    [
        "client_secret=leakvalue-compound",
        "refresh_token: leakvalue-compound",
        "auth_token=leakvalue-compound",
        "id_token=leakvalue-compound",
        "api_secret=leakvalue-compound",
        "secret_key=leakvalue-compound",
        "user_session=leakvalue-compound",
        "jwt=leakvalue-compound",
        '"client_secret": "leakvalue-compound"',
    ],
)
def test_compound_secret_kv_lines_are_redacted_in_text(line: str) -> None:
    """文本形态（非结构化）也要认复合键名，值不能留下来。"""
    assert "leakvalue-compound" not in replies.fit_text(f"错误详情：{line}")


@pytest.mark.parametrize(
    "line",
    [
        "monkey=apples",
        "hockey=sticks",
        "keyboard=qwerty",
        "keynote=slides",
    ],
)
def test_non_secret_kv_lines_are_not_redacted_in_text(line: str) -> None:
    rendered = replies.fit_text(f"错误详情：{line}")
    assert "leakvalue-compound" not in rendered
    assert line.split("=")[1] in rendered


# ---------------------------------------------------------------------------
# 反向误报：分页游标不是凭据，URL 里的密钥不能被前一个非密钥键吞掉
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["page_token", "pagination_token", "next_page_token"])
def test_pagination_token_keys_are_not_redacted(key: str) -> None:
    """分页游标是功能参数：整值抹掉会让复核者看不出请求分到了哪一页。"""
    redacted = replies.redact_structure({key: "cursor-abc"})
    assert redacted == {key: "cursor-abc"}


@pytest.mark.parametrize(
    "key",
    ["max_age_hours", "snapshot_as_of", "start_published_date", "sortOrder"],
)
def test_ordinary_catalog_keys_are_not_redacted(key: str) -> None:
    redacted = replies.redact_structure({key: "2026-01-01"})
    assert redacted == {key: "2026-01-01"}


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1/x?token=leakvalue-compound&page=2",
        "https://api.example.com/v1/x?api_key=leakvalue-compound",
        "https://api.example.com/v1/x?a=1&refresh_token=leakvalue-compound",
    ],
)
def test_secret_in_url_query_is_redacted(url: str) -> None:
    """URL 里的密钥必须抹掉：前一个非密钥键不能把后面的 `&token=` 整段吞掉。"""
    assert "leakvalue-compound" not in replies.fit_text(url)


def test_secret_in_url_keeps_non_secret_query_params() -> None:
    url = "https://api.example.com/v1/x?region=us&page=2&token=leakvalue-compound&page=2"
    rendered = replies.fit_text(url)
    assert "region=us" in rendered
    assert "page=2" in rendered
    assert "SECRET_5x26hodm" not in rendered

