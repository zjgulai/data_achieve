# Governed Task Platform S0 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立 S0 切片中关闭 C0 最终审查确认的 MCP 租户隔离、报告校验、治理字段泄漏、MCP 向后兼容、发布证据和 CI 门禁缺陷；保留 `pg0-baseline-v1` 不变，最终安全审查通过后才创建新的本地 `pg0-baseline-v2`。

**Architecture:** S0 从 C0 `0c11c2b1556f5f274b93cb1cdbf9500b01d7f60c` 分出，使用服务层可选 `project_id` 过滤和工具层既有身份辅助函数关闭越权路径。兼容性修复只在 MCP 工具装配层恢复旧字段和旧行语义，不修改全局 catalog projection、数据库模型或迁移。报告哈希由 build/verify 共享一个输入 ID 解析器。证据和 CI 修复与运行时代码分开提交。

**Tech Stack:** Python 3.12、FastAPI、MCP SDK、SQLAlchemy async、Pydantic、pytest、Ruff 0.15.16、mypy、Alembic、GitHub Actions、GitNexus 1.6.12、Git annotated tags。

## Global Constraints

- S0 分支固定为 `fix/s0-c0-hardening`，worktree 固定为 `/Users/lute/Project/data_scrapy-c0-s0`，起点固定为 `0c11c2b1556f5f274b93cb1cdbf9500b01d7f60c`。不同则停止。
- 本地 annotated tag `pg0-baseline-v1` 必须始终保持 tag object `48aaccfa5a3689f23f7517cfb88b59c2533805ab`，并指向 commit `e227070054914f9cbef8cb5d508e5f4aa73d8dcb`。不得移动、删除、强制覆盖或推送。
- 不修改 Alembic migration、SQLAlchemy model、`configs/*.lock.json`、`apps/scraper-console/**`、Dockerfile、compose、`tool_catalog/projection.py`。`SCHEMA_HEAD` 必须保持 `202610210057`，catalog digest 必须保持 `35ead4d917a7ce71835edbd7ee0eaefe85db47c0faf992a1c606144cd7b4493c`。
- 只修确认的 Critical/Important 缺陷及其直接测试、证据、CI 门禁。不得顺手移植 main 的 provider cancellation、record deep-link、enrichment quota 或错误码全量改名。
- 全局 token 没有项目身份时保持既有行为；项目密钥必须 fail-closed，跨项目和跨工作区不得读、写或计量他项目数据。
- MCP 工具总数保持 39。`create_report`、`discover`、`inspect` 是相对整合比较基座 `f0560ca` 的三个净新增工具；它们在 S0 起点 `0c11c2b` 已存在。不得删除或改名。
- `get_playbook` 和 `list_capabilities` 恢复旧字段时采用加法兼容。旧字段至少保留一个迁移周期；本计划不删除新结构化字段。
- 修改函数、类或方法前必须运行 GitNexus upstream impact。`UNKNOWN` 必须用文本搜索确认。HIGH/CRITICAL 必须先记录风险。每个提交前运行 `detect-changes --scope all`；`partial` 或 `truncated` 不是 clean。
- 每个行为修复必须有真实 RED。characterization test 必须在计划中明确标为“当前即应通过”，不得伪称 RED。
- 每次写入 Python/Markdown 后验证 UTF-8、NUL=0、原生 `/usr/bin/stat -f %z == os.stat().st_size == len(read_bytes())`。出现 `+4096` 尾洞时用 `/tmp` 副本配合删除后复制重建 inode，并保持 Git 内容不变。
- 不 push 分支、不 push 标签、不创建 PR、不操作生产、不启动生产 compose。
- `pg0-baseline-v2` 只允许在所有任务、最终 whole-branch 安全审查和标签前门禁通过后创建；标签也只保留本地。

## File Structure

| 文件 | 责任 |
|---|---|
| `apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py` | 运行查询、取消和项目余额服务；S0 只给 `stop_run` 增加可选项目过滤。 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/server.py` | MCP 工具装配、身份过滤和兼容字段；修复 `deep_research_check`、`stop`、`balance`、`list_capabilities`、`get_playbook`。 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py` | `inspect` 契约投影与结构化 playbook；改用 public projection，并恢复 `markdown` 别名。 |
| `apps/api/src/data_intelligence_hub/services/report_artifacts.py` | 报告哈希构建与复核；build/verify 共用输入 ID 解析器。 |
| `apps/api/tests/unit/test_mcp_run_service.py` | 服务层 `stop_run` 项目隔离。 |
| `apps/api/tests/unit/test_mcp_tools_b5.py` | MCP 越权、inspect 脱敏、能力列表兼容、playbook 兼容、空 ledger guard。 |
| `apps/api/tests/unit/test_report_artifacts.py` | 报告构建/复核 round-trip。 |
| `apps/api/tests/integration/test_tools_routes.py` | REST public projection 与 MCP inspect 一致性。 |
| `.github/workflows/ci.yml` | 修复 API job 根目录、无 DB 测试范围、platform-packages job 的 integration DB 缺口。 |
| `scripts/verify-*-migration.sh` | 只更新“当前 Alembic 单头断言”为 `202610210057`；历史 upgrade/downgrade revision 保持原值。 |
| `apps/api/tests/unit/test_*_postgres_guard.py` | 同步当前单头断言。 |
| `apps/api/tests/unit/test_migration_head_pins.py` | 新增统一单头 pin 守卫，防止脚本再次陈旧。 |
| `scripts/check_mypy_baseline.py` | 归一化 mypy 输出并拒绝新增诊断签名；允许存量债务减少。 |
| `configs/quality/mypy-src-signatures.txt` | Task 0 冻结的 `mypy src` multiset：62 个签名、123 个实例。 |
| `configs/quality/mypy-src-tests-signatures.txt` | Task 0 冻结的 `mypy src tests` multiset：498 个签名、1200 个实例，供 CI non-regression。 |
| `docs/ops/pg0-baseline-c0-2026-10-22.md` | 修正工具增量、兼容性变化、GitNexus compare、CI 风险、Ruff 和 Console build-arg 事实。 |
| `docs/ops/pg0-ruff-cleanup-2026-10-22.md` | 修正 Ruff 负控使用项目配置和 100 列阈值。 |
| `docs/ops/pg0-s0-hardening-2026-10-24.md` | S0 执行证据、门禁和标签前事实。 |

---

### Task 0: 冻结 S0 工作区、v1 标签与 RED 基线

**Files:**
- Create: `docs/superpowers/plans/2026-10-24-governed-task-platform-s0-hardening.md`
- Create: `docs/ops/pg0-s0-hardening-2026-10-24.md`
- Create: `configs/quality/mypy-src-signatures.txt`
- Create: `configs/quality/mypy-src-tests-signatures.txt`

**Interfaces:**
- Consumes: C0 `0c11c2b`、本地 `pg0-baseline-v1`、C0 最终审查发现。
- Produces: S0 ledger、基线证据、mypy 诊断基线、tag immutability 断言。

- [ ] **Step 1: 验证工作区与标签**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
test "$(git branch --show-current)" = "fix/s0-c0-hardening"
test "$(git rev-parse HEAD)" = "0c11c2b1556f5f274b93cb1cdbf9500b01d7f60c"
test -z "$(git status --porcelain -uno)"
test "$(git rev-parse pg0-baseline-v1)" = "48aaccfa5a3689f23f7517cfb88b59c2533805ab"
test "$(git rev-parse pg0-baseline-v1^{commit})" = "e227070054914f9cbef8cb5d508e5f4aa73d8dcb"
```

Expected: 全部退出码 0。

- [ ] **Step 2: 建立依赖与索引**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
uv sync --locked --dev
cd /Users/lute/Project/data_scrapy-c0-s0
if [ ! -f .gitnexus/run.cjs ]; then
  bunx gitnexus@latest analyze --index-only
fi
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs status --json > /tmp/s0-gitnexus-status.json
```

Expected: 锁文件无 diff；默认 runner 的 `status=up-to-date`、`runnerIdentityStatus=current`、`incompleteReasons=[]`。

- [ ] **Step 3: 冻结 mypy 和测试基线**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
set +e
.venv/bin/python -m mypy src > /tmp/s0-mypy-baseline.txt 2>&1
MYPY_RC=$?
set -e
test "$MYPY_RC" -eq 1
grep -q '^Found 123 errors in 28 files' /tmp/s0-mypy-baseline.txt
.venv/bin/python -m pytest tests/unit -q > /tmp/s0-unit-baseline.txt
```

Expected: `mypy src` 基线 123 errors/28 files；unit 不得有 failed/error。记录实际 passed/skip 数，不把 ignored `generated/` 存在导致的 skip 转 pass 误写成固定数量。

另运行 `.venv/bin/python -m mypy src tests > /tmp/s0-mypy-src-tests-baseline.txt 2>&1`，预期 `Found 1200 errors in 117 files (checked 689 source files)`。规范化两份输出：删除 summary/note，只保留 `: error:` 行，把 `:line[:column]:` 归一化为 `:LINE:`，去重排序后写入：

```text
configs/quality/mypy-src-signatures.txt              # multiset v1；62 行/123 实例；SHA-256 47001690...
configs/quality/mypy-src-tests-signatures.txt        # multiset v1；498 行/1200 实例；SHA-256 9df7ee3e...
```

两份文件是 Task 0 冻结基线；Task 1-10 不得重新生成或放宽。后续门禁按每个签名的实例计数比较：允许减少；新签名或任一签名计数增加都失败。

- [ ] **Step 4: 冻结确认缺陷的 RED**

运行以下现有行为探针并保存到 `/tmp/s0-red-baseline.json`：

```text
stop：项目 A 密钥可取消项目 B run。
balance：项目 A 密钥可读项目 B 账本。
deep_research_check：项目 A 密钥可读项目 B run/records。
inspect：返回 authorization 和 reachability.block_reason。
verify_artifact：空 run_ledger + artifact.run_id 的合法产物被报 data_sha256 mismatch。
list_capabilities("rss")：返回 0，而平台包含 19 endpoints。
get_playbook("tiktok")：没有 markdown 字段。
```

使用 `apps/api/.venv/bin/python -I` 运行隔离探针。Expected: 七项都复现；探针不得修改 tracked 文件。

- [ ] **Step 5: 创建 S0 证据文件**

安全写入 `docs/ops/pg0-s0-hardening-2026-10-24.md`，至少记录：start SHA、v1 tag object/commit、mypy baseline、unit baseline、七项 RED、`SCHEMA_HEAD=202610210057`、catalog digest、`migration=none`、`v1_immutable=true`、`push=forbidden`。

- [ ] **Step 6: 变更分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/superpowers/plans/2026-10-24-governed-task-platform-s0-hardening.md docs/ops/pg0-s0-hardening-2026-10-24.md configs/quality/mypy-src-signatures.txt configs/quality/mypy-src-tests-signatures.txt
git commit -m "docs(plan): add S0 hardening slice"
```

Expected: 只提交两个文档；工作树 clean；v1 标签不变。

---

### Task 1: 服务层为 stop_run 增加项目过滤

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py:130-157`
- Test: `apps/api/tests/unit/test_mcp_run_service.py`

**Interfaces:**
- Consumes: `Run.project_id`、现有 `runs_repository.cancel_run`。
- Produces:

```python
async def stop_run(
    run_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]: ...
```

`project_id=None` 保持全局 token/旧调用行为；不匹配时抛 `ValueError("run_not_found")`，且不改变 run 状态。

- [ ] **Step 1: impact**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs impact stop_run --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py
```

Expected: LOW/exact，直接 caller 为 `server.stop`。若结果不同，记录后继续，不把 UNKNOWN 当低风险。

- [ ] **Step 2: 写真实 RED**

在 `test_mcp_run_service.py` 新增：

```python
@pytest.mark.anyio
async def test_stop_run_is_project_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    factory, engine = _make_factory()
    await _create_schema(engine)
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    sibling_project_id = uuid.uuid4()
    run_id = await _seed_running(
        factory,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    monkeypatch.setattr(run_service, "async_session_factory", factory)
    try:
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.stop_run(run_id, project_id=sibling_project_id)
        async with factory() as session:
            row = await session.get(Run, run_id)
            assert row is not None
            assert row.status == "running"
        result = await run_service.stop_run(run_id, project_id=project_id)
        assert result["cancelled"] is True
    finally:
        await engine.dispose()
```

根据现有 helper 的实际签名调整 `_seed_running` 参数，不新建第二套造数器。

- [ ] **Step 3: 运行 RED**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
.venv/bin/python -m pytest tests/unit/test_mcp_run_service.py::test_stop_run_is_project_scoped -q
```

Expected: FAIL，`stop_run()` 不接受 `project_id`。

- [ ] **Step 4: 最小实现**

```python
async def stop_run(
    run_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or (project_id is not None and run.project_id != project_id):
            raise ValueError("run_not_found")
        ...
```

不修改 cancellation 后续逻辑。

- [ ] **Step 5: GREEN 与兼容性**

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_run_service.py -q
.venv/bin/ruff check src/data_intelligence_hub/mcp_runtime/run_service.py tests/unit/test_mcp_run_service.py
```

Expected: 全部通过；现有不传 `project_id` 的测试保持 green。

- [ ] **Step 6: 变更分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py apps/api/tests/unit/test_mcp_run_service.py
git commit -m "fix(mcp): scope stop_run to the calling project"
```

---

### Task 2: 工具层关闭 stop 与 balance 越权

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:868-892`
- Test: `apps/api/tests/unit/test_mcp_tools_b5.py`

**Interfaces:**
- Consumes: Task 1 的 `stop_run(..., project_id=...)`、`project_filter`、`_parse_project_id`。
- Produces: 项目密钥只能取消和查询自身项目；全局 token 保持不过滤。

- [ ] **Step 1: impact**

```bash
node .gitnexus/run.cjs impact stop --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
node .gitnexus/run.cjs impact balance --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
node .gitnexus/run.cjs impact _parse_project_id --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
```

Expected: `_parse_project_id` 为 CRITICAL/exact；**不得修改该函数或错误词汇**。stop/balance 若 UNKNOWN，用 `rg` 确认 tool registration 和 tests。

- [ ] **Step 2: 写真实 RED**

在 `test_mcp_tools_b5.py` 新增同工作区跨项目、跨工作区、正向、全局 token 用例。每个项目身份的 allowlist 必须显式包含 `("stop", "balance")`，否则只会得到 `tool_not_allowed` 假绿。

关键断言：

```python
assert stop_other.is_error is True
assert "run_not_found" in _error_text(stop_other)
assert str(other_project_id) not in _error_text(stop_other)

with pytest.raises(ValueError, match="project_mismatch"):
    await server_module.balance(context, str(other_project_id))
```

并复查 foreign run 仍为 `running`。

- [ ] **Step 3: 运行 RED**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_mcp_tools_b5.py -k 'stop or balance' -q
```

Expected: foreign stop 被取消或 foreign balance 返回数据，测试失败。

- [ ] **Step 4: 最小实现**

```python
return await stop_run(parsed, project_id=project_filter(context))
```

```python
parsed = _parse_project_id(project_id, context)
return await get_project_balance(parsed)
```

禁止在工具体内新增直接 `project_api_key_context` 读取。

- [ ] **Step 5: GREEN 与 seam guard**

新增测试固定：patch `runtime.project_api_key_context` 后，`server_module.project_filter(context)` 返回身份项目；own project 成功；global token (`None`) 保持旧行为。

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_tools_b5.py -k 'stop or balance or project_filter' -q
.venv/bin/ruff check src/data_intelligence_hub/mcp_runtime/server.py tests/unit/test_mcp_tools_b5.py
```

- [ ] **Step 6: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "fix(mcp): scope stop and balance to the calling project"
```

---

### Task 3: 关闭 deep_research_check 跨项目读取

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:689-704`
- Test: `apps/api/tests/unit/test_mcp_tools_b5.py`
- Verify unchanged caller: `apps/api/src/data_intelligence_hub/api/routes/research.py:67-78`

**Interfaces:**
- Consumes: `get_run_detail(..., project_id=None)`、`list_run_records(..., project_id=None)`。
- Produces: 项目密钥按 `project_filter` 过滤；全局 token 仍可不传 filter；坏 UUID 返回 `run_id_invalid`。

- [ ] **Step 1: impact + UNKNOWN 文本确认**

```bash
node .gitnexus/run.cjs impact deep_research_check --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
node .gitnexus/run.cjs impact get_run_detail --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py
node .gitnexus/run.cjs impact list_run_records --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py
rg -n 'deep_research_check|get_run_detail\(|list_run_records\(' apps/api/src apps/api/tests
```

Expected: service functions LOW/exact；HTTP route 不传 `project_id`，因此参数必须保持可选。

- [ ] **Step 2: 写真实 RED**

新增：allowlist 包含 `deep_research_check`；same-workspace sibling run 和 cross-workspace run 均 `run_not_found`；own run 成功；global token 保持旧行为；`not-a-uuid` 返回 `run_id_invalid`，不得暴露 Python UUID 文本。

- [ ] **Step 3: 运行 RED**

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_tools_b5.py -k deep_research_check -q
```

Expected: foreign run 仍泄漏，坏 UUID 错误文本不一致。

- [ ] **Step 4: 最小实现**

```python
try:
    parsed = uuid.UUID(run_id)
except ValueError as exc:
    raise ValueError("run_id_invalid") from exc
scope = project_filter(context)
detail = await get_run_detail(parsed, project_id=scope)
records = await list_run_records(parsed, limit=20, project_id=scope)
```

删除 `Run` import；保留 `async_session_factory`。

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_tools_b5.py tests/unit/test_mcp_exa_tools.py -q
.venv/bin/ruff check src/data_intelligence_hub/mcp_runtime/server.py tests/unit/test_mcp_tools_b5.py
```

- [ ] **Step 6: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "fix(mcp): scope deep_research_check to the calling project"
```

---

### Task 4: inspect 使用 public projection 脱敏

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py:206-219`
- Test: `apps/api/tests/unit/test_mcp_tools_b5.py`
- Test: `apps/api/tests/unit/test_mcp_runtime.py`
- Test: `apps/api/tests/integration/test_tools_routes.py`

**Interfaces:**
- Consumes: `to_public_tool(ToolDescriptor)`、`_input_schema`、`_output_schema`。
- Produces: `PublicTool` 字段 + `input_schema` + `output_schema` + `method`；无 governance 原文。

- [ ] **Step 1: impact**

```bash
node .gitnexus/run.cjs impact inspect_tool --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py
node .gitnexus/run.cjs impact to_public_tool --direction upstream --repo . --file apps/api/src/data_intelligence_hub/tool_catalog/public.py
```

UNKNOWN 时用 `rg -n 'inspect_tool\(|to_public_tool\(' apps/api` 确认。

- [ ] **Step 2: 写真实 RED**

新增测试递归扫描返回值，断言不存在：`authorization`、`reachability`、`block_reason`、`policy_block_reason`、`collection_policy_denied`、`demo_workspace`、`执行入口当前不校验身份`。

再断言：

```python
expected = set(PublicTool.model_fields) | {"input_schema", "output_schema", "method"}
assert set(body) == expected
assert "availability" in body
assert "availability_view" not in body
```

全 284 工具循环；`aliens_eye_advanced` 必须 `execution_kind="unsupported"`、`permanently_blocked=True`、`executable_now=False`、`output_schema is None`。

- [ ] **Step 3: 运行 RED**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_mcp_tools_b5.py \
  tests/unit/test_mcp_runtime.py \
  tests/integration/test_tools_routes.py \
  -k inspect -q
```

Expected: 当前返回 `authorization`/`reachability`，失败。

- [ ] **Step 4: 最小实现**

```python
from data_intelligence_hub.tool_catalog.public import to_public_tool

public = to_public_tool(tool)
payload = public.model_dump(mode="json")
payload["input_schema"] = _input_schema(tool)
payload["output_schema"] = _output_schema(tool.tool_id)
payload["method"] = tool.method
```

不改 `PublicTool` 模型、不改 `projection.py`。

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_mcp_tools_b5.py \
  tests/unit/test_mcp_runtime.py \
  tests/integration/test_tools_routes.py -q
.venv/bin/ruff check src/data_intelligence_hub/mcp_runtime/tools/discovery.py tests/unit/test_mcp_tools_b5.py tests/unit/test_mcp_runtime.py tests/integration/test_tools_routes.py
```

- [ ] **Step 6: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py apps/api/tests/unit/test_mcp_tools_b5.py apps/api/tests/unit/test_mcp_runtime.py apps/api/tests/integration/test_tools_routes.py
git commit -m "fix(mcp): project inspect through the public tool view"
```

---

### Task 5: 报告 build/verify 共用输入 ID 解析器

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/report_artifacts.py:170-278`
- Test: `apps/api/tests/unit/test_report_artifacts.py`

**Interfaces:**
- Produces:

```python
def _resolve_input_ids(
    contract: ContractInput,
    *,
    run_id: uuid.UUID | str | None,
    run_ids: Iterable[uuid.UUID | str] | None = None,
    evidence_ids: Iterable[uuid.UUID | str] | None = None,
) -> tuple[Iterable[uuid.UUID | str], Iterable[uuid.UUID | str]]: ...
```

`verify_artifact` 新增 keyword-only `run_ids=None`、`evidence_ids=None`；旧四参数调用完全兼容。

- [ ] **Step 1: impact**

```bash
node .gitnexus/run.cjs impact build_artifact --direction upstream --repo . --file apps/api/src/data_intelligence_hub/services/report_artifacts.py
node .gitnexus/run.cjs impact verify_artifact --direction upstream --repo . --file apps/api/src/data_intelligence_hub/services/report_artifacts.py
```

记录所有 caller；`create_report` 的完整合同路径必须保持 green。

- [ ] **Step 2: 写真实 RED**

新增测试：

```python
def test_build_and_verify_agree_when_contract_ledger_is_empty() -> None: ...
def test_empty_ledger_survives_repository_round_trip() -> None: ...
def test_verify_accepts_matching_explicit_input_ids() -> None: ...
def test_verify_does_not_invent_ids() -> None: ...
```

空 ledger + `artifact.run_id` round-trip 当前应报 `data_sha256` mismatch。explicit overrides 必须在 verify 传同一 ids 后返回 `[]`；不传 ids 仍报 mismatch。

- [ ] **Step 3: 运行 RED**

```bash
.venv/bin/python -m pytest tests/unit/test_report_artifacts.py -k 'empty_ledger or explicit_input_ids or invent_ids' -q
```

- [ ] **Step 4: 实现共享 resolver**

按 Interfaces 的签名实现 `_resolve_input_ids`。build 和 verify 都必须调用它；verify 使用 `artifact.run_id` fallback。

- [ ] **Step 5: CHARACTERIZATION guard（当前应通过）**

在 `test_mcp_tools_b5.py` 新增 `test_create_report_rejects_empty_run_ledger`：合同 `run_ledger=[]`、`evidences=[]`，断言 `report_run_not_in_contract` 且 DB 中 `ReportArtifact` 行数为 0。这个测试不是 RED；若在实现前不通过，停止并重新设计。

- [ ] **Step 6: GREEN**

```bash
.venv/bin/python -m pytest tests/unit/test_report_artifacts.py tests/unit/test_mcp_tools_b5.py -q
.venv/bin/ruff check src/data_intelligence_hub/services/report_artifacts.py tests/unit/test_report_artifacts.py tests/unit/test_mcp_tools_b5.py
```

- [ ] **Step 7: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/report_artifacts.py apps/api/tests/unit/test_report_artifacts.py apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "fix(reports): make build and verify share one input-id resolver"
```

---

### Task 6: 恢复 list_capabilities 旧行语义与旧字段

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:178-213`
- Test: `apps/api/tests/unit/test_mcp_tools_b5.py`
- Test: `apps/api/tests/unit/test_catalog_digest_parity.py`

**Interfaces:**
- Consumes: `PlatformPackage.endpoints`、`ToolDescriptor` catalog、`_public_endpoint_payload`。
- Produces: 每个平台按 package endpoint 行返回；保留新字段，同时在顶层恢复旧 18-key 行字段；`status` 恢复 endpoint status 语义。

- [ ] **Step 1: impact + UNKNOWN**

```bash
node .gitnexus/run.cjs impact list_capabilities --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
rg -n 'list_capabilities' apps/api apps/scraper-console docs
```

若 impact UNKNOWN，记录 riskNote 和文本 caller。

- [ ] **Step 2: 写真实 RED**

新增：

```python
@pytest.mark.parametrize(
    ("platform_id", "count"),
    [("rss", 19), ("web", 69), ("regulatory", 4), ("tiktok", 39)],
)
async def test_list_capabilities_platform_row_counts(...): ...
```

新增 `status="disabled"` 基线：rss=9、web=2、pypi=1。冻结旧字段集合：

```python
LEGACY_KEYS = {
    "capability_id", "canonical_capability_id", "content_type", "cost_hint",
    "description", "endpoint_type", "is_alias_view", "label", "method", "notes",
    "optional_params", "param_fields", "platform", "provider", "provider_group",
    "provider_label", "required_params", "status",
}
```

遍历 70 平台，任何 `endpoint_count>0` 的平台不得返回空列表。

- [ ] **Step 3: 运行 RED**

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_tools_b5.py -k list_capabilities -q
```

Expected: rss=0、web=63、regulatory=1，失败。

- [ ] **Step 4: 最小实现**

保留 `package = await get_platform_package(platform_id)`。按 `package.endpoints` 遍历。按当前 platform 建 `descriptor` lookup；有 descriptor 时先生成 `_public_endpoint_payload(descriptor)`，再覆盖 endpoint 的旧字段；无 descriptor 时使用 `_public_endpoint_payload(endpoint)` 并补 `tool_id=endpoint.endpoint_type`。

**合并优先级是绑定契约：`LEGACY_KEYS` 中 endpoint 值必须覆盖 descriptor 值。** `web/generic_web` 的 `description`、`is_alias_view` 和 `regulatory/public_feed` 的 `label` 都必须来自平台 endpoint 行，不得被 canonical descriptor 覆盖。

旧字段必须保持顶层，不放到 nested `legacy`。新字段仍保留。`status` filter 对 `endpoint.status` 生效。测试使用 `LEGACY_KEYS <= set(row)` 的子集语义；fallback 行允许额外 `tool_id`。新增已知冲突行断言，确认 endpoint 旧值胜出。

不改 `tool_catalog/projection.py`，不改变 digest。

- [ ] **Step 5: GREEN 与 digest**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_mcp_tools_b5.py \
  tests/unit/test_catalog_digest_parity.py -q
uv run python ../../scripts/test_tool_catalog.py
uv run python ../../scripts/test_platform_packages.py
```

Expected: 39 tools；digest 和 284/284/226、70/312/284 不变。

- [ ] **Step 6: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/tests/unit/test_mcp_tools_b5.py apps/api/tests/unit/test_catalog_digest_parity.py
git commit -m "fix(mcp): restore per-platform capability rows"
```

---

### Task 7: 恢复 get_playbook markdown 兼容别名

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py:264-307`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py:223-257`
- Test: `apps/api/tests/unit/test_mcp_tools_b5.py`

**Interfaces:**
- Produces: structured playbook 保持全部新字段，新增 `markdown` 和 `deprecated_fields=["markdown"]`。

- [ ] **Step 1: impact**

```bash
node .gitnexus/run.cjs impact structured_playbook --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py
node .gitnexus/run.cjs impact get_playbook --direction upstream --repo . --file apps/api/src/data_intelligence_hub/mcp_runtime/server.py
```

- [ ] **Step 2: 写真实 RED**

修改现有 `assert "markdown" not in structured` 为：

```python
expected_markdown = await get_platform_playbook("tiktok")
assert structured["markdown"] == expected_markdown
assert structured["deprecated_fields"] == ["markdown"]
```

Expected: 当前无 markdown，失败。

- [ ] **Step 3: 实现**

`structured_playbook` 已有 `markdown` 变量；在返回值加入：

```python
"markdown": markdown,
"deprecated_fields": ["markdown"],
```

保留 server 对 capability `policy_block_reason` 的移除。`describe_capability` 保留 `endpoint_type`，只把错误注释改为“与 `tool_id` 同值的兼容别名”，不得声称 base caller 已使用。

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/unit/test_mcp_tools_b5.py -k 'playbook or describe_capability' -q
```

- [ ] **Step 5: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/tools/discovery.py apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "fix(mcp): restore get_playbook markdown alias"
```

---

### Task 8: 修正 C0/R0 证据与记录 MCP 兼容窗口

**Files:**
- Modify: `docs/ops/pg0-baseline-c0-2026-10-22.md`
- Modify: `docs/ops/pg0-ruff-cleanup-2026-10-22.md`
- Modify: `docs/ops/pg0-s0-hardening-2026-10-24.md`

**Interfaces:**
- Consumes: Tasks 1-7 的最终行为和真实计数。
- Produces: 无误导的 release evidence；v1 非推广状态；S0 修复清单。

- [ ] **Step 1: impact + 文本确认**

对三个 Markdown File 运行 upstream impact。UNKNOWN 时用 `rg` 确认只有计划/证据引用，无代码引用。

- [ ] **Step 2: 修正工具增量和兼容性变化**

C0 证据第 2 节改为：

```text
集成后净增 MCP 工具（f0560ca..S0）：create_report、discover、inspect；36 → 39。
get_run/list_records/stop/balance 在 f0560ca 已存在，不是新增工具。
```

另列兼容性：`get_playbook` 恢复 markdown alias；`list_capabilities` 恢复 endpoint 行和旧字段；`inspect` 改用 public projection；`create_report` 是新 surface，无 legacy shape。

- [ ] **Step 3: 修正 release 事实**

- Console：`SCRAPY_PUBLIC_URL` 是 compose build arg，只在重新构建时注入，不是运行时 override。
- Ruff：748 entries = 747 `.py` + `pyproject.toml`；line-length=100。
- R0 Ruff 负控使用：

```bash
ruff check /tmp/probe.py --select E501 --config apps/api/pyproject.toml --no-cache
```

记录 `> 100`，不得出现默认 `> 88`。
- 分支 compare：记录真实命令、base、files、risk；若 CLI 后端 1000-list cap 导致 truncated，明确“计数/risk 完整，列表不完整”，不得写 clean。

- [ ] **Step 4: 修正 CI 风险**

把 CI 风险拆成：

```text
R2a API Quality Gate 的 file integrity step 工作目录错误。
R2b API job 无 DB 却运行 full pytest 和默认 guard。
R2c Platform Skill And MCP Gate 无 DB 却包含 integration route test。
R2d Workflow Planner/Lineage PostgreSQL jobs 的 current-head guard pin 陈旧。
```

所有 CI 结论标为 `main-lineage`；S0 分支未 push，无分支 CI 证据。

- [ ] **Step 5: 写 S0 证据**

记录 Critical/Important 修复、测试、mypy non-regression、catalog/schema 不变、v1 immutable、未 push、未生产操作。安全写入并验证字节。

同时纠正 Task 0 点时证据：计划从未固定 `2495`；Task 0 建索引时工作树已含未提交 plan，因此 45,266 不是纯 `0c11c2b` Git tree；mypy 123 行错误码分布补齐 `attr-defined`、`import-not-found`、`assignment` 各 1；Task 0 的 15-symbol detect 数是点时输出，不作为耐久总数。

- [ ] **Step 6: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/ops/pg0-baseline-c0-2026-10-22.md docs/ops/pg0-ruff-cleanup-2026-10-22.md docs/ops/pg0-s0-hardening-2026-10-24.md
git commit -m "docs(ops): correct C0 compatibility and release evidence"
```

---

### Task 9: 修复 CI、mypy multiset 与 current-head guards

### Files

- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify-capability-governance-migration.sh`, `scripts/verify-workflow-action-migration.sh`, `scripts/verify-workflow-execution-migration.sh`, `scripts/verify-workflow-executor-migration.sh`, `scripts/verify-workflow-lineage-migration.sh`, `scripts/verify-workflow-planner-phase2-migration.sh`
- Modify: `apps/api/tests/unit/test_capability_governance_postgres_guard.py`, `test_workflow_action_postgres_guard.py`, `test_workflow_execution_postgres_guard.py`, `test_workflow_executor_postgres_guard.py`, `test_workflow_lineage_postgres_guard.py`
- Modify: `apps/api/tests/postgres/test_workflow_plan_migration.py`, `apps/api/tests/postgres_workflow_lineage/test_migration.py`, `apps/api/tests/postgres_workflow_lineage/test_materialization.py`, `apps/api/tests/postgres_capability_governance/test_migration.py`, `apps/api/tests/postgres_workflow_execution/test_migration.py`
- Modify: `apps/api/tests/postgres_workflow_lineage/conftest.py` — extract `_seed_lineage_graph` and add the `_at_034` fixtures (Step 7)
- Create: `scripts/check_mypy_baseline.py`, `apps/api/tests/unit/test_mypy_baseline_guard.py`, `apps/api/tests/unit/test_migration_head_pins.py`, `apps/api/tests/unit/test_ci_gate_contract.py`
- Delete (git rm): `scripts/verify-workflow-planner-phase2-migration.sh.bak`

### Interfaces

```python
# scripts/check_mypy_baseline.py
CURRENT_HEAD = "202610210057"          # read-only constant used by tests, not by the helper
def normalize_diagnostics(stderr_stdout: str) -> Counter[str]   # raises UnparsableLine
def compare(baseline: Counter[str], current: Counter[str]) -> tuple[list[tuple[str,int,int]], list[tuple[str,int,int]]]
    # returns (regressions, decreases); regressions = new signature or current_count > baseline_count
def main(argv: list[str] | None = None) -> int                  # 0 ok, 1 regression, 2 invalid
```

CLI (exact):

```
python scripts/check_mypy_baseline.py --baseline PATH --path TARGET [--path TARGET ...]
                                     [--api-dir DIR] [--python EXE]
```

- `--baseline` required, single. Relative paths resolve against the **caller's** cwd at startup.
- `--path` repeatable, required, forwarded verbatim to mypy as positional targets.
- `--api-dir` default `<repo>/apps/api`, where `<repo> = Path(__file__).resolve().parents[1]`.
- `--python` default `sys.executable`.
- No `--update` / no baseline write path anywhere. The helper must be incapable of re-baselining.
- Exit codes: `0` clean; `1` regression (any count increase or new signature); `2` invalid (missing/unparsable baseline, unparsable mypy line, mypy exit not in {0, 1}). Exit 2 must never be reported as success.

### Output (exact, stdout)

Success prints exactly one line:

```
OK: mypy baseline non-regression current=<current_total> baseline=<baseline_total> decreased=<decreased_total>
```

- `baseline_total` / `current_total` are **instance** totals (the sum of every count), not signature counts. For the two tracked baselines they are `1200` (`--path src --path tests`) and `123` (`--path src`).
- `decreased_total` is the summed drop over signatures whose count went down.
- Regression (exit 1) keeps the same three fields and replaces the `OK:` prefix with `REGRESSION:`, then prints one `  <signature> baseline=<n> current=<m>` line per regression.
- Invalid input (exit 2) replaces the prefix with `INVALID:` and prints the reason.
- stdout carries only these lines; nothing else. Diagnostics go to stderr.

### Baseline file format (multiset v1)

```
<count>\t<normalized-signature>\n
```

- One record per line, `count` = positive decimal integer, single TAB separator, signature is everything after the first TAB.
- Signature = `<repo-relative-path>:LINE: error: <message>` where `<message>` keeps its trailing ` [error-code]`. Line **and column** are collapsed to the literal `LINE`; `note:` lines and the `Found N errors ...` summary are dropped.
- Sorted by signature in UTF-8 byte order; LF only; exactly one trailing LF; no header, no blank lines, no comments; ASCII only.
- Duplicate signature lines are invalid (exit 2). Parsing is order-insensitive (Counter), sorting exists only for byte stability and reviewability.

### mypy invocation (cwd-independent)

```
[python, "-m", "mypy", *paths, "--no-incremental", "--no-pretty", "--show-error-codes", "--no-error-summary"]
cwd=<api_dir resolved absolute>
```

`cwd` is fixed to `--api-dir`, never inherited from the caller, so `mypy_path = "src"` and `apps/api/pyproject.toml` always resolve. Only exit codes 0 and 1 are accepted; stderr and stdout are combined and parsed; any line containing `" error: "` that does not match `^(?P<path>[^:\n]+):(?P<line>\d+):(?: (?P<col>\d+):)? error: (?P<msg>.*)$` aborts with exit 2 (fail closed, no silent dropping).

### Steps

**Step 1: impact**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs impact check_mypy_baseline --direction upstream --repo .
for f in scripts/verify-capability-governance-migration.sh scripts/verify-workflow-action-migration.sh \
         scripts/verify-workflow-execution-migration.sh scripts/verify-workflow-executor-migration.sh \
         scripts/verify-workflow-lineage-migration.sh scripts/verify-workflow-planner-phase2-migration.sh; do
  node .gitnexus/run.cjs impact "$(basename "$f")" --direction upstream --repo . --file "$f"
done
```

Expected: LOW/UNKNOWN. UNKNOWN is confirmed by text search over `.github/workflows/ci.yml` and `apps/api/tests/unit/*postgres_guard.py`. No global revision replacement.

**Step 2: RED — CI contract test**

Write `apps/api/tests/unit/test_ci_gate_contract.py` (plain-text assertions on `Path(__file__).parents[4] / ".github/workflows/ci.yml"`, same style as `test_ci_no_unscoped_real_e2e.py`; do not add a YAML dependency). Assertions:

```text
api job: "Check file integrity" step has working-directory: .
api job: pytest step is "uv run pytest tests/unit"
api job: guard step is "...check_pytest_baseline.py --path tests/unit"
api job: step "Mypy (non-regression)" runs "...check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests"
api job: "uv run mypy" appears in no step, and no step name is exactly "Mypy"
platform-packages job: test list contains none of tests/integration/**; specifically not tests/integration/test_platform_package_routes.py
```

**Step 3: RED — head pins**

`test_migration_head_pins.py` computes the head with `subprocess.run([sys.executable, "-m", "alembic", "heads"], cwd=API_ROOT, capture_output=True, text=True)` (no `DATABASE_URL`), asserts exactly one non-empty line, and pins the expected value `202610210057` in the test itself (a change of head must edit this test — that is the point). Then it asserts every current-head occurrence:

```text
# the six verify scripts, named explicitly -- never the scripts/*.sh glob
scripts/verify-capability-governance-migration.sh
scripts/verify-workflow-action-migration.sh
scripts/verify-workflow-execution-migration.sh
scripts/verify-workflow-executor-migration.sh
scripts/verify-workflow-lineage-migration.sh
scripts/verify-workflow-planner-phase2-migration.sh

# in each of those six files
grep -Eq '^<HEAD> \(head\)$'
"expected exactly one Alembic head at <HEAD>"
"alembic head check passed: <HEAD>"            (allow the optional "source " infix)

# verify-workflow-lineage-migration.sh cleanup only
'uv run alembic upgrade <HEAD>' and revision != "<HEAD>" and "cleanup passed: head <HEAD>"

# four dedicated suites
'heads == ["<HEAD> (head)"]' and the companion revision assertion immediately after it

# tracked backup files
no tracked path matching scripts/*.bak (git ls-files) and no such file on disk
```

The glob is deliberately not used: `scripts/` holds 27 shell scripts, and only these six carry an `expected exactly one Alembic head` pin. `verify-mvp.sh` and `verify-browser-production-metadata-gate.sh` do not, so a glob-based assertion would fail on them.

Explicitly out of scope for this test (must stay untouched): `202607160033`, `202607170034`, `202607270043`, `202607280044` where used as `alembic upgrade/downgrade` targets, `downgrade refused:` message strings, `module.revision`/`down_revision` in the `test_*_migration_source.py` family, and the executor candidate label `202607280044` in exactly two places that must stay in lockstep — `scripts/verify-workflow-executor-migration.sh` `REVISION` (line 39) and `apps/api/tests/postgres_workflow_executor/conftest.py` `REVISION` (line 32), together with every `revision-202607280044` string derived from them.

**Step 4: RED — helper tests**

`test_mypy_baseline_guard.py` with a fake interpreter shim (a small executable written to `tmp_path`, passed via `--python`) that records `os.getcwd()` and emits a canned diagnostic block. Cases:

```text
1 normalization: line:col collapse; "note:" and "Found ... errors" dropped; two identical diagnostics -> count 2
2 decrease allowed: baseline count 3, current 2 -> exit 0, printed as decreased
3 count increase on an existing signature (2 -> 3) -> exit 1   (the gap-2 regression)
4 brand-new signature -> exit 1
5 signature entirely absent -> exit 0
6 mypy exit 2 (usage error) -> helper exits 2, never 0
7 cwd independence: invoke from repo root with --api-dir <tmp>/apps/api; shim records cwd == that absolute path
8 malformed baseline (duplicate signature, count 0, missing TAB) -> exit 2
```

**Step 5: RED — run the suites and the two CI jobs**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
.venv/bin/python -m pytest \
  tests/unit/test_capability_governance_postgres_guard.py \
  tests/unit/test_workflow_action_postgres_guard.py \
  tests/unit/test_workflow_execution_postgres_guard.py \
  tests/unit/test_workflow_executor_postgres_guard.py \
  tests/unit/test_workflow_lineage_postgres_guard.py \
  tests/unit/test_migration_head_pins.py \
  tests/unit/test_mypy_baseline_guard.py \
  tests/unit/test_ci_gate_contract.py -q
```

Expected: failures in the five guard tests (stale head), the two new tests, and the CI contract test.

**Step 6: RED — rehearse the two red CI PostgreSQL jobs locally (disposable postgres:15)**

Run this block verbatim; it mirrors the CI service containers (`POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, CI database names, CI healthcheck) but binds loopback-only on non-production ports. It never touches 5432, the `data-intel` compose DB, or any shared database.

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
set -u
docker rm -f s0-ci-rehearsal-planner-pg s0-ci-rehearsal-lineage-pg >/dev/null 2>&1 || true

docker run -d --name s0-ci-rehearsal-planner-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=data_scrapy_workflow_plan_phase2_test \
  -p 127.0.0.1:55451:5432 postgres:15
docker run -d --name s0-ci-rehearsal-lineage-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=data_scrapy_ci_workflow_lineage_test \
  -p 127.0.0.1:55452:5432 postgres:15

for i in $(seq 1 60); do
  docker exec s0-ci-rehearsal-planner-pg pg_isready -U postgres -d data_scrapy_workflow_plan_phase2_test >/dev/null 2>&1 \
   && docker exec s0-ci-rehearsal-lineage-pg pg_isready -U postgres -d data_scrapy_ci_workflow_lineage_test >/dev/null 2>&1 \
   && break; sleep 1
done
```

Job A (mirrors `workflow-planner-postgres`, CI lines 179-183):

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55451/data_scrapy_workflow_plan_phase2_test' \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
bash scripts/verify-workflow-planner-phase2-migration.sh
echo "planner_rc=$?"
```

Job B (mirrors `workflow-lineage-postgres`, CI lines 226-231):

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED=true \
WORKFLOW_LINEAGE_TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55452/data_scrapy_ci_workflow_lineage_test' \
WORKFLOW_LINEAGE_AUTHORIZED_TARGET='127.0.0.1:55452/data_scrapy_ci_workflow_lineage_test' \
bash scripts/verify-workflow-lineage-migration.sh
echo "lineage_rc=$?"
```

Expected RED: both exit `1` at the source-head guard before pytest runs —
`error: expected exactly one Alembic head at 202607160033` and
`error: expected exactly one Alembic head at 202607170034`.

Cleanup (always, even on RED):

```bash
docker rm -f s0-ci-rehearsal-planner-pg s0-ci-rehearsal-lineage-pg >/dev/null 2>&1 || true
docker ps -a --filter name=s0-ci-rehearsal --format '{{.Names}}'   # expect empty
lsof -nP -iTCP:55451 -sTCP:LISTEN; lsof -nP -iTCP:55452 -sTCP:LISTEN  # expect empty
```

**Step 7: minimal implementation**

`.github/workflows/ci.yml`:

```yaml
  api:
    steps:
      - name: Check file integrity
        working-directory: .            # job default is apps/api; the script lives at repo root
        run: python3 scripts/check_file_integrity.py
      ...
      - name: Mypy (non-regression)     # replaces "uv run mypy src tests"; there is no second mypy step
        run: uv run python ../../scripts/check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
      - name: Pytest
        run: uv run pytest tests/unit
      - name: Pytest regression guard (unit scope)
        run: uv run python ../../scripts/check_pytest_baseline.py --path tests/unit
```

`platform-packages` job: delete the `tests/integration/test_platform_package_routes.py` line from the `Run package and MCP tests` list (job has no DB; the file needs 5432). Leave that job's `Check file integrity` step without `working-directory` — it already resolves at repo root.

Six scripts — current-head only:

| script | occurrences to change → `202610210057` |
|---|---|
| `verify-capability-governance-migration.sh` | 101, 102, 106 |
| `verify-workflow-action-migration.sh` | 106, 107, 111 |
| `verify-workflow-execution-migration.sh` | 115, 116, 120 |
| `verify-workflow-executor-migration.sh` | 138, 139, 143 only. **`REVISION` at line 39 stays `202607280044`** — it builds the `revision-<REVISION>` component of the authorization tuple, which `conftest.py:32` hardcodes; the head pin is the live head, the `revision-` component is a fixed candidate label. Do not couple them. |
| `verify-workflow-lineage-migration.sh` | 116, 117, 121 **and** cleanup 144, 185, 214 |
| `verify-workflow-planner-phase2-migration.sh` | 98, 99, 103 |

Do not touch any historical `upgrade`/`downgrade` target or `downgrade refused:` string in these scripts.

#### Two different kinds of `202607170034` — do not conflate them

- **Fake-uv shim inside `apps/api/tests/unit/test_workflow_lineage_postgres_guard.py` (lines 188, 196, 260) — all three move to `202610210057`.** The shim stands in for the real `uv`, so its canned `alembic heads` reply and its cleanup dispatch arm must answer the commands the script actually issues. After the lineage script's cleanup is repinned to 057, a shim still answering `run alembic upgrade 202607170034` falls through to `*) exit 91`, cleanup returns 91 instead of preserving the pytest status, and `test_guard_cleanup_runs_after_success_or_failure_and_preserves_exit_status` fails its `(0,0,0)` case.
- **Real database suite `apps/api/tests/postgres_workflow_lineage/` — historical `upgrade`/`downgrade` 034 targets stay.** Those tests pin their own start revision (`_run_alembic(..., "upgrade", "202607170034")`) and then assert `_revision(...) == "202607170034"` after a refused downgrade; the literal is the fixture's contract, not the live head. Only the head pair at `test_migration.py:290-291` moves to 057.

Guard tests: five current-head assertions move to `202610210057`. `test_workflow_lineage_postgres_guard.py`: the fake-uv `alembic heads` reply at line 188 becomes `printf '%s\n' "202610210057 (head)"`, the cleanup dispatch arm at line 196 becomes `"run alembic upgrade 202610210057")`, and the `commands[2:4]` assertion at line 260 becomes `"run alembic upgrade 202610210057",`. All three move together — see the shim/suite distinction above. `test_workflow_executor_postgres_guard.py`: rename `test_guard_is_pinned_to_revision_044_without_runner_commands` → `..._to_current_head_...`, update the two head assertions at lines 174-175 to `202610210057`, and **leave `SAFE_AUTHORIZATION` (line 30) and the unsafe-override replacement (line 141) at `revision-202607280044`**. The authorization tuple is a candidate label shared with `conftest.py`, not a head pin; changing it makes the gate unsatisfiable, because the fixture rejects any tuple that disagrees with its own `REVISION` and raises `pytest.UsageError("authorization does not match the exact candidate tuple")` before connecting.

Four dedicated suites — change only the head pair:

- `tests/postgres/test_workflow_plan_migration.py:474-475` → `["202610210057 (head)"]` / `"202610210057"`
- `tests/postgres_workflow_lineage/test_migration.py:290-291` → same; rename `test_source_has_one_head_at_034` → `test_source_has_one_head_at_current_head`
- `tests/postgres_capability_governance/test_migration.py:537-538` → same
- `tests/postgres_workflow_execution/test_migration.py:329-330` → same

Historical literals in those files (lines 298-346, 385-388, 488-516, 573-600, 362-372) stay.

Known second-order breakage to fix in the same pass (triage rule below): `tests/postgres_workflow_lineage/test_migration.py::test_downgrade_refuses_persisted_v2_lineage` (defined at `:350`, asserts at `:388`) and `tests/postgres_workflow_lineage/test_materialization.py::test_downgrade_refuses_nonempty_materialization_ledger` (defined at `:276`, asserts at `:308`) start from the head-upgraded fixture. At head 057 the downgrade command is a single transaction (`alembic/env.py` does not set `transaction_per_migration`), so it now rolls back to `202610210057` instead of parking at `202607170034`. Repair by bringing those two tests up on a database already at 034 — keep every existing literal and assertion.

The repair must be a **fixture**, not inline test-body code. `seeded_lineage_graph` (`conftest.py:144-296`) resolves before the test body runs, and `postgres_database_url` (`:128-132`) has already reset the schema and upgraded to head; a reset inside the body would wipe the seed, and the subsequent `raw_records` insert would violate `fk_raw_records_workflow_run_tenant` (created by `202607160033_workflow_raw_dataset_lineage.py:57-65`). Leave `guarded_database_url`, `postgres_database_url`, `postgres_engine` and `seeded_lineage_graph` behaving as they do today — the rest of the suite, including `test_head_exposes_materialization_constraints_and_tenant_fks` (`test_materialization.py:164-166`), needs them at head.

Edit `apps/api/tests/postgres_workflow_lineage/conftest.py` in four steps:

**(a) Extract the seed body.** Move the whole body of `seeded_lineage_graph` (`:144-296`) into a module-level `_seed_lineage_graph(engine: Engine) -> LineageSeed` that takes the engine as a parameter, and reduce the fixture to a call:

```python
def _seed_lineage_graph(engine: Engine) -> LineageSeed:
    seed = LineageSeed(*(uuid.uuid4() for _ in range(9)))
    # ... existing body verbatim, with postgres_engine renamed to engine ...
    return seed


@pytest.fixture()
def seeded_lineage_graph(postgres_engine: Engine) -> LineageSeed:
    return _seed_lineage_graph(postgres_engine)
```

**(b) Add the at-034 database fixtures** beside `postgres_database_url` (`:128-141`), reusing the module-level `reset_public_schema` (`:113-120`) and `run_alembic` (`:100-110`) helpers that already live in this conftest:

```python
@pytest.fixture()
def postgres_database_at_034(guarded_database_url: str) -> str:
    reset_public_schema(guarded_database_url)
    run_alembic(guarded_database_url, "upgrade", "202607170034")
    return guarded_database_url


@pytest.fixture()
def postgres_engine_at_034(postgres_database_at_034: str) -> Iterator[Engine]:
    engine = create_engine(sync_database_url(postgres_database_at_034))
    try:
        yield engine
    finally:
        engine.dispose()
```

**(c) Add the seeded variant** that seeds onto the 034 engine through the shared helper:

```python
@pytest.fixture()
def seeded_lineage_graph_at_034(postgres_engine_at_034: Engine) -> LineageSeed:
    return _seed_lineage_graph(postgres_engine_at_034)
```

**(d) Switch exactly two tests** — `test_downgrade_refuses_persisted_v2_lineage` and `test_downgrade_refuses_nonempty_materialization_ledger` — to the three new fixtures. In their signatures replace `postgres_database_url`, `postgres_engine` and `seeded_lineage_graph` with `postgres_database_at_034`, `postgres_engine_at_034` and `seeded_lineage_graph_at_034`; change nothing inside their bodies. Every other test in `postgres_workflow_lineage/` keeps the current-head fixtures.

Schema viability: every column the two tests write comes from revisions at or before 034 — `raw_records.workflow_run_id` / `workflow_step_run_id` / `workflow_lineage_contract_version` and `dataset_versions.lineage_contract_version` / `source_workflow_run_id` / `source_workflow_step_run_ids` / `source_raw_record_ids` from `202607160033`, the fixture and actor/browser/LLM columns of `workflow_runs` and `step_runs` from `202606110029`, and `workflow_lineage_materialization_requests` itself from `202607170034`. So the seed and the ledger insert are valid at 034.

Do **not** add `_reset_public_schema` or `_run_alembic` to `test_materialization.py`: that module defines neither (`test_migration.py` keeps its own private copies at `:53-77`), and neither is a fixture. The shared helpers are the conftest ones named above.

Triage rule for anything further the rehearsal surfaces: a failure caused by "the DB/fixture is now at a different head" is fixed by pinning the test's *start* revision explicitly; a failure caused by new behavior in revisions 035-057 is out of S0 scope and must be recorded as a blocked defect, never papered over by editing the assertion to the new value. `git rm scripts/verify-workflow-planner-phase2-migration.sh.bak`.

**Step 8: GREEN**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
.venv/bin/python -m pytest \
  tests/unit/test_capability_governance_postgres_guard.py \
  tests/unit/test_workflow_action_postgres_guard.py \
  tests/unit/test_workflow_execution_postgres_guard.py \
  tests/unit/test_workflow_executor_postgres_guard.py \
  tests/unit/test_workflow_lineage_postgres_guard.py \
  tests/unit/test_migration_head_pins.py \
  tests/unit/test_mypy_baseline_guard.py \
  tests/unit/test_ci_gate_contract.py -q
.venv/bin/python ../../scripts/check_mypy_baseline.py \
  --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
.venv/bin/python ../../scripts/check_mypy_baseline.py \
  --baseline ../../configs/quality/mypy-src-signatures.txt --path src
cd /Users/lute/Project/data_scrapy-c0-s0 && python3 scripts/check_file_integrity.py
```

Expected: unit set green; both helper runs exit 0 and print exactly `OK: mypy baseline non-regression current=1200 baseline=1200 decreased=0` and `OK: mypy baseline non-regression current=123 baseline=123 decreased=0`; integrity `file integrity OK (N files)`.

Then re-run Step 6 (both jobs) and expect exit 0:

- Job A: `alembic head check passed: 202610210057` then `tests/postgres` fully green, including the renamed head test and the two downgrade-refusal tests.
- Job B: `alembic source head check passed: 202610210057`, `tests/postgres_workflow_lineage` green, then `authorized workflow lineage database cleanup passed: head 202610210057, zero rows`.

This rehearsal *is* the CI evidence: the branch is never pushed, so record it as `local rehearsal of workflow-planner-postgres / workflow-lineage-postgres; no remote CI run` in the evidence file.

**Step 9: commit**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs detect-changes --scope all --repo .
git rm --cached scripts/verify-workflow-planner-phase2-migration.sh.bak && rm -f scripts/verify-workflow-planner-phase2-migration.sh.bak
git add .github/workflows/ci.yml scripts/check_mypy_baseline.py scripts/verify-*-migration.sh \
  apps/api/tests/unit/test_*postgres_guard.py apps/api/tests/unit/test_migration_head_pins.py \
  apps/api/tests/unit/test_mypy_baseline_guard.py apps/api/tests/unit/test_ci_gate_contract.py \
  apps/api/tests/postgres/test_workflow_plan_migration.py \
  apps/api/tests/postgres_workflow_lineage/test_migration.py \
  apps/api/tests/postgres_workflow_lineage/conftest.py \
  apps/api/tests/postgres_workflow_lineage/test_materialization.py \
  apps/api/tests/postgres_capability_governance/test_migration.py \
  apps/api/tests/postgres_workflow_execution/test_migration.py
git commit -m "ci: replace mypy gate with multiset baseline and refresh current head pins"
```

Note the deliberate difference from the old plan: the `.bak` is removed from the index, never added. `configs/quality/*.txt` are **not** in this commit — they were migrated in the Task 0 fix commit. Scope check before commit: `git diff --cached --name-only | grep -E '^(apps/api/src|apps/api/alembic|configs/[^q]|apps/scraper-console|docker)'` must be empty.

---

### Task 10: S0 全量门禁、最终安全审查与本地 v2 标签

**Files:**
- Modify: `docs/ops/pg0-s0-hardening-2026-10-24.md`
- Create: local annotated tag `pg0-baseline-v2`，仅在最终审查通过后。

**Interfaces:**
- Produces: S0 完整证据、最终审查结论、可回滚的本地 v2 tag。

- [ ] **Step 1: focused suite**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
.venv/bin/python -m pytest \
  tests/unit/test_mcp_run_service.py \
  tests/unit/test_mcp_tools_b5.py \
  tests/unit/test_mcp_exa_tools.py \
  tests/unit/test_mcp_runtime.py \
  tests/unit/test_report_artifacts.py \
  tests/unit/test_catalog_digest_parity.py \
  tests/integration/test_tools_routes.py -q
```

- [ ] **Step 2: full quality gates**

```bash
.venv/bin/python -m pytest tests/unit -q
.venv/bin/ruff check . --no-cache
.venv/bin/python ../../scripts/check_mypy_baseline.py \
  --baseline ../../configs/quality/mypy-src-signatures.txt --path src
.venv/bin/python ../../scripts/check_mypy_baseline.py \
  --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
.venv/bin/python ../../scripts/check_pytest_baseline.py --path tests/unit
cd /Users/lute/Project/data_scrapy-c0-s0
python3 scripts/check_file_integrity.py
```

Expected: unit green；ruff clean；两份 mypy multiset 各打印一行且前缀为 `OK:`（`current=1200 baseline=1200 decreased=0` 与 `current=123 baseline=123 decreased=0`）；任何新签名或计数增加打印 `REGRESSION:` 并 exit 1，任何无法解析的输入打印 `INVALID:` 并 exit 2，两者都算失败；pytest guard `OK: 0 failed。`；integrity green。helper 必须固定 cwd 到 `apps/api`，从 repo root 或 `apps/api` 调用结果一致。

- [ ] **Step 2a: 六个 PostgreSQL guard 的 disposable rehearsal**

安全边界：容器前缀 `s0-gate-`，只绑定 `127.0.0.1`，不得用 5432、不得使用 compose DB、不得使用 named volume 或 `--network host`。以下整段是**一个** shell invocation：`trap` 在块内注册，任何一步失败（含某个 gate 返回非零）都会删掉六个容器。

| gate | container | port | user/password | database |
|---|---|---:|---|---|
| planner | `s0-gate-planner-pg` | 55451 | postgres/postgres | `data_scrapy_workflow_plan_phase2_test` |
| lineage | `s0-gate-lineage-pg` | 55452 | postgres/postgres | `data_scrapy_ci_workflow_lineage_test` |
| capability-governance | `s0-gate-cg-pg` | 55453 | postgres/postgres | `s0_capability_governance_test` |
| workflow-execution | `s0-gate-exec-pg` | 55454 | postgres/postgres | `s0_workflow_execution_test` |
| workflow-executor | `s0-gate-executor-pg` | 55455 | `s0_executor` / trust | `s0_workflow_executor_test` |
| workflow-action | `s0-gate-action-pg` | 55443 | `phase_e_test` / trust | `uix09_phase_e_20260728_workflow_execution_test` |

每个数据库名都满足对应脚本的后缀校验（`_workflow_plan_phase2_test`、`_workflow_lineage_test`、`_capability_governance_test`、`_workflow_execution_test`、`_workflow_executor_test`，action 脚本比对精确名）。executor 与 action 两个脚本拒绝带密码的 URL，所以那两个容器必须用 `POSTGRES_HOST_AUTH_METHOD=trust`。

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
set -euo pipefail

cleanup() {
  docker rm -f s0-gate-planner-pg s0-gate-lineage-pg s0-gate-cg-pg \
              s0-gate-exec-pg s0-gate-executor-pg s0-gate-action-pg >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# remove same-name leftovers before starting
cleanup

docker run -d --name s0-gate-planner-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=data_scrapy_workflow_plan_phase2_test \
  -p 127.0.0.1:55451:5432 postgres:15
docker run -d --name s0-gate-lineage-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=data_scrapy_ci_workflow_lineage_test \
  -p 127.0.0.1:55452:5432 postgres:15
docker run -d --name s0-gate-cg-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=s0_capability_governance_test \
  -p 127.0.0.1:55453:5432 postgres:15
docker run -d --name s0-gate-exec-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=s0_workflow_execution_test \
  -p 127.0.0.1:55454:5432 postgres:15
docker run -d --name s0-gate-executor-pg \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=s0_executor \
  -e POSTGRES_DB=s0_workflow_executor_test \
  -p 127.0.0.1:55455:5432 postgres:15
docker run -d --name s0-gate-action-pg \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=phase_e_test \
  -e POSTGRES_DB=uix09_phase_e_20260728_workflow_execution_test \
  -p 127.0.0.1:55443:5432 postgres:15

wait_pg() {
  name="$1"; user="$2"; db="$3"
  for _ in $(seq 1 60); do
    if docker exec "$name" pg_isready -U "$user" -d "$db" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  printf '%s\n' "error: $name did not accept connections within 60s" >&2
  return 1
}

wait_pg s0-gate-planner-pg  postgres    data_scrapy_workflow_plan_phase2_test
wait_pg s0-gate-lineage-pg  postgres    data_scrapy_ci_workflow_lineage_test
wait_pg s0-gate-cg-pg       postgres    s0_capability_governance_test
wait_pg s0-gate-exec-pg     postgres    s0_workflow_execution_test
wait_pg s0-gate-executor-pg s0_executor s0_workflow_executor_test
wait_pg s0-gate-action-pg   phase_e_test uix09_phase_e_20260728_workflow_execution_test

TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55451/data_scrapy_workflow_plan_phase2_test' ALLOW_DESTRUCTIVE_MIGRATION_TEST=true bash scripts/verify-workflow-planner-phase2-migration.sh

WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED=true WORKFLOW_LINEAGE_TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55452/data_scrapy_ci_workflow_lineage_test' WORKFLOW_LINEAGE_AUTHORIZED_TARGET='127.0.0.1:55452/data_scrapy_ci_workflow_lineage_test' bash scripts/verify-workflow-lineage-migration.sh

CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED=true CAPABILITY_GOVERNANCE_TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55453/s0_capability_governance_test' bash scripts/verify-capability-governance-migration.sh

WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED=true WORKFLOW_EXECUTION_TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:55454/s0_workflow_execution_test' WORKFLOW_EXECUTION_AUTHORIZED_TARGET='127.0.0.1:55454/s0_workflow_execution_test' bash scripts/verify-workflow-execution-migration.sh

WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true WORKFLOW_EXECUTOR_TEST_DATABASE_URL='postgresql+asyncpg://s0_executor@127.0.0.1:55455/s0_workflow_executor_test' WORKFLOW_EXECUTOR_AUTHORIZED_TARGET='127.0.0.1:55455/s0_workflow_executor_test' WORKFLOW_EXECUTOR_RUNNER_ID='s0-gate-runner' WORKFLOW_EXECUTOR_POSTGRES_IMAGE='postgres:15' WORKFLOW_EXECUTOR_CLEANUP_CONTRACT='destroy_exact_runner_and_prove_port_closed' WORKFLOW_EXECUTOR_AUTHORIZATION='authorize-workflow-executor-postgres-candidate:127.0.0.1:55455/s0_workflow_executor_test:revision-202607280044:runner-s0-gate-runner:image-postgres:15:cleanup-destroy_exact_runner_and_prove_port_closed' bash scripts/verify-workflow-executor-migration.sh

WORKFLOW_ACTION_POSTGRES_TEST_AUTHORIZED=true WORKFLOW_ACTION_TEST_DATABASE_URL='postgresql+asyncpg://phase_e_test@127.0.0.1:55443/uix09_phase_e_20260728_workflow_execution_test' WORKFLOW_ACTION_AUTHORIZED_TARGET='127.0.0.1:55443/uix09_phase_e_20260728_workflow_execution_test' bash scripts/verify-workflow-action-migration.sh

cleanup
trap - EXIT INT TERM

test -z "$(docker ps -a --filter name=s0-gate --format '{{.Names}}' || true)"
for port in 55443 55451 55452 55453 55454 55455; do
  test -z "$(lsof -nP -iTCP:"$port" -sTCP:LISTEN || true)"
done
printf '%s\n' "all six gates green; containers and ports released"
```

任何一个 gate 未跑到 current-head 通过并执行完对应 dedicated suite，就是该 gate 失败：整块以非零退出（`trap` 仍会清理），把失败 gate 记为 `BLOCKED`，并且**不得**继续 Step 3 之后到 Step 9 建 v2 标签的任何步骤。不得把四个 gate 绿、两个 `BLOCKED` 当成切片可交付。

- [ ] **Step 3: contracts and invariants**

```bash
uv run alembic heads
uv run python ../../scripts/test_tool_catalog.py
uv run python ../../scripts/test_platform_packages.py
cd /Users/lute/Project/data_scrapy-c0-s0
test "$(git rev-parse pg0-baseline-v1)" = "48aaccfa5a3689f23f7517cfb88b59c2533805ab"
test "$(git rev-parse pg0-baseline-v1^{commit})" = "e227070054914f9cbef8cb5d508e5f4aa73d8dcb"
test "$(git ls-files 'scripts/*.bak')" = ""
test -z "$(find scripts -name '*.bak' -print -quit)"
test "$(shasum -a 256 configs/quality/mypy-src-signatures.txt | cut -d' ' -f1)" = "4700169095b3f12445559069b42f37fdf25e1a8e8332dd3449e24a396a16576e"
test "$(shasum -a 256 configs/quality/mypy-src-tests-signatures.txt | cut -d' ' -f1)" = "9df7ee3e41ddc0352e65f01a7306654a4ca2cda0c570a20b9d4bddb68e736cf4"
```

Expected: head 057；catalog/lock/digest 不变；v1 不变。

- [ ] **Step 4: tenant probes**

以 MCP client 运行 same-workspace sibling、cross-workspace、global-token 三组：

```text
deep_research_check: foreign => run_not_found；own/global 正常。
stop: foreign => run_not_found 且状态未变；own/global 正常。
balance: foreign => project_mismatch；own/global 正常。
```

错误文本不得包含 foreign project/run id。

- [ ] **Step 5: inspect 和兼容性扫描**

- 全 284 tools 的 inspect 不含 governance 原文。
- 70 platforms 中 endpoint_count>0 的 list_capabilities 不为空。
- rss=19、web=69、regulatory=4、tiktok=39。
- get_playbook markdown 与 REST renderer 值相同。
- tool count=39。

- [ ] **Step 6: GitNexus compare**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs detect-changes --scope compare --base-ref 0c11c2b --repo .
```

若后端 1000 symbol hard cap 导致 `truncated`，按 C0 最终审查的已验证方式临时提高本地缓存工具上限，运行同版本结构化 compare，保存结果，恢复工具原 SHA。任何 `partial` 阻塞。

- [ ] **Step 7: 独立 whole-branch security review**

范围 `0c11c2b..HEAD`，至少三视角：tenant isolation、compat/contracts、CI/evidence。所有 Critical/Important 必须关闭。只记录存量 residual risks。

CI/evidence reviewer 必须确认：workflow 中不存在阻塞式 `uv run mypy`；API mypy 使用 multiset helper；API pytest/guard 只跑 unit；platform-packages 不含 integration 路径；六个 PostgreSQL guard 本地 rehearsal 全绿；四个 dedicated suite current-head 断言为 057；历史 upgrade/downgrade revision 未被全局替换。

- [ ] **Step 8: 追加并提交最终证据**

记录命令、计数、hash、tag immutability、compare、review verdict。安全写入。另记录：两份 mypy multiset 的 baseline/current/decreased；API 与 platform-packages CI contract；六个 PostgreSQL guard rehearsal 的容器名、端口、exit 和 cleanup；`.bak` 删除；`ci_evidence=local-rehearsal-only`（分支未 push，无远端 CI run）。

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/ops/pg0-s0-hardening-2026-10-24.md
git commit -m "docs(ops): record S0 hardening verification"
```

- [ ] **Step 9: 创建本地 v2 标签**

只有 Step 7 review verdict Ready/Ready with documented risks 时执行：

```bash
cd /Users/lute/Project/data_scrapy-c0-s0
test -z "$(git tag -l pg0-baseline-v2)"
BASELINE_COMMIT=$(cat /tmp/s0-reviewed-code-baseline.txt)
test "$(git diff --name-only "$BASELINE_COMMIT"..HEAD)" = "docs/ops/pg0-s0-hardening-2026-10-24.md"
git tag -a pg0-baseline-v2 "$BASELINE_COMMIT" \
  -m "PG0 baseline v2: S0 hardening; tenant isolation and MCP compatibility fixed; schema 202610210057; v1 preserved"
test "$(git rev-parse pg0-baseline-v2^{commit})" = "$BASELINE_COMMIT"
test "$(git rev-parse pg0-baseline-v1)" = "48aaccfa5a3689f23f7517cfb88b59c2533805ab"
```

标签只在本地，不 push。最终 review 通过后、写 evidence 前，把 reviewed HEAD 写入 `/tmp/s0-reviewed-code-baseline.txt`。证据提交后用 diff 断言它到当前 HEAD 只有 `docs/ops/pg0-s0-hardening-2026-10-24.md`；不得用 `HEAD^` 猜标签目标。

- [ ] **Step 10: 最终状态**

```bash
git status --porcelain -uno
git log -12 --oneline
git for-each-ref --format='%(refname) %(objectname) %(objecttype)' \
  refs/tags/pg0-baseline-v1 refs/tags/pg0-baseline-v2
```

Expected: 工作树 clean；v1 不变；v2 指向审查通过的 S0 code baseline；无 push。

## Self-Review

- Spec coverage：覆盖 3 个越权工具、report hash、inspect 泄漏、list_capabilities 行语义、get_playbook alias、证据和 CI 门禁、v1/v2 标签策略。
- Placeholder scan：无 TBD/TODO/“类似 Task N”或未定义接口。
- Type consistency：`stop_run(project_id=None)`、`verify_artifact(run_ids=None, evidence_ids=None)`、`inspect` key set、list_capabilities 旧字段、playbook markdown alias 在各任务一致。
- Scope consistency：无 migration/model/catalog projection/Console/Docker 改动；CI 脚本只改 current-head 断言；四个 dedicated suite 也只改 current-head 断言（`postgres/test_workflow_plan_migration.py:474-475`、`postgres_workflow_lineage/test_migration.py:290-291`、`postgres_capability_governance/test_migration.py:537-538`、`postgres_workflow_execution/test_migration.py:329-330`）；`postgres_workflow_lineage/` 额外新增 `postgres_database_at_034`、`postgres_engine_at_034`、`seeded_lineage_graph_at_034` 三个 fixture，只把两个 downgrade-refusal 测试的**起始 revision**钉到 034，不放宽也不改写它们的期望值；历史 upgrade/downgrade revision 全部不变。
- Safety：所有 production/tag/remote 操作均禁止；v1 immutable；v2 只在最终 review 后本地创建。
