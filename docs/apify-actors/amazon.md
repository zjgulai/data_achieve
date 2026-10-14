# Apify 采集方案卡 — Amazon

日期：2026-10-14。数据来源同总说明。

> **平台级风险提示**：Amazon 是十个平台里反爬最强、成功率天花板最低的。商品类最好主力也只有 92.8%，没有 ≥98% 的选项。策略是"主力+强制重试+监控告警"，而非追求一次成功率。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 商品详情/批量爬取 | ● | junglee/amazon-crawler | junglee/free-amazon-product-scraper | apify/rag-web-browser（页面正文兜底） |
| 评论 | ● | axesso_data/amazon-reviews-scraper | ~~web_wanderer/amazon-reviews-extractor~~（2026-10-15 实测恒 0 条：Amazon 封禁其抓取端点，run SUCCEEDED 是假象） | junglee/amazon-reviews-scraper |
| 榜单（Best Sellers） | ● | junglee/amazon-bestsellers | junglee/amazon-crawler（分类页 URL） | — |
| 竞品研究 | ◐ | samstorm/amazon-competitor-research-scraper | junglee/amazon-crawler 多关键词 | — |
| BSR 追踪 | ◐ | ~~marketplace-scrapers/amazon-bsr-scraper~~（已从 Store 下架） | junglee/amazon-bestsellers（position 字段） | — |

**下架警示**：项目现有端点引用的 marketplace-scrapers/amazon-bsr-scraper 已无 Store 页（API 仍可调但随时会停），BSR 追踪改用 amazon-bestsellers 的 position 字段，并标记旧端点 deprecated。

## 主力 actor 详情

### junglee/amazon-crawler — 商品主力
- 稳定性：ok 92.8%（3190 用户）——**接受现状，配重试**
- 计费：result $0.005/条（商品类最贵），offer/seller 事件 $0.0025
- 输入 14 项：关键词/分类/ASIN 列表 + maxItems + depthOfCrawl + detailedInformation + useCaptchaSolver
- 输出 41 字段：title, url, asin, brand, price, value, currency, listPrice, shippingPrice, inStock, inStockText, stars, starsBreakdown, 5star~1star 分布, reviewsCount, soldBy, sellerInfo, features, description, images, categories, rank, badge, coupon 等促销字段
- 亮点：starsBreakdown 五档评分分布 + coupon/促销标记

### axesso_data/amazon-reviews-scraper — 评论主力
- 稳定性：ok **99.9%**（Amazon 类最稳）
- 输入 1 项：input（json 数组 [{asin, domainCode, sortBy, maxPages}]）——**json 编辑器形状，审计要按对象数组校验**
- 输出 27 字段（实测）：statusCode, statusMessage, asin, productTitle, currentPage, sortStrategy, countReviews, countRatings, productRating, reviewSummary（分档统计）, reviewId, text, date, rating, title, userName, numberOfHelpful, variationId, imageUrlList, variationList, locale, verified, vine, videoUrlList, profilePath, domainCode, filters
- 亮点：reviewSummary 服务端预聚合 + verified/vine 标记 + 99.9% 成功率，评论类唯一首选

### junglee/amazon-bestsellers — 榜单主力
- 稳定性：ok 91.8%
- 输入 6 项：categoryUrls（zgbs 分类链接）+ maxItemsPerStartUrl + depthOfCrawl + detailedInformation
- 输出 14 字段（实测）：name, url, asin, position（**榜单排名**）, price, numberOfOffers, stars, reviewsCount, thumbnailUrl, categoryName, categoryFullName, subcategories, categoryUrl, input
- position + categoryFullName 树即 BSR 追踪数据源

### junglee/free-amazon-product-scraper — 商品降级
- 稳定性：ok 87.5%（免费额度），41 字段与主力同构
- 定位：主力连续失败时的应急通道，量大不推荐（免费版限流）

## 降级链

1. **商品**：crawler 失败 → free-product-scraper → rag-web-browser 抓商品页正文（丢结构化，保标题/价格正则提取）。
2. **评论**：axesso → junglee/amazon-reviews-scraper（96.2%）。web_wanderer 已失效（2026-10-15 实测恒 0 条，Amazon 封禁其端点；教训：SUCCEEDED ≠ 有数据，评论类验收必须看 records_count）。
3. **BSR**：下架的 bsr-scraper → bestsellers.position → crawler 的 rank 字段。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| 商品类 85-93% 成功率 | Amazon 反爬（验证码/封 IP） | max_total_charge 里预算重试 2-3 次；useCaptchaSolver 开 |
| axesso input 400 | input 是对象数组不是平铺参数 | json 编辑器形状审计 |
| junglee 系多 actor 字段重叠 | 同一家的产品线 | 只接 crawler+reviews+bestsellers 三个，不重复接入 |
| bsr-scraper 静默停摆 | Store 下架无通知 | 接入清单加「Store 页存在性」月检 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| junglee/amazon-crawler / amazon-bestsellers / amazon-reviews-scraper | 保留；reviews 建议降为第三降级，主力换 axesso |
| marketplace-scrapers/amazon-bsr-scraper | **标记 deprecated**，BSR 改走 bestsellers.position |
| samstorm/amazon-competitor-research-scraper | 84.8%，保留但仅作竞品研究专项 |
| — | 新增建议：axesso_data/amazon-reviews-scraper（评论主力）、web_wanderer/amazon-reviews-extractor（评论降级）、junglee/free-amazon-product-scraper（应急） |
