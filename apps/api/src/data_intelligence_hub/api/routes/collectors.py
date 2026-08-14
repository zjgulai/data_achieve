"""Collector routes: list registered collectors + platform capability catalog."""

from __future__ import annotations

from fastapi import APIRouter

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.repositories.collectors import list_collectors
from data_intelligence_hub.schemas.collector import CollectorResponse
from data_intelligence_hub.schemas.collector_catalog import (
    CollectorCatalogEntry,
    CollectorCatalogResponse,
    CollectorEndpointMetadata,
)
from data_intelligence_hub.services.collector_catalog import ensure_collectors_seeded

router = APIRouter(tags=["collectors"])


@router.get("", response_model=list[CollectorResponse])
async def list_collector_items(session: SessionDep) -> list[CollectorResponse]:
    await ensure_collectors_seeded(session)
    collectors = await list_collectors(session)
    return [CollectorResponse.model_validate(collector) for collector in collectors]


@router.get("/catalog", response_model=CollectorCatalogResponse)
async def get_collector_catalog() -> CollectorCatalogResponse:
    """Capability catalog: all registered collectors and their endpoints.

    Used by the Console /platforms page to render ability cards.
    """
    tikhub_endpoints = [
        CollectorEndpointMetadata(
            endpoint_type="tikhub_tiktok_video_search",
            label="TikTok 视频搜索",
            platform="tiktok",
            description="按关键词搜索 TikTok 公开视频，返回视频文案、互动数据和作者信息",
            status="verified",
            required_params=["keyword"],
            optional_params=["max_items", "cursor", "sort_type"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="tikhub_tiktok_user_posts",
            label="TikTok 账号视频",
            platform="tiktok",
            description="获取指定 TikTok 账号的公开视频列表",
            status="verified",
            required_params=["unique_id"],
            optional_params=["max_items", "max_cursor"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="tikhub_tiktok_hashtag_posts",
            label="TikTok 话题视频",
            platform="tiktok",
            description="获取指定话题下的 TikTok 视频列表",
            status="verified",
            required_params=["ch_id"],
            optional_params=["max_items", "cursor"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="tikhub_instagram_search",
            label="Instagram 关键词搜索",
            platform="instagram",
            description="按关键词搜索 Instagram 公开帖子，返回帖子内容和互动数据",
            status="verified",
            required_params=["keyword"],
            optional_params=["max_items"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="tikhub_instagram_user_posts",
            label="Instagram 账号帖子",
            platform="instagram",
            description="获取指定 Instagram 账号的公开帖子列表",
            status="pending",
            required_params=["user_id"],
            optional_params=["max_items", "max_id"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="tikhub_xiaohongshu_search",
            label="小红书笔记搜索",
            platform="xiaohongshu",
            description="按关键词搜索小红书公开笔记，返回笔记标题、内容和互动数据",
            status="verified",
            required_params=["keyword"],
            optional_params=["max_items", "sort_type"],
            cost_hint="~$0.001/条",
            provider="TikHub REST API",
        ),
    ]

    apify_endpoints = [
        CollectorEndpointMetadata(
            endpoint_type="apify_tiktok",
            label="TikTok Scraper",
            platform="tiktok",
            description="通过 Apify clockworks/tiktok-scraper 采集 TikTok 视频和评论",
            status="verified",
            required_params=["searchQueries"],
            optional_params=["resultsPerPage", "max_items", "max_total_charge_usd"],
            cost_hint="~$0.5/次起",
            provider="Apify Actor (clockworks/tiktok-scraper)",
        ),
        CollectorEndpointMetadata(
            endpoint_type="apify_instagram",
            label="Instagram Scraper",
            platform="instagram",
            description="通过 Apify apify/instagram-scraper 采集 Instagram 帖子",
            status="verified",
            required_params=["search"],
            optional_params=["resultsLimit", "resultsType", "max_items", "max_total_charge_usd"],
            cost_hint="按事件计费",
            provider="Apify Actor (apify/instagram-scraper)",
        ),
        CollectorEndpointMetadata(
            endpoint_type="apify_youtube_transcript",
            label="YouTube 字幕转录",
            platform="youtube",
            description="通过 Apify 提取 YouTube 视频字幕/转录文本",
            status="verified",
            required_params=["startUrls"],
            optional_params=["max_items", "max_total_charge_usd"],
            cost_hint="按事件计费",
            provider="Apify Actor (topaz_sharingan/youtube-transcript-scraper-1)",
        ),
    ]

    github_endpoints = [
        CollectorEndpointMetadata(
            endpoint_type="github_repo",
            label="GitHub 仓库监测",
            platform="github",
            description="监测 GitHub 仓库的 Stars、Fork、Issue、发布和 README",
            status="verified",
            required_params=["owner", "repo"],
            optional_params=[],
            cost_hint="免费",
            provider="GitHub REST API",
        ),
        CollectorEndpointMetadata(
            endpoint_type="github_topic",
            label="GitHub 话题发现",
            platform="github",
            description="按话题发现 GitHub 仓库，跟踪生态趋势",
            status="verified",
            required_params=["topic"],
            optional_params=["max_items"],
            cost_hint="免费",
            provider="GitHub REST API",
        ),
    ]

    rss_endpoints = [
        CollectorEndpointMetadata(
            endpoint_type="public_feed",
            label="RSS/Atom 订阅源",
            platform="rss",
            description="采集公开 RSS/Atom 订阅源的最新内容，支持 content-hash drift 检测",
            status="verified",
            required_params=["url"],
            optional_params=[],
            cost_hint="免费",
            provider="自研 HTTP Collector",
        ),
        CollectorEndpointMetadata(
            endpoint_type="generic_web",
            label="公开网页快照",
            platform="web",
            description="采集公开网页内容，生成 content-hash 用于变更检测",
            status="verified",
            required_params=["url"],
            optional_params=[],
            cost_hint="免费",
            provider="自研 HTTP Collector",
        ),
    ]

    return CollectorCatalogResponse(
        collectors=[
            CollectorCatalogEntry(
                collector_type="tikhub_social",
                label="TikHub Social",
                platform="tikhub",
                endpoints=tikhub_endpoints,
            ),
            CollectorCatalogEntry(
                collector_type="apify_actor",
                label="Apify Actors",
                platform="apify",
                endpoints=apify_endpoints,
            ),
            CollectorCatalogEntry(
                collector_type="github",
                label="GitHub",
                platform="github",
                endpoints=github_endpoints,
            ),
            CollectorCatalogEntry(
                collector_type="rss_web",
                label="RSS / 公开网页",
                platform="web",
                endpoints=rss_endpoints,
            ),
        ]
    )
