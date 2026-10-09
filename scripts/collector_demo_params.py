"""各采集端点 live 测试用的最小演示参数（单一事实源）。

被 scripts/test_all_collectors.py 与 scripts/verify_platform_live.py 共用。
每个 provider 用最简单的无敏感数据参数。
"""
from __future__ import annotations

from typing import Any

DEMO_PARAMS: dict[str, dict[str, Any]] = {
    # ── TikHub ────────────────────────────────────────────────────────────────
    "tikhub_tiktok_video_search":          {"keyword": "python"},
    "tikhub_tiktok_user_posts":            {"unique_id": "tiktok"},
    "tikhub_tiktok_hashtag_posts":         {"ch_id": "7340824418278440993"},
    "tikhub_instagram_search":             {"keyword": "python"},
    "tikhub_instagram_user_posts":         {"user_id": "25025320"},
    "tikhub_xiaohongshu_search":           {"keyword": "python"},
    "tikhub_youtube_search":               {"keyword": "python tutorial"},
    "tikhub_youtube_channel_videos":       {"channel_id": "UC8butISFwT-Wl7EV0hUK0BQ"},
    "tikhub_reddit_search":                {"keyword": "python"},
    "tikhub_reddit_subreddit_posts":       {"subreddit": "python"},
    "tikhub_x_search":                     {"keyword": "python"},
    "tikhub_x_user_tweets":               {"username": "python"},
    "tikhub_threads_search":               {"keyword": "python"},
    "tikhub_threads_user_posts":           {"user_id": "63055343223"},
    "tikhub_threads_post_comments":        {"post_id": "3928882651670873164"},
    "tikhub_linkedin_user_posts":          {"username": "williamhgates"},
    "tikhub_linkedin_company_profile":     {"company_username": "microsoft"},
    "tikhub_linkedin_company_posts":       {"company_username": "microsoft"},
    "tikhub_linkedin_search_jobs":         {"keyword": "data engineer"},
    "tikhub_linkedin_job_detail":          {"job_id": "3768164426"},
    "tikhub_linkedin_post_comments":       {"post_urn": "7234567890123456"},
    "tikhub_lemon8_search":               {"keyword": "python"},
    "tikhub_lemon8_user_posts":           {"user_id": "6776100267084940294"},
    "tikhub_lemon8_trending":             {},
    "tikhub_tiktok_ads_search":           {"material_id": "7182310470102122497"},
    "tikhub_tiktok_top_ads":             {},
    "tikhub_tiktok_shop_products":        {"keyword": "phone case"},
    "tikhub_tiktok_creator_info":         {"unique_id": "tiktok"},
    "tikhub_instagram_post_comments":     {"shortcode": "DMVbQ0MAzn8"},
    "tikhub_youtube_video_comments":      {"video_id": "dQw4w9WgXcQ"},
    "tikhub_reddit_post_comments":        {"post_id": "t3_1x0wpat"},
    "tikhub_tiktok_live_search":          {"keyword": "music"},
    "tikhub_tiktok_live_room_detail":     {"room_id": "7694650101042170654"},
    "tikhub_tiktok_live_user":            {"unique_id": "tiktok"},
    "tikhub_youtube_trending":            {},
    "tikhub_reddit_trending":             {},
    "tikhub_x_trending":                  {},
    "tikhub_tiktok_user_followers":       {"sec_user_id": "MS4wLjABAAAAJSeUGWT_kX5G9KuMcBscOt3abx3ymUBIblbLD3LSn6_NUj9hAdk1eeSM2WPdJs65"},
    "tikhub_instagram_user_followers":    {"user_id": "25025320"},
    "tikhub_x_user_followers":            {"username": "0xOrionVega"},
    "tikhub_tiktok_creator_insights":     {"unique_id": "tiktok"},
    "tikhub_tiktok_creator_insights_trend": {"unique_id": "tiktok"},
    "tikhub_tiktok_creator_account_health": {"unique_id": "tiktok"},
    "tikhub_tiktok_ads_detail":           {"ad_id": "7182310470102122497"},
    "tikhub_tiktok_ads_keyword_suggest":  {"keyword": "python"},
    "tikhub_douyin_video_search":         {"keyword": "python"},
    "tikhub_douyin_user_posts":           {"sec_user_id": "MS4wLjABAAAA1CK6ZDbjFQEuSSQGibnmuqebt8aC2oS9aQ6G4hEhy8ZjY7Q3FSNOJ8VXAADfXksN"},
    "tikhub_douyin_hot_search":           {},
    "tikhub_douyin_comments":             {"aweme_id": "7481996508087274811"},
    "tikhub_douyin_brand_hot_search":     {},
    "tikhub_wechat_search":               {"keyword": "python"},
    "tikhub_wechat_channels_video":       {"username": "v2_020302030405060708090a0b0c0d0e0f@finder"},
    "tikhub_weibo_search":                {"keyword": "python"},
    "tikhub_weibo_user_posts":            {"uid": "1669879400"},
    "tikhub_zhihu_search":                {"keyword": "python"},
    "tikhub_zhihu_question_answers":      {"question_id": "19550783"},
    "tikhub_kuaishou_search":             {"keyword": "python"},
    "tikhub_kuaishou_user_posts":         {"user_id": "1066390834"},
    # ── Apify (为每个 actor 提供最小有效输入) ─────────────────────────────
    # TikTok
    "apify_tiktok":                        {"profiles": ["tiktok"], "maxItems": 3},
    "apify_tiktok_scraper":                {"profiles": ["tiktok"], "maxItems": 3},
    "apify_tiktok_comments_scraper":       {"postURLs": ["https://www.tiktok.com/@tiktok/video/7106594312292453675"], "maxItems": 5},
    "apify_tiktok_shop_scraper":           {"keywords": ["phone case"], "maxItems": 3},
    "apify_tiktok_media_profile_scraper":  {"profiles": ["tiktok"], "maxItems": 3},
    "apify_tiktok_ads_library_scraper":    {"query": "python", "maxItems": 3},
    "apify_tiktok_ads_scraper":            {"keywords": ["python"], "maxItems": 3},
    "apify_tiktok_transcript_extractor":   {"postURLs": ["https://www.tiktok.com/@tiktok/video/7106594312292453675"]},
    "apify_tiktok_creative_center":        {"keywords": ["python"], "maxItems": 3},
    "apify_tiktok_shop_search_scraper":    {"keyword": "phone case", "maxItems": 3},
    # Instagram
    "apify_instagram":                     {"usernames": ["instagram"], "maxItems": 3},
    "apify_instagram_scraper":             {"usernames": ["instagram"], "maxItems": 3},
    "apify_instagram_profile_scraper":     {"usernames": ["instagram"], "maxItems": 3},
    "apify_instagram_hashtag_scraper":     {"hashtags": ["python"], "resultsPerPage": 3},
    "apify_instagram_media_profile_scraper": {"usernames": ["instagram"], "maxItems": 3},
    # YouTube
    "apify_youtube":                       {"searchKeywords": "python tutorial", "maxResults": 3},
    "apify_youtube_scraper":               {"searchKeywords": "python tutorial", "maxResults": 3},
    "apify_youtube_comments_scraper":      {"videoUrls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"], "maxComments": 5},
    "apify_youtube_comment_scraper":       {"videoUrls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"], "maxComments": 5},
    "apify_youtube_media_channel_scraper": {"channelUrls": ["https://www.youtube.com/@Python"], "maxResults": 3},
    "apify_youtube_transcript_scraper":    {"videoUrls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]},
    # Reddit
    "apify_reddit_scraper":                {"searches": ["python"], "maxItems": 5},
    "apify_reddit_community_monitor":      {"searches": [{"keyword": "python"}], "maxItems": 3},
    "apify_reddit_ads_scraper":            {"keywords": ["python"], "maxItems": 3},
    # Facebook
    "apify_facebook_posts_scraper":        {"startUrls": [{"url": "https://www.facebook.com/facebook"}], "maxItems": 3},
    "apify_facebook_comments_scraper":     {"startUrls": [{"url": "https://www.facebook.com/facebook"}], "maxItems": 3},
    "apify_facebook_group_scraper":        {"startUrls": [{"url": "https://www.facebook.com/groups/programming"}], "maxItems": 3},
    "apify_facebook_media_page_scraper":   {"startUrls": [{"url": "https://www.facebook.com/facebook"}], "maxItems": 3},
    "apify_facebook_ads_scraper":          {"adLibraryUrl": "https://www.facebook.com/ads/library/?q=python&active_status=all&ad_type=all&country=US", "maxItems": 3},
    "apify_facebook_marketplace_scraper":  {"searchQuery": "laptop", "maxItems": 3},
    # X/Twitter
    "apify_x_scraper":                     {"searchTerms": ["python programming"], "maxItems": 5},
    "apify_x_tweet_scraper":               {"startUrls": [{"url": "https://twitter.com/Python"}], "maxItems": 5},
    "apify_x_ads_transparency_scraper":    {"advertiserHandles": ["Python"], "maxItems": 3},
    "apify_x_media_account_scraper":       {"startUrls": [{"url": "https://twitter.com/Python"}], "maxItems": 3},
    # Threads
    "apify_threads_scraper":               {"usernames": ["zuck"], "maxPosts": 3},
    "apify_threads_profile_scraper":       {"usernames": ["zuck"], "maxPosts": 3},
    "apify_threads_posts_scraper":         {"usernames": ["zuck"], "maxPosts": 3},
    # Other Social
    "apify_bluesky_scraper":               {"queries": ["python"], "maxItems": 3},
    "apify_telegram_scraper":              {"channels": ["@python"], "maxItems": 3},
    "apify_snapchat_scraper":              {"usernames": ["python"], "maxItems": 3},
    "apify_snapchat_profile_scraper":      {"usernames": ["python"], "maxItems": 3},
    "apify_snapchat_ads_scraper":          {"keywords": ["python"], "maxItems": 3},
    "apify_pinterest_scraper":             {"searchKeywords": ["python"], "maxResults": 3},
    "apify_pinterest_media_profile_scraper": {"userUrls": ["https://www.pinterest.com/python"], "maxResults": 3},
    "apify_pinterest_ads_scraper":         {"keywords": ["python"], "maxItems": 3},
    # LinkedIn
    "apify_linkedin_profile_scraper":      {"profileUrls": ["https://www.linkedin.com/in/guido-van-rossum/"]},
    "apify_linkedin_company_scraper":      {"companyUrls": ["https://www.linkedin.com/company/python-software-foundation/"]},
    "apify_linkedin_company_posts_scraper":{"companyUrls": ["https://www.linkedin.com/company/python-software-foundation/"], "maxPosts": 3},
    "apify_linkedin_jobs_scraper":         {"keywords": "Python Developer"},
    "apify_linkedin_company_employees_scraper": {"companyUrls": ["https://www.linkedin.com/company/python-software-foundation/"], "maxItems": 3},
    "apify_linkedin_company_search_scraper": {"keywords": "software company", "maxResults": 3},
    "apify_linkedin_ads_scraper":          {"query": "python", "maxItems": 3},
    # Amazon
    "apify_amazon_product_scraper":        {"asins": ["B09G9FPHY6"]},
    "apify_amazon_review_scraper":         {"asins": ["B09G9FPHY6"], "maxReviews": 5},
    "apify_amazon_reviews_scraper":        {"productUrls": ["https://www.amazon.com/dp/B09G9FPHY6"], "maxReviews": 5},
    # Walmart
    "apify_walmart_product_scraper":       {"startUrls": [{"url": "https://walmart.com/search?q=tshirt"}], "maxProductsPerStartUrl": 3},
    "apify_walmart_reviews_scraper":       {"productIds": ["565742697"], "maxReviews": 5},
    "apify_walmart_scraper":               {"searchQuery": "laptop", "maxItems": 3},
    # eBay
    "apify_ebay_product_scraper":          {"startUrls": [{"url": "https://www.ebay.com/sch/i.html?_nkw=laptop"}], "maxItems": 3},
    "apify_ebay_scraper":                  {"searchQuery": "laptop", "maxItems": 3},
    "apify_ebay_sold_listings_scraper":    {"keywords": ["laptop"], "count": 3},
    # Other E-commerce
    "apify_etsy_scraper":                  {"searchQueries": ["handmade bags"], "maxItems": 3},
    "apify_shopify_scraper":               {"domain": "allbirds.com", "maxItems": 3},
    "apify_aliexpress_products_scraper":   {"searchQuery": "phone case", "maxItems": 3},
    "apify_shein_product_scraper":         {"startUrl": "https://us.shein.com/New-in-Dresses-sc-00020466.html", "results_wanted": 3},
    "apify_temu_products_scraper":         {"searchQueries": ["women dress"], "maxResults": 20},
    "apify_target_products_scraper":       {"searchQueries": ["coffee maker"], "maxProductsPerSearch": 3},
    # Reviews / B2B
    "apify_trustpilot_scraper":            {"companyUrls": ["https://www.trustpilot.com/review/amazon.com"], "maxReviews": 5},
    "apify_trustpilot_reviews_scraper":    {"companyUrls": ["https://www.trustpilot.com/review/amazon.com"], "maxReviews": 5},
    "apify_appstore_scraper":              {"appIds": ["284882215"], "maxItems": 3},
    "apify_appstore_reviews_scraper":      {"appIds": ["284882215"], "maxReviews": 5},
    "apify_google_play_scraper":           {"packageIds": ["com.google.android.apps.maps"], "maxItems": 3},
    "apify_google_play_reviews_scraper":   {"packageIds": ["com.google.android.apps.maps"], "maxReviews": 5},
    "apify_tripadvisor_scraper":           {"startUrls": [{"url": "https://www.tripadvisor.com/Hotel_Review-g60763-d93589-Reviews-The_Plaza-New_York_City_New_York.html"}], "maxItems": 3},
    "apify_tripadvisor_reviews_scraper":   {"startUrls": [{"url": "https://www.tripadvisor.com/Hotel_Review-g60763-d93589-Reviews-The_Plaza-New_York_City_New_York.html"}], "maxItems": 5},
    "apify_yelp_scraper":                  {"location": "New York, NY", "term": "coffee", "maxItems": 3},
    "apify_booking_scraper":               {"search": "Paris", "checkIn": "2025-12-01", "checkOut": "2025-12-03", "maxItems": 3},
    "apify_airbnb_scraper":                {"locationQuery": "New York", "maxListings": 3},
    "apify_glassdoor_scraper":             {"command": "reviews", "startUrls": [{"url": "https://www.glassdoor.fr/Avis/Aza%C3%A9-Avis-E1360610.htm"}], "maxItems": 3},
    "apify_indeed_scraper":                {"position": "Python Developer", "country": "US", "maxItems": 3},
    "apify_indeed_jobs_scraper":           {"keyword": "python", "location": "New York", "maxItems": 3},
    # Google
    "apify_google_search_scraper":         {"queries": ["python programming"], "maxPagesPerQuery": 1, "resultsPerPage": 5},
    "apify_google_maps_scraper":           {"searchStringsArray": ["coffee shops in New York"], "maxCrawledPlaces": 3},
    "apify_google_maps_reviews_scraper":   {"startUrls": [{"url": "https://www.google.com/maps/place/Yellowstone+National+Park/@44.5857951,-110.5140571,9z/data=!3m1!4b1!4m5!3m4!1s0x5351e55555555555:0xaca8f930348fe1bb!8m2!3d44.427963!4d-110.588455?hl=en-GB"}], "maxReviews": 3},
    "apify_google_shopping_scraper":       {"queries": ["laptop"], "maxItems": 3},
    "apify_google_trends_scraper":         {"searchTerms": ["python"], "geo": "US"},
    "apify_google_news_scraper":           {"keywords": ["python programming"], "maxArticles": 5},
    "apify_google_news_media_search":      {"keywords": ["python programming"], "maxArticles": 5},
    "apify_google_ai_overviews_scraper":   {"queries": ["python programming"]},
    "apify_google_ads_scraper":            {"startUrls": [{"url": "https://adstransparency.google.com/advertiser/AR18135649662495883265?region=anywhere"}], "maxItems": 3},
    "apify_google_ads_transparency_scraper": {"advertiserId": "AR01234567890", "maxItems": 3},
    # AI Search
    "apify_chatgpt_scraper":               {"queries": ["what is python"], "maxItems": 3},
    "apify_chatgpt_search_scraper":        {"queries": ["what is python"], "maxItems": 3},
    "apify_perplexity_scraper":            {"queries": ["what is python"], "maxItems": 3},
    "apify_perplexity_search_scraper":     {"queries": ["what is python"], "maxItems": 3},
    "apify_gemini_scraper":                {"queries": ["what is python"], "maxItems": 3},
    "apify_gemini_search_scraper":         {"queries": ["what is python"], "maxItems": 3},
    # Ads
    "apify_meta_ads_library_scraper":      {"query": "python", "country": "US", "maxItems": 3},
    # B2B / Others
    "apify_crunchbase_scraper":            {"startUrls": [{"url": "https://www.crunchbase.com/organization/python-software-foundation"}]},
    "apify_product_hunt_scraper":          {"maxDaysInPast": 1},
    "apify_producthunt_scraper":           {"maxDaysInPast": 1},
    "apify_hacker_news_scraper":           {"maxItems": 5},
    "apify_similarweb_scraper":            {"websites": ["python.org"], "maxItems": 3},
    # Open Web
    "apify_website_content_crawler":       {"startUrls": [{"url": "https://example.com"}], "maxCrawlPages": 2},
    "apify_web_scraper":                   {"startUrls": [{"url": "https://example.com"}], "maxPagesPerCrawl": 2},
    "apify_rag_web_browser":               {"query": "python programming", "maxResults": 1},
    # ── GitHub ─────────────────────────────────────────────────────────────────
    "github_repo":   {"url": "https://github.com/tiangolo/fastapi"},
    "github_topic":  {"topic": "python", "max_results": 5},
    # ── RSS / Web ──────────────────────────────────────────────────────────────
    "public_feed":                {"url": "https://hnrss.org/frontpage"},
    "generic_web":                {"url": "https://example.com"},
    "autoscraper_enhanced_web":   {"url": "https://example.com", "wanted_list": ["Example Domain"]},
    # ── Ecommerce ─────────────────────────────────────────────────────────────
    "ecommerce_product_page":     {"url": "https://www.amazon.com/dp/B09G9FPHY6"},
    "ecommerce_product_discovery": {"url": "https://www.amazon.com/s?k=laptop"},
    # ── Browser ────────────────────────────────────────────────────────────────
    "playwright_browser_text":       {"url": "https://example.com"},
    "playwright_browser_html":       {"url": "https://example.com"},
    "playwright_browser_screenshot": {"url": "https://example.com"},
    # ── AnySearch ─────────────────────────────────────────────────────────────
    "anysearch_brand_media": {"query": "python programming"},
    "anysearch_competitor":  {"query": "python programming"},
    # ── Jina ──────────────────────────────────────────────────────────────────
    "jina_page_content":  {"url": "https://example.com"},
    "jina_dtc_review":    {"url": "https://example.com"},
    "jina_news_article":  {"url": "https://example.com"},
    # ── OSINT ─────────────────────────────────────────────────────────────────
    "sherlock_username":  {"username": "python"},
    "maigret_username":   {"username": "python"},
    "blackbird_email_osint":    {"email": "test@example.com"},
    "blackbird_username_osint": {"username": "python"},
    "spiderfoot_domain_osint":  {"target": "example.com"},
    "spiderfoot_ip_osint":      {"target": "8.8.8.8"},
    "spiderfoot_email_osint":   {"target": "test@example.com"},
    "spiderfoot_subdomain_enum":{"target": "example.com"},
    "spiderfoot_threat_intel":  {"target": "example.com"},
    "spiderfoot_breach_check":  {"target": "test@example.com"},
    # ── twscrape ──────────────────────────────────────────────────────────────
    "twscrape_search":     {"query": "python", "limit": 5},
    "twscrape_user_tweets":{"username": "python", "limit": 5},
    "twscrape_trends":     {},
    # ── Bilibili ──────────────────────────────────────────────────────────────
    "bilibili_video_info":     {"url": "https://www.bilibili.com/video/BV1GJ411x7h7"},
    "bilibili_user_videos":    {"uid": "2267573"},
    "bilibili_video_comments": {"bvid": "BV1GJ411x7h7"},
    # ── Weibo ─────────────────────────────────────────────────────────────────
    "weibo_keyword_search":  {"keyword": "python"},
    "weibo_user_posts":      {"uid": "1669879400"},
    "weibo_trending_topics": {},
    # ── Zhihu ─────────────────────────────────────────────────────────────────
    "zhihu_question_answers": {"question_id": "19550783"},
    "zhihu_keyword_search":   {"keyword": "python"},
    "zhihu_hot_list":         {},
    # ── SERP ──────────────────────────────────────────────────────────────────
    "baidu_search":     {"query": "python"},
    "bing_search":      {"query": "python"},
    "duckduckgo_search":{"query": "python"},
    # ── Kuaishou ──────────────────────────────────────────────────────────────
    "kuaishou_video_search": {"keyword": "python"},
    "kuaishou_user_videos":  {"user_id": "123456"},
    # ── Firecrawl ─────────────────────────────────────────────────────────────
    "firecrawl_crawl":         {"url": "https://example.com", "limit": 1},
    "firecrawl_extract":       {"url": "https://example.com"},
    "firecrawl_batch_scrape":  {"urls": ["https://example.com"]},
    # ── Tech Blog ─────────────────────────────────────────────────────────────
    "devto_articles":   {"tag": "python", "per_page": 5},
    "juejin_articles":  {"category_id": "6809637767543259144"},
    "substack_posts":   {"publication": "pragmaticengineer"},
    # ── Tech Stack ────────────────────────────────────────────────────────────
    "tech_stack_detect": {"url": "https://example.com"},
    # ── BestBlogs ─────────────────────────────────────────────────────────────
    "bestblogs_articles": {"limit": 5},
    # ── Anydoc ────────────────────────────────────────────────────────────────
    "anydoc_file_to_markdown": {"file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"},
}


# ── 后续新增端点的演示参数（单一事实源，勿删） ──────────────────────────────
DEMO_PARAMS.update(
    {
        # TikHub Bilibili
        "tikhub_bilibili_video_search": {"keyword": "python"},
        "tikhub_bilibili_user_videos": {"mid": "2267573"},
        "tikhub_bilibili_comments": {"oid": "1234567890"},
        # AnySearch
        "anysearch_code_doc": {"query": "python requests"},
        "anysearch_tag_search": {"query": "requests", "tag": "code.doc", "params": {"library": "python"}},
        # OSINT
        "sherlock_username_search": {"username": "python"},
        "maigret_username_profile": {"username": "python"},
        # Bilibili
        "bilibili_video_search": {"keyword": "python"},
        # SERP
        "baidu_search_results": {"keyword": "python"},
        "bing_search_results": {"keyword": "python"},
        "duckduckgo_search_results": {"keyword": "python"},
        # Tech blog
        "devto_articles_search": {},
        "juejin_articles_search": {"keyword": "python"},
        # SpiderFoot 扩展
        "spiderfoot_cert_transparency": {"target": "example.com"},
        "spiderfoot_dark_web": {"target": "example.com"},
        "spiderfoot_attack_surface": {"target": "example.com"},
        # Aliens Eye
        "aliens_eye_basic": {"username": "python"},
        "aliens_eye_advanced": {"username": "python"},
        "aliens_eye_correlate": {"username": "python"},
        "aliens_eye_recurse": {"username": "python"},
        "aliens_eye_domain": {"username": "python"},
        "aliens_eye_batch": {"usernames": ["python"]},
        "aliens_eye_selfcheck": {},
        # Robin (Tor)
        "robin_darkweb_search": {"keyword": "python"},
        "robin_darkweb_username": {"username": "python"},
        "robin_darkweb_email": {"email": "test@example.com"},
        # browser-use
        "browser_use_task": {"task": "Open https://example.com and return the page title"},
        # Hacker News
        "hackernews_front_page": {},
        "hackernews_search": {"query": "python"},
        "hackernews_user": {"username": "pg"},
        # 包注册表
        "npm_package": {"package": "express"},
        "npm_search": {"query": "http"},
        "pypi_package": {"package": "requests"},
        "crates_package": {"package": "serde"},
        "crates_search": {"query": "http"},
        "rubygems_package": {"package": "rails"},
        "rubygems_search": {"query": "http"},
        "go_package": {"package": "github.com/gin-gonic/gin"},
        "go_search": {"query": "http"},
        "packagist_package": {"package": "laravel/framework"},
        "packagist_search": {"query": "http"},
        "nuget_package": {"package": "Newtonsoft.Json"},
        "nuget_search": {"query": "json"},
        "pubdev_package": {"package": "http"},
        "pubdev_search": {"query": "http"},
        # Exa
        "exa_search_auto": {"query": "python programming"},
        "exa_search_news": {"query": "python programming"},
        "exa_company_search": {"query": "Anthropic"},
        "exa_find_similar": {"url": "https://example.com"},
        "exa_contents": {"urls": ["https://example.com"]},
        "exa_research_paper": {"query": "retrieval augmented generation"},
        "exa_people_search": {"query": "Guido van Rossum"},
        "exa_financial_report": {"query": "Nvidia annual report"},
        "exa_deep_research": {
            "query": "What is Python?",
            "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
        },
        "exa_deep_reasoning": {"query": "What is Python?"},
        "exa_answer": {"query": "What is Python?"},
        "exa_search_instant": {"query": "python programming"},
        "exa_search_fast": {"query": "python programming"},
        "exa_personal_site": {"query": "python programming"},
        "exa_domain_search": {"query": "python", "include_domains": ["example.com"]},
        "exa_deep_lite": {"query": "What is Python?"},
        # Apify 跨境电商（新增）
        "apify_1688_product_search": {"keyword": "phone case"},
        "apify_1688_product_detail": {"mode": "detail", "inputs": ["https://detail.1688.com/offer/642952568827.html"]},
        "apify_1688_advanced": {"mode": "search", "inputs": ["phone case"]},
        "apify_alibaba_product_search": {"startUrls": [{"url": "https://www.alibaba.com/trade/search?SearchText=phone+case"}]},
        "apify_alibaba_product_detail": {"productUrls": ["https://www.alibaba.com/product-detail/WATA-In-Ear-Waterproof-Sport-Earbud_1601685362945.html"]},
        "apify_amazon_bestsellers": {"categoryUrls": ["https://www.amazon.com/Best-Sellers/zgbs"], "maxItemsPerStartUrl": 5},
        "apify_amazon_competitor_research": {"asins": ["B09G9FPHY6"]},
        "apify_amazon_bsr_tracker": {"asins": ["B09G9FPHY6"], "marketplaces": ["US"]},
        "apify_amazon_price_tracker": {"products": ["B09G9FPHY6"]},
        "apify_aliexpress_product_search_v2": {"queries": ["phone case"]},
        "apify_shopify_products_monitor": {"domains": ["allbirds.com"], "maxProducts": 5},
        "apify_shopify_full_catalog": {"startUrls": [{"url": "https://allbirds.com"}]},
    }
)
