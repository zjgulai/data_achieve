# Apify 采集方案卡 — Reddit

日期：2026-10-14。数据来源同总说明。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 帖子 | ● | harshmaur/reddit-scraper | harshmaur/reddit-scraper-pro | fatihtahta/reddit-scraper-search-fast |
| 评论 | ● | harshmaur/reddit-scraper（dataType=comment） | scraper-pro | — |
| 社区资料 | ● | harshmaur/reddit-scraper（dataType=community） | trudax/reddit-scraper-lite | — |
| 用户资料 | ● | harshmaur/reddit-scraper（dataType=user） | trudax | — |
| 关键词搜索 | ● | fatihtahta/reddit-scraper-search-fast | harshmaur（searches 入口） | — |
| 情绪/内容分析 | ◐ | fatihtahta（sentiment_analysis/content_analysis 开关） | — | — |

**主力更换建议**：项目现有 trudax/reddit-scraper-lite 实测 30 天成功率 **87.2%**，是全部已集成主力里最差的。建议升 harshmaur/reddit-scraper 为主力（97.7%，76 实测字段），trudax 降为社区/用户维度的备用。

## 主力 actor 详情

### harshmaur/reddit-scraper — 一体化主力
- 稳定性：ok 97.7%（3807 用户）
- 输入 42 项：searches[] + startUrls + maxItems + maxComments + postDateLimit/commentDateLimit + sort/time + includeNSFW + includeMediaLinks
- 输出 **76 字段（实测全场最多）**，一条记录按 dataType 分四类：
  - 公共：id, parsedId, title, body, bodyHtml, contentUrl, postUrl, createdAt, crawledAt, dataType, searchTerm, url 类
  - 帖子：postType, flair, images, upVotes, score, upvoteRatio, commentsCount, over18, isSelf, isVideo, isGallery, spoiler, locked, archived, pinned, stickied, edited, editedAt, distinguished, isOriginalContent, numCrossposts, totalAwardsReceived, gilded, domain, thumbnail, media, secureMedia, mediaMetadata, galleryData, galleryImages, mediaAssets, galleryCount, videoUrl, mediaType, hasMedia, removedByCategory, removedBy, bannedBy, removalReason, isRobotIndexable, subredditSubscribers
  - 互动增强（该 actor 特有预计算）：ageHours, scorePerHour, commentsPerHour, engagementTotal, commentToScoreRatio, isHighEngagement, titleLength, bodyLength, wordCount, outboundUrlHost
  - 作者/社区：authorId, authorName, authorFlairText, authorPremium, communityName, communityId, parsedCommunityName/Subreddit
- **engagementTotal/scorePerHour 等预计算字段**直接可做热度排序，省一层后处理

### harshmaur/reddit-scraper-pro — 降级①
- 稳定性：ok 98.7%（400 用户）
- 定位：同厂付费增强版，成功率更高但 README 示例字段少（11），实际与主力同构。量大要稳时切换。

### fatihtahta/reddit-scraper-search-fast — 搜索降级②
- 稳定性：ok 98.7%（2877 用户）
- 输入 23 项：queries[] + sort + timeframe + dateFrom/dateTo + maxPosts + scrapeComments + **sentiment_analysis + content_analysis**（内置情绪分析开关）
- 输出 21 字段：帖子+评论，含 subReddit/subredditName 过滤
- 定位：舆情监测场景——按关键词+时间窗+情绪分析一次出结果

### trudax/reddit-scraper-lite — 现有端点，降级为备用
- 稳定性：ok **87.2%**（7593 用户，量最大但失败率最高）
- 输出 38 字段：id, parsedId, url, username, userId, title, communityName, body, html, numberOfComments, upVotes, upVoteRatio, authorFlair, isVideo, isAd, over18, imageUrls, videoUrls, createdAt, scrapedAt, dataType
- 保留理由：便宜、社区/用户维度有输出；但 87% 成功率不配主力。

## 降级链

1. **帖子/评论**：harshmaur → harshmaur-pro → fatihtahta（搜索入口）。
2. **搜索**：fatihtahta → harshmaur（searches 入口）。
3. **社区/用户**：harshmaur dataType 分支 → trudax（保底，接受重试）。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| trudax 87% 成功率 | 上游 Reddit 限流策略变化 | 换 harshmaur 主力；trudax 调用处加重试 |
| harshmaur 一次 run 出四类记录 | dataType 混在一起 | 验收按 dataType 分流到不同表 |
| body 与 bodyHtml 双字段 | 同内容两格式 | 归一化取一，另一存原文 |
| 时间过滤不生效感 | postDateLimit 是 ISO 日期 | 演示参数用真实近期日期 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| trudax/reddit-scraper-lite（已集成） | **降级为备用**，建议 A/B 后正式换 harshmaur |
| — | 新增建议：harshmaur/reddit-scraper（新主力）、fatihtahta/reddit-scraper-search-fast（舆情搜索+情绪分析缺口） |
