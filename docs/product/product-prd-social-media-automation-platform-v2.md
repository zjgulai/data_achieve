---
title: Data Intelligence Hub PRD V2.0 全社媒自动化数据采集与能力发现平台
doc_type: prd
module: product
topic: social-media-automation-platform
version: "2.0"
status: stable
review_status: approved
created: 2026-07-10
updated: 2026-07-10
approved: 2026-07-10
owner: self
source: human+ai
supersedes: product-prd-data-intelligence-hub-stable.md
design_spec: ../superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
goal_execution: ready_for_goal_activation
---

# Data Intelligence Hub PRD V2.0

## 全社媒自动化数据采集与能力发现平台

> **文档状态**：V2.0 稳定目标基线，已于 2026-07-10 获得用户确认。
>
> **当前执行边界**：`provider_call=false`、`production unchanged`、`goal_execution=ready_for_goal_activation`。
>
> **技术设计**：[全社媒自动化数据采集平台 V2 总体设计](../superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md)

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

以下 Goal 仅定义目标与退出条件。当前状态均为 `ready_for_goal_activation`，本 PRD 本身不自动创建或启动 Goal。

### GOAL-V2-01：产品与能力合同底座

**Objective**：建立 V2.0 词表、Schema、Catalog 与兼容层。

**Scope**：

- Platform、AccessChannel、Resource、Operation、Status
- CapabilityImplementation、Assertion、Constraint、Evidence
- external_provider_catalog.v1 兼容入口
- Fixture 与 Schema 测试

**Exit Gate**：Catalog 单一事实源、迁移方案和全部契约测试通过。

### GOAL-V2-02：能力矩阵与网站导航

**Objective**：交付矩阵产品和六入口信息架构。

**Scope**：

- Matrix API 与 Read Model
- 场景、矩阵和列表视图
- 栅格详情、比较和 Evidence
- Sidebar、Project Selector、Mobile Navigation

**Exit Gate**：7 x 6 矩阵有显式状态，桌面端与移动端 E2E 通过。

### GOAL-V2-03：MonitoringScope 与 Workflow Planner

**Objective**：从品牌词、品类词和 Seed URL 生成可执行计划。

**Scope**：

- MonitoringScope
- 三层查询模型
- WorkflowPlan V2 与 Versioning
- Capability Resolver 与场景策略
- RoutePlan、Fallback 和 Shadow 规则

**Exit Gate**：两个核心 Flow 可在 Fixture 下生成确定性计划并完整解释。

### GOAL-V2-04：浏览器能力发现

**Objective**：把 TikHub、Apify、官方文档和 GitHub 供给转为候选能力。

**Scope**：

- BrowserCapabilityDiscoveryStep
- Parser 与 Evidence
- Candidate、Verification、Publication
- Drift Probe

**Exit Gate**：至少两个市场样本和两个官方文档样本可重复生成 Candidate Assertion。

### GOAL-V2-05：YouTube 与 Reddit 首批采集

**Objective**：交付首批官方或授权 Provider 路线。

**Scope**：

- 当前官方文档和开源客户端核验
- Adapter、Credential、Budget、Rate Limit、Cache
- Fixture、Readiness、Single Step Run
- RawRecord 与标准对象

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
