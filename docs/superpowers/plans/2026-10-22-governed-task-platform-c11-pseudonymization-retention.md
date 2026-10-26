# 受治理任务平台 C11：工作区伪名化与保留清理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为受治理任务平台建立工作区级稳定伪名、导出 PII 遮蔽、只读 PII 扫描（C9/C10 唯一扫描器）、来源 URL 去追踪参数、六类保留期、法律保留只读/写入服务和可 dry-run 的保留清理，并只新增一个迁移 `202610220069`。C11 只做伪名、遮蔽、保留与法律保留 dry-run；删除请求和 DSR 归 C12。

**Architecture:** 新增独立的服务边界：`pseudonymization` 管盐与 HMAC 伪名，`export_policy` 管导出字段策略与只读 PII 扫描（C9/C10 的唯一扫描器），`governed_dataset_export` 是客户导出唯一接缝并替换 `automation_service` 的旧导出路由。保留清理由 `retention_policy`、`legal_hold_service`、`retention_service` 与运维 CLI 组成；所有保留期清理删除先写 `retention_tombstones`，`legal_hold` 在候选筛选阶段阻断，`dry_run` 默认不写库。C12 的删除请求只写 `deletion_tombstones`，两个服务不得互相调用。客户导出四个路径与服务都先过 C2 项目 ACL；导出允许/拒绝、法律保留建立/释放与保留清理执行都写 C2 统一审计表。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2 async、Alembic、PostgreSQL/SQLite 测试、pytest、ruff、mypy。

## Global Constraints

- Q43 已定：普通评论者使用**工作区级盐**。同一工作区内稳定；跨工作区不可关联；不提供反查映射；项目隔离靠权限，不改项目级盐。
- **隔离 worktree。** 执行分支是 `feat/gov-c11`，worktree 是 `/Users/lute/Project/data_scrapy-gov-c11`，起点是 `feat/gov-c10`。主工作树 `/Users/lute/Project/data_scrapy` 只用于 Task 0 的 `git worktree prune`、前驱断言、`git worktree add` 与复制本计划。Task 0 之后所有 Run/Commit 命令都在 worktree 执行。
- `creator_cookie` 保留在**内部隔离客户链**。客户导出必须拒绝来源端点 `tikhub_tiktok_video_products` 和 `tikhub_tiktok_creator_showcase`，错误码固定为 `dataset_export_internal_isolated_source`。
- 八客户 MCP 工具清单是后续客户契约。C11 不新增、不改名、不删除任何 MCP 工具，不把导出接缝暴露为 MCP 工具。
- 保留期冻结如下，不得在代码、配置或环境变量中改写：原始响应 30 天；标准化数据集 12 个月（365 天）；正式报告和交付包 24 个月（730 天）；运行日志 180 天；安全与访问审计 24 个月（730 天）；备份 30 天。六类 TTL 必须与 `RETENTION_POLICY_VERSION = "retention_policy.v1"` 一一对应。
- 功能开关只有一个：`RETENTION_CLEANUP_ENABLED`，默认 `false`。关闭时 `retention_cleanup --execute` 拒绝写库；dry-run、法律保留写入和法律保留读取仍可用。回滚点是关闭该开关并回退应用版本，不删除 067 已建的表。
- C1 独占契约与 registry。C11 不修改 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 或 `configs/contracts/v1.1.0/registry.json`；缺对象时停止，由 C1 所有者补登记。
- 盐只使用 C1 已登记的对象：优先 `workspace_pseudonym_salts`；若 C1 把盐登记为 `PlatformCredentialBundle` 扩展，则按 C1 的对象实现。不得在 C11 自行新增第二种盐存储。
- 保留策略不建表；TTL 是代码常量。迁移只创建 C1 登记的四个 C11 对象，并替换两个既有审计触发器函数；不给任何既有表加列。若后续需要保留元数据列，只允许加在已存在的表，并先在 C1 登记。
- 安全审计 24 个月清理只允许专用数据库角色 `dih_retention_cleaner` 执行。迁移 067 必须替换 C2 `audit_events` 的 `reject_audit_event_mutation()` 与 C9 `report_audit_events` 的 `report_audit_events_append_only_fn()`：只允许该角色删除已过期行（`audit_events.occurred_at` 或 `report_audit_events.created_at` 早于 `now() - interval '730 days'`）；`UPDATE` 与普通应用角色的 `DELETE` 仍抛出异常。触发器替换、角色权限与普通应用拒绝行为必须有 PostgreSQL 测试。
- C2 链头导出与 `/api/audit-events/verify` 按可用段校验。C11 删除链首后不要求重建前缀；首个留存事件的 `prev_hash` 写入 `anchor_prev_hash`，更早的每日链头由 O0 的 WORM 证据保存。
- 只允许一个迁移：`revision = "202610220069"`，`down_revision = "202610220068"`。执行前 `alembic heads` 必须只有 `202610220068`。
- 不修改 `apps/api/src/data_intelligence_hub/services/automation_service.py`。该文件是冻结大文件；旧导出函数保留给内部隔离链，客户路由改走新接缝。
- 不做删除请求 / DSR 流程，不建 DSR 表，不实现删除审批 UI。
- C14 独占控制台与 Playwright。C11 只提供浏览器交接单，不修改 `apps/scraper-console/**`，不新增 HTTP 端点。
- 修改既有符号前必须跑 GitNexus `impact`。`ingest_tiktok_content` 的当前 upstream 风险为 **HIGH**，受影响流程是 `execute_collector_call`、`quick_collect`、`tiktok_video_comments`。不得忽略该警告。
- 每次 commit 前必须跑 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不是干净检查。
- **生产发布所有权。** PG0 发布负责人（PG0 发布批次）是生产 A/B 的唯一发布 owner：备份、迁移 067、角色检查、`.env.production` 设值、重启与 `RETENTION_CLEANUP_ENABLED` 切换都由该负责人执行。C14 只读：health、canary、preflight 与浏览器验收。C11 只在仓库追加 `RETENTION_CLEANUP_ENABLED` 与 `RETENTION_CLEANER_ROLE` 的静态 compose 映射和 `.env.example` 示例；不执行 ssh、备份、迁移、种子、生产 `.env` 值变更、容器重启或开关切换。生产 B 在 `202610190045` 的目标授权与备份门禁通过前保持 `BLOCKED`，不得应用 067；B 不阻断 A。
- **项目 ACL 接缝。** 客户导出的创建、列表、详情与下载四个路径和服务都调用 C2 `api.authz.require_project_access`。owner/admin 全项目通过；同工作区 member 只通过 `project_members` 授权项目；同工作区跨项目 403 `project_access_forbidden`；跨工作区 404 `project_not_found`。不得按 `workspace_members.role` 自行放行。
- **统一审计。** 导出允许写 `dataset.export.created` 与 `privacy.projection.applied`；导出拒绝经 C2 `record_authorization_denial` 写 `project.access.denied`。法律保留建立/释放写 `legal_hold.created` / `legal_hold.released`。保留清理 execute 写 `retention.cleanup.executed`，`details.config` 记录 policy version、开关与专用角色。动作只来自 C2 `AUDIT_ACTIONS`，不建第二张审计表。
- **保留工作区伪名与 067 触发器。** 不得改写工作区级盐语义（同工作区稳定、跨工作区不可关联、无返查映射）；不得改写 067 替换的 `dih_retention_cleaner` 730 天删除例外。C12 的 068 只能保留该例外并新增自己的角色例外；普通应用 `UPDATE` / `DELETE` 仍拒绝。
- **唯一 PII 扫描器。** `export_policy.scan_export_policy` / `scan_export_value` 是 C9 报告门禁与 C10 交付门禁的唯一扫描 API，版本常量为 `EXPORT_POLICY_VERSION = "export_policy.v1"`。C11 不新增第二套正则或第二套遮蔽规则；C9/C10 不复制规则，只消费 `PiiHit(kind, field_path, start, end)`，不得回传原始值。contact 匹配必须跳过 UUID（带连字符与 32 位无连字符）与 ISO-8601 时间戳，避免把 `contract_id`、`task_id`、`evidence_id`、`generated_at` 误报为电话。
- 浏览器门禁：C11 不修改 `apps/scraper-console/**`。出现控制台改动时停止，交 C14。C11 的浏览器交接只允许 C14 在 `/settings` 内联展示，不新增第 12 条合同路由。
- 中文文档按 ASD-STE100 等效规则写：短句、主动语态、一义一词。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `docs/design/【契约冻结】v1-表名-枚举-接口.md` | 只读校验 C1 v1.1 的四个 C11 对象、枚举、TTL 与导出规则；C11 不修改 |
| `apps/api/alembic/versions/202610220069_pseudonymization_retention.py` | 唯一迁移：C1 登记的四个 C11 对象与索引；替换 C2/C9 审计 append-only 触发器函数并授予专用角色权限 |
| `apps/api/src/data_intelligence_hub/models/retention.py` | 四个 SQLAlchemy 模型与保留枚举常量 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | 导出新模型 |
| `apps/api/src/data_intelligence_hub/services/pseudonymization.py` | 工作区盐、HMAC 伪名、无日志承诺 |
| `apps/api/src/data_intelligence_hub/services/export_policy.py` | 纯函数：PII 遮蔽、只读 PII 扫描（`scan_export_policy` / `scan_export_value`）、handle 伪名、URL 去追踪参数 |
| `apps/api/src/data_intelligence_hub/services/governed_dataset_export.py` | 客户导出唯一接缝：项目 ACL、审计、策略应用、渲染、任务记录、下载 |
| `apps/api/src/data_intelligence_hub/api/authz.py` | C2 提供 `require_project_access`；C11 只调用，不修改 |
| `apps/api/src/data_intelligence_hub/services/audit_log.py` | C2 提供 `append_audit_event` 与 `record_authorization_denial`；C11 只调用，不修改 |
| `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py` | 在规范化阶段写入评论者与评论作者伪名 |
| `apps/api/src/data_intelligence_hub/core/config.py` | `retention_cleaner_role`、`retention_cleanup_enabled` 开关 |
| `apps/api/.env.example` | 追加 `RETENTION_CLEANUP_ENABLED=false` 与 `RETENTION_CLEANER_ROLE=dih_retention_cleaner` 示例 |
| `configs/deploy/scrapy/docker-compose.yml` | 只追加两个静态环境变量映射；部署与设值由 PG0 发布负责人执行，C14 只读 |
| `apps/api/src/data_intelligence_hub/services/retention_policy.py` | 冻结的六类 TTL 常量 |
| `apps/api/src/data_intelligence_hub/services/legal_hold_service.py` | 法律保留创建、释放、查询与匹配 |
| `apps/api/src/data_intelligence_hub/services/retention_service.py` | dry-run / execute 清理引擎、tombstone、清理运行记录 |
| `apps/api/src/data_intelligence_hub/maintenance/retention_cleanup.py` | 运维 CLI：保留清理与法律保留，默认 dry-run |
| `apps/api/src/data_intelligence_hub/api/routes/automation.py` | 四个导出路由改走新接缝 |
| `apps/api/tests/unit/test_contract_c11_objects.py` | 契约 v1.1 对象登记测试 |
| `apps/api/tests/unit/test_pseudonymization_retention_migration_source.py` | 迁移 067 源测试 |
| `apps/api/tests/postgres/test_audit_retention_cleaner.py` | PostgreSQL 触发器测试：普通应用拒绝、专用角色只删过期行、`UPDATE` 始终拒绝 |
| `apps/api/tests/unit/test_retention_models.py` | 模型表与约束测试 |
| `apps/api/tests/unit/test_pseudonymization.py` | 盐与伪名稳定性测试 |
| `apps/api/tests/unit/test_export_policy.py` | 遮蔽与只读 PII 扫描纯函数测试（含 C9 report/claim/html 与 C10 manifest 调用方形态） |
| `apps/api/tests/integration/test_governed_dataset_export.py` | 客户导出端到端遮蔽测试 |
| `apps/api/tests/unit/test_tiktok_ingestion_pseudonymization.py` | 规范化阶段伪名测试 |
| `apps/api/tests/unit/test_retention_policy.py` | TTL 冻结测试 |
| `apps/api/tests/unit/test_retention_deploy_facts.py` | `.env.example` 与共享 compose 的精确键名和默认值测试 |
| `apps/api/tests/unit/test_legal_hold_service.py` | 法律保留测试 |
| `apps/api/tests/unit/test_retention_cleanup.py` | 清理 dry-run / execute / 法律保留 / 路径测试 |
| `apps/api/tests/unit/test_retention_cleanup_cli.py` | CLI 默认 dry-run 测试 |

---

### Task 0: 隔离 worktree 初始化

**Files:**
- 只读：`/Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c11-pseudonymization-retention.md`（主工作树的计划文件，复制源）
- Create: `/Users/lute/Project/data_scrapy-gov-c11`（worktree 根）

**Interfaces:**
- Consumes: 前置分支 `feat/gov-c10`；主工作树的计划文件。
- Produces: 分支 `feat/gov-c11` 与 worktree `/Users/lute/Project/data_scrapy-gov-c11`；Task 0 之后所有 Run/Commit 都在该 worktree 执行。

- [ ] **Step 0: 主工作树只读预检**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c10^{commit}
git rev-parse --verify --quiet refs/heads/feat/gov-c11 || echo "C11_BRANCH_ABSENT"
test ! -e /Users/lute/Project/data_scrapy-gov-c11 && echo "worktree_path_free"
```

Expected: `git worktree prune` 退出码 0；`git rev-parse` 输出 `feat/gov-c10` 提交 SHA；输出 `C11_BRANCH_ABSENT` 与 `worktree_path_free`。`feat/gov-c10` 不存在、分支 `feat/gov-c11` 已存在或 worktree 路径已存在时停止，先审查旧分支与旧 worktree，不得复用或删除。

- [ ] **Step 1: 创建 worktree 并同步依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree add /Users/lute/Project/data_scrapy-gov-c11 -b feat/gov-c11 feat/gov-c10
cd /Users/lute/Project/data_scrapy-gov-c11
test "$(git branch --show-current)" = feat/gov-c11 && echo "branch=feat/gov-c11"
git merge-base --is-ancestor feat/gov-c10 HEAD; echo "c10_ancestor=$?"
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c11-pseudonymization-retention.md docs/superpowers/plans/
cd apps/api && uv sync
```

Expected: `branch=feat/gov-c11`；`c10_ancestor=0`；`uv sync` 退出码 0。本计划的 Markdown 不在 `feat/gov-c10` 内，必须先从主工作树复制到 worktree。主工作树只用于本 Step 的 `git worktree add`、只读预检与 `cp` 源。

- [ ] **Step 2: 固定执行路径与迁移基线**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
git rev-parse --show-toplevel
git status --short
cd apps/api && uv run alembic heads
```

Expected: 输出 `/Users/lute/Project/data_scrapy-gov-c11`；工作区干净或只有本计划文件；Alembic 只有一行 `202610220068 (head)`。不是单 head 时停止，C1–C10 尚未落地；不得把本迁移改号或接到 `202610210055`。后续 Run/Commit 块必须在该 worktree 内执行。

---

### Task 1: C1 契约与 GitNexus 预检

**Files:**
- Test: `apps/api/tests/unit/test_contract_c11_objects.py`

**Interfaces:**
- Consumes: C1 已冻结的 `docs/design/【契约冻结】v1-表名-枚举-接口.md`、`configs/contracts/v1.1.0/registry.json`。
- Produces: C11 对象与 TTL 的只读门禁。C11 不修改契约、不修改 registry。

- [ ] **Step 1: 跑 GitNexus impact 并记录风险**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs impact "ingest_tiktok_content" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_product_dataset_export" --direction upstream --repo .
node .gitnexus/run.cjs impact "_ingest_comment" --direction upstream --repo .
node .gitnexus/run.cjs impact "_ingest_product_review" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_product_dataset_export_route" --direction upstream --repo .
```
Expected:
- `ingest_tiktok_content`: `risk: HIGH`，直接调用者 `_ingest_tiktok_content_if_needed`、`backfill_tiktok_content`，流程 `execute_collector_call`、`quick_collect`、`tiktok_video_comments`。执行时必须在提交说明中记录该风险与缓解。
- `create_product_dataset_export`: `risk: LOW`，唯一直接调用者 `create_product_dataset_export_route`。
- `_ingest_comment` 与 `_ingest_product_review`: `risk: LOW`。
- `create_product_dataset_export_route`: `risk: UNKNOWN`。按 CLAUDE.md，UNKNOWN 不是放行。必须跑下面的文本搜索确认调用面。

Run:
```bash
rg -n "create_product_dataset_export_route|create_product_dataset_export" apps/api/src apps/api/tests
```
Expected: 只有 `apps/api/src/data_intelligence_hub/api/routes/automation.py` 的导入与路由调用，加上本计划新增测试。

- [ ] **Step 2: 记录 C1 契约只读基线**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```
Expected: `contract_registry_ok`。失败时停止，先由 C1 所有者修复。

- [ ] **Step 3: 写只读契约登记测试**

Create `apps/api/tests/unit/test_contract_c11_objects.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "design"
    / "【契约冻结】v1-表名-枚举-接口.md"
)
REGISTRY = (
    Path(__file__).resolve().parents[4]
    / "configs"
    / "contracts"
    / "v1.1.0"
    / "registry.json"
)

C11_TABLES = {
    "workspace_pseudonym_salts",
    "legal_holds",
    "retention_cleanup_runs",
    "retention_tombstones",
}


def test_contract_has_c11_objects_and_ttl() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for table in C11_TABLES:
        assert f"`{table}`" in text, table
    for token in (
        "raw_response",
        "normalized_dataset",
        "report_delivery",
        "run_log",
        "security_access_audit",
        "backup",
        "retention_ttl",
        "202610220069",
    ):
        assert token in text, token
    assert "原始响应 | 30 天" in text
    assert "标准化数据集 | 12 个月（365 天）" in text
    assert "正式报告和交付包 | 24 个月（730 天）" in text
    assert "运行日志 | 180 天" in text
    assert "安全与访问审计 | 24 个月（730 天）" in text
    assert "备份 | 30 天" in text


def test_registry_registers_c11_tables() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    names = {table["name"] for table in registry["tables"]}
    assert C11_TABLES <= names
    c11 = next(item for item in registry["work_packages"] if item["id"] == "C11")
    assert {f"table:{table}" for table in C11_TABLES} <= set(c11["objects"])
```

- [ ] **Step 4: 运行只读契约测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_contract_c11_objects.py -v
```
Expected: PASS（只读门禁）。若 FAIL，缺项由 C1 所有者补登记；C11 不直接改契约或 registry。

- [ ] **Step 5: 记录不改契约的边界**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
git diff --exit-code -- "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  configs/contracts/v1.1.0/registry.json
```
Expected: 退出码 0，无输出。

- [ ] **Step 6: 运行图变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_contract_c11_objects.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(contract): verify c11 objects are registered by c1"
```
Expected: `detect-changes` 不是 `partial: true`，不是 `truncated: true`。

---

### Task 2: 迁移 067 与保留模型

**Files:**
- Create: `apps/api/alembic/versions/202610220069_pseudonymization_retention.py`
- Create: `apps/api/src/data_intelligence_hub/models/retention.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Test: `apps/api/tests/unit/test_pseudonymization_retention_migration_source.py`
- Test: `apps/api/tests/unit/test_retention_models.py`
- Test: `apps/api/tests/postgres/test_audit_retention_cleaner.py`

**Interfaces:**
- Consumes: 契约 v1.1 的表名、枚举、TTL；C2 迁移 058 的 `reject_audit_event_mutation()` 与 `trg_audit_events_append_only`；C9 迁移 065 的 `report_audit_events_append_only_fn()` 与 `trg_report_audit_events_append_only`。
- Produces:
  - `WorkspacePseudonymSalt(workspace_id, salt_version, salt_b64, created_at)`
  - `LegalHold(workspace_id, project_id, data_class, status, reason, requested_by_user_id, requested_at, released_by_user_id, released_at, release_reason, created_at)`
  - `RetentionCleanupRun(mode, status, policy_version, requested_by_user_id, started_at, finished_at, cutoffs, counts, samples, blocked, error_message, created_at)`
  - `RetentionTombstone(workspace_id, project_id, data_class, subject_type, subject_id, cleanup_run_id, deleted_at, reason, metadata_json)`
  - 常量 `RETENTION_DATA_CLASSES`
  - 角色 `dih_retention_cleaner`（`NOLOGIN`，若不存在则创建）；两个审计表的 `SELECT`、`DELETE` 权限；角色授予迁移执行者，供 `SET LOCAL ROLE` 使用。
  - 替换后的触发器函数：普通应用 `DELETE` 与所有 `UPDATE` 仍拒绝；专用角色只能删除超过 730 天的行。

- [ ] **Step 0: 确认迁移父修订**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run alembic heads
```
Expected: 只有一行 `202610220068 (head)`。
If not, stop. C1–C10 尚未落地。不得把本迁移改号或接到 `202610210055`。

- [ ] **Step 1: 写迁移源测试（先失败）**

Create `apps/api/tests/unit/test_pseudonymization_retention_migration_source.py`:
```python
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202610220069_pseudonymization_retention.py"
)


class RecordingOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, args, kwargs))

        return record


class MigrationModule(Protocol):
    revision: str
    down_revision: str | None
    op: object

    def upgrade(self) -> None: ...

    def downgrade(self) -> None: ...


def _load_migration() -> MigrationModule:
    assert MIGRATION_PATH.is_file()
    spec = importlib.util.spec_from_file_location(
        "pseudonymization_retention_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def _constraint_names(args: tuple[object, ...]) -> set[str]:
    return {
        cast(str, item.name)
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }


def test_migration_is_single_revision_after_066() -> None:
    module = _load_migration()
    assert module.revision == "202610220069"
    assert module.down_revision == "202610220068"


def test_upgrade_creates_four_c11_tables_and_constraints() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    tables = {
        args[0]
        for name, args, _ in recorder.calls
        if name == "create_table"
    }
    assert tables == {
        "workspace_pseudonym_salts",
        "legal_holds",
        "retention_cleanup_runs",
        "retention_tombstones",
    }
    assert not any(
        name in {"add_column", "alter_column", "drop_column"}
        for name, _args, _kwargs in recorder.calls
    )

    by_table = {
        args[0]: _constraint_names(args)
        for name, args, _ in recorder.calls
        if name == "create_table"
    }
    assert "ck_workspace_pseudonym_salts_salt_version" in by_table[
        "workspace_pseudonym_salts"
    ]
    assert {
        "ck_legal_holds_status",
        "ck_legal_holds_data_class",
        "ck_legal_holds_release_fields",
    } <= by_table["legal_holds"]
    assert {
        "ck_retention_cleanup_runs_mode",
        "ck_retention_cleanup_runs_status",
    } <= by_table["retention_cleanup_runs"]
    assert {
        "ck_retention_tombstones_data_class",
        "ck_retention_tombstones_reason",
    } <= by_table["retention_tombstones"]


def test_upgrade_creates_scope_indexes() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    indexes = {
        args[0]
        for name, args, _ in recorder.calls
        if name == "create_index"
    }
    assert {
        "ix_legal_holds_workspace_status",
        "ix_legal_holds_scope",
        "ix_retention_cleanup_runs_created_at",
        "ix_retention_tombstones_workspace_class",
        "ix_retention_tombstones_cleanup_run",
    } <= indexes


def test_upgrade_replaces_audit_append_only_triggers_for_cleaner_role() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    executed = " ".join(
        str(args[0]) for name, args, _ in recorder.calls if name == "execute"
    )
    assert "c11_requires_c2_audit_events" in executed
    assert "c11_requires_c9_report_audit_events" in executed
    assert "trg_audit_events_append_only" in executed
    assert "trg_report_audit_events_append_only" in executed
    assert "CREATE ROLE dih_retention_cleaner NOLOGIN" in executed
    assert "GRANT SELECT, DELETE ON audit_events, report_audit_events" in executed
    assert "CREATE OR REPLACE FUNCTION reject_audit_event_mutation" in executed
    assert "CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn" in executed
    assert "current_user = 'dih_retention_cleaner'" in executed
    assert "OLD.occurred_at < now() - interval '730 days'" in executed
    assert "OLD.created_at < now() - interval '730 days'" in executed
    assert "audit_events is append-only" in executed
    assert "report_audit_events_append_only" in executed


def test_downgrade_restores_strict_append_only_functions() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    executed = " ".join(
        str(args[0]) for name, args, _ in recorder.calls if name == "execute"
    )
    assert "CREATE OR REPLACE FUNCTION reject_audit_event_mutation" in executed
    assert "CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn" in executed
    assert "REVOKE SELECT, DELETE ON audit_events, report_audit_events" in executed
    assert "OLD.occurred_at < now() - interval '730 days'" not in executed
    assert "OLD.created_at < now() - interval '730 days'" not in executed


def test_downgrade_drops_c11_tables() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    dropped = {
        args[0]
        for name, args, _ in recorder.calls
        if name == "drop_table"
    }
    assert dropped == {
        "retention_tombstones",
        "retention_cleanup_runs",
        "legal_holds",
        "workspace_pseudonym_salts",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization_retention_migration_source.py -v
```
Expected: FAIL。`MIGRATION_PATH.is_file()` 为假。

- [ ] **Step 3: 写迁移 067**

Create `apps/api/alembic/versions/202610220069_pseudonymization_retention.py`:
```python
"""Create workspace pseudonym salts, legal holds and retention bookkeeping.

Revision ID: 202610220069
Revises: 202610220068
Create Date: 2026-10-22

说明：

- 一个工作区一行伪名盐。盐只供平台运行时使用，不写日志和导出。
- 法律保留按工作区、项目和数据类收窄。空项目与空数据类表示全范围。
- 保留清理只记录 execute。dry-run 不写库。
- tombstone 记录被删除或脱敏的主体，不保存正文。
- 本迁移替换 C2 ``audit_events`` 与 C9 ``report_audit_events`` 的 append-only
  触发器函数，只允许 ``dih_retention_cleaner`` 删除超过 730 天的行。
  ``UPDATE`` 和普通应用角色的 ``DELETE`` 仍抛出异常。
- 角色不存在时创建 ``NOLOGIN`` 角色，并授予迁移执行者成员关系，供
  ``SET LOCAL ROLE`` 使用。迁移执行者需要 ``CREATEROLE`` 权限；否则由 DBA
  预先创建同名角色并授予迁移执行者 ``ADMIN OPTION``。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220069"
down_revision: str | None = "202610220068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_CLASSES = (
    "raw_response",
    "normalized_dataset",
    "report_delivery",
    "run_log",
    "security_access_audit",
    "backup",
)
_DATA_CLASS_SQL = ", ".join(f"'{value}'" for value in _DATA_CLASSES)


def upgrade() -> None:
    op.create_table(
        "workspace_pseudonym_salts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "salt_version",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
        sa.Column("salt_b64", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_pseudonym_salts"),
        sa.UniqueConstraint(
            "workspace_id",
            name="uq_workspace_pseudonym_salts_workspace_id",
        ),
        sa.CheckConstraint(
            "salt_version = 'v1'",
            name="ck_workspace_pseudonym_salts_salt_version",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_pseudonym_salts_workspace_id_workspaces",
        ),
    )

    op.create_table(
        "legal_holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("data_class", sa.String(length=40), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_legal_holds"),
        sa.CheckConstraint(
            "status IN ('active', 'released')",
            name="ck_legal_holds_status",
        ),
        sa.CheckConstraint(
            f"data_class IS NULL OR data_class IN ({_DATA_CLASS_SQL})",
            name="ck_legal_holds_data_class",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND released_at IS NULL "
            "AND released_by_user_id IS NULL AND release_reason IS NULL) "
            "OR (status = 'released' AND released_at IS NOT NULL "
            "AND released_by_user_id IS NOT NULL AND release_reason IS NOT NULL)",
            name="ck_legal_holds_release_fields",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_legal_holds_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_legal_holds_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_legal_holds_requested_by_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["released_by_user_id"],
            ["users.id"],
            name="fk_legal_holds_released_by_user_id_users",
        ),
    )
    op.create_index(
        "ix_legal_holds_workspace_status",
        "legal_holds",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_legal_holds_scope",
        "legal_holds",
        ["workspace_id", "project_id", "data_class"],
    )

    op.create_table(
        "retention_cleanup_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cutoffs", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("samples", sa.JSON(), nullable=False),
        sa.Column("blocked", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_retention_cleanup_runs"),
        sa.CheckConstraint(
            "mode IN ('dry_run', 'execute')",
            name="ck_retention_cleanup_runs_mode",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'blocked', 'failed')",
            name="ck_retention_cleanup_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_retention_cleanup_runs_requested_by_user_id_users",
        ),
    )
    op.create_index(
        "ix_retention_cleanup_runs_created_at",
        "retention_cleanup_runs",
        ["created_at"],
    )

    op.create_table(
        "retention_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("data_class", sa.String(length=40), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=120), nullable=False),
        sa.Column("cleanup_run_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reason",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'retention_ttl'"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_retention_tombstones"),
        sa.UniqueConstraint(
            "workspace_id",
            "data_class",
            "subject_type",
            "subject_id",
            name="uq_retention_tombstones_subject",
        ),
        sa.CheckConstraint(
            f"data_class IN ({_DATA_CLASS_SQL})",
            name="ck_retention_tombstones_data_class",
        ),
        sa.CheckConstraint(
            "reason IN ('retention_ttl')",
            name="ck_retention_tombstones_reason",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_retention_tombstones_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_retention_tombstones_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["cleanup_run_id"],
            ["retention_cleanup_runs.id"],
            name="fk_retention_tombstones_cleanup_run_id_retention_cleanup_runs",
        ),
    )
    op.create_index(
        "ix_retention_tombstones_workspace_class",
        "retention_tombstones",
        ["workspace_id", "data_class"],
    )
    op.create_index(
        "ix_retention_tombstones_cleanup_run",
        "retention_tombstones",
        ["cleanup_run_id"],
    )

    # C2 与 C9 必须先落地。缺少表或触发器时停止，不静默跳过。
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.audit_events') IS NULL THEN
                RAISE EXCEPTION 'c11_requires_c2_audit_events';
            END IF;
            IF to_regclass('public.report_audit_events') IS NULL THEN
                RAISE EXCEPTION 'c11_requires_c9_report_audit_events';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_audit_events_append_only'
                  AND tgrelid = 'audit_events'::regclass
                  AND NOT tgisinternal
            ) THEN
                RAISE EXCEPTION 'c11_requires_c2_audit_trigger';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_report_audit_events_append_only'
                  AND tgrelid = 'report_audit_events'::regclass
                  AND NOT tgisinternal
            ) THEN
                RAISE EXCEPTION 'c11_requires_c9_report_audit_trigger';
            END IF;
        END;
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'dih_retention_cleaner'
            ) THEN
                EXECUTE 'CREATE ROLE dih_retention_cleaner NOLOGIN';
            END IF;
        END;
        $$
        """
    )
    op.execute(
        "GRANT dih_retention_cleaner TO CURRENT_USER"
    )
    op.execute(
        "GRANT SELECT, DELETE ON audit_events, report_audit_events "
        "TO dih_retention_cleaner"
    )
    op.execute(
        "REVOKE INSERT, UPDATE, TRUNCATE ON audit_events, report_audit_events "
        "FROM dih_retention_cleaner"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_user = 'dih_retention_cleaner'
               AND OLD.occurred_at < now() - interval '730 days' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn()
        RETURNS trigger
        AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_user = 'dih_retention_cleaner'
               AND OLD.created_at < now() - interval '730 days' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'report_audit_events_append_only: %', OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # 回滚时恢复严格 append-only 函数。触发器本身沿用 C2/C9 已创建的对象。
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn()
        RETURNS trigger
        AS $$
        BEGIN
            RAISE EXCEPTION 'report_audit_events_append_only: %', OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'dih_retention_cleaner'
            ) THEN
                EXECUTE 'REVOKE SELECT, DELETE ON audit_events, report_audit_events '
                    'FROM dih_retention_cleaner';
            END IF;
        END;
        $$
        """
    )
    op.drop_index(
        "ix_retention_tombstones_cleanup_run",
        table_name="retention_tombstones",
    )
    op.drop_index(
        "ix_retention_tombstones_workspace_class",
        table_name="retention_tombstones",
    )
    op.drop_table("retention_tombstones")
    op.drop_index(
        "ix_retention_cleanup_runs_created_at",
        table_name="retention_cleanup_runs",
    )
    op.drop_table("retention_cleanup_runs")
    op.drop_index("ix_legal_holds_scope", table_name="legal_holds")
    op.drop_index("ix_legal_holds_workspace_status", table_name="legal_holds")
    op.drop_table("legal_holds")
    op.drop_table("workspace_pseudonym_salts")
```

- [ ] **Step 4: 运行迁移源测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization_retention_migration_source.py -v
```
Expected: PASS，6 passed。

- [ ] **Step 5: 写模型**

Create `apps/api/src/data_intelligence_hub/models/retention.py`:
```python
"""Pseudonymization salt and retention bookkeeping models.

契约冻结 v1.1 §1.1、§2.9、§4.4 是唯一事实源。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

RETENTION_DATA_CLASSES: tuple[str, ...] = (
    "raw_response",
    "normalized_dataset",
    "report_delivery",
    "run_log",
    "security_access_audit",
    "backup",
)

_DATA_CLASS_SQL = ", ".join(f"'{value}'" for value in RETENTION_DATA_CLASSES)


class WorkspacePseudonymSalt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_pseudonym_salts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            name="uq_workspace_pseudonym_salts_workspace_id",
        ),
        CheckConstraint(
            "salt_version = 'v1'",
            name="ck_workspace_pseudonym_salts_salt_version",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    salt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'v1'"),
    )
    salt_b64: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LegalHold(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'released')",
            name="ck_legal_holds_status",
        ),
        CheckConstraint(
            f"data_class IS NULL OR data_class IN ({_DATA_CLASS_SQL})",
            name="ck_legal_holds_data_class",
        ),
        CheckConstraint(
            "(status = 'active' AND released_at IS NULL "
            "AND released_by_user_id IS NULL AND release_reason IS NULL) "
            "OR (status = 'released' AND released_at IS NOT NULL "
            "AND released_by_user_id IS NOT NULL AND release_reason IS NOT NULL)",
            name="ck_legal_holds_release_fields",
        ),
        Index("ix_legal_holds_workspace_status", "workspace_id", "status"),
        Index("ix_legal_holds_scope", "workspace_id", "project_id", "data_class"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    data_class: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RetentionCleanupRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retention_cleanup_runs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('dry_run', 'execute')",
            name="ck_retention_cleanup_runs_mode",
        ),
        CheckConstraint(
            "status IN ('completed', 'blocked', 'failed')",
            name="ck_retention_cleanup_runs_status",
        ),
        Index("ix_retention_cleanup_runs_created_at", "created_at"),
    )

    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cutoffs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    samples: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blocked: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RetentionTombstone(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retention_tombstones"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "data_class",
            "subject_type",
            "subject_id",
            name="uq_retention_tombstones_subject",
        ),
        CheckConstraint(
            f"data_class IN ({_DATA_CLASS_SQL})",
            name="ck_retention_tombstones_data_class",
        ),
        CheckConstraint(
            "reason IN ('retention_ttl')",
            name="ck_retention_tombstones_reason",
        ),
        Index(
            "ix_retention_tombstones_workspace_class",
            "workspace_id",
            "data_class",
        ),
        Index(
            "ix_retention_tombstones_cleanup_run",
            "cleanup_run_id",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    data_class: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(120), nullable=False)
    cleanup_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retention_cleanup_runs.id"),
        nullable=False,
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'retention_ttl'"),
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
```

- [ ] **Step 6: 导出新模型**

Modify `apps/api/src/data_intelligence_hub/models/__init__.py`:
- Add import after `report` imports:
```python
from data_intelligence_hub.models.retention import (
    LegalHold,
    RetentionCleanupRun,
    RetentionTombstone,
    WorkspacePseudonymSalt,
)
```
- Add to `__all__` in alphabetical order:
```python
    "LegalHold",
    "RetentionCleanupRun",
    "RetentionTombstone",
    "WorkspacePseudonymSalt",
```

- [ ] **Step 7: 写模型测试**

Create `apps/api/tests/unit/test_retention_models.py`:
```python
from __future__ import annotations

from data_intelligence_hub.models import (
    Base,
    LegalHold,
    RetentionCleanupRun,
    RetentionTombstone,
    WorkspacePseudonymSalt,
)
from data_intelligence_hub.models.retention import RETENTION_DATA_CLASSES


def test_c11_tables_are_registered() -> None:
    for table in (
        "workspace_pseudonym_salts",
        "legal_holds",
        "retention_cleanup_runs",
        "retention_tombstones",
    ):
        assert table in Base.metadata.tables


def test_affected_models_for_retention_exist() -> None:
    for table in (
        "raw_records",
        "datasets",
        "dataset_versions",
        "dataset_export_jobs",
        "reports",
        "task_runs",
        "audit_events",
        "report_audit_events",
        "workflow_run_action_audit_events",
    ):
        assert table in Base.metadata.tables, f"retention target missing: {table}"


def test_c11_models_are_exported() -> None:
    assert WorkspacePseudonymSalt.__tablename__ == "workspace_pseudonym_salts"
    assert LegalHold.__tablename__ == "legal_holds"
    assert RetentionCleanupRun.__tablename__ == "retention_cleanup_runs"
    assert RetentionTombstone.__tablename__ == "retention_tombstones"


def test_retention_data_classes_are_frozen() -> None:
    assert RETENTION_DATA_CLASSES == (
        "raw_response",
        "normalized_dataset",
        "report_delivery",
        "run_log",
        "security_access_audit",
        "backup",
    )


def test_constraint_names_match_contract() -> None:
    legal_names = {
        constraint.name for constraint in Base.metadata.tables["legal_holds"].constraints
    }
    assert {
        "ck_legal_holds_status",
        "ck_legal_holds_data_class",
        "ck_legal_holds_release_fields",
    } <= legal_names

    run_names = {
        constraint.name
        for constraint in Base.metadata.tables["retention_cleanup_runs"].constraints
    }
    assert {
        "ck_retention_cleanup_runs_mode",
        "ck_retention_cleanup_runs_status",
    } <= run_names

    tombstone_names = {
        constraint.name
        for constraint in Base.metadata.tables["retention_tombstones"].constraints
    }
    assert {
        "ck_retention_tombstones_data_class",
        "ck_retention_tombstones_reason",
    } <= tombstone_names
```

- [ ] **Step 8: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization_retention_migration_source.py tests/unit/test_retention_models.py -v
```
Expected: PASS，11 passed。

- [ ] **Step 9: 写并运行 PostgreSQL 触发器测试**

Create `apps/api/tests/postgres/test_audit_retention_cleaner.py`:

```python
"""PostgreSQL audit retention trigger test.

Requires a scratch database:
TEST_DATABASE_URL=postgresql+asyncpg://localhost/c11_retention_cleaner_workflow_plan_phase2_test
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import (
    AuditEvent,
    Project,
    Report,
    ReportAuditEvent,
    User,
    Workspace,
    WorkspaceMember,
)

NOW = datetime.now(UTC)


@pytest_asyncio.fixture()
async def session_factory(
    postgres_database_url: str,
) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(postgres_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed(
    factory: async_sessionmaker[AsyncSession],
) -> dict[str, uuid.UUID]:
    async with factory() as session:
        user = User(
            email=f"c11-{uuid.uuid4()}@example.com",
            password_hash="x",
            name="C11",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            name="C11", slug=f"c11-{user.id}", owner_id=user.id
        )
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=user.id, role="owner"
            )
        )
        project = Project(
            workspace_id=workspace.id,
            name="C11",
            domain="mixed",
            status="active",
            owner_id=user.id,
        )
        session.add(project)
        await session.flush()
        report = Report(
            workspace_id=workspace.id,
            project_id=project.id,
            report_type="daily",
            title="C11",
            content="body",
            status="draft",
            period_start=NOW - timedelta(days=800),
            period_end=NOW - timedelta(days=799),
        )
        session.add(report)
        await session.flush()

        ids = {
            "old_event": uuid.uuid4(),
            "fresh_event": uuid.uuid4(),
            "update_event": uuid.uuid4(),
            "old_report_event": uuid.uuid4(),
            "fresh_report_event": uuid.uuid4(),
        }
        session.add_all(
            [
                AuditEvent(
                    id=ids["old_event"],
                    workspace_id=workspace.id,
                    sequence_number=1,
                    actor_type="system",
                    action="old",
                    resource_type="test",
                    result="success",
                    details={},
                    prev_hash="0" * 64,
                    event_hash="1" * 64,
                    occurred_at=NOW - timedelta(days=731),
                ),
                AuditEvent(
                    id=ids["fresh_event"],
                    workspace_id=workspace.id,
                    sequence_number=2,
                    actor_type="system",
                    action="fresh",
                    resource_type="test",
                    result="success",
                    details={},
                    prev_hash="1" * 64,
                    event_hash="2" * 64,
                    occurred_at=NOW - timedelta(days=1),
                ),
                AuditEvent(
                    id=ids["update_event"],
                    workspace_id=workspace.id,
                    sequence_number=3,
                    actor_type="system",
                    action="update",
                    resource_type="test",
                    result="success",
                    details={},
                    prev_hash="2" * 64,
                    event_hash="3" * 64,
                    occurred_at=NOW - timedelta(days=731),
                ),
                ReportAuditEvent(
                    id=ids["old_report_event"],
                    workspace_id=workspace.id,
                    report_id=report.id,
                    actor_id=user.id,
                    event_type="old",
                    created_at=NOW - timedelta(days=731),
                ),
                ReportAuditEvent(
                    id=ids["fresh_report_event"],
                    workspace_id=workspace.id,
                    report_id=report.id,
                    actor_id=user.id,
                    event_type="fresh",
                    created_at=NOW - timedelta(days=1),
                ),
            ]
        )
        await session.commit()
        return ids


_DELETE_SQL = {
    "audit_events": text("DELETE FROM audit_events WHERE id = :id"),
    "report_audit_events": text(
        "DELETE FROM report_audit_events WHERE id = :id"
    ),
}


async def _delete(
    session: AsyncSession,
    table: str,
    row_id: uuid.UUID,
) -> None:
    await session.execute(_DELETE_SQL[table], {"id": row_id})


@pytest.mark.asyncio
async def test_application_role_still_cannot_delete_audit_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(session_factory)
    async with session_factory() as session:
        with pytest.raises(DBAPIError, match="audit_events is append-only"):
            await _delete(session, "audit_events", ids["old_event"])
        await session.rollback()
        with pytest.raises(DBAPIError, match="report_audit_events_append_only"):
            await _delete(session, "report_audit_events", ids["old_report_event"])
        await session.rollback()


@pytest.mark.asyncio
async def test_cleaner_role_deletes_only_expired_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(session_factory)
    async with session_factory() as session:
        await session.execute(text("SET LOCAL ROLE dih_retention_cleaner"))
        await _delete(session, "audit_events", ids["old_event"])
        await _delete(session, "report_audit_events", ids["old_report_event"])
        await session.commit()

    async with session_factory() as session:
        await session.execute(text("SET LOCAL ROLE dih_retention_cleaner"))
        with pytest.raises(DBAPIError, match="audit_events is append-only"):
            await _delete(session, "audit_events", ids["fresh_event"])
        await session.rollback()

    async with session_factory() as session:
        await session.execute(text("SET LOCAL ROLE dih_retention_cleaner"))
        with pytest.raises(DBAPIError, match="report_audit_events_append_only"):
            await _delete(session, "report_audit_events", ids["fresh_report_event"])
        await session.rollback()


@pytest.mark.asyncio
async def test_cleaner_role_cannot_update_audit_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(session_factory)
    async with session_factory() as session:
        await session.execute(text("SET LOCAL ROLE dih_retention_cleaner"))
        with pytest.raises(DBAPIError, match="audit_events is append-only"):
            await session.execute(
                text("UPDATE audit_events SET action = 'tamper' WHERE id = :id"),
                {"id": ids["update_event"]},
            )
        await session.rollback()

    async with session_factory() as session:
        await session.execute(text("SET LOCAL ROLE dih_retention_cleaner"))
        with pytest.raises(DBAPIError, match="report_audit_events_append_only"):
            await session.execute(
                text(
                    "UPDATE report_audit_events SET event_type = 'tamper' "
                    "WHERE id = :id"
                ),
                {"id": ids["fresh_report_event"]},
            )
        await session.rollback()
```

Run（只有本机有受控测试库时）：
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://localhost/c11_retention_cleaner_workflow_plan_phase2_test \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest tests/postgres/test_audit_retention_cleaner.py -v
```
Expected: `3 passed`。没有测试库时显示 `skipped`；发布前必须在受控库补跑。

- [ ] **Step 10: 跑迁移门禁**

Run against a scratch Postgres, not production:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run alembic heads
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: `heads` 只有 `202610220069 (head)`；upgrade、downgrade、upgrade 全部成功。`upgrade head` 需要迁移执行者具备 `CREATEROLE`，或 DBA 已创建 `dih_retention_cleaner` 并授予迁移执行者 `ADMIN OPTION`；迁移执行者还必须是 C2 `audit_events` 与 C9 `report_audit_events` 的属主，或对这两张表有 `GRANT OPTION`。

- [ ] **Step 11: 提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220069_pseudonymization_retention.py apps/api/src/data_intelligence_hub/models/retention.py apps/api/src/data_intelligence_hub/models/__init__.py apps/api/tests/unit/test_pseudonymization_retention_migration_source.py apps/api/tests/unit/test_retention_models.py apps/api/tests/postgres/test_audit_retention_cleaner.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(retention): 迁移 067 与伪名盐、法律保留、清理账本模型"
```

---

### Task 3: 工作区盐与伪名服务

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/pseudonymization.py`
- Test: `apps/api/tests/unit/test_pseudonymization.py`

**Interfaces:**
- Consumes: `WorkspacePseudonymSalt` 表。
- Produces:
  - `generate_workspace_salt() -> str`
  - `pseudonymize_identifier(salt_b64: str, namespace: str, value: str | None) -> str | None`
  - `get_or_create_workspace_salt(session: AsyncSession, workspace_id: uuid.UUID) -> WorkspacePseudonymSalt`
  - 常量 `PSEUDONYM_PREFIX = "psn_"`、`PSEUDONYM_ALGORITHM = "hmac-sha256.v1"`、`SALT_BYTES = 32`

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_pseudonymization.py`:
```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import Base, User, Workspace
from data_intelligence_hub.services.pseudonymization import (
    PSEUDONYM_PREFIX,
    generate_workspace_salt,
    get_or_create_workspace_salt,
    pseudonymize_identifier,
)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_workspace(session: AsyncSession) -> uuid.UUID:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="hash",
            name="Tester",
            status="active",
        )
    )
    session.add(
        Workspace(
            id=workspace_id,
            name="Workspace",
            slug=f"ws-{workspace_id}",
            owner_id=user_id,
        )
    )
    await session.flush()
    return workspace_id


def test_pseudonym_is_stable_and_idempotent() -> None:
    salt = generate_workspace_salt()
    first = pseudonymize_identifier(salt, "tiktok.comment_author", "alice")
    second = pseudonymize_identifier(salt, "tiktok.comment_author", "alice")
    assert first == second
    assert first is not None
    assert first.startswith(PSEUDONYM_PREFIX)
    assert "alice" not in first
    assert pseudonymize_identifier(salt, "tiktok.comment_author", first) == first


def test_different_namespaces_do_not_collide() -> None:
    salt = generate_workspace_salt()
    comment = pseudonymize_identifier(salt, "tiktok.comment_author", "alice")
    review = pseudonymize_identifier(salt, "tiktok.product_review_author", "alice")
    assert comment != review


def test_different_workspace_salts_are_unlinkable() -> None:
    first = pseudonymize_identifier(generate_workspace_salt(), "comment_author", "alice")
    second = pseudonymize_identifier(generate_workspace_salt(), "comment_author", "alice")
    assert first != second


@pytest.mark.asyncio
async def test_get_or_create_workspace_salt_is_stable(session: AsyncSession) -> None:
    workspace_id = await _seed_workspace(session)
    first = await get_or_create_workspace_salt(session, workspace_id)
    second = await get_or_create_workspace_salt(session, workspace_id)
    await session.commit()

    assert first.id == second.id
    assert first.workspace_id == workspace_id
    assert first.salt_version == "v1"
    assert len(first.salt_b64) >= 40
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization.py -v
```
Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.pseudonymization`。

- [ ] **Step 3: 实现伪名服务**

Create `apps/api/src/data_intelligence_hub/services/pseudonymization.py`:
```python
"""Workspace-scoped pseudonymization.

契约冻结 v1.1 §4.4：

- 同一工作区稳定。
- 跨工作区不可关联。
- 不提供反查映射。
- 盐不进入日志、导出、审计和错误。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.retention import WorkspacePseudonymSalt

PSEUDONYM_ALGORITHM = "hmac-sha256.v1"
PSEUDONYM_PREFIX = "psn_"
PSEUDONYM_TOKEN_LENGTH = 32
SALT_BYTES = 32
SALT_VERSION = "v1"


def generate_workspace_salt() -> str:
    raw = secrets.token_bytes(SALT_BYTES)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_salt(salt_b64: str) -> bytes:
    padding = "=" * (-len(salt_b64) % 4)
    return base64.urlsafe_b64decode(f"{salt_b64}{padding}")


def pseudonymize_identifier(
    salt_b64: str,
    namespace: str,
    value: str | None,
) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.startswith(PSEUDONYM_PREFIX):
        return normalized
    digest = hmac.new(
        _decode_salt(salt_b64),
        f"{namespace}\x1f{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = digest.hex()
    return f"{PSEUDONYM_PREFIX}{token[:PSEUDONYM_TOKEN_LENGTH]}"


async def get_or_create_workspace_salt(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspacePseudonymSalt:
    existing = await _select_salt(session, workspace_id)
    if existing is not None:
        return existing

    candidate = WorkspacePseudonymSalt(
        workspace_id=workspace_id,
        salt_version=SALT_VERSION,
        salt_b64=generate_workspace_salt(),
    )
    try:
        async with session.begin_nested():
            session.add(candidate)
            await session.flush()
    except IntegrityError:
        existing = await _select_salt(session, workspace_id)
        if existing is None:
            raise
        return existing
    return candidate


async def _select_salt(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspacePseudonymSalt | None:
    result = await session.execute(
        select(WorkspacePseudonymSalt).where(
            WorkspacePseudonymSalt.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization.py -v
```
Expected: PASS，5 passed。

- [ ] **Step 5: 跑静态检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run ruff check src/data_intelligence_hub/services/pseudonymization.py tests/unit/test_pseudonymization.py
uv run mypy src/data_intelligence_hub/services/pseudonymization.py
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/pseudonymization.py apps/api/tests/unit/test_pseudonymization.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(privacy): 工作区盐与 HMAC 伪名服务"
```

---

### Task 4: 导出策略纯函数

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/export_policy.py`
- Test: `apps/api/tests/unit/test_export_policy.py`

**Interfaces:**
- Consumes: `pseudonymize_identifier`。
- Produces:
  - `sanitize_source_url(url: str | None) -> str | None`
  - `mask_comment_text(value: str) -> str`
  - `apply_export_policy(rows: list[dict[str, object]], *, workspace_salt: str) -> list[dict[str, object]]`（保留既有行为，不改成扫描器）
  - `PiiHit(kind: Literal["contact", "profile_link", "avatar", "tracking"], field_path: str, start: int, end: int)`：只含命中类型、字段路径与偏移，绝不携带原始值
  - `EXPORT_POLICY_VERSION: Final[str] = "export_policy.v1"`
  - `scan_export_policy(text: str, field_path: str = "$") -> tuple[PiiHit, ...]`：扫描单段文本；contact 匹配跳过 UUID 与 ISO-8601 时间戳
  - `scan_export_value(value: object, field_path: str = "$") -> tuple[PiiHit, ...]`：递归扫描映射、列表与 URL 字符串
  - `__all__`：导出上述扫描 API 与既有遮蔽函数
  - 常量 `PII_MASK = "[redacted]"`、`PROFILE_LINK_MASK = "[redacted:profile_link]"`、`CONTACT_MASK = "[redacted:contact]"`、`LINK_MASK = "[redacted:link]"`、`AVATAR_MASK = "[redacted:avatar]"`
- 调用方契约：C9 `report_publication.scan_contract_pii` 扫描报告合同、claim 与两页 HTML 时调用 `scan_export_policy(text, field_path=...)`；C10 `services/delivery/pii.py` 扫描 manifest、bundle、HTML 与 claim bundle 时调用 `scan_export_value(value, field_path=...)`。C9/C10 只消费本节 API，不得复制正则、词表或自造第二套 PII 规则。C11 不提供任何旧扫描名称的兼容别名；C10 使用 `scan_export_value`、`PiiHit`、`EXPORT_POLICY_VERSION`，命中类型只取 `contact` / `profile_link` / `avatar` / `tracking` 四类，且不得记录原始值。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_export_policy.py`:
```python
from __future__ import annotations

from dataclasses import fields

from data_intelligence_hub.services.export_policy import (
    CONTACT_MASK,
    EXPORT_POLICY_VERSION,
    LINK_MASK,
    PROFILE_LINK_MASK,
    PiiHit,
    apply_export_policy,
    sanitize_source_url,
    scan_export_policy,
    scan_export_value,
)
from data_intelligence_hub.services.pseudonymization import generate_workspace_salt


def test_source_url_keeps_product_id_and_removes_tracking() -> None:
    url = (
        "https://www.amazon.com/dp/B000000001"
        "?utm_source=newsletter&th=1&fbclid=abc&gclid=def"
    )
    cleaned = sanitize_source_url(url)
    assert cleaned == "https://www.amazon.com/dp/B000000001?th=1"


def test_source_url_none_and_relative_are_unchanged() -> None:
    assert sanitize_source_url(None) is None
    assert sanitize_source_url("/local/path?utm_source=x") == "/local/path?utm_source=x"


def test_export_policy_masks_contacts_handles_and_comment_links() -> None:
    salt = generate_workspace_salt()
    rows = [
        {
            "source_url": "https://shop.example/p/1?utm_source=x&th=1",
            "values": {
                "reviewer_name_masked": "alice",
                "email": "alice@example.com",
                "text": "write me at alice@example.com or https://evil.example/x",
                "profile_url": "https://www.tiktok.com/@alice",
                "reviewer_avatar_url": "https://cdn.example/avatar.jpg",
                "brand_name": "Acme",
                "shop_handle": "@acme-shop",
                "creator_handle": "@acme-creator",
            },
        }
    ]
    masked = apply_export_policy(rows, workspace_salt=salt)
    values = masked[0]["values"]
    assert isinstance(values, dict)
    assert values["reviewer_name_masked"].startswith("psn_")
    assert "alice" not in values["reviewer_name_masked"]
    assert values["email"] == CONTACT_MASK
    assert CONTACT_MASK in values["text"]
    assert LINK_MASK in values["text"]
    assert "evil.example" not in values["text"]
    assert values["profile_url"] == PROFILE_LINK_MASK
    assert values["reviewer_avatar_url"] == "[redacted:avatar]"
    assert values["brand_name"] == "Acme"
    assert values["shop_handle"] == "@acme-shop"
    assert values["creator_handle"] == "@acme-creator"
    assert masked[0]["source_url"] == "https://shop.example/p/1?th=1"


def test_export_policy_is_idempotent() -> None:
    salt = generate_workspace_salt()
    rows = [
        {
            "source_url": "https://shop.example/p/1?utm_source=x",
            "values": {"author_unique_id": "bob", "email": "bob@example.com"},
        }
    ]
    once = apply_export_policy(rows, workspace_salt=salt)
    twice = apply_export_policy(once, workspace_salt=salt)
    assert once == twice


def test_cross_workspace_tokens_differ() -> None:
    rows = [{"source_url": None, "values": {"author_unique_id": "bob"}}]
    first = apply_export_policy(rows, workspace_salt=generate_workspace_salt())
    second = apply_export_policy(rows, workspace_salt=generate_workspace_salt())
    assert first[0]["values"]["author_unique_id"] != second[0]["values"]["author_unique_id"]


def test_scan_export_policy_reports_kinds_and_offsets_without_raw_values() -> None:
    text = "写邮件到 alice@example.com 或访问 https://www.tiktok.com/@alice?utm_source=x"
    hits = scan_export_policy(text, field_path="claims[0].text")

    assert {hit.kind for hit in hits} == {"contact", "profile_link", "tracking"}
    assert all(hit.field_path == "claims[0].text" for hit in hits)
    assert all(0 <= hit.start < hit.end <= len(text) for hit in hits)
    assert {field.name for field in fields(PiiHit)} == {
        "kind",
        "field_path",
        "start",
        "end",
    }
    assert "alice@example.com" not in repr(hits)
    assert "tiktok.com/@alice" not in repr(hits)


def test_scan_export_policy_uses_field_path_for_contact_and_avatar() -> None:
    avatar_url = "https://cdn.example/avatar.jpg"
    contact = scan_export_policy("alice", field_path="reviewer_email")
    avatar = scan_export_policy(avatar_url, field_path="reviewer_avatar_url")

    assert [(hit.kind, hit.start, hit.end) for hit in contact] == [
        ("contact", 0, len("alice"))
    ]
    assert [(hit.kind, hit.start, hit.end) for hit in avatar] == [
        ("avatar", 0, len(avatar_url))
    ]


def test_scan_export_policy_flags_tracking_but_not_plain_source_url() -> None:
    assert scan_export_policy("https://shop.example/p/1?th=1", field_path="source_url") == ()

    dirty = "https://shop.example/p/1?utm_source=x"
    hits = scan_export_policy(dirty, field_path="source_url")
    assert [(hit.kind, hit.start, hit.end) for hit in hits] == [
        ("tracking", 0, len(dirty))
    ]


def test_scan_export_policy_skips_uuid_and_iso_timestamp_contacts() -> None:
    text = (
        "22222222-2222-2222-2222-222222222222 "
        "22222222222222222222222222222222 "
        "2026-10-22T00:00:00Z "
        "+1 555 010 9999"
    )
    hits = scan_export_policy(text, field_path="decision.answer")

    assert [(hit.kind, text[hit.start:hit.end]) for hit in hits] == [
        ("contact", "+1 555 010 9999")
    ]


def test_scan_export_policy_serves_c9_report_and_html_callers() -> None:
    report_hits = scan_export_policy(
        "负责人邮箱 alice@example.com",
        field_path="decision.answer",
    )
    html_hits = scan_export_policy(
        '<p>联系 alice@example.com</p><a href="https://www.tiktok.com/@alice" >主页</a>',
        field_path="artifact.report_html",
    )

    assert [(hit.kind, hit.field_path) for hit in report_hits] == [
        ("contact", "decision.answer")
    ]
    assert ("contact", "artifact.report_html") in {
        (hit.kind, hit.field_path) for hit in html_hits
    }
    assert ("profile_link", "artifact.report_html") in {
        (hit.kind, hit.field_path) for hit in html_hits
    }


def test_scan_export_value_serves_c9_claim_and_c10_manifest_callers() -> None:
    claim_bundle = {
        "claims": [
            {"text": "买家邮箱 buyer@example.com", "counterevidence_text": "无"},
        ],
        "evidences": [
            {
                "excerpt": "见 https://www.instagram.com/@buyer",
                "url": "https://shop.example/p/1?utm_source=x",
            },
        ],
    }
    manifest = {
        "files": [
            {
                "path": "report.html",
                "reviewer_name_masked": "psn_x",
                "reviewer_avatar_url": "https://cdn.example/avatar.jpg",
            }
        ],
        "public_contract": {
            "decision": {"answer": "邮箱 buyer@example.com"},
        },
    }

    claim_hits = scan_export_value(claim_bundle, field_path="claim_bundle")
    manifest_hits = scan_export_value(manifest, field_path="manifest")

    claim_kinds = {(hit.kind, hit.field_path) for hit in claim_hits}
    manifest_kinds = {(hit.kind, hit.field_path) for hit in manifest_hits}
    assert ("contact", "claim_bundle.claims[0].text") in claim_kinds
    assert ("profile_link", "claim_bundle.evidences[0].excerpt") in claim_kinds
    assert ("tracking", "claim_bundle.evidences[0].url") in claim_kinds
    assert ("avatar", "manifest.files[0].reviewer_avatar_url") in manifest_kinds
    assert ("contact", "manifest.public_contract.decision.answer") in manifest_kinds


def test_scan_export_value_is_stable_and_never_returns_raw_values() -> None:
    value = {
        "texts": [
            "first alice@example.com",
            "second https://shop.example/p/1?utm_source=x",
        ],
        "count": 3,
        "empty": None,
    }
    first = scan_export_value(value, field_path="root")
    second = scan_export_value(value, field_path="root")

    assert first == second
    assert all(isinstance(hit, PiiHit) for hit in first)
    assert "alice@example.com" not in repr(first)
    assert "utm_source" not in repr(first)


def test_export_policy_scanner_is_exported_in_interfaces() -> None:
    import data_intelligence_hub.services.export_policy as export_policy

    assert EXPORT_POLICY_VERSION == "export_policy.v1"
    for name in (
        "PiiHit",
        "apply_export_policy",
        "scan_export_policy",
        "scan_export_value",
    ):
        assert name in export_policy.__all__
        assert callable(getattr(export_policy, name))
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_export_policy.py -v
```
Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.export_policy`。

- [ ] **Step 3: 实现导出策略**

Create `apps/api/src/data_intelligence_hub/services/export_policy.py`:
```python
"""Export-time PII policy.

契约冻结 v1.1 §4.4：

- 来源 URL 保留，只移除追踪参数。
- 联系方式、个人主页链接、评论正文外部链接、普通用户 handle 遮蔽。
- 品牌、店铺和商业创作者公开身份保留。
"""

from __future__ import annotations

import re
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from data_intelligence_hub.services.pseudonymization import pseudonymize_identifier

PII_MASK = "[redacted]"
PROFILE_LINK_MASK = "[redacted:profile_link]"
CONTACT_MASK = "[redacted:contact]"
LINK_MASK = "[redacted:link]"
AVATAR_MASK = "[redacted:avatar]"

EXPORT_POLICY_VERSION: Final[str] = "export_policy.v1"
PiiKind = Literal["contact", "profile_link", "avatar", "tracking"]
_IDENTIFIER_DELIMITERS = frozenset(" \t\r\n\"'`<>()[]{},;.?!&=/#")

__all__ = [
    "AVATAR_MASK",
    "CONTACT_MASK",
    "EXPORT_POLICY_VERSION",
    "LINK_MASK",
    "PII_MASK",
    "PROFILE_LINK_MASK",
    "PiiHit",
    "PiiKind",
    "apply_export_policy",
    "mask_comment_text",
    "sanitize_source_url",
    "scan_export_policy",
    "scan_export_value",
]


@dataclass(frozen=True, slots=True)
class PiiHit:
    """一个 PII 命中。只记录类型、字段路径与偏移，不携带原始值。"""

    kind: PiiKind
    field_path: str
    start: int
    end: int


TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "msclkid",
        "yclid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "si",
        "ref",
        "ref_src",
        "spm",
        "_ga",
        "_gl",
        "vero_id",
        "oly_anon_id",
        "oly_enc_id",
    }
)

CONTACT_PATTERN = re.compile(
    r"(?i)([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|\+?\d[\d\s().-]{7,}\d)"
)
URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
CONTACT_FIELD_PATTERN = re.compile(
    r"(?i)(^|_)(email|phone|mobile|contact|whatsapp|wechat|telegram)($|_)"
)
HANDLE_FIELD_PATTERN = re.compile(
    r"(?i)(handle|username|unique_id|nickname|author|reviewer|screen_name)"
)
PROFILE_FIELD_PATTERN = re.compile(r"(?i)(profile|homepage)")
AVATAR_FIELD_PATTERN = re.compile(r"(?i)avatar")
COMMENT_TEXT_FIELDS = frozenset(
    {"text", "comment_text", "review_text", "reply_text", "comment", "review"}
)
SOURCE_URL_FIELDS = frozenset(
    {"source_url", "canonical_url", "html_url", "url", "link", "feed_url"}
)
PRESERVED_IDENTITY_PREFIXES = ("brand_", "shop_", "creator_")
PROFILE_HOSTS = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "instagram.com",
        "www.instagram.com",
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
        "facebook.com",
        "www.facebook.com",
        "youtube.com",
        "www.youtube.com",
    }
)


def sanitize_source_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_key(key)
    ]
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=True),
            parts.fragment,
        )
    )


def _is_tracking_key(key: str) -> bool:
    lower = key.lower()
    return lower.startswith("utm_") or lower in TRACKING_QUERY_KEYS


def mask_comment_text(value: str) -> str:
    without_urls = URL_PATTERN.sub(LINK_MASK, value)
    return CONTACT_PATTERN.sub(CONTACT_MASK, without_urls)


def scan_export_policy(text: str, field_path: str = "$") -> tuple[PiiHit, ...]:
    """扫描一段文本，返回 PII 类型与偏移。

    复用本模块遮蔽规则使用的同一组正则、字段路径模式与主机清单，
    不新增第二套规则。``PiiHit`` 不含原始值。
    """
    if not text:
        return ()
    hits: list[PiiHit] = []
    leaf = _leaf_field(field_path)
    if AVATAR_FIELD_PATTERN.search(leaf):
        hits.append(PiiHit("avatar", field_path, 0, len(text)))
    elif CONTACT_FIELD_PATTERN.search(leaf) and not CONTACT_PATTERN.search(text):
        hits.append(PiiHit("contact", field_path, 0, len(text)))
    for match in CONTACT_PATTERN.finditer(_blank_identifiers(text)):
        hits.append(PiiHit("contact", field_path, match.start(), match.end()))
    for match in URL_PATTERN.finditer(text):
        url = match.group(0)
        if _has_tracking_parameters(url):
            hits.append(PiiHit("tracking", field_path, match.start(), match.end()))
        if _is_profile_url(url):
            hits.append(PiiHit("profile_link", field_path, match.start(), match.end()))
    return _sorted_unique_hits(hits)


def scan_export_value(value: object, field_path: str = "$") -> tuple[PiiHit, ...]:
    """递归扫描映射、列表与 URL 字符串；规则与 ``scan_export_policy`` 相同。"""
    if isinstance(value, str):
        return scan_export_policy(value, field_path)
    if isinstance(value, Mapping):
        hits: list[PiiHit] = []
        for key, item in value.items():
            hits.extend(scan_export_value(item, f"{field_path}.{key}"))
        return _sorted_unique_hits(hits)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        hits = []
        for index, item in enumerate(value):
            hits.extend(scan_export_value(item, f"{field_path}[{index}]"))
        return _sorted_unique_hits(hits)
    return ()


def _leaf_field(field_path: str) -> str:
    leaf = field_path.rsplit(".", 1)[-1]
    return leaf.split("[", 1)[0]


def _blank_identifiers(text: str) -> str:
    """把 UUID 与 ISO-8601 时间戳替换成等长空格，避免 contact 误报。"""
    blanked = list(text)
    index = 0
    while index < len(text):
        if text[index] in _IDENTIFIER_DELIMITERS:
            index += 1
            continue
        start = index
        while index < len(text) and text[index] not in _IDENTIFIER_DELIMITERS:
            index += 1
        token = text[start:index]
        if _looks_like_uuid(token) or _looks_like_iso8601(token):
            blanked[start:index] = [" "] * (index - start)
    return "".join(blanked)


def _looks_like_uuid(token: str) -> bool:
    compact = token.replace("-", "")
    if len(token) == 36:
        if token.count("-") != 4:
            return False
        if [len(part) for part in token.split("-")] != [8, 4, 4, 4, 12]:
            return False
    elif len(token) != 32:
        return False
    return all(char in string.hexdigits for char in compact)


def _looks_like_iso8601(token: str) -> bool:
    if "T" not in token and " " not in token:
        return False
    candidate = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _has_tracking_parameters(url: str) -> bool:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return False
    return any(
        _is_tracking_key(key)
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    )


def _sorted_unique_hits(hits: list[PiiHit]) -> tuple[PiiHit, ...]:
    unique = {
        (hit.field_path, hit.start, hit.end, hit.kind): hit
        for hit in hits
    }
    return tuple(unique[key] for key in sorted(unique))


def apply_export_policy(
    rows: list[dict[str, object]],
    *,
    workspace_salt: str,
) -> list[dict[str, object]]:
    masked_rows: list[dict[str, object]] = []
    for row in rows:
        copied = dict(row)
        values = copied.get("values")
        if isinstance(values, dict):
            copied["values"] = _mask_values(values, workspace_salt)
        raw_source_url = copied.get("source_url")
        copied["source_url"] = sanitize_source_url(
            raw_source_url if isinstance(raw_source_url, str) else None
        )
        masked_rows.append(copied)
    return masked_rows


def _mask_values(values: dict[str, Any], workspace_salt: str) -> dict[str, Any]:
    return {
        field: _mask_field(field, value, workspace_salt)
        for field, value in values.items()
    }


def _mask_field(field: str, value: Any, workspace_salt: str) -> Any:
    lower = field.lower()
    if lower in SOURCE_URL_FIELDS and isinstance(value, str):
        return sanitize_source_url(value)
    if lower in COMMENT_TEXT_FIELDS:
        if isinstance(value, str):
            return mask_comment_text(value)
        if isinstance(value, list):
            return [
                mask_comment_text(item) if isinstance(item, str) else item
                for item in value
            ]
    if AVATAR_FIELD_PATTERN.search(lower):
        return AVATAR_MASK if value is not None else None
    if CONTACT_FIELD_PATTERN.search(lower):
        return CONTACT_MASK if value is not None else None
    if _is_preserved_identity(lower):
        return value
    if (
        PROFILE_FIELD_PATTERN.search(lower)
        and isinstance(value, str)
        and _is_profile_url(value)
    ):
        return PROFILE_LINK_MASK
    if HANDLE_FIELD_PATTERN.search(lower):
        if isinstance(value, list):
            return [
                pseudonymize_identifier(workspace_salt, f"export.{lower}", _string(item))
                for item in value
            ]
        if isinstance(value, str):
            return pseudonymize_identifier(workspace_salt, f"export.{lower}", value)
    if isinstance(value, dict):
        return {
            key: _mask_field(key, item, workspace_salt)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_field(field, item, workspace_salt) for item in value]
    return value


def _is_preserved_identity(field: str) -> bool:
    return field.startswith(PRESERVED_IDENTITY_PREFIXES)


def _is_profile_url(value: str) -> bool:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        return False
    return parts.netloc.lower() in PROFILE_HOSTS and (
        parts.path.startswith("/@") or parts.path.count("/") == 1
    )


def _string(value: Any) -> str | None:
    return None if value is None else str(value)
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_export_policy.py -v
```
Expected: PASS，13 passed。既有 5 个遮蔽测试保持通过，新增 8 个扫描测试覆盖 C9 report/claim/html、C10 manifest 调用方形态，以及 UUID/ISO-8601 不误报。

- [ ] **Step 5: 提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/export_policy.py apps/api/tests/unit/test_export_policy.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(privacy): 导出 PII 遮蔽、只读扫描与来源 URL 去追踪参数"
```

---

### Task 5: 客户导出接缝与路由收敛

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/governed_dataset_export.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/automation.py`
- Test: `apps/api/tests/integration/test_governed_dataset_export.py`

**Interfaces:**
- Consumes: `apply_export_policy`、`get_or_create_workspace_salt`、C2 `require_project_access`、`append_audit_event`、`record_authorization_denial`、`Dataset`、`DatasetVersion`、`DatasetExportJob`、`AutomationProductDatasetExportCreateRequest`、`AutomationProductDatasetExportJobResponse`。
- Produces:
  - `create_governed_dataset_export(session, workspace, user, payload, idempotency_key=None, request_id=None) -> AutomationProductDatasetExportJobResponse`
  - `list_governed_dataset_exports(session, workspace, user, dataset_id, dataset_version_id=None, limit=20, request_id=None) -> AutomationProductDatasetExportListResponse`
  - `get_governed_dataset_export(session, workspace, user, export_job_id, request_id=None) -> AutomationProductDatasetExportJobResponse`
  - `get_governed_dataset_export_file(session, workspace, user, dataset_id, dataset_version_id, export_job_id, request_id=None) -> tuple[DatasetExportJob, Path]`
  - `_require_export_project_access(session, *, workspace, user, project_id, request_id=None) -> None`：调用 C2 项目 ACL；403 时写 `project.access.denied` 统一审计后重抛。
  - `assert_no_internal_isolated_sources(session, version) -> None`
  - `is_governed_export_job(job: DatasetExportJob) -> bool`
  - 常量 `GOVERNED_EXPORT_POLICY_VERSION = EXPORT_POLICY_VERSION`、`GOVERNED_EXPORT_IDEMPOTENCY_SCOPE = "governed_dataset_export"`、`INTERNAL_ISOLATED_ENDPOINT_TYPES`

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/integration/test_governed_dataset_export.py`:
```python
"""Governed dataset export: masking, URL policy and creator-cookie isolation."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import (
    AuditEvent,
    Base,
    CollectionTask,
    Dataset,
    DatasetExportJob,
    DatasetVersion,
    Project,
    ProjectMember,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.services.governed_dataset_export import (
    assert_no_internal_isolated_sources,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)

USER_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
SOURCE_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()
DATASET_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
LEGACY_JOB_ID = uuid.uuid4()
MEMBER_ID = uuid.uuid4()
OTHER_PROJECT_ID = uuid.uuid4()
OTHER_DATASET_ID = uuid.uuid4()
OTHER_VERSION_ID = uuid.uuid4()
OTHER_JOB_ID = uuid.uuid4()

SELECTED_FIELDS = [
    "title",
    "reviewer_name_masked",
    "email",
    "text",
    "brand_name",
    "creator_handle",
]


async def _seed(session: AsyncSession) -> None:
    session.add(
        User(
            id=USER_ID,
            email="owner@example.com",
            password_hash="hashed",
            name="Owner",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Workspace(
            id=WORKSPACE_ID,
            name="Demo",
            slug="data-achieve-demo",
            owner_id=USER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        WorkspaceMember(
            workspace_id=WORKSPACE_ID,
            user_id=USER_ID,
            role="owner",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Project(
            id=PROJECT_ID,
            workspace_id=WORKSPACE_ID,
            name="Project",
            description="demo",
            domain="ecommerce",
            status="active",
            owner_id=USER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Source(
            id=SOURCE_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            name="Source",
            type="tikhub_social",
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        CollectionTask(
            id=TASK_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            source_id=SOURCE_ID,
            collector_type="tikhub_social",
            name="Comments",
            schedule_cron=None,
            status="enabled",
            config={"endpoint_type": "tikhub_tiktok_comments_app"},
            success_count=1,
            failure_count=0,
            last_run_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        TaskRun(
            id=RUN_ID,
            task_id=TASK_ID,
            project_id=PROJECT_ID,
            workspace_id=WORKSPACE_ID,
            status="success",
            started_at=NOW,
            finished_at=NOW,
            records_count=1,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=NOW,
        )
    )
    session.add(
        Dataset(
            id=DATASET_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            name="Comments",
            dataset_type="ecommerce_product",
            status="active",
            description="demo",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        DatasetVersion(
            id=VERSION_ID,
            dataset_id=DATASET_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            created_by_user_id=USER_ID,
            cleaning_plan_id=None,
            source_workflow_run_id=None,
            lineage_contract_version=None,
            version_number=1,
            source_task_run_ids=[str(RUN_ID)],
            selected_fields=SELECTED_FIELDS,
            cleaning_script=[],
            rows=[
                {
                    "row_id": "row-1",
                    "task_run_id": str(RUN_ID),
                    "raw_record_id": str(uuid.uuid4()),
                    "source_url": (
                        "https://www.amazon.com/dp/B000000001"
                        "?utm_source=newsletter&th=1&fbclid=abc"
                    ),
                    "values": {
                        "title": "Product",
                        "reviewer_name_masked": "alice",
                        "email": "alice@example.com",
                        "text": "contact https://evil.example/x",
                        "brand_name": "Acme",
                        "creator_handle": "@acme-creator",
                    },
                    "missing_fields": [],
                    "completeness_percent": 100,
                }
            ],
            export_preview={"schema": {"title": "string"}},
            row_count=1,
            average_completeness_percent=100,
            status="saved",
            created_at=NOW,
        )
    )
    session.add(
        DatasetExportJob(
            id=LEGACY_JOB_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            dataset_id=DATASET_ID,
            dataset_version_id=VERSION_ID,
            created_by_user_id=USER_ID,
            export_format="csv",
            status="success",
            filename="legacy-unmasked.csv",
            content_type="text/csv; charset=utf-8",
            artifact_path="/tmp/legacy-unmasked.csv",
            artifact_size_bytes=1,
            row_count=1,
            checksum_sha256="0" * 64,
            error_message=None,
            audit_events=[],
            created_at=NOW,
            finished_at=NOW,
        )
    )
    session.add(
        User(
            id=MEMBER_ID,
            email="member@example.com",
            password_hash="hashed",
            name="Member",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        WorkspaceMember(
            workspace_id=WORKSPACE_ID,
            user_id=MEMBER_ID,
            role="member",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        ProjectMember(
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            user_id=MEMBER_ID,
            created_by_user_id=USER_ID,
            created_at=NOW,
        )
    )
    session.add(
        Project(
            id=OTHER_PROJECT_ID,
            workspace_id=WORKSPACE_ID,
            name="Other Project",
            description="other",
            domain="ecommerce",
            status="active",
            owner_id=USER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Dataset(
            id=OTHER_DATASET_ID,
            workspace_id=WORKSPACE_ID,
            project_id=OTHER_PROJECT_ID,
            name="Other Dataset",
            dataset_type="ecommerce_product",
            status="active",
            description="other",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        DatasetVersion(
            id=OTHER_VERSION_ID,
            dataset_id=OTHER_DATASET_ID,
            workspace_id=WORKSPACE_ID,
            project_id=OTHER_PROJECT_ID,
            created_by_user_id=USER_ID,
            cleaning_plan_id=None,
            source_workflow_run_id=None,
            lineage_contract_version=None,
            version_number=1,
            source_task_run_ids=[str(RUN_ID)],
            selected_fields=SELECTED_FIELDS,
            cleaning_script=[],
            rows=[],
            export_preview={"schema": {}},
            row_count=0,
            average_completeness_percent=100,
            status="saved",
            created_at=NOW,
        )
    )
    session.add(
        DatasetExportJob(
            id=OTHER_JOB_ID,
            workspace_id=WORKSPACE_ID,
            project_id=OTHER_PROJECT_ID,
            dataset_id=OTHER_DATASET_ID,
            dataset_version_id=OTHER_VERSION_ID,
            created_by_user_id=USER_ID,
            export_format="csv",
            status="success",
            filename="other.csv",
            content_type="text/csv; charset=utf-8",
            artifact_path="/tmp/other.csv",
            artifact_size_bytes=1,
            row_count=0,
            checksum_sha256="0" * 64,
            error_message=None,
            audit_events=[
                {
                    "event": "governed_dataset_export_requested",
                    "export_policy_version": "export_policy.v1",
                    "pii_masked": True,
                }
            ],
            created_at=NOW,
            finished_at=NOW,
        )
    )
    await session.commit()


@pytest_asyncio.fixture()
async def api_bundle(
    tmp_path_factory,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await _seed(session)

    async def override_session() -> AsyncGenerator[object, None]:
        async with factory() as session:
            yield session

    export_dir = tmp_path_factory.mktemp("governed-exports")
    settings = get_settings()
    original_export_dir = settings.dataset_export_dir
    original_rbac = settings.workspace_rbac_enforced
    settings.dataset_export_dir = str(export_dir)
    settings.workspace_rbac_enforced = False

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", create_access_token(USER_ID))
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        settings.dataset_export_dir = original_export_dir
        settings.workspace_rbac_enforced = original_rbac
        await engine.dispose()


@pytest_asyncio.fixture()
async def api(api_bundle) -> AsyncIterator[AsyncClient]:
    client, _factory = api_bundle
    yield client


async def test_export_masks_pii_and_tracking_params(api_bundle) -> None:
    api, factory = api_bundle
    response = await api.post(
        "/api/automation/product-dataset-exports",
        json={
            "authorized": True,
            "confirm_create": True,
            "dataset_id": str(DATASET_ID),
            "dataset_version_id": str(VERSION_ID),
            "export_format": "csv",
        },
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["status"] == "success"

    download = await api.get(job["download_url"])
    assert download.status_code == 200
    text = download.content.decode("utf-8")
    assert "psn_" in text
    assert "alice@example.com" not in text
    assert "reviewer_name_masked,alice" not in text
    assert "evil.example" not in text
    assert "utm_source" not in text
    assert "fbclid" not in text
    assert "https://www.amazon.com/dp/B000000001" in text
    assert "th=1" in text
    assert "Acme" in text
    assert "@acme-creator" in text

    async with factory() as session:
        events = list(
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.workspace_id == WORKSPACE_ID,
                        AuditEvent.action.in_(
                            ("dataset.export.created", "privacy.projection.applied")
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {event.action for event in events} == {
        "dataset.export.created",
        "privacy.projection.applied",
    }
    assert all(event.result == "success" for event in events)
    assert all(event.project_id == PROJECT_ID for event in events)


@pytest.mark.asyncio
async def test_legacy_unmasked_export_is_not_served(api: AsyncClient) -> None:
    response = await api.get(
        f"/api/automation/product-dataset-exports/{LEGACY_JOB_ID}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "dataset_export_not_found"


@pytest.mark.asyncio
async def test_creator_cookie_source_is_rejected() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await _seed(session)
        task = await session.get(CollectionTask, TASK_ID)
        assert task is not None
        task.config = {"endpoint_type": "tikhub_tiktok_creator_showcase"}
        version = await session.get(DatasetVersion, VERSION_ID)
        assert version is not None
        with pytest.raises(CollectorError, match="dataset_export_internal_isolated_source"):
            await assert_no_internal_isolated_sources(session, version)
    await engine.dispose()


@pytest.mark.asyncio
async def test_member_can_export_authorized_project(api_bundle) -> None:
    api, _factory = api_bundle
    settings = get_settings()
    original = settings.workspace_rbac_enforced
    settings.workspace_rbac_enforced = True
    try:
        api.cookies.set("access_token", create_access_token(MEMBER_ID))
        response = await api.post(
            "/api/automation/product-dataset-exports",
            json={
                "authorized": True,
                "confirm_create": True,
                "dataset_id": str(DATASET_ID),
                "dataset_version_id": str(VERSION_ID),
                "export_format": "csv",
            },
        )
        assert response.status_code == 200, response.text
    finally:
        settings.workspace_rbac_enforced = original


@pytest.mark.asyncio
async def test_same_workspace_cross_project_export_is_forbidden(api_bundle) -> None:
    api, factory = api_bundle
    settings = get_settings()
    original = settings.workspace_rbac_enforced
    settings.workspace_rbac_enforced = True
    try:
        api.cookies.set("access_token", create_access_token(MEMBER_ID))
        responses = [
            await api.post(
                "/api/automation/product-dataset-exports",
                json={
                    "authorized": True,
                    "confirm_create": True,
                    "dataset_id": str(OTHER_DATASET_ID),
                    "dataset_version_id": str(OTHER_VERSION_ID),
                    "export_format": "csv",
                },
            ),
            await api.get(
                f"/api/automation/product-datasets/{OTHER_DATASET_ID}/exports"
            ),
            await api.get(
                f"/api/automation/product-dataset-exports/{OTHER_JOB_ID}"
            ),
            await api.get(
                f"/api/automation/product-datasets/{OTHER_DATASET_ID}"
                f"/versions/{OTHER_VERSION_ID}/exports/{OTHER_JOB_ID}/download"
            ),
        ]
        for response in responses:
            assert response.status_code == 403, response.text
            assert response.json()["error"]["code"] == "project_access_forbidden"
    finally:
        settings.workspace_rbac_enforced = original

    async with factory() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.workspace_id == WORKSPACE_ID,
                        AuditEvent.action == "project.access.denied",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 4
    assert {row.result for row in rows} == {"denied"}
    assert {row.project_id for row in rows} == {OTHER_PROJECT_ID}
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/integration/test_governed_dataset_export.py -v
```
Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.governed_dataset_export`。

- [ ] **Step 3: 实现接缝**

Create `apps/api/src/data_intelligence_hub/services/governed_dataset_export.py`:
```python
"""Customer dataset export seam.

这是客户导出唯一入口。旧 `automation_service` 导出函数保留给内部隔离链，
不得再被客户路由调用。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models import (
    CollectionTask,
    Dataset,
    DatasetExportJob,
    DatasetVersion,
    TaskRun,
    User,
    Workspace,
)
from data_intelligence_hub.repositories.datasets import (
    create_dataset_export_job,
    get_dataset,
    get_dataset_export_job,
    get_dataset_export_job_by_id,
    get_dataset_version,
    list_dataset_export_jobs,
)
from data_intelligence_hub.schemas.automation import (
    AutomationDatasetResponse,
    AutomationDatasetVersionResponse,
    AutomationProductDatasetExportCreateRequest,
    AutomationProductDatasetExportJobResponse,
    AutomationProductDatasetExportListResponse,
)
from data_intelligence_hub.services.audit_log import (
    append_audit_event,
    record_authorization_denial,
)
from data_intelligence_hub.services.export_policy import (
    EXPORT_POLICY_VERSION,
    apply_export_policy,
)
from data_intelligence_hub.services.pseudonymization import get_or_create_workspace_salt

GOVERNED_EXPORT_POLICY_VERSION = EXPORT_POLICY_VERSION
GOVERNED_EXPORT_IDEMPOTENCY_SCOPE = "governed_dataset_export"
DATASET_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
INTERNAL_ISOLATED_ENDPOINT_TYPES = frozenset(
    {
        "tikhub_tiktok_video_products",
        "tikhub_tiktok_creator_showcase",
    }
)
EXPORT_FIELDS = (
    "row_id",
    "source_url",
    "task_run_id",
    "raw_record_id",
    "missing_fields",
    "completeness_percent",
)


def is_governed_export_job(job: DatasetExportJob) -> bool:
    for event in job.audit_events:
        if event.get("export_policy_version") != GOVERNED_EXPORT_POLICY_VERSION:
            continue
        if event.get("pii_masked") is True:
            return True
    return False


async def _require_export_project_access(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    project_id: uuid.UUID,
    request_id: str | None = None,
) -> None:
    """项目 ACL 唯一接缝。403 时写统一审计，再抛出原错误。"""

    try:
        await require_project_access(
            session,
            workspace=workspace,
            user=user,
            project_id=project_id,
            manage=False,
        )
    except APIError as exc:
        if exc.status_code == 403:
            await record_authorization_denial(
                session,
                workspace_id=workspace.id,
                project_id=project_id,
                actor_user_id=user.id,
                action="project.access.denied",
                resource_type="project",
                resource_id=str(project_id),
                request_id=request_id,
                code=exc.code,
            )
        raise


async def assert_no_internal_isolated_sources(
    session: AsyncSession,
    version: DatasetVersion,
) -> None:
    run_ids: list[uuid.UUID] = []
    for value in version.source_task_run_ids:
        try:
            run_ids.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    if not run_ids:
        return
    result = await session.execute(
        select(TaskRun.id, CollectionTask.config)
        .join(CollectionTask, CollectionTask.id == TaskRun.task_id)
        .where(TaskRun.id.in_(run_ids))
    )
    for _, config in result.all():
        endpoint_type = (config or {}).get("endpoint_type")
        if endpoint_type in INTERNAL_ISOLATED_ENDPOINT_TYPES:
            raise CollectorError("dataset_export_internal_isolated_source")


async def create_governed_dataset_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationProductDatasetExportCreateRequest,
    idempotency_key: str | None = None,
    request_id: str | None = None,
) -> AutomationProductDatasetExportJobResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("dataset_export_confirmation_required")

    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    await _require_export_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=dataset.project_id,
        request_id=request_id,
    )
    await assert_no_internal_isolated_sources(session, version)

    export_format = payload.export_format
    idempotency_key_hash = _idempotency_key_hash(
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        export_format=export_format,
        idempotency_key=idempotency_key,
    )
    if idempotency_key_hash is not None:
        existing = await _existing_governed_job(
            session=session,
            workspace=workspace,
            dataset_id=dataset.id,
            dataset_version_id=version.id,
            export_format=export_format,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing is not None:
            return _job_response(
                existing,
                dataset,
                version,
                idempotency_replayed=True,
                idempotency_key_hash=idempotency_key_hash,
            )

    salt = await get_or_create_workspace_salt(session, workspace.id)
    rows = apply_export_policy(_dataset_export_rows(version), workspace_salt=salt.salt_b64)
    content = _render_export(dataset, version, export_format, rows)

    job_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    filename = _export_filename(dataset, version, job_id, export_format)
    target_path = _export_path(
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        version_id=version.id,
        filename=filename,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f"{target_path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(target_path)

    checksum = hashlib.sha256(content).hexdigest()
    audit_events: list[dict[str, Any]] = [
        {
            "event": "governed_dataset_export_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "export_format": export_format,
            "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
            "pii_masked": True,
            "source_url_tracking_removed": True,
            "pseudonym_salt_version": salt.salt_version,
            "pseudonym_salt_recorded": False,
        }
    ]
    if idempotency_key_hash is not None:
        audit_events.append(
            {
                "event": "governed_dataset_export_idempotency_key_recorded",
                "scope": GOVERNED_EXPORT_IDEMPOTENCY_SCOPE,
                "idempotency_key_hash": idempotency_key_hash,
                "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
                "raw_key_stored": False,
            }
        )
    audit_events.append(
        {
            "event": "governed_dataset_export_file_written",
            "artifact_size_bytes": len(content),
            "checksum_sha256": checksum,
            "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
            "pii_masked": True,
        }
    )

    job = DatasetExportJob(
        id=job_id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        created_by_user_id=user.id,
        export_format=export_format,
        status="success",
        filename=filename,
        content_type=DATASET_EXPORT_CONTENT_TYPES[export_format],
        artifact_path=str(target_path),
        artifact_size_bytes=len(content),
        row_count=version.row_count,
        checksum_sha256=checksum,
        error_message=None,
        audit_events=audit_events,
        created_at=created_at,
        finished_at=datetime.now(UTC),
    )
    created = await create_dataset_export_job(session, job)
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        actor_user_id=user.id,
        action="dataset.export.created",
        resource_type="dataset_export_job",
        resource_id=str(created.id),
        request_id=request_id,
        result="success",
        details={
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "export_format": export_format,
            "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
            "pii_masked": True,
            "pseudonymized": True,
            "source_url_tracking_removed": True,
        },
    )
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        actor_user_id=user.id,
        action="privacy.projection.applied",
        resource_type="dataset_version",
        resource_id=str(version.id),
        request_id=request_id,
        result="success",
        details={
            "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
            "pii_masked": True,
            "pseudonymized": True,
            "source_url_tracking_removed": True,
        },
    )
    await session.commit()
    return _job_response(
        created,
        dataset,
        version,
        idempotency_key_hash=idempotency_key_hash,
    )


async def list_governed_dataset_exports(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
    request_id: str | None = None,
) -> AutomationProductDatasetExportListResponse:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    await _require_export_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=dataset.project_id,
        request_id=request_id,
    )
    if dataset_version_id is not None:
        version = await get_dataset_version(
            session,
            workspace.id,
            dataset.id,
            dataset_version_id,
        )
        if version is None:
            raise CollectorError("dataset_version_not_found")
    jobs = await list_dataset_export_jobs(
        session,
        workspace.id,
        dataset.id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )
    items: list[AutomationProductDatasetExportJobResponse] = []
    for job in jobs:
        if not is_governed_export_job(job):
            continue
        version = await get_dataset_version(
            session,
            workspace.id,
            job.dataset_id,
            job.dataset_version_id,
        )
        if version is None:
            continue
        items.append(_job_response(job, dataset, version))
    return AutomationProductDatasetExportListResponse(
        items=items,
        total=len(items),
        export_created=False,
        run_started=False,
    )


async def get_governed_dataset_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    export_job_id: uuid.UUID,
    request_id: str | None = None,
) -> AutomationProductDatasetExportJobResponse:
    job = await get_dataset_export_job_by_id(session, workspace.id, export_job_id)
    if job is None or not is_governed_export_job(job):
        raise CollectorError("dataset_export_not_found")
    dataset = await get_dataset(session, workspace.id, job.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    await _require_export_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=dataset.project_id,
        request_id=request_id,
    )
    version = await get_dataset_version(
        session,
        workspace.id,
        job.dataset_id,
        job.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    return _job_response(job, dataset, version)


async def get_governed_dataset_export_file(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    export_job_id: uuid.UUID,
    request_id: str | None = None,
) -> tuple[DatasetExportJob, Path]:
    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        dataset_id,
        dataset_version_id,
    )
    await _require_export_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=dataset.project_id,
        request_id=request_id,
    )
    job = await get_dataset_export_job(
        session,
        workspace.id,
        dataset.id,
        version.id,
        export_job_id,
    )
    if job is None:
        raise CollectorError("dataset_export_not_found")
    if not is_governed_export_job(job):
        raise CollectorError("dataset_export_not_found")
    if job.status != "success":
        raise CollectorError("dataset_export_not_ready")
    artifact_path = Path(job.artifact_path).resolve()
    export_root = _export_root()
    try:
        artifact_path.relative_to(export_root)
    except ValueError as exc:
        raise CollectorError("dataset_export_artifact_outside_root") from exc
    if not artifact_path.is_file():
        raise CollectorError("dataset_export_file_missing")
    return job, artifact_path


async def _get_dataset_and_version(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> tuple[Dataset, DatasetVersion]:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(session, workspace.id, dataset.id, version_id)
    if version is None:
        raise CollectorError("dataset_version_not_found")
    return dataset, version


def _dataset_export_rows(version: DatasetVersion) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for saved_row in version.rows:
        values = saved_row.get("values") if isinstance(saved_row, dict) else None
        if not isinstance(values, dict):
            values = {}
        row: dict[str, object] = {
            field: values.get(field) for field in version.selected_fields
        }
        row["row_id"] = saved_row.get("row_id")
        row["source_url"] = saved_row.get("source_url")
        row["task_run_id"] = saved_row.get("task_run_id")
        row["raw_record_id"] = saved_row.get("raw_record_id")
        row["missing_fields"] = saved_row.get("missing_fields", [])
        row["completeness_percent"] = saved_row.get("completeness_percent")
        rows.append(row)
    return rows


def _render_export(
    dataset: Dataset,
    version: DatasetVersion,
    export_format: str,
    rows: list[dict[str, object]],
) -> bytes:
    if export_format == "csv":
        return _render_csv(version, rows)
    if export_format == "jsonl":
        lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
        return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    if export_format == "xlsx":
        return _render_xlsx(version, rows)
    payload = {
        "dataset": {
            "id": str(dataset.id),
            "project_id": str(dataset.project_id),
            "name": dataset.name,
            "dataset_type": dataset.dataset_type,
        },
        "version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "selected_fields": version.selected_fields,
            "row_count": version.row_count,
            "average_completeness_percent": version.average_completeness_percent,
            "created_at": version.created_at.isoformat(),
        },
        "schema": version.export_preview.get("schema", {}),
        "rows": rows,
        "export_policy_version": GOVERNED_EXPORT_POLICY_VERSION,
        "pii_masked": True,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _fieldnames(version: DatasetVersion) -> list[str]:
    return [*version.selected_fields, *EXPORT_FIELDS]


def _render_csv(version: DatasetVersion, rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO()
    fieldnames = _fieldnames(version)
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    return stream.getvalue().encode("utf-8")


def _csv_value(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _render_xlsx(version: DatasetVersion, rows: list[dict[str, object]]) -> bytes:
    from openpyxl import Workbook

    fieldnames = _fieldnames(version)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = f"v{version.version_number}"[:31]
    worksheet.append(fieldnames)
    for row in rows:
        worksheet.append([_xlsx_value(row.get(field)) for field in fieldnames])
    worksheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _xlsx_value(value: object) -> str | int | float | bool | None:
    converted = _csv_value(value)
    if isinstance(converted, str) and len(converted) > 32767:
        return converted[:32760] + "…"
    return converted


def _export_root() -> Path:
    return Path(get_settings().dataset_export_dir).expanduser().resolve()


def _export_path(
    *,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    filename: str,
) -> Path:
    return (
        _export_root()
        / str(workspace_id)
        / str(dataset_id)
        / str(version_id)
        / filename
    ).resolve()


def _export_filename(
    dataset: Dataset,
    version: DatasetVersion,
    job_id: uuid.UUID,
    export_format: str,
) -> str:
    return (
        f"{_slug(dataset.name)}-v{version.version_number}-"
        f"{str(job_id)[:8]}.{export_format}"
    )


def _slug(value: str) -> str:
    characters: list[str] = []
    for character in value.lower():
        if character.isalnum():
            characters.append(character)
        elif characters and characters[-1] != "-":
            characters.append("-")
    return "".join(characters).strip("-")[:80] or "dataset"


def _idempotency_key_hash(
    *,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    export_format: str,
    idempotency_key: str | None,
) -> str | None:
    if idempotency_key is None:
        return None
    normalized = idempotency_key.strip()
    if not normalized:
        return None
    payload = {
        "scope": GOVERNED_EXPORT_IDEMPOTENCY_SCOPE,
        "workspace_id": str(workspace_id),
        "dataset_id": str(dataset_id),
        "dataset_version_id": str(dataset_version_id),
        "export_format": export_format,
        "idempotency_key": normalized,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


async def _existing_governed_job(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    export_format: str,
    idempotency_key_hash: str,
) -> DatasetExportJob | None:
    jobs = await list_dataset_export_jobs(
        session,
        workspace.id,
        dataset_id,
        dataset_version_id=dataset_version_id,
        limit=100,
    )
    for job in jobs:
        if job.export_format != export_format:
            continue
        for event in job.audit_events:
            if event.get("event") != "governed_dataset_export_idempotency_key_recorded":
                continue
            if event.get("scope") != GOVERNED_EXPORT_IDEMPOTENCY_SCOPE:
                continue
            if event.get("export_policy_version") != GOVERNED_EXPORT_POLICY_VERSION:
                continue
            if event.get("idempotency_key_hash") == idempotency_key_hash:
                return job
    return None


def _job_response(
    job: DatasetExportJob,
    dataset: Dataset,
    version: DatasetVersion,
    *,
    idempotency_replayed: bool = False,
    idempotency_key_hash: str | None = None,
) -> AutomationProductDatasetExportJobResponse:
    detected_hash = idempotency_key_hash
    if detected_hash is None:
        for event in job.audit_events:
            if event.get("event") != "governed_dataset_export_idempotency_key_recorded":
                continue
            if event.get("scope") == GOVERNED_EXPORT_IDEMPOTENCY_SCOPE:
                value = event.get("idempotency_key_hash")
                if isinstance(value, str) and value:
                    detected_hash = value
                    break
    download_url = None
    if job.status == "success":
        download_url = (
            f"/api/automation/product-datasets/{dataset.id}/versions/{version.id}"
            f"/exports/{job.id}/download"
        )
    return AutomationProductDatasetExportJobResponse(
        id=job.id,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            cleaning_plan_id=version.cleaning_plan_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            source_workflow_run_id=version.source_workflow_run_id,
            source_workflow_step_run_ids=version.source_workflow_step_run_ids,
            source_raw_record_ids=version.source_raw_record_ids,
            lineage_contract_version=version.lineage_contract_version,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        export_format=job.export_format,
        status=job.status,
        filename=job.filename,
        content_type=job.content_type,
        artifact_size_bytes=job.artifact_size_bytes,
        row_count=job.row_count,
        checksum_sha256=job.checksum_sha256,
        error_message=job.error_message,
        created_at=job.created_at,
        finished_at=job.finished_at,
        download_url=download_url,
        audit_events=job.audit_events,
        blocked_reasons=[
            "导出已按工作区伪名、PII 遮蔽和来源 URL 去追踪参数策略生成。"
        ],
        idempotency_replayed=idempotency_replayed,
        idempotency_scope=(
            GOVERNED_EXPORT_IDEMPOTENCY_SCOPE if detected_hash else None
        ),
        idempotency_key_hash=detected_hash,
    )
```

- [ ] **Step 4: 改路由导入、请求 ID 与四个调用点**

Modify `apps/api/src/data_intelligence_hub/api/routes/automation.py`:
- Remove from the `automation_service` import block:
```python
    create_product_dataset_export,
    get_product_dataset_export,
    get_product_dataset_export_file,
    list_product_dataset_exports,
```
- 在既有的 `data_intelligence_hub.api.deps` 导入块加入 `RequestIdDep`，不新建重复导入。
- Add after the `automation_service` import block:
```python
from data_intelligence_hub.services.governed_dataset_export import (
    create_governed_dataset_export,
    get_governed_dataset_export,
    get_governed_dataset_export_file,
    list_governed_dataset_exports,
)
```
- Add `request_id: RequestIdDep` to the four route signatures，并透传 `context.user` 与 `request_id`。创建路由保持 `get_authenticated_context`，其余三个保持 `get_auth_context`。
```python
        return await create_governed_dataset_export(
            session,
            context.workspace,
            context.user,
            payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
```
```python
        return await get_governed_dataset_export(
            session,
            context.workspace,
            context.user,
            export_job_id,
            request_id=request_id,
        )
```
```python
        return await list_governed_dataset_exports(
            session,
            context.workspace,
            context.user,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            limit=limit,
            request_id=request_id,
        )
```
```python
        export_job, artifact_path = await get_governed_dataset_export_file(
            session,
            context.workspace,
            context.user,
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            export_job_id=export_job_id,
            request_id=request_id,
        )
```

- [ ] **Step 5: 运行导出测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/integration/test_governed_dataset_export.py tests/integration/test_dataset_export_preview.py -v
```
Expected: PASS。新测试 6 passed；覆盖 owner 允许、member 已授权项目允许、同工作区跨项目 403、导出 allow/deny 审计与既有导出回归。

- [ ] **Step 6: 确认冻结文件未改并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
git diff --name-only | grep -c "services/automation_service.py"
```
Expected: `0`。

Run:
```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/governed_dataset_export.py apps/api/src/data_intelligence_hub/api/routes/automation.py apps/api/tests/integration/test_governed_dataset_export.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(export): 客户导出接缝应用伪名与 PII 策略"
```

---

### Task 6: 规范化阶段写入评论者伪名

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py`
- Modify: `apps/api/tests/unit/test_tiktok_content_ingestion.py`（TABLES 加盐表）
- Modify: `apps/api/tests/unit/test_tiktok_commerce_ingestion.py`（TABLES 加盐表）
- Modify: `apps/api/tests/unit/test_tiktok_content_backfill.py`（TABLES 加盐表）
- Test: `apps/api/tests/unit/test_tiktok_ingestion_pseudonymization.py`

**Interfaces:**
- Consumes: `get_or_create_workspace_salt`、`pseudonymize_identifier`。
- Produces:
  - `IngestionContext.pseudonym_salt: str | None = None`
  - 评论表 `author_unique_id` 与 `author_nickname` 写同一伪名 token。
  - 商品评论 `reviewer_name_masked` 写伪名 token；`reviewer_avatar_url` 写 `None`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_tiktok_ingestion_pseudonymization.py`:
```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import Base, ProductReview, Project, User, Workspace
from data_intelligence_hub.models.tiktok_content import Comment
from data_intelligence_hub.services.tiktok_content_ingestion import (
    IngestionContext,
    ingest_tiktok_content,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
TABLES = [
    "users",
    "workspaces",
    "projects",
    "workspace_pseudonym_salts",
    "creator",
    "video",
    "comment",
    "comment_snapshot",
    "product_review",
]


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables[name] for name in TABLES]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=tables,
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_tenant(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="hash",
            name="Tester",
            status="active",
        )
    )
    session.add(
        Workspace(
            id=workspace_id,
            name="TikTok",
            slug=f"tiktok-{workspace_id}",
            owner_id=user_id,
        )
    )
    session.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="Content",
            domain="tiktok",
            status="active",
            owner_id=user_id,
        )
    )
    await session.commit()
    return workspace_id, project_id


def _context(workspace_id: uuid.UUID, project_id: uuid.UUID) -> IngestionContext:
    return IngestionContext(
        workspace_id=workspace_id,
        project_id=project_id,
        endpoint_type="tikhub_tiktok_comments_app",
        schema_version="tikhub_tiktok_comment.v1",
        captured_at=NOW,
        country_code="US",
        period_days=7,
        time_window="7d",
        language="en",
    )


def _comment(comment_id: str, author: str = "alice") -> dict:
    return {
        "record_type": "tiktok_comment",
        "provider": "tikhub",
        "schema_version": "tikhub_tiktok_comment.v1",
        "comment_id": comment_id,
        "video_id": f"video-{comment_id}",
        "author_id": "u1",
        "author_unique_id": author,
        "author_nickname": author.title(),
        "text": "nice",
        "text_language": "en",
        "like_count": 1,
        "reply_count": 0,
        "is_pinned": False,
        "creator_interacted": False,
        "published_at": "2026-10-22T11:30:00+00:00",
    }


@pytest.mark.asyncio
async def test_comment_author_is_workspace_scoped_pseudonym(
    session: AsyncSession,
) -> None:
    ws1, project1 = await _seed_tenant(session)
    ws2, project2 = await _seed_tenant(session)

    await ingest_tiktok_content(session, [_comment("c1")], _context(ws1, project1))
    await ingest_tiktok_content(session, [_comment("c2")], _context(ws1, project1))
    await ingest_tiktok_content(session, [_comment("c3")], _context(ws2, project2))
    await session.commit()

    first = await session.get(Comment, "c1")
    second = await session.get(Comment, "c2")
    other = await session.get(Comment, "c3")
    assert first is not None and second is not None and other is not None
    assert first.author_unique_id is not None
    assert first.author_unique_id.startswith("psn_")
    assert first.author_unique_id == first.author_nickname
    assert first.author_unique_id == second.author_unique_id
    assert "alice" not in first.author_unique_id.lower()
    assert other.author_unique_id != first.author_unique_id


@pytest.mark.asyncio
async def test_product_reviewer_is_pseudonymized(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_product_review",
        "provider": "tikhub",
        "schema_version": "tikhub_tiktok_commerce.v1",
        "review_id": "r1",
        "product_id": "p1",
        "region": "US",
        "rating": 5,
        "reviewer_name": "Bob",
        "reviewer_avatar_url": "https://cdn.example/bob.jpg",
        "text": "good",
    }
    await ingest_tiktok_content(session, [content], _context(workspace_id, project_id))
    await session.commit()

    review = await session.get(ProductReview, "r1")
    assert review is not None
    assert review.reviewer_name_masked is not None
    assert review.reviewer_name_masked.startswith("psn_")
    assert "bob" not in review.reviewer_name_masked.lower()
    assert review.reviewer_avatar_url is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_tiktok_ingestion_pseudonymization.py -v
```
Expected: FAIL。评论 `author_unique_id` 仍是 `alice`，`reviewer_name_masked` 仍是 `Bob`。

- [ ] **Step 3: 改 ingestion**

Modify `apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py`:

1. Change the dataclasses import:
```python
from dataclasses import dataclass, field, replace
```

2. Add imports:
```python
from data_intelligence_hub.services.pseudonymization import (
    get_or_create_workspace_salt,
    pseudonymize_identifier,
)
```

3. Add `pseudonym_salt` to `IngestionContext` after `language`:
```python
    pseudonym_salt: str | None = None
```

4. In `ingest_tiktok_content`, before `result = IngestionResult()`:
```python
    if context.pseudonym_salt is None:
        salt = await get_or_create_workspace_salt(session, context.workspace_id)
        context = replace(context, pseudonym_salt=salt.salt_b64)
```

5. Add helper before `_ingest_comment`:
```python
def _pseudonymize_actor(
    context: IngestionContext,
    namespace: str,
    value: object,
) -> str | None:
    if value is None:
        return None
    assert context.pseudonym_salt is not None
    return pseudonymize_identifier(context.pseudonym_salt, namespace, str(value))
```

6. Replace the comment author values in `_ingest_comment`:
```python
            "author_unique_id": _pseudonymize_actor(
                context,
                "tiktok.comment_author",
                content.get("author_unique_id") or content.get("author_nickname"),
            ),
            "author_nickname": _pseudonymize_actor(
                context,
                "tiktok.comment_author",
                content.get("author_unique_id") or content.get("author_nickname"),
            ),
```

7. Replace the product review PII values in `_ingest_product_review`:
```python
            "reviewer_name_masked": _pseudonymize_actor(
                context,
                "tiktok.product_review_author",
                _pick(content, "reviewer_name_masked", "reviewer_name"),
            ),
            "reviewer_avatar_url": None,
```

8. Add `"workspace_pseudonym_salts"` to the `TABLES` list in:
- `apps/api/tests/unit/test_tiktok_content_ingestion.py`
- `apps/api/tests/unit/test_tiktok_commerce_ingestion.py`
- `apps/api/tests/unit/test_tiktok_content_backfill.py`

- [ ] **Step 4: 运行新测试与回归**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_tiktok_ingestion_pseudonymization.py tests/unit/test_tiktok_content_ingestion.py tests/unit/test_tiktok_commerce_ingestion.py tests/unit/test_tiktok_content_backfill.py -v
```
Expected: PASS。新测试 2 passed，既有 ingestion 与 backfill 测试全部通过。

- [ ] **Step 5: 复跑 HIGH 风险影响面测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_tiktok_tools.py tests/unit/test_quick_collect_service.py -q
```
Expected: PASS。若文件不存在，改用 `rg --files tests | rg "quick_collect|tiktok_tools"` 找到对应测试并运行；不得跳过。

- [ ] **Step 6: 静态检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run ruff check src/data_intelligence_hub/services/tiktok_content_ingestion.py tests/unit/test_tiktok_ingestion_pseudonymization.py
uv run mypy src/data_intelligence_hub/services/tiktok_content_ingestion.py
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/tiktok_content_ingestion.py apps/api/tests/unit/test_tiktok_ingestion_pseudonymization.py apps/api/tests/unit/test_tiktok_content_ingestion.py apps/api/tests/unit/test_tiktok_commerce_ingestion.py apps/api/tests/unit/test_tiktok_content_backfill.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(privacy): 评论者与评论作者在规范化阶段写入工作区伪名"
```

---

### Task 7: 保留策略常量与法律保留服务

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/retention_policy.py`
- Create: `apps/api/src/data_intelligence_hub/services/legal_hold_service.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/.env.example`
- Modify: `configs/deploy/scrapy/docker-compose.yml`
- Test: `apps/api/tests/unit/test_retention_policy.py`
- Test: `apps/api/tests/unit/test_retention_deploy_facts.py`
- Test: `apps/api/tests/unit/test_legal_hold_service.py`

**Interfaces:**
- Consumes: `LegalHold`、`Project`。
- Produces:
  - `RETENTION_POLICY_VERSION = "retention_policy.v1"`
  - `RETENTION_TTL_DAYS: dict[str, int]`
  - `RETENTION_POLICIES: tuple[RetentionPolicy, ...]`
  - `policy_by_class(data_class: str) -> RetentionPolicy`
  - `policy_snapshot() -> list[dict[str, object]]`
  - `hold_applies(hold, *, workspace_id, project_id, data_class) -> bool`
  - `create_legal_hold(...) -> LegalHold`：成功后写 `legal_hold.created` 统一审计。
  - `release_legal_hold(...) -> LegalHold`：成功后写 `legal_hold.released` 统一审计。
  - `list_active_legal_holds(session, *, workspace_id) -> list[LegalHold]`

- [ ] **Step 1: 登记专用保留角色配置、环境变量示例与共享 compose 映射**

在 `apps/api/src/data_intelligence_hub/core/config.py` 的 `Settings` 中追加：

```python
    retention_cleaner_role: str = "dih_retention_cleaner"
    retention_cleanup_enabled: bool = False
```

该字段只允许数据库角色名，不允许环境变量改写为应用角色。迁移 067 在角色不存在时创建同名 `NOLOGIN` 角色，授予审计表 `DELETE` 权限，并授予迁移执行者成员关系；DBA 也可以在生产迁移前预先创建角色并授予 `ADMIN OPTION`。

在 `apps/api/.env.example` 追加：

```dotenv
RETENTION_CLEANUP_ENABLED=false
RETENTION_CLEANER_ROLE=dih_retention_cleaner
```

在 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 段追加两行静态映射：

```yaml
      RETENTION_CLEANUP_ENABLED: ${RETENTION_CLEANUP_ENABLED:-false}
      RETENTION_CLEANER_ROLE: ${RETENTION_CLEANER_ROLE:-dih_retention_cleaner}
```

共享 compose 是生产 A 与 B 的权威文件。C11 只追加映射键，不设置生产值，不改 `configs/deploy/scrapy-new/**`。PG0 发布负责人只改 `.env.production` 的值并重启 api；C14 只读验收。

Create `apps/api/tests/unit/test_retention_deploy_facts.py`:

```python
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "configs/deploy/scrapy/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "apps/api/.env.example"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_env_example_has_retention_switches() -> None:
    text = _text(ENV_EXAMPLE)
    assert text.count("RETENTION_CLEANUP_ENABLED=false") == 1
    assert text.count("RETENTION_CLEANER_ROLE=dih_retention_cleaner") == 1


def test_shared_compose_maps_retention_switches() -> None:
    text = _text(COMPOSE)
    assert text.count("RETENTION_CLEANUP_ENABLED:") == 1
    assert text.count("RETENTION_CLEANER_ROLE:") == 1
    assert "RETENTION_CLEANUP_ENABLED: ${RETENTION_CLEANUP_ENABLED:-false}" in text
    assert (
        "RETENTION_CLEANER_ROLE: ${RETENTION_CLEANER_ROLE:-dih_retention_cleaner}"
    ) in text
    assert "scrapy-new" not in text
```

- [ ] **Step 2: 写保留策略测试（先失败）**

Create `apps/api/tests/unit/test_retention_policy.py`:
```python
from __future__ import annotations

import pytest

from data_intelligence_hub.services.retention_policy import (
    BACKUP,
    NORMALIZED_DATASET,
    RAW_RESPONSE,
    REPORT_DELIVERY,
    RETENTION_POLICIES,
    RETENTION_POLICY_VERSION,
    RETENTION_TTL_DAYS,
    RUN_LOG,
    SECURITY_ACCESS_AUDIT,
    policy_by_class,
    policy_snapshot,
)


def test_retention_ttls_are_frozen() -> None:
    assert RETENTION_POLICY_VERSION == "retention_policy.v1"
    assert RETENTION_TTL_DAYS == {
        RAW_RESPONSE: 30,
        NORMALIZED_DATASET: 365,
        REPORT_DELIVERY: 730,
        RUN_LOG: 180,
        SECURITY_ACCESS_AUDIT: 730,
        BACKUP: 30,
    }


def test_policy_order_and_actions() -> None:
    assert [policy.data_class for policy in RETENTION_POLICIES] == [
        RAW_RESPONSE,
        NORMALIZED_DATASET,
        REPORT_DELIVERY,
        RUN_LOG,
        SECURITY_ACCESS_AUDIT,
        BACKUP,
    ]
    assert policy_by_class(BACKUP).managed_by == "backup_lifecycle"
    assert policy_by_class(BACKUP).action == "external"
    assert policy_by_class(RUN_LOG).action == "redact"
    assert policy_by_class(RAW_RESPONSE).action == "delete"
    assert "report_artifacts" in policy_by_class(REPORT_DELIVERY).target
    assert "delivery_bundles" in policy_by_class(REPORT_DELIVERY).target
    assert "audit_events" in policy_by_class(SECURITY_ACCESS_AUDIT).target
    assert policy_by_class(SECURITY_ACCESS_AUDIT).managed_by == "retention_cleaner_role"


def test_policy_snapshot_exposes_no_secrets() -> None:
    snapshot = policy_snapshot()
    assert len(snapshot) == 6
    assert all("salt" not in str(item).lower() for item in snapshot)


def test_unknown_class_is_rejected() -> None:
    with pytest.raises(ValueError, match="retention_data_class_unknown"):
        policy_by_class("everything")
```

- [ ] **Step 3: 写法律保留测试（先失败）**

Create `apps/api/tests/unit/test_legal_hold_service.py`:
```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import (
    AuditEvent,
    Base,
    LegalHold,
    Project,
    User,
    Workspace,
)
from data_intelligence_hub.services.legal_hold_service import (
    create_legal_hold,
    hold_applies,
    list_active_legal_holds,
    release_legal_hold,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="hash",
            name="Owner",
            status="active",
        )
    )
    session.add(
        Workspace(
            id=workspace_id,
            name="Workspace",
            slug=f"ws-{workspace_id}",
            owner_id=user_id,
        )
    )
    session.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="Project",
            domain="test",
            status="active",
            owner_id=user_id,
        )
    )
    await session.commit()
    return user_id, workspace_id, project_id


def test_hold_matching() -> None:
    hold = LegalHold(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=None,
        data_class=None,
        status="active",
        reason="litigation",
        requested_by_user_id=uuid.uuid4(),
        requested_at=NOW,
    )
    assert hold_applies(
        hold,
        workspace_id=hold.workspace_id,
        project_id=None,
        data_class="raw_response",
    )
    assert not hold_applies(
        hold,
        workspace_id=uuid.uuid4(),
        project_id=None,
        data_class="raw_response",
    )


@pytest.mark.asyncio
async def test_create_list_release_legal_hold(session: AsyncSession) -> None:
    user_id, workspace_id, project_id = await _seed(session)
    hold = await create_legal_hold(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        data_class="raw_response",
        reason="regulator_request",
        requested_by_user_id=user_id,
    )
    await session.commit()
    assert hold.status == "active"
    assert hold.release_reason is None

    active = await list_active_legal_holds(session, workspace_id=workspace_id)
    assert [item.id for item in active] == [hold.id]

    released = await release_legal_hold(
        session,
        workspace_id=workspace_id,
        hold_id=hold.id,
        released_by_user_id=user_id,
        release_reason="request_closed",
    )
    await session.commit()
    assert released.status == "released"
    assert released.released_by_user_id == user_id
    assert released.released_at is not None
    assert released.release_reason == "request_closed"

    active_after = await list_active_legal_holds(session, workspace_id=workspace_id)
    assert active_after == []

    events = list(
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.workspace_id == workspace_id)
                .order_by(AuditEvent.sequence_number)
            )
        )
        .scalars()
        .all()
    )
    assert [event.action for event in events] == [
        "legal_hold.created",
        "legal_hold.released",
    ]
    assert {event.result for event in events} == {"success"}
    assert events[0].details["data_class"] == "raw_response"
    assert events[1].details["status"] == "released"


@pytest.mark.asyncio
async def test_cross_workspace_project_is_rejected(session: AsyncSession) -> None:
    user_id, workspace_id, _ = await _seed(session)
    _, other_workspace_id, other_project_id = await _seed(session)

    with pytest.raises(ValueError, match="legal_hold_project_scope_invalid"):
        await create_legal_hold(
            session,
            workspace_id=workspace_id,
            project_id=other_project_id,
            data_class="raw_response",
            reason="test",
            requested_by_user_id=user_id,
        )
    assert other_workspace_id != workspace_id


@pytest.mark.asyncio
async def test_duplicate_release_is_rejected(session: AsyncSession) -> None:
    user_id, workspace_id, _ = await _seed(session)
    hold = await create_legal_hold(
        session,
        workspace_id=workspace_id,
        project_id=None,
        data_class=None,
        reason="test",
        requested_by_user_id=user_id,
    )
    await release_legal_hold(
        session,
        workspace_id=workspace_id,
        hold_id=hold.id,
        released_by_user_id=user_id,
        release_reason="closed",
    )
    await session.commit()

    with pytest.raises(ValueError, match="legal_hold_not_found"):
        await release_legal_hold(
            session,
            workspace_id=workspace_id,
            hold_id=hold.id,
            released_by_user_id=user_id,
            release_reason="closed_again",
        )
```

- [ ] **Step 4: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_policy.py tests/unit/test_legal_hold_service.py -v
```
Expected: FAIL，两个模块都不存在。

- [ ] **Step 5: 实现保留策略常量**

Create `apps/api/src/data_intelligence_hub/services/retention_policy.py`:
```python
"""Frozen retention policy.

契约冻结 v1.1 §2.10。TTL 不得由环境变量或 CLI 覆盖。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

RETENTION_POLICY_VERSION = "retention_policy.v1"

RAW_RESPONSE = "raw_response"
NORMALIZED_DATASET = "normalized_dataset"
REPORT_DELIVERY = "report_delivery"
RUN_LOG = "run_log"
SECURITY_ACCESS_AUDIT = "security_access_audit"
BACKUP = "backup"

RETENTION_TTL_DAYS: dict[str, int] = {
    RAW_RESPONSE: 30,
    NORMALIZED_DATASET: 365,
    REPORT_DELIVERY: 730,
    RUN_LOG: 180,
    SECURITY_ACCESS_AUDIT: 730,
    BACKUP: 30,
}


@dataclass(frozen=True)
class RetentionPolicy:
    data_class: str
    ttl_days: int
    target: str
    action: str
    managed_by: str = "platform"


RETENTION_POLICIES: tuple[RetentionPolicy, ...] = (
    RetentionPolicy(
        data_class=RAW_RESPONSE,
        ttl_days=RETENTION_TTL_DAYS[RAW_RESPONSE],
        target="raw_records",
        action="delete",
    ),
    RetentionPolicy(
        data_class=NORMALIZED_DATASET,
        ttl_days=RETENTION_TTL_DAYS[NORMALIZED_DATASET],
        target="dataset_versions,datasets,dataset_export_jobs",
        action="delete",
    ),
    RetentionPolicy(
        data_class=REPORT_DELIVERY,
        ttl_days=RETENTION_TTL_DAYS[REPORT_DELIVERY],
        target="reports,report_artifacts,delivery_bundles",
        action="delete",
    ),
    RetentionPolicy(
        data_class=RUN_LOG,
        ttl_days=RETENTION_TTL_DAYS[RUN_LOG],
        target="task_runs.logs,task_runs.error_traceback",
        action="redact",
    ),
    RetentionPolicy(
        data_class=SECURITY_ACCESS_AUDIT,
        ttl_days=RETENTION_TTL_DAYS[SECURITY_ACCESS_AUDIT],
        target="audit_events,report_audit_events,workflow_run_action_audit_events",
        action="delete",
        managed_by="retention_cleaner_role",
    ),
    RetentionPolicy(
        data_class=BACKUP,
        ttl_days=RETENTION_TTL_DAYS[BACKUP],
        target="backup_lifecycle",
        action="external",
        managed_by="backup_lifecycle",
    ),
)


def policy_by_class(data_class: str) -> RetentionPolicy:
    for policy in RETENTION_POLICIES:
        if policy.data_class == data_class:
            return policy
    raise ValueError("retention_data_class_unknown")


def policy_snapshot() -> list[dict[str, object]]:
    return [asdict(policy) for policy in RETENTION_POLICIES]
```

- [ ] **Step 6: 实现法律保留服务**

Create `apps/api/src/data_intelligence_hub/services/legal_hold_service.py`:
```python
"""Legal hold creation, release and matching."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models import LegalHold, Project
from data_intelligence_hub.models.retention import RETENTION_DATA_CLASSES
from data_intelligence_hub.services.audit_log import append_audit_event


def hold_applies(
    hold: LegalHold,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    data_class: str,
) -> bool:
    if hold.status != "active":
        return False
    if hold.workspace_id != workspace_id:
        return False
    if hold.project_id is not None and hold.project_id != project_id:
        return False
    if hold.data_class is not None and hold.data_class != data_class:
        return False
    return True


async def create_legal_hold(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    data_class: str | None,
    reason: str,
    requested_by_user_id: uuid.UUID,
) -> LegalHold:
    if data_class is not None and data_class not in RETENTION_DATA_CLASSES:
        raise ValueError("retention_data_class_unknown")
    if not reason.strip():
        raise ValueError("legal_hold_reason_required")
    if project_id is not None:
        project = await session.get(Project, project_id)
        if project is None or project.workspace_id != workspace_id:
            raise ValueError("legal_hold_project_scope_invalid")
    hold = LegalHold(
        workspace_id=workspace_id,
        project_id=project_id,
        data_class=data_class,
        status="active",
        reason=reason.strip(),
        requested_by_user_id=requested_by_user_id,
        requested_at=datetime.now(UTC),
    )
    session.add(hold)
    await session.flush()
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_user_id=requested_by_user_id,
        action="legal_hold.created",
        resource_type="legal_hold",
        resource_id=str(hold.id),
        result="success",
        details={
            "data_class": data_class,
            "project_id": str(project_id) if project_id is not None else None,
            "status": "active",
        },
    )
    return hold


async def release_legal_hold(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    hold_id: uuid.UUID,
    released_by_user_id: uuid.UUID,
    release_reason: str,
) -> LegalHold:
    if not release_reason.strip():
        raise ValueError("legal_hold_release_reason_required")
    result = await session.execute(
        select(LegalHold)
        .where(
            LegalHold.id == hold_id,
            LegalHold.workspace_id == workspace_id,
            LegalHold.status == "active",
        )
        .with_for_update()
    )
    hold = result.scalar_one_or_none()
    if hold is None:
        raise ValueError("legal_hold_not_found")
    hold.status = "released"
    hold.released_by_user_id = released_by_user_id
    hold.released_at = datetime.now(UTC)
    hold.release_reason = release_reason.strip()
    await session.flush()
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=hold.project_id,
        actor_user_id=released_by_user_id,
        action="legal_hold.released",
        resource_type="legal_hold",
        resource_id=str(hold.id),
        result="success",
        details={"hold_id": str(hold.id), "status": "released"},
    )
    return hold


async def list_active_legal_holds(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
) -> list[LegalHold]:
    result = await session.execute(
        select(LegalHold)
        .where(
            LegalHold.workspace_id == workspace_id,
            LegalHold.status == "active",
        )
        .order_by(LegalHold.requested_at)
    )
    return list(result.scalars().all())
```

- [ ] **Step 7: 运行测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_policy.py tests/unit/test_legal_hold_service.py tests/unit/test_retention_deploy_facts.py -v
```
Expected: PASS，10 passed。

- [ ] **Step 8: 提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/.env.example configs/deploy/scrapy/docker-compose.yml apps/api/src/data_intelligence_hub/services/retention_policy.py apps/api/src/data_intelligence_hub/services/legal_hold_service.py apps/api/tests/unit/test_retention_policy.py apps/api/tests/unit/test_retention_deploy_facts.py apps/api/tests/unit/test_legal_hold_service.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(retention): 冻结六类 TTL 与法律保留服务"
```

---

### Task 8: 清理引擎：原始响应与标准化数据集

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/retention_service.py`
- Test: `apps/api/tests/unit/test_retention_cleanup.py`

**Interfaces:**
- Consumes: `RETENTION_POLICIES`、`hold_applies`、`LegalHold`、`RetentionCleanupRun`、`RetentionTombstone`、`DatasetExportJob`、`DatasetVersion`、`RawRecord`。
- Produces:
  - `RetentionArtifactOutsideRootError`
  - `RetentionClassReport`
  - `RetentionCleanupReport`
  - `cleanup_expired_data(session, *, dry_run=True, now=None, workspace_id=None, export_root=None, requested_by_user_id=None) -> RetentionCleanupReport`
  - `dry_run=False` 时 `workspace_id` 必填；缺失抛 `retention_cleanup_workspace_required`。
  - execute 末尾写 `retention.cleanup.executed` 统一审计；`details.config` 记录 policy version、开关与专用角色。dry_run 不写审计。
  - `_handle_raw_response(...)`、`_handle_normalized_dataset(...)` 内部处理器

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_retention_cleanup.py`:
```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import (
    AuditEvent,
    Base,
    CollectionTask,
    Dataset,
    DatasetExportJob,
    DatasetVersion,
    LegalHold,
    Project,
    RawRecord,
    Report,
    ReportAuditEvent,
    RetentionCleanupRun,
    RetentionTombstone,
    Source,
    TaskRun,
    User,
    Workspace,
)
from data_intelligence_hub.services.retention_service import (
    RetentionArtifactOutsideRootError,
    cleanup_expired_data,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_tenant(session: AsyncSession) -> dict[str, uuid.UUID]:
    ids = {
        "user": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "project": uuid.uuid4(),
        "source": uuid.uuid4(),
        "task": uuid.uuid4(),
        "run": uuid.uuid4(),
    }
    session.add(
        User(
            id=ids["user"],
            email=f"{ids['user']}@example.com",
            password_hash="hash",
            name="Owner",
            status="active",
        )
    )
    session.add(
        Workspace(
            id=ids["workspace"],
            name="Workspace",
            slug=f"ws-{ids['workspace']}",
            owner_id=ids["user"],
        )
    )
    session.add(
        Project(
            id=ids["project"],
            workspace_id=ids["workspace"],
            name="Project",
            domain="test",
            status="active",
            owner_id=ids["user"],
        )
    )
    session.add(
        Source(
            id=ids["source"],
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            name="Source",
            type="generic_web",
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
        )
    )
    session.add(
        CollectionTask(
            id=ids["task"],
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            source_id=ids["source"],
            collector_type="generic_web",
            name="Task",
            schedule_cron=None,
            status="enabled",
            config={},
        )
    )
    session.add(
        TaskRun(
            id=ids["run"],
            task_id=ids["task"],
            project_id=ids["project"],
            workspace_id=ids["workspace"],
            status="success",
            started_at=NOW,
            finished_at=NOW,
            records_count=1,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=[],
            created_at=NOW,
        )
    )
    await session.flush()
    return ids


async def _add_raw_record(
    session: AsyncSession,
    ids: dict[str, uuid.UUID],
    *,
    age_days: int,
) -> uuid.UUID:
    record_id = uuid.uuid4()
    created_at = NOW - timedelta(days=age_days)
    session.add(
        RawRecord(
            id=record_id,
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            source_id=ids["source"],
            task_run_id=ids["run"],
            record_type="generic_page",
            source_url="https://example.com/page?utm_source=x",
            content={"text": "hello"},
            content_hash=str(uuid.uuid4()),
            collected_at=created_at,
            created_at=created_at,
        )
    )
    await session.flush()
    return record_id


async def _add_dataset(
    session: AsyncSession,
    ids: dict[str, uuid.UUID],
    tmp_path: Path,
    *,
    age_days: int,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    dataset_id = uuid.uuid4()
    version_id = uuid.uuid4()
    job_id = uuid.uuid4()
    created_at = NOW - timedelta(days=age_days)
    session.add(
        Dataset(
            id=dataset_id,
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            name=f"Dataset {dataset_id}",
            dataset_type="public_content_update",
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.add(
        DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            created_by_user_id=ids["user"],
            cleaning_plan_id=None,
            source_workflow_run_id=None,
            lineage_contract_version=None,
            version_number=1,
            source_task_run_ids=[str(ids["run"])],
            selected_fields=["title"],
            cleaning_script=[],
            rows=[],
            export_preview={"schema": {}},
            row_count=0,
            average_completeness_percent=100,
            status="saved",
            created_at=created_at,
        )
    )
    path = artifact_path or (tmp_path / f"{job_id}.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("title\nhello\n", encoding="utf-8")
    session.add(
        DatasetExportJob(
            id=job_id,
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            dataset_id=dataset_id,
            dataset_version_id=version_id,
            created_by_user_id=ids["user"],
            export_format="csv",
            status="success",
            filename=path.name,
            content_type="text/csv; charset=utf-8",
            artifact_path=str(path),
            artifact_size_bytes=path.stat().st_size,
            row_count=0,
            checksum_sha256="0" * 64,
            error_message=None,
            audit_events=[],
            created_at=created_at,
            finished_at=created_at,
        )
    )
    await session.flush()
    return {"dataset": dataset_id, "version": version_id, "job": job_id, "path": path}


@pytest.mark.asyncio
async def test_dry_run_counts_without_writing(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    old_raw = await _add_raw_record(session, ids, age_days=31)
    fresh_raw = await _add_raw_record(session, ids, age_days=1)
    old_dataset = await _add_dataset(session, ids, tmp_path, age_days=366)
    fresh_dataset = await _add_dataset(session, ids, tmp_path, age_days=1)
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=True,
        now=NOW,
        export_root=tmp_path,
    )
    await session.commit()

    assert report.dry_run is True
    assert report.cleanup_run_id is None
    assert report.classes["raw_response"].candidates == 1
    assert report.classes["raw_response"].deleted == 0
    assert report.classes["normalized_dataset"].candidates >= 1
    assert report.classes["normalized_dataset"].deleted == 0
    assert await session.get(RawRecord, old_raw) is not None
    assert await session.get(RawRecord, fresh_raw) is not None
    assert await session.get(DatasetVersion, old_dataset["version"]) is not None
    assert await session.get(DatasetVersion, fresh_dataset["version"]) is not None
    assert (
        await session.scalar(
            select(func.count()).select_from(RetentionCleanupRun)
        )
        == 0
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "retention.cleanup.executed")
        )
        == 0
    )


@pytest.mark.asyncio
async def test_execute_deletes_expired_raw_and_dataset(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    old_raw = await _add_raw_record(session, ids, age_days=31)
    fresh_raw = await _add_raw_record(session, ids, age_days=1)
    old_dataset = await _add_dataset(session, ids, tmp_path, age_days=366)
    fresh_dataset = await _add_dataset(session, ids, tmp_path, age_days=1)
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=False,
        now=NOW,
        workspace_id=ids["workspace"],
        export_root=tmp_path,
    )
    await session.commit()

    assert report.cleanup_run_id is not None
    assert report.status == "completed"
    assert await session.get(RawRecord, old_raw) is None
    assert await session.get(RawRecord, fresh_raw) is not None
    assert await session.get(DatasetVersion, old_dataset["version"]) is None
    assert await session.get(Dataset, old_dataset["dataset"]) is None
    assert not old_dataset["path"].exists()
    assert await session.get(DatasetVersion, fresh_dataset["version"]) is not None
    assert fresh_dataset["path"].is_file()
    assert (
        await session.scalar(
            select(func.count()).select_from(RetentionTombstone)
        )
        >= 2
    )
    events = list(
        (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "retention.cleanup.executed"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].resource_id == str(report.cleanup_run_id)
    assert events[0].details["config"]["workspace_id"] == str(ids["workspace"])
    assert events[0].details["config"]["policy_version"] == "retention_policy.v1"
    assert "retention_cleaner_role" in events[0].details["config"]


@pytest.mark.asyncio
async def test_artifact_outside_root_aborts_execute(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    outside = tmp_path / "outside.csv"
    outside.write_text("x\n", encoding="utf-8")
    old_dataset = await _add_dataset(
        session,
        ids,
        tmp_path,
        age_days=366,
        artifact_path=outside,
    )
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=True,
        now=NOW,
        export_root=tmp_path / "exports",
    )
    assert report.classes["normalized_dataset"].artifact_path_violations == 1
    assert report.cleanup_ready is False

    with pytest.raises(RetentionArtifactOutsideRootError):
        await cleanup_expired_data(
            session,
            dry_run=False,
            now=NOW,
            workspace_id=ids["workspace"],
            export_root=tmp_path / "exports",
        )
    await session.rollback()
    assert outside.is_file()
    assert await session.get(DatasetVersion, old_dataset["version"]) is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup.py -v
```
Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.retention_service`。

- [ ] **Step 3: 实现清理引擎基础、原始响应与数据集**

Create `apps/api/src/data_intelligence_hub/services/retention_service.py`:
```python
"""Retention cleanup engine.

- dry_run 默认不写库。
- execute 先校验导出文件路径，再删除；任何路径越界整体回滚。
- 每个被删除或脱敏的主体写 tombstone。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models import (
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
    Evidence,
    EntitySnapshot,
    LegalHold,
    RawRecord,
    Report,
    ReportAuditEvent,
    ReportSubscriptionRun,
    RetentionCleanupRun,
    RetentionTombstone,
    TaskRun,
    WorkflowRunActionAuditEvent,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.legal_hold_service import hold_applies
from data_intelligence_hub.services.retention_policy import (
    BACKUP,
    NORMALIZED_DATASET,
    RAW_RESPONSE,
    REPORT_DELIVERY,
    RETENTION_POLICIES,
    RETENTION_POLICY_VERSION,
    RUN_LOG,
    SECURITY_ACCESS_AUDIT,
    RetentionPolicy,
)


class RetentionArtifactOutsideRootError(RuntimeError):
    """导出文件路径不在受控根目录内。"""


@dataclass(frozen=True)
class RetentionClassReport:
    data_class: str
    cutoff: datetime
    candidates: int
    deleted: int = 0
    redacted: int = 0
    blocked: int = 0
    artifacts_deleted: int = 0
    artifacts_missing: int = 0
    artifact_path_violations: int = 0
    samples: tuple[str, ...] = ()
    managed_by: str = "platform"
    cleanup_ready: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "data_class": self.data_class,
            "cutoff": self.cutoff.isoformat(),
            "candidates": self.candidates,
            "deleted": self.deleted,
            "redacted": self.redacted,
            "blocked": self.blocked,
            "artifacts_deleted": self.artifacts_deleted,
            "artifacts_missing": self.artifacts_missing,
            "artifact_path_violations": self.artifact_path_violations,
            "samples": list(self.samples),
            "managed_by": self.managed_by,
            "cleanup_ready": self.cleanup_ready,
        }


@dataclass(frozen=True)
class RetentionCleanupReport:
    dry_run: bool
    policy_version: str
    started_at: datetime
    finished_at: datetime
    classes: dict[str, RetentionClassReport]
    cleanup_run_id: uuid.UUID | None = None
    status: str = "completed"

    @property
    def cleanup_ready(self) -> bool:
        return all(item.cleanup_ready for item in self.classes.values())

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "policy_version": self.policy_version,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "classes": {
                key: value.to_dict() for key, value in self.classes.items()
            },
            "cleanup_run_id": (
                str(self.cleanup_run_id) if self.cleanup_run_id is not None else None
            ),
            "status": self.status,
            "cleanup_ready": self.cleanup_ready,
        }


@dataclass(frozen=True)
class _Subject:
    subject_id: str
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    event_count: int = 1


async def cleanup_expired_data(
    session: AsyncSession,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
    workspace_id: uuid.UUID | None = None,
    export_root: Path | None = None,
    requested_by_user_id: uuid.UUID | None = None,
) -> RetentionCleanupReport:
    if not dry_run and workspace_id is None:
        raise ValueError("retention_cleanup_workspace_required")
    started_at = now or datetime.now(UTC)
    root = (
        export_root.expanduser().resolve()
        if export_root is not None
        else Path(get_settings().dataset_export_dir).expanduser().resolve()
    )
    holds = await _active_holds(session, workspace_id)

    run: RetentionCleanupRun | None = None
    if not dry_run:
        run = RetentionCleanupRun(
            mode="execute",
            status="completed",
            policy_version=RETENTION_POLICY_VERSION,
            requested_by_user_id=requested_by_user_id,
            started_at=started_at,
            finished_at=started_at,
            cutoffs={},
            counts={},
            samples={},
            blocked=[],
            error_message=None,
            created_at=started_at,
        )
        session.add(run)
        await session.flush()

    classes: dict[str, RetentionClassReport] = {}
    for policy in RETENTION_POLICIES:
        cutoff = started_at - timedelta(days=policy.ttl_days)
        if policy.data_class == RAW_RESPONSE:
            report = await _handle_raw_response(
                session,
                policy=policy,
                cutoff=cutoff,
                workspace_id=workspace_id,
                holds=holds,
                dry_run=dry_run,
                cleanup_run_id=run.id if run is not None else None,
                now=started_at,
            )
        elif policy.data_class == NORMALIZED_DATASET:
            report = await _handle_normalized_dataset(
                session,
                policy=policy,
                cutoff=cutoff,
                workspace_id=workspace_id,
                holds=holds,
                dry_run=dry_run,
                cleanup_run_id=run.id if run is not None else None,
                now=started_at,
                export_root=root,
            )
        else:
            report = await _dispatch_remaining(
                session,
                policy=policy,
                cutoff=cutoff,
                workspace_id=workspace_id,
                holds=holds,
                dry_run=dry_run,
                cleanup_run_id=run.id if run is not None else None,
                now=started_at,
            )
        classes[policy.data_class] = report

    finished_at = datetime.now(UTC)
    if run is not None:
        total_actions = sum(
            item.deleted + item.redacted for item in classes.values()
        )
        total_blocked = sum(item.blocked for item in classes.values())
        run.finished_at = finished_at
        run.status = (
            "blocked"
            if total_actions == 0 and total_blocked > 0
            else "completed"
        )
        run.cutoffs = {
            key: value.cutoff.isoformat() for key, value in classes.items()
        }
        run.counts = {
            key: {
                "candidates": value.candidates,
                "deleted": value.deleted,
                "redacted": value.redacted,
                "blocked": value.blocked,
            }
            for key, value in classes.items()
        }
        run.samples = {
            key: list(value.samples) for key, value in classes.items()
        }
        run.blocked = [
            {"data_class": key, "blocked": value.blocked}
            for key, value in classes.items()
            if value.blocked
        ]
        await session.flush()
        assert workspace_id is not None
        await append_audit_event(
            session,
            workspace_id=workspace_id,
            actor_user_id=requested_by_user_id,
            actor_type="user" if requested_by_user_id else "system",
            action="retention.cleanup.executed",
            resource_type="retention_cleanup_run",
            resource_id=str(run.id),
            result="success",
            details={
                "mode": "execute",
                "workspace_id": str(workspace_id),
                "policy_version": RETENTION_POLICY_VERSION,
                "cutoffs": run.cutoffs,
                "counts": run.counts,
                "blocked": run.blocked,
                "config": {
                    "workspace_id": str(workspace_id),
                    "policy_version": RETENTION_POLICY_VERSION,
                    "retention_cleanup_enabled": (
                        get_settings().retention_cleanup_enabled
                    ),
                    "retention_cleaner_role": (
                        get_settings().retention_cleaner_role
                    ),
                    "workspace_scoped": True,
                },
            },
        )

    return RetentionCleanupReport(
        dry_run=dry_run,
        policy_version=RETENTION_POLICY_VERSION,
        started_at=started_at,
        finished_at=finished_at,
        classes=classes,
        cleanup_run_id=run.id if run is not None else None,
        status=run.status if run is not None else "completed",
    )


async def _active_holds(
    session: AsyncSession,
    workspace_id: uuid.UUID | None,
) -> list[LegalHold]:
    statement = select(LegalHold).where(LegalHold.status == "active")
    if workspace_id is not None:
        statement = statement.where(LegalHold.workspace_id == workspace_id)
    result = await session.execute(statement)
    return list(result.scalars().all())


def _is_blocked(
    holds: list[LegalHold],
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    data_class: str,
) -> bool:
    return any(
        hold_applies(
            hold,
            workspace_id=workspace_id,
            project_id=project_id,
            data_class=data_class,
        )
        for hold in holds
    )


def _split_subjects(
    subjects: list[_Subject],
    holds: list[LegalHold],
    data_class: str,
) -> tuple[list[_Subject], int, tuple[str, ...]]:
    eligible: list[_Subject] = []
    blocked = 0
    samples: list[str] = []
    for subject in subjects:
        if _is_blocked(
            holds,
            workspace_id=subject.workspace_id,
            project_id=subject.project_id,
            data_class=data_class,
        ):
            blocked += 1
            continue
        eligible.append(subject)
        if len(samples) < 10:
            samples.append(subject.subject_id)
    return eligible, blocked, tuple(samples)


async def _handle_raw_response(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    statement = select(
        RawRecord.id,
        RawRecord.workspace_id,
        RawRecord.project_id,
    ).where(RawRecord.collected_at < cutoff)
    if workspace_id is not None:
        statement = statement.where(RawRecord.workspace_id == workspace_id)
    rows = list((await session.execute(statement)).all())
    subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id) for row in rows
    ]
    eligible, blocked, samples = _split_subjects(subjects, holds, policy.data_class)
    if dry_run:
        return _class_report(
            policy,
            cutoff,
            candidates=len(subjects),
            blocked=blocked,
            samples=samples,
        )

    if eligible:
        ids = [uuid.UUID(subject.subject_id) for subject in eligible]
        await session.execute(
            delete(EntitySnapshot).where(EntitySnapshot.raw_record_id.in_(ids))
        )
        await session.execute(
            update(Evidence)
            .where(Evidence.raw_record_id.in_(ids))
            .values(raw_record_id=None)
        )
        await session.execute(delete(RawRecord).where(RawRecord.id.in_(ids)))
        _add_tombstones(
            session,
            cleanup_run_id=cleanup_run_id,
            data_class=policy.data_class,
            subject_type="raw_records",
            subjects=eligible,
            deleted_at=now,
        )
    return _class_report(
        policy,
        cutoff,
        candidates=len(subjects),
        deleted=len(eligible),
        blocked=blocked,
        samples=samples,
    )


async def _handle_normalized_dataset(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
    export_root: Path,
) -> RetentionClassReport:
    version_statement = select(
        DatasetVersion.id,
        DatasetVersion.workspace_id,
        DatasetVersion.project_id,
    ).where(DatasetVersion.created_at < cutoff)
    if workspace_id is not None:
        version_statement = version_statement.where(
            DatasetVersion.workspace_id == workspace_id
        )
    version_rows = list((await session.execute(version_statement)).all())
    version_subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id)
        for row in version_rows
    ]
    eligible_versions, blocked_versions, version_samples = _split_subjects(
        version_subjects,
        holds,
        policy.data_class,
    )
    version_ids = [uuid.UUID(subject.subject_id) for subject in eligible_versions]

    export_rows: list[Any] = []
    if version_ids:
        export_rows = list(
            (
                await session.execute(
                    select(
                        DatasetExportJob.id,
                        DatasetExportJob.artifact_path,
                    ).where(
                        DatasetExportJob.dataset_version_id.in_(version_ids)
                    )
                )
            ).all()
        )
    artifacts = _classify_artifacts(
        [row.artifact_path for row in export_rows],
        export_root,
    )

    dataset_statement = select(
        Dataset.id,
        Dataset.workspace_id,
        Dataset.project_id,
    ).where(Dataset.created_at < cutoff)
    if workspace_id is not None:
        dataset_statement = dataset_statement.where(
            Dataset.workspace_id == workspace_id
        )
    dataset_rows = list((await session.execute(dataset_statement)).all())
    dataset_subjects: list[_Subject] = []
    for row in dataset_rows:
        if await _has_unexpired_versions(session, row.id, cutoff):
            continue
        dataset_subjects.append(
            _Subject(str(row.id), row.workspace_id, row.project_id)
        )
    eligible_datasets, blocked_datasets, dataset_samples = _split_subjects(
        dataset_subjects,
        holds,
        policy.data_class,
    )

    if not dry_run:
        if artifacts["violations"]:
            raise RetentionArtifactOutsideRootError(
                "retention_export_artifact_outside_root"
            )
        if version_ids:
            await session.execute(
                delete(DatasetDriftEvent).where(
                    DatasetDriftEvent.dataset_version_id.in_(version_ids)
                )
            )
            await session.execute(
                delete(DatasetExportJob).where(
                    DatasetExportJob.dataset_version_id.in_(version_ids)
                )
            )
            for path in artifacts["existing"]:
                path.unlink()
            await session.execute(
                delete(DatasetVersion).where(DatasetVersion.id.in_(version_ids))
            )
            await session.flush()
            _add_tombstones(
                session,
                cleanup_run_id=cleanup_run_id,
                data_class=policy.data_class,
                subject_type="dataset_versions",
                subjects=eligible_versions,
                deleted_at=now,
            )
        if eligible_datasets:
            dataset_ids = [
                uuid.UUID(subject.subject_id) for subject in eligible_datasets
            ]
            await session.execute(
                delete(Dataset).where(Dataset.id.in_(dataset_ids))
            )
            _add_tombstones(
                session,
                cleanup_run_id=cleanup_run_id,
                data_class=policy.data_class,
                subject_type="datasets",
                subjects=eligible_datasets,
                deleted_at=now,
            )

    return _class_report(
        policy,
        cutoff,
        candidates=len(version_subjects) + len(dataset_subjects),
        deleted=len(eligible_versions) + len(eligible_datasets),
        blocked=blocked_versions + blocked_datasets,
        artifacts_deleted=(
            len(artifacts["existing"]) if not dry_run else 0
        ),
        artifacts_missing=len(artifacts["missing"]),
        artifact_path_violations=len(artifacts["violations"]),
        samples=version_samples + dataset_samples,
        cleanup_ready=not artifacts["violations"],
    )


async def _has_unexpired_versions(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    cutoff: datetime,
) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(DatasetVersion)
        .where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.created_at >= cutoff,
        )
    )
    return bool(count)


def _classify_artifacts(
    values: list[str],
    export_root: Path,
) -> dict[str, list[Any]]:
    existing: list[Path] = []
    missing: list[str] = []
    violations: list[str] = []
    for value in values:
        path = Path(value).expanduser()
        try:
            resolved = path.resolve()
            resolved.relative_to(export_root)
        except (OSError, ValueError):
            violations.append(str(path))
            continue
        if resolved.is_file():
            existing.append(resolved)
        else:
            missing.append(str(resolved))
    return {
        "existing": existing,
        "missing": missing,
        "violations": violations,
    }


def _add_tombstones(
    session: AsyncSession,
    *,
    cleanup_run_id: uuid.UUID | None,
    data_class: str,
    subject_type: str,
    subjects: list[_Subject],
    deleted_at: datetime,
) -> None:
    if cleanup_run_id is None:
        raise RuntimeError("retention_cleanup_run_required")
    for subject in subjects:
        session.add(
            RetentionTombstone(
                workspace_id=subject.workspace_id,
                project_id=subject.project_id,
                data_class=data_class,
                subject_type=subject_type,
                subject_id=subject.subject_id,
                cleanup_run_id=cleanup_run_id,
                deleted_at=deleted_at,
                reason="retention_ttl",
                metadata_json=(
                    {"event_count": subject.event_count}
                    if subject.event_count != 1
                    else {}
                ),
            )
        )


def _class_report(
    policy: RetentionPolicy,
    cutoff: datetime,
    *,
    candidates: int,
    deleted: int = 0,
    redacted: int = 0,
    blocked: int = 0,
    artifacts_deleted: int = 0,
    artifacts_missing: int = 0,
    artifact_path_violations: int = 0,
    samples: tuple[str, ...] = (),
    cleanup_ready: bool = True,
) -> RetentionClassReport:
    return RetentionClassReport(
        data_class=policy.data_class,
        cutoff=cutoff,
        candidates=candidates,
        deleted=deleted,
        redacted=redacted,
        blocked=blocked,
        artifacts_deleted=artifacts_deleted,
        artifacts_missing=artifacts_missing,
        artifact_path_violations=artifact_path_violations,
        samples=samples,
        managed_by=policy.managed_by,
        cleanup_ready=cleanup_ready,
    )


async def _dispatch_remaining(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    if policy.data_class == BACKUP:
        return _class_report(policy, cutoff, candidates=0)
    if policy.data_class in {REPORT_DELIVERY, RUN_LOG, SECURITY_ACCESS_AUDIT}:
        return _class_report(policy, cutoff, candidates=0)
    return _class_report(policy, cutoff, candidates=0)
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup.py -v
```
Expected: PASS，3 passed。

- [ ] **Step 5: 提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/retention_service.py apps/api/tests/unit/test_retention_cleanup.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(retention): 清理引擎 dry-run 与原始响应、数据集删除"
```

---

### Task 9: 清理引擎：报告、运行日志与审计

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/retention_service.py`
- Modify: `apps/api/tests/unit/test_retention_cleanup.py`

**Interfaces:**
- Consumes: Task 8 的 `_class_report`、`_split_subjects`、`_add_tombstones`、`_active_holds`。
- Produces:
  - `_handle_report_delivery(...) -> RetentionClassReport`
  - `_handle_run_log(...) -> RetentionClassReport`
  - `_handle_security_access_audit(...) -> RetentionClassReport`
  - `_set_retention_cleaner_role(...)`、`_reset_retention_cleaner_role(...)`
  - 报告存在未过期 `report_audit_events` 行时阻塞该报告，不删除。
  - C2 链头导出与 `/api/audit-events/verify` 使用段校验：删除链首后，首个留存事件的 `prev_hash` 写入 `anchor_prev_hash`；C11 不重建已删除前缀。

- [ ] **Step 1: 追加报告、日志、审计失败测试**

Append to `apps/api/tests/unit/test_retention_cleanup.py`:
```python
async def _add_report(
    session: AsyncSession,
    ids: dict[str, uuid.UUID],
    *,
    age_days: int,
) -> dict[str, uuid.UUID]:
    report_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    created_at = NOW - timedelta(days=age_days)
    session.add(
        Report(
            id=report_id,
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            report_type="daily",
            title="Report",
            content="body",
            status="generated",
            period_start=created_at,
            period_end=created_at,
            created_at=created_at,
        )
    )
    session.add(
        ReportAuditEvent(
            id=audit_id,
            workspace_id=ids["workspace"],
            report_id=report_id,
            actor_id=ids["user"],
            event_type="generated",
            created_at=created_at,
        )
    )
    await session.flush()
    return {"report": report_id, "audit": audit_id}


@pytest.mark.asyncio
async def test_execute_redacts_old_run_logs_and_deletes_old_reports(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    old_report = await _add_report(session, ids, age_days=731)
    fresh_report = await _add_report(session, ids, age_days=1)
    old_run = await _add_raw_run(session, ids, age_days=181)
    fresh_run = await _add_raw_run(session, ids, age_days=1)
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=False,
        now=NOW,
        workspace_id=ids["workspace"],
        export_root=tmp_path,
    )
    await session.commit()

    assert report.classes["report_delivery"].deleted == 1
    assert report.classes["run_log"].redacted == 1
    assert await session.get(Report, old_report["report"]) is None
    assert await session.get(ReportAuditEvent, old_report["audit"]) is None
    assert await session.get(Report, fresh_report["report"]) is not None
    old_model = await session.get(TaskRun, old_run)
    fresh_model = await session.get(TaskRun, fresh_run)
    assert old_model is not None and old_model.logs == []
    assert old_model.error_traceback is None
    assert fresh_model is not None and fresh_model.logs == [{"step": "kept"}]


@pytest.mark.asyncio
async def test_report_with_fresh_audit_event_is_blocked(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    old_report = await _add_report(session, ids, age_days=731)
    session.add(
        ReportAuditEvent(
            id=uuid.uuid4(),
            workspace_id=ids["workspace"],
            report_id=old_report["report"],
            actor_id=ids["user"],
            event_type="viewed",
            created_at=NOW - timedelta(days=1),
        )
    )
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=False,
        now=NOW,
        workspace_id=ids["workspace"],
        export_root=tmp_path,
    )
    await session.commit()

    assert report.classes["report_delivery"].deleted == 0
    assert report.classes["report_delivery"].blocked == 1
    assert await session.get(Report, old_report["report"]) is not None


async def _add_raw_run(
    session: AsyncSession,
    ids: dict[str, uuid.UUID],
    *,
    age_days: int,
) -> uuid.UUID:
    run_id = uuid.uuid4()
    created_at = NOW - timedelta(days=age_days)
    session.add(
        TaskRun(
            id=run_id,
            task_id=ids["task"],
            project_id=ids["project"],
            workspace_id=ids["workspace"],
            status="success",
            started_at=created_at,
            finished_at=created_at,
            records_count=0,
            entities_count=0,
            error_message="failed once",
            error_traceback="trace",
            logs=[{"step": "kept"}],
            created_at=created_at,
        )
    )
    await session.flush()
    return run_id


@pytest.mark.asyncio
async def test_legal_hold_blocks_raw_response_cleanup(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    ids = await _seed_tenant(session)
    old_raw = await _add_raw_record(session, ids, age_days=31)
    session.add(
        LegalHold(
            workspace_id=ids["workspace"],
            project_id=None,
            data_class="raw_response",
            status="active",
            reason="litigation",
            requested_by_user_id=ids["user"],
            requested_at=NOW,
        )
    )
    await session.commit()

    report = await cleanup_expired_data(
        session,
        dry_run=False,
        now=NOW,
        workspace_id=ids["workspace"],
        export_root=tmp_path,
    )
    await session.commit()

    assert report.classes["raw_response"].blocked == 1
    assert report.classes["raw_response"].deleted == 0
    assert await session.get(RawRecord, old_raw) is not None


def test_security_audit_cleanup_uses_dedicated_role() -> None:
    source = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "api"
        / "src"
        / "data_intelligence_hub"
        / "services"
        / "retention_service.py"
    ).read_text(encoding="utf-8")
    assert "SET LOCAL ROLE" in source
    assert "dih_retention_cleaner" in source
    assert "RESET ROLE" in source
    assert "DELETE FROM audit_events" not in source


@pytest.mark.asyncio
async def test_backup_class_is_delegated(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    await _seed_tenant(session)
    await session.commit()
    report = await cleanup_expired_data(
        session,
        dry_run=True,
        now=NOW,
        export_root=tmp_path,
    )
    backup = report.classes["backup"]
    assert backup.managed_by == "backup_lifecycle"
    assert backup.deleted == 0
    assert backup.redacted == 0
```


- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup.py -v
```
Expected: FAIL。缺少报告、运行日志或审计处理器；不得在失败证据缺失时实现。

- [ ] **Step 3: 接入三个真实处理器**

Replace the `_dispatch_remaining` function body in `apps/api/src/data_intelligence_hub/services/retention_service.py` with:
```python
async def _dispatch_remaining(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    if policy.data_class == BACKUP:
        return _class_report(policy, cutoff, candidates=0)
    if policy.data_class == REPORT_DELIVERY:
        return await _handle_report_delivery(
            session,
            policy=policy,
            cutoff=cutoff,
            workspace_id=workspace_id,
            holds=holds,
            dry_run=dry_run,
            cleanup_run_id=cleanup_run_id,
            now=now,
        )
    if policy.data_class == RUN_LOG:
        return await _handle_run_log(
            session,
            policy=policy,
            cutoff=cutoff,
            workspace_id=workspace_id,
            holds=holds,
            dry_run=dry_run,
            cleanup_run_id=cleanup_run_id,
            now=now,
        )
    if policy.data_class == SECURITY_ACCESS_AUDIT:
        return await _handle_security_access_audit(
            session,
            policy=policy,
            cutoff=cutoff,
            workspace_id=workspace_id,
            holds=holds,
            dry_run=dry_run,
            cleanup_run_id=cleanup_run_id,
            now=now,
        )
    raise ValueError("retention_data_class_unknown")
```

Add the three handlers after `_class_report`:
```python
async def _handle_report_delivery(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    statement = select(
        Report.id,
        Report.workspace_id,
        Report.project_id,
    ).where(Report.created_at < cutoff)
    if workspace_id is not None:
        statement = statement.where(Report.workspace_id == workspace_id)
    rows = list((await session.execute(statement)).all())
    report_ids = [row.id for row in rows]
    fresh_audit_ids: set[uuid.UUID] = set()
    if report_ids:
        fresh_audit = await session.execute(
            select(ReportAuditEvent.report_id)
            .where(
                ReportAuditEvent.report_id.in_(report_ids),
                ReportAuditEvent.created_at >= cutoff,
            )
            .distinct()
        )
        fresh_audit_ids = {
            row.report_id for row in fresh_audit if row.report_id is not None
        }
    subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id) for row in rows
    ]
    eligible, blocked, samples = _split_subjects(
        subjects,
        holds,
        policy.data_class,
    )
    blocked_by_audit = [
        subject
        for subject in eligible
        if uuid.UUID(subject.subject_id) in fresh_audit_ids
    ]
    eligible = [
        subject
        for subject in eligible
        if uuid.UUID(subject.subject_id) not in fresh_audit_ids
    ]
    if not dry_run and eligible:
        ids = [uuid.UUID(subject.subject_id) for subject in eligible]
        await session.flush()
        await _set_retention_cleaner_role(session)
        await session.execute(
            delete(ReportAuditEvent).where(ReportAuditEvent.report_id.in_(ids))
        )
        await _reset_retention_cleaner_role(session)
        await session.execute(
            update(ReportSubscriptionRun)
            .where(ReportSubscriptionRun.report_id.in_(ids))
            .values(report_id=None)
        )
        await session.execute(delete(Report).where(Report.id.in_(ids)))
        _add_tombstones(
            session,
            cleanup_run_id=cleanup_run_id,
            data_class=policy.data_class,
            subject_type="reports",
            subjects=eligible,
            deleted_at=now,
        )
    return _class_report(
        policy,
        cutoff,
        candidates=len(subjects),
        deleted=len(eligible) if not dry_run else 0,
        blocked=blocked + len(blocked_by_audit),
        samples=samples,
    )


async def _handle_run_log(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    statement = select(
        TaskRun.id,
        TaskRun.workspace_id,
        TaskRun.project_id,
        TaskRun.logs,
        TaskRun.error_traceback,
    ).where(TaskRun.created_at < cutoff)
    if workspace_id is not None:
        statement = statement.where(TaskRun.workspace_id == workspace_id)
    rows = list((await session.execute(statement)).all())
    subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id) for row in rows
    ]
    eligible, blocked, samples = _split_subjects(
        subjects,
        holds,
        policy.data_class,
    )
    content_ids = {
        uuid.UUID(str(row.id))
        for row in rows
        if row.logs or row.error_traceback
    }
    redact_subjects = [
        subject
        for subject in eligible
        if uuid.UUID(subject.subject_id) in content_ids
    ]
    if not dry_run and redact_subjects:
        ids = [uuid.UUID(subject.subject_id) for subject in redact_subjects]
        await session.execute(
            update(TaskRun)
            .where(TaskRun.id.in_(ids))
            .values(logs=[], error_traceback=None)
        )
        _add_tombstones(
            session,
            cleanup_run_id=cleanup_run_id,
            data_class=policy.data_class,
            subject_type="task_runs.logs",
            subjects=redact_subjects,
            deleted_at=now,
        )
    return _class_report(
        policy,
        cutoff,
        candidates=len(subjects),
        redacted=len(redact_subjects) if not dry_run else 0,
        blocked=blocked,
        samples=samples,
    )


async def _set_retention_cleaner_role(session: AsyncSession) -> None:
    """审计表只允许专用保留角色删除。

    PostgreSQL 上设置本地角色；SQLite 单元测试没有角色，跳过。
    迁移 067 已替换 C2/C9 的 append-only 触发器函数：该角色只能删除超过
    730 天的行。触发器仍拒绝时本步骤失败，清理报告记为 blocked，不得静默跳过。
    """

    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from data_intelligence_hub.core.config import get_settings

    role = get_settings().retention_cleaner_role
    await session.execute(text(f'SET LOCAL ROLE "{role}"'))


async def _reset_retention_cleaner_role(session: AsyncSession) -> None:
    """恢复应用角色，保证后续业务表写入仍使用应用权限。"""

    if session.get_bind().dialect.name != "postgresql":
        return
    await session.execute(text("RESET ROLE"))


async def _handle_security_access_audit(
    session: AsyncSession,
    *,
    policy: RetentionPolicy,
    cutoff: datetime,
    workspace_id: uuid.UUID | None,
    holds: list[LegalHold],
    dry_run: bool,
    cleanup_run_id: uuid.UUID | None,
    now: datetime,
) -> RetentionClassReport:
    from data_intelligence_hub.models.audit_event import AuditEvent

    audit_statement = select(
        AuditEvent.id,
        AuditEvent.workspace_id,
        AuditEvent.project_id,
    ).where(AuditEvent.occurred_at < cutoff)
    if workspace_id is not None:
        audit_statement = audit_statement.where(AuditEvent.workspace_id == workspace_id)
    audit_rows = list((await session.execute(audit_statement)).all())
    audit_subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id) for row in audit_rows
    ]
    eligible_audit, blocked_audit, audit_samples = _split_subjects(
        audit_subjects,
        holds,
        policy.data_class,
    )

    report_statement = (
        select(
            ReportAuditEvent.id,
            ReportAuditEvent.workspace_id,
            Report.project_id,
        )
        .join(Report, Report.id == ReportAuditEvent.report_id)
        .where(ReportAuditEvent.created_at < cutoff)
    )
    if workspace_id is not None:
        report_statement = report_statement.where(
            ReportAuditEvent.workspace_id == workspace_id
        )
    report_rows = list((await session.execute(report_statement)).all())
    report_subjects = [
        _Subject(str(row.id), row.workspace_id, row.project_id)
        for row in report_rows
    ]
    eligible_reports, blocked_reports, report_samples = _split_subjects(
        report_subjects,
        holds,
        policy.data_class,
    )

    workflow_statement = (
        select(
            WorkflowRunActionAuditEvent.workflow_run_id,
            WorkflowRunActionAuditEvent.workspace_id,
            WorkflowRunActionAuditEvent.project_id,
            func.count().label("event_count"),
        )
        .group_by(
            WorkflowRunActionAuditEvent.workflow_run_id,
            WorkflowRunActionAuditEvent.workspace_id,
            WorkflowRunActionAuditEvent.project_id,
        )
        .having(func.max(WorkflowRunActionAuditEvent.created_at) < cutoff)
    )
    if workspace_id is not None:
        workflow_statement = workflow_statement.where(
            WorkflowRunActionAuditEvent.workspace_id == workspace_id
        )
    workflow_rows = list((await session.execute(workflow_statement)).all())
    workflow_subjects = [
        _Subject(
            str(row.workflow_run_id),
            row.workspace_id,
            row.project_id,
            event_count=int(row.event_count),
        )
        for row in workflow_rows
    ]
    eligible_workflows, blocked_workflows, workflow_samples = _split_subjects(
        workflow_subjects,
        holds,
        policy.data_class,
    )

    if not dry_run:
        if eligible_audit:
            await session.flush()
            await _set_retention_cleaner_role(session)
            ids = [uuid.UUID(subject.subject_id) for subject in eligible_audit]
            await session.execute(delete(AuditEvent).where(AuditEvent.id.in_(ids)))
            await _reset_retention_cleaner_role(session)
            _add_tombstones(
                session,
                cleanup_run_id=cleanup_run_id,
                data_class=policy.data_class,
                subject_type="audit_events",
                subjects=eligible_audit,
                deleted_at=now,
            )
        if eligible_reports:
            await session.flush()
            await _set_retention_cleaner_role(session)
            ids = [uuid.UUID(subject.subject_id) for subject in eligible_reports]
            await session.execute(
                delete(ReportAuditEvent).where(ReportAuditEvent.id.in_(ids))
            )
            await _reset_retention_cleaner_role(session)
            _add_tombstones(
                session,
                cleanup_run_id=cleanup_run_id,
                data_class=policy.data_class,
                subject_type="report_audit_events",
                subjects=eligible_reports,
                deleted_at=now,
            )
        if eligible_workflows:
            run_ids = [uuid.UUID(subject.subject_id) for subject in eligible_workflows]
            await session.execute(
                delete(WorkflowRunActionAuditEvent).where(
                    WorkflowRunActionAuditEvent.workflow_run_id.in_(run_ids)
                )
            )
            _add_tombstones(
                session,
                cleanup_run_id=cleanup_run_id,
                data_class=policy.data_class,
                subject_type="workflow_run_action_audit_events",
                subjects=eligible_workflows,
                deleted_at=now,
            )

    return _class_report(
        policy,
        cutoff,
        candidates=(
            len(audit_subjects)
            + len(report_subjects)
            + sum(subject.event_count for subject in workflow_subjects)
        ),
        deleted=(
            len(eligible_audit)
            + len(eligible_reports)
            + sum(subject.event_count for subject in eligible_workflows)
            if not dry_run
            else 0
        ),
        blocked=blocked_audit + blocked_reports + blocked_workflows,
        samples=audit_samples + report_samples + workflow_samples,
    )
```


Delete `_unused_imports_guard` and any now-unused imports. Keep `RETENTION_DATA_CLASSES` import only if used; remove if not. Keep `RETENTION_POLICIES`, `BACKUP`, etc.


- [ ] **Step 4: 运行清理测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup.py -v
```
Expected: PASS，9 passed。


- [ ] **Step 5: 静态检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run ruff check src/data_intelligence_hub/services/retention_service.py tests/unit/test_retention_cleanup.py
uv run mypy src/data_intelligence_hub/services/retention_service.py
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/retention_service.py apps/api/tests/unit/test_retention_cleanup.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(retention): 报告、运行日志与审计 TTL 清理"
```

---

### Task 10: 保留清理与法律保留 CLI

**Files:**
- Create: `apps/api/src/data_intelligence_hub/maintenance/retention_cleanup.py`
- Test: `apps/api/tests/unit/test_retention_cleanup_cli.py`

**Interfaces:**
- Consumes: `cleanup_expired_data`、`legal_hold_service`、`async_session_factory`。
- Produces:
  - `main() -> None`
  - 保留清理默认 dry-run；只有 `--execute` 才写库。
  - 法律保留 `place` / `release` 默认 dry-run；只有 `--execute` 才写库。
  - `--workspace-id` 对 dry-run 可选、对 `--execute` 必填；`--export-root` 可选。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_retention_cleanup_cli.py`:
```python
from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from data_intelligence_hub.maintenance import retention_cleanup


class FakeReport:
    def to_dict(self) -> dict[str, Any]:
        return {"dry_run": True, "classes": {}, "cleanup_ready": True}


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def commit(self) -> None:
        self.committed = True


def test_cli_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[bool] = []
    session = FakeSession()

    async def fake_cleanup(session_arg: Any, **kwargs: Any) -> FakeReport:
        calls.append(bool(kwargs["dry_run"]))
        return FakeReport()

    monkeypatch.setattr(retention_cleanup, "cleanup_expired_data", fake_cleanup)
    monkeypatch.setattr(retention_cleanup, "async_session_factory", lambda: session)
    monkeypatch.setattr(sys, "argv", ["retention_cleanup"])

    retention_cleanup.main()
    output = capsys.readouterr().out
    assert calls == [True]
    assert session.committed is False
    assert '"dry_run": true' in output


def test_cli_execute_commits(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[bool] = []
    session = FakeSession()

    async def fake_cleanup(session_arg: Any, **kwargs: Any) -> FakeReport:
        calls.append(bool(kwargs["dry_run"]))
        return FakeReport()

    monkeypatch.setattr(retention_cleanup, "cleanup_expired_data", fake_cleanup)
    monkeypatch.setattr(retention_cleanup, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        retention_cleanup,
        "get_settings",
        lambda: type("Settings", (), {"retention_cleanup_enabled": True})(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["retention_cleanup", "--execute", "--workspace-id", str(uuid4())],
    )

    retention_cleanup.main()
    capsys.readouterr()
    assert calls == [False]
    assert session.committed is True


def test_cli_execute_requires_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        retention_cleanup,
        "get_settings",
        lambda: type("Settings", (), {"retention_cleanup_enabled": False})(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["retention_cleanup", "--execute", "--workspace-id", str(uuid4())],
    )
    with pytest.raises(SystemExit):
        retention_cleanup.main()


def test_cli_execute_requires_workspace_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        retention_cleanup,
        "get_settings",
        lambda: type("Settings", (), {"retention_cleanup_enabled": True})(),
    )
    monkeypatch.setattr(sys, "argv", ["retention_cleanup", "--execute"])
    with pytest.raises(SystemExit):
        retention_cleanup.main()


def test_cli_rejects_bad_workspace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["retention_cleanup", "--workspace-id", "bad"])
    with pytest.raises(SystemExit):
        retention_cleanup.main()


def test_legal_hold_place_defaults_to_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_place(session: Any, **kwargs: Any) -> Any:
        calls.append(dict(kwargs))
        return type(
            "Hold",
            (),
            {
                "id": uuid4(),
                "workspace_id": kwargs["workspace_id"],
                "project_id": kwargs["project_id"],
                "status": "active",
            },
        )()

    monkeypatch.setattr(retention_cleanup, "create_legal_hold", fake_place)
    monkeypatch.setattr(retention_cleanup, "async_session_factory", FakeSession)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "retention_cleanup",
            "legal-hold",
            "place",
            "--workspace-id",
            str(uuid4()),
            "--reason",
            "litigation",
            "--requested-by-user-id",
            str(uuid4()),
        ],
    )

    retention_cleanup.main()
    output = capsys.readouterr().out
    assert calls == []
    assert "legal_hold_dry_run" in output


def test_legal_hold_execute_requires_explicit_flag(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_place(session: Any, **kwargs: Any) -> Any:
        calls.append(dict(kwargs))
        return type(
            "Hold",
            (),
            {
                "id": uuid4(),
                "workspace_id": kwargs["workspace_id"],
                "project_id": kwargs["project_id"],
                "status": "active",
            },
        )()

    monkeypatch.setattr(retention_cleanup, "create_legal_hold", fake_place)
    monkeypatch.setattr(retention_cleanup, "async_session_factory", FakeSession)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "retention_cleanup",
            "legal-hold",
            "place",
            "--execute",
            "--workspace-id",
            str(uuid4()),
            "--reason",
            "litigation",
            "--requested-by-user-id",
            str(uuid4()),
        ],
    )

    retention_cleanup.main()
    capsys.readouterr()
    assert len(calls) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup_cli.py -v
```
Expected: FAIL，`ModuleNotFoundError` 或 `main` 不存在。

- [ ] **Step 3: 实现 CLI**

Create `apps/api/src/data_intelligence_hub/maintenance/retention_cleanup.py`:
```python
"""Retention cleanup and legal-hold operator CLI.

默认 dry-run。只有显式 `--execute` 才写库。
法律保留写操作只在本 CLI 提供；C12 只读消费 list_active_legal_holds。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services.legal_hold_service import (
    create_legal_hold,
    release_legal_hold,
)
from data_intelligence_hub.services.retention_service import cleanup_expired_data


async def _run(
    *,
    dry_run: bool,
    workspace_id: uuid.UUID | None,
    export_root: Path | None,
) -> None:
    if not dry_run and not get_settings().retention_cleanup_enabled:
        raise SystemExit("retention_cleanup_disabled")
    if not dry_run and workspace_id is None:
        raise SystemExit("retention_cleanup_workspace_required")
    async with async_session_factory() as session:
        report = await cleanup_expired_data(
            session,
            dry_run=dry_run,
            workspace_id=workspace_id,
            export_root=export_root,
        )
        if not dry_run:
            await session.commit()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


async def _run_legal_hold(args: argparse.Namespace) -> None:
    if args.action == "place":
        if not args.execute:
            print(
                json.dumps(
                    {
                        "action": "legal_hold_dry_run",
                        "operation": "place",
                        "workspace_id": args.workspace_id,
                        "project_id": args.project_id,
                        "data_class": args.data_class,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        async with async_session_factory() as session:
            hold = await create_legal_hold(
                session,
                workspace_id=args.workspace_id,
                project_id=args.project_id,
                data_class=args.data_class,
                reason=args.reason,
                requested_by_user_id=args.requested_by_user_id,
            )
            await session.commit()
        print(json.dumps({"legal_hold_id": str(hold.id), "status": hold.status}))
        return
    if args.action == "release":
        if not args.execute:
            print(
                json.dumps(
                    {
                        "action": "legal_hold_dry_run",
                        "operation": "release",
                        "workspace_id": args.workspace_id,
                        "hold_id": args.hold_id,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return
        async with async_session_factory() as session:
            hold = await release_legal_hold(
                session,
                workspace_id=args.workspace_id,
                hold_id=args.hold_id,
                released_by_user_id=args.released_by_user_id,
                release_reason=args.reason,
            )
            await session.commit()
        print(json.dumps({"legal_hold_id": str(hold.id), "status": hold.status}))
        return
    raise SystemExit("unsupported_legal_hold_action")


def _workspace_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("workspace_id_invalid") from exc


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("uuid_invalid") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit or execute retention cleanup and legal holds."
    )
    parser.add_argument("--execute", action="store_true", help="Write changes.")
    parser.add_argument("--workspace-id", type=_workspace_id, default=None)
    parser.add_argument("--export-root", type=Path, default=None)

    sub = parser.add_subparsers(dest="command")
    legal = sub.add_parser("legal-hold")
    legal_sub = legal.add_subparsers(dest="action", required=True)
    place = legal_sub.add_parser("place")
    place.add_argument("--execute", action="store_true")
    place.add_argument("--workspace-id", type=_workspace_id, required=True)
    place.add_argument("--project-id", type=_uuid, default=None)
    place.add_argument("--data-class", default=None)
    place.add_argument("--reason", required=True)
    place.add_argument("--requested-by-user-id", type=_uuid, required=True)
    release = legal_sub.add_parser("release")
    release.add_argument("--execute", action="store_true")
    release.add_argument("--workspace-id", type=_workspace_id, required=True)
    release.add_argument("--hold-id", type=_uuid, required=True)
    release.add_argument("--released-by-user-id", type=_uuid, required=True)
    release.add_argument("--reason", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "legal-hold":
        asyncio.run(_run_legal_hold(args))
        return
    asyncio.run(
        _run(
            dry_run=not args.execute,
            workspace_id=args.workspace_id,
            export_root=args.export_root,
        )
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行 CLI 测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_retention_cleanup_cli.py -v
```
Expected: PASS，7 passed。

- [ ] **Step 5: 提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/maintenance/retention_cleanup.py apps/api/tests/unit/test_retention_cleanup_cli.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(retention): 保留清理与法律保留 CLI，默认 dry-run"
```

---

## Release Gates

以下门禁不属于单个任务，但发布前必须全部通过。

### GitNexus

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs detect-changes --scope compare --base-ref feat/gov-c10 --repo .
```
Expected: 两次都不是 `partial: true`，不是 `truncated: true`。`compare` 不出现跨工作区、密钥、Cookie 或盐泄漏。

### 隔离 worktree 与本地根目录

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
git rev-parse --show-toplevel
git status --short
rg -n "/Users/lute/Project/data_scrapy([^-]|$)" \
  docs/superpowers/plans/2026-10-22-governed-task-platform-c11-pseudonymization-retention.md
```
Expected: `git rev-parse --show-toplevel` 输出 `/Users/lute/Project/data_scrapy-gov-c11`；工作区只有本计划与切片改动；`rg` 只命中 Task 0 的主工作树预检、`git worktree add` 与复制源命令，其他 Run/Commit 命令都使用 worktree 根。

### 静态 compose 映射与配置示例

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
rg -n "RETENTION_CLEANUP_ENABLED|RETENTION_CLEANER_ROLE" \
  configs/deploy/scrapy/docker-compose.yml apps/api/.env.example
```
Expected: `.env.example` 各一处 `RETENTION_CLEANUP_ENABLED=false` 与 `RETENTION_CLEANER_ROLE=dih_retention_cleaner`；共享 compose 的 `api.environment` 各一处静态映射 `${RETENTION_CLEANUP_ENABLED:-false}` 与 `${RETENTION_CLEANER_ROLE:-dih_retention_cleaner}`。C11 不修改 `configs/deploy/scrapy-new/**`。PG0 发布负责人只改 `.env.production` 的值，不追加映射键；C14 只读。

### 统一审计

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
rg -n "dataset.export.created|privacy.projection.applied|project.access.denied|legal_hold.created|legal_hold.released|retention.cleanup.executed" \
  apps/api/src/data_intelligence_hub/services apps/api/src/data_intelligence_hub/maintenance
rg -n "AUDIT_ACTIONS|validate_audit_action" apps/api/src/data_intelligence_hub/services/audit_log.py
```
Expected: 导出服务包含允许与拒绝两类动作；法律保留服务包含 `legal_hold.created` / `legal_hold.released`；清理服务包含 `retention.cleanup.executed`；所有动作都来自 C2 `AUDIT_ACTIONS`，没有第二张审计表，没有未登记动作。导出拒绝的 `project.access.denied` 由 C2 `record_authorization_denial` 写入。

### 伪名与审计触发器不回退

```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest tests/unit/test_pseudonymization.py tests/unit/test_tiktok_ingestion_pseudonymization.py -q
rg -n "workspace_pseudonym_salts|uq_workspace_pseudonym_salts_workspace_id|dih_retention_cleaner|interval '730 days'" \
  src/data_intelligence_hub/services/pseudonymization.py \
  src/data_intelligence_hub/services/tiktok_content_ingestion.py \
  alembic/versions/202610220069_pseudonymization_retention.py
```
Expected: 伪名测试通过；盐表仍是一工作区一行，伪名同工作区稳定、跨工作区不可关联；067 仍包含 `dih_retention_cleaner` 与 730 天删除例外；普通应用 `UPDATE` / `DELETE` 仍拒绝。C12 的 068 只能保留该例外并新增自己的角色例外。

### 测试与静态检查

```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run pytest \
  tests/unit/test_contract_c11_objects.py \
  tests/unit/test_pseudonymization_retention_migration_source.py \
  tests/unit/test_retention_models.py \
  tests/unit/test_pseudonymization.py \
  tests/unit/test_export_policy.py \
  tests/unit/test_tiktok_ingestion_pseudonymization.py \
  tests/unit/test_retention_policy.py \
  tests/unit/test_retention_deploy_facts.py \
  tests/unit/test_legal_hold_service.py \
  tests/unit/test_retention_cleanup.py \
  tests/unit/test_retention_cleanup_cli.py \
  tests/integration/test_governed_dataset_export.py \
  tests/integration/test_dataset_export_preview.py \
  -q
uv run ruff check \
  src/data_intelligence_hub/models/retention.py \
  src/data_intelligence_hub/services/pseudonymization.py \
  src/data_intelligence_hub/services/export_policy.py \
  src/data_intelligence_hub/services/governed_dataset_export.py \
  src/data_intelligence_hub/services/tiktok_content_ingestion.py \
  src/data_intelligence_hub/services/retention_policy.py \
  src/data_intelligence_hub/services/legal_hold_service.py \
  src/data_intelligence_hub/services/retention_service.py \
  src/data_intelligence_hub/maintenance/retention_cleanup.py \
  src/data_intelligence_hub/api/routes/automation.py
```
Expected: 全部 PASS；ruff 0 错误。

### 迁移

```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
uv run alembic heads
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: 只有一个 head `202610220069 (head)`；round-trip 成功。禁止在两套生产上直接试验 downgrade。

### PostgreSQL 审计触发器

```bash
cd /Users/lute/Project/data_scrapy-gov-c11/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://localhost/c11_retention_cleaner_workflow_plan_phase2_test \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest tests/postgres/test_audit_retention_cleaner.py -v
```

Expected: `3 passed`。断言：普通应用角色不能 `DELETE` 或 `UPDATE`；`dih_retention_cleaner` 只能删除 730 天前的 `audit_events` 与 `report_audit_events` 行；未过期行仍被拒绝；`UPDATE` 对专用角色也拒绝。没有受控测试库时 `skipped` 不算通过，必须补跑。

### 生产 A/B（PG0 发布负责人执行；C14 只读）

C11 是代码、迁移与测试切片，不部署。生产发布只有一个 owner：

| 角色 | 唯一职责 | 禁止 |
|---|---|---|
| PG0 发布负责人（PG0 发布批次） | A/B 备份、迁移 067、`dih_retention_cleaner` 角色检查、`.env.production` 设值、重启、`RETENTION_CLEANUP_ENABLED` 切换，并记录开关变更事实 | 不修改 C11 代码、迁移或测试 |
| C14 | 只读 health、canary、preflight、Playwright 与浏览器交接验收 | 不备份、不迁移、不改 compose/env、不重启、不切换开关、不写法律保留、不运行清理命令 |

开关变更审计使用 C2 登记的 `config.switch.changed`，由 C2 或 PG0 发布负责人执行；C11 不自造动作，不写该动作。仓库内的 `RETENTION_CLEANUP_ENABLED` 与 `RETENTION_CLEANER_ROLE` 静态映射由 C11 提交；PG0 发布负责人不追加映射键，只设置值。

PG0 发布负责人的执行顺序：

1. A 先备份 PostgreSQL，并确认迁移执行者具备 `CREATEROLE`，或 DBA 已创建 `dih_retention_cleaner` 并授予迁移执行者 `ADMIN OPTION`。
2. A 应用迁移 067。迁移必须保持单 head `202610220069`。
3. PG0 发布负责人在 A 的受控会话执行 `SELECT current_user, pg_has_role(current_user, 'dih_retention_cleaner', 'MEMBER');`，结果必须包含 `dih_retention_cleaner` 的成员关系。该检查只允许 PG0 发布负责人执行。
4. A 健康检查必须 `status=ok`，`schema_revision=schema_head=202610220069`。
5. B 的 `202610190045` 目标授权与备份门禁未通过时，不升级 B。记录 `BLOCKED`，不阻断 A。B 通过门禁后，由同一 PG0 发布负责人应用 067，再报告自己的 schema head。
6. 不要求 A 与 B 同批迁移，不因 B 落后延长 A 的发布窗口。

共享 compose 的两行静态映射已在 C11 提交：`RETENTION_CLEANUP_ENABLED` 默认 `false`，`RETENTION_CLEANER_ROLE` 默认 `dih_retention_cleaner`。PG0 发布负责人在验收前保持 `RETENTION_CLEANUP_ENABLED=false`；C11 验收通过后只把 `.env.production` 的值设为 `true`，再重启 api。C14 只读确认取值，不改 compose 或 env。

C14 只读验收：

```bash
curl -fsSL https://scrapy.luteos.com/api/health \
  | jq '{status, schema_revision, schema_head}'
curl -fsSL https://scrapy.lute-tlz-dddd.top/api/health \
  | jq '{status, schema_revision, schema_head}'
```

Expected: A 返回 `status=ok` 与 `schema_revision=schema_head=202610220069`；B 在解锁前返回旧 head 或 `BLOCKED` 记录。C14 不修改任何环境变量、compose 文件、数据库行或功能开关。

浏览器验收由 C14 执行，范围限于 `/settings` 的只读展示与下方交接单。C14 不执行迁移、不写法律保留、不运行清理命令。

### 冻结文件

```bash
cd /Users/lute/Project/data_scrapy-gov-c11
git diff --exit-code -- apps/api/src/data_intelligence_hub/services/automation_service.py
git diff --exit-code -- apps/scraper-console
```
Expected: 两条命令退出码 0，无输出。任一输出表示越界，停止发布。

### 浏览器交接

C11 不修改 `apps/scraper-console/**`，不新增 HTTP 端点。浏览器页面由 C14 独占。

C14 在 `/settings` 内联展示：

- 六类 TTL 的只读表格；数据来自 C1 契约常量，不来自新端点。
- 当前工作区的 active 法律保留；数据来自 C12 已登记的 `GET /api/privacy/legal-holds`。
- 保留清理最近一次 dry-run 的结论；数据来自 C11 CLI 输出，运维手工粘贴或从运维记录读取，不新增 API。

C11 只提供交接单 `docs/ops/retention-legal-hold-handoff.md`，内容：

- 六类 TTL 与 C1 契约版本。
- `retention_cleanup` CLI 的 dry-run 和 execute 命令。
- 法律保留 place/release 命令。
- 专用保留角色 `dih_retention_cleaner` 与审计表清理限制。
- 禁止在浏览器展示盐、`creator_cookie`、原始响应正文或审计正文。

C14 不得：

- 新增 `/settings/retention` 第 12 条合同路由。
- 直接调用 `cleanup_expired_data` 或 `create_legal_hold` 服务。
- 展示伪名盐、反查映射或 `creator_cookie`。

---

## 覆盖矩阵

| 设计 / 任务要求 | 落地任务 |
|---|---|
| 工作区级盐 | Task 2、Task 3 |
| 工作区内稳定、跨工作区不可关联 | Task 3、Task 4、Task 5 |
| 导出 PII 遮蔽 | Task 4、Task 5 |
| 只读 PII 扫描（C9/C10 唯一扫描器） | Task 4 |
| 来源 URL 保留并去追踪参数 | Task 4、Task 5 |
| 六类 retention TTL | Task 7、Task 8、Task 9 |
| legal_hold | Task 2、Task 7、Task 9 |
| dry-run 清理 | Task 8、Task 9、Task 10 |
| 一个迁移 067 | Task 2 |
| 审计 append-only 触发器替换、专用角色只删过期行、普通应用仍拒绝 | Task 2、Task 9、Release Gates（PostgreSQL） |
| 不改 `automation_service.py` | Task 5、Release Gates |
| 新导出策略接缝并收敛路径 | Task 4、Task 5 |
| 不做 DSR / 删除请求 | Global Constraints |
| 浏览器 settings 保留页交 C14 | Release Gates |
| C1 契约只读门禁 | Task 1 |
| 环境变量示例与共享 compose 静态映射 | Task 7、Release Gates |
| 隔离 worktree `/Users/lute/Project/data_scrapy-gov-c11` 与本地根目录归一 | Task 0、Release Gates |
| 导出项目 ACL：同工作区跨项目 403、跨工作区 404 | Task 5 |
| 统一审计：导出允许/拒绝、法律保留建立/释放、清理执行/配置 | Task 5、Task 7、Task 8、Release Gates |
| PG0 发布负责人唯一发布所有权、C14 只读 | Global Constraints、Release Gates |
| 工作区伪名与 067 触发器不回退 | Task 2、Task 3、Task 6、Release Gates |
| GitNexus / 迁移 / 生产 A-B / 浏览器门禁 | Task 0、Task 1、Task 2、Release Gates |
