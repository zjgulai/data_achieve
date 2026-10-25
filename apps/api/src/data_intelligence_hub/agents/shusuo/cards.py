"""数说的飞书确认卡与结果卡。

纯函数生成飞书卡片 JSON（schema 2.0），不做任何 IO；
按钮 value 只携带 action 与 token，完整参数只保存在服务端。
所有动态文本先过脱敏/截断再进卡片。
"""

from __future__ import annotations

from typing import Any

from .capabilities import CollectOutcome, PreflightResult
from .proposal_store import PENDING_TTL_SECONDS, PendingProposal
from .replies import (
    MAX_TITLE_CHARS,
    _cost_line,
    _fit,
    _format_cost,
    _format_duration,
    _redact,
    _render_previews,
    fit_text,
    preflight_error_text,
    redact_structure,
    run_detail_url,
    structured_text,
)

SCHEMA_VERSION = "2.0"
MAX_PARAM_LINES = 8
MAX_PARAM_VALUE_CHARS = 120
MAX_FOOTER_CHARS = 200
MAX_NOTE_CHARS = 300
MAX_ERROR_CHARS = 800

_EXPIRY_LINE = f"{PENDING_TTL_SECONDS // 60} 分钟内有效"


def _card_title(title: str) -> str:
    """动态标题（可能含用户关键词）：先脱敏再截断，密钥片段绝不进卡。"""
    return _fit(structured_text(title), MAX_TITLE_CHARS)


def _card_text(value: str, limit: int) -> str:
    """卡片边界脱敏：先脱敏再截断。

    标题、说明等动态文本来自用户输入，上游（replies/fit_text）不保证
    已经脱敏；卡片构造函数自己再过一次，密钥不落卡。
    """
    return _fit(structured_text(value), limit)


def _shell(
    title: str, template: str, elements: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "config": {"update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": _card_title(title)},
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
    """标量直出；容器按结构脱敏后压成单行 JSON。只用于摘要展示，不进按钮 value。"""
    return structured_text(value)


def _param_summary(params: dict[str, Any]) -> str:
    """白名单摘要：每行 key=value，最多 MAX_PARAM_LINES 行。

    值和键都过 `structured_text`：嵌套 dict/list 会先按结构抹掉密钥再渲染，
    避免 `str(dict)` 的形态绕过文本正则。整行再过一次 `_redact` 兜底
    无键名的裸 Bearer 之类。
    """
    lines: list[str] = []
    safe_params = redact_structure(params)
    for key, value in safe_params.items():
        line = _redact(
            f"- {_fit(str(key), MAX_PARAM_VALUE_CHARS)}"
            f"={_fit(_summary_value(value), MAX_PARAM_VALUE_CHARS)}"
        )
        lines.append(line)
        if len(lines) >= MAX_PARAM_LINES:
            break
    return "\n".join(lines)


def _footer(pending: PendingProposal) -> str:
    return fit_text(f"提案短码：{pending.token}", limit=MAX_FOOTER_CHARS)


def _proposal_summary(
    pending: PendingProposal, preflight: PreflightResult
) -> str:
    proposal = pending.proposal
    params = preflight.normalized_params or dict(proposal.params)
    lines = [
        f"**意图：{_card_title(proposal.title)}**",
        f"端点：{proposal.endpoint_type}",
        "参数：",
        _param_summary(params),
        f"预计记录数：{proposal.estimated_items}",
        _cost_line(preflight.cost_notice),
        _EXPIRY_LINE,
    ]
    if proposal.note:
        lines.append(f"说明：{_card_text(proposal.note, MAX_NOTE_CHARS)}")
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
        f"**正在采集：{_card_title(proposal.title)}**\n\n"
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


def retryable_preflight_card(
    pending: PendingProposal, preflight: PreflightResult
) -> dict[str, Any]:
    """预检失败卡：条件挡执行，token 仍有效，给「重试」与「取消」。

    这不是上游失败：绝不能复用 failure_card 的「采集未返回数据」文案，
    否则用户会以为额度已经花掉。
    """
    reasons = preflight_error_text(preflight)
    content = fit_text(
        "**当前状态或配置不允许执行**\n\n"
        f"{reasons}\n\n"
        "提案仍然有效，条件恢复后可以重试。",
        limit=MAX_ERROR_CHARS,
    )
    elements = [
        _markdown(content),
        *_action_row(
            _callback_button("重试", "primary_filled", "confirm", pending.token),
            _callback_button("取消", "danger", "cancel", pending.token),
        ),
        _markdown(_footer(pending)),
    ]
    return _shell("当前无法执行", "orange", elements)


def internal_error_card() -> dict[str, Any]:
    """后台未捕获异常的安全落卡。

    绝不能留在「正在采集」：那一屏会让用户以为还在跑，也就不会重发。
    文案不带异常类名、堆栈或内部字段。
    """
    content = "服务内部错误，本次未执行，请重新发起提案"
    return _shell("服务内部错误", "red", [_markdown(content)])


def replaced_card() -> dict[str, Any]:
    """旧 token 被新提案替换：请到新卡片操作。"""
    content = "该提案已被新提案替换。请在新提案卡片上操作；要继续采集请重新发场景命令。"
    return _shell("提案已被替换", "grey", [_markdown(content)])


def cancelled_card(pending: PendingProposal) -> dict[str, Any]:
    proposal = pending.proposal
    content = (
        f"已取消：{_card_title(proposal.title)}\n\n"
        "该提案已作废，token 不可再用。要继续采集请重新发场景命令。"
    )
    return _shell("提案已取消", "grey", [_markdown(content)])


def expired_card() -> dict[str, Any]:
    content = "待确认的操作已过期。请重新发一次场景命令，生成新提案后再确认。"
    return _shell("提案已过期", "grey", [_markdown(content)])
