"""One-click quick collect: create ephemeral Source + Task, run immediately."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.collectors.apify_actor import DEFAULT_MAX_TOTAL_CHARGE_USD
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.repositories.collectors import get_collector_by_type
from data_intelligence_hub.repositories.projects import get_project
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
    "tikhub_douyin_video_search": "tikhub_social",
    "tikhub_douyin_user_posts": "tikhub_social",
    "tikhub_douyin_hot_search": "tikhub_social",
    "tikhub_douyin_comments": "tikhub_social",
    "tikhub_douyin_brand_hot_search": "tikhub_social",
    "tikhub_bilibili_video_search": "tikhub_social",
    "tikhub_bilibili_user_videos": "tikhub_social",
    "tikhub_bilibili_comments": "tikhub_social",
    "tikhub_weibo_search": "tikhub_social",
    "tikhub_weibo_user_posts": "tikhub_social",
    "tikhub_kuaishou_search": "tikhub_social",
    "tikhub_kuaishou_user_posts": "tikhub_social",
    "tikhub_wechat_search": "tikhub_social",
    "tikhub_wechat_channels_video": "tikhub_social",
    "tikhub_zhihu_search": "tikhub_social",
    "tikhub_zhihu_question_answers": "tikhub_social",
    # Apify Social (18 endpoints)
    "apify_tiktok_scraper": "apify_actor",
    "apify_tiktok_comments_scraper": "apify_actor",
    "apify_tiktok_shop_scraper": "apify_actor",
    "apify_instagram_scraper": "apify_actor",
    "apify_instagram_profile_scraper": "apify_actor",
    "apify_youtube_scraper": "apify_actor",
    "apify_youtube_comments_scraper": "apify_actor",
    "apify_reddit_scraper": "apify_actor",
    "apify_facebook_posts_scraper": "apify_actor",
    "apify_facebook_comments_scraper": "apify_actor",
    "apify_linkedin_company_posts_scraper": "apify_actor",
    "apify_linkedin_jobs_scraper": "apify_actor",
    "apify_linkedin_company_employees_scraper": "apify_actor",
    "apify_linkedin_company_search_scraper": "apify_actor",
    "apify_x_tweet_scraper": "apify_actor",
    "apify_threads_profile_scraper": "apify_actor",
    "apify_threads_posts_scraper": "apify_actor",
    # Apify E-commerce (13 endpoints)
    "apify_amazon_product_scraper": "apify_actor",
    "apify_amazon_reviews_scraper": "apify_actor",
    "apify_walmart_product_scraper": "apify_actor",
    "apify_walmart_reviews_scraper": "apify_actor",
    "apify_temu_products_scraper": "apify_actor",
    "apify_shein_product_scraper": "apify_actor",
    "apify_aliexpress_products_scraper": "apify_actor",
    "apify_ebay_product_scraper": "apify_actor",
    "apify_ebay_sold_listings_scraper": "apify_actor",
    "apify_etsy_scraper": "apify_actor",
    "apify_shopify_scraper": "apify_actor",
    # Apify Google (8 endpoints)
    "apify_google_search_scraper": "apify_actor",
    "apify_google_maps_scraper": "apify_actor",
    "apify_google_maps_reviews_scraper": "apify_actor",
    "apify_google_trends_scraper": "apify_actor",
    "apify_google_news_media_search": "apify_actor",
    "apify_google_news_scraper": "apify_actor",
    "apify_google_ai_overviews_scraper": "apify_actor",
    # Apify AI Search (6 endpoints)
    "apify_perplexity_search_scraper": "apify_actor",
    "apify_chatgpt_search_scraper": "apify_actor",
    "apify_gemini_search_scraper": "apify_actor",
    # Apify Ads (10 endpoints)
    "apify_google_ads_scraper": "apify_actor",
    "apify_facebook_ads_scraper": "apify_actor",
    "apify_tiktok_ads_scraper": "apify_actor",
    "apify_pinterest_ads_scraper": "apify_actor",
    "apify_snapchat_ads_scraper": "apify_actor",
    # Apify B2B (13 endpoints)
    "apify_trustpilot_reviews_scraper": "apify_actor",
    "apify_appstore_reviews_scraper": "apify_actor",
    "apify_google_play_reviews_scraper": "apify_actor",
    "apify_tripadvisor_reviews_scraper": "apify_actor",
    "apify_booking_scraper": "apify_actor",
    "apify_airbnb_scraper": "apify_actor",
    "apify_crunchbase_scraper": "apify_actor",
    "apify_glassdoor_scraper": "apify_actor",
    "apify_hacker_news_scraper": "apify_actor",
    "apify_bluesky_scraper": "apify_actor",
    "apify_indeed_jobs_scraper": "apify_actor",
    # Apify Media (7 endpoints)
    "apify_instagram_media_profile_scraper": "apify_actor",
    "apify_tiktok_media_profile_scraper": "apify_actor",
    "apify_youtube_media_channel_scraper": "apify_actor",
    "apify_facebook_media_page_scraper": "apify_actor",
    "apify_x_media_account_scraper": "apify_actor",
    # Apify Open Web (3 endpoints)
    "apify_website_content_crawler": "apify_actor",
    "apify_rag_web_browser": "apify_actor",
    "apify_tiktok_transcript_extractor": "apify_actor",
    "apify_youtube_transcript_scraper": "apify_actor",
    "apify_tiktok_creative_center": "apify_actor",
    "apify_similarweb_scraper": "apify_actor",
    "apify_tiktok_shop_search_scraper": "apify_actor",
    "apify_target_products_scraper": "apify_actor",
    "apify_facebook_marketplace_scraper": "apify_actor",
    # 跨境供应链 - 1688.com (3 endpoints)
    "apify_1688_product_search":    "apify_actor",
    "apify_1688_product_detail":    "apify_actor",
    "apify_1688_advanced":          "apify_actor",
    # 跨境供应链 - 阿里巴巴国际站 (2 endpoints)
    "apify_alibaba_product_search": "apify_actor",
    "apify_alibaba_product_detail": "apify_actor",
    # Amazon 选品竞品 (4 endpoints)
    "apify_amazon_bestsellers":          "apify_actor",
    "apify_amazon_competitor_research":  "apify_actor",
    "apify_amazon_bsr_tracker":          "apify_actor",
    "apify_amazon_price_tracker":        "apify_actor",
    # AliExpress 升级 (1 endpoint)
    "apify_aliexpress_product_search_v2": "apify_actor",
    # 独立站竞品 (2 endpoints)
    "apify_shopify_products_monitor": "apify_actor",
    # GitHub (2 endpoints)
    "github_repo": "github_repo",
    "github_topic": "github_topic",
    # RSS / Web (3 endpoints)
    "public_feed": "public_feed",
    "generic_web": "generic_web",
    "autoscraper_enhanced_web": "autoscraper_enhanced_web",
    # Ecommerce Web (2 endpoints)
    "ecommerce_product_page": "ecommerce_product_page",
    "ecommerce_product_discovery": "ecommerce_product_discovery",
    # Browser (3 endpoints)
    "playwright_browser_text": "playwright_browser",
    "playwright_browser_html": "playwright_browser",
    "playwright_browser_screenshot": "playwright_browser",
    # AnySearch (2 endpoints)
    "anysearch_brand_media": "anysearch",
    "anysearch_competitor": "anysearch",
    "anysearch_code_doc": "anysearch",
    "anysearch_tag_search": "anysearch",
    "exa_search_auto": "exa_search",
    "exa_search_news": "exa_search",
    "exa_company_search": "exa_search",
    "exa_research_paper": "exa_search",
    "exa_people_search": "exa_search",
    "exa_financial_report": "exa_search",
    "exa_deep_research": "exa_search",
    "exa_deep_reasoning": "exa_search",
    "exa_search_instant": "exa_search",
    "exa_search_fast": "exa_search",
    "exa_personal_site": "exa_search",
    "exa_domain_search": "exa_search",
    "exa_deep_lite": "exa_search",
    "exa_find_similar": "exa_find_similar",
    "exa_contents": "exa_contents",
    "exa_answer": "exa_answer",
    # Jina Reader (3 endpoints)
    "jina_page_content": "jina_reader",
    "jina_dtc_review": "jina_reader",
    "jina_news_article": "jina_reader",
    # OSINT (2 endpoints)
    "sherlock_username": "sherlock",
    "sherlock_username_search": "sherlock",
    "maigret_username": "maigret",
    "maigret_username_profile": "maigret",
    # X/Twitter twscrape (3 endpoints)
    "twscrape_search": "twscrape_search",
    "twscrape_user_tweets": "twscrape_user_tweets",
    "twscrape_trends": "twscrape_trends",
    # Document to Markdown (1 endpoint)
    "anydoc_file_to_markdown": "anydoc_file_to_markdown",
     # Bilibili / B站 (3 endpoints)
     "bilibili_video_search": "bilibili_video_search",
     "bilibili_user_videos": "bilibili_user_videos",
     "bilibili_video_comments": "bilibili_video_comments",
    # 微博 (3 endpoints)
    "weibo_keyword_search": "weibo_keyword_search",
    "weibo_user_posts": "weibo_user_posts",
    "weibo_trending_topics": "weibo_trending_topics",
    # 知乎 (3 endpoints)
    "zhihu_question_answers": "zhihu_question_answers",
    "zhihu_keyword_search": "zhihu_keyword_search",
    "zhihu_hot_list": "zhihu_hot_list",
    # SERP 搜索引擎 (3 endpoints)
    "baidu_search": "baidu_search",
    "baidu_search_results": "baidu_search",
    "bing_search": "bing_search",
    "bing_search_results": "bing_search",
    "duckduckgo_search": "duckduckgo_search",
    "duckduckgo_search_results": "duckduckgo_search",
    # 快手 (2 endpoints)
    "kuaishou_video_search": "kuaishou_video_search",
    "kuaishou_user_videos": "kuaishou_user_videos",
    # Firecrawl (3 endpoints)
    "firecrawl_crawl": "firecrawl_crawl",
    "firecrawl_extract": "firecrawl_extract",
    "firecrawl_batch_scrape": "firecrawl_batch_scrape",
    # 技术博客 (3 endpoints)
    "devto_articles": "devto_articles",
    "devto_articles_search": "devto_articles",
    "juejin_articles": "juejin_articles",
    "juejin_articles_search": "juejin_articles",
    "substack_posts": "substack_posts",
    # 技术栈检测 (1 endpoint)
    "tech_stack_detect": "tech_stack_detect",
    # SpiderFoot OSINT (3 + 6 extended endpoints)
    "spiderfoot_domain_osint": "spiderfoot_domain_osint",
    "spiderfoot_ip_osint": "spiderfoot_ip_osint",
    "spiderfoot_email_osint": "spiderfoot_email_osint",
    "spiderfoot_subdomain_enum": "spiderfoot_subdomain_enum",
    "spiderfoot_threat_intel": "spiderfoot_threat_intel",
    "spiderfoot_breach_check": "spiderfoot_breach_check",
    "spiderfoot_cert_transparency": "spiderfoot_cert_transparency",
    "spiderfoot_dark_web": "spiderfoot_dark_web",
    "spiderfoot_attack_surface": "spiderfoot_attack_surface",
    # BestBlogs (1 endpoint)
    "bestblogs_articles": "bestblogs_articles",
    # Blackbird OSINT (2 endpoints)
    "blackbird_email_osint": "blackbird_email_osint",
    "blackbird_username_osint": "blackbird_username_osint",
    # Aliens Eye ML-OSINT (7 endpoints)
    "aliens_eye_basic":     "aliens_eye_basic",
    "aliens_eye_advanced":  "aliens_eye_advanced",
    "aliens_eye_correlate": "aliens_eye_correlate",
    "aliens_eye_recurse":   "aliens_eye_recurse",
    "aliens_eye_domain":    "aliens_eye_domain",
    "aliens_eye_batch":     "aliens_eye_batch",
    "aliens_eye_selfcheck": "aliens_eye_selfcheck",
    # Robin 暗网 OSINT (3 endpoints)
    "robin_darkweb_search":   "robin_darkweb_search",
    "robin_darkweb_username": "robin_darkweb_username",
    "robin_darkweb_email":    "robin_darkweb_email",
    "browser_use_task":       "browser_use_task",
    # Hacker News (3 endpoints)
    "hackernews_front_page":  "hackernews_front_page",
    "hackernews_search":      "hackernews_search",
    "hackernews_user":        "hackernews_user",
    # npm registry (2 endpoints)
    "npm_package":            "npm_package",
    "npm_search":             "npm_search",
    # PyPI (2 endpoints)
    "pypi_package":           "pypi_package",
    "pypi_search":            "pypi_search",
    # crates.io Rust 包 (2 endpoints)
    "crates_package":         "crates_package",
    "crates_search":          "crates_search",
    # RubyGems Ruby 包 (2 endpoints)
    "rubygems_package":       "rubygems_package",
    "rubygems_search":        "rubygems_search",
    # Go 包 (2 endpoints)
    "go_package":             "go_package",
    "go_search":              "go_search",
    # Packagist PHP 包 (2 endpoints)
    "packagist_package":      "packagist_package",
    "packagist_search":       "packagist_search",
    # NuGet .NET 包 (2 endpoints)
    "nuget_package":          "nuget_package",
    "nuget_search":           "nuget_search",
    # pub.dev Dart/Flutter 包 (2 endpoints)
    "pubdev_package":         "pubdev_package",
    "pubdev_search":          "pubdev_search",
}

_COLLECTOR_TEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "firecrawl_crawl":            {"url": "https://example.com", "max_pages": 2},
    "firecrawl_extract":          {"url": "https://example.com", "prompt": "Extract title and description"},
    "firecrawl_batch_scrape":     {"urls": ["https://example.com", "https://httpbin.org/get"]},
    "autoscraper_enhanced_web":   {"url": "https://books.toscrape.com", "wanted_list": ["Books to Scrape"]},
    "spiderfoot_cert_transparency": {"target": "example.com"},
    "spiderfoot_dark_web":          {"target": "example.com"},
    "spiderfoot_attack_surface":    {"target": "example.com"},
    "baidu_search":               {"keyword": "python"},
    "bing_search":                {"keyword": "python"},
    "duckduckgo_search":          {"keyword": "python"},
    "devto_articles":             {"keyword": "python"},
    "juejin_articles":            {"keyword": "python"},
    "sherlock":                   {"username": "github"},
    "maigret":                    {"username": "github"},
    "aliens_eye_basic":           {"username": "github"},
    "aliens_eye_advanced":        {"username": "github"},
    "aliens_eye_correlate":       {"username": "github"},
    "aliens_eye_recurse":         {"username": "github", "depth": 1},
    "aliens_eye_domain":          {"username": "github"},
    "aliens_eye_batch":           {"usernames": "github,torvalds"},
    "aliens_eye_selfcheck":       {},
    "robin_darkweb_search":       {"keyword": "data breach", "max_results": 5},
    "robin_darkweb_username":     {"username": "testuser", "max_results": 5},
    "robin_darkweb_email":        {"email": "test@example.com", "max_results": 5},
    "browser_use_task":           {"task": "Extract the page title and main heading", "url": "https://example.com", "max_steps": 5},
    "hackernews_front_page":      {"max_items": 10},
    "hackernews_search":          {"query": "python", "max_items": 10},
    "hackernews_user":            {"username": "pg", "max_items": 10},
    "npm_package":                {"package": "react"},
    "npm_search":                 {"query": "typescript", "max_items": 10},
    "pypi_package":               {"package": "requests"},
    "pypi_search":                {"query": "fastapi", "max_items": 10},
    "crates_package":             {"package": "serde"},
    "crates_search":              {"query": "async", "max_items": 10},
    "rubygems_package":           {"package": "rails"},
    "rubygems_search":            {"query": "web", "max_items": 10},
    "go_package":                 {"package": "github.com/gin-gonic/gin"},
    "go_search":                  {"query": "http server", "max_items": 10},
    "packagist_package":          {"package": "laravel/framework"},
    "packagist_search":           {"query": "http", "max_items": 10},
    "nuget_package":              {"package": "Newtonsoft.Json"},
    "nuget_search":               {"query": "json", "max_items": 10},
    "pubdev_package":             {"package": "http"},
    "pubdev_search":              {"query": "flutter", "max_items": 10},
}

# Apify endpoint → (actor_id, base_input_defaults)
# quick-collect 级别的采集开关，绝不能传给 Actor：Actor 的 inputSchema 是
# additionalProperties:false，多一个键就整单 400。除此之外的入参一律透传。
# 曾把 query/url/keyword/... 也列进这个集合，结果调用方传的 query 被静默丢弃
# → 上游报 "Field input.query is required"（2026-10-09 实测 apify_rag_web_browser）。
_APIFY_META_KEYS = frozenset(
    {"maxItems", "max_items", "max_total_charge_usd", "run_timeout_seconds"}
)


def build_apify_actor_input(base_input: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """把调用方入参并到端点的缺省 Actor 入参上。

    只有采集开关（``_APIFY_META_KEYS``）留在 quick-collect 层，其余键一律透传给
    Actor。Actor 的 inputSchema 是 ``additionalProperties: false``：漏传必填键或
    多传未知键都会让整单 400，所以这里刻意不做白名单过滤，让上游的报错
    （"Field input.X is required" / "Property input.X is not allowed"）直接暴露给调用方。
    """
    return {**base_input, **{k: v for k, v in params.items() if k not in _APIFY_META_KEYS}}


_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {
    # Social
    "apify_tiktok_scraper": ("clockworks/tiktok-scraper", {}),
    "apify_tiktok_comments_scraper": ("clockworks/tiktok-comments-scraper", {}),
    "apify_tiktok_shop_scraper": ("clockworks/tiktok-shop-scraper", {"keywords": ["laptop"]}),
    "apify_instagram_scraper": ("apify/instagram-scraper", {}),
    "apify_instagram_profile_scraper": (
        "apify/instagram-profile-scraper",
        {"usernames": ["humansofny"]},
    ),
    "apify_youtube_scraper": (
        "streamers/youtube-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/@mkbhd"}], "maxResults": 3},
    ),
    "apify_youtube_comments_scraper": (
        "streamers/youtube-comments-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}], "maxComments": 5},
    ),
    "apify_reddit_scraper": ("trudax/reddit-scraper-lite", {}),
    "apify_facebook_posts_scraper": (
        "apify/facebook-posts-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/humansofnewyork/"}]},
    ),
    "apify_facebook_comments_scraper": (
        "apify/facebook-comments-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/humansofnewyork/"}]},
    ),
    "apify_linkedin_company_posts_scraper": ("harvestapi/linkedin-company-posts", {}),
    "apify_linkedin_jobs_scraper": (
        "freshdata/linkedin-job-scraper",
        {"keywords": "Python Developer"},
    ),
    "apify_linkedin_company_employees_scraper": (
        "apimaestro/linkedin-company-employees-scraper-no-cookies",
        {
            "identifier": "https://www.linkedin.com/company/python-software-foundation/",
            "max_employees": 3,
        },
    ),
    "apify_linkedin_company_search_scraper": (
        "khadinakbar/linkedin-company-search-scraper",
        # 该 Actor 的 keywords 要**字符串**（传数组会 400 must be string）
        {"keywords": "software company", "maxResults": 3},
    ),
    "apify_x_tweet_scraper": ("apidojo/tweet-scraper", {}),
    "apify_threads_profile_scraper": (
        "apify/threads-profile-api-scraper",
        {"usernames": ["guinnessworldrecords"]},
    ),
    "apify_threads_posts_scraper": (
        "futurizerush/meta-threads-scraper",
        {"mode": "user", "usernames": ["zuck"], "max_posts": 10},
    ),
    # E-commerce
    "apify_amazon_product_scraper": (
        "junglee/amazon-crawler",
        {"categoryOrProductUrls": [{"url": "https://www.amazon.com/dp/B09G9FPHY6"}]},
    ),
    "apify_amazon_reviews_scraper": (
        "junglee/amazon-reviews-scraper",
        {"productUrls": [{"url": "https://www.amazon.com/dp/B09G9FPHY6"}], "maxReviews": 5},
    ),
    "apify_walmart_product_scraper": (
        "e-commerce/walmart-product-detail-scraper",
        {"startUrls": [{"url": "https://walmart.com/search?q=tshirt"}], "maxProductsPerStartUrl": 3},
    ),
    "apify_walmart_reviews_scraper": ("e-commerce/walmart-reviews-scraper", {}),
    "apify_temu_products_scraper": (
        "amit123/temu-products-scraper",
        # maxResults 的下限是 20，传 3 会被 400 拒绝
        {"searchQueries": ["women dress"], "maxResults": 20},
    ),
    "apify_shein_product_scraper": (
        "shahidirfan/shein-product-scraper",
        {"startUrl": "https://us.shein.com/New-in-Dresses-sc-00020466.html",
         "results_wanted": 3},
    ),

    "apify_aliexpress_products_scraper": (
        "devcake/aliexpress-products-scraper",
        {"searchQueries": ["laptop stand"]},
    ),
    "apify_ebay_product_scraper": (
        "dtrungtin/ebay-items-scraper",
        {
            "startUrls": [{"url": "https://www.ebay.com/sch/i.html?_nkw=laptop"}],
            "maxItems": 5,
            "proxyConfig": {"useApifyProxy": True},
        },
    ),
    "apify_ebay_sold_listings_scraper": (
        "caffein.dev/ebay-sold-listings",
        {"keywords": ["laptop"], "count": 3},
    ),
    "apify_etsy_scraper": ("automation-lab/etsy-scraper", {"searchQuery": "handmade mug"}),
    "apify_shopify_scraper": (
        "clearpath/shopify-store-leads",
        {"query": "sneakers", "maxItems": 3},
    ),
    # Google
    "apify_google_search_scraper": (
        "apify/google-search-scraper",
        {"queries": "python programming\nai tools", "maxPagesPerQuery": 1},
    ),
    "apify_google_maps_scraper": ("compass/crawler-google-places", {}),
    "apify_google_maps_reviews_scraper": (
        "compass/Google-Maps-Reviews-Scraper",
        {
            "startUrls": [{"url": "https://www.google.com/maps/place/Yellowstone+National+Park/@44.5857951,-110.5140571,9z/data=!3m1!4b1!4m5!3m4!1s0x5351e55555555555:0xaca8f930348fe1bb!8m2!3d44.427963!4d-110.588455?hl=en-GB"}],
            "maxReviews": 3,
        },
    ),
    "apify_google_trends_scraper": ("apify/google-trends-scraper", {}),
    "apify_google_news_media_search": (
        "data_xplorer/google-news-scraper-fast",
        {"keywords": [], "maxArticles": 10, "timeframe": "7d"},
    ),
    "apify_google_news_scraper": ("data_xplorer/google-news-scraper-fast", {}),
    "apify_google_ai_overviews_scraper": (
        "apify/google-ai-overviews-scraper",
        {"queries": "python programming"},
    ),
    # AI Search
    "apify_perplexity_search_scraper": (
        "apify/perplexity-search-scraper",
        {"queries": "what is python"},
    ),
    "apify_chatgpt_search_scraper": (
        "apify/chatgpt-search-scraper",
        {"queries": "what is python"},
    ),
    # gemini-scraper is deprecated — fall back to google-search-scraper
    "apify_gemini_search_scraper": (
        "apify/google-search-scraper",
        {"queries": "python programming", "maxPagesPerQuery": 1},
    ),
    # Ads
    "apify_google_ads_scraper": (
        "lexis-solutions/google-ads-scraper",
        {"startUrls": [{"url": "https://adstransparency.google.com/advertiser/AR18135649662495883265?region=anywhere"}], "maxItems": 3},
    ),
    "apify_facebook_ads_scraper": (
        "apify/facebook-ads-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US&q=python&search_type=keyword_unordered"}]},
    ),
    "apify_tiktok_ads_scraper": ("lexis-solutions/tiktok-ads-scraper", {}),
    "apify_pinterest_ads_scraper": (
        "shahidirfan/Pinterest-Ads-Scraper",
        {"country": "FR", "results_limit": 5},
    ),
    # snapchat-ads-library is deprecated — no public replacement found; disable
    "apify_snapchat_ads_scraper": (
        "apify/google-search-scraper",
        {"queries": "site:snap.com/en-US/ad-policies python", "maxPagesPerQuery": 1},
    ),
    # B2B / Review / Community
    "apify_trustpilot_reviews_scraper": ("memo23/trustpilot-scraper-ppe", {}),
    "apify_appstore_reviews_scraper": ("johnvc/apple-app-store-reviews-api", {}),
    "apify_google_play_reviews_scraper": (
        "neatrat/google-play-store-reviews-scraper",
        {"appIdOrUrl": "com.google.android.apps.maps", "maxReviews": 5},
    ),
    "apify_tripadvisor_reviews_scraper": ("maxcopell/tripadvisor-reviews", {}),
    "apify_booking_scraper": (
        "voyager/booking-scraper",
        {"startUrls": [{"url": "https://www.booking.com/hotel/gb/the-z-hotel-victoria.html"}]},
    ),
    "apify_airbnb_scraper": (
        "tri_angle/airbnb-scraper",
        {"startUrls": [{"url": "https://www.airbnb.com/s/New-York--NY/homes?checkin=2025-12-01&checkout=2025-12-07&adults=2"}], "maxResults": 3},
    ),
    # crunchbase-scraper is deprecated — use google-search-scraper fallback
    "apify_crunchbase_scraper": (
        "apify/google-search-scraper",
        {"queries": "site:crunchbase.com openai", "maxPagesPerQuery": 1},
    ),
    "apify_glassdoor_scraper": (
        "memo23/glassdoor-scraper-ppr",
        {
            "command": "reviews",
            "startUrls": [{"url": "https://www.glassdoor.fr/Avis/Aza%C3%A9-Avis-E1360610.htm"}],
            "maxItems": 3,
        },
    ),
    "apify_hacker_news_scraper": ("onescales/hacker-news-data", {}),
    "apify_bluesky_scraper": (
        "fatihtahta/All-In-One-Bluesky-Scraper",
        {"actionToPerform": "searchPosts", "queries": ["atproto.com"], "maxItems": 3},
    ),
    "apify_indeed_jobs_scraper": ("misceres/indeed-scraper", {}),
    # Media account monitoring
    "apify_instagram_media_profile_scraper": (
        "apify/instagram-profile-scraper",
        {"usernames": ["humansofny"]},
    ),
    "apify_tiktok_media_profile_scraper": (
        "clockworks/tiktok-scraper",
        {"profiles": ["https://www.tiktok.com/@apple"], "resultsPerPage": 3},
    ),
    "apify_youtube_media_channel_scraper": (
        "streamers/youtube-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/@mkbhd"}], "maxResults": 3},
    ),
    "apify_facebook_media_page_scraper": (
        "apify/facebook-posts-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/humansofnewyork/"}]},
    ),
    "apify_x_media_account_scraper": ("apidojo/tweet-scraper", {}),
    # Open Web
    "apify_website_content_crawler": (
        "apify/website-content-crawler",
        {
            "startUrls": [{"url": "https://example.com"}],
            "maxCrawlPages": 2,
            "proxyConfiguration": {"useApifyProxy": True},
        },
    ),
    "apify_rag_web_browser": (
        "apify/rag-web-browser",
        {"query": "python programming", "maxResults": 1},
    ),
    "apify_tiktok_transcript_extractor": (
        "clockworks/tiktok-transcript-extractor",
        {"postURLs": ["https://www.tiktok.com/@tiktok/video/7106594312292453675"]},
    ),
    "apify_youtube_transcript_scraper": ("johnvc/youtubetranscripts", {}),
    "apify_tiktok_creative_center": ("doliz/tiktok-creative-center-scraper", {}),
    "apify_similarweb_scraper": (
        "curious_coder/similarweb-scraper",
        {"domains": ["apify.com"]},
    ),
    "apify_tiktok_shop_search_scraper": (
        "pratikdani/tiktok-shop-search-scraper",
        {"keyword": "laptop", "country_code": "US"},
    ),
    "apify_target_products_scraper": (
        "bovi/target-products",
        {"searchQueries": ["coffee maker"], "maxProductsPerSearch": 3},
    ),
    "apify_facebook_marketplace_scraper": (
        "apify/facebook-marketplace-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/marketplace/search?query=laptop"}]},
    ),
    "apify_1688_product_search": (
        "ecomscrape/1688-product-search-scraper",
        {"keyword": "wireless earbuds", "max_items_per_url": 20},
    ),
    "apify_1688_product_detail": (
        "dltik/1688-scraper",
        {"mode": "detail", "inputs": ["https://detail.1688.com/offer/642952568827.html"]},
    ),
    "apify_1688_advanced": (
        "dltik/1688-scraper",
        {
            "mode": "search",
            "inputs": ["wireless earbuds"],
            "maxResults": 20,
            "shippingCountry": "US",
        },
    ),
    "apify_alibaba_product_search": (
        "zen-studio/alibaba-scraper",
        {"resultType": "products", "keywords": ["led lights"], "maxResults": 5,
         "shipToCountry": "US"},
    ),
    "apify_alibaba_product_detail": (
        "xtracto/alibaba-product-scraper",
        {"productUrls": [{"url": "https://www.alibaba.com/product-detail/WATA-In-Ear-Waterproof-Sport-Earbud_1601685362945.html"}]},
    ),
    "apify_amazon_bestsellers": (
        "junglee/amazon-bestsellers",
        {
            "categoryUrls": ["https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/"],
            "maxItemsPerStartUrl": 5,
        },
    ),
    "apify_amazon_competitor_research": (
        "samstorm/amazon-competitor-research-scraper",
        {"asins": ["B08N5WRWNW"], "marketplace": "amazon.com"},
    ),
    "apify_amazon_bsr_tracker": (
        "marketplace-scrapers/amazon-bsr-scraper",
        {"asins": ["B08N5WRWNW"], "marketplaces": ["amazon.com"]},
    ),
    "apify_amazon_price_tracker": (
        "ramsford/ecommerce-price-tracker",
        {"products": [{"url": "https://www.amazon.com/dp/B08N5WRWNW"}]},
    ),
    "apify_aliexpress_product_search_v2": (
        "skystone_labs/aliexpress-product-scraper",
        {"queries": ["wireless earbuds"], "shipTo": "US", "currency": "USD", "maxPages": 3},
    ),
    "apify_shopify_products_monitor": (
        "trovevault/shopify-products-scraper",
        {"domains": ["allbirds.com"], "maxProducts": 5},
    ),

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
    # 必须先确认 project 存在：sources/tasks 都有 project_id 外键，直接插入会撞
    # ForeignKeyViolation → 500 并把原始 SQL 栈回给调用方（2026-10-09 生产实测）。
    if await get_project(session, workspace.id, body.project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown project_id: {body.project_id}",
        )

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

    collector_defaults = _COLLECTOR_TEST_DEFAULTS.get(collector_type)
    if collector_defaults is not None:
        config = {"endpoint_type": body.endpoint_type, **collector_defaults, **body.params}

    apify_defaults = _APIFY_ENDPOINT_DEFAULTS.get(body.endpoint_type)
    if apify_defaults is not None:
        actor_id, base_input = apify_defaults
        actor_input = build_apify_actor_input(base_input, body.params)
        config = {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": body.params.get("maxItems") or body.params.get("max_items") or 10,
            "max_total_charge_usd": body.params.get(
                "max_total_charge_usd", DEFAULT_MAX_TOTAL_CHARGE_USD
            ),
            "run_timeout_seconds": body.params.get("run_timeout_seconds", 600),
        }

    try:
        validated = validate_collector_config(collector_type, config)
    except (CollectorConfigError, CollectorNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collector config: {exc}",
        ) from exc
    # Validators return a whitelist of collection parameters only. Keep the
    # endpoint_type: dataset platform attribution walks task.config["endpoint_type"].
    validated.setdefault("endpoint_type", body.endpoint_type)

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
