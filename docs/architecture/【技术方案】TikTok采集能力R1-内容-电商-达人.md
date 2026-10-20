---
name: tiktok-r1-collection-plan
description: TikTok 采集能力 R1 方案，覆盖内容与趋势、Shop 商品与评论、达人带货，给出 21 张表、31 个 TikHub 端点、Provider 主备链、13 个工具契约、验收门槛与 9 周排期。评审或实施 TikTok 采集模块时先读这份。
---

# TikTok 采集能力 R1 技术方案

> 状态：Phase 0 已实施。Phase 1 待评审。
> 日期：2026-10-19。
> 范围：内容与趋势、Shop 商品与评论、达人带货。
> 数据模型：21 张全域表。一次建 schema，分波启用。
> Provider：Apify 主力，TikHub 补身份、详情与分析。
> TikHub：先接 31 个公开端点。
> 配套数据模型：[【数据模型】TikTok-R1-21张表](./【数据模型】TikTok-R1-21张表.md)。
> 探测报告：[TikHub 31 个端点](./【探测报告】TikHub-TikTok-31端点-2026-10-19.md)。

## 1. 方案摘要

R1 建设一个可复用的 TikTok 采集与元数据底座。底座服务三个业务模块：

1. 内容与趋势。
2. Shop 商品与评论。
3. 达人带货。

底座分三层：

1. Provider 适配层。统一 Apify 与 TikHub 的输入、输出、错误与成本。
2. 标准元数据层。21 张表。主数据可更新。指标快照只追加。
3. Agent 与工作台层。13 个工具。1 个 TikTok 模块页。

R1 不做广告、直播、独立音乐页面、品牌舆情。广告与直播表先建空表，不采集，不暴露。

## 2. 目标与非目标

### 2.1 目标

1. 三个模块各有稳定主备链。
2. 每个模块过统一验收门槛。
3. 每条记录可追溯到 provider、endpoint、run 与原始响应。
4. Agent 可调用工具。工作台可查看结果与运行状态。
5. 成本可控。单日成本不超过 10 美元。

### 2.2 非目标

1. 不做 AI 分析。采集层只输出原文、语言、来源与指标。
2. 不做全量 TikTok 数据镜像。
3. 不做多租户 UI。表结构保留 `workspace_id` 与 `project_id`。
4. 不做广告与直播采集。
5. 不做媒体长期转存。只存 URL、过期时间与按需代理。
6. 不做 `creator/*` 登录态端点。

## 3. 决策记录

| 编号 | 决策 | 说明 |
|---|---|---|
| D1 | R1 覆盖模块 1、2、3 | 内容与趋势、Shop 商品与评论、达人带货。执行顺序：内容 → Shop → 达人。 |
| D2 | 一次建 21 张表 | schema 一次成型。表按波次启用。广告表先建空表。 |
| D3 | Apify 主力，TikHub 补充 | Apify 负责批量公开数据。TikHub 负责身份、详情、评论回复、商品详情与评论、分析。 |
| D4 | TikHub 先接 31 个公开端点 | 不接 `creator/*` 登录态端点。 |

## 4. 现状与问题

### 4.1 飞书文档

飞书文档《数据采集agent-TK平台》是爆款洞察 MVP。它覆盖榜单、视频、评论 3 个环节。

可保留的原则：

1. 纯数据管道。
2. 主数据加指标快照。
3. 缺失字段显式标记。
4. 双源降级。
5. 字段标准化。
6. 重试与幂等。

必须修正的问题：

| 编号 | 问题 | 证据 | 影响 |
|---|---|---|---|
| P1 | 覆盖窄 | 只有 L1、L3、L5。Shop、广告、直播、音乐、字幕缺失。 | 无法支撑多业务场景。 |
| P2 | 评论字段不存在 | `clockworks/tiktok-comments-scraper` 不返回 `repliesToId`、`pinnedByAuthor`、`likedByAuthor`。 | 回复树、置顶、作者互动无法落库。 |
| P3 | 作者字段错位 | `authorMeta.region` 只在 profile-scraper 出现。`createTime` 需额外参数。 | 作者地区与注册时间可能为空。 |
| P4 | 视频字段不稳定 | `downloadAddr` 是签名 CDN。标准 scraper 不保证 `region`、`locationCreated`。 | 视频直链会过期。地区归因缺失。 |
| P5 | 缺治理字段与关系表 | 6 张表无 `run_id`、`raw_ref`、`schema_version`、`quality_flags`。hashtags 存 JSON。 | 无法回放、追溯与多标签归因。 |

飞书文档写的 3 个 TikHub 端点在上游存在，但仓库没有接入。它们是：

1. `web/fetch_post_detail`。
2. `web/fetch_post_comment`。
3. `ads/get_trends_hashtag_list`。

不能把“上游存在”写成“仓库已验证”。

### 4.2 Apify Store

Apify Store 有 96 个 TikTok Actor。本项目已审阅 145 个候选。可归为 13 个能力模块。

高价值且飞书文档缺失的模块：

1. Shop 商品。
2. Shop 评论。
3. 达人带货。
4. 选题需求。
5. 广告创意。
6. 直播。
7. 音乐。
8. 字幕。
9. 关键词与账号搜索。

R1 取 8 个能力模块：

1. 趋势榜。
2. 话题视频。
3. 关键词搜索。
4. 视频详情。
5. 评论。
6. 账号与达人。
7. Shop 商品与评论。
8. 达人带货与选题需求。

音乐与字幕作为内容子能力。广告与直播后置。

### 4.3 TikHub

TikHub 上游有 166 个 TikTok 端点。仓库只接 16 个。

R1 先接 31 个公开端点。重点补：

1. 身份解析。
2. 评论回复。
3. 商品详情与评论。
4. 直播商品（R2 使用）。
5. 假流量检测。
6. 评论关键词。
7. 搜索需求。

### 4.4 现有端点

生产 `providers/status` 显示 25 个 TikTok 端点：

| 状态 | 数量 | 端点 |
|---|---|---|
| verified | 18 | 有记录且无错误。 |
| empty | 5 | `ads_search`、`ads_keyword_suggest`、`creator_account_health`、`creator_insights`、`creator_insights_trend`。 |
| degraded | 2 | `creator_info`、`live_user`。 |

catalog 把 25 个端点全标 `verified`。这是状态失真。验收必须读 `providers/status`。

### 4.5 现有 tiktok_cdo

现有 `tiktok_cdo` 有 9 个 action。关键问题：

| 编号 | 问题 | 影响 |
|---|---|---|
| C1 | quick-collect 响应不含 records | `gather_data` 拿不到数据。结果卡恒为空。 |
| C2 | hashtag 传 `name` | 采集器只读 `ch_id` 或 `hashtag_id`。空结果。 |
| C3 | user_posts 与 followers 把 handle 填进 `sec_user_id` | 空结果或 400。 |
| C4 | ads_search 缺 `material_id` | 422。 |
| C5 | creator 传 `sec_user_id` | 采集器读 `creator_uid` 或 `keyword`。400 或空。 |
| C6 | `count` 不在白名单 | `intent.limit` 无效。默认取 20 条。 |
| C7 | 客户端 30 秒超时 | Apify 外层上限 300 秒。长任务必断。 |
| C8 | 固定 `_DEMO_WORKSPACE` | 没有 `project_id`。无法多项目复用。 |

R1 必须先修 C1 到 C8。

## 5. R1 能力矩阵

| 模块 | 主链 | 备链 | 关键字段 |
|---|---|---|---|
| 趋势榜 | `data_xplorer/tiktok-trends` | `clockworks/tiktok-trends-scraper`；TikHub `ads/get_trends_hashtag_list` | `rank`、`posts`、`video_views`、`trend_data`、`top_creators`、`industry`、`country`、`period` |
| 话题视频 | `clockworks/tiktok-hashtag-scraper` | `clockworks/tiktok-scraper`；TikHub `fetch_hashtag_video_list` | `video_id`、`caption`、`play_count`、`digg_count`、`comment_count`、`share_count`、`hashtags`、`music_id`、`is_ad`、`has_shop_product` |
| 关键词搜索 | `xmolodtsov/tiktok-search-scraper` | `clockworks/tiktok-scraper`；TikHub `fetch_general_search` | `title`、`views`、`likes`、`comments`、`shares`、`bookmarks`、`channel`、`uploaded_at` |
| 视频详情 | TikHub `web/fetch_post_detail` | `clockworks/tiktok-scraper` | `aweme_id`、`author`、`statistics`、`video`、`music`、`is_ad` |
| 评论 | TikHub `app/v3/fetch_video_comments` 与 `fetch_video_comment_replies` | `clockworks/tiktok-comments-scraper`；`xtdata` | `cid`、`parent_comment_id`、`text`、`digg_count`、`reply_count`、`is_pinned`、`creator_interacted` |
| 账号与达人 | `clockworks/tiktok-profile-scraper` | TikHub `fetch_user_profile`；`clockworks/tiktok-user-search-scraper` | `uid`、`sec_uid`、`unique_id`、`nickname`、`fans`、`heart`、`video`、`verified`、`region`、`tt_seller` |
| 选题需求 | `cunning_soil/tiktok-creator-search-insights` | TikHub `fetch_creator_search_insights_detail` | `search_volume_label`、`popularity_score`、`trend_growth_percent`、`is_content_gap`、`related_topics`、`outline_insights` |
| Shop 商品 | `pratikdani/tiktok-shop-scraper` | `pratikdani/tiktok-shop-search-scraper`；TikHub `fetch_search_products_list_v2` | `product_id`、`price`、`sale_30d_cnt`、`gmv_30d_amt`、`commission`、`stock`、`skus`、`rating`、`review_count`、`ifl_30d_cnt`、`video_30d_cnt`、`live_30d_cnt` |
| Shop 评论 | `vistics/tiktok-shop-product-reviews` | TikHub `fetch_product_reviews_v2`；`unseenuser` | `review_id`、`rating`、`text`、`verified_purchase`、`incentivized`、`sku_id`、`variant`、`country`、`images` |
| 达人带货 | `lemur/tiktok-shop-creators` | `cunning_soil` CSI | `gmv`、`gpm`、`video_gpm`、`live_gpm`、`units_sold`、`avg_commission`、`top_brands`、`top_demographics`、`promotion_performance_score` |
| 达人风控 | TikHub `analytics/detect_fake_views` | `creator_snapshot` 粉丝与播放序列 | `fake_view_score`、`sample_size`、`confidence` |
| 音乐 | `clockworks/tiktok-sound-scraper` | TikHub `fetch_music_detail`、`fetch_music_video_list` | `music_id`、`music_name`、`music_author`、`play_count`、`usage_count` |
| 字幕 | `clockworks/tiktok-transcript-extractor` | `scrape-creators/best-tiktok-transcripts-scraper` | `text`、`text_language`、`videoMeta.subtitleLinks`、`videoMeta.transcriptionLink` |

### 5.1 字段证据规则

1. 字段名必须来自 `input_schema`、README 示例或实测 sample。
2. 只来自 README 的字段标 `needs_live_verification=true`。
3. 输入字段不得当输出字段。
4. 上层展示字段必须能追溯到至少一个 provider。
5. 无 provider 可填的字段不建列。

### 5.2 已知字段修正

| 编号 | 错误写法 | 正确写法 |
|---|---|---|
| F1 | `productUrls` | `pratikdani/tiktok-shop-scraper` 的输入是 `url`。 |
| F2 | burbn 为主力 | burbn 处于 `UNDER_MAINTENANCE`。主力改 `clockworks/tiktok-sound-scraper`。 |
| F3 | easyapi 支持 handles | easyapi 只收 `keywords`、`categories`、`maxItems`。开播监测用 `unseenuser/tiktok-live-status-scraper`。 |
| F4 | profile-scraper 返回 `connectionType` | `connectionType` 与 `connectedTo` 属于 `tiktok-followers-scraper`。 |
| F5 | lemur 返回 `searchVolumeLabel` | `searchVolumeLabel` 与 `isContentGap` 属于 `cunning_soil/tiktok-creator-search-insights`。 |
| F6 | 搜索返回 `createTime` | 搜索返回 `uploadedAtFormatted`。`createTime` 只在作者主页附加字段。 |
| F7 | 字幕顶层有 `subtitleLinks` | 实际路径是 `videoMeta.subtitleLinks` 与 `videoMeta.transcriptionLink`。 |
| F8 | `data_xplorer` 字段是 snake_case | 实际是 Title Case，如 `Video Views`、`Trend Direction`。 |

## 6. Provider 主备链

### 6.1 主备规则

1. 每个模块必须有主链与备链。
2. 主链失败后切备链。
3. 403 不重试同一 Actor。直接切备链。
4. 400 参数错不重试。先修参数。
5. 空结果标 `empty`。不自动调参。
6. 超时保留 `provider_run_id`。可续查。
7. 每个 provider 记录成本、耗时、记录数、错误分类。

### 6.2 降级顺序

| 模块 | 顺序 |
|---|---|
| 趋势榜 | `data_xplorer` → `clockworks/tiktok-trends-scraper` → TikHub `ads/get_trends_hashtag_list` |
| 话题视频 | `clockworks/tiktok-hashtag-scraper` → `clockworks/tiktok-scraper` → TikHub `fetch_hashtag_video_list` |
| 关键词搜索 | `xmolodtsov` → `clockworks/tiktok-scraper` → TikHub `fetch_general_search` |
| 视频详情 | TikHub `fetch_post_detail` → `clockworks/tiktok-scraper` |
| 评论 | TikHub `fetch_video_comments` 与 `fetch_video_comment_replies` → `clockworks/tiktok-comments-scraper` → `xtdata` |
| 账号 | `clockworks/tiktok-profile-scraper` → TikHub `fetch_user_profile` |
| 达人搜索 | `clockworks/tiktok-user-search-scraper` → TikHub `fetch_search_user` |
| Shop 商品详情 | `pratikdani/tiktok-shop-scraper` → `clockworks/tiktok-shop-scraper` |
| Shop 商品搜索 | `pratikdani/tiktok-shop-search-scraper` → TikHub `fetch_search_products_list_v2` |
| Shop 评论 | `vistics` → TikHub `fetch_product_reviews_v2` |
| 达人带货 | `lemur` → `cunning_soil` CSI |
| 音乐 | `clockworks/tiktok-sound-scraper` → TikHub `fetch_music_detail` |

## 7. 31 个 TikHub 端点

### 7.1 身份（3）

1. `web/get_sec_user_id`。
2. `web/get_user_id`。
3. `app/v3/get_user_id_and_sec_user_id_by_username`。

### 7.2 视频（5）

1. `web/fetch_post_detail`。
2. `web/fetch_user_post`。
3. `web/fetch_general_search`。
4. `web/fetch_search_video`。
5. `app/v3/fetch_one_video`。

注意：`web/fetch_search_video` 实测 400。视频搜索用 `web/fetch_general_search`。

### 7.3 评论（4）

1. `web/fetch_post_comment`。
2. `web/fetch_post_comment_reply`。
3. `app/v3/fetch_video_comments`。
4. `app/v3/fetch_video_comment_replies`。

注意：`web/fetch_post_comment_reply` 实测 400。回复树用 `app/v3/fetch_video_comment_replies`。

### 7.4 话题（4）

1. `web/fetch_tag_detail`。
2. `web/fetch_tag_post`。
3. `web/fetch_trending_searchwords`。
4. `app/v3/fetch_hashtag_detail`。

注意：`web/fetch_tag_post` 只认 Web `challengeID`。`app/v3/fetch_hashtag_detail` 只认 App `ch_id`。两者不能混用。

### 7.5 达人（4）

1. `web/fetch_user_profile`。
2. `web/fetch_user_fans`。
3. `web/fetch_user_follow`。
4. `web/fetch_search_user`。

注意：`web/fetch_user_fans` 实测可用。`web/fetch_user_follow` 与 `web/fetch_search_user` 实测 400。关注列表用 App 端点或 Apify。用户搜索用 Apify。

### 7.6 音乐（3）

1. `app/v3/fetch_music_detail`。
2. `app/v3/fetch_music_video_list`。
3. `app/v3/fetch_music_chart_list`。

### 7.7 Shop（5）

1. `shop/web/fetch_product_detail_v3`。
2. `shop/web/fetch_product_reviews_v2`。
3. `shop/web/fetch_search_products_list_v2`。
4. `shop/web/fetch_hot_selling_products_list`。
5. `shop/web/fetch_search_word_suggestion_v2`。

注意：`fetch_product_detail_v3` 实测只回页面配置，不回商品字段。不要当详情源。
注意：`fetch_hot_selling_products_list` 不支持美国。支持地区：ID、JP、MX、MY、PH、SG、TH、VN。
注意：美国商品发现用 `fetch_search_products_list_v2`。

### 7.8 分析（2）

1. `analytics/detect_fake_views`。
2. `analytics/fetch_comment_keywords`。

### 7.9 趋势补充（1）

1. `ads/get_trends_hashtag_list`。

### 7.10 接入规则

1. 现有 16 个 TikHub 端点继续使用。本表是新增端点。
2. 每个端点先跑 10 条金标准用例。
3. 记录响应顶层键与字段类型。
4. 只接有稳定字段的端点。
5. 需要 cookie 的端点不接。
6. 端点路径与参数以 TikHub OpenAPI 为准。
7. 端点计费按调用记录。未知费用记“待对账”。
8. 直接调用 TikHub 必须带 `Authorization`、`Accept`、`User-Agent`。缺 `User-Agent` 或 `Accept` 会返回 403。

## 8. 21 张表

### 8.1 表清单

| 组 | 表 |
|---|---|
| 内容（12） | `creator`、`creator_snapshot`、`video`、`video_snapshot`、`comment`、`comment_snapshot`、`hashtag`、`hashtag_snapshot`、`video_hashtag`、`trend_topic`、`sound`、`transcript` |
| 电商（7） | `product`、`product_snapshot`、`shop`、`product_review`、`creator_commerce`、`video_product`、`creator_product` |
| 广告（2） | `ad`、`ad_creative` |
| 治理（复用） | `raw_records`、`task_runs`、`sources`、`datasets` |

### 8.2 建模原则

1. 所有 ID 用 `TEXT`。TikTok ID 超过 2^53。
2. 所有时间用 `TIMESTAMPTZ`，存 UTC。
3. 计数用 `BIGINT`。比率用 `NUMERIC(6,5)`，范围 0 到 1。
4. 金额用 `NUMERIC(18,4)`，另带 `currency`。
5. 缺失值写 `NULL`。禁止写 0 或推测值。
6. 数组与对象用 `JSONB`。禁止逗号拼接字符串。
7. 快照表只插入。修正写新行。
8. 每张表带 8 个治理列：`provider`、`endpoint_type`、`run_id`、`raw_ref`、`schema_version`、`captured_at`、`is_stale`、`quality_flags`。另带 `workspace_id` 与 `project_id`。
9. 快照 ID 用 `UUIDv5`。输入包含实体键、`captured_at`、`provider`、`endpoint_type` 与 `run_id`。
10. `video.hashtags` 只做展示。归因必须走 `video_hashtag`。
11. 主数据表的主键不得为空。
12. `product` 用 `(region, product_id)` 作用域。
13. `shop` 用非空 `shop_key`，`shop_id` 可空。
14. `ad_id` 带命名空间前缀。
15. `comment_id` 缺失时用派生键，并标 `derived_identity`。
16. 原始响应只存 `raw_ref`。不把原始 JSON 内联进标准表。

### 8.3 必须修正的建模问题

| 编号 | 问题 | 修正 |
|---|---|---|
| M1 | 快照 ID 用 wall-clock | 加 `endpoint_type` 与 `run_id`。重跑必须得到同一 ID。 |
| M2 | `shop_id` 可空当主键 | 改非空 `shop_key`。`shop_id` 作业务键。 |
| M3 | `live_room` 只用 `room_id` | 加 `started_at`。R2 建表。 |
| M4 | `trend_topic` 主键缺周期 | 主键加 `country_code`、`time_window`、`language`。 |
| M5 | `video_hashtag` 缺位置 | 主键加 `position`。 |
| M6 | `ad_creative` 用过期 URL 生成 ID | 用 `ad_id + format + asset_hash`。 |
| M7 | 缺 `product_review`、`video_product`、`creator_product` | R1 补齐。 |
| M8 | 缺字段 | 补 `location_created`、`web_video_url`、`has_shop_product`、`ifl_30d_cnt`、`video_30d_cnt`、`live_30d_cnt`、`gmv_video`、`gmv_live`、`promotion_performance_score`。 |

### 8.4 字段字典

完整字段见[《TikTok R1 21 张表 schema 草案》](./【数据模型】TikTok-R1-21张表.md)。本方案只列关键口径：

1. `play_count` 是生命周期累计。
2. `play_delta` 是本次快照减上次快照。
3. `engagement_rate = (like + comment + share + collect) / play`。
4. `save_rate = collect / play`。
5. `share_rate = share / play`。
6. `gpm = gmv / play * 1000`。
7. `gmv_30d_amt` 是第三方估算。必须带 `is_estimated=true`。
8. `commission` 是佣金率，存 0 到 1 小数。
9. `sold_count` 与 `sale_30d_cnt` 口径不同。不得相加。
10. `viewer_count` 是瞬时值。`total_entered` 是累计值。

## 9. 13 个 Agent 工具

### 9.1 内容波（8）

| 工具 | 输入 | 输出 | 执行 |
|---|---|---|---|
| `tiktok_trend_rank` | `rank_type`、`country_code`、`industry_id`、`period`、`limit` | 榜单行与趋势曲线 | 异步，300 秒，单次上限 2 美元 |
| `tiktok_hashtag_videos` | `hashtag`、`country_code`、`date_range`、`sort_by`、`limit` | 视频列表与指标 | 异步，600 秒，单次上限 3 美元 |
| `tiktok_video_search` | `query`、`country_code`、`date_range`、`sort_by`、`limit` | 视频列表与指标 | 异步，600 秒，单次上限 3 美元 |
| `tiktok_video_detail` | `video_urls` 或 `video_ids`、`include_transcript` | 视频详情、作者、字幕 | 异步，600 秒，单次上限 3 美元 |
| `tiktok_video_comments` | `video_urls`、`comments_per_video`、`include_replies` | 评论与回复树 | 异步，600 秒，单次上限 2 美元 |
| `tiktok_creator_profile` | `handles` 或 `sec_uids`、`view`、`video_limit` | 达人资料、作品、带货 | 异步，600 秒，单次上限 3 美元 |
| `tiktok_creator_search` | `query`、`region`、`follower_min`、`follower_max`、`limit` | 达人候选 | 异步，300 秒，单次上限 2 美元 |
| `tiktok_transcript` | `video_urls`、`language` | 字幕与转写 | 异步，600 秒，单次上限 2 美元 |

### 9.2 Shop 波（3）

| 工具 | 输入 | 输出 | 执行 |
|---|---|---|---|
| `tiktok_shop_product_search` | `keyword`、`country_code`、`sort_by`、`limit` | 商品列表与指标 | 异步，300 秒，单次上限 3 美元 |
| `tiktok_shop_product_detail` | `product_urls` 或 `product_ids`、`region` | 商品详情、SKU、GMV、库存 | 异步，300 秒，单次上限 3 美元 |
| `tiktok_shop_reviews` | `product_urls`、`max_reviews`、`region` | 商品评论 | 异步，300 秒，单次上限 2 美元 |

### 9.3 达人波（2）

| 工具 | 输入 | 输出 | 执行 |
|---|---|---|---|
| `tiktok_creator_commerce` | `handles`、`region` | GMV、GPM、品牌、受众 | 异步，600 秒，单次上限 3 美元 |
| `tiktok_topic_demand` | `keyword`、`region`、`time_window` | 搜索热度、增长、内容缺口 | 异步，300 秒，单次上限 2 美元 |

### 9.4 工具契约规则

1. 输入 schema 由 provider schema 生成。
2. 每个工具声明同步或异步。
3. 每个工具声明超时、单次上限、缓存 TTL、幂等键与降级链。
4. 未过验收门槛的工具不暴露。
5. 工具返回 `run_id`、`status`、`records_count`、`cost`、`provider`。
6. 工具不得返回未脱敏的 cookie、token 或密钥。

## 10. 工作台

### 10.1 页面

一个 TikTok 模块页：`/tools/tiktok`。

5 个页签：

1. 趋势。
2. 视频。
3. 达人。
4. 商品。
5. 运行。

### 10.2 页签内容

| 页签 | 卡片 | 表格 | 动作 |
|---|---|---|---|
| 趋势 | 今日采集量、成本、成功率 | 排名、名称、帖子数、播放量、增长率、趋势状态、行业、国家、快照时间 | 看话题视频、加入监控、对比昨日、导出 |
| 视频 | 视频数、总播放、Top 作者 | 封面、文案、作者、发布时间、播放、点赞、评论、互动率、增速、广告/带货标记 | 详情、评论、字幕、监控、导出 |
| 达人 | 候选数、平均粉丝、平均互动率 | 头像、handle、昵称、粉丝、平均播放、互动率、类目、地区、认证、带货 GMV | 看视频、看粉丝质量、看带货商品、加入合作清单 |
| 商品 | 商品数、总 GMV、中位价、平均佣金 | 图片、商品名、价格、30 天销量、30 天 GMV、佣金率、评分、评论数、卖家 | 详情、评论、看带货达人、加入选品池 |
| 运行 | 运行中、今日成功率、今日成本 | run_id、工具、状态、记录数、成本、provider、耗时 | 取消、重跑、看原始记录 |

### 10.3 运行页增强

1. 显示异步状态。
2. 显示 `provider_run_id`。
3. 显示预留成本与实际成本。
4. 显示错误分类。
5. 支持取消与重跑。

## 11. 异步任务

### 11.1 状态机

`accepted` → `queued` → `running` → `succeeded` | `partial_success` | `empty` | `failed` | `timed_out` | `cancelled`。

### 11.2 规则

1. 提交返回 `run_id`。
2. 同一输入返回同一幂等键。
3. Apify 启动后持久化 `provider_run_id` 与 `dataset_id`。
4. 每 5 秒轮询。
5. 超时保留 `provider_run_id`。可续查。
6. 失败重试最多 2 次。退避 10 秒与 60 秒。
7. 取消先调 Apify abort。确认后标 `cancelled`。
8. 原始响应按 `run_id` 分区保存。
9. 标准表写入以 `run_id` 与实体键幂等。
10. 同步 quick-collect 只服务 30 秒内的 TikHub 单页查询。

### 11.3 现有客户端改造

1. `tiktok_cdo` 改为提交异步任务。
2. 飞书卡片按 `message_id` 原地更新。
3. 结果卡显示 `run_id`、状态、记录数、成本。
4. 从 `raw-records` 或扩展后的 quick-collect 响应取 records。

## 12. 成本与配额

### 12.1 单价

| 类型 | 单价 |
|---|---|
| 帖子 | 约 3.7 美元每千条 |
| 评论 | 约 1.25 美元每千条 |
| Shop 搜索 | 约 15 美元每千条 |
| Shop 详情 | 约 25 美元每千条 |
| Shop 评论 | 约 3 美元每千条 |
| 广告 | 约 0.49 美元每千条 |
| 趋势 | 约 1.5 美元每千条 |
| 直播 | 约 5 美元每千条 |
| 达人带货 | 启动 0.005 美元每次。结果计费待对账。 |

### 12.2 配额

1. 单次调用默认上限 2 美元。
2. 视频详情、达人、商品详情单次上限 3 美元。
3. 项目日额度 20 美元。
4. 项目并发 2。模块并发 4。
5. 缓存优先。相同输入不重复调用。
6. 80% 额度告警。
7. 触顶阻止。不自动放宽。

### 12.3 预算

R1 日成本目标：

1. 内容 1 到 2 美元。
2. Shop 1 到 3 美元。
3. 达人 0.5 美元。

R1 月预算上限 300 美元。

## 13. 验收门槛

### 13.1 模块门槛

每个模块必须通过 7 类用例：

1. 正常：10 条金标准用例，记录数大于 0。
2. 空：上游返回 0 条，标 `empty`，不重试。
3. 参数错：400，不重试，记录错误。
4. 权限错：403，切备链。
5. 超时：保留 `provider_run_id`，可续查。
6. 去重：同一输入重复调用，不产生重复实体。
7. 成本：单次与单日不超上限。

### 13.2 数据门槛

1. 核心字段完整率不低于 90%。
2. 重复率低于 1%。
3. 快照 ID 幂等。
4. 每条记录有 `provider`、`endpoint_type`、`run_id`、`raw_ref`。
5. 估算值带 `is_estimated`。
6. 缺失值写 `NULL`，不写 0。

### 13.3 稳定性门槛

1. 连续 7 天成功率不低于 95%。
2. 主备切换至少演练 1 次。
3. 状态语义正确：`verified` 只在有记录且无错误时成立。
4. Agent 与工作台只读通过门槛的工具。

## 14. 9 周排期

| 周 | 阶段 | 交付 |
|---|---|---|
| 1 | 底座 | 修 quick-collect 或改读 raw-records。修 CDO 参数与身份解析。修状态语义。 |
| 2 | 底座 | 21 张表 schema v1。异步任务四态。契约测试框架。 |
| 3 | 内容 | 趋势榜、话题视频。 |
| 4 | 内容 | 关键词搜索、视频详情、评论。 |
| 5 | 内容 | 达人资料、达人搜索、字幕。内容模块过门槛。 |
| 6 | Shop | 商品搜索、商品详情。 |
| 7 | Shop | 商品评论、快照。Shop 模块过门槛。 |
| 8 | 达人 | 达人带货、选题需求、假流量。达人模块过门槛。 |
| 9 | 集成 | 工作台 5 个页签。Agent 13 个工具。成本看板。月度巡检。 |

## 15. 风险与对策

| 编号 | 风险 | 触发 | 对策 |
|---|---|---|---|
| R1 | 字段不可得 | 首次建表或看板读取 | 字段必须有证据。缺证据的字段不建列。 |
| R2 | 工具契约与 Actor 输入不符 | 首次联调 | 契约由 schema 生成。先探测，再写契约。 |
| R3 | 成本失控 | 同时开 3 个模块或缩短刷新 | 单次上限、日额度、缓存、Top-N 采样、80% 告警。 |
| R4 | Provider 下架 | 月度巡检失败 | 每月跑 Actor 巡检。保留备链。 |
| R5 | 身份错配 | 跨源 join | `creator_id` 用 uid。handle 只做别名。`product` 用 region 作用域。`ad_id` 带命名空间。 |
| R6 | 指标口径不一致 | 看板跨源对比 | 指标字典带公式、窗口、来源、是否估算。禁止跨源相加。 |
| R7 | 评论样本偏差 | 用评论做定量结论 | 标样本量与覆盖。只做定性洞察。定量用 Shop 评论。 |
| R8 | 媒体链接过期 | 看板回看历史 | 存 URL 与 `expires_at`。按需代理。长期留存后置。 |
| R9 | 美国广告数据缺口 | 广告模块进入 P0 | 广告后置。只做 Creative Center。标 `coverage=partial`。 |
| R10 | 直播数据稀疏 | 直播模块进入 P1 | 直播后置。只监控 10 到 20 个房间。 |
| R11 | 权限伪实现 | 第二个项目接入 | R1 单项目。强制 `project_id`。MCP 强制 Bearer。 |
| R12 | 状态失真 | 按 catalog 排优先级 | 以 `providers/status` 与最近 TaskRun 为准。 |

## 16. 交付物

1. 本方案文档。
2. [《TikTok R1 21 张表 schema 草案》](./【数据模型】TikTok-R1-21张表.md)。
3. 21 张表迁移脚本。
4. 31 个 TikHub 端点适配器。
5. 13 个工具契约。
6. 工作台 5 个页签。
7. 验收用例与测试报告。
8. 月度 Actor 巡检脚本。

## 17. Phase 0 实施记录（2026-10-19）

### 17.1 已完成

1. CDO 改为按 `task_run_id` 读 `/api/raw-records`，不再依赖 quick-collect 返回 records。
2. CDO 请求使用 `LARK_CDO_PROJECT_ID`，不再发 `workspace_id`。
3. 话题、账号、达人、粉丝、广告 action 的参数已修正。
4. `creator` action 先解析数字 `creator_uid`，再调用 `fetch_creator_info`。
5. cleaner 支持 TikHub content，L1/L2 不再只认 Apify 字段名。
6. `/api/collector-docs` 的状态由最近实测证据派生。
7. 新增 `POST /api/quick-collect/async`，返回 202 与 `task_id`。
8. 新增 Phase 0 契约测试 `tests/unit/test_tiktok_cdo_phase0.py`。
9. 新增 21 张表 Alembic 迁移草案 `202610190045_tiktok_r1_canonical_tables.py`。
10. 完成 31 个 TikHub 端点字段探测。

### 17.2 验证结果

1. 相关单元测试 116 个通过。
2. 全量单元测试 1635 个通过。
3. 3 个既有失败与本改动无关：
   - `test_firecrawl_collector.py`：环境存在 Firecrawl 配置。
   - `test_v2_traceability.py`：既有文档缺失。
   - `test_workflow_executor_postgres_guard.py`：既有授权包文档缺失。
4. `ruff` 对新增 CDO 文件与测试通过。
5. 变更文件的 `stat` 与可读字节一致，无 NUL 字节。
6. 21 张表迁移在临时 PostgreSQL 16 上升级与降级通过：21 张表、64 个外键。
7. 31 个 TikHub 端点探测：25 个可用、4 个失败、2 个受限。

### 17.3 未完成

1. 21 张表迁移尚未应用到项目数据库或生产库。
2. 探测报告待评审，字段契约待回写。
3. Phase 1 内容模块。

## 18. Phase 1 Slice 1 实施记录（2026-10-19）

### 18.1 已完成

1. 新增 17 个 TikHub 内容端点。
2. 新增 `TIKHUB_CONTENT_ENDPOINT_MAP` 与专属提取器、归一化器。
3. 目录、校验白名单、quick-collect 映射已同步。
4. 新增 13 个契约测试。

### 18.2 新端点

身份：`tikhub_tiktok_sec_uid`、`tikhub_tiktok_user_id`、`tikhub_tiktok_identity_by_username`。

视频：`tikhub_tiktok_video_detail`、`tikhub_tiktok_user_posts_web`、`tikhub_tiktok_search_web`。

评论：`tikhub_tiktok_comments_app`、`tikhub_tiktok_comment_replies_app`。

达人：`tikhub_tiktok_user_profile_web`、`tikhub_tiktok_user_fans_web`。

话题：`tikhub_tiktok_hashtag_detail_app`、`tikhub_tiktok_tag_posts_web`、`tikhub_tiktok_trending_searchwords`。

音乐：`tikhub_tiktok_music_chart`。

分析：`tikhub_tiktok_fake_views`、`tikhub_tiktok_comment_keywords`。

趋势：`tikhub_tiktok_ads_trends`。

### 18.3 验证结果

1. 新增契约测试 13 个通过。
2. 相关测试 128 个通过。
3. 全量单元测试 1655 个通过。
4. 3 个既有失败与本改动无关。
5. catalog 唯一端点从 258 增至 275。

### 18.4 未完成

1. 12 张内容标准表的 ORM 与 Repository。
2. 8 个内容工具契约与 Agent 路由。
3. 工作台内容页。
4. 新端点生产实测。

## 19. Phase 1 Slice 2 实施记录（2026-10-19）

### 19.1 已完成

1. 新增 12 张内容表的 ORM 模型。
2. 新增租户仓储 `repositories/tiktok_content.py`。
3. 12 张表的列与迁移 SQL 逐列一致。
4. 新增 8 个仓储测试，使用 SQLite async。

### 19.2 仓储能力

| 实体 | 能力 |
|---|---|
| creator | upsert、get、snapshot、list snapshots |
| video | upsert、get、snapshot、list snapshots |
| comment | upsert、get、snapshot、list by video |
| hashtag | upsert、get、snapshot、list snapshots |
| video_hashtag | add |
| trend_topic | add、list |
| sound | upsert、get |
| transcript | upsert、get |

### 19.3 验证结果

1. 8 个仓储测试通过。
2. 相关测试 194 个通过。
3. 全量单元测试 1663 个通过。
4. 3 个既有失败与本改动无关。
5. 12 张表列与迁移逐列一致。

### 19.4 未完成

1. 采集结果写入标准表的编排服务。
2. 8 个内容工具契约与 Agent 路由。
3. 工作台内容页。
4. 新端点生产实测。

## 20. Phase 1 Slice 3 实施记录（2026-10-19）

### 20.1 已完成

1. 新增 `services/tiktok_content_ingestion.py`。
2. 两阶段写入：主数据 → 快照与关系。
3. 接入 `execute_collection_task`。只对 17 个内容端点触发。
4. 投影失败用 savepoint 隔离，不影响原始采集。
5. 新增 9 个写入测试。

### 20.2 记录映射

| 记录 | 写入表 |
|---|---|
| `tiktok_video` | creator、sound、video、video_snapshot、hashtag、video_hashtag |
| `tiktok_user` | creator、creator_snapshot |
| `tiktok_comment` | 最小 video、creator、comment、comment_snapshot |
| `tiktok_hashtag` | hashtag |
| `tiktok_trend` / hashtag | hashtag、hashtag_snapshot、trend_topic |
| `tiktok_trend` / search_word | trend_topic |
| `tiktok_trend` / music | sound、trend_topic |
| `tiktok_analytics` | 跳过 |
| `tiktok_identity` | 跳过 |

### 20.3 验证结果

1. 9 个写入测试通过。
2. 相关测试 214 个通过。
3. 全量单元测试 1672 个通过。
4. 3 个既有失败与本改动无关。

### 20.4 未完成

1. 8 个内容工具契约与 Agent 路由。
2. 工作台内容页。
3. 新端点生产实测。
4. 历史 RawRecord 回填标准表。

## 21. Phase 1 Slice 4 实施记录（2026-10-19）

### 21.1 已完成

1. 新增 `services/tiktok_tools.py`，实现 8 个内容工具。
2. MCP 服务注册 8 个工具。
3. 新增 REST 入口 `GET /api/tiktok/tools` 与 `POST /api/tiktok/tools/{tool_id}`。
4. 新增 13 个工具测试。

### 21.2 工具清单

| tool_id | 主端点 | 说明 |
|---|---|---|
| `tiktok_trend_rank` | `tikhub_tiktok_ads_trends` | Creative Center 热门话题榜 |
| `tiktok_hashtag_videos` | `tikhub_tiktok_tag_posts_web` / `tikhub_tiktok_hashtag_posts` / `tikhub_tiktok_search_web` | 按 challengeID、ch_id 或话题名 |
| `tiktok_video_search` | `tikhub_tiktok_search_web` | 关键词视频搜索 |
| `tiktok_video_detail` | `tikhub_tiktok_video_detail` | 失败降级 `apify_tiktok_scraper` |
| `tiktok_video_comments` | `tikhub_tiktok_comments_app` | 可选回复树 |
| `tiktok_creator_profile` | `tikhub_tiktok_user_profile_web` | 可选作品与粉丝；失败降级 `apify_tiktok_media_profile_scraper` |
| `tiktok_creator_search` | `tikhub_tiktok_search_web` | 从视频作者提取达人候选 |
| `tiktok_transcript` | `apify_tiktok_transcript_extractor` | 按视频 URL 提取字幕 |

### 21.3 验证结果

1. 13 个工具测试通过。
2. 相关测试 234 个通过。
3. 全量单元测试 1685 个通过。
4. 3 个既有失败与本改动无关。
5. MCP 工具总数 13：5 个通用工具 + 8 个 TikTok 内容工具。

### 21.4 已知限制

1. `tiktok_creator_search` 是视频作者代理，不是原生用户搜索。`web/fetch_search_user` 实测 400。
2. `tiktok_hashtag_videos` 只给话题名时走关键词搜索并客户端过滤，结果不是全量。
3. `tiktok_transcript` 走 Apify，耗时约 25 秒。
4. CDO 飞书机器人仍走原有直连端点，尚未切到工具层。

### 21.5 未完成

1. 工作台内容页。
2. 新端点与工具生产实测。
3. 回填历史 RawRecord。
4. CDO 意图迁移到工具层。

## 22. Phase 1 Slice 5 实施记录（2026-10-19）

### 22.1 已完成

1. 新增 `/tools/tiktok` 工作台页面。
2. 新增趋势、视频、达人三个页签。
3. 新增 `lib/api/tiktok-tools.ts` API 客户端。
4. 侧边栏新增「TikTok 工作台」入口。
5. 页面支持项目选择、运行状态、记录表、上游 run 与原始 JSON。

### 22.2 页面能力

| 页签 | 工具 | 输入 |
|---|---|---|
| 趋势 | `tiktok_trend_rank` | 国家、周期、条数 |
| 视频 | `tiktok_video_search` / `tiktok_hashtag_videos` / `tiktok_video_detail` / `tiktok_video_comments` | 关键词、话题、视频 ID/URL、评论回复开关 |
| 达人 | `tiktok_creator_profile` / `tiktok_creator_search` | handle、搜索词、作品/粉丝开关 |

### 22.3 验证结果

1. `pnpm lint`：0 error，6 个既有 warning。
2. `pnpm test`：9 通过。
3. `pnpm build`：成功，路由包含 `/tools/tiktok`。
4. 本地截图复核：趋势、视频、达人三个页签布局正常。
5. 本地 API 未启动，项目选择显示「暂无项目」；真实运行待生产实测。

### 22.4 未完成

1. 工具与页面生产实测。
2. 历史 RawRecord 回填。
3. CDO 意图迁移到工具层。
4. 运行记录页展示工具调用。

## 23. 下一步

1. 评审 Slice 5。
2. 跑工具与页面生产实测。
3. 回填历史 RawRecord。
4. 迁移 CDO 意图到工具层。
5. 在运行记录页展示工具调用。

## 24. 生产 A 实测记录（2026-10-19）

### 24.1 部署口径

1. 目标：生产 A，`https://scrapy.luteos.com`。
2. 分支：`main`。
3. 提交：`d8c23e5`（R1 主体）→ `894eabd`（cover 修复）→ `a551cd3`（字幕入库）。
4. 数据库备份：`/opt/data-achieve-scrapy/backups/tiktok_r1_pre_20261019_205338.dump`，8.5 MB。
5. 迁移：`202607280044` → `202610190045`。
6. 表数核验：21/21 张表存在。

### 24.2 工具实测

| tool_id | 状态 | 记录数 | 耗时 | 备注 |
|---|---|---:|---:|---|
| `tiktok_trend_rank` | success | 20 | 1.39s | 页面复跑 50 条成功 |
| `tiktok_video_search` | success | 10 | 2.44s | 修复 cover 后通过 |
| `tiktok_hashtag_videos` | success | 3 | 2.18s | 上游搜索 10 条，客户端过滤后 3 条 |
| `tiktok_video_detail` | success | 1 | 1.79s | 详情字段完整 |
| `tiktok_video_comments` | success | 51 | 7.87s | 20 条主评论 + 31 条回复 |
| `tiktok_creator_profile` | success | 16 | 4.33s | 1 条资料 + 15 条作品 |
| `tiktok_creator_search` | success | 9 | 2.23s | 视频作者代理 |
| `tiktok_transcript` | success | 1 | 29.9s | 修复后写入 transcript 表 |

### 24.3 规范表核验

首轮内容工具运行后的行数：

| 表 | 行数 |
|---|---:|
| `creator` | 53 |
| `creator_snapshot` | 1 |
| `video` | 27 |
| `video_snapshot` | 46 |
| `comment` | 51 |
| `comment_snapshot` | 51 |
| `hashtag` | 162 |
| `hashtag_snapshot` | 20 |
| `video_hashtag` | 396 |
| `trend_topic` | 20 |
| `sound` | 27 |

字幕修复后 `transcript` 表新增 1 行，`video_id=7670318941658483981`，`language=en`，`transcript_source=third_party_asr`，`word_count=49`。

### 24.4 实测发现与修复

1. Web 搜索的 `video.cover` 是 URL 字符串，App 详情才是 `{url_list: [...]}`。旧归一化对字符串调用 `.get`，导致 `tiktok_video_search` 全部失败。修复：`_normalize_tiktok_video` 同时接受字符串与对象，并给 `author`、`stats`、`music` 加类型护栏。
2. 字幕记录此前只写 `RawRecord`，`transcript` 表为空。原因：入库钩子只匹配 `tikhub_social`。修复：钩子支持 `apify_tiktok_transcript_extractor`，新增字幕主表与 `transcript` 写入。
3. 两条修复都补了回归测试。

### 24.5 验证结果

1. 单元测试：1930 通过。
2. 控制台：`tsc --noEmit`、`eslint`、`next build` 全部通过。
3. 生产页面 `/tools/tiktok` 正常加载项目、页签、运行状态与结果表。
4. 页面实测趋势工具：50 条记录、1 次上游调用、0 错误。

### 24.6 尚未完成

1. 回填历史 `RawRecord` 到规范表。
2. 迁移 CDO 意图到工具层。
3. 在运行记录页展示工具调用。
4. 电商与达人商务表的工具层尚未接入。

## 25. 收尾实施记录（2026-10-19）

### 25.1 历史 RawRecord 回填

1. 新增 `services/tiktok_content_backfill.py`。
2. 新增 `maintenance/tiktok_raw_record_backfill.py`。
3. 新增 `scripts/backfill-tiktok-raw-records.sh`。
4. 默认 dry-run。`--execute` 才写库。
5. 复用原始 `run_id` 与逐条 `collected_at`，快照 ID 保持幂等。
6. 逐条 savepoint。单条失败不中断整批。
7. 默认只回填内容与电商端点。`--include-phase0-tikhub` 可纳入旧 Phase 0 端点。
8. 回填期间启用“旧数据不覆盖新数据”保护。

### 25.2 CDO 工具层迁移

1. 新增 `agents/tiktok_cdo/tool_router.py`。
2. `search`、`hashtag`、`user_posts`、`creator`、`followers` 改走工具层。
3. `top_ads`、`ads_search`、`live` 保留直连。`sentiment` 保留 Exa。
4. `LARK_CDO_TOOL_ROUTING=off|hybrid|all` 控制灰度，默认 `hybrid`。
5. `LARK_CDO_TOOL_ACTIONS` 控制 hybrid 下启用的动作。
6. 直连回退修正为发送 `project_id`，并按 `task_run_id` 读取 RawRecord。
7. 清洗器与卡片兼容规范字段。

### 25.3 运行页工具标识

1. `CollectionTask.config["tool_call"]` 保存工具调用元数据，不需要新迁移。
2. 工具调用写入 `tool_call_id`、`tool_id`、标签、角色与参数摘要。
3. `TaskRunResponse` 返回工具字段、任务名、端点与项目。
4. 运行列表新增「工具」列。
5. 运行详情新增工具调用卡片。
6. 服务端配置合并时剔除 `tool_call`，避免进入采集器或 Actor 输入。

### 25.4 电商与达人带货

1. 新增 7 张电商 ORM：`shop`、`product`、`product_snapshot`、`product_review`、`creator_commerce`、`video_product`、`creator_product`。
2. 新增 3 个 TikHub 端点：商品搜索 V2、热卖商品、商品评论 V2。
3. 新增 4 个工具：
   - `tiktok_product_search`
   - `tiktok_product_detail`
   - `tiktok_product_reviews`
   - `tiktok_creator_commerce`
4. 商品搜索主链 Apify，回退 TikHub。
5. 商品详情主链 Apify。
6. 商品评论走 TikHub V2。
7. 达人与带货走 Apify `lemur/tiktok-shop-creators`。
8. 入库支持商品、店铺、商品快照、评论与达人带货观察。
9. `product_key` 使用 `region:product_id`。`shop_key` 使用 `shop:region:shop_id`。
10. 百分比字段统一从 0–100 换算为 0–1。

### 25.5 验证

1. 单元测试 1972 通过。
2. 新增 40 个测试，覆盖回填、电商归一化、电商入库、电商工具、CDO 路由。
3. 控制台 `tsc --noEmit`、`eslint`、`next build` 通过。

### 25.6 生产 A 验证（2026-10-19）

1. 回填预检：扫描 431 个运行、1392 条 RawRecord，其中 189 条可回填。
2. 回填执行：189 条全部投影，失败 0。
3. 回填新增：`product` 17、`product_snapshot` 17、`shop` 13、`transcript` 3、`trend_topic` 70、`video_hashtag` 396。
4. 追加 Phase 0 口径：可回填 345 条，执行后失败 0；2 条跨项目实体冲突被记录。
5. 回填后总量：`creator` 139、`video` 102、`comment` 51、`hashtag` 228、`product` 23、`product_snapshot` 33、`product_review` 20、`creator_commerce` 3、`shop` 17。
4. `tiktok_product_search`：success，3 条，约 7.7 秒。
5. `tiktok_product_detail`：success，1 条，约 8.8 秒；价格 84.49、30 天销量 304、30 天 GMV 25,680。
6. `tiktok_product_reviews`：success，10 条，约 5.1 秒。
7. `tiktok_creator_commerce`：success，1 条，约 7.6 秒；粉丝 151,353、GMV 1,098,437、销量 12,428。
8. 运行列表与详情页已显示工具名、端点、调用 ID 与参数。
9. CDO `search` 意图通过 `run_intent_tool` 返回 3 条视频，状态 success。

### 25.7 已知限制

1. `shop.rating`、`shop.follower_count`、`shop.product_count` 在现有 Apify 详情中多数为空。
2. 回填默认排除 Phase 0 旧端点，避免误收。需要时显式加 `--include-phase0-tikhub`。
3. 规范表主键是全局的，租户是行属性。同一实体被多个项目采集时，回填会记录 `tiktok_entity_belongs_to_another_tenant`。本次生产出现 2 条，已跳过，不影响其余记录。

## 26. 广告与商品关系补齐（2026-10-19）

### 26.1 广告

1. 新增 `Ad` 与 `AdCreative` ORM、仓储与入库。
2. 新增工具 `tiktok_ads_top` 与 `tiktok_ads_detail`。
3. 列表工具返回素材、CTR、成本与互动指标。
4. 详情工具补充广告主、落地页、行业与目标。
5. 生产实测：`tiktok_ads_top` 返回 3 条；`tiktok_ads_detail` 返回 1 条；`ad` 与 `ad_creative` 各写入 3 行。

### 26.2 视频与达人商品关系

1. 新增端点：
   - `tikhub_tiktok_video_products`
   - `tikhub_tiktok_creator_showcase`
2. 新增工具：
   - `tiktok_video_products`
   - `tiktok_creator_showcase`
3. 两个端点需要 `TIKHUB_TIKTOK_CREATOR_COOKIE`。未配置时工具返回 `tikhub_creator_cookie_not_configured`，不发起计费请求。
4. 视频商品入库可自动派生达人商品关系，`relation_type=promoted_in_video`。
5. 当前生产未配置 Cookie，两张关系表保持为空。配置 Cookie 后即可写入。

### 26.3 跨项目实体冲突

1. 回填报告新增 `cross_tenant_conflicts` 计数。
2. 冲突记录仍保留在 `errors` 中，包含实体类型与 ID。
3. 当前策略：跳过冲突记录，不覆盖其他项目的实体。

### 26.4 工具总数

TikTok 工具从 12 个增加到 16 个：

- 8 个内容工具
- 4 个电商工具
- 2 个商品关系工具（Cookie 门控）
- 2 个广告工具

## 27. 创作者 Cookie 的配置方式（2026-10-20）

### 27.1 设计

1. 不把 Cookie 写死为服务器环境变量。
2. TikTok 凭证新增 `creator_cookie` 字段。
3. Cookie 存入工作区加密凭证库 `platform_credential_bundles`。
4. 商品关系工具在调用时从凭证库解析 Cookie。
5. Cookie 通过 `ContextVar` 传入采集器，不写入 `CollectionTask.config`。
6. 运行记录只显示工具与端点，不显示 Cookie。

### 27.2 网站配置项

1. 打开「凭证设置」。
2. 找到 TikTok Research。
3. 填写「TikTok creator Cookie」。
4. 保存。

凭证库需要 `PLATFORM_CREDENTIAL_MASTER_KEY`。生产 A 已配置有效 Fernet 密钥，权限 `600`。

### 27.3 使用时的弹窗

1. 在 TikTok 工作台选择「视频关联商品」或「达人橱窗」。
2. 未配置 Cookie 时，工具返回 `credential_required:tiktok.creator_cookie`。
3. 工作台弹出「连接 TikTok 创作者账号」窗口。
4. 用户粘贴 Cookie 后点击「保存并继续」。
5. 系统写入凭证库，并自动重试上一次工具调用。
6. 不需要刷新页面。

说明：TikTok 没有面向该端点的公开 OAuth。弹窗保存的是登录态 Cookie，不是 OAuth 授权。

### 27.4 生产验证

1. 凭证库加密与解密往返成功。
2. 未配置 Cookie 时返回 `credential_required:tiktok.creator_cookie`。
3. 工具列表为 16 个。
4. 提供方目录已返回 `creator_cookie` 字段。
5. 公网 `/api/health` 与 `/api/tiktok/tools` 恢复 200。

