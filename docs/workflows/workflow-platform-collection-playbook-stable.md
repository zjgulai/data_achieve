---
name: platform-collection-playbook
description: 全平台数据采集方法手册，覆盖 TikHub、Apify 及内部采集器共 137 个已核验端点（50个平台、14种数据类型）。说明每个平台的采集能力、调用参数和成本估算。当需要接入新平台、确认采集路径、或在平台能力中心配置采集任务时使用。
---

# 平台数据采集手册

> **版本**：2026-08-16 · **状态**：已核验端点 137 / 禁用 11 · **负责人**：数据工程
>
> 本手册覆盖系统当前所有已核验采集端点，包含调用示例和参数说明。
> 调用入口统一为 `/api/collectors/catalog`，前端在「平台能力中心」页面渲染（三层矩阵：平台分类 → 内容类型 → 采集方式）。

---

## 概览

| 采集器组 | 方法 | 端点数 | 平台 |
|---|---|---|---|
| TikHub Social | tikhub | 45 | TikTok / Instagram / 小红书 / YouTube / Reddit / X / Threads / LinkedIn / Lemon8 |
| Apify 社交 | apify | 20 | Instagram / Facebook / TikTok / YouTube / X / Reddit / Pinterest / Bluesky / Telegram / Snapchat |
| Apify 电商 & 评价 | apify | 18 | Amazon / Walmart / Temu / SHEIN / AliExpress / TikTok Shop / Trustpilot / Google Play / App Store / eBay / Etsy / Tripadvisor / Yelp / Booking / Airbnb / Shopify |
| Apify Google 生态 | apify | 9 | Google Search / Maps / Maps Reviews / Trends / News / AI Overviews / Google Play Reviews |
| Apify AI 搜索 | apify | 6 | ChatGPT / Perplexity / Gemini（含 search + scraper 两版） |
| Apify 广告情报 | apify | 11 | Meta Ads / Google Ads / TikTok Ads / Snap Ads / Pinterest Ads / TikTok Creative Center |
| Apify B2B & LinkedIn | apify | 14 | LinkedIn（帖子/职位/员工/公司搜索）/ Threads / Glassdoor / Product Hunt / Crunchbase / HN / Indeed |
| Apify 社群 & 渠道 | apify | 5 | Facebook Group / TikTok Shop Search / SimilarWeb / Target / Facebook Marketplace |
| Apify 内容分析 | apify | 4 | TikTok字幕 / YouTube字幕 / Website Crawler / RAG Browser |
| Apify PR 媒体 | apify | 11 | Google News + 媒体账号监测（Instagram/TikTok/YouTube/Facebook/X/Pinterest）|
| GitHub | github_api | 2 | GitHub Repo / Topics |
| RSS / 公开网页 | rss + web_crawl | 15 | RSS 订阅源 + Web Snapshot |

**数据类型覆盖（14种）**：`post` · `comment` · `account` · `product` · `review` · `ad` · `job` · `trend` · `ai_answer` · `news` · `web_page` · `repo` · `feed` · `search`


## 1. TikHub Social

**采集器类型**：`tikhub_social`  
**服务商**：TikHub REST API（`https://api.tikhub.io`）  
**凭据**：`TIKHUB_API_KEY`（存于 `apps/api/.env`）  
**成本**：约 $0.001 / 条记录  
**调用方式**：后端通过 `TikHubSocialCollector` 统一调度，`endpoint_type` 字段区分具体端点。

### 1.1 TikTok

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_tiktok_video_search` | 按关键词搜索 TikTok 公开视频 | `keyword` | `max_items`, `cursor`, `sort_type` |
| `tikhub_tiktok_user_posts` | 获取指定账号的公开视频列表 | `unique_id` | `max_items`, `max_cursor` |
| `tikhub_tiktok_hashtag_posts` | 获取指定话题下的视频列表 | `ch_id` | `max_items`, `cursor` |

**调用示例**：

```python
config = {
    "endpoint_type": "tikhub_tiktok_video_search",
    "keyword": "婴儿推车",
    "max_items": 50,
}
result = await collector.collect(config)
```

返回字段：`id`, `desc`, `createTime`, `author.uniqueId`, `stats.playCount`, `stats.diggCount`

### 1.2 Instagram

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_instagram_search` | 按关键词搜索公开帖子 | `keyword` | `max_items` |
| `tikhub_instagram_user_posts` | 获取指定账号的公开帖子列表 | `user_id` | `max_items`, `max_id` |

**调用示例**：

```python
config = {
    "endpoint_type": "tikhub_instagram_search",
    "keyword": "stroller review",
    "max_items": 30,
}
```

### 1.3 小红书

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_xiaohongshu_search` | 按关键词搜索公开笔记 | `keyword` | `max_items`, `sort_type` |

`sort_type` 可选值：`general`（综合）/ `time`（最新）/ `hot`（热门）

### 1.4 YouTube（TikHub 通道）

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_youtube_search` | 按关键词搜索公开视频 | `keyword` | `max_items` |
| `tikhub_youtube_channel_videos` | 获取指定频道的公开视频列表 | `channel_id` | `max_items` |

### 1.5 Reddit（TikHub 通道）

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_reddit_search` | 按关键词搜索 Reddit 公开帖子 | `keyword` | `max_items` |
| `tikhub_reddit_subreddit_posts` | 获取指定 Subreddit 帖子列表 | `subreddit` | `max_items` |

### 1.6 X / Twitter（TikHub 通道）

| 端点类型 | 说明 | 必填参数 | 可选参数 |
|---|---|---|---|
| `tikhub_x_search` | 按关键词搜索公开推文 | `keyword` | `max_items` |
| `tikhub_x_user_tweets` | 获取指定账号的公开推文列表 | `username` | `max_items` |

---

## 2. Apify 社交平台

**采集器类型**：`apify_actor`  
**服务商**：Apify（`https://api.apify.com`）  
**凭据**：`APIFY_API_TOKEN`（存于 `apps/api/.env`）  
**调用方式**：后端通过 `ApifyActorCollector` 统一调度，`actor_id` 字段区分 Actor。

### 2.1 Instagram

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_instagram_scraper` | `apify/instagram-scraper` | 帖子搜索（关键词 / 话题 / 账号）；支持 Reels / Stories | `search` |
| `apify_instagram_profile_scraper` | `apify/instagram-profile-scraper` | 账号资料和帖子列表 | `usernames` |

**调用示例**：

```python
config = {
    "endpoint_type": "apify_instagram_scraper",
    "search": "baby stroller",
    "resultsLimit": 100,
    "resultsType": "posts",
}
```

### 2.2 Facebook

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_facebook_posts_scraper` | `apify/facebook-posts-scraper` | 公开帖子（页面 / 群组 / 用户时间线） | `startUrls` |
| `apify_facebook_comments_scraper` | `apify/facebook-comments-scraper` | 帖子评论：产品反馈、危机信号 | `startUrls` |

成本：`$0.0017+` / 运行

### 2.3 TikTok（Apify 通道）

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_tiktok_scraper` | `clockworks/tiktok-scraper` | 视频搜索（关键词 / 话题 / 账号） | `searchQueries` |
| `apify_tiktok_comments_scraper` | `clockworks/tiktok-comments-scraper` | 视频评论：产品痛点、购买意向 | `postURLs` |

成本：`$0.5+`（视频量）

### 2.4 YouTube（Apify 通道）

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_youtube_scraper` | `streamers/youtube-scraper` | 视频搜索：测评 / 教程 / 竞品视频 | `searchQueries` |
| `apify_youtube_comments_scraper` | `streamers/youtube-comments-scraper` | 评论：产品体验、问题挖掘 | `startUrls` |

### 2.5 X / Twitter（Apify 通道）

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_x_tweet_scraper` | `apidojo/tweet-scraper` | 推文搜索：实时舆情、媒体传播、危机预警 | `searchTerms` |

### 2.6 Reddit（Apify 通道）

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_reddit_scraper` | `trudax/reddit-scraper-lite` | 帖子与评论：真实讨论、竞品口碑 | `startUrls` |

成本：`$0.04+`

---

## 3. Apify 电商 & 评价

### 3.1 电商平台商品

| 端点类型 | 平台 | Actor | 说明 | 必填参数 |
|---|---|---|---|---|
| `apify_amazon_product_scraper` | Amazon | `junglee/Amazon-crawler` | 商品详情：价格 / 库存 / 变体 / Q&A | `startUrls` |
| `apify_walmart_product_scraper` | Walmart | `e-commerce/walmart-product-detail-scraper` | 商品详情：价格监测、库存追踪 | `startUrls` |
| `apify_temu_products_scraper` | Temu | `amit123/temu-products-scraper` | 低价竞品监测 | `startUrls` |
| `apify_shein_product_scraper` | SHEIN | `shahidirfan/shein-product-scraper` | 快时尚竞品监测 | `startUrls` |
| `apify_aliexpress_products_scraper` | AliExpress | `devcake/aliexpress-products-scraper` | 供应链监测 | `startUrls` |
| `apify_tiktok_shop_scraper` | TikTok Shop | `clockworks/tiktok-shop-scraper` | 直播电商商品监测 | `startUrls` |
| `apify_ebay_product_scraper` | eBay | `dtrungtin/ebay-items-scraper` | 二手 / 竞价商品监测 | `startUrls` |
| `apify_etsy_scraper` | Etsy | `vbarbarosh/etsy-scraper` | 手工 / 定制商品监测 | `startUrls` |
| `apify_shopify_scraper` | Shopify | `cwlimit/shopify-scraper` | Shopify 独立站商品 | `startUrls` |

### 3.2 评价平台

| 端点类型 | 平台 | Actor | 说明 | 必填参数 |
|---|---|---|---|---|
| `apify_amazon_reviews_scraper` | Amazon | `junglee/amazon-reviews-scraper` | 竞品口碑 / 痛点挖掘 | `asin` |
| `apify_walmart_reviews_scraper` | Walmart | `e-commerce/walmart-reviews-scraper` | 北美市场用户反馈 | `startUrls` |
| `apify_trustpilot_reviews_scraper` | Trustpilot | `memo23/trustpilot-scraper-ppe` | 品牌口碑、竞品对比 | `startUrls` |
| `apify_appstore_reviews_scraper` | Apple App Store | `ni8mr/app-store-reviews` | App 评价：功能反馈、版本问题 | `startUrls` |
| `apify_tripadvisor_reviews_scraper` | Tripadvisor | `maxcopell/tripadvisor-reviews` | 酒店 / 景点评价 | `startUrls` |
| `apify_yelp_scraper` | Yelp | `tri_angle/yelp-scraper` | 本地商家评价 | `startUrls` |

### 3.3 住宿 & 本地

| 端点类型 | 平台 | Actor | 说明 | 必填参数 |
|---|---|---|---|---|
| `apify_booking_scraper` | Booking.com | `voyager/booking-scraper` | 酒店价格 / 评价 | `startUrls` |
| `apify_airbnb_scraper` | Airbnb | `tri_angle/airbnb-scraper` | 短租价格 / 评价 | `startUrls` |

---

## 4. Apify Google 生态

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_google_search_scraper` | `apify/google-search-scraper` | Google 搜索结果：SEO 监测、竞品曝光 | `queries` |
| `apify_google_maps_scraper` | `compass/crawler-google-places` | Google 地图 POI：门店 / 商圈 | `searchStringsArray` |
| `apify_google_maps_reviews_scraper` | `compass/google-maps-reviews-scraper` | Google 地图评价：本地口碑 | `startUrls` |
| `apify_google_trends_scraper` | `emastra/google-trends-scraper` | Google 趋势：搜索热度时序 | `searchTerms` |
| `apify_google_news_scraper` | `lhotanova/google-news-scraper` | Google 新闻：媒体报道监测 | `queries` |
| `apify_google_ai_overviews_scraper` | `apify/google-ai-overviews-scraper` | Google AI Overviews：生成式搜索摘要 | `queries` |

**调用示例**（Google 搜索）：

```python
config = {
    "endpoint_type": "apify_google_search_scraper",
    "queries": ["best baby stroller 2026", "婴儿推车推荐"],
    "maxPagesPerQuery": 3,
    "countryCode": "us",
}
```

---

## 5. Apify AI 搜索

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_chatgpt_search_scraper` | `apify/chatgpt-scraper` | ChatGPT Search 返回内容：AI 推荐品牌监测 | `queries` |
| `apify_perplexity_search_scraper` | `muhammedogz/perplexity-ai-scraper` | Perplexity 答案：AI 引用来源 | `queries` |
| `apify_gemini_search_scraper` | `apify/gemini-scraper` | Gemini 搜索结果：Google AI 推荐监测 | `queries` |

> 这三个端点用于监测品牌在 AI 搜索引擎中的曝光和推荐位，适合与 Google 搜索结果联动分析。

---

## 6. Apify 广告情报

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_facebook_ads_scraper` | `apify/facebook-ads-scraper` | Meta 广告素材库：竞品投放策略 | `searchTerms` |
| `apify_google_ads_scraper` | `apify/google-ads-scraper` | Google 广告：关键词竞投 | `queries` |
| `apify_tiktok_ads_scraper` | `clockworks/tiktok-ads-scraper` | TikTok 广告素材：竞品创意 | `searchQueries` |
| `apify_snapchat_ads_scraper` | `tri_angle/snapchat-ads-scraper` | Snap 广告素材 | `searchTerms` |
| `apify_pinterest_ads_scraper` | `tri_angle/pinterest-ads-scraper` | Pinterest 推广 Pin：视觉竞品 | `searchTerms` |

**调用示例**（Meta 广告库）：

```python
config = {
    "endpoint_type": "apify_facebook_ads_scraper",
    "searchTerms": ["baby stroller", "婴儿车"],
    "country": "US",
    "maxAds": 200,
}
```

---

## 7. Apify B2B & 内容平台

### 7.1 专业社交 & 职场

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_linkedin_company_posts_scraper` | `apimaestro/linkedin-post-search-scraper` | LinkedIn 企业动态：B2B 竞品发声 | `startUrls` |
| `apify_glassdoor_scraper` | `bebity/glassdoor-reviews-scraper` | Glassdoor 评价：雇主品牌监测 | `startUrls` |
| `apify_indeed_jobs_scraper` | `misceres/indeed-scraper` | Indeed 职位：竞品招聘动向 | `startUrls` |

### 7.2 内容社区

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_threads_profile_scraper` | `apidojo/threads-profile-scraper` | Threads 账号资料和帖子列表 | `usernames` |
| `apify_threads_posts_scraper` | `apidojo/threads-posts-scraper` | Threads 内容：话题讨论 | `searchQueries` |
| `apify_pinterest_scraper` | `apify/pinterest-scraper` | Pinterest 图钉：视觉趋势、灵感版 | `searchQueries` |
| `apify_bluesky_scraper` | `blue-sky/bluesky-scraper` | Bluesky 去中心化社交内容 | `searchTerms` |

### 7.3 技术 & 资讯

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_hacker_news_scraper` | `onescales/hacker-news-data` | Hacker News 帖子与评论 | `startUrls` |
| `apify_telegram_scraper` | `apify/telegram-scraper` | Telegram 公开频道内容 | `channelUsernames` |

### 7.4 投资 & 竞品

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_product_hunt_scraper` | `scrapeninja/product-hunt-scraper` | Product Hunt 新产品：市场动态 | `startUrls` |
| `apify_crunchbase_scraper` | `apify/crunchbase-scraper` | Crunchbase 公司信息：融资动态 | `startUrls` |

---

## 8. Apify PR 媒体监测

### 8.1 Google 新闻搜索

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_google_news_media_search` | `lhotanova/google-news-scraper` | Google 新闻媒体搜索（已预核验） | `queries` |

### 8.2 媒体账号监测

| 端点类型 | 平台 | 说明 |
|---|---|---|
| `apify_instagram_media_profile_scraper` | Instagram | 媒体账号发布监测 |
| `apify_tiktok_media_profile_scraper` | TikTok | 媒体账号内容监测 |
| `apify_youtube_media_channel_scraper` | YouTube | 媒体频道视频监测 |
| `apify_facebook_media_page_scraper` | Facebook | 媒体页面发布监测 |
| `apify_x_media_account_scraper` | X | 媒体账号推文监测 |
| `apify_pinterest_media_profile_scraper` | Pinterest | 媒体 Pinterest 账号监测 |

这六个端点共享同一调用方式，`required_params` 均为 `startUrls`（目标媒体账号页面 URL）。

### 8.3 通用网页内容

| 端点类型 | Actor | 说明 | 必填参数 |
|---|---|---|---|
| `apify_website_content_crawler` | `apify/website-content-crawler` | 全站爬取 + 结构化内容提取 | `startUrls` |
| `apify_web_scraper` | `apify/web-scraper` | 自定义 CSS/JS 规则提取 | `startUrls` |
| `apify_rag_web_browser` | `apify/rag-web-browser` | RAG 场景网页读取 + 摘要 | `query` |

---

## 9. GitHub

**采集器类型**：`github`  
**服务商**：GitHub REST API  
**凭据**：`GITHUB_TOKEN`（可选；未配置时使用匿名限速 60 req/h）

| 端点类型 | 说明 | 必填参数 |
|---|---|---|
| `github_repo_search` | 仓库搜索：关键词、语言、星数 | `query` |
| `github_repo_issues` | 仓库 Issues 列表：功能需求、Bug 讨论 | `owner`, `repo` |
| `github_repo_commits` | 仓库提交记录：更新频率、贡献者 | `owner`, `repo` |
| `github_user_repos` | 用户 / 组织公开仓库列表 | `username` |
| `github_trending` | GitHub Trending 日榜 / 周榜 | — |

**调用示例**：

```python
config = {
    "endpoint_type": "github_repo_search",
    "query": "baby monitor language:python stars:>100",
    "per_page": 30,
}
```

---

## 10. RSS & 公开网页

**采集器类型**：`rss_web`  
**服务商**：自研 HTTP Collector（无需 API Key）  
**成本**：免费

### 10.1 母婴 & 育儿 RSS

以下 RSS 端点已核验，可直接订阅：

| 端点类型 | 来源 | URL |
|---|---|---|
| `rss_parents_magazine` | Parents 杂志 | `https://www.parents.com/rss/` |
| `rss_babycenter` | BabyCenter | `https://www.babycenter.com/rss` |
| `rss_what_to_expect` | What to Expect | `https://www.whattoexpect.com/rss`（当前 disabled） |
| `rss_romper` | Romper | `https://www.romper.com/rss` |

**调用示例**：

```python
config = {
    "endpoint_type": "rss_feed",
    "url": "https://www.parents.com/rss/",
}
```

### 10.2 PR 媒体 Listicle 网页快照

| 端点类型 | 来源 | 说明 |
|---|---|---|
| `generic_web_forbes_vetted` | Forbes Vetted | 母婴 / 育儿 Listicle |
| `generic_web_good_housekeeping` | Good Housekeeping | 母婴产品推荐 |
| `generic_web_babylist` | Babylist | 产品推荐 / 注册礼单 |
| `generic_web_babycenter` | BabyCenter | 产品推荐 |

---

## 11. 生产部署

代码已推送至分支 `codex/social-api-private-matrix-20260708`。在服务器上执行以下命令更新生产环境：

```bash
# 在服务器 /opt/data-achieve-scrapy/app 目录执行

# 1. 拉取最新代码
git fetch origin
git checkout codex/social-api-private-matrix-20260708
git pull origin codex/social-api-private-matrix-20260708

# 2. 预检
bash scripts/deploy-preflight-scrapy.sh

# 3. 重建并启动 API 容器（catalog 路由为纯内存计算，无需迁移）
docker compose -f configs/deploy/scrapy/docker-compose.yml \
  --env-file /opt/data-achieve-scrapy/.env.production \
  up --build --detach api

# 4. 验证
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/health
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/collectors/catalog | python3 -m json.tool | grep '"status": "verified"' | wc -l
# 期望输出：91
```

> 前端无需重新部署。`/api/collectors/catalog` 是纯内存路由，重建 API 镜像即可生效。

---

## 12. 快速选型指引

| 需求场景 | 推荐端点 | 说明 |
|---|---|---|
| TikTok UGC 关键词监测（低成本） | `tikhub_tiktok_video_search` | $0.001/条，实时 |
| TikTok UGC 大批量（高覆盖） | `apify_tiktok_scraper` | 支持多关键词并发 |
| Amazon 竞品评价挖掘 | `apify_amazon_reviews_scraper` | 必填 ASIN |
| Google 搜索 SEO 监测 | `apify_google_search_scraper` | 返回排名、摘要、来源 |
| Meta 广告素材竞品分析 | `apify_facebook_ads_scraper` | 公开广告库，无需授权 |
| AI 搜索品牌曝光监测 | `apify_chatgpt_search_scraper` + `apify_perplexity_search_scraper` | 联动使用覆盖主流 AI 搜索 |
| 媒体报道追踪 | `apify_google_news_media_search` + RSS | Google 新闻 + RSS 双路径 |
| 全站内容爬取 | `apify_website_content_crawler` | 支持 JS 渲染、Markdown 输出 |
| GitHub 开源竞品监测 | `github_repo_search` + `github_repo_issues` | 免费，无需 Token |

---

## 附：调用规范

### 通用调用结构

所有采集任务通过 Workflow Task 下发，`config` 字段按平台规范填写：

```json
{
  "collector_type": "apify_actor",
  "config": {
    "endpoint_type": "apify_amazon_reviews_scraper",
    "asin": "B08XYZ1234",
    "maxReviews": 500,
    "country": "US"
  }
}
```

### 成本控制原则

1. TikHub 端点优先用于高频轻量采集（成本约 $0.001/条）。
2. Apify 端点用于批量、结构化、需要 JS 渲染的场景（成本 $0.004–$0.5+/次）。
3. GitHub 和 RSS 端点免费，适合每日增量同步。
4. 广告情报端点（Meta / TikTok Ads）仅读公开广告库，不涉及账户授权。

### 限速与重试

- TikHub：API 层自动重试 2 次（`TIKHUB_MAX_RETRY=2`），退避 1–3 秒。
- Apify：Actor 本身有队列和重试机制；超时默认 5 分钟。
- GitHub 匿名：60 req/h；配置 Token 后 5000 req/h。
- RSS：建议采集间隔 ≥ 15 分钟，避免触发目标服务器限制。
