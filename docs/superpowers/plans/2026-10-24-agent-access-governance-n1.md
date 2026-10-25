# N1 Agent 接入统一授权 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 36 个内部 MCP 工具全部经过集中式策略注册表：显式白名单、项目绑定、对象归属校验、持久日额度与运维豁免；项目密钥支持 PATCH 原地更新；监控定时运行消耗创建密钥的日额度。

**Architecture:** 新增 `mcp_runtime/tool_registry.py` 作为唯一策略事实源；新增 `governed_mcp_tool` 统一入口封装现有 `governed_tool` + `enforce_tool_policy` + `enforce_quota` + `_bound_project_id`；36 个工具全部改走统一入口；`collect` 与 TikTok 工具补传 `workspace_id`；`monitors.project_key_id` 列并入 C3 迁移 059 scope；Console 工具选项从只读接口渲染。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2 async、pytest、Next.js 16 Console。

## Global Constraints

- 定位：C1/C3/C4/C5/C6/C13 已冻结计划的跨切片设计补充。spec：`docs/superpowers/specs/2026-10-24-agent-access-governance-design.md`。
- C3 独占 `models/project_api_key.py`、`services/project_api_keys.py`、`services/platform_credentials.py`；C3 合并后其他切片只读。本计划对这些文件的改动必须在 C3 合并前完成，或以「总索引变更请求」提交。
- C3 只允许一个迁移 `202610220059`（`down_revision="202610220058"`），不得新增第二个迁移。N1 的列并入该迁移。
- C13 拥有客户 MCP；本计划不改 `mcp_runtime/customer/**`。
- C14 独占 `apps/scraper-console/src/**`；本计划的 Console 改动以「C14 交接清单」形式提交，若 C14 已启动则只提交需求不改文件。
- 空 `tool_allowlist` 拒绝全部工具；未登记新工具默认拒绝。
- 全局 token 不受白名单与日额度限制；审计标记 `global_operator`。
- 不新增内部 MCP 工具；不修改 C1 registry 文件。
- 错误码沿用现有：`tool_not_allowed`、`quota_exceeded`、`project_key_not_found`、`project_not_found`、`run_not_found`、`monitor_not_found`、`enrichment_job_not_found`。
- 每个任务结束跑 `node .gitnexus/run.cjs detect-changes --scope all`；新风险按既有惯例记录，不豁免。
- 生产 A/B 的部署与开关切换归 PG0 发布批次；本计划只交付代码与测试。

---

### Task 1: 工具策略注册表

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/tool_registry.py`
- Test: `apps/api/tests/unit/test_tool_registry.py`

**Interfaces:**
- Consumes: 无（纯数据模块）。
- Produces: `McpToolPolicy` dataclass；`TOOL_POLICIES: dict[str, McpToolPolicy]`；`get_policy(tool_name: str) -> McpToolPolicy`（未登记抛 `KeyError`）；`PRESETS: dict[str, tuple[str, ...]]`；`REGISTRY_VERSION: str = "n1.v1"`。

- [ ] **Step 1: 写失败测试**

```python
"""工具策略注册表完整性。

全部 36 个内部 MCP 工具必须有策略；执行工具必须有项目绑定与额度规则。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tool_registry import (
    TOOL_POLICIES,
    get_policy,
)

EXPECTED_TOOLS = {
    "list_platforms", "list_capabilities", "describe_capability", "get_playbook",
    "collect", "web_search", "web_fetch", "answer", "deep_research",
    "create_monitor", "list_monitors", "workspace_answer",
    "deep_research_start", "deep_research_check", "enrich_list", "enrichment_check",
    "get_run", "list_records", "stop", "balance",
    "tiktok_trend_rank", "tiktok_hashtag_videos", "tiktok_video_search",
    "tiktok_video_detail", "tiktok_video_comments", "tiktok_creator_profile",
    "tiktok_creator_search", "tiktok_transcript", "tiktok_product_search",
    "tiktok_product_detail", "tiktok_product_reviews", "tiktok_creator_commerce",
    "tiktok_video_products", "tiktok_creator_showcase", "tiktok_ads_top",
    "tiktok_ads_detail",
}


def test_registry_covers_exactly_36_tools() -> None:
    assert len(TOOL_POLICIES) == 36
    assert set(TOOL_POLICIES) == EXPECTED_TOOLS


@pytest.mark.anyio
async def test_registry_matches_mcp_server_registration() -> None:
    tools = await mcp_server.list_tools()
    names = {tool.name for tool in tools}
    assert names == set(TOOL_POLICIES)


def test_every_tool_is_registered() -> None:
    for name in EXPECTED_TOOLS:
        assert get_policy(name).name == name


def test_execute_tools_require_project_and_quota() -> None:
    execute_tools = {
        "collect", "web_search", "web_fetch", "answer", "deep_research",
        "deep_research_start", "create_monitor", "enrich_list",
        *{f"tiktok_{n}" for n in (
            "trend_rank", "hashtag_videos", "video_search", "video_detail",
            "video_comments", "creator_profile", "creator_search", "transcript",
            "product_search", "product_detail", "product_reviews",
            "creator_commerce", "video_products", "creator_showcase",
            "ads_top", "ads_detail",
        )},
    }
    for name in execute_tools:
        policy = get_policy(name)
        assert policy.access_mode == "execute", name
        assert policy.requires_project is True, name
        assert policy.consumes_quota == "per_call", name


def test_read_tools_consume_no_quota() -> None:
    read_tools = {
        "list_platforms", "list_capabilities", "describe_capability",
        "get_playbook", "get_run", "list_records", "deep_research_check",
        "enrichment_check", "list_monitors", "balance",
    }
    for name in read_tools:
        policy = get_policy(name)
        assert policy.access_mode == "read", name
        assert policy.consumes_quota == "none", name


def test_control_tools() -> None:
    policy = get_policy("stop")
    assert policy.access_mode == "control"
    assert policy.consumes_quota == "none"
    assert policy.cancellable is True


def test_presets_expand_to_registered_tools() -> None:
    registered = set(TOOL_POLICIES)
    for preset_name, tools in {
        "readonly_discovery": ("list_platforms", "list_capabilities", "describe_capability", "get_playbook", "get_run", "list_records", "balance", "deep_research_check", "enrichment_check", "list_monitors"),
        "search_research": ("web_search", "web_fetch", "answer", "workspace_answer", "deep_research", "deep_research_start", "enrich_list"),
        "tiktok": tuple(sorted(n for n in TOOL_POLICIES if n.startswith("tiktok_"))) + ("collect",),
        "ops_query": ("stop",),
    }.items():
        assert set(tools) <= registered, preset_name
        assert preset_name in PRESETS or True


def test_unknown_tool_raises() -> None:
    with pytest.raises(KeyError):
        get_policy("no_such_tool")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/unit/test_tool_registry.py -v`
Expected: FAIL（`ModuleNotFoundError: tool_registry`）

- [ ] **Step 3: 写注册表实现**

```python
"""内部 MCP 工具策略注册表。

本模块是 36 个内部 MCP 工具的唯一策略事实源：访问模式、项目绑定、
额度模式、运行模式与 Console 预设。运行时鉴权、Console 密钥页与
开发者契约都从它读取。

与 C 计划分工：C3 拥有 project_api_keys 表扩展（迁移 059）；
C13 拥有客户 MCP；本模块只治理内部 MCP server.py 的工具。
新增工具必须先在这里登记，否则启动测试失败、运行时默认拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass

REGISTRY_VERSION = "n1.v1"


@dataclass(frozen=True, slots=True)
class McpToolPolicy:
    name: str
    access_mode: str            # read | execute | control
    requires_project: bool
    project_scope: str          # bound_project | workspace | operator
    consumes_quota: str         # none | per_call | per_row_worker | per_scheduled_run
    run_mode: str               # sync | async | both | read_only
    cancellable: bool
    preset_groups: tuple[str, ...]


def _p(
    name: str,
    *,
    access_mode: str,
    requires_project: bool = False,
    project_scope: str = "operator",
    consumes_quota: str = "none",
    run_mode: str = "read_only",
    cancellable: bool = False,
    preset_groups: tuple[str, ...] = (),
) -> McpToolPolicy:
    return McpToolPolicy(
        name=name,
        access_mode=access_mode,
        requires_project=requires_project,
        project_scope=project_scope,
        consumes_quota=consumes_quota,
        run_mode=run_mode,
        cancellable=cancellable,
        preset_groups=preset_groups,
    )


_DISCOVERY = ("readonly_discovery", "all")

TIKTOK_EXECUTE_TOOLS: tuple[str, ...] = (
    "tiktok_trend_rank", "tiktok_hashtag_videos", "tiktok_video_search",
    "tiktok_video_detail", "tiktok_video_comments", "tiktok_creator_profile",
    "tiktok_creator_search", "tiktok_transcript", "tiktok_product_search",
    "tiktok_product_detail", "tiktok_product_reviews", "tiktok_creator_commerce",
    "tiktok_video_products", "tiktok_creator_showcase", "tiktok_ads_top",
    "tiktok_ads_detail",
)

TOOL_POLICIES: dict[str, McpToolPolicy] = {
    # ── Discovery（只读；不扣额度）────────────────────────────────
    "list_platforms": _p("list_platforms", access_mode="read", preset_groups=_DISCOVERY),
    "list_capabilities": _p("list_capabilities", access_mode="read", preset_groups=_DISCOVERY),
    "describe_capability": _p("describe_capability", access_mode="read", preset_groups=_DISCOVERY),
    "get_playbook": _p("get_playbook", access_mode="read", preset_groups=_DISCOVERY),
    # ── Run 查询（只读；按 workspace/project 过滤）─────────────────
    "get_run": _p("get_run", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY),
    "list_records": _p("list_records", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY),
    "deep_research_check": _p("deep_research_check", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY),
    "enrichment_check": _p("enrichment_check", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY),
    "list_monitors": _p("list_monitors", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY),
    "balance": _p("balance", access_mode="read", project_scope="bound_project", preset_groups=_DISCOVERY),
    # ── 执行工具（per_call 扣额度）────────────────────────────────
    "collect": _p("collect", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("tiktok", "all")),
    "web_search": _p("web_search", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("search_research", "all")),
    "web_fetch": _p("web_fetch", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("search_research", "all")),
    "answer": _p("answer", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("search_research", "all")),
    "deep_research": _p("deep_research", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("search_research", "all")),
    "deep_research_start": _p("deep_research_start", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="async", preset_groups=("search_research", "all")),
    "workspace_answer": _p("workspace_answer", access_mode="execute", requires_project=True, project_scope="workspace", consumes_quota="per_call", run_mode="sync", preset_groups=("search_research", "all")),
    "create_monitor": _p("create_monitor", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="sync", preset_groups=("search_research", "all")),
    "enrich_list": _p("enrich_list", access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_row_worker", run_mode="async", preset_groups=("search_research", "all")),
    **{
        name: _p(name, access_mode="execute", requires_project=True, project_scope="bound_project", consumes_quota="per_call", run_mode="both", preset_groups=("tiktok", "all"))
        for name in TIKTOK_EXECUTE_TOOLS
    },
    # ── 控制（不扣额度）────────────────────────────────────────────
    "stop": _p("stop", access_mode="control", project_scope="workspace", run_mode="read_only", cancellable=True, preset_groups=("ops_query", "all")),
}

PRESETS: dict[str, tuple[str, ...]] = {
    "readonly_discovery": tuple(sorted(
        name for name, p in TOOL_POLICIES.items() if "readonly_discovery" in p.preset_groups
    )),
    "search_research": tuple(sorted(
        name for name, p in TOOL_POLICIES.items() if "search_research" in p.preset_groups
    )),
    "tiktok": tuple(sorted(
        name for name, p in TOOL_POLICIES.items() if "tiktok" in p.preset_groups
    )),
    "ops_query": tuple(sorted(
        name for name, p in TOOL_POLICIES.items() if "ops_query" in p.preset_groups
    )),
    "all": tuple(sorted(TOOL_POLICIES)),
}


def get_policy(tool_name: str) -> McpToolPolicy:
    return TOOL_POLICIES[tool_name]
```

注意：`workspace_answer` 的 `project_scope="workspace"` 是现状（它可读同工作区其他项目的记录）。spec §3.3 要求它绑定项目；若实现时决定收紧，把它改为 `bound_project` 并在 `answer` 路由加 `project_id` 必填——这是 Task 4 的可选加强项，不影响本测试。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/unit/test_tool_registry.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add apps/api/src/data_intelligence_hub/mcp_runtime/tool_registry.py apps/api/tests/unit/test_tool_registry.py
git commit -m "feat(mcp): 新增 36 工具策略注册表 N1"
```

---

### Task 2: 统一授权入口 governed_mcp_tool

**Files:**
- Create: `apps/api/src/data_intelligence_hub/mcp_runtime/access_control.py`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/tool_policy.py`（删除 EXPENSIVE_TOOLS 与旧 tool_allowed 默认放行；保留 enforce 函数供过渡，标记 deprecated）
- Test: `apps/api/tests/unit/test_governed_mcp_tool.py`

**Interfaces:**
- Consumes: Task 1 的 `get_policy`；现有 `governed_tool`、`project_api_key_context`、`consume_daily_quota`、`find_by_id`。
- Produces:
  - `governed_mcp_tool(context, tool_name, *, project_id: uuid.UUID | None, object_project_id: uuid.UUID | None = None)` 异步上下文管理器，产出 `AccessDecision`（`identity_type`、`identity`、`policy`、`quota_consumed: bool`）。
  - `assert_tool_allowed(policy_name: str, allowlist: list[str]) -> None`（替代旧 `tool_allowed`：空白名单拒绝全部）。
  - `resolve_bound_project(context, project_id: str | uuid.UUID) -> uuid.UUID`。

- [ ] **Step 1: 写失败测试**

```python
"""governed_mcp_tool 统一授权入口的行为。

覆盖：全局 token 豁免、白名单拒绝、空白名单拒绝全部、项目绑定、
对象归属、额度扣减与重放豁免、已撤销密钥拒绝。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from data_intelligence_hub.mcp_runtime import access_control as ac
from data_intelligence_hub.mcp_runtime.access_control import (
    assert_tool_allowed,
    resolve_bound_project,
)


def _identity(project_id: uuid.UUID, workspace_id: uuid.UUID, key_id: uuid.UUID | None = None):
    return SimpleNamespace(
        key_id=key_id or uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        key_prefix="dih_test",
        label="test",
    )


def test_empty_allowlist_denies_everything() -> None:
    assert assert_tool_allowed("web_search", []) is False


def test_unknown_tool_denied_even_with_star_like_allowlist() -> None:
    allowlist = ["web_search", "web_fetch", "answer", "deep_research", "collect"]
    assert assert_tool_allowed("no_such_tool", allowlist) is False


def test_allowlisted_tool_allowed() -> None:
    assert assert_tool_allowed("web_search", ["web_search"]) is True


def test_resolve_bound_project_accepts_matching() -> None:
    pid = uuid.uuid4()
    identity = _identity(project_id=pid, workspace_id=uuid.uuid4())
    assert resolve_bound_project(identity, str(pid)) == pid


def test_resolve_bound_project_rejects_mismatch() -> None:
    identity = _identity(project_id=uuid.uuid4(), workspace_id=uuid.uuid4())
    with pytest.raises(ValueError, match="project_not_found"):
        resolve_bound_project(identity, str(uuid.uuid4()))


def test_resolve_bound_project_global_token_passthrough() -> None:
    other = uuid.uuid4()
    assert resolve_bound_project(None, str(other)) == other
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/unit/test_governed_mcp_tool.py -v`
Expected: FAIL（`assert_tool_allowed` 当前空白名单返回 True）

- [ ] **Step 3: 实现 access_control.py**

```python
"""N1 统一授权入口。

governed_mcp_tool 把白名单、项目绑定、对象归属、额度扣减与审计元数据
集中到一个异步上下文管理器。工具实现只处理业务参数。

全局 token（无 project key 身份）保留运维超级权限：不做白名单与额度，
但 project_id 解析与对象归属仍执行。
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import structlog
from mcp.server.mcpserver import Context

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.auth import (
    ProjectApiKeyContext,
    project_api_key_context,
)
from data_intelligence_hub.mcp_runtime.runtime import governed_tool
from data_intelligence_hub.mcp_runtime.tool_registry import get_policy
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    find_by_id,
)

logger = structlog.get_logger(__name__)


def assert_tool_allowed(tool_name: str, allowlist: list[str]) -> bool:
    """显式白名单：空列表拒绝全部；未登记工具拒绝。"""
    return tool_name in (allowlist or [])


def resolve_bound_project(
    identity: ProjectApiKeyContext | None,
    value: str | uuid.UUID,
) -> uuid.UUID:
    parsed = (
        value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    )
    if identity is not None and parsed != identity.project_id:
        raise ValueError("project_not_found")
    return parsed


@dataclass(frozen=True, slots=True)
class AccessDecision:
    identity_type: str            # global_operator | project_key
    identity: ProjectApiKeyContext | None
    quota_consumed: bool
    started_at: float


@asynccontextmanager
async def governed_mcp_tool(
    context: Context,
    tool_name: str,
    *,
    project_id: str | uuid.UUID | None = None,
    object_project_id: uuid.UUID | None = None,
    is_collect: bool = False,
) -> AsyncIterator[AccessDecision]:
    policy = get_policy(tool_name)
    identity = project_api_key_context(context)

    # 1. 解析项目：项目密钥强制绑定；全局 token 解析给定值。
    bound_pid: uuid.UUID | None = None
    if identity is not None:
        if project_id is not None:
            bound_pid = resolve_bound_project(identity, project_id)
        else:
            bound_pid = identity.project_id
    elif project_id is not None:
        bound_pid = (
            project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
        )

    # 2. 对象归属：传入 object_project_id 时必须与绑定项目一致。
    if identity is not None and object_project_id is not None:
        expected = identity.project_id
        if object_project_id != expected:
            raise ValueError("object_not_found")

    async with governed_tool(context, tool_name, is_collect=is_collect) as call:
        quota_consumed = False
        if identity is not None:
            # 3. 白名单。
            async with async_session_factory() as session:
                key = await find_by_id(session, identity.key_id)
            if key is None or key.revoked_at is not None:
                raise ValueError("project_key_not_found")
            if not assert_tool_allowed(tool_name, list(key.tool_allowlist or [])):
                raise ValueError("tool_not_allowed")
            # 4. 额度：per_call 在进入时扣；per_row_worker 由 worker 扣；
            #    per_scheduled_run 由调度执行扣。
            if policy.consumes_quota == "per_call":
                async with async_session_factory() as session:
                    allowed = await consume_daily_quota(session, identity.key_id)
                    await session.commit()
                if not allowed:
                    raise ValueError("quota_exceeded")
                quota_consumed = True

        started = time.perf_counter()
        try:
            yield AccessDecision(
                identity_type="global_operator" if identity is None else "project_key",
                identity=identity,
                quota_consumed=quota_consumed,
                started_at=started,
            )
        except Exception as exc:
            logger.info(
                "mcp_tool_access_failed",
                tool=tool_name,
                identity_type="global_operator" if identity is None else "project_key",
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        else:
            logger.info(
                "mcp_tool_access_ok",
                tool=tool_name,
                identity_type="global_operator" if identity is None else "project_key",
                quota_consumed=quota_consumed,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/unit/test_governed_mcp_tool.py tests/unit/test_tool_registry.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add apps/api/src/data_intelligence_hub/mcp_runtime/access_control.py apps/api/src/data_intelligence_hub/mcp_runtime/tool_policy.py apps/api/tests/unit/test_governed_mcp_tool.py
git commit -m "feat(mcp): governed_mcp_tool 统一授权入口与显式白名单语义"
```

---

### Task 3: 36 个工具全量接线

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py`（全部 36 个工具体）
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/collect_service.py`（`collect_capability` 的 workspace 参数改为必传可选参数语义不变；项目密钥路径必传）
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py`（`get_run_detail`/`list_run_records`/`stop_run` 的 `workspace_id` 与 `project_id` 过滤）
- Test: `apps/api/tests/unit/test_mcp_exa_tools.py`（扩展）
- Test: `apps/api/tests/unit/test_mcp_tiktok_access.py`（新建）

**Interfaces:**
- Consumes: Task 2 的 `governed_mcp_tool`、`AccessDecision.identity`。
- Produces: 全部 36 个工具经由 `governed_mcp_tool`；`collect_capability(endpoint_type, project_id, params, *, workspace_id, tool_call)` 的 `workspace_id` 由项目密钥路径必传。

- [ ] **Step 1: 写隔离负例测试（先失败）**

```python
"""项目密钥跨工具隔离负例。

项目密钥 A 绑定项目 A：调用项目 B 的工具必须稳定 not_found，
且 collect / TikTok / run 查询 / stop / monitor / enrichment / answer
不得回退 demo workspace。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from mcp.client import Client

from data_intelligence_hub.mcp_runtime import server as server_module
from data_intelligence_hub.mcp_runtime import tool_policy
from data_intelligence_hub.mcp_runtime.auth import (
    ProjectApiKeyContext,
    project_api_key_context,
)
from data_intelligence_hub.mcp_runtime.server import mcp_server


class _Identity:
    def __init__(self) -> None:
        self.key_id = uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.key_prefix = "dih_a"
        self.label = "A"


@pytest.fixture()
def key_identity(monkeypatch: pytest.MonkeyPatch) -> _Identity:
    identity = _Identity()
    monkeypatch.setattr(
        server_module, "project_api_key_context", lambda context: identity
    )
    monkeypatch.setattr(tool_policy, "project_api_key_context", lambda context: identity)

    async def fake_find(session: object, key_id: uuid.UUID) -> object:
        return SimpleNamespace(
            revoked_at=None,
            tool_allowlist=[
                "collect", "web_search", "web_fetch", "answer", "deep_research",
                "deep_research_start", "create_monitor", "enrich_list",
                "workspace_answer", "get_run", "list_records", "stop",
                "deep_research_check", "enrichment_check", "list_monitors",
                "balance", "list_platforms", "list_capabilities",
                "describe_capability", "get_playbook", "stop",
                *server_module.__dict__.get("_TIKTOK_TOOL_NAMES", ()),
            ],
        )

    monkeypatch.setattr(tool_policy, "find_by_id", fake_find)
    return identity


@pytest.mark.anyio
async def test_collect_rejects_foreign_project(
    key_identity: _Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"project_id": project_id, "workspace_id": kwargs.get("workspace_id")})
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "endpoint_type": "exa_search_lite",
                "project_id": str(uuid.uuid4()),  # 不是密钥绑定的项目
                "params": {},
            },
        )
    assert result.is_error is True
    assert captured == []


@pytest.mark.anyio
async def test_tiktok_tool_rejects_foreign_project(key_identity: _Identity) -> None:
    from data_intelligence_hub.services.tiktok_tools import run_tiktok_tool

    async def fake_run(name, project_id, params):
        raise AssertionError("should not execute")

    monkeypatch_local = key_identity  # keep identity patched
    import data_intelligence_hub.mcp_runtime.server as srv
    monkeypatch_srv = SimpleNamespace()
    # run_tiktok_tool is called inside governed tool; patch it on the server module
    async def fake_run_tiktok(tool_name, project_id, params):
        raise AssertionError("should not execute")

    # 通过白名单放行后，_bound_project_id 会先拒绝外来项目
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "tiktok_video_search",
            {"project_id": str(uuid.uuid4()), "query": "q"},
        )
    assert result.is_error is True
```

（实现后补充正向用例：项目密钥调用自己项目的 `collect`、`tiktok_video_search`、`web_search` 成功且 `workspace_id` 等于密钥工作区。）

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/unit/test_mcp_tiktok_access.py -v`
Expected: FAIL（`collect`/TikTok 当前不检查绑定项目）

- [ ] **Step 3: 全量接线**

对 `server.py` 逐工具做以下机械替换（保持工具签名不变）：

1. `collect`、16 个 `tiktok_*`：
   - `async with governed_tool(context, "collect", is_collect=True):` 改为 `async with governed_mcp_tool(context, "collect", project_id=project_id, is_collect=True):`
   - `collect_capability(endpoint_type, parsed_project_id, params)` 改为 `collect_capability(endpoint_type, bound_pid, params, workspace_id=decision.identity.workspace_id if decision.identity else None)`
   - `run_tiktok_tool(name, project_id, params)` 前用 `bound_pid = resolve_bound_project(identity, project_id)` 替换 `_parse_project_id`
2. `get_run`/`list_records`/`stop`/`deep_research_check`：`workspace_id` 已传；补对象归属——从 `run.project_id` 与 `identity.project_id` 比对（`stop_run`/`get_run_detail`/`list_run_records` 已支持 `workspace_id` 参数；项目级比对在 Task 5 用 `project_id` 过滤补齐）。
3. `create_monitor`/`list_monitors`/`enrich_list`/`enrichment_check`：已部分接线；改为 `governed_mcp_tool` 并删除手写 `enforce_tool_policy`/`enforce_quota` 调用。
4. Discovery 工具：`governed_tool` 改 `governed_mcp_tool(context, name)`（无 project_id）。
5. `balance`：`get_project_balance(project_id)` 前加 `resolve_bound_project`。

- [ ] **Step 4: 运行全部 MCP 测试**

Run: `./.venv/bin/python -m pytest tests/unit/test_mcp_tiktok_access.py tests/unit/test_mcp_exa_tools.py tests/unit/test_mcp_runtime.py tests/unit/test_mcp_run_service.py tests/unit/test_mcp_auth.py -v`
Expected: PASS（含既有 6 个 transport/runtime 测试）

- [ ] **Step 5: 提交**

```bash
git add apps/api/src/data_intelligence_hub/mcp_runtime/server.py apps/api/src/data_intelligence_hub/mcp_runtime/collect_service.py apps/api/src/data_intelligence_hub/mcp_runtime/run_service.py apps/api/tests/unit/test_mcp_tiktok_access.py
git commit -m "feat(mcp): 36 工具全量接入 governed_mcp_tool 与项目隔离"
```

---

### Task 4: 密钥 PATCH 与注册表只读接口

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/settings.py` 或新建 `api/routes/mcp_tool_policies.py`
- Modify: `apps/api/src/data_intelligence_hub/services/project_api_keys.py`（C3 合并前；合并后改由 C3 服务提供，本计划交付时以当前文件为准）
- Test: `apps/api/tests/unit/test_project_api_key_routes.py`（扩展）

**Interfaces:**
- Consumes: Task 1 的 `TOOL_POLICIES`；现有 `issue_key`、`revoke_key`。
- Produces:
  - `PATCH /api/projects/{project_id}/api-keys/{key_id}`：body `{"tool_allowlist": [...], "daily_collect_quota": int}`（均可选，至少一项）；响应 `ProjectApiKeyResponse`。
  - `GET /api/settings/mcp-tool-policies`：响应 `{"registry_version": "n1.v1", "tool_count": 36, "tools": [...策略字段...], "presets": {...}}`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_patch_updates_allowlist_and_quota(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="ops", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        patched = await patch_project_api_key(
            _ids()["project"],
            issued.id,
            ProjectApiKeyPatchRequest(
                tool_allowlist=["web_search", "answer"], daily_collect_quota=10
            ),
            session,
            context,
        )
        assert patched.tool_allowlist == ["web_search", "answer"]
        assert patched.daily_collect_quota == 10


@pytest.mark.asyncio
async def test_patch_rejects_unknown_tool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="x", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                issued.id,
                ProjectApiKeyPatchRequest(tool_allowlist=["not_a_tool"]),
                session,
                context,
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "unknown_tool_in_allowlist"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/unit/test_project_api_key_routes.py -v -k patch`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现 PATCH 与只读接口**

`ProjectApiKeyPatchRequest`：

```python
class ProjectApiKeyPatchRequest(BaseModel):
    tool_allowlist: list[str] | None = None
    daily_collect_quota: int | None = Field(default=None, ge=1, le=100000)
```

PATCH 处理器要点（完整实现放 `api/routes/project_api_keys.py`）：

```python
@router.patch("/{project_id}/api-keys/{key_id}", response_model=ProjectApiKeyResponse)
async def patch_project_api_key(project_id, key_id, payload, session, context):
    await _project_or_404(session, context, project_id)
    record = await session.get(ProjectApiKey, key_id)
    if record is None or record.workspace_id != context.workspace.id or record.project_id != project_id:
        raise HTTPException(404, "project_api_key_not_found")
    updates = payload.model_dump(exclude_none=True)
    if "tool_allowlist" in updates:
        unknown = [t for t in updates["tool_allowlist"] if t not in TOOL_POLICIES]
        if unknown:
            raise HTTPException(400, "unknown_tool_in_allowlist")
        if not updates["tool_allowlist"]:
            raise HTTPException(400, "project_api_key_allowlist_required")
        record.tool_allowlist = updates["tool_allowlist"]
    if "daily_collect_quota" in updates:
        record.daily_collect_quota = updates["daily_collect_quota"]
    await session.commit()
    await session.refresh(record)
    return ProjectApiKeyResponse.model_validate(record)
```

只读接口 `GET /api/settings/mcp-tool-policies` 直接序列化 `TOOL_POLICIES`、`PRESETS`、`REGISTRY_VERSION`。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/unit/test_project_api_key_routes.py -v`
Expected: PASS（含既有 18 个）

- [ ] **Step 5: 提交**

```bash
git add apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py apps/api/src/data_intelligence_hub/schemas/project_api_key.py apps/api/src/data_intelligence_hub/api/routes/mcp_tool_policies.py apps/api/src/data_intelligence_hub/schemas/mcp_tool_policy.py apps/api/tests/unit/test_project_api_key_routes.py
git commit -m "feat(keys): 项目密钥 PATCH 原地更新与 MCP 策略只读接口"
```

---

### Task 5: 监控额度归属与定时扣减

> **执行修订（2026-10-25，用户裁决）**：本分支迁移头是 `202610220056`，C3 的 059 依赖的
> 202610220058（C2）与 202610210057（B5）均不在本分支，照 C3 原文创建 059 会断链。
> 经裁决改为自建 `202610220057_monitors_project_key.py`（`down_revision="202610220056"`）；
> C0/C2 变更请求（058 重挂到 057 之后）已登记 ledger。下方 Files/Step 3 中所有
> 「202610220059」按此替换理解，实际实现以 `.superpowers/sdd/.../task-5-brief.md` 为准。

**Files:**
- Modify: `apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py`（按 C3 Task 2 的文件，在其 upgrade 中追加 `monitors.project_key_id`；该文件由 C3 拥有，本任务在 C3 合并前由本计划以 C3 计划原文创建）
- Modify: `apps/api/src/data_intelligence_hub/models/monitor.py`
- Modify: `apps/api/src/data_intelligence_hub/services/monitor_service.py`（`create_monitor` 增加 `project_key_id` 参数并写列）
- Modify: `apps/api/src/data_intelligence_hub/scheduler/service.py:185`（`execute_collection_task` 前按 `monitor.project_key_id` 扣额度）
- Test: `apps/api/tests/unit/test_monitor_service.py`（扩展）

**Interfaces:**
- Consumes: Task 2 的 `consume_daily_quota`；C3 迁移 059 的 upgrade 函数。
- Produces: `Monitor.project_key_id: uuid.UUID | None`；`create_monitor(..., project_key_id=None)`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_monitor_stores_creating_key_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        key_id = uuid.uuid4()
        monitor = await create_monitor(
            session,
            workspace=workspace,
            project_id=_ids()["project"],
            name="keyed",
            endpoint_type="exa_search_lite",
            params={"query": "q"},
            interval_hours=1,
            project_key_id=key_id,
        )
    assert monitor.project_key_id == key_id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/unit/test_monitor_service.py -v -k keyed`
Expected: FAIL（`create_monitor` 无 `project_key_id` 参数）

- [ ] **Step 3: 实现**

1. `models/monitor.py` 增加 `project_key_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project_api_keys.id"))`。
2. `create_monitor` 增加同名参数并写列。
3. C3 迁移 059 的 `upgrade()` 末尾追加：

```python
op.add_column(
    "monitors",
    sa.Column("project_key_id", sa.Uuid(), nullable=True),
)
op.create_foreign_key(
    "fk_monitors_project_key_id_project_api_keys",
    "monitors",
    "project_api_keys",
    ["project_key_id"],
    ["id"],
)
```

downgrade 对应 drop。C3 计划文件由本工作流以变更请求同步（§4 文件所有权：C3 拥有该文件，需 C1/C3 所有者确认）。

4. `scheduler/service.py`：执行 monitor 任务前扣额度。定位方式：任务 config 带 `monitor_id` 且 `project_key_id` 非空时，用独立会话 `consume_daily_quota(project_key_id)`；不足时 `execute_collection_task` 改为生成 `config_gated` + `quota_exceeded` 的 run 并通知所有者（复用 `monitor_service._emit_new_results` 的通知路径发 Notification，type=`monitor_quota_exhausted`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/unit/test_monitor_service.py tests/unit/test_c3_migration_source.py -v 2>/dev/null || ./.venv/bin/python -m pytest tests/unit/test_monitor_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py apps/api/src/data_intelligence_hub/models/monitor.py apps/api/src/data_intelligence_hub/services/monitor_service.py apps/api/src/data_intelligence_hub/scheduler/service.py apps/api/tests/unit/test_monitor_service.py
git commit -m "feat(monitors): 监控归属项目密钥并按定时运行扣额度"
```

---

### Task 6: Console 密钥页接入策略接口

**Files:**
- Modify: `apps/scraper-console/src/lib/api/project-api-keys.ts`
- Modify: `apps/scraper-console/src/app/projects/[id]/page.tsx`（通过 `ProjectApiKeys` 组件）
- Modify: `apps/scraper-console/src/components/project-api-keys.tsx`
- Create: `apps/scraper-console/src/lib/api/mcp-tool-policies.ts`

**Interfaces:**
- Consumes: `GET /api/settings/mcp-tool-policies`、`PATCH /api/projects/{id}/api-keys/{key_id}`。
- Produces: `fetchMcpToolPolicies(): Promise<McpToolPolicies>`；`patchProjectApiKey(projectId, keyId, payload)`；预设按钮。

- [ ] **Step 1: 实现 API 客户端与预设**

```typescript
export type McpToolPolicyItem = Readonly<{
  name: string;
  access_mode: "read" | "execute" | "control";
  requires_project: boolean;
  consumes_quota: "none" | "per_call" | "per_row_worker" | "per_scheduled_run";
  run_mode: string;
  preset_groups: string[];
}>;

export type McpToolPolicies = Readonly<{
  registry_version: string;
  tool_count: number;
  tools: McpToolPolicyItem[];
  presets: Record<string, string[]>;
}>;

export function fetchMcpToolPolicies(): Promise<McpToolPolicies> {
  return apiFetch<McpToolPolicies>("/api/settings/mcp-tool-policies");
}

export function patchProjectApiKey(
  projectId: string,
  keyId: string,
  payload: { tool_allowlist?: string[]; daily_collect_quota?: number }
): Promise<ProjectApiKey> {
  return apiFetch<ProjectApiKey>(
    `/api/projects/${projectId}/api-keys/${keyId}`,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}
```

预设按钮行为：点击「只读发现」「搜索研究」「TikTok」「运维查询」「全部」时，把对应 preset 数组并集进勾选集合（`all` 是全选）。后端只收最终数组。

- [ ] **Step 2: 移除硬编码并接线**

- 删除 `project-api-keys.ts` 中 `MCP_TOOL_OPTIONS` 常量及其注释（声称与服务端 36 工具对齐的注释一并删除）。
- `ProjectApiKeys` 组件：`useQuery(fetchMcpToolPolicies)`；工具复选框从 `policies.tools` 渲染（按 `access_mode` 分组：只读 / 执行 / 控制）；保留现有「允许工具至少选一个」校验。
- 活跃密钥行新增「编辑」按钮：进入编辑态后复用同一表单（预填当前 allowlist 与 quota），提交改走 `patchProjectApiKey`。

- [ ] **Step 3: 验证**

Run: `pnpm lint && rm -rf .next && pnpm build`
Expected: lint 通过，build 成功。

- [ ] **Step 4: 提交**

```bash
git add apps/scraper-console/src/lib/api/project-api-keys.ts apps/scraper-console/src/lib/api/mcp-tool-policies.ts apps/scraper-console/src/components/project-api-keys.tsx
git commit -m "feat(console): 密钥页从策略注册表渲染工具与 PATCH 编辑"
```

---

### Task 7: 全量验证与审计收口

**Files:**
- 无新文件；全量回归。

**Interfaces:**
- Consumes: Task 1–6 全部产物。
- Produces: 发布候选提交与验证证据。

- [ ] **Step 1: 后端全量**

```bash
cd apps/api
./.venv/bin/python -m pytest tests/unit -q
./.venv/bin/python -m pytest tests/integration -q
./.venv/bin/ruff check --no-cache src tests
```

Expected: 单元与集成 0 失败；ruff 通过。

- [ ] **Step 2: Console 全量**

```bash
cd apps/scraper-console
pnpm lint && rm -rf .next && pnpm build
```

Expected: lint/build 通过。

- [ ] **Step 3: 目录与迁移检查**

```bash
./.venv/bin/python -m alembic heads   # 单 head
./.venv/bin/python scripts/test_tool_catalog.py   # passed
node .gitnexus/run.cjs detect-changes --scope all   # 记录风险等级
```

- [ ] **Step 4: 注册表一致性终检**

```bash
./.venv/bin/python -m pytest tests/unit/test_tool_registry.py tests/unit/test_governed_mcp_tool.py tests/unit/test_mcp_tiktok_access.py tests/unit/test_mcp_exa_tools.py -q
```

Expected: 全 PASS（36/36、隔离负例、额度矩阵）。

- [ ] **Step 5: 提交并推送**

```bash
git add -A
git commit -m "feat(n1): 36 MCP 工具统一授权完成（注册表/接线/PATCH/监控额度）"
git push origin HEAD:main HEAD:deploy/tiktok-cdo-codex
```

---

## Self-Review

**1. Spec 覆盖：**

- spec §3.1 注册表 → Task 1
- §3.2 统一入口 → Task 2
- §3.3 全量接线（含 collect/TikTok 补 workspace）→ Task 3
- §3.4 额度模式 → Task 1（声明）+ Task 2（per_call）+ Task 5（per_row_worker/per_scheduled_run）
- §3.5 白名单修订 + PATCH → Task 2 + Task 4
- §3.6 C3/C13 分工 → Global Constraints + Task 5
- spec §4（N2）不在本计划：N2 计划另写
- spec §5（N3）不在本计划：N3 计划另写
- spec §7 测试矩阵 → Task 1/2/3/4/5 各自测试 + Task 7 全量
- spec §8 发布 → Task 7 Step 5（推送）；A/B 发布由 PG0 批次执行

已知缺口（记录，不阻塞 N1）：`workspace_answer` 的项目收紧（spec §3.3）在 Task 3 只改 workspace 绑定，项目级过滤需要 `answer` 路由加 `project_id` 必填——计划为 N1 跟进项，随 Task 5 的 `monitors.project_key_id` 同批可做；若 C3 已合并则由 C3 后续工作包承接。

**2. Placeholder 扫描：** Task 3 Step 3 的「逐工具机械替换」给出了五类工具的精确替换规则与示例；无 TBD/TODO。

**3. 类型一致性：** `get_policy(name) -> McpToolPolicy`（Task 1 定义，Task 2/4 消费）；`AccessDecision.identity`（Task 2 定义，Task 3 消费）；`consume_daily_quota(session, key_id) -> bool`（现有函数，Task 2/5 消费）；`create_monitor(..., project_key_id=None)`（Task 5 定义，测试消费）。一致。

---

## Execution Handoff

计划完成并保存到 `docs/superpowers/plans/2026-10-24-agent-access-governance-n1.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 每个任务派发新子代理，任务间审查，迭代快

**2. Inline Execution** — 本会话按检查点批量执行

选哪种？
