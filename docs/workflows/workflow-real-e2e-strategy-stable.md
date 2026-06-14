---
title: 真实 API E2E 策略
doc_type: workflow
module: qa
topic: real-api-e2e
status: stable
created: 2026-06-14
updated: 2026-06-14
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

## 当前执行方式

本地命令：

```bash
PLAYWRIGHT_REAL_API=true \
PLAYWRIGHT_BASE_URL="https://scrapy.lute-tlz-dddd.top" \
SCRAPY_DEMO_EMAIL="$E2E_EMAIL" \
SCRAPY_DEMO_PASSWORD="$E2E_PASSWORD" \
pnpm -C apps/web exec playwright test
```

CI 当前提供手动入口：

```bash
gh workflow run CI \
  -f base_url=https://scrapy.lute-tlz-dddd.top
```

GitHub Actions job：`web-real-e2e`，触发条件为 `workflow_dispatch`。

## 测试账号策略

必须使用一次性账号，禁止使用 demo 账号。

执行前置：

1. 生成一次性 email。
2. 生成一次性强密码。
3. 调用 `/api/auth/register`。
4. 使用注册返回 cookie 调用 `/api/projects` 创建 `osint` 项目。
5. 把一次性 email/password 传给 Playwright。

这样可以隔离测试产生的 source、task、report、notification，避免污染演示账号最新情报排序。GitHub Actions 的 `web-real-e2e` job 已按此策略执行。

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

## 夜间策略

夜间执行建议：

1. 在 GitHub Actions 增加 `schedule`，频率不高于每日一次。
2. 使用动态注册策略创建 `e2e-` 一次性用户。
3. 夜间只跑真实 API E2E，不执行部署。
4. 失败时保留 Playwright trace。
5. 连续失败 2 次再升级为发布阻塞，避免短时网络抖动误报。

暂不直接启用自动夜间任务的原因：

1. 真实 E2E 会持续创建用户和测试数据。
2. 当前还没有自动清理 job。
3. 生产环境不是专用 staging 环境。

启用夜间任务前必须完成测试数据清理策略。

## 测试数据清理策略

短期：

1. 一次性用户以 `e2e-` 前缀命名。
2. E2E 项目名以 `Production E2E` 前缀命名。
3. 不在 demo 账号内创建测试数据。

中期：

1. 新增 admin-only cleanup script。
2. 删除超过 7 天的 `e2e-` 用户 workspace。
3. cleanup script 先 dry-run 输出数量，再执行。

## 通过标准

一次生产真实 API E2E 合格必须同时满足：

1. `/api/health` 返回 200。
2. API 容器、web 容器、edge 容器、db 容器均 healthy。
3. Playwright 主流程 `17 passed, 5 skipped`。
4. skipped 项必须是 desktop 下 mobile-only layout guard。
5. 失败 trace 不为空，便于定位。

## 最近验收记录

2026-06-14 已完成：

1. 本地完整 gate：API `45 passed`，Playwright `17 passed, 5 skipped`。
2. 生产真实 API E2E：Playwright `17 passed, 5 skipped`。
3. 生产容器：api、db、edge、web 均 healthy。
