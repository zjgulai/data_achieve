from __future__ import annotations

from typing import Any

import httpx

from data_intelligence_hub.collectors.exa_collector import (
    ExaAnswerCollector,
    ExaContentsCollector,
    ExaFindSimilarCollector,
    ExaSearchCollector,
)
from data_intelligence_hub.collectors.anycrawl_collector import (
    BaiduSearchCollector,
    BingSearchCollector,
    DuckDuckGoSearchCollector,
)
from data_intelligence_hub.collectors.anydoc_collector import AnydocCollector
from data_intelligence_hub.collectors.anysearch_collector import AnySearchCollector
from data_intelligence_hub.collectors.apify_actor import ApifyActorCollector
from data_intelligence_hub.collectors.autoscraper_collector import (
    AutoScraperEnhancedWebCollector,
)
from data_intelligence_hub.collectors.base import BaseCollector, CollectorError
from data_intelligence_hub.collectors.bestblogs_collector import BestBlogsArticlesCollector
from data_intelligence_hub.collectors.blackbird_collector import (
    BlackbirdEmailCollector,
    BlackbirdUsernameCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.aliens_eye_collector import (
    AliensEyeAdvancedCollector,
    AliensEyeBatchCollector,
    AliensEyeBasicCollector,
    AliensEyeCorrelateCollector,
    AliensEyeDomainCollector,
    AliensEyeRecurseCollector,
    AliensEyeSelfcheckCollector,
)
from data_intelligence_hub.collectors.browser_use_collector import BrowserUseCollector
from data_intelligence_hub.collectors.robin_collector import (
    RobinEmailCollector,
    RobinKeywordCollector,
    RobinUsernameCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
from data_intelligence_hub.collectors.firecrawl_collector import (
    FirecrawlBatchScrapeCollector,
    FirecrawlCrawlCollector,
    FirecrawlExtractCollector,
)
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.github_topic import GitHubTopicCollector
from data_intelligence_hub.collectors.jina_reader import JinaReaderCollector
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector
from data_intelligence_hub.collectors.mediacrawler_collector import (
    BilibiliUserVideosCollector,
    BilibiliVideoCommentsCollector,
    BilibiliVideoSearchCollector,
    KuaishouUserVideosCollector,
    KuaishouVideoSearchCollector,
    WeiboKeywordSearchCollector,
    WeiboTrendingTopicsCollector,
    WeiboUserPostsCollector,
    ZhihuHotListCollector,
    ZhihuKeywordSearchCollector,
    ZhihuQuestionAnswersCollector,
)
from data_intelligence_hub.collectors.osint_collector import MaigretCollector, SherlockCollector
from data_intelligence_hub.collectors.playwright_browser import PlaywrightBrowserCollector
from data_intelligence_hub.collectors.public_feed import PublicFeedCollector
from data_intelligence_hub.collectors.spiderfoot_collector import (
    SpiderFootDomainCollector,
    SpiderFootEmailCollector,
    SpiderFootIPCollector,
)
from data_intelligence_hub.collectors.spiderfoot_extended_collectors import (
    SpiderFootAttackSurfaceCollector,
    SpiderFootBreachCollector,
    SpiderFootCertCollector,
    SpiderFootDarkWebCollector,
    SpiderFootSubdomainCollector,
    SpiderFootThreatIntelCollector,
)
from data_intelligence_hub.collectors.tech_blog_collector import (
    DevToArticlesCollector,
    JuejinArticlesCollector,
    SubstackPostsCollector,
)
from data_intelligence_hub.collectors.tikhub_social import TikHubSocialCollector
from data_intelligence_hub.collectors.twscrape_collector import (
    TwscrapeSearchCollector,
    TwscrapeTrendsCollector,
    TwscrapeUserTweetsCollector,
)
from data_intelligence_hub.collectors.wappalyzer_collector import TechStackDetectCollector
from data_intelligence_hub.collectors.hackernews_collector import (
    HackerNewsFrontPageCollector,
    HackerNewsSearchCollector,
    HackerNewsUserCollector,
)
from data_intelligence_hub.collectors.package_registry_collector import (
    NpmPackageCollector,
    NpmSearchCollector,
    PyPIPackageCollector,
    PyPISearchCollector,
)
from data_intelligence_hub.collectors.pkg_community_collector import (
    CratesIoPackageCollector,
    CratesIoSearchCollector,
    RubyGemsPackageCollector,
    RubyGemsSearchCollector,
    GoPackageCollector,
    GoSearchCollector,
)
from data_intelligence_hub.collectors.pkg_registry2_collector import (
    PackagistPackageCollector,
    PackagistSearchCollector,
    NuGetPackageCollector,
    NuGetSearchCollector,
    PubDevPackageCollector,
    PubDevSearchCollector,
)

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
    JinaReaderCollector.collector_type: JinaReaderCollector,
    SherlockCollector.collector_type: SherlockCollector,
    MaigretCollector.collector_type: MaigretCollector,
    TwscrapeSearchCollector.collector_type: TwscrapeSearchCollector,
    TwscrapeUserTweetsCollector.collector_type: TwscrapeUserTweetsCollector,
    TwscrapeTrendsCollector.collector_type: TwscrapeTrendsCollector,
    AnydocCollector.collector_type: AnydocCollector,
    BilibiliVideoSearchCollector.collector_type: BilibiliVideoSearchCollector,
    BilibiliUserVideosCollector.collector_type: BilibiliUserVideosCollector,
    BilibiliVideoCommentsCollector.collector_type: BilibiliVideoCommentsCollector,
    WeiboKeywordSearchCollector.collector_type: WeiboKeywordSearchCollector,
    WeiboUserPostsCollector.collector_type: WeiboUserPostsCollector,
    WeiboTrendingTopicsCollector.collector_type: WeiboTrendingTopicsCollector,
    ZhihuQuestionAnswersCollector.collector_type: ZhihuQuestionAnswersCollector,
    ZhihuKeywordSearchCollector.collector_type: ZhihuKeywordSearchCollector,
    ZhihuHotListCollector.collector_type: ZhihuHotListCollector,
    BaiduSearchCollector.collector_type: BaiduSearchCollector,
    BingSearchCollector.collector_type: BingSearchCollector,
    DuckDuckGoSearchCollector.collector_type: DuckDuckGoSearchCollector,
    KuaishouVideoSearchCollector.collector_type: KuaishouVideoSearchCollector,
    KuaishouUserVideosCollector.collector_type: KuaishouUserVideosCollector,
    FirecrawlCrawlCollector.collector_type: FirecrawlCrawlCollector,
    FirecrawlExtractCollector.collector_type: FirecrawlExtractCollector,
    FirecrawlBatchScrapeCollector.collector_type: FirecrawlBatchScrapeCollector,
    DevToArticlesCollector.collector_type: DevToArticlesCollector,
    JuejinArticlesCollector.collector_type: JuejinArticlesCollector,
    SubstackPostsCollector.collector_type: SubstackPostsCollector,
    TechStackDetectCollector.collector_type: TechStackDetectCollector,
    SpiderFootDomainCollector.collector_type: SpiderFootDomainCollector,
    SpiderFootIPCollector.collector_type: SpiderFootIPCollector,
    SpiderFootEmailCollector.collector_type: SpiderFootEmailCollector,
    SpiderFootSubdomainCollector.collector_type: SpiderFootSubdomainCollector,
    SpiderFootThreatIntelCollector.collector_type: SpiderFootThreatIntelCollector,
    SpiderFootBreachCollector.collector_type: SpiderFootBreachCollector,
    SpiderFootCertCollector.collector_type: SpiderFootCertCollector,
    SpiderFootDarkWebCollector.collector_type: SpiderFootDarkWebCollector,
    SpiderFootAttackSurfaceCollector.collector_type: SpiderFootAttackSurfaceCollector,
    BestBlogsArticlesCollector.collector_type: BestBlogsArticlesCollector,
    BlackbirdEmailCollector.collector_type: BlackbirdEmailCollector,
    BlackbirdUsernameCollector.collector_type: BlackbirdUsernameCollector,
    AutoScraperEnhancedWebCollector.collector_type: AutoScraperEnhancedWebCollector,
    AliensEyeBasicCollector.collector_type: AliensEyeBasicCollector,
    AliensEyeAdvancedCollector.collector_type: AliensEyeAdvancedCollector,
    AliensEyeCorrelateCollector.collector_type: AliensEyeCorrelateCollector,
    AliensEyeRecurseCollector.collector_type: AliensEyeRecurseCollector,
    AliensEyeDomainCollector.collector_type: AliensEyeDomainCollector,
    AliensEyeBatchCollector.collector_type: AliensEyeBatchCollector,
    AliensEyeSelfcheckCollector.collector_type: AliensEyeSelfcheckCollector,
    RobinKeywordCollector.collector_type: RobinKeywordCollector,
    RobinUsernameCollector.collector_type: RobinUsernameCollector,
    RobinEmailCollector.collector_type: RobinEmailCollector,
    BrowserUseCollector.collector_type: BrowserUseCollector,
    HackerNewsFrontPageCollector.collector_type: HackerNewsFrontPageCollector,
    HackerNewsSearchCollector.collector_type: HackerNewsSearchCollector,
    HackerNewsUserCollector.collector_type: HackerNewsUserCollector,
    NpmPackageCollector.collector_type: NpmPackageCollector,
    NpmSearchCollector.collector_type: NpmSearchCollector,
    PyPIPackageCollector.collector_type: PyPIPackageCollector,
    PyPISearchCollector.collector_type: PyPISearchCollector,
    CratesIoPackageCollector.collector_type: CratesIoPackageCollector,
    CratesIoSearchCollector.collector_type: CratesIoSearchCollector,
    RubyGemsPackageCollector.collector_type: RubyGemsPackageCollector,
    RubyGemsSearchCollector.collector_type: RubyGemsSearchCollector,
    GoPackageCollector.collector_type: GoPackageCollector,
    GoSearchCollector.collector_type: GoSearchCollector,
    PackagistPackageCollector.collector_type: PackagistPackageCollector,
    PackagistSearchCollector.collector_type: PackagistSearchCollector,
    NuGetPackageCollector.collector_type: NuGetPackageCollector,
    NuGetSearchCollector.collector_type: NuGetSearchCollector,
    PubDevPackageCollector.collector_type: PubDevPackageCollector,
    PubDevSearchCollector.collector_type: PubDevSearchCollector,
    ExaSearchCollector.collector_type: ExaSearchCollector,
    ExaFindSimilarCollector.collector_type: ExaFindSimilarCollector,
    ExaContentsCollector.collector_type: ExaContentsCollector,
    ExaAnswerCollector.collector_type: ExaAnswerCollector,
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
