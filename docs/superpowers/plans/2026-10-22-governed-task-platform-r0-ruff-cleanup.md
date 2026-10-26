# Governed Task Platform R0 Ruff Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除 C0 合入 B5 后的 140 个 Ruff 错误，不改变产品行为、API 合同、迁移、测试语义、目录摘要或平台包输出，然后把清理分支合回 `feat/pg0-baseline-c0`，恢复 C0 Task 5。

**Architecture:** R0 是无迁移、无产品功能的机械清理切片。分支 `feat/pg0-ruff-cleanup` 从 C0 `8a68069790d9d7c905505892be2968d90f394629` 创建到 `/Users/lute/Project/data_scrapy-r0`。任务按风险划分：先修 import/测试结构，再处理 B905/E402，再按功能域换行 124 个 E501。每个任务先运行精确 Ruff RED，再改动，再运行目标测试和 Ruff GREEN，并提交。最终运行 C0 Task 5 的后端门禁；全分支审查通过后，由 C0 控制器把 R0 合回 C0。

**Tech Stack:** Python 3.12、uv、Ruff、mypy、pytest、GitNexus。

## Global Constraints

- 起点固定为 `feat/pg0-baseline-c0` @ `8a68069790d9d7c905505892be2968d90f394629`。不同则停止。
- 只在 `/Users/lute/Project/data_scrapy-r0`、分支 `feat/pg0-ruff-cleanup` 工作。主工作树与 C0 worktree 只读。
- 无 Alembic migration。不得修改 schema、API 路径、枚举、配置默认值、依赖版本或锁文件。
- 不运行全库 `ruff --fix`，不运行 `--unsafe-fixes`。所有改动逐文件审查。
- E501 只换行。不得改变字符串内容、字典键、集合顺序、参数顺序、业务常量、工具 ID 或 provider 文案。
- B905 必须先确认 zip 的长度语义。只有等长是不变量时使用 `strict=True`；允许截断时显式 `strict=False`。
- B006 把可变默认值改为 `None`，在函数内创建新字典；测试必须证明两次调用不共享 headers。
- E402 只有在 import 顺序确实依赖环境设置时使用单行 `# noqa: E402`，并写注释；否则移动 import。
- 每个任务改既有符号前运行 GitNexus impact。`UNKNOWN` 用 `rg` 查调用方；HIGH/CRITICAL 写入报告。
- 每次提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial`/`truncated` 不得为 true。
- 不删除、skip、xfail 或放宽任何测试。测试输出出现 warning 或 error 时记录。
- 最终必须通过：`uv run ruff check .`、`pytest tests/unit -q`、带 `c0-pg15` 的 `pytest tests/integration -q`、工具目录与平台包契约测试。`uv run mypy src tests` 采用 C0 起点基线非回归门禁：不新增归一化后的唯一诊断签名；仅因 AST 等价换行造成的同一诊断跨行重复计数不阻塞。该口径由用户于 2026-10-23 裁决。
- 不推送、不打标签。R0 不自行合并到 C0；合并由 C0 控制器在 R0 最终审查通过后执行。

## Frozen Ruff Baseline

```text
total=140, files=17
E501=124, I001=5, F401=4, SIM117=3, B905=2, E402=1, B006=1
```

| 文件 | 错误 |
|---|---|
| `src/data_intelligence_hub/services/collector_catalog.py` | E501×39 |
| `src/data_intelligence_hub/api/routes/collectors.py` | E501×25 |
| `src/data_intelligence_hub/collectors/pkg_community_collector.py` | E501×16、I001×1 |
| `src/data_intelligence_hub/collectors/pkg_registry2_collector.py` | E501×9、E402×1 |
| `tests/unit/test_tikhub_social_collector.py` | E501×9 |
| `src/data_intelligence_hub/collectors/tikhub_social.py` | E501×8 |
| `src/data_intelligence_hub/collectors/hackernews_collector.py` | E501×4、B905×2 |
| `src/data_intelligence_hub/collectors/package_registry_collector.py` | E501×6 |
| `src/data_intelligence_hub/collectors/aliens_eye_collector.py` | E501×5 |
| `tests/unit/test_anydoc_collector.py` | I001、F401、SIM117×2 |
| `tests/unit/test_twscrape_collector.py` | I001、F401、SIM117 |
| `tests/unit/test_anycrawl_collector.py` | I001、F401 |
| `tests/unit/test_wappalyzer_collector.py` | F401、B006 |
| `tests/unit/test_platform_package_generation.py` | I001 |
| `src/data_intelligence_hub/collectors/base.py` | E501 |
| `src/data_intelligence_hub/collectors/robin_collector.py` | E501 |
| `src/data_intelligence_hub/platform_packages/renderers.py` | E501 |

---

### Task 0: 创建 R0 worktree、复制计划并冻结基线

**Files:**
- Create: `/Users/lute/Project/data_scrapy-r0`
- Create/Commit: `docs/superpowers/plans/2026-10-22-governed-task-platform-r0-ruff-cleanup.md`
- Create: `docs/ops/pg0-ruff-cleanup-2026-10-22.md`

**Interfaces:**
- Consumes: C0 `8a68069`、`/tmp/c0-ruff.json`。
- Produces: R0 worktree、基线证据、分支 `feat/pg0-ruff-cleanup`。

- [ ] **Step 1: 创建 worktree**

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
test "$(git rev-parse feat/pg0-baseline-c0)" = "8a68069790d9d7c905505892be2968d90f394629"
test -z "$(git branch --list feat/pg0-ruff-cleanup)"
test ! -e /Users/lute/Project/data_scrapy-r0
git worktree add /Users/lute/Project/data_scrapy-r0 -b feat/pg0-ruff-cleanup feat/pg0-baseline-c0
mkdir -p /Users/lute/Project/data_scrapy-r0/docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-r0-ruff-cleanup.md /Users/lute/Project/data_scrapy-r0/docs/superpowers/plans/
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv sync --locked --dev
```

- [ ] **Step 2: RED 基线**

```bash
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv run ruff check . --output-format json > /tmp/r0-ruff-baseline.json; test $? -eq 1
python3 -I -c 'import json,collections; d=json.load(open("/tmp/r0-ruff-baseline.json")); assert len(d)==140; assert collections.Counter(x["code"] for x in d)=={"E501":124,"I001":5,"F401":4,"SIM117":3,"B905":2,"E402":1,"B006":1}; print("R0_BASELINE_OK")'
```

- [ ] **Step 3: 写证据**

Create `docs/ops/pg0-ruff-cleanup-2026-10-22.md` with start SHA, exact rule/file table above, `migration=none`, `behavior_change=forbidden`.

- [ ] **Step 4: 提交**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/superpowers/plans/2026-10-22-governed-task-platform-r0-ruff-cleanup.md docs/ops/pg0-ruff-cleanup-2026-10-22.md
git commit -m "docs(ops): freeze R0 Ruff baseline"
```

---

### Task 1: 清理 import、context manager 与 mutable default

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
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv run ruff check src/data_intelligence_hub/collectors/pkg_community_collector.py tests/unit/test_anycrawl_collector.py tests/unit/test_anydoc_collector.py tests/unit/test_platform_package_generation.py tests/unit/test_twscrape_collector.py tests/unit/test_wappalyzer_collector.py --select I001,F401,SIM117,B006
```

Expected: 13 findings: I001×5、F401×4、SIM117×3、B006×1。

- [ ] **Step 2: 写 B006 回归测试**

Add `import inspect` and append to `test_wappalyzer_collector.py`:

```python
def test_fake_response_default_headers_is_none() -> None:
    parameter = inspect.signature(_fake_response).parameters["headers"]
    assert parameter.default is None
```

Run the assertion against the parent implementation before editing:

```bash
git show HEAD:apps/api/tests/unit/test_wappalyzer_collector.py > /tmp/r0-wappalyzer-before.py
PYTHONPATH=src uv run python - <<'PY'
import inspect
import runpy
module = runpy.run_path("/tmp/r0-wappalyzer-before.py")
parameter = inspect.signature(module["_fake_response"]).parameters["headers"]
assert parameter.default is None
PY
```

Expected: FAIL with `AssertionError` because the parent default is `{}`.

- [ ] **Step 3: 实现**

- Sort the six import blocks.
- Remove unused `httpx`, `_max_bytes`, `os`, and `typing.Any` imports.
- Combine the two nested `with` blocks in `test_anydoc_collector.py` and the nested block in `test_twscrape_collector.py` into one parenthesized `with` statement; preserve patch lifetimes.
- Change `_fake_response(html, headers=None, status=200)` and set `headers = {} if headers is None else headers` before assigning the mock.

- [ ] **Step 4: GREEN**

```bash
uv run ruff check src/data_intelligence_hub/collectors/pkg_community_collector.py tests/unit/test_anycrawl_collector.py tests/unit/test_anydoc_collector.py tests/unit/test_platform_package_generation.py tests/unit/test_twscrape_collector.py tests/unit/test_wappalyzer_collector.py --select I001,F401,SIM117,B006
uv run pytest tests/unit/test_anycrawl_collector.py tests/unit/test_anydoc_collector.py tests/unit/test_platform_package_generation.py tests/unit/test_twscrape_collector.py tests/unit/test_wappalyzer_collector.py -q
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/collectors/pkg_community_collector.py apps/api/tests/unit/test_anycrawl_collector.py apps/api/tests/unit/test_anydoc_collector.py apps/api/tests/unit/test_platform_package_generation.py apps/api/tests/unit/test_twscrape_collector.py apps/api/tests/unit/test_wappalyzer_collector.py
git commit -m "style(api): clean imports and test contexts"
```

---

### Task 2: 明确 hackernews zip 与 pkg_registry2 import 语义

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/collectors/hackernews_collector.py`
- Modify: `apps/api/src/data_intelligence_hub/collectors/pkg_registry2_collector.py`
- Test: `apps/api/tests/unit/test_outbound_provider_gates.py`
- Test: `apps/api/tests/unit/test_collector_empty_policy.py`
- Test: `apps/api/tests/unit/test_package_registry_specs.py`
- Test: `apps/api/tests/unit/test_collector_specs.py`

**Interfaces:**
- Produces: B905=0、E402=0，不改变输出数量或导入初始化顺序。

- [ ] **Step 1: impact**

Run GitNexus impact for the two functions containing `zip()` and the symbol imported at `pkg_registry2_collector.py:19`. If UNKNOWN, use `rg` for exact callers/imports.

- [ ] **Step 2: RED**

```bash
uv run ruff check src/data_intelligence_hub/collectors/hackernews_collector.py src/data_intelligence_hub/collectors/pkg_registry2_collector.py --select B905,E402
```

Expected: B905×2、E402×1。

- [ ] **Step 3: 实现**

- Read both zip producers. Add `strict=True` only if both input lists are constructed from the same source and tests require equal lengths; otherwise add `strict=False` to preserve truncation.
- `pkg_registry2_collector.py` 的 late import 不依赖环境或模块初始化。把 `.base` import block 移到 `_NoRedirectClient` 之前的正常 import 区，不使用 `# noqa: E402`，也不移动其他 import。

- [ ] **Step 4: GREEN**

```bash
uv run ruff check src/data_intelligence_hub/collectors/hackernews_collector.py src/data_intelligence_hub/collectors/pkg_registry2_collector.py --select B905,E402
uv run pytest tests/unit/test_outbound_provider_gates.py tests/unit/test_collector_empty_policy.py tests/unit/test_package_registry_specs.py tests/unit/test_collector_specs.py -q
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/collectors/hackernews_collector.py apps/api/src/data_intelligence_hub/collectors/pkg_registry2_collector.py
git commit -m "style(collectors): make zip and import intent explicit"
```

---

### Task 3: 换行 collector catalog 与 collector routes（64 E501）

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/collector_catalog.py`（39）
- Modify: `apps/api/src/data_intelligence_hub/api/routes/collectors.py`（25）

**Interfaces:**
- Produces: 两文件 E501=0；catalog IDs、description、params、provider 和顺序不变。

- [ ] **Step 1: impact 与 RED**

Impact `collector_specs`/catalog construction and collector route catalog symbols. Then:

```bash
uv run ruff check src/data_intelligence_hub/services/collector_catalog.py src/data_intelligence_hub/api/routes/collectors.py --select E501 --output-format concise | tee /tmp/r0-task3-red.txt
test "$(grep -c E501 /tmp/r0-task3-red.txt)" -eq 64
```

- [ ] **Step 2: 冻结输出**

Run `uv run python ../../scripts/test_tool_catalog.py > /tmp/r0-catalog-before.json` and save SHA-256 of `configs/tool-catalog.lock.json`.

- [ ] **Step 3: 实现**

Only split parenthesized calls/lists and use adjacent string literals. Do not alter rendered strings or collection order.

- [ ] **Step 4: GREEN**

```bash
uv run ruff check src/data_intelligence_hub/services/collector_catalog.py src/data_intelligence_hub/api/routes/collectors.py --select E501
uv run pytest tests/unit/test_collector_specs.py tests/unit/test_collector_seeding.py tests/unit/test_collector_catalog_live_status.py tests/unit/test_provider_status.py tests/unit/test_catalog_digest_parity.py tests/integration/test_sources_tasks.py -q
uv run python ../../scripts/test_tool_catalog.py > /tmp/r0-catalog-after.json
cmp /tmp/r0-catalog-before.json /tmp/r0-catalog-after.json
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/collector_catalog.py apps/api/src/data_intelligence_hub/api/routes/collectors.py
git commit -m "style(catalog): wrap collector metadata"
```

---

### Task 4: 换行 package 与社区 collectors（41 E501）

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/collectors/pkg_community_collector.py`（16）
- Modify: `apps/api/src/data_intelligence_hub/collectors/pkg_registry2_collector.py`（9）
- Modify: `apps/api/src/data_intelligence_hub/collectors/package_registry_collector.py`（6）
- Modify: `apps/api/src/data_intelligence_hub/collectors/aliens_eye_collector.py`（5）
- Modify: `apps/api/src/data_intelligence_hub/collectors/hackernews_collector.py`（4）
- Modify: `apps/api/src/data_intelligence_hub/collectors/robin_collector.py`（1）

**Interfaces:**
- Produces: 41 E501 → 0；collector payloads unchanged。

- [ ] **Step 1: RED**

```bash
uv run ruff check src/data_intelligence_hub/collectors/pkg_community_collector.py src/data_intelligence_hub/collectors/pkg_registry2_collector.py src/data_intelligence_hub/collectors/package_registry_collector.py src/data_intelligence_hub/collectors/aliens_eye_collector.py src/data_intelligence_hub/collectors/hackernews_collector.py src/data_intelligence_hub/collectors/robin_collector.py --select E501 --output-format concise | tee /tmp/r0-task4-red.txt
test "$(grep -c E501 /tmp/r0-task4-red.txt)" -eq 41
```

- [ ] **Step 2: 实现**

Wrap only. Preserve URLs, headers, queries, timeouts, exception text and result shapes.

- [ ] **Step 3: GREEN**

```bash
uv run ruff check src/data_intelligence_hub/collectors/pkg_community_collector.py src/data_intelligence_hub/collectors/pkg_registry2_collector.py src/data_intelligence_hub/collectors/package_registry_collector.py src/data_intelligence_hub/collectors/aliens_eye_collector.py src/data_intelligence_hub/collectors/hackernews_collector.py src/data_intelligence_hub/collectors/robin_collector.py --select E501
uv run pytest tests/unit/test_outbound_provider_gates.py tests/unit/test_collector_empty_policy.py tests/unit/test_package_registry_specs.py tests/unit/test_collector_specs.py tests/unit/test_outbound_scanner_gates.py tests/integration/test_quick_collect_routes.py -q
```

- [ ] **Step 4: Commit**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/collectors/pkg_community_collector.py apps/api/src/data_intelligence_hub/collectors/pkg_registry2_collector.py apps/api/src/data_intelligence_hub/collectors/package_registry_collector.py apps/api/src/data_intelligence_hub/collectors/aliens_eye_collector.py apps/api/src/data_intelligence_hub/collectors/hackernews_collector.py apps/api/src/data_intelligence_hub/collectors/robin_collector.py
git commit -m "style(collectors): wrap package collector code"
```

---

### Task 5: 换行 TikHub 与剩余文件（19 E501）

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/collectors/tikhub_social.py`（8）
- Modify: `apps/api/tests/unit/test_tikhub_social_collector.py`（9）
- Modify: `apps/api/src/data_intelligence_hub/collectors/base.py`（1）
- Modify: `apps/api/src/data_intelligence_hub/platform_packages/renderers.py`（1）

**Interfaces:**
- Produces: repository E501=0；TikHub schemas and package rendering unchanged。

- [ ] **Step 1: RED**

```bash
uv run ruff check src/data_intelligence_hub/collectors/tikhub_social.py tests/unit/test_tikhub_social_collector.py src/data_intelligence_hub/collectors/base.py src/data_intelligence_hub/platform_packages/renderers.py --select E501 --output-format concise | tee /tmp/r0-task5-red.txt
test "$(grep -c E501 /tmp/r0-task5-red.txt)" -eq 19
```

- [ ] **Step 2: 实现**

Wrap only. Keep endpoint types, tool IDs, schemas, exception strings and golden render output unchanged.

- [ ] **Step 3: GREEN**

```bash
uv run ruff check src/data_intelligence_hub/collectors/tikhub_social.py tests/unit/test_tikhub_social_collector.py src/data_intelligence_hub/collectors/base.py src/data_intelligence_hub/platform_packages/renderers.py --select E501
uv run pytest tests/unit/test_tikhub_social_collector.py tests/unit/test_tikhub_param_contract.py tests/unit/test_tikhub_tiktok_content.py tests/unit/test_tikhub_tiktok_commerce.py tests/unit/test_platform_package_generation.py tests/unit/test_platform_package_builder.py -q
```

- [ ] **Step 4: Commit**

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/collectors/tikhub_social.py apps/api/tests/unit/test_tikhub_social_collector.py apps/api/src/data_intelligence_hub/collectors/base.py apps/api/src/data_intelligence_hub/platform_packages/renderers.py
git commit -m "style(tikhub): wrap social collector and tests"
```

---

### Task 6: R0 全量门禁与交接

**Files:**
- Modify: `docs/ops/pg0-ruff-cleanup-2026-10-22.md`

**Interfaces:**
- Produces: clean R0 branch and merge-back packet for C0 controller。

- [ ] **Step 1: Ruff/mypy**

```bash
cd /Users/lute/Project/data_scrapy-r0/apps/api
uv run ruff check .
uv run mypy src tests
```

mypy 判定：与 C0 起点 `8a68069790d9d7c905505892be2968d90f394629` 运行同一命令；去除 `summary` 和 `note` 并归一化行列号后，唯一诊断签名集合必须相同。原始错误数可因 AST 等价换行把同一诊断拆到两行而变化，但必须记录并证明无新增诊断签名。

- [ ] **Step 2: unit/integration**

```bash
uv run pytest tests/unit -q
DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' uv run pytest tests/integration -q
```

Expected: `2493 passed, 2 skipped`; `386 passed`.

- [ ] **Step 3: contracts**

```bash
uv run alembic heads
uv run python ../../scripts/test_tool_catalog.py
uv run python ../../scripts/generate_platform_packages.py
cd /Users/lute/Project/data_scrapy-r0
git status --porcelain -uno
cd apps/api
uv run python ../../scripts/test_platform_packages.py
```

Expected: head `202610210057`; catalog 284/284/226 and frozen digest; package 70/312/284; generation has no diff.

- [ ] **Step 4: evidence and commit**

Append exact final counts, tests, digests, and commit range to R0 evidence.

```bash
cd /Users/lute/Project/data_scrapy-r0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/ops/pg0-ruff-cleanup-2026-10-22.md
git commit -m "docs(ops): record R0 Ruff cleanup verification"
```

- [ ] **Step 5: final branch review**

Controller generates review package from `8a68069` to R0 HEAD. Dispatch most-capable reviewer. One fix wave maximum for final review findings.

- [ ] **Step 6: C0 controller merge-back**

After clean final review, controller runs:

```bash
cd /Users/lute/Project/data_scrapy-c0
git merge --no-ff feat/pg0-ruff-cleanup -m "merge(r0): clean inherited Ruff baseline"
uv --directory apps/api run ruff check .
```

Then append C0 evidence with R0 commit range and `All checks passed!`, run GitNexus, and commit evidence. R0 itself must not execute this merge.

## C0 Resume

1. Keep `c0-pg15` running.
2. Rerun C0 Task 5 Step 2 Ruff once in the merged C0 worktree.
3. Resume at Task 5 Step 3 (`mypy src tests`) with the amended baseline non-regression gate; use the amended unit baseline `2493 passed, 2 skipped` for Steps 4 and 6.
4. R0 adds no migration; C0 head remains `202610210057`.

## Self-Review

- All 140 findings are assigned exactly once: Task 1 handles 13, Task 2 handles 3, Task 3 handles 64, Task 4 handles 41, Task 5 handles 19; total 140.
- No placeholders or unspecified file lists remain.
- No product behavior, migrations, dependencies, API contracts or test expectations are changed.
