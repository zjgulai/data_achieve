"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, CheckCircle, AlertCircle, Loader2, ArrowRight } from "lucide-react";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { postQuickCollect, type QuickCollectResponse } from "@/lib/api/quick-collect";
import { fetchProjects } from "@/lib/api/projects";
import { ApiError } from "@/lib/api/client";

/* ── Param field definitions per endpoint_type ── */
type FieldDef = {
  key: string;
  label: string;
  type: "text" | "number";
  required: boolean;
  placeholder: string;
  defaultValue?: string | number;
};

const PARAM_FIELDS: Record<string, FieldDef[]> = {
  tikhub_tiktok_video_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_user_posts: [
    { key: "unique_id", label: "账号名 (unique_id)", type: "text", required: true, placeholder: "charlidamelio" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_hashtag_posts: [
    { key: "ch_id", label: "话题 ID (ch_id)", type: "text", required: true, placeholder: "7273" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_instagram_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_instagram_user_posts: [
    { key: "user_id", label: "账号 user_id", type: "text", required: true, placeholder: "12345678" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "12", defaultValue: 12 },
  ],
  tikhub_xiaohongshu_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "吸奶器" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_youtube_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "breast pump review" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_youtube_channel_videos: [
    { key: "channel_id", label: "频道 ID", type: "text", required: true, placeholder: "UCxxxxxx" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_reddit_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_reddit_subreddit_posts: [
    { key: "subreddit", label: "Subreddit 名称", type: "text", required: true, placeholder: "breastfeeding" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_x_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "momcozy" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_x_user_tweets: [
    { key: "username", label: "X 账号名", type: "text", required: true, placeholder: "ForbesVetted" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok: [
    { key: "actor_id", label: "Actor ID", type: "text", required: true, placeholder: "clockworks/tiktok-scraper", defaultValue: "clockworks/tiktok-scraper" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
    { key: "max_total_charge_usd", label: "费用上限 (USD)", type: "number", required: false, placeholder: "0.5", defaultValue: 0.5 },
  ],
  apify_instagram: [
    { key: "actor_id", label: "Actor ID", type: "text", required: true, placeholder: "apify/instagram-scraper", defaultValue: "apify/instagram-scraper" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
    { key: "max_total_charge_usd", label: "费用上限 (USD)", type: "number", required: false, placeholder: "0.5", defaultValue: 0.5 },
  ],
  apify_instagram_scraper: [
    { key: "search", label: "搜索词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "resultsLimit", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_instagram_profile_scraper: [
    { key: "usernames", label: "账号名 (逗号分隔)", type: "text", required: true, placeholder: "forbesvetted,babylist" },
    { key: "resultsLimit", label: "最大条数", type: "number", required: false, placeholder: "12", defaultValue: 12 },
  ],
  apify_instagram_media_profile_scraper: [
    { key: "usernames", label: "媒体账号名 (逗号分隔)", type: "text", required: true, placeholder: "forbesvetted,consumerreports,parents" },
    { key: "resultsLimit", label: "最大条数", type: "number", required: false, placeholder: "12", defaultValue: 12 },
  ],
  apify_facebook_posts_scraper: [
    { key: "startUrls", label: "Facebook 页面 URL", type: "text", required: true, placeholder: "https://www.facebook.com/forbesvetted/" },
    { key: "maxPosts", label: "最大帖子数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_facebook_comments_scraper: [
    { key: "startUrls", label: "Facebook 帖子 URL", type: "text", required: true, placeholder: "https://www.facebook.com/..." },
    { key: "resultsLimit", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_facebook_media_page_scraper: [
    { key: "startUrls", label: "媒体 Facebook 页面 URL", type: "text", required: true, placeholder: "https://www.facebook.com/ConsumerReports/" },
    { key: "maxPosts", label: "最大帖子数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok_scraper: [
    { key: "searchQueries", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "resultsPerPage", label: "每页数量", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok_comments_scraper: [
    { key: "postURLs", label: "视频 URL", type: "text", required: true, placeholder: "https://www.tiktok.com/@user/video/..." },
    { key: "commentsPerPost", label: "每视频评论数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_tiktok_media_profile_scraper: [
    { key: "profiles", label: "媒体 TikTok 账号 (逗号分隔)", type: "text", required: true, placeholder: "forbesvetted,consumerreports,parents" },
    { key: "resultsPerPage", label: "每页数量", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_youtube_scraper: [
    { key: "searchQueries", label: "搜索词", type: "text", required: true, placeholder: "breast pump review 2026" },
    { key: "maxResults", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_youtube_comments_scraper: [
    { key: "startUrls", label: "视频 URL", type: "text", required: true, placeholder: "https://www.youtube.com/watch?v=..." },
    { key: "maxComments", label: "最大评论数", type: "number", required: false, placeholder: "100", defaultValue: 100 },
  ],
  apify_youtube_media_channel_scraper: [
    { key: "startUrls", label: "媒体 YouTube 频道 URL", type: "text", required: true, placeholder: "https://www.youtube.com/@consumerreports" },
    { key: "maxResults", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_x_tweet_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_x_media_account_scraper: [
    { key: "twitterHandles", label: "媒体 X 账号 (逗号分隔)", type: "text", required: true, placeholder: "ForbesVetted,ConsumerReports,parentsmagazine" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_reddit_scraper: [
    { key: "startUrls", label: "Reddit 起始 URL", type: "text", required: true, placeholder: "https://www.reddit.com/r/breastfeeding/" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_amazon_product_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.amazon.com/dp/B09..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_amazon_reviews_scraper: [
    { key: "asin", label: "ASIN", type: "text", required: true, placeholder: "B09XXXXXX" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_walmart_product_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.walmart.com/ip/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_walmart_reviews_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.walmart.com/ip/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_temu_products_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.temu.com/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_shein_product_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.shein.com/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_aliexpress_products_scraper: [
    { key: "startUrls", label: "商品页 URL", type: "text", required: true, placeholder: "https://www.aliexpress.com/item/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_tiktok_shop_scraper: [
    { key: "startUrls", label: "TikTok Shop URL", type: "text", required: true, placeholder: "https://www.tiktok.com/shop/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_trustpilot_reviews_scraper: [
    { key: "startUrls", label: "Trustpilot 商家页 URL", type: "text", required: true, placeholder: "https://www.trustpilot.com/review/momcozy.com" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_appstore_reviews_scraper: [
    { key: "appId", label: "App Store App ID", type: "text", required: true, placeholder: "1234567890" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_ebay_product_scraper: [
    { key: "startUrls", label: "eBay 商品 URL", type: "text", required: true, placeholder: "https://www.ebay.com/sch/i.html?_nkw=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_etsy_scraper: [
    { key: "startUrls", label: "Etsy URL", type: "text", required: true, placeholder: "https://www.etsy.com/search?q=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tripadvisor_reviews_scraper: [
    { key: "startUrls", label: "Tripadvisor URL", type: "text", required: true, placeholder: "https://www.tripadvisor.com/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_yelp_scraper: [
    { key: "startUrls", label: "Yelp 商家 URL", type: "text", required: true, placeholder: "https://www.yelp.com/biz/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_booking_scraper: [
    { key: "startUrls", label: "Booking.com URL", type: "text", required: true, placeholder: "https://www.booking.com/hotel/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_airbnb_scraper: [
    { key: "startUrls", label: "Airbnb URL", type: "text", required: true, placeholder: "https://www.airbnb.com/rooms/..." },
    { key: "maxListings", label: "最大房源数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_shopify_scraper: [
    { key: "startUrls", label: "Shopify 店铺 URL", type: "text", required: true, placeholder: "https://store.example.com/collections/all" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_google_search_scraper: [
    { key: "queries", label: "搜索词", type: "text", required: true, placeholder: "best wearable breast pump 2026" },
    { key: "maxPagesPerQuery", label: "每词最大页数", type: "number", required: false, placeholder: "3", defaultValue: 3 },
  ],
  apify_google_maps_scraper: [
    { key: "searchStringsArray", label: "搜索词", type: "text", required: true, placeholder: "breast pump store New York" },
    { key: "maxCrawledPlacesPerSearch", label: "最大地点数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_google_maps_reviews_scraper: [
    { key: "startUrls", label: "Google Maps 地点 URL", type: "text", required: true, placeholder: "https://www.google.com/maps/place/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_google_trends_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "timeRange", label: "时间范围", type: "text", required: false, placeholder: "today 12-m" },
  ],
  apify_google_news_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_google_news_media_search: [
    { key: "searchTerms", label: "搜索词 (品牌+媒体名)", type: "text", required: true, placeholder: "momcozy site:forbes.com OR site:babycenter.com" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
    { key: "includedDomains", label: "限定域名 (逗号分隔)", type: "text", required: false, placeholder: "forbes.com,babycenter.com,wirecutter.com" },
  ],
  apify_google_ai_overviews_scraper: [
    { key: "queries", label: "搜索词", type: "text", required: true, placeholder: "best wearable breast pump" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_chatgpt_search_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "recommend a breast pump for new moms" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_perplexity_search_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "best wearable breast pump brand" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_gemini_search_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "best breast pump 2026" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_facebook_ads_scraper: [
    { key: "searchTerms", label: "品牌/关键词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_google_ads_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok_ads_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_snapchat_ads_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_pinterest_ads_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_linkedin_company_posts_scraper: [
    { key: "companyUrls", label: "公司 LinkedIn URL", type: "text", required: true, placeholder: "https://www.linkedin.com/company/momcozy/" },
    { key: "maxPosts", label: "最大帖子数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_threads_profile_scraper: [
    { key: "usernames", label: "账号名 (逗号分隔)", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxPosts", label: "最大帖子数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_threads_posts_scraper: [
    { key: "mode", label: "搜索模式", type: "text", required: true, placeholder: "SEARCH" },
    { key: "keywords", label: "关键词", type: "text", required: false, placeholder: "breast pump" },
  ],
  apify_pinterest_scraper: [
    { key: "startUrls", label: "Pinterest URL", type: "text", required: true, placeholder: "https://www.pinterest.com/babylist/" },
    { key: "maxPinsCnt", label: "最大 Pin 数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_pinterest_media_profile_scraper: [
    { key: "startUrls", label: "媒体 Pinterest 账号 URL", type: "text", required: true, placeholder: "https://www.pinterest.com/parents/" },
    { key: "maxPinsCnt", label: "最大 Pin 数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_glassdoor_scraper: [
    { key: "startUrls", label: "Glassdoor 公司页 URL", type: "text", required: true, placeholder: "https://www.glassdoor.com/Overview/..." },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_product_hunt_scraper: [
    { key: "maxDays", label: "抓取天数", type: "number", required: false, placeholder: "7", defaultValue: 7 },
  ],
  apify_crunchbase_scraper: [
    { key: "companyUrls", label: "公司 Crunchbase URL", type: "text", required: true, placeholder: "https://www.crunchbase.com/organization/momcozy" },
    { key: "maxCompanies", label: "最大公司数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_hacker_news_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "wearable pump startup" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_bluesky_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_telegram_scraper: [
    { key: "channelUrls", label: "Telegram 频道 URL", type: "text", required: true, placeholder: "https://t.me/channel_name" },
    { key: "maxMessages", label: "最大消息数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_indeed_jobs_scraper: [
    { key: "queries", label: "职位搜索词", type: "text", required: true, placeholder: "breast pump product manager" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_website_content_crawler: [
    { key: "startUrls", label: "起始 URL", type: "text", required: true, placeholder: "https://www.forbes.com/sites/forbesvetted/" },
    { key: "maxCrawlPages", label: "最大页面数", type: "number", required: false, placeholder: "10", defaultValue: 10 },
  ],
  apify_web_scraper: [
    { key: "startUrls", label: "起始 URL", type: "text", required: true, placeholder: "https://example.com" },
    { key: "maxCrawlDepth", label: "最大抓取深度", type: "number", required: false, placeholder: "2", defaultValue: 2 },
  ],
  apify_rag_web_browser: [
    { key: "startUrls", label: "起始 URL", type: "text", required: true, placeholder: "https://example.com/article" },
    { key: "maxCrawlDepth", label: "最大抓取深度", type: "number", required: false, placeholder: "1", defaultValue: 1 },
  ],
  github_repo: [
    { key: "owner", label: "仓库所有者", type: "text", required: true, placeholder: "facebook" },
    { key: "repo", label: "仓库名称", type: "text", required: true, placeholder: "react" },
  ],
  github_topic: [
    { key: "topic", label: "GitHub 话题", type: "text", required: true, placeholder: "machine-learning" },
    { key: "max_results", label: "最大结果数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  public_feed: [
    { key: "url", label: "RSS/Atom URL", type: "text", required: true, placeholder: "https://example.com/feed.xml" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  generic_web: [
    { key: "url", label: "网页 URL", type: "text", required: true, placeholder: "https://example.com/page" },
  ],
  tikhub_threads_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "momcozy" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_threads_user_posts: [
    { key: "username", label: "Threads 账号名", type: "text", required: true, placeholder: "momcozy.official" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_threads_post_comments: [
    { key: "post_id", label: "帖子 ID", type: "text", required: true, placeholder: "1234567890" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  tikhub_linkedin_user_posts: [
    { key: "username", label: "LinkedIn 用户名", type: "text", required: true, placeholder: "johndoe" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_linkedin_company_profile: [
    { key: "company_username", label: "企业 LinkedIn 标识", type: "text", required: true, placeholder: "momcozy" },
  ],
  tikhub_linkedin_company_posts: [
    { key: "company_username", label: "企业 LinkedIn 标识", type: "text", required: true, placeholder: "momcozy" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_linkedin_search_jobs: [
    { key: "keyword", label: "职位关键词", type: "text", required: true, placeholder: "product manager" },
    { key: "location", label: "地区 (可选)", type: "text", required: false, placeholder: "United States" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_linkedin_job_detail: [
    { key: "job_id", label: "职位 ID", type: "text", required: true, placeholder: "3890123456" },
  ],
  tikhub_linkedin_post_comments: [
    { key: "post_urn", label: "帖子 URN", type: "text", required: true, placeholder: "urn:li:activity:7234567890" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  tikhub_lemon8_search: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_lemon8_user_posts: [
    { key: "user_id", label: "用户 ID", type: "text", required: true, placeholder: "12345678" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_lemon8_trending: [
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_ads_search: [
    { key: "keyword", label: "广告关键词", type: "text", required: true, placeholder: "breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
  ],
  tikhub_tiktok_top_ads: [
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
  ],
  tikhub_tiktok_shop_products: [
    { key: "keyword", label: "商品关键词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_creator_info: [
    { key: "unique_id", label: "TikTok 账号名", type: "text", required: true, placeholder: "momcozy_official" },
  ],
  tikhub_instagram_post_comments: [
    { key: "shortcode", label: "帖子 shortcode", type: "text", required: true, placeholder: "CxYzABCDEFG" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  tikhub_youtube_video_comments: [
    { key: "video_id", label: "YouTube 视频 ID", type: "text", required: true, placeholder: "dQw4w9WgXcQ" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  tikhub_reddit_post_comments: [
    { key: "post_id", label: "Reddit 帖子 ID", type: "text", required: true, placeholder: "t3_abc123" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  tikhub_tiktok_live_search: [
    { key: "keyword", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_tiktok_live_room_detail: [
    { key: "room_id", label: "直播间 ID", type: "text", required: true, placeholder: "7234567890" },
  ],
  tikhub_tiktok_live_user: [
    { key: "unique_id", label: "主播账号名", type: "text", required: true, placeholder: "momcozy_live" },
  ],
  tikhub_youtube_trending: [
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
    { key: "category_id", label: "分类 ID (可选)", type: "text", required: false, placeholder: "26" },
  ],
  tikhub_reddit_trending: [
    { key: "subreddit", label: "Subreddit (留空为全站)", type: "text", required: false, placeholder: "parenting" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  tikhub_x_trending: [
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
  ],
  tikhub_tiktok_user_followers: [
    { key: "unique_id", label: "TikTok 账号名", type: "text", required: true, placeholder: "momcozy_official" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "100", defaultValue: 100 },
  ],
  tikhub_instagram_user_followers: [
    { key: "user_id", label: "Instagram user_id", type: "text", required: true, placeholder: "12345678" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "100", defaultValue: 100 },
  ],
  tikhub_x_user_followers: [
    { key: "username", label: "X 账号名", type: "text", required: true, placeholder: "momcozy" },
    { key: "max_items", label: "最大条数", type: "number", required: false, placeholder: "100", defaultValue: 100 },
  ],
  tikhub_tiktok_creator_insights: [
    { key: "unique_id", label: "创作者账号名", type: "text", required: true, placeholder: "momcozy_official" },
    { key: "time_range", label: "时间范围", type: "text", required: false, placeholder: "30d" },
  ],
  tikhub_tiktok_creator_insights_trend: [
    { key: "unique_id", label: "创作者账号名", type: "text", required: true, placeholder: "momcozy_official" },
    { key: "time_range", label: "时间范围", type: "text", required: false, placeholder: "30d" },
  ],
  tikhub_tiktok_creator_account_health: [
    { key: "unique_id", label: "创作者账号名", type: "text", required: true, placeholder: "momcozy_official" },
  ],
  tikhub_tiktok_ads_detail: [
    { key: "ad_id", label: "广告 ID", type: "text", required: true, placeholder: "7234567890" },
  ],
  tikhub_tiktok_ads_keyword_suggest: [
    { key: "keyword", label: "关键词", type: "text", required: true, placeholder: "breast pump" },
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
  ],
  apify_google_play_reviews_scraper: [
    { key: "appId", label: "App ID (包名)", type: "text", required: true, placeholder: "com.momcozy.app" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
    { key: "language", label: "语言", type: "text", required: false, placeholder: "en" },
  ],
  apify_ebay_sold_listings_scraper: [
    { key: "search", label: "搜索词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok_transcript_extractor: [
    { key: "startUrls", label: "TikTok 视频 URL", type: "text", required: true, placeholder: "https://www.tiktok.com/@user/video/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_youtube_transcript_scraper: [
    { key: "startUrls", label: "YouTube 视频 URL", type: "text", required: true, placeholder: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" },
    { key: "language", label: "字幕语言", type: "text", required: false, placeholder: "en" },
  ],
  apify_tiktok_creative_center: [
    { key: "country_code", label: "国家代码", type: "text", required: false, placeholder: "US" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_facebook_group_scraper: [
    { key: "startUrls", label: "Facebook 群组 URL", type: "text", required: true, placeholder: "https://www.facebook.com/groups/..." },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_similarweb_scraper: [
    { key: "startUrls", label: "竞品网站 URL", type: "text", required: true, placeholder: "https://www.elvie.com" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_tiktok_shop_search_scraper: [
    { key: "keyword", label: "商品关键词", type: "text", required: true, placeholder: "wearable breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_target_products_scraper: [
    { key: "startUrls", label: "Target 商品 URL", type: "text", required: true, placeholder: "https://www.target.com/s?searchTerm=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_facebook_marketplace_scraper: [
    { key: "startUrls", label: "Facebook Marketplace URL", type: "text", required: true, placeholder: "https://www.facebook.com/marketplace/search?query=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_linkedin_jobs_scraper: [
    { key: "keyword", label: "职位关键词", type: "text", required: true, placeholder: "product manager momcozy" },
    { key: "location", label: "地区", type: "text", required: false, placeholder: "United States" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_linkedin_company_employees_scraper: [
    { key: "companyUrl", label: "LinkedIn 公司 URL", type: "text", required: true, placeholder: "https://www.linkedin.com/company/momcozy/" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_linkedin_company_search_scraper: [
    { key: "keyword", label: "公司关键词", type: "text", required: true, placeholder: "breast pump manufacturer" },
    { key: "location", label: "地区", type: "text", required: false, placeholder: "United States" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_instagram_hashtag_scraper: [
    { key: "hashtags", label: "话题标签 (逗号分隔)", type: "text", required: true, placeholder: "breastpump,momcozy" },
    { key: "resultsLimit", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_youtube_comment_scraper: [
    { key: "startUrls", label: "视频 URL", type: "text", required: true, placeholder: "https://www.youtube.com/watch?v=..." },
    { key: "maxComments", label: "最大评论数", type: "number", required: false, placeholder: "100", defaultValue: 100 },
  ],
  apify_reddit_community_monitor: [
    { key: "startUrls", label: "Reddit URL", type: "text", required: true, placeholder: "https://www.reddit.com/r/breastfeeding/" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_google_play_scraper: [
    { key: "queries", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_amazon_review_scraper: [
    { key: "asin", label: "ASIN", type: "text", required: true, placeholder: "B09XXXXXX" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_walmart_scraper: [
    { key: "startUrls", label: "Walmart URL", type: "text", required: true, placeholder: "https://www.walmart.com/search?q=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_trustpilot_scraper: [
    { key: "startUrls", label: "Trustpilot 商家页 URL", type: "text", required: true, placeholder: "https://www.trustpilot.com/review/momcozy.com" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_appstore_scraper: [
    { key: "appId", label: "App Store App ID", type: "text", required: true, placeholder: "1234567890" },
    { key: "maxReviews", label: "最大评价数", type: "number", required: false, placeholder: "50", defaultValue: 50 },
  ],
  apify_ebay_scraper: [
    { key: "startUrls", label: "eBay URL", type: "text", required: true, placeholder: "https://www.ebay.com/sch/i.html?_nkw=breast+pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_x_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_snapchat_profile_scraper: [
    { key: "usernames", label: "Snapchat 账号 (逗号分隔)", type: "text", required: true, placeholder: "momcozy" },
  ],
  apify_snapchat_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_linkedin_profile_scraper: [
    { key: "profileUrls", label: "LinkedIn 个人主页 URL (逗号分隔)", type: "text", required: true, placeholder: "https://www.linkedin.com/in/johndoe/" },
  ],
  apify_linkedin_company_scraper: [
    { key: "companyUrls", label: "LinkedIn 公司 URL (逗号分隔)", type: "text", required: true, placeholder: "https://www.linkedin.com/company/momcozy/" },
  ],
  apify_linkedin_ads_scraper: [
    { key: "searchTerms", label: "广告搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_reddit_ads_scraper: [
    { key: "searchTerms", label: "搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_x_ads_transparency_scraper: [
    { key: "searchTerms", label: "广告搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_tiktok_ads_library_scraper: [
    { key: "searchTerms", label: "广告搜索词", type: "text", required: true, placeholder: "breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_google_ads_transparency_scraper: [
    { key: "searchTerms", label: "广告搜索词", type: "text", required: true, placeholder: "momcozy breast pump" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_meta_ads_library_scraper: [
    { key: "searchTerms", label: "广告搜索词", type: "text", required: true, placeholder: "momcozy" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
  apify_perplexity_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "best wearable breast pump" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_chatgpt_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "recommend a breast pump" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_gemini_scraper: [
    { key: "queries", label: "查询词", type: "text", required: true, placeholder: "best breast pump 2026" },
    { key: "maxQueries", label: "最大查询数", type: "number", required: false, placeholder: "5", defaultValue: 5 },
  ],
  apify_indeed_scraper: [
    { key: "queries", label: "职位搜索词", type: "text", required: true, placeholder: "product manager baby products" },
    { key: "maxItems", label: "最大条数", type: "number", required: false, placeholder: "20", defaultValue: 20 },
  ],
};

function getDefaultParams(endpoint_type: string): Record<string, string | number> {
  const fields = PARAM_FIELDS[endpoint_type] ?? [];
  const out: Record<string, string | number> = {};
  for (const f of fields) {
    if (f.defaultValue !== undefined) out[f.key] = f.defaultValue;
    else if (f.type === "text") out[f.key] = "";
    else out[f.key] = 0;
  }
  return out;
}

/* ── Result card ── */
function RunResult({ result }: { result: QuickCollectResponse }) {
  const router = useRouter();
  const ok = result.status === "completed";
  return (
    <div
      className={`mt-4 rounded-[var(--radius-3)] border p-4 ${
        ok
          ? "border-[var(--state-success)] bg-[var(--success-soft)]"
          : "border-[var(--state-danger)] bg-[var(--danger-soft)]"
      }`}
    >
      <div className="flex items-start gap-3">
        {ok ? (
          <CheckCircle size={18} className="mt-0.5 shrink-0 text-[var(--state-success)]" />
        ) : (
          <AlertCircle size={18} className="mt-0.5 shrink-0 text-[var(--state-danger)]" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {ok ? "采集完成" : "采集失败"}
          </p>
          {ok ? (
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              写入 <span className="font-semibold text-[var(--state-success)]">{result.records_count}</span> 条原始记录
            </p>
          ) : (
            <p className="mt-1 text-sm text-[var(--state-danger)]">
              {result.error_message ?? "未知错误"}
            </p>
          )}
          <div className="mt-3 grid gap-1 text-xs text-[var(--text-tertiary)]">
            <span>运行 ID: <code className="font-mono">{result.task_run_id.slice(0, 8)}…</code></span>
            <span>状态: <code>{result.status}</code></span>
          </div>
          {ok && (
            <button
              type="button"
              onClick={() => router.push(`/collect/${result.task_run_id}`)}
              className="mt-3 flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--text-inverse)] transition-opacity hover:opacity-90"
            >
              查看详细结果
              <ArrowRight size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Drawer ── */
type Props = {
  endpoint: CollectorEndpoint;
  open: boolean;
  onClose: () => void;
};

export function QuickCollectDrawer({ endpoint, open, onClose }: Props) {
  const fields = PARAM_FIELDS[endpoint.endpoint_type] ?? [];

  const [params, setParams] = useState<Record<string, string | number>>(
    () => getDefaultParams(endpoint.endpoint_type)
  );
  const [projectId, setProjectId] = useState<string>("");

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () =>
      postQuickCollect({
        project_id: projectId,
        endpoint_type: endpoint.endpoint_type,
        params,
        label: endpoint.label,
      }),
  });

  /* sync project_id when projects loaded */
  if (projects && projects.length > 0 && !projectId) {
    setProjectId(projects[0].id);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  function handleClose() {
    mutation.reset();
    onClose();
  }

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-[var(--overlay-scrim)]"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`快速采集：${endpoint.label}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-primary)] shadow-[var(--shadow-overlay)]"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border-subtle)] px-6 py-4">
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              快速采集
            </h2>
            <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
              {endpoint.label}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="关闭"
            className="rounded-[var(--radius-2)] p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Meta */}
          <div className="mb-5 rounded-[var(--radius-2)] bg-[var(--surface-muted)] px-4 py-3 text-xs text-[var(--text-tertiary)]">
            <p>{endpoint.description}</p>
            {endpoint.cost_hint && (
              <p className="mt-1 text-[var(--state-info)]">
                预估费用：{endpoint.cost_hint}
              </p>
            )}
          </div>

          {mutation.isSuccess ? (
            <>
              <RunResult result={mutation.data} />
              <button
                type="button"
                onClick={() => mutation.reset()}
                className="mt-4 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                再次采集
              </button>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="grid gap-5">
              {/* Project selector */}
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-[var(--text-primary)]">
                  所属项目 <span className="text-[var(--state-danger)]">*</span>
                </label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  required
                  className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                >
                  {!projects || projects.length === 0 ? (
                    <option value="">加载中...</option>
                  ) : (
                    projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Dynamic param fields */}
              {fields.map((field) => (
                <div key={field.key} className="grid gap-1.5">
                  <label className="text-sm font-medium text-[var(--text-primary)]">
                    {field.label}
                    {field.required && (
                      <span className="ml-1 text-[var(--state-danger)]">*</span>
                    )}
                  </label>
                  <input
                    type={field.type}
                    value={String(params[field.key] ?? "")}
                    onChange={(e) =>
                      setParams((prev) => ({
                        ...prev,
                        [field.key]:
                          field.type === "number"
                            ? Number(e.target.value)
                            : e.target.value,
                      }))
                    }
                    placeholder={field.placeholder}
                    required={field.required}
                    min={field.type === "number" ? 1 : undefined}
                    className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                  />
                </div>
              ))}

              {/* Error banner */}
              {mutation.isError && (
                <div className="rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
                  {mutation.error instanceof ApiError
                    ? mutation.error.message
                    : "采集失败，请稍后重试"}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={mutation.isPending}
                  className="flex-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-muted)] disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={mutation.isPending || !projectId}
                  className="flex flex-1 items-center justify-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--text-inverse)] transition-colors hover:bg-[var(--action-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {mutation.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      采集中...
                    </>
                  ) : (
                    "▶ 开始采集"
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
