"""工作区问答。

先检索工作区内的采集记录做摘录式回答与引用；本地证据不足时
（可选）调用 Exa /answer 补充外部回答。

本地打分是简单的词元重叠：够用、可解释、不依赖额外模型。
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.exa_collector import ExaAnswerCollector
from data_intelligence_hub.models.raw_record import RawRecord

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]+")
_MAX_RECORDS_SCANNED = 500
_SNIPPET_CHARS = 320


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text) if len(token) >= 2}


def _flatten_text(value: Any, *, limit: int = 4000) -> str:
    parts: list[str] = []

    def walk(node: Any) -> None:
        if len(" ".join(parts)) >= limit:
            return
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, (int, float)):
            parts.append(str(node))
        elif isinstance(node, dict):
            for item in node.values():
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
    allow_external: bool = True,
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
        score = len(query_tokens & _tokens(f"{text} {source_url or ''}"))
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

    local_answer: str | None = None
    if citations:
        local_answer = "\n\n".join(
            f"[{index}] {citation['snippet']}"
            for index, citation in enumerate(citations, start=1)
        )

    external: dict[str, Any] | None = None
    if allow_external and len(citations) < 2:
        external = await _exa_answer(query)

    return {
        "query": query,
        "answer": local_answer,
        "citations": citations,
        "external": external,
        "source": "workspace" if citations else ("exa" if external else "none"),
    }


async def _exa_answer(query: str) -> dict[str, Any] | None:
    collector = ExaAnswerCollector({"query": query})
    result = await collector.collect()
    if result.errors:
        return {"error": "; ".join(result.errors[:3])}
    if not result.raw_records:
        return None
    content = result.raw_records[0].content
    return {
        "answer": content.get("answer"),
        "citations": content.get("citations"),
        "request_id": content.get("request_id"),
    }