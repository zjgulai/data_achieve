---
name: data-intelligence-hub-agent-guide
description: Data Intelligence Hub Agent 工程协作指南，涵盖项目定位、当前生产速查、关键代码、采集能力接入、实测坑点、验证和发布约束。当 AI Agent 或开发者修改本仓库时使用。
---

# Data Intelligence Hub — Agent 工作指南

> 最后更新：2026-10-11。生产环境易变事实以 [生产环境基线](docs/【运维手册】生产环境基线.md) 为准。

## 项目定位

Data Intelligence Hub 是纯数据采集平台。FastAPI 后端提供统一 catalog、quick-collect、任务调度、平台 Skill 和 MCP Runtime。Next.js `scraper-console` 提供生产采集管理台。

当前产品口径：

- 70 个平台。
- 270 个能力视图。
- 242 个唯一 endpoint。
- Catalog 静态声明：258 verified / 12 disabled。
- 实测状态（`providers/status` 的 `availability`）：191 verified、21 config-gated、20 degraded、9 empty、1 disabled。
- 生产主域名：`https://scrapy.luteos.com`。

## 当前生产速查

| 项目 | 当前值 |
|---|---|
| 腾讯云主机 | `ubuntu@43.163.92.244` |
| 密钥 | 仓库根目录 `zhoujian_pachong.pem`（**不得 commit**）|
| 项目路径 | `/opt/data-achieve-scrapy/app` |
| 环境变量 | `/opt/data-achieve-scrapy/.env.production` |
| 部署分支 | `feat/live-capability-verification-sink-notes` |
| Compose | `configs/deploy/scrapy/docker-compose.yml` |
| Compose 项目 | `data_achieve_scrapy` |
| 数据库 schema | `202607280044` |
| 共享网关 | `ai_video_nginx` |
| 外部网络 | `lighthouse_ai_video_net` |
| Edge 别名 | `data_achieve_scrapy_proxy` |

不要在本文固定当前 commit。需要时现场读取：

```bash
git -C /opt/data-achieve-scrapy/app rev-parse HEAD
```

生产拓扑、容器与数据卷见 [生产环境基线](docs/【运维手册】生产环境基线.md)。

## 关键代码

```text
apps/api/src/data_intelligence_hub/
├── collectors/                   ★ 采集器实现
│   ├── base.py                   — BaseCollector 基类与结果模型
│   ├── registry.py               ★ COLLECTOR_REGISTRY 注册表
│   ├── tikhub_social.py          — TikHub 社交采集
│   ├── apify_actor.py            — Apify Actor 采集
│   ├── public_feed.py            — RSS + Web crawl + AutoScraper
│   ├── github_repo.py / github_topic.py
│   ├── playwright_browser.py     — 浏览器采集（text/html/screenshot）
│   ├── ecommerce_product_page.py / ecommerce_product_discovery.py
│   ├── exa_collector.py          — Exa 搜索与内容
│   ├── anysearch_collector.py    — AnySearch API
│   ├── jina_reader.py            — Jina Reader（需代理）
│   ├── firecrawl_collector.py    — Firecrawl 全站采集
│   ├── spiderfoot_collector.py   / spiderfoot_extended_collectors.py
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
│   ├── quick_collect.py          ★ _ENDPOINT_TO_COLLECTOR 映射 + Apify 缺省入参
│   ├── platform_packages.py      — 平台 Skill 包与 Provider 状态
│   └── ...
├── services/
│   └── collector_catalog.py      ★ CollectorDefinition + _validate_* 函数
├── platform_packages/            — 平台包生成与渲染（notes/ 是坑点单一事实源）
├── mcp_runtime/                  — 共享 MCP Runtime
└── agents/tiktok_cdo/            — TikTok CDO 飞书入口

apps/scraper-console/src/
├── app/platforms/                ★ 平台能力中心（PLATFORM_LOGOS / 分类 / 方法）
├── app/skills/                   — Skill 与 MCP 目录
├── app/projects/                 — 项目管理
├── app/tasks/                    — 任务管理
├── app/runs/                     — 运行记录
├── app/raw-records/              — 原始数据
├── app/datasets/                 — 数据集
└── components/platforms/         — 快速采集抽屉

configs/deploy/scrapy/
├── docker-compose.yml            ★ 当前生产编排（含 provider keys 显式 environment 列表）
└── edge-nginx.conf               — 项目 edge 路由

configs/bridges/
├── spiderfoot-bridge/
└── mediacrawler-bridge/
```

## 新增采集能力

### 1. 实现 collector

在 `apps/api/src/data_intelligence_hub/collectors/` 新建或扩展 collector，继承 `BaseCollector`，返回 `CollectionResult`。

```python
from .base import BaseCollector, CollectionResult, RawRecord

class YourCollector(BaseCollector):
    async def collect(self) -> CollectionResult:
        # self.config 包含前端传入的参数
        url = self.config.get("url", "")
        record = RawRecord(content={"key": "value"}, metadata={})
        return CollectionResult(raw_records=[record], errors=[])
```

### 2. 注册 collector

在 `collectors/registry.py` 注册 collector type。

```python
from .your_collector import YourCollector
COLLECTOR_REGISTRY["your_collector"] = YourCollector
```

### 3. 添加 catalog endpoint

在 `api/routes/collectors.py` 添加 `CollectorEndpoint`，明确 `endpoint_type`、`platform`、`method`、`content_type`、`status`、`required_params`、`optional_params`、`provider`。

```python
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

### 4. 对齐 quick-collect

在 `api/routes/quick_collect.py` 添加 `_ENDPOINT_TO_COLLECTOR` 映射、必要的 `_COLLECTOR_TEST_DEFAULTS`，以及 Apify endpoint 的缺省入参。

```python
"your_endpoint_name": ("your_collector", {"url": "url"}),
```

### 5. 添加配置校验

在 `services/collector_catalog.py` 添加或复用 `_validate_*_config`。白名单必须覆盖 collector 实际读取的**所有**键，否则那些键会静默变成空串。

```python
def _validate_your_config(params: dict) -> dict:
    url = params.get("url", "").strip()
    if not url:
        raise ValueError("url is required")
    return {"url": url}
```

### 6. 同步平台包与前端

新增平台或参数形态时同步：

- `configs/platform-packages.lock.json`（用 `--update-lock` 重新生成）
- 平台包生成测试
- `apps/scraper-console` 平台 Logo、分类或参数表单
- 相关 Playbook 和测试用例

```typescript
// apps/scraper-console/src/app/platforms/page.tsx
your_platform: { bg: "#XXXXXX", fg: "#fff", letter: "XX" },
// 并在 PLATFORM_GROUP_META 对应分组的 platforms[] 里登记
```

### 7. 验证

```bash
cd apps/api
uv run ruff check <changed-paths>
uv run mypy <changed-paths>
uv run pytest <focused-tests>

cd ../../
pnpm --dir apps/scraper-console test
pnpm --dir apps/scraper-console exec tsc --noEmit
pnpm --dir apps/scraper-console build
```

---

## 平台采集实测与坑点体系（2026-10-09 起）

- **能力总账（先读这份）**：`docs/architecture/【能力总账】DIH-平台能力现状与维护手册.md`
  （可用/缺配置/上游故障/恒空端点清单、现状快照、维护方法、待补清单）
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
- **Apify Actor 会下架**：2026-10-09 巡检时它含 118 个端点 / 103 个 distinct Actor，其中 **25 个已下架 + 2 个被标废弃**（对应 28 个 endpoint_type，已改指存活 Actor）。下架后调用一律返回 403（**不是** 404），极易误判为反爬。改 Actor 时三处要一起动：`_APIFY_ENDPOINT_DEFAULTS`、`scripts/collector_demo_params.py`、`api/routes/collectors.py` 的 `provider`/`required_params`。巡检方法（免额度、不产生 run）见 [运行手册](./docs/workflows/workflow-console-capability-live-verification-stable.md)。
- **quick-collect 能跑的端点必须等于目录里有的端点**（2026-10-10 已收敛为相等）：此前 `_APIFY_ENDPOINT_DEFAULTS` 有 118 个而 catalog 只暴露 87 个 Apify 端点，多出的 31 个"幽灵端点"无人可发现却照样消耗额度，已全部删除。现在两边都是 **79 个**，回归测试 `tests/unit/test_quick_collect_apify_input.py` 双向钉住集合相等。**历史副作用**：幽灵端点没有平台包，所以它**不能挂 endpoint 级坑点**——写 `notes/<platform>.json` 时 `builder` 会直接报 `target unknown endpoint_type`，这类坑点只能写 `scope: "platform"`。
- **改 Apify 入参前先跑 `python scripts/audit_apify_inputs.py`**（只读 schema，0 额度）。它会报缺必填键、键名不存在、editor 形状不符。2026-10-09 首次运行（当时 118 个端点）报 33 个不合格，其中 17 个缺必填键会直接 400。取默认值用 `inputSchema.properties[key].prefill`，不要用 `exampleRunInput`（常是 `{"helloWorld":123}` 占位）。
- **`editor` 决定值的形状**：`requestListSources` 要 `[{"url": ...}]`，`stringList` 要裸字符串数组。传错形状即使值本身合法也报 `... do not contain valid URLs`。`minimum`/`maximum`/`enum` 也要照抄——`limit`、`max_posts` 常有 `minimum: 10`。
- **`max_total_charge_usd` 不是限流开关**：调小会让按事件计费的 Actor 直接 `ABORTED`，而不是少返回几条。要限流用入参里的数量字段。
- **排查 degraded 端点的顺序**：① 先读 400/422 的响应体（上游会点名是哪个字段）；② 拿官方 spec 比对路径与方法（TikHub 的 `https://api.tikhub.io/openapi.json` 免鉴权）；③ 确认参数真的传到了上游；④ "成功但 0 条"再去比原始响应形状。详见 [运行手册](./docs/workflows/workflow-console-capability-live-verification-stable.md)。
- **`_validate_*_config` 的白名单会静默丢参数**：它必须覆盖 collector 实际读取的所有键，否则那些键变成空串，上游报一个看不出原因的参数错误。TikHub 已补 27 个键并有回归测试 `tests/unit/test_tikhub_param_contract.py`；其它 collector 同理。
- **第三方库的位置参数与返回类型要核对**：`AutoScraper.build()` 的第一个位置参数是 `url`（传 HTML 会触发 `requests.get(HTML)`），`get_result()` 返回 `(similar, exact)` 二元组。
- **TikHub 有 POST-only 端点**：走 GET 会得到 405/422；新增端点时先查 spec 的方法。
- **坑点写错端点名会被静默丢弃吗**：不会了。`builder` 现在对"target 命中不了任何端点"和"坑点文件 platform_id 对不上平台包"**直接报错**（2026-10-09 前是静默忽略，写错的坑点会看起来已沉淀却从不出现）。
- **quick-collect 一定会落库**：`QuickCollectRequest` **没有** `save_records` 开关，传了也被忽略——每次调用都会建 `Source`+`CollectionTask`+`TaskRun` 并**保存 `RawRecord`**（2026-10-09/10 两轮全量扫描累计留下 265 组运行 / 565 条记录）。做扫描时用 `label` 打 `[test]` 前缀以便回收，别指望"不保存"。
- **quick-collect 曾把 `endpoint_type` 从任务 config 里剥掉**：各 `_validate_*_config` 返回白名单字典，只留采集参数；而数据集平台归因（`_dataset_origin_signals`）靠 `task.config["endpoint_type"]` 取端点。结果：quick-collect 存出的数据集 `platforms=[]`，永远落到粗分类兜底（2026-10-09 已修：`validated.setdefault("endpoint_type", ...)`，quick_collect.py）。判断旧数据是否受影响：列表接口 `platforms` 为空但 `collector_types` 非空，且该版本血缘里的任务建于修复前。
- **实测证据只认精确 label**：`/providers/status` 与 `/collectors/docs` 的证据来自 task name 匹配 `^\[quick\](?: \[quick\])? \[test\] (.+)$`，捕获组就是 `endpoint_type`。label 写成 `[test] 冒烟 <ep>` 之类会被**静默忽略**，状态看起来从未测过。要刷新某个端点的真值，label 必须**恰好**是 `[test] <endpoint_type>`。
- **新 provider key 只写 `.env.production` 不生效**：`configs/deploy/scrapy/docker-compose.yml` 的 api 服务用**显式 `environment:` 列表**注入变量，`--env-file` 只用于列表里那些 `${VAR:-}` 的插值。2026-10-09 前 `FIRECRAWL_API_KEY`（以及 bestblogs/blackbird/twscrape/browser_use 那几组）不在列表里，写进 env 文件也到不了容器。排查手法：`docker exec <api> python -c "import os;print(bool(os.environ.get('X')))"`。已补全（commit `fix(deploy): inject the provider keys the collectors read`）。
- **商品记录有两种来源，字段取法不同**（2026-10-09 修复后）：
  1. 自研 `ecommerce_product_page` 采集器**直接写** `content["extracted_fields"]`，字段名就是 `ECOMMERCE_PRODUCT_FIELDS`。
  2. Apify 电商 actor 写 actor 自己的 item 形状：`content = {provider, platform, actor_id, schema_version, text, raw}`，**没有 `extracted_fields`**。
  记录类型白名单是 `PRODUCT_RECORD_TYPES`（`ecommerce_product_page` / `amazon_product` / `walmart_product` / `ecommerce_product`）；`_raw_record_extracted_fields` 对 `provider == "apify"` 且 `raw` 是 dict 的记录走 `_marketplace_extracted_fields` 别名映射，其余无 `extracted_fields` 的记录返回 `{}`（github、feed 不受影响）。
  **历史坑**：修复前只认 `ecommerce_product_page`，真实 Apify 电商采集落不了数据集（`product-dataset-preview` 返回 `rows=0`、`matched=0/N`）。别名表见 `_MARKETPLACE_PRODUCT_ALIASES`；实测 Amazon actor 的 `price` 是嵌套 `{value, currency}`、`brand` 藏在 `productOverview` 的 `key/value` 列表里、`inStock` 布尔对应 `availability`（原文归 `availability_detail`）。
  **`product` 记录类型不属于商品**：那是包注册表（npm/PyPI/Go 等）的条目，别加进 `PRODUCT_RECORD_TYPES`。
  验证商品页路径可用免费的 `ecommerce_product_page` 端点抓带 JSON-LD/microdata 的公开页（实测 `books.toscrape.com` 仅 7% 完整度——无结构化标记；`scrapeme.live/shop/<name>/` 有 JSON-LD，79%）。
- **MCP 鉴权**：`SCRAPY_MCP_TOKEN=`（空串）曾被当成有效 token，导致 `/mcp/` 对所有人 401（2026-10-09 已修）。生产要用 MCP 就必须**显式设置**一个非空 `SCRAPY_MCP_TOKEN`（或 `SCRAPY_MCP_TOKENS_JSON`）；不设置则中间件放行（等价开放）。
- **回归**：改 collector 前先枚举调用点（无 GitNexus 时 `grep -rn <symbol> apps/api/src`）；改完跑 `cd apps/api && uv run pytest -q`。当前基线允许 **4 个**已知失败：`test_firecrawl_collector::test_test_fails_without_api_key`、`test_spiderfoot_collector::TestValidateConfig::test_valid_target`、`test_v2_traceability`、`test_workflow_executor_postgres_guard`。

---

---

## 设计规范（改 UI 前必读）

- 设计 token：`opendesign/design-systems/data-intelligence-product/tokens/colors_and_type.css`
- 设计规范：`opendesign/design-systems/data-intelligence-product/DESIGN.md`
- **禁止** emoji 出现在 UI 中（DESIGN.md §10）
- **禁止** 彩色渐变卡片、glassmorphism（DESIGN.md §12）
- 平台图标用 `PlatformLogo` 组件（letter badge），方法/内容类型用 Lucide 图标
- 所有颜色使用 `var(--token-name)`，不得写 raw hex
- **`src/app/globals.css` 是手工从 token 文件转录的，会漏 token**。2026-10-09 发现它漏了 `--overlay-scrim`，导致 4 处遮罩（两个抽屉、项目页、确认弹窗）`bg-[var(--overlay-scrim)]` 解析失败、完全透明。改 UI 前先 diff 两边的 token 名单：
  `grep -oE "^\s*--[a-z0-9-]+" <token文件> | sort -u` 对比 `... src/app/globals.css | sort -u`，再对差异项 `grep -rn "var(--x)" src/` 确认是否被引用。

---

---

## 当前配置依赖

代码已支持、但生产效果依赖 secrets 或外部服务的能力：

| 能力 | 配置 |
|---|---|
| MediaCrawler（B站/微博/知乎/快手）| `MEDIACRAWLER_BASE_URL` 与各平台 cookies |
| AnyCrawl SERP（百度/Bing/DDG）| `ANYCRAWL_BASE_URL` |
| twscrape | `TWITTER_ACCOUNTS_JSON` |
| TikHub | `TIKHUB_API_KEY` |
| Apify | `APIFY_API_TOKEN` |
| Exa | `EXA_API_KEY` |
| Firecrawl | `FIRECRAWL_API_KEY` |
| Jina Reader | `JINA_API_KEY` 与可用网络出口 |
| SpiderFoot / Blackbird | `SPIDERFOOT_BASE_URL` / `BLACKBIRD_BASE_URL` |
| Robin 暗网 OSINT | `TOR_PROXY_URL`（Compose 的 `tor` 服务，`socks5h://tor:9050`）|
| MCP | `SCRAPY_MCP_TOKEN` 或 `SCRAPY_MCP_TOKENS_JSON` |
| TikTok CDO | 飞书、DeepSeek 和 demo project 相关变量 |

凭据缺失必须在 Provider 状态或采集结果中明确体现，不得把空结果标记为已验证成功。

新增 provider key 时**只写 `.env.production` 不生效**：api 服务用显式 `environment:` 列表注入变量，`--env-file` 只用于列表里那些 `${VAR:-}` 的插值。漏加时排查手法：

```bash
docker exec <api容器> python -c "import os;print(bool(os.environ.get('X_API_KEY')))"
```

## 关键约束

- `provider_call=false`：业务路由、Agent 和 UI 不得直接调用第三方 Provider，必须经过 collector 抽象层。
- 不新增独立的官方 Reddit 或 YouTube collector；现有 TikHub/Apify 能力保持不变。
- Shopee 直连方案已取消，不恢复被生产 IP 封禁的路径。
- 不得提交 `.env.production`、SSH key、TLS 私钥、API key、Cookie 或账号 JSON。
- 不得删除共享 `lighthouse_ai_video_net`，不得重启无关 Compose 项目。
- `proxy_rotator` 位于显式 profile `proxy`，默认部署不启动。
- 热替换容器文件不是正式发布；下一次部署必须重建镜像。
- 历史 ADR 和执行日志中的旧域名、数量和 revision 是历史证据，不批量改写。

## 发布

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244
cd /opt/data-achieve-scrapy/app
git fetch origin feat/live-capability-verification-sink-notes
git reset --hard FETCH_HEAD
cd configs/deploy/scrapy
ENV=/opt/data-achieve-scrapy/.env.production
docker compose --env-file "$ENV" build api console
docker compose --env-file "$ENV" up -d api console
docker compose --env-file "$ENV" restart edge        # 必须，见下
```

只改 Console 时可 `build console` 加 `up -d --no-deps console`。

**发布四坑**：

1. **必须先 `git push`**。只提交到本地就上服务器发布，服务器会取到旧 commit，表现为"改动完全没生效"。
2. **重建 api 后必须 `restart edge`**。edge 启动时把 api 的 IP 缓存住了，`up -d api` 换新 IP 后 edge 不重解析，外部一律 502，而容器内 `curl http://api:8000/api/health` 仍是 200。
3. **不要用 `git pull`**。服务器上的本地分支没有 upstream，`git pull` 会静默返回 "Already up to date" 而不拉任何提交。用上面的 `fetch` + `reset --hard FETCH_HEAD`。
4. **notes 改动要重建 api**。平台坑点在 api 镜像内，只重建 console 不会生效。

完整步骤和回滚条件见 [发布与回滚清单](docs/workflows/workflow-release-rollback-stable.md)。

## 健康验收

```bash
B=https://scrapy.luteos.com
curl -fsSL $B/api/health
curl -fsSL $B/api/platform-packages | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  print(d['platform_count'], d['capability_count'], d['unique_endpoint_count'])"
# 期望：70 270 242
curl -sS -L -o /dev/null -w '%{http_code}\n' $B/mcp
# 无 Token 期望：401
```

其他真值来源：

- `/api/collectors/docs` → `total_endpoints` / `tested_endpoints` / `success_endpoints`。
- `/api/platform-packages/providers/status` → 逐端点的 `availability`，取值 `verified` / `config-gated` / `degraded` / `empty` / `disabled` / `untested`。

## 文档规范

- 当前生产事实只维护在 [生产环境基线](docs/【运维手册】生产环境基线.md)。
- 新增或重写 Markdown 必须包含 `name`、`description` Frontmatter。
- 业务文档之间使用 Markdown 链接建立关系。
- 历史材料顶部可增加"历史快照"提示，但不改写当时数据。

<!-- gitnexus:start -->
## GitNexus — 代码图谱（可选）

项目已被 GitNexus 索引为 **data_achieve**。改动前可用以下工具评估影响：

- `impact({target: "symbolName", direction: "upstream"})` — 评估改动影响范围
- `context({name: "symbolName"})` — 查看符号的调用者/被调用者
- `query({search_query: "concept"})` — 按语义搜索执行流

> GitNexus 索引可能已过时。运行 `node .gitnexus/run.cjs analyze` 刷新。
<!-- gitnexus:end -->
