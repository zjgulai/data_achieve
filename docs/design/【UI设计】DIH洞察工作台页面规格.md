---
name: dih-insight-workbench-ui-spec
description: DIH 洞察工作台的 11 条路由页面规格。给出设计原则、信息架构、逐页线框与验收判据、组件清单、设计 token、报告阅读页与工作台三栏的详细实现规格。设计或实现 DIH 页面时先读这份。
---

# UI 设计：DIH 洞察工作台页面规格

> 版本：v1.0 · 2026-10-20
> 范围：`apps/scraper-console`。技术栈为 Next.js 16.3.0、React 19.2.8、Tailwind v4。见 `apps/scraper-console/package.json:1-34`。
> 依据：[PRD](../product/【PRD】母婴出海数据洞察Agent工作台.md) · [Playbook](../product/【Playbook】母婴出海洞察交付.md) · [Monid 逆向报告 v2](../architecture/【逆向报告】Monid源码-站点-产物-v2.md) · [首页与目录视觉规范](../architecture/【设计规范】DIH首页与目录视觉规范.md)
> 契约以 [契约冻结 v1](./【契约冻结】v1-表名-枚举-接口.md) 为准。

## 0. 范围、现状与判定口径

### 0.1 本文件覆盖的 11 条路由

本文件只写 11 条路由。路由分组与层级来自 PRD 第 3.3 节。页面的数据契约来自 PRD 第 6 节与第 7 节。

| # | 路由 | 分组 | 鉴权 | 渲染方式 | 主数据源 | 页面状态 |
|---|---|---|---|---|---|---|
| 1 | `/` | 公开区 | 否 | RSC + 客户端表单 | `GET /api/platform-packages`（live） | new |
| 2 | `/capabilities` | 公开区 | 否 | RSC + 客户端筛选 | `GET /api/tools`（new）；`GET /api/platform-packages`（live） | new |
| 3 | `/capabilities/[id]` | 公开区 | 否 | RSC + 客户端抽屉 | `GET /api/tools/{tool_id}`（new）；`GET /api/platform-packages/{platform_id}/playbook`（live） | new |
| 4 | `/workbench` | 授权区 | 是 | 客户端 | `GET /api/projects`、`GET /api/tasks`（live） | new |
| 5 | `/workbench/[taskId]` | 授权区 | 是 | 客户端 | `POST /api/workbench/plans/preview`（new）；运行端点（new） | new |
| 6 | `/reports` | 授权区 | 是 | 客户端 | `GET /api/reports`（live） | new |
| 7 | `/reports/[id]` | 授权区 | 是 | 客户端 + 服务端首屏 | `GET /api/reports/{id}`、`GET /api/reports/{id}/evidence-references`（live）；合同端点（new） | new |
| 8 | `/reports/public/[id]` | 公开区 | 否 | RSC | `GET /api/reports/public/{token}`（new） | new，P2 |
| 9 | `/connectors` | 授权区 | 是 | 客户端 | `GET /api/platform-packages`、`GET /api/settings/platform-credentials`（live） | new |
| 10 | `/settings` | 授权区 | 是 | 客户端 | `GET /api/auth/me`（live）；成员、额度、审计（new） | new |
| 11 | `/docs` | 公开区 | 否 | RSC | 静态 MDX；`GET /api/collectors/docs`（live） | new |

规则：

- `/workbench` 是唯一任务入口。不得把 `/dashboard` 或 `/projects` 设为一级入口。
- `/reports/[id]` 的 SOP 视图使用同一路由加查询参数 `?view=sop`。SOP 不新增第 12 条路由。依据见 PRD 第 7.5 节。
- 11 条路由之外，现有 `/datasets`、`/tools/tiktok` 保留为二级页面。它们不在主导航。

### 0.2 现有页面处置

“已有的继续使用”必须落到具体文件。下表给出每个现有页面的处置与证据。

| 现有路由 | 现状证据 | 处置 | 目标 |
|---|---|---|---|
| `/platforms` | `apps/scraper-console/src/app/platforms/page.tsx:387-401`。`GET /api/collectors/catalog`。生产标 live。 | replace | `/capabilities` |
| `/skills` | `apps/scraper-console/src/app/skills/page.tsx:1-5` 包装 `SkillsDirectory`。 | merge | `/capabilities` 的平台包入口 |
| `/skills/[platformId]` | `apps/scraper-console/src/components/skills/skill-detail.tsx:15-27` 请求平台包、playbook、release。 | merge | `/capabilities/[id]` 的内嵌 playbook 区块 |
| `/projects` | `apps/scraper-console/src/app/projects/page.tsx:116-118` 请求 `GET /api/projects`。 | 保留为 /workbench 下钻 | `/workbench` 左栏 |
| `/projects/[id]` | `apps/scraper-console/src/app/projects/[id]/page.tsx:144` 与 `:156` 是静态占位，不发请求。 | 保留为 /workbench 下钻 | `/workbench/[taskId]` |
| `/tasks` | `apps/scraper-console/src/app/tasks/page.tsx:96-102` 10 秒轮询。 | 保留为 /workbench 下钻 | `/workbench/[taskId]` 运行时间线 |
| `/runs` | `apps/scraper-console/src/app/runs/page.tsx:164-168` 15 秒轮询。 | 保留为 /workbench 下钻 | 同上 |
| `/collect/[run_id]` | `apps/scraper-console/src/app/collect/[run_id]/page.tsx:14-16`。 | merge | 运行下钻 |
| `/raw-records` | `apps/scraper-console/src/app/raw-records/page.tsx:35-37`。页面可用，侧栏无入口。 | merge | 证据抽屉的数据层 |
| `/datasets` | `apps/scraper-console/src/app/datasets/page.tsx:121-123`。生产标 live。 | keep | 二级页面，从报告与任务下钻进入 |
| `/dashboard` | `apps/scraper-console/src/app/dashboard/page.tsx:25-29`。页面可用，侧栏无入口。 | retire nav | 指标并入 `/workbench` 左栏头部 |
| `/collector-docs` | `apps/scraper-console/src/app/collector-docs/page.tsx:273-275`。 | merge | `/docs` |
| `/tools/tiktok` | `apps/scraper-console/src/app/tools/tiktok/page.tsx:161-200`。生产截图存在。 | keep | 二级页面，从能力详情与任务进入 |
| `/settings/credentials` | `apps/scraper-console/src/app/settings/credentials/page.tsx:228-230`。 | replace | `/connectors` |
| `/settings/account` | `apps/scraper-console/src/app/settings/account/page.tsx:3-14`。只有“建设中”文案，无 API。 | delete | 无 |
| `/` | `apps/scraper-console/src/app/page.tsx:3-4` 重定向到 `/platforms`。 | replace | 新首页 |

处置规则：

- `replace` 表示新页面重写。旧页面下线。
- `merge` 表示旧页面的能力进入新页面。旧路由保留一个重定向周期，然后删除。
- `keep` 表示保留现有页面与现有调用路径。只改导航入口。
- `保留为 /workbench 下钻` 表示旧路由保留，作为 `/workbench` 的下钻页面。不进入一级导航，也不删除。
- `delete` 表示直接删除。删除前必须确认没有动态链接。

### 0.3 判定口径

本文件使用四种状态。它们与前端清点 JSON 的规则一致。

| 状态 | 判据 |
|---|---|
| `live` | 有生产只读证据，或有通过的测试。 |
| `extend` | 模块存在，但范围不足。必须改造后才能用。 |
| `new` | 仓库中没有实现。必须新建。 |
| `dead` | 代码存在，但没有可用调用路径。不得复用。 |

本文件引用的当前证据：

1. 2026-10-20 对 `https://scrapy.luteos.com` 的只读 GET 探测。端点包括 `/api/health`、`/api/tasks/scheduler/overview`、`/api/reports`、`/api/signals`、`/api/intelligence`、`/api/dashboard/overview`、`/api/collectors/catalog`、`/api/capabilities/matrix`、`/api/toolkit`、`/api/tiktok/tools`、`/api/projects/{id}/workflow-plans`、`/api/projects/{id}/workflow-runs`。
2. 本机 2026-10-20 执行 `pnpm test`：9 个用例通过。
3. 本机 2026-10-20 执行 `pnpm exec tsc --noEmit`：通过。
4. 本机 2026-10-20 执行 `pnpm build`：通过，生成 16 个页面。

三条限制：

- 测试基线：2026-10-20 执行 `pytest -q apps/api/tests/unit` → 1980 passed / 0 failed；`pytest -q apps/api/tests/integration` → 384 passed / 0 failed。`reports/live-sweep/baseline-pytest-failures.txt` 的 137 条基线已作废，不得再引用。
- 生产 `/api/collectors/catalog` 当前返回 309 个能力视图、281 个唯一端点、70 个平台（`catalog_digest=dad20448…`）。仓库生成物为 286 与 258，口径不同，不得混用。见 `README.md:16-17`。
- TikTok R1 的 7 个关键文件未纳入 HEAD 跟踪。涉及 TikTok 的页面必须先确认部署分支包含这些文件。

### 0.4 本批页面顺序

P0 先交付主路径。P1 再交付公开页面。P2 最后交付分享。

| 优先级 | 路由 | 理由 | 前置 |
|---|---|---|---|
| P0 | `/capabilities`、`/capabilities/[id]` | 目录是唯一发现入口。目录缺 schema 时，工作台无法选源。 | `tool_catalog` 表与 `GET /api/tools` |
| P0 | `/workbench`、`/workbench/[taskId]` | 任务入口。计划与门禁在这里产生。 | 真实运行端点；七个槽位的适配器 |
| P0 | `/reports`、`/reports/[id]` | 交付物。报告合同在这里渲染。 | `report_contract` 与 `report_artifacts` |
| P1 | `/connectors` | 连接器决定 `config_gated` 是否可解除。 | 项目级凭据解析 |
| P1 | `/settings` | 成员、额度、审计是授权区基础。 | 租户鉴权 |
| P1 | `/docs` | 支撑自服务。 | 无 |
| P1 | `/` | 公开页面。依赖 P0 的真实产物。 | 一份可公开的样例报告 |
| P2 | `/reports/public/[id]` | 对外分享。依赖签收与分享审计。 | `report_shares` 表 |

三条阻断项必须先解决。否则页面只能显示 `held` 或 `config_gated`。

1. `tool_catalog` 不存在。目录详情页的参数表与成本无法渲染。
2. 真实运行层不可用。`workflow_runs` 是已挂载的 fixture-only 路由（`origin/main:143` 已注册）。生产 `/api/projects/{id}/workflow-runs` 返回 200，`execution_mode=fixture`。它不能承载真实执行。
3. 报告合同不存在。现有 `_render_daily_report` 只输出三个通用章节。见 `apps/api/src/data_intelligence_hub/services/report_service.py:1198-1244`。

## 1. 设计原则

五条。每条给一个可判定的标准。

### 原则 1 结论必须带反证

每条结论必须配一个反向字段。报告中的每个 exhibit 必须有 `counterevidence_text`。

判定标准：

- `report_contract` 校验时，任一 exhibit 缺少第 4 段 `Counterevidence`，构建失败。
- 报告页面不得渲染缺少第 4 段的 exhibit。
- 反证字段允许写“未发现反证”。字段不得为空。

依据：PRD 第 7.2 节与第 5.4.1 节。

### 原则 2 门禁与缺口必须可见

报告首屏必须分别显示三项：最低证据等级、门禁状态、claim 分布。三项不得合并成一个“可信度”数字。

判定标准：

- 三个独立的 DOM 节点。每个节点有 `data-testid`。
- 页面文本中不出现“综合可信度”“可信度评分”等合并指标。
- `evidence_gap` 与 `blocked` 必须出现在 claim 分布里。不得隐藏。

依据：PRD 第 7.3.1 节。

### 原则 3 一个任务一条路径

新用户从 `/workbench` 到第一份报告，最多改变 2 次路由。侧栏不得提供第二个任务入口。

判定标准：

- 主导航只有 4 个授权区入口：工作台、报告中心、连接器、设置。
- `/workbench` 的任务创建表单在首屏可见。不要求先建项目。
- 任务详情的“查看报告”按钮直接跳 `/reports/[id]`。不经过 `/reports`。

依据：PRD 第 3.3 节与第 6.4 节。

### 原则 4 目录用行，报告用版式

目录默认使用紧凑行。报告使用固定版式。两者不混用。

判定标准：

- 桌面宽度 1440px 时，目录行高不超过 56px。
- 目录不使用同尺寸卡片网格。
- 报告正文宽度不超过 820px。正文行高不小于 1.66。
- 报告图表不使用图表库。图表用 CSS grid 与 flex 实现。

依据：PRD 第 6.2 节。逆向报告第 3.2 节与第 5.4 节。

### 原则 5 状态必须可读，不靠颜色

每个状态必须有中文文字、图标和可访问名称。颜色只作辅助。

判定标准：

- 状态元素包含 `<span>` 文本与 `aria-label`。
- 正文对比度不低于 4.5:1。图形对比度不低于 3:1。
- 关闭颜色后，用户仍能区分 `success`、`empty`、`config_gated`、`failed`。

依据：设计规范第 6.3 节与第 9 节。

## 2. 信息架构

### 2.1 路由树

```text
DIH 洞察工作台
├─ 公开区（5 条）
│  ├─ /                        首页
│  ├─ /capabilities            能力目录
│  │  └─ /capabilities/[id]    能力详情
│  ├─ /reports/public/[id]     报告分享页（P2）
│  └─ /docs                    文档
└─ 授权区（6 条）
   ├─ /workbench               工作台首页（任务入口）
   │  └─ /workbench/[taskId]   任务详情（对话 + 计划 + 证据）
   ├─ /reports                 报告中心
   │  └─ /reports/[id]         报告阅读页
   │     └─ ?view=sop          SOP 视图（同一路由）
   ├─ /connectors              连接器与凭据
   └─ /settings                设置（成员、额度、审计）
```

### 2.2 一级导航

公开区与授权区使用两套壳。两套壳共享品牌与页头组件。

| 区域 | 导航 | 数量 |
|---|---|---|
| 公开区 | 页头链接：首页、能力目录、文档 | 3 |
| 公开区页头 | 工作台入口 | 1 |
| 授权区 | 一级导航：工作台、报告中心、连接器、设置 | 4 |

一级导航只有授权区 4 项。公开区 3 项与页头入口 1 项是页头链接，不计入一级导航。依据 PRD 第 3.3 节。

导航规则：

- 当前项必须有 `aria-current="page"`。
- 公开区页头不显示授权区菜单。授权区侧栏不显示公开区菜单。
- 二级页面不出现在一级导航。它们通过面包屑与详情链接进入。
- 移动端导航放入抽屉。抽屉使用焦点陷阱。
- 授权区未登录时打开登录对话框。对话框覆盖当前页面。登录成功后回到原路由。不新增 `/login` 路由。

### 2.3 壳层分工

| 壳层 | 使用路由 | 侧栏 | 内容宽度 | 用途 |
|---|---|---|---|---|
| `AppShell` | `/capabilities`、`/capabilities/[id]`、`/reports`、`/connectors`、`/settings`、`/docs` | 272px，`lg` 以上显示 | 1280px | 常规工作页面（6 条） |
| `ReaderShell` | `/reports/[id]`、`/reports/public/[id]` | 无 | 1348px | 阅读与打印（2 条） |
| `WorkbenchShell` | `/workbench`、`/workbench/[taskId]` | 无全局侧栏 | 全宽 | 三栏工作区（2 条） |
| `PublicShell` | `/` | 无 | 1240px | 公开首页（1 条） |

现有 `AppShell` 见 `apps/scraper-console/src/components/layout/app-shell.tsx:16-52`。它已包含侧栏、页头、面包屑与说明条。常规页面继续使用它。

`PublicShell`、`ReaderShell` 与 `WorkbenchShell` 是新建组件。原因：

- 报告页需要 1348px 阅读壳宽度与打印样式。`AppShell` 的 `max-w-7xl` 为 1280px。它包含 272px 侧栏与 64px 内边距。1440px 视口下正文约 1104px。见 `app-shell.tsx:22`。
- 工作台需要三栏独立滚动。`AppShell` 的 `main` 是单列布局。
- 首页需要 1240px 容器与公开页头。`AppShell` 带授权区侧栏，不适用。

### 2.4 现有导航缺口

现有 `Sidebar` 只有 9 项。见 `apps/scraper-console/src/components/layout/sidebar.tsx:7-20`。

| 缺口 | 现状 | 处置 |
|---|---|---|
| 缺 `/workbench` | 无入口 | 新增一级项 |
| 缺 `/reports` | 报告页只在 `apps/web`，控制台无入口 | 新增一级项 |
| 缺 `/connectors` | 只有 `/settings/credentials` | 合并后新增一级项 |
| 缺 `/settings` | 只有 `/settings/account` 死页 | 新增一级项 |
| 有多余入口 | `/platforms`、`/skills`、`/projects`、`/tasks`、`/runs`、`/datasets`、`/collector-docs`、`/tools/tiktok` | 收敛为 4 项 |

### 2.5 页面与数据表

下表把页面结论落到真实表。新表在 `apps/api/src/data_intelligence_hub/models/` 中没有对应文件。

| 页面 | 现有表 | 新表 | 证据 |
|---|---|---|---|
| `/` | `collectors` | `tool_catalog` 读模型 | `models/collector.py:11-18` |
| `/capabilities` | `collectors` | `tool_catalog` | 生产目录 309 个能力视图、281 个唯一端点、70 个平台（`catalog_digest=dad20448…`） |
| `/capabilities/[id]` | `collectors` | `tool_catalog` | PRD 5.1 的最小字段集 |
| `/workbench` | `projects`、`collection_tasks`、`task_runs`、`workflow_plans`、`workflow_versions`、`monitoring_scopes` | `claims`、`claim_evidence`、运行成本字段 | `models/task.py:19-66`；`models/workflow_plan.py:35`、`:136`、`:227` |
| `/reports` | `reports`、`report_audit_events`、`report_subscriptions`、`report_subscription_runs` | `report_artifacts` | `models/report.py:16-88` |
| `/reports/[id]` | `reports`、`intelligence_items`、`evidences` | `report_artifacts`、`claims`、`claim_evidence`、`report_shares` | `models/intelligence.py:21-70` |
| `/connectors` | `collectors`、`platform_credential_bundles`、`provider_health_snapshots` | 项目级凭据表 | `models/platform_credential.py:12`；`models/provider_health.py:33` |
| `/settings` | `users`、`workspaces`、`workspace_members` | 角色、额度、审计事件表 | `models/user.py:16`；`models/workspace.py:23`、`:47` |
| `/docs` | 无 | 无 | 静态内容 |

新增表的依据：

- `tool_catalog`：PRD 5.1 与 5.2.1。
- `claims` 与 `claim_evidence`：PRD 5.4.1。
- `report_artifacts` 与 `report_shares`：PRD 5.5.2。

## 3. 逐页规格

每页给四部分：线框图、区块清单、交互、验收判据。

通用规则：

- 所有页面必须有唯一 `h1`。
- 所有数据区块必须有空态、加载态、错误态。
- 加载态必须占位固定高度。不得让目录行高度跳动。
- 错误态必须显示：发生了什么、影响什么、如何恢复、请求 ID。
- 空态必须区分三种：无结果、无权限、加载失败。
- 所有筛选与分页状态必须写入 URL。

页面高度比例：

| 页面 | 参考高度 | 主要区块高度比例 |
|---|---|---|
| `/` | 4500–5500px | header 1.6 / hero 15 / wall 11.6 / flow 8 / report 20 / templates 13.4 / faq 10.7 / footer 6.2 |
| `/capabilities` | 900px | header 8 / search 7 / facet 5 / results 80 |
| `/capabilities/[id]` | 1600px | header 10 / params 20 / output 15 / example 23 / playbook 25 |
| `/workbench` | 900px | topbar 6 / three columns 94 |
| `/workbench/[taskId]` | 900px | topbar 6 / three columns 94 |
| `/reports` | 900px | header 8 / filter 6 / table header 5 / rows 81 |
| `/reports/[id]` | 900px | topbar 6 / first screen 31 / chapters 63 |
| `/reports/public/[id]` | 900px | topbar 6 / first screen 31 / body 63 |
| `/connectors` | 900px | header 8 / three columns 92 |
| `/settings` | 900px | header 8 / subnav and content 92 |
| `/docs` | 900px | header 8 / three columns 92 |

### 3.1 `/` 首页

#### 线框图

参考视口 1440×900。容器 1240px。12 列。列间距 24px。总高目标 4500–5500px。

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Header 72px                                                          │
│ logo · 首页 · 能力目录 · 文档 ····················· 工作台入口 · 登录 │
├──────────────────────────────────────────────────────────────────────┤
│ Hero 680px（15%）                                                    │
│ ┌────────────────────────────────┬─────────────────────────────────┐ │
│ │ 主张 H1 56/62，最多 2 行       │ 决策问题输入 640×56             │ │
│ │ 副文 16/26，最多 2 行          │ 3 个示例问题 chip               │ │
│ │ 主按钮 160×48                  │ 提交后跳 /workbench?q=          │ │
│ └────────────────────────────────┴─────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ 数据源墙 520px（11.6%）                                              │
│ 5 列 × 2 行 tile，每块 188×64，间距 16px                            │
├──────────────────────────────────────────────────────────────────────┤
│ 五步流程 360px（8%）                                                 │
│ 5 列 × 220px：问题 → 计划 → 采集 → 分析 → 报告                      │
├──────────────────────────────────────────────────────────────────────┤
│ 真实报告 900px（20%）                                                │
│ 左 40% 说明 360px · 右 60% 报告预览 720×540                          │
├──────────────────────────────────────────────────────────────────────┤
│ 行业模板 600px（13.4%）                                              │
│ 5 列 × 224×280 卡片，间距 16px                                       │
├──────────────────────────────────────────────────────────────────────┤
│ 常见问题 480px（10.7%）  内容宽 820px，5 条折叠项                    │
├──────────────────────────────────────────────────────────────────────┤
│ Footer 280px（6.2%）                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 首屏主张 | 静态文案 | 不适用 | 不适用 | 不适用 |
| 决策问题输入 | 静态表单。提交到 `/workbench?q=` | 输入为空时，主按钮禁用 | 按钮内 spinner | 前端校验错误，显示字段级错误 |
| 数据源墙 | `GET /api/platform-packages`（live）；`GET /api/platform-packages/providers/status`（live） | “暂无已核验数据源。进入能力目录查看全部。” | 10 个 188×64 骨架块 | 隐藏数据源墙。显示一行错误与“重试”。不得用静态 logo 替代 |
| 五步流程 | 静态。链接到 `/docs#flow` 等锚点 | 不适用 | 不适用 | 不适用 |
| 真实报告 | 构建时样例 `apps/scraper-console/src/content/sample-report.json`（new）。必须标注“样例，不是实时报告” | 样例缺失时整块隐藏 | 不适用 | 显示“样例加载失败”。不显示伪造报告 |
| 行业模板 | 静态注册表。5 个模板 | 不适用 | 不适用 | 不适用 |
| 常见问题 | 静态内容 | 不适用 | 不适用 | 不适用 |

#### 交互

1. 首屏输入框获得焦点后，按 Enter 跳 `/workbench?q={encodeURIComponent(q)}`。
2. 示例问题 chip 点击后填入输入框。第二次点击提交。
3. 数据源 tile 点击后跳 `/capabilities?platform={platform_id}`。
4. 五步流程每步点击后跳 `/docs#flow-{step}`。
5. 报告预览点击后跳 `/reports/public/sample`。该页只读。
6. 模板卡点击后跳 `/workbench?template={template_id}`。表单预填模板默认值。
7. 常见问题使用 `<details>`。支持键盘展开与折叠。
8. 页面无自动播放动画。无轮播。

#### 验收判据

- 1440×900 下页面总高在 4500–5500px。
- 首屏只有一个主要动作。次要动作样式为链接或描边按钮。
- 每个展示的数字都有来源脚注。脚注可点击到能力目录。
- 页面不出现订阅、钱包、免费额度、声明式规模数字。
- 报告样例必须带“样例”标签与证据徽章。
- 关闭 JavaScript 后，首屏文案、数据源墙之外的静态区块仍可读。
- 首页不加载外部字体。字体栈来自 `globals.css:33-37`。

### 3.2 `/capabilities` 能力目录

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 页头 72px：能力目录 H1 32/38 · 结果计数                              │
├──────────────────────────────────────────────────────────────────────┤
│ 搜索条 64px，粘性。输入 640×44。右侧“清除筛选”                      │
├──────────────┬───────────────────────────────────────────────────────┤
│ 分类 rail    │ facet 条 48px：市场 · 内容类型 · 成本 · 健康度 · 核验 │
│ 240px 粘性   ├───────────────────────────────────────────────────────┤
│ 7 项，每项44 │ 表头 40px                                             │
│ 名称 + 数量  │ 行 56px × 12 = 672px                                  │
│              │ 名称 28% | 分类 12% | 市场 14% | 成本 12% | 健康 10%  │
│              │ 核验 10% | 证据等级 8% | 操作 6%                      │
│              │ 底部“加载更多” 48px                                   │
└──────────────┴───────────────────────────────────────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 搜索条 | `GET /api/tools?q=`（new）。过渡期用 `GET /api/platform-packages?query=`（live） | 显示“没有匹配的能力视图”。给“清除全部筛选”按钮 | 输入框内 spinner。结果区保留旧结果并降低透明度 | 结果区 `StateBlock`。显示错误、请求 ID、重试 |
| 分类 rail | 同一目录响应聚合。7 个稳定分类见 PRD 5.2.2。只来自 `tool_catalog` | 分类计数为 0 时置灰。不可点击 | 7 个 44px 骨架 | rail 隐藏。结果区显示错误 |
| facet 条 | `tool_catalog.markets`、`content_types`、`cost_model`、`health_status`、`verified_at`（new） | 无可用 facet 时隐藏整条 | facet 骨架 48px | 隐藏 facet。保留搜索与结果 |
| 结果表 | `GET /api/tools`（new）。字段见 PRD 5.1 | 三种空态：无结果、无权限、加载失败 | 12 行骨架，行高固定 56px | 表格区域 `StateBlock`。保留表头 |
| 分页 | `cursor` 或 `page`（new） | 不适用 | 按钮 spinner | 行内错误与重试 |

服务端获取规则：

- 首屏目录必须在 RSC 中读取。不得等待浏览器请求。
- 当前 `apiFetch` 只在浏览器运行。它读取 `NEXT_PUBLIC_API_URL`，见 `apps/scraper-console/src/lib/api/client.ts:1-2`。
- 新建 `apps/scraper-console/src/lib/api/server.ts`。它读取服务端 `API_BASE_URL`，使用 `cache: "no-store"`。
- 生产由 edge nginx 把 `/api` 转发到 `api:8000`。见 `configs/deploy/scrapy/edge-nginx.conf:26`。
- 客户端筛选只处理已加载的数据。跨页筛选必须请求服务端。

过渡期限制：

- `GET /api/platform-packages` 只能按平台分组。它没有七个任务分类。
- 七类任务分类只在 `tool_catalog` 上线后显示。
- 过渡期不得伪造任务分类计数。

#### 交互

1. 搜索输入防抖 250ms。按 Enter 立即提交。按 Escape 清空。
2. 分类点击后写入 `?category=consumer_insight`。刷新后保留。
3. facet 多选写入重复 query 参数。例如 `?market=US&market=DE`。
4. 结果计数显示“共 281 条（生产唯一端点口径），当前显示 50 条”。计数来自响应。
5. 行点击进入 `/capabilities/[id]`。
6. 键盘：↑/↓ 移动行焦点。Enter 打开。`/` 聚焦搜索框。
7. “加载更多”按钮保留焦点。追加结果后焦点回到第一行新增项。
8. 表头不提供排序。默认按任务匹配度排序。依据 PRD 5.2.3。
9. 不可执行条目默认不显示。显式“包含不可用”开关打开后显示，排最后，并标原因。

#### 验收判据

- 首屏 HTML 含至少 20 行结果。不得依赖客户端请求后才出现。
- 输入“德国吸乳器差评”，前 3 条包含评论类工具。
- 刷新页面后，搜索词、分类、facet、分页状态不丢。
- 三种空态文案不同。无权限不得显示为“没有结果”。
- 目录条目数等于可执行条目数加显式 `unsupported` 条目数。差集为 0。
- 幽灵端点为 0。判据：每个 `tool_id` 都能在 `tool_catalog` 找到对应行。
- 行高固定 56px。加载态不改变行高。

### 3.3 `/capabilities/[id]` 能力详情

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 面包屑 32px：能力目录 / {category} / {display_name}                  │
│ 头部 160px：H1 32/38 · 分类 · 市场 · 成本 · 健康 · 核验 · 风险       │
├──────────────────────────────────────────────┬───────────────────────┤
│ 主列 68%                                     │ 侧栏 320px 粘性        │
│ ┌──────────────────────────────────────────┐ │ ┌───────────────────┐ │
│ │ 参数表 320px（按 input_schema 渲染）     │ │ │ 调用方式          │ │
│ ├──────────────────────────────────────────┤ │ │ MCP / REST        │ │
│ │ 输出字段 240px                           │ │ │ CLI 未发布时隐藏  │ │
│ ├──────────────────────────────────────────┤ │ ├───────────────────┤ │
│ │ 真实示例 360px（请求 + 截断响应）        │ │ │ 相关工具          │ │
│ ├──────────────────────────────────────────┤ │ │ 替代方案          │ │
│ │ 内嵌 playbook 400px                      │ │ │ 上游依赖          │ │
│ │ 步骤 / 坑点 / 验收 / 风险边界            │ │ └───────────────────┘ │
│ └──────────────────────────────────────────┘ │                       │
└──────────────────────────────────────────────┴───────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 头部 | `GET /api/tools/{tool_id}`（new）。过渡期用 `GET /api/platform-packages/{platform_id}`（live） | `tool_id` 不存在时显示 404 页面 | 头部骨架 160px | 404 或 500 `StateBlock` |
| 参数表 | `input_schema`（new）。JSON Schema draft 2020-12 | “该工具未登记输入契约”。禁用复制与调用按钮 | 表格骨架 320px | 契约解析失败时显示错误与 schema 版本 |
| 输出字段 | `output_schema`（new） | “该工具未登记输出契约” | 表格骨架 240px | 同上 |
| 真实示例 | `GET /api/tools/{tool_id}`（new）的 `examples` 字段 | “暂无真实调用样例”。给“去工作台发起一次调用”链接 | 代码块骨架 360px | 显示“样例加载失败”。不伪造样例 |
| 内嵌 playbook | `GET /api/platform-packages/{platform_id}/playbook`（live） | “该平台没有 playbook” | Markdown 骨架 400px | 区块级错误与重试 |
| 相关工具 | `related_tool_ids`（new）。过渡期按 `category` 查询目录 | “没有同类工具” | 3 行骨架 | 隐藏区块 |
| 调用方式 | MCP 与 REST（live）。CLI 未发布时隐藏（new） | 不适用 | 不适用 | 不适用 |

#### 交互

1. 参数表按 schema 渲染。不得手写字段。每行显示名称、类型、必填、默认值、示例、说明。
2. 字段超过 20 个时，参数表顶部显示筛选输入框。筛选只影响显示。
3. 示例区显示 `run_id`。点击 `run_id` 跳 `/workbench/[taskId]?run={run_id}`。
4. 复制按钮复制完整命令。复制成功后显示 toast“已复制”。失败时显示错误。
5. MCP 调用复制 `tool_id` 与 `/mcp` 端点。REST 调用复制 `POST /api/quick-collect` 的请求体。CLI 只在产品 CLI 发布后显示。当前仓库没有产品 CLI 入口。不得显示不可用的 CLI 复制按钮。
6. 内嵌 playbook 使用锚点导航：步骤、坑点、验收、风险边界。
7. 页面不直接发起调用。调用从工作台发起。依据原则 3。
8. 键盘：Tab 顺序为头部 → 参数表 → 输出 → 示例 → playbook → 侧栏操作。

#### 验收判据

- 参数表完全由 `input_schema` 渲染。手写字段数为 0。
- 示例带真实 `run_id`。没有真实样例时显示空态。
- 头部六个字段齐全：名称、分类、覆盖市场、成本、健康度、最近核验。
- playbook 四个区块齐全，或显示明确空态。
- 复制 MCP 与 REST 两种调用方式均可用。剪贴板权限被拒绝时显示可手动复制的文本框。
- CLI 未发布时，页面不显示 CLI 复制入口。
- 页面关闭 JavaScript 后，头部、参数表、输出字段、playbook 仍可读。

### 3.4 `/workbench` 工作台首页

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 工作台页头 56px：项目切换 · 新建任务 · 调度状态                      │
├──────────────┬─────────────────────────────────┬─────────────────────┤
│ 左栏 280px   │ 中栏 minmax(480px, 1fr)         │ 右栏 360px          │
│ 项目列表     │ 任务表单 七槽位+派生           │ 门禁说明            │
│ 搜索 40px    │ 任务类型选择                    │ 成本口径            │
│ 任务行 72px  │ 模板快捷入口                    │ 证据等级图例        │
│ 底部 48px    │ 最近计划                        │ 空态提示            │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```

高度：页头 56px。三栏高度为 `calc(100dvh - 56px)`。三栏独立滚动。详见第 7 节。

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 项目列表 | `GET /api/projects`（live） | “还没有项目。创建第一个项目。” 给创建按钮 | 6 行 72px 骨架 | 左栏 `StateBlock` |
| 任务列表 | `GET /api/tasks?project_id=`（live） | “该项目还没有采集任务” | 6 行 72px 骨架 | 行内错误与重试 |
| 任务表单 | 静态字段 + `taxonomy/maternal_v1.json`（new） | 必填缺失时显示字段错误 | 提交按钮 spinner | 422 字段错误映射到表单 |
| 任务类型选择 | 规则加分类器（new）。置信度低于 0.7 时必须人工确认 | 未推断时显示“请选择任务类型” | 分类器 spinner | 显示“无法推断。请手动选择。” |
| 最近计划 | `POST /api/workbench/plans/preview`（new）。计划单属于工作台任务，不读项目级 `workflow-plans` | “暂无计划” | 3 行骨架 | 区块级错误 |
| 右栏门禁说明 | 静态。门禁名来自 Playbook 1.3 | 不适用 | 不适用 | 不适用 |

#### 交互

1. 选择项目后，左栏任务列表更新。URL 写入 `?project={id}`。
2. 新建任务表单字段固定为 PRD 2.3 的十个字段。七个槽位来自 Playbook 1.1。语言、负责人、任务类型是派生字段。第一屏显示品牌、品类、市场、决策问题。其余字段折叠在“更多设置”。
3. 提交表单后调用 `POST /api/workbench/plans/preview`（new）。请求体必须由七槽位适配为 `PlanningInput`。适配器是新建代码。现有 `PlanningInput` 见 `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py:141-200`。
4. preview 返回 `held` 时，页面显示“计划被门禁保持”。列出 `policy_gates` 与 `approval_reasons`。不得显示“开始执行”。
5. preview 返回可执行状态时，显示计划单与成本估算。批准按钮调用计划批准端点 `POST /api/workbench/plans/{plan_id}/approve`（new）。
6. 保存成功后跳 `/workbench/[taskId]`。
7. 模板快捷入口点击后预填表单。URL 写入 `?template=t1_voc`。
8. 键盘：Tab 顺序为项目列表 → 表单 → 右栏说明。`Cmd/Ctrl+Enter` 提交表单。

#### 验收判据

- 新用户不读文档，5 分钟内可提交第一份计划。
- 从 `/workbench` 到任务详情只改变 1 次路由。
- 表单缺任一必填项时，提交按钮禁用。字段级错误可见。
- preview 为 `held` 时，页面不显示可执行按钮。
- 每次 preview 显示请求 ID。失败时可复制请求 ID。
- 右栏门禁说明与 Playbook 1.3 的五个门禁名一致。

### 3.5 `/workbench/[taskId]` 任务详情

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 工作台页头 56px：← 工作台 · 任务标题 · 状态 · 中止 · 新建            │
├──────────────┬─────────────────────────────────┬─────────────────────┤
│ 左栏 280px   │ 中栏 minmax(480px, 1fr)         │ 右栏 360px          │
│ 任务列表     │ 对话消息流                      │ 证据 / 成本 / 门禁  │
│ 当前任务高亮 │ 计划单（可展开）                │ 三个 tab            │
│              │ 运行时间线                      │ 底部成本条 96px     │
│              │ 输入框 sticky 120px             │                     │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 任务标题与状态 | `GET /api/workbench/tasks/{task_id}`（new）与 `GET /api/runs/{run_id}`（new） | 任务不存在时 404 | 标题骨架 | 404 或 500 `StateBlock` |
| 对话消息流 | 任务事件（过渡期）。消息端点未在契约登记，暂不实现 | “还没有消息。输入决策问题开始。” | 3 条消息骨架 | 消息区错误条。保留已有消息 |
| 计划单 | preview 响应 + 保存的计划（live） | “计划尚未生成” | 计划骨架 360px | 区块级错误。可重试 preview |
| 运行时间线 | `GET /api/runs/{run_id}`（new）。不得调用 `/fixture-runs` | “尚未开始运行” | 步骤骨架 5 行 | 每个步骤显示 `failed` 与原因 |
| 输入框 | 消息端点未在契约登记，暂不实现。输入框保留，发送禁用 | 空输入时禁用发送 | 不适用 | 不适用 |
| 证据 tab | `GET /api/raw-records?task_run_id=`（live）；`GET /api/signals`（live）；claim 端点（new） | “本次运行还没有证据” | 证据行骨架 | tab 级错误 |
| 成本 tab | preview 的 `budget_summary`（live）；结算字段（new） | “成本尚未结算” | 成本卡骨架 | 显示“估算可用，结算不可用” |
| 门禁 tab | preview 的 `policy_gates`、`approval_reasons`（live） | “没有门禁记录” | 3 行骨架 | tab 级错误 |

#### 交互

1. 发送消息：`Cmd/Ctrl+Enter`。空输入不可发送。发送后消息立即出现在流末尾。
2. 对话流默认滚动到底部。用户向上滚动超过 80px 后，停止自动滚动。显示“有新消息”按钮。
3. 计划单可折叠。编辑来源行后，成本在 400ms 防抖后重算。重算期间批准按钮禁用。
4. 批准计划：调用保存或状态流转端点。成功后右栏门禁刷新。
5. 中止运行：打开确认对话框。确认后调用 `POST /api/runs/{run_id}/cancel`（new）。已完成步骤保留。状态显示“已中止”。
6. 右栏 tab 写入 `?panel=evidence&tab=cost`。刷新后保留。
7. 证据条目点击后打开抽屉。抽屉显示原始记录、来源、时间、证据等级。焦点陷阱生效。
8. 窄屏：右栏变为抽屉。左栏变为抽屉。详见第 7.7 节。
9. 键盘：`Esc` 关闭抽屉。`Alt+1/2/3` 聚焦左、中、右栏。不得覆盖浏览器快捷键。

#### 验收判据

- 页面不调用 `/api/projects/{id}/workflow-runs`。该路由已挂载，但为 fixture-only（生产返回 200，`execution_mode=fixture`）。真实运行走 `/api/runs`。
- 页面不显示“fixture”字样。
- 运行中的步骤 2 秒内更新一次状态。
- 中止后已完成步骤仍可见。中止状态有文字与时间。
- 计划编辑后成本重算。重算完成前批准按钮禁用。
- 右栏三个 tab 均可键盘操作。
- 页面在 1024px 宽度下无横向滚动。

### 3.6 `/reports` 报告中心

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 页头 72px：报告中心 H1 32/38 · 新建报告                             │
├──────────────────────────────────────────────────────────────────────┤
│ 筛选条 56px：任务类型 · 品牌 · 市场 · 时间 · 状态 · 搜索            │
├──────────────────────────────────────────────────────────────────────┤
│ 表头 44px：标题 30% | 结论句 30% | 最低证据等级 10% | 生成时间 12%   │
│              | 签收 10% | 操作 8%                                   │
│ 行 72px × N                                                          │
│ 空态 320px                                                           │
└──────────────────────────────────────────────────────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 筛选条 | `GET /api/reports` 扩展参数（new）：`template_id`、`brand`、`market`、`status`、`from`、`to`、`q` | 无报告时隐藏筛选，显示总空态 | 筛选器可用，表格骨架 | 筛选器保留。表格显示错误 |
| 报告表 | `GET /api/reports`（live）。当前只支持 `project_id`，见 `apps/api/src/data_intelligence_hub/api/routes/reports.py:54-61` | 三种空态：无报告、无权限、加载失败 | 8 行 72px 骨架 | `StateBlock` 与重试 |
| 行操作 | `GET /api/reports/{id}`（live）；导出与分享（new） | 不适用 | 行内 spinner | 行内错误 |
| 分页 | `GET /api/reports?page=`（new） | 不适用 | 按钮 spinner | 行内错误 |

字段缺口：

- 当前 `ReportResponse` 有 `title`、`content`、`status`、`period_start`、`period_end`、`created_at`。见 `apps/api/src/data_intelligence_hub/schemas/report.py:46-85`。
- 当前没有结论句、最低证据等级、签收状态。
- 结论句取 `report_contract.decision.answer`。
- 最低证据等级取 `claims[].evidence_grade` 的最小值。
- 签收状态取 `gates[]` 中 `G-Publish` 的状态。
- 合同不存在时，这三列显示“未生成合同”。不得从正文猜测。

#### 交互

1. 筛选变化写入 URL。刷新与返回保留。
2. 搜索防抖 250ms。搜索标题与结论句。不搜索正文全文。
3. 行点击进入 `/reports/[id]`。
4. 行操作：打开、导出、分享、复制结论。
5. 复制结论复制 `decision.answer` 与报告链接。不复制正文。
6. 导出默认 HTML。PDF 为第二选项。导出任务未完成时显示“生成中”并轮询。
7. 分享打开对话框。设置过期时间与访问范围。生成链接后写入审计事件。
8. 表格不提供排序。报告不是表格。依据 PRD 6.6。
9. 键盘：↑/↓ 移动行。Enter 打开。`Cmd/Ctrl+Enter` 复制结论。

#### 验收判据

- 每行显示：标题、结论句、最低证据等级、生成时间、签收状态。
- 合同缺失时，三列显示“未生成合同”。不得显示猜测值。
- 筛选状态刷新后不丢。
- 三种空态文案不同。
- 行高 72px。标题最多 2 行。超出截断。
- 导出与分享操作写入审计事件。

### 3.7 `/reports/[id]` 报告阅读页

本页的完整规格见第 6 节。这里只给页面级摘要。

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Reader 页头 56px：← 报告中心 · 标题 · 主题 · 打印 · 分享            │
├──────────────┬─────────────────────────────────┬─────────────────────┤
│ 锚点导航     │ 报告正文                        │ 证据栏 280px        │
│ 200px 粘性   │ minmax(0, 820px)                │ 粘性                │
│              │ 首屏决策区 280px                │ 证据分组            │
│              │ 11 章，每章 H2 结论句           │ 合同哈希            │
│              │ 每个 exhibit 六段式             │                     │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 报告头 | `GET /api/reports/{id}`（live）；`GET /api/reports/{id}/contract`（new） | 报告不存在时 404 | 标题与状态骨架 | 404 或 500 `StateBlock` |
| 首屏决策区 | `report_contract.decision`、`gates`、`claims`（new） | 合同缺失时显示“本合同未生成”。回退旧版 Markdown 阅读 | 首屏骨架 280px | 合同校验失败时显示错误与合同版本 |
| 章节正文 | `report_contract`（new）。旧版回退 `Report.content`（live） | “本章没有内容” | 段落骨架 | 章节级错误。保留其他章节 |
| exhibit | `report_contract.claims[]` 与 `metrics[]`（new） | 缺反证时不渲染。显示“合同校验失败” | 图表骨架固定高度 | 图表级错误。显示数据表 |
| 证据栏 | `GET /api/reports/{id}/evidence-references`（live）；`report_contract.evidences[]`（new） | “本报告没有可追溯证据” | 证据行骨架 | 证据栏错误。正文不受影响 |
| 审计 | `GET /api/reports/{id}/audit-events`（live） | “没有审计事件” | 时间线骨架 | 区块级错误 |
| SOP 视图 | `report_contract` 同一份数据（new） | “本合同没有 SOP 切片” | SOP 骨架 | 区块级错误 |

#### 交互

1. 章节锚点导航。滚动高亮。`aria-current="location"`。
2. 市场筛选。写入 `?market=US&market=DE`。
3. 人群或分群 tab。写入 `?segment=...`。
4. 证据抽屉。一次展开全部证据。
5. 明暗主题。主题写入 `data-theme` 与 `localStorage`。
6. 打印。使用专用打印样式。
7. 复制单条结论。复制结论句、claim ID、报告链接。
8. SOP 视图。`?view=sop`。同一份合同渲染第二份页面。
9. 不做排序。不做图表 tooltip。依据 PRD 6.6。

#### 验收判据

- 首屏三项分开显示：证据等级、门禁、claim 分布。
- 每个 exhibit 有六段。缺第 4 段时构建失败。
- 证据抽屉可一次展开全部证据。
- 打印输出 A4 无截断。
- 明暗主题切换后，正文对比度不低于 4.5:1。
- 复制结论只复制结论句、claim ID、链接。不复制整章。

### 3.8 `/reports/public/[id]` 报告分享页

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 分享页头 56px：品牌 · “只读分享” · 过期时间                          │
├──────────────────────────────────────────────────────────────────────┤
│ 内容宽 820px 居中                                                    │
│ 首屏决策区 280px                                                    │
│ 报告章节（按合同裁剪）                                               │
│ 页脚：合同哈希 · 访问审计说明 · 禁止输出清单                         │
└──────────────────────────────────────────────────────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 分享头 | `GET /api/reports/public/{token}`（new） | 不适用 | 标题骨架 | 404 链接无效；410 链接过期 |
| 报告正文 | `report_contract`（new） | “该分享没有正文” | 段落骨架 | 410 页面。显示过期时间与联系人 |
| 页脚 | `report_artifacts`（new） | 哈希缺失时显示“哈希未生成” | 不适用 | 不适用 |
| 访问审计 | `POST /api/reports/public/{token}/access`（new） | 不适用 | 不适用 | 静默失败。不阻断阅读 |

#### 交互

1. 无登录要求。不得读取登录 cookie。
2. 只读。不显示发送、编辑、内部跳转。
3. 证据只显示公开字段：来源、摘录、时间、证据等级。不显示原始记录 ID。
4. 打印可用。
5. 链接过期后显示 410 页面。页面给报告所有者联系方式。
6. 首次访问写入访问审计。重复访问按 token 去重到小时。

#### 验收判据

- 未登录可访问有效链接。
- 过期链接返回 410。撤销链接返回 404。
- 页面不显示内部导航、发送按钮、原始记录 ID。
- 每次访问写入审计事件。审计事件含时间、IP 哈希、user agent 哈希。
- 合同哈希在页脚可见。

### 3.9 `/connectors` 连接器与凭据

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 页头 72px：连接器 H1 32/38 · 环境状态（生产 / 演示）                 │
├──────────────┬─────────────────────────────────┬─────────────────────┤
│ 平台 rail    │ 端点与凭据列表                  │ 详情 360px          │
│ 240px 粘性   │ 1fr                             │ 可用性              │
│ 平台名 + 状态│ 行 64px：端点、状态、最近核验   │ 缺失配置            │
│              │                                 │ 凭据表单            │
└──────────────┴─────────────────────────────────┴─────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 环境状态 | `GET /api/health`（live）；`GET /api/settings/platform-credentials`（live） | 不适用 | 状态骨架 | 显示“状态未知” |
| 平台 rail | `GET /api/platform-packages`（live） | “没有平台包” | 8 行骨架 | rail 错误 |
| 端点列表 | `GET /api/platform-packages/providers/status`（live） | “该平台没有端点” | 8 行 64px 骨架 | 列表错误 |
| 可用性 | `EndpointAvailability`（live）。字段见 `apps/scraper-console/src/lib/api/platform-packages.ts:66-80` | “未测试” | 状态骨架 | 显示“可用性未知” |
| 凭据表单 | `GET /api/settings/platform-credentials`（live）；`PUT` 与 `DELETE`（live） | “尚未配置凭据” | 表单骨架 | 保存失败显示原因与请求 ID |
| 主密钥缺失 | 响应字段 `vault_write_enabled=false` | 显示“主密钥未配置。凭据写入关闭。” | 不适用 | 不适用 |

#### 交互

1. 平台点击后写入 `?platform=`。列表与详情更新。
2. 端点状态分为 `verified`、`config-gated`、`degraded`、`empty`、`untested`、`disabled`。每种状态有文字与图标。`degraded` 是 `health_status` 的取值，不是 `runs.status`；`runs.status` 只有 `queued`、`running`、`completed`、`failed`、`cancelled`。
3. API 值用 `config-gated`。运行结果用 `config_gated`。两者不混用。
3. 凭据表单只显示字段名与是否已配置。不回显密文。
4. 保存前显示确认对话框。对话框写明平台、字段、影响。
5. 删除凭据必须二次确认。确认对话框写明后果。
6. 项目级凭据未上线时，页面显示“项目级隔离未启用”。不得伪造项目选择器。
7. 键盘：平台 rail 支持 ↑/↓。Enter 选择。表单 Tab 顺序按字段顺序。

#### 验收判据

- 页面不显示任何明文密钥。DOM、日志、网络响应均不得出现密钥。
- 主密钥缺失时，保存按钮禁用。说明原因。
- 每个端点状态有文字、图标、`aria-label`。
- `config_gated` 与 `failed` 文案不同。`config_gated` 必须写“缺少配置”，不写“采集失败”。
- 保存成功后，可用性列表刷新。
- 删除操作有确认对话框与审计提示。

### 3.10 `/settings` 设置

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 页头 72px：设置 H1 32/38                                             │
├──────────────┬───────────────────────────────────────────────────────┤
│ 子导航 200px │ 内容 1fr，最大 960px                                  │
│ 成员         │ 区块 1 成员表：行 56px                                │
│ 角色         │ 区块 2 额度卡：3 列 × 120px                           │
│ 额度         │ 区块 3 审计日志：行 56px，筛选 48px                   │
│ 审计         │                                                       │
└──────────────┴───────────────────────────────────────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 当前用户 | `GET /api/auth/me`（live） | 未登录时打开登录对话框 | 骨架 | 401 打开登录对话框 |
| 成员表 | `GET /api/settings/members`（new） | “还没有成员” | 5 行骨架 | `StateBlock` |
| 角色 | 无。契约未登记角色端点，暂不实现 | “没有自定义角色” | 3 行骨架 | 区块错误 |
| 额度 | 无。契约未登记额度端点，暂不实现 | “额度未配置” | 3 张卡骨架 | 区块错误 |
| 审计日志 | `GET /api/settings/audit-events`（new） | “没有审计事件” | 时间线骨架 | 区块错误 |
| 系统状态 | `GET /api/tasks/scheduler/overview`（live） | 不适用 | 骨架 | 显示“调度状态未知” |

#### 交互

1. 子导航写入 `?section=members`。刷新保留。
2. 成员角色变更打开对话框。对话框写明成员、旧角色、新角色、影响。
3. 额度显示三种口径：估算、已发生、已结算。依据 PRD 5.6。
4. 审计日志按时间倒序。筛选时间、操作者、事件类型。
5. 危险操作必须二次确认。确认按钮使用危险色。
6. 键盘：子导航使用 tablist 模式。方向键切换。
7. 保存成功后显示 toast。失败保留表单值。

#### 验收判据

- 成员、角色、额度、审计四个区块齐全。
- 额度三种口径分开显示。不得合并成一个数字。
- 审计日志覆盖登录、角色变更、凭据变更、报告分享。
- 危险操作有确认对话框与后果说明。
- 未登录访问返回 401 并打开登录对话框。不得回退 demo workspace。当前回退逻辑见 `apps/api/src/data_intelligence_hub/api/deps.py:54-79`。

### 3.11 `/docs` 文档

#### 线框图

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 页头 72px：文档 H1 32/38 · 搜索 480×40                              │
├──────────────┬───────────────────────────────┬───────────────────────┤
│ 左导航 240px │ 正文 760px                    │ 本页目录 220px        │
│ 粘性         │ 16/1.66                       │ 粘性                  │
│ 5 组         │ 代码块可复制                  │ 当前节高亮            │
└──────────────┴───────────────────────────────┴───────────────────────┘
```

#### 区块清单

| 区块 | 数据来源 | 空态 | 加载态 | 错误态 |
|---|---|---|---|---|
| 左导航 | 静态 MDX 索引 | “没有匹配的文档” | 导航骨架 | 显示静态索引 |
| 正文 | 静态 MDX；`GET /api/collectors/docs`（live） | 页面不存在时 404 | 文章骨架 | 404 页面 |
| 本页目录 | 正文标题生成 | 标题少于 2 个时隐藏 | 不适用 | 不适用 |
| 搜索 | 静态索引（new） | “没有匹配结果” | 结果骨架 | 搜索不可用提示 |

#### 交互

1. 左导航分组：API 参考、数据源、报告规范、行业模板、证据与引用。
2. 文档页锚点稳定。标题变化时保留旧锚点别名。
3. 代码块右上角有复制按钮。复制内容不含行号。
4. 搜索按标题与正文匹配。结果高亮关键词。
5. 移动端左导航放入抽屉。本页目录折叠为顶部下拉。
6. 文档内的能力链接跳到 `/capabilities/[id]`。不复制能力内容。

#### 验收判据

- 五个分组齐全。
- 每个代码块可复制。
- 刷新后锚点不丢。
- 文档不加载外部字体。
- 移动端无横向滚动。
- 文档中的数字与生产探测一致。过期数字必须标注日期。

## 4. 组件清单

### 4.1 复用现有

下列组件已有生产页面或测试证据。可以直接复用。

| 组件 | 路径 | 证据 | 用途 |
|---|---|---|---|
| `AppShell` | `apps/scraper-console/src/components/layout/app-shell.tsx:16-52` | 13 个页面 import；`pnpm build` 通过；生产页面标 live | 6 条常规路由的壳 |
| `TopBar` | `apps/scraper-console/src/components/layout/top-bar.tsx:6-24` | 由 `AppShell` 引用；构建通过 | 页面标题与说明 |
| `StatTile` | `apps/scraper-console/src/components/ui/stat-tile.tsx:1-19` | dashboard、datasets、tools/tiktok 引用；`/dashboard` 生产标 live | KPI 卡 |
| `PlatformLogo` | `apps/scraper-console/src/components/platforms/platform-logo.tsx:7-33` | platforms、datasets、data-preview-drawer 引用；构建通过 | 平台字母徽标 |
| `ConfirmDialog` | `apps/scraper-console/src/components/ui/confirm-dialog.tsx:13-91` | `/datasets` 使用；生产标 live；构建通过 | 危险操作确认 |
| `useFocusTrap` | `apps/scraper-console/src/components/ui/use-focus-trap.ts:21-66` | `ConfirmDialog:33` 与 `DataPreviewDrawer:157` 使用 | 抽屉与对话框焦点 |
| `DataPreviewDrawer` | `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx:136-420` | `/datasets` 使用；生产标 live；`fetchDatasetVersions` 与 `fetchVersionPreview` 有真实端点 | 数据集预览 |
| `Providers` | `apps/scraper-console/src/components/providers.tsx:6-20` | 根布局挂载；构建通过 | TanStack Query |
| API 模块 | `apps/scraper-console/src/lib/api/*.ts` | 11 个模块对应已挂载路由；`pnpm test` 9/9 | 数据访问 |
| 设计 token | `apps/scraper-console/src/app/globals.css:4-112` | 构建通过；页面使用 | 颜色、间距、圆角、动效 |
| `cn` | `apps/scraper-console/src/lib/utils.ts:1-7` | 多组件引用 | 类名合并 |
| `canStartCollection` | `apps/scraper-console/src/lib/collection-policy.ts:6-8` | 单测见 `collection-policy.test.ts:1-13`；待复测 | 能力可用性判断 |

### 4.2 改造现有

| 组件 | 路径 | 缺口 | 改造内容 | 验证 |
|---|---|---|---|---|
| `Sidebar` | `apps/scraper-console/src/components/layout/sidebar.tsx:7-20` | 9 项旧导航；缺工作台、报告、连接器、设置 | 改为 4 项授权区导航 + 公开区入口 | 导航快照测试 |
| `AppShell` | `apps/scraper-console/src/components/layout/app-shell.tsx:16-52` | `max-w-7xl`；无操作槽；无跳转链接 | 增加 `actions` 槽、`skipLink`、`wide` 变体 | 构建 + 键盘测试 |
| `TopBar` | `apps/scraper-console/src/components/layout/top-bar.tsx:6-24` | 只有标题与说明 | 增加面包屑、状态、操作按钮 | 组件测试 |
| `apiFetch` | `apps/scraper-console/src/lib/api/client.ts:13-34` | 无超时、重试、AbortController、响应校验 | 增加 15 秒超时、2 次重试、AbortSignal、zod 校验钩子 | 单测 |
| `QuickCollectDrawer` | `apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx:24-735` | 162 个硬编码 endpoint_type；281 个生产端点；无 `useFocusTrap` | 改为 catalog 驱动；补焦点陷阱；删除失效键 | 覆盖 281 端点的快照测试 |
| `SkillsDirectory` | `apps/scraper-console/src/components/skills/skills-directory.tsx:78-181` | 平台包视图，不是工具视图 | 合并进能力目录；保留平台包筛选 | 生产回归 |
| `SkillDetail` | `apps/scraper-console/src/components/skills/skill-detail.tsx:15-232` | 平台详情，不是工具详情 | 抽取 playbook 区块到能力详情 | 生产回归 |
| `ReportDetailPanel` | `apps/web/src/components/reports/report-detail-panel.tsx:58-825` | 组件内直接 import API（`:24-31`）；83 处硬编码颜色；无单测 | 抽出 API；换 token；拆出 exhibit 渲染 | 迁移后组件测试 |
| `lib/api/reports.ts` | `apps/web/src/lib/api/reports.ts:1-384` | 属于 `apps/web`，鉴权与路径不同 | 移植到 `apps/scraper-console/src/lib/api/reports.ts` | 类型检查 |
| `collection-policy` | `apps/scraper-console/src/lib/collection-policy.ts:1-8` | 只判断状态与策略原因 | 增加健康度、证据等级判断 | 单测 |

### 4.3 新建

以下组件在仓库中不存在。必须新建。

| 组件 | 用途 | 使用路由 | 基础 |
|---|---|---|---|
| `ReaderShell` | 阅读壳。顶部 56px，无侧栏 | `/reports/[id]`、`/reports/public/[id]` | 新建 |
| `WorkbenchShell` | 三栏工作区壳 | `/workbench`、`/workbench/[taskId]` | 新建 |
| `CapabilityRow` | 目录行。固定 56px | `/capabilities` | 新建 |
| `CapabilityFilters` | 分类、市场、成本、健康度、核验 | `/capabilities` | shadcn `Select`、`Checkbox`、`Badge` |
| `SchemaTable` | 按 JSON Schema 渲染参数与输出 | `/capabilities/[id]` | 新建 |
| `CopyCommand` | MCP/REST 复制；CLI 未发布时隐藏 | `/capabilities/[id]` | shadcn `Button`、`Tooltip` |
| `PlanSheet` | 计划单。来源、排除、成本、等级 | `/workbench` | 新建 |
| `PlanSourceRow` | 计划来源行。可编辑、可排除 | `/workbench` | 新建 |
| `CostPanel` | 估算、已发生、已结算 | `/workbench` | `StatTile` 扩展 |
| `GateStatusBar` | 门禁状态条 | `/workbench`、`/reports/[id]` | 新建 |
| `RunTimeline` | 运行步骤时间线 | `/workbench/[taskId]` | 新建 |
| `EvidenceDrawer` | 证据抽屉。一次展开全部 | `/reports/[id]`、`/workbench/[taskId]` | shadcn `Sheet` + `useFocusTrap` |
| `EvidenceItem` | 证据条目。来源、摘录、等级 | 同上 | 新建 |
| `ExhibitBlock` | 六段式 exhibit | `/reports/[id]` | 新建 |
| `ExhibitChart` | CSS 图表。bar/heatmap/waterfall/matrix | `/reports/[id]` | 新建。不用图表库 |
| `ClaimBadge` | claim 状态徽章 | `/reports/[id]`、`/reports` | shadcn `Badge` |
| `EvidenceGradeBadge` | 证据等级徽章 | 同上 | shadcn `Badge` |
| `OutcomeBadge` | 运行结果四态 | `/workbench`、`/reports` | shadcn `Badge` |
| `AnchorNav` | 章节锚点导航 | `/reports/[id]`、`/docs` | 新建 |
| `ThemeToggle` | 明暗主题 | `/reports/[id]` | 新建 |
| `PrintButton` | 打印 | `/reports/[id]` | shadcn `Button` |
| `CopyClaimButton` | 复制单条结论 | `/reports/[id]` | shadcn `Button` |
| `ReportFilterBar` | 报告筛选 | `/reports` | shadcn `Select`、`Input` |
| `StateBlock` | 空、加载、错误、无权限四态 | 全部 | shadcn `Alert`、`Skeleton` |
| `DataTable` | 参数、成员、审计、报告表 | 多处 | shadcn `Table` |
| `Toast` | 复制、保存、错误提示 | 全部 | shadcn `Sonner` |
| `DocsNav` | 文档左导航 | `/docs` | 新建 |
| `DocsToc` | 文档本页目录 | `/docs` | 新建 |
| `PublicShareBanner` | 分享页只读与过期提示 | `/reports/public/[id]` | 新建 |

### 4.4 shadcn 组件映射

当前 `shadcn` 未安装。证据：

- `apps/scraper-console/components.json:7` 指向 `tailwind.config.ts`。该文件不存在。
- `apps/scraper-console/package.json:13-23` 没有 `@radix-ui/*`、`class-variance-authority`、`sonner`。
- `apps/scraper-console/src/components/ui` 只有 3 个手写文件。

接入前置：

1. 修改 `components.json`。Tailwind v4 使用 CSS-first 配置。把 `tailwind.config` 设为空字符串，或创建空配置文件。
2. 安装依赖：`@radix-ui/react-dialog`、`@radix-ui/react-tabs`、`@radix-ui/react-select`、`@radix-ui/react-tooltip`、`@radix-ui/react-dropdown-menu`、`@radix-ui/react-checkbox`、`@radix-ui/react-accordion`、`@radix-ui/react-popover`、`class-variance-authority`、`sonner`、`react-hook-form`、`@hookform/resolvers`。
3. 用 `pnpm dlx shadcn@latest add` 添加组件。组件放入 `src/components/ui`。
4. 不安装图表库。`package.json` 不得出现 `recharts`、`echarts`、`chart.js`、`d3`。

映射表：

| 新组件 | shadcn 基础 | 说明 |
|---|---|---|
| `Button`、`IconButton` | `button` | 主要、次要、危险三种 |
| `SearchInput` | `input` + `command` | 目录与文档搜索 |
| `FilterSelect` | `select`、`popover`、`command` | 单选与多选 |
| `MarketFilter` | `checkbox`、`badge` | 市场多选 |
| `Badge` | `badge` | claim、等级、状态 |
| `Tabs` | `tabs` | 右栏、报告分群 |
| `DataTable` | `table` | 参数、报告、成员、审计 |
| `EvidenceDrawer` | `sheet` | 右侧抽屉 |
| `ConfirmDialog` | `dialog` | 中止、删除 |
| `FaqAccordion` | `accordion` | 首页、文档 |
| `Tooltip` | `tooltip` | 枚举解释 |
| `Breadcrumb` | `breadcrumb` | 详情页 |
| `Skeleton` | `skeleton` | 固定尺寸加载 |
| `Alert` | `alert` | 区块错误 |
| `Progress` | `progress` | 运行进度 |
| `ScrollArea` | `scroll-area` | 三栏滚动 |
| `Toast` | `sonner` | 复制、保存 |
| `PlanForm` | `form` + `react-hook-form` + `zod` | 任务表单（七槽位 + 派生字段） |
| `RowMenu` | `dropdown-menu` | 行操作 |

### 4.5 不得复用

| 资产 | 路径 | 原因 |
|---|---|---|
| `ReportsWorkspace` | `apps/web/src/components/reports/reports-workspace.tsx:61-1382` | 页面级工作区；手写 `useEffect`；148 处硬编码颜色；与控制台 token 不一致。必须按新页面拆分重写 |
| `ReportDetailPageWorkspace` | `apps/web/src/components/reports/report-detail-page-workspace.tsx:10-76` | 薄壳；依赖旧 API 与 `next/link`。重写成本低于迁移 |
| `/settings/account` | `apps/scraper-console/src/app/settings/account/page.tsx:3-14` | 死页。无 API。必须删除 |
| `workflow_execution` fixture 路径 | `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py:170` | 已挂载的 fixture-only 路由（生产返回 200，`execution_mode=fixture`）。不得用它承载真实执行；UI 不提供真实运行入口 |
| `QuickCollectDrawer` 现状 | `apps/scraper-console/src/components/platforms/quick-collect-drawer.tsx:24-735` | 162 个硬编码端点，生产有 281 个。直接复用会产生空参数提交 |
| 未使用的 API 导出 | `apps/scraper-console/src/lib/api/*.ts` | `fetchTikTokTools`、`fetchTaskRuns`、`archiveProject`、`fetchExportJob` 在 `src` 内调用数为 0。删除前必须确认无动态调用 |

## 5. 设计 token

### 5.1 token 结构

现有 `globals.css` 有两套词族：

- 语义词族：`--surface-*`、`--text-*`、`--action-*`、`--border-*`。约 757 处引用。
- 旧词族：`--fg-1`、`--bg-1`、`--accent-1`。约 26 处引用。

规则：

- 新组件只使用语义词族。
- 旧词族保留为别名层。不得一次性删除。
- 新增 token 必须加在 `:root` 与 `[data-theme="dark"]` 两处。
- 组件不得写十六进制颜色。图表色用 `var(--chart-*)`。

### 5.2 颜色 token

下表给出本规格的目标值。现有值见 `apps/scraper-console/src/app/globals.css:4-112`。

| token | 亮色 | 暗色 | 用途 |
|---|---|---|---|
| `--surface-canvas` | `#f7f2ed` | `#161211` | 页面底色 |
| `--surface-primary` | `#ffffff` | `#1f1a19` | 面板 |
| `--surface-secondary` | `#fffdfb` | `#26201e` | 次级面板 |
| `--surface-muted` | `#f4ece7` | `#2c2523` | 弱背景 |
| `--surface-inset` | `#efe6df` | `#120f0e` | 内嵌区 |
| `--text-primary` | `#241b1b` | `#f5efea` | 正文 |
| `--text-secondary` | `#5b5050` | `#c9beb8` | 次要文字 |
| `--text-tertiary` | `#786d6a` | `#a69a94` | 元数据 |
| `--text-inverse` | `#ffffff` | `#161211` | 反色文字 |
| `--border-subtle` | `#ded3cc` | `#3a302d` | 细边框 |
| `--border-strong` | `#c9b8af` | `#564843` | 强边框 |
| `--action-primary` | `#9b4355` | `#e39aa8` | 主操作 |
| `--action-primary-hover` | `#823747` | `#edb2bd` | 悬停 |
| `--action-primary-pressed` | `#6f2f3d` | `#c97f8e` | 按下 |
| `--action-soft` | `#f8e6e2` | `#3a252a` | 主操作浅底 |
| `--state-info` | `#284e7a` | `#8fb6d0` | 信息 |
| `--state-success` | `#287a45` | `#7fc9a3` | 成功 |
| `--state-warning` | `#87611b` | `#d9b36c` | 警告 |
| `--state-danger` | `#a04437` | `#e29a91` | 危险 |
| `--claim-confirmed` | `#2f6b4f` | `#7fc9a3` | claim 确认 |
| `--claim-directional` | `#45687d` | `#8fb6d0` | claim 方向性 |
| `--claim-hypothesis` | `#756078` | `#c3a8c8` | claim 假设 |
| `--claim-gap` | `#8a6a2f` | `#d9b36c` | 证据缺口 |
| `--claim-blocked` | `#a5534b` | `#e29a91` | 门禁阻断 |
| `--claim-unknown` | `#6f6862` | `#b3a8a2` | 未知 |
| `--chart-positive` | `#3f6b57` | `#7fc9a3` | 正向 |
| `--chart-negative` | `#a5534b` | `#e29a91` | 负向 |
| `--chart-candidate` | `#45687d` | `#8fb6d0` | 候选 |
| `--chart-qual` | `#756078` | `#c3a8c8` | 定性 |
| `--chart-unknown` | `#8a827d` | `#b3a8a2` | 未知填充 |
| `--chart-grid` | `#ded7d1` | `#3a302d` | 网格线 |
| `--report-paper` | `#fbfaf8` | `#1a1615` | 报告纸色 |
| `--report-ink` | `#252321` | `#f5efea` | 报告正文 |
| `--report-ink-2` | `#625c58` | `#c9beb8` | 报告次要文字 |
| `--report-line` | `#e3ddd8` | `#3a302d` | 报告分隔线 |

对比度规则：

- `--text-tertiary` 在亮色画布上的对比度为 4.50:1。只用于 12px 及以上文字。不得用于关键结论。
- `--chart-unknown` 在白色上的对比度为 3.77:1。只用于图形填充。不得用作文字颜色。
- 主操作按钮：白字在 `#9b4355` 上为 6.31:1。暗色按钮：`#161211` 字在 `#e39aa8` 上为 8.38:1。
- 五个 claim 颜色在白色上的对比度为 5.02:1 至 6.29:1。均满足正文要求。

### 5.3 字体 token

| token | 值 | 用途 |
|---|---|---|
| `--font-sans` | 现有系统栈，`globals.css:33-37` | 全部界面 |
| `--font-mono` | 现有等宽栈，`globals.css:38-39` | ID、哈希、代码 |
| `--text-display` | 56px / 62px，600 | 首页主标题 |
| `--text-h1` | 40px / 46px，600 | 公开区区块标题 |
| `--text-h2` | 32px / 38px，600 | 控制台页面标题 |
| `--text-h3` | 24px / 30px，600 | 报告章节标题 |
| `--text-h4` | 18px / 24px，600 | 面板标题 |
| `--text-body` | 14px / 22px，400 | 控制台正文 |
| `--text-report` | 16px / 1.66，400 | 报告正文 |
| `--text-label` | 13px / 18px，500 | 字段与状态 |
| `--text-meta` | 12px / 17px，400 | 时间、来源、ID |
| `--text-micro` | 11px / 14px，600，字距 0.08em | 图表标签 |

规则：

- 中文标题不使用全大写。英文枚举可以使用大写。
- 标题字距最大 -1px。首页主标题可用 -1.5px。
- 数字使用 `font-variant-numeric: tabular-nums`。
- 不使用外部字体。不加载 `next/font`。

### 5.4 间距、圆角、阴影

| token 组 | 值 | 用途 |
|---|---|---|
| 间距 | 4、8、12、16、24、32、48、64、96、120px | 基准 4px |
| `--radius-1` | 4px | 标签、输入 |
| `--radius-2` | 8px | 按钮、行 |
| `--radius-3` | 12px | 卡片、面板 |
| `--radius-4` | 16px | 抽屉、对话框 |
| `--radius-pill` | 999px | 状态、筛选 |
| `--shadow-raised` | `0 1px 2px rgb(36 27 27 / 6%)` | 抬升面板 |
| `--shadow-overlay` | `0 18px 48px rgb(46 32 28 / 18%)` | 抽屉、对话框 |
| `--shadow-report` | `0 1px 2px rgb(36 27 27 / 5%), 0 12px 32px rgb(36 27 27 / 6%)` | 报告纸 |
| `--sidebar-width` | 17rem | 侧栏 |
| `--topbar-height` | 4.5rem | 控制台页头 |
| `--reader-topbar-height` | 3.5rem | 阅读页头 |
| `--workbench-topbar-height` | 3.5rem | 工作台页头 |

### 5.5 与现有 `globals.css` 的差异

| token | 现状 | 本规格 | 处置 |
|---|---|---|---|
| `--surface-canvas` | `#f7f2ed`，`:10,62` | 保持 | keep |
| `--surface-primary` | `#ffffff`，`:11,63` | 保持 | keep |
| `--surface-muted` | `#f4ece7`，`:13,65` | 保持 | keep |
| `--surface-inset` | 不存在 | `#efe6df` / `#120f0e` | add |
| `--text-primary` | `#241b1b`，`:6,66` | 保持 | keep |
| `--text-secondary` | `#5b5050`，`:7,67` | 保持 | keep |
| `--text-tertiary` | `#786d6a`，`:8,68` | 保持。增加使用限制 | keep |
| `--action-primary` | `#9b4355`，`:15,72` | 保持 | keep |
| `--border-subtle` | `#ded3cc`，`:27,70` | 保持 | keep |
| 暗色主题 | 只有 `:root` 与 `[data-theme="light"]`，`:4-5` | 新增 `[data-theme="dark"]` 块 | add |
| claim 颜色 | 不存在 | 5 个 | add |
| chart 颜色 | 不存在 | 6 个 | add |
| 报告纸色 | 不存在 | 4 个 | add |
| `--shadow-raised` | 不存在 | 新增 | add |
| `--shadow-overlay` | 存在，`:80` | 保持 | keep |
| `--radius-1..4` | 存在，`:47-51` | 保持 | keep |
| `--duration-*` | 存在，`:56-58` | 保持 | keep |
| `prefers-reduced-motion` | 存在，`:114-120` | 保持。新组件必须使用 token | keep |
| shadcn 变量 | 存在，`:82-111` | 保持。暗色主题补一份 | extend |
| 旧词族 | 存在，`:6-31` | 保留为别名层 | keep |
| `body` 字号 | 14px / 1.55，`:126-134` | 控制台保持。报告覆盖 16px / 1.66 | extend |

迁移规则：

- 新组件不得引用 `--fg-*`、`--bg-*`、`--accent-1`。
- 修改旧组件时，顺手把颜色换成语义词族。
- 双词族清理不阻塞本批。

## 6. 报告阅读页详细规格

### 6.1 阅读壳与网格

参考视口 1440×900。阅读壳总宽 1348px。页面外边距 24px。

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ ReaderTopBar 56px：← 报告中心 · 标题（截断） · 主题 · 打印 · 分享          │
├──────────────┬──────────────────────────────────────────┬──────────────────┤
│ AnchorNav    │ ReportBody                               │ EvidenceRail     │
│ 200px        │ minmax(0, 820px)                        │ 280px            │
│ sticky top   │ 章节 × 11（T1；其余模板按合同裁剪）      │ sticky top       │
│ 72px         │ 首屏 280px + 章节                         │ 72px             │
│              │ 阅读进度条 2px                            │                  │
└──────────────┴──────────────────────────────────────────┴──────────────────┘
```

CSS：

```css
.reader-shell {
  --reader-topbar: 3.5rem;
  --anchor-width: 12.5rem;
  --rail-width: 17.5rem;
  --report-width: 51.25rem;
  display: grid;
  grid-template-columns: var(--anchor-width) minmax(0, var(--report-width)) var(--rail-width);
  gap: 1.5rem;
  max-width: 84.25rem;
  margin-inline: auto;
  padding-inline: 1.5rem;
}
```

规则：

- 三列顶部对齐。锚点导航与证据栏使用 `position: sticky; top: calc(var(--reader-topbar) + 1rem); max-height: calc(100dvh - var(--reader-topbar) - 2rem); overflow-y: auto;`。
- 正文列不设固定高度。滚动由页面承担。
- 阅读进度条固定在页头下方 2px。宽度按已读章节计算。

### 6.2 首屏决策区

首屏必须在 5 秒内回答三个问题：结论是什么、证据够不够硬、门禁到哪一步。

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 模板徽章 T1 VOC · 报告标题 H1 40/46                                  │ 96px
│ 决策问题 16/26                                                       │ 40px
│ 决策句 24/34，最多 3 行                                              │ 96px
├──────────────────────────────────────────────────────────────────────┤
│ KPI 卡 1 120px │ KPI 卡 2 120px │ KPI 卡 3 120px                     │ 120px
├──────────────────────────────────────────────────────────────────────┤
│ 证据等级 最低 L3_live_single                                         │ 28px
│ 门禁 G7 PENDING                                                      │ 28px
│ claim 分布 confirmed 2 · directional 5 · hypothesis 3 · gap 1 · blocked 1 │ 28px
└──────────────────────────────────────────────────────────────────────┘
```

DOM：

```html
<header class="report-head">
  <p class="report-head__template"><span class="badge">T1 VOC</span></p>
  <h1 class="report-head__title">德国可穿戴吸乳器新品 VOC</h1>
  <p class="report-head__question">Fit 与支撑，哪个是主要摩擦？</p>
  <p class="report-head__answer">Fit 是主要摩擦；支撑问题集中在夜间使用场景。</p>
</header>

<section class="report-kpis" aria-label="关键数字">
  <div class="stat-tile"><p class="stat-tile__label">帧成员</p><p class="stat-tile__value">68</p><p class="stat-tile__hint">规范记录 74</p></div>
  <div class="stat-tile"><p class="stat-tile__label">负向标注占比</p><p class="stat-tile__value">41%</p><p class="stat-tile__hint">分母 68</p></div>
  <div class="stat-tile"><p class="stat-tile__label">覆盖市场</p><p class="stat-tile__value">2</p><p class="stat-tile__hint">DE / US</p></div>
</section>

<section class="report-status" aria-label="证据与门禁状态">
  <p class="report-status__row" data-testid="grade-line">
    <span class="report-status__key">证据等级</span>
    <span class="report-status__value">最低 L3_live_single</span>
  </p>
  <p class="report-status__row" data-testid="gate-line">
    <span class="report-status__key">门禁</span>
    <span class="report-status__value">G7 PENDING</span>
  </p>
  <p class="report-status__row" data-testid="claim-line">
    <span class="report-status__key">claim 分布</span>
    <span class="report-status__value">confirmed 2 · directional 5 · hypothesis 3 · gap 1 · blocked 1</span>
  </p>
</section>
```

规则：

- 三行必须是三个独立节点。不得合并。
- 证据等级使用 `EvidenceGradeBadge`。
- 门禁使用 `GateStatusBar`。五态：`pending`、`pass`、`fail`、`blocked`、`expired`。`expired` 表示授权过期导致门禁失效，文案为“授权已过期，门禁失效”，并给“重新授权”入口。不得把它显示为 `blocked` 或 `fail`。
- claim 分布使用五个 `ClaimBadge`。零值也显示。
- 首屏不显示“综合可信度”。
- 首屏必须有“禁止输出”链接。点击跳到文末清单。

文末禁止输出清单至少包含七条。依据 PRD 7.4：

1. 不推断销量、份额、营收。
2. 不把评论方向性证据写成总体比例。
3. 不做医疗结论。健康类表述必须标“非医疗建议”。
4. 不把社媒声称当作自然消费者口碑。
5. 不把不同样本来源的计数相减或相加。
6. 不把定性优先级热力图当作量化评分。
7. 不在证据等级不足时给单一结论。

清单由模板注册表提供。页面不得手写。见 PRD 8.6 的 `prohibited_outputs`。

### 6.3 六段式 exhibit

#### 6.3.1 DOM 结构

每个 exhibit 必须渲染六段。第 4 段是硬要求。第 5 段可选。

```html
<article
  class="exhibit"
  data-exhibit-id="ex_014"
  data-claim-id="clm_014"
  data-claim-status="directional"
  data-evidence-grade="L3_live_single"
  data-exhibit-type="bar"
>
  <!-- 段 1：结论图题 -->
  <h3 class="exhibit__title">
    24 条舒适或外观正向记录中，14 条仍出现支撑、适配或稳定性问题
  </h3>

  <!-- 段 2：scope + 徽章 -->
  <p class="exhibit__scope">
    <span class="badge">样本 68</span>
    <span class="badge">窗口 2026-06-20 — 2026-09-20</span>
    <span class="badge badge--grade" data-grade="L3_live_single">L3 · 单次真实调用</span>
    <span class="badge badge--gate" data-gate="pending">G7 PENDING</span>
  </p>

  <!-- 段 3：图表 -->
  <figure class="exhibit__figure">
    <div
      class="chart chart--bar"
      role="img"
      aria-label="Fit 负向 62，支撑负向 58，噪声负向 31，清洁负向 24"
    >
      <div class="chart__row">
        <span class="chart__label">Fit</span>
        <span class="chart__track"><span class="chart__bar chart__bar--negative" style="--v:62"></span></span>
        <span class="chart__value">62</span>
      </div>
      <div class="chart__row">
        <span class="chart__label">支撑</span>
        <span class="chart__track"><span class="chart__bar chart__bar--negative" style="--v:58"></span></span>
        <span class="chart__value">58</span>
      </div>
    </div>
    <figcaption class="exhibit__caption">图 1 · 各维度负向标注数。分母为帧成员 68。</figcaption>
    <details class="exhibit__data">
      <summary>数据表</summary>
      <table>
        <caption>图 1 数据</caption>
        <thead><tr><th scope="col">维度</th><th scope="col">负向标注</th></tr></thead>
        <tbody><tr><th scope="row">Fit</th><td>62</td></tr></tbody>
      </table>
    </details>
  </figure>

  <!-- 段 4：三段读图。Counterevidence 必填 -->
  <div class="exhibit__read">
    <section class="read-block" data-read="interpretation">
      <h4 class="read-block__title">Interpretation</h4>
      <p>Fit 负向标注集中在“错位”和“漏液”两个词。</p>
    </section>
    <section class="read-block" data-read="counterevidence">
      <h4 class="read-block__title">Counterevidence</h4>
      <p>4 条记录同时写明“调整后贴合”。未发现支撑问题。</p>
    </section>
    <section class="read-block" data-read="decision">
      <h4 class="read-block__title">Decision</h4>
      <p>先改肩带与杯口结构。把夜间使用作为验证场景。</p>
    </section>
  </div>

  <!-- 段 5：人声。可选 -->
  <blockquote class="exhibit__voice">
    <p>“白天能穿，晚上侧躺会漏。”</p>
    <footer>人工释义，不是原文引语 · 记录 <code>g4_7f02</code></footer>
  </blockquote>

  <!-- 段 6：来源脚注 + 证据抽屉 -->
  <footer class="exhibit__foot">
    <dl class="exhibit__meta">
      <div><dt>Basis</dt><dd>Amazon.de 评论</dd></div>
      <div><dt>Unit</dt><dd>帧成员</dd></div>
      <div><dt>Limit</dt><dd>不含 TikTok 评论</dd></div>
      <div><dt>Status</dt><dd>Directional · 未过 G7</dd></div>
    </dl>
    <button class="exhibit__evidence-trigger" aria-expanded="false" aria-controls="ev-ex-014">
      证据 12
    </button>
    <div class="exhibit__evidence" id="ev-ex-014" hidden>
      <!-- EvidenceDrawer 的内容。一次展开全部证据。 -->
    </div>
    <div class="exhibit__evidence-print">
      <!-- 打印专用证据表。渲染器始终输出。屏幕隐藏，打印显示。 -->
      <table>
        <caption>证据 12 条</caption>
        <thead><tr><th scope="col">角色</th><th scope="col">来源</th><th scope="col">摘录</th></tr></thead>
        <tbody><tr><td>support</td><td>Amazon.de</td><td>“白天贴合。”</td></tr></tbody>
      </table>
    </div>
    <p class="exhibit__hash">contract sha256 · <code>af5607158f0970ed</code></p>
  </footer>
</article>
```

渲染前置校验：

1. `claim_status` 必须是五态之一。未知值构建失败。
2. `evidence_grade` 必须是五级之一。未知值构建失败。
3. `counterevidence_text` 必须存在且非空。缺失时构建失败。
4. `evidence_ids` 至少 1 条。缺失时构建失败。
5. 第 6 段的 `Basis`、`Unit`、`Limit`、`Status` 四项必须存在。缺一项构建失败。

禁止：

- 不得用 CSS 隐藏缺失的第 4 段。
- 不得把 `Counterevidence` 放进 tooltip。
- 不得在图表上挂 tooltip。依据 PRD 6.6。

#### 6.3.2 CSS 实现

全局：

```css
.report-body {
  max-width: 51.25rem;
  font-size: 1rem;
  line-height: 1.66;
  color: var(--report-ink);
  background: var(--report-paper);
}

.exhibit {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  padding-block: 2rem;
  border-top: 1px solid var(--report-line);
}

.exhibit__title {
  font-size: 1.5rem;
  line-height: 1.25;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.exhibit__scope {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--report-ink-2);
}

.exhibit__read {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.read-block {
  padding: 1rem;
  border: 1px solid var(--report-line);
  border-radius: var(--radius-3);
  background: var(--surface-primary);
}

.read-block[data-read="counterevidence"] {
  border-left: 3px solid var(--claim-gap);
  background: var(--surface-muted);
}

.exhibit__evidence-print {
  display: none;
}

.read-block__title {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--report-ink-2);
}
```

条形图：

```css
.chart--bar {
  display: grid;
  gap: 0.5rem;
}

.chart__row {
  display: grid;
  grid-template-columns: minmax(6rem, 8.75rem) minmax(0, 1fr) 3rem;
  align-items: center;
  gap: 0.75rem;
}

.chart__track {
  position: relative;
  height: 0.75rem;
  overflow: hidden;
  border-radius: var(--radius-pill);
  background: var(--chart-grid);
}

.chart__bar {
  display: block;
  width: calc(var(--v) * 1%);
  height: 100%;
  border-radius: inherit;
  background: var(--chart-candidate);
}

.chart__bar--negative { background: var(--chart-negative); }
.chart__bar--positive { background: var(--chart-positive); }
.chart__value { font-variant-numeric: tabular-nums; text-align: right; }
```

热力图：

```css
.chart--heat {
  display: grid;
  grid-template-columns: minmax(7rem, 9rem) repeat(var(--cols, 5), minmax(2rem, 1fr));
  gap: 2px;
}

.chart--heat [role="rowheader"] {
  display: flex;
  align-items: center;
  padding-right: 0.5rem;
  font-size: 0.75rem;
  color: var(--report-ink-2);
}

.chart--heat [data-level="0"] { background: var(--surface-muted); }
.chart--heat [data-level="1"] { background: color-mix(in srgb, var(--chart-candidate) 18%, var(--surface-primary)); }
.chart--heat [data-level="2"] { background: color-mix(in srgb, var(--chart-candidate) 36%, var(--surface-primary)); }
.chart--heat [data-level="3"] { background: color-mix(in srgb, var(--chart-candidate) 54%, var(--surface-primary)); }
.chart--heat [data-level="4"] { background: color-mix(in srgb, var(--chart-candidate) 72%, var(--surface-primary)); }
```

热力图每个单元格必须显示数值。不得只靠颜色。

瀑布图：

```css
.chart--waterfall {
  display: flex;
  align-items: flex-end;
  gap: 0.25rem;
  min-height: 14rem;
  padding-block: 1rem;
  border-bottom: 1px solid var(--chart-grid);
}

.chart--waterfall .chart__column {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
}

.chart--waterfall .chart__fill {
  width: 100%;
  height: calc(var(--v) * 1%);
  background: var(--chart-candidate);
}
```

矩阵：

```css
.chart--matrix {
  display: grid;
  grid-template-columns: minmax(8rem, 10rem) repeat(var(--cols, 3), minmax(0, 1fr));
  border-top: 1px solid var(--chart-grid);
  border-left: 1px solid var(--chart-grid);
}

.chart--matrix > * {
  padding: 0.5rem;
  border-right: 1px solid var(--chart-grid);
  border-bottom: 1px solid var(--chart-grid);
}
```

共同规则：

- 图表容器高度固定。数据加载后不改变高度。
- 不使用 SVG、Canvas、WebGL。
- 不引入图表库。
- 每个图表必须有 `role="img"` 与 `aria-label`。
- 每个图表必须有一个可展开的数据表。数据表是文本替代。
- 数值使用 `tabular-nums`。
- 图表不使用渐变。颜色只表达语义。

#### 6.3.3 响应式断点

| 断点 | 正文宽 | 锚点导航 | 证据栏 | 三段读图 | 图表 |
|---|---|---|---|---|---|
| ≥1440px | 820px | 左栏 200px | 右栏 280px | 3 列 | 全宽 |
| 1200–1439px | 760px | 左栏 200px | 抽屉 | 3 列 | 全宽 |
| 1024–1199px | 720px | 左栏 200px | 抽屉 | 3 列 | 全宽 |
| 768–1023px | 流式 | 顶部横向 chip 条 | 抽屉 | 1 列 | 全宽 |
| 480–767px | 流式 | 顶部横向 chip 条 | 抽屉 | 1 列 | 标签在条形上方 |
| <480px | 流式 | 隐藏。目录放入抽屉 | 抽屉 | 1 列 | 矩阵横向滚动 |

规则：

- 1200px 以下，证据栏变为右侧抽屉。页头出现“证据”按钮。
- 1024px 以下，锚点导航变为横向 chip 条。`overflow-x: auto`。当前章节自动滚入视野。
- 768px 以下，三段读图改为单列。`Counterevidence` 仍必须在 `Interpretation` 之后、`Decision` 之前。
- 480px 以下，条形图标签移到条形上方。每行两行布局。
- 矩阵在 480px 以下允许横向滚动。第一列固定。滚动容器必须有 `aria-label`。

#### 6.3.4 打印样式

```css
@page {
  size: A4;
  margin: 14mm 12mm 16mm;
}

@media print {
  :root {
    --report-paper: #ffffff;
    --report-ink: #000000;
    --report-ink-2: #333333;
    --report-line: #999999;
  }

  .reader-topbar,
  .anchor-nav,
  .evidence-rail,
  .reader-actions,
  .theme-toggle,
  .print-button,
  .copy-claim,
  .exhibit__evidence-trigger {
    display: none !important;
  }

  .reader-shell {
    display: block;
    max-width: none;
    padding: 0;
  }

  .report-body {
    max-width: none;
    font-size: 11pt;
    line-height: 1.5;
  }

  .exhibit {
    break-inside: avoid;
    page-break-inside: avoid;
    border-top: 1px solid #999;
  }

  .exhibit__read {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6mm;
  }

  .exhibit__voice {
    break-inside: avoid;
  }

  /* details 的 open 状态不能由 CSS 强制。渲染器必须始终输出打印用证据表。 */
  .exhibit__evidence-print {
    display: block !important;
  }

  .exhibit__evidence,
  .exhibit__data {
    display: none !important;
  }

  a[href^="http"]::after {
    content: " (" attr(href) ")";
    font-size: 8pt;
    word-break: break-all;
  }

  h1, h2, h3, h4 {
    break-after: avoid;
    page-break-after: avoid;
  }

  .chart__bar,
  .chart__fill,
  .chart--heat [data-level] {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
```

打印规则：

1. 打印用证据表必须由渲染器始终输出。`<details>` 的展开状态不能由 CSS 控制。
2. 每个 exhibit 不跨页。单条 exhibit 超过一页时，允许内部跨页，但标题与第 4 段必须同页。
3. 页脚输出合同哈希与报告标题。
4. 打印强制亮色。不打印主题切换按钮。
5. 链接打印完整 URL。内部锚点不打印 URL。
6. 图表颜色在灰度打印下仍可区分。每个图表有数值标签与数据表。
7. 打印不输出证据抽屉的交互控件。只输出证据表。

### 6.4 claim 状态与证据等级

#### 6.4.1 两套层级，不混用

| 层级 | 回答的问题 | 取值 |
|---|---|---|
| 证据等级 | 数据有多可复核 | `L0_unverified`、`L1_contract`、`L2_fixture_local`、`L3_live_single`、`L4_authorized_live` |
| claim 状态 | 这句结论能说到多强 | `confirmed`、`directional`、`hypothesis`、`evidence_gap`、`blocked` |

等级决定 claim 上限。依据 PRD 7.3。

| 证据等级 | 允许的最高 claim |
|---|---|
| `L0_unverified` | 不生成 claim |
| `L1_contract` | 不生成 claim |
| `L2_fixture_local` | `hypothesis` |
| `L3_live_single` | `directional` |
| `L4_authorized_live` | `confirmed` |

#### 6.4.2 显示规则

| 状态 | 中文标签 | 颜色 token | 图标 | 允许词 | 禁止词 |
|---|---|---|---|---|---|
| `confirmed` | 已确认 | `--claim-confirmed` | 勾 | 确认、显示、达到 | — |
| `directional` | 方向性 | `--claim-directional` | 箭头 | 方向性支持、迹象表明 | 证明、必然 |
| `hypothesis` | 假设 | `--claim-hypothesis` | 问号 | 假设、待验证 | 显示、达到 |
| `evidence_gap` | 证据缺口 | `--claim-gap` | 缺口 | 未覆盖、样本不足 | 任何结论性表述 |
| `blocked` | 门禁阻断 | `--claim-blocked` | 锁 | 门禁未解除、不可推断 | 任何结论性表述 |

规则：

- `evidence_gap` 与 `blocked` 是结果状态。它们必须出现在报告里。不得当作失败隐藏。
- claim 徽章显示中文标签。`title` 与 `aria-label` 显示英文枚举。
- 证据等级徽章显示等级与全称。例如 `L3 · 单次真实调用`。
- 报告首屏的 claim 分布必须包含零值。
- 禁用词检查在渲染器执行。命中时构建失败。

### 6.5 交互规格

#### 6.5.1 章节锚点导航

```html
<nav class="anchor-nav" aria-label="报告章节">
  <ol>
    <li><a href="#ch-00" aria-current="location">00 执行结论</a></li>
    <li><a href="#ch-01">01 核心矛盾</a></li>
  </ol>
</nav>
```

规则：

- 锚点来自合同章节 ID。不得手写。
- 滚动时使用 `IntersectionObserver` 更新 `aria-current`。
- 点击锚点后焦点移到章节标题。标题必须有 `tabindex="-1"`。
- 锚点导航自身可滚动。当前项自动滚入视野。

#### 6.5.2 市场筛选

```html
<fieldset class="market-filter">
  <legend>市场</legend>
  <label><input type="checkbox" name="market" value="US" checked> US</label>
  <label><input type="checkbox" name="market" value="DE"> DE</label>
</fieldset>
```

规则：

- 市场来自 `coverage` 的键。
- 筛选写入 `?market=US&market=DE`。
- 筛选只影响 claim、metric、exhibit 的显示。不改变分母。
- 某市场无数据时，显示 `evidence_gap`。不得隐藏该市场。
- 结果计数显示“显示 3/7 个市场”。

#### 6.5.3 人群或分群 tab

```html
<div role="tablist" aria-label="人群分群">
  <button role="tab" id="tab-all" aria-selected="true" aria-controls="panel-all" tabindex="0">全部</button>
  <button role="tab" id="tab-new" aria-selected="false" aria-controls="panel-new" tabindex="-1">新用户</button>
</div>
<div role="tabpanel" id="panel-all" aria-labelledby="tab-all" tabindex="0">...</div>
```

规则：

- 分群来自 `claims[].scope.segment`。合同扩展字段必须写入 schema。
- 没有分群时，不渲染 tab。
- 键盘：←/→ 切换。Home/End 跳到首尾。`aria-selected` 与 `tabindex` 同步。

#### 6.5.4 证据抽屉

规则：

- 每个 exhibit 有一个“证据 N”按钮。
- 点击打开右侧抽屉。抽屉宽度 420px。`role="dialog" aria-modal="true"`。
- 抽屉一次显示该 claim 的全部证据。按 `role` 分组：support、counter、context、gap。
- 每条证据显示：来源工具、市场、时间、等级、摘录、原文链接。
- 抽屉顶部有“展开全部证据”按钮。点击后显示整份报告的证据。
- 焦点陷阱使用 `useFocusTrap`。关闭后焦点回到触发按钮。
- `Escape` 关闭。点击遮罩关闭。
- 抽屉打开时，背景内容 `aria-hidden="true"`。滚动锁定。

#### 6.5.5 主题

规则：

- 默认跟随系统 `prefers-color-scheme`。
- 用户切换后写入 `localStorage`。键名 `dih-theme`。值 `light` 或 `dark`。
- 主题写到 `<html data-theme="...">`。
- 打印强制亮色。不得打印暗色。
- 切换不使用过渡动画。`prefers-reduced-motion` 下立即切换。

#### 6.5.6 打印

规则：

- 页头“打印”按钮调用 `window.print()`。
- 打印前必须展开所有 `details`。使用 `beforeprint` 事件。
- 打印后恢复原来的展开状态。
- 打印样式见 6.3.4。

#### 6.5.7 复制单条结论

规则：

- 每个 claim 标题右侧有复制按钮。
- 复制内容：claim 文本、claim ID、报告 URL。每项一行。
- 不复制正文、不复制证据摘录。
- 复制成功显示 toast“已复制结论”。失败显示可手动复制的文本框。

### 6.6 SOP 视图

同一份合同渲染第二份页面。使用 `?view=sop`。

| 区块 | 数据来源 | 内容 |
|---|---|---|
| 阶段 stepper | `gates[]` | G0–G10。每阶段显示 inputs、outputs、acceptance、rollback |
| 数据合同 | `metrics[]` | 六种计数定义：原始对象、出现、规范记录、帧成员、标注、指标行 |
| 算法 | `skills[]` | 准入、去重、编码、校准、计算、解释、行动、复核 |
| 校准 | `gates[]` 的 G7 | 双盲编码与一致性指标 |
| skill 清单 | `skills[]` | 每个 skill 的输入输出与验收 |
| 检查清单 | `checks[]` | 交付前逐项勾选。14 项 |
| 验证记分卡 | `checks[]` | 通过数 / 总数 |
| 案例边界 | `limits[]`、`unknowns[]` | 本次跑到哪个门禁 |

规则：

- 报告与 SOP 读同一份合同。
- 合同哈希在两份页面一致。
- 换品牌重跑，SOP 的阶段与验收不变。
- SOP 不做图表。全部使用表格与列表。
- `skills[]` 与 `checks[]` 不在 PRD 5.5.1 的顶层字段里。它们必须作为合同扩展字段写入 schema。未写入时 SOP 页显示空态。

### 6.7 报告页验收判据

- 合同必须通过 `report_contract.schema.json` 校验。校验失败不发布。
- 每个 exhibit 六段齐全。缺第 4 段时构建失败。
- 首屏三项分开显示。DOM 中存在三个 `data-testid`。
- 页面不出现“综合可信度”或单一评分。
- `evidence_gap` 与 `blocked` 在首屏 claim 分布中可见。
- 证据抽屉一次展开全部证据。
- 明暗主题切换后，正文对比度不低于 4.5:1。图表不低于 3:1。
- 打印 A4：无截断。每个 exhibit 不跨页。链接打印完整 URL。
- 键盘可完成：锚点跳转、市场筛选、分群切换、抽屉打开与关闭、复制结论。
- 图表库依赖数为 0。

## 7. 工作台三栏规格

### 7.1 布局与尺寸

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ WorkbenchTopBar 56px：← 工作台 · 项目切换 · 任务标题 · 状态 · 中止 · 新建  │
├──────────────┬──────────────────────────────────┬──────────────────────────┤
│ LeftRail     │ Center                           │ RightRail                │
│ 280px        │ minmax(480px, 1fr)               │ 360px                    │
│              │                                  │                          │
│ header 56    │ thread 1fr（独立滚动）           │ tabs 44（粘性）          │
│ search 40    │                                  │ content 1fr（独立滚动）  │
│ list 72/行   │ plan sheet（可折叠）             │                          │
│ footer 48    │ run timeline                     │ cost footer 96（粘性）   │
│              │ composer 120（粘性）             │                          │
└──────────────┴──────────────────────────────────┴──────────────────────────┘
```

CSS：

```css
.workbench-shell {
  --workbench-topbar: 3.5rem;
  display: grid;
  grid-template-columns: 17.5rem minmax(0, 1fr) 22.5rem;
  height: calc(100dvh - var(--workbench-topbar));
  overflow: hidden;
}

.workbench-col {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.workbench-center {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  border-inline: 1px solid var(--border-subtle);
}
```

规则：

- 三栏各自滚动。页面 body 不滚动。
- 栏间距用 1px 边框，不用阴影。
- 每栏必须有 `aria-label`。例如“任务列表”“任务对话”“证据与成本”。
- 栏宽变化时，中栏优先保证 480px。

### 7.2 左栏

| 区块 | 高度 | 行为 |
|---|---|---|
| 栏头 | 56px，粘性 | 项目名、项目切换、新建任务 |
| 搜索 | 40px，粘性 | 本地过滤任务。250ms 防抖 |
| 任务列表 | 1fr，滚动 | 行高 72px。当前任务 `aria-current="true"` |
| 栏尾 | 48px，粘性 | 调度状态、最近运行时间 |

规则：

- 任务行显示：标题、状态、最近运行时间、模板徽章。
- 任务超过 50 条时使用虚拟列表。虚拟列表必须保留键盘焦点。
- 切换任务时，左栏滚动位置保留。
- 左栏不显示全局导航。全局导航在公开区页头或移动端抽屉。
- 空态显示“还没有任务”与“新建任务”按钮。

### 7.3 中栏

中栏从上到下分三段：对话、计划、运行。三段共用一个滚动容器。输入框固定底部。

| 区块 | 行为 |
|---|---|
| 对话消息流 | 新消息追加到末尾。默认贴底。用户上滚后停止贴底 |
| 计划单 | 可折叠。展开时高度不超过 60vh。内部滚动 |
| 运行时间线 | 步骤状态更新。失败步骤自动展开 |
| 输入框 | `position: sticky; bottom: 0`。安全区内边距 |

规则：

- 对话消息分三类：用户消息、系统消息、门禁消息。三类样式不同。
- 系统消息不得伪装成用户消息。
- 门禁消息必须显示门禁名、状态、下一步。
- 计划单的来源行可编辑。排除项保留在计划里。不得静默删除。
- 运行时间线每步显示：工具、市场、预计条数、状态、耗时、成本。
- 输入框高度 120px。支持多行。`Cmd/Ctrl+Enter` 发送。
- 贴底判断：用户距底部小于 80px 时自动贴底。大于 80px 时显示“有新消息”按钮。
- 发送中禁用发送按钮。草稿保留。
- 中栏不做无限滚动历史。消息超过 200 条时使用“加载更早”。

### 7.4 右栏

| 区块 | 高度 | 行为 |
|---|---|---|
| Tab 条 | 44px，粘性 | 证据、成本、门禁 |
| Tab 内容 | 1fr，滚动 | 每个 tab 保留自己的滚动位置 |
| 成本条 | 96px，粘性 | 估算、已发生、剩余额度 |

规则：

- 证据 tab 按 claim 或步骤分组。每条证据显示来源、时间、等级、摘录。
- 成本 tab 显示三种口径：估算、已发生、已结算。依据 PRD 5.6。
- 门禁 tab 显示五个门禁：`G-Plan`、`G-Cost`、`G-Evidence`、`G-Claim`、`G-Publish`。每个门禁有状态、负责人、时间、说明。
- 成本条只显示估算与剩余额度。已结算成本在成本 tab 内。
- 右栏不得显示 `confidence_score` 作为“可信度”。该字段是情报评分，不是证据等级。
- 右栏空态必须说明“本次运行还没有证据”或“成本尚未结算”。

### 7.5 滚动行为

| 区域 | 滚动容器 | 规则 |
|---|---|---|
| 左栏 | `aside` | 独立滚动。切换任务保留位置。滚动到顶部时栏头粘性 |
| 中栏 | `section` | 独立滚动。默认贴底。上滚后停止贴底 |
| 右栏 | `aside` | 独立滚动。tab 切换保留每个 tab 的位置 |
| 输入框 | 中栏底部 | 粘性。不随消息滚走 |
| 成本条 | 右栏底部 | 粘性。不随 tab 内容滚走 |
| 抽屉 | 自身 | 打开时锁定背景滚动。关闭后恢复原位置 |

规则：

- `overscroll-behavior: contain`。防止滚动穿透。
- `scrollbar-gutter: stable`。防止滚动条出现时布局跳动。
- 移动端使用 `100dvh`，不用 `100vh`。键盘弹出时输入框可见。
- 不使用 `scroll-behavior: smooth`。`prefers-reduced-motion` 下必须立即跳转。
- 消息流贴底使用 `scrollTop = scrollHeight`。不使用动画。

### 7.6 宽度策略

| 视口 | 左栏 | 中栏 | 右栏 | 说明 |
|---|---|---|---|---|
| ≥1440px | 280px | minmax(480px, 1fr) | 360px | 三栏常驻 |
| 1280–1439px | 260px | minmax(480px, 1fr) | 320px | 三栏常驻 |
| 1024–1279px | 260px | minmax(480px, 1fr) | 抽屉 | 右栏折叠 |
| 768–1023px | 抽屉 | 1fr | 抽屉 | 左、右折叠 |
| <768px | 抽屉 | 1fr | 抽屉 | 中栏全宽 |

规则：

- 中栏宽度不得小于 480px。低于 480px 时优先折叠右栏。
- 三栏总宽不得超过视口。出现横向滚动即为失败。
- 抽屉宽度：左抽屉 320px，右抽屉 420px。窄屏抽屉宽度 100%。
- 抽屉打开时，背景内容 `aria-hidden="true"`。

### 7.7 窄屏折叠

| 断点 | 左栏 | 右栏 | 触发方式 | 关闭方式 |
|---|---|---|---|---|
| 1024–1279px | 常驻 | 抽屉 | 页头“证据”按钮 | Escape、遮罩、关闭按钮 |
| 768–1023px | 抽屉 | 抽屉 | 页头“任务”与“证据”按钮 | 同上 |
| <768px | 抽屉 | 全屏 sheet | 底部三段控件：对话、计划、证据 | 返回按钮、Escape |

移动端规则：

- 顶部显示分段控件：对话、计划、证据。三个视图互斥。
- 输入框固定在底部。使用 `env(safe-area-inset-bottom)`。
- 程序化滚动在键盘弹出后执行。延迟 100ms。
- 不显示横向滚动。
- 触摸目标不小于 44×44px。

### 7.8 URL 与键盘

URL：

- `/workbench?project={id}`。
- `/workbench/[taskId]?panel=evidence&tab=cost&claim={claim_id}&market=US`。
- `/workbench/[taskId]?view=plan`。
- 筛选、tab、选中的 claim 写入 URL。刷新后保留。

键盘：

| 快捷键 | 动作 | 范围 |
|---|---|---|
| `Cmd/Ctrl+Enter` | 发送消息或提交计划 | 中栏 |
| `Escape` | 关闭抽屉或对话框 | 全局 |
| `Alt+1` | 聚焦左栏 | 桌面 |
| `Alt+2` | 聚焦中栏 | 桌面 |
| `Alt+3` | 聚焦右栏 | 桌面 |
| `↑/↓` | 移动列表行焦点 | 左栏 |
| `Enter` | 打开任务或证据 | 列表 |

规则：

- 快捷键不得覆盖浏览器与读屏软件快捷键。
- `Alt+1/2/3` 只在工作台注册。离开页面时注销。
- 焦点移动后必须有可见焦点环。

### 7.9 工作台验收判据

- 三栏各自滚动。桌面下 body 不滚动。
- 1024px 宽度下无横向滚动。
- 中栏宽度不小于 480px。
- 默认贴底。上滚超过 80px 后停止贴底。出现“有新消息”按钮。
- 计划编辑后 1 秒内完成成本重算。重算期间批准按钮禁用。
- 中止运行后已完成步骤保留。状态显示“已中止”。
- 页面不调用 `/fixture-runs`。页面不显示 fixture 字样。
- 右栏三个 tab 可键盘操作。抽屉焦点陷阱生效。
- 移动端输入框在键盘弹出时可见。

## 8. 可访问性

### 8.1 焦点顺序

#### 常规页面（`AppShell`）

1. 跳到主要内容链接。
2. 侧栏品牌。
3. 主导航项。
4. 辅助导航项。
5. 页头标题与操作。
6. 面包屑。
7. 页面主内容。
8. 页脚链接。

#### 报告阅读页（`ReaderShell`）

1. 跳到报告正文。
2. 返回报告中心。
3. 页头操作：主题、打印、分享。
4. 锚点导航。
5. 报告首屏。
6. 章节正文。
7. 证据栏。
8. 页脚。

#### 工作台（`WorkbenchShell`）

1. 跳到任务对话。
2. 页头操作：项目切换、新建、中止。
3. 左栏：搜索、任务列表。
4. 中栏：消息流、计划单、运行时间线、输入框。
5. 右栏：tab 条、tab 内容、成本条。

规则：

- 每个页面必须有“跳到主要内容”链接。链接在获得焦点时可见。
- 抽屉与对话框打开时，焦点进入容器。关闭后回到触发元素。
- 不得使用正数 `tabindex`。
- 标题层级不得跳级。`h1` 只有一个。

### 8.2 ARIA

| 模式 | 角色与属性 | 规则 |
|---|---|---|
| 主导航 | `<nav aria-label="主导航">` | 当前项 `aria-current="page"` |
| 面包屑 | `<nav aria-label="面包屑">` | 最后一项 `aria-current="page"` |
| Tab | `role="tablist"`、`role="tab"`、`role="tabpanel"` | 方向键切换。`aria-selected` 与 `tabindex` 同步 |
| 抽屉 | `role="dialog"`、`aria-modal="true"`、`aria-labelledby` | 焦点陷阱。Escape 关闭 |
| 折叠 | `<button aria-expanded aria-controls>` | 展开状态同步 |
| 运行状态 | `role="status" aria-live="polite" aria-atomic="true"` | 每次只播报一条。错误用 `role="alert"` |
| 图表 | `role="img" aria-label` | 必须有数据表文本替代 |
| 状态徽章 | `<span aria-label="...">文字</span>` | 不只用颜色 |
| 加载 | `aria-busy="true"` | 加载完成后移除 |
| 禁用按钮 | `disabled` 与 `aria-disabled="true"` | 必须说明禁用原因 |
| 进度 | `role="progressbar"` 或文本 | 不确定进度用 `aria-valuetext` |

示例：

```html
<a class="skip-link" href="#main">跳到主要内容</a>
<main id="main" tabindex="-1">...</main>

<div role="tablist" aria-label="右栏视图">
  <button role="tab" id="tab-evidence" aria-selected="true" aria-controls="panel-evidence" tabindex="0">证据</button>
  <button role="tab" id="tab-cost" aria-selected="false" aria-controls="panel-cost" tabindex="-1">成本</button>
</div>
<div role="tabpanel" id="panel-evidence" aria-labelledby="tab-evidence" tabindex="0">...</div>

<div role="status" aria-live="polite" aria-atomic="true">
  第 3 步：采集 Amazon.de 评论，运行中
</div>
```

规则：

- 读屏播报不得重复。状态变化只播报一次。
- 图表 `aria-label` 必须包含图题、单位、关键数值。
- 图标按钮必须有 `aria-label`。纯装饰图标使用 `aria-hidden="true"`。
- 表单错误必须与字段关联。使用 `aria-describedby` 与 `aria-invalid`。

### 8.3 对比度

正文要求 4.5:1。大字与图形要求 3:1。

| 前景 | 背景 | 对比度 | 用途 | 判定 |
|---|---|---|---|---|
| `#241b1b` | `#f7f2ed` | 15.13:1 | 主文字 | 通过 |
| `#5b5050` | `#f7f2ed` | 6.97:1 | 次要文字 | 通过 |
| `#786d6a` | `#f7f2ed` | 4.50:1 | 元数据 | 通过，限 12px 以上 |
| `#9b4355` | `#f7f2ed` | 5.67:1 | 主操作文字 | 通过 |
| `#ffffff` | `#9b4355` | 6.31:1 | 主按钮文字 | 通过 |
| `#5b5050` | `#ffffff` | 7.75:1 | 面板次要文字 | 通过 |
| `#786d6a` | `#ffffff` | 5.01:1 | 面板元数据 | 通过 |
| `#2f6b4f` | `#ffffff` | 6.29:1 | confirmed | 通过 |
| `#45687d` | `#ffffff` | 5.95:1 | directional | 通过 |
| `#756078` | `#ffffff` | 5.67:1 | hypothesis | 通过 |
| `#8a6a2f` | `#ffffff` | 5.02:1 | evidence_gap | 通过 |
| `#a5534b` | `#ffffff` | 5.33:1 | blocked | 通过 |
| `#8a827d` | `#ffffff` | 3.77:1 | 图表未知填充 | 只用于图形 |
| `#f5efea` | `#161211` | 16.32:1 | 暗色主文字 | 通过 |
| `#c9beb8` | `#161211` | 10.22:1 | 暗色次要文字 | 通过 |
| `#a69a94` | `#161211` | 6.80:1 | 暗色元数据 | 通过 |
| `#e39aa8` | `#1f1a19` | 7.75:1 | 暗色主操作 | 通过 |
| `#161211` | `#e39aa8` | 8.38:1 | 暗色按钮文字 | 通过 |
| `#f5efea` | `#9b4355` | 5.53:1 | 亮色按钮反色 | 通过 |

规则：

- `--text-tertiary` 只用于 12px 及以上文字。不得用于关键结论。
- `--chart-unknown` 只用于图形填充。不得用作文字颜色。
- 所有状态都不得只靠颜色区分。必须同时有文字或图标。
- 图表颜色在灰度下仍需有数值标签。

### 8.4 键盘

| 组件 | 按键 | 行为 |
|---|---|---|
| 目录行 | ↑/↓ | 移动行焦点 |
| 目录行 | Enter | 打开详情 |
| 搜索 | `/` | 聚焦搜索框 |
| 搜索 | Escape | 清空并退出 |
| Tabs | ←/→ | 切换 tab |
| Tabs | Home/End | 跳到首尾 |
| 抽屉 | Escape | 关闭 |
| 抽屉 | Tab/Shift+Tab | 循环焦点 |
| 对话框 | Escape | 取消 |
| 对话框 | Enter | 确认默认按钮 |
| 工作台 | `Cmd/Ctrl+Enter` | 发送消息或提交计划 |
| 工作台 | `Alt+1/2/3` | 聚焦三栏 |
| 报告 | `p` | 打印。输入框聚焦时不生效 |

规则：

- 所有交互必须键盘可达。
- 焦点环必须可见。使用 `--focus-ring`。见 `globals.css:79` 与 `:139-142`。
- 不得使用 `outline: none` 去掉焦点环。
- 抽屉打开时，背景不可聚焦。
- 跳过链接在获得焦点时可见。

### 8.5 reduced motion

现有 `globals.css:114-120` 已把 `--duration-fast`、`--duration-base`、`--duration-slow` 设为 0ms。

新组件规则：

- 只使用 `var(--duration-*)`。不得硬编码动画时长。
- 不使用 `scroll-behavior: smooth`。
- 不使用视差、自动轮播、自动播放视频。
- 骨架屏不使用 shimmer。使用静态灰块。
- 运行状态更新不使用打字机效果。
- 主题切换不使用过渡。
- 进度条动画在 reduced motion 下改为文本状态。
- `prefers-reduced-motion` 下，所有过渡立即完成。

### 8.6 可访问性验收判据

- axe 扫描 0 个 critical 问题。
- 仅用键盘可完成：登录、创建任务、批准计划、打开报告、切换市场、打开证据抽屉、打印。
- 每个图标按钮有可访问名称。
- 每个图表有文本替代。
- 正文对比度不低于 4.5:1。
- 200% 缩放下无横向滚动。320px 宽度下内容可读。
- 触摸目标不小于 44×44px。
- `prefers-reduced-motion` 下无动画。
- 读屏软件可读出状态变化。不得重复播报。

## 9. 交付检查清单

本批 UI 交付前逐项检查。

| # | 检查项 | 通过判据 |
|---|---|---|
| 1 | 11 条路由 | 路由表与 PRD 3.3 一致。无第 12 条一级路由 |
| 2 | 现有页面处置 | 每个现有页面有处置结论与证据 |
| 3 | 设计原则 | 五条原则各有可判定标准 |
| 4 | 逐页线框 | 每页有线框、区块清单、交互、验收 |
| 5 | 组件清单 | 复用、改造、新建、禁止复用四类齐全 |
| 6 | shadcn 映射 | 每个新组件有基础组件。无图表库 |
| 7 | token | 颜色、字体、间距、圆角、阴影齐全 |
| 8 | token 差异 | 与 `globals.css` 的差异逐项列出 |
| 9 | 报告阅读页 | 六段式 DOM、CSS、断点、打印齐全 |
| 10 | 工作台三栏 | 滚动、宽度、窄屏折叠齐全 |
| 11 | 可访问性 | 焦点、ARIA、对比度、reduced motion 齐全 |
| 12 | 证据 | 所有 `live` 结论有文件行号或测试证据 |
| 13 | 写作 | 短句、主动语态、术语一致 |

## 10. 已知限制

1. `tool_catalog` 表不存在。目录详情页的参数表、输出表、成本、示例无法上线。必须新建表与 API。
2. `report_contract` 与 `report_artifacts` 不存在。报告阅读页的六段式无法上线。必须新建合同层。
3. 真实运行层不可用。`workflow_runs` 是已挂载的 fixture-only 路由（生产返回 200，`execution_mode=fixture`），不能承载真实执行。工作台的执行与中止无法上线。
4. 通用 agent runtime 不存在。工作台对话只能显示任务事件。自由对话端点必须新建。
5. 项目级凭据隔离不存在。`platform_credential_bundles` 只有 workspace 维度。连接器页的项目选择器不得伪造。
6. 鉴权未完成。11 个路由模块直接调用 `get_demo_workspace`。见 `apps/api/src/data_intelligence_hub/api/deps.py:54-79`。授权区页面必须先补 middleware 与 401。
7. 报告中心缺少服务端筛选与三个列表字段。必须扩展 `GET /api/reports`。
8. 现有 `QuickCollectDrawer` 只覆盖 162 个 endpoint_type。生产有 281 个唯一端点。直接复用会提交空参数。
9. shadcn 未安装。`components.json:7` 指向不存在的 `tailwind.config.ts`。
10. 暗色主题不存在。`globals.css` 只有亮色块。
11. `apps/web` 的报告组件没有公网路由。迁移时必须换 token 与鉴权。
12. TikTok R1 的 7 个关键文件未纳入 HEAD 跟踪。涉及 TikTok 的页面必须先确认部署分支。

这些限制必须写进实施计划。不得在 UI 中隐藏。
