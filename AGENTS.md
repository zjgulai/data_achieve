# Data Intelligence Hub — Agent 工作指南

> 最后更新：2026-09-03 · 热推 · 分支 `codex/social-api-private-matrix-20260708`

## 项目一句话定位

**纯数据采集平台**。后端 FastAPI 提供 270 个能力视图（242 个唯一 endpoint），前端 Next.js scraper-console 提供采集管理台、74 个平台 Skill 卡片和共享 MCP Runtime，生产主域名为 `scrapy.luteos.com`。

---

## 生产环境

### 旧生产（腾讯云 · 兼容保留）

| 项目 | 值 |
|---|---|
| 域名 | `scrapy.lute-tlz-dddd.top` |
| 服务器 IP | `101.34.52.232`（公网）|
| SSH key | `DDDD.pem`（项目根目录，**不得 commit**）|
| 部署分支 | `codex/social-api-private-matrix-20260708` |
| 当前 commit | `42a0dc7` |
| API health | `GET /api/health` → `{"status":"ok"}` |
| 采集端点 | 历史快照，不作为当前口径 |
| 认证模式 | **无需登录**，全路由使用 demo workspace `bf51c6a8-fba5-5528-ac91-89ffd84f85c2` |
| docker-compose | `configs/deploy/scrapy/docker-compose.yml` |

### 新服务器（内网 · **已部署运行**）

| 项目 | 值 |
|---|---|
| 服务器 IP | `192.168.204.230`（内网）|
| 规格 | 8 vCPU · 62 GB RAM · 200 GB 系统盘 + 1 TB `/data` 数据盘 |
| 访问方式 | 堡垒机 `jumpserver.luteos.site:2222` → `lute@192.168.204.230` 密码登录 |
| 项目路径 | `~/apps/data_scrapy` |
| 环境变量 | `/data/scrapy/configs/.env.production` |
| API health | `http://192.168.204.230/api/health` → `{"status":"ok"}` |
| 采集端点 | 270 capability views / 242 unique endpoint types |
| docker-compose | `configs/deploy/scrapy-new/docker-compose.yml` |
| 持久化路径 | Postgres: `/data/scrapy/postgres`，Exports: `/data/scrapy/exports` |
| 部署文档 | [`docs/deployment-new-server.md`](docs/deployment-new-server.md) |
| 部署日期 | 2026-09-01 |

### 公网入口与 Skill/MCP（2026-10-09）

| 项目 | 值 |
|---|---|
| 主域名 | `https://scrapy.luteos.com` |
| 公网网关 | `43.163.92.244` |
| 链路 | 共享 Nginx → relay → 受限 SSH 反向隧道 → `192.168.204.230:80` |
| Skill 目录 | `/skills` |
| MCP | `/mcp/`，生产要求 `SCRAPY_MCP_TOKEN` |
| 平台包 | 70 个，可从 `/api/platform-packages/{platform_id}/download` 下载 |
| 当前口径 | 270 capability views / 242 unique endpoint types |

### 容器（新服务器 192.168.204.230）

| 容器名 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| `data_achieve_scrapy_api` | `data_achieve_scrapy_api:latest` | 8000 | FastAPI 后端 |
| `data_achieve_scrapy_console` | `data_achieve_scrapy_console:latest` | 3001 | 采集管理台 |
| `data_achieve_scrapy_edge` | `nginx:1.27-alpine` | 8080 | 反向代理 |
| `data_achieve_scrapy_db` | `postgres:16` | 5432 | 数据库 |
| `data_achieve_scrapy_maigret` | `soxoj/maigret:latest` | 5000 | OSINT 用户名追踪 |
| `data_achieve_scrapy_spiderfoot_real` | `crivellarodiego/spiderfoot:latest` | 5001（内部）| SpiderFoot Web UI |
| `data_achieve_scrapy_spiderfoot` | `spiderfoot_bridge:latest` | 5001 | SpiderFoot REST API 桥接 |
| `data_achieve_scrapy_mediacrawler` | `bllxk/mediacrawler-api:latest` | 8001（内部）| MediaCrawler 爬虫服务 |
| `data_achieve_scrapy_mc_bridge` | `mediacrawler_bridge:latest` | 8080（内部）| MediaCrawler 路由桥接 |

> Bridge 镜像源码在 `configs/bridges/`，需要在服务器上 build（`docker compose ... up --build`）。

> MediaCrawler 需配置平台 cookies 才能获取真实数据：`BILIBILI_COOKIES`、`WEIBO_COOKIES`、`ZHIHU_COOKIES`、`KUAISHOU_COOKIES`（写入 `.env.production`）。

---

## 代码结构（只需关注这几个文件）

```
apps/api/src/data_intelligence_hub/
├── collectors/                   ★ 采集器实现
│   ├── base.py                   — BaseCollector 基类
│   ├── registry.py               ★ COLLECTOR_REGISTRY 注册表
│   ├── tikhub_social.py          — TikHub 61 端点
│   ├── apify_actor.py            — Apify 75 端点
│   ├── public_feed.py            — RSS + Web crawl + AutoScraper
│   ├── github_repo.py / github_topic.py
│   ├── playwright_browser.py     — 浏览器采集（text/html/screenshot）
│   ├── ecommerce_product_page.py / ecommerce_product_discovery.py
│   ├── anysearch_collector.py    — AnySearch API
│   ├── jina_reader.py            — Jina Reader（需代理）
│   ├── spiderfoot_collector.py   — SpiderFoot 基础 3 端点
│   ├── spiderfoot_extended_collectors.py — SpiderFoot 扩展 6 端点
│   ├── bestblogs_collector.py    — BestBlogs AI 精选文章
│   ├── blackbird_collector.py    — Blackbird 邮箱/用户名 OSINT
│   ├── autoscraper_collector.py  — AutoScraper 智能提取
│   ├── mediacrawler_collector.py — B站/微博/知乎/快手
│   ├── twscrape_collector.py     — X/Twitter 多账号采集
│   ├── anycrawl_collector.py     — 百度/Bing/DDG SERP
│   ├── tech_blog_collector.py    — Dev.to/掘金/Substack
│   ├── osint_collector.py        — Maigret/Sherlock 用户名追踪
│   └── wappalyzer_collector.py   — 技术栈检测
├── api/routes/
│   ├── collectors.py             ★ catalog 端点 + CollectorEndpoint 定义
│   └── quick_collect.py          ★ _ENDPOINT_TO_COLLECTOR 映射
└── services/
    └── collector_catalog.py      ★ CollectorDefinition + _validate_* 函数

apps/scraper-console/src/app/
├── platforms/page.tsx            ★ 前端卡片渲染（PLATFORM_LOGOS / 分类 / 方法）
├── dashboard/                    — 采集概览
├── projects/                     — 项目管理
├── tasks/                        — 任务列表
├── runs/                         — 采集记录
├── raw-records/                  — 原始数据
└── datasets/                     — 数据集

configs/deploy/scrapy/
├── docker-compose.yml            ★ 生产容器编排（含 API keys env）
└── edge-nginx.conf               — Nginx 路由
```

---

## 当前任务状态

### 已完成（生产可用）

| 任务 | commit/热推 | 状态 |
|---|---|---|
| D4 监管 RSS（FDA/NHS/OPSS/PR Newswire）| `8d462e8` | ✅ verified×4 |
| D5 AnySearch 采集器 | `7e8468a` | ✅ verified×2，records=10 |
| D1 Jina Reader 采集器 | `ca8b647` | ✅ verified×3，本地 OK，生产需代理 |
| 平台能力中心 UI 重设计 | `e59cbcc` | ✅ 去 emoji，PlatformLogo，工业质感行布局 |
| 项目减负 | `b339f45` | ✅ git 干净，分支精简，文档更新 |
| SpiderFoot 升级（6 扩展模块）| `5a37483` | ✅ spiderfoot 从 3→9 端点 |
| BestBlogs AI 精选文章 | `5a37483` | ✅ verified×1，catalog 独立分组 |
| Blackbird 邮箱/用户名 OSINT | `5a37483` | ✅ verified×2，catalog 独立分组 |
| AutoScraper 智能提取 | `42a0dc7` | ✅ verified×1，已入 rss_web 组 |
| MediaCrawler（B站/微博/知乎/快手）| `c299697` | ✅ 8 端点（cookies 需配置才生效）|
| AnyCrawl SERP（百度/Bing/DDG）| `fedb26b` | ✅ 3 端点 |
| Maigret/Sherlock OSINT | `cdc81e9` | ✅ 2 端点 |
| twscrape X/Twitter | `cdc81e9` | ✅ 3 端点（多账号需配置）|
| Firecrawl 全站采集 | `fe8cd0a` | ✅ 3 端点 |
| 技术博客（Dev.to/掘金/Substack）| `11b5cf0` | ✅ 3 端点 |
| Wappalyzer 技术栈检测 | `11b5cf0` | ✅ 1 端点 |
| catalog 同步（bestblogs/blackbird/spiderfoot 扩展）| 热推 2026-08-31 | ✅ verified 197→207 |
| **Aliens Eye ML-OSINT**（7 端点）| 热推 2026-09-03 | ✅ 207→217 verified，ML+840+平台 |
| **Robin 暗网 OSINT**（3 端点）| 热推 2026-09-03 | ✅ catalog 已注册，需 Tor |
| **Obscura CDP 接入**（3 端点质量提升）| 2026-09-03 | ✅ PlaywrightBrowserCollector 优先用 Obscura，降级 Chromium |
| **browser-use AI 浏览器**（1 端点）| 2026-09-03 | ✅ BrowserUseCollector 已实现，需 LLM key |
| **Aliens Eye ML-OSINT**（7 端点）| 热推 2026-09-03 | ✅ 207→217 verified，ML+840+平台 |
| **Robin 暗网 OSINT**（3 端点）| 热推 2026-09-03 | ✅ catalog 已注册，需 Tor |
| **Obscura CDP 接入**（3 端点质量提升）| 2026-09-03 | ✅ PlaywrightBrowserCollector 优先用 Obscura，降级 Chromium |
| **browser-use AI 浏览器**（1 端点）| 2026-09-03 | ✅ BrowserUseCollector 已实现，需 LLM key |

### 未完成 / 等待配置

| 任务 | 说明 | 优先级 |
|---|---|---|
| E1: MediaCrawler cookies | 需用户提供 BILIBILI/WEIBO/ZHIHU/KUAISHOU cookies，写入 `.env.production` | **高** |
| E2: Twitter 多账号 | 需用户提供 TWITTER_ACCOUNTS_JSON，写入 `.env.production` | **高** |
| Robin Tor 配置 | 新服务器安装 Tor（`apt install tor`），docker-compose INSTALL_OSINT=true 重建 | 中 |
| browser-use LLM key | 在 `.env.production` 配 ANTHROPIC_API_KEY 或 OPENAI_API_KEY | 中 |
| Obscura 容器启动 | 新服务器 docker-compose 重建时自动拉取 `h4ckf0r0day/obscura:latest` | 中 |
| Jina Reader 生产网络 | 服务器 IP 直连 `r.jina.ai` 超时，需配代理或中转 | 低 |
| D2 Shopee | 生产 IP 被封（HTTP 403），暂不可行 | 取消 |
| B1 Reddit collector | **永久取消**（用户明确要求）| 取消 |
| B2 YouTube collector | **永久取消**（用户明确要求）| 取消 |

### 下一步可做的事（代码已就绪，等配置）

1. 提供 B站 Cookie → 立即激活 3 个 MediaCrawler 端点
2. 提供微博/知乎/快手 Cookie → 各再激活若干端点
3. 提供 Twitter 多账号 JSON → twscrape 3 端点稳定运行
4. 新服务器 `docker compose up --build` → Obscura + Robin(Tor) + aliens-eye 全部生效

---

## 新增采集卡片流程（5 步）

### Step 1：新建 collector

```python
# apps/api/src/data_intelligence_hub/collectors/your_collector.py
from .base import BaseCollector, CollectionResult, RawRecord

class YourCollector(BaseCollector):
    async def collect(self) -> CollectionResult:
        # self.config 包含前端传入的参数
        url = self.config.get("url", "")
        # ... 实现采集逻辑
        record = RawRecord(content={"key": "value"}, metadata={})
        return CollectionResult(raw_records=[record], errors=[])
```

### Step 2：注册

```python
# collectors/registry.py
from .your_collector import YourCollector
COLLECTOR_REGISTRY["your_collector"] = YourCollector
```

### Step 3：加 catalog 端点

```python
# api/routes/collectors.py — 在对应 group 的 endpoints 列表里加：
CollectorEndpoint(
    endpoint_type="your_endpoint_name",
    label="端点显示名称",
    platform="platform_key",      # 对应 PLATFORM_LOGOS 的 key
    description="采集内容说明",
    method="your_method",          # 对应 METHOD_META 的 key
    content_type="web_page",       # 对应 CONTENT_TYPE_META 的 key
    status="verified",
    required_params=["url"],
    optional_params=[],
    cost_hint=None,
    provider="your_provider",
)
```

### Step 4：加 quick_collect 映射

```python
# api/routes/quick_collect.py — 在 _ENDPOINT_TO_COLLECTOR 加：
"your_endpoint_name": ("your_collector", {"url": "url"}),
```

### Step 5：加 validate 函数

```python
# services/collector_catalog.py
def _validate_your_config(params: dict) -> dict:
    url = params.get("url", "").strip()
    if not url:
        raise ValueError("url is required")
    return {"url": url}
```

### Step 6（可选）：前端加平台 Logo

```typescript
// apps/scraper-console/src/app/platforms/page.tsx
// 在 PLATFORM_LOGOS 加：
your_platform: { bg: "#XXXXXX", fg: "#fff", letter: "XX" },

// 在 PLATFORM_GROUP_META 对应分组的 platforms[] 加平台名：
open_web: { ..., platforms: [..., "your_platform"] },
```

### Step 7：正式部署

```bash
ssh lute@192.168.204.230
cd ~/apps/data_scrapy
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy-new/docker-compose.yml \
  --env-file /data/scrapy/configs/.env.production \
  up --build --no-deps --detach api console

# 验收
curl https://scrapy.luteos.com/api/collectors/catalog | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  [print(e['endpoint_type'],e['status']) for g in d['collectors'] \
  for e in g['endpoints'] if 'your_endpoint' in e['endpoint_type']]"
```

---

## 关键约束（不可违反）

- `provider_call=false` — 不得直接调用第三方 Provider API，只通过 collector 抽象层
- B1(Reddit) / B2(YouTube) collector **永远不做**
- D2(Shopee) **取消**，服务器 IP 被封
- 热更新后必须在下次正式发布时完整重建镜像，否则 `docker compose up --build` 会回退
- 不得 commit `DDDD.pem`、`.env.production`、API keys

---

## 部署操作

### SSH 登录

```bash
ssh lute@192.168.204.230
```

### 完整重建（code 已 push 后）

```bash
cd ~/apps/data_scrapy
git pull origin codex/social-api-private-matrix-20260708
docker compose -f configs/deploy/scrapy-new/docker-compose.yml \
  --env-file /data/scrapy/configs/.env.production \
  up --build --no-deps --detach api console
```

### 健康检查

```bash
curl -fsSL https://scrapy.luteos.com/api/health
curl -fsSL https://scrapy.luteos.com/api/platform-packages | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  print(d['platform_count'], d['capability_count'], d['unique_endpoint_count'])"
# 期望：70 270 242
```

---

## 平台采集实测与坑点体系（2026-10-09 起）

- **能力图谱**：`docs/architecture/【能力图谱】DIH-控制台能力地图.md`（逐页 → 后端 → 实测状态）
- **测试计划**：`docs/playbooks/【测试计划】DIH-平台采集生产实测.md`（L1–L8 分层 + 通过标准）
- **坑点库（自动生成）**：`docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md`
- **坑点单一事实源**：`apps/api/src/data_intelligence_hub/platform_packages/notes/<platform_id>.json`
  → 生成器把它渲染进每平台 `SKILL.md` / `README.md` / `references/playbook.md`，
  并经 `GET /api/platform-packages/<id>` 与控制台 `/skills/<id>` 展示。
- **七个必须记住的坑**：
  1. catalog 的 `status="verified"` 只是静态声明，**不等于实测通过**；真实状态看 `/api/collectors/docs` 与 `/providers/status`（证据来自 `label=[test] <endpoint_type>` 的 quick-collect 运行）。
  2. 端点归属的 `platform` 未必等于 collector 名（例：Exa 端点的 platform 是 `web`）；写坑点/建 Skill 包时以 catalog 的 `platform` 字段为准。
  3. **`success` + `records_count=0` 通常是归一化形状过时，不是参数问题**。TikHub 会改嵌套层级（YouTube `data.contents` 由 list 变 dict、Reddit `data.search` 同理）；`_extract_items` 按固定路径取值会静默返回空列表。排查时**先取原始响应确认形状**（服务器上直接用 `TIKHUB_API_KEY` curl 上游），别反复调 `params`。
  4. `quick-collect` 的 `project_id` 必须属于 demo workspace；此前不校验，传错值直接撞外键 → **500 + 原始 SQL 栈**（2026-10-09 已改成 400 `Unknown project_id`）。
  5. **Apify 的 403 ≠ 反爬**。看 TaskRun 耗时：**<2 秒**的 `http_forbidden` 来自 `POST /acts/<id>/runs`，Apify run 根本没创建（Actor 已下架，或拒绝本账号运行）；耗时长才是上游站点反爬。前者换参数、加代理都没用，只能换 Actor。
  6. **Apify Actor 的 `inputSchema` 是 `additionalProperties:false`**：缺必填键**或**多传未知键都整单 400。真实 schema 用 `GET https://api.apify.com/v2/acts/<user~name>/builds/default` 免鉴权取（`exampleRunInput` 常是 `{"helloWorld":123}` 占位，不能当示例用）。
  7. **quick-collect 的 Apify 元键白名单只该有 4 个采集开关**（`maxItems`/`max_items`/`max_total_charge_usd`/`run_timeout_seconds`，见 `_APIFY_META_KEYS`）。曾把 `query`/`url`/`keyword`/`asin`/… 也列进去，`apify_rag_web_browser` 必填的 `query` 因此被静默丢弃。
- **Apify Actor 会下架**：`_APIFY_ENDPOINT_DEFAULTS` 的 103 个 distinct Actor 里，2026-10-09 巡检发现 **25 个已下架 + 2 个被标废弃**（对应 28 个 endpoint_type，已改指存活 Actor）。下架后调用一律返回 403（**不是** 404），极易误判为反爬。改 Actor 时三处要一起动：`_APIFY_ENDPOINT_DEFAULTS`、`scripts/collector_demo_params.py`、`api/routes/collectors.py` 的 `provider`/`required_params`。巡检方法（免额度、不产生 run）见 [运行手册](./docs/workflows/workflow-console-capability-live-verification-stable.md)。
- **quick-collect 能跑的端点 ≠ 目录里有的端点**：`_APIFY_ENDPOINT_DEFAULTS` 有 118 个，`/api/collectors/catalog` 只暴露 87 个 Apify 端点，前者是后者的真超集——多出的 31 个"幽灵端点"无人可发现却照样消耗额度。回归测试 `tests/unit/test_quick_collect_apify_input.py` 钉住了 `catalog ⊆ defaults` 这一方向。**副作用**：幽灵端点没有平台包，所以它**不能挂 endpoint 级坑点**——写 `notes/<platform>.json` 时 `builder` 会直接报 `target unknown endpoint_type`。这类坑点要改成 `scope: "platform"`。
- **改 Apify 入参前先跑 `python scripts/audit_apify_inputs.py`**（只读 schema，0 额度）。它会报缺必填键、键名不存在、editor 形状不符。2026-10-09 首次运行：118 个端点里 33 个不合格（17 个缺必填键，直接 400）。取默认值用 `inputSchema.properties[key].prefill`，不要用 `exampleRunInput`（常是 `{"helloWorld":123}` 占位）。
- **`editor` 决定值的形状**：`requestListSources` 要 `[{"url": ...}]`，`stringList` 要裸字符串数组。传错形状即使值本身合法也报 `... do not contain valid URLs`。`minimum`/`maximum`/`enum` 也要照抄——`limit`、`max_posts` 常有 `minimum: 10`。
- **`max_total_charge_usd` 不是限流开关**：调小会让按事件计费的 Actor 直接 `ABORTED`，而不是少返回几条。要限流用入参里的数量字段。
- **排查 degraded 端点的顺序**：① 先读 400/422 的响应体（上游会点名是哪个字段）；② 拿官方 spec 比对路径与方法（TikHub 的 `https://api.tikhub.io/openapi.json` 免鉴权）；③ 确认参数真的传到了上游；④ "成功但 0 条"再去比原始响应形状。详见 [运行手册](./docs/workflows/workflow-console-capability-live-verification-stable.md)。
- **`_validate_*_config` 的白名单会静默丢参数**：它必须覆盖 collector 实际读取的所有键，否则那些键变成空串，上游报一个看不出原因的参数错误。TikHub 已补 27 个键并有回归测试 `tests/unit/test_tikhub_param_contract.py`；其它 collector 同理。
- **第三方库的位置参数与返回类型要核对**：`AutoScraper.build()` 的第一个位置参数是 `url`（传 HTML 会触发 `requests.get(HTML)`），`get_result()` 返回 `(similar, exact)` 二元组。
- **TikHub 有 POST-only 端点**：走 GET 会得到 405/422；新增端点时先查 spec 的方法。
- **坑点写错端点名会被静默丢弃吗**：不会了。`builder` 现在对"target 命中不了任何端点"和"坑点文件 platform_id 对不上平台包"**直接报错**（2026-10-09 前是静默忽略，写错的坑点会看起来已沉淀却从不出现）。
- **quick-collect 一定会落库**：`QuickCollectRequest` **没有** `save_records` 开关，传了也被忽略——每次调用都会建 `Source`+`CollectionTask`+`TaskRun` 并**保存 `RawRecord`**（实测一次全量扫描留下 265 组运行 / 565 条记录）。做扫描时用 `label` 打 `[test]` 前缀以便回收，别指望"不保存"。
- **quick-collect 曾把 `endpoint_type` 从任务 config 里剥掉**：各 `_validate_*_config` 返回白名单字典，只留采集参数；而数据集平台归因（`_dataset_origin_signals`）靠 `task.config["endpoint_type"]` 取端点。结果：quick-collect 存出的数据集 `platforms=[]`，永远落到粗分类兜底（2026-10-09 已修：`validated.setdefault("endpoint_type", ...)`，quick_collect.py）。判断旧数据是否受影响：列表接口 `platforms` 为空但 `collector_types` 非空，且该版本血缘里的任务建于修复前。
- **实测证据只认精确 label**：`/providers/status` 与 `/collectors/docs` 的证据来自 task name 匹配 `^\[quick\](?: \[quick\])? \[test\] (.+)$`，捕获组就是 `endpoint_type`。label 写成 `[test] 冒烟 <ep>` 之类会被**静默忽略**，状态看起来从未测过。要刷新某个端点的真值，label 必须**恰好**是 `[test] <endpoint_type>`。
- **新 provider key 只写 `.env.production` 不生效**：`configs/deploy/scrapy/docker-compose.yml` 的 api 服务用**显式 `environment:` 列表**注入变量，`--env-file` 只用于列表里那些 `${VAR:-}` 的插值。2026-10-09 前 `FIRECRAWL_API_KEY`（以及 bestblogs/blackbird/twscrape/browser_use 那几组）不在列表里，写进 env 文件也到不了容器。排查手法：`docker exec <api> python -c "import os;print(bool(os.environ.get('X')))"`。已补全（commit `fix(deploy): inject the provider keys the collectors read`）。
- **`product-dataset-save` 只认 `ecommerce_product_page` 一种记录**：`_product_page_records` 与 `_raw_record_extracted_fields` 都只认 `ecommerce_product_page` 采集器的输出（它才产 `content["extracted_fields"]`）。真实 Apify 电商端点产出的是 `amazon_product` / `walmart_product` / `ecommerce_product`，content 只有 `{"provider","platform","actor_id","text","raw"}`。因此**真实 Apify 电商采集无法落成商品数据集**：`product-dataset-preview` 返回 `rows=0`、`matched=0/N`。要验证商品数据集路径，用免费的 `ecommerce_product_page` 端点抓带 JSON-LD/microdata 的公开商品页（实测 `books.toscrape.com` 只有 7% 完整度——该站无结构化标记；`scrapeme.live/shop/<name>/` 有 JSON-LD，完整度 79%）。把 Apify 商品记录接进数据集需要新增字段映射层，属未实现功能。
- **MCP 鉴权**：`SCRAPY_MCP_TOKEN=`（空串）曾被当成有效 token，导致 `/mcp/` 对所有人 401（2026-10-09 已修）。生产要用 MCP 就必须**显式设置**一个非空 `SCRAPY_MCP_TOKEN`（或 `SCRAPY_MCP_TOKENS_JSON`）；不设置则中间件放行（等价开放）。
- **回归**：改 collector 前先枚举调用点（无 GitNexus 时 `grep -rn <symbol> apps/api/src`）；改完跑 `cd apps/api && uv run pytest -q`，只允许出现 `deploy/scrapy-luteos-rebuild` 既有基线内的失败。

---

## 设计规范（改 UI 前必读）

- 设计 token：`opendesign/design-systems/data-intelligence-product/tokens/colors_and_type.css`
- 设计规范：`opendesign/design-systems/data-intelligence-product/DESIGN.md`
- **禁止** emoji 出现在 UI 中（DESIGN.md §10）
- **禁止** 彩色渐变卡片、glassmorphism（DESIGN.md §12）
- 平台图标用 `PlatformLogo` 组件（letter badge），方法/内容类型用 Lucide 图标
- 所有颜色使用 `var(--token-name)`，不得写 raw hex

---

<!-- gitnexus:start -->
## GitNexus — 代码图谱（可选）

项目已被 GitNexus 索引为 **data_achieve**。改动前可用以下工具评估影响：

- `impact({target: "symbolName", direction: "upstream"})` — 评估改动影响范围
- `context({name: "symbolName"})` — 查看符号的调用者/被调用者
- `query({search_query: "concept"})` — 按语义搜索执行流

> GitNexus 索引可能已过时。运行 `node .gitnexus/run.cjs analyze` 刷新。
<!-- gitnexus:end -->
