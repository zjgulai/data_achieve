# Apify 采集方案卡 — X(Twitter)

日期：2026-10-14。数据来源同总说明（Store API 30 天实测 + 本项目真实试跑）。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 推文（搜索/用户/会话/URL） | ● | apidojo/tweet-scraper | kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest | apidojo/twitter-scraper-lite |
| 用户资料 | ● | apidojo/twitter-user-scraper | danek/twitter-scraper | tweet-scraper（twitterHandles 入口） |
| 用户关系（粉丝/关注） | ◐ | twitter-user-scraper（getFollowers/getFollowing 开关） | — | — |
| 媒体/视频明细 | ● | tweet-scraper（extendedEntities/media/videos） | twitter-scraper-lite | — |

## 主力 actor 详情

### apidojo/tweet-scraper — 推文主力
- 稳定性：ok 98.1%，30 天用户 8.7k（X 平台用户量最大）
- 计费：$0.0004/条（apify-default-dataset-item）
- 输入（26 项，无必填但四入口至少一个）：searchTerms（支持高级操作符 lang: from: since:）、twitterHandles、conversationIds、startUrls；maxItems、sort(Latest/Top)、tweetLanguage、onlyVerifiedUsers、onlyImage/onlyVideo 等过滤
- 输出 30 字段（实测）：type, id, url, twitterUrl, text, fullText, source, retweetCount, replyCount, likeCount, quoteCount, viewCount, createdAt, lang, bookmarkCount, isReply, inReplyToId, conversationId, inReplyToUserId, inReplyToUsername, author(对象：完整用户卡), extendedEntities, card, place, entities(hashtags/urls/mentions), isRetweet, isQuote, media, videos, isConversationControlled
- 亮点：viewCount/bookmarkCount 是 X 特有互动指标，多数竞品缺

### apidojo/twitter-user-scraper — 用户主力
- 稳定性：ok 99.5%，用户 1.1k
- 输入（15 项）：twitterHandles/startUrls；getFollowers、getFollowing、getRetweeters 开关；maxItems
- 输出 35 字段（实测）：userName, id, name, isVerified, profilePicture, coverPicture, description, location, followers, following, statusesCount, mediaCount, favouritesCount, createdAt, protected, canDm, pinnedTweetIds, entities + 一批 X 内部状态位（advertiserAccountType/fastFollowersCount 等）
- 计费注意：开 getFollowers 后按粉丝条数计费，量大先设 maxItems

## 降级链

1. **kaitoeasyapi/...-cheapest**：$0.00025/条（比主力便宜 37%），ok 98.8%，用户 7k。字段 25 个略少。量大、字段要求低的场景直接用它当主力更省。
2. **apidojo/twitter-scraper-lite**：ok 99.9%（本平台最高），字段 18 个（核心计数+文本），输入 8 项最简单。最稳但最浅。
3. **danek/twitter-scraper**：ok 100%，字段 18，但月活仅 474——单人维护风险，只作第三降级。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| searchTerms 高级操作符被静默忽略 | 各 actor 支持度不一 | 上线前用 `from:x` 查询实测确认生效 |
| 粉丝列表跑量大 | getFollowers 展开后按条计费 | 先关开关跑资料，需要时单开 |
| kaitoeasyapi 名字含 filter: 前缀字段 | README 里是搜索操作符文档，不是字段 | 解析按实测字段表，勿抄 README |

## 成本对比（每 1 万条推文）

| actor | 单价 | 1 万条成本 |
|---|---|---|
| kaitoeasyapi cheapest | $0.00025 | $2.5 |
| apidojo/tweet-scraper | $0.0004 | $4.0 |
| twitter-scraper-lite | 更低 | 视事件表 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| quick_collect 已含 apidojo/tweet-scraper | 保留为主力，与本卡一致 |
| — | 新增建议：kaitoeasyapi（成本降级通道）、twitter-user-scraper（用户维度缺口） |
