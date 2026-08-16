---
title: 真实 API E2E 策略
doc_type: workflow
module: qa
topic: real-api-e2e
status: stable
created: 2026-06-14
updated: 2026-07-17
owner: self
source: human+ai
---

# 真实 API E2E 策略

## 目标

真实 API E2E 用来验证生产数据链路，不替代本地 mock E2E。它必须证明以下事实：

1. 生产域名可访问。
2. Cookie 登录有效。
3. 项目、source、task、run、intelligence、evidence、report、alert、notification 主路径可用。
4. 页面没有移动端横向溢出。
5. 测试产生的数据与演示账号隔离。

## 当前执行边界（2026-07-14）

通用 GitHub Actions `web-real-e2e` job 已移除，`workflow_dispatch` 也不再接收 `base_url`。原因是原 job 会创建持久对象，却没有可强制执行的 `always()` cleanup、精确 ID 账本和 recount 控制面。当前仓库没有可声明为 V2 release gate 的 generic real-API CI 路径。

`apps/web test:e2e:real` 暂时只保留为 Owner-run 工具。任何执行都需要新的精确授权包；本文不是生产执行授权，Route A 也没有运行真实 API E2E。

2026-07-17 新增的 WorkflowRun materialization 仍是 server-registered offline
fixture 路径，Web 没有写控件。其 `976 passed / 72 skipped / 6 warnings` API full 和 26-page
mock build 不能作为 real API/Provider 证据。Revision 034 PostgreSQL gate 已在唯一
授权的 disposable target 通过 `13/13`；未来真实验收仍须为 live Provider adapter、目标 Project/Dataset、请求预算、
RawRecord retention、cleanup/recount 和禁止触碰其他数据库取得单独授权。

## Owner-run 命令模板

本地命令：

```bash
PLAYWRIGHT_REAL_API=true \
PLAYWRIGHT_BASE_URL="https://scrapy.lute-tlz-dddd.top" \
SCRAPY_DEMO_EMAIL="$E2E_EMAIL" \
SCRAPY_DEMO_PASSWORD="$E2E_PASSWORD" \
pnpm -C apps/web exec playwright test
```

必须显式设置 `PLAYWRIGHT_BASE_URL`；package script 的历史默认 URL 不能替代授权。执行前还必须冻结命名测试范围、一次性身份、创建 ID 记录、预算、保留与清理方式。

## 测试账号策略

必须使用一次性账号，禁止使用 demo 账号。

执行前置：

1. 生成一次性 email。
2. 生成一次性强密码。
3. 调用 `/api/auth/register`。
4. 使用注册返回 cookie 调用 `/api/projects` 创建 `osint` 项目。
5. 把一次性 email/password 传给 Playwright。

这样可以把测试对象与 demo 账号分开，但“隔离账号”本身不等于“可回收”。执行方仍须记录本轮创建的所有 ID，并在成功、失败或取消后执行 cleanup 与 recount。

## 覆盖范围

当前 `apps/web/tests/e2e/main-flows.spec.ts` 覆盖：

| 页面 | 验证点 |
|---|---|
| `/dashboard` | 真实登录后 dashboard 可见，情报总量可见 |
| `/intelligence` | 情报列表、证据时间线、详情页、Raw Record 链接 |
| `/reports` | 报告队列、订阅保存、手动执行、详情页、Markdown 下载、发送报告 |
| `/alerts` | 告警中心、规则创建、事件展示 |
| `/sources` | source 创建、编辑、重测、启用、停用 |
| `/tasks` | 任务列表、暂停、恢复、日志、运行历史 |
| `/notifications` | 偏好保存、批量标记已读 |
| 移动端 | `/reports`、`/alerts`、`/notifications`、`/tasks`、`/sources` 无横向溢出 |

## 未来夜间策略（GOAL-V2-07）

夜间执行建议：

1. 先设计独立、命名、定向的 real-API workflow，再考虑 `schedule`，频率不高于每日一次。
2. 使用动态注册策略创建 `e2e-` 一次性用户。
3. 夜间只跑真实 API E2E，不执行部署。
4. 失败时保留 Playwright trace。
5. 连续失败 2 次再升级为发布阻塞，避免短时网络抖动误报。

暂不直接启用自动夜间任务的原因：

1. 真实 E2E 会持续创建用户和测试数据。
2. 当前还没有自动清理 job。
3. 生产环境不是专用 staging 环境。

启用夜间任务前必须完成可强制执行的测试数据清理策略；当前未启用。

## 测试数据清理策略

短期：

1. 一次性用户以 `e2e-` 前缀命名。
2. E2E 项目名以 `Production E2E` 前缀命名。
3. 不在 demo 账号内创建测试数据。

中期：

1. 已新增服务器侧 cleanup script：`scripts/cleanup-e2e-fixtures.sh`。
2. 默认只审计或删除超过 7 天的 `e2e-*@example.com` 用户及其 workspace 全链路数据。
3. cleanup script 默认 dry-run，只有显式 `--execute` 才写库。

执行方式：

```bash
# dry-run
SCRAPY_CLEANUP_USE_DOCKER=1 bash scripts/cleanup-e2e-fixtures.sh

# 清理超过 7 天的 E2E fixture
SCRAPY_CLEANUP_USE_DOCKER=1 bash scripts/cleanup-e2e-fixtures.sh --execute

# 部署验收后立即清理本轮 E2E fixture
SCRAPY_CLEANUP_USE_DOCKER=1 bash scripts/cleanup-e2e-fixtures.sh --older-than-hours 0 --execute
```

## 未来 V2 通过标准

一次被授权的定向生产真实 API E2E 合格必须同时满足：

1. 授权包明确目标环境、命名测试、预算、数据保留和回滚负责人。
2. `/api/health` 与目标容器健康检查通过。
3. 定向 Playwright 测试全部通过；skip 必须逐项解释，不能沿用历史固定计数。
4. 创建 ID 账本完整，`always()` cleanup 或等价失败闭环执行。
5. cleanup 后 recount 为零；保留项必须有独立批准和 TTL。
6. trace、测试结果、cleanup 与 recount 产物均被保留。

## 最近验收记录

历史记录（不代表当前 V2 gate）：2026-06-14 已完成：

1. 本地完整 gate：API `45 passed`，Playwright `17 passed, 5 skipped`。
2. 生产真实 API E2E：Playwright `17 passed, 5 skipped`。
3. 生产容器：api、db、edge、web 均 healthy。
