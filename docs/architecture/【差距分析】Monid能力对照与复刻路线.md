---
name: monid-dih-gap-analysis
description: DIH 与 Monid 的能力对照与复刻路线。区分网站实测、Monid 开源 connector 源码与托管产品，给出 75 行差距矩阵、P0-P4 路线、超越点与不做项。规划 Agent 体验层、身份计费或目录改版时先读这份。
---

# DIH 与 Monid 能力对照与复刻路线

> 文档类型：差距分析
> 状态：评审稿
> 日期：2026-10-17
> 依据：Monid 网站实测、monid-ai/monid 源码、DIH 当前分支代码与生产实测
> 相关文档：[Monid 网站 UI 与能力逆向](./【逆向报告】Monid网站UI与能力逆向.md) · [DIH 整站能力整合方案](./【技术方案】DIH整站能力整合方案.md) · [DIH 控制台能力地图](./【能力图谱】DIH-控制台能力地图.md)
> 写作规范：[技术写作标准（ASD-STE100 等效）](../standards/writing-standard-ste.md)

## 1. 结论摘要

差距集中在 Agent 体验层，不在采集层。75 行对照中，29 行完全缺失，26 行有但更弱或形态不同。17 行是我们的反向优势，3 行无差距。最关键的三个缺口是身份与租户、运行回执与异步、计费链路。先做 P0：部署当前分支，开放 `/api/tools`、`/tools`、`/docs`、`/connect`。再做 P1 身份统一、P2 回执与最小异步、P3 语义发现与健康投影、P4 计费最小链路。P0-P4 合计 52.5-87 人日。超越点不在工具数量。超越点有六项：合规治理、数据交付链路、平台包、中文资产、数据控制台、无 playground 的反向机会。Monid 托管目录有 2719 个端点。开源仓库只有 32 provider / 719 endpoint。我们不复刻 marketplace 与品牌。首页继续按 monid.ai 网站逆向结果做。源码没有 UI。

## 2. 依据与方法

### 2.1 两套依据各管一段

本文把证据分成两段。两段不能混用。

| 判断对象 | 依据 | 日期与版本 | 不用于 |
|---|---|---|---|
| UI、UX、页面结构、首页版块 | monid.ai 网站实测 | 2026-10-15 逆向报告；2026-10-17 复核 | 不用于推断后端机制 |
| 架构、契约、引擎、计费机制 | monid-ai/monid 源码 | MIT；commit `96e1569dee3a0beee8a6aa8a70ec8c1773e32a21`；提交时间 2026-10-15 20:23:28 -0700；克隆时间 2026-10-17 15:22:06；路径 `/tmp/monid-src-check/monid` | 不用于判断托管产品全貌 |
| 托管 API、目录规模、控制台页面 | 线上 API、docs、app bundle 实测 | 2026-10-17 | 不用于证明源码实现 |
| DIH 代码能力 | `/Users/lute/Project/data_scrapy-p0g` 当前分支 `feat/dih-p0-on-guardrails`，commit `d7afa177255ce8b4377a47ef2623ccf2246c23ad` | 2026-10-17 | 不用于证明生产已部署 |
| DIH 生产形态 | `scrapy.luteos.com` 与 `scrapy.lute-tlz-dddd.top` 实测 | 2026-10-17 | 不用于证明代码不存在 |

首页判断只取网站实测。源码没有 UI。不从源码找首页。用户要求：源码没有 UI 可复刻，所以首页仍按网站逆向的结果做。

### 2.2 源码边界

该仓库只有 connector 层。没有 UI。没有服务端。没有数据库。

实测数字：

```text
find /tmp/monid-src-check/monid -name '*.tsx' | wc -l    -> 0
find /tmp/monid-src-check/monid -name '*.html' | wc -l   -> 0
find /tmp/monid-src-check/monid -name '*.css' | wc -l    -> 0
find /tmp/monid-src-check/monid -name '*.sql' | wc -l    -> 0
grep -rn 'Deno.serve' /tmp/monid-src-check/monid --include='*.ts'
  -> /tmp/monid-src-check/monid/scripts/webhook.ts:490
```

`Deno.serve` 只有 1 处。该处是本地 webhook 调试 ingress。注释说明 engine 不监听端口。

`README.md:28` 原文：

> **This repo is the connector layer**, the one generic framework every endpoint above is described in.

Web 控制台、API 服务、数据库、计费后端在私有仓库 `monid-services`。GitHub API 对 `monid-ai/monid-services` 返回 404。组织公开仓库列表没有它。`AGENT.md:18-20` 指向 `monid-services`。

一个例外：`scripts/store/kv.ts:14-38` 使用 Deno KV，写入 `.output/local.db`。它存 owned resources。它不是服务端数据库。

### 2.3 目录规模

两个口径必须分开写。

| 口径 | provider | endpoint | 证据 |
|---|---|---|---|
| 开源 connector 仓库 | 32 | 719 | `find connectors -name provider.ts` 为 32；`find connectors -name endpoint.ts` 为 719 |
| 托管目录 | 91 | 2719 | `GET https://api.monid.ai/public/v1/stats`，2026-10-17 实测 `{endpointCount:2719,providerCount:91}` |

`README.md:20-21` 的产品口径是 2,000+ tools across 72+ providers。这是产品声明，不是仓库计数。

结论：32/719 只能描述开源 connector 层。不能描述 Monid 产品。本文所有 Monid 规模判断都写两个口径。

### 2.4 证据标记

| 标记 | 含义 |
|---|---|
| 实测 | 命令输出或线上响应 |
| 源码 | `file:line` |
| 文档 | 官方 README、docs 或设计文档 |
| 待核实 | 未复现，不能当事实 |

矩阵中的 `file:line` 均可复核。没有来源的数字不写。估计值只出现在“复刻代价”列。

### 2.5 修正口径

三路校验完成后再写本文。verdict 不是 UPHELD 的条目必须先修正。本文按 correction 改写。OVERTURNED 用 correction 表述。MIXED 收敛到 correction 口径。

主要修正：

| 原判断 | 修正后 |
|---|---|
| 69 行摘要写 14 行反向优势、20 行完全缺失、16 行更弱 | 按当前 gap 字段：反向优势 17、完全缺失 29（23 行主干 + 6 行补录）、更弱或形态不同 26、无差距 3。行17、42 已从反向优势改为更弱 |
| Monid 32 provider / 719 endpoint 与 DIH 70 平台 / 258 端点直接对比 | 开源 32/719；托管 91/2719。规模对比必须写两个口径 |
| 部署在 3 行重复计费，合计 8-11 人日 | 部署只算一次。P0 为 0.5-1 人日 |
| API key 10-15、MCP workspace 10-20、租户 15-30，合计 35-65 | 同一个身份项目。MVP 合计 12-21 人日 |
| 计费 8 行独立相加，合计 46-85 | 同一个 billing kernel。P4 为 21-32 人日 |
| provider_health 有 p95/成功率数据，只缺投影 | 只有 schema 与 fixture kernel。没有 live 写入。要从 TaskRun 新建聚合 |
| get_demo_workspace 有 59 处调用 | 59 是文本引用行数。实际调用 45 处，其中 43 处在路由层 |
| Monid 有 12 个运行/钱包/资源 API | 至少 20 条公开路径：10 条文档化 `/v1` + 2 条 x402 + 3 条 public catalog + 5 条 resources |
| Monid 托管控制台只有 key/预算 | 托管控制台有 wallet、usage、tools、resources、rules 等页面与对应 API |
| Monid 无 UI | 只对开源仓库成立。托管 app 有完整控制台 |
| workflow budget 是现成预算控制 | fixture-only。生产无写入路径。只有 MCP 每日 collect 配额是 live |
| 浏览器自动化、目录治理是 0 成本反向优势 | 行17 只有骨架，默认不可执行。行42 API 未上线，缺 membership seed 与控制台页 |
| 28 个 alias 视图全部被丢弃 | 28 个 alias 视图，27 个丢弃，1 个保留。保留行本身是 alias |
| 12 个 UI 分类 | 含“全部”共 12 项，真实分类 11 项 |

MIT 覆盖代码，不覆盖品牌。复刻 UI 时用自有等效物。不复制 Monid 的图片、logo、`SKILL.md` 文案与营销文案。

## 3. 定位差异

### 3.1 Monid 卖什么

Monid 是面向 AI Agent 的工具调用市场与 broker。

`README.md:18` 标题是 `Monid (OpenRouter for agent tools)`。`README.md:20-21` 写明一个 base URL 与一个 key。它宣称 2,000+ tools across 72+ providers。这是产品声明。

开源层是 connector 标准。作者用 TypeScript/zod 声明 EndpointDoc。编译器产出 bundle。引擎执行 `load -> validate -> toRequest -> buildRequest -> transport -> settle`。仓库内有 1034 个 fixture 文件与 244 个 `.test.ts`（`find connectors -path '*fixtures*' -type f` 与 `find . -name '*.test.ts'`，2026-10-17 实测）。

托管层是 broker。它提供 `discover`、`inspect`、`run`、`runs`、`wallet`、API key、OAuth、MCP 13 个工具与公开目录。

托管计费入口齐全。端到端扣款未验证。本文不把文档当成交付证据。

它的优势是广度聚合、统一契约、按调用结算、Agent 分发。它不是垂直数据源。

### 3.2 DIH 卖什么

DIH 是面向出海业务的垂直数据采集与情报控制台。

当前目录有 70 个平台包与 258 个唯一端点。目录还有 36 个 provider_group 与 286 个能力视图。代码见 `platform_packages/builder.py:37-107` 与 `tool_catalog/projection.py:229-282`。

DIH 有 4 级出站策略：provider_api 28 / guarded_http 4 / offline 1 / unsupported 53。258 个端点按策略分为 197 / 4 / 57。证据见 `collectors/outbound_policy.py:19-118`。

DIH 有授权与确认门控、70 份中文 Playbook、107 条坑点（`notes/*.json` 34 个文件，共 107 条；Playbook 由 `render_playbook` 按平台实时渲染）。DIH 还有 `RawRecord -> Dataset -> DatasetVersion -> DatasetExportJob` 数据交付链路。DIH 也有实体、信号、情报、报告、告警，以及 15 个 App Router `page.tsx`（`find apps/scraper-console/src/app -name page.tsx | wc -l`，2026-10-17 实测）。

它的优势是垂直深度、合规可控、数据产品交付。它不是中立工具路由。

### 3.3 复刻边界

应复刻 Agent 体验层：

- `discover`、`inspect`、`run` 三动词。
- typed contract 与统一校验。
- 价格、健康、延迟。
- 统一运行回执。
- 余额与用量。
- MCP、Skill、API key 接入。

不应复刻：

- marketplace/broker 商业模式。
- 按调用抽成。
- 第三方 connector PR 生态。
- durable resource 租用业务。
- 品牌文案与素材。

现有 [整站能力整合方案](./【技术方案】DIH整站能力整合方案.md) §3 已写明首期不做支付、钱包、CLI。本文的 P4 只在对外自助售卖时启用。内部受邀模式可以停在 P3。

## 4. 差距矩阵

### 4.1 读表说明

- 矩阵共 75 行。69 行来自主干矩阵。6 行是补录。补录行在能力名后标“补”。
- 每个维度内按 `blocker > high > medium > low > none` 排序。
- `blocker` 只在明确场景成立。矩阵在严重度后标注“对外”或“内部”。
- “复刻代价”是单项估算。标“计入 Pn”的行不单独计费。路线按合并后的阶段计费。
- 证据写在 Monid 与“我们”两列。没有来源的数字不写。未知项标“待核实”。

### 4.2 发现

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 发现 | 02 自然语言语义发现与排序 | 托管 `POST /v1/discover` 支持自然语言 query、AI routing、score/scoreBreakdown、price/hints（`https://monid.ai/docs/api/discover.md`，2026-10-17）。源码树没有 discover 排序实现；grep `discover` 只命中 vendor 端点名与文案。`README.md:43-45` 只有声明。 | 仅子串匹配。`api/routes/tools.py:78-89` 对 tool_id、label、description、platform、provider、provider_group 做 casefold contains。`mcp_runtime/server.py:74-99` 同。无评分、无排序。`capability_discovery` 是 fixture preview（`services/capability_discovery/fixture_loader.py:27`）。 | 完全缺失 | high | 词法 3-5；向量 8-15；10-20 只含语义+评测+运维。计入 P3 |
| 发现 | 03 发现结果带结构化价格、健康与延迟 | 价格是公开 API 字段。discover 示例 `price={value:0.003,currency:USD}`（discover.md）。健康与 p50/p95 只有 `README.md:44-45` 声明与 CLI 类型（`monid-ai/cli src/api/types.ts:176-185`）。API 文档未列。源码无实现。 | `cost_hint` 是 str（`schemas/collector_catalog.py:16`）。availability 在 `tool_catalog/public.py:167-173`。`provider_health` 只有 schema 与 fixture kernel（`models/provider_health.py:86-92`）。`record_provider_health_snapshot` 在 src 内 0 调用方；调用方只有集成测试（`tests/integration/test_provider_health_kernel.py`，首个调用在 `:134`）。真实证据是名为 `[quick] [test]` 的 TaskRun 最近一次（`platform_packages/service.py:104-136`）。 | 我们有但更弱 | high | 5-8（从 task_runs 聚合 p50/p95/成功率）。与行55 合并，只计一次。计入 P3 |
| 发现 | 04 单工具 inspect / 完整契约页 | 托管 `POST /v1/inspect` 返回按 body/queryParams/pathParams 分组的 JSON Schema、price、notes（inspect.md）。CLI `catalog inspect <id>` 打印完整 EndpointDoc（`scripts/catalog.ts:62-69`；`shared/core/catalog.ts:70-78`）。 | `GET /api/tools/{id}` 返回 PublicTool（`api/routes/tools.py:54-63`；`tool_catalog/public.py:140-173`）。本机 `tests/integration/test_tools_routes.py` 8 passed。生产 `/api/tools` 404（2026-10-17 实测）。`/tools/[toolId]` 传 platformId 给 SkillDetail（`tools/[toolId]/page.tsx:11-13`），不是单工具页。抽屉 `fetchTool` 只在当前分支（`quick-collect-drawer.tsx:248`）。 | 我们有但更弱 | high（部署后 medium） | 后端 0（代码已有）。部署计入 P0。单工具详情页 1-2 |
| 发现 | 06 分类法闭集与校验 | 64 个闭集 leaf category。未知 id 编译失败（`connectors/categories.ts` 实测 64；`shared/core/schema/taxonomy/leaf.ts:27-39`；`compile.ts:1471-1481`）。TOP groups、provider placement、visibility 是托管 concern（`categories.ts:9-12`）。 | 12 个 UI 标签含“全部”，真实分类 11。36 个 provider_group。platform 是自由字符串（`schemas/collector_catalog.py:11`）。`matchCategory` 只做子串（`lib/platforms/catalog.ts:267-271`）。无启动或编译校验。 | 我们有但更弱 | medium（可降 low-medium） | 1-2（定义闭集 + 启动校验）。不需要数据库迁移 |
| 发现 | 70（补）公开目录 Web 与公开目录 API | `monid.ai/tools` 200、`monid.ai/tools/apify` 200（2026-10-17）。`GET /public/v1/providers` 200（`limit=50`，cursor）。`GET /public/v1/endpoints` 200（total 2719，条目含 price USD、categories、supportedX402Networks）。`GET /public/v1/stats` 200。 | 新 console `/tools` 未部署。生产 `/tools` 404。无公开 catalog API。旧 `/platforms` 200。 | 完全缺失 | medium | 公开只读 API 1-2。Web 由 P0 部署开放 |
| 发现 | 01 跨 provider 的统一工具目录 | 开源 bundle 有 32 provider / 719 endpoint。providers/endpoints 为 map（`shared/core/schema/bundle/bundle.ts:35-52`；`shared/compiler/compile.ts:1133-1159`）。托管目录是并集，实测 91 provider / 2719 endpoint。 | 代码目录有 36 provider_group / 286 能力视图 / 258 唯一端点 / 70 平台包（`platform_packages/builder.py:37-107`）。工具投影 258 tools / 650 params / 294 typed（`tool_catalog/projection.py:229-282`）。数字为代码期构造值。 | 无差距 | none | 0（已有） |
| 发现 | 05 目录浏览与筛选 | CLI 有 `catalog` 的 providers、endpoints、categories 三个子命令。endpoints 支持 `--provider` 与 `--category`（`scripts/catalog.ts:19-90`；`shared/core/catalog.ts:20-113`）。 | 当前分支 `/tools` 有 12 个标签含“全部”、300ms 防抖、URL cat/q/ep（`tools/page.tsx:440-503`；`lib/platforms/catalog.ts:208-265`；`url-state.ts:32`）。生产载体是旧 `/platforms`，12 分类 + 本地 useState 搜索，无 URL 状态（`fc1e60b:platforms/page.tsx`）。 | 无差距 | none | 0（已有）。新代码未上线 |
| 发现 | 07 别名、去重与 canonical 能力标识 | 无别名与去重机制。重复 id 编译失败（`compile.ts:268-274`）。同一上游操作人工拆分为两个 endpoint（`connectors/hunterio/endpoints/discover-ai/endpoint.ts:28-33`）。 | `canonical_capability_id` 在 `builder.py:54-66` 生成。投影按 `endpoint_type` 去重（`projection.py:246,279-281`）。实测 alias 视图 28 个，27 个丢弃，1 个保留。保留行本身是 alias。disabled 视图丢失 public_feed 9、generic_web 2。pypi_search 1 在本树不可复现。 | 我们有对方没有 | none | 2-4（按 `canonical_capability_id` 选行，保留 alias 与状态） |
| 发现 | 08 平台包作为发现单元 | 无平台包概念。catalog 只有 provider、endpoint、category、resource 四类列表（`shared/core/catalog.ts:20-113`）。 | 70 个 PlatformPackage。带 endpoint_count、verified_count、methods、content_types、provider_groups（`builder.py:136-157`）。`/tools` 平台卡与 `/tools/[toolId]` 平台 Skill。`verified_count` 是 catalog status 与 policy 的派生值（`builder.py:144-146`），不是运行验证。生产 tiktok `verified_count=22`，同卡有 2 个 degraded。 | 我们有对方没有 | none | 0（已有） |

### 4.3 执行

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 执行 | 09 按工具 ID 执行并直接返回输出 | `RunCompleted {output,usage,isProviderError,timing}` 一次返回（`shared/core/schema/run/result.ts:69-94`）。托管 `POST /v1/run` 同步返回 output，或返回 202 + runId（run.md）。 | `POST /api/quick-collect` 只返回 `{task_run_id,task_id,source_id,status,records_count,error_message}`（`api/routes/quick_collect.py:822-829`）。记录再查 `/api/raw-records`（`apps/scraper-console/src/lib/api/runs.ts:57-75`）。MCP collect 复用 quick_collect（`mcp_runtime/collect_service.py:13-23`）。 | 我们有但更弱 | high | 2-3（响应加 records/output，注意分页与截断）。计入 P2 |
| 执行 | 11 异步 start/poll/stop 生命周期 | `lifecycle.start/poll/stop`。115 个 `endpoint.ts` 声明 lifecycle（`grep -rl 'lifecycle:' connectors --include='endpoint.ts'` 为 115）。引擎实现 start/poll/stop（`lifecycle.ts:27-42`；`engine/engine.ts:377-520`；`run/result.ts:106-155`）。托管提供 202 + poll + stop（run.md、runs/stop.md）。 | 无通用 start/poll/stop。quick-collect 同步 `await`（`quick_collect.py:946`）。browser diagnostic 有 cancel（`automation_service.py:1333-1354`）。export job 在请求内 `status=success`（`automation_service.py:5081`）。采集有 `asyncio.wait_for` 超时（`collector_service.py:122`）。 | 完全缺失 | high | MVP 5-10；持久多 worker 与重启恢复 15-25。计入 P2 |
| 执行 | 15 参数类型契约与统一校验 | 作者写 zod，编译为 draft-2020-12 JSON Schema。运行时用 AJV。pathParams 只接受 string。query 只接受 scalar 或数组 multimap（`config.yml:14`；`shared/core/schema/run/input.ts:9-13`；`compile.ts:118-135`；`engine/request.ts:18-73,94-135`；`engine/validate.ts:1-76`）。 | 258 tools / 650 params / 294 typed（`projection.py:229-282`）。MCP `describe_capability` 返回 PackageEndpoint 的 `param_fields`（`dict[str,str]`），不返回 typed schema（`mcp_runtime/server.py:103-113`；`platform_packages/models.py:45`）。quick-collect 逐 collector validate（`quick_collect.py:902`；`services/collector_catalog.py:827`）。 | 我们有但更弱 | high（投影 medium，统一校验 high） | MCP inspect 投影 1-2；34 个定义 validate 的 collector 模块统一校验 8-15。与行58 合并计一次 |
| 执行 | 10 通用执行引擎与统一 Endpoint 契约 | 单一 Engine + Transport port。流程为 `load -> validate -> toRequest -> buildRequest -> transport -> settle`。无 per-provider adapter（`engine/engine.ts:94-190`；`engine/interfaces/mod.ts:72-75`；`README.md:107`）。 | 36 个 collector 组，每类一个 Python 实现。`collectors/` 下 39 个 `.py` 文件、90 个类名以 Collector 结尾。无统一 EndpointDoc 或执行契约（`services/collector_service.py:114`）。 | 完全缺失 | medium（原 high，降级） | 增量 Python EndpointSpec 10-20；完整引擎与沙箱 30-60 |
| 执行 | 12 后台任务队列与 worker | 引擎无队列。它的类型定义是 Temporal-activity-shaped（`engine/interfaces/mod.ts:158-176`）。托管 Temporal 只在注释与设计（`openspec/changes/add-async-run-protocol/design.md:6,110,275`）。 | 无 Celery/RQ/arq。`workers/` 只有 `__init__.py`。scheduler 默认 `SCHEDULER_ENABLED=false`（`core/config.py:77`）。后台执行只有 scheduler 循环与 FastAPI BackgroundTasks（`agents/tiktok_cdo/router.py:74`）。 | 完全缺失 | medium（原 high，降级） | DB-backed worker 复用 scheduler/lease 5-10；Redis/Celery 与 worker 部署 10-20 |
| 执行 | 13 重试与退避 | 引擎只标 retriable。`RETRIABLE={EXECUTION_FAILED,RESOURCE_OP_FAILED}`（`engine/errors.ts:55-58`）。engine 无 retry/backoff 循环。 | collector 级重试已实现。`guarded_http` 为 3 attempts / 2 次退避（`guarded_http.py:133-174`）。base 为 `(0.25,1.0)`（`collectors/base.py:28`）。TikHub 为 `(1.0,3.0)`（`tikhub_social.py:35,427-431`）。 | 我们有但形态不同 | medium | 3-5（统一策略 + 指标） |
| 执行 | 14 限流与并发控制 | 引擎无限流。vendor 429 作为 data（`connectors/apify/provider.ts:89-95`）。宿主策略不在 clone。 | MCP 按 token 内存限流 120/min、并发 8、每日 collect 500（`mcp_runtime/governance.py:54-86`；`core/config.py:59-71`）。REST 与 quick-collect 无全局限流。未配置 token 时共用一个内存桶。 | 我们有但更弱 | medium | 3-5（Redis 化 + 覆盖 REST） |
| 执行 | 16 输出 schema 校验 | `output.schema` 在 fromResponse 后校验最终输出。失败为 `CONTRACT_VIOLATION`（`endpoint/doc.ts:60-66`；`engine/engine.ts:930-938`；`errors.ts:26-27`）。仅 37/719 个 endpoint.ts 声明 `output.schema`。 | 无输出 schema。`RawRecord.content` 直接存任意 JSON（`models/raw_record.py:84`）。 | 完全缺失 | medium | 统一信封 1-2；按 collector 完整输出契约 15-25。与行58 合并 |
| 执行 | 17 浏览器自动化与诊断 | 源码无本地浏览器 harness。`grep playwright/puppeteer` 为 0。Apify 通过远端 actor（`connectors/apify/provider.ts:80-105`）。托管目录另有 browserbase 等第三方 provider（`/public/v1/endpoints`）。 | `browser_use` 与 `playwright` collectors 存在（`browser_use_collector.py:72`；`playwright_browser.py:71`）。`outbound_policy` 把 `browser_use_task` 与 `playwright_browser` 标为 unsupported（`outbound_policy.py:62-118`）。诊断默认 `diagnostic_snapshot_replay`（`automation_service.py:1937-2101`）。只有显式 probe 且本机存在 `/Users/pray/.local/bin/browser-harness` 才启动（`automation_service.py:9579-9598`）。 | 我们有但更弱 | medium | 待核实（策略放行 + harness 路径配置；未产品化） |
| 执行 | 19 定时调度 | 源码无 scheduler。cron 只有 CI drift（`.github/workflows/drift.yml:9-10`）。`engine.ts:1071-1073` 注释 `The host owns WHEN`。托管 Temporal 负责 WHEN（设计层，见行12）。 | CollectionScheduler + lease，默认关闭（`scheduler/service.py:51-129`；`core/config.py:77`）。采集任务有 `schedule_cron`（`models/task.py`）。 | 我们有但更弱 | low（原 medium，降级） | 0.5-1 启用并验证；加监控 1-2 |
| 执行 | 18 批量执行 | 一次 run 一个 endpoint。无 batch verb（run.md）。 | `POST /api/automation/product-batch-run` 逐采集任务执行（`automation_service.py:2341-2412`）。只接受 `ecommerce_product_page` 且 enabled 的采集任务。前端批量选择逐个打开抽屉（`tools/page.tsx:599-633`），不是自动提交。 | 我们有对方没有 | none | 2-4（把抽屉批量化） |

### 4.4 计费

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 计费 | 20 端点级费率卡 | 开源只有 4 种 credit 模型：FREE/PER_CALL/PER_UNIT/COMPOSITE（`shared/core/schema/usage/model/mod.ts:36-41`）。`consumes` 在 `shared/core/schema/usage/model/consumes.ts:33-38`。usage 编译后必填（`doc.ts:67-97`；`compile.ts:502-511`）。USD 与 rates 在托管 rate card。托管 wire 还有 PER_RESULT、BY_PERIOD、METERED、PER_UNIT_MATRIX、TIERED、PER_TOKEN、flatFee（CLI types.ts 注释）。 | 仅 `cost_hint` 文本（`schemas/collector_catalog.py:16`）。`collectors.py` 中 288 处声明。`tool_catalog/models.py` 无 usage/rate 字段。 | 完全缺失 | high | 展示型 2-4；计费级 8-15。计入 P4 |
| 计费 | 21 用量计量与结算 | settle 在 raw envelope 上运行 evidence，再 fold `ceil(q/every)*amount`。consolidate 非空 claim 覆盖 derived fold。差异写 mismatch（`engine/engine.ts:836-940`；`usage/validate.ts:36-102`；`usage.ts:34-42`）。 | 无用量计量。TaskRun 只有 `records_count`（`models/task.py:44-57`）。 | 完全缺失 | high | 10-20。计入 P4 kernel，不单独计费 |
| 计费 | 22 预估计费与准入 hold | `RunnableEndpoint.estimate` 纯函数已实现（`engine/engine.ts:330-348`；`hooks/estimate.ts:8-14`；`interfaces/mod.ts:178-188`）。hold/truing 只在注释与设计（`hooks/estimate.ts:10-11`；`design.md:414`）。OSS 无账本。 | 无预估与预扣。MCP 只有每日 collect 次数上限（`governance.py:54-86`）。 | 完全缺失 | high | 10-15，依赖 metering。计入 P4 kernel |
| 计费 | 23 余额与钱包 | 托管 `GET /v1/wallet/balance` 返回 `{balance,held}`（wallet/balance.md）。app bundle 还有 topup、auto-reload、payment-methods、invoices、promo-codes。源码 `*.sql=0`，无 wallet 实现。 | 无余额、钱包、充值。`models` 下 26 个 `.py` 模块无 Balance/Wallet/Invoice。 | 完全缺失 | high（对外自助付费为 blocker） | 10-20。计入 P4 kernel |
| 计费 | 24 账单流水与充值记录 | 托管 `GET /v1/wallet/activities` 返回 top-up/credits 流水。run charges 另见 `/v1/runs`（wallet/activities.md）。源码无账本。 | 无账单流水。`workflow_budget_ledger_entries` 是 fixture-only 预算，不是计费（`models/workflow_execution.py:611-695`）。 | 完全缺失 | high | 2-3（wallet/ledger 之后做投影）。计入 P4 |
| 计费 | 25 单次运行的价格、成本与 billedUnits | 托管 `GET /v1/runs/:id` 返回 price、cost、billedUnits、providerResponse.httpStatus。run.md 还有 `billing.calculatedCost`（MICRO_DOLLAR）。OSS `RunCompleted` 只有 usage/timing（`result.ts:69-94`）。 | TaskRun 只有 status、records_count、logs（`models/task.py:44-57`）。无 price/cost/billedUnits。 | 完全缺失 | high | 1-2（依赖 rate card 与 metering）。计入 P4 |
| 计费 | 26 失败零计费与厂商 meter 对账 | 非 2xx 强制 zeroUsage。成功才 evidence + assemble。consolidate 非空 claim 胜出。差异写 mismatch（`engine.ts:846-916`；`usage.ts:50-54`）。 | 无计费，故无零计费与对账。失败只记 error_message（`models/task.py:52-53`）。 | 完全缺失 | medium | 5-10，依赖 metering。计入 P4 |
| 计费 | 27 预算与配额控制 | 托管 run detail 有 controls/BLOCKED（WORKSPACE_BUDGET、WORKSPACE_RUN_CAP，runs/get.md）。app bundle 有 `/v1/controls/workspace/budgets` 与 run-caps。 | `WorkflowBudgetAccount` 有 max_cost_usd、quota_ceilings（`workflow_execution.py:522-586`）；`WorkflowBudgetLedgerEntry` 有 cumulative_cost_usd（`:611-695`）。`fixture_boundaries` 禁止 provider_call、credential_read、raw_record_write、production_write（557-564）。生产无写入路径。MCP 每日 collect 配额是唯一 live 部分（`governance.py`；`config.py:69-71`）。 | 我们有但形态不同 | medium | 4-6（解除 fixture 约束 + settled 语义 + API/UI） |
| 计费 | 74（补）资源所有权生命周期 | resource doc + FIXED/ESTIMATED 周期 rate card + verify/release/refresh/views + endpoint provisions/uses/updates/releases/reads 绑定 + ownership pre-gate + `RunCompleted.resources` + 本地 Deno KV store（`resource/doc.ts:42-118`；`resource/usage.ts:25-88`；`resource/ops.ts:60-164`；`endpoint/doc.ts:112-152`；`engine.ts:196-320,966-1019`；`store/kv.ts:14-138`）。saperly 有 17 endpoints + phone-number resource。13 个 saperly endpoint.ts 绑定资源（全仓 14 个，另 1 个在 surf）。 | 无 durable resource 模型、租约、计费。 | 完全缺失 | medium（当前业务不需要） | 待核实。先做 resource doc + rate card + ownership gate。不在 P0-P4 |
| 计费 | 75（补）x402 加密支付通道 | `x402.monid.ai/v1/run` 与 `/v1/runs/:id`。USDC。Base mainnet `eip155:8453` 与 Monad `eip155:143`。docs 最低 $0.01。metered endpoints 不支持。公开 endpoint 条目带 supportedX402Networks。docs 的 $0.01 与实测 `amount=1000`（USDC 6 位约 $0.001）存在 floor 不一致，待核实。 | 无加密支付。 | 完全缺失 | low（不在目标市场） | 待核实。当前阶段不做 |

### 4.5 接入

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 接入 | 31 MCP workspace 作用域与跨租户隔离 | workspaceId 可选。API key 绑定 workspace。跨 workspace 返回 403（runs/get.md；auth/workspaces.md）。引擎 tenancy-blind（`engine/interfaces/mod.ts:87-97,136-141`）。 | 无 workspace 参数。quick-collect 固定 demo workspace（`quick_collect.py:836`）。MCP collect 复用 quick_collect（`collect_service.py:13-23`）。 | 完全缺失 | blocker（仅对外多租户） | 统一身份后 2-4；独立做 4-6。计入 P1 |
| 接入 | 36 API key 签发与轮换 | 托管 `app.monid.ai/access/api-keys` 创建 `monid_live_...` key。key 绑定 workspace。app bundle 有 `/v1/api-keys` 与 `/scopes`。源码无 key 模型。 | 无 API key 模型与路由。REST 只认 HttpOnly cookie JWT（`api/deps.py:31-36`）。 | 完全缺失 | blocker（仅外部自助） | MVP 4-7；轮换、scope、UI 加 3-5。10-15 是完整版上限。计入 P1 的 12-21 |
| 接入 | 28 远程 MCP 服务器与工具面 | 托管 `https://mcp.monid.ai/v1`。13 个 `monid_*` 工具。OAuth（plugins SKILL.md:55-71；initialize 401 + PRM）。源码无 MCP server。 | `/mcp` 挂 Streamable HTTP（`main.py:163`）。5 个元工具（`mcp_runtime/server.py:47-149`）。实测 `list_tools=5`。无 get_run、list_records、stop、balance、resource。`describe_capability` 直接返回 PackageEndpoint，暴露 `policy_block_reason`（`server.py:103-113`）；REST 有 PublicTool 脱敏。 | 我们有但更弱 | high | 5-10（补运行、资源、余额工具 + 描述 + 统一投影）。计入 P2/P3 |
| 接入 | 30 MCP 工具描述与选择信号 | 13 个工具在插件 SKILL.md 有用途表。`monid_run` 输入形状明确（SKILL.md:55-95）。 | 5 个工具函数无 docstring。实测 `list_tools` 的 description 全为空串（`server.py:47-149`）。 | 我们有但更弱 | high | 0.5-1（补 docstring/annotations）。计入 P3。与行47 重复，只计一次 |
| 接入 | 33 官方 CLI | `@monid-ai/cli` 0.1.7，bin 为 `monid`。命令有 discover、inspect、run、runs、resources、whoami、balance、keys，另有 setup、generate_session_id（npm registry；`src/index.ts:23-32`）。 | 无产品 CLI。只有内部 scripts（generate/test/verify/deploy）。首页 TerminalDemo 的 `dih runs tail` 是虚构（`TerminalDemo.tsx:25`）。设计文档明确不承诺 CLI（技术方案:76）。 | 完全缺失 | high | 8-15。不在 P0-P4 |
| 接入 | 34 根 SKILL.md 与统一 Agent 入口 | `monid.ai/SKILL.md` 21,925 B，v0.1.7，CLI-only。plugins 包 v1.0.0，MCP+CLI，`mcp.json` 指向 `mcp.monid.ai/v1`。 | 每平台 Skill ZIP，SKILL.md 3.2KB + manifest 27KB + playbook 7.6KB。无根 SKILL.md 与 llms.txt。`/connect` 生产 404。 | 我们有但形态不同 | high | 2-4（写根 SKILL + 部署 `/connect`）。与行49 合并，只计一次。计入 P3 |
| 接入 | 37 用户登录与 OAuth | Clerk OAuth（MCP）+ API key/JWT（REST）（overview.md；AS metadata）。源码只有 relayTransport 桩（`transport.ts:184-198`）。 | cookie JWT login/register/logout/me（`api/routes/auth.py:26-93`）。211/212 可匿名。`auth_cookie_secure` 默认 False（`core/config.py:29`）。默认 workspace 查询把 demo 排第一（`repositories/workspaces.py:26-29`）。 | 我们有但更弱 | high（对外） | 10-20（OAuth + 强制鉴权）。先收紧软鉴权。不在 P0-P4 |
| 接入 | 38 账户自助与设置页 | 托管控制台有 `/access`、`/wallet`、`/usage`、`/tools`、`/tools/:category`、`/resources`、`/resource-files`、`/email-inboxes`、`/rules`、`/mint-assets`。API 有 wallet topup/auto-reload/payment-methods/invoices/promo-codes、controls、api-keys/scopes、mandates、proxies、status。不是只有 key/预算。 | `/settings/account` 整页占位“账户设置建设中...”（`settings/account/page.tsx:3-12`）。只有 `/settings/credentials`。`lib/routes.ts:105-110` 声明 `/settings/providers` 与 `/settings/members`，仓库无页面。 | 完全缺失 | high | 5-10（账户、密钥、预算页）。另修失效链接 0.5 |
| 接入 | 29 MCP OAuth 与动态客户端注册 | OAuth authorization-code + PKCE S256。Clerk authorization server。DCR `/oauth/register`。PRM（`mcp.monid.ai/.well-known/oauth-protected-resource/v1`；`clerk.app.monid.ai/.well-known/oauth-authorization-server`）。源码只有 relayTransport callerAuth 桩函数（`transport.ts:184-198`）。 | 仅静态 Bearer token（`SCRAPY_MCP_TOKEN(S)`）。未配置时 fail-open（`mcp_runtime/auth.py:20-27`）。无 OAuth、PRM、DCR 路由。 | 完全缺失 | medium（原 high，降级；bearer 够内部用） | 自建 10-20；接第三方 IdP 5-8。不在 P0-P4 |
| 接入 | 32 对外 REST 产品 API | 至少 20 条公开路径：10 条文档化 `/v1`（overview.md）+ 2 条 x402 + 3 条 public catalog + 5 条 resources（CLI `client.ts:206-242`）。app bundle 还有 api-keys/scopes、controls、wallet、mandates、proxies。 | 190 paths / 212 ops。严格鉴权 1、软鉴权 149、仅 session 51、无依赖 11（本机 `app.routes` 枚举）。quick-collect 只有 SessionDep。生产目录 API 404。当前分支挂载 tools 与 capability_*；fc1e60b 未挂载，生产 ops 少于 212。 | 我们有但形态不同 | medium | 10-20（抽产品 API + 鉴权） |
| 接入 | 39 公开文档站与可发现性 | `docs.monid.ai` 为 VitePress 1.6.4；`monid.ai/docs/*.md` 页脚自称 Mintlify。`llms.txt` 在 `monid.ai/docs/llms.txt`（7,489 B）。`robots.txt` 与 `sitemap.xml` 200。 | FastAPI `/openapi.json` 与 `/docs` 在代码里（`main.py:87-93`），生产 404。无 llms.txt、robots、sitemap、OG。layout 只有 title/description（`layout.tsx:5-8`）。 | 完全缺失 | medium | 1-2（robots、sitemap、OG、llms + 部署 openapi）。计入 P3 追加项 |
| 接入 | 71（补）商业化接入模式 | `docs/integrations/overview.md` 有三卡：Direct API key、OAuth、Proxy。Proxy 用 `MONID_API_BASE_URL`。Claude Tag access bundle。quickstart MCP 列 Claude.ai、Claude Code、Codex、OpenCode、ChatGPT。 | 无三种接入模式。只有 cookie JWT 与静态 MCP bearer。 | 完全缺失 | medium（对外付费） | 5-8（Proxy 模式 + 文档；OAuth 另计行29）。不在 P0-P4 |
| 接入 | 72（补）多 Agent 分发生态 | `monid-ai/plugins`（Claude Code）、`cursor-plugin`、`hermes-plugin`、`skills`（`npx skills add`）。`awesome-monid` 收录 72 个项目、11 类。Claude.ai、Claude Code、Codex、OpenCode、ChatGPT 有 MCP 安装说明。 | 无插件与技能分发包。只有平台 ZIP 与控制台。 | 完全缺失 | medium | 2-4（发布插件清单 + 安装文档） |
| 接入 | 73（补）Webhook | provider-scope 有声明式 HMAC verify、`route({who,what})` verdict、subscribe/unsubscribe、本地 ingress + cloudflared/tailscale（`hooks/webhooks.ts:35-150`；`sections/webhooks.ts:31-55`；`scripts/webhook.ts:1-30`）。resource-scope 只有 schema（`resource/doc.ts:34-39`），in-tree 未 serving。 | 无 webhook。 | 完全缺失 | low | 待核实（provider-scope 优先；签名与重试） |
| 接入 | 35 Skill 包内容 | 插件包有 `plugin.json`、`.claude-plugin/plugin.json`、`mcp.json`、`SKILL.md`、logo（`monid-ai/plugins`）。 | 每平台 ZIP 固定 5 文件：`SKILL.md`、`README.md`、`manifest.json`、`references/playbook.md`、`evals/trigger_cases.json`（`platform_packages/service.py:79-101`）。本机 tiktok ZIP 为 9589 B、5 entries。 | 我们有对方没有 | none | 0（已有） |

### 4.6 治理

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 治理 | 42 目录治理（导入、审核、发布、回滚） | connector 以 PR 进入。compile check + `ids.lock` + catalog-v tag（`README.md:58-59`；`ci.yml:18-19`；`publish-catalog.yml:11-13,30-41`；`connectors/ids.lock.json` 27,666 B）。无 DB 治理与回滚。托管 ingest 端到端未验证（`DEVELOPMENT.md:282-289` 与 workflow 不一致）。 | capability governance 有 imports、publications、decisions、rollback。membership 有 can_read、review、publish（`authority.py:21-49`；`api/routes/capability_governance.py`；`main.py:144` 当前分支挂载）。但 src 无 membership 实例化与 seed。fc1e60b 未挂载。console 无治理页。apps/web 的治理页只在 mock 模式使用。 | 我们有但更弱（未上线） | medium | 部署 + bootstrap/seed + 控制台页 2-4 |
| 治理 | 44 厂商契约漂移守卫 | 每周一 06:00 UTC 执行 Apify 定价与输入 schema 漂移（`drift.yml:9-10`；`drift.ts:11-16,28`）。覆盖只有 Apify。 | product、public-content、GitHub tool 漂移检查（`automation.py:937-975`；`automation_service.py:3449/3635/3825`）。不检查厂商定价与 schema。 | 我们有但形态不同 | medium | 5-10（扩展到 provider 定价与 schema） |
| 治理 | 45 版本兼容与可复现发布 | specVersion + minEngineVersion + ENGINE_VERSION 0.5.0（`config.yml:13,37,48,59,67`；`engine/deno.json:3`）。byte-identical compile 由测试保证（`compiler.test.ts:998-1006`；`publish.test.ts:151-165`）。catalog-v semver tag（`publish-catalog.yml:13,32-34`）。 | `tool.v1` 与 `tool-params.v1` 全局契约版本。catalog_digest。平台包 release 为 `1.0.0+digest`（`projection.py`；`parameters.py:22`；`builder.py:107`；`platform_packages.py:104`）。无 per-tool version。生产 digest 公式与本树不同（生产含 verified_count）。 | 我们有但更弱 | medium | 5-10（per-tool version + digest 公式版本化）。部署会改所有 release 与 ZIP SHA |
| 治理 | 40 出站采集策略（服务端强制） | 无采集策略层。只有 auth 与同源凭据规则（`engine/interfaces/mod.ts:34-59`；`auth.ts:18-79`）。同源凭据规则不是采集策略。 | 4 级策略：provider_api 28 / guarded_http 4 / offline 1 / unsupported 53，共 86 类型。258 端点 197/4/57（`collectors/outbound_policy.py:19-118`）。本机统计一致。 | 我们有对方没有 | none | 0（已有）。核心合规资产，不要削弱 |
| 治理 | 41 业务授权与确认门控 | 无业务授权与确认门控。供应商调用由托管方凭据执行；开源层只声明 auth.inject 与 `<PROVIDER>_CREDENTIALS_<FIELD>` 约定（`AGENT.md:219-225`）。 | site-analysis 与 product-discovery 要 body.authorized（`automation_service.py:607-609,2108-2109`）。report send 要 authorized + confirm_send（`report_service.py:734-737`）。email live-send 要 enabled + allowlist + approval_id（`notification_service.py:924-931`；`config.py:41-43`）。authorized/confirm 是客户端布尔。只有 email live-send 是服务端强制。 | 我们有对方没有 | none | 0（已有）。不要写成“合规级授权” |
| 治理 | 43 工具状态与可用性语义 | 无 status/deprecated 字段（`meta/base.ts:17-19`）。availability 与 visibility 是托管策略（`categories.ts:9-12`）。托管 inspect 有 tags。 | availability 有 6 态：verified、config-gated、degraded、empty、untested、disabled（`status.py:12,65-112`）。catalog 行带 policy_block_reason 与 status。证据只来自 `[quick] [test]` 采集任务（`service.py:104-136`）。`/api/tools` 不返回 p95。 | 我们有对方没有 | none | 0（已有）。去重会丢 disabled 状态；修去重后更强 |
| 治理 | 46 审计轨迹 | 源码无审批与审计。托管侧未知（`AGENT.md:18-20`）。 | `report_audit_events`（`models/report.py:36-53`；`report_service.py:882-949`）。email 有 request/decision_snapshot（`models/notification.py:56-120`）。governance decisions 与 publications 模型存在，但无 membership 写入。 | 我们有对方没有 | none | 0（已有，限报告与邮件）。不要宣称目录治理审计可用 |

### 4.7 内容

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 内容 | 49 产品级 Skill 内容 | `monid.ai/SKILL.md` v0.1.7，21.9KB，CLI-only。插件 SKILL.md v1.0.0，transport-aware，13 工具（`monid.ai/SKILL.md`；plugins SKILL.md:1-95）。 | 每平台 SKILL.md 3.2KB + manifest 27KB + playbook 7.6KB（`service.py:79-101`；tiktok ZIP 实测）。无产品级总入口、故障排查、状态语义。 | 我们有但更弱 | medium | 2-4。与行34 合并，只计一次。计入 P3 |
| 内容 | 47 工具描述质量 | EndpointDoc meta 有 displayName、summary、description、notes、docsUrl、categories（`meta/base.ts:21-33`；`meta/endpoint.ts:9-12`）。notes 级联 316 个 endpoint.ts，连 provider 共 332 处（`compile.ts:281-294`）。 | catalog 有 label、description、notes、playbook。34 个 notes JSON / 107 条（`notes.py:28,55-93`）。`/docs` 展示 description、参数、最近测试（`docs/page.tsx:139-234`）。 | 无差距 | none | MCP description 0.5-1（已计入行30；本行不重复计） |
| 内容 | 48 Playbook 与坑点库 | 无 playbook 概念。notes 与 docsUrl 是分散文案（grep playbook 仅 vendor 的 google-play-books）。 | `render_playbook` 从 catalog 与 notes 实时渲染（`renderers.py:134-194`）。70 个平台 playbook。MCP `get_playbook`、REST `/playbook`、ZIP `references/playbook.md` 同源（`service.py:75-76`；`generator.py:49`）。实测 tiktok playbook 5417 字符，三处一致。 | 我们有对方没有 | none | 0（已有） |
| 内容 | 50 中文与双语内容 | 英文 README、SKILL、docs。grep CJK 只命中 vendor 数据。无中文内容。 | 中文 UI（`layout.tsx:16` 为 `lang=zh-CN`）、中文 playbook、中文 notes、中文错误文案（`renderers.py` 中文模板）。 | 我们有对方没有 | none | 0（已有） |

### 4.8 账户

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 账户 | 51 用户与工作区模型及租户隔离 | workspace-bound API key。OAuth 用 `x-workspace-id`。跨 workspace 403（runs/get.md；auth/workspaces.md）。引擎 tenancy-blind（`engine/interfaces/mod.ts:87-97,136-141`）。 | users/workspaces/workspace_members 模型存在（`models/workspace.py:20-60`）。业务路径固定 demo workspace：`quick_collect.py:836`、`tasks.py:38,74,104,123`、`dashboard.py:26`、`raw_records.py:27,48`。登录也加入 demo（`auth_service.py:61-64,123`）。`get_default_workspace_for_user` 把 demo 排第一（`repositories/workspaces.py:18-33`）。实际调用 45 处，其中 43 处在路由层。59 是文本引用行数。 | 完全缺失 | blocker（仅对外售卖） | MVP 6-10；多 workspace、邀请、管理员、迁移 10-15。计入 P1 的 12-21 |
| 账户 | 52 成员与角色 | workspaces + list_workspaces。角色由 Clerk/org 管理，API 文档未展开（auth/workspaces.md；plugins SKILL）。 | `workspace_members` 有 owner/member（`models/workspace.py:46-54`）。governance membership 有 can_read/review/publish（`authority.py:21-49`）。workspace 角色未用于授权。治理角色因无 membership 写入不可用。 | 我们有但形态不同 | medium | 3-5（角色 UI 与权限矩阵） |

### 4.9 可观测

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 可观测 | 53 统一调用记录 | `RunCompleted {kind,httpStatus,providerHttpStatus,output,usage,isProviderError,timing,resources}`（`result.ts:69-94`）。托管 run detail 再加 caller、provider、endpoint、price、cost、billedUnits（runs/get.md）。 | 分散对象：TaskRun（`models/task.py:44`）、WorkflowRun/StepRun（`workflow_execution.py:35,192`；fixture-only 65-68,114）、DatasetExportJob（`models/dataset.py:185`）、ReportSubscriptionRun、EmailProviderLiveSendRun、CapabilityGovernanceRequest。无统一表记录 tool + input + output + status + cost。 | 完全缺失 | high | 只读视图 2-3；新 call_records 全入口 15-25。计入 P2 的 9-16（只读视图） |
| 可观测 | 54 单次运行详情与调用日志 | 托管 `GET /v1/runs/:id` 返回 input、output、providerResponse.httpStatus、status、stoppable、price、cost、timestamps（runs/get.md）。引擎 logger 默认 NOOP（`engine.ts:86-98`）。auth silent（`auth.ts:71-79`）。 | `/runs` 行展开显示 TaskRun.logs（`runs/page.tsx:61-107`）。`/runs/[runId]` 显示 raw records。无输入记录、HTTP 状态、价格、请求 ID（`schemas/task.py:115-132`）。 | 我们有但更弱 | high | 2-5（扩展 TaskRun 与读模型 + UI）。计入 P2 |
| 可观测 | 55 健康与延迟指标 | EndpointMetrics 有 status 与 runTimeMs.p50/p95（`monid-ai/cli src/api/types.ts:176-185`）。discover 与 inspect 都带是 README 与 CLI 声明（`README.md:44-45`）。API 文档未列。源码无实现。 | availability 6 态。provider_health_snapshots 有 sample_count、success_rate_bps、p95_latency_ms（`provider_health.py:32-122`）。但 `fixture_boundaries` 禁止 health_probe、provider_call、production_write（86-92）。`record_provider_health_snapshot` 在 src 内 0 调用方。读取面只挂 workflow_runs（fixture-only，生产未挂载）。 | 完全缺失（可计算，未实现） | high | 5-8（从 task_runs 聚合）。与行3 合并，只计一次。计入 P3 |
| 可观测 | 56 用量与成本面板 | 托管 wallet balance/activities + run cost/billedUnits。app bundle 有 `/usage` 与 `/wallet` 页面。ClickHouse 只在 `design.md:302-325` 与 `result.ts:28-35` 注释。 | dashboard 是情报与采集任务健康度（`dashboard/page.tsx:49-266`）。全仓无 usage、billing、quota、balance 面板（grep 只有 cost_hint）。 | 完全缺失 | high | 3-5（metering 之后做投影）。计入 P4 |
| 可观测 | 57 业务告警与异常通知 | 仅 usage mismatch 的 `logger.warn`（`engine.ts:911`）。grep alert 只有 openspec 文案。无告警模型、路由、通知。 | alert_rules 与 alert_events，支持 in_app/both（`models/alert.py:16-33`；`schemas/alert.py:11`；`alert_service.py:162-176`）。drift 有独立 email 路由（`automation_service.py:5656`，需 authorized + confirm_send）。`AlertChannel` 含 email，但 `match_alert_rules_for_signal` 只发 in_app/both。email 永不发送。 | 我们有对方没有 | none | 0（已有；email 通道未实现） |

### 4.10 信任

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 信任 | 58 输入与输出契约校验 | load gates + AJV input/output + hook contract（`engine.ts:106-144`；`validate.ts:1-76`；`link.ts:203-234`；`errors.ts:12-17`）。`output.schema` 仅 37/719 声明。 | Pydantic request models + per-collector `validate_collector_config`（`quick_collect.py:902`；`services/collector_catalog.py:827`；34 个 collector 模块定义 validate）。无统一 output schema。tool_catalog 有 typed，但 MCP 不暴露完整 schema。 | 我们有但更弱 | high | 契约层 15-20（输入 8-15 + 输出 5-10，共享框架）；MCP 投影 1-2 单列。与行15/16 合并计一次 |
| 信任 | 61 密钥托管与注入边界 | `auth.inject` 由 Transport/Relay 执行，值不进 pipeline。env 命名 `<PROVIDER>_CREDENTIALS_<FIELD>`。auth hook 用 SILENT_LOGGER。fixture 不录 request headers（`interfaces/mod.ts:34-58`；`auth.ts:18-98`；`fixtures.ts:24-42`）。托管 Broker/KMS 只在注释与设计（`transport.ts:180-184`）。 | Fernet vault + key_version。workspace + provider 唯一。仅 owner 可写。覆盖 7 个社媒平台（`platform_credentials.py:78-112,130,197-212`；`fixtures/capability_catalog_overseas_v2.json`）。`VaultCredentialSource` 在 src 内 0 实例化（仅 `tests/unit/test_vault_credential_source.py`）。`EnvironmentCredentialSource` 只在未调用的 `social_api/environment_composition.py:15`。collectors 仍读 env（`exa_collector.py:38`、`apify_actor.py:51`、`tikhub_social.py:376`）。无统一输出脱敏。 | 我们有但更弱 | high（对外）/ medium（内部） | 全量 15-25；已验证社媒与搜索平台 8-12 |
| 信任 | 59 失败关闭闸门与密封执行单元 | sealed unit `{doc,fns}`。fn 内容哈希校验。`new Function` 空作用域（`sealed-unit.ts:16-27`；`link.ts:132-196`）。fail-closed gates（`engine.ts:106-144`）。 | 无 sealed unit 与哈希校验。collector 是普通 Python 导入（`services/collector_service.py:112`）。 | 完全缺失 | medium | 30-60（不建议照搬） |
| 信任 | 62 采集器录制、回放与测试证据 | 1034 fixtures、244 个 `.test.ts`、1448 个 `Deno.test`、434 个 `liveSkip`。零网络 replay（`runner.ts:35,124-146`；`fixtures.ts:24-42`）。 | 有 `httpx.MockTransport` 与 `tests/fixtures`（`test_outbound_budget_scope.py:42`）。无 per-collector record/replay 工具。运行证据靠 `[quick] [test]` 真实执行。 | 我们有但更弱 | medium | 5-10 每个采集族；全量 20+ |
| 信任 | 60 数据血缘 | 无数据集血缘。只有 run output/usage（`result.ts:69-94`）。无 dataset、version、export 模型。 | `RawRecord.workflow_run_id/step_run_id`（`raw_record.py:65-81`）。`DatasetVersion` 有 source_workflow_run_id、source_raw_record_ids、lineage_contract_version（`dataset.py:111-149`）。强血缘仅 fixture（`lineage_preview.py:37`）。live `save_product_dataset_version` 只写 source_task_run_ids（`automation_service.py:3168-3195`）。rows JSON 保留逐行 raw_record_id 与 task_run_id。缺正式 source_raw_record_ids 字段。preview 路由 workflow-runs 生产 404。 | 我们有对方没有 | none | 5-10（把强血缘扩展到 live 采集） |

### 4.11 形态

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 形态 | 64 公开首页与新 IA 部署 | `monid.ai` 200。`/tools` 200。`/tools/apify` 200。`docs.monid.ai` 200（2026-10-17 实测）。 | 新 IA 代码在当前分支（`/`、`/tools`、`/docs`、`/connect`）。生产 `/` 为 307 到 `/platforms`。`/tools`、`/docs`、`/connect` 404（2026-10-17 实测）。fc1e60b 根 page.tsx 是 `redirect('/platforms')`。`NEW_ROUTES` 还列 `/settings/providers` 与 `/settings/members`，仓库无页面（`lib/routes.ts:105-110`）。首页统计硬编码 286/258/285/248（`page.tsx:29-34`）。 | 我们有但更弱 | high | 0.5-1 部署 + 修失效链接。不含单工具详情页 1-2 与根 SKILL 2-4。计入 P0。首页仍按网站逆向结果做 |
| 形态 | 66 Agent-first 三动词入口 | `discover -> inspect -> run` 三动词。一个 base URL + 一个 key。13 个 MCP 工具（`README.md:52-54`；plugins SKILL）。“first two free”是文档声明，不是源码强制。 | MCP 5 元工具：list_platforms、list_capabilities、describe_capability、get_playbook、collect（`server.py:47-149`）。无 discover 排序与价格健康。REST 212 ops。 | 我们有但更弱 | high | 入口编排与别名 1-2。discover、run、MCP 工具分别在行2、9、28 计费。删除原 5-10 的重复估算 |
| 形态 | 63 Web 数据控制台 | 开源仓库 0 `.tsx`、0 `.jsx`、0 `.html`、0 `.css`，只有 3 张 PNG。托管 app 有完整控制台（见行38）。 | 15 个 App Router `page.tsx`（find 实测），含公开首页。路径 `apps/scraper-console/src/app`。 | 我们有对方没有 | none | 0（已有）。15 包含公开首页本身 |
| 形态 | 65 设计系统与视觉规范 | 开源 0 CSS、0 tsx。托管 `monid.ai/tools` 内联 Nuxt UI token（`--ui-color-*` 与品牌色）。app 使用 Nuxt/Clerk 组件。产品侧有设计系统，开源没有。 | `globals.css` 手写 token：`--fg-1`、`--bg-1`、`--accent-1`、`--space-*`、`--radius-*`、`--duration-*`、`--focus-1`（`globals.css:4-60`）。Tailwind v4。无暗色模式。`components.json` 指向不存在的 `tailwind.config.ts`。 | 我们有对方没有 | none | 0（已有）。只写“开源无设计系统”，不推断产品无设计系统 |

### 4.12 数据

| 维度 | 能力 | Monid | 我们 | 差距 | 严重度 | 复刻代价 |
|---|---|---|---|---|---|---|
| 数据 | 67 原始记录到数据集、版本、导出 | 无数据集、版本、导出产品。run output 即结果（`result.ts:69-94`）。本地 Deno KV 只存 owned resources（`scripts/store/kv.ts:14-38`）。托管有 `/v1/resources` 数据面。 | `RawRecord -> Dataset -> DatasetVersion -> DatasetExportJob`。支持 CSV、Excel、JSON、JSONL，sha256、行数、预览（`raw_record.py:29-88`；`dataset.py:87-207`；`automation_service.py:4992-5097`）。只覆盖 3 类 dataset_type：ecommerce_product、public_content_update、github_tool_radar。 | 我们有对方没有 | none | 0（已有；范围限 3 类数据集） |
| 数据 | 68 数据预览与字段结构 | 开源 connector doc 有可选 `output.schema`（37/719）。托管 inspect 文档不暴露 output schema。两端都无数据预览。 | 预览前 50 行。字段结构显示类型与空值数，由前 50 行推断。显示平均完整度（`data-preview-drawer.tsx:279,362,451-482`）。 | 我们有对方没有 | none | 0（已有）。类型推断非权威 schema |
| 数据 | 69 垂直领域平台与数据覆盖 | 开源 32 provider / 719 endpoint。托管 91 provider / 2719 endpoint（stats，2026-10-17）。托管 categories 含 instagram、tikhub、browserbase、virtual-machines，不只 B2B。 | 70 平台 / 258 端点 / 36 provider_group。覆盖 TikTok/CDO、电商、OSINT、社媒、包 registry。中文 playbook（`builder.py`；本机构造）。 | 我们有对方没有 | none | 0（已有）。覆盖面不同。不要写成“平台数更多” |

### 4.13 补录说明

补录 6 行来自三路校验的 misses。它们是真实能力，不能只写在脚注。

| 编号 | 维度 | 能力 | 补录理由 |
|---|---|---|---|
| 70 | 发现 | 公开目录 Web 与公开目录 API | Monid 有匿名目录 Web 与 `/public/v1` 目录 API。矩阵原稿漏了第二个发现入口 |
| 71 | 接入 | 商业化接入模式 | Direct、OAuth、Proxy 与 Claude Tag 决定 API key 与 OAuth 的边界 |
| 72 | 接入 | 多 Agent 分发生态 | Monid 有 plugins、cursor-plugin、hermes-plugin、skills 与 awesome-monid |
| 73 | 接入 | Webhook | provider-scope 已在 OSS 实现。resource-scope 只有 schema |
| 74 | 计费 | 资源所有权生命周期 | OSS 有 resource doc、rate card、ownership gate、local store。不是纯商业模式 |
| 75 | 计费 | x402 加密支付通道 | 托管有 x402 支付路径。docs 与实测的 floor 不一致，待核实 |

### 4.14 矩阵汇总

| 项目 | 数值 | 说明 |
|---|---|---|
| 矩阵行数 | 75 | 69 行主干 + 6 行补录 |
| 完全缺失 | 29 | 23 行主干 + 6 行补录 |
| 有但更弱 | 20 | 含行17、42（修正后不再算反向优势） |
| 有但形态不同 | 6 | 重试、预算、REST 形态、根 Skill、漂移、角色 |
| 反向优势 | 17 | 合规策略、数据交付链路、平台包、中文资产、控制台等 |
| 无差距 | 3 | 统一目录、浏览筛选、描述质量 |
| blocker | 3 | 行31、36、51。只在对外场景成立 |
| high | 26 | 含发现、执行、计费、接入、可观测、信任、形态 |
| medium | 23 | 含分类法、引擎、队列、健康聚合、治理等 |
| low | 3 | 定时调度、Webhook、x402 |
| none | 20 | 已有能力或明确战略取舍 |

69 行主干的原估算合计为 356.5-686 人日。P0-P4 只覆盖 Agent 可用性的最小集合，合计 52.5-87 人日。其余工作不在本路线。

## 5. 复刻路线

### 5.0 两条路径

先选场景。场景决定顺序。

| 场景 | 顺序 | 说明 |
|---|---|---|
| 对外自助售卖 | P0 -> P1 -> P2 -> P4 -> P3 | 身份与计费是前提。发现质量可以后置 |
| 内部受邀使用 | P0 -> P2 -> P3 -> P4 | P1 可选。静态 MCP token 够用。P4 可后置 |
| 只做数据产品 | P0 -> P2 -> P3 | 不做 P1 与 P4。保留现有受邀模式 |

所有阶段都先做 P0。P0 是当前唯一的 blocker。小节按编号写。执行顺序按上表。

### 5.1 P0 部署与可达性

- 做什么：部署当前分支。检查 edge 路由。验证 `/api/tools`、`/tools`、`/docs`、`/connect`。修 `/settings/providers` 与 `/settings/members` 的失效链接。
- 为什么：代码已在当前分支。生产仍是旧 IA。一次部署同时开放 typed 参数表单、单工具 inspect API、`/connect` 接入页。生产 404 是部署缺口，不是代码缺口。
- 涉及文件：`apps/api/src/data_intelligence_hub/api/routes/tools.py`、`apps/scraper-console/src/app/tools/page.tsx`、`apps/scraper-console/src/app/docs/page.tsx`、`apps/scraper-console/src/app/connect/page.tsx`、`apps/scraper-console/src/lib/routes.ts`、`apps/scraper-console/src/components/quick-collect-drawer.tsx`、部署与 edge 配置（路径待核实）。
- 要不要改后端：不需要新后端代码。需要部署配置与路由配置。
- 人日：0.5-1。
- MVP：部署、冒烟测试、修失效链接。
- 完整版（不在本阶段）：单工具详情页 1-2；根 SKILL 2-4。
- 验收：`/api/tools` 200；`/tools`、`/docs`、`/connect` 200；`tests/integration/test_tools_routes.py` 8 passed；抽屉能渲染 typed 参数。
- 证据：生产 `/api/tools` 404、`/tools` 404、`/` 307 到 `/platforms`（2026-10-17 实测）。当前分支 `tools.py` 存在。`test_tools_routes.py` 8 passed。

### 5.2 P1 身份与租户统一

- 做什么：新增 `api_keys` 表，存 hash、prefix、workspace、scopes、last_used。`get_auth_context` 增加 Bearer 分支。删除 `deps.py:67` 的 demo 回退。修正 `get_default_workspace_for_user` 的排序。把 43-44 个 `get_demo_workspace` 调用点改为 `context.workspace`。MCP token 映射 workspace。
- 为什么：211/212 路由可匿名。所有业务路径固定 demo workspace。对外多租户售卖必须有身份与隔离。
- 涉及文件：`apps/api/src/data_intelligence_hub/api/deps.py`、`repositories/workspaces.py`、`models/workspace.py`、新 `models/api_key.py` 与迁移、`mcp_runtime/auth.py`、`api/routes/quick_collect.py`、`api/routes/tasks.py`、`api/routes/dashboard.py`、`api/routes/raw_records.py`、`services/auth_service.py`。
- 要不要改后端：要。
- 人日：MVP 12-21。构成：API key 4-7 + MCP workspace 2-4 + 租户 6-10。
- 完整版（另计）：轮换、scope、管理 UI 3-5；多 workspace 切换、邀请、管理员、数据迁移 10-15；OAuth/DCR 5-20。
- MVP 与完整版分界：MVP 只做单 workspace 默认绑定、Bearer 鉴权、去除 demo 回退。不做 OAuth，不做邀请，不做多 workspace 切换。
- 验收：API key 可创建、可撤销、可鉴权。跨 workspace 返回 403。业务路径不再读取 demo workspace。43-44 个调用点都有 workspace 上下文。

### 5.3 P2 统一运行回执、最小异步与调用记录读模型

- 做什么：`QuickCollectResponse` 与 MCP `collect` 增加 `records`、`output`、`usage`、`timing`。新增 `GET /api/runs/{id}` 详情。新增 MCP `get_run` 与 `list_records`。把同步 `await` 改为后台 asyncio 任务，增加 poll 与 stop。把 TaskRun 定义为 tool call record。先做只读统一视图。
- 为什么：Agent 只拿到 run id。结果要再查 `/api/raw-records`。长采集没有 poll/stop。调用记录分散在多个对象。
- 涉及文件：`api/routes/quick_collect.py`、`schemas/task.py`、`mcp_runtime/collect_service.py`、`mcp_runtime/server.py`、`services/collector_service.py`、`models/task.py`、`api/routes/raw_records.py`、`apps/scraper-console/src/app/runs/page.tsx`、`apps/scraper-console/src/app/runs/[runId]/page.tsx`。
- 要不要改后端：要。
- 人日：MVP 9-16。构成：回执 2-3 + 异步 MVP 5-10 + 只读调用记录 2-3。
- 完整版（另计）：新 `call_records` 表并覆盖 quick-collect、workflow、export、report、email 写入 15-25；durable queue 与多 worker 10-15。
- MVP 与完整版分界：MVP 复用 TaskRun 与 RawRecord，不新建 canonical 表。不引入 Redis。后台任务只保证单进程 poll/stop。
- 验收：一次调用返回首屏 records 与 usage。`GET /api/runs/{id}` 返回输入记录、状态、耗时、记录数。MCP 能读运行与记录。stop 能取消运行。
- 注意：不要复用 WorkflowRun/StepRun。它们是 fixture-only（`models/workflow_execution.py:65-68,114`）。

### 5.4 P3 发现、契约投影与健康聚合

- 做什么：在 `/api/tools` 增加 BM25、字段权重、中英文同义词、score 与 scoreBreakdown。新增 `/api/discover`，或合并进 `/api/tools`。MCP 增加 `discover` 与 `inspect`。`inspect` 复用 `to_public_tool`。从 TaskRun 计算每个端点的 p50、p95、成功率，加入 discover 与 inspect。补 MCP 5 个工具的 description。定义分类闭集与启动校验。写根 SKILL 与 llms.txt。补 robots、sitemap、OG。
- 为什么：当前只有子串匹配。MCP description 全为空。健康数据没有 live 写入。
- 涉及文件：`api/routes/tools.py`、`tool_catalog/projection.py`、`tool_catalog/public.py`、`mcp_runtime/server.py`、`platform_packages/service.py`、`platform_packages/status.py`、`models/provider_health.py`、`lib/platforms/catalog.ts`、`app/layout.tsx`、新增 `app/robots.ts`、`app/sitemap.ts`、`app/opengraph-image.tsx`、`public/llms.txt`。
- 要不要改后端：要。
- 人日：核心 10-17。构成：词法 discover 3-5 + inspect 投影 1-2 + 健康聚合 5-8 + MCP typed 投影 1-2。
- 可并行追加（不计入 10-17）：分类闭集 1-2；根 SKILL 2-4；SEO 与 llms 1-2；单工具详情页 1-2。
- 完整版（另计）：向量索引 8-15；契约层统一 15-20。
- MVP 与完整版分界：MVP 不引入向量库。MVP 的健康指标从 TaskRun 计算，不新建 provider_health 写入链。MVP 的 inspect 只复用现有 PublicTool。
- 验收：discover 返回 score 与 scoreBreakdown。inspect 返回 typed schema。`/api/tools` 与 discover 返回 p50、p95、成功率。MCP `list_tools` 的 description 非空。分类未知值在启动时失败。

### 5.5 P4 计费最小链路

- 做什么：把 288 条 `cost_hint` 解析为结构化 rate card，字段至少含 price_model、amount、unit、currency。TaskRun 记录 usage、cost、timing。新增 wallet、ledger、hold 最小表与并发扣减。run 回执与 `/api/tools` 增加 price、cost、billedUnits。实现失败零计费。实现 wallet activities 投影。实现用量与成本面板。
- 为什么：当前只有 cost_hint 文本。没有 hold，无法安全开放 Agent 自助调用。没有成本回执，运营无法解释一次采集花了多少。
- 涉及文件：新 `models/billing.py` 与迁移、`tool_catalog/models.py`、`schemas/collector_catalog.py`、`api/routes/collectors.py`、`api/routes/quick_collect.py`、`models/task.py`、新 `services/billing_service.py`、新 `api/routes/wallet.py`、`apps/scraper-console/src/app/wallet/page.tsx`、`apps/scraper-console/src/app/usage/page.tsx`。
- 要不要改后端：要。
- 人日：MVP 21-32。构成：billing kernel 20-30 + run cost 投影 1-2。
- 投影另计：activities 2-3；dashboard 3-5。
- 完整版（另计）：厂商 meter 对账 5-10；预算控制解除 fixture 4-6；多币种与税务待核实。
- MVP 与完整版分界：MVP 只做单一币种、按调用或按记录计量、单 workspace 钱包。不做厂商对账，不做多币种。
- 验收：调用前有 estimate 与 hold。调用后 settle。失败调用 zeroUsage。钱包返回 balance 与 held。run detail 返回 price、cost、billedUnits。wallet activities 有流水。
- 条件：只有对外自助售卖才必须做 P4。内部受邀与预付费可以停在 P3。现有整站方案 §3 的首期范围不含支付与钱包。

### 5.6 MVP 与完整版分界

| 阶段 | MVP | 完整版增量 | 不做的后果 |
|---|---|---|---|
| P0 | 部署、冒烟、修失效链接 0.5-1 | 单工具详情页 1-2；根 SKILL 2-4 | 目录与抽屉仍不可用 |
| P1 | API key + workspace 绑定 + 去 demo 12-21 | OAuth/DCR 5-20；轮换与 UI 3-5；多 workspace 10-15 | 只能内部使用，不能对外售卖 |
| P2 | 回执 + poll/stop + 只读调用记录 9-16 | call_records 表 15-25；durable queue 10-15 | 长采集不可靠，Agent 读结果困难 |
| P3 | 词法 discover + inspect + 健康 + MCP 描述 10-17 | 向量索引 8-15；契约层 15-20；分类、根 SKILL、SEO 4-8 | 发现质量弱，契约不统一 |
| P4 | rate card + usage + wallet/ledger/hold + run cost 21-32 | 厂商对账 5-10；activities 2-3；dashboard 3-5；预算 4-6 | 不能安全开放自助付费 |

P0-P4 的 MVP 合计：0.5-1 + 12-21 + 9-16 + 10-17 + 21-32 = 52.5-87 人日。

### 5.7 不进入 P0-P4 的工作

| 工作 | 人日 | 触发条件 |
|---|---|---|
| OAuth 与 DCR | 自建 10-20；第三方 IdP 5-8 | 公开 Agent 接入要求 OAuth |
| 官方 CLI | 8-15 | 内部脚本不够用。现有范围不做 |
| 完整 call_records 表 | 15-25 | 多入口必须统一调用记录 |
| Durable queue 与多 worker | 10-15 | 并发与重启恢复成为问题 |
| 完整输出契约 | 15-25 | 数据质量问题需要输出校验 |
| 密钥托管全量接入 | 15-25；限定平台 8-12 | 对外多租户使用平台凭据 |
| Webhook | 待核实 | 需要 provider 推送 |
| 资源生命周期 | 待核实 | 决定售卖 durable resources |
| x402 | 待核实 | 进入加密支付市场 |
| 公开目录 API | 1-2 | 需要匿名发现入口 |
| 多 Agent 分发 | 2-4 | 需要插件与技能分发 |
| 账户自助页 | 5-10 | 需要自助管理密钥与预算 |
| 文档站与 SEO | 1-2 | 公开获客 |
| 分类闭集 | 1-2 | 目录治理需要契约 |
| 根 SKILL | 2-4 | Agent 统一入口 |
| 单工具详情页 | 1-2 | 抽屉不够用 |
| 契约层统一 | 15-20 | 34 个定义 validate 的 collector 模块需要统一 |
| 浏览器产品化 | 待核实 | 需要真实浏览器采集链路 |
| 预算控制解除 fixture | 4-6 | 需要 live 预算 |

## 6. 超越路线

### 6.1 合规治理

Monid 没有采集策略层。只有 auth 与同源凭据规则（`engine/interfaces/mod.ts:34-59`）。

DIH 有 4 级出站策略与 197/4/57 的端点分布。证据见 `collectors/outbound_policy.py:19-118`。

产品化做法：

- 在目录与单工具页展示策略级别与拦截原因。
- 提供合规模板与审计导出。
- 在平台包 playbook 写明授权、频率与禁止项。
- 服务端强制策略。客户端不能绕过。

这条线面向受监管客户。它是 Monid 不做的市场。

### 6.2 数据交付链路

Monid 停在 run output。它没有数据集、版本、导出（`result.ts:69-94`）。

DIH 有 `RawRecord -> Dataset -> DatasetVersion -> DatasetExportJob`。支持 CSV、Excel、JSON、JSONL、sha256、行数、预览。

产品化做法：

- 把 3 类 dataset_type 扩展到更多已验证端点。
- 增加版本对比与完整度趋势。
- 公开血缘字段，支持审计复现。
- 把导出格式与字段结构写进平台包。

### 6.3 平台包

Monid 是单产品 Skill 与插件。DIH 有 70 个平台包（`platform_count=70`，2026-10-17 构造），每包 5 文件 ZIP。

产品化做法：

- 保持 manifest、playbook、trigger cases 同源。
- 给平台包加版本与 digest。
- 提供一键安装到 Claude Code 与其他 Agent。
- 不开放第三方 connector PR 市场。

### 6.4 中文资产

Monid 没有中文内容。DIH 有中文 UI、70 份中文 playbook、107 条坑点（计数来源见 §3.2）。

产品化做法：

- 把中文 playbook 发布为公开文档与 Skill 内容。
- 增加中英双语切换。
- 面向中国出海团队做案例与模板。
- 保持坑点为可检索条目。

### 6.5 数据控制台

Monid 开源仓库没有 UI。托管控制台是工具市场控制台。

DIH 有 15 个页面（`find apps/scraper-console/src/app -name page.tsx | wc -l` 为 15），覆盖目录、采集任务、运行、资产、报告与设置。

产品化做法：

- 以数据结果为中心组织首页与导航。
- 把运行、数据集、报告、告警放在同一工作区。
- 提供批量选择与抽屉操作。
- 不复制 Monid 的视觉素材。用自有设计系统。

### 6.6 无 playground 的反向机会

Monid 没有公开 playground。`https://monid.ai/playground` 返回 404（2026-10-17 实测）。

DIH 可以做 typed playground：

- 从 PublicTool 生成参数表单。
- 提供示例输入与 dry-run。
- 显示预估价格与策略检查。
- 返回首屏记录与运行链接。
- 先限受邀用户。加配额与成本保护。

这是 Agent 体验层的差异点。Monid 只有目录与文档。

### 6.7 运行证据与状态

Monid 的 health 与 p50/p95 只有两处声明。声明在 README 与 CLI 类型中。API 文档未列。源码无实现。

DIH 有 availability 6 态与 `[quick] [test]` 运行证据。可以从 TaskRun 聚合 p50、p95、成功率。

产品化做法：

- 在目录行展示最近核验时间与结果。
- 在单工具页展示最近窗口的成功率与延迟。
- 把证据时间与样本数一起展示。
- 不承诺 SLA。先展示实测。

### 6.8 审计与告警

DIH 的报告与邮件审计是 live。告警有 in_app/both。

产品化做法：

- 把审计事件导出为合规报告。
- 在 metering 后增加成本与用量告警。
- 补 email 告警通道。
- 把 drift 告警接入统一告警面板。

### 6.9 品牌与素材边界

MIT 覆盖代码，不覆盖品牌。

复刻 UI 时必须用自有等效物。不复制 Monid 的图片、logo、`SKILL.md` 文案与营销文案。首页继续按 monid.ai 网站逆向结果做。源码没有 UI，不能从源码复刻首页。

## 7. 明确不做

| 不做项 | 理由 |
|---|---|
| Marketplace 与 broker 商业模式 | 与 DIH 垂直数据产品定位冲突。复刻会把 DIH 变成中立工具市场 |
| 按调用抽成与供应商分成 | 商业定价不能从源码复制。需要按 DIH 成本结构自定 |
| 2,000+ tools 与 91 provider 的中立目录规模 | 需要长期 BD 与 connector PR 生态。合规策略会拒绝大量低优先级条目 |
| 第三方 connector PR 开放标准 | 与审核责任、合规边界、数据质量责任冲突。可内部采用 EndpointDoc 风格 |
| Clerk OAuth 与 DCR 的托管实现 | 不在 MIT 仓库。需要自建或选型。不能照搬 |
| Durable resource 租用业务 | 当前不卖号码、邮箱、VM。投入产出低。资源生命周期只作为后续选项 |
| x402 与加密支付 | 不在目标市场。计价单位与 floor 未核实 |
| Monid 品牌素材、SKILL 文案、logo、营销文案 | MIT 不覆盖品牌。必须原创 |
| Hosted Temporal 与 ClickHouse 实现 | 不在仓库。自建成本高。按 DIH 规模选型 |
| SLA 与 uptime 承诺 | 没有证据。先用运行证据说话 |
| 整体移植 Deno 引擎 | 30-60 人日。当前瓶颈不是执行器。用 Python EndpointSpec 增量替代 |
| Sealed unit 与沙箱 | 30-60 人日。DIH 是自研单体，不是开放 connector 市场。收益低 |
| 首期产品级 CLI | 现有整站方案明确不承诺。8-15 人日留到后续 |
| 首期支付、钱包、订阅 | 现有整站方案 §3 明确不做。P4 只在对外自助售卖时启用 |
| 复制 Monid 首页与目录视觉 | 源码没有 UI。首页按网站逆向结果做。用自有设计系统与素材 |

## 8. 待决策项

### 8.1 产品与范围

| 编号 | 决策项 | 选项 | 影响 |
|---|---|---|---|
| D1 | 产品模式 | 内部受邀 / 对外自助 / 预付费 | 决定 P1 与 P4 是否为 blocker |
| D2 | 首期用户 | 内部 Agent / 外部开发者 / 两者 | 决定路线顺序 |
| D3 | 是否现在部署当前分支 | 是 / 否 | 决定 P0 是否立即执行 |
| D4 | 是否保留静态 MCP token | 保留 / 换 API key | 影响 P1 范围 |
| D5 | 租户模型 | 单 workspace / 多 workspace | 影响 P1 成本与数据迁移 |
| D6 | 计费单位 | 按调用 / 按记录 / credit | 决定 P4 费率卡与 metering |
| D7 | 是否做 playground | 做 / 不做 | 影响超越路线 6.6 |
| D8 | 是否做公开目录 API | 做 / 不做 | 影响发现入口与限流 |
| D9 | 是否扩展数据集类型 | 扩展 / 保持 3 类 | 影响数据交付链路优势 |
| D10 | 是否做资源生命周期 | 做 / 不做 | 影响行74 与商业模式 |

### 8.2 技术与数据

| 编号 | 决策项 | 选项 | 影响 |
|---|---|---|---|
| D11 | 健康数据来源 | TaskRun 聚合 / 新建 provider_health 写入链 | 决定行3 与行55 的实现 |
| D12 | 搜索方案 | 词法 BM25 / 向量 / 两者 | 决定 P3 成本 |
| D13 | 分类法 | 闭集校验 / 保持展示分组 | 决定行6 成本 |
| D14 | 单工具详情载体 | 独立页 / 全屏抽屉 | 影响 `/tools/[toolId]` 路由语义 |
| D15 | 根 SKILL 范围 | 全局 / 分平台 / 两者 | 影响行34 与行49 |
| D16 | 账户页范围 | 密钥 / 钱包 / 预算 / 成员 | 影响行38 成本 |
| D17 | alias 去重修复 | 现在修 / 后置 | 影响 disabled 状态丢失 |
| D18 | 预算账本 | 解除 fixture / 保持 | 影响行27 |
| D19 | 浏览器采集 | 策略放行 / 外部浏览器服务 | 影响行17 |
| D20 | Webhook 范围 | provider-scope / resource-scope | 影响行73 |

### 8.3 待核实事实

以下事实未复现。不能当结论使用。

| 编号 | 待核实项 | 当前状态 |
|---|---|---|
| U1 | 部署与 edge 配置路径与负责人 | 未在文档中定位 |
| U2 | 生产最新 commit 与部署时间 | 只知道 fc1e60b 是生产基线。当前生产 commit 待核实 |
| U3 | Monid 托管 discover/inspect 响应是否含 p50/p95 | 文档未列。需要带 key 实测 |
| U4 | Monid 托管控制台 `/email-inboxes`、`/mint-assets`、`/resource-files`、`/rules` 的语义 | app bundle 有路由。docs 未解释 |
| U5 | x402 的 `amount=1000` 单位与 $0.01 floor | docs 与实测不一致 |
| U6 | provider_health 无 live 写入的原因 | 只有代码与测试证据 |
| U7 | 59 与 45 的口径差异 | 59 是文本引用行数。45 是实际调用数 |
| U8 | `/settings/providers` 与 `/settings/members` 是否计划实现 | 只在 `NEW_ROUTES` 声明，无页面 |
| U9 | 数据集扩展到哪些端点 | 需要业务排序 |
| U10 | 行17 浏览器产品化成本 | 需要策略与 harness 评估 |
| U11 | 行73 Webhook 成本 | 需要签名、重试、幂等设计 |
| U12 | 行74 资源生命周期成本 | 需要商业模式确认 |
| U13 | 行75 x402 成本与合规 | 需要支付与合规评估 |
| U14 | 69 行主干估算 356.5-686 人日的逐行复核 | 原矩阵估算。单价与拆分未复算 |
| U15 | 生产两套环境的差异 | 只复核路由状态。数据与配置差异未核对 |

---

文档完。
