---
name: adr-index
description: Data Intelligence Hub 架构决策记录（ADR）索引。列出所有已记录的架构决策，提供快速查阅入口。当需要了解某项架构选择的历史背景和权衡依据时使用。
---

# Architecture Decision Records — Data Intelligence Hub

> ADR 格式参考 [Michael Nygard's template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

## 索引

| 编号 | 标题 | 状态 | 日期 |
|---|---|---|---|
| [ADR-001](ADR-001-multi-backend-fallback-architecture.md) | 采集器多后端路由架构（Collector-Level Fallback） | 已采纳 | 2026-09-03 |
| [ADR-002](ADR-002-browser-engine-obscura-browser-use.md) | 浏览器引擎选型（Obscura 优先，browser-use 补充） | 已采纳 | 2026-09-03 |
| [ADR-003](ADR-003-osint-upgrade-aliens-eye-robin.md) | OSINT 能力升级（Aliens Eye + Robin，补充而非替换） | 已采纳 | 2026-09-03 |
| [ADR-004](ADR-004-mediacrawler-cookie-strategy.md) | MediaCrawler Cookies 管理策略（手动优先，ego-lite 长效） | 已采纳（阶段一执行中）| 2026-09-03 |
| [ADR-005](ADR-005-implementation-priority-order.md) | 研发优先级排序（2026-09-03 批次） | 已采纳 | 2026-09-03 |

## ADR 状态说明

- **提议中**：已起草，待讨论确认
- **已采纳**：决策已确认并执行
- **已废弃**：决策被新 ADR 替代
- **已拒绝**：经讨论后决定不采纳

## 新增 ADR

新决策按 `ADR-NNN-short-title.md` 命名，放在本目录下。
