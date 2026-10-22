# Governed Task Platform C0 Baseline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **命名说明：** 本计划按 `docs/superpowers/plans/2026-10-22-governed-task-platform-master-plan.md` §1.1 与 §8.2 使用 `feat/pg0-baseline-c0`、`pg0-baseline-v1` 和 `docs/ops/pg0-baseline-c0-2026-10-22.md`。任务文本中的 `p0-baseline-v1` 是同一基线的旧写法。

**Goal:** 在 `feat/pg0-baseline-c0` 上合入 B5，保留已批准设计，验证 056/057 迁移和测试基线，冻结 catalog/image/schema 事实，重建 GitNexus，并创建本地标签 `pg0-baseline-v1`。

**Architecture:** 先做只读预检和契约审查，再用三步合并保留正式 spec。合并后依次验证迁移、后端、前端、镜像和事实快照。代码变更只来自 B5 合并；本计划只手工修改证据文档。最后重建 GitNexus、运行全量变更分析并打本地标签。

**Tech Stack:** Git 2.x、Alembic、PostgreSQL 15/16、Python 3.12、uv、pytest、ruff、mypy、pnpm 9.15.4、Node 22/26、Next.js 16、Docker/Colima、GitNexus 1.6.12。

## Global Constraints

- 执行分支是 `feat/pg0-baseline-c0`，只在隔离 worktree `/Users/lute/Project/data_scrapy-c0` 中创建和执行。不得切换主工作树 `/Users/lute/Project/data_scrapy` 的分支，不得在主工作树执行 `git switch`。
- 主工作树当前分支 `feat/tool-catalog-catalog` 保留全部计划文件及其提交；计划提交由计划编写流程负责。C0 不提交、不暂存、不删除主工作树的计划文件；C0 只把自己的计划文件复制到隔离 worktree 后提交。
- 起始提交是 `f0560ca652a378ddf9ba65e15284a0311769994b`。`feat/p1-identity` 已是它的祖先。
- B5 是 `feat/b5-workbench` @ `94d95b24064a4ce2addafb8c50537f0f29aa755c`，领先 13 个提交。只合入这个分支。
- B4 是 `feat/b4-report-contract` @ `ad968f66570a6738ad122dfef02b1ce4503229d0`，领先 `f0560ca` 5 个提交。**B4 已是 B5 的祖先**：`git merge-base --is-ancestor feat/b4-report-contract feat/b5-workbench` 退出码为 0。合入 B5 即包含 B4 全部历史。不得再单独合并 B4 分支。
- B4 的 `202610210052_claims.py` 与 `202610210053_report_artifacts.py` 占用 052/053，与 main 的 052–055 冲突。B5 已把这两张表重编号为 056/057；B5 树中不再存在 B4 的 052/053 文件。
- 已批准设计是 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md`。其 blob 是 `052c602942ad8dd42fc80cd38d17c95ac20d2bd2`，SHA-256 是 `a648533c80bce42dca385e38347b33b3f666869323f6d34b2e47392a3af1d96f`。合并后必须逐字保留。
- 冻结契约是 `docs/design/【契约冻结】v1-表名-枚举-接口.md`。新增表、列、路径或枚举前，先升级契约并重新批准。
- Alembic 单头是 `202610210057`。迁移链是 `202610210055 → 202610210056 → 202610210057`。
- 056/057 只允许在一次性数据库验证。不得对生产 A、生产 B 或任何共享数据库执行 upgrade 或 downgrade。
- `run_ledger_entries` 只追加。`settle` 为正数实际成本，`release` 为负数修正。本计划不修改账本代码或数据。
- 本计划不手工修改业务代码、测试代码、迁移代码、前端代码。代码变更只来自 B5 合并。
- 后端 unit 基线是 `2492 passed, 2 skipped`。后端 integration 基线是带 `DATABASE_URL` 时 `386 passed`。前端基线是 `220 passed`。
- 有效测试命令中的任何 `failed` 或 `error` 都是门禁失败。没有 `DATABASE_URL` 时只运行 `tests/unit`；不得运行 `tests/integration` 或全量 `pytest`，避免 PostgreSQL 连接错误伪装成代码失败。
- 目录基线是 `catalog_digest=35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c`、`tool_count=284`、`canonical_tool_count=284`、`executable_count=226`。
- 平台包基线是 `platform_count=70`、`capability_count=312`、`unique_endpoint_count=284`。
- GitNexus 合并前分析必须覆盖 staged 合并树。`partial: true` 或 `truncated: true` 不算通过。最终索引必须指向标签提交。
- 每次提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。文档提交应输出“未检测到变更。”。合并提交必须输出非空映射。
- 每个 Run 块默认在 `/Users/lute/Project/data_scrapy-c0` 执行。块内未写 `cd` 时，执行者先进入该 worktree；只有明确写 `cd /Users/lute/Project/data_scrapy` 的步骤才在主工作树执行。
- 只操作隔离 C0 worktree `/Users/lute/Project/data_scrapy-c0`。主工作树只做只读预检。只清理 4 条 prunable 元数据。不得删除或重建其他 13 个有效 worktree；必须保留干净的 detached worktree `/private/tmp/b5wt`。
- 主工作树可能有其他 workflow 生成或暂存的计划文件。C0 不得暂存、删除或提交这些文件。C0 worktree 只暂存本计划与证据文件。
- 只创建本地 annotated tag `pg0-baseline-v1`。不执行 `git push`。推送标签需要人工批准。
- 回滚点：`pg0-baseline-v1` 是只读基线锚点；C0 不创建迁移、不改业务开关。合并失败时 `git merge --abort`；标签创建后不得移动或覆盖。
- 文档写入用 Write/Edit 或 `printf` 重定向。不得使用 heredoc。
- 所有输出用中文技术写作：短句、主动语态、一段一个动作。

---

## File Structure

| 路径 | 动作 | 责任 |
|---|---|---|
| `docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md` | 创建 | 本计划。Task 1 提交。 |
| `docs/ops/pg0-baseline-c0-2026-10-22.md` | 创建并追加 | 执行证据。每个 Task 追加一节。 |
| `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` | 保留 | 不修改。blob 必须是 `052c602942ad8dd42fc80cd38d17c95ac20d2bd2`。 |
| `apps/api/alembic/versions/202610210056_claims.py` | 合并带入 | B5 既有文件。只验证，不编辑。 |
| `apps/api/alembic/versions/202610210057_report_artifacts.py` | 合并带入 | B5 既有文件。只验证，不编辑。 |
| `apps/api/src/data_intelligence_hub/**` | 合并带入 | B5 既有代码。只验证，不编辑。 |
| `apps/api/tests/**` | 合并带入 | B5 既有测试。只运行，不编辑。 |
| `apps/scraper-console/src/**` | 合并带入 | B5 既有页面与测试。只验证，不编辑。 |
| `configs/tool-catalog.lock.json` | 合并带入 | 只读快照。不编辑。 |
| `configs/platform-packages.lock.json` | 合并带入 | 只读快照。不编辑。 |
| `refs/tags/pg0-baseline-v1` | 创建 | Task 8 创建本地 annotated tag。不推送。 |
| `/Users/lute/Project/data_scrapy-c0` | 创建 worktree | Task 1 从 `f0560ca` 创建。C0 全部写操作只在此 worktree。 |

---

### Task 1: 执行前预检与工作树清理

**Files:**
- Create: `docs/ops/pg0-baseline-c0-2026-10-22.md`
- Create/Commit: `docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md`
- Worktree: `/Users/lute/Project/data_scrapy-c0`

**Interfaces:**
- Consumes: `f0560ca`；本计划文件；`feat/p1-identity`、`feat/b5-workbench`、`feat/b4-report-contract`；主工作树当前分支 `feat/tool-catalog-catalog`。
- Produces: 隔离 C0 worktree；证据文档第 1 节；`START_SHA=f0560ca`；`SPEC_BLOB=052c602942ad8dd42fc80cd38d17c95ac20d2bd2`；`B5_TIP=94d95b24064a4ce2addafb8c50537f0f29aa755c`；`B4_TIP=ad968f66570a6738ad122dfef02b1ce4503229d0`；worktree 15 条记录、0 条 prunable。

- [ ] **Step 1: 在主工作树做只读预检，不切换分支**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git branch --show-current
git status --porcelain | grep -vE '^.. docs/superpowers/plans/' && echo "UNEXPECTED" || echo "ONLY_PLAN_CHANGES"
git show-ref --verify --quiet refs/heads/feat/pg0-baseline-c0 && echo "BRANCH_EXISTS" || echo "BRANCH_ABSENT"
```

Expected:

```text
feat/tool-catalog-catalog
ONLY_PLAN_CHANGES
BRANCH_ABSENT
```

主工作树保留已暂存或未跟踪的计划文件。不得在主工作树执行 `git switch`、`git stash`、`git commit` 或 `git add`。`ONLY_PLAN_CHANGES` 表示所有改动都在 `docs/superpowers/plans/`；出现其他路径时停止。`BRANCH_EXISTS` 表示旧分支已存在，停止并先审查旧分支。

- [ ] **Step 2: 从 `f0560ca` 创建隔离 C0 worktree**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git cat-file -e f0560ca652a378ddf9ba65e15284a0311769994b^{commit}
git worktree add /Users/lute/Project/data_scrapy-c0 \
  -b feat/pg0-baseline-c0 f0560ca652a378ddf9ba65e15284a0311769994b
```

Expected: `git cat-file` 退出码 0；`git worktree add` 输出 `Preparing worktree`，退出码 0。分支已存在或路径已存在时停止，不删除旧 worktree。

- [ ] **Step 3: 把本计划复制到 C0 worktree**

Run:

```bash
mkdir -p /Users/lute/Project/data_scrapy-c0/docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md \
  /Users/lute/Project/data_scrapy-c0/docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md
cd /Users/lute/Project/data_scrapy-c0
git status --porcelain
```

Expected:

```text
?? docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md
```

只允许这一行。主工作树的其他计划文件不得复制、暂存或删除。

- [ ] **Step 4: 确认 C0 worktree 的 HEAD 与起始提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor f0560ca HEAD; echo "spec_commit_ancestor=$?"
git diff --name-only f0560ca..HEAD
```

Expected:

```text
feat/pg0-baseline-c0
f0560ca652a378ddf9ba65e15284a0311769994b
spec_commit_ancestor=0
```

`git diff` 输出必须为空。C0 worktree 刚从 `f0560ca` 创建，还没有本计划的提交。出现任何文件就停止。

- [ ] **Step 5: 记录三个分支的提交**

Run:

```bash
git rev-parse feat/p1-identity
git rev-parse feat/b5-workbench
git rev-parse feat/b4-report-contract
```

Expected:

```text
5d07eaf4831403733109b1383efdc166c7727bb0
94d95b24064a4ce2addafb8c50537f0f29aa755c
ad968f66570a6738ad122dfef02b1ce4503229d0
```

任何不同的 SHA 都表示基线已移动。停止，重新审查。

- [ ] **Step 6: 验证 `feat/p1-identity` 分支是 HEAD 的祖先**

Run:

```bash
git merge-base --is-ancestor feat/p1-identity HEAD; echo "p1_ancestor=$?"
```

Expected: `p1_ancestor=0`。

非 0 表示 HEAD 不含 `feat/p1-identity`。停止。

- [ ] **Step 7: 验证 B5 与 B4 的领先提交数**

Run:

```bash
git rev-list --count HEAD..feat/b5-workbench
git rev-list --count feat/b5-workbench..HEAD
git rev-list --count HEAD..feat/b4-report-contract
```

Expected:

```text
13
1
5
```

`B5` 必须是 13。`HEAD` 领先 B5 的 1 个提交是已批准设计 `f0560ca`。`B4` 必须是 5。

- [ ] **Step 8: 确认没有进行中的 Git 操作**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
test ! -e "$(git rev-parse --git-path MERGE_HEAD)" && echo "no_merge"
test ! -d "$(git rev-parse --git-path rebase-merge)" && echo "no_rebase"
```

Expected:

```text
no_merge
no_rebase
```

缺少任一行就停止。

- [ ] **Step 9: 记录 worktree 预检状态**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git worktree list --porcelain | grep -c '^worktree '
git worktree list --porcelain | grep -c '^prunable '
```

Expected:

```text
19
4
```

19 = 原有 18 条记录加新建的 C0 worktree。4 条 prunable 是 `/private/tmp` 下已消失的旧 worktree 元数据；`/private/tmp/b5wt` 是有效、干净、detached 的 B5 worktree，必须保留。

- [ ] **Step 10: 写入失败的清理断言**

Run:

```bash
test "$(git worktree list --porcelain | grep -c '^prunable ')" -eq 0 \
  && echo "PRUNED" \
  || echo "PRUNABLE_PRESENT"
```

Expected: `PRUNABLE_PRESENT`。这一步故意失败，证明 4 条 prunable 元数据仍在。

- [ ] **Step 11: 预演 worktree 清理**

Run:

```bash
git worktree prune --dry-run -v
```

Expected: 4 行，每行以 `Removing worktrees/dih-` 开头。顺序可以不同。

```text
Removing worktrees/dih-baseline-HEAD: gitdir file points to non-existent location
Removing worktrees/dih-main: gitdir file points to non-existent location
Removing worktrees/dih-main-chk: gitdir file points to non-existent location
Removing worktrees/dih-base-session: gitdir file points to non-existent location
```

- [ ] **Step 12: 执行 worktree 清理**

Run:

```bash
git worktree prune -v
```

Expected: 与 Step 11 相同的 4 行。除 `.git/worktrees` 元数据外，不改动跟踪内容。不得清理 C0 worktree 自身。

- [ ] **Step 13: 验证清理结果**

Run:

```bash
test "$(git worktree list --porcelain | grep -c '^prunable ')" -eq 0 && echo "PRUNED"
test "$(git worktree list --porcelain | grep -c '^worktree ')" -eq 15 && echo "WORKTREE_COUNT_OK"
```

Expected:

```text
PRUNED
WORKTREE_COUNT_OK
```

- [ ] **Step 14: 验证其他 worktree 未被删除**

Run:

```bash
git worktree list --porcelain | grep '^worktree ' | sort
```

Expected: 以下 15 条路径，不增不减。

```text
/private/tmp/b5wt
/Users/lute/Project/data_scrapy
/Users/lute/Project/data_scrapy-b4
/Users/lute/Project/data_scrapy-b5
/Users/lute/Project/data_scrapy-c0
/Users/lute/Project/data_scrapy-docs-rescue
/Users/lute/Project/data_scrapy-exa
/Users/lute/Project/data_scrapy-p0
/Users/lute/Project/data_scrapy-p0g
/Users/lute/Project/data_scrapy-p1
/Users/lute/Project/data_scrapy-r1
/Users/lute/Project/data_scrapy-shusuo
/Users/lute/Project/data_scrapy-skill-mcp
/Users/lute/Project/data_scrapy-sp
/Users/lute/Project/data_scrapy-sp41
```

- [ ] **Step 15: 创建证据文档第 1 节**

Run:

```bash
mkdir -p /Users/lute/Project/data_scrapy-c0/docs/ops
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' '# PG0 C0 基线整合证据'
  printf '%s\n' ''
  printf '%s\n' '> 执行日期：2026-10-22'
  printf '%s\n' '> 计划：`docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md`'
  printf '%s\n' '> 状态：进行中'
  printf '%s\n' ''
  printf '%s\n' '## 1. 执行前事实'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '| 起始提交 | `%s` |\n' "$(git rev-parse HEAD)"
  printf '| `feat/p1-identity` 分支 | `feat/p1-identity` @ `%s`；是 HEAD 的祖先 |\n' "$(git rev-parse feat/p1-identity)"
  printf '| B5 分支 | `feat/b5-workbench` @ `%s`；领先 13 个提交 |\n' "$(git rev-parse feat/b5-workbench)"
  printf '| B4 分支 | `feat/b4-report-contract` @ `%s`；领先 5 个提交；不合并 |\n' "$(git rev-parse feat/b4-report-contract)"
  printf '%s\n' '| 已批准设计 blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |'
  printf '%s\n' '| 已批准设计 SHA-256 | `a648533c80bce42dca385e38347b33b3f666869323f6d34b2e47392a3af1d96f` |'
  printf '%s\n' '| Alembic head | `202610210055` |'
  printf '%s\n' '| worktree | 19 条记录；4 条 prunable；清理后 15 条记录、0 条 prunable；保留 `/private/tmp/b5wt`；新增 C0 worktree |'
  printf '%s\n' '| 预检结论 | 通过 |'
} > docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 命令退出码 0。用 Read 打开文件，确认表格内容完整，无 NUL 字节。

- [ ] **Step 16: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。这是文档变更，不映射到符号。出现代码变更就停止。

- [ ] **Step 17: 提交计划与预检证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 建立 C0 基线整合计划与预检证据"
git status --porcelain -uno
git log -1 --oneline
```

Expected: `git status --porcelain -uno` 空输出。`git log` 显示 `docs(ops): 建立 C0 基线整合计划与预检证据`。

---

### Task 2: B5 审查与契约门禁

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 2 节）

**Interfaces:**
- Consumes: 证据第 1 节；`B5_TIP=94d95b2`；`SPEC_BLOB=052c602`。
- Produces: `MERGE_READY=yes`；B5 变更规模；契约审查结论；spec 删除差异的处理规则。

- [ ] **Step 1: 写入失败的合并前断言**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge-base --is-ancestor feat/b5-workbench HEAD; echo "b5_ancestor=$?"
test -f apps/api/tests/unit/test_claims.py && echo "PRESENT" || echo "ABSENT"
```

Expected:

```text
b5_ancestor=1
ABSENT
```

这两行证明 B5 尚未合入。非 1 或 `PRESENT` 表示基线已变化。停止。

- [ ] **Step 2: 列出 B5 的 13 个提交**

Run:

```bash
git log --oneline HEAD..feat/b5-workbench
```

Expected: 13 行，第一行是 `94d95b2 merge(main): 合入 052-055 并重编号 B5 迁移`，第二行是 `b02a3a5 docs(tickets): SP-08 文档同步完成`。行数不是 13 就停止。

- [ ] **Step 3: 记录 B5 变更规模**

Run:

```bash
git diff --shortstat "$(git merge-base HEAD feat/b5-workbench)..feat/b5-workbench"
git show -s --format='%H %P' feat/b5-workbench
```

Expected:

```text
 57 files changed, 17096 insertions(+), 211 deletions(-)
94d95b24064a4ce2addafb8c50537f0f29aa755c e7f51c71d1edec71f0298a4d8225319ba9311ebd b02a3a5a1791d17079f202be5cd7f89542b003ae
```

任何不同的数字或父提交都表示 B5 已移动。停止。

- [ ] **Step 4: 证明 B4 已是 B5 祖先且 B4 的 052/053 文件未进入 B5**

Run:

```bash
git ls-tree --name-only feat/b4-report-contract apps/api/alembic/versions/ \
  | grep -xE 'apps/api/alembic/versions/202610210052_claims\.py|apps/api/alembic/versions/202610210053_report_artifacts\.py'
git merge-base --is-ancestor feat/b4-report-contract feat/b5-workbench; echo "b4_in_b5=$?"
git ls-tree --name-only feat/b5-workbench apps/api/alembic/versions/ \
  | grep -xE 'apps/api/alembic/versions/202610210052_claims\.py|apps/api/alembic/versions/202610210053_report_artifacts\.py' \
  || echo "B4_052_053_ABSENT_IN_B5"
git ls-tree --name-only feat/b5-workbench apps/api/alembic/versions/ \
  | grep -xE 'apps/api/alembic/versions/202610210052_project_api_key_quota\.py|apps/api/alembic/versions/202610210053_monitors\.py'
git rev-list --count feat/b4-report-contract..feat/b5-workbench
```

Expected:

```text
apps/api/alembic/versions/202610210052_claims.py
apps/api/alembic/versions/202610210053_report_artifacts.py
b4_in_b5=0
B4_052_053_ABSENT_IN_B5
apps/api/alembic/versions/202610210052_project_api_key_quota.py
apps/api/alembic/versions/202610210053_monitors.py
34
```

`b4_in_b5` 必须是 0，表示 B4 的全部历史已经在 B5 中。第三条命令只匹配 B4 的两个精确文件名，确认 B5 树里没有 `202610210052_claims.py` 与 `202610210053_report_artifacts.py`。第四条命令列出 B5 主线的 `202610210052_project_api_key_quota.py` 与 `202610210053_monitors.py`，证明前一条断言没有误把同号不同名的文件当作 B4 迁移。第五条命令是 B4 tip 到 B5 tip 的提交数，当前为 34。任一行不同就停止，重新核对分支基线。

- [ ] **Step 5: 验证 B5 迁移重编号**

Run:

```bash
git show feat/b5-workbench:apps/api/alembic/versions/202610210056_claims.py | grep -E '^(revision|down_revision)'
git show feat/b5-workbench:apps/api/alembic/versions/202610210057_report_artifacts.py | grep -E '^(revision|down_revision)'
```

Expected:

```text
revision: str = "202610210056"
down_revision: str | None = "202610210055"
revision: str = "202610210057"
down_revision: str | None = "202610210056"
```

不是这条链就停止。

- [ ] **Step 6: 审查冻结契约覆盖**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
grep -n 'claims\|claim_evidence\|report_artifacts' 'docs/design/【契约冻结】v1-表名-枚举-接口.md'
grep -n 'confirmed · directional · hypothesis · evidence_gap · blocked' 'docs/design/【契约冻结】v1-表名-枚举-接口.md'
git diff --name-only b02a3a5..feat/b5-workbench -- apps/api/src/data_intelligence_hub/api/routes
```

Expected:

- `claims`、`claim_evidence`、`report_artifacts` 出现在表名冻结区。
- claim 五态枚举出现在 §2.6。
- 第三条命令无输出，表示 B5 相对 main 没有新增 REST 路径。

任一表名、路径或枚举未登记时停止。先在 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 登记并重新批准，再继续合并。

- [ ] **Step 7: 审查迁移列与设计映射**

Run:

```bash
git show feat/b5-workbench:apps/api/alembic/versions/202610210056_claims.py | grep -n 'sa.Column'
git show feat/b5-workbench:apps/api/alembic/versions/202610210057_report_artifacts.py | grep -n 'sa.Column'
```

Expected: 056 共有 18 个 `sa.Column`，其中 `claims` 14 个、`claim_evidence` 4 个；057 有 16 个 `sa.Column`。`claims` 的 `owner`、`scope_market`、`scope_window_days`、`scope_sample_n`、`counterevidence_text` 必须能追溯到已批准设计 §5.5 的 Claim 字段。`report_artifacts` 的五个哈希列、`contract_json`、`version`、`report_id` 必须能追溯到设计 §6.1。

发现无法追溯的新列时停止。先升级冻结契约，再继续。

- [ ] **Step 8: 审查新 MCP 工具边界**

Run:

```bash
git show feat/b5-workbench:apps/api/src/data_intelligence_hub/mcp_runtime/server.py \
  | grep -nE '^async def (get_run|list_records|create_report|stop|balance)\b'
```

Expected: 5 行，函数名分别是 `get_run`、`list_records`、`create_report`、`stop`、`balance`。这些是内部工具，不是设计 §7.3 的 8 个客户工具。

门禁：客户工具名只能是 `discover_capabilities`、`estimate_task`、`create_task`、`get_task`、`cancel_task`、`get_delivery_manifest`、`get_evidence`、`collect`。B5 的新工具不得进入客户密钥的 `tools/list`。Task 5 的 `test_mcp_tools_b5.py::test_tool_outside_allowlist_is_rejected` 必须通过。否则停止。

- [ ] **Step 9: 识别并记录 spec 删除差异**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git diff --diff-filter=D --name-only HEAD..feat/b5-workbench -- \
  docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
git cat-file -e feat/b5-workbench:docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md; echo "b5_has_spec=$?"
git log --oneline HEAD..feat/b5-workbench -- docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md | wc -l
```

Expected:

```text
docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
b5_has_spec=128
0
```

解释：`HEAD..B5` 的树差异把 spec 显示为删除，因为 `f0560ca` 只在 HEAD 上，B5 从未包含该路径。B5 也没有任何提交修改该路径。`git merge-base HEAD feat/b5-workbench` 是 `32dd00d`。标准三方合并会保留 HEAD 新增的 spec。

门禁：不得用 `git checkout feat/b5-workbench -- .`、`git merge -X theirs`、`git merge --squash` 或整树覆盖。合并后必须检查 spec blob。

- [ ] **Step 10: 检查 B5 补丁完整性**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git diff --check "$(git merge-base HEAD feat/b5-workbench)..feat/b5-workbench"
```

Expected: 无输出，退出码 0。

- [ ] **Step 11: 追加证据第 2 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 2. B5 审查与契约门禁'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| B5 提交数 | 13 |'
  printf '%s\n' '| B5 tip | `94d95b24064a4ce2addafb8c50537f0f29aa755c` |'
  printf '%s\n' '| B5 tip 父提交 | `e7f51c71d1edec71f0298a4d8225319ba9311ebd`、`b02a3a5a1791d17079f202be5cd7f89542b003ae` |'
  printf '%s\n' '| B5 变更规模 | 57 files changed, 17096 insertions(+), 211 deletions(-) |'
  printf '%s\n' '| B4 关系 | 已是 B5 祖先（`b4_in_b5=0`）；随 B5 历史进入；未单独合并 B4 分支 |'
  printf '%s\n' '| B4 迁移 | B4 树有 `202610210052_claims.py`、`202610210053_report_artifacts.py`；B5 树无这两个精确文件（`B4_052_053_ABSENT_IN_B5`）；B5 主线的 `202610210052_project_api_key_quota.py`、`202610210053_monitors.py` 不是 B4 迁移 |'
  printf '%s\n' '| B4→B5 提交数 | 34（`git rev-list --count feat/b4-report-contract..feat/b5-workbench`） |'
  printf '%s\n' '| B5 迁移 | 056 claims（down 055）、057 report_artifacts（down 056） |'
  printf '%s\n' '| 契约表名 | `claims`、`claim_evidence`、`report_artifacts` 已登记 |'
  printf '%s\n' '| 新增 REST 路径 | 无（相对 `b02a3a5`） |'
  printf '%s\n' '| 新 MCP 工具 | `get_run`、`list_records`、`create_report`、`stop`、`balance`；内部工具 |'
  printf '%s\n' '| spec 删除差异 | `HEAD..B5` 显示 D；B5 无该路径（`cat-file` 128）；合并保留 HEAD blob |'
  printf '%s\n' '| `git diff --check` | 通过 |'
  printf '%s\n' '| MERGE_READY | yes |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。用 Read 确认第 2 节追加在文件末尾。

- [ ] **Step 12: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 13: 提交审查证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录 B5 审查与契约门禁"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 3: 合入 B5 并保留已批准设计

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 3 节）
- Merge: B5 的 57 个文件，包括 056/057 迁移、后端服务和测试、Console 页面和测试

**Interfaces:**
- Consumes: `MERGE_READY=yes`；`B5_TIP=94d95b2`；`SPEC_BLOB=052c602`。
- Produces: 分支 `feat/pg0-baseline-c0`；`MERGE_SHA`；B5 与 B4 都是 HEAD 祖先（B4 通过 B5 历史进入，未单独合并）；spec blob 保持不变。

- [ ] **Step 1: 确认在集成分支**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git branch --show-current
git merge-base --is-ancestor f0560ca HEAD; echo "start_ancestor=$?"
```

Expected:

```text
feat/pg0-baseline-c0
start_ancestor=0
```

不是集成分支就停止。不要切换到其他分支。

- [ ] **Step 2: 再次写入合并前失败断言**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge-base --is-ancestor feat/b5-workbench HEAD; echo "b5_ancestor=$?"
test -f apps/api/tests/unit/test_claims.py && echo "PRESENT" || echo "ABSENT"
```

Expected:

```text
b5_ancestor=1
ABSENT
```

- [ ] **Step 3: 执行不自动提交的合并**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge --no-commit --no-ff feat/b5-workbench
```

Expected: 退出码 0，输出包含：

```text
Automatic merge went well; stopped before committing as requested
```

退出码 1 表示冲突。进入 Step 4。

- [ ] **Step 4: 处理冲突门禁**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git diff --name-only --diff-filter=U
```

Expected: 空输出。正常基线没有冲突。

如果唯一冲突文件是 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md`，执行：

```bash
git checkout --ours -- docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
git add docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
```

如果冲突包含任何其他文件，执行：

```bash
git merge --abort
```

然后停止。不要手工解决业务代码冲突。

- [ ] **Step 5: 验证 index 中的 spec blob**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
test "$(git rev-parse :docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md)" = "052c602942ad8dd42fc80cd38d17c95ac20d2bd2" \
  && echo "SPEC_PRESERVED" \
  || echo "SPEC_MISMATCH"
```

Expected: `SPEC_PRESERVED`。`SPEC_MISMATCH` 时停止。

- [ ] **Step 6: 验证 staged 中没有 spec 删除**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git diff --cached --name-status --diff-filter=D | grep 'docs/superpowers/specs/' \
  && echo "SPEC_DELETED" \
  || echo "NO_SPEC_DELETE"
```

Expected: `NO_SPEC_DELETE`。

- [ ] **Step 7: 验证 B4 作为 B5 祖先随合并进入**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge-base --is-ancestor feat/b4-report-contract MERGE_HEAD; echo "b4_in_merge=$?"
```

Expected: `b4_in_merge=0`。

解释：B4 是 B5 的祖先，所以 B4 的历史必然随 B5 合并进入。这里验证的是“没有单独合并 B4 分支”，不是“树中没有 B4 历史”。B5 已经把 B4 的 052/053 重编号为 056/057，合并树中不会出现 B4 的 052/053 文件。

- [ ] **Step 8: 验证 MERGE_HEAD 与迁移文件**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git rev-parse MERGE_HEAD
test -f apps/api/alembic/versions/202610210056_claims.py && echo "MIGRATION_056_PRESENT"
test -f apps/api/alembic/versions/202610210057_report_artifacts.py && echo "MIGRATION_057_PRESENT"
```

Expected:

```text
94d95b24064a4ce2addafb8c50537f0f29aa755c
MIGRATION_056_PRESENT
MIGRATION_057_PRESENT
```

- [ ] **Step 9: 对 staged 合并树重建 GitNexus 并分析变更**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected:

- `analyze` 退出码 0。
- `detect-changes` 输出非空，包含变更符号或流程。

门禁：输出出现 `"partial": true` 或 `"truncated": true` 时停止。先运行 `node .gitnexus/run.cjs analyze --index-only --force`，再重跑 `detect-changes`。两项都干净后才能提交。

- [ ] **Step 10: 检查 staged 补丁格式**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git diff --cached --check
```

Expected: 无输出，退出码 0。

- [ ] **Step 11: 提交合并**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git commit -m "merge(b5): 合入工作台与报告链，保留已批准设计" \
  -m "B5 @ 94d95b2；B4 已含于 B5 历史，未单独合并。保留已批准设计 blob 052c602。Alembic 单头 202610210057。"
```

Expected: 提交成功。`git log -1 --oneline` 显示 `merge(b5): 合入工作台与报告链，保留已批准设计`。

- [ ] **Step 12: 运行合并后断言**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge-base --is-ancestor feat/b5-workbench HEAD; echo "b5_ancestor=$?"
git merge-base --is-ancestor feat/b4-report-contract HEAD; echo "b4_ancestor=$?"
git rev-list --count HEAD..feat/b5-workbench
git rev-parse HEAD^2
git rev-parse HEAD:docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
test -f apps/api/tests/unit/test_claims.py && echo "B5_TESTS_PRESENT"
```

Expected:

```text
b5_ancestor=0
b4_ancestor=0
0
94d95b24064a4ce2addafb8c50537f0f29aa755c
052c602942ad8dd42fc80cd38d17c95ac20d2bd2
B5_TESTS_PRESENT
```

任何不同的值都停止。不要继续测试。

- [ ] **Step 13: 追加证据第 3 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 3. B5 合并与 spec 保留'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| 集成分支 | `feat/pg0-baseline-c0` |'
  printf '%s\n' '| 合并方式 | `git merge --no-commit --no-ff feat/b5-workbench` |'
  printf '%s\n' '| 冲突文件 | 无 |'
  printf '%s\n' '| index spec blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |'
  printf '%s\n' '| staged spec 删除 | 无 |'
  printf '%s\n' '| B4 关系 | 已是 B5 祖先；未单独合并 B4 分支 |'
  printf '%s\n' '| MERGE_HEAD | `94d95b24064a4ce2addafb8c50537f0f29aa755c` |'
  printf '%s\n' '| GitNexus staged 分析 | 非空；无 partial/truncated |'
  printf '| 合并提交 | `%s` |\n' "$(git rev-parse HEAD)"
  printf '%s\n' '| 合并后 B5 祖先 | 是（`b5_ancestor=0`） |'
  printf '%s\n' '| 合并后 B4 祖先 | 是（`b4_ancestor=0`；B4 是 B5 的祖先） |'
  printf '%s\n' '| 合并后 spec blob | `052c602942ad8dd42fc80cd38d17c95ac20d2bd2` |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。

- [ ] **Step 14: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 非空映射，或 `未检测到变更。`。合并已在 Step 9 分析。出现 `partial: true` 或 `truncated: true` 时停止。

- [ ] **Step 15: 提交合并证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录 B5 合并与 spec 保留"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 4: 验证 056/057 迁移链

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 4 节）
- Runtime: Docker 容器 `c0-pg15`（PostgreSQL 15，临时）

**Interfaces:**
- Consumes: 合并后的 `apps/api/alembic/versions/202610210056_claims.py` 和 `202610210057_report_artifacts.py`。
- Produces: `SCHEMA_HEAD=202610210057`；一次性数据库证据；保留 `c0-pg15` 给 Task 5。

- [ ] **Step 1: 确认 Alembic 单头**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run alembic heads
```

Expected:

```text
202610210057 (head)
```

不是单头就停止。

- [ ] **Step 2: 启动一次性 PostgreSQL 15**

Run:

```bash
colima start
docker version --format '{{.Server.Version}}'
```

Expected: Docker 服务端版本非空。`colima start` 已运行时输出 already running，可以继续。使用 Docker Desktop 时跳过 `colima start`，只要 `docker version` 成功即可。

然后运行：

```bash
docker rm -f c0-pg15 >/dev/null 2>&1 || true
docker run --rm -d --name c0-pg15 \
  -e POSTGRES_USER=c0 \
  -e POSTGRES_PASSWORD=c0 \
  -e POSTGRES_DB=c0_migrations \
  -p 55432:5432 \
  postgres:15
```

Expected: 输出一个容器 ID。

- [ ] **Step 3: 等待数据库就绪**

Run:

```bash
for i in $(seq 1 30); do
  docker exec c0-pg15 pg_isready -U c0 -d c0_migrations >/dev/null 2>&1 && break
  sleep 1
done
docker exec c0-pg15 pg_isready -U c0 -d c0_migrations
```

Expected: 输出包含 `accepting connections`。

- [ ] **Step 4: 写入失败的迁移前断言**

Run:

```bash
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select to_regclass('public.claims') is null;"
```

Expected: `t`。这一步证明 056 尚未执行。

- [ ] **Step 5: 升级到 055**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' \
  uv run alembic upgrade 202610210055
```

Expected: 退出码 0，最后一行是 `Running upgrade ... -> 202610210055`。

- [ ] **Step 6: 验证 055 后 claims 不存在**

Run:

```bash
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select to_regclass('public.claims'), to_regclass('public.report_artifacts');"
```

Expected: `|`（两个空值）。

- [ ] **Step 7: 升级到 057**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' \
  uv run alembic upgrade 202610210057
```

Expected: 退出码 0，包含两行：

```text
Running upgrade 202610210055 -> 202610210056, Create claims and claim_evidence.
Running upgrade 202610210056 -> 202610210057, Create the report_artifacts table.
```

- [ ] **Step 8: 验证三张表和版本号**

Run:

```bash
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select to_regclass('public.claims'), to_regclass('public.claim_evidence'), to_regclass('public.report_artifacts');"
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select version_num from alembic_version;"
```

Expected:

```text
claims|claim_evidence|report_artifacts
202610210057
```

- [ ] **Step 9: 降级到 055 并验证回滚**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' \
  uv run alembic downgrade 202610210055
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select to_regclass('public.claims') is null and to_regclass('public.claim_evidence') is null and to_regclass('public.report_artifacts') is null;"
```

Expected: downgrade 退出码 0；查询输出 `t`。

- [ ] **Step 10: 再升级到 057**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' \
  uv run alembic upgrade 202610210057
psql 'postgresql://c0:c0@127.0.0.1:55432/c0_migrations' -Atc \
  "select version_num from alembic_version;"
```

Expected: `202610210057`。

- [ ] **Step 11: 追加证据第 4 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 4. 056/057 迁移验证'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| 一次性数据库 | Docker `postgres:15`，`127.0.0.1:55432`，库 `c0_migrations` |'
  printf '%s\n' '| 055 前 claims | `null` |'
  printf '%s\n' '| upgrade 055 | 通过 |'
  printf '%s\n' '| upgrade 057 | 通过：055 → 056 → 057 |'
  printf '%s\n' '| 三张表 | `claims`、`claim_evidence`、`report_artifacts` |'
  printf '%s\n' '| alembic_version | `202610210057` |'
  printf '%s\n' '| downgrade 055 | 通过；三张表为 `null` |'
  printf '%s\n' '| 再次 upgrade 057 | 通过 |'
  printf '%s\n' '| SCHEMA_HEAD | `202610210057` |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。容器 `c0-pg15` 保持运行，供 Task 5 使用。

- [ ] **Step 12: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 13: 提交迁移证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录 056/057 迁移验证"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 5: 后端测试、目录与契约基线

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 5 节）
- Runtime: 使用 Task 4 的 `c0-pg15`；结束时删除

**Interfaces:**
- Consumes: `SCHEMA_HEAD=202610210057`；`c0-pg15`；合并后的后端代码和测试。
- Produces: 后端测试基线；`catalog_digest=35ead4d...`；平台包基线 `70/312/284`；清理后的 Docker 环境。

- [ ] **Step 1: 同步锁定的 Python 依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv sync --locked --dev
```

Expected: 退出码 0。锁文件不变。

- [ ] **Step 2: 运行 Ruff**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: 运行 Mypy**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run mypy src tests
```

Expected: 最后一行以 `Success: no issues found in` 开头。

- [ ] **Step 4: 运行后端 unit 测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run pytest tests/unit -q
```

Expected: 最后一行包含：

```text
2492 passed, 2 skipped
```

任何 `failed` 或 `error` 都停止。数量不同也停止，记录差异，不要修改证据表来匹配。

- [ ] **Step 5: 带一次性数据库运行 integration 测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' \
  uv run pytest tests/integration -q
```

Expected: 最后一行包含：

```text
386 passed
```

任何 `failed` 或 `error` 都停止。

- [ ] **Step 6: 记录无数据库时的准确测试范围**

`tests/integration` 需要 PostgreSQL。CI api job 没有 PostgreSQL 服务时，不得运行全量 `pytest`，否则连接错误会伪装成代码失败。本步骤只运行不依赖数据库的 `tests/unit`，作为无数据库探针。

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run pytest tests/unit -q
```

Expected: 最后一行包含：

```text
2492 passed, 2 skipped
```

任何 `failed` 或 `error` 都停止。本步骤不设置不可达 `DATABASE_URL`，也不运行 `tests/integration`。集成测试只在 Step 5 的一次性 PostgreSQL 上运行。

- [ ] **Step 7: 运行回归守卫**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run python ../../scripts/check_pytest_baseline.py --path tests/unit
```

Expected:

```text
OK: 0 failed。
```

- [ ] **Step 8: 验证 Alembic 单头**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run alembic heads
```

Expected:

```text
202610210057 (head)
```

- [ ] **Step 9: 验证工具目录契约**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run python ../../scripts/test_tool_catalog.py
```

Expected: JSON 输出与以下值一致：

```json
{
  "status": "passed",
  "contract_version": "tool.v1",
  "schema_version": "tool-catalog.v1",
  "tool_count": 284,
  "canonical_tool_count": 284,
  "executable_count": 226,
  "catalog_digest": "35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c",
  "failures": []
}
```

- [ ] **Step 10: 重新生成并验证平台包**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run python ../../scripts/generate_platform_packages.py
cd /Users/lute/Project/data_scrapy-c0
git status --porcelain -uno
```

Expected: 生成命令退出码 0；`git status --porcelain -uno` 空输出。生成物必须与锁文件一致。

如果 `git status --porcelain -uno` 有变化，停止。不要提交自动生成的变化。先审查差异。

- [ ] **Step 11: 运行平台包契约测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0/apps/api
uv run python ../../scripts/test_platform_packages.py
```

Expected: 退出码 0。记录输出中的 `platform_count=70`、`capability_count=312`、`unique_endpoint_count=284`。

- [ ] **Step 12: 删除一次性数据库容器**

Run:

```bash
docker rm -f c0-pg15
```

Expected: 输出 `c0-pg15`。

- [ ] **Step 13: 追加证据第 5 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 5. 后端测试与目录基线'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| `uv sync --locked --dev` | 通过 |'
  printf '%s\n' '| Ruff | All checks passed! |'
  printf '%s\n' '| Mypy | Success: no issues found |'
  printf '%s\n' '| `pytest tests/unit` | 2492 passed, 2 skipped |'
  printf '%s\n' '| `pytest tests/integration`（`DATABASE_URL`） | 386 passed |'
  printf '%s\n' '| 无数据库 unit 探针 | 2492 passed, 2 skipped；不运行 `tests/integration`，避免 PostgreSQL 连接错误误判 |'
  printf '%s\n' '| `check_pytest_baseline.py --path tests/unit` | OK: 0 failed。 |'
  printf '%s\n' '| `alembic heads` | `202610210057 (head)` |'
  printf '%s\n' '| 工具目录 | passed；284/284/226；`35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c` |'
  printf '%s\n' '| 平台包 | 生成无 diff；契约测试通过；70/312/284 |'
  printf '%s\n' '| 环境缺口 | CI api job 没有 PostgreSQL 服务；无数据库只运行 tests/unit，integration 必须显式提供 `DATABASE_URL` |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。

- [ ] **Step 14: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 15: 提交后端基线证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录后端测试与目录基线"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 6: 前端测试与生产构建基线

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 6 节）

**Interfaces:**
- Consumes: 合并后的 `apps/scraper-console`。
- Produces: 前端基线 `220 passed`；lint 与 build 通过证据。

- [ ] **Step 1: 安装锁定的前端依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
pnpm install --frozen-lockfile
```

Expected: 退出码 0。锁文件不变。

- [ ] **Step 2: 运行前端单元测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
pnpm -C apps/scraper-console test
```

Expected: 输出包含：

```text
ℹ tests 220
ℹ pass 220
ℹ fail 0
```

- [ ] **Step 3: 运行前端 lint**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
pnpm -C apps/scraper-console lint
```

Expected: 退出码 0。

- [ ] **Step 4: 运行生产构建**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
NEXT_PUBLIC_API_URL=https://scrapy.luteos.com \
  pnpm -C apps/scraper-console build
```

Expected: 退出码 0，输出包含 `Compiled successfully`。路由表包含 `/workbench`、`/reports`、`/capabilities`。

- [ ] **Step 5: 验证构建没有改动跟踪文件**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git status --porcelain -uno
```

Expected: 空输出。`.next` 和缓存必须被忽略。

- [ ] **Step 6: 登记 B5 新页面的浏览器验收交接**

C0 不改 `apps/scraper-console/e2e/**`；该路径归 C14。B5 合入的 `/workbench`、`/reports`、`/capabilities` 三个页面必须在 C14 的 Playwright 套件中验收。C0 只做交接登记，不新增 e2e 文件。

交接判据，C14 必须逐条覆盖：

1. `/workbench`、`/reports`、`/capabilities` 返回 200，页面根节点存在 `<main>`。
2. 三个页面都不出现 5xx 响应。
3. 浏览器控制台没有 `console.error`。
4. `/workbench` 显示五步流程入口；`/reports` 显示报告列表或空态；`/capabilities` 显示能力目录。

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
grep -n 'workbench\|reports\|capabilities' apps/scraper-console/e2e/routes.spec.ts || echo "C14_HANDOFF_REQUIRED"
```

Expected: 三个路由全部已覆盖时输出匹配行；任一缺失时输出 `C14_HANDOFF_REQUIRED`。把实际结果写入证据第 6 节。

风险记录：C0 的合并门禁是后端单元/集成测试、前端单元测试、lint 与生产构建。浏览器验收延期到 C14。若 C14 未在 PG0 验收前执行，风险是 B5 页面在真实 API 下的空态、权限态或控制台错误未被发现。该风险由 C14 的 `e2e/routes.spec.ts` 与 PG0 验收门禁关闭。不得用本步骤替代 C14 的验收。

- [ ] **Step 7: 追加证据第 6 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 6. 前端测试与构建基线'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| `pnpm install --frozen-lockfile` | 通过 |'
  printf '%s\n' '| `pnpm -C apps/scraper-console test` | 220 passed, 0 failed |'
  printf '%s\n' '| `pnpm -C apps/scraper-console lint` | 退出码 0 |'
  printf '%s\n' '| `next build` | Compiled successfully；包含 `/workbench`、`/reports`、`/capabilities` |'
  printf '%s\n' '| 浏览器验收交接 | 延期 C14；四个判据已登记；风险已记录 |'
  printf '%s\n' '| 构建后 `git status` | 空输出 |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。

- [ ] **Step 8: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 9: 提交前端基线证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录前端测试与构建基线"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 7: 构建镜像并冻结 catalog/image/schema 事实

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 7 节）
- Runtime: Docker 镜像 `data_achieve_scrapy_api:c0-${SHA}`、`data_achieve_scrapy_console:c0-${SHA}`

**Interfaces:**
- Consumes: 全部测试通过；合并后的 API 与 Console。
- Produces: `API_IMAGE_ID`；`CONSOLE_IMAGE_ID`；compose 镜像引用列表；锁文件 SHA-256；`CATALOG_DIGEST`；`SCHEMA_HEAD`。

- [ ] **Step 1: 确认 Docker 可用**

Run:

```bash
docker version --format '{{.Server.Version}}'
```

Expected: 服务端版本非空。失败时先运行 `colima start`，再重试。

- [ ] **Step 2: 记录 compose 解析出的镜像引用**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
SCRAPY_POSTGRES_USER=x \
SCRAPY_POSTGRES_PASSWORD=x \
SCRAPY_POSTGRES_DB=x \
SCRAPY_JWT_SECRET=x \
SCRAPY_AUTH_COOKIE_SECURE=true \
docker compose -f configs/deploy/scrapy/docker-compose.yml config --images | sort -u
```

Expected: 以下 9 行。

```text
crivellarodiego/spiderfoot:latest
data_achieve_scrapy-tor
data_achieve_scrapy_api:latest
data_achieve_scrapy_console:latest
data_achieve_scrapy_web:latest
nginx:1.27-alpine
postgres:16
soxoj/maigret:latest
spiderfoot_bridge:latest
```

- [ ] **Step 3: 构建 API 镜像**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
SHA=$(git rev-parse --short HEAD)
docker build \
  -f apps/api/Dockerfile \
  -t "data_achieve_scrapy_api:c0-${SHA}" \
  apps/api
```

Expected: 退出码 0，最后输出包含 `naming to docker.io/library/data_achieve_scrapy_api:c0-${SHA}`。

默认 `INSTALL_PLAYWRIGHT=false`、`INSTALL_OSINT=false`。不安装 Chromium 和 OSINT 系统包。

- [ ] **Step 4: 构建 Console 镜像**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
SHA=$(git rev-parse --short HEAD)
docker build \
  -f apps/scraper-console/Dockerfile \
  -t "data_achieve_scrapy_console:c0-${SHA}" \
  .
```

Expected: 退出码 0，最后输出包含 `naming to docker.io/library/data_achieve_scrapy_console:c0-${SHA}`。

- [ ] **Step 5: 记录镜像 ID**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
SHA=$(git rev-parse --short HEAD)
docker image inspect --format '{{.Id}}' "data_achieve_scrapy_api:c0-${SHA}"
docker image inspect --format '{{.Id}}' "data_achieve_scrapy_console:c0-${SHA}"
```

Expected: 两行，每行以 `sha256:` 开头，后接 64 位十六进制。

- [ ] **Step 6: 记录 catalog 与 schema 事实**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git rev-parse HEAD
cat configs/tool-catalog.lock.json
cat configs/platform-packages.lock.json
shasum -a 256 configs/tool-catalog.lock.json configs/platform-packages.lock.json
cd apps/api
uv run alembic heads
```

Expected:

```json
{
  "schema_version": "tool-catalog.v1",
  "contract_version": "tool.v1",
  "catalog_digest": "35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c",
  "tool_count": 284,
  "canonical_tool_count": 284,
  "executable_count": 226
}
```

```json
{
  "schema_version": "platform-packages.v1",
  "catalog_digest": "35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c",
  "platform_count": 70,
  "capability_count": 312,
  "unique_endpoint_count": 284
}
```

Alembic 输出：

```text
202610210057 (head)
```

- [ ] **Step 7: 追加证据第 7 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
SHA=$(git rev-parse --short HEAD)
API_ID=$(docker image inspect --format '{{.Id}}' "data_achieve_scrapy_api:c0-${SHA}")
CONSOLE_ID=$(docker image inspect --format '{{.Id}}' "data_achieve_scrapy_console:c0-${SHA}")
TOOL_HASH=$(shasum -a 256 configs/tool-catalog.lock.json | cut -d' ' -f1)
PLATFORM_HASH=$(shasum -a 256 configs/platform-packages.lock.json | cut -d' ' -f1)
{
  printf '%s\n' ''
  printf '%s\n' '## 7. catalog/image/schema 事实快照'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '| 事实提交 | `%s` |\n' "$(git rev-parse HEAD)"
  printf '| API 镜像 | `data_achieve_scrapy_api:c0-%s` |\n' "$SHA"
  printf '| API 镜像 ID | `%s` |\n' "$API_ID"
  printf '| Console 镜像 | `data_achieve_scrapy_console:c0-%s` |\n' "$SHA"
  printf '| Console 镜像 ID | `%s` |\n' "$CONSOLE_ID"
  printf '%s\n' '| compose 镜像引用 | 9 个：api、console、web、postgres:16、nginx:1.27-alpine、spiderfoot、spiderfoot_bridge、maigret、tor |'
  printf '%s\n' '| `catalog_digest` | `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c` |'
  printf '%s\n' '| 工具计数 | 284 / 284 / 226（tool / canonical / executable） |'
  printf '%s\n' '| 平台包计数 | 70 / 312 / 284（platform / capability / unique endpoint） |'
  printf '| `tool-catalog.lock.json` SHA-256 | `%s` |\n' "$TOOL_HASH"
  printf '| `platform-packages.lock.json` SHA-256 | `%s` |\n' "$PLATFORM_HASH"
  printf '%s\n' '| `SCHEMA_HEAD` | `202610210057` |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。两个镜像 ID 必须是 `sha256:` 加 64 位十六进制。任何空值都停止。

- [ ] **Step 8: 提交前运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 9: 提交事实快照**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 冻结 C0 catalog/image/schema 事实"
git status --porcelain -uno
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 8: GitNexus 重建、最终门禁与本地标签

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`（追加第 8 节）
- Create: annotated tag `pg0-baseline-v1`

**Interfaces:**
- Consumes: Task 7 的事实提交；全部测试与迁移证据。
- Produces: fresh GitNexus 索引；最终变更分析；本地 tag `pg0-baseline-v1`；最终证据提交。

- [ ] **Step 1: 重建 GitNexus 索引**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs analyze --index-only
```

Expected: 退出码 0。

- [ ] **Step 2: 验证索引状态**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs status --json
```

Expected:

- `index.commit` 等于 `git rev-parse HEAD`。
- `status` 是 `fresh`。
- `incompleteReasons` 是空数组。

状态是 `stale` 时重跑 Step 1。仍是 `stale` 就停止。

- [ ] **Step 3: 运行最终变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。当前工作树只有即将追加的文档。

门禁：出现 `"partial": true` 或 `"truncated": true` 时停止。先运行 `node .gitnexus/run.cjs analyze --index-only --force`，再重跑本步。

- [ ] **Step 4: 创建本地 annotated tag**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git tag -a pg0-baseline-v1 \
  -m "PG0 baseline v1: C0 integration at $(git rev-parse --short HEAD); B5 94d95b2 merged; spec 052c602 preserved; schema 202610210057"
git tag -n99 pg0-baseline-v1
git rev-parse pg0-baseline-v1^{commit}
git rev-parse HEAD
```

Expected:

- `git tag -n99` 输出 `pg0-baseline-v1` 和上述标签消息。
- `git rev-parse pg0-baseline-v1^{commit}` 等于 `git rev-parse HEAD`。

标签已存在时停止。不要移动或强制覆盖标签。

- [ ] **Step 5: 确认只有本地标签**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git for-each-ref --format='%(refname) %(objectname)' refs/tags/pg0-baseline-v1
git status --short --branch
```

Expected:

- `git for-each-ref` 显示 `refs/tags/pg0-baseline-v1` 和一个 tag 对象 SHA。
- `git status` 显示当前分支。

不要执行 `git push origin pg0-baseline-v1`。推送需要人工批准。不要运行会访问远端的标签检查。

- [ ] **Step 6: 追加证据第 8 节**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
{
  printf '%s\n' ''
  printf '%s\n' '## 8. GitNexus 重建与 pg0-baseline-v1'
  printf '%s\n' ''
  printf '%s\n' '| 项目 | 值 |'
  printf '%s\n' '|---|---|'
  printf '%s\n' '| GitNexus analyze | 退出码 0 |'
  printf '| GitNexus index.commit | `%s` |\n' "$(git rev-parse HEAD)"
  printf '%s\n' '| GitNexus status | `fresh`；`incompleteReasons=[]` |'
  printf '%s\n' '| 最终 `detect-changes` | 未检测到变更（仅文档） |'
  printf '%s\n' '| `partial` / `truncated` | 未出现 / 未出现 |'
  printf '| 标签 | `pg0-baseline-v1` → `%s` |\n' "$(git rev-parse pg0-baseline-v1^{commit})"
  printf '%s\n' '| 远端标签 | 未推送；等待人工批准 |'
} >> docs/ops/pg0-baseline-c0-2026-10-22.md
```

Expected: 退出码 0。

- [ ] **Step 7: 提交最终证据**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/ops/pg0-baseline-c0-2026-10-22.md
git commit -m "docs(ops): 记录 GitNexus 重建与 pg0-baseline-v1 标签"
git status --porcelain -uno
git log -3 --oneline
```

Expected:

- `detect-changes` 输出 `未检测到变更。`。
- 提交成功。
- `git status --porcelain -uno` 空输出。
- 日志包含 `docs(ops): 记录 GitNexus 重建与 pg0-baseline-v1 标签`。

- [ ] **Step 8: 最终验收**

Run:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge-base --is-ancestor feat/b5-workbench HEAD; echo "b5_ancestor=$?"
git merge-base --is-ancestor feat/b4-report-contract HEAD; echo "b4_ancestor=$?"
git rev-parse HEAD:docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md
git rev-parse --verify pg0-baseline-v1^{commit} >/dev/null
test "$(git rev-parse pg0-baseline-v1^{commit})" = "$(git rev-parse HEAD^)" && echo "TAG_ON_CODE_BASELINE"
git status --porcelain -uno
```

Expected:

```text
b5_ancestor=0
b4_ancestor=0
052c602942ad8dd42fc80cd38d17c95ac20d2bd2
TAG_ON_CODE_BASELINE
```

`git status` 空输出。标签指向 Task 7 的代码与事实提交。Task 8 的证据提交在标签之后，只改文档。

---

## Self-Review

- 规格覆盖：主工作树只读预检、隔离 C0 worktree、清理 prunable、验证 P1 祖先、审查并合入 B5、确认 B4 已是 B5 祖先、迁移 056/057、后端/前端测试基线、catalog/image/schema 快照、GitNexus 重建、`pg0-baseline-v1` 标签、B5 页面浏览器交接均有对应任务。
- B5 删除正式 spec 的差异：Task 2 记录树差异，Task 3 用标准三方合并保留 HEAD blob，并给出冲突门禁和 blob 断言。
- 占位符扫描已通过；没有未完成标记或未定义函数。动态值由命令替换写入证据。`SCRAPY_JWT_SECRET` 使用固定假值 `x`，不是真实密钥。无数据库探针只运行 `tests/unit`，不运行 `tests/integration`。
- 类型与名称一致性：`claims`、`claim_evidence`、`report_artifacts`、`202610210056`、`202610210057`、`pg0-baseline-v1` 在各任务中一致。
- 项目规则：不手工改业务代码；新表列路径枚举先过冻结契约；账本 settle 正、release 负；提交前运行 GitNexus 变更分析。

---

## 审查摘要（2026-10-22 修订）

| 审查项 | 级别 | 处理 | 落点 |
|---|---|---:|---|
| B4 祖先事实写反 | P0 | B4 已是 B5 祖先。Task 2 改为断言 `b4_in_b5=0` 与 `B4_052_053_ABSENT_IN_B5`；Task 3/8 改为 `b4_ancestor=0`；合并信息改为“B4 已含于 B5 历史”。 | Global、Task 2 Step 4、Task 3 Step 7/12、Task 8 Step 8、证据表、Self-Review |
| 缺浏览器验收 | P1 | 新增 Task 6 Step 6：登记 `/workbench`、`/reports`、`/capabilities` 的 C14 Playwright 交接，四个判据与风险记录；不改 e2e 文件。 | Task 6 Step 6、证据第 6 节 |
| JWT 固定假值易误读 | P2 | `SCRAPY_JWT_SECRET=x`。 | Task 7 Step 2 |
| 无数据库探针误判 | P1 | 删除不可达 `DATABASE_URL` 的全量 `pytest`；改为只运行 `tests/unit`，并断言 2492 passed、2 skipped。 | Task 5 Step 6、证据第 5 节、Self-Review |
| 主工作树脏索引无法原地切换 | P0 | Task 1 不再 `git switch` 主工作树；从 `f0560ca` 创建隔离 worktree `/Users/lute/Project/data_scrapy-c0`，复制本计划后提交；全部 C0 命令改在该 worktree 执行。 | Global、File Structure、Task 1、审查摘要 |
| B4/B5 迁移与提交数断言不准 | P0 | 用精确文件名 `202610210052_claims.py` 与 `202610210053_report_artifacts.py`；补列 B5 主线同号文件；B4→B5 提交数改为 34。 | Task 2 Step 4、审查摘要 |
| B5 spec 保留 | 保持 | 原样保留：Task 2 记录删除差异，Task 3 断言 blob `052c602` 与 `NO_SPEC_DELETE`。 | Task 2/3 |

自检结论：占位符扫描已通过。C0 只在隔离 worktree `/Users/lute/Project/data_scrapy-c0` 操作，只创建本地标签，不改业务代码；主工作树只做只读预检。
