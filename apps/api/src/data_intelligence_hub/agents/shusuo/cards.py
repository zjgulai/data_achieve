"""数说的飞书确认卡与结果卡。

纯函数生成飞书卡片 JSON（schema 2.0），不做任何 IO；
按钮 value 只携带 action 与 token，完整参数只保存在服务端。
所有动态文本先过脱敏/截断再进卡片。
"""

from __future__ import annotations

import json
from typing import Any

from .capabilities import CollectOutcome, PreflightResult
from .proposal_store import PENDING_TTL_SECONDS, PendingProposal
from .replies import (
    MAX_TITLE_CHARS,
    _fit,
    _format_cost,
    _format_duration,
    _redact,
    _render_previews,
    fit_text,
    run_detail_url,
)

SCHEMA_VERSION = "2.0"
MAX_PARAM_LINES = 8
MAX_PARAM_VALUE_CHARS = 120
MAX_FOOTER_CHARS = 200
MAX_NOTE_CHARS = 300

_EXPIRY_LINE = f"{PENDING_TTL_SECONDS // 60} 分钟内有效"
_UNKNOWN_COST_TEXT = "费用未知，按上游实际计费"


def _shell(
    title: str, template: str, elements: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "config": {"update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": _fit(title, MAX_TITLE_CHARS)},
            "template": template,
        },
        "body": {"direction": "vertical", "elements": elements},
    }


def _markdown(content: str) -> dict[str, Any]:
    return {"tag": "markdown", "content": content}


def _callback_button(text: str, style: str, action: str, token: str) -> dict[str, Any]:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": style,
        "behaviors": [{"type": "callback", "value": {"action": action, "token": token}}],
    }


def _action_row(
    confirm: dict[str, Any], cancel: dict[str, Any]
) -> list[dict[str, Any]]:
    """2.0 已废弃 1.0 的 action 模块；按钮直接放 elements，并排成一行。"""
    return [confirm, cancel]


def _summary_value(value: Any) -> str:
    """标量直出；容器压成单行 JSON。只用于摘要展示，不进按钮 value。"""
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _param_summary(params: dict[str, Any]) -> str:
    """白名单摘要：每行 key=value，最多 MAX_PARAM_LINES 行。

    先拼完整行再脱敏：键值对规则需要 key=value 上下文才命中，
    对裸值脱敏会漏掉无键名形态的密钥。
    """
    lines: list[str] = []
    for key, value in params.items():
        line = _redact(
            f"- {_fit(str(key), MAX_PARAM_VALUE_CHARS)}"
            f"={_fit(_summary_value(value), MAX_PARAM_VALUE_CHARS)}"
        )
        lines.append(line)
        if len(lines) >= MAX_PARAM_LINES:
            break
    return "\n".join(lines)


def _cost_line(preflight: PreflightResult) -> str:
    notice = preflight.cost_notice or _UNKNOWN_COST_TEXT
    if "费用未知" in notice:
        return f"⚠️ {_UNKNOWN_COST_TEXT}"
    return f"费用：{notice}"


def _footer(pending: PendingProposal) -> str:
    return fit_text(f"提案短码：{pending.token}", limit=MAX_FOOTER_CHARS)


def _proposal_summary(
    pending: PendingProposal, preflight: PreflightResult
) -> str:
    proposal = pending.proposal
    params = preflight.normalized_params or dict(proposal.params)
    lines = [
        f"**意图：{_fit(proposal.title, MAX_TITLE_CHARS)}**",
        f"端点：{proposal.endpoint_type}",
        "参数：",
        _param_summary(params),
        f"预计记录数：{proposal.estimated_items}",
        _cost_line(preflight),
        _EXPIRY_LINE,
    ]
    if proposal.note:
        lines.append(f"说明：{fit_text(proposal.note, limit=MAX_NOTE_CHARS)}")
    return "\n".join(lines)


def proposal_card(
    pending: PendingProposal, preflight: PreflightResult
) -> dict[str, Any]:
    elements = [
        _markdown(_proposal_summary(pending, preflight)),
        *_action_row(
            _callback_button("确认", "primary_filled", "confirm", pending.token),
            _callback_button("取消", "danger", "cancel", pending.token),
        ),
        _markdown(_footer(pending)),
    ]
    return _shell("确认采集提案", "blue", elements)


def processing_card(pending: PendingProposal) -> dict[str, Any]:
    proposal = pending.proposal
    content = (
        f"**正在采集：{_fit(proposal.title, MAX_TITLE_CHARS)}**\n\n"
        f"端点：{proposal.endpoint_type}\n\n请稍候，结果会更新在这张卡片上。"
    )
    return _shell("正在采集", "blue", [_markdown(content)])


def success_card(
    pending: PendingProposal, outcome: CollectOutcome
) -> dict[str, Any]:
    lines = [
        "**采集完成**",
        f"端点：{outcome.endpoint_type}",
        f"记录数：{outcome.records_count}",
    ]
    duration = _format_duration(outcome.duration_ms)
    if duration:
        lines.append(f"耗时：{duration}")
    cost = _format_cost(outcome.total_cost_usd)
    if cost:
        lines.append(cost)
    previews = _render_previews(outcome)
    if previews:
        lines.extend(previews)
    if outcome.task_run_id:
        lines.append(f"查看：{run_detail_url(outcome.task_run_id)}")
    return _shell("采集完成", "green", [_markdown(fit_text("\n".join(lines)))])


def failure_card(pending: PendingProposal, message: str) -> dict[str, Any]:
    content = fit_text(f"**采集未返回数据**\n原因：{message}")
    return _shell("采集未返回数据", "red", [_markdown(content)])


def cancelled_card(pending: PendingProposal) -> dict[str, Any]:
    proposal = pending.proposal
    content = (
        f"已取消：{_fit(proposal.title, MAX_TITLE_CHARS)}\n\n"
        "该提案已作废，token 不可再用。要继续采集请重新发场景命令。"
    )
    return _shell("提案已取消", "grey", [_markdown(content)])


def expired_card() -> dict[str, Any]:
    content = "待确认的操作已过期。请重新发一次场景命令，生成新提案后再确认。"
    return _shell("提案已过期", "grey", [_markdown(content)])
