# Governed Task Platform R0 Ruff Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除 C0 合入 B5 后的 140 个 Ruff 错误，不改变产品行为、API 合同、迁移或测试语义，然后把清理提交合回 `feat/pg0-baseline-c0`，恢复 C0 Task 5。

**Architecture:** R0 是无迁移、无产品功能的机械清理切片。分支 `feat/pg0-ruff-cleanup` 从 C0 当前提交 `8a68069` 创建独立 worktree `/Users/lute/Project/data_scrapy-r0`。按风险拆分：先处理 import/测试语法，再处理行为敏感规则，最后分组换行 124 个 E501。每个任务先运行精确 Ruff RED，再修改，再运行目标测试与 Ruff GREEN，并提交。最终运行 C0 Task 5 的后端门禁；通过后，把 R0 合回 C0。

**Tech Stack:** Python 3.12、uv、Ruff、mypy、pytest、GitNexus。

## Global Constraints

- 起点固定为 `feat/pg0-baseline-c0` @ `8a68069790d9d7c905505892be2968d90f394629`。如果 C0 HEAD 移动，停止并重新基线。
- 只在 `/Users/lute/Project/data_scrapy-r0`、分支 `feat/pg0-ruff-cleanup` 工作。主工作树与 C0 worktree只读。
- 无 Alembic migration。不得修改 schema、API 路径、枚举、配置默认值、依赖版本或锁文件。
- 不使用 `ruff --fix` 全库自动修复，不使用 `--unsafe-fixes`。可以对精确文件运行安全 import 修复，但必须审查 diff。
- E501 只换行，不改字符串内容、集合顺序、参数顺序、字典键、描述文本或业务常量。
- `B905` 必须按现有长度语义选择 `strict=True` 或 `strict=False`；先读调用上下文和测试，不得机械添加。
- `B006` 把可变默认值改为 `None`，函数内创建新对象，并加回归测试证明调用间不共享状态。
- `E402` 优先移动 import；若 import 顺序是有意的运行时初始化，使用最窄的局部 noqa 并写测试证明，不改初始化顺序。
- 每个任务编辑既有符号前运行 GitNexus impact；`UNKNOWN` 用文本搜索确认；HIGH/CRITICAL 必须记录。
- 每次提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`；`partial`/`truncated` 不得为 true。
- 每个任务必须保留目标测试行为。不得删除、skip 或放宽测试。
- 最终必须通过 `uv run ruff check .`、`uv run mypy src tests`、`pytest tests/unit -q` 和带 `c0-pg15` 的 `pytest tests/integration -q`。
- 不推送、不打标签。R0 合回 C0 后删除 R0 worktree/分支由 C0 控制器处理。

## Baseline

Fresh Ruff JSON baseline:

```text
total: 140
rules: E501=124, I001=5, F401=4, SIM117=3, B905=2, E402=1, B006=1
files: 17
```

Top files:

```text
39 services/collector_catalog.py
25 api/routes/collectors.py
17 collectors/pkg_community_collector.py
10 collectors/pkg_registry2_collector.py
9 tests/unit/test_tikhub_social_collector.py
8 collectors/tikhub_social.py
6 collectors/hackernews_collector.py
6 collectors/package_registry_collector.py
5 collectors/aliens_eye_collector.py
```

---

### Task 0: 创建 R0 worktree 并冻结 Ruff JSON

**Files:**
- Create: `/Users/lute/Project/data_scrapy-r0`
- Create: `docs/ops/pg0-ruff-cleanup-2026-10-22.md`

**Interfaces:**
- Consumes: C0 HEAD `8a68069`。
- Produces: R0 worktree、Ruff JSON baseline、证据文档。

- [ ] **Step 1: 创建隔离 worktree**

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
test "$(git rev-parse feat/pg0-baseline-c0)" = "8a68069790d9d7c905505892be2968d90f394629"
test -z "$(git branch --list feat/pg0-ruff-cleanup)"
test ! -e /Users/lute/Project/data_scrapy-r0
git worktree add /Users/lute/Project/data_scrapy-r0 -b feat/pg0-ruff-cleanup feat/pg0-baseline-c0
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv sync --locked --dev
```

- [ ] **Step 2: 写 RED baseline**

```bash
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv run ruff check . --output-format json > /tmp/r0-ruff-baseline.json; test $? -eq 1
python3 -I -c 'import json,collections; d=json.load(open("/tmp/r0-ruff-baseline.json")); assert len(d)==140; print(collections.Counter(x["code"] for x in d))'
```

Expected: exactly 140 and the frozen rule counts above.

- [ ] **Step 3: 创建证据并提交**

Evidence records start SHA, rule counts, 17 files, and no migration/product changes.

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/ops/pg0-ruff-cleanup-2026-10-22.md
git commit -m "docs(ops): freeze R0 Ruff baseline"
```

---

### Task 1: 清理 imports 与测试结构规则

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/collectors/pkg_community_collector.py`
- Modify: `apps/api/tests/unit/test_anycrawl_collector.py`
- Modify: `apps/api/tests/unit/test_anydoc_collector.py`
- Modify: `apps/api/tests/unit/test_platform_package_generation.py`
- Modify: `apps/api/tests/unit/test_twscrape_collector.py`
- Modify: `apps/api/tests/unit/test_wappalyzer_collector.py`

**Interfaces:**
- Produces: I001=0、F401=0、SIM117=0、B006=0。

- [ ] **Step 1: RED**

```bash
uv run ruff check <six-files> --select I001,F401,SIM117,B006
```

Expected: 13 findings.

- [ ] **Step 2: 实现**

Sort imports; remove unused imports; combine nested context managers without changing patch lifetime; change `_fake_response(..., headers=None, ...)` and initialize `{}` inside.

- [ ] **Step 3: GREEN**

```bash
uv run ruff check <six-files> --select I001,F401,SIM117,B006
uv run pytest tests/unit/test_anycrawl_collector.py tests/unit/test_anydoc_collector.py tests/unit/test_platform_package_generation.py tests/unit/test_twscrape_collector.py tests/unit/test_wappalyzer_collector.py -q
```

- [ ] **Step 4: Commit**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -am "style(api): clean imports and test contexts"
```

---

### Task 2: 修复 B905 与 E402

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/collectors/hackernews_collector.py`
- Modify: `apps/api/src/data_intelligence_hub/collectors/pkg_registry2_collector.py`
- Test: focused collector tests discovered by text search.

**Interfaces:**
- Produces: B905=0、E402=0，不改变 zip 截断或模块初始化语义。

- [ ] **Step 1: impact 与 RED**

Run GitNexus impact for the functions containing both `zip()` sites and for the module-level import consumer. Search callers if UNKNOWN.

```bash
uv run ruff check <two-files> --select B905,E402
```

Expected: 3 findings.

- [ ] **Step 2: 实现**

Determine expected sequence lengths from code/tests. Use `strict=True` only when equality is an invariant; otherwise `strict=False`. Move E402 import only if initialization order is unaffected; otherwise use one line-specific `# noqa: E402` with an explanatory comment.

- [ ] **Step 3: GREEN and commit**

```bash
uv run ruff check <two-files> --select B905,E402
uv run pytest <focused-tests> -q
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -am "style(collectors): make sequence and import intent explicit"
```

---

### Task 3: 换行 collector 目录与路由

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/collector_catalog.py`（39 E501）
- Modify: `apps/api/src/data_intelligence_hub/api/routes/collectors.py`（25 E501）

**Interfaces:**
- Produces: 两文件 E501=0；目录内容与顺序逐字不变。

- [ ] **Step 1: RED and impact**

Run impact for collector catalog construction and collector route catalog symbols. Record HIGH/CRITICAL. Run exact Ruff E501 and expect 64.

- [ ] **Step 2: 实现**

Only parenthesize/split argument lists and adjacent string literals. Preserve rendered strings byte-for-byte; add tests or a before/after serialization comparison for catalog output.

- [ ] **Step 3: GREEN and commit**

Run Ruff on two files, relevant catalog/route tests, and compare generated catalog digest before/after. Commit `style(catalog): wrap collector metadata` after detect-changes.

---

### Task 4: 换行 package collectors

**Files:**
- Modify: `collectors/pkg_community_collector.py`（remaining E501）
- Modify: `collectors/pkg_registry2_collector.py`（remaining E501）
- Modify: `collectors/package_registry_collector.py`
- Modify: `collectors/aliens_eye_collector.py`
- Modify: `collectors/hackernews_collector.py`（remaining E501）
- Modify: `collectors/robin_collector.py`

**Interfaces:**
- Produces: listed files E501=0.

RED exact Ruff; wrap only; run focused collector tests; detect-changes; commit `style(collectors): wrap package collector code`.

---

### Task 5: 换行 TikHub 与剩余测试/渲染器

**Files:**
- Modify: `collectors/tikhub_social.py`
- Modify: `tests/unit/test_tikhub_social_collector.py`
- Modify: remaining E501 files from frozen JSON, including `collectors/base.py` and `platform_packages/renderers.py`.

**Interfaces:**
- Produces: E501=0 across repository.

RED exact Ruff on group; wrap only; run TikHub/social/platform package tests; detect-changes; commit `style(tikhub): wrap social collector and tests`.

---

### Task 6: R0 全量门禁与合回 C0

**Files:**
- Modify: `docs/ops/pg0-ruff-cleanup-2026-10-22.md`
- Merge into: `feat/pg0-baseline-c0`

- [ ] **Step 1: 全量静态门禁**

```bash
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv run ruff check .
uv run mypy src tests
```

- [ ] **Step 2: 测试门禁**

```bash
uv run pytest tests/unit -q
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' uv run pytest tests/integration -q
uv run python ../../scripts/test_tool_catalog.py
uv run python ../../scripts/test_platform_packages.py
```

Expected: original C0 baselines and digests unchanged.

- [ ] **Step 3: 全分支审查**

Generate review package from `8a68069` to R0 HEAD. Review spec/quality. Fix all Critical/Important findings.

- [ ] **Step 4: 合回 C0**

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge --no-ff feat/pg0-ruff-cleanup -m "merge(r0): clean inherited Ruff baseline"
uv --directory apps/api run ruff check .
```

Append C0 evidence noting R0 commit range and `All checks passed!`; run GitNexus; commit evidence.

## C0 Resume

After R0 merge:

1. Resume C0 Task 5 at Step 3 (`mypy`); Ruff Step 2 is satisfied by R0 and must be rerun once in C0.
2. Continue unit/integration/catalog/platform gates unchanged.
3. Keep `c0-pg15` running until C0 Task 5 finishes.
4. R0 introduces no schema revision, so C0 schema head remains `202610210057`.
