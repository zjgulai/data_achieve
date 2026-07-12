---
title: GOAL-V2-02 能力矩阵与六入口导航设计
doc_type: design
module: capability-market
topic: goal-v2-02-capability-matrix-navigation
status: approved
review_status: approved
created: 2026-07-11
updated: 2026-07-11
owner: self
source: human+ai
product_prd: ../../product/product-prd-social-media-automation-platform-v2.md
parent_design: 2026-07-10-social-media-automation-platform-v2-design.md
depends_on: ../plans/2026-07-10-goal-v2-01-capability-contract-foundation.md
evidence_level: L1-local-repo-and-L2-targeted-tests
provider_call: false
database_migration: false
production_boundary: production unchanged
goal_execution: local_implementation_complete
---

# GOAL-V2-02 能力矩阵与六入口导航设计

> 本文固化用户已确认的路线 A：以 `capability_catalog.v1` 文件为唯一能力事实源，构建只读 7×6 能力矩阵、能力市场三视图、六入口导航和全局项目选择器。本 Goal 不引入 Capability 数据库持久化，不进入 MonitoringScope、WorkflowPlan V2、Provider Live 或生产部署。

## 1. 执行摘要

当前仓库已经完成 GOAL-V2-01：后端具备 7 个海外平台的统一枚举、Capability Implementation、Assertion、Constraint、Evidence、八维评分、规范 Fixture Loader，以及 `external_provider_catalog.v1` 兼容投影。

GOAL-V2-02 把这些合同变成可使用的产品读模型：

1. 后端从规范 Catalog 派生 7 个平台 × 6 个访问通道，共 42 个显式矩阵格。
2. 前端能力市场统一从后端读取能力事实，不再维护独立的 Provider、政策、状态、成本和证据副本。
3. 能力市场提供场景、矩阵、列表三种视图，并可下钻到 Assertion、Implementation、Constraint 和 Evidence。
4. 网站一级入口收敛为工作台、监测项目、采集工作流、数据资产、洞察与交付、能力市场六项。
5. 桌面和移动导航使用同一份配置；Project Selector 在全局可见，但不会虚构尚未实现的全站项目过滤能力。

本 Goal 只建立只读产品面和导航信息架构。35 条现有 Assertion 继续保持 `candidate`，不会因矩阵聚合、页面展示或用户筛选升级为可执行能力。

## 2. 已验证基线

### 2.1 产品与文档事实

- 当前产品源头是 `docs/product/product-prd-social-media-automation-platform-v2.md`。
- 当前系统总体设计是 `docs/superpowers/specs/2026-07-10-social-media-automation-platform-v2-design.md`。
- 旧 `product-prd-data-intelligence-hub-stable.md` 和 PRD2 workflow 只保留为历史基线。
- `TODO.md`、`.codex/ralph-loop.local.md` 和 `.kiro/plan/*` 仍保留旧 PRD2/Loop 状态，不能继续作为 V2 当前执行真相。

### 2.2 代码事实

- 规范运行时事实源：`apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json`。
- 当前 Catalog：7 个 Implementation、35 条 Assertion、14 条 Evidence。
- 当前 35 条 Assertion 全部为 `candidate`。
- 当前 7 个 Implementation 全部属于 `official_authorized_api`；其余 5 个访问通道尚无 Implementation。
- `apps/api/src/data_intelligence_hub/services/capability_catalog.py` 已提供严格 Loader、平台过滤、缓存隔离和 V1 兼容投影。
- `/api/automation/social-provider-*` 继续承担兼容的 Fixture、Readiness、Gate、Preview 和 Approval Template 链。
- 前端 `apps/web/src/lib/api-market-catalog.ts` 仍维护 18 个 Endpoint 的独立静态能力事实。
- 当前 Sidebar 使用 7 个业务域、9 个全局中心和 7 个工程中心入口；移动端没有与桌面端等价的完整主导航。
- 代码中尚无 `/api/capabilities/*`、MonitoringScope、WorkflowPlan V2、RoutePlan、Fallback 或 Shadow 实现。

### 2.3 新鲜验证

- Capability/Social Provider API 定向测试：62 项通过。
- API Market/Social Provider Web 定向单测：21 项通过。
- `git diff --check`：通过。
- 独立 TypeScript gate 返回 6 个 `TS2345`，集中在 readonly 测试 Fixture 与可变 DTO 数组之间的类型不兼容。
- 本轮没有执行完整 API 回归、Web build、Playwright、数据库迁移、远端 CI、Provider 调用或生产检查。

### 2.4 固定边界

```text
provider_call=false
provider_call_attempted=false
credential_read_attempted=false
live_client_created=false
production_write_allowed=false
database_migration=false
production unchanged
```

## 3. Goal 与非目标

### 3.1 Goal

GOAL-V2-02 交付一个由单一 Canonical Catalog 驱动、可解释、可筛选、可下钻、桌面与移动一致的能力市场，并将网站一级入口收敛为六项。

### 3.2 覆盖的 PRD 需求

- `CAP-001`：7×6 矩阵具有显式状态。
- `CAP-004`：矩阵格是 Assertion 的聚合读模型。
- `CAP-008`：前后端使用单一 Catalog 数据源。
- `CAP-009`：矩阵格可下钻到资源、操作、实现、局限和证据。
- `CAP-010`：支持实现比较的只读产品面。
- `UI-001`：一级导航收敛为六项。
- `UI-004`：能力市场提供场景、矩阵、列表三视图。
- `UI-005`：矩阵格尺寸和状态布局稳定。
- `UI-006`：格详情使用侧边抽屉。
- `UI-009`：375px 与 1440px 视口通过验收。

### 3.3 非目标

- 不创建 Capability、Assertion、Evidence 或 Health Snapshot 数据表。
- 不新增 Alembic migration，不做 Fixture 到数据库的 seed、双写或回填。
- 不实现 MonitoringScope、Query Compiler、WorkflowPlan V2、Resolver、Fallback 或 Shadow。
- 不创建 `social_api` Collector，不把 Fixture Preview 接入真实 Source/Task/RawRecord 写路径。
- 不安装 Provider SDK，不读取凭据，不创建 Live Client，不调用外部 Provider。
- 不改变 `/api/automation/social-provider-*` 现有兼容行为。
- 不删除旧页面或旧 URL，不进行 Automation Service、Social Provider Service 的整体重构。
- 不执行 push、PR、merge、deploy、生产浏览器、生产写入或真实 API E2E。

## 4. 已确认设计决策

### 4.1 Matrix 是派生读模型，不是新的事实源

42 个矩阵格由 `PlatformId × AccessChannel` 枚举笛卡尔积生成。Implementation、Assertion、Constraint、Evidence 和状态仍只存在于 Canonical Catalog。

矩阵 API 每次从经过 Pydantic 严格校验的 Catalog 派生读模型，并复用现有只读缓存。它不保存聚合结果，不维护第二份状态，不生成数据库行。

选择这一方案的原因：

- 当前所有能力事实仍是版本化、可审阅的 L1 Fixture。
- 矩阵格本质上是 Assertion 聚合视图，持久化会产生同步和双写问题。
- GOAL-V2-04 的 Candidate、Verification、Publication 才首次需要动态写入能力事实；持久化应在那个 Goal 根据真实写入合同设计。

### 4.2 前端只保留展示增强，不保留能力事实

前端允许保留 Endpoint 的标题、业务摘要、示例参数和 Fixture 响应示例，但以下字段必须来自后端：

- platform、provider、access channel、delivery form、deployment mode
- auth mode、credentials、quota、cost、policy、blocked actions
- support status、resource、operation、score、last verified time
- evidence grade、Evidence URL、Capability 限制和边界标志

展示增强以 `provider_id + endpoint_id` 为键。Parity Test 必须保证：

1. 每个前端展示键都能在后端 Implementation 的 `supported_endpoints` 中找到。
2. 缺少展示增强的后端 Endpoint 使用通用详情呈现，不影响能力事实。
3. 前端多出无法映射的 Endpoint 时测试直接中止。

### 4.3 Candidate 永远不能因展示而升级

矩阵的 `summary_status` 只用于显示聚合状态，不修改任何 Assertion 的 `support_status`。

- `candidate` 不进入自动运行路线。
- Matrix、List、Scenario 视图都必须显示 Candidate 的证据级别和不可执行原因。
- 页面不得出现会被理解为真实执行的“运行”“立即采集”“启用 Provider”操作。
- 现有“生成预案”继续进入 Fixture/Review 链，不增加 Live 行为。

### 4.4 使用现有 `/api-market` 路由

本 Goal 不新增平行的 `/capabilities` 前端入口。`/api-market` 升级为“能力市场”，并在同一页面提供：

- `view=scenarios`
- `view=matrix`
- `view=list`

现有 `/api-market/[endpointId]` 保留，详情页改为从后端能力事实与前端展示增强组合生成。

### 4.5 六入口只重组导航，不删除业务页面

一级入口固定为：

| 一级入口 | 当前主路由 | 本 Goal 处理方式 |
|---|---|---|
| 工作台 | `/dashboard` | 保留现有页面 |
| 监测项目 | `/projects` | 保留现有页面并加入 Project Selector |
| 采集工作流 | `/automation` | 保留 Automation；Tasks、Sources 作为次级入口 |
| 数据资产 | `/datasets` | Datasets 为主；Raw Records、Entities 作为次级入口 |
| 洞察与交付 | `/intelligence` | Signals、Reports、Alerts、Notifications 作为次级入口 |
| 能力市场 | `/api-market` | 升级为场景、矩阵、列表三视图 |

`/domain/*`、`/toolkit`、`/tasks`、`/sources`、`/raw-records`、`/entities`、`/signals`、`/reports`、`/alerts` 和 `/notifications` 继续可访问，只是不再占用一级导航位置。

### 4.6 Project Selector 不虚构全站过滤

Project Selector 复用现有 `GET /api/projects`，只允许选择当前 Workspace 返回的 active Project。

本 Goal 的选择状态用于：

- 在全局顶部显示当前项目上下文。
- 为已经支持 `project_id` 的链接和请求提供默认值。
- 为能力市场后续“用于哪个项目”入口保留明确上下文。

尚未支持项目过滤的旧页面必须显示“全局数据”或“当前页面未应用项目过滤”，不能静默展示全局数据并让用户误以为已经按项目过滤。全站数据 API 改造属于后续 Goal。

## 5. 后端设计

### 5.1 模块边界

新增职责单一的模块：

- `schemas/capability_matrix.py`：Matrix、Cell、Summary、Filter 和详情响应合同。
- `services/capability_matrix.py`：42 格生成、状态聚合、过滤和详情投影。
- `api/routes/capabilities.py`：只读 HTTP 入口、鉴权和错误映射。

现有 `schemas/capability_catalog.py` 和 `services/capability_catalog.py` 继续负责原子合同与 Canonical Catalog Loader，不吸收 UI 聚合逻辑。

### 5.2 Matrix 合同

`capability_matrix.v1` 顶层至少包含：

```text
schema_version
generated_at
evidence_level
provider_call=false
production_write_allowed=false
platforms[7]
access_channels[6]
cells[42]
summary
```

每个 `CapabilityMatrixCell` 至少包含：

```text
platform
access_channel
summary_status
status_counts
implementation_ids
assertion_ids
resource_types
operations
constraint_codes
evidence_count
last_verified_at
```

没有 Implementation 或 Assertion 的格仍必须返回，并具有：

```text
summary_status=unknown
status_counts={unknown: 1}
implementation_ids=[]
assertion_ids=[]
evidence_count=0
```

### 5.3 状态聚合

单格状态使用确定性优先级：

```text
verified > partial > candidate > blocked > unsupported > deprecated > unknown
```

规则：

1. 无 Assertion 时为 `unknown`。
2. 有 Assertion 时按上述优先级选择 `summary_status`。
3. `status_counts` 始终保留所有底层状态数量，避免聚合状态掩盖混合事实。
4. 聚合状态只服务 UI，不写回 Catalog，也不能作为自动执行依据。

### 5.4 只读 API

新增：

- `GET /api/capabilities/matrix`
- `GET /api/capabilities/assertions`
- `GET /api/capabilities/implementations`
- `GET /api/capabilities/implementations/{implementation_id}`

过滤参数使用现有枚举：platform、access_channel、resource_type、operation、support_status。

错误语义：

- 无效枚举输入返回 `422`。
- 不存在的 Implementation 返回 `404 capability_implementation_not_found`。
- Catalog 文件、编码或 Pydantic 校验异常返回现有 `capability_catalog_load_failed`，不回落到前端静态数据。
- 合法过滤无结果返回空列表，不伪造 `unknown` Assertion；只有 Matrix Cross Product 负责生成空格。

### 5.5 数据流

```text
capability_catalog_overseas_v2.json
-> CapabilityCatalog.model_validate_json
-> cached deep-copy loader
-> Capability Matrix read model
-> authenticated read-only API
-> Web capability client
-> Scenario / Matrix / List / Detail UI
```

## 6. 前端设计

### 6.1 类型与 API Client

新增独立 Capability 类型与 API Client，不把新合同继续塞入已经超过千行的 `social-provider.ts` 和 `lib/api/social-provider.ts`。

建议边界：

- `types/capability.ts`
- `lib/api/capabilities.ts`
- `lib/capability-matrix.ts`
- `lib/api-market-presentation.ts`

### 6.2 三种视图

#### 场景视图

按业务目标组织能力：市场监测、关键词发现、内容详情、评论与对话、创作者、增量监测、批量解析和导出。每个场景显示覆盖平台、候选能力、已知限制和证据等级，不展示未经核验的“可运行”承诺。

#### 矩阵视图

桌面端显示 7 个逻辑平台 × 6 个访问通道。格尺寸固定，状态通过颜色、文本和数量共同表达，不能只依赖颜色。

移动端不压缩成不可读的 42 格横向表；改为“平台选择器 + 6 个通道列表”，使用同一 Matrix 数据和同一详情抽屉。

#### 列表视图

按 Implementation 展示 Provider、平台、通道、交付形态、状态摘要、资源、操作、成本提示、证据和最近核验时间。筛选状态写入 URL Query，支持刷新和分享。

### 6.3 详情抽屉

矩阵格和列表项共用一个详情抽屉，按顺序展示：

1. 聚合状态与边界说明。
2. Resource 与 Operation。
3. Implementation。
4. Constraint 与禁止动作。
5. 八维评分。
6. Evidence 与核验时间。
7. 现有 Fixture Review 入口。

详情抽屉不嵌套新的卡片墙，不展示 Credential 值，不提供 Live 按钮。

### 6.4 实现比较

只允许比较同一平台、相同资源或操作范围内的 2–3 个 Implementation。比较字段固定为：覆盖、Freshness、History、Reliability、Schema Stability、Cost Efficiency、Maintainability、Evidence Confidence、限制和 Evidence。

当前多数格只有一个 Implementation 时，比较入口禁用并解释原因，不能填充虚构替代项。

## 7. 导航与项目上下文

### 7.1 单一导航配置

新增一份共享 Navigation Config，同时驱动：

- Desktop Sidebar
- Mobile Navigation Drawer
- 当前路由高亮
- 次级入口分组

Sidebar 和 Mobile Drawer 不得分别维护路由数组。

### 7.2 移动导航

Top Bar 在小视口提供菜单按钮。Drawer 包含完整六入口和当前入口的次级页面，支持键盘关闭、Escape、焦点返回和可访问名称。

### 7.3 Project Selector

Project Selector 使用既有 Project API，不新增数据库字段。选择值需要：

- 校验仍存在且状态为 active。
- 不存在或被归档时回退到“全部项目”。
- 本地持久化只能保存 Project ID，不保存用户、凭据或业务数据。
- 所有页面明确显示项目过滤是否已生效。

## 8. 控制面与文档同步

本 Goal 的第一批实施必须先恢复可相信的状态入口，但不删除历史记录。

### 8.1 当前正式资产

- V2 PRD：继续作为产品目标单一事实源。
- V2 总体设计：继续作为跨 Goal 系统设计。
- 本文：仅作为 GOAL-V2-02 设计规格。
- 后续 Implementation Plan：作为本 Goal 详细执行与勾选源。

### 8.2 需要同步的状态文件

- GOAL-V2-01 计划：状态改为 complete，并让任务勾选与执行证据一致。
- V2 PRD：GOAL-V2-01 改为 complete，GOAL-V2-02 改为 approved/ready，后续 Goal 保持 queued。
- `TODO.md`：切换为当前 GOAL-V2-02 的简短执行索引，只链接详细计划，不复制全部步骤。
- `.codex/context-pack.md`：Current Focus 改为 V2 GOAL-V2-02 和固定证据边界。
- `.codex/ralph-loop.local.md`：旧 Loop 37 不再标 active；在用户单独启动执行循环前保持 inactive。
- `.kiro/plan/task_plan.md`：增加 V2 当前 Overlay 和正式计划链接，历史 Phase 记录保留。
- `.kiro/plan/findings.md`、`.kiro/plan/progress.md`：只追加本次稳定结论和后续执行证据。
- 技术架构与 API 合同：同步 Capability Matrix 模块和只读 API。

### 8.3 历史资产

旧 PRD2 workflow、7 月 8–10 日微型 Social Provider 计划和旧 Loop 证据不删除。只在入口处标记 historical/superseded，避免继续被解释为当前执行源。

## 9. 实施批次

### Batch 0：基线恢复与控制面同步

- 修复 readonly Fixture 与 DTO 数组的 TypeScript 合同不兼容。
- 重新运行 TypeScript、Web lint、Web unit、Web build。
- 同步 GOAL-V2-01、V2 Goal 状态、`TODO.md`、Codex/Kiro 当前入口。
- 冻结本 Goal 精确文件清单，保留既有未跟踪 drafts、`output/` 和 `ref/`。

### Batch 1：Matrix 合同与纯读模型

- 先写 42 格、unknown 空格、混合状态、过滤和缓存隔离测试。
- 实现 Matrix Schema 与 Service。
- 验证不修改 Canonical Catalog 对象。

### Batch 2：只读 Capability API

- 增加 Matrix、Assertion、Implementation List/Detail Route。
- 增加鉴权、过滤、422/404/Loader 异常集成测试。
- 保持 `/api/automation/social-provider-*` 回归通过。

### Batch 3：前端单一能力事实源

- 增加 Capability 类型与 API Client。
- 把 API Market 的能力事实切换到后端。
- 将静态 Catalog 缩减为展示增强，并增加双向 Parity Test。
- API 不可用时显式显示不可用状态，不静默回退到旧静态事实。

### Batch 4：能力市场产品面

- 交付场景、矩阵、列表三视图。
- 交付格详情抽屉和有界实现比较。
- 复用现有视觉语言，完成桌面与移动响应式布局。

### Batch 5：六入口与 Project Selector

- 建立共享 Navigation Config。
- 重构 Desktop Sidebar。
- 增加 Mobile Drawer。
- 增加全局 Project Selector 和过滤生效提示。
- 保留全部旧路由可访问。

### Batch 6：完整本地验收与文档收口

- 完成 API unit/integration、ruff、mypy、Alembic 单 head 检查。
- 完成 Web typecheck、lint、unit、build。
- 完成 Mock Playwright desktop/mobile 能力市场与导航用例。
- 完成 `git diff --check`、边界标志扫描和状态文档一致性扫描。
- 记录本地证据，不升级为远端 CI、生产或 Live Provider 证明。

## 10. 测试策略

### 10.1 后端单元测试

- 7×6 笛卡尔积始终产生 42 格。
- 当前只有 7 个官方 API 格聚合为 `candidate`，其余 35 格为 `unknown`。
- mixed status 按固定优先级聚合，并完整保留 `status_counts`。
- platform/channel/resource/operation/status 过滤确定且不修改缓存对象。
- Evidence 引用、Implementation 引用和 last_verified_at 投影正确。
- Catalog 异常 fail-fast，不使用静态兜底。

### 10.2 API 集成测试

- 未登录访问遵循现有鉴权合同。
- 合法 Matrix 请求返回 42 格和 false 边界标志。
- 无效枚举返回 422。
- 未知 Implementation 返回指定 404。
- 现有 Social Provider 兼容接口响应保持不变。

### 10.3 前端单元测试

- Matrix DTO 映射和状态文案。
- 18 个现有展示增强与后端 Endpoint 的 Parity。
- Filter URL 序列化与反序列化。
- Candidate 不出现 Live 操作。
- Project Selector 的 active、archived、missing 回退。
- Desktop/Mobile 导航由同一 Config 生成。

### 10.4 E2E

- `/api-market?view=scenarios`、`matrix`、`list` 可切换并保持 Query。
- Matrix 格打开详情抽屉，显示限制和 Evidence。
- Desktop Sidebar 只显示六个一级入口。
- 375px Mobile Drawer 可以访问六入口和次级入口，无不可恢复横向溢出。
- Project Selector 明确展示过滤状态。
- 旧 `/api-market/[endpointId]` 和其他旧页面仍可访问。

### 10.5 验证命令族

```text
cd apps/api && uv run ruff check .
cd apps/api && uv run mypy src tests
cd apps/api && uv run pytest
cd apps/api && uv run alembic heads
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API corepack pnpm --dir apps/web test:e2e
git diff --check
```

这些命令在实施计划中拆成独立步骤执行，不能把历史记录替代为当前 HEAD 的新鲜结果。

## 11. 错误处理与可观测性

- Catalog 无法加载时 API 明确返回专用错误，不返回过期或前端硬编码能力。
- UI 区分“请求未完成”“Catalog 不可用”“过滤结果为空”“Matrix unknown”。
- Matrix Summary 和 Detail 显示生成时间、Evidence Level 和边界标志。
- 不把用户提交的 `credentials_ready=true` 表述为已读取或已验证凭据。
- 所有 Candidate 和 Fixture 操作继续显示 `provider_call=false`。
- 本 Goal 不新增长期日志或审计表；HTTP 和 Service 错误沿用现有结构化日志。

## 12. 安全与合规

- API 响应只返回 Credential 名称，不返回值、引用内容或环境变量状态。
- 前端示例不得包含真实 token、Cookie、账号会话或个人数据。
- Relationship Graph、私信、登录态、验证码规避、反检测继续保持 blocked/unsupported。
- Evidence URL 只能作为只读来源链接，不自动抓取或调用。
- Matrix 状态不能绕过 Policy、Auth、Purpose、Region、Data 门禁。

## 13. Exit Gate

GOAL-V2-02 只有在以下条件全部满足时才能完成：

1. Matrix API 稳定返回 7 个平台、6 个访问通道和 42 个显式格。
2. 当前 7 个官方 API 格显示 `candidate`，其余格显示 `unknown`；底层 Assertion 未被修改。
3. API Market 的能力事实全部来自后端 Canonical Catalog。
4. 前端展示增强与后端 Endpoint Parity Test 通过。
5. 场景、矩阵、列表三视图和详情抽屉可用。
6. 一级导航只有六项，Desktop 与 Mobile 使用同一配置。
7. Project Selector 不把全局数据误表述为项目过滤结果。
8. 旧页面和 `/api/automation/social-provider-*` 兼容行为保持可用。
9. TypeScript、API、Web、Build 和 Mock E2E 本地门禁全部通过。
10. `provider_call=false`、`credential_read_attempted=false`、`live_client_created=false`、`production_write_allowed=false`。
11. 无数据库迁移、无外部调用、无生产变更。
12. GOAL-V2-01、V2 PRD、`TODO.md`、Codex/Kiro 和架构/API 文档的当前状态一致。

## 14. 回滚

本 Goal 不含数据库迁移和外部副作用，回滚只涉及代码与文档：

1. 按原子提交逆序 revert Capability UI、Navigation、Web Client、API Route、Matrix Service、Schema 和状态文档。
2. `/api/automation/social-provider-*` 从始至终保持兼容，不需要数据回填。
3. 旧 URL 保持存在，因此导航回滚不需要 URL 或数据迁移。
4. 如果前端 API 切换需要回滚，只能整体回滚到上一个版本；运行时不得同时维护隐式静态兜底。

## 15. 后续 Goal 依赖

- GOAL-V2-03 消费 Matrix API、Capability Assertion 和 Project Selector，新增 MonitoringScope 与 WorkflowPlan Preview。
- GOAL-V2-04 在稳定的 Capability 合同上新增 Candidate、Verification、Publication 和 Drift Probe；届时再设计能力事实持久化。
- GOAL-V2-05 消费经过核验的能力、Credential、Budget 和 Rate Limit Gate，准备 YouTube/Reddit 独立授权 Small Run。
- 本 Goal 的完成不自动激活任何后续 Goal。
