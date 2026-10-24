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
# token=xxx / api_key: xxx / password=xxx / secret: xxx / cookie=xxx，
# 以及 JSON 形态的 "token": "xxx"（键后带引号）。值取到空白、逗号、分号或右括号为止。
_SECRET_KV_PATTERN = re.compile(
    r"(?i)\b(token|secret|password|passwd|api_key|apikey|access_key|access_token|"
    r"private_key|credential|authorization|cookie)"
    r"(\"?\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)

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


def _redact(text: str) -> str:
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", text)
    redacted = _SECRET_KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", redacted)
    return redacted


def _canonical_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).casefold())


def _is_secret_key(key: Any) -> bool:
    return _canonical_key(key) in _SECRET_KEY_CANONICAL


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
