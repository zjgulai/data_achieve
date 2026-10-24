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
