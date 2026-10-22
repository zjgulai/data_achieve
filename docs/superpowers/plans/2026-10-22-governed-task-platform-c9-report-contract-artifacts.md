# C9 受治理报告合同与产物发布实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 B5 报告合同基线上补齐“草稿 → 人工审核 → 发布 → 修订取代”的受治理报告产物链，让 `report_artifacts.contract_json` 成为报告内容的唯一事实源，并向 C14 提供报告页复核交接。

**Architecture:** 复用 B5 的 `report_contract`、`report_builder`、`report_renderers`、`report_templates`、`report_artifacts`，不新建第二套报告或 claim 实现；两个控制台页面由 PG0 发布批次修改。新增一个发布生命周期服务与一条迁移 065：草稿可审核，审核签字绑定 `contract_sha256`，发布后合同与两页 HTML 不可改，修订通过 `supersedes_id` 指向旧版本，旧版本在同一事务内转为 `superseded`。装配器消费 C7 的已审核 Claim 与 C8 的结论语义，并生成 Quick 2 小时方向稿；发布前消费 C11 导出策略的 PII 扫描。所有读取路径只返回或渲染 `contract_json`，不重新查 claim/evidence，也不调用模型。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、PostgreSQL、pytest、ruff、mypy。控制台与 Playwright 由 C14 负责。

## Global Constraints

- **开关与回滚。** 本切片不新增布尔开关，入口受 `GOVERNED_TASK_PLATFORM_ENABLED` 控制；回滚点是迁移 `065` 的 `downgrade` 与发布前数据库备份，生产回滚用备份恢复或新迁移，不手改 `alembic_version`。
- **前置分支不可分叉。** 执行前必须从 C8 前置分支 `feat/gov-c8` 创建独立 worktree：`git worktree add /Users/lute/Project/data_scrapy-gov-c9 -b feat/gov-c9 feat/gov-c8`。`git merge-base --is-ancestor feat/gov-c8 HEAD` 必须成功，Alembic head 必须是 `202610220064`。不得在 `feat/b5-workbench` 或 `main` 上直接开发，也不得在 worktree 内合并 C1–C8。不得复制或重写 `schemas/report_contract.py`、`schemas/report_contract.schema.json`、`services/report_builder.py`、`services/report_renderers.py`、`services/report_templates.py`、`services/report_artifacts.py`。claim 基线是 B5 的 `claims` 与 `claim_evidence`，不另建主张表或第二套枚举。
- **C7/C8 是前置。** C7 提供 claim 与 evidence；C8 提供质量、缺口与门禁事实。C4/C5/C6 的事实已通过 `feat/gov-c8` 分支进入基线。C9 只消费装配完成的 `report_contract`，不直接查询 claim/evidence 表，不重新计算证据等级。前置迁移 058–064 必须已存在，C9 的迁移固定为 `202610220065`，`down_revision` 固定为 `202610220064`。
- **canonical profile 由 C1 冻结。** C1 必须在 `schemas/report_contract.py` 导出 `CANONICAL_PROFILE_ID: Final[str] = "dih-canonical-json-v1"` 与 `SCHEMA_VERSION: Final[str] = "1.1.0"`。`dih-canonical-json-v1` 绑定 B5 现有 `canonical_json_bytes` 的近似 RFC 8785 行为；严格 RFC 8785 升级延期，未来若实施必须使用不同 ID `dih-canonical-json-rfc8785-v1`，不得改变 v1 的字节输出。C9 只 import 这两个常量与 `canonical_json_bytes`，不另写哈希实现，也不定义本地 profile。
- **契约只读。** C1 的 `configs/contracts/v1.1.0/registry.json` 是唯一机器契约，`docs/design/【契约冻结】v1-表名-枚举-接口.md` 是唯一权威。C9 只读 C1 已登记的 `ck_report_artifacts_status`、`uq_report_artifacts_current_published`、`report_reviewer_assignments`、`reviewer_role`、`reviewer_assignment_required`、`reviewer_self_review_forbidden`、`report_quality_not_ready`、`report_forbidden_language`、`dih-descriptive-language-v1` 与报告合同 1.1 schema；不修改契约文档、不修改 registry、不追加实现决定。Task 1 缺任一登记项时停止并返回 C1 补充登记。契约文档与 `registry.json` 不在本切片的修改清单和提交范围内。未登记的表名、列名、路径、错误码不得实现。
- **报告构建前质量门禁。** C9 不计算质量、不写 `market_assessments` / `data_gaps`。`assemble_report_contract_v1_1` 与 `create_draft_artifact` 在写入 `report_artifacts` 前，若 `run_id` 非空，必须调用 C8 的 `services.market_quality.ensure_market_quality(session, run_id=run_id, task_id=contract["task_id"])`。顶层 `task_id` 是唯一权威；`identity.task_id` 只是 B5 兼容镜像，必须与顶层相等，C9 不读它做业务判断。质量不可用（run 未 completed、workbench task 缺失、市场不属于任务单）时抛 `ReportQualityNotReadyError`，对外错误码 `report_quality_not_ready`。`run_id` 为空的历史/手工报告跳过该门禁，质量字段保持 null；`run.workflow_version_id` 为空的 legacy run 同样跳过，报告质量字段保持 null，不得伪造成有质量。C9 不 import C8 的 `compute_market_assessment`，不重新计算阈值、样本数或独立来源。
- **C9 拥有 1.1 装配器与不可变生命周期。** `services/report_contract_v1_1.py` 的 `assemble_report_contract_v1_1` 从 C8 的 `market_assessments`、`data_gaps`、`dataset_versions` 读取事实，写出全部 29 个顶层键，并写入合法占位 `review` / `acceptance` / `delivery` 组。审核通过由 `create_reviewed_contract_version` 创建 `report_version + 1` 的新产物；交付由 C10 调用 `create_delivery_contract_version` 创建再下一个版本。已发布合同不得原地改 `review` / `acceptance` / `delivery`；只允许旧版本 `status -> superseded` 并写 `superseded_at`。继承审核只在 `content_contract_sha256` 与祖先审核事件完全一致时成立。
- **唯一禁用语言画像。** C9 只 import C1 的 `FORBIDDEN_LANGUAGE_PROFILE` 与 `scan_forbidden_language()`；不得复制词表或定义第二个画像。`publish_artifact` 在写 `report_published` 前扫描 `decision.answer`、`decision.protect[]`、`decision.resolve[]`、`decision.prove[]`、`claims[].text`、`claims[].text_en` 与 `claims[].counterevidence_text`；任一命中抛 `ReportForbiddenLanguageError`（`report_forbidden_language`），合同保持 `draft`。报告合同 1.1 没有 `decision.answer_en`；C9 不得新增该键。
- **C7 Claim 是装配输入。** `assemble_report_contract_v1_1` 只调用 C7 的 `load_publishable_claim_rows()` 与 `validate_claim_bundle()`；不直接查询 `claims`、`claim_evidence`、`evidences` 表，不复制等级表或来源簇推导。`load_publishable_claim_rows` 必须接受 `task_id: uuid.UUID` 并沿 `claims.run_id -> runs.workflow_version_id -> workflow_versions.workbench_task_id` 过滤到任务单；这是 C7 Task 7 的只读签名扩展。C7 未提供该过滤时 C9 停止并返回 C7，不得按市场或时间窗猜测，也不得把同项目其他任务的 Claim 写入合同。返回的 bundle 必须全部为 `approved` 且 `reviewed_content_version == content_version`；出现 `draft`、`pending`、`rejected`、`stale` 任一状态时抛 `ReportContractInvalidError`（`report_contract_invalid`），不静默丢弃。C7 语义门禁在装配器执行；`create_draft_artifact` 只接受已装配合同，不重新加载 Claim bundle。MCP `create_report` 的合同必须由调用方先经装配器生成。`publish_artifact` 在审核通过后用同一 bundle 复核 `validate_claim_bundle`、`validate_claim_semantics` 与 `claim_review_digest`；bundle 与合同快照不一致时抛 `ReportPublishGateBlockedError` 的 `claim_bundle_stale`。`run_id` 为空或 legacy run（`workflow_version_id` 为空）跳过该复核。
- **C8 结论语义是唯一判定。** 装配器对每个市场调用 C8 `validate_conclusion()`。Standard `enter` 必须 3–5 个非暂定 SKU 候选且 rank 唯一；`do_not_enter` 必须市场 `quality_status='qualified'` 且至少 2 个独立原始记录簇；`conditional_enter` 必须同时有 `test_budget_usd`、`observation_window_days`、`success_threshold`、`stop_loss` 四个测试字段。`ConclusionDecision.standard` / `.quick` 为 `None` 时装配器抛 `ReportContractInvalidError`（`report_contract_invalid`，详情含 C8 原因码），不得降级成其他结论，也不得在 `reports.drafts.create` 路径返回未登记的错误码。发布阶段的 Claim bundle 复核失败时用 `report_publish_gate_blocked`；结论本身由审核签字与 G-Publish 门禁绑定，不在发布时重算。C9 只读 `task.package_type` 选择档位，不新增阈值、等级表或第二套候选模型。
- **Quick 2 小时方向稿。** Quick 首次草稿是 2 小时方向稿：同一 `task_id` 与 `order_id`，`report_version=1`，`review.status='draft'`，`acceptance` 只用 C1 合法占位组且不触发验收，`delivery` 保持 nil。证据等级上限 L3，`sku_candidates` 必须为空，`conclusion_standard` 必须缺省；只允许五个 Quick 方向标签 `worth_validating`、`deprioritize`、`key_risk`、`evidence_gap`、`recommend_standard_scope`，不得出现 `confirmed`。24 小时正式版由 `create_reviewed_contract_version` 创建 `report_version=2`，沿用同一 `report_id`、`task_id`、`order_id` 与 L3 上限；不得新建 run、workflow、订单、授权或预算账本条目，因此不重复收费。C9 不做计费；同一任务只有一个订单由 C5 保证。
- **C11 导出策略 PII 门禁。** `publish_artifact` 在写 `report_published` 前，用 C11 `services.export_policy.scan_export_policy()` 扫描合同文本字段、`claims[]`、`evidences[].excerpt` / `evidences[].url` 与渲染后的 `report_html` / `sop_html`。命中联系方式、个人主页、头像或追踪参数时，写 `gate_evaluated` 审计事件（`gate_id='G-Publish'`、`gate_status='blocked'`、`reason='pii_detected'`、`export_policy_version`），合同保持 `draft`，抛 `ReportPublishGateBlockedError`（`report_publish_gate_blocked`）。普通商品/来源 URL、品牌、店铺与商业创作者公开身份不命中；证据来源 URL 只去掉追踪参数。`scan_export_policy` 的 contact 匹配必须跳过 UUID（带连字符与 32 位无连字符）与 ISO-8601 时间戳，不得把 `contract_id`、`task_id`、`evidence_id` 误报为电话。命中项只记录 kind、字段路径与偏移，审计事件不得含原始 PII 值。不新增错误码。`report_publish_gate_blocked` 已在 C1 登记为错误码，且 `reports.publish` 的路径 `error_codes` 必须包含它；缺项时 Task 1 停止并返回 C1 重新生成 registry。C11 Task 4 的 `services/export_policy.py` 必须先导出 `scan_export_policy(text: str, *, field_path: str) -> tuple[PiiHit, ...]`、`PiiHit(kind: Literal["contact", "profile_link", "avatar", "tracking"], field_path: str, start: int, end: int)`（不回传原始值）与 `EXPORT_POLICY_VERSION = "export_policy.v1"`；C9 Task 4 开始前用导入测试确认，缺失时停止并返回 C11。C11 迁移 067、保留与删除服务不是 C9 前置。
- **内部审核人不是客户角色。** C9 只认 `report_reviewer_assignments` 的 active 行，`assignment_scope='report_review'`，事件 `reviewer_role='internal_reviewer'`。`workspace_members.role` 仍只有 `owner/admin/member`，不得新增 `reviewer`。客户 owner/admin、报告创建人、Claim owner 不得自审。审核路由使用内部审核上下文，不用客户 `_require_report_admin`。
- **发布归属。** C9 不执行生产发布、A/B 切换、compose/env 修改或重启。生产备份、迁移、compose/env 与重启由 PG0 发布批次执行；控制台由 C14 实现并由 PG0 批次部署；C14 只做只读健康、canary 前置与浏览器验收。
- **唯一内容源。** `report_artifacts.contract_json` 是正式报告内容的唯一事实源。合同读取、SOP 读取、审核绑定、发布校验、控制台展示都只读它。不得从 `reports.content`、claim 表或 evidence 表重新拼合同。
- **已发布不可变。** `status='published'` 的行只能在同一事务内转为 `'superseded'` 并写 `superseded_at`，其他列不得变化。`report_audit_events` 只追加，不得更新或删除。数据库触发器与服务工作层同时守这两条。
- **修订取代。** 新产物用 `supersedes_id` 指向同 `report_id` 的已发布旧产物。发布新产物时旧产物转 `superseded`。同一 `report_id` 最多一行 `published`。
- **不新建 `modules/reports`。** 路由写在现有 `api/routes/reports.py`。不新建 manifest、bundle、delivery 账本、分享或导出实现；这些不属于 C9。
- **GitNexus 强制。** 编辑任何函数、类或方法前先跑 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .` 并记录 callers、processes、risk。`risk: UNKNOWN` 必须用文本搜索复核后才能继续。提交前跑 `node .gitnexus/run.cjs detect-changes --scope all --repo .`；`partial: true` 或 `truncated: true` 不算通过，必须重跑。
- **测试命令固定。** 后端在 `apps/api` 下用 `uv run pytest`、`uv run ruff check .`、`uv run mypy src`。C9 不运行控制台测试；C14 负责 `apps/scraper-console` 的 `npm test`、`tsc --noEmit` 与 Playwright。
- **不直接部署。** 本切片不直接部署任何环境，不执行生产发布、A/B 切换或回滚。生产 A/B 的备份、迁移、compose/env 修改与重启只由 PG0 发布批次执行；控制台由 C14 实现并由 PG0 批次部署；C14 只做只读健康、canary 前置与浏览器验收；C9 只交付迁移、测试证据与交接清单。
- **文案规则。** 面向用户的中文按仓库现有技术写作风格：短句、事实先行、不用营销词、不把“接口未实现”写成“数据未生成”。

---

## File Structure

### 复用，不新建

| 文件 | 责任 |
|---|---|
| `apps/api/src/data_intelligence_hub/schemas/report_contract.py` | 合同模型、语义校验、唯一哈希入口 |
| `apps/api/schemas/report_contract.schema.json` | 合同 JSON Schema，字段与 Pydantic 互校 |
| `apps/api/src/data_intelligence_hub/services/report_builder.py` | 合同构建与等级上限校验 |
| `apps/api/src/data_intelligence_hub/services/report_renderers.py` | 决策者视图与执行者视图两个纯渲染器 |
| `apps/api/src/data_intelligence_hub/services/report_templates.py` | T1/T2/T5 模板注册表 |
| `apps/api/src/data_intelligence_hub/services/report_artifacts.py` | 五哈希、两页哈希、合同载荷、复核 |
| `apps/api/src/data_intelligence_hub/models/report_artifact.py` | `report_artifacts` 模型 |
| `apps/api/src/data_intelligence_hub/models/report.py` | `reports` 与 `report_audit_events` 模型 |
| `apps/api/src/data_intelligence_hub/repositories/report_artifacts.py` | 产物读写，只 flush |
| `apps/api/src/data_intelligence_hub/repositories/reports.py` | `reports` 与审计事件读写 |
| `apps/api/src/data_intelligence_hub/api/routes/reports.py` | 现有报告路由，C9 在此追加 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/tools/reports.py` | MCP `create_report`，C9 改为只产草稿 |

### 新建

| 文件 | 责任 |
|---|---|
| `apps/api/src/data_intelligence_hub/services/report_publication.py` | 草稿、审核、发布、修订、读取完整性 |
| `apps/api/src/data_intelligence_hub/services/report_contract_v1_1.py` | 1.1 装配器、C7 Claim / C8 结论映射、Quick 方向稿、占位组、不可变版本推进 |
| `apps/api/src/data_intelligence_hub/services/report_reviewers.py` | 内部审核人指派与自审拒绝 |
| `apps/api/alembic/versions/202610220065_report_publication.py` | 065 模型缺口、部分唯一索引、不可变与只追加触发器 |
| `apps/api/tests/unit/test_report_contract_v1_1.py` | 装配器、C7 Claim 映射、C8 结论语义、三档质量、占位与版本推进测试 |
| `apps/api/tests/unit/test_report_quick_directional.py` | Quick 2 小时方向稿、L3 上限、24 小时正式版取代与不重复收费测试 |
| `apps/api/tests/unit/test_report_reviewers.py` | 内部审核人 active assignment 与自审拒绝测试 |
| `apps/api/tests/unit/test_report_contract_profile.py` | canonical profile、forbidden-language 与 schema 版本锁定 |
| `apps/api/tests/unit/test_report_publication.py` | 发布生命周期服务测试 |
| `apps/api/tests/unit/test_report_pii_gate.py` | C11 导出策略 PII 扫描、发布阻断与审计测试 |
| `apps/api/tests/unit/test_report_publication_migration.py` | 迁移链与模型列测试 |
| `apps/api/tests/postgres/test_report_publication_constraints.py` | PostgreSQL 触发器与唯一索引验收 |
| `apps/api/tests/integration/test_report_publication_routes.py` | REST 端点端到端测试 |

### 明确不建

- 不建 `apps/api/src/data_intelligence_hub/modules/reports/`。
- 不建 `delivery_manifest.json`、bundle、分享、导出或验收账本。
- 不建第二份 `report_contract`、claim 状态表、证据等级表或模板注册表。

---

### Task 0: 前置基线检查

**Files:**
- Read: `apps/api/alembic/versions/`
- Read: `apps/api/src/data_intelligence_hub/schemas/report_contract.py`
- Read: `apps/api/src/data_intelligence_hub/services/claims.py`
- Read: `apps/api/src/data_intelligence_hub/services/claim_semantics.py`
- Read: `apps/api/src/data_intelligence_hub/services/dataset_quality.py`
- Read: `apps/api/src/data_intelligence_hub/services/export_policy.py`
- Read: `.gitnexus/run.cjs`

**Interfaces:**
- Consumes: B5 报告合同基线；C1 的 `CANONICAL_PROFILE_ID` 与 `SCHEMA_VERSION`；C7 `load_publishable_claim_rows(task_id=...)` 与 `validate_claim_bundle`；C8 `validate_conclusion` 与 `ConclusionInputs`；C11 `scan_export_policy`、`PiiHit`、`EXPORT_POLICY_VERSION`；C7/C8 的迁移与事实表。
- Produces: 一份可继续执行的基线结论。任何一项不满足时停止，不进入 Task 1。

- [ ] **Step 1: 确认前置分支是祖先**

Run:
```bash
cd /Users/lute/Project/data_scrapy
git worktree add /Users/lute/Project/data_scrapy-gov-c9 -b feat/gov-c9 feat/gov-c8
cd /Users/lute/Project/data_scrapy-gov-c9
git rev-parse --abbrev-ref HEAD
git rev-parse --verify feat/gov-c8^{commit}
git merge-base --is-ancestor feat/gov-c8 HEAD && echo C8_BRANCH_BASE_OK
git rev-parse --short HEAD
```
Expected: 当前分支是 `feat/gov-c9`；`feat/gov-c8` 可解析；输出 `C8_BRANCH_BASE_OK`；HEAD 等于前置分支提交。工作树必须由 `git worktree add /Users/lute/Project/data_scrapy-gov-c9 -b feat/gov-c9 feat/gov-c8` 创建。

- [ ] **Step 2: 确认 C1 的 canonical profile 常量与 registry 存在**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run python -c "from data_intelligence_hub.schemas.report_contract import CANONICAL_PROFILE_ID, SCHEMA_VERSION; print(CANONICAL_PROFILE_ID, SCHEMA_VERSION)"
cd .. && test -f configs/contracts/v1.1.0/registry.json && echo C1_REGISTRY_PRESENT
```
Expected: `dih-canonical-json-v1 1.1.0` 与 `C1_REGISTRY_PRESENT`。其他组合停止执行，返回 C1。严格 RFC 8785 不在本切片实施。

- [ ] **Step 2A: 确认 C7/C8/C11 装配接口**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run python -c "import inspect; from data_intelligence_hub.services.claims import load_publishable_claim_rows; assert 'task_id' in inspect.signature(load_publishable_claim_rows).parameters; print('C7_TASK_SCOPE_OK')"
uv run python -c "from data_intelligence_hub.services.dataset_quality import ConclusionInputs, SkuCandidate, validate_conclusion; print('C8_CONCLUSION_OK')"
uv run python -c "from data_intelligence_hub.services.export_policy import EXPORT_POLICY_VERSION, PiiHit, scan_export_policy; print(EXPORT_POLICY_VERSION, PiiHit.__name__, callable(scan_export_policy))"
```
Expected: `C7_TASK_SCOPE_OK`、`C8_CONCLUSION_OK` 与 `export_policy.v1 PiiHit True`。`load_publishable_claim_rows` 缺 `task_id` 时停止并返回 C7 Task 7 补只读签名；C8 或 C11 缺符号时分别返回 C8/C11。C9 不得复制 claim 簇推导、结论阈值或 PII 正则。

- [ ] **Step 3: 确认 058–064 迁移存在且单头**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
ls apps/api/alembic/versions/202610220058_*.py
ls apps/api/alembic/versions/202610220059_*.py
ls apps/api/alembic/versions/202610220060_*.py
ls apps/api/alembic/versions/202610220061_*.py
ls apps/api/alembic/versions/202610220062_*.py
ls apps/api/alembic/versions/202610220063_*.py
ls apps/api/alembic/versions/202610220064_*.py
cd apps/api && uv run alembic heads
```
Expected: 七个文件全部存在；`alembic heads` 只有一行 `202610220064 (head)`。缺一个或 head 不是 064 时停止执行，先补 C1–C8。

- [ ] **Step 4: 记录 GitNexus 基线**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "ReportArtifact" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_report" --direction upstream --repo .
```
Expected: 输出 callers、processes 与 risk。若 `risk: UNKNOWN`，用 `git grep -n "ReportArtifact\\|create_report" -- apps/api/src apps/api/tests` 复核后再继续。HIGH 或 CRITICAL 必须在计划执行记录中标注，不得用 `riskSharedAxes` 豁免。

---

### Task 1: C1 registry 只读守卫

**Files:**
- Create: `apps/api/tests/unit/test_report_publication_migration.py`（先放 C1 registry 只读守卫，Task 3 再扩）

**Interfaces:**
- Consumes: C1 的 `configs/contracts/v1.1.0/registry.json` 与已批准设计 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` §3.2、§6.1、§6.3。
- Produces: 只读登记守卫测试：`ck_report_artifacts_status`、`uq_report_artifacts_current_published`、`reviewer_role`。C9 不修改契约文档与 registry；缺项时停止并返回 C1。

- [ ] **Step 1: 写只读守卫测试**

Create `apps/api/tests/unit/test_report_publication_migration.py`:
```python
"""C9：C1 registry 只读守卫与迁移静态检查。

本测试只读 C1 的机器 registry。它不修改契约文档，不修改 registry。
"""

from __future__ import annotations

from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
REGISTRY = REPO_ROOT / "configs/contracts/v1.1.0/registry.json"


def registry_text() -> str:
    if not REGISTRY.exists():
        raise AssertionError(
            "C1 registry 缺失：configs/contracts/v1.1.0/registry.json；返回 C1"
        )
    return REGISTRY.read_text(encoding="utf-8")


def test_c1_registry_registers_published_status_check() -> None:
    assert "ck_report_artifacts_status" in registry_text()


def test_c1_registry_registers_current_published_unique() -> None:
    assert "uq_report_artifacts_current_published" in registry_text()


def test_c1_registry_registers_reviewer_role() -> None:
    assert "reviewer_role" in registry_text()


def test_c1_registry_registers_internal_reviewer_assignment() -> None:
    text = registry_text()
    assert "report_reviewer_assignments" in text
    assert "report_review" in text
    assert "reviewer_assignment_required" in text
    assert "reviewer_self_review_forbidden" in text
    assert '"reviewer"' not in text.split("workspace_members.role", 1)[1].split("]", 1)[0]


def test_c1_registry_registers_report_lifecycle_errors_and_deferred_shares() -> None:
    text = registry_text()
    for marker in (
        "report_quality_not_ready",
        "report_contract_not_published",
        "report_contract_hash_mismatch",
        "report_contract_invalid",
        "report_artifact_not_draft",
        "report_artifact_incomplete",
        "report_artifact_integrity_failed",
        "report_publish_gate_blocked",
        "report_revision_target_invalid",
        "report_review_required",
        "report_forbidden_language",
    ):
        assert marker in text
    assert '"report_shares"' in text
    assert "首期延期" in text


def test_c1_registry_registers_publish_gate_blocked_on_publish_path() -> None:
    text = registry_text()
    publish_path = text.split('"id": "reports.publish"', 1)[1].split("}", 1)[0]
    assert "report_publish_gate_blocked" in publish_path


def test_c1_registry_registers_one_versioned_forbidden_language_profile() -> None:
    text = registry_text()
    assert text.count('"profile_id": "dih-descriptive-language-v1"') == 1
    assert '"profile_version": "1.0.0"' in text
    assert "导致" in text
    assert "销量" in text
```

- [ ] **Step 2: 运行测试，确认 C1 登记齐全**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication_migration.py -v
```
Expected: `7 passed`。任一断言失败表示 C1 registry 缺约束、内部审核指派、错误码、发布路径错误码、延期分享或唯一禁用语言画像；停止 C9，把缺失项返回 C1 补充登记。

- [ ] **Step 3: 处理缺项（不写契约）**

若 Step 2 失败，按失败断言列出缺失的约束名或字段，返回 C1。C9 不得：

- 修改 `docs/design/【契约冻结】v1-表名-枚举-接口.md`。
- 修改或重新生成 `configs/contracts/v1.1.0/registry.json`。
- 在 C9 内追加“实现决定”或本地契约副本。

C1 补齐并重新生成 registry 后，从 Step 2 重跑。

- [ ] **Step 4: 运行测试，确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication_migration.py -v
```
Expected: `7 passed`。这是只读守卫；C9 没有修改契约文档或 registry。

- [ ] **Step 5: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_report_publication_migration.py
git commit -m "test(report): guard c1 registered report publication contract"
```
Expected: `detect-changes` 输出不含 `partial: true` 或 `truncated: true`；提交成功，且本次提交不包含契约文档或 registry。

---

### Task 2: 锁定 canonical profile 与 schema 版本

**Files:**
- Create: `apps/api/tests/unit/test_report_contract_profile.py`
- Read: `apps/api/src/data_intelligence_hub/schemas/report_contract.py`

**Interfaces:**
- Consumes: C1 导出的 `CANONICAL_PROFILE_ID: str`、`SCHEMA_VERSION: str`、`canonical_json_bytes`。
- Produces: 一条不可绕过的测试：profile 固定为 `dih-canonical-json-v1`，schema 固定为 `1.1.0`。

- [ ] **Step 1: 写测试**

Create `apps/api/tests/unit/test_report_contract_profile.py`:
```python
"""C9：canonical profile 与 schema 版本由 C1 单一冻结。"""

from __future__ import annotations

from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    FORBIDDEN_LANGUAGE_PROFILE,
    FORBIDDEN_LANGUAGE_PROFILE_ID,
    FORBIDDEN_LANGUAGE_PROFILE_VERSION,
    SCHEMA_VERSION,
    canonical_json_bytes,
    scan_forbidden_language,
)


def test_profile_is_b5_v1() -> None:
    assert CANONICAL_PROFILE_ID == "dih-canonical-json-v1"
    assert SCHEMA_VERSION == "1.1.0"


def test_forbidden_language_profile_is_single_sourced() -> None:
    assert FORBIDDEN_LANGUAGE_PROFILE_ID == "dih-descriptive-language-v1"
    assert FORBIDDEN_LANGUAGE_PROFILE_VERSION == "1.0.0"
    assert FORBIDDEN_LANGUAGE_PROFILE["profile_id"] == FORBIDDEN_LANGUAGE_PROFILE_ID
    assert scan_forbidden_language(
        {"decision": {"answer": "两个变量共同出现，属于描述性差异。"}}
    ) == []
    hits = scan_forbidden_language(
        {"decision": {"answer": "评论提升销量。"}}
    )
    assert [(hit.term, hit.rule) for hit in hits] == [("提升", "causal")]


def test_canonical_bytes_exclude_generated_at_and_artifact() -> None:
    contract = {
        "schema_version": SCHEMA_VERSION,
        "template_id": "t1_voc",
        "generated_at": "2026-10-21T00:00:00Z",
        "identity": {
            "task_id": "11111111-1111-1111-1111-111111111111",
            "brand": "Fixture",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
        },
        "decision": {
            "decision_question": "是否进入？",
            "answer": "先验证。",
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [],
        "coverage": {"cells": []},
        "metrics": [],
        "claims": [],
        "evidences": [],
        "run_ledger": [],
        "limits": [],
        "unknowns": [],
        "artifact": {
            "report_html_sha256": "",
            "sop_html_sha256": "",
            "contract_sha256": "",
        },
    }
    baseline = canonical_json_bytes(contract)
    changed_time = dict(contract, generated_at="2030-01-01T00:00:00Z")
    changed_artifact = dict(
        contract,
        artifact={
            "report_html_sha256": "a" * 64,
            "sop_html_sha256": "b" * 64,
            "contract_sha256": "c" * 64,
        },
    )

    assert canonical_json_bytes(changed_time) == baseline
    assert canonical_json_bytes(changed_artifact) == baseline
```

- [ ] **Step 2: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_contract_profile.py -v
```
Expected: `3 passed`。若 C1 尚未冻结常量或画像，测试在导入处失败；停止执行，先完成 C1。严格 RFC 8785 延期，C9 不测试第二套 profile。

- [ ] **Step 3: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_report_contract_profile.py
git commit -m "test(report): pin c1 canonical profile and schema version"
```
Expected: `detect-changes` 无 `partial` 或 `truncated`；提交成功。

---

### Task 3: 迁移 065 补模型缺口

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/models/report_artifact.py`
- Modify: `apps/api/src/data_intelligence_hub/models/report.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/report_artifacts.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/workspaces.py`
- Create: `apps/api/src/data_intelligence_hub/models/report_reviewer_assignment.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/report_reviewers.py`
- Create: `apps/api/alembic/versions/202610220065_report_publication.py`
- Modify: `apps/api/tests/unit/test_report_publication_migration.py`
- Create: `apps/api/tests/unit/test_report_reviewers.py`
- Create: `apps/api/tests/postgres/test_report_publication_constraints.py`

**Interfaces:**
- Consumes: Task 1 的 C1 registry 守卫结论；B5 的 `report_artifacts` 与 `report_audit_events`。
- Produces: `ReportArtifact.status / created_by / published_at / published_by / supersedes_id / superseded_at`；`ReportAuditEvent.artifact_id`；`ReportReviewerAssignment`；`create_reviewer_assignment`；`get_active_reviewer_assignment`；`revoke_reviewer_assignment`；`create_artifact(..., artifact_id=None, status="draft", created_by=None, supersedes_id=None)`；`get_artifact_for_update`；`get_current_published`；`get_latest_artifact`；`latest_artifacts_for_reports`；`get_workspace_member_role`。

- [ ] **Step 1: 扩展静态测试**

在 `apps/api/tests/unit/test_report_publication_migration.py` 末尾追加：
```python
import runpy

from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact

MIGRATION = API_ROOT / "alembic/versions/202610220065_report_publication.py"


def test_revision_chain_points_to_c8() -> None:
    module = runpy.run_path(str(MIGRATION))

    assert module["revision"] == "202610220065"
    assert module["down_revision"] == "202610220064"


def test_migration_adds_publication_columns_and_triggers() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for token in (
        '"status"',
        '"created_by"',
        '"published_at"',
        '"published_by"',
        '"supersedes_id"',
        '"superseded_at"',
        '"artifact_id"',
        "uq_report_artifacts_current_published",
        "trg_report_artifacts_guard_published",
        "trg_report_audit_events_append_only",
        "report_artifact_immutable",
        "report_audit_events_append_only",
    ):
        assert token in source


def test_model_publication_columns() -> None:
    table = ReportArtifact.__table__

    assert table.columns["status"].nullable is False
    assert table.columns["status"].default.arg == "draft"
    assert table.columns["created_by"].nullable is True
    assert table.columns["published_at"].nullable is True
    assert table.columns["published_by"].nullable is True
    assert table.columns["supersedes_id"].nullable is True
    assert table.columns["superseded_at"].nullable is True


def test_audit_event_has_optional_artifact_id() -> None:
    table = ReportAuditEvent.__table__

    assert table.columns["report_id"].nullable is True
    assert table.columns["artifact_id"].nullable is True


def test_migration_creates_internal_reviewer_assignment_table() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for token in (
        '"report_reviewer_assignments"',
        '"reviewer_user_id"',
        '"assignment_scope"',
        '"assigned_by"',
        '"expires_at"',
        '"revoked_at"',
        "ck_report_reviewer_assignments_scope",
        "ck_report_reviewer_assignments_status",
        "uq_report_reviewer_assignments_active",
    ):
        assert token in source


def test_reviewer_assignment_model_has_limited_scope() -> None:
    from data_intelligence_hub.models.report_reviewer_assignment import (
        ReportReviewerAssignment,
    )

    columns = ReportReviewerAssignment.__table__.columns
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
    } <= set(columns.keys())
    assert columns["status"].default.arg == "active"
    assert columns["assignment_scope"].default.arg == "report_review"
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication_migration.py -v
```
Expected: 迁移文件不存在；模型列断言失败。

- [ ] **Step 3: 修改模型**

在 `models/report_artifact.py` 中：
- `report_id` 改为真正外键：`mapped_column(ForeignKey("reports.id"), nullable=True)`。
- 在 `created_at` 前加入：
```python
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_artifacts.id")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```
- 在 `__table_args__` 加入：
```python
        Index("ix_report_artifacts_report_status", "report_id", "status"),
```
- 在类 docstring 补一句：部分唯一索引与触发器只在迁移 065 中创建，因为 SQLite 不支持同样的语法。

在 `models/report.py` 中：
- `ReportAuditEvent.report_id` 改为 `Mapped[uuid.UUID | None]`。
- 增加：
```python
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_artifacts.id")
    )
```
- `__table_args__` 加入：
```python
        Index("ix_report_audit_events_artifact_created", "artifact_id", "created_at"),
```
需要从 SQLAlchemy 导入 `Index`。

Create `models/report_reviewer_assignment.py`:
```python
"""内部审核人指派。不是客户工作区角色。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base


class ReportReviewerAssignment(Base):
    __tablename__ = "report_reviewer_assignments"
    __table_args__ = (
        Index(
            "uq_report_reviewer_assignments_active",
            "report_id",
            "reviewer_user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index(
            "ix_report_reviewer_assignments_reviewer_status",
            "reviewer_user_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_artifacts.id")
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assignment_scope: Mapped[str] = mapped_column(
        String(30), default="report_review", server_default="report_review"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Create `repositories/report_reviewers.py`:
```python
"""内部审核人指派的追加与只读查询。仓储只 flush。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)


async def create_reviewer_assignment(
    session: AsyncSession,
    row: ReportReviewerAssignment,
) -> ReportReviewerAssignment:
    session.add(row)
    await session.flush()
    return row


async def get_active_reviewer_assignment(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
) -> ReportReviewerAssignment | None:
    result = await session.execute(
        select(ReportReviewerAssignment).where(
            ReportReviewerAssignment.report_id == report_id,
            ReportReviewerAssignment.reviewer_user_id == reviewer_user_id,
            ReportReviewerAssignment.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def list_active_reviewer_assignments(
    session: AsyncSession,
    *,
    reviewer_user_id: uuid.UUID,
) -> list[ReportReviewerAssignment]:
    result = await session.execute(
        select(ReportReviewerAssignment).where(
            ReportReviewerAssignment.reviewer_user_id == reviewer_user_id,
            ReportReviewerAssignment.status == "active",
        )
    )
    return list(result.scalars().all())


async def revoke_reviewer_assignment(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    revoked_at: datetime,
) -> ReportReviewerAssignment | None:
    row = await get_active_reviewer_assignment(
        session,
        report_id=report_id,
        reviewer_user_id=reviewer_user_id,
    )
    if row is None:
        return None
    row.status = "revoked"
    row.revoked_at = revoked_at
    await session.flush()
    return row
```

- [ ] **Step 4: 写迁移**

Create `apps/api/alembic/versions/202610220065_report_publication.py`:
```python
"""Report publication lifecycle.

Revision ID: 202610220065
Revises: 202610220064
Create Date: 2026-10-22

本迁移只补模型缺口，不改 B5 的五个哈希列与两个 HTML 列。

不可变规则：
- published 行只允许在同一事务内把 status 改为 superseded 并写 superseded_at。
- 其他列变化一律拒绝。
- superseded 行禁止更新与删除。
- draft 行允许删除，便于清理未审核草稿。

只追加规则：
- report_audit_events 禁止 UPDATE 与 DELETE。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220065"
down_revision: str | None = "202610220064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_reviewer_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "assignment_scope",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'report_review'"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "assignment_scope IN ('report_read', 'report_review')",
            name="ck_report_reviewer_assignments_scope",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_report_reviewer_assignments_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_report_reviewer_assignments_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_report_reviewer_assignments_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"],
            name="fk_report_reviewer_assignments_report_id_reports",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["report_artifacts.id"],
            name="fk_report_reviewer_assignments_artifact_id_report_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"],
            name="fk_report_reviewer_assignments_reviewer_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["users.id"],
            name="fk_report_reviewer_assignments_assigned_by_users",
        ),
    )
    op.create_index(
        "uq_report_reviewer_assignments_active",
        "report_reviewer_assignments",
        ["report_id", "reviewer_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_report_reviewer_assignments_reviewer_status",
        "report_reviewer_assignments",
        ["reviewer_user_id", "status"],
    )
    op.add_column(
        "report_artifacts",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
    )
    op.add_column("report_artifacts", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column(
        "report_artifacts",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("report_artifacts", sa.Column("published_by", sa.Uuid(), nullable=True))
    op.add_column(
        "report_artifacts",
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "report_artifacts",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_report_artifacts_status",
        "report_artifacts",
        "status IN ('draft', 'published', 'superseded')",
    )
    op.create_foreign_key(
        "fk_report_artifacts_report_id_reports",
        "report_artifacts",
        "reports",
        ["report_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_artifacts_created_by_users",
        "report_artifacts",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_artifacts_published_by_users",
        "report_artifacts",
        "users",
        ["published_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_artifacts_supersedes_id_report_artifacts",
        "report_artifacts",
        "report_artifacts",
        ["supersedes_id"],
        ["id"],
    )
    op.create_index(
        "ix_report_artifacts_report_status",
        "report_artifacts",
        ["report_id", "status"],
    )
    op.create_index(
        "uq_report_artifacts_current_published",
        "report_artifacts",
        ["report_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )

    op.add_column(
        "report_audit_events",
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
    )
    op.alter_column(
        "report_audit_events",
        "report_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_report_audit_events_artifact_id_report_artifacts",
        "report_audit_events",
        "report_artifacts",
        ["artifact_id"],
        ["id"],
    )
    op.create_index(
        "ix_report_audit_events_artifact_created",
        "report_audit_events",
        ["artifact_id", "created_at"],
    )
    op.create_check_constraint(
        "ck_report_audit_events_target",
        "report_audit_events",
        "report_id IS NOT NULL OR artifact_id IS NOT NULL",
    )

    op.execute(
        sa.text(
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

            CREATE TRIGGER trg_report_artifacts_guard_published
            BEFORE UPDATE OR DELETE ON report_artifacts
            FOR EACH ROW EXECUTE FUNCTION report_artifacts_guard_published();

            CREATE OR REPLACE FUNCTION report_audit_events_append_only_fn()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'report_audit_events_append_only: %', OLD.id;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_report_audit_events_append_only
            BEFORE UPDATE OR DELETE ON report_audit_events
            FOR EACH ROW EXECUTE FUNCTION report_audit_events_append_only_fn();
            """
        )
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_report_audit_events_append_only ON report_audit_events"
    )
    op.execute("DROP FUNCTION IF EXISTS report_audit_events_append_only_fn()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_report_artifacts_guard_published ON report_artifacts"
    )
    op.execute("DROP FUNCTION IF EXISTS report_artifacts_guard_published()")
    op.drop_constraint(
        "ck_report_audit_events_target",
        "report_audit_events",
        type_="check",
    )
    op.drop_index(
        "ix_report_audit_events_artifact_created",
        table_name="report_audit_events",
    )
    op.drop_constraint(
        "fk_report_audit_events_artifact_id_report_artifacts",
        "report_audit_events",
        type_="foreignkey",
    )
    op.alter_column(
        "report_audit_events",
        "report_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.drop_column("report_audit_events", "artifact_id")
    op.drop_index(
        "uq_report_artifacts_current_published",
        table_name="report_artifacts",
    )
    op.drop_index("ix_report_artifacts_report_status", table_name="report_artifacts")
    op.drop_constraint(
        "fk_report_artifacts_supersedes_id_report_artifacts",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_artifacts_published_by_users",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_artifacts_created_by_users",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_artifacts_report_id_reports",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_report_artifacts_status",
        "report_artifacts",
        type_="check",
    )
    op.drop_column("report_artifacts", "superseded_at")
    op.drop_column("report_artifacts", "supersedes_id")
    op.drop_column("report_artifacts", "published_by")
    op.drop_column("report_artifacts", "published_at")
    op.drop_column("report_artifacts", "created_by")
    op.drop_column("report_artifacts", "status")
    op.drop_index(
        "ix_report_reviewer_assignments_reviewer_status",
        table_name="report_reviewer_assignments",
    )
    op.drop_index(
        "uq_report_reviewer_assignments_active",
        table_name="report_reviewer_assignments",
    )
    op.drop_table("report_reviewer_assignments")
```

- [ ] **Step 5: 扩展仓储**

在 `repositories/report_artifacts.py` 中：
- `create_artifact` 增加参数 `artifact_id: uuid.UUID | None = None`、`status: str = "draft"`、`created_by: uuid.UUID | None = None`、`supersedes_id: uuid.UUID | None = None`，并写入模型。`artifact_id` 供交付版本在合同 `delivery.report_artifact_id` 中自引用。
- 增加：
```python
async def get_artifact_for_update(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> ReportArtifact | None:
    """按工作区锁一行产物。SQLite 忽略 FOR UPDATE。"""
    result = await session.execute(
        select(ReportArtifact)
        .where(
            ReportArtifact.id == artifact_id,
            ReportArtifact.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def get_current_published(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> ReportArtifact | None:
    """返回该报告当前 published 的一行。"""
    result = await session.execute(
        select(ReportArtifact)
        .where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.report_id == report_id,
            ReportArtifact.status == "published",
        )
        .order_by(ReportArtifact.published_at.desc(), ReportArtifact.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> ReportArtifact | None:
    """优先返回 published；没有时返回最新草稿。"""
    published = await get_current_published(
        session,
        workspace_id=workspace_id,
        report_id=report_id,
    )
    if published is not None:
        return published
    result = await session.execute(
        select(ReportArtifact)
        .where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.report_id == report_id,
        )
        .order_by(ReportArtifact.created_at.desc(), ReportArtifact.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_artifacts_for_reports(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ReportArtifact]:
    """一次查出多个报告的最新产物，published 优先。"""
    if not report_ids:
        return {}
    result = await session.execute(
        select(ReportArtifact)
        .where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.report_id.in_(report_ids),
        )
        .order_by(ReportArtifact.created_at.desc(), ReportArtifact.id)
    )
    rank = {"superseded": 0, "draft": 1, "published": 2}
    latest: dict[uuid.UUID, ReportArtifact] = {}
    for artifact in result.scalars().all():
        if artifact.report_id is None:
            continue
        current = latest.get(artifact.report_id)
        if current is None or rank[artifact.status] > rank[current.status]:
            latest[artifact.report_id] = artifact
    return latest
```

在 `repositories/workspaces.py` 中增加：
```python
async def get_workspace_member_role(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """返回成员角色。不是成员时返回 None。"""
    result = await session.execute(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 6: 写 PostgreSQL 约束测试**

Create `apps/api/tests/postgres/test_report_publication_constraints.py`:
```python
"""C9：已发布不可变、审计只追加、同一报告最多一个 published。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


@asynccontextmanager
async def _engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed(connection: AsyncConnection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    report_id = uuid.uuid4()
    await connection.execute(
        text(
            "INSERT INTO users (id, email, password_hash, name, status) "
            "VALUES (:id, :email, 'x', 'C9', 'active')"
        ),
        {"id": user_id, "email": f"{user_id}@example.test"},
    )
    await connection.execute(
        text(
            "INSERT INTO workspaces (id, name, slug, owner_id) "
            "VALUES (:id, 'C9', :slug, :owner)"
        ),
        {"id": workspace_id, "slug": f"c9-{workspace_id}", "owner": user_id},
    )
    await connection.execute(
        text(
            "INSERT INTO projects (id, workspace_id, name, domain, status, owner_id) "
            "VALUES (:id, :ws, 'C9', 'osint', 'active', :owner)"
        ),
        {"id": project_id, "ws": workspace_id, "owner": user_id},
    )
    await connection.execute(
        text(
            "INSERT INTO reports "
            "(id, workspace_id, project_id, report_type, title, content, status, "
            " period_start, period_end) "
            "VALUES (:id, :ws, :project, 't1_voc', 'C9', '', 'draft', now(), now())"
        ),
        {"id": report_id, "ws": workspace_id, "project": project_id},
    )
    return workspace_id, project_id, report_id


async def _insert_artifact(
    connection: AsyncConnection,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    status: str,
) -> uuid.UUID:
    artifact_id = uuid.uuid4()
    await connection.execute(
        text(
            """
            INSERT INTO report_artifacts (
                id, workspace_id, project_id, report_id, template_id, version,
                contract_json, contract_sha256, data_sha256,
                report_html_sha256, sop_html_sha256, combined_sha256,
                report_html, sop_html, status
            ) VALUES (
                :id, :ws, :project, :report, 't1_voc', '1.0.0',
                CAST('{}' AS json), :contract_hash, :data_hash,
                :report_hash, :sop_hash, :combined_hash,
                '', '', :status
            )
            """
        ),
        {
            "id": artifact_id,
            "ws": workspace_id,
            "project": project_id,
            "report": report_id,
            "contract_hash": "a" * 64,
            "data_hash": "b" * 64,
            "report_hash": "c" * 64,
            "sop_hash": "d" * 64,
            "combined_hash": "e" * 64,
            "status": status,
        },
    )
    return artifact_id


@pytest.mark.anyio
async def test_published_artifact_content_is_immutable(
    postgres_database_url: str,
) -> None:
    async with _engine(postgres_database_url) as engine:
        async with engine.begin() as connection:
            workspace_id, project_id, report_id = await _seed(connection)
            artifact_id = await _insert_artifact(
                connection,
                workspace_id=workspace_id,
                project_id=project_id,
                report_id=report_id,
                status="published",
            )
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError, match="report_artifact_immutable"):
                await connection.execute(
                    text(
                        "UPDATE report_artifacts SET contract_json = '{\"x\":1}' "
                        "WHERE id = :id"
                    ),
                    {"id": artifact_id},
                )


@pytest.mark.anyio
async def test_only_one_published_per_report(postgres_database_url: str) -> None:
    async with _engine(postgres_database_url) as engine:
        async with engine.begin() as connection:
            workspace_id, project_id, report_id = await _seed(connection)
            await _insert_artifact(
                connection,
                workspace_id=workspace_id,
                project_id=project_id,
                report_id=report_id,
                status="published",
            )
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError):
                await _insert_artifact(
                    connection,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    report_id=report_id,
                    status="published",
                )


@pytest.mark.anyio
async def test_audit_events_are_append_only(postgres_database_url: str) -> None:
    async with _engine(postgres_database_url) as engine:
        async with engine.begin() as connection:
            workspace_id, project_id, report_id = await _seed(connection)
            artifact_id = await _insert_artifact(
                connection,
                workspace_id=workspace_id,
                project_id=project_id,
                report_id=report_id,
                status="draft",
            )
            event_id = uuid.uuid4()
            await connection.execute(
                text(
                    "INSERT INTO report_audit_events "
                    "(id, workspace_id, report_id, artifact_id, event_type) "
                    "VALUES (:id, :ws, :report, :artifact, 'report_draft_created')"
                ),
                {
                    "id": event_id,
                    "ws": workspace_id,
                    "report": report_id,
                    "artifact": artifact_id,
                },
            )
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError, match="report_audit_events_append_only"):
                await connection.execute(
                    text(
                        "UPDATE report_audit_events SET event_type = 'x' "
                        "WHERE id = :id"
                    ),
                    {"id": event_id},
                )
```

- [ ] **Step 7: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication_migration.py -v
```
Expected: `7 passed`。

Run（只有本机有受控测试库时）：
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://localhost/c9_publication_workflow_plan_phase2_test \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest tests/postgres/test_report_publication_constraints.py -v
```
Expected: `3 passed`。没有测试库时这些用例显示 `skipped`，这是允许的；生产发布前必须在受控库补跑。

- [ ] **Step 8: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "ReportArtifact" --direction upstream --repo .
node .gitnexus/run.cjs impact "ReportAuditEvent" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220065_report_publication.py \
  apps/api/src/data_intelligence_hub/models/report_artifact.py \
  apps/api/src/data_intelligence_hub/models/report.py \
  apps/api/src/data_intelligence_hub/repositories/report_artifacts.py \
  apps/api/src/data_intelligence_hub/repositories/workspaces.py \
  apps/api/tests/unit/test_report_publication_migration.py \
  apps/api/tests/postgres/test_report_publication_constraints.py
git commit -m "feat(report): 065 补发布状态、修订与审核事件模型"
```
Expected: 两次 impact 都列出 callers 与 processes；`detect-changes` 无 `partial` 或 `truncated`；提交成功。

---

### Task 4: 报告发布生命周期服务

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/report_publication.py`
- Modify: `apps/api/src/data_intelligence_hub/services/report_artifacts.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Create: `apps/api/tests/unit/test_report_publication.py`
- Create: `apps/api/tests/unit/test_report_pii_gate.py`

**Interfaces:**
- Consumes: Task 3 的模型与仓储；Task 4A 的 `assemble_report_contract_v1_1`、`assert_single_task_id`、`content_contract_sha256` 与 `create_reviewed_contract_version`；B5 的 `build_artifact`、`verify_artifact`、`contract_payload`；C8 的 `services.market_quality.ensure_market_quality` 与 `MarketQualityNotReadyError`；C1 的 `FORBIDDEN_LANGUAGE_PROFILE` 与 `scan_forbidden_language`；C11 的 `services.export_policy.scan_export_policy`、`PiiHit` 与 `EXPORT_POLICY_VERSION`。
- Produces:
  - `render_contract_pages(contract: ReportContract) -> RenderedContractPages`
  - `create_draft_artifact(session, *, workspace, report, template_id, contract, created_by, project_id=None, run_id=None, supersedes_id=None, version="1.0.0") -> ReportArtifact`
  - `claim_review_digest(contract: ReportContract | Mapping[str, Any]) -> str`
  - `scan_contract_pii(contract: ReportContract | Mapping[str, Any], *, report_html: str = "", sop_html: str = "") -> list[PiiHit]`
  - `record_review(session, *, workspace, report_id, artifact_id, reviewer, assignment, decision, review_scope, notes, expected_contract_sha256) -> ReportAuditEvent`
  - `publish_artifact(session, *, workspace, report_id, artifact_id, publisher, expected_contract_sha256) -> ReportArtifact`
  - `get_current_contract(session, *, workspace, report_id) -> tuple[ReportArtifact, dict[str, Any]]`
  - `get_readable_artifact(session, *, workspace, report_id) -> ReportArtifact`
  - `list_revisions(session, *, workspace, report_id) -> list[ReportArtifact]`
  - `ReportQualityNotReadyError(ServiceError)`：质量门禁失败，错误码 `report_quality_not_ready`

- [ ] **Step 0: 确认 C11 导出策略接口存在**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run python -c "from data_intelligence_hub.services.export_policy import EXPORT_POLICY_VERSION, PiiHit, scan_export_policy; print(EXPORT_POLICY_VERSION, PiiHit.__name__, callable(scan_export_policy))"
```
Expected: `export_policy.v1 PiiHit True`。缺任一符号时停止 C9，把缺失符号返回 C11 Task 4 补齐；C9 不得在本地复制正则、词表或第二套遮蔽规则，也不得跳过 PII 门禁。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_report_publication.py`:
```python
"""C9：草稿、审核、发布、修订与唯一内容源。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.services.report_publication as report_publication
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.exceptions import (
    ReportContractHashMismatchError,
    ReportContractNotPublishedError,
    ReportPublishGateBlockedError,
    ReportQualityNotReadyError,
    ReportReviewRequiredError,
)
from data_intelligence_hub.services.market_quality import MarketQualityNotReadyError
from data_intelligence_hub.services.report_publication import (
    create_draft_artifact,
    get_current_contract,
    list_revisions,
    publish_artifact,
    record_review,
)

API_ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "11111111-1111-1111-1111-111111111111"


def _contract() -> dict[str, Any]:
    """C1 唯一 1.1 形状；B5 嵌套组保持原字段名。"""
    task_id = "11111111-1111-1111-1111-111111111111"
    nil = "00000000-0000-0000-0000-000000000000"
    zero = "0" * 64
    return {
        "schema_version": "1.1.0",
        "contract_id": "22222222-2222-2222-2222-222222222222",
        "task_id": task_id,
        "order_id": task_id,
        "template_id": "t1_voc",
        "template_version": "1.0.0",
        "report_version": 1,
        "generated_at": "2026-10-22T00:00:00Z",
        "identity": {
            "task_id": task_id,
            "brand": "Example",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
        },
        "decision": {
            "decision_question": "是否进入？",
            "answer": "先验证。",
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [{"gate_id": "G-Publish", "status": "pass"}],
        "coverage": {"cells": []},
        "markets": [],
        "metrics": [],
        "claims": [],
        "evidences": [],
        "sku_candidates": [],
        "datasets": [],
        "scorecard": {
            "markets": [],
            "minimum_evidence_grade": "L1_contract",
            "claims": {
                "total": 0,
                "by_status": {},
                "by_grade": {},
                "independent_source_count": 0,
            },
        },
        "rights": {"sources": []},
        "currency": {
            "base_currency": "USD",
            "quote_currency": "USD",
            "rate": 1.0,
            "rate_date": "2026-10-22",
            "source": "fixture",
        },
        "language": {
            "primary_language": "zh-CN",
            "executive_summary_language": "en",
            "translation_method": "deterministic_template",
        },
        "run_ledger": [],
        "limits": [],
        "unknowns": [],
        "review": {
            "status": "draft",
            "reviewer_id": nil,
            "reviewer_assignment_id": nil,
            "reviewer_role": "internal_reviewer",
            "review_scope": [],
            "reviewed_at": "1970-01-01T00:00:00Z",
            "review_version": 1,
            "contract_sha256": zero,
        },
        "acceptance": {
            "status": "pending",
            "window_start": "2026-10-22",
            "window_end": "2026-10-29",
        },
        "delivery": {
            "manifest_id": nil,
            "report_artifact_id": nil,
            "report_version": 1,
            "access_scope": ["workspace_project"],
            "retention_class": "standard_24m",
        },
        "artifact": {
            "report_html_sha256": zero,
            "sop_html_sha256": zero,
            "contract_sha256": zero,
        },
    }

@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession) -> tuple[Workspace, Report, User, User, object]:
    user = User(email="c9@example.test", password_hash="x", name="C9 Owner")
    reviewer = User(
        email="c9-reviewer@example.test", password_hash="x", name="C9 Reviewer"
    )
    session.add_all([user, reviewer])
    await session.flush()
    workspace = Workspace(name="C9", slug="c9-unit", owner_id=user.id)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    await session.flush()
    project = Project(
        workspace_id=workspace.id,
        name="C9",
        domain="osint",
        status="active",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="t1_voc",
        title="C9 报告",
        content="旧版正文不得成为合同来源",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    from data_intelligence_hub.models.report_reviewer_assignment import (
        ReportReviewerAssignment,
    )

    assignment = ReportReviewerAssignment(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        project_id=project.id,
        report_id=report.id,
        artifact_id=None,
        reviewer_user_id=reviewer.id,
        assignment_scope="report_review",
        status="active",
        assigned_by=user.id,
        assigned_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    session.add(assignment)
    await session.flush()
    return workspace, report, user, reviewer, assignment


@pytest.mark.anyio
async def test_draft_is_the_only_mutable_stage(session: AsyncSession) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )

    assert artifact.status == "draft"
    assert artifact.report_id == report.id
    assert artifact.created_by == user.id


@pytest.mark.anyio
async def test_draft_requires_market_quality_for_governed_run(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    run_id = uuid.uuid4()
    session.add(
        Run(
            id=run_id,
            workspace_id=workspace.id,
            project_id=report.project_id,
            status="completed",
            workflow_version_id=uuid.uuid4(),
            market_code="US",
            finished_at=datetime.now(UTC),
        )
    )
    await session.flush()
    calls: list[dict[str, object]] = []

    async def missing_quality(*args, **kwargs):
        calls.append(kwargs)
        raise MarketQualityNotReadyError("run_not_completed")

    monkeypatch.setattr(
        report_publication,
        "ensure_market_quality",
        missing_quality,
    )
    with pytest.raises(ReportQualityNotReadyError):
        await create_draft_artifact(
            session,
            workspace=workspace,
            report=report,
            template_id="t1_voc",
            contract=_contract(),
            created_by=user,
            run_id=run_id,
        )
    assert calls == [{"run_id": run_id, "task_id": uuid.UUID(TASK_ID)}]


@pytest.mark.anyio
async def test_draft_without_run_id_skips_quality_gate(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)

    async def forbidden_quality(*args, **kwargs):
        raise AssertionError("legacy draft must not call quality gate")

    monkeypatch.setattr(
        report_publication,
        "ensure_market_quality",
        forbidden_quality,
    )
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )
    assert artifact.status == "draft"


@pytest.mark.anyio
async def test_publish_requires_approved_review(session: AsyncSession) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )

    with pytest.raises(ReportReviewRequiredError):
        await publish_artifact(
            session,
            workspace=workspace,
            report_id=report.id,
            artifact_id=artifact.id,
            publisher=user,
            expected_contract_sha256=artifact.contract_sha256,
        )


@pytest.mark.anyio
async def test_review_must_bind_the_same_contract_hash(
    session: AsyncSession,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )

    with pytest.raises(ReportContractHashMismatchError):
        await record_review(
            session,
            workspace=workspace,
            report_id=report.id,
            artifact_id=artifact.id,
            reviewer=reviewer,
            assignment=assignment,
            decision="approve",
            review_scope="全量审核",
            notes=None,
            expected_contract_sha256="0" * 64,
        )


@pytest.mark.anyio
async def test_publish_blocks_when_publish_gate_is_not_pass(
    session: AsyncSession,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    payload = _contract()
    payload["gates"] = [
        {**gate, "status": "blocked"} if gate["gate_id"] == "G-Publish" else gate
        for gate in payload["gates"]
    ]
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=payload,
        created_by=user,
    )
    await record_review(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=artifact.id,
        reviewer=reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes=None,
        expected_contract_sha256=artifact.contract_sha256,
    )

    with pytest.raises(ReportPublishGateBlockedError):
        await publish_artifact(
            session,
            workspace=workspace,
            report_id=report.id,
            artifact_id=artifact.id,
            publisher=user,
            expected_contract_sha256=artifact.contract_sha256,
        )


@pytest.mark.anyio
async def test_publish_reads_contract_json_and_supersedes_previous(
    session: AsyncSession,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    first = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )
    await record_review(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=first.id,
        reviewer=reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes="首版通过",
        expected_contract_sha256=first.contract_sha256,
    )
    published = await publish_artifact(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=first.id,
        publisher=user,
        expected_contract_sha256=first.contract_sha256,
    )

    second = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
        supersedes_id=published.id,
    )
    await record_review(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=second.id,
        reviewer=reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes="修订通过",
        expected_contract_sha256=second.contract_sha256,
    )
    revised = await publish_artifact(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=second.id,
        publisher=user,
        expected_contract_sha256=second.contract_sha256,
    )

    old = await session.get(ReportArtifact, published.id)
    assert revised.status == "published"
    assert old is not None
    assert old.status == "superseded"
    assert old.superseded_at is not None

    _, payload = await get_current_contract(
        session,
        workspace=workspace,
        report_id=report.id,
    )
    assert payload == revised.contract_json
    assert payload["decision"]["answer"] == _contract()["decision"]["answer"]

    revisions = await list_revisions(
        session,
        workspace=workspace,
        report_id=report.id,
    )
    assert [row.id for row in revisions] == [revised.id, published.id]


@pytest.mark.anyio
async def test_current_contract_requires_published_artifact(
    session: AsyncSession,
) -> None:
    workspace, report, user, reviewer, assignment = await _seed(session)
    await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )

    with pytest.raises(ReportContractNotPublishedError):
        await get_current_contract(
            session,
            workspace=workspace,
            report_id=report.id,
        )
```

- [ ] **Step 1A: 写 PII 门禁测试**

Create `apps/api/tests/unit/test_report_pii_gate.py`。测试用假的 `scan_export_policy` 固定命中集合，只验证 C9 的扫描范围、阻断、审计与不回传原始值；C11 正则细节由 `test_export_policy.py` 负责：

```python
"""C9：发布前 C11 导出策略 PII 门禁。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.services.report_publication as report_publication
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.exceptions import ReportPublishGateBlockedError
from data_intelligence_hub.services.export_policy import PiiHit
from data_intelligence_hub.services.report_publication import (
    create_draft_artifact,
    publish_artifact,
    scan_contract_pii,
)

PiiKind = Literal["contact", "profile_link", "avatar", "tracking"]


def _contract(*, answer: str = "先验证。") -> dict[str, Any]:
    task_id = "11111111-1111-1111-1111-111111111111"
    nil = "00000000-0000-0000-0000-000000000000"
    zero = "0" * 64
    return {
        "schema_version": "1.1.0",
        "contract_id": "22222222-2222-2222-2222-222222222222",
        "task_id": task_id,
        "order_id": task_id,
        "template_id": "t1_voc",
        "template_version": "1.0.0",
        "report_version": 1,
        "generated_at": "2026-10-22T00:00:00Z",
        "identity": {
            "task_id": task_id,
            "brand": "Example",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
        },
        "decision": {
            "decision_question": "是否进入？",
            "answer": answer,
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [{"gate_id": "G-Publish", "status": "pass"}],
        "coverage": {"cells": []},
        "markets": [],
        "metrics": [],
        "claims": [],
        "evidences": [],
        "sku_candidates": [],
        "datasets": [],
        "scorecard": {
            "markets": [],
            "minimum_evidence_grade": "L1_contract",
            "claims": {
                "total": 0,
                "by_status": {},
                "by_grade": {},
                "independent_source_count": 0,
            },
        },
        "rights": {"sources": []},
        "currency": {
            "base_currency": "USD",
            "quote_currency": "USD",
            "rate": 1.0,
            "rate_date": "2026-10-22",
            "source": "fixture",
        },
        "language": {
            "primary_language": "zh-CN",
            "executive_summary_language": "en",
            "translation_method": "deterministic_template",
        },
        "run_ledger": [],
        "limits": [],
        "unknowns": [],
        "review": {
            "status": "draft",
            "reviewer_id": nil,
            "reviewer_assignment_id": nil,
            "reviewer_role": "internal_reviewer",
            "review_scope": [],
            "reviewed_at": "1970-01-01T00:00:00Z",
            "review_version": 1,
            "contract_sha256": zero,
        },
        "acceptance": {
            "status": "pending",
            "window_start": "2026-10-22",
            "window_end": "2026-10-29",
        },
        "delivery": {
            "manifest_id": nil,
            "report_artifact_id": nil,
            "report_version": 1,
            "access_scope": ["workspace_project"],
            "retention_class": "standard_24m",
        },
        "artifact": {
            "report_html_sha256": zero,
            "sop_html_sha256": zero,
            "contract_sha256": zero,
        },
    }


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession) -> tuple[Workspace, Report, User]:
    user = User(email="pii@example.test", password_hash="x", name="PII Owner")
    session.add(user)
    await session.flush()
    workspace = Workspace(name="PII", slug="pii-unit", owner_id=user.id)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    await session.flush()
    project = Project(
        workspace_id=workspace.id,
        name="PII",
        domain="osint",
        status="active",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="t1_voc",
        title="PII 报告",
        content="",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    return workspace, report, user


def _fake_scanner(hits_by_text: dict[str, "PiiKind"]):
    """按命中文本返回固定 kind；不复制 C11 正则。"""

    def scan(text: str, *, field_path: str) -> tuple[PiiHit, ...]:
        for needle, kind in hits_by_text.items():
            index = text.find(needle)
            if index >= 0:
                return (
                    PiiHit(
                        kind=kind,
                        field_path=field_path,
                        start=index,
                        end=index + len(needle),
                    ),
                )
        return ()

    return scan


def test_scan_covers_contract_claims_evidence_and_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _contract(answer="联系 alice@example.com")
    payload["claims"] = [
        {
            "claim_id": "33333333-3333-3333-3333-333333333333",
            "text": "主页 https://www.tiktok.com/@alice",
            "text_en": "Profile link",
            "claim_status": "directional",
            "evidence_grade": "L3_live_single",
            "scope": {
                "market": "US",
                "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
                "sample_n": 100,
            },
            "counterevidence_text": "未发现反证",
            "owner": "44444444-4444-4444-4444-444444444444",
            "evidence_ids": ["55555555-5555-5555-5555-555555555555"],
        }
    ]
    payload["evidences"] = [
        {
            "evidence_id": "55555555-5555-5555-5555-555555555555",
            "claim_id": "33333333-3333-3333-3333-333333333333",
            "role": "support",
            "source_tool_id": "tikhub.products",
            "url": "https://shop.example/p/1?utm_source=x",
            "excerpt": "邮箱 bob@example.com",
            "captured_at": "2026-03-02T00:00:00Z",
            "market": "US",
            "locale": "en-US",
            "evidence_grade": "L3_live_single",
        }
    ]
    scanner = _fake_scanner(
        {
            "alice@example.com": "contact",
            "tiktok.com/@alice": "profile_link",
            "bob@example.com": "contact",
            "utm_source": "tracking",
        }
    )
    monkeypatch.setattr(report_publication, "scan_export_policy", scanner)
    hits = scan_contract_pii(
        payload,
        report_html="<a href='https://www.tiktok.com/@alice'>x</a>",
        sop_html="<p>alice@example.com</p>",
    )
    paths = {hit.field_path for hit in hits}
    assert "decision.answer" in paths
    assert "claims[0].text" in paths
    assert "evidences[0].excerpt" in paths
    assert "evidences[0].url" in paths
    assert "artifact.report_html" in paths
    assert "artifact.sop_html" in paths


def test_scan_is_pure_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        report_publication,
        "scan_export_policy",
        _fake_scanner({"alice@example.com": "contact"}),
    )
    first = scan_contract_pii(_contract(answer="alice@example.com"))
    second = scan_contract_pii(_contract(answer="alice@example.com"))
    assert first == second
    assert [hit.kind for hit in first] == ["contact"]


def test_real_scanner_does_not_flag_uuids_or_timestamps() -> None:
    from data_intelligence_hub.services.export_policy import scan_export_policy

    assert scan_export_policy(
        "11111111-1111-1111-1111-111111111111",
        field_path="contract.task_id",
    ) == ()
    assert scan_export_policy(
        "2026-10-22T00:00:00Z",
        field_path="generated_at",
    ) == ()


@pytest.mark.anyio
async def test_publish_blocks_pii_and_writes_blocked_gate_event(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, report, user = await _seed(session)
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(answer="联系 alice@example.com"),
        created_by=user,
    )
    session.add(
        ReportAuditEvent(
            workspace_id=workspace.id,
            report_id=report.id,
            artifact_id=artifact.id,
            actor_id=user.id,
            event_type="report_review_approved",
            from_status="draft",
            to_status="draft",
            metadata_json="{}",
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    monkeypatch.setattr(
        report_publication,
        "scan_export_policy",
        _fake_scanner({"alice@example.com": "contact"}),
    )

    with pytest.raises(ReportPublishGateBlockedError, match="pii_detected"):
        await publish_artifact(
            session,
            workspace=workspace,
            report_id=report.id,
            artifact_id=artifact.id,
            publisher=user,
            expected_contract_sha256=artifact.contract_sha256,
        )

    stored = await session.get(type(artifact), artifact.id)
    assert stored is not None
    assert stored.status == "draft"
    events = list(
        (
            await session.execute(
                select(ReportAuditEvent).where(
                    ReportAuditEvent.artifact_id == artifact.id
                )
            )
        ).scalars()
    )
    blocked = [e for e in events if e.event_type == "gate_evaluated"]
    assert len(blocked) == 1
    metadata = blocked[0].metadata_json or ""
    assert '"gate_id": "G-Publish"' in metadata
    assert '"gate_status": "blocked"' in metadata
    assert '"reason": "pii_detected"' in metadata
    assert '"export_policy_version": "export_policy.v1"' in metadata
    assert "alice@example.com" not in metadata
    assert all(e.event_type != "report_published" for e in events)


@pytest.mark.anyio
async def test_publish_clean_contract_writes_pass_gate_event(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, report, user = await _seed(session)
    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id="t1_voc",
        contract=_contract(),
        created_by=user,
    )
    session.add(
        ReportAuditEvent(
            workspace_id=workspace.id,
            report_id=report.id,
            artifact_id=artifact.id,
            actor_id=user.id,
            event_type="report_review_approved",
            from_status="draft",
            to_status="draft",
            metadata_json="{}",
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    monkeypatch.setattr(
        report_publication,
        "scan_export_policy",
        lambda text, *, field_path: (),
    )

    published = await publish_artifact(
        session,
        workspace=workspace,
        report_id=report.id,
        artifact_id=artifact.id,
        publisher=user,
        expected_contract_sha256=artifact.contract_sha256,
    )

    assert published.status == "published"
    events = list(
        (
            await session.execute(
                select(ReportAuditEvent).where(
                    ReportAuditEvent.artifact_id == artifact.id
                )
            )
        ).scalars()
    )
    types = [event.event_type for event in events]
    assert types.count("gate_evaluated") == 1
    assert types.count("report_published") == 1
    gate = next(e for e in events if e.event_type == "gate_evaluated")
    assert '"gate_status": "pass"' in (gate.metadata_json or "")
    assert '"reason": "pii_scan_clear"' in (gate.metadata_json or "")
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication.py tests/unit/test_report_pii_gate.py -v
```
Expected: 导入失败，`report_publication` 或 `scan_contract_pii` 不存在。

- [ ] **Step 3: 抽出双页渲染纯函数**

在 `services/report_artifacts.py` 顶部补充导入：
```python
from dataclasses import dataclass

from data_intelligence_hub.schemas.report_contract import Artifact
from data_intelligence_hub.services.report_renderers import (
    render_report_html,
    render_report_html_unhashed,
    render_sop_html,
    render_sop_html_unhashed,
)
```

在 `build_artifact` 前加入：
```python
@dataclass(frozen=True, slots=True)
class RenderedContractPages:
    """一份合同的最终两页与三个哈希。"""

    contract: ReportContract
    report_html: str
    sop_html: str
    report_html_sha256: str
    sop_html_sha256: str
    data_sha256: str


def render_contract_pages(contract: ReportContract) -> RenderedContractPages:
    """从合同渲染两页。

    本函数是纯函数。它不读库、不联网、不调用模型、不读时钟。
    页脚自引用协议见模块 docstring。
    """
    run_ids, evidence_ids = contract_input_ids(contract)
    data_hash = data_sha256(run_ids, evidence_ids)
    render_contract = contract.model_copy(
        update={
            "artifact": Artifact(
                report_html_sha256="",
                sop_html_sha256="",
                contract_sha256=contract_sha256(contract),
            )
        }
    )
    report_unhashed = render_report_html_unhashed(
        render_contract,
        data_hash=data_hash,
    )
    sop_unhashed = render_sop_html_unhashed(
        render_contract,
        data_hash=data_hash,
    )
    report_digest = render_sha256(report_unhashed)
    sop_digest = render_sha256(sop_unhashed)
    report_html = render_report_html(
        render_contract,
        report_hash=report_digest,
        sop_hash=sop_digest,
        data_hash=data_hash,
    )
    sop_html = render_sop_html(
        render_contract,
        report_hash=report_digest,
        sop_hash=sop_digest,
        data_hash=data_hash,
    )
    final = contract.model_copy(
        update={
            "artifact": Artifact(
                report_html_sha256=report_digest,
                sop_html_sha256=sop_digest,
                contract_sha256=contract_sha256(contract),
            )
        }
    )
    return RenderedContractPages(
        contract=final,
        report_html=report_html,
        sop_html=sop_html,
        report_html_sha256=report_digest,
        sop_html_sha256=sop_digest,
        data_sha256=data_hash,
    )
```
把 `render_contract_pages` 与 `RenderedContractPages` 加入 `__all__`。

- [ ] **Step 4: 写异常类**

在 `services/exceptions.py` 的 `ReportNotFoundError` 后加入：
```python
class ReportArtifactNotFoundError(ServiceError):
    message = "report_artifact_not_found"


class ReportArtifactNotDraftError(ServiceError):
    message = "report_artifact_not_draft"


class ReportArtifactIncompleteError(ServiceError):
    message = "report_artifact_incomplete"


class ReportArtifactIntegrityError(ServiceError):
    message = "report_artifact_integrity_failed"


class ReportContractInvalidError(ServiceError):
    message = "report_contract_invalid"


class ReportContractNotPublishedError(ServiceError):
    message = "report_contract_not_published"


class ReportContractHashMismatchError(ServiceError):
    message = "report_contract_hash_mismatch"


class ReportQualityNotReadyError(ServiceError):
    message = "report_quality_not_ready"


class ReportReviewRequiredError(ServiceError):
    message = "report_review_required"


class ReportPublishGateBlockedError(ServiceError):
    message = "report_publish_gate_blocked"


class ReportRevisionTargetInvalidError(ServiceError):
    message = "report_revision_target_invalid"


class ReportPublishForbiddenError(ServiceError):
    message = "report_publish_forbidden"


class ReportForbiddenLanguageError(ServiceError):
    message = "report_forbidden_language"


class ReportReviewerForbiddenError(ServiceError):
    message = "reviewer_assignment_required"
```

- [ ] **Step 5: 写发布服务**

Create `apps/api/src/data_intelligence_hub/services/report_publication.py`:
```python
"""报告产物的草稿、审核、发布与修订。

唯一内容源是 ``report_artifacts.contract_json``。
本模块不重建合同，不查 claim/evidence 表，不调用模型。

发布前必须同时满足：

1. 产物是草稿。
2. 调用方给的 ``contract_sha256`` 与记录一致。
3. 合同的 ``G-Publish`` 门禁为 ``pass``。
4. 该产物最近一次审核事件是 ``report_review_approved``。
5. 审核事件绑定的合同哈希与当前记录一致。
6. 受治理 run 的当前 Claim bundle 与合同快照一致；不一致时抛
   ``claim_bundle_stale``。
7. 合同文本、claims、evidence 摘录与渲染两页没有 C11 PII 命中。命中时写
   ``gate_evaluated`` 阻断事件，产物保持 ``draft``。

发布后：

- 旧版本在同一事务内转 ``superseded``。
- 写入 ``report_published`` 与 ``report_superseded`` 事件。
- ``reports.status`` 更新为 ``generated``，只作列表投影。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.claim import ClaimReviewStatus
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench_task import WorkbenchTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.report_artifacts import (
    create_artifact,
    get_artifact,
    get_artifact_for_update,
    get_current_published,
    list_artifacts,
)
from data_intelligence_hub.repositories.reports import (
    create_report_audit_event,
    get_report,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_member_role
from data_intelligence_hub.services.report_artifacts import (
    RenderedContractPages,
    build_artifact,
    render_contract_pages,
    verify_artifact,
)
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    canonical_json_bytes,
    contract_sha256,
    scan_forbidden_language,
    validate_contract,
)
from data_intelligence_hub.services.exceptions import (
    ReportArtifactIncompleteError,
    ReportArtifactIntegrityError,
    ReportArtifactNotFoundError,
    ReportArtifactNotDraftError,
    ReportContractHashMismatchError,
    ReportContractInvalidError,
    ReportContractNotPublishedError,
    ReportForbiddenLanguageError,
    ReportNotFoundError,
    ReportPublishGateBlockedError,
    ReportQualityNotReadyError,
    ReportReviewRequiredError,
    ReportRevisionTargetInvalidError,
)
from data_intelligence_hub.services.export_policy import (
    EXPORT_POLICY_VERSION,
    PiiHit,
    scan_export_policy,
)
from data_intelligence_hub.services.market_quality import (
    MarketQualityNotReadyError,
    ensure_market_quality,
)
from data_intelligence_hub.services.claim_semantics import validate_claim_semantics
from data_intelligence_hub.services.claims import (
    load_publishable_claim_rows,
    validate_claim_bundle,
)
from data_intelligence_hub.services.report_contract_v1_1 import (
    assert_single_task_id,
    claim_bundle_payload,
)
from data_intelligence_hub.services.report_reviewers import assert_reviewer_eligible
from data_intelligence_hub.services.report_templates import get_template

ReviewDecision = Literal["approve", "reject"]

_EVENT_DRAFT = "report_draft_created"
_EVENT_APPROVED = "report_review_approved"
_EVENT_REJECTED = "report_review_rejected"
_EVENT_PUBLISHED = "report_published"
_EVENT_SUPERSEDED = "report_superseded"


def _now() -> datetime:
    return datetime.now(UTC)


def _report_title(contract: ReportContract) -> str:
    title = f"{contract.identity.brand} · {contract.decision.decision_question}"
    return title[:300]


def claim_review_digest(contract: ReportContract | Mapping[str, Any]) -> str:
    """C9 唯一的审核 Claim 摘要。

    C10 只 import 本函数，不定义第二套 payload。载荷只取
    ``report_artifacts.contract_json`` 中的 claims 与 evidences。
    """
    payload = (
        contract.model_dump(mode="json")
        if isinstance(contract, ReportContract)
        else dict(contract)
    )
    claims: list[dict[str, Any]] = []
    for claim in payload.get("claims") or []:
        scope = claim.get("scope") or {}
        window = scope.get("window") or {}
        claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "text": claim.get("text"),
                "claim_status": claim.get("claim_status"),
                "evidence_grade": claim.get("evidence_grade"),
                "scope": {
                    "market": scope.get("market"),
                    "window": {
                        "start": window.get("start"),
                        "end": window.get("end"),
                        "days": window.get("days"),
                    },
                    "sample_n": scope.get("sample_n"),
                },
                "counterevidence_text": claim.get("counterevidence_text"),
                "owner": claim.get("owner"),
                "evidence_ids": sorted(claim.get("evidence_ids") or []),
            }
        )
    claims.sort(key=lambda item: str(item["claim_id"]))
    evidences: list[dict[str, Any]] = []
    for evidence in payload.get("evidences") or []:
        evidences.append(
            {
                "evidence_id": evidence.get("evidence_id"),
                "claim_id": evidence.get("claim_id"),
                "role": evidence.get("role"),
                "source_tool_id": evidence.get("source_tool_id"),
                "url": evidence.get("url"),
                "captured_at": evidence.get("captured_at"),
                "market": evidence.get("market"),
                "locale": evidence.get("locale"),
                "evidence_grade": evidence.get("evidence_grade"),
            }
        )
    evidences.sort(key=lambda item: str(item["evidence_id"]))
    return hashlib.sha256(
        canonical_json_bytes({"claims": claims, "evidences": evidences})
    ).hexdigest()


def _create_report_row(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    template_id: str,
    contract: ReportContract,
) -> Report:
    window = contract.identity.window
    return Report(
        workspace_id=workspace_id,
        project_id=project_id,
        report_type=template_id,
        title=_report_title(contract),
        content="",
        status="draft",
        period_start=datetime.combine(window.start, time.min, tzinfo=UTC),
        period_end=datetime.combine(window.end, time.max, tzinfo=UTC),
    )


async def _record_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID | None,
    artifact_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    metadata: Mapping[str, str],
) -> ReportAuditEvent:
    event = ReportAuditEvent(
        workspace_id=workspace_id,
        report_id=report_id,
        artifact_id=artifact_id,
        actor_id=actor_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        metadata_json=json.dumps(
            dict(metadata),
            ensure_ascii=False,
            sort_keys=True,
        ),
        created_at=_now(),
    )
    return await create_report_audit_event(session, event)


async def _get_report_or_raise(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> Report:
    report = await get_report(session, workspace_id, report_id)
    if report is None:
        raise ReportNotFoundError
    return report


async def _latest_review_decision(
    session: AsyncSession,
    *,
    artifact_id: uuid.UUID,
) -> ReviewDecision | None:
    result = await session.execute(
        select(ReportAuditEvent.event_type)
        .where(
            ReportAuditEvent.artifact_id == artifact_id,
            ReportAuditEvent.event_type.in_((_EVENT_APPROVED, _EVENT_REJECTED)),
        )
        .order_by(ReportAuditEvent.created_at.desc(), ReportAuditEvent.id.desc())
        .limit(1)
    )
    event_type = result.scalar_one_or_none()
    if event_type == _EVENT_APPROVED:
        return "approve"
    if event_type == _EVENT_REJECTED:
        return "reject"
    return None


def _assert_contract_hash(artifact: ReportArtifact, expected: str) -> None:
    actual = contract_sha256(artifact.contract_json)
    if actual != artifact.contract_sha256 or actual != expected:
        raise ReportContractHashMismatchError


def _assert_publish_gate(contract: ReportContract) -> None:
    gate = next(
        (item for item in contract.gates if item.gate_id == "G-Publish"),
        None,
    )
    if gate is None or gate.status != "pass":
        raise ReportPublishGateBlockedError


def _pii_text_fields(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    """列出发布前必须扫描的合同文本字段。

    只扫描用户可见文本与 evidence 摘录、URL。品牌、店铺与商业创作者
    公开身份不扫描。``PiiHit`` 不回传原始值。
    """
    fields: list[tuple[str, str]] = []

    def add(path: str, value: object) -> None:
        if isinstance(value, str) and value.strip():
            fields.append((path, value))

    def add_list(path: str, value: object) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                add(f"{path}[{index}]", item)

    decision = payload.get("decision")
    if isinstance(decision, Mapping):
        add("decision.answer", decision.get("answer"))
        for key in ("protect", "resolve", "prove"):
            add_list(f"decision.{key}", decision.get(key))
    add_list("limits", payload.get("limits"))
    add_list("unknowns", payload.get("unknowns"))
    claims = payload.get("claims")
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            if isinstance(claim, Mapping):
                for key in ("text", "text_en", "counterevidence_text"):
                    add(f"claims[{index}].{key}", claim.get(key))
    evidences = payload.get("evidences")
    if isinstance(evidences, list):
        for index, evidence in enumerate(evidences):
            if isinstance(evidence, Mapping):
                for key in ("excerpt", "url"):
                    add(f"evidences[{index}].{key}", evidence.get(key))
    markets = payload.get("markets")
    if isinstance(markets, list):
        for market_index, market in enumerate(markets):
            if not isinstance(market, Mapping):
                continue
            gaps = market.get("gaps")
            if not isinstance(gaps, list):
                continue
            for gap_index, gap in enumerate(gaps):
                if isinstance(gap, Mapping):
                    for key in (
                        "impact",
                        "customer_text_zh",
                        "customer_text_en",
                        "remediation",
                    ):
                        add(
                            f"markets[{market_index}].gaps[{gap_index}].{key}",
                            gap.get(key),
                        )
    metrics = payload.get("metrics")
    if isinstance(metrics, list):
        for index, metric in enumerate(metrics):
            if isinstance(metric, Mapping):
                for key in ("label", "note"):
                    add(f"metrics[{index}].{key}", metric.get(key))
    return fields


def scan_contract_pii(
    contract: ReportContract | Mapping[str, Any],
    *,
    report_html: str = "",
    sop_html: str = "",
) -> list[PiiHit]:
    """用 C11 导出策略扫描合同与两页。

    纯函数：不读库、不写库、不读时钟、不改写文本。
    命中项只含 kind、field_path 与偏移，不含原始 PII 值。
    """
    payload = (
        contract.model_dump(mode="json")
        if isinstance(contract, ReportContract)
        else dict(contract)
    )
    hits: list[PiiHit] = []
    for field_path, text in _pii_text_fields(payload):
        hits.extend(scan_export_policy(text, field_path=field_path))
    if report_html:
        hits.extend(scan_export_policy(report_html, field_path="artifact.report_html"))
    if sop_html:
        hits.extend(scan_export_policy(sop_html, field_path="artifact.sop_html"))
    return hits


async def _assert_publishable_claim_bundle(
    session: AsyncSession,
    *,
    workspace: Workspace,
    artifact: ReportArtifact,
    contract: ReportContract,
) -> None:
    """发布前用内部 bundle 复核 Claim，不只读公开计数。

    ``run_id`` 为空或 legacy run（``workflow_version_id`` 为空）跳过；
    这是历史/手工报告路径。未跳过时缺任务单直接阻断。
    """
    if artifact.run_id is None:
        return
    run = await session.get(Run, artifact.run_id)
    if run is None or run.workflow_version_id is None:
        return
    task = await session.get(WorkbenchTask, contract.task_id)
    if task is None or task.project_id is None:
        raise ReportPublishGateBlockedError("task_not_found")
    bundle = await load_publishable_claim_rows(
        session,
        workspace_id=workspace.id,
        project_id=task.project_id,
        task_id=contract.task_id,
    )
    for claim in bundle.claims:
        if claim.review_status is not ClaimReviewStatus.APPROVED:
            raise ReportPublishGateBlockedError(
                f"claim_not_approved: {claim.claim_id}"
            )
    issues = validate_claim_bundle(bundle)
    if issues:
        raise ReportPublishGateBlockedError("；".join(issues))
    semantic = validate_claim_semantics(
        bundle,
        markets=[item.model_dump(mode="json") for item in contract.markets],
        package_type=task.package_type,
    )
    if semantic:
        raise ReportPublishGateBlockedError("；".join(semantic))
    if claim_review_digest(claim_bundle_payload(bundle)) != claim_review_digest(
        artifact.contract_json
    ):
        raise ReportPublishGateBlockedError("claim_bundle_stale")


async def create_draft_artifact(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report: Report | None,
    template_id: str,
    contract: Mapping[str, Any],
    created_by: User | None,
    project_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    supersedes_id: uuid.UUID | None = None,
    version: str = "1.0.0",
) -> ReportArtifact:
    """创建一份草稿产物。

    ``report`` 为空时按合同新建 ``reports`` 行。
    合同必须覆盖全部组。缺组时抛 ``ReportContractInvalidError``。
    """
    try:
        get_template(template_id)
    except KeyError as exc:
        raise ReportContractInvalidError(
            f"template_not_registered: {template_id}"
        ) from exc

    task_id_value = assert_single_task_id(contract)

    if run_id is not None:
        run_row = await session.get(Run, run_id)
        if run_row is not None and run_row.workflow_version_id is not None:
            try:
                await ensure_market_quality(
                    session,
                    run_id=run_id,
                    task_id=task_id_value,
                )
            except MarketQualityNotReadyError as exc:
                raise ReportQualityNotReadyError(str(exc)) from exc

    try:
        parsed = ReportContract.model_validate(contract)
    except (KeyError, TypeError, ValidationError) as exc:
        raise ReportContractInvalidError(
            f"report_contract_incomplete: {exc}"
        ) from exc

    if report is None:
        report = _create_report_row(
            workspace_id=workspace.id,
            project_id=project_id,
            template_id=template_id,
            contract=parsed,
        )
        session.add(report)
        await session.flush()
    elif report.workspace_id != workspace.id:
        raise ReportNotFoundError

    if supersedes_id is not None:
        previous = await get_artifact(
            session,
            workspace_id=workspace.id,
            artifact_id=supersedes_id,
        )
        if (
            previous is None
            or previous.report_id != report.id
            or previous.status != "published"
        ):
            raise ReportRevisionTargetInvalidError

    target_project_id = project_id if project_id is not None else report.project_id
    if target_project_id is None:
        raise ReportContractInvalidError("project_id_required")

    rendered = render_contract_pages(parsed)
    built = build_artifact(
        workspace_id=workspace.id,
        project_id=target_project_id,
        template_id=template_id,
        contract=rendered.contract,
        report_html=rendered.report_html,
        sop_html=rendered.sop_html,
        run_id=run_id,
        report_id=report.id,
        version=version,
    )
    row = await create_artifact(
        session,
        workspace_id=built.workspace_id,
        project_id=built.project_id,
        run_id=built.run_id,
        report_id=built.report_id,
        template_id=built.template_id,
        contract_json=built.contract_json,
        contract_sha256=built.contract_sha256,
        data_sha256=built.data_sha256,
        report_html_sha256=built.report_html_sha256,
        sop_html_sha256=built.sop_html_sha256,
        combined_sha256=built.combined_sha256,
        version=built.version,
        report_html=built.report_html,
        sop_html=built.sop_html,
        status="draft",
        created_by=created_by.id if created_by is not None else None,
        supersedes_id=supersedes_id,
    )
    await _record_event(
        session,
        workspace_id=workspace.id,
        report_id=report.id,
        artifact_id=row.id,
        actor_id=created_by.id if created_by is not None else None,
        event_type=_EVENT_DRAFT,
        from_status=None,
        to_status="draft",
        metadata={
            "contract_sha256": row.contract_sha256,
            "template_id": template_id,
            "supersedes_id": str(supersedes_id) if supersedes_id else "",
        },
    )
    await session.commit()
    await session.refresh(row)
    return row


async def record_review(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
    artifact_id: uuid.UUID,
    reviewer: User,
    assignment: ReportReviewerAssignment,
    decision: ReviewDecision,
    review_scope: str,
    notes: str | None,
    expected_contract_sha256: str,
) -> ReportAuditEvent:
    """写入一条人工审核事件。只认内部审核人的 active assignment。"""
    report = await _get_report_or_raise(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )
    artifact = await get_artifact(
        session,
        workspace_id=workspace.id,
        artifact_id=artifact_id,
    )
    if artifact is None or artifact.report_id != report.id:
        raise ReportArtifactNotFoundError
    if artifact.status != "draft":
        raise ReportArtifactNotDraftError
    _assert_contract_hash(artifact, expected_contract_sha256)
    scope = review_scope.strip()
    if not scope:
        raise ReportContractInvalidError("review_scope_required")
    await assert_reviewer_eligible(
        session,
        workspace=workspace,
        report=report,
        reviewer_user_id=reviewer.id,
        required_scope="report_review",
        assignment=assignment,
        artifact_created_by=artifact.created_by,
    )

    event = await _record_event(
        session,
        workspace_id=workspace.id,
        report_id=report.id,
        artifact_id=artifact.id,
        actor_id=reviewer.id,
        event_type=_EVENT_APPROVED if decision == "approve" else _EVENT_REJECTED,
        from_status=artifact.status,
        to_status=artifact.status,
        metadata={
            "contract_sha256": artifact.contract_sha256,
            "review_scope": scope,
            "notes": notes or "",
            "reviewer_role": "internal_reviewer",
            "reviewer_assignment_id": str(assignment.id),
            "reviewed_contract_sha256": artifact.contract_sha256,
            "reviewed_data_sha256": artifact.data_sha256,
            "reviewed_report_html_sha256": artifact.report_html_sha256,
            "reviewed_sop_html_sha256": artifact.sop_html_sha256,
            "reviewed_claim_digest": claim_review_digest(artifact.contract_json),
        },
    )
    await session.commit()
    await session.refresh(event)
    return event


async def _reviewed_ancestor(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact: ReportArtifact,
) -> ReportArtifact | None:
    current = artifact
    seen: set[uuid.UUID] = set()
    while current.supersedes_id is not None and current.supersedes_id not in seen:
        seen.add(current.id)
        parent = await get_artifact(
            session, workspace_id=workspace_id, artifact_id=current.supersedes_id
        )
        if parent is None:
            return None
        if (
            parent.status in {"published", "superseded"}
            and await _latest_review_decision(session, artifact_id=parent.id)
            == "approve"
        ):
            return parent
        current = parent
    return None


def _assert_inherited_review(
    artifact: ReportArtifact,
    ancestor: ReportArtifact,
) -> None:
    from data_intelligence_hub.services.report_contract_v1_1 import (
        content_contract_sha256,
    )

    contract = ReportContract.model_validate(artifact.contract_json)
    parent = ReportContract.model_validate(ancestor.contract_json)
    if contract.review.status != "approved":
        raise ReportReviewRequiredError
    if contract.review.contract_sha256 != ancestor.contract_sha256:
        raise ReportReviewRequiredError
    if content_contract_sha256(contract) != content_contract_sha256(parent):
        raise ReportReviewRequiredError


async def publish_artifact(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
    artifact_id: uuid.UUID,
    publisher: User,
    expected_contract_sha256: str,
    allow_inherited_review: bool = False,
) -> ReportArtifact:
    """发布草稿。重复发布同一哈希时幂等返回。"""
    report = await _get_report_or_raise(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )
    artifact = await get_artifact_for_update(
        session,
        workspace_id=workspace.id,
        artifact_id=artifact_id,
    )
    if artifact is None or artifact.report_id != report.id:
        raise ReportArtifactNotFoundError
    _assert_contract_hash(artifact, expected_contract_sha256)

    if artifact.status == "published":
        return artifact
    if artifact.status != "draft":
        raise ReportArtifactNotDraftError

    try:
        contract = ReportContract.model_validate(artifact.contract_json)
    except ValidationError as exc:
        raise ReportContractInvalidError(str(exc)) from exc
    issues = validate_contract(contract)
    if issues:
        raise ReportContractInvalidError("；".join(issues))
    forbidden = scan_forbidden_language(contract.model_dump(mode="json"))
    if forbidden:
        raise ReportForbiddenLanguageError(
            "；".join(f"{hit.field_path}:{hit.term}" for hit in forbidden)
        )
    pii_hits = scan_contract_pii(
        contract,
        report_html=artifact.report_html or "",
        sop_html=artifact.sop_html or "",
    )
    if pii_hits:
        await _record_event(
            session,
            workspace_id=workspace.id,
            report_id=report.id,
            artifact_id=artifact.id,
            actor_id=publisher.id,
            event_type="gate_evaluated",
            from_status=artifact.status,
            to_status=artifact.status,
            metadata={
                "gate_id": "G-Publish",
                "gate_status": "blocked",
                "reason": "pii_detected",
                "export_policy_version": EXPORT_POLICY_VERSION,
                "pii_kinds": ",".join(sorted({hit.kind for hit in pii_hits})),
                "pii_field_paths": ",".join(
                    sorted({hit.field_path for hit in pii_hits})
                ),
                "contract_sha256": artifact.contract_sha256,
            },
        )
        await session.commit()
        raise ReportPublishGateBlockedError(
            "pii_detected: "
            + "；".join(
                sorted({f"{hit.field_path}:{hit.kind}" for hit in pii_hits})
            )
        )
    _assert_publish_gate(contract)

    decision = await _latest_review_decision(session, artifact_id=artifact.id)
    if decision is None and allow_inherited_review:
        ancestor = await _reviewed_ancestor(
            session, workspace_id=workspace.id, artifact=artifact
        )
        if ancestor is not None:
            _assert_inherited_review(artifact, ancestor)
            decision = "approve"
    if decision != "approve":
        raise ReportReviewRequiredError

    await _assert_publishable_claim_bundle(
        session,
        workspace=workspace,
        artifact=artifact,
        contract=contract,
    )

    await _record_event(
        session,
        workspace_id=workspace.id,
        report_id=report.id,
        artifact_id=artifact.id,
        actor_id=publisher.id,
        event_type="gate_evaluated",
        from_status=artifact.status,
        to_status=artifact.status,
        metadata={
            "gate_id": "G-Publish",
            "gate_status": "pass",
            "reason": "pii_scan_clear",
            "export_policy_version": EXPORT_POLICY_VERSION,
            "pii_hit_count": "0",
            "contract_sha256": artifact.contract_sha256,
        },
    )

    now = _now()
    if artifact.supersedes_id is not None:
        previous = await get_artifact_for_update(
            session,
            workspace_id=workspace.id,
            artifact_id=artifact.supersedes_id,
        )
        if (
            previous is None
            or previous.report_id != report.id
            or previous.status not in {"published", "superseded"}
        ):
            raise ReportRevisionTargetInvalidError
        if previous.status == "published":
            from_status = previous.status
            previous.status = "superseded"
            previous.superseded_at = now
            await session.flush()
            await _record_event(
                session,
                workspace_id=workspace.id,
                report_id=report.id,
                artifact_id=previous.id,
                actor_id=publisher.id,
                event_type=_EVENT_SUPERSEDED,
                from_status=from_status,
                to_status="superseded",
                metadata={
                    "contract_sha256": previous.contract_sha256,
                    "superseded_by": str(artifact.id),
                },
            )

    artifact.status = "published"
    artifact.published_at = now
    artifact.published_by = publisher.id
    report.status = "generated"
    await session.flush()
    await _record_event(
        session,
        workspace_id=workspace.id,
        report_id=report.id,
        artifact_id=artifact.id,
        actor_id=publisher.id,
        event_type=_EVENT_PUBLISHED,
        from_status="draft",
        to_status="published",
        metadata={"contract_sha256": artifact.contract_sha256},
    )
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def get_current_contract(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> tuple[ReportArtifact, dict[str, Any]]:
    """返回当前已发布合同。只读 ``contract_json``。"""
    await _get_report_or_raise(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )
    artifact = await get_current_published(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )
    if artifact is None:
        raise ReportContractNotPublishedError
    _assert_contract_hash(artifact, artifact.contract_sha256)
    return artifact, dict(artifact.contract_json)


async def get_readable_artifact(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> ReportArtifact:
    """返回当前已发布产物，并复核五个哈希。"""
    artifact, _ = await get_current_contract(
        session,
        workspace=workspace,
        report_id=report_id,
    )
    if artifact.report_html is None or artifact.sop_html is None:
        raise ReportArtifactIncompleteError
    mismatches = verify_artifact(
        artifact,
        artifact.contract_json,
        artifact.report_html,
        artifact.sop_html,
    )
    if mismatches:
        raise ReportArtifactIntegrityError("；".join(mismatches))
    return artifact


async def list_revisions(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> list[ReportArtifact]:
    """按创建时间倒序返回修订链。"""
    await _get_report_or_raise(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )
    return await list_artifacts(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
    )


__all__ = [
    "RenderedContractPages",
    "claim_review_digest",
    "create_draft_artifact",
    "get_current_contract",
    "get_readable_artifact",
    "list_revisions",
    "publish_artifact",
    "record_review",
    "render_contract_pages",
    "scan_contract_pii",
]
```
注意：`RenderedContractPages`、`render_contract_pages` 从 `report_artifacts` 导入并重新导出。

- [ ] **Step 6: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_publication.py tests/unit/test_report_pii_gate.py -v
```
Expected: `8 passed`（生命周期）与 `5 passed`（PII 门禁）。

- [ ] **Step 7: 静态检查**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run ruff check src/data_intelligence_hub/services/report_publication.py \
  src/data_intelligence_hub/services/report_artifacts.py \
  src/data_intelligence_hub/services/exceptions.py \
  tests/unit/test_report_publication.py \
  tests/unit/test_report_pii_gate.py
uv run mypy src/data_intelligence_hub/services/report_publication.py
```
Expected: ruff 无输出；mypy `Success`。

- [ ] **Step 8: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "build_artifact" --direction upstream --repo .
node .gitnexus/run.cjs impact "verify_artifact" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/report_publication.py \
  apps/api/src/data_intelligence_hub/services/report_artifacts.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/tests/unit/test_report_publication.py \
  apps/api/tests/unit/test_report_pii_gate.py
git commit -m "feat(report): 报告草稿、审核、发布、修订与 PII 门禁"
```
Expected: impact 列出 `build_artifact` 与 `verify_artifact` 的调用方；`detect-changes` 无 `partial` 或 `truncated`；提交成功。

---

### Task 4A: 1.1 装配器、C7/C8 语义映射、Quick 方向稿与不可变生命周期

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/report_contract_v1_1.py`
- Create: `apps/api/src/data_intelligence_hub/services/report_reviewers.py`
- Create: `apps/api/tests/unit/test_report_contract_v1_1.py`
- Create: `apps/api/tests/unit/test_report_quick_directional.py`
- Create: `apps/api/tests/unit/test_report_reviewers.py`

**Interfaces:**
- Consumes: C8 的 `MarketAssessment`、`DataGap`、`DatasetVersion`、`validate_conclusion()`、`ConclusionInputs`、`SkuCandidate`、`PackageTier`；C7 的 `load_publishable_claim_rows()`、`validate_claim_bundle()`、`ClaimContractBundle`、`ClaimContractRow`、`EvidenceContractRow`、`market_independent_cluster_count()`、`validate_claim_semantics()`；C4 的 `WorkbenchTask`；C1 的 `ReportContract` 1.1、`SCHEMA_VERSION`、`Gate`、`scan_forbidden_language()`；B5 的 `render_contract_pages`、`build_artifact`。
- Produces:
  - `ASSEMBLED_TOP_LEVEL_KEYS: tuple[str, ...]`：C1 的 29 个必填顶层键。
  - `assert_single_task_id(contract: Mapping[str, Any]) -> uuid.UUID`
  - `content_contract_sha256(contract: ReportContract | Mapping[str, Any]) -> str`
  - `assemble_report_contract_v1_1(session, *, workspace_id, task, run_id, template_id, generated_at, report_version=1, supersedes_id=None, requested_conclusions=None, sku_candidates=(), test_budget_usd=None, observation_window_days=None, success_threshold=None, stop_loss=None) -> ReportContract`
  - `QuickDirectionalDraft(artifact: ReportArtifact, contract: ReportContract)`
  - `create_quick_directional_artifact(session, *, workspace, report, task, run_id, template_id, generated_at, created_by) -> QuickDirectionalDraft`
  - `ReviewedVersion(artifact: ReportArtifact, event: ReportAuditEvent)`
  - `create_reviewed_contract_version(...) -> ReviewedVersion`
  - `create_delivery_contract_version(...) -> ReportArtifact`
  - `request_reviewer_assignment(session, *, workspace, report, reviewer_user_id, assignment_scope, assigned_by, now, expires_at) -> ReportReviewerAssignment`
  - `assert_reviewer_eligible(session, *, workspace, report, reviewer_user_id, required_scope="report_review", assignment=None, artifact_created_by=None, now=None) -> ReportReviewerAssignment`

- [ ] **Step 1: 写装配器与三档质量失败测试**

Create `apps/api/tests/unit/test_report_contract_v1_1.py`。测试夹具只种 C8 事实，不复制合同模型：

```python
"""C9：装配器从 C8 事实生成唯一 1.1 合同。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import data_intelligence_hub.services.report_contract_v1_1 as report_contract_v1_1
import data_intelligence_hub.services.report_publication as report_publication
from data_intelligence_hub.models.claim import (
    ClaimReviewStatus,
    ClaimState,
    EvidenceRole,
)
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workbench_task import WorkbenchTask
from data_intelligence_hub.services.claims import (
    ClaimContractBundle,
    ClaimContractRow,
    ClaimScopeRow,
    EvidenceContractRow,
    validate_claim_bundle,
)
from data_intelligence_hub.services.exceptions import (
    ReportContractInvalidError,
    ReportPublishGateBlockedError,
)
from data_intelligence_hub.services.report_contract_v1_1 import (
    ASSEMBLED_TOP_LEVEL_KEYS,
    assemble_report_contract_v1_1,
    assert_single_task_id,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade

TASK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
WORKSPACE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
RUN_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
GAP_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
VERSION_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
USER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


async def _seed_quality(
    session: AsyncSession, *, quality_status: str, gap_severity: str | None
) -> WorkbenchTask:
    task = WorkbenchTask(
        id=TASK_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        owner_id=USER_ID,
        brand="Example",
        category="baby_bottle",
        competitors=[],
        package_type="standard",
        primary_market="US",
        comparison_markets=["DE"],
        markets=["US", "DE"],
        locale_by_market={"US": "en-US", "DE": "de-DE"},
        window_start=date(2026, 1, 1),
        window_end=date(2026, 3, 1),
        decision_question="Should we enter?",
        does_not_answer=[],
        status="submitted",
    )
    session.add(task)
    await session.flush()
    session.add_all(
        [
            MarketAssessment(
                id=uuid.uuid4(),
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                market="US",
                market_role="primary",
                quality_status=quality_status,
                conclusion_standard="conditional_enter",
                evidence_grade="L3_live_single",
                core_domain_coverage={"products": "pass", "reviews": "partial"},
                sample_counts={"products": 120, "reviews": 30},
                thresholds={"products": 50, "reviews": 20},
                gap_ids=[str(GAP_ID)] if gap_severity else [],
                details_json={
                    "domains": [
                        {"data_domain": "products", "status": "pass", "record_count": 120, "threshold": 50},
                        {"data_domain": "reviews", "status": "partial", "record_count": 30, "threshold": 20},
                    ]
                },
                computed_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
            MarketAssessment(
                id=uuid.uuid4(),
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                market="DE",
                market_role="compare",
                quality_status=quality_status,
                evidence_grade="L3_live_single",
                core_domain_coverage={"products": "pass"},
                sample_counts={"products": 80},
                thresholds={"products": 50},
                gap_ids=[],
                details_json={
                    "domains": [
                        {"data_domain": "products", "status": "pass", "record_count": 80, "threshold": 50}
                    ]
                },
                computed_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
        ]
    )
    if gap_severity:
        session.add(
            DataGap(
                id=GAP_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                run_id=RUN_ID,
                step_id=None,
                market="US",
                data_domain="reviews",
                reason_code="sample_below_threshold",
                actual_value=30,
                threshold_value=50,
                impact="Review conclusions are directional only.",
                customer_text_zh="评论样本低于门槛。",
                customer_text_en="Review sample is below the threshold.",
                remediation="Collect more reviews.",
                severity=gap_severity,
                status="open",
                created_at=datetime(2026, 3, 2, tzinfo=UTC),
            )
        )
    session.add(
        DatasetVersion(
            id=VERSION_ID,
            dataset_id=uuid.uuid4(),
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            created_by_user_id=USER_ID,
            version_number=1,
            task_id=TASK_ID,
            market="US",
            source_task_run_ids=[str(RUN_ID)],
            selected_fields=["title"],
            cleaning_script=[],
            rows=[{"title": "a"}],
            export_preview={},
            row_count=1,
            average_completeness_percent=100,
            status="saved",
            content_sha256="a" * 64,
            schema_hash="b" * 64,
            quality_status=quality_status,
            created_at=datetime(2026, 3, 2, tzinfo=UTC),
        )
    )
    await session.flush()
    return task


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("quality_status", "gap_severity"),
    [
        ("qualified", None),
        ("qualified_with_gap", "warning"),
        ("not_qualified", "blocking"),
    ],
)
async def test_assemble_maps_c8_facts_to_markets_datasets_scorecard(
    session: AsyncSession, quality_status: str, gap_severity: str | None
) -> None:
    task = await _seed_quality(
        session, quality_status=quality_status, gap_severity=gap_severity
    )
    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=WORKSPACE_ID,
        task=task,
        run_id=RUN_ID,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
    )
    payload = contract.model_dump(mode="json")
    assert set(payload) - {"supersedes_id"} == set(ASSEMBLED_TOP_LEVEL_KEYS)
    assert contract.task_id == TASK_ID
    assert contract.identity.task_id == TASK_ID
    assert contract.order_id == TASK_ID
    assert [item.quality_status for item in contract.markets] == [
        quality_status,
        quality_status,
    ]
    assert [item.market for item in contract.datasets] == ["US"]
    assert contract.datasets[0].content_sha256 == "a" * 64
    assert contract.datasets[0].quality_status == quality_status
    assert contract.scorecard.minimum_evidence_grade == "L3_live_single"
    assert contract.scorecard.markets[0].market == "US"
    if gap_severity:
        assert contract.markets[0].gaps[0].gap_id == GAP_ID
        assert contract.markets[0].gaps[0].severity == gap_severity
        assert contract.markets[0].gaps[0].customer_text_zh == "评论样本低于门槛。"


def test_top_level_task_id_is_authoritative() -> None:
    base = {
        "task_id": str(TASK_ID),
        "identity": {"task_id": str(TASK_ID)},
    }
    assert assert_single_task_id(base) == TASK_ID
    with pytest.raises(ValueError, match="task_id_mismatch"):
        assert_single_task_id(
            {"task_id": str(TASK_ID), "identity": {"task_id": str(uuid.uuid4())}}
        )


CLAIM_ID_1 = "88888888-8888-8888-8888-888888888888"
CLAIM_ID_2 = "99999999-9999-9999-9999-999999999999"


def _evidence_ids(index: int) -> tuple[str, str]:
    return (
        str(uuid.uuid5(TASK_ID, f"evidence-{index}-a")),
        str(uuid.uuid5(TASK_ID, f"evidence-{index}-b")),
    )


def _claim_row(
    *,
    claim_id: str,
    status: ClaimState = ClaimState.DIRECTIONAL,
    grade: EvidenceGrade = EvidenceGrade.L3_LIVE_SINGLE,
    review_status: ClaimReviewStatus = ClaimReviewStatus.APPROVED,
    independent: int = 2,
    evidence_ids: tuple[str, ...],
) -> ClaimContractRow:
    return ClaimContractRow(
        claim_id=claim_id,
        text="美国市场商品描述性差异。",
        text_en="US product descriptions differ.",
        claim_status=status,
        evidence_grade=grade,
        risk_flags=(),
        review_status=review_status,
        independent_source_count=independent,
        blocked_reason=None,
        scope=ClaimScopeRow(
            market="US",
            window_start=date(2026, 1, 1),
            window_end=date(2026, 3, 1),
            window_days=60,
            sample_n=100,
        ),
        counterevidence_text="未发现反证。",
        owner=USER_ID,
        evidence_ids=evidence_ids,
    )


def _evidence_row(
    *,
    evidence_id: str,
    claim_id: str,
    role: EvidenceRole,
    cluster: str,
    grade: EvidenceGrade = EvidenceGrade.L3_LIVE_SINGLE,
) -> EvidenceContractRow:
    return EvidenceContractRow(
        evidence_id=evidence_id,
        claim_id=claim_id,
        role=role,
        raw_record_id=None,
        source_tool_id="tikhub.products",
        url=f"https://example.com/{evidence_id}",
        excerpt=None,
        captured_at=datetime(2026, 3, 2, tzinfo=UTC),
        market="US",
        locale="en-US",
        evidence_grade=grade,
        source_cluster_key=cluster,
        source_cluster_basis="url",
        independent=True,
    )


def _two_claim_bundle(*, clusters_per_claim: int = 2) -> ClaimContractBundle:
    claims: list[ClaimContractRow] = []
    evidences: list[EvidenceContractRow] = []
    for index, claim_id in enumerate((CLAIM_ID_1, CLAIM_ID_2), start=1):
        evidence_ids = _evidence_ids(index)
        cluster_a = (
            "market:us"
            if clusters_per_claim == 1
            else f"claim-{index}:a"
        )
        cluster_b = f"claim-{index}:b" if clusters_per_claim == 2 else cluster_a
        evidences.extend(
            (
                _evidence_row(
                    evidence_id=evidence_ids[0],
                    claim_id=claim_id,
                    role=EvidenceRole.SUPPORT,
                    cluster=cluster_a,
                ),
                _evidence_row(
                    evidence_id=evidence_ids[1],
                    claim_id=claim_id,
                    role=EvidenceRole.COUNTER,
                    cluster=cluster_b,
                ),
            )
        )
        claims.append(
            _claim_row(
                claim_id=claim_id,
                independent=clusters_per_claim,
                evidence_ids=evidence_ids,
            )
        )
    return ClaimContractBundle(claims=tuple(claims), evidences=tuple(evidences))


def _single_claim_bundle(
    *,
    status: ClaimState = ClaimState.DIRECTIONAL,
    grade: EvidenceGrade = EvidenceGrade.L3_LIVE_SINGLE,
    review_status: ClaimReviewStatus = ClaimReviewStatus.APPROVED,
) -> ClaimContractBundle:
    evidence_ids = _evidence_ids(1)
    return ClaimContractBundle(
        claims=(
            _claim_row(
                claim_id=CLAIM_ID_1,
                status=status,
                grade=grade,
                review_status=review_status,
                evidence_ids=evidence_ids,
            ),
        ),
        evidences=(
            _evidence_row(
                evidence_id=evidence_ids[0],
                claim_id=CLAIM_ID_1,
                role=EvidenceRole.SUPPORT,
                cluster="claim-1:a",
                grade=grade,
            ),
            _evidence_row(
                evidence_id=evidence_ids[1],
                claim_id=CLAIM_ID_1,
                role=EvidenceRole.COUNTER,
                cluster="claim-1:b",
                grade=grade,
            ),
        ),
    )


def _install_bundle(
    monkeypatch: pytest.MonkeyPatch,
    bundle: ClaimContractBundle,
) -> None:
    async def loader(*args, **kwargs):
        assert kwargs["workspace_id"] == WORKSPACE_ID
        assert kwargs["project_id"] == PROJECT_ID
        assert kwargs["task_id"] == TASK_ID
        return bundle

    monkeypatch.setattr(report_contract_v1_1, "load_publishable_claim_rows", loader)


def _sku_rows(count: int) -> list[dict[str, object]]:
    return [
        {
            "market": "US",
            "rank": rank,
            "price_band_local": {"min": 10 + rank, "max": 20 + rank},
            "price_band_usd": {"min": 10 + rank, "max": 20 + rank},
            "evidence_grade": "L3_live_single",
            "risks": [],
            "next_validation": "验证价格带与评价。",
        }
        for rank in range(1, count + 1)
    ]


@pytest.mark.anyio
async def test_assemble_populates_claims_evidences_and_decision(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    bundle = _two_claim_bundle()
    assert validate_claim_bundle(bundle) == []
    _install_bundle(monkeypatch, bundle)

    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=WORKSPACE_ID,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
        requested_conclusions={"US": "enter"},
        sku_candidates=_sku_rows(3),
    )

    assert len(contract.claims) == 2
    assert len(contract.evidences) == 4
    assert contract.claims[0].text_en == "US product descriptions differ."
    assert contract.claims[0].review_status == "approved"
    assert contract.evidences[0].source_tool_id == "tikhub.products"
    assert contract.scorecard.claims.total == 2
    assert contract.scorecard.claims.by_status == {"directional": 2}
    assert contract.scorecard.claims.by_grade == {"L3_live_single": 2}
    assert contract.scorecard.claims.independent_source_count == 4
    assert "enter" in contract.decision.answer
    assert [item.rank for item in contract.sku_candidates] == [1, 2, 3]
    gates = {gate.gate_id: gate.status for gate in contract.gates}
    assert gates["G-Claim"] == "pass"
    assert gates["G-Publish"] == "pending"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "review_status",
    [ClaimReviewStatus.PENDING, ClaimReviewStatus.STALE],
)
async def test_assemble_rejects_pending_or_stale_claims(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    review_status: ClaimReviewStatus,
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    _install_bundle(
        monkeypatch,
        _single_claim_bundle(review_status=review_status),
    )

    with pytest.raises(ReportContractInvalidError, match="claim_not_approved"):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("candidate_count", "allowed"),
    [(2, False), (3, True), (5, True), (6, False)],
)
async def test_standard_enter_requires_three_to_five_candidates(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    candidate_count: int,
    allowed: bool,
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    _install_bundle(monkeypatch, ClaimContractBundle(claims=(), evidences=()))

    if allowed:
        contract = await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "enter"},
            sku_candidates=_sku_rows(candidate_count),
        )
        assert contract.markets[0].conclusion_standard == "enter"
        assert len(contract.sku_candidates) == candidate_count
        return

    with pytest.raises(
        ReportContractInvalidError,
        match="enter_requires_3_to_5_non_provisional_sku_candidates",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "enter"},
            sku_candidates=_sku_rows(candidate_count),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("clusters_per_claim", "allowed"),
    [(2, True), (1, False)],
)
async def test_standard_do_not_enter_requires_two_clusters(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    clusters_per_claim: int,
    allowed: bool,
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    _install_bundle(
        monkeypatch,
        _two_claim_bundle(clusters_per_claim=clusters_per_claim),
    )

    if allowed:
        contract = await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "do_not_enter"},
        )
        assert contract.markets[0].conclusion_standard == "do_not_enter"
        return

    with pytest.raises(
        ReportContractInvalidError,
        match="do_not_enter_requires_two_independent_clusters",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "do_not_enter"},
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "missing_field",
    [
        "test_budget_usd",
        "observation_window_days",
        "success_threshold",
        "stop_loss",
    ],
)
async def test_standard_conditional_enter_requires_four_test_fields(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    task = await _seed_quality(
        session, quality_status="qualified_with_gap", gap_severity="warning"
    )
    _install_bundle(monkeypatch, ClaimContractBundle(claims=(), evidences=()))
    fields: dict[str, object] = {
        "test_budget_usd": Decimal("500.00"),
        "observation_window_days": 14,
        "success_threshold": "首月转化率达到试点门槛",
        "stop_loss": "连续两周低于止损线时停止",
    }
    fields[missing_field] = None

    with pytest.raises(
        ReportContractInvalidError,
        match=f"conditional_enter_requires_{missing_field}",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "conditional_enter"},
            **fields,
        )


@pytest.mark.anyio
async def test_standard_conditional_enter_populates_four_test_fields(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await _seed_quality(
        session, quality_status="qualified_with_gap", gap_severity="warning"
    )
    _install_bundle(monkeypatch, ClaimContractBundle(claims=(), evidences=()))

    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=WORKSPACE_ID,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
        requested_conclusions={"US": "conditional_enter"},
        test_budget_usd=Decimal("500.00"),
        observation_window_days=14,
        success_threshold="首月转化率达到试点门槛",
        stop_loss="连续两周低于止损线时停止",
    )

    assert contract.markets[0].conclusion_standard == "conditional_enter"
    assert contract.decision.resolve == ["测试预算 500.00 USD", "观察窗口 14 天"]
    assert contract.decision.prove == ["首月转化率达到试点门槛"]
    assert contract.decision.protect == ["连续两周低于止损线时停止"]


@pytest.mark.anyio
async def test_quick_uses_only_directional_labels(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    task.package_type = "quick"
    await session.flush()
    _install_bundle(monkeypatch, _two_claim_bundle())

    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=WORKSPACE_ID,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
    )

    assert contract.markets[0].conclusion_quick == "worth_validating"
    assert contract.markets[0].conclusion_standard is None
    assert contract.sku_candidates == []
    assert "方向性" in contract.decision.answer
    assert "confirmed" not in contract.decision.answer


@pytest.mark.anyio
async def test_quick_rejects_confirmed_and_l4_claims(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    task.package_type = "quick"
    await session.flush()
    _install_bundle(
        monkeypatch,
        _single_claim_bundle(
            status=ClaimState.CONFIRMED,
            grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        ),
    )

    with pytest.raises(
        ReportContractInvalidError,
        match="quick_evidence_grade_exceeds_l3",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
        )


@pytest.mark.anyio
async def test_quick_rejects_standard_conclusion_and_sku_candidates(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    task.package_type = "quick"
    await session.flush()
    _install_bundle(monkeypatch, ClaimContractBundle(claims=(), evidences=()))

    with pytest.raises(
        ReportContractInvalidError,
        match="quick_conclusion_not_allowed",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            requested_conclusions={"US": "enter"},
        )

    with pytest.raises(
        ReportContractInvalidError,
        match="quick_sku_candidates_forbidden",
    ):
        await assemble_report_contract_v1_1(
            session,
            workspace_id=WORKSPACE_ID,
            task=task,
            run_id=None,
            template_id="t2_competitor",
            generated_at=datetime(2026, 3, 3, tzinfo=UTC),
            sku_candidates=_sku_rows(3),
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_contract_v1_1.py -v
```
Expected: `ModuleNotFoundError: data_intelligence_hub.services.report_contract_v1_1`。

- [ ] **Step 3: 写装配器**

Create `apps/api/src/data_intelligence_hub/services/report_contract_v1_1.py`。装配器直接构造 1.1 字典，再交给 `ReportContract` 校验；不得调用 `build_contract`，不得用 `identity.task_id` 做业务判断（只允许 `assert_single_task_id` 做镜像相等校验）。

```python
"""C9 的 1.1 装配器与不可变版本推进。"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.claim import ClaimReviewStatus
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.report_reviewer_assignment import ReportReviewerAssignment
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.report_artifacts import (
    create_artifact,
    get_artifact,
    get_current_published,
)
from data_intelligence_hub.schemas.report_contract import (
    SCHEMA_VERSION,
    Acceptance,
    Artifact,
    Delivery,
    Gate,
    ReportContract,
    Review,
    contract_sha256,
    validate_contract,
)
from data_intelligence_hub.services.claim_semantics import (
    market_independent_cluster_count,
    validate_claim_semantics,
)
from data_intelligence_hub.services.claims import (
    ClaimContractBundle,
    ClaimContractRow,
    EvidenceContractRow,
    load_publishable_claim_rows,
    validate_claim_bundle,
)
from data_intelligence_hub.services.dataset_quality import (
    ConclusionInputs,
    SkuCandidate,
    validate_conclusion,
)
from data_intelligence_hub.services.exceptions import (
    ReportContractInvalidError,
    ReportQualityNotReadyError,
    ReportRevisionTargetInvalidError,
)
from data_intelligence_hub.services.market_quality import (
    MarketQualityNotReadyError,
    ensure_market_quality,
)
from data_intelligence_hub.services.report_artifacts import (
    build_artifact,
    render_contract_pages,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import PackageTier

# ``report_publication`` imports this module at import time.  Import its
# functions inside the functions that need them to avoid a cycle.

NIL_UUID = uuid.UUID(int=0)
ZERO_SHA256 = "0" * 64
DEFAULT_ACCESS_SCOPE = ["workspace_project"]
DEFAULT_RETENTION_CLASS = "standard_24m"
ASSEMBLED_TOP_LEVEL_KEYS = (
    "schema_version", "contract_id", "task_id", "order_id", "template_id",
    "template_version", "report_version", "generated_at", "identity",
    "decision", "gates", "coverage", "markets", "metrics", "claims",
    "evidences", "sku_candidates", "datasets", "scorecard", "rights",
    "currency", "language", "run_ledger", "limits", "unknowns", "review",
    "acceptance", "delivery", "artifact",
)
_GRADE_ORDER = {
    "L0_unverified": 0,
    "L1_contract": 1,
    "L2_fixture_local": 2,
    "L3_live_single": 3,
    "L4_authorized_live": 4,
}
_QUICK_MAX_GRADE = "L3_live_single"
_QUICK_DEFAULT_CONCLUSIONS = {
    "qualified": "worth_validating",
    "qualified_with_gap": "recommend_standard_scope",
    "not_qualified": "evidence_gap",
}
_STANDARD_DEFAULT_CONCLUSION = "insufficient_evidence"
_QUICK_ANSWERS = {
    "worth_validating": "方向性结论：worth_validating。本稿未审核，不触发验收。",
    "deprioritize": "方向性结论：deprioritize。本稿未审核，不触发验收。",
    "key_risk": "方向性结论：key_risk。本稿未审核，不触发验收。",
    "evidence_gap": "方向性结论：evidence_gap。本稿未审核，不触发验收。",
    "recommend_standard_scope": (
        "方向性结论：recommend_standard_scope。本稿未审核，不触发验收。"
    ),
}
_STANDARD_ANSWERS = {
    "enter": "Standard 结论：enter。",
    "conditional_enter": "Standard 结论：conditional_enter。",
    "do_not_enter": "Standard 结论：do_not_enter。",
    "insufficient_evidence": "Standard 结论：insufficient_evidence。",
}
QUICK_LIMITS = (
    "Quick 方向性稿：未审核，不触发验收，不构成最终四态。",
    "证据等级上限 L3，不允许 confirmed。",
)


def assert_single_task_id(contract: Mapping[str, Any]) -> uuid.UUID:
    value = contract.get("task_id")
    identity = contract.get("identity")
    mirrored = identity.get("task_id") if isinstance(identity, Mapping) else None
    if value is None:
        raise ValueError("task_id_required")
    if mirrored is None or str(mirrored) != str(value):
        raise ValueError("task_id_mismatch")
    return uuid.UUID(str(value))


def content_contract_sha256(contract: ReportContract | Mapping[str, Any]) -> str:
    """实质内容哈希。

    排除审核与交付状态、版本身份、生成时间、产物哈希和 gates。gates 由审核
    动作推进，contract_id 与 report_version 是新版本身份，不属于被审核的
    实质内容；不排除会使继承审核永远失败。
    """
    payload = (
        contract.model_dump(mode="json")
        if isinstance(contract, ReportContract)
        else dict(contract)
    )
    excluded = {
        "contract_id", "generated_at", "artifact", "review", "acceptance",
        "delivery", "gates", "report_version", "supersedes_id",
    }
    return contract_sha256(
        {key: value for key, value in payload.items() if key not in excluded}
    )


def _add_working_days(start: date, days: int) -> date:
    """按 C1 占位规则加五个工作日；只跳过周末，不引入节假日表。"""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def draft_placeholders(generated_at: datetime, report_version: int = 1) -> dict[str, Any]:
    """草稿的三个合法占位组；审核与交付后只在新版本中替换。"""
    return {
        "review": Review(
            status="draft",
            reviewer_id=NIL_UUID,
            reviewer_assignment_id=NIL_UUID,
            reviewer_role="internal_reviewer",
            review_scope=[],
            reviewed_at=datetime(1970, 1, 1, tzinfo=UTC),
            review_version=1,
            contract_sha256=ZERO_SHA256,
        ).model_dump(mode="json"),
        "acceptance": Acceptance(
            status="pending",
            window_start=generated_at.date(),
            window_end=_add_working_days(generated_at.date(), 5),
        ).model_dump(mode="json"),
        "delivery": Delivery(
            manifest_id=NIL_UUID,
            report_artifact_id=NIL_UUID,
            report_version=report_version,
            access_scope=list(DEFAULT_ACCESS_SCOPE),
            retention_class=DEFAULT_RETENTION_CLASS,
        ).model_dump(mode="json"),
        "artifact": Artifact(
            report_html_sha256=ZERO_SHA256,
            sop_html_sha256=ZERO_SHA256,
            contract_sha256=ZERO_SHA256,
        ).model_dump(mode="json"),
    }


def _gap_row(gap: DataGap) -> dict[str, Any]:
    return {
        "gap_id": str(gap.id),
        "market": gap.market,
        "data_domain": gap.data_domain,
        "reason_code": gap.reason_code,
        "actual_value": gap.actual_value,
        "threshold_value": gap.threshold_value,
        "impact": gap.impact,
        "customer_text_zh": gap.customer_text_zh,
        "customer_text_en": gap.customer_text_en,
        "remediation": gap.remediation,
        "severity": gap.severity,
    }


def _dataset_row(version: DatasetVersion) -> dict[str, Any]:
    return {
        "dataset_version_id": str(version.id),
        "market": version.market,
        "row_count": version.row_count,
        "content_sha256": version.content_sha256,
        "schema_hash": version.schema_hash,
        "quality_status": version.quality_status,
    }


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _claim_row(row: ClaimContractRow) -> dict[str, Any]:
    scope = row.scope
    if scope.window_start is None or scope.window_end is None:
        raise ReportContractInvalidError(
            f"claim_scope_window_required: {row.claim_id}"
        )
    if row.owner is None:
        raise ReportContractInvalidError(f"claim_owner_required: {row.claim_id}")
    if row.evidence_grade is None:
        raise ReportContractInvalidError(
            f"claim_evidence_grade_required: {row.claim_id}"
        )
    item: dict[str, Any] = {
        "claim_id": row.claim_id,
        "text": row.text,
        "text_en": row.text_en or "",
        "claim_status": row.claim_status.value,
        "evidence_grade": row.evidence_grade.value,
        "scope": {
            "market": scope.market,
            "window": {
                "start": scope.window_start.isoformat(),
                "end": scope.window_end.isoformat(),
                "days": scope.window_days,
            },
            "sample_n": scope.sample_n or 0,
        },
        "owner": str(row.owner),
        "review_status": row.review_status.value,
        "sample_n": scope.sample_n or 0,
        "independent_source_count": row.independent_source_count,
        "counterevidence_text": row.counterevidence_text or "",
        "risk_flags": sorted(row.risk_flags),
        "evidence_ids": list(row.evidence_ids),
    }
    if row.blocked_reason is not None:
        item["blocked_reason"] = row.blocked_reason
    return item


def _evidence_row(row: EvidenceContractRow) -> dict[str, Any]:
    if (
        row.source_tool_id is None
        or row.market is None
        or row.evidence_grade is None
        or row.captured_at is None
    ):
        raise ReportContractInvalidError(f"evidence_incomplete: {row.evidence_id}")
    item: dict[str, Any] = {
        "evidence_id": row.evidence_id,
        "claim_id": row.claim_id,
        "role": row.role.value,
        "raw_record_id": str(row.raw_record_id) if row.raw_record_id else None,
        "source_tool_id": row.source_tool_id,
        "captured_at": _timestamp(row.captured_at),
        "market": row.market,
        "evidence_grade": row.evidence_grade.value,
    }
    if row.url:
        item["url"] = row.url
    if row.excerpt:
        item["excerpt"] = row.excerpt
    if row.locale:
        item["locale"] = row.locale
    return item


def claim_bundle_payload(
    bundle: ClaimContractBundle,
) -> dict[str, list[dict[str, Any]]]:
    """把 C7 bundle 投影为合同 ``claims`` / ``evidences``。

    装配器与发布前复核共用同一投影，保证 claim digest 可比。
    """
    return {
        "claims": [_claim_row(row) for row in bundle.claims],
        "evidences": [_evidence_row(row) for row in bundle.evidences],
    }


def _requested_conclusion(
    *,
    package_type: PackageTier,
    market: Mapping[str, Any],
    requested: Mapping[str, str] | None,
) -> str:
    market_code = str(market["market"])
    if requested is not None and market_code in requested:
        return requested[market_code]
    if package_type is PackageTier.QUICK:
        return _QUICK_DEFAULT_CONCLUSIONS[str(market["quality_status"])]
    return _STANDARD_DEFAULT_CONCLUSION


def _conclusion_inputs(
    *,
    package_type: PackageTier,
    requested: str,
    bundle: ClaimContractBundle,
    market: str,
    sku_candidates: Sequence[Mapping[str, Any]],
    test_budget_usd: Decimal | None,
    observation_window_days: int | None,
    success_threshold: str | None,
    stop_loss: str | None,
) -> ConclusionInputs:
    market_rows = [
        row for row in sku_candidates if str(row.get("market")) == market
    ]
    candidates = tuple(
        SkuCandidate(candidate_id=str(index), rank=int(row["rank"]))
        for index, row in enumerate(market_rows, start=1)
    )
    common: dict[str, Any] = {
        "sku_candidates": candidates,
        "test_budget_usd": test_budget_usd,
        "observation_window_days": observation_window_days,
        "success_threshold": success_threshold,
        "stop_loss": stop_loss,
        "c7_independent_cluster_count": market_independent_cluster_count(
            bundle, market
        ),
    }
    if package_type is PackageTier.QUICK:
        return ConclusionInputs(requested_quick=requested, **common)
    return ConclusionInputs(requested_standard=requested, **common)


def _assembly_gates(
    assessments: Sequence[MarketAssessment],
    *,
    claim_gate_blocked: bool,
) -> list[dict[str, Any]]:
    evidence_status = "pass"
    for item in assessments:
        for domain in (item.details_json or {}).get("domains") or []:
            if domain.get("status") in {"missing", "blocked"}:
                evidence_status = "blocked"
                break
        if evidence_status == "blocked":
            break
    return [
        Gate(gate_id="G-Evidence", status=evidence_status).model_dump(mode="json"),
        Gate(
            gate_id="G-Claim",
            status="blocked" if claim_gate_blocked else "pass",
        ).model_dump(mode="json"),
        Gate(gate_id="G-Publish", status="pending").model_dump(mode="json"),
    ]


def _decision_block(
    *,
    task: Any,
    package_type: PackageTier,
    markets: Sequence[Mapping[str, Any]],
    test_budget_usd: Decimal | None,
    observation_window_days: int | None,
    success_threshold: str | None,
    stop_loss: str | None,
) -> dict[str, Any]:
    primary = next(
        (item for item in markets if item["market_role"] == "primary"),
        markets[0],
    )
    if package_type is PackageTier.QUICK:
        label = str(primary["conclusion_quick"])
        answer = _QUICK_ANSWERS[label]
    else:
        label = str(primary["conclusion_standard"])
        answer = _STANDARD_ANSWERS[label]
    protect: list[str] = []
    resolve: list[str] = []
    prove: list[str] = []
    if label == "conditional_enter":
        if test_budget_usd is not None:
            resolve.append(f"测试预算 {test_budget_usd} USD")
        if observation_window_days is not None:
            resolve.append(f"观察窗口 {observation_window_days} 天")
        if success_threshold:
            prove.append(success_threshold)
        if stop_loss:
            protect.append(stop_loss)
    return {
        "decision_question": task.decision_question,
        "answer": answer,
        "protect": protect,
        "resolve": resolve,
        "prove": prove,
    }


async def assemble_report_contract_v1_1(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task: Any,
    run_id: uuid.UUID | None,
    template_id: str,
    generated_at: datetime,
    report_version: int = 1,
    supersedes_id: uuid.UUID | None = None,
    requested_conclusions: Mapping[str, str] | None = None,
    sku_candidates: Sequence[Mapping[str, Any]] = (),
    test_budget_usd: Decimal | None = None,
    observation_window_days: int | None = None,
    success_threshold: str | None = None,
    stop_loss: str | None = None,
) -> ReportContract:
    """从 C8 事实与 C7 已审核 Claim 装配 29 个顶层键。"""
    try:
        package_type = PackageTier(task.package_type)
    except ValueError as exc:
        raise ReportContractInvalidError("package_type_invalid") from exc
    if task.project_id is None:
        raise ReportContractInvalidError("project_id_required")
    if package_type is PackageTier.QUICK and sku_candidates:
        raise ReportContractInvalidError("quick_sku_candidates_forbidden")
    if run_id is not None:
        run = await session.get(Run, run_id)
        if run is not None and run.workflow_version_id is not None:
            try:
                await ensure_market_quality(
                    session, run_id=run_id, task_id=task.id
                )
            except MarketQualityNotReadyError as exc:
                raise ReportQualityNotReadyError(str(exc)) from exc
    assessments = list(
        (
            await session.execute(
                select(MarketAssessment)
                .where(
                    MarketAssessment.workspace_id == workspace_id,
                    MarketAssessment.task_id == task.id,
                )
                .order_by(MarketAssessment.market)
            )
        ).scalars()
    )
    if not assessments:
        raise ReportQualityNotReadyError("market_assessment_missing")
    assessments.sort(
        key=lambda item: (item.market_role != "primary", item.market)
    )
    gaps = list(
        (
            await session.execute(
                select(DataGap)
                .where(
                    DataGap.workspace_id == workspace_id,
                    DataGap.task_id == task.id,
                    DataGap.status == "open",
                )
                .order_by(DataGap.market, DataGap.data_domain)
            )
        ).scalars()
    )
    versions = list(
        (
            await session.execute(
                select(DatasetVersion)
                .where(
                    DatasetVersion.workspace_id == workspace_id,
                    DatasetVersion.task_id == task.id,
                    DatasetVersion.status == "saved",
                )
                .order_by(DatasetVersion.market, DatasetVersion.version_number)
            )
        ).scalars()
    )
    bundle = await load_publishable_claim_rows(
        session,
        workspace_id=workspace_id,
        project_id=task.project_id,
        task_id=task.id,
    )
    for claim in bundle.claims:
        if claim.review_status is not ClaimReviewStatus.APPROVED:
            raise ReportContractInvalidError(
                f"claim_not_approved: {claim.claim_id}: "
                f"{claim.review_status.value}"
            )
    claim_issues = validate_claim_bundle(bundle)
    if claim_issues:
        raise ReportContractInvalidError("；".join(claim_issues))
    if package_type is PackageTier.QUICK:
        for item in assessments:
            if _GRADE_ORDER.get(item.evidence_grade, -1) > _GRADE_ORDER[
                _QUICK_MAX_GRADE
            ]:
                raise ReportContractInvalidError(
                    f"quick_evidence_grade_exceeds_l3: {item.market}"
                )
        for claim in bundle.claims:
            grade = claim.evidence_grade.value if claim.evidence_grade else ""
            if _GRADE_ORDER.get(grade, -1) > _GRADE_ORDER[_QUICK_MAX_GRADE]:
                raise ReportContractInvalidError(
                    "quick_evidence_grade_exceeds_l3: "
                    f"claim {claim.claim_id}"
                )
        for evidence in bundle.evidences:
            grade = (
                evidence.evidence_grade.value
                if evidence.evidence_grade
                else ""
            )
            if _GRADE_ORDER.get(grade, -1) > _GRADE_ORDER[_QUICK_MAX_GRADE]:
                raise ReportContractInvalidError(
                    "quick_evidence_grade_exceeds_l3: "
                    f"evidence {evidence.evidence_id}"
                )
    gaps_by_market: dict[str, list[dict[str, Any]]] = {}
    for gap in gaps:
        gaps_by_market.setdefault(gap.market, []).append(_gap_row(gap))
    markets: list[dict[str, Any]] = []
    for item in assessments:
        market: dict[str, Any] = {
            "market": item.market,
            "market_role": item.market_role,
            "quality_status": item.quality_status,
            "evidence_grade": item.evidence_grade,
            "domains": list((item.details_json or {}).get("domains") or []),
            "sample_counts": dict(item.sample_counts or {}),
            "thresholds": dict(item.thresholds or {}),
            "gaps": gaps_by_market.get(item.market, []),
        }
        requested = _requested_conclusion(
            package_type=package_type,
            market=market,
            requested=requested_conclusions,
        )
        decision = validate_conclusion(
            quality_status=item.quality_status,
            package_type=package_type,
            inputs=_conclusion_inputs(
                package_type=package_type,
                requested=requested,
                bundle=bundle,
                market=item.market,
                sku_candidates=sku_candidates,
                test_budget_usd=test_budget_usd,
                observation_window_days=observation_window_days,
                success_threshold=success_threshold,
                stop_loss=stop_loss,
            ),
        )
        resolved = (
            decision.quick
            if package_type is PackageTier.QUICK
            else decision.standard
        )
        if resolved is None:
            detail = "；".join(decision.reasons) or "conclusion_not_allowed"
            raise ReportContractInvalidError(
                f"conclusion_not_allowed: {item.market}:{detail}"
            )
        if package_type is PackageTier.QUICK:
            market["conclusion_quick"] = resolved
        else:
            market["conclusion_standard"] = resolved
        markets.append(market)
    semantic_issues = validate_claim_semantics(
        bundle,
        markets=markets,
        package_type=task.package_type,
    )
    if semantic_issues:
        raise ReportContractInvalidError(
            "claim_semantics_invalid: " + "；".join(semantic_issues)
        )
    bundle_payload = claim_bundle_payload(bundle)
    claims = bundle_payload["claims"]
    evidences = bundle_payload["evidences"]
    contract_skus = (
        [dict(row) for row in sku_candidates]
        if package_type is PackageTier.STANDARD
        else []
    )
    datasets = [_dataset_row(version) for version in versions]
    minimum_grade = min(
        (item.evidence_grade for item in assessments),
        key=lambda grade: _GRADE_ORDER.get(grade, -1),
    )
    claim_status_counts = Counter(
        claim.claim_status.value for claim in bundle.claims
    )
    claim_grade_counts = Counter(
        claim.evidence_grade.value
        for claim in bundle.claims
        if claim.evidence_grade is not None
    )
    independent_source_count = len(
        {
            evidence.source_cluster_key
            for evidence in bundle.evidences
            if evidence.independent and evidence.source_cluster_key
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"report-contract:{task.id}:{run_id}:{template_id}:{report_version}",
            )
        ),
        "task_id": str(task.id),
        "order_id": str(task.id),
        "template_id": template_id,
        "template_version": "1.0.0",
        "report_version": report_version,
        "generated_at": _timestamp(generated_at),
        "identity": {
            "task_id": str(task.id),
            "brand": task.brand,
            "category": task.category,
            "competitors": list(task.competitors or []),
            "markets": list(task.markets),
            "window": {
                "start": task.window_start.isoformat(),
                "end": task.window_end.isoformat(),
                "days": (task.window_end - task.window_start).days + 1,
            },
        },
        "decision": _decision_block(
            task=task,
            package_type=package_type,
            markets=markets,
            test_budget_usd=test_budget_usd,
            observation_window_days=observation_window_days,
            success_threshold=success_threshold,
            stop_loss=stop_loss,
        ),
        "gates": _assembly_gates(
            assessments,
            claim_gate_blocked=bool(claim_issues),
        ),
        "coverage": {"cells": []},
        "metrics": [],
        "claims": claims,
        "evidences": evidences,
        "sku_candidates": contract_skus,
        "markets": markets,
        "datasets": datasets,
        "scorecard": {
            "markets": markets,
            "minimum_evidence_grade": minimum_grade,
            "claims": {
                "total": len(claims),
                "by_status": dict(claim_status_counts),
                "by_grade": dict(claim_grade_counts),
                "independent_source_count": independent_source_count,
            },
        },
        "rights": {"sources": []},
        "currency": {
            "base_currency": "USD",
            "quote_currency": "USD",
            "rate": 1.0,
            "rate_date": generated_at.date().isoformat(),
            "source": "fixed",
        },
        "language": {
            "primary_language": "zh-CN",
            "executive_summary_language": "en",
            "translation_method": "deterministic_template",
        },
        "run_ledger": [],
        "limits": (
            list(QUICK_LIMITS)
            if package_type is PackageTier.QUICK
            else []
        ),
        "unknowns": [],
        **draft_placeholders(generated_at, report_version),
    }
    if supersedes_id is not None:
        payload["supersedes_id"] = str(supersedes_id)
    try:
        contract = ReportContract.model_validate(payload)
    except (KeyError, TypeError, ValidationError) as exc:
        raise ReportContractInvalidError(str(exc)) from exc
    issues = validate_contract(contract)
    if issues:
        raise ReportContractInvalidError("；".join(issues))
    assert_single_task_id(contract.model_dump(mode="json"))
    return contract
```

`order_id` 使用 C4 任务单 ID：C4 把客户订单建模为 `workbench_tasks`，v1.1 不新建独立订单表。

装配边界固定如下：

- `load_publishable_claim_rows` 必须接受 `task_id`（C7 Task 7 的只读签名扩展），C9 传 `task_id=task.id`、`project_id=task.project_id`。C7 未提供该过滤时停止，不按市场或时间窗猜测。
- 先检查 bundle 内每条 Claim 的 `review_status`；非 `approved` 抛 `report_contract_invalid` 的 `claim_not_approved`。再调用 `validate_claim_bundle`，问题非空同样抛 `report_contract_invalid`。
- Quick 默认方向标签按质量状态固定：`qualified -> worth_validating`、`qualified_with_gap -> recommend_standard_scope`、`not_qualified -> evidence_gap`。调用方可用 `requested_conclusions` 覆盖，但只能取 C8 `allowed_conclusions` 的子集。
- Standard 默认结论固定 `insufficient_evidence`。`enter`、`do_not_enter`、`conditional_enter` 必须由调用方显式请求，并由 `validate_conclusion` 检查候选数、独立簇与四个测试字段。
- `gates` 只写 C9 拥有的三项：`G-Evidence`（任一市场核心域 `missing`/`blocked` 时为 `blocked`）、`G-Claim`（Claim 门禁通过时为 `pass`）、`G-Publish`（草稿为 `pending`，审核通过后由 `create_reviewed_contract_version` 改为 `pass`）。
- `acceptance` 占位窗口按 C1 规则使用生成日与五个工作日；Quick 方向稿的占位组同样存在，但 2 小时稿不触发验收流程。

- [ ] **Step 4: 写版本推进**

在 `report_contract_v1_1.py` 追加。`delivery.report_artifact_id` 必须指向新版本自身，因此先预生成 `artifact_id`：

```python
@dataclass(frozen=True, slots=True)
class ReviewedVersion:
    artifact: ReportArtifact
    event: ReportAuditEvent


def _successor_contract(
    source: ReportContract,
    *,
    report_version: int,
    artifact_id: uuid.UUID,
    review: Review | None = None,
    acceptance: Acceptance | None = None,
    delivery: Delivery | None = None,
    gates: Sequence[Gate] | None = None,
) -> ReportContract:
    return source.model_copy(
        update={
            "contract_id": uuid.uuid4(),
            "report_version": report_version,
            "supersedes_id": source.contract_id,
            "review": review or source.review,
            "acceptance": acceptance or source.acceptance,
            "delivery": delivery or source.delivery,
            "gates": list(gates) if gates is not None else source.gates,
            "artifact": Artifact(
                report_html_sha256=ZERO_SHA256,
                sop_html_sha256=ZERO_SHA256,
                contract_sha256=ZERO_SHA256,
            ),
            "generated_at": datetime.now(UTC),
        }
    )


async def _create_successor_artifact(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
    source: ReportArtifact,
    contract: ReportContract,
    artifact_id: uuid.UUID,
) -> ReportArtifact:
    rendered = render_contract_pages(contract)
    built = build_artifact(
        workspace_id=workspace.id,
        project_id=source.project_id,
        template_id=source.template_id,
        contract=rendered.contract,
        report_html=rendered.report_html,
        sop_html=rendered.sop_html,
        run_id=source.run_id,
        report_id=report_id,
        version=f"1.{contract.report_version}.0",
    )
    return await create_artifact(
        session,
        artifact_id=artifact_id,
        workspace_id=built.workspace_id,
        project_id=built.project_id,
        run_id=built.run_id,
        report_id=built.report_id,
        template_id=built.template_id,
        contract_json=built.contract_json,
        contract_sha256=built.contract_sha256,
        data_sha256=built.data_sha256,
        report_html_sha256=built.report_html_sha256,
        sop_html_sha256=built.sop_html_sha256,
        combined_sha256=built.combined_sha256,
        version=built.version,
        report_html=built.report_html,
        sop_html=built.sop_html,
        status="draft",
        created_by=source.created_by,
        supersedes_id=source.id,
    )


async def create_reviewed_contract_version(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
    artifact_id: uuid.UUID,
    reviewer: Any,
    assignment: ReportReviewerAssignment,
    decision: str,
    review_scope: str,
    notes: str | None,
    expected_contract_sha256: str,
) -> ReviewedVersion:
    """审核后创建下一个版本；不改写草稿 contract_json。"""
    from data_intelligence_hub.services.report_publication import record_review

    source = await get_artifact(
        session, workspace_id=workspace.id, artifact_id=artifact_id
    )
    if source is None or source.report_id != report_id:
        raise ReportRevisionTargetInvalidError
    source_contract_json = dict(source.contract_json)
    source_contract_sha256 = source.contract_sha256
    event = await record_review(
        session,
        workspace=workspace,
        report_id=report_id,
        artifact_id=artifact_id,
        reviewer=reviewer,
        assignment=assignment,
        decision=decision,
        review_scope=review_scope,
        notes=notes,
        expected_contract_sha256=expected_contract_sha256,
    )
    await session.refresh(source)
    if decision != "approve":
        return ReviewedVersion(artifact=source, event=event)
    try:
        contract = ReportContract.model_validate(source_contract_json)
    except ValidationError as exc:
        raise ReportContractInvalidError(str(exc)) from exc
    successor_id = uuid.uuid4()
    reviewed_gates = [
        Gate(
            gate_id="G-Publish",
            status="pass",
            owner=reviewer.id,
            decided_at=event.created_at,
            note="internal_review_approved",
        )
        if gate.gate_id == "G-Publish"
        else gate
        for gate in contract.gates
    ]
    if not any(gate.gate_id == "G-Publish" for gate in reviewed_gates):
        reviewed_gates.append(
            Gate(
                gate_id="G-Publish",
                status="pass",
                owner=reviewer.id,
                decided_at=event.created_at,
                note="internal_review_approved",
            )
        )
    reviewed = _successor_contract(
        contract,
        report_version=contract.report_version + 1,
        artifact_id=successor_id,
        review=Review(
            status="approved",
            reviewer_id=reviewer.id,
            reviewer_assignment_id=assignment.id,
            reviewer_role="internal_reviewer",
            review_scope=[review_scope],
            reviewed_at=event.created_at,
            review_version=contract.report_version,
            contract_sha256=source_contract_sha256,
        ),
        gates=reviewed_gates,
    )
    row = await _create_successor_artifact(
        session,
        workspace=workspace,
        report_id=report_id,
        source=source,
        contract=reviewed,
        artifact_id=successor_id,
    )
    await _record_event(
        session,
        workspace_id=workspace.id,
        report_id=report_id,
        artifact_id=row.id,
        actor_id=reviewer.id,
        event_type=_EVENT_APPROVED,
        from_status="draft",
        to_status="draft",
        metadata={
            "contract_sha256": row.contract_sha256,
            "review_scope": review_scope,
            "notes": notes or "",
            "reviewer_role": "internal_reviewer",
            "reviewer_assignment_id": str(assignment.id),
            "reviewed_contract_sha256": row.contract_sha256,
            "reviewed_data_sha256": row.data_sha256,
            "reviewed_report_html_sha256": row.report_html_sha256,
            "reviewed_sop_html_sha256": row.sop_html_sha256,
            "reviewed_claim_digest": claim_review_digest(row.contract_json),
        },
    )
    source.status = "superseded"
    source.superseded_at = event.created_at
    await session.commit()
    await session.refresh(row)
    return ReviewedVersion(artifact=row, event=event)


async def create_delivery_contract_version(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report_id: uuid.UUID,
    artifact_id: uuid.UUID,
    publisher: Any,
    acceptance_window_start: date,
    acceptance_window_end: date,
    manifest_id: uuid.UUID,
    access_scope: list[str],
    retention_class: str,
    publish: bool = True,
) -> ReportArtifact:
    """交付时创建下一个版本；review 组从已发布审核版本原样复制。"""
    source = await get_current_published(
        session, workspace_id=workspace.id, report_id=report_id
    )
    if source is None or source.id != artifact_id or source.status != "published":
        raise ReportRevisionTargetInvalidError
    try:
        contract = ReportContract.model_validate(source.contract_json)
    except ValidationError as exc:
        raise ReportContractInvalidError(str(exc)) from exc
    successor_version = contract.report_version + 1
    successor_id = uuid.uuid4()
    successor = _successor_contract(
        contract,
        report_version=successor_version,
        artifact_id=successor_id,
        acceptance=Acceptance(
            status="pending",
            window_start=acceptance_window_start,
            window_end=acceptance_window_end,
        ),
        delivery=Delivery(
            manifest_id=manifest_id,
            report_artifact_id=successor_id,
            report_version=successor_version,
            access_scope=access_scope,
            retention_class=retention_class,
        ),
    )
    row = await _create_successor_artifact(
        session,
        workspace=workspace,
        report_id=report_id,
        source=source,
        contract=successor,
        artifact_id=successor_id,
    )
    if not publish:
        return row
    publisher_row = publisher
    if not isinstance(publisher, User):
        publisher_row = await session.get(User, publisher)
    if publisher_row is None:
        raise ReportRevisionTargetInvalidError
    from data_intelligence_hub.services.report_publication import publish_artifact

    return await publish_artifact(
        session,
        workspace=workspace,
        report_id=report_id,
        artifact_id=row.id,
        publisher=publisher_row,
        expected_contract_sha256=row.contract_sha256,
        allow_inherited_review=True,
    )


@dataclass(frozen=True, slots=True)
class QuickDirectionalDraft:
    artifact: ReportArtifact
    contract: ReportContract


async def create_quick_directional_artifact(
    session: AsyncSession,
    *,
    workspace: Workspace,
    report: Report | None,
    task: Any,
    run_id: uuid.UUID | None,
    template_id: str,
    generated_at: datetime,
    created_by: User | None,
) -> QuickDirectionalDraft:
    """创建 Quick 2 小时方向稿。

    约束：

    - 与 24 小时正式版共用同一 ``report_id``、``task_id`` 与 ``order_id``；
    - ``report_version=1``，``review.status='draft'``；
    - 证据等级上限 L3，``sku_candidates`` 为空，不出现 ``confirmed``；
    - 只使用 C1 合法占位 ``acceptance``，不写交付，不触发验收；
    - 不新建 run、workflow、订单、授权或 ``run_ledger_entries``，因此不重复收费。
    """
    if task.package_type != "quick":
        raise ReportContractInvalidError("quick_package_required")
    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=workspace.id,
        task=task,
        run_id=run_id,
        template_id=template_id,
        generated_at=generated_at,
        report_version=1,
    )
    from data_intelligence_hub.services.report_publication import (
        create_draft_artifact,
    )

    artifact = await create_draft_artifact(
        session,
        workspace=workspace,
        report=report,
        template_id=template_id,
        contract=contract.model_dump(mode="json"),
        created_by=created_by,
        project_id=task.project_id,
        run_id=run_id,
    )
    stored = ReportContract.model_validate(artifact.contract_json)
    return QuickDirectionalDraft(artifact=artifact, contract=stored)
```

`create_quick_directional_artifact` 只创建方向稿；24 小时正式版由内部审核人走 `create_reviewed_contract_version` 生成。C9 不写 `runs`、`workflow_versions`、`authorizations` 或 `run_ledger_entries`；同一 `task_id` 只对应一个订单由 C5 保证，因此两个版本不重复收费。`content_contract_sha256` 排除 `gates`：审核动作会把 `G-Publish` 从 `pending` 推进到 `pass`，不排除会使继承审核永远失败。

- [ ] **Step 5: 写内部审核人服务**

Create `apps/api/src/data_intelligence_hub/services/report_reviewers.py`。审核主体只来自 `report_reviewer_assignments`；客户 `owner/admin` 与报告创建人一律拒绝：

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.repositories.report_reviewers import (
    create_reviewer_assignment,
    get_active_reviewer_assignment,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_member_role
from data_intelligence_hub.services.exceptions import ReportReviewerForbiddenError


async def assert_reviewer_eligible(
    session: AsyncSession,
    *,
    workspace,
    report,
    reviewer_user_id: uuid.UUID,
    required_scope: str = "report_review",
    assignment: ReportReviewerAssignment | None = None,
    artifact_created_by: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ReportReviewerAssignment:
    if assignment is None:
        assignment = await get_active_reviewer_assignment(
            session, report_id=report.id, reviewer_user_id=reviewer_user_id
        )
    if assignment is None or assignment.status != "active":
        raise ReportReviewerForbiddenError("reviewer_assignment_required")
    if (
        assignment.workspace_id != workspace.id
        or assignment.report_id != report.id
        or assignment.assignment_scope != required_scope
    ):
        raise ReportReviewerForbiddenError("reviewer_assignment_invalid")
    moment = now or datetime.now(UTC)
    if assignment.expires_at <= moment:
        raise ReportReviewerForbiddenError("reviewer_assignment_expired")
    role = await get_workspace_member_role(
        session, workspace_id=workspace.id, user_id=reviewer_user_id
    )
    if role in {"owner", "admin"}:
        raise ReportReviewerForbiddenError("reviewer_self_review_forbidden")
    if artifact_created_by is not None and reviewer_user_id == artifact_created_by:
        raise ReportReviewerForbiddenError("reviewer_self_review_forbidden")
    if reviewer_user_id in {
        claim.get("owner")
        for claim in (getattr(report, "contract_json", {}) or {}).get("claims") or []
    }:
        raise ReportReviewerForbiddenError("reviewer_self_review_forbidden")
    return assignment


async def request_reviewer_assignment(
    session: AsyncSession,
    *,
    workspace,
    report,
    reviewer_user_id: uuid.UUID,
    assignment_scope: str,
    assigned_by: uuid.UUID,
    now: datetime,
    expires_at: datetime,
) -> ReportReviewerAssignment:
    role = await get_workspace_member_role(
        session, workspace_id=workspace.id, user_id=reviewer_user_id
    )
    if role in {"owner", "admin"} or reviewer_user_id == assigned_by:
        raise ReportReviewerForbiddenError("reviewer_self_review_forbidden")
    if assignment_scope not in {"report_read", "report_review"}:
        raise ReportReviewerForbiddenError("reviewer_assignment_invalid")
    return await create_reviewer_assignment(
        session,
        ReportReviewerAssignment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=report.project_id,
            report_id=report.id,
            artifact_id=None,
            reviewer_user_id=reviewer_user_id,
            assignment_scope=assignment_scope,
            status="active",
            assigned_by=assigned_by,
            assigned_at=now,
            expires_at=expires_at,
        ),
    )
```

- [ ] **Step 6: 写生命周期与审核人失败测试**

追加到 `test_report_contract_v1_1.py`：

```python
from data_intelligence_hub.services.report_contract_v1_1 import (
    create_delivery_contract_version,
    create_reviewed_contract_version,
)


async def test_draft_placeholders_are_legal(session: AsyncSession) -> None:
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=WORKSPACE_ID,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
    )
    assert contract.review.status == "draft"
    assert contract.review.reviewer_id == uuid.UUID(int=0)
    assert contract.review.contract_sha256 == "0" * 64
    assert contract.acceptance.status == "pending"
    assert contract.delivery.report_artifact_id == uuid.UUID(int=0)
    assert contract.delivery.access_scope == ["workspace_project"]
    assert contract.artifact.contract_sha256 == "0" * 64


async def _seed_lifecycle_owner(session: AsyncSession):
    from types import SimpleNamespace

    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.report import Report
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

    owner = User(email="owner-c9@example.test", password_hash="x", name="Owner")
    reviewer = User(email="reviewer-c9@example.test", password_hash="x", name="Reviewer")
    session.add_all([owner, reviewer])
    await session.flush()
    workspace = Workspace(
        id=WORKSPACE_ID, name="W", slug="w-c9", owner_id=owner.id
    )
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner"))
    project = Project(
        id=PROJECT_ID,
        workspace_id=workspace.id,
        name="P",
        domain="ecommerce",
        status="active",
        owner_id=owner.id,
    )
    session.add(project)
    await session.flush()
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="t2_competitor",
        title="C9",
        content="",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    return SimpleNamespace(workspace=workspace, project=project, report=report, owner=owner, reviewer=reviewer)


async def test_review_and_delivery_never_mutate_published_contract_json(
    session: AsyncSession,
) -> None:
    from data_intelligence_hub.services.report_contract_v1_1 import (
        create_delivery_contract_version,
        create_reviewed_contract_version,
    )
    from data_intelligence_hub.services.report_publication import (
        create_draft_artifact,
        publish_artifact,
    )
    from data_intelligence_hub.services.report_reviewers import request_reviewer_assignment

    seed = await _seed_lifecycle_owner(session)
    task = await _seed_quality(session, quality_status="qualified_with_gap", gap_severity="warning")
    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=seed.workspace.id,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
    )
    draft = await create_draft_artifact(
        session,
        workspace=seed.workspace,
        report=seed.report,
        template_id="t2_competitor",
        contract=contract.model_dump(mode="json"),
        created_by=seed.owner,
    )
    draft_bytes = canonical_json_bytes(draft.contract_json)
    assignment = await request_reviewer_assignment(
        session,
        workspace=seed.workspace,
        report=seed.report,
        reviewer_user_id=seed.reviewer.id,
        assignment_scope="report_review",
        assigned_by=seed.owner.id,
        now=datetime(2026, 3, 3, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    reviewed = await create_reviewed_contract_version(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=draft.id,
        reviewer=seed.reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes="通过",
        expected_contract_sha256=draft.contract_sha256,
    )
    published = await publish_artifact(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=reviewed.artifact.id,
        publisher=seed.owner,
        expected_contract_sha256=reviewed.artifact.contract_sha256,
        allow_inherited_review=True,
    )
    published_bytes = canonical_json_bytes(published.contract_json)
    delivered = await create_delivery_contract_version(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=published.id,
        publisher=seed.owner,
        acceptance_window_start=date(2026, 3, 4),
        acceptance_window_end=date(2026, 3, 11),
        manifest_id=uuid.uuid4(),
        access_scope=["workspace_project"],
        retention_class="standard_24m",
    )
    old_draft = await session.get(type(draft), draft.id)
    old_published = await session.get(type(published), published.id)
    assert canonical_json_bytes(old_draft.contract_json) == draft_bytes
    assert canonical_json_bytes(old_published.contract_json) == published_bytes
    assert old_draft.status == "superseded"
    assert old_published.status == "superseded"
    assert delivered.contract_json["report_version"] == 3
    assert delivered.contract_json["review"] == published.contract_json["review"]
    assert delivered.contract_json["delivery"]["report_artifact_id"] == str(delivered.id)


@pytest.mark.anyio
async def test_publish_rejects_changed_claim_bundle(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from data_intelligence_hub.services.report_contract_v1_1 import (
        create_reviewed_contract_version,
    )
    from data_intelligence_hub.services.report_publication import (
        create_draft_artifact,
        publish_artifact,
    )
    from data_intelligence_hub.services.report_reviewers import (
        request_reviewer_assignment,
    )

    seed = await _seed_lifecycle_owner(session)
    task = await _seed_quality(session, quality_status="qualified", gap_severity=None)
    run_id = uuid.uuid4()
    session.add(
        Run(
            id=run_id,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            status="completed",
            workflow_version_id=uuid.uuid4(),
            market_code="US",
            finished_at=datetime.now(UTC),
        )
    )
    await session.flush()

    async def empty_loader(*args, **kwargs):
        return ClaimContractBundle(claims=(), evidences=())

    async def skip_quality(*args, **kwargs):
        return None

    monkeypatch.setattr(
        report_contract_v1_1, "load_publishable_claim_rows", empty_loader
    )
    monkeypatch.setattr(report_publication, "ensure_market_quality", skip_quality)
    contract = await assemble_report_contract_v1_1(
        session,
        workspace_id=seed.workspace.id,
        task=task,
        run_id=None,
        template_id="t2_competitor",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
    )
    draft = await create_draft_artifact(
        session,
        workspace=seed.workspace,
        report=seed.report,
        template_id="t2_competitor",
        contract=contract.model_dump(mode="json"),
        created_by=seed.owner,
        run_id=run_id,
    )
    assignment = await request_reviewer_assignment(
        session,
        workspace=seed.workspace,
        report=seed.report,
        reviewer_user_id=seed.reviewer.id,
        assignment_scope="report_review",
        assigned_by=seed.owner.id,
        now=datetime(2026, 3, 3, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    reviewed = await create_reviewed_contract_version(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=draft.id,
        reviewer=seed.reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes="通过",
        expected_contract_sha256=draft.contract_sha256,
    )
    changed = _two_claim_bundle()
    assert validate_claim_bundle(changed) == []

    async def changed_loader(*args, **kwargs):
        return changed

    monkeypatch.setattr(
        report_publication, "load_publishable_claim_rows", changed_loader
    )
    with pytest.raises(ReportPublishGateBlockedError, match="claim_bundle_stale"):
        await publish_artifact(
            session,
            workspace=seed.workspace,
            report_id=seed.report.id,
            artifact_id=reviewed.artifact.id,
            publisher=seed.owner,
            expected_contract_sha256=reviewed.artifact.contract_sha256,
            allow_inherited_review=True,
        )
```

审核人测试文件 `apps/api/tests/unit/test_report_reviewers.py` 用同一个 `_seed_lifecycle_owner` 夹具覆盖：active `report_review` 通过；无 assignment 抛 `reviewer_assignment_required`；客户 owner/admin 抛 `reviewer_self_review_forbidden`；`report_read` 范围抛 `reviewer_assignment_invalid`；`expires_at` 已过抛 `reviewer_assignment_expired`；报告创建人不能审核。测试只读 `report_reviewer_assignments`，不把 `workspace_members.role` 当审核角色。

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.services.exceptions import ReportReviewerForbiddenError
from data_intelligence_hub.services.report_reviewers import (
    assert_reviewer_eligible,
    request_reviewer_assignment,
)


@pytest.fixture
async def session():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from data_intelligence_hub.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.fixture
async def report_seed(session: AsyncSession):
    from types import SimpleNamespace

    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.report import Report
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

    owner = User(email="owner-r@example.test", password_hash="x", name="Owner")
    reviewer = User(email="reviewer-r@example.test", password_hash="x", name="Reviewer")
    session.add_all([owner, reviewer])
    await session.flush()
    workspace = Workspace(name="W", slug="w-r", owner_id=owner.id)
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner"))
    project = Project(
        workspace_id=workspace.id, name="P", domain="ecommerce", status="active", owner_id=owner.id
    )
    session.add(project)
    await session.flush()
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="t2_competitor",
        title="R",
        content="",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    return SimpleNamespace(workspace=workspace, project=project, report=report, owner=owner, reviewer=reviewer)


async def _assignment(session, seed, *, scope="report_review", expires_at=None):
    return await request_reviewer_assignment(
        session,
        workspace=seed.workspace,
        report=seed.report,
        reviewer_user_id=seed.reviewer.id,
        assignment_scope=scope,
        assigned_by=seed.owner.id,
        now=datetime(2026, 3, 3, tzinfo=UTC),
        expires_at=expires_at or datetime(2027, 3, 3, tzinfo=UTC),
    )


async def test_active_report_review_assignment_passes(session, report_seed) -> None:
    assignment = await _assignment(session, report_seed)
    assert (
        await assert_reviewer_eligible(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.reviewer.id,
            assignment=assignment,
            now=datetime(2026, 3, 4, tzinfo=UTC),
        )
    ).id == assignment.id


async def test_missing_assignment_is_rejected(session, report_seed) -> None:
    with pytest.raises(
        ReportReviewerForbiddenError, match="reviewer_assignment_required"
    ):
        await assert_reviewer_eligible(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.reviewer.id,
        )


async def test_customer_owner_cannot_be_reviewer(session, report_seed) -> None:
    with pytest.raises(
        ReportReviewerForbiddenError, match="reviewer_self_review_forbidden"
    ):
        await request_reviewer_assignment(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.owner.id,
            assignment_scope="report_review",
            assigned_by=report_seed.owner.id,
            now=datetime(2026, 3, 3, tzinfo=UTC),
            expires_at=datetime(2027, 3, 3, tzinfo=UTC),
        )


async def test_report_read_scope_cannot_review(session, report_seed) -> None:
    assignment = await _assignment(session, report_seed, scope="report_read")
    with pytest.raises(
        ReportReviewerForbiddenError, match="reviewer_assignment_invalid"
    ):
        await assert_reviewer_eligible(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.reviewer.id,
            assignment=assignment,
            now=datetime(2026, 3, 4, tzinfo=UTC),
        )


async def test_expired_assignment_is_rejected(session, report_seed) -> None:
    assignment = await _assignment(
        session,
        report_seed,
        expires_at=datetime(2026, 3, 2, tzinfo=UTC),
    )
    with pytest.raises(
        ReportReviewerForbiddenError, match="reviewer_assignment_expired"
    ):
        await assert_reviewer_eligible(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.reviewer.id,
            assignment=assignment,
            now=datetime(2026, 3, 4, tzinfo=UTC),
        )


async def test_artifact_creator_cannot_review(session, report_seed) -> None:
    assignment = await _assignment(session, report_seed)
    with pytest.raises(
        ReportReviewerForbiddenError, match="reviewer_self_review_forbidden"
    ):
        await assert_reviewer_eligible(
            session,
            workspace=report_seed.workspace,
            report=report_seed.report,
            reviewer_user_id=report_seed.reviewer.id,
            assignment=assignment,
            artifact_created_by=report_seed.reviewer.id,
            now=datetime(2026, 3, 4, tzinfo=UTC),
        )
```

- [ ] **Step 6A: 写 Quick 2 小时方向稿测试**

Create `apps/api/tests/unit/test_report_quick_directional.py`：

```python
"""C9：Quick 2 小时方向稿与 24 小时正式版。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.market_assessment import MarketAssessment
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench_task import WorkbenchTask
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.exceptions import ReportRevisionTargetInvalidError
from data_intelligence_hub.services.report_contract_v1_1 import (
    create_delivery_contract_version,
    create_quick_directional_artifact,
    create_reviewed_contract_version,
)
from data_intelligence_hub.services.report_publication import publish_artifact
from data_intelligence_hub.services.report_reviewers import request_reviewer_assignment

TASK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
NIL = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(session: AsyncSession) -> SimpleNamespace:
    owner = User(email="quick-owner@example.test", password_hash="x", name="Owner")
    reviewer = User(email="quick-reviewer@example.test", password_hash="x", name="Reviewer")
    session.add_all([owner, reviewer])
    await session.flush()
    workspace = Workspace(name="Quick", slug="quick-unit", owner_id=owner.id)
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner"))
    project = Project(
        workspace_id=workspace.id,
        name="Quick",
        domain="ecommerce",
        status="active",
        owner_id=owner.id,
    )
    session.add(project)
    await session.flush()
    task = WorkbenchTask(
        id=TASK_ID,
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=owner.id,
        owner_id=owner.id,
        brand="Example",
        category="baby_bottle",
        competitors=[],
        package_type="quick",
        primary_market="US",
        comparison_markets=[],
        markets=["US"],
        locale_by_market={"US": "en-US"},
        window_start=date(2026, 1, 1),
        window_end=date(2026, 3, 1),
        decision_question="Should we enter?",
        does_not_answer=[],
        status="submitted",
    )
    session.add(task)
    session.add(
        MarketAssessment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=TASK_ID,
            market="US",
            market_role="primary",
            quality_status="qualified",
            conclusion_standard=None,
            conclusion_quick=None,
            evidence_grade="L3_live_single",
            core_domain_coverage={"products": "pass", "reviews": "pass"},
            sample_counts={"products": 30, "reviews": 400},
            thresholds={"products": 20, "reviews": 300},
            gap_ids=[],
            details_json={
                "domains": [
                    {"data_domain": "products", "status": "pass", "record_count": 30, "threshold": 20},
                    {"data_domain": "reviews", "status": "pass", "record_count": 400, "threshold": 300},
                ]
            },
            computed_at=datetime(2026, 3, 2, tzinfo=UTC),
        )
    )
    session.add(
        DatasetVersion(
            id=uuid.uuid4(),
            dataset_id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=project.id,
            created_by_user_id=owner.id,
            version_number=1,
            task_id=TASK_ID,
            market="US",
            source_task_run_ids=[],
            selected_fields=["title"],
            cleaning_script=[],
            rows=[{"title": "a"}],
            export_preview={},
            row_count=1,
            average_completeness_percent=100,
            status="saved",
            content_sha256="a" * 64,
            schema_hash="b" * 64,
            quality_status="qualified",
            created_at=datetime(2026, 3, 2, tzinfo=UTC),
        )
    )
    report = Report(
        workspace_id=workspace.id,
        project_id=project.id,
        report_type="t1_voc",
        title="Quick",
        content="",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    return SimpleNamespace(
        workspace=workspace,
        project=project,
        task=task,
        report=report,
        owner=owner,
        reviewer=reviewer,
    )


@pytest.mark.anyio
async def test_quick_two_hour_draft_and_reviewed_formal_version(
    session: AsyncSession,
) -> None:
    seed = await _seed(session)
    run_count_before = await session.scalar(select(func.count()).select_from(Run))
    draft = await create_quick_directional_artifact(
        session,
        workspace=seed.workspace,
        report=seed.report,
        task=seed.task,
        run_id=None,
        template_id="t1_voc",
        generated_at=datetime(2026, 3, 3, tzinfo=UTC),
        created_by=seed.owner,
    )
    payload = draft.contract.model_dump(mode="json")

    assert draft.artifact.status == "draft"
    assert payload["report_version"] == 1
    assert payload["review"]["status"] == "draft"
    assert payload["review"]["reviewer_role"] == "internal_reviewer"
    assert payload["review"]["reviewer_id"] == NIL
    assert payload["task_id"] == str(TASK_ID)
    assert payload["order_id"] == str(TASK_ID)
    assert payload["acceptance"]["status"] == "pending"
    assert payload["delivery"]["manifest_id"] == NIL
    assert payload["markets"][0].get("conclusion_standard") is None
    assert payload["markets"][0]["conclusion_quick"] == "worth_validating"
    assert payload["sku_candidates"] == []
    assert any("方向性" in item for item in payload["limits"])
    assert all(claim["claim_status"] != "confirmed" for claim in payload["claims"])
    assert draft.artifact.report_id == seed.report.id

    with pytest.raises(ReportRevisionTargetInvalidError):
        await create_delivery_contract_version(
            session,
            workspace=seed.workspace,
            report_id=seed.report.id,
            artifact_id=draft.artifact.id,
            publisher=seed.owner,
            acceptance_window_start=date(2026, 3, 4),
            acceptance_window_end=date(2026, 3, 11),
            manifest_id=uuid.uuid4(),
            access_scope=["workspace_project"],
            retention_class="standard_24m",
        )

    assignment = await request_reviewer_assignment(
        session,
        workspace=seed.workspace,
        report=seed.report,
        reviewer_user_id=seed.reviewer.id,
        assignment_scope="report_review",
        assigned_by=seed.owner.id,
        now=datetime(2026, 3, 3, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    reviewed = await create_reviewed_contract_version(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=draft.artifact.id,
        reviewer=seed.reviewer,
        assignment=assignment,
        decision="approve",
        review_scope="全量审核",
        notes="通过",
        expected_contract_sha256=draft.artifact.contract_sha256,
    )
    formal = reviewed.artifact.contract_json

    assert formal["report_version"] == 2
    assert formal["contract_id"] != payload["contract_id"]
    assert formal["supersedes_id"] == payload["contract_id"]
    assert formal["review"]["status"] == "approved"
    assert formal["review"]["reviewer_role"] == "internal_reviewer"
    assert formal["review"]["contract_sha256"] == draft.artifact.contract_sha256
    assert formal["task_id"] == str(TASK_ID)
    assert formal["order_id"] == str(TASK_ID)
    assert [item["market"] for item in formal["markets"]] == [
        item["market"] for item in payload["markets"]
    ]
    assert formal["markets"][0]["conclusion_quick"] == "worth_validating"
    assert formal["markets"][0].get("conclusion_standard") is None
    assert formal["sku_candidates"] == []
    assert {gate["gate_id"]: gate["status"] for gate in formal["gates"]}[
        "G-Publish"
    ] == "pass"
    assert reviewed.artifact.report_id == draft.artifact.report_id

    old = await session.get(ReportArtifact, draft.artifact.id)
    assert old is not None
    assert old.status == "superseded"
    assert old.contract_json["review"]["status"] == "draft"
    assert await session.scalar(select(func.count()).select_from(Run)) == run_count_before
    assert await session.scalar(
        select(func.count()).select_from(WorkbenchTask)
    ) == 1

    published = await publish_artifact(
        session,
        workspace=seed.workspace,
        report_id=seed.report.id,
        artifact_id=reviewed.artifact.id,
        publisher=seed.owner,
        expected_contract_sha256=reviewed.artifact.contract_sha256,
        allow_inherited_review=True,
    )
    assert published.status == "published"
    assert published.contract_json["review"]["status"] == "approved"
    assert published.contract_json["review"]["review_version"] == 1
```

- [ ] **Step 7: 运行测试确认通过**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_contract_v1_1.py \
  tests/unit/test_report_quick_directional.py \
  tests/unit/test_report_reviewers.py -v
```
Expected: 24 个装配器用例、1 个 Quick 2 小时用例、5 个审核人用例通过。

- [ ] **Step 8: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "build_artifact" --direction upstream --repo .
node .gitnexus/run.cjs impact "publish_artifact" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/report_contract_v1_1.py \
  apps/api/src/data_intelligence_hub/services/report_reviewers.py \
  apps/api/tests/unit/test_report_contract_v1_1.py \
  apps/api/tests/unit/test_report_quick_directional.py \
  apps/api/tests/unit/test_report_reviewers.py
git commit -m "feat(report): assemble 1.1 contracts, quick directional draft and immutable versions"
```
Expected: `detect-changes` 无 `partial` 或 `truncated`；提交成功。

---

### Task 5: MCP 只产草稿并复用双页渲染

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/tools/reports.py`
- Modify: `apps/api/src/data_intelligence_hub/mcp_runtime/server.py`
- Modify: `apps/api/tests/unit/test_mcp_tools_b5.py`

**Interfaces:**
- Consumes: Task 4 的 `create_draft_artifact`、`render_contract_pages`。
- Produces: `create_report(run_id, template_id, contract, *, project_id=None, workspace_id=None, report_id=None, supersedes_id=None)` 返回 `report_id`、`artifact_id`、`status="draft"`、`review_required=True`；MCP 工具签名新增两个可选参数。

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/unit/test_mcp_tools_b5.py` 的 `test_create_report_requires_contract` 后追加：
```python
@pytest.mark.anyio
async def test_create_report_returns_draft_and_never_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP 只能产草稿。发布必须走人工审核。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        contract = _contract_payload(
            run_id=run_id,
            task_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
        )
        contract["gates"] = [
            {**gate, "status": "pass"} if gate["gate_id"] == "G-Publish" else gate
            for gate in contract["gates"]
        ]
        result = await report_tools.create_report(run_id, TEMPLATE_ID, contract)

        assert result["status"] == "draft"
        assert result["review_required"] is True
        assert result["report_id"]
        async with factory() as session:
            artifact = await session.get(ReportArtifact, uuid.UUID(result["artifact_id"]))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert artifact is not None
    assert artifact.status == "draft"
    assert artifact.published_at is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_mcp_tools_b5.py::test_create_report_returns_draft_and_never_publishes -v
```
Expected: `KeyError: 'status'` 或断言失败。

- [ ] **Step 3: 重构 MCP 工具**

在 `mcp_runtime/tools/reports.py` 中，把导入改为：
```python
import uuid
from collections.abc import Mapping
from typing import Any

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.report_contract import SCHEMA_VERSION
from data_intelligence_hub.services import report_templates
from data_intelligence_hub.services.exceptions import (
    ReportContractInvalidError,
    ReportQualityNotReadyError,
)
from data_intelligence_hub.services.report_publication import create_draft_artifact
```

把整个 `create_report` 函数替换为：
```python
async def create_report(
    run_id: uuid.UUID,
    template_id: str,
    contract: dict[str, object] | None = None,
    *,
    project_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    supersedes_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """为一次运行生成草稿报告产物。

    本函数不发布。发布必须走人工审核与 ``publish_artifact``。
    ``report_id`` 为空时按合同新建 ``reports`` 行。
    """
    _registered_template(template_id)

    if contract is None:
        raise _missing_contract_error()
    if not isinstance(contract, Mapping):
        raise ValueError("report_contract_invalid: contract 必须是对象")

    declared_template = contract.get("template_id")
    if declared_template is not None and declared_template != template_id:
        raise ValueError("template_id_mismatch")

    declared_schema = contract.get("schema_version")
    if declared_schema is not None and declared_schema != SCHEMA_VERSION:
        raise ValueError(f"report_contract_invalid: schema_version 必须是 {SCHEMA_VERSION}")

    _contract_build_inputs(contract)

    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or (project_id is not None and run.project_id != project_id):
            raise ValueError("run_not_found")

        target_workspace_id = workspace_id if workspace_id is not None else run.workspace_id
        workspace = await session.get(Workspace, target_workspace_id)
        if workspace is None:
            raise ValueError("workspace_not_found")

        report = None
        if report_id is not None:
            report = await session.get(Report, report_id)
            if report is None or report.workspace_id != workspace.id:
                raise ValueError("report_not_found")

        try:
            row = await create_draft_artifact(
                session,
                workspace=workspace,
                report=report,
                template_id=template_id,
                contract=contract,
                created_by=None,
                project_id=project_id if project_id is not None else run.project_id,
                run_id=run_id,
                supersedes_id=supersedes_id,
            )
        except ReportQualityNotReadyError as exc:
            raise ValueError(f"report_quality_not_ready: {exc.message}") from exc
        except ReportContractInvalidError as exc:
            raise ValueError(f"report_contract_invalid: {exc.message}") from exc

    return {
        "run_id": str(run_id),
        "report_id": str(row.report_id),
        "template_id": template_id,
        "artifact_id": str(row.id),
        "status": row.status,
        "review_required": True,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "contract": row.contract_json,
        "artifact": {
            "contract_sha256": row.contract_sha256,
            "data_sha256": row.data_sha256,
            "report_html_sha256": row.report_html_sha256,
            "sop_html_sha256": row.sop_html_sha256,
            "combined_sha256": row.combined_sha256,
        },
    }
```
保留 `REQUIRED_CONTRACT_GROUPS`、`REQUIRED_CONTRACT_FIELDS`、`_missing_contract_error`、`_registered_template` 与 `_contract_build_inputs`。
删除 `_render_contract`、`_final_contract` 以及 `build_artifact`、`contract_input_ids`、`contract_payload`、`data_sha256`、`render_sha256`、`verify_artifact`、两个渲染器的导入与使用。

在 `mcp_runtime/server.py` 的 `create_report` 工具签名中加入：
```python
    report_id: str | None = None,
    supersedes_id: str | None = None,
```
并解析：
```python
        parsed_report_id = uuid.UUID(report_id) if report_id else None
        parsed_supersedes_id = uuid.UUID(supersedes_id) if supersedes_id else None
```
传入工具函数。

- [ ] **Step 4: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_mcp_tools_b5.py -v
```
Expected: 全部通过；新增用例通过。

- [ ] **Step 5: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "create_report" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/mcp_runtime/tools/reports.py \
  apps/api/src/data_intelligence_hub/mcp_runtime/server.py \
  apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "refactor(report): 抽出合同双页渲染并让 MCP 只产草稿"
```
Expected: impact 列出 MCP `server.create_report` 与测试调用方；`detect-changes` 干净；提交成功。

---

### Task 6: 报告合同、产物、SOP、审核与发布端点

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/report.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/reports.py`
- Create: `apps/api/tests/integration/test_report_publication_routes.py`

**Interfaces:**
- Consumes: Task 4 的服务；Task 3 的仓储；Task 4A 的 `assemble_report_contract_v1_1` 与 `create_quick_directional_artifact`；C1 路径 `reports.drafts.create`、`reports.publish`；现有 `get_auth_context` 与 `get_authenticated_context`。
- Produces:
  - `POST /api/reports/drafts` → Quick 走 `create_quick_directional_artifact`，Standard 走装配器 + `create_draft_artifact`；质量失败 409 `report_quality_not_ready`，合同失败 422 `report_contract_invalid`
  - `GET /api/reports/{report_id}/contract` → `contract_json`
  - `GET /api/reports/{report_id}/artifact` → `ReportArtifactResponse`
  - `GET /api/reports/{report_id}/sop` → `text/html`
  - `GET /api/reports/{report_id}/revisions` → `list[ReportArtifactResponse]`
  - `POST /api/reports/{report_id}/reviews` → `ReportAuditEventResponse`
  - `POST /api/reports/{report_id}/publish` → `ReportArtifactResponse`
  - `GET /api/reports` 的每行新增可选 `artifact` 摘要。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/integration/test_report_publication_routes.py`:
```python
"""C9：报告发布端点端到端。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import (
    InternalReviewerContext,
    get_internal_reviewer_context,
)
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.services.report_publication import create_draft_artifact

API_ROOT = Path(__file__).resolve().parents[2]


def _contract() -> dict[str, object]:
    """C1 唯一 1.1 形状；与 Task 4 共用同一组 B5 嵌套字段名。"""
    task_id = "11111111-1111-1111-1111-111111111111"
    nil = "00000000-0000-0000-0000-000000000000"
    zero = "0" * 64
    return {
        "schema_version": "1.1.0",
        "contract_id": "22222222-2222-2222-2222-222222222222",
        "task_id": task_id,
        "order_id": task_id,
        "template_id": "t1_voc",
        "template_version": "1.0.0",
        "report_version": 1,
        "generated_at": "2026-10-22T00:00:00Z",
        "identity": {
            "task_id": task_id,
            "brand": "Example",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": {"start": "2026-01-01", "end": "2026-03-01", "days": 60},
        },
        "decision": {
            "decision_question": "是否进入？",
            "answer": "先验证。",
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [{"gate_id": "G-Publish", "status": "pass"}],
        "coverage": {"cells": []},
        "markets": [],
        "metrics": [],
        "claims": [],
        "evidences": [],
        "sku_candidates": [],
        "datasets": [],
        "scorecard": {
            "markets": [],
            "minimum_evidence_grade": "L1_contract",
            "claims": {
                "total": 0,
                "by_status": {},
                "by_grade": {},
                "independent_source_count": 0,
            },
        },
        "rights": {"sources": []},
        "currency": {
            "base_currency": "USD",
            "quote_currency": "USD",
            "rate": 1.0,
            "rate_date": "2026-10-22",
            "source": "fixture",
        },
        "language": {
            "primary_language": "zh-CN",
            "executive_summary_language": "en",
            "translation_method": "deterministic_template",
        },
        "run_ledger": [],
        "limits": [],
        "unknowns": [],
        "review": {
            "status": "draft",
            "reviewer_id": nil,
            "reviewer_assignment_id": nil,
            "reviewer_role": "internal_reviewer",
            "review_scope": [],
            "reviewed_at": "1970-01-01T00:00:00Z",
            "review_version": 1,
            "contract_sha256": zero,
        },
        "acceptance": {
            "status": "pending",
            "window_start": "2026-10-22",
            "window_end": "2026-10-29",
        },
        "delivery": {
            "manifest_id": nil,
            "report_artifact_id": nil,
            "report_version": 1,
            "access_scope": ["workspace_project"],
            "retention_class": "standard_24m",
        },
        "artifact": {
            "report_html_sha256": zero,
            "sop_html_sha256": zero,
            "contract_sha256": zero,
        },
    }


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

    app.dependency_overrides[get_session] = override_session

    async def override_internal_reviewer_context():
        return async_client.internal_reviewer_context  # type: ignore[attr-defined]

    app.dependency_overrides[get_internal_reviewer_context] = (
        override_internal_reviewer_context
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        async_client.session_factory = factory  # type: ignore[attr-defined]
        yield async_client
    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed(
    client: AsyncClient,
    *,
    acting_role: str = "owner",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        owner = User(email="c9-route@example.test", password_hash="x", name="C9")
        session.add(owner)
        await session.flush()
        workspace = Workspace(name="C9 Route", slug="c9-route", owner_id=owner.id)
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="C9 Route",
            domain="osint",
            status="active",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=owner.id,
                role="owner",
            )
        )
        actor = owner
        if acting_role != "owner":
            actor = User(
                email=f"c9-{acting_role}@example.test",
                password_hash="x",
                name="C9 Member",
            )
            session.add(actor)
            await session.flush()
            session.add(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=actor.id,
                    role=acting_role,
                )
            )
        report = Report(
            workspace_id=workspace.id,
            project_id=project.id,
            report_type="t1_voc",
            title="C9 路由报告",
            content="legacy-content-must-not-be-used",
            status="draft",
            period_start=datetime(2026, 1, 1, tzinfo=UTC),
            period_end=datetime(2026, 3, 1, tzinfo=UTC),
        )
        session.add(report)
        await session.flush()
        reviewer = User(
            email="c9-internal-reviewer@example.test",
            password_hash="x",
            name="C9 Internal Reviewer",
        )
        session.add(reviewer)
        await session.flush()
        assignment = ReportReviewerAssignment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=project.id,
            report_id=report.id,
            artifact_id=None,
            reviewer_user_id=reviewer.id,
            assignment_scope="report_review",
            status="active",
            assigned_by=owner.id,
            assigned_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=datetime(2027, 1, 1, tzinfo=UTC),
        )
        session.add(assignment)
        await session.flush()
        artifact = await create_draft_artifact(
            session,
            workspace=workspace,
            report=report,
            template_id="t1_voc",
            contract=_contract(),
            created_by=owner,
        )
        await session.commit()
        client.internal_reviewer_context = InternalReviewerContext(
            user=reviewer,
            workspace=workspace,
            report_id=report.id,
            assignment=assignment,
        )
        client.cookies.set("access_token", create_access_token(actor.id))
        return workspace.id, report.id, artifact.id


@pytest.mark.anyio
async def test_contract_is_unpublished_before_review(
    client: AsyncClient,
) -> None:
    _, report_id, artifact_id = await _seed(client)

    contract = await client.get(f"/api/reports/{report_id}/contract")
    artifact = await client.get(f"/api/reports/{report_id}/artifact")

    assert contract.status_code == 404
    assert contract.json()["detail"] == "report_contract_not_published"
    assert artifact.status_code == 200
    assert artifact.json()["id"] == str(artifact_id)
    assert artifact.json()["status"] == "draft"


@pytest.mark.anyio
async def test_review_publish_and_read_contract(
    client: AsyncClient,
) -> None:
    _, report_id, _ = await _seed(client)
    artifact = (await client.get(f"/api/reports/{report_id}/artifact")).json()

    review = await client.post(
        f"/api/reports/{report_id}/reviews",
        json={
            "decision": "approve",
            "review_scope": "全量审核",
            "notes": "通过",
            "contract_sha256": artifact["contract_sha256"],
        },
    )
    publish = await client.post(
        f"/api/reports/{report_id}/publish",
        json={"contract_sha256": artifact["contract_sha256"]},
    )
    contract = await client.get(f"/api/reports/{report_id}/contract")
    sop = await client.get(f"/api/reports/{report_id}/sop")

    assert review.status_code == 201
    assert review.json()["event_type"] == "report_review_approved"
    reviewed = (await client.get(f"/api/reports/{report_id}/artifact")).json()
    assert reviewed["status"] == "draft"
    assert reviewed["contract_sha256"] != artifact["contract_sha256"]
    assert publish.status_code == 200
    assert publish.json()["status"] == "published"
    assert contract.status_code == 200
    assert contract.json()["decision"]["answer"] != "legacy-content-must-not-be-used"
    assert contract.json()["artifact"]["contract_sha256"] == reviewed["contract_sha256"]
    assert sop.status_code == 200
    assert sop.headers["content-type"].startswith("text/html")


@pytest.mark.anyio
async def test_publish_requires_review(client: AsyncClient) -> None:
    _, report_id, _ = await _seed(client)
    artifact = (await client.get(f"/api/reports/{report_id}/artifact")).json()

    response = await client.post(
        f"/api/reports/{report_id}/publish",
        json={"contract_sha256": artifact["contract_sha256"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "report_review_required"


@pytest.mark.anyio
async def test_contract_hash_mismatch_blocks_publish(client: AsyncClient) -> None:
    _, report_id, _ = await _seed(client)

    response = await client.post(
        f"/api/reports/{report_id}/publish",
        json={"contract_sha256": "0" * 64},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "report_contract_hash_mismatch"


@pytest.mark.anyio
async def test_member_cannot_publish(client: AsyncClient) -> None:
    _, report_id, _ = await _seed(client, acting_role="member")
    artifact = (await client.get(f"/api/reports/{report_id}/artifact")).json()
    await client.post(
        f"/api/reports/{report_id}/reviews",
        json={
            "decision": "approve",
            "review_scope": "全量审核",
            "contract_sha256": artifact["contract_sha256"],
        },
    )
    reviewed = (await client.get(f"/api/reports/{report_id}/artifact")).json()
    response = await client.post(
        f"/api/reports/{report_id}/publish",
        json={"contract_sha256": reviewed["contract_sha256"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "report_publish_forbidden"


@pytest.mark.anyio
async def test_revisions_lists_newest_first(client: AsyncClient) -> None:
    _, report_id, artifact_id = await _seed(client)

    response = await client.get(f"/api/reports/{report_id}/revisions")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(artifact_id)]
```

审核夹具要求：`_seed` 必须额外创建独立内部审核人（不是 `WorkspaceMember(role="owner|admin")`）并插入 active `ReportReviewerAssignment(assignment_scope="report_review")`。`/reviews` 请求使用审核人 Cookie 与 `assignment_id`；owner/admin Cookie 只用于 `/publish`，不得自审。审核通过后 `/publish` 发布 `create_reviewed_contract_version` 返回的新版本，而不是原草稿。

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/integration/test_report_publication_routes.py -v
```
Expected: 404 或 405；端点不存在。

- [ ] **Step 3: 扩展响应模型**

在 `schemas/report.py` 中增加：
```python
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade

ReportArtifactStatus = Literal["draft", "published", "superseded"]


def _lowest_grade(contract_json: dict[str, object]) -> str | None:
    claims = contract_json.get("claims")
    if not isinstance(claims, list):
        return None
    grades = [
        str(item["evidence_grade"])
        for item in claims
        if isinstance(item, dict) and item.get("evidence_grade")
    ]
    valid: list[tuple[int, str]] = []
    for grade in grades:
        try:
            valid.append((GRADE_ORDER[EvidenceGrade(grade)], grade))
        except ValueError:
            continue
    return min(valid)[1] if valid else None


class ReportArtifactResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    status: ReportArtifactStatus
    version: str
    template_id: str
    contract_sha256: str
    data_sha256: str
    report_html_sha256: str
    sop_html_sha256: str
    combined_sha256: str
    supersedes_id: uuid.UUID | None
    created_by: uuid.UUID | None
    published_at: datetime | None
    published_by: uuid.UUID | None
    superseded_at: datetime | None
    created_at: datetime
    decision_answer: str | None = None
    lowest_evidence_grade: str | None = None

    @classmethod
    def from_model(cls, artifact: ReportArtifact) -> ReportArtifactResponse:
        payload = artifact.contract_json
        decision = payload.get("decision")
        answer = decision.get("answer") if isinstance(decision, dict) else None
        return cls(
            id=artifact.id,
            report_id=artifact.report_id,
            status=artifact.status,
            version=artifact.version,
            template_id=artifact.template_id,
            contract_sha256=artifact.contract_sha256,
            data_sha256=artifact.data_sha256,
            report_html_sha256=artifact.report_html_sha256,
            sop_html_sha256=artifact.sop_html_sha256,
            combined_sha256=artifact.combined_sha256,
            supersedes_id=artifact.supersedes_id,
            created_by=artifact.created_by,
            published_at=artifact.published_at,
            published_by=artifact.published_by,
            superseded_at=artifact.superseded_at,
            created_at=artifact.created_at,
            decision_answer=answer if isinstance(answer, str) else None,
            lowest_evidence_grade=_lowest_grade(payload),
        )


class ReportReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    review_scope: str = Field(min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportPublishRequest(BaseModel):
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportDraftRequest(BaseModel):
    task_id: uuid.UUID
    run_id: uuid.UUID | None = None
    template_id: str = Field(min_length=1, max_length=80)
    decision_question: str | None = Field(default=None, max_length=2000)
    generated_at: datetime | None = None


class ReviewerAssignmentRequest(BaseModel):
    reviewer_user_id: uuid.UUID
    assignment_scope: Literal["report_read", "report_review"] = "report_review"
```
把 `ReportResponse` 增加 `artifact: ReportArtifactResponse | None = None`，并在 `from_model` 增加参数 `artifact: ReportArtifact | None = None`，返回体带上 `artifact=ReportArtifactResponse.from_model(artifact) if artifact is not None else None`。
把 `ReportAuditEventResponse.report_id` 改为 `uuid.UUID | None`，并增加 `artifact_id: uuid.UUID | None`。

- [ ] **Step 4: 写路由**

在 `api/routes/reports.py` 顶部补充：
```python
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse

from data_intelligence_hub.api.deps import (
    InternalReviewerContext,
    get_current_user,
    get_internal_reviewer_context,
)
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.report_artifacts import (
    get_latest_artifact,
    latest_artifacts_for_reports,
)
from data_intelligence_hub.repositories.report_reviewers import (
    get_active_reviewer_assignment,
    revoke_reviewer_assignment,
)
from data_intelligence_hub.repositories.reports import get_report
from data_intelligence_hub.repositories.workbench import get_workbench_task_scoped
from data_intelligence_hub.repositories.workspaces import get_workspace_member_role
from data_intelligence_hub.schemas.report import (
    ReportArtifactResponse,
    ReportDraftRequest,
    ReportPublishRequest,
    ReportReviewRequest,
    ReviewerAssignmentRequest,
)
from data_intelligence_hub.services.exceptions import (
    ReportArtifactIncompleteError,
    ReportArtifactIntegrityError,
    ReportArtifactNotFoundError,
    ReportArtifactNotDraftError,
    ReportContractHashMismatchError,
    ReportContractInvalidError,
    ReportContractNotPublishedError,
    ReportPublishGateBlockedError,
    ReportPublishForbiddenError,
    ReportQualityNotReadyError,
    ReportReviewRequiredError,
    ReportRevisionTargetInvalidError,
    ReportReviewerForbiddenError,
)
from data_intelligence_hub.services.report_contract_v1_1 import (
    assemble_report_contract_v1_1,
    create_quick_directional_artifact,
    create_reviewed_contract_version,
)
from data_intelligence_hub.services.report_publication import (
    create_draft_artifact,
    get_current_contract,
    get_readable_artifact,
    list_revisions,
    publish_artifact,
    record_review,
)
from data_intelligence_hub.services.report_reviewers import request_reviewer_assignment
```

在 `@router.get("/{report_id}")` **之前**插入：
```python
@dataclass(frozen=True)
class InternalReviewerContext:
    """内部审核人的受限读上下文。不是客户工作区角色。"""

    user: User
    workspace: Workspace
    report_id: uuid.UUID
    assignment: ReportReviewerAssignment


async def get_internal_reviewer_context(
    report_id: uuid.UUID,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> InternalReviewerContext:
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_artifact_not_found",
        )
    workspace = await session.get(Workspace, report.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_artifact_not_found",
        )
    assignment = await get_active_reviewer_assignment(
        session,
        report_id=report_id,
        reviewer_user_id=user.id,
    )
    if assignment is None or assignment.assignment_scope != "report_review":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="reviewer_assignment_required",
        )
    return InternalReviewerContext(
        user=user,
        workspace=workspace,
        report_id=report_id,
        assignment=assignment,
    )


async def _require_report_admin(
    session: SessionDep,
    context: AuthContext,
) -> None:
    if context.workspace.owner_id == context.user.id:
        return
    role = await get_workspace_member_role(
        session,
        workspace_id=context.workspace.id,
        user_id=context.user.id,
    )
    if role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ReportPublishForbiddenError.message,
        )


@router.post("/drafts", response_model=ReportArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_report_draft_item(
    payload: ReportDraftRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ReportArtifactResponse:
    await _require_report_admin(session, context)
    task = await get_workbench_task_scoped(
        session,
        workspace_id=context.workspace.id,
        task_id=payload.task_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task_not_found",
        )
    generated_at = payload.generated_at or datetime.now(UTC)
    try:
        if task.package_type == "quick":
            draft = await create_quick_directional_artifact(
                session,
                workspace=context.workspace,
                report=None,
                task=task,
                run_id=payload.run_id,
                template_id=payload.template_id,
                generated_at=generated_at,
                created_by=context.user,
            )
            return ReportArtifactResponse.from_model(draft.artifact)
        contract = await assemble_report_contract_v1_1(
            session,
            workspace_id=context.workspace.id,
            task=task,
            run_id=payload.run_id,
            template_id=payload.template_id,
            generated_at=generated_at,
        )
        artifact = await create_draft_artifact(
            session,
            workspace=context.workspace,
            report=None,
            template_id=payload.template_id,
            contract=contract.model_dump(mode="json"),
            created_by=context.user,
            project_id=task.project_id,
            run_id=payload.run_id,
        )
    except ReportQualityNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except ReportContractInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    return ReportArtifactResponse.from_model(artifact)


@router.post("/{report_id}/reviewers", status_code=status.HTTP_201_CREATED)
async def assign_report_reviewer_item(
    report_id: uuid.UUID,
    payload: ReviewerAssignmentRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> dict[str, str]:
    await _require_report_admin(session, context)
    report = await get_report(session, context.workspace.id, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_artifact_not_found",
        )
    try:
        assignment = await request_reviewer_assignment(
            session,
            workspace=context.workspace,
            report=report,
            reviewer_user_id=payload.reviewer_user_id,
            assignment_scope=payload.assignment_scope,
            assigned_by=context.user.id,
            now=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    except ReportReviewerForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    return {
        "assignment_id": str(assignment.id),
        "reviewer_user_id": str(assignment.reviewer_user_id),
        "assignment_scope": assignment.assignment_scope,
        "status": assignment.status,
    }


@router.delete("/{report_id}/reviewers/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_report_reviewer_item(
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> None:
    await _require_report_admin(session, context)
    revoked = await revoke_reviewer_assignment(
        session,
        report_id=report_id,
        reviewer_user_id=user_id,
        revoked_at=datetime.now(UTC),
    )
    if revoked is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reviewer_assignment_invalid",
        )


@router.get("/{report_id}/contract")
async def get_report_contract_item(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> JSONResponse:
    try:
        _, payload = await get_current_contract(
            session,
            workspace=context.workspace,
            report_id=report_id,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportContractNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportContractHashMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return JSONResponse(content=payload)


@router.get("/{report_id}/artifact", response_model=ReportArtifactResponse)
async def get_report_artifact_item(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportArtifactResponse:
    artifact = await get_latest_artifact(
        session,
        workspace_id=context.workspace.id,
        report_id=report_id,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ReportArtifactNotFoundError.message,
        )
    return ReportArtifactResponse.from_model(artifact)


@router.get("/{report_id}/revisions", response_model=list[ReportArtifactResponse])
async def list_report_revision_items(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[ReportArtifactResponse]:
    try:
        revisions = await list_revisions(
            session,
            workspace=context.workspace,
            report_id=report_id,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [ReportArtifactResponse.from_model(item) for item in revisions]


@router.get("/{report_id}/sop", response_class=HTMLResponse)
async def get_report_sop_item(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> HTMLResponse:
    try:
        artifact = await get_readable_artifact(
            session,
            workspace=context.workspace,
            report_id=report_id,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportContractNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportArtifactIncompleteError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except (ReportArtifactIntegrityError, ReportContractHashMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    if artifact.sop_html is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ReportArtifactIncompleteError.message,
        )
    return HTMLResponse(
        content=artifact.sop_html,
        media_type="text/html; charset=utf-8",
    )


@router.post(
    "/{report_id}/reviews",
    response_model=ReportAuditEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report_review_item(
    report_id: uuid.UUID,
    payload: ReportReviewRequest,
    session: SessionDep,
    context: Annotated[InternalReviewerContext, Depends(get_internal_reviewer_context)],
) -> ReportAuditEventResponse:
    assignment = await get_active_reviewer_assignment(
        session,
        report_id=report_id,
        reviewer_user_id=context.user.id,
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="reviewer_assignment_required",
        )
    artifact = await get_latest_artifact(
        session,
        workspace_id=context.workspace.id,
        report_id=report_id,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ReportArtifactNotFoundError.message,
        )
    try:
        if payload.decision == "approve":
            result = await create_reviewed_contract_version(
                session,
                workspace=context.workspace,
                report_id=report_id,
                artifact_id=artifact.id,
                reviewer=context.user,
                assignment=assignment,
                decision=payload.decision,
                review_scope=payload.review_scope,
                notes=payload.notes,
                expected_contract_sha256=payload.contract_sha256,
            )
            event = result.event
        else:
            event = await record_review(
                session,
                workspace=context.workspace,
                report_id=report_id,
                artifact_id=artifact.id,
                reviewer=context.user,
                assignment=assignment,
                decision=payload.decision,
                review_scope=payload.review_scope,
                notes=payload.notes,
                expected_contract_sha256=payload.contract_sha256,
            )
    except ReportReviewerForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
        ) from exc
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (ReportArtifactNotDraftError, ReportContractHashMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except ReportContractInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    return ReportAuditEventResponse.from_model(event)


@router.post("/{report_id}/publish", response_model=ReportArtifactResponse)
async def publish_report_item(
    report_id: uuid.UUID,
    payload: ReportPublishRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> ReportArtifactResponse:
    await _require_report_admin(session, context)
    artifact = await get_latest_artifact(
        session,
        workspace_id=context.workspace.id,
        report_id=report_id,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ReportArtifactNotFoundError.message,
        )
    try:
        published = await publish_artifact(
            session,
            workspace=context.workspace,
            report_id=report_id,
            artifact_id=artifact.id,
            publisher=context.user,
            expected_contract_sha256=payload.contract_sha256,
            allow_inherited_review=True,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ReportArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (
        ReportArtifactNotDraftError,
        ReportContractHashMismatchError,
        ReportReviewRequiredError,
        ReportPublishGateBlockedError,
        ReportRevisionTargetInvalidError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except (ReportContractInvalidError, ReportForbiddenLanguageError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    return ReportArtifactResponse.from_model(published)
```

`reports.drafts.create` 首期对 Standard 使用 C8 默认结论 `insufficient_evidence`；显式 `enter`、`do_not_enter`、`conditional_enter` 与四个测试字段由内部构建调用传入 `requested_conclusions` 和测试字段，路由不猜测结论。Quick 走 `create_quick_directional_artifact`，不进入 Standard 分支。

- [ ] **Step 5: 列表带产物摘要**

在 `api/routes/reports.py` 的 `list_report_items` 中改为：
```python
    reports = await get_reports(session, context.workspace, project_id=project_id)
    artifacts = await latest_artifacts_for_reports(
        session,
        workspace_id=context.workspace.id,
        report_ids=[report.id for report in reports],
    )
    return [
        ReportResponse.from_model(report, artifact=artifacts.get(report.id))
        for report in reports
    ]
```

- [ ] **Step 6: 运行测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/integration/test_report_publication_routes.py -v
```
Expected: `6 passed`。

- [ ] **Step 7: 静态检查**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run ruff check src/data_intelligence_hub/api/routes/reports.py \
  src/data_intelligence_hub/schemas/report.py \
  src/data_intelligence_hub/repositories/report_artifacts.py
uv run mypy src/data_intelligence_hub/api/routes/reports.py src/data_intelligence_hub/schemas/report.py
```
Expected: ruff 无输出；mypy `Success`。

- [ ] **Step 8: GitNexus 变更检查并提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs impact "list_report_items" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_report_or_raise" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/api/routes/reports.py \
  apps/api/src/data_intelligence_hub/schemas/report.py \
  apps/api/src/data_intelligence_hub/repositories/report_artifacts.py \
  apps/api/tests/integration/test_report_publication_routes.py
git commit -m "feat(report): 合同、产物、SOP、审核与发布端点"
```
Expected: impact 列出路由调用方；`detect-changes` 干净；提交成功。

---

### Task 7: C14 浏览器交接（C9 不改控制台）

**Files:** 无。C9 不修改 `apps/scraper-console/**`，不创建 Playwright 用例。

**Interfaces:**
- Consumes: Task 6 的 `/artifact`、`/contract`、`/sop`、`/revisions`、`/reviews`、`/publish` 端点。
- Produces: C14 可直接执行的报告页交接清单。

- [ ] **Step 1: 固定 API 响应字段**

`GET /api/reports/{report_id}/artifact` 返回：

```text
id, report_id, status, version, template_id,
contract_sha256, data_sha256, report_html_sha256,
sop_html_sha256, combined_sha256,
supersedes_id, created_by, published_at, published_by,
superseded_at, created_at
```

`GET /api/reports/{report_id}/contract` 在未发布时返回 404，`detail` 为 `report_contract_not_published`；已发布时返回 `contract_json`。`GET /sop` 在未发布时同样返回 404。`GET /revisions` 返回按发布时间倒序的产物链。

- [ ] **Step 2: 写 C14 交接清单**

C14 负责修改报告中心与报告阅读页，并创建 `apps/scraper-console/e2e/report-page.spec.ts`。控制台由 C14 实现，由 PG0 发布批次部署；C14 只做只读验收。交接断言：

1. 报告中心显示结论句、最低证据等级与发布状态。
2. 状态标签：`draft` 显示“草稿”，`published` 显示“已发布”，`superseded` 显示“已被取代”。
3. 报告阅读页显示三个哈希行：合同、数据、渲染；值来自 `artifact`，不从合同重新计算。
4. 未发布时显示“本合同尚未发布”，不得显示空值、`0` 或“数据未生成”。
5. 已发布时显示内部审核人（`reviewer_role=internal_reviewer`）、审核时间与修订链；owner/admin 只看到“分配内部审核人”与“发布”，不得出现客户自审入口。
6. 页面不得调用模型或重新拼合同；只读 API 字段。
7. 草稿创建因质量未就绪失败时，页面显示 `report_quality_not_ready`，不得显示空合同或“数据未生成”。
8. 报告页面只显示后端合同与质量字段，不重新计算质量状态、样本数或独立来源。
9. 审核版本与交付版本各有一行修订记录；旧版本的合同哈希不得变化。
10. 浏览器 console 无错误。
11. Quick 方向稿显示“方向性、未审核”：合同 `review.status='draft'`，`markets[]` 只有 `conclusion_quick`，没有 `conclusion_standard`；页面不得显示 `confirmed`、最终四态或验收入口。24 小时正式版显示 `review.status='approved'` 与内部审核人，修订链包含方向稿与正式版两行，且两行属于同一 `task_id` / `order_id`。

- [ ] **Step 3: 运行后端路由测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/integration/test_report_publication_routes.py -v
```

Expected: 全部通过。测试覆盖 404 `report_contract_not_published`、三个哈希、审核与发布权限。

- [ ] **Step 4: 确认无控制台改动**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c9
git status --porcelain apps/scraper-console
```

Expected: 无输出。C14 在独立切片实现控制台与 Playwright。

**发布交接。** C9 不直接部署任何环境，不执行生产发布、A/B 切换或回滚。A、B 两套生产的发布、切换与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；C9 只交付迁移 065、测试证据与上述交接清单。PG0 发布批次先备份，A 先 canary，B 在目标授权、备份校验与迁移门禁通过后发布。

---

### Task 8: 全量验收、GitNexus 与提交

**Files:**
- Read: 所有改动文件
- Test: 后端全量相关测试

**Interfaces:**
- Consumes: Task 1–7 的全部产物。
- Produces: 一份可复核的完成证据；不新增报告文件。

- [ ] **Step 1: 后端定向与全量测试**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest \
  tests/unit/test_report_contract_profile.py \
  tests/unit/test_report_contract_v1_1.py \
  tests/unit/test_report_quick_directional.py \
  tests/unit/test_report_reviewers.py \
  tests/unit/test_report_publication.py \
  tests/unit/test_report_pii_gate.py \
  tests/unit/test_report_publication_migration.py \
  tests/unit/test_report_artifacts.py \
  tests/unit/test_report_builder.py \
  tests/unit/test_report_contract.py \
  tests/unit/test_report_renderers.py \
  tests/unit/test_mcp_tools_b5.py \
  tests/integration/test_report_publication_routes.py -v
uv run ruff check .
uv run mypy src
uv run alembic heads
```
Expected: 全部 `passed`；ruff 无输出；mypy `Success`；Alembic 只有一行 `202610220065 (head)`。

- [ ] **Step 2: 确认 C14 交接边界**

C9 不运行控制台测试。C14 在独立切片运行 `npm test`、`npx tsc --noEmit` 与 `npm run test:e2e -- e2e/report-page.spec.ts`，并按 Task 7 的交接清单验收。

- [ ] **Step 3: 离线可重复性检查**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9/apps/api
uv run pytest tests/unit/test_report_contract.py tests/unit/test_report_renderers.py -v
```
Expected: 两次运行结果一致；渲染器测试包含“同一输入连调两次输出相同”。

- [ ] **Step 4: 确认没有第二套报告实现**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
test ! -d apps/api/src/data_intelligence_hub/modules/reports && echo no-second-report-module
test ! -e apps/api/src/data_intelligence_hub/services/delivery_manifest.py && echo no-manifest-bundle
git grep -n "delivery_manifest\|report_contract_v2\|ClaimStateV2" -- apps/api/src || true
```
Expected: `no-second-report-module` 与 `no-manifest-bundle`；`git grep` 无命中。

- [ ] **Step 5: GitNexus 全量变更检查**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
node .gitnexus/run.cjs detect-changes --scope all --repo .
```
Expected: 输出不含 `partial: true` 或 `truncated: true`。若含，重跑；仍含时停止提交并在交付记录中写明未检查范围。

- [ ] **Step 6: 最终提交**

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c9
git status --short
git add \
  apps/api/alembic/versions/202610220065_report_publication.py \
  apps/api/src/data_intelligence_hub/models/report_artifact.py \
  apps/api/src/data_intelligence_hub/models/report.py \
  apps/api/src/data_intelligence_hub/repositories/report_artifacts.py \
  apps/api/src/data_intelligence_hub/repositories/workspaces.py \
  apps/api/src/data_intelligence_hub/services/report_contract_v1_1.py \
  apps/api/src/data_intelligence_hub/services/report_reviewers.py \
  apps/api/src/data_intelligence_hub/services/report_publication.py \
  apps/api/src/data_intelligence_hub/services/report_artifacts.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/src/data_intelligence_hub/schemas/report.py \
  apps/api/src/data_intelligence_hub/api/routes/reports.py \
  apps/api/src/data_intelligence_hub/mcp_runtime/tools/reports.py \
  apps/api/src/data_intelligence_hub/mcp_runtime/server.py \
  apps/api/tests/unit/test_report_contract_profile.py \
  apps/api/tests/unit/test_report_contract_v1_1.py \
  apps/api/tests/unit/test_report_quick_directional.py \
  apps/api/tests/unit/test_report_reviewers.py \
  apps/api/tests/unit/test_report_publication.py \
  apps/api/tests/unit/test_report_pii_gate.py \
  apps/api/tests/unit/test_report_publication_migration.py \
  apps/api/tests/postgres/test_report_publication_constraints.py \
  apps/api/tests/integration/test_report_publication_routes.py \
  apps/api/tests/unit/test_mcp_tools_b5.py
git commit -m "feat(report): C9 受治理报告合同与产物发布"
```
Expected: 提交成功，工作区干净。

---

## 验收对照

| 要求 | 落点 |
|---|---|
| 契约只读 | Task 1 只读 C1 registry 的 `ck_report_artifacts_status`、`uq_report_artifacts_current_published`、`reviewer_role`；缺项返回 C1 |
| 复用 B5 合同 schema 与 JSON Schema | Task 4、Task 5 只 import，不复制 |
| 复用 B5 builder/renderers/artifacts/templates | Task 4 抽出 `render_contract_pages`，Task 5 让 MCP 复用 |
| canonical profile 冻结 | Task 2 锁定 C1 的 `dih-canonical-json-v1` 与 `1.1.0` |
| `report_artifacts.contract_json` 唯一内容源 | Task 4 `get_current_contract`、Task 6 路由、Task 7 交接清单 |
| published 不可变 | Task 3 数据库触发器、Task 4 服务状态机、Task 3 PostgreSQL 测试 |
| 修订 supersedes | Task 4 `supersedes_id` 与 `superseded` 转换、Task 6 revisions 端点 |
| HTML/SOP 纯渲染 | Task 4 `render_contract_pages` 纯函数、Task 6 SOP 只读已存 HTML 并复核哈希 |
| 人工审核事件 | Task 4 `record_review` 写 `report_review_approved` 与 `reviewed_*` metadata、Task 6 reviews 端点、Task 3 只追加触发器 |
| 一个迁移 065 | Task 3 `202610220065_report_publication.py` |
| 不建 `modules/reports` | Global Constraints 与 Task 8 检查 |
| 不做 manifest bundle | Global Constraints 与 Task 8 检查 |
| 报告构建前质量门禁 | Task 4A `assemble_report_contract_v1_1` 与 Task 4 `create_draft_artifact` 在写产物前调用 C8 `ensure_market_quality`；失败抛 `ReportQualityNotReadyError`（`report_quality_not_ready`） |
| 1.1 装配器与 C8 映射 | Task 4A 装配 29 个顶层键；`markets` / `datasets` / `scorecard` 来自 C8；三档质量参数化测试 |
| C7 Claim 装配 | Task 4A `load_publishable_claim_rows(..., task_id=...)` + `validate_claim_bundle`；`claims` / `evidences` / `scorecard.claims` 来自已审核 bundle；pending/stale 拒绝；Task 4 发布前用 `claim_review_digest` 复核 bundle 未变 |
| C8 结论语义 | Task 4A `validate_conclusion`：Standard `enter` 3–5 候选、`do_not_enter` 2 个独立簇、`conditional_enter` 四个测试字段；失败不写入草稿 |
| Quick 2 小时方向稿 | Task 4A `create_quick_directional_artifact`；L3 上限、无 `confirmed`、无 `conclusion_standard`、无 `sku_candidates`、不触发验收 |
| Quick 24 小时正式版 | Task 4A `create_reviewed_contract_version` 创建 `report_version=2`；同一 `report_id` / `task_id` / `order_id`；不新建 run 或账本，不重复收费 |
| C11 PII 门禁 | Task 4 `scan_contract_pii` 扫描合同、claims、evidence 与两页；命中写 `gate_evaluated` 阻断事件并保持 `draft`；C11 接口缺失时停止 |
| 报告契约不可变生命周期 | Task 4A `draft_placeholders`、`create_reviewed_contract_version`、`create_delivery_contract_version`；旧行的 `contract_json` 字节不变 |
| 内部审核人 | Task 3 表、Task 4A 服务、Task 6 `get_internal_reviewer_context`；客户 owner/admin 自审返回 403 |
| 唯一 task_id | Task 4A `assert_single_task_id`；顶层 `task_id` 权威，`identity.task_id` 镜像必须相等 |
| 错误码 | `report_quality_not_ready`、`reviewer_assignment_required`、`reviewer_assignment_expired`、`reviewer_self_review_forbidden`、`reviewer_assignment_invalid`、`report_forbidden_language` 全部由 C1 先登记 |
| 质量依赖方向 | C8 依赖 C6 的 `run.completed`；C9 依赖 C8 的 `ensure_market_quality`；C9 不写 `market_assessments` / `data_gaps` |
| C14 浏览器交接 | Task 7 的交接清单；C9 不改控制台、不建 Playwright |
| 不直接部署 | Global Constraints 与 Task 7 发布交接；A、B 两套生产的发布、切换与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收 |
| C7/C8 前置 | Task 0 检查 058–064 迁移与 `feat/gov-c8` 分支 |
| GitNexus 强制 | 每个代码任务的 impact 与 detect-changes 步骤 |

## 非目标

- 不实现 `delivery_manifest.json`、交付 bundle、分享链接、导出 PDF、验收快照。
- 不实现订单、计划、run、claim 或证据等级的创建逻辑；这些属于 C2–C8。
- 不新增 `modules/reports` 包，不新增第二套合同模型或 claim 枚举。
- 不把 `reports.content` 迁移成合同来源；它只是旧版正文的只读回退。

## 执行顺序与停止条件

1. Task 0 任一检查失败：停止，不创建分支。
2. Task 1 C1 registry 缺 `ck_report_artifacts_status`、`uq_report_artifacts_current_published` 或 `reviewer_role`：停止并返回 C1，不写迁移。
3. Task 2 profile 不是 `dih-canonical-json-v1/1.1.0`：停止，先修 C1。严格 RFC 8785 不在本切片实施。
4. Task 3 PostgreSQL 触发器测试在受控库失败：停止发布，先修触发器。
5. Task 6 合同端点返回的内容与 `contract_json` 不完全一致：停止，不允许上线。
6. Task 7 交接清单与后端路由测试不一致：停止，先修 API 或交接文档。
7. 任何 `detect-changes` 返回 `partial: true` 或 `truncated: true`：停止提交，重跑图谱检查。
