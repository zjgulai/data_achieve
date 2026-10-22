# C12 删除请求与人工 DSR 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付项目/工作区删除请求、法律保留只读检查、墓碑、删除证明、恢复后删除重放和人工 DSR 审计。C12 不改契约，不写法律保留，不实现前端，不依赖分享服务。

**Architecture:** 删除是带审计链的状态机。`deletion_requests` 保存请求和确认状态；`deletion_tombstones` 保存不可反查的对象类摘要；`deletion_proofs` 保存删除证明；`privacy_audit_events` 保存每个流的追加式哈希链。执行器先只读检查 C11 的 active 法律保留和活跃运行，再在同一个事务内撤销项目密钥、删除或脱敏业务数据与文件、写墓碑和证明。恢复后由独立 manifest 触发重放，不依赖被回滚的库内状态。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.0 async、Alembic、Pydantic v2、PostgreSQL 15/16、pytest。前端与浏览器验收不属本切片。

## Global Constraints

- **契约与 registry 由 C1 独占。** C12 只读 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 与 `configs/contracts/v1.1.0/registry.json`。C12 不修改契约、不升级版本、不追加登记、不手改 registry。开工守卫测试逐项断言 C1 已登记 C12 的八张表、枚举、`/api/privacy/*` 路径和五个错误码。缺任一项时停止 C12，把缺口交回 C1。
- **依赖 C3、C4、C8、C10、C11。** C3 提供 `project_api_keys.status`、复合外键和密钥撤销语义。C4 提供 `workbench_tasks` 与 `models/workbench.py` 的 `WorkbenchTask`。C8 提供 `data_gaps`、`market_assessments` 与对应模型。C10 提供 `services/delivery/store.py` 的 `DeliveryStore`。C11 提供迁移 `202610220067`、法律保留表、`services/legal_hold_service.py` 的 `list_active_legal_holds` 与 `hold_applies`。C12 只读取、删除或脱敏这些行，不重建、不改写表结构与业务规则。
- **分享首期延期。** C12 不建 `report_shares` 表，不导入分享服务，不调用分享撤销。删除执行时只追加一条 no-op 审计事件 `deletion_share_revocation_deferred`。删除证明中的 `report_shares` 计数固定为 `0`。
- **`deletion_share_revocation_deferred` 不是新契约枚举。** 它是 `privacy_audit_events` 的事件数据，写在既有 `event_type` 字符串列中；C1 registry 不新增该事件枚举，C12 也不新增错误码或路径。C12 只在 `privacy_audit_events.event_type` 写入该字符串，测试断言事件行存在且 `report_shares` 计数为 `0`。
- **法律保留写入归 C11。** C12 不提供法律保留写接口，不写法律保留表，不注册法律保留命令行。C12 只在确认、执行和重新评估时只读检查 active 保留。
- **删除授权。** 删除操作使用 owner/admin 人类会话，并校验项目 ACL、二次确认和审计。owner 和 admin 可发起。admin 的申请必须由 owner 批准。确认和执行只允许 owner。项目目标还必须通过 C2 `require_project_access(..., manage=True)` 的项目 ACL。二次确认使用 15 分钟一次性 token 和 `DELETE <目标名>` 文本。Agent、项目密钥、服务账号和客户 MCP 不能发起、批准、确认或执行。
- **不新增额外认证依赖。** C12 不导入额外认证依赖，不挂路由依赖，不定义相关错误码，不写相关文案。C1 已把该事项延期为 PG0 之后。
- **只引入一个迁移。** 迁移文件是 `apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py`。`down_revision = "202610220067"`。迁移前唯一 head 必须是 `202610220067`。不得创建第二个 head。不得改 067 及更早迁移。068 不得创建法律保留表。
- **功能开关不新增错误码。** 唯一开关是 `PRIVACY_DELETION_ENABLED`，默认 `false`。关闭时写接口返回 404 `deletion_request_not_found`，读取接口仍可用。不新增未登记的错误码。回滚点是关闭开关并回退应用版本，保留 068 已建的表；生产不执行 downgrade 068。
- **审计只追加。** `privacy_audit_events` 普通应用角色不能 UPDATE 或 DELETE。24 个月清理只允许专用数据库角色 `dih_privacy_audit_cleaner` 按完整流失批删除。不得逐行删除活跃流。
- **C9 不可变触发器有删除与脱敏例外，C11 保留期例外必须保留。** C9 的 `report_artifacts` 与 `report_audit_events` 有不可变触发器。068 必须替换这两个触发器函数，除专用角色外保留原有 UPDATE 限制，只增加专用角色 `dih_deletion_executor` 的例外：`report_artifacts` 允许 DELETE，`report_audit_events` 允许 UPDATE 与 DELETE。`report_audit_events` 的函数还必须保留 C11 的 067 定义：`dih_retention_cleaner` 只能 DELETE `OLD.created_at < now() - interval '730 days'` 的行。普通角色仍被拒绝。执行器用 `SET LOCAL ROLE` 进入 `dih_deletion_executor`。应用角色可以是该 `NOLOGIN` 角色的成员，成员关系只用于在受控事务内执行 `SET LOCAL ROLE`；应用角色在常态角色下没有这两张表的直接 UPDATE 或 DELETE 授权。`report_audit_events` 原地脱敏 `metadata_json` 与 `artifact_id`，保留事件类型、状态流转与时间等最小审计元数据。
- **删除范围必须完整。** 执行范围包含 `workbench_tasks`、`data_gaps`、`market_assessments`、`runs`、`run_steps`、`task_runs`、`collection_tasks`、`sources`、`claims`、`claim_evidence`、`evidences`、`report_artifacts`、`report_audit_events`、交付 manifest 与交付文件、dataset export artifact 文件、`dataset_export_jobs`。`workbench_tasks`、`market_assessments`、`runs`、`run_steps`、`task_runs`、`collection_tasks`、`sources` 与 `report_audit_events` 原地脱敏，不删除。`data_gaps`、`claims`、`claim_evidence`、`evidences`、`report_artifacts` 与 `dataset_export_jobs` 删除。删除证明必须写出每类行数、文件数或保留元数据行数。
- **账本、审计与证据等级不删除。** `run_ledger_entries`、`run_evidence_grades`、`tool_calls`、`authorizations` 与 `privacy_audit_events` 原样保留，不删除、不改写。`runs`、`run_steps`、`task_runs` 的品牌、竞品、决策问题等正文来自上游 `workbench_tasks` 与 `workflow_versions.plan_payload`；脱敏后保留状态、成本、证据等级与时间等最小元数据。
- **不实现前端。** 控制台与 Playwright 由 C14 独占。C12 只提交浏览器交接单。C12 不创建、不修改任何前端目录或端到端测试。
- **发布交 PG0 发布批次。** C12 不直接部署，不部署生产。A/B 两套环境由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。生产 B 在 `202610190045` 的目标授权与备份门禁通过前保持 `BLOCKED`，不得应用 068。
- **每次提交前检查图变更。** 每个 commit 前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不算通过，必须重跑。
- **测试基线是空集。** 任何新失败都是回归。提交前必须跑 `scripts/check_pytest_baseline.py`。
- **GitNexus 索引。** 索引落后时先运行 `node .gitnexus/run.cjs analyze --index-only`。改既有符号前跑 `impact`。`risk: UNKNOWN` 必须用文本搜索复核，不得当作低风险。
- **写作。** 代码注释和文档用简洁中文。回复和文档遵守 ASD-STE100 等效写法：短句、主动语态、一个句子一个意思。

## 依赖门禁

Task 0 创建并进入 `/Users/lute/Project/data_scrapy-gov-c12` 后，执行以下命令。任何一条不符合，停止并先完成依赖切片。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
git merge-base --is-ancestor feat/gov-c11 HEAD
node .gitnexus/run.cjs status --repo .
cd apps/api
uv run alembic heads
```

预期：

```text
git merge-base 退出码 0。
GitNexus status 不是 behind；如 behind，先 analyze。
alembic heads 只输出 202610220067 (head)。
```

GitNexus 影响面门禁：

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs impact "ProjectApiKey" --direction upstream --repo .
node .gitnexus/run.cjs impact "ReportArtifact" --direction upstream --repo .
node .gitnexus/run.cjs impact "DatasetVersion" --direction upstream --repo .
node .gitnexus/run.cjs impact "RawRecord" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkbenchTask" --direction upstream --repo .
```

预期：每条命令输出 risk、callers 和 processes。`HIGH` 或 `CRITICAL` 时先写缓解方案；`UNKNOWN` 时用 `git grep -n "ProjectApiKey\|ReportArtifact\|DatasetVersion\|RawRecord\|WorkbenchTask" -- apps/api/src apps/api/tests` 补充调用点，不得按零影响继续。

依赖接口门禁：

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run python - <<'PY'
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.retention import LegalHold
from data_intelligence_hub.models.run_evidence_grade import RunEvidenceGradeRecord
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.legal_hold_service import list_active_legal_holds

assert "status" in ProjectApiKey.__table__.columns
assert "data_class" in LegalHold.__table__.columns
assert "target_type" not in LegalHold.__table__.columns
assert "decision_question" in WorkbenchTask.__table__.columns
assert "customer_text_zh" in DataGap.__table__.columns
assert "evidence_grade" in MarketAssessment.__table__.columns
assert "run_id" in RunLedgerEntry.__table__.columns
assert "grade" in RunEvidenceGradeRecord.__table__.columns
assert callable(DeliveryStore.remove_bundle)
assert callable(list_active_legal_holds)
print("c12_dependencies_ok")
PY
```

预期输出 `c12_dependencies_ok`。缺 `WorkbenchTask`、`DataGap` 或 `MarketAssessment` 时停止，先完成 C4 与 C8。C11 的读取函数签名固定为：

```python
async def list_active_legal_holds(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> list[LegalHold]: ...
```

C10 的交付目录接口固定为：

```python
class DeliveryStore:
    def bundle_dir(self, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Path: ...
    def remove_bundle(self, *, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> None: ...
```

C3 的密钥撤销字段固定为 `revoked_at` 与 `status`。C12 直接更新 `project_api_keys`，因为撤销是幂等状态变更。

---

## File Structure

**创建**

| 路径 | 责任 |
|---|---|
| `apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py` | C12 唯一迁移：八张表、索引、约束、审计只追加触发器。 |
| `apps/api/src/data_intelligence_hub/models/privacy_deletion.py` | 删除请求、墓碑、回执、证明、重放、DSR、隐私审计模型。 |
| `apps/api/src/data_intelligence_hub/services/privacy_audit.py` | 追加式隐私审计链。 |
| `apps/api/src/data_intelligence_hub/services/deletion_service.py` | 删除请求状态机、二次确认、法律保留只读检查。 |
| `apps/api/src/data_intelligence_hub/services/subprocessor_receipts.py` | 子处理者回执人工记录。 |
| `apps/api/src/data_intelligence_hub/services/dsr_service.py` | 人工 DSR 案件流转。 |
| `apps/api/src/data_intelligence_hub/services/deletion_proof.py` | 删除证明生成与校验。 |
| `apps/api/src/data_intelligence_hub/services/deletion_executor.py` | 删除执行器、墓碑、业务数据删除或脱敏、文件删除。 |
| `apps/api/src/data_intelligence_hub/services/deletion_replay.py` | 删除 manifest 与恢复后重放。 |
| `apps/api/src/data_intelligence_hub/repositories/privacy.py` | 隐私对象只读查询。 |
| `apps/api/src/data_intelligence_hub/schemas/privacy.py` | API 请求与响应模型。 |
| `apps/api/src/data_intelligence_hub/api/routes/privacy.py` | `/api/privacy/*` 路由。 |
| `apps/api/src/data_intelligence_hub/maintenance/privacy_ops.py` | DSR、删除证明、manifest、重放命令行。 |
| `apps/api/src/data_intelligence_hub/maintenance/privacy_receipts.py` | 子处理者回执命令行。 |
| `apps/api/src/data_intelligence_hub/maintenance/privacy_audit_retention.py` | 24 个月审计流清理，只允许专用角色。 |
| `apps/api/tests/unit/test_c12_contract_registration.py` | C1 registry 只读守卫。 |
| `apps/api/tests/unit/test_privacy_models.py` | 表名、枚举、约束测试。 |
| `apps/api/tests/unit/test_privacy_audit.py` | 审计链追加与篡改检测。 |
| `apps/api/tests/unit/test_deletion_service.py` | 状态机、二次确认、法律保留阻断。 |
| `apps/api/tests/unit/test_subprocessor_receipts.py` | 回执录入与幂等更新。 |
| `apps/api/tests/unit/test_dsr.py` | DSR 状态流转与不透明引用。 |
| `apps/api/tests/unit/test_deletion_executor.py` | 删除范围、文件删除、证明计数。 |
| `apps/api/tests/unit/test_deletion_replay.py` | manifest 校验与重放。 |
| `apps/api/tests/unit/test_privacy_routes.py` | 鉴权、错误码、只读端点。 |
| `apps/api/tests/unit/test_privacy_ops_cli.py` | 命令行分组与默认 dry-run。 |
| `apps/api/tests/unit/test_privacy_audit_retention.py` | 角色守卫与整流失批。 |
| `apps/api/tests/unit/test_privacy_deploy_facts.py` | `.env.example` 与共享 compose 的精确键名和默认值测试。 |
| `apps/api/tests/postgres/test_deletion_dsr_migration.py` | 068 升级、降级、C11 保留期例外、执行器例外与普通角色拒绝。 |
| `docs/ops/privacy-deletion-dsr.md` | 删除、DSR、重放与审计保留运行手册。 |

**修改**

| 路径 | 责任 |
|---|---|
| `apps/api/src/data_intelligence_hub/models/__init__.py` | 只追加 C12 模型导入。 |
| `apps/api/src/data_intelligence_hub/main.py` | 只追加 privacy router 挂载。 |
| `apps/api/src/data_intelligence_hub/core/config.py` | 追加 `privacy_deletion_enabled` 与 `privacy_audit_cleaner_database_url`。 |
| `apps/api/src/data_intelligence_hub/repositories/projects.py` | 只读过滤 `Project.status == "deleted"`。 |
| `apps/api/.env.example` | 追加 `PRIVACY_DELETION_ENABLED=false` 与 `PRIVACY_AUDIT_CLEANER_DATABASE_URL=` 示例。 |
| `configs/deploy/scrapy/docker-compose.yml` | 追加 `PRIVACY_DELETION_ENABLED` 与 `PRIVACY_AUDIT_CLEANER_DATABASE_URL` 的静态映射；PG0 发布批次只设值，C14 只做只读验收。 |

**禁止创建**

- 不创建法律保留写入服务或法律保留命令行。
- 不创建分享撤销端口、分享服务适配器或分享表。
- 不创建任何控制台、前端或 Playwright 文件。
- 不创建契约、registry 或附录变更。

---

## 跨任务接口

以下签名是任务之间的唯一接口。后续任务不得改名。

```python
# services/privacy_audit.py
def canonical_json(payload: Mapping[str, Any]) -> str
def sha256_digest(payload: Mapping[str, Any]) -> str
async def append_privacy_event(session, *, workspace_id, stream_type, stream_id, event_type, actor_user_id, actor_kind, payload) -> PrivacyAuditEvent
async def verify_privacy_chain(session, *, workspace_id, stream_type, stream_id) -> str | None

# services/deletion_service.py
async def create_deletion_request(session, *, workspace_id, requested_by_user_id, target_type, project_id, reason) -> CreatedDeletionRequest
async def approve_deletion_request(session, *, request_id, workspace_id, actor_user_id, decision, reason=None) -> CreatedDeletionRequest
async def confirm_deletion_request(session, *, request_id, workspace_id, actor_user_id, token, confirmation_text) -> DeletionRequest
async def resend_confirmation(session, *, request_id, workspace_id, actor_user_id) -> CreatedDeletionRequest
async def cancel_deletion_request(session, *, request_id, workspace_id, actor_user_id, reason) -> DeletionRequest
async def retry_deletion_request(session, *, request_id, workspace_id, actor_user_id) -> DeletionRequest
async def reevaluate_deletion_request(session, *, request_id, workspace_id, actor_user_id) -> DeletionRequest
async def mark_deletion_failed(session, *, request_id, workspace_id, actor_user_id, code) -> DeletionRequest
async def active_hold_count(session, *, workspace_id, project_id) -> int

# services/deletion_proof.py
async def issue_deletion_proof(session, *, request, tombstones, revocations, file_deletions, receipts, preserved, audit_head_digest, schema_revision, completed_at) -> DeletionProof
def verify_proof_digest(proof: DeletionProof) -> bool

# services/deletion_executor.py
async def execute_deletion_request(session, *, request_id, workspace_id, actor_user_id, delivery_store) -> DeletionExecutionResult
async def purge_project_target(session, *, request, project_id, delivery_store, record_tombstones=True, audit_share_noop=True) -> tuple[list[DeletionTombstone], dict[str, int], FileDeletionResult, dict[str, int]]
async def purge_workspace_target(session, *, request, delivery_store, record_tombstones=True) -> tuple[list[DeletionTombstone], dict[str, int], FileDeletionResult, dict[str, int]]

# services/deletion_replay.py
async def build_deletion_manifest(session, *, workspace_id) -> dict[str, Any]
async def write_deletion_manifest(session, *, workspace_id, output_path) -> dict[str, Any]
async def apply_deletion_manifest(session, *, manifest, source_backup_ref, operator_label, delivery_store) -> DeletionReplayRun
```

---

### Task 0: 隔离 worktree 初始化

**Files:**
- 只读：`/Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md`（主工作树的计划文件，复制源）
- Create: `/Users/lute/Project/data_scrapy-gov-c12`（worktree 根）

**Interfaces:**
- Consumes: 前置分支 `feat/gov-c11`；主工作树的计划文件。
- Produces: 分支 `feat/gov-c12` 与 worktree `/Users/lute/Project/data_scrapy-gov-c12`；Task 0 之后所有 Run/Commit 都在该 worktree 执行。

- [ ] **Step 0: 主工作树只读预检**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c11^{commit}
git rev-parse --verify --quiet refs/heads/feat/gov-c12 || echo "C12_BRANCH_ABSENT"
test ! -e /Users/lute/Project/data_scrapy-gov-c12 && echo "worktree_path_free"
```

Expected: `git worktree prune` 退出码 0；`git rev-parse` 输出 `feat/gov-c11` 提交 SHA；输出 `C12_BRANCH_ABSENT` 与 `worktree_path_free`。`feat/gov-c11` 不存在、分支 `feat/gov-c12` 已存在或 worktree 路径已存在时停止，先审查旧分支与旧 worktree，不得复用或删除。

- [ ] **Step 1: 创建 worktree、复制本计划并同步依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree add /Users/lute/Project/data_scrapy-gov-c12 -b feat/gov-c12 feat/gov-c11
cd /Users/lute/Project/data_scrapy-gov-c12
test "$(git branch --show-current)" = feat/gov-c12 && echo "branch=feat/gov-c12"
git merge-base --is-ancestor feat/gov-c11 HEAD; echo "c11_ancestor=$?"
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md docs/superpowers/plans/
test -s docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md && echo "plan_copied"
cd apps/api && uv sync
```

Expected: `branch=feat/gov-c12`；`c11_ancestor=0`；`plan_copied`；`uv sync` 退出码 0。本计划的 Markdown 不在 `feat/gov-c11` 内，必须先从主工作树复制到 worktree。主工作树只用于本 Step 的 `git worktree add`、只读预检与 `cp` 源。

- [ ] **Step 2: 固定执行路径与迁移基线**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
git rev-parse --show-toplevel
git status --short
cd apps/api && uv run alembic heads
```

Expected: 输出 `/Users/lute/Project/data_scrapy-gov-c12`；工作区干净或只有未跟踪的本计划文件；Alembic 只有一行 `202610220067 (head)`。不是单 head 时停止，C1–C11 尚未落地；不得把本迁移改号或接到 `202610210055`。后续 Run/Commit 块必须在该 worktree 内执行。

---

### Task 1: C1 契约守卫、迁移 068 与隐私模型

**Files:**
- Create: `apps/api/tests/unit/test_c12_contract_registration.py`
- Create: `apps/api/src/data_intelligence_hub/models/privacy_deletion.py`
- Create: `apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Test: `apps/api/tests/unit/test_privacy_models.py`
- Test: `apps/api/tests/postgres/test_deletion_dsr_migration.py`

**Interfaces:**
- Consumes: C1 registry、C11 迁移 067 的法律保留表。
- Produces: `DeletionRequest`、`DeletionTombstone`、`DeletionSubprocessorReceipt`、`DeletionProof`、`DeletionReplayRun`、`DeletionReplayItem`、`DsrCase`、`PrivacyAuditEvent` 及枚举。

- [ ] **Step 1: 写 C1 registry 只读守卫**

Create `apps/api/tests/unit/test_c12_contract_registration.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = API_ROOT.parents[1] / "configs/contracts/v1.1.0/registry.json"

REQUIRED_TABLES = {
    "deletion_requests",
    "deletion_tombstones",
    "deletion_subprocessor_receipts",
    "deletion_proofs",
    "deletion_replay_runs",
    "deletion_replay_items",
    "dsr_cases",
    "privacy_audit_events",
}
REQUIRED_ENUMS = {
    "deletion_requests.target_type",
    "deletion_requests.requested_by_role",
    "deletion_requests.status",
    "deletion_subprocessor_receipts.status",
    "dsr_cases.request_type",
    "dsr_cases.status",
    "dsr_cases.responsibility",
    "deletion_replay_runs.status",
    "deletion_replay_items.status",
    "privacy_audit_events.stream_type",
    "privacy_audit_events.actor_kind",
}
REQUIRED_PATHS = {
    "/api/privacy/deletion-requests",
    "/api/privacy/deletion-requests/{request_id}",
    "/api/privacy/deletion-requests/{request_id}/approve",
    "/api/privacy/deletion-requests/{request_id}/confirm",
    "/api/privacy/deletion-requests/{request_id}/execute",
    "/api/privacy/deletion-requests/{request_id}/proof",
    "/api/privacy/legal-holds",
    "/api/privacy/dsr-cases",
    "/api/privacy/audit-events",
}
REQUIRED_CODES = {
    "deletion_request_not_found",
    "legal_hold_active",
    "deletion_state_conflict",
    "deletion_proof_not_ready",
    "dsr_case_not_found",
}


def _registry() -> dict:
    assert REGISTRY_PATH.is_file(), "C1 registry 不存在；停止 C12，先完成 C1"
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_c12_tables_are_registered() -> None:
    registry = _registry()
    tables = {table["name"] for table in registry["tables"]}
    missing = REQUIRED_TABLES - tables
    assert not missing, f"C1 registry 缺 C12 表：{sorted(missing)}；停止 C12，交回 C1"


def test_c12_enums_are_registered() -> None:
    registry = _registry()
    enums = {enum["name"] for enum in registry["enums"]}
    missing = REQUIRED_ENUMS - enums
    assert not missing, f"C1 registry 缺 C12 枚举：{sorted(missing)}"


def test_c12_paths_are_registered() -> None:
    registry = _registry()
    paths = {path["path"] for path in registry["paths"]}
    missing = REQUIRED_PATHS - paths
    assert not missing, f"C1 registry 缺 C12 路径：{sorted(missing)}"


def test_c12_error_codes_are_registered() -> None:
    registry = _registry()
    codes = {item["code"] for item in registry["error_codes"]}
    missing = REQUIRED_CODES - codes
    assert not missing, f"C1 registry 缺 C12 错误码：{sorted(missing)}"


def test_legal_holds_stay_with_c11() -> None:
    registry = _registry()
    hold = next(table for table in registry["tables"] if table["name"] == "legal_holds")
    columns = {column["name"] for column in hold["columns"]}
    assert "target_type" not in columns
    assert "target_id" not in columns
    assert "data_class" in columns
    assert all(
        column["phase"] == "C11"
        for column in hold["columns"]
        if column["name"] in {"data_class", "status", "reason"}
    )
```

- [ ] **Step 2: 运行守卫**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_c12_contract_registration.py
```

Expected: `5 passed`。失败时停止。C12 不得自行修改契约或 registry。

- [ ] **Step 3: 写模型失败测试**

Create `apps/api/tests/unit/test_privacy_models.py`:

```python
from __future__ import annotations

from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequest,
    DeletionRequestStatus,
    DeletionTargetType,
    DsrCase,
    DsrStatus,
    PrivacyAuditEvent,
    PrivacyStreamType,
)


def test_privacy_table_names_are_frozen() -> None:
    assert DeletionRequest.__tablename__ == "deletion_requests"
    assert DsrCase.__tablename__ == "dsr_cases"
    assert PrivacyAuditEvent.__tablename__ == "privacy_audit_events"


def test_deletion_request_status_has_nine_values() -> None:
    assert {item.value for item in DeletionRequestStatus} == {
        "pending_owner_approval",
        "pending_confirmation",
        "ready",
        "blocked_legal_hold",
        "executing",
        "completed",
        "failed",
        "rejected",
        "cancelled",
    }


def test_target_and_stream_values_are_frozen() -> None:
    assert {item.value for item in DeletionTargetType} == {"project", "workspace"}
    assert {item.value for item in PrivacyStreamType} == {
        "deletion_request",
        "legal_hold",
        "dsr_case",
        "deletion_replay",
    }
    assert {item.value for item in DsrStatus} == {
        "received",
        "verifying",
        "in_progress",
        "completed",
        "rejected",
        "closed",
    }


def test_legal_hold_model_is_owned_by_c11() -> None:
    import data_intelligence_hub.models.privacy_deletion as module

    assert not hasattr(module, "LegalHold")
    assert not hasattr(module, "LegalHoldStatus")
```


- [ ] **Step 4: 运行模型测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_models.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.models.privacy_deletion`。若模块已存在，则至少因缺少冻结模型或枚举失败；不得在测试未呈红色时实现。

- [ ] **Step 5: 实现模型**

Create `apps/api/src/data_intelligence_hub/models/privacy_deletion.py`:

```python
"""隐私删除、DSR 与追加式审计模型。

本模块只保存删除状态、摘要和证明，不保存已删除正文。
法律保留模型由 C11 的 models/retention.py 拥有。
审计表只追加。PostgreSQL 迁移额外创建 UPDATE/DELETE 触发器。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeletionTargetType(StrEnum):
    PROJECT = "project"
    WORKSPACE = "workspace"


class DeletionRequesterRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"


class DeletionRequestStatus(StrEnum):
    PENDING_OWNER_APPROVAL = "pending_owner_approval"
    PENDING_CONFIRMATION = "pending_confirmation"
    READY = "ready"
    BLOCKED_LEGAL_HOLD = "blocked_legal_hold"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class SubprocessorReceiptStatus(StrEnum):
    PENDING = "pending"
    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    NOT_APPLICABLE = "not_applicable"


class DsrRequestType(StrEnum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    RESTRICTION = "restriction"
    DELETION = "deletion"


class DsrStatus(StrEnum):
    RECEIVED = "received"
    VERIFYING = "verifying"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CLOSED = "closed"


class DsrResponsibility(StrEnum):
    CONTROLLER = "controller"
    PROCESSOR = "processor"
    UNDETERMINED = "undetermined"


class DeletionReplayStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DeletionReplayItemStatus(StrEnum):
    REPLAYED = "replayed"
    SKIPPED_ABSENT = "skipped_absent"
    FAILED = "failed"


class PrivacyStreamType(StrEnum):
    DELETION_REQUEST = "deletion_request"
    LEGAL_HOLD = "legal_hold"
    DSR_CASE = "dsr_case"
    DELETION_REPLAY = "deletion_replay"


class PrivacyActorKind(StrEnum):
    USER = "user"
    OPERATOR = "operator"
    SYSTEM = "system"


_ACTIVE_DELETION_STATUSES = (
    "pending_owner_approval",
    "pending_confirmation",
    "ready",
    "blocked_legal_hold",
    "executing",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


class DeletionRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        Index(
            "uq_deletion_requests_active_target",
            "workspace_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text(_in_list("status", _ACTIVE_DELETION_STATUSES)),
            sqlite_where=text(_in_list("status", _ACTIVE_DELETION_STATUSES)),
        ),
        CheckConstraint(_in_list("target_type", ("project", "workspace")), name="target_type"),
        CheckConstraint(
            _in_list("requested_by_role", ("owner", "admin")),
            name="requested_by_role",
        ),
        CheckConstraint(
            _in_list("status", tuple(item.value for item in DeletionRequestStatus)),
            name="status",
        ),
        CheckConstraint(
            "(target_type = 'project' AND project_id IS NOT NULL AND target_id = project_id) "
            "OR (target_type = 'workspace' AND project_id IS NULL AND target_id = workspace_id)",
            name="target_scope",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    requested_by_role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    confirmation_token_hash: Mapped[str | None] = mapped_column(String(64))
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    tombstone_digest: Mapped[str | None] = mapped_column(String(71))


class DeletionTombstone(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deletion_tombstones"
    __table_args__ = (
        UniqueConstraint(
            "deletion_request_id",
            "object_class",
            "target_id",
            name="uq_deletion_tombstones_request_class_target",
        ),
    )

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deletion_requests.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    object_class: Mapped[str] = mapped_column(String(60), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeletionSubprocessorReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deletion_subprocessor_receipts"
    __table_args__ = (
        UniqueConstraint(
            "deletion_request_id",
            "subprocessor_name",
            name="uq_deletion_subprocessor_receipts_request_name",
        ),
        CheckConstraint(
            _in_list("status", tuple(item.value for item in SubprocessorReceiptStatus)),
            name="status",
        ),
    )

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deletion_requests.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    subprocessor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    request_reference: Mapped[str | None] = mapped_column(String(200))
    receipt_reference: Mapped[str | None] = mapped_column(String(200))
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_note: Mapped[str | None] = mapped_column(Text)
    recorded_by_operator: Mapped[str] = mapped_column(String(200), nullable=False)


class DeletionProof(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deletion_proofs"
    __table_args__ = (
        UniqueConstraint("deletion_request_id", name="uq_deletion_proofs_request"),
        UniqueConstraint("proof_number", name="uq_deletion_proofs_number"),
    )

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deletion_requests.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    proof_number: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    proof_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    audit_head_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeletionReplayRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deletion_replay_runs"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", tuple(item.value for item in DeletionReplayStatus)),
            name="status",
        ),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    manifest_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    source_backup_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    replayed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    operator_label: Mapped[str] = mapped_column(String(200), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeletionReplayItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deletion_replay_items"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "target_type", "target_id", name="uq_deletion_replay_items_run_target"
        ),
        CheckConstraint(
            _in_list("status", tuple(item.value for item in DeletionReplayItemStatus)),
            name="status",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deletion_replay_runs.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DsrCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dsr_cases"
    __table_args__ = (
        UniqueConstraint("case_number", name="uq_dsr_cases_number"),
        CheckConstraint(
            _in_list("request_type", tuple(item.value for item in DsrRequestType)),
            name="request_type",
        ),
        CheckConstraint(_in_list("status", tuple(item.value for item in DsrStatus)), name="status"),
        CheckConstraint(
            _in_list("responsibility", tuple(item.value for item in DsrResponsibility)),
            name="responsibility",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    case_number: Mapped[str] = mapped_column(String(40), nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    responsibility: Mapped[str] = mapped_column(String(20), nullable=False)
    requester_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    verification_method: Mapped[str | None] = mapped_column(String(80))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_note: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deletion_requests.id")
    )
    summary: Mapped[str | None] = mapped_column(Text)
    created_by_operator: Mapped[str] = mapped_column(String(200), nullable=False)


class PrivacyAuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "privacy_audit_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "stream_type",
            "stream_id",
            "sequence_number",
            name="uq_privacy_audit_events_stream_sequence",
        ),
        UniqueConstraint(
            "workspace_id",
            "stream_type",
            "stream_id",
            "event_digest",
            name="uq_privacy_audit_events_stream_digest",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "stream_type",
                "stream_id",
                "previous_event_digest",
            ],
            [
                "privacy_audit_events.workspace_id",
                "privacy_audit_events.stream_type",
                "privacy_audit_events.stream_id",
                "privacy_audit_events.event_digest",
            ],
            name="fk_privacy_audit_events_predecessor",
        ),
        CheckConstraint("sequence_number >= 1", name="sequence_number"),
        CheckConstraint(
            "(sequence_number = 1 AND previous_event_digest IS NULL) "
            "OR (sequence_number > 1 AND previous_event_digest IS NOT NULL)",
            name="predecessor",
        ),
        CheckConstraint(
            _in_list("actor_kind", tuple(item.value for item in PrivacyActorKind)),
            name="actor_kind",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    stream_type: Mapped[str] = mapped_column(String(30), nullable=False)
    stream_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_event_digest: Mapped[str | None] = mapped_column(String(71))
    event_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "DeletionProof",
    "DeletionReplayItem",
    "DeletionReplayItemStatus",
    "DeletionReplayRun",
    "DeletionReplayStatus",
    "DeletionRequest",
    "DeletionRequestStatus",
    "DeletionRequesterRole",
    "DeletionSubprocessorReceipt",
    "DeletionTargetType",
    "DeletionTombstone",
    "DsrCase",
    "DsrRequestType",
    "DsrResponsibility",
    "DsrStatus",
    "PrivacyActorKind",
    "PrivacyAuditEvent",
    "PrivacyStreamType",
    "SubprocessorReceiptStatus",
]
```

- [ ] **Step 6: 导出模型**

在 `apps/api/src/data_intelligence_hub/models/__init__.py` 的 import 区追加：

```python
from data_intelligence_hub.models.privacy_deletion import (
    DeletionProof,
    DeletionReplayItem,
    DeletionReplayRun,
    DeletionRequest,
    DeletionSubprocessorReceipt,
    DeletionTombstone,
    DsrCase,
    PrivacyAuditEvent,
)
```

在 `__all__` 追加同名八项。不得导入或重新导出法律保留模型；法律保留由 C11 的 `models/retention.py` 导出。

- [ ] **Step 7: 写 PostgreSQL 迁移失败测试**

Create `apps/api/tests/postgres/test_deletion_dsr_migration.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

API_ROOT = Path(__file__).resolve().parents[2]
PRIVACY_TABLES = {
    "deletion_requests",
    "deletion_tombstones",
    "deletion_subprocessor_receipts",
    "deletion_proofs",
    "deletion_replay_runs",
    "deletion_replay_items",
    "dsr_cases",
    "privacy_audit_events",
}


def _sync_url(async_url: str) -> str:
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def test_upgrade_creates_privacy_tables_and_keeps_legal_holds(
    postgres_database_url: str,
) -> None:
    engine = create_engine(_sync_url(postgres_database_url))
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert PRIVACY_TABLES <= tables
    assert "legal_holds" in tables


def test_privacy_audit_events_are_append_only(postgres_database_url: str) -> None:
    engine = create_engine(_sync_url(postgres_database_url))
    owner_id = "44444444-4444-4444-4444-444444444444"
    event_id = "11111111-1111-1111-1111-111111111111"
    workspace_id = "22222222-2222-2222-2222-222222222222"
    stream_id = "33333333-3333-3333-3333-333333333333"
    insert = sa.text(
        """
        INSERT INTO privacy_audit_events (
            id, workspace_id, stream_type, stream_id, sequence_number,
            previous_event_digest, event_digest, event_type, actor_user_id,
            actor_kind, payload, occurred_at
        ) VALUES (
            :id, :workspace_id, 'deletion_request', :stream_id, 1,
            NULL, 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'deletion_request_created', NULL, 'system',
            '{}'::json, now()
        )
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, email, password_hash, name, status) "
                    "VALUES (:owner_id, 'audit-owner@example.com', 'x', 'Audit Owner', 'active') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"owner_id": owner_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO workspaces (id, name, slug, owner_id) "
                    "VALUES (:workspace_id, 'Audit WS', 'audit-ws', :owner_id) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"workspace_id": workspace_id, "owner_id": owner_id},
            )
            connection.execute(
                insert,
                {"id": event_id, "workspace_id": workspace_id, "stream_id": stream_id},
            )
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(
                    sa.text("UPDATE privacy_audit_events SET event_type = 'tampered'")
                )
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            with engine.begin() as connection:
                connection.execute(sa.text("DELETE FROM privacy_audit_events"))
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "DO $$ BEGIN "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    "'dih_privacy_audit_cleaner') THEN "
                    "CREATE ROLE dih_privacy_audit_cleaner NOLOGIN; "
                    "END IF; END $$;"
                )
            )
            connection.execute(
                sa.text("GRANT USAGE ON SCHEMA public TO dih_privacy_audit_cleaner")
            )
            connection.execute(
                sa.text(
                    "GRANT SELECT, DELETE ON privacy_audit_events TO dih_privacy_audit_cleaner"
                )
            )
        with engine.begin() as connection:
            connection.execute(sa.text("SET ROLE dih_privacy_audit_cleaner"))
            connection.execute(
                sa.text("DELETE FROM privacy_audit_events WHERE id = :id"), {"id": event_id}
            )
            connection.execute(sa.text("RESET ROLE"))
        with engine.connect() as connection:
            remaining = connection.execute(
                sa.text("SELECT count(*) FROM privacy_audit_events WHERE id = :id"),
                {"id": event_id},
            ).scalar_one()
        assert remaining == 0
    finally:
        engine.dispose()


def test_report_triggers_preserve_retention_and_deletion_exceptions(
    postgres_database_url: str,
) -> None:
    _alembic(postgres_database_url, "downgrade", "202610220067")
    _alembic(postgres_database_url, "upgrade", "head")

    engine = create_engine(_sync_url(postgres_database_url))
    owner_id = "55555555-5555-5555-5555-555555555555"
    workspace_id = "66666666-6666-6666-6666-666666666666"
    project_id = "77777777-7777-7777-7777-777777777777"
    report_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    old_event_id = "88888888-8888-8888-8888-888888888888"
    fresh_event_id = "99999999-9999-9999-9999-999999999999"
    scrub_event_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    delete_event_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    artifact_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    insert_event = sa.text(
        """
        INSERT INTO report_audit_events (
            id, workspace_id, report_id, event_type, metadata_json, created_at
        ) VALUES (
            :id, :workspace_id, :report_id, 'report_published',
            '{"consumer_email": "customer@example.com"}',
            now() - (:age_days * interval '1 day')
        )
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, email, password_hash, name, status) "
                    "VALUES (:owner_id, 'trigger-owner@example.com', 'x', "
                    "'Trigger Owner', 'active') ON CONFLICT (id) DO NOTHING"
                ),
                {"owner_id": owner_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO workspaces (id, name, slug, owner_id) "
                    "VALUES (:workspace_id, 'Trigger WS', 'trigger-ws', :owner_id) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"workspace_id": workspace_id, "owner_id": owner_id},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO projects (id, workspace_id, name, domain, owner_id) "
                    "VALUES (:project_id, :workspace_id, 'Trigger Project', 'generic', "
                    ":owner_id) ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "project_id": project_id,
                    "workspace_id": workspace_id,
                    "owner_id": owner_id,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO reports (id, workspace_id, project_id, report_type, "
                    "title, content, status, period_start, period_end) VALUES "
                    "(:report_id, :workspace_id, :project_id, 'custom', 'Trigger Report', "
                    "'', 'generated', now() - interval '1 day', now()) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "report_id": report_id,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                },
            )
            connection.execute(
                insert_event,
                {
                    "id": old_event_id,
                    "report_id": report_id,
                    "workspace_id": workspace_id,
                    "age_days": 731,
                },
            )
            connection.execute(
                insert_event,
                {
                    "id": fresh_event_id,
                    "report_id": report_id,
                    "workspace_id": workspace_id,
                    "age_days": 0,
                },
            )
            connection.execute(
                insert_event,
                {
                    "id": scrub_event_id,
                    "report_id": report_id,
                    "workspace_id": workspace_id,
                    "age_days": 0,
                },
            )
            connection.execute(
                insert_event,
                {
                    "id": delete_event_id,
                    "report_id": report_id,
                    "workspace_id": workspace_id,
                    "age_days": 0,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO report_artifacts (
                        id, workspace_id, project_id, template_id, contract_json,
                        contract_sha256, data_sha256, report_html_sha256,
                        sop_html_sha256, combined_sha256, status,
                        published_at, published_by
                    ) VALUES (
                        :artifact_id, :workspace_id, :project_id, 'default',
                        '{}'::json, repeat('a', 64), repeat('b', 64), repeat('c', 64),
                        repeat('d', 64), repeat('e', 64), 'published', now(), :owner_id
                    )
                    """
                ),
                {
                    "artifact_id": artifact_id,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "owner_id": owner_id,
                },
            )

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "DO $$ BEGIN "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    "'dih_retention_cleaner') THEN "
                    "CREATE ROLE dih_retention_cleaner NOLOGIN; "
                    "END IF; "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    "'dih_deletion_executor') THEN "
                    "CREATE ROLE dih_deletion_executor NOLOGIN; "
                    "END IF; "
                    "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    "'c12_ordinary_role') THEN "
                    "CREATE ROLE c12_ordinary_role NOLOGIN; "
                    "END IF; END $$;"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT USAGE ON SCHEMA public TO "
                    "dih_retention_cleaner, dih_deletion_executor, c12_ordinary_role"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT SELECT, DELETE ON report_audit_events TO dih_retention_cleaner"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT SELECT, DELETE ON report_artifacts TO dih_deletion_executor"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT SELECT, UPDATE, DELETE ON report_audit_events "
                    "TO dih_deletion_executor"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT SELECT, UPDATE, DELETE ON report_audit_events, "
                    "report_artifacts TO c12_ordinary_role"
                )
            )
            connection.execute(
                sa.text(
                    "GRANT dih_retention_cleaner, dih_deletion_executor TO CURRENT_USER"
                )
            )

        with engine.begin() as connection:
            connection.execute(sa.text("SET LOCAL ROLE dih_retention_cleaner"))
            connection.execute(
                sa.text("DELETE FROM report_audit_events WHERE id = :id"),
                {"id": old_event_id},
            )
        with pytest.raises(sa.exc.DBAPIError, match="report_audit_events_append_only"):
            with engine.begin() as connection:
                connection.execute(sa.text("SET LOCAL ROLE dih_retention_cleaner"))
                connection.execute(
                    sa.text("DELETE FROM report_audit_events WHERE id = :id"),
                    {"id": fresh_event_id},
                )
        with pytest.raises(sa.exc.DBAPIError, match="report_audit_events_append_only"):
            with engine.begin() as connection:
                connection.execute(sa.text("SET LOCAL ROLE dih_retention_cleaner"))
                connection.execute(
                    sa.text(
                        "UPDATE report_audit_events SET metadata_json = '{}' "
                        "WHERE id = :id"
                    ),
                    {"id": scrub_event_id},
                )
        with pytest.raises(sa.exc.DBAPIError, match="report_audit_events_append_only"):
            with engine.begin() as connection:
                connection.execute(sa.text("SET LOCAL ROLE c12_ordinary_role"))
                connection.execute(
                    sa.text(
                        "UPDATE report_audit_events SET metadata_json = '{}' "
                        "WHERE id = :id"
                    ),
                    {"id": scrub_event_id},
                )
        with pytest.raises(sa.exc.DBAPIError, match="report_audit_events_append_only"):
            with engine.begin() as connection:
                connection.execute(sa.text("SET LOCAL ROLE c12_ordinary_role"))
                connection.execute(
                    sa.text("DELETE FROM report_audit_events WHERE id = :id"),
                    {"id": fresh_event_id},
                )
        with pytest.raises(sa.exc.DBAPIError, match="report_artifact_immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text("SET LOCAL ROLE c12_ordinary_role"))
                connection.execute(
                    sa.text("DELETE FROM report_artifacts WHERE id = :id"),
                    {"id": artifact_id},
                )
        with engine.begin() as connection:
            connection.execute(sa.text("SET LOCAL ROLE dih_deletion_executor"))
            connection.execute(
                sa.text(
                    "UPDATE report_audit_events SET metadata_json = '{}' "
                    "WHERE id = :id"
                ),
                {"id": scrub_event_id},
            )
            connection.execute(
                sa.text("DELETE FROM report_audit_events WHERE id = :id"),
                {"id": delete_event_id},
            )
            connection.execute(
                sa.text("DELETE FROM report_artifacts WHERE id = :id"),
                {"id": artifact_id},
            )

        with engine.connect() as connection:
            retained_ids = {
                str(event_id)
                for event_id in connection.execute(
                    sa.text("SELECT id FROM report_audit_events")
                ).scalars()
            }
            scrub_metadata = connection.execute(
                sa.text(
                    "SELECT metadata_json FROM report_audit_events "
                    "WHERE id = :id"
                ),
                {"id": scrub_event_id},
            ).scalar_one()
            artifact_count = connection.execute(
                sa.text("SELECT count(*) FROM report_artifacts WHERE id = :id"),
                {"id": artifact_id},
            ).scalar_one()

        assert str(old_event_id) not in retained_ids
        assert str(fresh_event_id) in retained_ids
        assert str(delete_event_id) not in retained_ids
        assert scrub_metadata == "{}"
        assert artifact_count == 0
    finally:
        engine.dispose()


def _alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )


def test_downgrade_keeps_legal_holds_and_reupgrade(postgres_database_url: str) -> None:
    _alembic(postgres_database_url, "downgrade", "-1")
    engine = create_engine(_sync_url(postgres_database_url))
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            audit_function = connection.execute(
                sa.text(
                    "SELECT pg_get_functiondef("
                    "'report_audit_events_append_only_fn()'::regprocedure)"
                )
            ).scalar_one()
            artifact_function = connection.execute(
                sa.text(
                    "SELECT pg_get_functiondef("
                    "'report_artifacts_guard_published()'::regprocedure)"
                )
            ).scalar_one()
    finally:
        engine.dispose()
    assert PRIVACY_TABLES.isdisjoint(tables)
    assert "legal_holds" in tables
    assert "dih_retention_cleaner" in audit_function
    assert "730 days" in audit_function
    assert "dih_deletion_executor" not in audit_function
    assert "dih_deletion_executor" not in artifact_function
    _alembic(postgres_database_url, "upgrade", "head")
```



- [ ] **Step 8: 运行迁移测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/data_scrapy_workflow_plan_phase2_test' \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest -q tests/postgres/test_deletion_dsr_migration.py
```

Expected: FAIL。迁移 068 尚不存在，或隐私表、append-only 触发器、C11 保留期例外、执行器例外、downgrade/re-upgrade 断言失败。若受控 PostgreSQL 不可用而 skip，不能进入下一步；先准备受控测试库。

- [ ] **Step 9: 写迁移 068**

Create `apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py`。文件头：

```python
"""Create privacy deletion, DSR and privacy audit tables.

Revision ID: 202610220068
Revises: 202610220067
Create Date: 2026-10-22

This migration does not create legal holds.
C11 migration 202610220067 owns the legal_holds table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220068"
down_revision: str | None = "202610220067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_DELETION = (
    "status IN ('pending_owner_approval', 'pending_confirmation', 'ready', "
    "'blocked_legal_hold', 'executing')"
)
```

`upgrade()` 创建八张表。表顺序是 `deletion_requests`、`deletion_tombstones`、`deletion_subprocessor_receipts`、`deletion_proofs`、`deletion_replay_runs`、`deletion_replay_items`、`dsr_cases`、`privacy_audit_events`。列、约束和索引与模型同名。关键片段：

```python
def upgrade() -> None:
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confirmation_token_hash", sa.String(length=64), nullable=True),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("tombstone_digest", sa.String(length=71), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "target_type IN ('project', 'workspace')", name="ck_deletion_requests_target_type"
        ),
        sa.CheckConstraint(
            "requested_by_role IN ('owner', 'admin')",
            name="ck_deletion_requests_requested_by_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending_owner_approval', 'pending_confirmation', 'ready', "
            "'blocked_legal_hold', 'executing', 'completed', 'failed', 'rejected', 'cancelled')",
            name="ck_deletion_requests_status",
        ),
        sa.CheckConstraint(
            "(target_type = 'project' AND project_id IS NOT NULL AND target_id = project_id) "
            "OR (target_type = 'workspace' AND project_id IS NULL AND target_id = workspace_id)",
            name="ck_deletion_requests_target_scope",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_deletion_requests_active_target",
        "deletion_requests",
        ["workspace_id", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_DELETION),
        sqlite_where=sa.text(ACTIVE_DELETION),
    )

    op.create_table(
        "deletion_tombstones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("object_class", sa.String(length=60), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(length=71), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["deletion_request_id"], ["deletion_requests.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deletion_request_id",
            "object_class",
            "target_id",
            name="uq_deletion_tombstones_request_class_target",
        ),
    )

    op.create_table(
        "deletion_subprocessor_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("subprocessor_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("request_reference", sa.String(length=200), nullable=True),
        sa.Column("receipt_reference", sa.String(length=200), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("recorded_by_operator", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'requested', 'acknowledged', 'not_applicable')",
            name="ck_deletion_subprocessor_receipts_status",
        ),
        sa.ForeignKeyConstraint(["deletion_request_id"], ["deletion_requests.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deletion_request_id",
            "subprocessor_name",
            name="uq_deletion_subprocessor_receipts_request_name",
        ),
    )

    op.create_table(
        "deletion_proofs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("proof_number", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("proof_digest", sa.String(length=71), nullable=False),
        sa.Column("audit_head_digest", sa.String(length=71), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["deletion_request_id"], ["deletion_requests.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deletion_request_id", name="uq_deletion_proofs_request"),
        sa.UniqueConstraint("proof_number", name="uq_deletion_proofs_number"),
    )

    op.create_table(
        "deletion_replay_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("manifest_digest", sa.String(length=71), nullable=False),
        sa.Column("source_backup_ref", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("replayed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("operator_label", sa.String(length=200), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_deletion_replay_runs_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deletion_replay_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('replayed', 'skipped_absent', 'failed')",
            name="ck_deletion_replay_items_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["deletion_replay_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "target_type", "target_id", name="uq_deletion_replay_items_run_target"
        ),
    )

    op.create_table(
        "dsr_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("case_number", sa.String(length=40), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("responsibility", sa.String(length=20), nullable=False),
        sa.Column("requester_ref", sa.String(length=200), nullable=False),
        sa.Column("verification_method", sa.String(length=80), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_request_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_by_operator", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "request_type IN ('access', 'rectification', 'restriction', 'deletion')",
            name="ck_dsr_cases_request_type",
        ),
        sa.CheckConstraint(
            "status IN ('received', 'verifying', 'in_progress', 'completed', 'rejected', 'closed')",
            name="ck_dsr_cases_status",
        ),
        sa.CheckConstraint(
            "responsibility IN ('controller', 'processor', 'undetermined')",
            name="ck_dsr_cases_responsibility",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["deletion_request_id"], ["deletion_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_number", name="uq_dsr_cases_number"),
    )

    op.create_table(
        "privacy_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("stream_type", sa.String(length=30), nullable=False),
        sa.Column("stream_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("previous_event_digest", sa.String(length=71), nullable=True),
        sa.Column("event_digest", sa.String(length=71), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_kind", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("sequence_number >= 1", name="ck_privacy_audit_events_sequence"),
        sa.CheckConstraint(
            "(sequence_number = 1 AND previous_event_digest IS NULL) "
            "OR (sequence_number > 1 AND previous_event_digest IS NOT NULL)",
            name="ck_privacy_audit_events_predecessor",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'operator', 'system')",
            name="ck_privacy_audit_events_actor_kind",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "stream_type", "stream_id", "previous_event_digest"],
            [
                "privacy_audit_events.workspace_id",
                "privacy_audit_events.stream_type",
                "privacy_audit_events.stream_id",
                "privacy_audit_events.event_digest",
            ],
            name="fk_privacy_audit_events_predecessor",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "stream_type",
            "stream_id",
            "sequence_number",
            name="uq_privacy_audit_events_stream_sequence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "stream_type",
            "stream_id",
            "event_digest",
            name="uq_privacy_audit_events_stream_digest",
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION privacy_audit_events_guard()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'privacy_audit_events is append-only';
                END IF;
                IF current_user <> 'dih_privacy_audit_cleaner' THEN
                    RAISE EXCEPTION 'privacy_audit_events is append-only';
                END IF;
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER privacy_audit_events_append_only
            BEFORE UPDATE OR DELETE ON privacy_audit_events
            FOR EACH ROW EXECUTE FUNCTION privacy_audit_events_guard();
            """
        )
```

068 还必须在 PostgreSQL 上替换 C9 的两个触发器函数。替换保留 C9 对普通角色原有的 UPDATE 限制，并保留 C11 的 067 `dih_retention_cleaner` 过期删除例外。只增加 `current_user = 'dih_deletion_executor'` 的例外：`report_artifacts` 允许 DELETE，`report_audit_events` 允许 UPDATE 与 DELETE。普通角色和 `dih_retention_cleaner` 的 UPDATE 仍抛出异常。不得放宽普通应用角色的删除或改写权限。

```python
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION report_artifacts_guard_published()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF current_user = 'dih_deletion_executor' THEN
                        RETURN OLD;
                    END IF;
                    IF OLD.status <> 'draft' THEN
                        RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                    END IF;
                    RETURN OLD;
                END IF;
                IF OLD.status = 'superseded' THEN
                    RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                END IF;
                IF OLD.status = 'published' THEN
                    IF NEW.status NOT IN ('published', 'superseded') THEN
                        RAISE EXCEPTION 'report_artifact_status_transition_invalid: %', OLD.id;
                    END IF;
                    IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
                       OR NEW.project_id IS DISTINCT FROM OLD.project_id
                       OR NEW.run_id IS DISTINCT FROM OLD.run_id
                       OR NEW.report_id IS DISTINCT FROM OLD.report_id
                       OR NEW.template_id IS DISTINCT FROM OLD.template_id
                       OR NEW.version IS DISTINCT FROM OLD.version
                       OR NEW.contract_json IS DISTINCT FROM OLD.contract_json
                       OR NEW.contract_sha256 IS DISTINCT FROM OLD.contract_sha256
                       OR NEW.data_sha256 IS DISTINCT FROM OLD.data_sha256
                       OR NEW.report_html_sha256 IS DISTINCT FROM OLD.report_html_sha256
                       OR NEW.sop_html_sha256 IS DISTINCT FROM OLD.sop_html_sha256
                       OR NEW.combined_sha256 IS DISTINCT FROM OLD.combined_sha256
                       OR NEW.report_html IS DISTINCT FROM OLD.report_html
                       OR NEW.sop_html IS DISTINCT FROM OLD.sop_html
                       OR NEW.created_at IS DISTINCT FROM OLD.created_at
                       OR NEW.created_by IS DISTINCT FROM OLD.created_by
                       OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id
                       OR NEW.published_at IS DISTINCT FROM OLD.published_at
                       OR NEW.published_by IS DISTINCT FROM OLD.published_by
                    THEN
                        RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE'
                   AND current_user = 'dih_retention_cleaner'
                   AND OLD.created_at < now() - interval '730 days' THEN
                    RETURN OLD;
                END IF;
                IF current_user = 'dih_deletion_executor' THEN
                    IF TG_OP = 'DELETE' THEN
                        RETURN OLD;
                    END IF;
                    IF TG_OP = 'UPDATE' THEN
                        RETURN NEW;
                    END IF;
                END IF;
                RAISE EXCEPTION 'report_audit_events_append_only: %', OLD.id;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
```

`downgrade()` 必须把 C9/C11 的触发器函数恢复到 067 的状态。`report_audit_events_append_only_fn()` 恢复 C11 的 067 定义：`dih_retention_cleaner` 只能 DELETE `OLD.created_at < now() - interval '730 days'` 的行；其余 DELETE 与 UPDATE 仍抛出异常。`report_artifacts_guard_published()` 恢复 C9 的 065 定义；C11 的 067 没有替换该函数。不得恢复成 C9 的严格 065 审计函数，否则 067 的保留期清理会失效。

生产不执行 downgrade 068。生产回滚是关闭 `PRIVACY_DELETION_ENABLED` 并回退应用版本，保留 068 已建的表和触发器。运行手册必须写明这一点。

`downgrade()` 只删除 068 的八张表和触发器，不删除 `legal_holds`：

```python
def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
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
        op.execute(
            """
            CREATE OR REPLACE FUNCTION report_artifacts_guard_published()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status <> 'draft' THEN
                        RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                    END IF;
                    RETURN OLD;
                END IF;
                IF OLD.status = 'superseded' THEN
                    RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                END IF;
                IF OLD.status = 'published' THEN
                    IF NEW.status NOT IN ('published', 'superseded') THEN
                        RAISE EXCEPTION 'report_artifact_status_transition_invalid: %', OLD.id;
                    END IF;
                    IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
                       OR NEW.project_id IS DISTINCT FROM OLD.project_id
                       OR NEW.run_id IS DISTINCT FROM OLD.run_id
                       OR NEW.report_id IS DISTINCT FROM OLD.report_id
                       OR NEW.template_id IS DISTINCT FROM OLD.template_id
                       OR NEW.version IS DISTINCT FROM OLD.version
                       OR NEW.contract_json IS DISTINCT FROM OLD.contract_json
                       OR NEW.contract_sha256 IS DISTINCT FROM OLD.contract_sha256
                       OR NEW.data_sha256 IS DISTINCT FROM OLD.data_sha256
                       OR NEW.report_html_sha256 IS DISTINCT FROM OLD.report_html_sha256
                       OR NEW.sop_html_sha256 IS DISTINCT FROM OLD.sop_html_sha256
                       OR NEW.combined_sha256 IS DISTINCT FROM OLD.combined_sha256
                       OR NEW.report_html IS DISTINCT FROM OLD.report_html
                       OR NEW.sop_html IS DISTINCT FROM OLD.sop_html
                       OR NEW.created_at IS DISTINCT FROM OLD.created_at
                       OR NEW.created_by IS DISTINCT FROM OLD.created_by
                       OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id
                       OR NEW.published_at IS DISTINCT FROM OLD.published_at
                       OR NEW.published_by IS DISTINCT FROM OLD.published_by
                    THEN
                        RAISE EXCEPTION 'report_artifact_immutable: %', OLD.id;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            "DROP TRIGGER IF EXISTS privacy_audit_events_append_only ON privacy_audit_events"
        )
        op.execute("DROP FUNCTION IF EXISTS privacy_audit_events_guard()")
    op.drop_table("privacy_audit_events")
    op.drop_table("dsr_cases")
    op.drop_table("deletion_replay_items")
    op.drop_table("deletion_replay_runs")
    op.drop_table("deletion_proofs")
    op.drop_table("deletion_subprocessor_receipts")
    op.drop_table("deletion_tombstones")
    op.drop_index("uq_deletion_requests_active_target", table_name="deletion_requests")
    op.drop_table("deletion_requests")
```

- [ ] **Step 10: 运行模型测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_models.py tests/unit/test_c12_contract_registration.py
```

Expected: `9 passed`。


- [ ] **Step 11: 运行迁移测试确认通过**

按 Step 9 的完整 068 内容补齐迁移，然后运行：

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/data_scrapy_workflow_plan_phase2_test' \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest -q tests/postgres/test_deletion_dsr_migration.py
```

Expected: `4 passed`。不得把 skip 当作通过。


- [ ] **Step 12: 检查单 head**


```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run alembic heads
```

Expected: 只输出 `202610220068 (head)`。


- [ ] **Step 13: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
git diff --name-only -- 'docs/design/*契约冻结*' 'configs/contracts/v1.1.0/*'
```

Expected: 无输出。出现输出时停止，撤销对契约或 registry 的修改。

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/models/privacy_deletion.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py \
  apps/api/tests/unit/test_c12_contract_registration.py \
  apps/api/tests/unit/test_privacy_models.py \
  apps/api/tests/postgres/test_deletion_dsr_migration.py
git commit -m "feat(privacy): 添加删除与 DSR 迁移 068"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 2: 追加式隐私审计链

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/privacy_audit.py`
- Test: `apps/api/tests/unit/test_privacy_audit.py`

**Interfaces:**
- Consumes: `PrivacyAuditEvent`、`PrivacyStreamType`、`PrivacyActorKind`。
- Produces: `canonical_json`、`sha256_digest`、`append_privacy_event`、`verify_privacy_chain`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_privacy_audit.py`:

```python
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.privacy_deletion import (
    PrivacyActorKind,
    PrivacyStreamType,
)
from data_intelligence_hub.services.privacy_audit import (
    PrivacyAuditChainError,
    append_privacy_event,
    verify_privacy_chain,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


@pytest.mark.asyncio
async def test_append_builds_hash_chain(session: AsyncSession) -> None:
    workspace_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    first = await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=stream_id,
        event_type="deletion_request_created",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.SYSTEM,
        payload={"target_type": "project"},
    )
    second = await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=stream_id,
        event_type="deletion_request_confirmed",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.SYSTEM,
        payload={"to_status": "ready"},
    )
    assert first.sequence_number == 1
    assert first.previous_event_digest is None
    assert second.sequence_number == 2
    assert second.previous_event_digest == first.event_digest
    assert await verify_privacy_chain(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=stream_id,
    ) == second.event_digest


@pytest.mark.asyncio
async def test_verify_detects_tamper(session: AsyncSession) -> None:
    workspace_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    event = await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DSR_CASE,
        stream_id=stream_id,
        event_type="dsr_case_opened",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.OPERATOR,
        payload={"request_type": "access"},
    )
    event.payload = {"request_type": "deletion"}
    await session.flush()
    with pytest.raises(PrivacyAuditChainError, match="privacy_audit_chain_invalid"):
        await verify_privacy_chain(
            session,
            workspace_id=workspace_id,
            stream_type=PrivacyStreamType.DSR_CASE,
            stream_id=stream_id,
        )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_audit.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.privacy_audit`。

- [ ] **Step 3: 实现审计服务**

Create `apps/api/src/data_intelligence_hub/services/privacy_audit.py`:

```python
"""追加式隐私审计链。

事件摘要覆盖工作区、流、序号、前序摘要、事件类型、主体、载荷和时间。
调用方必须先在同一个事务内锁定被审计的主体行，再调用本模块，
避免同一流并发写。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    PrivacyActorKind,
    PrivacyAuditEvent,
    PrivacyStreamType,
)


class PrivacyAuditChainError(RuntimeError):
    """审计链校验失败。"""


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _plain(value: StrEnum | str) -> str:
    return value.value if isinstance(value, StrEnum) else value


def _material(
    *,
    workspace_id: uuid.UUID,
    stream_type: str,
    stream_id: uuid.UUID,
    sequence_number: int,
    previous_event_digest: str | None,
    event_type: str,
    actor_user_id: uuid.UUID | None,
    actor_kind: str,
    payload: Mapping[str, Any],
    occurred_at: datetime,
) -> dict[str, Any]:
    return {
        "workspace_id": str(workspace_id),
        "stream_type": stream_type,
        "stream_id": str(stream_id),
        "sequence_number": sequence_number,
        "previous_event_digest": previous_event_digest,
        "event_type": event_type,
        "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        "actor_kind": actor_kind,
        "payload": dict(payload),
        "occurred_at": occurred_at.astimezone(UTC).isoformat(),
    }


async def append_privacy_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    stream_type: PrivacyStreamType | str,
    stream_id: uuid.UUID,
    event_type: str,
    actor_user_id: uuid.UUID | None,
    actor_kind: PrivacyActorKind | str,
    payload: Mapping[str, Any],
) -> PrivacyAuditEvent:
    stream_value = _plain(stream_type)
    actor_value = _plain(actor_kind)
    result = await session.execute(
        select(PrivacyAuditEvent)
        .where(
            PrivacyAuditEvent.workspace_id == workspace_id,
            PrivacyAuditEvent.stream_type == stream_value,
            PrivacyAuditEvent.stream_id == stream_id,
        )
        .order_by(PrivacyAuditEvent.sequence_number.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()
    sequence_number = 1 if previous is None else previous.sequence_number + 1
    previous_digest = None if previous is None else previous.event_digest
    occurred_at = datetime.now(UTC)
    digest = sha256_digest(
        _material(
            workspace_id=workspace_id,
            stream_type=stream_value,
            stream_id=stream_id,
            sequence_number=sequence_number,
            previous_event_digest=previous_digest,
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_kind=actor_value,
            payload=payload,
            occurred_at=occurred_at,
        )
    )
    event = PrivacyAuditEvent(
        workspace_id=workspace_id,
        stream_type=stream_value,
        stream_id=stream_id,
        sequence_number=sequence_number,
        previous_event_digest=previous_digest,
        event_digest=digest,
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_kind=actor_value,
        payload=dict(payload),
        occurred_at=occurred_at,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_privacy_chain(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    stream_type: PrivacyStreamType | str,
    stream_id: uuid.UUID,
) -> str | None:
    stream_value = _plain(stream_type)
    result = await session.execute(
        select(PrivacyAuditEvent)
        .where(
            PrivacyAuditEvent.workspace_id == workspace_id,
            PrivacyAuditEvent.stream_type == stream_value,
            PrivacyAuditEvent.stream_id == stream_id,
        )
        .order_by(PrivacyAuditEvent.sequence_number.asc())
    )
    events = list(result.scalars().all())
    previous_digest: str | None = None
    for index, event in enumerate(events, start=1):
        if event.sequence_number != index:
            raise PrivacyAuditChainError("privacy_audit_chain_invalid")
        if event.previous_event_digest != previous_digest:
            raise PrivacyAuditChainError("privacy_audit_chain_invalid")
        expected = sha256_digest(
            _material(
                workspace_id=event.workspace_id,
                stream_type=event.stream_type,
                stream_id=event.stream_id,
                sequence_number=event.sequence_number,
                previous_event_digest=event.previous_event_digest,
                event_type=event.event_type,
                actor_user_id=event.actor_user_id,
                actor_kind=event.actor_kind,
                payload=event.payload,
                occurred_at=event.occurred_at,
            )
        )
        if expected != event.event_digest:
            raise PrivacyAuditChainError("privacy_audit_chain_invalid")
        previous_digest = event.event_digest
    return previous_digest


__all__ = [
    "PrivacyAuditChainError",
    "append_privacy_event",
    "canonical_json",
    "sha256_digest",
    "verify_privacy_chain",
]
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_audit.py
```

Expected: `2 passed`。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/privacy_audit.py \
  apps/api/tests/unit/test_privacy_audit.py
git commit -m "feat(privacy): 添加追加式隐私审计链"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 3: 删除请求状态机、二次确认与法律保留只读检查

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/deletion_service.py`
- Test: `apps/api/tests/unit/test_deletion_service.py`

**Interfaces:**
- Consumes: `DeletionRequest`、`DeletionRequestStatus`、`append_privacy_event`、C11 `list_active_legal_holds`、C2 `get_workspace_role`。
- Produces: 跨任务接口中的状态机函数与 `active_hold_count`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_deletion_service.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequestStatus,
    DeletionTargetType,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.retention import LegalHold
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.deletion_service import (
    DeletionStateError,
    approve_deletion_request,
    confirm_deletion_request,
    create_deletion_request,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed(session: AsyncSession) -> dict[str, uuid.UUID]:
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session.add_all(
        [
            User(id=owner_id, email="owner@example.com", password_hash="x", name="Owner"),
            User(id=admin_id, email="admin@example.com", password_hash="x", name="Admin"),
            User(id=member_id, email="member@example.com", password_hash="x", name="Member"),
            Workspace(id=workspace_id, name="WS", slug="ws", owner_id=owner_id),
            WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role="owner"),
            WorkspaceMember(workspace_id=workspace_id, user_id=admin_id, role="admin"),
            WorkspaceMember(workspace_id=workspace_id, user_id=member_id, role="member"),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                name="母婴新品",
                domain="ecommerce",
                status="active",
                owner_id=owner_id,
            ),
        ]
    )
    await session.commit()
    return {
        "owner": owner_id,
        "admin": admin_id,
        "member": member_id,
        "workspace": workspace_id,
        "project": project_id,
    }


@pytest.mark.asyncio
async def test_owner_create_then_confirm(session: AsyncSession) -> None:
    ids = await _seed(session)
    created = await create_deletion_request(
        session,
        workspace_id=ids["workspace"],
        requested_by_user_id=ids["owner"],
        target_type=DeletionTargetType.PROJECT,
        project_id=ids["project"],
        reason="客户要求",
    )
    assert created.request.status == DeletionRequestStatus.PENDING_CONFIRMATION.value
    assert created.confirmation_token is not None
    assert created.confirmation_phrase == "DELETE 母婴新品"

    with pytest.raises(DeletionStateError) as wrong:
        await confirm_deletion_request(
            session,
            request_id=created.request.id,
            workspace_id=ids["workspace"],
            actor_user_id=ids["owner"],
            token=created.confirmation_token,
            confirmation_text="DELETE 另一个项目",
        )
    assert wrong.value.code == "deletion_confirmation_text_mismatch"

    confirmed = await confirm_deletion_request(
        session,
        request_id=created.request.id,
        workspace_id=ids["workspace"],
        actor_user_id=ids["owner"],
        token=created.confirmation_token,
        confirmation_text="DELETE 母婴新品",
    )
    assert confirmed.status == DeletionRequestStatus.READY.value
    assert confirmed.confirmed_at is not None
    assert confirmed.confirmation_token_hash is None


@pytest.mark.asyncio
async def test_admin_request_needs_owner_approval(session: AsyncSession) -> None:
    ids = await _seed(session)
    created = await create_deletion_request(
        session,
        workspace_id=ids["workspace"],
        requested_by_user_id=ids["admin"],
        target_type=DeletionTargetType.PROJECT,
        project_id=ids["project"],
        reason=None,
    )
    assert created.request.status == DeletionRequestStatus.PENDING_OWNER_APPROVAL.value
    assert created.confirmation_token is None

    with pytest.raises(DeletionStateError) as not_owner:
        await approve_deletion_request(
            session,
            request_id=created.request.id,
            workspace_id=ids["workspace"],
            actor_user_id=ids["admin"],
            decision="approve",
        )
    assert not_owner.value.code == "workspace_owner_required"

    approved = await approve_deletion_request(
        session,
        request_id=created.request.id,
        workspace_id=ids["workspace"],
        actor_user_id=ids["owner"],
        decision="approve",
    )
    assert approved.request.status == DeletionRequestStatus.PENDING_CONFIRMATION.value
    assert approved.confirmation_token is not None


@pytest.mark.asyncio
async def test_expired_confirmation_is_rejected(session: AsyncSession) -> None:
    ids = await _seed(session)
    created = await create_deletion_request(
        session,
        workspace_id=ids["workspace"],
        requested_by_user_id=ids["owner"],
        target_type=DeletionTargetType.PROJECT,
        project_id=ids["project"],
        reason=None,
    )
    created.request.confirmation_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()
    with pytest.raises(DeletionStateError) as expired:
        await confirm_deletion_request(
            session,
            request_id=created.request.id,
            workspace_id=ids["workspace"],
            actor_user_id=ids["owner"],
            token=created.confirmation_token,
            confirmation_text="DELETE 母婴新品",
        )
    assert expired.value.code == "deletion_confirmation_expired"


@pytest.mark.asyncio
async def test_active_legal_hold_blocks_confirmation(session: AsyncSession) -> None:
    ids = await _seed(session)
    session.add(
        LegalHold(
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            data_class="raw_response",
            status="active",
            reason="诉讼",
            requested_by_user_id=ids["owner"],
            requested_at=datetime.now(UTC),
        )
    )
    await session.flush()
    created = await create_deletion_request(
        session,
        workspace_id=ids["workspace"],
        requested_by_user_id=ids["owner"],
        target_type=DeletionTargetType.PROJECT,
        project_id=ids["project"],
        reason=None,
    )
    confirmed = await confirm_deletion_request(
        session,
        request_id=created.request.id,
        workspace_id=ids["workspace"],
        actor_user_id=ids["owner"],
        token=created.confirmation_token,
        confirmation_text="DELETE 母婴新品",
    )
    assert confirmed.status == DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value


@pytest.mark.asyncio
async def test_member_cannot_create(session: AsyncSession) -> None:
    ids = await _seed(session)
    with pytest.raises(DeletionStateError) as forbidden:
        await create_deletion_request(
            session,
            workspace_id=ids["workspace"],
            requested_by_user_id=ids["member"],
            target_type=DeletionTargetType.PROJECT,
            project_id=ids["project"],
            reason=None,
        )
    assert forbidden.value.code == "workspace_role_forbidden"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_service.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.deletion_service`。

- [ ] **Step 3: 实现状态机**

Create `apps/api/src/data_intelligence_hub/services/deletion_service.py`:

```python
"""删除请求状态机。

owner 创建后进入 pending_confirmation；admin 创建后进入
pending_owner_approval。确认挑战只存 sha256，明文只返回一次。
状态机只读检查 C11 的 active 法律保留，不写法律保留。
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequest,
    DeletionRequestStatus,
    DeletionRequesterRole,
    DeletionTargetType,
    PrivacyActorKind,
    PrivacyStreamType,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.retention import LegalHold
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.services.legal_hold_service import list_active_legal_holds
from data_intelligence_hub.services.privacy_audit import append_privacy_event

CONFIRMATION_TTL = timedelta(minutes=15)
ACTIVE_RUN_STATUSES = ("queued", "running")
ACTIVE_STATUSES = (
    DeletionRequestStatus.PENDING_OWNER_APPROVAL.value,
    DeletionRequestStatus.PENDING_CONFIRMATION.value,
    DeletionRequestStatus.READY.value,
    DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value,
    DeletionRequestStatus.EXECUTING.value,
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    DeletionRequestStatus.PENDING_OWNER_APPROVAL.value: frozenset(
        {
            DeletionRequestStatus.PENDING_CONFIRMATION.value,
            DeletionRequestStatus.REJECTED.value,
        }
    ),
    DeletionRequestStatus.PENDING_CONFIRMATION.value: frozenset(
        {
            DeletionRequestStatus.READY.value,
            DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value,
            DeletionRequestStatus.CANCELLED.value,
        }
    ),
    DeletionRequestStatus.READY.value: frozenset(
        {
            DeletionRequestStatus.EXECUTING.value,
            DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value,
            DeletionRequestStatus.CANCELLED.value,
        }
    ),
    DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value: frozenset(
        {DeletionRequestStatus.READY.value, DeletionRequestStatus.CANCELLED.value}
    ),
    DeletionRequestStatus.EXECUTING.value: frozenset(
        {DeletionRequestStatus.COMPLETED.value, DeletionRequestStatus.FAILED.value}
    ),
    DeletionRequestStatus.FAILED.value: frozenset(
        {DeletionRequestStatus.READY.value, DeletionRequestStatus.CANCELLED.value}
    ),
    DeletionRequestStatus.COMPLETED.value: frozenset(),
    DeletionRequestStatus.REJECTED.value: frozenset(),
    DeletionRequestStatus.CANCELLED.value: frozenset(),
}


class DeletionStateError(Exception):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclasses.dataclass(frozen=True, slots=True)
class CreatedDeletionRequest:
    request: DeletionRequest
    confirmation_token: str | None
    confirmation_phrase: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _role(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> str:
    role = await get_workspace_role(session, workspace_id, user_id)
    if role is None:
        raise DeletionStateError("workspace_membership_required", 403)
    return role


def _require_role(actual: str, allowed: set[str], code: str) -> None:
    if actual not in allowed:
        raise DeletionStateError(code, 403)


def _transition(record: DeletionRequest, target: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(record.status, frozenset())
    if target not in allowed:
        raise DeletionStateError("deletion_request_state_conflict", 409)
    record.status = target


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_token(record: DeletionRequest) -> str:
    token = secrets.token_urlsafe(32)
    record.confirmation_token_hash = _hash_token(token)
    record.confirmation_expires_at = _now() + CONFIRMATION_TTL
    return token


def _confirmation_phrase(record: DeletionRequest) -> str:
    return f"DELETE {record.target_name_snapshot}"


async def active_hold_count(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
) -> int:
    """返回适用于目标的 active 法律保留数量。只读，不写。"""

    holds: list[LegalHold] = await list_active_legal_holds(
        session, workspace_id=workspace_id
    )
    if project_id is None:
        return len(holds)
    return sum(1 for hold in holds if hold.project_id is None or hold.project_id == project_id)


async def _target_name(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    target_type: str,
    project_id: uuid.UUID | None,
) -> tuple[str, uuid.UUID, uuid.UUID | None]:
    if target_type == DeletionTargetType.PROJECT.value:
        if project_id is None:
            raise DeletionStateError("deletion_project_id_required", 400)
        project = await session.get(Project, project_id)
        if project is None or project.workspace_id != workspace_id or project.status == "deleted":
            raise DeletionStateError("project_not_found", 404)
        return project.name, project.id, project.id
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise DeletionStateError("workspace_not_found", 404)
    return workspace.name, workspace.id, None


async def _active_request_exists(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(DeletionRequest.id)
        .where(
            DeletionRequest.workspace_id == workspace_id,
            DeletionRequest.target_type == target_type,
            DeletionRequest.target_id == target_id,
            DeletionRequest.status.in_(ACTIVE_STATUSES),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _completed_request_exists(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(DeletionRequest.id)
        .where(
            DeletionRequest.workspace_id == workspace_id,
            DeletionRequest.target_type == target_type,
            DeletionRequest.target_id == target_id,
            DeletionRequest.status == DeletionRequestStatus.COMPLETED.value,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _ensure_no_active_runs(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    target_type: str,
    project_id: uuid.UUID | None,
) -> None:
    statement = select(Run.id).where(
        Run.workspace_id == workspace_id,
        Run.status.in_(ACTIVE_RUN_STATUSES),
    )
    if target_type == DeletionTargetType.PROJECT.value:
        statement = statement.where(Run.project_id == project_id)
    result = await session.execute(statement.limit(1))
    if result.scalar_one_or_none() is not None:
        raise DeletionStateError("deletion_target_has_active_runs", 409)


async def _audit(
    session: AsyncSession,
    record: DeletionRequest,
    *,
    event_type: str,
    actor_user_id: uuid.UUID | None,
    actor_kind: PrivacyActorKind,
    payload: dict[str, object],
) -> None:
    await append_privacy_event(
        session,
        workspace_id=record.workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=record.id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_kind=actor_kind,
        payload=payload,
    )


async def create_deletion_request(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    target_type: DeletionTargetType,
    project_id: uuid.UUID | None,
    reason: str | None,
) -> CreatedDeletionRequest:
    actual_role = await _role(session, workspace_id, requested_by_user_id)
    _require_role(actual_role, {"owner", "admin"}, "workspace_role_forbidden")
    target_name, target_id, scoped_project_id = await _target_name(
        session, workspace_id=workspace_id, target_type=target_type.value, project_id=project_id
    )
    if await _completed_request_exists(
        session,
        workspace_id=workspace_id,
        target_type=target_type.value,
        target_id=target_id,
    ):
        raise DeletionStateError("deletion_target_already_deleted", 409)
    if await _active_request_exists(
        session,
        workspace_id=workspace_id,
        target_type=target_type.value,
        target_id=target_id,
    ):
        raise DeletionStateError("deletion_request_active_exists", 409)
    await _ensure_no_active_runs(
        session,
        workspace_id=workspace_id,
        target_type=target_type.value,
        project_id=scoped_project_id,
    )
    status = (
        DeletionRequestStatus.PENDING_CONFIRMATION.value
        if actual_role == DeletionRequesterRole.OWNER.value
        else DeletionRequestStatus.PENDING_OWNER_APPROVAL.value
    )
    record = DeletionRequest(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=scoped_project_id,
        target_type=target_type.value,
        target_id=target_id,
        target_name_snapshot=target_name,
        requested_by_user_id=requested_by_user_id,
        requested_by_role=actual_role,
        status=status,
        reason=reason,
    )
    session.add(record)
    await session.flush()
    token: str | None = None
    if actual_role == DeletionRequesterRole.OWNER.value:
        token = _issue_token(record)
    await _audit(
        session,
        record,
        event_type="deletion_request_created",
        actor_user_id=requested_by_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={
            "target_type": record.target_type,
            "target_id": str(record.target_id),
            "requested_by_role": record.requested_by_role,
        },
    )
    return CreatedDeletionRequest(
        request=record,
        confirmation_token=token,
        confirmation_phrase=_confirmation_phrase(record) if token else None,
    )


async def _lock_request(
    session: AsyncSession, request_id: uuid.UUID, workspace_id: uuid.UUID
) -> DeletionRequest:
    result = await session.execute(
        select(DeletionRequest)
        .where(
            DeletionRequest.id == request_id,
            DeletionRequest.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise DeletionStateError("deletion_request_not_found", 404)
    return record


async def approve_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    decision: str,
    reason: str | None = None,
) -> CreatedDeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    if record.requested_by_user_id == actor_user_id:
        raise DeletionStateError("deletion_self_approval_forbidden", 403)
    if record.status != DeletionRequestStatus.PENDING_OWNER_APPROVAL.value:
        raise DeletionStateError("deletion_request_state_conflict", 409)
    if decision not in {"approve", "reject"}:
        raise DeletionStateError("deletion_decision_invalid", 400)
    if decision == "reject":
        _transition(record, DeletionRequestStatus.REJECTED.value)
        record.decided_at = _now()
        record.rejection_reason = reason
        await _audit(
            session,
            record,
            event_type="deletion_request_rejected",
            actor_user_id=actor_user_id,
            actor_kind=PrivacyActorKind.USER,
            payload={"from_status": "pending_owner_approval", "to_status": "rejected"},
        )
        return CreatedDeletionRequest(record, None, None)
    _transition(record, DeletionRequestStatus.PENDING_CONFIRMATION.value)
    record.approved_by_user_id = actor_user_id
    record.approved_at = _now()
    token = _issue_token(record)
    await _audit(
        session,
        record,
        event_type="deletion_request_approved",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"from_status": "pending_owner_approval", "to_status": "pending_confirmation"},
    )
    return CreatedDeletionRequest(record, token, _confirmation_phrase(record))


async def confirm_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    token: str,
    confirmation_text: str,
) -> DeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    if record.status != DeletionRequestStatus.PENDING_CONFIRMATION.value:
        raise DeletionStateError("deletion_request_state_conflict", 409)
    if record.confirmation_token_hash is None or record.confirmation_expires_at is None:
        raise DeletionStateError("deletion_confirmation_not_issued", 409)
    if _as_utc(record.confirmation_expires_at) <= _now():
        raise DeletionStateError("deletion_confirmation_expired", 410)
    if not hmac.compare_digest(record.confirmation_token_hash, _hash_token(token)):
        raise DeletionStateError("deletion_confirmation_token_invalid", 403)
    if confirmation_text != _confirmation_phrase(record):
        raise DeletionStateError("deletion_confirmation_text_mismatch", 400)
    hold_count = await active_hold_count(
        session, workspace_id=workspace_id, project_id=record.project_id
    )
    target = (
        DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value
        if hold_count
        else DeletionRequestStatus.READY.value
    )
    _transition(record, target)
    record.confirmation_token_hash = None
    record.confirmation_expires_at = None
    record.confirmed_by_user_id = actor_user_id
    record.confirmed_at = _now()
    await _audit(
        session,
        record,
        event_type="deletion_request_confirmed",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"to_status": target, "legal_hold_count": hold_count},
    )
    return record


async def resend_confirmation(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> CreatedDeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    if record.status != DeletionRequestStatus.PENDING_CONFIRMATION.value:
        raise DeletionStateError("deletion_request_state_conflict", 409)
    token = _issue_token(record)
    await _audit(
        session,
        record,
        event_type="deletion_confirmation_resent",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={},
    )
    return CreatedDeletionRequest(record, token, _confirmation_phrase(record))


async def cancel_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> DeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    _transition(record, DeletionRequestStatus.CANCELLED.value)
    record.decided_at = _now()
    record.rejection_reason = reason
    await _audit(
        session,
        record,
        event_type="deletion_request_cancelled",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"reason_provided": reason is not None},
    )
    return record


async def retry_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> DeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    _transition(record, DeletionRequestStatus.READY.value)
    record.failure_code = None
    record.failure_detail = None
    record.failed_at = None
    await _audit(
        session,
        record,
        event_type="deletion_request_retried",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"to_status": "ready"},
    )
    return record


async def reevaluate_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> DeletionRequest:
    actual_role = await _role(session, workspace_id, actor_user_id)
    _require_role(actual_role, {"owner"}, "workspace_owner_required")
    record = await _lock_request(session, request_id, workspace_id)
    if record.status != DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value:
        raise DeletionStateError("deletion_request_state_conflict", 409)
    hold_count = await active_hold_count(
        session, workspace_id=workspace_id, project_id=record.project_id
    )
    if hold_count:
        raise DeletionStateError("legal_hold_active", 409)
    _transition(record, DeletionRequestStatus.READY.value)
    await _audit(
        session,
        record,
        event_type="deletion_request_reevaluated",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"to_status": "ready"},
    )
    return record


async def mark_deletion_failed(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    code: str,
) -> DeletionRequest:
    record = await _lock_request(session, request_id, workspace_id)
    if record.status != DeletionRequestStatus.EXECUTING.value:
        return record
    _transition(record, DeletionRequestStatus.FAILED.value)
    record.failed_at = _now()
    record.failure_code = code
    record.failure_detail = None
    await _audit(
        session,
        record,
        event_type="deletion_request_failed",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"failure_code": code},
    )
    return record


__all__ = [
    "ACTIVE_STATUSES",
    "ALLOWED_TRANSITIONS",
    "CONFIRMATION_TTL",
    "CreatedDeletionRequest",
    "DeletionStateError",
    "active_hold_count",
    "approve_deletion_request",
    "cancel_deletion_request",
    "confirm_deletion_request",
    "create_deletion_request",
    "mark_deletion_failed",
    "reevaluate_deletion_request",
    "resend_confirmation",
    "retry_deletion_request",
]
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_service.py
```

Expected: `5 passed`。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/deletion_service.py \
  apps/api/tests/unit/test_deletion_service.py
git commit -m "feat(privacy): 添加删除请求状态机与二次确认"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 4: 子处理者回执与人工 DSR

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/subprocessor_receipts.py`
- Create: `apps/api/src/data_intelligence_hub/services/dsr_service.py`
- Test: `apps/api/tests/unit/test_subprocessor_receipts.py`
- Test: `apps/api/tests/unit/test_dsr.py`

**Interfaces:**
- Consumes: `DeletionSubprocessorReceipt`、`DsrCase`、`append_privacy_event`。
- Produces: `ReceiptError`、`record_subprocessor_receipt`、`DsrError`、`open_dsr_case`、`transition_dsr_case`。

- [ ] **Step 1: 写回执测试**

Create `apps/api/tests/unit/test_subprocessor_receipts.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequest,
    DeletionSubprocessorReceipt,
    SubprocessorReceiptStatus,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.subprocessor_receipts import (
    record_subprocessor_receipt,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed(session: AsyncSession) -> dict[str, uuid.UUID]:
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    request_id = uuid.uuid4()
    session.add_all(
        [
            User(id=owner_id, email="receipt@example.com", password_hash="x", name="Owner"),
            Workspace(id=workspace_id, name="Receipt WS", slug="receipt-ws", owner_id=owner_id),
            DeletionRequest(
                id=request_id,
                workspace_id=workspace_id,
                project_id=None,
                target_type="workspace",
                target_id=workspace_id,
                target_name_snapshot="Receipt WS",
                requested_by_user_id=owner_id,
                requested_by_role="owner",
                status="pending_confirmation",
            ),
        ]
    )
    await session.commit()
    return {"workspace": workspace_id, "request": request_id}


@pytest.mark.asyncio
async def test_receipt_is_upserted_by_subprocessor(session: AsyncSession) -> None:
    ids = await _seed(session)
    first = await record_subprocessor_receipt(
        session,
        deletion_request_id=ids["request"],
        workspace_id=ids["workspace"],
        subprocessor_name="Apify",
        status=SubprocessorReceiptStatus.REQUESTED,
        request_reference="REQ-1",
        receipt_reference=None,
        received_at=None,
        evidence_note=None,
        operator="ops@example.com",
    )
    second = await record_subprocessor_receipt(
        session,
        deletion_request_id=ids["request"],
        workspace_id=ids["workspace"],
        subprocessor_name="Apify",
        status=SubprocessorReceiptStatus.ACKNOWLEDGED,
        request_reference="REQ-1",
        receipt_reference="APIFY-1",
        received_at=datetime.now(UTC),
        evidence_note="邮件回执",
        operator="ops@example.com",
    )
    rows = list(
        (
            await session.execute(
                select(DeletionSubprocessorReceipt).where(
                    DeletionSubprocessorReceipt.deletion_request_id == ids["request"]
                )
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert first.id == second.id
    assert rows[0].status == "acknowledged"
    assert rows[0].receipt_reference == "APIFY-1"
```

- [ ] **Step 2: 写 DSR 测试**

Create `apps/api/tests/unit/test_dsr.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.privacy_deletion import DsrStatus
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.dsr_service import (
    DsrError,
    open_dsr_case,
    transition_dsr_case,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _workspace(session: AsyncSession) -> uuid.UUID:
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    session.add_all(
        [
            User(id=owner_id, email="dsr-owner@example.com", password_hash="x", name="Owner"),
            Workspace(id=workspace_id, name="DSR WS", slug="dsr-ws", owner_id=owner_id),
        ]
    )
    await session.commit()
    return workspace_id


@pytest.mark.asyncio
async def test_dsr_requires_verification_and_responsibility(session: AsyncSession) -> None:
    workspace_id = await _workspace(session)
    case = await open_dsr_case(
        session,
        workspace_id=workspace_id,
        project_id=None,
        request_type="access",
        requester_ref="TICKET-1001",
        received_at=datetime.now(UTC),
        due_at=None,
        operator="ops@example.com",
    )
    assert case.status == DsrStatus.RECEIVED.value

    with pytest.raises(DsrError, match="dsr_verification_method_required"):
        await transition_dsr_case(
            session,
            case_id=case.id,
            workspace_id=workspace_id,
            target_status=DsrStatus.VERIFYING,
            operator="ops@example.com",
        )

    case = await transition_dsr_case(
        session,
        case_id=case.id,
        workspace_id=workspace_id,
        target_status=DsrStatus.VERIFYING,
        operator="ops@example.com",
        verification_method="工单双因子核验",
    )
    with pytest.raises(DsrError, match="dsr_responsibility_required"):
        await transition_dsr_case(
            session,
            case_id=case.id,
            workspace_id=workspace_id,
            target_status=DsrStatus.IN_PROGRESS,
            operator="ops@example.com",
        )

    case = await transition_dsr_case(
        session,
        case_id=case.id,
        workspace_id=workspace_id,
        target_status=DsrStatus.IN_PROGRESS,
        operator="ops@example.com",
        responsibility="controller",
    )
    assert case.status == DsrStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_dsr_rejects_email_as_requester_ref(session: AsyncSession) -> None:
    workspace_id = await _workspace(session)
    with pytest.raises(DsrError, match="dsr_requester_ref_must_be_opaque"):
        await open_dsr_case(
            session,
            workspace_id=workspace_id,
            project_id=None,
            request_type="deletion",
            requester_ref="customer@example.com",
            received_at=datetime.now(UTC),
            due_at=None,
            operator="ops@example.com",
        )
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_subprocessor_receipts.py tests/unit/test_dsr.py
```

Expected: FAIL，两个服务模块不存在。

- [ ] **Step 4: 实现回执服务**

Create `apps/api/src/data_intelligence_hub/services/subprocessor_receipts.py`:

```python
"""子处理者删除回执的人工记录。

回执由内部运营录入。重复录入同名子处理者时更新同一行，并追加审计事件。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequest,
    DeletionSubprocessorReceipt,
    PrivacyActorKind,
    PrivacyStreamType,
    SubprocessorReceiptStatus,
)
from data_intelligence_hub.services.privacy_audit import append_privacy_event


class ReceiptError(Exception):
    pass


async def record_subprocessor_receipt(
    session: AsyncSession,
    *,
    deletion_request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    subprocessor_name: str,
    status: SubprocessorReceiptStatus,
    request_reference: str | None,
    receipt_reference: str | None,
    received_at: datetime | None,
    evidence_note: str | None,
    operator: str,
) -> DeletionSubprocessorReceipt:
    request = await session.get(DeletionRequest, deletion_request_id)
    if request is None or request.workspace_id != workspace_id:
        raise ReceiptError("deletion_request_not_found")
    name = subprocessor_name.strip()
    if not name:
        raise ReceiptError("subprocessor_name_required")
    result = await session.execute(
        select(DeletionSubprocessorReceipt).where(
            DeletionSubprocessorReceipt.deletion_request_id == deletion_request_id,
            DeletionSubprocessorReceipt.subprocessor_name == name,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        receipt = DeletionSubprocessorReceipt(
            id=uuid.uuid4(),
            deletion_request_id=deletion_request_id,
            workspace_id=workspace_id,
            subprocessor_name=name,
            status=status.value,
            request_reference=request_reference,
            receipt_reference=receipt_reference,
            requested_at=(
                datetime.now(UTC) if status != SubprocessorReceiptStatus.PENDING else None
            ),
            received_at=received_at,
            evidence_note=evidence_note,
            recorded_by_operator=operator,
        )
        session.add(receipt)
    else:
        receipt.status = status.value
        receipt.request_reference = request_reference
        receipt.receipt_reference = receipt_reference
        receipt.received_at = received_at
        receipt.evidence_note = evidence_note
        receipt.recorded_by_operator = operator
    await session.flush()
    await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=deletion_request_id,
        event_type="subprocessor_receipt_recorded",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.OPERATOR,
        payload={"subprocessor_name": name, "status": status.value},
    )
    return receipt


__all__ = ["ReceiptError", "record_subprocessor_receipt"]
```

- [ ] **Step 5: 实现 DSR 服务**

Create `apps/api/src/data_intelligence_hub/services/dsr_service.py`:

```python
"""人工 DSR 案件流转。

不提供客户提交门户。运营通过命令行建案和推进状态，每个变更写审计链。
requester_ref 必须是工单号等不透明引用，不得写邮箱或其他联系方式。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionRequest,
    DeletionRequestStatus,
    DsrCase,
    DsrRequestType,
    DsrResponsibility,
    DsrStatus,
    PrivacyActorKind,
    PrivacyStreamType,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.services.privacy_audit import append_privacy_event

ALLOWED_DSR_TRANSITIONS: dict[str, frozenset[str]] = {
    DsrStatus.RECEIVED.value: frozenset({DsrStatus.VERIFYING.value, DsrStatus.REJECTED.value}),
    DsrStatus.VERIFYING.value: frozenset(
        {DsrStatus.IN_PROGRESS.value, DsrStatus.REJECTED.value}
    ),
    DsrStatus.IN_PROGRESS.value: frozenset(
        {DsrStatus.COMPLETED.value, DsrStatus.REJECTED.value}
    ),
    DsrStatus.COMPLETED.value: frozenset({DsrStatus.CLOSED.value}),
    DsrStatus.REJECTED.value: frozenset({DsrStatus.CLOSED.value}),
    DsrStatus.CLOSED.value: frozenset(),
}


class DsrError(Exception):
    pass


def _case_number(now: datetime) -> str:
    return f"DSR-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


async def open_dsr_case(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    request_type: str,
    requester_ref: str,
    received_at: datetime,
    due_at: datetime | None,
    operator: str,
) -> DsrCase:
    if request_type not in {item.value for item in DsrRequestType}:
        raise DsrError("dsr_request_type_invalid")
    reference = requester_ref.strip()
    if not reference:
        raise DsrError("dsr_requester_ref_required")
    if "@" in reference:
        raise DsrError("dsr_requester_ref_must_be_opaque")
    if project_id is not None:
        project = await session.get(Project, project_id)
        if project is None or project.workspace_id != workspace_id:
            raise DsrError("project_not_found")
    now = datetime.now(UTC)
    case = DsrCase(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        case_number=_case_number(now),
        request_type=request_type,
        status=DsrStatus.RECEIVED.value,
        responsibility=DsrResponsibility.UNDETERMINED.value,
        requester_ref=reference,
        received_at=received_at,
        due_at=due_at,
        created_by_operator=operator,
    )
    session.add(case)
    await session.flush()
    await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DSR_CASE,
        stream_id=case.id,
        event_type="dsr_case_opened",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.OPERATOR,
        payload={"request_type": request_type},
    )
    return case


async def transition_dsr_case(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    workspace_id: uuid.UUID,
    target_status: DsrStatus,
    operator: str,
    verification_method: str | None = None,
    responsibility: str | None = None,
    deletion_request_id: uuid.UUID | None = None,
    note: str | None = None,
) -> DsrCase:
    result = await session.execute(
        select(DsrCase)
        .where(DsrCase.id == case_id, DsrCase.workspace_id == workspace_id)
        .with_for_update()
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise DsrError("dsr_case_not_found")
    if target_status.value not in ALLOWED_DSR_TRANSITIONS.get(case.status, frozenset()):
        raise DsrError("dsr_state_conflict")
    if target_status == DsrStatus.VERIFYING:
        if not verification_method:
            raise DsrError("dsr_verification_method_required")
        case.verification_method = verification_method
        case.verified_at = datetime.now(UTC)
    if target_status == DsrStatus.IN_PROGRESS:
        if case.verified_at is None:
            raise DsrError("dsr_verification_required")
        if responsibility is None or responsibility == DsrResponsibility.UNDETERMINED.value:
            raise DsrError("dsr_responsibility_required")
        if responsibility not in {item.value for item in DsrResponsibility}:
            raise DsrError("dsr_responsibility_invalid")
        case.responsibility = responsibility
    if target_status == DsrStatus.COMPLETED and case.request_type == DsrRequestType.DELETION.value:
        if deletion_request_id is None:
            raise DsrError("dsr_deletion_request_required")
        deletion = await session.get(DeletionRequest, deletion_request_id)
        if (
            deletion is None
            or deletion.workspace_id != workspace_id
            or deletion.status != DeletionRequestStatus.COMPLETED.value
        ):
            raise DsrError("dsr_deletion_request_not_completed")
        case.deletion_request_id = deletion_request_id
    if target_status in {DsrStatus.COMPLETED, DsrStatus.REJECTED}:
        case.closed_at = datetime.now(UTC)
    case.status = target_status.value
    if note is not None:
        case.summary = note
    await session.flush()
    await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DSR_CASE,
        stream_id=case.id,
        event_type=f"dsr_case_{target_status.value}",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.OPERATOR,
        payload={"to_status": target_status.value},
    )
    return case


__all__ = [
    "ALLOWED_DSR_TRANSITIONS",
    "DsrError",
    "open_dsr_case",
    "transition_dsr_case",
]
```

- [ ] **Step 6: 运行测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_subprocessor_receipts.py tests/unit/test_dsr.py
```

Expected: `3 passed`。

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/subprocessor_receipts.py \
  apps/api/src/data_intelligence_hub/services/dsr_service.py \
  apps/api/tests/unit/test_subprocessor_receipts.py \
  apps/api/tests/unit/test_dsr.py
git commit -m "feat(privacy): 添加子处理者回执与人工 DSR"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 5: 删除执行器、墓碑、文件删除与删除证明

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/deletion_proof.py`
- Create: `apps/api/src/data_intelligence_hub/services/deletion_executor.py`
- Test: `apps/api/tests/unit/test_deletion_executor.py`

**Interfaces:**
- Consumes: 状态机、审计链、C3 `ProjectApiKey`、C4 `WorkbenchTask`、C5 `RunLedgerEntry` 与 `RunEvidenceGradeRecord`、C7 `Claim`/`ClaimEvidence`、B5 `Evidence`、C8 `DataGap`/`MarketAssessment`、C9 `ReportArtifact`、C10 `DeliveryStore`、C11 `DatasetExportJob` 与 `dataset_export_dir`。
- Produces: `FileDeletionResult`、`DeletionExecutionResult`（含 `preserved` 计数）、`issue_deletion_proof`、`execute_deletion_request`、`purge_project_target`、`purge_workspace_target`。

**删除范围与证明计数**

处理方式只有三种：`delete` 删除行，`scrub` 原地脱敏并保留最小元数据，`preserve` 原样保留。`workbench_tasks`、`market_assessments`、`runs`、`run_steps`、`task_runs`、`collection_tasks`、`sources` 与 `report_audit_events` 使用 `scrub`，不删除。`data_gaps`、`claims`、`claim_evidence`、`evidences`、`report_artifacts` 与 `dataset_export_jobs` 使用 `delete`。`run_ledger_entries` 与 `run_evidence_grades` 使用 `preserve`，执行器只读计数，不写入，并在证明中计数。`tool_calls`、`authorizations` 与 `privacy_audit_events` 原样保留，不计数。

| object_class | 来源 | 处理 | 证明计数 |
|---|---|---|---|
| `workbench_tasks` | C4 `models/workbench.py` 的 `WorkbenchTask` | `scrub`：`brand`、`category`、`competitors`、`markets`、`locale_by_market`、`decision_question`、`does_not_answer`；`status` 置 `cancelled`。保留 `id`、项目、owner、时间窗与 `task_type`。 | `row_count` |
| `data_gaps` | C8 `models/data_gap.py` 的 `DataGap` | `delete` | `row_count` |
| `market_assessments` | C8 `models/market_assessment.py` 的 `MarketAssessment` | `scrub`：`core_domain_coverage`、`sample_counts`、`thresholds`、`gap_ids`、`details_json`。保留 `market`、`market_role`、`quality_status`、`conclusion_standard`、`conclusion_quick`、`evidence_grade`、`computed_at`。 | `row_count` |
| `runs` | `models/run.py` 的 `Run` | `scrub`：`error_message`。保留状态、`market_code`、成本、证据等级与时间。 | `row_count` |
| `run_steps` | `models/run.py` 的 `RunStep` | `scrub`：`error_message`。保留状态、成本、证据等级与步骤序号。 | `row_count` |
| `task_runs` | `models/task.py` 的 `TaskRun` | `scrub`：`error_message`、`error_traceback`、`logs`。保留状态、成本与证据等级。 | `row_count` |
| `collection_tasks` | `models/task.py` 的 `CollectionTask` | `scrub`：`name`、`config`、`schedule_cron`。保留 `collector_type`、`status` 与 `source_id`。 | `row_count` |
| `sources` | `models/source.py` 的 `Source` | `scrub`：`name`、`url`、`config`、`schedule_cron`，`enabled` 置 `false`。保留 `type`。 | `row_count` |
| `run_ledger_entries` | C5 `models/run_ledger.py` 的 `RunLedgerEntry` | `preserve`。账本只有金额元数据，不删除、不改写。 | `preserved.run_ledger_entries` |
| `run_evidence_grades` | `models/run_evidence_grade.py` 的 `RunEvidenceGradeRecord` | `preserve`。证据等级最小元数据不删除、不改写。 | `preserved.run_evidence_grades` |
| `claims` | `models/claim.py` 的 `Claim` | `delete` | `row_count` |
| `claim_evidence` | `models/claim.py` 的 `ClaimEvidence` | `delete` | `row_count` |
| `evidences` | `models/intelligence.py` 的 `Evidence` | `delete` | `row_count` |
| `report_artifacts` | `models/report_artifact.py` 的 `ReportArtifact` | `delete` | `row_count` |
| `report_audit_events` | `models/report.py` 的 `ReportAuditEvent` | `scrub`：`metadata_json`、`artifact_id`；先用产物的 `report_id` 回填空 `report_id`。保留事件类型、状态流转、主体与时间。 | `row_count` |
| `delivery_bundles` | C10 `DeliveryStore.remove_bundle` | `delete` 文件 | `file_deletions.delivery_bundles` |
| `delivery_files` | C10 `DeliveryStore.bundle_dir` 文件计数 | `delete` 文件 | `file_deletions.delivery_files` |
| `dataset_export_jobs` | `models/dataset.py` 的 `DatasetExportJob` | `delete` | `row_count` |
| `dataset_export_files` | `DatasetExportJob.artifact_path` | `delete` 文件 | `file_deletions.dataset_export_files` |
| `project_api_keys` | C3 密钥撤销 | 撤销，不删除 | `revocations.project_api_keys` |
| `report_shares` | 首期延期 | 不适用 | 固定 `0` |

`runs`、`run_steps` 与 `task_runs` 不保存七槽位正文。品牌、竞品与决策问题主要落在 `task_runs.logs`、`error_message`、`error_traceback`，以及 `workbench_tasks` 与 `workflow_versions.plan_payload`。执行器必须脱敏这些内容字段，不得只解绑外键。

`privacy_audit_events` 属于工作区审计流。项目删除不删除、不改写、不计数。`authorizations` 是授权与门禁审计，原样保留，不删除、不改写。`report_audit_events` 的脱敏需要 `dih_deletion_executor` 的 UPDATE 例外。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_deletion_executor.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import Dataset, DatasetExportJob, DatasetVersion
from data_intelligence_hub.models.intelligence import Evidence
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.privacy_deletion import (
    DeletionProof,
    DeletionRequestStatus,
    DeletionTargetType,
    DeletionTombstone,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_evidence_grade import RunEvidenceGradeRecord
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_executor import execute_deletion_request
from data_intelligence_hub.services.deletion_service import (
    confirm_deletion_request,
    create_deletion_request,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed(session: AsyncSession, export_root: Path) -> dict[str, uuid.UUID]:
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    report_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    version_id = uuid.uuid4()
    export_id = uuid.uuid4()
    source_id = uuid.uuid4()
    task_id = uuid.uuid4()
    task_run_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    workbench_id = uuid.uuid4()
    gap_id = uuid.uuid4()
    assessment_id = uuid.uuid4()
    ledger_id = uuid.uuid4()
    grade_id = uuid.uuid4()
    audit_event_id = uuid.uuid4()
    now = datetime.now(UTC)
    export_file = export_root / f"{export_id}.csv"
    export_file.write_text("sku\n1\n", encoding="utf-8")
    session.add_all(
        [
            User(id=owner_id, email="del-owner@example.com", password_hash="x", name="Owner"),
            Workspace(id=workspace_id, name="Del WS", slug="del-ws", owner_id=owner_id),
            WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role="owner"),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                name="待删除项目",
                domain="ecommerce",
                status="active",
                owner_id=owner_id,
            ),
            Report(
                id=report_id,
                workspace_id=workspace_id,
                project_id=project_id,
                report_type="daily",
                title="Report",
                content="raw report",
                status="generated",
                period_start=now,
                period_end=now,
            ),
            ReportArtifact(
                id=artifact_id,
                report_id=report_id,
                workspace_id=workspace_id,
                contract_json={},
                contract_sha256="a" * 64,
                data_sha256="b" * 64,
                report_html_sha256="c" * 64,
                sop_html_sha256="d" * 64,
                combined_sha256="e" * 64,
                report_html="<html></html>",
                sop_html="<html></html>",
                status="draft",
                manifest_json={"files": [{"path": "report.zh.html"}]},
                delivery_status="delivered",
            ),
            Claim(
                id=claim_id,
                workspace_id=workspace_id,
                project_id=project_id,
                claim_type="market",
                state="hypothesis",
                text="claim",
                confidence=0.5,
            ),
            Evidence(
                id=evidence_id,
                workspace_id=workspace_id,
                project_id=project_id,
                evidence_type="signal",
                title="Evidence",
            ),
            ClaimEvidence(claim_id=claim_id, evidence_id=evidence_id, role="support"),
            Dataset(
                id=dataset_id,
                workspace_id=workspace_id,
                project_id=project_id,
                name="Dataset",
                dataset_type="records",
                status="active",
            ),
            DatasetVersion(
                id=version_id,
                workspace_id=workspace_id,
                project_id=project_id,
                dataset_id=dataset_id,
                version_number=1,
                status="ready",
                row_count=1,
                created_by_user_id=owner_id,
            ),
            DatasetExportJob(
                id=export_id,
                workspace_id=workspace_id,
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_version_id=version_id,
                created_by_user_id=owner_id,
                export_format="csv",
                status="completed",
                filename="export.csv",
                content_type="text/csv",
                artifact_path=str(export_file),
                artifact_size_bytes=8,
                row_count=1,
                checksum_sha256="c" * 64,
                audit_events=[],
                created_at=now,
            ),
            Source(
                id=source_id,
                workspace_id=workspace_id,
                project_id=project_id,
                name="品牌竞品来源",
                type="search",
                url="https://example.com/?q=momcozy",
                config={"query": "Momcozy vs Medela"},
                enabled=True,
            ),
            CollectionTask(
                id=task_id,
                workspace_id=workspace_id,
                project_id=project_id,
                source_id=source_id,
                collector_type="search",
                name="Momcozy 竞品任务",
                status="active",
                config={"query": "Momcozy vs Medela"},
            ),
            WorkbenchTask(
                id=workbench_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=owner_id,
                owner_id=owner_id,
                brand="Momcozy",
                category="baby",
                competitors=["Medela"],
                markets=["US"],
                locale_by_market={"US": "en-US"},
                window_start=now.date(),
                window_end=now.date(),
                decision_question="Fit 与支撑哪个是主要摩擦？",
                does_not_answer=[],
                status="submitted",
            ),
            Run(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=task_id,
                status="completed",
                outcome="success",
                execution_mode="live",
                trigger="manual",
                records_count=1,
                total_cost_usd=Decimal("0.100000"),
                error_message="Momcozy query failed",
                evidence_grade="L3_live_single",
                created_at=now,
            ),
            RunStep(
                id=step_id,
                run_id=run_id,
                step_index=1,
                endpoint_type="search",
                collector_type="search",
                task_run_id=task_run_id,
                status="success",
                outcome="success",
                records_count=1,
                total_cost_usd=Decimal("0.100000"),
                error_message="Momcozy query failed",
            ),
            TaskRun(
                id=task_run_id,
                task_id=task_id,
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run_id,
                step_index=1,
                status="completed",
                records_count=1,
                logs=[{"request": "Momcozy vs Medela"}],
                error_message="Momcozy query failed",
                error_traceback="Traceback: Momcozy",
                created_at=now,
            ),
            RunLedgerEntry(
                id=ledger_id,
                run_id=run_id,
                step_id=step_id,
                entry_kind="settle",
                amount_usd=Decimal("0.100000"),
                balance_after_usd=Decimal("9.900000"),
                idempotency_key="settle-run-1",
                created_at=now,
            ),
            RunEvidenceGradeRecord(
                id=grade_id,
                run_id=run_id,
                live_call=True,
                sample_n=1,
                required_n=1,
                window_days=7,
                required_window_days=7,
                source_count=1,
                required_source_count=1,
                grade="L3_live_single",
            ),
            DataGap(
                id=gap_id,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=workbench_id,
                run_id=run_id,
                step_id=step_id,
                market="US",
                data_domain="reviews",
                reason_code="low_sample",
                actual_value=None,
                threshold_value=30,
                impact="低置信",
                customer_text_zh="样本不足",
                customer_text_en="Not enough samples",
                remediation="补采",
                severity="warning",
                status="open",
                created_at=now,
            ),
            MarketAssessment(
                id=assessment_id,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=workbench_id,
                market="US",
                market_role="primary",
                quality_status="qualified_with_gap",
                conclusion_standard="pass",
                conclusion_quick="pass",
                evidence_grade="L3_live_single",
                core_domain_coverage={"reviews": 1},
                sample_counts={"reviews": 1},
                thresholds={"reviews": 30},
                gap_ids=[str(gap_id)],
                details_json={"brand": "Momcozy"},
                computed_at=now,
            ),
            ReportAuditEvent(
                id=audit_event_id,
                workspace_id=workspace_id,
                report_id=report_id,
                actor_id=owner_id,
                event_type="report_generated",
                from_status=None,
                to_status="generated",
                metadata_json='{"brand": "Momcozy"}',
                created_at=now,
            ),
            ProjectApiKey(
                project_id=project_id,
                workspace_id=workspace_id,
                label="key",
                key_prefix="dih_test",
                key_hash="b" * 64,
                created_by_user_id=owner_id,
                status="active",
                tool_allowlist=["collect"],
                daily_collect_quota=1,
            ),
        ]
    )
    await session.commit()
    return {
        "owner": owner_id,
        "workspace": workspace_id,
        "project": project_id,
        "report": report_id,
        "artifact": artifact_id,
        "claim": claim_id,
        "evidence": evidence_id,
        "dataset": dataset_id,
        "version": version_id,
        "export": export_id,
        "export_file": export_file,
        "source": source_id,
        "task": task_id,
        "task_run": task_run_id,
        "run": run_id,
        "step": step_id,
        "workbench": workbench_id,
        "gap": gap_id,
        "assessment": assessment_id,
        "ledger": ledger_id,
        "grade": grade_id,
        "audit_event": audit_event_id,
    }


@pytest.mark.asyncio
async def test_execute_handles_scope_and_writes_proof_counts(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "data_intelligence_hub.services.deletion_executor.get_settings",
        lambda: type("Settings", (), {"dataset_export_dir": str(tmp_path / "exports")})(),
    )
    export_root = tmp_path / "exports"
    export_root.mkdir()
    ids = await _seed(session, export_root)
    bundle_dir = tmp_path / "delivery" / str(ids["workspace"]) / str(ids["artifact"])
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "report.zh.html").write_text("report", encoding="utf-8")
    (bundle_dir / "manifest.json").write_text("{}", encoding="utf-8")
    created = await create_deletion_request(
        session,
        workspace_id=ids["workspace"],
        requested_by_user_id=ids["owner"],
        target_type=DeletionTargetType.PROJECT,
        project_id=ids["project"],
        reason=None,
    )
    await confirm_deletion_request(
        session,
        request_id=created.request.id,
        workspace_id=ids["workspace"],
        actor_user_id=ids["owner"],
        token=created.confirmation_token,
        confirmation_text=created.confirmation_phrase,
    )
    result = await execute_deletion_request(
        session,
        request_id=created.request.id,
        workspace_id=ids["workspace"],
        actor_user_id=ids["owner"],
        delivery_store=DeliveryStore(tmp_path / "delivery"),
    )
    assert result.request.status == DeletionRequestStatus.COMPLETED.value
    assert result.proof.proof_number.startswith("DP-")
    assert result.proof.proof_digest.startswith("sha256:")
    assert result.revocations == {"project_api_keys": 1, "report_shares": 0}
    assert result.file_deletions.dataset_export_files == 1
    assert result.file_deletions.delivery_bundles == 1
    assert result.file_deletions.delivery_files == 2
    assert result.preserved == {"run_evidence_grades": 1, "run_ledger_entries": 1}
    assert not ids["export_file"].exists()
    assert not bundle_dir.exists()
    assert await session.get(Claim, ids["claim"]) is None
    assert await session.get(Evidence, ids["evidence"]) is None
    assert await session.get(ReportArtifact, ids["artifact"]) is None
    assert await session.get(DatasetExportJob, ids["export"]) is None
    assert await session.get(DataGap, ids["gap"]) is None

    workbench = await session.get(WorkbenchTask, ids["workbench"])
    assert workbench is not None
    assert workbench.brand == "[deleted]"
    assert workbench.competitors == []
    assert workbench.decision_question == "[deleted]"
    assert workbench.status == "cancelled"

    assessment = await session.get(MarketAssessment, ids["assessment"])
    assert assessment is not None
    assert assessment.evidence_grade == "L3_live_single"
    assert assessment.details_json == {}
    assert assessment.gap_ids == []

    run = await session.get(Run, ids["run"])
    assert run is not None and run.error_message is None
    step = await session.get(RunStep, ids["step"])
    assert step is not None and step.error_message is None
    task_run = await session.get(TaskRun, ids["task_run"])
    assert task_run is not None
    assert task_run.logs == []
    assert task_run.error_message is None
    assert task_run.error_traceback is None
    task = await session.get(CollectionTask, ids["task"])
    assert task is not None and task.name == "[deleted]"
    assert task.config is None
    source = await session.get(Source, ids["source"])
    assert source is not None and source.url is None and source.config == {}

    assert await session.get(RunLedgerEntry, ids["ledger"]) is not None
    assert await session.get(RunEvidenceGradeRecord, ids["grade"]) is not None
    audit_event = await session.get(ReportAuditEvent, ids["audit_event"])
    assert audit_event is not None
    assert audit_event.metadata_json is None
    assert audit_event.event_type == "report_generated"

    proof = (
        await session.execute(
            select(DeletionProof).where(
                DeletionProof.deletion_request_id == created.request.id
            )
        )
    ).scalar_one()
    classes = {item["object_class"] for item in proof.payload["tombstones"]}
    assert {
        "workbench_tasks",
        "data_gaps",
        "market_assessments",
        "runs",
        "run_steps",
        "task_runs",
        "collection_tasks",
        "sources",
        "claims",
        "claim_evidence",
        "evidences",
        "report_artifacts",
        "report_audit_events",
    } <= classes
    assert proof.payload["revocations"]["report_shares"] == 0
    assert proof.payload["file_deletions"]["dataset_export_files"] == 1
    assert proof.payload["file_deletions"]["delivery_bundles"] == 1
    assert proof.payload["file_deletions"]["delivery_files"] == 2
    assert proof.payload["preserved"] == {
        "run_evidence_grades": 1,
        "run_ledger_entries": 1,
    }
    counts = {item["object_class"]: item["row_count"] for item in proof.payload["tombstones"]}
    for object_class in (
        "workbench_tasks",
        "data_gaps",
        "market_assessments",
        "runs",
        "run_steps",
        "task_runs",
        "collection_tasks",
        "sources",
        "claims",
        "claim_evidence",
        "evidences",
        "report_artifacts",
        "report_audit_events",
        "dataset_export_files",
        "project",
    ):
        assert counts.get(object_class, 0) >= 1, object_class
    tombstones = list(
        (
            await session.execute(
                select(DeletionTombstone).where(
                    DeletionTombstone.deletion_request_id == created.request.id
                )
            )
        ).scalars()
    )
    assert {item.object_class for item in tombstones} >= {
        "workbench_tasks",
        "data_gaps",
        "market_assessments",
        "runs",
        "run_steps",
        "task_runs",
        "collection_tasks",
        "sources",
        "claims",
        "claim_evidence",
        "evidences",
        "report_artifacts",
        "report_audit_events",
        "dataset_export_files",
        "project",
    }
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_executor.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.deletion_executor`。

- [ ] **Step 3: 实现删除证明**

Create `apps/api/src/data_intelligence_hub/services/deletion_proof.py`:

```python
"""删除证明。

证明只包含对象类、行数、摘要、撤销计数、文件删除计数、保留元数据计数、回执摘要和审计头。
不包含目标名称、正文、联系方式、密钥、Cookie 或盐。
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionProof,
    DeletionRequest,
    DeletionSubprocessorReceipt,
    DeletionTombstone,
)
from data_intelligence_hub.services.privacy_audit import sha256_digest


@dataclasses.dataclass(frozen=True, slots=True)
class FileDeletionResult:
    delivery_bundles: int = 0
    delivery_files: int = 0
    dataset_export_files: int = 0


def build_proof_payload(
    *,
    request: DeletionRequest,
    tombstones: list[DeletionTombstone],
    revocations: dict[str, int],
    file_deletions: FileDeletionResult,
    receipts: list[DeletionSubprocessorReceipt],
    preserved: dict[str, int],
    audit_head_digest: str,
    schema_revision: str,
    completed_at: datetime,
) -> dict[str, Any]:
    return {
        "proof_version": "deletion_proof.v1",
        "deletion_request_id": str(request.id),
        "workspace_id": str(request.workspace_id),
        "target": {"type": request.target_type, "id": str(request.target_id)},
        "completed_at": completed_at.astimezone(UTC).isoformat(),
        "tombstones": [
            {
                "object_class": item.object_class,
                "row_count": item.row_count,
                "content_digest": item.content_digest,
            }
            for item in sorted(tombstones, key=lambda row: (row.object_class, str(row.target_id)))
        ],
        "revocations": dict(sorted(revocations.items())),
        "file_deletions": dataclasses.asdict(file_deletions),
        "preserved": dict(sorted(preserved.items())),
        "subprocessor_receipts": [
            {
                "subprocessor_name": item.subprocessor_name,
                "status": item.status,
                "received_at": (
                    None
                    if item.received_at is None
                    else item.received_at.astimezone(UTC).isoformat()
                ),
            }
            for item in sorted(receipts, key=lambda row: row.subprocessor_name)
        ],
        "audit_head_digest": audit_head_digest,
        "schema_revision": schema_revision,
    }


async def issue_deletion_proof(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    tombstones: list[DeletionTombstone],
    revocations: dict[str, int],
    file_deletions: FileDeletionResult,
    receipts: list[DeletionSubprocessorReceipt],
    preserved: dict[str, int],
    audit_head_digest: str,
    schema_revision: str,
    completed_at: datetime,
) -> DeletionProof:
    payload = build_proof_payload(
        request=request,
        tombstones=tombstones,
        revocations=revocations,
        file_deletions=file_deletions,
        receipts=receipts,
        preserved=preserved,
        audit_head_digest=audit_head_digest,
        schema_revision=schema_revision,
        completed_at=completed_at,
    )
    digest = sha256_digest(payload)
    proof = DeletionProof(
        id=uuid.uuid4(),
        deletion_request_id=request.id,
        workspace_id=request.workspace_id,
        proof_number=f"DP-{completed_at.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        payload=payload,
        proof_digest=digest,
        audit_head_digest=audit_head_digest,
        issued_at=completed_at,
    )
    session.add(proof)
    await session.flush()
    return proof


def verify_proof_digest(proof: DeletionProof) -> bool:
    return sha256_digest(proof.payload) == proof.proof_digest


__all__ = [
    "FileDeletionResult",
    "build_proof_payload",
    "issue_deletion_proof",
    "verify_proof_digest",
]
```

- [ ] **Step 4: 实现删除执行器**

Create `apps/api/src/data_intelligence_hub/services/deletion_executor.py`。文件包含以下函数。对象类名必须与证明计数表一致。

```python
"""删除执行器。

一个请求的全部删除、撤销、墓碑和证明在一个事务内完成。
任何步骤失败时由调用方回滚，再把请求标成 failed。
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.automation_plan import ExtractionPlan, SiteAnalysis
from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import (
    CleaningPlan,
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
)
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.enrichment import EnrichmentJob, EnrichmentRow
from data_intelligence_hub.models.intelligence import (
    Evidence,
    IntelligenceFeedback,
    IntelligenceItem,
)
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.monitor import Monitor
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.privacy_deletion import (
    DeletionProof,
    DeletionRequest,
    DeletionRequestStatus,
    DeletionSubprocessorReceipt,
    DeletionTargetType,
    DeletionTombstone,
    PrivacyActorKind,
    PrivacyStreamType,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report import (
    Report,
    ReportAuditEvent,
    ReportSubscription,
    ReportSubscriptionRun,
)
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_evidence_grade import RunEvidenceGradeRecord
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.webhook import WebhookDelivery, WebhookEndpoint
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest,
)
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    QueryTerm,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
)
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_proof import (
    FileDeletionResult,
    issue_deletion_proof,
)
from data_intelligence_hub.services.deletion_service import active_hold_count
from data_intelligence_hub.services.privacy_audit import (
    append_privacy_event,
    sha256_digest,
    verify_privacy_chain,
)


class DeletionExecutionError(Exception):
    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclasses.dataclass(frozen=True, slots=True)
class ObjectClassResult:
    object_class: str
    row_count: int
    content_digest: str


@dataclasses.dataclass(frozen=True, slots=True)
class DeletionExecutionResult:
    request: DeletionRequest
    proof: DeletionProof
    tombstones: list[DeletionTombstone]
    revocations: dict[str, int]
    file_deletions: FileDeletionResult
    preserved: dict[str, int]


def _now() -> datetime:
    return datetime.now(UTC)


def _digest_ids(object_class: str, ids: list[uuid.UUID]) -> str:
    return sha256_digest(
        {"object_class": object_class, "ids": [str(item) for item in sorted(ids, key=str)]}
    )


async def _collect(
    session: AsyncSession, model: type[Any], *conditions: Any
) -> list[uuid.UUID]:
    result = await session.execute(select(model.id).where(*conditions).order_by(model.id))
    return list(result.scalars().all())


async def _count(session: AsyncSession, model: type[Any], *conditions: Any) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(*conditions)
    )
    return int(result.scalar_one())


async def _preserved_counts(
    session: AsyncSession, *, workspace_id: uuid.UUID, project_id: uuid.UUID | None
) -> dict[str, int]:
    """统计账本与证据等级保留的最小元数据行数。"""

    conditions = [Run.workspace_id == workspace_id]
    if project_id is not None:
        conditions.append(Run.project_id == project_id)
    run_ids = select(Run.id).where(*conditions)
    return {
        "run_ledger_entries": await _count(
            session, RunLedgerEntry, RunLedgerEntry.run_id.in_(run_ids)
        ),
        "run_evidence_grades": await _count(
            session, RunEvidenceGradeRecord, RunEvidenceGradeRecord.run_id.in_(run_ids)
        ),
    }


async def _set_deletion_role(session: AsyncSession) -> None:
    """C9 的不可变触发器只允许专用角色删除报告产物与脱敏报告审计事件。

    SQLite 单元测试没有角色，跳过。PostgreSQL 上进入本地角色。
    应用角色只是该 NOLOGIN 角色的成员，成员关系只用于受控事务内的 SET LOCAL ROLE。
    应用角色在常态角色下没有这两张表的直接 UPDATE 或 DELETE 授权。
    """

    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await session.execute(text('SET LOCAL ROLE "dih_deletion_executor"'))


async def _reset_deletion_role(session: AsyncSession) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await session.execute(text("RESET ROLE"))


async def _delete_ids(session: AsyncSession, model: type[Any], ids: list[uuid.UUID]) -> None:
    if ids:
        await session.execute(delete(model).where(model.id.in_(ids)))


class _Recorder:
    def __init__(self) -> None:
        self.results: list[ObjectClassResult] = []
        self.files = FileDeletionResult()

    def record(self, object_class: str, ids: list[uuid.UUID]) -> None:
        if not ids:
            return
        self.results.append(
            ObjectClassResult(object_class, len(ids), _digest_ids(object_class, ids))
        )

    def add_files(self, **increments: int) -> None:
        self.files = dataclasses.replace(
            self.files,
            delivery_bundles=self.files.delivery_bundles
            + increments.get("delivery_bundles", 0),
            delivery_files=self.files.delivery_files + increments.get("delivery_files", 0),
            dataset_export_files=self.files.dataset_export_files
            + increments.get("dataset_export_files", 0),
        )

    async def delete(
        self, session: AsyncSession, model: type[Any], object_class: str, ids: list[uuid.UUID]
    ) -> None:
        if not ids:
            return
        self.record(object_class, ids)
        await _delete_ids(session, model, ids)

    async def scrub(
        self,
        session: AsyncSession,
        model: type[Any],
        object_class: str,
        ids: list[uuid.UUID],
        values: dict[str, Any],
    ) -> None:
        if not ids:
            return
        self.record(object_class, ids)
        await session.execute(update(model).where(model.id.in_(ids)).values(**values))


async def _audit_share_deferred(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    scope_type: str,
    scope_id: uuid.UUID,
) -> None:
    await append_privacy_event(
        session,
        workspace_id=request.workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=request.id,
        event_type="deletion_share_revocation_deferred",
        actor_user_id=None,
        actor_kind=PrivacyActorKind.SYSTEM,
        payload={"report_shares": 0, "scope_type": scope_type, "scope_id": str(scope_id)},
    )


async def _revoke_keys(
    session: AsyncSession, *, workspace_id: uuid.UUID, project_id: uuid.UUID | None
) -> int:
    conditions = [
        ProjectApiKey.workspace_id == workspace_id,
        ProjectApiKey.revoked_at.is_(None),
    ]
    if project_id is not None:
        conditions.append(ProjectApiKey.project_id == project_id)
    ids = await _collect(session, ProjectApiKey, *conditions)
    if ids:
        await session.execute(
            update(ProjectApiKey)
            .where(ProjectApiKey.id.in_(ids))
            .values(revoked_at=_now(), status="revoked")
        )
    return len(ids)


def _tombstones_from_recorder(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    recorder: _Recorder,
    target_id: uuid.UUID,
    project_id: uuid.UUID | None,
    record_tombstones: bool,
) -> list[DeletionTombstone]:
    if not record_tombstones:
        return []
    rows: list[DeletionTombstone] = []
    for item in recorder.results:
        row = DeletionTombstone(
            id=uuid.uuid4(),
            deletion_request_id=request.id,
            workspace_id=request.workspace_id,
            project_id=project_id,
            target_type=request.target_type,
            target_id=target_id,
            object_class=item.object_class,
            row_count=item.row_count,
            content_digest=item.content_digest,
            deleted_at=_now(),
        )
        session.add(row)
        rows.append(row)
    return rows


async def _delete_delivery_bundles(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_ids: list[uuid.UUID],
    delivery_store: DeliveryStore,
    recorder: _Recorder,
) -> None:
    if not artifact_ids:
        return
    result = await session.execute(
        select(ReportArtifact).where(ReportArtifact.id.in_(artifact_ids))
    )
    bundles = 0
    files = 0
    for artifact in result.scalars().all():
        bundle = delivery_store.bundle_dir(workspace_id, artifact.id)
        file_count = sum(1 for path in bundle.rglob("*") if path.is_file()) if bundle.exists() else 0
        delivery_store.remove_bundle(workspace_id=workspace_id, artifact_id=artifact.id)
        bundles += 1
        files += file_count
    recorder.record("delivery_bundles", artifact_ids)
    recorder.add_files(delivery_bundles=bundles, delivery_files=files)


async def _delete_dataset_export_files(
    session: AsyncSession,
    *,
    export_ids: list[uuid.UUID],
    recorder: _Recorder,
) -> None:
    if not export_ids:
        return
    root = Path(get_settings().dataset_export_dir).expanduser().resolve()
    result = await session.execute(
        select(DatasetExportJob).where(DatasetExportJob.id.in_(export_ids))
    )
    deleted: list[uuid.UUID] = []
    for job in result.scalars().all():
        try:
            resolved = Path(job.artifact_path).expanduser().resolve(strict=False)
            resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise DeletionExecutionError("deletion_export_path_invalid", 500) from exc
        if resolved.is_file():
            resolved.unlink()
            deleted.append(job.id)
    if deleted:
        recorder.record("dataset_export_files", deleted)
        recorder.add_files(dataset_export_files=len(deleted))


async def _purge_report_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_ids: list[uuid.UUID],
    delivery_store: DeliveryStore,
    recorder: _Recorder,
) -> None:
    if not report_ids:
        return
    await _set_deletion_role(session)
    artifact_rows = list(
        (
            await session.execute(
                select(ReportArtifact).where(ReportArtifact.report_id.in_(report_ids))
            )
        ).scalars()
    )
    artifact_ids = [row.id for row in artifact_rows]
    artifact_report = {row.id: row.report_id for row in artifact_rows}
    audit_rows = list(
        (
            await session.execute(
                select(ReportAuditEvent).where(
                    or_(
                        ReportAuditEvent.report_id.in_(report_ids),
                        ReportAuditEvent.artifact_id.in_(artifact_ids or [uuid.uuid4()]),
                    )
                )
            )
        ).scalars()
    )
    # C9 的检查约束要求 report_id 与 artifact_id 至少一个非空。
    # 删除产物前，用产物的 report_id 回填空 report_id。
    for event in audit_rows:
        if event.report_id is None and event.artifact_id in artifact_report:
            event.report_id = artifact_report[event.artifact_id]
    audit_ids = [row.id for row in audit_rows]
    await session.flush()
    await _delete_delivery_bundles(
        session,
        workspace_id=workspace_id,
        artifact_ids=artifact_ids,
        delivery_store=delivery_store,
        recorder=recorder,
    )
    await recorder.scrub(
        session,
        ReportAuditEvent,
        "report_audit_events",
        audit_ids,
        {"metadata_json": None, "artifact_id": None},
    )
    await recorder.delete(session, ReportArtifact, "report_artifacts", artifact_ids)
    await _reset_deletion_role(session)


async def _purge_project_content(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    project_id: uuid.UUID,
    delivery_store: DeliveryStore,
    recorder: _Recorder,
    record_tombstones: bool,
) -> list[DeletionTombstone]:
    workspace_id = request.workspace_id

    report_ids = await _collect(
        session, Report, Report.workspace_id == workspace_id, Report.project_id == project_id
    )
    await _purge_report_scope(
        session,
        workspace_id=workspace_id,
        report_ids=report_ids,
        delivery_store=delivery_store,
        recorder=recorder,
    )

    subscription_ids = await _collect(
        session,
        ReportSubscription,
        ReportSubscription.workspace_id == workspace_id,
        ReportSubscription.project_id == project_id,
    )
    subscription_run_ids = await _collect(
        session,
        ReportSubscriptionRun,
        ReportSubscriptionRun.subscription_id.in_(subscription_ids or [uuid.uuid4()]),
    )
    await recorder.delete(
        session, ReportSubscriptionRun, "report_subscription_runs", subscription_run_ids
    )
    await recorder.delete(
        session, ReportSubscription, "report_subscriptions", subscription_ids
    )
    await recorder.scrub(
        session,
        Report,
        "reports",
        report_ids,
        {"title": "[deleted]", "content": "", "status": "deleted"},
    )

    rule_ids = await _collect(
        session, AlertRule, AlertRule.workspace_id == workspace_id, AlertRule.project_id == project_id
    )
    alert_ids = await _collect(
        session, AlertEvent, AlertEvent.rule_id.in_(rule_ids or [uuid.uuid4()])
    )
    await recorder.delete(session, AlertEvent, "alert_events", alert_ids)
    await recorder.delete(session, AlertRule, "alert_rules", rule_ids)

    claim_ids = await _collect(
        session, Claim, Claim.workspace_id == workspace_id, Claim.project_id == project_id
    )
    claim_evidence_count = await _count(
        session, ClaimEvidence, ClaimEvidence.claim_id.in_(claim_ids or [uuid.uuid4()])
    )
    if claim_evidence_count:
        recorder.results.append(
            ObjectClassResult(
                "claim_evidence",
                claim_evidence_count,
                _digest_ids("claim_evidence", claim_ids),
            )
        )
        await session.execute(
            delete(ClaimEvidence).where(ClaimEvidence.claim_id.in_(claim_ids))
        )
    await recorder.delete(session, Claim, "claims", claim_ids)

    gap_ids = await _collect(
        session, DataGap, DataGap.workspace_id == workspace_id, DataGap.project_id == project_id
    )
    await recorder.delete(session, DataGap, "data_gaps", gap_ids)
    assessment_ids = await _collect(
        session,
        MarketAssessment,
        MarketAssessment.workspace_id == workspace_id,
        MarketAssessment.project_id == project_id,
    )
    await recorder.scrub(
        session,
        MarketAssessment,
        "market_assessments",
        assessment_ids,
        {
            "core_domain_coverage": {},
            "sample_counts": {},
            "thresholds": {},
            "gap_ids": [],
            "details_json": {},
        },
    )
    workbench_ids = await _collect(
        session,
        WorkbenchTask,
        WorkbenchTask.workspace_id == workspace_id,
        WorkbenchTask.project_id == project_id,
    )
    await recorder.scrub(
        session,
        WorkbenchTask,
        "workbench_tasks",
        workbench_ids,
        {
            "brand": "[deleted]",
            "category": "[deleted]",
            "competitors": [],
            "markets": [],
            "locale_by_market": {},
            "decision_question": "[deleted]",
            "does_not_answer": [],
            "status": "cancelled",
        },
    )

    intelligence_ids = await _collect(
        session,
        IntelligenceItem,
        IntelligenceItem.workspace_id == workspace_id,
        IntelligenceItem.project_id == project_id,
    )
    feedback_ids = await _collect(
        session,
        IntelligenceFeedback,
        IntelligenceFeedback.intelligence_id.in_(intelligence_ids or [uuid.uuid4()]),
    )
    evidence_ids = await _collect(
        session,
        Evidence,
        Evidence.workspace_id == workspace_id,
        Evidence.project_id == project_id,
    )
    await recorder.delete(session, IntelligenceFeedback, "intelligence_feedback", feedback_ids)
    await recorder.delete(session, Evidence, "evidences", evidence_ids)
    await recorder.delete(session, IntelligenceItem, "intelligence_items", intelligence_ids)

    signal_ids = await _collect(
        session, Signal, Signal.workspace_id == workspace_id, Signal.project_id == project_id
    )
    await recorder.delete(session, Signal, "signals", signal_ids)

    entity_ids = await _collect(
        session, Entity, Entity.workspace_id == workspace_id, Entity.project_id == project_id
    )
    snapshot_ids = await _collect(
        session, EntitySnapshot, EntitySnapshot.entity_id.in_(entity_ids or [uuid.uuid4()])
    )
    if snapshot_ids:
        await session.execute(
            update(Entity)
            .where(Entity.latest_snapshot_id.in_(snapshot_ids))
            .values(latest_snapshot_id=None)
        )
    await recorder.delete(session, EntitySnapshot, "entity_snapshots", snapshot_ids)
    await recorder.delete(session, Entity, "entities", entity_ids)

    raw_ids = await _collect(
        session, RawRecord, RawRecord.workspace_id == workspace_id, RawRecord.project_id == project_id
    )
    await recorder.delete(session, RawRecord, "raw_records", raw_ids)

    lineage_ids = await _collect(
        session,
        WorkflowLineageMaterializationRequest,
        WorkflowLineageMaterializationRequest.workspace_id == workspace_id,
        WorkflowLineageMaterializationRequest.project_id == project_id,
    )
    await recorder.delete(
        session, WorkflowLineageMaterializationRequest, "workflow_lineage_requests", lineage_ids
    )

    dataset_ids = await _collect(
        session, Dataset, Dataset.workspace_id == workspace_id, Dataset.project_id == project_id
    )
    version_ids = await _collect(
        session, DatasetVersion, DatasetVersion.dataset_id.in_(dataset_ids or [uuid.uuid4()])
    )
    drift_ids = await _collect(
        session, DatasetDriftEvent, DatasetDriftEvent.dataset_id.in_(dataset_ids or [uuid.uuid4()])
    )
    export_ids = await _collect(
        session, DatasetExportJob, DatasetExportJob.dataset_id.in_(dataset_ids or [uuid.uuid4()])
    )
    cleaning_ids = await _collect(
        session,
        CleaningPlan,
        CleaningPlan.workspace_id == workspace_id,
        CleaningPlan.project_id == project_id,
    )
    await _delete_dataset_export_files(
        session, export_ids=export_ids, recorder=recorder
    )
    await recorder.delete(session, DatasetDriftEvent, "dataset_drift_events", drift_ids)
    await recorder.delete(session, DatasetExportJob, "dataset_export_jobs", export_ids)
    await recorder.delete(session, DatasetVersion, "dataset_versions", version_ids)
    await recorder.delete(session, CleaningPlan, "cleaning_plans", cleaning_ids)
    await recorder.delete(session, Dataset, "datasets", dataset_ids)

    site_ids = await _collect(
        session, SiteAnalysis, SiteAnalysis.workspace_id == workspace_id, SiteAnalysis.project_id == project_id
    )
    extraction_ids = await _collect(
        session,
        ExtractionPlan,
        ExtractionPlan.workspace_id == workspace_id,
        ExtractionPlan.project_id == project_id,
    )
    await recorder.delete(session, ExtractionPlan, "extraction_plans", extraction_ids)
    await recorder.delete(session, SiteAnalysis, "site_analyses", site_ids)

    job_ids = await _collect(
        session, EnrichmentJob, EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.project_id == project_id
    )
    row_ids = await _collect(
        session, EnrichmentRow, EnrichmentRow.job_id.in_(job_ids or [uuid.uuid4()])
    )
    await recorder.delete(session, EnrichmentRow, "enrichment_rows", row_ids)
    await recorder.delete(session, EnrichmentJob, "enrichment_jobs", job_ids)

    monitor_ids = await _collect(
        session, Monitor, Monitor.workspace_id == workspace_id, Monitor.project_id == project_id
    )
    if monitor_ids:
        await session.execute(update(Monitor).where(Monitor.id.in_(monitor_ids)).values(task_id=None))
    await recorder.delete(session, Monitor, "monitors", monitor_ids)

    task_ids = await _collect(
        session,
        CollectionTask,
        CollectionTask.workspace_id == workspace_id,
        CollectionTask.project_id == project_id,
    )
    task_run_ids = await _collect(
        session, TaskRun, TaskRun.task_id.in_(task_ids or [uuid.uuid4()])
    )
    run_ids = await _collect(
        session, Run, Run.workspace_id == workspace_id, Run.project_id == project_id
    )
    run_step_ids = await _collect(
        session, RunStep, RunStep.run_id.in_(run_ids or [uuid.uuid4()])
    )
    await recorder.scrub(
        session,
        TaskRun,
        "task_runs",
        task_run_ids,
        {"error_message": None, "error_traceback": None, "logs": []},
    )
    await recorder.scrub(session, Run, "runs", run_ids, {"error_message": None})
    await recorder.scrub(
        session, RunStep, "run_steps", run_step_ids, {"error_message": None}
    )
    await recorder.scrub(
        session,
        CollectionTask,
        "collection_tasks",
        task_ids,
        {"name": "[deleted]", "config": None, "schedule_cron": None},
    )
    source_ids = await _collect(
        session, Source, Source.workspace_id == workspace_id, Source.project_id == project_id
    )
    await recorder.scrub(
        session,
        Source,
        "sources",
        source_ids,
        {
            "name": "[deleted]",
            "url": None,
            "config": {},
            "schedule_cron": None,
            "enabled": False,
        },
    )

    plan_ids = await _collect(
        session, WorkflowPlan, WorkflowPlan.workspace_id == workspace_id, WorkflowPlan.project_id == project_id
    )
    version_ids = await _collect(
        session, WorkflowVersion, WorkflowVersion.workspace_id == workspace_id, WorkflowVersion.project_id == project_id
    )
    if plan_ids:
        await session.execute(
            update(WorkflowPlan)
            .where(WorkflowPlan.id.in_(plan_ids))
            .values(name="[deleted]", status="archived")
        )
    if version_ids:
        await session.execute(
            update(WorkflowVersion)
            .where(WorkflowVersion.id.in_(version_ids))
            .values(plan_payload={}, normalized_input={}, fingerprint_payload={}, query_versions={})
        )
    scope_ids = await _collect(
        session, MonitoringScope, MonitoringScope.workspace_id == workspace_id, MonitoringScope.project_id == project_id
    )
    if scope_ids:
        await session.execute(
            update(MonitoringScope)
            .where(MonitoringScope.id.in_(scope_ids))
            .values(
                canonical_term=None,
                aliases=[],
                include_terms=[],
                exclude_terms=[],
                official_accounts=[],
                seed_urls=[],
            )
        )
    term_ids = await _collect(
        session, QueryTerm, QueryTerm.workspace_id == workspace_id, QueryTerm.project_id == project_id
    )
    if term_ids:
        await session.execute(
            update(QueryTerm)
            .where(QueryTerm.id.in_(term_ids))
            .values(term="[deleted]", normalized_term="[deleted]", reason=None)
        )
    save_ids = await _collect(
        session,
        WorkflowPlanSaveRequest,
        WorkflowPlanSaveRequest.workspace_id == workspace_id,
        WorkflowPlanSaveRequest.project_id == project_id,
    )
    if save_ids:
        await session.execute(
            update(WorkflowPlanSaveRequest)
            .where(WorkflowPlanSaveRequest.id.in_(save_ids))
            .values(response_payload={})
        )

    return _tombstones_from_recorder(
        session,
        request=request,
        recorder=recorder,
        target_id=project_id,
        project_id=project_id,
        record_tombstones=record_tombstones,
    )
```

`purge_project_target`：

```python
async def purge_project_target(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    project_id: uuid.UUID,
    delivery_store: DeliveryStore,
    record_tombstones: bool = True,
    audit_share_noop: bool = True,
) -> tuple[list[DeletionTombstone], dict[str, int], FileDeletionResult, dict[str, int]]:
    recorder = _Recorder()
    tombstones = await _purge_project_content(
        session,
        request=request,
        project_id=project_id,
        delivery_store=delivery_store,
        recorder=recorder,
        record_tombstones=record_tombstones,
    )
    key_count = await _revoke_keys(
        session, workspace_id=request.workspace_id, project_id=project_id
    )
    if audit_share_noop:
        await _audit_share_deferred(
            session, request=request, scope_type="project", scope_id=project_id
        )
    if record_tombstones:
        row = DeletionTombstone(
            id=uuid.uuid4(),
            deletion_request_id=request.id,
            workspace_id=request.workspace_id,
            project_id=project_id,
            target_type=request.target_type,
            target_id=project_id,
            object_class="project",
            row_count=1,
            content_digest=_digest_ids("project", [project_id]),
            deleted_at=_now(),
        )
        session.add(row)
        tombstones.append(row)
    project = await session.get(Project, project_id)
    if project is not None:
        project.status = "deleted"
        project.name = "[deleted project]"
        project.description = None
    return tombstones, {
        "project_api_keys": key_count,
        "report_shares": 0,
    }, recorder.files, await _preserved_counts(
        session, workspace_id=request.workspace_id, project_id=project_id
    )
```

`purge_workspace_target`：

```python
async def _purge_workspace_residual(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    delivery_store: DeliveryStore,
    recorder: _Recorder,
    record_tombstones: bool,
) -> list[DeletionTombstone]:
    workspace_id = request.workspace_id
    report_ids = await _collect(
        session, Report, Report.workspace_id == workspace_id, Report.project_id.is_(None)
    )
    await _purge_report_scope(
        session,
        workspace_id=workspace_id,
        report_ids=report_ids,
        delivery_store=delivery_store,
        recorder=recorder,
    )
    await recorder.scrub(
        session,
        Report,
        "reports_unscoped",
        report_ids,
        {"title": "[deleted]", "content": "", "status": "deleted"},
    )
    evidence_ids = await _collect(
        session,
        Evidence,
        Evidence.workspace_id == workspace_id,
        Evidence.project_id.is_(None),
    )
    await recorder.delete(session, Evidence, "evidences_unscoped", evidence_ids)
    return _tombstones_from_recorder(
        session,
        request=request,
        recorder=recorder,
        target_id=workspace_id,
        project_id=None,
        record_tombstones=record_tombstones,
    )


async def purge_workspace_target(
    session: AsyncSession,
    *,
    request: DeletionRequest,
    delivery_store: DeliveryStore,
    record_tombstones: bool = True,
) -> tuple[list[DeletionTombstone], dict[str, int], FileDeletionResult, dict[str, int]]:
    workspace_id = request.workspace_id
    project_ids = await _collect(session, Project, Project.workspace_id == workspace_id)
    all_tombstones: list[DeletionTombstone] = []
    key_count = 0
    files = FileDeletionResult()
    preserved: dict[str, int] = {"run_ledger_entries": 0, "run_evidence_grades": 0}
    for project_id in project_ids:
        tombstones, revocations, project_files, project_preserved = await purge_project_target(
            session,
            request=request,
            project_id=project_id,
            delivery_store=delivery_store,
            record_tombstones=record_tombstones,
            audit_share_noop=False,
        )
        all_tombstones.extend(tombstones)
        key_count += revocations["project_api_keys"]
        for key, value in project_preserved.items():
            preserved[key] = preserved.get(key, 0) + value
        files = dataclasses.replace(
            files,
            delivery_bundles=files.delivery_bundles + project_files.delivery_bundles,
            delivery_files=files.delivery_files + project_files.delivery_files,
            dataset_export_files=files.dataset_export_files + project_files.dataset_export_files,
        )
    recorder = _Recorder()
    all_tombstones.extend(
        await _purge_workspace_residual(
            session,
            request=request,
            delivery_store=delivery_store,
            recorder=recorder,
            record_tombstones=record_tombstones,
        )
    )
    files = dataclasses.replace(
        files,
        delivery_bundles=files.delivery_bundles + recorder.files.delivery_bundles,
        delivery_files=files.delivery_files + recorder.files.delivery_files,
        dataset_export_files=files.dataset_export_files + recorder.files.dataset_export_files,
    )
    key_count += await _revoke_keys(
        session, workspace_id=workspace_id, project_id=None
    )
    await _audit_share_deferred(
        session, request=request, scope_type="workspace", scope_id=workspace_id
    )
    endpoint_ids = await _collect(
        session, WebhookEndpoint, WebhookEndpoint.workspace_id == workspace_id
    )
    delivery_ids = await _collect(
        session, WebhookDelivery, WebhookDelivery.workspace_id == workspace_id
    )
    notification_ids = await _collect(
        session, Notification, Notification.workspace_id == workspace_id
    )
    credential_ids = await _collect(
        session, PlatformCredentialBundle, PlatformCredentialBundle.workspace_id == workspace_id
    )
    workspace_recorder = _Recorder()
    await workspace_recorder.delete(
        session, WebhookDelivery, "webhook_deliveries", delivery_ids
    )
    await workspace_recorder.delete(
        session, WebhookEndpoint, "webhook_endpoints", endpoint_ids
    )
    await workspace_recorder.delete(
        session, Notification, "notifications", notification_ids
    )
    await workspace_recorder.delete(
        session, PlatformCredentialBundle, "platform_credentials", credential_ids
    )
    all_tombstones.extend(
        _tombstones_from_recorder(
            session,
            request=request,
            recorder=workspace_recorder,
            target_id=workspace_id,
            project_id=None,
            record_tombstones=record_tombstones,
        )
    )
    workspace_record = await session.get(Workspace, workspace_id)
    if workspace_record is not None:
        workspace_record.name = "[deleted workspace]"
    if record_tombstones:
        row = DeletionTombstone(
            id=uuid.uuid4(),
            deletion_request_id=request.id,
            workspace_id=workspace_id,
            project_id=None,
            target_type=request.target_type,
            target_id=workspace_id,
            object_class="workspace",
            row_count=1,
            content_digest=_digest_ids("workspace", [workspace_id]),
            deleted_at=_now(),
        )
        session.add(row)
        all_tombstones.append(row)
    return all_tombstones, {
        "project_api_keys": key_count,
        "report_shares": 0,
    }, files, preserved
```

执行入口：

```python
async def execute_deletion_request(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    delivery_store: DeliveryStore,
) -> DeletionExecutionResult:
    result = await session.execute(
        select(DeletionRequest)
        .where(DeletionRequest.id == request_id, DeletionRequest.workspace_id == workspace_id)
        .with_for_update()
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise DeletionExecutionError("deletion_request_not_found", 404)
    role = await get_workspace_role(session, workspace_id, actor_user_id)
    if role != "owner":
        raise DeletionExecutionError("workspace_owner_required", 403)
    if request.status == DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value:
        raise DeletionExecutionError("legal_hold_active", 409)
    if request.status != DeletionRequestStatus.READY.value:
        raise DeletionExecutionError("deletion_state_conflict", 409)
    hold_count = await active_hold_count(
        session, workspace_id=workspace_id, project_id=request.project_id
    )
    if hold_count:
        request.status = DeletionRequestStatus.BLOCKED_LEGAL_HOLD.value
        await append_privacy_event(
            session,
            workspace_id=workspace_id,
            stream_type=PrivacyStreamType.DELETION_REQUEST,
            stream_id=request.id,
            event_type="deletion_request_blocked",
            actor_user_id=actor_user_id,
            actor_kind=PrivacyActorKind.USER,
            payload={"legal_hold_count": hold_count},
        )
        raise DeletionExecutionError("legal_hold_active", 409)
    request.status = DeletionRequestStatus.EXECUTING.value
    request.execution_started_at = _now()
    await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=request.id,
        event_type="deletion_execution_started",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={"target_type": request.target_type, "target_id": str(request.target_id)},
    )
    if request.target_type == DeletionTargetType.PROJECT.value:
        if request.project_id is None:
            raise DeletionExecutionError("deletion_project_id_missing", 500)
        tombstones, revocations, file_deletions, preserved = await purge_project_target(
            session,
            request=request,
            project_id=request.project_id,
            delivery_store=delivery_store,
        )
    else:
        tombstones, revocations, file_deletions, preserved = await purge_workspace_target(
            session, request=request, delivery_store=delivery_store
        )
    receipts_result = await session.execute(
        select(DeletionSubprocessorReceipt).where(
            DeletionSubprocessorReceipt.deletion_request_id == request.id
        )
    )
    receipts = list(receipts_result.scalars().all())
    completed_at = _now()
    request.tombstone_digest = sha256_digest(
        {
            "deletion_request_id": str(request.id),
            "tombstones": [
                {
                    "object_class": item.object_class,
                    "row_count": item.row_count,
                    "content_digest": item.content_digest,
                }
                for item in tombstones
            ],
        }
    )
    audit_head = await verify_privacy_chain(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=request.id,
    )
    proof = await issue_deletion_proof(
        session,
        request=request,
        tombstones=tombstones,
        revocations=revocations,
        file_deletions=file_deletions,
        receipts=receipts,
        preserved=preserved,
        audit_head_digest=audit_head or request.tombstone_digest,
        schema_revision="202610220068",
        completed_at=completed_at,
    )
    request.status = DeletionRequestStatus.COMPLETED.value
    request.completed_at = completed_at
    await append_privacy_event(
        session,
        workspace_id=workspace_id,
        stream_type=PrivacyStreamType.DELETION_REQUEST,
        stream_id=request.id,
        event_type="deletion_execution_completed",
        actor_user_id=actor_user_id,
        actor_kind=PrivacyActorKind.USER,
        payload={
            "proof_number": proof.proof_number,
            "proof_digest": proof.proof_digest,
            "tombstone_count": len(tombstones),
            "revocations": revocations,
            "file_deletions": dataclasses.asdict(file_deletions),
            "preserved": preserved,
        },
    )
    return DeletionExecutionResult(
        request=request,
        proof=proof,
        tombstones=tombstones,
        revocations=revocations,
        file_deletions=file_deletions,
        preserved=preserved,
    )


__all__ = [
    "DeletionExecutionError",
    "DeletionExecutionResult",
    "FileDeletionResult",
    "ObjectClassResult",
    "execute_deletion_request",
    "purge_project_target",
    "purge_workspace_target",
]
```

- [ ] **Step 5: 运行测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_executor.py
```

Expected: `1 passed`。如果 SQLite 不支持某个约束，修模型或执行器，不得放宽断言。

- [ ] **Step 6: 检查导入与 lint**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run ruff check src/data_intelligence_hub/services/deletion_executor.py \
  src/data_intelligence_hub/services/deletion_proof.py \
  tests/unit/test_deletion_executor.py
uv run mypy src/data_intelligence_hub/services/deletion_executor.py \
  src/data_intelligence_hub/services/deletion_proof.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

- [ ] **Step 7: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/deletion_proof.py \
  apps/api/src/data_intelligence_hub/services/deletion_executor.py \
  apps/api/tests/unit/test_deletion_executor.py
git commit -m "feat(privacy): 添加删除执行、文件清理、墓碑与删除证明"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 6: 恢复后删除重放

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/deletion_replay.py`
- Test: `apps/api/tests/unit/test_deletion_replay.py`

**Interfaces:**
- Consumes: `DeletionTombstone`、`purge_project_target`、`purge_workspace_target`、`DeletionReplayRun`、`DeletionReplayItem`、`DeliveryStore`。
- Produces: `DeletionReplayError`、`build_deletion_manifest`、`write_deletion_manifest`、`apply_deletion_manifest`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_deletion_replay.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.privacy_deletion import (
    DeletionReplayItem,
    DeletionReplayItemStatus,
    DeletionReplayStatus,
    DeletionRequest,
    DeletionRequestStatus,
    DeletionTombstone,
)
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_replay import (
    apply_deletion_manifest,
    build_deletion_manifest,
)


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed(session: AsyncSession) -> dict[str, uuid.UUID]:
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    request_id = uuid.uuid4()
    now = datetime.now(UTC)
    session.add_all(
        [
            User(id=owner_id, email="replay-owner@example.com", password_hash="x", name="Owner"),
            Workspace(id=workspace_id, name="Replay WS", slug="replay-ws", owner_id=owner_id),
            WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role="owner"),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                name="Replay Project",
                domain="mixed",
                status="deleted",
                owner_id=owner_id,
            ),
            DeletionRequest(
                id=request_id,
                workspace_id=workspace_id,
                project_id=project_id,
                target_type="project",
                target_id=project_id,
                target_name_snapshot="Replay Project",
                requested_by_user_id=owner_id,
                requested_by_role="owner",
                status=DeletionRequestStatus.COMPLETED.value,
                completed_at=now,
            ),
            DeletionTombstone(
                id=uuid.uuid4(),
                deletion_request_id=request_id,
                workspace_id=workspace_id,
                project_id=project_id,
                target_type="project",
                target_id=project_id,
                object_class="raw_records",
                row_count=1,
                content_digest="sha256:" + "a" * 64,
                deleted_at=now,
            ),
            DeletionTombstone(
                id=uuid.uuid4(),
                deletion_request_id=request_id,
                workspace_id=workspace_id,
                project_id=project_id,
                target_type="project",
                target_id=project_id,
                object_class="project",
                row_count=1,
                content_digest="sha256:" + "b" * 64,
                deleted_at=now,
            ),
        ]
    )
    await session.commit()
    return {"owner": owner_id, "workspace": workspace_id, "project": project_id}


@pytest.mark.asyncio
async def test_replay_removes_restored_rows_without_duplicate_tombstones(
    session: AsyncSession, tmp_path: Path
) -> None:
    ids = await _seed(session)
    manifest = await build_deletion_manifest(session, workspace_id=ids["workspace"])
    session.add(
        RawRecord(
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            record_type="page",
            content={"secret": "restored"},
            content_hash="c" * 64,
            collected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    before = len(list((await session.execute(select(DeletionTombstone))).scalars()))
    run = await apply_deletion_manifest(
        session,
        manifest=manifest,
        source_backup_ref="backup-2026-10-22",
        operator_label="ops@example.com",
        delivery_store=DeliveryStore(tmp_path / "delivery"),
    )
    after = len(list((await session.execute(select(DeletionTombstone))).scalars()))
    assert run.status == DeletionReplayStatus.COMPLETED.value
    assert run.replayed_count == 1
    assert before == after
    remaining = await session.execute(select(RawRecord))
    assert remaining.first() is None


@pytest.mark.asyncio
async def test_replay_marks_absent_target(session: AsyncSession, tmp_path: Path) -> None:
    ids = await _seed(session)
    manifest = await build_deletion_manifest(session, workspace_id=ids["workspace"])
    manifest["tombstones"].append(
        {
            "deletion_request_id": str(uuid.uuid4()),
            "target_type": "project",
            "target_id": str(uuid.uuid4()),
            "object_class": "raw_records",
            "row_count": 1,
            "content_digest": "sha256:" + "d" * 64,
            "deleted_at": datetime.now(UTC).isoformat(),
        }
    )
    run = await apply_deletion_manifest(
        session,
        manifest=manifest,
        source_backup_ref="backup-2026-10-22",
        operator_label="ops@example.com",
        delivery_store=DeliveryStore(tmp_path / "delivery"),
    )
    items = list(
        (
            await session.execute(
                select(DeletionReplayItem).where(DeletionReplayItem.run_id == run.id)
            )
        ).scalars()
    )
    assert any(item.status == DeletionReplayItemStatus.SKIPPED_ABSENT.value for item in items)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_replay.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.deletion_replay`。

- [ ] **Step 3: 实现 manifest 与重放**

Create `apps/api/src/data_intelligence_hub/services/deletion_replay.py`:

```python
"""恢复后删除重放。

manifest 由删除完成后的墓碑生成，保存在备份库以外的控制面。
恢复后把 manifest 交给本模块，重新执行同一目标的删除。
重放不写新墓碑，不生成新证明，只记录重放批次和条目。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionReplayItem,
    DeletionReplayItemStatus,
    DeletionReplayRun,
    DeletionReplayStatus,
    DeletionRequest,
    DeletionRequestStatus,
    DeletionTombstone,
    PrivacyActorKind,
    PrivacyStreamType,
)
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_executor import (
    DeletionExecutionError,
    purge_project_target,
    purge_workspace_target,
)
from data_intelligence_hub.services.privacy_audit import (
    append_privacy_event,
    sha256_digest,
)


class DeletionReplayError(Exception):
    pass


async def build_deletion_manifest(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> dict[str, Any]:
    request_result = await session.execute(
        select(DeletionRequest.id).where(
            DeletionRequest.workspace_id == workspace_id,
            DeletionRequest.status == DeletionRequestStatus.COMPLETED.value,
        )
    )
    request_ids = list(request_result.scalars().all())
    tombstone_result = await session.execute(
        select(DeletionTombstone)
        .where(DeletionTombstone.deletion_request_id.in_(request_ids or [uuid.uuid4()]))
        .order_by(DeletionTombstone.deleted_at.asc(), DeletionTombstone.id)
    )
    tombstones = [
        {
            "deletion_request_id": str(item.deletion_request_id),
            "target_type": item.target_type,
            "target_id": str(item.target_id),
            "object_class": item.object_class,
            "row_count": item.row_count,
            "content_digest": item.content_digest,
            "deleted_at": item.deleted_at.astimezone(UTC).isoformat(),
        }
        for item in tombstone_result.scalars().all()
    ]
    payload: dict[str, Any] = {
        "manifest_version": "deletion_manifest.v1",
        "workspace_id": str(workspace_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "tombstones": tombstones,
    }
    payload["manifest_digest"] = sha256_digest(payload)
    return payload


async def write_deletion_manifest(
    session: AsyncSession, *, workspace_id: uuid.UUID, output_path: Path
) -> dict[str, Any]:
    manifest = await build_deletion_manifest(session, workspace_id=workspace_id)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def _verify_manifest(manifest: dict[str, Any]) -> None:
    supplied = manifest.get("manifest_digest")
    if not isinstance(supplied, str):
        raise DeletionReplayError("deletion_manifest_digest_missing")
    body = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    if sha256_digest(body) != supplied:
        raise DeletionReplayError("deletion_manifest_digest_invalid")
    if manifest.get("manifest_version") != "deletion_manifest.v1":
        raise DeletionReplayError("deletion_manifest_version_invalid")


async def _record_item(
    session: AsyncSession,
    run: DeletionReplayRun,
    target_type: str,
    target_id: uuid.UUID,
    status: DeletionReplayItemStatus,
    detail: str | None,
) -> None:
    session.add(
        DeletionReplayItem(
            id=uuid.uuid4(),
            run_id=run.id,
            target_type=target_type,
            target_id=target_id,
            status=status.value,
            detail=detail,
        )
    )


async def apply_deletion_manifest(
    session: AsyncSession,
    *,
    manifest: dict[str, Any],
    source_backup_ref: str,
    operator_label: str,
    delivery_store: DeliveryStore,
) -> DeletionReplayRun:
    _verify_manifest(manifest)
    workspace_value = manifest.get("workspace_id")
    workspace_id = None if workspace_value is None else uuid.UUID(str(workspace_value))
    run = DeletionReplayRun(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        manifest_digest=str(manifest["manifest_digest"]),
        source_backup_ref=source_backup_ref,
        status=DeletionReplayStatus.RUNNING.value,
        operator_label=operator_label,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    grouped: dict[tuple[str, uuid.UUID], uuid.UUID] = {}
    for item in manifest.get("tombstones", []):
        key = (str(item["target_type"]), uuid.UUID(str(item["target_id"])))
        grouped.setdefault(key, uuid.UUID(str(item["deletion_request_id"])))
    for (target_type, target_id), request_id in sorted(grouped.items()):
        request = await session.get(DeletionRequest, request_id)
        if request is None:
            await _record_item(
                session,
                run,
                target_type,
                target_id,
                DeletionReplayItemStatus.SKIPPED_ABSENT,
                "deletion_request_absent",
            )
            continue
        try:
            if target_type == "project":
                await purge_project_target(
                    session,
                    request=request,
                    project_id=target_id,
                    delivery_store=delivery_store,
                    record_tombstones=False,
                    audit_share_noop=False,
                )
            elif target_type == "workspace":
                await purge_workspace_target(
                    session,
                    request=request,
                    delivery_store=delivery_store,
                    record_tombstones=False,
                )
            else:
                raise DeletionReplayError("deletion_manifest_target_invalid")
        except DeletionExecutionError as exc:
            await _record_item(
                session,
                run,
                target_type,
                target_id,
                DeletionReplayItemStatus.FAILED,
                exc.code,
            )
            continue
        await _record_item(
            session,
            run,
            target_type,
            target_id,
            DeletionReplayItemStatus.REPLAYED,
            None,
        )
    items_result = await session.execute(
        select(DeletionReplayItem).where(DeletionReplayItem.run_id == run.id)
    )
    items = list(items_result.scalars().all())
    run.matched_count = len(items)
    run.replayed_count = sum(
        1 for item in items if item.status == DeletionReplayItemStatus.REPLAYED.value
    )
    run.failed_count = sum(
        1 for item in items if item.status == DeletionReplayItemStatus.FAILED.value
    )
    run.status = (
        DeletionReplayStatus.FAILED.value
        if run.failed_count
        else DeletionReplayStatus.COMPLETED.value
    )
    run.finished_at = datetime.now(UTC)
    await session.flush()
    if workspace_id is not None:
        await append_privacy_event(
            session,
            workspace_id=workspace_id,
            stream_type=PrivacyStreamType.DELETION_REPLAY,
            stream_id=run.id,
            event_type="deletion_replay_completed",
            actor_user_id=None,
            actor_kind=PrivacyActorKind.OPERATOR,
            payload={
                "matched_count": run.matched_count,
                "replayed_count": run.replayed_count,
                "failed_count": run.failed_count,
            },
        )
    return run


__all__ = [
    "DeletionReplayError",
    "apply_deletion_manifest",
    "build_deletion_manifest",
    "write_deletion_manifest",
]
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_deletion_replay.py
```

Expected: `2 passed`。第一条测试中恢复的 `RawRecord` 必须被删除，且墓碑数量不变。第二条测试必须出现 `skipped_absent` 条目。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/deletion_replay.py \
  apps/api/tests/unit/test_deletion_replay.py
git commit -m "feat(privacy): 添加恢复后删除重放"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 7: 隐私 API、仓库查询与鉴权

**Files:**
- Create: `apps/api/src/data_intelligence_hub/repositories/privacy.py`
- Create: `apps/api/src/data_intelligence_hub/schemas/privacy.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/privacy.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/projects.py`
- Test: `apps/api/tests/unit/test_privacy_routes.py`

**Interfaces:**
- Consumes: Task 3–6 的服务、`AuthenticatedContextDep`、C2 `require_project_access`、C10 `DeliveryStore`、C11 法律保留读取。
- Produces: `/api/privacy/*` 路由与响应模型。

- [ ] **Step 1: 写失败的路由测试**

Create `apps/api/tests/unit/test_privacy_routes.py`。覆盖：owner 创建返回明文 token；admin 创建待 owner 批准；member 403；错误确认文本 409；法律保留只读；路由没有额外全局依赖。

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext
from data_intelligence_hub.api.routes import privacy as privacy_routes
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.retention import LegalHold
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.privacy import DeletionRequestCreate


@pytest_asyncio.fixture()
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as current:
        yield current
    await engine.dispose()


async def _seed(session: AsyncSession) -> dict[str, uuid.UUID]:
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session.add_all(
        [
            User(id=owner_id, email="route-owner@example.com", password_hash="x", name="Owner"),
            User(id=admin_id, email="route-admin@example.com", password_hash="x", name="Admin"),
            User(id=member_id, email="route-member@example.com", password_hash="x", name="Member"),
            Workspace(id=workspace_id, name="Route WS", slug="route-ws", owner_id=owner_id),
            WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role="owner"),
            WorkspaceMember(workspace_id=workspace_id, user_id=admin_id, role="admin"),
            WorkspaceMember(workspace_id=workspace_id, user_id=member_id, role="member"),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                name="Route Project",
                domain="mixed",
                status="active",
                owner_id=owner_id,
            ),
        ]
    )
    await session.commit()
    return {
        "owner": owner_id,
        "admin": admin_id,
        "member": member_id,
        "workspace": workspace_id,
        "project": project_id,
    }


async def _context(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> AuthContext:
    user = await session.get(User, user_id)
    workspace = await session.get(Workspace, workspace_id)
    assert user is not None and workspace is not None
    return AuthContext(user=user, workspace=workspace)


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        privacy_routes,
        "get_settings",
        lambda: type("S", (), {"privacy_deletion_enabled": True})(),
    )


@pytest.mark.asyncio
async def test_owner_create_and_member_forbidden(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = await _seed(session)
    _enable(monkeypatch)
    owner_context = await _context(session, ids["owner"], ids["workspace"])
    created = await privacy_routes.create_deletion_request_endpoint(
        DeletionRequestCreate(
            target_type="project", project_id=ids["project"], reason="客户要求"
        ),
        session,
        owner_context,
    )
    assert created.confirmation_token is not None
    assert created.confirmation_phrase == "DELETE Route Project"

    member_context = await _context(session, ids["member"], ids["workspace"])
    with pytest.raises(APIError) as forbidden:
        await privacy_routes.create_deletion_request_endpoint(
            DeletionRequestCreate(
                target_type="project", project_id=ids["project"], reason=None
            ),
            session,
            member_context,
        )
    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_approve_and_wrong_text_conflicts(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = await _seed(session)
    _enable(monkeypatch)
    admin_context = await _context(session, ids["admin"], ids["workspace"])
    created = await privacy_routes.create_deletion_request_endpoint(
        DeletionRequestCreate(target_type="project", project_id=ids["project"], reason=None),
        session,
        admin_context,
    )
    assert created.request.status == "pending_owner_approval"

    with pytest.raises(APIError) as not_owner:
        await privacy_routes.approve_deletion_request_endpoint(
            created.request.id,
            privacy_routes.DeletionApproveRequest(decision="approve"),
            session,
            admin_context,
        )
    assert not_owner.value.code == "workspace_owner_required"

    owner_context = await _context(session, ids["owner"], ids["workspace"])
    approved = await privacy_routes.approve_deletion_request_endpoint(
        created.request.id,
        privacy_routes.DeletionApproveRequest(decision="approve"),
        session,
        owner_context,
    )
    with pytest.raises(APIError) as conflict:
        await privacy_routes.confirm_deletion_request_endpoint(
            approved.id,
            privacy_routes.DeletionConfirmRequest(
                confirmation_token=approved.confirmation_token or "",
                confirmation_text="DELETE 错误项目",
            ),
            session,
            owner_context,
        )
    assert conflict.value.status_code == 409
    assert conflict.value.code == "deletion_state_conflict"


@pytest.mark.asyncio
async def test_legal_hold_read_only(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = await _seed(session)
    _enable(monkeypatch)
    session.add(
        LegalHold(
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            data_class="raw_response",
            status="active",
            reason="诉讼",
            requested_by_user_id=ids["owner"],
            requested_at=datetime.now(UTC),
        )
    )
    await session.flush()
    owner_context = await _context(session, ids["owner"], ids["workspace"])
    rows = await privacy_routes.list_legal_holds_endpoint(session, owner_context)
    assert len(rows) == 1
    assert rows[0].data_class == "raw_response"
    assert privacy_routes.router.dependencies == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_routes.py
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.api.routes.privacy`。

- [ ] **Step 3: 新增配置开关**

在 `core/config.py` 追加：

```python
    # 隐私删除写接口开关。默认关闭。PG0 发布批次负责打开；C14 只读验收。
    privacy_deletion_enabled: bool = False
    # 只允许专用清理角色使用。普通应用不配置。
    privacy_audit_cleaner_database_url: str | None = None
```

- [ ] **Step 4: 实现仓库查询**

Create `apps/api/src/data_intelligence_hub/repositories/privacy.py`:

```python
"""隐私对象的只读查询。写操作在 service 层。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.privacy_deletion import (
    DeletionProof,
    DeletionRequest,
    DeletionSubprocessorReceipt,
    DsrCase,
    PrivacyAuditEvent,
)
from data_intelligence_hub.models.retention import LegalHold


async def get_deletion_request(
    session: AsyncSession, *, workspace_id: uuid.UUID, request_id: uuid.UUID
) -> DeletionRequest | None:
    result = await session.execute(
        select(DeletionRequest).where(
            DeletionRequest.id == request_id,
            DeletionRequest.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_deletion_requests(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> list[DeletionRequest]:
    statement = select(DeletionRequest).where(DeletionRequest.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(DeletionRequest.project_id == project_id)
    result = await session.execute(
        statement.order_by(DeletionRequest.created_at.desc(), DeletionRequest.id)
    )
    return list(result.scalars().all())


async def get_proof(
    session: AsyncSession, *, workspace_id: uuid.UUID, request_id: uuid.UUID
) -> DeletionProof | None:
    result = await session.execute(
        select(DeletionProof).where(
            DeletionProof.deletion_request_id == request_id,
            DeletionProof.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_receipts(
    session: AsyncSession, *, workspace_id: uuid.UUID, request_id: uuid.UUID
) -> list[DeletionSubprocessorReceipt]:
    result = await session.execute(
        select(DeletionSubprocessorReceipt)
        .where(
            DeletionSubprocessorReceipt.deletion_request_id == request_id,
            DeletionSubprocessorReceipt.workspace_id == workspace_id,
        )
        .order_by(DeletionSubprocessorReceipt.subprocessor_name)
    )
    return list(result.scalars().all())


async def list_holds(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> list[LegalHold]:
    result = await session.execute(
        select(LegalHold)
        .where(LegalHold.workspace_id == workspace_id)
        .order_by(LegalHold.requested_at.desc(), LegalHold.id)
    )
    return list(result.scalars().all())


async def list_dsr_cases(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> list[DsrCase]:
    result = await session.execute(
        select(DsrCase)
        .where(DsrCase.workspace_id == workspace_id)
        .order_by(DsrCase.received_at.desc(), DsrCase.id)
    )
    return list(result.scalars().all())


async def get_dsr_case(
    session: AsyncSession, *, workspace_id: uuid.UUID, case_id: uuid.UUID
) -> DsrCase | None:
    result = await session.execute(
        select(DsrCase).where(DsrCase.id == case_id, DsrCase.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def list_audit_events(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    stream_type: str | None = None,
    stream_id: uuid.UUID | None = None,
    limit: int = 500,
) -> list[PrivacyAuditEvent]:
    statement = select(PrivacyAuditEvent).where(PrivacyAuditEvent.workspace_id == workspace_id)
    if stream_type is not None:
        statement = statement.where(PrivacyAuditEvent.stream_type == stream_type)
    if stream_id is not None:
        statement = statement.where(PrivacyAuditEvent.stream_id == stream_id)
    result = await session.execute(
        statement.order_by(
            PrivacyAuditEvent.recorded_at.asc(),
            PrivacyAuditEvent.stream_type,
            PrivacyAuditEvent.stream_id,
            PrivacyAuditEvent.sequence_number,
        ).limit(limit)
    )
    return list(result.scalars().all())
```

- [ ] **Step 5: 实现 schema**

Create `apps/api/src/data_intelligence_hub/schemas/privacy.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeletionRequestCreate(BaseModel):
    target_type: Literal["project", "workspace"]
    project_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)


class DeletionApproveRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)


class DeletionConfirmRequest(BaseModel):
    confirmation_token: str = Field(min_length=16, max_length=200)
    confirmation_text: str = Field(min_length=1, max_length=240)


class DeletionCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class DeletionRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    target_type: str
    target_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    requested_by_role: str
    status: str
    confirmation_expires_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    confirmed_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    tombstone_digest: str | None
    created_at: datetime


class DeletionRequestCreatedResponse(DeletionRequestResponse):
    confirmation_token: str | None = None
    confirmation_phrase: str | None = None


class DeletionProofResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    proof_number: str
    payload: dict[str, Any]
    proof_digest: str
    audit_head_digest: str
    issued_at: datetime


class SubprocessorReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subprocessor_name: str
    status: str
    request_reference: str | None
    receipt_reference: str | None
    received_at: datetime | None


class LegalHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    data_class: str | None
    status: str
    reason: str
    requested_by_user_id: uuid.UUID
    requested_at: datetime
    released_at: datetime | None
    release_reason: str | None


class DsrCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_number: str
    project_id: uuid.UUID | None
    request_type: str
    status: str
    responsibility: str
    received_at: datetime
    due_at: datetime | None
    closed_at: datetime | None
    deletion_request_id: uuid.UUID | None


class PrivacyAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stream_type: str
    stream_id: uuid.UUID
    sequence_number: int
    previous_event_digest: str | None
    event_digest: str
    event_type: str
    actor_user_id: uuid.UUID | None
    actor_kind: str
    payload: dict[str, Any]
    occurred_at: datetime
```

- [ ] **Step 6: 实现路由**

Create `apps/api/src/data_intelligence_hub/api/routes/privacy.py`:

```python
"""隐私删除、DSR 与审计 API。

写操作要求 owner 或 admin 的会话。admin 只能发起；owner 批准、确认和执行。
项目目标还必须通过 C2 的项目 ACL。路由不挂额外认证依赖。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.repositories import privacy as privacy_repo
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.schemas.privacy import (
    DeletionApproveRequest,
    DeletionCancelRequest,
    DeletionConfirmRequest,
    DeletionProofResponse,
    DeletionRequestCreate,
    DeletionRequestCreatedResponse,
    DeletionRequestResponse,
    DsrCaseResponse,
    LegalHoldResponse,
    PrivacyAuditEventResponse,
    SubprocessorReceiptResponse,
)
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_executor import (
    DeletionExecutionError,
    execute_deletion_request,
)
from data_intelligence_hub.services.deletion_service import (
    DeletionStateError,
    approve_deletion_request,
    cancel_deletion_request,
    confirm_deletion_request,
    create_deletion_request,
    mark_deletion_failed,
    reevaluate_deletion_request,
    resend_confirmation,
    retry_deletion_request,
)

router = APIRouter(tags=["privacy"])
STATE_CONFLICT_CODES = {
    "deletion_request_state_conflict",
    "deletion_confirmation_expired",
    "deletion_confirmation_not_issued",
    "deletion_confirmation_token_invalid",
    "deletion_confirmation_text_mismatch",
    "deletion_decision_invalid",
    "deletion_target_has_active_runs",
    "deletion_target_already_deleted",
    "deletion_request_active_exists",
    "deletion_role_conflict",
    "deletion_self_approval_forbidden",
}


def _enabled() -> None:
    if not get_settings().privacy_deletion_enabled:
        # 开关关闭时写接口按不存在处理。不新增未登记的错误码。
        raise APIError(404, "deletion_request_not_found")


async def _role(session: SessionDep, context: AuthenticatedContextDep) -> str:
    role = await get_workspace_role(session, context.workspace.id, context.user.id)
    if role is None:
        raise APIError(403, "workspace_membership_required")
    return role


def _require_owner(role: str) -> None:
    if role != "owner":
        raise APIError(403, "workspace_owner_required")


def _require_admin_or_owner(role: str) -> None:
    if role not in {"owner", "admin"}:
        raise APIError(403, "workspace_role_forbidden")


async def _check_project_access(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID | None,
) -> None:
    if project_id is None:
        raise APIError(400, "invalid_request")
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )


def _state_error(exc: DeletionStateError) -> APIError:
    if exc.code == "deletion_request_not_found":
        return APIError(404, "deletion_request_not_found")
    if exc.code == "legal_hold_active":
        return APIError(409, "legal_hold_active")
    if exc.code in STATE_CONFLICT_CODES:
        return APIError(409, "deletion_state_conflict")
    if exc.status_code == 403:
        return APIError(403, "workspace_owner_required")
    return APIError(409, "deletion_state_conflict")


def _execution_error(exc: DeletionExecutionError) -> APIError:
    if exc.code == "deletion_request_not_found":
        return APIError(404, "deletion_request_not_found")
    if exc.code == "legal_hold_active":
        return APIError(409, "legal_hold_active")
    if exc.code == "workspace_owner_required":
        return APIError(403, "workspace_owner_required")
    return APIError(409, "deletion_state_conflict")


async def _request_or_404(
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: uuid.UUID,
):
    record = await privacy_repo.get_deletion_request(
        session, workspace_id=context.workspace.id, request_id=request_id
    )
    if record is None:
        raise APIError(404, "deletion_request_not_found")
    return record


def _delivery_store() -> DeliveryStore:
    return DeliveryStore(Path(get_settings().delivery_export_dir))


DeliveryStoreDep = Annotated[DeliveryStore, Depends(_delivery_store)]


@router.post(
    "/deletion-requests",
    response_model=DeletionRequestCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deletion_request_endpoint(
    payload: DeletionRequestCreate,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> DeletionRequestCreatedResponse:
    _enabled()
    role = await _role(session, context)
    _require_admin_or_owner(role)
    if payload.target_type == "project":
        await _check_project_access(session, context, payload.project_id)
    try:
        created = await create_deletion_request(
            session,
            workspace_id=context.workspace.id,
            requested_by_user_id=context.user.id,
            target_type=payload.target_type,
            project_id=payload.project_id,
            reason=payload.reason,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestCreatedResponse(
        **DeletionRequestResponse.model_validate(created.request).model_dump(),
        confirmation_token=created.confirmation_token,
        confirmation_phrase=created.confirmation_phrase,
    )


@router.get("/deletion-requests", response_model=list[DeletionRequestResponse])
async def list_deletion_requests_endpoint(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID | None = Query(default=None),
) -> list[DeletionRequestResponse]:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    rows = await privacy_repo.list_deletion_requests(
        session, workspace_id=context.workspace.id, project_id=project_id
    )
    return [DeletionRequestResponse.model_validate(row) for row in rows]


@router.get("/deletion-requests/{request_id}", response_model=DeletionRequestResponse)
async def get_deletion_request_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DeletionRequestResponse:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    record = await _request_or_404(session, context, request_id)
    return DeletionRequestResponse.model_validate(record)


@router.post(
    "/deletion-requests/{request_id}/approve",
    response_model=DeletionRequestCreatedResponse,
)
async def approve_deletion_request_endpoint(
    request_id: uuid.UUID,
    payload: DeletionApproveRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> DeletionRequestCreatedResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        created = await approve_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
            decision=payload.decision,
            reason=payload.reason,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestCreatedResponse(
        **DeletionRequestResponse.model_validate(created.request).model_dump(),
        confirmation_token=created.confirmation_token,
        confirmation_phrase=created.confirmation_phrase,
    )


@router.post(
    "/deletion-requests/{request_id}/confirm",
    response_model=DeletionRequestResponse,
)
async def confirm_deletion_request_endpoint(
    request_id: uuid.UUID,
    payload: DeletionConfirmRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> DeletionRequestResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        record = await confirm_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
            token=payload.confirmation_token,
            confirmation_text=payload.confirmation_text,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestResponse.model_validate(record)


@router.post(
    "/deletion-requests/{request_id}/resend-confirmation",
    response_model=DeletionRequestCreatedResponse,
)
async def resend_confirmation_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DeletionRequestCreatedResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        created = await resend_confirmation(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestCreatedResponse(
        **DeletionRequestResponse.model_validate(created.request).model_dump(),
        confirmation_token=created.confirmation_token,
        confirmation_phrase=created.confirmation_phrase,
    )


@router.post(
    "/deletion-requests/{request_id}/cancel",
    response_model=DeletionRequestResponse,
)
async def cancel_deletion_request_endpoint(
    request_id: uuid.UUID,
    payload: DeletionCancelRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> DeletionRequestResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        record = await cancel_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
            reason=payload.reason,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestResponse.model_validate(record)


@router.post(
    "/deletion-requests/{request_id}/retry",
    response_model=DeletionRequestResponse,
)
async def retry_deletion_request_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DeletionRequestResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        record = await retry_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestResponse.model_validate(record)


@router.post(
    "/deletion-requests/{request_id}/reevaluate",
    response_model=DeletionRequestResponse,
)
async def reevaluate_deletion_request_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DeletionRequestResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    try:
        record = await reevaluate_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
        )
        await session.commit()
    except DeletionStateError as exc:
        await session.rollback()
        raise _state_error(exc) from exc
    return DeletionRequestResponse.model_validate(record)


@router.post(
    "/deletion-requests/{request_id}/execute",
    response_model=DeletionProofResponse,
)
async def execute_deletion_request_endpoint(
    request_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    delivery_store: DeliveryStoreDep,
) -> DeletionProofResponse:
    _enabled()
    role = await _role(session, context)
    _require_owner(role)
    record = await _request_or_404(session, context, request_id)
    if record.target_type == "project":
        await _check_project_access(session, context, record.project_id)
    try:
        result = await execute_deletion_request(
            session,
            request_id=request_id,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
            delivery_store=delivery_store,
        )
        await session.commit()
    except DeletionExecutionError as exc:
        await session.rollback()
        try:
            await mark_deletion_failed(
                session,
                request_id=request_id,
                workspace_id=context.workspace.id,
                actor_user_id=context.user.id,
                code=exc.code,
            )
            await session.commit()
        except DeletionStateError:
            await session.rollback()
        raise _execution_error(exc) from exc
    return DeletionProofResponse.model_validate(result.proof)


@router.get(
    "/deletion-requests/{request_id}/proof",
    response_model=DeletionProofResponse,
)
async def get_deletion_proof_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DeletionProofResponse:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    proof = await privacy_repo.get_proof(
        session, workspace_id=context.workspace.id, request_id=request_id
    )
    if proof is None:
        raise APIError(409, "deletion_proof_not_ready")
    return DeletionProofResponse.model_validate(proof)


@router.get(
    "/deletion-requests/{request_id}/subprocessor-receipts",
    response_model=list[SubprocessorReceiptResponse],
)
async def list_subprocessor_receipts_endpoint(
    request_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> list[SubprocessorReceiptResponse]:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    await _request_or_404(session, context, request_id)
    rows = await privacy_repo.list_receipts(
        session, workspace_id=context.workspace.id, request_id=request_id
    )
    return [SubprocessorReceiptResponse.model_validate(row) for row in rows]


@router.get("/legal-holds", response_model=list[LegalHoldResponse])
async def list_legal_holds_endpoint(
    session: SessionDep, context: AuthenticatedContextDep
) -> list[LegalHoldResponse]:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    rows = await privacy_repo.list_holds(session, workspace_id=context.workspace.id)
    return [LegalHoldResponse.model_validate(row) for row in rows]


@router.get("/dsr-cases", response_model=list[DsrCaseResponse])
async def list_dsr_cases_endpoint(
    session: SessionDep, context: AuthenticatedContextDep
) -> list[DsrCaseResponse]:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    rows = await privacy_repo.list_dsr_cases(session, workspace_id=context.workspace.id)
    return [DsrCaseResponse.model_validate(row) for row in rows]


@router.get("/dsr-cases/{case_id}", response_model=DsrCaseResponse)
async def get_dsr_case_endpoint(
    case_id: uuid.UUID, session: SessionDep, context: AuthenticatedContextDep
) -> DsrCaseResponse:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    row = await privacy_repo.get_dsr_case(
        session, workspace_id=context.workspace.id, case_id=case_id
    )
    if row is None:
        raise APIError(404, "dsr_case_not_found")
    return DsrCaseResponse.model_validate(row)


@router.get("/audit-events", response_model=list[PrivacyAuditEventResponse])
async def list_audit_events_endpoint(
    session: SessionDep,
    context: AuthenticatedContextDep,
    stream_type: str | None = Query(default=None),
    stream_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=500),
) -> list[PrivacyAuditEventResponse]:
    role = await _role(session, context)
    _require_admin_or_owner(role)
    rows = await privacy_repo.list_audit_events(
        session,
        workspace_id=context.workspace.id,
        stream_type=stream_type,
        stream_id=stream_id,
        limit=limit,
    )
    return [PrivacyAuditEventResponse.model_validate(row) for row in rows]
```

- [ ] **Step 7: 挂载路由**

在 `main.py` 追加 import 与 include：

```python
from data_intelligence_hub.api.routes.privacy import router as privacy_router
...
app.include_router(privacy_router, prefix="/api/privacy")
```

- [ ] **Step 8: 过滤已删除项目**

在 `repositories/projects.py` 的 `list_projects` 与 `get_project` 查询加：

```python
Project.status != "deleted"
```

不修改工作区解析。删除后的工作区仍只有原成员可访问，用于读取证明和审计。

- [ ] **Step 9: 运行路由测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_routes.py tests/unit/test_deletion_service.py
```

Expected: 全部 PASS。

- [ ] **Step 10: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/privacy.py \
  apps/api/src/data_intelligence_hub/schemas/privacy.py \
  apps/api/src/data_intelligence_hub/api/routes/privacy.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/src/data_intelligence_hub/repositories/projects.py \
  apps/api/tests/unit/test_privacy_routes.py
git commit -m "feat(privacy): 添加删除与 DSR 接口"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 8: 运维 CLI、审计保留清理与运行手册

**Files:**
- Create: `apps/api/src/data_intelligence_hub/maintenance/privacy_ops.py`
- Create: `apps/api/src/data_intelligence_hub/maintenance/privacy_receipts.py`
- Create: `apps/api/src/data_intelligence_hub/maintenance/privacy_audit_retention.py`
- Create: `docs/ops/privacy-deletion-dsr.md`
- Modify: `apps/api/.env.example`
- Modify: `configs/deploy/scrapy/docker-compose.yml`
- Test: `apps/api/tests/unit/test_privacy_ops_cli.py`
- Test: `apps/api/tests/unit/test_privacy_deploy_facts.py`
- Test: `apps/api/tests/unit/test_privacy_audit_retention.py`

**Interfaces:**
- Consumes: Task 3–6 的服务、`async_session_factory`。
- Produces: `privacy_ops` 只有 DSR、删除证明、manifest 和重放四组命令。回执录入在 `privacy_receipts`。审计清理在 `privacy_audit_retention`。

- [ ] **Step 1: 写 CLI 测试**

Create `apps/api/tests/unit/test_privacy_ops_cli.py`:

```python
from __future__ import annotations

from data_intelligence_hub.maintenance import privacy_ops


def test_parser_has_only_dsr_proof_and_deletion_groups() -> None:
    parser = privacy_ops._parser()
    actions = [action.dest for action in parser._actions if action.dest == "command"]
    assert actions == ["command"]
    help_text = parser.format_help()
    assert "dsr" in help_text
    assert "proof" in help_text
    assert "deletion" in help_text
    assert "receipt" not in help_text


def test_replay_defaults_are_explicit() -> None:
    args = privacy_ops._parser().parse_args(
        [
            "deletion",
            "replay",
            "--manifest",
            "/tmp/manifest.json",
            "--source-backup-ref",
            "backup-1",
            "--operator",
            "ops@example.com",
        ]
    )
    assert args.command == "deletion"
    assert args.action == "replay"
    assert args.manifest == "/tmp/manifest.json"
```

- [ ] **Step 2: 写审计保留测试**

Create `apps/api/tests/unit/test_privacy_audit_retention.py`:

```python
from __future__ import annotations

from pathlib import Path

from data_intelligence_hub.maintenance import privacy_audit_retention


def test_default_is_dry_run() -> None:
    args = privacy_audit_retention._parser().parse_args([])
    assert args.execute is False
    assert args.cutoff_months == 24


def test_sql_prunes_whole_old_streams() -> None:
    source = Path(privacy_audit_retention.__file__).read_text(encoding="utf-8")
    assert "current_user" in source
    assert "dih_privacy_audit_cleaner" in source
    assert "HAVING max(recorded_at) <" in source
    assert "LIMIT :batch_size" in source
```

- [ ] **Step 3: 运行失败测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_ops_cli.py tests/unit/test_privacy_audit_retention.py
```

Expected: FAIL，`privacy_ops` 或 `privacy_audit_retention` 尚不存在，或 CLI/SQL 断言未满足。不得在失败证据缺失时实现。

- [ ] **Step 4: 实现 privacy_ops**

Create `apps/api/src/data_intelligence_hub/maintenance/privacy_ops.py`:

```python
"""隐私运营命令行。

用法：
  uv run python -m data_intelligence_hub.maintenance.privacy_ops dsr open ...
  uv run python -m data_intelligence_hub.maintenance.privacy_ops dsr transition ...
  uv run python -m data_intelligence_hub.maintenance.privacy_ops deletion manifest ...
  uv run python -m data_intelligence_hub.maintenance.privacy_ops deletion replay ...
  uv run python -m data_intelligence_hub.maintenance.privacy_ops proof verify ...

本命令行只有 DSR、删除证明和重放。法律保留写入属于 C11。
回执录入在 privacy_receipts。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.privacy_deletion import DeletionProof, DsrStatus
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.deletion_proof import verify_proof_digest
from data_intelligence_hub.services.deletion_replay import (
    apply_deletion_manifest,
    write_deletion_manifest,
)
from data_intelligence_hub.services.dsr_service import open_dsr_case, transition_dsr_case


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def _payload(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


async def _run(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        if args.command == "dsr" and args.action == "open":
            result = await open_dsr_case(
                session,
                workspace_id=_uuid(args.workspace_id),
                project_id=None if args.project_id is None else _uuid(args.project_id),
                request_type=args.request_type,
                requester_ref=args.requester_ref,
                received_at=datetime.now(UTC),
                due_at=None,
                operator=args.operator,
            )
        elif args.command == "dsr" and args.action == "transition":
            result = await transition_dsr_case(
                session,
                case_id=_uuid(args.case_id),
                workspace_id=_uuid(args.workspace_id),
                target_status=DsrStatus(args.status),
                operator=args.operator,
                verification_method=args.verification_method,
                responsibility=args.responsibility,
                deletion_request_id=(
                    None
                    if args.deletion_request_id is None
                    else _uuid(args.deletion_request_id)
                ),
                note=args.note,
            )
        elif args.command == "deletion" and args.action == "manifest":
            result = await write_deletion_manifest(
                session, workspace_id=_uuid(args.workspace_id), output_path=Path(args.output)
            )
        elif args.command == "deletion" and args.action == "replay":
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            result = await apply_deletion_manifest(
                session,
                manifest=manifest,
                source_backup_ref=args.source_backup_ref,
                operator_label=args.operator,
                delivery_store=DeliveryStore(Path(get_settings().delivery_export_dir)),
            )
        elif args.command == "proof" and args.action == "verify":
            proof = (
                await session.execute(
                    select(DeletionProof).where(DeletionProof.id == _uuid(args.proof_id))
                )
            ).scalar_one_or_none()
            if proof is None:
                raise SystemExit("proof_not_found")
            print(
                _payload(
                    {"proof_number": proof.proof_number, "valid": verify_proof_digest(proof)}
                )
            )
            return
        else:
            raise SystemExit("unsupported_command")
        await session.commit()
    print(_payload(result))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Privacy deletion and DSR operations")
    sub = parser.add_subparsers(dest="command", required=True)

    dsr = sub.add_parser("dsr")
    dsr_sub = dsr.add_subparsers(dest="action", required=True)
    dsr_open = dsr_sub.add_parser("open")
    dsr_open.add_argument("--workspace-id", required=True)
    dsr_open.add_argument("--project-id")
    dsr_open.add_argument(
        "--request-type",
        choices=["access", "rectification", "restriction", "deletion"],
        required=True,
    )
    dsr_open.add_argument("--requester-ref", required=True)
    dsr_open.add_argument("--operator", required=True)
    dsr_move = dsr_sub.add_parser("transition")
    dsr_move.add_argument("--case-id", required=True)
    dsr_move.add_argument("--workspace-id", required=True)
    dsr_move.add_argument(
        "--status",
        choices=["verifying", "in_progress", "completed", "rejected", "closed"],
        required=True,
    )
    dsr_move.add_argument("--verification-method")
    dsr_move.add_argument(
        "--responsibility", choices=["controller", "processor", "undetermined"]
    )
    dsr_move.add_argument("--deletion-request-id")
    dsr_move.add_argument("--note")
    dsr_move.add_argument("--operator", required=True)

    deletion = sub.add_parser("deletion")
    deletion_sub = deletion.add_subparsers(dest="action", required=True)
    manifest = deletion_sub.add_parser("manifest")
    manifest.add_argument("--workspace-id", required=True)
    manifest.add_argument("--output", required=True)
    replay = deletion_sub.add_parser("replay")
    replay.add_argument("--manifest", required=True)
    replay.add_argument("--source-backup-ref", required=True)
    replay.add_argument("--operator", required=True)

    proof = sub.add_parser("proof")
    proof_sub = proof.add_subparsers(dest="action", required=True)
    verify = proof_sub.add_parser("verify")
    verify.add_argument("--proof-id", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 实现回执命令行**

Create `apps/api/src/data_intelligence_hub/maintenance/privacy_receipts.py`:

```python
"""子处理者回执命令行。

用法：
  uv run python -m data_intelligence_hub.maintenance.privacy_receipts receipt record ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.privacy_deletion import SubprocessorReceiptStatus
from data_intelligence_hub.services.subprocessor_receipts import (
    record_subprocessor_receipt,
)


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


async def _run(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        receipt = await record_subprocessor_receipt(
            session,
            deletion_request_id=_uuid(args.request_id),
            workspace_id=_uuid(args.workspace_id),
            subprocessor_name=args.subprocessor,
            status=SubprocessorReceiptStatus(args.status),
            request_reference=args.request_reference,
            receipt_reference=args.receipt_reference,
            received_at=(
                None if args.received_at is None else datetime.fromisoformat(args.received_at)
            ),
            evidence_note=args.note,
            operator=args.operator,
        )
        await session.commit()
    print(
        json.dumps(
            {
                "id": str(receipt.id),
                "subprocessor_name": receipt.subprocessor_name,
                "status": receipt.status,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Subprocessor receipt operations")
    sub = parser.add_subparsers(dest="command", required=True)
    receipt = sub.add_parser("receipt")
    receipt_sub = receipt.add_subparsers(dest="action", required=True)
    record = receipt_sub.add_parser("record")
    record.add_argument("--request-id", required=True)
    record.add_argument("--workspace-id", required=True)
    record.add_argument("--subprocessor", required=True)
    record.add_argument(
        "--status",
        choices=["pending", "requested", "acknowledged", "not_applicable"],
        required=True,
    )
    record.add_argument("--request-reference")
    record.add_argument("--receipt-reference")
    record.add_argument("--received-at")
    record.add_argument("--note")
    record.add_argument("--operator", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 实现审计保留清理**

Create `apps/api/src/data_intelligence_hub/maintenance/privacy_audit_retention.py`:

```python
"""隐私审计 24 个月保留清理。

只允许专用数据库角色 dih_privacy_audit_cleaner 执行。
默认 dry-run。--execute 才写库。
清理按完整流失批：只删除最后一条记录早于 cutoff 的流。
这样保留的流仍有完整哈希链。
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from data_intelligence_hub.core.config import get_settings

CLEANER_ROLE = "dih_privacy_audit_cleaner"
COUNT_OLD_STREAM_SQL = text(
    """
    SELECT count(*)
    FROM (
        SELECT workspace_id, stream_type, stream_id
        FROM privacy_audit_events
        GROUP BY workspace_id, stream_type, stream_id
        HAVING max(recorded_at) < now() - (:cutoff_months * interval '1 month')
    ) AS old_streams
    """
)
DELETE_OLD_STREAM_SQL = text(
    """
    WITH old_streams AS (
        SELECT workspace_id, stream_type, stream_id
        FROM privacy_audit_events
        GROUP BY workspace_id, stream_type, stream_id
        HAVING max(recorded_at) < now() - (:cutoff_months * interval '1 month')
        ORDER BY workspace_id, stream_type, stream_id
        LIMIT :batch_size
    )
    DELETE FROM privacy_audit_events AS events
    USING old_streams
    WHERE events.workspace_id = old_streams.workspace_id
      AND events.stream_type = old_streams.stream_type
      AND events.stream_id = old_streams.stream_id
    """
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Privacy audit retention cleanup")
    parser.add_argument("--execute", action="store_true", help="write changes")
    parser.add_argument("--cutoff-months", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=50)
    return parser


async def _run(args: argparse.Namespace) -> None:
    url = get_settings().privacy_audit_cleaner_database_url
    if not url:
        raise SystemExit("privacy_audit_cleaner_database_url_required")
    engine = create_async_engine(url)
    deleted = 0
    try:
        async with engine.connect() as connection:
            current_user = (await connection.execute(text("SELECT current_user"))).scalar_one()
        if current_user != CLEANER_ROLE:
            raise SystemExit("privacy_audit_cleaner_role_required")
        if not args.execute:
            async with engine.connect() as connection:
                candidates = (
                    await connection.execute(
                        COUNT_OLD_STREAM_SQL, {"cutoff_months": args.cutoff_months}
                    )
                ).scalar_one()
            print(
                f"mode=dry_run cutoff_months={args.cutoff_months} "
                f"candidate_streams={candidates}"
            )
            return
        while True:
            async with engine.begin() as connection:
                result = await connection.execute(
                    DELETE_OLD_STREAM_SQL,
                    {
                        "cutoff_months": args.cutoff_months,
                        "batch_size": args.batch_size,
                    },
                )
                count = result.rowcount or 0
            deleted += count
            print(
                f"mode=execute cutoff_months={args.cutoff_months} "
                f"batch_deleted={count} total={deleted}"
            )
            if count == 0:
                break
    finally:
        await engine.dispose()


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: 运行 CLI 冒烟与单元测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run pytest -q tests/unit/test_privacy_ops_cli.py tests/unit/test_privacy_audit_retention.py
uv run python -m data_intelligence_hub.maintenance.privacy_ops --help
uv run python -m data_intelligence_hub.maintenance.privacy_receipts --help
uv run python -m data_intelligence_hub.maintenance.privacy_audit_retention --help
```

Expected: `3 passed`。三次帮助文本退出码 0。`privacy_ops --help` 不出现法律保留或回执分组。

- [ ] **Step 8: 写运行手册**

Create `docs/ops/privacy-deletion-dsr.md`。至少包含：

```markdown
# 隐私删除与 DSR 运行手册

## 1. 状态机

pending_owner_approval → pending_confirmation → ready → executing → completed
admin 只能发起。owner 批准后仍要二次确认。
blocked_legal_hold 只能由 owner 在保留解除后 reevaluate。
executing 不能取消。

## 2. 删除前检查

1. 确认目标项目或工作区。
2. 确认没有 queued 或 running 的 run。
3. 确认没有 active 法律保留。法律保留的放置和解除使用 C11 的 retention_cleanup 命令行。
4. 确认发起人是 owner 或 admin。
5. 记录变更单号和操作者。

## 3. 法律保留

C12 只读展示。写入、释放和命令行由 C11 负责。
不得在 C12 的 privacy_ops 中添加法律保留命令。

## 4. 子处理者回执

uv run python -m data_intelligence_hub.maintenance.privacy_receipts receipt record \
  --request-id <uuid> --workspace-id <uuid> --subprocessor Apify \
  --status acknowledged --receipt-reference APIFY-2026-001 --operator "ops@example.com"

## 5. 删除证明

GET /api/privacy/deletion-requests/{request_id}/proof

证明只含对象类、行数、摘要、撤销计数、文件删除计数、保留元数据计数、回执摘要和审计头。
不含正文和个人数据。`preserved` 记录账本与证据等级保留的行数；`tombstones` 同时覆盖删除与脱敏的对象类。

## 6. 恢复后重放

备份恢复后、开放流量前执行：

uv run python -m data_intelligence_hub.maintenance.privacy_ops deletion manifest \
  --workspace-id <uuid> --output /secure/deletion-manifest.json

uv run python -m data_intelligence_hub.maintenance.privacy_ops deletion replay \
  --manifest /secure/deletion-manifest.json --source-backup-ref backup-2026-10-22 \
  --operator "ops@example.com"

重放完成后检查 deletion_replay_runs 的 replayed_count 和 failed_count。
failed_count 必须为 0。

## 7. 隐私审计保留

普通应用角色不能删除 privacy_audit_events。
DBA 先创建专用角色并授权：

CREATE ROLE dih_privacy_audit_cleaner NOLOGIN;
GRANT USAGE ON SCHEMA public TO dih_privacy_audit_cleaner;
GRANT SELECT, DELETE ON privacy_audit_events TO dih_privacy_audit_cleaner;

把专用 DSN 写入 PRIVACY_AUDIT_CLEANER_DATABASE_URL。默认 dry-run：

uv run python -m data_intelligence_hub.maintenance.privacy_audit_retention

确认候选数量后执行：

uv run python -m data_intelligence_hub.maintenance.privacy_audit_retention --execute

清理只删除最后一条记录早于 24 个月的完整流。活跃流的哈希链保持完整。

## 7.1 报告产物删除与审计脱敏角色

C9 的 report_artifacts 与 report_audit_events 有不可变触发器。
C12 的 068 为专用角色 dih_deletion_executor 增加 DELETE 例外，并为 report_audit_events 增加 UPDATE 例外。
068 同时保留 C11 的 067 保留期例外：dih_retention_cleaner 只能删除超过 730 天的审计行。
DBA 创建角色并把角色授予应用角色：

CREATE ROLE dih_deletion_executor NOLOGIN;
GRANT USAGE ON SCHEMA public TO dih_deletion_executor;
GRANT SELECT, DELETE ON report_artifacts TO dih_deletion_executor;
GRANT SELECT, UPDATE, DELETE ON report_audit_events TO dih_deletion_executor;
GRANT dih_deletion_executor TO <app_role>;

应用角色是该 NOLOGIN 角色的成员。成员关系只用于在受控事务内执行 SET LOCAL ROLE。
应用角色在常态角色下不得直接拥有 DELETE 或 UPDATE 权限。
执行器只在删除报告产物与脱敏报告审计事件的本地事务内进入该角色。

## 8. 发布交接

C12 不部署。A/B 两套环境由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。
生产 A：PG0 发布批次备份 → 迁移 068 → 健康检查；C14 浏览器合成删除验收通过后，由 PG0 批次打开开关。
生产 B：在 202610190045 的目标授权与备份门禁通过前保持 BLOCKED。不得应用 068。
生产 A 与生产 B 都不执行 downgrade 068。回滚是关闭 PRIVACY_DELETION_ENABLED 并回退应用版本，保留 068 已建的表和触发器。降级时的 C11 保留期函数恢复只用于受控测试库。
```

- [ ] **Step 9: 更新环境变量示例与共享 compose 静态映射**

在 `apps/api/.env.example` 追加：

```text
PRIVACY_DELETION_ENABLED=false
PRIVACY_AUDIT_CLEANER_DATABASE_URL=
```

在 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 段追加两行静态映射：

```yaml
      PRIVACY_DELETION_ENABLED: ${PRIVACY_DELETION_ENABLED:-false}
      PRIVACY_AUDIT_CLEANER_DATABASE_URL: ${PRIVACY_AUDIT_CLEANER_DATABASE_URL:-}
```

只加映射键，不设置生产值，不改 `configs/deploy/scrapy-new/**`。PG0 发布批次只在 `.env.production` 设置专用 DSN 与开关值并重启 api；C14 只读。不得把真实 DSN 写入仓库或日志。

Create `apps/api/tests/unit/test_privacy_deploy_facts.py`:

```python
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "configs/deploy/scrapy/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "apps/api/.env.example"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_env_example_has_privacy_switches() -> None:
    text = _text(ENV_EXAMPLE)
    assert "PRIVACY_DELETION_ENABLED=false" in text
    assert "PRIVACY_AUDIT_CLEANER_DATABASE_URL=" in text


def test_shared_compose_maps_privacy_switches() -> None:
    text = _text(COMPOSE)
    assert "PRIVACY_DELETION_ENABLED: ${PRIVACY_DELETION_ENABLED:-false}" in text
    assert (
        "PRIVACY_AUDIT_CLEANER_DATABASE_URL: "
        "${PRIVACY_AUDIT_CLEANER_DATABASE_URL:-}"
    ) in text
    assert "scrapy-new" not in text
```

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c12
rg -n 'PRIVACY_DELETION_ENABLED|PRIVACY_AUDIT_CLEANER_DATABASE_URL' \
  apps/api/.env.example configs/deploy/scrapy/docker-compose.yml
git diff --exit-code -- configs/deploy/scrapy-new/docker-compose.yml
cd apps/api
uv run pytest -q tests/unit/test_privacy_deploy_facts.py
```

Expected: `.env.example` 有两行命中，共享 compose 有两行命中；`scrapy-new` 的 diff 退出码 0；`2 passed`。

- [ ] **Step 10: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/maintenance/privacy_ops.py \
  apps/api/src/data_intelligence_hub/maintenance/privacy_receipts.py \
  apps/api/src/data_intelligence_hub/maintenance/privacy_audit_retention.py \
  apps/api/tests/unit/test_privacy_ops_cli.py \
  apps/api/tests/unit/test_privacy_audit_retention.py \
  apps/api/tests/unit/test_privacy_deploy_facts.py \
  docs/ops/privacy-deletion-dsr.md \
  apps/api/.env.example \
  configs/deploy/scrapy/docker-compose.yml
git commit -m "ops(privacy): 添加删除、DSR、重放与审计保留命令"
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`。

---

### Task 9: 全量验证、浏览器交接与发布交接

**Files:**
- Add/Modify: `docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md`（Task 0 从主工作树复制，尚未跟踪；本任务更新状态并首次提交）
- Test: 全量后端测试与边界检查

**Interfaces:**
- Consumes: Task 1–8 的全部交付物。
- Produces: C12 完成证据、C14 浏览器交接单、PG0 发布批次 A/B 交接单。

- [ ] **Step 1: 全量后端验证**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
uv run ruff check src tests
uv run mypy src tests
uv run pytest -q
uv run python ../../scripts/check_pytest_baseline.py
uv run alembic heads
```

Expected:

```text
ruff: All checks passed!
mypy: Success: no issues found
pytest: 0 failed
check_pytest_baseline: PASS
alembic heads: 202610220068 (head)
```

- [ ] **Step 2: 迁移升降级验证**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12/apps/api
TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/data_scrapy_workflow_plan_phase2_test' \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest -q tests/postgres/test_deletion_dsr_migration.py
```

Expected: `4 passed`。确认 068 降级后 `legal_holds` 仍在，且触发器函数恢复到 067 定义。

- [ ] **Step 3: 边界检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
PLAN='docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md'
rg -n 'require_[r]ecent_mfa' "$PLAN" apps/api/src apps/api/tests
rg -n 'apps/[w]eb|apps/[s]craper-console' "$PLAN" apps/api
rg -n 'services[.]report_shares|from .*report_shares' apps/api/src apps/api/tests
rg -n 'legal[-]hold' apps/api/src/data_intelligence_hub/maintenance/privacy_ops.py
```

Expected: 四条命令都无输出，退出码 1。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
rg -n '"workbench_tasks"|"data_gaps"|"market_assessments"|"runs"|"run_steps"|"task_runs"|"collection_tasks"|"sources"|"claims"|"claim_evidence"|"evidences"|"report_artifacts"|"report_audit_events"' \
  apps/api/src/data_intelligence_hub/services/deletion_executor.py
```

Expected: 至少 13 行命中，覆盖 workbench_tasks、data_gaps、market_assessments、runs、run_steps、task_runs、collection_tasks、sources、claims、claim_evidence、evidences、report_artifacts、report_audit_events。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
rg -n 'dataset_export_files|delivery_files|"preserved"' \
  apps/api/src/data_intelligence_hub/services/deletion_executor.py \
  apps/api/src/data_intelligence_hub/services/deletion_proof.py
```

Expected: 至少 8 行命中，包含 dataset_export_files、delivery_files 与 preserved。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
rg -n 'delete\(session, Claim|delete\(session, Evidence|delete\(session, ReportArtifact|delete\(session, DataGap|DatasetExportJob|scrub\(' \
  apps/api/src/data_intelligence_hub/services/deletion_executor.py
```

Expected: 至少 10 行命中，包含 delete 与 scrub 两类处理。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
rg -n 'dih_deletion_executor' \
  apps/api/alembic/versions/202610220068_privacy_deletion_dsr.py \
  apps/api/src/data_intelligence_hub/services/deletion_executor.py
```

Expected: 至少 3 行命中，包含 068 的两个触发器函数和执行器的 `SET LOCAL ROLE`。

- [ ] **Step 4: UTF-8 与 NUL 检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
test -f docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md && echo "plan_present"
python3 - <<'PY'
from pathlib import Path

path = Path("docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md")
data = path.read_bytes()
assert b"\x00" not in data, "NUL byte found"
assert data.endswith(b"\n"), "file must end with newline"
data.decode("utf-8")
print("utf8_ok", len(data))
PY
```

Expected: `plan_present`，随后 `utf8_ok <字节数>`。

- [ ] **Step 5: GitNexus 变更检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs detect-changes --scope compare --base-ref feat/gov-c11 --repo .
```

Expected: `partial: false` 且 `truncated: false`。出现 `partial: true` 时重新分析并重跑。

- [ ] **Step 6: 浏览器交接单交 C14**

C14 独占控制台与 Playwright。C12 不创建、不修改前端文件。C14 的基础设施权限是只读：只做 health、canary、preflight 与浏览器验收；浏览器验收只在专用合成工作区写应用数据，不执行 SQL、备份、迁移、compose/env、重启或开关切换。交接内容固定为：

| 项目 | 内容 |
|---|---|
| 设置面板 | 删除请求列表、DSR 列表、法律保留只读列表。 |
| 写操作 | 发起、批准、确认、重发确认、取消、重试、重新评估、执行。 |
| 角色 | owner/admin 发起；owner 批准、确认、执行；member 403。 |
| 二次确认 | 返回 `confirmation_phrase`，文本必须等于 `DELETE <目标名>`。 |
| 证明 | `GET /api/privacy/deletion-requests/{request_id}/proof` 返回 `proof_number` 与 `proof_digest`。未生成时返回 409 `deletion_proof_not_ready`。 |
| 法律保留 | 只读。不得提供写入按钮。写入使用 C11 的运维命令行。 |
| 错误码 | `deletion_request_not_found`、`legal_hold_active`、`deletion_state_conflict`、`deletion_proof_not_ready`、`dsr_case_not_found`。 |
| 不展示 | 明文密钥、Cookie、provider、内部单价、分享链接。 |

C14 的验收必须包含：owner 发起、二次确认文本错误返回冲突、正确确认、执行后显示 `DP-` 证明、法律保留 active 时执行被阻断。

- [ ] **Step 7: 生产 A/B 发布交接单交 PG0 发布批次；C14 只读验收

C12 不部署：不执行 SSH、备份、迁移、种子、生产 compose/env 值变更、重启或开关切换。仓库内的两行静态映射由 C12 提交。PG0 发布批次按总索引 §8.4 执行：

| 阶段 | 责任 | 条件 |
|---|---|---|
| 生产 A 备份与迁移 | PG0 发布批次 | C11 的 067 已应用；先备份，再应用 068；健康检查 200。 |
| 生产 A 开关与 env 值 | PG0 发布批次 | C12 已提交 compose 静态映射；PG0 只在 `.env.production` 设置 `PRIVACY_AUDIT_CLEANER_DATABASE_URL` 专用 DSN 与 `PRIVACY_DELETION_ENABLED=false`，合成项目删除验收通过后改设 `PRIVACY_DELETION_ENABLED=true`。C14 只读。 |
| 生产 B | PG0 发布批次 | `202610190045` 的目标授权与备份门禁未通过时保持 `BLOCKED`。B 不应用 068，不打开开关。 |
| 浏览器验收 | C14 | 只读 health 与 `/settings` 浏览器验收；可在一个专用合成工作区执行 owner 发起、批准、确认、执行流程；不得删除真实客户项目。 |
| C14 禁止 | C14 | 不执行 SQL、备份、迁移、种子、compose/env、重启或开关切换。 |

不得删除任何真实客户项目。合成验收只使用专用工作区。

- [ ] **Step 8: 更新计划状态并提交**

把本计划状态改为“已完成”，记录测试数字、迁移 head 与 GitNexus 结论。

```bash
cd /Users/lute/Project/data_scrapy-gov-c12
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md
git ls-files --error-unmatch docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md >/dev/null && echo "plan_tracked"
git commit -m "docs(plan): 完成 C12 删除与 DSR 交接"
git status --short
```

Expected: detect-changes 的 `partial` 与 `truncated` 均为 `false`；`plan_tracked`；提交后 `git status --short` 不含本计划文件。

---

## Self-Review

**Spec coverage**

- C1 独占契约：Global Constraints、Task 1 Step 1–2、每次提交的契约差异检查。
- 隔离 worktree 与本计划复制：Task 0、Task 9 Step 4 与 Step 8。
- 依赖 C3/C4/C8/C10/C11：Task 0 依赖门禁、Task 1 迁移、Task 5 执行器、Task 7 只读法律保留。
- 分享延期与 no-op 审计：Global Constraints、Task 5 `deletion_share_revocation_deferred`、证明 `report_shares: 0`。该事件使用既有 `privacy_audit_events.event_type` 字符串，不是新契约枚举。
- 移除额外认证依赖：Global Constraints、Task 7 路由无全局依赖测试、Task 9 边界检查。
- 法律保留写入归 C11：Global Constraints、Task 3 只读 `active_hold_count`、Task 8 运行手册、Task 9 边界检查。
- 删除前端实现任务：File Structure 的“禁止创建”、Task 9 浏览器交接单。
- `privacy_ops` 只创建一次且只含 DSR、证明、重放：Task 8。
- 删除范围含 workbench_tasks、data_gaps、market_assessments、runs、run_steps、task_runs、collection_tasks、sources、claims、claim_evidence、evidences、report_artifacts、report_audit_events、交付文件、dataset export 文件：Task 5 删除范围表与执行器。
- 运行/账本/审计保留时的脱敏与 tombstone：Task 5 的 `scrub` 与 `preserve` 处理、Global Constraints 的删除范围条目。
- 证明写计数：Task 5 `tombstones`、`revocations`、`file_deletions`、`preserved`。
- 审计只追加与 24 个月清理：Task 1 触发器、Task 8 `privacy_audit_retention`、运行手册。
- 每 commit 前 detect-changes：Global Constraints 与每个 Task 的提交步骤。
- 一个迁移 068 接 067：Global Constraints、Task 1。
- A/B 发布交 PG0 发布批次，B 保持 BLOCKED，C14 只做只读验收：Global Constraints、Task 9 Step 7。

**边界扫描**

- 计划中没有契约升级任务。
- 计划中没有法律保留写入服务或命令行。
- 计划中没有分享服务导入、分享端口或分享表。
- 计划中没有前端实现任务。
- 计划中没有额外认证导入、依赖、错误码或文案。

**类型一致性**

- `DeletionRequestStatus` 九值在模型、迁移、状态机、路由和 C14 交接单中一致。
- `DeletionTargetType` 两值在 C1 registry、模型、状态机、执行器中一致。
- `FileDeletionResult` 在证明、执行器、重放中同名。
- 证明字段 `preserved` 在 `build_proof_payload`、`issue_deletion_proof`、`DeletionExecutionResult` 与执行器测试中同名。
- `active_hold_count` 在状态机、执行器、重新评估中同名。
- `/api/privacy/*` 路径在 C1 registry、路由、运行手册、C14 交接单中一致。
- 证明字段 `proof_number`、`proof_digest`、`audit_head_digest` 在模型、服务、schema、C14 交接单中一致。
- 公开错误码只有 C1 登记的五个：`deletion_request_not_found`、`legal_hold_active`、`deletion_state_conflict`、`deletion_proof_not_ready`、`dsr_case_not_found`。状态机的细分内部错误在路由边界映射到这些码。

**风险**

- C11 的 067 必须先合入。缺 067 时 068 无法创建外键和读取法律保留。
- C10 的 `DeliveryStore` 必须先合入。缺它时执行器无法删除交付文件。
- SQLite 不执行 PostgreSQL 触发器。只追加测试必须在 PostgreSQL 迁移测试中运行。
- 生产 B 的门禁不由 C12 解除。PG0 发布批次必须先取得目标授权和备份计划；C14 只读验收。
