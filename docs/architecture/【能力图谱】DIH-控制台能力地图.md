---
name: dih-console-capability-map
description: Data Intelligence Hub 采集控制台能力图谱，逐页映射页面能力、后端入口与生产实测状态。当核对站点能力边界、排查死链或评估采集覆盖率时使用。
---

# Data Intelligence Hub 控制台能力图谱

> 站点：`https://scrapy.luteos.com` · 采集后端：`apps/api/src/data_intelligence_hub` · 控制台：`apps/scraper-console`
> 首次测绘：2026-10-09（基于生产实测，见 [测试计划](../playbooks/【测试计划】DIH-平台采集生产实测.md)）

## 1. 概览

| 指标 | 值 |
|---|---|
| 生产域名 | `https://scrapy.luteos.com`（控制台）· `/api/*`（FastAPI）· `/mcp/`（共享 MCP） |
| 部署分支 | `deploy/scrapy-luteos-rebuild` |
| catalog 条目 | 278（266 verified + 12 disabled） |
| 唯一端点 | 250（按 endpoint_type 去重；非 disabled 的去重端点 249） |
| 平台（Skill 包） | 74 |
| collector group | 36 |
| **生产实测状态（2026-10-09）** | `GET /api/collectors/docs` → `tested_endpoints=0`；`/api/platform-packages/providers/status` 全部 `last_test_status=null` |

> ⚠️ **既有能力声明 ≠ 实测可用**。测绘当日 catalog 里 266 个端点标 `verified`，但平台从未记录过任何一条真实测试结果；本轮全量实测（249 唯一端点）显示仅 **101 个真正返回数据**。`/collector-docs` 与 `/skills` 详情页的"验证比例/最近测试"在此之前一直是空的。

## 2. 页面清单

| 页面 | route | 关键组件 | 后端 API | 数据来源 | 状态 |
|---|---|---|---|---|---|
| 平台能力中心 | `/platforms` | `app/platforms/page.tsx`、`components/platforms/quick-collect-drawer.tsx` | `GET /api/collectors/catalog`、`POST /api/quick-collect`、`GET /api/projects` | 静态 catalog + 运行任务 | live |
| Skill 与 MCP 目录 | `/skills` | `components/skills/skills-directory.tsx` | `GET /api/platform-packages`、`/providers/status` | 生成器产物 | live |
| Skill 详情 | `/skills/[platformId]` | `components/skills/skill-detail.tsx` | `GET /api/platform-packages/{id}`、`/{id}/playbook`、`/{id}/release`、`/{id}/download` | 生成器产物 + 策展坑点 | live |
| 我的项目 | `/projects` | `app/projects/page.tsx` | `GET/POST /api/projects` | DB | live |
| 项目详情 | `/projects/[id]` | `app/projects/[id]/page.tsx` | `GET /api/projects/{id}` | DB | 部分占位（"采集任务/最近运行/数据集"为静态占位；链接到不存在的 `/tasks/new`） |
| 运行记录 | `/runs` | `app/runs/page.tsx` | `GET /api/tasks/runs`、`GET /api/raw-records?task_run_id=` | DB | live |
| 采集结果 | `/collect/[run_id]` | `app/collect/[run_id]/page.tsx` | `GET /api/raw-records?task_run_id=` | DB | live（但**无任何入口链接**） |
| 数据集 | `/datasets` | `app/datasets/page.tsx` | `GET /api/automation/product-datasets`、`POST/GET /api/automation/product-dataset-exports` | DB + 异步导出 | live |
| 采集文档 | `/collector-docs` | `app/collector-docs/page.tsx` | `GET /api/collectors/docs` | catalog + 最近 `[test]` TaskRun | live（实测前"最近测试"全空） |
| 凭证配置 | `/settings/credentials` | `app/settings/credentials/page.tsx` | `GET/PUT/DELETE /api/settings/platform-credentials` | DB（需 `PLATFORM_CREDENTIAL_MASTER_KEY`） | live |
| 洞察面板 | `/insight/dashboard`（外链） | `components/layout/sidebar.tsx` | — | — | **死链 404** |
| 采集任务 | `/tasks`（不在导航） | `app/tasks/page.tsx` | `GET /api/tasks`、`POST /api/tasks/{id}/run` | DB | live |
| 工作台 | `/dashboard` | `app/dashboard/page.tsx` | — | 硬编码 | stub 占位 |
| 原始数据 | `/raw-records` | `app/raw-records/page.tsx` | — | — | stub 占位 |
| 账户设置 | `/settings/account` | `app/settings/account/page.tsx` | — | — | stub 占位 |
| 共享 MCP | `/mcp/` | — | `mcp_runtime/server.py`（5 工具） | 复用 catalog | live（Bearer `SCRAPY_MCP_TOKEN`） |

## 3. 平台能力矩阵

### 3.1 `/platforms` 平台能力中心

| 能力 | 用户动作 | backing endpoint(s) | collector_type | 实测 |
|---|---|---|---|---|
| 浏览全部采集能力 | 分类标签 + 搜索 | `GET /api/collectors/catalog` | 全部 36 组 | 静态声明 266 verified |
| 单端点采集 | Quick Collect 抽屉提交 | `POST /api/quick-collect` | `_ENDPOINT_TO_COLLECTOR` 映射 | 见 §4 |
| 批量采集 | 逐端点串行触发 | `POST /api/quick-collect` ×N | 同上 | 消耗额度 |
| 选择归属项目 | 抽屉内项目下拉 | `GET /api/projects` | — | live |

### 3.2 `/skills` 与 `/skills/[platformId]`

| 能力 | backing | 说明 |
|---|---|---|
| 平台工具包目录 | `GET /api/platform-packages` | 74 平台 / 278 能力视图 / 250 唯一端点 |
| 实时可用性 | `GET /api/platform-packages/providers/status` | 依赖 `task_runs` 证据；实测前全为 `verified`（**误导**） |
| 平台详情 | `GET /api/platform-packages/{id}` | 含能力表、参数、**策展坑点 `platform_notes` / `notes`** |
| Playbook | `GET /api/platform-packages/{id}/playbook` | 请求时实时渲染（含「坑点与规避」） |
| 发布元数据 | `GET /api/platform-packages/{id}/release` | version = `1.0.0+{digest[:12]}`、ZIP SHA-256 |
| 下载 Skill ZIP | `GET /api/platform-packages/{id}/download` | `application/zip` |

### 3.3 MCP `/mcp/`

工具：`list_platforms`、`list_capabilities`、`describe_capability`、`get_playbook`、`collect`。
`collect` 复用服务端 quick-collect 服务层；`get_playbook` 返回含坑点的 Markdown；`describe_capability` 返回带 `notes` 的端点。
鉴权：`Bearer SCRAPY_MCP_TOKEN`（未配置时中间件放行，生产必须配置）；限流见 `mcp_runtime/runtime.py`（`SCRAPY_MCP_RATE_PER_MINUTE` / `CONCURRENT_CALLS` / `DAILY_COLLECTS`）。

## 4. 生产实测结果（2026-10-09）

对 249 个唯一非 disabled 端点各跑一次 `POST /api/quick-collect`（`label=[test] <endpoint_type>`）：

| failure_class | 数量 | 含义 | 典型 |
|---|---|---|---|
| ok | 101 | 返回 ≥1 条记录 | github、apify 多数、tikhub 热点类 |
| empty_records | 55 | 成功但 0 条 | **已定位：不是演示参数不足，是归一化形状过时**（YouTube `data.contents`、Reddit `data.search` 由 list 变 dict，`_extract_items` 静默返回空列表）；其余见下 |
| upstream_4xx | 23 | 上游 4xx | apify 反爬 403（pinterest/telegram/1688/shopify）、tikhub 400/422 |
| config_gated | 23 | 缺配置 | Exa×16、firecrawl×2、twscrape×3、anycrawl(bing/baidu)×2 |
| params_invalid | 12 | 入参/上游 schema 不符 | apify 1688/alibaba/shopify/rag；tikhub 少量 |
| network_proxy | 11 | 出口不可达 | bilibili/weibo/zhihu/kuaishou（生产 IP 直连超时） |
| request_error | 7 | 客户端超时/异常 | aliens_eye×6、apify_google_ai_overviews |
| container_missing | 5 | 镜像缺依赖 | playwright×3、anydoc(PDF deps)、browser_use |
| actor_failed | 5 | Apify actor run FAILED | reddit/booking/bluesky/amazon_bsr/amazon_competitor |
| timeout / rate_limit | 2 | — | aliens_eye_domain / anysearch_tag_search |

### 4.1 上线后（2026-10-09，分支 `feat/live-capability-verification-sink-notes`，生产 commit `b771909`）

| 指标 | 上线前 | 上线后 |
|---|---|---|
| `/api/collectors/docs` | `tested=0, success=0` | `tested=273/278, success=191` |
| `/providers/status` | 全部 `verified`（无证据也报 verified） | `verified 108 / degraded 59 / empty 55 / config-gated 26 / untested 1 / disabled 1` |
| 坑点渲染 | 无 | 平台 playbook 含「坑点与规避」（`web` 的 `platform_notes=8`） |
| `/mcp/` | **对所有人 401，完全不可用** | 无 token 401；带 token 5 工具全通，`collect` 实测返回记录 |
| 4 个 "not available" 端点 | 400 | 可执行（转为 config/param 类错误） |

> 语义：`verified` = 最近一次 `[test]` 运行成功**且返回 ≥1 条记录**；`empty` = 运行成功但 0 条；`degraded` = 最近失败；`untested` = 无证据；`config-gated` = 缺 Provider 配置。

### 4.2 空记录根因修复（2026-10-09，生产 commit `b4c1015`）

上一节的 `empty_records=55` 经原始响应比对，**首因不是参数**：TikHub 上游把搜索结果由 list 改成了 dict。

| 端点 | 修复前 | 修复后 | 状态 |
|---|---|---|---|
| `tikhub_youtube_search` | `success` / 0 条 | `success` / **17 条** | `empty` → `verified` |
| `tikhub_reddit_search` | `success` / 0 条 | `success` / **7 条** | `empty` → `verified` |

修复方式：`_extract_items` 增加 `_deep_find_dicts`（找 `videoRenderer`）/ `_deep_find_typename`（找 `SearchPost`）深度查找兜底，
并按平台新增 `_normalize_youtube_video` / `_normalize_reddit_post`（Reddit 字段名是 `postTitle` / `content.markdown` / `authorInfo.name`，通用归一化器认不出）。

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `/providers/status` | `verified 108 / empty 55` | `verified 110 / empty 53` |

### 4.3 全量重扫（清理 `[test]` 证据后的重建，2026-10-09 第二次）

`[test]` 运行记录清理后证据归零，重跑 `scripts/verify_platform_live.py` 全量（249 端点）重建：

| 指标 | 值 |
|---|---|
| `/api/collectors/docs` | `tested=277/278, success=189` |
| `/providers/status` | `verified 112 / degraded 62 / empty 49 / config-gated 26 / disabled 1` |
| `tikhub_youtube_search` | `verified`（12 条） |
| `tikhub_reddit_search` | `verified`（7 条） |

剩余 `empty_records=49` 的分布（待后续按"先看原始响应"的方法逐个归因，不再默认是参数问题）：
tiktok×11、douyin×4、linkedin×3、web(robin)×3、youtube/threads/lemon8/reddit/x/bilibili/zhihu×各2、
instagram/kuaishou/duckduckgo×1、apify 电商/地图类×10。

> 同类风险仍在：`x` / `xiaohongshu` / `instagram` / `douyin` 等平台同样按固定路径取 `data.*`，上游改版会以完全相同的方式静默返回空。
> 排查这类"成功但 0 条"时**先取原始响应**（服务器上用 `TIKHUB_API_KEY` 直接 curl 上游），不要反复调 `params`。
> 另：证据只认 label 恰好为 `[test] <endpoint_type>` 的运行（正则 `^\[quick\](?: \[quick\])? \[test\] (.+)$`）。
> label 格式一旦漂移，实测结果会被**静默忽略**，状态看起来从未测过。

## 5. Catalog ↔ 页面覆盖

- **有 catalog 定义但无 UI 入口**：所有 `/tasks`（未进导航）、`/collect/[run_id]`（无链接）、`/dashboard` `/raw-records` `/settings/account`（stub）。
- **有 UI 但无真实后端**：`/projects/[id]` 的"采集任务/最近运行/数据集"段、TopBar 的 ⌘K 命令搜索（无功能）。
- **死链**：`/insight/dashboard`（导航外链，404）。
- **端点 → 页面**：全部 278 条都经 `/platforms`（catalog）与 `/skills/[platform]`（平台包）双路径暴露；`/collector-docs` 暴露文档 + 最近测试。

## 6. 死链与桩面清单

| 位置 | 现象 | 备注 |
|---|---|---|
| `sidebar.tsx:19` `INSIGHT_URL=/insight/dashboard` | 404 | 该页可能属 `apps/web`，需先确认引用来源再决定是否补路由 |
| `/projects/[id]` → `/tasks/new` | 目标路由不存在 | 死链 |
| `/dashboard` `/raw-records` `/settings/account` | "建设中"占位 | 非导航入口 |
| `/skills` 详情"验证比例" | 实测前恒为空/误导 | 本轮修复 `providers/status` 语义 + 跑实测后可读 |

## 7. 维护方式

1. 更新本图谱的**实测列**：跑 `scripts/verify_platform_live.py`（见测试计划），把 `reports/live-sweep/latest.json` 的 `summary` 粘贴到 §4。
2. 页面清单变化时同步 §2；新增/删除端点由 catalog 自动反映，无需手改 §3。
3. 坑点在 `apps/api/src/data_intelligence_hub/platform_packages/notes/*.json` 维护，会自动渲染进 Skill/Playbook 与控制台详情页。
