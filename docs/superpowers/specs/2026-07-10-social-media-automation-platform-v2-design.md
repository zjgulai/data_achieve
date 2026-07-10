---
title: 全社媒自动化数据采集平台 V2 总体设计
doc_type: design_spec
module: product-and-system
topic: social-media-automation-platform-v2
status: draft
review_status: awaiting_written_user_review
created: 2026-07-10
updated: 2026-07-10
owner: self
source: human+ai
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
---

# 全社媒自动化数据采集平台 V2 总体设计

> 本文是 V2 产品与系统重构的书面设计规格。设计方向已在对话中逐段确认，当前等待用户对书面版本复核。
>
> 本文不授权外部 Provider 调用、Actor 运行、生产写入、部署、数据库迁移或真实社媒采集。当前边界固定为 `provider_call=false`、`production unchanged`。

## 1. 执行摘要

Data Intelligence Hub V2 面向品牌与市场运营人员，提供两条相互连接的一等工作流：

1. 自动化采集品牌、品类、竞品与话题数据，并交付异动预警、VOC 洞察、趋势分析和周期简报。
2. 自动发现和治理可用于采集的 API、Actor、Collector、Skill、MCP 与 Agent，并把它们沉淀为可验证、可路由的能力供给。

产品前台以自动化市场监测为入口，能力市场作为供给底座。用户配置品牌词、品类词、账号、Seed URL、平台、地区、语言与交付目标，系统据此生成完整、版本化、可审计的 `WorkflowPlan`。自动化执行始终基于显式计划，保留选路、预算、Fallback、数据质量和证据链。

V2 的关键结构是两层能力矩阵：

- X 轴为社媒平台。
- Y 轴为数据访问通道。
- 栅格聚合资源能力、操作、具体实现、限制、评分与证据。
- API、Actor、浏览器、自托管组件、MCP 和 Agent 作为实现或交付形态挂载到栅格内部。

采集稳定性通过策略路由实现。正常状态仅运行 Primary；满足切换条件时选择经过验证的 Fallback；系统按预算执行小样本 Shadow 对账，持续核验替代路线的等价性。

## 2. 设计依据与当前基线

### 2.1 当前仓库事实

当前系统已经具备以下可复用主链路：

```text
Source
-> CollectionTask
-> TaskRun
-> RawRecord
-> Entity / Snapshot
-> Signal
-> Intelligence / Evidence
-> Alert / Report / Dataset
```

当前稳定采集入口包括 GitHub、公开网页、RSS/Atom、手工 JSON 和独立站商品相关 Collector。海外社媒目前主要是 Catalog、Readiness、Gate、Fixture 与 Preview 能力；现有代码不能据此宣称已经形成通用社媒真实采集能力。

当前前端同时承载采集执行、数据资产、情报、培训目录和工程门禁，一级入口较多，产品主任务不够集中。V2 需要压缩导航、强化项目上下文，并把能力目录与工作流运行建立正式数据关系。

### 2.2 外部产品样本

本设计对两个已登录公开产品界面进行了只读下钻审计：

| 样本 | 观察到的产品模型 | 对 V2 的启发 |
|---|---|---|
| TikHub API 市场 | 平台、资源分类、端点、参数、单价、RPS、日志、数据集与响应辅助 | 适合作为原子 Endpoint 供给和端点详情的参考 |
| Apify Store | Actor、输入表单、JSON、运行、任务、调度、存储、监控、集成、评分与计费 | 适合作为可执行采集组件及其运行生命周期的参考 |

TikHub Endpoint 与 Apify Actor 处于不同抽象层。V2 需要在它们之上建立统一能力合同，避免把 Endpoint、Actor、浏览器和 MCP 混成同一种采集方法。

### 2.3 证据边界

- 页面审计只证明公开产品界面及其可见字段。
- 未点击 TikHub 测试端点。
- 未启动 Apify Actor。
- 未读取或传输 API key。
- 未调用社媒平台数据接口。
- 未改变生产环境。

## 3. 已确认的产品决策

| 主题 | 已确认决策 |
|---|---|
| 首批用户 | 品牌与市场运营人员 |
| 产品入口 | 自动化业务任务优先，能力市场作为供给层 |
| 核心业务 | 品牌、品类、竞品、话题的周期监测与关键词/链接批量解析 |
| 能力业务 | 自动发现 API、Actor、Collector、Skill、MCP、Agent |
| 计划透明度 | 全自动运行仍必须保留完整 WorkflowPlan |
| 能力模型 | 平台 x 数据访问通道两层矩阵 |
| 证据治理 | 市场展示分层，自动执行消费经过验证的能力 |
| 稳定策略 | Primary 单路执行、条件切换、Shadow 小样本对账 |
| 能力词表 | 8 类资源 x 7 类操作 |
| 局限评价 | 硬门禁 + 八维评分 |
| 路由策略 | 场景化策略模板，默认 `market_monitoring_balanced` |
| 关键词模型 | 确定性词典 + LLM 候选扩展 + 平台查询编译器 |
| 混合监测 | 同一项目可配置多个品牌词和品类词，分轨采集、统一分析 |
| 浏览器角色 | 能力发现、内容采集、漂移核验 |
| 实施原则 | 优先复用官方 SDK 和成熟开源组件，仅编写必要 Glue Code |

## 4. 产品定位、目标与边界

### 4.1 一句话定位

一个面向品牌和市场运营人员的全社媒自动化数据采集与洞察平台：系统自动匹配官方 API、外部 Provider、自托管采集器和浏览器能力，形成透明工作流，并持续交付可追溯的数据、预警、VOC 与简报。

### 4.2 产品目标

1. 把一次性关键词检索、链接解析和账号跟踪升级为可复用周期工作流。
2. 用统一能力矩阵描述每个平台、访问通道和资源操作的真实边界。
3. 通过 Primary、Fallback 和 Shadow 核验提升采集连续性。
4. 把 API、Actor、Skill、MCP、Agent 等外部供给转化为可验证的能力资产。
5. 保证所有洞察可回溯到 `RawRecord`、`Evidence` 与具体采集路线。
6. 支持私有化部署的自托管 Collector、数据合同、工作流、审计与洞察链路。

### 4.3 非目标

- 登录绕过、验证码规避、反检测或风控对抗。
- 私信采集、Cookie 导出或未经授权的账号会话复用。
- 未授权媒体下载、用户画像合并或关系图谱扩张。
- 复制 TikHub、Apify 或其他 Provider 未公开实现。
- 用 LLM 生成缺少原始证据的新事实。
- 在首批实现中引入大型分布式工作流引擎。

## 5. 产品信息架构

V2 将一级导航压缩为六个入口。

### 5.1 工作台

- 项目状态、今日异动、数据新鲜度、采集健康度。
- 最新预警、VOC 摘要和简报状态。
- 主操作为“创建监测项目”和“批量检索与解析”。

### 5.2 监测项目

- 管理品牌、品类、竞品、话题和 Campaign。
- 配置关键词、别名、账号、Seed URL、平台、地区、语言与交付目标。
- 项目详情包含概览、监测范围、平台、数据、洞察和设置。

### 5.3 采集工作流

- 展示 Template、Plan、Version、Run 和 StepRun。
- 支持简单配置视图与完整计划视图。
- 展示 Primary、Fallback、Shadow、预算、门禁、步骤证据与运行轨迹。

### 5.4 数据资产

- 统一展示 Content、Conversation、Creator、Topic、Metrics 等对象。
- 支持来源追溯、质量状态、DatasetVersion、导出和保留策略。

### 5.5 洞察与交付

- 异动预警、VOC、话题趋势、竞品比较、周期简报与交付记录。
- 每条结论可下钻到原始内容和 Evidence。

### 5.6 能力市场

- 默认展示业务场景与工作流能力。
- 专业用户可切换矩阵视图和全部能力列表。
- 统一承载官方 API、TikHub、Apify Actor、自托管组件、Browser、Skill、MCP 与 Agent。

### 5.7 UI 原则

- 首屏进入可操作工作台，不使用营销型 Hero。
- 使用紧凑表格、状态栏、分栏和侧边详情，减少装饰性卡片。
- 工程字段默认进入高级视图，业务视图使用品牌运营语言。
- 全局顶部保留项目切换器、时间范围、搜索、通知和新建入口。
- 移动端提供完整导航，优先支持预警、运行状态和简报阅读。
- 现有 UI 组件和视觉语言优先复用，新增卡片圆角不超过现有设计系统约束。

## 6. 能力矩阵

### 6.1 第一批平台

第一批包含 7 个逻辑平台、6 个接入族：

- YouTube
- Reddit
- X
- Instagram
- Threads
- TikTok
- LinkedIn

Instagram 与 Threads 可以共享 Meta 接入族，但必须保留独立平台列和独立能力声明。

### 6.2 X 轴与 Y 轴

X 轴为平台。Y 轴固定为以下数据访问通道：

1. 官方或授权 API
2. 授权合作数据服务
3. 公开页面或 Feed
4. 授权浏览器采集
5. 托管且机制未完全披露的采集服务
6. 授权导出或文件导入

`delivery_form` 与 `deployment_mode` 是栅格内属性：

- `delivery_form`: endpoint、sdk、actor、collector、parser、workflow、skill、mcp、agent
- `deployment_mode`: official_cloud、managed_saas、byok、self_hosted、browser_runtime、manual_import

### 6.3 统一资源词表

| resource_type | 范围 |
|---|---|
| `content` | Post、Video、Reel、Thread、Article |
| `conversation` | Comment、Reply |
| `creator` | Profile、Account、Channel |
| `topic` | Keyword、Hashtag、Trend、Feed |
| `metrics` | Views、Likes、Shares、Follower Snapshot |
| `media_live` | Image、Audio、Transcript、Live |
| `commerce_ads` | Product、Shop、Ad、Affiliate |
| `relationship_graph` | Followers、Following、Community Member，默认受限 |

### 6.4 统一操作词表

- `resolve_detail`
- `search_discover`
- `list_enumerate`
- `monitor_incremental`
- `backfill_history`
- `batch_parse`
- `export_download`

### 6.5 能力状态

| 状态 | 含义 | 自动路由 |
|---|---|---|
| `unknown` | 尚未评估 | 禁止 |
| `candidate` | 已发现，等待核验 | 禁止 |
| `verified` | 证据和合同满足执行要求 | 允许，仍需通过门禁 |
| `partial` | 能力或字段覆盖有限 | 仅策略明确放行 |
| `blocked` | 当前权限、政策或运行条件阻断 | 禁止 |
| `unsupported` | 已核验无可用路线 | 禁止 |
| `deprecated` | 已停止推荐或等待迁移 | 禁止新工作流使用 |

### 6.6 原子能力模型

能力事实使用原子化 `CapabilityAssertion`，矩阵栅格是聚合读模型。

```text
Implementation A
在 Region R、Purpose P、Auth Scope S 条件下
支持 Platform X 的 Resource Y + Operation Z
状态为 SupportStatus
受 Constraints C 限制
证据来自 Evidence E
```

建议对象：

- `Platform`
- `AccessChannel`
- `CapabilityImplementation`
- `CapabilityAssertion`
- `CapabilityConstraint`
- `CapabilityEvidence`
- `ProviderHealthSnapshot`
- `WorkflowCapabilityUsage`

`CapabilityAssertion` 至少包含：

```text
id
platform_id
access_channel_id
implementation_id
resource_type
operation
support_status
region_scope
purpose_scope
auth_scope
field_contract
constraints
score_profile
evidence_refs
valid_from
valid_until
last_verified_at
```

`CapabilityImplementation` 至少包含：

```text
id
provider_id
platform_id
access_channel_id
delivery_form
deployment_mode
auth_mode
api_version
quota_hint
cost_hint
policy_flags
blocked_actions
source_url
lifecycle_status
```

`CapabilityEvidence` 至少包含：

```text
id
evidence_type: official_doc | public_market | repository | fixture | authorized_runtime
source_url
source_version
observed_at
content_hash
evidence_grade
provider_call_attempted
credential_read_attempted
live_client_created
```

### 6.7 硬门禁

- `policy_gate`: allowed、review_required、blocked
- `auth_gate`: ready、credential_required、approval_required
- `purpose_gate`: commercial、research_only、owned_assets_only
- `region_gate`: global 或 region_limited
- `data_gate`: public、authorized、sensitive

任何硬门禁未通过时，不计算自动选路结果。

### 6.8 八维评分

每项使用 1 至 5 级，并保留评分依据：

- Coverage
- Freshness
- History
- Reliability
- Schema Stability
- Cost Efficiency
- Maintainability
- Evidence Confidence

评分记录 `limitation_severity`、`last_verified_at`、`evidence_ref` 和适用范围。硬门禁不能被综合评分抵消。

### 6.9 矩阵 UI

栅格摘要显示：

- 能力状态
- 资源覆盖数
- 实现数量
- 最高稳定等级
- 首要局限

矩阵支持按资源、操作、证据状态、部署方式、商业用途、地区、鉴权和成本筛选。每个栅格必须给出显式状态，禁止以空白代替 `unknown` 或 `unsupported`。

点击栅格后进入详情抽屉：

1. 支持的资源与操作
2. 官方 API、TikHub、Apify、自托管和浏览器实现
3. 字段、时效、历史、配额、成本与地区边界
4. 硬门禁与八维评分
5. 证据及最近核验时间
6. 当前 WorkflowPlan 使用情况
7. 比较实现、加入工作流、发起核验

## 7. 监测范围与查询模型

### 7.1 MonitoringScope

`MonitoringScope` 从属于现有 `Project`。V2 通过扩展 Project 的领域配置承载监测项目语义，不新增平行的 MonitoringProject 表。

```text
scope_type: brand | category | competitor | topic | campaign
canonical_term
aliases
include_terms
exclude_terms
official_accounts
seed_urls
languages
regions
platforms
match_mode: exact | phrase | semantic | hybrid
```

同一项目可以配置多个品牌词和品类词。每条结果保留：

- `matched_scope_id`
- `matched_term`
- `match_reason`
- `query_version`
- `platform_query`

### 7.2 品牌词与品类词策略

- 品牌词使用 Precision-first：标准名、别名、多语言名、产品线、官方账号、域名与排除词。
- 品类词使用 Recall-first：品类名、同义词、上下位词、使用场景和语义扩展，再进行相关性过滤。

### 7.3 三层查询模型

1. 确定性词典：品牌别名、产品名、官方账号、排除词。
2. Kimi/DeepSeek 候选扩展：品类同义词、场景词、竞品关联词、多语言表达。
3. 平台查询编译器：按平台搜索能力、语法、长度和过滤条件生成实际查询。

LLM 输出进入 `candidate_terms`。候选词经过相关性评分、冲突检查和小样本预览后进入 `active_terms`。所有词项保留来源、理由、版本和命中贡献。

## 8. 采集工作流

### 8.1 四级对象

```text
WorkflowTemplate
-> WorkflowPlan
-> WorkflowVersion
-> WorkflowRun / StepRun
```

- Template：可复用业务模板。
- Plan：项目级完整执行计划。
- Version：冻结关键词、平台、选路、预算和治理规则。
- Run：一次实际执行及其逐步证据。

### 8.2 业务数据采集链路

```text
MonitoringScope
-> 品牌词/品类词编译
-> 平台查询生成
-> 关键词与账号检索
-> Seed URL 合并
-> 链接规范化、去重和分类
-> Capability Resolver 选路
-> 批量 API / Actor / 浏览器解析
-> 增量游标与分页
-> 标准化、实体对齐和质量检查
-> Shadow 抽样对账
-> 证据约束的 LLM 增强
-> Signal / Alert / VOC / Brief / Dataset
```

### 8.3 能力发现链路

```text
API 市场 / Actor Store / 官方文档 / GitHub
-> Browser Capability Discovery
-> 页面和文档解析
-> API / Actor / Collector / Skill / MCP / Agent 分类
-> 输入输出、定价、权限、限制提取
-> candidate CapabilityAssertion
-> Evidence 保存
-> 自动核验或人工复核
-> 发布到能力矩阵
```

### 8.4 浏览器角色

- `BrowserCapabilityDiscoveryStep`: 发现和解析能力供给。
- `BrowserContentCollectionStep`: 采集公开或已授权页面内容。
- `BrowserVerificationProbeStep`: 检查页面结构、字段和能力漂移。

授权浏览器会话属于高敏感执行条件，需要独立审批、范围和保留策略。浏览器能力不得用于验证码规避、Cookie 导出、登录绕过或未授权私有接口访问。

### 8.5 RoutePlan

每个平台、资源与操作生成独立 RoutePlan：

```text
primary_implementation
fallback_implementations
shadow_verification_rule
required_fields
optional_fields
budget
rate_limit
retention
policy_gates
degradation_rule
```

### 8.6 自适应混合路由

- 正常状态只运行 Primary。
- 限流、超时、Schema 漂移、字段缺失或数据质量下降可触发 Fallback 评估。
- Fallback 必须重新经过 Policy、Credential、Budget 和字段合同检查。
- 周期性小样本 Shadow 对账用于验证备用路线的语义等价性。
- 切换后的数据保留独立 Provider 与方法血缘，禁止静默覆盖。

### 8.7 场景化路由策略

| profile | 默认优先级 |
|---|---|
| `market_monitoring_balanced` | 合规、必需字段、稳定性、时效、成本 |
| `realtime_anomaly_alert` | 合规、时效、稳定性、字段覆盖、成本 |
| `voc_deep_analysis` | 合规、评论覆盖、历史深度、质量、成本 |
| `historical_research` | 合规、历史深度、覆盖、稳定性、时效 |
| `low_cost_batch` | 合规、必需字段、成本、稳定性、时效 |
| `capability_discovery` | 证据新鲜度、文档完整度、可验证性 |

`market_monitoring_balanced` 是默认策略。

### 8.8 自动执行审批

满足以下条件时允许自动执行：

- 能力状态为 `verified`
- Credential 和 Scope 就绪
- 预算与请求量处于已批准范围
- 硬门禁全部通过
- 数据用途与保留策略未变化

以下变化进入审批节点：

- 新 Provider 或新访问通道进入路由
- Credential、Scope、地区或数据用途变化
- 预算、请求量或保留周期提升
- `partial` 能力进入正式路由
- Relationship Graph、授权浏览器会话或敏感数据
- Policy override 或商业用途边界变化

## 9. 首批工作流模板

1. 品牌舆情周期监测
2. 品类趋势发现
3. 竞品账号与内容追踪
4. 关键词到链接再到批量解析
5. 评论采集与 VOC 分析
6. 单账号或频道增量监控
7. API 与 AI 工具能力发现
8. Provider 能力漂移核验

“批量检索与解析”保留为工作台独立快捷入口：

```text
关键词或 Seed URL
-> 多平台检索
-> 链接去重与分类
-> 批量解析
-> 质量检查
-> 保存为 Dataset
-> 可升级为周期 WorkflowPlan
```

## 10. 数据合同

### 10.1 能力与工作流合同

- `external_provider_catalog.v1`，作为现有海外 Provider Catalog 的兼容入口
- `capability_implementation.v1`
- `capability_assertion.v1`
- `capability_evidence.v1`
- `provider_health_snapshot.v1`
- `monitoring_scope.v1`
- `workflow_plan.v2`
- `route_plan.v1`
- `workflow_run.v1`

### 10.2 标准社媒合同

- `social_raw.v1`
- `social_post.v1`
- `social_comment.v1`
- `social_creator_snapshot.v1`
- `social_topic_trend.v1`
- `social_voc_item.v1`

### 10.3 血缘要求

标准化对象至少保留：

```text
workflow_plan_id
workflow_version
workflow_run_id
step_run_id
platform
provider_id
access_channel
implementation_id
raw_record_id
evidence_refs
observed_at
normalized_at
schema_version
```

### 10.4 作者与敏感数据

- 默认 `author_policy=hashed|dropped`。
- 明文保留需要 `retained_with_approval`。
- Relationship Graph 默认禁用。
- `allow_ai_training=false` 为默认策略。
- `social_voc_item` 必须引用 RawRecord 和 Evidence。

## 11. 运行状态与可靠性

### 11.1 WorkflowRun 状态

```text
draft -> ready -> running -> completed
                  -> degraded
                  -> held
                  -> cancelled
```

- `degraded`: 已切换备用能力或输出字段缩减。
- `held`: 权限、预算、凭证、质量或审批阻断。
- `cancelled`: 用户或系统按策略终止。

### 11.2 可靠性规则

- 仅对超时、限流和短暂网络中断进行有界重试。
- 所有采集步骤必须支持幂等键和断点游标。
- 原始记录不可覆盖，标准化结果通过版本与来源关联。
- `empty_valid` 与运行异常分开表达。
- 成本达到上限时进入 `held`，停止继续产生外部调用。
- Schema 漂移先隔离新字段并生成核验任务。
- 相同 WorkflowVersion 和相同输入必须生成确定性 RoutePlan。

## 12. 与现有架构的集成

### 12.1 延续现有主链路

V2 不替换 Source、CollectionTask、TaskRun、RawRecord、Dataset、Signal、Evidence、Alert 和 Report。新增对象在这些资产上方提供计划、选路和能力治理。

现有 `Project` 继续作为租户内业务项目根对象。品牌、品类、竞品、话题和 Campaign 通过 `MonitoringScope` 关联到 Project，避免形成两套项目生命周期。

### 12.2 建议模块边界

后端新增或拆分为以下职责单一模块：

- Capability Catalog 与 Matrix Read Model
- Capability Evidence 与 Verification
- Monitoring Scope 与 Query Compiler
- Workflow Planner 与 Versioning
- Capability Resolver 与 Route Policy
- Provider Registry 与 Credential Resolver
- Budget Ledger、Rate Limit Gate 与 Request Cache
- Fixture Replay 与 Call Audit
- Platform Adapter 与 Normalizer
- LLM Enrichment Adapter

当前体积较大的 Automation Service 应按上述边界逐步迁移，禁止一次性整体重写。

### 12.3 建议 API 面

新 API 以现有路由约定为准，逻辑合同包括：

- `GET /api/capabilities/matrix`
- `GET /api/capabilities/assertions`
- `GET /api/capabilities/implementations/{implementation_id}`
- `POST /api/capabilities/discovery-plans`
- `POST /api/capabilities/verifications`
- `POST /api/projects`，复用现有项目创建合同
- `GET /api/projects/{project_id}/monitoring-scopes`
- `POST /api/projects/{project_id}/monitoring-scopes`
- `POST /api/workflow-plans/preview`
- `POST /api/workflow-plans/{plan_id}/activate`
- `GET /api/workflow-runs`
- `GET /api/workflow-runs/{run_id}`

现有 `/api/automation/social-provider-*` 合同保留兼容层，迁移前不得破坏已有 Fixture、Readiness 和 Gate 流程。

### 12.4 调度与规模

首版继续使用现有 Task、TaskRun、APScheduler 和数据库锁。只有在并发量、重试队列或多 Worker 所有权超出现有边界时，才评估独立工作流引擎。

## 13. 开源与第三方复用策略

### 13.1 选型顺序

1. 平台官方 API、OpenAPI、SDK 与 Webhook
2. 官方维护的客户端或成熟社区客户端
3. Apify 等可审计的托管组件
4. 许可证清晰且维护活跃的自托管开源采集器
5. 现有 Generic Web、Public Feed、Browser 与 Manual Import 能力

### 13.2 选型门槛

- 许可证允许目标部署与商业用途。
- 维护状态、文档、自动化测试和安全记录可验证。
- 鉴权与平台政策边界明确。
- 能通过 Fixture Replay 和 Adapter Contract 测试。
- 第三方数据结构可以隔离在 Adapter 内。
- 可以设置成本、并发、保留和删除策略。
- 不依赖验证码规避、反检测、Cookie 获取或未披露私有接口。

### 13.3 候选组件核验范围

实施计划阶段需要实时核验以下类别的官方或成熟组件：

- YouTube 官方 API 客户端
- Reddit OAuth 客户端
- X API 客户端
- Meta Graph API 客户端或生成式 REST Client
- TikTok Research API 客户端或直接 REST Adapter
- LinkedIn API REST Client
- Apify 官方 Client
- OpenAPI、JSON Schema、OAuth、HTTP Retry、Rate Limit 与 Cache 组件

具体包名、版本与许可证必须以实施时的官方文档和仓库状态为准。未经核验的候选不得写入运行时依赖。

### 13.4 Glue Code 原则

- 外部组件统一包裹在 `PlatformAdapter` 或 `CapabilitySourceAdapter` 后。
- 业务服务不直接消费第三方响应。
- 优先复用现有浏览器解析、TaskRun、RawRecord 与 DI 容器。
- 首版不自研调度器、OAuth 协议、Schema Validator 或通用爬虫引擎。

## 14. 分批实施

### Batch 1: 能力底座

- 落地平台、访问通道、资源、操作和状态词表。
- 实现 Assertion、Constraint、Evidence 与 Health Snapshot。
- 建立 Fixture Catalog 和只读 Matrix API。
- 边界：`provider_call=false`、`production unchanged`。

### Batch 2: 能力矩阵产品

- 新增矩阵、栅格详情、实现比较、证据和限制下钻。
- 压缩导航并加入全局项目选择器。
- 前后端 Catalog 统一为单一数据源。

### Batch 3: Workflow Planner

- 实现 MonitoringScope、品牌词与品类词分轨。
- 实现三层查询模型、Resolver、RoutePlan、Fallback 和 Shadow 规则。
- 仅运行 Fixture 与模拟路径。

### Batch 4: 浏览器能力发现

- 复用现有浏览器基础设施。
- 建立 TikHub、Apify、官方文档和 GitHub 发现模板。
- 结果先进入 `candidate`，再经过核验流程。

### Batch 5: 海外平台内容采集

- 第一波：YouTube、Reddit。
- 第二波：X。
- 第三波：Instagram、Threads。
- 第四波：TikTok Research、LinkedIn。
- 每个平台依次通过 Fixture、Readiness、授权小规模运行门禁。

### Batch 6: 洞察、交付与生产加固

- 完成 RawRecord 到 Signal、Alert、VOC 和 Brief 的证据链。
- 增加运行健康、预算、质量、Schema 漂移和 Provider 状态监控。
- 完成项目工作台、预警中心、周期简报和数据导出。

## 15. 测试策略

### 15.1 单元测试

- Schema 与 Catalog
- Capability Resolver 与场景权重
- Policy、Budget、Credential、Rate Limit Gate
- Query Compiler 与 Keyword State
- URL Canonicalization 与 Deduplication
- Normalizer 与 Evidence Binding
- LLM JSON Schema Validation

### 15.2 契约与集成测试

- Provider Adapter 统一契约
- Fixture Replay
- Primary、Fallback 与 Shadow 路由
- Capability Discovery 到 Candidate Assertion
- RawRecord 到 Social Object 再到 VOC 的引用链
- 幂等、断点游标和重复运行

### 15.3 E2E

1. 周期市场监测：Scope 到 Alert、VOC 和 Brief Preview。
2. 关键词或 Seed URL 到多平台链接发现、批量解析和 Dataset。
3. 市场页面到 Candidate、Verification 和 Matrix Publication。
4. 工作流计划、运行详情、Fallback 轨迹与 Evidence 下钻。
5. 桌面端和移动端导航、筛选、抽屉和文本适配。

### 15.4 Live Gate

真实外部调用必须单独提供：

- `authorized=true`
- `approval_id`
- provider 与 endpoint scope
- keyword、account、subreddit 或 URL scope
- `max_requests`
- `max_items`
- `max_cost_usd`
- retention 与 delete policy
- `allow_ai_training=false`

## 16. 首版验收标准

### 16.1 能力矩阵

- 第一批 7 个平台和 6 个访问通道均有显式状态。
- 每项可执行能力拥有 Evidence 和最近核验时间。
- 栅格能下钻到资源、操作、实现、限制和工作流使用情况。
- 前后端读取同一个 Catalog 事实源。

### 16.2 Workflow Planner

- 同一 WorkflowVersion 和相同输入生成确定性 RoutePlan。
- 品牌词与品类词可以在同一项目中分轨运行并保留归因。
- 用户可以查看完整计划、预算、Primary、Fallback 和 Shadow 规则。
- `candidate` 不进入自动执行路线。

### 16.3 运行与数据

- 自动切换完整保留来源、原因、字段差异和额外成本。
- 原始数据、标准对象、Signal、VOC 与 Brief 形成可追溯血缘。
- 日志、页面和数据集中不出现明文 Credential。
- LLM 输出能回溯到 RawRecord 和 Evidence。

### 16.4 UI

- 六个一级入口可完整覆盖核心任务。
- 品牌运营人员可以在业务语言下完成项目创建和运行查看。
- 高级用户可以使用矩阵、证据和技术实现详情。
- 桌面端与移动端无不可恢复的内容遮挡或横向溢出。

## 17. 风险与控制

| 风险 | 控制方式 |
|---|---|
| 外部 Provider 能力或价格变化 | 版本化 Assertion、Evidence、Health Snapshot 与核验任务 |
| 多 Provider 数据语义差异 | Required Field Contract、Shadow 对账和独立血缘 |
| 浏览器页面漂移 | DOM Fixture、Verification Probe 和降级状态 |
| LLM 扩展词语义漂移 | Candidate 状态、冲突检查、小样本预览和命中贡献追踪 |
| Provider 成本扩张 | Budget Ledger、请求上限、Cache 和自动 Hold |
| 合规边界变化 | Policy Gate、Purpose Scope、Region Scope 和审批版本 |
| 当前大文件继续膨胀 | 按单一职责拆分服务和组件，逐批迁移 |
| 目录数量再次扩张 | 固定六个一级入口，工程能力进入高级视图 |

## 18. 迁移与兼容策略

1. 保留现有 `/api-market` 和 `/api/automation/social-provider-*` 行为，先接入统一 Catalog 读模型。
2. 现有静态 API Market Catalog 迁移为 `CapabilityImplementation` 与 `CapabilityAssertion`。
3. 现有 Source、Task、TaskRun、RawRecord 和 Dataset 无需重建。
4. 旧页面先通过导航映射进入新六入口，再逐步拆分大组件。
5. 任何数据库迁移单独提供升级、回滚和数据核对方案。
6. 每批都保持可发布状态，禁止长期保留双写或隐式兼容逻辑。

## 19. 后续门禁

本文通过书面审阅后，下一步只进入实施计划编写。实施计划必须：

1. 先实时核验候选开源库、官方 SDK、许可证与维护状态。
2. 从 Batch 1 开始，禁止跨批同时铺开业务实现。
3. 为每项改动列出精确文件、测试、回滚和验收证据。
4. 保持 `provider_call=false`，直到单独获得 Live Gate 授权。
5. 保持 `production unchanged`，直到单独获得部署授权。
