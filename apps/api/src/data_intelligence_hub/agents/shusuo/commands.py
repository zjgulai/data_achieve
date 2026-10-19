"""数说的命令解析与回复文本。

设计原则：
- 先支持确定性的命令，避免模型幻觉导致误采集。
- 自由文本不直接触发采集；最多给出建议。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from . import capabilities

HELP_TEXT = """数说 · 全域外部数据助手

可用命令：
- 帮助：显示本说明
- 平台 [关键词]：列出平台包
- 能力 <平台或关键词>：列出端点
- 详情 <端点>：查看参数与坑点
- 采集 <端点> [key=value ...]：立即采集
- 总览：查看能力统计

示例：
- 能力 github
- 详情 tikhub_reddit_search
- 采集 tikhub_reddit_search keyword=AI max_items=5

提示：端点名可在「能力」结果中复制。采集会消耗上游额度。
"""

_PLATFORM_HINTS = {"平台", "平台列表", "platform", "platforms"}
_CAPABILITY_HINTS = {"/能力", "能力", "端点", "capability", "capabilities"}
_DESCRIBE_HINTS = {"详情", "说明", "describe"}
_COLLECT_HINTS = {"采集", "抓取", "收集", "collect", "run"}
_STATUS_HINTS = {"总览", "状态", "overview", "status"}
_HELP_HINTS = {"帮助", "菜单", "help", "你好", "hi", "hello", "?"}

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


def clean_text(text: str) -> str:
    return _MENTION_PATTERN.sub("", text).strip()


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
    if head in {h.casefold() for h in _PLATFORM_HINTS}:
        return Command("platforms", " ".join(rest).strip())
    if head in {h.casefold() for h in _CAPABILITY_HINTS}:
        return Command("capabilities", " ".join(rest).strip())
    if head in {h.casefold() for h in _DESCRIBE_HINTS}:
        return Command("describe", rest[0] if rest else "")
    if head in {h.casefold() for h in _COLLECT_HINTS}:
        if not rest:
            return Command("collect_error", "缺少端点名")
        try:
            params = parse_params(rest[1:])
        except ValueError as exc:
            return Command("collect_error", str(exc))
        return Command("collect", rest[0], params)

    return Command("unknown", cleaned)


async def execute(command: Command) -> Reply:
    if command.name == "help":
        return Reply(HELP_TEXT)
    if command.name == "status":
        return Reply(await capabilities.overview_text())
    if command.name == "platforms":
        return Reply(await capabilities.platforms_text(command.argument))
    if command.name == "capabilities":
        return Reply(await capabilities.capabilities_text(command.argument))
    if command.name == "describe":
        if not command.argument:
            return Reply("用法：详情 <端点名>")
        return Reply(await capabilities.describe_text(command.argument))
    if command.name == "collect_error":
        return Reply(f"命令格式有误：{command.argument}\n\n{HELP_TEXT}")
    if command.name == "collect":
        outcome = await capabilities.collect(command.argument, command.params)
        return Reply(outcome.text, ack=f"正在采集 {command.argument}，请稍候…")
    if command.name == "unknown":
        return Reply(
            "我没有识别这条指令。可以试试：\n"
            "- 平台\n"
            "- 能力 <关键词>\n"
            "- 采集 <端点> key=value\n\n"
            + HELP_TEXT
        )
    return Reply(HELP_TEXT)
