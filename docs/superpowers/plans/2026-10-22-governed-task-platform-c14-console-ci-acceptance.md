# 受治理任务平台 C14：控制台与 CI 验收实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `apps/scraper-console` 收敛到 11 条合同路由与 4 条一级导航，让工作台、运行、报告、资产、连接器、设置六个页族使用真实 API，并把单元测试、tsc、lint、build、Playwright 设为 CI 阻塞门禁。治理写动作只调用 C1 已登记路径，并只在本地/CI 专用合成工作区验收；生产 canary/preflight 保持只读。

**Architecture:** 前端只增加路由注册表、middleware 策略、六个 API 客户端和页面状态组件。所有数据来自已登记接口；缺接口时显示明确的缺口状态，不生成假数据。控制台代码与 Playwright 只在开发/CI 实现；PG0 发布批次负责部署、迁移、compose/env 与开关翻转。C14 的验收由 Playwright 正负黄金路径、截图清单、`scripts/p0_acceptance.sh`、生产 A 只读 canary、生产 B 只读 preflight 与四个 PG0 开关的只读证据组成。

**Tech Stack:** Next.js 16.3.0、React 19.2.8、TypeScript 5.7、TanStack Query 5、Tailwind v4、Node 26 `node --test`、Playwright 1.60、FastAPI/Python 3.12、PostgreSQL 15、GitHub Actions。

## Global Constraints

- 权威顺序：`docs/design/【契约冻结】v1-表名-枚举-接口.md` > 已批准设计 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` > 当前迁移与代码事实 > 其他文档。C0 未完成时先停止，不在 C14 里补契约。
- C14 独占 `apps/scraper-console/src/**`、`apps/scraper-console/e2e/**` 与 Playwright。C11/C12/C13 只提供浏览器交接单，不得修改这些目录。
- 11 条合同路由是唯一合同面：10 条启用、1 条禁用（`/reports/public/[id]`）。一级导航只有 4 条：工作台 `/workbench`、报告 `/reports`、连接器 `/connectors`、设置 `/settings`。`/runs`、`/assets`、`/projects`、`/tasks`、`/dashboard` 不得进入一级导航；legacy 页面按重定向或保留清单处理。
- 成员管理是 `/settings` 页面的内联面板，不新增 `/settings/members` 路由或第 12 条合同路由。成员面板的选择器、邀请、改角色、最后 owner 错误、项目分配与 owner/admin/member 可见性以 `docs/ops/c2-c14-members-handoff.md` 为准。
- 动态段名以冻结契约 §5 为唯一来源（C1 v1.1 登记 `/capabilities/[toolId]`、`/reports/[artifactId]`、`/workbench/[taskId]`；公开分享保持 `/reports/public/[id]`）。B5 已落地的 `[toolId]`、`[artifactId]`、`[runId]` 页面只用于实现核对。不得另起 `[id]` 页面，也不得在测试或代码里维护第二份路由清单。
- 功能开关只有一个：`PUBLIC_REPORT_SHARE_ENABLED`，固定 `false`。回滚点是回退控制台提交；C14 无迁移、无 API 路由，不需要数据库回滚。
- 不启用公开分享：`PUBLIC_REPORT_SHARE_ENABLED = false`。不创建 `/reports/public/[id]` 页面，不提供分享按钮，任何 `/reports/public/*` 请求返回 404。
- 不新设计系统、不新增审批收件箱或审批页面。超额、加购和密钥变更的 owner/admin 批准只在工作台任务详情与设置页项目密钥行内联展示；发起人不能批准自己的请求。C14 不新增审批 API 路由；Task 8A 只调用 C1/C3/C5 已登记的批准路径，服务端授权边界仍属于后端切片。
- 无迁移。C14 不新增 Alembic revision、不新增表、不新增列、不新增枚举、不新增 API 路由、不新增或改名 MCP 工具。任何新对象先升级契约 v1.1 并重新批准，再另立切片。
- 客户 MCP 固定八个工具，顺序固定：`discover_capabilities`、`estimate_task`、`create_task`、`get_task`、`cancel_task`、`get_delivery_manifest`、`get_evidence`、`collect`。C14 不得修改 `apps/api/src/data_intelligence_hub/mcp_runtime/`。
- Q43：普通评论者使用工作区级伪名盐。同一工作区稳定，跨工作区不可关联。项目隔离靠权限，不改项目级盐，不提供反查映射。
- `tiktok.creator_cookie` 只保留在内部隔离客户链。连接器页不得展示、导出或接受该 Cookie。客户数据集、Claim、报告、manifest 不得包含其输出。
- 保留期冻结：原始响应 30 天；标准化数据集 12 个月；正式报告和交付包 24 个月；运行日志 180 天；安全与访问审计 24 个月；备份 30 天。C14 不改保留策略。
- `workbench_tasks.status` 只允许 `draft`、`submitted`、`cancelled`（C4 契约）。工作台页面不得把运行状态写进任务单状态。
- 工作台 API 字段以 C4 为准：`WorkbenchTaskCreateRequest`、`WorkbenchTaskResponse`、`WorkbenchTaskDetailResponse`、`WorkbenchTaskListResponse`、`WorkbenchSubmissionResponse`、`WorkbenchGateResponse`。
- 生产 A 和 B 只做只读健康检查、canary 与 preflight。C14 不部署、不备份、不迁移、不重启、不重建 edge、不写 compose/env、不 seed 生产、不翻转任何功能开关。备份、迁移、compose/env 变更、部署、重启与四个 PG0 开关的翻转只属于 PG0 发布批次。
- C14 的控制台代码、Playwright 与验收脚本只在本地与 CI 运行。生产验收在 PG0 发布批次完成部署后执行；C14 只记录只读证据。
- 报告页默认只读显示 C9 的 `published_by`、`published_at` 与 `GET /api/reports/{report_id}/revisions` 修订链。Task 8A 在本地/CI 合成工作区调用 C1 已登记的审核人指派、审核、发布、Quick 草稿、交付与验收路径；不调用未登记端点。生产 canary 仍只读。
- 四个 PG0 开关的只读证据是 `budget_enforcement_enabled`、`strict_price_enabled`、`run_execution_convergence_enabled`、`retention_cleanup_enabled`。C14 只断言它们为 true，不写 `.env.production`，不重启容器。
- 每次编辑函数、类或方法前运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。`risk: UNKNOWN` 按未解决处理，必须用文本搜索确认调用方。HIGH/CRITICAL 必须在提交说明中报告，不得用 `riskSharedAxes` 豁免。
- 每次提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 必须重跑。
- 先写失败测试，再写最小实现，再跑通过。每个任务结束提交一次。
- Next.js 16.3.0 有破坏性变更。写代码前先读 `apps/scraper-console/node_modules/next/dist/docs/` 中与当前文件相关的章节。`params` 与 `searchParams` 是 Promise。
- 使用现有设计 token 和组件。禁止新增颜色体系、图标库或第二套 `AppShell`。
- 所有运行与提交命令默认在隔离 worktree `/Users/lute/Project/data_scrapy-gov-c14` 执行。主工作树 `/Users/lute/Project/data_scrapy` 只用于创建 worktree、复制本计划与读取 `C14_BASE_REF`。前端命令使用 `pnpm -C apps/scraper-console`。

---

## 0. 范围锁定

### 0.1 11 条合同路由

下表只用于范围说明，不是第二个路由事实源。权威列表是冻结契约 §5；`contract-routes.test.ts` 直接从该节解析并与 `CONTRACT_ROUTES` 逐条比较。任何差异都停止并返回 C1 修正登记，不在 C14 里改契约。

| # | 路由 | 分组 | 本期状态 | 页面文件 |
|---:|---|---|---|---|
| 1 | `/` | 公开 | 启用 | `src/app/page.tsx` |
| 2 | `/capabilities` | 公开 | 启用 | `src/app/capabilities/page.tsx` |
| 3 | `/capabilities/[toolId]` | 公开 | 启用 | `src/app/capabilities/[toolId]/page.tsx` |
| 4 | `/reports/public/[id]` | 公开 | 禁用 | 不存在 |
| 5 | `/docs` | 公开 | 启用 | `src/app/docs/page.tsx` |
| 6 | `/workbench` | 授权 | 启用 | `src/app/workbench/page.tsx` |
| 7 | `/workbench/[taskId]` | 授权 | 启用 | `src/app/workbench/[taskId]/page.tsx` |
| 8 | `/reports` | 授权 | 启用 | `src/app/reports/page.tsx` |
| 9 | `/reports/[artifactId]` | 授权 | 启用 | `src/app/reports/[artifactId]/page.tsx` |
| 10 | `/connectors` | 授权 | 启用 | `src/app/connectors/page.tsx` |
| 11 | `/settings` | 授权 | 启用 | `src/app/settings/page.tsx` |

### 0.2 六个页族与真实数据源

| 页族 | 路由 | 真实数据源 |
|---|---|---|
| 工作台 | `/workbench`、`/workbench/[taskId]` | `GET/POST /api/workbench/tasks`、`GET /api/workbench/tasks/{task_id}`、`GET /api/workbench/tasks/{task_id}/gates`、`GET /api/projects` |
| 运行 | `/runs`、`/runs/[runId]` | `GET /api/tasks/runs`、`GET /api/runs/{run_id}`、`GET /api/runs/{run_id}/steps`、`GET /api/raw-records?task_run_id=` |
| 报告 | `/reports`、`/reports/[artifactId]` | `GET /api/reports`、`GET /api/reports/{report_id}`、`GET /api/reports/{report_id}/contract`（合同 JSON 内含 claims 与 evidences） |
| 资产 | `/assets`、`/assets/records` | `GET /api/automation/product-datasets`、`GET /api/raw-records` |
| 连接器 | `/connectors` | `GET /api/settings/platform-credentials`、`GET /api/platform-packages`、`GET /api/platform-packages/providers/status` |
| 设置 | `/settings` | `GET /api/auth/me`、`GET /api/workspaces`、`GET /api/workspaces/current/members`、`GET /api/usage/summary` |

### 0.3 明确不做

- C14 不创建后端 API、不新增路由、不新建系统、不改数据库。所有服务端行为来自 C0–C13 已登记接口；任何新行为先升级契约 v1.1 并另立切片。
- C14 必须实现已登记 API 的 UI 客户端与动作：任务单创建与提交、`POST /api/runs` 提交/重放/冲突、运行取消与重试入口、内联审批、成员管理、项目密钥 CRUD（一次性明文、轮换、撤销）、客户 MCP 面板、额度与预算卡片、Claim 只读、报告审核指派/读取/批准/拒绝、owner/admin 发布、修订列表、Quick 草稿、交付发布/下载、accepted/disputed/deemed-accepted 事件，以及隐私合成删除、DSR、证明与法律保留阻断。
- 连接器页复用现有 `PUT/DELETE /api/settings/platform-credentials/{platform}`。客户 MCP 面板只展示事实、密钥前缀与配置 JSON，不展示 provider、端点、Cookie 或内部单价。
- 不做公开分享页、分享链接、分享按钮、分享审计。
- 不做暗色主题、视觉换肤、动画重构。
- 不做新数据库对象、新 API 路由、新 MCP 工具。
- 不做生产写入。生产 A 只读 canary，生产 B 只读 preflight。

### 0.4 前置命令

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
rg -n '/capabilities/\[toolId\]|/reports/\[artifactId\]|/workbench/\[taskId\]' \
  "docs/design/【契约冻结】v1-表名-枚举-接口.md"
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console exec tsc --noEmit
pnpm -C apps/scraper-console lint
pnpm -C apps/scraper-console build
```

预期：契约检查输出 `contract_registry_ok`；`rg` 在契约 §5 命中三个动态段名；后四条全部通过。任一失败时停止，不进入 Task 1。`rg` 未命中表示 C1 尚未登记页面路由，必须返回 C1，不在 C14 里补契约。

---

### Task 0: 开工门禁与基线

**Files:**
- Create: `tmp/c14-baseline.txt`（不提交）

**Interfaces:**
- Consumes: C0/C1 的契约脚本、GitNexus 索引。
- Produces: 风险基线、调用方清单、干净工作树。

- [ ] **Step 0: 创建隔离 worktree 并安装依赖**

`C14_BASE_REF` 必填，必须指向已包含 C0–C13 的集成分支或标签。只在主工作树执行本步骤。

Run:
```bash
cd /Users/lute/Project/data_scrapy
: "${C14_BASE_REF:?set C14_BASE_REF to the integration tip containing C0-C13}"
git worktree prune
git rev-parse --verify "${C14_BASE_REF}^{commit}"
test -z "$(git branch --list feat/gov-c14)"
test ! -e /Users/lute/Project/data_scrapy-gov-c14
git worktree add /Users/lute/Project/data_scrapy-gov-c14 -b feat/gov-c14 "$C14_BASE_REF"
cp docs/superpowers/plans/2026-10-22-governed-task-platform-c14-console-ci-acceptance.md \
  /Users/lute/Project/data_scrapy-gov-c14/docs/superpowers/plans/
cd /Users/lute/Project/data_scrapy-gov-c14/apps/api
uv sync --locked --dev
cd /Users/lute/Project/data_scrapy-gov-c14
pnpm install --frozen-lockfile
git branch --show-current
git merge-base --is-ancestor "$C14_BASE_REF" HEAD && echo C14_BASE_REF_ANCESTOR_OK
git status --porcelain
```
Expected: worktree 固定在 `/Users/lute/Project/data_scrapy-gov-c14`，分支为 `feat/gov-c14`，输出 `C14_BASE_REF_ANCESTOR_OK`；`uv sync` 与 `pnpm install` 退出码 0；工作树只有复制进来的 C14 计划文件。分支或路径已存在时停止并检查，不得删除或复用。后续所有 Run/Commit 路径都在 `/Users/lute/Project/data_scrapy-gov-c14`，不得回主工作树执行。

- [ ] **Step 1: 核对契约与迁移基线**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c14
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
git status --porcelain
git rev-parse --short HEAD
rg -n '/capabilities/\[toolId\]|/reports/\[artifactId\]|/workbench/\[taskId\]' \
  "docs/design/【契约冻结】v1-表名-枚举-接口.md"
```
Expected: `contract_registry_ok`；工作树除 `docs/superpowers/plans/` 下的计划文件外无代码改动。`rg` 必须在契约 §5 命中 `[toolId]`、`[artifactId]`、`[taskId]` 三个动态段名；缺任一就停止并返回 C1 登记，C14 不修改契约。有未提交的 C1–C13 代码时停止，先让对方收口。

- [ ] **Step 2: 记录 GitNexus 影响**

Run:
```bash
node .gitnexus/run.cjs impact "middleware" --direction upstream --file-path apps/scraper-console/src/middleware.ts --repo . | tee tmp/c14-baseline.txt
node .gitnexus/run.cjs impact "PRIMARY_NAVIGATION" --direction upstream --file-path apps/scraper-console/src/lib/routes.ts --repo . | tee -a tmp/c14-baseline.txt
node .gitnexus/run.cjs impact "Sidebar" --direction upstream --file-path apps/scraper-console/src/components/layout/sidebar.tsx --repo . | tee -a tmp/c14-baseline.txt
node .gitnexus/run.cjs impact "fetchWorkbenchSnapshot" --direction upstream --file-path apps/scraper-console/src/lib/api/workbench.ts --repo . | tee -a tmp/c14-baseline.txt
node .gitnexus/run.cjs impact "fetchReports" --direction upstream --file-path apps/scraper-console/src/lib --repo . | tee -a tmp/c14-baseline.txt
node .gitnexus/run.cjs impact "CredentialsPage" --direction upstream --file-path apps/scraper-console/src/app/settings/credentials/page.tsx --repo . | tee -a tmp/c14-baseline.txt
```
Expected: 六个目标都有输出。`risk: UNKNOWN` 的目标用 `grep -rn "<symbol>" apps/scraper-console/src` 确认调用方；HIGH/CRITICAL 必须在提交说明中报告，并在 Task 1–8 的提交里重复该风险。

- [ ] **Step 3: 记录基线测试**

Run:
```bash
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console exec tsc --noEmit
pnpm -C apps/scraper-console lint
pnpm -C apps/scraper-console build
```
Expected: 四条全部通过。失败项写入 `tmp/c14-baseline.txt`，先修基线或调整任务顺序，不在红灯上叠加改动。

- [ ] **Step 4: 确认浏览器门禁可运行**

Run:
```bash
pnpm -C apps/scraper-console exec playwright install chromium
pnpm -C apps/scraper-console exec playwright test --list
```
Expected: 列出 setup/public/authenticated 三个项目和现有用例，不执行网络请求。记录当前用例数到 `tmp/c14-baseline.txt`。

---

## File Structure

### 新建

| 文件 | 责任 |
|---|---|
| `apps/scraper-console/src/lib/contract-routes.ts` | 11 条合同路由、4 条一级导航、2 条辅助导航的唯一注册表 |
| `apps/scraper-console/src/lib/contract-routes.test.ts` | 路由数量、动态段名、页面存在性、分享禁用 |
| `apps/scraper-console/src/lib/contract-routes.pages.test.ts` | 最终检查 10 条启用路由有页面、1 条禁用路由无页面 |
| `apps/scraper-console/src/lib/middleware-policy.ts` | 公开 allowlist 与登录跳转的纯函数 |
| `apps/scraper-console/src/lib/middleware-policy.test.ts` | 公开/受保护路径、`next` 净化、分享禁用 |
| `apps/scraper-console/src/lib/api/workbench.test.ts` | 路径、查询串、ID 编码 |
| `apps/scraper-console/src/lib/api/privacy-handoff.ts` | C2/C3/C11/C12/C13 交接面板客户端 |
| `apps/scraper-console/src/lib/api/privacy-handoff.test.ts` | 交接路径与八工具断言 |
| `apps/scraper-console/src/lib/workbench-view.ts` | 工作台页面状态、11 个正式市场、档位限额与门禁文案的纯函数 |
| `apps/scraper-console/src/lib/workbench-view.test.ts` | 四态、门禁、市场清单、Quick/Standard 限额与提交载荷 |
| `apps/scraper-console/src/lib/inline-approvals.ts` | 超额、加购、密钥变更的内联批准资格纯函数；不调用审批 API |
| `apps/scraper-console/src/lib/inline-approvals.test.ts` | owner/admin、发起人自批、非人类主体与终态断言 |
| `apps/scraper-console/src/components/workbench/task-form.tsx` | 七槽位任务单表单；package_type 与 1 主市场 + 受限对比市场 |
| `apps/scraper-console/src/components/workbench/task-list.tsx` | 任务单列表 |
| `apps/scraper-console/src/components/workbench/task-detail.tsx` | 任务详情、门禁、Task 8A 提交/取消/内联批准控件；不新增计划预览路由 |
| `apps/scraper-console/src/app/workbench/[taskId]/page.tsx` | 任务详情路由 |
| `apps/scraper-console/src/lib/assets-quality.ts` | 质量状态/样本标签与质量页签类型 |
| `apps/scraper-console/src/lib/assets-quality.test.ts` | 未评分、有缺口、缺失值不显示 0 |
| `apps/scraper-console/e2e/assets-quality.spec.ts` | `/assets` 质量列与质量页签浏览器验收 |
| `apps/scraper-console/src/lib/runs-view.ts` | 运行状态与步骤时间的纯函数 |
| `apps/scraper-console/src/lib/runs-view.test.ts` | 运行四态与步骤标签 |
| `apps/scraper-console/src/lib/api/connectors.ts` | 连接器合并读模型 |
| `apps/scraper-console/src/lib/api/connectors.test.ts` | 合并、脱敏、缺失字段 |
| `apps/scraper-console/src/components/connectors/connectors-workspace.tsx` | 连接器与凭据页面主体 |
| `apps/scraper-console/src/app/connectors/page.tsx` | 连接器路由 |
| `apps/scraper-console/src/lib/api/settings.ts` | 设置页会话、成员、用量客户端 |
| `apps/scraper-console/src/lib/api/settings.test.ts` | 路径与空态 |
| `apps/scraper-console/src/app/settings/page.tsx` | 设置路由 |
| `apps/api/src/data_intelligence_hub/maintenance/e2e_seed.py` | 只写本地/CI 的 E2E 种子 |
| `apps/api/tests/unit/test_e2e_seed.py` | 种子 ID、邮箱前缀、行数、无 Cookie |
| `apps/api/tests/integration/test_e2e_seed_db.py` | 真实数据库种子、C2 哈希链合法性与重复 seed 幂等 |
| `scripts/seed-console-e2e.sh` | 清库、种子、写 manifest |
| `apps/scraper-console/e2e/auth.setup.ts` | 登录并保存 storage state |
| `apps/scraper-console/e2e/auth-limited.setup.ts` | 以同工作区受限项目成员登录并保存第二个 storage state |
| `apps/scraper-console/e2e/limited-member.spec.ts` | 同工作区跨项目负路径：任务、Claim、报告、交付与资产 |
| `apps/scraper-console/e2e/members.spec.ts` | `/settings` 内联成员面板：邀请、改角色、最后 owner 错误、项目分配与三视角可见性 |
| `apps/scraper-console/e2e/support/page-problems.ts` | 共享 console/pageerror/5xx 监听 |
| `apps/scraper-console/e2e/support/seed-manifest.ts` | 读取 `tmp/console-e2e.json` |
| `apps/scraper-console/e2e/golden-path.spec.ts` | 正黄金路径 |
| `apps/scraper-console/e2e/negative-paths.spec.ts` | 负路径 |
| `apps/scraper-console/e2e/screenshots.spec.ts` | 截图与 manifest |
| `scripts/verify-console-ci-gates.py` | 检查 CI 五个阻塞门禁 |
| `scripts/p0_acceptance.sh` | 只读 HTTP 验收 |
| `scripts/canary-console-production.sh` | 生产 A 只读 canary |
| `scripts/preflight-production-b.sh` | 生产 B 只读 preflight |
| `scripts/preflight-production-a.sh` | 生产 A 只读 schema preflight 包装；要求 PG0 发布批次提供 `SCRAPY_EXPECTED_SCHEMA` |
| `scripts/verify-pg0-switches.sh` | 生产 A/B 只读读取四个 PG0 开关；不写 env、不重启 |
| `docs/ops/console-acceptance.md` | 运行手册与证据表 |

### 修改

| 文件 | 改动 |
|---|---|
| `apps/scraper-console/src/lib/routes.ts` | 从 `contract-routes.ts` 重导出导航；增加 2 条重定向；按任务追加 2 条新路由 |
| `apps/scraper-console/src/lib/routes.test.ts` | 更新分组数量与导航断言 |
| `apps/api/src/data_intelligence_hub/maintenance/e2e_cleanup.py` | 清理 `workbench_tasks`、`ProjectMember`、`Claim`/`ClaimEvidence`、`ReportArtifact`、C3 密钥、C11 法律保留、C12 删除请求和项目级 E2E 业务数据；解除 `workflow_versions.workbench_task_id` 引用；保留确定性的 E2E 用户、工作区、成员与 C2 追加式审计根，不修改或删除审计行 |
| `apps/scraper-console/src/middleware.ts` | 改用 `middleware-policy.ts` |
| `apps/scraper-console/src/app/login/page.tsx` | 默认 `next` 改为 `/workbench`，使用 `safeNextPath` |
| `apps/scraper-console/src/app/workbench/page.tsx` | 改为真实 tasks 数据；不调用未登记的 overview |
| `apps/scraper-console/src/lib/api/workbench.ts` | 保留 `fetchWorkbenchSnapshot`；替换为 C4 tasks/detail/gates 客户端 |
| `apps/scraper-console/src/lib/api/runs.ts` | 增加 `fetchRunSteps` 与 `RunStep` 类型 |
| `apps/scraper-console/src/app/runs/page.tsx` | 使用 `runs-view.ts`，增加状态筛选 |
| `apps/scraper-console/src/app/runs/[runId]/page.tsx` | 增加步骤时间线 |
| `apps/scraper-console/src/lib/api/reports.ts` | 增加证据引用、`/artifact` 与 `/revisions` 只读客户端 |
| `apps/scraper-console/src/app/reports/[artifactId]/page.tsx` | 增加证据抽屉 |
| `apps/scraper-console/src/app/assets/page.tsx` | 使用 `assets-view.ts` 四态，增加“质量”列与 test id |
| `apps/scraper-console/src/app/assets/records/page.tsx` | 增加错误态与 test id |
| `apps/scraper-console/src/lib/api/datasets.ts` | 增加 `quality_status`、`quality_assessment`、`data_gaps` 类型 |
| `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx` | 增加“质量”页签、样本表与缺口表 |
| `apps/scraper-console/src/app/settings/credentials/page.tsx` | 改为重定向到 `/connectors` |
| `apps/scraper-console/playwright.config.ts` | 增加 setup、public、authenticated 三个项目 |
| `apps/scraper-console/e2e/routes.spec.ts` | 复用 `page-problems.ts`，更新路由清单 |
| `apps/scraper-console/package.json` | 增加 `typecheck` 脚本 |
| `.github/workflows/ci.yml` | 增加阻塞的 `console-quality` 与 `console-acceptance` 作业 |
| `apps/scraper-console/README.md` | 增加验收命令 |

---

### Task 1: 合同路由与 4 条一级导航

**Files:**
- Create: `apps/scraper-console/src/lib/contract-routes.ts`
- Create: `apps/scraper-console/src/lib/contract-routes.test.ts`
- Modify: `apps/scraper-console/src/lib/routes.ts`
- Modify: `apps/scraper-console/src/lib/routes.test.ts`

**Interfaces:**
- Consumes: PRD §3.3、契约冻结 v1.1 §5、B5 页面路径。
- Produces: `CONTRACT_ROUTES`、`PRIMARY_NAVIGATION`、`SECONDARY_NAVIGATION`、`PUBLIC_REPORT_SHARE_ENABLED`、`contractRoutePageFile(route)`、`NavigationItem`。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/contract-routes.test.ts`：

```typescript
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  CONTRACT_ROUTES,
  PRIMARY_NAVIGATION,
  PUBLIC_REPORT_SHARE_ENABLED,
  SECONDARY_NAVIGATION,
  contractRoutePageFile,
} from "./contract-routes.ts";

const APP_DIR = new URL("../app/", import.meta.url);

/** 从冻结契约 §5 解析页面路由。§5 是唯一路由事实源。 */
function contractRoutePaths(): string[] {
  const doc = readFileSync(
    resolve(process.cwd(), "../../docs/design/【契约冻结】v1-表名-枚举-接口.md"),
    "utf8",
  );
  const section = doc.match(/^## 5\. 页面路由\n([\s\S]*?)^## 6\./m)?.[1] ?? "";
  assert.notEqual(section, "", "契约 §5 页面路由章节缺失");
  return [...section.matchAll(/```text\n([\s\S]*?)```/g)]
    .flatMap(match => match[1].split(/[·\n]+/))
    .map(value => value.trim())
    .filter(value => value.startsWith("/"));
}

test("CONTRACT_ROUTES 与 C1 契约 §5 逐条一致", () => {
  const expected = contractRoutePaths();
  assert.equal(expected.length, 11);
  assert.deepEqual(CONTRACT_ROUTES.map(route => route.path), expected);
});

test("合同路由表恰好有 11 条", () => {
  assert.equal(CONTRACT_ROUTES.length, 11);
  assert.equal(new Set(CONTRACT_ROUTES.map(route => route.path)).size, 11);
  assert.equal(CONTRACT_ROUTES.filter(route => route.enabled).length, 10);
  assert.equal(CONTRACT_ROUTES.filter(route => !route.enabled).length, 1);
  assert.equal(CONTRACT_ROUTES.filter(route => route.group === "public").length, 5);
  assert.equal(CONTRACT_ROUTES.filter(route => route.group === "auth").length, 6);
});

test("一级导航恰好是合同规定的 4 条", () => {
  assert.deepEqual(
    PRIMARY_NAVIGATION.map(item => item.href),
    ["/workbench", "/reports", "/connectors", "/settings"],
  );
  assert.deepEqual(
    PRIMARY_NAVIGATION.map(item => item.name),
    ["工作台", "报告", "连接器", "设置"],
  );
});

test("运行、资产、项目和任务不得进入主导航", () => {
  const hrefs = [...PRIMARY_NAVIGATION, ...SECONDARY_NAVIGATION].map(item => item.href);
  for (const href of ["/runs", "/assets", "/projects", "/tasks", "/dashboard"]) {
    assert.equal(hrefs.includes(href), false, `${href} 不得进入主导航`);
  }
});

test("没有审批收件箱或通知中心路由", () => {
  const paths = [
    ...CONTRACT_ROUTES.map(route => route.path),
    ...PRIMARY_NAVIGATION.map(item => item.href),
    ...SECONDARY_NAVIGATION.map(item => item.href),
  ];
  for (const forbidden of ["/approvals", "/approval-requests", "/inbox", "/notifications"]) {
    assert.equal(paths.includes(forbidden), false, `${forbidden} 不得存在`);
  }
});

test("动态段名与契约路径一致", () => {
  for (const route of CONTRACT_ROUTES.filter(item => item.dynamicSegment !== null)) {
    assert.equal(route.path.includes(`[${route.dynamicSegment}]`), true);
  }
});

test("公开分享保持禁用且没有页面文件", () => {
  assert.equal(PUBLIC_REPORT_SHARE_ENABLED, false);
  const share = CONTRACT_ROUTES.find(route => route.key === "public-report");
  assert.ok(share);
  assert.equal(share.enabled, false);
  const file = fileURLToPath(new URL(contractRoutePageFile(share), APP_DIR));
  assert.equal(existsSync(file), false, `分享页不得存在：${file}`);
});

test("页面文件助手保留 Next 动态段括号", () => {
  const route = CONTRACT_ROUTES.find(item => item.key === "capability");
  assert.ok(route);
  assert.equal(contractRoutePageFile(route), "capabilities/[toolId]/page.tsx");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/contract-routes.test.ts"`
Expected: FAIL，报 `Cannot find module './contract-routes.ts'`。

- [ ] **Step 3: 写路由注册表**

`apps/scraper-console/src/lib/contract-routes.ts`：

```typescript
/**
 * 11 条合同路由与 4 条一级导航的唯一注册表。
 *
 * 路径来自 PRD §3.3 与契约冻结 v1.1 §5。
 * 动态段名以 B5 已落地的页面为准。
 * 本模块不依赖 React，Node 测试可以直接加载。
 */

export type ContractRouteGroup = "public" | "auth";

export type ContractRoute = {
  readonly key: string;
  readonly path: string;
  readonly group: ContractRouteGroup;
  readonly enabled: boolean;
  readonly dynamicSegment: string | null;
};

export type NavigationItem = {
  readonly name: string;
  readonly href: string;
};

export const PUBLIC_REPORT_SHARE_ENABLED = false;

export const CONTRACT_ROUTES: readonly ContractRoute[] = [
  { key: "home", path: "/", group: "public", enabled: true, dynamicSegment: null },
  {
    key: "capabilities",
    path: "/capabilities",
    group: "public",
    enabled: true,
    dynamicSegment: null,
  },
  {
    key: "capability",
    path: "/capabilities/[toolId]",
    group: "public",
    enabled: true,
    dynamicSegment: "toolId",
  },
  {
    key: "public-report",
    path: "/reports/public/[id]",
    group: "public",
    enabled: PUBLIC_REPORT_SHARE_ENABLED,
    dynamicSegment: "id",
  },
  { key: "docs", path: "/docs", group: "public", enabled: true, dynamicSegment: null },
  { key: "workbench", path: "/workbench", group: "auth", enabled: true, dynamicSegment: null },
  {
    key: "workbench-task",
    path: "/workbench/[taskId]",
    group: "auth",
    enabled: true,
    dynamicSegment: "taskId",
  },
  { key: "reports", path: "/reports", group: "auth", enabled: true, dynamicSegment: null },
  {
    key: "report",
    path: "/reports/[artifactId]",
    group: "auth",
    enabled: true,
    dynamicSegment: "artifactId",
  },
  {
    key: "connectors",
    path: "/connectors",
    group: "auth",
    enabled: true,
    dynamicSegment: null,
  },
  { key: "settings", path: "/settings", group: "auth", enabled: true, dynamicSegment: null },
];

export const PRIMARY_NAVIGATION: readonly NavigationItem[] = [
  { name: "工作台", href: "/workbench" },
  { name: "报告", href: "/reports" },
  { name: "连接器", href: "/connectors" },
  { name: "设置", href: "/settings" },
];

export const SECONDARY_NAVIGATION: readonly NavigationItem[] = [
  { name: "能力目录", href: "/capabilities" },
  { name: "文档", href: "/docs" },
];

/** Next 页面文件相对 `src/app` 的路径。 */
export function contractRoutePageFile(route: ContractRoute): string {
  if (route.path === "/") return "page.tsx";
  return `${route.path.slice(1)}/page.tsx`;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/contract-routes.test.ts"`
Expected: `6 tests passed`。

- [ ] **Step 5: 接入 `routes.ts`**

在 `apps/scraper-console/src/lib/routes.ts` 中删除本文件旧的 `NavigationItem`、`PRIMARY_NAVIGATION`、`SECONDARY_NAVIGATION` 定义，改为：

```typescript
export {
  PRIMARY_NAVIGATION,
  SECONDARY_NAVIGATION,
  type NavigationItem,
} from "./contract-routes";
```

`NEW_ROUTES` 本任务不追加 C14 页面。三张页面分别在 Task 3、Task 7、Task 8 创建，创建时同步登记，避免“路由已声明但没有页面”的测试红灯。

把 `apps/scraper-console/src/components/layout/sidebar.tsx` 顶部品牌链接的 `href="/tools"` 改为 `href="/workbench"`，使点击 Logo 回到唯一任务入口。

在 `ROUTE_REDIRECTS` 中追加：

```typescript
  {
    source: "/dashboard",
    destination: "/workbench",
    permanent: true,
    note: "工作台取代旧概览。",
  },
  {
    source: "/settings/credentials",
    destination: "/connectors",
    permanent: true,
    note: "凭据并入连接器页。",
  },
```

把 `/platforms`、`/skills` 的目标改为 `/capabilities`，把 `/skills/:platformId` 的目标改为 `/capabilities/:platformId`。从 `KEPT_ROUTES` 删除 `/dashboard` 与 `/settings/credentials`，保留：

```typescript
export const KEPT_ROUTES: readonly string[] = [
  "/projects",
  "/projects/[id]",
  "/tasks",
  "/runs",
];
```

- [ ] **Step 6: 更新 `routes.test.ts`**

把“三组路由数量”测试改为：

```typescript
test("the three route groups have explicit sizes", () => {
  assert.equal(KEPT_ROUTES.length, 4);
  // 9 条 B5 新增路由。C14 的三张页面在后续任务创建时各自追加。
  assert.equal(NEW_ROUTES.length, 9);
  assert.equal(
    ROUTE_REDIRECTS.length + KEPT_ROUTES.length + (ROOT_ROUTE ? 1 : 0) + NEW_ROUTES.length,
    23,
  );
});
```

把旧断言 `/platforms -> /tools` 改为 `/platforms -> /capabilities`，`/skills -> /tools` 改为 `/skills -> /capabilities`，`/skills/:platformId -> /tools/:platformId` 改为 `/capabilities/:platformId`。删除旧的“dashboard 在二级导航”断言，改为以下两个测试：

```typescript
test("B5 路由按合同分组", () => {
  const primary = PRIMARY_NAVIGATION.map(item => item.href);
  const secondary = SECONDARY_NAVIGATION.map(item => item.href);
  assert.equal(primary.includes("/workbench"), true);
  assert.equal(primary.includes("/reports"), true);
  assert.equal(primary.includes("/capabilities"), false);
  assert.equal(secondary.includes("/capabilities"), true);
  assert.equal(secondary.includes("/docs"), true);
});

test("dashboard 不再出现在任一导航", () => {
  const hrefs = [...PRIMARY_NAVIGATION, ...SECONDARY_NAVIGATION].map(item => item.href);
  assert.equal(hrefs.includes("/dashboard"), false);
});
```

- [ ] **Step 7: 运行全部前端单元测试**

Run: `pnpm -C apps/scraper-console test`
Expected: 全部通过，`routes.test.ts` 与 `contract-routes.test.ts` 无失败。

- [ ] **Step 8: 提交**

```bash
git add apps/scraper-console/src/lib/contract-routes.ts \
  apps/scraper-console/src/lib/contract-routes.test.ts \
  apps/scraper-console/src/lib/routes.ts \
  apps/scraper-console/src/lib/routes.test.ts \
  apps/scraper-console/src/components/layout/sidebar.tsx
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): register 11 contract routes and 4 primary nav entries"
```

---

### Task 2: Middleware 公开 allowlist

**Files:**
- Create: `apps/scraper-console/src/lib/middleware-policy.ts`
- Create: `apps/scraper-console/src/lib/middleware-policy.test.ts`
- Modify: `apps/scraper-console/src/middleware.ts`
- Modify: `apps/scraper-console/src/app/login/page.tsx`

**Interfaces:**
- Consumes: `contract-routes.ts` 的公开路由集合。
- Produces: `MiddlewareAction`、`isPublicPath(pathname)`、`safeNextPath(value)`、`middlewareAction(pathname, search, hasToken)`。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/middleware-policy.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import {
  isPublicPath,
  middlewareAction,
  safeNextPath,
} from "./middleware-policy.ts";

test("公开 allowlist 只含合同公开路由与登录页", () => {
  for (const path of ["/", "/capabilities", "/capabilities/exa_search", "/docs", "/docs/api", "/reports/public/token", "/login"]) {
    assert.equal(isPublicPath(path), true, `${path} 应公开`);
  }
  for (const path of ["/workbench", "/reports", "/connectors", "/settings", "/runs", "/assets", "/projects"]) {
    assert.equal(isPublicPath(path), false, `${path} 应受保护`);
  }
});

test("相邻前缀不得误判为公开", () => {
  assert.equal(isPublicPath("/capabilities-archive"), false);
  assert.equal(isPublicPath("/docs-private"), false);
  assert.equal(isPublicPath("/reports-public/x"), false);
});

test("无 token 访问受保护页跳到登录并保留 next", () => {
  assert.deepEqual(middlewareAction("/workbench", "?project=x", false), {
    type: "redirect-login",
    next: "/workbench?project=x",
  });
});

test("有 token 访问登录页回到工作台", () => {
  assert.deepEqual(middlewareAction("/login", "", true), {
    type: "redirect-workbench",
  });
});

test("公开页与已登录受保护页直接放行", () => {
  assert.deepEqual(middlewareAction("/capabilities/exa_search", "", false), { type: "next" });
  assert.deepEqual(middlewareAction("/reports", "", true), { type: "next" });
});

test("next 参数只接受同源绝对路径", () => {
  assert.equal(safeNextPath(null), "/workbench");
  assert.equal(safeNextPath(""), "/workbench");
  assert.equal(safeNextPath("https://evil.example"), "/workbench");
  assert.equal(safeNextPath("//evil.example"), "/workbench");
  assert.equal(safeNextPath("/\\evil.example"), "/workbench");
  assert.equal(safeNextPath("/reports?x=1"), "/reports?x=1");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/middleware-policy.test.ts"`
Expected: FAIL，报模块不存在。

- [ ] **Step 3: 写策略与 middleware**

`apps/scraper-console/src/lib/middleware-policy.ts`：

```typescript
/** 公开页的前缀。命中前缀本身或子路径都算公开。 */
const PUBLIC_PREFIXES = ["/capabilities", "/docs", "/reports/public"] as const;

/** 公开的精确路径。 */
const PUBLIC_EXACT_PATHS = new Set(["/", "/login"]);

export type MiddlewareAction =
  | { type: "next" }
  | { type: "redirect-login"; next: string }
  | { type: "redirect-workbench" };

export function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some(
    prefix => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/** 只接受同源绝对路径。拒绝协议相对地址和反斜杠。 */
export function safeNextPath(value: string | null): string {
  if (!value) return "/workbench";
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/workbench";
  }
  return value;
}

export function middlewareAction(
  pathname: string,
  search: string,
  hasToken: boolean,
): MiddlewareAction {
  if (pathname === "/login") {
    return hasToken ? { type: "redirect-workbench" } : { type: "next" };
  }
  if (isPublicPath(pathname)) return { type: "next" };
  if (!hasToken) return { type: "redirect-login", next: `${pathname}${search}` };
  return { type: "next" };
}
```

`apps/scraper-console/src/middleware.ts` 整体替换为：

```typescript
import { NextResponse, type NextRequest } from "next/server";
import { middlewareAction } from "@/lib/middleware-policy";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasToken = Boolean(request.cookies.get("access_token")?.value);
  const action = middlewareAction(pathname, search, hasToken);

  if (action.type === "next") return NextResponse.next();

  if (action.type === "redirect-workbench") {
    return NextResponse.redirect(new URL("/workbench", request.url));
  }

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(action.next)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
```

- [ ] **Step 4: 登录页使用安全 next**

在 `apps/scraper-console/src/app/login/page.tsx` 中：

```typescript
import { safeNextPath } from "@/lib/middleware-policy";
```

把：

```typescript
const nextPath = searchParams.get("next") ?? "/dashboard";
```

改为：

```typescript
const nextPath = safeNextPath(searchParams.get("next"));
```

把 `router.replace(target)` 前的 `target` 逻辑删除，直接使用 `nextPath`：

```typescript
router.replace(nextPath);
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/middleware-policy.test.ts"`
Run: `pnpm -C apps/scraper-console exec tsc --noEmit`
Expected: 测试全过；tsc 无错误。

- [ ] **Step 6: 提交**

```bash
git add apps/scraper-console/src/lib/middleware-policy.ts \
  apps/scraper-console/src/lib/middleware-policy.test.ts \
  apps/scraper-console/src/middleware.ts \
  apps/scraper-console/src/app/login/page.tsx
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): allowlist public routes in middleware"
```

---

### Task 3: 工作台接真实 API

**Files:**
- Modify: `apps/scraper-console/src/lib/api/workbench.ts`
- Create: `apps/scraper-console/src/lib/api/workbench.test.ts`
- Create: `apps/scraper-console/src/lib/workbench-view.ts`
- Create: `apps/scraper-console/src/lib/workbench-view.test.ts`
- Create: `apps/scraper-console/src/components/workbench/task-form.tsx`
- Create: `apps/scraper-console/src/components/workbench/task-list.tsx`
- Create: `apps/scraper-console/src/components/workbench/task-detail.tsx`
- Create: `apps/scraper-console/src/app/workbench/[taskId]/page.tsx`
- Modify: `apps/scraper-console/src/app/workbench/page.tsx`

**Interfaces:**
- Consumes: C4 `WorkbenchTaskCreateRequest`（含 `package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`max_cost_usd/max_pages/max_records`）、`WorkbenchTaskResponse`、`WorkbenchTaskDetailResponse`、`WorkbenchTaskListResponse`、`WorkbenchGateResponse`；`GET /api/projects`。
- Produces: `fetchWorkbenchTasks`、`createWorkbenchTask`、`fetchWorkbenchTask`、`fetchWorkbenchGates`、`resolveWorkbenchState`、`gateLabel`、`FORMAL_MARKETS`、`comparisonLimit`、`canAddComparison`、`buildWorkbenchTaskPayload`。C14 不新增 `overview`、`plans/preview`、`plans/{id}/approve` 客户端，也不新增后端路由。
- 市场固定为 11 个正式市场 `US,GB,DE,FR,IT,ES,IE,NL,BE,AT,PL`，locale 分别为 `en-US,en-GB,de-DE,fr-FR,it-IT,es-ES,en-IE,nl-NL,nl-BE,de-AT,pl-PL`。`JP`/`ja-JP` 不在列表内，不得渲染、不得提交。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/api/workbench.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { workbenchPaths } from "./workbench.ts";

test("工作台路径只使用 C4 已登记路由", () => {
  assert.equal(
    workbenchPaths.tasks({ projectId: "p1", limit: 20 }),
    "/api/workbench/tasks?project_id=p1&limit=20",
  );
  assert.equal(workbenchPaths.create("p1"), "/api/workbench/tasks?project_id=p1");
  assert.equal(workbenchPaths.task("t/1"), "/api/workbench/tasks/t%2F1");
  assert.equal(workbenchPaths.gates("t1"), "/api/workbench/tasks/t1/gates");
  assert.equal("overview" in workbenchPaths, false);
  assert.equal("preview" in workbenchPaths, false);
  assert.equal("approve" in workbenchPaths, false);
});
```

`apps/scraper-console/src/lib/workbench-view.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import {
  FORMAL_MARKETS,
  buildWorkbenchTaskPayload,
  canAddComparison,
  comparisonLimit,
  gateLabel,
  resolveWorkbenchState,
} from "./workbench-view.ts";

test("工作台四态", () => {
  assert.equal(resolveWorkbenchState({ isLoading: true, error: null, count: 0 }), "loading");
  assert.equal(resolveWorkbenchState({ isLoading: false, error: new Error("x"), count: 0 }), "error");
  assert.equal(resolveWorkbenchState({ isLoading: false, error: null, count: 0 }), "empty");
  assert.equal(resolveWorkbenchState({ isLoading: false, error: null, count: 2 }), "ready");
});

test("门禁文案区分通过、待决和阻断", () => {
  assert.equal(gateLabel("pass"), "已通过");
  assert.equal(gateLabel("pending"), "待决定");
  assert.equal(gateLabel("blocked"), "已阻断");
  assert.equal(gateLabel("expired"), "已过期");
  assert.equal(gateLabel("unknown"), "unknown");
});

test("市场列表只含 11 个正式市场", () => {
  assert.deepEqual(
    FORMAL_MARKETS.map(market => market.code),
    ["US", "GB", "DE", "FR", "IT", "ES", "IE", "NL", "BE", "AT", "PL"],
  );
  assert.deepEqual(
    Object.fromEntries(FORMAL_MARKETS.map(market => [market.code, market.locale])),
    {
      US: "en-US",
      GB: "en-GB",
      DE: "de-DE",
      FR: "fr-FR",
      IT: "it-IT",
      ES: "es-ES",
      IE: "en-IE",
      NL: "nl-NL",
      BE: "nl-BE",
      AT: "de-AT",
      PL: "pl-PL",
    },
  );
  assert.equal(FORMAL_MARKETS.some(market => market.code === "JP"), false);
  assert.equal(FORMAL_MARKETS.some(market => market.locale.startsWith("ja")), false);
});

test("Quick 限制 1 主 + 最多 1 对比，Standard 最多 3 对比", () => {
  assert.equal(comparisonLimit("quick"), 1);
  assert.equal(comparisonLimit("standard"), 3);
  assert.equal(canAddComparison("quick", []), true);
  assert.equal(canAddComparison("quick", ["GB"]), false);
  assert.equal(canAddComparison("standard", ["GB", "FR"]), true);
  assert.equal(canAddComparison("standard", ["GB", "FR", "IT"]), false);
});

test("提交载荷带 package_type、主对比市场与对应 locale", () => {
  const payload = buildWorkbenchTaskPayload({
    package_type: "standard",
    brand: " Momcozy ",
    category: " breast_pump ",
    competitors: "Medela, Spectra",
    primary_market: "DE",
    comparison_markets: ["FR", "IT", "ES"],
    window: { start: "2026-07-01", end: "2026-09-30" },
    decision_question: "德国市场是否值得进入？",
    does_not_answer: "不推断销量\n不推断市场份额",
  });
  assert.equal(payload.package_type, "standard");
  assert.equal(payload.brand, "Momcozy");
  assert.equal(payload.primary_market, "DE");
  assert.deepEqual(payload.comparison_markets, ["FR", "IT", "ES"]);
  assert.deepEqual(payload.locale_by_market, {
    DE: "de-DE",
    FR: "fr-FR",
    IT: "it-IT",
    ES: "es-ES",
  });
  assert.deepEqual(payload.competitors, ["Medela", "Spectra"]);
  assert.equal("markets" in payload, false);
});

test("超出档位上限或提交非正式市场时拒绝组包", () => {
  const base = {
    package_type: "quick" as const,
    brand: "Momcozy",
    category: "breast_pump",
    competitors: "",
    primary_market: "US",
    window: { start: "2026-07-01", end: "2026-09-30" },
    decision_question: "美国市场是否值得进入？",
    does_not_answer: "",
  };
  assert.throws(
    () => buildWorkbenchTaskPayload({ ...base, comparison_markets: ["GB", "DE"] }),
    /market_selection_limit/,
  );
  assert.throws(
    () => buildWorkbenchTaskPayload({ ...base, primary_market: "JP", comparison_markets: [] }),
    /market_not_formal/,
  );
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/api/workbench.test.ts" "src/lib/workbench-view.test.ts"`
Expected: FAIL，模块或导出不存在。

- [ ] **Step 3: 修改 API 客户端**

`apps/scraper-console/src/lib/api/workbench.ts`（Modify）：

保留文件已有的 `fetchWorkbenchSnapshot` 导出与类型，不要删除。只替换 C4 任务路由相关部分：

```typescript
import { apiFetch } from "./client";

// 保留现有 fetchWorkbenchSnapshot 及其类型，不在此重复定义。

export type WorkbenchTask = {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  owner_id: string;
  brand: string;
  category: string;
  competitors: string[];
  package_type: "quick" | "standard";
  primary_market: string;
  comparison_markets: string[];
  markets: string[];
  locale_by_market: Record<string, string>;
  window_start: string;
  window_end: string;
  decision_question: string;
  does_not_answer: string[];
  acceptance_contact_id: string | null;
  max_cost_usd: string | number | null;
  max_pages: number | null;
  max_records: number | null;
  task_type: "T1" | "T2" | "T3" | "T4" | "T5" | null;
  task_type_confidence: number | null;
  status: "draft" | "submitted" | "cancelled";
  created_at: string;
  updated_at: string;
};

export type WorkbenchTaskList = { items: WorkbenchTask[] };

export type WorkbenchGate = {
  authorization_id: string;
  gate_id: string;
  gate_status: "pending" | "pass" | "fail" | "blocked" | "expired";
  market_code: string | null;
  reason_code: string | null;
  gap: Record<string, unknown> | null;
};

export type WorkbenchTaskDetail = {
  task: WorkbenchTask;
  workflow_versions: Array<Record<string, unknown>>;
  runs: Array<Record<string, unknown>>;
  gates: WorkbenchGate[];
};

export type WorkbenchTaskCreatePayload = {
  package_type: "quick" | "standard";
  primary_market: string;
  comparison_markets: string[];
  brand: string;
  category: string;
  competitors?: string[];
  locale_by_market: Record<string, string>;
  window: { start: string; end: string };
  decision_question: string;
  does_not_answer?: string[];
};

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const workbenchPaths = {
  tasks: (params: { projectId: string; status?: string; limit?: number; offset?: number }) =>
    `/api/workbench/tasks${query({
      project_id: params.projectId,
      status: params.status,
      limit: params.limit,
      offset: params.offset,
    })}`,
  create: (projectId: string) =>
    `/api/workbench/tasks${query({ project_id: projectId })}`,
  task: (taskId: string) => `/api/workbench/tasks/${encodeURIComponent(taskId)}`,
  gates: (taskId: string) =>
    `/api/workbench/tasks/${encodeURIComponent(taskId)}/gates`,
};

export function fetchWorkbenchTasks(params: {
  projectId: string;
  limit?: number;
}): Promise<WorkbenchTaskList> {
  return apiFetch<WorkbenchTaskList>(workbenchPaths.tasks(params));
}

export function createWorkbenchTask(
  projectId: string,
  payload: WorkbenchTaskCreatePayload,
): Promise<WorkbenchTask> {
  return apiFetch<WorkbenchTask>(workbenchPaths.create(projectId), {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(payload),
  });
}

export function fetchWorkbenchTask(taskId: string): Promise<WorkbenchTaskDetail> {
  return apiFetch<WorkbenchTaskDetail>(workbenchPaths.task(taskId));
}

export function fetchWorkbenchGates(taskId: string): Promise<WorkbenchGate[]> {
  return apiFetch<WorkbenchGate[]>(workbenchPaths.gates(taskId));
}
```

- [ ] **Step 3b: 写内联批准资格纯函数**

`apps/scraper-console/src/lib/inline-approvals.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import {
  approvalKindFromGate,
  approvalKindLabel,
  approvalPolicyText,
  canDecideApproval,
  normalizeWorkspaceRole,
} from "./inline-approvals.ts";

const owner = { user_id: "u-owner", role: "owner" as const, principal: "human_session" as const };
const admin = { user_id: "u-admin", role: "admin" as const, principal: "human_session" as const };
const member = { user_id: "u-member", role: "member" as const, principal: "human_session" as const };

test("只有非发起人的 owner 或 admin 人类会话可以批准", () => {
  for (const kind of ["overage", "addon", "key_change"] as const) {
    const request = { kind, requester_user_id: "u-requester", status: "pending" as const };
    assert.equal(canDecideApproval(request, { ...owner, user_id: "u-requester" }), false);
    assert.equal(canDecideApproval(request, owner), true);
    assert.equal(canDecideApproval(request, admin), true);
    assert.equal(canDecideApproval(request, member), false);
    assert.equal(canDecideApproval(request, { ...owner, principal: "agent" }), false);
    assert.equal(canDecideApproval(request, { ...admin, principal: "project_key" }), false);
    assert.equal(canDecideApproval({ ...request, status: "approved" }, owner), false);
    assert.equal(canDecideApproval({ ...request, status: "rejected" }, admin), false);
  }
});

test("工作区角色值收敛到 owner/admin/member", () => {
  assert.equal(normalizeWorkspaceRole("owner"), "owner");
  assert.equal(normalizeWorkspaceRole("admin"), "admin");
  assert.equal(normalizeWorkspaceRole("member"), "member");
  assert.equal(normalizeWorkspaceRole("auditor"), "member");
  assert.equal(normalizeWorkspaceRole(null), "member");
});

test("G-Cost 的 approval_required 门禁映射为超额", () => {
  assert.equal(
    approvalKindFromGate({ gate_id: "budget.overage", gate_status: "approval_required" }),
    "overage",
  );
  assert.equal(
    approvalKindFromGate({ gate_id: "budget.addon", gate_status: "approval_required" }),
    "addon",
  );
  assert.equal(
    approvalKindFromGate({ gate_id: "project_key.change", gate_status: "approval_required" }),
    "key_change",
  );
  assert.equal(approvalKindFromGate({ gate_id: "budget.overage", gate_status: "pass" }), null);
  assert.equal(approvalKindLabel("overage"), "超额批准");
  assert.equal(approvalPolicyText("key_change"), "仅 owner/admin 可批准，发起人不能自批。");
});
```

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/inline-approvals.test.ts"`
Expected: FAIL，报模块不存在。

`apps/scraper-console/src/lib/inline-approvals.ts`：

```typescript
export type ApprovalKind = "overage" | "addon" | "key_change";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type WorkspaceRole = "owner" | "admin" | "member";
export type ApprovalPrincipal = "human_session" | "agent" | "project_key";

export type ApprovalRequest = {
  kind: ApprovalKind;
  requester_user_id: string;
  status: ApprovalStatus;
};

export type ApprovalActor = {
  user_id: string;
  role: WorkspaceRole;
  principal: ApprovalPrincipal;
};

export function normalizeWorkspaceRole(value: unknown): WorkspaceRole {
  if (value === "owner" || value === "admin") return value;
  return "member";
}

export function canDecideApproval(
  request: ApprovalRequest,
  actor: ApprovalActor,
): boolean {
  if (request.status !== "pending") return false;
  if (actor.principal !== "human_session") return false;
  if (actor.user_id === request.requester_user_id) return false;
  return actor.role === "owner" || actor.role === "admin";
}

export function approvalKindFromGate(gate: {
  gate_id: string;
  gate_status: string;
}): ApprovalKind | null {
  if (gate.gate_status !== "approval_required") return null;
  if (gate.gate_id.includes("addon")) return "addon";
  if (gate.gate_id.includes("key")) return "key_change";
  return "overage";
}

const APPROVAL_KIND_LABELS: Record<ApprovalKind, string> = {
  overage: "超额批准",
  addon: "加购批准",
  key_change: "密钥变更批准",
};

const APPROVAL_POLICY_TEXT: Record<ApprovalKind, string> = {
  overage: "仅 owner/admin 可批准，发起人不能自批。",
  addon: "仅 owner/admin 可批准，发起人不能自批。",
  key_change: "仅 owner/admin 可批准，发起人不能自批。",
};

export function approvalKindLabel(kind: ApprovalKind): string {
  return APPROVAL_KIND_LABELS[kind];
}

export function approvalPolicyText(kind: ApprovalKind): string {
  return APPROVAL_POLICY_TEXT[kind];
}
```

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/inline-approvals.test.ts"`
Expected: `3 tests passed`。该纯函数只判定资格；Task 8A 的客户端调用 C1 已登记的批准写路径。服务端授权仍由 C3/C5 负责。

- [ ] **Step 4: 写视图状态纯函数**

`apps/scraper-console/src/lib/workbench-view.ts`：

```typescript
import type { WorkbenchTaskCreatePayload } from "./api/workbench";

export type WorkbenchState = "loading" | "error" | "empty" | "ready";

export function resolveWorkbenchState(input: {
  isLoading: boolean;
  error: Error | null;
  count: number;
}): WorkbenchState {
  if (input.isLoading) return "loading";
  if (input.error) return "error";
  if (input.count === 0) return "empty";
  return "ready";
}

const GATE_LABELS: Record<string, string> = {
  pass: "已通过",
  pending: "待决定",
  fail: "未通过",
  blocked: "已阻断",
  expired: "已过期",
};

export function gateLabel(status: string): string {
  return GATE_LABELS[status] ?? "unknown";
}

export type PackageType = "quick" | "standard";

/** 正式市场与 locale 的唯一来源。JP/ja-JP 不是正式市场。 */
export const FORMAL_MARKETS = [
  { code: "US", locale: "en-US" },
  { code: "GB", locale: "en-GB" },
  { code: "DE", locale: "de-DE" },
  { code: "FR", locale: "fr-FR" },
  { code: "IT", locale: "it-IT" },
  { code: "ES", locale: "es-ES" },
  { code: "IE", locale: "en-IE" },
  { code: "NL", locale: "nl-NL" },
  { code: "BE", locale: "nl-BE" },
  { code: "AT", locale: "de-AT" },
  { code: "PL", locale: "pl-PL" },
] as const;

const COMPARISON_LIMITS: Record<PackageType, number> = {
  quick: 1,
  standard: 3,
};

/** Quick 固定 1 个主市场，最多 1 个对比市场；Standard 最多 3 个对比市场。 */
export function comparisonLimit(packageType: PackageType): number {
  return COMPARISON_LIMITS[packageType];
}

export function canAddComparison(
  packageType: PackageType,
  comparisonMarkets: readonly string[],
): boolean {
  return comparisonMarkets.length < comparisonLimit(packageType);
}

function localeForMarket(code: string): string {
  const market = FORMAL_MARKETS.find(item => item.code === code);
  if (!market) throw new Error(`market_not_formal:${code}`);
  return market.locale;
}

export function buildWorkbenchTaskPayload(input: {
  package_type: PackageType;
  brand: string;
  category: string;
  competitors: string;
  primary_market: string;
  comparison_markets: readonly string[];
  window: { start: string; end: string };
  decision_question: string;
  does_not_answer: string;
}): WorkbenchTaskCreatePayload {
  if (input.comparison_markets.length > comparisonLimit(input.package_type)) {
    throw new Error("market_selection_limit");
  }
  const markets = [input.primary_market, ...input.comparison_markets];
  if (new Set(markets).size !== markets.length) {
    throw new Error("market_role_conflict");
  }
  return {
    package_type: input.package_type,
    primary_market: input.primary_market,
    comparison_markets: [...input.comparison_markets],
    brand: input.brand.trim(),
    category: input.category.trim(),
    competitors: input.competitors
      .split(",")
      .map(value => value.trim())
      .filter(Boolean),
    locale_by_market: Object.fromEntries(
      markets.map(code => [code, localeForMarket(code)]),
    ),
    window: input.window,
    decision_question: input.decision_question.trim(),
    does_not_answer: input.does_not_answer
      .split("\n")
      .map(value => value.trim())
      .filter(Boolean),
  };
}
```

- [ ] **Step 5: 写七槽位表单**

`apps/scraper-console/src/components/workbench/task-form.tsx`：

```tsx
"use client";

import { type FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { createWorkbenchTask } from "@/lib/api/workbench";
import {
  FORMAL_MARKETS,
  buildWorkbenchTaskPayload,
  canAddComparison,
  comparisonLimit,
  type PackageType,
} from "@/lib/workbench-view";

const PACKAGE_TYPES: ReadonlyArray<{ value: PackageType; label: string; hint: string }> = [
  { value: "quick", label: "Quick", hint: "1 个主市场 + 最多 1 个对比市场" },
  { value: "standard", label: "Standard", hint: "1 个主市场 + 最多 3 个对比市场" },
];

export function WorkbenchTaskForm({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [packageType, setPackageType] = useState<PackageType>("quick");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [primaryMarket, setPrimaryMarket] = useState("US");
  const [comparisonMarkets, setComparisonMarkets] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [doesNotAnswer, setDoesNotAnswer] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createWorkbenchTask(
        projectId,
        buildWorkbenchTaskPayload({
          package_type: packageType,
          brand,
          category,
          competitors,
          primary_market: primaryMarket,
          comparison_markets: comparisonMarkets,
          window: { start, end },
          decision_question: question,
          does_not_answer: doesNotAnswer,
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workbench-tasks", projectId] });
      setBrand("");
      setCategory("");
      setCompetitors("");
      setComparisonMarkets([]);
      setQuestion("");
      setDoesNotAnswer("");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  function selectPackageType(next: PackageType) {
    setPackageType(next);
    setComparisonMarkets(current => current.slice(0, comparisonLimit(next)));
  }

  function selectPrimaryMarket(code: string) {
    setPrimaryMarket(code);
    setComparisonMarkets(current => current.filter(item => item !== code));
  }

  function toggleComparisonMarket(code: string) {
    if (code === primaryMarket) return;
    setComparisonMarkets(current => {
      if (current.includes(code)) return current.filter(item => item !== code);
      return canAddComparison(packageType, current) ? [...current, code] : current;
    });
  }

  return (
    <form
      onSubmit={submit}
      data-testid="workbench-task-form"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5"
    >
      <div className="flex items-center gap-2">
        <Plus size={16} className="text-[var(--action-primary)]" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">新建任务包</h2>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          品牌
          <input required value={brand} onChange={event => setBrand(event.target.value)}
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          品类 ID
          <input required value={category} onChange={event => setCategory(event.target.value)}
            placeholder="取自 maternal_v1.json"
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          竞品（逗号分隔）
          <input value={competitors} onChange={event => setCompetitors(event.target.value)}
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          决策问题
          <input required minLength={8} value={question} onChange={event => setQuestion(event.target.value)}
            placeholder="必须包含问号"
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          开始日期
          <input required type="date" value={start} onChange={event => setStart(event.target.value)}
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
        <label className="grid gap-1 text-xs text-[var(--text-secondary)]">
          结束日期
          <input required type="date" value={end} onChange={event => setEnd(event.target.value)}
            className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm" />
        </label>
      </div>
      <fieldset className="mt-3">
        <legend className="text-xs text-[var(--text-secondary)]">任务包档位</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {PACKAGE_TYPES.map(option => (
            <button key={option.value} type="button"
              data-testid="workbench-package-type-option"
              data-package-type={option.value}
              title={option.hint}
              aria-pressed={packageType === option.value}
              onClick={() => selectPackageType(option.value)}
              className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs aria-pressed:bg-[var(--action-primary)] aria-pressed:text-[var(--text-inverse)]">
              {option.label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          {PACKAGE_TYPES.find(option => option.value === packageType)?.hint}
        </p>
      </fieldset>
      <fieldset className="mt-3">
        <legend className="text-xs text-[var(--text-secondary)]">主市场（必选 1 个）</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {FORMAL_MARKETS.map(market => (
            <button key={market.code} type="button"
              data-testid="workbench-primary-market"
              data-market-code={market.code}
              aria-pressed={primaryMarket === market.code}
              onClick={() => selectPrimaryMarket(market.code)}
              className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs aria-pressed:bg-[var(--action-primary)] aria-pressed:text-[var(--text-inverse)]">
              {market.code}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset className="mt-3">
        <legend className="text-xs text-[var(--text-secondary)]">
          对比市场（{packageType === "quick" ? "最多 1 个" : "最多 3 个"}）
        </legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {FORMAL_MARKETS.map(market => {
            const selected = comparisonMarkets.includes(market.code);
            const disabled =
              market.code === primaryMarket ||
              (!selected && !canAddComparison(packageType, comparisonMarkets));
            return (
              <button key={market.code} type="button"
                data-testid="workbench-comparison-market"
                data-market-code={market.code}
                aria-pressed={selected}
                disabled={disabled}
                onClick={() => toggleComparisonMarket(market.code)}
                className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs aria-pressed:bg-[var(--action-primary)] aria-pressed:text-[var(--text-inverse)] disabled:opacity-40">
                {market.code}
              </button>
            );
          })}
        </div>
      </fieldset>
      <label className="mt-3 grid gap-1 text-xs text-[var(--text-secondary)]">
        不回答的问题（每行一条）
        <textarea value={doesNotAnswer} onChange={event => setDoesNotAnswer(event.target.value)}
          className="min-h-20 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 py-2 text-sm" />
      </label>
      {mutation.error ? (
        <p role="alert" className="mt-3 text-xs text-[var(--state-danger)]">
          创建失败：{mutation.error.message}
        </p>
      ) : null}
      <button type="submit" data-testid="workbench-submit-task" disabled={mutation.isPending}
        className="mt-4 inline-flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] disabled:opacity-60">
        {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
        创建任务包
      </button>
    </form>
  );
}
```

- [ ] **Step 6: 写列表与详情**

`apps/scraper-console/src/components/workbench/task-list.tsx` 与详情见现有文件；列表保持 `data-testid="workbench-task-row"`，详情使用：

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchWorkbenchGates, fetchWorkbenchTask } from "@/lib/api/workbench";
import { gateLabel } from "@/lib/workbench-view";

export function WorkbenchTaskDetail({ taskId }: { taskId: string }) {
  const task = useQuery({
    queryKey: ["workbench-task", taskId],
    queryFn: () => fetchWorkbenchTask(taskId),
  });
  const gates = useQuery({
    queryKey: ["workbench-gates", taskId],
    queryFn: () => fetchWorkbenchGates(taskId),
    enabled: task.isSuccess,
  });

  if (task.isLoading) return <p className="text-sm text-[var(--text-tertiary)]">加载任务…</p>;
  if (task.error || !task.data) {
    return <p role="alert" className="text-sm text-[var(--state-danger)]">任务不存在或无权访问。</p>;
  }
  const gateRows = gates.data ?? task.data.gates;
  return (
    <section data-testid="workbench-task-detail" className="grid gap-4">
      <h1 className="text-lg font-semibold">{task.data.task.brand}</h1>
      <p className="text-sm text-[var(--text-secondary)]">{task.data.task.decision_question}</p>
      <div>
        <h2 className="text-sm font-semibold">门禁</h2>
        {gates.error ? (
          <p role="alert" className="mt-2 text-xs text-[var(--state-danger)]">
            门禁读取失败：{gates.error.message}
          </p>
        ) : gateRows.length === 0 ? (
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">暂无门禁。</p>
        ) : (
          <ul className="mt-2 grid gap-2">
            {gateRows.map(gate => (
              <li key={gate.gate_id} data-testid="workbench-gate" className="flex justify-between text-sm">
                <span>{gate.gate_id}</span>
                <span>{gateLabel(gate.gate_status)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: 写工作台页面**

`apps/scraper-console/src/app/workbench/page.tsx`：

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { WorkbenchTaskForm } from "@/components/workbench/task-form";
import { WorkbenchTaskList } from "@/components/workbench/task-list";
import { fetchProjects } from "@/lib/api/projects";
import { fetchWorkbenchTasks } from "@/lib/api/workbench";
import { resolveWorkbenchState } from "@/lib/workbench-view";

export default function WorkbenchPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const projectId = projects.data?.[0]?.id ?? "";
  const tasks = useQuery({
    queryKey: ["workbench-tasks", projectId],
    queryFn: () => fetchWorkbenchTasks({ projectId, limit: 20 }),
    enabled: Boolean(projectId),
  });
  const rows = tasks.data?.items ?? [];
  const state = resolveWorkbenchState({
    isLoading: projects.isLoading || tasks.isLoading,
    error: (projects.error as Error | null) ?? (tasks.error as Error | null),
    count: rows.length,
  });

  return (
    <AppShell title="工作台" description="任务包、计划与门禁">
      <div data-testid="workbench-page" className="grid gap-4">
        {state === "loading" ? <p className="text-sm text-[var(--text-tertiary)]">加载中…</p> : null}
        {state === "error" ? <p role="alert" className="text-sm text-[var(--state-danger)]">加载失败</p> : null}
        {state === "empty" ? <p className="text-sm text-[var(--text-tertiary)]">暂无任务包。</p> : null}
        {state === "ready" ? <WorkbenchTaskList tasks={rows} /> : null}
        {projectId ? <WorkbenchTaskForm projectId={projectId} /> : null}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 8: 创建任务详情页**

`apps/scraper-console/src/app/workbench/[taskId]/page.tsx`：

```tsx
import { WorkbenchTaskDetail } from "@/components/workbench/task-detail";

export default async function WorkbenchTaskPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return <WorkbenchTaskDetail taskId={taskId} />;
}
```

- [ ] **Step 9: 运行门禁**

Run:
```bash
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console exec tsc --noEmit
pnpm -C apps/scraper-console lint
```
Expected: 全部通过。

- [ ] **Step 10: 提交**

```bash
git add apps/scraper-console/src/lib/api/workbench.ts \
  apps/scraper-console/src/lib/api/workbench.test.ts \
  apps/scraper-console/src/lib/workbench-view.ts \
  apps/scraper-console/src/lib/workbench-view.test.ts \
  apps/scraper-console/src/components/workbench \
  apps/scraper-console/src/app/workbench
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): wire workbench to c4 task api"
```

---

### Task 4: 运行页接真实步骤 API

**Files:**
- Modify: `apps/scraper-console/src/lib/api/runs.ts`
- Create: `apps/scraper-console/src/lib/runs-view.ts`
- Create: `apps/scraper-console/src/lib/runs-view.test.ts`
- Modify: `apps/scraper-console/src/app/runs/page.tsx`
- Modify: `apps/scraper-console/src/app/runs/[runId]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/tasks/runs`、`GET /api/runs/{run_id}`、`GET /api/runs/{run_id}/steps`。
- Produces: `RunStep`、`fetchRunSteps(runId)`、`resolveRunsState`、`stepStatusLabel`。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/runs-view.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { resolveRunsState, stepStatusLabel } from "./runs-view.ts";

test("运行列表四态", () => {
  assert.equal(resolveRunsState({ isLoading: true, error: null, count: 0 }), "loading");
  assert.equal(resolveRunsState({ isLoading: false, error: new Error("x"), count: 0 }), "error");
  assert.equal(resolveRunsState({ isLoading: false, error: null, count: 0 }), "empty");
  assert.equal(resolveRunsState({ isLoading: false, error: null, count: 1 }), "ready");
});

test("步骤状态使用契约七值", () => {
  assert.equal(stepStatusLabel("pending"), "待执行");
  assert.equal(stepStatusLabel("running"), "执行中");
  assert.equal(stepStatusLabel("success"), "成功");
  assert.equal(stepStatusLabel("empty"), "空结果");
  assert.equal(stepStatusLabel("config_gated"), "缺配置");
  assert.equal(stepStatusLabel("failed"), "失败");
  assert.equal(stepStatusLabel("skipped"), "跳过");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/runs-view.test.ts"`
Expected: FAIL，报模块不存在。

- [ ] **Step 3: 增加步骤客户端**

在 `apps/scraper-console/src/lib/api/runs.ts` 追加：

```typescript
export type RunStep = {
  id: string;
  run_id: string;
  step_index: number;
  endpoint_type: string;
  collector_type: string;
  task_run_id: string | null;
  status: "pending" | "running" | "success" | "empty" | "config_gated" | "failed" | "skipped";
  outcome: "success" | "empty" | "config_gated" | "failed" | null;
  records_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export async function fetchRunSteps(runId: string): Promise<RunStep[]> {
  return apiFetch<RunStep[]>(`/api/runs/${encodeURIComponent(runId)}/steps`);
}
```

`apps/scraper-console/src/lib/runs-view.ts`：

```typescript
export type RunsPageState = "loading" | "error" | "empty" | "ready";

export function resolveRunsState(input: {
  isLoading: boolean;
  error: unknown;
  count: number;
}): RunsPageState {
  if (input.isLoading) return "loading";
  if (input.error) return "error";
  if (input.count === 0) return "empty";
  return "ready";
}

const STEP_LABELS: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  empty: "空结果",
  config_gated: "缺配置",
  failed: "失败",
  skipped: "跳过",
};

export function stepStatusLabel(status: string): string {
  return STEP_LABELS[status] ?? status;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/runs-view.test.ts"`
Expected: `2 tests passed`。

- [ ] **Step 5: 在运行详情页增加步骤时间线**

在 `apps/scraper-console/src/app/runs/[runId]/page.tsx` 的 imports 中加入：

```typescript
import { fetchRunSteps } from "@/lib/api/runs";
import { stepStatusLabel } from "@/lib/runs-view";
```

在既有运行查询后加入：

```typescript
  const steps = useQuery({
    queryKey: ["run-steps", runId],
    queryFn: () => fetchRunSteps(runId),
    enabled: Boolean(runId),
  });
```

在页面主内容中插入：

```tsx
      <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">步骤</h2>
        {steps.isLoading ? (
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">加载步骤…</p>
        ) : steps.error ? (
          <p role="alert" className="mt-2 text-xs text-[var(--state-danger)]">
            步骤读取失败：{steps.error.message}
          </p>
        ) : (steps.data ?? []).length === 0 ? (
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">暂无步骤记录。</p>
        ) : (
          <ol className="mt-3 grid gap-2">
            {steps.data?.map(step => (
              <li key={step.id} className="flex items-center justify-between text-xs">
                <span className="font-mono">
                  {step.step_index}. {step.endpoint_type}
                </span>
                <span className="text-[var(--text-secondary)]">
                  {stepStatusLabel(step.status)} · {step.records_count} 条
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
```

- [ ] **Step 6: 运行页使用四态**

在 `apps/scraper-console/src/app/runs/page.tsx` 中导入：

```typescript
import { resolveRunsState } from "@/lib/runs-view";
```

在 `const { data, isLoading, error, refetch, isFetching } = useQuery(...)` 后加入：

```typescript
  const runsState = resolveRunsState({
    isLoading,
    error,
    count: data?.length ?? 0,
  });
```

把现有 `error` 与空列表分支改为使用 `runsState`。当 `runsState === "error"` 时显示错误；`"empty"` 时显示“暂无运行”；`"ready"` 时渲染列表。给页面根容器加 `data-testid="runs-page"`。

- [ ] **Step 7: 运行门禁**

Run: `pnpm -C apps/scraper-console test`
Run: `pnpm -C apps/scraper-console exec tsc --noEmit`
Expected: 全部通过。

- [ ] **Step 8: 提交**

```bash
git add apps/scraper-console/src/lib/api/runs.ts \
  apps/scraper-console/src/lib/runs-view.ts \
  apps/scraper-console/src/lib/runs-view.test.ts \
  apps/scraper-console/src/app/runs
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): show governed run steps from real API"
```

---

### Task 5: 报告页接合同与证据引用

**Files:**
- Modify: `apps/scraper-console/src/lib/api/reports.ts`
- Modify: `apps/scraper-console/src/lib/reports-view.ts`
- Create: `apps/scraper-console/src/lib/reports-view.test.ts`（若尚未存在）
- Modify: `apps/scraper-console/src/app/reports/[artifactId]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/reports`、`GET /api/reports/{report_id}`、`GET /api/reports/{report_id}/contract`。合同 JSON 已包含 `claims`、`evidences` 与 `artifact`；C14 不调用未登记的 `/evidence-references`。
- Produces: `evidenceReferencesFromContract(contract) -> ReportEvidenceReference[]`。

- [ ] **Step 1: 写失败测试**

在 `apps/scraper-console/src/lib/reports-view.test.ts` 增加：

```typescript
import { evidenceReferencesFromContract } from "./reports-view.ts";

test("从合同 JSON 提取 Claim 与证据引用，不请求额外端点", () => {
  const references = evidenceReferencesFromContract({
    claims: [
      { claim_id: "c1", text: "需求增长", claim_status: "confirmed", evidence_ids: ["e1", "e2"] },
    ],
    evidences: [
      { evidence_id: "e1", claim_id: "c1", role: "support", evidence_grade: "A" },
      { evidence_id: "e2", claim_id: "c1", role: "context", evidence_grade: "B" },
    ],
  });
  assert.equal(references.length, 1);
  assert.equal(references[0].claim_id, "c1");
  assert.equal(references[0].evidences.length, 2);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/reports-view.test.ts"`
Expected: FAIL，`evidenceReferencesFromContract` 未导出。

- [ ] **Step 3: 增加纯函数**

在 `apps/scraper-console/src/lib/reports-view.ts` 追加：

```typescript
export type ReportEvidenceReference = {
  claim_id: string;
  text: string;
  claim_status: string;
  evidences: Array<Record<string, unknown>>;
};

type ContractLike = {
  claims?: Array<Record<string, unknown>>;
  evidences?: Array<Record<string, unknown>>;
};

export function evidenceReferencesFromContract(
  contract: ContractLike,
): ReportEvidenceReference[] {
  const evidenceById = new Map(
    (contract.evidences ?? []).map(item => [String(item.evidence_id ?? ""), item]),
  );
  return (contract.claims ?? []).map(claim => {
    const ids = Array.isArray(claim.evidence_ids)
      ? claim.evidence_ids.map(String)
      : [];
    return {
      claim_id: String(claim.claim_id ?? ""),
      text: String(claim.text ?? ""),
      claim_status: String(claim.claim_status ?? ""),
      evidences: ids
        .map(id => evidenceById.get(id))
        .filter((item): item is Record<string, unknown> => Boolean(item)),
    };
  });
}
```

- [ ] **Step 4: 在报告阅读页使用合同数据**

`apps/scraper-console/src/app/reports/[artifactId]/page.tsx` 已有合同查询。删除任何 `fetchReportEvidenceReferences` 调用；改为：

```tsx
import { evidenceReferencesFromContract } from "@/lib/reports-view";

const references = evidenceReferencesFromContract(contractQuery.data ?? {});
```

在合同首屏后加入：

```tsx
<section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
  <h2 className="text-sm font-semibold text-[var(--text-primary)]">证据引用</h2>
  {references.length === 0 ? (
    <p className="mt-2 text-xs text-[var(--text-tertiary)]">暂无证据引用。</p>
  ) : (
    <ul className="mt-3 grid gap-2 text-xs">
      {references.map(reference => (
        <li key={reference.claim_id} className="flex items-center justify-between">
          <span>{reference.text || "Claim"}</span>
          <span className="text-[var(--text-secondary)]">
            {reference.evidences.length} 条证据 · {reference.claim_status}
          </span>
        </li>
      ))}
    </ul>
  )}
</section>
```

合同 404 时页面显示 `contractAbsenceText` 的明确缺口；报告 404 时显示固定文案 `报告不存在或无权访问`，不得显示假 Claim。

- [ ] **Step 5: 运行门禁**

给报告列表页根容器加 `data-testid="reports-page"`，给报告阅读页根容器加 `data-testid="report-detail"`。

Run: `pnpm -C apps/scraper-console test`
Run: `pnpm -C apps/scraper-console exec tsc --noEmit`
Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add apps/scraper-console/src/lib/reports-view.ts \
  apps/scraper-console/src/lib/reports-view.test.ts \
  apps/scraper-console/src/lib/api/reports.ts \
  apps/scraper-console/src/app/reports/page.tsx \
  "apps/scraper-console/src/app/reports/[artifactId]/page.tsx"
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): derive report evidence from contract"
```

---

### Task 6: 资产页四态、质量列与质量页签

**Files:**
- Create: `apps/scraper-console/src/lib/assets-view.ts`
- Create: `apps/scraper-console/src/lib/assets-view.test.ts`
- Create: `apps/scraper-console/src/lib/assets-quality.ts`
- Create: `apps/scraper-console/src/lib/assets-quality.test.ts`
- Create: `apps/scraper-console/e2e/assets-quality.spec.ts`
- Modify: `apps/scraper-console/src/lib/api/datasets.ts`
- Modify: `apps/scraper-console/src/app/assets/page.tsx`
- Modify: `apps/scraper-console/src/app/assets/records/page.tsx`
- Modify: `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx`

**Interfaces:**
- Consumes: `GET /api/automation/product-datasets`、`GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/preview`、`GET /api/raw-records`。质量字段来自 C8：`latest_version.quality_status`、`task_id`、`market`、`schema_hash`、`content_sha256`；预览的 `quality_assessment` 与 `data_gaps`。C8 依赖 C6 的 `run.completed`；C14 不重算质量。
- Produces: `resolveAssetsState`、`qualityStatusLabel`、`qualitySampleLabel`、`QualityAssessment`、`QualityDataGap`。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/assets-view.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { resolveAssetsState } from "./assets-view.ts";

test("资产页四态", () => {
  assert.equal(resolveAssetsState({ isLoading: true, error: null, count: 0 }), "loading");
  assert.equal(resolveAssetsState({ isLoading: false, error: new Error("x"), count: 0 }), "error");
  assert.equal(resolveAssetsState({ isLoading: false, error: null, count: 0 }), "empty");
  assert.equal(resolveAssetsState({ isLoading: false, error: null, count: 3 }), "ready");
});
```

`apps/scraper-console/src/lib/assets-quality.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { qualitySampleLabel, qualityStatusLabel } from "./assets-quality.ts";

test("质量状态标签", () => {
  assert.equal(qualityStatusLabel(null), "未评分");
  assert.equal(qualityStatusLabel(undefined), "未评分");
  assert.equal(qualityStatusLabel("qualified"), "达标");
  assert.equal(qualityStatusLabel("qualified_with_gap"), "有缺口");
  assert.equal(qualityStatusLabel("not_qualified"), "未达标");
  assert.equal(qualityStatusLabel("unknown"), "未知");
});

test("样本缺失显示缺失而不是 0", () => {
  assert.equal(qualitySampleLabel(null), "缺失");
  assert.equal(qualitySampleLabel(undefined), "缺失");
  assert.equal(qualitySampleLabel(0), "0");
  assert.equal(qualitySampleLabel(2000), "2,000");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/assets-view.test.ts"`
Run: `pnpm -C apps/scraper-console exec node --test "src/lib/assets-quality.test.ts"`
Expected: 第一条通过；第二条 FAIL，报 `assets-quality.ts` 不存在。

- [ ] **Step 3: 写纯函数并扩展类型**

`apps/scraper-console/src/lib/assets-view.ts`：

```typescript
export type AssetsPageState = "loading" | "error" | "empty" | "ready";

export function resolveAssetsState(input: {
  isLoading: boolean;
  error: unknown;
  count: number;
}): AssetsPageState {
  if (input.isLoading) return "loading";
  if (input.error) return "error";
  if (input.count === 0) return "empty";
  return "ready";
}
```

`apps/scraper-console/src/lib/assets-quality.ts`：

```typescript
export type MarketQualityStatus =
  | "qualified"
  | "qualified_with_gap"
  | "not_qualified"
  | null;

export function qualityStatusLabel(status: MarketQualityStatus | string | undefined): string {
  switch (status) {
    case "qualified":
      return "达标";
    case "qualified_with_gap":
      return "有缺口";
    case "not_qualified":
      return "未达标";
    case null:
    case undefined:
    case "":
      return "未评分";
    default:
      return "未知";
  }
}

export function qualitySampleLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) return "缺失";
  return value.toLocaleString("zh-CN");
}

export type QualityAssessment = {
  id: string;
  task_id: string;
  market: string;
  market_role: string;
  quality_status: Exclude<MarketQualityStatus, null>;
  conclusion_standard: string | null;
  conclusion_quick: string | null;
  evidence_grade: string;
  core_domain_coverage: Record<string, string>;
  sample_counts: Record<string, number | null>;
  thresholds: Record<string, unknown>;
  gap_ids: string[];
  details_json: Record<string, unknown>;
  computed_at: string;
};

export type QualityDataGap = {
  id: string;
  task_id: string;
  market: string;
  data_domain: string;
  reason_code: string;
  actual_value: unknown | null;
  threshold_value: unknown | null;
  impact: string;
  customer_text_zh: string;
  customer_text_en: string;
  remediation: string | null;
  severity: "info" | "warning" | "blocking" | "critical";
  status: "open" | "mitigated" | "accepted" | "closed";
  created_at: string;
  resolved_at: string | null;
};
```

在 `apps/scraper-console/src/lib/api/datasets.ts` 的现有 `DatasetVersion` 与 `DatasetVersionPreview` 类型中只追加以下字段，保留原有字段：

```typescript
type DatasetVersionQualityFields = {
  task_id: string | null;
  market: string | null;
  schema_hash: string | null;
  content_sha256: string | null;
  license_class: string | null;
  quality_status:
    | "qualified"
    | "qualified_with_gap"
    | "not_qualified"
    | null;
};

type DatasetVersionPreviewQualityFields = {
  quality_assessment: import("./assets-quality").QualityAssessment | null;
  data_gaps: import("./assets-quality").QualityDataGap[];
};
```

- [ ] **Step 4: 资产列表加质量列**

在 `apps/scraper-console/src/app/assets/page.tsx`：

1. 导入 `qualityStatusLabel`。
2. 给根容器加 `data-testid="assets-page"`，给数据集行加 `data-testid="asset-row"`；在 `apps/scraper-console/src/app/assets/records/page.tsx` 给根容器加 `data-testid="assets-records-page"`，给记录行加 `data-testid="raw-record-row"`。
3. 表头增加“质量”列。
4. 每行增加：

```tsx
<td data-testid="asset-quality" className="px-3 py-2 text-xs">
  {qualityStatusLabel(item.latest_version?.quality_status)}
</td>
```

5. `quality_status` 为 `null` 或 `undefined` 时显示“未评分”，不得显示“未达标”。
6. 不新增质量筛选，不在前端重算状态。

- [ ] **Step 5: 预览抽屉加质量页签**

在 `apps/scraper-console/src/components/datasets/data-preview-drawer.tsx`：

1. 在 lucide 导入中加入 `ShieldCheck`；导入 `qualitySampleLabel`、`qualityStatusLabel`、`QualityAssessment`、`QualityDataGap` 类型。
2. 把 `type Tab` 改为：

```typescript
type Tab = "rows" | "schema" | "lineage" | "quality";
```

3. 在 tabs 数组加入：

```tsx
{ key: "quality", label: "质量", icon: <ShieldCheck size={13} /> },
```

并给页签按钮加：

```tsx
data-testid={t.key === "quality" ? "asset-quality-tab" : `asset-tab-${t.key}`}
```

4. 在组件内、返回 JSX 之前加入：

```tsx
const quality = preview?.quality_assessment ?? null;
const gaps = preview?.data_gaps ?? [];
```

5. 在内容区加入：

```tsx
) : tab === "quality" ? (
  <div data-testid="asset-quality-panel" className="space-y-4">
    {quality ? (
      <>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <p>状态：{qualityStatusLabel(quality.quality_status)}</p>
          <p>市场：{quality.market}</p>
          <p>任务：{quality.task_id}</p>
          <p>证据等级：{quality.evidence_grade}</p>
          <p className="col-span-2">
            阈值：<span data-testid="asset-quality-thresholds">{JSON.stringify(quality.thresholds)}</span>
          </p>
        </div>
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              <th>数据域</th>
              <th>样本数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(quality.sample_counts).map(([domain, count]) => (
              <tr key={domain}>
                <td>{domain}</td>
                <td data-testid="asset-quality-sample">{qualitySampleLabel(count)}</td>
                <td>{quality.core_domain_coverage[domain] ?? "missing"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table className="w-full text-left text-xs">
          <thead>
            <tr>
              <th>缺口</th>
              <th>严重度</th>
              <th>实际值</th>
              <th>门槛</th>
              <th>客户说明</th>
              <th>修复建议</th>
            </tr>
          </thead>
          <tbody>
            {gaps.map(gap => (
              <tr key={gap.id} data-testid="asset-quality-gap">
                <td>{gap.reason_code}</td>
                <td>{gap.severity}</td>
                <td data-testid="asset-quality-gap-actual">
                  {gap.actual_value === null || gap.actual_value === undefined
                    ? "缺失"
                    : String(gap.actual_value)}
                </td>
                <td>{gap.threshold_value === null || gap.threshold_value === undefined
                  ? "—"
                  : String(gap.threshold_value)}</td>
                <td>{gap.customer_text_zh}</td>
                <td>{gap.remediation ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    ) : (
      <p data-testid="asset-quality-empty">未评分</p>
    )}
  </div>
) : tab === "rows" ? (
```

6. 缺失样本数显示“缺失”，缺口 `actual_value` 为 `null` 时显示“缺失”，不得显示 `0`。
7. 在“采集溯源”页签显示 `activeVersion.content_sha256` 与 `schema_hash`；字段为 null 时显示“未记录”，不显示空字符串。
8. 前端不重新计算 `quality_status`、独立来源数或阈值。

- [ ] **Step 6: 写 `assets-quality.spec.ts`**

Create `apps/scraper-console/e2e/assets-quality.spec.ts`：

```typescript
import { expect, test } from "@playwright/test";
import { readSeedManifest } from "./support/seed-manifest";

test.describe("@authenticated 资产质量", () => {
  test("列表显示质量列，预览显示质量页签与缺口", async ({ page }) => {
    const seed = readSeedManifest();
    expect(seed.dataset_id.length).toBeGreaterThan(0);
    await page.goto("/assets");
    await expect(page.getByTestId("assets-page")).toBeVisible();

    const row = page.getByTestId("asset-row").filter({ hasText: "E2E Dataset" });
    await expect(row.getByTestId("asset-quality")).toHaveText("有缺口");
    await expect(row.getByTestId("asset-quality")).not.toHaveText("未达标");

    await row.getByRole("button", { name: /预览|查看/ }).click();
    await page.getByTestId("asset-quality-tab").click();
    await expect(page.getByTestId("asset-quality-panel")).toContainText("有缺口");
    await expect(page.getByTestId("asset-quality-panel")).toContainText("缺失");
    await expect(page.getByTestId("asset-quality-gap")).toContainText("data_domain_missing");
    await expect(page.getByTestId("asset-quality-gap-actual").first()).toHaveText("缺失");
    await expect(page.getByTestId("asset-quality-gap")).toContainText("评论样本不足");
  });

  test("未评分版本不显示未达标", async ({ page }) => {
    await page.route("**/api/automation/product-datasets**", route =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              dataset: {
                id: "00000000-0000-0000-0000-000000000001",
                project_id: "00000000-0000-0000-0000-000000000002",
                name: "Legacy Dataset",
                dataset_type: "ecommerce_product",
                status: "active",
                description: null,
                created_at: "2026-10-01T00:00:00Z",
                updated_at: "2026-10-01T00:00:00Z",
              },
              latest_version: {
                id: "00000000-0000-0000-0000-000000000003",
                dataset_id: "00000000-0000-0000-0000-000000000001",
                cleaning_plan_id: null,
                version_number: 1,
                source_task_run_ids: [],
                source_workflow_run_id: null,
                selected_fields: ["title"],
                cleaning_script: [],
                row_count: 0,
                average_completeness_percent: 0,
                status: "saved",
                created_at: "2026-10-01T00:00:00Z",
                export_preview: {},
                task_id: null,
                market: null,
                schema_hash: null,
                content_sha256: null,
                license_class: null,
                quality_status: null,
              },
              version_count: 1,
              latest_drift_event: null,
              drift_event_count: 0,
              platforms: [],
              category: null,
              collector_types: [],
              content_types: [],
            },
          ],
          total: 1,
        }),
      }),
    );
    await page.goto("/assets");
    const row = page.getByTestId("asset-row").filter({ hasText: "Legacy Dataset" });
    await expect(row.getByTestId("asset-quality")).toHaveText("未评分");
    await expect(row.getByTestId("asset-quality")).not.toHaveText("未达标");
  });
});
```

在预览抽屉的质量页签上补 `data-testid="asset-quality-tab"`，在质量面板补 `data-testid="asset-quality-panel"`，在缺口行补 `data-testid="asset-quality-gap"`。

- [ ] **Step 7: 运行门禁**

Run:
```bash
pnpm -C apps/scraper-console exec node --test "src/lib/assets-view.test.ts"
pnpm -C apps/scraper-console exec node --test "src/lib/assets-quality.test.ts"
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console exec tsc --noEmit
pnpm -C apps/scraper-console exec playwright test e2e/assets-quality.spec.ts
```
Expected: 全部通过；质量列与质量页签可见；缺失值显示“缺失”。

- [ ] **Step 8: 提交**

```bash
git add apps/scraper-console/src/lib/assets-view.ts \
  apps/scraper-console/src/lib/assets-view.test.ts \
  apps/scraper-console/src/lib/assets-quality.ts \
  apps/scraper-console/src/lib/assets-quality.test.ts \
  apps/scraper-console/src/lib/api/datasets.ts \
  apps/scraper-console/src/app/assets \
  apps/scraper-console/src/components/datasets/data-preview-drawer.tsx \
  apps/scraper-console/e2e/assets-quality.spec.ts
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): show market quality on assets"
```

---

### Task 7: 连接器页接真实凭据与提供方状态

**Files:**
- Create: `apps/scraper-console/src/lib/api/connectors.ts`
- Create: `apps/scraper-console/src/lib/api/connectors.test.ts`
- Create: `apps/scraper-console/src/components/connectors/connectors-workspace.tsx`（从 `settings/credentials/page.tsx` 迁移）
- Create: `apps/scraper-console/src/app/connectors/page.tsx`
- Modify: `apps/scraper-console/src/app/settings/credentials/page.tsx`（改为重定向）

**Interfaces:**
- Consumes: `PlatformCredential`、`CredentialsSettings`、`PlatformPackageCatalog`、`ProviderStatus`。
- Produces: `ConnectorRow`、`mergeConnectors(credentials, packages, providerStatus)`。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/api/connectors.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { mergeConnectors } from "./connectors.ts";

test("合并凭据、平台包和提供方状态", () => {
  const rows = mergeConnectors(
    {
      vault_write_enabled: true,
      platforms: [
        {
          platform: "youtube",
          provider_id: "youtube",
          label: "YouTube Data API",
          auth_mode: "oauth",
          fields: [{ key: "api_key", label: "API Key", configured: true }],
          configured: true,
          configured_field_count: 1,
          updated_at: "2026-10-01T00:00:00Z",
        },
      ],
    },
    {
      schema_version: "1.0.0",
      catalog_digest: "abc",
      source_entry_count: 1,
      unique_endpoint_count: 1,
      capability_count: 1,
      platform_count: 1,
      packages: [
        {
          platform_id: "youtube",
          display_name: "YouTube",
          description: "",
          endpoint_count: 4,
          verified_count: 3,
          disabled_count: 0,
          provider_groups: [],
          methods: [],
          content_types: [],
          endpoints: [],
          skill_path: "",
          playbook_path: "",
          detail_path: "",
          platform_notes: [],
        },
      ],
    },
    {
      catalog_digest: "abc",
      endpoints: [
        {
          endpoint_type: "youtube_search",
          availability: "verified",
          missing_configuration: [],
          last_test_status: "success",
          last_test_at: "2026-10-01T00:00:00Z",
          last_records_count: 5,
          last_error_message: null,
        },
      ],
    },
  );

  assert.equal(rows.length, 1);
  assert.equal(rows[0].platform, "youtube");
  assert.equal(rows[0].configured, true);
  assert.equal(rows[0].endpoint_count, 4);
  assert.equal(rows[0].verified_count, 3);
  assert.equal(rows[0].health_status, "verified");
  assert.equal(JSON.stringify(rows).includes("cookie"), false);
});

test("缺少平台包时仍返回凭据行", () => {
  const rows = mergeConnectors(
    {
      vault_write_enabled: false,
      platforms: [
        {
          platform: "reddit",
          provider_id: "reddit",
          label: "Reddit",
          auth_mode: "oauth",
          fields: [],
          configured: false,
          configured_field_count: 0,
          updated_at: null,
        },
      ],
    },
    null,
    null,
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].endpoint_count, 0);
  assert.equal(rows[0].health_status, "unknown");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/api/connectors.test.ts"`
Expected: FAIL，报模块不存在。

- [ ] **Step 3: 写合并实现**

`apps/scraper-console/src/lib/api/connectors.ts`：

```typescript
import type { CredentialsSettings, PlatformCredential } from "./credentials";
import type { PlatformPackageCatalog, ProviderStatus } from "./platform-packages";

export type ConnectorRow = {
  platform: string;
  label: string;
  auth_mode: string;
  configured: boolean;
  configured_field_count: number;
  updated_at: string | null;
  endpoint_count: number;
  verified_count: number;
  health_status: string;
};

export function mergeConnectors(
  credentials: CredentialsSettings | null | undefined,
  packages: PlatformPackageCatalog | null | undefined,
  providerStatus: ProviderStatus | null | undefined,
): ConnectorRow[] {
  const packageByPlatform = new Map(
    (packages?.packages ?? []).map(item => [item.platform_id, item]),
  );
  const healthByPlatform = new Map<string, string>();
  for (const endpoint of providerStatus?.endpoints ?? []) {
    const platform = endpoint.endpoint_type.split("_")[0];
    if (!healthByPlatform.has(platform)) {
      healthByPlatform.set(platform, endpoint.availability);
    }
  }
  return (credentials?.platforms ?? []).map((platform: PlatformCredential) => {
    const pkg = packageByPlatform.get(platform.platform);
    return {
      platform: platform.platform,
      label: platform.label,
      auth_mode: platform.auth_mode,
      configured: platform.configured,
      configured_field_count: platform.configured_field_count,
      updated_at: platform.updated_at,
      endpoint_count: pkg?.endpoint_count ?? 0,
      verified_count: pkg?.verified_count ?? 0,
      health_status:
        healthByPlatform.get(platform.platform) ?? pkg?.endpoints[0]?.status ?? "unknown",
    };
  });
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/api/connectors.test.ts"`
Expected: `2 tests passed`。

- [ ] **Step 5: 迁移凭据页并新建连接器页**

```bash
mkdir -p apps/scraper-console/src/components/connectors
git mv apps/scraper-console/src/app/settings/credentials/page.tsx \
  apps/scraper-console/src/components/connectors/connectors-workspace.tsx
```

把迁移后的导出函数 `CredentialsPage` 改名为 `ConnectorsWorkspace`，并在 `AppShell` 的 `title` 改为 `连接器与凭据`，`description` 改为 `Provider 目录、凭据与就绪度`。保留原有 `PlatformCard`、`SecretInput` 和写入逻辑。禁止渲染 `creator_cookie` 字段：过滤 `fields[].key === "creator_cookie"`，同时删除响应对象中的 `creator_cookie` 与 `creator_cookie_metadata`。测试必须断言整个序列化响应字符串不含 `cookie`。给最外层内容容器加 `data-testid="connectors-page"`。

新建 `apps/scraper-console/src/app/connectors/page.tsx`：

```tsx
import { ConnectorsWorkspace } from "@/components/connectors/connectors-workspace";

export default function ConnectorsPage() {
  return <ConnectorsWorkspace />;
}
```

把 `apps/scraper-console/src/app/settings/credentials/page.tsx` 改为：

```tsx
import { redirect } from "next/navigation";

export default function LegacyCredentialsPage() {
  redirect("/connectors");
}
```

- [ ] **Step 6: 登记连接器路由并运行门禁**

在 `apps/scraper-console/src/lib/routes.ts` 的 `NEW_ROUTES` 中追加：

```typescript
  // C14：连接器与凭据。
  "/connectors",
```

把 `routes.test.ts` 的数量断言改为 `NEW_ROUTES.length === 10`，总数改为 `24`。

Run: `pnpm -C apps/scraper-console test`
Run: `pnpm -C apps/scraper-console exec tsc --noEmit`
Run: `pnpm -C apps/scraper-console lint`
Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add apps/scraper-console/src/lib/api/connectors.ts \
  apps/scraper-console/src/lib/api/connectors.test.ts \
  apps/scraper-console/src/lib/routes.ts \
  apps/scraper-console/src/lib/routes.test.ts \
  apps/scraper-console/src/components/connectors \
  apps/scraper-console/src/app/connectors \
  apps/scraper-console/src/app/settings/credentials
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): move credentials into connectors page"
```

---

### Task 8: 设置页接会话、内联成员、用量与交接面板

**Files:**
- Create: `apps/scraper-console/src/lib/api/settings.ts`
- Create: `apps/scraper-console/src/lib/api/settings.test.ts`
- Create: `apps/scraper-console/src/lib/api/privacy-handoff.ts`
- Create: `apps/scraper-console/src/lib/api/privacy-handoff.test.ts`
- Create: `apps/scraper-console/src/app/settings/page.tsx`

**Interfaces:**
- Consumes: `docs/ops/c2-c14-members-handoff.md`（C2 交接的 `/settings` 内联成员面板选择器、邀请、改角色、最后 owner 错误、项目分配与 owner/admin/member 可见性判据）、`fetchAuthSession`、`fetchWorkspaces`、`fetchWorkspaceMembers`、`GET /api/usage/summary`、`GET /api/audit-events`、`GET /api/projects/{project_id}/keys`、`GET /api/privacy/legal-holds`、`GET /api/privacy/deletion-requests`、`GET /api/privacy/dsr-cases`。
- Produces: `fetchUsageSummary(days)`、`fetchAuditEvents()`、`fetchProjectKeys(projectId)`、`fetchLegalHolds()`、`fetchDeletionRequests()`、`fetchDsrCases()`、`CUSTOMER_MCP_TOOLS`、`formatUsd(value)`、`roleLabel(role)`。C14 不新增 API 路由；所有数据来自 C2/C3/C11/C12/C13 已登记接口。
- 交接 UI：C2 审计列表与 `/settings` 内联成员面板、C3 项目密钥列表/创建/轮换/撤销、C11 保留策略与法律保留只读、C12 删除/DSR 列表与链接、C13 客户 MCP 地址/八工具/密钥前缀与撤销。密钥明文只在创建响应显示一次；刷新后只显示前缀。不得显示 provider、端点、Cookie 或内部单价。

- [ ] **Step 0: 读取 C2 设置页内联成员面板交接**

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
test -f docs/ops/c2-c14-members-handoff.md
rg -n 'settings-members|member-invite-form|member-role-|member-remove-|project-member-panel|members-non-owner-hint|workspace_last_owner_required' \
  docs/ops/c2-c14-members-handoff.md
```

Expected: 文件存在，选择器与错误码全部命中。缺文件或缺少选择器时停止，先修 C2 交接，不凭记忆实现。成员面板是 `/settings` 的内联区块，不新增 `/settings/members` 路由。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/api/settings.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { formatUsd, roleLabel, usageSummaryPath } from "./settings.ts";

test("用量路径带天数", () => {
  assert.equal(usageSummaryPath(30), "/api/usage/summary?days=30");
  assert.equal(usageSummaryPath(7), "/api/usage/summary?days=7");
});

test("角色文案与 C2 交接一致", () => {
  assert.equal(roleLabel("owner"), "所有者");
  assert.equal(roleLabel("admin"), "管理员");
  assert.equal(roleLabel("member"), "成员");
});

test("金额按六位小数显示，不做浮点运算", () => {
  assert.equal(formatUsd("1.234567"), "USD 1.234567");
  assert.equal(formatUsd("0"), "USD 0.000000");
  assert.equal(formatUsd(null), "—");
});
```

`apps/scraper-console/src/lib/api/privacy-handoff.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import {
  CUSTOMER_MCP_TOOLS,
  deletionRequestPath,
  legalHoldScopeLabel,
  legalHoldsPath,
  projectKeysPath,
} from "./privacy-handoff.ts";

test("交接面板只使用已登记路径", () => {
  assert.equal(legalHoldsPath(), "/api/privacy/legal-holds");
  assert.equal(deletionRequestPath(), "/api/privacy/deletion-requests");
  assert.equal(projectKeysPath("p/1"), "/api/projects/p%2F1/keys");
});

test("法律保留使用 C11/C12 实际作用域字段", () => {
  assert.equal(
    legalHoldScopeLabel({
      id: "h1",
      workspace_id: "w1",
      project_id: null,
      data_class: null,
      status: "active",
      reason: "case",
      requested_by_user_id: "u1",
      requested_at: "2026-10-22T00:00:00Z",
    }),
    "workspace · w1",
  );
  assert.equal(
    legalHoldScopeLabel({
      id: "h2",
      workspace_id: "w1",
      project_id: "p1",
      data_class: "raw_response",
      status: "active",
      reason: "case",
      requested_by_user_id: "u1",
      requested_at: "2026-10-22T00:00:00Z",
    }),
    "project · p1",
  );
});

test("客户 MCP 固定八工具", () => {
  assert.deepEqual(CUSTOMER_MCP_TOOLS, [
    "discover_capabilities",
    "estimate_task",
    "create_task",
    "get_task",
    "cancel_task",
    "get_delivery_manifest",
    "get_evidence",
    "collect",
  ]);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/api/settings.test.ts" "src/lib/api/privacy-handoff.test.ts"`
Expected: FAIL，模块不存在。

- [ ] **Step 3: 写 API 客户端**

`apps/scraper-console/src/lib/api/settings.ts`：

```typescript
import { apiFetch } from "./client";

export type UsageBucket = { runs: number; records: number; cost_usd: string };

export type UsageSummary = {
  since: string;
  days: number;
  project_id: string | null;
  totals: UsageBucket;
  by_provider: Array<{ provider: string } & UsageBucket>;
  by_endpoint: Array<{ endpoint_type: string } & UsageBucket>;
  by_day: Array<{ date: string } & UsageBucket>;
};

export function usageSummaryPath(days: number): string {
  return `/api/usage/summary?days=${encodeURIComponent(String(days))}`;
}

export function fetchUsageSummary(days = 30): Promise<UsageSummary> {
  return apiFetch<UsageSummary>(usageSummaryPath(days));
}

export function formatUsd(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const [whole, fraction = ""] = value.split(".");
  return `USD ${whole}.${(fraction + "000000").slice(0, 6)}`;
}

export function roleLabel(role: string): string {
  if (role === "owner") return "所有者";
  if (role === "admin") return "管理员";
  return "成员";
}

export type AuditEvent = {
  id: string;
  action: string;
  result: "success" | "denied" | "failed";
  occurred_at: string;
};

export function fetchAuditEvents(): Promise<AuditEvent[]> {
  return apiFetch<AuditEvent[]>("/api/audit-events?limit=20");
}
```

`apps/scraper-console/src/lib/api/privacy-handoff.ts`：

```typescript
import { apiFetch } from "./client";

export const CUSTOMER_MCP_TOOLS = [
  "discover_capabilities",
  "estimate_task",
  "create_task",
  "get_task",
  "cancel_task",
  "get_delivery_manifest",
  "get_evidence",
  "collect",
] as const;

export type LegalHold = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  data_class: string | null;
  status: "active" | "released";
  reason: string;
  requested_by_user_id: string;
  requested_at: string;
};

export type DeletionRequest = {
  id: string;
  target_type: "project" | "workspace";
  status: string;
  created_at: string;
};

export type DsrCase = {
  id: string;
  case_number: string;
  request_type: string;
  status: string;
};

export type ProjectKey = {
  id: string;
  key_prefix: string;
  label: string;
  status: string;
};

export function legalHoldsPath(): string {
  return "/api/privacy/legal-holds";
}

export function deletionRequestPath(): string {
  return "/api/privacy/deletion-requests";
}

export function dsrCasesPath(): string {
  return "/api/privacy/dsr-cases";
}

export function projectKeysPath(projectId: string): string {
  return `/api/projects/${encodeURIComponent(projectId)}/keys`;
}

export function fetchLegalHolds(): Promise<LegalHold[]> {
  return apiFetch<LegalHold[]>(legalHoldsPath());
}

export function fetchDeletionRequests(): Promise<DeletionRequest[]> {
  return apiFetch<DeletionRequest[]>(deletionRequestPath());
}

export function fetchDsrCases(): Promise<DsrCase[]> {
  return apiFetch<DsrCase[]>(dsrCasesPath());
}

export function fetchProjectKeys(projectId: string): Promise<ProjectKey[]> {
  return apiFetch<ProjectKey[]>(projectKeysPath(projectId));
}

export function legalHoldScopeLabel(hold: LegalHold): string {
  return hold.project_id
    ? `project · ${hold.project_id}`
    : `workspace · ${hold.workspace_id}`;
}
```

- [ ] **Step 4: 写设置页**

`apps/scraper-console/src/app/settings/page.tsx`：

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchAuthSession,
  fetchWorkspaceMembers,
  fetchWorkspaces,
} from "@/lib/api/auth";
import { fetchProjects } from "@/lib/api/projects";
import {
  fetchAuditEvents,
  fetchUsageSummary,
  formatUsd,
  roleLabel,
} from "@/lib/api/settings";
import {
  CUSTOMER_MCP_TOOLS,
  fetchDeletionRequests,
  fetchDsrCases,
  fetchLegalHolds,
  fetchProjectKeys,
  legalHoldScopeLabel,
} from "@/lib/api/privacy-handoff";

function ErrorLine({ label, error }: { label: string; error: Error | null }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-2 text-xs text-[var(--state-danger)]">
      {label}读取失败：{error.message}
    </p>
  );
}

export default function SettingsPage() {
  const session = useQuery({ queryKey: ["auth-session"], queryFn: fetchAuthSession });
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: fetchWorkspaces });
  const members = useQuery({
    queryKey: ["workspace-members"],
    queryFn: fetchWorkspaceMembers,
    enabled: session.isSuccess,
  });
  const usage = useQuery({
    queryKey: ["usage-summary", 30],
    queryFn: () => fetchUsageSummary(30),
    enabled: session.isSuccess,
  });
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const projectId = projects.data?.[0]?.id ?? "";
  const audit = useQuery({
    queryKey: ["audit-events"],
    queryFn: fetchAuditEvents,
    enabled: session.isSuccess,
  });
  const keys = useQuery({
    queryKey: ["project-keys", projectId],
    queryFn: () => fetchProjectKeys(projectId),
    enabled: Boolean(projectId),
  });
  const holds = useQuery({
    queryKey: ["legal-holds"],
    queryFn: fetchLegalHolds,
    enabled: session.isSuccess,
  });
  const deletions = useQuery({
    queryKey: ["deletion-requests"],
    queryFn: fetchDeletionRequests,
    enabled: session.isSuccess,
  });
  const dsr = useQuery({
    queryKey: ["dsr-cases"],
    queryFn: fetchDsrCases,
    enabled: session.isSuccess,
  });

  return (
    <AppShell title="设置" description="工作区、成员、访问、凭据、保留与隐私">
      <div data-testid="settings-page" className="grid gap-4">
        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">工作区</h2>
          <p className="mt-2 text-sm">{session.data?.workspace.name ?? "—"}</p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">可切换工作区 {workspaces.data?.length ?? 0} 个</p>
        </section>

        <section data-testid="settings-members" className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">成员</h2>
          <ErrorLine label="成员" error={members.error as Error | null} />
          <ul className="mt-3 grid gap-2 text-sm">
            {(members.data ?? []).map(member => (
              <li
                key={member.user.id}
                data-testid={`member-row-${member.user.email}`}
                className="flex justify-between"
              >
                <span>{member.user.name}</span>
                <span className="text-xs text-[var(--text-tertiary)]">{roleLabel(member.role)}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">用量</h2>
          <ErrorLine label="用量" error={usage.error as Error | null} />
          {usage.data ? (
            <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
              <div><dt className="text-xs text-[var(--text-tertiary)]">运行</dt><dd>{usage.data.totals.runs}</dd></div>
              <div><dt className="text-xs text-[var(--text-tertiary)]">记录</dt><dd>{usage.data.totals.records}</dd></div>
              <div><dt className="text-xs text-[var(--text-tertiary)]">成本</dt><dd>{formatUsd(usage.data.totals.cost_usd)}</dd></div>
            </dl>
          ) : null}
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">访问审计（C2）</h2>
          <ErrorLine label="审计" error={audit.error as Error | null} />
          {audit.data?.length === 0 ? <p className="mt-2 text-xs text-[var(--text-tertiary)]">暂无审计事件。</p> : null}
          <ul className="mt-3 grid gap-2 text-xs">
            {(audit.data ?? []).map(event => (
              <li key={event.id} className="flex justify-between">
                <span>{event.action}</span>
                <span>{event.result}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">项目密钥（C3）</h2>
          <ErrorLine label="项目密钥" error={keys.error as Error | null} />
          <ul className="mt-3 grid gap-2 text-xs">
            {(keys.data ?? []).map(key => (
              <li key={key.id} className="flex justify-between">
                <span>{key.label}</span>
                <span>{key.key_prefix}… · {key.status}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">保留与法律保留（C11）</h2>
          <table className="mt-3 w-full text-xs">
            <tbody>
              <tr><td>原始响应</td><td>30 天</td></tr>
              <tr><td>标准化数据集</td><td>12 个月</td></tr>
              <tr><td>正式报告和交付包</td><td>24 个月</td></tr>
              <tr><td>运行日志</td><td>180 天</td></tr>
              <tr><td>安全与访问审计</td><td>24 个月</td></tr>
              <tr><td>备份</td><td>30 天</td></tr>
            </tbody>
          </table>
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">
            保留清理只通过运维 CLI dry-run 执行，本页不触发删除。
          </p>
          <ErrorLine label="法律保留" error={holds.error as Error | null} />
          <ul className="mt-2 grid gap-1 text-xs">
            {(holds.data ?? []).map(hold => (
              <li key={hold.id}>{legalHoldScopeLabel(hold)} · {hold.data_class ?? "全部"} · {hold.status}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">隐私与删除（C12）</h2>
          <ErrorLine label="删除请求" error={deletions.error as Error | null} />
          <ul className="mt-2 grid gap-1 text-xs">
            {(deletions.data ?? []).map(item => (
              <li key={item.id}>{item.target_type} · {item.status}</li>
            ))}
          </ul>
          <ErrorLine label="DSR" error={dsr.error as Error | null} />
          <ul className="mt-2 grid gap-1 text-xs">
            {(dsr.data ?? []).map(item => (
              <li key={item.id}>{item.case_number} · {item.request_type} · {item.status}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
          <h2 className="text-sm font-semibold">客户 MCP（C13）</h2>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">地址：/mcp/customer</p>
          <ul className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {CUSTOMER_MCP_TOOLS.map(tool => <li key={tool}>{tool}</li>)}
          </ul>
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">
            密钥签发与撤销复用上方项目密钥接口；本页不展示明文、Cookie 或 provider。
          </p>
        </section>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 5: 登记设置路由并运行门禁**

在 `apps/scraper-console/src/lib/routes.ts` 的 `NEW_ROUTES` 中追加：

```typescript
  // C14：设置。
  "/settings",
```

把 `routes.test.ts` 的数量断言改为 `NEW_ROUTES.length === 11`，总数改为 `25`。`NEW_ROUTES` 只追加 `/settings`，不追加 `/settings/members`；在 `contract-routes.test.ts` 中断言 `CONTRACT_ROUTES.some(route => route.path === "/settings/members") === false`，成员面板只存在于 `/settings`。若 legacy `/settings/members` 页面仍保留，它不得成为合同路由，也不得从 `/settings` 链接进入。

Run:
```bash
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console exec tsc --noEmit
pnpm -C apps/scraper-console lint
```
Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add apps/scraper-console/src/lib/routes.ts \
  apps/scraper-console/src/lib/routes.test.ts \
  apps/scraper-console/src/lib/api/settings.ts \
  apps/scraper-console/src/lib/api/settings.test.ts \
  apps/scraper-console/src/lib/api/privacy-handoff.ts \
  apps/scraper-console/src/lib/api/privacy-handoff.test.ts \
  apps/scraper-console/src/app/settings/page.tsx
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): wire settings and handoff panels"
```

---

### Task 8A: 治理动作客户端与内联动作面

**Goal:** 把 §0.3 的动作清单变成可执行代码。所有动作只调用 C1 v1.1 已登记的路径。每个 mutation 接收调用方生成的幂等键。UI 每个意图只生成一次幂等键，重试复用同一个键。C14 不在生产执行这些动作；动作只在本地/CI 的专用合成工作区运行。

**Files:**
- Create: `apps/scraper-console/src/lib/api/governance-actions.ts`
- Create: `apps/scraper-console/src/lib/api/governance-actions.test.ts`
- Create: `apps/scraper-console/src/components/workbench/governance-actions.tsx`
- Create: `apps/scraper-console/src/components/settings/members-and-keys.tsx`
- Create: `apps/scraper-console/src/components/settings/quota-cards.tsx`
- Create: `apps/scraper-console/src/components/reports/review-delivery-actions.tsx`
- Create: `apps/scraper-console/src/components/settings/privacy-actions.tsx`
- Create: `apps/scraper-console/e2e/governance-actions.spec.ts`
- Create: `apps/scraper-console/e2e/members.spec.ts`
- Modify: `apps/scraper-console/src/lib/api/reports.ts`（追加 C7 `ClaimView` 与交付/验收类型）
- Modify: `apps/scraper-console/src/components/workbench/task-detail.tsx`（挂载工作台内联动作）
- Modify: `apps/scraper-console/src/app/reports/[artifactId]/page.tsx`（挂载审核、发布、交付、验收与 Claim 只读）
- Modify: `apps/scraper-console/src/app/settings/page.tsx`（挂载成员/密钥、额度、隐私动作）
- Modify: `apps/scraper-console/e2e/support/seed-manifest.ts`（追加治理动作可选字段；缺字段时测试用固定 UUID 与 route mock）

**Interfaces:**
- Consumes: `docs/ops/c2-c14-members-handoff.md`（`/settings` 内联成员面板：`settings-members`、邀请、改角色、最后 owner 错误、项目分配与 owner/admin/member 可见性）、`POST /api/runs`、`POST /api/runs/{run_id}/cancel`、`POST /api/workbench/tasks/{task_id}/approvals`、`POST /api/workbench/tasks/{task_id}/approvals/{approval_id}`、`POST/PATCH /api/workspaces/current/members*`、`POST/DELETE /api/projects/{project_id}/members*`、`GET/POST/DELETE /api/projects/{project_id}/keys*`、`GET /api/quota`、`GET /api/quota/projects/{project_id}`、`GET /api/usage/summary`、`POST /api/reports/{report_id}/reviewers`、`DELETE /api/reports/{report_id}/reviewers/{user_id}`、`POST /api/reports/{report_id}/reviews`、`POST /api/reports/{report_id}/publish`、`GET /api/reports/{report_id}/revisions`、`POST /api/reports/drafts`、`POST /api/reports/{artifact_id}/delivery/publish`、`GET /api/reports/{artifact_id}/delivery`、`GET /api/reports/{artifact_id}/delivery/manifest`、`POST /api/reports/{artifact_id}/delivery/quick-draft`、`GET /api/reports/{artifact_id}/delivery/quick-draft`、`GET /api/tasks/{task_id}/delivery/quick-draft`、`GET/POST /api/reports/{artifact_id}/delivery/acceptance*`、`POST/GET /api/privacy/deletion-requests*`、`GET /api/privacy/dsr-cases`、`GET /api/privacy/legal-holds`。
- Produces: `governancePaths`、`IntentKeyStore`、`submitRun`、`retryRunSubmission`、`cancelRun`、`createApproval`、`decideApproval`、`requestQuotaOverage`、`inviteWorkspaceMember`、`updateWorkspaceMemberRole`、`grantProjectMember`、`revokeProjectMember`、`createProjectKey`、`rotateProjectKey`、`revokeProjectKey`、`fetchProjectKeys`、`customerMcpConfig`、`assignReviewer`、`revokeReviewer`、`createReview`、`publishReport`、`fetchReportRevisions`、`createReportDraft`、`publishDelivery`、`fetchDeliveryManifest`、`downloadDeliveryZip`、`publishQuickDraft`、`downloadQuickDraftZip`、`fetchTaskQuickDraft`、`fetchAcceptance`、`acceptDelivery`、`disputeDelivery`、`deemAccepted`、`createDeletionRequest`、`approveDeletionRequest`、`confirmDeletionRequest`、`executeDeletionRequest`、`fetchDeletionProof`、`fetchDeletionRequests`、`fetchDsrCases`、`fetchLegalHolds`、`canDecideApproval`、`acceptanceActionsFor`、`legalHoldBlocks`、`isToolNotPriced`、`isIdempotencyConflict`、`CLAIM_VIEW_FIELD_MAP`。
- 运行重试没有登记路由。C14 的“重试”只重放同一 `POST /api/runs` 请求与同一幂等键。取消只调用 `POST /api/runs/{run_id}/cancel`。不得调用未登记的重试端点。
- 额度上限没有登记写端点。额度卡片只读取 `GET /api/quota` 与 `GET /api/quota/projects/{project_id}`。“写”只走已登记的内联批准 `POST /api/workbench/tasks/{task_id}/approvals`（`budget_overage`）。C14 不新增 `PUT /api/quota`。
- 所有 mutation 都发送 `Idempotency-Key`。同一意图的重试复用同一个键。幂等冲突 `idempotency_conflict` 不自动换键重试。

- [ ] **Step 0: 读取 C2 设置页内联成员面板交接并锁定选择器**

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
test -f docs/ops/c2-c14-members-handoff.md
rg -n 'settings-members|member-row-|member-invite-form|member-invite-email|member-invite-role|member-invite-submit|member-role-|member-remove-|member-error|project-member-panel|project-member-project|project-member-user|project-member-grant|project-member-row-|project-member-revoke-|members-non-owner-hint|workspace_last_owner_required' \
  docs/ops/c2-c14-members-handoff.md
```

Expected: 全部命中；实现选择器必须逐字复用，不改名。成员面板只存在于 `/settings`，不新增 `/settings/members` 路由。

- [ ] **Step 1: 写失败测试**

`apps/scraper-console/src/lib/api/governance-actions.test.ts`：

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import type { ClaimView } from "./reports.ts";
import {
  CLAIM_VIEW_FIELD_MAP,
  GovernanceApiError,
  IntentKeyStore,
  acceptanceActionsFor,
  canDecideApproval,
  customerMcpConfig,
  governancePaths,
  grantProjectMember,
  inviteWorkspaceMember,
  isIdempotencyConflict,
  isToolNotPriced,
  legalHoldBlocks,
  revokeProjectMember,
  retryRunSubmission,
  updateWorkspaceMemberRole,
} from "./governance-actions.ts";

const RUN_INPUT = {
  project_id: "p1",
  workbench_task_id: "t1",
  workflow_version_id: "v1",
  trigger: "manual" as const,
};

function approvalInput(overrides: Record<string, unknown> = {}) {
  return {
    requesterUserId: "u1",
    currentUserId: "u1",
    currentRole: "owner" as const,
    status: "pending" as const,
    expiresAt: "2026-10-23T00:00:00Z",
    now: new Date("2026-10-22T00:00:00Z"),
    ...overrides,
  };
}

test("动作路径全部来自 C1 v1.1 登记", () => {
  assert.deepEqual(
    [
      governancePaths.runs(),
      governancePaths.runCancel("r/1"),
      governancePaths.taskApprovals("t/1"),
      governancePaths.taskApproval("t/1", "a/1"),
      governancePaths.workspaceMembers(),
      governancePaths.workspaceMember("u/1"),
      governancePaths.projectMembers("p/1"),
      governancePaths.projectMember("p/1", "u/1"),
      governancePaths.projectKeys("p/1"),
      governancePaths.projectKey("p/1", "k/1"),
      governancePaths.projectKeyRotate("p/1", "k/1"),
      governancePaths.quota(),
      governancePaths.projectQuota("p/1"),
      governancePaths.usageSummary(30),
      governancePaths.reportReviewers("r/1"),
      governancePaths.reportReviewer("r/1", "u/1"),
      governancePaths.reportReviews("r/1"),
      governancePaths.reportPublish("r/1"),
      governancePaths.reportRevisions("r/1"),
      governancePaths.reportDrafts(),
      governancePaths.deliveryPublish("a/1"),
      governancePaths.deliveryManifest("a/1"),
      governancePaths.deliveryDownload("a/1"),
      governancePaths.deliveryAcceptance("a/1"),
      governancePaths.deliveryAcceptanceAction("a/1", "accept"),
      governancePaths.quickDraft("a/1"),
      governancePaths.taskQuickDraft("t/1"),
      governancePaths.deletionRequests(),
      governancePaths.deletionRequest("d/1"),
      governancePaths.deletionApprove("d/1"),
      governancePaths.deletionConfirm("d/1"),
      governancePaths.deletionExecute("d/1"),
      governancePaths.deletionProof("d/1"),
      governancePaths.dsrCases(),
      governancePaths.legalHolds(),
    ],
    [
      "/api/runs",
      "/api/runs/r%2F1/cancel",
      "/api/workbench/tasks/t%2F1/approvals",
      "/api/workbench/tasks/t%2F1/approvals/a%2F1",
      "/api/workspaces/current/members",
      "/api/workspaces/current/members/u%2F1",
      "/api/projects/p%2F1/members",
      "/api/projects/p%2F1/members/u%2F1",
      "/api/projects/p%2F1/keys",
      "/api/projects/p%2F1/keys/k%2F1",
      "/api/projects/p%2F1/keys/k%2F1/rotate",
      "/api/quota",
      "/api/quota/projects/p%2F1",
      "/api/usage/summary?days=30",
      "/api/reports/r%2F1/reviewers",
      "/api/reports/r%2F1/reviewers/u%2F1",
      "/api/reports/r%2F1/reviews",
      "/api/reports/r%2F1/publish",
      "/api/reports/r%2F1/revisions",
      "/api/reports/drafts",
      "/api/reports/a%2F1/delivery/publish",
      "/api/reports/a%2F1/delivery/manifest",
      "/api/reports/a%2F1/delivery",
      "/api/reports/a%2F1/delivery/acceptance",
      "/api/reports/a%2F1/delivery/acceptance/accept",
      "/api/reports/a%2F1/delivery/quick-draft",
      "/api/tasks/t%2F1/delivery/quick-draft",
      "/api/privacy/deletion-requests",
      "/api/privacy/deletion-requests/d%2F1",
      "/api/privacy/deletion-requests/d%2F1/approve",
      "/api/privacy/deletion-requests/d%2F1/confirm",
      "/api/privacy/deletion-requests/d%2F1/execute",
      "/api/privacy/deletion-requests/d%2F1/proof",
      "/api/privacy/dsr-cases",
      "/api/privacy/legal-holds",
    ],
  );
});

test("成员动作使用登记路径与请求体", async () => {
  const calls: Array<{ path: string; method: string; body: string | null }> = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (url, init) => {
    calls.push({
      path: new URL(String(url), "http://localhost").pathname,
      method: init?.method ?? "GET",
      body: typeof init?.body === "string" ? init.body : null,
    });
    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  try {
    const store = new IntentKeyStore();
    await inviteWorkspaceMember("member@example.com", "member", store);
    await updateWorkspaceMemberRole("u1", "admin", store);
    await grantProjectMember("p1", "u1", store);
    await revokeProjectMember("p1", "u1", store);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.deepEqual(calls, [
    [
      "/api/workspaces/current/members",
      "POST",
      JSON.stringify({ email: "member@example.com", role: "member" }),
    ],
    [
      "/api/workspaces/current/members/u1",
      "PATCH",
      JSON.stringify({ role: "admin" }),
    ],
    [
      "/api/projects/p1/members",
      "POST",
      JSON.stringify({ user_id: "u1" }),
    ],
    ["/api/projects/p1/members/u1", "DELETE", null],
  ]);
});

test("同一意图复用幂等键，重试不换键", () => {
  const store = new IntentKeyStore();
  const first = store.key("run-submit:t1:v1");
  assert.equal(store.key("run-submit:t1:v1"), first);
  assert.notEqual(store.key("run-submit:t1:v2"), first);
  store.reset("run-submit:t1:v1");
  assert.notEqual(store.key("run-submit:t1:v1"), first);
});

test("重试提交复用第一次的 Idempotency-Key", async () => {
  const seen: Array<string | null> = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (_url, init) => {
    seen.push(new Headers(init?.headers).get("Idempotency-Key"));
    return new Response(
      JSON.stringify({
        workbench_task_id: "t1",
        workflow_version_id: "v1",
        runs: [],
        run_ids: [],
        gaps: [],
        idempotent_replay: false,
      }),
      { status: 201, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;
  try {
    const store = new IntentKeyStore();
    await retryRunSubmission(RUN_INPUT, store);
    await retryRunSubmission(RUN_INPUT, store);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(seen.length, 2);
  assert.ok(seen[0]);
  assert.equal(seen[1], seen[0]);
});

test("发起人不能批准自己的请求", () => {
  assert.equal(canDecideApproval(approvalInput()), false);
  assert.equal(canDecideApproval(approvalInput({ currentUserId: "u2" })), true);
  assert.equal(
    canDecideApproval(approvalInput({ currentUserId: "u2", currentRole: "member" })),
    false,
  );
  assert.equal(
    canDecideApproval(approvalInput({ currentUserId: "u2", status: "approved" })),
    false,
  );
});

test("tool_not_priced 与幂等冲突有独立状态", () => {
  assert.equal(
    isToolNotPriced(new GovernanceApiError(422, "tool_not_priced", "tool_not_priced")),
    true,
  );
  assert.equal(
    isIdempotencyConflict(
      new GovernanceApiError(409, "idempotency_conflict", "idempotency_conflict"),
    ),
    true,
  );
  assert.equal(isToolNotPriced(new Error("other")), false);
});

test("Quick 稿没有验收动作，逾期才出现 deemed-accepted", () => {
  assert.deepEqual(
    acceptanceActionsFor("quick_draft", "pending", null),
    [],
  );
  assert.deepEqual(
    acceptanceActionsFor(
      "formal",
      "pending",
      "2026-10-20T00:00:00Z",
      new Date("2026-10-22T00:00:00Z"),
    ),
    ["accept", "dispute", "deemed-accepted"],
  );
  assert.deepEqual(acceptanceActionsFor("formal", "accepted", null), []);
});

test("法律保留阻断删除", () => {
  const holds = [
    { status: "active", workspace_id: "w1", project_id: null },
  ];
  assert.equal(legalHoldBlocks(holds, { workspaceId: "w1", projectId: "p1" }), true);
  assert.equal(legalHoldBlocks(holds, { workspaceId: "w2", projectId: "p1" }), false);
  assert.equal(
    legalHoldBlocks(
      [{ status: "released", workspace_id: "w1", project_id: null }],
      { workspaceId: "w1", projectId: "p1" },
    ),
    false,
  );
});

test("客户 MCP 配置只使用登记入口与 Bearer 占位符", () => {
  assert.deepEqual(customerMcpConfig("https://scrapy.luteos.com/"), {
    mcpServers: {
      "dih-customer": {
        type: "streamable-http",
        url: "https://scrapy.luteos.com/mcp/customer",
        headers: { Authorization: "Bearer ${DIH_CUSTOMER_MCP_KEY}" },
      },
    },
  });
});

test("ClaimView 覆盖 C7 交接的 13 个字段", () => {
  const fields = Object.keys(CLAIM_VIEW_FIELD_MAP).sort();
  assert.deepEqual(fields, [
    "blocked_reason",
    "claim_id",
    "claim_status",
    "counterevidence_text",
    "evidence_grade",
    "evidence_ids",
    "independent_source_count",
    "owner",
    "review_status",
    "risk_flags",
    "scope",
    "text",
    "text_en",
  ]);
  const claim: ClaimView = {
    claim_id: "c1",
    text: "需求增长",
    text_en: "Demand grows",
    claim_status: "directional",
    evidence_grade: "L3_live_single",
    risk_flags: ["single_source"],
    review_status: "approved",
    independent_source_count: 1,
    blocked_reason: null,
    scope: {
      market: "US",
      window_start: "2026-01-01",
      window_end: "2026-03-31",
      window_days: 90,
      sample_n: 12,
    },
    counterevidence_text: "无",
    owner: "u1",
    evidence_ids: ["e1"],
  };
  assert.equal(claim.scope.market, "US");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm -C apps/scraper-console exec node --test "src/lib/api/governance-actions.test.ts"`
Expected: FAIL。`governance-actions.ts` 与 `reports.ts` 的 `ClaimView` 尚不存在。


- [ ] **Step 3: 写治理动作客户端与 ClaimView**

Create `governance-actions.ts` with every path and export asserted in Step 1. Every mutation accepts an `IntentKeyStore`; the store key is `action:resource:payload_sha256`, and retries reuse the same `Idempotency-Key`. `retryRunSubmission` replays `POST /api/runs`; it does not call an unregistered retry endpoint. Add C7's exact `ClaimView` fields to `reports.ts`: `claim_id`, `text`, `text_en`, `claim_status`, `evidence_grade`, `risk_flags`, `review_status`, `independent_source_count`, `blocked_reason`, `scope`, `counterevidence_text`, `owner`, `evidence_ids`.

The implementation must export the clients listed in **Interfaces** and reject `idempotency_conflict` without silently generating a new key. `ProjectKeyCreateResponse.plaintext_key` is optional and is never persisted in cache or local storage.

成员动作按 C2 交接实现：`inviteWorkspaceMember(email, role, store)` 调用 `POST /api/workspaces/current/members`，body `{"email": email, "role": role}`；`updateWorkspaceMemberRole(userId, role, store)` 调用 `PATCH /api/workspaces/current/members/{user_id}`，body `{"role": role}`；`grantProjectMember(projectId, userId, store)` 调用 `POST /api/projects/{project_id}/members`，body `{"user_id": userId}`；`revokeProjectMember(projectId, userId, store)` 调用 `DELETE /api/projects/{project_id}/members/{user_id}`。邀请与改角色成功后刷新 `fetchWorkspaceMembers()`；项目分配成功后刷新 `GET /api/projects/{project_id}/members`。最后 owner 冲突返回 `workspace_last_owner_required` 时不得改本地角色。

- [ ] **Step 4: 写内联动作组件并挂载页面**

Create the five component files listed above.

- `governance-actions.tsx`: submit/replay run, cancel, inline approval create/decide. Use `canDecideApproval`; requester cannot self-approve.
- `members-and-keys.tsx`:
  - 成员区块根节点 `data-testid="settings-members"`；密钥区块根节点 `data-testid="settings-project-keys"`。两者同属该组件，但选择器不互相嵌套。角色文案统一使用 `roleLabel`。
  - owner 渲染邀请表单：`member-invite-form`、`member-invite-email`、`member-invite-role`（选项 owner/admin/member）、`member-invite-submit`。admin 与 member 不渲染。
  - 每个成员行使用 `member-row-<email>`；owner 对每行渲染 `member-role-<email>`，对非本人行渲染 `member-remove-<email>`；admin 与 member 不渲染角色下拉与移除按钮。
  - owner 与 admin 渲染 `project-member-panel`，内含 `project-member-project`（option value 为 `project.id`）、`project-member-user`（option value 为 `user.id`）、`project-member-grant`、`project-member-row-<project>-<email>` 与 `project-member-revoke-<project>-<email>`；member 不渲染。
  - admin 与 member 渲染 `members-non-owner-hint`，文案固定为“只有工作区所有者可以添加、移除成员或修改角色。管理员可以查看成员列表。”
  - 错误行 `member-error` 原样显示 `error.code`；至少区分 `workspace_last_owner_required`、`workspace_owner_immovable`、`workspace_owner_required`、`workspace_member_exists`、`workspace_member_not_found`、`project_member_exists`。不得合并成泛化文案。
  - 邀请成功后清空邮箱输入并重新读取成员列表；改角色、移除与项目分配成功后重新读取对应列表；失败时保留当前选择。
  - 密钥区：key create/rotate/revoke；`plaintext_key` 只在创建后显示一次于 `<code data-testid="project-key-plaintext">`，刷新或导航后清除；客户 MCP 配置不得显示 provider、Cookie 或内部单价。
- `quota-cards.tsx`: render `daily_limit_usd`, `reserved_usd`, `used_usd`, `remaining_usd`; show separate `tool_not_priced`, `approval_required`, `quota_exceeded` states. Quota increases only create the registered `budget_overage` approval action.
- `review-delivery-actions.tsx`: reviewer assign/revoke, review approve/reject, owner/admin publish, revisions, Quick draft, formal delivery publish/download, acceptance accept/dispute/deemed. Hide acceptance actions for `quick_draft` and display `方向稿不启动验收`.
- `privacy-actions.tsx`: deletion create/approve/confirm/execute/proof and DSR list. Disable execute when `legalHoldBlocks(...)` is true; display `legal_hold_active`. Mount write actions only when `workspace.slug` starts with `e2e-` in local/CI.

Mount them in task detail, settings and report pages. 在 `/settings` 用 `<MembersAndKeys />` 替换 Task 8 的成员区块，保留 `data-testid="settings-members"` 根节点；不新增 `/settings/members` 页面或链接。All errors render `error.code` so `idempotency_conflict`, `workspace_last_owner_required`, `workspace_owner_immovable`, `project_access_forbidden`, `report_forbidden_language`, `delivery_pii_detected` and `legal_hold_active` remain distinct.

- [ ] **Step 5: 运行客户端测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
pnpm -C apps/scraper-console exec node --test \
  "src/lib/api/governance-actions.test.ts" \
  "src/lib/inline-approvals.test.ts"
pnpm -C apps/scraper-console exec tsc --noEmit
```

Expected: all tests pass; TypeScript exits 0.

- [ ] **Step 6: 写治理动作 Playwright**

Create `apps/scraper-console/e2e/governance-actions.spec.ts` with seven named tests:

1. `task submit reuses one idempotency key`: intercept POST `/api/runs`; all retries use one non-empty key.
2. `requester cannot self approve`: `approval-decide-approved` is disabled.
3. `project key plaintext is one time`: create shows `dih_...`; reload removes the plaintext element.
4. `same workspace cross project is denied`: limited member opens another project's report and sees `project_access_forbidden`.
5. `quick draft has no acceptance`: Quick page shows `方向稿不启动验收`; no accept/dispute/deemed buttons.
6. `legal hold blocks synthetic deletion`: active legal hold disables execute and displays `legal_hold_active`.
7. `public share remains absent`: `/reports/public/not-enabled` returns 404 or login and no share button.

Use only the dedicated synthetic workspace and the Task 9 seed manifest. Do not point these mutation tests at production A or B.

- [ ] **Step 6b: 写成员面板 Playwright**

Create `apps/scraper-console/e2e/members.spec.ts`，使用 `test.describe.configure({ mode: "serial" })`，读取 Task 9 生成的 `tmp/console-e2e.json` 中的 `main_email`、`other_email` 与 `project_id`。只读 admin/member 视角用 `page.route("**/api/auth/me", ...)` 取真实响应后把 `role` 改为 `admin` 或 `member`；邀请、改角色、最后 owner 错误与项目分配使用真实 owner storage state 与真实 API。每个用例监听 `console` 的 `error`、`pageerror` 与 `/api/` 5xx，结束断言三者均为空；Task 10 的 `watchPage` 可复用，但不作为本任务的前置依赖。

1. `members panel is inline on settings`: 打开 `/settings`；`page.url()` 以 `/settings` 结尾；`settings-members`、`member-invite-form`、`member-invite-email`、`member-invite-role`、`member-invite-submit`、`member-row-<main_email>`、`member-role-<main_email>` 与 `project-member-panel` 可见；`member-remove-<main_email>` 数量为 0；`a[href="/settings/members"]` 数量为 0。
2. `owner invites member`: 在 `member-invite-email` 填 `other_email`，`member-invite-role` 选 `member`，点 `member-invite-submit`；`member-row-<other_email>` 可见；`member-error` 数量为 0。
3. `owner changes member role`: `member-role-<other_email>` 选 `admin`；刷新后该行包含“管理员”；再选 `member`，刷新后包含“成员”。
4. `last owner error is visible`: `member-role-<main_email>` 选 `member`；`member-error` 包含 `workspace_last_owner_required`；`member-row-<main_email>` 仍包含“所有者”。
5. `owner grants and revokes project assignment`: `project-member-project` 选 `project_id`；`project-member-user` 选 label `other_email`；点 `project-member-grant`；`project-member-row-<project_id>-<other_email>` 可见；点 `project-member-revoke-<project_id>-<other_email>` 后该 test id 数量为 0。
6. `admin sees project assignment but no workspace mutations`: route `/api/auth/me` 的 `role` 为 `admin`；成员行可见；`project-member-panel` 与 `members-non-owner-hint` 可见；`member-invite-form`、`member-role-<other_email>`、`member-remove-<other_email>` 数量均为 0。
7. `member sees read-only list`: route `role` 为 `member`；成员行与 `members-non-owner-hint` 可见；`member-invite-form`、`member-role-<other_email>`、`member-remove-<other_email>` 与 `project-member-panel` 数量均为 0。
8. `owner removes invited member`: 点击 `member-remove-<other_email>`；`member-row-<other_email>` 数量为 0；成员列表不再包含该邮箱。

`project-member-project` 的 option 使用 `value=project.id`、label 为 `project.name`；`project-member-user` 的 option 使用 `value=user.id`、label 为 `user.email`；邀请目标必须是种子中已存在、尚未加入当前工作区的用户。不得访问生产。

- [ ] **Step 7: 运行治理动作浏览器测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
pnpm -C apps/scraper-console exec playwright test \
  e2e/governance-actions.spec.ts e2e/members.spec.ts --project=authenticated
```

Expected: `15 passed`（治理动作 7 + 成员面板 8）；no console/pageerror/5xx；the test database is the local/CI E2E database.

- [ ] **Step 8: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c14
git add apps/scraper-console/src/lib/api/governance-actions.ts \
  apps/scraper-console/src/lib/api/governance-actions.test.ts \
  apps/scraper-console/src/lib/api/reports.ts \
  apps/scraper-console/src/components/workbench/governance-actions.tsx \
  apps/scraper-console/src/components/settings/members-and-keys.tsx \
  apps/scraper-console/src/components/settings/quota-cards.tsx \
  apps/scraper-console/src/components/reports/review-delivery-actions.tsx \
  apps/scraper-console/src/components/settings/privacy-actions.tsx \
  apps/scraper-console/src/components/workbench/task-detail.tsx \
  apps/scraper-console/src/app/settings/page.tsx \
  'apps/scraper-console/src/app/reports/[artifactId]/page.tsx' \
  apps/scraper-console/e2e/governance-actions.spec.ts \
  apps/scraper-console/e2e/members.spec.ts
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(console): wire registered governance actions"
```

Expected: `partial` and `truncated` are false. The commit contains no API route, migration, MCP, public-share page or production infrastructure write.

---

### Task 9: E2E 种子、清理与 auth storage

**Files:**
- Create: `apps/api/src/data_intelligence_hub/maintenance/e2e_seed.py`
- Create: `apps/api/tests/unit/test_e2e_seed.py`
- Create: `apps/api/tests/integration/test_e2e_seed_db.py`
- Modify: `apps/api/src/data_intelligence_hub/maintenance/e2e_cleanup.py`
- Create: `scripts/seed-console-e2e.sh`
- Create: `apps/scraper-console/e2e/auth.setup.ts`
- Modify: `apps/scraper-console/playwright.config.ts`

**Interfaces:**
- Consumes: 现有 `User`、`Workspace`、`WorkspaceMember`、`Project`、`Source`、`CollectionTask`、`TaskRun`、`RawRecord`、`Report`、`Dataset`、`DatasetVersion`、C4 `WorkbenchTask`、C8 `MarketAssessment` 与 `DataGap`。
- Produces: `build_seed_rows(password)`、`seed_e2e(session, rows)`、`tmp/console-e2e.json`、`tmp/playwright-console-auth.json`。

- [ ] **Step 1: 写失败测试**

`apps/api/tests/unit/test_e2e_seed.py`：

```python
import os
from pathlib import Path

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.maintenance.e2e_seed import build_seed_rows

REPO_ROOT = Path(__file__).resolve().parents[4]
TAXONOMY_PATH = REPO_ROOT / "configs/taxonomy/maternal_v1.json"


def _configure_taxonomy() -> None:
    os.environ.setdefault("WORKBENCH_TAXONOMY_PATH", str(TAXONOMY_PATH))
    get_settings.cache_clear()


def test_seed_rows_are_deterministic_and_isolated() -> None:
    _configure_taxonomy()
    first = build_seed_rows("e2e-password-123")
    second = build_seed_rows("e2e-password-123")
    assert first.user_main.id == second.user_main.id
    assert first.workspace_main.id == second.workspace_main.id
    assert first.user_main.email.startswith("e2e-")
    assert first.user_other.email.startswith("e2e-")
    assert first.report_main.id != first.report_other.id
    assert first.version_main.quality_status == "qualified_with_gap"
    assert first.market_assessment.sample_counts["reviews"] is None
    assert first.data_gap.actual_value is None


def test_seed_contains_no_cookie_fields() -> None:
    _configure_taxonomy()
    rows = build_seed_rows("e2e-password-123")
    text = repr(rows)
    assert "creator_cookie" not in text
    assert "cookie" not in text.lower()
```

- [ ] **Step 1b: 写真实数据库种子与哈希链测试**

`apps/api/tests/integration/test_e2e_seed_db.py`：

```python
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.maintenance.e2e_seed import build_seed_rows, seed_e2e
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AUDIT_GENESIS_HASH, AuditEvent
from data_intelligence_hub.services.audit_log import verify_audit_chain

REPO_ROOT = Path(__file__).resolve().parents[4]
TAXONOMY_PATH = REPO_ROOT / "configs/taxonomy/maternal_v1.json"
PASSWORD = "e2e-password-123"
SEED_REQUEST_ID = "e2e-handoff-seed"


def _configure_workbench(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_TASKS_ENABLED", "true")
    monkeypatch.setenv("WORKBENCH_TAXONOMY_PATH", str(TAXONOMY_PATH))
    get_settings.cache_clear()


async def _seed_events(
    session_factory: async_sessionmaker[AsyncSession],
    workspace_id: object,
) -> list[AuditEvent]:
    async with session_factory() as session:
        result = await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.sequence_number)
        )
        return list(result.all())


@pytest_asyncio.fixture()
async def sqlite_session_factory() -> AsyncIterator[
    async_sessionmaker[AsyncSession]
]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seed_e2e_appends_one_valid_audit_event(
    sqlite_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_workbench(monkeypatch)
    rows = build_seed_rows(PASSWORD)

    async with sqlite_session_factory() as session:
        await seed_e2e(session, rows)

    events = await _seed_events(sqlite_session_factory, rows.workspace_main.id)
    assert len(events) == 1
    assert events[0].sequence_number == 1
    assert events[0].prev_hash == AUDIT_GENESIS_HASH
    assert events[0].action == "project.created"
    assert events[0].request_id == SEED_REQUEST_ID
    assert events[0].workspace_id == rows.workspace_main.id
    assert events[0].actor_user_id == rows.user_main.id
    assert verify_audit_chain(events) == (True, None)

    async with sqlite_session_factory() as session:
        await seed_e2e(session, rows)

    replayed = await _seed_events(sqlite_session_factory, rows.workspace_main.id)
    assert len(replayed) == 1
    assert verify_audit_chain(replayed) == (True, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("CONSOLE_E2E_DATABASE_TEST") != "true",
    reason="requires migrated console E2E PostgreSQL database",
)
async def test_seed_e2e_appends_valid_audit_chain_on_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_workbench(monkeypatch)
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        pytest.skip("console E2E PostgreSQL test requires DATABASE_URL")
    if "console_e2e" not in settings.database_url:
        pytest.skip("DATABASE_URL must target a console E2E database")
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        rows = build_seed_rows(PASSWORD)
        async with session_factory() as session:
            await seed_e2e(session, rows)
        events = await _seed_events(session_factory, rows.workspace_main.id)
        seed_events = [
            event for event in events if event.request_id == SEED_REQUEST_ID
        ]
        assert len(seed_events) == 1
        assert seed_events[0].action == "project.created"
        assert verify_audit_chain(events) == (True, None)

        async with session_factory() as session:
            await seed_e2e(session, rows)
        replayed = await _seed_events(session_factory, rows.workspace_main.id)
        assert len(
            [event for event in replayed if event.request_id == SEED_REQUEST_ID]
        ) == 1
        assert verify_audit_chain(replayed) == (True, None)
    finally:
        await engine.dispose()
        get_settings.cache_clear()
```

Run: `cd apps/api && uv run pytest tests/integration/test_e2e_seed_db.py -v`
Expected: FAIL，报模块不存在。

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd apps/api
uv run pytest tests/unit/test_e2e_seed.py tests/integration/test_e2e_seed_db.py -v
```
Expected: FAIL，报 `e2e_seed` 模块不存在。

- [ ] **Step 3: 写种子实现**

`apps/api/src/data_intelligence_hub/maintenance/e2e_seed.py`：

```python
from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.core.security import hash_password
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

NAMESPACE = uuid.UUID("2f4f6b7e-3c9a-4d31-9c2e-8a1b7d5e6f00")
MANIFEST_PATH = Path("tmp/console-e2e.json")


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"c14-console:{key}")


@dataclass(frozen=True)
class SeedRows:
    user_main: User
    user_other: User
    workspace_main: Workspace
    workspace_other: Workspace
    member_main: WorkspaceMember
    member_other: WorkspaceMember
    project_main: Project
    project_other: Project
    source_main: Source
    task_main: CollectionTask
    run_main: TaskRun
    raw_records: tuple[RawRecord, RawRecord]
    report_main: Report
    report_other: Report
    dataset_main: Dataset
    version_main: DatasetVersion
    workbench_main: WorkbenchTask
    market_assessment: MarketAssessment
    data_gap: DataGap


def build_seed_rows(password: str) -> SeedRows:
    now = datetime.now(UTC).replace(microsecond=0)
    window_start = now.date() - timedelta(days=30)
    window_end = now.date() - timedelta(days=1)
    user_main = User(
        id=_id("user-main"),
        email="e2e-console@example.com",
        password_hash=hash_password(password),
        name="E2E Console",
        status="active",
        created_at=now,
        updated_at=now,
    )
    user_other = User(
        id=_id("user-other"),
        email="e2e-console-other@example.com",
        password_hash=hash_password(password),
        name="E2E Other",
        status="active",
        created_at=now,
        updated_at=now,
    )
    workspace_main = Workspace(
        id=_id("workspace-main"),
        name="E2E Console Workspace",
        slug="e2e-console-main",
        owner_id=user_main.id,
        created_at=now,
        updated_at=now,
    )
    workspace_other = Workspace(
        id=_id("workspace-other"),
        name="E2E Other Workspace",
        slug="e2e-console-other",
        owner_id=user_other.id,
        created_at=now,
        updated_at=now,
    )
    member_main = WorkspaceMember(
        id=_id("member-main"),
        workspace_id=workspace_main.id,
        user_id=user_main.id,
        role="owner",
        created_at=now,
        updated_at=now,
    )
    member_other = WorkspaceMember(
        id=_id("member-other"),
        workspace_id=workspace_other.id,
        user_id=user_other.id,
        role="owner",
        created_at=now,
        updated_at=now,
    )
    project_main = Project(
        id=_id("project-main"),
        workspace_id=workspace_main.id,
        name="E2E Maternal Project",
        description="C14 console acceptance fixture",
        domain="mixed",
        status="active",
        owner_id=user_main.id,
        created_at=now,
        updated_at=now,
    )
    project_other = Project(
        id=_id("project-other"),
        workspace_id=workspace_other.id,
        name="E2E Other Project",
        description="C14 cross-tenant negative fixture",
        domain="mixed",
        status="active",
        owner_id=user_other.id,
        created_at=now,
        updated_at=now,
    )
    source_main = Source(
        id=_id("source-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        name="E2E Source",
        type="manual_json",
        url=None,
        config={},
        schedule_cron=None,
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    task_main = CollectionTask(
        id=_id("collection-task-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        source_id=source_main.id,
        collector_type="manual_json",
        name="E2E Collection Task",
        schedule_cron=None,
        status="enabled",
        config={},
        success_count=1,
        failure_count=0,
        last_run_at=now,
        created_at=now,
        updated_at=now,
    )
    run_main = TaskRun(
        id=_id("run-main"),
        task_id=task_main.id,
        workspace_id=workspace_main.id,
        status="success",
        started_at=now - timedelta(minutes=2),
        finished_at=now - timedelta(minutes=1),
        records_count=2,
        entities_count=0,
        error_message=None,
        error_traceback=None,
        logs=[
            {
                "step": "collect",
                "message": "e2e seed",
                "level": "info",
                "timestamp": now.isoformat(),
            }
        ],
        created_at=now - timedelta(minutes=2),
        project_id=project_main.id,
    )
    raw_one = RawRecord(
        id=_id("raw-one"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        source_id=source_main.id,
        task_run_id=run_main.id,
        record_type="e2e_product",
        source_url="https://example.com/product/1",
        content={"title": "E2E Product One", "price": 19.99},
        content_hash="a" * 64,
        screenshot_url=None,
        collected_at=now - timedelta(minutes=2),
        created_at=now - timedelta(minutes=2),
    )
    raw_two = RawRecord(
        id=_id("raw-two"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        source_id=source_main.id,
        task_run_id=run_main.id,
        record_type="e2e_review",
        source_url="https://example.com/review/1",
        content={"title": "E2E Review One", "rating": 5},
        content_hash="b" * 64,
        screenshot_url=None,
        collected_at=now - timedelta(minutes=2),
        created_at=now - timedelta(minutes=2),
    )
    report_main = Report(
        id=_id("report-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        report_type="daily",
        title="E2E 母婴洞察报告",
        content="# E2E 报告\n\n这是验收种子。",
        status="generated",
        period_start=now - timedelta(days=30),
        period_end=now - timedelta(days=1),
        created_at=now - timedelta(minutes=30),
    )
    report_other = Report(
        id=_id("report-other"),
        workspace_id=workspace_other.id,
        project_id=project_other.id,
        report_type="daily",
        title="E2E 其他工作区报告",
        content="# Other\n\nCross-tenant fixture.",
        status="generated",
        period_start=now - timedelta(days=30),
        period_end=now - timedelta(days=1),
        created_at=now - timedelta(minutes=30),
    )
    dataset_main = Dataset(
        id=_id("dataset-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        name="E2E Dataset",
        dataset_type="ecommerce_product",
        status="active",
        description="C14 console acceptance fixture",
        created_at=now,
        updated_at=now,
    )
    version_main = DatasetVersion(
        id=_id("dataset-version-main"),
        dataset_id=dataset_main.id,
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        created_by_user_id=user_main.id,
        cleaning_plan_id=None,
        source_workflow_run_id=None,
        source_workflow_step_run_ids=None,
        source_raw_record_ids=None,
        lineage_contract_version=None,
        version_number=1,
        source_task_run_ids=[str(run_main.id)],
        selected_fields=["title", "price"],
        cleaning_script=[],
        rows=[{"title": "E2E Product One", "price": 19.99}],
        export_preview={},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=now,
        task_id=_id("workbench-main"),
        market="US",
        content_sha256="c" * 64,
        schema_hash="d" * 64,
        quality_status="qualified_with_gap",
    )
    workbench_main = WorkbenchTask(
        id=_id("workbench-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        created_by_user_id=user_main.id,
        owner_id=user_main.id,
        brand="E2E Baby",
        category=_seed_category_id(),
        competitors=[],
        markets=["US"],
        locale_by_market={"US": "en-US"},
        window_start=window_start,
        window_end=window_end,
        decision_question="美国母婴市场是否值得进入？",
        does_not_answer=[],
        task_type="T1",
        task_type_confidence=None,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    data_gap = DataGap(
        id=_id("data-gap-reviews"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        task_id=workbench_main.id,
        run_id=None,
        step_id=None,
        market="US",
        data_domain="reviews",
        reason_code="data_domain_missing",
        actual_value=None,
        threshold_value=300,
        impact="US 评论样本缺失。",
        customer_text_zh="评论样本不足。实际值：缺失；门槛：300。",
        customer_text_en="Reviews sample is missing. Actual: missing; threshold: 300.",
        remediation="继续采集评论。",
        severity="blocking",
        status="open",
        created_at=now,
        resolved_at=None,
    )
    market_assessment = MarketAssessment(
        id=_id("market-assessment-main"),
        workspace_id=workspace_main.id,
        project_id=project_main.id,
        task_id=workbench_main.id,
        market="US",
        market_role="primary",
        quality_status="qualified_with_gap",
        conclusion_standard=None,
        conclusion_quick=None,
        evidence_grade="L3_live_single",
        core_domain_coverage={
            "products": "pass",
            "reviews": "missing",
            "creator_content": "pass",
        },
        sample_counts={"products": 2, "reviews": None, "creator_content": 1},
        thresholds={"package_type": "quick"},
        gap_ids=[str(data_gap.id)],
        details_json={"scorecard_sha256": "e" * 64},
        computed_at=now,
    )
    return SeedRows(
        user_main=user_main,
        user_other=user_other,
        workspace_main=workspace_main,
        workspace_other=workspace_other,
        member_main=member_main,
        member_other=member_other,
        project_main=project_main,
        project_other=project_other,
        source_main=source_main,
        task_main=task_main,
        run_main=run_main,
        raw_records=(raw_one, raw_two),
        report_main=report_main,
        report_other=report_other,
        dataset_main=dataset_main,
        version_main=version_main,
        workbench_main=workbench_main,
        market_assessment=market_assessment,
        data_gap=data_gap,
    )


def _existing_rows(rows: SeedRows) -> list[Any]:
    return [
        rows.user_main,
        rows.user_other,
        rows.workspace_main,
        rows.workspace_other,
        rows.member_main,
        rows.member_other,
        rows.project_main,
        rows.project_other,
        rows.source_main,
        rows.task_main,
        rows.run_main,
        *rows.raw_records,
        rows.report_main,
        rows.report_other,
        rows.dataset_main,
        rows.version_main,
        rows.workbench_main,
        rows.market_assessment,
        rows.data_gap,
    ]


def _seed_category_id() -> str:
    """返回 C4 taxonomy 中确定性的品类 ID，不依赖进程 cwd。"""
    return sorted(load_maternal_category_ids())[0]


async def seed_e2e(session: Any, rows: SeedRows) -> None:
    for row in _existing_rows(rows):
        await session.merge(row)
    await session.commit()


def _manifest(rows: SeedRows, password: str) -> dict[str, str]:
    return {
        "main_email": rows.user_main.email,
        "other_email": rows.user_other.email,
        "password": password,
        "project_id": str(rows.project_main.id),
        "other_project_id": str(rows.project_other.id),
        "report_id": str(rows.report_main.id),
        "other_report_id": str(rows.report_other.id),
        "dataset_id": str(rows.dataset_main.id),
        "run_id": str(rows.run_main.id),
        "task_id": str(rows.workbench_main.id),
        "category_id": rows.workbench_main.category,
    }


async def _run(execute: bool, password: str, manifest_path: Path) -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("e2e_seed_refuses_production")
    rows = build_seed_rows(password)
    if not execute:
        print(json.dumps(_manifest(rows, password), ensure_ascii=False, indent=2, sort_keys=True))
        return
    async with async_session_factory() as session:
        await seed_e2e(session, rows)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(_manifest(rows, password), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest_path.chmod(0o600)
    print("console_e2e_seeded")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed isolated C14 console E2E fixtures.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--password", default=os.getenv("CONSOLE_E2E_PASSWORD", ""))
    parser.add_argument("--manifest-path", default=str(MANIFEST_PATH))
    args = parser.parse_args()
    if len(args.password) < 8:
        raise SystemExit("CONSOLE_E2E_PASSWORD must be at least 8 characters")
    asyncio.run(_run(args.execute, args.password, Path(args.manifest_path)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行种子测试**

Run: `cd apps/api && WORKBENCH_TAXONOMY_PATH="$PWD/../../configs/taxonomy/maternal_v1.json" uv run pytest tests/unit/test_e2e_seed.py tests/integration/test_e2e_seed_db.py -v`
Expected: `3 passed, 1 skipped`；PostgreSQL 用例因未设置 `CONSOLE_E2E_DATABASE_TEST` 跳过。

Run（已迁移的本地/CI PostgreSQL E2E 库）：
```bash
cd apps/api
DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/dih_console_e2e' \
CONSOLE_E2E_DATABASE_TEST=true \
WORKBENCH_TASKS_ENABLED=true \
WORKBENCH_TAXONOMY_PATH="$PWD/../../configs/taxonomy/maternal_v1.json" \
uv run pytest tests/integration/test_e2e_seed_db.py -v
```
Expected: `2 passed`；SQLite 用例与 PostgreSQL 用例都执行。该命令验证真实 PostgreSQL 上种子 `project.created` 事件恰好一条、完整哈希链 `verify_audit_chain == (True, None)`，以及重复 seed 不追加第二条审计。

- [ ] **Step 5: 扩展清理并写清库、种子脚本**

`e2e_cleanup.py` 目前不认识 `workbench_tasks`。不扩展时，清理 E2E 工作区会被外键拦住。做以下修改：

1. 导入 `WorkbenchTask` 与 `WorkflowVersion`。
2. 在 `notification_ids` 前取：

```python
    workbench_task_ids = _unique_ids(
        await _fetch_ids(
            session,
            select(WorkbenchTask.id).where(
                or_(
                    WorkbenchTask.workspace_id.in_(workspace_ids),
                    WorkbenchTask.project_id.in_(project_ids),
                    WorkbenchTask.created_by_user_id.in_(user_ids),
                    WorkbenchTask.owner_id.in_(user_ids),
                ),
            ),
        )
    )
```

3. 在 `counts` 中加入 `"workbench_tasks": len(workbench_task_ids),`。
4. 在 `_apply_cleanup` 的参数列表中加入 `workbench_task_ids: list[uuid.UUID],`，调用处传入该参数。
5. 在删除 `Project` 前执行：

```python
    if workbench_task_ids:
        await session.execute(
            update(WorkflowVersion)
            .where(WorkflowVersion.workbench_task_id.in_(workbench_task_ids))
            .values(workbench_task_id=None)
        )
    await _delete_ids(session, WorkbenchTask, workbench_task_ids)
```

若 C4 的 `runs.workbench_task_id` 列已存在，先按同样方式置空，再删除任务单。C14 的种子和黄金路径不创建 `runs` 行；这一句只防止其他 E2E 用例留下引用。

`scripts/seed-console-e2e.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/apps/api"

# C4 workbench 配置只用于本地/CI E2E。taxonomy 必须是绝对路径，不能依赖 cwd。
export WORKBENCH_TASKS_ENABLED=true
: "${WORKBENCH_TAXONOMY_PATH:=$ROOT_DIR/configs/taxonomy/maternal_v1.json}"
if [[ "$WORKBENCH_TAXONOMY_PATH" != /* ]]; then
  echo "WORKBENCH_TAXONOMY_PATH must be absolute" >&2
  exit 2
fi
export WORKBENCH_TAXONOMY_PATH

if [[ -z "${CONSOLE_E2E_PASSWORD:-}" || ${#CONSOLE_E2E_PASSWORD} -lt 8 ]]; then
  echo "CONSOLE_E2E_PASSWORD must be at least 8 characters" >&2
  exit 2
fi

uv run python -m data_intelligence_hub.maintenance.e2e_cleanup \
  --execute --older-than-hours 0
uv run python -m data_intelligence_hub.maintenance.e2e_seed \
  --execute --manifest-path "$ROOT_DIR/tmp/console-e2e.json"
```

- [ ] **Step 5b: 补 C2/C3/C11/C12/C13 交接种子与清理

在 `e2e_seed.py` 追加（`CUSTOMER_MCP_TOOLS` 从 `apps/scraper-console/src/lib/api/privacy-handoff.ts` 同步为 Python 常量，禁止在测试中手写第二份工具名）：

```python
from sqlalchemy import select

from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.privacy_deletion import DeletionRequest
from data_intelligence_hub.models.retention import LegalHold
from data_intelligence_hub.services.audit_log import append_audit_event

CUSTOMER_MCP_TOOLS = (
    "discover_capabilities",
    "estimate_task",
    "create_task",
    "get_task",
    "cancel_task",
    "get_delivery_manifest",
    "get_evidence",
    "collect",
)

SEED_AUDIT_REQUEST_ID = "e2e-handoff-seed"


def build_handoff_rows(rows: SeedRows) -> tuple[object, ...]:
    now = datetime.now(UTC).replace(microsecond=0)
    return (
        ProjectApiKey(
            id=_id("key-handoff"),
            workspace_id=rows.workspace_main.id,
            project_id=rows.project_main.id,
            label="E2E Customer MCP",
            key_prefix="dih_e2e",
            key_hash="0" * 64,
            created_by_user_id=rows.user_main.id,
            status="active",
            capability_allowlist=["cap-product"],
            tool_allowlist=list(CUSTOMER_MCP_TOOLS),
            daily_collect_quota=10,
            created_at=now,
        ),
        LegalHold(
            id=_id("legal-hold-handoff"),
            workspace_id=rows.workspace_main.id,
            project_id=rows.project_main.id,
            data_class="raw_response",
            status="active",
            reason="e2e legal hold",
            requested_by_user_id=rows.user_main.id,
            requested_at=now,
            created_at=now,
        ),
        DeletionRequest(
            id=_id("deletion-handoff"),
            workspace_id=rows.workspace_main.id,
            project_id=rows.project_main.id,
            target_type="project",
            target_id=rows.project_main.id,
            target_name_snapshot=rows.project_main.name,
            requested_by_user_id=rows.user_main.id,
            requested_by_role="owner",
            status="pending_confirmation",
            reason="e2e seeded request",
            created_at=now,
        ),
    )
```

`build_handoff_rows` 只返回可 `merge` 的业务行，不构造 `AuditEvent`。审计行只能由 C2 `append_audit_event` 生成：它负责 `sequence_number`、`prev_hash`、`event_hash`、事件 ID 与并发锁；手写 `AuditEvent` 会缺列并破坏哈希链。动作名必须来自 C1 `audit-actions.v1`，这里使用已登记的 `project.created`，不得自造 `handoff.seeded`。

用以下实现替换 Step 3 的 `seed_e2e`。先 `merge` 确定性的用户/工作区根与全部业务行，再 `flush`，最后追加审计。重复 seed 通过 `request_id` 判定，不追加第二条审计行，也不修改或删除既有审计行：

```python
async def seed_e2e(session: Any, rows: SeedRows) -> None:
    for row in _existing_rows(rows):
        await session.merge(row)
    for row in build_handoff_rows(rows):
        await session.merge(row)
    await session.flush()

    seeded_event_id = await session.scalar(
        select(AuditEvent.id).where(
            AuditEvent.workspace_id == rows.workspace_main.id,
            AuditEvent.action == "project.created",
            AuditEvent.request_id == SEED_AUDIT_REQUEST_ID,
        )
    )
    if seeded_event_id is None:
        await append_audit_event(
            session,
            workspace_id=rows.workspace_main.id,
            project_id=rows.project_main.id,
            actor_user_id=rows.user_main.id,
            actor_type="user",
            action="project.created",
            resource_type="project",
            resource_id=str(rows.project_main.id),
            request_id=SEED_AUDIT_REQUEST_ID,
            result="success",
            details={"seed": True, "fixture": "c14_console_e2e"},
        )
    await session.commit()
```

在 `_manifest` 中追加 `handoff_project_id`，供 C14 的交接面板定位。

在 `e2e_cleanup.py` 顶部加入 `AuditEvent`、`ProjectApiKey`、`LegalHold`、`DeletionRequest` 的导入。在删除顺序中，`Project` 之前追加以下业务对象清理：

```python
    await _delete_ids(
        session,
        DeletionRequest,
        await _fetch_ids(
            session,
            select(DeletionRequest.id).where(
                or_(
                    DeletionRequest.workspace_id.in_(workspace_ids),
                    DeletionRequest.project_id.in_(project_ids),
                )
            ),
        ),
    )
    await _delete_ids(
        session,
        LegalHold,
        await _fetch_ids(
            session,
            select(LegalHold.id).where(
                or_(
                    LegalHold.workspace_id.in_(workspace_ids),
                    LegalHold.project_id.in_(project_ids),
                )
            ),
        ),
    )
    await _delete_ids(
        session,
        ProjectApiKey,
        await _fetch_ids(
            session,
            select(ProjectApiKey.id).where(
                or_(
                    ProjectApiKey.workspace_id.in_(workspace_ids),
                    ProjectApiKey.project_id.in_(project_ids),
                )
            ),
        ),
    )
```

C2 `audit_events` 是追加式哈希链。`e2e_cleanup.py` 不得修改或删除审计行，也不得删除被审计事件外键引用的 E2E 用户和工作区。因此，扩展 `_apply_cleanup` 时：

1. 删除项目级 E2E 业务数据和 `ProjectApiKey`、`LegalHold`、`DeletionRequest`；
2. 保留确定性的 E2E `User`、`Workspace`、`WorkspaceMember` 与种子 `AuditEvent`；
3. 不执行既有的 `Project`、`WorkspaceMember`、`Workspace`、`User` 删除步骤，除非先通过 C2/C11 的正式保留流程，且事件已超过 730 天；C14 不走该例外；
4. 再次运行 seed 时使用 `merge` 更新保留根，不产生重复工作区或审计链分叉。

追加清理回归测试：读取 `e2e_cleanup.py` 源码，断言不存在 `delete(AuditEvent)`、`update(AuditEvent)`、`_delete_ids(session, AuditEvent`。PostgreSQL 集成测试断言清理后种子审计行、E2E 用户和工作区仍存在，业务项目数据已删除，哈希链校验继续通过。

`e2e_cleanup` 与 `seed-console-e2e.sh` 都必须先拒绝生产：

```python
from data_intelligence_hub.core.config import get_settings

if get_settings().app_env == "production":
    raise SystemExit("e2e_cleanup_refuses_production")
```

```bash
if [[ "${APP_ENV:-development}" == "production" ]]; then
  echo "e2e_cleanup_refuses_production" >&2
  exit 2
fi
```

- [ ] **Step 6: 写 auth setup**

`apps/scraper-console/e2e/auth.setup.ts`：

```typescript
import { expect, test as setup } from "@playwright/test";
import path from "node:path";

const AUTH_FILE =
  process.env.PLAYWRIGHT_STORAGE_STATE ??
  path.resolve(process.cwd(), "../../tmp/playwright-console-auth.json");

setup("authenticate", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("邮箱").fill(process.env.CONSOLE_E2E_EMAIL ?? "e2e-console@example.com");
  await page.getByLabel("密码").fill(process.env.CONSOLE_E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/workbench/);
  await page.context().storageState({ path: AUTH_FILE });
});
```

`apps/scraper-console/e2e/auth-limited.setup.ts`：

```typescript
import { expect, test as setup } from "@playwright/test";
import path from "node:path";

const AUTH_FILE =
  process.env.PLAYWRIGHT_LIMITED_STORAGE_STATE ??
  path.resolve(process.cwd(), "../../tmp/playwright-console-limited-auth.json");

setup("authenticate limited member", async ({ page }) => {
  await page.goto("/login");
  await page
    .getByLabel("邮箱")
    .fill(process.env.CONSOLE_E2E_LIMITED_EMAIL ?? "e2e-console-limited@example.com");
  await page.getByLabel("密码").fill(process.env.CONSOLE_E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/workbench/);
  await page.context().storageState({ path: AUTH_FILE });
});
```

- [ ] **Step 7: 更新 Playwright 项目**

把 `apps/scraper-console/playwright.config.ts` 的 `projects` 替换为：

```typescript
const authFile =
  process.env.PLAYWRIGHT_STORAGE_STATE ??
  "../../tmp/playwright-console-auth.json";

projects: [
  {
    name: "setup",
    testMatch: /auth\.setup\.ts/,
  },
  {
    name: "public",
    testIgnore: /auth\.setup\.ts/,
    grepInvert: /@authenticated/,
    use: { ...devices["Desktop Chrome"] },
  },
  {
    name: "authenticated",
    dependencies: ["setup"],
    testMatch: /.*\.spec\.ts/,
    grep: /@authenticated/,
    use: { ...devices["Desktop Chrome"], storageState: authFile },
  },
],
```

- [ ] **Step 8: 本地运行种子与 setup**

先设置只用于本地/CI E2E 的 C4 配置；两个变量都不写入生产：

```bash
export WORKBENCH_TASKS_ENABLED=true
export WORKBENCH_TAXONOMY_PATH="$(git rev-parse --show-toplevel)/configs/taxonomy/maternal_v1.json"
```

Run:
```bash
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash scripts/seed-console-e2e.sh
```
Expected: 输出 `console_e2e_seeded`，生成 `tmp/console-e2e.json`，文件权限 `600`。

Run:
```bash
pnpm -C apps/scraper-console exec playwright test --project=setup
```
Expected: `2 passed`，生成 `tmp/playwright-console-auth.json` 与 `tmp/playwright-console-limited-auth.json`。受限成员只属于 `project_second`，用于 Task 10 的同工作区跨项目负路径。

- [ ] **Step 9: 提交**

```bash
git add apps/api/src/data_intelligence_hub/maintenance/e2e_seed.py \
  apps/api/src/data_intelligence_hub/maintenance/e2e_cleanup.py \
  apps/api/tests/unit/test_e2e_seed.py \
  apps/api/tests/integration/test_e2e_seed_db.py \
  scripts/seed-console-e2e.sh \
  apps/scraper-console/e2e/auth.setup.ts \
  apps/scraper-console/e2e/auth-limited.setup.ts \
  apps/scraper-console/playwright.config.ts
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(console): seed isolated fixtures and save auth storage"
```

---

### Task 10: 正负黄金路径

**Files:**
- Create: `apps/scraper-console/e2e/support/page-problems.ts`
- Create: `apps/scraper-console/e2e/support/seed-manifest.ts`
- Create: `apps/scraper-console/e2e/golden-path.spec.ts`
- Create: `apps/scraper-console/e2e/negative-paths.spec.ts`
- Create: `apps/scraper-console/e2e/limited-member.spec.ts`
- Modify: `apps/scraper-console/e2e/routes.spec.ts`

**Interfaces:**
- Consumes: `tmp/console-e2e.json`、`tmp/playwright-console-auth.json`。
- Produces: 正路径 3 条、负路径 6 条、共享 `watchPage(page)`。

- [ ] **Step 1: 写共享监听器**

`apps/scraper-console/e2e/support/page-problems.ts`：

```typescript
import { expect, type Page } from "@playwright/test";

export type PageProblems = {
  consoleErrors: string[];
  pageErrors: string[];
  apiServerErrors: string[];
};

export function watchPage(page: Page): PageProblems {
  const problems: PageProblems = {
    consoleErrors: [],
    pageErrors: [],
    apiServerErrors: [],
  };
  page.on("console", message => {
    if (message.type() === "error") problems.consoleErrors.push(message.text());
  });
  page.on("pageerror", error => problems.pageErrors.push(error.message));
  page.on("response", response => {
    const url = new URL(response.url());
    if (url.pathname.includes("/api/") && response.status() >= 500) {
      problems.apiServerErrors.push(`${response.status()} ${url.pathname}`);
    }
  });
  return problems;
}

export function expectClean(problems: PageProblems): void {
  expect(problems.pageErrors).toEqual([]);
  expect(problems.apiServerErrors).toEqual([]);
  expect(
    problems.consoleErrors.filter(
      text => !/401|Unauthorized|WebSocket connection to .*\/_next\//i.test(text),
    ),
  ).toEqual([]);
}
```

`apps/scraper-console/e2e/support/seed-manifest.ts`：

```typescript
import { readFileSync } from "node:fs";
import path from "node:path";

export type SeedManifest = {
  main_email: string;
  other_email: string;
  password: string;
  project_id: string;
  other_project_id: string;
  report_id: string;
  other_report_id: string;
  dataset_id: string;
  run_id: string;
  task_id: string;
  category_id: string;
  handoff_project_id: string;
};

export function readSeedManifest(): SeedManifest {
  const file = path.resolve(process.cwd(), "../../tmp/console-e2e.json");
  return JSON.parse(readFileSync(file, "utf8")) as SeedManifest;
}
```

- [ ] **Step 1b: 写同工作区跨项目成员负路径**

`apps/scraper-console/e2e/limited-member.spec.ts`：

```typescript
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const manifest = JSON.parse(
  readFileSync(path.resolve(process.cwd(), "../../tmp/console-e2e.json"), "utf8"),
) as {
  project_id: string;
  report_id: string;
  claim_id: string;
  artifact_id: string;
};

test.use({
  storageState:
    process.env.PLAYWRIGHT_LIMITED_STORAGE_STATE ??
    path.resolve(process.cwd(), "../../tmp/playwright-console-limited-auth.json"),
});

test.describe("同工作区跨项目成员负路径", () => {
  test("任务、Claim、报告、交付与资产一律 403", async ({ request }) => {
    const paths = [
      `/api/workbench/tasks?project_id=${manifest.project_id}`,
      `/api/claims?project_id=${manifest.project_id}`,
      `/api/reports?project_id=${manifest.project_id}`,
      `/api/reports/${manifest.report_id}`,
      `/api/reports/${manifest.artifact_id}/artifact`,
      `/api/claims/${manifest.claim_id}`,
      `/api/automation/product-datasets?project_id=${manifest.project_id}`,
    ];
    for (const pathname of paths) {
      const response = await request.get(pathname);
      expect(response.status(), pathname).toBe(403);
    }
  });
});
```

Run: `pnpm -C apps/scraper-console exec playwright test --project=limited`
Expected: `1 passed`。受限成员只能读取 `project_second`；对同工作区 `project_main` 的任务、Claim、报告、交付与资产一律 403。

- [ ] **Step 2: 写正路径测试**

`apps/scraper-console/e2e/golden-path.spec.ts`：

```typescript
import { expect, test } from "@playwright/test";
import { readSeedManifest } from "./support/seed-manifest";
import { expectClean, watchPage } from "./support/page-problems";

test.describe("@authenticated 正黄金路径", () => {
  test("工作台显示种子任务并可打开详情", async ({ page }) => {
    const seed = readSeedManifest();
    const problems = watchPage(page);
    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-page")).toBeVisible();
    await expect(page.getByTestId("workbench-task-row").first()).toContainText("E2E Baby");
    await page.getByTestId("workbench-task-row").first().click();
    await expect(page.getByTestId("workbench-task-detail")).toBeVisible();
    await expect(page.getByText("E2E Baby")).toBeVisible();
    expect(seed.task_id.length).toBeGreaterThan(0);
    expectClean(problems);
  });

  test("任务表单只渲染正式市场并提交 package_type、主对比市场与 locale", async ({ page }) => {
    const seed = readSeedManifest();
    const problems = watchPage(page);
    const posts: Array<Record<string, unknown>> = [];
    await page.route("**/api/workbench/tasks**", async route => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      posts.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "11111111-1111-1111-1111-111111111111",
          workspace_id: "22222222-2222-2222-2222-222222222222",
          project_id: seed.project_id,
          created_by_user_id: "33333333-3333-3333-3333-333333333333",
          owner_id: "33333333-3333-3333-3333-333333333333",
          brand: "E2E Form",
          category: seed.category_id,
          competitors: [],
          package_type: "standard",
          primary_market: "DE",
          comparison_markets: ["FR", "IT", "ES"],
          markets: ["DE", "FR", "IT", "ES"],
          locale_by_market: { DE: "de-DE", FR: "fr-FR", IT: "it-IT", ES: "es-ES" },
          window_start: "2026-07-01",
          window_end: "2026-09-30",
          decision_question: "德国市场是否值得进入？",
          does_not_answer: [],
          acceptance_contact_id: null,
          max_cost_usd: null,
          max_pages: null,
          max_records: null,
          task_type: null,
          task_type_confidence: null,
          status: "draft",
          created_at: "2026-10-22T00:00:00Z",
          updated_at: "2026-10-22T00:00:00Z",
        }),
      });
    });

    await page.goto("/workbench");
    await expect(page.getByTestId("workbench-primary-market")).toHaveCount(11);
    await expect(page.getByTestId("workbench-comparison-market")).toHaveCount(11);
    await expect(
      page.locator('[data-testid="workbench-primary-market"][data-market-code="JP"]'),
    ).toHaveCount(0);
    await expect(
      page.locator('[data-testid="workbench-primary-market"][data-market-code="US"]'),
    ).toHaveAttribute("aria-pressed", "true");

    const form = page.getByTestId("workbench-task-form");
    await form.getByLabel("品牌").fill("E2E Form");
    await form.getByLabel("品类 ID").fill(seed.category_id);
    await form.getByLabel("决策问题").fill("德国市场是否值得进入？");
    await form.getByLabel("开始日期").fill("2026-07-01");
    await form.getByLabel("结束日期").fill("2026-09-30");

    await page
      .locator('[data-testid="workbench-package-type-option"][data-package-type="standard"]')
      .click();
    await page.locator('[data-testid="workbench-primary-market"][data-market-code="DE"]').click();
    for (const code of ["FR", "IT", "ES"]) {
      await page
        .locator(`[data-testid="workbench-comparison-market"][data-market-code="${code}"]`)
        .click();
    }
    await expect(
      page.locator('[data-testid="workbench-comparison-market"][data-market-code="NL"]'),
    ).toBeDisabled();

    await page.getByTestId("workbench-submit-task").click();
    await expect.poll(() => posts.length).toBe(1);
    expect(posts[0]).toMatchObject({
      package_type: "standard",
      primary_market: "DE",
      comparison_markets: ["FR", "IT", "ES"],
      locale_by_market: {
        DE: "de-DE",
        FR: "fr-FR",
        IT: "it-IT",
        ES: "es-ES",
      },
    });
    expectClean(problems);
  });

  test("报告列表与阅读页读取真实报告", async ({ page }) => {
    const seed = readSeedManifest();
    const problems = watchPage(page);
    await page.goto("/reports");
    await expect(page.getByText("E2E 母婴洞察报告")).toBeVisible();
    await page.goto(`/reports/${seed.report_id}`);
    await expect(page.getByText("E2E 母婴洞察报告")).toBeVisible();
    expectClean(problems);
  });

  test("资产、连接器、设置显示真实数据", async ({ page }) => {
    const seed = readSeedManifest();
    const problems = watchPage(page);
    await page.goto("/assets");
    await expect(page.getByTestId("assets-page")).toBeVisible();
    await expect(page.getByText("E2E Dataset")).toBeVisible();
    await expect(
      page.getByTestId("asset-row").filter({ hasText: "E2E Dataset" }).getByTestId("asset-quality"),
    ).toHaveText("有缺口");

    await page.goto("/connectors");
    await expect(page.getByText("连接器与凭据")).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByTestId("settings-page")).toBeVisible();
    await expect(page.getByText("E2E Console Workspace")).toBeVisible();
    expect(seed.dataset_id.length).toBeGreaterThan(0);
    expectClean(problems);
  });
});
```

- [ ] **Step 3: 写负路径测试**

`apps/scraper-console/e2e/negative-paths.spec.ts`：

```typescript
import { expect, test } from "@playwright/test";
import { readSeedManifest } from "./support/seed-manifest";

const PROTECTED = [
  "/workbench",
  "/workbench/00000000-0000-0000-0000-000000000000",
  "/reports",
  "/reports/00000000-0000-0000-0000-000000000000",
  "/connectors",
  "/settings",
] as const;

test.describe("负路径", () => {
  for (const route of PROTECTED) {
    test(`匿名访问 ${route} 跳到登录`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login\?next=/);
    });
  }

  test("公开分享保持 404", async ({ page }) => {
    const response = await page.goto("/reports/public/00000000-0000-0000-0000-000000000000");
    expect(response?.status()).toBe(404);
  });

  test("错误密码停在登录页并显示错误", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("邮箱").fill("e2e-console@example.com");
    await page.getByLabel("密码").fill("wrong-password-123");
    await page.getByRole("button", { name: "登录" }).click();
    await expect(page.getByRole("alert")).toContainText("邮箱或密码不正确");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("@authenticated 负路径", () => {
  test("跨工作区报告返回 404 状态", async ({ page }) => {
    const seed = readSeedManifest();
    await page.goto(`/reports/${seed.other_report_id}`);
    await expect(page.getByText(/报告不存在|报告未找到|无权访问/)).toBeVisible();
  });

  test("工作台接口 500 时显示错误态而不是假数据", async ({ page }) => {
    await page.route("**/api/workbench/tasks**", route =>
      route.fulfill({ status: 500, body: "boom" }),
    );
    await page.goto("/workbench");
    await expect(page.getByRole("alert")).toContainText("加载失败");
    await expect(page.getByTestId("workbench-task-row")).toHaveCount(0);
  });

  test("未认证 API 返回 401", async ({ request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
    const response = await request.get(
      `${apiBase}/api/workbench/tasks?project_id=00000000-0000-0000-0000-000000000000`,
    );
    expect(response.status()).toBe(401);
  });
});
```

- [ ] **Step 4: 更新 routes.spec.ts**

把本地 `watchPage` 与 `isAllowedConsoleNoise` 删除，改为：

```typescript
import { expectClean, watchPage } from "./support/page-problems";
```

并把 `assertRoute` 末尾的断言替换为：

```typescript
  expectClean(problems);
```

更新 `PAGE_ROUTES`，加入合同路由：

```typescript
const PAGE_ROUTES = [
  "/",
  "/capabilities",
  "/docs",
  "/workbench",
  "/reports",
  "/connectors",
  "/settings",
  "/runs",
  "/assets",
  "/assets/records",
] as const;
```

更新 `REDIRECT_ROUTES` 的三条能力目录目标，并加入两条新重定向：

```typescript
const REDIRECT_ROUTES = [
  { source: "/platforms", destination: "/capabilities" },
  { source: "/skills", destination: "/capabilities" },
  { source: "/skills/tiktok", destination: "/capabilities/tiktok" },
  { source: "/datasets", destination: "/assets" },
  { source: "/raw-records", destination: "/assets/records" },
  { source: "/collector-docs", destination: "/docs" },
  { source: "/dashboard", destination: "/workbench" },
  { source: "/settings/credentials", destination: "/connectors" },
  {
    source: "/collect/00000000-0000-0000-0000-000000000000",
    destination: "/runs/00000000-0000-0000-0000-000000000000",
  },
] as const;
```

- [ ] **Step 5: 运行 Playwright**

Run:
```bash
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash scripts/seed-console-e2e.sh
pnpm -C apps/scraper-console exec playwright test
```
Expected: setup、public、authenticated 全部通过；负路径中跨工作区报告显示 404 状态；分享页 404。

- [ ] **Step 6: 提交**

```bash
git add apps/scraper-console/e2e
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(console): add positive and negative golden paths"
```

---

### Task 11: 截图与截图清单

**Files:**
- Create: `apps/scraper-console/e2e/screenshots.spec.ts`

**Interfaces:**
- Consumes: 认证 storage state、种子 manifest。
- Produces: `tmp/console-screenshots/*.png` 与 `tmp/console-screenshots/manifest.json`。

- [ ] **Step 1: 写截图测试**

`apps/scraper-console/e2e/screenshots.spec.ts`：

```typescript
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { readSeedManifest } from "./support/seed-manifest";
import { expectClean, watchPage } from "./support/page-problems";

const OUTPUT = path.resolve(process.cwd(), "../../tmp/console-screenshots");
const MIN_BYTES = 20_000;

test.describe("@authenticated 截图", () => {
  test("六个页族截图并写清单", async ({ page }) => {
    const seed = readSeedManifest();
    mkdirSync(OUTPUT, { recursive: true });
    const routes = [
      ["workbench", "/workbench", "workbench-page"],
      ["workbench-task", `/workbench/${seed.task_id}`, "workbench-task-detail"],
      ["runs", "/runs", "runs-page"],
      ["reports", "/reports", "reports-page"],
      ["report", `/reports/${seed.report_id}`, "report-detail"],
      ["assets", "/assets", "assets-page"],
      ["assets-records", "/assets/records", "assets-records-page"],
      ["connectors", "/connectors", "connectors-page"],
      ["settings", "/settings", "settings-page"],
    ] as const;
    const manifest: Array<Record<string, unknown>> = [];

    for (const [name, route, anchor] of routes) {
      const problems = watchPage(page);
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.getByTestId(anchor).waitFor({ state: "visible", timeout: 15_000 });
      await page.waitForTimeout(500);
      const text = (await page.locator("body").innerText()).trim();
      expect(text.length, `${route} 不得是空页`).toBeGreaterThan(50);
      const file = path.join(OUTPUT, `${name}.png`);
      await page.screenshot({ path: file, fullPage: false });
      const size = statSync(file).size;
      expect(size, `${route} 截图过小`).toBeGreaterThanOrEqual(MIN_BYTES);
      manifest.push({
        route,
        file: path.basename(file),
        bytes: size,
        sha256: createHash("sha256").update(readFileSync(file)).digest("hex"),
        taken_at: new Date().toISOString(),
      });
      expectClean(problems);
    }

    writeFileSync(
      path.join(OUTPUT, "manifest.json"),
      JSON.stringify({ generated_at: new Date().toISOString(), screenshots: manifest }, null, 2),
      "utf8",
    );
    expect(manifest).toHaveLength(9);
  });
});
```

- [ ] **Step 2: 运行截图测试**

Run:
```bash
pnpm -C apps/scraper-console exec playwright test --project=authenticated e2e/screenshots.spec.ts
```
Expected: `1 passed`；`tmp/console-screenshots/` 下有 9 张 PNG 与 `manifest.json`。

- [ ] **Step 3: 人工复核截图**

逐张打开 9 张截图，确认：

- 页面有 `AppShell` 侧栏与主区域；
- 侧栏一级导航只有 4 项；
- 没有空白主区域、没有 `undefined`、没有 `NaN`、没有英文占位；
- 连接器页不显示 Cookie 值；
- 设置页不显示假审计数据。

把复核结论写入 `docs/ops/console-acceptance.md` 的“截图复核”表。

- [ ] **Step 4: 提交**

```bash
git add apps/scraper-console/e2e/screenshots.spec.ts
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(console): capture acceptance screenshots and manifest"
```

---

### Task 12: CI 五个阻塞门禁

**Files:**
- Create: `scripts/verify-console-ci-gates.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `apps/scraper-console/package.json`

**Interfaces:**
- Consumes: `.github/workflows/ci.yml`、`apps/scraper-console/package.json`。
- Produces: `console-quality` 作业、`console-acceptance` 作业、`typecheck` 脚本、`console_ci_gates_ok`。

- [ ] **Step 1: 写失败检查脚本**

`scripts/verify-console-ci-gates.py`：

```python
from __future__ import annotations

import argparse
import re
from pathlib import Path


def job_block(text: str, name: str) -> str | None:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.fullmatch(rf"  {re.escape(name)}:\s*", line):
            start = index
            break
    if start is None:
        return None
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            break
        block.append(line)
    return "\n".join(block)


def check(workflow: str) -> list[str]:
    issues: list[str] = []
    quality = job_block(workflow, "console-quality")
    if quality is None:
        issues.append("console_ci_gate_missing:console-quality")
    else:
        for token in (
            "pnpm -C apps/scraper-console test",
            "pnpm -C apps/scraper-console typecheck",
            "pnpm -C apps/scraper-console lint",
            "pnpm -C apps/scraper-console build",
            'node-version: "26"',
        ):
            if token not in quality:
                issues.append(f"console_ci_gate_missing:{token}")

    acceptance = job_block(workflow, "console-acceptance")
    if acceptance is None:
        issues.append("console_ci_gate_missing:console-acceptance")
    else:
        if "continue-on-error: true" in acceptance:
            issues.append("console_ci_gate_non_blocking")
        for token in (
            "pnpm exec playwright test",
            "scripts/seed-console-e2e.sh",
            "scripts/p0_acceptance.sh",
            "Upload Playwright report",
            'DEMO_MODE: "false"',
            'WORKBENCH_TASKS_ENABLED: "true"',
            "WORKBENCH_TAXONOMY_PATH: ${{ github.workspace }}/configs/taxonomy/maternal_v1.json",
            'node-version: "26"',
        ):
            if token not in acceptance:
                issues.append(f"console_ci_gate_missing:{token}")
        service_password = re.search(
            r"^\s+POSTGRES_PASSWORD:\s*(.+?)\s*$", acceptance, re.MULTILINE
        )
        database_password = re.search(
            r"^\s+DATABASE_URL:\s*\"?postgresql\+asyncpg://postgres:(.+?)@",
            acceptance,
            re.MULTILINE,
        )
        if service_password is None or database_password is None:
            issues.append("console_ci_database_password_mismatch")
        elif service_password.group(1).strip() != database_password.group(1).strip():
            issues.append("console_ci_database_password_mismatch")
    if job_block(workflow, "console-routes-e2e") is not None:
        issues.append("console_ci_legacy_job_still_present")
    for job in ("console-quality", "console-acceptance"):
        block = job_block(workflow, job)
        if block is not None and "continue-on-error" in block:
            issues.append(f"console_ci_gate_non_blocking:{job}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", default=".github/workflows/ci.yml")
    args = parser.parse_args()
    issues = check(Path(args.workflow).read_text(encoding="utf-8"))
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("console_ci_gates_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行检查确认失败**

Run: `python3 scripts/verify-console-ci-gates.py`
Expected: FAIL，输出 `console_ci_gate_missing:console-quality`。

- [ ] **Step 3: 增加 `typecheck` 脚本**

在 `apps/scraper-console/package.json` 的 `scripts` 中加入：

```json
    "typecheck": "next typegen && tsc --noEmit",
```

- [ ] **Step 4: 替换 CI 的 `console-routes-e2e` 作业**

先在 GitHub 仓库设置三个 Actions secrets：`CONSOLE_E2E_POSTGRES_PASSWORD`（Postgres service 密码）、`CONSOLE_E2E_JWT_SECRET`（至少 32 位）与 `CONSOLE_E2E_PASSWORD`（至少 8 位）。E2E 种子、API 启动和 Playwright 登录共用同一个登录密码；数据库密码只由 `CONSOLE_E2E_POSTGRES_PASSWORD` 提供，service 与 `DATABASE_URL` 必须引用同一个 secret，禁止一处写死、另一处用占位符。

删除 `.github/workflows/ci.yml` 中整个 `console-routes-e2e` 作业（含 `continue-on-error: true`），加入：

```yaml
  console-quality:
    name: Console Quality Gate (blocking)
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Check file integrity
        run: python3 scripts/check_file_integrity.py

      - name: Verify console CI gates
        run: python3 scripts/verify-console-ci-gates.py

      - name: Set up pnpm
        uses: pnpm/action-setup@v6
        with:
          version: 9.15.4
          run_install: false

      - name: Set up Node.js
        uses: actions/setup-node@v6
        with:
          node-version: "26"
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml

      - name: Install workspace dependencies
        run: pnpm install --frozen-lockfile

      - name: Console unit tests
        run: pnpm -C apps/scraper-console test

      - name: Console typecheck
        run: pnpm -C apps/scraper-console typecheck

      - name: Console lint
        run: pnpm -C apps/scraper-console lint

      - name: Console build
        env:
          NEXT_PUBLIC_API_URL: "https://scrapy.luteos.com"
        run: pnpm -C apps/scraper-console build

  console-acceptance:
    name: Console Acceptance E2E (blocking)
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: ${{ secrets.CONSOLE_E2E_POSTGRES_PASSWORD }}
          POSTGRES_DB: dih_console_e2e
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres -d dih_console_e2e"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: "postgresql+asyncpg://postgres:${{ secrets.CONSOLE_E2E_POSTGRES_PASSWORD }}@127.0.0.1:5432/dih_console_e2e"
      DEMO_MODE: "false"
      JWT_SECRET: "${{ secrets.CONSOLE_E2E_JWT_SECRET }}"
      AUTH_COOKIE_SECURE: "false"
      CORS_ORIGINS: "http://127.0.0.1:3001"
      SCHEDULER_ENABLED: "false"
      RUN_WORKER_ENABLED: "false"
      WORKBENCH_TASKS_ENABLED: "true"
      WORKBENCH_TAXONOMY_PATH: ${{ github.workspace }}/configs/taxonomy/maternal_v1.json
      CONSOLE_E2E_EMAIL: "e2e-console@example.com"
      CONSOLE_E2E_PASSWORD: ${{ secrets.CONSOLE_E2E_PASSWORD }}
      NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000"
      PLAYWRIGHT_API_URL: "http://127.0.0.1:8000"

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Check file integrity
        run: python3 scripts/check_file_integrity.py

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Set up uv
        uses: astral-sh/setup-uv@v8.2.0
        with:
          enable-cache: true
          cache-dependency-glob: apps/api/uv.lock

      - name: Install API dependencies
        working-directory: apps/api
        run: uv sync --locked --dev

      - name: Apply existing migrations
        working-directory: apps/api
        run: uv run alembic upgrade head

      - name: Verify seed audit chain on PostgreSQL
        working-directory: apps/api
        env:
          CONSOLE_E2E_DATABASE_TEST: "true"
        run: uv run pytest tests/integration/test_e2e_seed_db.py -q

      - name: Seed console E2E fixtures
        run: bash scripts/seed-console-e2e.sh

      - name: Start API
        working-directory: apps/api
        run: |
          nohup uv run uvicorn data_intelligence_hub.main:app \
            --host 127.0.0.1 --port 8000 > /tmp/console-e2e-api.log 2>&1 &
          for attempt in $(seq 1 60); do
            if curl -fsS http://127.0.0.1:8000/api/health > /dev/null; then
              exit 0
            fi
            sleep 2
          done
          cat /tmp/console-e2e-api.log
          exit 1

      - name: Set up pnpm
        uses: pnpm/action-setup@v6
        with:
          version: 9.15.4
          run_install: false

      - name: Set up Node.js
        uses: actions/setup-node@v6
        with:
          node-version: "26"
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml

      - name: Install workspace dependencies
        run: pnpm install --frozen-lockfile

      - name: Install Playwright Chromium
        run: pnpm -C apps/scraper-console exec playwright install --with-deps chromium

      - name: Build console
        run: pnpm -C apps/scraper-console build

      - name: Start console
        working-directory: apps/scraper-console
        run: |
          nohup pnpm exec next start --port 3001 > /tmp/console-e2e-web.log 2>&1 &
          for attempt in $(seq 1 60); do
            if curl -fsS http://127.0.0.1:3001/login > /dev/null; then
              exit 0
            fi
            sleep 2
          done
          cat /tmp/console-e2e-web.log
          exit 1

      - name: Run Playwright acceptance
        working-directory: apps/scraper-console
        env:
          PLAYWRIGHT_BASE_URL: "http://127.0.0.1:3001"
          PLAYWRIGHT_STORAGE_STATE: "../../tmp/playwright-console-auth.json"
        run: pnpm exec playwright test

      - name: Run p0 acceptance
        env:
          P0_BASE_URL: "http://127.0.0.1:3001"
          P0_API_BASE_URL: "http://127.0.0.1:8000"
          P0_EMAIL: "e2e-console@example.com"
          P0_PASSWORD: ${{ secrets.CONSOLE_E2E_PASSWORD }}
        run: bash scripts/p0_acceptance.sh

      - name: Cleanup E2E fixtures
        if: always()
        working-directory: apps/api
        run: uv run python -m data_intelligence_hub.maintenance.e2e_cleanup --execute --older-than-hours 0

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: console-playwright-report
          path: |
            tmp/playwright-console-report/
            tmp/playwright-console-results/
            tmp/console-screenshots/
          if-no-files-found: ignore
          retention-days: 14
```

- [ ] **Step 5: 运行检查确认通过**

Run: `python3 scripts/verify-console-ci-gates.py`
Expected: `console_ci_gates_ok`。

- [ ] **Step 6: 提交**

```bash
git add .github/workflows/ci.yml \
  scripts/verify-console-ci-gates.py \
  apps/scraper-console/package.json
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ci(console): make unit typecheck lint build and e2e blocking"
```

---

### Task 13: `p0_acceptance.sh`

**Files:**
- Create: `scripts/p0_acceptance.sh`

**Interfaces:**
- Consumes: `P0_BASE_URL`、`P0_API_BASE_URL`、`P0_EMAIL`、`P0_PASSWORD`。
- Produces: PASS/FAIL 行、退出码 0/1、可选 JSON 摘要。

- [ ] **Step 1: 先跑一次失败验收**

Run:
```bash
P0_BASE_URL='http://127.0.0.1:3999' P0_API_BASE_URL='http://127.0.0.1:3999' \
P0_EMAIL='e2e-console@example.com' P0_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" \
bash scripts/p0_acceptance.sh
```
Expected: 脚本不存在，退出 127。这一步确认验收命令是阻塞的。

- [ ] **Step 2: 写脚本**

`scripts/p0_acceptance.sh`：

```bash
#!/usr/bin/env bash
set -uo pipefail

BASE_URL="${P0_BASE_URL:-http://127.0.0.1:3001}"
API_BASE_URL="${P0_API_BASE_URL:-http://127.0.0.1:8000}"
EMAIL="${P0_EMAIL:-}"
PASSWORD="${P0_PASSWORD:-}"
COOKIE_JAR="$(mktemp)"
FAIL=0
JSON_OUT="${P0_JSON_OUT:-}"

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
skip() { printf 'SKIP  %s\n' "$1"; }

cleanup() { rm -f "$COOKIE_JAR"; }
trap cleanup EXIT

status_of() {
  local method="$1" url="$2"
  curl -sS -o /dev/null -w '%{http_code}' -X "$method" "$url" -b "$COOKIE_JAR" -c "$COOKIE_JAR"
}

expect_status() {
  local label="$1" method="$2" url="$3" expected="$4"
  local actual
  actual="$(status_of "$method" "$url")"
  if [[ "$actual" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label expected $expected got $actual"
  fi
}

expect_redirect_to_login() {
  local label="$1" url="$2"
  local headers status location
  headers="$(curl -sS -o /dev/null -D - "$url" -b "$COOKIE_JAR" -c "$COOKIE_JAR")"
  status="$(printf '%s' "$headers" | awk 'toupper($1) ~ /^HTTP/ {print $2}' | tail -1)"
  location="$(printf '%s' "$headers" | awk 'tolower($1) == "location:" {print $2}' | tr -d '\r' | tail -1)"
  if [[ "$status" =~ ^30[1-8]$ && "$location" == *"/login"* ]]; then
    pass "$label"
  else
    fail "$label expected redirect to /login got $status $location"
  fi
}

expect_body() {
  local label="$1" url="$2" needle="$3"
  local body
  body="$(curl -sS "$url" -b "$COOKIE_JAR" -c "$COOKIE_JAR")"
  if printf '%s' "$body" | grep -q "$needle"; then
    pass "$label"
  else
    fail "$label missing text: $needle"
  fi
}

expect_json() {
  local label="$1" url="$2" expression="$3"
  local body
  body="$(curl -sS "$url" -b "$COOKIE_JAR" -c "$COOKIE_JAR")"
  if printf '%s' "$body" | python3 -c "import json,sys; data=json.load(sys.stdin); assert $expression" 2>/dev/null; then
    pass "$label"
  else
    fail "$label JSON assertion failed: $expression"
  fi
}

echo "== Health =="
expect_status "health 200" GET "$API_BASE_URL/api/health" 200
expect_json "health current" "$API_BASE_URL/api/health" "data['status'] == 'ok' and data.get('schema') == 'current'"

echo "== Public =="
expect_status "home 200" GET "$BASE_URL/" 200
expect_status "capabilities 200" GET "$BASE_URL/capabilities" 200
expect_status "docs 200" GET "$BASE_URL/docs" 200
expect_status "public share disabled" GET "$BASE_URL/reports/public/00000000-0000-0000-0000-000000000000" 404

echo "== Anonymous =="
for route in /workbench /reports /connectors /settings; do
  expect_redirect_to_login "anonymous $route" "$BASE_URL$route"
done
expect_status "anonymous workbench API 401" GET "$API_BASE_URL/api/workbench/tasks?project_id=00000000-0000-0000-0000-000000000000" 401

echo "== Login =="
if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  fail "P0_EMAIL and P0_PASSWORD are required"
else
  payload="$(python3 -c 'import json,sys; print(json.dumps({"email": sys.argv[1], "password": sys.argv[2]}))' "$EMAIL" "$PASSWORD")"
  code="$(curl -sS -o /tmp/p0-login.json -w '%{http_code}' -c "$COOKIE_JAR" \
    -H 'Content-Type: application/json' -d "$payload" "$API_BASE_URL/api/auth/login")"
  if [[ "$code" == "200" ]]; then pass "login 200"; else fail "login expected 200 got $code"; fi
fi

echo "== Authenticated pages =="
expect_status "workbench 200" GET "$BASE_URL/workbench" 200
expect_body "workbench body" "$BASE_URL/workbench" "工作台"
expect_status "reports 200" GET "$BASE_URL/reports" 200
expect_body "reports body" "$BASE_URL/reports" "报告"
expect_status "connectors 200" GET "$BASE_URL/connectors" 200
expect_body "connectors body" "$BASE_URL/connectors" "连接器"
expect_status "settings 200" GET "$BASE_URL/settings" 200
expect_body "settings body" "$BASE_URL/settings" "设置"

echo "== Authenticated APIs =="
PROJECTS="$(curl -sS "$API_BASE_URL/api/projects" -b "$COOKIE_JAR" -c "$COOKIE_JAR")"
PROJECT_ID="$(printf '%s' "$PROJECTS" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert isinstance(data, list) and data, "project_required"
print(data[0]["id"])
' 2>/dev/null || true)"
if [[ -n "$PROJECT_ID" ]]; then
  pass "project available"
  expect_status "workbench tasks API 200" GET "$API_BASE_URL/api/workbench/tasks?project_id=$PROJECT_ID" 200
else
  fail "project_required"
fi
expect_status "reports API 200" GET "$API_BASE_URL/api/reports" 200
expect_status "datasets API 200" GET "$API_BASE_URL/api/automation/product-datasets" 200
expect_status "credentials API 200" GET "$API_BASE_URL/api/settings/platform-credentials" 200
expect_status "random report 404" GET "$API_BASE_URL/api/reports/00000000-0000-0000-0000-000000000000" 404
expect_status "random task 404" GET "$API_BASE_URL/api/workbench/tasks/00000000-0000-0000-0000-000000000000" 404

echo "== Result =="
if [[ -n "$JSON_OUT" ]]; then
  python3 -c "import json,sys; print(json.dumps({'passed': sys.argv[1] == '0', 'base_url': sys.argv[2]}, ensure_ascii=False))" "$FAIL" "$BASE_URL" > "$JSON_OUT"
fi
if [[ "$FAIL" == "0" ]]; then
  echo "PG0 ACCEPTANCE PASSED"
  exit 0
fi
echo "PG0 ACCEPTANCE FAILED"
exit 1
```

- [ ] **Step 3: 运行脚本**

Run:
```bash
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash scripts/seed-console-e2e.sh
P0_BASE_URL='http://127.0.0.1:3001' P0_API_BASE_URL='http://127.0.0.1:8000' \
P0_EMAIL='e2e-console@example.com' P0_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" \
bash scripts/p0_acceptance.sh
```
Expected: 全部 PASS，最后输出 `PG0 ACCEPTANCE PASSED`。

- [ ] **Step 4: 提交**

```bash
git add scripts/p0_acceptance.sh
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(console): add read-only p0 acceptance script"
```

---

### Task 14: 生产 A canary 与生产 B preflight

**Files:**
- Create: `scripts/canary-console-production.sh`
- Create: `scripts/preflight-production-a.sh`
- Create: `scripts/preflight-production-b.sh`
- Create: `scripts/verify-pg0-switches.sh`

**Interfaces:**
- Consumes: `P0_EMAIL`、`P0_PASSWORD`、SSH key `DDDD.pem`；容器内 `Settings`；`SCRAPY_EXPECTED_SCHEMA`（PG0 发布批次提供的最终 head `202610220068`）。
- Produces: 只读 canary/preflight 退出码；A 的 `schema revision 202610220068` 证据；四个 PG0 开关的只读证据行。
- 前置：PG0 发布批次已完成 A/B 备份、迁移、compose/env 变更、部署、重启与四个开关翻转。C14 只在发布后读取证据；不执行上述任何动作。MFA 仍延期，不在 canary 里要求 MFA。

- [ ] **Step 0b: 写生产 A 只读 schema preflight 包装**

`scripts/preflight-production.sh` 已支持 `SCRAPY_EXPECTED_SCHEMA`，默认值属于 PG0 发布批次，C14 不修改该脚本、不把默认值改成 C6 的 `202610220062`。新增参数化包装，只允许最终 head `202610220068`，缺少环境变量时 fail-closed：

`scripts/preflight-production-a.sh`：

```bash
#!/usr/bin/env bash
# Read-only wrapper for Production A preflight.
# C14 never edits scripts/preflight-production.sh and never passes an intermediate head.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED="${SCRAPY_EXPECTED_SCHEMA:-}"
FINAL_HEAD="202610220068"

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "SCRAPY_EXPECTED_SCHEMA=${EXPECTED:-<required>}"
  echo "delegate=scripts/preflight-production.sh"
  echo "mode=read-only"
  exit 0
fi

if [[ -z "$EXPECTED" ]]; then
  echo "SCRAPY_EXPECTED_SCHEMA is required; PG0 release batch supplies $FINAL_HEAD" >&2
  exit 2
fi
if [[ "$EXPECTED" != "$FINAL_HEAD" ]]; then
  echo "unexpected schema head: $EXPECTED (expected $FINAL_HEAD)" >&2
  exit 2
fi

exec bash "$ROOT_DIR/scripts/preflight-production.sh"
```

包装脚本只读；它继承 `SCRAPY_EXPECTED_SCHEMA` 并委托 `scripts/preflight-production.sh` 做 SSH/HTTP 只读检查。C14 不写 `.env.production`、不执行迁移、不重启容器。PG0 发布批次负责在发布证据里提供 `SCRAPY_EXPECTED_SCHEMA=202610220068`。

- [ ] **Step 1: 写 A canary**

`scripts/canary-console-production.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${CANARY_BASE_URL:-https://scrapy.luteos.com}"

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "CANARY_BASE_URL=$BASE_URL"
  echo "P0_EMAIL=${P0_EMAIL:-<required>}"
  echo "P0_PASSWORD=<redacted>"
  exit 0
fi

if [[ -z "${P0_EMAIL:-}" || -z "${P0_PASSWORD:-}" ]]; then
  echo "P0_EMAIL and P0_PASSWORD are required" >&2
  exit 2
fi

curl -fsS "$BASE_URL/api/health" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert data["status"] == "ok", data
assert data.get("schema") == "current", data
assert data["schema_revision"] == data["schema_head"], data
print("canary_health_ok")
'

P0_BASE_URL="$BASE_URL" P0_API_BASE_URL="$BASE_URL" \
P0_EMAIL="$P0_EMAIL" P0_PASSWORD="$P0_PASSWORD" \
bash "$ROOT_DIR/scripts/p0_acceptance.sh"
```

- [ ] **Step 2: 写 B preflight**

`scripts/preflight-production-b.sh`：

```bash
#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SCRAPY_B_HOST:-ubuntu@101.34.52.232}"
KEY="${SCRAPY_B_KEY:-$ROOT_DIR/DDDD.pem}"
APP_DIR="${SCRAPY_B_APP_DIR:-/opt/data-achieve-scrapy/app}"
PUBLIC_URL="${SCRAPY_B_PUBLIC_URL:-https://scrapy.lute-tlz-dddd.top}"
EXPECTED_BRANCH="${SCRAPY_B_BRANCH:-deploy/tiktok-cdo-codex}"
FAIL=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "ssh -i $KEY $HOST"
  echo "app_dir=$APP_DIR branch=$EXPECTED_BRANCH public=$PUBLIC_URL"
  exit 0
fi

ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "
cd '$APP_DIR' || exit 1
echo -n 'HEAD '
git rev-parse --short HEAD
echo -n 'BRANCH '
git rev-parse --abbrev-ref HEAD
echo -n 'STATUS '
if [ -z \"\$(git status --porcelain)\" ]; then echo clean; else echo dirty; fi
echo -n 'API '
docker ps --filter name=data_achieve_scrapy_api --format '{{.Status}}'
echo -n 'CONSOLE '
docker ps --filter name=data_achieve_scrapy_console --format '{{.Status}}'
echo -n 'EDGE '
docker inspect data_achieve_scrapy_edge --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'
echo -n 'HEALTH '
docker exec data_achieve_scrapy_api python -c 'import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:8000/api/health\", timeout=3).read().decode())'
" > /tmp/scrapy_b_preflight.txt 2>&1

grep -q '^HEAD ' /tmp/scrapy_b_preflight.txt && pass "B reachable" || fail "B unreachable"
grep -q "^BRANCH $EXPECTED_BRANCH$" /tmp/scrapy_b_preflight.txt \
  && pass "B branch $EXPECTED_BRANCH" \
  || fail "B branch mismatch (see /tmp/scrapy_b_preflight.txt)"
grep -q '^STATUS clean$' /tmp/scrapy_b_preflight.txt && pass "B worktree clean" || fail "B worktree dirty"
grep -q '^API Up .*healthy' /tmp/scrapy_b_preflight.txt && pass "B API healthy" || fail "B API not healthy"
grep -q '^CONSOLE Up ' /tmp/scrapy_b_preflight.txt && pass "B console up" || fail "B console not up"
grep -q '^EDGE .*172\.' /tmp/scrapy_b_preflight.txt && pass "B edge fixed IP" || warn "B edge IP not observed"

HEALTH="$(curl -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/api/health" || echo 000)"
[[ "$HEALTH" == "200" ]] && pass "B public health 200" || fail "B public health $HEALTH"

LOGIN="$(curl -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/login" || echo 000)"
[[ "$LOGIN" == "200" ]] && pass "B login 200" || fail "B login $LOGIN"

WORKBENCH="$(curl -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/workbench" || echo 000)"
[[ "$WORKBENCH" =~ ^30[1-8]$ ]] && pass "B workbench redirects" || fail "B workbench $WORKBENCH"

echo "== Result =="
if [[ "$FAIL" == "0" ]]; then
  echo "B PREFLIGHT PASSED"
  exit 0
fi
echo "B PREFLIGHT FAILED"
exit 1
```

- [ ] **Step 2b: 写四个 PG0 开关的只读证据脚本**

`scripts/verify-pg0-switches.sh` 只读取容器内 `Settings`，不写 `.env.production`、不重启、不执行迁移、不翻转开关。C14 只断言 PG0 发布批次已经打开的四个开关；开关的打开动作属于 PG0 发布批次。

```bash
#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${PG0_SWITCH_HOST:-ubuntu@43.163.92.244}"
KEY="${PG0_SWITCH_KEY:-$ROOT_DIR/zhoujian_pachong.pem}"
CONTAINER="${PG0_API_CONTAINER:-data_achieve_scrapy_api}"

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "host=$HOST container=$CONTAINER key=$KEY"
  echo "mode=read-only"
  exit 0
fi

REMOTE_PY="$(cat <<'PY'
import json

from data_intelligence_hub.core.config import get_settings

settings = get_settings()
print(json.dumps({
    "budget_enforcement_enabled": bool(settings.budget_enforcement_enabled),
    "strict_price_enabled": bool(settings.strict_price_enabled),
    "run_execution_convergence_enabled": bool(settings.run_execution_convergence_enabled),
    "retention_cleanup_enabled": bool(settings.retention_cleanup_enabled),
}, sort_keys=True))
PY
)"

OUTPUT="$(printf '%s' "$REMOTE_PY" | ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "$HOST" \
  "docker exec -i $CONTAINER python -" 2>&1)"
STATUS=$?
if [[ "$STATUS" -ne 0 || -z "$OUTPUT" ]]; then
  echo "pg0_switch_read_failed:$STATUS" >&2
  printf '%s\n' "$OUTPUT" >&2
  exit 1
fi

printf '%s' "$OUTPUT" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
required = (
    "budget_enforcement_enabled",
    "strict_price_enabled",
    "run_execution_convergence_enabled",
    "retention_cleanup_enabled",
)
missing = [key for key in required if key not in data]
if missing:
    print("pg0_switch_missing:" + ",".join(missing))
    raise SystemExit(1)
failed = [key for key in required if data[key] is not True]
for key in required:
    print(f"{key}={str(data[key]).lower()}")
if failed:
    print("pg0_switch_not_enabled:" + ",".join(failed))
    raise SystemExit(1)
print("pg0_switches_ok")
'
```

开关为 `false`、缺失或容器不可读时脚本退出 1。C14 不得执行 `docker compose up`、`docker restart`、`alembic upgrade`、修改 compose/env 或 seed 生产来“修复”证据；失败时返回 PG0 发布批次。

- [ ] **Step 3: 运行只读 dry-run**

Run:
```bash
bash scripts/canary-console-production.sh --dry-run
bash scripts/preflight-production-a.sh --dry-run
bash scripts/preflight-production-b.sh --dry-run
bash scripts/verify-pg0-switches.sh --dry-run
```
Expected: 只打印目标和路径，不发起网络或 SSH 请求。

- [ ] **Step 4: 本地跑 A canary（可选）**

只有本机可访问生产 A 且持有验收账号时运行：

```bash
P0_EMAIL='<验收账号>' P0_PASSWORD='<验收密码>' bash scripts/canary-console-production.sh
```
Expected: `canary_health_ok`，随后 p0 验收全部 PASS。没有账号时记录“未执行”，不得写成通过。

- [ ] **Step 4b: 跑 A schema preflight（只读）**

`SCRAPY_EXPECTED_SCHEMA` 由 PG0 发布批次提供，值为最终 head `202610220068`。C14 不硬编码 C6 的 `202610220062`，也不修改 `scripts/preflight-production.sh`。

Run:
```bash
: "${SCRAPY_EXPECTED_SCHEMA:?PG0 release batch must export 202610220068}"
bash scripts/preflight-production-a.sh
```
Expected: `PASS  schema revision 202610220068`。任一检查失败时记录 `BLOCKED` 并返回 PG0 发布批次；C14 不部署、不迁移、不重启。

- [ ] **Step 5: 跑 B preflight（只读）**

Run:
```bash
bash scripts/preflight-production-b.sh
```
Expected: 输出 PASS/FAIL 行。B 当前落后于主线时，`B branch` 或 schema 检查应失败；记录失败项，不在 C14 部署 B。

- [ ] **Step 5b: 记录四个 PG0 开关的只读证据**

Run:
```bash
bash scripts/verify-pg0-switches.sh
PG0_SWITCH_HOST='ubuntu@101.34.52.232' PG0_SWITCH_KEY="$PWD/DDDD.pem" \
  bash scripts/verify-pg0-switches.sh
```

Expected: 两套环境都输出四行 `key=true` 与 `pg0_switches_ok`。四项分别是 `budget_enforcement_enabled`、`strict_price_enabled`、`run_execution_convergence_enabled`、`retention_cleanup_enabled`。任一项为 `false`、缺失或 SSH/容器不可读时，记录 `BLOCKED` 并返回 PG0 发布批次；C14 不翻转开关、不改 env、不重启。

- [ ] **Step 6: 提交**

```bash
git add scripts/canary-console-production.sh scripts/preflight-production-a.sh \
  scripts/preflight-production-b.sh scripts/verify-pg0-switches.sh
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(console): add production A canary, A/B preflight, and pg0 switch evidence"
```

---

### Task 15: 验收文档与最终门禁

**Files:**
- Create: `docs/ops/console-acceptance.md`
- Modify: `apps/scraper-console/README.md`

**Interfaces:**
- Consumes: Task 1–14 的脚本与测试。
- Produces: 运行手册、证据表、最终验收记录。

- [ ] **Step 1: 写运行手册**

`docs/ops/console-acceptance.md`：

````markdown
# 控制台 C14 验收手册

## 范围

11 条合同路由（10 启用、1 禁用）、4 条一级导航、六个页族真实 API、CI 五个阻塞门禁、正负黄金路径、截图、p0 验收、生产 A canary、生产 A schema preflight、生产 B preflight 与四个 PG0 开关的只读证据。

## 本地验收

```bash
export DEMO_MODE=false
export WORKBENCH_TASKS_ENABLED=true
export WORKBENCH_TAXONOMY_PATH="$(git rev-parse --show-toplevel)/configs/taxonomy/maternal_v1.json"
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console typecheck
pnpm -C apps/scraper-console lint
pnpm -C apps/scraper-console build
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash scripts/seed-console-e2e.sh
pnpm -C apps/scraper-console exec playwright test
P0_BASE_URL='http://127.0.0.1:3001' P0_API_BASE_URL='http://127.0.0.1:8000' \
P0_EMAIL='e2e-console@example.com' P0_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" \
bash scripts/p0_acceptance.sh
python3 scripts/verify-console-ci-gates.py
```

`WORKBENCH_TASKS_ENABLED=true` 与 `WORKBENCH_TAXONOMY_PATH` 只用于本地/CI E2E。生产 A/B 的开关与 taxonomy 挂载由 PG0 发布批次负责；C14 不写生产 env、不重启容器，只读取发布后的健康与开关证据。

## 截图复核

| 页面 | 截图 | 结论 | 复核人 | 日期 |
|---|---|---|---|---|
| 工作台 | `tmp/console-screenshots/workbench.png` |  |  |  |
| 任务详情 | `tmp/console-screenshots/workbench-task.png` |  |  |  |
| 运行 | `tmp/console-screenshots/runs.png` |  |  |  |
| 报告中心 | `tmp/console-screenshots/reports.png` |  |  |  |
| 报告阅读 | `tmp/console-screenshots/report.png` |  |  |  |
| 资产 | `tmp/console-screenshots/assets.png` |  |  |  |
| 原始记录 | `tmp/console-screenshots/assets-records.png` |  |  |  |
| 连接器 | `tmp/console-screenshots/connectors.png` |  |  |  |
| 设置 | `tmp/console-screenshots/settings.png` |  |  |  |

## 生产 A canary

只读。需要验收账号。

```bash
P0_EMAIL='<账号>' P0_PASSWORD='<密码>' bash scripts/canary-console-production.sh
```

## 生产 A schema preflight

只读。`SCRAPY_EXPECTED_SCHEMA` 由 PG0 发布批次提供，固定为最终 head `202610220068`；C14 不修改 `scripts/preflight-production.sh` 的默认值，也不传 C6 的 `202610220062`。

```bash
SCRAPY_EXPECTED_SCHEMA=202610220068 bash scripts/preflight-production-a.sh
```

## 生产 B preflight

只读。不部署。

```bash
bash scripts/preflight-production-b.sh
```

## PG0 开关只读证据

PG0 发布批次负责打开四个开关并重启。C14 只读：

```bash
bash scripts/verify-pg0-switches.sh
PG0_SWITCH_HOST='ubuntu@101.34.52.232' PG0_SWITCH_KEY="$PWD/DDDD.pem" \
  bash scripts/verify-pg0-switches.sh
```

四个开关：`budget_enforcement_enabled`、`strict_price_enabled`、`run_execution_convergence_enabled`、`retention_cleanup_enabled`。任一不是 `true` 就记 `BLOCKED`，C14 不翻转。

## 证据

| 门禁 | 命令 | 结果 | 日期 |
|---|---|---|---|
| 单元测试 | `pnpm -C apps/scraper-console test` |  |  |
| 类型检查 | `pnpm -C apps/scraper-console typecheck` |  |  |
| Lint | `pnpm -C apps/scraper-console lint` |  |  |
| Build | `pnpm -C apps/scraper-console build` |  |  |
| Playwright | `pnpm -C apps/scraper-console exec playwright test` |  |  |
| p0 验收 | `bash scripts/p0_acceptance.sh` |  |  |
| A canary | `bash scripts/canary-console-production.sh` |  |  |
| A schema preflight | `SCRAPY_EXPECTED_SCHEMA=202610220068 bash scripts/preflight-production-a.sh` |  |  |
| B preflight | `bash scripts/preflight-production-b.sh` |  |  |
| PG0 开关 A | `bash scripts/verify-pg0-switches.sh` |  |  |
| PG0 开关 B | `PG0_SWITCH_HOST='ubuntu@101.34.52.232' PG0_SWITCH_KEY=DDDD.pem bash scripts/verify-pg0-switches.sh` |  |  |
````

- [ ] **Step 2: 更新 README**

在 `apps/scraper-console/README.md` 增加：

````markdown
## C14 验收

```bash
export WORKBENCH_TASKS_ENABLED=true
export WORKBENCH_TAXONOMY_PATH="$(git rev-parse --show-toplevel)/configs/taxonomy/maternal_v1.json"
pnpm test
pnpm typecheck
pnpm lint
pnpm build
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash ../../scripts/seed-console-e2e.sh
pnpm exec playwright test
```
````

- [ ] **Step 3: 增加页面存在性测试并跑最终门禁**

新建 `apps/scraper-console/src/lib/contract-routes.pages.test.ts`：

```typescript
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { CONTRACT_ROUTES, contractRoutePageFile } from "./contract-routes.ts";

const APP_DIR = new URL("../app/", import.meta.url);

test("每条启用的合同路由都有页面文件", () => {
  for (const route of CONTRACT_ROUTES) {
    if (!route.enabled) continue;
    const file = fileURLToPath(new URL(contractRoutePageFile(route), APP_DIR));
    assert.equal(existsSync(file), true, `${route.path} 缺少页面：${file}`);
  }
});

test("禁用的公开分享路由没有页面文件", () => {
  const share = CONTRACT_ROUTES.find(route => route.key === "public-report");
  assert.ok(share);
  const file = fileURLToPath(new URL(contractRoutePageFile(share), APP_DIR));
  assert.equal(existsSync(file), false);
});
```

Run:
```bash
export WORKBENCH_TASKS_ENABLED=true
export WORKBENCH_TAXONOMY_PATH="$(git rev-parse --show-toplevel)/configs/taxonomy/maternal_v1.json"
pnpm -C apps/scraper-console test
pnpm -C apps/scraper-console typecheck
pnpm -C apps/scraper-console lint
pnpm -C apps/scraper-console build
CONSOLE_E2E_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" bash scripts/seed-console-e2e.sh
pnpm -C apps/scraper-console exec playwright test
P0_BASE_URL='http://127.0.0.1:3001' P0_API_BASE_URL='http://127.0.0.1:8000' \
P0_EMAIL='e2e-console@example.com' P0_PASSWORD="${CONSOLE_E2E_PASSWORD:?set CONSOLE_E2E_PASSWORD}" \
bash scripts/p0_acceptance.sh
python3 scripts/verify-console-ci-gates.py
```
Expected: 全部通过。Playwright 生成 9 张截图与 `manifest.json`。

- [ ] **Step 4: 检查边界**

先设置包含 C0–C13 的集成分支或标签为比较基线，再检查整个 C14 分支没有迁移、API 路由、MCP 或后端服务改动：

```bash
BASE="${C14_BASE_REF:?set C14_BASE_REF to the integration tip containing C0-C13}"
git merge-base --is-ancestor "${C12_TIP:?set C12_TIP}" "$BASE"
CHANGED="$(git diff --name-only "$BASE"..HEAD)"
printf '%s\n' "$CHANGED" | grep -E '^apps/api/(alembic/versions|src/data_intelligence_hub/api/routes|src/data_intelligence_hub/mcp_runtime)/' && exit 1
printf '%s\n' "$CHANGED" | grep -E '^apps/api/src/data_intelligence_hub/(models|services|repositories|schemas)/' | grep -v -E '^apps/api/src/data_intelligence_hub/maintenance/e2e_(seed|cleanup)\.py$' && exit 1
printf '%s\n' "$CHANGED" | grep -E '^docs/design/.*契约冻结' && exit 1
! grep -rn "reports/public" apps/scraper-console/src/app --include="page.tsx"
```
Expected: 四条检查均无输出且退出码为 0。出现输出时停止并修复。C14 不得新增迁移、API 路由、MCP 工具或后端业务代码；只允许 `maintenance/e2e_seed.py` 与 `maintenance/e2e_cleanup.py` 例外。

- [ ] **Step 5: 运行 GitNexus 变更检查**

Run: `node .gitnexus/run.cjs detect-changes --scope all --repo .`
Expected: `partial` 与 `truncated` 均为 `false`。不通过时重跑，不提交。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/console-acceptance.md apps/scraper-console/README.md \
  apps/scraper-console/src/lib/contract-routes.pages.test.ts
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(console): record c14 acceptance runbook and evidence"
```

---

## 验收矩阵

| 要求 | 任务 | 可复核证据 |
|---|---|---|
| 4 条一级导航 | Task 1 | `contract-routes.test.ts`；9 张截图侧栏 |
| 11 条合同路由（10 启用、1 禁用） | Task 1 | `CONTRACT_ROUTES.length === 11`；启用 10、禁用 1 |
| 与 B5 动态段名对齐 | Task 1 | `[toolId]`、`[taskId]`、`[artifactId]` 断言 |
| 工作台接真实 API | Task 3 | `workbench.ts`、Playwright 工作台路径 |
| 运行接真实 API | Task 4 | `fetchRunSteps`、运行详情步骤时间线 |
| 报告接真实 API | Task 5 | 合同与证据引用读取 |
| 内部审阅与发布 | Task 5、Task 8A | 默认只读显示发布账号和修订链；本地/CI 合成工作区执行审核人指派、审核、发布、Quick 草稿、交付与验收动作 |
| 资产接真实 API | Task 6 | 数据集与原始记录四态 |
| 资产质量列与质量页签 | Task 6、Task 9 | `assets-quality.spec.ts`；质量列、质量页签、缺失值显示“缺失” |
| 质量链只读 C8 | Task 6 | 控制台只显示 `quality_status`/`quality_assessment`/`data_gaps`，不重算；C8 依赖 C6 `run.completed` |
| 连接器接真实 API | Task 7 | 凭据、平台包、提供方状态合并 |
| 设置接真实 API | Task 8、Task 8A | 会话、`/settings` 内联成员、用量、C2/C3/C11/C12/C13 交接面板；`members.spec.ts` 覆盖邀请、改角色、最后 owner 错误、项目分配与三视角可见性 |
| Middleware 公开 allowlist | Task 2 | `middleware-policy.test.ts` |
| CI unit/tsc/lint/build | Task 12 | `console-quality` 作业 |
| CI Playwright 阻塞 | Task 12 | `console-acceptance` 无 `continue-on-error` |
| Seed/cleanup/auth storage | Task 9 | `e2e_seed.py`、`test_e2e_seed_db.py`、`seed-console-e2e.sh`、`auth.setup.ts` |
| 正负黄金路径 | Task 10 | 正 3 条、负 11 条 Playwright（含 6 条匿名路由） |
| 截图 | Task 11 | 9 张 PNG 与 manifest |
| `p0_acceptance.sh` | Task 13 | PASS/FAIL 输出与退出码 |
| 生产 A canary | Task 14 | `canary-console-production.sh` |
| 生产 A schema preflight | Task 14 | `preflight-production-a.sh`；`SCRAPY_EXPECTED_SCHEMA=202610220068` 由 PG0 发布批次提供，断言 `schema revision 202610220068` |
| 生产 B preflight | Task 14 | `preflight-production-b.sh` |
| PG0 开关只读证据 | Task 14 | `verify-pg0-switches.sh` 四项均为 true；C14 不翻转 |
| 无迁移 | 全部 | `git diff` 边界检查 |
| 不启用公开分享 | Task 1、2、10 | 路由无页面、middleware 放行后 404、负路径测试 |
| 不新增审批收件箱 | Task 3、Task 8A | 批准只在任务详情与项目密钥行内联；使用 C1 已登记的批准路径 |
| Q43 工作区级盐 | 全部 | 不改伪名盐代码；设置页不展示盐 |
| `creator_cookie` 内部隔离 | Task 7 | 连接器页过滤 `creator_cookie` 与 `creator_cookie_metadata`，序列化响应不含 `cookie` |
| 八客户 MCP 工具 | 全部 | 不改 `mcp_runtime/`；边界检查 |
| 保留期冻结 | 全部 | 不改保留策略 |
| 已登记治理动作 UI | Task 8A | 任务提交/取消、内联批准、成员与密钥 CRUD、quota、Claim、审核发布、交付验收、隐私删除；`governance-actions.spec.ts` 七条正负路径；`members.spec.ts` 八条成员面板路径 |

## Self-Review

- [ ] Task 8A 的治理动作客户端、页面控件、七条治理动作 Playwright 用例与八条 `members.spec.ts` 用例全部通过；只使用 C1 已登记路径。
- [ ] 成员管理是 `/settings` 的内联面板，`docs/ops/c2-c14-members-handoff.md` 已消费；没有 `/settings/members` 路由或链接，11 条合同路由不变。

- [ ] 11 条合同路由逐条有任务或明确禁用状态。
- [ ] 4 条一级导航逐条有断言。
- [ ] 六个页族逐族有真实 API 客户端和 Playwright 路径。
- [ ] `/workbench` 表单发送 `package_type`、`primary_market`、`comparison_markets`；Quick 最多 1 个对比市场，Standard 最多 3 个；不新增其他产品阈值。
- [ ] 动态段名来自契约 §5；`contract-routes.test.ts` 直接解析 §5，没有第二份硬编码路由清单。
- [ ] 生产只读：C14 不部署、不备份、不迁移、不重启、不改 compose/env、不 seed 生产、不翻转四个 PG0 开关；发布动作只属于 PG0 发布批次。
- [ ] 超额、加购、密钥变更的批准资格只在任务详情与项目密钥行内联展示；没有 `/approvals` 路由；发起人不能自批由 `inline-approvals.test.ts` 覆盖。
- [ ] 同工作区跨项目成员负路径覆盖任务、Claim、报告、交付与资产，断言 403。
- [ ] 报告页显示 C9 的 `published_by`、`published_at` 与修订链；Task 8A 在本地/CI 合成工作区调用已登记的审核、发布与交付验收动作；生产 canary 只读。
- [ ] 四个 PG0 开关有只读证据脚本；C14 只记录 true/false，不写 env、不重启。
- [ ] CI 五个门禁全部阻塞，旧 `continue-on-error` 已删除。
- [ ] 种子只写本地/CI，生产 guard 生效。
- [ ] 种子审计只调用 C2 `append_audit_event`，使用已登记动作 `project.created`；不手写 `AuditEvent`，不缺少 `sequence_number`/`prev_hash`/`event_hash`；`test_e2e_seed_db.py` 在 SQLite 与 PostgreSQL 上都验证哈希链与重复 seed 幂等。
- [ ] CI Postgres service 的 `POSTGRES_PASSWORD` 与 `DATABASE_URL` 密码一致；`verify-console-ci-gates.py` 解析两处并比较，不依赖单一片段字符串。
- [ ] `WORKBENCH_TASKS_ENABLED=true` 与绝对路径 `WORKBENCH_TAXONOMY_PATH` 只出现在本地/CI E2E；生产 A/B 只由 PG0 发布批次设置，C14 只读。
- [ ] 生产 A schema preflight 通过 `SCRAPY_EXPECTED_SCHEMA` 读取 PG0 提供的最终 head `202610220068`；不硬编码 C6 的 `202610220062`，不修改 `scripts/preflight-production.sh`。
- [ ] 公开分享无页面、无入口、无分享 API 调用。
- [ ] 没有迁移、没有新 API 路由、没有 MCP 工具改动。
- [ ] 所有代码步骤都有实际代码，且占位符扫描通过。
- [ ] `/assets` 质量列与质量页签由 `assets-quality.spec.ts` 覆盖；`quality_status=null` 显示“未评分”，缺失样本显示“缺失”。
- [ ] C14 不重算质量；质量数据来自 C8，C8 的 `run.completed` 消费依赖 C6。
