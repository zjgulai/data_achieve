# Apify 采集方案卡 — Shopify

日期：2026-10-14。数据来源同总说明。

> **平台特性**：Shopify 店铺全部暴露公开 JSON 端点（`/products.json`），所以这是十个平台里唯一有"零成本降级"的——不用任何 actor 也能拿商品目录。Apify actor 的价值在增强字段（库存/推荐/跨店线索库）和批量调度。

## 主题矩阵

| 主题 | 覆盖 | 主力 | 降级① | 降级② |
|---|---|---|---|---|
| 店铺商品目录 | ● | trovevault/shopify-products-scraper | autofacts/shopify | 直连 /products.json（零成本） |
| 跨店线索库（按品类/国家找店） | ● | ecommerce_leads/store-leads-14m-e-commerce-leads | clearpath/shopify-store-leads | xmiso_scrapers/shopify-shops-email-leads-scraper |
| 店铺邮箱线索 | ◐ | xmiso_scrapers/shopify-shops-email-leads-scraper | store-leads（emails 字段） | — |
| 商品监控/库存 | ◐ | trovevault（includeInventoryDetails） | autofacts（grabRealInventory） | 直连 /products.json 轮询 |

## 主力 actor 详情

### trovevault/shopify-products-scraper — 目录主力
- 稳定性：ok 99.0%
- 计费：$0.001/条 + $0.001/run（便宜档），inventory-enrichment $0.001
- 输入 6 项：domains（店铺域名列表）+ maxProducts + includeInventoryDetails
- 输出 31 字段（实测）：store, productId, handle, vendor, title, url, featuredImage, imageUrls, imageCount, imageAltTexts, images, currency, priceMin, priceMax, compareAtPrice, onSale, available, fullyOutOfStock, requiresShipping, weightAndUnit, variantCount, variants[], options, productOptions, productType, tags, description, descriptionHtml, createdAt, publishedAt, updatedAt
- 价格区间/对比价/上架时间/库存标记齐全，竞品目录监控首选

### ecommerce_leads/store-leads-14m-e-commerce-leads — 线索库主力
- 稳定性：ok **100%**，★5.0
- 输入 16 项：category/country/platform 过滤 + 关键词
- 输出 22 字段：platform, domain, merchant, category, categories, country, region, city, emails, phones, instagram, facebook, tiktok, youtube, linkedin, twitter, pinterest
- **1400 万店铺库**：按品类/国家检索已建索引的店铺名单，一次查询出整批线索，不用逐店爬

### clearpath/shopify-store-leads — 线索降级（项目已集成）
- 稳定性：ok 99.5%
- 输出 51 字段：id, name, websiteUrl, myshopifyDomain, shareUrl, address1/2, city, zone, country, + 产品面过滤（category/query/priceMin/priceMax/inStock）
- 与 store-leads 互补：clearpath 偏"当前在售商品"过滤，ecommerce_leads 偏"存量库检索"

### autofacts/shopify — 目录降级
- 稳定性：ok 93.8%
- 输入 12 项：startUrls（collection 页也行）+ query + grabRealInventory + grabStorefrontDetail + grabContentSections + maxRecommendationsPerProduct
- 输出 12 字段：source, title, description, brand, categories, tags, variants, medias, options, price, priceRange, fullyOutOfStock
- 特色：**商品推荐图谱**（maxRecommendationsPerProduct）——拿"买了此商品还看什么"数据

### xmiso_scrapers/shopify-shops-email-leads-scraper — 邮箱线索
- 稳定性：ok 100%（17 用户，规模小）
- 输出 9 字段：id, shop_name, domain_name, language, currency, email, phone, description, published_date
- 定位：只要邮箱/电话的轻量通道

## 零成本降级（独有）

直连 `https://{store}/products.json?limit=250&page=N`：
- 返回官方结构化商品 JSON（title/handle/variants/ images/tags）
- 字段比 actor 少（无库存聚合/对比价），但零费用、零依赖
- 项目现有 `apify_shopify_full_catalog` 端点的输入源可保留 actor 增强层，底层换直连作为 ②

## 降级链

1. **目录**：trovevault → autofacts → /products.json 直连（脚本化，不需要 Apify 配额）。
2. **线索**：ecommerce_leads（存量库）→ clearpath（在售过滤）→ xmiso（纯邮箱）。

## 坑点

| 症状 | 原因 | 规避 |
|---|---|---|
| autofacts 93.8% | 部分店铺禁爬 | 降级链兜底 |
| /products.json 分页 250 上限 | Shopify 平台限制 | page 参数循环 |
| variants 嵌套价格 | priceMin/Max 是聚合，单价在 variants[] | 归一化拆层 |
| store-leads 库是快照 | 新店可能不在库 | 新店发现补 xmiso 搜索模式 |

## 与现有 catalog 对照

| 现有端点 | 本卡结论 |
|---|---|
| trovevault/shopify-products-scraper / clearpath/shopify-store-leads | 保留，与主力一致 |
| — | 新增建议：ecommerce_leads/store-leads-14m（跨店线索库缺口）、autofacts/shopify（推荐图谱）；考虑 /products.json 直连通道固化成端点 |
