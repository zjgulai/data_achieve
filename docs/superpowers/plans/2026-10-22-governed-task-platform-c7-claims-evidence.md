# C7 受治理任务包：主张与证据实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 B5 基线上补齐 `claims`、`claim_evidence`、`evidences` 的治理字段、独立来源簇、证据等级上限、L0/L1 不生成 Claim、五状态、风险与审核字段、逐市场 scope，用一个迁移 063 落地，并把报告页浏览器验收交接给 C14。

**Architecture:** 只扩展 B5 已有的 `models/claim.py`、`models/intelligence.py`、`repositories/claims.py`、`services/claims.py`，不新建第二套 evidence 模块。新增纯函数 `services/source_clusters.py` 按原始记录簇判定独立来源；新增纯函数 `services/claim_semantics.py` 把 `do_not_enter`、`confirmed` 与 Quick 的语义证据规则交给 C9 消费；证据等级上限沿用 B5 `schemas/report_contract.max_claim_status_for_grade`，不复制第二张表。迁移 063 加列、加 CHECK、加索引；写入层允许不完整草稿，`load_publishable_claim_rows()` 是正式交付的唯一门禁。Claim 审核只接受 C1/C2 的 active 内部审核指派（`report_reviewer_assignments`，范围 `report_read`/`report_review`），不把客户 `owner/admin/member` 当作审核人；审核、覆盖、阻断统一写 C2 `audit_events`。Claim/evidence 只读 API 全部调用 C2 `require_project_access`。C1 冻结 canonical profile 与报告 schema 版本；C14 用只读 API 和合同行做浏览器验收。

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic · Pydantic 2 · pytest / pytest-asyncio · SQLite 内存库（单元测试）· PostgreSQL（迁移目标）· uv · Ruff · mypy.

## Global Constraints

- **隔离 worktree。** 执行分支是 `feat/gov-c7`，只在 `/Users/lute/Project/data_scrapy-gov-c7` 中创建和执行。主工作树 `/Users/lute/Project/data_scrapy` 只做只读预检和本计划的复制源。不得在主工作树切换分支、暂存、提交或运行测试。Task 0 Step 0 给出完整命令；后续所有 Run/Commit 命令使用 worktree 路径。
- **开关与回滚。** 本切片不新增布尔开关，入口受 `GOVERNED_TASK_PLATFORM_ENABLED` 控制；回滚点是迁移 `063` 的 `downgrade` 与发布前数据库备份，生产回滚用备份恢复或新迁移，不手改 `alembic_version`。
- **基线固定。** 实现分支必须从前置切片 C6 的前置分支 `feat/gov-c6` 创建独立 worktree：`cd /Users/lute/Project/data_scrapy && git worktree prune && git worktree add /Users/lute/Project/data_scrapy-gov-c7 -b feat/gov-c7 feat/gov-c6`。创建后执行 `cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv sync --locked --dev`。该分支已包含 C0–C6 与 C1 契约，Alembic head 必须是 `202610220062`。不得在 `feat/b5-workbench` 或 `main` 上直接开发，也不得在 worktree 内合并 C1–C6。B5 只是报告与 claim 的实现基线，不再作为分支起点。不得另建第二套 claims/evidence 模型、仓储或服务；不得复制 `modules/evidence`。
- **C4/C5/C6 前置。** C4 的运行与步骤、C5 的证据写入、C6 的合同装配必须已包含在 `feat/gov-c6` 分支中。C7 只消费以下已冻结接口：`runs.id`、`runs.evidence_grade`、`run_evidence_grades`、`evidences` 行、`report_contract` 的 `SCHEMA_VERSION` 与 `CANONICAL_PROFILE_ID`。缺任一接口时，Task 0 直接失败，不进入编码。
- **契约只读。** C1 已把 C7 需要的全部新列、枚举与约束名登记到 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 与 `configs/contracts/v1.1.0/registry.json`。C7 只读 registry 做守卫，不修改契约文档、不修改 registry、不追加实现决定。Task 1 缺任一登记项时停止并返回 C1 补充登记；C7 不落地未登记对象。契约文档与 `registry.json` 不在本切片的修改清单和提交范围内。冻结表名、主键、`claims.state` 五值、`run_ledger_entries` 八列与六种 `entry_kind` 不得修改。
- **Canonical profile 只能由 C1 冻结。** B5 `canonical_json_bytes` 的 docstring 明确写着“RFC 8785 的近似，不是完整实现”。C1 必须导出 `CANONICAL_PROFILE_ID = "dih-canonical-json-v1"`，并把 `SCHEMA_VERSION` 升级到 `1.1.0`；`claims[].text_en`、`risk_flags`、`review_status`、`independent_source_count`、`blocked_reason`、嵌套 `scope`、`owner` 必须进入 1.1.0 合同。`dih-canonical-json-v1` 绑定 B5 现有 `canonical_json_bytes` 的近似 RFC 8785 行为；严格 RFC 8785 升级延期，未来若实施必须使用不同 ID `dih-canonical-json-rfc8785-v1`，不得改变 v1 的字节输出。C7 只从 `schemas.report_contract` import `CANONICAL_PROFILE_ID`、`SCHEMA_VERSION` 与 `canonical_json_bytes`，不定义本地副本；所有审核签名调用 C1 的 `canonical_json_bytes`。C7 把 profile ID 存进 `claims.reviewed_profile`，验证时不一致即拒绝发布。
- **证据等级。**`L0_unverified` 与 `L1_contract` 不生成 Claim。Claim 最低 L2。状态上限固定：L2 → `hypothesis`，L3 → `directional`，L4 → `confirmed`。`confirmed` 还必须同时满足：`review_status='approved'`、`reviewed_content_version=content_version`、独立来源 ≥ 2。
- **五状态固定。**`confirmed · directional · hypothesis · evidence_gap · blocked`。显示别名（Verified、Supported 等）只用于界面文案，不得写进数据库、合同、API 或测试枚举。
- **独立来源按原始记录簇计。** 同一 provider 的不同端点、同一端点的多次调用、同一页面的多条抓取路径、同一记录的翻译、转载、不同导出格式、两把不同 API Key，都只能算 1 个来源。推导不出簇的证据不算独立来源。翻译、转载、导出副本必须由采集器写 `reference_metadata['source_cluster_key']`；C7 不猜测语义重复。
- **逐市场 scope。**`scope_market` 只能是 11 个正式市场：`US/GB/DE/FR/IT/ES`（core）与 `IE/NL/BE/AT/PL`（supported）。正式 Claim 必须有 `scope_market`、`scope_window_start`、`scope_window_end`、`scope_window_days`、`scope_sample_n`。`missing` 不能写成数值 0；`blocked` 不能写成空结果。
- **审核人是内部指派，不是客户角色。** Claim 审核只接受 C1 登记、C2 实现的 `report_reviewer_assignments` 中的 active 指派：审核范围必须是 `report_review`；`report_read` 只是受限只读范围，不能签发审核。客户 `owner`、`admin`、`member` 一律不得作为 Claim 审核人，即使存在错误指派行也必须拒绝。审核人不得是 Claim owner、任务单 owner 或任务单请求人（`workbench_tasks.owner_id`、`workbench_tasks.created_by_user_id`）。第二审核人同样必须 active 且范围 `report_review`，并不得与第一审核人、Claim owner、任务 owner 或请求人重复。受限只读用 `assert_claim_read_scope()` 单独校验，不把只读范围升级成审核范围。C7 不新建审核指派表，也不写客户侧 `reviewer` 角色。
- **审核、覆盖、阻断统一审计。** `submit_claim_for_review()`、`review_claim()`、`override_claim_review()`、`block_claim()`、`unblock_claim()` 与 `revise_claim()` 必须在同一事务内调用 C2 `services.audit_log.append_audit_event()`。动作固定为 `claim.review.submitted`、`claim.review.approved`、`claim.review.rejected`、`claim.review.overridden`、`claim.blocked`、`claim.unblocked`、`claim.revised`；`resource_type='claim'`，`resource_id=str(claim.id)`，`details` 不含密钥、Cookie、token 或哈希盐。审计写入失败时整个事务回滚，不得静默跳过。
- **Claim/evidence API 走项目 ACL。** `GET /api/claims` 与 `GET /api/claims/{claim_id}`（含其 `evidences` 段）必须调用 C2 `api.authz.require_project_access()`。`GET /api/claims` 的 `project_id` 是必填查询参数。跨工作区返回 404（`project_not_found` 或 `claim_not_found`），同工作区但无项目权限返回 403 `project_access_forbidden`。C7 不新增独立 evidence 路径；证据读取只经 Claim 详情，因而继承同一 ACL。C1 必须把 `project_not_found`、`project_access_forbidden` 登记到 `claims.list` 与 `claims.detail` 的 `error_codes`，并在正文写明 `claims.list` 需要 `project_id`。
- **语义证据规则交给 C9。** `services/claim_semantics.py` 提供纯函数 `validate_claim_semantics()` 与 `assert_claim_semantics()`，C9 在报告装配与发布前必须消费。规则只用已批准项：`do_not_enter` 要求市场 `quality_status='qualified'` 且至少 2 个独立原始记录簇；`confirmed` 仍要求 L4、`review_status='approved'`、独立来源 ≥ 2；Quick 不得出现 `confirmed`，也不得输出 Standard 四态（`conclusion_standard` 必须为空）。不新增阈值，不新增等级表。
- **审核后修改。** `approved` 只能由内部审核人签发。医疗、健康、安全、法律、召回、儿童风险必须由第二人复核。审核后修改 Claim 内容、scope、风险标记或反证文本，必须置 `stale` 并清空全部签字。C7 不新建独立审核表；`claims.review_history` 只做行内追加，正式报告审核事实仍写 `report_audit_events`。
- **草稿与正式分离。** 写入层允许字段不完整的草稿，只强制枚举、等级下限、状态上限和反证规则。`load_publishable_claim_rows()` 与 `validate_claim_bundle()` 是正式交付门禁，缺任一字段即拒绝，不允许 C14 或报告构建器绕过。
- **GitNexus 强制。** 每个修改既有符号的任务先跑 `impact`；每个提交前跑 `detect-changes --scope all`。`partial: true` 或 `truncated: true` 不算通过，必须重跑。`risk: UNKNOWN` 必须用文本搜索确认调用方，不能当作安全。
- **测试命令。** 所有 Python 命令在 `/Users/lute/Project/data_scrapy-gov-c7/apps/api` 下执行：`uv run pytest ...`、`uv run ruff check ...`、`uv run mypy src`。迁移头检查：`uv run alembic heads`。
- **浏览器交接。** C7 只负责后端字段、只读 API、合同行和夹具，不修改 `apps/scraper-console/src/app/reports/**`。报告页浏览器验收由 C14 完成，交接清单见文末。
- **不直接部署。** 本切片不直接部署任何环境，不执行生产发布、A/B 切换或回滚。A、B 两套生产的发布与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；C7 只交付迁移、测试证据与交接清单。

## 前置事实与依赖

| 事实 | 值 | 用途 |
|---|---|---|
| 前置分支 | `feat/gov-c6`（C6 完成） | C7 worktree 起点；必须含 C0–C6 与 C1 契约 |
| B5 现有迁移头 | `202610210057` | 056 claims、057 report_artifacts |
| C7 迁移 | `202610220063` | 本计划唯一迁移 |
| C7 迁移的 `down_revision` | `202610220062` | C6 的迁移头 |
| 现有 claim 测试 | `apps/api/tests/unit/test_claims.py` 21 passed | 基线回归 |
| 现有升级链 | `alembic heads` → `202610220062 (head)` | 前置分支上必须只有一行 |
| 内部审核指派 | `report_reviewer_assignments` 表与 `assignment_scope`（`report_read`/`report_review`） | C1 登记，C2 迁移与实现；C7 只读 service |
| 统一审计 | C2 `services.audit_log.append_audit_event()` 与 `audit_events` 表 | Claim 审核/覆盖/阻断同一事务追加 |
| 项目 ACL | C2 `api.authz.require_project_access()` | Claim/evidence 只读 API 唯一授权接缝 |

**C1/C2 前置登记（缺一项即停止，返回 C1 或 C2）。** C1 必须已登记 `report_reviewer_assignments` 表、`report_reviewer_assignments.assignment_scope` 枚举值 `report_read`/`report_review`、`claims.list` 与 `claims.detail` 的 `project_not_found`/`project_access_forbidden` 错误码，以及 C7 使用的全部 `claim_*`/`reviewer_*` 错误码（清单见 Task 1）。C2 必须已提供 `services.reviewer_assignments.get_active_reviewer_assignment()`、`grant_reviewer_assignment()`、`ReviewerAssignment`、`REVIEWER_SCOPE_READ`、`REVIEWER_SCOPE_REVIEW`，以及 `services.audit_log.append_audit_event()` 与 `api.authz.require_project_access()`。C7 不创建这些表、不修改契约、不复制服务；接口名以 C1/C2 修复后的计划为准，若不同则先对齐再编码。

C7 不新建表。所有新列都挂在 B5 已冻结的三张表上：

- `claims`：M05 证据与主张。
- `claim_evidence`：M05 证据与主张，主键只有 `(claim_id, evidence_id)`。
- `evidences`：现有证据表，C7 只补列与可空性。

## File Structure

**创建**

| 文件 | 职责 |
|---|---|
| `apps/api/alembic/versions/202610220063_claim_evidence_completeness.py` | 唯一迁移：补列、CHECK、索引、可空性、workspace/project 回填 |
| `apps/api/src/data_intelligence_hub/tool_catalog/markets.py` | 11 个正式市场的唯一常量 |
| `apps/api/src/data_intelligence_hub/services/source_clusters.py` | 原始记录簇纯函数：URL 规范化、簇键推导、独立性分配 |
| `apps/api/src/data_intelligence_hub/services/claim_semantics.py` | C9 消费的语义证据纯函数：`do_not_enter`、`confirmed`、Quick 规则 |
| `apps/api/src/data_intelligence_hub/services/claim_signing.py` | 审核签名载荷与哈希，唯一调用 C1 canonicalizer |
| `apps/api/src/data_intelligence_hub/schemas/claim.py` | 只读 Claim API 的响应模型 |
| `apps/api/src/data_intelligence_hub/api/routes/claims.py` | `GET /api/claims`、`GET /api/claims/{claim_id}`，全部走项目 ACL |
| `apps/api/tests/unit/test_claim_contract_freeze.py` | C1 registry 与 C1 常量的只读守卫 |
| `apps/api/tests/unit/test_source_clusters.py` | 独立来源簇规则 |
| `apps/api/tests/unit/test_claim_semantics.py` | C9 语义证据规则 |
| `apps/api/tests/unit/test_claim_evidence_policy.py` | 等级下限、状态上限、市场、风险标记 |
| `apps/api/tests/unit/test_claim_evidence_schema.py` | 模型列、CHECK 名、迁移 063 |
| `apps/api/tests/postgres/test_claim_evidence_migration.py` | PostgreSQL 062→063→062 升级、降级与单头 |
| `apps/api/tests/unit/test_claim_creation_governance.py` | 创建服务治理规则 |
| `apps/api/tests/unit/test_claim_review.py` | 审核生命周期、第二审核人、stale |
| `apps/api/tests/unit/test_claim_contract_rows.py` | 可发布 Claim 合同行与门禁 |
| `apps/api/tests/integration/test_claims_api.py` | 只读 Claim API 与工作区隔离 |

**修改**

| 文件 | 改动 |
|---|---|
| `apps/api/src/data_intelligence_hub/models/claim.py` | 新枚举、Claim/ClaimEvidence 新列与 CHECK |
| `apps/api/src/data_intelligence_hub/models/intelligence.py` | Evidence 新列、`intelligence_id` 可空、workspace/project |
| `apps/api/src/data_intelligence_hub/repositories/claims.py` | 扩展创建/关联；加载证据行；更新审核字段；加载任务 owner/请求人 |
| `apps/api/src/data_intelligence_hub/services/claims.py` | 创建治理、内部审核指派校验、统一审计、覆盖、阻断、修订、可发布合同行 |
| `apps/api/src/data_intelligence_hub/services/exceptions.py` | 新增 Claim 治理错误，错误码与 C1 registry 对齐 |
| `apps/api/src/data_intelligence_hub/schemas/intelligence.py` | `EvidenceResponse.intelligence_id` 改为可空 |
| `apps/api/src/data_intelligence_hub/main.py` | 挂载 `/api/claims` |
| `apps/api/tests/unit/test_claims.py` | 更新 seed、确认态测试、迁移 CHECK 断言 |
| `apps/api/tests/unit/test_claim_contract_freeze.py` | 追加 reviewer assignment、ACL 与错误码登记守卫 |
| `apps/api/tests/unit/test_claim_review.py` | 审核指派、任务 owner/请求人排除、覆盖、阻断、统一审计 |
| `apps/api/tests/integration/test_claims_api.py` | 项目 ACL、同工作区跨项目 403、跨工作区 404 |

**明确不创建**

- `apps/api/src/data_intelligence_hub/modules/evidence/`
- 第二套 `models/evidence.py`、`services/evidence.py`、`repositories/evidence.py`
- 第二张等级上限表
- `report_reviewer_assignments` 表、`audit_events` 表及其迁移（C1 登记、C2 实现）
- 客户侧 `reviewer` 角色或审核指派管理页面
- 第二个 063 之后的迁移

## Task Files Interfaces

| Task | 文件 | Consumes | Produces |
|---|---|---|---|
| 0 | 前置门禁 | C1 registry；C2 审核指派、审计、ACL；C4 `workbench_tasks`；C6 迁移头 | 绿色前置状态；缺接口返回 C1/C2 |
| 1 | C1 registry、`test_claim_contract_freeze.py` | C1 的 `SCHEMA_VERSION=1.1.0`、`CANONICAL_PROFILE_ID`、`report_reviewer_assignments` 与 registry | 只读登记守卫结论；缺项返回 C1 |
| 2 | `source_clusters.py` | `Evidence` 的 `url`、`provider_id`、`reference_metadata`；`RawRecord.content_hash` | `SourceCluster`、`LinkCluster`、`resolve_source_cluster()`、`assign_link_clusters()` |
| 3 | `services/claims.py`、`test_claim_evidence_policy.py` | B5 `max_claim_status_for_grade`、`GRADE_ORDER` | `assert_claim_grade_at_least_l2()`、`assert_claim_state_within_grade()`、`assert_confirmed_requirements()` |
| 4 | 模型、迁移 063、schema 守卫 | 契约 v1.1 | 新列、CHECK、索引、可空 `intelligence_id` |
| 5 | `services/claims.py`、`repositories/claims.py` | Task 2/3/4 | `create_claim_with_evidence()` 治理版；blocked 创建审计 |
| 6 | `services/claims.py`、`claim_signing.py`、`repositories/claims.py` | Task 5；C2 `reviewer_assignments`、`audit_log` | `submit_claim_for_review()`、`review_claim()`、`override_claim_review()`、`block_claim()`、`unblock_claim()`、`revise_claim()`；统一审计 |
| 7 | `services/claims.py` | Task 5/6 | `load_publishable_claim_rows(session, *, workspace_id, project_id, task_id: uuid.UUID \| None = None) -> ClaimContractBundle`、`validate_claim_bundle()` |
| 7B | `claim_semantics.py`、`test_claim_semantics.py` | Task 7 的 `ClaimContractBundle`；C8/合同 `markets[]`；C4 `PACKAGE_TYPES` | `validate_claim_semantics()`、`assert_claim_semantics()`、`market_independent_cluster_count()` |
| 8 | `api/routes/claims.py`、`schemas/claim.py`、`main.py` | Task 7；C2 `require_project_access` | `GET /api/claims`、`GET /api/claims/{claim_id}`，项目 ACL |
| 9 | `test_claim_contract_rows.py`、集成测试、C14 交接清单 | Task 7/7B/8 | C14 浏览器验收输入；C9 语义消费接口 |

## 冻结契约字段映射

### `claims` → 报告合同 `claims[]`

| `claims` 列 | 报告合同字段 | 规则 |
|---|---|---|
| `claim_text` | `claims[].text` | 非空 |
| `text_en` | `claims[].text_en` | 正式 Claim 非空；C1 schema 1.1.0 |
| `state` | `claims[].claim_status` | 五值枚举 |
| `evidence_grade` | `claims[].evidence_grade` | L2/L3/L4，L0/L1 禁止 |
| `scope_market` | `claims[].scope.market` | 11 个正式市场 |
| `scope_window_start` | `claims[].scope.window.start` | 日期 |
| `scope_window_end` | `claims[].scope.window.end` | 不早于 start |
| `scope_window_days` | `claims[].scope.window.days` | 等于 `(end-start).days + 1` |
| `scope_sample_n` | `claims[].scope.sample_n` | ≥ 0 |
| `counterevidence_text` | `claims[].counterevidence_text` | 正式 Claim 非空 |
| `owner` | `claims[].owner` | 正式 Claim 必填 |
| `claim_evidence.evidence_id` | `claims[].evidence_ids` | 至少 1 条，按字符串排序去重 |
| `risk_flags` | `claims[].risk_flags` | 封闭集合，`single_source` 自动补 |
| `review_status` | `claims[].review_status` | 五值枚举 |
| `independent_source_count` | `claims[].independent_source_count` | 与独立簇数一致 |
| `blocked_reason` | `claims[].blocked_reason` | `blocked` 必填，其余为空 |
| `reviewed_payload_sha256` | 不公开 | 审核签名，C14 不渲染 |
| `reviewed_profile` | 不公开 | C1 canonical profile ID |

### `evidences` + `claim_evidence` → 报告合同 `evidences[]`

| 来源列 | 报告合同字段 | 规则 |
|---|---|---|
| `evidences.id` | `evidences[].evidence_id` | uuid 字符串 |
| `claim_evidence.claim_id` | `evidences[].claim_id` | 关联 claim |
| `claim_evidence.role` | `evidences[].role` | `support/counter/context/gap` |
| `evidences.raw_record_id` | `evidences[].raw_record_id` | 可空 |
| `evidences.source_tool_id` | `evidences[].source_tool_id` | 正式 Claim 非空 |
| `evidences.url` | `evidences[].url` | support/counter 必填 |
| `evidences.excerpt` | `evidences[].excerpt` | 可空 |
| `evidences.captured_at` | `evidences[].captured_at` | 空时用 `created_at` |
| `evidences.market` | `evidences[].market` | 正式 Claim 非空 |
| `evidences.locale` | `evidences[].locale` | 正式 Claim 非空 |
| `claim_evidence.evidence_grade` | `evidences[].evidence_grade` | 正式 Claim 非空 |
| `claim_evidence.source_cluster_key` | 不公开 | 独立来源判定快照 |
| `claim_evidence.source_cluster_basis` | 不公开 | `explicit/content_hash/platform_item/url/unresolved` |
| `claim_evidence.independent` | 不公开 | 同一 claim 同一簇只有第一条为真 |

### 新枚举（契约 v1.1 冻结）

```text
claim 审核状态 review_status:
draft · pending · approved · rejected · stale

claim 风险标记 risk_flags:
medical · health · safety · legal · recall · children · causal_language · single_source · price_comparison

claim 阻断原因 blocked_reason:
rights · permission · configuration · gate · upstream

claim 审核决定 review_decision:
approved · rejected

report_reviewer_assignments.assignment_scope:
report_read · report_review

C2 审计动作（Claim 治理）:
claim.review.submitted · claim.review.approved · claim.review.rejected · claim.review.overridden · claim.blocked · claim.unblocked · claim.revised
```

`SECOND_REVIEW_RISK_FLAGS = {medical, health, safety, legal, recall, children}`。

审核指派的范围固定为 `report_read`（只读）与 `report_review`（可签发审核）。`report_review` 隐含读取，但 C7 不把只读范围升级成审核范围；客户角色不进入指派表。

---

### Task 0: 前置门禁与隔离 worktree

**Files:**
- Read-only: `/Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md`（主工作树的计划文件，复制源）
- Create: `/Users/lute/Project/data_scrapy-gov-c7`（worktree 根）
- Create/Commit: worktree 内的本计划副本

**Interfaces:**
- Consumes: 前置分支 `feat/gov-c6`；主工作树的计划文件；C1 的 canonical profile、schema 1.1.0 与 `report_reviewer_assignments` 登记；C2 的审核指派、统一审计与项目 ACL；C4/C5/C6 的迁移头 062。
- Produces: 分支 `feat/gov-c7` 与 worktree `/Users/lute/Project/data_scrapy-gov-c7`；后续任务可开工的绿色前置状态。后续所有 Run/Commit 命令只在该 worktree 执行。

- [ ] **Step 0: 从主工作树创建隔离 worktree 并同步依赖**

Run:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c6^{commit}
git branch --list feat/gov-c7
git worktree list --porcelain | grep -F 'worktree /Users/lute/Project/data_scrapy-gov-c7' || true
git worktree add /Users/lute/Project/data_scrapy-gov-c7 -b feat/gov-c7 feat/gov-c6
cd /Users/lute/Project/data_scrapy-gov-c7
git branch --show-current
git merge-base --is-ancestor feat/gov-c6 HEAD && echo C6_BRANCH_BASE_OK
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api
uv sync --locked --dev
cd /Users/lute/Project/data_scrapy-gov-c7
mkdir -p docs/superpowers/plans
cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md \
  docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md
git status --porcelain
git add docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md
git commit -m "docs(plan): add c7 claims and evidence plan"
```

Expected: `git worktree prune` 退出码 0；`git rev-parse` 打印前置提交 SHA；`git branch --list` 无输出；路径检查无输出；`git worktree add` 输出 `Preparing worktree`，退出码 0；当前分支 `feat/gov-c7`；输出 `C6_BRANCH_BASE_OK`；`uv sync` 退出码 0；`git status --porcelain` 只有一行 `?? docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md`；计划提交成功。`cp` 的源路径在主工作树，只读；不得在主工作树执行 `git add`、`git commit`、切换分支或运行测试。分支或路径已存在时停止，先审查旧分支与旧 worktree；不得复用或删除。

- [ ] **Step 1: 确认分支基线**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
git rev-parse --abbrev-ref HEAD
git rev-parse --verify feat/gov-c6^{commit}
git merge-base --is-ancestor feat/gov-c6 HEAD && echo C6_BRANCH_BASE_OK
git rev-parse --short HEAD
```

Expected: 当前分支是 `feat/gov-c7`；`feat/gov-c6` 可解析；输出 `C6_BRANCH_BASE_OK`；HEAD 等于前置分支提交。工作树已由 Step 0 创建，后续命令从 `/Users/lute/Project/data_scrapy-gov-c7` 执行。

- [ ] **Step 2: 确认 C1 常量与 registry**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run python -c "from data_intelligence_hub.schemas.report_contract import CANONICAL_PROFILE_ID, SCHEMA_VERSION; print(SCHEMA_VERSION); print(CANONICAL_PROFILE_ID)"
cd /Users/lute/Project/data_scrapy-gov-c7 && test -f configs/contracts/v1.1.0/registry.json && echo C1_REGISTRY_PRESENT
cd /Users/lute/Project/data_scrapy-gov-c7 && uv run python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: 第一行 `1.1.0`；第二行 `dih-canonical-json-v1`；输出 `C1_REGISTRY_PRESENT`；checker 退出码 0。任一失败时停止并返回 C1 补充登记，不在 C7 修改契约或 registry。

- [ ] **Step 3: 确认 C4/C5/C6 迁移链**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run alembic heads
```

Expected: `202610220062 (head)`，只有一行。失败时停止，先完成 C6。

- [ ] **Step 3b: 确认 C2 内部审核、统一审计与项目 ACL 接口**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run python -c "
from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.reviewer_assignments import (
    REVIEWER_SCOPE_READ,
    REVIEWER_SCOPE_REVIEW,
    ReviewerAssignment,
    get_active_reviewer_assignment,
    grant_reviewer_assignment,
)
from data_intelligence_hub.models.workbench import PACKAGE_TYPES, WorkbenchTask
assert REVIEWER_SCOPE_READ == 'report_read'
assert REVIEWER_SCOPE_REVIEW == 'report_review'
assert set(PACKAGE_TYPES) == {'quick', 'standard'}
print('C2_ACL_AUDIT_REVIEWER_OK')
"
cd /Users/lute/Project/data_scrapy-gov-c7 && python3 -I -c "
import json
from pathlib import Path
registry = json.loads(Path('configs/contracts/v1.1.0/registry.json').read_text(encoding='utf-8'))
names = {table['name'] for table in registry['tables']}
assert 'report_reviewer_assignments' in names, sorted(names)
scope = next(
    item for item in registry['enums']
    if item['name'] == 'report_reviewer_assignments.assignment_scope'
)
assert set(scope['values']) == {'report_read', 'report_review'}, scope['values']
print('C1_REVIEWER_REGISTRY_OK')
"
```

Expected: `C2_ACL_AUDIT_REVIEWER_OK`；`C1_REVIEWER_REGISTRY_OK`。任一失败时停止：审核指派表或 `assignment_scope` 属 C1 登记、C2 实现；审计与 ACL 属 C2。C7 不创建这些表或服务，只按上述接口消费；接口名与 C1/C2 修复后的计划不一致时，先对齐名称再编码。

- [ ] **Step 4: GitNexus 影响面预检**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
test -f .gitnexus/run.cjs || bunx gitnexus@latest analyze
node .gitnexus/run.cjs impact "create_claim_with_evidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "Claim" --direction upstream --repo .
node .gitnexus/run.cjs impact "Evidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "max_claim_status_for_grade" --direction upstream --repo .
```

Expected: 每条命令退出码 0 并打印风险等级。`risk: HIGH` 或 `CRITICAL` 时停止并写缓解方案；`risk: UNKNOWN` 时执行 `git grep -n "create_claim_with_evidence\|class Claim\|class Evidence\|max_claim_status_for_grade" apps/api/src apps/api/tests` 确认调用方，不能当作安全。

- [ ] **Step 5: 记录基线测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claims.py -q
```

Expected: `21 passed`。不是 21 时停止，先修基线。

---

### Task 1: C1 registry 只读守卫

**Files:**
- Test: `apps/api/tests/unit/test_claim_contract_freeze.py`

**Interfaces:**
- Consumes: C1 的 `configs/contracts/v1.1.0/registry.json`、`SCHEMA_VERSION`、`CANONICAL_PROFILE_ID`、`canonical_json_bytes`；`ReportContract.claims[]` 已含 `text_en/risk_flags/review_status/independent_source_count/blocked_reason`。
- Produces: 只读登记守卫测试；C7 不修改契约文档与 registry。缺任一登记项时停止并返回 C1。

- [ ] **Step 1: 写只读守卫测试**

```python
"""C7：C1 registry 与 C1 常量的只读守卫。

本测试只读 C1 的机器 registry 与报告合同常量。它不修改契约文档，
不修改 registry，不写业务数据。
"""

from __future__ import annotations

import json
from pathlib import Path

from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    SCHEMA_VERSION,
    ReportContract,
    canonical_json_bytes,
)

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
REGISTRY = REPO_ROOT / "configs/contracts/v1.1.0/registry.json"

CLAIM_COLUMNS = (
    "text_en",
    "scope_window_start",
    "scope_window_end",
    "risk_flags",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "reviewed_content_version",
    "reviewed_payload_sha256",
    "reviewed_profile",
    "second_reviewed_by",
    "second_reviewed_at",
    "review_note",
    "content_version",
    "independent_source_count",
    "blocked_reason",
    "review_history",
)
CLAIM_EVIDENCE_COLUMNS = (
    "evidence_grade",
    "source_cluster_key",
    "source_cluster_basis",
    "independent",
)
EVIDENCE_COLUMNS = (
    "workspace_id",
    "project_id",
    "evidence_grade",
    "market",
    "locale",
    "source_tool_id",
    "provider_id",
    "captured_at",
    "source_cluster_key",
    "source_cluster_basis",
)
REQUIRED_ENUMS = {
    "claim_review_status",
    "claim_risk_flags",
    "claims.blocked_reason",
    "source_cluster_basis",
    "report_reviewer_assignments.assignment_scope",
}
REQUIRED_ERROR_CODES = {
    "claim_not_found",
    "claim_blocked_reason_required",
    "claim_scope_invalid",
    "claim_grade_below_minimum",
    "claim_grade_exceeds_evidence",
    "claim_state_exceeds_grade",
    "claim_confirmation_requires_review",
    "claim_market_unsupported",
    "claim_evidence_not_found",
    "claim_review_transition_invalid",
    "claim_second_review_required",
    "claim_second_reviewer_invalid",
    "claim_bundle_not_publishable",
    "reviewer_assignment_required",
    "reviewer_self_review_forbidden",
    "reviewer_assignment_invalid",
    "project_not_found",
    "project_access_forbidden",
}
REQUIRED_PATH_ERRORS = {
    "claims.list": {"project_not_found", "project_access_forbidden"},
    "claims.detail": {"project_not_found", "project_access_forbidden"},
}
REQUIRED_CONSTRAINTS = {
    "ck_claims_evidence_grade_min",
    "ck_claims_state_grade_ceiling",
    "ck_claims_review_status",
    "ck_claims_review_coherence",
    "ck_claims_confirmed_review",
    "ck_claims_content_version",
    "ck_claims_reviewed_version",
    "ck_claims_independent_count",
    "ck_claims_scope_window",
    "ck_claims_scope_days",
    "ck_claims_scope_sample",
    "ck_claims_blocked_reason",
    "ck_claims_blocked_state",
    "ck_claims_second_review_pair",
    "ck_claims_reviewer_differ",
    "ck_claim_evidence_evidence_grade",
    "ck_claim_evidence_source_cluster_basis",
    "ck_claim_evidence_independent_cluster",
    "ck_evidences_evidence_grade",
    "ck_evidences_source_cluster_basis",
    "ck_evidences_source_cluster_coherence",
    "ck_evidences_workspace_project_pair",
}


def load_registry() -> dict:
    if not REGISTRY.exists():
        raise AssertionError(
            "C1 registry 缺失：configs/contracts/v1.1.0/registry.json；返回 C1"
        )
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def table(name: str) -> dict:
    return next(item for item in load_registry()["tables"] if item["name"] == name)


def enum_names() -> set[str]:
    return {item["name"] for item in load_registry()["enums"]}


def enum_values(name: str) -> set[str]:
    return set(next(item for item in load_registry()["enums"] if item["name"] == name)["values"])


def path_error_codes(path_id: str) -> set[str]:
    paths = {item["id"]: item for item in load_registry()["paths"]}
    return set(paths[path_id]["error_codes"])


def test_c1_registry_registers_claim_columns() -> None:
    columns = {column["name"] for column in table("claims")["columns"]}
    assert set(CLAIM_COLUMNS) <= columns


def test_c1_registry_registers_claim_evidence_columns() -> None:
    columns = {column["name"] for column in table("claim_evidence")["columns"]}
    assert set(CLAIM_EVIDENCE_COLUMNS) <= columns


def test_c1_registry_registers_evidence_columns() -> None:
    columns = {column["name"] for column in table("evidences")["columns"]}
    assert set(EVIDENCE_COLUMNS) <= columns


def test_c1_registry_registers_claim_enums() -> None:
    assert REQUIRED_ENUMS <= enum_names()


def test_c1_registry_registers_constraint_names() -> None:
    registered: set[str] = set()
    for name in ("claims", "claim_evidence", "evidences"):
        registered.update(table(name).get("constraints", []))
    assert REQUIRED_CONSTRAINTS <= registered


def test_c1_registry_registers_reviewer_assignments() -> None:
    names = {item["name"] for item in load_registry()["tables"]}
    assert "report_reviewer_assignments" in names
    assert enum_values("report_reviewer_assignments.assignment_scope") == {
        "report_read",
        "report_review",
    }


def test_c1_registry_registers_claim_error_codes() -> None:
    codes = {item["code"] for item in load_registry()["error_codes"]}
    assert REQUIRED_ERROR_CODES <= codes


def test_c1_claim_paths_register_project_acl_errors() -> None:
    for path_id, required in REQUIRED_PATH_ERRORS.items():
        assert required <= path_error_codes(path_id), path_id
    assert "claim_not_found" in path_error_codes("claims.detail")


def test_c1_frozen_schema_and_profile() -> None:
    assert SCHEMA_VERSION == "1.1.0"
    assert CANONICAL_PROFILE_ID == "dih-canonical-json-v1"
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_c1_claim_contract_has_governance_fields() -> None:
    fields = ReportContract.model_fields["claims"].annotation
    claim_model = fields.__args__[0]
    for name in (
        "text_en",
        "risk_flags",
        "review_status",
        "independent_source_count",
        "blocked_reason",
    ):
        assert name in claim_model.model_fields, name


def test_c1_claim_contract_has_nested_scope_and_owner() -> None:
    fields = ReportContract.model_fields["claims"].annotation
    claim_model = fields.__args__[0]
    for name in ("scope", "owner", "review_status", "blocked_reason"):
        assert name in claim_model.model_fields, name
    scope_annotation = claim_model.model_fields["scope"].annotation
    scope_model = next(
        argument
        for argument in getattr(scope_annotation, "__args__", (scope_annotation,))
        if argument is not type(None)
    )
    for name in ("market", "window", "sample_n"):
        assert name in scope_model.model_fields, name
```

- [ ] **Step 2: 运行测试，确认 C1 登记齐全**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_contract_freeze.py -q
```

Expected: `11 passed`。任一断言失败表示 C1 registry 缺项（列、枚举、约束名、审核指派表/枚举、Claim 错误码或路径 ACL 错误码）；此时停止 C7，把缺失项清单返回 C1 补充登记，不得修改契约文档、registry 或用代码绕过。

- [ ] **Step 3: 处理缺项（不写契约）**

若 Step 2 失败，按失败断言列出缺失的列、枚举、约束名、审核指派登记、错误码或常量，返回 C1。C7 必须把以下登记项作为 C1 前置：`report_reviewer_assignments` 表与 `report_reviewer_assignments.assignment_scope`（`report_read`、`report_review`）；`claims.list` 与 `claims.detail` 的 `project_not_found`、`project_access_forbidden`；`REQUIRED_ERROR_CODES` 中的全部错误码；正文写明 `GET /api/claims` 的 `project_id` 必填。C7 不得：

- 修改 `docs/design/【契约冻结】v1-表名-枚举-接口.md`。
- 修改或重新生成 `configs/contracts/v1.1.0/registry.json`。
- 在 C7 内追加“实现决定”或本地契约副本。

C1 补齐并重新生成 registry 后，从 Step 2 重跑。

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_contract_freeze.py -q
```

Expected: `11 passed`。这是只读守卫；C7 没有修改契约文档或 registry。

- [ ] **Step 5: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_claim_contract_freeze.py
git commit -m "test(claims): 守卫 c1 registry 的 claim 登记"
```

---

### Task 2: 独立来源簇纯函数

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/source_clusters.py`
- Test: `apps/api/tests/unit/test_source_clusters.py`

**Interfaces:**
- Consumes: `Evidence.url`、`Evidence.provider_id`、`Evidence.reference_metadata`；`RawRecord.content_hash`、`RawRecord.source_url`。
- Produces: `ClusterBasis`、`SourceCluster`、`LinkCluster`、`normalise_url()`、`resolve_source_cluster()`、`assign_link_clusters()`。

- [ ] **Step 1: 写失败测试**

```python
"""C7：独立来源簇。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from data_intelligence_hub.services.source_clusters import (
    ClusterBasis,
    SourceCluster,
    assign_link_clusters,
    normalise_url,
    resolve_source_cluster,
)

HASH_A = "a" * 64
HASH_B = "b" * 64


@dataclass
class StubEvidence:
    id: uuid.UUID
    url: str | None = None
    provider_id: str | None = None
    reference_metadata: dict[str, object] | None = None


@dataclass
class StubRawRecord:
    content_hash: str
    source_url: str | None = None


def _evidence(**kwargs: object) -> StubEvidence:
    return StubEvidence(id=uuid.uuid4(), **kwargs)


def test_normalise_url_strips_tracking_and_sorts_query() -> None:
    assert (
        normalise_url("HTTPS://Example.COM:443/a/?utm_source=x&b=2&a=1#frag")
        == "https://example.com/a?a=1&b=2"
    )
    assert normalise_url("not-a-url") is None
    assert normalise_url("ftp://example.com/a") is None


def test_content_hash_wins_over_url() -> None:
    evidence = _evidence(url="https://example.com/a")
    cluster = resolve_source_cluster(
        evidence, StubRawRecord(content_hash=HASH_A, source_url="https://example.com/b")
    )
    assert cluster == SourceCluster(key=f"content:{HASH_A}", basis=ClusterBasis.CONTENT_HASH)


def test_explicit_cluster_key_wins() -> None:
    evidence = _evidence(
        url="https://example.com/a",
        reference_metadata={"source_cluster_key": "tiktok:item:1", "content_hash": HASH_A},
    )
    cluster = resolve_source_cluster(evidence)
    assert cluster == SourceCluster(key="explicit:tiktok:item:1", basis=ClusterBasis.EXPLICIT)


def test_platform_item_merges_different_endpoints() -> None:
    first = _evidence(reference_metadata={"platform": "tiktok", "item_id": "123"})
    second = _evidence(
        url="https://example.com/other",
        reference_metadata={"platform": "tiktok", "item_id": "123"},
    )
    assert resolve_source_cluster(first) == resolve_source_cluster(second)
    assert resolve_source_cluster(first).basis is ClusterBasis.PLATFORM_ITEM


def test_url_merges_same_page_with_tracking() -> None:
    first = _evidence(url="https://example.com/p/1?utm_source=a")
    second = _evidence(url="https://EXAMPLE.com/p/1/#x")
    assert resolve_source_cluster(first) == resolve_source_cluster(second)
    assert resolve_source_cluster(first).basis is ClusterBasis.URL


def test_translation_without_explicit_key_is_not_merged() -> None:
    english = _evidence(url="https://example.com/en/p/1")
    chinese = _evidence(url="https://example.com/zh/p/1")
    assert resolve_source_cluster(english).key != resolve_source_cluster(chinese).key


def test_unresolved_is_not_independent() -> None:
    cluster = resolve_source_cluster(_evidence())
    assert cluster.key is None
    assert cluster.basis is ClusterBasis.UNRESOLVED
    assert cluster.independent is False


def test_assign_marks_only_first_link_of_cluster_independent() -> None:
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assigned = assign_link_clusters(
        [
            (first, SourceCluster("content:a", ClusterBasis.CONTENT_HASH)),
            (second, SourceCluster("content:a", ClusterBasis.CONTENT_HASH)),
            (third, SourceCluster("content:b", ClusterBasis.CONTENT_HASH)),
        ]
    )
    assert [link.independent for link in assigned] == [True, False, True]
    assert [link.key for link in assigned] == ["content:a", "content:a", "content:b"]


def test_two_api_keys_do_not_change_cluster() -> None:
    first = _evidence(reference_metadata={"content_hash": HASH_A})
    second = _evidence(reference_metadata={"content_hash": HASH_A, "api_key_id": "other"})
    assert resolve_source_cluster(first) == resolve_source_cluster(second)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_source_clusters.py -q
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.source_clusters`。

- [ ] **Step 3: 实现纯函数模块**

创建 `apps/api/src/data_intelligence_hub/services/source_clusters.py`：

```python
"""独立来源簇：按原始记录身份归并证据。

设计 5.4：独立来源按原始记录簇计算，不按端点数量计算。
同一 provider 的不同端点、同一端点的多次调用、同一页面的多条抓取路径、
同一记录的翻译、转载、不同导出格式和两把不同 API Key 都只能算一个来源。

本模块是纯函数层。它不读库、不联网、不读时钟。
显式簇键优先。采集器识别翻译、转载、导出副本时必须写
``reference_metadata['source_cluster_key']``。没有显式键时，按
content_hash、平台对象 ID、规范化 URL 依次推导。推导不出的证据不算独立来源。
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_HEX64 = re.compile(r"[0-9a-f]{64}")
_TRACKING_PARAMS = frozenset(
    {"gclid", "fbclid", "msclkid", "yclid", "igshid", "mc_cid", "mc_eid", "spm", "scm"}
)
_TRACKING_PREFIXES = ("utm_",)
_PLATFORM_ID_KEYS = (
    "item_id",
    "aweme_id",
    "note_id",
    "video_id",
    "product_id",
    "sku_id",
    "post_id",
    "tweet_id",
)


class ClusterBasis(StrEnum):
    EXPLICIT = "explicit"
    CONTENT_HASH = "content_hash"
    PLATFORM_ITEM = "platform_item"
    URL = "url"
    UNRESOLVED = "unresolved"


class EvidenceLike(Protocol):
    id: uuid.UUID
    url: str | None
    provider_id: str | None
    reference_metadata: Mapping[str, Any] | None


class RawRecordLike(Protocol):
    content_hash: str
    source_url: str | None


@dataclass(frozen=True, slots=True)
class SourceCluster:
    key: str | None
    basis: ClusterBasis

    @property
    def independent(self) -> bool:
        return self.key is not None


@dataclass(frozen=True, slots=True)
class LinkCluster:
    evidence_id: uuid.UUID
    key: str | None
    basis: ClusterBasis
    independent: bool


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _first_text(metadata: Mapping[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        found = _text(metadata.get(key))
        if found is not None:
            return found
    return None


def normalise_url(value: str) -> str | None:
    """规范化 URL。只接受 http/https 绝对地址。

    去掉 fragment 与已知跟踪参数；保留路径大小写；主机名小写；
    查询参数按键值排序；去掉默认端口与末尾斜杠。
    """
    text = value.strip()
    if not text:
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    host = parts.hostname.lower()
    netloc = host if port in {None, 80, 443} else f"{host}:{port}"
    pairs = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
        and not key.lower().startswith(_TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(pairs))
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, query, ""))


def resolve_source_cluster(
    evidence: EvidenceLike,
    raw_record: RawRecordLike | None = None,
) -> SourceCluster:
    """按固定优先级推导证据的原始记录簇。"""
    metadata: Mapping[str, Any] = evidence.reference_metadata or {}
    explicit = _first_text(metadata, ("source_cluster_key", "cluster_key"))
    if explicit is not None:
        return SourceCluster(f"explicit:{explicit}", ClusterBasis.EXPLICIT)

    content_hash = _text(getattr(raw_record, "content_hash", None)) or _text(
        metadata.get("content_hash")
    )
    if content_hash is not None and _HEX64.fullmatch(content_hash.lower()):
        return SourceCluster(f"content:{content_hash.lower()}", ClusterBasis.CONTENT_HASH)

    platform = _first_text(metadata, ("platform", "provider_id")) or _text(evidence.provider_id)
    item_id = _first_text(metadata, _PLATFORM_ID_KEYS)
    if item_id is not None:
        return SourceCluster(
            f"item:{platform or 'unknown'}:{item_id}",
            ClusterBasis.PLATFORM_ITEM,
        )

    url = _text(evidence.url) or _text(getattr(raw_record, "source_url", None))
    normalised = normalise_url(url) if url is not None else None
    if normalised is not None:
        return SourceCluster(f"url:{normalised}", ClusterBasis.URL)

    return SourceCluster(None, ClusterBasis.UNRESOLVED)


def assign_link_clusters(
    pairs: Iterable[tuple[uuid.UUID, SourceCluster]],
) -> list[LinkCluster]:
    """给一组证据分配独立性。同一簇只有第一条算独立来源。"""
    seen: set[str] = set()
    assigned: list[LinkCluster] = []
    for evidence_id, cluster in pairs:
        key = cluster.key
        independent = key is not None and key not in seen
        if key is not None:
            seen.add(key)
        assigned.append(
            LinkCluster(
                evidence_id=evidence_id,
                key=key,
                basis=cluster.basis,
                independent=independent,
            )
        )
    return assigned


__all__ = [
    "ClusterBasis",
    "EvidenceLike",
    "LinkCluster",
    "RawRecordLike",
    "SourceCluster",
    "assign_link_clusters",
    "normalise_url",
    "resolve_source_cluster",
]
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_source_clusters.py -q
```

Expected: `9 passed`。

- [ ] **Step 5: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "Evidence" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/source_clusters.py apps/api/tests/unit/test_source_clusters.py
git commit -m "feat(claims): 独立来源簇按原始记录归并"
```

`impact` 若报 `risk: HIGH` 或 `CRITICAL`，停止并先写缓解说明。`detect-changes` 出现 `partial: true` 或 `truncated: true` 时重跑。

---

### Task 3: 证据等级下限、状态上限与正式市场策略

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/claims.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Create: `apps/api/src/data_intelligence_hub/tool_catalog/markets.py`
- Test: `apps/api/tests/unit/test_claim_evidence_policy.py`

**Interfaces:**
- Consumes: B5 `schemas.report_contract.max_claim_status_for_grade()`、`tool_catalog.evidence_grade.GRADE_ORDER`、`models.claim.ClaimState`。
- Produces:
  - `MIN_CLAIM_GRADE`
  - `assert_claim_grade_at_least_l2(grade)`
  - `assert_claim_state_within_grade(state, grade)`
  - `assert_confirmed_requirements(state, grade, independent_source_count, review_status)`
  - `normalise_risk_flags(flags)`
  - `assert_formal_market(market)`
  - `assert_scope_window(start, end, days, sample_n)`

- [ ] **Step 1: 写失败测试**

```python
"""C7：证据等级下限、状态上限、市场与风险标记。"""

from __future__ import annotations

from datetime import date

import pytest

from data_intelligence_hub.models.claim import ClaimReviewStatus, ClaimRiskFlag, ClaimState
from data_intelligence_hub.services.claims import (
    assert_claim_grade_at_least_l2,
    assert_claim_state_within_grade,
    assert_confirmed_requirements,
    assert_formal_market,
    assert_scope_window,
    normalise_risk_flags,
)
from data_intelligence_hub.services.exceptions import (
    ClaimGradeBelowMinimumError,
    ClaimMarketUnsupportedError,
    ClaimScopeInvalidError,
    ClaimStateExceedsGradeError,
    ClaimConfirmationRequiresReviewError,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
from data_intelligence_hub.tool_catalog.markets import FORMAL_MARKETS


def test_eleven_formal_markets_are_frozen() -> None:
    assert FORMAL_MARKETS == (
        "US", "GB", "DE", "FR", "IT", "ES", "IE", "NL", "BE", "AT", "PL"
    )
    assert assert_formal_market("US") == "US"
    with pytest.raises(ClaimMarketUnsupportedError):
        assert_formal_market("XX")


@pytest.mark.parametrize("grade", [EvidenceGrade.L0_UNVERIFIED, EvidenceGrade.L1_CONTRACT])
def test_l0_and_l1_are_rejected(grade: EvidenceGrade) -> None:
    with pytest.raises(ClaimGradeBelowMinimumError):
        assert_claim_grade_at_least_l2(grade)


@pytest.mark.parametrize(
    ("grade", "allowed_state"),
    [
        (EvidenceGrade.L2_FIXTURE_LOCAL, ClaimState.HYPOTHESIS),
        (EvidenceGrade.L3_LIVE_SINGLE, ClaimState.DIRECTIONAL),
        (EvidenceGrade.L4_AUTHORIZED_LIVE, ClaimState.CONFIRMED),
    ],
)
def test_state_ceiling(grade: EvidenceGrade, allowed_state: ClaimState) -> None:
    assert_claim_state_within_grade(allowed_state, grade)
    if allowed_state is ClaimState.HYPOTHESIS:
        with pytest.raises(ClaimStateExceedsGradeError):
            assert_claim_state_within_grade(ClaimState.DIRECTIONAL, grade)
    if allowed_state is ClaimState.DIRECTIONAL:
        with pytest.raises(ClaimStateExceedsGradeError):
            assert_claim_state_within_grade(ClaimState.CONFIRMED, grade)


def test_evidence_gap_and_blocked_are_allowed_at_any_claim_grade() -> None:
    for state in (ClaimState.EVIDENCE_GAP, ClaimState.BLOCKED):
        assert_claim_state_within_grade(state, EvidenceGrade.L2_FIXTURE_LOCAL)


def test_confirmed_requires_l4_two_sources_and_approval() -> None:
    assert_confirmed_requirements(
        ClaimState.CONFIRMED,
        EvidenceGrade.L4_AUTHORIZED_LIVE,
        2,
        ClaimReviewStatus.APPROVED,
    )
    with pytest.raises(ClaimStateExceedsGradeError):
        assert_confirmed_requirements(
            ClaimState.CONFIRMED,
            EvidenceGrade.L4_AUTHORIZED_LIVE,
            1,
            ClaimReviewStatus.APPROVED,
        )
    with pytest.raises(ClaimConfirmationRequiresReviewError):
        assert_confirmed_requirements(
            ClaimState.CONFIRMED,
            EvidenceGrade.L4_AUTHORIZED_LIVE,
            2,
            ClaimReviewStatus.DRAFT,
        )


def test_risk_flags_are_closed_set_and_single_source_is_auto_added() -> None:
    flags = normalise_risk_flags([ClaimRiskFlag.MEDICAL, "single_source"], independent_count=1)
    assert flags == {ClaimRiskFlag.MEDICAL, ClaimRiskFlag.SINGLE_SOURCE}
    assert normalise_risk_flags([], independent_count=2) == set()
    with pytest.raises(ValueError):
        normalise_risk_flags(["unknown_flag"], independent_count=2)


def test_scope_window_is_inclusive_and_ordered() -> None:
    assert_scope_window(date(2026, 1, 1), date(2026, 3, 1), 60, 0)
    with pytest.raises(ClaimScopeInvalidError):
        assert_scope_window(date(2026, 3, 1), date(2026, 1, 1), 60, 0)
    with pytest.raises(ClaimScopeInvalidError):
        assert_scope_window(date(2026, 1, 1), date(2026, 3, 1), 59, 0)
    with pytest.raises(ClaimScopeInvalidError):
        assert_scope_window(date(2026, 1, 1), date(2026, 3, 1), 60, -1)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_evidence_policy.py -q
```

Expected: FAIL，`ImportError: cannot import name 'assert_claim_grade_at_least_l2'`，`ModuleNotFoundError: tool_catalog.markets`。

- [ ] **Step 3: 实现策略与市场常量**

创建 `apps/api/src/data_intelligence_hub/tool_catalog/markets.py`：

```python
"""正式市场目录。设计 §2.4。

core 6 个，supported 5 个，共 11 个。顺序固定。
未取得逐市场书面证据前，不得把其他市场加入本表。
"""

from __future__ import annotations

from typing import Final

CORE_MARKETS: Final[tuple[str, ...]] = ("US", "GB", "DE", "FR", "IT", "ES")
SUPPORTED_MARKETS: Final[tuple[str, ...]] = ("IE", "NL", "BE", "AT", "PL")
FORMAL_MARKETS: Final[tuple[str, ...]] = CORE_MARKETS + SUPPORTED_MARKETS


def is_formal_market(value: str) -> bool:
    return value in FORMAL_MARKETS


__all__ = ["CORE_MARKETS", "FORMAL_MARKETS", "SUPPORTED_MARKETS", "is_formal_market"]
```

在 `models/claim.py` 的 `EvidenceRole` 之后追加以下枚举。Task 4 只加列与 CHECK，不重复定义：

```python
class ClaimReviewStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"


class ClaimRiskFlag(StrEnum):
    MEDICAL = "medical"
    HEALTH = "health"
    SAFETY = "safety"
    LEGAL = "legal"
    RECALL = "recall"
    CHILDREN = "children"
    CAUSAL_LANGUAGE = "causal_language"
    SINGLE_SOURCE = "single_source"
    PRICE_COMPARISON = "price_comparison"


class ClaimBlockedReason(StrEnum):
    RIGHTS = "rights"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"
    GATE = "gate"
    UPSTREAM = "upstream"


SECOND_REVIEW_RISK_FLAGS = frozenset(
    {
        ClaimRiskFlag.MEDICAL,
        ClaimRiskFlag.HEALTH,
        ClaimRiskFlag.SAFETY,
        ClaimRiskFlag.LEGAL,
        ClaimRiskFlag.RECALL,
        ClaimRiskFlag.CHILDREN,
    }
)
```

在 `services/exceptions.py` 末尾追加：

```python
class ClaimGradeBelowMinimumError(ServiceError):
    message = "claim_grade_below_minimum"

    def __init__(self, grade: str) -> None:
        super().__init__(self.message)
        self.grade = grade


class ClaimGradeExceedsEvidenceError(ServiceError):
    message = "claim_grade_exceeds_evidence"

    def __init__(self, claim_grade: str, evidence_grade: str) -> None:
        super().__init__(self.message)
        self.claim_grade = claim_grade
        self.evidence_grade = evidence_grade


class ClaimStateExceedsGradeError(ServiceError):
    message = "claim_state_exceeds_grade"

    def __init__(self, state: str, ceiling: str) -> None:
        super().__init__(self.message)
        self.state = state
        self.ceiling = ceiling


class ClaimConfirmationRequiresReviewError(ServiceError):
    message = "claim_confirmation_requires_review"


class ClaimMarketUnsupportedError(ServiceError):
    message = "claim_market_unsupported"

    def __init__(self, market: str) -> None:
        super().__init__(self.message)
        self.market = market


class ClaimScopeInvalidError(ServiceError):
    message = "claim_scope_invalid"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ClaimReviewerAssignmentRequiredError(ServiceError):
    message = "reviewer_assignment_required"


class ClaimReviewerAssignmentInvalidError(ServiceError):
    message = "reviewer_assignment_invalid"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
```

把 `services/claims.py` 顶部的 `models.claim`、`schemas.report_contract`、`services.exceptions`、`tool_catalog.evidence_grade`、`tool_catalog.markets` 导入替换为以下完整块（保留仓储导入）：

```python
from datetime import date
from typing import Final

from data_intelligence_hub.models.claim import (
    Claim,
    ClaimBlockedReason,
    ClaimReviewStatus,
    ClaimRiskFlag,
    ClaimState,
    EvidenceRole,
)
from data_intelligence_hub.schemas.report_contract import max_claim_status_for_grade
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.exceptions import (
    ClaimConfirmationRequiresReviewError,
    ClaimCounterEvidenceRequiredError,
    ClaimGapOnlyStateInvalidError,
    ClaimGradeBelowMinimumError,
    ClaimMarketUnsupportedError,
    ClaimScopeInvalidError,
    ClaimStateExceedsGradeError,
)
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade
from data_intelligence_hub.tool_catalog.markets import is_formal_market
```

在 `services/claims.py` 的常量区追加：

```python
MIN_CLAIM_GRADE: Final[EvidenceGrade] = EvidenceGrade.L2_FIXTURE_LOCAL

_CLAIM_STATE_ORDER: Final[dict[ClaimState, int]] = {
    ClaimState.HYPOTHESIS: 0,
    ClaimState.DIRECTIONAL: 1,
    ClaimState.CONFIRMED: 2,
}

_ANY_GRADE_STATES: Final[frozenset[ClaimState]] = frozenset(
    {ClaimState.EVIDENCE_GAP, ClaimState.BLOCKED}
)


def assert_claim_grade_at_least_l2(
    grade: EvidenceGrade | str | None,
) -> EvidenceGrade | None:
    """L0/L1 不生成 Claim。None 表示草稿，留给发布门禁。"""
    if grade is None:
        return None
    value = EvidenceGrade(grade)
    if GRADE_ORDER[value] < GRADE_ORDER[MIN_CLAIM_GRADE]:
        raise ClaimGradeBelowMinimumError(value.value)
    return value


def assert_claim_state_within_grade(
    state: ClaimState | str,
    grade: EvidenceGrade | str | None,
) -> None:
    """状态不得超过该等级允许的上限。"""
    state_value = _normalise_state(state)
    if state_value in _ANY_GRADE_STATES:
        return
    if grade is None:
        if state_value is not ClaimState.HYPOTHESIS:
            raise ClaimStateExceedsGradeError(state_value.value, "none")
        return
    grade_value = EvidenceGrade(grade)
    ceiling = max_claim_status_for_grade(grade_value)
    if _CLAIM_STATE_ORDER[state_value] > _CLAIM_STATE_ORDER[ceiling]:
        raise ClaimStateExceedsGradeError(state_value.value, grade_value.value)


def assert_confirmed_requirements(
    state: ClaimState | str,
    grade: EvidenceGrade | str | None,
    independent_source_count: int,
    review_status: ClaimReviewStatus | str,
) -> None:
    """confirmed 的三重条件：L4、独立来源 ≥ 2、已审核。"""
    state_value = _normalise_state(state)
    if state_value is not ClaimState.CONFIRMED:
        return
    if grade is None or EvidenceGrade(grade) is not EvidenceGrade.L4_AUTHORIZED_LIVE:
        raise ClaimStateExceedsGradeError(
            ClaimState.CONFIRMED.value,
            grade.value if grade is not None else "none",
        )
    if independent_source_count < 2:
        raise ClaimStateExceedsGradeError(ClaimState.CONFIRMED.value, "independent_source_count<2")
    if ClaimReviewStatus(review_status) is not ClaimReviewStatus.APPROVED:
        raise ClaimConfirmationRequiresReviewError()


def normalise_risk_flags(
    flags: object,
    *,
    independent_count: int,
) -> set[ClaimRiskFlag]:
    """校验风险标记封闭集合。独立来源 < 2 时自动加 single_source。"""
    if isinstance(flags, (str, bytes)) or not hasattr(flags, "__iter__"):
        raise TypeError("risk_flags 必须是可迭代对象")
    result: set[ClaimRiskFlag] = set()
    for flag in flags:  # type: ignore[union-attr]
        result.add(ClaimRiskFlag(flag))
    if independent_count < 2:
        result.add(ClaimRiskFlag.SINGLE_SOURCE)
    return result


def assert_formal_market(market: str) -> str:
    value = market.strip()
    if not is_formal_market(value):
        raise ClaimMarketUnsupportedError(value)
    return value


def assert_scope_window(
    start: date,
    end: date,
    days: int,
    sample_n: int,
) -> None:
    if end < start:
        raise ClaimScopeInvalidError("scope_window_end 必须不早于 scope_window_start")
    if days != (end - start).days + 1:
        raise ClaimScopeInvalidError("scope_window_days 必须等于含首尾的天数")
    if sample_n < 0:
        raise ClaimScopeInvalidError("scope_sample_n 不能为负")
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_evidence_policy.py -q
```

Expected: `10 passed`。

- [ ] **Step 5: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "max_claim_status_for_grade" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_claim_with_evidence" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/tool_catalog/markets.py apps/api/src/data_intelligence_hub/services/claims.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_claim_evidence_policy.py
git commit -m "feat(claims): 冻结证据等级下限与状态上限"
```

`impact` 输出 `risk: HIGH` 或 `CRITICAL` 时停止。`risk: UNKNOWN` 时执行 `git grep -n "create_claim_with_evidence\|max_claim_status_for_grade" apps/api/src apps/api/tests`，确认调用方后再继续。

---

### Task 4: 模型与迁移 063

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/models/claim.py`
- Modify: `apps/api/src/data_intelligence_hub/models/intelligence.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/intelligence.py:191-230`
- Create: `apps/api/alembic/versions/202610220063_claim_evidence_completeness.py`
- Test: `apps/api/tests/unit/test_claim_evidence_schema.py`
- Test: `apps/api/tests/postgres/test_claim_evidence_migration.py`

**Interfaces:**
- Consumes: 契约 v1.1 的列名、枚举、约束名。
- Produces: `Claim`、`ClaimEvidence`、`Evidence` 新列与 CHECK；迁移 `202610220063`。

- [ ] **Step 1: 写失败的 schema/迁移测试**

```python
"""C7：claims / claim_evidence / evidences 的列与约束。"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

from sqlalchemy import CheckConstraint, Table

from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.intelligence import Evidence

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610220063_claim_evidence_completeness.py"

CLAIM_COLUMNS = {
    "text_en",
    "scope_window_start",
    "scope_window_end",
    "risk_flags",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "reviewed_content_version",
    "reviewed_payload_sha256",
    "reviewed_profile",
    "second_reviewed_by",
    "second_reviewed_at",
    "review_note",
    "content_version",
    "independent_source_count",
    "blocked_reason",
    "review_history",
}
CLAIM_EVIDENCE_COLUMNS = {
    "evidence_grade",
    "source_cluster_key",
    "source_cluster_basis",
    "independent",
}
EVIDENCE_COLUMNS = {
    "workspace_id",
    "project_id",
    "evidence_grade",
    "market",
    "locale",
    "source_tool_id",
    "provider_id",
    "captured_at",
    "source_cluster_key",
    "source_cluster_basis",
}
CLAIM_CHECKS = {
    "ck_claims_state",
    "ck_claims_evidence_grade",
    "ck_claims_evidence_grade_min",
    "ck_claims_state_grade_ceiling",
    "ck_claims_confidence_range",
    "ck_claims_review_status",
    "ck_claims_review_coherence",
    "ck_claims_confirmed_review",
    "ck_claims_content_version",
    "ck_claims_reviewed_version",
    "ck_claims_independent_count",
    "ck_claims_scope_window",
    "ck_claims_scope_days",
    "ck_claims_scope_sample",
    "ck_claims_blocked_reason",
    "ck_claims_blocked_state",
    "ck_claims_second_review_pair",
    "ck_claims_reviewer_differ",
}
CLAIM_EVIDENCE_CHECKS = {
    "ck_claim_evidence_role",
    "ck_claim_evidence_evidence_grade",
    "ck_claim_evidence_source_cluster_basis",
    "ck_claim_evidence_independent_cluster",
}
EVIDENCE_CHECKS = {
    "ck_evidences_evidence_grade",
    "ck_evidences_source_cluster_basis",
    "ck_evidences_source_cluster_coherence",
    "ck_evidences_workspace_project_pair",
}


def test_claim_columns_exist() -> None:
    assert CLAIM_COLUMNS <= set(Claim.__table__.columns.keys())


def test_claim_evidence_columns_exist() -> None:
    assert CLAIM_EVIDENCE_COLUMNS <= set(ClaimEvidence.__table__.columns.keys())


def test_evidence_columns_exist_and_intelligence_is_nullable() -> None:
    assert EVIDENCE_COLUMNS <= set(Evidence.__table__.columns.keys())
    assert Evidence.__table__.columns["intelligence_id"].nullable is True


def _model_checks(table: Table) -> set[str]:
    return {
        str(constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_model_check_names() -> None:
    assert _model_checks(Claim.__table__) == CLAIM_CHECKS
    assert _model_checks(ClaimEvidence.__table__) == CLAIM_EVIDENCE_CHECKS
    assert _model_checks(Evidence.__table__) == EVIDENCE_CHECKS


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("c7_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202610220063"
    assert module.down_revision == "202610220062"
    assert "This revision is source-only." in (module.__doc__ or "")


def test_migration_adds_every_column() -> None:
    source = inspect.getsource(_load_migration())
    for table, columns in (
        ("claims", CLAIM_COLUMNS),
        ("claim_evidence", CLAIM_EVIDENCE_COLUMNS),
        ("evidences", EVIDENCE_COLUMNS),
    ):
        assert f'add_column("{table}"' in source or f"add_column(\n        \"{table}\"" in source
        for column in columns:
            assert f'"{column}"' in source, (table, column)


def test_migration_check_names_match_models() -> None:
    source = inspect.getsource(_load_migration())
    existing_claim_checks = {
        "ck_claims_state",
        "ck_claims_evidence_grade",
        "ck_claims_confidence_range",
    }
    existing_claim_evidence_checks = {"ck_claim_evidence_role"}
    for name in CLAIM_CHECKS - existing_claim_checks:
        assert f'"{name}"' in source, name
    for name in CLAIM_EVIDENCE_CHECKS - existing_claim_evidence_checks:
        assert f'"{name}"' in source, name
    for name in EVIDENCE_CHECKS:
        assert f'"{name}"' in source, name


def test_migration_downgrade_drops_new_columns() -> None:
    source = inspect.getsource(_load_migration())
    for column in (*CLAIM_COLUMNS, *CLAIM_EVIDENCE_COLUMNS, *EVIDENCE_COLUMNS):
        assert f'"{column}"' in source
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_evidence_schema.py -q
```

Expected: FAIL，`FileNotFoundError: 202610220063_claim_evidence_completeness.py`；模型缺新列。

- [ ] **Step 3: 修改模型**

`models/claim.py` 保留 Task 3 已加入的枚举；只替换导入块、`Claim.__table_args__`、`Claim` 列区、`ClaimEvidence.__table_args__`、`ClaimEvidence` 列区。导入块改为：

```python
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin
```

保留 `ClaimState`、`EvidenceRole`、`ClaimReviewStatus`、`ClaimRiskFlag`、`ClaimBlockedReason`、`SECOND_REVIEW_RISK_FLAGS`。从下面这行开始追加 CHECK 常量：

```python
_CLAIM_STATE_CHECK = (
    "state IN ('confirmed', 'directional', 'hypothesis', 'evidence_gap', 'blocked')"
)
_CLAIM_GRADE_CHECK = (
    "evidence_grade IS NULL OR evidence_grade IN ('L0_unverified', 'L1_contract', "
    "'L2_fixture_local', 'L3_live_single', 'L4_authorized_live')"
)
_CLAIM_GRADE_MIN_CHECK = (
    "evidence_grade IS NULL OR evidence_grade IN "
    "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live')"
)
_CLAIM_STATE_GRADE_CEILING_CHECK = (
    "evidence_grade IS NULL OR "
    "(state = 'confirmed' AND evidence_grade = 'L4_authorized_live') OR "
    "(state = 'directional' AND evidence_grade IN ('L3_live_single', 'L4_authorized_live')) OR "
    "(state = 'hypothesis' AND evidence_grade IN "
    "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live')) OR "
    "(state IN ('evidence_gap', 'blocked') AND evidence_grade IN "
    "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live'))"
)
_CLAIM_CONFIDENCE_CHECK = "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"
_CLAIM_REVIEW_STATUS_CHECK = (
    "review_status IN ('draft', 'pending', 'approved', 'rejected', 'stale')"
)
_CLAIM_REVIEW_COHERENCE_CHECK = (
    "review_status <> 'approved' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL "
    "AND reviewed_content_version IS NOT NULL AND reviewed_payload_sha256 IS NOT NULL "
    "AND reviewed_profile IS NOT NULL)"
)
_CLAIM_CONFIRMED_REVIEW_CHECK = (
    "state <> 'confirmed' OR (review_status = 'approved' "
    "AND reviewed_content_version = content_version)"
)
_CLAIM_CONTENT_VERSION_CHECK = "content_version >= 1"
_CLAIM_REVIEWED_VERSION_CHECK = (
    "reviewed_content_version IS NULL OR "
    "(reviewed_content_version >= 1 AND reviewed_content_version <= content_version)"
)
_CLAIM_INDEPENDENT_COUNT_CHECK = "independent_source_count >= 0"
_CLAIM_SCOPE_WINDOW_CHECK = (
    "scope_window_start IS NULL OR scope_window_end IS NULL "
    "OR scope_window_end >= scope_window_start"
)
_CLAIM_SCOPE_DAYS_CHECK = "scope_window_days IS NULL OR scope_window_days >= 1"
_CLAIM_SCOPE_SAMPLE_CHECK = "scope_sample_n IS NULL OR scope_sample_n >= 0"
_CLAIM_BLOCKED_REASON_CHECK = (
    "blocked_reason IS NULL OR blocked_reason IN "
    "('rights', 'permission', 'configuration', 'gate', 'upstream')"
)
_CLAIM_BLOCKED_STATE_CHECK = "state <> 'blocked' OR blocked_reason IS NOT NULL"
_CLAIM_SECOND_REVIEW_PAIR_CHECK = (
    "(second_reviewed_by IS NULL) = (second_reviewed_at IS NULL)"
)
_CLAIM_REVIEWER_DIFFER_CHECK = (
    "second_reviewed_by IS NULL OR reviewed_by IS NULL OR second_reviewed_by <> reviewed_by"
)
_ROLE_CHECK = "role IN ('support', 'counter', 'context', 'gap')"
_CLAIM_EVIDENCE_GRADE_CHECK = (
    "evidence_grade IS NULL OR evidence_grade IN "
    "('L0_unverified', 'L1_contract', 'L2_fixture_local', "
    "'L3_live_single', 'L4_authorized_live')"
)
_CLAIM_EVIDENCE_BASIS_CHECK = (
    "source_cluster_basis IS NULL OR source_cluster_basis IN "
    "('explicit', 'content_hash', 'platform_item', 'url', 'unresolved')"
)
_CLAIM_EVIDENCE_INDEPENDENT_CHECK = (
    "independent = false OR source_cluster_key IS NOT NULL"
)
```

`Claim.__table_args__` 替换为：

```python
    __table_args__ = (
        CheckConstraint(_CLAIM_STATE_CHECK, name=conv("ck_claims_state")),
        CheckConstraint(_CLAIM_GRADE_CHECK, name=conv("ck_claims_evidence_grade")),
        CheckConstraint(_CLAIM_GRADE_MIN_CHECK, name=conv("ck_claims_evidence_grade_min")),
        CheckConstraint(
            _CLAIM_STATE_GRADE_CEILING_CHECK,
            name=conv("ck_claims_state_grade_ceiling"),
        ),
        CheckConstraint(_CLAIM_CONFIDENCE_CHECK, name=conv("ck_claims_confidence_range")),
        CheckConstraint(_CLAIM_REVIEW_STATUS_CHECK, name=conv("ck_claims_review_status")),
        CheckConstraint(_CLAIM_REVIEW_COHERENCE_CHECK, name=conv("ck_claims_review_coherence")),
        CheckConstraint(_CLAIM_CONFIRMED_REVIEW_CHECK, name=conv("ck_claims_confirmed_review")),
        CheckConstraint(_CLAIM_CONTENT_VERSION_CHECK, name=conv("ck_claims_content_version")),
        CheckConstraint(_CLAIM_REVIEWED_VERSION_CHECK, name=conv("ck_claims_reviewed_version")),
        CheckConstraint(_CLAIM_INDEPENDENT_COUNT_CHECK, name=conv("ck_claims_independent_count")),
        CheckConstraint(_CLAIM_SCOPE_WINDOW_CHECK, name=conv("ck_claims_scope_window")),
        CheckConstraint(_CLAIM_SCOPE_DAYS_CHECK, name=conv("ck_claims_scope_days")),
        CheckConstraint(_CLAIM_SCOPE_SAMPLE_CHECK, name=conv("ck_claims_scope_sample")),
        CheckConstraint(_CLAIM_BLOCKED_REASON_CHECK, name=conv("ck_claims_blocked_reason")),
        CheckConstraint(_CLAIM_BLOCKED_STATE_CHECK, name=conv("ck_claims_blocked_state")),
        CheckConstraint(_CLAIM_SECOND_REVIEW_PAIR_CHECK, name=conv("ck_claims_second_review_pair")),
        CheckConstraint(_CLAIM_REVIEWER_DIFFER_CHECK, name=conv("ck_claims_reviewer_differ")),
        Index("ix_claims_workspace_project", "workspace_id", "project_id"),
        Index("ix_claims_run_id", "run_id"),
        Index("ix_claims_review_status", "workspace_id", "review_status"),
        Index("ix_claims_scope_market", "scope_market"),
    )
```

`Claim` 的列区在 `counterevidence_text` 之后追加：

```python
    text_en: Mapped[str | None] = mapped_column(Text)
    scope_window_start: Mapped[date | None] = mapped_column(Date)
    scope_window_end: Mapped[date | None] = mapped_column(Date)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), default=ClaimReviewStatus.DRAFT.value, nullable=False
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_content_version: Mapped[int | None] = mapped_column(Integer)
    reviewed_payload_sha256: Mapped[str | None] = mapped_column(String(64))
    reviewed_profile: Mapped[str | None] = mapped_column(String(40))
    second_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    second_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    independent_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(40))
    review_history: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, nullable=False
    )
```

同时把 `owner` 改为可空外键（草稿可无 owner）：

```python
    owner: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
```

`ClaimEvidence.__table_args__` 替换为：

```python
    __table_args__ = (
        CheckConstraint(_ROLE_CHECK, name=conv("ck_claim_evidence_role")),
        CheckConstraint(
            _CLAIM_EVIDENCE_GRADE_CHECK,
            name=conv("ck_claim_evidence_evidence_grade"),
        ),
        CheckConstraint(
            _CLAIM_EVIDENCE_BASIS_CHECK,
            name=conv("ck_claim_evidence_source_cluster_basis"),
        ),
        CheckConstraint(
            _CLAIM_EVIDENCE_INDEPENDENT_CHECK,
            name=conv("ck_claim_evidence_independent_cluster"),
        ),
        Index("ix_claim_evidence_evidence_id", "evidence_id"),
        Index("ix_claim_evidence_source_cluster_key", "source_cluster_key"),
    )
```

`ClaimEvidence` 在 `role` 之后追加：

```python
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    source_cluster_key: Mapped[str | None] = mapped_column(String(200))
    source_cluster_basis: Mapped[str | None] = mapped_column(String(20))
    independent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

把 `__all__` 更新为包含新枚举：

```python
__all__ = [
    "Claim",
    "ClaimBlockedReason",
    "ClaimEvidence",
    "ClaimReviewStatus",
    "ClaimRiskFlag",
    "ClaimState",
    "EvidenceRole",
    "SECOND_REVIEW_RISK_FLAGS",
]
```

`models/intelligence.py` 的 `Evidence` 类替换为：

```python
class Evidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidences"
    __table_args__ = (
        CheckConstraint(
            "evidence_grade IS NULL OR evidence_grade IN "
            "('L0_unverified', 'L1_contract', 'L2_fixture_local', "
            "'L3_live_single', 'L4_authorized_live')",
            name=conv("ck_evidences_evidence_grade"),
        ),
        CheckConstraint(
            "source_cluster_basis IS NULL OR source_cluster_basis IN "
            "('explicit', 'content_hash', 'platform_item', 'url', 'unresolved')",
            name=conv("ck_evidences_source_cluster_basis"),
        ),
        CheckConstraint(
            "(source_cluster_key IS NULL AND (source_cluster_basis IS NULL "
            "OR source_cluster_basis = 'unresolved')) OR "
            "(source_cluster_key IS NOT NULL AND source_cluster_basis IN "
            "('explicit', 'content_hash', 'platform_item', 'url'))",
            name=conv("ck_evidences_source_cluster_coherence"),
        ),
        CheckConstraint(
            "workspace_id IS NULL OR project_id IS NOT NULL",
            name=conv("ck_evidences_workspace_project_pair"),
        ),
        Index("ix_evidences_source_cluster_key", "source_cluster_key"),
        Index("ix_evidences_workspace_project", "workspace_id", "project_id"),
    )

    intelligence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("intelligence_items.id")
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_records.id"))
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    market: Mapped[str | None] = mapped_column(String(10))
    locale: Mapped[str | None] = mapped_column(String(16))
    source_tool_id: Mapped[str | None] = mapped_column(String(200))
    provider_id: Mapped[str | None] = mapped_column(String(40))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_cluster_key: Mapped[str | None] = mapped_column(String(200))
    source_cluster_basis: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    highlighted_text: Mapped[str | None] = mapped_column(Text)
    reference_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    intelligence: Mapped[IntelligenceItem | None] = relationship(back_populates="evidences")
    signal: Mapped[Signal | None] = relationship()
    entity: Mapped[Entity | None] = relationship()
    raw_record: Mapped[RawRecord | None] = relationship()
```

导入行改为：

```python
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.sql.elements import conv
```

`schemas/intelligence.py` 的 `EvidenceResponse.intelligence_id` 改为：

```python
    intelligence_id: uuid.UUID | None
```

- [ ] **Step 4: 写迁移 063**

创建 `apps/api/alembic/versions/202610220063_claim_evidence_completeness.py`：

```python
"""Complete claims, claim_evidence and evidences for governed claim delivery.

Revision ID: 202610220063
Revises: 202610220062
Create Date: 2026-10-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 唯一迁移。不得再拆第二个 063 之后的迁移。
- 目标数据库是 PostgreSQL。单元测试只用 ``Base.metadata.create_all``，不跑本迁移。
- ``claims`` 与 ``claim_evidence`` 已在 056 建表；本迁移只补列与约束。
- ``evidences.intelligence_id`` 改为可空。契约 §4.2 要求。
- ``evidences.workspace_id`` / ``project_id`` 从 ``intelligence_items`` 回填。
- CHECK 约束名与模型逐字一致。模型用 ``conv`` 屏蔽命名约定的前缀。
- downgrade 先删索引、约束、外键，再删列；最后恢复 ``intelligence_id`` 非空。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220063"
down_revision: str | None = "202610220062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _claim_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("scope_window_start", sa.Date(), nullable=True),
        sa.Column("scope_window_end", sa.Date(), nullable=True),
        sa.Column("risk_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_content_version", sa.Integer(), nullable=True),
        sa.Column("reviewed_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("reviewed_profile", sa.String(length=40), nullable=True),
        sa.Column("second_reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("second_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "independent_source_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("blocked_reason", sa.String(length=40), nullable=True),
        sa.Column(
            "review_history",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def _claim_evidence_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
        sa.Column("source_cluster_key", sa.String(length=200), nullable=True),
        sa.Column("source_cluster_basis", sa.String(length=20), nullable=True),
        sa.Column("independent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def _evidence_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
        sa.Column("market", sa.String(length=10), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=True),
        sa.Column("source_tool_id", sa.String(length=200), nullable=True),
        sa.Column("provider_id", sa.String(length=40), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_cluster_key", sa.String(length=200), nullable=True),
        sa.Column("source_cluster_basis", sa.String(length=20), nullable=True),
    )


_CLAIM_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "ck_claims_evidence_grade_min",
        "evidence_grade IS NULL OR evidence_grade IN "
        "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live')",
    ),
    (
        "ck_claims_state_grade_ceiling",
        "evidence_grade IS NULL OR "
        "(state = 'confirmed' AND evidence_grade = 'L4_authorized_live') OR "
        "(state = 'directional' AND evidence_grade IN ('L3_live_single', 'L4_authorized_live')) OR "
        "(state = 'hypothesis' AND evidence_grade IN "
        "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live')) OR "
        "(state IN ('evidence_gap', 'blocked') AND evidence_grade IN "
        "('L2_fixture_local', 'L3_live_single', 'L4_authorized_live'))",
    ),
    (
        "ck_claims_review_status",
        "review_status IN ('draft', 'pending', 'approved', 'rejected', 'stale')",
    ),
    (
        "ck_claims_review_coherence",
        "review_status <> 'approved' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL "
        "AND reviewed_content_version IS NOT NULL AND reviewed_payload_sha256 IS NOT NULL "
        "AND reviewed_profile IS NOT NULL)",
    ),
    (
        "ck_claims_confirmed_review",
        "state <> 'confirmed' OR (review_status = 'approved' "
        "AND reviewed_content_version = content_version)",
    ),
    ("ck_claims_content_version", "content_version >= 1"),
    (
        "ck_claims_reviewed_version",
        "reviewed_content_version IS NULL OR "
        "(reviewed_content_version >= 1 AND reviewed_content_version <= content_version)",
    ),
    ("ck_claims_independent_count", "independent_source_count >= 0"),
    (
        "ck_claims_scope_window",
        "scope_window_start IS NULL OR scope_window_end IS NULL "
        "OR scope_window_end >= scope_window_start",
    ),
    ("ck_claims_scope_days", "scope_window_days IS NULL OR scope_window_days >= 1"),
    ("ck_claims_scope_sample", "scope_sample_n IS NULL OR scope_sample_n >= 0"),
    (
        "ck_claims_blocked_reason",
        "blocked_reason IS NULL OR blocked_reason IN "
        "('rights', 'permission', 'configuration', 'gate', 'upstream')",
    ),
    ("ck_claims_blocked_state", "state <> 'blocked' OR blocked_reason IS NOT NULL"),
    (
        "ck_claims_second_review_pair",
        "(second_reviewed_by IS NULL) = (second_reviewed_at IS NULL)",
    ),
    (
        "ck_claims_reviewer_differ",
        "second_reviewed_by IS NULL OR reviewed_by IS NULL "
        "OR second_reviewed_by <> reviewed_by",
    ),
)

_CLAIM_EVIDENCE_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "ck_claim_evidence_evidence_grade",
        "evidence_grade IS NULL OR evidence_grade IN "
        "('L0_unverified', 'L1_contract', 'L2_fixture_local', "
        "'L3_live_single', 'L4_authorized_live')",
    ),
    (
        "ck_claim_evidence_source_cluster_basis",
        "source_cluster_basis IS NULL OR source_cluster_basis IN "
        "('explicit', 'content_hash', 'platform_item', 'url', 'unresolved')",
    ),
    (
        "ck_claim_evidence_independent_cluster",
        "independent = false OR source_cluster_key IS NOT NULL",
    ),
)

_EVIDENCE_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "ck_evidences_evidence_grade",
        "evidence_grade IS NULL OR evidence_grade IN "
        "('L0_unverified', 'L1_contract', 'L2_fixture_local', "
        "'L3_live_single', 'L4_authorized_live')",
    ),
    (
        "ck_evidences_source_cluster_basis",
        "source_cluster_basis IS NULL OR source_cluster_basis IN "
        "('explicit', 'content_hash', 'platform_item', 'url', 'unresolved')",
    ),
    (
        "ck_evidences_source_cluster_coherence",
        "(source_cluster_key IS NULL AND (source_cluster_basis IS NULL "
        "OR source_cluster_basis = 'unresolved')) OR "
        "(source_cluster_key IS NOT NULL AND source_cluster_basis IN "
        "('explicit', 'content_hash', 'platform_item', 'url'))",
    ),
    (
        "ck_evidences_workspace_project_pair",
        "workspace_id IS NULL OR project_id IS NOT NULL",
    ),
)


def upgrade() -> None:
    for column in _claim_columns():
        op.add_column("claims", column)
    for name, condition in _CLAIM_CHECKS:
        op.create_check_constraint(name, "claims", condition)
    op.create_index("ix_claims_review_status", "claims", ["workspace_id", "review_status"])
    op.create_index("ix_claims_scope_market", "claims", ["scope_market"])

    for column in _claim_evidence_columns():
        op.add_column("claim_evidence", column)
    for name, condition in _CLAIM_EVIDENCE_CHECKS:
        op.create_check_constraint(name, "claim_evidence", condition)
    op.create_index(
        "ix_claim_evidence_source_cluster_key",
        "claim_evidence",
        ["source_cluster_key"],
    )

    for column in _evidence_columns():
        op.add_column("evidences", column)
    op.alter_column("evidences", "intelligence_id", existing_type=sa.Uuid(), nullable=True)
    op.execute(
        """
        UPDATE evidences AS e
        SET workspace_id = i.workspace_id,
            project_id = i.project_id
        FROM intelligence_items AS i
        WHERE e.intelligence_id = i.id
          AND e.workspace_id IS NULL
        """
    )
    for name, condition in _EVIDENCE_CHECKS:
        op.create_check_constraint(name, "evidences", condition)
    op.create_index("ix_evidences_source_cluster_key", "evidences", ["source_cluster_key"])
    op.create_index("ix_evidences_workspace_project", "evidences", ["workspace_id", "project_id"])

    op.create_foreign_key(
        "fk_claims_owner_users", "claims", "users", ["owner"], ["id"]
    )
    op.create_foreign_key(
        "fk_claims_reviewed_by_users", "claims", "users", ["reviewed_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_claims_second_reviewed_by_users",
        "claims",
        "users",
        ["second_reviewed_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_evidences_workspace_id_workspaces",
        "evidences",
        "workspaces",
        ["workspace_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_evidences_project_id_projects",
        "evidences",
        "projects",
        ["project_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evidences_project_id_projects", "evidences", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_evidences_workspace_id_workspaces", "evidences", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_claims_second_reviewed_by_users", "claims", type_="foreignkey"
    )
    op.drop_constraint("fk_claims_reviewed_by_users", "claims", type_="foreignkey")
    op.drop_constraint("fk_claims_owner_users", "claims", type_="foreignkey")

    op.drop_index("ix_evidences_workspace_project", table_name="evidences")
    op.drop_index("ix_evidences_source_cluster_key", table_name="evidences")
    for name, _ in reversed(_EVIDENCE_CHECKS):
        op.drop_constraint(name, "evidences", type_="check")
    for column in reversed(_evidence_columns()):
        op.drop_column("evidences", column.name)
    op.alter_column("evidences", "intelligence_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_claim_evidence_source_cluster_key", table_name="claim_evidence")
    for name, _ in reversed(_CLAIM_EVIDENCE_CHECKS):
        op.drop_constraint(name, "claim_evidence", type_="check")
    for column in reversed(_claim_evidence_columns()):
        op.drop_column("claim_evidence", column.name)

    op.drop_index("ix_claims_scope_market", table_name="claims")
    op.drop_index("ix_claims_review_status", table_name="claims")
    for name, _ in reversed(_CLAIM_CHECKS):
        op.drop_constraint(name, "claims", type_="check")
    for column in reversed(_claim_columns()):
        op.drop_column("claims", column.name)
```

- [ ] **Step 5: 运行 schema 测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_evidence_schema.py -q
```

Expected: `8 passed`。

- [ ] **Step 5b: 写并运行 PostgreSQL 迁移测试**

Create `apps/api/tests/postgres/test_claim_evidence_migration.py`：

```python
"""C7：迁移 063 在一次性 PostgreSQL 上升级、降级与单头。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

API_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL 未设置；发布门禁必须设置")
    if not url.startswith("postgresql+asyncpg://"):
        raise pytest.UsageError("TEST_DATABASE_URL 必须使用 postgresql+asyncpg")
    return url


def _alembic(url: str, *args: str) -> None:
    environment = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )


async def _columns(engine: AsyncEngine, table: str) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns(table)
        )
    return {row["name"] for row in rows}


@pytest.mark.asyncio
async def test_062_to_063_and_back() -> None:
    url = _database_url()
    _alembic(url, "upgrade", "202610220062")
    _alembic(url, "upgrade", "202610220063")
    engine = create_async_engine(url)
    try:
        claim_columns = await _columns(engine, "claims")
        for name in ("text_en", "review_status", "scope_window_start", "scope_window_end"):
            assert name in claim_columns
        evidence_columns = await _columns(engine, "evidences")
        for name in ("workspace_id", "source_cluster_key", "source_cluster_basis"):
            assert name in evidence_columns
        _alembic(url, "downgrade", "202610220062")
        assert "text_en" not in await _columns(engine, "claims")
        _alembic(url, "upgrade", "head")
    finally:
        await engine.dispose()


def test_single_head_is_063() -> None:
    url = _database_url()
    environment = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=API_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.count("(head)") == 1
    assert "202610220063" in result.stdout
```

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/dih_migration_test \
  uv run pytest tests/postgres/test_claim_evidence_migration.py -q
```

Expected: `2 passed`。未设置 `TEST_DATABASE_URL` 时是 `2 skipped`；切片完成门禁必须用一次性 PostgreSQL 跑出 `2 passed`。

- [ ] **Step 6: 运行 B5 claim 测试，确认只差预期修改**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claims.py -q
```

Expected: FAIL 在 `test_claim_check_constraint_names_match_migration` 与 `test_create_claim_accepts_confirmed_state_with_support_evidence`。这两个失败在 Task 5 修正。

- [ ] **Step 7: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "Claim" --direction upstream --repo .
node .gitnexus/run.cjs impact "ClaimEvidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "Evidence" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220063_claim_evidence_completeness.py apps/api/src/data_intelligence_hub/models/claim.py apps/api/src/data_intelligence_hub/models/intelligence.py apps/api/src/data_intelligence_hub/schemas/intelligence.py apps/api/tests/unit/test_claim_evidence_schema.py apps/api/tests/postgres/test_claim_evidence_migration.py
git commit -m "feat(claims): 主张与证据治理字段及迁移 063"
```

`impact` 报 `risk: HIGH` 或 `CRITICAL` 时停止。`detect-changes` 出现 `partial: true` 或 `truncated: true` 时重跑。

---

### Task 5: 受治理的 Claim 创建

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/repositories/claims.py`
- Modify: `apps/api/src/data_intelligence_hub/services/claims.py`
- Modify: `apps/api/tests/unit/test_claims.py`
- Test: `apps/api/tests/unit/test_claim_creation_governance.py`

**Interfaces:**
- Consumes: Task 2 `resolve_source_cluster()`、`assign_link_clusters()`；Task 3 策略函数；Task 4 模型列。
- Produces:
  - `create_claim_with_evidence()` 新签名（保留 B5 旧参数）
  - `load_evidence_rows()`
  - `update_claim_fields()`
  - `ClaimEvidenceNotFoundError`、`ClaimBlockedReasonRequiredError`

- [ ] **Step 1: 写失败测试**

```python
"""C7：Claim 创建治理。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.claims import create_claim_with_evidence
from data_intelligence_hub.services.exceptions import (
    ClaimBlockedReasonRequiredError,
    ClaimConfirmationRequiresReviewError,
    ClaimGradeBelowMinimumError,
    ClaimGradeExceedsEvidenceError,
    ClaimMarketUnsupportedError,
)


class Seed:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self) -> Seed:
        owner = User(
            email=f"c7-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        self.session.add(owner)
        await self.session.flush()
        workspace = Workspace(
            name="C7",
            slug=f"c7-{uuid.uuid4().hex}",
            owner_id=owner.id,
        )
        self.session.add(workspace)
        await self.session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="C7",
            domain="mother_baby",
            owner_id=owner.id,
        )
        self.session.add(project)
        await self.session.flush()
        item = IntelligenceItem(
            workspace_id=workspace.id,
            project_id=project.id,
            title="Item",
            summary="Summary",
            intelligence_type="signal",
            impact_score=0.5,
            confidence_score=0.5,
            novelty_score=0.5,
            urgency_score=0.5,
            final_score=0.5,
            generated_by="system",
            domain="mother_baby",
        )
        self.session.add(item)
        await self.session.flush()
        self.owner = owner
        self.workspace = workspace
        self.project = project
        self.item = item
        self.support = await self._evidence("support", "https://example.com/a")
        self.counter = await self._evidence("counter", "https://example.com/b")
        self.gap = await self._evidence("gap", None)
        return self

    async def _evidence(self, title: str, url: str | None) -> Evidence:
        evidence = Evidence(
            intelligence_id=self.item.id,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            evidence_type="web",
            title=title,
            url=url,
            evidence_grade="L3_live_single",
            market="US",
            locale="en-US",
            source_tool_id="tikhub.products",
            provider_id="tikhub",
            captured_at=datetime.now(UTC),
            source_cluster_key=f"url:{url}" if url else None,
            source_cluster_basis="url" if url else "unresolved",
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    def kwargs(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "workspace_id": self.workspace.id,
            "project_id": self.project.id,
            "claim_text": "美国市场母婴新品有需求",
            "text_en": "US demand exists for the new baby product",
            "owner": self.owner.id,
            "scope_market": "US",
            "scope_window_start": date(2026, 1, 1),
            "scope_window_end": date(2026, 3, 1),
            "scope_window_days": 60,
            "scope_sample_n": 120,
            "counterevidence_text": "未发现反证",
            "evidence": [
                (self.support.id, "support"),
                (self.counter.id, "counter"),
            ],
            "evidence_grade": "L4_authorized_live",
        }
        values.update(overrides)
        return values


async def _with_session(callback) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(await Seed(session).build())
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_complete_claim_is_created() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await create_claim_with_evidence(seed.session, **seed.kwargs())
        assert claim.evidence_grade == "L4_authorized_live"
        assert claim.independent_source_count == 2
        assert claim.review_status == "draft"
        assert claim.content_version == 1
        assert claim.risk_flags == []

    await _with_session(scenario)


@pytest.mark.anyio
async def test_l0_and_l1_are_rejected() -> None:
    async def scenario(seed: Seed) -> None:
        for grade in ("L0_unverified", "L1_contract"):
            with pytest.raises(ClaimGradeBelowMinimumError):
                await create_claim_with_evidence(
                    seed.session, **seed.kwargs(evidence_grade=grade)
                )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_claim_grade_cannot_exceed_evidence_grade() -> None:
    async def scenario(seed: Seed) -> None:
        seed.counter.evidence_grade = "L3_live_single"
        with pytest.raises(ClaimGradeExceedsEvidenceError):
            await create_claim_with_evidence(
                seed.session, **seed.kwargs(evidence_grade="L4_authorized_live")
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_confirmed_cannot_be_created_directly() -> None:
    async def scenario(seed: Seed) -> None:
        with pytest.raises(ClaimConfirmationRequiresReviewError):
            await create_claim_with_evidence(
                seed.session, **seed.kwargs(state="confirmed")
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_single_source_flag_is_added() -> None:
    async def scenario(seed: Seed) -> None:
        seed.counter.source_cluster_key = seed.support.source_cluster_key
        claim = await create_claim_with_evidence(
            seed.session,
            **seed.kwargs(evidence_grade="L3_live_single", state="directional"),
        )
        assert claim.independent_source_count == 1
        assert "single_source" in claim.risk_flags

    await _with_session(scenario)


@pytest.mark.anyio
async def test_unsupported_market_is_rejected() -> None:
    async def scenario(seed: Seed) -> None:
        with pytest.raises(ClaimMarketUnsupportedError):
            await create_claim_with_evidence(
                seed.session, **seed.kwargs(scope_market="XX")
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_blocked_requires_reason() -> None:
    async def scenario(seed: Seed) -> None:
        with pytest.raises(ClaimBlockedReasonRequiredError):
            await create_claim_with_evidence(
                seed.session,
                **seed.kwargs(
                    state="blocked",
                    evidence=[(seed.gap.id, "gap")],
                    evidence_grade="L2_fixture_local",
                ),
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_evidence_from_other_workspace_is_rejected() -> None:
    async def scenario(seed: Seed) -> None:
        other_workspace = Workspace(
            name="Other",
            slug=f"other-{uuid.uuid4().hex}",
            owner_id=seed.owner.id,
        )
        seed.session.add(other_workspace)
        await seed.session.flush()
        other_project = Project(
            workspace_id=other_workspace.id,
            name="Other",
            domain="mother_baby",
            owner_id=seed.owner.id,
        )
        seed.session.add(other_project)
        await seed.session.flush()
        foreign = Evidence(
            workspace_id=other_workspace.id,
            project_id=other_project.id,
            evidence_type="web",
            title="Foreign",
            url="https://example.com/foreign",
            evidence_grade="L3_live_single",
        )
        seed.session.add(foreign)
        await seed.session.flush()
        from data_intelligence_hub.services.exceptions import ClaimEvidenceNotFoundError

        with pytest.raises(ClaimEvidenceNotFoundError):
            await create_claim_with_evidence(
                seed.session,
                **seed.kwargs(
                    evidence=[(seed.support.id, "support"), (foreign.id, "counter")]
                ),
            )

    await _with_session(scenario)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_creation_governance.py -q
```

Expected: FAIL，`TypeError: create_claim_with_evidence() got an unexpected keyword argument 'text_en'`。

- [ ] **Step 3: 扩展仓储**

在 `repositories/claims.py` 中替换 `create_claim` 与 `link_evidence`，并新增两个函数：

```python
async def create_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    claim_text: str,
    run_id: uuid.UUID | None = None,
    state: ClaimState | str = ClaimState.HYPOTHESIS,
    evidence_grade: EvidenceGrade | str | None = None,
    confidence: float | None = None,
    text_en: str | None = None,
    owner: uuid.UUID | None = None,
    scope_market: str | None = None,
    scope_window_start: date | None = None,
    scope_window_end: date | None = None,
    scope_window_days: int | None = None,
    scope_sample_n: int | None = None,
    counterevidence_text: str | None = None,
    risk_flags: list[str] | None = None,
    review_status: ClaimReviewStatus | str = ClaimReviewStatus.DRAFT,
    content_version: int = 1,
    independent_source_count: int = 0,
    blocked_reason: ClaimBlockedReason | str | None = None,
) -> Claim:
    """写入一行 claim 并 flush。治理规则由 services/claims.py 负责。"""
    text = claim_text.strip()
    if not text:
        raise ValueError("claim_text 不能为空")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence 必须在 0 到 1 之间")
    record = Claim(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        claim_text=text,
        text_en=text_en.strip() if text_en is not None else None,
        state=_claim_state(state),
        evidence_grade=_evidence_grade(evidence_grade),
        confidence=confidence,
        owner=owner,
        scope_market=scope_market,
        scope_window_start=scope_window_start,
        scope_window_end=scope_window_end,
        scope_window_days=scope_window_days,
        scope_sample_n=scope_sample_n,
        counterevidence_text=(
            counterevidence_text.strip() if counterevidence_text is not None else None
        ),
        risk_flags=list(risk_flags or []),
        review_status=ClaimReviewStatus(review_status).value,
        content_version=content_version,
        independent_source_count=independent_source_count,
        blocked_reason=(
            ClaimBlockedReason(blocked_reason).value if blocked_reason is not None else None
        ),
    )
    session.add(record)
    await session.flush()
    return record


async def link_evidence(
    session: AsyncSession,
    *,
    claim_id: uuid.UUID,
    evidence_id: uuid.UUID,
    role: EvidenceRole | str,
    evidence_grade: EvidenceGrade | str | None = None,
    source_cluster_key: str | None = None,
    source_cluster_basis: str | None = None,
    independent: bool = False,
) -> ClaimEvidence:
    """写入一条 claim 与 evidence 的关联并 flush。"""
    record = ClaimEvidence(
        claim_id=claim_id,
        evidence_id=evidence_id,
        role=_evidence_role(role),
        evidence_grade=_evidence_grade(evidence_grade),
        source_cluster_key=source_cluster_key,
        source_cluster_basis=source_cluster_basis,
        independent=independent,
    )
    session.add(record)
    await session.flush()
    return record


async def load_evidence_rows(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    evidence_ids: list[uuid.UUID],
) -> list[Evidence]:
    """按工作区与项目加载证据行。空输入返回空列表。"""
    if not evidence_ids:
        return []
    result = await session.execute(
        select(Evidence).where(
            Evidence.id.in_(evidence_ids),
            Evidence.workspace_id == workspace_id,
            Evidence.project_id == project_id,
        )
    )
    return list(result.scalars().all())


async def update_claim_fields(
    session: AsyncSession,
    claim: Claim,
    **values: object,
) -> Claim:
    """更新 claim 的受控字段并 flush。未知字段直接拒绝。"""
    allowed = {
        "claim_text",
        "text_en",
        "state",
        "evidence_grade",
        "confidence",
        "owner",
        "scope_market",
        "scope_window_start",
        "scope_window_end",
        "scope_window_days",
        "scope_sample_n",
        "counterevidence_text",
        "risk_flags",
        "review_status",
        "review_note",
        "reviewed_by",
        "reviewed_at",
        "reviewed_content_version",
        "reviewed_payload_sha256",
        "reviewed_profile",
        "second_reviewed_by",
        "second_reviewed_at",
        "content_version",
        "independent_source_count",
        "blocked_reason",
        "review_history",
    }
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"不允许更新字段：{sorted(unknown)}")
    for key, value in values.items():
        setattr(claim, key, value)
    await session.flush()
    return claim


@dataclass(frozen=True, slots=True)
class ClaimTaskPrincipals:
    owner_id: uuid.UUID
    requester_id: uuid.UUID


async def get_claim_task_principals(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None,
) -> ClaimTaskPrincipals | None:
    """沿 claim.run_id → runs.workflow_version_id → workflow_versions.workbench_task_id
    读取任务单 owner 与请求人。run 未关联任务单时返回 None。"""
    if run_id is None:
        return None
    statement = (
        select(
            WorkbenchTask.owner_id,
            WorkbenchTask.created_by_user_id,
        )
        .join(
            WorkflowVersion,
            WorkflowVersion.workbench_task_id == WorkbenchTask.id,
        )
        .join(Run, Run.workflow_version_id == WorkflowVersion.id)
        .where(Run.id == run_id)
    )
    row = (await session.execute(statement)).first()
    if row is None:
        return None
    return ClaimTaskPrincipals(owner_id=row[0], requester_id=row[1])
```

顶部导入补充：

```python
from dataclasses import dataclass
from datetime import date

from data_intelligence_hub.models.claim import (
    Claim,
    ClaimBlockedReason,
    ClaimEvidence,
    ClaimReviewStatus,
    ClaimState,
    EvidenceRole,
)
from data_intelligence_hub.models.intelligence import Evidence
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
```

- [ ] **Step 4: 实现创建治理**

在 `services/claims.py` 中新增：

```python
def _normalise_scope(
    market: str | None,
    start: date | None,
    end: date | None,
    days: int | None,
    sample_n: int | None,
) -> tuple[str, date, date, int, int] | None:
    values = (market, start, end, days, sample_n)
    if all(value is None for value in values):
        return None
    if market is None or start is None or end is None or days is None or sample_n is None:
        raise ClaimScopeInvalidError("scope 字段必须同时给出")
    market_value = assert_formal_market(market)
    assert_scope_window(start, end, days, sample_n)
    return market_value, start, end, days, sample_n


def _normalise_blocked_reason(
    value: ClaimBlockedReason | str | None,
) -> ClaimBlockedReason | None:
    if value is None:
        return None
    try:
        return ClaimBlockedReason(value)
    except ValueError as exc:
        raise ValueError(f"未知的阻断原因：{value!r}") from exc


AUDIT_ACTION_REVIEW_SUBMITTED = "claim.review.submitted"
AUDIT_ACTION_REVIEW_APPROVED = "claim.review.approved"
AUDIT_ACTION_REVIEW_REJECTED = "claim.review.rejected"
AUDIT_ACTION_REVIEW_OVERRIDDEN = "claim.review.overridden"
AUDIT_ACTION_BLOCKED = "claim.blocked"
AUDIT_ACTION_UNBLOCKED = "claim.unblocked"
AUDIT_ACTION_REVISED = "claim.revised"


async def _append_claim_audit(
    session: AsyncSession,
    *,
    claim: Claim,
    actor_id: uuid.UUID | None,
    action: str,
    details: dict[str, object] | None = None,
    request_id: str | None = None,
    result: str = "success",
) -> None:
    """在同一事务内追加 C2 统一审计。失败时异常向外传播，整单回滚。"""
    await append_audit_event(
        session,
        workspace_id=claim.workspace_id,
        project_id=claim.project_id,
        actor_user_id=actor_id,
        actor_type="user" if actor_id is not None else "system",
        action=action,
        resource_type="claim",
        resource_id=str(claim.id),
        request_id=request_id,
        result=result,
        details={
            "claim_id": str(claim.id),
            "review_status": claim.review_status,
            "claim_status": claim.state,
            "content_version": claim.content_version,
            "reviewed_by": str(claim.reviewed_by) if claim.reviewed_by else None,
            "second_reviewed_by": (
                str(claim.second_reviewed_by) if claim.second_reviewed_by else None
            ),
            **(details or {}),
        },
    )


async def create_claim_with_evidence(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    claim_text: str,
    evidence: object | None = None,
    evidences: object | None = None,
    evidence_roles: object | None = None,
    run_id: uuid.UUID | None = None,
    state: ClaimState | str = ClaimState.HYPOTHESIS,
    evidence_grade: EvidenceGrade | str | None = None,
    confidence: float | None = None,
    text_en: str | None = None,
    owner: uuid.UUID | None = None,
    scope_market: str | None = None,
    scope_window_start: date | None = None,
    scope_window_end: date | None = None,
    scope_window_days: int | None = None,
    scope_sample_n: int | None = None,
    counterevidence_text: str | None = None,
    risk_flags: object = (),
    blocked_reason: ClaimBlockedReason | str | None = None,
    actor_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> Claim:
    """创建 claim 并写入治理字段与证据关联。

    写入层只强制：文本非空、证据必须属于同一工作区与项目、每条证据
    的等级不得低于 L2、Claim 等级不得高于最低证据等级、状态不得超过
    等级上限、confirmed 不得直接创建、blocked 必须有原因、反证完整。
    blocked 创建必须追加 C2 统一审计。正式发布所需的 owner、双语、
    scope、反证文本与证据元数据由 ``load_publishable_claim_rows`` 统一检查。
    """
    text = claim_text.strip()
    if not text:
        raise ValueError("claim_text 不能为空")
    state_value = _normalise_state(state)
    blocked = _normalise_blocked_reason(blocked_reason)
    if state_value is ClaimState.BLOCKED and blocked is None:
        raise ClaimBlockedReasonRequiredError()
    if state_value is not ClaimState.BLOCKED and blocked is not None:
        raise ValueError("只有 blocked 状态可以带 blocked_reason")
    scope = _normalise_scope(
        scope_market,
        scope_window_start,
        scope_window_end,
        scope_window_days,
        scope_sample_n,
    )

    provided = [value for value in (evidence, evidences, evidence_roles) if value is not None]
    if len(provided) > 1:
        raise ValueError("evidence、evidences 与 evidence_roles 只能给一个")
    links = _normalise_evidence(provided[0] if provided else None)
    if not any(link.role in COUNTER_EVIDENCE_ROLES for link in links):
        raise ClaimCounterEvidenceRequiredError()

    rows = await load_evidence_rows(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        evidence_ids=[link.evidence_id for link in links],
    )
    row_by_id = {row.id: row for row in rows}
    missing = [link.evidence_id for link in links if link.evidence_id not in row_by_id]
    if missing:
        raise ClaimEvidenceNotFoundError(str(missing[0]))

    grade_by_id: dict[uuid.UUID, EvidenceGrade] = {}
    for link in links:
        row = row_by_id[link.evidence_id]
        if row.evidence_grade is None:
            continue
        grade = EvidenceGrade(row.evidence_grade)
        assert_claim_grade_at_least_l2(grade)
        grade_by_id[link.evidence_id] = grade

    minimum_grade = (
        min(grade_by_id.values(), key=lambda grade: GRADE_ORDER[grade])
        if grade_by_id
        else None
    )
    requested_grade = assert_claim_grade_at_least_l2(evidence_grade)
    if minimum_grade is not None:
        if (
            requested_grade is not None
            and GRADE_ORDER[requested_grade] > GRADE_ORDER[minimum_grade]
        ):
            raise ClaimGradeExceedsEvidenceError(
                requested_grade.value, minimum_grade.value
            )
        claim_grade = requested_grade or minimum_grade
    else:
        claim_grade = requested_grade

    clusters = assign_link_clusters(
        [
            (link.evidence_id, resolve_source_cluster(row_by_id[link.evidence_id]))
            for link in links
        ]
    )
    independent_count = sum(1 for cluster in clusters if cluster.independent)
    flags = normalise_risk_flags(risk_flags, independent_count=independent_count)

    support_count, counter_count = _role_counts(link.role for link in links)
    if (
        support_count == 0
        and counter_count == 0
        and state_value not in GAP_ONLY_ALLOWED_STATES
    ):
        raise ClaimGapOnlyStateInvalidError()
    if state_value is ClaimState.CONFIRMED:
        raise ClaimConfirmationRequiresReviewError()
    assert_claim_state_within_grade(state_value, claim_grade)

    claim = await create_claim(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        claim_text=text,
        text_en=text_en,
        owner=owner,
        run_id=run_id,
        state=state_value,
        evidence_grade=claim_grade,
        confidence=confidence,
        scope_market=scope[0] if scope is not None else None,
        scope_window_start=scope[1] if scope is not None else None,
        scope_window_end=scope[2] if scope is not None else None,
        scope_window_days=scope[3] if scope is not None else None,
        scope_sample_n=scope[4] if scope is not None else None,
        counterevidence_text=counterevidence_text,
        risk_flags=sorted(flag.value for flag in flags),
        independent_source_count=independent_count,
        blocked_reason=blocked.value if blocked is not None else None,
    )
    for link, cluster in zip(links, clusters, strict=True):
        await link_evidence(
            session,
            claim_id=claim.id,
            evidence_id=link.evidence_id,
            role=link.role,
            evidence_grade=grade_by_id.get(link.evidence_id),
            source_cluster_key=cluster.key,
            source_cluster_basis=cluster.basis.value,
            independent=cluster.independent,
        )
    if state_value is ClaimState.BLOCKED:
        await _append_claim_audit(
            session,
            claim=claim,
            actor_id=actor_id,
            action=AUDIT_ACTION_BLOCKED,
            details={
                "blocked_reason": blocked.value if blocked is not None else None,
                "created": True,
            },
            request_id=request_id,
        )
    return claim
```

把 `services/claims.py` 顶部的 `repositories.claims` 导入替换为以下完整块，并新增 `source_clusters` 导入：

```python
from data_intelligence_hub.repositories.claims import (
    COUNTER_EVIDENCE_ROLES,
    create_claim,
    link_evidence,
    list_evidence,
    load_evidence_rows,
    update_claim_fields,
)
from data_intelligence_hub.services.source_clusters import (
    assign_link_clusters,
    resolve_source_cluster,
)
```

把 `ClaimBlockedReasonRequiredError` 与 `ClaimEvidenceNotFoundError` 并入现有 `services.exceptions` 导入块。

在 `services/exceptions.py` 追加：

```python
class ClaimEvidenceNotFoundError(ServiceError):
    message = "claim_evidence_not_found"

    def __init__(self, evidence_id: str) -> None:
        super().__init__(self.message)
        self.evidence_id = evidence_id


class ClaimBlockedReasonRequiredError(ServiceError):
    message = "claim_blocked_reason_required"
```

- [ ] **Step 5: 更新 B5 测试 seed 与两个预期**

在 `apps/api/tests/unit/test_claims.py` 中：

1. `_seed` 的三条 `Evidence` 改为：

```python
    support = Evidence(
        intelligence_id=item.id,
        workspace_id=workspace_a.id,
        project_id=project_a.id,
        evidence_type="web",
        title="Support",
        url="https://example.com/support",
        evidence_grade="L3_live_single",
        market="US",
        locale="en-US",
        source_tool_id="test.tool",
        captured_at=datetime.now(UTC),
        source_cluster_key="url:https://example.com/support",
        source_cluster_basis="url",
    )
    counter = Evidence(
        intelligence_id=item.id,
        workspace_id=workspace_a.id,
        project_id=project_a.id,
        evidence_type="web",
        title="Counter",
        url="https://example.com/counter",
        evidence_grade="L3_live_single",
        market="US",
        locale="en-US",
        source_tool_id="test.tool",
        captured_at=datetime.now(UTC),
        source_cluster_key="url:https://example.com/counter",
        source_cluster_basis="url",
    )
    context = Evidence(
        intelligence_id=item.id,
        workspace_id=workspace_a.id,
        project_id=project_a.id,
        evidence_type="web",
        title="Context",
        url="https://example.com/context",
        evidence_grade="L3_live_single",
        market="US",
        locale="en-US",
        source_tool_id="test.tool",
        captured_at=datetime.now(UTC),
        source_cluster_key="url:https://example.com/context",
        source_cluster_basis="url",
    )
```

2. `test_create_claim_accepts_confirmed_state_with_support_evidence` 改为：

```python
@pytest.mark.anyio
async def test_create_claim_rejects_confirmed_state() -> None:
    """confirmed 只能由审核服务晋升，创建入口一律拒绝。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        from data_intelligence_hub.services.exceptions import (
            ClaimConfirmationRequiresReviewError,
        )

        with pytest.raises(ClaimConfirmationRequiresReviewError):
            await create_claim_with_evidence(
                session,
                **_kwargs(seed),
                claim_text="创建即确认的主张",
                evidence=[
                    (seed.support_evidence.id, "support"),
                    (seed.context_evidence.id, "gap"),
                ],
                state="confirmed",
            )
        observed["claims"] = await list_claims(
            session, workspace_id=seed.workspace_a.id
        )

    await _with_session(scenario)

    assert observed["claims"] == []
```

3. `test_claim_check_constraint_names_match_migration` 改为只断言 056 的四个约束是子集：

```python
def test_claim_check_constraint_names_include_056_contract_checks() -> None:
    claim_names = _model_check_names(Claim.__table__)
    evidence_names = _model_check_names(ClaimEvidence.__table__)
    assert {
        "ck_claims_state",
        "ck_claims_evidence_grade",
        "ck_claims_confidence_range",
    } <= claim_names
    assert {"ck_claim_evidence_role"} <= evidence_names
```

4. `test_assert_gap_only_state_valid_lists_only_violations` 中把 `state="confirmed"` 改为 `state="directional"`，把 `valid_support` 的 `state="confirmed"` 改为 `state="directional"`。测试语义不变：只有 gap/context 时不得给方向性状态。
5. `test_create_claim_accepts_gap_only_blocked_state` 的调用增加 `blocked_reason="rights"`。`blocked` 状态现在必须给出原因。
6. `test_create_claim_rejects_gap_only_confirmed_state` 不改。创建服务先判 gap-only，再判 confirmed，所以第一次调用仍抛 `ClaimGapOnlyStateInvalidError`。

- [ ] **Step 6: 运行创建测试与 B5 claim 测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_creation_governance.py tests/unit/test_claims.py -q
```

Expected: `8 passed` + `21 passed`（共 29 passed）。若 `test_claims.py` 报 owner/scope 缺失，说明 `create_claim_with_evidence` 仍强制了草稿字段；按本任务 Step 4 的实现，草稿字段必须保持可选。

- [ ] **Step 7: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "create_claim_with_evidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "link_evidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_claim" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/claims.py apps/api/src/data_intelligence_hub/services/claims.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_claims.py apps/api/tests/unit/test_claim_creation_governance.py
git commit -m "feat(claims): 受治理的主张创建与独立来源计数"
```

`impact` 报 `risk: HIGH` 或 `CRITICAL` 时停止。`risk: UNKNOWN` 时用 `git grep -n "create_claim_with_evidence\|link_evidence" apps/api/src apps/api/tests` 确认调用方。

---

### Task 6: 审核生命周期、内部审核指派与统一审计

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/claim_signing.py`
- Modify: `apps/api/src/data_intelligence_hub/services/claims.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/claims.py`
- Test: `apps/api/tests/unit/test_claim_review.py`

**Interfaces:**
- Consumes: Task 5 的 `create_claim_with_evidence()`、`update_claim_fields()`、`list_evidence()`；C1 的 `CANONICAL_PROFILE_ID`、`canonical_json_bytes()`；C2 的 `get_active_reviewer_assignment()`、`grant_reviewer_assignment()`、`ReviewerAssignment`、`REVIEWER_SCOPE_READ`、`REVIEWER_SCOPE_REVIEW`、`append_audit_event()`、`get_workspace_role()`；C4 的 `workbench_tasks.owner_id`/`created_by_user_id`。
- Produces:
  - `claim_payload()`、`claim_payload_sha256()`
  - `submit_claim_for_review()`
  - `review_claim()`
  - `override_claim_review()`
  - `block_claim()`、`unblock_claim()`
  - `revise_claim()`
  - `assert_claim_read_scope()`
  - `assert_reviewer_principal_independence()`、`reviewer_violation()`
  - `get_claim_task_principals()`、`ClaimTaskPrincipals`
  - `ClaimReviewDecision`
  - 统一审计动作常量 `AUDIT_ACTION_*`

- [ ] **Step 1: 写失败测试**

```python
"""C7：审核生命周期。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.audit_events import list_audit_events
from data_intelligence_hub.repositories.claims import (
    ClaimTaskPrincipals,
    list_evidence,
)
from data_intelligence_hub.services.claims import (
    assert_claim_read_scope,
    block_claim,
    create_claim_with_evidence,
    override_claim_review,
    review_claim,
    revise_claim,
    submit_claim_for_review,
    unblock_claim,
)
from data_intelligence_hub.services.claim_signing import claim_payload_sha256
from data_intelligence_hub.services.exceptions import (
    ClaimReviewerAssignmentInvalidError,
    ClaimReviewerAssignmentRequiredError,
    ClaimReviewTransitionError,
    ClaimSecondReviewRequiredError,
    ClaimSecondReviewerInvalidError,
    ClaimSelfReviewError,
    ClaimStateExceedsGradeError,
)
from data_intelligence_hub.services.reviewer_assignments import (
    REVIEWER_SCOPE_READ,
    REVIEWER_SCOPE_REVIEW,
    grant_reviewer_assignment,
)


class Seed:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self) -> Seed:
        self.owner = User(
            email=f"review-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        self.reviewer = User(
            email=f"reviewer-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Reviewer",
        )
        self.second = User(
            email=f"second-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Second",
        )
        self.customer_admin = User(
            email=f"admin-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Admin",
        )
        self.customer_member = User(
            email=f"member-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Member",
        )
        self.reader = User(
            email=f"reader-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Reader",
        )
        self.outsider = User(
            email=f"outsider-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Outsider",
        )
        self.session.add_all(
            [
                self.owner,
                self.reviewer,
                self.second,
                self.customer_admin,
                self.customer_member,
                self.reader,
                self.outsider,
            ]
        )
        await self.session.flush()
        self.workspace = Workspace(
            name="Review",
            slug=f"review-{uuid.uuid4().hex}",
            owner_id=self.owner.id,
        )
        self.session.add(self.workspace)
        await self.session.flush()
        self.session.add_all(
            [
                WorkspaceMember(
                    workspace_id=self.workspace.id, user_id=self.owner.id, role="owner"
                ),
                WorkspaceMember(
                    workspace_id=self.workspace.id,
                    user_id=self.customer_admin.id,
                    role="admin",
                ),
                WorkspaceMember(
                    workspace_id=self.workspace.id,
                    user_id=self.customer_member.id,
                    role="member",
                ),
            ]
        )
        await self.session.flush()
        self.project = Project(
            workspace_id=self.workspace.id,
            name="Review",
            domain="mother_baby",
            owner_id=self.owner.id,
        )
        self.session.add(self.project)
        await self.session.flush()
        self.reviewer_assignment = await grant_reviewer_assignment(
            self.session,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            user_id=self.reviewer.id,
            assignment_scope=REVIEWER_SCOPE_REVIEW,
            assigned_by=self.owner.id,
        )
        self.second_assignment = await grant_reviewer_assignment(
            self.session,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            user_id=self.second.id,
            assignment_scope=REVIEWER_SCOPE_REVIEW,
            assigned_by=self.owner.id,
        )
        self.reader_assignment = await grant_reviewer_assignment(
            self.session,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            user_id=self.reader.id,
            assignment_scope=REVIEWER_SCOPE_READ,
            assigned_by=self.owner.id,
        )
        self.item = IntelligenceItem(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            title="Item",
            summary="Summary",
            intelligence_type="signal",
            impact_score=0.5,
            confidence_score=0.5,
            novelty_score=0.5,
            urgency_score=0.5,
            final_score=0.5,
            generated_by="system",
            domain="mother_baby",
        )
        self.session.add(self.item)
        await self.session.flush()
        self.support = await self._evidence("support", "https://example.com/a")
        self.counter = await self._evidence("counter", "https://example.com/b")
        return self

    async def _evidence(self, title: str, url: str) -> Evidence:
        evidence = Evidence(
            intelligence_id=self.item.id,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            evidence_type="web",
            title=title,
            url=url,
            evidence_grade="L4_authorized_live",
            market="US",
            locale="en-US",
            source_tool_id="tikhub.products",
            provider_id="tikhub",
            captured_at=datetime.now(UTC),
            source_cluster_key=f"url:{url}",
            source_cluster_basis="url",
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def claim(self, **overrides: object):
        values: dict[str, object] = {
            "workspace_id": self.workspace.id,
            "project_id": self.project.id,
            "claim_text": "美国市场母婴新品有需求",
            "text_en": "US demand exists for the new baby product",
            "owner": self.owner.id,
            "scope_market": "US",
            "scope_window_start": date(2026, 1, 1),
            "scope_window_end": date(2026, 3, 1),
            "scope_window_days": 60,
            "scope_sample_n": 120,
            "counterevidence_text": "未发现反证",
            "evidence": [
                (self.support.id, "support"),
                (self.counter.id, "counter"),
            ],
            "evidence_grade": "L4_authorized_live",
            "state": "directional",
        }
        values.update(overrides)
        return await create_claim_with_evidence(self.session, **values)


async def _with_session(callback) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(await Seed(session).build())
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_submit_then_approve_directional() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        claim = await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        assert claim.review_status == "pending"
        claim = await review_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="approved",
            note="证据一致，方向性成立",
        )
        assert claim.review_status == "approved"
        assert claim.reviewed_content_version == 1
        links = await list_evidence(seed.session, claim_id=claim.id)
        assert claim.reviewed_payload_sha256 == claim_payload_sha256(claim, links)

    await _with_session(scenario)


@pytest.mark.anyio
async def test_self_review_is_rejected() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimSelfReviewError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.owner.id,
                decision="approved",
                note="自审",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_confirmed_requires_two_sources_and_l4() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim(evidence_grade="L3_live_single", state="directional")
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimStateExceedsGradeError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="越级确认",
                approved_state="confirmed",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_sensitive_claim_needs_second_reviewer() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim(risk_flags=["medical"])
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimSecondReviewRequiredError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="单人审核",
            )
        with pytest.raises(ClaimSecondReviewerInvalidError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="第二人无效",
                second_reviewer_id=seed.owner.id,
            )
        claim = await review_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="approved",
            note="第二人复核通过",
            second_reviewer_id=seed.second.id,
        )
        assert claim.second_reviewed_by == seed.second.id
        assert claim.second_reviewed_at is not None

    await _with_session(scenario)


@pytest.mark.anyio
async def test_revise_after_approval_marks_stale_and_clears_signature() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        claim = await review_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="approved",
            note="通过",
        )
        claim = await revise_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
            claim_text="美国市场母婴新品有稳定需求",
        )
        assert claim.review_status == "stale"
        assert claim.content_version == 2
        assert claim.reviewed_by is None
        assert claim.reviewed_payload_sha256 is None
        assert claim.reviewed_profile is None
        assert claim.review_history[-1]["event"] == "revise"

    await _with_session(scenario)


@pytest.mark.anyio
async def test_review_requires_pending_state() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        with pytest.raises(ClaimReviewTransitionError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="未提交即审核",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_review_requires_active_internal_assignment() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimReviewerAssignmentRequiredError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.outsider.id,
                decision="approved",
                note="无指派",
            )

    await _with_session(scenario)


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["owner", "admin", "member"])
async def test_customer_workspace_roles_cannot_review(role: str) -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim(owner=seed.outsider.id)
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        reviewer_id = {
            "owner": seed.owner.id,
            "admin": seed.customer_admin.id,
            "member": seed.customer_member.id,
        }[role]
        with pytest.raises(ClaimReviewerAssignmentInvalidError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=reviewer_id,
                decision="approved",
                note=f"{role} 不是内部审核人",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_read_only_assignment_cannot_review_but_can_read() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimReviewerAssignmentRequiredError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reader.id,
                decision="approved",
                note="只读范围",
            )
        assignment = await assert_claim_read_scope(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            user_id=seed.reader.id,
        )
        assert assignment.assignment_scope == REVIEWER_SCOPE_READ

    await _with_session(scenario)


@pytest.mark.anyio
async def test_assignment_for_other_project_cannot_review() -> None:
    async def scenario(seed: Seed) -> None:
        other = Project(
            workspace_id=seed.workspace.id,
            name="Other",
            domain="mother_baby",
            owner_id=seed.owner.id,
        )
        seed.session.add(other)
        await seed.session.flush()
        await grant_reviewer_assignment(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=other.id,
            user_id=seed.outsider.id,
            assignment_scope=REVIEWER_SCOPE_REVIEW,
            assigned_by=seed.owner.id,
        )
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimReviewerAssignmentRequiredError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.outsider.id,
                decision="approved",
                note="跨项目指派",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_expired_assignment_cannot_review() -> None:
    async def scenario(seed: Seed) -> None:
        await grant_reviewer_assignment(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            user_id=seed.outsider.id,
            assignment_scope=REVIEWER_SCOPE_REVIEW,
            assigned_by=seed.owner.id,
            active_from=datetime.now(UTC) - timedelta(days=2),
            active_until=datetime.now(UTC) - timedelta(days=1),
        )
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimReviewerAssignmentRequiredError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.outsider.id,
                decision="approved",
                note="过期指派",
            )

    await _with_session(scenario)


@pytest.mark.anyio
@pytest.mark.parametrize("principal", ["owner", "requester"])
async def test_reviewer_cannot_be_task_owner_or_requester(
    monkeypatch: pytest.MonkeyPatch, principal: str
) -> None:
    async def scenario(seed: Seed) -> None:
        async def fake_principals(session, *, run_id):
            return ClaimTaskPrincipals(
                owner_id=seed.reviewer.id if principal == "owner" else seed.outsider.id,
                requester_id=(
                    seed.reviewer.id if principal == "requester" else seed.outsider.id
                ),
            )

        monkeypatch.setattr(
            "data_intelligence_hub.services.claims.get_claim_task_principals",
            fake_principals,
        )
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimReviewerAssignmentInvalidError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="任务 owner 或请求人不得审核",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_second_reviewer_requires_active_assignment() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim(risk_flags=["medical"])
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        with pytest.raises(ClaimSecondReviewerInvalidError):
            await review_claim(
                seed.session,
                workspace_id=seed.workspace.id,
                claim_id=claim.id,
                reviewer_id=seed.reviewer.id,
                decision="approved",
                note="第二人无指派",
                second_reviewer_id=seed.outsider.id,
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_approve_appends_c2_audit_event() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
            request_id="req-submit",
        )
        claim = await review_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="approved",
            note="通过",
            request_id="req-approve",
        )
        events = await list_audit_events(
            seed.session, workspace_id=seed.workspace.id
        )
        approved = [event for event in events if event.action == "claim.review.approved"]
        assert len(approved) == 1
        event = approved[0]
        assert event.resource_type == "claim"
        assert event.resource_id == str(claim.id)
        assert event.actor_user_id == seed.reviewer.id
        assert event.request_id == "req-approve"
        assert event.details["review_scope"] == REVIEWER_SCOPE_REVIEW
        assert event.details["assignment_id"] == str(seed.reviewer_assignment.id)
        assert any(event.action == "claim.review.submitted" for event in events)

    await _with_session(scenario)


@pytest.mark.anyio
async def test_override_appends_audit_and_clears_signature() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        await submit_claim_for_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.owner.id,
        )
        claim = await review_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="approved",
            note="通过",
        )
        claim = await override_claim_review(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            reviewer_id=seed.reviewer.id,
            decision="rejected",
            reason="复核发现反证",
            request_id="req-override",
        )
        assert claim.review_status == "rejected"
        assert claim.state == "directional"
        assert claim.reviewed_payload_sha256 is None
        assert claim.reviewed_profile is None
        events = await list_audit_events(
            seed.session, workspace_id=seed.workspace.id
        )
        overridden = [
            event for event in events if event.action == "claim.review.overridden"
        ]
        assert len(overridden) == 1
        assert overridden[0].details["reason"] == "复核发现反证"
        assert overridden[0].details["previous_review_status"] == "approved"

    await _with_session(scenario)


@pytest.mark.anyio
async def test_block_and_unblock_append_audit() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        claim = await block_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.reviewer.id,
            blocked_reason="rights",
            note="上游权利未确认",
            request_id="req-block",
        )
        assert claim.state == "blocked"
        assert claim.blocked_reason == "rights"
        assert claim.content_version == 2
        claim = await unblock_claim(
            seed.session,
            workspace_id=seed.workspace.id,
            claim_id=claim.id,
            actor_id=seed.reviewer.id,
            state="hypothesis",
            note="权利已确认",
            request_id="req-unblock",
        )
        assert claim.state == "hypothesis"
        assert claim.blocked_reason is None
        assert claim.content_version == 3
        events = await list_audit_events(
            seed.session, workspace_id=seed.workspace.id
        )
        actions = [event.action for event in events]
        assert "claim.blocked" in actions
        assert "claim.unblocked" in actions

    await _with_session(scenario)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_review.py -q
```

Expected: FAIL，`ImportError: cannot import name 'override_claim_review'` 或 `ModuleNotFoundError: reviewer_assignments`。

- [ ] **Step 3: 实现审核签名**

创建 `apps/api/src/data_intelligence_hub/services/claim_signing.py`：

```python
"""审核签名：只调用 C1 的 canonicalizer。

C1 负责冻结 canonical profile。本模块不实现第二套 JSON 规范化。
签名载荷只含内容字段，不含审核字段；否则批准后哈希会变化。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from data_intelligence_hub.models.claim import Claim, ClaimEvidence, ClaimState
from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    canonical_json_bytes,
)


def claim_payload(
    claim: Claim,
    links: Iterable[ClaimEvidence],
    *,
    state_override: ClaimState | None = None,
) -> dict[str, Any]:
    ordered = sorted(links, key=lambda link: str(link.evidence_id))
    claim_status = state_override or ClaimState(claim.state)
    return {
        "claim_id": str(claim.id),
        "workspace_id": str(claim.workspace_id),
        "project_id": str(claim.project_id),
        "run_id": str(claim.run_id) if claim.run_id is not None else None,
        "text": claim.claim_text,
        "text_en": claim.text_en,
        "claim_status": claim_status.value,
        "evidence_grade": claim.evidence_grade,
        "confidence": claim.confidence,
        "owner": str(claim.owner) if claim.owner is not None else None,
        "scope": {
            "market": claim.scope_market,
            "window_start": (
                claim.scope_window_start.isoformat()
                if claim.scope_window_start is not None
                else None
            ),
            "window_end": (
                claim.scope_window_end.isoformat()
                if claim.scope_window_end is not None
                else None
            ),
            "window_days": claim.scope_window_days,
            "sample_n": claim.scope_sample_n,
        },
        "counterevidence_text": claim.counterevidence_text,
        "risk_flags": list(claim.risk_flags),
        "independent_source_count": claim.independent_source_count,
        "blocked_reason": claim.blocked_reason,
        "content_version": claim.content_version,
        "evidence": [
            {
                "evidence_id": str(link.evidence_id),
                "role": link.role,
                "evidence_grade": link.evidence_grade,
                "source_cluster_key": link.source_cluster_key,
                "source_cluster_basis": link.source_cluster_basis,
                "independent": link.independent,
            }
            for link in ordered
        ],
    }


def claim_payload_sha256(
    claim: Claim,
    links: Iterable[ClaimEvidence],
    *,
    state_override: ClaimState | None = None,
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            claim_payload(claim, links, state_override=state_override)
        )
    ).hexdigest()


__all__ = ["CANONICAL_PROFILE_ID", "claim_payload", "claim_payload_sha256"]
```

- [ ] **Step 4: 实现审核与修订服务**

在 `services/exceptions.py` 追加：

```python
class ClaimNotFoundError(ServiceError):
    message = "claim_not_found"


class ClaimSelfReviewError(ServiceError):
    message = "reviewer_self_review_forbidden"


class ClaimReviewTransitionError(ServiceError):
    message = "claim_review_transition_invalid"

    def __init__(self, status: str) -> None:
        super().__init__(self.message)
        self.status = status


class ClaimSecondReviewRequiredError(ServiceError):
    message = "claim_second_review_required"


class ClaimSecondReviewerInvalidError(ServiceError):
    message = "claim_second_reviewer_invalid"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
```

把以下导入并入 `services/claims.py` 现有导入块（`ClaimReviewStatus` 与 `ClaimRiskFlag` 已在 Task 3 导入）：

```python
from datetime import UTC, datetime
from enum import StrEnum

from data_intelligence_hub.models.claim import SECOND_REVIEW_RISK_FLAGS
from data_intelligence_hub.repositories.claims import (
    ClaimTaskPrincipals,
    get_claim_task_principals,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.services.claim_signing import (
    CANONICAL_PROFILE_ID,
    claim_payload_sha256,
)
from data_intelligence_hub.services.exceptions import (
    ClaimNotFoundError,
    ClaimReviewerAssignmentInvalidError,
    ClaimReviewerAssignmentRequiredError,
    ClaimReviewTransitionError,
    ClaimSecondReviewerInvalidError,
    ClaimSecondReviewRequiredError,
    ClaimSelfReviewError,
)
from data_intelligence_hub.services.reviewer_assignments import (
    REVIEWER_SCOPE_READ,
    REVIEWER_SCOPE_REVIEW,
    ReviewerAssignment,
    get_active_reviewer_assignment,
)
```

`append_audit_event` 已在 Task 5 导入；`ClaimReviewerAssignmentRequiredError` 与 `ClaimReviewerAssignmentInvalidError` 已在 Task 3 定义。

然后在 `services/claims.py` 追加：

```python
class ClaimReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


def _history_entry(
    event: str,
    *,
    actor_id: uuid.UUID,
    content_version: int,
    note: str,
    payload_sha256: str | None = None,
    second_reviewer_id: uuid.UUID | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {
        "event": event,
        "at": datetime.now(UTC).isoformat(),
        "actor_id": str(actor_id),
        "content_version": content_version,
        "note": note,
    }
    if payload_sha256 is not None:
        entry["payload_sha256"] = payload_sha256
    if second_reviewer_id is not None:
        entry["second_reviewer_id"] = str(second_reviewer_id)
    return entry


async def _get_claim_or_raise(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
) -> Claim:
    claim = await get_claim(session, workspace_id=workspace_id, claim_id=claim_id)
    if claim is None:
        raise ClaimNotFoundError()
    return claim


def reviewer_violation(
    claim_owner: uuid.UUID | None,
    reviewer_id: uuid.UUID,
    principals: ClaimTaskPrincipals | None,
) -> str | None:
    """返回审核人独立性问题。None 表示通过。"""
    if claim_owner is not None and claim_owner == reviewer_id:
        return "reviewer_is_claim_owner"
    if principals is not None and reviewer_id in {
        principals.owner_id,
        principals.requester_id,
    }:
        return "reviewer_is_task_principal"
    return None


def assert_reviewer_principal_independence(
    *,
    claim_owner: uuid.UUID | None,
    reviewer_id: uuid.UUID,
    principals: ClaimTaskPrincipals | None,
) -> None:
    violation = reviewer_violation(claim_owner, reviewer_id, principals)
    if violation == "reviewer_is_claim_owner":
        raise ClaimSelfReviewError()
    if violation is not None:
        raise ClaimReviewerAssignmentInvalidError(violation)


async def _load_internal_reviewer_assignment(
    session: AsyncSession,
    *,
    claim: Claim,
    reviewer_id: uuid.UUID,
    required_scope: str = REVIEWER_SCOPE_REVIEW,
) -> ReviewerAssignment:
    """只接受 C1/C2 的内部审核指派。客户角色即使有指派行也拒绝。"""
    role = await get_workspace_role(session, claim.workspace_id, reviewer_id)
    if role is not None:
        raise ClaimReviewerAssignmentInvalidError("reviewer_is_customer_member")
    await assert_claim_read_scope(
        session,
        workspace_id=claim.workspace_id,
        project_id=claim.project_id,
        user_id=reviewer_id,
    )
    assignment = await get_active_reviewer_assignment(
        session,
        workspace_id=claim.workspace_id,
        project_id=claim.project_id,
        user_id=reviewer_id,
        scopes=frozenset({required_scope}),
    )
    if assignment is None:
        raise ClaimReviewerAssignmentRequiredError()
    if assignment.assignment_scope != required_scope:
        raise ClaimReviewerAssignmentInvalidError("reviewer_scope_insufficient")
    return assignment


async def _load_second_reviewer_assignment(
    session: AsyncSession,
    *,
    claim: Claim,
    second_reviewer_id: uuid.UUID,
) -> ReviewerAssignment:
    try:
        return await _load_internal_reviewer_assignment(
            session,
            claim=claim,
            reviewer_id=second_reviewer_id,
        )
    except (ClaimReviewerAssignmentRequiredError, ClaimReviewerAssignmentInvalidError) as exc:
        raise ClaimSecondReviewerInvalidError(str(exc)) from exc


async def assert_claim_read_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ReviewerAssignment:
    """受限只读范围。`report_read` 与 `report_review` 都可用于读取。"""
    assignment = await get_active_reviewer_assignment(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        scopes=frozenset({REVIEWER_SCOPE_READ, REVIEWER_SCOPE_REVIEW}),
    )
    if assignment is None:
        raise ClaimReviewerAssignmentRequiredError()
    return assignment


async def submit_claim_for_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    actor_id: uuid.UUID,
    request_id: str | None = None,
) -> Claim:
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    status = ClaimReviewStatus(claim.review_status)
    if status not in {
        ClaimReviewStatus.DRAFT,
        ClaimReviewStatus.REJECTED,
        ClaimReviewStatus.STALE,
    }:
        raise ClaimReviewTransitionError(status.value)
    history = [
        *claim.review_history,
        _history_entry(
            "submit",
            actor_id=actor_id,
            content_version=claim.content_version,
            note="提交审核",
        ),
    ]
    claim = await update_claim_fields(
        session,
        claim,
        review_status=ClaimReviewStatus.PENDING.value,
        review_history=history,
    )
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=actor_id,
        action=AUDIT_ACTION_REVIEW_SUBMITTED,
        details={"content_version": claim.content_version},
        request_id=request_id,
    )
    return claim


async def review_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ClaimReviewDecision | str,
    note: str,
    approved_state: ClaimState | str | None = None,
    second_reviewer_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> Claim:
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    status = ClaimReviewStatus(claim.review_status)
    if status is not ClaimReviewStatus.PENDING:
        raise ClaimReviewTransitionError(status.value)
    principals = await get_claim_task_principals(session, run_id=claim.run_id)
    assert_reviewer_principal_independence(
        claim_owner=claim.owner,
        reviewer_id=reviewer_id,
        principals=principals,
    )
    assignment = await _load_internal_reviewer_assignment(
        session, claim=claim, reviewer_id=reviewer_id
    )
    decision_value = ClaimReviewDecision(decision)
    flags = {ClaimRiskFlag(flag) for flag in claim.risk_flags}
    needs_second = bool(flags & SECOND_REVIEW_RISK_FLAGS)
    second_assignment: ReviewerAssignment | None = None
    if needs_second:
        if second_reviewer_id is None:
            raise ClaimSecondReviewRequiredError()
        if second_reviewer_id in {reviewer_id, claim.owner}:
            raise ClaimSecondReviewerInvalidError("第二审核人不得是 owner 或第一审核人")
        assert_reviewer_principal_independence(
            claim_owner=claim.owner,
            reviewer_id=second_reviewer_id,
            principals=principals,
        )
        second_assignment = await _load_second_reviewer_assignment(
            session, claim=claim, second_reviewer_id=second_reviewer_id
        )
    elif second_reviewer_id is not None:
        raise ClaimSecondReviewerInvalidError("非敏感 claim 不接受第二审核人")

    now = datetime.now(UTC)
    note_text = note.strip()
    if decision_value is ClaimReviewDecision.REJECTED:
        history = [
            *claim.review_history,
            _history_entry(
                "reject",
                actor_id=reviewer_id,
                content_version=claim.content_version,
                note=note_text,
            ),
        ]
        claim = await update_claim_fields(
            session,
            claim,
            review_status=ClaimReviewStatus.REJECTED.value,
            review_note=note_text,
            reviewed_by=reviewer_id,
            reviewed_at=now,
            review_history=history,
        )
        await _append_claim_audit(
            session,
            claim=claim,
            actor_id=reviewer_id,
            action=AUDIT_ACTION_REVIEW_REJECTED,
            details={
                "reviewer_role": "internal_reviewer",
                "review_scope": assignment.assignment_scope,
                "assignment_id": str(assignment.id),
                "note": note_text,
            },
            request_id=request_id,
        )
        return claim

    state_value = _normalise_state(approved_state or claim.state)
    grade_value = (
        EvidenceGrade(claim.evidence_grade)
        if claim.evidence_grade is not None
        else None
    )
    assert_claim_state_within_grade(state_value, grade_value)
    assert_confirmed_requirements(
        state_value,
        grade_value,
        claim.independent_source_count,
        ClaimReviewStatus.APPROVED,
    )
    links = await list_evidence(session, claim_id=claim.id)
    payload_sha256 = claim_payload_sha256(
        claim, links, state_override=state_value
    )
    history = [
        *claim.review_history,
        _history_entry(
            "approve",
            actor_id=reviewer_id,
            content_version=claim.content_version,
            note=note_text,
            payload_sha256=payload_sha256,
            second_reviewer_id=second_reviewer_id,
        ),
    ]
    values: dict[str, object] = {
        "state": state_value.value,
        "review_status": ClaimReviewStatus.APPROVED.value,
        "review_note": note_text,
        "reviewed_by": reviewer_id,
        "reviewed_at": now,
        "reviewed_content_version": claim.content_version,
        "reviewed_payload_sha256": payload_sha256,
        "reviewed_profile": CANONICAL_PROFILE_ID,
        "review_history": history,
    }
    if second_reviewer_id is not None:
        values["second_reviewed_by"] = second_reviewer_id
        values["second_reviewed_at"] = now
    claim = await update_claim_fields(session, claim, **values)
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=reviewer_id,
        action=AUDIT_ACTION_REVIEW_APPROVED,
        details={
            "reviewer_role": "internal_reviewer",
            "review_scope": assignment.assignment_scope,
            "assignment_id": str(assignment.id),
            "second_assignment_id": (
                str(second_assignment.id) if second_assignment is not None else None
            ),
            "note": note_text,
            "payload_sha256": payload_sha256,
        },
        request_id=request_id,
    )
    return claim


async def override_claim_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ClaimReviewDecision | str,
    reason: str,
    approved_state: ClaimState | str | None = None,
    second_reviewer_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> Claim:
    """覆盖已批准的审核结论。必须由内部审核人带原因执行，并写统一审计。"""
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    if ClaimReviewStatus(claim.review_status) is not ClaimReviewStatus.APPROVED:
        raise ClaimReviewTransitionError(claim.review_status)
    reason_text = reason.strip()
    if not reason_text:
        raise ValueError("override 必须给出原因")
    principals = await get_claim_task_principals(session, run_id=claim.run_id)
    assert_reviewer_principal_independence(
        claim_owner=claim.owner,
        reviewer_id=reviewer_id,
        principals=principals,
    )
    assignment = await _load_internal_reviewer_assignment(
        session, claim=claim, reviewer_id=reviewer_id
    )
    flags = {ClaimRiskFlag(flag) for flag in claim.risk_flags}
    second_assignment: ReviewerAssignment | None = None
    if flags & SECOND_REVIEW_RISK_FLAGS:
        if second_reviewer_id is None:
            raise ClaimSecondReviewRequiredError()
        if second_reviewer_id in {reviewer_id, claim.owner}:
            raise ClaimSecondReviewerInvalidError("第二审核人不得是 owner 或第一审核人")
        assert_reviewer_principal_independence(
            claim_owner=claim.owner,
            reviewer_id=second_reviewer_id,
            principals=principals,
        )
        second_assignment = await _load_second_reviewer_assignment(
            session, claim=claim, second_reviewer_id=second_reviewer_id
        )
    elif second_reviewer_id is not None:
        raise ClaimSecondReviewerInvalidError("非敏感 claim 不接受第二审核人")

    decision_value = ClaimReviewDecision(decision)
    previous_status = claim.review_status
    now = datetime.now(UTC)
    if decision_value is ClaimReviewDecision.REJECTED:
        state_value = (
            ClaimState.DIRECTIONAL
            if ClaimState(claim.state) is ClaimState.CONFIRMED
            else ClaimState(claim.state)
        )
        history = [
            *claim.review_history,
            _history_entry(
                "override_reject",
                actor_id=reviewer_id,
                content_version=claim.content_version,
                note=reason_text,
            ),
        ]
        claim = await update_claim_fields(
            session,
            claim,
            state=state_value.value,
            review_status=ClaimReviewStatus.REJECTED.value,
            review_note=reason_text,
            reviewed_by=reviewer_id,
            reviewed_at=now,
            reviewed_content_version=claim.content_version,
            reviewed_payload_sha256=None,
            reviewed_profile=None,
            second_reviewed_by=None,
            second_reviewed_at=None,
            review_history=history,
        )
    else:
        state_value = _normalise_state(approved_state or claim.state)
        grade_value = (
            EvidenceGrade(claim.evidence_grade)
            if claim.evidence_grade is not None
            else None
        )
        assert_claim_state_within_grade(state_value, grade_value)
        assert_confirmed_requirements(
            state_value,
            grade_value,
            claim.independent_source_count,
            ClaimReviewStatus.APPROVED,
        )
        links = await list_evidence(session, claim_id=claim.id)
        payload_sha256 = claim_payload_sha256(
            claim, links, state_override=state_value
        )
        history = [
            *claim.review_history,
            _history_entry(
                "override_approve",
                actor_id=reviewer_id,
                content_version=claim.content_version,
                note=reason_text,
                payload_sha256=payload_sha256,
                second_reviewer_id=second_reviewer_id,
            ),
        ]
        values: dict[str, object] = {
            "state": state_value.value,
            "review_status": ClaimReviewStatus.APPROVED.value,
            "review_note": reason_text,
            "reviewed_by": reviewer_id,
            "reviewed_at": now,
            "reviewed_content_version": claim.content_version,
            "reviewed_payload_sha256": payload_sha256,
            "reviewed_profile": CANONICAL_PROFILE_ID,
            "review_history": history,
        }
        if second_reviewer_id is not None:
            values["second_reviewed_by"] = second_reviewer_id
            values["second_reviewed_at"] = now
        claim = await update_claim_fields(session, claim, **values)
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=reviewer_id,
        action=AUDIT_ACTION_REVIEW_OVERRIDDEN,
        details={
            "reviewer_role": "internal_reviewer",
            "review_scope": assignment.assignment_scope,
            "assignment_id": str(assignment.id),
            "second_assignment_id": (
                str(second_assignment.id) if second_assignment is not None else None
            ),
            "previous_review_status": previous_status,
            "new_review_status": claim.review_status,
            "reason": reason_text,
        },
        request_id=request_id,
    )
    return claim


async def block_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    actor_id: uuid.UUID,
    blocked_reason: ClaimBlockedReason | str,
    note: str = "",
    request_id: str | None = None,
) -> Claim:
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    if ClaimState(claim.state) is ClaimState.BLOCKED:
        raise ClaimReviewTransitionError("already_blocked")
    reason = _normalise_blocked_reason(blocked_reason)
    if reason is None:
        raise ClaimBlockedReasonRequiredError()
    content_version = claim.content_version + 1
    history = [
        *claim.review_history,
        _history_entry(
            "block",
            actor_id=actor_id,
            content_version=content_version,
            note=note.strip(),
        ),
    ]
    values: dict[str, object] = {
        "state": ClaimState.BLOCKED.value,
        "blocked_reason": reason.value,
        "content_version": content_version,
        "review_history": history,
    }
    if ClaimReviewStatus(claim.review_status) in {
        ClaimReviewStatus.PENDING,
        ClaimReviewStatus.APPROVED,
    }:
        values.update(
            review_status=ClaimReviewStatus.STALE.value,
            reviewed_by=None,
            reviewed_at=None,
            reviewed_content_version=None,
            reviewed_payload_sha256=None,
            reviewed_profile=None,
            second_reviewed_by=None,
            second_reviewed_at=None,
        )
    claim = await update_claim_fields(session, claim, **values)
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=actor_id,
        action=AUDIT_ACTION_BLOCKED,
        details={"blocked_reason": reason.value, "note": note.strip()},
        request_id=request_id,
    )
    return claim


async def unblock_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    actor_id: uuid.UUID,
    state: ClaimState | str = ClaimState.HYPOTHESIS,
    note: str = "",
    request_id: str | None = None,
) -> Claim:
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    if ClaimState(claim.state) is not ClaimState.BLOCKED:
        raise ClaimReviewTransitionError(claim.state)
    target = _normalise_state(state)
    if target in {ClaimState.BLOCKED, ClaimState.CONFIRMED}:
        raise ClaimReviewTransitionError(target.value)
    grade_value = (
        EvidenceGrade(claim.evidence_grade)
        if claim.evidence_grade is not None
        else None
    )
    assert_claim_state_within_grade(target, grade_value)
    content_version = claim.content_version + 1
    history = [
        *claim.review_history,
        _history_entry(
            "unblock",
            actor_id=actor_id,
            content_version=content_version,
            note=note.strip(),
        ),
    ]
    values: dict[str, object] = {
        "state": target.value,
        "blocked_reason": None,
        "content_version": content_version,
        "review_history": history,
    }
    if ClaimReviewStatus(claim.review_status) is ClaimReviewStatus.APPROVED:
        values.update(
            review_status=ClaimReviewStatus.STALE.value,
            reviewed_by=None,
            reviewed_at=None,
            reviewed_content_version=None,
            reviewed_payload_sha256=None,
            reviewed_profile=None,
            second_reviewed_by=None,
            second_reviewed_at=None,
        )
    claim = await update_claim_fields(session, claim, **values)
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=actor_id,
        action=AUDIT_ACTION_UNBLOCKED,
        details={"state": target.value, "note": note.strip()},
        request_id=request_id,
    )
    return claim


async def revise_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
    actor_id: uuid.UUID,
    claim_text: str | None = None,
    text_en: str | None = None,
    scope_market: str | None = None,
    scope_window_start: date | None = None,
    scope_window_end: date | None = None,
    scope_window_days: int | None = None,
    scope_sample_n: int | None = None,
    counterevidence_text: str | None = None,
    risk_flags: object | None = None,
    blocked_reason: ClaimBlockedReason | str | None = None,
    request_id: str | None = None,
) -> Claim:
    claim = await _get_claim_or_raise(
        session, workspace_id=workspace_id, claim_id=claim_id
    )
    changes: dict[str, object] = {}
    if claim_text is not None:
        text = claim_text.strip()
        if not text:
            raise ValueError("claim_text 不能为空")
        changes["claim_text"] = text
    if text_en is not None:
        english = text_en.strip()
        if not english:
            raise ValueError("text_en 不能为空")
        changes["text_en"] = english
    if counterevidence_text is not None:
        counter = counterevidence_text.strip()
        if not counter:
            raise ValueError("counterevidence_text 不能为空")
        changes["counterevidence_text"] = counter
    scope_values = (
        scope_market,
        scope_window_start,
        scope_window_end,
        scope_window_days,
        scope_sample_n,
    )
    if any(value is not None for value in scope_values):
        scope = _normalise_scope(
            scope_market if scope_market is not None else claim.scope_market,
            scope_window_start if scope_window_start is not None else claim.scope_window_start,
            scope_window_end if scope_window_end is not None else claim.scope_window_end,
            scope_window_days if scope_window_days is not None else claim.scope_window_days,
            scope_sample_n if scope_sample_n is not None else claim.scope_sample_n,
        )
        if scope is not None:
            (
                changes["scope_market"],
                changes["scope_window_start"],
                changes["scope_window_end"],
                changes["scope_window_days"],
                changes["scope_sample_n"],
            ) = scope
    if risk_flags is not None:
        flags = normalise_risk_flags(risk_flags, independent_count=claim.independent_source_count)
        changes["risk_flags"] = sorted(flag.value for flag in flags)
    if blocked_reason is not None:
        blocked = _normalise_blocked_reason(blocked_reason)
        if ClaimState(claim.state) is not ClaimState.BLOCKED and blocked is not None:
            raise ValueError("只有 blocked 状态可以带 blocked_reason")
        changes["blocked_reason"] = blocked.value if blocked is not None else None
    if not changes:
        return claim

    content_version = claim.content_version + 1
    history = [
        *claim.review_history,
        _history_entry(
            "revise",
            actor_id=actor_id,
            content_version=content_version,
            note="内容修订",
        ),
    ]
    changes.update(
        content_version=content_version,
        review_history=history,
    )
    if ClaimReviewStatus(claim.review_status) in {
        ClaimReviewStatus.PENDING,
        ClaimReviewStatus.APPROVED,
    }:
        changes.update(
            review_status=ClaimReviewStatus.STALE.value,
            reviewed_by=None,
            reviewed_at=None,
            reviewed_content_version=None,
            reviewed_payload_sha256=None,
            reviewed_profile=None,
            second_reviewed_by=None,
            second_reviewed_at=None,
        )
    claim = await update_claim_fields(session, claim, **changes)
    await _append_claim_audit(
        session,
        claim=claim,
        actor_id=actor_id,
        action=AUDIT_ACTION_REVISED,
        details={"content_version": claim.content_version},
        request_id=request_id,
    )
    return claim
```

顶部导入补充 `from enum import StrEnum`（`services/claims.py` 当前没有）。

- [ ] **Step 5: 运行审核测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_review.py -q
```

Expected: `19 passed`。

- [ ] **Step 6: 运行 claim 全量回归**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claims.py tests/unit/test_claim_creation_governance.py tests/unit/test_claim_review.py -q
```

Expected: `48 passed`。

- [ ] **Step 7: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "create_claim_with_evidence" --direction upstream --repo .
node .gitnexus/run.cjs impact "ClaimReviewStatus" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/claim_signing.py apps/api/src/data_intelligence_hub/services/claims.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/src/data_intelligence_hub/repositories/claims.py apps/api/tests/unit/test_claim_review.py
git commit -m "feat(claims): 内部审核指派、覆盖阻断与统一审计"
```

`impact` 报 `HIGH`/`CRITICAL` 时停止。`detect-changes` 出现 `partial`/`truncated` 时重跑。

---

### Task 7: 可发布 Claim 合同行与正式门禁

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/claims.py`
- Test: `apps/api/tests/unit/test_claim_contract_rows.py`

**Interfaces:**
- Consumes: Task 5/6 的 claim、link、evidence 行；C1 的 `Claim` 合同字段；C4 的 `workflow_versions.workbench_task_id` 与 C6 的 `runs.workflow_version_id`（`task_id` 过滤链）。
- Produces:
  - `ClaimScopeRow`
  - `ClaimContractRow`
  - `EvidenceContractRow`
  - `ClaimContractBundle`
  - `load_publishable_claim_rows(session, *, workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID | None = None) -> ClaimContractBundle`
    - `task_id=None` 只按工作区与项目过滤，保持 C10/C13 既有调用行为。
    - `task_id` 非空时沿 `Claim.run_id -> Run.workflow_version_id -> WorkflowVersion.workbench_task_id` 过滤到该任务单；C9 装配必须传 `task_id`，未关联 run 的旧 Claim 不返回。
  - `validate_claim_bundle()`
  - `assert_claim_bundle_publishable()`

- [ ] **Step 1: 写失败测试**

```python
"""C7：可发布 Claim 合同行与门禁。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.claims import (
    assert_claim_bundle_publishable,
    create_claim_with_evidence,
    load_publishable_claim_rows,
    review_claim,
    submit_claim_for_review,
    validate_claim_bundle,
)
from data_intelligence_hub.services.exceptions import ClaimBundleNotPublishableError


class Seed:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self) -> Seed:
        self.owner = User(
            email=f"rows-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        self.reviewer = User(
            email=f"rows-reviewer-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Reviewer",
        )
        self.session.add_all([self.owner, self.reviewer])
        await self.session.flush()
        self.workspace = Workspace(
            name="Rows",
            slug=f"rows-{uuid.uuid4().hex}",
            owner_id=self.owner.id,
        )
        self.session.add(self.workspace)
        await self.session.flush()
        self.session.add(
            WorkspaceMember(
                workspace_id=self.workspace.id,
                user_id=self.owner.id,
                role="owner",
            )
        )
        await self.session.flush()
        self.project = Project(
            workspace_id=self.workspace.id,
            name="Rows",
            domain="mother_baby",
            owner_id=self.owner.id,
        )
        self.session.add(self.project)
        await self.session.flush()
        self.item = IntelligenceItem(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            title="Item",
            summary="Summary",
            intelligence_type="signal",
            impact_score=0.5,
            confidence_score=0.5,
            novelty_score=0.5,
            urgency_score=0.5,
            final_score=0.5,
            generated_by="system",
            domain="mother_baby",
        )
        self.session.add(self.item)
        await self.session.flush()
        self.support = await self._evidence("support", "https://example.com/a")
        self.counter = await self._evidence("counter", "https://example.com/b")
        return self

    async def _evidence(self, title: str, url: str) -> Evidence:
        evidence = Evidence(
            intelligence_id=self.item.id,
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            evidence_type="web",
            title=title,
            url=url,
            evidence_grade="L4_authorized_live",
            market="US",
            locale="en-US",
            source_tool_id="tikhub.products",
            provider_id="tikhub",
            captured_at=datetime.now(UTC),
            source_cluster_key=f"url:{url}",
            source_cluster_basis="url",
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def task_run(self, name: str) -> tuple[WorkbenchTask, Run]:
        """在同一项目内创建任务单、计划版本与 run。"""
        task = WorkbenchTask(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            created_by_user_id=self.owner.id,
            owner_id=self.owner.id,
            brand=name,
            category="mother_baby",
            competitors=[],
            package_type="standard",
            primary_market="US",
            comparison_markets=[],
            seed_products=[],
            markets=["US"],
            locale_by_market={"US": "en-US"},
            window_start=date(2026, 1, 1),
            window_end=date(2026, 3, 1),
            decision_question="美国市场是否需要该品类？",
            does_not_answer=["不推断销量与市场份额"],
            status="submitted",
        )
        self.session.add(task)
        await self.session.flush()
        plan = WorkflowPlan(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            created_by_user_id=self.owner.id,
            name=f"{name} plan",
            flow_mode="batch_research",
            status="approved",
        )
        self.session.add(plan)
        await self.session.flush()
        version = WorkflowVersion(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            workflow_plan_id=plan.id,
            workbench_task_id=task.id,
            created_by_user_id=self.owner.id,
            version_number=1,
            planning_status="resolved",
            planner_contract_version="workflow_planner.v1",
            catalog_snapshot_id="catalog-v1",
            policy_version="policy.v1",
            mode_template_version="template.v1",
            query_versions={},
            fingerprint_payload={},
            normalized_input={},
            plan_payload={"execution_steps": []},
            preview_fingerprint="sha256:" + "a" * 64,
        )
        self.session.add(version)
        await self.session.flush()
        run = Run(
            workspace_id=self.workspace.id,
            project_id=self.project.id,
            workflow_version_id=version.id,
            status="completed",
            outcome="success",
            market_code="US",
        )
        self.session.add(run)
        await self.session.flush()
        return task, run

    async def claim(self, **overrides: object):
        values: dict[str, object] = {
            "workspace_id": self.workspace.id,
            "project_id": self.project.id,
            "claim_text": "美国市场母婴新品有需求",
            "text_en": "US demand exists for the new baby product",
            "owner": self.owner.id,
            "scope_market": "US",
            "scope_window_start": date(2026, 1, 1),
            "scope_window_end": date(2026, 3, 1),
            "scope_window_days": 60,
            "scope_sample_n": 120,
            "counterevidence_text": "未发现反证",
            "evidence": [
                (self.support.id, "support"),
                (self.counter.id, "counter"),
            ],
            "evidence_grade": "L4_authorized_live",
            "state": "directional",
        }
        values.update(overrides)
        return await create_claim_with_evidence(self.session, **values)

    async def approve(self, claim):
        await submit_claim_for_review(
            self.session,
            workspace_id=self.workspace.id,
            claim_id=claim.id,
            actor_id=self.owner.id,
        )
        return await review_claim(
            self.session,
            workspace_id=self.workspace.id,
            claim_id=claim.id,
            reviewer_id=self.reviewer.id,
            decision="approved",
            note="通过",
        )


async def _with_session(callback) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(await Seed(session).build())
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_only_approved_current_claims_are_published() -> None:
    async def scenario(seed: Seed) -> None:
        approved = await seed.approve(await seed.claim())
        await seed.claim()  # draft, must be excluded
        bundle = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
        )
        assert [row.claim_id for row in bundle.claims] == [str(approved.id)]
        assert validate_claim_bundle(bundle) == []

    await _with_session(scenario)


@pytest.mark.anyio
async def test_confirmed_requires_two_independent_sources() -> None:
    async def scenario(seed: Seed) -> None:
        seed.counter.source_cluster_key = seed.support.source_cluster_key
        claim = await seed.claim(evidence_grade="L3_live_single", state="directional")
        await seed.approve(claim)
        # 人工把状态改成 confirmed 会越过服务；门禁必须抓住。
        claim.state = "confirmed"
        claim.evidence_grade = "L4_authorized_live"
        await seed.session.flush()
        bundle = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
        )
        issues = validate_claim_bundle(bundle)
        assert any("独立来源" in issue for issue in issues)
        with pytest.raises(ClaimBundleNotPublishableError):
            assert_claim_bundle_publishable(bundle)

    await _with_session(scenario)


@pytest.mark.anyio
async def test_missing_evidence_metadata_is_rejected() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.claim()
        seed.support.market = None
        await seed.session.flush()
        await seed.approve(claim)
        bundle = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
        )
        issues = validate_claim_bundle(bundle)
        assert any("market" in issue for issue in issues)

    await _with_session(scenario)


@pytest.mark.anyio
async def test_cross_workspace_claim_is_excluded() -> None:
    async def scenario(seed: Seed) -> None:
        claim = await seed.approve(await seed.claim())
        other = Workspace(
            name="Other",
            slug=f"other-{uuid.uuid4().hex}",
            owner_id=seed.owner.id,
        )
        seed.session.add(other)
        await seed.session.flush()
        bundle = await load_publishable_claim_rows(
            seed.session,
            workspace_id=other.id,
            project_id=seed.project.id,
        )
        assert bundle.claims == ()
        assert bundle.evidences == ()

    await _with_session(scenario)


@pytest.mark.anyio
async def test_task_filter_returns_only_that_tasks_claims() -> None:
    async def scenario(seed: Seed) -> None:
        task_a, run_a = await seed.task_run("Task A")
        task_b, run_b = await seed.task_run("Task B")
        claim_a = await seed.approve(await seed.claim(run_id=run_a.id))
        claim_b = await seed.approve(await seed.claim(run_id=run_b.id))

        scoped_a = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            task_id=task_a.id,
        )
        scoped_b = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            task_id=task_b.id,
        )
        unscoped = await load_publishable_claim_rows(
            seed.session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
        )

        assert [row.claim_id for row in scoped_a.claims] == [str(claim_a.id)]
        assert [row.claim_id for row in scoped_b.claims] == [str(claim_b.id)]
        assert {row.claim_id for row in unscoped.claims} == {
            str(claim_a.id),
            str(claim_b.id),
        }

    await _with_session(scenario)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_contract_rows.py -q
```

Expected: FAIL。函数不存在时为 `ImportError: cannot import name 'load_publishable_claim_rows'`；函数已存在但缺少 `task_id` 时，`test_task_filter_returns_only_that_tasks_claims` 报 `TypeError: load_publishable_claim_rows() got an unexpected keyword argument 'task_id'`。

- [ ] **Step 3: 实现合同行与门禁**

在 `services/claims.py` 顶部加入以下导入（`Claim`、`is_formal_market`、`date`、`uuid`、`datetime` 已在 Task 3/6 导入）：

```python
from dataclasses import dataclass

from sqlalchemy import select

from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
```

然后追加：

```python
@dataclass(frozen=True, slots=True)
class ClaimScopeRow:
    market: str | None
    window_start: date | None
    window_end: date | None
    window_days: int | None
    sample_n: int | None


@dataclass(frozen=True, slots=True)
class ClaimContractRow:
    claim_id: str
    text: str
    text_en: str | None
    claim_status: ClaimState
    evidence_grade: EvidenceGrade | None
    risk_flags: tuple[str, ...]
    review_status: ClaimReviewStatus
    independent_source_count: int
    blocked_reason: str | None
    scope: ClaimScopeRow
    counterevidence_text: str | None
    owner: uuid.UUID | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceContractRow:
    evidence_id: str
    claim_id: str
    role: EvidenceRole
    raw_record_id: uuid.UUID | None
    source_tool_id: str | None
    url: str | None
    excerpt: str | None
    captured_at: datetime | None
    market: str | None
    locale: str | None
    evidence_grade: EvidenceGrade | None
    source_cluster_key: str | None
    source_cluster_basis: str | None
    independent: bool


@dataclass(frozen=True, slots=True)
class ClaimContractBundle:
    claims: tuple[ClaimContractRow, ...]
    evidences: tuple[EvidenceContractRow, ...]


def _require_text(value: str | None, field: str, claim_id: uuid.UUID) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(f"claim {claim_id} 的 {field} 为空")
    return text


async def _load_task_claim_ids(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
) -> set[uuid.UUID]:
    """沿 claims.run_id -> runs.workflow_version_id ->
    workflow_versions.workbench_task_id 返回属于该任务单的 Claim ID。

    三张表都同时应用工作区与项目过滤；未关联 run、run 未关联计划版本，
    或计划版本属于其他任务单的 Claim 不在结果中。
    """
    statement = (
        select(Claim.id)
        .join(Run, Run.id == Claim.run_id)
        .join(WorkflowVersion, WorkflowVersion.id == Run.workflow_version_id)
        .where(
            Claim.workspace_id == workspace_id,
            Claim.project_id == project_id,
            Run.workspace_id == workspace_id,
            Run.project_id == project_id,
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workbench_task_id == task_id,
        )
    )
    return set((await session.execute(statement)).scalars().all())


async def load_publishable_claim_rows(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
) -> ClaimContractBundle:
    """加载已审核且内容版本一致的 Claim，组装合同行。

    本函数只返回 approved 且 reviewed_content_version == content_version 的行。
    缺字段不在本函数抛错；由 ``validate_claim_bundle`` 汇总问题。

    工作区与项目过滤始终生效。``task_id`` 为空时保持 C10/C13 的既有行为；
    ``task_id`` 非空时沿
    ``claims.run_id -> runs.workflow_version_id -> workflow_versions.workbench_task_id``
    过滤到该任务单，C9 装配必须传 ``task_id``。
    """
    task_claim_ids: set[uuid.UUID] | None = None
    if task_id is not None:
        task_claim_ids = await _load_task_claim_ids(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
        )
    claims = await list_claims(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    rows: list[ClaimContractRow] = []
    evidence_rows: list[EvidenceContractRow] = []
    for claim in claims:
        if task_claim_ids is not None and claim.id not in task_claim_ids:
            continue
        if ClaimReviewStatus(claim.review_status) is not ClaimReviewStatus.APPROVED:
            continue
        if claim.reviewed_content_version != claim.content_version:
            continue
        links = await list_evidence(session, claim_id=claim.id)
        evidence_ids = [link.evidence_id for link in links]
        loaded = await load_evidence_rows(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            evidence_ids=evidence_ids,
        )
        by_id = {row.id: row for row in loaded}
        rows.append(
            ClaimContractRow(
                claim_id=str(claim.id),
                text=claim.claim_text,
                text_en=claim.text_en,
                claim_status=ClaimState(claim.state),
                evidence_grade=(
                    EvidenceGrade(claim.evidence_grade)
                    if claim.evidence_grade is not None
                    else None
                ),
                risk_flags=tuple(sorted(claim.risk_flags)),
                review_status=ClaimReviewStatus(claim.review_status),
                independent_source_count=claim.independent_source_count,
                blocked_reason=claim.blocked_reason,
                scope=ClaimScopeRow(
                    market=claim.scope_market,
                    window_start=claim.scope_window_start,
                    window_end=claim.scope_window_end,
                    window_days=claim.scope_window_days,
                    sample_n=claim.scope_sample_n,
                ),
                counterevidence_text=claim.counterevidence_text,
                owner=claim.owner,
                evidence_ids=tuple(sorted({str(link.evidence_id) for link in links})),
            )
        )
        for link in links:
            evidence = by_id.get(link.evidence_id)
            if evidence is None:
                continue
            evidence_rows.append(
                EvidenceContractRow(
                    evidence_id=str(evidence.id),
                    claim_id=str(claim.id),
                    role=EvidenceRole(link.role),
                    raw_record_id=evidence.raw_record_id,
                    source_tool_id=evidence.source_tool_id,
                    url=evidence.url,
                    excerpt=evidence.excerpt,
                    captured_at=evidence.captured_at or evidence.created_at,
                    market=evidence.market,
                    locale=evidence.locale,
                    evidence_grade=(
                        EvidenceGrade(link.evidence_grade)
                        if link.evidence_grade is not None
                        else None
                    ),
                    source_cluster_key=link.source_cluster_key,
                    source_cluster_basis=link.source_cluster_basis,
                    independent=link.independent,
                )
            )
    return ClaimContractBundle(claims=tuple(rows), evidences=tuple(evidence_rows))


def validate_claim_bundle(bundle: ClaimContractBundle) -> list[str]:
    """正式交付门禁。返回问题列表，空列表表示可发布。"""
    issues: list[str] = []
    claim_ids = {row.claim_id for row in bundle.claims}
    evidence_by_claim: dict[str, list[EvidenceContractRow]] = {}
    for evidence in bundle.evidences:
        evidence_by_claim.setdefault(evidence.claim_id, []).append(evidence)
    for claim in bundle.claims:
        evidences = evidence_by_claim.get(claim.claim_id, [])
        roles = {evidence.role.value for evidence in evidences}
        if not (claim.text or "").strip():
            issues.append(f"claim {claim.claim_id} 的 text 为空")
        if not (claim.text_en or "").strip():
            issues.append(f"claim {claim.claim_id} 的 text_en 为空")
        if not (claim.counterevidence_text or "").strip():
            issues.append(f"claim {claim.claim_id} 的 counterevidence_text 为空")
        if claim.owner is None:
            issues.append(f"claim {claim.claim_id} 的 owner 为空")
        if not claim.scope.market or not is_formal_market(claim.scope.market):
            issues.append(f"claim {claim.claim_id} 的 scope.market 不是正式市场")
        if claim.scope.window_start is None or claim.scope.window_end is None:
            issues.append(f"claim {claim.claim_id} 的 scope.window 缺失")
        elif claim.scope.window_end < claim.scope.window_start:
            issues.append(f"claim {claim.claim_id} 的 scope.window 顺序错误")
        elif claim.scope.window_days != (
            claim.scope.window_end - claim.scope.window_start
        ).days + 1:
            issues.append(f"claim {claim.claim_id} 的 scope.window.days 不一致")
        if claim.scope.sample_n is None or claim.scope.sample_n < 0:
            issues.append(f"claim {claim.claim_id} 的 scope.sample_n 无效")
        if claim.review_status is not ClaimReviewStatus.APPROVED:
            issues.append(f"claim {claim.claim_id} 未审核")
        if "counter" not in roles and "gap" not in roles:
            issues.append(f"claim {claim.claim_id} 缺少 counter 或 gap 证据")
        if not claim.evidence_ids:
            issues.append(f"claim {claim.claim_id} 没有证据")
        if {evidence.evidence_id for evidence in evidences} != set(claim.evidence_ids):
            issues.append(f"claim {claim.claim_id} 的证据行不完整")
        independent_keys = {
            evidence.source_cluster_key
            for evidence in evidences
            if evidence.independent and evidence.source_cluster_key
        }
        if len(independent_keys) != claim.independent_source_count:
            issues.append(f"claim {claim.claim_id} 的独立来源数与证据簇不一致")
        if claim.evidence_grade is None:
            issues.append(f"claim {claim.claim_id} 缺少证据等级")
        else:
            grades = [
                evidence.evidence_grade
                for evidence in evidences
                if evidence.evidence_grade is not None
            ]
            if grades and GRADE_ORDER[claim.evidence_grade] > min(
                GRADE_ORDER[grade] for grade in grades
            ):
                issues.append(f"claim {claim.claim_id} 的证据等级高于其证据")
            if claim.claim_status is ClaimState.CONFIRMED:
                if claim.evidence_grade is not EvidenceGrade.L4_AUTHORIZED_LIVE:
                    issues.append(f"claim {claim.claim_id} 的 confirmed 不是 L4")
                if claim.independent_source_count < 2:
                    issues.append(f"claim {claim.claim_id} 的独立来源少于 2")
            elif claim.claim_status is ClaimState.DIRECTIONAL:
                if claim.evidence_grade not in {
                    EvidenceGrade.L3_LIVE_SINGLE,
                    EvidenceGrade.L4_AUTHORIZED_LIVE,
                }:
                    issues.append(f"claim {claim.claim_id} 的 directional 低于 L3")
            elif claim.claim_status is ClaimState.HYPOTHESIS:
                if claim.evidence_grade not in {
                    EvidenceGrade.L2_FIXTURE_LOCAL,
                    EvidenceGrade.L3_LIVE_SINGLE,
                    EvidenceGrade.L4_AUTHORIZED_LIVE,
                }:
                    issues.append(f"claim {claim.claim_id} 的 hypothesis 低于 L2")
        if claim.claim_status is ClaimState.BLOCKED and not claim.blocked_reason:
            issues.append(f"claim {claim.claim_id} 的 blocked 缺少原因")
    for evidence in bundle.evidences:
        if evidence.claim_id not in claim_ids:
            issues.append(f"evidence {evidence.evidence_id} 关联了不存在的 claim")
        if not evidence.source_tool_id:
            issues.append(f"evidence {evidence.evidence_id} 缺少 source_tool_id")
        if not evidence.market:
            issues.append(f"evidence {evidence.evidence_id} 缺少 market")
        if not evidence.locale:
            issues.append(f"evidence {evidence.evidence_id} 缺少 locale")
        if evidence.evidence_grade is None:
            issues.append(f"evidence {evidence.evidence_id} 缺少证据等级")
        if evidence.captured_at is None:
            issues.append(f"evidence {evidence.evidence_id} 缺少 captured_at")
        if evidence.role.value in {"support", "counter"} and not evidence.url:
            issues.append(f"evidence {evidence.evidence_id} 缺少来源 URL")
    return issues


def assert_claim_bundle_publishable(bundle: ClaimContractBundle) -> None:
    issues = validate_claim_bundle(bundle)
    if issues:
        raise ClaimBundleNotPublishableError(issues)
```

在 `services/exceptions.py` 追加：

```python
class ClaimBundleNotPublishableError(ServiceError):
    message = "claim_bundle_not_publishable"

    def __init__(self, issues: list[str]) -> None:
        super().__init__(self.message)
        self.issues = issues
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_contract_rows.py -q
```

Expected: `5 passed`。其中 `test_task_filter_returns_only_that_tasks_claims` 证明同一项目内两个任务单只返回各自 run 关联的 Claim，省略 `task_id` 时仍返回两条。

- [ ] **Step 5: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "load_publishable_claim_rows" --direction upstream --repo . 2>/dev/null || true
node .gitnexus/run.cjs impact "validate_claim_bundle" --direction upstream --repo . 2>/dev/null || true
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/claims.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_claim_contract_rows.py
git commit -m "feat(claims): 可发布主张合同行与正式门禁"
```

两个新符号首次出现时 `impact` 可能返回 UNKNOWN；用 `git grep -n "load_publishable_claim_rows\|validate_claim_bundle" apps/api/src apps/api/tests` 确认尚未接线，再继续。

---

### Task 7B: C9 消费的语义证据规则

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/claim_semantics.py`
- Test: `apps/api/tests/unit/test_claim_semantics.py`

**Interfaces:**
- Consumes: Task 7 的 `ClaimContractBundle`、`ClaimContractRow`、`EvidenceContractRow`；C1 的 `claim_status`、`market_quality`、`evidence_grade`、`market_assessments.conclusion_standard`/`conclusion_quick` 枚举；C4 的 `PACKAGE_TYPES`；C8 的 `allowed_conclusions()` 语义（C7 不 import C8，只固化已批准规则）。
- Produces:
  - `MIN_DO_NOT_ENTER_CLUSTERS`
  - `MarketConclusionRow`
  - `market_independent_cluster_count()`
  - `validate_claim_semantics()`
  - `assert_claim_semantics()`

**规则来源（只使用已批准项）：**
- 设计 §5.2 与 O1：`do_not_enter` 只允许市场 `quality_status='qualified'`，且至少 2 个独立原始记录簇支持；不能由缺失或失败推导。
- 设计 §5.3：`confirmed` 只能是 L4，且至少 2 个独立原始记录簇，且已审核。
- 设计 §4.2：Quick 的所有标签都是方向性的；Quick 不得出现 `confirmed`，不得输出 Standard 四态。
- 独立簇的判定只复用 Task 2 已写入 `EvidenceContractRow` 的 `source_cluster_key`/`independent`，本任务不重新计算簇。

- [ ] **Step 1: 写失败测试**

```python
"""C7：C9 消费的语义证据规则。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from data_intelligence_hub.models.claim import ClaimReviewStatus, ClaimState, EvidenceRole
from data_intelligence_hub.services.claim_semantics import (
    MIN_DO_NOT_ENTER_CLUSTERS,
    assert_claim_semantics,
    market_independent_cluster_count,
    validate_claim_semantics,
)
from data_intelligence_hub.services.claims import (
    ClaimContractBundle,
    ClaimContractRow,
    ClaimScopeRow,
    EvidenceContractRow,
)
from data_intelligence_hub.services.exceptions import ClaimBundleNotPublishableError
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade


def _claim(
    *,
    claim_id: str,
    market: str = "US",
    status: ClaimState = ClaimState.DIRECTIONAL,
    grade: EvidenceGrade | None = EvidenceGrade.L4_AUTHORIZED_LIVE,
    review: ClaimReviewStatus = ClaimReviewStatus.APPROVED,
    independent: int = 2,
) -> ClaimContractRow:
    return ClaimContractRow(
        claim_id=claim_id,
        text="美国市场母婴新品有需求",
        text_en="US demand exists",
        claim_status=status,
        evidence_grade=grade,
        risk_flags=(),
        review_status=review,
        independent_source_count=independent,
        blocked_reason=None,
        scope=ClaimScopeRow(
            market=market,
            window_start=date(2026, 1, 1),
            window_end=date(2026, 3, 1),
            window_days=60,
            sample_n=100,
        ),
        counterevidence_text="未发现反证",
        owner=uuid.uuid4(),
        evidence_ids=(f"ev-{claim_id}",),
    )


def _evidence(
    *,
    claim_id: str,
    evidence_id: str,
    cluster: str | None,
    independent: bool = True,
    market: str = "US",
) -> EvidenceContractRow:
    return EvidenceContractRow(
        evidence_id=evidence_id,
        claim_id=claim_id,
        role=EvidenceRole.SUPPORT,
        raw_record_id=None,
        source_tool_id="tikhub.products",
        url="https://example.com/item",
        excerpt=None,
        captured_at=datetime.now(UTC),
        market=market,
        locale="en-US",
        evidence_grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        source_cluster_key=cluster,
        source_cluster_basis="url" if cluster else "unresolved",
        independent=independent,
    )


def _bundle(*claims: ClaimContractRow, evidences: tuple[EvidenceContractRow, ...]) -> ClaimContractBundle:
    return ClaimContractBundle(claims=claims, evidences=evidences)


def _market(
    *,
    market: str = "US",
    quality: str = "qualified",
    standard: str | None = "do_not_enter",
    quick: str | None = None,
) -> dict[str, object]:
    return {
        "market": market,
        "quality_status": quality,
        "conclusion_standard": standard,
        "conclusion_quick": quick,
    }


def test_do_not_enter_requires_two_independent_clusters() -> None:
    first = _claim(claim_id="c1")
    second = _claim(claim_id="c2")
    bundle = _bundle(
        first,
        second,
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c2", evidence_id="e2", cluster="content:b"),
        ),
    )
    assert market_independent_cluster_count(bundle, "US") == 2
    assert validate_claim_semantics(
        bundle, markets=[_market()], package_type="standard"
    ) == []

    one_cluster = _bundle(
        first,
        second,
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c2", evidence_id="e2", cluster="content:a"),
        ),
    )
    issues = validate_claim_semantics(
        one_cluster, markets=[_market()], package_type="standard"
    )
    assert any("do_not_enter" in issue and "2" in issue for issue in issues)


def test_do_not_enter_requires_qualified_market() -> None:
    bundle = _bundle(
        _claim(claim_id="c1"),
        _claim(claim_id="c2"),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c2", evidence_id="e2", cluster="content:b"),
        ),
    )
    issues = validate_claim_semantics(
        bundle,
        markets=[_market(quality="qualified_with_gap")],
        package_type="standard",
    )
    assert any("qualified" in issue for issue in issues)


def test_do_not_enter_does_not_count_hypothesis_or_evidence_gap() -> None:
    bundle = _bundle(
        _claim(claim_id="c1", status=ClaimState.HYPOTHESIS),
        _claim(claim_id="c2", status=ClaimState.EVIDENCE_GAP),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c2", evidence_id="e2", cluster="content:b"),
        ),
    )
    assert market_independent_cluster_count(bundle, "US") == 0
    issues = validate_claim_semantics(
        bundle, markets=[_market()], package_type="standard"
    )
    assert any("do_not_enter" in issue for issue in issues)


def test_confirmed_requires_l4() -> None:
    bundle = _bundle(
        _claim(
            claim_id="c1",
            status=ClaimState.CONFIRMED,
            grade=EvidenceGrade.L3_LIVE_SINGLE,
            independent=2,
        ),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c1", evidence_id="e2", cluster="content:b"),
        ),
    )
    issues = validate_claim_semantics(bundle, package_type="standard")
    assert any("L4" in issue for issue in issues)


def test_confirmed_requires_two_clusters() -> None:
    bundle = _bundle(
        _claim(
            claim_id="c1",
            status=ClaimState.CONFIRMED,
            grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
            independent=1,
        ),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(
                claim_id="c1",
                evidence_id="e2",
                cluster="content:a",
                independent=False,
            ),
        ),
    )
    issues = validate_claim_semantics(bundle, package_type="standard")
    assert any("独立来源少于 2" in issue for issue in issues)
    assert any("独立原始记录簇少于 2" in issue for issue in issues)


def test_quick_cannot_confirmed() -> None:
    bundle = _bundle(
        _claim(
            claim_id="c1",
            status=ClaimState.CONFIRMED,
            grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
            independent=2,
        ),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c1", evidence_id="e2", cluster="content:b"),
        ),
    )
    issues = validate_claim_semantics(bundle, package_type="quick")
    assert any("Quick" in issue and "confirmed" in issue for issue in issues)


def test_quick_cannot_use_standard_conclusion() -> None:
    bundle = _bundle(evidences=())
    issues = validate_claim_semantics(
        bundle,
        markets=[_market(standard="enter", quick="worth_validating")],
        package_type="quick",
    )
    assert any("不得输出 Standard 四态" in issue for issue in issues)


def test_unknown_package_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_claim_semantics(_bundle(evidences=()), package_type="pilot")


def test_assert_claim_semantics_raises_bundle_error() -> None:
    bundle = _bundle(
        _claim(
            claim_id="c1",
            status=ClaimState.CONFIRMED,
            grade=EvidenceGrade.L3_LIVE_SINGLE,
        ),
        evidences=(_evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),),
    )
    with pytest.raises(ClaimBundleNotPublishableError):
        assert_claim_semantics(bundle, package_type="standard")


def test_approved_directional_bundle_passes() -> None:
    bundle = _bundle(
        _claim(claim_id="c1"),
        evidences=(
            _evidence(claim_id="c1", evidence_id="e1", cluster="content:a"),
            _evidence(claim_id="c1", evidence_id="e2", cluster="content:b"),
        ),
    )
    assert MIN_DO_NOT_ENTER_CLUSTERS == 2
    assert validate_claim_semantics(bundle, package_type="standard") == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_semantics.py -q
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.claim_semantics`。

- [ ] **Step 3: 实现语义证据纯函数**

创建 `apps/api/src/data_intelligence_hub/services/claim_semantics.py`：

```python
"""C9 消费的 Claim 语义证据规则。

本模块是纯函数层。它不读库、不联网、不读时钟。
独立原始记录簇来自 C7 `ClaimContractBundle` 的 `source_cluster_key` 与
`independent` 快照；本模块不重新计算簇，也不复制第二张等级表。

已批准规则：
- `do_not_enter` 只允许 `quality_status='qualified'`，且至少 2 个独立原始记录簇。
- `confirmed` 只允许 L4、已审核、独立来源 ≥ 2、独立原始记录簇 ≥ 2。
- Quick 不得出现 `confirmed`，不得输出 Standard 四态。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from data_intelligence_hub.models.claim import ClaimReviewStatus, ClaimState
from data_intelligence_hub.models.workbench import PACKAGE_TYPES
from data_intelligence_hub.services.claims import ClaimContractBundle
from data_intelligence_hub.services.exceptions import ClaimBundleNotPublishableError
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade

MIN_DO_NOT_ENTER_CLUSTERS = 2

_CONCLUSION_SUPPORT_STATES = frozenset(
    {ClaimState.CONFIRMED, ClaimState.DIRECTIONAL}
)


@dataclass(frozen=True, slots=True)
class MarketConclusionRow:
    market: str
    quality_status: str
    conclusion_standard: str | None
    conclusion_quick: str | None


def _market_rows(markets: Sequence[Mapping[str, Any]]) -> list[MarketConclusionRow]:
    rows: list[MarketConclusionRow] = []
    for item in markets:
        market = item.get("market")
        quality_status = item.get("quality_status")
        if not isinstance(market, str) or not isinstance(quality_status, str):
            continue
        standard = item.get("conclusion_standard")
        quick = item.get("conclusion_quick")
        rows.append(
            MarketConclusionRow(
                market=market,
                quality_status=quality_status,
                conclusion_standard=standard if isinstance(standard, str) else None,
                conclusion_quick=quick if isinstance(quick, str) else None,
            )
        )
    return rows


def market_independent_cluster_count(
    bundle: ClaimContractBundle,
    market: str,
) -> int:
    """统计该市场下可支持结论的 Claim 的独立原始记录簇数。"""
    claim_by_id = {claim.claim_id: claim for claim in bundle.claims}
    keys: set[str] = set()
    for evidence in bundle.evidences:
        claim = claim_by_id.get(evidence.claim_id)
        if claim is None or claim.scope.market != market:
            continue
        if claim.claim_status not in _CONCLUSION_SUPPORT_STATES:
            continue
        if not evidence.independent or not evidence.source_cluster_key:
            continue
        keys.add(evidence.source_cluster_key)
    return len(keys)


def _confirmed_cluster_count(
    bundle: ClaimContractBundle,
    claim_id: str,
) -> int:
    return len(
        {
            evidence.source_cluster_key
            for evidence in bundle.evidences
            if evidence.claim_id == claim_id
            and evidence.independent
            and evidence.source_cluster_key
        }
    )


def validate_claim_semantics(
    bundle: ClaimContractBundle,
    *,
    markets: Sequence[Mapping[str, Any]] = (),
    package_type: str = "standard",
) -> list[str]:
    """返回全部语义问题；空列表表示通过。C9 直接消费本函数。"""
    if package_type not in PACKAGE_TYPES:
        raise ValueError(f"未知的 package_type：{package_type!r}")
    issues: list[str] = []
    for market in _market_rows(markets):
        if package_type == "quick" and market.conclusion_standard is not None:
            issues.append(
                f"market {market.market} 是 Quick，不得输出 Standard 四态"
            )
        if market.conclusion_standard == "do_not_enter":
            if market.quality_status != "qualified":
                issues.append(
                    f"market {market.market} 的 do_not_enter 只允许 quality_status=qualified"
                )
            clusters = market_independent_cluster_count(bundle, market.market)
            if clusters < MIN_DO_NOT_ENTER_CLUSTERS:
                issues.append(
                    f"market {market.market} 的 do_not_enter 只有 {clusters} 个独立原始记录簇；"
                    f"至少需要 {MIN_DO_NOT_ENTER_CLUSTERS} 个"
                )
    for claim in bundle.claims:
        if claim.claim_status is not ClaimState.CONFIRMED:
            continue
        if package_type == "quick":
            issues.append(f"claim {claim.claim_id} 是 Quick，不得为 confirmed")
        if claim.evidence_grade is not EvidenceGrade.L4_AUTHORIZED_LIVE:
            issues.append(f"claim {claim.claim_id} 的 confirmed 不是 L4")
        if claim.review_status is not ClaimReviewStatus.APPROVED:
            issues.append(f"claim {claim.claim_id} 的 confirmed 未审核")
        if claim.independent_source_count < 2:
            issues.append(f"claim {claim.claim_id} 的 confirmed 独立来源少于 2")
        if _confirmed_cluster_count(bundle, claim.claim_id) < 2:
            issues.append(
                f"claim {claim.claim_id} 的 confirmed 独立原始记录簇少于 2"
            )
    return issues


def assert_claim_semantics(
    bundle: ClaimContractBundle,
    *,
    markets: Sequence[Mapping[str, Any]] = (),
    package_type: str = "standard",
) -> None:
    issues = validate_claim_semantics(
        bundle,
        markets=markets,
        package_type=package_type,
    )
    if issues:
        raise ClaimBundleNotPublishableError(issues)


__all__ = [
    "MIN_DO_NOT_ENTER_CLUSTERS",
    "MarketConclusionRow",
    "assert_claim_semantics",
    "market_independent_cluster_count",
    "validate_claim_semantics",
]
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_claim_semantics.py -q
```

Expected: `10 passed`。

- [ ] **Step 5: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "validate_claim_semantics" --direction upstream --repo . 2>/dev/null || true
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/claim_semantics.py apps/api/tests/unit/test_claim_semantics.py
git commit -m "feat(claims): 语义证据规则供 c9 消费"
```

新符号首次出现时 `impact` 可能返回 UNKNOWN；用 `git grep -n "validate_claim_semantics\|market_independent_cluster_count" apps/api/src apps/api/tests` 确认尚未接线，再继续。C9 计划必须新增消费步骤，见文末“C9 语义消费”。

---

### Task 8: 只读 Claim API

**Files:**
- Create: `apps/api/src/data_intelligence_hub/schemas/claim.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/claims.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py:208-224`
- Test: `apps/api/tests/integration/test_claims_api.py`

**Interfaces:**
- Consumes: Task 5/7 的仓储与服务；C2 `get_authenticated_context`、`require_project_access`、`get_settings().workspace_rbac_enforced`。
- Produces: `GET /api/claims`（`project_id` 必填）、`GET /api/claims/{claim_id}`（含 evidence 段），两者全部走项目 ACL。

- [ ] **Step 1: 写失败测试**

```python
"""C7：只读 Claim API。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_member import ProjectMember
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.claims import (
    create_claim_with_evidence,
    review_claim,
    submit_claim_for_review,
)
from data_intelligence_hub.services.reviewer_assignments import (
    REVIEWER_SCOPE_REVIEW,
    grant_reviewer_assignment,
)


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[object, None]:
        async with factory() as session:
            yield session

    settings = get_settings()
    original_rbac = settings.workspace_rbac_enforced
    settings.workspace_rbac_enforced = True
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            async_client.session_factory = factory  # type: ignore[attr-defined]
            yield async_client
    finally:
        app.dependency_overrides.clear()
        settings.workspace_rbac_enforced = original_rbac
        await engine.dispose()


async def _seed(client: AsyncClient) -> dict[str, object]:
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        owner = User(
            email=f"api-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Owner",
        )
        reviewer = User(
            email=f"api-reviewer-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Reviewer",
        )
        session.add_all([owner, reviewer])
        await session.flush()
        workspace = Workspace(
            name="API",
            slug=f"api-{uuid.uuid4().hex}",
            owner_id=owner.id,
        )
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner")
        )
        project = Project(
            workspace_id=workspace.id,
            name="API",
            domain="mother_baby",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()
        item = IntelligenceItem(
            workspace_id=workspace.id,
            project_id=project.id,
            title="Item",
            summary="Summary",
            intelligence_type="signal",
            impact_score=0.5,
            confidence_score=0.5,
            novelty_score=0.5,
            urgency_score=0.5,
            final_score=0.5,
            generated_by="system",
            domain="mother_baby",
        )
        session.add(item)
        await session.flush()
        evidence = Evidence(
            intelligence_id=item.id,
            workspace_id=workspace.id,
            project_id=project.id,
            evidence_type="web",
            title="Support",
            url="https://example.com/a",
            evidence_grade="L3_live_single",
            market="US",
            locale="en-US",
            source_tool_id="tikhub.products",
            provider_id="tikhub",
            captured_at=datetime.now(UTC),
            source_cluster_key="url:https://example.com/a",
            source_cluster_basis="url",
        )
        counter = Evidence(
            intelligence_id=item.id,
            workspace_id=workspace.id,
            project_id=project.id,
            evidence_type="web",
            title="Counter",
            url="https://example.com/b",
            evidence_grade="L3_live_single",
            market="US",
            locale="en-US",
            source_tool_id="tikhub.products",
            provider_id="tikhub",
            captured_at=datetime.now(UTC),
            source_cluster_key="url:https://example.com/b",
            source_cluster_basis="url",
        )
        session.add_all([evidence, counter])
        await session.flush()
        claim = await create_claim_with_evidence(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
            claim_text="美国市场母婴新品有需求",
            text_en="US demand exists for the new baby product",
            owner=owner.id,
            scope_market="US",
            scope_window_start=date(2026, 1, 1),
            scope_window_end=date(2026, 3, 1),
            scope_window_days=60,
            scope_sample_n=120,
            counterevidence_text="未发现反证",
            evidence=[(evidence.id, "support"), (counter.id, "counter")],
            evidence_grade="L3_live_single",
            state="directional",
        )
        await grant_reviewer_assignment(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
            user_id=reviewer.id,
            assignment_scope=REVIEWER_SCOPE_REVIEW,
            assigned_by=owner.id,
        )
        await submit_claim_for_review(
            session,
            workspace_id=workspace.id,
            claim_id=claim.id,
            actor_id=owner.id,
        )
        await review_claim(
            session,
            workspace_id=workspace.id,
            claim_id=claim.id,
            reviewer_id=reviewer.id,
            decision="approved",
            note="通过",
        )
        await session.commit()
        client.cookies.set("access_token", create_access_token(owner.id))
        return {
            "workspace_id": workspace.id,
            "owner_id": owner.id,
            "project_id": project.id,
            "claim_id": claim.id,
        }


async def _add_workspace_user(
    client: AsyncClient,
    *,
    workspace_id: uuid.UUID,
    role: str,
    project_ids: tuple[uuid.UUID, ...] = (),
) -> str:
    """创建客户工作区成员，可选授予项目可见性。返回访问 token。"""
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        user = User(
            email=f"acl-{role}-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name=role.title(),
        )
        session.add(user)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user.id,
                role=role,
            )
        )
        for project_id in project_ids:
            session.add(
                ProjectMember(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    user_id=user.id,
                    created_by_user_id=user.id,
                )
            )
        await session.commit()
        return create_access_token(user.id)


@pytest.mark.anyio
async def test_list_claims_returns_governance_fields(client: AsyncClient) -> None:
    seeded = await _seed(client)
    response = await client.get(
        "/api/claims", params={"project_id": str(seeded["project_id"])}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["review_status"] == "approved"
    assert body[0]["independent_source_count"] == 2
    assert body[0]["scope_market"] == "US"
    assert "risk_flags" in body[0]


@pytest.mark.anyio
async def test_claim_detail_returns_links_and_evidence(client: AsyncClient) -> None:
    seeded = await _seed(client)
    response = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["claim"]["review_status"] == "approved"
    assert len(body["claim_evidence"]) == 2
    assert {item["role"] for item in body["claim_evidence"]} == {"support", "counter"}
    assert len(body["evidences"]) == 2


@pytest.mark.anyio
async def test_cross_workspace_claim_is_404(client: AsyncClient) -> None:
    seeded = await _seed(client)
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        other_owner = User(
            email=f"other-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Other",
        )
        session.add(other_owner)
        await session.flush()
        other = Workspace(
            name="Other",
            slug=f"other-{uuid.uuid4().hex}",
            owner_id=other_owner.id,
        )
        session.add(other)
        await session.flush()
        session.add(
            WorkspaceMember(workspace_id=other.id, user_id=other_owner.id, role="owner")
        )
        await session.commit()
        other_token = create_access_token(other_owner.id)
    client.cookies.set("access_token", other_token)
    response = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_review_status_filter(client: AsyncClient) -> None:
    seeded = await _seed(client)
    approved = await client.get(
        "/api/claims",
        params={"project_id": str(seeded["project_id"]), "review_status": "approved"},
    )
    rejected = await client.get(
        "/api/claims",
        params={"project_id": str(seeded["project_id"]), "review_status": "rejected"},
    )
    assert len(approved.json()) == 1
    assert rejected.json() == []


@pytest.mark.anyio
async def test_list_claims_requires_project_id(client: AsyncClient) -> None:
    await _seed(client)
    response = await client.get("/api/claims")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_member_without_project_access_is_403(client: AsyncClient) -> None:
    seeded = await _seed(client)
    token = await _add_workspace_user(
        client, workspace_id=seeded["workspace_id"], role="member"
    )
    client.cookies.set("access_token", token)
    listed = await client.get(
        "/api/claims", params={"project_id": str(seeded["project_id"])}
    )
    detail = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "project_access_forbidden"
    assert detail.status_code == 403
    assert detail.json()["error"]["code"] == "project_access_forbidden"
    assert "evidences" not in detail.json()


@pytest.mark.anyio
async def test_member_with_project_access_can_read(client: AsyncClient) -> None:
    seeded = await _seed(client)
    token = await _add_workspace_user(
        client,
        workspace_id=seeded["workspace_id"],
        role="member",
        project_ids=(seeded["project_id"],),
    )
    client.cookies.set("access_token", token)
    listed = await client.get(
        "/api/claims", params={"project_id": str(seeded["project_id"])}
    )
    detail = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert detail.status_code == 200
    assert len(detail.json()["evidences"]) == 2


@pytest.mark.anyio
async def test_same_workspace_cross_project_is_403(client: AsyncClient) -> None:
    seeded = await _seed(client)
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        other_project = Project(
            workspace_id=seeded["workspace_id"],
            name="Other Project",
            domain="mother_baby",
            owner_id=seeded["owner_id"],
        )
        session.add(other_project)
        await session.commit()
        other_project_id = other_project.id
    token = await _add_workspace_user(
        client,
        workspace_id=seeded["workspace_id"],
        role="member",
        project_ids=(other_project_id,),
    )
    client.cookies.set("access_token", token)
    listed = await client.get(
        "/api/claims", params={"project_id": str(seeded["project_id"])}
    )
    other_listed = await client.get(
        "/api/claims", params={"project_id": str(other_project_id)}
    )
    detail = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert listed.status_code == 403
    assert listed.json()["error"]["code"] == "project_access_forbidden"
    assert other_listed.status_code == 200
    assert other_listed.json() == []
    assert detail.status_code == 403
    assert detail.json()["error"]["code"] == "project_access_forbidden"
    assert "evidences" not in detail.json()


@pytest.mark.anyio
async def test_admin_can_read_all_projects(client: AsyncClient) -> None:
    seeded = await _seed(client)
    token = await _add_workspace_user(
        client, workspace_id=seeded["workspace_id"], role="admin"
    )
    client.cookies.set("access_token", token)
    listed = await client.get(
        "/api/claims", params={"project_id": str(seeded["project_id"])}
    )
    detail = await client.get(f"/api/claims/{seeded['claim_id']}")
    assert listed.status_code == 200
    assert detail.status_code == 200
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/integration/test_claims_api.py -q
```

Expected: FAIL，`404 Not Found`，`/api/claims` 未挂载。

- [ ] **Step 3: 实现 schema 与路由**

创建 `apps/api/src/data_intelligence_hub/schemas/claim.py`：

```python
"""只读 Claim API 的响应模型。字段与契约 v1.1 对齐。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.intelligence import Evidence


class ClaimResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    run_id: uuid.UUID | None
    claim_text: str
    text_en: str | None
    state: str
    evidence_grade: str | None
    confidence: float | None
    owner: uuid.UUID | None
    scope_market: str | None
    scope_window_start: date | None
    scope_window_end: date | None
    scope_window_days: int | None
    scope_sample_n: int | None
    counterevidence_text: str | None
    risk_flags: list[str]
    review_status: str
    review_note: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    reviewed_content_version: int | None
    reviewed_payload_sha256: str | None
    reviewed_profile: str | None
    second_reviewed_by: uuid.UUID | None
    second_reviewed_at: datetime | None
    content_version: int
    independent_source_count: int
    blocked_reason: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, claim: Claim) -> ClaimResponse:
        return cls(
            id=claim.id,
            workspace_id=claim.workspace_id,
            project_id=claim.project_id,
            run_id=claim.run_id,
            claim_text=claim.claim_text,
            text_en=claim.text_en,
            state=claim.state,
            evidence_grade=claim.evidence_grade,
            confidence=claim.confidence,
            owner=claim.owner,
            scope_market=claim.scope_market,
            scope_window_start=claim.scope_window_start,
            scope_window_end=claim.scope_window_end,
            scope_window_days=claim.scope_window_days,
            scope_sample_n=claim.scope_sample_n,
            counterevidence_text=claim.counterevidence_text,
            risk_flags=list(claim.risk_flags),
            review_status=claim.review_status,
            review_note=claim.review_note,
            reviewed_by=claim.reviewed_by,
            reviewed_at=claim.reviewed_at,
            reviewed_content_version=claim.reviewed_content_version,
            reviewed_payload_sha256=claim.reviewed_payload_sha256,
            reviewed_profile=claim.reviewed_profile,
            second_reviewed_by=claim.second_reviewed_by,
            second_reviewed_at=claim.second_reviewed_at,
            content_version=claim.content_version,
            independent_source_count=claim.independent_source_count,
            blocked_reason=claim.blocked_reason,
            created_at=claim.created_at,
        )


class ClaimEvidenceResponse(BaseModel):
    evidence_id: uuid.UUID
    role: str
    evidence_grade: str | None
    source_cluster_key: str | None
    source_cluster_basis: str | None
    independent: bool

    @classmethod
    def from_model(cls, link: ClaimEvidence) -> ClaimEvidenceResponse:
        return cls(
            evidence_id=link.evidence_id,
            role=link.role,
            evidence_grade=link.evidence_grade,
            source_cluster_key=link.source_cluster_key,
            source_cluster_basis=link.source_cluster_basis,
            independent=link.independent,
        )


class ClaimEvidenceRowResponse(BaseModel):
    evidence_id: uuid.UUID
    title: str
    url: str | None
    excerpt: str | None
    market: str | None
    locale: str | None
    source_tool_id: str | None
    captured_at: datetime | None
    evidence_grade: str | None

    @classmethod
    def from_model(cls, evidence: Evidence) -> ClaimEvidenceRowResponse:
        return cls(
            evidence_id=evidence.id,
            title=evidence.title,
            url=evidence.url,
            excerpt=evidence.excerpt,
            market=evidence.market,
            locale=evidence.locale,
            source_tool_id=evidence.source_tool_id,
            captured_at=evidence.captured_at,
            evidence_grade=evidence.evidence_grade,
        )


class ClaimDetailResponse(BaseModel):
    claim: ClaimResponse
    claim_evidence: list[ClaimEvidenceResponse]
    evidences: list[ClaimEvidenceRowResponse]


__all__ = [
    "ClaimDetailResponse",
    "ClaimEvidenceResponse",
    "ClaimEvidenceRowResponse",
    "ClaimResponse",
]
```

创建 `apps/api/src/data_intelligence_hub/api/routes/claims.py`：

```python
"""只读 Claim API。冻结路径见契约 §3.1。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.api.deps import (
    AuthContext,
    SessionDep,
    get_authenticated_context,
)
from data_intelligence_hub.models.claim import ClaimReviewStatus, ClaimState
from data_intelligence_hub.repositories.claims import (
    get_claim,
    list_claims,
    list_evidence,
    load_evidence_rows,
)
from data_intelligence_hub.schemas.claim import (
    ClaimDetailResponse,
    ClaimEvidenceResponse,
    ClaimEvidenceRowResponse,
    ClaimResponse,
)

router = APIRouter(tags=["claims"])


@router.get("", response_model=list[ClaimResponse])
async def list_claim_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    project_id: Annotated[uuid.UUID, Query()],
    run_id: Annotated[uuid.UUID | None, Query()] = None,
    state: Annotated[ClaimState | None, Query()] = None,
    review_status: Annotated[ClaimReviewStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ClaimResponse]:
    access = await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project_id,
    )
    claims = await list_claims(
        session,
        workspace_id=context.workspace.id,
        project_id=access.project.id,
        run_id=run_id,
        state=state,
        review_status=review_status,
    )
    return [ClaimResponse.from_model(claim) for claim in claims[:limit]]


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
async def get_claim_item(
    claim_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ClaimDetailResponse:
    claim = await get_claim(
        session,
        workspace_id=context.workspace.id,
        claim_id=claim_id,
    )
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=claim.project_id,
    )
    links = await list_evidence(session, claim_id=claim.id)
    evidence_rows = await load_evidence_rows(
        session,
        workspace_id=claim.workspace_id,
        project_id=claim.project_id,
        evidence_ids=[link.evidence_id for link in links],
    )
    return ClaimDetailResponse(
        claim=ClaimResponse.from_model(claim),
        claim_evidence=[ClaimEvidenceResponse.from_model(link) for link in links],
        evidences=[ClaimEvidenceRowResponse.from_model(row) for row in evidence_rows],
    )
```

`repositories/claims.py` 的 `list_claims` 增加 `state` 与 `review_status` 过滤：

```python
async def list_claims(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    state: ClaimState | str | None = None,
    review_status: ClaimReviewStatus | str | None = None,
) -> list[Claim]:
    statement = select(Claim).where(Claim.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Claim.project_id == project_id)
    if run_id is not None:
        statement = statement.where(Claim.run_id == run_id)
    if state is not None:
        statement = statement.where(Claim.state == _claim_state(state))
    if review_status is not None:
        statement = statement.where(
            Claim.review_status == ClaimReviewStatus(review_status).value
        )
    result = await session.execute(
        statement.order_by(Claim.created_at.desc(), Claim.id)
    )
    return list(result.scalars().all())
```

`main.py` 在 reports 路由之后插入：

```python
from data_intelligence_hub.api.routes.claims import router as claims_router

# 在 create_app 内，reports_router 之后：
    app.include_router(claims_router, prefix="/api/claims")
```

- [ ] **Step 4: 运行 API 测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/integration/test_claims_api.py -q
```

Expected: `9 passed`。

- [ ] **Step 5: GitNexus 检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs impact "list_claims" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_app" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/schemas/claim.py apps/api/src/data_intelligence_hub/api/routes/claims.py apps/api/src/data_intelligence_hub/main.py apps/api/src/data_intelligence_hub/repositories/claims.py apps/api/tests/integration/test_claims_api.py
git commit -m "feat(claims): 只读主张接口"
```

`impact` 报 `HIGH`/`CRITICAL` 时停止。

---

### Task 9: C14 交接夹具、全量回归与提交

**Files:**
- Create: `apps/api/tests/unit/test_c14_claim_handoff.py`
- Modify: `apps/api/tests/unit/test_claims.py`（如 Task 5 已改完，只补一条全量断言）

**Interfaces:**
- Consumes: Task 7 的 `ClaimContractBundle`、Task 8 的 API。
- Produces: C14 可直接使用的 13 个字段与浏览器断言清单。

- [ ] **Step 1: 写交接测试**

```python
"""C7 → C14 交接：合同行必须带齐报告页要显示的字段。"""

from __future__ import annotations

from dataclasses import fields

from data_intelligence_hub.services.claims import (
    ClaimContractRow,
    ClaimScopeRow,
    EvidenceContractRow,
)

C14_FIELDS = {
    "claim_id",
    "text",
    "text_en",
    "claim_status",
    "evidence_grade",
    "scope",
    "counterevidence_text",
    "owner",
    "evidence_ids",
    "risk_flags",
    "review_status",
    "independent_source_count",
    "blocked_reason",
}


def test_claim_contract_row_has_every_c14_field() -> None:
    names = {field.name for field in fields(ClaimContractRow)}
    assert C14_FIELDS <= names


def test_claim_scope_and_evidence_rows_have_c14_fields() -> None:
    assert {field.name for field in fields(ClaimScopeRow)} == {
        "market",
        "window_start",
        "window_end",
        "window_days",
        "sample_n",
    }
    assert {
        "evidence_id",
        "claim_id",
        "role",
        "source_tool_id",
        "url",
        "captured_at",
        "market",
        "locale",
        "evidence_grade",
    } <= {field.name for field in fields(EvidenceContractRow)}
```

- [ ] **Step 2: 运行交接测试并跑全量回归**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run pytest tests/unit/test_c14_claim_handoff.py tests/unit/test_claims.py tests/unit/test_source_clusters.py tests/unit/test_claim_evidence_policy.py tests/unit/test_claim_evidence_schema.py tests/unit/test_claim_creation_governance.py tests/unit/test_claim_review.py tests/unit/test_claim_contract_rows.py tests/unit/test_claim_semantics.py tests/integration/test_claims_api.py tests/postgres/test_claim_evidence_migration.py -q
```

Expected: 全部通过，`failed=0`。

- [ ] **Step 3: 运行质量门**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run ruff check src tests
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run mypy src
cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run alembic heads
```

Expected:

- Ruff：`All checks passed!`
- mypy：`Success: no issues found`
- Alembic：`202610220063 (head)`（只有一行）

- [ ] **Step 4: GitNexus 全量变更检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 退出码 0；输出不含 `partial: true`，不含 `truncated: true`。若出现，重跑；仍出现时停止提交并记录未覆盖符号。

- [ ] **Step 5: 完整性检查并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c7
python3 scripts/check_file_integrity.py --staged
git add apps/api/tests/unit/test_c14_claim_handoff.py
git commit -m "test(claims): C14 交接字段与全量回归"
```

`check_file_integrity.py --staged` 必须在 `git add` 之后运行；输出 `file integrity OK` 才提交。

---

## C14 浏览器交接

C7 不修改报告页。C14 必须在以下事实成立后开始浏览器验收：

- `GET /api/claims?project_id=<uuid>` 返回 200，且每条 claim 含 `text_en`、`risk_flags`、`review_status`、`independent_source_count`、`blocked_reason`、`scope_market`。
- `GET /api/claims/<claim_id>` 返回 `claim`、`claim_evidence`、`evidences` 三段。
- 同工作区 `member` 未被授予该项目时，列表与详情都返回 403 `project_access_forbidden`；跨工作区返回 404；详情 403 响应不含 `evidences`。
- `load_publishable_claim_rows()` 返回的 `ClaimContractRow` 已含 C14 需要的 13 个字段。
- 报告合同 `SCHEMA_VERSION` 为 `1.1.0`，`claims[]` 含 5 个新字段。

C14 浏览器验收步骤：

1. 启动 API：`cd /Users/lute/Project/data_scrapy-gov-c7/apps/api && uv run uvicorn data_intelligence_hub.main:app --reload --port 8000`。
2. 启动控制台：`cd apps/scraper-console && pnpm dev`。
3. 打开 `/reports`，进入一份由 C7 数据构建的报告产物页 `/reports/<artifactId>`。
4. 断言首屏显示：最低证据等级、五个 claim 状态分布、各市场质量状态。缺失时显示原因，不显示数值 0。
5. 滚动到 `aria-labelledby="claims-heading"` 的“结论与证据”区块。
6. 断言每条 claim 显示：中文文本、英文文本、`claim_status` 徽章、`evidence_grade` 徽章、`risk_flags` 徽章、`review_status`、`independent_source_count`、`scope_market` 与时间窗。
7. 断言 `blocked` claim 显示 `blocked_reason`；`evidence_gap` claim 显示缺口说明。
8. 断言 `single_source` 风险标记在独立来源 < 2 时出现，且 `confirmed` 不会出现在 L3 或单源 claim 上。
9. 打开浏览器网络面板，确认 `GET /api/claims` 与报告合同请求均返回 200；同工作区跨项目列表/详情返回 403 `project_access_forbidden` 且详情体不含 `evidences`；跨工作区请求返回 404。
10. 截图归档到 C14 的验收记录；C14 不得修改 C7 的迁移 063、模型或服务。

C14 必须新增的前端类型字段（`apps/scraper-console/src/lib/api/reports.ts` 的 `ClaimView`）：

```text
text_en: string
risk_flags: string[]
review_status: "draft" | "pending" | "approved" | "rejected" | "stale"
independent_source_count: number
blocked_reason: "rights" | "permission" | "configuration" | "gate" | "upstream" | null
```

C14 不得把 `reviewed_payload_sha256`、`reviewed_profile`、`source_cluster_key`、`source_cluster_basis`、`independent` 渲染到客户页面。它们只用于内部审核和独立来源判定。

**发布交接。** C7 不直接部署任何环境，不执行生产发布、A/B 切换或回滚。A、B 两套生产的发布、切换与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；C7 只交付迁移 063、测试证据与上述交接清单。PG0 发布批次先备份，A 先 canary，B 在目标授权、备份校验与迁移门禁通过后发布。

## C9 语义消费

C7 提供 `services/claim_semantics.py`，C9 必须在报告装配与发布前消费，不得把语义检查留到客户页面或 C14：

- 在 `create_draft_artifact` 写入 `report_artifacts` 前，C9 用 C7 的 `ClaimContractBundle`（来自 `load_publishable_claim_rows(session, workspace_id=..., project_id=task.project_id, task_id=contract["task_id"])`，含内部 `source_cluster_key`/`independent`）调用：

```python
issues = validate_claim_semantics(
    bundle,
    markets=contract["markets"],
    package_type=task.package_type,
)
```

- `issues` 非空时，C9 必须把问题并入 `report_publish_gate_blocked` 或 `claim_bundle_not_publishable`，不得发布，也不得把 `do_not_enter` 降级成 `conditional_enter` 绕过。
- 在 `publish_artifact` 前，C9 必须重新调用 `assert_claim_semantics(...)`；`contract_json` 已序列化时，C9 仍要用内部 bundle 校验，不得只用公开的 `claims[].independent_source_count` 推断独立簇。
- 规则固定为：`do_not_enter` 需要 `quality_status='qualified'` 且至少 2 个独立原始记录簇；`confirmed` 仍需 L4、`review_status='approved'`、独立来源 ≥ 2 且独立簇 ≥ 2；Quick 不得出现 `confirmed`，不得输出 Standard 四态。
- C9 计划必须新增上述调用与失败测试；C7 不修改 C9 文件。C9 若无法拿到 `ClaimContractBundle`，先修订 C9 计划并保持本清单的接口名，不得复制第二套簇推导。

## Definition of Done

- [ ] C1 registry 为 v1.1，登记 C7 需要的全部新列、枚举、约束名、`report_reviewer_assignments` 与 `assignment_scope`、Claim 错误码及 `claims.list`/`claims.detail` 的 ACL 错误码；C7 未修改契约文档或 registry；Task 1 缺项时停止并返回 C1。
- [ ] C1 导出 `CANONICAL_PROFILE_ID`，`SCHEMA_VERSION == "1.1.0"`，`canonical_json_bytes` 是唯一规范化入口。
- [ ] 迁移只有 `202610220063_claim_evidence_completeness.py`，`down_revision='202610220062'`，`alembic heads` 单头 `202610220063`。
- [ ] PostgreSQL 迁移测试 `062→063→062→head` 通过，且 `alembic heads` 只有一行。
- [ ] `claims`、`claim_evidence`、`evidences` 新列与 CHECK 名和模型逐字一致。
- [ ] L0/L1 创建 Claim 被拒；L2→hypothesis、L3→directional、L4→confirmed 上限生效。
- [ ] `confirmed` 创建入口被拒，只能经审核晋升；晋升要求 L4、独立来源 ≥ 2、审核通过。
- [ ] 独立来源按原始记录簇计；同簇只算 1；无法解析不算独立。
- [ ] `single_source` 在独立来源 < 2 时自动加入。
- [ ] 11 个正式市场固定；非正式市场被拒；时间窗含首尾天数校验生效。
- [ ] `blocked` 必须有 `blocked_reason`；其他状态不得带原因。
- [ ] Claim 审核只接受 active `report_reviewer_assignments` 且范围 `report_review`；客户 `owner/admin/member` 一律拒绝；`report_read` 只能读不能审；审核人不得是 Claim owner、任务 owner 或请求人；第二审核人同样 active 且不重复。
- [ ] `submit`/`approve`/`reject`/`override`/`block`/`unblock`/`revise` 都在同一事务追加 C2 `audit_events`，动作名固定；审计失败整单回滚。
- [ ] 审核后修订置 `stale`，清空第一/第二签字与签名哈希，`content_version` 递增。
- [ ] `load_publishable_claim_rows()` 只返回 approved 且内容版本一致的 claim；`task_id` 为空时保持工作区/项目过滤，非空时沿 `Claim.run_id -> Run.workflow_version_id -> WorkflowVersion.workbench_task_id` 过滤，C10/C13 省略 `task_id` 的调用不受影响；缺 `text_en`、owner、scope、反证文本、证据 URL/market/locale/source_tool_id/grade 时 `validate_claim_bundle()` 报问题。
- [ ] `validate_claim_semantics()` 对 `do_not_enter` 要求 qualified 且 ≥ 2 个独立原始记录簇；`confirmed` 要求 L4、approved、独立来源 ≥ 2 且独立簇 ≥ 2；Quick 不得 `confirmed`、不得输出 Standard 四态；C9 消费该 helper。
- [ ] `GET /api/claims` 的 `project_id` 必填，且与 `GET /api/claims/{claim_id}`（含 `evidences` 段）都调用 `require_project_access`；同工作区跨项目 403 `project_access_forbidden`，跨工作区 404，403 响应不含证据。
- [ ] 没有 `modules/evidence/`、第二套 evidence 服务或第二张等级上限表。
- [ ] `uv run pytest` 目标测试 `failed=0`；`uv run ruff check src tests` 通过；`uv run mypy src` 通过。
- [ ] 每个提交前 `detect-changes --scope all` 无 `partial`/`truncated`；`impact` 的 HIGH/CRITICAL 已处理。
- [ ] C14 拿到 13 个交接字段与浏览器验收清单；C9 拿到语义 helper 消费清单。
- [ ] 未直接部署；A、B 两套生产的发布、切换与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收，C7 只交付迁移 063、测试证据与交接清单。

## Self-Review

**Spec coverage**

- 设计 5.3 证据等级：Task 3、Task 5、Task 7。
- 设计 5.4 独立来源簇：Task 2、Task 5、Task 7。
- 设计 5.5 Claim 字段与五状态：Task 1、Task 4、Task 5、Task 7。
- 设计 5.2 逐市场状态与 `missing`/`blocked` 语义：Task 3、Task 7（scope 与 block reason）。
- 设计 6.3 人工审核与第二人复核：Task 6；审核人只认 C1/C2 内部指派，不认客户 `owner/admin/member`，并排除 Claim owner、任务 owner 与请求人。
- 设计 6.1 不可变报告合同：Task 7 提供合同行；Task 7B 提供 C9 语义门禁；C14 负责合同 API 与页面。
- 设计 0.5 契约优先：Task 1 只读 C1 registry 做守卫，缺项返回 C1；canonical profile 固定为 C1 的 `dih-canonical-json-v1`，严格 RFC 8785 延期并使用不同 ID。
- 设计 7.8 审计：Task 6 的 `review_history` 行内追加 + C2 `audit_events` 统一审计；正式报告审核事件仍由 `report_audit_events` 承担，C7 不建独立审核表。
- 设计 5.2 Quick/Standard 结论：Task 7B 的 `do_not_enter` 与 Quick 规则，C9 消费。
- C2 项目 ACL：Task 8 的 `require_project_access` 与同工作区跨项目 403 负例。
- GitNexus 强制：每个任务末尾的 `impact` / `detect-changes` 步骤。
- C14 交接：文末清单；C9 语义消费：文末清单。

**Placeholder scan**

已检查：占位符扫描已通过。每个代码步骤给出可粘贴的完整函数或完整测试。

**Type consistency**

- `ClaimState`、`ClaimReviewStatus`、`ClaimRiskFlag`、`ClaimBlockedReason` 在 Task 4 定义，Task 3/5/6/7/7B 使用同名。
- `SourceCluster`、`LinkCluster`、`ClusterBasis` 在 Task 2 定义，Task 5 使用。
- `ClaimTaskPrincipals`、`get_claim_task_principals()` 在 Task 5 的仓储代码定义，Task 6 使用。
- `ReviewerAssignment`、`REVIEWER_SCOPE_READ`、`REVIEWER_SCOPE_REVIEW`、`get_active_reviewer_assignment()`、`grant_reviewer_assignment()` 由 C2 提供，Task 0 检查，Task 6/8 测试使用；C7 不定义副本。
- `ClaimContractRow`、`EvidenceContractRow`、`ClaimContractBundle`、`load_publishable_claim_rows(session, *, workspace_id, project_id, task_id=None)` 在 Task 7 定义，Task 7B/9 测试使用；C9 传 `task_id`，C10/C13 省略。
- `MarketConclusionRow`、`validate_claim_semantics()`、`assert_claim_semantics()`、`market_independent_cluster_count()` 在 Task 7B 定义，C9 消费。
- `ClaimResponse`、`ClaimEvidenceResponse`、`ClaimEvidenceRowResponse`、`ClaimDetailResponse` 在 Task 8 定义，集成测试使用。
- 迁移 CHECK 名与模型 `conv()` 名逐字一致；Task 4 的测试同时断言两侧。
