---
name: dih-platform-pitfalls
description: Data Intelligence Hub 全平台采集坑点与限制汇总，由平台工具包生成器自动生成，按失败分类分组。当排查采集失败或评估能力边界时使用。
---

# 平台采集坑点库

> 自动生成，请勿手工编辑。catalog_digest：`79e395cea8e1565960f3ae9774723936fa8e830698a28450c5ab1c6144047f9d`
> 坑点总数：27 · 覆盖平台：18

## config_gated

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| baidu | baidu | baidu_search_results 报 “ANYCRAWL_BASE_URL is not configured” | SERP 采集依赖 AnyCrawl 服务，生产未配置 ANYCRAWL_BASE_URL | 配置 ANYCRAWL_BASE_URL（及 ANYCRAWL_API_KEY）后重建 api 容器 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| bing | bing | bing_search_results 报 “ANYCRAWL_BASE_URL is not configured” | 同上，Bing SERP 依赖 AnyCrawl | 配置 ANYCRAWL_BASE_URL（及 ANYCRAWL_API_KEY）后重建 api 容器 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | Exa 系列端点（exa_search_auto / exa_answer / exa_contents / exa_deep_* 等 16 个）调用后 records=0，错误为 “EXA_API_KEY not set” | 生产 API 容器运行时环境未注入 EXA_API_KEY；compose 已声明该变量但服务器 .env.production 未提供值 | 在服务器 .env.production 增加 EXA_API_KEY=<key> 后重建 api 容器；在此之前不要把 Exa 端点视为可采集 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | firecrawl_crawl / firecrawl_extract / firecrawl_batch_scrape 报缺 FIRECRAWL_API_KEY | FIRECRAWL_API_KEY 未在 compose/.env.production 中配置 | 配置 FIRECRAWL_API_KEY（及可选 FIRECRAWL_BASE_URL）后重建 api 容器 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| x | x | twscrape_search / _user_tweets / _trends 报 “No Twitter accounts configured” | twscrape 需要登录态账号池，生产未配置 TWITTER_ACCOUNTS_JSON / TWITTER_ACCOUNTS_FILE | 配置 TWITTER_ACCOUNTS_JSON（账号+代理）后重建；否则用 tikhub_x_* 或 apify_x_* 替代 | warning | 2026-10-09 | reports/live-sweep/latest.json |

## container_missing

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| web | web | playwright_browser_text / _html / _screenshot 返回 “playwright_not_installed: add 'browser' extra and rebuild image” | api 镜像构建时未开启 INSTALL_PLAYWRIGHT，容器内无 Chromium | 构建镜像时传 build-arg INSTALL_PLAYWRIGHT=true 重建 api 容器 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | anydoc_file_to_markdown 对 PDF 报 “markitdown ... PdfConverter MissingDependencyException” | markitdown 的可选 PDF 依赖未装进 API 镜像 | 在镜像中安装 markitdown 的 PDF extra（markitdown[pdf]）后重建；否则该端点标 verified 也是不可用的 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | browser_use_task 返回 “browser-use not installed — pip install browser-use” | browser-use 与 LLM key 均未在镜像/环境中提供 | 安装 browser-use 并配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 后重建；否则视为 config-gated | warning | 2026-10-09 | reports/live-sweep/latest.json |

## empty_records

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| linkedin | linkedin | tikhub_linkedin_* 多个端点返回 records=0（无报错），apify_linkedin_jobs/company_search 亦为空 | LinkedIn 上游对无有效会话的请求返回空结果集；演示参数不足以触发真实数据 | 视为“需真实会话/参数”的高不稳定端点；不要据此判定能力可用，接入前用小样本人工验证 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | reddit | 搜索结果零记录；帖子字段名与通用归一化器预期不一致 | Reddit 走的是 GraphQL 风格响应：标题字段是 postTitle（不是 title）、正文在 content.markdown、作者在 authorInfo.name、时间在 createdAt（形如 2026-10-03T19:08:43.382000+0000）。_normalize_generic 认不出这些字段，即便取到条目也只会得到空 text。 | reddit 已单独走 _normalize_reddit_post；新增 reddit 端点时先确认字段名，不要直接复用 _normalize_generic。 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | tikhub_reddit_search | quick-collect 返回 status=success，但 records_count=0（扫描归为 empty_records） | TikHub 的 app/fetch_dynamic_search 把结果放在 data.search，而 search 是 dict（search.dynamic.components.main.edges[].node.children[]），帖子挂在 __typename=SearchPost 的 node.post；归一化器只认 data.search 为 list，于是取到 0 条。 | 已在 _extract_items 中对 reddit 增加 _deep_find_typename(inner, "SearchPost") 深度查找，再由 _normalize_reddit_post 抽取 postTitle/url/score/authorInfo.name/subreddit.name/createdAt。实测同一响应由 0 条变为 7 条。 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | robin_darkweb_search / _username / _email 返回 records=0（无报错） | Robin 暗网采集依赖 Tor 出口，生产容器未运行 Tor | 在服务器安装 tor 并以 INSTALL_OSINT=true 重建；否则应视为 config-gated 而非可采集 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| youtube | youtube | 搜索类端点全部零记录（tikhub_youtube_search / tikhub_youtube_video_search，后者当前未进 catalog 包），而直接调用 TikHub 上游却返回 HTTP 200 且负载很大 | TikHub 上游改版会改变嵌套层级；collector 按固定的 JSON 路径取值，一旦层级变化就静默返回空列表，不会报错。 | 排查 zero-record 时先取原始响应确认形状（而不是反复调参数）：从服务器用 TIKHUB_API_KEY 直接 curl 上游，再比对 _extract_items 的取值路径。新增归一化分支要同时加单测（tests/unit/test_tikhub_social_collector.py 的 YOUTUBE_SEARCH_RESPONSE）。 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| youtube | tikhub_youtube_search | quick-collect 返回 status=success，但 records_count=0（扫描归为 empty_records） | TikHub 的 web_v2/get_general_search 把搜索结果放在 data.contents，而 contents 是 dict（结构为 twoColumnSearchResultsRenderer→…→videoRenderer），不是 list；归一化器只认 list，于是静默取到 0 条。参数本身正确，换关键词也不会变。 | 已在 _extract_items 中对 youtube 增加深度查找兜底：_deep_find_dicts(inner, "videoRenderer")，再由 _normalize_youtube_video 抽取 videoId/title/ownerText/viewCountText。实测同一响应由 0 条变为 18 条。 | blocker | 2026-10-09 | reports/live-sweep/latest.json |

## network_proxy

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| bilibili | bilibili | bilibili_video_search / _user_videos / _video_comments 报 http_connection_failed | 生产服务器 IP 直连该站点超时（http_connection_failed） | 改用 tikhub_* 对应端点，或在服务器配置可用的 HTTP_PROXY/HTTPS_PROXY 后重试 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| kuaishou | kuaishou | kuaishou_video_search / _user_videos 报 http_connection_failed | 生产服务器 IP 直连该站点超时（http_connection_failed） | 改用 tikhub_* 对应端点，或在服务器配置可用的 HTTP_PROXY/HTTPS_PROXY 后重试 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| weibo | weibo | weibo_keyword_search / _user_posts / _trending_topics 报 http_connection_failed | 生产服务器 IP 直连该站点超时（http_connection_failed） | 改用 tikhub_* 对应端点，或在服务器配置可用的 HTTP_PROXY/HTTPS_PROXY 后重试 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| zhihu | zhihu | zhihu_question_answers / _keyword_search / _hot_list 报 http_connection_failed | 生产服务器 IP 直连该站点超时（http_connection_failed） | 改用 tikhub_* 对应端点，或在服务器配置可用的 HTTP_PROXY/HTTPS_PROXY 后重试 | warning | 2026-10-09 | reports/live-sweep/latest.json |

## params_invalid

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| web | web | autoscraper_enhanced_web / bestblogs_articles / blackbird_email_osint / blackbird_username_osint 曾一律返回 400 “Collector ... is not available” | 这四个 collector 已注册且有校验函数，但漏在播种清单 COLLECTOR_CATALOG 里，DB 中无 collector 行 | 已在本轮修复：向 COLLECTOR_CATALOG 补齐定义；重建 api 容器后生效。之后它们会返回真实的 config/param 错误 | blocker | 2026-10-09 | reports/live-sweep/latest.json |

## timeout

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| web | web | aliens_eye_basic/_advanced/_correlate/_recurse/_batch 请求超时（>180s） | Aliens Eye 全平台扫描耗时长，超出默认采集超时 | 增大超时或限定 sites 范围；对交互式调用不适用 | warning | 2026-10-09 | reports/live-sweep/latest.json |

## upstream_4xx

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| alibaba | alibaba | apify_1688_product_search/_detail 报 403；apify_alibaba_product_search 报 403；apify_1688_advanced、apify_alibaba_product_detail 报 invalid-input | 跨境站点对无代理请求反爬；部分 actor 入参 schema 与演示参数不符 | 配置代理并为 actor 传入其真实入参（inputs/startUrls/productUrls 等，见 manifest）；先用最小样例验证 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| amazon | amazon | apify_amazon_bestsellers 报 403；apify_amazon_bsr_tracker、apify_amazon_competitor_research actor run FAILED | Amazon 反爬 + 部分 actor 需特定入参（categoryUrls/asins）与代理 | 配置代理并核对 actor 入参；apify_amazon_product_scraper 已验证可用，可作首选 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| devto | devto | devto_articles_search 报 http_forbidden (403) | Dev.to API/站点对生产出口 IP 返回 403 | 配置代理或改用其它技术博客端点（juejin/substack） | info | 2026-10-09 | reports/live-sweep/latest.json |
| pinterest | pinterest | apify_pinterest_scraper / apify_pinterest_media_profile_scraper 报 http_forbidden (403) | Pinterest 反爬对生产出口 IP 返回 403 | 配置 Apify 住宅代理（actor 代理参数）或使用代理出口后重试 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| shopify | shopify | apify_shopify_products_monitor 报 404；apify_shopify_full_catalog 报 403 | 演示域名（allbirds.com）路径不匹配或对无代理请求 403 | 改用真实存在的 /products.json 目标域名与代理后重试 | info | 2026-10-09 | reports/live-sweep/latest.json |
| telegram | telegram | apify_telegram_scraper 报 http_forbidden (403) | Telegram 频道采集被上游拒绝 | 确认目标频道公开且配置代理；否则视为不可用 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| walmart | walmart | apify_walmart_product_scraper 返回 0 条；apify_walmart_reviews_scraper 报 403 | Walmart 对无代理请求返回空/403 | 配置代理并确认商品 ID 有效 | info | 2026-10-09 | reports/live-sweep/latest.json |

