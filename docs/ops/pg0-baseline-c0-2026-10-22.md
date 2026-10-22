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

## 2. B5 审查与契约门禁

| 项目 | 值 |
|---|---|
| B5 提交数 | 13 |
| B5 tip | `94d95b24064a4ce2addafb8c50537f0f29aa755c` |
| B5 tip 父提交 | `e7f51c71d1edec71f0298a4d8225319ba9311ebd`、`b02a3a5a1791d17079f202be5cd7f89542b003ae` |
| B5 变更规模 | 57 files changed, 17096 insertions(+), 211 deletions(-) |
| B4 关系 | 已是 B5 祖先（`b4_in_b5=0`）；随 B5 历史进入；未单独合并 B4 分支 |
| B4 迁移 | B4 树有 `202610210052_claims.py`、`202610210053_report_artifacts.py`；B5 树无这两个精确文件；B5 主线的 `202610210052_project_api_key_quota.py`、`202610210053_monitors.py` 不是 B4 迁移 |
| B4→B5 提交数 | 34 |
| B5 迁移 | 056 claims（down 055）、057 report_artifacts（down 056） |
| 迁移列数 | 056：18（claims 14、claim_evidence 4）；057：16 |
| 契约表名 | `claims`、`claim_evidence`、`report_artifacts` 已登记 |
| Claim 五态 | `confirmed · directional · hypothesis · evidence_gap · blocked` 已登记 |
| 新增 REST 路径 | 无（相对 `b02a3a5`） |
| 新 MCP 工具 | `get_run`、`list_records`、`create_report`、`stop`、`balance`；仅内部工具 |
| spec 删除差异 | 仅对 spec 路径检查时 `HEAD..B5` 显示 D；B5 无该路径（`cat-file` 128）；B5 历史没有修改该路径 |
| `git diff --check` | 通过 |
| MERGE_READY | yes |
