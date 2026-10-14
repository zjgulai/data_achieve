# Apify 采集方案卡 — Instagram

日期：2026-10-14。数据来源同总说明。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 帖子 | ● | apify/instagram-post-scraper | apify/instagram-scraper（directUrls 兜底） | — |
| Reels | ● | apify/instagram-reel-scraper | apify/instagram-scraper | — |
| 账号资料 | ● | apify/instagram-profile-scraper | apify/instagram-scraper（profiles 模式） | — |
| 话题 | ● | apify/instagram-hashtag-scraper | apify/instagram-scraper（hashtag 模式） | — |
| 评论 | ● | apify/instagram-comment-scraper | post-scraper（latestComments/firstComment 字段） | — |
| 站内搜索 | ● | apify/instagram-scraper（search 模式） | — | — |

要点：官方全家桶（apify/*）全平台覆盖率第一（49641 用户/30 天，全场最高）。**apify/instagram-scraper 是万能兜底**：resultsType + directUrls 两个参数可替代全部专项 actor，任何专项失败都降级到它。

## 主力 actor 详情

### apify/instagram-scraper — 全能兜底
- 稳定性：ok 99.6%，**49641 用户/30 天（Apify 全店第一）**
- 计费：result $0.0027/条
- 输入 8 项：resultsType(posts/profiles/hashtag/search) + directUrls + search/searchType/searchLimit + resultsLimit + onlyPostsNewerThan + addParentData
- 输出 24 字段（README/实测）：inputUrl, id, type, shortCode, caption, hashtags, mentions, url, commentsCount, firstComment, latestComments, dimensionsHeight/Width, displayUrl, images, alt, likesCount, timestamp, childPosts, ownerFullName, ownerUsername, ownerId, isCommentsDisabled

### apify/instagram-post-scraper — 帖子主力
- 稳定性：ok 99.9%
- 输入 6 项：username（stringList，可放 URL）+ resultsLimit + skipPinnedPosts + includeMusicData + onlyPostsNewerThan + dataDetailLevel(basicData/fullData)
- 输出 37 字段（实测）：id, type, shortCode, caption, hashtags, mentions, url, commentsCount, firstComment, latestComments, dimensionsHeight/Width, displayUrl, images, videoUrl, likesCount, videoViewCount, videoPlayCount, timestamp, childPosts, ownerFullName, ownerUsername, ownerId, productType, paidPartnership, sponsors, taggedUsers, isPinned, coauthorProducers, isCommentsDisabled, originalHeight/Width, audioUrl, alt, videoDuration, musicInfo, inputUrl
- **sponsors/taggedUsers/coauthorProducers** 是商业合作情报字段

### apify/instagram-reel-scraper — Reels 主力
- 稳定性：ok 99.9%（18194 用户）
- 输入 8 项：username + resultsLimit + onlyPostsNewerThan + skipPinnedPosts + skipTrialReels + includeSharesCount + includeTranscript + includeDownloadedVideo
- 输出 34 字段（实测）：帖子字段同构 + videoDuration, videoPlayCount, audioUrl, musicInfo + 可选 transcript/downloadedVideo

### apify/instagram-profile-scraper — 账号主力
- 稳定性：ok 99.7%（32501 用户）
- 输入 2 项：usernames + resultsLimit
- 输出 21 字段（实测）：inputUrl, id, username, url, fullName, biography, externalUrls, externalUrl, followersCount, followsCount, postsCount, isBusinessAccount, businessCategoryName, private, verified, profilePicUrl, profilePicUrlHD, latestIgtvVideos, latestPosts, fbid
- **latestPosts 内嵌最新帖子**，账号监控一次 run 出资料+近期内容

### apify/instagram-hashtag-scraper — 话题主力
- 稳定性：ok 99.5%（13226 用户；★3.49 偏低但成功率达标——低分主要是价格抱怨）
- 输入 4 项：hashtags + resultsType(top/recent) + resultsLimit
- 输出 30 字段（实测）：帖子字段同构 + productType, paidPartnership, musicInfo, childPosts

### apify/instagram-comment-scraper — 评论主力
- 稳定性：ok 99.9%（6504 用户）
- 输入 3 项：startUrls（帖子 URL）
- 输出 8 字段（实测）：id, text, ownerUsername, ownerProfilePicUrl, timestamp, likesCount, repliesCount, replies[]
- 字段最少但评论核心五件套齐（正文/作者/时间/点赞/回复数）

## 降级链

1. **全部主题**：专项 actor → instagram-scraper 换 resultsType。输入形状不同（directUrls vs usernames/hashtags），配置映射写死在端点默认值里。
2. **评论**：comment-scraper → post-scraper 的 latestComments（内嵌，每帖限量）。
3. **注意**：apify/instagram-comments-scraper（复数）已 404 下架，正确名是 instagram-comment-scraper（单数）——接入时用单数。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| post/reel-scraper 400 "username required" | 必填键是 username，不是 directUrls | 审计按各自 schema |
| hashtag ★3.49 | 价格抱怨非质量问题 | 只看成功率即可 |
| comments-scraper 字段少 | 评论轻量化设计 | 需评论者档案时二段接力 profile-scraper |
| dataDetailLevel 默认 basicData | fullData 才出全字段 | 需要深字段时显式开 fullData |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| apify/instagram-scraper / instagram-profile-scraper | 保留，与主力一致 |
| — | 新增建议：instagram-post-scraper、instagram-reel-scraper、instagram-hashtag-scraper、instagram-comment-scraper（四个专项维度全部缺失，现只靠万能入口） |
