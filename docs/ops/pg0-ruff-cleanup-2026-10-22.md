# PG0 Ruff 基线冻结（2026-10-22）

R0 任务 0 的 RED 基线证据。本文只记录事实，不做修复。

## 起点

- 分支：`feat/pg0-ruff-cleanup`（自 `feat/pg0-baseline-c0` 切出）
- 起始 SHA：`8a68069790d9d7c905505892be2968d90f394629`
- Worktree：`/Users/lute/Project/data_scrapy-r0`
- 依赖：`uv sync --locked --dev`（apps/api，未改锁文件）
- 命令：`uv run ruff check . --output-format json`（apps/api 内）
- 原始输出：`/tmp/r0-ruff-baseline.json`（退出码 1，即存在违规）

## 基线总量与分布

总量：**140**。规则计数：E501=124、I001=5、F401=4、SIM117=3、B905=2、E402=1、B006=1。

| 规则 | 数量 | 文件（apps/api 相对路径） |
| --- | --- | --- |
| E501 | 39 | src/data_intelligence_hub/services/collector_catalog.py |
| E501 | 25 | src/data_intelligence_hub/api/routes/collectors.py |
| E501 | 16 | src/data_intelligence_hub/collectors/pkg_community_collector.py |
| E501 | 9 | src/data_intelligence_hub/collectors/pkg_registry2_collector.py |
| E501 | 9 | tests/unit/test_tikhub_social_collector.py |
| E501 | 8 | src/data_intelligence_hub/collectors/tikhub_social.py |
| E501 | 6 | src/data_intelligence_hub/collectors/package_registry_collector.py |
| E501 | 5 | src/data_intelligence_hub/collectors/aliens_eye_collector.py |
| E501 | 4 | src/data_intelligence_hub/collectors/hackernews_collector.py |
| B905 | 2 | src/data_intelligence_hub/collectors/hackernews_collector.py |
| SIM117 | 2 | tests/unit/test_anydoc_collector.py |
| B006 | 1 | tests/unit/test_wappalyzer_collector.py |
| E402 | 1 | src/data_intelligence_hub/collectors/pkg_registry2_collector.py |
| E501 | 1 | src/data_intelligence_hub/collectors/base.py |
| E501 | 1 | src/data_intelligence_hub/collectors/robin_collector.py |
| E501 | 1 | src/data_intelligence_hub/platform_packages/renderers.py |
| F401 | 1 | tests/unit/test_anycrawl_collector.py |
| F401 | 1 | tests/unit/test_anydoc_collector.py |
| F401 | 1 | tests/unit/test_twscrape_collector.py |
| F401 | 1 | tests/unit/test_wappalyzer_collector.py |
| I001 | 1 | src/data_intelligence_hub/collectors/pkg_community_collector.py |
| I001 | 1 | tests/unit/test_anycrawl_collector.py |
| I001 | 1 | tests/unit/test_anydoc_collector.py |
| I001 | 1 | tests/unit/test_platform_package_generation.py |
| I001 | 1 | tests/unit/test_twscrape_collector.py |
| SIM117 | 1 | tests/unit/test_twscrape_collector.py |

合计 26 行（规则 × 文件），140 条违规。

## 约束

- `migration=none`：本任务不含任何数据库迁移。
- `behavior_change=forbidden`：只做 lint 修复，禁止行为变更。


## Task 6 全量门禁（2026-10-23）

范围：`8a68069790d9d7c905505892be2968d90f394629..e9028e4425defd7a19d95cb8dae7490fe7b01ce5`（implementation HEAD `e9028e4`，分支 `feat/pg0-ruff-cleanup`）。本节只记录事实。

### GitNexus

- 索引重建：在 implementation HEAD `e9028e4` 运行 `GITNEXUS_INVOCATION=bun node .gitnexus/run.cjs analyze --index-only`，成功，16.6s，快照为 45,229 nodes / 76,559 edges / 988 clusters / 901 flows，增量 changed=18。解决 ledger 记录的索引落后问题（Task 4 时 behind 5 commits）。
- 编辑前 impact：`File:docs/ops/pg0-ruff-cleanup-2026-10-22.md` upstream → impactedCount 0，risk UNKNOWN（riskNote：零边不等于未被引用）；文本搜索确认仅 `docs/superpowers/plans/2026-10-22-…md` 引用该文件名，无代码引用。
- 提交前 detect-changes（clean 树）：`未检测到变更`，partial=false、truncated=false（输出无「结果不完整」「列表已截断」字符串）。`bb43838` 提交前先把索引增量更新到 `af0f107`（45,238 nodes / 76,568 edges / 988 clusters / 901 flows），再对计划与证据勘误运行 detect-changes：2 个文件、7 个符号、0 个受影响流程、risk low，输出同样无 partial/truncated 警告。

### 140 findings 分配（各任务修复数）

Task 1 = 13（8323a41、45a98f5）；Task 2 = 3（0599c75）；Task 3 = 64（3b483b0）；Task 4 = 41（3eb8555）；Task 5 = 19（e9028e4）。合计 140，每条恰好分配一次。Task 0（2f214d2）仅冻结基线，不含修复。

### Ruff（apps/api 口径）

- 命令：`.venv/bin/ruff check . --no-cache`（apps/api 内）。exit 0，stderr 0 字节，stdout 恰为 `All checks passed!`（sha256 82b3e6a6…f18）。E501=0 的准确范围是 apps/api，不是仓库根所有 Python。
- 实扫文件数：`.venv/bin/ruff check . --no-cache --show-files` 列出 748 个条目 = 747 个 `.py` + `apps/api/pyproject.toml`（不是 748 个 .py）。行数阈值口径：E501 阈值来自 `apps/api/pyproject.toml` 的 `line-length = 100`，不是 ruff 默认 88。
- 负控：在 /tmp 副本追加超长注释行后，`ruff check --select E501` exit 1，并报告 `E501 Line too long (122 > 88)`；防假 GREEN 成立。阈值口径勘误（2026-10-25）：该负控当时未带 `--config apps/api/pyproject.toml`，`88` 是 ruff 默认 line-length，不是项目阈值；正确阈值为 `apps/api/pyproject.toml` 的 `line-length = 100`，正确负控命令为 `ruff check /tmp/probe.py --select E501 --config apps/api/pyproject.toml --no-cache`，应报告 `> 100`（复测实例：新探针 121 字符行，带 `--config` 报告 `(121 > 100)`，不带报告 `(121 > 88)`）。apps/api 全量扫描自动使用项目配置，140 条基线计数（E501=124）不受此影响。
- 执行口径修正：Task 3–5 brief 的 `wc -l` 会把 Ruff 汇总行（`Found N errors.`）计入而 +1；实际以 `grep -c E501` 为准（Task 3 = 64、Task 4 = 41、Task 5 = 19，均与 brief 计划数一致）。

### mypy

- `uv run mypy src tests`（apps/api）：exit 1，`Found 1200 errors in 117 files (checked 689 source files)`。
- 基线对照：在 C0 worktree（`/Users/lute/Project/data_scrapy-c0`，HEAD `8a68069`）运行同一命令得 `Found 1199 errors in 117 files (checked 689 source files)`。mypy 失败为存量基线，非 R0 引入。
- +1 差值分析：`tikhub_social.py` 全文件的 `union-attr` 计数为 C0 14 条、R0 15 条；其中 `_normalize_tiktok_live` 区域为 9 条、10 条。基线 L1411 `anchor.get(...) if isinstance(anchor.get(...), dict)` 单行含两次 `.get`，mypy 报 1 次；Task 5 的 AST 等价换行把该表达式拆到 L1414/L1415，mypy 按行各报 1 次。两版本 `ast.dump(include_attributes=False)` 完全一致（本次验证重跑确认 `AST identical: True`）。属同一表达式的行计数差异，无新增类型错误类别。
- R0 范围内未修改任何测试或代码以改变 mypy 结果。
- 2026-10-23 用户裁决：R0 的 mypy 门禁采用 C0 起点基线非回归，不扩大为约 1200 项存量类型清理。去除 summary/note 并归一化行列号后，C0 与 R0 的唯一诊断签名均为 498，新增 0、移除 0；因此 1200 对 1199 的差值不构成新的类型错误语义，mypy 基线非回归门禁通过。

### pytest

- unit：`uv run pytest tests/unit -q` → exit 0，`2493 passed, 2 skipped, 1 warning`。
- integration：`DATABASE_URL='postgresql+asyncpg://c0:c0@127.0.0.1:55432/c0_migrations' uv run pytest tests/integration -q` → exit 0，`386 passed, 1 warning`（容器 c0-pg15，只读使用，未重启）。
- 历史计划曾预期 `2492 passed, 2 skipped`；Task 1 新增 `test_fake_response_default_headers_is_none`（commit `45a98f5`）后，实际基线为 `2493 passed, 2 skipped`。R0 计划和 C0 计划已在最终审查 fix wave 中同步为 2493。0 failed。
- warning：unit 与 integration 各 1 条，均为第三方 passlib `DeprecationWarning: 'crypt' is deprecated`（passlib/utils/__init__.py:854），与 R0 改动无关。

### 合同门禁

- `uv run alembic heads` → `202610210057 (head)`。R0 不含 migration，与约束 `migration=none` 一致。
- `uv run python ../../scripts/test_tool_catalog.py` → passed，tool_count 284 / canonical 284 / executable 226，digest `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c`（与冻结 digest 一致）。
- `uv run python ../../scripts/generate_platform_packages.py` → `generated 70 platform packages covering 284 unique endpoints`；随后 `git status --porcelain -uno` 0 行，无 tracked diff，未提交任何生成物。
- `uv run python ../../scripts/test_platform_packages.py` → passed，platform 70 / capability 312 / unique endpoint 284 / note 119。

### 源文件字节完整性（8a68069..e9028e4 全部 17 个改动的 .py）

逐一验证 `/usr/bin/stat -f %z` == `os.stat().st_size` == `len(read_bytes())`，UTF-8 解码通过，NUL=0：17/17 OK，0 失败。未发现尾洞，无需 inode 修复。

### 证据文档自身的尾洞修复（本次发现并处理）

- 修复前：本文件 `/usr/bin/stat -f %z` = 6727，`os.stat().st_size` = 2631，`read_bytes()` = 2631，差值恰 4096；可读区 NUL=0、UTF-8 通过、git blob 2631 字节、git diff 干净。与 MEMORY 记录的 heredoc/Edit 写入尾洞损坏特征一致（此前 Task 0 写入所致，Ruff/pytest 均未受影响，因本文件非 Python）。
- 修复方式：按规约用 /tmp Python 脚本以「当前可读字节 + 追加本节」写入同目录临时文件，flush+fsync 后 `os.replace` 替换 inode；git diff 相对提交保持「仅本节新增」（53 行新增），未触碰既有 52 行内容。
- 修复后复核：任务执行期间，该文档的部分新 inode 曾出现 `/usr/bin/stat -f %z` 比 `os.stat().st_size` 和 `read_bytes()` 多 4096 字节的现象；该现象未能稳定复现，因此不归因于 `stat` 工具或文件系统。每次出现后均用 /tmp 副本配合删除后复制重建 inode。最终值（含后续两次文本修订，见下）：`/usr/bin/stat -f %z` = `os.stat().st_size` = `read_bytes()`，NUL=0，UTF-8 通过。
- 后续修订：本节两次勘误（补幻影尺寸记录、补执行口径修正行），每次均走同目录临时文件 + fsync + `os.replace` + rm/cp 重建 inode；提交前做最终三重尺寸验证，数值随修订行数变化，以提交时验证输出为准。
