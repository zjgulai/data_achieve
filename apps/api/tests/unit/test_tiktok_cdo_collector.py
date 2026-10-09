from __future__ import annotations

from data_intelligence_hub.agents.tiktok_cdo.collector_client import build_collect_request
from data_intelligence_hub.agents.tiktok_cdo.models import TikTokIntent


def test_sentiment_uses_exa_collector_boundary() -> None:
    request = build_collect_request(TikTokIntent(action="sentiment", keyword="小米", limit=5))
    assert request["project_id"] == "7fd6ed55-7b0c-5482-92f3-d03130168b70"
    assert request["endpoint_type"] == "exa_search_news"
    assert request["params"] == {"query": "TikTok 小米 舆情 新闻", "num_results": 5}
