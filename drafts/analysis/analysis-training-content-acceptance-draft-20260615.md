---
title: 培训内容生产验收记录
doc_type: analysis
module: training-content
topic: production-acceptance
status: draft
created: 2026-06-15
updated: 2026-06-15
owner: self
source: human+ai
---

# 培训内容生产验收记录

## 结论

生产站点 `https://scrapy.lute-tlz-dddd.top` 已完成培训内容刷新、页面交互修复、生产部署、真实 API E2E、测试噪音清理和页面级内容验收。

当前生产提交为 `08b5f6b`，数据库 schema 为 `202606110015`，`api/db/web/edge` 均为 healthy。

## 数据覆盖

| 页面 | 数据证据 | 当前数量 |
| --- | --- | ---: |
| `/projects` | 训练项目与 curated demo 项目 | 8 |
| `/sources` | GitHub、文档、网页、manual_json 来源 | 48 |
| `/tasks` | 采集任务 | 48 |
| `/raw-records` | 原始采集记录 | 52 |
| `/entities` | 仓库、网页、平台方法、合规边界实体 | 48 |
| `/signals` | 关注度、topic coverage、risk boundary、page_changed 信号 | 17 |
| `/intelligence` | 结构化情报 | 18 |
| `/reports` | 培训周报与日报 | 2 |
| `/alerts` | 预警规则与事件 | 6 rules / 6 events |
| `/notifications` | 站内通知 | 7 |

新增训练业务域已在前端正式展示：

- `/domain/agent`：Agent 生态
- `/domain/platform`：平台采集
- `/domain/governance`：合规边界

## 关键修复

- Alert 页面不再暴露 `Signal ID` 等技术噪音，事件卡片改为展示短批次号。
- Projects 页面不再因生产真实 domain/status 枚举导致客户端异常。
- 前端已补齐 `agent`、`platform`、`governance` 三个训练业务域的类型、导航、项目页、来源页、任务页和 dashboard 文案。
- 培训周报时间窗已覆盖训练情报生成时间，`weekly_training` 报告现在有 14 条结构化 evidence references。

## 验证结果

- `cd apps/api && uv run pytest`：64 passed，1 warning。
- `pnpm --dir apps/web lint`：passed。
- `pnpm --dir apps/web build`：passed。
- `pnpm --dir apps/web test`：1 passed。
- `pnpm --dir apps/web test:e2e`：23 passed，5 skipped。
- 生产新增业务域路由检查：`agent/platform/governance` passed。
- 生产真实 API E2E：23 passed，5 skipped。
- 生产 cleanup dry-run：所有可删除 E2E/demo 噪音计数为 0。

机器可读验收文件：`tmp/outputs/training-content-acceptance-20260615.json`。

## 剩余风险

- 生产服务器从 GitHub HTTPS 拉取连续出现 `GnuTLS recv error`，本轮使用 Git bundle 快进部署并保留真实提交 SHA。后续应修复服务器 GitHub 拉取链路。
- 高风险平台采集仍保持为方法与合规边界情报，没有上线真实绕过式采集 adapter。这个边界符合当前 PRD 目标，不应在培训中误讲为已实现平台级自动采集。
