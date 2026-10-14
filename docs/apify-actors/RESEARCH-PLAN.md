# Apify Store 十平台深度研究方案（讨论稿）

日期：2026-10-14
状态：草案，待确认后执行全量
目标平台：Google、LinkedIn、TikTok、Shopify、Facebook、Amazon、Instagram、X(Twitter)、Trustpilot、Reddit

---

## 1. 研究目标

对每个平台回答四个问题：

1. 能取哪些主题数据（帖子、评论、广告、商品、评论、榜单……）。
2. 每个主题有哪些字段。字段名、类型、含义。
3. 用哪些 actor 取。每个 actor 覆盖哪些字段。
4. 主力方案 1 个 + 降级方案 2 个。依据是完整性和稳定性。

产出物：

- 每平台一份《采集方案卡》：主题矩阵、字段表、actor 分工、降级链、成本。
- 总账一份：跨平台规律、风险清单、接入 TODO。

## 2. 证据源（不是拍脑袋）

| 证据 | 来源 | 说明 |
|---|---|---|
| 30 天真实成功率 | Store API `publicActorRunStats30Days` | SUCCEEDED/TOTAL，非官方宣传值 |
| 30 天活跃用户数 | Store API `totalUsers30Days` | 生态规模代理指标 |
| 评分与评论数 | Store API | 质量参考 |
| 输入 schema | `GET /v2/acts/{actor}/builds/default`（免费匿名） | 全部 74 个 actor 已抓取 |
| 输出字段 | 两条路：README 样例挖掘 + 真实试跑 | 29 个 actor 已实测验证 |
| 定价 | Store API `currentPricingInfo` | 按事件计费的单价已逐个抓取 |

已抓数据落盘在 `reports/apify-deep-research/`：

- `actors_p1/p2/p3.jsonl` — 74 个 actor 的完整元数据（stats、pricing、input schema、readme）
- `sample_runs*.jsonl` — 5 批真实试跑记录
- `live_output_fields.json` — 29 个 actor 的实测输出字段表

## 3. 评估框架

**完整性**（每主题打分 0-3）：
- 3 = 字段覆盖该主题核心要素（正文 + 互动计数 + 作者 + 时间 + 媒体/附加对象）
- 2 = 有正文和计数，缺附属对象
- 1 = 只有 ID 或链接
- 0 = 取不到该主题

**稳定性**（硬门槛）：
- ≥98% 成功率：可当主力
- 93-98%：可当主力，需配重试
- <93%：只当降级，或必须配监控
- 输入含 cookie/登录态：一律降权（会话失效 = 批量失败）

**成本**：PAY_PER_EVENT 单价 × 预估量。单价区间 $0.00025-$0.005/条。

**接入成本**：输入形状（stringList / requestListSources / json object）已在 schema 里核实，接入前可离线审计（复用 `scripts/audit_apify_inputs.py` 的方法）。

## 4. 十平台方案总表（按已抓数据初排）

> ★ = 主力，①② = 降级。ok% 为 30 天实测。字段数为实测或 README 挖掘数。

### 4.1 TikTok（生态最成熟，13 个候选全部 ≥96%）

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 视频/搜索/账号一体的帖子 | ★ | clockworks/tiktok-scraper | 98.9 | 29 |
| 帖子（降级） | ① | clockworks/free-tiktok-scraper | 99.2 | 19 |
| 帖子（降级2） | ② | apidojo/tiktok-scraper | 96.0 | 1（空结果形状） |
| 账号深挖 | ★ | clockworks/tiktok-profile-scraper | 99.2 | 31 |
| 评论 | ★ | clockworks/tiktok-comments-scraper | 99.7 | 16 |
| 评论（降级） | ① | 主力 actor 的 commentsPerPost 参数 | — | 0 参数加挂 |
| 话题 | ★ | clockworks/tiktok-hashtag-scraper | 99.8 | 30 |
| 字幕 | ★ | clockworks/tiktok-transcript-extractor | 99.3 | 2 |
| Shop 商品详情 | ★ | pratikdani/tiktok-shop-scraper | 100 | 54（含 GMV30d/佣金） |
| Shop 商品搜索 | ★ | pratikdani/tiktok-shop-search-scraper | 99.9 | 48 |
| Shop（降级） | ① | clockworks/tiktok-shop-scraper | 97.1 | 26 |
| Shop 达人 | ② | lemur/tiktok-shop-creators | 92.8 | 27 |
| 广告 | ★ | lexis-solutions/tiktok-ads-scraper | 98.1 | 31 |
| Creative Center 趋势 | ★ | doliz/tiktok-creative-center-scraper | 99.8 | 4（信封形 code/msg/data） |

要点：clockworks 全家桶一家覆盖帖子/账号/评论/话题/字幕，输入形状一致，维护成本最低。TikTok Shop 字段最富（54 字段，含 gmv_30d、commission、sell_7d）。

### 4.2 X(Twitter)

| 主题 | 主力/降级 | actor | ok% | 实测字段 | 单价 |
|---|---|---|---|---|---|
| 推文搜索/用户/会话 | ★ | apidojo/tweet-scraper | 98.1 | 30 | $0.0004/条 |
| 推文（降级，最便宜） | ① | kaitoeasyapi/twitter-x-data-...-cheapest | 98.8 | 25 | $0.00025/条 |
| 推文（降级2） | ② | apidojo/twitter-scraper-lite | 99.9 | 4 | 更低单价、字段少 |
| 用户资料 | ★ | apidojo/twitter-user-scraper | 99.5 | 4 | — |
| 全功能备选 | ② | danek/twitter-scraper | 100 | 18 | 用户少（474） |

要点：tweet-scraper 一个入口覆盖搜索/用户/会话/URL 四种输入。单价差 1.6 倍，量大时 kaitoeasyapi 省钱但字段略少。

### 4.3 LinkedIn

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 档案 | ★ | harvestapi/linkedin-profile-scraper | 100 | 53（含技能/经历/教育） |
| 档案搜索 | ★ | harvestapi/linkedin-profile-search | 99.6 | 3（41 个输入过滤项） |
| 公司员工 | ★ | apimaestro/linkedin-company-employees-scraper-no-cookies | 99.9 | 20 |
| 员工（降级） | ① | curious_coder/linkedin-jobs-scraper 不覆盖，改用 apimaestro 失败后走 harvestapi 搜索 | — | — |
| 职位 | ★ | curious_coder/linkedin-jobs-scraper | 98.7 | 25 |
| 职位（降级） | ① | bebity/linkedin-jobs-scraper | 99.1 | — |
| 公司帖子 | ★ | harvestapi/linkedin-company-posts | 100 | 42 |

要点：**淘汰 curious_coder/linkedin-profile-scraper**——输入强制要 cookie + userAgent，会话失效即批量失败，且月活仅 13。harvestapi 系全部免 cookie。带邮箱版本单价 $10/1k（不带 $4/1k），按需选。

### 4.4 Google

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| SERP（含 PAA/AI Overview） | ★ | apify/google-search-scraper | 98.4 | 15 |
| SERP（降级） | ① | scraperlink/google-search-results-serp-scraper | 99.9 | 8 |
| SERP（降级2） | ② | apify/rag-web-browser（要正文不要 SERP 时） | 98.8 | 4 |
| Maps 商户 | ★ | compass/crawler-google-places | 97.0 | 39 输入项 |
| Maps 商户（降级） | ① | compass/google-maps-extractor | 96.2 | 7 |
| Maps 商户（降级2） | ② | lukaskrivka/google-maps-with-contact-details | 93.7 | 带邮箱增强 |
| Maps 评论 | ★ | compass/Google-Maps-Reviews-Scraper | 99.7 | 试跑 0 条（需精确 place URL，待复测） |
| Trends | ★ | data_xplorer/google-trends-fast-scraper | 99.5 | 7 |
| Trends（弃用） | ✗ | apify/google-trends-scraper | **56.6** | 官方榜出品但实测近半失败，直接排除 |
| News | ★ | data_xplorer/google-news-scraper-fast | 99.4 | 6 |
| AI Overviews 专项 | ★ | apify/google-ai-overviews-scraper | 98.8 | 5 |
| Google Ads | ★ | lexis-solutions/google-ads-scraper | 99.4 | 20 |

要点：apify/google-trends-scraper 是唯一被数据否决的"官方"actor。注意 google-search-scraper 的 `queries` 是**字符串不是数组**（实测 400 教训）。

### 4.5 Facebook

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 页面帖子 | ★ | apify/facebook-posts-scraper | 99.8 | 32（含 6 种反应计数） |
| 帖子（降级） | ① | apify/facebook-pages-scraper 概览兜底 | 99.9 | — |
| 评论 | ★ | apify/facebook-comments-scraper | 100 | — |
| 小组 | ★ | apify/facebook-groups-scraper | 99.7 | 21 |
| 广告库（关键词/URL 驱动） | ★ | curious_coder/facebook-ads-library-scraper | 99.7 | 37（含 spend/reach） |
| 广告库（降级，页面驱动） | ① | apify/facebook-ads-scraper | 99.4 | 36 |
| Marketplace | ★ | apify/facebook-marketplace-scraper | 99.4 | 25 |
| 全站搜索 | ★ | apify/facebook-search-scraper | 99.7 | — |

要点：广告两条路按输入形态选——有关键词/广告库 URL 用 curious_coder；只有页面用 apify 官方。二者字段高度同构（同源于 Ad Library API）。

### 4.6 Amazon（整体成功率最低的平台，需接受现状或混合策略）

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 商品爬取 | ★ | junglee/amazon-crawler | 92.8 | 41 |
| 商品（降级） | ① | junglee/free-amazon-product-scraper | 87.5 | 41 |
| 评论 | ★ | axesso_data/amazon-reviews-scraper | 99.9 | 27（含评分汇总/verified） |
| 评论（降级） | ① | web_wanderer/amazon-reviews-extractor | 99.8 | 36 |
| 评论（降级2） | ② | junglee/amazon-reviews-scraper | 96.2 | — |
| 榜单 | ★ | junglee/amazon-bestsellers | 91.8 | 14（position/分类树） |
| 竞品研究 | ① | samstorm/amazon-competitor-research-scraper | 84.8 | 22 |

要点：Amazon 反爬最凶。junglee 系 85-93%，没有 ≥98% 的商品主爬虫。策略：商品用 junglee/amazon-crawler + 3 次重试 + 断点续跑；评论用 axesso（99.9%）独立保障。本项目已集成的 marketplace-scrapers/amazon-bsr-scraper **已从 Store 下架**（API 还能调但无商店页），要标记风险。

### 4.7 Instagram

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 全能入口（帖子+档案+搜索） | ★ | apify/instagram-scraper | 99.6 | 8 输入，万能兜底 |
| 帖子 | ★ | apify/instagram-post-scraper | 99.9 | 37 |
| Reels | ★ | apify/instagram-reel-scraper | 99.9 | 34 |
| 档案 | ★ | apify/instagram-profile-scraper | 99.7 | 21（含 latestPosts） |
| 话题 | ★ | apify/instagram-hashtag-scraper | 99.5 | 26（★3.49 评分偏低） |
| 评论 | ★ | apify/instagram-comment-scraper | 99.9 | 3 |
| 全能（降级） | ①② | apify/instagram-scraper 对所有主题兜底 | 99.6 | 23 |

要点：官方全家桶。任何专项 actor 失败，instagram-scraper 都能换 resultsType/directUrls 兜住。hashtag 评分 3.49 但成功率 99.5%——评分低多是价格抱怨，不是数据问题。

### 4.8 Shopify

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 店铺全目录 | ★ | trovevault/shopify-products-scraper | 99.0 | 31（variants/库存/图片全集） |
| 全目录（降级） | ① | autofacts/shopify | 93.8 | 12（含推荐/店铺详情） |
| 全目录（降级2，零成本） | ② | 直连 `/products.json`（不用 actor） | — | 项目已有 apify_shopify_full_catalog 通道 |
| 店铺线索库 | ★ | ecommerce_leads/store-leads-14m-e-commerce-leads | 100 | 22（1400 万店铺库查询） |
| 线索（降级） | ① | clearpath/shopify-store-leads | 99.5 | 8（已集成） |
| 邮件线索 | ② | xmiso_scrapers/shopify-shops-email-leads-scraper | 100 | 9 |

要点：Shopify 是唯一有"不用 actor"降级路径的平台（`/products.json` 公开 JSON）。跨平台方案里应把"零成本直连"作为 ②。

### 4.9 Trustpilot（生态最薄，只有 3 个可用候选）

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 企业评论 | ★ | memo23/trustpilot-scraper-ppe | 97.7 | 37（verified/星级/语言/点赞） |
| 评论（降级） | ① | saswave/storeleads-scraper | 85.7 | 50 |
| 评论（降级2） | ② | apify/rag-web-browser 兜底抓评论页 | 98.8 | 4（markdown） |

要点：memo23 实测一次全量跑 5 分钟+（超时需给 600s 预算，与本项目 aliens_eye 教训同款）。②是通用兜底：结构化字段丢，但保正文可见。已集成的就是 memo23，方向不变，补超时预算即可。

### 4.10 Reddit

| 主题 | 主力/降级 | actor | ok% | 实测字段 |
|---|---|---|---|---|
| 帖子+评论+社区+用户一体 | ★ | harshmaur/reddit-scraper | 97.7 | 76（实测字段最多） |
| 一体（降级，付费增强） | ① | harshmaur/reddit-scraper-pro | 98.7 | 6 |
| 搜索（降级2） | ② | fatihtahta/reddit-scraper-search-fast | 98.7 | 21 |
| 便宜大碗 | 参考 | trudax/reddit-scraper-lite | **87.2** | 38 |

要点：**已集成的 trudax/reddit-scraper-lite 成功率只有 87%**，是十个平台里现有主力中风险最高的一个，建议把 harshmaur/reddit-scraper 提为主力，trudax 降为补充。harshmaur 一个入口出帖子/评论/社区/用户四类记录（dataType 字段区分）。

## 5. 跨平台规律（数据说话）

1. **clockworks > apidojo > 其他**（TikTok）；**apify 官方 > 第三方**（IG/FB）；**harvestapi > apimaestro > curious_coder**（LinkedIn）。
2. **要 cookie 的 actor 一律不进主力**（curious_coder/linkedin-profile-scraper 是唯一踩线的，已淘汰）。
3. **官方出品 ≠ 稳定**：apify/google-trends-scraper 56.6%。
4. **评分低 ≠ 不可用**：instagram-hashtag-scraper ★3.49 但成功率 99.5%。
5. **电商三平台（Amazon/Shopify/TikTok Shop）字段最富**：40-54 字段，含价格/GMV/库存/佣金。
6. **本项目现有 69 个 actor 里发现 2 个风险项**：marketplace-scrapers/amazon-bsr-scraper 已下架；trudax/reddit-scraper-lite 成功率 87%。
7. **输入形状三大坑**（已全部核实进 schema）：`queries` 字符串 vs 数组、`startUrls` 裸字符串 vs `[{url}]`、json 编辑器要对象数组。接入前跑一次 `audit_apify_inputs.py` 思路的离线审计可拦截全部三类。

## 6. 执行 TODO（确认后分三阶段）

### 阶段一：方案卡定稿（0.5 天）
- [ ] 按第 4 节结构，10 份平台方案卡写成 `docs/playbooks/platforms/` 的增补章（或独立文档，格式待定）
- [ ] 每卡含：主题矩阵、字段表（字段名/类型/描述）、主力+2 降级、单价、超时预算
- [ ] 字段描述来源：input schema 自带 title/description（已抓）；输出字段描述由 README + 试跑样本补

### 阶段二：风险项处置（0.5 天）
- [ ] trudax/reddit-scraper-lite → 评估换 harshmaur/reddit-scraper（跑 A/B）
- [ ] marketplace-scrapers/amazon-bsr-scraper 下架风险 → 找替代或标记 deprecated
- [ ] compass/Google-Maps-Reviews-Scraper 试跑 0 条 → 复测（精确 place URL 或 placeIds）
- [ ] apify/google-trends-scraper 56% → 换 data_xplorer/google-trends-fast-scraper
- [ ] 补试跑 8 个低字段数 actor（facebook-comments/pages/search、IG profile 之外剩余等）

### 阶段三：接入与验收（按需排期）
- [ ] 新增 actor 对照现有 69 端点清单，产出「新增/替换/保留」三色表
- [ ] 每个新端点走 quick_collect 默认参数表 + audit 离线审计 + 一次实测
- [ ] 更新能力总账与平台 playbook 的坑点库（沿用现有格式）
- [ ] 成本护栏：max_total_charge_usd + run_timeout 写进每端点默认值

## 7. 待讨论的决策点

1. **方案卡落在哪**：增补进现有 `docs/playbooks/platforms/*.md`，还是独立 `docs/apify-actors/<platform>.md`？前者贴合现有验收链路，后者不碰已验证文档。
2. **Amazon 现状接受度**：商品主爬虫最高 92.8%，是否接受"重试+监控"策略，还是引入非 Apify 备选？
3. **Reddit 主力更换**：trudax 87% 是否立即换 harshmaur，还是等 A/B 数据？
4. **Trends 替换**：apify/google-trends-scraper 是否直接弃用换 data_xplorer？
5. **成本红线**：本次新增 actor 的单价区间 $0.00025-$0.005/条，是否按现有 max_total_charge_usd 机制设上限？
