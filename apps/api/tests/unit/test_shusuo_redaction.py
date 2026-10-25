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


# ---------------------------------------------------------------------------
# 压缩 JSON：外层非密钥键不能把内层密钥整段吞成「值」
# ---------------------------------------------------------------------------

# 上游返回的 minified JSON 常整个塞进 error_message / 说明文本。
# 花括号分支若匹配任意单层 JSON，`{"error": {...}}` 会被外层键当成值吞掉，
# 内层的 api_key / password / token 就再也不会被单独匹配到。
MINIFIED_SECRETS = (
    '{"error":{"api_key":"sekr1t"}}',
    '{"a":{"password":"sekr1t"}}',
    'data={"token":"sekr1t"}',
    '{"error": "token=sekr1t"}',
    '{"error":"refresh_token=sekr1t"}',
    '{"outer":{"inner":{"client_secret":"sekr1t"}}}',
)


@pytest.mark.parametrize("payload", MINIFIED_SECRETS)
def test_minified_json_secrets_are_redacted_in_text(payload: str) -> None:
    assert "sekr1t" not in replies.fit_text(payload)


@pytest.mark.parametrize("payload", MINIFIED_SECRETS)
def test_minified_json_secrets_are_redacted_in_failure_card(payload: str) -> None:
    """失败卡是错误文本的真实落点：上游 JSON 原样进卡片也必须脱敏。"""
    pending = _pending({"query": "AI"})
    card = cards.failure_card(pending, payload)
    assert "sekr1t" not in json.dumps(card, ensure_ascii=False)


def test_minified_json_keeps_non_secret_payload() -> None:
    """脱敏不等于清空：非密钥字段仍要能看清。"""
    rendered = replies.fit_text('{"error":{"api_key":"sekr1t","region":"us"}}')
    assert "sekr1t" not in rendered
    assert "region" in rendered
    assert "us" in rendered


def test_minified_json_stays_valid_json_after_redaction() -> None:
    """抹掉的是值不是结构：脱敏后必须仍是可解析 JSON，引号不能被吃掉。"""
    rendered = replies.fit_text('{"error":{"api_key":"sekr1t","region":"us"}}')
    parsed = json.loads(rendered)
    assert parsed == {"error": {"api_key": replies.REDACTED, "region": "us"}}


@pytest.mark.parametrize(
    "payload",
    ["token={{SECRET_A}}", "api_key={{SECRET_B}}", "看这里 token={{SECRET_C}} 结束"],
)
def test_template_placeholder_still_redacted_after_brace_narrowing(payload: str) -> None:
    """收窄花括号分支后，`{{...}}` 模板值的脱敏必须原样保留。"""
    rendered = replies.fit_text(payload)
    assert "SECRET_" not in rendered
    assert replies.REDACTED in rendered


def test_structural_redaction_unchanged_for_minified_json() -> None:
    """结构路径不依赖正则：minified JSON 解析成 dict 后整键抹掉。"""
    redacted = replies.redact_structure({"error": {"api_key": "sekr1t", "region": "us"}})
    assert redacted == {"error": {"api_key": replies.REDACTED, "region": "us"}}


def test_redact_stays_linear_on_long_token_free_text() -> None:
    """用户文本可以很长：键名匹配不能在每个起点回退整段，否则 O(n²)。

    8000 字符的裸字母串在旧写法下要约 0.66 秒，20 万字符就会卡住请求线程。
    """
    import time

    payload = "x" * 200_000
    started = time.perf_counter()
    replies.fit_text(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"200k 字符脱敏耗时 {elapsed:.2f}s，键名正则出现回溯"


def test_redact_stays_linear_on_many_kv_pairs() -> None:
    import time

    payload = " ".join(f"k{i}=v{i}" for i in range(20_000))
    started = time.perf_counter()
    replies.fit_text(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, f"2 万组 key=value 脱敏耗时 {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# 安全补丁：单花括号值 / 超长值 / 超长键 / 分隔符洪泛
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "token={S3cr3tVal}",
        "password={hunter2}",
        "api_key={abc123}",
        "client_secret={S3cr3tVal}",
        '{"error": "token={S3cr3tVal}"}',
    ],
)
def test_single_brace_values_are_redacted(payload: str) -> None:
    """单花括号值是上游真实形态（`token={...}`），不能因为收窄模板分支而漏掉。"""
    assert "S3cr3tVal" not in replies.fit_text(payload)
    assert "hunter2" not in replies.fit_text(payload)
    assert "abc123" not in replies.fit_text(payload)


@pytest.mark.parametrize(
    "payload", ["token={{SECRET_A}}", "api_key={{SECRET_B}}", "x token={{SECRET_C}} y"]
)
def test_double_brace_templates_still_redacted(payload: str) -> None:
    """恢复单花括号的同时，双花括号模板必须仍然整值抹掉。"""
    rendered = replies.fit_text(payload)
    assert "SECRET_" not in rendered
    assert replies.REDACTED in rendered


@pytest.mark.parametrize("size", [5000, 20_000])
def test_long_bare_secret_value_is_fully_redacted(size: int) -> None:
    """超长值必须整体抹掉：只抹前 4096 字符会把尾部明文留在回复里。"""
    value = "A" * size
    out = replies._redact(f"token={value}")
    assert out == f"token={replies.REDACTED}"
    assert "A" not in out
    assert "A" not in replies.fit_text(f"token={value}")


def test_long_jwt_like_value_is_fully_redacted() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9." + "x" * 5000 + ".sig"
    out = replies._redact(f"token={jwt}")
    assert "x" * 100 not in out
    assert "eyJhbGciOiJIUzI1NiJ9" not in out


def test_long_bare_secret_absent_from_failure_card() -> None:
    pending = _pending({"query": "AI"})
    secret = "A" * 5000
    card = cards.failure_card(pending, f"upstream rejected: token={secret}")
    serialized = json.dumps(card, ensure_ascii=False)
    assert "A" * 100 not in serialized


@pytest.mark.parametrize(
    "key",
    [
        "s" * 70 + "_token",
        "s" * 70 + "_secret",
        "a" * 200 + "_password",
        "client_" + "a" * 100 + "_secret",
    ],
)
def test_over_bound_secret_key_still_redacts_its_value(key: str) -> None:
    """键名超过 64 字符时不能退化成"没有键"：旧正则干脆整条匹配不上。

    键名带凭据后缀且有分隔边界，就仍是凭据键，值必须抹。
    """
    assert replies._is_secret_key(key) is True
    out = replies._redact(f"{key}=S3cr3tVal")
    assert "S3cr3tVal" not in out


@pytest.mark.parametrize(
    "key",
    [
        "a" * 80 + "_api_key",
        "x" * 100 + "_access_token",
        "c" * 70 + "_client_secret",
    ],
)
def test_over_bound_quoted_json_key_still_redacts(key: str) -> None:
    """压缩 JSON 里的超长键：旧正则因键名截断根本匹配不到，值原样输出。"""
    payload = '{"' + key + '":"S3cr3tVal","region":"us"}'
    out = replies._redact(payload)
    assert "S3cr3tVal" not in out
    assert '"region":"us"' in out


@pytest.mark.parametrize("key", ["s" * 70 + "token", "a" * 200 + "password"])
def test_no_boundary_long_key_is_not_treated_as_secret(key: str) -> None:
    """没有分隔边界的长键仍按普通键处理（与 `monkey` 同一策略），不是漏抹。"""
    assert replies._is_secret_key(key) is False
    assert replies._redact(f"{key}=S3cr3tVal") == f"{key}=S3cr3tVal"


@pytest.mark.parametrize("length", [1000, 4000, 10_000])
def test_separator_flood_does_not_recurse(length: int) -> None:
    """分隔符洪泛不能走进 Python 递归：~500 个分隔符就会 RecursionError。"""
    payload = "note" + "=" * length + "x"
    out = replies._redact(payload)
    assert isinstance(out, str)


def test_mixed_separator_flood_does_not_recurse() -> None:
    """`a=a=a=...` 形态每层都留一个分隔符，旧写法必然打爆递归栈。"""
    out = replies._redact(("a" + "=") * 600)
    assert isinstance(out, str)


def test_one_megabyte_flood_is_handled_quickly() -> None:
    import time

    payload = ("a=" * 500_000)[:1_000_000]
    started = time.perf_counter()
    replies._redact(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"1MB 分隔符洪泛耗时 {elapsed:.2f}s"


def test_deep_colon_nesting_does_not_recurse() -> None:
    """深度 1000 的 `{"a":` 嵌套：旧写法按分隔符递归，必然炸栈。"""
    payload = '{"a":' * 1000 + '"token=S3cr3tVal"'
    out = replies._redact(payload)
    assert "SECRET_t2xyzx5r" not in out
    assert replies.REDACTED in out


def test_single_brace_template_inside_deep_nesting() -> None:
    payload = '{"a":' * 200 + "{'token': {S3cr3tVal}}" + "}" * 200
    assert "S3cr3tVal" not in replies._redact(payload)


def test_null_byte_payload_still_redacts():
    payload = "token=\x00S3cr3tVal\x00"
    out = replies._redact(payload)
    assert "S3cr3tVal" not in out


# ---------------------------------------------------------------------------
# Unicode 空白：只在「空白之后确实开始下一个密钥键值对」时终止裸值
# ---------------------------------------------------------------------------
#
# 空白既可能是值的**分界线**（`token=abc password: hunter2`），也可能是值的
# **内部字符**（`password: hunter<NBSP>2tail`、中文短语、PEM 正文）。
# 见到空白一律终止会留下尾部明文；一律不终止会把后面的密钥整段吞掉。
#
# 判据只有一条：空白之后是否开始下一个**密钥**键值对。键名解析、分隔符扫描
# 与密钥判定（含复合后缀、驼峰）全部复用主扫描器那一套，不另立规则。
# 只认密钥键、不认任意键是刻意的：PEM 正文里的 base64 填充行
# （`Q2x5ZDEyMzQ1Njc4OTA=`）与 `Proc-Type:` 都长得像普通键值对，放宽成
# "任意键 + 分隔符"会把私钥尾部整段留在回复里。代价是非密钥键（`note=ok`）
# 会被一起抹掉——宁可多抹，不留明文。

# 程序化枚举 `str.isspace()` 为真的全部码位（CPython 3.12 是 29 个）。
# 不用字面量：NBSP / U+3000 / U+202F 在编辑器与终端里和普通空格长得一样，
# 手写的字面量一旦被归一化，测试就会在"看起来相同、实际不同"的输入上空转。
UNICODE_SPACE_CODEPOINTS: tuple[int, ...] = tuple(
    codepoint for codepoint in range(0x110000) if chr(codepoint).isspace()
)
UNICODE_SPACES: tuple[str, ...] = tuple(chr(cp) for cp in UNICODE_SPACE_CODEPOINTS)
SPACE_IDS: list[str] = [f"U+{cp:04X}" for cp in UNICODE_SPACE_CODEPOINTS]

# 行分隔类空白：PEM 正文与多行日志用它分行。
LINE_BREAK_CODEPOINTS: tuple[int, ...] = (0x0A, 0x0B, 0x0C, 0x0D, 0x85, 0x2028, 0x2029)
LINE_BREAKS: tuple[str, ...] = tuple(chr(cp) for cp in LINE_BREAK_CODEPOINTS)
LINE_BREAK_IDS: list[str] = [f"U+{cp:04X}" for cp in LINE_BREAK_CODEPOINTS]

ASCII_SPACE = chr(0x20)
NBSP = chr(0x00A0)
IDEOGRAPHIC_SPACE = chr(0x3000)
LINE_SEPARATOR = chr(0x2028)
NEL = chr(0x0085)

PEM_BODY_LINES = (
    "MIIEowIBAAKCAQEA7bq8xyzS3cr3tq0p4fragment",
    "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ab",
    "Q2x5ZDEyMzQ1Njc4OTA=",
)
PEM_FRAGMENTS = (
    "MIIEow",
    "S3cr3tq0p4",
    "AbCdEfGh",
    "Q2x5ZDEy",
    "BEGIN",
    "END",
)

_FIVE_DASHES = "-" * 5
_PEM_LABEL = "RSA " + "PRIVATE KEY"
PEM_ARMOR_BEGIN = f"{_FIVE_DASHES}BEGIN {_PEM_LABEL}{_FIVE_DASHES}"
PEM_ARMOR_END = f"{_FIVE_DASHES}END {_PEM_LABEL}{_FIVE_DASHES}"


def _pem_block(separator: str) -> str:
    """未加密 PEM：头部 + 三行正文 + 尾部，行间用给定分隔符连接。

    头部与尾部由片段拼出，源码里不出现连续 PEM 标记；正文带一行 `=` 填充的
    base64（`Q2x5ZDEyMzQ1Njc4OTA=`），它的形状与 `key=value` 完全一样。
    """
    return separator.join((PEM_ARMOR_BEGIN, *PEM_BODY_LINES, PEM_ARMOR_END))


def _assert_no_pem_fragments(rendered: str) -> None:
    for fragment in PEM_FRAGMENTS:
        assert fragment not in rendered, f"私钥片段泄漏: {fragment}"


def test_unicode_space_table_is_generated_and_complete() -> None:
    """表必须是程序化枚举出来的，且覆盖全部 29 个 `str.isspace()` 码位。"""
    assert len(UNICODE_SPACES) == 29
    assert len(set(UNICODE_SPACES)) == 29
    assert all(space.isspace() for space in UNICODE_SPACES)
    # ASCII 的四个必须在表里。
    assert {"\t", "\n", "\r", ASCII_SPACE} <= set(UNICODE_SPACES)
    # 零宽字符不是 `isspace()`，不能混进来当空白。
    assert chr(0x200B) not in UNICODE_SPACES
    assert chr(0xFEFF) not in UNICODE_SPACES


def test_line_break_table_is_a_subset_of_unicode_spaces() -> None:
    """行分隔表必须是空白表的子集，并覆盖 PEM / 日志常用的换行。"""
    assert set(LINE_BREAKS) <= set(UNICODE_SPACES)
    assert {"\n", "\r", NEL, LINE_SEPARATOR, chr(0x2029)} <= set(LINE_BREAKS)


# --- 分界形态：空白后是 `password:`，值在此结束，两个密钥都抹 -------------


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_delimiter_unicode_space_redacts_both_values(space: str) -> None:
    """空白后面是 `password:`——确实是下一个密钥键值对，两个值都抹。"""
    out = replies.fit_text(f"token=abc{space}password: hunter2")
    assert out == f"token={replies.REDACTED}{space}password: {replies.REDACTED}"


@pytest.mark.parametrize(
    "key",
    ["password", "api_key", "access_token", "client_secret", "Authorization", "refreshToken"],
)
def test_delimiter_detection_reuses_secret_key_policy(key: str) -> None:
    """终止判定复用扫描器的密钥键策略：复合键、驼峰键都算。"""
    out = replies.fit_text(f"token=abc{NBSP}{key}=S3cr3tVal")
    assert "S3cr3tVal" not in out
    assert key in out


# --- 内部形态：空白属于值本身，整段抹掉，不留尾巴 -------------------------


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_unicode_space_keeps_secret_whole(space: str) -> None:
    """空白后面是 `2tail`——没有分隔符，不是键值对：整段抹掉。"""
    assert replies.fit_text(f"password: hunter{space}2tail") == (
        f"password: {replies.REDACTED}"
    )


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_unicode_space_in_cjk_secret(space: str) -> None:
    """中文值内部的空白（`我的<NBSP>密码`）：后面的汉字不是键，整值抹掉。"""
    assert replies.fit_text(f"password: 我的{space}密码") == f"password: {replies.REDACTED}"


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_access_token_fragment_after_unicode_space_is_redacted(space: str) -> None:
    """`access_token: abc123<WS>2tail789`：尾部片段不能留在回复里。"""
    assert replies.fit_text(f"access_token: abc123{space}2tail789") == (
        f"access_token: {replies.REDACTED}"
    )


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_several_whitespace_runs_inside_one_secret(space: str) -> None:
    """一个值里多处空白：每处都判一次，全都不终止才算同一个值。"""
    assert replies.fit_text(f"token=abc{space}def{space}ghi") == f"token={replies.REDACTED}"


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_equals_and_colons_are_not_pairs(space: str) -> None:
    """值里出现 `=` / `:` 但不构成键值对（`===def`）时仍属同一个值。"""
    assert replies.fit_text(f"token=abc{space}===def") == f"token={replies.REDACTED}"


@pytest.mark.parametrize("nonsecret", ["region", "page", "note", "monkey", "keyboard"])
def test_non_secret_pair_after_value_is_swallowed_with_the_value(nonsecret: str) -> None:
    """非密钥键不是终止点：它随同被抹，属于刻意的 fail-closed 取舍。

    不能因为 `region=us` 长得像键值对就把 `token=` 的值截短——一旦截短，
    后面真正的密钥（`<空白>api_key=...`）会落进上一条"值"里被整段吞掉，
    再也扫不到。宁可多抹一段可见文本，也不留明文。
    """
    out = replies.fit_text(f"token=abc{NBSP}{nonsecret}=ordinary")
    assert out == f"token={replies.REDACTED}"


# --- PEM：整个密钥块是一个值 ---------------------------------------------


@pytest.mark.parametrize("separator", LINE_BREAKS, ids=LINE_BREAK_IDS)
def test_private_key_armored_block_redacted_whole(separator: str) -> None:
    """PEM 的行分隔符在值内部：整块一次抹掉，头部、正文、尾部都不留。"""
    out = replies.fit_text(f"private_key: {_pem_block(separator)}")
    assert out == f"private_key: {replies.REDACTED}"


@pytest.mark.parametrize("separator", LINE_BREAKS, ids=LINE_BREAK_IDS)
def test_private_key_block_followed_by_another_secret(separator: str) -> None:
    """PEM 块之后还有密钥键值对：块内整抹，后面的密钥单独抹、键名保留。"""
    out = replies.fit_text(
        f"private_key={_pem_block(separator)}{separator}api_key=S3cr3tVal"
    )
    _assert_no_pem_fragments(out)
    assert "S3cr3tVal" not in out
    assert out == f"private_key={replies.REDACTED}{separator}api_key={replies.REDACTED}"


@pytest.mark.parametrize("separator", LINE_BREAKS, ids=LINE_BREAK_IDS)
def test_padded_base64_line_does_not_terminate_the_value(separator: str) -> None:
    """base64 填充行 `Q2x5ZDEyMzQ1Njc4OTA=` 形如 `key=value`，但不是密钥键。

    若把"任意键 + 分隔符"当终止点，私钥正文会从这一行起整段留在回复里。
    """
    padded_line = PEM_BODY_LINES[-1]
    assert padded_line.endswith("=")
    block = separator.join(
        (PEM_ARMOR_BEGIN, PEM_BODY_LINES[0], padded_line, PEM_ARMOR_END)
    )
    out = replies.fit_text(f"private_key: {block}")
    assert out == f"private_key: {replies.REDACTED}"


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_pem_metadata_lines_are_not_treated_as_next_pairs(space: str) -> None:
    """旧式 PEM 的 `Proc-Type:` / `DEK-Info:` 是值内容，不是下一个密钥参数。"""
    assert replies._starts_secret_pair(f"{space}Proc-Type: 4ENCRYPTED", 0) is False
    assert replies._starts_secret_pair(f"{space}DEK-Info: AES-256-CBC", 0) is False
    assert replies._starts_secret_pair(f"{space}MIIEowIBAA: x", 0) is False


def test_unterminated_armor_is_redacted_to_end_of_text() -> None:
    """头部在、尾部被日志截断：仍然整段抹掉（fail-closed）。"""
    payload = f"private_key: {PEM_ARMOR_BEGIN}\n" + "\n".join(PEM_BODY_LINES)
    assert replies.fit_text(payload) == f"private_key: {replies.REDACTED}"


def test_armored_value_inside_structured_payload() -> None:
    """卡片里的私钥参数：结构脱敏按父键整值抹掉，非敏感字段保留。"""
    rendered = replies.structured_text(
        {"private_key": _pem_block("\n"), "region": "us"}
    )
    _assert_no_pem_fragments(rendered)
    assert "region" in rendered
    assert "us" in rendered


# --- 白盒：终止点位置与谓词 -----------------------------------------------


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_scan_value_ends_before_a_secret_pair_only(space: str) -> None:
    """终止点是空白段起点（不是空白之后），且只在后面是密钥键值对时终止。"""
    # 内部空白：整段都算值。
    internal = f"hunter{space}2tail"
    assert replies._scan_value(internal, 0) == len(internal)

    # 后面是密钥键值对：在空白段起点结束，空白与键名都留给下一轮。
    next_pair = f"hunter{space}password: x"
    assert replies._scan_value(next_pair, 0) == len("hunter")

    # 后面是键名但没有分隔符：不是键值对，整段仍是值。
    no_separator = f"hunter{space}definitely"
    assert replies._scan_value(no_separator, 0) == len(no_separator)


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_starts_secret_pair_predicate(space: str) -> None:
    """谓词本身：密钥键 + 分隔符才算，其余都不算。"""
    assert replies._starts_secret_pair(f"{space}password: x", 0) is True
    assert replies._starts_secret_pair(f"{space}api_key=x", 0) is True
    assert replies._starts_secret_pair(f'{space}"client_secret": "x"', 0) is True
    assert replies._starts_secret_pair(f"{space}refreshToken=x", 0) is True
    assert replies._starts_secret_pair(f"{space}region: us", 0) is False
    assert replies._starts_secret_pair(f"{space}2tail", 0) is False
    assert replies._starts_secret_pair(space, 0) is False
    assert replies._starts_secret_pair(f"{space}密码: x", 0) is False
    # 非空白起点不是这个谓词的输入，必须判 False。
    assert replies._starts_secret_pair("password: x", 0) is False


# --- 用户可见路径 ---------------------------------------------------------


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_unicode_space_via_structured_text(space: str) -> None:
    """`structured_text` 是卡片与记录预览的共用渲染路径。"""
    assert replies.structured_text(f"password: hunter{space}2tail") == (
        f"password: {replies.REDACTED}"
    )


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_unicode_space_via_failure_card(space: str) -> None:
    """失败卡是错误文本的真实落点：内部空白的密钥尾部不能进卡片 JSON。"""
    pending = _pending({"query": "AI"})
    card = cards.failure_card(pending, f"upstream 400: password: hunter{space}2tail")
    serialized = json.dumps(card, ensure_ascii=False)
    assert "hunter" not in serialized
    assert "2tail" not in serialized
    assert "password" in serialized


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_delimiter_unicode_space_secrets_absent_from_failure_card(space: str) -> None:
    """分界形态在失败卡上仍要抹两个值、留键名。"""
    pending = _pending({"query": "AI"})
    card = cards.failure_card(pending, f"upstream 400: token=abc{space}password: hunter2")
    serialized = json.dumps(card, ensure_ascii=False)
    assert "hunter2" not in serialized
    assert "abc" not in serialized
    assert "password" in serialized


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_internal_unicode_space_via_record_preview(space: str) -> None:
    """记录预览的标题走 `_record_preview`，密钥尾部同样不能出现。"""
    preview = replies._record_preview(
        {"content": {"title": f"标题 password: hunter{space}2tail"}}
    )
    assert preview is not None
    assert "hunter" not in preview.title
    assert "2tail" not in preview.title


# --- 形状保持：花括号 / 引号 / 压缩 JSON / 超长输入 ------------------------


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_brace_values_survive_unicode_space_boundary_rule(space: str) -> None:
    """单花括号与双花括号模板走各自分支，不受裸值空白规则影响。"""
    payload = f"token={{S3cr3tVal}}{space}password={{{{SECRET_B}}}}{space}note=ok"
    out = replies.fit_text(payload)
    assert "S3cr3tVal" not in out
    assert "SECRET_B" not in out
    assert "note=ok" in out


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_quoted_value_with_internal_unicode_space(space: str) -> None:
    """引号值按闭合引号定位：内部空白不影响，脱敏后仍是合法 JSON。"""
    payload = f'{{"error":{{"api_key":"sek{space}r1t"}}}}'
    out = replies.fit_text(payload)
    assert "sek" not in out
    assert "r1t" not in out
    assert json.loads(out) == {"error": {"api_key": replies.REDACTED}}


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_minified_json_guarded_by_unicode_space(space: str) -> None:
    """压缩 JSON 里的密钥在空白规则下仍要被取到。"""
    payload = f'{{"error":{{"token=sekr1t{space}password=sekr1t"}}}}'
    out = replies.fit_text(payload)
    assert "sekr1t" not in out


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_5k_value_with_internal_unicode_space_fully_redacted(space: str) -> None:
    """5k 值内部带空白：整值抹掉，不是"抹到空白为止"。"""
    value = "A" * 2500 + space + "B" * 2500
    assert replies._redact(f"token={value}") == f"token={replies.REDACTED}"
    assert replies.fit_text(f"token={value}") == f"token={replies.REDACTED}"


@pytest.mark.parametrize("space", UNICODE_SPACES, ids=SPACE_IDS)
def test_long_key_with_internal_unicode_space_value(space: str) -> None:
    """超长键与内部空白组合：键名与值都不限长，值必须整段抹掉。"""
    key = "s" * 70 + "_token"
    value = "x" * 2500 + space + "y" * 2500
    out = replies.fit_text(f"{key}={value}")
    assert "x" not in out
    assert "y" not in out
    assert out == f"{key}={replies.REDACTED}"


def test_ascii_separator_behaviour_unchanged() -> None:
    """ASCII 路径不能因为改边界判定而变：密钥键值对仍要被分开。"""
    for separator in (" ", "\t", "\n", "\r\n", "\x0b", "\x0c"):
        out = replies.fit_text(f"token=abc{separator}password: hunter2")
        assert out == f"token={replies.REDACTED}{separator}password: {replies.REDACTED}"


def test_5k_value_then_secret_pair_keeps_the_pair() -> None:
    """超长值之后紧跟密钥键值对：值整抹，后面的密钥单独抹，键名保留。"""
    payload = f"token={'A' * 5000}{NBSP}api_key={{S3cr3tVal}}"
    out = replies.fit_text(payload)
    assert "A" not in out
    assert "S3cr3tVal" not in out
    assert out == f"token={replies.REDACTED}{NBSP}api_key={replies.REDACTED}"


def test_non_secret_key_value_stays_visible() -> None:
    """非密钥键本身不消费值：`note=hello` 的普通词照旧可见。"""
    out = replies.fit_text(f"note=hello{IDEOGRAPHIC_SPACE}token=S3cr3tVal")
    assert "hello" in out
    assert "SECRET_t2xyzx5r" not in out


def test_trailing_whitespace_at_end_of_value_is_consumed() -> None:
    """值末尾的空白段属于该值：整段被抹，不留孤立空白。"""
    assert replies.fit_text(f"token=abc{IDEOGRAPHIC_SPACE * 3}") == (
        f"token={replies.REDACTED}"
    )


# --- 性能与线性 -----------------------------------------------------------


def test_one_megabyte_whitespace_separated_value_is_linear() -> None:
    """1MB「值 + 空白」重复形态：每个空白做一次键预读，总代价必须线性。"""
    import time

    payload = "token=" + ("secretvalue " * 90_000)[:1_000_000]
    started = time.perf_counter()
    out = replies._redact(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"1MB 空白密集值耗时 {elapsed:.2f}s"
    assert "secretvalue" not in out


def test_one_megabyte_single_whitespace_run_is_linear() -> None:
    """1MB 单段空白：空白段整段跳过，不能逐字符回到起点重扫。"""
    import time

    payload = f"token=abc{IDEOGRAPHIC_SPACE * 1_000_000}"
    started = time.perf_counter()
    out = replies._redact(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"1MB 单段空白耗时 {elapsed:.2f}s"
    assert out == f"token={replies.REDACTED}"


def test_one_megabyte_keylike_runs_between_whitespace_are_linear() -> None:
    """空白之间是长键形状的串：每次预读只看一段，不能回扫整条尾巴。"""
    import time

    payload = "token=" + ("a" * 200 + LINE_SEPARATOR) * 6000
    assert len(payload) > 1_000_000
    started = time.perf_counter()
    out = replies._redact(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"1MB 长键形状串耗时 {elapsed:.2f}s"
    assert "a" * 100 not in out


def test_one_megabyte_alternating_whitespace_runs_are_linear() -> None:
    """长键串与长空白段交替：预读不得把后续空白段重复扫多遍。"""
    import time

    unit = "a" * 100 + IDEOGRAPHIC_SPACE * 100
    payload = "token=" + unit * 5000
    assert len(payload) > 1_000_000
    started = time.perf_counter()
    replies._redact(payload)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"1MB 交替形态耗时 {elapsed:.2f}s"


def test_whitespace_heavy_value_does_not_recurse() -> None:
    """空白密集输入不能走进 Python 递归：调用栈深度与空白段数无关。"""
    payload = "token=" + ("hunter " * 4000)
    out = replies._redact(payload)
    assert isinstance(out, str)
    assert "hunter" not in out


def test_scan_value_uses_no_recursion_or_regex() -> None:
    """实现约束：预读只用 `_scan_key` / `_scan_separator`，不递归、不用正则。"""
    import inspect

    source = inspect.getsource(replies._scan_value)
    assert "re." not in source
    assert "_scan_value" not in source.split('"""')[-1]
