# 受治理任务平台 C3：项目密钥与项目级凭据实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `project_api_keys` 增加 capability 白名单、租户复合外键、原子轮换、撤销状态与 `last_used_at`；给平台凭据增加项目作用域与 `creator_cookie` 元数据；提供管理路由与 C14 的 `/keys`、`/connectors` 浏览器交接。

**Architecture:** 密钥表继续只存 SHA-256 与可读前缀。轮换在一个事务内先锁定旧钥、写入 `status='rotating'` 并释放活跃唯一索引，再签发新钥，最后把旧钥置为 `revoked` 并写 `superseded_by_key_id`；任一步失败由路由回滚整个事务。凭据表增加可空 `project_id`，用两个部分唯一索引分别约束工作区级与项目级，解析顺序为项目级优先、工作区级回退。所有写路由复用 C2 的 `api/authz`、`RequestIdDep`、`APIError` 与 `append_audit_event`，不复制 RBAC 或审计实现。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、PostgreSQL 15、SQLite 单元测试、pytest、ruff、Next.js 16 控制台、Playwright、GitNexus CLI。

## Global Constraints

- 产品阶段只写 `PG0`、`PG1`。不得写成 `P0`、`P1`。
- 当前基线：C0 标签 `pg0-baseline-v1` 已存在，C1 分支 `feat/gov-c1` 已完成，C2 分支 `feat/gov-c2` 已完成。C3 从 `feat/gov-c2` 创建独立 worktree：`git worktree add ../data_scrapy-gov-c3 -b feat/gov-c3 feat/gov-c2`。不得从 `f0560ca`、`main` 或 `pg0-baseline-v1` 直接开工。
- 开工断言：`git merge-base --is-ancestor feat/gov-c2 HEAD` 退出码 0；`uv run alembic heads` 只有 `202610220058 (head)`；`configs/contracts/v1.1.0/registry.json` 存在且 checker 通过。
- 契约所有权：`docs/design/【契约冻结】v1-表名-枚举-接口.md` 与 `configs/contracts/v1.1.0/*` 只读。C1 已登记 C3 的列、约束、部分唯一索引、路径与错误码。C3 不得修改契约或 registry；守卫测试只读校验，失败时停止并交回 C1。
- 控制台所有权：`apps/scraper-console/src/**` 与 `apps/scraper-console/e2e/**` 归 C14。C3 只提供 `/keys` 与 `/connectors` 的浏览器交接清单，不改页面、不改测试、不改路由表。
- C3 只允许一个迁移：`202610220059_project_keys_credentials_scope.py`，`down_revision = "202610220058"`。不得新增第二个迁移。
- 回滚点：关闭 `vault_write_enabled` 停止凭据写入；轮换任一步失败由路由回滚整事务；迁移 059 只在一次性库执行 `downgrade -1`，生产回滚用备份恢复或新迁移。
- 发布门禁：本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；先备份，A 先 canary，B 只在目标授权、备份与迁移门禁通过后发布；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。任一步失败记 `BLOCKED`。
- C2 提供以下接缝，本计划只调用，不复制实现：
  - `data_intelligence_hub.api.authz.require_workspace_role(session, *, workspace, user, allowed) -> WorkspaceRole`
  - `data_intelligence_hub.api.authz.require_project_access(session, *, workspace, user, project_id, manage=False) -> ProjectAccess`
  - `data_intelligence_hub.api.deps.RequestIdDep`
  - `data_intelligence_hub.core.errors.APIError`
  - `data_intelligence_hub.services.audit_log.append_audit_event(session, *, workspace_id, project_id=None, actor_user_id=None, actor_type="user", action, resource_type, resource_id=None, request_id=None, result="success", details=None, occurred_at=None) -> AuditEvent`
- 冻结契约路径以 C1 v1.1 为准：项目密钥管理写 `/api/projects/{project_id}/keys`，轮换写 `/api/projects/{project_id}/keys/{key_id}/rotate`。旧 `/api-keys` 路径保留一个发布周期，用 `include_in_schema=False` 隐藏，不新增旧路径的轮换动作。
- C3 不新增 `Idempotency-Key` 存储。重复 create 返回 409 `project_api_key_active_exists`；重复 rotate 返回 409 `state_conflict`。registry 的 `idempotent` 标志描述目标接缝，不是 C3 的持久化保证。
- `project_api_keys.capability_allowlist` 存稳定 `tool_catalog.tool_id`。C3 负责存储、展示、审计，并通过 `ProjectApiKeyIdentity.capability_allowlist` 与 `ProjectApiKeyIdentity.allows_capability(capability_id)` 暴露给调用方。C13 负责客户 MCP 的 enforcement；C3 不修改 `mcp_runtime` 的白名单或鉴权实现。`tool_allowlist` 仍是现有 MCP 工具名白名单。
- `platform_credential_bundles.project_id` 为空表示工作区级，非空表示项目级。Postgres 的普通复合唯一约束不会把两个 `NULL` 视为相等，因此必须使用两个部分唯一索引：`WHERE project_id IS NULL` 与 `WHERE project_id IS NOT NULL`。
- `creator_cookie_metadata` 只存 `captured_at`、`expires_at`、`last_verified_at`、`account_label`。不得存 Cookie 明文、密文、哈希或任何可还原值。`creator_cookie` 值继续只存在 Fernet 密文里。
- `creator_cookie` 只留在内部控制台与内部采集链。客户 MCP、客户 REST、报告、数据集和 manifest 不得读取平台凭据服务。C3 不修改 `mcp_runtime` 的凭据解析。
- 明文密钥只出现在签发或轮换响应一次。不得进入 URL、日志、错误、审计 details、报告、bundle 或工单。审计 details 的键不得使用 `secret`、`cookie`、`key_hash`、`password`、`access_token`、`authorization`、`salt`。
- 金额只用 `Decimal` 与 `Numeric(12, 6)`。本计划不修改 `run_ledger_entries` 八列与六种 `entry_kind`；`settle` 必须正数，`release` 必须负数。
- 每个 task 先写失败测试，运行并确认失败，写最小实现，运行并确认通过，再 commit。每个 task 可独立评审。
- 每个 commit 前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不算通过，必须重跑。
- 改既有符号前运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。已测结果：`issue_key` LOW（1 个直接调用者）、`authenticate_key` LOW（2）、`revoke_key` LOW（1）、`get_platform_credential_values` LOW（3）、`update_platform_credentials` LOW（1 个流程）、`ProjectApiKey` LOW（lower-bound 12）、`PlatformCredentialBundle` LOW（lower-bound 13）。空调用集按 `UNKNOWN` 处理，必须再用文本搜索确认。
- 文档正文写中文；表名、列名、枚举值、错误码、函数名写英文 `snake_case`。
- 每个步骤必须给出实际命令、实际代码或实际断言；占位符扫描必须通过。

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `apps/api/tests/unit/test_contract_freeze_c3.py` | Create | 只读契约与 C2 依赖守卫。 |
| `apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py` | Create | 唯一迁移：密钥列、复合 FK、凭据项目作用域、部分唯一索引。 |
| `apps/api/src/data_intelligence_hub/models/project_api_key.py` | Modify | 密钥新列、复合 FK、自引用轮换列。 |
| `apps/api/src/data_intelligence_hub/models/platform_credential.py` | Modify | `project_id`、`creator_cookie_metadata`、部分唯一索引、复合 FK。 |
| `apps/api/src/data_intelligence_hub/repositories/project_api_keys.py` | Modify | capability 列、锁定查询、撤销状态、`last_used_at` 节流更新。 |
| `apps/api/src/data_intelligence_hub/services/project_api_keys.py` | Modify | capability 规范化、状态检查、原子轮换。 |
| `apps/api/src/data_intelligence_hub/schemas/project_api_key.py` | Modify | 请求与响应新字段。 |
| `apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py` | Modify | 规范 `/keys` 路由、轮换、审计、错误映射。 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py` | Modify | 鉴权成功后提交 `last_used_at`。 |
| `apps/api/src/data_intelligence_hub/repositories/platform_credentials.py` | Modify | 精确作用域查询与项目优先解析。 |
| `apps/api/src/data_intelligence_hub/services/platform_credentials.py` | Modify | 项目作用域、回退、元数据、事务归属。 |
| `apps/api/src/data_intelligence_hub/schemas/platform_credentials.py` | Modify | `scope`、`project_id`、`CreatorCookieMetadata`。 |
| `apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py` | Modify | 项目参数、C2 RBAC、审计、错误信封。 |
| `apps/api/src/data_intelligence_hub/services/tiktok_tools.py` | Modify | `creator_cookie` 按项目作用域解析。 |
| `apps/api/tests/unit/test_c3_migration_source.py` | Create | 迁移单 head、复合 FK、部分唯一索引、NULL 陷阱。 |
| `apps/api/tests/unit/test_project_api_keys.py` | Modify | capability、状态、轮换、`last_used_at`。 |
| `apps/api/tests/unit/test_project_api_key_routes.py` | Modify | 规范路由、轮换、审计、错误码。 |
| `apps/api/tests/unit/test_platform_credentials.py` | Modify | 项目优先、回退、元数据、无明文回显。 |
| `apps/api/tests/integration/test_platform_credential_routes.py` | Modify | 项目参数、RBAC、审计、OpenAPI。 |
| `apps/api/tests/unit/test_tiktok_creator_cookie_scope.py` | Create | `creator_cookie` 项目级优先与工作区回退。 |
| `docs/superpowers/plans/2026-10-22-governed-task-platform-c3-project-keys-credentials.md` | Commit | 本计划文件，随 Task 1 提交。 |
| `docs/ops/c3-c14-keys-connectors-handoff.md` | Create | C14 的 `/keys` 与 `/connectors` 浏览器交接判据。 |

---

### Task 1: 只读契约守卫与 C2 依赖门禁

**Files:**
- Create: `apps/api/tests/unit/test_contract_freeze_c3.py`
- Commit: `docs/superpowers/plans/2026-10-22-governed-task-platform-c3-project-keys-credentials.md`

**Interfaces:**
- Consumes: C1 契约 v1.1、`configs/contracts/v1.1.0/registry.json`；C2 的 `api/authz.py`、`api/deps.py`、`core/errors.py`、`services/audit_log.py`。
- Produces: `C3_CONTRACT_READY=yes`；C3 只使用 C1 已登记的名称。
- Produces: 分支 `feat/gov-c3`，起点 `feat/gov-c2`。

- [ ] **Step 1: 从 C2 分支创建独立 worktree**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
git worktree prune
git rev-parse --verify feat/gov-c2^{commit}
git worktree add ../data_scrapy-gov-c3 -b feat/gov-c3 feat/gov-c2
cd ../data_scrapy-gov-c3
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c3-project-keys-credentials.md docs/superpowers/plans/
git branch --show-current
git merge-base --is-ancestor feat/gov-c2 HEAD; echo "c2_ancestor=$?"
cd apps/api && uv run alembic heads
cd /Users/lute/Project/data_scrapy-gov-c3
test -f configs/contracts/v1.1.0/registry.json && echo "C1_REGISTRY_PRESENT"
```

Expected:

```text
feat/gov-c3
c2_ancestor=0
202610220058 (head)
C1_REGISTRY_PRESENT
```

`feat/gov-c3` 已存在时停止，先审查旧分支。Alembic head 不是 `202610220058` 或 registry 缺失时停止，先完成 C0/C1/C2。

- [ ] **Step 2: 写只读契约与依赖守卫测试**

Create `apps/api/tests/unit/test_contract_freeze_c3.py`:

```python
"""C3 契约与 C2 依赖守卫。"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"


def test_c3_contract_entries_are_registered() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    required = (
        "platform_credential_bundles",
        "creator_cookie_metadata",
        "capability_allowlist",
        "tool_allowlist",
        "rotation_group_id",
        "superseded_by_key_id",
        "last_rotated_at",
        "expires_at",
        "daily_budget_usd",
        "/api/projects/{project_id}/keys",
        "/api/projects/{project_id}/keys/{key_id}/rotate",
        "/api/settings/platform-credentials/{platform}",
        "project_api_key_active_exists",
        "project_api_key_not_found",
        "connector_not_found",
        "credential_invalid",
        "vault_write_disabled",
        "project_not_found",
        "project_id IS NULL",
        "project_id IS NOT NULL",
        "uq_platform_credential_bundles_workspace_provider",
        "uq_platform_credential_bundles_project_provider",
        "fk_platform_credential_bundles_workspace_project_projects",
        "fk_project_api_keys_workspace_project_projects",
        "uq_project_api_keys_active_project",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"C3 contract entries missing: {missing}"


def test_c3_registry_entries_exist() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    project_keys = next(
        table for table in registry["tables"] if table["name"] == "project_api_keys"
    )
    columns = {column["name"] for column in project_keys["columns"]}
    assert {"tool_allowlist", "capability_allowlist", "rotation_group_id"} <= columns
    constraints = set(project_keys.get("constraints", []))
    assert "fk_project_api_keys_workspace_project_projects" in constraints
    assert "uq_project_api_keys_active_project" in constraints
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("GET", "/api/settings/platform-credentials") in paths
    assert ("PUT", "/api/settings/platform-credentials/{platform}") in paths
    assert ("DELETE", "/api/settings/platform-credentials/{platform}") in paths
    assert ("POST", "/api/settings/platform-credentials") not in paths


def test_c2_public_interfaces_are_importable() -> None:
    from data_intelligence_hub.api.authz import require_project_access, require_workspace_role
    from data_intelligence_hub.api.deps import RequestIdDep
    from data_intelligence_hub.core.errors import APIError
    from data_intelligence_hub.services.audit_log import append_audit_event

    assert callable(require_workspace_role)
    assert callable(require_project_access)
    assert RequestIdDep is not None
    assert issubclass(APIError, Exception)
    assert callable(append_audit_event)


def test_c2_migration_precedes_c3() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(PROJECT_ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "apps/api/alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_revision("202610220058") is not None
    heads = script.get_heads()
    assert len(heads) == 1
    ancestors: set[str] = set()
    current: str | None = heads[0]
    while current is not None:
        ancestors.add(current)
        revision = script.get_revision(current)
        down = getattr(revision, "down_revision", None)
        current = down if isinstance(down, str) else None
    assert "202610220058" in ancestors
```

- [ ] **Step 3: 运行守卫测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_contract_freeze_c3.py -v
```

Expected: 4 passed。缺任一 token 时停止，把缺口交回 C1；C3 不得修改契约。

- [ ] **Step 4: 运行 C1 checker**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `registry check OK`。

- [ ] **Step 5: 提交前运行 GitNexus 变更分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
git add apps/api/tests/unit/test_contract_freeze_c3.py \
  docs/superpowers/plans/2026-10-22-governed-task-platform-c3-project-keys-credentials.md
git commit -m "test(contract): guard C3 project keys and credential scope"
```

Expected: `detect-changes` 不含 `partial: true` 或 `truncated: true`；提交成功。

---

### Task 2: 迁移 059 与模型复合约束

**Files:**
- Create: `apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py`
- Modify: `apps/api/src/data_intelligence_hub/models/project_api_key.py`
- Modify: `apps/api/src/data_intelligence_hub/models/platform_credential.py`
- Test: `apps/api/tests/unit/test_c3_migration_source.py`

**Interfaces:**
- Consumes: `projects` 的 `uq_projects_workspace_id (workspace_id, id)`；C2 revision `202610220058`。
- Produces: `ProjectApiKey.capability_allowlist`、`daily_budget_usd`、`status`、`rotation_group_id`、`superseded_by_key_id`、`last_rotated_at`、`expires_at`。
- Produces: `PlatformCredentialBundle.project_id`、`creator_cookie_metadata`。
- Produces: Alembic revision `202610220059`，`down_revision = "202610220058"`。

- [ ] **Step 0: 编辑前运行 GitNexus impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs impact "ProjectApiKey" --direction upstream --repo .
node .gitnexus/run.cjs impact "PlatformCredentialBundle" --direction upstream --repo .
```

Expected: 记录调用方、进程与风险。HIGH/CRITICAL 先报告并给出缓解；`UNKNOWN` 用 `rg -n "ProjectApiKey|PlatformCredentialBundle" apps/api` 复核，不得按低风险处理。

- [ ] **Step 1: 写失败的迁移与模型守卫测试**

Create `apps/api/tests/unit/test_c3_migration_source.py`:

```python
"""C3 迁移与模型约束守卫。"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610220059_project_keys_credentials_scope.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("c3_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_059_is_linear_after_c2() -> None:
    module = _load()
    assert module.revision == "202610220059"
    assert module.down_revision == "202610220058"

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1
    ancestors: set[str] = set()
    current: str | None = heads[0]
    while current is not None:
        ancestors.add(current)
        revision = script.get_revision(current)
        down = getattr(revision, "down_revision", None)
        current = down if isinstance(down, str) else None
    assert module.revision in ancestors


def test_upgrade_declares_null_trap_and_composite_foreign_keys() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    for token in (
        "capability_allowlist",
        "creator_cookie_metadata",
        "fk_project_api_keys_workspace_project_projects",
        "fk_platform_credential_bundles_workspace_project_projects",
        "uq_platform_credential_bundles_workspace_provider",
        "uq_platform_credential_bundles_project_provider",
        "project_id IS NULL",
        "project_id IS NOT NULL",
        "cross-workspace project_api_keys rows exist",
        "UPDATE project_api_keys SET status = 'revoked'",
        "downgrade refused: project-scoped credential bundles exist",
        "downgrade refused: project capability allowlists exist",
    ):
        assert token in source


def test_models_declare_composite_tenant_foreign_keys() -> None:
    for table_name, fk_name in (
        ("project_api_keys", "fk_project_api_keys_workspace_project_projects"),
        (
            "platform_credential_bundles",
            "fk_platform_credential_bundles_workspace_project_projects",
        ),
    ):
        table = Base.metadata.tables[table_name]
        assert any(
            fk.name == fk_name and len(fk.columns) == 2
            for fk in table.foreign_key_constraints
        ), f"{table_name} missing {fk_name}"


def test_platform_credential_indexes_are_partial() -> None:
    indexes = {
        index.name: index for index in PlatformCredentialBundle.__table__.indexes
    }
    workspace_index = indexes["uq_platform_credential_bundles_workspace_provider"]
    project_index = indexes["uq_platform_credential_bundles_project_provider"]
    assert workspace_index.unique is True
    assert project_index.unique is True
    assert (
        str(workspace_index.dialect_options["postgresql"]["where"])
        == "project_id IS NULL"
    )
    assert (
        str(project_index.dialect_options["postgresql"]["where"])
        == "project_id IS NOT NULL"
    )


@pytest.mark.anyio
async def test_null_project_scope_cannot_duplicate_and_cross_workspace_key_is_rejected() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        owner = User(
            email=f"c3-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        session.add(owner)
        await session.flush()
        workspace_a = Workspace(
            name="A", slug=f"a-{uuid.uuid4().hex}", owner_id=owner.id
        )
        workspace_b = Workspace(
            name="B", slug=f"b-{uuid.uuid4().hex}", owner_id=owner.id
        )
        session.add_all([workspace_a, workspace_b])
        await session.flush()
        project_a = Project(
            workspace_id=workspace_a.id,
            name="A1",
            domain="mixed",
            owner_id=owner.id,
        )
        session.add(project_a)
        await session.flush()
        session.add(
            PlatformCredentialBundle(
                workspace_id=workspace_a.id,
                project_id=None,
                provider_id="youtube",
                encrypted_payload="x",
                configured_fields=[],
                key_version="fernet.v1",
                created_by_user_id=owner.id,
                updated_by_user_id=owner.id,
            )
        )
        await session.commit()
        user_id = owner.id
        workspace_a_id = workspace_a.id
        workspace_b_id = workspace_b.id
        project_a_id = project_a.id

    async with factory() as session:
        session.add(
            PlatformCredentialBundle(
                workspace_id=workspace_a_id,
                project_id=None,
                provider_id="youtube",
                encrypted_payload="y",
                configured_fields=[],
                key_version="fernet.v1",
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with factory() as session:
        session.add(
            ProjectApiKey(
                project_id=project_a_id,
                workspace_id=workspace_b_id,
                label="cross",
                key_prefix="dih_test",
                key_hash="b" * 64,
                created_by_user_id=user_id,
                tool_allowlist=["collect"],
                daily_collect_quota=1,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    await engine.dispose()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_c3_migration_source.py -v
```

Expected: FAIL。迁移文件不存在；`PlatformCredentialBundle` 缺 `project_id`；`ProjectApiKey` 缺复合 FK。

- [ ] **Step 3: 修改 `ProjectApiKey` 模型**

Replace `apps/api/src/data_intelligence_hub/models/project_api_key.py` with:

```python
"""项目级 API 密钥的持久化模型。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ProjectApiKey(UUIDPrimaryKeyMixin, Base):
    """一行代表一把项目级 MCP 密钥。"""

    __tablename__ = "project_api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_project_api_keys_key_hash"),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_project_api_keys_workspace_project_projects",
            ondelete="CASCADE",
        ),
        Index("ix_project_api_keys_workspace_project", "workspace_id", "project_id"),
        Index(
            "uq_project_api_keys_active_project",
            "project_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tool_allowlist: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    capability_allowlist: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    daily_collect_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    quota_date: Mapped[date | None] = mapped_column(Date())
    quota_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default=text("'active'")
    )
    rotation_group_id: Mapped[uuid.UUID | None] = mapped_column()
    superseded_by_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_api_keys.id")
    )
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: 修改 `PlatformCredentialBundle` 模型**

Replace `apps/api/src/data_intelligence_hub/models/platform_credential.py` with:

```python
"""Provider 凭据密文模型。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformCredentialBundle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_credential_bundles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_platform_credential_bundles_workspace_project_projects",
            ondelete="CASCADE",
        ),
        Index(
            "uq_platform_credential_bundles_workspace_provider",
            "workspace_id",
            "provider_id",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
            sqlite_where=text("project_id IS NULL"),
        ),
        Index(
            "uq_platform_credential_bundles_project_provider",
            "workspace_id",
            "project_id",
            "provider_id",
            unique=True,
            postgresql_where=text("project_id IS NOT NULL"),
            sqlite_where=text("project_id IS NOT NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column()
    provider_id: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    configured_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    creator_cookie_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    key_version: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
```

- [ ] **Step 5: 写迁移 059**

Create `apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py`:

```python
"""Project key governance and project-scoped credentials.

Revision ID: 202610220059
Revises: 202610220058
Create Date: 2026-10-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

Postgres NULL uniqueness trap:
``UNIQUE (workspace_id, provider_id, project_id)`` does not make two
workspace-scoped rows equal because ``project_id IS NULL``. This migration
uses two partial unique indexes instead.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220059"
down_revision: str | None = "202610220058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_no_cross_workspace_keys() -> None:
    bind = op.get_bind()
    mismatched = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM project_api_keys k "
            "JOIN projects p ON p.id = k.project_id "
            "WHERE p.workspace_id <> k.workspace_id"
        )
    ).scalar_one()
    if mismatched:
        raise RuntimeError(
            "migration refused: cross-workspace project_api_keys rows exist"
        )


def upgrade() -> None:
    _assert_no_cross_workspace_keys()

    op.add_column(
        "project_api_keys",
        sa.Column(
            "capability_allowlist",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "project_api_keys",
        sa.Column("daily_budget_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "project_api_keys",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column(
        "project_api_keys", sa.Column("rotation_group_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "project_api_keys",
        sa.Column("superseded_by_key_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "project_api_keys",
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_api_keys",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE project_api_keys SET status = 'revoked' "
        "WHERE revoked_at IS NOT NULL"
    )

    with op.batch_alter_table("project_api_keys") as batch_op:
        batch_op.drop_constraint(
            "fk_project_api_keys_project_id_projects", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_project_api_keys_workspace_project_projects",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_project_api_keys_superseded_by_key_id",
            "project_api_keys",
            ["superseded_by_key_id"],
            ["id"],
        )

    op.add_column(
        "platform_credential_bundles",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "platform_credential_bundles",
        sa.Column("creator_cookie_metadata", sa.JSON(), nullable=True),
    )

    with op.batch_alter_table("platform_credential_bundles") as batch_op:
        batch_op.drop_constraint(
            "uq_platform_credential_bundles_workspace_provider", type_="unique"
        )
        batch_op.create_foreign_key(
            "fk_platform_credential_bundles_workspace_project_projects",
            "projects",
            ["workspace_id", "project_id"],
            ["workspace_id", "id"],
            ondelete="CASCADE",
        )

    op.create_index(
        "uq_platform_credential_bundles_workspace_provider",
        "platform_credential_bundles",
        ["workspace_id", "provider_id"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
        sqlite_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_platform_credential_bundles_project_provider",
        "platform_credential_bundles",
        ["workspace_id", "project_id", "provider_id"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
        sqlite_where=sa.text("project_id IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    project_scoped = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM platform_credential_bundles "
            "WHERE project_id IS NOT NULL"
        )
    ).scalar_one()
    if project_scoped:
        raise RuntimeError(
            "downgrade refused: project-scoped credential bundles exist"
        )
    non_empty = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM project_api_keys "
            "WHERE CAST(capability_allowlist AS TEXT) NOT IN ('[]', 'null')"
        )
    ).scalar_one()
    if non_empty:
        raise RuntimeError(
            "downgrade refused: project capability allowlists exist"
        )

    op.drop_index(
        "uq_platform_credential_bundles_project_provider",
        table_name="platform_credential_bundles",
    )
    op.drop_index(
        "uq_platform_credential_bundles_workspace_provider",
        table_name="platform_credential_bundles",
    )
    with op.batch_alter_table("platform_credential_bundles") as batch_op:
        batch_op.drop_constraint(
            "fk_platform_credential_bundles_workspace_project_projects",
            type_="foreignkey",
        )
        batch_op.create_unique_constraint(
            "uq_platform_credential_bundles_workspace_provider",
            ["workspace_id", "provider_id"],
        )
    op.drop_column("platform_credential_bundles", "creator_cookie_metadata")
    op.drop_column("platform_credential_bundles", "project_id")

    with op.batch_alter_table("project_api_keys") as batch_op:
        batch_op.drop_constraint(
            "fk_project_api_keys_superseded_by_key_id", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_project_api_keys_workspace_project_projects", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_project_api_keys_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )
    op.drop_column("project_api_keys", "expires_at")
    op.drop_column("project_api_keys", "last_rotated_at")
    op.drop_column("project_api_keys", "superseded_by_key_id")
    op.drop_column("project_api_keys", "rotation_group_id")
    op.drop_column("project_api_keys", "status")
    op.drop_column("project_api_keys", "daily_budget_usd")
    op.drop_column("project_api_keys", "capability_allowlist")
```

- [ ] **Step 6: 运行迁移测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_c3_migration_source.py -v
```

Expected: `5 passed`。SQLite 上两个工作区级同 provider 行被部分唯一索引拒绝；跨工作区密钥被复合 FK 拒绝。

- [ ] **Step 7: 检查迁移 head**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m alembic heads
```

Expected: 只有一行 `202610220059 (head)`。本步不执行 `upgrade`。

- [ ] **Step 8: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220059_project_keys_credentials_scope.py \
  apps/api/src/data_intelligence_hub/models/project_api_key.py \
  apps/api/src/data_intelligence_hub/models/platform_credential.py \
  apps/api/tests/unit/test_c3_migration_source.py
git commit -m "feat(schema): add key rotation fields and credential project scope"
```

---

### Task 3: capability 白名单、状态与过期检查

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/repositories/project_api_keys.py`
- Modify: `apps/api/src/data_intelligence_hub/services/project_api_keys.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/project_api_key.py`
- Test: `apps/api/tests/unit/test_project_api_keys.py`

**Interfaces:**
- Consumes: `ProjectApiKey` 新列。
- Produces: `normalize_capability_allowlist(values: Sequence[str]) -> tuple[str, ...]`。
- Produces: `ProjectApiKeyIdentity.capability_allowlist: tuple[str, ...]` 与 `allows_capability(capability_id: str) -> bool`。
- Produces: `issue_key(..., capability_allowlist: Sequence[str] = (), rotation_group_id: uuid.UUID | None = None, last_rotated_at: datetime | None = None, expires_at: datetime | None = None) -> IssuedProjectApiKey`。
- Produces: `ProjectApiKeyResponse.capability_allowlist`、`status`、`rotation_group_id`、`superseded_by_key_id`、`last_rotated_at`、`expires_at`、`daily_budget_usd`。

- [ ] **Step 1: 写失败的服务测试**

Append to `apps/api/tests/unit/test_project_api_keys.py`:

```python
@pytest.mark.anyio
async def test_capability_allowlist_is_normalized_deduplicated_and_persisted() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await issue_key(
            session,
            project_id=seed.project_a1.id,
            workspace_id=seed.workspace_a.id,
            label="caps",
            created_by_user_id=seed.owner.id,
            tool_allowlist=("collect",),
            daily_collect_quota=10,
            capability_allowlist=("tikhub.tiktok.video.search.us", " tikhub.tiktok.video.search.us ", "tikhub.tiktok.comment.list.us"),
        )
        await session.commit()
        identity = await authenticate_key(session, issued.plaintext)
        assert identity is not None
        observed["capabilities"] = identity.capability_allowlist
        observed["allows"] = identity.allows_capability("tikhub.tiktok.video.search.us")
        observed["denies"] = identity.allows_capability("tikhub.tiktok.user.info.us")

    await _with_session(scenario)

    assert observed["capabilities"] == (
        "tikhub.tiktok.video.search.us",
        "tikhub.tiktok.comment.list.us",
    )
    assert observed["allows"] is True
    assert observed["denies"] is False


@pytest.mark.anyio
async def test_revoked_or_expired_status_is_rejected() -> None:
    from datetime import UTC, datetime, timedelta

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await issue_key(
            session,
            project_id=seed.project_a1.id,
            workspace_id=seed.workspace_a.id,
            label="expired",
            created_by_user_id=seed.owner.id,
            tool_allowlist=("collect",),
            daily_collect_quota=10,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        await session.commit()
        assert await authenticate_key(session, issued.plaintext) is None

        issued.record.status = "revoked"
        await session.commit()
        assert await authenticate_key(session, issued.plaintext) is None

    await _with_session(scenario)


@pytest.mark.anyio
async def test_capability_allowlist_rejects_oversized_value() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        with pytest.raises(ValueError, match="capability_allowlist_invalid"):
            await issue_key(
                session,
                project_id=seed.project_a1.id,
                workspace_id=seed.workspace_a.id,
                label="bad",
                created_by_user_id=seed.owner.id,
                tool_allowlist=("collect",),
                daily_collect_quota=10,
                capability_allowlist=("x" * 201,),
            )

    await _with_session(scenario)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_keys.py -k "capability or expired" -v
```

Expected: FAIL。`issue_key` 不接受 `capability_allowlist`；`ProjectApiKeyIdentity` 没有该字段。

- [ ] **Step 3: 修改仓储 `create_key`**

In `apps/api/src/data_intelligence_hub/repositories/project_api_keys.py`, change `create_key`:

```python
async def create_key(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    label: str,
    key_prefix: str,
    key_hash: str,
    created_by_user_id: uuid.UUID,
    tool_allowlist: Sequence[str],
    daily_collect_quota: int,
    capability_allowlist: Sequence[str] = (),
    rotation_group_id: uuid.UUID | None = None,
    last_rotated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ProjectApiKey:
    record = ProjectApiKey(
        project_id=project_id,
        workspace_id=workspace_id,
        label=label,
        key_prefix=key_prefix,
        key_hash=key_hash,
        created_by_user_id=created_by_user_id,
        tool_allowlist=list(tool_allowlist),
        capability_allowlist=list(capability_allowlist),
        daily_collect_quota=daily_collect_quota,
        status="active",
        rotation_group_id=rotation_group_id,
        last_rotated_at=last_rotated_at,
        expires_at=expires_at,
    )
    session.add(record)
    await session.flush()
    return record
```

- [ ] **Step 4: 修改服务：规范化、身份字段、状态检查**

In `apps/api/src/data_intelligence_hub/services/project_api_keys.py`, add:

```python
MAX_CAPABILITY_ALLOWLIST = 500
MAX_CAPABILITY_ID_LENGTH = 200


def normalize_capability_allowlist(values: Sequence[str]) -> tuple[str, ...]:
    """去空白、去重、保序。空列表合法；超长或非字符串按配置错误拒绝。"""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("capability_allowlist_invalid")
        value = raw.strip()
        if not value:
            continue
        if len(value) > MAX_CAPABILITY_ID_LENGTH:
            raise ValueError("capability_allowlist_invalid")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    if len(normalized) > MAX_CAPABILITY_ALLOWLIST:
        raise ValueError("capability_allowlist_too_large")
    return tuple(normalized)
```

Change `ProjectApiKeyIdentity`:

```python
@dataclasses.dataclass(frozen=True, slots=True)
class ProjectApiKeyIdentity:
    key_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: str
    tool_allowlist: tuple[str, ...]
    capability_allowlist: tuple[str, ...]
    daily_collect_quota: int

    def allows_tool(self, tool_name: str) -> bool:
        return tool_name in self.tool_allowlist

    def allows_capability(self, capability_id: str) -> bool:
        return capability_id in self.capability_allowlist
```

Change `issue_key` signature and body:

```python
async def issue_key(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    label: str,
    created_by_user_id: uuid.UUID,
    tool_allowlist: Sequence[str],
    daily_collect_quota: int,
    capability_allowlist: Sequence[str] = (),
    rotation_group_id: uuid.UUID | None = None,
    last_rotated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> IssuedProjectApiKey:
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("project_api_key_label_required")
    normalized_allowlist = tuple(item.strip() for item in tool_allowlist if item.strip())
    if not normalized_allowlist:
        raise ValueError("project_api_key_allowlist_required")
    if daily_collect_quota < 1:
        raise ValueError("project_api_key_quota_must_be_positive")
    normalized_capabilities = normalize_capability_allowlist(capability_allowlist)
    plaintext, key_prefix = generate_plaintext()
    record = await create_key(
        session,
        project_id=project_id,
        workspace_id=workspace_id,
        label=normalized_label,
        key_prefix=key_prefix,
        key_hash=hash_key(plaintext),
        created_by_user_id=created_by_user_id,
        tool_allowlist=normalized_allowlist,
        capability_allowlist=normalized_capabilities,
        daily_collect_quota=daily_collect_quota,
        rotation_group_id=rotation_group_id,
        last_rotated_at=last_rotated_at,
        expires_at=expires_at,
    )
    return IssuedProjectApiKey(plaintext=plaintext, record=record)
```

Change `authenticate_key`:

```python
async def authenticate_key(
    session: AsyncSession,
    plaintext: str,
    *,
    now: datetime | None = None,
) -> ProjectApiKeyIdentity | None:
    if not plaintext:
        return None
    record = await find_by_hash(session, hash_key(plaintext))
    current = now or datetime.now(UTC)
    if record is None or record.revoked_at is not None or record.status != "active":
        return None
    if record.expires_at is not None and record.expires_at <= current:
        return None
    return ProjectApiKeyIdentity(
        key_id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        key_prefix=record.key_prefix,
        label=record.label,
        tool_allowlist=tuple(record.tool_allowlist or ()),
        capability_allowlist=tuple(record.capability_allowlist or ()),
        daily_collect_quota=record.daily_collect_quota,
    )
```

Add `from datetime import UTC, datetime` to imports.

- [ ] **Step 5: 修改请求与响应模型**

Replace `apps/api/src/data_intelligence_hub/schemas/project_api_key.py` with:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IssueProjectApiKeyRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    tool_allowlist: list[str] = Field(min_length=1)
    capability_allowlist: list[str] = Field(default_factory=list, max_length=500)
    daily_collect_quota: int = Field(ge=1, le=100000)
    expires_at: datetime | None = None


class RotateProjectApiKeyRequest(IssueProjectApiKeyRequest):
    pass


class ProjectApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    label: str
    key_prefix: str
    tool_allowlist: list[str]
    capability_allowlist: list[str]
    daily_collect_quota: int
    daily_budget_usd: Decimal | None = None
    quota_date: object | None = None
    quota_used: int = 0
    status: str
    rotation_group_id: uuid.UUID | None = None
    superseded_by_key_id: uuid.UUID | None = None
    last_rotated_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class IssuedProjectApiKeyResponse(ProjectApiKeyResponse):
    plaintext: str
```

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_keys.py -v
```

Expected: 全部 passed。旧用例不传 `capability_allowlist` 时默认空元组。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/project_api_keys.py \
  apps/api/src/data_intelligence_hub/services/project_api_keys.py \
  apps/api/src/data_intelligence_hub/schemas/project_api_key.py \
  apps/api/tests/unit/test_project_api_keys.py
git commit -m "feat(keys): add capability allowlist and key status checks"
```

---

### Task 4: 原子轮换与 last_used_at 节流

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/repositories/project_api_keys.py`
- Modify: `apps/api/src/data_intelligence_hub/services/project_api_keys.py`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py`
- Test: `apps/api/tests/unit/test_project_api_keys.py`

**Interfaces:**
- Consumes: `ProjectApiKey.status`、`rotation_group_id`、`superseded_by_key_id`、`last_rotated_at`、`expires_at`。
- Produces: `get_key_for_update(session, *, workspace_id, project_id, key_id) -> ProjectApiKey | None`。
- Produces: `revoke_key_with_state(...) -> RevokedProjectApiKey | None`。
- Produces: `touch_last_used(session, key_id, *, now=None) -> bool`。
- Produces: `rotate_key(...) -> RotatedProjectApiKey`。
- Produces: `ProjectApiKeyNotFoundError`、`ProjectApiKeyStateError`。

- [ ] **Step 0: 编辑前运行 GitNexus impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs impact "issue_key" --direction upstream --repo .
node .gitnexus/run.cjs impact "authenticate_key" --direction upstream --repo .
node .gitnexus/run.cjs impact "revoke_key" --direction upstream --repo .
```

Expected: 记录调用方与风险；HIGH/CRITICAL 先报告；`UNKNOWN` 用文本搜索复核。

- [ ] **Step 1: 写失败的轮换与 last_used 测试**

Append to `apps/api/tests/unit/test_project_api_keys.py`:

```python
@pytest.mark.anyio
async def test_rotation_revokes_old_and_returns_new_plaintext() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        first = await _issue(session, seed, project=seed.project_a1, label="v1")
        await session.commit()
        result = await rotate_key(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a1.id,
            key_id=first.record.id,
            label="v2",
            created_by_user_id=seed.owner.id,
            tool_allowlist=("collect",),
            capability_allowlist=("tikhub.tiktok.video.search.us",),
            daily_collect_quota=20,
        )
        await session.commit()
        observed["old_auth"] = await authenticate_key(session, first.plaintext)
        observed["new_auth"] = await authenticate_key(session, result.issued.plaintext)
        old = await session.get(ProjectApiKey, first.record.id)
        assert old is not None
        observed["old_status"] = old.status
        observed["superseded_by"] = old.superseded_by_key_id
        observed["new_id"] = result.issued.record.id
        observed["rotation_group"] = old.rotation_group_id
        observed["new_rotation_group"] = result.issued.record.rotation_group_id

    await _with_session(scenario)

    assert observed["old_auth"] is None
    assert observed["new_auth"] is not None
    assert observed["old_status"] == "revoked"
    assert observed["superseded_by"] == observed["new_id"]
    assert observed["rotation_group"] is not None
    assert observed["rotation_group"] == observed["new_rotation_group"]


@pytest.mark.anyio
async def test_rotation_failure_leaves_old_key_active_after_rollback() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        first = await _issue(session, seed, project=seed.project_a1, label="v1")
        await session.commit()
        try:
            await rotate_key(
                session,
                workspace_id=seed.workspace_a.id,
                project_id=seed.project_a1.id,
                key_id=first.record.id,
                label="v2",
                created_by_user_id=seed.owner.id,
                tool_allowlist=("collect",),
                daily_collect_quota=0,
            )
        except ValueError:
            await session.rollback()
        observed["old_auth"] = await authenticate_key(session, first.plaintext)

    await _with_session(scenario)
    assert observed["old_auth"] is not None


@pytest.mark.anyio
async def test_last_used_is_touched_with_throttle() -> None:
    from datetime import UTC, datetime, timedelta

    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await _issue(session, seed, project=seed.project_a1)
        await session.commit()
        base = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        await authenticate_key(session, issued.plaintext, now=base)
        await session.commit()
        first = await session.get(ProjectApiKey, issued.record.id)
        assert first is not None
        observed["first"] = first.last_used_at
        await authenticate_key(session, issued.plaintext, now=base + timedelta(seconds=30))
        await session.commit()
        second = await session.get(ProjectApiKey, issued.record.id)
        assert second is not None
        observed["second"] = second.last_used_at
        await authenticate_key(session, issued.plaintext, now=base + timedelta(seconds=61))
        await session.commit()
        third = await session.get(ProjectApiKey, issued.record.id)
        assert third is not None
        observed["third"] = third.last_used_at

    await _with_session(scenario)
    assert observed["first"] == observed["second"]
    assert observed["third"] != observed["first"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_keys.py -k "rotation or last_used" -v
```

Expected: FAIL。`rotate_key` 与 `touch_last_used` 未定义。

- [ ] **Step 3: 增加仓储锁定、撤销状态与 last_used**

In `apps/api/src/data_intelligence_hub/repositories/project_api_keys.py`, add:

```python
import dataclasses
from datetime import timedelta

LAST_USED_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclasses.dataclass(frozen=True, slots=True)
class RevokedProjectApiKey:
    record: ProjectApiKey
    changed: bool


async def get_key_for_update(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
) -> ProjectApiKey | None:
    result = await session.execute(
        select(ProjectApiKey)
        .where(
            ProjectApiKey.id == key_id,
            ProjectApiKey.workspace_id == workspace_id,
            ProjectApiKey.project_id == project_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def revoke_key_with_state(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    revoked_at: datetime | None = None,
) -> RevokedProjectApiKey | None:
    result = await session.execute(
        select(ProjectApiKey)
        .where(
            ProjectApiKey.id == key_id,
            ProjectApiKey.workspace_id == workspace_id,
            ProjectApiKey.project_id == project_id,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = revoked_at or datetime.now(UTC)
        record.status = "revoked"
        await session.flush()
        return RevokedProjectApiKey(record=record, changed=True)
    return RevokedProjectApiKey(record=record, changed=False)


async def touch_last_used(
    session: AsyncSession,
    key_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> bool:
    timestamp = now or datetime.now(UTC)
    cutoff = timestamp - LAST_USED_TOUCH_INTERVAL
    statement = (
        update(ProjectApiKey)
        .where(
            ProjectApiKey.id == key_id,
            ProjectApiKey.revoked_at.is_(None),
            or_(
                ProjectApiKey.last_used_at.is_(None),
                ProjectApiKey.last_used_at < cutoff,
            ),
        )
        .values(last_used_at=timestamp)
    )
    result = await session.execute(statement)
    return result.rowcount == 1
```

Change existing `revoke_key`:

```python
async def revoke_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    revoked_at: datetime | None = None,
) -> ProjectApiKey | None:
    result = await revoke_key_with_state(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        key_id=key_id,
        revoked_at=revoked_at,
    )
    return None if result is None else result.record
```

Add to `__all__`: `"RevokedProjectApiKey"`, `"get_key_for_update"`, `"revoke_key_with_state"`, `"touch_last_used"`.

- [ ] **Step 4: 增加服务轮换与鉴权触发**

In `apps/api/src/data_intelligence_hub/services/project_api_keys.py`, add imports:

```python
from data_intelligence_hub.repositories.project_api_keys import (
    create_key,
    find_by_hash,
    get_key_for_update,
    touch_last_used,
)
```

Add:

```python
class ProjectApiKeyNotFoundError(RuntimeError):
    code = "project_api_key_not_found"


class ProjectApiKeyStateError(RuntimeError):
    code = "state_conflict"


@dataclasses.dataclass(frozen=True, slots=True)
class RotatedProjectApiKey:
    issued: IssuedProjectApiKey
    revoked_key_id: uuid.UUID


async def rotate_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    label: str,
    created_by_user_id: uuid.UUID,
    tool_allowlist: Sequence[str],
    daily_collect_quota: int,
    capability_allowlist: Sequence[str] = (),
    expires_at: datetime | None = None,
    now: datetime | None = None,
) -> RotatedProjectApiKey:
    """原子轮换指定密钥。调用方负责 commit；任一步失败回滚整个事务。"""
    current = await get_key_for_update(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        key_id=key_id,
    )
    if current is None:
        raise ProjectApiKeyNotFoundError("project_api_key_not_found")
    timestamp = now or datetime.now(UTC)
    if current.status != "active" or current.revoked_at is not None:
        raise ProjectApiKeyStateError("state_conflict")
    if current.expires_at is not None and current.expires_at <= timestamp:
        raise ProjectApiKeyStateError("state_conflict")

    rotation_group_id = current.rotation_group_id or uuid.uuid4()
    current.rotation_group_id = rotation_group_id
    current.status = "rotating"
    current.revoked_at = timestamp
    await session.flush()

    issued = await issue_key(
        session,
        project_id=project_id,
        workspace_id=workspace_id,
        label=label,
        created_by_user_id=created_by_user_id,
        tool_allowlist=tool_allowlist,
        capability_allowlist=capability_allowlist,
        daily_collect_quota=daily_collect_quota,
        rotation_group_id=rotation_group_id,
        last_rotated_at=timestamp,
        expires_at=expires_at,
    )
    current.superseded_by_key_id = issued.record.id
    current.status = "revoked"
    await session.flush()
    return RotatedProjectApiKey(issued=issued, revoked_key_id=current.id)
```

In `authenticate_key`, after the expiry check and before constructing the identity:

```python
    await touch_last_used(session, record.id, now=current)
```

Add `"ProjectApiKeyNotFoundError"`, `"ProjectApiKeyStateError"`, `"RotatedProjectApiKey"`, `"normalize_capability_allowlist"` to `__all__`.

- [ ] **Step 5: 让 MCP 中间件提交 last_used_at**

In `apps/api/src/data_intelligence_hub/mcp_runtime/auth.py`, change `_resolve_project_key`:

```python
    async def _resolve_project_key(self, token: str) -> ProjectApiKeyContext | None:
        try:
            async with self._session_factory() as session:
                identity = await authenticate_key(session, token)
                if identity is None:
                    return None
                try:
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    logger.warning(
                        "mcp_project_key_last_used_failed",
                        error_type=type(exc).__name__,
                    )
        except Exception as exc:
            logger.warning(
                "mcp_project_key_lookup_failed",
                error_type=type(exc).__name__,
            )
            return None
        return ProjectApiKeyContext(
            key_id=identity.key_id,
            workspace_id=identity.workspace_id,
            project_id=identity.project_id,
            key_prefix=identity.key_prefix,
            label=identity.label,
        )
```

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_keys.py -v
```

Expected: 全部 passed。轮换失败用例在 `rollback` 后旧密钥仍可鉴权；`last_used_at` 在 60 秒内不重复写。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/project_api_keys.py \
  apps/api/src/data_intelligence_hub/services/project_api_keys.py \
  apps/api/src/data_intelligence_hub/mcp_runtime/auth.py \
  apps/api/tests/unit/test_project_api_keys.py
git commit -m "feat(keys): rotate atomically and track last use"
```

---

### Task 5: 规范密钥管理路由与审计

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py`
- Test: `apps/api/tests/unit/test_project_api_key_routes.py`

**Interfaces:**
- Consumes: C2 `APIError`、`RequestIdDep`、`append_audit_event`、`_project_or_404` 的 owner/admin 检查。
- Produces: `POST/GET /api/projects/{project_id}/keys`。
- Produces: `POST /api/projects/{project_id}/keys/{key_id}/rotate`。
- Produces: `DELETE /api/projects/{project_id}/keys/{key_id}`。
- Produces: 隐藏的旧路径 `POST/GET /api/projects/{project_id}/api-keys` 与 `DELETE /api/projects/{project_id}/api-keys/{key_id}`。

- [ ] **Step 0: 编辑前运行 GitNexus impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs impact "issue_key" --direction upstream --repo .
node .gitnexus/run.cjs impact "revoke_key" --direction upstream --repo .
node .gitnexus/run.cjs impact "ProjectApiKey" --direction upstream --repo .
```

Expected: 记录调用方与风险；HIGH/CRITICAL 先报告；`UNKNOWN` 用文本搜索复核。

- [ ] **Step 1: 写失败的路由测试**

Append to `apps/api/tests/unit/test_project_api_key_routes.py`:

```python
@pytest.mark.asyncio
async def test_canonical_key_paths_are_mounted(session_factory: async_sessionmaker[AsyncSession]) -> None:
    from data_intelligence_hub.main import create_app

    paths = create_app().openapi()["paths"]
    assert "/api/projects/{project_id}/keys" in paths
    assert "/api/projects/{project_id}/keys/{key_id}/rotate" in paths
    assert "/api/projects/{project_id}/keys/{key_id}" in paths
    assert "/api/projects/{project_id}/api-keys" not in paths


@pytest.mark.asyncio
async def test_rotate_route_revokes_and_audits(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from data_intelligence_hub.api.routes import project_api_keys as route_module

    audit = AsyncMock()
    monkeypatch.setattr(route_module, "append_audit_event", audit)

    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="v1",
                tool_allowlist=["web_search"],
                capability_allowlist=["tikhub.tiktok.video.search.us"],
                daily_collect_quota=5,
            ),
            session,
            context,
            "req-1",
        )
        rotated = await rotate_project_api_key(
            _ids()["project"],
            issued.id,
            IssueProjectApiKeyRequest(
                label="v2",
                tool_allowlist=["web_search"],
                capability_allowlist=["tikhub.tiktok.video.search.us"],
                daily_collect_quota=5,
            ),
            session,
            context,
            "req-2",
        )

    assert rotated.plaintext != issued.plaintext
    assert audit.await_count == 2
    assert audit.await_args_list[0].kwargs["action"] == "project_api_key.issued"
    assert audit.await_args_list[1].kwargs["action"] == "project_api_key.rotated"
    assert "plaintext" not in repr(audit.await_args_list)


@pytest.mark.asyncio
async def test_rotate_missing_key_returns_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from data_intelligence_hub.core.errors import APIError

    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        with pytest.raises(APIError) as exc:
            await rotate_project_api_key(
                _ids()["project"],
                uuid.uuid4(),
                IssueProjectApiKeyRequest(
                    label="v2",
                    tool_allowlist=["web_search"],
                    daily_collect_quota=5,
                ),
                session,
                context,
                "req-3",
            )
    assert exc.value.status_code == 404
    assert exc.value.code == "project_api_key_not_found"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_key_routes.py -k "canonical or rotate" -v
```

Expected: FAIL。`rotate_project_api_key` 未定义；OpenAPI 没有 `/keys`。

- [ ] **Step 3: 重写路由文件**

Replace `apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py` with:

```python
"""项目 API 密钥的签发、列表、轮换与撤销。

规范路径是 ``/api/projects/{project_id}/keys``。
旧 ``/api-keys`` 路径保留一个发布周期，但不出现在 OpenAPI。

鉴权：登录会话。工作区 owner/admin 可管理密钥。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.api.deps import (
    AuthenticatedContextDep,
    RequestIdDep,
    SessionDep,
)
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.repositories.project_api_keys import (
    list_keys,
    revoke_key_with_state,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.schemas.project_api_key import (
    IssuedProjectApiKeyResponse,
    IssueProjectApiKeyRequest,
    ProjectApiKeyResponse,
    RotateProjectApiKeyRequest,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.project_api_keys import (
    ProjectApiKeyNotFoundError,
    ProjectApiKeyStateError,
    issue_key,
    rotate_key,
)

router = APIRouter(tags=["project-api-keys"])


async def _project_or_404(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID,
):
    project = await get_project(session, context.workspace.id, project_id)
    if project is None:
        raise APIError(404, "project_not_found")
    role = await get_workspace_role(
        session, context.workspace.id, context.user.id
    )
    if role not in ("owner", "admin"):
        raise APIError(403, "project_key_management_forbidden")
    return project


def _response(record) -> ProjectApiKeyResponse:
    response = ProjectApiKeyResponse.model_validate(record)
    if (
        response.status == "active"
        and response.expires_at is not None
        and response.expires_at <= datetime.now(UTC)
    ):
        return response.model_copy(update={"status": "expired"})
    return response


@router.post(
    "/{project_id}/keys",
    response_model=IssuedProjectApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/{project_id}/api-keys",
    response_model=IssuedProjectApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def issue_project_api_key(
    project_id: uuid.UUID,
    payload: IssueProjectApiKeyRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> IssuedProjectApiKeyResponse:
    await _project_or_404(session, context, project_id)
    try:
        issued = await issue_key(
            session,
            project_id=project_id,
            workspace_id=context.workspace.id,
            label=payload.label,
            created_by_user_id=context.user.id,
            tool_allowlist=payload.tool_allowlist,
            capability_allowlist=payload.capability_allowlist,
            daily_collect_quota=payload.daily_collect_quota,
            expires_at=payload.expires_at,
        )
        await append_audit_event(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            actor_user_id=context.user.id,
            action="project_api_key.issued",
            resource_type="project_api_key",
            resource_id=str(issued.record.id),
            request_id=request_id,
            details={
                "key_prefix": issued.record.key_prefix,
                "tool_allowlist_count": len(issued.record.tool_allowlist),
                "capability_allowlist_count": len(
                    issued.record.capability_allowlist
                ),
                "daily_collect_quota": issued.record.daily_collect_quota,
            },
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise APIError(
            400, "invalid_request", details={"reason": str(exc)}
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise APIError(409, "project_api_key_active_exists") from exc
    except Exception:
        await session.rollback()
        raise
    await session.refresh(issued.record)
    return IssuedProjectApiKeyResponse(
        **_response(issued.record).model_dump(),
        plaintext=issued.plaintext,
    )


@router.get(
    "/{project_id}/keys",
    response_model=list[ProjectApiKeyResponse],
)
@router.get(
    "/{project_id}/api-keys",
    response_model=list[ProjectApiKeyResponse],
    include_in_schema=False,
)
async def list_project_api_keys(
    project_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> list[ProjectApiKeyResponse]:
    await _project_or_404(session, context, project_id)
    rows = await list_keys(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
    )
    return [_response(row) for row in rows]


@router.post(
    "/{project_id}/keys/{key_id}/rotate",
    response_model=IssuedProjectApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rotate_project_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    payload: RotateProjectApiKeyRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> IssuedProjectApiKeyResponse:
    await _project_or_404(session, context, project_id)
    try:
        result = await rotate_key(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            key_id=key_id,
            label=payload.label,
            created_by_user_id=context.user.id,
            tool_allowlist=payload.tool_allowlist,
            capability_allowlist=payload.capability_allowlist,
            daily_collect_quota=payload.daily_collect_quota,
            expires_at=payload.expires_at,
        )
        await append_audit_event(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            actor_user_id=context.user.id,
            action="project_api_key.rotated",
            resource_type="project_api_key",
            resource_id=str(result.issued.record.id),
            request_id=request_id,
            details={
                "revoked_key_id": str(result.revoked_key_id),
                "new_key_prefix": result.issued.record.key_prefix,
                "capability_allowlist_count": len(
                    result.issued.record.capability_allowlist
                ),
            },
        )
        await session.commit()
    except ProjectApiKeyNotFoundError as exc:
        await session.rollback()
        raise APIError(404, "project_api_key_not_found") from exc
    except ProjectApiKeyStateError as exc:
        await session.rollback()
        raise APIError(409, "state_conflict") from exc
    except ValueError as exc:
        await session.rollback()
        raise APIError(
            400, "invalid_request", details={"reason": str(exc)}
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise APIError(409, "state_conflict") from exc
    except Exception:
        await session.rollback()
        raise
    await session.refresh(result.issued.record)
    return IssuedProjectApiKeyResponse(
        **_response(result.issued.record).model_dump(),
        plaintext=result.issued.plaintext,
    )


@router.delete(
    "/{project_id}/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def revoke_project_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> None:
    await _project_or_404(session, context, project_id)
    try:
        result = await revoke_key_with_state(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            key_id=key_id,
        )
        if result is None:
            raise APIError(404, "project_api_key_not_found")
        if result.changed:
            await append_audit_event(
                session,
                workspace_id=context.workspace.id,
                project_id=project_id,
                actor_user_id=context.user.id,
                action="project_api_key.revoked",
                resource_type="project_api_key",
                resource_id=str(result.record.id),
                request_id=request_id,
                details={"key_prefix": result.record.key_prefix},
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
```

- [ ] **Step 4: 运行路由测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_api_key_routes.py -v
```

Expected: 全部 passed。规范路径出现在 OpenAPI；旧路径不出现；轮换写两条审计。

- [ ] **Step 5: 运行 C2 的 ACL 测试确认未回归**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_project_acl.py tests/unit/test_project_api_key_routes.py -v
```

Expected: 全部 passed。member 仍得到 403 `project_key_management_forbidden`；admin 可以管理。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py \
  apps/api/tests/unit/test_project_api_key_routes.py
git commit -m "feat(keys): expose canonical key routes and audit rotation"
```

---

### Task 6: 凭据仓储的项目优先解析

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/repositories/platform_credentials.py`
- Modify: `apps/api/src/data_intelligence_hub/services/platform_credentials.py`
- Test: `apps/api/tests/unit/test_platform_credentials.py`

**Interfaces:**
- Consumes: `platform_credential_bundles.project_id` 与两个部分唯一索引。
- Produces: `list_platform_credential_bundles(session, workspace_id, project_id=None) -> list[PlatformCredentialBundle]`。
- Produces: `get_platform_credential_bundle(session, workspace_id, provider_id, project_id=None) -> PlatformCredentialBundle | None`，`None` 表示精确工作区级。
- Produces: `resolve_platform_credential_bundle(session, workspace_id, provider_id, project_id=None) -> tuple[PlatformCredentialBundle | None, str]`，第二项是 `project`、`workspace` 或 `none`。
- Produces: `get_platform_credential_values(..., project_id=None)`。

- [ ] **Step 0: 编辑前运行 GitNexus impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs impact "get_platform_credential_values" --direction upstream --repo .
node .gitnexus/run.cjs impact "resolve_platform_credential_bundle" --direction upstream --repo .
```

Expected: 记录调用方与风险；HIGH/CRITICAL 先报告；`UNKNOWN` 用文本搜索复核。

- [ ] **Step 1: 写失败的解析测试**

Append to `apps/api/tests/unit/test_platform_credentials.py`:

```python
@pytest.mark.anyio
async def test_project_scope_wins_and_workspace_scope_falls_back() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from data_intelligence_hub.models.base import Base
    from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace
    from data_intelligence_hub.services.platform_credentials import (
        PlatformCredentialCipher,
        get_platform_credential_values,
    )

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cipher = PlatformCredentialCipher.from_secret(
        SecretStr(Fernet.generate_key().decode())
    )
    async with factory() as session:
        owner = User(
            email=f"scope-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        session.add(owner)
        await session.flush()
        workspace = Workspace(
            name="W", slug=f"w-{uuid.uuid4().hex}", owner_id=owner.id
        )
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="P",
            domain="mixed",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                PlatformCredentialBundle(
                    workspace_id=workspace.id,
                    project_id=None,
                    provider_id="youtube",
                    encrypted_payload=cipher.encrypt({"api_key": "workspace-secret"}),
                    configured_fields=["api_key"],
                    key_version=cipher.key_version,
                    created_by_user_id=owner.id,
                    updated_by_user_id=owner.id,
                ),
                PlatformCredentialBundle(
                    workspace_id=workspace.id,
                    project_id=project.id,
                    provider_id="youtube",
                    encrypted_payload=cipher.encrypt({"api_key": "project-secret"}),
                    configured_fields=["api_key"],
                    key_version=cipher.key_version,
                    created_by_user_id=owner.id,
                    updated_by_user_id=owner.id,
                ),
            ]
        )
        await session.commit()
        workspace_id = workspace.id
        project_id = project.id

    async with factory() as session:
        values = await get_platform_credential_values(
            session,
            workspace_id=workspace_id,
            provider_id="youtube",
            project_id=project_id,
            cipher=cipher,
        )
        assert values["api_key"] == "project-secret"
        await session.delete(
            (
                await session.execute(
                    select(PlatformCredentialBundle).where(
                        PlatformCredentialBundle.project_id == project_id
                    )
                )
            ).scalar_one()
        )
        await session.commit()

    async with factory() as session:
        values = await get_platform_credential_values(
            session,
            workspace_id=workspace_id,
            provider_id="youtube",
            project_id=project_id,
            cipher=cipher,
        )
        assert values["api_key"] == "workspace-secret"
    await engine.dispose()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -k "project_scope_wins" -v
```

Expected: FAIL。`get_platform_credential_values` 不接受 `project_id`。

- [ ] **Step 3: 修改仓储**

Replace `apps/api/src/data_intelligence_hub/repositories/platform_credentials.py` with:

```python
"""``platform_credential_bundles`` 的读写。

项目级行 ``project_id`` 非空，工作区级行为空。
写路径必须使用精确作用域；读路径使用项目优先、工作区回退。
"""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle


async def list_platform_credential_bundles(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[PlatformCredentialBundle]:
    statement = select(PlatformCredentialBundle).where(
        PlatformCredentialBundle.workspace_id == workspace_id
    )
    if project_id is None:
        statement = statement.where(PlatformCredentialBundle.project_id.is_(None))
    else:
        statement = statement.where(
            or_(
                PlatformCredentialBundle.project_id.is_(None),
                PlatformCredentialBundle.project_id == project_id,
            )
        )
    statement = statement.order_by(PlatformCredentialBundle.provider_id.asc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_platform_credential_bundle(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider_id: str,
    project_id: uuid.UUID | None = None,
) -> PlatformCredentialBundle | None:
    scope = (
        PlatformCredentialBundle.project_id.is_(None)
        if project_id is None
        else PlatformCredentialBundle.project_id == project_id
    )
    result = await session.execute(
        select(PlatformCredentialBundle).where(
            PlatformCredentialBundle.workspace_id == workspace_id,
            PlatformCredentialBundle.provider_id == provider_id,
            scope,
        )
    )
    return result.scalar_one_or_none()


async def resolve_platform_credential_bundle(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider_id: str,
    project_id: uuid.UUID | None = None,
) -> tuple[PlatformCredentialBundle | None, str]:
    if project_id is not None:
        project_bundle = await get_platform_credential_bundle(
            session,
            workspace_id,
            provider_id,
            project_id=project_id,
        )
        if project_bundle is not None:
            return project_bundle, "project"
    workspace_bundle = await get_platform_credential_bundle(
        session,
        workspace_id,
        provider_id,
        project_id=None,
    )
    if workspace_bundle is not None:
        return workspace_bundle, "workspace"
    return None, "none"


async def get_platform_credential_bundle_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    bundle_id: uuid.UUID,
) -> PlatformCredentialBundle | None:
    result = await session.execute(
        select(PlatformCredentialBundle).where(
            PlatformCredentialBundle.workspace_id == workspace_id,
            PlatformCredentialBundle.id == bundle_id,
        )
    )
    return result.scalar_one_or_none()


__all__ = [
    "get_platform_credential_bundle",
    "get_platform_credential_bundle_by_id",
    "list_platform_credential_bundles",
    "resolve_platform_credential_bundle",
]
```

- [ ] **Step 4: 修改 `get_platform_credential_values`**

In `apps/api/src/data_intelligence_hub/services/platform_credentials.py`, add `import structlog` and:

```python
logger = structlog.get_logger(__name__)


async def get_platform_credential_values(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    provider_id: str,
    cipher: PlatformCredentialCipher,
    project_id: uuid.UUID | None = None,
) -> dict[str, str]:
    bundle, scope = await resolve_platform_credential_bundle(
        session,
        workspace_id,
        provider_id,
        project_id=project_id,
    )
    if bundle is None:
        return {}
    if project_id is not None and scope == "workspace":
        logger.info(
            "platform_credential_workspace_fallback",
            workspace_id=str(workspace_id),
            project_id=str(project_id),
            provider_id=provider_id,
        )
    return cipher.decrypt(bundle.encrypted_payload)
```

Update imports from the repository to include `resolve_platform_credential_bundle`.

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -v
```

Expected: 全部 passed。项目级密文优先；删除项目级行后回退工作区级。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/platform_credentials.py \
  apps/api/src/data_intelligence_hub/services/platform_credentials.py \
  apps/api/tests/unit/test_platform_credentials.py
git commit -m "feat(credentials): resolve project scope before workspace scope"
```

---

### Task 7: 凭据设置列表与作用域投影

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/platform_credentials.py`
- Modify: `apps/api/src/data_intelligence_hub/services/platform_credentials.py`
- Test: `apps/api/tests/unit/test_platform_credentials.py`

**Interfaces:**
- Consumes: `list_platform_credential_bundles`、`get_project`。
- Produces: `CreatorCookieMetadata(captured_at, expires_at, last_verified_at, account_label)`。
- Produces: `PlatformCredentialSettings.scope: Literal["project","workspace","none"]`、`project_id`、`creator_cookie_metadata`。
- Produces: `PlatformCredentialSettingsResponse.project_id`。
- Produces: `list_platform_credentials(session, *, workspace, catalog, vault_write_enabled, project_id=None) -> PlatformCredentialSettingsResponse`。

- [ ] **Step 1: 写失败的列表投影测试**

Append to `apps/api/tests/unit/test_platform_credentials.py`:

```python
@pytest.mark.anyio
async def test_settings_projection_marks_project_scope_and_cookie_metadata() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from data_intelligence_hub.models.base import Base
    from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace
    from data_intelligence_hub.services.platform_credentials import (
        list_platform_credentials,
    )

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = User(
            email=f"projection-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        session.add(owner)
        await session.flush()
        workspace = Workspace(
            name="W", slug=f"w-{uuid.uuid4().hex}", owner_id=owner.id
        )
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="P",
            domain="mixed",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()
        session.add(
            PlatformCredentialBundle(
                workspace_id=workspace.id,
                project_id=project.id,
                provider_id="tiktok_research",
                encrypted_payload="ciphertext",
                configured_fields=["creator_cookie"],
                creator_cookie_metadata={
                    "captured_at": "2026-10-20T10:00:00Z",
                    "expires_at": "2026-12-31T00:00:00Z",
                    "last_verified_at": None,
                    "account_label": "brand-account",
                },
                key_version="fernet.v1",
                created_by_user_id=owner.id,
                updated_by_user_id=owner.id,
            )
        )
        await session.commit()
        project_id = project.id

    async with factory() as session:
        response = await list_platform_credentials(
            session,
            workspace=workspace,
            catalog=get_social_provider_catalog(),
            vault_write_enabled=True,
            project_id=project_id,
        )
    tiktok = next(
        item for item in response.platforms if item.provider_id == "tiktok_research"
    )
    assert tiktok.scope == "project"
    assert tiktok.project_id == project_id
    assert tiktok.configured is True
    assert tiktok.creator_cookie_metadata is not None
    assert tiktok.creator_cookie_metadata.account_label == "brand-account"
    await engine.dispose()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -k "settings_projection_marks" -v
```

Expected: FAIL。`PlatformCredentialSettings` 没有 `scope`；`list_platform_credentials` 不接受 `project_id`。

- [ ] **Step 3: 修改 schema**

Replace `apps/api/src/data_intelligence_hub/schemas/platform_credentials.py` with:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

CredentialScope = Literal["project", "workspace", "none"]


class CreatorCookieMetadata(BaseModel):
    captured_at: datetime | None = None
    expires_at: datetime | None = None
    last_verified_at: datetime | None = None
    account_label: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_times(self) -> "CreatorCookieMetadata":
        for value in (
            self.captured_at,
            self.expires_at,
            self.last_verified_at,
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError("creator_cookie_metadata_timezone_required")
        if (
            self.captured_at is not None
            and self.expires_at is not None
            and self.expires_at <= self.captured_at
        ):
            raise ValueError("creator_cookie_metadata_expiry_invalid")
        return self


class PlatformCredentialUpdateRequest(BaseModel):
    values: dict[str, SecretStr] = Field(default_factory=dict, max_length=12)
    creator_cookie_metadata: CreatorCookieMetadata | None = None

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: dict[str, SecretStr]) -> dict[str, SecretStr]:
        for key, value in values.items():
            if not key or len(key) > 80 or not key.replace("_", "").isalnum():
                raise ValueError("platform_credential_field_invalid")
            secret = value.get_secret_value()
            if not secret or secret.isspace() or len(secret) > 8192:
                raise ValueError("platform_credential_value_invalid")
        return values

    @model_validator(mode="after")
    def require_one_change(self) -> "PlatformCredentialUpdateRequest":
        if not self.values and self.creator_cookie_metadata is None:
            raise ValueError("platform_credential_update_empty")
        return self


class PlatformCredentialFieldStatus(BaseModel):
    key: str
    label: str
    configured: bool


class PlatformCredentialSettings(BaseModel):
    platform: str
    provider_id: str
    label: str
    auth_mode: str
    fields: list[PlatformCredentialFieldStatus]
    configured: bool
    configured_field_count: int
    scope: CredentialScope
    project_id: uuid.UUID | None = None
    creator_cookie_metadata: CreatorCookieMetadata | None = None
    updated_at: datetime | None = None
    live_execution_enabled: Literal[False] = False


class PlatformCredentialSettingsResponse(BaseModel):
    schema_version: Literal["platform_credential_settings.v1"] = (
        "platform_credential_settings.v1"
    )
    vault_write_enabled: bool
    provider_call_allowed: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    project_id: uuid.UUID | None = None
    platforms: list[PlatformCredentialSettings]
```

- [ ] **Step 4: 修改设置投影**

In `apps/api/src/data_intelligence_hub/services/platform_credentials.py`, replace `build_platform_credential_settings` and `list_platform_credentials`:

```python
from collections import defaultdict

from data_intelligence_hub.repositories.projects import get_project


class PlatformCredentialProjectNotFoundError(PlatformCredentialError):
    code = "project_not_found"


def _creator_cookie_metadata(
    bundle: PlatformCredentialBundle | None,
    provider: SocialProviderCatalogItem,
) -> CreatorCookieMetadata | None:
    if bundle is None or "creator_cookie" not in provider.required_credentials:
        return None
    raw = bundle.creator_cookie_metadata
    if not raw:
        return None
    return CreatorCookieMetadata.model_validate(raw)


def build_platform_credential_settings(
    *,
    catalog: SocialProviderCatalogResponse,
    bundles: list[PlatformCredentialBundle],
    vault_write_enabled: bool,
    project_id: uuid.UUID | None = None,
) -> PlatformCredentialSettingsResponse:
    by_provider: dict[str, list[PlatformCredentialBundle]] = defaultdict(list)
    for bundle in bundles:
        by_provider[bundle.provider_id].append(bundle)

    platforms: list[PlatformCredentialSettings] = []
    for provider in sorted(catalog.providers, key=lambda item: item.platform):
        candidates = by_provider.get(provider.provider_id, [])
        project_bundle = (
            next(
                (
                    bundle
                    for bundle in candidates
                    if bundle.project_id == project_id
                ),
                None,
            )
            if project_id is not None
            else None
        )
        workspace_bundle = next(
            (bundle for bundle in candidates if bundle.project_id is None),
            None,
        )
        effective = project_bundle or workspace_bundle
        if project_bundle is not None:
            scope: CredentialScope = "project"
        elif workspace_bundle is not None:
            scope = "workspace"
        else:
            scope = "none"
        configured_fields = set(effective.configured_fields if effective else [])
        fields = [
            PlatformCredentialFieldStatus(
                key=key,
                label=_field_label(key),
                configured=key in configured_fields,
            )
            for key in provider.required_credentials
        ]
        platforms.append(
            PlatformCredentialSettings(
                platform=provider.platform,
                provider_id=provider.provider_id,
                label=PLATFORM_LABELS.get(provider.platform, provider.platform.title()),
                auth_mode=provider.auth_mode,
                fields=fields,
                configured=bool(fields) and all(field.configured for field in fields),
                configured_field_count=sum(field.configured for field in fields),
                scope=scope,
                project_id=effective.project_id if scope == "project" else None,
                creator_cookie_metadata=_creator_cookie_metadata(effective, provider),
                updated_at=effective.updated_at if effective else None,
            )
        )
    return PlatformCredentialSettingsResponse(
        vault_write_enabled=vault_write_enabled,
        project_id=project_id,
        platforms=platforms,
    )


async def _assert_project_in_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise PlatformCredentialProjectNotFoundError("project_not_found")


async def list_platform_credentials(
    session: AsyncSession,
    *,
    workspace: Workspace,
    catalog: SocialProviderCatalogResponse,
    vault_write_enabled: bool,
    project_id: uuid.UUID | None = None,
) -> PlatformCredentialSettingsResponse:
    if project_id is not None:
        await _assert_project_in_workspace(session, workspace.id, project_id)
    bundles = await list_platform_credential_bundles(
        session,
        workspace.id,
        project_id=project_id,
    )
    return build_platform_credential_settings(
        catalog=catalog,
        bundles=bundles,
        vault_write_enabled=vault_write_enabled,
        project_id=project_id,
    )
```

Update schema imports to include `CreatorCookieMetadata`, `CredentialScope`.

- [ ] **Step 5: 更新旧测试调用**

In `apps/api/tests/unit/test_platform_credentials.py`, remove `user=` from every `list_platform_credentials(...)` call. Replace `test_non_owner_is_rejected_before_vault_status_query` with:

```python
async def test_list_does_not_read_secrets_and_reports_scope() -> None:
    user = User(
        id=uuid.uuid4(),
        email="member@example.com",
        password_hash="hash",
        name="Member",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Vault",
        slug="vault-scope",
        owner_id=user.id,
    )
    session = AsyncMock()
    session.execute.return_value.scalars.return_value.all.return_value = []

    response = await list_platform_credentials(
        session,
        workspace=workspace,
        catalog=get_social_provider_catalog(),
        vault_write_enabled=True,
    )

    assert response.credential_read_attempted is False
    assert all(item.scope == "none" for item in response.platforms)
```

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -v
```

Expected: 全部 passed。项目级行显示 `scope=project`；无行显示 `scope=none`；响应不含密文。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/schemas/platform_credentials.py \
  apps/api/src/data_intelligence_hub/services/platform_credentials.py \
  apps/api/tests/unit/test_platform_credentials.py
git commit -m "feat(credentials): project scope projection and cookie metadata schema"
```

---

### Task 8: 项目级写入、回退与 creator cookie 元数据

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/platform_credentials.py`
- Test: `apps/api/tests/unit/test_platform_credentials.py`

**Interfaces:**
- Consumes: `CreatorCookieMetadata`、`get_platform_credential_bundle`、`list_platform_credential_bundles`。
- Produces: `update_platform_credentials(..., project_id=None) -> PlatformCredentialSettings`。
- Produces: `remove_platform_credentials(..., project_id=None) -> PlatformCredentialSettings`。
- Produces: 事务只 `flush`，提交权在路由。

- [ ] **Step 1: 写失败的写入测试**

Append to `apps/api/tests/unit/test_platform_credentials.py`:

```python
@pytest.mark.anyio
async def test_project_scope_update_stores_cookie_metadata_without_plaintext() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from data_intelligence_hub.models.base import Base
    from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace
    from data_intelligence_hub.schemas.platform_credentials import (
        CreatorCookieMetadata,
        PlatformCredentialUpdateRequest,
    )
    from data_intelligence_hub.services.platform_credentials import (
        PlatformCredentialCipher,
        update_platform_credentials,
    )

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cipher = PlatformCredentialCipher.from_secret(
        SecretStr(Fernet.generate_key().decode())
    )
    async with factory() as session:
        owner = User(
            email=f"cookie-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        session.add(owner)
        await session.flush()
        workspace = Workspace(
            name="W", slug=f"w-{uuid.uuid4().hex}", owner_id=owner.id
        )
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="P",
            domain="mixed",
            owner_id=owner.id,
        )
        session.add(project)
        await session.commit()
        workspace_id = workspace.id
        project_id = project.id
        owner_id = owner.id

    async with factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        user = await session.get(User, owner_id)
        assert workspace is not None and user is not None
        item = await update_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            project_id=project_id,
            platform="tiktok",
            payload=PlatformCredentialUpdateRequest(
                values={"creator_cookie": SecretStr("cookie-secret-value")},
                creator_cookie_metadata=CreatorCookieMetadata(
                    captured_at="2026-10-20T10:00:00Z",
                    expires_at="2026-12-31T00:00:00Z",
                    account_label="brand-account",
                ),
            ),
            catalog=get_social_provider_catalog(),
            cipher=cipher,
        )
        await session.commit()
        assert item.scope == "project"
        assert item.creator_cookie_metadata is not None
        assert item.creator_cookie_metadata.account_label == "brand-account"
        assert "cookie-secret-value" not in repr(item)
        stored = (
            await session.execute(
                select(PlatformCredentialBundle).where(
                    PlatformCredentialBundle.project_id == project_id
                )
            )
        ).scalar_one()
        assert "cookie-secret-value" not in stored.encrypted_payload
        assert stored.creator_cookie_metadata["captured_at"].startswith(
            "2026-10-20T10:00:00"
        )

    async with factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        user = await session.get(User, owner_id)
        assert workspace is not None and user is not None
        removed = await remove_platform_credentials(
            session,
            workspace=workspace,
            project_id=project_id,
            platform="tiktok",
            catalog=get_social_provider_catalog(),
            vault_write_enabled=True,
        )
        await session.commit()
        assert removed.scope == "none"
    await engine.dispose()


@pytest.mark.anyio
async def test_cookie_metadata_is_rejected_for_non_cookie_provider() -> None:
    from data_intelligence_hub.schemas.platform_credentials import (
        CreatorCookieMetadata,
        PlatformCredentialUpdateRequest,
    )
    from data_intelligence_hub.services.platform_credentials import (
        PlatformCredentialFieldInvalidError,
        update_platform_credentials,
    )

    session = AsyncMock()
    workspace = Workspace(
        id=uuid.uuid4(), name="W", slug="c3-cookie", owner_id=uuid.uuid4()
    )
    user = User(
        id=workspace.owner_id,
        email="owner@example.com",
        password_hash="x",
        name="Owner",
    )
    cipher = PlatformCredentialCipher.from_secret(
        SecretStr(Fernet.generate_key().decode())
    )
    with pytest.raises(PlatformCredentialFieldInvalidError):
        await update_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            platform="youtube",
            payload=PlatformCredentialUpdateRequest(
                creator_cookie_metadata=CreatorCookieMetadata(
                    captured_at="2026-10-20T10:00:00Z"
                )
            ),
            catalog=get_social_provider_catalog(),
            cipher=cipher,
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -k "cookie_metadata or project_scope_update" -v
```

Expected: FAIL。`update_platform_credentials` 不接受 `project_id`；元数据未存储。

- [ ] **Step 3: 重写 `update_platform_credentials`**

Replace the function in `apps/api/src/data_intelligence_hub/services/platform_credentials.py`:

```python
async def update_platform_credentials(
    session: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    platform: str,
    payload: PlatformCredentialUpdateRequest,
    catalog: SocialProviderCatalogResponse,
    cipher: PlatformCredentialCipher,
    project_id: uuid.UUID | None = None,
) -> PlatformCredentialSettings:
    if project_id is not None:
        await _assert_project_in_workspace(session, workspace.id, project_id)
    provider = _provider_for_platform(catalog, platform)
    allowed_fields = set(provider.required_credentials)
    requested_fields = set(payload.values)
    if not requested_fields.issubset(allowed_fields):
        raise PlatformCredentialFieldInvalidError("platform_credential_field_invalid")

    supports_cookie = "creator_cookie" in provider.required_credentials
    if payload.creator_cookie_metadata is not None and not supports_cookie:
        raise PlatformCredentialFieldInvalidError(
            "creator_cookie_metadata_not_supported"
        )

    bundle = await get_platform_credential_bundle(
        session,
        workspace.id,
        provider.provider_id,
        project_id=project_id,
    )
    existing_values = cipher.decrypt(bundle.encrypted_payload) if bundle else {}
    merged_values = {
        **existing_values,
        **{key: value.get_secret_value() for key, value in payload.values.items()},
    }
    encrypted_payload = cipher.encrypt(merged_values)
    configured_fields = sorted(merged_values)

    if supports_cookie:
        if payload.creator_cookie_metadata is not None:
            metadata = payload.creator_cookie_metadata.model_dump(
                mode="json", exclude_none=True
            )
        elif bundle is not None:
            metadata = bundle.creator_cookie_metadata
        else:
            metadata = None
    else:
        metadata = None

    if bundle is None:
        bundle = PlatformCredentialBundle(
            workspace_id=workspace.id,
            project_id=project_id,
            provider_id=provider.provider_id,
            encrypted_payload=encrypted_payload,
            configured_fields=configured_fields,
            creator_cookie_metadata=metadata,
            key_version=cipher.key_version,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
        )
        session.add(bundle)
    else:
        bundle.encrypted_payload = encrypted_payload
        bundle.configured_fields = configured_fields
        bundle.creator_cookie_metadata = metadata
        bundle.key_version = cipher.key_version
        bundle.updated_by_user_id = user.id
    await session.flush()
    await session.refresh(bundle)

    response = build_platform_credential_settings(
        catalog=catalog,
        bundles=[bundle],
        vault_write_enabled=True,
        project_id=project_id,
    )
    return next(
        item for item in response.platforms if item.platform == provider.platform
    )
```

- [ ] **Step 4: 重写 `remove_platform_credentials`**

Replace the function:

```python
async def remove_platform_credentials(
    session: AsyncSession,
    *,
    workspace: Workspace,
    platform: str,
    catalog: SocialProviderCatalogResponse,
    vault_write_enabled: bool,
    project_id: uuid.UUID | None = None,
) -> PlatformCredentialSettings:
    if project_id is not None:
        await _assert_project_in_workspace(session, workspace.id, project_id)
    provider = _provider_for_platform(catalog, platform)
    bundle = await get_platform_credential_bundle(
        session,
        workspace.id,
        provider.provider_id,
        project_id=project_id,
    )
    if bundle is not None:
        await session.delete(bundle)
        await session.flush()

    remaining = await list_platform_credential_bundles(
        session,
        workspace.id,
        project_id=project_id,
    )
    response = build_platform_credential_settings(
        catalog=catalog,
        bundles=remaining,
        vault_write_enabled=vault_write_enabled,
        project_id=project_id,
    )
    return next(
        item for item in response.platforms if item.platform == provider.platform
    )
```

- [ ] **Step 5: 更新旧测试的 remove 调用**

In `apps/api/tests/unit/test_platform_credentials.py`, remove `user=` from every `remove_platform_credentials(...)` call. The function no longer performs authorization; the route owns RBAC.

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -v
```

Expected: 全部 passed。项目级删除后回退工作区级；元数据只存允许的四个键；非 TikTok provider 拒绝元数据。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/platform_credentials.py \
  apps/api/tests/unit/test_platform_credentials.py
git commit -m "feat(credentials): write project scope and creator cookie metadata"
```

---

### Task 9: 凭据路由的 C2 RBAC、审计与错误码

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py`
- Test: `apps/api/tests/integration/test_platform_credential_routes.py`

**Interfaces:**
- Consumes: C2 `require_workspace_role`、`require_project_access`、`RequestIdDep`、`APIError`、`append_audit_event`。
- Produces: `GET/PUT/DELETE /api/settings/platform-credentials[/{platform}]` 接受可选 `project_id`。
- Produces: 错误码 `project_not_found`、`connector_not_found`、`credential_invalid`、`vault_write_disabled`。

- [ ] **Step 1: 写失败的路由测试**

Append to `apps/api/tests/integration/test_platform_credential_routes.py`:

```python
@pytest.mark.asyncio
async def test_project_scope_round_trip_and_audit_without_secret(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_owner(client)
    settings = Settings(platform_credential_master_key=Fernet.generate_key().decode())
    monkeypatch.setattr(credential_routes, "get_settings", lambda: settings)

    project_response = await client.post(
        "/api/projects",
        json={"name": "C3 Connectors", "domain": "mixed"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    secret = "project-scope-secret-never-echoed"
    saved = await client.put(
        f"/api/settings/platform-credentials/tiktok?project_id={project_id}",
        json={
            "values": {"creator_cookie": secret},
            "creator_cookie_metadata": {
                "captured_at": "2026-10-20T10:00:00Z",
                "expires_at": "2026-12-31T00:00:00Z",
                "account_label": "brand-account",
            },
        },
    )
    assert saved.status_code == 200
    assert saved.json()["scope"] == "project"
    assert saved.json()["project_id"] == project_id
    assert secret not in saved.text

    listed = await client.get(
        f"/api/settings/platform-credentials?project_id={project_id}"
    )
    assert listed.status_code == 200
    tiktok = next(
        item for item in listed.json()["platforms"] if item["platform"] == "tiktok"
    )
    assert tiktok["scope"] == "project"
    assert tiktok["creator_cookie_metadata"]["account_label"] == "brand-account"
    assert secret not in listed.text

    audit = await client.get("/api/audit-events")
    assert audit.status_code == 200
    assert any(
        event["action"] == "platform_credential.updated"
        for event in audit.json()
    )
    assert secret not in audit.text


@pytest.mark.asyncio
async def test_project_scope_of_other_workspace_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_owner(client)
    settings = Settings(platform_credential_master_key=Fernet.generate_key().decode())
    monkeypatch.setattr(credential_routes, "get_settings", lambda: settings)

    response = await client.get(
        f"/api/settings/platform-credentials?project_id={uuid.uuid4()}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "project_not_found"
```

Add `import uuid` to the test imports if missing.

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/integration/test_platform_credential_routes.py -k "project_scope" -v
```

Expected: FAIL。路由不接受 `project_id`；审计未写；跨工作区未返回 404。

- [ ] **Step 3: 重写路由文件**

Replace `apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py` with:

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from data_intelligence_hub.api.authz import (
    require_project_access,
    require_workspace_role,
)
from data_intelligence_hub.api.deps import (
    AuthenticatedContextDep,
    RequestIdDep,
    SessionDep,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.schemas.platform_credentials import (
    PlatformCredentialSettings,
    PlatformCredentialSettingsResponse,
    PlatformCredentialUpdateRequest,
)
from data_intelligence_hub.schemas.social_provider import SocialProviderCatalogResponse
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.platform_credentials import (
    PlatformCredentialCipher,
    PlatformCredentialError,
    PlatformCredentialFieldInvalidError,
    PlatformCredentialPlatformNotFoundError,
    PlatformCredentialProjectNotFoundError,
    PlatformCredentialVaultUnavailableError,
    list_platform_credentials,
    remove_platform_credentials,
    update_platform_credentials,
)
from data_intelligence_hub.services.social_provider import get_social_provider_catalog

router = APIRouter(tags=["settings"])


def _vault_write_enabled() -> bool:
    return get_settings().platform_credential_master_key is not None


def _credential_error(exc: PlatformCredentialError) -> APIError:
    if isinstance(exc, PlatformCredentialProjectNotFoundError):
        return APIError(404, "project_not_found")
    if isinstance(exc, PlatformCredentialPlatformNotFoundError):
        return APIError(404, "connector_not_found")
    if isinstance(exc, PlatformCredentialVaultUnavailableError):
        return APIError(503, "vault_write_disabled")
    if isinstance(exc, PlatformCredentialFieldInvalidError):
        return APIError(422, "credential_invalid")
    return APIError(422, "credential_invalid")


async def _catalog(session: SessionDep) -> SocialProviderCatalogResponse:
    try:
        current = await resolve_current_capability_catalog(session)
        return get_social_provider_catalog(catalog=current)
    except CapabilityCatalogResolutionError as exc:
        raise APIError(500, "internal_error", details={"reason": exc.code}) from exc


@router.get("", response_model=PlatformCredentialSettingsResponse)
async def list_platform_credential_items(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PlatformCredentialSettingsResponse:
    if project_id is not None:
        await require_project_access(
            session,
            workspace=context.workspace,
            user=context.user,
            project_id=project_id,
            manage=False,
        )
    try:
        return await list_platform_credentials(
            session,
            workspace=context.workspace,
            catalog=await _catalog(session),
            vault_write_enabled=_vault_write_enabled(),
            project_id=project_id,
        )
    except PlatformCredentialError as exc:
        raise _credential_error(exc) from exc


@router.put(
    "/{platform}",
    response_model=PlatformCredentialSettings,
)
async def update_platform_credential_item(
    platform: str,
    payload: PlatformCredentialUpdateRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PlatformCredentialSettings:
    if project_id is not None:
        await require_project_access(
            session,
            workspace=context.workspace,
            user=context.user,
            project_id=project_id,
            manage=True,
        )
    else:
        await require_workspace_role(
            session,
            workspace=context.workspace,
            user=context.user,
            allowed=("owner", "admin"),
        )
    master_key = get_settings().platform_credential_master_key
    if master_key is None:
        raise APIError(503, "vault_write_disabled")
    try:
        item = await update_platform_credentials(
            session,
            user=context.user,
            workspace=context.workspace,
            project_id=project_id,
            platform=platform,
            payload=payload,
            catalog=await _catalog(session),
            cipher=PlatformCredentialCipher.from_secret(master_key),
        )
        await append_audit_event(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            actor_user_id=context.user.id,
            action="platform_credential.updated",
            resource_type="platform_credential",
            resource_id=(
                f"{platform}:{project_id}" if project_id else f"{platform}:workspace"
            ),
            request_id=request_id,
            details={
                "platform": platform,
                "project_id": str(project_id) if project_id else None,
                "scope": item.scope,
                "field_names": sorted(payload.values),
                "metadata_changed": payload.creator_cookie_metadata is not None,
            },
        )
        await session.commit()
    except PlatformCredentialError as exc:
        await session.rollback()
        raise _credential_error(exc) from exc
    except Exception:
        await session.rollback()
        raise
    return item


@router.delete(
    "/{platform}",
    response_model=PlatformCredentialSettings,
)
async def delete_platform_credential_item(
    platform: str,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PlatformCredentialSettings:
    if project_id is not None:
        await require_project_access(
            session,
            workspace=context.workspace,
            user=context.user,
            project_id=project_id,
            manage=True,
        )
    else:
        await require_workspace_role(
            session,
            workspace=context.workspace,
            user=context.user,
            allowed=("owner", "admin"),
        )
    try:
        item = await remove_platform_credentials(
            session,
            workspace=context.workspace,
            project_id=project_id,
            platform=platform,
            catalog=await _catalog(session),
            vault_write_enabled=_vault_write_enabled(),
        )
        await append_audit_event(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            actor_user_id=context.user.id,
            action="platform_credential.removed",
            resource_type="platform_credential",
            resource_id=(
                f"{platform}:{project_id}" if project_id else f"{platform}:workspace"
            ),
            request_id=request_id,
            details={
                "platform": platform,
                "project_id": str(project_id) if project_id else None,
                "scope": item.scope,
            },
        )
        await session.commit()
    except PlatformCredentialError as exc:
        await session.rollback()
        raise _credential_error(exc) from exc
    except Exception:
        await session.rollback()
        raise
    return item
```

- [ ] **Step 4: 运行集成测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/integration/test_platform_credential_routes.py -v
```

Expected: 全部 passed。项目级 PUT 返回 `scope=project`；审计含动作且不含明文；未知项目返回 404 `project_not_found`。

- [ ] **Step 5: 运行 OpenAPI 无密文测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_platform_credentials.py -k "openapi" -v
```

Expected: passed。OpenAPI 与响应模型不含 `encrypted_payload` 或明文。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py \
  apps/api/tests/integration/test_platform_credential_routes.py
git commit -m "feat(credentials): expose project scope routes with audit"
```

---

### Task 10: TikTok creator cookie 按项目解析

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/tiktok_tools.py`
- Test: `apps/api/tests/unit/test_tiktok_creator_cookie_scope.py`

**Interfaces:**
- Consumes: `get_platform_credential_values(..., project_id=...)`。
- Produces: `resolve_creator_cookie(session, *, project_id: uuid.UUID, cipher: PlatformCredentialCipher) -> str | None`。
- Produces: `_resolve_creator_cookie` 继续优先读 `TIKHUB_TIKTOK_CREATOR_COOKIE` 环境变量。

- [ ] **Step 0: 编辑前运行 GitNexus impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs impact "get_platform_credential_values" --direction upstream --repo .
node .gitnexus/run.cjs impact "build_platform_credential_settings" --direction upstream --repo .
```

Expected: 记录调用方与风险；HIGH/CRITICAL 先报告；`UNKNOWN` 用文本搜索复核。

- [ ] **Step 1: 写失败的作用域测试**

Create `apps/api/tests/unit/test_tiktok_creator_cookie_scope.py`:

```python
from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.platform_credentials import PlatformCredentialCipher
from data_intelligence_hub.services.tiktok_tools import resolve_creator_cookie


@pytest.mark.anyio
async def test_creator_cookie_uses_project_scope_then_workspace_fallback() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    cipher = PlatformCredentialCipher.from_secret(
        SecretStr(Fernet.generate_key().decode())
    )

    async with factory() as session:
        owner = User(
            email=f"cookie-scope-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        session.add(owner)
        await session.flush()
        workspace = Workspace(
            name="W", slug=f"w-{uuid.uuid4().hex}", owner_id=owner.id
        )
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="P",
            domain="mixed",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                PlatformCredentialBundle(
                    workspace_id=workspace.id,
                    project_id=None,
                    provider_id="tiktok_research",
                    encrypted_payload=cipher.encrypt(
                        {"creator_cookie": "workspace-cookie"}
                    ),
                    configured_fields=["creator_cookie"],
                    key_version=cipher.key_version,
                    created_by_user_id=owner.id,
                    updated_by_user_id=owner.id,
                ),
                PlatformCredentialBundle(
                    workspace_id=workspace.id,
                    project_id=project.id,
                    provider_id="tiktok_research",
                    encrypted_payload=cipher.encrypt(
                        {"creator_cookie": "project-cookie"}
                    ),
                    configured_fields=["creator_cookie"],
                    key_version=cipher.key_version,
                    created_by_user_id=owner.id,
                    updated_by_user_id=owner.id,
                ),
            ]
        )
        await session.commit()
        project_id = project.id

    async with factory() as session:
        assert (
            await resolve_creator_cookie(
                session, project_id=project_id, cipher=cipher
            )
            == "project-cookie"
        )
        project_bundle = (
            await session.execute(
                PlatformCredentialBundle.__table__.select().where(
                    PlatformCredentialBundle.project_id == project_id
                )
            )
        ).first()
        assert project_bundle is not None
        await session.execute(
            PlatformCredentialBundle.__table__.delete().where(
                PlatformCredentialBundle.project_id == project_id
            )
        )
        await session.commit()

    async with factory() as session:
        assert (
            await resolve_creator_cookie(
                session, project_id=project_id, cipher=cipher
            )
            == "workspace-cookie"
        )
    await engine.dispose()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_tiktok_creator_cookie_scope.py -v
```

Expected: FAIL。`tiktok_tools` 没有 `resolve_creator_cookie`；当前解析不传 `project_id`。

- [ ] **Step 3: 抽出解析函数并传 project_id**

In `apps/api/src/data_intelligence_hub/services/tiktok_tools.py`, replace `_resolve_creator_cookie` with:

```python
async def resolve_creator_cookie(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    cipher: PlatformCredentialCipher,
) -> str | None:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.services.platform_credentials import (
        get_platform_credential_values,
    )

    project = await session.get(Project, project_id)
    if project is None:
        return None
    values = await get_platform_credential_values(
        session,
        workspace_id=project.workspace_id,
        provider_id="tiktok_research",
        project_id=project_id,
        cipher=cipher,
    )
    return values.get("creator_cookie") or None


async def _resolve_creator_cookie(project_id: uuid.UUID) -> str | None:
    env_cookie = os.getenv("TIKHUB_TIKTOK_CREATOR_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    from data_intelligence_hub.core.config import get_settings
    from data_intelligence_hub.services.platform_credentials import (
        PlatformCredentialCipher,
    )

    master_key = get_settings().platform_credential_master_key
    if master_key is None:
        return None
    async with collect_session_factory() as session:
        return await resolve_creator_cookie(
            session,
            project_id=project_id,
            cipher=PlatformCredentialCipher.from_secret(master_key),
        )
```

Add `from sqlalchemy.ext.asyncio import AsyncSession` to the imports.

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/python -m pytest tests/unit/test_tiktok_creator_cookie_scope.py -v
```

Expected: `1 passed`。项目级 cookie 优先；删除项目级行后回退工作区级。

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/tiktok_tools.py \
  apps/api/tests/unit/test_tiktok_creator_cookie_scope.py
git commit -m "fix(tiktok): resolve creator cookie at project scope"
```

---

### Task 11: C14 控制台 `/keys` 与 `/connectors` 浏览器交接

C3 不改 `apps/scraper-console/**`。项目密钥 UI、`/connectors` 页面、侧栏、路由表与 Playwright 用例全部由 C14 实现。C3 只提供交接文档、API 形状与验收判据。

**Files:**
- Create: `docs/ops/c3-c14-keys-connectors-handoff.md`
- No console or e2e changes.

**Interfaces:**
- Consumes: `POST/GET /api/projects/{project_id}/keys`、`POST /api/projects/{project_id}/keys/{key_id}/rotate`、`DELETE /api/projects/{project_id}/keys/{key_id}`、`GET/PUT/DELETE /api/settings/platform-credentials`。
- Produces: C14 可直接执行的页面行为与浏览器判据。

- [ ] **Step 1: 写 C14 交接文档**

```bash
mkdir -p docs/ops
```

Create `docs/ops/c3-c14-keys-connectors-handoff.md`:

```markdown
# C3 → C14 密钥与连接器页面交接

## 项目密钥

- 列表：`GET /api/projects/{project_id}/keys`。
- 签发：`POST /api/projects/{project_id}/keys`，请求体包含 `label`、`tool_allowlist`、`capability_allowlist`、`daily_collect_quota`、可选 `expires_at`。
- 轮换：`POST /api/projects/{project_id}/keys/{key_id}/rotate`，请求体同签发。
- 撤销：`DELETE /api/projects/{project_id}/keys/{key_id}`。
- 明文只在签发与轮换响应出现一次；页面不得缓存或再次请求明文。
- 409 `project_api_key_active_exists` 显示“该项目已有一把未撤销的密钥”。
- 409 `state_conflict` 显示“该密钥已不在可轮换状态”。

## 凭据与连接器

- 列表：`GET /api/settings/platform-credentials`，可选 `project_id`。
- 写入：`PUT /api/settings/platform-credentials/{platform}`，可选 `project_id`。
- 删除：`DELETE /api/settings/platform-credentials/{platform}`，可选 `project_id`。
- 项目级优先，工作区级回退；页面必须显示当前作用域 `project`、`workspace` 或 `none`。
- `creator_cookie_metadata` 只显示 `captured_at`、`expires_at`、`last_verified_at`、`account_label`；不得显示 Cookie 明文或密文。
- 503 `vault_write_disabled` 显示“凭据写入被开关关闭”。

## Playwright 判据

1. `/connectors` 返回 200，存在 `<main>`。
2. 项目选择器切换后，凭据列表显示项目级徽标；清空项目后显示工作区级徽标。
3. 保存凭据后出现 `captured_at` 与 `expires_at`，不出现 Cookie 值。
4. 项目密钥卡显示 capability 列表、状态与轮换按钮；轮换后旧前缀消失。
5. 三个页面都没有 5xx、没有 `console.error`。

## 风险

C14 未完成前，C3 只有 API 与单元测试证据，没有真实浏览器证据。该风险由 C14 的 `/connectors` 与密钥用例、PG0 验收关闭。
```

- [ ] **Step 2: 确认没有控制台改动**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
git status --porcelain -- apps/scraper-console | tee /tmp/c3-console-status.txt
test ! -s /tmp/c3-console-status.txt && echo "CONSOLE_UNTOUCHED"
```

Expected: `CONSOLE_UNTOUCHED`。

- [ ] **Step 3: 提交前运行 GitNexus 变更分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 4: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
git add docs/ops/c3-c14-keys-connectors-handoff.md
git commit -m "docs(ops): hand off C3 keys and connectors to C14"
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 12: 全量回归与图谱门禁

**Files:**
- No source changes.

**Interfaces:**
- Consumes: 前 11 个 task 的全部交付。
- Produces: 可复核的测试、构建与图谱结果。

- [ ] **Step 1: 运行后端全量测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
export DATABASE_URL="postgresql+asyncpg://data_intel:dev_password@127.0.0.1:5432/c3_keys_test"
createdb c3_keys_test 2>/dev/null || true
DATABASE_URL="$DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$DATABASE_URL" ./.venv/bin/python -m pytest -q tests/unit tests/integration
```

Expected: 迁移升级成功；退出 0，无 failed。任何新失败都是回归。

- [ ] **Step 2: 运行后端静态检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3/apps/api
./.venv/bin/ruff check src tests
./.venv/bin/mypy src tests
```

Expected: 退出 0，`All checks passed!` 与 `Success: no issues found`。

- [ ] **Step 3: 运行契约校验**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: 退出 0。

- [ ] **Step 4: 运行图谱变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs impact "issue_key" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_platform_credential_values" --direction upstream --repo .
```

Expected: `detect-changes` 不含 `partial: true` 或 `truncated: true`；两个 impact 为 LOW，调用者与计划一致。

- [ ] **Step 5: 检查工作树**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c3
git status --short
git log --oneline -12
```

Expected: 工作树干净；12 个 commit 对应本计划 12 个 task。若仍有未提交文件，先定位原因，不得用 `git add -A` 掩盖。

---

## 统一发布门禁（PG0 发布批次；C14 只读）

本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。C3 只交付可合并的代码、迁移与验收证据，不执行生产发布命令。

发布顺序固定，任一步失败即停止同批次：

1. **先备份**：备份目标数据库与 compose 使用的持久卷，记录备份路径与 SHA-256。
2. **A 环境 canary**：先发布 A，运行冒烟与本计划 API 验收；失败时回滚 A，B 不发布。
3. **B 环境门禁**：B 只在用户对生产 B 给出明确目标授权，且 PG0 发布负责人完成备份校验和迁移门禁后发布。C14 只读记录授权与发布窗口，不授予目标权限；迁移门禁指 `alembic heads` 只有 `202610220059 (head)`、迁移在一次性库演练通过、备份可恢复。
4. **失败记 `BLOCKED`**：记录失败步骤、证据路径与决策人；不得跳过门禁继续发布。

C3 不改 compose，不部署，不执行生产迁移。部署证据由 PG0 发布批次收集；C14 收集只读验收证据。

---

## Self-Review

**Spec coverage**

| 设计或任务要求 | 覆盖 task |
|---|---|
| `project_api_keys.capability_allowlist` | 1、2、3、5、11 |
| 复合 FK 阻止跨工作区绑定 | 1、2、5 |
| 原子轮换 | 2、4、5、11 |
| 撤销与 `last_used_at` | 2、4、5 |
| 规范管理路由与旧路径兼容 | 1、5、11 |
| 平台凭据项目作用域 | 1、2、6、7、8、9、11 |
| `creator_cookie` 元数据 | 1、2、7、8、9、11 |
| Postgres NULL 唯一陷阱 | 1、2 |
| 依赖 C2 审计与 RBAC | 全局约束、1、5、9 |
| 客户 MCP enforcement 由 C13 执行 | 全局约束；C3 提供 `ProjectApiKeyIdentity.capability_allowlist` 与 `allows_capability`；无 `mcp_runtime` 白名单改动 |
| 控制台 `/connectors` 浏览器验收 | 11（C14 交接） |
| 精确错误码 | 1、5、9 |
| TDD 与提交 | 每个 task |

**Placeholder scan**

已检查：占位符扫描已通过；每个代码步骤含实际代码，每个测试步骤含实际断言。

**Type consistency**

- `rotate_key` 返回 `RotatedProjectApiKey`，路由使用 `.issued` 与 `.revoked_key_id`。
- `revoke_key_with_state` 返回 `RevokedProjectApiKey`，路由使用 `.record` 与 `.changed`。
- `resolve_platform_credential_bundle` 返回 `(bundle, scope)`，服务使用同名变量。
- `CreatorCookieMetadata` 在 schema、服务、C14 页面共用四个键。
- 契约路径、C2 依赖名与 C1/C2 计划一致。

---

## 审查摘要（2026-10-22 修订）

| 审查项 | 级别 | 处理 | 落点 |
|---|---|---:|---|
| 越权修改 C1 契约 | P0 | Task 1 改为只读守卫；删除契约/registry 写入；缺口交回 C1。 | Task 1、Global Constraints |
| 越权修改 C14 控制台 | P0 | 删除 Task 11-13 的全部 `apps/scraper-console/**` 与 e2e 改动；合并为 Task 11 C14 交接文档。 | File Structure、Task 11 |
| 没有分支/worktree 起点 | P0 | `git worktree add ../data_scrapy-gov-c3 -b feat/gov-c3 feat/gov-c2`；断言 C2 祖先、head 058、registry 存在。 | Global、Task 1 Step 1 |
| `project_keys.*` phase 写成 C2 | P0 | C1 已统一为 C3；C3 只读校验。 | Task 1 Step 2、C1 Task 8 |
| `credentials.list` 路径重复 | P0 | C1 统一为 `credentials.list/update/delete`；C3 只读。 | Task 1 Step 2、C1 Task 8 |
| C1 缺 C3 约束 | P0 | C1 登记两个部分唯一索引、两个复合外键、`uq_project_api_keys_active_project` 与 `tool_allowlist`；C3 守卫断言。 | Task 1 Step 2、C1 Task 3 |
| 缺逐任务 GitNexus impact | P1 | Global 要求每个编辑既有符号的任务先跑 impact；Task 12 复跑关键符号。 | Global、Task 12 Step 4 |
| Task 14 缺 mypy 与数据库 | P1 | 改为 Task 12：`mypy src tests`，显式 `DATABASE_URL` 一次性库。 | Task 12 |
| 计划 Markdown 未入提交 | P1 | Task 1 提交本计划文件；最终工作树干净。 | Task 1 Step 6 |
| `capability_allowlist` 与 `tool_allowlist` 双白名单 | P2 | 契约登记两列；C3 存储、展示、审计 `capability_allowlist`，并经 `ProjectApiKeyIdentity.capability_allowlist` 与 `allows_capability` 暴露；`tool_allowlist` 与 `capability_allowlist` 的 enforcement 都由 C13 执行。 | Global、C1 Task 3、Task 2、Task 3 |
| 原子轮换、凭据 scope、NULL 唯一 | 保持 | 单事务锁旧钥、`rotating` 释放活跃索引、新钥签发、旧钥 revoked；项目级优先工作区回退；两个部分唯一索引区分 NULL。 | Task 2、Task 4、Task 6 |

自检结论：占位符扫描已通过；C3 不修改契约、registry、控制台或 e2e；每个 commit 前运行 `detect-changes`。
