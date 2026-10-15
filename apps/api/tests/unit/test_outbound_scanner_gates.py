"""Do not invoke any scanner while checking its policy boundary."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.core.config import get_settings

RISKY_TYPES = [
    "aliens_eye_basic",
    "aliens_eye_advanced",
    "aliens_eye_correlate",
    "aliens_eye_recurse",
    "aliens_eye_domain",
    "aliens_eye_batch",
    "aliens_eye_selfcheck",
    "sherlock",
    "maigret",
    "blackbird_email_osint",
    "blackbird_username_osint",
    "spiderfoot_domain_osint",
    "spiderfoot_subdomain_enum",
    "spiderfoot_dark_web",
    "robin_darkweb_search",
    "robin_darkweb_username",
    "robin_darkweb_email",
    "browser_use_task",
    "playwright_browser",
    "autoscraper_enhanced_web",
    "tech_stack_detect",
    "anydoc_file_to_markdown",
    "spiderfoot_ip_osint",
    "spiderfoot_email_osint",
    "spiderfoot_threat_intel",
    "spiderfoot_breach_check",
    "spiderfoot_cert_transparency",
    "spiderfoot_attack_surface",
    "firecrawl_crawl",
    "firecrawl_extract",
    "firecrawl_batch_scrape",
    "jina_reader",
    "bestblogs_articles",
    "devto_articles",
    "juejin_articles",
    "substack_posts",
    "twscrape_search",
    "twscrape_user_tweets",
    "twscrape_trends",
    "baidu_search",
    "bing_search",
    "duckduckgo_search",
    "bilibili_video_search",
    "bilibili_user_videos",
    "bilibili_video_comments",
    "weibo_keyword_search",
    "weibo_user_posts",
    "weibo_trending_topics",
    "zhihu_question_answers",
    "zhihu_keyword_search",
    "zhihu_hot_list",
    "kuaishou_video_search",
    "kuaishou_user_videos",
]


@pytest.fixture(autouse=True)
def forbid_real_activity(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("an unsupported collector attempted external activity")

    import socket

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(side_effect=forbidden))
    monkeypatch.setattr(httpx.AsyncClient, "request", AsyncMock(side_effect=forbidden))
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("collector_type", RISKY_TYPES)
@pytest.mark.parametrize("operation", ["collect", "test"])
@pytest.mark.asyncio
async def test_direct_collector_calls_are_denied(collector_type: str, operation: str) -> None:
    collector = COLLECTOR_REGISTRY[collector_type](
        {
            "username": "nobody",
            "usernames": ["nobody"],
            "keyword": "example",
            "email": "test@example.com",
            "domain": "example.com",
            "target": "example.com",
            "url": "https://example.com",
            "file_url": "https://example.com/file.txt",
            "task": "read example.com",
            "sites": ["GitHub"],
            "approved": True,
        }
    )
    with pytest.raises(CollectorError, match="collection_policy_denied"):
        await getattr(collector, operation)()
