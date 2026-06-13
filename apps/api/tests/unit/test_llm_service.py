from __future__ import annotations

import pytest

from data_intelligence_hub.services.llm_service import LLMService


class InvalidSchemaAdapter:
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        return '{"title": ["not", "a", "string"], "summary": "valid"}'


class InvalidJsonAdapter:
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        return "not json"


@pytest.mark.asyncio
async def test_mock_llm_summary_is_evidence_bounded() -> None:
    copy = await LLMService().summarize_intelligence(
        {
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
    )

    assert copy.title == "Scrapy is showing accelerated traction"
    assert "metric=stars" in copy.summary
    assert "backed by 4 evidence records" in copy.summary


@pytest.mark.asyncio
async def test_llm_service_rejects_invalid_copy_schema() -> None:
    with pytest.raises(TypeError, match="invalid intelligence copy"):
        await LLMService(InvalidSchemaAdapter()).summarize_intelligence({})


@pytest.mark.asyncio
async def test_llm_service_rejects_invalid_json() -> None:
    with pytest.raises(TypeError, match="invalid intelligence copy"):
        await LLMService(InvalidJsonAdapter()).summarize_intelligence({})
