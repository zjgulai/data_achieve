---
name: dih-platform-pitfalls
description: Data Intelligence Hub 全平台采集坑点与限制汇总，由平台工具包生成器自动生成，按失败分类分组。当排查采集失败或评估能力边界时使用。
---

# 平台采集坑点库

> 自动生成，请勿手工编辑。catalog_digest：`9234cf4b15090fbe4ed246b1f17403b7ee66e889b1fbc807d11166170e523cf8`
> 坑点总数：87 · 覆盖平台：31

## actor_failed

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| amazon | amazon | apify_amazon_bsr_tracker、apify_amazon_competitor_research 的 Apify run 状态为 FAILED | 入参/代理被 Amazon 拒绝，失败发生在 Actor 内部（run 已创建），与 403 类不同——需要读 run log 才能定位 | 用 GET /v2/actor-runs/<runId>/log 看 Actor 自身日志；apify_amazon_product_scraper 与 apify_amazon_reviews_scraper 已验证可用，可作首选替代 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| target | apify_target_products_scraper | Apify run 状态 FAILED | 入参已按 schema 修正（searchQueries/maxProductsPerSearch），run 能创建，但 Actor 自身以 FAILED 结束 | Actor 侧问题，改入参无效；需要读 run log 或换 Actor | blocker | 2026-10-09 | reports/live-sweep/latest.json |

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
| web | autoscraper_enhanced_web | AutoScraper build failed: No connection adapters were found for '<html ...>' | collector 把网页 HTML 当第一个**位置参数**传给 AutoScraper.build()/get_result()，而该位置参数是 url，库于是对 HTML 字符串发起 requests.get。另外 get_result() 返回 (similar, exact) 二元组，len() 恒为 0 | 已修：改成 scraper.build(wanted_list=..., html=...)，并按 mode 调用 get_result_exact() / get_result_similar()。演示参数同步为 example.com + ['Example Domain']（实测 exact 模式抽到 1 条） | blocker | 2026-10-09 | reports/live-sweep/latest.json |

## empty_records

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| bilibili | tikhub_bilibili_user_videos | 运行成功但恒返回 0 条 | fetch_user_videos 的条目在 data.data.item（**单数** item），提取器的键清单里只有 item_list/items | 已修：提取器先把 inner / inner.data / inner.results 都收进候选作用域，并补上 item 键。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| bilibili | tikhub_bilibili_video_search | 运行成功但恒返回 0 条 | 开量搜索的结果同样嵌在 data.data 下 | 已修：同上的作用域展开。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_brand_hot_search | 运行成功但恒返回 0 条 | fetch_brand_hot_search_list_detail 的榜单在 data.brand_list | 已修：补 brand_list 键。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_comments | 运行成功但恒返回 0 条 | 演示 aweme_id 是占位 123456；上游对不存在的视频不返回评论 | 需要真实视频 ID（可从 fetch_video_search_result 的结果里取） | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_comments | 运行成功但恒返回 0 条 | 两处：(1) fetch_video_comments 的评论在 data.comments，键清单里没有；(2) 演示 aweme_id 是占位 123456 | 已修：补 comments 键；aweme_id 从 fetch_video_search_v1 的结果回收。实测 0 -> 19 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_hot_search | 运行成功但恒返回 0 条 | fetch_hot_search_list 的热榜在 data.data.word_list / trending_list，多套了一层 data | 已修：作用域展开 + 补 word_list / trending_list 键。实测 0 -> 5 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_user_posts | 运行成功但恒返回 0 条 | 演示 sec_user_id 是占位 MS4wLjABAAAA（长度不足） | 需要真实 sec_user_id | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| douyin | tikhub_douyin_user_posts | 运行成功但恒返回 0 条 | 演示 sec_user_id 是占位 MS4wLjABAAAA，上游查不到该用户 | 已修：sec_user_id 从 fetch_video_search_v1 的 author.sec_uid 回收。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| ebay | apify_ebay_sold_listings_scraper | 运行成功但 0 条记录 | caffein.dev/ebay-sold-listings 的输入是搜索链接（Store 未提供示例入参，exampleRunInput 为 {"helloWorld":123}），演示参数 searchQuery 未必被识别 | 按“先看原始响应”的方法核对数据集；必要时改传 startUrls 形式的已售列表 URL | warning | 2026-10-09 | reports/live-sweep/latest.json |
| ebay | apify_ebay_sold_listings_scraper | 运行成功但数据集 0 条 | 演示参数用了 searchQuery/maxItems，Actor 的键是 keywords/count | 已修：keywords=["laptop"] + count=3，实测 3 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| facebook | facebook | 曾有一个 apify_facebook_group_scraper 端点：运行成功但恒返回 0 条 | whoareyouanas/facebook-group-scraper 的入参已按 schema 补齐（startUrls 必填），但用演示群组和公开群组 URL 都返回空数据集——Actor 侧能力问题 | 该端点已于 2026-10-09 从目录下线。要采 Facebook 群组内容请用 apify_facebook_posts_scraper（已验证返回记录）；判定同类问题的方法：同一 Actor 用自己文档里的公开样例 URL 仍返回空，就不要再调参数 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| glassdoor | apify_glassdoor_scraper | 运行成功但数据集 0 条 | 演示参数用了 keyword，而 memo23/glassdoor-scraper-ppr 靠 command(reviews/interviews/…) + startUrls（Glassdoor 公司页 URL）取数 | 已修：command=reviews + startUrls 用 Actor 自己的 prefill URL + maxItems=3 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| google_ads | apify_google_ads_scraper | 运行成功但数据集 0 条 | 演示参数用了 keywords/maxItems，Actor 要 startUrls；且原来的 advertiser ID 是个不存在的占位值 | 已修：startUrls 换成 Actor prefill 里的真实 advertiser URL + maxItems=3，实测 3 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| google_maps | apify_google_maps_reviews_scraper | 运行成功但数据集 0 条 | 演示 startUrls 用的是 maps.google.com/maps?cid=… 这种短链，Actor 要求含 /maps/search、/maps/place 或 /maps/review 的完整 URL | 已修：换成 Actor prefill 里的 /maps/place/… 完整链接，实测返回记录 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| google_news | apify_google_news_media_search | 曾报运行成功但 0 条 | DB 里是 10:54 扫描的旧证据；用 keywords/maxArticles 直连 Actor 实测能返回 1 条 | 重跑即恢复，属证据过期而非代码问题 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| kuaishou | tikhub_kuaishou_user_posts | 运行成功但恒返回 0 条 | 两处：(1) fetch_user_post_v2 的作品列表键是 feedback feeds，键清单里没有；(2) 演示 user_id 是占位 123456 | 已修：补 feeds 键；user_id 从 search_comprehensive 回收。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| lemon8 | tikhub_lemon8_trending | 运行成功但恒返回 0 条 | fetch_discover_tab 的 data.data 是空列表（该 tab 需要额外参数或上游无内容） | 提取分支已覆盖该形状；数据为空属上游侧 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| lemon8 | tikhub_lemon8_user_posts | 运行成功但恒返回 0 条 | fetch_user_profile 的 data.data 是**单个用户对象**（不是列表），且演示 user_id 是占位 12345 | 已修：新增 lemon8 提取分支（区分 list 与单对象）；user_id 从 fetch_search 回收。实测 0 -> 1 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| linkedin | linkedin | tikhub_linkedin_* 多个端点返回 records=0（无报错），apify_linkedin_jobs/company_search 亦为空 | LinkedIn 上游对无有效会话的请求返回空结果集；演示参数不足以触发真实数据 | 视为“需真实会话/参数”的高不稳定端点；不要据此判定能力可用，接入前用小样本人工验证 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| linkedin | apify_linkedin_company_search_scraper | 运行成功但数据集 0 条 | 演示参数用了 searchQuery/maxItems，而 khadinakbar/linkedin-company-search-scraper 的键是 keywords/maxResults；且 keywords 必须是**字符串**（传数组会被 400 must be string 拒绝） | 已修：keywords="software company" + maxResults=3，实测 3 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| linkedin | apify_linkedin_jobs_scraper | 运行成功但数据集 0 条 | 演示参数用了 title/location/maxJobs，而 freshdata/linkedin-job-scraper 的键是 keywords/geo_code/date_posted 等 | 已修：keywords="Python Developer"，实测 1 条（结果是响应信封，字段较浅） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| linkedin | tikhub_linkedin_company_profile | 运行成功但恒返回 0 条 | get_company_profile 的 data 直接就是单个公司对象（id/name/followers/about/description/url），不是列表；没有 linkedin 分支时提取返回空 | 已修：_extract_items 增加 linkedin 分支（有 name/id 时返回 [data]） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | reddit | 搜索结果零记录；帖子字段名与通用归一化器预期不一致 | Reddit 走的是 GraphQL 风格响应：标题字段是 postTitle（不是 title）、正文在 content.markdown、作者在 authorInfo.name、时间在 createdAt（形如 2026-10-03T19:08:43.382000+0000）。_normalize_generic 认不出这些字段，即便取到条目也只会得到空 text。 | reddit 已单独走 _normalize_reddit_post；新增 reddit 端点时先确认字段名，不要直接复用 _normalize_generic。 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | reddit | apify_reddit_ads_scraper 运行成功但恒返回 0 条 | Actor 的 query 是必填键，已补齐；但 lexis-solutions/reddit-ads-scraper 的 schema 自己写明“没有 ads.reddit.com 会话 cookie 时最多返回约 30 条”，实测无 cookie 时直接返回空数据集。（该 endpoint_type 只在 quick-collect 表里、不在 catalog 里，因此坑点只能挂在平台级。） | 按 Actor 入参 cookies 传入登录态 cookie（需含 token_v2）后才可能出数据；在此之前视为不可用 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | tikhub_reddit_post_comments | 运行成功但恒返回 0 条 | fetch_post_comments 在 data.postInfoById（单条帖子 + commentForest），提取器只找 search/posts/SearchPost/CellGroup | 已修：新增 postInfoById 分支。实测 0 -> 1 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | tikhub_reddit_search | quick-collect 返回 status=success，但 records_count=0（扫描归为 empty_records） | TikHub 的 app/fetch_dynamic_search 把结果放在 data.search，而 search 是 dict（search.dynamic.components.main.edges[].node.children[]），帖子挂在 __typename=SearchPost 的 node.post；归一化器只认 data.search 为 list，于是取到 0 条。 | 已在 _extract_items 中对 reddit 增加 _deep_find_typename(inner, "SearchPost") 深度查找，再由 _normalize_reddit_post 抽取 postTitle/url/score/authorInfo.name/subreddit.name/createdAt。实测同一响应由 0 条变为 7 条。 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | tikhub_reddit_subreddit_posts | quick-collect 报 422：subreddit_name 长度不足；修好参数后又恒返回 0 条 | 两个独立问题：(1) 参数白名单漏了 subreddit，_build_params 传出空串；(2) 上游把响应换成了 UI 结构 data.subredditV3.elements.edges[].node（__typename=CellGroup），帖子内容散在 cells[] 里，标题在 TitleCell.title、作者/时间在 MetadataCell，按 postTitle 取永远为空 | 已修：白名单补齐 subreddit；_extract_items 增加 CellGroup 深度查找，_normalize_reddit_subreddit_post 按 cells 抽字段（groupId t3_xxx → https://www.reddit.com/comments/xxx）。同一响应由 0 条变 6 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| reddit | tikhub_reddit_trending | 运行成功但恒返回 0 条 | fetch_popular_feed 放在 data.popularfeed.postsInfoByIds（list），条目只有 id（如 1o8v3kd）与 postTitle，没有 permalink / url | 已修：_extract_items 增加 popularfeed 分支；_normalize_reddit_post 增加由 id 拼 https://www.reddit.com/comments/<id> 的兜底。同一响应由 0 条变 8 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| temu | apify_temu_products_scraper | 运行成功但数据集 0 条；传 maxResults=3 则 400 | 演示参数用了 keywords/maxItems（都不存在），而 amit123/temu-products-scraper 的键是 searchQueries/maxResults，且 maxResults **下限为 20** | 已修：searchQueries=["women dress"] + maxResults=20（该值是 Actor 的下限，不是我们要这么多） | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| threads | tikhub_threads_post_comments | 运行成功但恒返回 0 条 | fetch_post_comments 在 data.edges[].node（含 thread_items），不是常见的 items/list | 已修：同上。实测 0 -> 19 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| threads | tikhub_threads_user_posts | 运行成功但恒返回 0 条 | fetch_user_posts 在 data.mediaData.edges[].node，正文在 thread_items[0].post.caption.text；且 user_id 必须是数值型 ID（用户名不行） | 已修：新增 threads 提取分支与 _normalize_threads_item；演示参数改用 fetch_user_info 拿到的数值 user_id。实测 0 -> 20 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_ads_detail | 运行成功但恒返回 0 条 | get_ads_detail（POST）的 data.data 是单个广告对象；且 body 的键是 ads_id 不是 ad_id，演示值曾是占位 123456 | 已修：提取器识别单对象形状；演示参数换成 top ads 回收的真实素材 ID。实测 0 -> 1 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_ads_keyword_suggest | 运行成功但恒返回 0 条 | get_query_suggestions 是 POST，body 需要 query/count，原先 _build_params 返回 {}；补上后上游对 query=python 仍返回空列表（上游侧无联想词） | 参数已正确传递；该端点暂视为 empty，换更常见的 seed 词可能出数据 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_hashtag_posts | 运行成功但恒返回 0 条 | 演示 ch_id 是占位 7654567，不是真实话题 ID | 已修：从视频搜索结果的 challenge cid 回收真实 ID。实测 0 -> 20 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_live_room_detail | 运行成功但恒返回 0 条 | fetch_live_room_info 的 data.data 是单个直播间对象（261 个字段），主播在 owner；演示 room_id 曾是 123456 | 已修：单对象形状识别 + _normalize_tiktok_live 兼容 owner/title。实测 0 -> 1 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_live_search | 运行成功但恒返回 0 条 | fetch_live_search_result 放在 data.data（list），且有两种条目形状：{"type":1,"lives":{...}} 与 {"type":2,"anchor":{"owner_user_info":...}}；tiktok 分支认不出 | 已修：_extract_items 增加 tiktok 分支（含 data.data / products / materials），_normalize_tiktok_live 兼容两种形状。同一响应由 0 条变 20 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_shop_products | 运行成功但恒返回 0 条 | fetch_search_products_list 放在 data.data.products（list），字段是 product_id/title/seo_url/product_price_info | 已修：_normalize_tiktok_product 抽 product_id/title/seo_url/price/sold_info。同一响应由 0 条变 15 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_top_ads | 运行成功但恒返回 0 条 | get_top_ads_spotlight 放在 data.data.materials（list），字段是 id/highlight/ctr/cost/like/video_info | 已修：_normalize_tiktok_ad 抽 material_id/highlight/ctr/like/video_info。同一响应由 0 条变 5 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| walmart | walmart | apify_walmart_scraper 运行成功但恒返回 0 条 | Actor 换成了 web_wanderer/walmart-product-scraper（旧的 apify/walmart-scraper 已下架），product_ids 用的是该 Actor 自己的 inputSchema.prefill 里的 walmart.ca 商品 URL，并配 reg=CA；仍返回空数据集。（该 endpoint_type 只在 quick-collect 表里、不在 catalog 里，因此坑点只能挂在平台级。） | 视为上游侧不可用；需要 Walmart 数据时优先用 apify_walmart_product_scraper 并确认代理链路 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| walmart | apify_walmart_product_scraper | 运行成功（run SUCCEEDED）但数据集 0 条 | e-commerce/walmart-product-detail-scraper 对演示商品 ID 没有返回结果；需按“先看原始响应”的方法确认是入参不匹配还是上游返回空页 | 改用真实商品 URL（而不是纯 ID）并确认 datasets 输出；同类 0 条问题不要默认是参数不足 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| walmart | apify_walmart_product_scraper | 运行成功但数据集 0 条 | 演示参数用了 productIds，而 e-commerce/walmart-product-detail-scraper 的键是 startUrls + maxProductsPerStartUrl | 已修：startUrls=[{url: https://walmart.com/search?q=tshirt}] + maxProductsPerStartUrl=3，实测 3 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | robin_darkweb_search / _username / _email 返回 records=0（无报错） | Robin 暗网采集依赖 Tor 出口，生产容器未运行 Tor | 在服务器安装 tor 并以 INSTALL_OSINT=true 重建；否则应视为 config-gated 而非可采集 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| web | firecrawl_batch_scrape | 运行成功但恒返回 0 条（此前一度报 401，是旧证据） | /v1/batch/scrape 是异步接口，首次响应只有 {"success": true, "id": "..."}，没有 data；collector 直接读 resp["data"]，于是永远 0 条 | 已修：无 data 时用 /v1/batch/scrape/{id} 轮询到 completed 再取 data（_poll_job 增加 base_path 参数，crawl 仍用 /v1/crawl） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| wechat | tikhub_wechat_channels_video | 运行成功但 0 条（此前为 422：body.username 至少 10 字符） | 该端点是 POST-only 且 body 必填 username，取值必须是视频号 finder id（形如 v2_<hex>@finder）；演示值无法凭空构造 | 调用方需传真实 finder username；管道已修好（POST + 参数透传），仅缺真实业务 ID | warning | 2026-10-09 | reports/live-sweep/latest.json |
| wechat | tikhub_wechat_channels_video | 运行成功但恒返回 0 条 | 演示 username 是自造的 v2_…@finder，上游只回 message/debug_id，没有作品列表 | 需要真实的视频号 finder username | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| wechat | tikhub_wechat_search | 运行成功但恒返回 0 条 | fetch_search 的结果在 data.results.data，而 results 是 dict 不是 list | 已修：作用域展开把 inner.results 也纳入。实测 0 -> 15 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| weibo | tikhub_weibo_user_posts | 运行成功但恒返回 0 条 | fetch_user_posts 的微博列表在 data.data.list，多套了一层 data | 已修：作用域展开。实测 0 -> 20 条 | blocker | 2026-10-10 | reports/live-sweep/latest.json |
| x | tikhub_x_trending | 运行成功但恒返回 0 条 | fetch_trending 放在 data.trends（list of {name, description, context}）；x 分支只找 timeline，认不出 trends | 已修：_extract_items 增加 trends 分支，_normalize_x_trend 抽 name/description/context。同一响应由 0 条变 50 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| x | tikhub_x_user_followers | 运行成功但恒返回 0 条 | fetch_user_followers 在 data.followers（list of 50），x 提取分支只找 timeline/trends；演示 username 曾是不存在的 python | 已修：新增 followers 分支，username 换成搜索结果里的真实账号。实测 0 -> 50 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| youtube | youtube | 搜索类端点全部零记录（tikhub_youtube_search / tikhub_youtube_video_search，后者当前未进 catalog 包），而直接调用 TikHub 上游却返回 HTTP 200 且负载很大 | TikHub 上游改版会改变嵌套层级；collector 按固定的 JSON 路径取值，一旦层级变化就静默返回空列表，不会报错。 | 排查 zero-record 时先取原始响应确认形状（而不是反复调参数）：从服务器用 TIKHUB_API_KEY 直接 curl 上游，再比对 _extract_items 的取值路径。新增归一化分支要同时加单测（tests/unit/test_tikhub_social_collector.py 的 YOUTUBE_SEARCH_RESPONSE）。 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| youtube | tikhub_youtube_search | quick-collect 返回 status=success，但 records_count=0（扫描归为 empty_records） | TikHub 的 web_v2/get_general_search 把搜索结果放在 data.contents，而 contents 是 dict（结构为 twoColumnSearchResultsRenderer→…→videoRenderer），不是 list；归一化器只认 list，于是静默取到 0 条。参数本身正确，换关键词也不会变。 | 已在 _extract_items 中对 youtube 增加深度查找兜底：_deep_find_dicts(inner, "videoRenderer")，再由 _normalize_youtube_video 抽取 videoId/title/ownerText/viewCountText。实测同一响应由 0 条变为 18 条。 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| youtube | tikhub_youtube_video_comments | 运行成功但恒返回 0 条 | 上游把评论放在 data.comments（list），字段是 snake_case（comment_id/content/published_time/like_count）；youtube 分支只找 videos/contents/videoRenderer，认不出 comments | 已修：_extract_items 增加 comments 分支，按 comment_id 存在与否分流到 _normalize_youtube_comment。同一响应由 0 条变 20 条 | blocker | 2026-10-09 | reports/live-sweep/latest.json |

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
| alibaba | apify_1688_advanced | 400 invalid-input：Field input.inputs is required | 调用方按想象传了 {"type":"keyword","queries":[...]}，而 dltik/1688-scraper 的 schema 只有 mode(detail/search/image) + inputs(数组) + maxResults，且 additionalProperties:false，所以既缺 inputs 又多出非法键 | 传 {"mode":"search","inputs":["<关键词或 offer id/URL>"],"maxResults":N}；_APIFY_ENDPOINT_DEFAULTS 已按真实 schema 修正 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| alibaba | apify_alibaba_product_detail | 400 invalid-input：Items in input.productUrls at positions ... | 演示参数里的商品 URL 是占位串（.../product-detail/10000000000000.html），xtracto/alibaba-product-scraper 会做 URL 校验，占位 ID 不是合法商品 | 必须传真实商品详情页 URL（形如 https://www.alibaba.com/product-detail/<slug>_<id>.html） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| ebay | apify_ebay_product_scraper | 400 invalid-input：Field input.startUrls is required | dtrungtin/ebay-items-scraper 的必填键是 startUrls（列表页 URL），且 proxyConfig 也标为必填；调用方传的是 listingUrls，键名不存在于 schema，additionalProperties:false 下直接整单拒绝 | 传 startUrls（如 https://www.ebay.com/sch/i.html?_nkw=<关键词>）+ maxItems + proxyConfig={useApifyProxy:true}；缺省值已按真实 schema 补齐 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| shein | apify_shein_product_scraper | 400 invalid-input：Property input.searchQuery is not allowed | Actor 的 inputSchema 是 additionalProperties:false，只接受 startUrl（必填）+ results_wanted + proxyConfiguration；调用方（扫描脚本的演示参数与 _APIFY_ENDPOINT_DEFAULTS 的缺省值曾不一致）多传了一个 searchQuery，整单被拒 | 只传 Actor schema 里存在的键。缺省值已统一为 {startUrl, results_wanted}；核对 schema 用 GET https://api.apify.com/v2/acts/shahidirfan~shein-product-scraper/builds/default 的 inputSchema 字段（免鉴权） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| tiktok | tikhub_tiktok_ads_search | http_status_error: upstream returned 422 / Field required: material_id | _build_params 对该端点返回 {}，而官方 spec 的 POST body 必填 material_id（industry / country_code 有默认值） | 已修：透传 material_id / industry / country_code；演示值取自 apify/tikhub 的 top ads 结果。注意 material_id 属业务 ID，调用方要传自己的素材 ID | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | autoscraper_enhanced_web / bestblogs_articles / blackbird_email_osint / blackbird_username_osint 曾一律返回 400 “Collector ... is not available” | 这四个 collector 已注册且有校验函数，但漏在播种清单 COLLECTOR_CATALOG 里，DB 中无 collector 行 | 已在本轮修复：向 COLLECTOR_CATALOG 补齐定义；重建 api 容器后生效。之后它们会返回真实的 config/param 错误 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | anysearch_tag_search | AnySearch HTTP 400: Invalid tag: python（改成合法 tag 后又报 Missing required params for tag 'code.doc': library） | tag 必须取自 AnySearch 的固定词表（如 code.doc / news），且带 tag 时还要在 **params 里**（不是顶层）附带该 tag 的必填参数 | 已修：演示参数改为 {"query": "requests", "tag": "code.doc", "params": {"library": "python"}}，实测返回结果 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| web | apify_rag_web_browser | 调用方传了 query 仍报 400 invalid-input：Field input.query is required | quick-collect 的 Apify 分支把一批“元键”（query/url/keyword/domain/asin/location/username/profile/handle…）从 actor_input 里剔除，而 apify/rag-web-browser 的必填键恰好就叫 query，于是入参被静默丢掉 | 已修：元键只保留 maxItems/max_items/max_total_charge_usd/run_timeout_seconds 四个采集开关，其余一律透传给 Actor（_APIFY_META_KEYS） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| wechat | tikhub_wechat_search | http_status_error: upstream returned 405 / {"detail":"Method Not Allowed"} | 官方 spec 里 /api/v1/wechat_search/v2/fetch_search 只注册了 POST，collector 却走 GET | 已修：加入 _TIKHUB_POST_ENDPOINTS；collector.test() 一并改成按端点选方法 | blocker | 2026-10-09 | reports/live-sweep/latest.json |

## timeout

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| google_trends | apify_google_trends_scraper | 客户端读超时（The read operation timed out），不是上游报错 | apify/google-trends-scraper 的 run 等待时间超过 quick-collect 的同步等待窗口；采集器内部 APIFY_TIMEOUT=30s、APIFY_RUN_WAIT_TIMEOUT=600s，而 quick-collect 路由是同步返回的 | 走异步任务（POST /api/tasks/{id}/run + 轮询 /api/tasks/runs）而不是 quick-collect；或调小 searchTerms 数量与 geo 范围 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| web | web | aliens_eye_basic/_advanced/_correlate/_recurse/_batch 请求超时（>180s） | Aliens Eye 全平台扫描耗时长，超出默认采集超时 | 增大超时或限定 sites 范围；对交互式调用不适用 | warning | 2026-10-09 | reports/live-sweep/latest.json |

## upstream_4xx

| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |
|---|---|---|---|---|---|---|---|
| alibaba | alibaba | 跨境端点（1688 / Alibaba）整组报 403 或 invalid-input，看起来像“反爬” | 两种完全不同的原因被混在一起：一是上游站点反爬，二是 Apify Actor 本身拒绝本账号发起运行（403 在 POST /acts/<id>/runs 阶段立即返回，1 秒内失败，根本没产生 run） | 先看失败耗时：<2s 且 http_forbidden 说明是 Actor 侧的 403，换 Actor 或申请租用；耗时长才是站点反爬。Actor 的真实入参用 https://api.apify.com/v2/acts/<user~name>/builds/default 的 inputSchema（免鉴权）核对 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| alibaba | apify_1688_product_detail | 400 或立即 403，且 Actor 元数据 isDeprecated=true、30 天活跃用户 0 | ecomscrape/1688-product-details-page-scraper 已被作者标记废弃（最后运行 2026-08-25） | 已改指 dltik/1688-scraper（mode=detail，inputs 传 offer id 或详情页 URL），与 apify_1688_advanced 共用同一 Actor | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| alibaba | apify_1688_product_search | 403，1 秒内失败，无 Apify run 产生 | ecomscrape/1688-product-search-scraper 仍存在但拒绝本账号发起运行（pricingInfos 为 FLAT_PRICE_PER_MONTH + FREE，疑似需先租用）；具体原因未确认，需要读 403 响应体 | 暂视为不可用；替换候选 dltik/1688-scraper 的 mode=search 可覆盖同一场景，待实测后切换 | warning | 2026-10-09 | reports/live-sweep/latest.json |
| alibaba | apify_alibaba_product_search | 403（曾被归类为 rate limit） | scraperx/alibaba-scraper 已从 Apify Store 下架：GET /v2/acts/scraperx~alibaba-scraper 返回 record-not-found，发起运行一律 403 | 已改指 zen-studio/alibaba-scraper（resultType/keywords/maxResults/shipToCountry） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| amazon | apify_amazon_bestsellers | 403，1 秒内失败；Actor 元数据查询返回 record-not-found | simpleapi/amazon-bestsellers-scraper 已从 Apify Store 下架，任何第三方发起运行都被 403 挡回（403 而不是 404，容易被误判为反爬） | 已改指 junglee/amazon-bestsellers（categoryUrls 必填、maxItemsPerStartUrl 限流、depthOfCrawl 控制子类目） | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| devto | devto | devto_articles_search 报 http_forbidden (403) | Dev.to API/站点对生产出口 IP 返回 403 | 配置代理或改用其它技术博客端点（juejin/substack） | info | 2026-10-09 | reports/live-sweep/latest.json |
| devto | devto_articles_search | http_forbidden: upstream returned 403（0.2s 内立即返回） | dev.to 走 Cloudflare：对 /api/articles 带**浏览器 User-Agent** 的请求返回 403，同一请求不带该 UA（或只带 Accept）返回 200。collector 给所有技术博客端点统一套了 Chrome UA | 已修：DevToArticlesCollector 改用中性 UA（data-intelligence-hub-collector/1.0）。判据：同一个 URL 换个 UA 就 200，说明是 UA 触发的拦截，与参数无关 | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| shopify | apify_shopify_products_monitor | 404（http_not_found），Actor 元数据查询同样 404 | autofacts/shopify-scraper 已下架；原演示参数 {url: ...} 也不是该 Actor 的入参名 | 已改指 trovevault/shopify-products-scraper，入参是 domains（域名数组）+ maxProducts | blocker | 2026-10-09 | reports/live-sweep/latest.json |
| walmart | apify_walmart_reviews_scraper | 403，1 秒内失败 | e-commerce/walmart-reviews-scraper 拒绝本账号发起运行（run 未创建），与代理或商品 ID 无关 | 改用 web_wanderer/walmart-reviews-scraper；或先用 apify_walmart_product_scraper 验证代理链路（它返回 success 但 0 条，属于另一类问题） | warning | 2026-10-09 | reports/live-sweep/latest.json |

