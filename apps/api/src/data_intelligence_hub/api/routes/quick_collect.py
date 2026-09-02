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
}

# Apify endpoint → (actor_id, base_input_defaults)
_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {
    # Social
    "apify_tiktok": ("clockworks/free-tiktok-scraper", {}),
    "apify_tiktok_scraper": ("clockworks/tiktok-scraper", {}),
    "apify_tiktok_comments_scraper": ("clockworks/tiktok-comments-scraper", {}),
    "apify_tiktok_shop_scraper": ("clockworks/tiktok-shop-scraper", {"keywords": ["laptop"]}),
    "apify_instagram": ("apify/instagram-scraper", {}),
    "apify_instagram_scraper": ("apify/instagram-scraper", {}),
    "apify_instagram_profile_scraper": ("apify/instagram-profile-scraper", {}),
    "apify_instagram_hashtag_scraper": ("apify/instagram-hashtag-scraper", {}),
    "apify_youtube": ("streamers/youtube-scraper", {}),
    "apify_youtube_scraper": (
        "streamers/youtube-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/@mkbhd"}], "maxVideos": 3},
    ),
    "apify_youtube_comments_scraper": (
        "streamers/youtube-comments-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}], "maxComments": 5},
    ),
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
    "apify_amazon_product_scraper": (
        "junglee/amazon-crawler",
        {"categoryOrProductUrls": [{"url": "https://www.amazon.com/dp/B09G9FPHY6"}]},
    ),
    "apify_amazon_review_scraper": ("junglee/amazon-review-scraper", {}),
    "apify_amazon_reviews_scraper": (
        "junglee/amazon-reviews-scraper",
        {"productUrls": [{"url": "https://www.amazon.com/dp/B09G9FPHY6"}], "maxReviews": 5},
    ),
    "apify_walmart_scraper": ("apify/walmart-scraper", {}),
    "apify_walmart_product_scraper": ("e-commerce/walmart-product-detail-scraper", {}),
    "apify_walmart_reviews_scraper": ("e-commerce/walmart-reviews-scraper", {}),
    "apify_temu_products_scraper": (
        "amit123/temu-products-scraper",
        {"searchQueries": ["phone case"]},
    ),
    "apify_shein_product_scraper": (
        "shahidirfan/shein-product-scraper",
        {"startUrl": "https://us.shein.com/New-in-Dresses-sc-00020466.html"},
    ),

    "apify_aliexpress_products_scraper": (
        "devcake/aliexpress-products-scraper",
        {"searchQueries": ["laptop stand"]},
    ),
    "apify_ebay_scraper": ("dtrungtin/ebay-items-scraper", {}),
    "apify_ebay_product_scraper": ("dtrungtin/ebay-items-scraper", {}),
    "apify_ebay_sold_listings_scraper": ("caffein.dev/ebay-sold-listings", {}),
    "apify_etsy_scraper": ("automation-lab/etsy-scraper", {"searchQuery": "handmade mug"}),
    "apify_shopify_scraper": (
        "clearpath/shopify-store-leads",
        {"searchQuery": "sneakers", "maxItems": 3},
    ),
    # Google
    "apify_google_search_scraper": (
        "apify/google-search-scraper",
        {"queries": "python programming\nai tools", "maxPagesPerQuery": 1, "resultsPerPage": 5},
    ),
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
    "apify_google_ai_overviews_scraper": (
        "apify/google-ai-overviews-scraper",
        {"queries": "python programming", "resultsPerPage": 3},
    ),
    # AI Search
    "apify_perplexity_scraper": ("apify/perplexity-scraper", {}),
    "apify_perplexity_search_scraper": (
        "apify/perplexity-search-scraper",
        {"queries": "what is python"},
    ),
    "apify_chatgpt_scraper": ("apify/chatgpt-scraper", {}),
    "apify_chatgpt_search_scraper": (
        "apify/chatgpt-search-scraper",
        {"queries": "what is python"},
    ),
    # gemini-scraper is deprecated — fall back to google-search-scraper
    "apify_gemini_scraper": (
        "apify/google-search-scraper",
        {"queries": "site:gemini.google.com python programming", "maxPagesPerQuery": 1, "resultsPerPage": 3},
    ),
    "apify_gemini_search_scraper": (
        "apify/google-search-scraper",
        {"queries": "python programming", "maxPagesPerQuery": 1, "resultsPerPage": 3},
    ),
    # Ads
    "apify_google_ads_transparency_scraper": ("apify/google-ads-transparency-scraper", {}),
    "apify_google_ads_scraper": (
        "lexis-solutions/google-ads-scraper",
        {"startUrls": [{"url": "https://adstransparency.google.com/advertiser/AR01694614460596224001?region=anywhere"}]},
    ),
    "apify_meta_ads_library_scraper": ("apify/meta-ads-library", {}),
    "apify_facebook_ads_scraper": (
        "apify/facebook-ads-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US&q=python&search_type=keyword_unordered"}]},
    ),
    "apify_tiktok_ads_library_scraper": ("apify/tiktok-ads-library", {}),
    "apify_tiktok_ads_scraper": ("lexis-solutions/tiktok-ads-scraper", {}),
    "apify_linkedin_ads_scraper": ("apify/linkedin-ads-scraper", {}),
    "apify_reddit_ads_scraper": ("apify/reddit-ads-scraper", {}),
    "apify_x_ads_transparency_scraper": ("apify/x-ads-transparency-scraper", {}),
    "apify_pinterest_ads_scraper": (
        "shahidirfan/Pinterest-Ads-Scraper",
        {"keyword": "fashion", "country": "FR"},
    ),
    # snapchat-ads-library is deprecated — no public replacement found; disable
    "apify_snapchat_ads_scraper": (
        "apify/google-search-scraper",
        {"queries": "site:snap.com/en-US/ad-policies python", "maxPagesPerQuery": 1, "resultsPerPage": 3},
    ),
    # B2B / Review / Community
    "apify_trustpilot_scraper": ("apify/trustpilot-scraper", {}),
    "apify_trustpilot_reviews_scraper": ("memo23/trustpilot-scraper-ppe", {}),
    "apify_appstore_scraper": ("apify/apple-app-store-scraper", {}),
    "apify_appstore_reviews_scraper": ("johnvc/apple-app-store-reviews-api", {}),
    "apify_google_play_reviews_scraper": (
        "neatrat/google-play-store-reviews-scraper",
        {"appIdOrUrl": "com.google.android.apps.maps", "maxReviews": 5},
    ),
    "apify_tripadvisor_scraper": ("maxcopell/tripadvisor", {}),
    "apify_tripadvisor_reviews_scraper": ("maxcopell/tripadvisor-reviews", {}),
    "apify_yelp_scraper": (
        "tri_angle/yelp-scraper",
        {"searchTerm": "coffee", "location": "New York"},
    ),
    "apify_booking_scraper": (
        "voyager/booking-scraper",
        {"startUrls": [{"url": "https://www.booking.com/hotel/gb/the-z-hotel-victoria.html"}]},
    ),
    "apify_airbnb_scraper": (
        "tri_angle/airbnb-scraper",
        {"startUrls": [{"url": "https://www.airbnb.com/s/New-York--NY/homes?checkin=2025-12-01&checkout=2025-12-07&adults=2"}], "maxItems": 3},
    ),
    # crunchbase-scraper is deprecated — use google-search-scraper fallback
    "apify_crunchbase_scraper": (
        "apify/google-search-scraper",
        {"queries": "site:crunchbase.com openai", "maxPagesPerQuery": 1, "resultsPerPage": 5},
    ),
    "apify_producthunt_scraper": ("apify/product-hunt-scraper", {}),
    "apify_product_hunt_scraper": ("happitap/product-hunt-daily-launch-scraper", {}),
    "apify_glassdoor_scraper": ("memo23/glassdoor-scraper-ppr", {}),
    "apify_hacker_news_scraper": ("onescales/hacker-news-data", {}),
    "apify_bluesky_scraper": (
        "fatihtahta/All-In-One-Bluesky-Scraper",
        {"profiles": ["atproto.com"], "maxPostsPerProfile": 3},
    ),
    "apify_telegram_scraper": ("danielmilevski9/telegram-channel-scraper", {}),
    "apify_indeed_scraper": ("apify/indeed-scraper", {}),
    "apify_indeed_jobs_scraper": ("misceres/indeed-scraper", {}),
    # Media account monitoring
    "apify_instagram_media_profile_scraper": ("apify/instagram-profile-scraper", {}),
    "apify_tiktok_media_profile_scraper": (
        "clockworks/tiktok-scraper",
        {"profiles": ["https://www.tiktok.com/@apple"], "resultsPerPage": 3},
    ),
    "apify_youtube_media_channel_scraper": (
        "streamers/youtube-scraper",
        {"startUrls": [{"url": "https://www.youtube.com/@mkbhd"}], "maxVideos": 3},
    ),
    "apify_facebook_media_page_scraper": ("apify/facebook-posts-scraper", {}),
    "apify_x_media_account_scraper": ("apidojo/tweet-scraper", {}),
    "apify_pinterest_media_profile_scraper": ("danielmilevski9/pinterest-crawler", {}),
    # Open Web
    "apify_website_content_crawler": ("apify/website-content-crawler", {}),
    "apify_web_scraper": ("apify/web-scraper", {}),
    "apify_rag_web_browser": ("apify/rag-web-browser", {}),
    "apify_tiktok_transcript_extractor": (
        "clockworks/tiktok-transcript-extractor",
        {"postURLs": ["https://www.tiktok.com/@tiktok/video/7106594312292453675"]},
    ),
    "apify_youtube_transcript_scraper": ("johnvc/youtubetranscripts", {}),
    "apify_tiktok_creative_center": ("doliz/tiktok-creative-center-scraper", {}),
    "apify_facebook_group_scraper": ("whoareyouanas/facebook-group-scraper", {}),
    "apify_similarweb_scraper": (
        "curious_coder/similarweb-scraper",
        {"domains": ["apify.com"]},
    ),
    "apify_tiktok_shop_search_scraper": (
        "pratikdani/tiktok-shop-search-scraper",
        {"keyword": "laptop", "country_code": "US"},
    ),
    "apify_target_products_scraper": ("bovi/target-products", {}),
    "apify_facebook_marketplace_scraper": (
        "apify/facebook-marketplace-scraper",
        {"startUrls": [{"url": "https://www.facebook.com/marketplace/search?query=laptop"}]},
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
        _meta_keys = {"maxItems", "max_items", "max_total_charge_usd", "run_timeout_seconds",
                      "query", "url", "keyword", "domain", "app_id", "asin", "location",
                      "username", "profile", "handle"}
        actor_input = {
            **base_input,
            **{k: v for k, v in body.params.items()
               if k not in _meta_keys and k not in base_input},
        }
        config = {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": body.params.get("maxItems") or body.params.get("max_items") or 10,
            "max_total_charge_usd": body.params.get("max_total_charge_usd", 1.0),
            "run_timeout_seconds": body.params.get("run_timeout_seconds", 600),
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
