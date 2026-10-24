"""数说的统一回复模板。

所有用户可见文本都从这里出：脱敏在截断之前，输出不超过 6000 字符。
模板是纯函数，不做 IO；采集结果经 `CollectOutcome`、预检经 `PreflightResult` 传入。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .capabilities import UNKNOWN_COST_NOTICE, CollectOutcome, PreflightResult
from .config import get_shushuo_config
from .proposal_store import PendingProposal, ProposalLookup

MAX_REPLY_CHARS = 6000
MAX_TITLE_CHARS = 120
MAX_URL_CHARS = 200
MAX_RECORD_PREVIEWS = 3

_TRUNCATION_SUFFIX = "\n…（内容过长，已截断）"

# 脱敏规则（最小集）：Bearer 头、常见密钥键值对。替换先于截断，
# 保证被截断的片段里也不会出现明文密钥。
REDACTED = "[redacted]"
_REDACTED = REDACTED
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+\S+")
# 文本形态的密钥键值对由一个确定性扫描器处理（见 `_redact_kv_text`），
# 不再用「键 + 分隔符 + 值」的正则加值递归——那条路有三个已知缺陷：
#
# 1. 递归深度与分隔符数量成正比：`a=` 重复 500 次就 RecursionError。
# 2. 值限长会让超长密钥被截断成"前 4096 字符已抹、尾部明文留下"。
# 3. 键名限长会让超长键退化成普通键，凭据值原样输出。
#
# 扫描器从左到右单遍推进，键名与值都不限长，天然线性且无递归。
_KV_KEY_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)
_KV_QUOTES = frozenset("\"'")
# 裸值在此处终止：与旧正则保持一致的边界，外加单/双花括号。
# 花括号不放宽成"任意单层 JSON"，否则 `{"error":{"api_key":"..."}}` 会被
# 外层键吞掉。
_KV_BARE_STOP = frozenset(" \t\r\n,;{}\"'?&")


# 结构脱敏用的键名集合：整键命中即把值换成 REDACTED（不保留原值形态）。
# 只放「装的就是凭据」的键。`auth` 这类容器键不放：它常装非敏感字段，
# 整棵抹掉会把 region 之类的正常参数也吞了。
_SECRET_KEYS = frozenset(
    {
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
        "credentials",
        "private_key",
        "session",
        "authorization",
        "set_cookie",
        "x_api_key",
    }
)
# 键名归一化：去掉分隔符与大小写差异，`Access-Token` / `accessToken` 都命中。
_SECRET_KEY_CANONICAL = frozenset(
    re.sub(r"[^a-z0-9]", "", key) for key in _SECRET_KEYS
)

# 复合键名（OAuth / 上游凭据字段）按「分隔边界 + 安全后缀」识别：
# `client_secret`、`refresh_token`、`user_session`、`secret_key`、`refreshToken`。
# 后缀必须真的带走一段前缀，且前缀与后缀之间要有分隔符（`_`、`-`、`.`）
# 或驼峰转折——所以 `monkey`、`hockey`、`keyboard`、`keynote`、`obsession`
# 都不会被误抹。
_SECRET_KEY_SUFFIXES = (
    "token",
    "secret",
    "password",
    "passwd",
    "cookie",
    "credential",
    "credentials",
    "session",
    "key",
)
# 本身就是完整键名的短词。
_SECRET_KEY_WORDS = frozenset({"bearer", "jwt"})

# 形似凭据、其实是功能参数的分页游标。整值抹掉会让复核者看不出请求分到了哪一页，
# 而它们本身不含凭据（`page_token` 是上游返回的游标串）。
_NON_SECRET_KEY_CANONICAL = frozenset(
    {
        "pagetoken",
        "paginationtoken",
        "nextpagetoken",
        "nexttoken",
        "cursortoken",
        "continuationtoken",
        "synctoken",
    }
)
_KEY_BOUNDARY_CHARS = frozenset("_-.")


def _has_secret_suffix(raw_key: str) -> bool:
    """复合键判定：`client_secret` 命中，`monkey` 不命中。"""
    lowered = raw_key.casefold()
    for suffix in _SECRET_KEY_SUFFIXES:
        if not lowered.endswith(suffix):
            continue
        suffix_start = len(raw_key) - len(suffix)
        if suffix_start <= 0:
            # 整键就是后缀（`token`/`key`），交给精确键集合判断。
            continue
        boundary = raw_key[suffix_start - 1]
        if boundary in _KEY_BOUNDARY_CHARS:
            return True
        # 驼峰：`refreshToken` / `xApiKey`。
        if raw_key[suffix_start].isupper() and boundary.islower():
            return True
    return False


def _redacted_value(original: str) -> str:
    """替换文本保持原值的引号外形，让脱敏后的 JSON 仍可解析。"""
    quoted = len(original) >= 2 and original[0] in _KV_QUOTES and original[-1] == original[0]
    if quoted:
        return f"{original[0]}{REDACTED}{original[0]}"
    return REDACTED


def _scan_key(text: str, start: int) -> tuple[str, int, bool] | None:
    """读 `[quote]key[quote]`，返回 (键名, 键后位置, 是否带引号)；读不到返回 None。

    键名不限长：限长会让 `xxxx..._token` 这类长键丢掉凭据后缀，
    值就再也不被抹。限长换来的线性时间由调用方的跳跃式推进保证。
    """
    index = start
    quote = ""
    if index < len(text) and text[index] in _KV_QUOTES:
        quote = text[index]
        index += 1
    key_start = index
    while index < len(text) and text[index] in _KV_KEY_CHARS:
        index += 1
    if index == key_start:
        return None
    key = text[key_start:index]
    if quote:
        if index < len(text) and text[index] == quote:
            index += 1
        else:
            # 引号没闭合：这是「引号值里藏 KV」（`"token=..."`），
            # 不能把引号当键的开头吃掉，退一格让下一轮从键名开始。
            return None
    return key, index, bool(quote)


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _scan_separator(text: str, start: int) -> int | None:
    """读 `\\s*[=:]\\s*`，返回分隔符之后的位置；不是分隔符返回 None。"""
    index = _skip_spaces(text, start)
    if index >= len(text) or text[index] not in "=:":
        return None
    return _skip_spaces(text, index + 1)


def _scan_value(text: str, start: int) -> int:
    """返回值结束位置（不含）。

    值不限长：截断会让超长密钥只抹前 4096 字符、尾部明文留在回复里。
    """
    if start >= len(text):
        return start
    head = text[start]
    if head in _KV_QUOTES:
        close = text.find(head, start + 1)
        return len(text) if close < 0 else close + 1
    if head == "{":
        if text.startswith("{{", start):
            close = text.find("}}", start + 2)
            return len(text) if close < 0 else close + 2
        close = text.find("}", start + 1)
        return len(text) if close < 0 else close + 1
    index = start
    while index < len(text) and text[index] not in _KV_BARE_STOP:
        index += 1
    return index


def _redact_kv_text(text: str) -> str:
    """单遍扫描脱敏 `key=value` / `key: value`，无递归。

    非密钥键只输出 `键 + 分隔符` 就继续扫值：值里的密钥（压缩 JSON、
    引号值里的 KV）会在同一遍里被后续步骤取到，不需要回扫值。
    因此递归深度与分隔符数量无关，分隔符洪泛不会打爆栈。

    只有密钥键才扫描并消费值。非密钥键若也扫值，`a=a=a=...` 这种
    「分隔符不是值终止符」的输入会在每个起点重扫整条尾巴（O(n²)）。
    """
    pieces: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        parsed = _scan_key(text, index)
        if parsed is None:
            pieces.append(text[index])
            index += 1
            continue
        key, after_key, _ = parsed
        after_sep = _scan_separator(text, after_key)
        if after_sep is None:
            # 键名之后没有分隔符：键内部任何起点都会以同样方式失败，
            # 直接跳过整段键名，避免长串上的 O(n²) 重扫。
            pieces.append(text[index:after_key])
            index = after_key
            continue
        if not _is_secret_key(key):
            # 非密钥键：只吐 `键 + 分隔符`，值留给下一轮（不消费、不递归）。
            pieces.append(text[index:after_sep])
            index = after_sep
            continue
        value_end = _scan_value(text, after_sep)
        pieces.append(text[index:after_sep])
        pieces.append(_redacted_value(text[after_sep:value_end]))
        index = max(value_end, after_sep)
    return "".join(pieces)


def _redact(text: str) -> str:
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", text)
    return _redact_kv_text(redacted)


def _canonical_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).casefold())


def _is_secret_key(key: Any) -> bool:
    raw = str(key)
    canonical = _canonical_key(raw)
    if not canonical:
        return False
    if canonical in _NON_SECRET_KEY_CANONICAL:
        return False
    if canonical in _SECRET_KEY_CANONICAL or canonical in _SECRET_KEY_WORDS:
        return True
    return _has_secret_suffix(raw)


def redact_structure(value: Any) -> Any:
    """递归结构脱敏：dict/list 里密钥键的值整体替换，其余值走文本脱敏。

    文本正则只认识 `token=xxx` 这种行内形态；`{"token": "xxx"}` 经
    `str(dict)` 渲染后形态会变，必须按结构先抹掉值。返回新对象，不改入参。
    """
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_secret_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_structure(item)
        return redacted
    if isinstance(value, list):
        return [redact_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_structure(item) for item in value)
    if isinstance(value, str):
        return _redact(value)
    return value


def structured_text(value: Any) -> str:
    """把任意值渲染成单行文本：容器走 JSON，密钥先按结构抹掉。"""
    safe = redact_structure(value)
    if isinstance(safe, str):
        return safe
    try:
        rendered = json.dumps(safe, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        rendered = str(safe)
    return _redact(rendered)


def fit_text(text: str, *, limit: int = MAX_REPLY_CHARS) -> str:
    """先脱敏再截断；limit 内原样返回。"""
    redacted = _redact(text)
    if len(redacted) <= limit:
        return redacted
    return redacted[: limit - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX


def _fit(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _trim_url(url: str) -> str:
    if not url:
        return ""
    return _fit(url, MAX_URL_CHARS)


@dataclass(frozen=True)
class _RecordPreview:
    title: str
    url: str


def _record_preview(record: dict[str, Any]) -> _RecordPreview | None:
    """从 quick-collect 记录摘要里取标题与链接。

    build_record_preview 的形状：{id, record_type, source_url, content,
    content_truncated, collected_at}；content 可能是 dict、list 或截断后的 str。

    回退标题走 `structured_text`：dict/list 渲染成脱敏后的 JSON，
    None 视为没有内容。绝不能落回 `str(content)` 的原样 repr——
    那既会把 `{'api_key': '...'}` 的形态带出来，也会让 `None` 变成 "None"。
    """
    if not isinstance(record, dict):
        return None
    content = record.get("content")
    url = ""
    raw_url = record.get("source_url")
    if isinstance(raw_url, str):
        url = raw_url
    title = ""
    if isinstance(content, dict):
        if not url:
            for key in ("url", "link", "source_url", "post_url"):
                value = content.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    url = value
                    break
        for key in ("title", "name", "text", "content", "post_title", "description"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                title = value.strip()
                break
    elif isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            for key in ("title", "name", "text"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break
    if not title and content is not None:
        title = structured_text(content)
    title = " ".join(_redact(title).split())
    if not title and not url:
        return None
    return _RecordPreview(title=_fit(title, MAX_TITLE_CHARS), url=_trim_url(url))


def run_detail_url(task_run_id: str) -> str:
    """运行详情链接。旧 /collect/ 路径已废弃。"""
    base = get_shushuo_config().console_base_url
    return f"{base}/runs/{task_run_id}"


def _format_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return ""
    seconds = duration_ms / 1000
    if seconds >= 10:
        return f"{seconds:.0f} 秒"
    return f"{seconds:.1f} 秒"


def _format_cost(total_cost_usd: str | None) -> str:
    if not total_cost_usd:
        return ""
    return f"费用：${total_cost_usd}"


def _render_previews(outcome: CollectOutcome) -> list[str]:
    lines: list[str] = []
    shown = 0
    for record in outcome.records[:MAX_RECORD_PREVIEWS]:
        preview = _record_preview(record)
        if preview is None:
            continue
        shown += 1
        lines.append(f"{shown}. {preview.title}")
        if preview.url:
            lines.append(f"   {preview.url}")
    return lines


def collect_success_text(outcome: CollectOutcome) -> str:
    lines = [
        "采集完成",
        f"端点：{outcome.endpoint_type}",
        f"记录数：{outcome.records_count}",
    ]
    duration = _format_duration(outcome.duration_ms)
    if duration:
        lines.append(f"耗时：{duration}")
    cost = _format_cost(outcome.total_cost_usd)
    if cost:
        lines.append(cost)
    lines.extend(_render_previews(outcome))
    if len(outcome.records) > MAX_RECORD_PREVIEWS:
        lines.append(f"…仅展示前 {MAX_RECORD_PREVIEWS} 条，共 {outcome.records_count} 条记录。")
    elif outcome.records and outcome.records_count > len(outcome.records):
        lines.append(f"…共 {outcome.records_count} 条记录。")
    if outcome.task_run_id:
        lines.append(f"运行 ID：{outcome.task_run_id}")
        lines.append(f"查看：{run_detail_url(outcome.task_run_id)}")
    return fit_text("\n".join(lines))


def collect_failure_text(outcome: CollectOutcome) -> str:
    # error_message 可能残留异常类名前缀（capabilities 已在源头去类名，
    # 这里是纵深防御）。只剥"类名 + 冒号"形态，且类名必须像异常类
    # （驼峰含 Error/Exception/Timeout 等，或至少带大写字母），避免把
    # "demo_endpoint 已下线"这类正常句子误剥。
    reason = outcome.error_message or "上游没有返回记录"
    reason = re.sub(
        r"^\s*[A-Za-z_][\w.]*(?:Error|Exception|Timeout|Denied|Failure|Abort)\w*"
        r"(?:\s*[:：]\s*|\s+)",
        "",
        reason,
    )
    reason = " ".join(reason.split())
    lines = [
        "采集未返回数据",
        f"端点：{outcome.endpoint_type}" if outcome.endpoint_type else "采集失败",
        f"原因：{reason}",
    ]
    previews = _render_previews(outcome)
    if previews:
        lines.append("已入库记录预览：")
        lines.extend(previews)
    if outcome.task_run_id:
        lines.append(f"运行 ID：{outcome.task_run_id}")
        lines.append(f"查看：{run_detail_url(outcome.task_run_id)}")
    return fit_text("\n".join(lines))


def proposal_text(pending: PendingProposal, preflight: PreflightResult) -> str:
    proposal = pending.proposal
    params = preflight.normalized_params or dict(proposal.params)
    # 整棵参数先按结构脱敏：`{"id": "..."}` 只有父键 `session` 命中密钥集合，
    # 逐值渲染会绕过父键判断。
    safe_params = redact_structure(params)
    param_lines = "\n".join(
        f"- {structured_text(key)}={structured_text(value)}"
        for key, value in safe_params.items()
    )
    lines = [
        f"意图：{_fit(structured_text(proposal.title), MAX_TITLE_CHARS)}",
        f"端点：{proposal.endpoint_type}",
        "参数：",
        param_lines,
    ]
    if proposal.note:
        lines.append(f"说明：{structured_text(proposal.note)}")
    if preflight.cost_notice:
        lines.append(_cost_line(preflight.cost_notice))
    lines.extend(
        [
            "回复「确认」执行；回复「取消」放弃。5 分钟内有效。",
        ]
    )
    return fit_text("\n".join(lines))


def _cost_line(cost_notice: str) -> str:
    """费用单行文案：未知加警示前缀，已知只写 `费用约 ...`，不重复 `费用` 二字。

    卡片与文本回复共用这一份，避免两处措辞漂移（曾出现 `费用：费用约 ...`）。
    """
    if not cost_notice:
        return ""
    if UNKNOWN_COST_NOTICE in cost_notice:
        return f"⚠️ {cost_notice}"
    return cost_notice


def preflight_error_text(result: PreflightResult) -> str:
    lines = ["无法执行采集：", *result.errors]
    lines.extend(result.warnings)
    return fit_text("\n".join(lines))


_STATUS_TEXTS: dict[ProposalLookup, str] = {
    ProposalLookup.ACTIVE: "",
    ProposalLookup.MISSING: "没有待确认的操作。请先发一个场景命令，例如「搜 reddit AI」。",
    ProposalLookup.EXPIRED: "待确认的操作已过期。请重新发一次场景命令。",
    ProposalLookup.REPLACED: "该提案已被新提案替换，请回复新提案卡片里的「确认」。",
    ProposalLookup.FORBIDDEN: "无法确认其他会话的提案。",
}


def pending_status_text(status: ProposalLookup) -> str:
    return _STATUS_TEXTS.get(status, "提案状态异常，请重新发起。")
