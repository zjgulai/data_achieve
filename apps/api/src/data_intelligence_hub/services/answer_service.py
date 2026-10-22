"""工作区问答。

只检索工作区内的采集记录，返回摘录与引用。外部 Exa 补充由 MCP ``answer``
或 REST 显式采集承担；本服务不绕过项目密钥白名单、额度与运行账本。
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.raw_record import RawRecord

_LATIN_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_RE = re.compile(r"[一-鿿]+")
_MAX_RECORDS_SCANNED = 2000
_SNIPPET_CHARS = 320


def _tokens(text: str) -> set[str]:
    """拉丁词 + CJK bigram。连续中文不能整体当一个词元。"""
    tokens = {token.lower() for token in _LATIN_RE.findall(text) if len(token) >= 2}
    for segment in _CJK_RE.findall(text):
        if len(segment) == 1:
            tokens.add(segment)
        else:
            tokens.update(segment[index : index + 2] for index in range(len(segment) - 1))
    return tokens


def _flatten_text(value: Any, *, limit: int = 4000) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if sum(len(item) for item in parts) >= limit:
            return
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, (int, float)):
            parts.append(str(node))
        elif isinstance(node, dict):
            # 优先内容字段，避免 request_id/provider 等元数据淹没证据正文。
            preferred = (
                "title",
                "text",
                "summary",
                "answer",
                "highlights",
                "description",
                "snippet",
                "structured_output",
            )
            seen: set[str] = set()
            for key in preferred:
                if key in node:
                    walk(node[key])
                    seen.add(key)
            for key, item in node.items():
                if key not in seen and key not in {
                    "request_id",
                    "provider",
                    "id",
                    "score",
                    "favicon",
                    "image",
                    "highlight_scores",
                }:
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return " ".join(parts)[:limit]


async def workspace_answer(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    statement = (
        select(
            RawRecord.id,
            RawRecord.source_url,
            RawRecord.record_type,
            RawRecord.content,
            RawRecord.collected_at,
        )
        .where(RawRecord.workspace_id == workspace_id)
        .order_by(RawRecord.collected_at.desc())
        .limit(_MAX_RECORDS_SCANNED)
    )
    if project_id is not None:
        statement = statement.where(RawRecord.project_id == project_id)
    rows = (await session.execute(statement)).all()

    query_tokens = _tokens(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for record_id, source_url, record_type, content, collected_at in rows:
        text = _flatten_text(content)
        score = len(query_tokens & _tokens(text))
        if score <= 0:
            continue
        scored.append(
            (
                score,
                {
                    "record_id": str(record_id),
                    "record_type": record_type,
                    "source_url": source_url,
                    "snippet": text[:_SNIPPET_CHARS],
                    "collected_at": collected_at.isoformat() if collected_at else None,
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    citations = [item for _, item in scored[: max(1, min(limit, 20))]]

    answer: str | None = None
    if citations:
        answer = "\n\n".join(
            f"[{index}] {citation['snippet']}"
            for index, citation in enumerate(citations, start=1)
        )

    return {
        "query": query,
        "answer": answer,
        "citations": citations,
        "source": "workspace" if citations else "none",
    }
