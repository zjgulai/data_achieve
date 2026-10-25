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
# Unicode 空白：分隔符扫描认 `isspace()`，裸值终止符也必须认
# ---------------------------------------------------------------------------

# 这些字符 str.isspace() 为真，但都不在 ASCII 的 " \t\r\n" 里。
# 上游 JSON / 日志里常见 NBSP、全角空格、NEL 等。
UNICODE_SPACES = (
    ("nbsp_u00a0", " "),
    ("ideographic_u3000", "　"),
    ("vertical_tab_u000b", "\u000b"),
    ("form_feed_u000c", "\u000c"),
    ("nel_u0085", "\u0085"),
    ("line_separator_u2028", " "),
    ("narrow_nbsp_u202f", " "),
)


@pytest.mark.parametrize(("label", "space"), UNICODE_SPACES, ids=[s[0] for s in UNICODE_SPACES])
def test_unicode_space_terminates_bare_value(label: str, space: str) -> None:
    """裸值必须在任何 Unicode 空白处停下，否则后面的 KV 整段被吞掉。"""
    assert space.isspace(), f"{label} 不是空白字符，测试前提失效"
    payload = f"token=abc{space}password: hunter2"
    out = replies.fit_text(payload)
    assert "hunter2" not in out
    assert "abc" not in out


@pytest.mark.parametrize(("label", "space"), UNICODE_SPACES, ids=[s[0] for s in UNICODE_SPACES])
def test_unicode_space_keeps_surrounding_text(label: str, space: str) -> None:
    """只抹值，不动结构：空白与普通词必须原样保留。"""
    payload = f"note=hello{space}token=S3cr3tVal"
    out = replies.fit_text(payload)
    assert "SECRET_t2xyzx5r" not in out
    assert "hello" in out


@pytest.mark.parametrize(("label", "space"), UNICODE_SPACES, ids=[s[0] for s in UNICODE_SPACES])
def test_unicode_space_secrets_absent_from_failure_card(label: str, space: str) -> None:
    """失败卡是错误文本的真实落点：两个密钥都不能出现在卡片 JSON 里。"""
    pending = _pending({"query": "AI"})
    message = f"upstream 400: token=abc{space}password: hunter2"
    card = cards.failure_card(pending, message)
    serialized = json.dumps(card, ensure_ascii=False)
    assert "hunter2" not in serialized
    assert "token=[redacted]" in serialized


@pytest.mark.parametrize(("label", "space"), UNICODE_SPACES, ids=[s[0] for s in UNICODE_SPACES])
def test_unicode_space_structured_text_path(label: str, space: str) -> None:
    """`structured_text` 是卡片与记录预览的共用渲染路径。"""
    rendered = replies.structured_text(f"token=abc{space}password: hunter2")
    assert "hunter2" not in rendered
    assert "token=[redacted]" in rendered


def test_ascii_separator_behaviour_unchanged() -> None:
    """ASCII 路径不能因为改空白判定而变：空格 / Tab / 换行都要照旧。"""
    for separator in (" ", "\t", "\n", "\r\n", "\x0b", "\x0c"):
        out = replies.fit_text(f"token=abc{separator}password: hunter2")
        assert "hunter2" not in out
        assert "abc" not in out


def test_braces_still_work_with_unicode_spaces() -> None:
    payload = "token={S3cr3tVal} password={{SECRET_B}}　note=ok"
    out = replies.fit_text(payload)
    assert "S3cr3tVal" not in out
    assert "SECRET_B" not in out
    assert "note=ok" in out


def test_long_value_with_unicode_space_is_fully_redacted() -> None:
    payload = "token=" + "A" * 5000 + " note=ok"
    out = replies.fit_text(payload)
    assert "A" not in out
    assert "note=ok" in out


