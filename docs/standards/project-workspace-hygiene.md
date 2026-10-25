---
name: project-workspace-hygiene
description: 本仓库的目录、工作树、分支与任务管理规范。新增并行工作、合并分支或清理工作区时先读这份。
---

# 项目工作区与分支管理规范

## 1. 要解决的问题

本仓库曾同时存在 28 个工作树、30 个本地分支，占用约 47 G。其中大多数是并行开发留下的副本。
`git branch --merged` 看不出问题：subagent 的提交经过 rebase 后 SHA 变了，分支显示「未合并」，
但补丁内容早已在 `main` 里。用错了判据就会误删工作，或者永远不敢删。

真正有效的判据是 `git cherry`：`-` 前缀表示补丁已在 `main`，`+` 前缀表示真实新增。

## 2. 目录约定

```
/Users/lute/Project/data_scrapy/            # 唯一主干工作区，检出 main
├── .worktrees/<短名>/                       # 所有并行工作树，已进 .gitignore
├── docs/standards/project-workspace-hygiene.md
└── scripts/check_workspace_hygiene.sh
```

规则：

1. 主干只有一处：`/Users/lute/Project/data_scrapy`。
2. 并行工作树一律放在 `.worktrees/` 下，不再在 `/Users/lute/Project/` 平级新建 `data_scrapy-*` 目录。
3. 临时沙箱放 `/private/tmp/`，用完即删；巡检脚本对 `/private/tmp/` 只是提示，不算违规。
4. 新增工作树：

   ```bash
   git worktree add .worktrees/<短名> -b <分支名> main
   ```

5. 已有的外部工作树迁入：

   ```bash
   cd /Users/lute/Project/data_scrapy
   git worktree move /Users/lute/Project/data_scrapy-<旧名> .worktrees/<短名>
   ```

## 3. 分支生命周期

1. `main` 是唯一长期分支。其余分支短命，按工作项开、按合并关。
2. 命名：`feat/<ticket>-<slug>`、`fix/<ticket>-<slug>`。slug 用英文短横线。
3. 合并方式用 `--no-ff`，保留工作项边界。
4. 合并后立刻删除本地分支与工作树，不留「以后再清」。
5. 删除判据按顺序：

   ```bash
   git merge-base --is-ancestor <分支> main   # 退出 0 表示完全合并
   git cherry main <分支> | grep -c '^+'      # 输出 0 表示无真实新增
   ```

   任一成立即可删。`git branch -d` 还会比对远端跟踪分支；本地合并尚未推送时会拒绝，
   此时先推送，或用 `-D`（前提是上面两条已取证）。

## 4. 工作树规范

1. 每个工作树同一时刻只对应一条分支。
2. 工作树内不得留着未提交改动过夜。要暂停就提交到分支，或写进 ticket 备注。
3. 长期不动的分支（超过两周无提交）要么合并，要么归档为 `archive/<名称>` 标签后删除分支。
4. subagent 的临时工作树用完即弃，不留分支。它们的提交若有价值，先摘到正式分支再丢弃。

## 5. 任务管理

单一事实源是 `SP-Agent-TODO` 飞书多维表格，仓库内镜像为 `docs/tickets/SP-Agent-TODO-<日期>.json`。

1. 一张 ticket 对应一个分支、最多一个工作树。
2. 分支名带上 ticket 编号，`git log` 就能反查工作项。
3. 每日闭环：读 ticket → 采集证据 → 更新表格状态 → 派发下一条。
4. 状态只在有证据时推进。「脚本写完」不等于「已完成」，至少要有测试输出或生产验收记录。
5. ticket 收口时同时做三件事：合并分支、删除工作树、更新表格。

## 6. 巡检

```bash
bash scripts/check_workspace_hygiene.sh          # 人读
bash scripts/check_workspace_hygiene.sh --quiet   # 只报异常
```

脚本只读，输出四类结论：

| 类别 | 含义 | 处置 |
| --- | --- | --- |
| 仍持有未发布工作的分支 | `git cherry` 有 `+` | 继续做，或合并 |
| 补丁已全部在 main | `git cherry` 全 `-` | 删工作树与分支 |
| 工作树不在 `.worktrees/` | 位置不合规 | `git worktree move` |
| 工作树有未提交改动 | 可能丢东西 | 先提交或记录 |

退出码 1 只在「位置不合规」或「有未提交改动」时出现，其余是建议。

`.claude/worktrees/` 下的 subagent 临时工作树由工具自动回收，脚本不纳入统计。

节奏：`.githooks/post-merge` 每次合并后自动跑一次 `--quiet`；每周再跑一次全量。

## 7. 2026-10-25 首次执行记录

清理前：28 个工作树、30 个本地分支、约 47 G。
清理后：6 个工作树、8 个本地分支、约 11.8 G。

处置明细：

1. 删除 13 个 subagent 工作树与对应分支。它们的 `git cherry` 真实新增全为 0。
2. 删除 19 条完全合并的分支，包括 `rescue/`、`deploy/`、`peer-`、`tmp/`、`wip/outbound-` 等历史遗留。
3. 删除 `feat/pg0-baseline-c0` 与 `feat/pg0-ruff-cleanup`：两者都是 `fix/s0-c0-hardening` 的祖先，工作已包含在内。
4. 合并 `feat/sp41-catalog-guard` 修复 main 的 CI：`ci.yml` 引用了 `scripts/check_catalog_locks.py`，而该脚本原本只在特性分支上，`platform-packages` job 必定失败。
5. 把 5 个保留的工作树用 `git worktree move` 迁入 `.worktrees/`。迁移后 `/Users/lute/Project/` 下不再有 `data_scrapy-*` 平级目录。

保留的 5 条分支与理由：

| 分支 | 真实新增提交 | 说明 |
| --- | --- | --- |
| `fix/s0-c0-hardening` | 53 | S0 加固，含 MCP 项目隔离修复 |
| `fix/n1-review-findings` | 17 | N1 授权评审修复 |
| `feat/shusuo-group-mention-gate` | 11 | 群聊 @ 门禁 |
| `feat/b5-workbench` | 10 | 洞察工作台 B5 |
| `feat/b4-report-contract` | 4 | 报告渲染器 |

6. 删除两条存档分支，留档备查：

   | 分支 | 删除前 HEAD | 日期 | 说明 |
   | --- | --- | --- | --- |
   | `codex/social-api-private-matrix-20260708` | `b2e264a` | 2026-10-09 | 旧 TikTok CDO agent，已被后续实现取代 |
   | `wip/snapshot-20261020` | `d17a76e` | 2026-10-20 | 同步前的整仓快照，无独立价值 |

   两者各只有 1 个相对 main 的真实新增提交，需要时可用
   `git show <sha>` 或 `git reflog` 找回。

## 8. 后续动作

1. 巡检脚本不接入 CI。GitHub Actions 的 checkout 只有单个工作树，巡检必然全绿，
   那样的绿灯证明不了任何事。工作树堆积只发生在本地。
2. 改为本地拦截：`.githooks/post-merge` 在每次合并后自动跑一次 `--quiet` 巡检，
   只在有问题时输出，且永远不阻断合并。
3. 仓库内的 hook 不会自动生效，需要每台机器执行一次：

   ```bash
   git config core.hooksPath .githooks
   ```

   该配置之前一直缺失，导致 `.githooks/pre-commit` 的文件完整性检查也从未运行。
4. 每次合并分支后跑一次巡检，避免再次堆积。
