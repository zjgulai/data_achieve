from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class BaseLLMAdapter(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str: ...


class EvidenceDigestAdapter:
    """生产默认适配器：只按证据字段拼装中文摘要。

    这是确定性实现，不调用外部模型。它取代了此前默认的
    ``MockLLMAdapter``——那个适配器在生产路径上输出英文模板串
    （"Scrapy is showing accelerated traction"），让「洞察」这一步
    实际依赖 mock，违背了「全程不依赖 mock」的定义。

    为什么先不接真实 LLM：接入需要 key、成本与失败回退策略，
    是独立的产品决策。先用证据驱动的确定性摘要，能让链路诚实：
    标题与摘要都由真实 signal/evidence 字段构成，不含虚构事实。
    """

    async def generate(
        self, system_prompt: str, user_prompt: str, **kwargs: object
    ) -> str:
        del system_prompt, user_prompt  # 确定性实现不使用提示词
        context = kwargs.get("context")
        if not isinstance(context, dict):
            context = {}
        return json.dumps(
            {
                "title": _title_from_context_zh(context),
                "summary": _summary_from_context_zh(context),
            },
            ensure_ascii=False,
        )


class MockLLMAdapter:
    """测试用固定英文输出。**不得**作为生产默认值。

    保留它是因为历史测试断言了这些英文字符串；生产路径已改用
    :class:`EvidenceDigestAdapter`。
    """

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
        self._adapter = adapter or EvidenceDigestAdapter()

    async def summarize_intelligence(self, context: dict[str, Any]) -> IntelligenceCopy:
        payload = await self._adapter.generate(
            system_prompt="Generate concise intelligence copy from verified evidence only.",
            user_prompt="Summarize the signal and evidence without inventing facts.",
            context=context,
        )
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TypeError("LLM adapter returned invalid intelligence copy") from exc
        if not isinstance(decoded, dict):
            raise TypeError("LLM adapter returned invalid intelligence copy")
        title = decoded.get("title")
        summary = decoded.get("summary")
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


# ── 生产用中文摘要（EvidenceDigestAdapter） ──────────────────────────────
# 只按 context 里的证据字段拼装，不虚构任何事实。
# 字段缺失时用中性表述，不写 "unknown" 这类英文占位。

_SEVERITY_ZH = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重",
}

_INTELLIGENCE_TYPE_ZH = {
    "risk": "风险信号",
    "anomaly": "数据质量异常",
    "competitor": "竞品变化",
    "trend": "趋势加速",
}


def _title_from_context_zh(context: dict[str, Any]) -> str:
    entity_name = str(context.get("entity_name") or "").strip()
    intelligence_type = str(context.get("intelligence_type") or "")
    signal_type = str(context.get("signal_type") or "信号").strip()
    subject = entity_name or "该主体"

    if intelligence_type == "risk":
        return f"{subject} 出现高风险信号"
    if intelligence_type == "anomaly":
        return f"{subject} 存在数据质量异常"
    if intelligence_type == "competitor":
        return f"{subject} 页面出现实质变化"
    if intelligence_type == "trend":
        return f"{subject} 呈加速趋势"
    return f"{subject} 产生一条可跟进的{signal_type}信号"


def _summary_from_context_zh(context: dict[str, Any]) -> str:
    """把证据字段拼成中文摘要。只用已有的值，不做推断。"""
    parts: list[str] = []

    signal_type = str(context.get("signal_type") or "").strip()
    intelligence_type = str(context.get("intelligence_type") or "")
    type_label = _INTELLIGENCE_TYPE_ZH.get(intelligence_type)
    if type_label and signal_type:
        parts.append(f"信号类型为{signal_type}（{type_label}）")
    elif signal_type:
        parts.append(f"信号类型为{signal_type}")
    elif type_label:
        parts.append(f"归类为{type_label}")

    severity = context.get("severity")
    if isinstance(severity, str) and severity:
        parts.append(f"严重程度{_SEVERITY_ZH.get(severity, severity)}")

    metric = context.get("metric")
    delta = context.get("delta")
    if isinstance(metric, str) and metric:
        if delta is not None:
            parts.append(f"{metric} 变化 {delta}")
        else:
            parts.append(f"指标为 {metric}")
    elif delta is not None:
        parts.append(f"变化量 {delta}")

    delta_ratio = context.get("delta_ratio")
    if isinstance(delta_ratio, (int, float)):
        parts.append(f"变化率 {delta_ratio:.2%}")

    evidence_count = context.get("evidence_count")
    if isinstance(evidence_count, int) and evidence_count > 0:
        parts.append(f"结论由 {evidence_count} 条证据支撑")

    final_score = context.get("final_score")
    if isinstance(final_score, (int, float)):
        parts.append(f"综合评分 {final_score:.2f}")

    if not parts:
        return "该条目暂无足够证据字段可用于生成摘要。"
    return "；".join(parts) + "。"
