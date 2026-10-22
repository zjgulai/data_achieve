# PG0 C0 基线整合证据

> 执行日期：2026-10-22
> 计划：`docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md`
> 状态：进行中

## 1. 执行前事实

| 项目 | 值 |
|---|---|
| 起始提交 | `f0560ca652a378ddf9ba65e15284a0311769994b` |
| `feat/p1-identity` 分支 | `feat/p1-identity` @ `5d07eaf4831403733109b1383efdc166c7727bb0`；是 HEAD 的祖先 |
| B5 分支 | `feat/b5-workbench` @ `94d95b24064a4ce2addafb8c50537f0f29aa755c`；领先 13 个提交 |
| B4 分支 | `feat/b4-report-contract` @ `ad968f66570a6738ad122dfef02b1ce4503229d0`；领先 5 个提交；不单独合并 |
| 已批准设计 blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |
| 已批准设计 SHA-256 | `a648533c80bce42dca385e38347b33b3f666869323f6d34b2e47392a3af1d96f` |
| Alembic head | `202610210055` |
| worktree | 19 条项目记录；4 条 prunable；清理后 15 条项目记录、0 条 prunable；保留 `/private/tmp/b5wt`；新增 C0 worktree |
| RED 清理断言 | `PRUNABLE_PRESENT`；4 条 `dih-*` 元数据待清理 |
| GREEN 清理断言 | `PRUNED`；`WORKTREE_COUNT_OK` |
| 预检结论 | 通过 |
