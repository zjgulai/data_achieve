---
name: dih-insight-workbench-architecture
description: DIH 洞察工作台的目标架构设计。给出分层与依赖规则、bounded context 模块地图、三条关键数据流、契约/编排/证据/渲染四层设计、复用替换表、分阶段迁移与 ADR。实现前先读这份。
---

# 架构设计：DIH 洞察工作台

> 版本：v1.0 · 2026-10-20
> 输入：[PRD v1.0](../product/【PRD】母婴出海数据洞察Agent工作台.md) · [Playbook v1.0](../product/【Playbook】母婴出海洞察交付.md) · 代码现状清点（2026-10-20）
> 范围：`apps/api/src/data_intelligence_hub/`、`apps/scraper-console/src/`、`apps/web/src/components/reports/`
> 证据口径：路径与行号以当前工作树（分支 `deploy/tiktok-cdo-codex`）为准。生产结论只引用 2026-10-20 的只读 GET 探测记录。测试口径（2026-10-20）：单元 1980 passed / 集成 384 passed，均 0 failed。`reports/live-sweep/baseline-pytest-failures.txt` 的 137 条基线已作废，当前 0 failed。本文件不把 `integration` 测试当作复用证据。
> 契约以 [契约冻结 v1](./【契约冻结】v1-表名-枚举-接口.md) 为准。

## 0. 结论

1. 生产主链已经存在。路径是：`quick-collect` 或 task 触发 → `collector_service.execute_collection_task` → collector → `raw_records` → `normalization_service` → `signal_service` → `intelligence_service` → `report_service`。下一批以这条链为骨架。
2. 不重写采集内核。`collectors/base.py:60` 的协议、`collectors/registry.py:130` 的 86 个注册项、`collectors/outbound_policy.py:201` 的准入检查都可用。采集单元测试待复测。
3. 四个缺口按依赖顺序补：契约层、编排层、证据层、渲染层。鉴权与事务所有权是前置条件。两项必须先修。
4. 新增 `tool_catalog` 作为唯一事实源。`services/fixtures/capability_catalog_overseas_v2.json` 的 35 条 assertion 全部是 `candidate`，不能承担目录职责。
5. 新增 `claims` 与 `claim_evidence`。保留 `intelligence_items` 作为监控投影，不作为报告结论源。
6. 新建 run executor。不复用 `workflow_execution` 的 fixture 执行路径。`workflow_runs` 路由已挂载（`origin/main:143`），生产返回 200，`execution_mode=fixture`，`provider_call=False`。它是 fixture-only 能力，不承载真实执行。
7. 报告改为 `report_contract` 加两个纯渲染器。`_render_daily_report` 退役。
8. 53 个 policy 拒绝的采集器不在本期范围。目录必须标 `unsupported` 并隐藏。
9. 分 9 个阶段上线。每个阶段可独立上线、独立回滚。

### 0.1 下一批推荐顺序

下一批不做全量重写。按依赖顺序做前五步。每一步都有独立验收。

| 顺序 | 批次 | 内容 | 为什么先做 | 完成标志 |
|---|---|---|---|---|
| 1 | P0 基线 | 提交未跟踪文件；统一 catalog 事实源；鉴权 fail-closed；修事务所有权 | 不做这一步，后续所有统计与隔离都不可信 | 三处 catalog 一致；无 token 返回 401；失败集合为空集（0 failed） |
| 2 | P1 契约层 | `tool_catalog`、价格簿、输出 schema、派生器 | 目录是发现、计划、执行、报告的共同输入 | 284 行；33 可执行；53 unsupported |
| 3 | P2 目录与授权 | 域名 grant；`discover` / `inspect`；三处切读 | T5 与 T2/T3 的域名页依赖 grant | 对账一致；真实调用返回记录 |
| 4 | P3 等级引擎 | 阈值表与 `compute_run_evidence_grade` | 没有等级就无法判定 L4，也无法约束 claim | 四个等级单测通过 |
| 5 | P4 执行层 | `runs`、`run_steps`、`run_ledger_entries`；授权；真实调用 | 解锁 R5 与 R6 的唯一路径 | 一次真实 run 为 L4；成本字段可读 |
| 6 | P5–P6 证据与报告 | `claims`、`claim_evidence`、合同、双渲染 | 把 run 结果变成可交付报告 | 结论可点回原文；两页同步变 |
| 7 | P7–P8 工作台与接入 | `/workbench`、五模板、MCP 18 工具 | 把能力交付给业务用户与外部 agent | 5 分钟出报告；零文档接入 |

停止条件：任一阶段的独立验收未通过时，不得进入下一阶段。不得用后续阶段的 UI 掩盖前一阶段的数据缺口。

---

## 1. 分层与依赖规则

### 1.1 分层图

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ L5 接入层                                                                     │
│   REST：apps/api/src/data_intelligence_hub/api/routes/*.py                    │
│   MCP ：apps/api/src/data_intelligence_hub/mcp_runtime/server.py              │
│   UI  ：apps/scraper-console/src/app/**/page.tsx                              │
│   职责：协议解析、参数校验、身份上下文注入、错误映射。                          │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ 只允许调用 L4
┌───────────────────────────────▼──────────────────────────────────────────────┐
│ L4 应用服务层                                                                 │
│   services/collector_service.py · services/report_service.py                  │
│   services/tool_catalog/*（新） · services/run/*（新）                         │
│   services/evidence/*（新） · services/reporting/*（新）                       │
│   services/workflow_planner/* · services/identity/*（新）                      │
│   职责：用例编排、事务边界、授权与预算、事件发布。                              │
└───────────────┬───────────────────────────────────┬──────────────────────────┘
                │ 调用纯规则                          │ 调用端口
┌───────────────▼───────────────────┐   ┌───────────▼──────────────────────────┐
│ L3 领域层                          │   │ L2 采集适配层                        │
│   services/evidence/grade.py（新） │   │   collectors/*                        │
│   services/evidence/claim_policy.py│   │   services/reporting/render_*.py（新）│
│   services/reporting/contract.py   │   │   services/llm/*（新）                 │
│   services/reporting/templates.py  │   │   services/tool_catalog/adapters.py   │
│   职责：纯函数。无 DB、无网络、无框架│   │   职责：外部 IO。入参/出参为值对象。    │
└───────────────────────────────────┘   └───────────┬──────────────────────────┘
                                                    │ 只允许调用 L1
┌───────────────────────────────────────────────────▼──────────────────────────┐
│ L1 基础设施层                                                                 │
│   core/database.py · core/config.py · core/security.py                        │
│   models/*.py · repositories/*.py · scheduler/leases                           │
│   职责：连接、ORM、持久化、配置、加密。                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 依赖方向规则

| 编号 | 规则 | 理由 |
|---|---|---|
| R1 | L5 只能调用 L4。L5 不得导入 `models`、`repositories`、`collectors`。 | 路由只做协议转换。当前 `api/routes/quick_collect.py:14-21` 直接导入 `apify_actor`、models、repositories，违反本条。 |
| R2 | L4 可以调用 L3、L2、L1。L4 不得导入 `fastapi.Request` 或 `fastapi.Response`。 | 应用服务必须能被 MCP、scheduler、worker 和 REST 共同调用。 |
| R3 | L3 不依赖任何其他层。 | 证据等级、claim 状态、合同构建必须是纯函数，才能单元测试和复算。 |
| R4 | L2 可以调用 L1。L2 不得导入 L4 或 L5。 | 采集器只做外部 IO。租户、预算、授权属于 L4。 |
| R5 | L1 不得导入 L2、L3、L4、L5。 | 防止 ORM 层反向依赖业务。 |
| R6 | 只有 `main.py` 可以导入 `api.routes`。 | 防止 MCP 或 service 通过 HTTP 路由复用逻辑。当前 `mcp_runtime/collect_service.py:5` 违反本条。 |

### 1.3 依赖矩阵

| 从 \ 到 | L5 | L4 | L3 | L2 | L1 |
|---|---|---|---|---|---|
| L5 | — | 允许 | 只读值对象 | 禁止 | 只允许注入 `SessionDep`，禁止查询 |
| L4 | 禁止 | — | 允许 | 允许 | 允许 |
| L3 | 禁止 | 禁止 | — | 禁止 | 禁止 |
| L2 | 禁止 | 禁止 | 禁止 | — | 允许 |
| L1 | 禁止 | 禁止 | 禁止 | 禁止 | — |

说明：

- `api/deps.py:12` 定义 `SessionDep`。L5 可以声明它并把它传给 L4。L5 不得自己执行 SQLAlchemy 查询。
- `schemas/` 归入 L3 契约定义。新 schema 不得导入 ORM 模型。现有 `schemas/report.py:12-17` 导入了 `models/report.py`，属于待清理项。
- 前端不在这五层内。它只通过 REST 与 MCP 访问系统。

### 1.4 现行违规与处置

| # | 违规 | 位置 | 影响 | 处置 |
|---|---|---|---|---|
| 1 | MCP 调用 API 路由 | `mcp_runtime/collect_service.py:5` | 接入层反向依赖。worker 无法复用。 | 抽出 `CollectionApplicationService.quick_collect()`。MCP 调用服务。 |
| 2 | 路由包含业务逻辑与 ORM | `api/routes/quick_collect.py:14-21`、`:860-1020` | 路由不可单测。逻辑无法被 MCP 复用。 | 迁到 L4。路由只保留 DTO 与错误映射。 |
| 3 | 路由直接导入适配器常量 | `api/routes/quick_collect.py:14` | L5 依赖 L2。 | 常量迁到 `collectors/endpoint_catalog.py`。 |
| 4 | 路由局部导入策略函数 | `api/routes/collectors.py:4713` | L5 依赖 L2。 | 通过 `ToolCatalogService.policy_reason()` 暴露。 |
| 5 | 仓储层提交事务 | `repositories/datasets.py:88,161,259`、`repositories/cleaning_plans.py:24`、`repositories/automation_plans.py:67,76,142,152`、`repositories/scheduler.py:14` | 跨仓储调用会产生部分写入。 | 删除仓储内 `commit()`。应用服务是唯一事务所有者。 |
| 6 | Agent 走自身 HTTP 回环 | `agents/tiktok_cdo/data_sources.py:223`、`:274` | 固定 30 秒超时。绕过应用服务。 | 改为调用 L4 应用服务。 |
| 7 | 证据构建函数产出 ORM 对象 | `services/evidence_service.py:13` | 不可纯测。 | 旧函数保留。新 claim builder 使用值对象。 |
| 8 | fixture-only 路由与模型 | `api/routes/workflow_runs.py:170`、`models/workflow_execution.py:35` | 已挂载（`origin/main:143`），生产返回 200，`execution_mode=fixture`。 | 保留并标 `fixture_only`。不得删除，不接生产执行。见 ADR-02。 |
| 9 | 单文件过大 | `services/automation_service.py` 13537 行 | 合并冲突与回归面放大。 | 冻结。新功能不得进入。见 ADR-08。 |

### 1.5 执行机制

新增测试 `apps/api/tests/unit/test_architecture_boundaries.py`。测试用 AST 检查，不依赖运行时。

必须检查的规则：

1. `services/`、`collectors/`、`scheduler/`、`mcp_runtime/` 下不得出现 `from data_intelligence_hub.api`。
2. `repositories/` 下不得出现 `session.commit()`。
3. `services/*/domain.py` 与 `services/*/contracts.py` 不得导入 `sqlalchemy`、`fastapi`、`httpx`。
4. `api/routes/` 下不得直接导入 `models.`、`repositories.`、`collectors.`。过渡期用白名单，白名单只减不增。
5. `main.py` 之外不得导入 `api.routes`。

CI 必须在 `ruff` 之后运行该测试。违反规则时构建失败。

---

## 2. 模块地图

模块按 bounded context 划分，不按技术分层划分。每个上下文拥有自己的数据与接口。跨上下文只能调用对方公开的应用服务。

### 2.1 上下文总览

| 编号 | 上下文 | 职责 | 拥有表 | 处置 |
|---|---|---|---|---|
| BC-01 | 工具发现 Tool Discovery | ToolContract 的派生、存储、检索、健康度 | `tool_catalog`、`tool_verification_events`（M02） | 新 + 扩展 |
| BC-02 | 采集执行 Run Execution | run 生命周期、步骤调用、预算、原始记录 | `sources`、`collection_tasks`、`task_runs`、`raw_records`、`runs`、`run_steps`（M10）、`run_ledger_entries`（M08） | 扩展 + 新 |
| BC-03 | 证据与洞察 Evidence & Insight | 规范化、实体快照、信号、claim、证据等级 | `entities`、`entity_snapshots`、`signals`、`intelligence_items`、`evidences`、`claims`、`claim_evidence`（M05） | 扩展 + 新 |
| BC-04 | 报告交付 Report Delivery | 合同生成、校验、双渲染、发布、发送 | `reports`、`report_subscriptions`、`report_subscription_runs`、`report_audit_events`、`report_artifacts`、`report_shares`（M07）、`report_templates`、`report_template_versions`（M06） | 扩展 + 新 |
| BC-05 | 计划与自动化 Planning & Automation | 计划预览、版本、批准、调度 | `workflow_plans`、`workflow_versions`、`workflow_templates`、`workflow_scope_templates` | 复用 + 扩展 |
| BC-06 | 身份与访问 Identity & Access | 用户、工作区、成员、项目 key、凭据 | `users`、`workspaces`、`workspace_members`、`platform_credential_bundles`、`project_api_keys`（M09）、`authorizations`（M08） | 扩展 + 新 |
| BC-07 | Agent 接入 Agent Access | MCP 传输、工具 schema、配额、接入文档 | 无（只读 M09 的 `project_api_keys`） | 扩展 |
| BC-08 | 工作台前端 Workbench Console | 公开目录、工作台、报告阅读器 | 无（只读 API） | 扩展 + 新 + 替换 |

### 2.2 BC-01 工具发现 Tool Discovery

**职责**

1. 从现有 collector 注册表与 endpoint 映射派生 `ToolContract`。
2. 维护 `tool_catalog`。目录条目必须能被执行，或被显式标为 `unsupported`。
3. 提供 `discover` 与 `inspect` 查询。
4. 维护健康度、最近核验时间、最近记录数。

**对外接口**

- Python：`ToolCatalogService.discover(DiscoveryQuery) -> list[ToolSummary]`、`ToolCatalogService.inspect(tool_id) -> ToolContract`、`ToolCatalogService.policy_reason(tool_id) -> str | None`。
- REST：`GET /api/tools`、`GET /api/tools/{tool_id}`、`GET /api/tools/discover`。
- MCP：`discover`、`inspect`、改造后的 `list_capabilities`、`describe_capability`。
- 内部只读端口：`ToolCatalogReader.snapshot() -> ToolCatalogSnapshot`。

**依赖**

- 依赖 L1：`models`、`repositories`、`core/database.py:43-52`。
- 只读 `collectors/endpoint_catalog.py` 的常量。该文件由 `api/routes/quick_collect.py:35` 与 `:437` 迁入。
- 不依赖 BC-02、BC-03、BC-04。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/collector_catalog.py:24`：99 个 `CollectorDefinition`。`:827` 是配置校验入口。
- `apps/api/src/data_intelligence_hub/api/routes/collectors.py:46`：`/catalog` 读模型。`:4713-4745` 硬编码 303 个 `CollectorEndpointMetadata`。
- `apps/api/src/data_intelligence_hub/services/capability_catalog.py:23`：读取静态 fixture。fixture 有 7 个 implementation、35 条 assertion、14 条 evidence。35 条 assertion 的状态全部是 `candidate`。
- `apps/api/src/data_intelligence_hub/services/capability_matrix.py:46`：能力矩阵读模型。
- `apps/api/src/data_intelligence_hub/platform_packages/service.py:52`：平台包目录。
- `apps/api/src/data_intelligence_hub/services/social_provider.py:140`、`:348`、`:395`：平台目录与门禁。

**状态**

- `collector_catalog`：保留。
- `api/routes/collectors.py` 的端点元数据：替换。
- `capability_catalog` fixture：冻结为只读。见 ADR-01。
- `tool_catalog`：新建。

### 2.3 BC-02 采集执行 Run Execution

**职责**

1. 创建 run。一个 run 对应一个已批准计划。
2. 预留与结算预算。
3. 解析 `tool_id` 到适配器。
4. 执行采集。落 `raw_records`。
5. 触发规范化与信号检测。
6. 写运行账本与步骤结果。

**对外接口**

- Python：`RunService.create_run(plan_id, authorization_id) -> Run`、`RunService.start(run_id)`、`RunService.cancel(run_id)`、`execute_collector_call(...)`。
- REST：`POST /api/runs`、`GET /api/runs/{run_id}`、`POST /api/runs/{run_id}/cancel`、`GET /api/runs/{run_id}/steps`、`POST /api/quick-collect`。
- MCP：`collect`、`get_run`、`list_records`。

**依赖**

- 依赖 BC-01 解析 tool 合同。
- 依赖 BC-06 获取 `AuthContext`、项目凭据、授权。
- 依赖 L2：`collectors/registry.py:220`、`collectors/outbound_policy.py:201`、`collectors/guarded_http.py:99`。
- 依赖 L1：`models/task.py`、`models/raw_record.py`、`core/database.py:50-52`。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/collector_service.py:73`：`execute_collection_task`。任务行锁在 `:302-318`。超时在 `:130`。去重哈希在 `:348`。规范化在 `:379`。信号检测在 `:381`。
- `apps/api/src/data_intelligence_hub/scheduler/service.py:71`、`:91`：调度器启动与 tick。
- `apps/api/src/data_intelligence_hub/services/task_service.py:86`：手动运行。
- `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:960`：同步快速采集。`:1027`：异步快速采集。
- `apps/api/src/data_intelligence_hub/models/task.py:19`、`:44`：任务与运行表。
- `apps/api/src/data_intelligence_hub/models/raw_record.py:30`：原始记录表。

**状态**

- `execute_collection_task`：扩展。拆出 `execute_collector_call`，保留原有行为。
- `scheduler`、`task_service`、`source_service`：保留。
- `quick_collect` 异步路径：替换。
- `runs`、`run_steps`、`run_ledger_entries`：新建。

### 2.4 BC-03 证据与洞察 Evidence & Insight

**职责**

1. 把 `raw_records` 规范化为 `entities` 与 `entity_snapshots`。
2. 从快照差异检测 `signals`。
3. 从信号生成 `intelligence_items`。这是监控投影。
4. 从 run 的规范化记录生成 `claims`，并绑定 `claim_evidence`。
5. 计算 run 的证据等级。

**对外接口**

- Python：`normalize_raw_record(session, workspace, raw_record)`、`detect_signals_for_snapshots(session, workspace, snapshots)`、`ClaimService.build_for_run(run_id)`、`compute_run_evidence_grade(...)`。
- REST：`GET /api/entities`、`GET /api/signals`、`GET /api/intelligence`、`GET /api/claims`（新）。
- MCP：`list_records` 返回原始记录。claim 查询走 REST。

**依赖**

- 依赖 BC-02 产出的 `raw_records` 与 `task_runs`。
- 依赖 L1：`models/entity.py`、`models/signal.py`、`models/intelligence.py`、`repositories/*`。
- 不依赖 BC-04。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/normalization_service.py:32`：`normalize_raw_record`。`:73-87` 只分派 7 类 `record_type`。未知类型返回空列表。
- `apps/api/src/data_intelligence_hub/services/signal_service.py:118`：`detect_signals_for_snapshots`。`:153`：数据质量异常。`:259-260`：GitHub stars 规则。`:291-292`：网页内容哈希规则。
- `apps/api/src/data_intelligence_hub/services/intelligence_service.py:128`：`generate_intelligence_for_signal`。
- `apps/api/src/data_intelligence_hub/services/evidence_service.py:13`：`build_evidences_for_signal`。
- `apps/api/src/data_intelligence_hub/models/intelligence.py:22`、`:51`：`intelligence_items` 与 `evidences`。
- `apps/api/src/data_intelligence_hub/models/entity.py:20`、`:57`：实体与快照。
- `apps/api/src/data_intelligence_hub/models/signal.py:19`：信号表。

**状态**

- `normalization_service`：扩展。新增品类映射。
- `signal_service`：扩展。规则改为注册表。
- `intelligence_service`：保留，作为监控投影。
- `claims`、`claim_evidence`：新建。
- 证据等级函数：新建。

### 2.5 BC-04 报告交付 Report Delivery

**职责**

1. 生成 `report_contract`。
2. 校验合同。
3. 渲染 `report.html` 与 `sop.html`。
4. 存档合同、HTML 与哈希。
5. 发布、签收、分享、发送。
6. 执行报告订阅。

**对外接口**

- Python：`ReportContractBuilder.build(request) -> ReportContract`、`ReportContractValidator.validate(contract) -> ValidationReport`、`render_report_html(contract, template) -> str`、`render_sop_html(contract, template) -> str`、`ReportService.generate_report(...)`、`ReportService.dispatch_report(...)`。
- REST：`GET/POST /api/reports`、`POST /api/reports/generate`、`POST /api/reports/{id}/send`、`GET /api/reports/{id}`、`GET /api/reports/subscriptions`。
- MCP：`create_report`。

**依赖**

- 依赖 BC-03 的 `claims`、`evidences`、`run_ledger`。
- 依赖 BC-04 的模板注册表（拥有模块 M06）。模板注册表由 M06 持有，BC-05 只读。
- 依赖 BC-06 的 `AuthContext`。
- 依赖 L1：`models/report.py`、`repositories/reports.py`。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/report_service.py:184`：订阅 upsert。`:536`：订阅执行。`:647`：报告生成。`:729`：发送。`:804`：分发。`:1198`：`_render_daily_report`。
- `apps/api/src/data_intelligence_hub/api/routes/reports.py:54-299`：13 个报告端点。
- `apps/api/src/data_intelligence_hub/models/report.py:16`、`:37`、`:58`、`:88`：报告、审计、订阅、订阅运行。
- `apps/api/src/data_intelligence_hub/services/notification_service.py:160`、`:603`：站内信与邮件发送。
- `apps/web/src/components/reports/report-detail-panel.tsx:58`：现有报告面板。

**状态**

- 订阅、发送、审计、幂等：保留。
- `_render_daily_report`：替换。
- `report_artifacts`、`report_shares`：新建。
- 两个渲染器：新建。

### 2.6 BC-05 计划与自动化 Planning & Automation

**职责**

1. 把七槽位任务单规范化为 `PlanningInput`。
2. 扩展候选词。候选来自 `tool_catalog`。
3. 解析 route plan。每个 route 绑定 `tool_id`、成本、目标证据等级。
4. 保存计划与版本。
5. 调度到期任务与报告订阅。

**对外接口**

- Python：`build_workflow_plan_result(input) -> WorkflowPlanBuildResult`、`resolve_route_plans(...)`、`WorkflowPlanService.preview/save/transition`。
- REST：`POST /api/workbench/tasks`、`GET /api/workbench/tasks`、`GET /api/workbench/tasks/{task_id}`、`POST /api/projects/{project_id}/workflow-plans/preview`、`GET/POST /api/projects/{project_id}/workflow-plans`。
- MCP：无。计划由 REST 或工作台触发。

**依赖**

- 依赖 BC-01 的 `ToolCatalogReader`。planner 不直接读 `capability_catalog` fixture。
- 依赖 BC-04 的 `ReportTemplateRegistry`（M06），只读。
- 依赖 L1：`models/workflow_plan.py`、`repositories/workflow_plans.py`。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py:477`：`build_workflow_plan_result`。
- `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py:67`：`resolve_route_plans`。`:293-298` 拒绝 `candidate`。`:570` 固定 `execution_authorized=False`。
- `apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py:17-19`：fixture 路径。fixture 只有 `acme` 与 `running shoes` 两个词条。
- `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:501`：preview。`:606`：保存 plan。`:742`：创建版本。
- `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py:89`：版本快照校验。

**状态**

- planner 与持久化：复用。
- 候选扩展：扩展。fixture 只用于测试。
- `capability_resolver`：保留算法，新增 `ToolCatalogAssertionProjector`。
- run 执行：不在本上下文。见 BC-02。

### 2.7 BC-06 身份与访问 Identity & Access

**职责**

1. 注册、登录、会话。
2. `AuthContext` 注入。
3. 工作区与项目成员隔离。
4. 项目级 API key。
5. 项目级 Provider 凭据解析。
6. 计划批准与授权。

**对外接口**

- Python：`register_user`、`login_user`、`get_session_for_user`、`get_auth_context`、`ProjectApiKeyResolver.resolve(key) -> ProjectPrincipal`、`CredentialResolver.resolve(project_id, provider) -> SecretStr`。
- REST：`POST /api/auth/register`、`POST /api/auth/login`、`GET/PUT /api/settings/platform-credentials`。
- MCP：Bearer key 解析在中间件。

**依赖**

- 依赖 L1：`models/user.py`、`models/workspace.py`、`models/project.py`、`models/platform_credential.py`、`core/security.py`。
- 被所有其他上下文依赖。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/services/auth_service.py:38`、`:81`、`:97`。
- `apps/api/src/data_intelligence_hub/core/security.py:23-43`：JWT 与 bcrypt。
- `apps/api/src/data_intelligence_hub/api/deps.py:28-51`：`get_current_user`。`:54-79`：`get_auth_context`，含 demo 回退。
- `apps/api/src/data_intelligence_hub/repositories/workspaces.py:10`、`:35`：demo workspace。
- `apps/api/src/data_intelligence_hub/services/platform_credentials.py:172`、`:189`：凭据读写。表 `platform_credential_bundles` 只有 workspace 维度，见 `models/platform_credential.py:11-12`。
- `apps/api/src/data_intelligence_hub/core/config.py:50`：`platform_credential_master_key`。

**状态**

- 注册、登录、JWT：保留。
- `get_auth_context`：扩展。必须 fail-closed。
- 凭据：扩展。新增 project 维度。
- `project_api_keys`、`authorizations`：新建。

### 2.8 BC-07 Agent 接入 Agent Access

**职责**

1. 暴露 MCP 传输。
2. 提供 18 个工具：13 个现有加 5 个新增。
3. 执行配额与并发限制。
4. 提供 `SKILL.md` 与 `llms.txt`。

**对外接口**

- MCP：`list_platforms`、`list_capabilities`、`describe_capability`、`get_playbook`、`collect`、8 个 `tiktok_*`、`discover`、`inspect`、`get_run`、`list_records`、`create_report`。
- REST：`GET /llms.txt`、`GET /llms-full.txt`、`GET /skills/dih/SKILL.md`。

**依赖**

- 依赖 BC-01、BC-02、BC-04 的应用服务。
- 依赖 BC-06 的 `ProjectApiKeyResolver`。
- 依赖 L1：`core/config.py:51-58`。

**现有代码位置**

- `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:55-309`：13 个工具。`:35-52`：transport security，`allowed_hosts` 不含第二套生产域名。
- `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py:20-23`：token 为空时直接放行。
- `apps/api/src/data_intelligence_hub/mcp_runtime/governance.py:54-86`：内存限额。
- `apps/api/src/data_intelligence_hub/mcp_runtime/collect_service.py:5`：调用 API 路由。
- `apps/api/src/data_intelligence_hub/services/tiktok_tools.py:29`、`:468`、`:480`：8 个 TikTok 工具。
- `apps/api/src/data_intelligence_hub/main.py:116`：`app.mount("/mcp", ...)`。

**状态**

- 传输与工具注册：保留。
- 鉴权与治理：扩展。
- 工具从 13 增到 18：扩展。
- 项目 key：新建。

### 2.9 BC-08 工作台前端 Workbench Console

**职责**

1. 公开区：首页、能力目录、能力详情、分享报告、文档。
2. 授权区：工作台、任务详情、报告中心、报告阅读、连接器、设置。
3. 只通过 REST 调用后端。不得包含业务规则。

**对外接口**

- 页面路由见 PRD 第 3.3 节。目标 11 条路由，4 个一级导航：工作台、报告、连接器、设置。
- 现有 `apps/scraper-console/src/app` 有 16 个 `page.tsx`。
- 组件：`AppShell`、`Sidebar`、`TopBar`、`StatTile`、`PlatformLogo`、`ConfirmDialog`、`useFocusTrap`、`DataPreviewDrawer`、`SkillsDirectory`、`SkillDetail`。

**依赖**

- 依赖 L5 的 REST API。浏览器直连 `NEXT_PUBLIC_API_URL`，生产由 edge 同源转发 `/api/`。
- 依赖设计 token：`apps/scraper-console/src/app/globals.css:4-112`。

**现有代码位置**

- `apps/scraper-console/src/components/layout/app-shell.tsx:16`。
- `apps/scraper-console/src/components/layout/sidebar.tsx:7-20`：当前 8 个主导航项与 1 个辅助项。目标收敛为 4 个一级导航（工作台、报告、连接器、设置）；`/dashboard`、`/raw-records`、`/settings/account` 不作为一级入口。
- `apps/scraper-console/src/lib/api/client.ts:13-34`：`apiFetch`。无超时、无重试、无响应校验。
- `apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx:24`、`:735`：162 个硬编码 `endpoint_type`。
- `apps/scraper-console/src/app/projects/[id]/page.tsx:144`、`:156`：静态占位。
- `apps/scraper-console/src/app/settings/account/page.tsx:10`：死页。

**状态**

- 布局壳、展示组件、数据预览、Skill 目录：保留。
- 侧栏、项目详情、API 客户端、快速采集抽屉：扩展。
- 账户设置页：删除或重做。
- 工作台、能力目录、报告阅读器：新建。
- `apps/web` 三个报告组件：包装或替换。

#### 2.9.1 UI/UX 边界

1. 路由分两组。公开区是 `/`、`/capabilities`、`/capabilities/[id]`、`/reports/public/[id]`、`/docs`。授权区是 `/workbench`、`/workbench/[taskId]`、`/reports`、`/reports/[id]`、`/connectors`、`/settings`。规则来自 PRD 3.3。
2. 公开目录必须 SSR 出首屏。`apps/scraper-console/src/app/skills/page.tsx` 已经是服务端组件，可作为模式。授权区可以用客户端组件加 TanStack Query。
3. 工作台是单页三栏：左项目与任务，中对话与计划单，右证据抽屉与成本。不得把任务、运行、原始记录做成一级入口。规则来自 PRD 6.4。
4. 报告阅读页必须支持章节锚点、市场筛选、分群 tab、证据抽屉、明暗主题、打印、复制单条结论。不做排序与图表 tooltip。规则来自 PRD 6.6。
5. 组件复用只认有跨页证据的资产：`AppShell`、`Sidebar`、`TopBar`、`StatTile`、`PlatformLogo`、`useFocusTrap`、`ConfirmDialog`、`DataPreviewDrawer`。`QuickCollectDrawer`、`ConfirmDialog`、`DataPreviewDrawer` 目前只在单页使用。不得把它们称为跨页复用资产。
6. 设计 token 以 `apps/scraper-console/src/app/globals.css:4-112` 为唯一来源。报告 HTML 内嵌冻结的 token 副本，不引用控制台 CSS。
7. 可访问性：覆盖层必须使用 `useFocusTrap`，支持 Escape 关闭。动效必须遵守 `prefers-reduced-motion`，见 `globals.css:114-120`。
8. 暗色模式当前不存在。`globals.css` 只有 `:root` 与 `[data-theme=light]`。必须新增 `[data-theme=dark]` 与切换组件。
9. 错误与加载态必须走路由级 `error.tsx` 与 `loading.tsx`。不得每页复制内联 spinner。
10. 所有 API 响应必须做运行时校验。`zod` 已在 `apps/scraper-console/package.json` 中，但 `src` 没有使用。

### 2.10 上下文依赖图

```text
                 ┌──────────────────────┐
                 │ BC-06 身份与访问       │
                 │ AuthContext / Keys    │
                 └───────┬──────────────┘
                         │ 被所有上下文依赖
     ┌───────────────────┼────────────────────┬───────────────────┐
     ▼                   ▼                    ▼                   ▼
┌─────────────┐   ┌─────────────┐      ┌─────────────┐     ┌─────────────┐
│ BC-01 发现   │   │ BC-02 执行   │      │ BC-03 证据   │     │ BC-04 报告   │
│ tool_catalog│◄──│ RunService  │─────►│ ClaimService│────►│ Contract    │
└──────┬──────┘   └──────┬──────┘      └─────────────┘     └──────┬──────┘
       │                 │                                       │
       │                 │                                       │
       ▼                 ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BC-05 计划与自动化：planner 读 BC-01；模板读 BC-04；调度触发 BC-02      │
└─────────────────────────────────────────────────────────────────────┘
       ▲
       │ MCP / REST
┌──────┴──────┐   ┌────────────────────┐
│ BC-07 Agent │   │ BC-08 工作台前端     │
└─────────────┘   └────────────────────┘
```

规则：

1. BC-05 允许读 BC-01 与 BC-04。BC-04 不得反向依赖 BC-05。
2. BC-02 允许调用 BC-01。BC-01 不得调用 BC-02。
3. BC-03 只读 BC-02 的结果表。不得调用采集适配器。
4. BC-04 只读 BC-03 的 claim 与 evidence。不得修改它们。
5. 禁止循环依赖。新增依赖必须在本文更新依赖图。

---

## 3. 关键数据流

### 3.1 一次 discover 查询

#### 调用序列

```text
1. 用户或 Agent 输入自然语言查询。
2. L5 接收 GET /api/tools/discover?q=德国吸乳器差评&markets=DE&limit=10。
3. L4 ToolDiscoveryService.discover(DiscoveryQuery)。
4. L4 调 ToolCatalogReader.snapshot()，读 tool_catalog。
5. 过滤：execution_kind=unsupported、health_status=outage、markets 不含目标市场。
6. 打分：category 匹配度、content_types 匹配度、成本、verified_at。
7. 生成 why_this。成本按 cost_model.estimate_formula 计算。
8. 返回 ToolSummary[]。响应带 snapshot_id。
9. 不写库。不发外部请求。不调用 LLM。
```

#### 失败点

| 失败 | 判据 | 返回 | 处理 |
|---|---|---|---|
| 目录不可用 | `tool_catalog` 为空或查询失败 | `503 catalog_unavailable` | 客户端显示重试。不得回退静态 fixture。 |
| 快照变化 | 请求期间目录版本变化 | 200，响应带旧 `snapshot_id` | 客户端提示“目录已更新”。下一次请求取新快照。 |
| 查询过宽 | 命中超过 100 条 | 200，带 category facet 计数 | 不静默截断。必须告诉调用方收窄条件。 |
| 无结果 | 过滤后为 0 | 200，`reason=no_match` | 不返回 404。给出最近核验时间与缺失市场。 |
| 未登录 | 无有效会话 | 401 | BC-06 fail-closed。 |
| 条目过期 | `verified_at` 超过 30 天 | 200，`stale=true` | 不隐藏。排序降权。 |
| 显式请求不可用工具 | `tool_id` 为 unsupported | 200，`executable=false` | 放在结果末尾。`inspect` 仍返回合同。 |

#### 验收

1. 输入“德国吸乳器差评”，前 3 条包含 Amazon 评论类工具。
2. 响应每条都有 `cost_estimate`、`verified_at`、`snapshot_id`。
3. 目录 API、MCP `list_capabilities`、控制台三处的 `tool_id` 集合一致。

### 3.2 一次真实 run：从计划到 raw_record

#### 调用序列

```text
1. POST /api/workbench/plans/preview，提交七槽位。
2. Planner 执行 normalization → candidate expansion → route resolve → cost estimate。
3. 返回 PlanContract：步骤、tool_id、target_grade、预计成本、排除理由。
4. 人批准。POST /api/workbench/plans/{plan_id}/approve。
5. BC-06 写 Authorization：scope、max_cost_usd、granted_at、expires_at。
6. POST /api/runs {plan_id, authorization_id}。RunService.create_run 写 runs(status=queued)。
7. Worker 领取 run。用租约或 SELECT ... FOR UPDATE SKIP LOCKED。
8. 对每个 step：
   8.1 预留预算。写 run_ledger_entries(entry_kind=reserve)。
   8.2 ToolAdapterRegistry.resolve(tool_id)。
   8.3 Adapter 调 assert_collector_allowed(collector_type)。
   8.4 Adapter 调 build_collector(collector_type, config)。
   8.5 collection_scope 建立请求预算。
   8.6 collector.collect()。
   8.7 按 (source_id, content_hash) 去重。写 raw_records。
   8.8 normalize_raw_record。写 entities 与 entity_snapshots。
   8.9 detect_signals_for_snapshots。写 signals。
   8.10 结算预算。写 run_ledger_entries(entry_kind=settle)。
   8.11 写 task_runs 与 run_steps 的终态、成本、outcome。
9. G6 统计合格记录数。compute_run_evidence_grade。
10. 写 run_evidence_grades.grade 与 runs.evidence_grade。run 状态置 completed / failed。
```

#### 时序图

```text
Client        PlanService        RunService        ToolAdapter       Collector        DB
  │ preview ────►│                  │                  │                │              │
  │◄─ plan ──────│                  │                  │                │              │
  │ approve ────►│ Authorization     │                  │                │              │
  │ create run ────────────────────►│                  │                │              │
  │               │                  │ reserve ──────────────────────────────────────►│
  │               │                  │ execute ────────►│ policy ───────►│              │
  │               │                  │                  │                │ raw ────────►│
  │               │                  │◄─ result ────────│◄─ records ─────│              │
  │               │                  │ normalize + signal ───────────────────────────►│
  │               │                  │ settle ───────────────────────────────────────►│
  │◄─ run status ───────────────────│                  │                │              │
```

#### 失败点

| 失败 | 判据 | 运行结果 | 处理 |
|---|---|---|---|
| 计划未批准 | 无 Authorization 或已撤销 | `plan_not_approved` | 409。不创建 run。 |
| 授权过期 | `expires_at < now` | `authorization_expired` | 403。不发起调用。 |
| 预算不足 | 估算超过剩余额度 | `budget_exceeded` | 409。阻断，不降级。 |
| 策略拒绝 | `CollectionPolicyDenied` | step `config_gated` | 记录原因。run 继续。报告写 gap。 |
| Provider 鉴权失败 | 401 或 403 | step `failed` | 不重试。health_status=degraded。 |
| Provider 限流 | 429 或 5xx | step `failed` | 重试 3 次，指数退避。仍失败则终态 failed。 |
| 超时 | `asyncio.wait_for` 超时 | step `failed` | 释放预算。不重试同一 step。 |
| 空结果 | 调用成功，0 条 | step `empty` | 不是失败。报告写 Evidence gap。 |
| 未知记录类型 | `build_snapshot_drafts` 返回空 | run 继续 | 记录 `normalization_unsupported`。不得静默。 |
| 重复记录 | `(source_id, content_hash)` 命中 | 跳过写入 | 计入日志。不计入 records_count。 |
| 跨租户读取 | project 不属于 workspace | 403 | 不返回任何记录。 |
| 进程崩溃 | 租约过期 | step `failed` | 有 provider_run_id 时按幂等键核对。不得重复计费。 |

#### 验收

1. 一次 T1 真实 run 的 `evidence_grade` 为 `L4_authorized_live`。
2. `task_runs` 能读到 `unit_price`、`total_cost_usd`、`remaining_budget`。
3. 任一步骤失败时，run 状态与 step 状态一致。不得出现 run=completed 但 step=failed 的组合。

### 3.3 一次报告：从 claim 到两份 HTML

#### 调用序列

```text
1. POST /api/reports {task_id, template_id}。或由订阅触发。
2. BC-03 ClaimService.list_for_task(task_id)。读取 claims、claim_evidence、evidences。
3. MetricService.compute(claims)。生成 metrics[]，每条带 count_type 与分母。
4. ReportContractBuilder.build(request)。读模板与 run_ledger。
5. 生成 report_contract：identity、decision、gates、coverage、metrics、claims、
   evidences、run_ledger、limits、unknowns。
6. ReportContractValidator.validate(contract)。Pydantic + JSON Schema + 语义规则。
7. RFC 8785 规范化 JSON。计算 contract_sha256。
8. render_report_html(contract, template)。输出 report.html。
9. render_sop_html(contract, template)。输出 sop.html。
10. 计算两个 HTML 的 sha256。
11. 一个事务写 reports、report_artifacts。
12. 签收。status: generated → signed → published。
13. 生成 report_shares。调用 dispatch_report 发 in_app 或 email。
```

#### 失败点

| 失败 | 判据 | 结果 | 处理 |
|---|---|---|---|
| claim 无证据 | `claim_evidence` 少于 1 条 | G-Evidence fail | claim 降为 `hypothesis` 或 `evidence_gap`。不得输出 confirmed。 |
| 缺反证字段 | `counterevidence_text` 为空 | 合同校验失败 | 不生成 artifact。返回 `report_contract_invalid`。 |
| claim 状态超过等级 | status 高于 grade 允许上限 | 合同校验失败 | 自动降级并记录。 |
| 模板缺章节 | sections 与模板不一致 | 合同校验失败 | 不渲染。 |
| 命中禁止输出 | 文案命中 prohibited_outputs | 合同校验失败 | 阻断发布。要求人工改写。 |
| 哈希不一致 | 重算 sha256 不同 | 发布阻断 | 保留旧 artifact。记录审计事件。 |
| 未签收 | `G-Publish` 未通过 | `publish_blocked` | 只能内部预览。不得公开分享。 |
| 邮件门禁关闭 | `email_live_send_enabled=false` | 只发站内信 | 写审计事件。不得静默。 |
| 渲染器异常 | 抛异常 | 不发布 | 合同保留。可重试渲染。 |

#### 验收

1. 改合同里的一个数字，两个渲染器的输出都变。
2. 报告页脚能读到两个 HTML 哈希与合同哈希。
3. 合同校验有单元测试。故意破坏必填字段时必须报错。
4. 报告与 SOP 的 gate 状态一致。

---

## 4. 契约层设计

### 4.1 派生源与计数

`tool_catalog` 的构建输入必须来自现有代码，不得手工维护第二份清单。

| 源 | 路径 | 数量 | 用途 | 处置 |
|---|---|---|---|---|
| collector 定义 | `apps/api/src/data_intelligence_hub/services/collector_catalog.py:24` | 99 | `collector_type` 的展示名与 `config_schema` | 保留 |
| collector 注册表 | `apps/api/src/data_intelligence_hub/collectors/registry.py:130` | 86 | 可实例化的类 | 保留 |
| 外访策略 | `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py:19-118` | 1 offline / 4 guarded_http / 28 provider_api / 53 unsupported | `execution_kind` | 保留 |
| endpoint 映射 | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:35` | 284 | `endpoint_type → collector_type` | 迁移到 `collectors/endpoint_catalog.py` |
| Apify 默认值 | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:437` | 95 | `endpoint_type → (actor_id, default_input)` | 迁移到 `collectors/endpoint_catalog.py` |
| 价格簿 | 新建 `services/tool_catalog/fixtures/price_book_v1.json` | 按 endpoint | `CostModel` | 新建 |
| 输出 schema | 新建 `services/tool_catalog/fixtures/output_schemas_v1.json` | 按 endpoint 家族 | `output_schema` | 新建 |
| 实测记录 | 新建 `tool_verification_events` 表 | 按 run | `verified_at`、`last_records_count`、`health_status` | 新建 |

计数必须写清楚。PRD 5.1 的计数口径如下：

- collector type：86 注册，99 声明。
- 可执行 collector type：33。计算方式是 1 offline + 4 guarded_http + 28 provider_api。
- endpoint_type 映射：284。
- Apify endpoint type：95。

清点记录显示生产 catalog 返回 309 个能力视图、281 个唯一端点、70 个平台（`catalog_digest=dad20448…`）。仓库生成物是 286 个视图、258 个唯一端点。两套数字口径不同，不得混用。P0 必须先对账。本设计以 284 条映射为构建输入，不以任一展示数字为准。

### 4.2 ToolContract

```python
# apps/api/src/data_intelligence_hub/services/tool_catalog/contracts.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

ToolCategory = Literal[
    "consumer_insight",
    "competitor_price",
    "selection_demand",
    "creator_content",
    "compliance_recall",
    "channel_retail",
    "content_source",
]
ContentType = Literal["review", "product", "creator", "ad", "recall", "trend", "web_page"]
RiskLevel = Literal["low", "medium", "high"]
ExecutionKind = Literal["offline", "guarded_http", "provider_api", "unsupported"]
HealthStatus = Literal["healthy", "stable", "degraded", "outage", "unknown"]
EvidenceGrade = Literal[
    "L0_unverified",
    "L1_contract",
    "L2_fixture_local",
    "L3_live_single",
    "L4_authorized_live",
]
ToolSupportStatus = Literal["candidate", "verified", "stale", "blocked", "unsupported"]


class CostModel(BaseModel):
    currency: Literal["USD"] = "USD"
    unit: Literal["call", "record", "1k_records"]
    unit_price: Decimal = Field(ge=0, decimal_places=6)
    min_charge: Decimal = Field(default=Decimal("0"), ge=0)
    free_tier: int = Field(default=0, ge=0)
    quantity_basis: Literal["records_returned", "records_requested", "calls"]
    estimate_formula: str
    source_url: str
    updated_at: date


class ToolContract(BaseModel):
    tool_id: str
    provider: str
    endpoint_type: str
    collector_type: str
    actor_id: str | None
    display_name: str
    category: ToolCategory
    markets: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    content_types: tuple[ContentType, ...]
    cost_model: CostModel
    risk_level: RiskLevel
    max_evidence_grade: EvidenceGrade
    contract_version: str
    verified_at: datetime | None
    last_records_count: int = 0
    health_status: HealthStatus = "unknown"
    p50_latency_ms: int | None = None
    execution_kind: ExecutionKind
    support_status: ToolSupportStatus
```

字段规则：

1. `tool_id = "{provider}.{endpoint_type}.{market_scope}"`。`market_scope` 在单市场时用 ISO 码小写，多市场时用 `multi`。生成后不得手改。
2. `actor_id` 在 `collector_type="apify_actor"` 时必填。它必须存在于 `_APIFY_ENDPOINT_DEFAULTS`，见 `api/routes/quick_collect.py:437`。
3. `input_schema` 必须由 `CollectorDefinition.config_schema` 与 Apify 默认入参合成。合成结果为 JSON Schema draft 2020-12。
4. `output_schema` 不能从现有代码完全推导。必须由人工维护的 `output_schemas_v1.json` 提供。没有输出 schema 的条目不得上线。
5. `max_evidence_grade` 是该工具的上限，不是本次等级。规则：offline→`L2_fixture_local`，guarded_http/provider_api→`L4_authorized_live`，unsupported→`L0_unverified`。
6. `support_status` 由实测记录计算。超过 30 天未核验为 `stale`。从未成功调用为 `candidate`。
7. `last_records_count=0` 且最近 run 状态为 success 时，`support_status` 必须为 `candidate`，并进入月度复核队列。

### 4.3 派生算法

```python
# apps/api/src/data_intelligence_hub/services/tool_catalog/derive.py
from collections.abc import Mapping, Sequence

from data_intelligence_hub.collectors.base import BaseCollector
from data_intelligence_hub.services.collector_catalog import CollectorDefinition
from data_intelligence_hub.services.tool_catalog.contracts import ToolContract


def build_tool_contracts(
    *,
    endpoint_catalog: EndpointCatalog,
    collector_definitions: Sequence[CollectorDefinition],
    registry: Mapping[str, type[BaseCollector]],
    price_book: PriceBook,
    output_schemas: OutputSchemaBook,
    verification: VerificationLedger,
) -> list[ToolContract]:
    """派生全部 ToolContract。纯函数。禁止网络与数据库访问。"""
    ...


def make_tool_id(provider: str, endpoint_type: str, markets: Sequence[str]) -> str:
    market_scope = markets[0].lower() if len(markets) == 1 else "multi"
    return f"{provider}.{endpoint_type}.{market_scope}"
```

算法步骤：

1. 遍历 `endpoint_catalog.endpoint_to_collector`。
2. 取 `collector_type` 的 `CollectorDefinition`。缺失时抛 `CollectorDefinitionMissing`。
3. 取 `execution_kind(collector_type)`，见 `collectors/outbound_policy.py:138`。
4. 取 Apify 默认值。`apify_actor` 类型缺 `actor_id` 时抛 `ActorIdMissing`。
5. 取价格簿。缺失时抛 `PriceBookMissing`。
6. 取输出 schema。缺失时抛 `OutputSchemaMissing`。
7. 取实测记录。计算 `support_status` 与 `health_status`。
8. 生成 `ToolContract`。按 `endpoint_type` 排序。
9. 对 53 个 unsupported 类型，生成 `execution_kind="unsupported"` 的条目。它们保留在表中，供 `inspect` 解释。`discover` 默认过滤。

### 4.4 适配器

```python
# apps/api/src/data_intelligence_hub/services/tool_catalog/adapters.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from data_intelligence_hub.collectors.base import CollectorRawRecord
from data_intelligence_hub.services.tool_catalog.contracts import ToolContract


class ToolExecutionRequest(BaseModel):
    tool_id: str
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    params: dict[str, Any]
    idempotency_key: str | None = None
    authorization_id: uuid.UUID | None = None
    timeout_seconds: float = 60.0


class ToolExecutionResult(BaseModel):
    outcome: Literal["success", "empty", "config_gated", "failed"]
    records: list[CollectorRawRecord]
    requests_sent: int
    provider_run_id: str | None
    started_at: datetime
    finished_at: datetime
    error_code: str | None = None
    error_message: str | None = None


class ToolAdapter(Protocol):
    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...


class CollectorToolAdapter:
    """把现有 collector 包成 ToolAdapter。唯一允许调用 build_collector 的位置。"""

    def __init__(self, contract: ToolContract, session_factory: Any) -> None:
        self._contract = contract
        self._session_factory = session_factory

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        ...
```

放置规则：

1. 适配器放 `services/tool_catalog/adapters.py`。不要放 `collectors/`。
2. 原因：适配器需要 `workspace_id`、`project_id`、授权、预算和数据库会话。`collectors/` 必须保持租户无关。
3. `collectors/registry.py:220` 的 `build_collector` 只允许被 `CollectorToolAdapter` 调用。CI 必须检查调用点。
4. `collectors/outbound_policy.py:201` 的 `assert_collector_allowed` 在适配器内调用一次。`collection_scope` 再调用一次，见 `collectors/guarded_http.py:99`。两次检查是幂等的，保留。

### 4.5 注册与防双清单

```python
# apps/api/src/data_intelligence_hub/services/tool_catalog/registry.py
class ToolAdapterRegistry:
    def __init__(self, adapters: dict[str, ToolAdapter]) -> None:
        self._adapters = adapters

    def resolve(self, tool_id: str) -> ToolAdapter:
        adapter = self._adapters.get(tool_id)
        if adapter is None:
            raise ToolNotExecutableError(tool_id)
        return adapter
```

注册规则：

1. 应用启动时构造一次。输入是 `tool_catalog` 中 `execution_kind != "unsupported"` 的行。
2. `tool_id` 不在注册表中时抛 `ToolNotExecutableError`。不返回空适配器。
3. `quick_collect`、`run_executor`、MCP `collect` 都只调用 `resolve(tool_id)`。不得直接调用 `build_collector`。
4. 不得在路由、MCP、前端各维护一份可用工具清单。

避免双份清单的硬规则：

1. 只有 seed 生成器可以导入 `_ENDPOINT_TO_COLLECTOR` 与 `_APIFY_ENDPOINT_DEFAULTS`。两者迁到 `collectors/endpoint_catalog.py` 后，`quick_collect.py` 只保留一个发布周期的 re-export。
2. 运行时只读 `tool_catalog`。`api/routes/collectors.py:4713-4745` 的 303 条硬编码元数据必须删除。
3. `/api/collectors/catalog`、`/api/tools`、MCP `list_capabilities`、控制台 `/platforms`、控制台 `/capabilities` 五处必须返回同一组 `tool_id`。
4. 新增 `tests/unit/test_tool_catalog_reconciliation.py`：
   ```python
   def test_catalog_sets_match():
       assert set(tool_catalog.endpoint_types) == set(endpoint_catalog.endpoint_to_collector)
       assert set(tool_catalog.tool_ids) == set(api_catalog.tool_ids)
       assert set(tool_catalog.tool_ids) == set(mcp_catalog.tool_ids)
   ```
5. 对账失败时 CI 阻断发布。规则来自 PRD 11.5.3。

### 4.6 验收

1. `tool_catalog` 有 284 行。每行都有 `input_schema`、`output_schema`、`cost_model`、`risk_level`、`max_evidence_grade`、`verified_at`、`contract_version`。
2. 33 个可执行 collector type 全部有对应条目。53 个 unsupported 全部标 `unsupported`。
3. Apify 条目全部有 `actor_id`，且在 `_APIFY_ENDPOINT_DEFAULTS` 中存在。
4. 幽灵端点差集为 0。回归测试为绿。
5. `inspect` 返回完整合同。`discover` 不返回 unsupported。

---

## 5. 编排层设计

### 5.1 planner 与 executor 的边界

| 关注点 | Planner（BC-05） | Executor（BC-02） |
|---|---|---|
| 输入 | 七槽位任务单 + catalog snapshot | 已批准 PlanContract + Authorization |
| 输出 | PlanContract：步骤、tool_id、target_grade、成本估算、排除理由 | Run、RunStep、RunLedgerEntry、TaskRun、RawRecord |
| 写库 | 只写 plan 与 version | 写 run、step、ledger、task_run、raw_record |
| 外部调用 | 禁止 | 允许。必须经 adapter 与 policy |
| 成本 | 只估算 | 预留、结算、释放 |
| 证据等级 | 只给 `target_grade` | 计算 `actual_grade` |
| 失败处理 | 返回 held 与原因 | 按 step 记录 outcome，不重规划 |

硬规则：

1. Planner 不得调用任何 Provider。它只读 `tool_catalog`。
2. Executor 不得静默替换工具。PRD 第 9 节禁止跨供应商 fallback。步骤失败就标记失败。
3. PlanContract 必须钉住 `catalog_snapshot_id` 与每个工具的 `contract_version`。执行时版本不一致必须抛 `contract_version_drift`。
4. Planner 的排除项必须保留在计划中。不得静默丢弃。

### 5.2 候选来源从 fixture 切到 tool_catalog

现状：

- `services/workflow_planner/candidate_expansion.py:17-19` 指向 `fixtures/candidate_expansions_v1.json`。
- fixture 只有 `acme` 与 `running shoes` 两个词条。
- `services/fixtures/capability_catalog_overseas_v2.json` 的 35 条 assertion 全部是 `candidate`。
- `capability_resolver.py:293-298` 对 `candidate` 一律拒绝。实测 preview 全部 held。

目标：

1. 新增 `ToolCatalogCandidateExpansionAdapter`。它实现现有 `CandidateExpansionAdapter` 协议。
2. 候选来源是 `tool_catalog` 的 `display_name`、`category`、`content_types`、`markets`。
3. 先规则匹配。可选 LLM 分类器必须由 `settings.llm_provider` 控制，默认关闭。
4. 输出 `origin="tool_catalog"`。fixture adapter 只在测试中使用。
5. 保留 `FixtureCandidateExpansionAdapter` 一个发布周期，用于回归对比。

`capability_resolver` 不重写。新增投影器：

```python
# apps/api/src/data_intelligence_hub/services/workflow_planner/tool_catalog_projection.py
class ToolCatalogAssertionProjector:
    """把 ToolContract 投影为 CapabilityImplementation + CapabilityAssertion。"""

    def project(self, contracts: list[ToolContract]) -> CapabilityCatalog:
        ...
```

投影规则：

| ToolContract 状态 | CapabilityStatus | 结果 |
|---|---|---|
| `execution_kind=unsupported` | `unsupported` | resolver 拒绝 |
| `health_status=outage` | `blocked` | resolver 拒绝 |
| `support_status=verified` 且 `verified_at` 在 30 天内 | `verified` | 可进路由 |
| `support_status=stale` | `candidate` | 不可进路由。计划标 held。 |
| `support_status=candidate` | `candidate` | 不可进路由 |
| 最近成功 run 的 `records_count=0` | `candidate` | 可疑。进入月度复核 |
| `support_status=blocked` | `blocked` | 拒绝 |

### 5.3 运行模型

七槽位存 `workbench_tasks`，不在 `runs`。

新增四张表：`runs`、`run_steps`、`run_ledger_entries`、`run_evidence_grades`。复用 `task_runs` 作为单次工具调用的记录。

#### `runs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `workspace_id` | uuid | 租户 |
| `project_id` | uuid | 项目 |
| `plan_id` | uuid | 关联 workflow plan |
| `plan_version` | int | 计划版本 |
| `catalog_snapshot_id` | string | 目录快照 |
| `authorization_id` | uuid | 批准记录 |
| `status` | string | `queued/running/completed/failed/cancelled` |
| `outcome` | string? | 运行结果：`success/empty/config_gated/failed` |
| `target_grade` | string | 计划目标等级 |
| `evidence_grade` | string? | 实际等级。工具上限见 `max_evidence_grade` |
| `estimated_cost_usd` | numeric(12,6) | 估算 |
| `total_cost_usd` | numeric(12,6) | 结算 |
| `started_at` / `finished_at` | datetime? | 时间 |

`runs` 是一次执行运行，不是任务单。它不存七槽位。七槽位存 `workbench_tasks`。

#### `run_steps`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `run_id` | uuid | 外键 |
| `step_index` | int | 顺序 |
| `requirement_ref` | string | 计划需求引用 |
| `tool_id` | string | 合同 ID |
| `endpoint_type` | string | 端点 |
| `collector_type` | string | 采集器 |
| `task_run_id` | uuid? | 单次调用记录 |
| `status` | string | `pending/running/success/empty/config_gated/failed/skipped` |
| `outcome` | string? | `success/empty/config_gated/failed` |
| `quantity` | numeric | 数量 |
| `unit` | string | 计费单位 |
| `unit_price` | numeric(12,6) | 单价 |
| `total_cost_usd` | numeric(12,6) | 总价 |
| `provider_run_id` | string? | 上游运行 ID |
| `evidence_grade` | string? | 该步骤等级 |
| `error_code` | string? | 错误码 |

约束：`unique(run_id, step_index)`、`unique(run_id, tool_id, step_index)`。

#### `run_ledger_entries`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `run_id` | uuid | 外键 |
| `step_id` | uuid? | 步骤 |
| `entry_kind` | string | `estimate/reserve/accrued/settle/release/block` |
| `amount_usd` | numeric(12,6) | 金额 |
| `balance_after_usd` | numeric(12,6) | 余额 |
| `idempotency_key` | string | 唯一 |
| `created_at` | datetime | 时间 |

#### `run_evidence_grades`

| 字段 | 类型 | 说明 |
|---|---|---|
| `run_id` | uuid | 主键，外键 `runs.id` |
| `grade` | string | 本次运行结果：`L0_unverified/L1_contract/L2_fixture_local/L3_live_single/L4_authorized_live` |
| `sample_n` | int | 过 G6 后的合格记录数 |
| `source_count` | int | 有效数据源数 |
| `computed_at` | datetime | 计算时间 |

`run_evidence_grades.grade` 是本次运行结果的唯一写入点。`runs.evidence_grade` 与 `task_runs.evidence_grade` 是它的镜像。

#### `task_runs` 扩展字段

必须新增：`project_id`、`run_id`、`step_index`、`unit`、`quantity`、`unit_price`、`total_cost_usd`、`remaining_budget`、`provider`、`provider_run_id`、`endpoint_type`、`evidence_grade`、`schema_version`。

现有 `TaskRun` 见 `models/task.py:44-66`。它没有 `project_id`、`updated_at`，只统计 `records_count` 与 `entities_count`。字段不足，必须扩展。

#### 状态机

```text
run:
  queued ──► running ──► completed
                    ├──► failed
                    └──► cancelled

step:
  pending ──► running ──► success
                     ├──► empty
                     ├──► config_gated
                     ├──► failed
                     └──► skipped
```

规则：

1. `run.status=completed` 要求所有 step 为 `success`、`empty`、`config_gated` 或 `skipped`。存在 `config_gated` 时报告写 gap。健康度与运行状态分离，健康度只写 `health_status`。
2. `run.status=failed` 要求至少一个 step 为 `failed`，且没有可交付结果。
3. 状态迁移只允许表中列出的方向。非法迁移抛 `InvalidRunTransition`。
4. 状态机放 `services/run/state_machine.py`。它可以参考 `services/workflow_execution/state_machine.py:20-44` 的表结构，但不得依赖 fixture 执行代码。

#### 执行原语

从 `collector_service.py:73` 拆出：

```python
async def execute_collector_call(
    *,
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
    source: Source,
    collector_type: str,
    config: dict[str, Any],
    task_run: TaskRun,
    trigger: str,
    timeout_seconds: float,
) -> CollectionCallResult:
    """执行一次 collector 调用。唯一事务所有者。"""
```

`execute_collection_task` 保留为调度器与手动任务的包装。`RunExecutor` 直接调用 `execute_collector_call`。三条路径共用同一实现。见 ADR-09。

### 5.4 evidence_grade 在哪一层计算

计算位置：L3 纯函数。调用位置：L4 `RunService.finish_run`。持久化位置：L1 `run_evidence_grades` 表；`runs.evidence_grade` 与 `task_runs.evidence_grade` 是镜像。

```python
# apps/api/src/data_intelligence_hub/services/evidence/grade.py
import uuid
from enum import StrEnum


class EvidenceGrade(StrEnum):
    L0_UNVERIFIED = "L0_unverified"
    L1_CONTRACT = "L1_contract"
    L2_FIXTURE_LOCAL = "L2_fixture_local"
    L3_LIVE_SINGLE = "L3_live_single"
    L4_AUTHORIZED_LIVE = "L4_authorized_live"


GRADE_ORDER = {
    EvidenceGrade.L0_UNVERIFIED: 0,
    EvidenceGrade.L1_CONTRACT: 1,
    EvidenceGrade.L2_FIXTURE_LOCAL: 2,
    EvidenceGrade.L3_LIVE_SINGLE: 3,
    EvidenceGrade.L4_AUTHORIZED_LIVE: 4,
}


def compute_run_evidence_grade(
    *,
    live_call: bool,
    authorization_id: uuid.UUID | None,
    sample_n: int,
    required_n: int,
    window_days: int,
    required_window_days: int,
    source_count: int,
    required_source_count: int,
    contract_ceiling: EvidenceGrade,
) -> EvidenceGrade:
    if not live_call:
        return EvidenceGrade.L2_FIXTURE_LOCAL
    if authorization_id is None:
        return EvidenceGrade.L3_LIVE_SINGLE
    if sample_n < required_n:
        return EvidenceGrade.L3_LIVE_SINGLE
    if window_days < required_window_days:
        return EvidenceGrade.L3_LIVE_SINGLE
    if source_count < required_source_count:
        return EvidenceGrade.L3_LIVE_SINGLE
    computed = EvidenceGrade.L4_AUTHORIZED_LIVE
    return min(computed, contract_ceiling, key=lambda grade: GRADE_ORDER[grade])
```

规则：

1. 输入只来自数据库与模板阈值。不得来自模型输出。
2. `contract_ceiling` 来自 `ToolContract.max_evidence_grade`。
3. `sample_n` 是过 G6 后的合格记录数。口径见 Playbook 1.6。
4. `source_count` 是有效数据源数。不同 `tool_id` 分别计数。不得跨来源相加样本。
5. 等级写入 `run_evidence_grades.grade`，并镜像到 `runs.evidence_grade` 与 `task_runs.evidence_grade`。工具上限见 `max_evidence_grade`。
6. claim 的等级取该 claim 所有 support/counter 证据所属 run 的最低等级。
7. 阈值表是唯一事实源。模板注册表引用它，Playbook 引用它。PRD 5.4.2 给出 T1–T5 的阈值。

### 5.5 失败、重试与幂等

| 失败类型 | 重试 | 幂等 | 结果 |
|---|---|---|---|
| 网络超时 | 不重试同一 step | `Idempotency-Key` | `failed` |
| 429 | 重试 3 次，指数退避 | 是 | 成功或 `failed` |
| 500/502/503 | 重试 3 次 | 是 | 成功或 `failed` |
| 400/401/403 | 不重试 | 是 | `config_gated` 或 `failed` |
| `CollectionPolicyDenied` | 不重试 | 是 | `config_gated` |
| 空结果 | 不默认重试 | 是 | `empty` |
| 计划未批准 | 不执行 | — | 409 |
| 预算不足 | 不执行 | — | 409 |

幂等要求：

1. `run_steps` 的唯一约束 `(run_id, step_index)` 防止重复步骤。
2. `run_ledger_entries.idempotency_key` 唯一。预留、结算、释放各用独立 key。
3. `task_runs` 必须增加 `idempotency_key_hash` 唯一索引。当前 `task_service.py:86-121` 只把 key 写进 `logs`，并发同 key 会建两次 run。
4. `raw_records` 已有 `(source_id, content_hash)` 唯一约束，见 `alembic/versions/202606110004_raw_records.py:37`。保留。
5. Provider 返回 `provider_run_id` 时必须落库。重试前先按 `provider_run_id` 查询上游结果。

---

## 6. 证据层设计

### 6.1 claim / claim_evidence 与 intelligence_items 的关系

现状：

- `intelligence_items` 有 `title`、`summary`、四个分数、`status`、`domain`。没有 `claim_status`、`evidence_grade`、`scope`、`counterevidence_text`、`owner`。见 `models/intelligence.py:21-47`。
- `evidences` 的 `intelligence_id` 是必填外键。见 `models/intelligence.py:50-70`。
- 证据来自信号与快照。`services/evidence_service.py:13` 只构造 signal、snapshot、raw_record 三类证据。
- `intelligence_items` 由 `services/intelligence_service.py:128` 从信号生成。它不是跨样本结论。

决策：**保留 `intelligence_items`，新增 `claims` 与 `claim_evidence`。**

理由：

1. 11 个路由模块与 dashboard、alerts 读 `intelligence_items`。删除会破坏生产。模块清单见 `api/routes/` 下 `alerts.py`、`dashboard.py`、`entities.py`、`automation.py`、`projects.py`、`quick_collect.py`、`signals.py`、`intelligence.py`、`sources.py`、`raw_records.py`、`tasks.py`。
2. 信号是“指标变化事件”。claim 是“可写进报告的结论”。两者粒度不同。一个 VOC 主题 claim 可以聚合 800 条评论，不对应单个 signal。
3. `intelligence_items` 没有反证与范围字段。把它扩成 claim 会破坏现有读模型。

读写边界：

| 读方 | 允许读 | 禁止读 |
|---|---|---|
| Dashboard、Alerts、Intelligence 页面 | `intelligence_items` | `claims` |
| ReportContractBuilder | `claims`、`claim_evidence`、`evidences`、`run_ledger` | `intelligence_items` |
| ClaimService | `evidences`、`raw_records`、`entity_snapshots`、`signals` | `intelligence_items` 的分数 |

### 6.2 ER 图

```text
┌────────────┐ 1     * ┌────────────┐
│ workspaces │─────────│ projects   │
└─────┬──────┘         └─────┬──────┘
      │                      │
      │ 1                    ├─────────────── * ┌──────────┐ 1     * ┌──────────────────┐ 1     * ┌───────────┐
      │                      │                 │ sources  │─────────│ collection_tasks │─────────│ task_runs │
      │                      │                 └──────────┘         └──────────────────┘         └─────┬─────┘
      │                      │                                                                          │
      │                      │                                                                          │ 1
      │                      │                                                                          │
      │                      │                                                                          * ┌──────────────┐
      │                      │                                                                            │ raw_records  │
      │                      │                                                                            └──────┬───────┘
      │                      │                                                                                   │ 1
      │                      │                                                                                   │
      │                      │                                                                          * ┌──────────────────┐
      │                      │                                                                            │ entity_snapshots │
      │                      │                                                                            └────────┬─────────┘
      │                      │                                                                                     │ 1
      │                      │                                                                                     │
      │                      │                                                                            * ┌──────────┐
      │                      │                                                                              │ signals  │
      │                      │                                                                              └────┬─────┘
      │                      │                                                                                   │ 1
      │                      │                                                                                   │
      │                      │                                                                          * ┌────────────────────┐
      │                      │                                                                            │ intelligence_items │
      │                      │                                                                            └─────────┬──────────┘
      │                      │                                                                                      │ 1
      │                      │                                                                                      │
      │                      │                                                                          * ┌───────────┐
      │                      │                                                                            │ evidences │
      │                      │                                                                            └─────┬─────┘
      │                      │                                                                                  │ *
      │                      │                                                                                  │
      │                      │                                                                          * ┌───────────────┐
      │                      │                                                                            │ claim_evidence │
      │                      │                                                                            └───────┬───────┘
      │                      │                                                                                    │ *
      │                      │                                                                          * ┌───────────┐
      │                      │                                                                            │  claims   │
      │                      │                                                                            └───────────┘
      │                      │
      │                      ├─────────────── * ┌──────────┐ 1     * ┌────────────┐ 1     * ┌──────────────────────┐
      │                      │                 │  runs    │─────────│ run_steps  │─────────│ run_ledger_entries   │
      │                      │                 └────┬─────┘         └─────┬──────┘         └──────────────────────┘
      │                      │                      │                     │
      │                      │                      │ 1                   │ 1
      │                      │                      │                     │
      │                      │                      *                     │ 1
      │                      │                 task_runs ◄────────────────┘
      │                      │
      │                      └─────────────── * ┌──────────┐ 1     * ┌──────────────────┐
      │                                        │ reports  │─────────│ report_artifacts │
      │                                        └────┬─────┘         └──────────────────┘
      │                                             │
      │                                             └─────────────── * ┌───────────────┐
      │                                                                 │ report_shares │
      └─────────────────────────────────────────────────────────────────└───────────────┘
```

说明：

1. `evidences.intelligence_id` 改为 nullable。一个 evidence 可以只服务 claim，不服务 intelligence item。
2. `claim_evidence` 是 `claims` 与 `evidences` 的多对多连接表。`role` 取值 `support`、`counter`、`context`、`gap`。
3. `claims` 不带 `intelligence_id`。它按 `project_id` 与 `run_id` 归属。
4. `report_artifacts.contract_json` 是快照。它不通过外键引用 claim。报告发布后 claim 变化不得改变旧报告。

### 6.3 claim 表与状态机

#### `claims`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `workspace_id` | uuid | 租户 |
| `project_id` | uuid | 项目 |
| `task_id` | uuid? | 任务 |
| `run_id` | uuid? | 来源 run |
| `template_id` | string | 模板 |
| `text` | text | 结论句 |
| `claim_status` | string | `confirmed/directional/hypothesis/evidence_gap/blocked` |
| `evidence_grade` | string | 等级 |
| `scope_market` | string | 市场 |
| `scope_window_start` | datetime | 时间窗起 |
| `scope_window_end` | datetime | 时间窗止 |
| `scope_sample_n` | int | 样本量 |
| `counterevidence_text` | text | 必填。可写“未发现反证” |
| `owner_id` | uuid | 责任人 |
| `created_at` / `updated_at` | datetime | 时间 |

#### `claim_evidence`

| 字段 | 类型 | 说明 |
|---|---|---|
| `claim_id` | uuid | 外键 |
| `evidence_id` | uuid | 外键 |
| `role` | string | `support/counter/context/gap` |
| `created_at` | datetime | 时间 |

约束：主键 `(claim_id, evidence_id)`。

#### 状态机

```text
hypothesis ──► directional ──► confirmed
     │              │              │
     │              │              └──► superseded（新 run 覆盖）
     ├──► evidence_gap
     └──► blocked
```

等级上限：

| 证据等级 | 最高 claim 状态 |
|---|---|
| `L0_unverified` | 不得生成 claim |
| `L1_contract` | 不得生成 claim |
| `L2_fixture_local` | `hypothesis` |
| `L3_live_single` | `directional` |
| `L4_authorized_live` | `confirmed` |

强制规则：

1. 每条 claim 必须至少有 1 条 `claim_evidence`。`role=gap` 也算证据，但此时 status 必须为 `hypothesis` 或 `blocked`。
2. 只有 `support` 或 `counter` 证据才能支撑 `confirmed`。
3. `counterevidence_text` 非空。允许写“未发现反证”，但字段必须存在。
4. 状态与词表必须匹配。`directional` 禁止“证明”“必然”。`hypothesis` 禁止“显示”“达到”。检查器放 `services/evidence/claim_policy.py`。
5. G-Claim 涉及医疗、法务、召回时，必须人工签字。签字前状态不得为 `confirmed`。

### 6.4 与 intelligence_items 的迁移

回填步骤：

1. 新建 `claims` 与 `claim_evidence`。
2. 对每条 `intelligence_items` 生成一条 claim。`text = title + "\n" + summary`。`claim_status = hypothesis`。`evidence_grade = L2_fixture_local`。`counterevidence_text = "未发现反证（回填，未复核）"`。
3. 对每条 `evidences` 生成 `claim_evidence`。`role = support`。
4. `evidences.intelligence_id` 改为 nullable。先加新列，双写一个周期，再切读。
5. 报告生成切换到 claims。dashboard 与 alerts 继续读 intelligence_items。
6. 回滚：保留旧表与旧列。删除新表即可回到原状。

### 6.5 验收

1. 报告里任取一条结论，能点到原文 URL 或 `raw_record`。
2. 反证字段非空率 100%。
3. 每条 claim 的证据数 ≥ 1。
4. claim 状态不超过等级上限。
5. 回填后的 claims 数量等于回填时的 intelligence_items 数量。允许后续新增 claim。

---

## 7. 渲染层设计

### 7.1 report_contract 的生成

生成器位置：`services/reporting/contract.py`。它是 L3 纯函数。

```python
class ReportContractBuilder:
    def __init__(
        self,
        templates: ReportTemplateRegistry,
        metrics: MetricCatalog,
    ) -> None: ...

    def build(self, request: ReportBuildRequest) -> ReportContract:
        """从 claim、evidence、run ledger 与模板生成合同。禁止 IO。"""
        ...
```

输入：

1. `identity`：来自任务单与项目。字段见 PRD 5.5.1。
2. `decision`：来自任务单的 `decision_question` 与 `does_not_answer`。
3. `gates`：来自任务状态与审批记录。
4. `coverage`：按 `{source_tool_id, market, window}` 三键聚合。
5. `metrics`：来自 `MetricCatalog.compute(claims)`。每条指标必须有 `count_type`、分子、分母、口径、日期。
6. `claims`：来自 BC-03。
7. `evidences`：来自 `claim_evidence`。
8. `run_ledger`：来自 `run_ledger_entries` 与 `task_runs`。
9. `limits`：来自 `does_not_answer` 与 Playbook 第 12 节。
10. `unknowns`：来自 gap 与 blocked 证据。

规则：

1. 顶层必须有 `schema_version` 与 `template_id`。
2. 任何 headline 数字不得写死在模板里。所有数字必须来自 `metrics[]`。
3. 合同必须能独立存档。它不依赖数据库读取就能复现报告。
4. `artifact` 组最后计算。它不参与 `contract_sha256`。

### 7.2 校验

校验器位置：`services/reporting/validate.py`。它是 L3 纯函数。

```python
class ReportContractValidator:
    def validate(self, contract: ReportContract) -> ValidationReport: ...
```

校验顺序：

1. Pydantic 结构校验。
2. `report_contract.schema.json` 校验。schema 用 draft 2020-12。
3. 语义校验：
   - `decision.answer` 非空。
   - 每条 claim 至少有 1 条 evidence。
   - `counterevidence_text` 非空。
   - claim 状态不超过等级上限。
   - `gates[]` 的 `G-Evidence` 与 `G-Publish` 状态存在。
   - `sections[]` 与模板注册表一致。
   - `limits` 包含模板的 `prohibited_outputs`。
   - 文案不命中禁止输出。检查器见 `services/reporting/prohibited.py`。
4. 哈希校验：`contract_sha256 = sha256(RFC8785(contract 排除 artifact))`。
5. 返回 `ValidationReport`。有错误时不得渲染。

规则：

1. 校验失败返回 `report_contract_invalid`，写审计事件，不写 `report_artifacts`。
2. 校验器必须有单元测试。故意破坏必填字段时必须报错。
3. 校验器不得调用 LLM。

### 7.3 两个渲染器

位置：

- `services/reporting/render_report.py`
- `services/reporting/render_sop.py`
- 共享组件：`services/reporting/components.py`

```python
def render_report_html(contract: ReportContract, template: ReportTemplate) -> str:
    """决策者视图。只读合同与模板。"""
    ...


def render_sop_html(contract: ReportContract, template: ReportTemplate) -> str:
    """执行者视图。只读合同与模板。"""
    ...
```

边界：

1. 两个函数都是纯函数。不得读数据库。不得发网络请求。不得调用 LLM。
2. 两个函数只接收合同与模板。不得接收 ORM 对象。
3. 图表用 CSS 实现。不引入图表库。规则来自 PRD 7.2。
4. 输出必须确定性。字典键排序。日期用 `generated_at`。不使用随机数。
5. 两个渲染器共享章节 ID。章节 ID 由 `ReportTemplateRegistry` 提供。PRD、Playbook、渲染器三处必须一致。
6. 每个 exhibit 必须有四段读图：Interpretation、Counterevidence、Decision。缺 Counterevidence 不得渲染。规则来自 PRD 7.2。
7. 页脚必须写三个哈希：`contract_sha256`、`report_html_sha256`、`sop_html_sha256`。

### 7.4 与 report_service 的边界

`ReportService` 保留四个职责：

1. 订阅 upsert 与执行。见 `services/report_service.py:184`、`:536`。
2. 报告生成编排。见 `:647`。
3. 发送与审计。见 `:729`、`:804`。
4. 列表与读取。见 `:116`、`:124`。

生成流程改为：

```text
ReportService.generate_report
  → ClaimService.list_for_task
  → MetricCatalog.compute
  → ReportContractBuilder.build
  → ReportContractValidator.validate
  → render_report_html
  → render_sop_html
  → ReportArtifactRepository.save
  → Report(status=generated)
```

退役：

- `_render_daily_report` 在 P7 后删除。
- 旧的 `report_type=daily` 只读保留。新报告使用 `template_id`。
- `reports.report_type` 扩枚举。旧值映射为 `daily_digest`。见 PRD 11.5.1。

### 7.5 验收

1. 改合同里的一个数字，两个渲染器的输出都变。
2. 页脚能读到三个哈希。
3. 合同校验有单元测试。
4. 报告与 SOP 的 gate 状态一致。
5. 五个模板各有一份黄金报告。换品牌重跑，段落级 diff 通过。

---

## 8. 复用与替换表

处置列含义：

- 保留：现在可用。有测试或生产证据。
- 扩展：模块可用，范围不足。必须新增能力。
- 包装：保留实现，外面加适配层。
- 替换：重写。旧实现不再使用。
- 删除：死代码或明确不做。

### 8.1 采集与执行

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| `execute_collection_task` | `apps/api/src/data_intelligence_hub/services/collector_service.py:73` | 扩展 | 拆出 `execute_collector_call`。保留任务锁 `:302`、超时 `:130`、去重 `:348`、规范化 `:379`。单元测试待复测。 |
| Collector 协议 | `apps/api/src/data_intelligence_hub/collectors/base.py:60` | 保留 | 39 个采集器文件、67 个子类使用。生产 `/api/collectors` 返回 99 行。 |
| Collector 注册表 | `apps/api/src/data_intelligence_hub/collectors/registry.py:130` | 保留 | 86 个注册项。`build_collector` 在 `:220` 是唯一实例化入口。采集单元测试通过。 |
| 外访策略 | `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py:19-118` | 保留 | 1/4/28/53 分类。`assert_collector_allowed` 在 `:201`。生产 catalog 的 77 个条目显示 `policy_block_reason`。文件未纳入 HEAD 跟踪，P0 必须提交。 |
| 受控 HTTP | `apps/api/src/data_intelligence_hub/collectors/guarded_http.py:39` | 保留 | 请求预算、host grant、重定向检查。`collection_scope` 在 `:99`。超时与采集测试待复测。 |
| Apify 采集器 | `apps/api/src/data_intelligence_hub/collectors/apify_actor.py:321` | 保留 | 95 个 endpoint 默认值。token 读取在 `:51`。Apify 十平台深挖有生产实测记录。 |
| TikHub 采集器 | `apps/api/src/data_intelligence_hub/collectors/tikhub_social.py:373` | 保留 | 内容端点映射。TikTok R1 已部署生产 A。 |
| 28 个 provider_api 采集器 | `apps/api/src/data_intelligence_hub/collectors/*` | 保留 | `outbound_policy.py:28-61` 列出。生产 catalog 有实测记录。 |
| 53 个 unsupported 采集器 | `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py:62-118` | 删除（仅产品范围；代码保留） | 永久拒绝。不得向下一批承诺。目录标 `unsupported`。PRD 第 1215 行确认不在本期范围。 |
| 调度器 | `apps/api/src/data_intelligence_hub/scheduler/service.py:71` | 保留 | 租约与 tick。`:91` tick。`:130` 跳过 quick_collect。生产 scanned=44。 |
| cron 解析 | `apps/api/src/data_intelligence_hub/scheduler/cron.py:31-53` | 扩展 | 只支持分钟/小时/每日。月、日、星期会被静默跳过。必须扩展或显式拒绝。 |
| 重试策略 | `apps/api/src/data_intelligence_hub/services/task_schedule_policy.py:69` | 保留 | 默认 3 次、间隔 15 分钟。`:89` 计算下次时间。`:128` 到期判断。调度与超时测试待复测。 |
| 手动任务 | `apps/api/src/data_intelligence_hub/services/task_service.py:86` | 扩展 | `Idempotency-Key` 只写 `logs`。无唯一约束。必须补唯一索引。`/api/tasks` 已挂载。 |
| 采集源 | `apps/api/src/data_intelligence_hub/services/source_service.py:35` | 保留 | 创建、测试、启用。`:132` 同步创建任务。`/api/sources` 已挂载于 `main.py:99`。 |
| 同步 quick-collect | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:960` | 扩展 | 每次新建 Source 与 Task。无鉴权。P0 补边界。生产覆盖实测待复测（目录计数口径见 §4.1：生产 281 唯一端点 / 仓库生成物 258，不得混用）。 |
| 异步 quick-collect | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:1027` | 替换 | 使用进程内 `BackgroundTasks`。重启丢任务。改为持久队列。 |
| fixture 执行服务 | `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py:1079` | 保留（fixture_only） | 只加载 fixture。服务于已挂载的 `workflow_runs` 路由（`origin/main:143`），生产返回 200，`execution_mode=fixture`。不得删除，不接生产执行。 |
| 禁用执行边界 | `apps/api/src/data_intelligence_hub/services/workflow_execution/executor_composition.py:61` | 保留（fixture_only） | `provider_call=False`。`:196` 直接 `del` 凭据解析器。`:317` 固定 `not_attempted`。服务于已挂载的 fixture 路由，不得用于生产执行。 |
| 状态机 | `apps/api/src/data_intelligence_hub/services/workflow_execution/state_machine.py:20-44` | 包装 | 纯状态迁移表。抽到 `services/run/state_machine.py`。 |
| 预算逻辑 | `apps/api/src/data_intelligence_hub/services/workflow_execution/budget.py:426-563` | 包装 | 哈希链账本可用。账本项仍写 `provider_call_attempted=False`（`:552`）。必须改写。 |
| workflow_runs 路由 | `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py:170` | 保留（fixture_only） | 已在 `main.py:143` 注册（`origin/main:143`）。生产返回 200，`execution_mode=fixture`。不得删除。 |
| workflow 运行模型 | `apps/api/src/data_intelligence_hub/models/workflow_execution.py:35` | 保留（fixture_only） | 服务已挂载的 fixture 路由。schema 固定 fixture，见 `schemas/workflow_execution.py:56-57`。不得删除。 |

### 8.2 目录与契约

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| collector 定义目录 | `apps/api/src/data_intelligence_hub/services/collector_catalog.py:24` | 保留 | 99 个定义。`validate_collector_config` 在 `:827`。`ensure_collectors_seeded` 写 `collectors` 表。`tests/unit/test_collector_seeding.py` 通过。 |
| 端点元数据 | `apps/api/src/data_intelligence_hub/api/routes/collectors.py:4713-4745` | 替换 | 303 条硬编码。与 284 映射、95 Apify 默认不一致。 |
| endpoint 映射 | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:35` | 扩展 | 284 项。迁到 `collectors/endpoint_catalog.py`。catalog 与 quick-collect 测试待复测。 |
| Apify 默认值 | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:437` | 扩展 | 95 项。迁到同一文件。 |
| capability 目录 | `apps/api/src/data_intelligence_hub/services/capability_catalog.py:23` | 包装（冻结） | 7 个 implementation、35 条 assertion，全部 `candidate`。冻结只读。生产 `/api/capabilities/matrix` 返回 200。 |
| 能力矩阵 | `apps/api/src/data_intelligence_hub/services/capability_matrix.py:46` | 扩展 | 改为读 `tool_catalog`。capability 测试待复测。 |
| 能力治理 | `apps/api/src/data_intelligence_hub/services/capability_governance/` | 扩展 | 保留 intake 与 verification，作为 `verified_at` 来源。catalog 发布冻结。 |
| 平台包目录 | `apps/api/src/data_intelligence_hub/platform_packages/service.py:52` | 保留 | 仓库生成物读模型为 286 能力视图、258 唯一端点；生产为 309 视图、281 唯一端点、70 平台（`catalog_digest=dad20448…`）。MCP `list_platforms` 与 `list_capabilities` 调用。 |
| 平台门禁 | `apps/api/src/data_intelligence_hub/services/social_provider.py:140` | 保留 | 只做 catalog、readiness、gate。`:348` readiness。`:395` gate。测试待复测。生产 `/api/automation/social-provider-catalog` 返回 200。 |
| 能力发现 | `apps/api/src/data_intelligence_hub/services/capability_discovery/preview.py:274` | 删除 | router 未挂载。生产 404。 |
| 计划器 | `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py:477` | 保留 | planner 与执行单元测试待复测。preview 路由已挂载于 `main.py:97`。生产用真实 project id 返回 200。 |
| 计划路由 | `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:501` | 保留 | preview、保存、clone、版本、比较均已挂载。`:606` 保存 plan。`:742` 创建版本。 |
| 版本快照校验 | `apps/api/src/data_intelligence_hub/services/workflow_execution/integrity.py:203` | 保留 | 被 `workflow_planner/persistence.py:89` 与 `scope_templates.py:41` 调用。planner 在线时可用。 |
| 工具合同 | 新建 `apps/api/src/data_intelligence_hub/services/tool_catalog/` | 新建 | 本设计的核心新模块。 |
| 价格簿 | 新建 `services/tool_catalog/fixtures/price_book_v1.json` | 新建 | 每个工具必须有 rate card。 |
| 输出 schema | 新建 `services/tool_catalog/fixtures/output_schemas_v1.json` | 新建 | 现有代码没有输出 schema。 |

### 8.3 证据与分析

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| 规范化 | `apps/api/src/data_intelligence_hub/services/normalization_service.py:32` | 扩展 | 只分派 7 类。`:73-87`。Apify 的 `amazon_product`、`tiktok_video` 不生成实体。scheduler/normalization/signals 测试待复测。 |
| 信号检测 | `apps/api/src/data_intelligence_hub/services/signal_service.py:118` | 扩展 | 只有 stars 增长 `:259-260` 与网页哈希变化 `:291-292`。另加质量异常 `:153`。规则必须改为注册表。测试待复测。 |
| 情报生成 | `apps/api/src/data_intelligence_hub/services/intelligence_service.py:128` | 保留 | 监控投影。报告不得读。生产 `/api/intelligence` 返回真实情报。 |
| 证据构建 | `apps/api/src/data_intelligence_hub/services/evidence_service.py:13` | 扩展 | 新增 claim 证据构建。旧函数保留。被 `intelligence_service.py:32` 调用。 |
| LLM 服务 | `apps/api/src/data_intelligence_hub/services/llm_service.py:12` | 替换 | 固定 `MockLLMAdapter`。`core/config.py:31-33` 的 provider、key、model 没有读取点。 |
| TikTok 摄取 | `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py:659` | 保留 | 仓储与摄取测试待复测。文件未跟踪，P0 必须提交。 |
| TikTok 仓储 | `apps/api/src/data_intelligence_hub/repositories/tiktok_content.py:190` | 保留 | creator/video/comment/hashtag/sound/transcript upsert。测试待复测。未跟踪。 |
| TikTok 模型 | `apps/api/src/data_intelligence_hub/models/tiktok_content.py:64-393` | 保留 | 12 个 ORM 类。迁移创建 21 张表，9 张没有 ORM。清点记录称生产 schema 为 `202610190045`，README 写 `202607280044`。P0 必须核对。 |
| TikTok 工具 | `apps/api/src/data_intelligence_hub/services/tiktok_tools.py:29` | 保留 | 8 个工具。`:468` handlers。`:480` 运行入口。测试待复测。生产 `/api/tiktok/tools` 返回 200。 |
| CDO Agent | `apps/api/src/data_intelligence_hub/agents/tiktok_cdo/router.py:33` | 扩展 | 六步管道。`:96-159`。HTTP 回环在 `data_sources.py:223`、`:274`，超时 30 秒。 |
| 自动化长流程 | `apps/api/src/data_intelligence_hub/services/automation_service.py` | 保留（冻结） | 13537 行、335 个函数。新功能不得进入。 |
| claims | 新建 | 新建 | 报告结论层。 |
| 证据等级 | 新建 `services/evidence/grade.py` | 新建 | 确定性计算。 |

### 8.4 报告与通知

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| 报告订阅 | `apps/api/src/data_intelligence_hub/services/report_service.py:184` | 保留 | upsert。`:536` 执行。调度器在 `scheduler/service.py:186` 调用。内存 SQLite 实测返回 success 与 in_app。 |
| 报告发送 | `apps/api/src/data_intelligence_hub/services/report_service.py:729` | 保留 | 授权、确认、幂等。`:804` dispatch。实测同 key 重放返回 `idempotency_replayed=true`。 |
| 报告生成编排 | `apps/api/src/data_intelligence_hub/services/report_service.py:647` | 扩展 | 改为调用合同生成器。当前实测 POST 返回 201 与 generated。 |
| 日报渲染 | `apps/api/src/data_intelligence_hub/services/report_service.py:1198` | 替换 | 只输出监控概览、核心发现、预警区三段。PRD 第 752 行指出该限制。 |
| 报告模型 | `apps/api/src/data_intelligence_hub/models/report.py:16-88` | 扩展 | 新增 `report_artifacts` 与 `report_shares`。 |
| 报告路由 | `apps/api/src/data_intelligence_hub/api/routes/reports.py:54-299` | 保留 | 13 个端点。生产 `/api/reports` 返回 status=200 的真实报告。 |
| 通知服务 | `apps/api/src/data_intelligence_hub/services/notification_service.py:160` | 保留 | 站内信。`:603` 邮件发送。`core/config.py:41` 默认关闭真实邮件。站内发送实测成功。 |
| 报告面板 | `apps/web/src/components/reports/report-detail-panel.tsx:58` | 包装 | 825 行。迁移到控制台时必须抽掉 API 调用与旧 token。 |
| 报告详情壳 | `apps/web/src/components/reports/report-detail-page-workspace.tsx:10` | 替换 | 76 行薄壳。重写成本低于迁移。 |
| 报告中心 | `apps/web/src/components/reports/reports-workspace.tsx:61` | 替换 | 1382 行页面级工作区。按控制台页面拆分。 |
| 合同生成器 | 新建 `services/reporting/contract.py` | 新建 | 唯一渲染输入。 |
| 合同校验 | 新建 `services/reporting/validate.py` | 新建 | schema 与语义校验。 |
| 两个渲染器 | 新建 `services/reporting/render_report.py`、`render_sop.py` | 新建 | 纯函数。CSS 图表。 |

### 8.5 身份与接入

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| 注册登录 | `apps/api/src/data_intelligence_hub/services/auth_service.py:38` | 保留 | 注册 `:38`、登录 `:81`、会话 `:97`。`/api/auth` 已挂载于 `main.py:92`。 |
| JWT 与哈希 | `apps/api/src/data_intelligence_hub/core/security.py:23-43` | 保留 | 被 `api/deps.py:10` 与 `auth_service.py:10` 调用。 |
| AuthContext | `apps/api/src/data_intelligence_hub/api/deps.py:54-79` | 扩展 | 无有效 cookie 时回退 demo workspace。必须 fail-closed。 |
| demo workspace | `apps/api/src/data_intelligence_hub/repositories/workspaces.py:10` | 替换行为 | `get_demo_workspace` 在 `:35`。11 个路由模块直接调用。只允许显式 demo 模式。 |
| 平台凭据 | `apps/api/src/data_intelligence_hub/services/platform_credentials.py:172` | 扩展 | 只按 workspace 存 Fernet 密文。表无 project_id。PRD 第 1222 行要求项目隔离。凭据测试待复测。 |
| MCP 鉴权 | `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py:20-23` | 扩展 | token 为空时直接放行。生产必须配置 token。 |
| MCP 限额 | `apps/api/src/data_intelligence_hub/mcp_runtime/governance.py:54-86` | 扩展 | 进程内计数。重启清零。多 worker 不共享。 |
| MCP 工具 | `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:55-309` | 扩展 | 13 个工具。`:35-52` allowed_hosts 缺第二套生产域名。 |
| MCP collect 桥 | `apps/api/src/data_intelligence_hub/mcp_runtime/collect_service.py:5` | 替换 | 直接导入 API 路由。改为应用服务。 |
| 项目 API key | 新建 `project_api_keys` | 新建 | 每项目一把 key。PRD 5.7。 |
| 授权表 | 新建 `authorizations` | 新建 | 计划批准、成本上限、过期。 |

### 8.6 前端

| 模块 | 路径:行 | 处置 | 理由与证据 |
|---|---|---|---|
| AppShell | `apps/scraper-console/src/components/layout/app-shell.tsx:16` | 保留 | 13 个页面引用。除根重定向外，15 个路由渲染它。生产 live。 |
| Sidebar | `apps/scraper-console/src/components/layout/sidebar.tsx:7-20` | 扩展 | 一级导航收敛为工作台、报告、连接器、设置四项。`/dashboard`、`/raw-records`、`/settings/account` 不作为一级入口。 |
| TopBar | `apps/scraper-console/src/components/layout/top-bar.tsx:7-9` | 保留 | AppShell 唯一引用。生产 15 个路由渲染壳。 |
| StatTile | `apps/scraper-console/src/components/ui/stat-tile.tsx:19` | 保留 | 3 个页面引用：dashboard、datasets、tools/tiktok。 |
| PlatformLogo | `apps/scraper-console/src/components/platforms/platform-logo.tsx:7` | 保留 | 3 个文件引用：platforms 页、datasets 页、data-preview-drawer。 |
| ConfirmDialog | `apps/scraper-console/src/components/ui/confirm-dialog.tsx:13` | 保留 | 使用焦点陷阱。datasets 页引用。生产 `/datasets` live。 |
| useFocusTrap | `apps/scraper-console/src/components/ui/use-focus-trap.ts:21` | 保留 | 2 个覆盖层引用：confirm-dialog 与 data-preview-drawer。 |
| 快速采集抽屉 | `apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx:24` | 扩展 | 162 个硬编码端点。生产有 281 个唯一端点。必须改为 catalog 驱动。 |
| 数据集预览 | `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx:136` | 保留 | 使用焦点陷阱。生产 `/datasets` live。 |
| Skill 目录 | `apps/scraper-console/src/components/skills/skills-directory.tsx:78` | 保留 | 生产 `/skills` live。 |
| Skill 详情 | `apps/scraper-console/src/components/skills/skill-detail.tsx:15` | 保留 | 生产 `/skills` 详情 live。 |
| 查询 Provider | `apps/scraper-console/src/components/providers.tsx:9-15` | 保留 | 根布局 `layout.tsx:18` 挂载。TanStack Query。 |
| API 客户端 | `apps/scraper-console/src/lib/api/client.ts:13-34` | 扩展 | 无超时、无重试、无响应校验。 |
| 领域 API 模块 | `apps/scraper-console/src/lib/api/` | 保留 | 11 个模块对应真实路由。`main.py:92-115` 可核对前缀。 |
| 页面 `/platforms` | `apps/scraper-console/src/app/platforms/page.tsx` | 保留 | 生产 live。 |
| 页面 `/tasks`、`/runs`、`/datasets`、`/collector-docs` | `apps/scraper-console/src/app/` | 保留 | 生产 live。 |
| 页面 `/settings/credentials` | `apps/scraper-console/src/app/settings/credentials/page.tsx` | 保留 | 生产 live。需要 master key。 |
| 页面 `/projects/[id]` | `apps/scraper-console/src/app/projects/[id]/page.tsx:144` | 扩展 | 运行记录与数据集是静态占位。 |
| 页面 `/settings/account` | `apps/scraper-console/src/app/settings/account/page.tsx:10` | 删除 | 14 行死页。无 API。 |
| 页面 `/dashboard`、`/raw-records` | `apps/scraper-console/src/app/dashboard/page.tsx`、`raw-records/page.tsx` | 保留 | 页面可用。作为二级页面访问，不补一级导航。 |
| 新 `/workbench`、`/capabilities`、`/reports` | 新建 | 新建 | PRD 第 6 节。 |
| 鉴权中间件 | 新建 `apps/scraper-console/src/middleware.ts` | 新建 | 当前无 middleware、无登录页。 |
| 错误与加载边界 | 新建 `error.tsx`、`loading.tsx` | 新建 | 当前每页内联处理。 |
| 运行时校验 | `apps/scraper-console/package.json` | 扩展 | `zod` 已安装但未使用。 |

---

## 9. 迁移路径

### 9.1 阶段总表

| 阶段 | 对应 PRD 里程碑 | 目标 | 主要变更 | 独立上线判据 | 回滚 |
|---|---|---|---|---|---|
| P0 | M0 | 基线与边界 | 提交未跟踪文件；统一 catalog 事实源；鉴权 fail-closed；事务所有权 | 失败集合为空集（0 failed）；无 token 返回 401；三处 catalog 一致 | 回退代码与开关。迁移只增不减；应用后按迁移回滚脚本处理 |
| P1 | M1 | 契约层 | `tool_catalog`、价格簿、输出 schema、派生器 | 284 行；33 可执行；53 unsupported；字段非空 | 删表。运行时不读 |
| P2 | M1.5 + M2 | 授权与目录 | 域名 grant；discover/inspect；三处切读 | 对账一致；前 3 条命中评论工具 | `TOOL_CATALOG_READS=legacy` |
| P3 | M2.5 | 等级引擎 | 阈值表与 `compute_run_evidence_grade` | 四个等级单测通过 | 不改变行为 |
| P4 | M3 | 执行层 | `runs`、`run_steps`、`run_ledger_entries`；`task_runs` 扩列；授权 | 一次真实 run 为 L4；成本字段可读 | `RUN_EXECUTOR_ENABLED=false` |
| P5 | M4 | 证据层 | `claims`、`claim_evidence`、回填 | 结论可点回原文；反证 100% | 停止写 claim。旧表保留 |
| P6 | M5 | 报告层 | 合同、校验、双渲染、artifact | 改一个数字两页同步变；三哈希 | `REPORT_RENDERER=legacy` |
| P7 | M6 + M7a | 工作台与三模板 | `/workbench`、`/reports`、T1/T5/T2 | 新用户 5 分钟出报告；2 品牌 × 2 市场 | 路由开关。旧页面保留 |
| P8 | M7b + M8 | 二批模板与接入 | T3/T4；TikTok 21 表；MCP 18 工具；项目 key | 外部 agent 零文档接入；T4 跑通 | 保留全局 token。关闭新工具 |

### 9.2 每阶段说明

#### P0 基线与边界

变更：

1. 提交未跟踪文件：`collectors/outbound_policy.py`、`collectors/guarded_http.py`、`models/tiktok_content.py`、`repositories/tiktok_content.py`、`services/tiktok_content_ingestion.py`、`services/tiktok_tools.py`、`alembic/versions/202610190045_tiktok_r1_canonical_tables.py`。不提交会丢能力。
2. 决定 `202610190045` 是否应用。应用前必须备份。未跟踪头是 `202607280044`，见 `apps/api/alembic/versions/202610190045_tiktok_r1_canonical_tables.py:20-21`。
3. 新增 `scripts/catalog_digest.py`。它比对 `/api/collectors/catalog`、MCP `list_capabilities`、控制台 `/platforms` 三处 `tool_id` 集合。
4. 修改 `api/deps.py:54-79`：删除无 token 回退。新增 `DEMO_MODE=true` 显式开关。修 `api/routes/projects.py:59` 的 `create_project(session, None, ...)`。
5. 删除仓储层 `commit()`。见 1.4 表第 5 行。

验收：

- `pytest -q` 的失败集合为空集。137 条基线已作废，当前 0 failed。
- 无 token 请求返回 401。
- 跨项目读取返回 403。
- catalog digest 三处一致。

回滚：只回退环境变量与代码。无 schema 变更。

#### P1 契约层

变更：

1. 新增 `tool_catalog` 与 `tool_verification_events` 表。迁移脚本只新增，不改旧表。
2. 新增 `services/tool_catalog/` 包。
3. 迁移 `_ENDPOINT_TO_COLLECTOR` 与 `_APIFY_ENDPOINT_DEFAULTS` 到 `collectors/endpoint_catalog.py`。`quick_collect.py` 保留 re-export 一个发布周期。
4. 编写 `price_book_v1.json` 与 `output_schemas_v1.json`。
5. 新增 seed 命令：`python -m data_intelligence_hub.services.tool_catalog.seed`。

验收：

- 284 行。每行字段非空。
- 33 个可执行 collector type 有映射。
- 53 个 unsupported 有标记。
- Apify 条目 `actor_id` 全部可查。

回滚：删除两张新表。运行时不读。

#### P2 授权与目录

变更：

1. 配置 `COLLECTION_HTTP_GRANTS`。T5 需要 `fda.gov`、`gov.uk`、`prnewswire.com`、`cpsc.gov`、`ec.europa.eu`。T2/T3 需要独立站域名。规则见 PRD 1214。
2. 新增 `GET /api/tools`、`GET /api/tools/discover`、`GET /api/tools/{tool_id}`。
3. `/api/collectors/catalog` 改为读 `tool_catalog`。
4. MCP `list_capabilities` 与 `describe_capability` 改为读同一服务。
5. 控制台 `/platforms` 与新增 `/capabilities` 读同一接口。

验收：

- 三处 `tool_id` 集合一致。
- `discover("德国吸乳器差评")` 前 3 条含 Amazon 评论工具。
- 4 个 guarded_http 类型各跑一次真实调用并返回记录。

回滚：`TOOL_CATALOG_READS=legacy`。旧元数据保留一个发布周期。

#### P3 等级引擎

变更：

1. 新增 `services/evidence/grade.py`。
2. 新增阈值表 `services/evidence/fixtures/template_thresholds_v1.json`。T1–T5 的 `required_n`、`required_window_days`、`required_source_count` 来自 PRD 5.4.2。
3. 新增 `RunEvidenceGrade` 值对象。

验收：

- `L2`、`L3`、`L4` 三类输入各有用例。
- 边界条件：`sample_n == required_n` 返回 L4。
- 合同上限低于计算值时返回上限。

回滚：不改变任何现有行为。

#### P4 执行层

变更：

1. 新增 `runs`、`run_steps`、`run_ledger_entries` 表。
2. 扩展 `task_runs` 字段。
3. 从 `collector_service.py:73` 拆出 `execute_collector_call`。
4. 新增 `services/run/` 包：`service.py`、`executor.py`、`state_machine.py`、`ledger.py`。
5. 新增 `authorizations` 表与审批端点。
6. `quick_collect` 改为调用 `execute_collector_call`。异步路径改用持久队列。
7. 调度器继续调用 `execute_collection_task`。行为不变。

验收：

- 一次 T1 真实 run。回执 `evidence_grade=L4_authorized_live`。
- `task_runs` 可读单价、总价、剩余额度。
- 预算不足时返回 409。不发起调用。
- 进程重启后 queued run 能继续或明确失败。不丢任务。

回滚：`RUN_EXECUTOR_ENABLED=false`。调度器与 quick_collect 走旧路径。

#### P5 证据层

变更：

1. 新增 `claims` 与 `claim_evidence`。
2. `evidences.intelligence_id` 改 nullable。先加列，双写，再切读。
3. 回填脚本：`scripts/backfill_claims.py`。
4. 新增 `ClaimService` 与 `claim_policy.py`。
5. 新增 `GET /api/claims`。

验收：

- 回填后 claim 数 = 回填时 intelligence_items 数。
- 每条 claim 至少 1 条 evidence。
- 反证字段 100% 非空。
- claim 状态不超过等级上限。

回滚：停止写 claim。旧表与旧列保留。报告回到 intelligence 路径。

#### P6 报告层

变更：

1. 新增 `report_contract.schema.json`。
2. 新增 `services/reporting/` 包：`contract.py`、`validate.py`、`render_report.py`、`render_sop.py`、`components.py`、`templates.py`。
3. 新增 `report_artifacts` 与 `report_shares` 表。
4. `ReportService.generate_report` 改为合同路径。
5. `_render_daily_report` 保留一个发布周期，作为回滚路径。

验收：

- 改合同一个数字，两份 HTML 都变。
- 页脚有三个哈希。
- 破坏必填字段时校验报错。
- 五个模板各有一份黄金报告。

回滚：`REPORT_RENDERER=legacy`。旧渲染器保留到 P7 结束。

#### P7 工作台与三模板

变更：

1. 控制台新增 `/workbench`、`/reports`、`/reports/[id]`、`/capabilities`、`/capabilities/[id]`。
2. 侧栏更新。一级导航只保留工作台、报告、连接器、设置。
3. 新增登录页与 middleware。删除 `settings/account` 死页。
4. 新增模板 T1、T5、T2。
5. `apps/web` 报告组件迁入控制台。`report-detail-panel` 包装复用。

验收：

- 新用户不读文档，5 分钟内产出第一份报告。
- 必须经过的路由数 ≤ 2。
- 计划单可编辑，编辑后成本重算。
- 每模板 2 品牌 × 2 市场跑通。

回滚：关闭 `/workbench` 与 `/reports` 路由开关。旧控制台页面保留。

#### P8 二批模板与接入

变更：

1. 模板 T3、T4。T4 依赖 `202610190045` 的 21 张表已应用。
2. MCP 工具从 13 增到 18。新增 `discover`、`inspect`、`get_run`、`list_records`、`create_report`。
3. 新增 `project_api_keys`。中间件按 key 解析 project。
4. 全局 `SCRAPY_MCP_TOKEN` 保留一个发布周期。写明退役日期。
5. 新增 `/skills/dih/SKILL.md` 与 `/llms.txt`。

验收：

- 外部 agent 只读 `SKILL.md`，能完成 discover → inspect → collect → list_records。
- 工具数量快照测试通过。
- 白名单外工具返回 403。
- 不同 project 不能互读记录。
- 全局 token 退役后，无项目 key 返回 401。

回滚：保留全局 token。关闭 5 个新工具。项目 key 表保留但不用。

### 9.3 依赖图

```text
P0 ──► P1 ──► P2 ──► P4 ──► P7 ──► P8
        │      │      ▲
        │      └► P3 ─┘
        │             │
        └────────────►P5 ──► P6 ──► P7
```

约束：

1. P4 依赖 P3。没有阈值就无法判定 L4。
2. P5 依赖 P1 与 P3。claim 需要合同与等级。
3. P6 依赖 P5。没有 claim 就没有报告结论。
4. P7 依赖 P4 与 P6。
5. P8 的 T4 依赖 P0 的迁移决定。未应用时 T4 顺延。

### 9.4 回滚原则

1. 每个阶段必须有环境变量开关。开关只控制读路径或写路径，不控制 schema。
2. schema 变更只增不减。删除列必须晚两个发布周期。
3. 新旧路径并行时，必须双写或双读。不得只切一半。
4. 回滚不得丢已产生的 run、claim 或 artifact。它们必须保持可读。
5. 每次回滚必须写审计事件。事件包含操作人、时间、原因、影响的 run 或 report。

---

## 10. 架构决策记录

### ADR-01：tool_catalog 取代 capability_catalog 作为唯一事实源

**背景**

目录数字三处不一致。`api/routes/collectors.py:4713-4745` 硬编码 303 条端点元数据。`quick_collect.py:35` 有 284 条映射。`quick_collect.py:437` 有 95 条 Apify 默认值。生产 catalog 返回 309 个视图、281 个唯一端点、70 个平台（`catalog_digest=dad20448…`）。仓库生成物是 286 与 258，两套数字口径不同，不得混用。`capability_catalog_overseas_v2.json` 只有 7 个 implementation、35 条 assertion，且全部是 `candidate`。PRD 5.2.1 要求一个事实源。

**决定**

采用 PRD 的方案 B。新建 `tool_catalog` 作为写入源。旧 `capability_catalog` 冻结为只读。所有消费方读同一个 `ToolCatalogService`。派生器只从现有常量生成一次。双读两个发布周期。提供迁移脚本与回滚脚本。

**后果**

正面：目录、执行、MCP、控制台读同一份数据。幽灵端点可对账。成本与风险字段有归属。

负面：必须维护价格簿与输出 schema。旧治理发布路径冻结。迁移期需要双读与对账测试。

回滚：删除 `tool_catalog`，恢复旧读路径。旧表未改，可回退。

### ADR-02：新建 RunExecutor，不复用 fixture workflow_execution

**背景**

`services/workflow_execution` 有 9223 行。`create_workflow_fixture_run` 在 `execution.py:1079`。`executor_composition.py:61` 固定 `provider_call=False`。`:196` 直接丢弃凭据解析器。`:317` 固定 `call_audit_state=not_attempted`。`schemas/workflow_execution.py:56-57` 固定 `execution_mode=fixture` 与 `live_execution_authorized=False`。`api/routes/workflow_runs.py:170` 已在 `main.py:143` 注册（`origin/main:143`）。生产返回 200，`execution_mode=fixture`。

**决定**

新建 `services/run/`。复用 `workflow_execution/state_machine.py:20-44` 的状态表与 `budget.py:426-563` 的账本算法。`workflow_runs` 路由、模型与 fixture 执行代码保留并标 `fixture_only`，不接生产执行。运行表使用 `runs`、`run_steps`、`run_ledger_entries`。单次工具调用复用 `task_runs`。

**后果**

正面：执行路径可真实调用 Provider。运行状态可审计。真实执行只有一套语义；`workflow_runs` 继续只承载 fixture。

负面：新表与新迁移。需要重写控制台的 `/automation/runs` 入口。

回滚：保留 `task_runs` 与调度器路径。关闭 `RUN_EXECUTOR_ENABLED`。

### ADR-03：保留 intelligence_items，新增 claims 作为报告结论层

**背景**

`intelligence_items` 只适合监控。它没有 claim 状态、证据等级、范围、反证、责任人。`evidences` 的 `intelligence_id` 非空。11 个路由模块读 `intelligence_items`。报告需要跨样本结论与反证。

**决定**

保留 `intelligence_items`。新增 `claims` 与 `claim_evidence`。`evidences.intelligence_id` 改 nullable。报告只读 claims。Dashboard 与 alerts 继续读 intelligence_items。回填一条 intelligence 到一条 hypothesis claim。

**后果**

正面：不破坏现有读模型。报告结论可独立演进。claim 可以聚合多次 run。

负面：两套模型并存。必须写清读写边界。回填数据只能作为初稿。

回滚：停止写 claim。旧路径继续可用。

### ADR-04：报告以合同为唯一渲染输入，两个渲染器为纯函数

**背景**

现有 `_render_daily_report` 只输出三段。PRD 5.5.1 要求一份合同、两个渲染器。两个渲染器如果各自读数据库，会产生口径漂移。报告数字不可复现。

**决定**

`report_contract` 是唯一渲染输入。两个渲染器只接收合同与模板。不得读数据库、不得发网络、不得调用 LLM。合同先通过 schema 与语义校验，再渲染。合同与两个 HTML 一起存档，写三个哈希。

**后果**

正面：报告与 SOP 口径一致。数字可复现。改一个数字两页同步变。

负面：必须维护合同 schema 与模板注册表。所有 headline 数字必须由指标函数计算。渲染器不能用临时查询补数据。

回滚：`REPORT_RENDERER=legacy`。旧渲染器保留一个发布周期。

### ADR-05：证据等级由确定性函数在应用层计算

**背景**

PRD 5.4.2 要求等级可复核。模型不能声明等级。现有 `schemas/workflow_executor_evidence.py:123` 固定 `L2_fixture_local`。

**决定**

新增 `services/evidence/grade.py` 纯函数。L4 `RunService` 在 G6 后调用。L1 持久化到 `runs.evidence_grade` 与 `task_runs.evidence_grade`。`ToolContract.max_evidence_grade` 只作上限。claim 状态由等级上限约束。

**后果**

正面：等级可复算。输入可审计。没有模型漂移。

负面：阈值变更必须改代码与模板。需要单元测试覆盖四个等级。

回滚：不改变现有行为。

### ADR-06：应用服务是唯一事务所有者，仓储不得提交

**背景**

`core/database.py:50-52` 的 `get_session` 只 yield，不提交。多数 service 显式 commit。`repositories/datasets.py:88,161,259`、`repositories/cleaning_plans.py:24`、`repositories/automation_plans.py:67,76,142,152`、`repositories/scheduler.py:14` 在仓储层提交。跨仓储用例会产生部分写入。

**决定**

应用服务是唯一事务所有者。仓储只做查询与 `flush`。路由不提交。Worker 的每个 step 边界提交一次。预算预留必须先提交，再发外部请求。

**后果**

正面：部分写入可消除。测试可用单事务回滚。预算与外部调用顺序明确。

负面：需要重构 4 个仓储文件。现有调用方要检查事务边界。

回滚：逐个文件回退。新增代码不得再引入仓储提交。

### ADR-07：鉴权默认拒绝，凭据按项目隔离

**背景**

`api/deps.py:54-79` 在无有效 cookie 时回退 demo workspace。`mcp_runtime/auth.py:20-23` 在 token 为空时直接放行。Provider key 直接读环境变量，无法按项目隔离。PRD 第 1220 行与第 1222 行要求修复。

**决定**

`get_auth_context` 默认返回 401。新增 `DEMO_MODE=true` 显式开关。MCP 默认拒绝空 token。新增 `project_api_keys`。新增 `CredentialResolver`，按 `project_id` 与 provider 解析密钥。环境变量只作引导回退。全局 token 保留一个发布周期后退役。

**后果**

正面：多租户隔离真实。项目可独立配额与审计。

负面：控制台必须补登录页与 middleware。演示环境必须显式配置。Provider key 需要迁移。

回滚：打开 `DEMO_MODE` 与全局 token。项目 key 表保留。

### ADR-08：冻结 automation_service，新功能进入 bounded context

**背景**

`services/automation_service.py` 有 13537 行、335 个函数。唯一调用方是 `api/routes/automation.py`。继续加功能会放大合并冲突与回归面。

**决定**

冻结该文件。只允许缺陷修复。新功能必须进入 `services/tool_catalog`、`services/run`、`services/evidence`、`services/reporting`、`services/planning` 之一。CI 增加文件行数守卫。超过 13537 行时构建失败。

**后果**

正面：新代码有清晰边界。回归面可控。

负面：短期需要在路由层做适配。长期需要拆分旧功能。

回滚：不适用。冻结是治理决定。

### ADR-09：统一采集执行原语，消除三条重复路径

**背景**

采集执行有三条路径：`execute_collection_task`（调度器与手动任务）、`quick_collect`（同步与异步）、CDO `_call_tikhub`（HTTP 回环）。三处各自处理 Source、Task、Run、超时、去重。CDO 固定 30 秒超时，见 `agents/tiktok_cdo/data_sources.py:222`、`:273`。

**决定**

抽出 `execute_collector_call`。它负责一次 collector 调用、事务、超时、去重、规范化与信号。`execute_collection_task`、`quick_collect`、`RunExecutor` 都调用它。CDO 改为调用 L4 应用服务。MCP `collect` 改为调用应用服务，不再导入 API 路由。

**后果**

正面：行为一致。超时与去重只有一份实现。MCP 与 CDO 可复用。

负面：需要重构 `collector_service.py` 与 `quick_collect.py`。需要回归采集测试（待复测）。

回滚：保留旧入口一个发布周期。新入口通过开关启用。

---

## 附录 A：关键文件索引

| 主题 | 文件 | 行 |
|---|---|---|
| 应用入口与路由挂载 | `apps/api/src/data_intelligence_hub/main.py` | `59-65`、`90-116` |
| 配置门控 | `apps/api/src/data_intelligence_hub/core/config.py` | `31-33`、`41-43`、`50-58`、`77-87` |
| 会话 | `apps/api/src/data_intelligence_hub/core/database.py` | `43-52`、`67` |
| 鉴权上下文 | `apps/api/src/data_intelligence_hub/api/deps.py` | `22-79` |
| 采集执行 | `apps/api/src/data_intelligence_hub/services/collector_service.py` | `73`、`302-318`、`335-389` |
| 规范化 | `apps/api/src/data_intelligence_hub/services/normalization_service.py` | `32`、`73-87` |
| 信号 | `apps/api/src/data_intelligence_hub/services/signal_service.py` | `118`、`153`、`259-292` |
| 情报 | `apps/api/src/data_intelligence_hub/services/intelligence_service.py` | `128` |
| 报告 | `apps/api/src/data_intelligence_hub/services/report_service.py` | `184`、`536`、`647`、`729`、`804`、`1198` |
| 调度器 | `apps/api/src/data_intelligence_hub/scheduler/service.py` | `71`、`91`、`130`、`186` |
| 采集器协议 | `apps/api/src/data_intelligence_hub/collectors/base.py` | `38`、`54`、`60` |
| 注册表 | `apps/api/src/data_intelligence_hub/collectors/registry.py` | `130`、`220` |
| 外访策略 | `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py` | `19-118`、`138`、`173`、`201`、`213` |
| 受控 HTTP | `apps/api/src/data_intelligence_hub/collectors/guarded_http.py` | `39`、`99`、`120` |
| 快速采集 | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py` | `35`、`437`、`860`、`960`、`1027` |
| 计划器 | `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py` | `477` |
| 路由解析 | `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py` | `67`、`293-298`、`570` |
| MCP | `apps/api/src/data_intelligence_hub/mcp_runtime/server.py` | `35-52`、`55-309` |
| CDO | `apps/api/src/data_intelligence_hub/agents/tiktok_cdo/` | `router.py:33`、`data_sources.py:209-293` |
| 控制台壳 | `apps/scraper-console/src/components/layout/app-shell.tsx` | `16` |
| 控制台导航 | `apps/scraper-console/src/components/layout/sidebar.tsx` | `7-20` |
| 控制台 API 客户端 | `apps/scraper-console/src/lib/api/client.ts` | `13-34` |

## 附录 B：数据表清单

### 现有表

`collection_tasks`、`task_runs`、`raw_records`、`entities`、`entity_snapshots`、`signals`、`intelligence_items`、`evidences`、`reports`、`report_subscriptions`、`report_subscription_runs`、`report_audit_events`、`projects`、`sources`、`collectors`、`users`、`workspaces`、`workspace_members`、`platform_credential_bundles`、`scheduler_leases`、`scheduler_ticks`、`datasets`、`dataset_versions`、`dataset_export_jobs`、`cleaning_plans`、`workflow_plans`、`workflow_versions`、`workflow_templates`、`workflow_scope_templates`、TikTok R1 的 21 张表。

### 新增表

| 表 | 用途 | 主要外键 |
|---|---|---|
| `tool_catalog` | 工具合同 | 无 |
| `tool_verification_events` | 实测记录 | `tool_id` |
| `runs` | 计划运行 | `project_id`、`plan_id`、`authorization_id` |
| `run_steps` | 运行步骤 | `run_id`、`task_run_id` |
| `run_ledger_entries` | 预算账本 | `run_id`、`step_id` |
| `authorizations` | 计划批准 | `project_id`、`approver_id` |
| `claims` | 报告结论 | `project_id`、`run_id` |
| `claim_evidence` | 结论证据 | `claim_id`、`evidence_id` |
| `report_artifacts` | 合同与 HTML | `report_id` |
| `report_shares` | 分享链接 | `report_id` |
| `project_api_keys` | 项目 key | `project_id` |

### 扩展表

| 表 | 变更 |
|---|---|
| `task_runs` | 新增 `project_id`、`run_id`、`step_index`、`unit`、`quantity`、`unit_price`、`total_cost_usd`、`remaining_budget`、`provider`、`provider_run_id`、`endpoint_type`、`evidence_grade`、`schema_version`、`idempotency_key_hash` |
| `evidences` | `intelligence_id` 改 nullable |
| `reports` | `report_type` 扩枚举。旧值映射 `daily_digest` |
| `platform_credential_bundles` | 新增 `project_id`。旧行 `project_id` 为空表示 workspace 级 |
| `collectors` | 保留。只作 collector type 注册表。不得当工具目录 |

## 附录 C：验收命令

```bash
# 1. 架构边界
cd apps/api && pytest -q tests/unit/test_architecture_boundaries.py

# 2. 合同派生与对账
cd apps/api && pytest -q tests/unit/test_tool_contract_derivation.py tests/unit/test_tool_catalog_reconciliation.py

# 3. 证据等级
cd apps/api && pytest -q tests/unit/test_evidence_grade.py

# 4. 报告合同与渲染
cd apps/api && pytest -q tests/unit/test_report_contract.py tests/unit/test_report_renderers.py

# 5. 采集回归
cd apps/api && pytest -q tests/unit/test_collectors.py tests/unit/test_collection_timeouts.py tests/unit/test_scheduler.py

# 6. 前端质量门
cd apps/scraper-console && pnpm test && pnpm exec tsc --noEmit && pnpm build
```

结果判据：

1. 上述命令全部通过。
2. `pytest -q` 全量失败集合为空集。137 条基线已作废，当前 0 failed。
3. 三个对账集合相等。
4. 一次真实 T1 run 为 `L4_authorized_live`。
5. 改合同一个数字，两份 HTML 同步变化。
