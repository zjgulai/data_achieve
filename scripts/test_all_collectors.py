"""批量测试所有采集 API 端点。

每个 endpoint 发起一次 quick_collect（label=[test] <endpoint_type>），
结果写入 task_runs，/api/collector-docs 会从中读取最新测试结果。

用法：
    python test_all_collectors.py --base-url http://192.168.204.230 --project-id <uuid>
    python test_all_collectors.py --base-url http://127.0.0.1:8080 --project-id <uuid> --dry-run
    python test_all_collectors.py --group tikhub  # 只测某组

默认测试参数（每个 provider 用最简单的无敏感数据参数）：
- TikHub / Apify：触发并记录 key 是否配置（key 未配置会 fail，但说明配置状态）
- GitHub / RSS / Web：真实调用，期望成功
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from typing import Any


DEMO_PARAMS: dict[str, dict[str, Any]] = {
    # ── TikHub ────────────────────────────────────────────────────────────────
    "tikhub_tiktok_video_search":          {"keyword": "python"},
    "tikhub_tiktok_user_posts":            {"unique_id": "tiktok"},
    "tikhub_tiktok_hashtag_posts":         {"ch_id": "7654567"},
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
    "tikhub_threads_user_posts":           {"username": "zuck"},
    "tikhub_threads_post_comments":        {"post_id": "test_post_id"},
    "tikhub_linkedin_user_posts":          {"username": "williamhgates"},
    "tikhub_linkedin_company_profile":     {"company_username": "microsoft"},
    "tikhub_linkedin_company_posts":       {"company_username": "microsoft"},
    "tikhub_linkedin_search_jobs":         {"keyword": "data engineer"},
    "tikhub_linkedin_job_detail":          {"job_id": "3768164426"},
    "tikhub_linkedin_post_comments":       {"post_urn": "7234567890123456"},
    "tikhub_lemon8_search":               {"keyword": "python"},
    "tikhub_lemon8_user_posts":           {"user_id": "12345"},
    "tikhub_lemon8_trending":             {},
    "tikhub_tiktok_ads_search":           {"keyword": "python"},
    "tikhub_tiktok_top_ads":             {},
    "tikhub_tiktok_shop_products":        {"keyword": "phone case"},
    "tikhub_tiktok_creator_info":         {"unique_id": "tiktok"},
    "tikhub_instagram_post_comments":     {"shortcode": "B1234567890"},
    "tikhub_youtube_video_comments":      {"video_id": "dQw4w9WgXcQ"},
    "tikhub_reddit_post_comments":        {"post_id": "t3_123456"},
    "tikhub_tiktok_live_search":          {"keyword": "music"},
    "tikhub_tiktok_live_room_detail":     {"room_id": "123456"},
    "tikhub_tiktok_live_user":            {"unique_id": "tiktok"},
    "tikhub_youtube_trending":            {},
    "tikhub_reddit_trending":             {},
    "tikhub_x_trending":                  {},
    "tikhub_tiktok_user_followers":       {"unique_id": "tiktok"},
    "tikhub_instagram_user_followers":    {"user_id": "25025320"},
    "tikhub_x_user_followers":            {"username": "python"},
    "tikhub_tiktok_creator_insights":     {"unique_id": "tiktok"},
    "tikhub_tiktok_creator_insights_trend": {"unique_id": "tiktok"},
    "tikhub_tiktok_creator_account_health": {"unique_id": "tiktok"},
    "tikhub_tiktok_ads_detail":           {"ad_id": "123456"},
    "tikhub_tiktok_ads_keyword_suggest":  {"keyword": "python"},
    "tikhub_douyin_video_search":         {"keyword": "python"},
    "tikhub_douyin_user_posts":           {"sec_user_id": "MS4wLjABAAAA"},
    "tikhub_douyin_hot_search":           {},
    "tikhub_douyin_comments":             {"aweme_id": "123456"},
    "tikhub_douyin_brand_hot_search":     {},
    "tikhub_wechat_search":               {"keyword": "python"},
    "tikhub_wechat_channels_video":       {"video_id": "123456"},
    "tikhub_weibo_search":                {"keyword": "python"},
    "tikhub_weibo_user_posts":            {"uid": "1669879400"},
    "tikhub_zhihu_search":                {"keyword": "python"},
    "tikhub_zhihu_question_answers":      {"question_id": "19550783"},
    "tikhub_kuaishou_search":             {"keyword": "python"},
    "tikhub_kuaishou_user_posts":         {"user_id": "123456"},
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
    "apify_reddit_scraper":                {"searches": [{"keyword": "python"}], "maxItems": 3},
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
    "apify_linkedin_jobs_scraper":         {"title": "Python Developer", "location": "United States", "maxJobs": 3},
    "apify_linkedin_company_employees_scraper": {"companyUrls": ["https://www.linkedin.com/company/python-software-foundation/"], "maxItems": 3},
    "apify_linkedin_company_search_scraper": {"searchQuery": "software company", "maxItems": 3},
    "apify_linkedin_ads_scraper":          {"query": "python", "maxItems": 3},
    # Amazon
    "apify_amazon_product_scraper":        {"asins": ["B09G9FPHY6"]},
    "apify_amazon_review_scraper":         {"asins": ["B09G9FPHY6"], "maxReviews": 5},
    "apify_amazon_reviews_scraper":        {"productUrls": ["https://www.amazon.com/dp/B09G9FPHY6"], "maxReviews": 5},
    # Walmart
    "apify_walmart_product_scraper":       {"productIds": ["565742697"]},
    "apify_walmart_reviews_scraper":       {"productIds": ["565742697"], "maxReviews": 5},
    "apify_walmart_scraper":               {"searchQuery": "laptop", "maxItems": 3},
    # eBay
    "apify_ebay_product_scraper":          {"listingUrls": ["https://www.ebay.com/itm/284574059539"], "maxItems": 3},
    "apify_ebay_scraper":                  {"searchQuery": "laptop", "maxItems": 3},
    "apify_ebay_sold_listings_scraper":    {"searchQuery": "laptop", "maxItems": 3},
    # Other E-commerce
    "apify_etsy_scraper":                  {"searchQueries": ["handmade bags"], "maxItems": 3},
    "apify_shopify_scraper":               {"domain": "allbirds.com", "maxItems": 3},
    "apify_aliexpress_products_scraper":   {"searchQuery": "phone case", "maxItems": 3},
    "apify_shein_product_scraper":         {"searchQuery": "dress", "maxItems": 3},
    "apify_temu_products_scraper":         {"keywords": ["phone case"], "maxItems": 3},
    "apify_target_products_scraper":       {"keywords": ["laptop"], "maxItems": 3},
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
    "apify_glassdoor_scraper":             {"keyword": "python developer", "maxItems": 3},
    "apify_indeed_scraper":                {"position": "Python Developer", "country": "US", "maxItems": 3},
    "apify_indeed_jobs_scraper":           {"keyword": "python", "location": "New York", "maxItems": 3},
    # Google
    "apify_google_search_scraper":         {"queries": ["python programming"], "maxPagesPerQuery": 1, "resultsPerPage": 5},
    "apify_google_maps_scraper":           {"searchStringsArray": ["coffee shops in New York"], "maxCrawledPlaces": 3},
    "apify_google_maps_reviews_scraper":   {"startUrls": [{"url": "https://maps.google.com/maps?cid=3048762&hl=en"}], "maxReviews": 5},
    "apify_google_shopping_scraper":       {"queries": ["laptop"], "maxItems": 3},
    "apify_google_trends_scraper":         {"searchTerms": ["python"], "geo": "US"},
    "apify_google_news_scraper":           {"keywords": ["python programming"], "maxArticles": 5},
    "apify_google_news_media_search":      {"keywords": ["python programming"], "maxArticles": 5},
    "apify_google_ai_overviews_scraper":   {"queries": ["python programming"]},
    "apify_google_ads_scraper":            {"keywords": ["python"], "maxItems": 3},
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
    "apify_rag_web_browser":               {"query": "python programming"},
    # ── GitHub ─────────────────────────────────────────────────────────────────
    "github_repo":   {"url": "https://github.com/tiangolo/fastapi"},
    "github_topic":  {"topic": "python", "max_results": 5},
    # ── RSS / Web ──────────────────────────────────────────────────────────────
    "public_feed":                {"url": "https://hnrss.org/frontpage"},
    "generic_web":                {"url": "https://example.com"},
    "autoscraper_enhanced_web":   {"url": "https://news.ycombinator.com", "examples": ["Ask HN", "Show HN"]},
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
    "substack_posts":   {"publication_url": "https://newsletter.pragmaticengineer.com"},
    # ── Tech Stack ────────────────────────────────────────────────────────────
    "tech_stack_detect": {"url": "https://example.com"},
    # ── BestBlogs ─────────────────────────────────────────────────────────────
    "bestblogs_articles": {"limit": 5},
    # ── Anydoc ────────────────────────────────────────────────────────────────
    "anydoc_file_to_markdown": {"url": "https://example.com/doc.pdf"},
}


def post_json(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)}


def get_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test all collector endpoints via quick_collect")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--group", default="", help="Only test endpoints in this group")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    args = parser.parse_args()

    catalog = get_json(f"{args.base_url}/api/collectors/catalog")
    if "error" in catalog:
        print(f"ERROR: Cannot fetch catalog: {catalog}", file=sys.stderr)
        sys.exit(1)

    endpoints = []
    for group in catalog.get("collectors", []):
        if args.group and group["collector_type"] != args.group:
            continue
        for ep in group["endpoints"]:
            if ep.get("status") == "disabled":
                continue
            endpoints.append(ep)

    print(f"Testing {len(endpoints)} endpoints (dry_run={args.dry_run})")
    print()

    results = []
    for i, ep in enumerate(endpoints, 1):
        ep_type = ep["endpoint_type"]
        params = DEMO_PARAMS.get(ep_type, {})
        label = f"[test] {ep_type}"

        print(f"[{i:3d}/{len(endpoints)}] {ep_type} ...", end=" ", flush=True)

        if args.dry_run:
            print("SKIP (dry-run)")
            continue

        payload = {
            "project_id": args.project_id,
            "endpoint_type": ep_type,
            "params": params,
            "label": label,
            "save_records": False,
        }

        resp = post_json(f"{args.base_url}/api/quick-collect", payload)

        if "error" in resp:
            print(f"ERROR {resp.get('error')} {resp.get('detail','')[:80]}")
            results.append({"endpoint_type": ep_type, "outcome": "request_error", "detail": str(resp)})
        else:
            run_status = resp.get("status", "?")
            records = resp.get("records_count", 0)
            err = (resp.get("error_message") or "")[:80]
            flag = "✓" if run_status == "success" else "✗"
            print(f"{flag} {run_status} records={records} {err}")
            results.append({
                "endpoint_type": ep_type,
                "outcome": run_status,
                "run_id": str(resp.get("task_run_id", "")),
                "records_count": records,
                "error": err,
            })

        if args.delay:
            time.sleep(args.delay)

    print()
    if results:
        ok = sum(1 for r in results if r.get("outcome") == "success")
        print(f"Done: {ok}/{len(results)} success")


if __name__ == "__main__":
    main()
