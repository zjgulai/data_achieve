from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class BaseLLMAdapter(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        ...


class MockLLMAdapter:
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        context = kwargs.get("context")
        if not isinstance(context, dict):
            return json.dumps({"title": "Generated intelligence", "summary": user_prompt})
        return json.dumps(
            {
                "title": _title_from_context(context),
                "summary": _summary_from_context(context),
            }
        )


@dataclass(frozen=True)
class IntelligenceCopy:
    title: str
    summary: str


class LLMService:
    def __init__(self, adapter: BaseLLMAdapter | None = None) -> None:
        self._adapter = adapter or MockLLMAdapter()

    async def summarize_intelligence(self, context: dict[str, Any]) -> IntelligenceCopy:
        payload = await self._adapter.generate(
            system_prompt="Generate concise intelligence copy from verified evidence only.",
            user_prompt="Summarize the signal and evidence without inventing facts.",
            context=context,
        )
        decoded = json.loads(payload)
        title = decoded["title"]
        summary = decoded["summary"]
        if not isinstance(title, str) or not isinstance(summary, str):
            raise TypeError("LLM adapter returned invalid intelligence copy")
        return IntelligenceCopy(title=title, summary=summary)


def _title_from_context(context: dict[str, Any]) -> str:
    signal_type = str(context.get("signal_type", "signal"))
    entity_name = str(context.get("entity_name", "entity"))
    intelligence_type = str(context.get("intelligence_type", "intelligence"))
    if intelligence_type == "risk":
        return f"{entity_name} raised a high-severity risk signal"
    if intelligence_type == "anomaly":
        return f"{entity_name} has a data quality anomaly"
    if intelligence_type == "competitor":
        return f"{entity_name} page changed materially"
    if intelligence_type == "trend":
        return f"{entity_name} is showing accelerated traction"
    return f"{entity_name} produced an actionable {signal_type} signal"


def _summary_from_context(context: dict[str, Any]) -> str:
    signal_type = str(context.get("signal_type", "signal"))
    severity = str(context.get("severity", "low"))
    final_score = float(context.get("final_score", 0.0))
    evidence_count = int(context.get("evidence_count", 0))
    delta = context.get("delta")
    delta_ratio = context.get("delta_ratio")
    metric = context.get("metric")
    metric_text = f" metric={metric}" if isinstance(metric, str) else ""
    return (
        f"{signal_type}{metric_text} was detected with severity={severity}. "
        f"delta={delta}, delta_ratio={delta_ratio}, final_score={final_score:.2f}. "
        f"The conclusion is backed by {evidence_count} evidence records."
    )
