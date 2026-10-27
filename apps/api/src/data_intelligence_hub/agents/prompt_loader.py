"""Agent 系统提示的加载与版本化的唯一入口。

提示词从 Python 常量抽成包内 Markdown 文件，目的是三件事：

1. 提示词可单独评审、单独回滚。以前改一句话混在代码 diff 里，
   看不出来是"改行为"还是"改实现"。
2. 口径数字不再写死在提示词里。模板用 {{platform_count}} 这类占位符，
   运行时从 catalog 注入，避免锁文件更新后 Agent 继续对用户说旧数字。
3. 文件内容有稳定 sha256，供 Agent 台账（registry.yaml）核对：
   提示词被改动但没重新登记时，校验脚本能发现。

读取方式沿用 platform_packages/notes 的先例：包内目录 + pathlib 定位。
文件缺失时不抛异常，回退到调用方提供的默认文本，保证 Agent 不会因为
一次部署遗漏就整条链路不可用。
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

# 只认双花括号，避免提示词正文里的 JSON 示例（{"action": ...}）被误当占位符。
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z_][a-z0-9_]*)\}\}")


def prompt_path(agent_id: str, name: str = "system") -> Path:
    """返回 <agent 包>/prompts/<name>.md 的绝对路径。"""
    agent_dir = Path(__file__).resolve().parent / agent_id
    return agent_dir / "prompts" / f"{name}.md"


def load_prompt(
    agent_id: str,
    *,
    name: str = "system",
    values: Mapping[str, object] | None = None,
    default: str | None = None,
) -> str | None:
    """读取提示词模板并替换占位符。

    values 里缺少的占位符保持原样，便于在测试和日志里看出"该注入没注入"，
    而不是悄悄变成空字符串。
    """
    path = prompt_path(agent_id, name)
    try:
        template = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if default is not None:
            logger.warning("agent_prompt_missing: %s，回退到内置文本", path)
        return default
    except OSError as exc:  # noqa: BLE001 - 读不到提示词不能影响主链路
        logger.warning("agent_prompt_unreadable: %s (%s)", path, exc)
        return default

    return render_prompt(template, values or {})


def render_prompt(template: str, values: Mapping[str, object]) -> str:
    """替换 {{name}} 占位符；未提供值的保持原样。"""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        return str(values[key])

    return _PLACEHOLDER_RE.sub(_replace, template)


def prompt_sha256(agent_id: str, name: str = "system") -> str | None:
    """返回提示词文件的 sha256 十六进制摘要；文件不存在返回 None。

    台账校验用：registry.yaml 里登记 prompt_sha，与本函数结果比对。
    """
    path = prompt_path(agent_id, name)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def missing_placeholders(text: str) -> list[str]:
    """列出文本中尚未替换的占位符名，供测试断言使用。"""
    return sorted({m.group(1) for m in _PLACEHOLDER_RE.finditer(text)})
