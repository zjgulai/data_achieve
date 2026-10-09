---
name: dih-platform-capability-ledger
description: Data Intelligence Hub 平台能力总账：可用/缺配置/上游故障/恒空端点的完整清单、本轮变更、维护方法与待补清单。接手平台维护时先读这份。
---

# DIH 平台能力总账与维护手册

> 数据截止 **2026-10-10**（生产 `degraded` 实测）。上游会变，数字会漂。
> 重新取数的命令见 §4。
> 相邻文档：[能力图谱](./【能力图谱】DIH-控制台能力地图.md)（逐页映射）·
> [运行手册](../workflows/workflow-console-capability-live-verification-stable.md)（操作步骤）·
> [坑点库](../playbooks/【坑点库】DIH-平台采集坑点汇总.md)（自动生成）

---

## 1. 现状快照

| 指标 | 值 | 说明 |
|---|---|---|
| 平台包 | 70 | 2026-10-09 前是 74，下线 4 个平台所致 |
| 能力视图 | 270 | catalog 条目数（同一端点可出现在多个平台视图） |
| 唯一端点 | 242 | 按 `endpoint_type` 去重 |
| 有实测证据的端点 | 269 / 270 | 证据来自 label 为 `[test] <endpoint_type>` 的 quick-collect 运行 |
| 成功返回过记录 | 227 | `success_endpoints` |

状态分布（`GET /api/platform-packages/providers/status`）：

| availability | 数量 | 含义 |
|---|---|---|
| `verified` | 189 | 最近一次实测成功**且返回 ≥1 条记录** |
| `config-gated` | 21 | **缺配置或缺少依赖的自建服务**，不是代码问题 |
| `degraded` | 22 | 最近一次实测失败（上游或 Actor 侧） |
| `empty` | 9 | 实测成功但 0 条记录 |
| `disabled` | 1 | catalog 里标 disabled |

> **语义要点**：`config-gated` 与 `degraded` 是两件事。
> 前者是"没配所以没跑"，后者是"跑了但失败"。不要把前者当缺陷去修代码。

---

## 2. 端点总账

### 2.1 缺配置（21 个）——每个都点名缺什么

这一档**不需要改代码**，只需要提供配置或部署服务。

| 缺什么 | 数量 | 端点 |
|---|---|---|
| `MEDIACRAWLER_BASE_URL` | 11 | bilibili×3、kuaishou×2、weibo×3、zhihu×3 |
| `ANYCRAWL_BASE_URL` | 3 | baidu_search_results、bing_search_results、duckduckgo_search_results |
| `TWITTER_ACCOUNTS_JSON` | 3 | twscrape_search / _trends / _user_tweets |
| `BLACKBIRD_BASE_URL` | 2 | blackbird_email_osint、blackbird_username_osint |
| `BESTBLOGS_API_KEY` | 1 | bestblogs_articles |
| LLM key | 1 | browser_use_task（需 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`） |

> ⚠️ **MediaCrawler 那 11 个曾被误判成"出口被墙需要代理"，是错的。**
> 实测：api 容器里连 MediaCrawler 默认地址 `http://localhost:8080` 得到
> `ConnectError [Errno 111] Connection refused` —— 服务**没有部署**，跟网络无关。
> 补齐方式：部署 MediaCrawler（注意它需要登录态 / 扫码）并设置
> `MEDIACRAWLER_BASE_URL`。可选的 `HTTP_PROXY` / `HTTPS_PROXY` 是加分项，不是前置条件。

### 2.2 上游故障（22 个）——我方改不动

| 类型 | 数量 | 端点 | 依据 |
|---|---|---|---|
| TikHub 上游通用 400 | 11 | bilibili_comments、kuaishou_search、linkedin×5、threads_search、tiktok_creator_info、tiktok_live_user、x_user_tweets | 参数与官方 OpenAPI 逐字段核对一致；TikHub 回 "Request failed… You won't be charged" |
| Apify Actor run FAILED | 5 | amazon_bsr_tracker、amazon_competitor_research、booking、reddit、target_products | run 创建成功但 Actor 自身失败，需读 run log |
| 运行前 403 | 2 | apify_1688_product_search、apify_walmart_reviews_scraper | Actor 拒绝本账号发起运行，耗时 <2s |
| 超时 | 3 | aliens_eye_advanced / _domain / _recurse | 单次扫描 >60s |
| 超时 | 1 | apify_google_trends_scraper | 超出 quick-collect 同步等待窗口 |

> `aliens_eye_basic` / `_batch` / `_correlate` / `_selfcheck` 是 `verified` —— 证明这个
> 采集器不需要 key，只是高级扫描太慢。**不要**给它加"缺 API key"的判定。

### 2.3 运行成功但无数据（9 个）

| 端点 | 原因 |
|---|---|
| `tikhub_tiktok_creator_account_health` | spec 只收 cookie，必须登录态 |
| `tikhub_tiktok_ads_search` / `_ads_keyword_suggest` | 参数正确，上游对演示种子词回空 |
| `tikhub_tiktok_creator_insights` / `_trend` | 参数正确，上游回空 |
| `tikhub_zhihu_search`、`tikhub_lemon8_trending` | 上游回空列表 |
| `tikhub_zhihu_question_answers` | 缺真实 question id；而 zhihu_search 本身回空，无法回收 |
| `tikhub_wechat_channels_video` | 缺真实视频号 finder username |

### 2.4 已下线（不给调用）

**a. 从 catalog 摘掉 8 个**（同时从 `_APIFY_ENDPOINT_DEFAULTS` 与 `_ENDPOINT_TO_COLLECTOR` 移除，
调用返回 400 `Unknown endpoint_type`）：

`apify_facebook_group_scraper`、`apify_product_hunt_scraper`、`apify_yelp_scraper`、
`apify_pinterest_scraper`、`apify_pinterest_media_profile_scraper`、`apify_telegram_scraper`、
`apify_web_scraper`、`apify_shopify_full_catalog`

连带影响：`pinterest`、`telegram`、`product_hunt`、`yelp` 四个平台失去全部端点，
平台包消失（74 → 70），对应的 `notes/*.json` 一并删除。

**b. 从 `_APIFY_ENDPOINT_DEFAULTS` 删掉 31 个"幽灵端点"**（只在 quick-collect 表里、
不在 catalog 里，无人可发现却仍消耗额度）。其中 `apify_tiktok`、`apify_youtube`、
`apify_instagram`、`apify_ebay_scraper`、`apify_gemini_scraper`、`apify_tripadvisor_scraper`
与 catalog 里的正式端点重复。

> ⚠️ 这 31 个里有约 20 个当轮实测**是通的**（`apify_x_scraper` 1 条、
> `apify_threads_scraper` 10 条、`apify_google_shopping_scraper` 10 条、
> `apify_trustpilot_scraper` 5 条…）。现在不可达。入参与 Actor 都还是对的，
> 要恢复只需重新补进 `_APIFY_ENDPOINT_DEFAULTS` 与 catalog。

**c. 幽灵端点有个副作用**：它没有平台包，所以**不能挂 endpoint 级坑点**。
写 `notes/<platform>.json` 时 `builder` 会直接报 `target unknown endpoint_type`。
这类坑点要写成 `scope: "platform"`。

---

## 3. 本轮变更（2026-10-09 ~ 10-10）

27 个提交。按主题归类，方便回溯。

### 3.1 Apify Actor 存活与入参

| 变更 | 影响 |
|---|---|
| 103 个 Actor 存活巡检 | 发现 **25 个已下架 + 2 个废弃**，下架后调用一律 **403（不是 404）** |
| 28 个 endpoint_type 改指存活 Actor | 新 Actor 见 §3.1 表 |
| 33 个端点补齐 `base_input` 使其满足 Actor 的 `inputSchema` | 首轮 118 个端点里 33 个不合格（17 个缺必填键） |
| 其余 7 个端点按实测修正入参 | linkedin×2 / ebay_sold / glassdoor / google_maps_reviews / temu / google_ads |
| `_APIFY_META_KEYS` 收窄为 4 个采集开关 | 原先把 `query`/`url`/… 一并剔除，导致 `apify_rag_web_browser` 必填的 `query` 被静默丢弃 |
| `max_total_charge_usd` 缺省 1.0 → 3.0 | 太小会让按事件计费的 Actor 直接 `ABORTED`，不是少返回几条 |

**当前指到的 Actor（2026-10-09 后新增）**：
`apidojo/tweet-scraper`、`apify/chatgpt-search-scraper`、`apify/perplexity-search-scraper`、
`brilliant_gum/tiktok-ads-library-scraper`、`burbn/google-shopping-scraper`、
`curious_coder/google-play-scraper`、`dltik/1688-scraper`、`dtrungtin/ebay-items-scraper`、
`futurizerush/meta-threads-scraper`、`harvestapi/linkedin-company`、
`harvestapi/linkedin-profile-scraper`、`igolaizola/facebook-ad-library-scraper`、
`junglee/amazon-bestsellers`、`junglee/amazon-reviews-scraper`、
`maximedupre/product-hunt-scraper`、`memo23/x-ads-transparency-scraper`、
`misceres/indeed-scraper`、`silva95gustavo/linkedin-ad-library-scraper`、
`solidcode/ads-transparency-scraper`、`streamers/youtube-comments-scraper`、
`tri_angle/snapchat-scraper`、`trovevault/shopify-products-scraper`、
`trudax/reddit-scraper-lite`、`web_wanderer/walmart-product-scraper`

### 3.2 TikHub 归一化

海外与国内共修 **20 个**"成功但 0 条"的端点。根因都是**响应形状变了、归一化器认不出**：

| 端点 | 条目实际位置 |
|---|---|
| `tikhub_youtube_video_comments` | `data.comments`（snake_case 字段） |
| `tikhub_reddit_trending` | `data.popularfeed.postsInfoByIds` |
| `tikhub_reddit_subreddit_posts` | `data.subredditV3.elements.edges[].node`（CellGroup，散在 `cells[]`） |
| `tikhub_x_trending` | `data.trends` |
| `tikhub_x_user_followers` | `data.followers` |
| `tikhub_linkedin_company_profile` | `data` 就是单个公司对象 |
| `tikhub_tiktok_live_search` | `data.data`，两种条目形状（`lives` / `anchor`） |
| `tikhub_tiktok_live_room_detail` | `data.data` 单个直播间对象，主播在 `owner` |
| `tikhub_tiktok_shop_products` | `data.data.products` |
| `tikhub_tiktok_top_ads` / `_ads_detail` | `data.data.materials` / `data.data` 单对象 |
| `tikhub_tiktok_user_followers` | `data.followers`（完整用户对象，需专门归一化） |
| `tikhub_tiktok_hashtag_posts` | `aweme_list`（原演示 ch_id 是占位） |
| `tikhub_threads_user_posts` | `data.mediaData.edges[].node` |
| `tikhub_threads_post_comments` | `data.edges[].node` |
| `tikhub_reddit_post_comments` | `data.postInfoById` |
| `tikhub_instagram_post_comments` | `data.data.items` |
| `tikhub_bilibili_user_videos` | `data.data.item`（**单数**） |
| `tikhub_bilibili_video_search` | `data.data.*` |
| `tikhub_douyin_hot_search` | `data.data.word_list` / `trending_list` |
| `tikhub_douyin_brand_hot_search` | `data.brand_list` |
| `tikhub_douyin_comments` | `data.comments` |
| `tikhub_weibo_user_posts` | `data.data.list` |
| `tikhub_wechat_search` | `data.results.data` |
| `tikhub_kuaishou_user_posts` | `data.feeds` |
| `tikhub_lemon8_user_posts` | `data.data`（单个用户对象） |

提取器现在的策略：**先把 `inner` / `inner.data` / `inner.results` / `inner.data.data` …
全收进候选作用域，再逐个找工作键**。

### 3.3 TikHub 参数与请求方式

| 缺陷 | 说明 |
|---|---|
| 参数白名单漏键 | `_validate_tikhub_social_config` 的键集合不覆盖 `_build_params` 实际读取的键，被漏的键**静默变空串**（`subreddit` 就是这样丢的）。已补 27 个键 |
| 路径错 | `tikhub_weibo_user_posts` 少了 `_v2`（实测 404）。62 个映射路径已全量比对官方 OpenAPI，只此一处 |
| POST-only 端点走 GET | `tikhub_wechat_search` → 405；`tikhub_tiktok_ads_search` / `_wechat_channels_video` 需要 body 参数 |
| 演示值是占位 | `123456` / `test_post_id` / `MS4wLjABAAAA` 这类。已从已跑通端点回收真实 ID |

### 3.4 其它 Provider

| 变更 | 说明 |
|---|---|
| `firecrawl_extract` | `/v1/scrape` 收 `url`（字符串），原先传的是 `urls` 数组 |
| `firecrawl_batch_scrape` | 异步接口，原先不轮询，**永远 0 条** |
| `devto_articles_search` | Cloudflare 对**浏览器 UA** 的 API 请求返回 403，换中性 UA |
| `autoscraper_enhanced_web` | `AutoScraper.build()` 第一个位置参数是 `url`，传 HTML 会触发 `requests.get(HTML)`；`get_result()` 返回二元组 |
| `anysearch_tag_search` | tag 必须取自固定词表，且必填参数放 **`params` 里**而不是顶层 |
| `playwright_browser_*` | 镜像原先没装 Chromium；且安装路径与运行路径不一致（已钉 `PLAYWRIGHT_BROWSERS_PATH`） |
| `anydoc_file_to_markdown` | markitdown 的 PDF 转换器在 extra 里，改成 `markitdown[all]` |
| `robin_darkweb_*` | 新增 **Tor sidecar**，api 的 `TOR_PROXY_URL=socks5h://tor:9050`（`h` 让 DNS 也走 Tor，`.onion` 必须） |

### 3.5 路由与状态

| 变更 | 说明 |
|---|---|
| quick-collect 入参装配 | `_APIFY_META_KEYS` 收窄；入参覆盖端点缺省值（原先缺省值胜出） |
| quick-collect `project_id` 校验 | 传不存在的 project 曾撞外键 → **500 + 原始 SQL 栈**，现为 400 |
| 状态分类 | 未部署的自建服务归 `config-gated`（不再算 `degraded`） |
| 4xx 响应体截断 | 120 → 500 字符。120 正好把 `Items in input.productUrls at positions [0]…` 砍掉 |

---

## 4. 维护方法

### 4.1 重新取数（只读，安全）

```bash
B=https://scrapy.luteos.com
curl -s $B/api/collectors/catalog      | jq '.collectors|length'
curl -s $B/api/collectors/docs         | jq '{total_endpoints,tested_endpoints,success_endpoints}'
curl -s $B/api/platform-packages       | jq '{platform_count,capability_count,unique_endpoint_count}'
curl -s $B/api/platform-packages/providers/status \
  | jq '[.endpoints|group_by(.availability)[]|{(.[0].availability):length}]|add'
```

### 4.2 两个**免额度**巡检（改动前先跑）

**Apify Actor 存活 + 入参审计**

```bash
python scripts/audit_apify_inputs.py     # 只读公开 inputSchema，0 额度、不产生 run
```
报三类问题：缺必填键 / 键名不在 schema 里 / `editor` 形状不符。
取值优先级：`inputSchema.properties[key].prefill` > `default` > 猜。
**`exampleRunInput` 不可用**（多为 `{"helloWorld":123}` 占位）。

**TikHub 路径与方法**

```bash
curl -s https://api.tikhub.io/openapi.json -o /tmp/tikhub_openapi.json   # 3MB，免鉴权
```
用它校验：路径是否存在、方法是 GET 还是 POST、body 的必填字段。

### 4.3 全量实测（**消耗额度**）

```bash
python scripts/verify_platform_live.py --base-url https://scrapy.luteos.com \
  --project-id <真实 project uuid> --delay 0.3 --concurrency 6 --timeout 180 [--resume]
```
- label 必须是**恰好** `[test] <endpoint_type>`，否则状态会被静默忽略。
- 先 `--dry-run` 校端点集合。
- `project_id` 必须属于 demo workspace；先用 `curl $B/api/projects | jq '.[].id'` 取一个真实值。

### 4.4 排查一个降级端点的顺序

1. **先读 400/422 的响应体**（采集器截 500 字符）。上游通常直接点名哪个字段。
2. **拿官方 spec 比对**路径与方法，别靠猜。
3. **确认参数真的传到了上游** —— 最隐蔽的一类：
   - `_validate_*_config` 的白名单漏键 → 静默变空串
   - 第三方库的**位置参数顺序**（`AutoScraper.build()` 第一个是 url）
   - 必填参数在**嵌套的 `params`** 里而不是顶层（AnySearch 的 `library`）
4. **"成功但 0 条" → 取原始响应比对形状**，不要反复调参数。
   直接 curl 上游（TikHub 用 `TIKHUB_API_KEY`，Apify 用 `run-sync-get-dataset-items`）。
5. **失败耗时的意义**：<2 秒的 403 来自 `POST /acts/<id>/runs`，run 根本没创建
   （Actor 下架或拒绝本账号）；耗时长才是上游反爬。

### 4.5 沉淀坑点（单一事实源）

在 `apps/api/src/data_intelligence_hub/platform_packages/notes/<platform_id>.json` 加一条：

```json
{"scope": "endpoint|platform", "target": "<endpoint_type|platform_id>",
 "symptom": "...", "cause": "...", "workaround": "...",
 "failure_class": "config_gated", "severity": "blocker",
 "verified_at": "YYYY-MM-DD", "source_ref": "reports/live-sweep/latest.json",
 "tags": ["..."]}
```

然后：

```bash
cd apps/api
PYTHONPATH=$PWD/src .venv/bin/python ../../scripts/generate_platform_packages.py --update-lock
PYTHONPATH=$PWD/src .venv/bin/python ../../scripts/test_platform_packages.py
```

坑点会渲染进 `SKILL.md` / `README.md` / `references/playbook.md`、控制台 `/skills/<id>`
与 MCP 的 `get_playbook`。

> **`target` 必须是真实存在的 endpoint_type 或 platform_id。**
> 命中不了时 `builder` 会**直接报错**（2026-10-09 前是静默忽略）。
> `platform` 未必等于 collector 名：Exa 端点的 platform 是 `web`，
> `tikhub_tiktok_shop_products` 的 platform 是 `tiktok_shop`。

### 4.6 发布

```bash
# 服务器上
cd /opt/data-achieve-scrapy/app
git fetch origin <branch> && git reset --hard FETCH_HEAD   # 别用 fetch 到当前分支
cd configs/deploy/scrapy
ENV=/opt/data-achieve-scrapy/.env.production
docker compose --env-file "$ENV" build api && docker compose --env-file "$ENV" up -d api
docker compose --env-file "$ENV" restart edge              # ⚠️ 必须，见下
```

> **必须先 push 再部署**。服务器是 `git fetch` 拿远端 —— 只在本地 commit 就部署，
> 拿到的还是旧提交。（本项目在这上面栽过一次，实测全 0 还以为是代码没生效。）
> **`edge` 必须 restart**：它缓存了 api 容器的旧 IP，不重启就 502。
> 改 UI 另需 `build console`。notes 烘进 api 镜像，改坑点必须重建 api。

---

## 5. 还缺什么

### 5.1 需要凭据 / 服务（对应 §2.1 的 21 个端点）

| 项 | 影响 | 备注 |
|---|---|---|
| MediaCrawler 部署 | 11 | 需登录态（扫码），先定账号方案 |
| AnyCrawl 部署 | 3 | baidu / bing / duckduckgo |
| `BESTBLOGS_API_KEY` | 1 | bestblogs.dev/settings |
| Blackbird 自建 | 2 | `--web 5002` |
| `TWITTER_ACCOUNTS_JSON` | 3 | twscrape 账号池 |
| LLM key | 1 | `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` |

服务器上**已配置**：`TIKHUB_API_KEY`、`APIFY_API_TOKEN`、`EXA_API_KEY`、
`FIRECRAWL_API_KEY`、`ANYSEARCH_API_KEY`、`JINA_API_KEY`、`PROXY_ROTATOR_URL`。
`PLATFORM_CREDENTIAL_MASTER_KEY` 是凭据加密主密钥，**不要更换**。

### 5.2 上游侧，无解（22 个）

见 §2.2。TikHub 的 11 个可以在有客服渠道时反馈；Apify 的 5 个可以读 run log 后换 Actor。

### 5.3 已知的账实不符

- `_APIFY_ENDPOINT_DEFAULTS` 与 catalog 的端点集合仍可能漂移。回归测试
  `tests/unit/test_quick_collect_apify_input.py` 钉住了 `catalog ⊆ defaults` 这一方向；
  反向（quick-collect 多出来的幽灵端点）没有约束。§2.4b 已清了 31 个。
- 4 个单测在改动前的基线上就失败（`test_firecrawl_collector`
  的 `test_test_fails_without_api_key`、`test_spiderfoot_collector` 的
  `test_valid_target`、`test_v2_traceability`、`test_workflow_executor_postgres_guard`）。
  前两个依赖环境变量，后两个依赖未入库的 `docs/superpowers/`。

---

## 6. 关键坑点索引

按"最容易被同一个坑绊两次"排序。

| # | 坑 | 一句话判据 |
|---|---|---|
| 1 | **Actor 会下架，下架后是 403 不是 404** | 失败耗时 <2s 且 `http_forbidden` → 换 Actor，改参数无效 |
| 2 | **`success` + 0 条通常是形状过时** | 先取原始响应比对，别调参数 |
| 3 | **入口参数会静默丢** | 白名单漏键 / 库的位置参数 / 嵌套 `params` |
| 4 | **`status="verified"` 不等于实测通过** | 看 `/api/collectors/docs` 与 `/providers/status` |
| 5 | **证据只认精确 label** | 必须是 `[test] <endpoint_type>`，写错就被忽略 |
| 6 | **`config-gated` ≠ `degraded`** | 前者没配，后者跑了失败 |
| 7 | **platform 未必等于 collector 名** | Exa→`web`；tiktok_shop_products→`tiktok_shop` |
| 8 | **quick-collect 一定落库** | 没有 `save_records` 开关，扫描会留数据 |
| 9 | **自建服务缺失长得像"网络不通"** | `Connection refused` 查服务，不是查代理 |
| 10 | **改完必须先 push 再部署** | 服务器 `git fetch` 拿远端 |

完整坑点（94 条）见 [`【坑点库】`](../playbooks/【坑点库】DIH-平台采集坑点汇总.md)。
