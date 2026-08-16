#!/usr/bin/env python3
"""
Batch annotate all 102 endpoints in collectors.py with content_type + method.
"""
import re

ENDPOINT_MAPPINGS = {
    # TikHub - video/post search & scraping
    "tikhub_tiktok_video_search": ("post", "tikhub"),
    "tikhub_tiktok_user_posts": ("post", "tikhub"),
    "tikhub_tiktok_hashtag_posts": ("post", "tikhub"),
    "tikhub_instagram_search": ("post", "tikhub"),
    "tikhub_instagram_user_posts": ("post", "tikhub"),
    "tikhub_xiaohongshu_search": ("post", "tikhub"),
    "tikhub_youtube_search": ("post", "tikhub"),
    "tikhub_youtube_channel_videos": ("post", "tikhub"),
    "tikhub_reddit_search": ("post", "tikhub"),
    "tikhub_reddit_subreddit_posts": ("post", "tikhub"),
    "tikhub_x_search": ("post", "tikhub"),
    "tikhub_x_user_tweets": ("post", "tikhub"),
    
    # Apify - social posts
    "apify_instagram_scraper": ("post", "apify"),
    "apify_instagram_profile_scraper": ("account", "apify"),
    "apify_facebook_posts_scraper": ("post", "apify"),
    "apify_facebook_comments_scraper": ("comment", "apify"),
    "apify_tiktok_scraper": ("post", "apify"),
    "apify_tiktok_comments_scraper": ("comment", "apify"),
    "apify_youtube_scraper": ("post", "apify"),
    "apify_youtube_comments_scraper": ("comment", "apify"),
    "apify_x_tweet_scraper": ("post", "apify"),
    "apify_reddit_scraper": ("post", "apify"),
    
    # Apify - ecommerce products
    "apify_amazon_product_scraper": ("product", "apify"),
    "apify_amazon_reviews_scraper": ("review", "apify"),
    "apify_walmart_product_scraper": ("product", "apify"),
    "apify_walmart_reviews_scraper": ("review", "apify"),
    "apify_temu_products_scraper": ("product", "apify"),
    "apify_shein_product_scraper": ("product", "apify"),
    "apify_aliexpress_products_scraper": ("product", "apify"),
    "apify_tiktok_shop_scraper": ("product", "apify"),
    "apify_trustpilot_reviews_scraper": ("review", "apify"),
    "apify_appstore_reviews_scraper": ("review", "apify"),
    "apify_ebay_product_scraper": ("product", "apify"),
    "apify_etsy_scraper": ("product", "apify"),
    "apify_tripadvisor_reviews_scraper": ("review", "apify"),
    "apify_yelp_scraper": ("review", "apify"),
    "apify_booking_scraper": ("product", "apify"),
    "apify_airbnb_scraper": ("product", "apify"),
    "apify_shopify_scraper": ("product", "apify"),
    
    # Apify - search & trends
    "apify_google_search_scraper": ("search", "apify"),
    "apify_google_maps_scraper": ("product", "apify"),
    "apify_google_maps_reviews_scraper": ("review", "apify"),
    "apify_google_trends_scraper": ("trend", "apify"),
    "apify_google_news_scraper": ("news", "apify"),
    "apify_google_ai_overviews_scraper": ("ai_answer", "apify"),
    "apify_chatgpt_search_scraper": ("ai_answer", "apify"),
    "apify_perplexity_search_scraper": ("ai_answer", "apify"),
    "apify_gemini_search_scraper": ("ai_answer", "apify"),
    
    # Apify - ads
    "apify_facebook_ads_scraper": ("ad", "apify"),
    "apify_google_ads_scraper": ("ad", "apify"),
    "apify_tiktok_ads_scraper": ("ad", "apify"),
    "apify_snapchat_ads_scraper": ("ad", "apify"),
    "apify_pinterest_ads_scraper": ("ad", "apify"),
    
    # Apify - B2B / social accounts
    "apify_linkedin_company_posts_scraper": ("post", "apify"),
    "apify_threads_profile_scraper": ("account", "apify"),
    "apify_threads_posts_scraper": ("post", "apify"),
    "apify_pinterest_scraper": ("post", "apify"),
    "apify_glassdoor_scraper": ("review", "apify"),
    "apify_product_hunt_scraper": ("product", "apify"),
    "apify_crunchbase_scraper": ("account", "apify"),
    "apify_hacker_news_scraper": ("post", "apify"),
    "apify_bluesky_scraper": ("post", "apify"),
    "apify_telegram_scraper": ("post", "apify"),
    "apify_indeed_jobs_scraper": ("job", "apify"),
    
    # Apify - media monitoring
    "apify_google_news_media_search": ("news", "apify"),
    "apify_instagram_media_profile_scraper": ("account", "apify"),
    "apify_tiktok_media_profile_scraper": ("account", "apify"),
    "apify_youtube_media_channel_scraper": ("account", "apify"),
    "apify_facebook_media_page_scraper": ("account", "apify"),
    "apify_x_media_account_scraper": ("account", "apify"),
    "apify_pinterest_media_profile_scraper": ("account", "apify"),
    
    # Apify - web crawling
    "apify_website_content_crawler": ("web_page", "apify"),
    "apify_web_scraper": ("web_page", "apify"),
    "apify_rag_web_browser": ("web_page", "apify"),
    
    # GitHub
    "github_repo": ("repo", "github_api"),
    "github_topic": ("repo", "github_api"),
    
    # RSS (19 feeds) + generic web (6)
    "public_feed": ("feed", "rss"),
    "generic_web": ("web_page", "web_crawl"),
}

def annotate_file():
    collectors_path = "apps/api/src/data_intelligence_hub/api/routes/collectors.py"
    
    with open(collectors_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find all CollectorEndpointMetadata( blocks
    pattern = r'(CollectorEndpointMetadata\(\s+endpoint_type="([^"]+)"[^)]+provider="([^"]+)")'
    
    def replacer(match):
        full_block = match.group(1)
        endpoint_type = match.group(2)
        provider = match.group(3)
        
        # Get classification
        content_type, method = ENDPOINT_MAPPINGS.get(endpoint_type, ("post", "tikhub"))
        
        # Insert before closing paren
        return f'{full_block},\n            content_type="{content_type}",\n            method="{method}"'
    
    # Apply replacements
    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    # Write back
    with open(collectors_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"✓ Annotated all endpoints in {collectors_path}")
    print(f"  Added content_type + method to {len(ENDPOINT_MAPPINGS)} endpoint types")

if __name__ == "__main__":
    annotate_file()
