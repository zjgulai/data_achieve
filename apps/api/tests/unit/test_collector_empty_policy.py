"""零产出策略声明测试。

钉住严格类型集合和解析优先级。
"""

from __future__ import annotations

from data_intelligence_hub.collectors.empty_result_policy import (
    APIFY_EMPTY_RESULT_POLICY,
    ENDPOINT_EMPTY_RESULT_POLICIES,
    TIKHUB_EMPTY_RESULT_POLICY,
    EmptyResultPolicy,
    default_policy_for,
    empty_result_error,
    resolve_empty_result_policy,
)
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_COMMERCE_ENDPOINT_MAP,
    TIKHUB_ENDPOINT_MAP,
    TikHubSocialCollector,
)


def _names(value: str) -> frozenset[str]:
    return frozenset(value.split())


STRICT_SIMPLE = _names(
    """anysearch exa_search exa_find_similar baidu_search bing_search
    duckduckgo_search hackernews_search twscrape_search weibo_keyword_search
    zhihu_keyword_search bilibili_video_search kuaishou_video_search
    npm_search pypi_search crates_search rubygems_search go_search
    packagist_search nuget_search pubdev_search robin_darkweb_search
    ecommerce_product_discovery hackernews_front_page hackernews_user
    twscrape_user_tweets twscrape_trends weibo_user_posts
    weibo_trending_topics zhihu_hot_list bilibili_user_videos
    kuaishou_user_videos public_feed bestblogs_articles devto_articles
    juejin_articles substack_posts github_topic firecrawl_crawl
    firecrawl_batch_scrape"""
)

DETAIL_SIMPLE = _names(
    """github_repo npm_package pypi_package crates_package rubygems_package
    go_package packagist_package nuget_package pubdev_package
    ecommerce_product_page exa_contents"""
)

STRICT_TIKHUB = _names(
    """tikhub_tiktok_video_search tikhub_instagram_search
    tikhub_xiaohongshu_search tikhub_youtube_search tikhub_reddit_search
    tikhub_x_search tikhub_douyin_video_search
    tikhub_bilibili_video_search tikhub_weibo_search
    tikhub_kuaishou_search tikhub_wechat_search tikhub_zhihu_search
    tikhub_douyin_brand_hot_search tikhub_youtube_video_search
    tikhub_threads_search tikhub_linkedin_search_jobs
    tikhub_lemon8_search tikhub_tiktok_ads_search
    tikhub_tiktok_ads_keyword_suggest tikhub_tiktok_live_search
    tikhub_tiktok_user_posts tikhub_tiktok_hashtag_posts
    tikhub_instagram_user_posts tikhub_youtube_channel_videos
    tikhub_reddit_subreddit_posts tikhub_x_user_tweets
    tikhub_douyin_user_posts tikhub_douyin_hot_search
    tikhub_bilibili_user_videos tikhub_weibo_user_posts
    tikhub_kuaishou_user_posts tikhub_wechat_channels_video
    tikhub_threads_user_posts tikhub_linkedin_user_posts
    tikhub_linkedin_company_posts tikhub_lemon8_user_posts
    tikhub_lemon8_trending tikhub_tiktok_top_ads
    tikhub_tiktok_shop_products tikhub_youtube_trending
    tikhub_reddit_trending tikhub_x_trending
    tikhub_tiktok_user_followers tikhub_instagram_user_followers
    tikhub_x_user_followers tikhub_linkedin_company_profile
    tikhub_linkedin_job_detail tikhub_tiktok_ads_detail
    tikhub_tiktok_creator_info tikhub_tiktok_creator_insights
    tikhub_tiktok_creator_insights_trend
    tikhub_tiktok_creator_account_health tikhub_tiktok_live_room_detail
    tikhub_tiktok_live_user tikhub_tiktok_shop_search_v2
    tikhub_tiktok_shop_hot_products"""
)

DETAIL_TIKHUB = _names(
    """tikhub_linkedin_company_profile tikhub_linkedin_job_detail
    tikhub_tiktok_ads_detail tikhub_tiktok_creator_info
    tikhub_tiktok_creator_insights tikhub_tiktok_creator_insights_trend
    tikhub_tiktok_creator_account_health tikhub_tiktok_live_room_detail
    tikhub_tiktok_live_user"""
)

ALLOW_TIKHUB = _names(
    """tikhub_bilibili_comments tikhub_douyin_comments
    tikhub_instagram_post_comments tikhub_linkedin_post_comments
    tikhub_reddit_post_comments tikhub_threads_post_comments
    tikhub_youtube_video_comments tikhub_zhihu_question_answers
    tikhub_tiktok_shop_reviews_v2"""
)

STRICT_APIFY = _names(
    """apify_1688_advanced apify_1688_product_detail
    apify_1688_product_search apify_alibaba_product_detail
    apify_alibaba_product_search apify_aliexpress_product_search_v2
    apify_aliexpress_products_scraper apify_amazon_bestsellers
    apify_amazon_bsr_tracker apify_amazon_competitor_research
    apify_amazon_price_tracker apify_amazon_product_scraper
    apify_ebay_product_scraper apify_ebay_sold_listings_scraper
    apify_etsy_scraper apify_shein_product_scraper
    apify_shopify_products_monitor apify_shopify_scraper
    apify_target_products_scraper apify_temu_products_scraper
    apify_tiktok_shop_product_detail apify_tiktok_shop_scraper
    apify_tiktok_shop_search_scraper apify_walmart_product_scraper
    apify_airbnb_scraper apify_booking_scraper apify_google_maps_scraper
    apify_bluesky_scraper apify_crunchbase_scraper
    apify_facebook_ads_library_scraper apify_facebook_ads_scraper
    apify_facebook_groups_scraper apify_facebook_marketplace_scraper
    apify_facebook_media_page_scraper apify_facebook_pages_scraper
    apify_facebook_posts_scraper apify_facebook_search_scraper
    apify_instagram_hashtag_scraper
    apify_instagram_media_profile_scraper
    apify_instagram_post_scraper apify_instagram_profile_scraper
    apify_instagram_reel_scraper apify_instagram_scraper
    apify_linkedin_company_employees_scraper
    apify_linkedin_company_posts_scraper
    apify_linkedin_company_search_scraper apify_linkedin_jobs_scraper
    apify_linkedin_profile_scraper apify_pinterest_ads_scraper
    apify_reddit_scraper apify_snapchat_ads_scraper
    apify_tiktok_ads_scraper apify_tiktok_creative_center
    apify_tiktok_media_profile_scraper apify_tiktok_scraper
    apify_threads_posts_scraper apify_threads_profile_scraper
    apify_twitter_user_scraper apify_x_media_account_scraper
    apify_x_tweet_scraper apify_youtube_media_channel_scraper
    apify_youtube_scraper apify_chatgpt_search_scraper
    apify_gemini_search_scraper apify_google_ads_scraper
    apify_google_ai_overviews_scraper apify_google_news_media_search
    apify_google_news_scraper apify_google_search_scraper
    apify_google_trends_scraper apify_hacker_news_scraper
    apify_indeed_jobs_scraper apify_perplexity_search_scraper
    apify_serp_scraperlink apify_shopify_store_leads
    apify_similarweb_scraper apify_rag_web_browser
    apify_website_content_crawler"""
)

ALLOW_APIFY = _names(
    """apify_amazon_free_product_scraper apify_amazon_reviews_axesso
    apify_amazon_reviews_extractor apify_amazon_reviews_scraper
    apify_appstore_reviews_scraper apify_facebook_comments_scraper
    apify_glassdoor_scraper apify_google_maps_reviews_scraper
    apify_google_play_reviews_scraper apify_instagram_comment_scraper
    apify_tiktok_comments_scraper apify_tiktok_transcript_extractor
    apify_tripadvisor_reviews_scraper apify_trustpilot_reviews_scraper
    apify_walmart_reviews_scraper apify_youtube_comments_scraper
    apify_youtube_transcript_scraper"""
)


class TestRegistryCoverage:
    def test_every_collector_declares_allow_empty(self):
        # 简单采集器在类体声明。多态采集器用端点覆盖表。
        missing = sorted(
            collector_type
            for collector_type, collector_class in COLLECTOR_REGISTRY.items()
            if "allow_empty" not in vars(collector_class)
            and collector_type not in ENDPOINT_EMPTY_RESULT_POLICIES
        )
        assert missing == []

    def test_strict_simple_set_is_exact(self):
        actual = {
            collector_type
            for collector_type, collector_class in COLLECTOR_REGISTRY.items()
            if vars(collector_class).get("allow_empty") is False
        }
        assert actual == STRICT_SIMPLE | DETAIL_SIMPLE

    def test_detail_simple_set_is_exact(self):
        actual = {
            collector_type
            for collector_type, collector_class in COLLECTOR_REGISTRY.items()
            if vars(collector_class).get("min_expected_records") == 1
        }
        assert actual == DETAIL_SIMPLE


class TestTikHubPolicy:
    def test_every_endpoint_has_a_policy(self):
        expected = set(TIKHUB_ENDPOINT_MAP) | set(TIKHUB_COMMERCE_ENDPOINT_MAP)
        assert set(TIKHUB_EMPTY_RESULT_POLICY) == expected

    def test_strict_set_is_exact(self):
        actual = {
            endpoint_type
            for endpoint_type, policy in TIKHUB_EMPTY_RESULT_POLICY.items()
            if not policy.allow_empty
        }
        assert actual == STRICT_TIKHUB

    def test_allow_empty_set_is_exact(self):
        actual = {
            endpoint_type
            for endpoint_type, policy in TIKHUB_EMPTY_RESULT_POLICY.items()
            if policy.allow_empty
        }
        assert actual == ALLOW_TIKHUB

    def test_detail_set_is_exact(self):
        actual = {
            endpoint_type
            for endpoint_type, policy in TIKHUB_EMPTY_RESULT_POLICY.items()
            if policy.min_expected_records == 1
        }
        assert actual == DETAIL_TIKHUB


class TestApifyPolicy:
    def test_strict_set_is_exact(self):
        actual = {
            endpoint_type
            for endpoint_type, policy in APIFY_EMPTY_RESULT_POLICY.items()
            if not policy.allow_empty
        }
        assert actual == STRICT_APIFY

    def test_allow_empty_set_is_exact(self):
        actual = {
            endpoint_type
            for endpoint_type, policy in APIFY_EMPTY_RESULT_POLICY.items()
            if policy.allow_empty
        }
        assert actual == ALLOW_APIFY


class TestPolicyResolution:
    def test_class_attribute_is_the_default(self):
        assert default_policy_for(GitHubRepoCollector) == EmptyResultPolicy(
            allow_empty=False,
            min_expected_records=1,
        )
        assert default_policy_for(GenericWebCollector) == EmptyResultPolicy(
            allow_empty=True,
            min_expected_records=0,
        )

    def test_endpoint_override_beats_class_default(self):
        policy = resolve_empty_result_policy(
            collector_type="tikhub_social",
            config={"endpoint_type": "tikhub_tiktok_video_search"},
            collector_class=TikHubSocialCollector,
        )
        assert policy.allow_empty is False

    def test_task_override_beats_endpoint_override(self):
        policy = resolve_empty_result_policy(
            collector_type="tikhub_social",
            config={"endpoint_type": "tikhub_tiktok_video_search"},
            collector_class=TikHubSocialCollector,
            task_config={"allow_empty": True, "min_expected_records": 5},
        )
        assert policy.allow_empty is True
        assert policy.min_expected_records == 5

    def test_task_min_records_override(self):
        policy = resolve_empty_result_policy(
            collector_type="github_repo",
            config={},
            collector_class=GitHubRepoCollector,
            task_config={"min_expected_records": 3},
        )
        assert policy.allow_empty is False
        assert policy.min_expected_records == 3

    def test_unknown_endpoint_uses_class_policy(self):
        policy = resolve_empty_result_policy(
            collector_type="tikhub_social",
            config={"endpoint_type": "tikhub_unknown_endpoint"},
            collector_class=TikHubSocialCollector,
        )
        assert policy.allow_empty is True


class TestEmptyResultError:
    def test_message_without_endpoint(self):
        assert empty_result_error(
            collector_type="github_repo",
            endpoint_type=None,
            expected_records=1,
        ) == (
            "collector_empty_result: expected >= 1 record(s), got 0 "
            "(collector_type=github_repo, endpoint_type=None)"
        )

    def test_message_with_endpoint(self):
        assert empty_result_error(
            collector_type="tikhub_social",
            endpoint_type="tikhub_tiktok_video_search",
            expected_records=1,
        ) == (
            "collector_empty_result: expected >= 1 record(s), got 0 "
            "(collector_type=tikhub_social, "
            "endpoint_type=tikhub_tiktok_video_search)"
        )
