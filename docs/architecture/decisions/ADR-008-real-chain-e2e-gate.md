---
name: adr-008-real-chain-e2e-gate
description: 真实链路 E2E 门禁的架构决策记录。固定一次性本地真实栈、一次性账号种子、网络响应作为非 mock 证明、门禁不写生产、CI scoped job 与生产只读冒烟边界。当修改 E2E 门禁、真实链路验收或生产只读冒烟时使用。
---

# ADR-008：真实链路 E2E 门禁（一次性本地真实栈，不写生产）

> 状态：已采纳
> 日期：2026-10-28
> 决策者：lute
> 相关文档：[ADR-007 基线](ADR-007-baseline-auth-and-transaction.md) · [真实 API E2E 策略](../workflows/workflow-real-e2e-strategy-stable.md) · [Monid 差距分析](../architecture/【差距分析】Monid能力对照与复刻路线.md)

## 背景

工作台的完成定义（DoD）是：一个人打开工作台，选业务域，看到真实采集的数据 → 形成的洞察 → 可交付的报告，全程不依赖 mock。

2026-10-28 复核这条链在仓库与生产上的真实状态，结论是代码路径存在但没有任何东西锁住它。

前端 mock 是构建期常量。`NEXT_PUBLIC_MOCK_API=true` 时各 API 模块在发请求前直接返回内存数据，`apps/web/src` 只剩 `client.ts` 一处 `fetch`（`client.ts:105`）。默认 `test:e2e` 由 `playwright.config.ts:24` 的 webServer 注入 `NEXT_PUBLIC_MOCK_API=true`，CI 的 Web Quality Gate 同样只在 mock 下跑（`ci.yml:253-258`）。仓库里没有 mock HTTP 服务，也没有 BFF。

设置 `PLAYWRIGHT_BASE_URL` 后 `playwright.config.ts:20-29` 完全不启动 webServer。三个既有套件在 `beforeAll` 里直接抛错（`platform-credentials.spec.ts:41-47`、`capability-governance.spec.ts:58-64`、`main-flows.spec.ts:1947-1953`），因此外置 base URL 时全量 suite 不可用。

生产拓扑与测试假设不一致。生产 A（`scrapy.luteos.com`）已部署 `890d06f`，web 挂在 `/insight`；生产 B 是 `bf7a2815`，其 edge 没有 `/insight` 也没有 web 路由，根路径只到 console。E2E 全部使用根绝对路径（`main-flows.spec.ts` 有 28 处 `page.goto("/...")`），没有一处处理 basePath。

真实登录链路本身可用，但注册不建项目。`POST /api/auth/login` 设置 `access_token` Cookie；生产 `APP_ENV=production` 使 demo 回退关闭。而 `auth_service.py:39-81` 只创建 User、Workspace、WorkspaceMember，不创建 Project；真实 fixture 在 `/api/projects` 为空时抛 `requires at least one project`（`main-flows.spec.ts:361-364`）。

生产有真实数据，但报告段没有闭环。生产 A 库内 `raw_records` 13630 条、`signals` 15 条、`intelligence_items` 13 条；competitor 域 13444 条记录、9 条情报。域页「最近采集」确实调用 `GET /api/raw-records?domain=...` 并展示。但 `reports` 只有 1 条，`project_id` 为 NULL，2026-10-09 生成；`repositories/reports.py:48-58` 的域筛选是 inner join projects，project_id 为 NULL 的报告被静默排除。

CI 主动禁止真实 E2E。`verify-ci-no-unscoped-real-e2e.py:44-60` 见到 `PLAYWRIGHT_REAL_API`、`web-real-e2e` 或 `workflow_dispatch.inputs.base_url` 即判违规。

把这些放在一起：登录、域记录、洞察、证据四段的代码路径都存在，缺的是一条无 mock 的同源运行面、可重复的域内数据种子、报告段的域内闭环，以及把这链路放进 CI 的门禁。

## D1 门禁目标是一次性本地真实栈

### 背景

浏览器要完成真实登录并取数，页面与 API 必须同源，且 Cookie 可写。现有默认 E2E 是 mock，外置 base URL 又不启动 webServer。生产 A 有真实数据但不允许写（下面 D5）。直接指向生产做门禁在报告段必然失败。

### 决定

新增一次性本地真实栈，作为唯一强制真实链路门禁。栈由 db、migrate、api、web、edge 五个服务组成：

- web 以 `NEXT_PUBLIC_MOCK_API=false`、空 basePath、`NEXT_PUBLIC_API_URL=http://127.0.0.1:8090` 构建。
- API 设 `APP_ENV=production` 关闭 demo 回退，`AUTH_COOKIE_SECURE=false` 使 http 下 Cookie 可用，`SCHEDULER_ENABLED=false` 与 `RUN_WORKER_ENABLED=false` 关掉后台任务。
- edge 把 `/api/` 转 `api:8000`、`/` 转 `web:3000`，与生产 A 的拓扑一致（区别只在生产把 web 挂在 `/insight`）。
- compose 项目名独立，`down -v` 只删这套栈的卷，不触碰任何生产卷。

落地为 `configs/deploy/scrapy/docker-compose.e2e.yml`、`e2e-edge-nginx.conf` 与 `scripts/e2e-real-stack.sh`。

### 后果

链路第一次有了可重复、无 mock、同源的运行面。代价是本地与 CI 都要为这套栈付出 Docker 构建时间。

不得为了省时间让门禁复用生产 compose。生产 compose 带 `/insight` 前缀与 `AUTH_COOKIE_SECURE=true`，两处都会让门禁在一个与本地栈不同的形态下运行，验证的就不是同一套东西。

## D2 数据种子用一次性账号，走真实服务路径

### 背景

真实 fixture 要求已有 project，而注册不建 project。生产库不能用来造种子。

### 决定

每次运行注册一个 `e2e-chain-*@example.com` 一次性账号，然后依次：

1. `POST /api/projects` 建 `domain=competitor` 的项目。
2. 建 `manual_json` source。
3. 以 stars 100 → 360 跑两次采集，走 `execute_collection_task` → 归一化 → signal → intelligence 的真实服务路径。

种子载荷是测试输入，不是前端 mock：它作为采集输入喂给真实采集器，随后的每一次读都是真实 HTTP 响应。不使用 demo 账号，不依赖任何手工前置步骤。

### 后果

每次运行的数据完全可丢弃，`down -v` 即清零。种子必须在栈内完成，不得靠 dump 生产库——dump 验证的是旧快照而不是当前代码与当前链路，且含生产敏感内容。

## D3 非 mock 由网络响应证明，不由页面文本证明

### 背景

mock 分支在 `client.ts` 与各 API 模块提前 return，不发 HTTP。因此「页面上有数据」完全不能区分 mock 与真实。

### 决定

用例必须观察到真实的以下响应才算通过：

- `POST /api/auth/login`
- `GET /api/raw-records?domain=...`
- `GET /api/intelligence?domain=...`
- `GET /api/intelligence/{id}/evidences`
- `GET /api/reports?domain=...`

仅断言页面文本不算通过。

### 后果

每段用例都要显式 `waitForResponse`。这多写了代码，但它是这条门禁唯一可靠的非 mock 证明。放宽这一点等于把门禁退回 mock 水平。

## D4 门禁只跑新增的独立配置

### 背景

既有 4 个 spec 共 88 条，全部建立在根绝对路径与 mock 之上。给它们统一加 basePath 支持会牵动 28 处 `page.goto` 与多处 `beforeAll` 断言，风险与收益不成比例。

### 决定

门禁只跑新增的 `playwright.real-chain.config.ts` 与 `tests/real-chain/real-chain.spec.ts`，仅 `desktop` project。旧 4 个 spec 继续跑 mock，不做全量 basePath 改造。

新 spec 用 `appPath(path)` 拼接 `PLAYWRIGHT_BASE_PATH`，以便同一份 spec 也能用于 D7 的生产只读冒烟。

### 后果

两套 E2E 并存：mock suite 保证页面行为，real-chain suite 保证链路真实。两者不得混用同一命令。

## D5 门禁不写生产

### 背景

生产 `users`、`workspaces`、`workspace_members` 均为 1。写测试没有隔离身份、没有精确 ID 账本、没有 `always()` cleanup，也不满足 V2 通过标准（见策略文档「当前执行边界」）。

### 决定

门禁只连本地栈。用例在两种情况下直接失败：

- 未显式设置 `PLAYWRIGHT_BASE_URL`；
- base URL 非 loopback 且未设 `PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true`。

生产 A 与 B 不产生新用户、项目、记录或报告。

### 后果

门禁与生产数据彻底解耦。代价是门禁不覆盖生产已有的历史数据形态（例如那条 `project_id` 为 NULL 的旧报告）。

## D6 CI 新增 scoped job，并扩展 verifier 正向校验

### 背景

CI 目前只跑 mock，且 verifier 的职责是「禁止无边界真实 E2E」。新增合法门禁后，verifier 不能只会说不行。

### 决定

`ci.yml` 新增 `web-real-chain-e2e` job：base URL 固定 `http://127.0.0.1:8090`，`always()` 执行 `down -v`，作为 PR 必过检查。

扩展 `verify-ci-no-unscoped-real-e2e.py`：若存在该 job，必须满足 loopback base URL 与 `always()` 内的 `down -v`；继续拒绝 `PLAYWRIGHT_REAL_API`、`web-real-e2e` 和 `workflow_dispatch.inputs.base_url`。

### 后果

verifier 从纯否定变成「否定无边界 + 强制有边界」，两者都必须有反面用例，否则它会退化成一句永真断言。补 `test_ci_no_unscoped_real_e2e.py` 的正例与反例。

## D7 生产只读冒烟是 owner-run，不进 CI

### 背景

门禁跑在一次性栈上，覆盖不到生产真实数据的形态。生产 A 有 13444 条 competitor 记录与 9 条情报，值得只读核对。

### 决定

owner 显式授权后，可用同一 spec 的 `@readonly` 用例访问生产 A。必须同时设置 `PLAYWRIGHT_BASE_URL=https://scrapy.luteos.com`、`PLAYWRIGHT_BASE_PATH=/insight`、`PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true` 与 owner 提供的账号密码。用例拒绝自动注册；监听全部请求，除 `POST /api/auth/login` 外只允许 GET。

报告段在只读冒烟中 skip 并写明原因：生产没有按项目或按域的报告，写入又未授权。

### 后果

生产只读冒烟是一份可以交给 owner 重复执行的检查，不是门禁的替代品。生产写入要另立授权，且必须先有 `always()` cleanup、精确 ID 账本与 recount 零校验。

## 未决事项

1. 报告按业务域生成与域筛选口径统一（RC-09）。生成请求没有 `domain`，域筛选又是 inner join，两边必须同时定。
2. 域页「查看全部原始数据」忽略 `?domain`（RC-04）。`GET /api/raw-records` 本身支持该参数。
3. 域页信号与报告链接不带域参数（RC-10、RC-06）。
4. 域页仪表盘同时叠加全局项目过滤会导致跨域清零（RC-12）。
5. `test:e2e:real` 默认指向生产 B，而 B 没有 web 路由（RC-11）。
6. 本机 mock E2E 依赖宿主 corepack；当前环境无 corepack，需 `corepack enable` 或 pnpm 转发。

## 相关证据

- 默认 E2E 固定 mock：`apps/web/playwright.config.ts:24`；CI 只在 mock 下跑：`.github/workflows/ci.yml:253-258`
- 外置 base URL 不启动 webServer：`apps/web/playwright.config.ts:20-29`
- 既有套件在外置模式下自弃：`platform-credentials.spec.ts:41-47`、`capability-governance.spec.ts:58-64`、`main-flows.spec.ts:1947-1953`
- 注册不建项目：`apps/api/src/data_intelligence_hub/services/auth_service.py:39-81`；fixture 要求项目：`main-flows.spec.ts:361-364`
- 报告域筛选排除全局报告：`apps/api/src/data_intelligence_hub/repositories/reports.py:48-58`；生成请求无 domain：`schemas/report.py:28-33`
- 原始记录全量页忽略 domain：`apps/web/src/components/raw-records/raw-records-workspace.tsx:88-133`；接口支持 domain：`routes/raw_records.py:25-38`
- 域页报告链接不带域：`apps/web/src/app/domain/[domain]/page.tsx:141-143`
- verifier 禁止无边界真实 E2E：`scripts/verify-ci-no-unscoped-real-e2e.py:44-60`
- 生产事实：A 部署 `890d06f`，web 在 `/insight`；B 为 `bf7a2815`，无 `/insight`（`docs/ops/releases.jsonl`）
- 生产数据：`raw_records` 13630、`signals` 15、`intelligence_items` 13、`reports` 1（project_id NULL）
