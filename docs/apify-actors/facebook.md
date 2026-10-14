# Apify 采集方案卡 — Facebook

日期：2026-10-14。数据来源同总说明。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 页面帖子 | ● | apify/facebook-posts-scraper | apify/facebook-pages-scraper（页面概览+最新帖） | curious_coder/facebook-ads-library-scraper（广告侧写） |
| 页面资料 | ● | apify/facebook-pages-scraper | apify/facebook-search-scraper（信息卡） | — |
| 评论 | ● | apify/facebook-comments-scraper | facebook-posts-scraper（topComments 字段） | — |
| 小组帖子 | ● | apify/facebook-groups-scraper | — | — |
| 站内搜索 | ● | apify/facebook-search-scraper | — | — |
| 广告库（关键词/URL 驱动） | ● | curious_coder/facebook-ads-library-scraper | apify/facebook-ads-scraper（页面驱动） | — |
| 广告库（页面驱动） | ● | apify/facebook-ads-scraper | curious_coder（ads/library URL 也能收页面） | — |
| Marketplace 商品 | ● | apify/facebook-marketplace-scraper | — | — |

要点：广告两条路**按输入形态分工**而非替代——有关键词/广告库搜索 URL 用 curious_coder，只有主页 URL 用 apify 官方。二者字段同源（Facebook Ad Library API），schema 高度一致。

## 主力 actor 详情

### apify/facebook-posts-scraper — 帖子主力
- 稳定性：ok 99.8%（16232 用户）
- 计费：result $0.0027/条
- 输入 5 项：startUrls（requestListSources 形 [{url}]）+ resultsLimit + onlyPostsNewerThan
- 输出 32 字段（实测）：facebookUrl, postId, pageName, url, time, timestamp, user{id,name,profileUrl}, text, textReferences, link, likes, comments, shares, topReactionsCount, reactionLikeCount, reactionLoveCount, reactionWowCount, reactionCareCount, reactionHahaCount, isVideo, viewsCount, videoPostViewCount, liveViewerCount, media, feedbackId, paidPartnership, topComments, topLevelUrl, facebookId, pageAdLibrary, inputUrl
- 亮点：**6 种反应分类计数**（like/love/wow/care/haha 等），情感信号比单一点赞数富

### apify/facebook-pages-scraper — 页面资料
- 稳定性：ok 99.9%，输入仅 1 项（startUrls），最简
- 输出 26 字段：title, pageId, pageName, pageUrl, categories, info, intro, likes, followers, messenger, websites, email, phone, address, rating, ratingOverall, ratingCount, creation_date, profilePictureUrl, coverPhotoUrl

### apify/facebook-comments-scraper — 评论主力
- 稳定性：ok **100%**（4012 用户）
- 输入 5 项：post URLs（requestListSources）
- 输出 17 字段：facebookUrl, commentUrl, commentId, id, feedbackId, date, text, profilePicture, profileId, profileName, likesCount, threadingDepth, postTitle
- 亮点：threadingDepth 支持楼中楼层级还原

### apify/facebook-groups-scraper — 小组主力
- 稳定性：ok 99.7%（5027 用户）
- 输入 4 项：startUrls（groups URL）+ resultsLimit + viewOption(CHRONOLOGICAL 等)
- 输出 21 字段（实测）：facebookUrl, url, time, user, text, textReferences, topReactionsCount, reactionLikeCount, likesCount, sharesCount, commentsCount, attachments, groupTitle, feedbackId, id, legacyId, paidPartnership

### curious_coder/facebook-ads-library-scraper — 广告（搜索入口）主力
- 稳定性：ok 99.7%（6593 用户），**FB Ads 类第一**
- 输入 10 项：urls（ads/library 搜索 URL，可带 q= 关键词/国家/活跃状态参数）+ count + scrapeAdDetails + scrapePageAds{period/activeStatus/sortBy/countryCode}
- 输出 37 字段（实测）：ad_archive_id, ad_id, page_id, page_name, page_is_deleted, is_active, snapshot（创意全量：正文/图/视频/CTA）, start_date, end_date, start_date_formatted, end_date_formatted, total_active_time, impressions_with_index, reach_estimate, spend, currency, publisher_platform, targeted_or_reached_countries, categories, gated_type, report_count, has_user_reported, collation_count, ad_library_url
- **spend/reach/impressions 三大投放指标齐全**，竞品广告情报核心字段

### apify/facebook-ads-scraper — 广告（页面入口）主力
- 稳定性：ok 99.4%（7992 用户）
- 输入 10 项：startUrls（**页面 URL**，非广告库 URL）+ resultsLimit + activeStatus + sorting + onlyAdsNewerThan/OlderThan + isDetailsPerAd + enrichWithEcommerceData
- 输出 36 字段（实测）：与 curious_coder 同构：adArchiveID, pageID, pageName, snapshot, isActive, startDateFormatted, endDateFormatted, impressionsWithIndex, reachEstimate, currency, stateMediaRunLabel, gatedType, categories, isAaaEligible + menuItems/pageInfo 等页面上下文

### apify/facebook-marketplace-scraper — Marketplace 主力
- 稳定性：ok 99.4%（935 用户）
- 输入 3 项：startUrls（marketplace 分类/搜索 URL）+ resultsLimit + includeListingDetails
- 输出 25 字段（实测）：facebookUrl, listingUrl, id, primary_listing_photo, listing_price, formatted_price, location, marketplace_listing_title, custom_title, is_sold, is_pending, is_hidden, is_live, min/max_listing_price, comparable_price, delivery_types, marketplace_listing_category_id, listing_video, parent_listing

### apify/facebook-search-scraper — 站内搜索
- 稳定性：ok 99.7%，★4.96（FB 系最高分）
- 输出 23 字段：页面信息卡（title, pageId, pageName, categories, likes, followers, phone, email, website, rating, ratingCount, address, creation_date）
- 定位：按关键词发现页面，产出喂给 posts/pages-scraper 二段接力

## 降级链

1. **帖子**：posts-scraper 失败 → pages-scraper（顺带最新帖+页面全量资料）。
2. **广告**：两主力互为降级（输入形态不同但字段同构，切换只改输入）。
3. **评论**：posts-scraper 的 topComments 内嵌字段（浅，但零额外成本）。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| startUrls 400 | 要 [{url}] 对象数组，不是裸字符串 | requestListSources 形状审计 |
| 广告两 actor 字段命名不同 | curious_coder 蛇形 vs apify 驼峰 | 归一化层做映射表 |
| Marketplace 部分listing is_sold | 已售商品仍返回 | 验收过滤 is_sold=true |
| enrichWithEcommerceData 加价 | 电商增强是付费事件 | 默认关，电商场景单开 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| apify/facebook-posts-scraper / comments / marketplace / ads-scraper | 全部保留，与主力一致 |
| — | 新增建议：facebook-pages-scraper（页面资料缺口）、facebook-groups-scraper（小组缺口）、facebook-search-scraper（发现入口）、curious_coder/facebook-ads-library-scraper（关键词驱动广告） |
