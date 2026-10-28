from __future__ import annotations

import pytest

from data_intelligence_hub.services.llm_service import (
    EvidenceDigestAdapter,
    LLMService,
    MockLLMAdapter,
)


class InvalidSchemaAdapter:
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        return '{"title": ["not", "a", "string"], "summary": "valid"}'


class InvalidJsonAdapter:
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        return "not json"


CONTEXT = {
    "entity_name": "Scrapy",
    "signal_type": "star_growth",
    "intelligence_type": "trend",
    "severity": "medium",
    "delta": 780,
    "delta_ratio": 0.014,
    "metric": "stars",
    "final_score": 82.4,
    "evidence_count": 4,
}


def test_default_adapter_is_not_the_mock() -> None:
    """生产默认适配器不得是 MockLLMAdapter。

    此前默认值是 MockLLMAdapter，导致生产路径上「洞察」的标题与摘要
    是英文模板串，「全程不依赖 mock」不成立。这条测试锁住默认值，
    防止有人无意中改回去。
    """
    service = LLMService()
    assert isinstance(service._adapter, EvidenceDigestAdapter)  # noqa: SLF001


@pytest.mark.asyncio
async def test_default_summary_is_chinese_and_evidence_bounded() -> None:
    copy = await LLMService().summarize_intelligence(CONTEXT)

    assert copy.title == "Scrapy 呈加速趋势"
    # 摘要必须由真实字段构成。
    assert "star_growth" in copy.summary
    assert "780" in copy.summary
    assert "4 条证据" in copy.summary
    # 不得出现 mock 适配器的英文模板。
    assert "accelerated traction" not in copy.title
    assert "evidence records" not in copy.summary


@pytest.mark.asyncio
async def test_default_summary_handles_missing_fields() -> None:
    """字段缺失时用中性中文表述，不写英文占位。"""
    copy = await LLMService().summarize_intelligence({"entity_name": "小米"})

    assert copy.title == "小米 产生一条可跟进的信号信号"
    assert "unknown" not in copy.summary


@pytest.mark.asyncio
async def test_default_summary_without_any_context() -> None:
    """空 context 不能崩，也不能编造事实。"""
    copy = await LLMService().summarize_intelligence({})

    assert copy.title == "该主体 产生一条可跟进的信号信号"
    assert "暂无足够证据字段" in copy.summary


@pytest.mark.asyncio
async def test_mock_adapter_keeps_its_english_output_for_tests() -> None:
    """MockLLMAdapter 仍保留，供历史测试与对比使用。"""
    copy = await LLMService(MockLLMAdapter()).summarize_intelligence(CONTEXT)

    assert copy.title == "Scrapy is showing accelerated traction"
    assert "backed by 4 evidence records" in copy.summary


@pytest.mark.asyncio
async def test_llm_service_rejects_invalid_copy_schema() -> None:
    with pytest.raises(TypeError, match="invalid intelligence copy"):
        await LLMService(InvalidSchemaAdapter()).summarize_intelligence({})


@pytest.mark.asyncio
async def test_llm_service_rejects_invalid_json() -> None:
    with pytest.raises(TypeError, match="invalid intelligence copy"):
        await LLMService(InvalidJsonAdapter()).summarize_intelligence({})
