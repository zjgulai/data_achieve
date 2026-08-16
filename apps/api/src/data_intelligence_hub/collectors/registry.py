from __future__ import annotations

from typing import Any

import httpx

from data_intelligence_hub.collectors.anysearch_collector import AnySearchCollector
from data_intelligence_hub.collectors.apify_actor import ApifyActorCollector
from data_intelligence_hub.collectors.base import BaseCollector, CollectorError
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.github_topic import GitHubTopicCollector
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector
from data_intelligence_hub.collectors.playwright_browser import PlaywrightBrowserCollector
from data_intelligence_hub.collectors.public_feed import PublicFeedCollector
from data_intelligence_hub.collectors.tikhub_social import TikHubSocialCollector

CollectorClass = type[BaseCollector]

COLLECTOR_REGISTRY: dict[str, CollectorClass] = {
    GitHubRepoCollector.collector_type: GitHubRepoCollector,
    GitHubTopicCollector.collector_type: GitHubTopicCollector,
    GenericWebCollector.collector_type: GenericWebCollector,
    ManualJsonCollector.collector_type: ManualJsonCollector,
    PublicFeedCollector.collector_type: PublicFeedCollector,
    EcommerceProductDiscoveryCollector.collector_type: EcommerceProductDiscoveryCollector,
    EcommerceProductPageCollector.collector_type: EcommerceProductPageCollector,
    TikHubSocialCollector.collector_type: TikHubSocialCollector,
    ApifyActorCollector.collector_type: ApifyActorCollector,
    PlaywrightBrowserCollector.collector_type: PlaywrightBrowserCollector,
    AnySearchCollector.collector_type: AnySearchCollector,
}


def build_collector(
    collector_type: str,
    config: dict[str, Any],
    http_client: httpx.AsyncClient | None = None,
) -> BaseCollector:
    collector_class = COLLECTOR_REGISTRY.get(collector_type)
    if collector_class is None:
        raise CollectorError(f"Collector is not registered: {collector_type}")
    return collector_class(config=config, http_client=http_client)
