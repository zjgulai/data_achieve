---
title: Data Intelligence Hub 开发计划草案
doc_type: analysis
module: engineering
topic: data-intelligence-hub-development-plan
status: draft
created: 2026-06-11
updated: 2026-06-11
owner: self
source: human+ai
---

# Data Intelligence Hub 开发计划草案

## 1. PRD 本质判断

Data Intelligence Hub 的核心不是“多源爬虫”，也不是“数据看板”，而是一个可追溯情报系统。

产品的不变量是：

```text
RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert
```

开发顺序必须服务这个不变量。只要证据链没有闭合，Dashboard、日报、预警都只是展示壳；只要 Signal 不是确定性规则，LLM 摘要就会污染事实层。

## 2. 关键产品约束

| 约束 | 落地判断 |
|---|---|
| MVP 做闭环平台 | 先实现一条端到端情报链路，再补页面完整度 |
| 多域浅覆盖 | 四类 Collector 都要有，但每类只做最小可验证能力 |
| 全链路可追溯 | 数据库外键、API 响应、前端审计抽屉都围绕 evidence 设计 |
| AI 不判断事实 | 评分、状态、触发规则全部由代码计算 |
| 小规模部署 | 单机 Docker Compose + PostgreSQL + APScheduler 足够 |
| 前后端并行 | FastAPI OpenAPI 作为契约，前端必须有 mock API 模式 |

## 3. 需要修正的 PRD 内部不一致

| 问题 | 判断 | 执行方案 |
|---|---|---|
| PRD 写 React 18+，项目规范要求 React 19 + Next.js 15 | 项目规范优先，且不破坏 PRD 目标 | 前端锁定 Next.js 15 + React 19 + TypeScript strict |
| PRD 后端结构出现 `requirements.txt`，项目规范要求 uv | 项目规范优先 | 使用 `pyproject.toml` + uv；如部署需要，再导出 requirements |
| PRD 默认目录是 `apps/api` / `apps/web`，项目标准目录未列 `apps/` | `apps/` 是全栈 monorepo 的必要边界 | 保留 `apps/`，不使用根级 `src/`；各 app 内部使用自己的 `src/` |
| GenericWebCollector 提到截图，但实现方式写 httpx + BeautifulSoup | httpx 不能生成真实渲染截图 | MVP 先保存 HTML 快照；截图能力放到 Playwright/S3 子任务，配置开启 |
| MVP 信号列了 price_drop，但 MVP Collector 不含正式电商采集 | 数据源不足时不能伪造信号 | `price_drop` 仅在 ManualJson 提供 price metrics 时启用；默认先做 star_growth、page_changed、data_quality_anomaly |
| APScheduler 在多进程 API 中会重复调度 | 单机可行，多 worker 有风险 | MVP 只运行一个 scheduler owner；部署文档禁止多 API worker 同时启调度 |

## 4. 当前目录初始化方案

当前项目已初始化为以下结构：

```text
data_scrapy/
├─ .gitignore
├─ apps/
│  ├─ api/
│  └─ web/
├─ scripts/
├─ sql/
├─ configs/
├─ docs/
│  ├─ product/
│  │  └─ product-prd-data-intelligence-hub-stable.md
│  ├─ architecture/
│  ├─ api/
│  ├─ workflows/
│  └─ knowledge/
├─ tests/
├─ assets/
│  ├─ images/
│  └─ diagrams/
├─ drafts/
│  ├─ docs/
│  ├─ analysis/
│  │  └─ analysis-development-plan-data-intelligence-hub-draft-20260611.md
│  ├─ scripts/
│  └─ ideas/
├─ tmp/
│  ├─ outputs/
│  ├─ screenshots/
│  ├─ debug/
│  └─ scratch/
└─ archive/
   ├─ docs/
   ├─ experiments/
   ├─ scripts/
   └─ snapshots/
```

目录职责：

| 目录 | 用途 |
|---|---|
| `apps/api/` | FastAPI 后端应用 |
| `apps/web/` | Next.js 前端应用 |
| `docs/product/` | 已冻结 PRD 和正式产品文档 |
| `docs/architecture/` | 系统架构、数据流、模块边界 |
| `docs/api/` | OpenAPI 契约、接口说明 |
| `docs/workflows/` | 开发、部署、采集运维流程 |
| `drafts/analysis/` | 待确认的分析和计划 |
| `tmp/` | 可丢弃的运行输出、截图、调试材料 |
| `archive/` | 失活但保留参考价值的历史资产 |

## 5. 技术栈锁定

### 5.1 后端

| 类别 | 决策 |
|---|---|
| Python | 3.12+ |
| 包管理 | uv |
| Web 框架 | FastAPI |
| 数据校验 | Pydantic V2 |
| ORM | SQLAlchemy 2.0 async |
| 数据库驱动 | asyncpg |
| 迁移 | Alembic |
| 数据库 | PostgreSQL 15+ |
| 调度 | APScheduler |
| HTTP Client | httpx |
| HTML 解析 | BeautifulSoup + readability-lxml |
| 截图 | Playwright，作为可选采集增强 |
| 测试 | pytest + pytest-asyncio + httpx |
| 质量 | ruff + mypy strict |

### 5.2 前端

| 类别 | 决策 |
|---|---|
| 框架 | Next.js 15 App Router |
| React | React 19 |
| 语言 | TypeScript strict |
| 样式 | Tailwind CSS |
| 组件 | shadcn/ui |
| 服务端状态 | TanStack Query |
| 表格 | TanStack Table |
| 表单 | React Hook Form + Zod |
| 图表 | Recharts |
| API 类型 | OpenAPI 生成 TypeScript client |
| 测试 | Vitest + Playwright |

### 5.3 部署

| 类别 | 决策 |
|---|---|
| 本地开发 | Docker Compose + 本机前后端 dev server |
| MVP 部署 | 单机 Docker Compose |
| 数据库 | PostgreSQL 容器或云数据库 |
| 对象存储 | S3-compatible，可选 |
| 邮件 | SMTP |
| LLM | OpenAI / Anthropic Adapter |

## 6. 后端目标结构

```text
apps/api/
├─ pyproject.toml
├─ alembic.ini
├─ alembic/
├─ src/
│  └─ data_intelligence_hub/
│     ├─ main.py
│     ├─ core/
│     ├─ api/
│     │  ├─ deps.py
│     │  └─ routes/
│     ├─ models/
│     ├─ schemas/
│     ├─ repositories/
│     ├─ services/
│     ├─ collectors/
│     ├─ scheduler/
│     └─ workers/
└─ tests/
   ├─ unit/
   └─ integration/
```

模块边界：

| 层 | 职责 | 禁止事项 |
|---|---|---|
| `api/routes` | HTTP 参数、状态码、依赖注入 | 不写业务规则 |
| `services` | 业务流程和状态流转 | 不直接拼 SQL |
| `repositories` | 查询与持久化 | 不调用 LLM、HTTP 外部服务 |
| `collectors` | 采集与标准化 | 不生成 Intelligence |
| `scheduler` | 任务注册和触发 | 不承载业务判断 |
| `models` | 数据结构和约束 | 不写流程逻辑 |

## 7. 前端目标结构

```text
apps/web/
├─ package.json
├─ next.config.ts
├─ tsconfig.json
├─ src/
│  ├─ app/
│  │  ├─ login/
│  │  ├─ dashboard/
│  │  ├─ domain/
│  │  ├─ projects/
│  │  ├─ sources/
│  │  ├─ tasks/
│  │  ├─ intelligence/
│  │  ├─ entities/
│  │  ├─ reports/
│  │  ├─ alerts/
│  │  └─ notifications/
│  ├─ components/
│  │  ├─ layout/
│  │  ├─ dashboard/
│  │  ├─ intelligence/
│  │  ├─ collectors/
│  │  └─ common/
│  ├─ lib/
│  │  ├─ api/
│  │  ├─ auth/
│  │  ├─ formatters/
│  │  └─ validators/
│  ├─ hooks/
│  └─ types/
└─ tests/
```

前端开发原则：

| 原则 | 执行 |
|---|---|
| 工作台优先 | 首屏直接进入 Dashboard，不做营销页 |
| 证据可见 | 情报详情必须显示 evidence 数量和审计入口 |
| 状态明确 | loading / empty / error / success 四态完整 |
| 页面不抢跑 | 没有 API 契约的页面先用 mock data |
| 操作可恢复 | 状态更新、启停任务、发送报告要有明确反馈 |

## 8. 数据库落地顺序

### 8.1 第一组：身份与工作区

- `users`
- `workspaces`
- `workspace_members`：PRD 未列，但长期权限边界需要；MVP 可只有 owner 记录

验收：注册用户后自动创建默认 workspace。

### 8.2 第二组：项目、数据源、任务

- `projects`
- `collectors`
- `sources`
- `collection_tasks`
- `task_runs`

验收：创建 Source 后可测试采集，启用后自动创建 CollectionTask。

### 8.3 第三组：采集产物与实体

- `raw_records`
- `entities`
- `entity_snapshots`

验收：一次 TaskRun 至少形成 RawRecord；可被标准化为 EntitySnapshot。

### 8.4 第四组：信号、情报、证据

- `signals`
- `intelligence_items`
- `evidences`
- `intelligence_feedback`：PRD 有 feedback API，但缺表；需要补齐

验收：Signal 生成后可创建 Intelligence，且每条 Intelligence 至少绑定一条 Evidence。

### 8.5 第五组：交付

- `reports`
- `alert_rules`
- `alert_events`
- `notifications`

验收：日报可生成、站内通知可读、预警命中可落库。

## 9. 开发节奏

总周期沿用 PRD 的 10 个 Sprint，但把 Sprint 0 扩为工程治理和契约固化阶段。

| Sprint | 周期 | 目标 | 交付 |
|---|---:|---|---|
| 0 | 2-3 天 | 仓库初始化与工程基线 | 目录、工具链、健康检查、数据库连接、前端空壳 |
| 1 | 1 周 | Auth + Workspace + Project | 注册登录、默认 workspace、项目 CRUD |
| 2 | 1 周 | Source + Task | Collector 元信息、Source CRUD、TaskRun 手动执行 |
| 3 | 1 周 | Collector + RawRecord | 四类 Collector 最小实现、原始记录落库 |
| 4 | 1 周 | Entity + Snapshot | 标准化、实体去重、快照历史 |
| 5 | 1 周 | Signal Engine | star_growth、page_changed、data_quality_anomaly |
| 6 | 1 周 | Intelligence + Evidence | 情报生成、评分、证据链、LLM mock/adapter |
| 7 | 1 周 | Intelligence UI + Audit Drawer | 情报列表、详情、证据时间线、审计抽屉 |
| 8 | 1 周 | Dashboard + Domain Views | 全局仪表盘、四域视图、任务健康度 |
| 9 | 1 周 | Report + Alert + Delivery | 日报、预警、通知、邮件 |
| 10 | 1 周 | 稳定化与部署 | 测试补齐、seed data、docker-compose、性能验收 |

## 10. Sprint 0 详细计划

### 10.1 目录与治理

任务：

1. 保留当前目录骨架。
2. 将 PRD 固定在 `docs/product/product-prd-data-intelligence-hub-stable.md`。
3. 新建 `README.md`，只写项目定位、启动方式、文档入口。
4. 新建 `.env.example`，列出后端、前端、数据库、SMTP、LLM、S3 配置。
5. 新建 `docs/workflows/workflow-development-setup-stable.md`，记录本地开发流程。

验收：

- 根目录没有业务草稿和临时文件。
- 新 Markdown 文档都有元信息。
- `.DS_Store` 不进入版本控制。

### 10.2 后端初始化

任务：

1. 在 `apps/api/` 初始化 uv 项目。
2. 配置 FastAPI、Pydantic V2、SQLAlchemy async、Alembic。
3. 建立 `core/config.py`，集中读取环境变量。
4. 建立 `core/database.py`，提供 async session。
5. 建立 `/health`。
6. 配置 ruff、mypy strict、pytest。
7. 建立第一条 migration：基础扩展、时间戳约定、UUID 策略。

验收：

- `uv run pytest` 通过。
- `uv run ruff check .` 通过。
- `uv run mypy src` 通过。
- `/health` 返回数据库连接状态。

### 10.3 前端初始化

任务：

1. 在 `apps/web/` 初始化 Next.js 15 + React 19 + TypeScript strict。
2. 配置 Tailwind CSS 和 shadcn/ui。
3. 建立 App Shell：Sidebar、TopBar、内容区。
4. 建立 `/login` 和 `/dashboard` 空状态。
5. 建立 API client 包装层，支持 mock mode。
6. 配置 ESLint、Prettier、Vitest。

验收：

- `pnpm lint` 通过。
- `pnpm test` 通过。
- `/login` 和 `/dashboard` 可渲染。
- mock mode 下不依赖后端可打开页面。

### 10.4 本地基础设施

任务：

1. 创建 `docker-compose.yml`，包含 PostgreSQL。
2. 创建后端 `.env.example`。
3. 创建前端 `.env.example`。
4. 创建 `scripts/dev-start.sh`，统一启动数据库、后端、前端。
5. 创建 `scripts/dev-reset-db.sh`，只用于开发环境重建数据库。

验收：

- 本地一条命令可启动 PostgreSQL。
- Alembic migration 可升级和回滚。
- 前后端启动端口固定且写入 README。

## 11. Sprint 1-10 详细任务

### Sprint 1：Auth + Workspace + Project

后端：

- 建模 `users`、`workspaces`、`workspace_members`、`projects`。
- 实现邮箱注册、登录、登出、`/api/auth/me`。
- 使用 HttpOnly Cookie 存 JWT。
- 注册后创建默认 workspace。
- Project 支持创建、列表、编辑、归档。

前端：

- 登录/注册页。
- Auth guard。
- Project 列表、创建弹窗、domain 筛选。
- Dashboard 空状态引导创建 Project。

测试：

- 密码哈希不可逆。
- 未登录不能访问项目 API。
- 用户只能看到自己 workspace 的项目。

### Sprint 2：Source + Task

后端：

- 建模 `collectors`、`sources`、`collection_tasks`、`task_runs`。
- 预置四类 Collector 元信息与 config schema。
- 实现 Source CRUD、test、enable、disable。
- 启用 Source 时创建或恢复 CollectionTask。
- 手动 `run now` 创建 TaskRun。

前端：

- Source 列表和动态表单。
- Collector 类型选择。
- Source 测试结果面板。
- Task 列表、任务详情、运行历史。

测试：

- 非法 config 被拒绝。
- enable/disable 与 task 状态一致。
- 手动运行失败时 TaskRun 记录结构化错误。

### Sprint 3：Collector + RawRecord

后端：

- 实现 `BaseCollector`。
- 实现 `GitHubRepoCollector`。
- 实现 `GitHubTopicCollector`。
- 实现 `GenericWebCollector` 的 HTML 快照版本。
- 实现 `ManualJsonCollector`。
- 建模并写入 `raw_records`。
- 增加 content hash 去重。

前端：

- RawRecord 列表和详情。
- TaskRun 日志展示。
- Manual JSON 输入和校验反馈。

测试：

- 每个 Collector 有 validate/test/collect/normalize 单元测试。
- HTTP timeout 和 User-Agent 必须存在。
- Collector 异常不会跳过 TaskRun 落库。

### Sprint 4：Entity + Snapshot

后端：

- 建模 `entities`、`entity_snapshots`。
- 实现 entity upsert。
- 实现 snapshot 创建。
- 实现实体详情、快照历史 API。
- 定义各 entity_type 的 metrics 规范。

前端：

- Entity 列表。
- Entity 详情。
- Snapshot 时间线。
- metrics 趋势图。

测试：

- 同一 external_id + entity_type 不重复创建 Entity。
- 每次成功采集都创建新 Snapshot。
- latest_snapshot_id 正确更新。

### Sprint 5：Signal Engine

后端：

- 建模 `signals`。
- 实现 `star_growth`。
- 实现 `page_changed`。
- 实现 `data_quality_anomaly`。
- 在 TaskRun 成功后触发 signal detection。
- 提供 signals 查询 API。

前端：

- Signal 列表。
- Entity 详情展示关联 signals。
- TaskHealthPanel 显示数据质量异常。

测试：

- 阈值边界测试。
- 无 previous snapshot 时不生成变化信号。
- Signal 必须绑定 previous/current snapshot。

### Sprint 6：Intelligence + Evidence

后端：

- 建模 `intelligence_items`、`evidences`、`intelligence_feedback`。
- 实现评分公式。
- 实现 evidence 构建。
- 实现 rule-based intelligence 聚合。
- 实现 LLM adapter 接口。
- 实现 MockLLMAdapter 作为默认开发适配器。
- 实现 OpenAI/Anthropic adapter 骨架。

前端：

- Intelligence 列表。
- Intelligence 详情。
- Evidence Timeline。
- 状态流转。
- feedback 按钮。

测试：

- 每条 Intelligence 至少一条 Evidence。
- final_score 不由 LLM 修改。
- LLM 输出必须经过 JSON schema 校验。

### Sprint 7：Audit Drawer

后端：

- Intelligence detail API 返回可审计 evidence。
- Evidence 包含 highlighted_text、raw_record、snapshot、signal 引用。
- Snapshot compare API 返回 old/new metrics。

前端：

- 审计抽屉。
- 摘要关键结论点击高亮。
- Evidence 原文片段。
- Old vs New Snapshot 对比。
- 截图 URL 存在时展示截图。

测试：

- 没有证据的摘要结论不允许进入可点击状态。
- Evidence 丢失时 UI 显示明确错误。
- 审计抽屉在移动端不遮挡主要操作。

### Sprint 8：Dashboard + Domain Views

后端：

- Dashboard overview API。
- Domain breakdown。
- Top intelligence。
- Task health。
- Data quality。

前端：

- 全局 Dashboard。
- `/domain/osint`。
- `/domain/ecommerce`。
- `/domain/social`。
- `/domain/competitor`。
- 统一筛选器和情报卡片。

测试：

- 空数据状态。
- 大量情报列表分页。
- Dashboard API P95 目标预留索引。

### Sprint 9：Report + Alert + Notification

后端：

- 建模 `reports`、`alert_rules`、`alert_events`、`notifications`。
- 实现日报生成。
- 实现 AlertRule matcher。
- 实现站内通知。
- 实现 SMTP 邮件发送。
- APScheduler 定时生成日报。

前端：

- 报告中心。
- 报告详情 Markdown 渲染。
- 预警规则配置。
- 预警事件列表。
- 通知中心。

测试：

- Alert condition 运算符测试。
- 日报只引用真实数据。
- 邮件发送失败不影响 Report 落库。

### Sprint 10：稳定化与交付

任务：

- 补齐核心 service 单元测试。
- 补齐 API integration tests。
- 补齐 Playwright happy path。
- 创建 seed data。
- 创建 Demo workspace。
- 完成 docker-compose。
- 完成部署文档。
- 做 Dashboard 查询性能检查。

验收：

- 后端核心测试通过。
- 前端 lint/test 通过。
- E2E happy path 通过。
- Alembic upgrade/downgrade 可重复执行。
- Dashboard 首屏目标小于 3 秒。

## 12. API 契约推进顺序

优先级：

1. Auth
2. Projects
3. Collectors
4. Sources
5. Tasks / TaskRuns
6. RawRecords
7. Entities / Snapshots
8. Signals
9. Intelligence / Evidences
10. Dashboard
11. Reports
12. Alerts
13. Notifications

契约规则：

- 后端 route 合并前必须更新 OpenAPI。
- 前端只依赖生成的 API 类型，不手写重复 DTO。
- 对列表接口统一分页、排序、筛选格式。
- 错误响应统一：

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## 13. 核心测试矩阵

| 模块 | 必测路径 |
|---|---|
| Auth | 注册、登录、过期 token、workspace 隔离 |
| Collector | config 校验、网络失败、空结果、normalize |
| TaskRun | success、partial_success、failed、日志落库 |
| Entity | upsert、snapshot、latest_snapshot 更新 |
| Signal | 阈值边界、缺少前置快照、重复检测 |
| Intelligence | 评分、证据、LLM JSON 校验、状态机 |
| Evidence | RawRecord/Snapshot/Signal 反向追溯 |
| Report | 时间窗口、空日报、发送失败 |
| Alert | condition 匹配、channel 分发、状态流转 |
| Dashboard | 聚合准确、分页、性能 |

## 14. 端到端验收路径

第一条必须跑通的 happy path：

```text
注册用户
-> 自动创建 Workspace
-> 创建 Project(osint)
-> 创建 GitHub Repo Source
-> 测试采集成功
-> 启用 Source 并生成 Task
-> 手动 Run Task
-> 保存 RawRecord
-> 生成 Entity + Snapshot
-> 第二次 Run Task
-> 触发 star_growth 或无信号
-> 人工 seed 一个变化快照
-> 触发 Signal
-> 生成 Intelligence + Evidence
-> 前端打开 Intelligence Detail
-> 打开 Audit Drawer
-> 生成日报
-> 创建预警规则
-> 触发站内通知
```

## 15. 风险与控制

| 风险 | 控制 |
|---|---|
| APScheduler 多进程重复执行 | MVP 单 worker；后续拆 scheduler service |
| GitHub API rate limit | 支持 token；做限流和错误记录 |
| Generic web 合规风险 | 遵守 robots.txt；不绕过登录墙/付费墙 |
| LLM 幻觉 | Prompt 限制 + JSON schema + evidence 强绑定 |
| Evidence 丢失 | 数据库约束 + 生成前校验 |
| Dashboard 慢查询 | 按 workspace/domain/project/time 建索引 |
| 前端页面先于 API 发散 | mock data 必须匹配 OpenAPI 类型 |
| 目录熵增 | 草稿、临时、归档严格分区 |

## 16. 反面论证与取舍

### 16.1 为什么不直接开始写 Collector

反面论点：Collector 是产品最显性的能力，先写能最快看到数据。

结论：不能先写。没有 RawRecord、EntitySnapshot、Signal、Evidence 的结构约束，Collector 很容易变成孤立脚本。先建工程基线和数据链路，再写 Collector。

### 16.2 为什么使用 `apps/` 而不是根级 `src/`

反面论点：项目规范默认顶层有 `src/`，使用它更统一。

结论：本项目是前后端双应用，`apps/api` 和 `apps/web` 能明确表达部署边界。根级 `src/` 会把 Python 后端和 Next.js 前端混在一个抽象目录下，长期维护成本更高。

### 16.3 为什么不把开发计划直接放入正式 `docs/workflows/`

反面论点：开发计划是工程资产，应进入正式文档。

结论：当前计划基于单份 PRD 推导，尚未经过用户确认，状态是 draft。确认后再迁移为 `docs/workflows/workflow-development-plan-stable.md`。

## 17. 下一步执行清单

按顺序执行：

1. 确认本计划。
2. 将本草案晋升为正式工作流文档，或按反馈修改。
3. 新建 `README.md` 和 `.env.example`。
4. 初始化 `apps/api` uv + FastAPI。
5. 初始化 `apps/web` Next.js 15。
6. 创建 PostgreSQL docker-compose。
7. 创建第一组数据库 migration。
8. 跑通 `/health`。
9. 跑通前端 `/login` 空页面。
10. 进入 Sprint 1。

## 18. Sprint 0 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| 根目录治理 | complete | PRD 迁入 `docs/product/`，开发计划保留在 `drafts/analysis/` |
| 入口文档 | complete | 已创建 `README.md`、`.env.example`、开发工作流文档 |
| 后端骨架 | complete | FastAPI、配置、数据库会话、健康检查、Alembic baseline 已建立 |
| 后端校验 | complete | `ruff`、`mypy`、`pytest` 通过 |
| 前端骨架 | complete | Next.js 15、React 19、Tailwind、App Shell、登录页、Dashboard、导航空状态页已建立 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| 本地数据库验证 | blocked | Docker daemon 未运行，无法拉起 PostgreSQL 容器和执行真实 Alembic 连接验证 |
| 前端运行验证 | complete | `http://localhost:3000/login`、`/dashboard`、`/domain/osint` 返回 200 |

下一步进入 Sprint 1 前，先启动 Docker Desktop 或其他 Docker daemon，然后执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

## 19. Sprint 1 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| 身份模型 | complete | 已建立 `users`、`workspaces`、`workspace_members`、`projects` ORM 模型 |
| 数据库迁移 | complete | 已新增 `202606110002_identity_and_projects.py` |
| Auth API | complete | 已实现 register、login、logout、me；JWT 写入 HttpOnly cookie |
| Workspace 初始化 | complete | 注册用户时自动创建默认 workspace 和 owner membership |
| Project API | complete | 已实现列表、创建、详情、更新、软归档 |
| 权限边界 | complete | Project API 通过当前用户默认 workspace 限定查询范围 |
| 后端测试 | complete | SQLite 内存库验证 Auth + Project 主路径；`pytest` 5 项通过 |
| 前端 Auth | complete | 登录/注册表单已接入 mock/real API 切换 |
| 前端 Project | complete | 已新增 `/projects` 页面、业务域筛选、搜索、创建表单 |
| OpenAPI 验证 | complete | 临时 `8010` 服务确认 Sprint 1 路由已暴露 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键修正：

- 显式 pin `bcrypt < 5`，避免 `passlib` 与 `bcrypt 5` 的运行时不兼容。
- 前端 API 层显式映射后端 snake_case 响应到前端 camelCase 模型。
- Project API 当前以默认 workspace 为边界，企业多 workspace 切换后置。

进入 Sprint 2 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

## 20. Sprint 2 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Collector 元信息 | complete | 已建立 `collectors` 表、迁移 seed、应用层 catalog |
| Source 模型 | complete | 已建立 `sources` 表和 ORM |
| Task 模型 | complete | 已建立 `collection_tasks`、`task_runs` 表和 ORM |
| Source API | complete | 已实现列表、创建、详情、更新、配置测试、启用、停用 |
| Task API | complete | 已实现任务列表、详情、run now、pause、resume、运行记录列表 |
| 配置校验 | complete | 四类 Collector 均有确定性 config validation |
| TaskRun 记录 | complete | 手动 run 会生成结构化 failed 记录，说明 Collector 执行在 Sprint 3 |
| APScheduler 边界 | partial | 已固定 CollectionTask 和 job id 边界；后台调度器启动留到 CollectorService 接入后 |
| 后端测试 | complete | Auth/Project/Source/Task 共 8 项测试通过 |
| 前端 Source | complete | `/sources` 支持 Collector 选择、动态配置表单、测试配置、启用 |
| 前端 Task | complete | `/tasks` 支持任务列表、Run Now、Pause、Resume、最近运行日志 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| OpenAPI 验证 | complete | 临时 `8010` 服务确认 Collector/Source/Task 路由已暴露 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- Source test 当前只验证 Collector 类型和配置结构，不执行网络采集。
- Task `run now` 当前创建失败态 TaskRun，这是诚实边界；采集成功态必须等 Sprint 3 的 CollectorService 和 RawRecord 表。
- APScheduler 不在 Sprint 2 启动后台任务，避免定时器运行但没有采集器可执行。

进入 Sprint 3 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

## 21. Sprint 3 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| RawRecord 模型 | complete | 已建立 `raw_records` ORM、schema、repository、API route |
| 数据库迁移 | complete | 已新增 `202606110004_raw_records.py`，含 source+content_hash 去重约束 |
| Collector 基类 | complete | 已建立 `BaseCollector`、`CollectorRawRecord`、`CollectionResult`、测试结果模型 |
| GitHub Repo Collector | complete | 已实现仓库元数据采集，使用固定 timeout 和 User-Agent |
| GitHub Topic Collector | complete | 已实现 topic search 快照采集，限制 `max_results` 范围 |
| Generic Web Collector | complete | 已实现 HTML 快照采集和标题/正文提取；真实渲染截图后置 |
| Manual JSON Collector | complete | 已实现手动 JSON payload 采集 |
| CollectorService | complete | `run now` 已接入真实 Collector 执行、RawRecord 写入、hash 去重和失败持久化 |
| TaskRun 日志 | complete | JSON 日志使用 `flag_modified` 显式持久化，避免原地变更丢日志 |
| RawRecord API | complete | 已暴露 `/api/raw-records` 列表和详情接口，支持 source/task_run 过滤 |
| 后端测试 | complete | Collector 单测、Manual JSON 闭环、去重、异常持久化共 13 项测试通过 |
| 前端 RawRecord | complete | `/raw-records` 已实现列表、选中详情、content JSON、hash 和来源展示 |
| 前端 Task | complete | Run Now 后按成功/失败更新计数，并显示真实运行日志 |
| 前端 Source | complete | Manual JSON 输入增加解析错误反馈，Source test 文案更新 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| OpenAPI 验证 | complete | 临时 `8010` 服务确认 `/api/raw-records` 已暴露；服务已停止 |
| 前端运行验证 | complete | `http://localhost:3000/raw-records` 返回 200 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键修正：

- TaskRun 不再用 Sprint 2 的占位失败记录，手动运行会真实执行 Collector。
- RawRecord 去重以 `source_id + content_hash` 为边界，避免同一 Source 重复写入相同快照。
- Collector 异常不会跳过 TaskRun，失败状态、错误信息和日志都会落库。
- Generic Web 当前只保存 HTML snapshot，不做 Playwright 渲染截图；这是 MVP 范围控制。

进入 Sprint 4 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 4 目标：

1. 建立 `entities` 和 `entity_snapshots`。
2. 将 RawRecord 转换为确定性 EntitySnapshot。
3. 完成 GitHub repo、Generic web、Manual JSON 三条最小 normalize 路径。
4. 前端 `/entities` 展示实体、latest snapshot 和来源 RawRecord。

## 22. Sprint 4 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Entity 模型 | complete | 已建立 `entities` ORM，支持 `external_id + entity_type` 去重和 `latest_snapshot_id` |
| EntitySnapshot 模型 | complete | 已建立 `entity_snapshots` ORM，关联 Entity 与 RawRecord |
| 数据库迁移 | complete | 已新增 `202606110005_entities_and_snapshots.py` |
| Entity API | complete | 已暴露 `/api/entities` 列表和 `/api/entities/{id}` 详情 |
| Snapshot API | complete | 已暴露 `/api/entities/{id}/snapshots` |
| NormalizationService | complete | 已实现 RawRecord 到 EntitySnapshot 的确定性标准化 |
| GitHub Repo normalize | complete | 输出 `github_repo` 实体和 stars/forks/issues/watchers metrics |
| GitHub Topic normalize | complete | 将 topic 搜索结果拆成多个 `github_repo` 实体快照 |
| Generic Web normalize | complete | 输出 `web_page` 实体和 text/html length metrics |
| Manual JSON normalize | complete | 支持 object/list payload，提取数值字段作为 metrics |
| CollectorService 接入 | complete | TaskRun 成功后同步创建 EntitySnapshot，并写入 `entities_count` |
| 后端测试 | complete | Normalization 单测、Manual JSON 端到端实体快照链路共 17 项测试通过 |
| 前端 Entity | complete | `/entities` 已实现实体列表、详情、快照时间线、metrics 展示 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| OpenAPI 验证 | complete | 临时 `8010` 服务确认 `/api/entities` 和 snapshots 路由已暴露；服务已停止 |
| 前端运行验证 | complete | `http://localhost:3000/entities` 返回 200 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- 标准化逻辑集中在 `normalization_service`，不让 Collector 直接知道 ORM 或数据库会话。
- `latest_snapshot_id` 使用循环外键，迁移中先建表再补外键，避免 PostgreSQL 建表顺序问题。
- RawRecord 去重后重复内容不会新增 EntitySnapshot；这是当前 MVP 对“内容不变”的保守处理。
- 前端暂不做复杂趋势图，只展示快照时间线和 metrics；Signal 阶段再补趋势对比。

进入 Sprint 5 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 5 目标：

1. 建立 `signals` 表。
2. 实现 `star_growth`、`page_changed`、`data_quality_anomaly` 三类确定性信号。
3. Signal 必须绑定 previous/current EntitySnapshot。
4. 前端展示 Signal 列表，并在 Entity 详情中显示关联 signals。

## 23. Sprint 5 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Signal 模型 | complete | 已建立 `signals` ORM，绑定 Entity、previous/current EntitySnapshot |
| 数据库迁移 | complete | 已新增 `202606110006_signals.py` |
| Signal API | complete | 已暴露 `/api/signals` 列表和 `/api/signals/{id}` 详情 |
| Entity 关联信号 API | complete | 已暴露 `/api/entities/{id}/signals` |
| star_growth | complete | 基于最近两次 `github_repo` snapshot 的 stars delta / ratio 确定性触发 |
| page_changed | complete | 基于 `web_page` content_hash 变化和 HTML Levenshtein 比例确定严重度 |
| data_quality_anomaly | complete | 基于最近 TaskRun 失败率/连续失败数触发；只有可绑定 Source 最近实体快照时落库 |
| CollectorService 接入 | complete | 新 EntitySnapshot 生成后同步检测快照信号；失败 TaskRun 后检测质量信号 |
| 后端测试 | complete | Signal 单测、star_growth API 端到端链路共 21 项测试通过 |
| 前端 Signal | complete | 新增 `/signals` 页面，展示信号列表、严重度、delta、metadata 和快照绑定 |
| Entity 关联展示 | complete | `/entities` 详情侧栏已显示关联 signals |
| 导航入口 | complete | 侧栏新增“信号中心” |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| OpenAPI 验证 | complete | 临时 `8010` 服务确认 `/api/signals` 和 `/api/entities/{id}/signals` 已暴露；服务已停止 |
| 前端运行验证 | complete | `http://localhost:3000/signals` 返回 200 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- Signal 生成仍是规则层，不调用 LLM，不生成 Intelligence。
- `data_quality_anomaly` 不创建无实体证据信号；没有可绑定快照时跳过，避免证据链断裂。
- `page_changed` 使用有上限的 Levenshtein 计算，避免大 HTML 快照导致单次检测过慢。
- 当前不做 Signal 去重更新，只防止同一 signal_type + snapshot pair 重复插入。

进入 Sprint 6 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 6 目标：

1. 建立 `intelligence_items`、`evidences` 和 `intelligence_feedback`。
2. 将 Signal 聚合为 Intelligence，所有 Intelligence 必须绑定 Evidence。
3. LLM 只生成摘要文本，不生成事实字段或评分。
4. 前端 `/intelligence` 从空状态升级为情报列表与证据入口。

## 24. Sprint 6 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Intelligence 模型 | complete | 已建立 `intelligence_items` ORM，包含四维评分、final_score、domain、status |
| Evidence 模型 | complete | 已建立 `evidences` ORM，支持 `signal`、`snapshot`、`raw_record`、`url` 四类证据 |
| Feedback 模型 | complete | 已补齐 PRD 未列出的 `intelligence_feedback` 表，支撑 feedback API |
| 数据库迁移 | complete | 已新增 `202606110007_intelligence_evidence.py` |
| Intelligence API | complete | 已暴露列表、详情、状态更新、证据列表、feedback 五类接口 |
| Signal 接入 | complete | 新 Signal 创建后同步触发 `generate_intelligence_for_signal` |
| 评分公式 | complete | 已按 PRD 权重实现 `impact 0.35 + confidence 0.25 + novelty 0.20 + urgency 0.20` |
| Evidence 构建 | complete | 每条 Intelligence 至少生成 Signal evidence；有快照和 RawRecord 时补齐证据链 |
| LLM adapter | partial | 已实现 `BaseLLMAdapter` 协议、`LLMService` 和 `MockLLMAdapter`；真实 OpenAI/Anthropic adapter 暂缓 |
| 前端 Intelligence | complete | `/intelligence` 已实现列表、筛选、详情、Score Breakdown、Evidence Timeline、审计面板、状态修改和 Feedback |
| Mock API | complete | 已新增 Intelligence/Evidence mock 数据，前端可在无后端时演示完整链路 |
| 后端测试 | complete | API 端到端覆盖 Signal -> Intelligence -> Evidence -> status -> feedback；`pytest` 22 项通过 |
| 后端静态检查 | complete | `uv run ruff check .`、`uv run mypy src tests` 通过 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过 |
| OpenAPI 验证 | complete | 本地 schema 校验确认 `/api/intelligence` 全部 Sprint 6 路由已暴露 |
| 前端运行验证 | complete | 新 dev server `http://localhost:3001/intelligence` 桌面和移动宽度渲染通过，无横向溢出 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- Intelligence 生成采用“单 Signal 可生成一条情报”的 MVP 规则；服务层已查询 project 内 recent signals，用于 novelty 评分，后续可扩展为多 Signal 聚合。
- `Evidence` 表按 PRD 原字段实现，没有新增 `snapshot_id`；snapshot evidence 通过 `signal_id + entity_id + raw_record_id` 和文本片段保持可审计性。
- LLM 只通过 Mock adapter 生成 title/summary，不允许修改评分、状态、URL 或证据字段。
- 真实 OpenAI/Anthropic adapter 暂不落空壳，等 provider 配置、调用预算、重试策略和 schema 契约明确后再实现。
- `/intelligence` 已包含基础审计面板，但尚未实现独立 `/intelligence/{id}` 详情路由、摘要关键结论点击映射和 old/new snapshot 对比。

进入 Sprint 7 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 7 目标：

1. 将当前 `/intelligence` 内联详情升级为独立 `/intelligence/{id}` 详情页。
2. 实现摘要关键结论到 Evidence 的可点击映射。
3. 增加 old/new snapshot metrics 对比 API 与前端对比视图。
4. 截图 URL 存在时在审计面板中展示截图证据。
5. 补充移动端审计面板交互，避免长证据文本压缩主要操作。

## 25. Sprint 7 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Signal snapshot compare API | complete | 已新增 `/api/signals/{signal_id}/snapshot-compare`，返回 previous/current snapshot、metrics_diff |
| Evidence asset 扩展 | complete | Evidence API 响应已补 `screenshot_url`，前端可展示截图证据 |
| 独立情报详情页 | complete | 已新增 `/intelligence/[intelligenceId]`，从列表页可进入详情 |
| 摘要到 Evidence 映射 | partial | 已实现摘要句子级点击映射到 Evidence；精确 claim span 需等待 LLM 输出 schema |
| Snapshot Compare UI | complete | 详情页展示 Old Snapshot vs New Snapshot 和 metrics diff |
| Audit Drawer | complete | 详情页展示 Evidence ID、Signal ID、RawRecord ID、URL、截图和 highlighted_text |
| 状态与反馈 | complete | 详情页支持 reviewed/following/dismissed/converted 和 useful/not_useful/false_positive |
| 后端测试 | complete | 集成测试覆盖 snapshot compare、Evidence screenshot_url 字段；`pytest` 22 项通过 |
| 后端静态检查 | complete | `uv run ruff check .`、`uv run mypy src tests` 通过 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过；`img` 外部截图存在 Next 性能 warning |
| HTTP 路由验证 | complete | `http://localhost:3001/intelligence/intel_star_growth` 返回 200 |
| 浏览器运行验证 | partial | in-app Browser 本轮对动态页 hydration 状态不稳定；以后需要正式 Playwright E2E 依赖 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- Snapshot compare 放在 Signal API 下，而不是 Intelligence API 下；原因是 compare 的天然边界是 previous/current snapshot pair。
- 未修改 `evidences` 表结构；截图来自已有关联 `raw_records.screenshot_url`，避免为展示字段新增迁移。
- 摘要到证据的映射暂为句子级确定性映射，不伪造精确 claim span。
- 外部截图使用原生 `img`，不使用 `next/image`；截图 URL 来自采集数据源，无法预先维护静态 remote allowlist。

进入 Sprint 8 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 8 目标：

1. 实现 Dashboard overview API。
2. 实现 task health、domain breakdown、top intelligence 聚合。
3. 将 `/dashboard` 从静态 mock 升级为 API 驱动。
4. 将四个 `/domain/{domain}` 页面接入域内 Project、Signal、Intelligence 汇总。
5. 补充分页或 limit，避免 Dashboard 直接拉取无界列表。

## 26. Sprint 8 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Dashboard overview API | complete | 已新增 `GET /api/dashboard/overview`，支持 `project_id`、`domain`、`from`、`to`、`limit` 查询参数 |
| Dashboard 聚合仓储 | complete | 已实现 source count、intelligence count、type breakdown、domain breakdown、top intelligence、task health、recent failures、snapshot metrics 聚合 |
| Dashboard 服务层 | complete | 已计算 `task_success_rate`、`field_completeness`、`failed_tasks`、`recent_runs`、`source_count` 等首屏指标 |
| 全局 Dashboard | complete | `/dashboard` 已从静态 mock 升级为 API 驱动组件，保留 mock API fallback |
| Domain Views | complete | `/domain/[domain]` 已接入同一 Dashboard 聚合接口，按 domain 展示域内 Project、Signal、Intelligence、任务健康度 |
| limit 边界 | complete | `top_intelligence` 默认限制 10 条，API 上限 50 条，避免首屏无界拉取 |
| 后端测试 | complete | 集成测试覆盖成功和失败任务下的 Dashboard 聚合；`pytest` 22 项通过 |
| 后端静态检查 | complete | `uv run ruff check .`、`uv run mypy src tests` 通过 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过；保留 Sprint 7 外部截图 `img` warning |
| HTTP 路由验证 | complete | `http://localhost:3001/dashboard`、`/domain/osint`、`/domain/competitor` 返回 200 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- `active_alerts` 暂时固定为 `0`；原因是 Alert Rule、Alert Event、Notification 尚未进入数据模型，不能用假聚合伪造告警能力。
- `field_completeness` 采用最近 200 条 snapshot metrics 的非空字段比例作为 MVP 代理指标；后续需要按 domain 定义核心字段权重。
- Dashboard 聚合走独立 repository/service，不复用列表 API；原因是首屏指标需要可控查询边界和后续索引优化空间。
- Domain Views 先做域内经营视图，不单独创建四套页面逻辑；避免四个 domain 在 MVP 阶段产生平行重复实现。

进入 Sprint 9 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 9 目标：

1. 新增 `reports`、`alert_rules`、`alert_events`、`notifications` 数据模型和 Alembic migration。
2. 实现从 Top Intelligence 和 Evidence 生成 Report draft 的服务层，不让 Report 脱离证据链。
3. 实现确定性 Alert Rule matcher，优先支持 score threshold、domain、intelligence type、status 条件。
4. 实现 Notification Center API 和前端入口，展示未读、已读、来源对象和触发规则。
5. 暂缓真实 SMTP / webhook 推送，只保留可测试 adapter 边界和 mock delivery，避免在告警模型未稳定前引入外部副作用。

## 27. Sprint 9 执行状态

更新时间：2026-06-11

| 项目 | 状态 | 结果 |
|---|---|---|
| Report 数据模型 | complete | 已新增 `reports` 表、SQLAlchemy model、schema、repository、service、API 和 Alembic revision `202606110008` |
| Alert 数据模型 | complete | 已新增 `alert_rules`、`alert_events`，支持 rule create/update/disable、event list 和 Signal 命中落库 |
| Notification 数据模型 | complete | 已新增 `notifications`，支持列表、单条已读、全部已读 |
| Report 生成 | complete | `POST /api/reports/generate` 从真实 Intelligence + Evidence count 渲染 Markdown，不生成不存在的 URL 或指标 |
| Report 发送 | complete | `POST /api/reports/{id}/send` 将 Report 标记为 `sent`，并创建站内 `report_ready` 通知 |
| Alert matcher | complete | Signal 创建后自动匹配 enabled AlertRule；condition 支持 `eq`、`in`、`gt`、`gte`、`lt`、`lte`，上下文包含 severity、domain、final_score、intelligence_type、status 等字段 |
| 站内通知 | complete | AlertRule 命中 `in_app` / `both` channel 时创建 `alert` 通知；`email` channel 不伪造发送结果 |
| Dashboard active alerts | complete | `active_alerts` 已由固定 `0` 改为统计未 resolved/muted 的 AlertEvent，并支持 project/domain/time 过滤 |
| 前端 Reports | complete | `/reports` 已实现报告列表、生成、发送、Markdown 正文查看 |
| 前端 Alerts | complete | `/alerts` 已实现规则创建表单、规则列表、预警事件列表 |
| 前端 Notifications | complete | `/notifications` 已实现 unread/all、单条已读、全部已读和关联入口 |
| 后端测试 | complete | 新增 Sprint 9 集成测试覆盖 AlertRule -> Signal -> AlertEvent -> Notification、Report generate/send/read；`pytest` 24 项通过 |
| 后端静态检查 | complete | `uv run ruff check .`、`uv run mypy src tests` 通过 |
| OpenAPI 验证 | complete | 已确认 `/api/reports`、`/api/alert-rules`、`/api/alert-events`、`/api/notifications` 路由暴露 |
| Alembic 验证 | complete | `uv run alembic heads` 返回 `202606110008 (head)` |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build` 通过；仍保留 Sprint 7 外部截图 `img` warning |
| HTTP 路由验证 | complete | `http://localhost:3001/reports`、`/alerts`、`/notifications` 返回 200 |
| PostgreSQL 实库验证 | blocked | Docker daemon 未运行，无法执行 PostgreSQL migration 实测 |

本阶段关键取舍：

- `DELETE /api/alert-rules/{id}` 当前实现为禁用规则，而不是物理删除；原因是 AlertEvent 需要保留规则来源，避免历史预警失去上下文。
- `email` channel 暂不创建“已发送”假象；只有 `in_app` / `both` 会把 AlertEvent 标记为 `sent` 并创建 Notification。
- Report 生成暂用确定性 Markdown renderer，不接 LLM；原因是当前真实 LLM adapter 和输出 schema 尚未确定，不能让日报越过证据链生成自由文本。
- Report 的预警区暂不并入 AlertEvent 明细；Alert 模型刚落地，日报与预警的时间窗口合并留到 Sprint 10 稳定化处理。
- 前端 mock 数据继续从同一批 Project / Signal / Intelligence 推导 Report、Alert、Notification，避免演示数据与真实领域链路分叉。

进入 Sprint 10 前仍需执行：

```bash
docker compose up -d db
cd apps/api
uv run alembic upgrade head
```

Sprint 10 目标：

1. 执行 PostgreSQL 实库 migration，修复 SQLite 与 PostgreSQL 行为差异。
2. 补 Report 与 Alert 的时间窗口合并，把当日 AlertEvent 安全并入日报。
3. 增加 Playwright E2E，覆盖 Dashboard、Intelligence、Reports、Alerts、Notifications 的主路径。
4. 做移动端视觉回归检查，重点看报告正文、规则表单、通知操作按钮是否溢出。
5. 收敛部署文档、环境变量、README 和开发启动脚本，形成 MVP 交付包。

## 28. Sprint 10 执行状态

更新时间：2026-06-12

| 项目 | 状态 | 结果 |
|---|---|---|
| PostgreSQL 实库 migration | blocked | `docker compose up -d db` 仍无法连接 Docker daemon，不能执行 `uv run alembic upgrade head` 实测 |
| Report + Alert 时间窗口合并 | complete | 日报生成已查询同周期 AlertEvent，并在 `## 预警区` 写入规则名、signal_type、severity、status、intelligence_id |
| 后端测试 | complete | 新增日报包含 AlertEvent 集成测试；`pytest` 25 项通过 |
| 后端静态检查 | complete | `uv run ruff check .`、`uv run mypy src tests` 通过 |
| OpenAPI 验证 | complete | Sprint 10 关键路由仍在 schema 中暴露 |
| Alembic head 验证 | complete | `uv run alembic heads` 返回 `202606110008 (head)` |
| Playwright E2E | complete | 已新增 `apps/web/playwright.config.ts` 和 `tests/e2e/main-flows.spec.ts`，覆盖 Dashboard、Intelligence、Reports、Alerts、Notifications |
| 移动端布局检查 | complete | Playwright mobile project 验证 `/reports`、`/alerts`、`/notifications` 无横向溢出 |
| 前端校验 | complete | `pnpm lint`、`pnpm test`、`pnpm build`、`pnpm test:e2e` 通过；仍保留 Sprint 7 外部截图 `img` warning |
| 文档收敛 | complete | README 和本地开发流程已补当前 MVP 能力、完整质量检查命令、E2E 和 Docker daemon 前置说明 |
| MVP 验证脚本 | complete | 已新增并验证 `bash scripts/verify-mvp.sh`；默认 API/Web 全质量线通过，`--with-db` 在 Docker daemon 阶段明确失败 |
| Dev DB 脚本收敛 | complete | `bash scripts/dev-start.sh`、`CONFIRM_RESET=1 bash scripts/dev-reset-db.sh` 已接入 Docker daemon 检查、PostgreSQL ready 等待和可选 `--migrate` |
| GitHub Actions CI | complete | 已新增 `.github/workflows/ci.yml`，在 push / pull request 到 `main` 时运行 API 与 Web 质量门；CI 不启动 Docker，PostgreSQL 实库 migration 仍由交付前本地验证承担 |

本阶段关键取舍：

- 未绕过 Docker daemon 阻塞去伪造 PostgreSQL 验证结果；当前只确认 Alembic head，实库 upgrade 等 Docker 可用后执行。
- Playwright E2E 使用 mock API 和独立 `3100` 端口；它验证前端主路径和响应式布局，不替代后端集成测试。
- 移动端项目固定使用 Chromium 小屏视口；避免引入 WebKit 下载依赖，同时保持布局断言稳定。
- `bash scripts/verify-mvp.sh` 默认不依赖 Docker；`--with-db` 用于 Docker 可用后的交付前实库复验。
- 本地 DB 操作统一走 `bash scripts/dev-start.sh` / `bash scripts/dev-reset-db.sh`；不再要求用户手写 `docker compose up -d db` 后猜测 ready 时机。
- GitHub Actions CI 只覆盖不依赖 Docker 的自动质量门；原因是当前迁移实测需要可控 PostgreSQL 环境，不能把 Docker daemon 阻塞伪装成远端已完成。

进入交付前仍需执行：

```bash
bash scripts/dev-start.sh --migrate
```

交付前建议：

1. Docker 可用后完成 PostgreSQL migration 和至少一条真实 API smoke test。
2. 如需真实邮件，先定义 SMTP adapter 的失败语义，再启用 `email` / `both` 外部投递。
3. 对外演示前保留 `NEXT_PUBLIC_MOCK_API=true`，生产联调时显式设置 `NEXT_PUBLIC_MOCK_API=false`。
