"""Nowledge Mem 读侧 recall（SOP 第 6.2 节，KG-08）。

从本项目的 source-agent 空间检索与查询强相关的持久口径、红线与避坑经验。
生命线原则：3 秒超时 + 全捕获异常 + 默认关闭（NMEM_RECALL=1 门控），
任何失败静默返回空串，绝不阻塞主链路。
"""
from __future__ import annotations

import json
import os
import subprocess

DEFAULT_SPACE = "source-agent"
DEFAULT_LIMIT = 2
DEFAULT_MIN_SCORE = 0.5
TIMEOUT_SECONDS = 3


def recall_durable_memories(
    query: str,
    limit: int = DEFAULT_LIMIT,
    min_score: float = DEFAULT_MIN_SCORE,
    space: str = DEFAULT_SPACE,
) -> str:
    """检索 Nowledge Mem 与 query 相关的记忆；失败/关闭/无匹配一律返回空串。

    门控：环境变量 NMEM_RECALL=1 时才启用（默认关闭）。
    空间解析：NMEM_SPACE 覆盖默认 space 参数。
    """
    if not query or not query.strip():
        return ""
    if os.environ.get("NMEM_RECALL") != "1":
        return ""
    try:
        cli = os.environ.get("NMEM_CLI_PATH", "nmem")
        target_space = os.environ.get("NMEM_SPACE", space)
        cmd = [cli, "--json", "memories", "search", query.strip()[:100],
               "--space", target_space, "-n", str(limit)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        if res.returncode != 0:
            return ""
        data = json.loads(res.stdout)
        items = data.get("memories", []) if isinstance(data, dict) else data
        blocks = []
        for m in items or []:
            try:
                score = float(m.get("score") or 0.0)
            except (TypeError, ValueError):
                continue
            if score < min_score:
                continue
            title = (m.get("title") or "").strip()
            content = (m.get("content") or m.get("snippet") or "").strip()
            if title and content:
                blocks.append(f"• 【{title}】(匹配度 {score:.2f})\n{content}")
        if not blocks:
            return ""
        return "【Nowledge Mem 专属记忆检索（核心口径/红线/避坑经验）】\n" + "\n\n".join(blocks)
    except Exception:
        return ""
