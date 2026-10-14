# Apify 采集方案卡 — TikTok

日期：2026-10-14。数据来源：Apify Store API（30 天真实运行统计、输入 schema）+ 本项目真实试跑。原始数据在 `reports/apify-deep-research/`。

## 主题矩阵

| 主题 | 覆盖 | 主力 actor | 降级① | 降级② |
|---|---|---|---|---|
| 帖子（搜索/话题/账号/URL 四入口） | ● | clockworks/tiktok-scraper | clockworks/free-tiktok-scraper | apidojo/tiktok-scraper |
| 账号主页深挖 | ● | clockworks/tiktok-profile-scraper | clockworks/tiktok-scraper（profiles 入口） | apidojo/tiktok-scraper |
| 评论 | ● | clockworks/tiktok-comments-scraper | clockworks/tiktok-scraper（commentsPerPost 加挂） | — |
| 话题聚合 | ● | clockworks/tiktok-hashtag-scraper | clockworks/tiktok-scraper（hashtags 入口） | — |
| 视频字幕 | ● | clockworks/tiktok-transcript-extractor | — | — |
| Shop 商品详情 | ● | pratikdani/tiktok-shop-scraper | clockworks/tiktok-shop-scraper | lemur/tiktok-shop-creators（达人维度） |
| Shop 商品搜索 | ● | pratikdani/tiktok-shop-search-scraper | clockworks/tiktok-shop-scraper（keywords 入口） | — |
| Shop 达人 | ● | lemur/tiktok-shop-creators | pratikdani/tiktok-shop-search-scraper（seller 字段） | — |
| 广告素材 | ● | lexis-solutions/tiktok-ads-scraper | doliz/tiktok-creative-center-scraper | — |
| Creative Center 趋势 | ● | doliz/tiktok-creative-center-scraper | — | — |

● = 完整覆盖；项目现有 tikhub 通道可与 Apify 互为降级（见《能力总账》）。

## 主力 actor 详情

### clockworks/tiktok-scraper — 帖子主力
- 稳定性：ok 98.9%，30 天用户 27.6k，★4.76（369 评）
- 计费：PAY_PER_EVENT，result $0.0037/条；下载/滤镜等附加事件 $0.0013
- 输入（34 项，无必填）：hashtags / profiles / searchQueries / postURLs 四类入口二选一，resultsPerPage 控量；profileScrapeSections、videoSearchDateFilter、oldestPostDateUnified 收窄范围；commentsPerPost 可顺带取评论；aiVideoDescription/aiVideoSummary 可选 AI 摘要
- 输出 29 字段（实测）：id, text, textLanguage, createTime, createTimeISO, isAd, authorMeta(含 name/verified/fans), musicMeta, webVideoUrl, videoMeta(duration/等), diggCount, shareCount, playCount, collectCount, commentCount, repostCount, mentions, detailedMentions, hashtags, effectStickers, isSlideshow, slideshowImageLinks, isPinned, isSponsored, shortDramaSeriesInfo, mediaUrls, isStory, searchQuery, commentsDatasetUrl
- 超时预算：600s（批量 profile 场景给 1200s）

### clockworks/tiktok-profile-scraper — 账号主力
- 稳定性：ok 99.2%，用户 8.8k，★4.73
- 输入（20 项）：profiles 必填（stringList）；profileScrapeSections 选板块；resultsPerPage 控每账号条数
- 输出 31 字段（实测）：帖子全字段 + hasTikTokShopProduct, locationMeta, fromProfileSection, input
- 定位：批量账号监控。只取账号元信息时 resultsPerPage=0 可省费用

### clockworks/tiktok-comments-scraper — 评论主力
- 稳定性：ok 99.7%，用户 4.6k，★4.73
- 输入（11 项）：postURLs 必填；commentsPerPost、topLevelCommentsPerPost、maxRepliesPerComment 控量
- 输出 16 字段：text, diggCount, replyCommentTotal, createTimeISO, uniqueId, uid, cid, avatarThumbnail, videoWebUrl, url + 输入回显/error
- 注意：cid/uid 是评论级 ID；error/errorCode 字段存在，验收时要过滤

### clockworks/tiktok-hashtag-scraper — 话题主力
- 稳定性：ok 99.8%，用户 1.6k，★4.92
- 输出 30 字段（实测）：与帖子字段同构 + searchHashtag, hasTikTokShopProduct, input

### clockworks/tiktok-transcript-extractor — 字幕主力
- 稳定性：ok 99.3%，用户 268
- 输入 3 项：postURLs + downloadSubtitlesOptions
- 输出 23 字段：字幕正文 text/textLanguage + 帖子元数据（playCount/diggCount/authorMeta.name 等）+ subtitleLinks（原始字幕轨 URL）

### pratikdani/tiktok-shop-scraper — Shop 详情主力
- 稳定性：ok 100%（528 用户），★4.58
- 输入 2 项：url（shop.tiktok.com/view/product/...）+ region
- 输出 54 字段（实测）：product_id, product_name, product_desc, product_url, price, original_price, real_price, min/max/avg_price, currency, commission（佣金率）, gmv_amt, gmv_30d_amt, sale_cnt, sale_30d_cnt, ifl_30d_cnt（种草数）, live_30d_cnt, video_30d_cnt, total_stock_cnt, review_count, skus, specification, seller, seller_type, shop_type, shipping_price, categories, labels, is_hot, is_mall_recommended + 格式化副本（*_fz 后缀）
- 电商情报价值最高的单一 actor：GMV/销量/佣金/库存全覆盖

### pratikdani/tiktok-shop-search-scraper — Shop 搜索主力
- 稳定性：ok 99.9%，用户 255（★3.64，低分主要是价格抱怨）
- 输出 55 字段：与详情同构 + category1/2/3, comment_rate, commission_rate, free_shipping, country_code

### lexis-solutions/tiktok-ads-scraper — 广告主力
- 稳定性：ok 98.1%，用户 174
- 计费：$0.00049/条（十平台里最便宜的广告类）
- 输出 42 字段：adId, adTitle, adType, adLandingUrl, adSpent, adVideoUrl, adVideoCover, adImageUrls, adStartDate, adEndDate, advertiserId, advertiserName, username, status, auditStatus, rejectionInfo

### doliz/tiktok-creative-center-scraper — 趋势主力
- 稳定性：ok 99.8%，用户 132
- 输入 39 项（榜单类型/国家/行业可选）
- 输出信封形（实测）：code, msg, request_id, data（数据在 data 内层）。解析器要做信封剥离，参考本项目 dataset 归因链的 endpoint_type 剥层坑

## 降级链说明

1. **帖子**：free-tiktok-scraper（99.2%，字段 19 略少）→ apidojo/tiktok-scraper（96.0%）。apidojo 空结果返回单条 {noResults:true}，验收逻辑要识别。
2. **评论**：主力 actor 的 commentsPerPost 加挂评论是零成本降级（省一次 run），但字段没有独立评论 actor 全（无 cid/uid 层级）。
3. **Shop**：pratikdani 失败换 clockworks/tiktok-shop-scraper（97.1%，29 字段，keywords 搜索入口）。注意 clockworks 版字段命名不同（salePrice/originalPrice/availableQuantity vs price/gmv_*）。
4. **项目现有 apify_tiktok_* 端点已覆盖 6 个同款 actor**，方案卡确认后可复用现通道，不重复接入。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| apidojo/tiktok-scraper 返回 {noResults:true} | 空结果也输出一条记录 | 验收按字段而非条数判断 |
| doliz 输出在 data 内层 | 信封响应 | 解析器剥层 |
| clockworks 系 hasTikTokShopProduct | 帖子挂 Shop 商品标记 | 电商场景用它筛带货帖 |
| pratikdani price 字段带 *_fz 格式化副本 | 同值双字段 | 归一化时取数值版，弃 _fz |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| apify_tiktok_scraper / comments / transcript / creative_center / media_profile / shop_search | 全部保留，与本卡主力一致 |
| — | 新增建议：pratikdani/tiktok-shop-scraper（商品详情，GMV 字段）、lexis-solutions/tiktok-ads-scraper（替代现有广告补充） |
