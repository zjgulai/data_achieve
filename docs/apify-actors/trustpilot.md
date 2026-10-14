# Apify 采集方案卡 — Trustpilot

日期：2026-10-14。数据来源同总说明。

> **平台特性**：生态最薄的十个平台之一——Store 搜索"trustpilot"只有 3 个可用候选，且主力月活只有 668。方案卡的重点是超时预算和兜底设计。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 企业评论 | ● | memo23/trustpilot-scraper-ppe | saswave/storeleads-scraper | apify/rag-web-browser（正文兜底） |
| 企业信息卡 | ◐ | memo23（businessName/businessUnitId/businessUrl 字段） | saswave（店铺档案字段） | — |
| 评论情绪分析 | ◐ | memo23（reviewInsights/painPointAnalysis 开关） | — | — |

## 主力 actor 详情

### memo23/trustpilot-scraper-ppe — 评论主力（项目已集成）
- 稳定性：ok 97.7%（668 用户），★4.8
- 计费：$0.0029/条 + actor-start $0.005 + additional-data $0.001
- 输入 32 项：startUrls（企业评论页 URL/企业名/用户页均收）+ searchTerms + scrapeAllReviews + reviewInsights + painPointAnalysis + enrichEmails + filterStars + filterLanguages + sampling
- 输出 37 字段（实测）：id, title, text, rating, language, source, isVerified, verificationLevel, status, numberOfLikes, filtered, isPending, dates{publishedDate, updatedDate, experiencedDate}, consumer{name, country, numberOfReviews}, reviewerName, reviewerCountry, reviewerNumberOfReviews, reply{企业回复}, report, hasUnhandledReports, consumersReviewCountOnSameDomain/Location, productReviews, location, url, businessUrl, businessName, businessUnitId, scrapedAt, _raw
- 亮点：isVerified/verificationLevel 认证评论标记 + reply 企业回复 + experiencedDate 消费时间线
- **超时预算：600s 起**（实测全量跑一次 5 分钟+；与项目 aliens_eye 慢端点教训同款，缺省超时要给足）

### saswave/storeleads-scraper — 降级①
- 稳定性：ok 85.7%（11 用户）——**仅作降级，勿当主力**
- 输出 50 字段：偏店铺档案（Storeleads 数据库视角），评论字段是附属
- 定位：memo23 挂掉时拿企业卡+部分评论

### apify/rag-web-browser — 降级②（通用兜底）
- 稳定性：ok 98.8%（31634 用户）
- 输出 4 字段：crawl, metadata, query, markdown
- 定位：结构化全挂时抓评论页 markdown，正则提星级/日期。丢结构保正文。

## 降级链

1. memo23 → saswave（结构化但有 85.7% 风险）→ rag-web-browser（98.8% 但非结构化）。
2. 大批量场景给 memo23 配「分批 + 断点续跑」：每次 run 限 1-2 个企业，失败单企重跑，避免整批超时。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| run 408 超时 | 全量评论页跑 5 分钟+ | run_timeout 给 600s+；或 scrapeAllReviews=false + sampling=first |
| _raw 字段巨大 | 原始 HTML 塞在记录里 | 落库前剥 _raw，省存储 |
| startUrls 收企业名也能跑 | 隐式解析 | 统一传完整评论页 URL，可复现 |
| filterLanguages 非空时 0 条 | 语言码格式敏感 | 默认空数组收全量，事后按 language 字段过滤 |

## 成本

每千条评论 $2.9 + 启动费。带 reviewInsights/painPointAnalysis 时加 additional-data $0.001/条。

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| memo23/trustpilot-scraper-ppe（已集成） | 保留主力；**补 600s 超时预算**（对齐 aliens_eye 修复模式） |
| — | 新增建议：无（生态里没有更好的第三方案；rag-web-browser 已有通用端点可复用） |
