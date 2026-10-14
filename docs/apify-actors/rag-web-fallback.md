# Google 平台补卡 — 通用网页兜底与跨境电商补充

本文是 google.md 的附属说明：Google 平台的"主题"除 SERP/Maps/Trends/News/Ads 外，还有一类"以 Google 为入口的通用网页抓取"，由 rag-web-browser 承担。它在多个平台的降级链里出现（Trustpilot②、Amazon②、Shopify 思路参考），统一说明一次。

## apify/rag-web-browser — 通用兜底

- 稳定性：ok 98.8%，**31634 用户（全店第一梯队）**
- 计费：按结果计
- 输入 15 项：query（搜索词或 URL 列表）+ maxResults + 抓取深度/缓存/格式配置
- 输出 4 字段（实测）：crawl（抓取结果）, metadata, query, markdown
- 定位：**任何结构化 actor 全挂时的通用兜底**——丢结构保正文。项目现有端点已集成。

## 使用原则

1. 只做降级②，不做主力——markdown 输出没有 schema，验收和归一化成本高。
2. 调用处统一走"正则提取关键要素（标题/价格/日期/星级）"的约定解析器，避免每个平台各写一套。
3. 配额预算按 1 次 run = 1 页面估算，别当批量爬虫用。
