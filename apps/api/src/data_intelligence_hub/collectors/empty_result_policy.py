"""Zero-record policy for collectors.

A collector run that returns zero raw records can be a valid result or a
failure. This module stores the per-collector and per-endpoint policy that
the service uses to decide.

Resolution order:

    explicit task config
      > endpoint override table
      > collector class attribute
      > BaseCollector default (allow_empty=True)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_intelligence_hub.collectors.base import BaseCollector


@dataclass(frozen=True)
class EmptyResultPolicy:
    allow_empty: bool = True
    min_expected_records: int = 0

    @property
    def effective_min_expected_records(self) -> int:
        """Strict policies always expect at least one record."""
        if self.allow_empty:
            return 0
        return max(self.min_expected_records, 1)


_ALLOW_EMPTY = EmptyResultPolicy()
_STRICT = EmptyResultPolicy(allow_empty=False)
_STRICT_DETAIL = EmptyResultPolicy(allow_empty=False, min_expected_records=1)


# TikHub is a single collector class with many endpoints, so the policy lives
# at endpoint level. Search, list and known-ID endpoints must return records.
# Comments and question answers may legitimately be empty.
TIKHUB_EMPTY_RESULT_POLICY: dict[str, EmptyResultPolicy] = {
    # Search endpoints (20)
    "tikhub_tiktok_video_search": _STRICT,
    "tikhub_instagram_search": _STRICT,
    "tikhub_xiaohongshu_search": _STRICT,
    "tikhub_youtube_search": _STRICT,
    "tikhub_reddit_search": _STRICT,
    "tikhub_x_search": _STRICT,
    "tikhub_douyin_video_search": _STRICT,
    "tikhub_bilibili_video_search": _STRICT,
    "tikhub_weibo_search": _STRICT,
    "tikhub_kuaishou_search": _STRICT,
    "tikhub_wechat_search": _STRICT,
    "tikhub_zhihu_search": _STRICT,
    "tikhub_douyin_brand_hot_search": _STRICT,
    "tikhub_youtube_video_search": _STRICT,
    "tikhub_threads_search": _STRICT,
    "tikhub_linkedin_search_jobs": _STRICT,
    "tikhub_lemon8_search": _STRICT,
    "tikhub_tiktok_ads_search": _STRICT,
    "tikhub_tiktok_ads_keyword_suggest": _STRICT,
    "tikhub_tiktok_live_search": _STRICT,
    "tikhub_tiktok_shop_search_v2": _STRICT,
    "tikhub_tiktok_shop_hot_products": _STRICT,
    "tikhub_tiktok_shop_reviews_v2": _ALLOW_EMPTY,
    "tikhub_tiktok_video_products": _ALLOW_EMPTY,
    "tikhub_tiktok_creator_showcase": _ALLOW_EMPTY,
    # List, subscription and ranking endpoints (25)
    "tikhub_tiktok_user_posts": _STRICT,
    "tikhub_tiktok_hashtag_posts": _STRICT,
    "tikhub_instagram_user_posts": _STRICT,
    "tikhub_youtube_channel_videos": _STRICT,
    "tikhub_reddit_subreddit_posts": _STRICT,
    "tikhub_x_user_tweets": _STRICT,
    "tikhub_douyin_user_posts": _STRICT,
    "tikhub_douyin_hot_search": _STRICT,
    "tikhub_bilibili_user_videos": _STRICT,
    "tikhub_weibo_user_posts": _STRICT,
    "tikhub_kuaishou_user_posts": _STRICT,
    "tikhub_wechat_channels_video": _STRICT,
    "tikhub_threads_user_posts": _STRICT,
    "tikhub_linkedin_user_posts": _STRICT,
    "tikhub_linkedin_company_posts": _STRICT,
    "tikhub_lemon8_user_posts": _STRICT,
    "tikhub_lemon8_trending": _STRICT,
    "tikhub_tiktok_top_ads": _STRICT,
    "tikhub_tiktok_shop_products": _STRICT,
    "tikhub_youtube_trending": _STRICT,
    "tikhub_reddit_trending": _STRICT,
    "tikhub_x_trending": _STRICT,
    "tikhub_tiktok_user_followers": _STRICT,
    "tikhub_instagram_user_followers": _STRICT,
    "tikhub_x_user_followers": _STRICT,
    # Known-ID detail endpoints (9)
    "tikhub_linkedin_company_profile": _STRICT_DETAIL,
    "tikhub_linkedin_job_detail": _STRICT_DETAIL,
    "tikhub_tiktok_ads_detail": _STRICT_DETAIL,
    "tikhub_tiktok_creator_info": _STRICT_DETAIL,
    "tikhub_tiktok_creator_insights": _STRICT_DETAIL,
    "tikhub_tiktok_creator_insights_trend": _STRICT_DETAIL,
    "tikhub_tiktok_creator_account_health": _STRICT_DETAIL,
    "tikhub_tiktok_live_room_detail": _STRICT_DETAIL,
    "tikhub_tiktok_live_user": _STRICT_DETAIL,
    # Comment and question-answer endpoints (8)
    "tikhub_bilibili_comments": _ALLOW_EMPTY,
    "tikhub_douyin_comments": _ALLOW_EMPTY,
    "tikhub_instagram_post_comments": _ALLOW_EMPTY,
    "tikhub_linkedin_post_comments": _ALLOW_EMPTY,
    "tikhub_reddit_post_comments": _ALLOW_EMPTY,
    "tikhub_threads_post_comments": _ALLOW_EMPTY,
    "tikhub_youtube_video_comments": _ALLOW_EMPTY,
    "tikhub_zhihu_question_answers": _ALLOW_EMPTY,
}


# Apify is also a single collector class, selected by endpoint_type. Product,
# social, search and crawl endpoints must return records. Reviews, comments
# and transcripts may legitimately be empty.
APIFY_EMPTY_RESULT_POLICY: dict[str, EmptyResultPolicy] = {
    # Product search, ranking and known-URL detail endpoints (27)
    "apify_1688_advanced": _STRICT,
    "apify_1688_product_detail": _STRICT,
    "apify_1688_product_search": _STRICT,
    "apify_alibaba_product_detail": _STRICT,
    "apify_alibaba_product_search": _STRICT,
    "apify_aliexpress_product_search_v2": _STRICT,
    "apify_aliexpress_products_scraper": _STRICT,
    "apify_amazon_bestsellers": _STRICT,
    "apify_amazon_bsr_tracker": _STRICT,
    "apify_amazon_competitor_research": _STRICT,
    "apify_amazon_price_tracker": _STRICT,
    "apify_amazon_product_scraper": _STRICT,
    "apify_ebay_product_scraper": _STRICT,
    "apify_ebay_sold_listings_scraper": _STRICT,
    "apify_etsy_scraper": _STRICT,
    "apify_shein_product_scraper": _STRICT,
    "apify_shopify_products_monitor": _STRICT,
    "apify_shopify_scraper": _STRICT,
    "apify_target_products_scraper": _STRICT,
    "apify_temu_products_scraper": _STRICT,
    "apify_tiktok_shop_product_detail": _STRICT,
    "apify_tiktok_shop_scraper": _STRICT,
    "apify_tiktok_shop_search_scraper": _STRICT,
    "apify_walmart_product_scraper": _STRICT,
    "apify_airbnb_scraper": _STRICT,
    "apify_booking_scraper": _STRICT,
    "apify_google_maps_scraper": _STRICT,
    # Social search, list and known-account endpoints (35)
    "apify_bluesky_scraper": _STRICT,
    "apify_crunchbase_scraper": _STRICT,
    "apify_facebook_ads_library_scraper": _STRICT,
    "apify_facebook_ads_scraper": _STRICT,
    "apify_facebook_groups_scraper": _STRICT,
    "apify_facebook_marketplace_scraper": _STRICT,
    "apify_facebook_media_page_scraper": _STRICT,
    "apify_facebook_pages_scraper": _STRICT,
    "apify_facebook_posts_scraper": _STRICT,
    "apify_facebook_search_scraper": _STRICT,
    "apify_instagram_hashtag_scraper": _STRICT,
    "apify_instagram_media_profile_scraper": _STRICT,
    "apify_instagram_post_scraper": _STRICT,
    "apify_instagram_profile_scraper": _STRICT,
    "apify_instagram_reel_scraper": _STRICT,
    "apify_instagram_scraper": _STRICT,
    "apify_linkedin_company_employees_scraper": _STRICT,
    "apify_linkedin_company_posts_scraper": _STRICT,
    "apify_linkedin_company_search_scraper": _STRICT,
    "apify_linkedin_jobs_scraper": _STRICT,
    "apify_linkedin_profile_scraper": _STRICT,
    "apify_pinterest_ads_scraper": _STRICT,
    "apify_reddit_scraper": _STRICT,
    "apify_snapchat_ads_scraper": _STRICT,
    "apify_tiktok_ads_scraper": _STRICT,
    "apify_tiktok_creative_center": _STRICT,
    "apify_tiktok_media_profile_scraper": _STRICT,
    "apify_tiktok_scraper": _STRICT,
    "apify_threads_posts_scraper": _STRICT,
    "apify_threads_profile_scraper": _STRICT,
    "apify_twitter_user_scraper": _STRICT,
    "apify_x_media_account_scraper": _STRICT,
    "apify_x_tweet_scraper": _STRICT,
    "apify_youtube_media_channel_scraper": _STRICT,
    "apify_youtube_scraper": _STRICT,
    # Search, news, AI answer, job and web-crawl endpoints (16)
    "apify_chatgpt_search_scraper": _STRICT,
    "apify_gemini_search_scraper": _STRICT,
    "apify_google_ads_scraper": _STRICT,
    "apify_google_ai_overviews_scraper": _STRICT,
    "apify_google_news_media_search": _STRICT,
    "apify_google_news_scraper": _STRICT,
    "apify_google_search_scraper": _STRICT,
    "apify_google_trends_scraper": _STRICT,
    "apify_hacker_news_scraper": _STRICT,
    "apify_indeed_jobs_scraper": _STRICT,
    "apify_perplexity_search_scraper": _STRICT,
    "apify_serp_scraperlink": _STRICT,
    "apify_shopify_store_leads": _STRICT,
    "apify_similarweb_scraper": _STRICT,
    "apify_rag_web_browser": _STRICT,
    "apify_website_content_crawler": _STRICT,
    # Review, comment and transcript endpoints (17)
    "apify_amazon_free_product_scraper": _ALLOW_EMPTY,
    "apify_amazon_reviews_axesso": _ALLOW_EMPTY,
    "apify_amazon_reviews_extractor": _ALLOW_EMPTY,
    "apify_amazon_reviews_scraper": _ALLOW_EMPTY,
    "apify_appstore_reviews_scraper": _ALLOW_EMPTY,
    "apify_facebook_comments_scraper": _ALLOW_EMPTY,
    "apify_glassdoor_scraper": _ALLOW_EMPTY,
    "apify_google_maps_reviews_scraper": _ALLOW_EMPTY,
    "apify_google_play_reviews_scraper": _ALLOW_EMPTY,
    "apify_instagram_comment_scraper": _ALLOW_EMPTY,
    "apify_tiktok_comments_scraper": _ALLOW_EMPTY,
    "apify_tiktok_transcript_extractor": _ALLOW_EMPTY,
    "apify_tripadvisor_reviews_scraper": _ALLOW_EMPTY,
    "apify_trustpilot_reviews_scraper": _ALLOW_EMPTY,
    "apify_walmart_reviews_scraper": _ALLOW_EMPTY,
    "apify_youtube_comments_scraper": _ALLOW_EMPTY,
    "apify_youtube_transcript_scraper": _ALLOW_EMPTY,
}


ENDPOINT_EMPTY_RESULT_POLICIES: dict[str, dict[str, EmptyResultPolicy]] = {
    "tikhub_social": TIKHUB_EMPTY_RESULT_POLICY,
    "apify_actor": APIFY_EMPTY_RESULT_POLICY,
}


def default_policy_for(collector_class: type[BaseCollector]) -> EmptyResultPolicy:
    return EmptyResultPolicy(
        allow_empty=bool(getattr(collector_class, "allow_empty", True)),
        min_expected_records=int(getattr(collector_class, "min_expected_records", 0)),
    )


def resolve_empty_result_policy(
    *,
    collector_type: str,
    config: dict[str, Any] | None = None,
    collector_class: type[BaseCollector] | None = None,
    task_config: dict[str, Any] | None = None,
) -> EmptyResultPolicy:
    """Resolve the zero-record policy for one run."""
    policy = (
        default_policy_for(collector_class)
        if collector_class is not None
        else EmptyResultPolicy()
    )
    endpoint_type = (config or {}).get("endpoint_type")
    if isinstance(endpoint_type, str):
        policy = ENDPOINT_EMPTY_RESULT_POLICIES.get(collector_type, {}).get(
            endpoint_type, policy
        )

    overrides = task_config or {}
    allow_empty = overrides.get("allow_empty")
    if isinstance(allow_empty, bool):
        policy = EmptyResultPolicy(
            allow_empty=allow_empty,
            min_expected_records=policy.min_expected_records,
        )
    min_expected_records = overrides.get("min_expected_records")
    if (
        isinstance(min_expected_records, int)
        and not isinstance(min_expected_records, bool)
        and min_expected_records >= 0
    ):
        policy = EmptyResultPolicy(
            allow_empty=policy.allow_empty,
            min_expected_records=min_expected_records,
        )
    return policy


def empty_result_error(
    *,
    collector_type: str,
    endpoint_type: str | None,
    expected_records: int,
) -> str:
    return (
        f"collector_empty_result: expected >= {expected_records} record(s), "
        f"got 0 (collector_type={collector_type}, endpoint_type={endpoint_type})"
    )
