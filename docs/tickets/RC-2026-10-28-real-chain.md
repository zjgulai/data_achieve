---
name: rc-real-chain-tickets-2026-10-28
description: 真实链路 E2E 门禁（A 切片）的 ticket 台账。记录 12 条任务的方案、依赖顺序与验收证据。当执行或复核真实链路门禁工作时使用。
title: 真实链路 E2E 门禁 ticket 台账
doc_type: ticket
module: qa
topic: real-chain-e2e
status: active
created: 2026-10-28
updated: 2026-10-28
owner: self
source: human+ai
---

# 真实链路 E2E 门禁 · ticket 台账（2026-10-28）

> 决策依据：[ADR-008 真实链路 E2E 门禁](../architecture/decisions/ADR-008-real-chain-e2e-gate.md)
> 机器可读版本：[RC-2026-10-28-real-chain.json](RC-2026-10-28-real-chain.json)

## 这份台账要解决的问题

工作台的完成定义是「打开工作台 → 选业务域 → 真实采集数据 → 洞察 → 证据 → 可交付报告，全程不依赖 mock」。

2026-10-28 复核的结论是：这条链的代码路径存在，但没有任何东西锁住它。默认 E2E 与 CI 都跑 mock；外置 base URL 时 Playwright 不启动 webServer；生产 A 的 web 在 `/insight` 而 E2E 全用根绝对路径；注册不建项目；报告域筛选用 inner join 会静默丢掉 `project_id` 为 NULL 的报告。

本批 ticket 把这条链拆成可独立验证的八片，逐片打通并最终进门禁。

## 总览

| 编号 | 标题 | 优先级 | 状态 | 依赖 |
|---|---|---|---|---|
| RC-01 | 落 ADR-008 并更新 ADR 索引 | P0 | 已完成 | — |
| RC-02 | 一次性本地真实栈与 edge 反代 | P0 | 已完成 | RC-01 |
| RC-03 | 真实链路 Playwright 配置、种子 helper 与 UI 登录用例 | P0 | 已完成 | RC-02 |
| RC-04 | 业务域记录断言与 /raw-records 域筛选修复 | P0 | 已完成 | RC-03 |
| RC-05 | 洞察与证据断言（非 mock 证明） | P0 | 已完成 | RC-04 |
| RC-06 | 报告生成、证据引用与站内发送 | P0 | 已完成 | RC-05 |
| RC-07 | CI scoped job、门禁脚本与 verifier 扩展 | P0 | 已完成 | RC-06 |
| RC-08 | 生产 A 只读真实数据冒烟（owner-run） | P1 | 未开始 | RC-07 |
| RC-09 | 报告按业务域生成与筛选口径统一 | P1 | 未开始 | RC-06 |
| RC-10 | 域页信号与工具库链接补域参数 | P2 | 未开始 | — |
| RC-11 | 生产写入前的清理账本与 test:e2e:real 收敛 | P2 | 未开始 | RC-08 |
| RC-12 | 域页仪表盘叠加全局项目过滤导致跨域清零 | P2 | 未开始 | — |

依赖是硬的：RC-02 到 RC-07 必须按序执行，每一片的验收证据是下一片的前置。RC-09、RC-10、RC-12 可以在任何时间并行，它们修的是产品口径，不阻塞门禁。

## 执行顺序的理由

**RC-02 先于 RC-03。** 没有同源真实栈，浏览器无法在真实模式下完成登录并取数：跨源会让 `SameSite=Lax` 的 Cookie 不随 fetch 发送。

**RC-03 先于 RC-04。** 每片用例都要复用同一份种子（一次性账号 + competitor 项目 + 两次采集）。种子不成立，后面四片全部无从断言。

**RC-06 必须做产品修复，不只是写测试。** 域页报告链接不带 domain、生成请求没有 domain、域筛选走 inner join，三处是同一个口径问题。只改测试会在断言处撞墙。报告口径的完整定稿另立 RC-09，RC-06 只做到「当前域内能生成并看到报告」。

**RC-07 最后。** 门禁脚本要跑前面五片的 spec，spec 不稳定时上门禁只会制造一个长期红灯。

## 每片的验收标准

验收一律以命令输出为准，不以「看起来对」为准。

### RC-02

```bash
bash scripts/e2e-real-stack.sh up
curl -fsS http://127.0.0.1:8090/api/health      # status=ok，database=connected
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/dashboard   # 307
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/api/projects # 401
bash scripts/e2e-real-stack.sh down
docker ps --filter name=data-achieve-e2e        # 无输出
```

### RC-03 到 RC-06

每片一条 `playwright.real-chain.config.ts` 的用例，各自带 grep 标签：

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8090 \
  pnpm -C apps/web exec playwright test -c playwright.real-chain.config.ts \
  --project=desktop --grep "@login"        # 或 @domain-records / @insight-evidence / @report
```

每条用例必须 `waitForResponse` 到对应的真实接口（见 ADR-008 的 D3），仅断言页面文本不算通过。

### RC-07

```bash
bash scripts/verify-real-chain-e2e.sh                       # 退出 0
python3 scripts/verify-ci-no-unscoped-real-e2e.py           # ci_real_e2e_boundary_ok
pytest apps/api/tests/unit/test_ci_no_unscoped_real_e2e.py  # 全过
```

verifier 必须有反面用例：构造一个外网 base URL 或缺少 `down -v` 的临时 workflow 时，它必须退出 1。

### RC-08

需要 owner 逐条授权，命令形如：

```bash
PLAYWRIGHT_BASE_URL=https://scrapy.luteos.com \
PLAYWRIGHT_BASE_PATH=/insight \
PLAYWRIGHT_CHAIN_ALLOW_REMOTE=true \
SCRAPY_DEMO_EMAIL=... SCRAPY_DEMO_PASSWORD=... \
  pnpm -C apps/web exec playwright test -c playwright.real-chain.config.ts \
  --project=desktop --grep "@readonly"
```

执行前后对比生产 `users`、`projects`、`raw_records` 计数必须一致。报告段 skip 并在输出里写明原因。

## 不做什么

以下都不在本批范围内，另行处理：

- **不写生产。** 门禁只连本地栈。生产写入要另立授权，且必须先有 `always()` cleanup、精确 ID 账本与 recount 零校验（RC-11）。
- **不改造既有 4 个 spec 的 basePath。** 88 条用例建立在根绝对路径与 mock 之上，统一改造风险远大于收益（ADR-008 D4）。
- **不引入 BFF 或本地 /api 代理。** 生产拓扑是 edge 分发，新增 BFF 会验证一套生产不存在的路径。
- **不用生产库 dump 当种子。** 验证的是旧快照，不是当前代码与当前链路。
- **不为绿灯放宽断言或加 skip。** 门禁失败时要么修链路，要么修测试；用 skip 换绿灯等于把门禁废掉。

## 变更记录

- 2026-10-28：建立台账。
- 2026-10-28：RC-01 至 RC-07 完成并实测通过。门禁 `bash scripts/verify-real-chain-e2e.sh` 退出 0，四条用例全绿，零残留容器与卷。RC-08、RC-09、RC-10、RC-11、RC-12 未开始。
