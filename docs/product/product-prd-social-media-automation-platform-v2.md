---
title: Data Intelligence Hub PRD V2.0 全社媒自动化数据采集与能力发现平台
doc_type: prd
module: product
topic: social-media-automation-platform
version: "2.0"
status: stable
review_status: approved
created: 2026-07-10
updated: 2026-07-24
approved: 2026-07-10
owner: self
source: human+ai
supersedes: product-prd-data-intelligence-hub-stable.md
design_spec: ../superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
goal_execution: goal_v2_05b_pad_01_application_preflight_locally_complete
---

# Data Intelligence Hub PRD V2.0

## 全社媒自动化数据采集与能力发现平台

> **文档状态**：V2.0 稳定目标基线，已于 2026-07-10 获得用户确认。
>
> **最新 UIX-09 Provider Health 边界（2026-07-24）**：Run 详情新增独立只读 `provider-health-evidence` 子资源，从 frozen Step route plan 精确匹配 Project-scoped RUN-10 最新快照，重验 version/hash chain，按 read time 区分 active/expired routing TTL，并只在 capability/original candidate order 完全一致时呈现 route feedback。默认层展示已观测候选、健康、成功率/P95 与候选顺序建议，digest 折叠；无快照明确为 unobserved。FastAPI focused `21 passed`、full `1225 passed / 73 skipped / 1 warning`，Web focused `10 passed`、full `278 passed`、TypeScript、ESLint、Next `27/27` build 与 Playwright 1440/390、0 error/0 warning 通过。未主动 probe、未改 Catalog/当前 Run route、未自动切路；所有 mutation/state-machine action 仍未开放，UIX-09 保持 partial。
>
> **UIX-09 Checkpoint/Budget 边界（2026-07-24）**：Run 详情新增独立只读 `checkpoint-budget-evidence` 子资源，以 `execution_session_id=workflow_run_id` 组合 RUN-07 已确认分页与 RUN-08 五维账本。Backend/Web 对 ownership、cursor chain、reservation 覆盖、ledger predecessor/cumulative、held reason 和全部 non-live flags fail closed；默认层展示分页/记录、用量/上限与暂停原因，诊断折叠。无证据不解释为可安全恢复或预算无限，`resume_action_available=false`、`budget_override_available=false`。FastAPI focused `13 passed`、full `1223 passed / 73 skipped / 1 warning`，Web focused `9 passed`、full `277 passed`、TypeScript、ESLint、Next `27/27` build 与 Playwright 1440/390、0 error/0 warning 通过。该检查点之后已补 Provider Health 读层；所有 mutation/state-machine action 仍未完成，UIX-09 保持 partial。
>
> **UIX-09 Attempt/Fallback 边界（2026-07-24）**：Run 详情在既有 Shadow 只读层之外，新增独立 `attempt-fallback-evidence` 子资源，组合持久化 Step Attempt 与 FallbackDecision。默认层展示尝试、重试和备用路线门禁结论，error code、幂等 hash、implementation、七段门禁、字段/成本 Evidence 与 digest 折叠；空列表不推断路线可用，且 `switch_executed=false`。FastAPI focused `12 passed`、full `1217 passed / 73 skipped / 1 warning`，Web focused `8 passed`、full `276 passed`、TypeScript、ESLint、Next `27/27` build 与 Playwright desktop/390px/console 0 error 通过。该检查点之后已补 RUN-07/08/10 只读产品组合；retry/resume/cancel/switch action 仍未完成，因此 UIX-09 保持 partial。
>
> **最新 UIX-08 边界**：Planner 已在本地 fixture 产品边界消费 current Version runnable gate，并把 Save、Approve、Activate、`fixture-primary-v1` Run 拆为逐回执动作；未保存草稿、错序状态、非 current Version 与合同 blocker 均 fail closed。Web 定向 `125/125`、Planner `70/70`、TypeScript、ESLint、Next `27/27` build、FastAPI transition `4 passed`、fixture gate/create `3 passed`、Playwright desktop/mobile `2/2` 通过。Run 回执明确 Provider、credential、browser、LLM 与 live authorization 均为 false；未注入 API Key，未调用 Provider/网络、未执行 migration/部署。durable governance、Template lifecycle、RUN-07/08/10 产品组合与 live adapter 仍未完成。
>
> **最新 WFL-001A 边界**：已新增 write-free fixture Run runnable gate，并让现有 `POST .../fixture-runs` 复用同一判断。只有 active Project + active Plan + current Version + 完整 resolved Primary fixture contract 可以创建本地 Run；active 本身不等于 runnable，非 active/non-current 在任何 Run/Step/request ledger 写入前 fail closed。focused `98 passed / 1 warning`、Workflow/Provider-health scoped `745 passed / 62 skipped / 1 warning`、API full `1211 passed / 73 skipped / 7 warnings`、scoped Ruff/Mypy 通过。UIX-08 现已消费该 gate 并开放本地 fixture 动作；RUN-07/08/10 尚未组合，未调用 Provider/网络、未执行 migration/部署。
>
> **最新 RUN-10 边界**：已新增 standalone Provider health fixture kernel。它不主动探测 Provider，只聚合结构化 observation；样本数、成功率与 p95 latency 生成四级健康状态，并将 observation digest、Policy、Evidence、原因和 hash chain 持久化。快照使用短期 routing TTL 与长期 Evidence retention；有效快照可调整后续候选顺序，过期快照不再影响排序但仍保留为版本化 feedback 原始依据。专项 `17 passed`、Workflow/health scoped `718 passed / 1 warning`、API full `1204 passed / 73 skipped / 7 warnings`、Alembic sole source head `202607230042` 通过。Revision 042 未执行 PostgreSQL，kernel 未接产品 Run/Planner/Web 或 live Provider；`health_probe_attempted=false`、`provider_call=false`、`network_call=false`、`production unchanged`。
>
> **最新 RUN-08 边界**：已新增 standalone fixture budget kernel，使用 immutable account 冻结 request/item/quota/cost/time 上限，并用 append-only hash-chained ledger 在 RUN-07 页级 executor 前原子预留。任一维度超限会先留下 blocked evidence 再返回 held，且不进入下一次 executor；crash-after-effect 重启复用 reservation，不重复计费，终态 replay 零新增账本。专项 `14 passed`、Workflow scoped `701 passed / 1 warning`、API full `1187 passed / 73 skipped / 1 warning`、Alembic sole source head `202607230041` 通过。Revision 041 未执行 PostgreSQL，kernel 未接产品 Run API/状态机、Web 或 live Provider；`credential_read_attempted=false`、`provider_call=false`、`network_call=false`、`production unchanged`。
>
> **最新 GOAL-V2-05B 边界**：PAD-04 已新增 provider-neutral fixture runtime：它复用 immutable preflight 上限，对 fake transport 的每次 attempt 先原子预留 request/quota/cost/rate budget，执行 bounded retry 与 timeout，只缓存成功响应且 cache hit 为零预算，并把 blocked/succeeded/cached/failed 终态写入注入的 immutable CallAudit repository interface；显式 cleanup 按 TTL/retention 清理当前 in-memory fake。TDD 聚焦 `9 passed`、PAD-01～04/adapter/runtime/route `106 passed / 1 warning`，API full `1079 passed / 73 skipped / 1 warning`，Ruff lint、Mypy `212 source files` 通过。YouTube/Reddit adapter output contract 与 PAD-02 `youtube_live_execution_disabled` 仍保持。仓库级格式门禁仍被 98 个既有无关文件阻断。`credential_read_attempted=false`、`client_construction=false`、`provider_call=false`、`network_call=false`、`database_write=false`、`production unchanged`；这不是 durable CallAudit、credential reachability、live transport、Provider、CI 或生产证明。
>
> **当前执行边界**：`GOAL-V2-03 status=payload_bound_fixture_materialization_postgres_accepted_live_provider_pending`。已实现 server-registered offline payload envelope、lineage-preview v2 和 authenticated/idempotent materialization POST，本地 SQLite 证明 RawRecord/DatasetVersion/ledger 原子写、rollback 与 exact replay。API full `976 passed / 72 skipped / 6 warnings`；warnings 为 1 个既有 passlib deprecation 和 5 个既有 retention 测试的 aiosqlite event-loop-close warnings。Alembic source head 为 `202607170034`，精确授权目标 `127.0.0.1:55367/local_workflow_lineage_test` 已通过 `033→034→033→034` 与 PostgreSQL `13/13`，cleanup head 034 且相关业务表零行。`provider_call=false`、`DAT-003=fixture_only`、`production unchanged`；这些证据不等于 live Provider、real API、CI、共享/生产数据库、部署或 live execution 验收。
>
> **技术设计**：原设计稿已由提交 `b339f45` 删除，可从 `b339f45^` 恢复；当前需求追踪见 [V2.0 需求追踪账本](./product-prd-social-media-automation-platform-v2-traceability.md)。

## 1. 产品定义

### 1.1 一句话定位

Data Intelligence Hub V2.0 是一个面向品牌和市场运营人员的全社媒自动化数据采集与洞察平台。用户配置品牌、品类、竞品、话题、账号和平台后，系统自动匹配经过验证的 API、采集工具和浏览器能力，形成透明的周期工作流，并持续交付可追溯的数据、异动预警、VOC 洞察和周期简报。

### 1.2 产品范式

V2.0 从“平台化采集工作台”升级为三层产品：

1. **业务结果层**：监测项目、异动预警、VOC、趋势、竞品比较和简报。
2. **自动化工作流层**：关键词检索、链接发现、批量解析、增量采集、Fallback、质量检查和交付。
3. **能力供给层**：官方 API、TikHub Endpoint、Apify Actor、自托管 Collector、Browser、Skill、MCP 与 Agent。

用户购买和使用的是稳定的数据结果。API、Actor、浏览器和 AI 工具是系统内部可替换、可评估、可审计的供给能力。

### 1.3 北极星目标

构建一个覆盖全社媒平台的自动化数据基础设施，使品牌运营人员无需理解每个平台的 API、配额、Actor、浏览器和数据合同，也能稳定完成：

- 品牌声量与口碑监测
- 品类趋势与消费者需求发现
- 竞品账号、内容和活动追踪
- 关键词到链接再到内容的批量解析
- 评论和对话的 VOC 分析
- 采集 API 与 AI 工具的持续发现和治理

### 1.4 V2.0 产品承诺

1. 自动化执行始终基于可见、版本化的 `WorkflowPlan`。
2. 每条数据和洞察都能追溯到采集路线、RawRecord 与 Evidence。
3. 每个平台的能力边界通过“平台 x 数据访问通道”矩阵公开表达。
4. 自动路由只使用满足证据、权限、预算和政策门禁的能力。
5. 外部 Provider 可以替换，业务工作流和标准数据合同保持稳定。

## 2. 背景与问题

### 2.1 用户问题

品牌和市场运营人员通常同时面临以下问题：

- 平台分散，同一监测主题需要跨 YouTube、Reddit、X、Instagram、Threads、TikTok 和 LinkedIn 执行。
- 官方 API、第三方 API、Actor、网页、浏览器和导出文件能力边界不同。
- 单一采集方式受到配额、地区、字段、时效和政策变化影响。
- 一次性采集容易完成，稳定的周期运行、增量更新和证据追溯较难。
- 采集结果与预警、VOC、趋势、简报之间缺少统一血缘。
- 市面上存在大量 API、Actor、Skill、MCP 和 Agent，缺少持续发现、核验和治理机制。

### 2.2 当前产品基础

当前仓库已经形成以下基础：

- Auth、Workspace、Project
- Source、CollectionTask、TaskRun、RawRecord
- Entity、Snapshot、Signal、Intelligence、Evidence
- Dataset、Export、Drift、Alert、Report、Notification
- GitHub、Generic Web、Public Feed、Manual JSON 和 Ecommerce Collector
- BrowserDiagnostic 与海外社媒 Catalog、Readiness、Gate、Fixture、Preview
- 独立 API Market 页面和社媒 Adapter Plan 页面

V2.0 将复用这些资产，新增能力矩阵、MonitoringScope、WorkflowPlan V2、Capability Resolver、Query Compiler、Fallback、Shadow 和统一能力发现工作流。

### 2.3 市场样本

| 样本 | 核心能力 | V2.0 吸收方向 |
|---|---|---|
| TikHub API 市场 | 原子 Endpoint、参数、价格、RPS、日志、数据集 | Endpoint 供给、平台和资源筛选、详情下钻 |
| Apify Store | Actor、输入、运行、任务、调度、存储、监控、集成 | 可执行组件生命周期、任务化与集成 |

V2.0 在两者之上提供业务目标、统一数据合同、能力矩阵、自动选路、证据治理和洞察交付。

## 3. 目标用户

### 3.1 首要用户：品牌与市场运营人员

典型职责：

- 监测品牌、产品线、品类和竞品声量
- 跟踪社媒活动、内容表现和用户反馈
- 识别舆情异动、消费者痛点和趋势机会
- 生成周报、月报和专项分析

核心诉求：

- 用业务语言创建监测任务
- 自动运行，减少逐平台手工操作
- 能理解数据来源、覆盖范围和局限
- 预警和洞察可以回到原始内容
- 成本和运行状态可控

### 3.2 次要用户：商业分析与消费者洞察人员

核心诉求：

- 使用标准化数据集进行跨平台比较
- 检查关键词归因、数据覆盖和证据
- 深入分析 VOC、趋势和竞争格局
- 导出结构化数据和周期报告

### 3.3 管理用户：采集运营与能力管理员

核心诉求：

- 维护平台能力矩阵
- 核验 Provider、Endpoint、Actor 和 Browser 能力
- 管理凭证、预算、限流、政策和保留策略
- 查看 Fallback、Schema 漂移和 Provider 健康状态

### 3.4 第一版本权限假设

V2.0 复用现有 Workspace 和 Project 权限模型。精细 RBAC 暂缓；需要审批的操作由 Workspace Owner 或具备等价管理权限的用户确认。

## 4. 用户任务与核心场景

### 4.1 JTBD-01：周期市场监测

当我负责一个品牌或品类时，我希望配置关键词、账号、平台和周期，让系统持续采集并通知重要变化，从而减少逐平台搜索和整理。

### 4.2 JTBD-02：关键词与链接批量解析

当我有一批关键词或 Seed URL 时，我希望系统跨平台发现、去重、分类和解析内容，并保存为数据集，从而快速完成专项研究。

### 4.3 JTBD-03：VOC 洞察

当我需要理解消费者反馈时，我希望系统采集内容、评论和回复，识别主题、情绪、痛点和需求，并让每条结论可回到原始证据。

### 4.4 JTBD-04：竞品追踪

当我关注多个竞品时，我希望系统监测账号、内容、互动和活动变化，并形成可比较的周期视图。

### 4.5 JTBD-05：采集能力发现

当平台能力、价格或工具发生变化时，我希望系统自动收集 API、Actor、Collector、Skill、MCP 和 Agent 信息，生成候选能力并安排核验。

### 4.6 JTBD-06：运行解释与治理

当系统自动选择或切换采集方式时，我希望看到选路原因、预算、限制、替代路线和证据，从而判断结果是否可用。

## 5. 产品目标与非目标

### 5.1 V2.0 目标

| ID | 目标 |
|---|---|
| G-01 | 建立 7 个海外平台的能力矩阵与统一能力合同 |
| G-02 | 支持品牌词、品类词、竞品词和 Seed URL 的混合监测 |
| G-03 | 建立可视、版本化、可模拟的 WorkflowPlan |
| G-04 | 建立 Primary、Fallback 与 Shadow 对账机制 |
| G-05 | 打通关键词检索、链接分类、批量解析和 Dataset 链路 |
| G-06 | 建立 API 与 AI 工具能力发现工作流 |
| G-07 | 打通 YouTube 与 Reddit 的首批授权生产链路 |
| G-08 | 交付异动预警、VOC 和周期简报的证据链 |
| G-09 | 把网站压缩为面向品牌运营人员的六个一级入口 |

### 5.2 非目标

- 登录绕过、验证码规避、反检测或风控对抗
- 私信采集、Cookie 导出或未经授权的账号会话复用
- 未授权媒体下载和用户画像聚合
- 未经许可的关系图谱扩张
- 复制 TikHub、Apify 或其他服务的未公开实现
- 让 LLM 在缺少 RawRecord 与 Evidence 时产生事实结论
- 在 V2.0 首版引入大型分布式工作流引擎
- 在 V2.0 首版完成企业计费、多租户隔离或精细 RBAC

## 6. V2.0 发布范围

### 6.1 V2.0 GA 必须交付

1. 7 个逻辑平台、6 个数据访问通道的能力矩阵。
2. 8 类资源、7 类操作、硬门禁和八维评分。
3. CapabilityAssertion、Evidence、Implementation 与 Health Snapshot。
4. MonitoringScope 和品牌词、品类词分轨。
5. 确定性词典、LLM 候选扩展和平台查询编译器。
6. WorkflowPlan V2、RoutePlan、Fallback 和 Shadow 规则。
7. 周期监测与关键词/链接批量解析两条主链路。
8. Browser Capability Discovery、Content Collection 和 Verification Probe。
9. YouTube 与 Reddit 的 Fixture、Readiness、授权小规模运行路径。
10. X、Instagram、Threads、TikTok、LinkedIn 的 Catalog、Fixture 和 Readiness 路径。
11. Dataset、Alert、VOC 和 Brief Preview 的证据链。
12. 六个一级入口和完整移动端导航。

### 6.2 V2.x 后续扩展

- X 正式采集路线
- Instagram 与 Threads 授权资产路线
- TikTok Research 授权路线
- LinkedIn Community Management 授权路线
- 中文社媒平台能力矩阵和官方开放能力
- 多 Workspace 企业治理、精细 RBAC 与计费
- 更大规模 Worker 和独立工作流引擎评估

### 6.3 平台交付级别

| 平台 | V2.0 必需交付级别 | Live 边界 |
|---|---|---|
| YouTube | Matrix + Fixture + Readiness + Authorized Small Run | 单独审批 |
| Reddit | Matrix + Fixture + Readiness + Authorized Small Run | 单独审批，遵守用途与保留边界 |
| X | Matrix + Fixture + Readiness + Cost Gate | 合同与预算就绪后审批 |
| Instagram | Matrix + Fixture + Readiness | 仅授权专业账号或自有资产 |
| Threads | Matrix + Fixture + Readiness | 仅授权范围 |
| TikTok | Matrix + Research Readiness + Fixture | 资格和用途审批后执行 |
| LinkedIn | Matrix + Application Readiness + Fixture | 产品申请和权限审批后执行 |

## 7. 成功指标

### 7.1 产品采用指标

| KPI | 定义 | V2.0 验收目标 |
|---|---|---|
| KPI-01 Time to First Plan | 从创建项目到生成首个 WorkflowPlan | 可用性测试中位数不超过 10 分钟 |
| KPI-02 Plan Activation Rate | 生成计划后进入激活或保存的项目占比 | 试点期达到 60% |
| KPI-03 Weekly Active Projects | 一周内产生有效 Run 的项目数 | 建立基线并持续上升 |
| KPI-04 Insight Traceback Rate | 可下钻到 Evidence 的洞察占比 | 100% |
| KPI-05 Useful Alert Rate | 用户标记有用的预警占已处理预警比例 | 试点两周后达到 60% |

### 7.2 运行与治理指标

| KPI | 定义 | V2.0 验收目标 |
|---|---|---|
| KPI-06 Route Explainability | Run 可展示选路和约束的比例 | 100% |
| KPI-07 Lineage Coverage | 标准对象能回溯到 RawRecord 和 Provider 的比例 | 100% |
| KPI-08 Policy And Budget Breach | 自动运行越过硬门禁或预算的次数 | 0 |
| KPI-09 Duplicate Side Effects | 相同幂等键产生重复副作用的次数 | 0 |
| KPI-10 Deterministic Planning | 相同版本和输入得到相同 RoutePlan 的比例 | 100% |
| KPI-11 Freshness SLA | 在用户配置窗口内完成有效刷新比例 | 7 天 Canary 达到 95% |
| KPI-12 Credential Exposure | 日志、页面、Dataset 中的明文凭证事件 | 0 |

产品采用类指标需要真实试点样本。缺少样本时只建立埋点和基线，禁止把模拟数据写成真实采用结果。

## 8. 产品信息架构

V2.0 一级导航固定为六项：

1. **工作台**：项目状态、今日异动、新鲜度、采集健康、预警和简报。
2. **监测项目**：品牌、品类、竞品、话题、平台、语言、地区和交付目标。
3. **采集工作流**：Template、Plan、Version、Run、步骤证据和 Fallback。
4. **数据资产**：标准对象、DatasetVersion、质量、来源、导出和保留。
5. **洞察与交付**：Alert、VOC、Trend、Comparison、Brief 和 Delivery。
6. **能力市场**：场景、矩阵、实现、Evidence、Verification 和 Provider Health。

全局顶部保留 Project Selector、Time Range、Search、Notification 和 Create Action。

## 9. 核心用户流程

### 9.1 Flow A：创建周期监测项目

```text
选择业务目标
-> 配置品牌词、品类词、竞品词或话题
-> 添加账号、Seed URL、语言和地区
-> 选择平台、周期和交付目标
-> 生成 WorkflowPlan
-> 查看覆盖、预算、局限和替代路线
-> 保存或激活
-> 周期运行
-> Alert / VOC / Brief
```

验收结果：用户无需选择具体 Provider，也能生成可解释计划；高级视图可以查看 Provider 和技术约束。

### 9.2 Flow B：关键词与链接批量解析

```text
输入关键词或 Seed URL
-> 多平台检索
-> 链接规范化、去重和分类
-> 选择或自动匹配解析能力
-> 批量解析
-> 质量与字段覆盖检查
-> Dataset Preview
-> 保存数据集或升级为周期计划
```

验收结果：每条内容保留 `matched_scope_id`、`matched_term`、`match_reason` 和解析路线。

### 9.3 Flow C：自动路由与 Fallback

```text
Run 开始
-> 硬门禁
-> Primary 执行
-> 质量检查
-> 满足切换条件时评估 Fallback
-> 再次执行门禁
-> 切换或降级
-> Shadow 抽样对账
-> 完成并记录路线
```

验收结果：切换后不覆盖来源；用户可见触发原因、字段差异和额外成本。

### 9.4 Flow D：能力发现与核验

```text
API 市场 / Actor Store / 官方文档 / GitHub
-> Browser Discovery
-> 结构化解析
-> Candidate Assertion
-> Evidence
-> 自动检查或人工核验
-> Verified / Partial / Blocked
-> 发布到矩阵
```

验收结果：Candidate 可以展示，但不能直接进入自动运行路线。

### 9.5 Flow E：洞察下钻

```text
Alert / VOC / Brief
-> Signal 或 Topic
-> 标准化对象
-> RawRecord
-> Provider / Method / WorkflowRun
-> Evidence
```

验收结果：所有产品结论具备完整回溯路径。

## 10. 功能需求

优先级定义：

- `P0`：V2.0 GA 必须交付。
- `P1`：V2.0 试点后优先扩展。
- `P2`：明确暂缓。

### 10.1 Project 与 MonitoringScope

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| PRJ-001 | P0 | 复用现有 Project 作为监测项目根对象 | 不新增平行项目表，现有项目数据继续可用 |
| PRJ-002 | P0 | 一个 Project 支持多个 MonitoringScope | 可同时保存品牌、品类、竞品、话题和 Campaign |
| PRJ-003 | P0 | MonitoringScope 支持别名、包含词和排除词 | 保存后可生成版本化查询输入 |
| PRJ-004 | P0 | 支持官方账号、Seed URL、语言、地区和平台 | 计划预览中展示其影响范围 |
| PRJ-005 | P0 | 品牌词使用 Precision-first，品类词使用 Recall-first | 测试覆盖同名品牌和宽泛品类场景 |
| PRJ-006 | P1 | 支持 Scope 模板复制 | 复制产生新 ID 并保留来源版本 |

### 10.2 Query 与关键词治理

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| QRY-001 | P0 | 提供确定性词典层 | 标准名、别名、账号和排除词可独立维护 |
| QRY-002 | P0 | Kimi/DeepSeek 生成候选扩展词 | 输出通过 JSON Schema，包含理由与来源 |
| QRY-003 | P0 | Candidate Term 不能直接进入执行 | 需经过评分、冲突检查和预览 |
| QRY-004 | P0 | 提供平台查询编译器 | 同一 Scope 能生成平台特定查询与版本 |
| QRY-005 | P0 | 记录每条结果的匹配原因 | `matched_scope_id`、`matched_term`、`match_reason` 完整 |
| QRY-006 | P1 | 记录词项命中贡献 | 可识别高噪声词和无贡献词 |

### 10.3 能力矩阵与能力市场

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| CAP-001 | P0 | 提供平台 x 数据访问通道矩阵 | 7 个平台和 6 个通道均有显式状态 |
| CAP-002 | P0 | 使用 8 类资源和 7 类操作 | 过滤、详情和 API 使用同一枚举 |
| CAP-003 | P0 | CapabilityAssertion 为原子能力事实 | 可按平台、资源、操作、地区和用途查询 |
| CAP-004 | P0 | 栅格为聚合读模型 | 更新单一 Assertion 无需重写整个栅格 |
| CAP-005 | P0 | 支持 7 种能力状态 | unknown、candidate、verified、partial、blocked、unsupported、deprecated |
| CAP-006 | P0 | 支持硬门禁和八维评分 | 路由先处理门禁，再计算场景评分 |
| CAP-007 | P0 | 每项可执行能力绑定 Evidence | 缺少 Evidence 或核验时间时不可进入 verified |
| CAP-008 | P0 | 前后端使用单一 Catalog 数据源 | API Market 卡片与后端能力计数一致 |
| CAP-009 | P0 | 栅格支持详情下钻 | 可查看资源、操作、实现、局限、证据和 Workflow 使用情况 |
| CAP-010 | P1 | 支持实现比较 | 可按覆盖、成本、稳定、Schema 和证据比较 |

### 10.4 WorkflowPlan 与 RoutePlan

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| WFL-001 | P0 | 支持 Template、Plan、Version、Run、StepRun | 所有 Run 绑定不可变 WorkflowVersion |
| WFL-002 | P0 | 生成完整 WorkflowPlan Preview | 展示步骤、平台、预算、门禁和输出 |
| WFL-003 | P0 | 相同版本和输入生成确定性 RoutePlan | 重复生成结果一致 |
| WFL-004 | P0 | 支持场景路由策略模板 | 默认 `market_monitoring_balanced` |
| WFL-005 | P0 | 每个平台、资源和操作拥有独立 RoutePlan | 可以独立选择 Primary 和 Fallback |
| WFL-006 | P0 | 保存 Required 与 Optional Fields | 降级时明确字段差异 |
| WFL-007 | P0 | 用户可查看完整计划 | 自动模式也能查看选路和替代路线 |
| WFL-008 | P1 | 支持计划克隆和版本比较 | 可显示关键词、平台、路线和预算差异 |

#### 当前 GOAL-V2-03 实现边界（2026-07-16）

已实现的是 Project-scoped WorkflowPlan 资产保存与不可变 Version 历史：用户先获得服务端确定性 Preview，再显式 Save；服务端重算输入并校验 Fingerprint，保存 v1 或后续 Version。当前 Version 相同语义返回 `semantic_no_op`，A→B→A 创建新 Version；历史 Version 不被覆盖。用户可查看 Saved Plans、当前 Preview、Version history 和服务端结构化 Compare。

此状态满足 WFL-002、WFL-003、WFL-004、WFL-005、WFL-006、WFL-007 的规划/资产部分，以及 WFL-008 的版本比较与本地 Plan clone 部分；PRJ-006 的 Scope template copy 也已在 API/Web source 与 SQLite fixture 层实现。Clone 会从指定冻结 Version 生成新 Plan/v1 并保留 source Plan/Version provenance；Scope copy 生成独立 template，不增加 canonical Scope。revision `202607160030` 尚未执行 Alembic/PostgreSQL，因此该 slice 仍是 L2 local implementation，不宣称 shared/production schema acceptance。GOAL-V2-03 Planner 产品路径仍不提供 `WorkflowRun`、Activate、Run、Pause、Schedule、Archive、Provider 调用或自动 Fallback 执行；历史 `从 vN 在 Planner 中继续` 仍是编辑草稿路径。GOAL-V2-05A 的后端 fixture-only Run kernel 是独立本地合同，不能从“已保存”或“已克隆”推导为产品可执行。

### 10.5 执行、Fallback 与 Shadow

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| RUN-001 | P0 | 正常状态只运行 Primary | 无切换条件时不产生备用调用 |
| RUN-002 | P0 | 支持有界重试 | 只覆盖超时、限流和短暂网络中断 |
| RUN-003 | P0 | Fallback 前重新执行全部门禁 | Policy、Credential、Budget 和字段合同均有记录 |
| RUN-004 | P0 | 支持显式降级 | Run 状态为 degraded，并列出缺失字段 |
| RUN-005 | P0 | 支持小样本 Shadow 对账 | 样本量受预算控制，结果记录等价性判断 |
| RUN-006 | P0 | 所有步骤支持幂等键 | 相同键不产生重复副作用 |
| RUN-007 | P0 | 支持断点游标和分页恢复 | 中断后从最近已确认游标继续 |
| RUN-008 | P0 | 成本达到上限时进入 held | 不再产生新的外部调用 |
| RUN-009 | P0 | `empty_valid` 独立表达 | 真实零结果不进入采集异常状态 |
| RUN-010 | P1 | Provider Health 影响后续选路 | 健康快照改变候选排序并保留原因 |

#### 当前 RUN-005 实现边界（2026-07-23）

已实现 fixture-only Shadow kernel：只有显式注册且同时绑定 Primary/Fallback payload
的 profile 才执行双路对账；样本量同时受冻结 `sample_rate` 与 `max_items` 限制，
比较 Required Field 的标准化语义值，并把逐 Step 等价性、差异 Evidence 和后续路由
建议写入 append-only `workflow_shadow_comparisons`。结果通过只读
`GET /api/projects/{project_id}/workflow-runs/{run_id}/shadow-comparisons` 暴露。
`eligible_for_governance_review` 仅是人工治理输入，数据库约束固定
`catalog_mutation_applied=false`、`route_ranking_mutation_applied=false`；不会自动修改
Catalog 或排序。Web Run 详情现已消费该读接口，以业务摘要、折叠诊断证据和显式无证据
空态呈现，不提供自动切换或运行按钮。revision `202607230039` 仅为 source，未执行真实
PostgreSQL，且本切片没有 API key、Credential、Provider、网络、RawRecord 或 Dataset
调用，不能作为 live Shadow、完整 UIX-09 或 AT-04 验收。

#### 当前 RUN-002/003 产品读取边界（2026-07-24）

新增只读
`GET /api/projects/{project_id}/workflow-runs/{run_id}/attempt-fallback-evidence`，从
tenant-scoped 持久化 `StepRunAttempt` 与 `WorkflowFallbackDecision` 生成严格的
`workflow_attempt_fallback_evidence.v1`。响应校验 attempt 必须按 Step 从 1 连续编号，
Fallback 必须包含 trigger、policy、credential、budget、fields、evidence、approval
七段有序门禁，并保持 Run/Step/Plan/Version ownership、outcome、approval 与计数一致。
所有 fixture/read boundary 均为 false，`switch_executed=false`，该接口不触发 retry、
resume、Provider call 或 route switch。

Web Run 详情按业务层优先呈现每个 Step 的尝试结果、重试次数、主路线失败和备用路线判断；
错误码、attempt key hash、Primary/Fallback implementation、门禁 code、字段/成本 Evidence
与 decision digest 进入折叠诊断层。无 Fallback Decision 时明确表示证据缺失，而不是备用
路线可用。该读取层补齐 RUN-002/003 的产品可见性，不证明 live Provider 幂等/重试、真实
Fallback fresh evidence、Revision 036~038 PostgreSQL 或任何执行动作。

#### 当前 RUN-007 实现边界（2026-07-23）

已实现独立的 fixture-only per-step pagination checkpoint kernel。每个已确认页以
append-only `workflow_step_checkpoints` 保存 immutable WorkflowVersion/Step 身份、
cursor-before/after、page output digest、checkpoint digest、Evidence 和确定性
side-effect key；每页使用独立事务确认。新 AsyncSession 会校验完整 cursor/digest 链，
从最后确认页的 next cursor 继续，终态重放不调用 executor、不追加 checkpoint。
模拟“物理副作用完成但 checkpoint 尚未提交”的进程退出测试证明，重启会向 fixture
executor 传递相同 side-effect key，因而不会重复物理 effect；这项保证要求未来 live
Provider/adapter 对该 key 提供真实幂等语义，当前不能外推为所有 Provider 的
exactly-once 保证。

revision `202607230040` 仅为 source，未执行 PostgreSQL。本切片没有接入现有
fixture-run API、Run 状态机、Provider、Credential、网络、RawRecord 或 Dataset；产品
Run resume、UIX-09 展示与 live adapter binding 仍是后续集成门。

### 10.6 关键词检索、链接和批量解析

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| BATCH-001 | P0 | 支持关键词和 Seed URL 混合输入 | 同一任务可同时使用两类输入 |
| BATCH-002 | P0 | 支持多平台检索 | 输出保留平台查询与命中范围 |
| BATCH-003 | P0 | 支持 URL 规范化和去重 | 分享链接、参数链接和规范链接可建立关联 |
| BATCH-004 | P0 | 支持平台与资源类型分类 | 无法识别的链接进入明确队列 |
| BATCH-005 | P0 | 按 Capability Resolver 批量解析 | 每条链接记录 Implementation 和 RoutePlan |
| BATCH-006 | P0 | 输出字段质量和覆盖报告 | Required Field 缺失可见 |
| BATCH-007 | P0 | 保存为 Dataset 或升级为周期计划 | 两条后续路径均可追溯到原任务 |

### 10.7 Browser 能力

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| BRW-001 | P0 | Browser Capability Discovery | 可解析市场、文档和仓库形成 Candidate Assertion |
| BRW-002 | P0 | Browser Content Collection | 仅处理公开或明确授权页面 |
| BRW-003 | P0 | Browser Verification Probe | 能检测 DOM、字段和能力漂移 |
| BRW-004 | P0 | Browser Evidence | 保存来源 URL、时间、Hash 和结构化摘要 |
| BRW-005 | P0 | 授权浏览器会话进入审批 | 必须提供 Scope、保留和删除策略 |
| BRW-006 | P0 | 禁止越界浏览器行为 | 验收覆盖验证码、Cookie、登录绕过和未授权接口阻断 |

### 10.8 Provider 与 Adapter

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| PAD-001 | P0 | 所有 Provider 通过 PlatformAdapter | 业务服务不直接消费第三方响应 |
| PAD-002 | P0 | Credential 只从环境变量或 Secret Manager 读取 | 日志和 API 响应无明文值 |
| PAD-003 | P0 | Provider 支持 Fixture Replay | 无外网条件下可运行契约测试 |
| PAD-004 | P0 | Provider 调用经过 Budget 和 Rate Limit | 审计中有请求、成本和限流记录 |
| PAD-005 | P0 | YouTube 与 Reddit 首批适配 | Fixture、Readiness 和授权小规模路径完整 |
| PAD-006 | P0 | 其余海外平台提供 Fixture 与 Readiness | 不把 Readiness 表述为真实采集完成 |
| PAD-007 | P1 | Apify 与 TikHub 作为可选 Provider | 不承担唯一数据路线 |
| PAD-008 | P1 | 自托管开源组件可插拔 | 许可证和安全核验通过后进入 Catalog |

### 10.9 数据资产与标准化

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| DAT-001 | P0 | 支持 social_raw.v1 | 保留来源、原始 Hash 和观察时间 |
| DAT-002 | P0 | 支持 Post、Comment、Creator、Topic 标准对象 | 各对象通过 Schema 验证 |
| DAT-003 | P0 | 保留完整采集血缘 | Workflow、Run、Step、Provider、RawRecord 和 Evidence 可关联 |
| DAT-004 | P0 | 原始记录不可覆盖 | 重采产生新观察或显式去重关系 |
| DAT-005 | P0 | 默认作者策略为 hashed 或 dropped | 明文保留需要审批标记 |
| DAT-006 | P0 | Relationship Graph 默认禁用 | 路由和 UI 均显示受限状态 |
| DAT-007 | P0 | DatasetVersion 支持来源和字段合同 | 导出可回溯到 TaskRun 与 RawRecord |
| DAT-008 | P1 | 支持跨 Provider 实体对齐 | 保留置信度和原始标识来源 |

### 10.10 洞察、预警与简报

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| INS-001 | P0 | 异动预警基于确定性 Signal | 阈值、时间窗和 Evidence 可见 |
| INS-002 | P0 | VOC 输出主题、情绪、痛点和需求 | 每个条目引用 RawRecord 和 Evidence |
| INS-003 | P0 | 支持品牌、品类和竞品分轨分析 | 结果可按 MonitoringScope 过滤 |
| INS-004 | P0 | 支持周期 Brief Preview | 包含覆盖、关键变化、证据和局限 |
| INS-005 | P0 | LLM 输出通过 JSON Schema | Schema 未通过时不发布正式洞察 |
| INS-006 | P0 | 默认 `allow_ai_training=false` | Policy 和审计中可见 |
| INS-007 | P1 | 用户可以标记预警有用性 | 形成 Useful Alert Rate 指标 |

### 10.11 UI 与交互

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| UI-001 | P0 | 一级导航压缩为六项 | 桌面端和移动端一致 |
| UI-002 | P0 | 工作台提供两个主入口 | 创建监测项目、批量检索与解析 |
| UI-003 | P0 | 品牌运营视图隐藏工程术语 | 高级视图仍可查看完整合同 |
| UI-004 | P0 | 能力市场支持场景、矩阵、列表三种视图 | 三者读取同一后端 Catalog |
| UI-005 | P0 | 矩阵栅格尺寸稳定 | 状态和标签变化不引发布局跳动 |
| UI-006 | P0 | 栅格详情使用侧边抽屉 | 无嵌套卡片堆叠 |
| UI-007 | P0 | WorkflowPlan 提供简单和完整视图 | 两种视图显示同一版本 |
| UI-008 | P0 | 洞察可以下钻 Evidence | 不离开项目上下文 |
| UI-009 | P0 | 375px 与 1440px 视口通过验收 | 无内容遮挡和不可恢复横向溢出 |
| UI-010 | P1 | 支持键盘导航和基础无障碍 | 核心流程满足自动化可访问性检查 |

### 10.12 治理、审计和自动审批

| ID | Priority | 需求 | 验收标准 |
|---|---|---|---|
| GOV-001 | P0 | Verified、凭证就绪和门禁通过后可自动执行 | Audit 记录自动批准依据 |
| GOV-002 | P0 | 新 Provider、用途、预算和敏感范围变化进入审批 | 未审批状态保持 held |
| GOV-003 | P0 | 每次调用记录 CallAudit | 包含 Provider、Operation、请求量和响应元数据 |
| GOV-004 | P0 | 支持 Retention 与 Delete Policy | WorkflowVersion 冻结策略版本 |
| GOV-005 | P0 | Provider Call 默认关闭 | 无授权时 Fixture 和 Preview 仍可运行 |
| GOV-006 | P0 | Production Change 独立授权 | 本地验证不能替代部署授权 |

## 11. 能力矩阵规格摘要

### 11.1 X 轴：平台

YouTube、Reddit、X、Instagram、Threads、TikTok、LinkedIn。

### 11.2 Y 轴：数据访问通道

1. 官方或授权 API
2. 授权合作数据服务
3. 公开页面或 Feed
4. 授权浏览器采集
5. 托管且机制未完全披露的采集服务
6. 授权导出或文件导入

### 11.3 资源词表

`content`、`conversation`、`creator`、`topic`、`metrics`、`media_live`、`commerce_ads`、`relationship_graph`。

### 11.4 操作词表

`resolve_detail`、`search_discover`、`list_enumerate`、`monitor_incremental`、`backfill_history`、`batch_parse`、`export_download`。

### 11.5 状态

`unknown`、`candidate`、`verified`、`partial`、`blocked`、`unsupported`、`deprecated`。

### 11.6 硬门禁

Policy、Auth、Purpose、Region、Data。

### 11.7 八维评分

Coverage、Freshness、History、Reliability、Schema Stability、Cost Efficiency、Maintainability、Evidence Confidence。

## 12. 核心产品对象

| 对象 | 作用 |
|---|---|
| Project | 现有业务项目根对象 |
| MonitoringScope | 品牌、品类、竞品、话题和 Campaign 范围 |
| QueryTerm | 确定性、候选、激活或停用词项 |
| CapabilityImplementation | Endpoint、Actor、Collector、Browser、MCP 等具体实现 |
| CapabilityAssertion | 平台、资源、操作和约束下的原子能力事实 |
| CapabilityEvidence | 官方文档、市场、仓库、Fixture 或授权运行证据 |
| ProviderHealthSnapshot | Provider 健康、漂移和运行信号 |
| WorkflowTemplate | 可复用场景模板 |
| WorkflowPlan | 项目级完整计划 |
| WorkflowVersion | 不可变执行版本 |
| RoutePlan | 平台、资源和操作的选路 |
| WorkflowRun | 一次运行 |
| StepRun | 一步运行及证据 |
| FallbackDecision | 路线切换、降级和原因 |
| RawRecord | 原始事实入口 |
| DatasetVersion | 结构化交付资产 |
| Social Object | Post、Comment、Creator、Topic 等标准对象 |
| Signal | 确定性变化 |
| VOC Item | 证据约束的用户声音条目 |
| Brief | 周期交付资产 |

## 13. 状态模型

### 13.1 Capability 状态

```text
unknown
-> candidate
-> verified | partial | blocked | unsupported
-> deprecated
```

### 13.2 WorkflowPlan 状态

```text
draft -> previewed -> approved -> active -> paused -> archived
```

这是 V2.0 完整产品生命周期目标。当前 GOAL-V2-03 Save/clone/Template instantiate 均创建 `previewed` Plan；本地 lifecycle foundation 已提供受限的 `draft→previewed→approved→active→paused→archived` 以及 `paused→active` transition contract、SQLite service/route、append-only WorkflowTemplate Revision 与 immutable Plan/Version lineage，但尚未提供生命周期 UI 或执行授权。`planning_status=resolved | partially_resolved | held` 是 Version 的规划结果，不等于 Plan 生命周期；`partial` 只属于 Route/Step 层。`active` 仍不是 runnable；GOAL-V2-05A 仅在后端 fixture-only 路径创建本地 Run receipt。

### 13.3 WorkflowRun 状态

```text
draft -> ready -> running -> completed
                  -> degraded
                  -> held
                  -> cancelled
```

### 13.4 QueryTerm 状态

```text
candidate -> active | rejected -> deprecated
```

## 14. 非功能需求

### 14.1 性能

- 能力矩阵在 10,000 条 Assertion 测试数据下，筛选和首屏响应目标为 p95 小于 2 秒，不包含外部网络时间。
- 不含 LLM 调用的 WorkflowPlan Preview 目标为 p95 小于 3 秒。
- 长任务通过异步 Run 返回，不阻塞 HTTP 请求直至采集完成。

### 14.2 可靠性

- 所有副作用入口支持幂等键。
- 所有 Provider 调用具备 Timeout、Retry Budget、Rate Limit 和 Cost Limit。
- Fallback 切换和降级具备完整 Audit。
- Fixture Replay 不依赖外部网络。

### 14.3 安全

- Credential 不写入数据库业务字段、日志、Fixture、页面或导出文件。
- Browser Session、关系图谱和敏感数据进入审批。
- 所有外部输入按不可信数据处理。
- Provider 响应在标准化前进行 Schema 和大小限制检查。

### 14.4 可观测性

- Run 和 Step 记录耗时、请求量、数据量、成本、限流、Route 和 Evidence。
- Provider Health 提供按平台、实现和 Operation 的状态聚合。
- Schema Drift 自动生成 Verification Task。

### 14.5 可维护性

- 外部组件通过 Adapter 隔离。
- Automation Service 按能力边界逐步拆分，禁止整体重写。
- 首版继续使用现有 APScheduler、TaskRun 和数据库锁。
- 自动生成文件只能从源合同重新生成。

### 14.6 可访问性与响应式

- 核心控件具备可访问名称和键盘焦点。
- 表格和矩阵在窄屏切换为可筛选列表或分段视图。
- 文本、状态、按钮和抽屉在目标视口无重叠。

## 15. 数据、隐私与合规

### 15.1 数据原则

- 公开数据、授权数据和敏感数据使用独立 Data Gate。
- 作者信息默认 dropped 或 hashed。
- 明文作者保留需要单独授权。
- RawRecord 不可覆盖，删除遵循 Retention 和 Delete Policy。

### 15.2 LLM 原则

- Kimi/DeepSeek 用于候选扩词、结构化解析和证据约束洞察。
- API key 仅通过环境变量或 Secret Manager 注入。
- 输出必须通过 JSON Schema。
- 正式结论必须绑定 RawRecord 和 Evidence。
- 默认 `allow_ai_training=false`。

### 15.3 统一禁止项

- 私信
- 登录绕过
- 验证码规避
- 反检测
- Cookie 导出
- 未授权关系图谱
- 未授权媒体下载
- 深度用户画像合并
- 未披露私有接口的逆向调用

## 16. 开源复用要求

### 16.1 原则

1. 官方 SDK 和官方 OpenAPI 优先。
2. 成熟社区组件优于自研通用能力。
3. 只编写业务合同、Adapter、Normalizer 和必要 Glue Code。
4. 组件必须通过许可证、维护、安全、异步兼容和替换成本核验。
5. Star 数只作为辅助信号。

### 16.2 实施前必须核验的组件类别

- YouTube 官方 API Client
- Reddit OAuth Client
- X API Client
- Meta Graph API Client 或生成式 REST Client
- TikTok Research API Client 或 REST Adapter
- LinkedIn REST Client
- Apify 官方 Client
- OpenAPI Parser 与 Validator
- JSON Schema Validator
- OAuth、Retry、Rate Limit、Cache 与 Circuit Breaker

具体包名、版本和许可证在对应 `/Goal` 开始时通过官方文档与 GitHub 当前状态核验。

## 17. 测试与验收

### 17.1 测试层级

- Unit：Schema、Catalog、Query、Resolver、Gate、Normalizer。
- Contract：所有 PlatformAdapter 与 CapabilitySourceAdapter。
- Fixture Integration：Primary、Fallback、Shadow、Browser DOM。
- API Integration：Project、Scope、Plan、Run、Dataset、Evidence。
- E2E：周期监测、批量解析、能力发现、洞察下钻。
- UI：桌面端、移动端、键盘和可访问性。
- Authorized Live：每个平台独立审批的小规模只读路径。

### 17.2 V2.0 验收场景

| ID | 场景 | 必须证明 |
|---|---|---|
| AT-01 | 创建品牌与品类混合监测项目 | Scope、Query、Plan 和预算完整 |
| AT-02 | 关键词到多平台链接到 Dataset | 去重、分类、解析和血缘完整 |
| AT-03 | Primary 进入降级并选择 Fallback | 门禁、字段差异、成本和 Evidence 完整 |
| AT-04 | Shadow 小样本对账 | 等价性结果和后续路由影响可见 |
| AT-05 | TikHub/Apify 页面能力发现 | Candidate Assertion 与 Evidence 完整 |
| AT-06 | Candidate 核验进入 Verified | 状态转换、核验人和时间完整 |
| AT-07 | YouTube 授权小规模运行 | Scope、请求量、RawRecord 和清理策略完整 |
| AT-08 | Reddit 授权小规模运行 | OAuth、用途、保留和 Evidence 完整 |
| AT-09 | VOC 与 Brief 下钻 | 每条结论可回溯到 RawRecord |
| AT-10 | 移动端预警与运行状态 | 无关键操作缺失或内容遮挡 |

### 17.3 Live Gate 输入

```text
authorized=true
approval_id
provider
endpoint_scope
keyword_account_url_scope
max_requests
max_items
max_cost_usd
retention_hours
delete_policy
allow_ai_training=false
```

## 18. 发布策略

### 18.1 证据等级

| 等级 | 含义 |
|---|---|
| L0 | 推断或待核验候选 |
| L1 | 公开文档、仓库或本地运行时可见 |
| L2 | Fixture、单元、集成、Dry Run 或本地 E2E |
| L3 | 生产只读观测 |
| L4 | 明确授权的真实调用或写入，并具有审计和清理记录 |

### 18.2 发布顺序

1. Schema 与 Catalog
2. Read-only API 与 Matrix UI
3. WorkflowPlan Preview 与 Fixture Run
4. Browser Capability Discovery
5. YouTube 与 Reddit 授权小规模运行
6. Alert、VOC 与 Brief Canary
7. V2.0 GA

### 18.3 回滚原则

- 每个 Goal 形成独立可回滚提交和迁移。
- 新 Catalog 和 WorkflowPlan 先并行读，迁移稳定后关闭旧静态读路径。
- 数据库迁移必须提供 Downgrade 或明确恢复方案。
- Live Provider 可以单独禁用，不影响 Fixture、Plan 和历史数据访问。

## 19. `/Goal` 分批执行包

以下 Goal 由独立规格、计划和证据推进；状态不代表部署或生产验收。

- GOAL-V2-01: complete (local contract evidence)
- GOAL-V2-02: locally_complete (local validation and mock E2E only)
- GOAL-V2-03: payload_bound_fixture_materialization_postgres_accepted_live_provider_pending (local API/SQLite/Web + exact disposable PostgreSQL evidence; live Provider pending)
- GOAL-V2-04A: fixture discovery Preview locally_complete (L2 Fixture/local only)
- GOAL-V2-04B: capability governance locally_complete (L2 local + exact disposable PostgreSQL only)
- GOAL-V2-04 overall: local discovery/governance complete；live capture、Provider execution 与后续 Goal 仍 queued

### GOAL-V2-01：产品与能力合同底座

**Status**: complete

**Objective**：建立 V2.0 词表、Schema、Catalog 与兼容层。

**Scope**：

- Platform、AccessChannel、Resource、Operation、Status
- CapabilityImplementation、Assertion、Constraint、Evidence
- external_provider_catalog.v1 兼容入口
- Fixture 与 Schema 测试

**Exit Gate**：Catalog 单一事实源、迁移方案和全部契约测试通过。

### GOAL-V2-02：能力矩阵与网站导航

**Status**: locally_complete

**Objective**：交付矩阵产品和六入口信息架构。

**Scope**：

- Matrix API 与 Read Model
- 场景、矩阵和列表视图
- 栅格详情、比较和 Evidence
- Sidebar、Project Selector、Mobile Navigation

**Exit Gate**：7 x 6 矩阵有显式状态，桌面端与移动端 E2E 通过。

### GOAL-V2-03：MonitoringScope 与 Workflow Planner

**Control State**：

    GOAL-V2-03 status=payload_bound_fixture_materialization_postgres_accepted_live_provider_pending
    current_batch=independent_review_fix_loop_complete_local_revalidation
    implementation_baseline_reference=1e4cc4863c9629e2ff249edc0f7722dafaaf6831
    phase_2_checkpoint_commit=39c07e9baf12ec2ec8a1a21afc4b4feacffc4d12
    checkpoint_commit_present=true
    database_write=local-test-only
    migration_applied=202607160033 historical exact target only; revision_034_execution_authorization=false
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=local-test-only during PostgreSQL acceptance; cleanup=0
    execution_authorized=false
    live_send=false
    production unchanged
    phase_1_web_mock_e2e=passed
    phase_2_web_mock_e2e=historical passed; static_mock_e2e=72_passed_12_expected_skipped
    persisted_lineage_contract_api_focused=49_passed
    task_15_full_exit_gate=historical
    migration_execution_authorization=consumed_complete_exact_target_only
    plan_lifecycle_transition=local_sqlite_green
    workflow_template_persistence=local_sqlite_api_green
    template_revision_association=local_api_sqlite_web_green
    local_api_full_pytest=976_passed_72_skipped_6_warnings
    lineage_materialization_postgres=13_passed; migration=033_to_034_to_033_to_034; cleanup=head_034_zero_rows
    local_template_sqlite=5_passed
    local_web_full_unit=246_passed; typescript_eslint_build=passed

**Objective**：从品牌词、品类词和 Seed URL 生成可解释 Preview，并将已验证的 Preview 保存为可审计、可比较但不可执行的规划资产。

**Scope**：

- MonitoringScope
- 三层查询模型
- WorkflowPlan V2 与 Versioning
- Capability Resolver 与场景策略
- RoutePlan、Fallback 和 Shadow 规则

**Phase 1 历史基线（L2 Fixture / Mock）**：

- 已实现并注册 write-free `POST /api/projects/{project_id}/workflow-plans/preview`；它只读取当前 workspace 可见且 active 的 Project 与 canonical Capability Catalog，不保存 MonitoringScope、WorkflowPlan、WorkflowVersion 或 WorkflowRun（本条仅限 Planner Preview 路径）。
- 当前流水线为 `MonitoringScopeDraft -> normalize -> Query Compiler -> periodic_monitoring.v1 / batch_research.v1 template -> Capability Resolver -> Catalog Snapshot -> Preview Fingerprint -> WorkflowPlanPreview`。
- canonical Catalog 的 Assertion 仍为 candidate，因此产品路径返回可解释 `held`，不虚构 Primary；Primary、Fallback、Shadow 与 partial 只由测试专用 synthetic Fixture 证明，不写回 canonical Catalog。
- Web 已交付同一 Planner 的周期监测与批量研究双模式向导；简单/高级视图消费同一个后端响应与 Fingerprint，不在前端重算路线。
- Project Selector 仅在一次成功的 Project-scoped Preview（包括 `held` 200）被接受后显示 applied；输入、mode 或 Project 变化会立即恢复为 false。
- 2026-07-13 Phase 1 exit gate：API targeted `240 passed`、API full `439 passed`、Web unit `151 passed`、Web mock E2E `58 passed / 12 expected skipped`、Preview `p95=5.287ms`、Alembic head `202606110026`。这些数字仅是 Phase 1 基线，不替代当前 Phase 2 证据。

**Phase 2 当前实现（本地完成）**：

- 已提供显式 Save、Plan/Version 只读查询、History、Compare 和 Project-scoped MonitoringScope 读取。首次保存创建 `previewed` Plan/v1；后续保存只能新增不可变 Version，Plan 名称和 flow mode 不可变。2026-07-16 增加 Plan clone 与 Scope template copy：前者从冻结 source Version 创建独立 Plan/v1 并保留 source provenance，后者生成新 template ID 且不增加 canonical Scope。
- 2026-07-16 补齐 Plan lifecycle foundation 与 Template Revision association：新增六态状态合同、受限 status-transition route、Project-scoped `WorkflowTemplate` header、append-only `WorkflowTemplateRevision`、tenant-safe CRUD 与 immutable Plan/Version lineage。状态转换只改 Plan `status/updated_at`，不触碰 immutable Version graph；同状态为 write-free no-op，stale expected status 与非法跳转 fail closed。生命周期 UI 与 execution authorization 仍未实现。
- 保存使用 `Idempotency-Key`，服务端重算 Preview 和 Fingerprint；同语义返回 `semantic_no_op`，并发冲突、stale Preview 与 archived Project 保存失败不会覆盖历史或本地草稿。
- MonitoringScope 在 Project 内按语义复用，Version–Scope 关联冻结顺序，QueryTerm 是 Version 级快照。迁移/约束测试仅在已授权 disposable PostgreSQL 15 数据库运行。
- Web 已提供 Save Preview、Saved Plans、Version history、服务端 Compare、Plan clone、Scope template copy、Template transport/mock contracts 与只读 `/automation/runs` fixture history；Template/Run focused `2 + 15`、full unit `246` 通过，TypeScript、ESLint、static build 通过。历史 `从 vN 在 Planner 中继续` 仍是编辑草稿路径。real API persistence E2E 明确未执行。
- Planner 产品路径仍不提供 Activate、Schedule、Archive、Provider、Actor、Browser 或 LLM 操作；`/automation/runs` 仅展示 fixture receipt，不提供 Run/Retry/Cancel/Activate/Schedule 写入口。status-transition 不是 Activate，05A fixture route 不改变 live execution 边界，`held` 与 `active` 仍只是可审计规划/生命周期状态，不是执行批准。

**Exit Gate**：payload-bound fixture materialization 已通过本地 schema/profile/service/API/zero-external/full regression，API full `976 passed / 72 skipped / 6 warnings`，Web `246 passed`，Ruff、full strict mypy、TypeScript、ESLint、26-page mock build 与 Alembic source single-head 通过。6 个 warnings 是 1 个既有 passlib deprecation 和 5 个既有 retention 测试的 aiosqlite event-loop-close warnings。Revision-034 PostgreSQL gate 已仅在精确授权目标通过 `033→034→033→034`、constraint/service concurrency/rollback/cleanup `13/13`；cleanup head 034 且相关业务表零行。`DAT-003` 仍因 live Provider 未实现而只能表述为 `fixture_only`。Template lifecycle UI、live Provider、real API、CI、deploy、共享/生产数据库和 live execution 仍未验收。

### GOAL-V2-04：浏览器能力发现

**Control State（2026-07-15）**：

    GOAL-V2-04A status=goal_v2_04a_fixture_discovery_preview_locally_complete
    GOAL-V2-04B status=goal_v2_04b_capability_governance_locally_complete
    final_exit_gate=passed
    evidence_grade=L2-local
    GOAL-V2-04 overall=local_discovery_and_governance_complete_live_capture_pending
    AT-05=fixture-discovery-local-only
    AT-06=implemented_local
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    database_write=local-test-only
    workflow_run_created=false (Discovery/Governance path; 05A fixture Run is local-test-only)
    candidate_publish_allowed=explicit-governance-permission-only
    ci_dispatch=false
    production unchanged

**Objective**：把 TikHub、Apify、官方文档和 GitHub 供给转为候选能力。

**Scope**：

- BrowserCapabilityDiscoveryStep
- Parser 与 Evidence
- Candidate、Verification、Publication
- Drift Probe

**GOAL-V2-04A 当前实现（本地 Fixture Preview）**：

- 独立的 TikHub、Apify、YouTube official docs、Reddit official docs 结构化快照由固定 Manifest 注册并通过 retrieved-content SHA-256 校验；运行时不接受 URL、HTML、任意路径或上传内容。
- 四个 source-specific pure parser 生成独立的 Proposed Implementation、`unverified` Candidate Assertion、Evidence 与 Diagnostic；canonical Catalog 不作为发现输入。
- `POST /api/capabilities/discovery/preview` 仅执行 AuthContext 读取与离线 Fixture 重放。四来源结果为 4 Sources、7 Candidates、4 Evidence、2 warnings，Preview fingerprint 对输入顺序稳定。
- `/api-market/discovery` 是能力市场的二级 Preview 工作区；六项主导航、Catalog 三视图和 7×6/42-cell 矩阵保持不变。
- 当前 Task 13 证据包括 Web focused unit `39`、mock build `25/25`、desktop/mobile mock Playwright `2/2`、375×812/1440×900、键盘焦点恢复和 `externalRequests=[]`。这仍是 L2 Fixture/UI-test 证据，不是页面实时抓取或产品 Browser 执行。

**GOAL-V2-04B 当前实现（本地治理闭环）**：

- 独立 `capability_governance` bounded context 持久化 DiscoveryBatch、SourceSnapshot、Candidate semantic version、Evidence lineage、VerificationTask/Decision、CatalogSnapshot、PublicationRevision 与 singleton CatalogHead；全局 read/review/publish membership 与 Workspace role 分离。
- Import 只接受注册 Fixture IDs 与 expected server Preview fingerprint，由服务端重建 Candidate/Evidence；exact replay、Evidence refresh 与 semantic drift 分流，Candidate/Evidence/Decision/Revision 保持 immutable。
- Reviewer 通过 version-checked open Task 显式 verify/reject/deprecate；Decision 冻结 reviewer、reviewed_at、reason、Candidate fingerprint、Evidence refs 与 canonical bundle。Verification 不自动发布。
- Publisher 以 expected parent 显式追加完整 content-addressed Catalog snapshot Revision；rollback 追加恢复 Revision，不倒退历史。Catalog、Matrix、Planner 与 Social Provider projection 读取同一 current Catalog，保存的 WorkflowVersion 继续冻结旧 snapshot。
- `/api-market/discovery` 在 Route A Preview 之后提供 Candidate inbox、Evidence dossier、review、publication、rollback、403 与 409 authoritative reload；六项主导航、三种 Catalog view 与 7×6/42-cell read model 不变。
- 精确授权的本机 PostgreSQL 15 数据库 `127.0.0.1:55367/data_scrapy_capability_governance_test`（GOAL-V2-04B 历史目标）已通过 Alembic `027→028→027→028` 与 guarded suite `19/19`，清理后保持 `202606110028`、singleton `global|NULL|0` 和 12 张治理业务表 0 行。未触碰其他数据库；该证据不替代 05A 的 029 目标。

**仍未完成（外部与后续 Goal）**：live page capture、产品 Browser/Provider execution、真实 governor bootstrap、CI、部署、生产验收，以及 CAP-009 的完整 Workflow usage drilldown 和 live DOM drift probe；这些不得由本地治理证据替代。

**Exit Gate**：GOAL-V2-04A 的四来源 Fixture Preview 与 GOAL-V2-04B Candidate→Verified→Published→Rollback 本地治理链均已通过。Task 14 fresh gate 为 repository guards GREEN、API Ruff/mypy `241` files/`696 passed / 51 skipped / 6 warnings`/head `202606110028`、Web unit `238`、两种 build `25/25`、mock E2E `72 passed / 12 expected skipped`；AT-06 为 `implemented_local`。这仍不代表 live capture、CI、deploy、Provider 或 production acceptance。

### GOAL-V2-05A：Fixture Execution Kernel（本地切片）

**Objective**：为不可变 `WorkflowVersion` 建立可审计、Primary-only、fixture-only、可幂等重放的后端 `WorkflowRun`/`StepRun` 内核；本地 receipt 与 `/automation/runs` 只读展示均不等于 Provider live、RawRecord、Dataset 或产品执行授权。

**当前实现与证据（2026-07-16）**：

- `workflow_execution` bounded context 已提供 Version integrity、Primary eligibility、registered fixture profile、deterministic adapter、transaction-owned `WorkflowRun`/`StepRun`/request ledger 和 same-key replay。
- 后端合同包括 write-free `GET /api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-run-gate`、受同一门禁约束的 `POST .../fixture-runs`、Run list/detail、lineage preview 与 Shadow comparisons 只读接口；门禁要求 active Plan 的 current、完整 resolved Version，`active` 不自动等于 runnable。Planner 已通过通用 status-transition 和该 gate 分离 Approve、Activate 与 fixture Run；Web `/automation/runs` 只读展示状态、lineage、Step 与 Shadow 摘要/诊断，但后端仍不提供 Schedule、Retry、Fallback switch 或 live Provider action endpoint。
- 2026-07-16 Template association follow-on 已将 immutable Version 的 `(workflow_template_id, workflow_template_revision_id)` 派生到 Run create/replay/list/detail response；不在 `workflow_runs` 重复存列，Version lineage 缺失或不一致时 read path 返回 sanitized `500 workflow_run_lineage_invalid`。该 focused gate 为 `58 passed / 1 warning`，route-level sanitized error matrix 为 `15 passed / 1 warning`，API full pytest 为 `900 passed / 59 skipped / 1 warning`；Web `/automation/runs` 只读展示该 lineage 与 StepRun evidence，并增加 fixture-only Provider/RawRecord/Dataset non-materialized preview，Run UI/navigation focused `15 passed`。
- 仅在用户明确授权的 `127.0.0.1:55367/local_workflow_execution_test` 执行 Alembic `028→029→028→029` 与 Task 13 PostgreSQL suite，结果 `14 passed`；cleanup head `202606110029`，`workflow_runs`、`step_runs`、`workflow_run_requests` 三表均为 0 行。
- API Task 14 静态/全量 gate 已通过：Ruff、strict mypy `268` source files、full pytest `836 passed / 59 skipped / 1 warning`、Alembic head `202606110029`。Web unit `238`、TypeScript、ESLint、static mock build `25/25` 和 static `next start` mock Playwright `72 passed / 12 expected skipped / 0 failed` 均通过；初次 `next dev` 的 3 个 mobile failures 已证实为 HMR/on-demand compile `ERR_ABORTED`，不是产品缺陷。

**状态边界**：`RUN-001=implemented_local`、`RUN-005=implemented_local_fixture_layer`、`RUN-006=implemented_local_fixture_layer`、`DAT-003=fixture_only`；`WFL-001=partial`。WFL-001A 已完成 active/current/complete fixture runnable gate 与产品写入口复用；UIX-08 已让 Planner 逐回执执行 Approve、Activate 与本地 fixture Run；UIX-09 已接入 Shadow、Step Attempt/Fallback、Checkpoint/Budget 与 Provider Health 只读呈现。本地 payload-bound fixture Run 可物化 RawRecord/DatasetVersion，revision-034 PostgreSQL 已完成 exact disposable acceptance，但 durable actor/reason/CallAudit、Template lifecycle UI、retry/resume/cancel/budget-override/switch actions 与 live Provider 尚未完成。RUN-07/08/10 mutation/state-machine composition、Provider/Actor/Browser/LLM、VOC/Brief lineage、CI、部署、生产、L3/L4/GA 均保持未完成。

### GOAL-V2-05：YouTube 与 Reddit 首批采集

**Objective**：交付首批官方或授权 Provider 路线。

**Scope**：

- 当前官方文档和开源客户端核验
- Adapter、Credential、Budget、Rate Limit、Cache
- Fixture、Readiness、Single Step Run
- RawRecord 与标准对象

**当前本地 foundation（2026-07-19）**：YouTube A1 已实现为 disabled
read Adapter foundation：严格请求合同只接受关键词、时间窗、区域、语言、排序、
`max_items<=50` 与 opaque `env:`/`secret:` reference；服务端使用 Manifest+SHA-256
注册的 `search.list`、`videos.list`、quota 离线证据，按首见顺序去重并编译
search→conditional detail 两步计划，再验证 typed normalized
`workflow_provider_payload.v1` compatibility。认证端点为
`POST /api/automation/social-provider-youtube-read-plan`。Readiness/gate v2 将
`declared_readiness` 与执行权限分离，`execution_enabled=false` 且
`provider_call_allowed=false`；没有 credential/environment read、SDK client、网络
调用、WorkflowRun/RawRecord/Dataset 写入或 migration。Cycle-2 已补齐 typed OpenAPI
body、精确 path 脱敏 422、granular bucket 的 `1/1` 正数 quota invariant、compiler
video-ID 校验与 10 条 Evidence refs 合法上限。2026-07-19 quota refresh 的当前
focused API 为 `68 passed / 1 warning`，full API 为 `1011 passed / 73 skipped / 1
warning`；full Ruff、strict Mypy `313 source files`、traceability `92/10/12` 和 CI
real-E2E boundary 均为 GREEN。Task 10 与本次配额合同修复均已本地 closeout；该证据
仍仅为 L2 fixture foundation。

**B1 credential-source boundary（2026-07-19）**：共享层现已统一解析
`env:` / `secret:` reference，并提供显式注入的 `CredentialSource` /
`InjectedCredentialResolver` 与 YouTube `YouTubeTransportFactory` 合同。唯一实现的
transport factory 为 fail-closed disabled factory；生产环境没有 env/Secret Manager
source、credential handle、Google client 或注册路径。定向测试为 `26 passed`，API
full 为 `1025 passed / 73 skipped / 1 warning`，Ruff 与应用源码 Mypy `205 files`
通过。该层仍不证明 credential 可达或 Provider 可调用。

**Platform credential settings vault（2026-07-22）**：Web 新增
`/settings/platforms`，按当前 Catalog 显示 YouTube、Reddit、X、Instagram、Threads、
TikTok Research、LinkedIn 的必需凭证字段。Secret 只以 password input 单向提交到
Workspace-scoped Fernet vault；API 与 UI 只返回 configured 状态，不回显或写入浏览器
存储。只有 Workspace Owner 可更新/删除，保存不会做 reachability、client construction
或 Provider call。revision 035 当前仅为 migration source，真实数据库 migration 未执行；
vault 主密钥只能由部署环境提供，vault 也尚未绑定 `secret:` resolver/live runtime。
因此 PAD-002 与 UIX-11 仍为 partial，本地配置成功不等于 credential reachable 或
provider_call_allowed。

**PAD-04 fixture runtime policy（2026-07-22）**：新增 provider-neutral
`provider_fixture_runtime.py`，只接受注入的 fixture transport、runtime store、
CallAudit repository、limits 与 UTC clock。preflight blocker 在 transport 前停止；
eligible path 对每次 attempt 原子消费 request/quota/cost/rate budget，timeout 与显式
retryable failure 只在冻结上限内重试。成功响应可进入 deterministic TTL cache，cache
hit 不消费预算。每个终态均形成冻结、脱敏、带实际 usage/response metadata/expiry 的
`CallAuditRecord`；当前 persistence 与 cleanup 仅用 in-memory fake 验证，没有新增
model、migration、数据库写或 live runtime wiring。聚焦测试 `9 passed`，相关回归
`106 passed / 1 warning`，API full `1079 passed / 73 skipped / 1 warning`，Ruff 与
Mypy `212 source files` 通过。PAD-004 与 GOV-003 因 live/durable gate 未完成仍为
`partial / L2-fixture`。

**Exit Gate**：Fixture 完整；Live Gate 材料齐备；真实调用仅在另行授权后执行。

### GOAL-V2-06：批量解析、洞察与交付

**Objective**：把采集结果转化为 Dataset、Alert、VOC 与 Brief。

**Scope**：

- URL Canonicalization、Deduplication、Classification
- Batch Parse 与 DatasetVersion
- Signal、Alert、VOC、Brief Preview
- Evidence Drilldown

**Exit Gate**：关键词/链接主流程和周期监测主流程完成 E2E 验收。

### GOAL-V2-07：V2.0 生产加固与 GA

**Objective**：完成运行健康、治理、Canary 和发布准备。

**Scope**：

- Provider Health、Schema Drift、Audit
- Retention、Delete、Rollback
- Performance、Security、Accessibility
- 7 天 Canary 与 KPI 基线

**Exit Gate**：V2.0 验收矩阵通过，Owner 批准 GA。

## 20. 依赖与风险

| 风险或依赖 | 影响 | 控制 |
|---|---|---|
| 官方 API 审批或价格变化 | Live 时间和成本 | Fixture/Readiness 先行，Provider 可替换 |
| TikHub/Apify 能力机制不透明 | 合规与稳定性 | 分类为受限通道，保留 Evidence 和替代路线 |
| 多 Provider 字段语义差异 | 数据比较偏差 | Field Contract、Normalizer、Shadow 对账 |
| LLM 扩词产生语义漂移 | 采集噪声 | Candidate、评分、冲突检查和命中贡献 |
| 浏览器页面结构变化 | 采集中断 | DOM Fixture、Drift Probe 和降级路线 |
| 外部成本超出预算 | 运行中止 | Budget Ledger、Cache、Cost Gate |
| 当前大组件继续膨胀 | 维护成本 | 按 Goal 渐进拆分，禁止整体重写 |
| 现有旧 PRD 与新目标冲突 | 执行方向分散 | 新 PRD 成为唯一当前目标，旧 PRD 标记为历史 |

## 21. 决策记录

| 日期 | 决策 |
|---|---|
| 2026-07-10 | 首批用户锁定为品牌与市场运营人员 |
| 2026-07-10 | 自动化业务结果作为产品入口，能力市场作为供给层 |
| 2026-07-10 | 采用平台 x 数据访问通道两层矩阵 |
| 2026-07-10 | 采用 Candidate/Verified/Partial 等分层治理 |
| 2026-07-10 | 采用 Primary、Fallback 和 Shadow 自适应混合路由 |
| 2026-07-10 | 采用 8 类资源、7 类操作、硬门禁和八维评分 |
| 2026-07-10 | 采用场景化路由，默认 market_monitoring_balanced |
| 2026-07-10 | 同一项目支持品牌词和品类词分轨、统一分析 |
| 2026-07-10 | 采用确定性词典、LLM 候选扩展和平台查询编译器 |
| 2026-07-10 | Browser 作为能力发现、内容采集和漂移核验的一等节点 |
| 2026-07-10 | V2.0 复用现有 Project、TaskRun、RawRecord、Dataset 与 APScheduler |

## 22. PRD 完成定义

本 PRD 满足以下条件后可以升级为 V2.0 稳定目标基线：

1. 用户确认产品定位、V2.0 范围和 7 个 Goal 包。
2. 所有需求均具备明确默认值，且当前状态互相一致。
3. README 指向本 PRD。
4. 旧 PRD 明确标记为历史基线。
5. 设计规格和 PRD 之间的平台、矩阵、状态、工作流和边界一致。
6. 后续每次 `/Goal` 只激活一个 Goal，并以对应 Exit Gate 作为完成判断。
