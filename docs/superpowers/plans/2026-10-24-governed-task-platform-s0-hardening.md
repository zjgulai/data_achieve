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
| `configs/quality/mypy-src-signatures.txt` | Task 0 冻结的 `mypy src` 62 个唯一签名。 |
| `configs/quality/mypy-src-tests-signatures.txt` | Task 0 冻结的 `mypy src tests` 498 个唯一签名，供 CI non-regression。 |
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
configs/quality/mypy-src-signatures.txt              # 62 行；SHA-256 db46d230...
configs/quality/mypy-src-tests-signatures.txt        # 498 行；SHA-256 718ca252...
```

两份文件是 Task 0 冻结基线；Task 1-10 不得重新生成或放宽。后续门禁只允许当前签名集合是基线子集，不允许新增。

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

### Task 9: 修复 CI 测试范围与当前 Alembic head guard

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify-capability-governance-migration.sh`
- Modify: `scripts/verify-workflow-action-migration.sh`
- Modify: `scripts/verify-workflow-execution-migration.sh`
- Modify: `scripts/verify-workflow-executor-migration.sh`
- Modify: `scripts/verify-workflow-lineage-migration.sh`
- Modify: `scripts/verify-workflow-planner-phase2-migration.sh`
- Modify: `apps/api/tests/unit/test_capability_governance_postgres_guard.py`
- Modify: `apps/api/tests/unit/test_workflow_action_postgres_guard.py`
- Modify: `apps/api/tests/unit/test_workflow_execution_postgres_guard.py`
- Modify: `apps/api/tests/unit/test_workflow_executor_postgres_guard.py`
- Modify: `apps/api/tests/unit/test_workflow_lineage_postgres_guard.py`
- Create: `apps/api/tests/unit/test_migration_head_pins.py`
- Create: `apps/api/tests/unit/test_mypy_baseline_guard.py`
- Create: `scripts/check_mypy_baseline.py`
- Delete: `scripts/verify-workflow-planner-phase2-migration.sh.bak`

**Interfaces:**
- Produces: 无 PostgreSQL 的 jobs 只运行 unit；API mypy 使用 tracked signature baseline 做 non-regression；migration guard 的“当前头”统一为 `202610210057`；历史迁移路径 revision 不变。

- [ ] **Step 1: impact**

对六个脚本 File 运行 impact。UNKNOWN 用文本搜索确认 workflow 和 unit tests。不得使用全局替换 revision。

- [ ] **Step 2: 写 CI RED 测试**

新增/扩展 unit tests 读取 `.github/workflows/ci.yml`，断言：

```text
API Check file integrity: working-directory = .
API Pytest: uv run pytest tests/unit
API guard: ...check_pytest_baseline.py --path tests/unit
API Mypy: ...check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
Platform Skill And MCP Gate: 不包含 tests/integration/test_platform_package_routes.py，或该 job 配置 PostgreSQL service + DATABASE_URL。首选移除 integration 文件，因该 job 无 DB。
```

- [ ] **Step 3: 写 head pin RED**

新增 `test_migration_head_pins.py`：解析 `uv run alembic heads` 的唯一 head `202610210057`；检查六个 `.sh` 脚本的 current-head error/success/grep 断言使用该值；断言仓库不再跟踪 `verify-*.sh.bak`。

只检查 current-head guard，不检查脚本内部历史 upgrade/downgrade revision。新增 `test_mypy_baseline_guard.py`，覆盖 normalization、允许 removed signatures、拒绝 added signatures、非 0/1 mypy exit 失败。

- [ ] **Step 4: 运行 RED**

```bash
cd /Users/lute/Project/data_scrapy-c0-s0/apps/api
.venv/bin/python -m pytest \
  tests/unit/test_capability_governance_postgres_guard.py \
  tests/unit/test_workflow_action_postgres_guard.py \
  tests/unit/test_workflow_execution_postgres_guard.py \
  tests/unit/test_workflow_executor_postgres_guard.py \
  tests/unit/test_workflow_lineage_postgres_guard.py \
  tests/unit/test_migration_head_pins.py \
  tests/unit/test_mypy_baseline_guard.py -q
```

Expected: stale pin 和 CI assertions 失败。

- [ ] **Step 5: 最小实现**

`.github/workflows/ci.yml`：

```yaml
- name: Check file integrity
  working-directory: .
  run: python3 scripts/check_file_integrity.py
...
- name: Mypy baseline (non-regression)
  run: uv run python ../../scripts/check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
...
- name: Pytest
  run: uv run pytest tests/unit
- name: Pytest regression guard (unit scope)
  run: uv run python ../../scripts/check_pytest_baseline.py --path tests/unit
```

platform-packages job 从测试列表删除 `tests/integration/test_platform_package_routes.py`；该 integration 已由有 DB 的本地门禁覆盖，CI 无 DB 时不运行。

六个脚本只替换 `alembic heads` 校验和对应 success/error message 的 expected head 为 `202610210057`。不要替换历史 `alembic upgrade/downgrade` revision、authorization packet revision 或 dedicated suite 内部断言。

五个 guard tests 更新 current-head 字符串。`test_workflow_lineage_postgres_guard.py` 的 fake `uv` 返回值改为 `202610210057 (head)`；它的历史 `alembic upgrade/downgrade 202607160033/202607170034` 与 cleanup assertions 保持不变。`test_workflow_executor_postgres_guard.py` 的 authorization revision `202607280044` 也保持不变。删除 tracked 的陈旧 `.bak`。

- [ ] **Step 6: GREEN**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_capability_governance_postgres_guard.py \
  tests/unit/test_workflow_action_postgres_guard.py \
  tests/unit/test_workflow_execution_postgres_guard.py \
  tests/unit/test_workflow_executor_postgres_guard.py \
  tests/unit/test_workflow_lineage_postgres_guard.py \
  tests/unit/test_migration_head_pins.py \
  tests/unit/test_mypy_baseline_guard.py -q
cd /Users/lute/Project/data_scrapy-c0-s0
python3 scripts/check_file_integrity.py
```

再用 YAML/文本聚焦检查 workflow 命令，不触发远端 CI。

- [ ] **Step 7: 提交**

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add .github/workflows/ci.yml scripts/check_mypy_baseline.py scripts/verify-*-migration.sh scripts/verify-workflow-planner-phase2-migration.sh.bak configs/quality/mypy-src-signatures.txt configs/quality/mypy-src-tests-signatures.txt apps/api/tests/unit/test_*postgres_guard.py apps/api/tests/unit/test_migration_head_pins.py apps/api/tests/unit/test_mypy_baseline_guard.py
git commit -m "ci: unblock api gates and refresh current head pins"
```

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
set +e
.venv/bin/python -m mypy src > /tmp/s0-mypy-final.txt 2>&1
MYPY_RC=$?
set -e
test "$MYPY_RC" -eq 1
```

运行 `python ../../scripts/check_mypy_baseline.py --baseline ../../configs/quality/mypy-src-signatures.txt --path src`，并使用 full baseline 对 `src tests` 再跑一次；两者 new=0。允许诊断减少，不允许 Task 1-9 的错误被重新取基线洗掉。

- [ ] **Step 3: contracts and invariants**

```bash
uv run alembic heads
uv run python ../../scripts/test_tool_catalog.py
uv run python ../../scripts/test_platform_packages.py
cd /Users/lute/Project/data_scrapy-c0-s0
test "$(git rev-parse pg0-baseline-v1)" = "48aaccfa5a3689f23f7517cfb88b59c2533805ab"
test "$(git rev-parse pg0-baseline-v1^{commit})" = "e227070054914f9cbef8cb5d508e5f4aa73d8dcb"
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

- [ ] **Step 8: 追加并提交最终证据**

记录命令、计数、hash、tag immutability、compare、review verdict。安全写入。

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
- Scope consistency：无 migration/model/catalog projection/Console/Docker 改动；CI 脚本只改 current-head guard，不改历史 revision。
- Safety：所有 production/tag/remote 操作均禁止；v1 immutable；v2 只在最终 review 后本地创建。
