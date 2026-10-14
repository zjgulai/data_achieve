# Apify Actor 采集方案卡

每平台一份方案卡：主题矩阵、主力 + 2 个降级、字段表（实测）、定价、坑点、与现有 catalog 对照。

| 平台 | 卡 | 主力速查 |
|---|---|---|
| TikTok | [tiktok.md](tiktok.md) | clockworks 全家桶（帖子/账号/评论/话题/字幕）+ pratikdani Shop 双子 + lexis 广告 |
| X(Twitter) | [x-twitter.md](x-twitter.md) | apidojo/tweet-scraper + twitter-user-scraper |
| LinkedIn | [linkedin.md](linkedin.md) | harvestapi（档案/搜索/公司帖）+ apimaestro（员工/个人帖）+ curious_coder jobs |
| Google | [google.md](google.md) + [rag-web-fallback.md](rag-web-fallback.md) | apify SERP + compass Maps 双子 + data_xplorer Trends/News |
| Facebook | [facebook.md](facebook.md) | apify 官方系（posts/pages/comments/groups/marketplace）+ curious_coder 广告库 |
| Amazon | [amazon.md](amazon.md) | junglee 商品/榜单 + axesso 评论（92.8% 天花板平台，重试策略） |
| Instagram | [instagram.md](instagram.md) | apify 官方全家桶 + instagram-scraper 万能兜底 |
| Shopify | [shopify.md](shopify.md) | trovevault 目录 + ecommerce_leads 线索库 + /products.json 零成本降级 |
| Trustpilot | [trustpilot.md](trustpilot.md) | memo23/trustpilot-scraper-ppe（唯一主力，600s 超时） |
| Reddit | [reddit.md](reddit.md) | harshmaur/reddit-scraper（76 字段，建议替换 trudax 87%） |

## 总纲

研究方案与跨平台结论见 `reports/apify-deep-research/RESEARCH-PLAN.md`。原始数据（74 actor 元数据、29+ actor 实测字段、定价）在同目录 `actors_p*.jsonl` / `live_output_fields.json`。

## 数据口径

- 成功率 = Store API `publicActorRunStats30Days` 的 SUCCEEDED/TOTAL（30 天滚动）
- 字段表 = 真实试跑实测优先，README 样例挖掘补位；标注「实测」的均为本项目跑通验证
- 定价 = Store API `currentPricingInfo`；PAY_PER_EVENT 按事件单价，FLAT 按月租
- 采集日：2026-10-14。建议每季度刷新一次（Store 排名与定价会变）

## 接入新 actor 的固定动作

1. 对照方案卡确认该 actor 在主力/降级位的分工。
2. 按 `builds/default` 的 inputSchema 核对输入形状（stringList / requestListSources / json 对象数组三大坑）。
3. 跑一次最小实测（≤5 条），确认输出字段与卡内一致。
4. quick_collect 默认参数表登记 + `max_total_charge_usd` + `run_timeout_seconds` 护栏。
5. 坑点回填本卡，更新《能力总账》。
