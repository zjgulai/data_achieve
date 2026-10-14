# Apify 采集方案卡 — Google

日期：2026-10-14。数据来源同总说明。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| SERP 搜索结果（含 PAA/AI Overview） | ● | apify/google-search-scraper | scraperlink/google-search-results-serp-scraper | apify/rag-web-browser（只要正文） |
| Maps 商户（搜索式） | ● | compass/crawler-google-places | compass/google-maps-extractor | lukaskrivka/google-maps-with-contact-details |
| Maps 评论 | ● | compass/Google-Maps-Reviews-Scraper | compass/crawler-google-places（reviews 事件） | apify/rag-web-browser（正文兜底） |
| Trends 趋势 | ● | data_xplorer/google-trends-fast-scraper | ~~apify/google-trends-scraper~~（56.6% 弃用） | — |
| News 新闻 | ● | data_xplorer/google-news-scraper-fast | apify/rag-web-browser | — |
| AI Overviews 专项 | ● | apify/google-ai-overviews-scraper | google-search-scraper（aiOverview 字段） | — |
| Google Ads 素材 | ● | lexis-solutions/google-ads-scraper | — | — |

**弃用决定：apify/google-trends-scraper 实测 30 天成功率 56.6%，不进任何位置**（官方出品但数据不达标）。

## 主力 actor 详情

### apify/google-search-scraper — SERP 主力
- 稳定性：ok 98.4%，23167 用户/30 天
- 计费：result $0.0027/条（按结果页计）
- 输入 33 项：**queries 是字符串不是数组**（实测 400 教训）；maxPagesPerQuery、aiOverview/aiModeSearch/geminiSearch/perplexitySearch/chatGptSearch/copilotSearch 六个 AI 搜索开关对象
- 输出 15 字段（实测）：searchQuery, url, hasNextPage, serpProviderCode, organicResults[], paidResults[], paidProducts[], relatedQueries[], suggestedResults[], peopleAlsoAsk[], aiOverview{}, customData, htmlSnapshotUrl, #debug, #error
- 定位：一个入口同时拿自然结果 + PAA + AI Overview，SERP 类信息密度最高

### compass/crawler-google-places — Maps 商户主力
- 稳定性：ok 97.0%，**39828 用户（十平台用户量第二）**
- 计费：place-scraped $0.004、place-details $0.002、contact-details $0.002、review-scraped $0.0005
- 输入 39 项：searchStringsArray + locationQuery；语言/评分过滤/跳过歇业等
- 输出 132 字段（生态最富）：searchString, rank, title, subTitle, description, price, categoryName, address, neighborhood, street, city, postalCode, state, countryCode, website, phone, plusCode, openingHours, categories, totalScore, reviewsCount, photos, location(lat/lng), placeId, fid, cid + 联系方式/预约/配送等业务属性
- 一个 actor 覆盖商户全生命周期字段

### compass/Google-Maps-Reviews-Scraper — Maps 评论主力
- 稳定性：ok 99.7%
- 计费：review-scraped $0.0005/条（比商户本体便宜 8 倍）
- 输入 9 项：startUrls（精确 place URL）或 placeIds；maxReviews、reviewsSort、reviewsStartDate、language
- 输出 51 字段：reviewerId, reviewerUrl, name, reviewerNumberOfReviews, isLocalGuide, reviewerPhotoUrl, text, textTranslated, publishAt, publishedAtDate, likesCount, reviewId, reviewUrl, reviewOrigin, stars, rating, responseFromOwnerDate
- 坑：startUrls 必须是**精确 place URL**（含 @lat,lng 的完整链接），搜索单词链接会 0 条（本项目试跑已踩）；优先用 placeIds

### data_xplorer/google-trends-fast-scraper — Trends 主力
- 稳定性：ok 99.5%（替代官方 56.6% 的 apify/google-trends-scraper）
- 输出 33 字段：geo, language, trending_searches[], trends_url, timeframe_hours, max_items, timestamp
- 输入 10 项：searchTerms + geo + timeRange

### data_xplorer/google-news-scraper-fast — News 主力
- 稳定性：ok 99.4%
- 输出 17 字段：title, source, url, publishedAt, publishedTimestamp, image, description, metadata, keyword, sourceType
- 输入 10 项：keywords/maxArticles/timeframe/region_language/topics

### apify/google-ai-overviews-scraper — AIO 专项主力
- 稳定性：ok 98.8%
- 输出 8 字段：query, type, text, sources[{url,title,description}], error
- 定位：只要 AIO 正文+引用源时的轻量通道（比全量 SERP 便宜）

### lexis-solutions/google-ads-scraper — Google Ads 主力
- 稳定性：ok 99.4%
- 输出 30 字段：id, advertiserId, advertiserName, creativeId, format, url, previewUrl, firstShownAt, lastShownAt, impressions, shownCountries, countryStats
- 输入 5 项：域名/关键词 + 国家/格式过滤

## 降级链

1. **SERP**：scraperlink（99.9%，字段 8 但含 organic 全集，按 SERP 专项计费）→ rag-web-browser（98.8%，输出 markdown 正文，丢 SERP 结构保内容）。
2. **Maps 商户**：google-maps-extractor（96.2%，53 字段）→ lukaskrivka（93.7%，42 字段，特色是 emails/phones/社交账号 15 种联系方式增强）。
3. **评论兜底**：crawler-google-places 开 review-scraped 事件（$0.0005 同价）。
4. **News 兜底**：rag-web-browser 抓 Google News 页。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| google-search-scraper 400 "queries must be string" | queries 是字符串 | 入参审计按 schema 拦截 |
| Maps Reviews 0 条 | startUrls 非精确 place URL | 用 placeIds 或完整 @lat,lng 链接 |
| 官方 trends actor 近半失败 | 上游不稳定 | 换 data_xplorer，端点标记 deprecated |
| lukaskrivka 联系方式字段有 null | 部分商户无公开邮箱 | 字段级容错，勿当失败 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| apify/google-search-scraper / google-trends-scraper / google-ai-overviews-scraper / rag-web-browser / data_xplorer google-news | 前四保留；**google-trends-scraper 建议替换为 data_xplorer/google-trends-fast-scraper** |
| compass/crawler-google-places / Google-Maps-Reviews-Scraper | 保留，与主力一致 |
| — | 新增建议：google-ads-scraper（Google Ads 维度缺口）、scraperlink SERP（成本降级） |
