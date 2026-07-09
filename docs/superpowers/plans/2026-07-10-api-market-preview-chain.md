# API Market Preview Chain Implementation Plan

> 本计划用于把 `API市场` 详情页接入现有 `social-provider` fixture-only 预案链。执行中保持 `provider_call=false`、`provider_call_attempted=false`、`credential_read_attempted=false`、`live_client_created=false`、`production unchanged`。

## 盘点结论

- 已完成：后端 `social-provider` catalog/readiness/gate/adapter-plan/source-template/dataset-preview/task-run-approval/execution-dry-run endpoints 已存在，并有 API 与 Web 测试覆盖。
- 已完成：`/automation` 已有海外社媒 fixture-only 预案面板。
- 已完成：`/api-market` 与 `/api-market/[endpointId]` 已有静态市场页、下钻详情页和 E2E。
- 未完成：API 市场详情页还不能在本页直接生成 readiness、adapter plan、dataset preview、source template、approval packet、execution dry-run 的 review bundle。

## 分批执行顺序

### Batch 1: 计划与边界冻结

- [x] 读取项目上下文、当前分支状态、social-provider 现状和已有计划文档。
- [x] 确认本批不做 live provider、credential read、Source/Task/Dataset create、production write。
- [x] 保存本计划。

### Batch 2: API Market Preview Helper

- [x] 新增纯 helper：`apps/web/src/lib/api-market-preview-chain.ts`。
- [x] 从 `ApiMarketEndpoint` 生成 social-provider preview chain inputs。
- [x] 单测覆盖 YouTube comment endpoint、Reddit/X 等非 YouTube endpoint，并断言 fixture-only 默认值。

### Batch 3: Detail UI Preview Chain

- [x] 修改 `ApiMarketDetailWorkspace`，新增 `生成本页预案` 按钮。
- [x] 调用现有 `social-provider` API glue：readiness、adapter plan、dataset preview、source template、task-run approval、execution dry-run。
- [x] 渲染 compact preview chain：Readiness、Adapter Plan Gate、Dataset Preview Gate、Source Template Gate、L4 Approval Packet Gate、Execution Dry Run。
- [x] 保留原 `生成预案` 跳转入口，但不新增 live/run/install/save/export 按钮。

### Batch 4: E2E 与浏览器验收

- [x] 扩展 API market E2E：在详情页点击 `生成本页预案`，断言关键 gate 可见。
- [x] 运行 API market scoped Playwright。
- [x] 运行移动 overflow guard。
- [x] 本地浏览器 smoke 检查 desktop/mobile 详情页 preview chain。

### Batch 5: 收尾验证

- [x] 运行 `corepack pnpm lint:web`。
- [x] 运行 `corepack pnpm test:web`。
- [x] 运行 `corepack pnpm --dir apps/web build`。
- [x] 运行 `git diff --check` 和凭据字段扫描。
- [x] 精确 stage 本批文件，保留既有未跟踪 draft。
- [x] commit、push，并观察 PR #11 checks。

## 本地验证结果

- `corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts`: passed, 7 tests.
- `corepack pnpm --dir apps/web exec playwright test --grep "API market"`: passed, desktop/mobile.
- `corepack pnpm --dir apps/web exec playwright test --grep "/api-market"`: passed, mobile overflow guard.
- Browser smoke: desktop/mobile preview chain overflow `0`, `provider_call_attempted=false`, `credential_read_attempted=false`.
- `corepack pnpm lint:web`: passed.
- `corepack pnpm test:web`: passed, 29 tests.
- `corepack pnpm --dir apps/web build`: passed.
- `git diff --check`: passed.

## 验收边界

- `provider_call=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `live_client_created=false`
- `source_created=false`
- `task_created=false`
- `dataset_write_allowed=false`
- `production_write_allowed=false`
- `production unchanged`
