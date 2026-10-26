# PG0 S0 Hardening Evidence

日期：2026-10-24
切片：S0（`fix/s0-c0-hardening`）
worktree：`/Users/lute/Project/data_scrapy-c0-s0`
计划：`docs/superpowers/plans/2026-10-24-governed-task-platform-s0-hardening.md`

本文记录 Task 0 建立的工作区、索引与基线事实。它不包含任何业务代码改动。

## 1. 起点与标签

| 项 | 值 |
|---|---|
| start HEAD | `0c11c2b1556f5f274b93cb1cdbf9500b01d7f60c` |
| branch | `fix/s0-c0-hardening` |
| `pg0-baseline-v1` tag object | `48aaccfa5a3689f23f7517cfb88b59c2533805ab` |
| `pg0-baseline-v1` commit | `e227070054914f9cbef8cb5d508e5f4aa73d8dcb` |
| `v1_immutable` | `true` |
| `push` | `forbidden` |

`pg0-baseline-v1` 是 annotated tag（`git cat-file -t pg0-baseline-v1` 返回 `tag`），
tagger 时间为 1792762998 +0800。Task 0 开始前与提交后各断言一次 object 与
`^{commit}` 值，两次一致。本切片不移动、不删除、不覆盖、不推送该标签，
也不创建 `pg0-baseline-v2`。

## 2. 依赖与索引

| 项 | 值 |
|---|---|
| `uv sync --locked --dev` | 成功，exit 0 |
| 锁文件 diff | 无（`uv.lock`、`pyproject.toml` 未变） |
| Python | 3.12.13（`apps/api/.venv`） |
| GitNexus | 1.6.12 |
| 索引 runner | `.gitnexus/run.cjs`（生成后统一使用） |
| `status` | `up-to-date` |
| `runnerIdentityStatus` | `current` |
| `incompleteReasons` | `[]` |
| 基线索引 commit | `0c11c2b1556f5f274b93cb1cdbf9500b01d7f60c` |
| 基线 `contentDrift` | `current`，`coveredFiles=1288` |
| 基线图规模 | 45,266 nodes / 76,596 edges / 988 clusters / 901 flows |
| 提交后 `contentDrift` | `current`，`coveredFiles=1289` |
| 提交后图规模 | 45,277 nodes / 76,607 edges / 988 clusters / 901 flows |

表格上段是在 commit 仍为 `0c11c2b` 时建立的工作树索引，但索引已包含未提交的 S0 plan 文件；它不是纯 Git tree 快照。证据文件当时尚不存在。提交后新增证据文档的 File + 10 个 Section 节点，使图规模 +11 nodes / +11 edges，`coveredFiles` 1288 → 1289。
提交后的确切 HEAD 与最终索引状态记在 Task 0 报告里，本文不复述，
避免「文档内容 → 提交哈希 → 文档内容」的循环。

首次索引用 `bunx gitnexus@latest` 建立，其 `runnerIdentity` 与随后生成的
`.gitnexus/run.cjs` 不同（bunx 临时目录，dependencyRuntime 253 包），
因此首次 `status` 报 `stale` / `stale-or-unknown`。
用 `.gitnexus/run.cjs analyze --index-only` 重建后三者归位：
`up-to-date`、`current`、`[]`。**后续所有 GitNexus 调用一律走 `.gitnexus/run.cjs`。**

索引自带的部分盲区（不是本切片的缺陷，记录以免误读）：

- `vectorSearch` 不可用（`ladybugdb-vector` unavailable），`exactScanLimit=10000`。
- 流程枚举被预算截断：3202 个候选入口点中 3002 个未参与排名，
  1058 个 callee 因 `maxBranching` 被跳过，34 次遍历触顶。
  缺失的 flow 不等于代码路径不存在。
- 496 处属性读写在「本语言之外」定义，按语言推断不断边。

## 3. mypy 基线

命令：`cd apps/api && .venv/bin/python -m mypy src`

| 项 | 值 |
|---|---|
| exit code | `1` |
| summary | `Found 123 errors in 28 files (checked 412 source files)` |
| 完整输出 | `/tmp/s0-mypy-baseline.txt` |

计划预写的 `123 errors / 28 files` 与实测一致。**这是诊断基线，不是待修清单。**
S0 各任务只要求不新增错误，不要求清零。

按错误码分布（共 123 行 `: error:`）：

| 错误码 | 数量 |
|---|---|
| `union-attr` | 54 |
| `no-any-return` | 24 |
| `arg-type` | 16 |
| `unused-ignore` | 6 |
| `no-untyped-def` | 5 |
| `no-untyped-call` | 4 |
| `operator` | 3 |
| `misc` | 2 |
| `import-untyped` | 2 |
| `call-overload` | 2 |
| `return-value` | 1 |
| `list-item` | 1 |
| `attr-defined` | 1 |
| `import-not-found` | 1 |
| `assignment` | 1 |

错误最集中的文件：

| 文件 | 错误数 |
|---|---|
| `collectors/tikhub_social.py` | 23 |
| `services/tiktok_content_ingestion.py` | 16 |
| `services/tiktok_tools.py` | 15 |
| `repositories/tiktok_content.py` | 11 |
| `repositories/tiktok_commerce.py` | 7 |

## 3.1 tracked mypy signature baselines

| 范围 | 签名数 | 实例数 | 文件 | SHA-256 |
|---|---:|---:|---|---|
| `mypy src` | 62 | 123 | `configs/quality/mypy-src-signatures.txt` | `4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e` |
| `mypy src tests` | 498 | 1200 | `configs/quality/mypy-src-tests-signatures.txt` | `9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4` |

表头应为「范围 / 签名数 / 实例数 / 文件 / SHA-256」。`mypy src` 来自 Task 0 原始输出；`mypy src tests` 在 Task 0 fix round 1 以同一代码 HEAD 重新运行。fix round 2 迁移为 multiset v1：每行 `<count>\t<signature>`。后续不得重新取基线；允许计数减少，不允许新签名或任一签名计数增加。

### 3.2 Task 0 计划修订

Task 0 独立审查后，S0 计划在 `1711ac9` 与后续 fix round 2 中补齐：第五个 lineage guard、endpoint 旧字段优先级、mypy multiset CI gate、四个 dedicated suite current-head 断言、两个 PostgreSQL CI job 的 disposable rehearsal、bootstrap 和 v2 reviewed-SHA 标签门禁。业务代码尚未修改。

### 3.3 Task 0 fix round 2：CI 可执行性

Task 0 第二轮复审发现 old mypy step 未替换、unique-set 会漏计数增加、dedicated suites 的 current-head 断言仍陈旧、且计划没有运行 PostgreSQL CI jobs。计划已改为 multiset helper、四 suite current-head 同步、六 guard disposable rehearsal；两份 baseline 已迁移为 multiset v1。业务代码仍未修改，v1 标签不变。

### 3.4 Task 0 fix round 3：执行计划阻塞项收口

第三轮复审（fresh verification against HEAD `04ed2ee`）确认 CI 契约、multiset 格式与 helper 语义、`.bak` 删除、v2 reviewed-SHA 标签门禁均可用，但计划里仍有四条会直接卡死执行的缺陷。**本轮只改计划文本，不改任何业务代码、CI、scripts、tests、tag 或 Docker 配置，也不执行任何 PostgreSQL container rehearsal。**

修正项：

1. **Task 9 lineage 的 034 自相矛盾。** 计划把 lineage 脚本 cleanup 的 `upgrade` 改成 `202610210057`，却让 guard test 的 fake-uv 仍只认 `run alembic upgrade 202607170034`。假 uv 的 dispatch 落到 `*) exit 91`，cleanup 返回 91 而不是保留 pytest 退出码，`test_guard_cleanup_runs_after_success_or_failure_and_preserves_exit_status` 的 `(0,0,0)` 用例必失败。现在明确：fake-uv 的 `alembic heads` 回复（188）、cleanup dispatch arm（196）、`commands[2:4]` 断言（260）三处一起改成 057；真实 postgres lineage suite 里的历史 `upgrade`/`downgrade` 034 目标保持不动。计划新增「两种 034」小节把两者分开，并给出各自的理由。
2. **Executor 的 candidate authorization revision 不能拆。** `scripts/verify-workflow-executor-migration.sh:39` 的 `REVISION = "202607280044"` 生成授权元组的 `revision-<REVISION>` 段，而 `apps/api/tests/postgres_workflow_executor/conftest.py:32` 把同一个值写死，不匹配就直接 `pytest.UsageError`，连不上库。原计划把脚本 `REVISION`、guard test `SAFE_AUTHORIZATION` 和 `WORKFLOW_EXECUTOR_AUTHORIZATION` 一起推到 057，等于让 `workflow-executor` gate 不可能通过。现在：脚本只改 138/139/143 三处 head pin，`REVISION` 留在 `202607280044`；guard unit test 的 head 断言改 057，`SAFE_AUTHORIZATION`（30）与 unsafe-override 替换（141）保持 `revision-202607280044`；Task 10 的 `WORKFLOW_EXECUTOR_AUTHORIZATION` 用 `revision-202607280044`。计划明确写「head pin 是活的 head，`revision-` 段是固定的 candidate label，两者不耦合」。
3. **Task 10 Step 2a 原来不可执行。** 旧文本用三行注释代替 `docker run`，缺镜像、缺 executor/action 的 `POSTGRES_HOST_AUTH_METHOD=trust`（这两个脚本拒收带密码的 URL）、缺 cg/exec/executor/action 的 `POSTGRES_DB`，且清理是后续另一个无 `trap` 的代码块——中途失败会留下容器。现在整段是一个可直接粘贴执行的 shell block：`set -euo pipefail`、`cleanup` 函数、`trap cleanup EXIT INT TERM`、开跑前先删同名旧容器、六个 `docker run`（`postgres:15`，loopback 55443 / 55451-55455）、`wait_pg` 最多 60 秒、六条 env guard 命令、结尾 `cleanup` + `trap -`、最后断言容器与端口都空。并写明任何 gate 未绿即整块非零退出，不得把部分 gate `BLOCKED` 当可交付。
4. **mypy helper 的成功输出没定义。** `Interfaces` 只规定了 exit code，Task 9/10 的 Expected 却断言 `current=1200 baseline=1200 decreased=0`，实现者写别的格式既合规又失败。现在 `Interfaces` 新增 `### Output (exact, stdout)`，固定成功行为 `OK: mypy baseline non-regression current=<current_total> baseline=<baseline_total> decreased=<decreased_total>`，回归前缀 `REGRESSION:`、非法输入前缀 `INVALID:`；Task 9 与 Task 10 的 Expected 使用同一字符串。
5. **head-pin test 的脚本范围改用显式清单。** 原写 `scripts/*.sh`，但目录里有 27 个 shell 脚本，只有六个带 `expected exactly one Alembic head`；按 glob 实现会在 `verify-mvp.sh` 与 `verify-browser-production-metadata-gate.sh` 上失败。现在逐个列出六个脚本路径。

不变项：两份 mypy multiset baseline 未重取、未改写。SHA 仍为 `4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e`（62 签名 / 123 实例）与 `9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4`（498 / 1200）；本轮复核仍为按签名 UTF-8 字节序排序、无重复签名、count 全为正、单个结尾 LF、无 CR、无 NUL、纯 ASCII。§3.1 的基线与 §4 的 unit 基线事实**未修改**。`pg0-baseline-v1` tag object `48aaccfa…` / commit `e2270700…` 未变，`pg0-baseline-v2` 仍不存在。

本轮是**执行计划修订**：`HEAD` 只增加了计划、本文和两份 baseline 文件的文档级改动，没有任何代码行为变化，所以仍不构成 v2 基线。

### 3.5 Task 0 fix round 4：PostgreSQL rehearsal 可执行化

第四轮复审（against HEAD `811bdbc`）逐条复核了 round 3 的四项收口与 minor 项，并确认它们都成立：
fake-uv shim 三处（`188`/`196`/`260`）确实必须同移；executor 的 `REVISION` 与 `conftest.py:32` 的耦合确实存在；
Task 10 Step 2a 的粘贴块逐行满足六个 gate 的契约；mypy helper 的输出可达；六个显式脚本范围正确。
它同时指出两个新缺陷会让「照计划机械执行」直接失败。**本轮仍然只改计划文本与本文**：不改业务代码、
tests、scripts、CI、tag 或 Docker 配置，也不跑任何 PostgreSQL container rehearsal。

修正项：

1. **Task 9 lineage 的二阶修复不可执行（Important）。** 旧文本给的片段是
   `_reset_public_schema(postgres_database_url)` 加 `_run_alembic(postgres_database_url, "upgrade", "202607170034")`，
   然后「再接既有 seed」。两处都会断：`test_materialization.py` 里根本不存在这两个 helper
   （`grep` 为 0，该文件在 `:291-300` 内联了裸 `subprocess.run`）；而 seed 是 fixture，
   `seeded_lineage_graph`（`conftest.py:144`）在测试体之前就已解析，`postgres_database_url`（`:128-132`）
   也已经把 schema reset 并 upgrade 到 head——把 reset 写进测试体等于先抹掉 seed，
   随后的 `raw_records` 插入会撞 `fk_raw_records_workflow_run_tenant`（`202607160033`，`:57-65`）。
   现在改成可执行的 fixture 方案，并写清四步：从 `seeded_lineage_graph` 抽出模块级
   `_seed_lineage_graph(engine: Engine) -> LineageSeed`，原 fixture 退化为一次调用；新增
   `postgres_database_at_034(guarded_database_url)`（复用 conftest 已有的 `reset_public_schema`（`:113-120`）
   与 `run_alembic`（`:100-110`），reset 后 `upgrade 202607170034`）；新增 `postgres_engine_at_034`；
   新增 `seeded_lineage_graph_at_034`（调用共享 helper）。只有
   `test_downgrade_refuses_persisted_v2_lineage`（`test_migration.py:350`）与
   `test_downgrade_refuses_nonempty_materialization_ledger`（`test_materialization.py:276`）改用这三个
   at_034 fixture，其余测试保持 current-head fixture。计划同时明确禁止把 `_reset_public_schema` /
   `_run_alembic` 写进 `test_materialization.py`。
2. **Task 9 两个脚本的行号错位（Important）。** `verify-workflow-action-migration.sh` 的 head 字面量实际在
   `106`（head 检查）/ `107`（错误信息）/ `111`（通过信息），计划原写 `107, 108, 111`——`108` 是 `exit 1`，
   且真正的 head 检查 `106` 被漏掉。`verify-workflow-execution-migration.sh` 实际是 `115, 116, 120`，
   原写 `116, 117, 120`。两行均已改正，并逐个 grep 复核过。

同步项：Task 9 的 `Files` 与 `git add` 清单都加上
`apps/api/tests/postgres_workflow_lineage/conftest.py`（fixture 实际落在这个文件）；
Self-Review 的 Scope consistency 一句改写为明确点名四个 dedicated suite 的 current-head 断言位置，
并说明 lineage 额外新增三个 at_034 fixture 只钉**起始 revision**、不改期望值、历史 migration 字面量保持原样。

本轮复核依据：`grep -n` 逐条比对 `verify-workflow-action-migration.sh`（`106/107/111`）、
`verify-workflow-execution-migration.sh`（`115/116/120`）、`conftest.py` 的 helper 与 fixture 区间
（`100-110`、`113-120`、`128-141`、`144-296`）、两个目标测试的 `def` 与断言行（`350`/`388`、`276`/`308`）；
并逐个 migration 文件确认 at_034 方案引用的每一列都出自 034 及更早的 revision
（`raw_records` 与 `dataset_versions` 的 lineage 列来自 `202607160033`，`workflow_runs`/`step_runs`
的 fixture 与 actor/browser/LLM 列来自 `202606110029`，ledger 表本身来自 `202607170034`），
所以 seed 与 ledger 插入在 034 上成立。

不变项：两份 mypy multiset baseline 未重取、未改写，SHA 仍为
`4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e`（62 签名 / 123 实例）与
`9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4`（498 / 1200）。
`pg0-baseline-v1` tag object `48aaccfa…` / commit `e2270700…` 未变，`pg0-baseline-v2` 仍不存在。
本轮仍是**执行计划修订**，无任何代码行为变化，因此不构成 v2 基线。

### 3.6 Task 0 fix round 5：fixture 起始 revision 落地

第五轮复审（against HEAD `de01a1a`）确认 round 4 的两项修复成立，但指出「切换 fixture 后测试体
仍引用旧局部名」会让照计划执行的人写出一份 NameError 的测试。本轮只改计划与本文：不改业务代码、
tests、scripts、CI、tag 或 Docker 配置，不跑 PostgreSQL，不建容器。

修正项：

1. **Lineage at_034：body identifier 一并改名。** 计划原来在把三个 fixture 换进两个测试后仍写
   「body 内什么都不改」，这是自相矛盾的：`test_migration.py:355` 的 `seed = seeded_lineage_graph`、
   `:356` 的 `with postgres_engine.begin()`、`:379` 的 `_run_alembic` 第一个实参、`:388` 的
   `_revision(...)` 实参、`:390` 的 `_columns(...)` 第一个实参，以及
   `test_materialization.py:281`、`:282`、`:292`、`:306` 全部仍指向旧参数名。现在逐行列出改名：
   `test_migration.py` 用 `seeded_lineage_graph_at_034`、`postgres_engine_at_034`、
   `postgres_database_at_034`；`test_materialization.py` 的 seed、database engine、environment
   `DATABASE_URL` 与 revision 断言四处同样换成 at_034 名。只改 identifier，`"202607160032"` /
   `"202607160033"` 降级目标、两条 `downgrade refused:` 文本与两处 `"202607170034"` 断言字面量
   全部不动。矛盾句已删除。
2. **Workflow Action at_043：新增起始 fixture。** `postgres_workflow_action/test_migration.py:90-109`
   的 `test_revision_043_downgrade_refuses_nonzero_retry_evidence` 从 head 057 库发起
   `downgrade 202607230042`，而 `alembic/env.py` 不设 `transaction_per_migration`，整个 downgrade
   是一笔事务，043 的拒绝会把库回滚到 057，`:109` 永远看不到 `202607270043`。计划改为在
   `apps/api/tests/postgres_workflow_action/conftest.py` 抽共享 helper：模块级 async
   `_seed_action_run(database: PostgresDatabase) -> SeededActionRun`，现有 `seeded_action_run`
   退化为一次 `await` 调用；新增 async `postgres_database_at_043(postgres_database_url)`，先
   `_run_alembic(..., "upgrade", "202607270043")` 再 `create_async_engine` + sessions，退出时
   `engine.dispose()`；新增 `seeded_action_run_at_043(postgres_database_at_043)` 调共享 helper。
   只把该测试的参数换成 `seeded_action_run_at_043`，并把 body 的
   `database = seeded_action_run_at_043.database`、`step_id = seeded_action_run_at_043.step_id`
   同步改名。`alembic_runner` / `sync_database_url` 仍由同一个 `postgres_database_url` 派生，
   其余 action tests 保持 current-head fixtures。
3. **Task 9 清单补 `workflow_action/conftest.py`。** `Files` 与 `git add` 都加上
   `apps/api/tests/postgres_workflow_action/conftest.py`，并把
   `apps/api/tests/postgres_workflow_action/test_migration.py` 列进 `Files` 与被修改 suite 清单。
4. **Scope consistency 补 action 起始 fixture。** Self-Review 明确 `postgres_workflow_action/`
   新增 `postgres_database_at_043`、`seeded_action_run_at_043` 与共享 `_seed_action_run`，
   只钉一个测试的**起始 revision**，期望值与 `"202607270043"` 断言原样保留。

本轮复核依据：逐行读 `apps/api/tests/postgres_workflow_action/conftest.py`
（`_run_alembic` `:134-144`、`postgres_database_url` `:147-151`、`postgres_database` `:169-180`、
`seeded_action_run` `:183-332`、`SeededActionRun` `:58-65`）、
`apps/api/tests/postgres_workflow_action/test_migration.py`（`def` `:90`、赋值 `:95-96`、断言 `:109`）、
`apps/api/tests/postgres_workflow_lineage/test_migration.py:350-392` 与
`apps/api/tests/postgres_workflow_lineage/test_materialization.py:276-308`；
并确认 043 库上 seed 合法：`users`/`workspaces`/`projects` 出自 `202606110002`，
`workflow_plans`/`workflow_versions` 出自 `202606110027`，`workflow_runs`/`step_runs` 出自
`202606110029`，`workflow_runs` 的 status/impact/`missing_fields`/`recovery_action_codes` 出自
`202607230038`，`step_runs.retry_generation` 出自 `202607270043` 本身；044-057 对上述七张表
没有任何加列。

文本门禁（计划文件）：`_seed_action_run`、`postgres_database_at_043`、`seeded_action_run_at_043`
与 `apps/api/tests/postgres_workflow_action/conftest.py` 均出现在 `Files` 与 `git add` 两处；
lineage 两个测试的 body 改名逐行列出；`change nothing inside` 出现 0 次。此前门禁未退化：
executor `revision-202607280044` 三处、lineage fake-uv 057 三处、六条 `docker run -d --name
s0-gate`、`trap cleanup EXIT INT TERM`、mypy helper 精确输出串与两组 `current=`/`baseline=`/
`decreased=` 计数都仍在；`revision-202610210057` 仍为 0 次。代码围栏 168 个，开闭配对。

不变项：§3.1 两份 mypy multiset baseline、§4 unit 基线、§5 七项 RED、§6 不变项的事实
**未修改**。SHA 仍为 `4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e`
（62 签名 / 123 实例）与 `9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4`
（498 / 1200）。`pg0-baseline-v1` tag object `48aaccfa…` / commit `e2270700…` 未变，
`pg0-baseline-v2` 仍不存在。

## 4. unit 基线

命令：`cd apps/api && .venv/bin/python -m pytest tests/unit -q`

| 项 | 值 |
|---|---|
| summary | `2493 passed, 2 skipped, 4 warnings in 69.08s` |
| failed | 0 |
| error | 0 |
| 完整输出 | `/tmp/s0-unit-baseline.txt` |

C0 既有证据曾记录生成物存在时 `2495 passed`；S0 计划没有固定 2495，而是要求冻结当前 clean-worktree 的真实 passed/skip。**实测是 2493 passed + 2 skipped。**

两个 skip 都与生成物缺失有关，不是缺陷：

```
SKIPPED tests/unit/test_catalog_digest_parity.py:132: generated/platform-packages.json 不存在（未纳入版本控制）
SKIPPED tests/unit/test_catalog_reconciliation.py:93: generated/platform-packages.json 不存在（未纳入版本控制）
```

`generated/` 在工作树中**不存在**（`apps/api/generated` 无此目录，
全仓 `-maxdepth 4` 也找不到），且被根 `.gitignore` 第 59 行 `generated/` 忽略。
Task 0 不生成、不移位、不改写任何生成物，因此基线就是「无生成物」状态。
生成物与工作树是否一致由 `scripts/reconcile_catalog.py` 回答，不由本测试回答。

4 条 warning 是 pytest 收集期 `PytestUnhandledThreadExceptionWarning`
（aiosqlite 连接线程在事件循环关闭后回调），不产生 failed。

## 5. 七项 RED 基线

探针：`/tmp/s0-red-probes.py`，用 `apps/api/.venv/bin/python -I` 从 `apps/api` 执行。
输出：`/tmp/s0-red-baseline.json`。探针只读，不修改任何 tracked 文件；
运行前后 `git status --porcelain` 只有未提交的计划文件。

结果：**7/7 复现**（`all_reproduced: true`）。

| # | 探针 | 缺陷 | 当前观测 |
|---|---|---|---|
| 1 | `stop_foreign_cancel` | 项目 A 密钥可取消项目 B run | 返回 `cancelled=true`，`status=cancelled`；foreign run 落库后确实变为 `cancelled` |
| 2 | `balance_foreign_ledger` | 项目 A 密钥可读项目 B 账本 | 返回 B 的 `accrued_usd=19.500000`、`authorized_ceiling_usd=77.500000`、`ledger_entries=1`、`authorization_count=1` |
| 3 | `deep_research_check_foreign_run` | 项目 A 密钥可读项目 B run/records | 返回 `run` + `records`，`records_total=2`，含 B 的记录内容 |
| 4 | `inspect_governance_fields` | `inspect` 泄漏治理字段 | 响应含 `authorization`（含「执行入口当前不校验身份」全文）与 `reachability.block_reason=collection_policy_denied: ...` |
| 5 | `verify_artifact_empty_ledger` | 空 `run_ledger` + `artifact.run_id` 的合法产物被误报 | `verify_artifact` 返回 `data_sha256 不一致：输入 run 或证据集合与记录不符` |
| 6 | `list_capabilities_rss_empty` | `list_capabilities("rss")` 空列表 | 返回 0 行，而 `rss` 平台包含 19 endpoints（`endpoint_count=19`，`len(endpoints)=19`） |
| 7 | `get_playbook_missing_markdown` | `get_playbook("tiktok")` 缺 `markdown` | 键为 `acceptance / capabilities / description / display_name / pitfalls / platform_id / risk_boundaries / steps / summary`，无 `markdown`，也无 `deprecated_fields` |

探针构造方式（便于复现，不是 grep 结论）：

1. stop：内存 SQLite 建全 schema，写入一个 `workspace_id` 相同、
   `project_id` 不同的 `running` run；把 `run_service.async_session_factory`
   指向该内存库，把 `project_api_key_context` 伪装成项目 A 身份，
   allowlist 显式含 `stop`，直接调用 `server_module.stop(context, run_b)`。
2. balance：同上库写入 B 项目的 `Run`、`Authorization`（pass，上限 77.5）
   与 `RunLedgerEntry`（accrued 19.5），allowlist 含 `balance`，
   直接调用 `server_module.balance(context, str(project_b))`。
3. deep_research_check：同工作区跨项目 run，allowlist 含
   `deep_research_check`，直接调用并检查返回是否含 B 的记录。
4. inspect：无身份，直接调用 `discovery_tools.inspect_tool("aliens_eye_advanced")`，
   递归扫描序列化文本。
5. verify_artifact：用 `build_artifact(run_id=...)` 构造合法产物，
   合同 `run_ledger=[]`、`evidences=[]`，再用同一合同与同一 HTML 调 `verify_artifact`。
6. list_capabilities：无身份，直接调用 `server_module.list_capabilities(context, "rss")`，
   并与 `get_platform_package("rss").endpoint_count` 对比。
7. get_playbook：无身份，直接调用 `server_module.get_playbook(context, "tiktok")`，检查键集合。

复现根因（读码确认，供后续任务定位）：

- `stop` / `balance` 工具体只解析参数，不传项目过滤；
  `stop_run` / `get_project_balance` 也没有 `project_id` 形参。
- `deep_research_check` 只比对 `workspace_id`，不比对 `project_id`。
- `inspect_tool` 直接 `model_dump` 内部 `ToolDescriptor`，未经
  `tool_catalog/public.py` 的对外投影。
- `build_artifact` 在合同无 `run_ledger` 时用 `run_id` 兜底，
  而 `verify_artifact` 只从合同取 id，两侧输入集合不同。
- `list_capabilities` 按 `ToolDescriptor.platform` 过滤，而目录按
  `canonical_tool_id` 去重，`public_feed` 只保留 `regulatory` 那一条，
  `rss` 的 19 行被去重掉。全平台计数 `web=63`、`regulatory=1`，
  与平台包的 69 / 4 不符。
- `structured_playbook` 已渲染出 markdown 文本，但返回值未包含它。

## 6. 不变项

| 项 | 值 | 状态 |
|---|---|---|
| `SCHEMA_HEAD` | `202610210057`（`alembic heads` 单头） | 未变 |
| catalog digest | `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c` | 未变 |
| 工具契约版本 | `tool.v1` | 未变 |
| 目录规模 | 70 platforms / 312 package endpoints / 284 tools / 226 executable / 284 canonical | 未变 |
| `migration` | `none`（Task 0 不新增、不修改任何 Alembic revision） | — |
| 业务代码 | 未修改（Task 0 只新增计划与本文） | — |

工具数与端点数在此记为 284 与 312，是 Task 0 实测值，供 Task 6 的
`list_capabilities` 行数基线（rss=19、web=69、regulatory=4、tiktok=39）对照。

## 7. 本切片的写入门禁

- 写入 Markdown 前先跑 GitNexus File impact。本文在建立索引时尚不存在，
  impact 返回 `Target ... not found` / `risk: UNKNOWN`；
  用 `grep -rn` 全文确认只有 S0 计划自身引用该路径，无代码或脚本引用。
- 计划文件 `docs/superpowers/plans/2026-10-24-governed-task-platform-s0-hardening.md`
  同为 UNKNOWN（文件节点无 process/community 归属），文本搜索同样只有自引用。
- 计划与本文都用 `/tmp` Python 脚本 + 同目录临时文件 + `fsync` + `os.replace` 写入，
  不使用 `Edit` / `Write` / heredoc。
- 提交前写字节校验：UTF-8 可解码、NUL 计数为 0、
  原生 `stat` 与 `os.stat()` 与 `len(read_bytes())` 三者相等。
- 提交前跑 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。
- 只提交计划与本文两份文档，提交信息固定
  `docs(plan): add S0 hardening slice`。
- 不 push 分支、不 push 标签、不建 PR、不操作生产、不启动生产 compose。

### 7.1 写入时实际发生了一次 `+4096` 尾洞

按上述协议写入本文后，写脚本自检报 `native_stat = os_stat = read_len = 10883`、
`nul = 0`、`triple_equal = True`。随后用 shell 复核，得到不同的结果：

| 读取方式 | 大小 |
|---|---|
| `/usr/bin/stat -f %z` | 14979 |
| `wc -c` | 14979 |
| `dd` 读到 EOF | 14979（尾部 4096 字节是随机二进制，不是本文内容） |
| Python `open().read()` / `os.read()` / `f.seek(0,2)` | 14979（seek）/ 10883（read） |

即：inode 的 `st_size` 被记成 14979，而按字节顺序读只能读到 10883 字节有效内容，
其后 4096 字节是垃圾。这正是本仓库已知的「`+4096` 尾洞」失效模式。

复现尝试（4 组对照，同一份 10883 字节 payload，分别落在 `/tmp` 与 `docs/ops/`，
其中两组 payload 换成纯 ASCII `B`）：四组全部出现 14979。再写入 5000 / 20000 字节
的纯 ASCII 文件则不出现，说明触发与「约 10.8 KB 的特定内容」相关，
与路径、与是否使用 `mkstemp` 无关。

修复按仓库既定做法执行：先 `rm` 目标文件再 `cp` 干净的 `/tmp` 副本，
以重建 inode。修复后三种度量一致：

```
/usr/bin/stat -f %z   → 10883
wc -c                 → 10883
os.stat().st_size     → 10883
len(open().read())    → 10883
```

修复前后内容不变，`sha256 = 9cac1d639492971878ae13cd9f83bec0dcd3835a2b4411e694ce5b10f460947a`，
`nul = 0`，UTF-8 可解码。计划文件
`docs/superpowers/plans/2026-10-24-governed-task-platform-s0-hardening.md`
度量始终一致（39928 / 39928 / 39928，
`sha256 = afa58269bf0d8beff97f33a404daa352182be19698b317e1824fc8a49e86e022`），
未受影响，也未修改。

**教训**：写脚本内的自检不足以判定文件完好。必须在 `os.replace` 之后
再用**独立进程**复核原生 `stat`，并与 `os.stat` 对比；两者不等即为尾洞。

## 8. 计划订阅中的已知偏差

- 计划 Task 0 Step 2 写的是首次即 `node .gitnexus/run.cjs analyze --index-only`；
  实际该 worktree 初始没有 `.gitnexus/`，必须先 bootstrap。
  已按运行时要求先 `bunx gitnexus@latest analyze --index-only`，
  再用生成的 runner 重建，最终状态与计划 Expected 一致。
- C0 既有证据的 `2495 passed` 来自生成物存在时两条 skip 转 pass；S0 计划未固定该数。clean-worktree 实测 `2493 passed + 2 skipped`，以实测为准。

## 9. Task 8：C0/R0 证据修正与 MCP 兼容窗口（2026-10-25）

本节只修正与补记文档陈述，不改任何代码。对应提交：`docs(ops): correct C0 compatibility and release evidence`。

### 9.1 Task 1-7 修复清单（均已落地并独立审查）

| 任务 | Commit | 修复内容 | 审查结论（一行） |
|---|---|---|---|
| Task 1 | `24b4fb5` | `stop_run` 增加 `project_id` 服务层过滤：跨项目 stop 返回 `run_not_found`，foreign run 保持 running | 独立审查 Approved；RED TypeError → GREEN 6 passed |
| Task 2 | `b2d9db8` | `stop`/`balance` 工具体解析调用方 project_id 并下传过滤；错误词汇 `project_mismatch`/`project_id_invalid` 未改 | 独立审查 Approved（独立 RED 复现；balance 直用 `_parse_project_id` 不包裹，经审查者验证正确）；26 passed |
| Task 3 | `9900dd5` | `deep_research_check` 改服务层 project 过滤并统一 `run_id_invalid`；workspace 预检被替换 | 独立审查 Approved；`research.py` 未动且兼容；49 passed |
| Task 4 | `08edb0b` | `inspect` 改走 `to_public_tool` 公共投影，治理字段（authorization 全文、`reachability.block_reason`）不再出 MCP 面 | 独立审查 Approved（独立 284 工具重扫 0 禁词）；46 passed |
| Task 5 | `e243440` | `build_artifact`/`verify_artifact` 共用 `_resolve_input_ids`（显式 ids > 合同 > run_id 兜底），空 ledger 产物不再误报 | 独立审查 Approved；篡改路径完整；旧四参调用兼容；66 passed |
| Task 6 | `53854bc` | `list_capabilities` 恢复每平台 endpoint 行与 18 个旧字段（rss 19 / web 69 / regulatory 4） | 独立审查 Approved（独立行数复算）；LEGACY_KEYS 冲突断言钉住；catalog digest 不变 |
| Task 7 | `cdc7d23` | `get_playbook` 恢复 `markdown` 别名并附 `deprecated_fields: ["markdown"]` | 独立审查 Approved（值等价断言，非 presence-only）；50 passed |

各任务 mypy 均为 123/28 非回归（multiset 基线未重取）。

### 9.2 MCP 兼容窗口（消费方可见变化）

- `get_playbook`（`cdc7d23`）：恢复 `markdown` 键，值与渲染文本等值；新增 `deprecated_fields: ["markdown"]`。纯恢复，无移除。
- `list_capabilities`（`53854bc`）：恢复每平台 endpoint 行与 18 个旧字段；descriptor 新字段保留。行为恢复，digest 不变。
- `inspect`（`08edb0b`）：**响应形状变化**——`availability_view` 改名 `availability`；`reachability` 不再展开，折叠为
  `execution_kind`/`executable_now`/`permanently_blocked` 三个布尔（`is_alias_view`/`canonical_tool_id`/`executable`
  等投影字段保留）；已在 `08edb0b` commit body 披露。是去治理字段修复的伴随形状变化，不是纯兼容恢复。
- `create_report`：新 surface，无 legacy shape，无兼容窗口。
- S0 未增删任何 MCP 工具：`0c11c2b` 与 `cdc7d23` 均为 39 个 `@_tool`，集合相同。

### 9.3 工具增量事实核对（C0 证据第 2 节勘误依据）

- `f0560ca`（集成基座）36 个 `@_tool`；`get_run`/`list_records`/`stop`/`balance` 已存在
  （`8e2c6ba`、`a8602ed` 引入，均为 `f0560ca` 祖先）。
- 净增（`f0560ca..S0`）：`create_report`、`discover`、`inspect`（随 B5 合并 `94d95b2` 进入 C0）；36 → 39。
- C0 证据第 2 节原「新 MCP 工具」行误把四个既有工具列为新增并漏列 `discover`、`inspect`，已勘误。

### 9.4 分支 compare（真实命令与结果）

命令：`node .gitnexus/run.cjs detect-changes --scope compare --base-ref 0c11c2b --repo .`
结果：变更 11 个文件、97 个符号、受影响流程 0、风险等级 low。输出无 partial/truncated 注记
（按「结果不完整」「列表已截断」检查无匹配）；符号列表仅展示前 15 个（尾注「… 以及另外 82 个」为展示层截断
——计数与 risk 完整，列表不完整）。base 为本切片起点 `0c11c2b`；分支未 push，无分支 CI 证据。

### 9.5 Task 0 点时证据勘误（汇总）

1. 计划从未固定 `2495`：`2495 passed` 只是 C0 在生成物存在时的观测（两条 skip 转 pass）；
   S0 基线为 clean-worktree 实测 `2493 passed, 2 skipped`（§4、§8 已记）。
2. `45,266` nodes 不是纯 `0c11c2b` Git tree 索引：Task 0 建索引时工作树已含未提交的 S0 plan 文件（§2 已记）。
3. mypy 123 行错误码分布已含 `attr-defined`、`import-not-found`、`assignment` 各 1；全表合计 123（§3），
   与 `/tmp/s0-mypy-baseline.txt` 逐码复核一致。
4. Task 0 的「2 个文件、15 个符号」detect 数是点时输出（当时工作树状态），不作为耐久总数；
   索引纳入未提交文档后同口径重跑为 25 个符号。

### 9.6 Task 8 时点复核（2026-10-25）

| 项 | 值 |
|---|---|
| mypy src @ `cdc7d23` | exit 1，`Found 123 errors in 28 files (checked 412 source files)`；multiset 基线 SHA 仍为 `47001690…` / `9df7ee3e…` |
| 触及面 unit @ `cdc7d23` | `test_mcp_run_service.py` + `test_mcp_tools_b5.py` + `test_report_artifacts.py`：83 passed, 1 warning |
| catalog lock SHA-256 | `tool-catalog.lock.json` `1e99add6…`；`platform-packages.lock.json` `59f5976d…`（与 §6 一致） |
| Alembic | `0c11c2b..cdc7d23` 对 `apps/api/alembic` 零 diff；`SCHEMA_HEAD` 维持 `202610210057` |
| v1 tag | object `48aaccfa5a3689f23f7517cfb88b59c2533805ab` / commit `e227070054914f9cbef8cb5d508e5f4aa73d8dcb`，提交前后各断言一次 |
| push / 生产 | 分支未 push、未建标签、未操作生产、未跑生产 compose |

CI 风险拆分（R2a/R2b/R2c/R2d）与 Console build-arg 口径修正记入 `docs/ops/pg0-baseline-c0-2026-10-22.md`
（§2、§7、§8.6）；Ruff 748 条目构成与负控阈值口径修正记入 `docs/ops/pg0-ruff-cleanup-2026-10-22.md`。

## 10. Task 10 最终证据（2026-10-25）

本节是 S0 切片的最终证据段。它汇总 brief Step 1-10 的实测结果，不新增任何代码改动。
reviewed 代码基线为 `cecdf449328fd27664761e740078bcba5e55f0a8`（`/tmp/s0-reviewed-code-baseline.txt`），
本节所在提交是它之后的唯一文档提交。

| 项 | 值 |
|---|---|
| reviewed code baseline | `cecdf449328fd27664761e740078bcba5e55f0a8` |
| branch | `fix/s0-c0-hardening`（无 upstream，未 push） |
| 切片范围 | `0c11c2b..cecdf44`，38 文件，+4461 / −229 |
| 终审 verdict | **READY_WITH_DOCUMENTED_RISKS** |
| `ci_evidence` | `local-rehearsal-only`（分支未 push，无远端 CI run；全部结论为本地实测） |

### 10.1 全部门禁计数（current HEAD `cecdf44`）

| gate | 命令 | 结果 | exit |
|---|---|---|---|
| focused suite（Step 1） | 七个文件的 pytest | `106 passed, 1 warning in 13.68s` | 0 |
| unit 全量 | `.venv/bin/python -m pytest tests/unit -q` | `2557 passed, 1 warning in 73.68s` | 0 |
| ruff | `.venv/bin/ruff check . --no-cache` | `All checks passed!` | 0 |
| mypy（src）multiset | `check_mypy_baseline.py --baseline …/mypy-src-signatures.txt --path src` | `OK: mypy baseline non-regression current=123 baseline=123 decreased=0` | 0 |
| mypy（src+tests）multiset | `check_mypy_baseline.py --baseline …/mypy-src-tests-signatures.txt --path src --path tests` | `OK: mypy baseline non-regression current=1200 baseline=1200 decreased=0` | 0 |
| pytest guard | `check_pytest_baseline.py --path tests/unit` | `2557 passed` 后 `OK: 0 failed。` | 0 |
| file integrity | `python3 scripts/check_file_integrity.py`（repo root） | `file integrity OK (1373 files)` | 0 |
| alembic heads | `.venv/bin/python -m alembic heads` | `202610210057 (head)` | 0 |
| tool catalog 契约 | `scripts/test_tool_catalog.py` | `failures: []`，`executable_count=226`，digest `35ead4d9…` | 0 |
| platform packages 契约 | `scripts/test_platform_packages.py` | 70 平台 / 312 capabilities / 284 unique endpoints / 119 notes，`failures: []` | 0 |

两份 mypy multiset 均无 `REGRESSION:` 行、无 `INVALID:` 行，`decreased=0`。
§3.1 与 §4 的基线事实（62 签名 / 123 实例；498 签名 / 1200 实例）未重取、未改写，
SHA 仍为 `4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e` 与
`9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4`。

`2557 passed` 与 §4 的 `2493 passed + 2 skipped` 不冲突：后者是 Task 0 clean-worktree 无生成物时的基线，
前者是 `generated/platform-packages.json` 与 `docs/playbooks/platforms/` 已生成后两条 skip 转 pass 的结果
（+2）再加上 S0 新增测试（+62）。两者都是真实观测，口径不同。

### 10.2 六个 PostgreSQL guard 复演

本地 disposable rehearsal 两轮：实现轮（`s0-gate-` 前缀）与独立审查轮（`s0-rv-` 前缀）。
两轮都是 `127.0.0.1` 专用端口、无 named volume、无 `--network host`、未用 5432、未用 compose DB，
`trap cleanup EXIT INT TERM` 收尾。

| gate | container（实现 / 审查） | port | user | database | 实现 exit | 审查 exit | suite |
|---|---|---:|---|---|---:|---:|---|
| planner | `s0-gate-planner-pg` / `s0-rv-planner` | 55451 | postgres | `data_scrapy_workflow_plan_phase2_test` | 0 | 0 | 49 passed |
| lineage | `s0-gate-lineage-pg` / `s0-rv-lineage` | 55452 | postgres | `data_scrapy_ci_workflow_lineage_test` | 0 | 0 | 14 passed |
| capability-governance | `s0-gate-cg-pg` / `s0-rv-cg` | 55453 | postgres | `s0_capability_governance_test` | 0 | 0 | 19 passed |
| workflow-execution | `s0-gate-exec-pg` / `s0-rv-exec` | 55454 | postgres | `s0_workflow_execution_test` | **1** | **1** | 13 passed / 1 failed |
| workflow-executor | `s0-gate-executor-pg` / `s0-rv-executor` | 55455 | `s0_executor`（trust） | `s0_workflow_executor_test` | 0 | 0 | 8 passed |
| workflow-action | `s0-gate-action-pg` / `s0-rv-action` | 55443 | `phase_e_test`（trust） | `uix09_phase_e_20260728_workflow_execution_test` | 0 | 0 | 7 passed |

六个脚本都打印了 current-head 通过行（`alembic head check passed: 202610210057`；
lineage 收尾另有 `authorized workflow lineage database cleanup passed: head 202610210057, zero rows`）。
清理后断言：`docker ps -a --filter name=s0-gate` 与 `--filter name=s0-rv` 计数均为 0，
55443 / 55451 / 55452 / 55453 / 55454 / 55455 六个端口均无 LISTEN，无残留 volume。

**workflow-execution 的 1 个失败是 pre-existing，不是本切片回归。** 三条独立证据：

1. `apps/api/tests/postgres_workflow_execution/test_constraints.py` 最后一次改动是 `b339f45`（2026-08-16），
   `git diff 0c11c2b..HEAD` 对它为空。
2. 该文件第 47、60 行仍断言旧名 `ck_workflow_runs_completed_snapshot` / `ck_step_runs_completed_snapshot`；
   实际名由 `202607230038_workflow_run_state_semantics.py` 第 64、86 行改为 `ck_*_state_snapshot`，
   `ck_step_runs_retry_generation` 由 `202607270043_workflow_run_actions.py:88` 新增。
3. 断言原文陈旧，数据库侧符合 head schema；审查者独立复演得到同一失败。

按纪律未修改断言、未标绿，已在 `progress.md` 登记为 blocked defect，归后续切片。
该 gate 不是 CI job。

### 10.3 探针矩阵

**Tenant probes（Step 4，实现轮 12/12 PASS；独立终审轮 26/26 PASS）。**
方法：内存 SQLite（`sqlite+aiosqlite://` + `StaticPool` + `create_all`）、in-process MCP client、
`run_service.async_session_factory` 打补丁、身份经 `runtime.project_api_key_context` 注入。
四组：same-workspace sibling、cross-workspace、global-token、错误文本 foreign-id 泄漏。

| 工具 | same-ws sibling foreign | cross-ws foreign | own | global token |
|---|---|---|---|---|
| `deep_research_check` | `run_not_found`，文本无 foreign project/run id | `run_not_found` | 正常 | 行为不变 |
| `stop` | `run_not_found`，foreign run 保持 `running` | `run_not_found`，状态未变 | `cancelled=True` | 行为不变 |
| `balance` | `project_mismatch`，文本无 foreign project id | `project_mismatch` | 正常 | 行为不变（`accrued_usd=1.250000`） |
| `get_run` / `list_records`（回归） | is_error | is_error | 正常 | 行为不变 |

拒绝语义落在服务层：`run_service.stop_run`、`get_run_detail`、`list_run_records` 都用
`run is None or (project_id is not None and run.project_id != project_id)`；
`Run.project_id` 是 `nullable=False`，比较不会因空值放行。
MCP 传输层把 `ValueError` 包装成 `Error executing tool <name>`，错误码在工具体直调时可见；
两条路径的文本都不含 foreign id。

**Step 5 兼容性扫描（12/12 PASS，独立终审复核一致）。**

| 检查 | 期望 | 实测 |
|---|---|---|
| 目录规模 | 284 | 284 |
| `inspect` 禁词扫描（284 工具逐个） | 0 泄漏 | 0（`inspect_tool` 与 `to_public_tool` 双路径） |
| `describe_capability` 禁词扫描（284 工具） | 0 泄漏 | 0（`describe_capability_public` → `to_public_tool`） |
| endpoint_count>0 ⇒ `list_capabilities` 非空（70 平台） | 无空行平台 | 无 |
| rss / web / regulatory / tiktok 行数 | 19 / 69 / 4 / 39 | 19 / 69 / 4 / 39 |
| `get_playbook.markdown` == REST renderer（70 平台） | 全等 | `mismatch=[]` |
| `deprecated_fields` | `["markdown"]` | 70 平台一致 |
| MCP tool count | 39 | 39（`@_tool` 计数 39） |

禁词集合含 `authorization`、`reachability`、`block_reason`、`policy_block_reason`、
`collection_policy_denied`、`demo_workspace`、`执行入口当前不校验身份`。

### 10.4 CI / evidence 契约复核

| 要求 | 实测 |
|---|---|
| workflow 不存在阻塞式 `uv run mypy` | `grep -rn "uv run mypy" .github/` 计数 0；`mypy` 只出现在 `check_mypy_baseline.py` 那一行 |
| API mypy 用 multiset helper | `Mypy (non-regression)` step 调 `check_mypy_baseline.py --path src --path tests`，本地双基线均 `OK:` 且 exit 0 |
| API pytest/guard 只跑 unit | `uv run pytest tests/unit`；guard `--path tests/unit`；`OK: 0 failed。` |
| `api` job integrity step 从 repo root 跑 | step 显式 `working-directory: .`（`7930c8c`），由 `test_ci_gate_contract.py` 固定 |
| platform-packages job 无 integration 路径 | job 块内 `tests/integration/` 出现 0 次（原 `test_platform_package_routes.py` 行已删） |
| 四个 dedicated suite current-head 断言 057 | `postgres/test_workflow_plan_migration.py:474-475`、`postgres_workflow_lineage/test_migration.py:293-294`、`postgres_capability_governance/test_migration.py:537-538`、`postgres_workflow_execution/test_migration.py:329-330` |
| 历史 revision 未被全局替换 | lineage `upgrade 202607160033` / `202607170034`、`downgrade 202607160033`、action `202607270043`、executor `REVISION = "202607280044"`（`scripts/verify-workflow-executor-migration.sh:39` 与 `tests/postgres_workflow_executor/conftest.py:32`）全部保留 |
| `.bak` 删除 | `scripts/verify-workflow-planner-phase2-migration.sh.bak` 在 `0c11c2b..cecdf44` 中为 `D`；`git ls-files 'scripts/*.bak'` 与 `find scripts -name '*.bak'` 均为空 |

`api` job 只挂 `src+tests` 合并基线，不单独挂 `src` 基线。已核对合并基线是 `src` 基线的超集：
62 个 `src` 签名全部出现在 498 签名基线里，且 count 都不低于 `src` 基线。所以只挂合并基线不丢覆盖。

### 10.5 扫描与 compare

`git status --porcelain` 在全部步骤前后均为空。`0c11c2b..cecdf44` 变更 38 文件。
本分支的 37 个仍存在的变更文件全部 `native stat == os.stat`（delta 0，逐文件比对）。

`detect-changes --scope all` 有两种观测，都是真实结果：

- 本提交之前（clean worktree，本文尚未修改）：返回「未检测到变更」。
- 本提交的自检时点（本文已修改、尚未 commit）：只报 1 个文件，变更符号是本文的 `Section` 节点
  （`PG0 S0 Hardening Evidence` 等），受影响流程落在 882-897 区间，风险 critical。
  该数字随本文内容长度浮动（每次写入后重跑会变），但形态恒定：唯一变更文件是本文，
  唯一变更符号是本文的 Section 节点，流程数与下文 compare 的 897 同源，都是空 id 碰撞伪影。

两种情形都没有 `partial`、没有 `truncated`（用 `partial` / `truncated` / 「结果不完整」/「列表已截断」
四种标记各 grep 一次，命中 0）。提交后工作树恢复 clean，该命令重新返回「未检测到变更」。

`detect-changes --scope compare --base-ref 0c11c2b` 在两种索引状态下给出不同结果：

| 索引状态 | 变更文件 | 变更符号 | 受影响流程 | 风险 |
|---|---:|---:|---:|---|
| 重建前（`cecdf44` 之前 3 个 commit 的增量索引） | 38 | 109 | 0 | low |
| 重建后（`analyze --index-only` 于 `cecdf44`） | 38 | 36 | **897** | **critical** |

重建后的 897 是**图模型的空 id 碰撞，不是代码影响面**。证据：

1. 897 条流程的 changed step 标签全部是文档 Section 名（`9.3 工具增量事实核对（C0 证据第 2 节勘误依据）`、
   `PG0 C0 基线整合证据`），没有一条是代码符号。
2. `Section` 节点在索引里 id 为空：`MATCH (n:Section) WHERE n.filePath = 'docs/ops/pg0-baseline-c0-2026-10-22.md'`
   返回 17 个节点，`size(n.id)` 全为 0。
3. 全库 `MATCH (n) WHERE n.id = ''` 命中 891 个 `Section` 与 8674 个 `Function`。
4. `detect-changes` 用 `WHERE n.id IN $ids` 查流程（`local-backend.js` 的 process 查询）。
   空 id 一旦进入 id 集合，`IN` 会匹配所有空 id 节点，把它们所在流程全部算成受影响。
   实测：`MATCH (n)-[r:CodeRelation {type:'STEP_IN_PROCESS'}]->(p:Process) WHERE n.id IN ['']`
   返回 897 条流程，与本次报告的 897 完全一致。
5. 反向验证：本次真正改动的五个代码符号
   （`stop_run`、`list_capabilities`、`deep_research_check`、`inspect_tool`、`verify_artifact`）
   在 `STEP_IN_PROCESS` 上的流程数为 0 —— 它们不在任何已枚举流程里。

结论：重建后 compare 的 897 / critical 是 `IN ['']` 的全匹配伪影；重建前的 low / 0 反映的是
「改动符号不在已枚举流程内」这一真实事实（§2 已记流程枚举本身被预算截断）。
两种结果都不能读作「897 个流程受这次改动影响」。风险等级以重建前结果为准，并附本条说明。

### 10.6 终审 verdict

独立终审（非实现者），范围 `0c11c2b..cecdf44`，三轴：tenant isolation、compat/contracts、CI/evidence。

- Tenant isolation 轴：26/26 PASS，拒绝语义在服务层，`Run.project_id` 非空。
- Compat / contracts 轴：284 工具脱敏 0 泄漏；`list_capabilities` 行数全等；`get_playbook` 70 平台等值；
  digest `35ead4d9…` 未变；alembic head 057。
- CI / evidence 轴：四项契约正确；六 guard 独立复演与台账逐一相同；blocked defect 未被擅改。

**Verdict: READY_WITH_DOCUMENTED_RISKS。** 所有 Critical / Important 已关闭，只余记录性风险：

| 编号 | 类型 | 内容 | 归属 |
|---|---|---|---|
| DR1 | 本切片引入 | `list_capabilities` 的 rss 19 行只有 19 键，其余 293 行 32 键；rss 行缺 `availability_view`/`cost`/`risk_class`/`run_mode`/`contract_version`/`executable`/`parameters`。根因是 rss 的 endpoint 全叫 `public_feed`，canonical descriptor 归给 `regulatory`，`descriptors.get()` 未命中走 `_public_endpoint_payload` 分支。与 §9.2「descriptor 新字段保留」的陈述对 rss 不成立。测试只钉 tiktok 与旧键子集，故未捕获 | 后续切片 |
| DR2 | 存量 | `list_monitors`（不带 `project_id` 时按工作区）、`enrichment_check`、`workspace_answer` 仍只看工作区，同工作区兄弟项目可见。本分支对 `monitor_service.py`、`enrichment_service.py`、`routes/runs.py` 零 diff | 需单列切片 |
| DR3 | 存量 | integration 套件已不在任何 CI job：33 文件 / 386 测试零覆盖，只有本地给 `DATABASE_URL` 才能跑。`test_platform_package_routes.py` 在无数据库时 1 failed / 1 passed（`Errno 61` 连 5432） | C0 文档 R2b/R2c/R3 已记 |
| DR4 | 存量 | `check_mypy_baseline.py` 在解释器缺 mypy 时 fail-open：mypy 退出 1 被当合法，解析出零诊断，打印 `current=0 … decreased=123` 并 exit 0。CI 用 `uv sync --locked --dev`（含 mypy）故当前有效；建议把 `current=0 且 baseline>0` 改判 `INVALID:` | 后续切片 |
| DR5 | 环境 | `+4096` 尾洞仍在本机写入路径复现，未污染任何提交内容（见 §10.7） | 环境事项 |

### 10.7 `+4096` 尾洞环境事项汇总

本机写入路径仍会出现「inode `st_size` 比可读字节多 4096」。本节汇总全部实测：

| 位置 | 命中数 | 追踪状态 | 内容是否受损 |
|---|---:|---|---|
| `generated/platform-skills/**` | 210（.md） | gitignored（`.gitignore:59` `generated/`） | 生成物，无 git blob 可比 |
| `docs/playbooks/platforms/**` | 70（.md） | gitignored（`.gitignore:60`） | 生成物，无 git blob 可比 |
| `docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md` | 1 | **tracked** | 未受损：`git hash-object` = `git rev-parse HEAD:…` = `02c477a98da4e7d611c536f65272fe4175b525fe`，`0c11c2b..cecdf44` 对它零 diff |
| `.superpowers/sdd/…-s0-hardening/`（主仓） | 17 | gitignored（`.gitignore:64`） | 未跟踪文档 |
| `.superpowers/sdd/` 其它切片（主仓） | 34 | gitignored | 未跟踪文档 |
| 本切片 38 个变更文件 | 0 | tracked | delta 0（逐文件比对） |
| 本文（追加前 35095 字节） | 0 | tracked | `native = os.stat = read = 35095`，NUL 0，UTF-8 可解码 |

扫描口径：对 worktree 内全部 `.md` / `.txt` 文件逐个用 `/usr/bin/stat -f %z` 与 Python `os.stat().st_size` 比对，
共 423 个文件，281 个命中，差值全部为 `+4096`。

**纪律**：写脚本内的自检不足以判定文件完好。落盘后必须用**独立进程**比对原生 `stat` 与 `os.stat`；
两者不等即为尾洞。命中时用「可读字节（`open().read()` 的长度）+ 同目录 tmp + `fsync` + `os.replace`」重建，
再用独立进程复验四方一致（native `stat` / `os.stat` / `read` / `sha256`）。
本文按此协议写入并复核。

### 10.8 受保护对象与标签不变性

| 对象 | 值 | 状态 |
|---|---|---|
| `pg0-baseline-v1` tag object | `48aaccfa5a3689f23f7517cfb88b59c2533805ab` | 未变 |
| `pg0-baseline-v1^{commit}` | `e227070054914f9cbef8cb5d508e5f4aa73d8dcb` | 未变 |
| `pg0-baseline-v1` type | `tag`（annotated） | 未变 |
| 两份 mypy 基线 sha256 | `47001690…` / `9df7ee3e…` | 未变 |
| `scripts/*.bak` | tracked 空、磁盘空 | 已删 |
| push / PR / 生产 / 5432 / compose DB | 未操作 | — |

`pg0-baseline-v2` 在本节写入时仍不存在；它只在本提交之后按 Step 9 创建，
目标为 reviewed 代码基线 `cecdf44`，且只存在于本地。
