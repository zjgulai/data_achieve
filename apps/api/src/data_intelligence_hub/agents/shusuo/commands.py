"""数说的命令解析与回复文本。

设计原则：
- 显式命令优先；场景词进入确定性的意图层。
- 自由文本只生成提案，用户回复「确认」后才执行采集。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from . import capabilities, cards, intents, llm, proposal_store, replies

HELP_TEXT = """数说 · 全域外部数据助手

场景命令（直接说人话，先给提案，回复「确认」才执行）：
- 搜 [平台] <关键词>：TikTok/抖音/小红书/微博/B站/YouTube/Instagram/X/Reddit；省略平台走 Exa
- 评论 <URL>：TikTok / Reddit / YouTube 评论
- 账号 <平台> <handle>：TikTok / Instagram / X 资料
- 热点 [平台]：抖音 / X / YouTube / Reddit
- 新闻 <关键词>：新闻搜索
- 选品 <关键词>：AliExpress 选品
- 价格 <URL 或 ASIN>：Amazon 价格追踪

管理命令：
- 帮助 / 总览
- 平台 [关键词]
- 能力 <平台或关键词>
- 详情 <端点>
- 采集 <端点> [key=value ...]
- 结果 <run_id>：查看最近一次运行的原始记录
- 确认 / 取消：执行或放弃当前提案

示例：
- 搜 reddit AI
- 评论 https://www.tiktok.com/@user/video/123
- 账号 instagram nike
- 新闻 新能源汽车
- 采集 tikhub_reddit_search keyword=AI max_items=5

提示：场景命令的参数可加 max_items=20。采集会消耗上游额度。
"""

_PLATFORM_HINTS = {"平台", "平台列表", "platform", "platforms"}
_CAPABILITY_HINTS = {"/能力", "能力", "端点", "capability", "capabilities"}
_DESCRIBE_HINTS = {"详情", "说明", "describe"}
_COLLECT_HINTS = {"采集", "抓取", "收集", "collect", "run"}
_STATUS_HINTS = {"总览", "状态", "overview", "status"}
_HELP_HINTS = {"帮助", "菜单", "help", "你好", "hi", "hello", "?"}
_RESULT_HINTS = {"结果", "数据", "result"}
_CONFIRM_HINTS = {"确认", "执行", "confirm", "ok"}
_CANCEL_HINTS = {"取消", "放弃", "cancel"}
_INTENT_HINTS = {"搜", "搜索", "评论", "账号", "热点", "热搜", "新闻", "选品", "价格"}

_MENTION_PATTERN = re.compile(r"@_user_\d+|@_all")


@dataclass(frozen=True)
class Command:
    name: str
    argument: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Reply:
    text: str
    ack: str | None = None
    card: dict[str, Any] | None = None
    pending_token: str | None = None


def clean_text(text: str) -> str:
    return _MENTION_PATTERN.sub("", text).strip()


def _collect_reply_text(outcome: capabilities.CollectOutcome) -> str:
    """采集结果统一走回复模板；text 兜底时同样过 fit_text。"""
    if outcome.ok:
        text = replies.collect_success_text(outcome)
    else:
        text = replies.collect_failure_text(outcome)
    return text or replies.fit_text(outcome.text)


def _coerce(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    if value.startswith(("[", "{")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def parse_params(tokens: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for token in tokens:
        if "=" not in token:
            raise ValueError(f"参数要写成 key=value：{token}")
        key, value = token.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("参数名不能为空")
        params[key] = _coerce(value.strip())
    return params


def parse_command(text: str) -> Command:
    cleaned = clean_text(text)
    if not cleaned:
        return Command("help")

    parts = cleaned.split()
    head = parts[0].casefold()
    rest = parts[1:]

    if head in {h.casefold() for h in _HELP_HINTS}:
        return Command("help")
    if head in {h.casefold() for h in _STATUS_HINTS}:
        return Command("status")
    if head in {h.casefold() for h in _CONFIRM_HINTS}:
        return Command("confirm", rest[0] if rest else "")
    if head in {h.casefold() for h in _CANCEL_HINTS}:
        return Command("cancel", rest[0] if rest else "")
    if head in {h.casefold() for h in _PLATFORM_HINTS}:
        return Command("platforms", " ".join(rest).strip())
    if head in {h.casefold() for h in _CAPABILITY_HINTS}:
        return Command("capabilities", " ".join(rest).strip())
    if head in {h.casefold() for h in _DESCRIBE_HINTS}:
        return Command("describe", rest[0] if rest else "")
    if head in {h.casefold() for h in _RESULT_HINTS}:
        return Command("result", rest[0] if rest else "")
    if head in {h.casefold() for h in _COLLECT_HINTS}:
        if not rest:
            return Command("collect_error", "缺少端点名")
        try:
            params = parse_params(rest[1:])
        except ValueError as exc:
            return Command("collect_error", str(exc))
        return Command("collect", rest[0], params)
    if head in {h.casefold() for h in _INTENT_HINTS}:
        return Command("intent", cleaned)

    return Command("unknown", cleaned)


def _fit(text: str) -> str:
    return replies.fit_text(text)


def _intent_reply(
    pending: proposal_store.PendingProposal, preflight: capabilities.PreflightResult
) -> Reply:
    """提案确认卡；文本兜底自带 token 短码，卡片失败时不丢确认入口。"""
    text_lines = [replies.proposal_text(pending, preflight), f"提案短码：{pending.token}"]
    return Reply(
        text=_fit("\n".join(text_lines)),
        card=cards.proposal_card(pending, preflight),
        pending_token=pending.token,
    )


async def _confirm_reply(
    token: str | None, chat_id: str, open_id: str
) -> Reply:
    """确认：peek → force preflight → consume → collect。

    预检失败不消费 token，用户可以修正后重试或取消。
    """
    status, pending = proposal_store.peek_pending(token, chat_id, open_id)
    if pending is None:
        return Reply(_fit(replies.pending_status_text(status)))
    proposal = pending.proposal
    preflight = await capabilities.preflight_proposal(proposal, force_status=True)
    if not preflight.allowed:
        return Reply(_fit(replies.preflight_error_text(preflight)))
    status, pending = proposal_store.consume_pending(token, chat_id, open_id)
    if pending is None:
        return Reply(_fit(replies.pending_status_text(status)))
    outcome = await capabilities.collect(
        proposal.endpoint_type, preflight.normalized_params
    )
    return Reply(
        _fit(_collect_reply_text(outcome)),
        ack=_fit(f"正在采集 {proposal.endpoint_type}，请稍候…"),
    )


async def execute(
    command: Command,
    *,
    chat_id: str = "",
    open_id: str = "",
    message_id: str = "",
) -> Reply:
    if command.name == "help":
        return Reply(_fit(HELP_TEXT))
    if command.name == "status":
        return Reply(_fit(await capabilities.overview_text()))
    if command.name == "platforms":
        return Reply(_fit(await capabilities.platforms_text(command.argument)))
    if command.name == "capabilities":
        return Reply(_fit(await capabilities.capabilities_text(command.argument)))
    if command.name == "describe":
        if not command.argument:
            return Reply(_fit("用法：详情 <端点名>"))
        return Reply(_fit(await capabilities.describe_text(command.argument)))
    if command.name == "result":
        if not command.argument:
            return Reply(_fit("用法：结果 <run_id>"))
        return Reply(_fit(await capabilities.run_records_text(command.argument)))
    if command.name == "collect_error":
        return Reply(_fit(f"命令格式有误：{command.argument}\n\n{HELP_TEXT}"))
    if command.name == "collect":
        proposal = intents.Proposal(
            endpoint_type=command.argument,
            params=dict(command.params),
            title=f"显式采集：{command.argument}",
        )
        preflight = await capabilities.preflight_proposal(proposal, force_status=True)
        if not preflight.allowed:
            return Reply(_fit(replies.preflight_error_text(preflight)))
        outcome = await capabilities.collect(
            proposal.endpoint_type, preflight.normalized_params
        )
        return Reply(
            _fit(_collect_reply_text(outcome)),
            ack=_fit(f"正在采集 {command.argument}，请稍候…"),
        )
    if command.name == "intent":
        built = intents.build_proposal(command.argument)
        if isinstance(built, str):
            return Reply(_fit(built))
        preflight = await capabilities.preflight_proposal(built)
        if not preflight.allowed:
            return Reply(_fit(replies.preflight_error_text(preflight)))
        pending = proposal_store.replace_pending(chat_id, open_id, built)
        return _intent_reply(pending, preflight)
    if command.name == "confirm":
        return await _confirm_reply(command.argument or None, chat_id, open_id)
    if command.name == "cancel":
        status = proposal_store.cancel_pending(
            command.argument or None, chat_id, open_id
        )
        if status is proposal_store.ProposalLookup.ACTIVE:
            return Reply(_fit("已取消待确认的操作。"))
        return Reply(_fit(replies.pending_status_text(status)))
    if command.name == "unknown":
        answer = await llm.answer_question(command.argument)
        if answer:
            return Reply(_fit(answer))
        return Reply(
            _fit(
                "我没有识别这条指令。可以试试：\n"
                "- 帮助\n"
                "- 平台 / 能力 <关键词>\n"
                "- 搜 reddit AI\n"
                "- 采集 <端点> key=value\n\n"
                + HELP_TEXT
            )
        )
    return Reply(_fit(HELP_TEXT))
