---
title: Data Intelligence Hub UI/UX Integrated Optimization Plan
doc_type: product-design-plan
module: web-product
status: approved_for_implementation
created: 2026-07-22
updated: 2026-07-27
owner: self
source: human+ai
---

# Data Intelligence Hub UI/UX 整合优化方案

## 0. 方案结论

本方案整合三个输入：

1. 2026-07-22 全项目复盘形成的产品、架构、数据和证据链路线。
2. `VoltAgent/awesome-design-md` 的 DESIGN.md 结构化方法，以及 Linear、Airtable、
   Sentry 三类参考中与本项目匹配的原则。
3. `TODO.md` 中仍未完成的 PAD、RUN、WFL、GOV、QRY、BATCH、DAT、BRW、CAP、INS、
   UI、AT 和 KPI 工作。

最终方向不是换皮，而是把当前界面升级为“业务默认、证据可钻、状态可行动、诊断
可展开”的数据智能工作台。

推荐视觉模型：

- 保留当前暖色画布、白色工作区、玫瑰色品牌识别和 Lucide 图标。
- 引入 Linear 式精确层级和稀缺主色，但不复制暗色或紫色品牌。
- 引入 Airtable 式浅色结构化工作区、表格密度和留白节奏。
- 引入 Sentry 式运行状态可见性，但不复制深紫、荧光或插画风格。
- 所有颜色、字体、间距、状态和交互通过项目 DESIGN.md 与 semantic tokens 固化。

## 1. 事实、推断和建议边界

### 当前事实

- Web 使用 Next.js 15、React 19、Tailwind 4、Lucide、TanStack Query/Table 和
  Recharts。
- 六项主导航已经稳定：工作台、监测项目、采集工作流、数据资产、洞察与交付、
  能力市场。
- 当前存在 56 个组件 TSX 文件和共享 `common/workbench-ui.tsx`。
- `apps/web/src` 当前有 4,778 次六位 hex 色值、267 个不同色值；CSS 变量只被使用
  两次。
- Dashboard 已把周期监测、批量解析和已保存计划放在内容顶部。
- Planner 已有 Simple/Advanced、保存、版本、比较和脏导航保护。
- Run UI 当前明确是只读 fixture 证据；Capability UI 已有场景、矩阵、列表、详情、
  比较、发现和治理视图。
- E2E 已覆盖部分 375/1440、移动导航、Planner 可访问表单和关键 mock 流程，但
  TODO 仍要求所有 V2 critical flow 完成响应式、键盘和自动 accessibility scan。

### 推断

- 大量直接色值和页面级变体会增加一致性、对比度、主题演进和审查成本。
- 当前业务语言与诊断语言混合，使品牌运营用户承担 Provider/fixture/fingerprint 等
  实现概念。
- 卡片使用偏多，适合摘要，但在 Run、Dataset 和 Capability 比较场景会降低扫描效率。
- 如果先做纯视觉重构、再补运行状态和治理，界面会看起来完整但仍无法安全执行。

### 建议

- 先迁移共享设计基础和交互合同，不做全仓换色。
- UI Wave 与后端 TODO 按依赖绑定：状态不存在时只做显式只读设计，不制造虚假控件。
- 默认业务视图与 Advanced 诊断视图分离。
- 所有业务结论、状态和按钮都带 Evidence / Gate / Next action。

## 2. awesome-design-md 的核心方法及本项目取舍

`awesome-design-md` 把设计语言写成 AI 和工程可以直接执行的纯文本规范，核心栏目包括
视觉气质、语义颜色、字体层级、组件状态、布局、深度、Do/Don't、响应式和 Agent
提示。它强调设计规则而非只有截图或 token 列表。

### 采用

| 参考 | 采用内容 | 在本项目中的表达 |
|---|---|---|
| DESIGN.md 方法 | 设计规则、tokens、组件状态、响应式、Do/Don't | 项目级 `DESIGN.md`、tokens、UI kit、执行 TODO |
| Linear | 稀缺主色、surface ladder、hairline、紧凑控制 | Rose 只用于品牌和主行动；层级靠表面和边框 |
| Airtable | 浅色工作区、结构化数据、留白、表格 | 暖色 canvas + 白色工作面；比较任务优先表格/行 |
| Sentry | 运维状态、单一主行动、功能页密度 | Run 状态必须显示原因、影响和下一步 |

### 不采用

- 不复制任何参考品牌的颜色、字体或独占资产。
- 不采用 Linear 的全局暗色、Sentry 的荧光/贴纸、Airtable 的营销彩色卡片。
- 不增加紫蓝渐变、玻璃拟态、发光卡片和纯装饰动画。
- 不用截图替代当前代码和组件审计。

参考：

- <https://github.com/VoltAgent/awesome-design-md>
- <https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/linear.app/DESIGN.md>
- <https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/airtable/DESIGN.md>
- <https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/sentry/DESIGN.md>

## 3. 目标体验架构

### 3.1 全局体验模型

每个页面必须回答五个问题：

1. 我当前在哪个 Workspace / Project / Scope？
2. 当前业务结果或状态是什么？
3. 为什么是这个结果，Evidence 在哪里？
4. 我现在能做什么，什么动作被 Gate 阻止？
5. 下一步会产生什么影响，是否需要审批？

### 3.2 两层信息表达

#### Default：业务层

- “采集已暂停，等待凭证检查”。
- “本次有 18 条结果，其中 3 条缺少作者字段”。
- “计划已保存，但尚未满足运行条件”。
- “该洞察基于 42 条可追溯证据”。

#### Advanced：诊断层

- canonical status、Provider/Adapter、fingerprint、quota、request ID、error code、
  RawRecord/DatasetVersion ID、payload digest 和 CallAudit。
- 默认折叠，切换只改变展示，不改变执行权限或数据。

### 3.3 状态表达公式

`状态名称 + 发生原因 + 业务影响 + Evidence + 可执行下一步`

示例：

> 已暂停，等待处理。Reddit OAuth 尚未配置，因此 2 个 Reddit 步骤没有启动；其他
> 平台不受影响。查看门禁证据 / 请求凭证检查。

### 3.4 行动等级

| 级别 | 示例 | 视觉与交互 |
|---|---|---|
| Primary | 创建监测、保存版本、提交审批 | 每个决策区域最多一个填充按钮 |
| Secondary | 预览、比较版本、查看 Evidence | 描边按钮或链接 |
| Gated | Activate、Run、Send、Export、Live Call | ActionGate + 影响复核 + 审批/缺口 |
| Destructive | Cancel、Delete、Revoke | Danger 样式 + 二次确认 + 回滚说明 |

## 4. 信息架构优化

六项一级导航不变，优化二级结构和跨页上下文。

### 工作台

- 立即行动：创建周期监测、解析一批数据。
- 需要关注：held、degraded、failed、stale、待审批。
- 业务结果：最新 Intelligence、Evidence 覆盖、下次交付。
- Advanced：任务健康、Provider、字段完整和运行诊断。

### 监测项目

- Project Overview。
- Scope & Query。
- Plans & Runs。
- Data & Intelligence。
- Access & Audit。

### 采集工作流

- Create：周期监测 / 批量研究。
- Plans：模板、计划、版本、审批。
- Operations：Runs、Tasks、Sources。
- 默认不把工程对象平铺为同等入口；按用户任务组织。

### 数据资产

- 原始记录、标准实体、数据集版本、质量与漂移。
- Evidence / Lineage 从侧边抽屉进入，不离开当前筛选。

### 洞察与交付

- Signals、Intelligence、VOC/Brief、Reports、Alerts、Notifications。
- “结论—证据—动作”是详情主线。

### 能力市场

- 场景发现、候选比较、Evidence、治理审批。
- Hard gates 先于评分；blocked/unknown 不进入可运行候选。

## 5. 视觉系统

Canonical files：

- `opendesign/design-systems/data-intelligence-product/DESIGN.md`
- `opendesign/design-systems/data-intelligence-product/tokens/colors_and_type.css`
- `opendesign/design-systems/data-intelligence-product/ui-kit-web/index.html`

### 核心变化

- 当前玫瑰色从“普遍装饰色”收敛为品牌和主行动。
- Success/Warning/Danger/Info 独立承担状态语义。
- Panel 默认无阴影，依靠白色 surface 和 1px border。
- radius 分为 4/8/12/16 四级，pill 只用于状态和筛选。
- 页面标题上限 32px；产品页不使用营销级大标题。
- 4px spacing system；数据页支持 Comfortable / Compact 两档密度。
- 不新增字体或图标 dependency。

## 6. 屏幕级优化方案

### 6.1 AppShell 与全局导航

当前基础：桌面 Sidebar、TopBar、Mobile drawer、Project selector、Global search 已存在。

优化：

- Project context 变成始终可见的上下文条，并同步 URL/query state。
- TopBar 从“标题 + 很长说明 + signal pills”收敛为标题、结果说明、主行动。
- live/fixture/read-only 等边界进入统一 BoundaryStrip，不以原始布尔串展示。
- 导航只展开当前组；支持 Cmd/Ctrl+K 搜索页面、项目和最近对象。
- 移动端保留现有 focus trap，并增加当前 Project、当前一级导航和底部步骤行动。

### 6.2 Dashboard

- 第一屏保留两个主任务，弱化“已保存计划”为次级入口。
- 第二块是 Needs attention queue，不先展示五个平权 KPI 卡。
- KPI 改为业务结果：准时交付、Evidence coverage、有效 Scope、需人工处理。
- Training、Provider、字段等工程运营信息进入 Advanced Operations。
- 所有异常直接给出下一步，不只链接到列表。

### 6.3 Project / Scope / Query

- Project Overview 汇总目标、Scope、最近运行、数据和交付。
- Scope Builder 采用分组表单：业务对象、平台市场、Query、时间、用途和隐私。
- QueryTerm 显示 active/rejected/deprecated、贡献和噪声。
- Scope 变更先展示影响：哪些 Plan/Run/Alert 会过期。

### 6.4 Workflow Planner / Plan / Version

- 五步：目标与范围 → 能力与来源 → 调度预算 → 交付 → 审阅保存。
- 页面持续显示 Summary rail；移动端改为底部 Summary sheet。
- Simple mode 只显示业务结果；Advanced 展开 canonical 配置。
- held 不只显示状态码，要显示 blocker、影响步骤和修复动作。
- Save、Approve、Activate、Run 四个动作彻底分离。
- 版本对比按业务变化、运行影响、成本、字段和治理分类，而非仅 JSON diff。

### 6.5 Workflow Run / Task

依赖 RUN-02/03/04/05/07/08/10 和 GOV 持久化。

- 头部：状态、业务影响、开始/结束、Provider、预算、允许行动。
- 主区：Step timeline，Attempt 折叠在 Step 下。
- 右侧：Evidence、Budget、Provider Health、Fallback decision。
- degraded 显示缺失字段和受影响交付；empty-valid 明确不是失败。
- retry/resume/cancel 先展示影响和幂等边界；没有 runtime 能力时保持只读。

### 6.6 Batch Workbench

依赖 BATCH-001~007。

- Paste/upload 输入 → 规范化预览 → 分类和未分类队列 → 路由 → 执行 → 质检。
- 每个输入有 canonical、平台、资源、Capability 和状态。
- 未分类输入不猜测执行；允许批量规则和逐项人工处理。
- 批次级预算、进度、失败局部重跑和 Dataset 结果固定在顶部。

### 6.7 Data Assets

依赖 DAT-001~008。

- 默认使用 table/list，而不是同构卡片网格。
- 行级 Evidence/Lineage drawer；支持字段级来源、标准化和 confidence。
- Dataset Version detail 按概要、字段、质量、血缘、漂移、导出组织。
- 作者隐私状态和 Relationship Graph 禁用必须可见且不可被普通用户绕过。

### 6.8 Intelligence / VOC / Delivery

依赖 INS-001~007。

- 详情采用 Claim → Evidence → Impact → Recommended action。
- topic/sentiment/pain/need 均可钻 Raw/Evidence。
- 报告、告警、通知统一 Preview → Approve → Send 状态。
- Useful Alert feedback 作为业务事件，而不是只记录“已读”。
- 低覆盖或模型不确定性在发布前可见并可阻断。

### 6.9 Capability Market / Provider Governance

依赖 CAP-009/010、GOV-001/002/003、PAD-06~08。

- 场景视图用于发现；矩阵用于覆盖；比较用于决策；治理用于状态变化。
- 候选详情先显示 hard gates，再显示评分。
- unknown/blocked/unsupported 不提供“运行”暗示。
- Candidate → verified/partial/blocked 的变化需要 Evidence、reason、actor 和 timestamp。
- Live Call 使用专门 Gate，不与 readiness、fixture 或 credential reachability 混淆。

## 7. 跨模块交互合同

### Project context

- 所有 Project-scoped 页面读取同一 URL/query-state。
- 切换 Project 前提示未保存状态；切换后清理不兼容的 Scope/filters。
- list → detail → Evidence → back 保留滚动、筛选和选择。

### Evidence drawer

- 输入：claim/status/row ID + Project context。
- 输出：grade、source、captured_at、lineage、limitations、canonical IDs。
- 未授权字段显示缺失原因，不回退为猜测。

### ActionGate

- `preview`：无写入。
- `save`：创建不可变版本，不激活。
- `activate`：改变计划状态，不代表 runnable。
- `run`：通过动态 gates 后创建执行。
- `send/export`：产生外部或数据副作用。
- `live_call`：需要 exact Provider 授权和 CallAudit。

### State summary

- label：用户语言。
- canonical state：Advanced only。
- cause、impact、evidence、next_actions：必填或明确 unavailable。

## 8. 执行 TODO 总账

以下 UIX 编号是跨模块整合层，不复制底层 TODO；每项都引用现有任务作为依赖。

### Wave 0 — 设计治理

- [x] **UIX-00 设计系统基础**：建立 DESIGN.md、semantic tokens、voice/tone、
  style notes 和静态 UI kit；记录参考来源和禁止复制边界。
- [x] **UIX-01 设计资产批准**：已确认主色、密度、默认/Advanced 分层和关键屏幕
  优先级，设计系统已标记为 stable。

### Wave 1 — 无后端依赖的 UI 基础

- [x] **UIX-02 Token foundation**：把 tokens 接入 `globals.css`；先迁移 AppShell、
  Sidebar、TopBar、MobileNavigation 和 `workbench-ui.tsx`。不做全仓换色。
  - 验收：迁移文件零新增 raw hex；对比度 AA；focused tests、TS、ESLint、build。
  - 2026-07-22 证据：迁移文件 raw hex 为 0；19/256 unit、TS、全量 ESLint、
    26/26 build 通过；Playwright 1440/375、抽屉 Escape focus restore、无横向溢出
    通过。视觉检查为本地只读证据，不代表 Provider、production 或 GA。
- [ ] **UIX-03 State and feedback primitives**：统一 StatusBadge、StatusSummary、
  BoundaryStrip、ActionGate、Empty/Loading/Error、EvidenceDrawer shell。
  - 验收：状态不只靠颜色；disabled 有原因；overlay focus 恢复；reduced motion。
  - 当前完成：StatusPill、ActionGate、ActionButton、EmptyState 与 overlay focus 基础；
    StatusSummary、BoundaryStrip、统一 Error/Loading、EvidenceDrawer shell 待续。
- [ ] **UIX-04 Content layer**：建立业务词汇与 Advanced diagnostics；清理默认页面的
  fixture/fingerprint/RawRecord/provider_call 等实现语言。
  - 验收：默认关键流程无 debug terms；Advanced 保留 canonical evidence。
  - 当前完成：Dashboard 已完成 Default/Advanced 分层；其余核心屏幕待续。

### Wave 2 — 现有数据即可优化的核心入口

- [x] **UIX-05 Shell + Project context**，映射 `UI-008`：统一 Project URL/query、
  list/detail/back、深链和未保存切换保护。
  - 当前完成：`project_id` 深链、本地偏好校验、跨标签同步、浏览器返回恢复、
    Planner 未保存项目切换保护，以及 Dashboard/Domain/Intelligence 成功响应后才标记
    过滤已应用。Intelligence list/detail/Evidence/back 保留 Project、Scope、filters、
    Intelligence 与 Evidence；详情 Project 错配 fail closed，下游 Task/RawRecord 继续
    携带 `project_id`。
  - L2 本地证据：Web `21/264` unit、TypeScript、全量 ESLint、`26/26` build；
    Playwright desktop/mobile `2/2` 和 1440/390 人工视觉检查通过，无横向溢出、无新增
    raw hex。未发生 Provider、数据库、生产、CI、commit、push 或 deploy。
- [x] **UIX-06 Dashboard JTBD**，映射 `UI-002/003`：两个主任务、Needs attention、
  Outcome summary、Advanced operations。
  - 2026-07-22 L2 本地证据：两项主任务 + 已保存计划次入口、Outcome summary、
    cause/impact/next-action 异常队列、优先洞察和 Advanced Operations 已实现；Mock
    Dashboard 同步按 Project 过滤。Web `20/261` unit、TS、ESLint、26/26 build、
    目标 Playwright 桌面/移动与 1440/390 零横向溢出通过；无 live/production 证据。
- [ ] **UIX-07 Browse surfaces**：Projects、Sources、Tasks、现有 Data/Intelligence
  列表使用统一 table/filter/density/empty/error 体系。

### Wave 3 — 与 P0 执行内核一起交付

- [x] **UIX-08 Planner and lifecycle**，依赖 `WFL-001`、`RUN-04`：五步 Planner、
  blocker summary、版本影响比较、Save/Approve/Activate/Run 分离。
  - `UX-B03` 本地边界子批已完成：五阶段导航在 current Preview 后激活
    `Review 与保存`；阻断摘要给出 cause/impact/missing fields/next action，版本影响
    覆盖 v1、vN→vN+1 与 semantic no-op。Save 保持唯一可执行动作，Approve、Activate、
    Run 只作为带原因的禁用 gate，不接入 fixture-only Run 内核。
  - L2 本地证据：focused unit `73/73`、TypeScript、目标 ESLint、`26/26` build、
    Planner persistence Playwright desktop/mobile `2/2` 和 1440/375 人工视觉检查通过；
    无横向溢出、外部请求为 0。`RUN-04` 状态合同已完成；WFL-001A 后端现已提供
    write-free runnable Version gate，并让 fixture Run 写入口只接受 active Plan 的
    current、完整 resolved Version。
  - `UX-B04` 本地动作子批已完成：Planner 消费 current Version gate，并将 Save、
    Approve、Activate、Run 拆为四个独立回执阶段；未保存修改、状态错序、非 current
    Version 和 gate blocker 均禁止 Run。最终 Run 固定为 `fixture-primary-v1` 本地样例，
    UI 同时展示 Provider、凭证、浏览器与 LLM 调用为 0，不使用 live/production 文案。
  - 2026-07-23 L2 本地证据：Web 定向 `125/125`、Planner `70/70`、TypeScript、目标
    ESLint、Next `27/27` build；FastAPI transition `4 passed`、fixture gate/create
    `3 passed`；Playwright desktop/mobile `2/2` 覆盖 1440/375。本项在本地 fixture
    产品边界完成；durable governance audit、RUN-07/08/10 composition、Template
    lifecycle UI 与 live adapter 继续归 WFL-001/UIX-09/UIX-10，不构成 UIX-08 缺口。
    GitNexus 重建为 `23,306 nodes / 40,259 edges / 300 flows`，定向关键符号均 LOW；
    仓库级 CRITICAL 是 `99` 个 tracked dirty 文件的累计结果，不归因于本批。
- [ ] **UIX-09 Run observability**，依赖 `RUN-02/03/04/05/07/08/10`：完整状态、
  Step/Attempt、retry/fallback/resume、budget、health 和允许行动。
  - RUN-04 子批已落地：Run list/detail 显示 held 与 empty-valid 状态；held 详情以
    cause/impact/missing fields/recovery direction 解释 frozen evidence，并区分 completed
    receipt 与 failed/no-receipt Step。页面不新增 retry、cancel 或 live action。
  - RUN-05 Shadow 读取子批已落地：Run 详情复用现有只读 API，默认先显示业务化的
    样本一致/差异、缺失必填字段与人工治理建议；implementation、digest 和 Evidence
    进入折叠诊断层。空列表不解释为路线等价，任何结果都不会自动修改 Catalog、route
    ranking、切换路线或调用 Provider。
  - 2026-07-23 L2 本地证据：Web focused `7 passed`、full unit `275 passed`、
    TypeScript、目标 ESLint、Next `27/27` build；FastAPI Shadow read/approved-route
    `2 passed / 1 existing warning`。Playwright CLI 在隔离端口 3107 验证 desktop
    差异/诊断展开、无证据空态与 390px 响应式，console error 为 0；定向 GitNexus
    impact 为 LOW。已知增量索引 UTF-8 故障后强制重建为
    `23,320 nodes / 40,300 edges / 300 flows`；仓库级 CRITICAL 是累计
    `99 files / 623 symbols / 113 affected items` overlay，不归因于本切片。
  - RUN-02/03 读取子批已落地：独立只读
    `GET .../workflow-runs/{run_id}/attempt-fallback-evidence` 组合持久化 Step Attempt 与
    FallbackDecision；默认层呈现每个 Step 的尝试/重试结果与备用路线结论，错误码、幂等
    hash、implementation、七段门禁、字段/成本 Evidence 与 digest 进入折叠诊断层。
    无 Fallback Evidence 时明确不推断路线可用，也不执行切换。
  - 2026-07-24 L2 本地证据：FastAPI focused `12 passed / 48 deselected /
    1 existing warning`、full API `1217 passed / 73 skipped / 1 warning`；Web focused
    `8 passed`、full unit `276 passed`、TypeScript、目标 ESLint、Next `27/27` build。
    Playwright CLI 在 1440 与 390px viewport（375px client width）完成 held/complete、
    诊断展开、Fallback 空态与响应式验收，无横向溢出、console error 为 0。共享
    `WorkflowRunDetailResponse` 的 upstream impact 为 HIGH，因此保持不变并采用独立子资源；
    新 GET route 为 LOW/0 直接消费者。Schema 文件因唯一直接 importer 是共享 route hub，
    文件级上游放大为 CRITICAL/70 flows，已由完整 API/Web 和 response contract 回归覆盖。
    GitNexus 刷新为 `23,510 nodes / 40,590 edges / 300 flows`；累计 detect_changes 为
    `99 files / 283 symbols / 300 affected flows / CRITICAL`，不归因于本切片。
  - RUN-07/08 只读产品组合已落地：独立
    `GET .../workflow-runs/{run_id}/checkpoint-budget-evidence` 按 tenant/Plan/Version/Run
    读取 checkpoint 与五维 budget ledger；默认层显示已确认分页、记录数、使用/上限与
    held 原因，cursor、policy/ledger/checkpoint digest 和 Evidence 折叠。空态明确不表示
    可安全恢复或预算无限；恢复与预算覆盖动作固定不可用。
  - 2026-07-24 L2 本地证据：FastAPI focused `13 passed / 50 deselected / 1 warning`、
    full API `1223 passed / 73 skipped / 1 warning`；Web focused `9 passed`、full unit
    `277 passed`、TypeScript、ESLint、Next `27/27` build。Playwright CLI 在 1440/390
    验证 held/not-configured、无 mutation control、无横向溢出及 console 0 error/0 warning。
    GitNexus `23,653 nodes / 40,870 edges / 300 flows`；新增 handler、mapper、panel 均 LOW，
    compare-main CRITICAL `100 files / 634 symbols / 113 affected items` 是累计 overlay。
  - RUN-10 只读产品组合已落地：独立
    `GET .../workflow-runs/{run_id}/provider-health-evidence` 精确绑定 frozen Step
    Primary/Fallback 顺序与最新 Project-scoped 快照，区分 active/expired routing TTL，并
    仅在 capability/original order 完全匹配时呈现 route feedback。默认层展示观测数、
    健康、成功率/P95 与候选顺序建议，digest 折叠；无快照明确为未观测，不推断健康。
  - 2026-07-24 L2 本地证据：FastAPI focused `21 passed / 57 deselected / 1 warning`、
    full API `1225 passed / 73 skipped / 1 warning`、Ruff/Mypy；Web focused `10 passed`、
    full `278 passed`、TypeScript、ESLint、Next `27/27` build。Playwright 1440/390 无横向
    溢出，console 0 error/0 warning，并验证 active/expired/unobserved 与只读 feedback。
    GitNexus `23,756 nodes / 41,082 edges / 300 flows`，定向符号/route LOW；累计
    compare-main `100 files / 630 symbols / 113 affected items / CRITICAL` 是跨批 overlay。
  - 2026-07-27 已完成 fixture-only Run action-gate 产品层：独立只读
    `workflow_run_action_gates.v1` 以固定顺序统一 retry、resume、cancel、budget override、
    route switch 的 precondition/cause/next-action/evidence。`ready_for_review` 与实际动作
    可用性分离，五类动作均保持 `action_available=false`，页面固定 `可执行 0`，没有
    mutation control。
  - 当前验证：后端 action-gate focused `15 passed`、完整 workflow execution routes 与
    新单元测试 `68 passed / 1 existing warning`；Web focused `11/11`、full `279/279`、
    TypeScript、ESLint、Next `27/27`；Playwright 1440/390 无横向溢出且 console
    `0 error / 0 warning`。UIX-09 的 fixture-only 只读 observability 已闭合。
  - mutation/state integration 正式规格已于 2026-07-27
    `approved_as_specified`；正式实施计划
    `docs/superpowers/plans/2026-07-27-uix-09-workflow-run-mutation-state-integration.md`
    已由 Owner 无修订批准。它按 Phase A-F 分离 pure contract、source-only
    persistence、fixture command、API/Web、PostgreSQL candidate 与另行立项的 live
    executor。
  - Phase A pure contracts/tests 已在本地完成：新增严格 v2 gate、审批/命令/回执、
    tenant-scoped canonical digest、Owner-only 纯授权与五类 action state-effect
    compiler，但没有接 route、Web、共享 model 或持久化。验证为 focused
    `26 passed`、相邻 workflow `82 passed`、full API
    `1257 passed / 73 skipped / 1 existing warning`，Ruff 与 strict Mypy 通过。
    Phase B 已在 Owner 明确授权并确认保守 CRITICAL `StepRunAttempt` 风险后完成：
    revision source `202607270043`、retry generation 与六个 tenant-scoped action
    persistence tables 仅在本地 SQLite/source 层落地。focused `54 passed`，完整
    Workflow + Provider Health `789 passed / 1 existing warning`，Ruff、strict
    Mypy、Alembic single head 与禁止边界扫描通过。Owner 随后授权并完成 Phase C
    fixture-only command service：本地 Owner approval、单次消费、canonical
    idempotency、五类批准 state effect、零写入 replay 与 hash-chain audit 已由
    focused `5 passed`、相邻 `97 passed`、完整 Workflow + Provider Health
    `803 passed / 40 skipped / 1 existing warning` 验证。Phase C 没有新增 route、
    Web mutation、Provider/Credential 或 executor wiring；下一步是 Phase D
    API/Web 的独立 Owner decision。Provider Health 继续不主动探测、不改
    Catalog/当前路线、不自动切路；API Key、Credential、Provider/网络、
    PostgreSQL、migration execution、CI、Git、deploy 与 production 仍未授权。
  - Owner 随后授权 Phase D API/Web mutation surface。当前本地实现已提供
    authenticated Owner approval/action POST、严格 v1/v2 transport/mapper、审核抽屉、
    独立幂等键、回执/精确重放与 authoritative refresh。API focused `5 passed`、
    full `1286 passed / 73 skipped / 1 existing warning`；Web focused
    `15 passed`、full `283 passed`、TypeScript、ESLint、Next `27/27` build；
    production-mode Playwright 1440/390 验证 v1 无控制、v2 disabled/available
    action、drawer、receipt、focus trap/Escape/refresh fallback、零横向溢出和 console
    `0 error / 0 warning`。Owner 随后授权 HIGH Provider Health Literal 静态基线
    窄修复：复用既有三值 alias，仅增加 import 与局部变量标注，不改变运行时值或分支。
    affected-route regression `70 passed`、strict Mypy 3 个 Phase D source 全绿、fresh
    full API `1286 passed / 73 skipped / 1 existing warning`。Phase D 现已本地完成。
    下一步仅决定是否为一个明确 disposable target 打开 Phase E PostgreSQL。API Key、
    Credential、Provider/网络、live executor、CI、Git、deploy 与 production 仍未授权。
  - 2026-07-27 已完成正式 mutation/state integration 规格：
    `docs/superpowers/specs/2026-07-27-uix-09-workflow-run-mutation-state-integration-design.md`。
    方案冻结为 v1 历史合同 + current v2 门禁、Owner-only typed command、单次审批 receipt、
    action-context version/row lock/hash audit；retry/resume 仅准备 held→ready，
    override 不自动继续，running cancel 等待 executor ack。Owner 已于 2026-07-27
    无修订批准六项决策，状态为 `approved_for_implementation_planning`；下一批可制定
    实施计划，但未自动授权 implementation/migration/PostgreSQL/Provider/Credential/live
    action。
  - 后续已按独立 Owner 门禁完成 mutation Phase A-D 与 exact disposable PostgreSQL
    Phase E candidate；Phase E runner 已销毁且端口关闭。Phase F live-executor 规格与
    实施计划也已获批，但按 F0-F6 分门禁执行：F0 pure contracts 与单独授权的 F1
    durable local persistence 已本地完成。F1 新增八张 relationship-free coordination
    model、tenant-scoped repository、source-only revision `202607280044` 和 disposable
    SQLite rollback/replay/permit-consumption 证据；focused `12`、related `238`、full API
    `1317 passed / 80 skipped / 5 warnings`，Ruff/format/Mypy/diff 与 Alembic single head
    044 通过。SQLite 未被宣称为 PostgreSQL concurrency/row-lock 证据，migration 未
    执行。下一步仅为 F2A connection-free candidate source 的独立 Owner decision；
    API key、Credential、Provider/network、F2B-F6、CI、Git、deploy 与 production
    仍关闭，因此 UIX-09 仍保持 partial。
  - Owner 随后单独授权并完成 F2A connection-free source slice：新增 target-unbound
    revision-044 guard、8 项 gated PostgreSQL candidate source、7 项 guard self-test 与
    未绑定 F2B authorization packet template。组合 executor 回归 `34 passed`；无授权
    candidate suite `8 skipped` 且显式收集 8 项；Ruff/format/Mypy/bash/diff 和 single
    source head 044 通过。没有 exact target、连接、migration、image pull 或 runner；
    下一门禁仍是一个完整 exact F2B tuple 的 Owner 逐字批准，UIX-09 保持 partial。
  - Owner 后续的通用 `同意下一门禁` 仅打开 F2B exact-tuple packet preparation。
    L1 只读 preflight 已选择新的 loopback target
    `127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test` 与独立 runner
    `data-scrapy-uix09-phase-f2b-pg15-20260728`：端口/名称空闲、Docker 29.4.1 可达、
    本地 `postgres:15` digest 已固定，因此不需要也未授权 image pull。精确 tuple
    `--check-only`、Alembic single head 044 与 packet guard `7 passed` 通过；没有启动
    container、连接、SQL 或 migration。F2B runtime 仍需 packet 授权字符串的逐字批准，
    UIX-09 继续保持 partial。
  - F2B 后续获得 exact authorization string 的逐字批准，并仅在独立 PostgreSQL
    15.18 target 上执行。前三次 relationship-free seed lifecycle 失败均作为负证据
    保留且每次 cleanup 通过；LOW/0 测试夹具修复后，第四次 candidate `8 passed`，
    final head 044、8 张 executor 表、`live_boundary_true_rows=0`。exact runner 已销毁，
    端口 55444 已关闭。该证据上限为 L2 disposable local PostgreSQL；F3、Credential、
    Provider/network、CI、Git、deploy 与 production 仍关闭，UIX-09 继续保持 partial。
- [ ] **UIX-10 Governance gate UX**，依赖 `GOV-001/002/003`：审批、transition reason、
  durable CallAudit 和 live gate receipt。
- [ ] **UIX-11 Provider UX**，依赖 `PAD-06/07/08`：Reddit OAuth、credential
  reachability 和 YouTube/Reddit live gate 仍分别授权；UI 不自动触发。
  - 平台凭证设置子批已完成本地实现：七个平台统一进入 `/settings/platforms`，Secret
    仅单向提交到 Workspace-scoped encrypted vault，页面只呈现 configured 状态；
    保存与删除不执行 reachability、client construction 或 Provider call。
  - vault 主密钥仍由部署环境引导；revision 035 仅生成 migration source，未执行真实
    migration。vault reference 尚未接入 live resolver，Reddit OAuth 与 live gate 仍待
    独立批次，因此 UIX-11 保持 partial。
  - L2 证据：API `34 passed`、Web full unit `23 files / 270 tests`、scoped
    lint/type/build、Playwright desktop/mobile `2/2` 及 375/1440 视觉检查通过；
    外部请求为 0，未注入真实 API key。

### Wave 4 — 与 P1 业务对象一起交付

- [ ] **UIX-12 Query & Batch**，依赖 `QRY-002/004/005/006`、`BATCH-001~007`。
- [ ] **UIX-13 Data asset explorer**，依赖 `DAT-001/002/004~008`。
- [ ] **UIX-14 Capability decision workspace**，依赖 `CAP-009/010`、`BRW-001~005`。
- [ ] **UIX-15 Intelligence & delivery**，依赖 `INS-001~007`。

### Wave 5 — 横向质量与发布

- [ ] **UIX-16 Responsive and accessibility**，映射 `UI-009/010`：所有 critical
  flows 在 375/768/1024/1440，无横向溢出、全键盘、focus、读屏和自动扫描。
- [ ] **UIX-17 Visual regression**：为 Shell、Dashboard、Planner、Run、Batch、
  Dataset、Intelligence、Capability 建立稳定 fixture 截图基线；截图只能证明视觉，
  不能替代行为测试。
- [ ] **UIX-18 Product analytics**：建立 task completion、time-to-first-result、
  blocker recovery、Evidence drilldown、alert usefulness 和 adoption 基线。
- [ ] **UIX-19 AT/KPI/GA**：与 AT-01~10、12 KPI、CI/staging/canary/production/GA
  证据合并评审，不把本地视觉通过当成 GA。

## 9. 推荐实施批次

| Batch | 范围 | 现有依赖 | 退出证据 |
|---|---|---|---|
| UX-B01 | tokens + AppShell + shared primitives | UIX-01/02 | unit/TS/lint/build + 375/1440 + contrast |
| UX-B02 | Dashboard + Project context | UI-002/003/008 | main task E2E + back/deep-link + visual diff |
| UX-B03 | Planner lifecycle | WFL-001, RUN-04 | save/approve/activate/run boundary tests |
| UX-B04 | Run observability | RUN-02~10, GOV | state/retry/fallback/resume/budget/audit E2E |
| UX-B05 | Batch + Data assets | QRY/BATCH/DAT | mixed input → Dataset + lineage E2E |
| UX-B06 | Capability + Intelligence + Delivery | CAP/BRW/INS/PAD | gate/evidence/publish/send boundaries |
| UX-B07 | Critical-flow accessibility and release | UI-009/010, AT/KPI | scan + keyboard + visual + candidate smoke |

`UX-B02` 已完成。`UX-B03` 已关闭五阶段 Planner、Review、blocker/version impact 与
Save/Approve/Activate/Run 本地呈现边界；RUN-04、RUN-05 与 RUN-02/03 已分别补齐 fixture
Run 状态、Shadow 和 Step Attempt/Fallback 的只读观测。下一子批继续受 `WFL-001`
约束，不能用 fixture-only Run 内核制造尚不存在的产品 runnable 能力；UX-B04 下一步
优先组合 RUN-07 checkpoint 与 RUN-08 budget，再接 RUN-10 health，所有执行动作仍需
独立治理与 live authorization。

## 10. 每批完成定义

- GitNexus impact 在编辑 symbol 前完成；HIGH/CRITICAL 先报告。
- diff 只包含批准的批次文件，不覆盖既有 dirty overlay。
- 不引入新的 raw hex、重复组件或无批准 dependency。
- Default/Advanced、loading/empty/error/disabled/success/held/degraded 都有明确表现。
- 375px 与 1440px 无页面横向溢出。
- 全键盘路径、focus visible、overlay focus restoration 通过。
- focused unit、相关 E2E、TypeScript、ESLint、Next build 通过。
- 视觉回归由 fixture 截图验证，但与行为、live 和 production 证据分开。
- 更新 TODO、traceability 和 context；标注事实、证据等级与剩余外部门。

## 11. 风险与防护

| 风险 | 防护 |
|---|---|
| 全仓换色导致 267 色值大 diff | 只迁移 shared primitive + 单屏 slice |
| UI 先于 runtime 制造假按钮 | 无后端状态时维持只读并显示 missing gate |
| 视觉升级掩盖 fixture 边界 | BoundaryStrip + Advanced evidence，保持 L2 标签 |
| Default/Advanced 状态分叉 | 共用同一 DTO；只改变呈现，不复制数据状态 |
| 移动端表格不可用 | Summary row/card + labeled horizontal region |
| 可访问性后补成本高 | 每批 Done definition 强制 keyboard/focus/contrast |
| 方案与 TODO 再次漂移 | 本文提供 UIX 映射，`TODO.md` 仍是执行状态唯一事实源 |

## 12. 产品 Owner 已确认的设计决定

1. 保留暖色 + Rose 品牌骨架，并将 Rose 从状态色收敛为品牌/主行动色。
2. 采用 Default 业务模式 + Advanced 诊断模式作为全局信息分层。
3. `UX-B01 → UX-B02` 已完成；`UX-B03` 本地生命周期呈现边界已完成，runtime 子批仍
   依赖 `WFL-001`、`RUN-04`。PAD-06 继续按原 Provider P0 顺序独立推进。
