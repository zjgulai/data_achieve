# 受治理任务平台 C2：身份、项目 ACL 与统一审计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把工作区角色收敛为 `owner`、`admin`、`member`，用 `project_members` 实现项目级 ACL，并把身份与 ACL 变更写入带 SHA-256 哈希链的追加式 `audit_events`；同时提供稳定的错误信封与一个可回退的功能开关。

**Architecture:** `workspace_members.role` 是唯一授权事实源。`workspaces.owner_id` 只保留“创建者/账单联系人”语义，并由迁移与不变量保证其成员行永远是 `owner`。授权判断集中在 `api/authz.py` 一个接缝：owner/admin 可见工作区全部项目，member 只可见 `project_members` 登记的项目；跨工作区返回 404，同工作区无项目权限返回 403。所有身份与 ACL 写操作在同一事务内追加 `audit_events` 行，哈希链按工作区串行追加，失败时整体回滚。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、PostgreSQL 15（生产）、SQLite（单元测试）、pytest、ruff、mypy、Next.js 16 控制台、Playwright、GitNexus CLI。

## Global Constraints

- 客户角色只有三个值：`owner`、`admin`、`member`。不得新增 `viewer`、`billing`、`reviewer` 等客户角色。
- 内部审阅者不是客户角色。唯一事实源是 C1 已登记的 `report_reviewer_assignments` 表（C9 迁移创建）；`workspace_members.role` 不得出现 `reviewer`。C2 只读该表并提供授权查找与审计，不创建该表、不写该表、不新增审阅者客户路径。
- `workspace_members.role` 是唯一授权事实源。所有授权读取必须走 `api/authz.py` 或 `repositories/workspaces.py:get_workspace_role()`。
- `workspaces.owner_id` 不是授权事实源。它表示创建者/账单联系人。迁移 058 必须为该用户补齐 `role='owner'` 的成员行；C2 禁止把该用户降级或移除。
- 每个工作区必须至少有一名 `role='owner'` 的成员。最后一个 owner 不能被降级或移除。该检查必须在工作区行锁内执行。
- `project_members` 只表达“该用户可查看该项目”，不新增项目级角色列。owner/admin 不需要 `project_members` 行即可访问全部项目。
- 跨工作区项目访问一律返回 404 `project_not_found`。同工作区但无项目权限返回 403 `project_access_forbidden`。项目成员尝试管理项目或项目成员返回 403 `project_management_forbidden`。
- 功能开关：`WORKSPACE_RBAC_ENFORCED`，默认 `false`。关闭时项目可见性退回旧行为（工作区成员可见全部项目）；打开后执行 member 项目过滤与 403 规则。owner/admin 的管理权限始终生效，不受开关影响。审计写入没有关闭开关，不得静默跳过。该开关只影响 `workspace_members.role` 的项目可见性，不影响内部审阅者接缝：审阅者过期、范围与撤销检查始终生效。
- 审计表 `audit_events` 只追加。C2 迁移 058 创建拒绝 `UPDATE` 与 `DELETE` 的触发器。C11 迁移 067 会替换同一触发器函数，只允许专用角色 `dih_retention_cleaner` 删除超过 730 天的行；C2 不实现该角色允许逻辑，也不依赖它。哈希链使用 SHA-256，`prev_hash` 指向上一条同工作区事件的 `event_hash`，首条为 64 个 `0`。
- 错误信封是附加字段，不替换既有 `detail`。所有 HTTP 错误响应同时包含 `detail` 和 `error`；既有控制台与测试读取 `detail` 的行为保持不变。
- 错误信封字段固定为 `error.code`、`error.message`、`error.request_id`、`error.details`。请求 ID 来自 `X-Request-ID`，缺失时生成 32 位小写十六进制。
- 不实现 MFA、TOTP、WebAuthn、SSO、SCIM。不创建 `user_sessions` 表。C2 不建 `audit_chain_anchors`、`deletion_requests`、`dsr_requests` 或 `workspace_pseudonym_salts`。`report_reviewer_assignments` 由 C9 迁移 065 创建，C2 只读；C2 不得在 058 中创建或修改该表。
- 只允许一个迁移：`202610220060_identity_acl_audit.py`，`down_revision = "202610220059"`。开工前 `alembic heads` 必须只有一行 `202610220059`（B5 的 claims 与 report_artifacts 已分别落到 058/059）；C2 落地后 head 变为 `202610220060`。
- 事务提交权在 service，repository 只 `flush`。见 ADR-007 D4。审计行与业务写操作在同一个 service 事务内提交。
- 不修改既有 `run_ledger_entries` 八列与六种 `entry_kind`。不修改 `settle` 正数、`release` 负数规则。
- 不新增契约外的表、列、枚举值或路径。C2 只实现 C1 已登记的对象；Task 1 是只读守卫，不修改契约。发现缺失时停止，先把缺口交回 C1。C2 不建新表：本计划只允许 Task 2 的 `project_members` 与 `audit_events`；Task 7 的链头导出只读既有表，不新增表；内部审阅者接缝只读 C9 的 `report_reviewer_assignments`，不建表、不加列。
- 统一审计动作必须来自 `services/audit_log.AUDIT_ACTIONS`。C1 必须在契约文档登记“审计动作注册表”。C2 的 `append_audit_event` 拒绝未登记动作（`audit_action_unregistered`）；下游切片不得自造动作名。动作名只允许小写字母、数字、下划线与点，最长 80 字符。
- C4-C12 的每个项目级路由与服务必须调用 `api/authz.require_project_access`（或带审计包装 `require_project_access_audited`）。C2 不在本计划修改它们的文件；C2 只交付消费者契约、交接文档与逐切片 403/404 测试判据。项目级写操作必须 `manage=True`，读操作 `manage=False`。
- 改既有符号前必须运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。空调用集是 `UNKNOWN`，必须再用文本搜索确认。
- 提交前必须运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不算通过，必须重跑。
- C0 已完成：`pg0-baseline-v1` 标签存在，B5 已合入，Alembic head 是 `202610220059`。C1 已完成：`feat/gov-c1` 分支存在，`configs/contracts/v1.1.0/registry.json` 可生成且 checker 通过。C2 从 `feat/gov-c1` 创建独立 worktree：`git worktree add /Users/lute/Project/data_scrapy-gov-c2 -b feat/gov-c2 feat/gov-c1`。主工作树 `/Users/lute/Project/data_scrapy` 只用于 Task 1 Step 0 的 worktree 创建、只读预检与复制本计划；Step 0 之后所有 Run/Commit 命令都在 `/Users/lute/Project/data_scrapy-gov-c2` 执行。不得从 `f0560ca`、`main` 或 `pg0-baseline-v1` 直接开工。
- C1 前置登记（并行修复中的 C1 计划必须先包含，否则 C2 停止并交回缺口）：`report_reviewer_assignments.expires_at`（`datetime`，非空）、`report_reviewer_assignments.assignment_scope` 值 `report_read` / `report_review`、错误码 `reviewer_assignment_expired`（403）、错误码 `reviewer_assignment_required`（403）、错误码 `reviewer_assignment_invalid`（422）、路径 `POST /api/reports/{report_id}/reviewers` 与 `DELETE /api/reports/{report_id}/reviewers/{user_id}`、以及“审计动作注册表”小节列出 `AUDIT_ACTIONS` 全部动作名。已登记的名称不得改名。C2 不修改 C1 契约；缺失时 Task 1 输出 `C2_CONTRACT_GAP` 并停止。
- 开工断言：`git rev-parse --verify feat/gov-c1^{commit}` 成功；`git merge-base --is-ancestor feat/gov-c1 HEAD` 退出码 0；`uv run alembic heads` 只有 `202610220059 (head)`；`configs/contracts/v1.1.0/registry.json` 存在；registry 中 `report_reviewer_assignments` 的列含 `expires_at`；契约文档含 `reviewer_assignment_expired` 与“审计动作注册表”。任一不成立就停止，先完成 C0 与 C1。
- 契约所有权：`docs/design/【契约冻结】v1-表名-枚举-接口.md` 与 `configs/contracts/v1.1.0/*` 只读。C1 已登记 `project_members`、`audit_events`、`workspace_members.role`、C2 路径、错误信封与错误码，并登记内部审阅者表 `report_reviewer_assignments`、审阅者路径、`reviewer_assignment_required` / `reviewer_assignment_invalid` / `reviewer_assignment_expired` 与审计动作注册表。C2 不得修改契约或 registry；守卫测试只读校验，失败时停止并交回 C1。
- 控制台所有权：`apps/scraper-console/src/**` 与 `apps/scraper-console/e2e/**` 归 C14。C2 只提供浏览器交接清单，不改页面、不改测试、不改路由表。C2 的 API 与测试必须能独立通过。
- 所有提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不算通过。
- 回滚点：关闭 `WORKSPACE_RBAC_ENFORCED` 恢复旧项目可见性；迁移 058 只在一次性空库执行 `downgrade -1`，有审计行时降级必须拒绝；不得删除审计行。
- 共享 compose：C2 只修改 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment`，增加 `WORKSPACE_RBAC_ENFORCED`（默认 `false`）、`AUDIT_CHAIN_HEAD_DIR`（默认 `var/audit-chain-heads`）与 `AUDIT_CHAIN_HEAD_HMAC_KEY`（默认空）三个映射，并新增 compose 事实测试。C2 不写 `.env.production`，不改 edge、网络、volume 或端口。
- 发布门禁：本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；先备份，A 先 canary，B 只在目标授权、备份与迁移门禁通过后发布；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。任一步失败记 `BLOCKED`。
- 文档正文用中文；表名、列名、枚举值、错误码、函数名用英文 `snake_case`。
- 每个步骤给出实际命令、实际代码或实际断言。不得使用占位符或跨任务引用代替内容。

## 身份事实源

本计划固定以下关系，后续任务不得偏离：

| 事实 | 来源 | 用途 |
|---|---|---|
| 工作区角色 | `workspace_members.role` | 唯一授权来源。取值 `owner` / `admin` / `member`。 |
| 工作区创建者 | `workspaces.owner_id` | 创建者与账单联系人。迁移 058 为其补齐 owner 成员行。 |
| 项目成员 | `project_members` 行 | 只给 `member` 增加项目可见性。owner/admin 不依赖它。 |
| 内部审阅者 | `report_reviewer_assignments` 行（C1 登记、C9 迁移创建） | 只读报告包（报告、Claim、Evidence）；`assignment_scope` 为 `report_read` 或 `report_review`；必须有 `expires_at`。不是 `workspace_members.role` 值。 |
| 项目所属工作区 | `projects.workspace_id` | 跨工作区隔离；查询必须带 `workspace_id`。 |
| 审计链 | `audit_events` 按 `workspace_id` 的 `sequence_number` 与 `prev_hash` | 追加式取证；不参与授权。 |

`workspaces.owner_id` 用户在 C2 中不能被降级或移除，因此旧的 `workspace.owner_id == user.id` 检查与新的 `role == "owner"` 检查在 C2 范围内等价。C3 迁移全部旧检查后才可以放开这条不变量。

## 工作包边界

本计划只实现以下内容：

```text
workspace_members.role 三值化与最后 owner 保护
project_members 表与项目 ACL 接缝
内部审阅者只读授权查找与审计（复用 C1 登记的 report_reviewer_assignments，不建表）
audit_events 表、追加服务、哈希链、查询与校验接口
统一审计动作注册表与 append_audit_event 严格校验
每日审计链头导出：本地 JSON、SHA-256、HMAC-SHA256
统一错误信封与 X-Request-ID
WORKSPACE_RBAC_ENFORCED 功能开关
登录、失败登录与登出审计
C4-C12 项目 ACL 与审计动作消费者契约（只交付文档与判据，不改它们的文件）
C14 设置页内联成员面板所需 API 与交接判据（C2 不改控制台，不新增 /settings/members 路由）
```

本计划为审计服务建立接缝，并覆盖工作区成员、项目、项目成员、登录会话、内部审阅者访问与 ACL 拒绝事件。项目密钥生命周期、任务单、预算、运行、Claim 审核、报告、交付、保留与删除事件的审计由各自工作包调用同一 `append_audit_event` 与同一 `AUDIT_ACTIONS` 注册表，不在 C2 重复实现。

本计划不实现：

```text
MFA / TOTP / WebAuthn / SSO / SCIM
user_sessions 表
审计链锚的独立防篡改存储
审计链头的 WORM/对象锁上传与外部持久化（O0 取证任务负责）
审计保留 24 个月清理 job
删除证明、DSR、伪名盐
预算审批、密钥轮换、客户 MCP 八工具
project_members 之外的项目级数据表行级隔离
report_reviewer_assignments 建表、审阅者分派/撤销路由与审阅签字（C9 所有）
```

## 路由接缝采用边界与 C4-C12 消费者契约

C2 的 `require_project_access` 是唯一项目授权接缝。C2 自己接入以下路由：

| 路由 | 规则 |
|---|---|
| `GET /api/projects` | owner/admin 全部；member 仅 `project_members` 项目（开关打开时） |
| `GET/PATCH/DELETE /api/projects/{project_id}` | 跨工作区 404；同工作区无权限 403；member 不能管理 |
| `GET/POST/DELETE /api/projects/{project_id}/members` | owner/admin 管理；member 403 `project_management_forbidden` |
| `POST/GET/DELETE /api/projects/{project_id}/api-keys*` | C3 负责；C2 不改该路由，C3 调用 C2 的 `require_workspace_role` |
| `POST /api/projects/{project_id}/workflow-plans/preview` | 使用 `require_project_access`；archived 仍返回 409 |

### 唯一消费者契约

任何 C4-C12 的项目级路由或项目级 service 入口只允许按以下契约调用：

```python
from data_intelligence_hub.api.authz import (
    ProjectAccess,
    require_project_access,
    require_project_access_audited,
)

# 路由层：有 request_id 时用带审计包装；拒绝会写 project.access.denied
# 或 project.management.denied，并随异常回滚业务写。
access: ProjectAccess = await require_project_access_audited(
    session,
    context=context,
    project_id=resolved_project_id,
    manage=<bool>,
    request_id=request_id,
)

# service 层：只接收已授权的 access.project，不重复解析角色。
await some_service(session, project=access.project, actor_user_id=context.user.id, ...)
```

固定规则：

1. `project_id` 必须来自路径参数、查询参数，或按 `workspace_id` 先加载的资源行（`claim.project_id`、`report.project_id`、`run.project_id`、`artifact.project_id`、`dataset.project_id`、`task.project_id`）。不得只信任请求体里的 `project_id`。
2. 项目级读操作 `manage=False`；创建、更新、取消、重试、审核、发布、导出、删除等项目级写操作 `manage=True`。
3. `owner` / `admin` 通过；`member` 只有 `project_members` 行时通过读；`member` 的写操作一律 403 `project_management_forbidden`。
4. 跨工作区项目一律 404 `project_not_found`；同工作区未授权读 403 `project_access_forbidden`；同工作区未授权写 403 `project_management_forbidden`。
5. 路由不得直接比较 `workspace.owner_id`、`workspace_members.role` 或 `context.user.id` 来判定项目权限。角色判定只允许出现在 `api/authz.py` 与 `repositories/workspaces.get_workspace_role()`。
6. `WORKSPACE_RBAC_ENFORCED=false` 只回退 member 的项目可见性；owner/admin 管理权限与审计写入不回退。下游测试必须覆盖开关打开与关闭两种状态，并在用例结束后恢复原值。
7. 无会话的公开路径（C10 的公开分享已延期）不得调用本接缝；有会话的交付下载仍须调用本接缝。工作区级路径（`/api/workspaces/*`、`/api/audit-events`、`/api/privacy/*` 的工作区目标）不传项目 ID，继续用 `require_workspace_role`。
8. service 层不得导入 `api.authz`。授权在路由层完成，service 只接收 `Project` 对象或已校验的 `project_id`。
9. 下游切片不得复制 `ProjectAccess`、`Project` 查询或 403/404 逻辑；统一从 `api.authz` 导入。

### C4-C12 逐切片接入表

C2 不修改下表任何文件。每个切片在自己的计划与测试中完成接入。

| 切片 | 必须接入的项目级路由/服务 | `project_id` 来源 | `manage` | 必测判据 |
|---|---|---|---|---|
| C3 | `POST/GET/DELETE /api/projects/{project_id}/api-keys*` | 路径 | 写 `True`，读 `False` | 跨工作区 404；member 写 403；owner/admin 通过 |
| C4 | `POST/GET /api/workbench/tasks`；`GET/PATCH /api/workbench/tasks/{task_id}`；`GET /api/workbench/tasks/{task_id}/gates`；`POST /api/runs` | 查询 `project_id`；任务行 `task.project_id`；提交载荷 `project_id` | 创建/更新 `True`；读 `False` | member 已授权项目 A 读 200；同工作区未授权项目 B 读 403；跨工作区项目 404；member 对 B 建任务写 403；拒绝后存在 `project.access.denied` 或 `project.management.denied` 审计行 |
| C5 | `GET /api/quota/projects/{project_id}`；`services/budget_service` 的 `reserve` / `settle` / `release` / `block` / `cancel` 项目级路径 | 路径；`run.project_id` | 读 `False`；预算写 `True` | 同 C4 四项；另测 `GET /api/quota/projects/{B}` 403 与跨工作区 404；预算写只在授权项目上落账 |
| C6 | `POST /api/runs/{run_id}/cancel`；取消/重试执行器入口；`run.completed` 之外的运行状态写 | `run.project_id` | `True` | 同 C4 四项；另测 member 取消未授权 run 403、跨工作区 run 404、取消成功后审计动作 `run.cancelled` 或 `task.retried` |
| C7 | `GET /api/claims?project_id=...`；`GET /api/claims/{claim_id}`；Claim 审核写路由 | 查询；`claim.project_id` | 读 `False`；审核 `True` | 同 C4 四项；另测 claim 详情跨工作区 404、未授权项目 403、member 审核 403 |
| C8 | `POST /api/automation/product-dataset-save`；`services.dataset_quality.evaluate_and_persist_market_quality` / `upsert_market_assessment` 的调用入口 | 载荷 `project_id`；`run.project_id` | 保存 `True`；质量读 `False` | 同 C4 四项；service 级用例必须先经路由接缝，禁止绕过 |
| C9 | `GET /api/reports/{report_id}/contract`、`artifact`、`revisions`、`sop`；`POST /api/reports/{report_id}/reviews`；`POST /api/reports/{report_id}/publish` | `report.project_id` | 读 `False`；审核/发布 `True` | 同 C4 四项；另测跨工作区报告 404、未授权项目报告 403、member 审核/发布 403；内部审阅者走独立接缝，不获得 owner/admin 写权限 |
| C10 | `POST /api/reports/{artifact_id}/delivery/publish`；`GET /api/reports/{artifact_id}/delivery`；`GET /api/reports/{artifact_id}/delivery/manifest`；下载 | `artifact.project_id` | 发布 `True`；读/下载 `False` | 同 C4 四项；公开分享延期，不得以公开令牌绕过接缝；下载拒绝写 `project.access.denied` |
| C11 | `POST/GET /api/automation/product-dataset-exports*`；数据集版本读取；`services.governed_dataset_export` 入口 | 载荷/行 `dataset.project_id` | 创建 `True`；读/导出 `False` | 同 C4 四项；遮蔽与伪名化在授权后执行；拒绝不得落导出文件 |
| C12 | `POST /api/privacy/deletion-requests` 的 `target_type='project'`；项目删除执行；法律保留项目匹配 | 载荷 `project_id`；`request.target_id` | `True` | 同 C4 四项；`target_type='workspace'` 只用 `require_workspace_role`，不调用项目接缝；跨工作区项目删除 404 |

C13 客户 MCP 不在本表；它通过项目密钥访问，必须复用 C3 的项目密钥与 C2 的接缝。

### 每个下游切片必须实现的 403/404 测试

下游切片必须复制以下用例骨架，替换为自己的路由与服务。C2 不代写、不代跑。

```python
import pytest
from sqlalchemy import select

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.audit_event import AuditEvent


@pytest.mark.asyncio
async def test_project_acl_consumer_contract(client, seeded, session) -> None:
    settings = get_settings()
    original = settings.workspace_rbac_enforced
    settings.workspace_rbac_enforced = True
    try:
        # owner/admin 全项目可读；member 只读 project_a。
        assert (await client.get(seeded.owner_client, seeded.url_a)).status_code == 200
        assert (await client.get(seeded.admin_client, seeded.url_a)).status_code == 200
        assert (await client.get(seeded.member_client, seeded.url_a)).status_code == 200

        denied = await client.get(seeded.member_client, seeded.url_b)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "project_access_forbidden"

        missing = await client.get(seeded.member_client, seeded.other_workspace_url)
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "project_not_found"

        write_denied = await client.write(seeded.member_client, seeded.write_url_b)
        assert write_denied.status_code == 403
        assert write_denied.json()["error"]["code"] == "project_management_forbidden"
    finally:
        settings.workspace_rbac_enforced = original

    rows = (
        await session.execute(
            select(AuditEvent).where(
                AuditEvent.workspace_id == seeded.workspace_id,
                AuditEvent.action.in_(
                    ("project.access.denied", "project.management.denied")
                ),
            )
        )
    ).scalars().all()
    assert rows, "denied project access must append audit evidence"
```

固定断言：

- 同工作区、未授权项目：读 403 `project_access_forbidden`；写 403 `project_management_forbidden`。
- 跨工作区项目：404 `project_not_found`，不得返回 403。
- owner 与 admin：同一项目读 200、写 200。
- member 已授权项目 A：读 200；写仍 403。
- 开关关闭：member 可读项目 B（旧行为）；owner/admin 写规则不变。
- 拒绝后新 session 能读到 `result='denied'` 的审计行，`resource_type='project'`，`request_id` 非空。

### 不允许的写法

```python
# 禁止：路由内直接比较 owner_id
if context.workspace.owner_id != context.user.id:
    raise HTTPException(403, "forbidden")

# 禁止：只按工作区过滤就宣称项目 ACL 完成
select(Claim).where(Claim.workspace_id == workspace.id)

# 禁止：service 内自行判定角色
if membership.role == "admin":
    ...
```

工作区级隔离仍然必要，但不能替代项目级接缝。C2 只在本计划接入上表 C2 行；其余行由 C4-C12 在各自提交中完成。

## 内部审阅者接缝（C1 登记，C2 只读实现）

内部审阅者与 `owner` / `admin` / `member` 完全分离。事实源是 C1 登记的 `report_reviewer_assignments`（C9 迁移 065 建表）：

| 字段 | 规则 |
|---|---|
| `workspace_id` / `project_id` / `report_id` | 指派范围。跨工作区或报告不存在一律 404，不泄漏存在性；指派行与报告的项目不一致按数据不合法返回 422 `reviewer_assignment_invalid`。 |
| `reviewer_user_id` | 审阅者本人。审阅者不必是工作区成员，也不获得工作区角色。 |
| `assignment_scope` | `report_read` 或 `report_review`。C2 的只读接缝接受两者，但只返回读权限；写权限由 C9 的 `report_review` 检查。 |
| `status` | `active` 或 `revoked`。撤销行保留，不删除。 |
| `expires_at` | C1 必须新增的非空列；到期后拒绝，即使 `status='active'`。 |
| `assigned_by` / `assigned_at` / `revoked_at` | C9 分派与撤销事实；C2 只读。 |

C2 只实现以下只读接缝，不实现分派/撤销路由、不写 `report_reviewer_assignments`、不新增客户角色：

```python
ReviewerResourceKind = Literal["report", "claim", "evidence"]

@dataclass(frozen=True)
class ReviewerReadAccess:
    assignment_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    reviewer_user_id: uuid.UUID
    assignment_scope: str
    expires_at: datetime
    resource_kind: ReviewerResourceKind


async def require_internal_reviewer_read(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
    resource_kind: ReviewerResourceKind,
    now: datetime | None = None,
) -> ReviewerReadAccess:
    ...
```

判定顺序固定：

1. `get_report(session, workspace.id, report_id)` 为空 → 404 `report_artifact_not_found`（跨工作区与不存在同码）。
2. 查 `report_reviewer_assignments`：`workspace_id`、`report_id`、`reviewer_user_id=user.id`、`status='active'`。无行 → 403 `reviewer_assignment_required`。
3. `project_id` 为空，或与 `report.project_id` 不一致，或 `assignment_scope` 不在 `("report_read", "report_review")` → 422 `reviewer_assignment_invalid`。
4. `expires_at <= now()`（UTC）→ 403 `reviewer_assignment_expired`，`details={"assignment_id": "..."}`。
5. 通过：返回 `ReviewerReadAccess`。`resource_kind` 只允许 `report`、`claim`、`evidence`。Claim/Evidence 的调用方必须先按 `claim_evidence` / `evidences` 的归属解析出 `report_id`，再调用本接缝；解析不到时 404。不得接受客户端直接提交的 `report_id` + `claim_id` 组合，也不得跨报告读取。

审计接缝：

- 审阅者访问审计的 `actor_type` 仍是 `user`；审阅者身份由 `details.assignment_id` 与 `details.scope` 表达，不新增 `audit_events.actor_type` 枚举值。
- `require_internal_reviewer_read_audited(session, *, context, report_id, resource_kind, request_id)` 在拒绝时写 `reviewer.access.denied`（`result='denied'`，`resource_type='report'`，`details` 含 `scope` 与 `code`），在通过时写 `reviewer.access.granted`（`result='success'`，`resource_type` 等于 `resource_kind`，`details` 含 `assignment_id` 与 `scope`）。
- 通过事件必须在读取敏感内容之前提交；拒绝事件必须在抛出前提交。审计失败时异常传播，读取不发生。
- 审计只写 `audit_events`，不改 `report_reviewer_assignments`；审阅者到期或撤销不产生 `audit_events` 更新。
- C9 的分派与撤销路由由 C9 写 `reviewer.assignment.created` / `reviewer.assignment.revoked`；C2 只在注册表中登记这两个动作，不实现 C9 路由。

C1 必须新增的登记（缺失时 Task 1 停止并输出 `C2_CONTRACT_GAP`）：

- `report_reviewer_assignments.expires_at`，类型 `datetime`，非空。
- 错误码 `reviewer_assignment_expired`，HTTP 403。
- “审计动作注册表”列出 `reviewer.access.granted`、`reviewer.access.denied`、`reviewer.assignment.created`、`reviewer.assignment.revoked`。

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `apps/api/tests/unit/test_contract_freeze_c2.py` | Create | 只读契约守卫：C2 对象必须已出现在 C1 契约与 registry。 |
| `apps/api/alembic/versions/202610220060_identity_acl_audit.py` | Create | 唯一迁移：建表、回填 owner 成员、角色约束、审计只追加触发器。 |
| `apps/api/src/data_intelligence_hub/models/project_member.py` | Create | `ProjectMember` 模型。 |
| `apps/api/src/data_intelligence_hub/models/audit_event.py` | Create | `AuditEvent` 模型与常量。 |
| `apps/api/src/data_intelligence_hub/models/workspace.py` | Modify | `WorkspaceMember.role` 约束与注释。 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | Modify | 注册两个新模型。 |
| `apps/api/tests/unit/test_c2_migration_source.py` | Create | 迁移单 head、建表列、触发器、模型约束、无 `user_sessions`。 |
| `apps/api/src/data_intelligence_hub/core/errors.py` | Create | `APIError`、错误信封处理器、请求 ID 中间件。 |
| `apps/api/tests/unit/test_error_envelope.py` | Create | 403/404/422/500 信封与请求 ID 回显。 |
| `apps/api/src/data_intelligence_hub/main.py` | Modify | 安装错误契约；删除局部 422 handler。 |
| `apps/api/src/data_intelligence_hub/core/config.py` | Modify | `workspace_rbac_enforced`、`audit_chain_head_dir`、`audit_chain_head_hmac_key`。 |
| `apps/api/.env.example` | Modify | 增加 `WORKSPACE_RBAC_ENFORCED=false` 与链头导出键示例。 |
| `configs/deploy/scrapy/docker-compose.yml` | Modify | 生产 A/B 共用 compose；只在 `api.environment` 增加 `WORKSPACE_RBAC_ENFORCED`、`AUDIT_CHAIN_HEAD_DIR`、`AUDIT_CHAIN_HEAD_HMAC_KEY` 映射。默认关闭；不部署。 |
| `apps/api/tests/unit/test_deploy_c2_facts.py` | Create | 共享 compose 与 `.env.example` 的 C2 配置事实。 |
| `apps/api/src/data_intelligence_hub/repositories/workspaces.py` | Modify | `get_workspace_role`、`count_workspace_owners`、`lock_workspace`。 |
| `apps/api/src/data_intelligence_hub/services/workspace_service.py` | Modify | 邀请、改角色、移除成员、最后 owner 与 owner_id 不变量。 |
| `apps/api/src/data_intelligence_hub/services/exceptions.py` | Modify | 新增工作区成员异常；`InvalidCredentialsError` 携带可选审计上下文。 |
| `apps/api/src/data_intelligence_hub/schemas/workspace.py` | Modify | 角色 Literal、邀请与改角色请求。 |
| `apps/api/src/data_intelligence_hub/schemas/auth.py` | Modify | `AuthSessionResponse.role`。 |
| `apps/api/src/data_intelligence_hub/services/auth_service.py` | Modify | `AuthSession.role`，登录/注册/会话返回角色；失败登录携带工作区与用户审计上下文。 |
| `apps/api/src/data_intelligence_hub/api/routes/auth.py` | Modify | 所有会话响应带 `role`；登录成功、失败登录与登出写审计。 |
| `apps/api/src/data_intelligence_hub/api/routes/workspaces.py` | Modify | owner 校验、邀请、改角色、移除。 |
| `apps/api/tests/unit/test_workspace_roles.py` | Create | 角色解析、最后 owner、owner_id 不变量、会话角色。 |
| `apps/api/src/data_intelligence_hub/repositories/project_members.py` | Create | 项目成员查询与写入。 |
| `apps/api/src/data_intelligence_hub/repositories/projects.py` | Modify | 按成员过滤项目列表。 |
| `apps/api/src/data_intelligence_hub/api/authz.py` | Create | 工作区角色、项目访问与内部审阅者只读接缝。 |
| `apps/api/src/data_intelligence_hub/repositories/reviewer_assignments.py` | Create | 只读 C1 登记的 `report_reviewer_assignments`；查 active 指派与到期时间。 |
| `apps/api/src/data_intelligence_hub/services/project_service.py` | Modify | 列表按角色过滤；创建/更新/归档审计入口。 |
| `apps/api/src/data_intelligence_hub/schemas/project.py` | Modify | 项目成员响应与请求。 |
| `apps/api/src/data_intelligence_hub/api/routes/projects.py` | Modify | ACL 接缝、项目成员 CRUD。 |
| `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py` | Modify | 计划预览使用项目 ACL。 |
| `apps/api/tests/unit/test_project_acl.py` | Create | 跨工作区 404、同工作区无权限 403、成员授予/撤销、开关回退。 |
| `apps/api/tests/unit/test_internal_reviewer_access.py` | Create | 内部审阅者只读接缝：active、撤销、到期、范围、跨工作区 404、Claim/Evidence 解析、写权限不授予。 |
| `apps/api/src/data_intelligence_hub/repositories/audit_events.py` | Create | 审计行查询与 flush；支持 `before_sequence` / `after_sequence` 分页。 |
| `apps/api/src/data_intelligence_hub/services/audit_log.py` | Create | 哈希计算、链式追加、校验、拒绝审计、统一审计动作注册表与严格校验。 |
| `apps/api/src/data_intelligence_hub/schemas/audit.py` | Create | 审计事件响应与校验响应。 |
| `apps/api/src/data_intelligence_hub/api/routes/audit_events.py` | Create | 工作区审计列表与链校验。 |
| `apps/api/src/data_intelligence_hub/main.py` | Modify | 挂载 `/api/audit-events`。 |
| `apps/api/tests/unit/test_audit_log.py` | Create | 序列、prev_hash、篡改检测、成员只读本人。 |
| `apps/api/tests/unit/test_audit_action_registry.py` | Create | 必需动作覆盖、动作名格式、C1 契约登记、C2 源码只发已登记动作、未登记动作拒绝。 |
| `apps/api/src/data_intelligence_hub/services/audit_chain_head.py` | Create | 每日链头计算、JSON 文档、SHA-256 与 HMAC-SHA256、校验函数。 |
| `apps/api/src/data_intelligence_hub/maintenance/audit_chain_head_export.py` | Create | `python -m ...` 导出命令；只写本地文件，不上传外部存储。 |
| `apps/api/tests/unit/test_audit_chain_head.py` | Create | 链头结构、签名、篡改检测、失败不落盘。 |
| `apps/api/tests/unit/test_acl_audit_integration.py` | Create | 身份/ACL/登录/登出/失败登录/内部审阅者操作写审计，拒绝也写审计。 |
| `apps/api/src/data_intelligence_hub/api/deps.py` | Modify | `RequestIdDep`、请求 ID 依赖与可选认证上下文（登出审计）。 |
| `apps/api/tests/unit/test_task_runs_route.py` | Modify | 项目 ACL 接缝的既有路由回归。 |
| `apps/api/tests/integration/test_social_provider_routes.py` | Modify | 项目 ACL 接缝的集成回归。 |
| `docs/superpowers/plans/2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md` | Commit | 本计划文件，随 Task 1 提交。 |
| `docs/ops/c2-c14-members-handoff.md` | Create | C14 `/settings` 内联成员面板的交接判据、选择器与风险；不新增 `/settings/members` 路由。 |
| `docs/ops/c2-c12-downstream-handoff.md` | Create | C4-C12 项目 ACL 消费者契约、逐切片 403/404 测试模板、统一审计动作与 owner 交接。 |

**授权接缝方向：**

```text
route
  → api/authz.require_workspace_role()
  → api/authz.require_project_access()
      → repositories/workspaces.get_workspace_role()
      → repositories/project_members.get_project_member()
  → api/authz.require_internal_reviewer_read()   # 只读审阅者，独立于工作区角色
      → repositories/reports.get_report()
      → repositories/reviewer_assignments.get_active_assignment()
  → service 写业务 + services/audit_log.append_audit_event()
  → session.commit()
```

任何路由不得直接比较 `workspace.owner_id` 来决定 owner 权限。新代码不得在 route 内复制角色判定。内部审阅者接缝只返回读权限，不返回 `owner` / `admin` / `member` 角色。

---

### Task 1: 只读契约守卫与 C1 依赖门禁

**Files:**
- Create: `apps/api/tests/unit/test_contract_freeze_c2.py`
- Commit: `docs/superpowers/plans/2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md`

**Interfaces:**
- Consumes: C1 契约 v1.1、`configs/contracts/v1.1.0/registry.json`、`scripts/contract_registry.py`。
- Produces: `C2_CONTRACT_READY=yes`；后续任务只能使用 C1 已登记的名称。
- Produces: 分支 `feat/gov-c2`，起点 `feat/gov-c1`。

- [ ] **Step 0: 从 C1 分支创建独立 worktree**

只在主工作树执行本步骤的 `git worktree prune` 与 `git worktree add`。本步骤之后所有 Run/Commit 都在 `/Users/lute/Project/data_scrapy-gov-c2` 执行。

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c1^{commit}
git worktree add /Users/lute/Project/data_scrapy-gov-c2 -b feat/gov-c2 feat/gov-c1
cd /Users/lute/Project/data_scrapy-gov-c2
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md docs/superpowers/plans/
git branch --show-current
git merge-base --is-ancestor feat/gov-c1 HEAD; echo "c1_ancestor=$?"
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api && uv sync
cd /Users/lute/Project/data_scrapy-gov-c2
test -x apps/api/.venv/bin/python && echo "C2_API_VENV_READY"
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api && uv run alembic heads
cd /Users/lute/Project/data_scrapy-gov-c2
test -f configs/contracts/v1.1.0/registry.json && echo "C1_REGISTRY_PRESENT"
```

Expected:

```text
feat/gov-c2
c1_ancestor=0
C2_API_VENV_READY
202610220059 (head)
C1_REGISTRY_PRESENT
```

`feat/gov-c2` 分支或 `/Users/lute/Project/data_scrapy-gov-c2` 路径已存在时停止，先审查旧分支或旧 worktree，不得复用。`uv sync` 非 0 时停止。Alembic head 不是 `202610220059` 或 registry 缺失时停止，先完成 C0/C1。主工作树只作为计划复制源，复制后不再写入。

- [ ] **Step 1: 写只读契约守卫测试**

Create `apps/api/tests/unit/test_contract_freeze_c2.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"

REQUIRED_AUDIT_ACTIONS = (
    "auth.login.succeeded",
    "auth.login.failed",
    "auth.logout.succeeded",
    "task.created",
    "task.cancelled",
    "task.retried",
    "budget.price.changed",
    "budget.limit.changed",
    "budget.blocked",
    "claim.review.approved",
    "claim.review.rejected",
    "config.switch.changed",
    "delivery.published",
    "delivery.projection.viewed",
    "privacy.projection.applied",
)


def _registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _table(registry: dict[str, Any], name: str) -> dict[str, Any]:
    for table in registry["tables"]:
        if table["name"] == name:
            return table
    raise AssertionError(f"table not registered: {name}")


def test_c2_contract_entries_are_registered() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    required = (
        "`project_members`",
        "`audit_events`",
        "`workspace_members.role`",
        "/api/projects/{project_id}/members",
        "/api/audit-events",
        "/api/audit-events/verify",
        "WORKSPACE_RBAC_ENFORCED",
        "project_access_forbidden",
        "workspace_last_owner_required",
        "workspace_owner_required",
        "workspace_role_invalid",
        "上一事件哈希",
        "`prev_hash`",
        "`event_hash`",
        "`created_by_user_id`",
        "错误信封",
        "report_reviewer_assignments",
        "expires_at",
        "reviewer_assignment_required",
        "reviewer_assignment_invalid",
        "reviewer_assignment_expired",
        "审计动作注册表",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"C2 contract entries missing: {missing}"


def test_c2_registry_entries_exist() -> None:
    registry = _registry()
    names = {table["name"] for table in registry["tables"]}
    assert {"workspace_members", "project_members", "audit_events"} <= names
    paths = {item["path"] for item in registry["paths"]}
    assert {
        "/api/projects/{project_id}/members",
        "/api/projects/{project_id}/members/{user_id}",
        "/api/workspaces/current/members/{user_id}",
        "/api/audit-events",
        "/api/audit-events/verify",
    } <= paths
    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "project_access_forbidden",
        "workspace_last_owner_required",
        "workspace_owner_required",
        "workspace_role_invalid",
    } <= codes


def test_internal_reviewer_assignment_is_registered_with_expiry() -> None:
    registry = _registry()
    table = _table(registry, "report_reviewer_assignments")
    columns = {column["name"] for column in table["columns"]}
    assert {
        "id",
        "workspace_id",
        "project_id",
        "report_id",
        "artifact_id",
        "reviewer_user_id",
        "assignment_scope",
        "status",
        "assigned_by",
        "assigned_at",
        "expires_at",
        "revoked_at",
    } <= columns
    expires = next(
        column for column in table["columns"] if column["name"] == "expires_at"
    )
    assert expires["nullable"] is False

    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["report_reviewer_assignments.assignment_scope"] == [
        "report_read",
        "report_review",
    ]
    assert "reviewer" not in enums["workspace_members.role"]

    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/api/reports/{report_id}/reviewers") in paths
    assert ("DELETE", "/api/reports/{report_id}/reviewers/{user_id}") in paths

    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "reviewer_assignment_required",
        "reviewer_assignment_invalid",
        "reviewer_assignment_expired",
    } <= codes


def test_c1_contract_lists_every_required_audit_action() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    missing = [action for action in REQUIRED_AUDIT_ACTIONS if action not in text]
    assert not missing, f"audit actions missing from C1 contract: {missing}"


def test_c2_contract_declares_single_owner_source() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "唯一授权事实源" in text
    assert "`workspaces.owner_id` 不是授权事实源" in text
```

- [ ] **Step 2: 运行守卫测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_contract_freeze_c2.py -v
```

Expected: 5 passed。缺任一对象时输出 `C2_CONTRACT_GAP` 并停止，把缺口交回 C1；C2 不得自行修改契约。

- [ ] **Step 3: 运行 C1 checker**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `registry check OK`。失败时停止，先修 C1，不在 C2 改契约。

- [ ] **Step 4: 提交前运行 GitNexus 变更分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。出现 `partial: true` 或 `truncated: true` 时重跑。

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git add apps/api/tests/unit/test_contract_freeze_c2.py \
  docs/superpowers/plans/2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md
git commit -m "test(contract): guard C2 identity ACL and audit entries"
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

### Task 2: 迁移 058 与两个新模型

**Files:**
- Create: `apps/api/alembic/versions/202610220060_identity_acl_audit.py`
- Create: `apps/api/src/data_intelligence_hub/models/project_member.py`
- Create: `apps/api/src/data_intelligence_hub/models/audit_event.py`
- Modify: `apps/api/src/data_intelligence_hub/models/workspace.py:46-57`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py:1-160`
- Test: `apps/api/tests/unit/test_c2_migration_source.py`

**Interfaces:**
- Consumes: 契约名称 `project_members`、`audit_events`、`workspace_members.role`。
- Produces: `ProjectMember` 模型，字段 `workspace_id`、`project_id`、`user_id`、`created_by_user_id`、`created_at`。
- Produces: `AuditEvent` 模型，字段 `workspace_id`、`project_id`、`sequence_number`、`actor_user_id`、`actor_type`、`action`、`resource_type`、`resource_id`、`request_id`、`result`、`details`、`prev_hash`、`event_hash`、`occurred_at`、`created_at`。
- Produces: `AUDIT_GENESIS_HASH = "0" * 64`。
- Produces: Alembic revision `202610220060`，`down_revision = "202610220059"`。

- [ ] **Step 1: 预检 B5 与 worktree**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git worktree prune
git fetch origin
git tag -l pg0-baseline-v1
git status --porcelain
git branch --show-current
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run alembic heads
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs status
node .gitnexus/run.cjs impact "WorkspaceMember" --direction upstream --repo .
```

Expected: `git tag -l pg0-baseline-v1` 有一行；`git branch --show-current` 是 `feat/gov-c2`；当前分支已包含 C0 与 C1；`git status --porcelain` 为空（计划 Markdown 除外）；`git worktree list` 不再列出 4 个 `/private/tmp/dih-*`；`alembic heads` 只有一行 `202610220059`；impact 输出列出 `WorkspaceMember` 的调用方与风险。标签或 C1 契约不存在时停止 C2，先执行 C0/C1；不得把 058 接到 055。

- [ ] **Step 2: 写失败的迁移与模型测试**

Create `apps/api/tests/unit/test_c2_migration_source.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import CheckConstraint, Constraint, ForeignKeyConstraint

from data_intelligence_hub.models import Base

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610220060_identity_acl_audit.py"


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
    spec = importlib.util.spec_from_file_location("identity_acl_audit", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_058_is_linear_after_b5() -> None:
    module = _load_migration()
    assert module.revision == "202610220060"
    assert module.down_revision == "202610220059"


def test_revision_058_creates_the_two_tables_and_backfills_owner() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    created = [args[0] for name, args, _ in recorder.calls if name == "create_table"]
    assert created == ["project_members", "audit_events"]

    audit_columns = {
        arg.name
        for name, args, _ in recorder.calls
        if name == "create_table" and args[0] == "audit_events"
        for arg in args[1:]
        if hasattr(arg, "name")
    }
    assert {
        "workspace_id",
        "project_id",
        "sequence_number",
        "actor_user_id",
        "actor_type",
        "action",
        "resource_type",
        "resource_id",
        "request_id",
        "result",
        "details",
        "prev_hash",
        "event_hash",
        "occurred_at",
        "created_at",
    } <= audit_columns

    executed = " ".join(str(args[0]) for name, args, _ in recorder.calls if name == "execute")
    assert "workspace_members" in executed
    assert "role='owner'" in executed
    assert "trg_audit_events_append_only" in executed
    assert "trg_workspace_members_last_owner" in executed


def test_models_expose_acl_and_audit_without_user_sessions() -> None:
    assert "project_members" in Base.metadata.tables
    assert "audit_events" in Base.metadata.tables
    assert "user_sessions" not in Base.metadata.tables

    workspace_members = Base.metadata.tables["workspace_members"]
    checks = [
        constraint
        for constraint in workspace_members.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert any("role IN" in str(check.sqltext) for check in checks)


def test_project_member_has_tenant_foreign_key_and_unique_grant() -> None:
    table = Base.metadata.tables["project_members"]
    names = {cast(str, constraint.name) for constraint in table.constraints if constraint.name}
    assert "uq_project_members_workspace_project_user" in names
    assert "fk_project_members_project_tenant" in names
    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 5
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_c2_migration_source.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.models.project_member'` 或迁移文件不存在。

- [ ] **Step 4: 新增 `ProjectMember` 模型**

Create `apps/api/src/data_intelligence_hub/models/project_member.py`:

```python
"""项目成员 ACL。

一行表示一个工作区成员可以查看一个项目。owner/admin 不需要行。
不设项目级角色列：项目权限只有“可见/不可见”。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.user import User


class ProjectMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "user_id",
            name="uq_project_members_workspace_project_user",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_project_members_project_tenant",
        ),
        Index("ix_project_members_workspace_user", "workspace_id", "user_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(foreign_keys=[project_id])
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
```

- [ ] **Step 5: 新增 `AuditEvent` 模型**

Create `apps/api/src/data_intelligence_hub/models/audit_event.py`:

```python
"""统一追加式审计事件。

审计表没有 updated_at。生产迁移创建 BEFORE UPDATE OR DELETE 触发器。
哈希链按 workspace_id 串行：sequence_number 从 1 开始，prev_hash 指向上一条
同工作区事件的 event_hash；首条 prev_hash 是 64 个 0。
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
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

AUDIT_GENESIS_HASH = "0" * 64
AUDIT_ACTOR_TYPES = ("user", "system", "project_key")
AUDIT_RESULTS = ("success", "denied", "failed")


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "sequence_number",
            name="uq_audit_events_workspace_sequence",
        ),
        UniqueConstraint(
            "workspace_id",
            "event_hash",
            name="uq_audit_events_workspace_hash",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_audit_events_project_tenant",
        ),
        CheckConstraint(
            "actor_type IN ('user','system','project_key')",
            name="actor_type",
        ),
        CheckConstraint(
            "result IN ('success','denied','failed')",
            name="result",
        ),
        Index(
            "ix_audit_events_workspace_occurred",
            "workspace_id",
            "occurred_at",
        ),
        Index("ix_audit_events_workspace_action", "workspace_id", "action"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 6: 修改 `WorkspaceMember` 增加角色约束**

Modify `apps/api/src/data_intelligence_hub/models/workspace.py:46-57`:

```python
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
```

```python
class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_user"),
        CheckConstraint("role IN ('owner','admin','member')", name="role"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="workspace_memberships")
```

- [ ] **Step 7: 注册模型**

在 `apps/api/src/data_intelligence_hub/models/__init__.py` 增加：

```python
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.project_member import ProjectMember
```

并在 `__all__` 中按字母序加入 `"AuditEvent"` 与 `"ProjectMember"`。

- [ ] **Step 8: 写迁移 058**

Create `apps/api/alembic/versions/202610220060_identity_acl_audit.py`:

```python
"""Identity roles, project ACL, and append-only audit.

Revision ID: 202610220060
Revises: 202610220059
Create Date: 2026-10-22

说明：

- ``project_members`` 只给 member 增加项目可见性；owner/admin 不需要行。
- ``audit_events`` 只追加。生产 PostgreSQL 安装 BEFORE UPDATE OR DELETE 触发器。
- 回填 ``workspace_members``：每个 ``workspaces.owner_id`` 必须有一条 owner 行。
- 本迁移不建 ``user_sessions``，也不建 MFA 表。
- source-only: 本迁移只含 schema 与必要回填，不含业务逻辑。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220060"
down_revision: str | None = "202610220059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_project_members_project_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "user_id",
            name="uq_project_members_workspace_project_user",
        ),
    )
    op.create_index(
        "ix_project_members_workspace_user",
        "project_members",
        ["workspace_id", "user_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "actor_type", sa.String(length=20), nullable=False, server_default="user"
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('user','system','project_key')",
            name="ck_audit_events_actor_type",
        ),
        sa.CheckConstraint(
            "result IN ('success','denied','failed')",
            name="ck_audit_events_result",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_audit_events_project_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "sequence_number",
            name="uq_audit_events_workspace_sequence",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "event_hash",
            name="uq_audit_events_workspace_hash",
        ),
    )
    op.create_index(
        "ix_audit_events_workspace_occurred",
        "audit_events",
        ["workspace_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_workspace_action",
        "audit_events",
        ["workspace_id", "action"],
    )

    op.execute(
        """
        UPDATE workspace_members
        SET role = 'member'
        WHERE role NOT IN ('owner','admin','member')
        """
    )
    op.execute(
        """
        INSERT INTO workspace_members (id, workspace_id, user_id, role, created_at, updated_at)
        SELECT gen_random_uuid(), w.id, w.owner_id, 'owner', now(), now()
        FROM workspaces AS w
        WHERE NOT EXISTS (
            SELECT 1
            FROM workspace_members AS m
            WHERE m.workspace_id = w.id AND m.user_id = w.owner_id
        )
        """
    )
    op.execute(
        """
        UPDATE workspace_members AS m
        SET role = 'owner', updated_at = now()
        FROM workspaces AS w
        WHERE m.workspace_id = w.id
          AND m.user_id = w.owner_id
          AND m.role <> 'owner'
        """
    )

    op.create_check_constraint(
        "ck_workspace_members_role",
        "workspace_members",
        "role IN ('owner','admin','member')",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_workspace_last_owner()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF (TG_OP = 'DELETE' AND OLD.role = 'owner')
               OR (TG_OP = 'UPDATE' AND OLD.role = 'owner' AND NEW.role <> 'owner') THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM workspace_members
                    WHERE workspace_id = OLD.workspace_id
                      AND role = 'owner'
                      AND id <> OLD.id
                ) THEN
                    RAISE EXCEPTION 'workspace_last_owner_required';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_workspace_members_last_owner
        BEFORE UPDATE OR DELETE ON workspace_members
        FOR EACH ROW EXECUTE FUNCTION enforce_workspace_last_owner()
        """
    )
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
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT count(*) FROM audit_events")).scalar_one()
    if count:
        raise RuntimeError("refusing downgrade with audit evidence")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_event_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workspace_members_last_owner ON workspace_members"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_workspace_last_owner()")
    op.drop_constraint("ck_workspace_members_role", "workspace_members", type_="check")
    op.drop_index("ix_audit_events_workspace_action", table_name="audit_events")
    op.drop_index("ix_audit_events_workspace_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_project_members_workspace_user", table_name="project_members")
    op.drop_table("project_members")
```

- [ ] **Step 9: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_c2_migration_source.py -v
uv run alembic heads
```

Expected: `4 passed`；`alembic heads` 输出只有 `202610220060 (head)`。若本机没有 PostgreSQL，`uv run alembic upgrade head` 留到本计划末尾的 C2 验收门禁执行。

- [ ] **Step 10: GitNexus impact 与 commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs impact "WorkspaceMember" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220060_identity_acl_audit.py \
  apps/api/src/data_intelligence_hub/models/project_member.py \
  apps/api/src/data_intelligence_hub/models/audit_event.py \
  apps/api/src/data_intelligence_hub/models/workspace.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/test_c2_migration_source.py
git commit -m "feat(identity): add C2 ACL and audit tables"
```

Expected: impact 报告 `WorkspaceMember` 的调用方与风险；`detect-changes` 不含 `partial: true` 或 `truncated: true`。

---

### Task 3: 统一错误信封与请求 ID

**Files:**
- Create: `apps/api/src/data_intelligence_hub/core/errors.py`
- Create: `apps/api/tests/unit/test_error_envelope.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py:1-190`
- Modify: `apps/api/tests/unit/test_task_runs_route.py:168,189`
- Modify: `apps/api/tests/integration/test_social_provider_routes.py:400,411,419,471`

**Interfaces:**
- Consumes: 无。
- Produces: `APIError(status_code: int, code: str, message: str | None = None, details: dict[str, Any] | None = None, headers: dict[str, str] | None = None)`。
- Produces: `install_error_contract(app: FastAPI) -> None`。
- Produces: `request_id_middleware(request: Request, call_next) -> Response`。
- Produces: 响应头 `X-Request-ID`；错误体 `detail` 与 `error` 双字段。

- [ ] **Step 1: 写失败的错误信封测试**

先运行 impact：

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs impact "create_app" --direction upstream --repo .
```

Create `apps/api/tests/unit/test_error_envelope.py`:

```python
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

from data_intelligence_hub.core.errors import APIError, install_error_contract


def _build_app() -> FastAPI:
    app = FastAPI()
    install_error_contract(app)

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise APIError(
            403,
            "project_access_forbidden",
            "Project access is forbidden",
            {"project_id": "p-1"},
        )

    @app.get("/legacy")
    async def legacy() -> None:
        raise HTTPException(status_code=404, detail="project_not_found")

    @app.get("/validate")
    async def validate(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret-value")

    return app


def test_api_error_has_detail_and_envelope() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/forbidden", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 403
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.json() == {
        "detail": "project_access_forbidden",
        "error": {
            "code": "project_access_forbidden",
            "message": "Project access is forbidden",
            "request_id": "req-123",
            "details": {"project_id": "p-1"},
        },
    }


def test_legacy_http_exception_keeps_detail() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/legacy")

    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "project_not_found"
    assert body["error"]["code"] == "project_not_found"
    assert len(body["error"]["request_id"]) == 32


def test_validation_error_gets_envelope() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/validate?limit=0")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_failed"
    assert body["error"]["details"] == {}
    assert isinstance(body["detail"], list)


def test_unhandled_error_does_not_leak_message() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert body["error"]["code"] == "internal_error"
    assert "secret-value" not in response.text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_error_envelope.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.core.errors'`。

- [ ] **Step 3: 新增 `core/errors.py`**

Create `apps/api/src/data_intelligence_hub/core/errors.py`:

```python
"""统一错误信封与请求 ID。

响应保留既有 ``detail``，并附加 ``error``。控制台与旧测试继续读 ``detail``。
未处理异常只返回固定文案，不回显异常内容。
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

SANITIZED_VALIDATION_PATHS = frozenset(
    {"/api/automation/social-provider-youtube-read-plan"}
)

_LEGACY_DETAIL_CODES = {
    "Authentication required": "authentication_required",
    "Invalid authentication token": "invalid_authentication_token",
    "User is not active": "user_not_active",
}


class APIError(HTTPException):
    """带稳定错误码的 HTTP 错误。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message or code.replace("_", " ")
        self.details = details or {}
        super().__init__(status_code=status_code, detail=code, headers=headers)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return uuid.uuid4().hex


def _envelope(
    request: Request,
    status_code: int,
    *,
    code: str,
    message: str,
    details: dict[str, Any],
    legacy_detail: Any,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = {
        "detail": jsonable_encoder(legacy_detail),
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": jsonable_encoder(details),
        },
    }
    response_headers = dict(headers or {})
    response_headers.setdefault("X-Request-ID", request_id)
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=response_headers,
    )


async def request_id_middleware(request: Request, call_next: Any) -> Any:
    request_id = (request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64]
    request.state.request_id = request_id
    response = await call_next(request)
    if "X-Request-ID" not in response.headers:
        response.headers["X-Request-ID"] = request_id
    return response


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _envelope(
        request,
        exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        legacy_detail=exc.detail,
        headers=exc.headers,
    )


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", code))
        details = {
            key: value for key, value in detail.items() if key not in {"code", "message"}
        }
    elif isinstance(detail, str):
        code = _LEGACY_DETAIL_CODES.get(detail, detail)
        message = detail
        details = {}
    else:
        code = "http_error"
        message = "HTTP error"
        details = {"detail": jsonable_encoder(detail)}
    return _envelope(
        request,
        exc.status_code,
        code=code,
        message=message,
        details=details,
        legacy_detail=detail,
        headers=exc.headers,
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if request.url.path in SANITIZED_VALIDATION_PATHS:
        return _envelope(
            request,
            422,
            code="youtube_read_plan_request_invalid",
            message="youtube_read_plan_request_invalid",
            details={},
            legacy_detail="youtube_read_plan_request_invalid",
        )
    return _envelope(
        request,
        422,
        code="request_validation_failed",
        message="Request validation failed",
        details={},
        legacy_detail=jsonable_encoder(exc.errors()),
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        request_id=_request_id(request),
        path=request.url.path,
    )
    return _envelope(
        request,
        500,
        code="internal_error",
        message="Internal server error",
        details={},
        legacy_detail="Internal server error",
    )


def install_error_contract(app: FastAPI) -> None:
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
```

- [ ] **Step 4: 在 `main.py` 安装错误契约**

Modify `apps/api/src/data_intelligence_hub/main.py`:

- 删除 `jsonable_encoder`、`RequestValidationError` 导入。
- 删除 `_sanitized_422_paths` 与局部 `@app.exception_handler(RequestValidationError)` 块（第 165-185 行附近）。
- 增加：

```python
from data_intelligence_hub.core.errors import install_error_contract
```

- 在 `app.add_middleware(CORSMiddleware, ...)` 之后、路由挂载之前调用：

```python
install_error_contract(app)
```

- 本任务不新增审计路由。`audit_events_router` 在 Task 6 创建后再挂载。

- [ ] **Step 5: 更新六个精确断言**

Modify `apps/api/tests/unit/test_task_runs_route.py:168,189`:

```python
    body = response.json()
    assert body["detail"] == "task_run_not_found"
    assert body["error"]["code"] == "task_run_not_found"
```

Modify `apps/api/tests/integration/test_social_provider_routes.py:400,411,419`:

```python
    assert rejected.json()["detail"] == "youtube_read_plan_request_invalid"
    assert rejected.json()["error"]["code"] == "youtube_read_plan_request_invalid"
```

Modify `apps/api/tests/integration/test_social_provider_routes.py:471`:

```python
        body = failed.json()
        assert body["detail"] == detail
        assert body["error"]["code"] == detail
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_error_envelope.py \
  tests/unit/test_task_runs_route.py \
  tests/integration/test_social_provider_routes.py -v
```

Expected: 全部 passed。

- [ ] **Step 7: 运行既有鉴权与项目测试确认兼容**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_auth_deps.py tests/integration/test_auth_projects.py -v
```

Expected: 全部 passed；既有 `detail` 断言不变。

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/data_intelligence_hub/core/errors.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/tests/unit/test_error_envelope.py \
  apps/api/tests/unit/test_task_runs_route.py \
  apps/api/tests/integration/test_social_provider_routes.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(api): add stable error envelope and request id"
```

---

### Task 4: 工作区角色、最后 owner 与会话角色

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/core/config.py:70-105`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/src/data_intelligence_hub/repositories/workspaces.py:1-160`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py:1-40`
- Modify: `apps/api/src/data_intelligence_hub/services/workspace_service.py:1-50`
- Modify: `apps/api/src/data_intelligence_hub/schemas/workspace.py:1-30`
- Modify: `apps/api/src/data_intelligence_hub/schemas/auth.py:42-50`
- Modify: `apps/api/src/data_intelligence_hub/services/auth_service.py:24-115`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/auth.py:31-85`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/workspaces.py:1-170`
- Test: `apps/api/tests/unit/test_workspace_roles.py`

**Interfaces:**
- Consumes: `workspace_members.role` 与 `workspaces.owner_id` 不变量。
- Produces: `get_workspace_role(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceRole | None`。
- Produces: `count_workspace_owners(session: AsyncSession, workspace_id: uuid.UUID) -> int`。
- Produces: `lock_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None`。
- Produces: `add_member(session, *, workspace: Workspace, actor_user_id: uuid.UUID, target_user_id: uuid.UUID, role: WorkspaceRole) -> WorkspaceMember`。
- Produces: `update_member_role(session, *, workspace: Workspace, actor_user_id: uuid.UUID, target_user_id: uuid.UUID, role: WorkspaceRole) -> WorkspaceMember`。
- Produces: `remove_member(session, *, workspace: Workspace, actor_user_id: uuid.UUID, target_user_id: uuid.UUID) -> bool`。
- Produces: `AuthSessionResponse.role: WorkspaceRole`。
- Produces: `PATCH /api/workspaces/current/members/{user_id}`。

- [ ] **Step 1: 写失败的角色测试**

先运行 impact：

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs impact "get_authenticated_context" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkspaceMember" --direction upstream --repo .
```

Create `apps/api/tests/unit/test_workspace_roles.py`:

```python
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.security import hash_password
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import (
    count_workspace_owners,
    get_workspace_role,
)
from data_intelligence_hub.services.auth_service import (
    login_user,
    register_user,
)
from data_intelligence_hub.services.exceptions import (
    WorkspaceLastOwnerError,
    WorkspaceOwnerImmutableError,
    WorkspaceOwnerRequiredError,
)
from data_intelligence_hub.services.workspace_service import (
    add_member,
    remove_member,
    update_member_role,
)
from data_intelligence_hub.schemas.auth import LoginRequest, RegisterRequest


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "owner": uuid.uuid4(),
        "admin": uuid.uuid4(),
        "member": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="c2-owner@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Owner",
                    status="active",
                ),
                User(
                    id=ids["admin"],
                    email="c2-admin@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Admin",
                    status="active",
                ),
                User(
                    id=ids["member"],
                    email="c2-member@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Member",
                    status="active",
                ),
                User(
                    id=ids["outsider"],
                    email="c2-outsider@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Outsider",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="C2 Workspace",
                    slug="c2-workspace",
                    owner_id=ids["owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["owner"], role="owner"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["admin"], role="admin"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["member"], role="member"
                ),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


async def _workspace(session: AsyncSession) -> Workspace:
    workspace = await session.get(Workspace, _ids()["workspace"])
    assert workspace is not None
    return workspace


@pytest.mark.asyncio
async def test_role_resolution_returns_three_roles_and_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert (
            await get_workspace_role(session, _ids()["workspace"], _ids()["owner"])
            == "owner"
        )
        assert (
            await get_workspace_role(session, _ids()["workspace"], _ids()["admin"])
            == "admin"
        )
        assert (
            await get_workspace_role(session, _ids()["workspace"], _ids()["member"])
            == "member"
        )
        assert (
            await get_workspace_role(session, _ids()["workspace"], _ids()["outsider"])
            is None
        )


@pytest.mark.asyncio
async def test_owner_can_promote_admin_and_last_owner_is_protected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        promoted = await update_member_role(
            session,
            workspace=workspace,
            actor_user_id=_ids()["owner"],
            target_user_id=_ids()["admin"],
            role="owner",
        )
        assert promoted.role == "owner"
        assert await count_workspace_owners(session, workspace.id) == 2

        demoted = await update_member_role(
            session,
            workspace=workspace,
            actor_user_id=_ids()["owner"],
            target_user_id=_ids()["admin"],
            role="admin",
        )
        assert demoted.role == "admin"
        assert await count_workspace_owners(session, workspace.id) == 1

        with pytest.raises(WorkspaceLastOwnerError):
            await update_member_role(
                session,
                workspace=workspace,
                actor_user_id=_ids()["owner"],
                target_user_id=_ids()["owner"],
                role="member",
            )


@pytest.mark.asyncio
async def test_owner_id_user_cannot_be_demoted_while_another_owner_exists(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        await update_member_role(
            session,
            workspace=workspace,
            actor_user_id=_ids()["owner"],
            target_user_id=_ids()["admin"],
            role="owner",
        )
        with pytest.raises(WorkspaceOwnerImmutableError):
            await update_member_role(
                session,
                workspace=workspace,
                actor_user_id=_ids()["owner"],
                target_user_id=_ids()["owner"],
                role="admin",
            )


@pytest.mark.asyncio
async def test_admin_cannot_manage_members_and_member_can_leave(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        with pytest.raises(WorkspaceOwnerRequiredError):
            await add_member(
                session,
                workspace=workspace,
                actor_user_id=_ids()["admin"],
                target_user_id=_ids()["outsider"],
                role="member",
            )
        with pytest.raises(WorkspaceOwnerRequiredError):
            await remove_member(
                session,
                workspace=workspace,
                actor_user_id=_ids()["admin"],
                target_user_id=_ids()["member"],
            )
        assert await remove_member(
            session,
            workspace=workspace,
            actor_user_id=_ids()["member"],
            target_user_id=_ids()["member"],
        )
        assert (
            await get_workspace_role(session, workspace.id, _ids()["member"]) is None
        )


@pytest.mark.asyncio
async def test_owner_adds_member_and_last_owner_cannot_leave(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        added = await add_member(
            session,
            workspace=workspace,
            actor_user_id=_ids()["owner"],
            target_user_id=_ids()["outsider"],
            role="admin",
        )
        assert added.role == "admin"
        with pytest.raises(WorkspaceLastOwnerError):
            await remove_member(
                session,
                workspace=workspace,
                actor_user_id=_ids()["owner"],
                target_user_id=_ids()["owner"],
            )


@pytest.mark.asyncio
async def test_auth_session_reports_role(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session_result = await register_user(
            session,
            RegisterRequest(
                email="c2-new@example.com",
                password="strong-password",
                name="New",
            ),
        )
        assert session_result.role == "owner"

        logged_in = await login_user(
            session,
            LoginRequest(
                email="c2-member@example.com", password="strong-password"
            ),
        )
        assert logged_in.role == "member"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_workspace_roles.py -v
```

Expected: FAIL，`ImportError` 找不到 `count_workspace_owners`、`WorkspaceLastOwnerError` 等。

- [ ] **Step 3: 增加配置开关**

Modify `apps/api/src/data_intelligence_hub/core/config.py` after `demo_mode`:

```python
    # workspace_rbac_enforced: 是否启用 owner/admin/member 项目 ACL。
    # 默认关闭以保留旧的项目可见性；打开后 member 只能访问 project_members 登记的项目。
    workspace_rbac_enforced: bool = False
```

Modify `apps/api/.env.example`，在 `DEMO_MODE` 段之后追加：

```dotenv
# WORKSPACE_RBAC_ENFORCED: 项目 ACL 的总开关。默认关闭以保留旧可见性。
# 打开后 owner/admin 可见全部项目，member 只能访问 project_members 授权项目。
WORKSPACE_RBAC_ENFORCED=false
```

- [ ] **Step 4: 增加仓储函数**

Modify `apps/api/src/data_intelligence_hub/repositories/workspaces.py`:

```python
from typing import Literal, cast

from sqlalchemy import case, func, select

WorkspaceRole = Literal["owner", "admin", "member"]
_VALID_ROLES = {"owner", "admin", "member"}


async def get_workspace_role(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceRole | None:
    result = await session.execute(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    role = result.scalar_one_or_none()
    if role in _VALID_ROLES:
        return cast(WorkspaceRole, role)
    return None


async def count_workspace_owners(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == "owner",
        )
    )
    return int(result.scalar_one())


async def lock_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> None:
    """串行化同一工作区的成员变更。

    SQLite 不支持 FOR UPDATE；SQLAlchemy 的 SQLite 方言会忽略它。
    PostgreSQL 下锁住工作区行，保证最后 owner 检查和并发邀请不会竞态。
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
    )
```

- [ ] **Step 5: 增加服务异常**

Modify `apps/api/src/data_intelligence_hub/services/exceptions.py`:

```python
class WorkspaceMembershipRequiredError(ServiceError):
    message = "workspace_membership_required"


class WorkspaceOwnerRequiredError(ServiceError):
    message = "workspace_owner_required"


class WorkspaceOwnerImmutableError(ServiceError):
    message = "workspace_owner_immovable"


class WorkspaceLastOwnerError(ServiceError):
    message = "workspace_last_owner_required"


class WorkspaceMemberExistsError(ServiceError):
    message = "workspace_member_exists"


class WorkspaceMemberNotFoundError(ServiceError):
    message = "workspace_member_not_found"


class WorkspaceRoleInvalidError(ServiceError):
    message = "workspace_role_invalid"
```

- [ ] **Step 6: 重写工作区成员服务**

Replace `apps/api/src/data_intelligence_hub/services/workspace_service.py`:

```python
"""工作区成员写入与最后 owner 保护。

提交权在 service，repository 只 flush。见 ADR-007 D4。
所有检查在工作区行锁内执行。
"""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import (
    WorkspaceRole,
    add_workspace_member,
    count_workspace_owners,
    get_workspace_role,
    lock_workspace,
    remove_workspace_member,
)
from data_intelligence_hub.services.exceptions import (
    WorkspaceLastOwnerError,
    WorkspaceMemberExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceMembershipRequiredError,
    WorkspaceOwnerImmutableError,
    WorkspaceOwnerRequiredError,
    WorkspaceRoleInvalidError,
)

_VALID_ROLES = {"owner", "admin", "member"}


async def _membership(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _require_owner(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    if await get_workspace_role(session, workspace_id, actor_user_id) != "owner":
        raise WorkspaceOwnerRequiredError


async def add_member(
    session: AsyncSession,
    *,
    workspace: Workspace,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: WorkspaceRole,
) -> WorkspaceMember:
    if role not in _VALID_ROLES:
        raise WorkspaceRoleInvalidError
    await lock_workspace(session, workspace.id)
    await _require_owner(session, workspace.id, actor_user_id)
    if await _membership(session, workspace.id, target_user_id) is not None:
        raise WorkspaceMemberExistsError
    member = await add_workspace_member(
        session, workspace.id, target_user_id, role
    )
    await session.commit()
    await session.refresh(member)
    return member


async def update_member_role(
    session: AsyncSession,
    *,
    workspace: Workspace,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: WorkspaceRole,
) -> WorkspaceMember:
    if role not in _VALID_ROLES:
        raise WorkspaceRoleInvalidError
    await lock_workspace(session, workspace.id)
    await _require_owner(session, workspace.id, actor_user_id)
    member = await _membership(session, workspace.id, target_user_id)
    if member is None:
        raise WorkspaceMemberNotFoundError
    current_role = cast(WorkspaceRole, member.role)

    if current_role == "owner" and role != "owner":
        if await count_workspace_owners(session, workspace.id) <= 1:
            raise WorkspaceLastOwnerError
        if target_user_id == workspace.owner_id:
            raise WorkspaceOwnerImmutableError

    member.role = role
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(
    session: AsyncSession,
    *,
    workspace: Workspace,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> bool:
    await lock_workspace(session, workspace.id)
    actor_role = await get_workspace_role(session, workspace.id, actor_user_id)
    if actor_role is None:
        raise WorkspaceMembershipRequiredError
    member = await _membership(session, workspace.id, target_user_id)
    if member is None:
        raise WorkspaceMemberNotFoundError

    if target_user_id != actor_user_id and actor_role != "owner":
        raise WorkspaceOwnerRequiredError

    if member.role == "owner":
        if await count_workspace_owners(session, workspace.id) <= 1:
            raise WorkspaceLastOwnerError
        if target_user_id == workspace.owner_id:
            raise WorkspaceOwnerImmutableError

    removed = await remove_workspace_member(
        session, workspace.id, target_user_id
    )
    if not removed:
        raise WorkspaceMemberNotFoundError
    await session.commit()
    return True
```

- [ ] **Step 7: 角色类型与请求 schema**

Replace `apps/api/src/data_intelligence_hub/schemas/workspace.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr

from data_intelligence_hub.schemas.auth import UserResponse, WorkspaceResponse

WorkspaceRole = Literal["owner", "admin", "member"]


class WorkspaceMembershipResponse(WorkspaceResponse):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    user: UserResponse
    role: WorkspaceRole


class AddWorkspaceMemberRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRole = "member"


class UpdateWorkspaceMemberRoleRequest(BaseModel):
    role: WorkspaceRole
```

Modify `apps/api/src/data_intelligence_hub/schemas/auth.py:42-50`。在文件顶部增加 `from typing import Literal`。`WorkspaceRole` 定义在 `schemas/auth.py`，`schemas/workspace.py` 从它导入，避免循环导入：

```python
WorkspaceRole = Literal["owner", "admin", "member"]


class AuthSessionResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
    role: WorkspaceRole
```

```python
# schemas/workspace.py
from data_intelligence_hub.schemas.auth import UserResponse, WorkspaceResponse, WorkspaceRole
```

- [ ] **Step 8: 让 `AuthSession` 带角色**

Modify `apps/api/src/data_intelligence_hub/services/auth_service.py`:

```python
from data_intelligence_hub.repositories.workspaces import (
    WorkspaceRole,
    get_workspace_role,
)
```

```python
@dataclass(frozen=True)
class AuthSession:
    user: User
    workspace: Workspace
    access_token: str
    role: WorkspaceRole


async def _role_for(
    session: AsyncSession,
    workspace: Workspace,
    user_id: uuid.UUID,
) -> WorkspaceRole:
    return await get_workspace_role(session, workspace.id, user_id) or "member"
```

`register_user` 的返回改为：

```python
    role = await _role_for(session, auth_workspace, user.id)
    return AuthSession(
        user=user,
        workspace=auth_workspace,
        access_token=create_access_token(user.id),
        role=role,
    )
```

`login_user` 与 `get_session_for_user` 的返回改为：

```python
    role = await _role_for(session, workspace, user.id)
    return AuthSession(
        user=user,
        workspace=workspace,
        access_token=create_access_token(user.id),
        role=role,
    )
```

- [ ] **Step 9: 会话响应带角色**

Modify `apps/api/src/data_intelligence_hub/api/routes/auth.py` 的三处 `AuthSessionResponse(...)`：

```python
    return AuthSessionResponse(
        user=auth_session.user,
        workspace=auth_session.workspace,
        role=auth_session.role,
    )
```

`me` 增加 `session: SessionDep` 并返回（文件顶部增加 `from data_intelligence_hub.repositories.workspaces import get_workspace_role`）：

```python
    role = await get_workspace_role(
        session, context.workspace.id, context.user.id
    ) or "member"
    return AuthSessionResponse(
        user=UserResponse.model_validate(context.user),
        workspace=WorkspaceResponse.model_validate(context.workspace),
        role=role,
    )
```

- [ ] **Step 10: 工作区路由改用服务与角色**

Replace the member portion of `apps/api/src/data_intelligence_hub/api/routes/workspaces.py` with:

```python
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.schemas.workspace import (
    AddWorkspaceMemberRequest,
    UpdateWorkspaceMemberRoleRequest,
    WorkspaceMemberResponse,
    WorkspaceMembershipResponse,
)
from data_intelligence_hub.services.exceptions import (
    WorkspaceLastOwnerError,
    WorkspaceMemberExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceMembershipRequiredError,
    WorkspaceOwnerImmutableError,
    WorkspaceOwnerRequiredError,
    WorkspaceRoleInvalidError,
)
from data_intelligence_hub.services.workspace_service import (
    add_member,
    remove_member,
    update_member_role,
)


def _member_response(member, user) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        user=UserResponse.model_validate(user), role=member.role
    )


@router.post(
    "/current/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_current_workspace_member(
    payload: AddWorkspaceMemberRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> WorkspaceMemberResponse:
    user = await get_user_by_email(session, str(payload.email))
    if user is None:
        raise APIError(404, "user_not_found")
    try:
        member = await add_member(
            session,
            workspace=context.workspace,
            actor_user_id=context.user.id,
            target_user_id=user.id,
            role=payload.role,
        )
    except WorkspaceOwnerRequiredError as exc:
        raise APIError(403, exc.message) from exc
    except WorkspaceMemberExistsError as exc:
        raise APIError(409, exc.message) from exc
    except WorkspaceRoleInvalidError as exc:
        raise APIError(400, exc.message) from exc
    return _member_response(member, user)


@router.patch(
    "/current/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def update_current_workspace_member_role(
    user_id: uuid.UUID,
    payload: UpdateWorkspaceMemberRoleRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> WorkspaceMemberResponse:
    try:
        member = await update_member_role(
            session,
            workspace=context.workspace,
            actor_user_id=context.user.id,
            target_user_id=user_id,
            role=payload.role,
        )
    except WorkspaceOwnerRequiredError as exc:
        raise APIError(403, exc.message) from exc
    except WorkspaceMemberNotFoundError as exc:
        raise APIError(404, exc.message) from exc
    except WorkspaceLastOwnerError as exc:
        raise APIError(409, exc.message) from exc
    except WorkspaceOwnerImmutableError as exc:
        raise APIError(403, exc.message) from exc
    except WorkspaceRoleInvalidError as exc:
        raise APIError(400, exc.message) from exc
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise APIError(404, "workspace_member_not_found")
    return _member_response(member, user)


@router.delete(
    "/current/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_current_workspace_member(
    user_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> None:
    try:
        await remove_member(
            session,
            workspace=context.workspace,
            actor_user_id=context.user.id,
            target_user_id=user_id,
        )
    except WorkspaceMembershipRequiredError as exc:
        raise APIError(403, exc.message) from exc
    except WorkspaceOwnerRequiredError as exc:
        raise APIError(403, exc.message) from exc
    except WorkspaceMemberNotFoundError as exc:
        raise APIError(404, exc.message) from exc
    except WorkspaceLastOwnerError as exc:
        raise APIError(409, exc.message) from exc
    except WorkspaceOwnerImmutableError as exc:
        raise APIError(403, exc.message) from exc
```

同时：

- 删除旧 `_require_owner`。
- `list_current_workspace_members` 保持所有工作区成员可读。
- `activate_workspace_item` 的响应增加 `role=await get_workspace_role(...) or "member"`。
- 导入 `APIError`、`get_user_by_id`、`get_workspace_role`。

- [ ] **Step 11: 更新最后 owner 的既有断言**

Modify `apps/api/tests/unit/test_workspace_resolution.py:test_owner_cannot_remove_owner`：

```python
    assert exc.value.status_code == 409
    assert exc.value.detail == "workspace_last_owner_required"
```

原因：该工作区只有一名 owner，移除自己先触发 `WorkspaceLastOwnerError`。旧断言 403 来自 `workspace_owner_immovable`，只适用于存在第二名 owner 的情况。

- [ ] **Step 12: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_workspace_roles.py \
  tests/integration/test_auth_projects.py \
  tests/unit/test_workspace_resolution.py -v
```

Expected: 全部 passed；`test_auth_projects` 中注册、登录、切换工作区响应多出 `role` 字段但不影响既有断言。

- [ ] **Step 13: Commit**

```bash
git add apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/.env.example \
  apps/api/src/data_intelligence_hub/repositories/workspaces.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/src/data_intelligence_hub/services/workspace_service.py \
  apps/api/src/data_intelligence_hub/schemas/workspace.py \
  apps/api/src/data_intelligence_hub/schemas/auth.py \
  apps/api/src/data_intelligence_hub/services/auth_service.py \
  apps/api/src/data_intelligence_hub/api/routes/auth.py \
  apps/api/src/data_intelligence_hub/api/routes/workspaces.py \
  apps/api/tests/unit/test_workspace_roles.py \
  apps/api/tests/unit/test_workspace_resolution.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(identity): unify workspace roles and protect last owner"
```

---

### Task 5: 项目 ACL、路由接缝与功能开关

**Files:**
- Create: `apps/api/src/data_intelligence_hub/repositories/project_members.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/reviewer_assignments.py`
- Create: `apps/api/src/data_intelligence_hub/api/authz.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/projects.py:1-40`
- Modify: `apps/api/src/data_intelligence_hub/services/project_service.py:1-100`
- Modify: `apps/api/src/data_intelligence_hub/schemas/project.py:1-70`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/projects.py:1-100`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:515-530`
- Test: `apps/api/tests/unit/test_project_acl.py`
- Test: `apps/api/tests/unit/test_internal_reviewer_access.py`

**Interfaces:**
- Consumes: `get_workspace_role`、`project_members` 表、`report_reviewer_assignments` 表（只读）、`WORKSPACE_RBAC_ENFORCED`。
- Produces: `ProjectAccess(project: Project, role: WorkspaceRole, is_project_member: bool)`。
- Produces: `require_workspace_role(session, *, workspace: Workspace, user: User, allowed: tuple[WorkspaceRole, ...]) -> WorkspaceRole`。
- Produces: `require_project_access(session, *, workspace: Workspace, user: User, project_id: uuid.UUID, manage: bool = False) -> ProjectAccess`。
- Produces: `ReviewerResourceKind = Literal["report", "claim", "evidence"]`。
- Produces: `ReviewerReadAccess(assignment_id, workspace_id, project_id, report_id, reviewer_user_id, assignment_scope, expires_at, resource_kind)`。
- Produces: `require_internal_reviewer_read(session, *, workspace, user, report_id, resource_kind, now=None) -> ReviewerReadAccess`。
- Produces: `get_active_reviewer_assignment(session, *, workspace_id, report_id, reviewer_user_id) -> dict[str, Any] | None`。
- Produces: `get_project_members(session, *, workspace_id, project_id) -> list[tuple[ProjectMember, User]]`。
- Produces: `add_project_member(session, *, workspace_id, project_id, user_id, created_by_user_id) -> ProjectMember`。
- Produces: `remove_project_member(session, *, workspace_id, project_id, user_id) -> bool`。
- Produces: `GET/POST /api/projects/{project_id}/members`、`DELETE /api/projects/{project_id}/members/{user_id}`。

- [ ] **Step 1: 写失败的项目 ACL 测试**

先运行 impact：

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs impact "get_projects" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_project" --direction upstream --repo .
```

Create `apps/api/tests/unit/test_project_acl.py`:

```python
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.authz import (
    require_project_access,
    require_workspace_role,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.project_members import (
    add_project_member,
    list_project_ids_for_member,
    remove_project_member,
)
from data_intelligence_hub.services.project_service import get_projects


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "owner": uuid.uuid4(),
        "admin": uuid.uuid4(),
        "member": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "other_workspace": uuid.uuid4(),
        "project_a": uuid.uuid4(),
        "project_b": uuid.uuid4(),
        "other_project": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="acl-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                User(
                    id=ids["admin"],
                    email="acl-admin@example.com",
                    password_hash="x",
                    name="Admin",
                    status="active",
                ),
                User(
                    id=ids["member"],
                    email="acl-member@example.com",
                    password_hash="x",
                    name="Member",
                    status="active",
                ),
                User(
                    id=ids["outsider"],
                    email="acl-outsider@example.com",
                    password_hash="x",
                    name="Outsider",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="ACL WS",
                    slug="acl-ws",
                    owner_id=ids["owner"],
                ),
                Workspace(
                    id=ids["other_workspace"],
                    name="Other WS",
                    slug="other-acl-ws",
                    owner_id=ids["outsider"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["owner"], role="owner"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["admin"], role="admin"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["member"], role="member"
                ),
                WorkspaceMember(
                    workspace_id=ids["other_workspace"],
                    user_id=ids["outsider"],
                    role="owner",
                ),
                Project(
                    id=ids["project_a"],
                    workspace_id=ids["workspace"],
                    name="Project A",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                Project(
                    id=ids["project_b"],
                    workspace_id=ids["workspace"],
                    name="Project B",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                Project(
                    id=ids["other_project"],
                    workspace_id=ids["other_workspace"],
                    name="Other Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["outsider"],
                ),
            ]
        )
        await session.commit()
        await add_project_member(
            session,
            workspace_id=ids["workspace"],
            project_id=ids["project_a"],
            user_id=ids["member"],
            created_by_user_id=ids["owner"],
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def reset_rbac_flag():
    settings = get_settings()
    original = settings.workspace_rbac_enforced
    yield
    settings.workspace_rbac_enforced = original


async def _load(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> tuple[User, Workspace]:
    user = await session.get(User, user_id)
    workspace = await session.get(Workspace, workspace_id)
    assert user is not None and workspace is not None
    return user, workspace


@pytest.mark.asyncio
async def test_owner_and_admin_see_all_projects_member_sees_assigned(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        owner, workspace = await _load(session, _ids()["owner"], _ids()["workspace"])
        admin, _ = await _load(session, _ids()["admin"], _ids()["workspace"])
        member, _ = await _load(session, _ids()["member"], _ids()["workspace"])

        assert {p.id for p in await get_projects(session, workspace, owner, None, None)} == {
            _ids()["project_a"],
            _ids()["project_b"],
        }
        assert {p.id for p in await get_projects(session, workspace, admin, None, None)} == {
            _ids()["project_a"],
            _ids()["project_b"],
        }
        assert {p.id for p in await get_projects(session, workspace, member, None, None)} == {
            _ids()["project_a"]
        }


@pytest.mark.asyncio
async def test_cross_workspace_is_404_and_same_workspace_unassigned_is_403(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        member, workspace = await _load(session, _ids()["member"], _ids()["workspace"])
        with pytest.raises(APIError) as cross:
            await require_project_access(
                session,
                workspace=workspace,
                user=member,
                project_id=_ids()["other_project"],
            )
        assert cross.value.status_code == 404
        assert cross.value.code == "project_not_found"

        with pytest.raises(APIError) as denied:
            await require_project_access(
                session,
                workspace=workspace,
                user=member,
                project_id=_ids()["project_b"],
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "project_access_forbidden"


@pytest.mark.asyncio
async def test_project_member_can_view_but_not_manage(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        member, workspace = await _load(session, _ids()["member"], _ids()["workspace"])
        access = await require_project_access(
            session,
            workspace=workspace,
            user=member,
            project_id=_ids()["project_a"],
        )
        assert access.is_project_member is True
        with pytest.raises(APIError) as denied:
            await require_project_access(
                session,
                workspace=workspace,
                user=member,
                project_id=_ids()["project_a"],
                manage=True,
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "project_management_forbidden"


@pytest.mark.asyncio
async def test_owner_grants_and_revokes_project_member(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        owner, workspace = await _load(session, _ids()["owner"], _ids()["workspace"])
        await add_project_member(
            session,
            workspace_id=workspace.id,
            project_id=_ids()["project_b"],
            user_id=_ids()["member"],
            created_by_user_id=owner.id,
        )
        await session.commit()
        assert await list_project_ids_for_member(
            session, workspace.id, _ids()["member"]
        ) == {_ids()["project_a"], _ids()["project_b"]}

        assert await remove_project_member(
            session,
            workspace_id=workspace.id,
            project_id=_ids()["project_b"],
            user_id=_ids()["member"],
        )
        await session.commit()
        assert await list_project_ids_for_member(
            session, workspace.id, _ids()["member"]
        ) == {_ids()["project_a"]}


@pytest.mark.asyncio
async def test_flag_off_preserves_legacy_project_visibility(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = False
    async with session_factory() as session:
        member, workspace = await _load(session, _ids()["member"], _ids()["workspace"])
        assert {p.id for p in await get_projects(session, workspace, member, None, None)} == {
            _ids()["project_a"],
            _ids()["project_b"],
        }
        access = await require_project_access(
            session,
            workspace=workspace,
            user=member,
            project_id=_ids()["project_b"],
        )
        assert access.project.id == _ids()["project_b"]


@pytest.mark.asyncio
async def test_member_cannot_create_project(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        member, workspace = await _load(session, _ids()["member"], _ids()["workspace"])
        with pytest.raises(APIError) as denied:
            await require_workspace_role(
                session,
                workspace=workspace,
                user=member,
                allowed=("owner", "admin"),
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "workspace_role_forbidden"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_project_acl.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.api.authz'`。

- [ ] **Step 3: 新增项目成员仓储**

Create `apps/api/src/data_intelligence_hub/repositories/project_members.py`:

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project_member import ProjectMember
from data_intelligence_hub.models.user import User


async def get_project_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ProjectMember | None:
    result = await session.execute(
        select(ProjectMember).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_project_members(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[tuple[ProjectMember, User]]:
    result = await session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.project_id == project_id,
        )
        .order_by(ProjectMember.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def add_project_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
) -> ProjectMember:
    member = ProjectMember(
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        created_by_user_id=created_by_user_id,
    )
    session.add(member)
    await session.flush()
    await session.refresh(member)
    return member


async def remove_project_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    member = await get_project_member(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
    )
    if member is None:
        return False
    await session.delete(member)
    await session.flush()
    return True


async def list_project_ids_for_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> set[uuid.UUID]:
    result = await session.execute(
        select(ProjectMember.project_id).where(
            ProjectMember.workspace_id == workspace_id,
            ProjectMember.user_id == user_id,
        )
    )
    return set(result.scalars().all())
```

- [ ] **Step 4: 项目列表按成员过滤**

Modify `apps/api/src/data_intelligence_hub/repositories/projects.py`:

```python
from sqlalchemy import and_, select

from data_intelligence_hub.models.project_member import ProjectMember


async def list_projects_for_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    domain: str | None = None,
    status: str | None = None,
) -> list[Project]:
    statement = (
        select(Project)
        .join(
            ProjectMember,
            and_(
                ProjectMember.project_id == Project.id,
                ProjectMember.workspace_id == Project.workspace_id,
            ),
        )
        .where(
            Project.workspace_id == workspace_id,
            ProjectMember.user_id == user_id,
        )
    )
    if domain is not None:
        statement = statement.where(Project.domain == domain)
    if status is not None:
        statement = statement.where(Project.status == status)
    statement = statement.order_by(Project.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())
```

- [ ] **Step 5: 新增授权接缝**

Create `apps/api/src/data_intelligence_hub/api/authz.py`:

```python
"""工作区与项目授权的唯一接缝。

规则：
- owner/admin 可见工作区全部项目。
- member 只可见 project_members 中登记的项目。
- 跨工作区一律 404；同工作区无项目权限 403。
- WORKSPACE_RBAC_ENFORCED 关闭时，项目可见性退回旧行为。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.project_members import get_project_member
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workspaces import (
    WorkspaceRole,
    get_workspace_role,
)


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    role: WorkspaceRole
    is_project_member: bool


async def require_workspace_role(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    allowed: tuple[WorkspaceRole, ...],
) -> WorkspaceRole:
    role = await get_workspace_role(session, workspace.id, user.id)
    if role is None:
        raise APIError(403, "workspace_membership_required")
    if role not in allowed:
        raise APIError(
            403,
            "workspace_role_forbidden",
            details={"allowed": list(allowed), "actual": role},
        )
    return role


async def require_project_access(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    project_id: uuid.UUID,
    manage: bool = False,
) -> ProjectAccess:
    project = await get_project(session, workspace.id, project_id)
    if project is None:
        raise APIError(404, "project_not_found")

    role = await get_workspace_role(session, workspace.id, user.id)
    if role is None:
        raise APIError(403, "workspace_membership_required")
    if role in ("owner", "admin"):
        return ProjectAccess(project=project, role=role, is_project_member=False)

    if not get_settings().workspace_rbac_enforced:
        return ProjectAccess(project=project, role=role, is_project_member=False)

    member = await get_project_member(
        session,
        workspace_id=workspace.id,
        project_id=project_id,
        user_id=user.id,
    )
    if member is None:
        raise APIError(403, "project_access_forbidden")
    if manage:
        raise APIError(403, "project_management_forbidden")
    return ProjectAccess(project=project, role=role, is_project_member=True)
```

- [ ] **Step 6: 项目服务按角色过滤并接收 project 对象**

Modify `apps/api/src/data_intelligence_hub/services/project_service.py`:

```python
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.projects import (
    get_project,
    list_projects,
    list_projects_for_member,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_role


async def get_projects(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    domain: str | None,
    status: str | None,
) -> list[Project]:
    role = await get_workspace_role(session, workspace.id, user.id)
    if role is None:
        return []
    if get_settings().workspace_rbac_enforced and role == "member":
        return await list_projects_for_member(
            session, workspace.id, user.id, domain=domain, status=status
        )
    return await list_projects(session, workspace.id, domain=domain, status=status)
```

`create_project` 保持原签名，但增加审计入口参数（Task 8 使用）：

```python
async def create_project(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    payload: ProjectCreateRequest,
    *,
    request_id: str | None = None,
) -> Project:
```

`update_project` 与 `archive_project` 改为接收已授权项目：

```python
async def update_project(
    session: AsyncSession,
    project: Project,
    payload: ProjectUpdateRequest,
    *,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
) -> Project:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "name" and isinstance(value, str):
            value = value.strip()
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def archive_project(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
) -> Project:
    project.status = "archived"
    await session.commit()
    await session.refresh(project)
    return project
```

保留 `get_project_or_raise` 与 `get_active_project_or_raise` 原签名，避免影响 workflow planner。项目 ACL 的计划预览切换在 Step 10 的路由层完成，service 不导入 `api.authz`。

- [ ] **Step 7: 项目 schema 增加成员响应**

Modify `apps/api/src/data_intelligence_hub/schemas/project.py`:

```python
from datetime import datetime

from data_intelligence_hub.schemas.auth import UserResponse


class ProjectMemberResponse(BaseModel):
    user: UserResponse
    added_at: datetime


class AddProjectMemberRequest(BaseModel):
    user_id: uuid.UUID
```

- [ ] **Step 8: 项目路由接入 ACL 与成员 CRUD**

Modify `apps/api/src/data_intelligence_hub/api/routes/projects.py`:

- 列表：

```python
from data_intelligence_hub.api.authz import (
    require_project_access,
    require_workspace_role,
)

@router.get("", response_model=list[ProjectResponse])
async def list_project_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    domain: Annotated[ProjectDomain | None, Query()] = None,
    status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None,
) -> list[ProjectResponse]:
    projects = await get_projects(
        session, context.workspace, context.user, domain=domain, status=status_filter
    )
    return [ProjectResponse.model_validate(project) for project in projects]
```

- 创建：

```python
@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_item(
    payload: ProjectCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ProjectResponse:
    await require_workspace_role(
        session,
        workspace=context.workspace,
        user=context.user,
        allowed=("owner", "admin"),
    )
    project = await create_project(session, context.user, context.workspace, payload)
    return ProjectResponse.model_validate(project)
```

- 详情/更新/归档：

```python
@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ProjectResponse:
    access = await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
    )
    return ProjectResponse.model_validate(access.project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_item(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ProjectResponse:
    access = await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )
    project = await update_project(
        session,
        access.project,
        payload,
        actor_user_id=context.user.id,
    )
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=ProjectResponse)
async def archive_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ProjectResponse:
    access = await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )
    project = await archive_project(
        session,
        access.project,
        actor_user_id=context.user.id,
    )
    return ProjectResponse.model_validate(project)
```

- 项目成员 CRUD：

```python
from data_intelligence_hub.repositories.project_members import (
    add_project_member,
    list_project_members,
    remove_project_member,
)
from data_intelligence_hub.repositories.workspaces import user_belongs_to_workspace
from data_intelligence_hub.schemas.project import (
    AddProjectMemberRequest,
    ProjectMemberResponse,
)


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
)
async def list_project_member_items(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> list[ProjectMemberResponse]:
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )
    rows = await list_project_members(session, context.workspace.id, project_id)
    return [
        ProjectMemberResponse(
            user=UserResponse.model_validate(user), added_at=member.created_at
        )
        for member, user in rows
    ]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member_item(
    project_id: uuid.UUID,
    payload: AddProjectMemberRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ProjectMemberResponse:
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )
    if not await user_belongs_to_workspace(
        session, payload.user_id, context.workspace.id
    ):
        raise APIError(404, "workspace_member_not_found")
    if await get_project_member(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        user_id=payload.user_id,
    ) is not None:
        raise APIError(409, "project_member_exists")
    member = await add_project_member(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        user_id=payload.user_id,
        created_by_user_id=context.user.id,
    )
    await session.commit()
    user = await get_user_by_id(session, payload.user_id)
    if user is None:
        raise APIError(404, "workspace_member_not_found")
    return ProjectMemberResponse(
        user=UserResponse.model_validate(user), added_at=member.created_at
    )


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member_item(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> None:
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
        manage=True,
    )
    removed = await remove_project_member(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        user_id=user_id,
    )
    if not removed:
        raise APIError(404, "project_member_not_found")
    await session.commit()
```

需要在 `projects.py` 导入 `APIError`、`get_project_member`、`get_user_by_id`、`UserResponse`。同时删除不再使用的 `get_project_or_raise`、`ProjectNotFoundError` 与旧 `HTTPException` 导入。

- [ ] **Step 9: 记录项目密钥的 C3 交接**

`apps/api/src/data_intelligence_hub/api/routes/project_api_keys.py` 归 C3 所有。C2 不修改该路由；C3 迁移 059 用 `require_workspace_role` 把密钥管理限制为 owner/admin，并保留既有错误码 `project_key_management_forbidden`。C2 的 `test_project_acl.py` 不测试项目密钥。

- [ ] **Step 10: 计划预览使用项目 ACL**

Modify `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py:515-530`:

```python
from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.services.exceptions import ProjectNotActiveError
```

```python
        access = await require_project_access(
            session,
            workspace=context.workspace,
            user=context.user,
            project_id=project_id,
        )
        if access.project.status != "active":
            raise ProjectNotActiveError
        project = access.project
```

- [ ] **Step 11: 写失败的内部审阅者只读接缝测试**

Create `apps/api/tests/unit/test_internal_reviewer_access.py`：

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import Column, DateTime, MetaData, String, Table, Uuid, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.authz import (
    ReviewerResourceKind,
    require_internal_reviewer_read,
)
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

# C1 登记的 report_reviewer_assignments 由 C9 迁移 065 创建。
# C2 用独立 MetaData 建等价 SQLite 表验证只读接缝，不新增生产表，
# 也不与 C9 的 ORM 模型共享 Base.metadata。
REVIEW_METADATA = MetaData()
REVIEWER_ASSIGNMENTS = Table(
    "report_reviewer_assignments",
    REVIEW_METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("workspace_id", Uuid(), nullable=False),
    Column("project_id", Uuid(), nullable=True),
    Column("report_id", Uuid(), nullable=False),
    Column("artifact_id", Uuid(), nullable=True),
    Column("reviewer_user_id", Uuid(), nullable=False),
    Column("assignment_scope", String(30), nullable=False),
    Column("status", String(20), nullable=False),
    Column("assigned_by", Uuid(), nullable=False),
    Column("assigned_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(REVIEW_METADATA.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    ids = {
        "owner": uuid.uuid4(),
        "reviewer": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "other_workspace": uuid.uuid4(),
        "project_a": uuid.uuid4(),
        "other_project": uuid.uuid4(),
        "report_a": uuid.uuid4(),
        "report_b": uuid.uuid4(),
        "report_c": uuid.uuid4(),
        "report_d": uuid.uuid4(),
        "other_report": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="review-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                User(
                    id=ids["reviewer"],
                    email="internal-reviewer@example.com",
                    password_hash="x",
                    name="Reviewer",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="Review WS",
                    slug="review-ws",
                    owner_id=ids["owner"],
                ),
                Workspace(
                    id=ids["other_workspace"],
                    name="Other Review WS",
                    slug="other-review-ws",
                    owner_id=ids["owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["owner"], role="owner"
                ),
                Project(
                    id=ids["project_a"],
                    workspace_id=ids["workspace"],
                    name="Review Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                Project(
                    id=ids["other_project"],
                    workspace_id=ids["other_workspace"],
                    name="Other Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                Report(
                    id=ids["report_a"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project_a"],
                    report_type="market",
                    title="Report A",
                    content="{}",
                    status="generated",
                    period_start=now - timedelta(days=7),
                    period_end=now,
                ),
                Report(
                    id=ids["report_b"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project_a"],
                    report_type="market",
                    title="Report B",
                    content="{}",
                    status="generated",
                    period_start=now - timedelta(days=7),
                    period_end=now,
                ),
                Report(
                    id=ids["report_c"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project_a"],
                    report_type="market",
                    title="Report C",
                    content="{}",
                    status="generated",
                    period_start=now - timedelta(days=7),
                    period_end=now,
                ),
                Report(
                    id=ids["report_d"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project_a"],
                    report_type="market",
                    title="Report D",
                    content="{}",
                    status="generated",
                    period_start=now - timedelta(days=7),
                    period_end=now,
                ),
                Report(
                    id=ids["other_report"],
                    workspace_id=ids["other_workspace"],
                    project_id=ids["other_project"],
                    report_type="market",
                    title="Other Report",
                    content="{}",
                    status="generated",
                    period_start=now - timedelta(days=7),
                    period_end=now,
                ),
            ]
        )
        await session.commit()
        await session.execute(
            insert(REVIEWER_ASSIGNMENTS).values(
                [
                    {
                        "id": uuid.uuid4(),
                        "workspace_id": ids["workspace"],
                        "project_id": ids["project_a"],
                        "report_id": ids["report_a"],
                        "reviewer_user_id": ids["reviewer"],
                        "assignment_scope": "report_read",
                        "status": "active",
                        "assigned_by": ids["owner"],
                        "assigned_at": now,
                        "expires_at": now + timedelta(hours=1),
                        "revoked_at": None,
                    },
                    {
                        "id": uuid.uuid4(),
                        "workspace_id": ids["workspace"],
                        "project_id": ids["project_a"],
                        "report_id": ids["report_b"],
                        "reviewer_user_id": ids["reviewer"],
                        "assignment_scope": "report_read",
                        "status": "revoked",
                        "assigned_by": ids["owner"],
                        "assigned_at": now,
                        "expires_at": now + timedelta(hours=1),
                        "revoked_at": now,
                    },
                    {
                        "id": uuid.uuid4(),
                        "workspace_id": ids["workspace"],
                        "project_id": ids["project_a"],
                        "report_id": ids["report_c"],
                        "reviewer_user_id": ids["reviewer"],
                        "assignment_scope": "report_read",
                        "status": "active",
                        "assigned_by": ids["owner"],
                        "assigned_at": now - timedelta(hours=2),
                        "expires_at": now - timedelta(hours=1),
                        "revoked_at": None,
                    },
                ]
            )
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


async def _reviewer(session: AsyncSession) -> User:
    reviewer = await session.get(User, _ids()["reviewer"])
    assert reviewer is not None
    return reviewer


async def _workspace(session: AsyncSession) -> Workspace:
    workspace = await session.get(Workspace, _ids()["workspace"])
    assert workspace is not None
    return workspace


@pytest.mark.asyncio
async def test_active_report_read_allows_report_claim_and_evidence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        kinds: tuple[ReviewerResourceKind, ...] = ("report", "claim", "evidence")
        for kind in kinds:
            access = await require_internal_reviewer_read(
                session,
                workspace=workspace,
                user=reviewer,
                report_id=_ids()["report_a"],
                resource_kind=kind,
            )
            assert access.project_id == _ids()["project_a"]
            assert access.assignment_scope == "report_read"
            assert access.resource_kind == kind
            assert not hasattr(access, "role")


@pytest.mark.asyncio
async def test_owner_without_assignment_is_denied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await _workspace(session)
        owner = await session.get(User, _ids()["owner"])
        assert owner is not None
        with pytest.raises(APIError) as denied:
            await require_internal_reviewer_read(
                session,
                workspace=workspace,
                user=owner,
                report_id=_ids()["report_a"],
                resource_kind="report",
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "reviewer_assignment_required"


@pytest.mark.asyncio
async def test_revoked_and_missing_assignments_are_denied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        for report_key in ("report_b", "report_d"):
            with pytest.raises(APIError) as denied:
                await require_internal_reviewer_read(
                    session,
                    workspace=workspace,
                    user=reviewer,
                    report_id=_ids()[report_key],
                    resource_kind="report",
                )
            assert denied.value.status_code == 403
            assert denied.value.code == "reviewer_assignment_required"


@pytest.mark.asyncio
async def test_expired_assignment_is_denied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        with pytest.raises(APIError) as denied:
            await require_internal_reviewer_read(
                session,
                workspace=workspace,
                user=reviewer,
                report_id=_ids()["report_c"],
                resource_kind="report",
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "reviewer_assignment_expired"


@pytest.mark.asyncio
async def test_cross_workspace_report_is_404(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        with pytest.raises(APIError) as missing:
            await require_internal_reviewer_read(
                session,
                workspace=workspace,
                user=reviewer,
                report_id=_ids()["other_report"],
                resource_kind="report",
            )
        assert missing.value.status_code == 404
        assert missing.value.code == "report_artifact_not_found"


@pytest.mark.asyncio
async def test_invalid_resource_kind_is_422(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        with pytest.raises(APIError) as invalid:
            await require_internal_reviewer_read(
                session,
                workspace=workspace,
                user=reviewer,
                report_id=_ids()["report_a"],
                resource_kind="dataset",  # type: ignore[arg-type]
            )
        assert invalid.value.status_code == 422
        assert invalid.value.code == "reviewer_assignment_invalid"
```

- [ ] **Step 12: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_internal_reviewer_access.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.repositories.reviewer_assignments'` 或 `ImportError: cannot import name 'require_internal_reviewer_read'`。

- [ ] **Step 13: 新增只读审阅者仓储**

Create `apps/api/src/data_intelligence_hub/repositories/reviewer_assignments.py`：

```python
"""内部审阅者只读仓储。

事实源是 C1 登记的 ``report_reviewer_assignments``，由 C9 迁移 065 创建。
本模块不建表、不写表、不导入 C9 的 ORM 模型；使用 Core table 只读查询，
避免 C2 在 C9 之前产生模型依赖。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import DateTime, String, Uuid, column, select, table
from sqlalchemy.ext.asyncio import AsyncSession

REVIEWER_ASSIGNMENTS = table(
    "report_reviewer_assignments",
    column("id", Uuid()),
    column("workspace_id", Uuid()),
    column("project_id", Uuid()),
    column("report_id", Uuid()),
    column("reviewer_user_id", Uuid()),
    column("assignment_scope", String(30)),
    column("status", String(20)),
    column("assigned_at", DateTime(timezone=True)),
    column("expires_at", DateTime(timezone=True)),
    column("revoked_at", DateTime(timezone=True)),
)


async def get_active_reviewer_assignment(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
) -> dict[str, Any] | None:
    result = await session.execute(
        select(REVIEWER_ASSIGNMENTS)
        .where(
            REVIEWER_ASSIGNMENTS.c.workspace_id == workspace_id,
            REVIEWER_ASSIGNMENTS.c.report_id == report_id,
            REVIEWER_ASSIGNMENTS.c.reviewer_user_id == reviewer_user_id,
            REVIEWER_ASSIGNMENTS.c.status == "active",
            REVIEWER_ASSIGNMENTS.c.revoked_at.is_(None),
        )
        .order_by(REVIEWER_ASSIGNMENTS.c.assigned_at.desc())
        .limit(1)
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None
```

- [ ] **Step 14: 在 `api/authz.py` 增加只读接缝**

在 `apps/api/src/data_intelligence_hub/api/authz.py` 顶部增加：

```python
from datetime import UTC, datetime
from typing import Literal

from data_intelligence_hub.repositories.reports import get_report
from data_intelligence_hub.repositories.reviewer_assignments import (
    get_active_reviewer_assignment,
)

ReviewerResourceKind = Literal["report", "claim", "evidence"]
REVIEWER_RESOURCE_KINDS = ("report", "claim", "evidence")
REVIEWER_READ_SCOPES = ("report_read", "report_review")


@dataclass(frozen=True)
class ReviewerReadAccess:
    assignment_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    report_id: uuid.UUID
    reviewer_user_id: uuid.UUID
    assignment_scope: str
    expires_at: datetime
    resource_kind: ReviewerResourceKind


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def require_internal_reviewer_read(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    report_id: uuid.UUID,
    resource_kind: ReviewerResourceKind,
    now: datetime | None = None,
) -> ReviewerReadAccess:
    """内部审阅者只读接缝。

    事实源是 C1 登记的 ``report_reviewer_assignments``。本函数不写该表，
    不返回工作区角色，不提供 manage 权限，也不受 WORKSPACE_RBAC_ENFORCED 影响。
    """
    if resource_kind not in REVIEWER_RESOURCE_KINDS:
        raise APIError(422, "reviewer_assignment_invalid")

    report = await get_report(session, workspace.id, report_id)
    if report is None:
        raise APIError(404, "report_artifact_not_found")

    assignment = await get_active_reviewer_assignment(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
        reviewer_user_id=user.id,
    )
    if assignment is None:
        raise APIError(403, "reviewer_assignment_required")

    project_id = assignment["project_id"]
    scope = assignment["assignment_scope"]
    if project_id is None or report.project_id != project_id:
        raise APIError(422, "reviewer_assignment_invalid")
    if scope not in REVIEWER_READ_SCOPES:
        raise APIError(422, "reviewer_assignment_invalid")

    expires_at = _as_utc(assignment["expires_at"])
    current = _as_utc(now) if now is not None else datetime.now(UTC)
    if expires_at <= current:
        raise APIError(
            403,
            "reviewer_assignment_expired",
            details={"assignment_id": str(assignment["id"])},
        )

    return ReviewerReadAccess(
        assignment_id=assignment["id"],
        workspace_id=assignment["workspace_id"],
        project_id=project_id,
        report_id=assignment["report_id"],
        reviewer_user_id=assignment["reviewer_user_id"],
        assignment_scope=scope,
        expires_at=expires_at,
        resource_kind=resource_kind,
    )
```

- [ ] **Step 15: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_internal_reviewer_access.py -v
```

Expected: 6 passed。owner 无指派也 403，证明审阅者接缝与工作区角色分离；跨工作区报告 404；到期 403 `reviewer_assignment_expired`。

- [ ] **Step 16: 为共享工作区建项目用例补角色**

Modify `apps/api/tests/unit/test_workspace_resolution.py:test_create_project_owner_is_requesting_user`。该用例原本让 `member` 在不是成员的 `shared_ws` 建项目；C2 要求 owner/admin 才能建项目。在该用例内补一条临时管理员成员行：

```python
    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        requesting_user = await session.get(User, _ids()["member"])
        assert shared_workspace is not None
        assert requesting_user is not None
        session.add(
            WorkspaceMember(
                workspace_id=shared_workspace.id,
                user_id=requesting_user.id,
                role="admin",
            )
        )
        await session.commit()
        response = await create_project_item(
            ProjectCreateRequest(name="Isolation Check", domain="mixed"),
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
        )
    assert response.owner_id == _ids()["member"]
```

Task 8 Step 8 会给同一调用补 `request_id` 参数。

- [ ] **Step 17: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_project_acl.py \
  tests/unit/test_internal_reviewer_access.py \
  tests/unit/test_project_api_key_routes.py \
  tests/unit/test_workspace_resolution.py \
  tests/integration/test_auth_projects.py \
  tests/integration/test_workflow_planner_preview.py -v
```

Expected: 全部 passed。`test_project_acl.py` 的 6 个用例与 `test_internal_reviewer_access.py` 的 6 个用例通过。项目密钥路由归 C3，本任务不改变既有 `project_api_key_routes` 行为。

- [ ] **Step 18: Commit**

```bash
git add apps/api/src/data_intelligence_hub/repositories/project_members.py \
  apps/api/src/data_intelligence_hub/repositories/reviewer_assignments.py \
  apps/api/src/data_intelligence_hub/api/authz.py \
  apps/api/src/data_intelligence_hub/repositories/projects.py \
  apps/api/src/data_intelligence_hub/services/project_service.py \
  apps/api/src/data_intelligence_hub/schemas/project.py \
  apps/api/src/data_intelligence_hub/api/routes/projects.py \
  apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py \
  apps/api/tests/unit/test_project_acl.py \
  apps/api/tests/unit/test_internal_reviewer_access.py \
  apps/api/tests/unit/test_workspace_resolution.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(acl): add project member and internal reviewer access seams"
```

---

### Task 6: 审计追加、哈希链与查询接口

**Files:**
- Create: `apps/api/src/data_intelligence_hub/repositories/audit_events.py`
- Create: `apps/api/src/data_intelligence_hub/services/audit_log.py`
- Create: `apps/api/src/data_intelligence_hub/schemas/audit.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/audit_events.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`（挂载路由）
- Test: `apps/api/tests/unit/test_audit_log.py`
- Test: `apps/api/tests/unit/test_audit_action_registry.py`

**Interfaces:**
- Consumes: `AuditEvent` 模型、`AUDIT_GENESIS_HASH`。
- Produces: `append_audit_event(session, *, workspace_id, project_id=None, actor_user_id=None, actor_type="user", action, resource_type, resource_id=None, request_id=None, result="success", details=None, occurred_at=None) -> AuditEvent`。
- Produces: `AUDIT_ACTION_OWNERS: dict[str, str]`、`AUDIT_ACTIONS: frozenset[str]`、`REQUIRED_AUDIT_ACTIONS: frozenset[str]`、`validate_audit_action(action: str) -> None`。
- Produces: `verify_audit_chain(events: Sequence[AuditEvent]) -> tuple[bool, int | None]`。
- Produces: `verify_audit_chain_segment(events, *, expected_prev=None) -> tuple[bool, int | None]`；保留清理删除链首后按首个留存事件的 `prev_hash` 校验。
- Produces: `record_authorization_denial(session, *, workspace_id, project_id, actor_user_id, action, resource_type, resource_id, request_id, code) -> None`。
- Produces: `GET /api/audit-events`、`GET /api/audit-events/verify`。
- Produces: `AuditVerificationResponse` 增加 `first_sequence_number` 与 `anchor_prev_hash`；这是附加字段，不改变既有 `valid`、`checked`、`first_invalid_sequence`。保留清理后按可用段校验。
- Rejects: 未登记动作抛 `ValueError("audit_action_unregistered")`；动作名格式非法抛 `ValueError("audit_action_invalid")`。下游切片不得自造动作名。

- [ ] **Step 1: 写失败的审计测试**

Create `apps/api/tests/unit/test_audit_log.py`:

```python
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.authz import require_workspace_role
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AUDIT_GENESIS_HASH
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.audit_events import list_audit_events
from data_intelligence_hub.services.audit_log import (
    append_audit_event,
    verify_audit_chain,
    verify_audit_chain_segment,
)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "owner": uuid.uuid4(),
        "member": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "other_workspace": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="audit-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                User(
                    id=ids["member"],
                    email="audit-member@example.com",
                    password_hash="x",
                    name="Member",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="Audit WS",
                    slug="audit-ws",
                    owner_id=ids["owner"],
                ),
                Workspace(
                    id=ids["other_workspace"],
                    name="Other Audit WS",
                    slug="other-audit-ws",
                    owner_id=ids["owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["owner"], role="owner"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["member"], role="member"
                ),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_append_builds_hash_chain_per_workspace(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await append_audit_event(
            session,
            workspace_id=_ids()["workspace"],
            actor_user_id=_ids()["owner"],
            action="project.created",
            resource_type="project",
            resource_id=str(uuid.uuid4()),
            request_id="req-1",
        )
        second = await append_audit_event(
            session,
            workspace_id=_ids()["workspace"],
            actor_user_id=_ids()["owner"],
            action="project.member.added",
            resource_type="project_member",
            resource_id=str(uuid.uuid4()),
            request_id="req-2",
        )
        await session.commit()

    async with session_factory() as session:
        events = await list_audit_events(
            session, _ids()["workspace"], limit=10, ascending=True
        )
    assert [event.sequence_number for event in events] == [1, 2]
    assert events[0].prev_hash == AUDIT_GENESIS_HASH
    assert events[1].prev_hash == events[0].event_hash
    valid, invalid = verify_audit_chain(events)
    assert valid is True
    assert invalid is None


@pytest.mark.asyncio
async def test_second_workspace_starts_a_new_chain(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await append_audit_event(
            session,
            workspace_id=_ids()["workspace"],
            action="workspace.member.added",
            resource_type="workspace_member",
        )
        await append_audit_event(
            session,
            workspace_id=_ids()["other_workspace"],
            action="workspace.member.added",
            resource_type="workspace_member",
        )
        await session.commit()

    async with session_factory() as session:
        other = await list_audit_events(
            session, _ids()["other_workspace"], limit=10, ascending=True
        )
    assert len(other) == 1
    assert other[0].sequence_number == 1
    assert other[0].prev_hash == AUDIT_GENESIS_HASH


@pytest.mark.asyncio
async def test_tampered_event_breaks_the_chain(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        for index in range(3):
            await append_audit_event(
                session,
                workspace_id=_ids()["workspace"],
                action=("project.created", "project.updated", "project.archived")[index],
                resource_type="test",
            )
        await session.commit()

    async with session_factory() as session:
        events = await list_audit_events(
            session, _ids()["workspace"], limit=10, ascending=True
        )
        events[1].action = "tampered"
        await session.commit()

    async with session_factory() as session:
        events = await list_audit_events(
            session, _ids()["workspace"], limit=10, ascending=True
        )
    valid, invalid = verify_audit_chain(events)
    assert valid is False
    assert invalid == 2


@pytest.mark.asyncio
async def test_segment_verification_survives_retention_trim(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        for index in range(3):
            await append_audit_event(
                session,
                workspace_id=_ids()["workspace"],
                action=("project.created", "project.updated", "project.archived")[index],
                resource_type="test",
            )
        await session.commit()

    async with session_factory() as session:
        events = await list_audit_events(
            session, _ids()["workspace"], limit=10, ascending=True
        )
        await session.delete(events[0])
        await session.commit()

    async with session_factory() as session:
        events = await list_audit_events(
            session, _ids()["workspace"], limit=10, ascending=True
        )
    assert [event.sequence_number for event in events] == [2, 3]
    full_valid, first_invalid = verify_audit_chain(events)
    assert full_valid is False
    assert first_invalid == 2
    segment_valid, segment_invalid = verify_audit_chain_segment(events)
    assert segment_valid is True
    assert segment_invalid is None


@pytest.mark.asyncio
async def test_forbidden_detail_keys_are_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="audit_detail_forbidden"):
            await append_audit_event(
                session,
                workspace_id=_ids()["workspace"],
                action="project.created",
                resource_type="test",
                details={"password": "never-store"},
            )


@pytest.mark.asyncio
async def test_member_filter_is_enforced_by_route_dependency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        member = await session.get(User, _ids()["member"])
        workspace = await session.get(Workspace, _ids()["workspace"])
        assert member is not None and workspace is not None
        role = await require_workspace_role(
            session,
            workspace=workspace,
            user=member,
            allowed=("owner", "admin", "member"),
        )
        assert role == "member"
        with pytest.raises(APIError) as denied:
            await require_workspace_role(
                session,
                workspace=workspace,
                user=member,
                allowed=("owner", "admin"),
            )
        assert denied.value.status_code == 403
        assert denied.value.code == "workspace_role_forbidden"


@pytest.mark.asyncio
async def test_actor_filter_returns_only_member_events(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await append_audit_event(
            session,
            workspace_id=_ids()["workspace"],
            actor_user_id=_ids()["owner"],
            action="project.created",
            resource_type="project",
        )
        await append_audit_event(
            session,
            workspace_id=_ids()["workspace"],
            actor_user_id=_ids()["member"],
            action="project.updated",
            resource_type="project",
        )
        await session.commit()

    async with session_factory() as session:
        rows = await list_audit_events(
            session,
            _ids()["workspace"],
            actor_user_id=_ids()["member"],
            limit=50,
        )
    assert [row.action for row in rows] == ["project.viewed"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_audit_log.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.services.audit_log'`。

- [ ] **Step 3: 审计仓储**

Create `apps/api/src/data_intelligence_hub/repositories/audit_events.py`:

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.audit_event import AuditEvent


async def get_last_audit_event(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> AuditEvent | None:
    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.sequence_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add_audit_event(
    session: AsyncSession,
    event: AuditEvent,
) -> AuditEvent:
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def list_audit_events(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    limit: int = 50,
    before_sequence: int | None = None,
    after_sequence: int | None = None,
    ascending: bool = False,
) -> list[AuditEvent]:
    statement = select(AuditEvent).where(AuditEvent.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(AuditEvent.project_id == project_id)
    if actor_user_id is not None:
        statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
    if before_sequence is not None:
        statement = statement.where(AuditEvent.sequence_number < before_sequence)
    if after_sequence is not None:
        statement = statement.where(AuditEvent.sequence_number > after_sequence)
    order = (
        AuditEvent.sequence_number.asc()
        if ascending
        else AuditEvent.sequence_number.desc()
    )
    result = await session.execute(statement.order_by(order).limit(limit))
    return list(result.scalars().all())
```

- [ ] **Step 4: 审计服务**

Create `apps/api/src/data_intelligence_hub/services/audit_log.py`:

```python
"""追加式审计与 SHA-256 哈希链。

链按 workspace_id 串行。PostgreSQL 下先锁工作区行，再读最后一条事件。
审计写入失败时异常向外传播，调用方事务整体回滚。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.audit_event import (
    AUDIT_GENESIS_HASH,
    AuditEvent,
)
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.audit_events import (
    add_audit_event,
    get_last_audit_event,
)

# 统一审计动作注册表。C1 契约文档必须登记同名动作。
# 每个动作只有一个写入 owner；下游切片只调用 append_audit_event，
# 不得自造动作名，也不得新增第二张审计表。
AUDIT_ACTION_OWNERS: dict[str, str] = {
    # C2：身份、项目 ACL、登录会话、内部审阅者访问
    "auth.login.succeeded": "C2",
    "auth.login.failed": "C2",
    "auth.logout.succeeded": "C2",
    "workspace.member.added": "C2",
    "workspace.member.role_changed": "C2",
    "workspace.member.removed": "C2",
    "project.created": "C2",
    "project.updated": "C2",
    "project.archived": "C2",
    "project.member.added": "C2",
    "project.member.removed": "C2",
    "project.access.denied": "C2",
    "project.management.denied": "C2",
    "reviewer.access.granted": "C2",
    "reviewer.access.denied": "C2",
    "config.switch.changed": "C2",
    # C4：任务单创建与取消
    "task.created": "C4",
    "task.cancelled": "C4",
    # C5：价格、额度、预算阻断与释放
    "budget.price.changed": "C5",
    "budget.limit.changed": "C5",
    "budget.blocked": "C5",
    "budget.released": "C5",
    # C6：运行取消、重试与完成
    "task.retried": "C6",
    "run.cancelled": "C6",
    "run.completed": "C6",
    # C7：Claim 审核
    "claim.review.approved": "C7",
    "claim.review.rejected": "C7",
    # C8：数据集质量
    "dataset.quality.evaluated": "C8",
    # C9：报告审核与发布、审阅者分派
    "report.review.approved": "C9",
    "report.review.rejected": "C9",
    "report.published": "C9",
    "report.superseded": "C9",
    "reviewer.assignment.created": "C9",
    "reviewer.assignment.revoked": "C9",
    # C10：交付与公开投影
    "delivery.published": "C10",
    "delivery.downloaded": "C10",
    "delivery.projection.viewed": "C10",
    "delivery.tamper_detected": "C10",
    "delivery.superseded": "C10",
    # C11：伪名化、导出与保留
    "privacy.projection.applied": "C11",
    "dataset.export.created": "C11",
    "retention.cleanup.executed": "C11",
    "legal_hold.created": "C11",
    "legal_hold.released": "C11",
    # C12：删除、DSR 与隐私流
    "privacy.deletion.requested": "C12",
    "privacy.deletion.executed": "C12",
    "privacy.dsr.received": "C12",
}

AUDIT_ACTIONS: frozenset[str] = frozenset(AUDIT_ACTION_OWNERS)

# 任务要求必须覆盖的最小动作集。缺一项 C2 不允许合并。
REQUIRED_AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "auth.login.succeeded",
        "auth.login.failed",
        "auth.logout.succeeded",
        "task.created",
        "task.cancelled",
        "task.retried",
        "budget.price.changed",
        "budget.limit.changed",
        "budget.blocked",
        "claim.review.approved",
        "claim.review.rejected",
        "config.switch.changed",
        "delivery.published",
        "delivery.projection.viewed",
        "privacy.projection.applied",
    }
)


def validate_audit_action(action: str) -> None:
    """校验动作已登记且形状合法。

    未登记动作必须失败，不允许下游切片用任意字符串写审计。
    """
    if action not in AUDIT_ACTIONS:
        raise ValueError("audit_action_unregistered")
    if not action or len(action) > 80:
        raise ValueError("audit_action_invalid")
    parts = action.split(".")
    if len(parts) < 2:
        raise ValueError("audit_action_invalid")
    for part in parts:
        if not part or not part[0].islower():
            raise ValueError("audit_action_invalid")
        if any(
            not (character.islower() or character.isdigit() or character == "_")
            for character in part
        ):
            raise ValueError("audit_action_invalid")


FORBIDDEN_DETAIL_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "access_token",
        "authorization",
        "cookie",
        "secret",
        "salt",
        "key_hash",
    }
)


def _assert_safe_details(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_DETAIL_KEYS:
                raise ValueError("audit_detail_forbidden")
            _assert_safe_details(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_safe_details(item)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _as_utc(value: datetime) -> datetime:
    """SQLite 返回 naive datetime；按 UTC 解释，保证追加与校验使用同一字符串。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_event_hash(
    *,
    event_id: uuid.UUID,
    workspace_id: uuid.UUID,
    sequence_number: int,
    project_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str | None,
    result: str,
    details: dict[str, Any],
    occurred_at: datetime,
    prev_hash: str,
) -> str:
    payload = {
        "event_id": str(event_id),
        "workspace_id": str(workspace_id),
        "sequence_number": sequence_number,
        "project_id": str(project_id) if project_id is not None else None,
        "actor_user_id": str(actor_user_id) if actor_user_id is not None else None,
        "actor_type": actor_type,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "request_id": request_id,
        "result": result,
        "details": details,
        "occurred_at": _as_utc(occurred_at).isoformat(),
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


async def append_audit_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str = "user",
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    request_id: str | None = None,
    result: str = "success",
    details: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    validate_audit_action(action)
    if actor_type not in ("user", "system", "project_key"):
        raise ValueError("audit_actor_type_invalid")
    if result not in ("success", "denied", "failed"):
        raise ValueError("audit_result_invalid")
    safe_details = details or {}
    _assert_safe_details(safe_details)

    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            select(Workspace.id)
            .where(Workspace.id == workspace_id)
            .with_for_update()
        )

    last = await get_last_audit_event(session, workspace_id)
    sequence_number = 1 if last is None else last.sequence_number + 1
    prev_hash = AUDIT_GENESIS_HASH if last is None else last.event_hash
    event_id = uuid.uuid4()
    occurred = occurred_at or datetime.now(UTC)
    event_hash = compute_event_hash(
        event_id=event_id,
        workspace_id=workspace_id,
        sequence_number=sequence_number,
        project_id=project_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        result=result,
        details=safe_details,
        occurred_at=occurred,
        prev_hash=prev_hash,
    )
    event = AuditEvent(
        id=event_id,
        workspace_id=workspace_id,
        project_id=project_id,
        sequence_number=sequence_number,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        result=result,
        details=safe_details,
        prev_hash=prev_hash,
        event_hash=event_hash,
        occurred_at=occurred,
    )
    return await add_audit_event(session, event)


def verify_audit_chain_segment(
    events: Sequence[AuditEvent],
    *,
    expected_prev: str | None = None,
) -> tuple[bool, int | None]:
    """校验可用事件段。

    保留清理删除链首后，首个留存事件的 ``prev_hash`` 是锚点，不再是
    64 个 0。调用方不传 ``expected_prev`` 时使用首个事件的 ``prev_hash``。
    """

    if not events:
        return True, None
    anchor = expected_prev if expected_prev is not None else events[0].prev_hash
    expected = anchor
    for event in events:
        if event.prev_hash != expected:
            return False, event.sequence_number
        recomputed = compute_event_hash(
            event_id=event.id,
            workspace_id=event.workspace_id,
            sequence_number=event.sequence_number,
            project_id=event.project_id,
            actor_user_id=event.actor_user_id,
            actor_type=event.actor_type,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            request_id=event.request_id,
            result=event.result,
            details=event.details,
            occurred_at=event.occurred_at,
            prev_hash=event.prev_hash,
        )
        if recomputed != event.event_hash:
            return False, event.sequence_number
        expected = event.event_hash
    return True, None


def verify_audit_chain(
    events: Sequence[AuditEvent],
) -> tuple[bool, int | None]:
    return verify_audit_chain_segment(
        events,
        expected_prev=AUDIT_GENESIS_HASH,
    )


async def record_authorization_denial(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str | None,
    code: str,
) -> None:
    """记录授权拒绝（403/404/422）。调用点必须在业务写之前；本函数提交当前 session。"""
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        result="denied",
        details={"code": code},
    )
    await session.commit()
```

- [ ] **Step 5: 写统一审计动作注册表测试**

Create `apps/api/tests/unit/test_audit_action_registry.py`：

```python
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from data_intelligence_hub.services.audit_log import (
    AUDIT_ACTION_OWNERS,
    AUDIT_ACTIONS,
    REQUIRED_AUDIT_ACTIONS,
    validate_audit_action,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
SRC_ROOT = PROJECT_ROOT / "apps/api/src/data_intelligence_hub"
C2_SOURCES = (
    SRC_ROOT / "api/authz.py",
    SRC_ROOT / "api/routes/auth.py",
    SRC_ROOT / "api/routes/workspaces.py",
    SRC_ROOT / "api/routes/projects.py",
    SRC_ROOT / "services/workspace_service.py",
    SRC_ROOT / "services/project_service.py",
    SRC_ROOT / "services/audit_log.py",
)


def test_required_actions_are_registered() -> None:
    assert REQUIRED_AUDIT_ACTIONS <= AUDIT_ACTIONS


def test_action_names_are_canonical() -> None:
    for action in AUDIT_ACTIONS:
        validate_audit_action(action)
        assert len(action) <= 80
        assert action == action.lower()
        assert not action.startswith(".")
        assert not action.endswith(".")


def test_every_action_has_one_owner() -> None:
    assert set(AUDIT_ACTION_OWNERS) == AUDIT_ACTIONS
    assert all(owner.startswith("C") for owner in AUDIT_ACTION_OWNERS.values())


def test_c1_contract_lists_every_action() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    missing = sorted(action for action in AUDIT_ACTIONS if action not in text)
    assert not missing, f"audit actions missing from C1 contract: {missing}"


def test_c2_sources_only_emit_registered_actions() -> None:
    emitted: set[str] = set()
    for path in C2_SOURCES:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in {"append_audit_event", "record_authorization_denial"}:
                continue
            for keyword in node.keywords:
                if keyword.arg != "action":
                    continue
                if isinstance(keyword.value, ast.Constant) and isinstance(
                    keyword.value.value, str
                ):
                    emitted.add(keyword.value.value)
    assert emitted <= AUDIT_ACTIONS, f"unregistered actions: {sorted(emitted - AUDIT_ACTIONS)}"


def test_unregistered_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="audit_action_unregistered"):
        validate_audit_action("project.viewed")
```

- [ ] **Step 6: 审计 schema 与路由**

Create `apps/api/src/data_intelligence_hub/schemas/audit.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    sequence_number: int
    actor_user_id: uuid.UUID | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: str | None
    request_id: str | None
    result: str
    details: dict[str, Any]
    prev_hash: str
    event_hash: str
    occurred_at: datetime


class AuditVerificationResponse(BaseModel):
    valid: bool
    checked: int
    first_invalid_sequence: int | None
    first_sequence_number: int | None
    anchor_prev_hash: str | None
```

Create `apps/api/src/data_intelligence_hub/api/routes/audit_events.py`:

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from data_intelligence_hub.api.authz import require_workspace_role
from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_authenticated_context
from data_intelligence_hub.repositories.audit_events import list_audit_events
from data_intelligence_hub.schemas.audit import (
    AuditEventResponse,
    AuditVerificationResponse,
)
from data_intelligence_hub.services.audit_log import verify_audit_chain_segment

router = APIRouter(tags=["audit"])


@router.get("", response_model=list[AuditEventResponse])
async def list_audit_event_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    project_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_sequence: Annotated[int | None, Query(ge=1)] = None,
) -> list[AuditEventResponse]:
    role = await require_workspace_role(
        session,
        workspace=context.workspace,
        user=context.user,
        allowed=("owner", "admin", "member"),
    )
    actor_filter = context.user.id if role == "member" else None
    rows = await list_audit_events(
        session,
        context.workspace.id,
        project_id=project_id,
        actor_user_id=actor_filter,
        limit=limit,
        before_sequence=before_sequence,
    )
    return [AuditEventResponse.model_validate(row) for row in rows]


@router.get("/verify", response_model=AuditVerificationResponse)
async def verify_audit_event_chain(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> AuditVerificationResponse:
    await require_workspace_role(
        session,
        workspace=context.workspace,
        user=context.user,
        allowed=("owner", "admin"),
    )
    rows = await list_audit_events(
        session,
        context.workspace.id,
        limit=limit,
        ascending=True,
    )
    valid, invalid = verify_audit_chain_segment(rows)
    return AuditVerificationResponse(
        valid=valid,
        checked=len(rows),
        first_invalid_sequence=invalid,
        first_sequence_number=rows[0].sequence_number if rows else None,
        anchor_prev_hash=rows[0].prev_hash if rows else None,
    )
```

需要 `Depends` 导入：

```python
from fastapi import APIRouter, Depends, Query
```

- [ ] **Step 7: 挂载审计路由**

Modify `apps/api/src/data_intelligence_hub/main.py`:

```python
from data_intelligence_hub.api.routes.audit_events import router as audit_events_router
```

```python
    app.include_router(audit_events_router, prefix="/api/audit-events")
```

- [ ] **Step 8: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_audit_log.py \
  tests/unit/test_audit_action_registry.py \
  tests/unit/test_c2_migration_source.py -v
```

Expected: 全部 passed。哈希链测试 `valid=True`；篡改后 `first_invalid_sequence=2`；未登记动作被拒绝。

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/data_intelligence_hub/repositories/audit_events.py \
  apps/api/src/data_intelligence_hub/services/audit_log.py \
  apps/api/src/data_intelligence_hub/schemas/audit.py \
  apps/api/src/data_intelligence_hub/api/routes/audit_events.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/tests/unit/test_audit_log.py \
  apps/api/tests/unit/test_audit_action_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(audit): add append-only hash-chained audit events"
```

---

### Task 7: 每日审计链头导出（本地 JSON + 哈希与签名）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/audit_chain_head.py`
- Create: `apps/api/src/data_intelligence_hub/maintenance/audit_chain_head_export.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/.env.example`
- Test: `apps/api/tests/unit/test_audit_chain_head.py`

**Interfaces:**
- Consumes: `AuditEvent`、`list_audit_events(after_sequence=...)`、`verify_audit_chain_segment`、`Workspace`。
- Produces: `AUDIT_CHAIN_HEAD_SCHEMA_VERSION = "audit_chain_head.v1"`。
- Produces: `collect_audit_chain_heads(session: AsyncSession) -> list[AuditChainHead]`。
- Produces: `build_audit_chain_head_document(heads, *, exported_at, hmac_key) -> dict[str, Any]`。
- Produces: `export_audit_chain_heads(session, *, output_dir: Path, hmac_key: str | None, exported_at: datetime | None = None) -> Path`。
- Produces: `verify_audit_chain_head_document(document, *, hmac_key: str | None) -> bool`。
- Produces: CLI `python -m data_intelligence_hub.maintenance.audit_chain_head_export`。
- Produces: `<output_dir>/audit-chain-head-YYYY-MM-DD.json`，权限 `0600`；文件只含工作区 ID、序号、哈希、计数和时间，不含事件正文。每个 head 含 `first_sequence_number`、`sequence_number`、`anchor_prev_hash`、`event_hash`、`prev_hash`、`event_count`、`last_occurred_at`。
- 边界：不建表，不写数据库，不上传外部存储。C2 不新增第三张表；本任务只读既有 `audit_events` 与 `workspaces`。本任务不新增 HTTP 路径、表、列或枚举；`audit_chain_head.v1` 是文件格式版本，不是数据库契约对象。段校验只证明当前留存段内部一致；全局不可篡改证明依赖 O0 WORM 中的每日链头。每日调度由运维 cron 执行；C2 只在共享 compose 增加链头目录与 HMAC 密钥映射，不修改 cron、systemd 或部署。O0 读取该文件后上传 WORM。

- [ ] **Step 1: 写失败的链头测试**

Create `apps/api/tests/unit/test_audit_chain_head.py`:

```python
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base, User, Workspace, WorkspaceMember
from data_intelligence_hub.models.audit_event import (
    AUDIT_GENESIS_HASH,
    AuditEvent,
)
from data_intelligence_hub.repositories.audit_events import list_audit_events
from data_intelligence_hub.services.audit_chain_head import (
    AuditChainHeadInvalidError,
    AuditChainHeadKeyMissingError,
    export_audit_chain_heads,
    verify_audit_chain_head_document,
)
from data_intelligence_hub.services.audit_log import append_audit_event

HMAC_KEY = "c2-test-chain-head-key-0123456789abcdef"
EXPORTED_AT = datetime(2026, 10, 22, 1, 0, tzinfo=UTC)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email="chain-head@example.com",
            password_hash="x",
            name="Owner",
            status="active",
        )
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Chain Head WS",
            slug="chain-head-ws",
            owner_id=user.id,
        )
        session.add_all(
            [
                user,
                workspace,
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="owner",
                ),
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()


async def _seed_two_events(
    factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    async with factory() as session:
        workspace_id = (
            await session.execute(select(Workspace.id).limit(1))
        ).scalar_one()
        for index in range(2):
            await append_audit_event(
                session,
                workspace_id=workspace_id,
                action=("project.created", "project.updated")[index],
                resource_type="test",
            )
        await session.commit()
        return workspace_id


@pytest.mark.asyncio
async def test_export_writes_signed_document_with_heads(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    workspace_id = await _seed_two_events(session_factory)
    async with session_factory() as session:
        path = await export_audit_chain_heads(
            session,
            output_dir=tmp_path,
            hmac_key=HMAC_KEY,
            exported_at=EXPORTED_AT,
        )

    assert path.name == "audit-chain-head-2026-10-22.json"
    assert path.stat().st_mode & 0o777 == 0o600
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == "audit_chain_head.v1"
    assert len(document["document_sha256"]) == 64
    assert len(document["hmac_sha256"]) == 64
    assert verify_audit_chain_head_document(document, hmac_key=HMAC_KEY) is True
    heads = document["heads"]
    assert len(heads) == 1
    assert heads[0]["workspace_id"] == str(workspace_id)
    assert heads[0]["first_sequence_number"] == 1
    assert heads[0]["sequence_number"] == 2
    assert heads[0]["anchor_prev_hash"] == AUDIT_GENESIS_HASH
    assert heads[0]["event_count"] == 2


def test_verification_rejects_tampered_document() -> None:
    document = {
        "schema_version": "audit_chain_head.v1",
        "exported_at": "2026-10-22T01:00:00+00:00",
        "date": "2026-10-22",
        "heads": [],
        "document_sha256": "0" * 64,
        "hmac_sha256": "0" * 64,
    }
    assert verify_audit_chain_head_document(document, hmac_key=HMAC_KEY) is False
    document["heads"] = [{"workspace_id": str(uuid.uuid4())}]
    assert verify_audit_chain_head_document(document, hmac_key=HMAC_KEY) is False


@pytest.mark.asyncio
async def test_export_anchors_trimmed_chain_after_retention(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    workspace_id = await _seed_two_events(session_factory)
    async with session_factory() as session:
        events = await list_audit_events(
            session, workspace_id, limit=10, ascending=True
        )
        anchor = events[0].event_hash
        await session.delete(events[0])
        await session.commit()

    async with session_factory() as session:
        path = await export_audit_chain_heads(
            session,
            output_dir=tmp_path,
            hmac_key=HMAC_KEY,
            exported_at=EXPORTED_AT,
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    head = document["heads"][0]
    assert head["first_sequence_number"] == 2
    assert head["anchor_prev_hash"] == anchor
    assert head["sequence_number"] == 2
    assert verify_audit_chain_head_document(document, hmac_key=HMAC_KEY) is True


@pytest.mark.asyncio
async def test_missing_or_short_key_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        with pytest.raises(AuditChainHeadKeyMissingError):
            await export_audit_chain_heads(
                session, output_dir=tmp_path, hmac_key=None
            )
        with pytest.raises(AuditChainHeadKeyMissingError):
            await export_audit_chain_heads(
                session, output_dir=tmp_path, hmac_key="short"
            )
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.asyncio
async def test_invalid_chain_is_not_written(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_two_events(session_factory)
    async with session_factory() as session:
        event_id = (
            await session.execute(select(AuditEvent.id).limit(1))
        ).scalar_one()
        await session.execute(
            update(AuditEvent)
            .where(AuditEvent.id == event_id)
            .values(action="tampered")
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(AuditChainHeadInvalidError):
            await export_audit_chain_heads(
                session,
                output_dir=tmp_path,
                hmac_key=HMAC_KEY,
                exported_at=EXPORTED_AT,
            )
    assert not list(tmp_path.glob("*.json"))
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_audit_chain_head.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.services.audit_chain_head'`。

- [ ] **Step 3: 实现链头服务**

Create `apps/api/src/data_intelligence_hub/services/audit_chain_head.py`:

```python
"""每日审计链头导出。

只读取 audit_events，不建表，不写数据库，不上传外部存储。
输出文档包含每个工作区的链头、文档 SHA-256 与 HMAC-SHA256。
任何工作区链校验失败时拒绝写文件。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.audit_events import list_audit_events
from data_intelligence_hub.services.audit_log import verify_audit_chain_segment

AUDIT_CHAIN_HEAD_SCHEMA_VERSION = "audit_chain_head.v1"
AUDIT_CHAIN_HEAD_BATCH_SIZE = 1000
MIN_HMAC_KEY_BYTES = 32


class AuditChainHeadError(RuntimeError):
    pass


class AuditChainHeadKeyMissingError(AuditChainHeadError):
    pass


class AuditChainHeadInvalidError(AuditChainHeadError):
    pass


@dataclass(frozen=True)
class AuditChainHead:
    workspace_id: uuid.UUID
    first_sequence_number: int
    sequence_number: int
    anchor_prev_hash: str
    event_hash: str
    prev_hash: str
    event_count: int
    last_occurred_at: datetime


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _require_key(hmac_key: str | None) -> str:
    if not hmac_key or len(hmac_key.encode("utf-8")) < MIN_HMAC_KEY_BYTES:
        raise AuditChainHeadKeyMissingError("audit_chain_head_hmac_key_missing")
    return hmac_key


async def collect_audit_chain_heads(
    session: AsyncSession,
) -> list[AuditChainHead]:
    workspace_ids = list(
        (
            await session.execute(select(Workspace.id).order_by(Workspace.id))
        ).scalars()
    )
    heads: list[AuditChainHead] = []
    for workspace_id in workspace_ids:
        events: list[AuditEvent] = []
        after_sequence: int | None = None
        while True:
            batch = await list_audit_events(
                session,
                workspace_id,
                limit=AUDIT_CHAIN_HEAD_BATCH_SIZE,
                after_sequence=after_sequence,
                ascending=True,
            )
            if not batch:
                break
            events.extend(batch)
            after_sequence = batch[-1].sequence_number
        if not events:
            continue
        valid, invalid = verify_audit_chain_segment(events)
        if not valid:
            raise AuditChainHeadInvalidError(
                f"audit_chain_invalid:{workspace_id}:{invalid}"
            )
        first = events[0]
        last = events[-1]
        heads.append(
            AuditChainHead(
                workspace_id=workspace_id,
                first_sequence_number=first.sequence_number,
                sequence_number=last.sequence_number,
                anchor_prev_hash=first.prev_hash,
                event_hash=last.event_hash,
                prev_hash=last.prev_hash,
                event_count=len(events),
                last_occurred_at=last.occurred_at,
            )
        )
    return heads


def build_audit_chain_head_document(
    heads: Sequence[AuditChainHead],
    *,
    exported_at: datetime,
    hmac_key: str | None,
) -> dict[str, Any]:
    key = _require_key(hmac_key)
    exported = _as_utc(exported_at)
    payload: dict[str, Any] = {
        "schema_version": AUDIT_CHAIN_HEAD_SCHEMA_VERSION,
        "exported_at": exported.isoformat(),
        "date": exported.date().isoformat(),
        "heads": [
            {
                "workspace_id": str(head.workspace_id),
                "first_sequence_number": head.first_sequence_number,
                "sequence_number": head.sequence_number,
                "anchor_prev_hash": head.anchor_prev_hash,
                "event_hash": head.event_hash,
                "prev_hash": head.prev_hash,
                "event_count": head.event_count,
                "last_occurred_at": _as_utc(head.last_occurred_at).isoformat(),
            }
            for head in heads
        ],
    }
    document_sha256 = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return {
        **payload,
        "document_sha256": document_sha256,
        "hmac_sha256": hmac.new(
            key.encode("utf-8"),
            document_sha256.encode("ascii"),
            hashlib.sha256,
        ).hexdigest(),
    }


def verify_audit_chain_head_document(
    document: dict[str, Any],
    *,
    hmac_key: str | None,
) -> bool:
    key = _require_key(hmac_key)
    payload = {
        "schema_version": document.get("schema_version"),
        "exported_at": document.get("exported_at"),
        "date": document.get("date"),
        "heads": document.get("heads"),
    }
    expected_document = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(
        str(document.get("document_sha256", "")), expected_document
    ):
        return False
    expected_hmac = hmac.new(
        key.encode("utf-8"),
        expected_document.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(
        str(document.get("hmac_sha256", "")), expected_hmac
    )


async def export_audit_chain_heads(
    session: AsyncSession,
    *,
    output_dir: Path,
    hmac_key: str | None,
    exported_at: datetime | None = None,
) -> Path:
    _require_key(hmac_key)
    exported = exported_at or datetime.now(UTC)
    heads = await collect_audit_chain_heads(session)
    document = build_audit_chain_head_document(
        heads,
        exported_at=exported,
        hmac_key=hmac_key,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"audit-chain-head-{document['date']}.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    return path
```

- [ ] **Step 4: 增加配置与导出命令**

Modify `apps/api/src/data_intelligence_hub/core/config.py`，在 `workspace_rbac_enforced` 之后追加：

```python
    # 每日审计链头导出的本地目录与 HMAC 密钥。
    # 密钥至少 32 字节，由密钥管理注入；不得写入仓库或审计事件。
    audit_chain_head_dir: str = "var/audit-chain-heads"
    audit_chain_head_hmac_key: str | None = None
```

Modify `apps/api/.env.example`，追加：

```dotenv
# AUDIT_CHAIN_HEAD_DIR: 每日审计链头 JSON 的本地目录。
AUDIT_CHAIN_HEAD_DIR=var/audit-chain-heads
# AUDIT_CHAIN_HEAD_HMAC_KEY: 链头文档 HMAC-SHA256 密钥，至少 32 字节。
# 生产从密钥管理注入；留空时导出命令拒绝运行。
AUDIT_CHAIN_HEAD_HMAC_KEY=
```

Create `apps/api/src/data_intelligence_hub/maintenance/audit_chain_head_export.py`:

```python
"""导出每日审计链头。

只写本地文件，不上传外部存储。O0 负责把文件上传到 WORM/对象锁存储。
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services.audit_chain_head import (
    export_audit_chain_heads,
)


def _parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    output_dir = Path(args.output_dir or settings.audit_chain_head_dir)
    exported_at = _parse_date(args.date) if args.date else datetime.now(UTC)
    async with async_session_factory() as session:
        path = await export_audit_chain_heads(
            session,
            output_dir=output_dir,
            hmac_key=settings.audit_chain_head_hmac_key,
            exported_at=exported_at,
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "path": str(path),
                "document_sha256": document["document_sha256"],
                "hmac_sha256": document["hmac_sha256"],
                "workspaces": len(document["heads"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD，默认 UTC 当天")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行链头测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_audit_chain_head.py tests/unit/test_audit_log.py -v
```

Expected: 全部 passed。链头文件包含 1 个工作区、2 条事件；篡改文档校验为 `False`；篡改数据库事件时导出抛 `AuditChainHeadInvalidError` 且不写文件。

- [ ] **Step 6: 在一次性库跑导出命令**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
DATABASE_URL="$C2_TEST_DATABASE_URL" \
AUDIT_CHAIN_HEAD_HMAC_KEY="c2-local-chain-head-key-0123456789abcdef" \
uv run python -m data_intelligence_hub.maintenance.audit_chain_head_export \
  --output-dir tmp/c2-acceptance/audit-chain-heads \
  --date 2026-10-22
```

Expected: 输出一行 JSON，包含 `path`、64 位 `document_sha256`、64 位 `hmac_sha256` 与 `workspaces`；文件权限 `0600`；`git status --porcelain` 不包含 `var/` 或 `tmp/` 下的证明文件。生产 A 的 cron 输出目录固定为 `/opt/data-achieve-scrapy/app/var/audit-chain-heads`；O0 Task 13 从该目录读取。

- [ ] **Step 7: 静态检查、GitNexus 与 Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run ruff check src/data_intelligence_hub/services/audit_chain_head.py \
  src/data_intelligence_hub/maintenance/audit_chain_head_export.py \
  tests/unit/test_audit_chain_head.py
uv run mypy src/data_intelligence_hub/services/audit_chain_head.py \
  src/data_intelligence_hub/maintenance/audit_chain_head_export.py
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/audit_chain_head.py \
  apps/api/src/data_intelligence_hub/maintenance/audit_chain_head_export.py \
  apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/.env.example \
  apps/api/tests/unit/test_audit_chain_head.py
git commit -m "feat(audit): export daily signed audit chain heads"
```

---

### Task 7b: 共用 compose 的 RBAC 与审计链头配置事实

**Files:**
- Modify: `configs/deploy/scrapy/docker-compose.yml`（生产 A 与 B 共用）
- Test: `apps/api/tests/unit/test_deploy_c2_facts.py`

**Interfaces:**
- 生产 A/B 共用 `configs/deploy/scrapy/docker-compose.yml`；不修改 `configs/deploy/scrapy-new/**`。
- `api.environment` 新增 `WORKSPACE_RBAC_ENFORCED`、`AUDIT_CHAIN_HEAD_DIR`、`AUDIT_CHAIN_HEAD_HMAC_KEY` 三个映射。
- `WORKSPACE_RBAC_ENFORCED` 默认 `false`；`AUDIT_CHAIN_HEAD_DIR` 默认 `var/audit-chain-heads`（容器工作目录 `/app` 下即 `/app/var/audit-chain-heads`）；`AUDIT_CHAIN_HEAD_HMAC_KEY` 默认空，由密钥管理注入。
- 本任务只改共享 compose 映射与测试；不写 `.env.production`、不部署、不重启容器。宿主 cron 通过导出命令的 `--output-dir` 写 `/opt/data-achieve-scrapy/app/var/audit-chain-heads`；compose 映射只让容器内命令能读取同一组配置，不改变调度。生产发布由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_deploy_c2_facts.py`:

```python
"""共享生产 compose 的 C2 配置事实。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "configs/deploy/scrapy/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "apps/api/.env.example"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rbac_switch_is_off_by_default_in_shared_compose() -> None:
    text = _text(COMPOSE)
    assert "WORKSPACE_RBAC_ENFORCED: ${WORKSPACE_RBAC_ENFORCED:-false}" in text


def test_audit_chain_head_env_is_mapped() -> None:
    text = _text(COMPOSE)
    assert "AUDIT_CHAIN_HEAD_DIR: ${AUDIT_CHAIN_HEAD_DIR:-var/audit-chain-heads}" in text
    assert "AUDIT_CHAIN_HEAD_HMAC_KEY: ${AUDIT_CHAIN_HEAD_HMAC_KEY:-}" in text


def test_scrapy_new_is_not_used() -> None:
    assert "scrapy-new" not in _text(COMPOSE)


def test_env_example_documents_c2_keys() -> None:
    text = _text(ENV_EXAMPLE)
    for expected in (
        "WORKSPACE_RBAC_ENFORCED=false",
        "AUDIT_CHAIN_HEAD_DIR=var/audit-chain-heads",
        "AUDIT_CHAIN_HEAD_HMAC_KEY=",
    ):
        assert expected in text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_deploy_c2_facts.py -q
```

Expected: FAIL。共享 compose 尚未映射 C2 的三个键。

- [ ] **Step 3: 修改共享 compose**

在 `configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 中、`SCHEDULER_*` 之后追加：

```yaml
      # C2：默认关闭。PG0 发布批次在 C2 通过后由 .env.production 显式打开。
      WORKSPACE_RBAC_ENFORCED: ${WORKSPACE_RBAC_ENFORCED:-false}
      # 每日审计链头导出。目录只写本地；HMAC 密钥由密钥管理注入，留空时导出拒绝运行。
      AUDIT_CHAIN_HEAD_DIR: ${AUDIT_CHAIN_HEAD_DIR:-var/audit-chain-heads}
      AUDIT_CHAIN_HEAD_HMAC_KEY: ${AUDIT_CHAIN_HEAD_HMAC_KEY:-}
```

不要改 `edge`、网络、volume 或端口；不要新增 `scrapy-new` 分支。

- [ ] **Step 4: 校验 compose 与测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
docker compose -f configs/deploy/scrapy/docker-compose.yml config --quiet
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_deploy_c2_facts.py -q
```

Expected: `docker compose config` 退出码 0；4 passed。若本机缺少生产必填变量，只运行测试，并在 C14 的 A/B 环境执行 `config --quiet`。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add configs/deploy/scrapy/docker-compose.yml \
  apps/api/tests/unit/test_deploy_c2_facts.py
git commit -m "ops(auth): map C2 RBAC and audit chain head settings"
```

Expected: `detect-changes` 不含 `partial: true` / `truncated: true`；没有 `configs/deploy/scrapy-new/**` 改动。

---

### Task 8: 身份与 ACL 写操作接入审计

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/deps.py`（`RequestIdDep` 与 `get_optional_authenticated_context`）
- Modify: `apps/api/src/data_intelligence_hub/api/authz.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workspace_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/project_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/auth_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/auth.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/workspaces.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/projects.py`
- Modify: `apps/api/tests/unit/test_workspace_resolution.py`
- Modify: `apps/api/tests/unit/test_internal_reviewer_access.py`
- Test: `apps/api/tests/unit/test_acl_audit_integration.py`

**Interfaces:**
- Consumes: `append_audit_event`、`record_authorization_denial`、`AUDIT_ACTIONS`。
- Produces: `RequestIdDep = Annotated[str, Depends(get_request_id)]`。
- Produces: `OptionalAuthenticatedContextDep = Annotated[AuthContext | None, Depends(get_optional_authenticated_context)]`；仅用于登出审计，不改变受保护路由的 fail-closed 行为。
- Produces: `require_project_access_audited(session, *, context: AuthContext, project_id, manage, request_id) -> ProjectAccess`。
- Produces: `require_internal_reviewer_read_audited(session, *, context: AuthContext, report_id, resource_kind, request_id) -> ReviewerReadAccess`。
- Produces: 审计动作名 `auth.login.succeeded`、`auth.login.failed`、`auth.logout.succeeded`、`workspace.member.added`、`workspace.member.role_changed`、`workspace.member.removed`、`project.created`、`project.updated`、`project.archived`、`project.member.added`、`project.member.removed`、`project.access.denied`、`project.management.denied`、`reviewer.access.granted`、`reviewer.access.denied`。

- [ ] **Step 1: 写失败的审计接入测试**

先运行 impact：

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs impact "add_member" --direction upstream --repo .
node .gitnexus/run.cjs impact "update_project" --direction upstream --repo .
```

Create `apps/api/tests/unit/test_acl_audit_integration.py`:

```python
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.authz import require_project_access_audited
from data_intelligence_hub.api.deps import AuthContext
from data_intelligence_hub.api.routes.auth import login, logout
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.core.security import hash_password
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_member import ProjectMember
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.auth import LoginRequest
from data_intelligence_hub.services.workspace_service import update_member_role


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "owner": uuid.uuid4(),
        "member": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "project_a": uuid.uuid4(),
        "project_b": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="audit-acl-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                User(
                    id=ids["member"],
                    email="audit-acl-member@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Member",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="Audit ACL WS",
                    slug="audit-acl-ws",
                    owner_id=ids["owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["owner"], role="owner"
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"], user_id=ids["member"], role="member"
                ),
                Project(
                    id=ids["project_a"],
                    workspace_id=ids["workspace"],
                    name="A",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                Project(
                    id=ids["project_b"],
                    workspace_id=ids["workspace"],
                    name="B",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
            ]
        )
        await session.commit()
        session.add(
            ProjectMember(
                workspace_id=ids["workspace"],
                project_id=ids["project_a"],
                user_id=ids["member"],
                created_by_user_id=ids["owner"],
            )
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def reset_rbac_flag():
    settings = get_settings()
    original = settings.workspace_rbac_enforced
    yield
    settings.workspace_rbac_enforced = original


async def _context(
    session: AsyncSession, user_id: uuid.UUID
) -> AuthContext:
    user = await session.get(User, user_id)
    workspace = await session.get(Workspace, _ids()["workspace"])
    assert user is not None and workspace is not None
    return AuthContext(user=user, workspace=workspace)


@pytest.mark.asyncio
async def test_denied_project_access_writes_denied_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    get_settings().workspace_rbac_enforced = True
    async with session_factory() as session:
        context = await _context(session, _ids()["member"])
        with pytest.raises(APIError) as denied:
            await require_project_access_audited(
                session,
                context=context,
                project_id=_ids()["project_b"],
                manage=False,
                request_id="req-denied",
            )
        assert denied.value.status_code == 403

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.workspace_id == _ids()["workspace"],
                    AuditEvent.result == "denied",
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "project.access.denied"
    assert rows[0].details == {"code": "project_access_forbidden"}
    assert rows[0].request_id == "req-denied"


@pytest.mark.asyncio
async def test_role_change_writes_success_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await session.get(Workspace, _ids()["workspace"])
        assert workspace is not None
        await update_member_role(
            session,
            workspace=workspace,
            actor_user_id=_ids()["owner"],
            target_user_id=_ids()["member"],
            role="admin",
            request_id="req-role",
        )

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "workspace.member.role_changed"
                )
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["owner"]
    assert row.result == "success"
    assert row.details == {"old_role": "member", "new_role": "admin"}
    assert row.request_id == "req-role"


@pytest.mark.asyncio
async def test_login_success_writes_success_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await login(
            LoginRequest(
                email="audit-acl-member@example.com",
                password="strong-password",
            ),
            Response(),
            session,
            "req-login-ok",
        )

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "auth.login.succeeded")
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["member"]
    assert row.workspace_id == _ids()["workspace"]
    assert row.result == "success"
    assert row.request_id == "req-login-ok"


@pytest.mark.asyncio
async def test_failed_login_writes_failed_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(HTTPException) as failed:
            await login(
                LoginRequest(
                    email="audit-acl-member@example.com",
                    password="wrong-password",
                ),
                Response(),
                session,
                "req-login-failed",
            )
        assert failed.value.status_code == 401

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "auth.login.failed")
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["member"]
    assert row.workspace_id == _ids()["workspace"]
    assert row.result == "failed"
    assert row.request_id == "req-login-failed"
    assert row.details == {"reason": "invalid_credentials"}


@pytest.mark.asyncio
async def test_logout_writes_success_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["member"])
        await logout(Response(), session, context, "req-logout")

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "auth.logout.succeeded")
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["member"]
    assert row.workspace_id == _ids()["workspace"]
    assert row.result == "success"
    assert row.request_id == "req-logout"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_acl_audit_integration.py -v
```

Expected: FAIL，`ImportError: cannot import name 'require_project_access_audited'`。

- [ ] **Step 3: 增加请求 ID 依赖**

Modify `apps/api/src/data_intelligence_hub/api/deps.py`:

```python
from fastapi import Cookie, Depends, HTTPException, Request, status


async def get_request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return uuid.uuid4().hex


RequestIdDep = Annotated[str, Depends(get_request_id)]
```

- [ ] **Step 4: 增加带审计的授权包装**

Modify `apps/api/src/data_intelligence_hub/api/authz.py`:

```python
from data_intelligence_hub.api.deps import AuthContext
from data_intelligence_hub.services.audit_log import record_authorization_denial


async def require_project_access_audited(
    session: AsyncSession,
    *,
    context: AuthContext,
    project_id: uuid.UUID,
    manage: bool,
    request_id: str,
) -> ProjectAccess:
    try:
        return await require_project_access(
            session,
            workspace=context.workspace,
            user=context.user,
            project_id=project_id,
            manage=manage,
        )
    except APIError as exc:
        if exc.status_code == 403:
            await record_authorization_denial(
                session,
                workspace_id=context.workspace.id,
                project_id=project_id,
                actor_user_id=context.user.id,
                action=(
                    "project.management.denied" if manage else "project.access.denied"
                ),
                resource_type="project",
                resource_id=str(project_id),
                request_id=request_id,
                code=exc.code,
            )
        raise
```

- [ ] **Step 5: 增加内部审阅者访问审计包装**

在 `apps/api/src/data_intelligence_hub/api/authz.py` 增加：

```python
from data_intelligence_hub.services.audit_log import append_audit_event


async def require_internal_reviewer_read_audited(
    session: AsyncSession,
    *,
    context: AuthContext,
    report_id: uuid.UUID,
    resource_kind: ReviewerResourceKind,
    request_id: str,
) -> ReviewerReadAccess:
    """只读审阅者接缝的审计包装。

    拒绝写 reviewer.access.denied；通过写 reviewer.access.granted。
    审计提交发生在读取敏感内容之前；审计失败时读取不发生。
    """
    try:
        access = await require_internal_reviewer_read(
            session,
            workspace=context.workspace,
            user=context.user,
            report_id=report_id,
            resource_kind=resource_kind,
        )
    except APIError as exc:
        if exc.status_code in (403, 404, 422):
            await record_authorization_denial(
                session,
                workspace_id=context.workspace.id,
                project_id=None,
                actor_user_id=context.user.id,
                action="reviewer.access.denied",
                resource_type="report",
                resource_id=str(report_id),
                request_id=request_id,
                code=exc.code,
            )
        raise

    await append_audit_event(
        session,
        workspace_id=access.workspace_id,
        project_id=access.project_id,
        actor_user_id=context.user.id,
        action="reviewer.access.granted",
        resource_type=resource_kind,
        resource_id=str(report_id),
        request_id=request_id,
        result="success",
        details={
            "assignment_id": str(access.assignment_id),
            "scope": access.assignment_scope,
            "resource_kind": resource_kind,
        },
    )
    await session.commit()
    return access
```

同时 Modify `apps/api/tests/unit/test_internal_reviewer_access.py`：在导入区增加 `select`、`AuthContext`、`require_internal_reviewer_read_audited`、`AuditEvent`，并追加两个审计用例：

```python
@pytest.mark.asyncio
async def test_reviewer_access_granted_is_audited(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        access = await require_internal_reviewer_read_audited(
            session,
            context=AuthContext(user=reviewer, workspace=workspace),
            report_id=_ids()["report_a"],
            resource_kind="report",
            request_id="req-review-ok",
        )
        assignment_id = access.assignment_id

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "reviewer.access.granted"
                )
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["reviewer"]
    assert row.result == "success"
    assert row.request_id == "req-review-ok"
    assert row.details == {
        "assignment_id": str(assignment_id),
        "scope": "report_read",
        "resource_kind": "report",
    }


@pytest.mark.asyncio
async def test_reviewer_access_denied_is_audited(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        reviewer = await _reviewer(session)
        workspace = await _workspace(session)
        with pytest.raises(APIError):
            await require_internal_reviewer_read_audited(
                session,
                context=AuthContext(user=reviewer, workspace=workspace),
                report_id=_ids()["report_d"],
                resource_kind="report",
                request_id="req-review-denied",
            )

    async with session_factory() as session:
        row = (
            await session.execute(
                select(AuditEvent).where(
                    AuditEvent.action == "reviewer.access.denied"
                )
            )
        ).scalar_one()
    assert row.actor_user_id == _ids()["reviewer"]
    assert row.result == "denied"
    assert row.request_id == "req-review-denied"
    assert row.details == {"code": "reviewer_assignment_required"}
```

- [ ] **Step 6: 登录、失败登录与登出写审计**

Modify `apps/api/src/data_intelligence_hub/services/exceptions.py`：

```python
class InvalidCredentialsError(ServiceError):
    message = "Invalid email or password"

    def __init__(
        self,
        *,
        audit_workspace_id: uuid.UUID | None = None,
        audit_user_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(self.message)
        self.audit_workspace_id = audit_workspace_id
        self.audit_user_id = audit_user_id
```

文件顶部增加 `import uuid`。

Modify `apps/api/src/data_intelligence_hub/services/auth_service.py` 的 `login_user`：在密码校验失败且用户存在时，解析该用户的默认工作区并传给异常：

```python
    user = await get_user_by_email(session, str(payload.email))
    if user is None:
        raise InvalidCredentialsError()

    workspace = await get_default_workspace_for_user(
        session,
        user.id,
        prefer_demo=get_settings().effective_demo_mode,
    )
    if user.status != "active":
        raise InvalidCredentialsError(
            audit_workspace_id=workspace.id if workspace is not None else None,
            audit_user_id=user.id,
        )
    if not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError(
            audit_workspace_id=workspace.id if workspace is not None else None,
            audit_user_id=user.id,
        )
```

未注册邮箱没有工作区，无法写 `audit_events.workspace_id`；此时只写结构化应用日志 `auth_login_failed_unknown_email`，不伪造工作区链。

Modify `apps/api/src/data_intelligence_hub/api/deps.py`，增加可选认证上下文：

```python
async def get_optional_authenticated_context(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
    active_workspace_id: Annotated[str | None, Cookie(alias=WORKSPACE_COOKIE_NAME)] = None,
) -> AuthContext | None:
    if access_token is None:
        return None
    user_id = decode_access_token(access_token)
    if user_id is None:
        return None
    user = await get_user_by_id(session, user_id)
    if user is None or user.status != "active":
        return None
    workspace = await resolve_workspace_for_user(session, user.id, active_workspace_id)
    if workspace is None:
        return None
    return AuthContext(user=user, workspace=workspace)


OptionalAuthenticatedContextDep = Annotated[
    AuthContext | None, Depends(get_optional_authenticated_context)
]
```

Modify `apps/api/src/data_intelligence_hub/api/routes/auth.py`：

```python
from data_intelligence_hub.api.deps import (
    OptionalAuthenticatedContextDep,
    RequestIdDep,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.auth_service import (
    AuthSession,
    login_user,
    register_user,
)
```

登录成功：

```python
    await append_audit_event(
        session,
        workspace_id=auth_session.workspace.id,
        actor_user_id=auth_session.user.id,
        action="auth.login.succeeded",
        resource_type="session",
        request_id=request_id,
        result="success",
        details={"method": "password"},
    )
    await session.commit()
```

失败登录：

```python
    except InvalidCredentialsError as exc:
        if exc.audit_workspace_id is not None and exc.audit_user_id is not None:
            await append_audit_event(
                session,
                workspace_id=exc.audit_workspace_id,
                actor_user_id=exc.audit_user_id,
                action="auth.login.failed",
                resource_type="session",
                request_id=request_id,
                result="failed",
                details={"reason": "invalid_credentials"},
            )
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=InvalidCredentialsError.message,
        ) from exc
```

登出：

```python
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    context: OptionalAuthenticatedContextDep,
    request_id: RequestIdDep,
) -> Response:
    if context is not None:
        await append_audit_event(
            session,
            workspace_id=context.workspace.id,
            actor_user_id=context.user.id,
            action="auth.logout.succeeded",
            resource_type="session",
            request_id=request_id,
            result="success",
            details={},
        )
        await session.commit()
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    response.delete_cookie(key=WORKSPACE_COOKIE_NAME, path="/")
    return response
```

登录与登出路由签名增加 `request_id: RequestIdDep`。登出无有效会话时仍然 204，不写审计，不清除失败；不得把登出改成 401。

- [ ] **Step 7: 工作区服务写审计**

Modify `apps/api/src/data_intelligence_hub/services/workspace_service.py`:

```python
from data_intelligence_hub.services.audit_log import append_audit_event
```

`add_member`、`update_member_role`、`remove_member` 增加关键字参数 `request_id: str | None = None`，并在 `session.commit()` 之前追加：

```python
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        actor_user_id=actor_user_id,
        action="workspace.member.added",
        resource_type="workspace_member",
        resource_id=str(target_user_id),
        request_id=request_id,
        details={"role": role},
    )
```

`update_member_role` 在设置 `member.role` 之前记录旧值，提交前追加：

```python
    old_role = current_role
    member.role = role
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        actor_user_id=actor_user_id,
        action="workspace.member.role_changed",
        resource_type="workspace_member",
        resource_id=str(target_user_id),
        request_id=request_id,
        details={"old_role": old_role, "new_role": role},
    )
    await session.commit()
```

`remove_member` 在删除前追加：

```python
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        actor_user_id=actor_user_id,
        action="workspace.member.removed",
        resource_type="workspace_member",
        resource_id=str(target_user_id),
        request_id=request_id,
        details={"role": member.role},
    )
```

- [ ] **Step 8: 项目服务写审计**

Modify `apps/api/src/data_intelligence_hub/services/project_service.py`:

- 导入 `append_audit_event`。
- `create_project` 在 `await session.flush()` 后、`commit` 前追加：

```python
    session.add(project)
    await session.flush()
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        project_id=project.id,
        actor_user_id=user.id,
        action="project.created",
        resource_type="project",
        resource_id=str(project.id),
        request_id=request_id,
        details={"name": project.name, "domain": project.domain},
    )
    await session.commit()
```

- `update_project` 在 `commit` 前追加：

```python
    changed = sorted(updates.keys())
    await append_audit_event(
        session,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor_user_id=actor_user_id,
        action="project.updated",
        resource_type="project",
        resource_id=str(project.id),
        request_id=request_id,
        details={"changed": changed},
    )
    await session.commit()
```

- `archive_project` 在 `commit` 前追加：

```python
    await append_audit_event(
        session,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor_user_id=actor_user_id,
        action="project.archived",
        resource_type="project",
        resource_id=str(project.id),
        request_id=request_id,
        details={"status": "archived"},
    )
    await session.commit()
```

- 新增项目成员服务函数：

```python
from data_intelligence_hub.models.project_member import ProjectMember
from data_intelligence_hub.repositories.project_members import (
    add_project_member as add_project_member_row,
    remove_project_member as remove_project_member_row,
)


async def add_project_member(
    session: AsyncSession,
    *,
    workspace: Workspace,
    project: Project,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
) -> ProjectMember:
    member = await add_project_member_row(
        session,
        workspace_id=workspace.id,
        project_id=project.id,
        user_id=user_id,
        created_by_user_id=actor_user_id,
    )
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        project_id=project.id,
        actor_user_id=actor_user_id,
        action="project.member.added",
        resource_type="project_member",
        resource_id=str(user_id),
        request_id=request_id,
        details={"project_id": str(project.id)},
    )
    await session.commit()
    await session.refresh(member)
    return member


async def remove_project_member(
    session: AsyncSession,
    *,
    workspace: Workspace,
    project: Project,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
) -> bool:
    removed = await remove_project_member_row(
        session,
        workspace_id=workspace.id,
        project_id=project.id,
        user_id=user_id,
    )
    if not removed:
        return False
    await append_audit_event(
        session,
        workspace_id=workspace.id,
        project_id=project.id,
        actor_user_id=actor_user_id,
        action="project.member.removed",
        resource_type="project_member",
        resource_id=str(user_id),
        request_id=request_id,
        details={"project_id": str(project.id)},
    )
    await session.commit()
    return True
```

- [ ] **Step 9: 路由传入 request_id**

Modify `apps/api/src/data_intelligence_hub/api/routes/workspaces.py`:

```python
from data_intelligence_hub.api.deps import RequestIdDep

# add_current_workspace_member
async def add_current_workspace_member(
    payload: AddWorkspaceMemberRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> WorkspaceMemberResponse:
    # 其余代码不变
    member = await add_member(
        session,
        workspace=context.workspace,
        actor_user_id=context.user.id,
        target_user_id=user.id,
        role=payload.role,
        request_id=request_id,
    )

# update_current_workspace_member_role
async def update_current_workspace_member_role(
    user_id: uuid.UUID,
    payload: UpdateWorkspaceMemberRoleRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> WorkspaceMemberResponse:
    # 其余代码不变
    member = await update_member_role(
        session,
        workspace=context.workspace,
        actor_user_id=context.user.id,
        target_user_id=user_id,
        role=payload.role,
        request_id=request_id,
    )

# remove_current_workspace_member
async def remove_current_workspace_member(
    user_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    request_id: RequestIdDep,
) -> None:
    # 其余代码不变
    await remove_member(
        session,
        workspace=context.workspace,
        actor_user_id=context.user.id,
        target_user_id=user_id,
        request_id=request_id,
    )
```

Modify `apps/api/src/data_intelligence_hub/api/routes/projects.py`:

```python
from data_intelligence_hub.api.deps import RequestIdDep


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_item(
    payload: ProjectCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> ProjectResponse:
    await require_workspace_role(
        session,
        workspace=context.workspace,
        user=context.user,
        allowed=("owner", "admin"),
    )
    project = await create_project(
        session,
        context.user,
        context.workspace,
        payload,
        request_id=request_id,
    )
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> ProjectResponse:
    access = await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=False,
        request_id=request_id,
    )
    return ProjectResponse.model_validate(access.project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_item(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> ProjectResponse:
    access = await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=True,
        request_id=request_id,
    )
    project = await update_project(
        session,
        access.project,
        payload,
        actor_user_id=context.user.id,
        request_id=request_id,
    )
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=ProjectResponse)
async def archive_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> ProjectResponse:
    access = await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=True,
        request_id=request_id,
    )
    project = await archive_project(
        session,
        access.project,
        actor_user_id=context.user.id,
        request_id=request_id,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
)
async def list_project_member_items(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> list[ProjectMemberResponse]:
    await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=True,
        request_id=request_id,
    )
    rows = await list_project_members(session, context.workspace.id, project_id)
    return [
        ProjectMemberResponse(
            user=UserResponse.model_validate(user), added_at=member.created_at
        )
        for member, user in rows
    ]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member_item(
    project_id: uuid.UUID,
    payload: AddProjectMemberRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> ProjectMemberResponse:
    access = await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=True,
        request_id=request_id,
    )
    if not await user_belongs_to_workspace(
        session, payload.user_id, context.workspace.id
    ):
        raise APIError(404, "workspace_member_not_found")
    if await get_project_member(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        user_id=payload.user_id,
    ) is not None:
        raise APIError(409, "project_member_exists")
    member = await add_project_member(
        session,
        workspace=context.workspace,
        project=access.project,
        user_id=payload.user_id,
        actor_user_id=context.user.id,
        request_id=request_id,
    )
    user = await get_user_by_id(session, payload.user_id)
    if user is None:
        raise APIError(404, "workspace_member_not_found")
    return ProjectMemberResponse(
        user=UserResponse.model_validate(user), added_at=member.created_at
    )


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member_item(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    request_id: RequestIdDep,
) -> None:
    access = await require_project_access_audited(
        session,
        context=context,
        project_id=project_id,
        manage=True,
        request_id=request_id,
    )
    removed = await remove_project_member(
        session,
        workspace=context.workspace,
        project=access.project,
        user_id=user_id,
        actor_user_id=context.user.id,
        request_id=request_id,
    )
    if not removed:
        raise APIError(404, "project_member_not_found")
```

`projects.py` 需要从 `api.authz` 导入 `require_project_access_audited`，并删除不再使用的 `require_project_access` 导入。项目成员路由导入 `add_project_member` 与 `remove_project_member` 的新 service 版本，而不是 repository 版本；`get_project_member`、`list_project_members`、`user_belongs_to_workspace` 仍从 repository 导入。

- [ ] **Step 10: 更新直接调用路由的测试**

Modify `apps/api/tests/unit/test_workspace_resolution.py`。直接调用路由函数时必须传 `request_id`：

```python
        response = await create_project_item(
            ProjectCreateRequest(name="Isolation Check", domain="mixed"),
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
            "test-request",
        )
```

```python
        await create_project_item(
            ProjectCreateRequest(name="Tenant Scoped", domain="mixed"),
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
            "test-request",
        )
```

```python
            await add_current_workspace_member(
                AddWorkspaceMemberRequest(email="shared-owner@example.com"),
                session,
                AuthContext(user=requesting_user, workspace=shared_workspace),
                "test-request",
            )
```

```python
        added = await add_current_workspace_member(
            AddWorkspaceMemberRequest(email="member@example.com"),
            session,
            context,
            "test-request",
        )
        assert added.user.email == "member@example.com"
        await remove_current_workspace_member(
            _ids()["member"], session, context, "test-request"
        )
```

```python
        await add_current_workspace_member(
            AddWorkspaceMemberRequest(email="member@example.com"),
            session,
            AuthContext(user=owner, workspace=shared_workspace),
            "test-request",
        )
```

```python
        await remove_current_workspace_member(
            _ids()["member"],
            fresh,
            AuthContext(user=owner, workspace=shared_workspace),
            "test-request",
        )
```

```python
            await remove_current_workspace_member(
                owner.id,
                session,
                AuthContext(user=owner, workspace=shared_workspace),
                "test-request",
            )
```

- [ ] **Step 11: 运行测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest tests/unit/test_acl_audit_integration.py \
  tests/unit/test_internal_reviewer_access.py \
  tests/unit/test_workspace_roles.py \
  tests/unit/test_project_acl.py \
  tests/unit/test_audit_log.py \
  tests/unit/test_audit_action_registry.py \
  tests/unit/test_workspace_resolution.py -v
```

Expected: 全部 passed。拒绝访问后新 session 能读到 `result='denied'` 的审计行；登录成功、失败登录与登出各写一条对应动作。

- [ ] **Step 12: Commit**

```bash
git add apps/api/src/data_intelligence_hub/api/deps.py \
  apps/api/src/data_intelligence_hub/api/authz.py \
  apps/api/src/data_intelligence_hub/services/workspace_service.py \
  apps/api/src/data_intelligence_hub/services/project_service.py \
  apps/api/src/data_intelligence_hub/services/auth_service.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/src/data_intelligence_hub/api/routes/auth.py \
  apps/api/src/data_intelligence_hub/api/routes/workspaces.py \
  apps/api/src/data_intelligence_hub/api/routes/projects.py \
  apps/api/tests/unit/test_workspace_resolution.py \
  apps/api/tests/unit/test_internal_reviewer_access.py \
  apps/api/tests/unit/test_acl_audit_integration.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(audit): record identity session and ACL changes"
```

---

### Task 9: 下游交接（C4-C12 契约与 C14 控制台）

C2 不改 `apps/scraper-console/**`，也不改 C4-C12 的文件。本任务交付两份交接文档：C4-C12 的项目 ACL/审计动作契约，以及 C14 `/settings` 内联成员面板的行为、选择器与浏览器判据。

**Files:**
- Create: `docs/ops/c2-c12-downstream-handoff.md`
- Create: `docs/ops/c2-c14-members-handoff.md`
- No console or e2e changes.

**Interfaces:**
- Consumes: `require_project_access`、`require_project_access_audited`、`AUDIT_ACTIONS`、`AuthSessionResponse.role`、`WorkspaceMember.role`。
- Produces: C4-C12 可直接执行的接入表、403/404 测试模板与审计动作 owner 表。
- Produces: C14 可直接执行的页面行为清单与浏览器验收矩阵。

- [ ] **Step 1: 写 C4-C12 下游交接文档**

```bash
mkdir -p docs/ops
```

Create `docs/ops/c2-c12-downstream-handoff.md`:

````markdown
# C2 → C4-C12 项目 ACL 与审计动作交接

C2 不修改 C4-C12 的文件。下游切片按本文件接入；C2 的合并门禁只检查本文件存在且 `test_audit_action_registry.py` 通过。

## 1. 唯一项目授权接缝

```python
from data_intelligence_hub.api.authz import require_project_access_audited

access = await require_project_access_audited(
    session,
    context=context,
    project_id=resolved_project_id,
    manage=<bool>,
    request_id=request_id,
)
```

规则：

1. `project_id` 来自路径、查询或按 `workspace_id` 加载的资源行；不得只信任请求体。
2. 项目级读 `manage=False`；写 `manage=True`。
3. owner/admin 全项目通过；member 只读 `project_members` 项目；member 写 403 `project_management_forbidden`。
4. 跨工作区 404 `project_not_found`；同工作区未授权读 403 `project_access_forbidden`。
5. 路由不得直接比较 `workspace.owner_id` 或角色；service 不导入 `api.authz`。
6. `WORKSPACE_RBAC_ENFORCED=false` 只回退 member 可见性；审计不回退。

## 2. 逐切片接入表

| 切片 | 路由/服务 | `project_id` 来源 | `manage` |
|---|---|---|---|
| C3 | `POST/GET/DELETE /api/projects/{project_id}/api-keys*` | 路径 | 写 `True`，读 `False` |
| C4 | `POST/GET /api/workbench/tasks`；`GET/PATCH /api/workbench/tasks/{task_id}`；`GET /api/workbench/tasks/{task_id}/gates`；`POST /api/runs` | 查询；`task.project_id`；提交载荷 | 创建/更新 `True`；读 `False` |
| C5 | `GET /api/quota/projects/{project_id}`；`budget_service` 项目级写 | 路径；`run.project_id` | 读 `False`；预算写 `True` |
| C6 | `POST /api/runs/{run_id}/cancel`；取消/重试执行器入口 | `run.project_id` | `True` |
| C7 | `GET /api/claims`；`GET /api/claims/{claim_id}`；Claim 审核写 | 查询；`claim.project_id` | 读 `False`；审核 `True` |
| C8 | `POST /api/automation/product-dataset-save`；质量评估入口 | 载荷；`run.project_id` | 保存 `True`；质量读 `False` |
| C9 | `GET /api/reports/{report_id}/contract`、`artifact`、`revisions`、`sop`；`POST /reviews`；`POST /publish` | `report.project_id` | 读 `False`；审核/发布 `True` |
| C10 | `POST/GET /api/reports/{artifact_id}/delivery*` | `artifact.project_id` | 发布 `True`；读/下载 `False` |
| C11 | `POST/GET /api/automation/product-dataset-exports*`；导出服务入口 | 载荷/行 `dataset.project_id` | 创建 `True`；读/导出 `False` |
| C12 | `POST /api/privacy/deletion-requests` 的 `target_type='project'`；项目删除 | 载荷；`request.target_id` | `True` |

## 3. 每个切片必须实现的 403/404 测试

```python
denied = await client.get(member_client, url_project_b)
assert denied.status_code == 403
assert denied.json()["error"]["code"] == "project_access_forbidden"

missing = await client.get(member_client, url_other_workspace_project)
assert missing.status_code == 404
assert missing.json()["error"]["code"] == "project_not_found"

write_denied = await client.write(member_client, write_url_project_b)
assert write_denied.status_code == 403
assert write_denied.json()["error"]["code"] == "project_management_forbidden"
```

每个切片还必须断言：owner/admin 对同一项目读 200、写 200；member 对已授权项目 A 读 200、写 403；开关关闭时 member 可读项目 B；拒绝后存在 `project.access.denied` 或 `project.management.denied` 审计行。

## 4. 审计动作 owner 表

| 动作 | owner | 调用点 |
|---|---|---|
| `auth.login.succeeded` | C2 | `api/routes/auth.py` 登录成功 |
| `auth.login.failed` | C2 | `api/routes/auth.py` 失败登录 |
| `auth.logout.succeeded` | C2 | `api/routes/auth.py` 登出 |
| `workspace.member.added` | C2 | `services/workspace_service.py` |
| `workspace.member.role_changed` | C2 | `services/workspace_service.py` |
| `workspace.member.removed` | C2 | `services/workspace_service.py` |
| `project.created` | C2 | `services/project_service.py` |
| `project.updated` | C2 | `services/project_service.py` |
| `project.archived` | C2 | `services/project_service.py` |
| `project.member.added` | C2 | `services/project_service.py` |
| `project.member.removed` | C2 | `services/project_service.py` |
| `project.access.denied` | C2 | `api/authz.py` 审计包装 |
| `project.management.denied` | C2 | `api/authz.py` 审计包装 |
| `reviewer.access.granted` | C2 | `api/authz.py` 审阅者审计包装 |
| `reviewer.access.denied` | C2 | `api/authz.py` 审阅者审计包装 |
| `config.switch.changed` | C2 | 运行时开关变更；当前无写路径，PG0 批次记录 |
| `task.created` | C4 | 任务单创建 |
| `task.cancelled` | C4 | 任务单取消 |
| `budget.price.changed` | C5 | 价格簿变更 |
| `budget.limit.changed` | C5 | 额度/订单上限变更 |
| `budget.blocked` | C5 | 预算阻断 |
| `budget.released` | C5 | 预算释放 |
| `task.retried` | C6 | 任务重试 |
| `run.cancelled` | C6 | 运行取消 |
| `run.completed` | C6 | 运行完成 |
| `claim.review.approved` | C7 | Claim 审核通过 |
| `claim.review.rejected` | C7 | Claim 审核拒绝 |
| `dataset.quality.evaluated` | C8 | 质量评估完成 |
| `report.review.approved` | C9 | 报告审核通过 |
| `report.review.rejected` | C9 | 报告审核拒绝 |
| `report.published` | C9 | 报告发布 |
| `report.superseded` | C9 | 报告取代 |
| `reviewer.assignment.created` | C9 | 审阅者分派 |
| `reviewer.assignment.revoked` | C9 | 审阅者撤销 |
| `delivery.published` | C10 | 交付发布 |
| `delivery.downloaded` | C10 | 交付下载 |
| `delivery.projection.viewed` | C10 | 公开合同投影读取 |
| `delivery.tamper_detected` | C10 | 交付篡改 |
| `delivery.superseded` | C10 | 交付取代 |
| `privacy.projection.applied` | C11 | 导出遮蔽/伪名投影 |
| `dataset.export.created` | C11 | 数据集导出创建 |
| `retention.cleanup.executed` | C11 | 保留清理执行 |
| `legal_hold.created` | C11 | 法律保留创建 |
| `legal_hold.released` | C11 | 法律保留释放 |
| `privacy.deletion.requested` | C12 | 删除请求创建 |
| `privacy.deletion.executed` | C12 | 删除执行 |
| `privacy.dsr.received` | C12 | DSR 案件创建 |

下游只允许调用 `append_audit_event(action=<上表动作>)`。未登记动作会抛 `ValueError("audit_action_unregistered")`，不得 catch 后继续。

## 5. 快速检查

```bash
rg -n "workspace\.owner_id ==" apps/api/src/data_intelligence_hub/api/routes
rg -n "require_project_access" apps/api/src/data_intelligence_hub/api/routes
rg -n "append_audit_event" apps/api/src/data_intelligence_hub
```

第一条应只剩 `api/authz.py` 之外的零命中；第二条应覆盖上表全部项目级路由；第三条不得出现未登记动作字面量。

## 6. 发布门禁

C4-C12 的切片只有在各自 403/404 测试通过、审计动作已登记、且 `node .gitnexus/run.cjs detect-changes --scope all --repo .` 无 `partial: true` / `truncated: true` 时才允许进入 PG0 发布批次。C2 不代跑这些测试。
````

- [ ] **Step 2: 写 C14 交接文档**

```bash
mkdir -p docs/ops
```

Create `docs/ops/c2-c14-members-handoff.md`:

```markdown
# C2 → C14 设置页内联成员面板交接

C2 不修改控制台，也不新增页面路由。成员管理作为 `/settings` 页面的内联面板交付；不得新增 `/settings/members` 页面或第 12 条合同路由，11 条合同路由保持不变。

## 数据源

- 会话角色来自 `GET /api/auth/me` 的 `role`，取值 `owner`、`admin`、`member`。
- 成员列表来自 `GET /api/workspaces/current/members`；每行包含 `user.id`、`user.email`、`user.name` 与 `role`。
- 邀请成员调用 `POST /api/workspaces/current/members`，请求体 `{"email": "...", "role": "member"}`。
- 改角色调用 `PATCH /api/workspaces/current/members/{user_id}`，请求体 `{"role": "admin"}` 或 `{"role": "member"}`。
- 移除成员调用 `DELETE /api/workspaces/current/members/{user_id}`。
- 项目分配读取 `GET /api/projects` 与 `GET /api/projects/{project_id}/members`；授予调用 `POST /api/projects/{project_id}/members`，请求体 `{"user_id": "..."}`；撤销调用 `DELETE /api/projects/{project_id}/members/{user_id}`。
- 项目分配只接受当前工作区成员；目标不是工作区成员时返回 404 `workspace_member_not_found`；重复授予返回 409 `project_member_exists`。

## 页面行为

面板挂载在 `/settings` 现有“成员”区块，根节点 `data-testid="settings-members"`。页面不新增路由。

| 控件 | owner | admin | member |
|---|---|---|---|
| 成员行 `member-row-<email>` | 显示 | 显示 | 显示 |
| 邀请表单 `member-invite-form` | 显示 | 隐藏 | 隐藏 |
| 角色下拉 `member-role-<email>` | 显示 | 隐藏 | 隐藏 |
| 非本人移除按钮 `member-remove-<email>` | 显示 | 隐藏 | 隐藏 |
| 项目分配面板 `project-member-panel` | 显示 | 显示 | 隐藏 |
| 非 owner 提示 `members-non-owner-hint` | 隐藏 | 显示 | 显示 |

1. owner 的本人行显示 `member-role-<own-email>`，不显示本人移除按钮；把最后一名 owner 降级时，服务端返回 409 `workspace_last_owner_required`，页面在 `member-error` 中原样显示该错误码，成员行与角色不改变。
2. owner 对非本人行显示角色下拉与移除按钮；移除 `workspaces.owner_id` 对应用户时，服务端返回 403 `workspace_owner_immovable`，页面显示该错误码。
3. admin 与 member 不显示邀请表单、角色下拉或移除按钮；admin 仍显示项目分配面板，member 不显示。
4. 非 owner 提示固定为：“只有工作区所有者可以添加、移除成员或修改角色。管理员可以查看成员列表。”
5. 角色文案：`owner` → 所有者，`admin` → 管理员，`member` → 成员。
6. 工作区成员管理只使用会话 `role === "owner"`；项目分配使用 `role === "owner" || role === "admin"`；不得用 `workspace.owner_id` 判断管理权限。
7. mutation 成功后重新读取对应列表；失败时保留当前选择，并在 `member-error` 显示 `error.code`。

## Playwright 判据

预置：真实 owner storage state；admin 与 member 只读视角可用 `/api/auth/me` 的 route fixture 切换 `role`。mutation 判据必须使用真实 owner 会话与真实 API，不得用 mock 代替。邀请目标使用种子已存在、尚未加入当前工作区的用户邮箱。

1. `/settings` 返回 200，存在 `<main>` 与 `[data-testid="settings-members"]`；`page.url()` 以 `/settings` 结尾；页面没有指向 `/settings/members` 的链接。
2. owner 面板：`[data-testid="member-invite-form"]`、`[data-testid="member-invite-email"]`、`[data-testid="member-invite-role"]`、`[data-testid="member-invite-submit"]`、`[data-testid="member-role-<own-email>"]` 与 `[data-testid="project-member-panel"]` 可见；本人行没有 `[data-testid="member-remove-<own-email>"]`。
3. 邀请：填 `[data-testid="member-invite-email"]`，选 `[data-testid="member-invite-role"]`，点 `[data-testid="member-invite-submit"]`；`[data-testid="member-row-<invited-email>"]` 出现，`[data-testid="member-error"]` 不存在。
4. 改角色：把 `[data-testid="member-role-<invited-email>"]` 从 `member` 改为 `admin`，刷新后该行显示“管理员”；再改回 `member`，刷新后显示“成员”。
5. 最后 owner 错误：把 `[data-testid="member-role-<own-email>"]` 改为 `member`；`[data-testid="member-error"]` 包含 `workspace_last_owner_required`；本人行仍显示“所有者”。
6. 项目分配：在 `[data-testid="project-member-panel"]` 选择 `[data-testid="project-member-project"]` 与 `[data-testid="project-member-user"]`，点 `[data-testid="project-member-grant"]`；`[data-testid="project-member-row-<project-id>-<invited-email>"]` 出现；点 `[data-testid="project-member-revoke-<project-id>-<invited-email>"]` 后消失。
7. 可见性：owner 看到邀请表单、`[data-testid="member-role-<invited-email>"]`、`[data-testid="member-remove-<invited-email>"]` 与项目分配面板；admin 看到成员行与项目分配面板，看不到邀请表单、角色下拉、移除按钮；member 只看到成员行，看不到邀请表单、角色下拉、移除按钮与项目分配面板；admin 与 member 都看到 `[data-testid="members-non-owner-hint"]`，文案与页面行为第 4 条一致。
8. 三个视角都没有 5xx、没有 `console.error`。

## 风险

C14 未完成前，C2 只有 API 与单元测试证据，没有真实浏览器证据。该风险由 C14 的 `members.spec.ts` 与 PG0 验收关闭。若可见性用例使用 mock 会话，邀请、改角色、最后 owner 错误与项目分配必须另有真实 API 用例；只有 mock 的成员面板不算关闭该风险。
```

- [ ] **Step 3: 确认没有控制台改动**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git status --porcelain -- apps/scraper-console | tee /tmp/c2-console-status.txt
test ! -s /tmp/c2-console-status.txt && echo "CONSOLE_UNTOUCHED"
```

Expected: `CONSOLE_UNTOUCHED`。

- [ ] **Step 4: 提交前运行 GitNexus 变更分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `未检测到变更。`。

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git add docs/ops/c2-c12-downstream-handoff.md \
  docs/ops/c2-c14-members-handoff.md
git commit -m "docs(ops): hand off C2 downstream ACL and C14 member page"
```

Expected: 提交成功，`git status --porcelain -uno` 空输出。

---

## C2 验收门禁

以下不是新实现任务，而是本计划完成的退出条件。全部通过后才允许合并。

### 后端门禁

- [ ] **迁移单 head**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run alembic heads
```

Expected: 只有 `202610220060 (head)`。

- [ ] **迁移在空 PostgreSQL 15 上升级**

```bash
createdb c2_identity_acl_test 2>/dev/null || true
export C2_TEST_DATABASE_URL="postgresql+asyncpg://data_intel:dev_password@127.0.0.1:5432/c2_identity_acl_test"
export C2_TEST_PSQL_URL="${C2_TEST_DATABASE_URL/postgresql+asyncpg/postgresql}"
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
DATABASE_URL="$C2_TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$C2_TEST_DATABASE_URL" uv run alembic downgrade -1
DATABASE_URL="$C2_TEST_DATABASE_URL" uv run alembic upgrade head
```

Expected: 三次命令退出码 0；表 `project_members`、`audit_events` 存在；`workspace_members` 有 `ck_workspace_members_role`；触发器 `trg_audit_events_append_only` 与 `trg_workspace_members_last_owner` 存在。`downgrade -1` 在空审计表上成功；若有审计行，降级必须拒绝。

- [ ] **SQL 验证只追加触发器**

执行顺序：先完成下方“真实栈浏览器验收”，让数据库里至少有一条 `audit_events` 行，再回到本步。没有审计行时 `UPDATE` 命中 0 行，不算通过。

```bash
psql "$C2_TEST_PSQL_URL" -v ON_ERROR_STOP=0 -c \
  "UPDATE audit_events SET action='tamper' WHERE id=(SELECT id FROM audit_events LIMIT 1);"
```

Expected: `ERROR: audit_events is append-only`。

- [ ] **SQL 验证最后 owner 触发器**

```bash
psql "$C2_TEST_PSQL_URL" -v ON_ERROR_STOP=0 -c \
  "UPDATE workspace_members SET role='member' WHERE id=(SELECT id FROM workspace_members WHERE role='owner' LIMIT 1);"
```

Expected: `ERROR: workspace_last_owner_required`（该工作区只有一名 owner 时）。

- [ ] 共享 compose 配置事实

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
docker compose -f configs/deploy/scrapy/docker-compose.yml config --quiet
rg -n 'WORKSPACE_RBAC_ENFORCED|AUDIT_CHAIN_HEAD_DIR|AUDIT_CHAIN_HEAD_HMAC_KEY' configs/deploy/scrapy/docker-compose.yml
cd apps/api
uv run pytest -q tests/unit/test_deploy_c2_facts.py
```

Expected: `docker compose config` 退出码 0；三个键各有一行映射；4 passed。若本机缺少生产必填变量，只运行测试，并在 C14 的 A/B 环境执行 `config --quiet`。

- [ ] **后端定向测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest -q \
  tests/unit/test_contract_freeze_c2.py \
  tests/unit/test_c2_migration_source.py \
  tests/unit/test_error_envelope.py \
  tests/unit/test_workspace_roles.py \
  tests/unit/test_project_acl.py \
  tests/unit/test_internal_reviewer_access.py \
  tests/unit/test_audit_log.py \
  tests/unit/test_audit_action_registry.py \
  tests/unit/test_audit_chain_head.py \
  tests/unit/test_deploy_c2_facts.py \
  tests/unit/test_acl_audit_integration.py \
  tests/unit/test_project_api_key_routes.py \
  tests/unit/test_workspace_resolution.py \
  tests/unit/test_task_runs_route.py \
  tests/integration/test_auth_projects.py \
  tests/integration/test_social_provider_routes.py
```

Expected: 全部 passed，0 failed。

- [ ] **审计动作注册表覆盖检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest -q tests/unit/test_audit_action_registry.py
```

Expected: 全部 passed；`REQUIRED_AUDIT_ACTIONS` 全部登记；C1 契约列出全部动作；C2 源码不含未登记动作。

- [ ] **下游交接文档覆盖检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
test -f docs/ops/c2-c12-downstream-handoff.md && echo "DOWNSTREAM_HANDOFF_PRESENT"
rg -n "C4|C5|C6|C7|C8|C9|C10|C11|C12" docs/ops/c2-c12-downstream-handoff.md
```

Expected: `DOWNSTREAM_HANDOFF_PRESENT`；每个切片都有接入行。

- [ ] **后端全量回归**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run pytest -q tests/unit tests/integration
```

Expected: 0 failed。任何失败都按回归处理，不得用基线豁免。

- [ ] **静态检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
uv run ruff check src tests
uv run mypy src tests
```

Expected: 退出码 0。

### 前端门禁（C14 交接）

C2 不修改控制台。前端单元测试、`tsc`、`next build` 与 Playwright 由 C14 在 `feat/gov-c14` 执行。C2 的合并门禁只要求：

- [ ] `docs/ops/c2-c14-members-handoff.md` 存在，且包含 `/settings` 内联成员面板的选择器、邀请、改角色、最后 owner 错误、项目分配与 owner/admin/member 三视角浏览器判据。
- [ ] `docs/ops/c2-c12-downstream-handoff.md` 存在且包含 C4-C12 接入表、403/404 模板与审计动作 owner 表。
- [ ] `git status --porcelain -- apps/scraper-console` 为空。

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
test -f docs/ops/c2-c12-downstream-handoff.md && echo "DOWNSTREAM_HANDOFF_PRESENT"
test -f docs/ops/c2-c14-members-handoff.md && echo "HANDOFF_PRESENT"
git status --porcelain -- apps/scraper-console
```

Expected: `DOWNSTREAM_HANDOFF_PRESENT` 与 `HANDOFF_PRESENT`；`git status` 空输出。

### 真实栈 API 验收

按以下步骤在本机真实 API 上验收。每一步都记录响应到 `tmp/c2-acceptance/`。浏览器验收由 C14 交接，不在 C2 执行。

- [ ] 启动真实栈（一次性数据库）

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
createdb c2_identity_acl_test 2>/dev/null || true
export C2_TEST_DATABASE_URL="postgresql+asyncpg://data_intel:dev_password@127.0.0.1:5432/c2_identity_acl_test"
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
DATABASE_URL="$C2_TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$C2_TEST_DATABASE_URL" WORKSPACE_RBAC_ENFORCED=true \
  uv run uvicorn data_intelligence_hub.main:app --host 127.0.0.1 --port 8000
```

Expected: `alembic upgrade head` 退出码 0；uvicorn 使用一次性库，不读取 `apps/api/.env` 的共享开发库。

- [ ] 创建 owner 与 member 两个一次性用户

```bash
mkdir -p tmp/c2-acceptance
curl -sS -c tmp/c2-acceptance/owner.cookies \
  -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"c2-acceptance-owner@example.com","password":"strong-password","name":"C2 Owner"}' \
  | tee tmp/c2-acceptance/owner.json

curl -sS -c tmp/c2-acceptance/member.cookies \
  -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"c2-acceptance-member@example.com","password":"strong-password","name":"C2 Member"}' \
  | tee tmp/c2-acceptance/member.json
```

Expected: 两个响应都是 201；`role` 都是 `owner`（新注册用户各自的个人工作区）。

- [ ] 登录成功与失败登录审计

```bash
curl -sS -o /tmp/c2-login-ok.json -w '%{http_code}\n' \
  -c tmp/c2-acceptance/owner-login.cookies \
  -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"c2-acceptance-owner@example.com","password":"strong-password"}'
curl -sS -o /tmp/c2-login-failed.json -w '%{http_code}\n' \
  -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"c2-acceptance-owner@example.com","password":"wrong-password"}'
```

Expected: 200 与 401；后续审计列表包含 `auth.login.succeeded` 与 `auth.login.failed`（`result='failed'`）。

- [ ] owner 邀请 member 并改角色

```bash
WORKSPACE_ID=$(python3 -c 'import json; print(json.load(open("tmp/c2-acceptance/owner.json"))["workspace"]["id"])')
MEMBER_ID=$(python3 -c 'import json; print(json.load(open("tmp/c2-acceptance/member.json"))["user"]["id"])')
curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X POST http://127.0.0.1:8000/api/workspaces/current/members \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"c2-acceptance-member@example.com\",\"role\":\"member\"}" \
  | tee tmp/c2-acceptance/invite.json
curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X PATCH "http://127.0.0.1:8000/api/workspaces/current/members/${MEMBER_ID}" \
  -H 'Content-Type: application/json' \
  -d '{"role":"admin"}' \
  | tee tmp/c2-acceptance/role-change.json
curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X PATCH "http://127.0.0.1:8000/api/workspaces/current/members/${MEMBER_ID}" \
  -H 'Content-Type: application/json' \
  -d '{"role":"member"}' \
  | tee tmp/c2-acceptance/role-change-back.json
```

Expected: 邀请 201；两次改角色 200；响应角色分别为 `admin` 与 `member`。

- [ ] 创建项目并授予 member 访问

```bash
PROJECT_ID=$(curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X POST http://127.0.0.1:8000/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"C2 Acceptance Project","domain":"mixed"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X POST "http://127.0.0.1:8000/api/projects/${PROJECT_ID}/members" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"${MEMBER_ID}\"}" \
  | tee tmp/c2-acceptance/project-member.json
```

Expected: 201；响应包含 member 用户。

- [ ] 创建未授权项目与跨工作区项目

```bash
UNASSIGNED_PROJECT_ID=$(curl -sS -b tmp/c2-acceptance/owner.cookies \
  -X POST http://127.0.0.1:8000/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"C2 Unassigned Project","domain":"mixed"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS -c tmp/c2-acceptance/other.cookies \
  -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"c2-acceptance-other@example.com","password":"strong-password","name":"C2 Other"}' \
  > tmp/c2-acceptance/other.json
OTHER_PROJECT_ID=$(curl -sS -b tmp/c2-acceptance/other.cookies \
  -X POST http://127.0.0.1:8000/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"C2 Other Workspace Project","domain":"mixed"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
```

Expected: 两个项目都创建成功。

- [ ] API 验收项目 ACL

```bash
curl -sS -o /tmp/c2-unassigned.json -w '%{http_code}\n' -b tmp/c2-acceptance/member.cookies \
  "http://127.0.0.1:8000/api/projects/${UNASSIGNED_PROJECT_ID}"
curl -sS -o /tmp/c2-other.json -w '%{http_code}\n' -b tmp/c2-acceptance/member.cookies \
  "http://127.0.0.1:8000/api/projects/${OTHER_PROJECT_ID}"
cat /tmp/c2-unassigned.json /tmp/c2-other.json
```

Expected: 403 与 404；错误码分别是 `project_access_forbidden` 与 `project_not_found`。

- [ ] 审计链校验

```bash
curl -sS -b tmp/c2-acceptance/owner.cookies \
  http://127.0.0.1:8000/api/audit-events/verify \
  | tee tmp/c2-acceptance/audit-verify.json
curl -sS -b tmp/c2-acceptance/owner.cookies \
  "http://127.0.0.1:8000/api/audit-events?limit=50" \
  | tee tmp/c2-acceptance/audit-events.json
```

Expected: `{"valid":true,"checked":N,"first_invalid_sequence":null,"first_sequence_number":1,"anchor_prev_hash":"64 个 0"}`，N > 0；列表包含 `auth.login.succeeded`、`workspace.member.added`、`workspace.member.role_changed`、`project.created`、`project.member.added`。失败登录用例后应出现 `auth.login.failed`（`result='failed'`）。

- [ ] 审计链头导出与校验

```bash
cd /Users/lute/Project/data_scrapy-gov-c2/apps/api
DATABASE_URL="$C2_TEST_DATABASE_URL" \
AUDIT_CHAIN_HEAD_HMAC_KEY="c2-local-chain-head-key-0123456789abcdef" \
uv run python -m data_intelligence_hub.maintenance.audit_chain_head_export \
  --output-dir /Users/lute/Project/data_scrapy-gov-c2/tmp/c2-acceptance/audit-chain-heads \
  --date 2026-10-22
uv run python - <<'PY'
import json
from pathlib import Path

from data_intelligence_hub.services.audit_chain_head import (
    verify_audit_chain_head_document,
)

root = Path("/Users/lute/Project/data_scrapy-gov-c2/tmp/c2-acceptance/audit-chain-heads")
path = sorted(root.glob("audit-chain-head-*.json"))[-1]
document = json.loads(path.read_text(encoding="utf-8"))
assert verify_audit_chain_head_document(
    document, hmac_key="c2-local-chain-head-key-0123456789abcdef"
)
assert document["heads"]
assert all(head["event_count"] > 0 for head in document["heads"])
assert (path.stat().st_mode & 0o777) == 0o600
print("chain_head_ok", path)
PY
```

Expected: `chain_head_ok .../audit-chain-head-2026-10-22.json`；`document_sha256` 与 `hmac_sha256` 各 64 位；文件权限 `0600`。C2 不执行外部上传。

- [ ] 清理一次性数据库

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
stop_api() { pkill -f 'uvicorn data_intelligence_hub.main:app' || true; }
stop_api
dropdb c2_identity_acl_test
```

Expected: API 停止；数据库删除。不得删除审计行，不得临时禁用触发器，不得对共享库执行本步骤。

### 统一发布门禁（PG0 发布批次；C14 只读）

本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。C2 只交付可合并的代码、迁移、共享 compose 映射与验收证据，不执行生产发布命令。

发布顺序固定，任一步失败即停止同批次：

1. **先备份**：备份目标数据库与 compose 使用的持久卷，记录备份路径与 SHA-256。
2. **A 环境 canary**：先发布 A，运行冒烟与本计划 API 验收；失败时回滚 A，B 不发布。
3. **B 环境门禁**：B 只在用户对生产 B 给出明确目标授权，且 PG0 发布负责人完成备份校验和迁移门禁后发布。C14 只读记录授权与发布窗口，不授予目标权限；迁移门禁指 `alembic heads` 只有 `202610220060 (head)`、迁移在一次性库演练通过、备份可恢复。
4. **失败记 `BLOCKED`**：记录失败步骤、证据路径与决策人；不得跳过门禁继续发布。

C2 只修改共享 compose 的 `api.environment` 映射（默认关闭），不部署、不执行生产迁移、不写 `.env.production`、不重启容器。部署证据由 PG0 发布批次收集；C14 收集只读验收证据。

### 变更审查门禁

- [ ] **GitNexus 变更分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 输出不含 `partial: true` 或 `truncated: true`。若出现，重跑；零不等于未受影响。

- [ ] **最终 diff 审查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git diff --stat HEAD
git diff --check
```

Expected: 只包含本计划 File Structure 列出的文件；无空白错误；无占位符标记、`user_sessions`、MFA 运行时代码或 `apps/scraper-console/**` 改动；`docs/ops/c2-c12-downstream-handoff.md` 与 `docs/ops/c2-c14-members-handoff.md` 已提交。

- [ ] **分支与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c2
git status --short
git log --oneline -9
```

Expected: 9 个提交分别对应 Task 1 到 Task 9；当前分支是 `feat/gov-c2`。工作树没有未提交改动；本计划 Markdown 已随 Task 1 提交。

---

## 审查摘要（2026-10-22 修订）

| 审查项 | 级别 | 处理 | 落点 |
|---|---|---:|---|
| 越权修改 C1 契约 | P0 | Task 1 改为只读守卫；删除契约写入与 registry 重建；缺口交回 C1。 | Task 1、Global Constraints |
| 越权修改 C14 控制台 | P0 | 删除全部 `apps/scraper-console/**` 与 e2e 改动；Task 9 改为 C14 交接文档，含页面行为与 Playwright 判据。 | File Structure、Task 9、前端门禁 |
| 审计链头无外部证据 | P1 | C2 只导出本地签名 JSON；O0 Task 13 上传 WORM/对象锁并验证不可覆盖。 | Task 7、Global Constraints |
| 分支起点错误 | P0 | `git worktree add ../data_scrapy-gov-c2 -b feat/gov-c2 feat/gov-c1`；断言 C1 祖先、head 057、registry 存在。 | Global、Task 1 Step 1 |
| 数据库 URL 占位符 | P0 | 改为 `data_intel` 本地默认凭据。 | 后端门禁 |
| 真实栈未用一次性库 | P1 | uvicorn 命令显式 `DATABASE_URL="$C2_TEST_DATABASE_URL"`。 | 真实栈 API 验收 |
| 清理步骤危险 | P1 | 停 API 后 `dropdb`；不删除审计行、不禁用触发器。 | 真实栈 API 验收 |
| File Structure 漏文件 | P1 | 增加 `api/deps.py`、`test_task_runs_route.py`、`test_social_provider_routes.py`。 | File Structure、后端门禁 |
| mypy 门禁不完整 | P2 | 改为 `uv run mypy src tests`。 | 后端门禁 |
| 计划 Markdown 未提交 | P2 | Task 1 提交本计划文件；最终工作树干净。 | Task 1 Step 6 |
| C4-C12 项目 ACL 未交接 | P0 | 增加唯一消费者契约、逐切片接入表、同工作区跨项目 403/404 测试模板与 `docs/ops/c2-c12-downstream-handoff.md`；C2 不修改下游文件。 | 路由接缝、Task 9、验收门禁 |
| 内部审阅者被当成客户角色 | P0 | 复用 C1 登记的 `report_reviewer_assignments`；只读、范围受限、`expires_at` 到期拒绝；C2 不建表、不写表、不加 `reviewer` 角色。 | 身份事实源、内部审阅者接缝、Task 5/8 |
| 审计动作分散、无法检查 | P0 | `AUDIT_ACTIONS` 注册表、`REQUIRED_AUDIT_ACTIONS`、`validate_audit_action` 严格拒绝未登记动作；增加注册表 checker 与下游 owner 表。 | Task 6、Task 9、验收门禁 |
| 追加式与保留语义被破坏 | 保持 | `audit_events` 只追加触发器、SHA-256 哈希链、`prev_hash` 与 730 天 C11 清理边界不变；审阅者接缝只读不写审计链之外的表。 | Global Constraints、Task 2、Task 6、Task 7 |
| 单一 owner 源、admin/member/ACL/audit | 保持 | `workspace_members.role` 是唯一授权事实源；`workspaces.owner_id` 不是；admin 只读、member 项目可见性、审计哈希链不变。 | 身份事实源、全局约束、Task 3-8 |

自检结论：占位符扫描已通过；C2 不修改契约、registry、控制台、e2e 或 C4-C12 文件；内部审阅者不新增客户角色、不建表；审计动作全部登记且未登记动作被拒绝；每个 commit 前运行 `detect-changes`。
