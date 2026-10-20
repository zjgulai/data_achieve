---
name: dih-module-design
description: DIH 工作模块与接口设计。定义 12 个业务模块、依赖规则、接口清单、前后端落位、页面映射、构建顺序与现有代码归属。规划模块边界、新增接口或拆分服务前先读这份。
---

# DIH 工作模块与接口设计

> 版本：v1.0 · 2026-10-20
> 依据：[PRD](../product/【PRD】母婴出海数据洞察Agent工作台.md) · [Playbook](../product/【Playbook】母婴出海洞察交付.md) · [整站能力整合方案](../architecture/【技术方案】DIH整站能力整合方案.md) · [能力图谱](../architecture/【能力图谱】DIH-控制台能力地图.md)
> 仓库根：`/Users/lute/Project/data_scrapy`
> 状态：设计稿。只定义模块与接口，不修改代码。
> 契约以 [契约冻结 v1](./【契约冻结】v1-表名-枚举-接口.md) 为准。

## 0. 阅读规则

### 0.1 结论先行

1. 系统必须切成 12 个业务模块。8 个是 PRD 要求的核心模块。4 个是支撑模块。
2. 主链必须是 M02 目录 → M04 采集 → M05 证据 → M07 报告。M10 只做编排，不持有采集内核。
3. M09 接入网关必须是唯一外部入口。REST、MCP、Skill 都必须过同一道门。
4. `workflow_execution` 必须保持离线。`workflow_runs` 路由已挂载，但只返回 fixture 数据（`execution_mode=fixture`、`provider_call=False`）。下一批不得把它当执行层。
5. 下一批必须先补四项：目录契约、证据与主张、额度账本、租户鉴权。四项完成后再接工作台与前端。
6. 现有主链可复用。复用项必须有测试或生产只读证据。无证据的项必须标 `new` 或 `dead`。

### 0.2 状态判定

| 状态 | 判定条件 |
| --- | --- |
| `reuse_as_is` | 已有挂载调用路径，并且有通过的单元测试或 2026-10-20 生产只读探测证据。 |
| `extend` | 模块可用，但范围不足。必须改代码或加字段。 |
| `new` | 仓库不存在，必须新建。 |
| `dead` | 代码存在，但没有可达调用路径。不得计入复用。 |

### 0.3 证据口径

本文使用三类证据。每条结论必须标注来源。

| 证据 | 口径 |
| --- | --- |
| 本地测试 | 2026-10-20 运行 `pytest -q apps/api/tests/unit` 与 `pytest -q apps/api/tests/integration`：单元 1980 passed、集成 384 passed，均 0 failed。覆盖 `test_collectors.py`、`test_apify_actor_collector.py`、`test_tikhub_social_collector.py`、`test_guarded_http.py`、`test_scheduler.py`、`test_collection_timeouts.py`、`test_outbound_scheduling.py`、`test_normalization.py`、`test_signals.py`、`test_mcp_runtime.py`、`test_mcp_auth.py`、`test_mcp_governance.py`、`test_mcp_transport_security.py`、`test_mcp_token_config.py`、`test_workflow_planner.py`、`test_workflow_planner_resolver.py`、`test_workflow_plan_persistence.py`、`test_workflow_plan_lifecycle.py`、`test_workflow_plan_comparison.py`、`test_platform_package_builder.py`、`test_llm_service.py`、`test_tiktok_tools.py`、`test_tiktok_content_ingestion.py`、`test_capability_catalog.py`、`test_capability_matrix.py`、`test_platform_credentials.py`、`test_collector_seeding.py`、`test_outbound_policy.py`、`test_automation_service.py`、`test_toolkit_preflight.py`、`test_toolkit_method_card_drafts.py`。 |
| 生产只读 | 2026-10-20 对 `https://scrapy.luteos.com` 的 GET 探测。证据来自上一轮清点记录。本文只引用，不重复探测。 |
| 静态事实 | 文件、行号、路由挂载、表定义。以当前工作树为准。 |

目录计数有两套口径，不得混用：生产为 309 视图 / 281 唯一端点 / 70 平台（`catalog_digest=dad20448…`）；仓库生成物为 286 视图 / 258 唯一端点。对账以 `catalog_digest` 为准。

不使用的证据：

- `reports/live-sweep/baseline-pytest-failures.txt`（137 条）已作废。不得再引用该文件作为当前失败数。
- 未登录生产做交互复核。只引用已记录的只读探测。

### 0.4 术语

术语按 [写作标准](../standards/writing-standard-ste.md) 与整站方案 §1.1。本文只用左列。

| 术语 | 含义 |
| --- | --- |
| 工具 | 用户可调用的最小单元，对应 `tool_id`。 |
| 能力视图 | 工具在某个平台分类下的展示条目。 |
| 端点 | 上游服务的实际接口。 |
| 平台包 | 平台维度的 Skill 打包单元。 |
| 调用 | 一次工具执行，对应 `ToolCall`。 |
| 采集任务 | 采集类任务，对应 `CollectionTask`。 |
| 运行 | 一份计划的一次执行，对应 `runs`。单次采集执行记录由 `task_runs` 承载。 |
| 产物 | 调用的输出资产，对应 `Artifact`。 |
| 数据集 | `Dataset`。 |
| 主张 | 报告里的一条结论，对应 `Claim`。 |
| 证据 | 支撑或反驳主张的记录，对应 `Evidence`。 |

## 1. 模块划分

### 1.0 切分规则

1. 一个模块对应一个业务能力。模块不对应技术层。
2. 模块名必须能出现在 PRD 的页面、流程或 Playbook 的阶段里。
3. 一个模块必须拥有数据。没有数据的模块不单列。
4. 一个模块必须写清不负责什么。
5. 共享技术能力放 K0。K0 不是业务模块。
6. 组合根只有两个：M10 工作台编排与 M09 接入网关。
7. 执行内核只有一处：M04。其他模块不得实例化 collector。
8. 报告只有一个生成入口：M07。其他模块不得拼报告正文。

### 1.1 模块总览

| ID | 模块 | 职责一句话 | 主要数据 | 总状态 |
| --- | --- | --- | --- | --- |
| M01 | 身份与租户 | 管理用户、工作区、项目与会话。 | `users`、`workspaces`、`workspace_members`、`projects` | extend |
| M02 | 目录与发现 | 维护唯一工具契约目录。 | `tool_catalog`（新）、`collectors`、`capability_*` | extend |
| M03 | 连接器与凭据 | 管理 Provider 凭据、域名 grant、连接器就绪度。 | `platform_credential_bundles`、`provider_health_snapshots` | extend |
| M04 | 采集执行 | 执行一次采集，写入原始记录。 | `sources`、`collection_tasks`、`task_runs`、`raw_records`、TikTok 规范表 | extend |
| M05 | 证据与主张 | 把原始记录转成实体、信号、主张与证据。 | `entities`、`entity_snapshots`、`signals`、`intelligence_items`、`evidences`、`claims`（新） | extend |
| M06 | 模板注册 | 注册报告模板、章节、阈值与禁止输出。 | `report_templates`（新）、`report_template_versions`（新） | new |
| M07 | 报告生成 | 用一份合同生成报告与 SOP。 | `reports`、`report_subscriptions`、`report_audit_events`、`report_artifacts`（新）、`report_shares`（新） | extend |
| M08 | 额度与审计 | 记录调用、成本、额度、授权与审计。 | `tool_calls`（新）、`run_ledger_entries`（新）、`quota_accounts`（新）、`authorizations`（新） | new |
| M09 | 接入网关 | 统一外部入口：项目 key、白名单、额度、分派。 | `project_api_keys`（新） | extend |
| M10 | 工作台编排 | 把任务单变成计划、门禁与执行序列。 | `workbench_tasks`（新）、`runs`（新）、`run_steps`（新）、`workflow_plans`、`workflow_versions` | new |
| M11 | 告警与通知 | 匹配预警规则，发送站内信与邮件。 | `alert_rules`、`alert_events`、`notifications`、`email_*` | reuse_as_is |
| M12 | 数据集与产物 | 管理数据集、版本、清洗计划、漂移与导出。 | `datasets`、`dataset_versions`、`cleaning_plans`、`dataset_drift_events`、`dataset_export_jobs` | extend |

模块 ID 的使用规则：

- 文档、代码目录、日志必须使用同一 ID。
- 模块 ID 不随页面改名。
- 一个表只能有一个拥有模块。见 §8.4。

### 1.2 M01 身份与租户（identity）

**职责**：管理用户、工作区、项目与会话。提供租户上下文。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `users` | `User` | `apps/api/src/data_intelligence_hub/models/user.py:15` | 用户与口令哈希。 |
| `workspaces` | `Workspace` | `apps/api/src/data_intelligence_hub/models/workspace.py:22` | 租户根。 |
| `workspace_members` | `WorkspaceMember` | `apps/api/src/data_intelligence_hub/models/workspace.py:46` | 成员关系。 |
| `projects` | `Project` | `apps/api/src/data_intelligence_hub/models/project.py:22` | 项目。报告与采集的归属。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `/api/auth/register`、`/api/auth/login`、`/api/auth/logout`、`/api/auth/me` | `apps/api/src/data_intelligence_hub/api/routes/auth.py:23` | reuse_as_is |
| HTTP | `/api/projects`、`/api/projects/{project_id}` | `apps/api/src/data_intelligence_hub/api/routes/projects.py:26` | extend |
| 服务 | `register_user`、`login_user`、`get_session_for_user` | `apps/api/src/data_intelligence_hub/services/auth_service.py:38`、`:81`、`:97` | reuse_as_is |
| 服务 | `get_projects`、`create_project`、`update_project`、`archive_project` | `apps/api/src/data_intelligence_hub/services/project_service.py:18`、`:27`、`:69`、`:86` | extend |

**不负责**：

- 不负责项目级 API key。项目 key 属于 M09。
- 不负责角色权限矩阵。PRD `/settings` 要求成员与角色。角色表必须新建。
- 不负责工具白名单。白名单属于 M09。

**状态**：`extend`。

**证据**：

- 路由已挂载：`apps/api/src/data_intelligence_hub/main.py:91`、`:96`。
- JWT 实现：`apps/api/src/data_intelligence_hub/core/security.py:23-43`。
- 部署契约：`docs/deployment-new-server.md:67-74`。

**必须修的问题**：

1. `get_auth_context` 在无 token 时回退 demo workspace。见 `apps/api/src/data_intelligence_hub/api/deps.py:54-79`。11 个路由模块直接调用 `get_demo_workspace`。见 §9.2。必须改为显式 401，或加明确的 demo 开关。
2. `POST /api/projects` 调用 `create_project(session, None, ...)`。见 `apps/api/src/data_intelligence_hub/api/routes/projects.py:59`。`create_project` 直接读 `user.id`。见 `apps/api/src/data_intelligence_hub/services/project_service.py:39`。demo workspace 存在时抛 `AttributeError`。必须传入当前用户。
3. `workspace_members` 没有角色字段。PRD `/settings` 要求成员与角色。必须新增 `role`。

### 1.3 M02 目录与发现（catalog）

**职责**：维护唯一工具契约目录。提供搜索、详情、分类、核验状态。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `collectors` | `Collector` | `apps/api/src/data_intelligence_hub/models/collector.py:12` | 采集器注册表。99 行。 |
| `capability_catalog_head` | `CapabilityCatalogHead` | `apps/api/src/data_intelligence_hub/models/capability_governance.py:352` | catalog 当前头。 |
| `capability_catalog_snapshots` | `CapabilityCatalogSnapshot` | `apps/api/src/data_intelligence_hub/models/capability_governance.py:303` | catalog 快照。 |
| `capability_publication_revisions` | `CapabilityPublicationRevision` | `apps/api/src/data_intelligence_hub/models/capability_governance.py:318` | 发布版本。 |
| `capability_candidate_versions` | 见模型 | `apps/api/src/data_intelligence_hub/models/capability_governance.py:138` | 候选。 |
| `capability_verification_tasks` | 见模型 | `apps/api/src/data_intelligence_hub/models/capability_governance.py:200` | 核验任务。 |
| `capability_verification_decisions` | 见模型 | `apps/api/src/data_intelligence_hub/models/capability_governance.py:250` | 核验决定。 |
| `tool_catalog` | `ToolCatalogEntry` | 新建 | 唯一工具契约表。字段见 PRD §5.1。 |
| `tool_verification_events` | `ToolVerificationEvent` | 新建 | 契约变更与核验审计。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET /api/capabilities/matrix` | `apps/api/src/data_intelligence_hub/api/routes/capabilities.py:39` | reuse_as_is |
| HTTP | `GET /api/capabilities/assertions` | `apps/api/src/data_intelligence_hub/api/routes/capabilities.py:60` | reuse_as_is |
| HTTP | `GET /api/capabilities/implementations` | `apps/api/src/data_intelligence_hub/api/routes/capabilities.py:93` | reuse_as_is |
| HTTP | `GET /api/collectors`、`GET /api/collectors/catalog`、`GET /api/collectors/docs` | `apps/api/src/data_intelligence_hub/api/routes/collectors.py:39`、`:46`、`:4785` | extend |
| HTTP | `GET /api/platform-packages`、`/{platform_id}`、`/{platform_id}/playbook` | `apps/api/src/data_intelligence_hub/api/routes/platform_packages.py:41`、`:61`、`:69` | reuse_as_is |
| HTTP | `GET /api/toolkit`、`GET/POST /api/toolkit/method-card-drafts` | `apps/api/src/data_intelligence_hub/api/routes/toolkit.py:27`、`:50`、`:60` | reuse_as_is |
| 服务 | `get_capability_catalog` | `apps/api/src/data_intelligence_hub/services/capability_catalog.py:38` | reuse_as_is |
| 服务 | `build_capability_matrix` | `apps/api/src/data_intelligence_hub/services/capability_matrix.py:46` | reuse_as_is |
| 服务 | `ensure_collectors_seeded`、`validate_collector_config` | `apps/api/src/data_intelligence_hub/services/collector_catalog.py:780`、`:827` | reuse_as_is |
| 服务 | `get_toolkit_overview` | `apps/api/src/data_intelligence_hub/services/toolkit_service.py:475` | reuse_as_is |
| 服务 | `list_method_card_drafts`、`save_method_card_draft` | `apps/api/src/data_intelligence_hub/services/toolkit_method_card_service.py:33`、`:54` | reuse_as_is |
| 新 HTTP | `GET /api/tools`、`GET /api/tools/{tool_id}` | 新建 `modules/catalog/routes.py` | new |
| 新 HTTP | `GET /api/tools/discover` | 新建 `modules/catalog/routes.py` | new |

**不负责**：

- 不负责执行工具。执行属于 M04。
- 不负责存储凭据。凭据属于 M03。
- 不负责结算成本。成本属于 M08。
- 不负责渲染报告。渲染属于 M07。
- 不负责发布路由。发布属于受控脚本或 M10 管理动作。当前 `capability_governance` router 未挂载。

**状态**：`extend`。现有读模型可复用。`tool_catalog` 必须新建。

**证据**：

- `tests/unit/test_capability_catalog.py`、`tests/unit/test_capability_matrix.py`、`tests/unit/test_collector_seeding.py`、`tests/unit/test_platform_package_builder.py` 通过。属于 2026-10-20 本地测试覆盖范围，结果见 §0.3。
- 生产只读：`GET /api/capabilities/matrix` 返回 200。`GET /api/collectors` 返回 99 行。
- 数据事实：`COLLECTOR_CATALOG` 有 99 个 `CollectorDefinition`。见 `apps/api/src/data_intelligence_hub/services/collector_catalog.py:24`。
- 数据事实：`COLLECTOR_REGISTRY` 有 86 项。见 `apps/api/src/data_intelligence_hub/collectors/registry.py:130-217`。
- 数据事实：`_ENDPOINT_TO_COLLECTOR` 有 284 项。见 `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:35`。
- 数据事实：`GET /api/collectors/catalog` 硬编码 303 个 `CollectorEndpointMetadata`。见 `apps/api/src/data_intelligence_hub/api/routes/collectors.py:46-48`。

**必须修的问题**：

1. 三处事实源不一致：303 条端点元数据、284 条映射、99 个 collector 类型（均为代码口径；生产目录为 309 视图 / 281 唯一端点 / 70 平台，仓库生成物为 286 / 258）。`tool_catalog` 必须以 `endpoint_type` 为计数单位，成为唯一事实源。
2. 默认 catalog 的 35 条 assertion 全部是 `candidate`。见 `apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json`。`capability_resolver` 对 `candidate` 一律拒绝。见 `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py:293-298`。实测 planner preview 全部 `held`。
3. `capability_governance` router 未挂载。见 `apps/api/src/data_intelligence_hub/main.py:90-115`。应用内无法发布 `verified` catalog。必须补受控发布路径。
4. `capability_discovery` router 未挂载。生产 404。见 `apps/api/src/data_intelligence_hub/services/capability_discovery/preview.py:274`。必须删除或挂载。

### 1.4 M03 连接器与凭据（connectors）

**职责**：管理 Provider 凭据、域名 grant、连接器就绪度与页面探测。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `platform_credential_bundles` | `PlatformCredentialBundle` | `apps/api/src/data_intelligence_hub/models/platform_credential.py:12` | Fernet 密文。无 `project_id`。 |
| `provider_health_snapshots` | `ProviderHealthSnapshot` | `apps/api/src/data_intelligence_hub/models/provider_health.py:33` | Provider 健康。 |
| `provider_health_route_feedbacks` | `ProviderHealthRouteFeedback` | `apps/api/src/data_intelligence_hub/models/provider_health.py:168` | 路由反馈。 |
| `site_analyses` | `SiteAnalysis` | `apps/api/src/data_intelligence_hub/models/automation_plan.py:24` | 站点分析。 |
| `browser_diagnostic_*` | 见模型 | `apps/api/src/data_intelligence_hub/models/automation_plan.py:56-206` | 浏览器诊断。 |
| `extraction_plans` | `ExtractionPlan` | `apps/api/src/data_intelligence_hub/models/automation_plan.py:207` | 抽取计划。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET/PUT/DELETE /api/settings/platform-credentials` | `apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py:59`、`:76`、`:106` | extend |
| HTTP | `GET /api/automation/social-provider-catalog` | `apps/api/src/data_intelligence_hub/api/routes/social_provider.py:71` | extend |
| HTTP | `POST /api/automation/social-provider-readiness`、`/social-provider-gate` | `apps/api/src/data_intelligence_hub/api/routes/social_provider.py:101`、`:120` | extend |
| HTTP | `POST /api/automation/site-analysis`、`GET /api/automation/site-analyses` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:208`、`:232` | extend |
| HTTP | `POST /api/automation/browser-diagnostic-jobs`、`GET /api/automation/browser-diagnostic-jobs/{id}` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:373`、`:430` | dead |
| HTTP | `POST /api/toolkit/preflight` | `apps/api/src/data_intelligence_hub/api/routes/toolkit.py:35` | extend |
| 服务 | `list_platform_credentials`、`update_platform_credentials`、`remove_platform_credentials` | `apps/api/src/data_intelligence_hub/services/platform_credentials.py:172`、`:189`、`:240` | reuse_as_is |
| 服务 | `get_social_provider_catalog`、`prepare_social_provider_readiness`、`prepare_social_provider_gate` | `apps/api/src/data_intelligence_hub/services/social_provider.py:140`、`:348`、`:395` | extend |
| 服务 | `run_toolkit_preflight` | `apps/api/src/data_intelligence_hub/services/toolkit_preflight_service.py:42` | replace |

**不负责**：

- 不负责生产采集。采集属于 M04。
- 不负责工具契约。契约属于 M02。
- 不负责成本结算。结算属于 M08。
- 不负责浏览器集群。PRD 明确不做自建浏览器集群。

**状态**：`extend`。

**证据**：

- `tests/unit/test_platform_credentials.py`、`tests/unit/test_outbound_policy.py` 通过。
- 生产只读：`GET /api/automation/social-provider-catalog` 返回 200。
- `platform_credentials` 使用 Fernet。密钥来自 `apps/api/src/data_intelligence_hub/core/config.py:50`。无 master key 时 `vault_write_enabled=false`。

**必须修的问题**：

1. 凭据只按 workspace 存。表 `platform_credential_bundles` 没有 `project_id`。PRD §10 风险 9 要求两个项目用不同 key 调同一工具且互不可见。必须给表加 `project_id`（可空）与唯一约束，或在 M03 新建项目级绑定表。解析顺序必须为项目 → 工作区。
2. Provider key 直接读环境变量。位置：`tikhub_social.py:493`、`apify_actor.py:51`、`exa_collector.py:38`、`firecrawl_collector.py:50`、`anysearch_collector.py:30`、`jina_reader.py:27`、`collectors/base.py:172`。无法按项目隔离。必须改为 M03 的凭据解析器。
3. `toolkit_preflight_service` 直接调用 `httpx`，只做 SSRF 检查，不经过 `outbound_policy` 的 host grant。见 `apps/api/src/data_intelligence_hub/services/toolkit_preflight_service.py:115-145`。必须补策略或写明例外。
4. `browser_structure_diagnostic` 是 `dead`。只被测试导入。见 `apps/api/src/data_intelligence_hub/services/browser_structure_diagnostic.py:13`。不得计入复用。
5. `provider_execution_preflight` 没有 live 调用路径。只被 `social_api/provider_fixture_runtime.py:13` 与两个 disabled 适配使用。见 `apps/api/src/data_intelligence_hub/services/provider_execution_preflight.py:33`。

### 1.5 M04 采集执行（execution）

**职责**：执行一次采集。写入原始记录。维护任务、运行、调度与 TikTok 规范表投影。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `sources` | `Source` | `apps/api/src/data_intelligence_hub/models/source.py:19` | 采集源。 |
| `collection_tasks` | `CollectionTask` | `apps/api/src/data_intelligence_hub/models/task.py:20` | 采集任务。 |
| `task_runs` | `TaskRun` | `apps/api/src/data_intelligence_hub/models/task.py:45` | 运行。必须扩成本字段。 |
| `scheduler_leases` | `SchedulerLease` | `apps/api/src/data_intelligence_hub/models/scheduler.py:12` | 调度租约。 |
| `scheduler_ticks` | `SchedulerTick` | `apps/api/src/data_intelligence_hub/models/scheduler.py:21` | 调度计数。 |
| `raw_records` | `RawRecord` | `apps/api/src/data_intelligence_hub/models/raw_record.py:30` | 原始记录。 |
| `creator`、`creator_snapshot`、`video`、`video_snapshot`、`comment`、`comment_snapshot`、`hashtag`、`hashtag_snapshot`、`video_hashtag`、`trend_topic`、`sound`、`transcript` | 见模型 | `apps/api/src/data_intelligence_hub/models/tiktok_content.py:65-394` | 12 张 TikTok 规范表。 |
| TikTok R1 其余 9 张表 | 无 ORM | `apps/api/alembic/versions/202610190045_tiktok_r1_canonical_tables.py` | 迁移创建 21 张，ORM 只映射 12 张。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `POST /api/quick-collect`、`POST /api/quick-collect/async` | `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:959`、`:1022` | extend |
| HTTP | `GET/POST /api/sources`、`GET/PATCH /api/sources/{id}` | `apps/api/src/data_intelligence_hub/api/routes/sources.py:36`、`:51`、`:70`、`:87` | reuse_as_is |
| HTTP | `POST /api/sources/{id}/test`、`/enable`、`/disable` | `apps/api/src/data_intelligence_hub/api/routes/sources.py:107`、`:130`、`:149` | reuse_as_is |
| HTTP | `GET /api/tasks`、`GET /api/tasks/runs`、`GET /api/tasks/scheduler/overview` | `apps/api/src/data_intelligence_hub/api/routes/tasks.py:32`、`:67`、`:57` | reuse_as_is |
| HTTP | `POST /api/tasks/{id}/run`、`/pause`、`/resume` | `apps/api/src/data_intelligence_hub/api/routes/tasks.py:108`、`:140`、`:157` | reuse_as_is |
| HTTP | `GET /api/raw-records`、`GET /api/raw-records/{id}` | `apps/api/src/data_intelligence_hub/api/routes/raw_records.py:19`、`:43` | reuse_as_is |
| HTTP | `GET /api/tiktok/tools`、`POST /api/tiktok/tools/{tool_id}` | `apps/api/src/data_intelligence_hub/api/routes/tiktok_tools.py:21`、`:28` | reuse_as_is |
| 服务 | `execute_collection_task` | `apps/api/src/data_intelligence_hub/services/collector_service.py:73` | reuse_as_is |
| 服务 | `run_task_now`、`pause_task`、`resume_task` | `apps/api/src/data_intelligence_hub/services/task_service.py:86`、`:62`、`:74` | reuse_as_is |
| 服务 | `create_source`、`test_source_config`、`enable_source` | `apps/api/src/data_intelligence_hub/services/source_service.py:35`、`:112`、`:132` | reuse_as_is |
| 服务 | `next_run_at`、`is_task_due`、`update_retry_state_after_run` | `apps/api/src/data_intelligence_hub/services/task_schedule_policy.py:89`、`:128`、`:69` | reuse_as_is |
| 服务 | `run_tiktok_tool` | `apps/api/src/data_intelligence_hub/services/tiktok_tools.py:480` | reuse_as_is |
| 服务 | `ingest_tiktok_content` | `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py:659` | reuse_as_is |
| 新 HTTP | `POST /api/runs/{run_id}/cancel`、`GET /api/runs/{run_id}/outcome` | 新建 `modules/execution/routes.py` | new |

**不负责**：

- 不负责工具契约。契约属于 M02。
- 不负责凭据。凭据属于 M03。
- 不负责 claim 与证据等级。属于 M05。
- 不负责报告。属于 M07。
- 不负责成本结算。结算属于 M08。

**状态**：模块级 `extend`。核心执行链 `reuse_as_is`。鉴权、幂等、队列与成本列必须扩展。

**证据**：

- `tests/unit/test_collectors.py`、`tests/unit/test_scheduler.py`、`tests/unit/test_tiktok_tools.py`、`tests/unit/test_tiktok_content_ingestion.py`、`tests/unit/test_collection_timeouts.py`、`tests/unit/test_outbound_scheduling.py` 通过。
- 生产只读：`GET /api/tasks/scheduler/overview` 返回 `scanned=44`。`GET /api/tiktok/tools` 返回 200。
- `execute_collection_task` 是唯一执行入口。调用方为 `scheduler/service.py:22`、`api/routes/quick_collect.py:26`、`services/task_service.py:19`。

**必须修的问题**：

1. `quick_collect` 没有鉴权依赖。见 `apps/api/src/data_intelligence_hub/main.py:95` 与 `api/routes/quick_collect.py:959`。每次新建 `Source`，跨调用不去重。
2. 异步路径使用 `FastAPI BackgroundTasks` 与进程内 session factory。见 `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:943-957`。重启或扩容会丢任务。必须换持久队列，或明确单实例限制。
3. `run_task_now` 的幂等只查 `TaskRun.logs`，没有唯一约束与索引。见 `apps/api/src/data_intelligence_hub/services/task_service.py:86-158`。并发同 key 可能各建一次 run。必须加唯一约束。
4. `TaskRun` 没有 `unit_price`、`total_cost_usd`、`remaining_budget`。见 `apps/api/src/data_intelligence_hub/models/task.py:44-66`。PRD R6 要求三字段非空。必须由 M08 扩列。
5. `normalization_service` 只支持 7 类 `record_type`。见 `apps/api/src/data_intelligence_hub/services/normalization_service.py:64-88`。Apify 的 `amazon_product`、`tiktok_video` 不生成 entity 或 snapshot。M04 必须把未识别类型写入 `raw_records`，并标 `normalization_status=unsupported`。不得静默丢弃。
6. `cron` 只支持分钟/小时步进与每日执行。见 `apps/api/src/data_intelligence_hub/scheduler/cron.py:31-53`。月、日、星期字段被静默跳过。必须返回明确错误。
7. `outbound_policy` 永久拒绝 53 个 collector。见 `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py:62-117`。目录必须隐藏这些类型。不得向下一批承诺。

### 1.6 M05 证据与主张（evidence）

**职责**：把原始记录转成实体、信号、情报、主张与证据。计算证据等级。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `entities` | `Entity` | `apps/api/src/data_intelligence_hub/models/entity.py:20` | 实体。 |
| `entity_snapshots` | `EntitySnapshot` | `apps/api/src/data_intelligence_hub/models/entity.py:57` | 快照。无租户列。 |
| `signals` | `Signal` | `apps/api/src/data_intelligence_hub/models/signal.py:19` | 信号。 |
| `intelligence_items` | `IntelligenceItem` | `apps/api/src/data_intelligence_hub/models/intelligence.py:22` | 情报。 |
| `evidences` | `Evidence` | `apps/api/src/data_intelligence_hub/models/intelligence.py:51` | 证据。`intelligence_id` 非空。 |
| `intelligence_feedback` | `IntelligenceFeedback` | `apps/api/src/data_intelligence_hub/models/intelligence.py:79` | 反馈。 |
| `claims` | `Claim` | 新建 | 主张。字段见 PRD §5.4.1。 |
| `claim_evidence` | `ClaimEvidence` | 新建 | 多对多。`role` 取 `support`/`counter`/`context`/`gap`。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET /api/entities`、`/{id}`、`/{id}/snapshots`、`/{id}/signals` | `apps/api/src/data_intelligence_hub/api/routes/entities.py:22`、`:44`、`:61`、`:78` | reuse_as_is |
| HTTP | `GET /api/signals`、`/{id}`、`/{id}/snapshot-compare` | `apps/api/src/data_intelligence_hub/api/routes/signals.py:28`、`:52`、`:69` | reuse_as_is |
| HTTP | `GET /api/intelligence`、`/{id}`、`/{id}/evidences` | `apps/api/src/data_intelligence_hub/api/routes/intelligence.py:28`、`:57`、`:97` | reuse_as_is |
| HTTP | `PATCH /api/intelligence/{id}/status`、`POST /api/intelligence/{id}/feedback` | `apps/api/src/data_intelligence_hub/api/routes/intelligence.py:74`、`:129` | reuse_as_is |
| 服务 | `normalize_raw_record` | `apps/api/src/data_intelligence_hub/services/normalization_service.py:32` | extend |
| 服务 | `detect_signals_for_snapshots`、`detect_data_quality_anomaly` | `apps/api/src/data_intelligence_hub/services/signal_service.py:118`、`:153` | extend |
| 服务 | `generate_intelligence_for_signal` | `apps/api/src/data_intelligence_hub/services/intelligence_service.py:128` | extend |
| 服务 | `build_evidences_for_signal` | `apps/api/src/data_intelligence_hub/services/evidence_service.py:13` | reuse_as_is |
| 服务 | `get_entities`、`get_snapshots_for_entity` | `apps/api/src/data_intelligence_hub/services/entity_service.py:17`、`:44` | reuse_as_is |
| 新 HTTP | `GET/POST /api/claims`、`GET/PATCH /api/claims/{claim_id}` | 新建 `modules/evidence/routes.py` | new |
| 新 HTTP | `POST /api/claims/{claim_id}/evidence-links` | 新建 `modules/evidence/routes.py` | new |
| 新服务 | `compute_evidence_grade` | 新建 `modules/evidence/grade.py` | new |

**不负责**：

- 不负责采集。采集属于 M04。
- 不负责报告渲染。属于 M07。
- 不负责发送通知。属于 M11。
- 不负责模板阈值定义。阈值属于 M06。M05 只读取阈值。
- 不拥有 `run_evidence_grades`。该表归 M10 工作台编排拥有。M05 只计算 `grade` 并交给 M10 写入。

**状态**：`extend`。claim 与证据等级必须新建。

**证据**：

- `tests/unit/test_normalization.py`、`tests/unit/test_signals.py`、`tests/unit/test_llm_service.py` 通过。
- 生产只读：`GET /api/signals`、`GET /api/intelligence` 返回真实数据。`GET /api/dashboard/overview` 返回 `intelligence_count=12`。

**必须修的问题**：

1. `normalize_raw_record` 只分派 7 类。见 `apps/api/src/data_intelligence_hub/services/normalization_service.py:64-88`。必须新增 `amazon_product`、`tiktok_video`、`amazon_review` 等映射，或写入 `normalization_status`。
2. `detect_signals_for_snapshots` 只识别 GitHub stars 增长与网页哈希变化。见 `apps/api/src/data_intelligence_hub/services/signal_service.py:252-286`。新品类必须新增规则。
3. `LLMService` 固定使用 `MockLLMAdapter`。见 `apps/api/src/data_intelligence_hub/services/llm_service.py:12`、`:31`。`settings.llm_provider`、`llm_api_key`、`llm_model` 没有读取点。见 `apps/api/src/data_intelligence_hub/core/config.py:31-33`。必须新增真实 adapter，并写入 K0。
4. `evidences.intelligence_id` 非空。见 `apps/api/src/data_intelligence_hub/models/intelligence.py:51-55`。claim 需要独立的 evidence。必须改为可空，或新建 claim 专用证据表。本文选择改可空。
5. `entity_snapshots` 没有 `workspace_id` 与 `project_id`。见 `apps/api/src/data_intelligence_hub/models/entity.py:57-64`。按租户查询必须 join `entities`，或扩列。
6. 证据等级必须由系统计算。禁止由模型声明。计算函数必须放在 M05，阈值读 M06。

### 1.7 M06 模板注册（templates）

**职责**：注册报告模板、章节、证据阈值与禁止输出。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `report_templates` | `ReportTemplate` | 新建 | 模板主表。字段见 PRD §8.6。 |
| `report_template_versions` | `ReportTemplateVersion` | 新建 | 模板版本。章节、阈值、禁止输出按版本冻结。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| 新 HTTP | `GET /api/report-templates` | 新建 `modules/templates/routes.py` | new |
| 新 HTTP | `GET /api/report-templates/{template_id}` | 新建 `modules/templates/routes.py` | new |
| 新 HTTP | `GET /api/report-templates/{template_id}/versions/{version}` | 新建 `modules/templates/routes.py` | new |
| 新 HTTP | `POST /api/report-templates` | 新建 `modules/templates/routes.py` | new |
| 新服务 | `get_template`、`list_templates`、`get_thresholds`、`assert_prohibited_outputs` | 新建 `modules/templates/registry.py`、`modules/templates/thresholds.py` | new |

**不负责**：

- 不负责渲染 HTML。渲染属于 M07。
- 不负责采集与证据。属于 M04 与 M05。
- 不负责模板内容运营。模板内容由产品维护，代码只存注册表。

**状态**：`new`。

**证据**：

- 仓库没有 `report_templates` 表。见 `apps/api/src/data_intelligence_hub/models/` 目录。
- `reports.report_type` 是 `String(20)`，schema 只允许 `daily`。见 `apps/api/src/data_intelligence_hub/schemas/report.py:17-30`。
- PRD §8.6 定义 `ReportTemplate` 字段。Playbook §2–§6 引用该表。

**必须满足的规则**：

1. `prohibited_outputs` 不得为空。最低七条见 PRD §7.4。
2. 章节 ID 必须在 PRD、Playbook、渲染器三处一致。
3. 阈值表必须唯一。PRD §5.4.2 的表是唯一事实源。M05 与 M07 不得复制阈值。
4. 新增模板必须先在注册表登记，再写渲染器。
5. 每个模板必须能跑 2 品牌 × 2 市场。全空报告判失败。

### 1.8 M07 报告生成（reports）

**职责**：用一份合同生成报告与 SOP。存档、导出、分享、发送与订阅。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `reports` | `Report` | `apps/api/src/data_intelligence_hub/models/report.py:16` | 报告。`content` 是 Text。 |
| `report_subscriptions` | `ReportSubscription` | `apps/api/src/data_intelligence_hub/models/report.py:58` | 订阅。 |
| `report_subscription_runs` | `ReportSubscriptionRun` | `apps/api/src/data_intelligence_hub/models/report.py:88` | 订阅运行。 |
| `report_audit_events` | `ReportAuditEvent` | `apps/api/src/data_intelligence_hub/models/report.py:37` | 审计。 |
| `report_artifacts` | `ReportArtifact` | 新建 | 合同 JSON、HTML、SOP、哈希、版本。 |
| `report_shares` | `ReportShare` | 新建 | 分享链接、过期时间、访问审计。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET /api/reports`、`GET /api/reports/{id}` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:54`、`:286` | reuse_as_is |
| HTTP | `POST /api/reports/generate` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:64` | extend |
| HTTP | `POST /api/reports/{id}/send` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:299` | reuse_as_is |
| HTTP | `GET /api/reports/{id}/audit-events`、`POST /api/reports/{id}/audit-events` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:248`、`:261` | reuse_as_is |
| HTTP | `GET /api/reports/{id}/evidence-references` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:211` | reuse_as_is |
| HTTP | `GET/PUT /api/reports/subscriptions`、`POST /subscriptions/{id}/run` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:81`、`:93`、`:111` | reuse_as_is |
| HTTP | `GET /subscriptions/{id}/runs`、`POST .../retry` | `apps/api/src/data_intelligence_hub/api/routes/reports.py:144`、`:167` | reuse_as_is |
| 服务 | `generate_report` | `apps/api/src/data_intelligence_hub/services/report_service.py:647` | extend |
| 服务 | `send_report_with_payload`、`dispatch_report` | `apps/api/src/data_intelligence_hub/services/report_service.py:729`、`:804` | reuse_as_is |
| 服务 | `upsert_report_subscription`、`execute_report_subscription` | `apps/api/src/data_intelligence_hub/services/report_service.py:184`、`:536` | reuse_as_is |
| 服务 | `_render_daily_report` | `apps/api/src/data_intelligence_hub/services/report_service.py:1198` | replace |
| 新 HTTP | `GET /api/reports/{id}/contract`、`GET /api/reports/{id}/artifact` | 新建 `modules/reports/routes.py` | new |
| 新 HTTP | `GET /api/reports/{id}/sop`、`POST /api/reports/{id}/share`、`POST /api/reports/{id}/export` | 新建 `modules/reports/routes.py` | new |
| 新 HTTP | `GET /api/reports/public/{token}`、`POST /api/reports/public/{token}/access` | 新建 `modules/reports/routes.py` | new |

**不负责**：

- 不负责创建 claim。属于 M05。
- 不负责采集。属于 M04。
- 不负责邮件传输。属于 M11。
- 不负责模板定义。属于 M06。

**状态**：`extend`。订阅、发送、审计、幂等可复用。合同、两个渲染器、产物、分享必须新建。

**证据**：

- 生产只读：`GET /api/reports` 返回 200。
- 上一轮清点用内存 SQLite 直连 FastAPI 跑通：`POST /api/reports/generate` 返回 201；`POST /api/reports/{id}/send` 返回 200，`delivered=[in_app]`；同 key 重放返回 `idempotency_replayed=true`；订阅手动执行返回 200 `success`。
- 发送门禁与审计：`apps/api/src/data_intelligence_hub/services/report_service.py:729-872`。

**必须修的问题**：

1. `_render_daily_report` 只输出监控概览、核心发现、预警区三段。见 `apps/api/src/data_intelligence_hub/services/report_service.py:1198-1244`。必须替换为六段式 exhibit 与 11 章骨架。不得复用该函数。
2. `reports.report_type` 只允许 `daily`。见 `apps/api/src/data_intelligence_hub/schemas/report.py:17-30`。必须扩为 `t1_voc` 等五个模板 ID。
3. 没有 `report_artifacts` 与 `report_shares` 表。必须新建。
4. 订阅到期查询没有 `FOR UPDATE`。见 `apps/api/src/data_intelligence_hub/repositories/reports.py:223-241`。计划执行没有幂等键。必须补。
5. 邮件真实发送默认关闭。`email_live_send_enabled=false`。见 `apps/api/src/data_intelligence_hub/core/config.py:41`。生产无邮件发送证据。

### 1.9 M08 额度与审计（metering）

**职责**：记录每次调用。预留、结算、释放成本。执行额度与授权。提供审计。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `tool_calls` | `ToolCall` | 新建 | 统一调用意图与分派。采集类关联 `TaskRun`，不复制状态。 |
| `run_ledger_entries` | `RunLedgerEntry` | 新建 | 预留、执行、结算、释放。 |
| `quota_accounts` | `QuotaAccount` | 新建 | 单次与每日额度。 |
| `authorizations` | `Authorization` | 新建 | 批准人、范围、成本上限、过期时间。 |
| `task_runs.unit_price`、`total_cost_usd`、`remaining_budget` | 扩列 | `apps/api/src/data_intelligence_hub/models/task.py:45` | PRD R6 要求。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| 新 HTTP | `GET /api/ledger/calls`、`GET /api/ledger/calls/{call_id}` | 新建 `modules/metering/routes.py` | new |
| 新 HTTP | `GET /api/quota`、`GET /api/quota/projects/{project_id}` | 新建 `modules/metering/routes.py` | new |
| 新 HTTP | `POST /api/authorizations`、`GET /api/authorizations/{id}`、`POST /api/authorizations/{id}/revoke` | 新建 `modules/metering/routes.py` | new |
| 新 HTTP | `GET /api/audit/events` | 新建 `modules/metering/routes.py` | new |
| 新服务 | `reserve`、`settle`、`release`、`get_remaining` | 新建 `modules/metering/ledger.py` | new |
| 新服务 | `check_quota`、`get_rate_card`、`authorize` | 新建 `modules/metering/quota.py`、`rate_card.py`、`authorization.py` | new |

**不负责**：

- 不负责执行调用。执行属于 M04 与 M09。
- 不负责运行状态。采集状态只由 `TaskRun` 拥有。
- 不负责报告渲染。属于 M07。

**状态**：`new`。现有 `workflow_execution/budget.py` 是 fixture-only，不得复用。

**证据**：

- `workflow_execution/budget.py` 的账本项固定写 `provider_call_attempted=False`。见 `apps/api/src/data_intelligence_hub/services/workflow_execution/budget.py:552`。
- `workflow_runs` router 已挂载（fixture-only）。生产返回 200 且 `execution_mode=fixture`。见 `apps/api/src/data_intelligence_hub/main.py:143`。
- `TaskRun` 没有成本字段。见 `apps/api/src/data_intelligence_hub/models/task.py:44-66`。
- PRD §5.6 与 §5.4.2 定义三种成本口径与 `Authorization` 字段。

**必须满足的规则**：

1. 每次调用必须先预留，再执行，再结算或释放。不得先执行后记账。
2. 非 2xx 必须归零。2xx 空结果按实际调用计费，并在报告标 `gap`。
3. 超额度必须阻断。不得降级。
4. 成本字段必须可读。PRD R6 要求 `unit_price`、`total_cost_usd`、`remaining_budget` 三字段非空。
5. `TaskRun` 只存投影字段。账本真值在 `run_ledger_entries`。不得双写状态。

### 1.10 M09 接入网关（gateway）

**职责**：统一外部入口。解析项目 key，检查工具白名单，检查额度，做幂等与分派。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `project_api_keys` | `ProjectApiKey` | 新建 | 字段见 PRD §5.7。 |
| 无其他业务表 | — | — | 网关不拥有业务数据。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| MCP | `/mcp` | `apps/api/src/data_intelligence_hub/main.py:116` | reuse_as_is |
| MCP | `list_platforms`、`list_capabilities`、`describe_capability`、`get_playbook`、`collect` | `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:55`、`:81`、`:110`、`:123`、`:133` | extend |
| MCP | 8 个 `tiktok_*` 工具 | `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:160-309` | reuse_as_is |
| 新 MCP | `discover`、`inspect`、`get_run`、`list_records`、`create_report` | 新建 `modules/gateway/mcp_tools.py` | new |
| 新 HTTP | `GET/POST /api/project-keys`、`DELETE /api/project-keys/{id}` | 新建 `modules/gateway/routes.py` | new |
| 新服务 | `resolve_project_key`、`assert_tool_allowed`、`dispatch_call` | 新建 `modules/gateway/service.py` | new |

**不负责**：

- 不负责业务逻辑。业务逻辑在 M02/M04/M07/M10。
- 不负责执行采集。属于 M04。
- 不负责生成报告。属于 M07。
- 不负责项目与成员管理。属于 M01。

**状态**：`extend`。MCP 13 个工具可复用。项目 key 与统一调用门必须新建。

**证据**：

- `tests/unit/test_mcp_runtime.py`、`test_mcp_auth.py`、`test_mcp_governance.py`、`test_mcp_transport_security.py` 通过。
- 生产只读：`GET /api/tiktok/tools` 返回 200。MCP 13 个工具名可读。
- 13 个工具注册位置：`apps/api/src/data_intelligence_hub/mcp_runtime/server.py:55-309`。

**必须修的问题**：

1. `SCRAPY_MCP_TOKEN` 与 `SCRAPY_MCP_TOKENS_JSON` 都为空时，`BearerTokenMiddleware` 直接放行。见 `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py:20-23`。生产必须配 token。网关必须 fail-closed。
2. MCP 限额保存在进程内 `defaultdict`。见 `apps/api/src/data_intelligence_hub/mcp_runtime/governance.py:54-86`。重启清零，多 worker 不共享。必须落库或明确单实例。
3. `allowed_hosts` 只含 `scrapy.luteos.com`、`127.0.0.1`、`localhost`、`test`。见 `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:35-52`。第二套生产域名不在列表。必须加 host 或写明不支持。
4. 没有项目 key。只有全局 token。必须新建 `project_api_keys` 与中间件。
5. `collect` 无 Idempotency-Key。见 `apps/api/src/data_intelligence_hub/mcp_runtime/collect_service.py:13-24`。必须补幂等。

### 1.11 M10 工作台编排（workbench）

**职责**：把七槽位任务单变成计划、门禁与执行序列。汇总工作台读模型。

**拥有或使用的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `workbench_tasks` | `WorkbenchTask` | 新建 | 七槽位任务单、决策问题、owner、状态；不记录执行状态。由 M10 工作台编排拥有。 |
| `runs` | `Run` | 新建 | 一次执行运行，一份计划执行一次；有 `plan_id`、`plan_version`、`authorization_id`，不存七槽位。由 M10 工作台编排拥有。 |
| `run_steps` | `RunStep` | 新建 | 执行步骤，含 `step_index`、`tool_id`、`endpoint_type`、`collector_type`、`task_run_id`、状态与成本；不存计划正文。由 M10 工作台编排拥有。 |
| `run_evidence_grades` | `RunEvidenceGrade` | 新建 | 每次运行的证据等级。由 M10 工作台编排拥有；`grade` 由 M05 计算。 |
| `authorizations` | `Authorization` | 新建 | G-Plan、G-Cost、G-Evidence、G-Claim、G-Publish。由 M08 额度与审计拥有，M10 只读。 |
| `workflow_plans`、`workflow_versions`、`monitoring_scopes`、`query_terms` | 见模型 | `apps/api/src/data_intelligence_hub/models/workflow_plan.py:35`、`:136`、`:227`、`:325` | planner 持久化。 |
| `workflow_templates`、`workflow_template_revisions`、`monitoring_scope_templates` | 见模型 | `apps/api/src/data_intelligence_hub/models/workflow_template.py:26`、`:85`；`apps/api/src/data_intelligence_hub/models/workflow_scope_template.py:26` | 计划模板。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `POST /api/projects/{project_id}/workflow-plans/preview` | `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:501` | reuse_as_is |
| HTTP | `POST /api/projects/{project_id}/workflow-plans` | `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:606` | reuse_as_is |
| HTTP | `GET /api/projects/{project_id}/workflow-plans`、`/{plan_id}` | `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:778`、`:805` | reuse_as_is |
| HTTP | `POST /{plan_id}/versions`、`GET /{plan_id}/versions`、`GET /{plan_id}/version-compare` | `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:742`、`:830`、`:859` | reuse_as_is |
| 服务 | `build_workflow_plan_result` | `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py:477` | reuse_as_is |
| 服务 | `resolve_route_plans` | `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py:67` | reuse_as_is |
| 新 HTTP | `POST /api/workbench/tasks`、`GET /api/workbench/tasks`、`GET /api/workbench/tasks/{id}` | 新建 `modules/workbench/routes.py` | new |
| 新 HTTP | `POST /api/workbench/plans/preview`、`PATCH /api/workbench/plans/{plan_id}`（⚠ 待登记：仅 PATCH） | 新建 `modules/workbench/routes.py` | new |
| 新 HTTP | `POST /api/workbench/plans/{plan_id}/approve` | 新建 `modules/workbench/routes.py` | new |
| 新 HTTP | `POST /api/runs`、`POST /api/runs/{run_id}/cancel` | 新建 `modules/workbench/routes.py` | new |
| 新 HTTP | `GET /api/workbench/tasks/{id}/gates`、`POST .../gates/{gate_id}/decide` | 新建 `modules/workbench/routes.py` | new |
| 新 HTTP | `GET /api/workbench/overview` | 新建 `modules/workbench/routes.py` | new |
| 服务 | `get_dashboard_overview` | `apps/api/src/data_intelligence_hub/services/dashboard_service.py:39` | extend |

**不负责**：

- 不负责采集内核。必须调用 M04 的 `execute_collection_task`。
- 不负责 claim 与证据等级。属于 M05。
- 不负责报告渲染。属于 M07。
- 不负责成本结算。属于 M08。
- 不负责外部接入。属于 M09。

**状态**：编排层 `new`。planner 解析器 `reuse_as_is`。`workflow_execution` 是 fixture-only，禁止复用。

**证据**：

- `tests/unit/test_workflow_planner_resolver.py`、`test_workflow_planner.py`、`test_workflow_plan_persistence.py`、`test_workflow_plan_lifecycle.py` 通过。
- 生产只读：`GET /api/projects/{id}/workflow-plans` 返回 200。
- `workflow_plans` router 已挂载。见 `apps/api/src/data_intelligence_hub/main.py:97`。

**必须修的问题**：

1. 默认 catalog 的 35 条 assertion 全是 `candidate`。resolver 一律拒绝。preview 全部 `held`。必须先完成 M02 的 catalog 发布。
2. `candidate_expansion` 只有 fixture adapter。见 `apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py:17-19`。必须新增真实语义扩展，或明确由用户输入关键词。
3. `execution_authorized` 恒为 `False`。见 `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py:570`。M10 必须新建执行授权层。不得改这个常量来伪装。
4. `workflow_execution` 执行层是 fixture-only；`workflow_runs` router 已挂载，生产返回 200 且 `execution_mode=fixture`。`schemas/workflow_execution.py:55-59` 固定 `execution_mode=fixture`、`live_execution_authorized=False`。必须另建执行层。
5. `POST /api/projects` 的 `user=None` 问题会影响任务单归属。见 §1.2。

### 1.12 M11 告警与通知（notify）

**职责**：匹配预警规则。创建预警事件。发送站内信与邮件。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `alert_rules` | `AlertRule` | `apps/api/src/data_intelligence_hub/models/alert.py:17` | 规则。 |
| `alert_events` | `AlertEvent` | `apps/api/src/data_intelligence_hub/models/alert.py:37` | 事件。 |
| `notifications` | `Notification` | `apps/api/src/data_intelligence_hub/models/notification.py:16` | 站内信。 |
| `email_channel_test_runs` | `EmailChannelTestRun` | `apps/api/src/data_intelligence_hub/models/notification.py:35` | 邮件测试。 |
| `email_provider_live_gate_runs` | `EmailProviderLiveGateRun` | `apps/api/src/data_intelligence_hub/models/notification.py:57` | 实发门禁。 |
| `email_provider_live_send_runs` | `EmailProviderLiveSendRun` | `apps/api/src/data_intelligence_hub/models/notification.py:86` | 实发记录。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET/POST /api/alert-rules`、`PATCH/DELETE /api/alert-rules/{id}` | `apps/api/src/data_intelligence_hub/api/routes/alerts.py:34`、`:48`、`:69`、`:89` | reuse_as_is |
| HTTP | `GET /api/alert-events`、`PATCH /{id}/status` | `apps/api/src/data_intelligence_hub/api/routes/alerts.py:106`、`:126` | reuse_as_is |
| HTTP | `GET /api/notifications`、`PATCH /{id}/read`、`POST /read-all`、`/read-bulk` | `apps/api/src/data_intelligence_hub/api/routes/notifications.py:48`、`:169`、`:182`、`:191` | reuse_as_is |
| HTTP | `GET /api/notifications/email-channel`、`POST /email-channel/test` | `apps/api/src/data_intelligence_hub/api/routes/notifications.py:58`、`:66` | reuse_as_is |
| HTTP | `POST /email-channel/provider-live-gate`、`/live-send` | `apps/api/src/data_intelligence_hub/api/routes/notifications.py:90`、`:135` | reuse_as_is |
| 服务 | `match_alert_rules_for_signal` | `apps/api/src/data_intelligence_hub/services/alert_service.py:133` | reuse_as_is |
| 服务 | `create_in_app_notification`、`send_email_notification` | `apps/api/src/data_intelligence_hub/services/notification_service.py:160`、`:603` | reuse_as_is |

**不负责**：

- 不负责信号检测。属于 M05。
- 不负责报告生成。属于 M07。
- 不负责外部邮件服务运维。只负责门禁与调用。

**状态**：`reuse_as_is`。

**证据**：

- 生产只读：`GET /api/dashboard/overview` 返回 `active_alerts=8`。通知路由已挂载。见 `apps/api/src/data_intelligence_hub/main.py:105-107`。
- 邮件门禁：`email_live_send_enabled=false` 默认拒绝。见 `apps/api/src/data_intelligence_hub/core/config.py:41`。
- 上一轮清点：站内发送成功。邮件在 SMTP 未配置时自动跳过。

**必须修的问题**：

1. 邮件真实发送没有生产证据。必须保持默认关闭，直到配置 SMTP 与 allowlist。
2. 预警规则没有 UI。PRD 页面未列入 M11 的独立页面。规则入口必须放在 `/settings`。
3. 报告发送必须通过 M11，不得在 M07 直接调用 SMTP。

### 1.13 M12 数据集与产物（assets）

**职责**：管理数据集、版本、清洗计划、漂移事件与导出。

**拥有的数据**：

| 表 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| `datasets` | `Dataset` | `apps/api/src/data_intelligence_hub/models/dataset.py:32` | 数据集。 |
| `cleaning_plans` | `CleaningPlan` | `apps/api/src/data_intelligence_hub/models/dataset.py:58` | 清洗计划。 |
| `dataset_versions` | `DatasetVersion` | `apps/api/src/data_intelligence_hub/models/dataset.py:88` | 版本。 |
| `dataset_drift_events` | `DatasetDriftEvent` | `apps/api/src/data_intelligence_hub/models/dataset.py:161` | 漂移。 |
| `dataset_export_jobs` | `DatasetExportJob` | `apps/api/src/data_intelligence_hub/models/dataset.py:186` | 导出。 |

**对外接口**：

| 类型 | 入口 | 位置 | 状态 |
| --- | --- | --- | --- |
| HTTP | `GET /api/automation/product-datasets`、`DELETE /{dataset_id}` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:1292`、`:1319` | reuse_as_is |
| HTTP | `GET /product-datasets/{dataset_id}/versions`、`.../preview` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:1340`、`:1364` | reuse_as_is |
| HTTP | `POST /product-dataset-exports`、`GET /product-dataset-exports/{id}` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:1390`、`:1415` | reuse_as_is |
| HTTP | `GET /product-datasets/{dataset_id}/exports`、`.../download` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:1433`、`:1459` | reuse_as_is |
| HTTP | `POST /cleaning-plans`、`GET /cleaning-plans` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:814`、`:834` | reuse_as_is |
| HTTP | `POST /product-drift-check`、`GET /product-drift-events` | `apps/api/src/data_intelligence_hub/api/routes/automation.py:937`、`:1027` | reuse_as_is |
| 服务 | `list_product_datasets`、`create_product_dataset_export` | `apps/api/src/data_intelligence_hub/services/automation_service.py:4856`、`:4992` | reuse_as_is |
| 服务 | `save_product_dataset_version`、`check_product_drift` | `apps/api/src/data_intelligence_hub/services/automation_service.py:3084`、`:3449` | reuse_as_is |

**不负责**：

- 不负责采集。属于 M04。
- 不负责报告渲染。属于 M07。
- 不负责 claim 与证据。属于 M05。

**状态**：模块级 `extend`。数据集与导出的现有接口可用。必须拆出独立服务，并解耦 `workflow_runs`。

**证据**：

- 生产只读：`GET /api/automation/product-datasets` 返回 200。
- 生产控制台 `/datasets` 标 live。见 `apps/scraper-console/src/app/datasets/page.tsx`。
- `tests/unit/test_automation_service.py` 通过。

**必须修的问题**：

1. `dataset_versions` 有复合外键指向 `workflow_runs`。见 `apps/api/src/data_intelligence_hub/models/dataset.py:88-131`。`source_workflow_run_id` 已可空，但有 `CheckConstraint` 要求四个 lineage 字段同时为空或同时非空。`workflow_runs` 是已挂载的 fixture-only 表。必须停止新增依赖。迁移时必须移除该复合外键，或把 lineage 迁到独立表。
2. 数据集与导出逻辑在 `automation_service.py`。该文件 13,537 行、335 个函数。必须拆到 `modules/assets/service.py`。不得继续扩该文件。
3. 导出下载无鉴权证据。必须纳入 M09 的门。

## 2. 模块依赖图

### 2.1 允许的依赖

箭头 `A ──> B` 表示 A 可以 import B 或调用 B 的公开服务。箭头只向下。

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 第 6 层  ［外部入口］                                                       │
│                                                                             │
│                        ┌──────────────────────────┐                         │
│                        │ M09 接入网关             │                         │
│                        └────────────┬─────────────┘                         │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│ 第 5 层  ［编排］                   v                                       │
│                        ┌──────────────────────────┐                         │
│                        │ M10 工作台编排           │                         │
│                        └────────────┬─────────────┘                         │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│ 第 4 层  ［交付］                   v                                       │
│         ┌──────────────────┐   ┌──────────────────┐                         │
│         │ M07 报告生成     │   │ M12 数据集与产物 │                         │
│         └───┬────┬────┬────┘   └────────┬─────────┘                         │
└─────────────┼────┼────┼─────────────────┼───────────────────────────────────┘
              │    │    │                 │
┌─────────────┼────┼────┼─────────────────┼───────────────────────────────────┐
│ 第 3 层     v    │    v                 v                                   │
│         ┌──────────────────┐   ┌──────────────────┐                         │
│         │ M11 告警与通知   │   │ M04 采集执行     │                         │
│         └────────┬─────────┘   └───┬────┬────┬────┘                         │
└──────────────────┼─────────────────┼────┼────┼──────────────────────────────┘
                   │                 │    │    │
┌──────────────────┼─────────────────┼────┼────┼──────────────────────────────┐
│ 第 2 层          v                 v    │    v                              │
│         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│         │ M05 证据与主张   │  │ M03 连接器与凭据 │  │ M08 额度与审计   │    │
│         └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘    │
└──────────────────┼─────────────────────┼─────────────────────┼──────────────┘
                   │                     │                     │
┌──────────────────┼─────────────────────┼─────────────────────┼──────────────┐
│ 第 1 层          v                     v                     v              │
│         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│         │ M06 模板注册     │  │ M02 目录与发现   │  │ M01 身份与租户   │    │
│         └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘    │
└──────────────────┼─────────────────────┼─────────────────────┼──────────────┘
                   │                     │                     │
┌──────────────────┼─────────────────────┼─────────────────────┼──────────────┐
│ 第 0 层          v                     v                     v              │
│         ┌──────────────────────────────────────────────────────────┐        │
│         │ K0 共享内核（core、models/base、exceptions、LLM adapter）│        │
│         └──────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

图为分层示意。完整依赖边以 §2.2 的清单为准。图只画主要边。M09 到 M02、M04、M07、M08 的边未画出，但清单已登记。

### 2.2 依赖清单

| 模块 | 允许依赖 | 说明 |
| --- | --- | --- |
| M01 身份与租户 | K0 | 只依赖核心库。 |
| M02 目录与发现 | M01、K0 | 目录只读身份上下文。 |
| M03 连接器与凭据 | M01、M02、K0 | 凭据按项目解析。就绪度读目录契约。 |
| M04 采集执行 | M01、M02、M03、M05、M08、K0 | 执行前解析契约与凭据。执行后调用证据管线与账本。 |
| M05 证据与主张 | M01、M06、K0 | 阈值读模板注册表。不读执行表。 |
| M06 模板注册 | M01、K0 | 不依赖其他业务模块。 |
| M07 报告生成 | M01、M04、M05、M06、M08、M11、K0 | 读运行事实、claim、模板、账本。发送交给 M11。 |
| M08 额度与审计 | M01、M02、K0 | 读目录 rate card。 |
| M09 接入网关 | M01、M02、M04、M07、M08、M10、K0 | 只做入口与分派。 |
| M10 工作台编排 | M01、M02、M03、M04、M05、M06、M07、M08、M11、M12、K0 | 组合根。 |
| M11 告警与通知 | M01、M05、K0 | 读信号与情报。不读报告。 |
| M12 数据集与产物 | M01、M04、K0 | 读原始记录与运行。 |

### 2.3 禁止的依赖

| 禁止边 | 理由 |
| --- | --- |
| M02 → M03、M04、M05、M07、M08、M09、M10、M11、M12 | 目录是叶子。它不知道消费方。 |
| M03 → M04、M05、M07、M08、M09、M10、M11、M12 | 连接器只服务执行。 |
| M06 → M02、M03、M04、M05、M07、M08、M09、M10、M11、M12 | 模板注册表是叶子。 |
| M04 → M07、M09、M10、M11、M12 | 执行不得生成报告、不得做入口、不得编排。 |
| M05 → M04、M07、M08、M09、M10、M11、M12 | 证据层不得读执行表。运行事实由 M04 以 DTO 传入。 |
| M08 → M04、M05、M07、M09、M10、M11、M12 | 账本不得拥有运行状态。 |
| M12 → M07、M09、M10、M11 | 数据集不得生成报告或做入口。 |
| M11 → M07、M04、M09、M10、M12 | 通知不得反向依赖报告或执行。 |
| M07 → M09、M10、M12 | 报告不得做入口或编排。 |
| M10 → M09 | 工作台不得调用网关。网关调用工作台。 |
| 任何模块 → `workflow_execution` | 该包是 fixture-only；`workflow_runs` 路由已挂载，只返回 fixture 数据。 |
| 任何模块 → `api.routes` | 业务层不得 import HTTP 层。 |
| 任何模块 → 其他模块的 `models.py` 或 `repository.py` | 只能读公开 DTO 或调用公开服务。 |

### 2.4 依赖图的使用规则

1. 新增依赖必须在本文 §2.2 登记。未登记不得合并。
2. 依赖方向不得反转。反转必须改设计，不得加 `# noqa`。
3. 跨模块只允许三种方式：公开服务、DTO、领域事件。见 §8.2。
4. 组合根只有两个：M10 与 M09。其他模块不得做跨模块聚合。
5. 边界测试必须落在 `apps/api/tests/unit/test_module_boundaries.py`。测试必须用 AST 扫描 import。

## 3. 模块接口清单

### 3.1 通用约定

| 项 | 规则 |
| --- | --- |
| 基路径 | HTTP 接口统一在 `/api` 下。MCP 在 `/mcp`。 |
| 认证 | 浏览器用 `access_token` cookie。程序用 `X-Project-Key`。两者都必须经 M09 或 M01 校验。 |
| 租户 | 每个请求必须解析出 `workspace_id` 与 `project_id`。缺失返回 401 或 403。 |
| 幂等 | 所有写操作接受 `Idempotency-Key` 头。同 key 不同参数返回 409 `idempotency_conflict`。 |
| 分页 | `limit` 默认 50，最大 200。`offset` 默认 0。响应带 `total`。 |
| 时间 | ISO 8601 UTC。字段后缀 `_at`。 |
| 错误体 | 必须为 `{"detail": "<snake_case_code>"}`。禁止返回堆栈。 |
| 请求 ID | 响应头必须带 `X-Request-Id`。日志必须记录。 |

通用错误码：

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | `invalid_request` | 参数不合法。 |
| 401 | `authentication_required` | 无有效会话或 key。 |
| 403 | `permission_denied` | 角色不足或跨项目。 |
| 404 | `<resource>_not_found` | 资源不存在。 |
| 409 | `idempotency_conflict` | 幂等键冲突。 |
| 409 | `state_conflict` | 状态不允许当前动作。 |
| 422 | `contract_validation_failed` | 契约或 schema 校验失败。 |
| 429 | `quota_exceeded` | 额度耗尽。 |
| 429 | `rate_limited` | 速率超限。 |
| 502 | `provider_call_failed` | 上游调用失败。 |
| 503 | `provider_not_configured` | 凭据或 grant 缺失。 |
| 503 | `demo_workspace_unavailable` | 演示工作区缺失。 |

说明：

- 现有路由的 `detail` 文本不完全统一。新路由必须使用上表。
- 现有路由可以保留旧文本。迁移时逐步改为 snake_case。
- 采集类运行失败不返回 5xx。同步 quick-collect 返回 201，`status=failed`。异步 run 通过 `GET /api/runs/{id}/outcome` 读取。

### 3.2 M01 身份与租户接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | `email`、`password`、`name` | `user{id,email,name,status}`、`workspace{id,slug}` | 409 `email_already_registered`、422 `invalid_request` |
| POST | `/api/auth/login` | `email`、`password` | `user`、`workspace`、`Set-Cookie: access_token` | 401 `invalid_credentials` |
| POST | `/api/auth/logout` | 无 | 204 | 401 `authentication_required` |
| GET | `/api/auth/me` | 无 | `user`、`workspace` | 401 `authentication_required` |
| GET | `/api/projects` | `domain`、`status` | `items[]{id,name,domain,status,owner_id}` | 401 |
| POST | `/api/projects` | `name`、`description`、`domain` | `ProjectResponse` | 401、404 `workspace_not_found`、422 |
| GET | `/api/projects/{project_id}` | 路径参数 | `ProjectResponse` | 404 `project_not_found`、403 `project_scope_denied` |
| PATCH | `/api/projects/{project_id}` | `name`、`description`、`domain`、`status` | `ProjectResponse` | 404、403、422 |
| DELETE | `/api/projects/{project_id}` | 路径参数 | 归档后的 `ProjectResponse` | 404、403 |
| GET | `/api/workspaces/{workspace_id}/members` | 路径参数 | `items[]{user_id,name,email,role}` | 401、403 |
| POST | `/api/workspaces/{workspace_id}/members` | `email`、`role` | `member` | 404 `user_not_found`、409 `member_exists` |
| PATCH | `/api/workspaces/{workspace_id}/members/{user_id}` | `role` | `member` | 404、403 `role_required` |

接口来源：

- 前 9 行来自现有路由。见 `apps/api/src/data_intelligence_hub/api/routes/auth.py:26-69` 与 `api/routes/projects.py:28-97`。
- 后 3 行是 `new`。成员与角色表当前不存在。

### 3.3 M02 目录与发现接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/tools` | `q`、`category`、`market`、`content_type`、`max_unit_price`、`health_status`、`verified_within_days`、`limit`、`offset` | `items[]{tool_id,display_name,provider,endpoint_type,category,markets,cost_model,risk_level,max_evidence_grade,health_status,verified_at,p50_latency_ms}`、`total` | 422 `invalid_request` |
| GET | `/api/tools/{tool_id}` | 路径参数 | 完整 `ToolContract`、`input_schema`、`output_schema`、`last_records_count`、`last_run_id`、`why_this` | 404 `tool_not_found` |
| GET | `/api/tools/discover` | `q`、`markets`、`limit` | `items[]{tool_id,display_name,category,cost_estimate,health,p50_ms,verified_at,content_types,why_this}` | 422 `invalid_request`、503 `catalog_unavailable` |
| GET | `/api/tools?facet=category` | 无 | `items[]{category,label,tool_count}` | 503 |
| GET | `/api/capabilities/matrix` | `platform` | `schema_version`、`rows[]` | 200 现有 |
| GET | `/api/capabilities/assertions` | `platform`、`implementation_id` | `items[]` | 200 现有 |
| GET | `/api/capabilities/implementations` | `platform` | `items[]` | 200 现有 |
| GET | `/api/capabilities/implementations/{id}` | 路径参数 | `implementation` | 404 `implementation_not_found` |
| GET | `/api/collectors/catalog` | `platform` | 旧端点目录。过渡期返回 `tool_catalog` 投影 | 410 `endpoint_retired`（迁移完成后） |
| GET | `/api/collectors/docs` | `collector_type` | 参数与最近测试 | 404 `collector_not_found` |
| GET | `/api/platform-packages` | `platform` | 平台包目录 | 200 现有 |
| GET | `/api/platform-packages/{platform_id}` | 路径参数 | `PlatformPackage` | 404 `platform_not_found` |
| GET | `/api/platform-packages/{platform_id}/playbook` | 路径参数 | playbook 文本 | 404 |
| GET | `/api/toolkit` | 无 | 工具、方法、学习路径 | 200 现有 |
| GET | `/api/toolkit/method-card-drafts` | `status` | 草稿列表 | 200 现有 |
| POST | `/api/toolkit/method-card-drafts` | `report`、`status` | 草稿 | 422 |

字段规则：

1. `tool_id` 必须按 PRD 规则生成：`{provider}.{endpoint_type}.{market_scope}`。禁止手填。
2. `cost_model` 必须含 `currency`、`unit`、`unit_price`、`min_charge`、`free_tier`、`quantity_basis`、`estimate_formula`、`source_url`、`updated_at`。
3. `max_evidence_grade` 是工具上限。它不是本次运行等级。
4. 目录条目必须可执行。不能执行的条目必须标 `execution_kind=unsupported` 并隐藏。
5. `GET /api/collectors/catalog` 必须与 `/api/tools` 返回同一组 `tool_id`。迁移完成前双读。见 PRD §11.5.3。

### 3.4 M03 连接器与凭据接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/connectors` | `project_id`、`market`、`status` | `items[]{connector_id,provider,platform,auth_mode,credential_status,grant_status,health_status,last_checked_at}` | 401 |
| GET | `/api/connectors/{connector_id}` | 路径参数 | `connector`、`required_fields[]`、`supported_endpoints[]`、`policy_flags[]` | 404 `connector_not_found` |
| POST | `/api/connectors/{connector_id}/probe` | `project_id`、`url`（可选） | `probe{status,dns_ok,http_status,robots_ok,grant_ok,latency_ms,document_preview}` | 403 `grant_missing`、422 `url_invalid`、503 `provider_not_configured` |
| GET | `/api/settings/platform-credentials` | `project_id`（可选） | `items[]{platform,provider,fields[]{key,label,masked_value,configured},vault_write_enabled}` | 401、403 |
| PUT | `/api/settings/platform-credentials/{platform}` | `project_id`（可选）、`credentials{key:value}` | 更新后的设置 | 403 `vault_write_disabled`、422 `credential_invalid` |
| DELETE | `/api/settings/platform-credentials/{platform}` | `project_id`（可选） | 删除后的设置 | 404 `credential_not_found` |
| GET | `/api/automation/social-provider-catalog` | `platform` | `items[]{provider,platform,sdks,capabilities,policy_flags}` | 200 现有 |
| POST | `/api/automation/social-provider-readiness` | `platform`、`provider_id`、`endpoints[]` | `readiness{ready,missing[],blockers[]}` | 422 |
| POST | `/api/automation/social-provider-gate` | `platform`、`provider_id`、`endpoints[]`、`budget` | `gate{allowed,reasons[],budget}` | 403 `provider_gate_denied` |
| POST | `/api/automation/site-analysis` | `url`、`project_id` | `site_analysis{id,status,plan}` | 422、503 |
| GET | `/api/automation/site-analyses` | `project_id` | `items[]` | 200 现有 |
| POST | `/api/automation/browser-automation-plans` | `site_analysis_id`、`fields[]` | `plan` | 200 现有 |
| POST | `/api/toolkit/preflight` | `url` | `report{status,final_url,title,collector_recommendation,issues[],network[]}` | 422 `url_invalid`、403 `grant_missing` |

字段规则：

1. 凭据返回必须脱敏。只返回 `masked_value` 与 `configured`。禁止返回密文或明文。
2. `PUT` 与 `DELETE` 必须写审计。审计表归 M08。
3. 项目级凭据优先。缺失时回退工作区级。回退必须记录日志。
4. `probe` 必须经过 `outbound_policy` 的 host grant 检查。当前 `toolkit_preflight_service` 没有走该检查。见 `apps/api/src/data_intelligence_hub/services/toolkit_preflight_service.py:115-145`。必须补。
5. 浏览器诊断在生产不可用。`browser_structure_diagnostic` 是 `dead`。必须隐藏该入口，或明确标注“仅本地”。

### 3.5 M04 采集执行接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| POST | `/api/quick-collect` | `project_id`、`endpoint_type`、`params`、`label` | `task_run_id`、`task_id`、`source_id`、`status`、`records_count`、`error_message` | 400 `collector_config_invalid`、403 `collection_policy_denied`、404 `project_not_found`、409 `task_already_running`、429 `quota_exceeded` |
| POST | `/api/quick-collect/async` | 同上 | `task_id`、`source_id`、`status=queued` | 同上 |
| GET | `/api/sources` | `project_id`、`type` | `items[]` | 401 |
| POST | `/api/sources` | `project_id`、`name`、`type`、`url`、`config`、`schedule_cron` | `SourceResponse` | 400 `collector_not_found`、404 `project_not_found` |
| GET | `/api/sources/{source_id}` | 路径参数 | `SourceResponse` | 404 `source_not_found` |
| PATCH | `/api/sources/{source_id}` | `name`、`url`、`config`、`schedule_cron` | `SourceResponse` | 404、400 |
| POST | `/api/sources/{source_id}/test` | 无 | `status`、`collector_type`、`message` | 404、400 |
| POST | `/api/sources/{source_id}/enable` | 无 | `CollectionTaskResponse` | 404、409 |
| POST | `/api/sources/{source_id}/disable` | 无 | `SourceResponse` | 404 |
| GET | `/api/tasks` | `project_id`、`status` | `items[]{id,name,collector_type,status,schedule_cron,latest_run_status,next_run_at}` | 401 |
| GET | `/api/tasks/runs` | `project_id`、`task_id`、`status`、`limit`、`offset` | `items[]{id,task_id,status,records_count,entities_count,started_at,finished_at}` | 401 |
| GET | `/api/tasks/scheduler/overview` | 无 | `scanned`、`due`、`started`、`errors`、`lease_owner`、`latest_tick_at` | 503 `scheduler_unavailable` |
| POST | `/api/tasks/{task_id}/run` | Header `Idempotency-Key` | `TaskRunResponse` | 404、409 `task_already_running`、422 `task_not_runnable` |
| POST | `/api/tasks/{task_id}/pause` | 无 | `CollectionTaskResponse` | 404、409 |
| POST | `/api/tasks/{task_id}/resume` | 无 | `CollectionTaskResponse` | 404、409 |
| GET | `/api/tasks/{task_id}/runs` | `limit`、`offset` | `items[]` | 404 |
| GET | `/api/raw-records` | `project_id`、`task_run_id`、`record_type`、`limit`、`offset` | `items[]{id,record_type,source_url,collected_at,content_hash}` | 401 |
| GET | `/api/raw-records/{raw_record_id}` | 路径参数 | `RawRecordResponse` | 404 `raw_record_not_found` |
| GET | `/api/tiktok/tools` | 无 | `items[]{tool_id,name,description}` | 200 现有 |
| POST | `/api/tiktok/tools/{tool_id}` | `params`、`project_id` | `tool result` | 404 `tool_not_found`、422、429 |
| POST | `/api/runs/{run_id}/cancel` | 无 | `run{id,status}` | 404 `run_not_found`、409 `run_not_cancellable` |
| GET | `/api/runs/{run_id}/outcome` | 无 | `status`、`outcome{success,empty,config_gated,failed}`、`records_count`、`error_code`、`source_count` | 404 |

字段规则：

1. `outcome` 必须取四态之一。见 Playbook §1.4。`health_status` 与 `outcome` 不得互相替代。
2. 同步 quick-collect 的 `status=failed` 是成功响应。不是 HTTP 5xx。
3. 每次 quick-collect 必须写 `execution_origin=quick_collect`。见 `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:860-940`。
4. 新建 `Source` 前必须检查同项目同端点是否已有可复用源。当前每次新建。见 `apps/api/src/data_intelligence_hub/api/routes/quick_collect.py:973-1000`。必须改为复用或显式标记一次性。
5. `Idempotency-Key` 必须加唯一约束。当前只写日志。见 §1.5。

### 3.6 M05 证据与主张接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/entities` | `project_id`、`entity_type`、`limit`、`offset` | `items[]{id,entity_type,name,domain,latest_snapshot_id}` | 401 |
| GET | `/api/entities/{entity_id}` | 路径参数 | `EntityResponse` | 404 `entity_not_found` |
| GET | `/api/entities/{entity_id}/snapshots` | `limit`、`offset` | `items[]{id,captured_at,metrics}` | 404 |
| GET | `/api/entities/{entity_id}/signals` | `limit`、`offset` | `items[]{id,signal_type,severity,delta,delta_ratio,detected_at}` | 404 |
| GET | `/api/signals` | `project_id`、`signal_type`、`severity`、`limit`、`offset` | `items[]` | 401 |
| GET | `/api/signals/{signal_id}` | 路径参数 | `SignalResponse` | 404 `signal_not_found` |
| GET | `/api/signals/{signal_id}/snapshot-compare` | 路径参数 | `previous`、`current`、`diff` | 404、409 `snapshot_compare_not_available` |
| GET | `/api/intelligence` | `project_id`、`status`、`domain`、`limit`、`offset` | `items[]{id,title,summary,intelligence_type,status,final_score,domain}` | 401 |
| GET | `/api/intelligence/{intelligence_id}` | 路径参数 | `IntelligenceResponse` | 404 `intelligence_not_found` |
| PATCH | `/api/intelligence/{intelligence_id}/status` | `status` | `IntelligenceResponse` | 404、422 |
| GET | `/api/intelligence/{intelligence_id}/evidences` | 路径参数 | `items[]{id,evidence_type,url,excerpt,raw_record_id}` | 404 |
| POST | `/api/intelligence/{intelligence_id}/feedback` | `feedback_type`、`comment` | `feedback` | 404、422 |
| GET | `/api/claims` | `task_id`、`claim_status`、`evidence_grade`、`limit`、`offset` | `items[]{claim_id,text,claim_status,evidence_grade,scope}` | 401 |
| POST | `/api/claims` | `task_id`、`text`、`claim_status`、`scope{market,window,sample_n}`、`counterevidence_text`、`owner` | `ClaimResponse` | 422 `contract_validation_failed`、404 `task_not_found` |
| GET | `/api/claims/{claim_id}` | 路径参数 | `ClaimResponse`、`evidence_ids[]` | 404 `claim_not_found` |
| PATCH | `/api/claims/{claim_id}` | `text`、`claim_status`、`counterevidence_text`、`owner` | `ClaimResponse` | 404、409 `claim_status_conflict`、422 `evidence_grade_insufficient` |
| POST | `/api/claims/{claim_id}/evidence-links` | `evidence_id`、`role` | `link{claim_id,evidence_id,role}` | 404、409 `evidence_link_exists`、422 `role_invalid` |
| DELETE | `/api/claims/{claim_id}/evidence-links/{evidence_id}` | 路径参数 | 204 | 404 |
| GET | `/api/claims/{claim_id}/evidences` | 路径参数 | `items[]{evidence_id,role,url,excerpt,evidence_grade}` | 404 |
| GET | `/api/evidence-grades/{run_id}` | 路径参数 | `RunEvidenceGrade` 全字段 | 404 `run_not_found` |

字段规则：

1. `claim_status` 只能取 `confirmed`、`directional`、`hypothesis`、`evidence_gap`、`blocked`。
2. `evidence_grade` 只能取 `L0_unverified` 到 `L4_authorized_live`。必须由系统计算。
3. 每条 claim 至少 1 条 evidence。只有 `gap` 时，状态必须是 `hypothesis` 或 `blocked`。
4. `counterevidence_text` 必填。允许写“未发现反证”。
5. `role` 只能取 `support`、`counter`、`context`、`gap`。
6. 证据等级上限由 M06 的模板阈值决定。M05 不得写死阈值。

### 3.7 M06 模板注册接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/report-templates` | `task_type`、`active`、`limit`、`offset` | `items[]{template_id,version,title,sections,gates}` | 401 |
| GET | `/api/report-templates/{template_id}` | `version`（可选） | 完整模板：`sections[]`、`sources[]`、`required_fields[]`、`evidence_rules`、`prohibited_outputs[]`、`gates[]` | 404 `template_not_found` |
| GET | `/api/report-templates/{template_id}/versions` | 路径参数 | `items[]{version,created_at,active}` | 404 |
| GET | `/api/report-templates/{template_id}/versions/{version}` | 路径参数 | `template version` | 404 |
| POST | `/api/report-templates` | `template_id`、`version`、`title`、`sections[]`、`sources[]`、`required_fields[]`、`evidence_rules`、`prohibited_outputs[]`、`gates[]` | `template` | 403 `role_required`、409 `template_version_exists`、422 `prohibited_outputs_empty` |
| PATCH | `/api/report-templates/{template_id}` | `title`、`sections`、`sources`、`required_fields`、`evidence_rules`、`prohibited_outputs`、`gates` | `template` | 404、422 |

字段规则：

1. `template_id` 只能取 `t1_voc`、`t2_competitor`、`t3_selection`、`t4_creator`、`t5_compliance`。
2. `sections[]` 每项必须含 `id`、`title`、`required`、`exhibit_type`。
3. `evidence_rules` 必须含 `required_n`、`required_window_days`、`required_source_count`。
4. `prohibited_outputs[]` 不得为空。最少七条。见 PRD §7.4。
5. 模板版本一旦被报告引用，不得修改。只能新建版本。

### 3.8 M07 报告生成接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/reports` | `project_id`、`report_type`、`status`、`from`、`to`、`limit`、`offset` | `items[]{id,title,report_type,status,period_start,period_end,created_at}` | 401 |
| GET | `/api/reports/{report_id}` | 路径参数 | `ReportResponse`（含 `content`、`delivered_channels`、`skipped_channels`） | 404 `report_not_found` |
| POST | `/api/reports/generate` | `project_id`、`report_type`、`template_id`、`period_start`、`period_end`、`task_id`（可选） | `ReportResponse` | 404 `project_not_found`、422 `contract_validation_failed`、409 `template_not_active` |
| POST | `/api/reports/{report_id}/send` | `channels[]`、`authorized`、`confirm_send`、Header `Idempotency-Key` | `delivered_channels[]`、`skipped_channels{}`、`idempotency_replayed` | 403 `report_send_authorization_required`、409 `report_send_confirmation_required`、404 |
| GET | `/api/reports/{report_id}/audit-events` | 路径参数 | `items[]{event_type,from_status,to_status,actor_id,created_at}` | 404 |
| POST | `/api/reports/{report_id}/audit-events` | `event_type`、`metadata` | `audit_event` | 404、422 |
| GET | `/api/reports/{report_id}/evidence-references` | 路径参数 | `items[]{evidence_id,claim_id,url,excerpt}` | 404 |
| GET | `/api/reports/{report_id}/contract` | 路径参数 | `report_contract` JSON，含 `schema_version`、`template_id`、`identity`、`decision`、`gates`、`coverage`、`metrics`、`claims`、`evidences`、`run_ledger`、`limits`、`unknowns`、`artifact` | 404、422 `contract_validation_failed` |
| GET | `/api/reports/{report_id}/artifact` | 路径参数 | `contract_sha256`、`report_html_sha256`、`sop_html_sha256`、`version`、`generated_at` | 404 |
| GET | `/api/reports/{report_id}/sop` | `format` = `html` 或 `json` | SOP 页面或 JSON | 404、406 `format_not_supported` |
| POST | `/api/reports/{report_id}/share` | `expires_at`、`audience` | `token`、`url`、`expires_at` | 404、409 `report_not_signed` |
| GET | `/api/reports/public/{token}` | 路径参数 | 只读报告 | 404、410 `share_expired` |
| GET | `/api/reports/subscriptions` | `project_id` | `items[]` | 401 |
| PUT | `/api/reports/subscriptions` | `project_id`、`report_type`、`schedule_time`、`timezone`、`channels[]`、`enabled` | `subscription` | 422 |
| POST | `/api/reports/subscriptions/{id}/run` | `authorized`、`confirm_run`、Header `Idempotency-Key` | `subscription_run` | 403、409、404 |
| GET | `/api/reports/subscriptions/{id}/runs` | `limit`、`offset` | `items[]{id,status,report_id,started_at,finished_at}` | 404 |
| POST | `/api/reports/subscriptions/{id}/runs/{run_id}/retry` | `authorized`、`confirm_retry` | `subscription_run` | 404、409 `retry_not_allowed` |

字段规则：

1. `report_type` 必须取五个模板 ID 之一。旧值 `daily` 映射为 `daily_digest`。
2. 合同必须通过 `report_contract.schema.json` 校验。失败不得发布。
3. 两个渲染器必须读同一份合同。改合同一个数字，两页都变。
4. 页脚必须显示两个 HTML 哈希与合同哈希。
5. `send` 的邮件渠道必须经 M11。M07 不得直接调用 SMTP。
6. 未签收的报告不得分享。`G-Publish` 未通过时返回 409。

### 3.9 M08 额度与审计接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/ledger/calls` | `project_id`、`tool_id`、`outcome`、`from`、`to`、`limit`、`offset` | `items[]{call_id,tool_id,endpoint_type,quantity,unit_price,total_cost_usd,outcome,started_at,finished_at}` | 401 |
| GET | `/api/ledger/calls/{call_id}` | 路径参数 | `ToolCall` 全字段 + `ledger_entries[]` | 404 `call_not_found` |
| GET | `/api/quota` | `project_id` | `accounts[]{project_id,period,daily_limit,used,remaining,currency}` | 401 |
| GET | `/api/quota/projects/{project_id}` | 路径参数 | `quota account` | 404 `quota_account_not_found` |
| POST | `/api/authorizations` | `project_id`、`scope{template_id,markets,window}`、`max_cost_usd`、`expires_at`、`approver` | `authorization{id,status,granted_at,expires_at}` | 403 `approver_required`、422 `scope_invalid` |
| GET | `/api/authorizations/{authorization_id}` | 路径参数 | `authorization` | 404 `authorization_not_found` |
| POST | `/api/authorizations/{authorization_id}/revoke` | `reason` | `authorization` | 404、409 `authorization_already_revoked` |
| GET | `/api/audit/events` | `project_id`、`event_type`、`from`、`to`、`limit`、`offset` | `items[]{event_type,actor_id,object_type,object_id,metadata,created_at}` | 401 |

字段规则：

1. `ToolCall` 必须记录 `project_id`、`tool_id`、`contract_version`、`idempotency_key_hash`、`request_hash`、`backend_ref`（`TaskRun.id` 或供应商任务 ID）、`outcome`。
2. 采集类调用的状态只由 `TaskRun` 拥有。`ToolCall` 只投影，不复制 `status`。
3. 账本必须按 `reserve → settle | release` 顺序写。禁止跳步。
4. `unit_price` 保留 6 位小数。`total_cost_usd` 保留 6 位小数。
5. 额度耗尽必须返回 429。不得静默降级。
6. `authorization` 过期后不得用于新 run。

### 3.10 M09 接入网关接口

MCP 工具清单：

| 工具 | 状态 | 输入关键字段 | 输出关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| `list_platforms` | 保留 | `query` | `items[]{platform_id,name}` | 401 |
| `list_capabilities` | 改造 | `platform_id`、`query`、`status` | `items[]` 来自 `tool_catalog` 投影 | 401、404 |
| `describe_capability` | 改造 | `tool_id` | 完整 `ToolContract` | 404 `tool_not_found` |
| `get_playbook` | 改造 | `platform_id` | 结构化 playbook | 404 |
| `collect` | 保留并加幂等 | `project_id`、`tool_id`（兼容 `endpoint_type`）、`params`、`idempotency_key` | `run_id`、`task_id`、`status` | 403 `tool_not_allowed`、429 |
| `tiktok_trend_rank` 等 8 个 | 保留 | 见 `services/tiktok_tools.py:19-73` | 工具结果 | 404、422、429 |
| `discover` | 新增 | `q`、`markets`、`limit` | `items[]{tool_id,why_this,cost_estimate}` | 422 |
| `inspect` | 新增 | `tool_id` | `input_schema`、`output_schema`、`cost_model`、`risk_level` | 404 |
| `get_run` | 新增 | `run_id` | `status`、`records_count`、`outcome`、`cost` | 404 |
| `list_records` | 新增 | `run_id`、`limit`、`cursor` | `items[]`、`next_cursor` | 404、403 |
| `create_report` | 新增 | `task_id`、`template_id`、`format` | `report_id`、`status` | 404、422 |

HTTP 接口：

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/project-keys` | `project_id` | `items[]{id,name,tool_allowlist,daily_collect_quota,last_used_at,revoked_at}` | 401、403 |
| POST | `/api/project-keys` | `project_id`、`name`、`tool_allowlist[]`、`daily_collect_quota` | `id`、`key`（只返回一次）、`created_at` | 403、422 |
| DELETE | `/api/project-keys/{key_id}` | `reason` | 204 | 404 `project_key_not_found` |

字段规则：

1. 所有工具必须经同一道门。禁止绕过 M09 直接调用 M04 的 HTTP。
2. `X-Project-Key` 必须解析为 `project_id`。解析失败返回 401。
3. 工具不在 `tool_allowlist` 时返回 403 `tool_not_allowed`。
4. 每日 collect 计数必须持久化。禁止只存进程内。
5. 全局 `SCRAPY_MCP_TOKEN` 只保留一个发布周期。必须写明退役日期。
6. 未配置任何 token 时必须 fail-closed。当前 `mcp_runtime/auth.py:20-23` 是 fail-open。必须改。

### 3.11 M10 工作台编排接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| POST | `/api/workbench/tasks` | `brand`、`category`、`competitors[]`、`markets[]`、`locale_by_market`、`window{start,end}`、`decision_question`、`does_not_answer[]`、`owner`、`task_type` | `task{id,status,task_type,task_type_confidence}` | 422 `required_slot_missing`、422 `category_unknown` |
| GET | `/api/workbench/tasks` | `project_id`、`status`、`task_type`、`limit`、`offset` | `items[]{id,brand,category,markets,decision_question,status,created_at}` | 401 |
| GET | `/api/workbench/tasks/{task_id}` | 路径参数 | `task`、`plan`、`gates[]`、`runs[]` | 404 `task_not_found` |
| PATCH | `/api/workbench/tasks/{task_id}` | 七槽位字段 | `task` | 404、409 `task_locked`、422 |
| POST | `/api/workbench/plans/preview` | `template_id`、`policy_profile` | `plan{version,items[],exclusions[],estimated_cost_usd,estimated_duration_s,target_grade}` | 404、409 `task_not_ready`、422 |
| PATCH | `/api/workbench/plans/{plan_id}`（⚠ 待登记） | `items[]`、`exclusions[]` | `plan`（重算成本） | 404、409、422 |
| POST | `/api/workbench/plans/{plan_id}/approve` | `authorized`、`confirm_approval`、`max_cost_usd` | `plan`、`authorization_id` | 403 `approval_required`、409 `plan_not_ready` |
| POST | `/api/runs` | `plan_id`、`authorization_id`、`plan_version`（可选）、Header `Idempotency-Key` | `run_ids[]`、`status=queued` | 409 `plan_not_approved`、429 `quota_exceeded` |
| POST | `/api/runs/{run_id}/cancel` | `reason` | `run{id,status=cancelled}` | 404、409 `run_not_cancellable` |
| GET | `/api/workbench/tasks/{task_id}/gates` | 路径参数 | `items[]{gate_id,status,owner,decided_at,note}` | 404 |
| POST | `/api/workbench/tasks/{task_id}/gates/{gate_id}/decide` | `status`、`note`、`owner` | `gate` | 403 `gate_owner_required`、404、409 `gate_not_pending` |
| GET | `/api/workbench/overview` | `project_id` | `tasks_count`、`runs_count`、`success_rate`、`open_gates`、`remaining_budget` | 401 |
| POST | `/api/projects/{project_id}/workflow-plans/preview` | `planning_input`、`policy_profile` | `route_plans[]`、`exclusions[]` | 200 现有 |
| POST | `/api/projects/{project_id}/workflow-plans` | `plan`、`version` | `workflow_plan` | 200 现有 |
| GET | `/api/projects/{project_id}/workflow-plans` | `status`、`limit`、`offset` | `items[]` | 200 现有 |

字段规则：

1. 七槽位必填校验必须在创建任务单时完成。缺一项返回 422。
2. `task_type` 留空时，系统必须给出候选与置信度。低于 0.7 必须由用户确认。
3. 计划单必须列出每个数据源的包含理由或排除理由。排除项不得静默丢弃。
4. 计划单可编辑。编辑后必须重算成本。
5. 没有 `authorization_id` 不得执行。`G-Plan` 与 `G-Cost` 未通过返回 409。
6. 执行必须调用 M04。M10 不得直接实例化 collector。
7. 中止必须保留已完成部分。
8. `workflow_plans` 只做计划持久化与版本比较。不得把 `workflow_runs` 当执行层。

### 3.12 M11 告警与通知接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/alert-rules` | `project_id`、`enabled` | `items[]{id,name,signal_type,severity_threshold,enabled}` | 401 |
| POST | `/api/alert-rules` | `project_id`、`name`、`signal_type`、`severity_threshold`、`channels[]` | `AlertRuleResponse` | 422 |
| PATCH | `/api/alert-rules/{rule_id}` | 同上可选字段 | `AlertRuleResponse` | 404 `alert_rule_not_found` |
| DELETE | `/api/alert-rules/{rule_id}` | 路径参数 | `AlertRuleResponse` | 404 |
| GET | `/api/alert-events` | `project_id`、`status`、`severity`、`limit`、`offset` | `items[]{id,rule_id,signal_id,status,severity,created_at}` | 401 |
| PATCH | `/api/alert-events/{event_id}/status` | `status`、`note` | `AlertEventResponse` | 404 `alert_event_not_found`、422 |
| GET | `/api/notifications` | `unread_only`、`limit`、`offset` | `items[]{id,type,title,body,read_at,created_at}` | 401 |
| PATCH | `/api/notifications/{notification_id}/read` | 无 | `NotificationResponse` | 404 `notification_not_found` |
| POST | `/api/notifications/read-all` | 无 | `updated_count` | 401 |
| POST | `/api/notifications/read-bulk` | `ids[]` | `updated_count` | 422 |
| GET | `/api/notifications/email-channel` | 无 | `configured`、`live_send_enabled`、`recipient_allowlist` | 401 |
| POST | `/api/notifications/email-channel/test` | `recipient`、`authorized`、`confirm_send` | `test_run{status,provider_message_id}` | 403 `email_channel_test_authorization_required`、409 |
| POST | `/api/notifications/email-channel/provider-live-gate` | `authorized`、`confirm_gate` | `gate_run` | 403、409 |
| GET | `/api/notifications/email-channel/live-send-readiness` | 无 | `ready`、`blockers[]` | 401 |
| POST | `/api/notifications/email-channel/live-send` | `recipient`、`subject`、`body`、`authorized`、`confirm_send` | `send_run` | 403 `email_provider_live_send_authorization_required`、409 |

字段规则：

1. 邮件实发必须经过四道门：配置、allowlist、`authorized`、`confirm_send`。
2. `email_live_send_enabled=false` 时所有实发返回 403。见 `apps/api/src/data_intelligence_hub/core/config.py:41`。
3. 站内信是默认渠道。报告发送必须至少写一条站内信。
4. 预警事件必须引用 `signal_id`。不得只存文本。

### 3.13 M12 数据集与产物接口

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 |
| --- | --- | --- | --- | --- |
| GET | `/api/automation/product-datasets` | `project_id`、`status`、`limit`、`offset` | `items[]{id,name,dataset_type,status,latest_version}` | 401 |
| DELETE | `/api/automation/product-datasets/{dataset_id}` | `reason` | `DatasetResponse` | 404 `dataset_not_found`、409 `dataset_has_running_export` |
| GET | `/api/automation/product-datasets/{dataset_id}/versions` | `limit`、`offset` | `items[]{id,version_number,row_count,created_at}` | 404 |
| GET | `/api/automation/product-datasets/{dataset_id}/versions/{version_id}/preview` | `limit`、`offset` | `items[]`、`columns[]` | 404 `version_not_found` |
| POST | `/api/automation/product-dataset-exports` | `dataset_id`、`version_id`、`format` | `export_job{id,status,format}` | 404、422 `export_format_unsupported` |
| GET | `/api/automation/product-dataset-exports/{export_job_id}` | 路径参数 | `export_job` | 404 `export_not_found` |
| GET | `/api/automation/product-datasets/{dataset_id}/exports` | `limit`、`offset` | `items[]` | 404 |
| GET | `/api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download` | 路径参数 | 文件流 | 404、410 `export_expired` |
| POST | `/api/automation/cleaning-plans` | `dataset_id`、`name`、`selected_fields[]`、`rules[]` | `cleaning_plan` | 422 |
| GET | `/api/automation/cleaning-plans` | `project_id`、`status` | `items[]` | 401 |
| POST | `/api/automation/product-drift-check` | `dataset_id`、`version_id` | `drift_event[]` | 404、422 |
| GET | `/api/automation/product-drift-events` | `dataset_id`、`severity`、`limit`、`offset` | `items[]` | 401 |

字段规则：

1. 数据集必须属于当前 `project_id`。跨项目读取返回 403。
2. 导出文件下载必须校验所有权与过期时间。不得暴露永久私有地址。
3. 数据集不得写入新的 `workflow_runs` lineage。`source_workflow_run_id` 只作历史引用。见 §1.13。
4. 清洗计划必须记录 `source_task_run_ids[]`。禁止无来源的清洗。
5. 漂移事件必须引用两个版本 ID。不得只存指标差。

### 3.14 接口与现有路由的差异汇总

| 类别 | 数量 | 说明 |
| --- | --- | --- |
| 直接复用 | 约 60 条 | 现有路由不改路径与语义。 |
| 扩字段 | 约 25 条 | 加 `project_id`、成本字段、证据等级、模板 ID。 |
| 新路径 | 约 30 条 | 目录、claim、模板、账本、工作台、项目 key、分享。 |
| 下线 | 1 组 | `capability_discovery` 路由。 |
| 保留 | 1 组 | `workflow-runs` 全部路由（fixture-only，生产返回 200）。 |
| 迁移 | 1 组 | `/api/collectors/catalog` → `/api/tools`。 |

规则：

1. 下线前必须保留一个发布周期的 410 响应。见 PRD §11.5。
2. 新路径必须先在本文登记，再写路由。
3. 任何路径变更必须写重定向或 410。禁止静默 404。
4. `automation.py` 拆分后，M03、M04、M12 的路径必须保留 `/api/automation` 前缀一个发布周期。M12 可以新增 `/api/assets` 别名。旧路径必须返回 308 或由边缘代理转发。不得直接 404。

## 4. Python 侧模块落位

### 4.1 目标目录

新建代码必须放在 `apps/api/src/data_intelligence_hub/modules/`。旧文件原位保留。

```text
apps/api/src/data_intelligence_hub/
├── modules/
│   ├── __init__.py
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── service.py          # 注册、登录、项目、成员用例
│   │   ├── routes.py           # /api/auth、/api/projects 的新实现
│   │   ├── schemas.py          # 请求与响应模型
│   │   └── contracts.py        # AuthContext、ProjectScope
│   ├── catalog/
│   │   ├── __init__.py
│   │   ├── models.py           # ToolCatalogEntry、ToolVerificationEvent
│   │   ├── service.py          # 读、写、核验、健康度
│   │   ├── discovery.py        # 检索、排序、why_this
│   │   ├── projection.py       # collector_catalog + 端点映射 → tool_catalog
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # ToolContract、CostModel、RiskLevel
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── service.py          # 连接器列表、就绪度、健康度
│   │   ├── credentials.py      # 项目级凭据解析与写入
│   │   ├── preflight.py        # URL 探测，走 outbound_policy
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # CredentialRef、GrantRef
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── service.py          # 创建 run、取消、结果查询
│   │   ├── runs.py             # TaskRun 状态与 outcome 投影
│   │   ├── queue.py            # 持久异步队列适配
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # RunFacts、RunOutcome
│   ├── evidence/
│   │   ├── __init__.py
│   │   ├── models.py           # Claim、ClaimEvidence、RunEvidenceGrade
│   │   ├── service.py          # claim 用例
│   │   ├── pipeline.py         # normalize → signal → intelligence
│   │   ├── grade.py            # 证据等级计算
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # ClaimDraft、EvidenceRef
│   ├── templates/
│   │   ├── __init__.py
│   │   ├── models.py           # ReportTemplate、ReportTemplateVersion
│   │   ├── registry.py         # 模板注册表
│   │   ├── thresholds.py       # 唯一阈值表
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # TemplateRef、EvidenceRules
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── models.py           # ReportArtifact、ReportShare
│   │   ├── service.py          # 订阅、发送、审计、幂等
│   │   ├── contract.py         # report_contract 构建与校验
│   │   ├── render_report.py    # 决策者视图
│   │   ├── render_sop.py       # 执行者视图
│   │   ├── artifacts.py        # 哈希、存档、导出
│   │   ├── shares.py           # 分享与访问审计
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # ReportContract、ArtifactHashes
│   ├── metering/
│   │   ├── __init__.py
│   │   ├── models.py           # ToolCall、RunLedgerEntry、QuotaAccount、Authorization
│   │   ├── ledger.py           # reserve、settle、release
│   │   ├── quota.py            # 单次与每日额度
│   │   ├── rate_card.py        # 从 tool_catalog 读价格
│   │   ├── authorization.py    # 批准与过期
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # CostEstimate、LedgerEntry
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── models.py           # ProjectApiKey
│   │   ├── service.py          # key 解析、白名单、分派
│   │   ├── mcp_tools.py        # 18 个 MCP 工具薄层
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # CallIntent
│   ├── workbench/
│   │   ├── __init__.py
│   │   ├── models.py           # Run、RunStep、RunEvidenceGrade、Authorization（表归 M10 与 M08）
│   │   ├── service.py          # 任务单、计划、运行
│   │   ├── planning.py         # 包装 workflow_planner
│   │   ├── gates.py            # 五个门禁
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # TaskOrderDraft、PlanPreview
│   ├── notify/
│   │   ├── __init__.py
│   │   ├── service.py          # 预警、站内信、邮件门禁
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── contracts.py        # NotificationIntent
│   └── assets/
│       ├── __init__.py
│       ├── service.py          # 数据集、版本、清洗、漂移、导出
│       ├── routes.py
│       ├── schemas.py
│       └── contracts.py        # DatasetRef、ExportRef
├── core/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── adapter.py          # 真实模型 adapter
│   │   ├── factory.py          # 按 settings 选择 adapter
│   │   └── mock.py             # 现有 MockLLMAdapter 迁入
│   ├── events/
│   │   ├── __init__.py
│   │   ├── outbox.py           # 领域事件 outbox
│   │   └── dispatcher.py       # 事件分发
│   └── ...                     # 现有 config、database、security 原位保留
├── api/routes/                 # 旧路由原位保留，逐文件迁移
├── models/                     # 旧模型原位保留，新模型进 modules/*/models.py
├── repositories/               # 旧仓储原位保留
├── services/                   # 旧服务原位保留，逐文件迁移
├── collectors/                 # 采集器原位保留，归属 M04
├── scheduler/                  # 调度器原位保留，归属 M04
├── mcp_runtime/                # MCP 现有实现原位保留，归属 M09
└── main.py                     # 只做路由装配
```

### 4.2 文件命名规则

| 文件名 | 用途 | 禁止 |
| --- | --- | --- |
| `service.py` | 模块用例入口。公开函数必须 async。 | 不放 SQL、不放 HTTP。 |
| `pipeline.py` | 多步骤领域流程。 | 不放路由。 |
| `projection.py` | 只读模型构建。 | 不写库。 |
| `registry.py` | 静态注册表。 | 不读数据库。 |
| `contracts.py` | 跨模块 DTO 与 Protocol。必须 frozen。 | 不 import ORM。 |
| `models.py` | 本模块新表。 | 不放其他模块的表。 |
| `routes.py` | APIRouter。只调用本模块 service。 | 不写业务逻辑。 |
| `schemas.py` | Pydantic 请求与响应。 | 不放 ORM。 |

禁止的文件名：

- `utils.py`
- `helpers.py`
- `common.py`
- `misc.py`

理由：这些名字没有边界。同名文件会让模块依赖失控。

函数命名：

| 动作 | 前缀 | 例 |
| --- | --- | --- |
| 读取单个 | `get_` | `get_tool` |
| 读取列表 | `list_` | `list_tools` |
| 创建 | `create_` | `create_claim` |
| 更新 | `update_` | `update_plan` |
| 状态迁移 | 动词 | `approve_plan`、`revoke_authorization` |
| 计算 | `compute_` | `compute_evidence_grade` |
| 校验 | `assert_` | `assert_tool_allowed` |

### 4.3 新建 service 文件清单

| 模块 | 新文件 | 用途 | 现有替代 |
| --- | --- | --- | --- |
| M01 | `modules/identity/service.py` | 会话、项目、成员。 | 逐步替代 `services/auth_service.py`、`services/project_service.py`。 |
| M02 | `modules/catalog/models.py` | `ToolCatalogEntry`、`ToolVerificationEvent`。 | 无。 |
| M02 | `modules/catalog/projection.py` | 从 `collector_catalog` 与 `_ENDPOINT_TO_COLLECTOR` 生成目录。 | 替代 `api/routes/collectors.py:46-48` 的硬编码。 |
| M02 | `modules/catalog/discovery.py` | 检索、排序、`why_this`。 | 无。 |
| M02 | `modules/catalog/service.py` | 目录读写与核验。 | 扩展 `services/capability_catalog.py`、`services/capability_matrix.py`。 |
| M03 | `modules/connectors/credentials.py` | 项目级凭据解析。 | 扩展 `services/platform_credentials.py`。 |
| M03 | `modules/connectors/preflight.py` | URL 探测。 | 替代 `services/toolkit_preflight_service.py`。 |
| M03 | `modules/connectors/service.py` | 连接器列表与就绪度。 | 扩展 `services/social_provider.py`。 |
| M04 | `modules/execution/service.py` | 运行用例。 | 包装 `services/collector_service.py`、`services/task_service.py`。 |
| M04 | `modules/execution/runs.py` | `outcome` 投影。 | 新增。 |
| M04 | `modules/execution/queue.py` | 持久异步队列。 | 替代 `BackgroundTasks`。 |
| M05 | `modules/evidence/models.py` | `Claim`、`ClaimEvidence`、`RunEvidenceGrade`。 | 无。 |
| M05 | `modules/evidence/pipeline.py` | 规范化、信号、情报。 | 包装 `normalization_service.py`、`signal_service.py`、`intelligence_service.py`。 |
| M05 | `modules/evidence/grade.py` | 证据等级计算。 | 无。 |
| M06 | `modules/templates/models.py` | `ReportTemplate`、`ReportTemplateVersion`。 | 无。 |
| M06 | `modules/templates/registry.py` | 模板注册表。 | 无。 |
| M06 | `modules/templates/thresholds.py` | 唯一阈值表。 | 无。 |
| M07 | `modules/reports/contract.py` | 合同构建与校验。 | 替代 `_render_daily_report` 的输入层。 |
| M07 | `modules/reports/render_report.py` | 决策者视图。 | 替代 `_render_daily_report`。 |
| M07 | `modules/reports/render_sop.py` | 执行者视图。 | 无。 |
| M07 | `modules/reports/artifacts.py` | 哈希与存档。 | 无。 |
| M07 | `modules/reports/shares.py` | 分享与访问审计。 | 无。 |
| M08 | `modules/metering/models.py` | 四张新表。 | 无。 |
| M08 | `modules/metering/ledger.py` | 预留、结算、释放。 | 不复用 `workflow_execution/budget.py`。 |
| M08 | `modules/metering/quota.py` | 额度。 | 无。 |
| M08 | `modules/metering/rate_card.py` | 价格读取。 | 无。 |
| M08 | `modules/metering/authorization.py` | 批准与过期。 | 无。 |
| M09 | `modules/gateway/models.py` | `ProjectApiKey`。 | 无。 |
| M09 | `modules/gateway/service.py` | key 解析、白名单、分派。 | 无。 |
| M09 | `modules/gateway/mcp_tools.py` | 18 个 MCP 工具。 | 包装 `mcp_runtime/server.py`。 |
| M10 | `modules/workbench/models.py` | 新建 `runs`、`run_steps`、`run_evidence_grades`；`authorizations` 归 M08。 | 无。 |
| M10 | `modules/workbench/planning.py` | 计划生成。 | 包装 `services/workflow_planner/planner.py`。 |
| M10 | `modules/workbench/gates.py` | 五个门禁。 | 无。 |
| M10 | `modules/workbench/service.py` | 任务单与执行。 | 包装 M04。 |
| M11 | `modules/notify/service.py` | 预警与通知。 | 包装 `alert_service.py`、`notification_service.py`。 |
| M12 | `modules/assets/service.py` | 数据集与导出。 | 从 `automation_service.py` 拆出。 |
| K0 | `core/llm/adapter.py`、`factory.py`、`mock.py` | 真实 LLM。 | 扩展 `services/llm_service.py`。 |
| K0 | `core/events/outbox.py`、`dispatcher.py` | 领域事件。 | 无。 |

### 4.4 迁移规则

1. 下一批不搬旧文件。新代码只进 `modules/`。
2. 旧文件只在被修改时迁移。一次 PR 只迁移一个文件。
3. 一次 PR 不得同时搬迁文件与改行为。搬迁 PR 必须零行为变化。
4. `main.py` 同时 include 旧 router 与新 router。路径冲突时新 router 优先，旧 router 必须加 410 或删除。
5. 旧测试必须保留。迁移后旧测试必须仍通过。
6. 新模块必须有单元测试。测试路径为 `apps/api/tests/unit/modules/<module>/test_<file>.py`。
7. `services/` 的 33 个文件按 §9.3 归属逐步迁移。迁移完成前，`modules/*/service.py` 可以 import 旧 service。旧 service 不得 import `modules/`。

### 4.5 事务规则

| 规则 | 说明 |
| --- | --- |
| 唯一所有者 | 每个用例必须有一个事务所有者。路由不得提交。 |
| 仓储不提交 | 新仓储不得调用 `session.commit()`。旧仓储提交点必须逐步移除。 |
| 采集 | `execute_collection_task` 是采集事务的所有者。见 `apps/api/src/data_intelligence_hub/services/collector_service.py:73`。 |
| 报告 | `generate_report` 必须在同一事务写 `reports`、`report_artifacts`、`report_audit_events`。 |
| 账本 | `reserve` 必须在执行前独立提交。`settle` 必须在执行后独立提交。两者不得与采集事务合并。 |
| 事件 | outbox 记录必须与业务写在同一事务。分发在提交后。 |
| 禁止 | 禁止在仓储层提交。现有提交点见 `repositories/datasets.py:88`、`:161`、`:259`；`repositories/cleaning_plans.py:24`；`repositories/automation_plans.py:67`、`:76`、`:142`、`:152`；`repositories/scheduler.py:14`。被改动时必须移除。 |

`get_session` 只 yield session，不提交也不回滚。见 `apps/api/src/data_intelligence_hub/core/database.py:50-52`。

## 5. TypeScript 侧模块落位

### 5.1 现状约束

| 事实 | 位置 | 影响 |
| --- | --- | --- |
| 16 个页面。 | `apps/scraper-console/src/app/` | 新模块必须复用页面壳，不新建第二套前端。 |
| 13 个页面是客户端组件。 | 同目录 | 目录与报告阅读页必须改服务端渲染。 |
| 无 `middleware.ts`、无登录页、无会话校验。 | `apps/scraper-console/src/` | 新模块不得假定有登录态。必须补鉴权边界。 |
| 无 `error.tsx`、`loading.tsx`、`not-found.tsx`。 | 同目录 | 新模块必须补路由级状态。 |
| API 由浏览器直连。 | `apps/scraper-console/src/lib/api/client.ts:1-2` | 必须补超时、重试、取消、错误归一。 |
| `zod` 已安装但未使用。 | `apps/scraper-console/package.json` | 新模块必须在边界做运行时校验。 |
| `apps/web` 报告组件没有公网路由。 | `apps/web/src/components/reports/` | 只作迁移源，不作生产入口。 |

### 5.2 目标目录

```text
apps/scraper-console/src/
├── features/
│   ├── identity/
│   │   ├── api.ts
│   │   ├── hooks.ts
│   │   ├── keys.ts
│   │   ├── types.ts
│   │   └── components/
│   ├── catalog/
│   │   ├── api.ts
│   │   ├── hooks.ts
│   │   ├── keys.ts
│   │   ├── types.ts
│   │   └── components/
│   ├── connectors/
│   ├── execution/
│   ├── evidence/
│   ├── templates/
│   ├── reports/
│   ├── metering/
│   ├── gateway/
│   ├── workbench/
│   ├── notify/
│   └── assets/
├── lib/
│   ├── api/
│   │   ├── client.ts        # 浏览器传输层
│   │   └── server.ts        # RSC 传输层
│   ├── query/
│   │   └── client.ts        # QueryClient 配置
│   └── ...
├── app/
│   ├── (public)/
│   │   ├── page.tsx                 # /
│   │   ├── capabilities/page.tsx    # /capabilities
│   │   └── capabilities/[id]/page.tsx
│   ├── (workbench)/
│   │   ├── workbench/page.tsx
│   │   └── workbench/[taskId]/page.tsx
│   ├── (reports)/
│   │   ├── reports/page.tsx
│   │   ├── reports/[id]/page.tsx
│   │   └── reports/public/[id]/page.tsx
│   ├── (settings)/
│   │   ├── connectors/page.tsx
│   │   └── settings/page.tsx
│   ├── error.tsx
│   ├── loading.tsx
│   └── not-found.tsx
└── components/
    ├── layout/             # AppShell、Sidebar、TopBar
    ├── ui/                 # StatTile、ConfirmDialog、useFocusTrap
    └── providers.tsx
```

规则：

1. 一个模块一个 `features/<module>/` 目录。
2. 页面只能 import 本页面对应模块的 `hooks.ts` 与共享组件。
3. 跨模块组件必须放进 `components/`，不得放在某个 feature 下。
4. 旧 `src/lib/api/*.ts` 逐步迁移到 `features/*/api.ts`。迁移期间不得保留两份实现。

### 5.3 fetcher 组织

| 文件 | 职责 | 规则 |
| --- | --- | --- |
| `lib/api/client.ts` | 浏览器请求。 | 必须补 `AbortController`、超时、重试、`ApiError` 归一。 |
| `lib/api/server.ts` | 服务端请求。 | 必须转发 cookie。只用于 RSC。 |
| `features/<module>/api.ts` | 模块 fetcher。 | 纯函数。不得 import React。 |
| `features/<module>/types.ts` | zod schema 与类型。 | `z.infer` 导出类型。 |
| `features/<module>/hooks.ts` | TanStack Query hooks。 | 只调用本模块 `api.ts`。 |
| `features/<module>/keys.ts` | query key 工厂。 | 必须集中。禁止散落字符串。 |

fetcher 命名：

| 动作 | 命名 | 例 |
| --- | --- | --- |
| 列表 | `fetch<Resource>List` | `fetchToolList` |
| 详情 | `fetch<Resource>` | `fetchTool` |
| 搜索 | `<verb><Resource>` | `discoverTools` |
| 创建 | `create<Resource>` | `createTaskOrder` |
| 更新 | `update<Resource>` | `updatePlan` |
| 状态动作 | `<verb><Resource>` | `approvePlan`、`runTask` |
| 删除 | `delete<Resource>` | `deleteProjectKey` |

硬规则：

1. 页面不得直接调用 `fetch`。
2. `api.ts` 必须用 zod 校验响应。校验失败必须抛 `ApiError(500, "response_schema_mismatch")`。
3. 所有 fetcher 必须接受可选 `signal: AbortSignal`。
4. 写操作必须接受 `idempotencyKey`。
5. 错误必须归一为 `ApiError { status, code, message, requestId }`。

### 5.4 hook 命名

| 类型 | 命名 | 例 |
| --- | --- | --- |
| 列表查询 | `use<Resource>List` | `useTaskOrderList` |
| 详情查询 | `use<Resource>` | `useReport` |
| 搜索 | `use<Verb><Resource>` | `useDiscoverTools` |
| 创建 | `useCreate<Resource>` | `useCreateClaim` |
| 更新 | `useUpdate<Resource>` | `useUpdatePlan` |
| 状态动作 | `use<Verb><Resource>` | `useApprovePlan`、`useRunTaskOrder` |
| 删除 | `useDelete<Resource>` | `useDeleteProjectKey` |

规则：

1. hook 必须返回 `{ data, error, isLoading, refetch }` 或 mutation 的 `{ mutate, isPending, error }`。
2. query hook 必须使用 `keys.ts` 的 key。禁止内联数组。
3. mutation 成功后必须精确失效相关 key。禁止 `invalidateQueries()` 全量失效。
4. 轮询只用于运行中任务。间隔 10 秒或 15 秒。现有页面已用 10 秒与 15 秒。见 `apps/scraper-console/src/app/tasks/page.tsx` 与 `runs/page.tsx`。
5. 运行结束后必须停止轮询。

### 5.5 query key 规则

```text
<module>Keys.all
<module>Keys.list(filters)
<module>Keys.detail(id)
<module>Keys.subresource(id, name)
```

示例：

```text
catalogKeys.list({ q, category, market })
catalogKeys.detail(toolId)
reportKeys.list({ projectId, status })
reportKeys.detail(reportId)
workbenchKeys.task(taskId)
workbenchKeys.gates(taskId)
```

规则：

1. key 必须可序列化。对象键顺序必须稳定。
2. 筛选变化必须产生新 key。不得复用旧 key。
3. key 工厂必须与 fetcher 参数一一对应。

### 5.6 页面与渲染边界

| 页面 | 渲染方式 | 数据入口 | 说明 |
| --- | --- | --- | --- |
| `/` | RSC | `fetchToolList`、`fetchReportSample` | 首屏必须 SSR。 |
| `/capabilities` | RSC + 客户端筛选 | `fetchToolList`、`discoverTools` | 首屏 SSR 出结果。筛选写 query string。 |
| `/capabilities/[id]` | RSC | `fetchTool` | 参数表由 `input_schema` 渲染。 |
| `/workbench` | 客户端 | `useTaskOrderList`、`useCreateTaskOrder` | 需要登录态。 |
| `/workbench/[taskId]` | 客户端 | `useTaskOrder`、`usePlan`、`useGates` | 轮询运行状态。 |
| `/reports` | RSC + 客户端筛选 | `fetchReportList` | 列表首屏 SSR。 |
| `/reports/[id]` | RSC + 客户端抽屉 | `fetchReport`、`fetchReportContract` | 报告正文 SSR。证据抽屉客户端加载。 |
| `/reports/public/[id]` | RSC | `fetchPublicReport` | 只读。必须校验分享 token。 |
| `/connectors` | 客户端 | `useConnectorList`、`useUpdateCredential` | 凭据写入必须确认。 |
| `/settings` | 客户端 | `useMemberList`、`useQuota`、`useAuditEvents` | 管理员页面。 |

规则：

1. 公开页必须 SSR。不得依赖客户端请求出首屏。
2. 授权页必须校验会话。无会话跳登录或返回 401 页面。
3. 报告正文必须 SSR。证据抽屉可以客户端加载。
4. 任何页面不得在 render 中 `setState`。现有 `quick-collect-drawer.tsx:760-761` 有该问题。迁移时必须修。

### 5.7 共享组件复用

| 组件 | 位置 | 复用方式 |
| --- | --- | --- |
| `AppShell` | `apps/scraper-console/src/components/layout/app-shell.tsx:16` | 直接复用。 |
| `Sidebar` | `apps/scraper-console/src/components/layout/sidebar.tsx:7-20` | 必须改导航清单。见 §6。 |
| `TopBar` | `apps/scraper-console/src/components/layout/top-bar.tsx` | 直接复用。 |
| `StatTile` | `apps/scraper-console/src/components/ui/stat-tile.tsx` | 直接复用。 |
| `PlatformLogo` | `apps/scraper-console/src/components/platforms/platform-logo.tsx` | 直接复用。 |
| `ConfirmDialog` | `apps/scraper-console/src/components/ui/confirm-dialog.tsx` | 直接复用。 |
| `useFocusTrap` | `apps/scraper-console/src/components/ui/use-focus-trap.ts` | 直接复用。 |
| `DataPreviewDrawer` | `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx` | 迁到 `features/assets/components/`。 |
| `QuickCollectDrawer` | `apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx` | 必须重写为 schema 驱动。见 §9.5。 |
| `report-detail-panel` | `apps/web/src/components/reports/report-detail-panel.tsx` | 抽取 API 调用后迁到 `features/reports/components/`。 |
| `reports-workspace` | `apps/web/src/components/reports/reports-workspace.tsx` | 不迁移。按页面重写。 |

### 5.8 前端迁移规则

1. 先补 `middleware.ts`、登录页、`error.tsx`、`loading.tsx`、`not-found.tsx`。见 PRD M0。
2. 再补 `lib/api/client.ts` 的超时、重试、取消、错误归一。
3. 再按页面迁移。一次一个页面。
4. 迁移一个页面时，必须同时迁走它调用的 `lib/api` 模块。
5. 旧页面必须保留路径或写重定向。不得静默 404。
6. 不得同时维护旧 `lib/api` 与新 `features/*/api.ts` 两份实现。
7. `apps/web` 的报告组件只作参考。迁移时必须替换 83 处与 148 处 raw hex 为控制台 token。见 §9.5。

## 6. 模块与页面映射

### 6.1 目标页面

页面清单按 PRD §3.3。共 11 条路由。一级导航 4 条。

| 页面 | 路由 | 供数模块 | 主要数据 | 验收判据 | 现状 |
| --- | --- | --- | --- | --- | --- |
| 首页 | `/` | M02、M07 | 工具数、实测数据源、真实报告片段 | 输入框跳 `/workbench?q=`；每个数字有实测来源 | 当前 `/` 重定向到 `/platforms`。见 `apps/scraper-console/src/app/page.tsx:4`。 |
| 能力目录 | `/capabilities` | M02 | `tool_catalog` 列表、分类、facet | 首屏 SSR 出结果；筛选写 query string；前 3 条命中评论类工具 | 当前 `/platforms` 可用。见 `apps/scraper-console/src/app/platforms/page.tsx`。 |
| 能力详情 | `/capabilities/[id]` | M02、M03 | 完整契约、输入输出 schema、示例、playbook、就绪度 | 参数表由 `input_schema` 渲染；示例带 `run_id` | 当前 `/skills/[platformId]` 只有包信息。 |
| 分享报告 | `/reports/public/[id]` | M07 | 只读合同与 HTML | 过期返回 410；访问写审计 | new |
| 文档 | `/docs` | M02、M09 | API、数据源、报告规范、模板、证据 | 三栏布局；可检索 | 当前 `/collector-docs` 只覆盖采集器。 |
| 工作台首页 | `/workbench` | M10、M04、M05、M08 | 任务单、计划、门禁、成本 | 新用户 5 分钟出第一份报告；路由 ≤ 2 | new。当前无对应页。 |
| 任务详情 | `/workbench/[taskId]` | M10、M04、M05、M06、M08、M11 | 对话、计划单、执行进度、证据抽屉、门禁 | 计划单可编辑；执行可中止；证据可点回原文 | new |
| 报告中心 | `/reports` | M07 | 报告列表、筛选、签收状态 | 筛选完整；行操作可导出与分享 | new |
| 报告阅读页 | `/reports/[id]` | M07、M05 | 合同、11 章正文、证据抽屉、SOP | 首屏显示最低证据等级与门禁；单条结论可复制 | new |
| 连接器 | `/connectors` | M03 | Provider 目录、凭据、就绪度 | 凭据脱敏；grant 状态可见 | 当前 `/settings/credentials` 可用。见 `apps/scraper-console/src/app/settings/credentials/page.tsx`。 |
| 设置 | `/settings` | M01、M08、M09、M11 | 成员、角色、额度、审计、项目 key、预警规则 | 角色可改；额度可见；审计可查 | 当前 `/settings/account` 是死页。 |

页面规则：

1. `/workbench` 是唯一任务入口。它取代 `/dashboard`。
2. 任务、运行、原始记录、项目、资产都是 `/workbench` 与 `/reports` 的下钻。不单独做一级入口。
3. 公开区与授权区共用同一份 `tool_catalog`。
4. 任何页面不得直接调用未登记的模块接口。

### 6.2 旧控制台页面处置

| 旧路由 | 新位置 | 处置 | 供数模块 | 证据 |
| --- | --- | --- | --- | --- |
| `/platforms` | `/capabilities` | 重定向，保留筛选参数 | M02、M04 | 页面已接 `GET /api/collectors/catalog`。见 `apps/scraper-console/src/app/platforms/page.tsx:397-399`。 |
| `/skills` | `/capabilities` | 重定向 | M02 | 页面可用。见 `apps/scraper-console/src/app/skills/page.tsx`。 |
| `/skills/[platformId]` | `/capabilities/[id]` | 重定向 | M02 | 页面可用。 |
| `/collector-docs` | `/docs` | 重定向 | M02 | 页面已接 `GET /api/collectors/docs`。见 `apps/scraper-console/src/app/collector-docs/page.tsx:273-275`。 |
| `/projects` | `/projects` | 作为 `/workbench` 的下钻保留，不是一级导航 | M01、M10 | 页面已接 `GET /api/projects`。 |
| `/projects/[id]` | `/projects/[id]` | 作为 `/workbench` 的下钻保留并补数据 | M01、M04、M10、M12 | 当前“暂无运行记录”与“暂无数据集”是静态占位。见 `apps/scraper-console/src/app/projects/[id]/page.tsx:144`、`:156`。 |
| `/tasks` | `/tasks` | 保留 | M04 | 页面已接 `GET /api/tasks`。 |
| `/runs` | `/runs` | 作为 `/workbench` 的下钻保留，不是一级导航 | M04 | 页面已接 `GET /api/tasks/runs`。 |
| `/collect/[run_id]` | `/collect/[run_id]` | 作为 `/workbench` 的下钻页保留，不重定向 | M04 | 页面已接 `GET /api/raw-records?task_run_id`。 |
| `/datasets` | `/datasets` | 作为 `/reports` 的下钻页保留，不重定向 | M12 | 页面可用。见 `apps/scraper-console/src/app/datasets/page.tsx:121-123`。 |
| `/raw-records` | `/raw-records` | 作为 `/reports` 的下钻页保留，不重定向 | M04 | 页面可用，但侧栏无入口。 |
| `/dashboard` | `/workbench` | 重定向 | M10 | 页面可用，但侧栏无入口。 |
| `/settings/account` | 删除 | 删除 | 无 | 14 行占位。见 `apps/scraper-console/src/app/settings/account/page.tsx:10`。 |
| `/settings/credentials` | `/connectors` | 重定向 | M03 | 页面可用。 |
| `/tools/tiktok` | `/tools/tiktok` | 保留 | M04 | 页面可用。见 `apps/scraper-console/src/app/tools/tiktok/page.tsx`。 |
| `/` | `/` | 由重定向改为公开首页 | M02、M07 | 当前 `redirect("/platforms")`。见 `apps/scraper-console/src/app/page.tsx:4`。 |

### 6.3 侧栏导航目标

`Sidebar` 必须改。当前只有 8 个主导航项与 1 个辅助项。见 `apps/scraper-console/src/components/layout/sidebar.tsx:7-20`。

目标导航：

| 顺序 | 名称 | 路径 | 模块 | 说明 |
| --- | --- | --- | --- | --- |
| 1 | 工作台 | `/workbench` | M10 | 唯一任务入口。项目与运行是它的下钻。 |
| 2 | 报告 | `/reports` | M07 | 报告中心。资产是它的下钻。 |
| 3 | 连接器 | `/connectors` | M03 | 凭据与就绪度。 |
| 4 | 设置 | `/settings` | M01、M08、M09、M11 | 管理员。 |
| 辅助 | 能力目录 | `/capabilities` | M02 | 公开区同源。二级入口。 |
| 辅助 | 文档 | `/docs` | M02、M09 | 接入文档。 |

规则：

1. 死页不得出现在导航。`/settings/account` 必须删除。
2. 可用但无入口的页面必须补入口。`/dashboard` 与 `/raw-records` 当前只能手输 URL。
3. 一级导航只有 4 个：工作台、报告、连接器、设置。辅助项不得超过 2 个。超出必须归入设置或分组。
4. 导航必须按角色过滤。普通成员不得见 `/settings` 的管理员动作。

### 6.4 页面与模块的读模型

| 读模型 | 拥有模块 | 数据来源 | 不得直接读 |
| --- | --- | --- | --- |
| 目录列表 | M02 | `tool_catalog`、`collectors` | 不得读 `raw_records`、`reports`。 |
| 能力详情 | M02 | `tool_catalog`、`platform_packages` | 不得读执行表。 |
| 工作台总览 | M10 | M04 运行、M05 claim、M08 账本、M07 报告 | 不得直接写任何表。 |
| 报告列表 | M07 | `reports`、`report_artifacts` | 不得读 `raw_records`。 |
| 报告详情 | M07 | 合同、claim、证据、账本 | 不得读采集器配置。 |
| 数据集列表 | M12 | `datasets`、`dataset_versions` | 不得读报告表。 |
| 连接器列表 | M03 | 凭据、健康度、目录就绪度 | 不得读运行记录正文。 |
| 设置 | M01、M08、M09、M11 | 成员、额度、key、规则 | 不得读报告正文。 |

规则：

1. 页面只读本页供数模块的读模型。
2. 跨模块数据必须由供数模块聚合。页面不得自己 join。
3. 读模型必须返回稳定 DTO。不得返回 ORM 对象。

## 7. 构建顺序

### 7.1 拓扑顺序

顺序按依赖图。前置未验收，不得进入下一步。

每个模块的前置：

| 模块 | 前置模块 | 可开始步骤 |
| --- | --- | --- |
| M01 身份与租户 | K0 | P0 |
| M02 目录与发现 | M01 | P1 |
| M03 连接器与凭据 | M01、M02 | P2 |
| M04 采集执行 | M01、M02、M03；完整链路还需 M05、M08 | P3 |
| M06 模板注册 | M01 | P4 |
| M05 证据与主张 | M01、M06 | P5 |
| M08 额度与审计 | M01、M02 | P6 |
| M12 数据集与产物 | M01、M04 | P7 |
| M11 告警与通知 | M01、M05 | P8 |
| M07 报告生成 | M01、M04、M05、M06、M08、M11 | P8a |
| M10 工作台编排 | M01–M08、M11、M12 | P8b |
| M09 接入网关 | M01、M02、M04、M07、M08、M10 | P8c |

说明：M04 的 P3 只建采集内核。M04 调用 M05 与 M08 的接线在 P5 与 P6 之后完成。这样 P3 不被 M05 与 M08 阻塞。

| 步骤 | 模块 | 前置 | 主要工作 | 验收判据 |
| --- | --- | --- | --- | --- |
| P0 | K0 + M01 | 无 | 共享内核；边界测试；移除 demo 兜底；补成员角色。 | 无 token 返回 401；跨项目返回 403；`test_module_boundaries.py` 通过。 |
| P1 | M02 目录 | P0 | `tool_catalog` 表；投影脚本；discover；详情。 | 幽灵端点差集 0；303/284/99 三处代码口径对账通过；生产目录 309/281/70 以 `catalog_digest` 对账；输入“德国吸乳器差评”前 3 条含评论工具。 |
| P2 | M03 连接器 | P1 | 项目级凭据；grant 检查；探测走策略。 | 两个项目用不同 key 调同一工具互不可见；4 个 guarded_http 类型各跑一次真实调用。 |
| P3 | M04 执行 | P2 | 鉴权；幂等唯一约束；持久队列；outcome 四态；`TaskRun` 扩成本列。 | quick-collect 无 token 返回 401；同 key 不重复建 run；重启不丢异步任务；四种 outcome 可读。 |
| P4 | M06 模板 | P0 | 五模板注册表；阈值表；禁止输出。 | 五模板可读；阈值唯一；`prohibited_outputs` 非空。 |
| P5 | M05 证据 | P3、P4 | 新 record_type；新信号规则；claim；证据等级。 | 每条 claim 至少 1 条证据；反证字段 100% 非空；等级计算单测通过。 |
| P6 | M08 额度 | P1、P3 | `ToolCall`；账本；额度；授权；`TaskRun` 投影。 | reserve → settle 可重放；额度耗尽返回 429；`TaskRun` 三成本字段非空。 |
| P7 | M12 数据集 | P3 | 从 `automation_service` 拆出；解耦 `workflow_runs`。 | 数据集 API 独立；导出校验所有权；新版本不写 `workflow_runs` lineage。 |
| P8 | M11 通知 | P5 | 报告发送适配；邮件门禁；预警规则入口。 | 报告发送至少写站内信；邮件默认拒绝；规则可管理。 |
| P8a | M07 报告 | P5、P6、P8 | 合同；两个渲染器；产物；分享；发送接 M11。 | 改合同一个数字两页都变；三个哈希写入页脚；合同 schema 校验失败阻断发布。 |
| P8b | M10 工作台 | P1–P8a | 任务单；计划；门禁；执行；总览。 | S1–S5 全链跑通；新用户 5 分钟出报告；未批准计划不得执行。 |
| P8c | M09 网关 | P1、P3、P8a、P8b | 项目 key；18 个 MCP 工具；白名单；额度。 | 外部 agent 只读 SKILL.md 完成 discover → inspect → collect → list_records；白名单外返回 403。 |
| P8d | 前端页面 | 对应后端步骤 | 按 §6 迁移页面。 | 首屏 SSR；无死链；错误与加载态齐全。 |

### 7.2 并行轨道

```text
轨道 A（主链）  P0 → P1 → P2 → P3 → P5 → P8a → P8b → P8c
轨道 B（模板）  P0 → P4 →（P5 的阈值输入）
轨道 C（账本）  P1 → P3 → P6 →（P8a 的成本输入）
轨道 D（资产）  P3 → P7 →（P8b 的数据集输入）
轨道 E（通知）  P5 → P8 → P8a
轨道 F（前端）  P1 → 目录页；P8a → 报告页；P8b → 工作台页；P8c → 接入页
```

规则：

1. 轨道 A 是关键路径。其他轨道不得阻塞 A。
2. P5 必须等 P4。没有阈值无法计算证据等级。
3. P8a 必须等 P5、P6、P8。没有 claim、账本与通知适配无法生成并发送报告。
4. P8b 必须等 P8a。工作台要展示报告。
5. P8c 必须等 P8b。网关要创建任务单。
6. 轨道 D 在 P3 后可以并行。轨道 E 在 P5 后可以并行。

### 7.3 与 PRD 里程碑对照

| PRD 里程碑 | 本文步骤 | 说明 |
| --- | --- | --- |
| M0 基线 | P0 | 统一鉴权、边界测试、路由决定。 |
| M1 契约层 | P1 | `tool_catalog` 与投影。 |
| M1.5 外访授权 | P2 | 4 个 guarded_http 类型的 grant。 |
| M2 目录 | P1 + P8d | 目录页与详情页。 |
| M2.5 证据阈值 | P4 | 五模板阈值。 |
| M3 编排 | P6 + P8b | 计划单、成本、真实调用。 |
| M4 证据层 | P5 | claim 与 `claim_evidence`。 |
| M5 报告 | P8a | 合同、两个渲染器、产物。 |
| M6 工作台 | P8b + P8d | `/workbench`。 |
| M7a 模板一批 | P4 + P8a | T1、T5、T2。 |
| M7b 模板二批 | P4 + P8a + P7 | T3、T4。T4 依赖 TikTok R1 迁移。 |
| M8 接入 | P8c | MCP 18 工具、项目 key、SKILL.md。 |

### 7.4 每步的质量门

每一步必须同时满足：

1. 新增单元测试通过。测试路径按 §4.4。
2. `pnpm --dir apps/scraper-console exec tsc --noEmit` 通过。
3. `pnpm --dir apps/scraper-console build` 通过。
4. `pytest -q` 必须 0 failed（单元 1980 passed / 集成 384 passed，2026-10-20 基线）。任何新失败都是回归。
5. 本步涉及的模块边界测试通过。
6. 本步涉及的接口有 OpenAPI 快照。
7. 本步涉及的页面有截图或 E2E 冒烟。

禁止：

- 用 integration 失败解释新失败。
- 用未完整（截断或未覆盖）的图分析结果当作通过。
- 跳过 `impact` 分析直接改核心符号。见 `CLAUDE.md`。

## 8. 隔离规则

### 8.1 允许调用矩阵

只列允许的调用。未列出的组合一律禁止。

| 调用方 | 允许调用 | 方式 |
| --- | --- | --- |
| M01 | K0 | import |
| M02 | M01、K0 | service |
| M03 | M01、M02、K0 | service |
| M04 | M01、M02、M03、M05、M08、K0 | service + DTO |
| M05 | M01、M06、K0 | service |
| M06 | M01、K0 | service |
| M07 | M01、M04、M05、M06、M08、M11、K0 | service + DTO |
| M08 | M01、M02、K0 | service |
| M09 | M01、M02、M04、M07、M08、M10、K0 | service |
| M10 | M01、M02、M03、M04、M05、M06、M07、M08、M11、M12、K0 | service |
| M11 | M01、M05、K0 | service + event |
| M12 | M01、M04、K0 | service + DTO |

### 8.2 禁止 import 清单

以下 import 必须在代码评审中直接拒绝：

| 禁止 | 例 | 理由 |
| --- | --- | --- |
| 业务模块 import `api.routes` | `from data_intelligence_hub.api.routes.reports import router` | 业务层不得依赖 HTTP 层。 |
| 业务模块 import 其他模块 `models` | `from data_intelligence_hub.modules.evidence.models import Claim` | 只能读 DTO 或调用 service。 |
| 业务模块 import 其他模块 `repository` | `from data_intelligence_hub.modules.execution.repository import get_run` | 仓储是模块私有。 |
| 叶子模块 import 组合根 | `M02 import M10` | 目录不得知道编排。 |
| 任何模块 import `workflow_execution` | `from ...workflow_execution.execution import ...` | fixture-only；`workflow_runs` 路由已挂载，只返回 fixture 数据。 |
| 任何模块 import `workflow_action` | `from ...models.workflow_action import ...` | 属于 dead 执行栈。 |
| M09 import 业务实现细节 | `M09 import M04.collector_service` | 网关只调用 M04 的公开 service。 |
| M10 import `api.routes.workflow_runs` | — | 该路由已挂载，但只返回 fixture 数据。 |
| M07 import SMTP 客户端 | `import smtplib` | 邮件必须经 M11。 |
| M11 import 报告渲染器 | `from ...modules.reports.render_report import ...` | 通知不得反向依赖报告。 |

### 8.3 允许的通信方式

只允许三种。第四种视为违规。

| 方式 | 用法 | 约束 |
| --- | --- | --- |
| 公开服务调用 | `await modules.execution.service.get_run_facts(run_id)` | 只调用 `service.py` 的公开函数。禁止调用下划线函数。 |
| DTO | `modules.execution.contracts.RunFacts` | 必须 frozen。不得含 ORM 对象。字段变更必须兼容一个版本。 |
| 领域事件 | `core.events.outbox.publish(Event(...))` | 只用于异步副作用。事件必须在业务事务内写 outbox。 |

不允许的方式：

- 直接读其他模块的表。
- 共享可变全局状态。
- 通过 HTTP 回环调用本进程接口。
- 通过 `importlib` 动态加载其他模块。
- 通过字符串路径调用函数。

事件清单：

| 事件 | 发布方 | 订阅方 | 用途 |
| --- | --- | --- | --- |
| `run.completed` | M04 | M08、M10、M11 | 结算成本、更新任务单、发通知。 |
| `run.failed` | M04 | M08、M10、M11 | 释放预留、记失败、发通知。 |
| `claim.created` | M05 | M10 | 更新门禁状态。 |
| `report.generated` | M07 | M11、M10 | 通知签收、更新任务单。 |
| `report.signed` | M07 | M10 | 关闭 `G-Publish`。 |
| `quota.exceeded` | M08 | M11、M10 | 预警。 |
| `authorization.expired` | M08 | M10 | 阻止新 run。 |
| `tool.health_changed` | M04 | M02 | 更新目录健康度。 |

事件规则：

1. 事件名必须是 `<object>.<past_tense_verb>`。
2. 事件载荷必须含 `event_id`、`occurred_at`、`workspace_id`、`project_id`。
3. 事件必须幂等。订阅方必须按 `event_id` 去重。
4. 事件不得携带凭据、原文全文、个人信息。
5. 事件失败不得回滚业务事务。必须进重试队列。

### 8.4 数据所有权

| 规则 | 说明 |
| --- | --- |
| 单写者 | 一个表只有一个拥有模块可以写。 |
| 读写分离 | 其他模块只能通过拥有模块的 service 读。 |
| 外键 | 跨模块外键只允许指向 M01 的 `workspaces`、`projects`、`users`，以及 M04 的 `task_runs`。 |
| 禁止跨模块级联删除 | 删除必须由拥有模块提供用例。 |
| 禁止共享枚举 | 枚举必须定义在拥有模块的 `contracts.py`。 |
| 禁止共享 ORM Base | 新模型必须继承 `models/base.py` 的 Base。Base 属于 K0。 |

表所有权见 §1 与 §9.4。冲突时以 §9.4 为准。

### 8.5 事务与事件

| 场景 | 事务所有者 | 规则 |
| --- | --- | --- |
| 创建任务单 | M10 | 任务单、计划、门禁在同一事务。 |
| 批准计划 | M10 | 计划状态与 `authorization` 关联在同一事务。 |
| 执行采集 | M04 | `TaskRun`、`raw_records`、TikTok 投影在同一事务。证据管线可以分批提交。 |
| 成本预留 | M08 | 独立事务。必须在 M04 执行前提交。 |
| 成本结算 | M08 | 独立事务。必须在 M04 运行结束后提交。 |
| 生成报告 | M07 | `reports`、`report_artifacts`、`report_audit_events` 在同一事务。 |
| 发送报告 | M07 | 状态与审计在同一事务。M11 的发送结果在另一事务。 |
| 发送通知 | M11 | 通知记录与投递尝试在同一事务。 |
| 写数据集版本 | M12 | 版本与导出任务在同一事务。 |

规则：

1. 路由不得 `commit`。
2. 新仓储不得 `commit`。
3. 跨模块调用不得共享 session。每个模块用自己的 session。
4. 需要跨模块原子性时，必须用 outbox 或补偿，不得共享事务。
5. `get_session` 只负责生命周期。见 `apps/api/src/data_intelligence_hub/core/database.py:50-52`。

### 8.6 边界测试

必须新增 `apps/api/tests/unit/test_module_boundaries.py`。

测试规则：

1. 用 `ast` 扫描 `apps/api/src/data_intelligence_hub/modules/` 下所有 import。
2. 把 import 解析为模块 ID。
3. 与 §8.1 的允许矩阵比对。
4. 发现禁止边必须失败。失败信息必须打印文件、行号、源模块、目标模块。
5. 扫描范围必须包含 `from ... import ...` 与 `import ...`。
6. 动态 import 必须用正则兜底扫描 `importlib.import_module`。
7. 测试必须能在 2 秒内跑完。不得连数据库。

附加检查：

| 检查 | 规则 |
| --- | --- |
| 旧层反向依赖 | `services/` 不得 import `modules/`。 |
| 路由瘦身 | `api/routes/*.py` 不得 import 其他模块的 repository。 |
| 模型单写者 | `modules/*/models.py` 的 `__tablename__` 必须在 §9.4 登记。 |
| 事件命名 | `core/events/` 的事件常量必须匹配 `^[a-z_]+\.[a-z_]+$`。 |

### 8.7 评审清单

每个 PR 必须回答：

1. 改动属于哪个模块？
2. 是否新增跨模块依赖？是否在 §2.2 登记？
3. 是否 import 了其他模块的 `models` 或 `repository`？
4. 是否新增表？表是否在 §9.4 登记？
5. 事务所有者是谁？
6. 是否发事件？事件是否幂等？
7. 是否改了公开 DTO？是否兼容一个版本？
8. 是否有边界测试？
9. 是否跑了 `impact`？
10. 是否跑了 `detect_changes`？

## 9. 现有代码归属

### 9.1 34 个 collector 模块

统计口径：`apps/api/src/data_intelligence_hub/collectors/` 有 39 个 `.py` 文件。其中 5 个是基础设施：`__init__.py`、`base.py`、`registry.py`、`outbound_policy.py`、`guarded_http.py`。其余 34 个是 collector 模块。

全部 34 个 collector 模块归 M04。理由：它们是执行适配器。目录元数据归 M02。凭据归 M03。

| # | 文件 | 行数 | 状态 | 依据 |
| --- | --- | --- | --- | --- |
| 1 | `collectors/aliens_eye_collector.py` | 624 | dead | `aliens_eye_*` 在 `UNSUPPORTED_COLLECTORS`。见 `outbound_policy.py:62-117`。 |
| 2 | `collectors/anycrawl_collector.py` | 306 | dead | `baidu_search`、`bing_search`、`duckduckgo_search` 被拒绝。 |
| 3 | `collectors/anydoc_collector.py` | 198 | dead | `anydoc_file_to_markdown` 被拒绝。 |
| 4 | `collectors/anysearch_collector.py` | 182 | reuse_as_is | `anysearch` 属于 `provider_api`。见 `outbound_policy.py:28-58`。 |
| 5 | `collectors/apify_actor.py` | 515 | reuse_as_is | `apify_actor` 属于 `provider_api`。`tests/unit/test_apify_actor_collector.py` 通过。 |
| 6 | `collectors/autoscraper_collector.py` | 193 | dead | `autoscraper_enhanced_web` 被拒绝。 |
| 7 | `collectors/bestblogs_collector.py` | 170 | dead | `bestblogs_articles` 被拒绝。 |
| 8 | `collectors/blackbird_collector.py` | 231 | dead | 两个 `blackbird_*` 被拒绝。 |
| 9 | `collectors/browser_use_collector.py` | 207 | dead | `browser_use_task` 被拒绝。 |
| 10 | `collectors/ecommerce_demo_fixture.py` | 147 | reuse_as_is | 被 `ecommerce_product_page.py:22` 与 `ecommerce_product_discovery.py:22` 使用。 |
| 11 | `collectors/ecommerce_product_discovery.py` | 630 | extend | `guarded_http`。生产 A 缺 grant，catalog 显示 `collection_policy_denied`。 |
| 12 | `collectors/ecommerce_product_page.py` | 791 | extend | `guarded_http`。生产 A 缺 grant。 |
| 13 | `collectors/exa_collector.py` | 712 | reuse_as_is | 4 个 `exa_*` 属于 `provider_api`。`tests/unit/test_exa_anysearch_collectors.py` 通过。 |
| 14 | `collectors/firecrawl_collector.py` | 403 | dead | 3 个 `firecrawl_*` 被拒绝。 |
| 15 | `collectors/generic_web.py` | 214 | reuse_as_is | `guarded_http`。`tests/unit/test_guarded_http.py` 通过。 |
| 16 | `collectors/github_repo.py` | 286 | reuse_as_is | `github_repo` 属于 `provider_api`。 |
| 17 | `collectors/github_topic.py` | 234 | reuse_as_is | `github_topic` 属于 `provider_api`。 |
| 18 | `collectors/hackernews_collector.py` | 276 | reuse_as_is | 3 个 `hackernews_*` 属于 `provider_api`。 |
| 19 | `collectors/jina_reader.py` | 137 | dead | `jina_reader` 被拒绝。 |
| 20 | `collectors/manual_json.py` | 56 | reuse_as_is | `offline`。无外访。 |
| 21 | `collectors/mediacrawler_collector.py` | 645 | dead | 11 个中文社媒 collector 被拒绝。 |
| 22 | `collectors/osint_collector.py` | 533 | dead | `sherlock`、`maigret` 被拒绝。 |
| 23 | `collectors/package_registry_collector.py` | 384 | reuse_as_is | 4 个包注册表 collector 属于 `provider_api`。 |
| 24 | `collectors/pkg_community_collector.py` | 484 | reuse_as_is | `crates_*`、`rubygems_*`、`go_*` 属于 `provider_api`。 |
| 25 | `collectors/pkg_registry2_collector.py` | 499 | reuse_as_is | `packagist_*`、`nuget_*`、`pubdev_*` 属于 `provider_api`。 |
| 26 | `collectors/playwright_browser.py` | 223 | dead | `playwright_browser` 被拒绝。 |
| 27 | `collectors/public_feed.py` | 279 | reuse_as_is | `guarded_http`。T5 的 4 个源依赖它。 |
| 28 | `collectors/robin_collector.py` | 264 | dead | 3 个 `robin_*` 被拒绝。 |
| 29 | `collectors/spiderfoot_collector.py` | 380 | dead | 3 个 `spiderfoot_*` 被拒绝。 |
| 30 | `collectors/spiderfoot_extended_collectors.py` | 117 | dead | 6 个 `spiderfoot_*` 被拒绝。 |
| 31 | `collectors/tech_blog_collector.py` | 347 | dead | `devto_*`、`juejin_*`、`substack_*` 被拒绝。 |
| 32 | `collectors/tikhub_social.py` | 2355 | reuse_as_is | `tikhub_social` 属于 `provider_api`。`tests/unit/test_tikhub_social_collector.py` 通过。 |
| 33 | `collectors/twscrape_collector.py` | 396 | dead | 3 个 `twscrape_*` 被拒绝。 |
| 34 | `collectors/wappalyzer_collector.py` | 225 | dead | `tech_stack_detect` 被拒绝。 |

统计：

| 状态 | 数量 | 说明 |
| --- | --- | --- |
| `reuse_as_is` | 14 | 真接可执行。 |
| `extend` | 2 | 需要 grant。 |
| `dead` | 18 | 被策略拒绝或无调用路径。 |

基础设施文件：

| 文件 | 行数 | 归属 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| `collectors/base.py` | 176 | M04 | reuse_as_is | `BaseCollector` 协议。67 个子类使用。 |
| `collectors/registry.py` | 231 | M04 | extend | 86 个注册项。新增 collector 必须同步 4 处。 |
| `collectors/outbound_policy.py` | 231 | M04 | reuse_as_is | 策略分类：offline 1、guarded_http 4、provider_api 28、unsupported 53。文件未跟踪。 |
| `collectors/guarded_http.py` | 176 | M04 | reuse_as_is | `RequestBudget`、`collection_scope`、`guarded_get`。文件未跟踪。 |
| `collectors/__init__.py` | 31 | M04 | reuse_as_is | 导出。 |

新增 collector 的同步点：

1. `collectors/registry.py:220`。
2. `collectors/outbound_policy.py:19-118`。
3. `api/routes/quick_collect.py:35` 的 `_ENDPOINT_TO_COLLECTOR`。
4. `services/collector_catalog.py:24` 的 `COLLECTOR_CATALOG`。
5. `api/routes/collectors.py:46-48` 的端点元数据。M02 完成后由 `tool_catalog` 取代。

### 9.2 26 个路由模块

统计口径：`apps/api/src/data_intelligence_hub/api/routes/` 有 26 个实现文件，另有 `__init__.py`。

| # | 文件 | 行数 | 归属 | 状态 | 处置 |
| --- | --- | --- | --- | --- | --- |
| 1 | `api/routes/alerts.py` | 147 | M11 | reuse_as_is | 保留。 |
| 2 | `api/routes/auth.py` | 94 | M01 | reuse_as_is | 保留。补成员角色接口。 |
| 3 | `api/routes/automation.py` | 1484 | M03、M04、M12 | replace | 按 §3 拆到三个模块。保留路径一个周期。 |
| 4 | `api/routes/capabilities.py` | 150 | M02 | reuse_as_is | 保留。目录读模型。 |
| 5 | `api/routes/capability_discovery.py` | 69 | M02 | dead | router 未挂载。生产 404。删除或挂载。 |
| 6 | `api/routes/capability_governance.py` | 535 | M02 | dead | router 未挂载。发布能力不可用。必须补受控发布。 |
| 7 | `api/routes/collectors.py` | 4870 | M02 | replace | 端点元数据硬编码 303 条。由 `tool_catalog` 取代。`/docs` 保留。 |
| 8 | `api/routes/dashboard.py` | 40 | M10 | extend | 改为 `/api/workbench/overview`。 |
| 9 | `api/routes/entities.py` | 93 | M05 | reuse_as_is | 保留。 |
| 10 | `api/routes/health.py` | 42 | K0 | reuse_as_is | 保留。 |
| 11 | `api/routes/intelligence.py` | 156 | M05 | reuse_as_is | 保留。 |
| 12 | `api/routes/notifications.py` | 202 | M11 | reuse_as_is | 保留。 |
| 13 | `api/routes/platform_credentials.py` | 125 | M03 | extend | 增加 `project_id`。 |
| 14 | `api/routes/platform_packages.py` | 119 | M02 | reuse_as_is | 保留。 |
| 15 | `api/routes/projects.py` | 112 | M01 | extend | 修 `user=None`；补成员角色。 |
| 16 | `api/routes/quick_collect.py` | 1076 | M04 | extend | 补鉴权、幂等、持久队列。 |
| 17 | `api/routes/raw_records.py` | 58 | M04 | reuse_as_is | 保留。 |
| 18 | `api/routes/reports.py` | 329 | M07 | extend | 加合同、产物、分享。 |
| 19 | `api/routes/signals.py` | 102 | M05 | reuse_as_is | 保留。 |
| 20 | `api/routes/social_provider.py` | 298 | M03 | extend | 只做门禁。无 live provider 执行。 |
| 21 | `api/routes/sources.py` | 164 | M04 | reuse_as_is | 保留。 |
| 22 | `api/routes/tasks.py` | 189 | M04 | reuse_as_is | 保留。 |
| 23 | `api/routes/tiktok_tools.py` | 39 | M04 | reuse_as_is | 保留。 |
| 24 | `api/routes/toolkit.py` | 70 | M02、M03 | extend | 方法卡归 M02；preflight 归 M03。 |
| 25 | `api/routes/workflow_plans.py` | 939 | M10 | reuse_as_is | 保留。planner 计划持久化。 |
| 26 | `api/routes/workflow_runs.py` | 1688 | M10 | reuse_as_is | 已挂载，fixture-only。生产返回 200 且 `execution_mode=fixture`。不得删除。 |

统计：

| 状态 | 数量 | 说明 |
| --- | --- | --- |
| `reuse_as_is` | 15 | 直接保留。 |
| `extend` | 7 | 补字段、补鉴权、补能力。 |
| `replace` | 2 | `automation.py`、`collectors.py`。 |
| `dead` | 2 | `capability_discovery.py`、`capability_governance.py`。 |

挂载状态：

- 已挂载：24 个模块。见 `apps/api/src/data_intelligence_hub/main.py:90-116`。`workflow_plans`、`workflow_runs` 与 `capabilities` 等已挂载。`collectors` 有三个路径。
- 未挂载：2 个模块。`capability_discovery.py`、`capability_governance.py`。PRD §10 风险 4 的未挂载路由数需按新事实重算。
- 生产证据：`/api/projects/{id}/workflow-runs` 返回 200，`execution_mode=fixture`。`/api/capabilities/matrix` 返回 200。

### 9.3 services 归属

统计口径：`apps/api/src/data_intelligence_hub/services/` 有 33 个实现文件，另有 `__init__.py`。另有 4 个包：`workflow_planner`、`workflow_execution`、`capability_discovery`、`capability_governance`。合计 37 个实现单元。

| # | 文件 | 行数 | 归属 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | `services/alert_service.py` | 271 | M11 | reuse_as_is | `match_alert_rules_for_signal` 在 :133。 |
| 2 | `services/auth_service.py` | 164 | M01 | reuse_as_is | 注册、登录、会话。见 :38、:81、:97。 |
| 3 | `services/automation_service.py` | 13537 | M03、M04、M12 | replace | 335 个函数。必须拆。站点分析与浏览器诊断归 M03；产品发现与批量运行归 M04；数据集与导出归 M12。 |
| 4 | `services/browser_structure_diagnostic.py` | 385 | M03 | dead | 只被测试导入。src 无调用方。 |
| 5 | `services/capability_catalog.py` | 115 | M02 | reuse_as_is | `get_capability_catalog` 在 :38。 |
| 6 | `services/capability_matrix.py` | 206 | M02 | reuse_as_is | `build_capability_matrix` 在 :46。 |
| 7 | `services/collector_catalog.py` | 1411 | M02 | extend | 99 个定义。`ensure_collectors_seeded` 在 :780。`validate_collector_config` 在 :827。必须成为 `tool_catalog` 的投影源。 |
| 8 | `services/collector_service.py` | 464 | M04 | reuse_as_is | `execute_collection_task` 在 :73。唯一执行入口。 |
| 9 | `services/dashboard_service.py` | 301 | M10 | extend | `get_dashboard_overview` 在 :39。改为工作台读模型。 |
| 10 | `services/disabled_reddit_execution.py` | 164 | M04 | dead | 只被单元测试调用。 |
| 11 | `services/disabled_youtube_execution.py` | 84 | M04 | dead | 只被单元测试调用。 |
| 12 | `services/entity_service.py` | 50 | M05 | reuse_as_is | 实体查询。 |
| 13 | `services/evidence_service.py` | 280 | M05 | reuse_as_is | `build_evidences_for_signal` 在 :13。纯函数。 |
| 14 | `services/exceptions.py` | 277 | K0 | reuse_as_is | 服务层异常。 |
| 15 | `services/intelligence_service.py` | 271 | M05 | extend | `generate_intelligence_for_signal` 在 :128。文案依赖 Mock LLM。 |
| 16 | `services/llm_service.py` | 82 | K0 | extend | 固定 `MockLLMAdapter`。见 :12。必须新增真实 adapter。 |
| 17 | `services/normalization_service.py` | 421 | M05 | extend | 只支持 7 类 `record_type`。见 :64-88。 |
| 18 | `services/notification_service.py` | 1071 | M11 | reuse_as_is | 站内信与邮件门禁。 |
| 19 | `services/platform_credentials.py` | 271 | M03 | extend | 无 `project_id`。必须扩。 |
| 20 | `services/project_service.py` | 95 | M01 | extend | `create_project` 读 `user.id`。必须修。 |
| 21 | `services/provider_execution_preflight.py` | 51 | M03 | dead | 无 live 调用路径。 |
| 22 | `services/raw_record_service.py` | 39 | M04 | reuse_as_is | 原始记录查询。 |
| 23 | `services/report_service.py` | 1244 | M07 | extend | 订阅、发送、审计可复用。渲染器必须替换。 |
| 24 | `services/signal_service.py` | 427 | M05 | extend | 只有两类信号规则。见 :252-286。 |
| 25 | `services/social_provider.py` | 1486 | M03 | extend | 只做 catalog、readiness、gate。无 live 执行。 |
| 26 | `services/source_service.py` | 190 | M04 | reuse_as_is | 采集源用例。 |
| 27 | `services/task_schedule_policy.py` | 152 | M04 | reuse_as_is | 到期与重试策略。 |
| 28 | `services/task_service.py` | 170 | M04 | extend | 手动运行幂等只写日志。必须加唯一约束。 |
| 29 | `services/tiktok_content_ingestion.py` | 812 | M04 | reuse_as_is | `ingest_tiktok_content` 在 :659。文件未跟踪。 |
| 30 | `services/tiktok_tools.py` | 491 | M04 | reuse_as_is | 8 个工具。`run_tiktok_tool` 在 :480。文件未跟踪。 |
| 31 | `services/toolkit_method_card_service.py` | 327 | M02 | reuse_as_is | 方法卡草稿。 |
| 32 | `services/toolkit_preflight_service.py` | 595 | M03 | replace | 直接 `httpx`，绕过 `outbound_policy`。见 :115-145。 |
| 33 | `services/toolkit_service.py` | 1419 | M02 | reuse_as_is | `get_toolkit_overview` 在 :475。 |
| 34 | `services/capability_discovery/` | 791 | M02 | dead | 5 个文件。router 未挂载。 |
| 35 | `services/capability_governance/` | 2059 | M02 | extend | 8 个文件。被已挂载的 `/api/capabilities` 使用。专用 router 未挂载。 |
| 36 | `services/workflow_execution/` | 9223 | M10 | dead | 23 个文件。fixture-only。禁止复用。 |
| 37 | `services/workflow_planner/` | 7438 | M10 | reuse_as_is | 14 个文件。resolver 与 planner 可复用。 |

统计：

| 状态 | 数量 | 说明 |
| --- | --- | --- |
| `reuse_as_is` | 17 | 直接复用。 |
| `extend` | 12 | 必须改范围。 |
| `replace` | 2 | `automation_service`、`toolkit_preflight_service`。 |
| `dead` | 6 | 4 个文件 + 2 个包。 |

### 9.4 模型与表归属

#### 9.4.1 现有表

| 模块 | 模型文件 | 表 |
| --- | --- | --- |
| M01 | `models/user.py:15`、`models/workspace.py:22`、`:46`、`models/project.py:22` | `users`、`workspaces`、`workspace_members`、`projects` |
| M02 | `models/collector.py:12`、`models/capability_governance.py:37-372` | `collectors`、`capability_governance_memberships`、`capability_discovery_batches`、`capability_source_snapshots`、`capability_discovery_batch_sources`、`capability_evidence`、`capability_candidate_versions`、`capability_candidate_evidence`、`capability_verification_tasks`、`capability_verification_decisions`、`capability_catalog_snapshots`、`capability_publication_revisions`、`capability_catalog_head`、`capability_governance_requests` |
| M03 | `models/platform_credential.py:12`、`models/provider_health.py:33`、`:168`、`models/automation_plan.py:24-207` | `platform_credential_bundles`、`provider_health_snapshots`、`provider_health_route_feedbacks`、`site_analyses`、`browser_diagnostic_runs`、`browser_diagnostic_jobs`、`browser_diagnostic_job_runs`、`extraction_plans` |
| M04 | `models/source.py:19`、`models/task.py:20`、`:45`、`models/scheduler.py:12`、`:21`、`models/raw_record.py:30`、`models/tiktok_content.py:65-394` | `sources`、`collection_tasks`、`task_runs`、`scheduler_leases`、`scheduler_ticks`、`raw_records`、`creator`、`creator_snapshot`、`video`、`video_snapshot`、`comment`、`comment_snapshot`、`hashtag`、`hashtag_snapshot`、`video_hashtag`、`trend_topic`、`sound`、`transcript` |
| M05 | `models/entity.py:20`、`:57`、`models/signal.py:19`、`models/intelligence.py:22`、`:51`、`:79` | `entities`、`entity_snapshots`、`signals`、`intelligence_items`、`evidences`、`intelligence_feedback` |
| M06 | 无 | 无。必须新建。 |
| M07 | `models/report.py:16`、`:37`、`:58`、`:88` | `reports`、`report_audit_events`、`report_subscriptions`、`report_subscription_runs` |
| M08 | 无 | 无。必须新建。`task_runs` 扩三列。 |
| M09 | 无 | 无。必须新建。 |
| M10 | `models/workflow_plan.py:35-369`、`models/workflow_template.py:26`、`:85`、`:155`、`models/workflow_scope_template.py:26` | `workflow_plans`、`workflow_versions`、`monitoring_scopes`、`workflow_version_scopes`、`query_terms`、`workflow_plan_save_requests`、`workflow_templates`、`workflow_template_revisions`、`workflow_template_mutation_requests`、`monitoring_scope_templates` |
| M11 | `models/alert.py:17`、`:37`、`models/notification.py:16`、`:35`、`:57`、`:86` | `alert_rules`、`alert_events`、`notifications`、`email_channel_test_runs`、`email_provider_live_gate_runs`、`email_provider_live_send_runs` |
| M12 | `models/dataset.py:32`、`:58`、`:88`、`:161`、`:186` | `datasets`、`cleaning_plans`、`dataset_versions`、`dataset_drift_events`、`dataset_export_jobs` |

#### 9.4.2 新增表

| 模块 | 表 | 主要字段 | 迁移 |
| --- | --- | --- | --- |
| M02 | `tool_catalog` | `tool_id`（PK）、`provider`、`endpoint_type`、`actor_id`、`display_name`、`category`、`markets`、`input_schema`、`output_schema`、`content_types`、`cost_model`、`risk_level`、`max_evidence_grade`、`contract_version`、`verified_at`、`last_records_count`、`health_status`、`p50_latency_ms`、`execution_kind` | 新建。由 `collector_catalog` 与 `_ENDPOINT_TO_COLLECTOR` 生成。 |
| M02 | `tool_verification_events` | `id`、`tool_id`、`contract_version`、`changed_fields`、`changed_by`、`changed_at` | 新建。 |
| M05 | `claims` | `id`、`task_id`、`text`、`claim_status`、`evidence_grade`、`owner`、`scope_market`、`scope_window_start`、`scope_window_end`、`scope_sample_n`、`counterevidence_text` | 新建。从 `intelligence_items` 回填初版。 |
| M05 | `claim_evidence` | `claim_id`、`evidence_id`、`role` | 新建。从 `evidences` 按 `intelligence_id` 回填。 |
| M10 | `run_evidence_grades` | `run_id`、`live_call`、`authorization_id`、`sample_n`、`required_n`、`window_days`、`required_window_days`、`source_count`、`required_source_count`、`grade` | 新建。`grade` 由 M05 计算，表由 M10 拥有。 |
| M06 | `report_templates` | `template_id`、`active_version`、`title`、`task_type` | 新建。 |
| M06 | `report_template_versions` | `id`、`template_id`、`version`、`sections`、`sources`、`required_fields`、`evidence_rules`、`prohibited_outputs`、`gates`、`created_at` | 新建。 |
| M07 | `report_artifacts` | `id`、`report_id`、`contract_json`、`contract_sha256`、`report_html_sha256`、`sop_html_sha256`、`version`、`generated_at` | 新建。旧报告不回填。 |
| M07 | `report_shares` | `id`、`report_id`、`token_hash`、`audience`、`expires_at`、`created_by`、`created_at`、`revoked_at` | 新建。 |
| M08 | `tool_calls` | `id`、`project_id`、`tool_id`、`contract_version`、`idempotency_key_hash`、`request_hash`、`backend_ref_type`、`backend_ref_id`、`outcome`、`started_at`、`finished_at` | 新建。 |
| M08 | `run_ledger_entries` | `id`、`run_id`、`step_id`、`entry_kind`、`amount_usd`、`balance_after_usd`、`idempotency_key`、`created_at` | 新建。`entry_kind` 取 `estimate`/`reserve`/`accrued`/`settle`/`release`/`block`。不得用 `entry_type` 或 `phase`。 |
| M08 | `quota_accounts` | `id`、`project_id`、`period`、`daily_limit_usd`、`used_usd`、`remaining_usd`、`currency`、`updated_at` | 新建。 |
| M08 | `authorizations` | `id`、`project_id`、`approver`、`scope`、`gate_status`、`max_cost_usd`、`granted_at`、`expires_at`、`revoked_at` | 新建。`gate_status` 取 `pending`/`pass`/`fail`/`blocked`/`expired`。不另建门禁表。 |
| M09 | `project_api_keys` | `id`、`project_id`、`key_hash`、`name`、`tool_allowlist`、`daily_collect_quota`、`created_by`、`last_used_at`、`revoked_at` | 新建。 |
| M10 | `workbench_tasks` | `id`、`project_id`、`brand`、`category`、`competitors`、`markets`、`locale_by_market`、`window_start`、`window_end`、`decision_question`、`does_not_answer`、`owner_id`、`task_type`、`task_type_confidence`、`status`、`created_at`、`updated_at` | 新建。七槽位任务单，不记录执行状态；`status` 是任务单状态。 |
| M10 | `runs` | `id`、`project_id`、`plan_id`、`plan_version`、`authorization_id`、`status`、`outcome`、`total_cost_usd`、`started_at`、`finished_at` | 新建。一次执行运行，一份计划执行一次；不存七槽位。`status` 取 `queued`/`running`/`completed`/`failed`/`cancelled`，不得取 `held`/`degraded`。`outcome` 取 `success`/`empty`/`config_gated`/`failed`。 |
| M10 | `run_steps` | `id`、`run_id`、`step_index`、`tool_id`、`endpoint_type`、`collector_type`、`task_run_id`、`status`、`outcome`、`unit`、`unit_price`、`total_cost_usd` | 新建。执行步骤，不存计划正文；计划正文归 `workflow_plans`/`workflow_versions`。`status` 取 `pending`/`running`/`success`/`empty`/`config_gated`/`failed`/`skipped`；`outcome` 取 `success`/`empty`/`config_gated`/`failed`。 |

门禁决定写入 M08 的 `authorizations` 表，不另建对应表。

表拥有者以契约冻结 §6.2 为准：`tool_catalog`、`tool_verification_events` → M02 目录与发现；`workbench_tasks`、`runs`、`run_steps`、`run_evidence_grades` → M10 工作台编排；`claims`、`claim_evidence` → M05 证据与主张；`report_templates`、`report_template_versions` → M06 模板注册；`report_artifacts`、`report_shares` → M07 报告生成；`authorizations`、`tool_calls`、`run_ledger_entries`、`quota_accounts` → M08 额度与审计；`project_api_keys` → M09 接入网关。M04 采集执行只写 `task_runs` 与 `raw_records`，不拥有 `runs`。

#### 9.4.3 扩列与改列

| 表 | 变更 | 回填 | 回滚 |
| --- | --- | --- | --- |
| `task_runs` | 加 `unit_price`、`total_cost_usd`、`remaining_budget`、`provider`、`endpoint_type`、`schema_version` | 旧 run 置空。新 run 必填。 | 删列。 |
| `platform_credential_bundles` | 加 `project_id`（可空）。唯一约束改为 `(workspace_id, project_id, platform)` | 旧行 `project_id=NULL` | 删列，恢复旧唯一约束。 |
| `evidences` | `intelligence_id` 改为可空 | 先加新列，双写一个周期 | 保留旧列。 |
| `reports` | `report_type` 扩为五个模板 ID + `daily_digest` | `daily` → `daily_digest` | 保留旧值。 |
| `dataset_versions` | 移除指向 `workflow_runs` 的复合外键；`source_workflow_run_id` 保留为历史列 | 无 | 恢复外键。 |
| `workspace_members` | 加 `role` | 旧行 `member` | 删列。 |

#### 9.4.4 隔离执行栈

以下表属于 `workflow_execution` / `workflow_action` / `workflow_executor`。除 `workflow_runs` 为已挂载的 fixture-only 表外，全部不得被新模块引用。部署前必须确认没有新依赖。

| 模型文件 | 表 |
| --- | --- |
| `models/workflow_execution.py` | `workflow_runs`、`step_runs`、`step_run_attempts`、`workflow_step_checkpoints`、`workflow_budget_accounts`、`workflow_budget_ledger_entries`、`workflow_fallback_decisions`、`workflow_shadow_comparisons`、`workflow_run_requests`、`workflow_lineage_materialization_requests` |
| `models/workflow_action.py` | `workflow_run_action_contexts`、`workflow_run_action_approval_receipts`、`workflow_run_action_requests`、`workflow_run_action_receipts`、`workflow_run_action_approval_consumptions`、`workflow_run_action_audit_events` |
| `models/workflow_executor.py` | `workflow_execution_dispatches`、`workflow_execution_leases`、`workflow_execution_events`、`workflow_credential_resolution_permits`、`workflow_provider_call_permits`、`workflow_provider_call_audits`、`workflow_cancellation_requests`、`workflow_cancellation_acknowledgements` |

规则：

1. 新模块不得 import 这些模型。
2. `raw_records` 仍有 `workflow_run_id` 与 `workflow_step_run_id` 外键。见 `models/raw_record.py:30-88`。短期保留，长期必须解耦。
3. `dataset_versions` 仍有指向 `workflow_runs` 的复合外键。见 `models/dataset.py:88-131`。必须停止新增依赖，并在迁移中移除该外键。
4. 不得删除这些表。删除必须先做数据归档与回滚演练。
5. `workflow_runs` 是已挂载的 fixture-only 表（`origin/main:143` 已注册，生产返回 200 且 `execution_mode=fixture`）。不得标 dead，不得删除。

### 9.5 前端文件归属

#### 9.5.1 页面

| 页面文件 | 行数 | 归属 | 状态 | 处置 |
| --- | --- | --- | --- | --- |
| `apps/scraper-console/src/app/page.tsx` | 5 | M02 | extend | 改为公开首页，不再 redirect。 |
| `apps/scraper-console/src/app/platforms/page.tsx` | 683 | M02、M04 | extend | 改为 `/capabilities`。 |
| `apps/scraper-console/src/app/skills/page.tsx` | 5 | M02 | reuse_as_is | 重定向到 `/capabilities`。 |
| `apps/scraper-console/src/app/skills/[platformId]/page.tsx` | 13 | M02 | reuse_as_is | 重定向到 `/capabilities/[id]`。 |
| `apps/scraper-console/src/app/projects/page.tsx` | 216 | M01 | reuse_as_is | 作为 `/workbench` 下钻保留。 |
| `apps/scraper-console/src/app/projects/[id]/page.tsx` | 162 | M01、M04、M10、M12 | extend | 作为 `/workbench` 下钻保留，接入运行与数据集。 |
| `apps/scraper-console/src/app/tasks/page.tsx` | 184 | M04 | reuse_as_is | 保留。 |
| `apps/scraper-console/src/app/runs/page.tsx` | 226 | M04 | reuse_as_is | 作为 `/workbench` 下钻保留。 |
| `apps/scraper-console/src/app/collect/[run_id]/page.tsx` | 119 | M04 | reuse_as_is | 作为 `/workbench` 下钻页保留，不重定向。 |
| `apps/scraper-console/src/app/datasets/page.tsx` | 672 | M12 | reuse_as_is | 作为 `/reports` 下钻页保留，不做重定向。 |
| `apps/scraper-console/src/app/collector-docs/page.tsx` | 405 | M02 | reuse_as_is | 重定向到 `/docs`。 |
| `apps/scraper-console/src/app/settings/credentials/page.tsx` | 287 | M03 | reuse_as_is | 重定向到 `/connectors`。 |
| `apps/scraper-console/src/app/dashboard/page.tsx` | 198 | M10 | reuse_as_is | 重定向到 `/workbench`。 |
| `apps/scraper-console/src/app/raw-records/page.tsx` | 164 | M04 | reuse_as_is | 作为 `/reports` 下钻页保留，不重定向到 `/assets/records`。 |
| `apps/scraper-console/src/app/tools/tiktok/page.tsx` | 715 | M04 | reuse_as_is | 保留。文件未跟踪。 |
| `apps/scraper-console/src/app/settings/account/page.tsx` | 14 | 无 | dead | 删除。 |

#### 9.5.2 组件

| 组件文件 | 归属 | 状态 | 说明 |
| --- | --- | --- | --- |
| `components/layout/app-shell.tsx` | K0 前端 | reuse_as_is | 13 个页面使用。 |
| `components/layout/sidebar.tsx` | K0 前端 | extend | 必须改导航。见 §6.3。 |
| `components/layout/top-bar.tsx` | K0 前端 | reuse_as_is | 直接复用。 |
| `components/ui/stat-tile.tsx` | K0 前端 | reuse_as_is | 直接复用。 |
| `components/ui/confirm-dialog.tsx` | K0 前端 | reuse_as_is | 直接复用。 |
| `components/ui/use-focus-trap.ts` | K0 前端 | reuse_as_is | 直接复用。 |
| `components/providers.tsx` | K0 前端 | reuse_as_is | TanStack Query 提供者。 |
| `components/platforms/platform-logo.tsx` | M02 | reuse_as_is | 品牌字母徽标。 |
| `components/platforms/quick-collect-drawer.tsx` | M04 | extend | 必须改为 catalog 驱动。当前硬编码 162 个 `endpoint_type`。生产 catalog 为 309 视图 / 281 唯一端点 / 70 平台（`catalog_digest=dad20448…`；仓库生成物为 286 / 258，口径不同）。150 个端点没有表单字段。 |
| `components/datasets/data-preview-drawer.tsx` | M12 | reuse_as_is | 迁到 `features/assets/components/`。 |
| `components/skills/skills-directory.tsx` | M02 | reuse_as_is | 迁到 `features/catalog/components/`。 |
| `components/skills/skill-detail.tsx` | M02 | reuse_as_is | 迁到 `features/catalog/components/`。 |

#### 9.5.3 API 模块

| 文件 | 归属 | 状态 | 目标 |
| --- | --- | --- | --- |
| `src/lib/api/client.ts` | K0 前端 | extend | 补超时、重试、取消、错误归一。 |
| `src/lib/api/collectors.ts` | M02 | reuse_as_is | `features/catalog/api.ts` |
| `src/lib/api/collector-docs.ts` | M02 | reuse_as_is | `features/catalog/api.ts` |
| `src/lib/api/platform-packages.ts` | M02 | reuse_as_is | `features/catalog/api.ts` |
| `src/lib/api/dashboard.ts` | M10 | extend | `features/workbench/api.ts` |
| `src/lib/api/projects.ts` | M01 | reuse_as_is | `features/identity/api.ts` |
| `src/lib/api/quick-collect.ts` | M04 | extend | `features/execution/api.ts` |
| `src/lib/api/runs.ts` | M04 | reuse_as_is | `features/execution/api.ts` |
| `src/lib/api/tasks.ts` | M04 | reuse_as_is | `features/execution/api.ts` |
| `src/lib/api/tiktok-tools.ts` | M04 | reuse_as_is | `features/execution/api.ts` |
| `src/lib/api/datasets.ts` | M12 | reuse_as_is | `features/assets/api.ts` |
| `src/lib/api/credentials.ts` | M03 | extend | `features/connectors/api.ts` |
| `src/lib/collection-policy.ts` | M02 | reuse_as_is | `features/catalog/policy.ts` |
| `src/lib/platforms/catalog.ts` | M02 | reuse_as_is | `features/catalog/catalog.ts` |
| `src/lib/skills/filter-platform-packages.ts` | M02 | reuse_as_is | `features/catalog/filter.ts` |
| `src/lib/run-status.ts` | M04 | reuse_as_is | `features/execution/run-status.ts` |

#### 9.5.4 `apps/web` 报告组件

| 文件 | 行数 | 归属 | 状态 | 处置 |
| --- | --- | --- | --- | --- |
| `apps/web/src/components/reports/report-detail-panel.tsx` | 825 | M07 | extend | 抽取 API 调用与颜色后迁移。83 处 raw hex。 |
| `apps/web/src/components/reports/report-detail-page-workspace.tsx` | 76 | M07 | replace | 薄壳。重写成本低于迁移。 |
| `apps/web/src/components/reports/reports-workspace.tsx` | 1382 | M07 | replace | 页面级工作区。按控制台页面重写。148 处 raw hex。 |
| `apps/web/src/lib/api/reports.ts` | 384 | M07 | extend | 迁到 `features/reports/api.ts`。 |
| `apps/web/src/types/report.ts` | 114 | M07 | extend | 迁到 `features/reports/types.ts`。 |
| `apps/web/src/components/common/workbench-ui.tsx` | 553 | M07 | extend | 只保留报告需要的样式与组件。 |
| `apps/web/src/lib/api/notifications.ts` | 430 | M11 | extend | 迁到 `features/notify/api.ts`。 |
| `apps/web/src/lib/training-data.ts` | 128 | M02 | extend | 迁到 `features/catalog/api.ts`。 |

`apps/web` 没有公网路由。edge 只代理 `console:3001`。见 `configs/deploy/scrapy/edge-nginx.conf:57`。不得把 `apps/web` 当生产入口。

### 9.6 必须删除或必须隔离的代码

#### 9.6.1 必须删除

| 对象 | 位置 | 理由 |
| --- | --- | --- |
| 账户设置死页 | `apps/scraper-console/src/app/settings/account/page.tsx` | 14 行占位。无 API。侧栏无入口。 |
| 未使用的 API 导出 | `src/lib/api/*` 的 `fetchTikTokTools`、`fetchTaskRuns`、`archiveProject`、`fetchExportJob` | `src` 内调用数为 0。删除前确认无动态调用。 |
| `capability_discovery` 路由 | `api/routes/capability_discovery.py` | router 未挂载。生产 404。 |
| `capability_governance` 专用路由 | `api/routes/capability_governance.py` | router 未挂载。发布能力改用受控脚本或 M02 管理接口。 |
| `browser_structure_diagnostic` | `services/browser_structure_diagnostic.py` | 只被测试导入。src 无调用方。 |
| `disabled_reddit_execution` | `services/disabled_reddit_execution.py` | 只被测试调用。 |
| `disabled_youtube_execution` | `services/disabled_youtube_execution.py` | 只被测试调用。 |
| `provider_execution_preflight` | `services/provider_execution_preflight.py` | 无 live 调用路径。 |

#### 9.6.2 必须隔离，不得删除

| 对象 | 位置 | 处置 |
| --- | --- | --- |
| `workflow_execution` 包 | `services/workflow_execution/` | 保留代码。禁止 import。路由已挂载（fixture-only）。 |
| `workflow_execution` 模型 | `models/workflow_execution.py` | 保留表。禁止新依赖。 |
| `workflow_action` 模型 | `models/workflow_action.py` | 保留表。禁止新依赖。 |
| `workflow_executor` 模型 | `models/workflow_executor.py` | 保留表。禁止新依赖。 |
| `workflow_runs` 路由 | `api/routes/workflow_runs.py` | 已挂载（fixture-only）。保留。控制台入口标注 fixture，不得删除。 |
| `repositories/workflow_execution.py` | 同文件 | 只服务 fixture 路由。 |
| `schemas/workflow_*.py` | `schemas/` | 只服务 fixture 栈。 |
| 19 个 dead collector | `collectors/` | 保留代码。目录必须隐藏。 |
| 53 个 policy 拒绝 collector | `collectors/outbound_policy.py:62-117` | 保留策略。不得在目录返回。 |

#### 9.6.3 未跟踪但必须保留的文件

以下文件在当前工作树存在，但未纳入 HEAD。部署当前分支会丢能力。发布前必须提交。

| 文件 | 影响 |
| --- | --- |
| `apps/api/src/data_intelligence_hub/collectors/outbound_policy.py` | 采集准入。丢失后所有执行无策略。 |
| `apps/api/src/data_intelligence_hub/collectors/guarded_http.py` | 受控 HTTP。丢失后 guarded_http 采集器不可用。 |
| `apps/api/src/data_intelligence_hub/models/tiktok_content.py` | 12 张 TikTok 表 ORM。 |
| `apps/api/src/data_intelligence_hub/repositories/tiktok_content.py` | TikTok 读写。 |
| `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py` | TikTok 投影。 |
| `apps/api/src/data_intelligence_hub/services/tiktok_tools.py` | 8 个 TikTok 工具。 |
| `apps/api/alembic/versions/202610190045_tiktok_r1_canonical_tables.py` | 21 张表迁移。 |
| `apps/scraper-console/src/app/tools/tiktok/page.tsx` | TikTok 工作台页面。 |

### 9.7 归属统计

| 类别 | 总数 | reuse_as_is | extend | replace | dead |
| --- | --- | --- | --- | --- | --- |
| collector 模块 | 34 | 14 | 2 | 0 | 18 |
| 路由模块 | 26 | 15 | 7 | 2 | 2 |
| services 实现单元 | 37 | 17 | 12 | 2 | 6 |
| 控制台页面 | 16 | 12 | 3 | 0 | 1 |
| `apps/web` 报告文件 | 8 | 0 | 6 | 2 | 0 |

## 10. 风险与未决

### 10.1 风险

| # | 风险 | 影响 | 处置 |
| --- | --- | --- | --- |
| R1 | 目录三处事实源不一致：303 / 284 / 99（代码口径） | 报告数字不可信 | P1 统一 `tool_catalog`。生产目录 309 / 281 / 70 以 `catalog_digest` 对账。 |
| R2 | 35 条 assertion 全是 `candidate` | planner preview 全部 held | P1 补发布路径。不得改 resolver 放宽。 |
| R3 | 53 个 collector 被策略拒绝 | 目录承诺不可兑现 | 目录隐藏。PRD 已明确不在本期范围。 |
| R4 | `workflow_execution` 是 fixture-only | 工作台无法执行 | P8b 新建执行层。禁止复用。 |
| R5 | 11 个路由模块走 demo workspace | 多租户隔离不真实 | P0 移除兜底。 |
| R6 | `quick_collect` 完全公开 | 公网可滥用 | P3 补 M09 门。 |
| R7 | `TaskRun` 无成本字段 | PRD R6 不达标 | P6 扩列。 |
| R8 | `LLMService` 只有 Mock | 报告无法起草 | K0 新增 adapter。起草结果必须人工批准。 |
| R9 | 邮件实发无生产证据 | 报告只能站内送达 | P8 保持默认关闭。 |
| R10 | 测试基线已全绿：单元 1980 passed / 集成 384 passed，均 0 failed（2026-10-20）。`reports/live-sweep/baseline-pytest-failures.txt` 的 137 条基线已作废 | 回归判定 | 任何新失败都是回归。 |
| R11 | 8 个关键文件未跟踪 | 部署丢能力 | 发布前必须提交。 |
| R12 | TikTok R1 的 21 张表未应用 | T4 只能落原始记录 | P7 前完成迁移与回滚演练。 |
| R13 | MCP 无 token 时 fail-open | 公网可未授权调用 | P8c 改 fail-closed。 |
| R14 | MCP 限额只在内存 | 多 worker 不共享 | P8c 落库或声明单实例。 |
| R15 | `cron` 静默跳过月/日/星期 | 任务不执行且无告警 | P3 返回明确错误。 |
| R16 | `automation_service` 13,537 行 | 合并冲突与回归面大 | P7 拆出 M12。禁止继续扩。 |
| R17 | 报告渲染器只有三段 | PRD 报告无法交付 | P8a 新建合同与两个渲染器。 |
| R18 | `dataset_versions` 依赖 `workflow_runs` | 数据集被 fixture 栈拖住 | P7 解耦。 |
| R19 | 控制台无登录页与 middleware | 任何公网复用都不安全 | P0 补鉴权边界。 |
| R20 | `QuickCollectDrawer` 硬编码 162 个端点 | 150 个端点提交空参数 | P8d 改为 schema 驱动。 |

### 10.2 未决问题

| # | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| Q1 | 目录路径用 `/capabilities` 还是 `/tools` | 前端路由与文档不一致 | 按 PRD 用 `/capabilities`。旧 `/tools/*` 重定向。 |
| Q2 | `run_steps` 与 `workflow_plans` 是否双存 | 计划数据可能重复 | 不双存：计划正文只落 `workflow_plans`/`workflow_versions`；`run_steps` 只存执行步骤。 |
| Q3 | 角色模型用三角色还是 RBAC | 影响 `/settings` 与所有接口 | 首期用 `owner`、`admin`、`member` 三角色。 |
| Q4 | 额度周期按日还是按月 | 影响 `quota_accounts.period` | 首期按日。PRD 要求单次与每日额度分开。 |
| Q5 | 全局 MCP token 何时退役 | 影响外部 agent 接入 | 项目 key 上线后保留一个发布周期。必须写退役日期。 |
| Q6 | 分享报告是否允许匿名访问 | 影响 `report_shares` 与审计 | 首期允许持 token 匿名只读。必须写访问审计。 |
| Q7 | `evidences` 是否改可空 | 影响 claim 模型迁移 | 建议改可空。新旧双写一个周期。 |
| Q8 | 隔离执行栈是否物理删除 | 影响迁移与回滚 | 本期只隔离。删除必须单独立项。 |
| Q9 | `apps/web` 是否继续维护 | 影响前端人力 | 只作迁移源。不新增功能。 |
| Q10 | TikTok R1 是否进首批 | 影响 T4 与 21 张表 | 按 PRD M7b。未应用迁移时 T4 顺延。 |

### 10.3 下一步

1. 先做 P0。移除 demo 兜底，补边界测试，补成员角色。
2. 再做 P1。落 `tool_catalog`，跑三处对账。
3. 然后按 §7 的轨道并行。轨道 A 是关键路径。
4. 每一步必须过 §7.4 的质量门。
5. 本文只定义模块与接口。实现计划必须另写。

---

本文结束。所有路径以仓库根 `/Users/lute/Project/data_scrapy` 为基准。
