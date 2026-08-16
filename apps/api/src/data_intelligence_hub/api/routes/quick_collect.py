"""One-click quick collect: create ephemeral Source + Task, run immediately."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.repositories.collectors import get_collector_by_type
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.services.collector_catalog import (
    ensure_collectors_seeded,
    validate_collector_config,
)
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import (
    CollectorConfigError,
    CollectorNotFoundError,
)

router = APIRouter(tags=["quick-collect"])

_ENDPOINT_TO_COLLECTOR: dict[str, str] = {
    # TikHub Social (12 endpoints)
    "tikhub_tiktok_video_search": "tikhub_social",
    "tikhub_tiktok_user_posts": "tikhub_social",
    "tikhub_tiktok_hashtag_posts": "tikhub_social",
    "tikhub_instagram_search": "tikhub_social",
    "tikhub_instagram_user_posts": "tikhub_social",
    "tikhub_xiaohongshu_search": "tikhub_social",
    "tikhub_youtube_video_search": "tikhub_social",
    "tikhub_youtube_search": "tikhub_social",
    "tikhub_youtube_channel_videos": "tikhub_social",
    "tikhub_reddit_search": "tikhub_social",
    "tikhub_reddit_subreddit_posts": "tikhub_social",
    "tikhub_x_search": "tikhub_social",
    "tikhub_x_user_tweets": "tikhub_social",
    "tikhub_threads_search": "tikhub_social",
    "tikhub_threads_user_posts": "tikhub_social",
    "tikhub_threads_post_comments": "tikhub_social",
    "tikhub_linkedin_user_posts": "tikhub_social",
    "tikhub_linkedin_company_profile": "tikhub_social",
    "tikhub_linkedin_company_posts": "tikhub_social",
    "tikhub_linkedin_search_jobs": "tikhub_social",
    "tikhub_linkedin_job_detail": "tikhub_social",
    "tikhub_linkedin_post_comments": "tikhub_social",
    "tikhub_lemon8_search": "tikhub_social",
    "tikhub_lemon8_user_posts": "tikhub_social",
    "tikhub_lemon8_trending": "tikhub_social",
    "tikhub_tiktok_ads_search": "tikhub_social",
    "tikhub_tiktok_top_ads": "tikhub_social",
    "tikhub_tiktok_shop_products": "tikhub_social",
    "tikhub_tiktok_creator_info": "tikhub_social",
    "tikhub_instagram_post_comments": "tikhub_social",
    "tikhub_youtube_video_comments": "tikhub_social",
    "tikhub_reddit_post_comments": "tikhub_social",
    "tikhub_tiktok_live_search": "tikhub_social",
    "tikhub_tiktok_live_room_detail": "tikhub_social",
    "tikhub_tiktok_live_user": "tikhub_social",
    "tikhub_youtube_trending": "tikhub_social",
    "tikhub_reddit_trending": "tikhub_social",
    "tikhub_x_trending": "tikhub_social",
    "tikhub_tiktok_user_followers": "tikhub_social",
    "tikhub_instagram_user_followers": "tikhub_social",
    "tikhub_x_user_followers": "tikhub_social",
    "tikhub_tiktok_creator_insights": "tikhub_social",
    "tikhub_tiktok_creator_insights_trend": "tikhub_social",
    "tikhub_tiktok_creator_account_health": "tikhub_social",
    "tikhub_tiktok_ads_detail": "tikhub_social",
    "tikhub_tiktok_ads_keyword_suggest": "tikhub_social",
    # Apify Social (18 endpoints)
    "apify_tiktok": "apify_actor",
    "apify_tiktok_scraper": "apify_actor",
    "apify_tiktok_comments_scraper": "apify_actor",
    "apify_tiktok_shop_scraper": "apify_actor",
    "apify_instagram": "apify_actor",
    "apify_instagram_scraper": "apify_actor",
    "apify_instagram_profile_scraper": "apify_actor",
    "apify_instagram_hashtag_scraper": "apify_actor",
    "apify_youtube": "apify_actor",
    "apify_youtube_scraper": "apify_actor",
    "apify_youtube_comments_scraper": "apify_actor",
    "apify_youtube_comment_scraper": "apify_actor",
    "apify_reddit_scraper": "apify_actor",
    "apify_reddit_community_monitor": "apify_actor",
    "apify_facebook_posts_scraper": "apify_actor",
    "apify_facebook_comments_scraper": "apify_actor",
    "apify_linkedin_profile_scraper": "apify_actor",
    "apify_linkedin_company_scraper": "apify_actor",
    "apify_linkedin_company_posts_scraper": "apify_actor",
    "apify_linkedin_jobs_scraper": "apify_actor",
    "apify_linkedin_company_employees_scraper": "apify_actor",
    "apify_linkedin_company_search_scraper": "apify_actor",
    "apify_x_scraper": "apify_actor",
    "apify_x_tweet_scraper": "apify_actor",
    "apify_threads_scraper": "apify_actor",
    "apify_threads_profile_scraper": "apify_actor",
    "apify_threads_posts_scraper": "apify_actor",
    "apify_pinterest_scraper": "apify_actor",
    "apify_snapchat_profile_scraper": "apify_actor",
    "apify_snapchat_scraper": "apify_actor",
    # Apify E-commerce (13 endpoints)
    "apify_amazon_product_scraper": "apify_actor",
    "apify_amazon_review_scraper": "apify_actor",
    "apify_amazon_reviews_scraper": "apify_actor",
    "apify_walmart_scraper": "apify_actor",
    "apify_walmart_product_scraper": "apify_actor",
    "apify_walmart_reviews_scraper": "apify_actor",
    "apify_temu_products_scraper": "apify_actor",
    "apify_shein_product_scraper": "apify_actor",
    "apify_aliexpress_products_scraper": "apify_actor",
    "apify_ebay_scraper": "apify_actor",
    "apify_ebay_product_scraper": "apify_actor",
    "apify_ebay_sold_listings_scraper": "apify_actor",
    "apify_etsy_scraper": "apify_actor",
    "apify_shopify_scraper": "apify_actor",
    # Apify Google (8 endpoints)
    "apify_google_search_scraper": "apify_actor",
    "apify_google_maps_scraper": "apify_actor",
    "apify_google_maps_reviews_scraper": "apify_actor",
    "apify_google_trends_scraper": "apify_actor",
    "apify_google_shopping_scraper": "apify_actor",
    "apify_google_play_scraper": "apify_actor",
    "apify_google_news_media_search": "apify_actor",
    "apify_google_news_scraper": "apify_actor",
    "apify_google_ai_overviews_scraper": "apify_actor",
    # Apify AI Search (6 endpoints)
    "apify_perplexity_scraper": "apify_actor",
    "apify_perplexity_search_scraper": "apify_actor",
    "apify_chatgpt_scraper": "apify_actor",
    "apify_chatgpt_search_scraper": "apify_actor",
    "apify_gemini_scraper": "apify_actor",
    "apify_gemini_search_scraper": "apify_actor",
    # Apify Ads (10 endpoints)
    "apify_google_ads_transparency_scraper": "apify_actor",
    "apify_google_ads_scraper": "apify_actor",
    "apify_meta_ads_library_scraper": "apify_actor",
    "apify_facebook_ads_scraper": "apify_actor",
    "apify_tiktok_ads_library_scraper": "apify_actor",
    "apify_tiktok_ads_scraper": "apify_actor",
    "apify_linkedin_ads_scraper": "apify_actor",
    "apify_reddit_ads_scraper": "apify_actor",
    "apify_x_ads_transparency_scraper": "apify_actor",
    "apify_pinterest_ads_scraper": "apify_actor",
    "apify_snapchat_ads_scraper": "apify_actor",
    # Apify B2B (13 endpoints)
    "apify_trustpilot_scraper": "apify_actor",
    "apify_trustpilot_reviews_scraper": "apify_actor",
    "apify_appstore_scraper": "apify_actor",
    "apify_appstore_reviews_scraper": "apify_actor",
    "apify_google_play_reviews_scraper": "apify_actor",
    "apify_tripadvisor_scraper": "apify_actor",
    "apify_tripadvisor_reviews_scraper": "apify_actor",
    "apify_yelp_scraper": "apify_actor",
    "apify_booking_scraper": "apify_actor",
    "apify_airbnb_scraper": "apify_actor",
    "apify_crunchbase_scraper": "apify_actor",
    "apify_producthunt_scraper": "apify_actor",
    "apify_product_hunt_scraper": "apify_actor",
    "apify_glassdoor_scraper": "apify_actor",
    "apify_hacker_news_scraper": "apify_actor",
    "apify_bluesky_scraper": "apify_actor",
    "apify_telegram_scraper": "apify_actor",
    "apify_indeed_scraper": "apify_actor",
    "apify_indeed_jobs_scraper": "apify_actor",
    # Apify Media (7 endpoints)
    "apify_instagram_media_profile_scraper": "apify_actor",
    "apify_tiktok_media_profile_scraper": "apify_actor",
    "apify_youtube_media_channel_scraper": "apify_actor",
    "apify_facebook_media_page_scraper": "apify_actor",
    "apify_x_media_account_scraper": "apify_actor",
    "apify_pinterest_media_profile_scraper": "apify_actor",
    # Apify Open Web (3 endpoints)
    "apify_website_content_crawler": "apify_actor",
    "apify_web_scraper": "apify_actor",
    "apify_rag_web_browser": "apify_actor",
    "apify_tiktok_transcript_extractor": "apify_actor",
    "apify_youtube_transcript_scraper": "apify_actor",
    "apify_tiktok_creative_center": "apify_actor",
    "apify_facebook_group_scraper": "apify_actor",
    "apify_similarweb_scraper": "apify_actor",
    "apify_tiktok_shop_search_scraper": "apify_actor",
    "apify_target_products_scraper": "apify_actor",
    "apify_facebook_marketplace_scraper": "apify_actor",
    # GitHub (2 endpoints)
    "github_repo": "github_repo",
    "github_topic": "github_topic",
    # RSS / Web (2 endpoints)
    "public_feed": "public_feed",
    "generic_web": "generic_web",
    # Ecommerce Web (2 endpoints)
    "ecommerce_product_page": "ecommerce_product_page",
    "ecommerce_product_discovery": "ecommerce_product_discovery",
    # Browser (3 endpoints)
    "playwright_browser_text": "playwright_browser",
    "playwright_browser_html": "playwright_browser",
    "playwright_browser_screenshot": "playwright_browser",
}

# Apify endpoint → (actor_id, base_input_defaults)
_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {
    # Social
    "apify_tiktok": ("clockworks/free-tiktok-scraper", {}),
    "apify_tiktok_scraper": ("clockworks/tiktok-scraper", {}),
    "apify_tiktok_comments_scraper": ("clockworks/tiktok-comments-scraper", {}),
    "apify_tiktok_shop_scraper": ("apify/tiktok-shop-scraper", {}),
    "apify_instagram": ("apify/instagram-scraper", {}),
    "apify_instagram_scraper": ("apify/instagram-scraper", {}),
    "apify_instagram_profile_scraper": ("apify/instagram-profile-scraper", {}),
    "apify_instagram_hashtag_scraper": ("apify/instagram-hashtag-scraper", {}),
    "apify_youtube": ("streamers/youtube-scraper", {}),
    "apify_youtube_scraper": ("streamers/youtube-scraper", {}),
    "apify_youtube_comments_scraper": ("streamers/youtube-comments-scraper", {}),
    "apify_youtube_comment_scraper": ("streamers/youtube-comment-scraper", {}),
    "apify_reddit_scraper": ("trudax/reddit-scraper-lite", {}),
    "apify_reddit_community_monitor": ("apify/reddit-scraper", {}),
    "apify_facebook_posts_scraper": ("apify/facebook-posts-scraper", {}),
    "apify_facebook_comments_scraper": ("apify/facebook-comments-scraper", {}),
    "apify_linkedin_profile_scraper": ("apimaestro/linkedin-profile-scraper", {}),
    "apify_linkedin_company_scraper": ("apimaestro/linkedin-company-scraper", {}),
    "apify_linkedin_company_posts_scraper": ("harvestapi/linkedin-company-posts", {}),
    "apify_linkedin_jobs_scraper": ("freshdata/linkedin-job-scraper", {}),
    "apify_linkedin_company_employees_scraper": (
        "apimaestro/linkedin-company-employees-scraper-no-cookies",
        {},
    ),
    "apify_linkedin_company_search_scraper": ("khadinakbar/linkedin-company-search-scraper", {}),
    "apify_x_scraper": ("quacker/twitter-scraper", {}),
    "apify_x_tweet_scraper": ("apidojo/tweet-scraper", {}),
    "apify_threads_scraper": ("apify/threads-scraper", {}),
    "apify_threads_profile_scraper": ("apify/threads-profile-api-scraper", {}),
    "apify_threads_posts_scraper": ("futurizerush/meta-threads-scraper", {}),
    "apify_pinterest_scraper": ("danielmilevski9/pinterest-crawler", {}),
    "apify_snapchat_profile_scraper": ("apify/snapchat-scraper", {}),
    "apify_snapchat_scraper": ("apify/snapchat-scraper", {}),
    # E-commerce
    "apify_amazon_product_scraper": ("junglee/amazon-crawler", {}),
    "apify_amazon_review_scraper": ("junglee/amazon-review-scraper", {}),
    "apify_amazon_reviews_scraper": ("junglee/amazon-reviews-scraper", {}),
    "apify_walmart_scraper": ("apify/walmart-scraper", {}),
    "apify_walmart_product_scraper": ("e-commerce/walmart-product-detail-scraper", {}),
    "apify_walmart_reviews_scraper": ("e-commerce/walmart-reviews-scraper", {}),
    "apify_temu_products_scraper": ("amit123/temu-products-scraper", {}),
    "apify_shein_product_scraper": ("shahidirfan/shein-product-scraper", {}),
    "apify_aliexpress_products_scraper": ("devcake/aliexpress-products-scraper", {}),
    "apify_ebay_scraper": ("dtrungtin/ebay-items-scraper", {}),
    "apify_ebay_product_scraper": ("dtrungtin/ebay-items-scraper", {}),
    "apify_ebay_sold_listings_scraper": ("caffein.dev/ebay-sold-listings", {}),
    "apify_etsy_scraper": ("automation-lab/etsy-scraper", {}),
    "apify_shopify_scraper": ("clearpath/shopify-store-leads", {}),
    # Google
    "apify_google_search_scraper": ("apify/google-search-scraper", {}),
    "apify_google_maps_scraper": ("compass/crawler-google-places", {}),
    "apify_google_maps_reviews_scraper": ("compass/Google-Maps-Reviews-Scraper", {}),
    "apify_google_trends_scraper": ("apify/google-trends-scraper", {}),
    "apify_google_shopping_scraper": ("apify/google-shopping-scraper", {}),
    "apify_google_play_scraper": ("apify/google-play-scraper", {}),
    "apify_google_news_media_search": (
        "data_xplorer/google-news-scraper-fast",
        {"keywords": [], "maxArticles": 10, "timeframe": "7d"},
    ),
    "apify_google_news_scraper": ("data_xplorer/google-news-scraper-fast", {}),
    "apify_google_ai_overviews_scraper": ("apify/google-ai-overviews-scraper", {}),
    # AI Search
    "apify_perplexity_scraper": ("apify/perplexity-scraper", {}),
    "apify_perplexity_search_scraper": ("apify/perplexity-search-scraper", {}),
    "apify_chatgpt_scraper": ("apify/chatgpt-scraper", {}),
    "apify_chatgpt_search_scraper": ("apify/chatgpt-search-scraper", {}),
    "apify_gemini_scraper": ("apify/gemini-scraper", {}),
    "apify_gemini_search_scraper": ("apify/gemini-scraper", {}),
    # Ads
    "apify_google_ads_transparency_scraper": ("apify/google-ads-transparency-scraper", {}),
    "apify_google_ads_scraper": ("lexis-solutions/google-ads-scraper", {}),
    "apify_meta_ads_library_scraper": ("apify/meta-ads-library", {}),
    "apify_facebook_ads_scraper": ("apify/facebook-ads-scraper", {}),
    "apify_tiktok_ads_library_scraper": ("apify/tiktok-ads-library", {}),
    "apify_tiktok_ads_scraper": ("lexis-solutions/tiktok-ads-scraper", {}),
    "apify_linkedin_ads_scraper": ("apify/linkedin-ads-scraper", {}),
    "apify_reddit_ads_scraper": ("apify/reddit-ads-scraper", {}),
    "apify_x_ads_transparency_scraper": ("apify/x-ads-transparency-scraper", {}),
    "apify_pinterest_ads_scraper": ("shahidirfan/Pinterest-Ads-Scraper", {}),
    "apify_snapchat_ads_scraper": ("apify/snapchat-ads-library", {}),
    # B2B / Review / Community
    "apify_trustpilot_scraper": ("apify/trustpilot-scraper", {}),
    "apify_trustpilot_reviews_scraper": ("memo23/trustpilot-scraper-ppe", {}),
    "apify_appstore_scraper": ("apify/apple-app-store-scraper", {}),
    "apify_appstore_reviews_scraper": ("johnvc/apple-app-store-reviews-api", {}),
    "apify_google_play_reviews_scraper": ("neatrat/google-play-store-reviews-scraper", {}),
    "apify_tripadvisor_scraper": ("maxcopell/tripadvisor", {}),
    "apify_tripadvisor_reviews_scraper": ("maxcopell/tripadvisor-reviews", {}),
    "apify_yelp_scraper": ("tri_angle/yelp-scraper", {}),
    "apify_booking_scraper": ("apify/booking-scraper", {}),
    "apify_airbnb_scraper": ("apify/airbnb-scraper", {}),
    "apify_crunchbase_scraper": ("apify/crunchbase-scraper", {}),
    "apify_producthunt_scraper": ("apify/product-hunt-scraper", {}),
    "apify_product_hunt_scraper": ("happitap/product-hunt-daily-launch-scraper", {}),
    "apify_glassdoor_scraper": ("memo23/glassdoor-scraper-ppr", {}),
    "apify_hacker_news_scraper": ("onescales/hacker-news-data", {}),
    "apify_bluesky_scraper": ("fatihtahta/All-In-One-Bluesky-Scraper", {}),
    "apify_telegram_scraper": ("danielmilevski9/telegram-channel-scraper", {}),
    "apify_indeed_scraper": ("apify/indeed-scraper", {}),
    "apify_indeed_jobs_scraper": ("misceres/indeed-scraper", {}),
    # Media account monitoring
    "apify_instagram_media_profile_scraper": ("apify/instagram-profile-scraper", {}),
    "apify_tiktok_media_profile_scraper": ("clockworks/tiktok-scraper", {}),
    "apify_youtube_media_channel_scraper": ("streamers/youtube-scraper", {}),
    "apify_facebook_media_page_scraper": ("apify/facebook-posts-scraper", {}),
    "apify_x_media_account_scraper": ("apidojo/tweet-scraper", {}),
    "apify_pinterest_media_profile_scraper": ("danielmilevski9/pinterest-crawler", {}),
    # Open Web
    "apify_website_content_crawler": ("apify/website-content-crawler", {}),
    "apify_web_scraper": ("apify/web-scraper", {}),
    "apify_rag_web_browser": ("apify/rag-web-browser", {}),
    "apify_tiktok_transcript_extractor": ("clockworks/tiktok-transcript-extractor", {}),
    "apify_youtube_transcript_scraper": ("johnvc/youtubetranscripts", {}),
    "apify_tiktok_creative_center": ("doliz/tiktok-creative-center-scraper", {}),
    "apify_facebook_group_scraper": ("whoareyouanas/facebook-group-scraper", {}),
    "apify_similarweb_scraper": ("curious_coder/similarweb-scraper", {}),
    "apify_tiktok_shop_search_scraper": ("pratikdani/tiktok-shop-search-scraper", {}),
    "apify_target_products_scraper": ("bovi/target-products", {}),
    "apify_facebook_marketplace_scraper": ("apify/facebook-marketplace-scraper", {}),
}


class QuickCollectRequest(BaseModel):
    project_id: uuid.UUID
    endpoint_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=200)


class QuickCollectResponse(BaseModel):
    task_run_id: uuid.UUID
    task_id: uuid.UUID
    source_id: uuid.UUID
    status: str
    records_count: int
    error_message: str | None


@router.post("", response_model=QuickCollectResponse, status_code=status.HTTP_201_CREATED)
async def quick_collect(
    body: QuickCollectRequest,
    session: SessionDep,
) -> QuickCollectResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    """Create an ephemeral Source + Task and run one collection immediately.

    Returns the completed (or failed) TaskRun synchronously.
    Suitable for small quick-collect requests (up to ~30 s) from the console UI.
    """
    collector_type = _ENDPOINT_TO_COLLECTOR.get(body.endpoint_type)
    if collector_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown endpoint_type: {body.endpoint_type!r}",
        )

    await ensure_collectors_seeded(session)
    collector_db = await get_collector_by_type(session, collector_type)
    if collector_db is None or not collector_db.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collector {collector_type!r} is not available",
        )

    config: dict[str, Any] = {"endpoint_type": body.endpoint_type, **body.params}

    apify_defaults = _APIFY_ENDPOINT_DEFAULTS.get(body.endpoint_type)
    if apify_defaults is not None:
        actor_id, base_input = apify_defaults
        actor_input = {**base_input, **body.params}
        config = {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": body.params.get("maxItems", 10),
            "max_total_charge_usd": body.params.get("max_total_charge_usd", 1.0),
        }

    try:
        validated = validate_collector_config(collector_type, config)
    except (CollectorConfigError, CollectorNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collector config: {exc}",
        ) from exc

    label = (body.label or body.endpoint_type).strip()[:200]

    source = Source(
        workspace_id=workspace.id,
        project_id=body.project_id,
        name=f"[quick] {label}",
        type=collector_type,
        url=None,
        config=validated,
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=body.project_id,
        source_id=source.id,
        collector_type=collector_type,
        name=f"[quick] {label}",
        schedule_cron=None,
        status="enabled",
        config=validated,
    )
    session.add(task)
    await session.flush()
    source_id = source.id
    task_id = task.id
    await session.commit()

    try:
        run: TaskRun = await execute_collection_task(session, workspace, task)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collection failed: {exc}",
        ) from exc

    return QuickCollectResponse(
        task_run_id=run.id,
        task_id=task_id,
        source_id=source_id,
        status=run.status,
        records_count=run.records_count,
        error_message=run.error_message,
    )
