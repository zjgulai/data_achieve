# 受治理任务平台 C8 数据集质量与任务包模板实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为受治理任务平台补上数据集内容哈希、逐市场质量记分卡、结构化缺口和首期唯一母婴新品任务包模板，并让 `/assets` 能显示质量状态与缺口。

**Architecture:** 从前置切片 C7 的前置分支 `feat/gov-c7` 创建独立 worktree，复用 B5 的报告/Claim 实现，不另建第二套 Claim、报告合同或报告产物。数据集层新增 `dataset_versions.content_sha256`、`schema_hash`、`quality_status` 等契约列；质量记分卡写入 C8 在迁移 064 唯一创建的 `market_assessments`，缺口写入 C8 在迁移 064 唯一创建的 `data_gaps`。任务包模板只存在于代码注册表，Quick/Standard 阈值只存在于 `tool_catalog/evidence_thresholds.py`。C8 不渲染报告，不生成交付包。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pydantic v2、pytest、PostgreSQL。控制台与 Playwright 由 C14 负责。

## Global Constraints

- **开关与回滚。** 本切片不新增布尔开关，入口受 `GOVERNED_TASK_PLATFORM_ENABLED` 控制；回滚点是迁移 `064` 的 `downgrade` 与发布前数据库备份，生产回滚用备份恢复或新迁移，不手改 `alembic_version`。
- 基线分支必须从前置切片 C7 的前置分支 `feat/gov-c7` 创建独立 worktree：`git worktree add /Users/lute/Project/data_scrapy-gov-c8 -b feat/gov-c8 feat/gov-c7`。该分支已包含 C0–C7 与 C1 契约，Alembic head 必须是 `202610220063`。禁止从 `main`、`feat/b5-workbench` 或 `feat/tool-catalog-catalog` 直接建 C8，也不得在 worktree 内合并 C1–C7。
- B5 的 `models/claim.py`、`models/intelligence.py` 的 `Evidence`、`schemas/report_contract.py`、`services/report_builder.py`、`services/report_templates.py`、`models/report_artifact.py` 是报告与 Claim 的唯一基线。C8 不新建 `claims_v2`、`report_contract_v2`、`report_artifacts_v2`，也不复制这些模型。
- B5 的 `schemas/report_contract.py` 的 `canonical_json_bytes` 明确写着“RFC 8785 的近似，不是完整实现”。C1 冻结 `CANONICAL_PROFILE_ID = "dih-canonical-json-v1"` 作为唯一 v1 profile，绑定该近似实现；严格 RFC 8785 升级延期，未来若实施必须使用不同 ID `dih-canonical-json-rfc8785-v1`，不得改变 v1 的字节输出。C8 直接 import C1 的 `canonical_json_bytes`，不实现第二套 canonicalizer，也不得声明 v1 是完整 RFC 8785。
- **契约只读。** C1 的 `configs/contracts/v1.1.0/registry.json` 是唯一机器契约，`docs/design/【契约冻结】v1-表名-枚举-接口.md` 是唯一权威。C8 只读这两份 C1 产物做门禁，不修改契约文档、不修改 registry、不追加“C8 实现决定”，也不新增未登记对象、枚举值或 API 路径。Task 1 缺任一登记项时停止并返回 C1 补充登记。契约文档与 `registry.json` 不在本切片的修改清单和提交范围内。
- C4、C6、C7 是前置：
  - C4 提供 `workbench_tasks`（含 `package_type`、`primary_market`、`comparison_markets`）、`workflow_versions.workbench_task_id` 与 `runs.market_code`。`market_role` 与 `package_type` 从 `workbench_tasks` 派生，`runs` 不存这两列。
  - C6 提供 `runs`、`run_steps`、`run_step_attempts` 与 `run.completed` 审计事件。C8 依赖 C6；C6 不依赖 C8。
  - C7 提供 `services/source_clusters.py` 与 `evidences.source_cluster_key`。C8 通过 `KeyClaimBinding` 入参消费 Claim，不查询第二套 Claim 表。
  - C5 的预算与账本不在 C8 范围；C5 是 C6/C7 的上游。
- 迁移只有一个：`apps/api/alembic/versions/202610220064_dataset_quality.py`。`revision = "202610220064"`，`down_revision = "202610220063"`。它扩展 `dataset_versions`，并创建 `market_assessments` 与 `data_gaps`。它不创建 `report_templates`、`delivery_manifests`。C5 的迁移 061 不创建这两张质量表，所以由 C8 在 064 创建，解决总索引 §1.1 第 7 条的阻塞。
- C4/C6 创建正式数据集版本时必须写 `task_id` 与 `market`。C8 的三个 legacy 保存路径保持这两个列为 null，`/assets` 显示“未评分”，不伪造 `not_qualified`。
- 质量门槛固定为：核心域 3/3；商品 Quick ≥20、Standard ≥100；评论 Quick ≥300、Standard ≥2,000；达人内容 Quick ≥50、Standard ≥200；核心字段完整率 ≥80%；重复率 <2%；来源 URL 覆盖率 100%；关键 Claim 证据绑定率 100%；关键判断独立来源 ≥2。前四项按市场分别计算，不按整包合计。
- `missing` 不得写成数值 0。数据域没有合格记录时，`sample_counts` 写 JSON `null`，`data_gaps.actual_value` 写 JSON `null`。
- `blocked` 不得写成空结果。数据域被市场、权限、配置、条款或上游阻断时，状态写 `blocked`，实际值写 `null`，并写缺口。
- 独立来源按原始记录簇计算。同一 provider 的不同端点、同一端点的多次调用、同一页面的多条抓取路径、同一记录的翻译/转载/不同导出格式、两把不同 API Key，都只算一个来源。
- Quick 的证据上限是 `L3_live_single`。Standard 达标时允许 `L4_authorized_live`。C8 不提升证据等级。
- 任务包模板的事实源是代码注册表 `apps/api/src/data_intelligence_hub/services/workbench_templates.py`。C8 不建 `task_templates` 表。`report_templates` 与 `report_template_versions` 是 B5 的 `services/report_templates.py` 代码注册表，C9 只读；C8 不创建、不写入。
- **模板能力白名单冻结。** `TaskTemplate.capability_allowlist` 只存现有工具目录的稳定 `tool_id`（`build_tool_catalog` 产出的 `ToolDescriptor.tool_id`）。首期模板使用显式冻结列表，不按目录谓词动态展开，也不回退到全部工具。`creator_cookie` 门控能力 `tikhub_tiktok_video_products`、`tikhub_tiktok_creator_showcase` 不在白名单。`template_capability_ids(template_id)` 是唯一读取入口；未知模板抛 `KeyError`，空白名单返回空元组并让调用方拒绝全部能力（失败关闭）。白名单进入 `template_registry_digest`，变化触发 `quality.template.changed` 审计。本项不新增列、路径或错误码；`capability_not_allowed` 已由 C1 登记。
- 不写报告渲染、HTML/PDF、`report_contract.json`、`delivery_manifest.json`、分享页或验收事件。
- 每个 task 先写失败测试，运行并确认失败，再写最小实现，运行并确认通过，最后 commit。
- 改既有符号前必须运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。`risk` 为 HIGH 或 CRITICAL 时必须停下并报告；`risk` 为 UNKNOWN 时必须用文本搜索确认调用面。
- 提交前必须运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。出现 `partial: true` 或 `truncated: true` 时不算通过，必须重跑。
- 后端命令在 `apps/api` 下执行，统一用 `uv run`。C8 不运行或修改控制台；前端命令与 Playwright 由 C14 负责。
- **不直接部署。** 本切片不直接部署任何环境，不执行生产发布、A/B 切换或回滚。A、B 两套生产的发布与回滚由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；C8 只交付迁移、测试证据与交接清单。
- **C1 登记边界。** C8 不新增 API 路径、表、列、枚举或公开错误码。C8 只消费 C1 `report_contract` schema 已登记的 `markets`、`datasets`、`scorecard` 与 `$defs` 中的 `market_assessment`、`dataset`、`scorecard`、`gap`、`sku_candidate`；Task 1 缺任一项时停止并返回 C1 补充登记。C8 的审计 `action` 是 C2 contract 的自由字符串；若 C1 后续把 `audit_events.action` 登记为枚举，Task 1 必须包含 `quality.assessment.computed`、`quality.gap.resolved`、`quality.template.changed` 三个值，缺项返回 C1。
- **项目 ACL 是唯一授权接缝。** C8 的资产、数据集、市场记分卡与缺口读写一律调用 C2 的 `require_project_access`，不新建第二套授权函数、不直接比较 `project_members`。同工作区但未授权项目的 member 返回 403 `project_access_forbidden`；跨工作区返回 404 `project_not_found`；owner/admin 通过。`GET /api/automation/product-datasets` 在未传 `project_id` 时用 `require_workspace_role` 确认成员身份，member 只返回其 `project_members` 可见项目；不得返回同工作区其他项目的数据集。服务层写质量前必须校验 `run.workspace_id`/`run.project_id` 与 `workbench_tasks` 归属一致，跨项目或跨工作区归因失败抛 `MarketQualityNotReadyError("project_mismatch")`。
- **C8 写操作必须写 C2 审计。** 质量计算、缺口解除、模板/阈值配置变化都调用 C2 的 `services.audit_log.append_audit_event`，不新建审计表、不复制哈希链、不因开关关闭跳过。C8 只使用三个 action：`quality.assessment.computed`、`quality.gap.resolved`、`quality.template.changed`。审计 `details` 只写 ID、市场、状态、摘要哈希与原因码，不写原始 PII、Cookie、密钥或正文。
- **结论语义由 C8 校验、C9/C10 发布。** C8 只产出 `allowed_conclusions` 并校验请求结论，不写报告、不发布、不生成交付包。Standard `enter` 必须由 3–5 个非暂定 SKU 候选支撑；`conditional_enter` 必须同时提供测试预算、观察窗口、成功阈值与止损线；`do_not_enter` 必须由 C7 的至少两个独立来源簇支撑；任一条件不满足时 C8 返回 `None` 与原因码，C9/C10 不得发布该结论。三项语义是已批准输入的校验规则，不是新阈值。
- **调度与生产激活属于 PG0。** `scripts/market_quality_backfill.py` 的 scheduler 注册、后台循环启动、生产存量 backfill、开关设置与 A/B 发布都由 PG0 发布批次执行并留证；C8 只交付脚本、测试与操作说明，C14 只做只读验收，不得注册任务、启动循环或写生产数据。
- 每个代码步骤给出可执行内容；占位符扫描必须通过。

## 前置门禁

执行 Task 1 前，必须全部满足：

```bash
cd /Users/lute/Project/data_scrapy
git worktree add /Users/lute/Project/data_scrapy-gov-c8 -b feat/gov-c8 feat/gov-c7
cd /Users/lute/Project/data_scrapy-gov-c8
git rev-parse --verify feat/gov-c7^{commit}
git merge-base --is-ancestor feat/gov-c7 HEAD && echo C7_BRANCH_BASE_OK
```

Expected: 当前目录是 `data_scrapy-gov-c8` worktree；`feat/gov-c7` 可解析；输出 `C7_BRANCH_BASE_OK`；HEAD 等于前置分支提交。不得在 worktree 内合并 C1–C7。

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run alembic heads
```

Expected: `202610220063 (head)`。不是这个值就停止，先合入 C1-C7 的迁移。

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
test -f configs/contracts/v1.1.0/registry.json
uv run python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: exit code 0。

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run python - <<'PY'
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.services.source_clusters import (
    SourceCluster,
    assign_link_clusters,
    normalise_url,
    resolve_source_cluster,
)

assert Claim.__tablename__ == "claims"
assert ClaimEvidence.__tablename__ == "claim_evidence"
assert "workbench_tasks" in Base.metadata.tables
assert "runs" in Base.metadata.tables
assert callable(normalise_url)
assert callable(resolve_source_cluster)
assert callable(assign_link_clusters)
print("c8 prerequisites ok")
PY
```

Expected: `c8 prerequisites ok`。任一 import 或断言失败就停止，先合入 C4/C6/C7。

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run python - <<'PY'
import json
from pathlib import Path

schema = json.loads(
    Path("schemas/report_contract.schema.json").read_text(encoding="utf-8")
)
assert {"markets", "datasets", "scorecard"} <= set(schema["required"])
assert {
    "market_assessment",
    "dataset",
    "scorecard",
    "gap",
    "sku_candidate",
} <= set(schema["$defs"])
market = schema["$defs"]["market_assessment"]
assert {
    "market",
    "market_role",
    "quality_status",
    "evidence_grade",
    "domains",
    "sample_counts",
    "thresholds",
    "gaps",
} <= set(market["required"])
dataset = schema["$defs"]["dataset"]
assert {
    "dataset_version_id",
    "market",
    "row_count",
    "content_sha256",
    "schema_hash",
} <= set(dataset["required"])
print("c8 report contract sections ok")
PY
```

Expected: `c8 report contract sections ok`。缺项时停止 C8，把缺失的 registry/schema 对象返回 C1 补充登记；C8 不修改 schema 或 registry。

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs status
```

Expected: `status` 的“索引提交”等于 `git rev-parse HEAD`。索引过期时先重新分析。

## 跨切片质量链依赖（C8 依赖 C6）

```mermaid
graph LR
  C2[C2 身份 ACL 与审计] -->|require_project_access / append_audit_event| C8[C8 质量消费]
  C6[C6 Run 执行收敛] -->|audit_events.action=run.completed| C8
  C8 -->|ensure_market_quality / validate_conclusion| C9[C9 报告草稿构建]
  C8 -->|load_report_quality_sections| C9
  C8 -->|dataset_versions.quality_status / preview| C14[C14 /assets]
  PG0[PG0 发布批次] -->|注册 backfill 调度并执行生产 backfill| C8
```

- C2 提供 `api.authz.require_project_access` 与 `services.audit_log.append_audit_event`。C8 只调用，不复制授权或审计实现。C8 的审计动作见 Global Constraints。
- C6 在 run 的全部 step 进入终态且 `runs.status='completed'` 后只发 `run.completed` 审计事件。C6 不 import C8，不计算质量。
- C8 依赖 C6 的 `runs`、`run_steps`、`run_step_attempts` 与 `run.completed` 事件。C8 的 `consume_completed_runs` / `consume_run_completed_events` 负责把事件变成 `market_assessments` 与 `data_gaps`。
- C9 依赖 C8 的 `ensure_market_quality`、`validate_conclusion` 与 `load_report_quality_sections`。报告草稿构建前必须确保质量存在，并按 C1 `report_contract` 的 `markets`/`datasets`/`scorecard` 形状装载 C8 输出。
- C14 依赖 C8 的 `/assets` 响应字段。控制台只显示，不重算。
- PG0 发布批次负责 scheduler 注册、生产 backfill 与开关激活；C14 只读。

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `apps/api/src/data_intelligence_hub/services/dataset_content_hash.py` | Create | `content_sha256` 与 `schema_hash` 的唯一计算入口。 |
| `apps/api/src/data_intelligence_hub/tool_catalog/evidence_thresholds.py` | Modify | 追加 `PackageTier`、`PackageTierThreshold`、`QualityGateThresholds`、`PACKAGE_TIER_THRESHOLDS`。 |
| `apps/api/src/data_intelligence_hub/services/workbench_templates.py` | Create | 首期唯一任务包模板的代码注册表；含冻结的 `capability_allowlist` 与 `template_capability_ids`。 |
| `apps/api/src/data_intelligence_hub/services/dataset_quality.py` | Create | 逐市场记分卡、缺口草稿、`validate_conclusion` 与内容哈希的公共入口。 |
| `apps/api/src/data_intelligence_hub/services/quality_audit.py` | Create | C8 的三个审计 action 常量与 `append_audit_event` 薄封装；不建审计表。 |
| `apps/api/src/data_intelligence_hub/services/quality_report_sections.py` | Create | 把质量行投影为 C1 `report_contract` 的 `markets`/`datasets`/`scorecard` 段。 |
| `apps/api/src/data_intelligence_hub/repositories/dataset_quality.py` | Create | 写 `market_assessments`/`data_gaps`，`set_data_gap_status`，同步 `dataset_versions.quality_status`；按 `task_id`+`market` 批量同步版本；按项目过滤读取。 |
| `apps/api/src/data_intelligence_hub/services/market_quality.py` | Create | `evaluate_and_persist_market_quality`、`ensure_market_quality`、`consume_completed_runs`、`consume_run_completed_events`、`handle_run_completed_event`；写质量与模板审计。 |
| `apps/api/src/data_intelligence_hub/api/routes/automation.py` | Modify | 资产/数据集读取与归档路由接入 `require_project_access`；传递 `AuthContext.user`。 |
| `apps/api/src/data_intelligence_hub/repositories/datasets.py` | Modify | `list_datasets`/`count_datasets` 支持 `project_ids`，供 member 的项目过滤。 |
| `scripts/market_quality_backfill.py` | Create | `--mode runs|events`、`--limit`、`--dry-run`、`--run-id`；生产执行属于 PG0。 |
| `apps/api/src/data_intelligence_hub/models/dataset.py` | Modify | 追加 `task_id`、`market`、`schema_hash`、`content_sha256`、`license_class`、`quality_status`。 |
| `apps/api/src/data_intelligence_hub/models/market_assessment.py` | Create | `market_assessments` 模型。 |
| `apps/api/src/data_intelligence_hub/models/data_gap.py` | Create | `data_gaps` 模型。 |
| `apps/api/alembic/versions/202610220064_dataset_quality.py` | Create | 唯一迁移。扩展 `dataset_versions`，创建 `market_assessments` 与 `data_gaps`。 |
| `apps/api/src/data_intelligence_hub/schemas/automation.py` | Modify | 数据集版本响应增加哈希/质量字段；版本预览增加评估与缺口。 |
| `apps/api/src/data_intelligence_hub/services/automation_service.py` | Modify | 三个保存函数写入哈希；版本预览返回质量评估与缺口。 |
| `apps/api/tests/unit/test_c8_contract_gate.py` | Create | C1 registry 只读门禁。 |
| `apps/api/tests/unit/test_dataset_canonical_profile.py` | Create | 锁定 C1 的 `dih-canonical-json-v1` 与 B5 近似行为。 |
| `apps/api/tests/unit/test_dataset_content_hash.py` | Create | 内容哈希与 schema 哈希。 |
| `apps/api/tests/unit/test_workbench_templates.py` | Create | 模板注册表、阈值引用与冻结能力白名单。 |
| `apps/api/tests/unit/test_dataset_quality.py` | Create | 质量门槛、missing/null、结论映射与结论语义校验。 |
| `apps/api/tests/unit/test_dataset_quality_repository.py` | Create | 幂等写入、项目过滤、缺口解除、审计写入与质量状态投影。 |
| `apps/api/tests/unit/test_quality_audit.py` | Create | C2 审计事件 action/resource/details、模板摘要变化与 no-op。 |
| `apps/api/tests/unit/test_market_quality_runner.py` | Create | `ensure`、消费、事件、幂等、归因失败与审计跳过。 |
| `apps/api/tests/integration/test_market_quality_backfill.py` | Create | backfill 命令端到端。 |
| `apps/api/tests/integration/test_c8_project_acl.py` | Create | 同工作区 member 跨项目 403、跨工作区 404、owner/admin 通过、member 列表过滤。 |
| `apps/api/tests/integration/test_report_quality_sections.py` | Create | `qualified`/`qualified_with_gap`/`not_qualified` 的 C9 报告段交接。 |
| `apps/api/tests/postgres_c8_dataset_quality/conftest.py` | Create | 受保护的 PostgreSQL 迁移测试夹具。 |
| `apps/api/tests/postgres_c8_dataset_quality/test_migration_064.py` | Create | 迁移升级/降级。 |
| `apps/api/tests/integration/test_dataset_export_preview.py` | Modify | 保存路径写入哈希；旧版本返回 null。 |

## Task Files Interfaces

| Task | 消费 | 产出 |
|---|---|---|
| 1 | C1 registry、B5 `Claim`/`ClaimEvidence` | C1 registry 只读门禁测试；缺项返回 C1 |
| 2 | C1 的 `schemas.report_contract` | profile 守卫测试；不新增 canonical 实现 |
| 3 | C7 `services/source_clusters.py` | 门禁测试，不新增模块 |
| 4 | Task 2、Task 3 | `DatasetContentDigest`、`compute_dataset_content_digest` |
| 5 | `evidence_thresholds`、`evidence_grade`、工具目录稳定 `tool_id` | `PackageTier`、`PackageTierThreshold`、`QualityGateThresholds`、`PACKAGE_TIER_THRESHOLDS`、`package_threshold_for`、`TaskTemplate`、`TaskTemplate.capability_allowlist`、`get_task_template`、`list_task_templates`、`template_capability_ids`、`template_registry_digest` |
| 6 | Task 3、Task 5 | `QualityRecord`、`DomainEvidence`、`KeyClaimBinding`、`MarketQualityInput`、`DataGapDraft`、`MarketAssessmentDraft`、`compute_market_assessment`、`allowed_conclusions`、`SkuCandidate`、`ConclusionInputs`、`ConclusionDecision`、`validate_conclusion` |
| 7 | C4 `workbench_tasks`、C6 `runs`/`run_steps`、`DatasetVersion` | 迁移 `202610220064`、`market_assessments`/`data_gaps` 模型列 |
| 8 | Task 6、Task 7、C8 模型、C2 `require_project_access`/`append_audit_event` | `get_market_assessment`、`list_data_gaps`、`set_data_gap_status`、`upsert_market_assessment`、`sync_dataset_quality_status`、`list_dataset_versions_for_task_market`、API 响应字段、路由 ACL |
| 9 | Task 6、Task 8、C6 `run.completed`、C4 `workbench_tasks`、C7 Claim、C2 审计 | `evaluate_and_persist_market_quality`、`ensure_market_quality`、`consume_completed_runs`、`consume_run_completed_events`、`handle_run_completed_event`、`load_report_quality_sections`、backfill CLI、审计事件 |
| 10 | Task 4 | 三个保存函数的 `content_sha256`/`schema_hash` |
| 11 | Task 8 的 `/assets` 响应字段、Task 9 的报告段与审计 | C9 报告段交接、C14 浏览器交接清单、PG0 调度交接；C8 不改控制台 |
| 12 | 全部 | 测试、类型检查、GitNexus 结论 |

---

### Task 1: C1 registry 只读门禁

**Files:**
- Create: `apps/api/tests/unit/test_c8_contract_gate.py`

**Interfaces:**
- Consumes: `configs/contracts/v1.1.0/registry.json`、C1 契约 v1.1、B5 的 `Claim` 与 `ClaimEvidence`。
- Produces: 测试 `test_registry_has_c8_dataset_columns`、`test_registry_has_quality_objects`、`test_registry_canonical_profile_is_b5_v1`、`test_b5_claim_tables_are_the_only_claim_tables`、`test_c8_does_not_create_a_task_template_table`、`test_c1_contract_and_registry_are_the_only_authority`。C8 不写契约；缺项返回 C1。

- [ ] **Step 1: 写只读门禁测试**

Create `apps/api/tests/unit/test_c8_contract_gate.py`:

```python
"""C8 契约门禁。

本测试只读契约与模型元数据。它不连接数据库，不写业务数据。
"""

from __future__ import annotations

import json
from pathlib import Path

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.claim import Claim, ClaimEvidence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
REGISTRY = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"
REPORT_SCHEMA = PROJECT_ROOT / "apps/api/schemas/report_contract.schema.json"


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def table(name: str) -> dict:
    registry = load_registry()
    return next(item for item in registry["tables"] if item["name"] == name)


def enum_values(name: str) -> list[str]:
    registry = load_registry()
    return next(item["values"] for item in registry["enums"] if item["name"] == name)


def test_registry_has_c8_dataset_columns() -> None:
    columns = {column["name"] for column in table("dataset_versions")["columns"]}
    assert {
        "task_id",
        "market",
        "schema_hash",
        "content_sha256",
        "license_class",
        "quality_status",
    } <= columns


GAP_COLUMNS = {
    "id",
    "workspace_id",
    "project_id",
    "task_id",
    "run_id",
    "step_id",
    "market",
    "data_domain",
    "reason_code",
    "actual_value",
    "threshold_value",
    "impact",
    "customer_text_zh",
    "customer_text_en",
    "remediation",
    "severity",
    "status",
    "created_at",
    "resolved_at",
}
ASSESSMENT_COLUMNS = {
    "id",
    "workspace_id",
    "project_id",
    "task_id",
    "market",
    "market_role",
    "quality_status",
    "conclusion_standard",
    "conclusion_quick",
    "evidence_grade",
    "core_domain_coverage",
    "sample_counts",
    "thresholds",
    "gap_ids",
    "details_json",
    "computed_at",
}


def test_registry_has_quality_objects() -> None:
    gap_columns = {column["name"] for column in table("data_gaps")["columns"]}
    assessment_columns = {
        column["name"] for column in table("market_assessments")["columns"]
    }
    assert gap_columns == GAP_COLUMNS
    assert assessment_columns == ASSESSMENT_COLUMNS
    assert enum_values("domain_status") == ["pass", "partial", "missing", "blocked"]
    assert enum_values("market_quality_status") == [
        "qualified",
        "qualified_with_gap",
        "not_qualified",
    ]
    assert enum_values("data_gaps.severity") == [
        "info",
        "warning",
        "blocking",
        "critical",
    ]
    assert enum_values("data_gaps.status") == [
        "open",
        "mitigated",
        "accepted",
        "closed",
    ]


def test_registry_canonical_profile_is_b5_v1() -> None:
    profile = load_registry()["canonical_profile"]
    assert profile["profile_id"] == "dih-canonical-json-v1"
    assert profile["digest_algorithm"] == "sha256"
    assert "rfc8785" not in profile["profile_id"].lower()


def test_b5_claim_tables_are_the_only_claim_tables() -> None:
    assert Claim.__tablename__ == "claims"
    assert ClaimEvidence.__tablename__ == "claim_evidence"
    assert "claims_v2" not in Base.metadata.tables
    assert "claim_evidence_v2" not in Base.metadata.tables


def test_c8_does_not_create_a_task_template_table() -> None:
    registry = load_registry()
    assert "task_templates" not in {item["name"] for item in registry["tables"]}
    assert "task_templates" not in Base.metadata.tables


def test_report_contract_exposes_c8_sections() -> None:
    """C8 只读 C1 的 report_contract schema，不新增段。"""
    schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    assert {"markets", "datasets", "scorecard"} <= set(schema["required"])
    assert {
        "market_assessment",
        "dataset",
        "scorecard",
        "gap",
        "sku_candidate",
    } <= set(schema["$defs"])
    market_required = set(schema["$defs"]["market_assessment"]["required"])
    assert {
        "market",
        "market_role",
        "quality_status",
        "evidence_grade",
        "domains",
        "sample_counts",
        "thresholds",
        "gaps",
    } <= market_required
    dataset_required = set(schema["$defs"]["dataset"]["required"])
    assert {
        "dataset_version_id",
        "market",
        "row_count",
        "content_sha256",
        "schema_hash",
    } <= dataset_required


def test_c8_audit_actions_are_registered_or_free_strings() -> None:
    """C2 的 action 是自由字符串；若 C1 登记为枚举，三个 C8 action 必须在内。"""
    registry = load_registry()
    enum_names = {item["name"] for item in registry["enums"]}
    c8_actions = {
        "quality.assessment.computed",
        "quality.gap.resolved",
        "quality.template.changed",
    }
    if "audit_events.action" in enum_names:
        assert c8_actions <= set(enum_values("audit_events.action"))
    else:
        action_column = next(
            column
            for column in table("audit_events")["columns"]
            if column["name"] == "action"
        )
        resource_column = next(
            column
            for column in table("audit_events")["columns"]
            if column["name"] == "resource_type"
        )
        assert action_column["type"] == "string(80)"
        assert resource_column["type"] == "string(40)"


def test_c1_contract_and_registry_are_the_only_authority() -> None:
    """读取 C1 的实现决定；C8 不追加自己的契约说明。"""
    text = CONTRACT.read_text(encoding="utf-8")
    assert "> 版本：v1.1 · 2026-10-22" in text
    registry = load_registry()
    assert registry["registry_version"] == "contract-registry.v1"
    documents = {item["path"]: item for item in registry["documents"]}
    contract = documents["docs/design/【契约冻结】v1-表名-枚举-接口.md"]
    assert contract["version"] == "v1.1"
```

- [ ] **Step 2: 运行测试，确认 C1 registry 齐全**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_c8_contract_gate.py -q
```

Expected: C1 registry 与契约 v1.1 就绪时 `8 passed`。任一断言失败表示 C1 缺登记项；停止 C8，把缺失项清单返回 C1 补充登记，不得在本切片修改契约文档或 registry。

- [ ] **Step 3: 处理缺项（不写契约）**

若 Step 2 失败，按失败断言列出缺失的表、列、枚举或契约版本，返回 C1。C8 不得：

- 修改 `docs/design/【契约冻结】v1-表名-枚举-接口.md`。
- 修改或重新生成 `configs/contracts/v1.1.0/registry.json`。
- 在 C8 内追加“C8 实现决定”或本地契约副本。

C1 补齐并重新生成 registry 后，从 Step 2 重跑。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_c8_contract_gate.py -q
```

Expected: `8 passed`。这是只读门禁；C8 没有修改契约文档或 registry。

- [ ] **Step 5: 运行契约检查与 GitNexus**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
uv run python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 契约检查 exit code 0。`detect-changes` 只列出 C8 的测试文件，不出现 `partial: true` 或 `truncated: true`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_c8_contract_gate.py
git commit -m "test(dataset): guard c8 objects in c1 registry"
```

---

### Task 2: 复用 C1 的 canonical profile

**Files:**
- Test: `apps/api/tests/unit/test_dataset_canonical_profile.py`

**Interfaces:**
- Consumes: `data_intelligence_hub.schemas.report_contract.CANONICAL_PROFILE_ID`、`SCHEMA_VERSION`、`canonical_json_bytes`。
- Produces: 一条不可绕过的守卫：数据集哈希只使用 `dih-canonical-json-v1`，C8 不实现第二套 canonicalizer。

- [ ] **Step 1: 写 profile 守卫测试**

Create `apps/api/tests/unit/test_dataset_canonical_profile.py`：

```python
"""C8：数据集哈希只使用 C1 冻结的 canonical profile。"""

from __future__ import annotations

import importlib

import pytest

from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    SCHEMA_VERSION,
    canonical_json_bytes,
)


def test_profile_id_is_c1_b5_v1() -> None:
    assert CANONICAL_PROFILE_ID == "dih-canonical-json-v1"
    assert SCHEMA_VERSION == "1.1.0"


def test_v1_pins_b5_approximation() -> None:
    # 这三处是 B5 近似实现与严格 RFC 8785 的差异。v1 冻结它们，不改语义。
    assert canonical_json_bytes({"x": 1e-07}) == b'{"x":1e-07}'
    assert canonical_json_bytes({"x": -0.0}) == b'{"x":-0.0}'
    assert canonical_json_bytes({"z": "😀", "a": "\ue000"}) == (
        '{"a":"\ue000","z":"😀"}'.encode("utf-8")
    )


def test_c8_does_not_ship_a_second_canonical_module() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("data_intelligence_hub.contracts.canonical_json")
```

- [ ] **Step 2: 运行测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_canonical_profile.py -q
```

Expected: `3 passed`。若 C1 未导出常量，测试在导入处失败；停止并回到 C1，不在 C8 建第二套常量或序列化器。严格 RFC 8785 升级延期，未来使用 `dih-canonical-json-rfc8785-v1`，不得复用 v1 ID。

- [ ] **Step 3: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_dataset_canonical_profile.py
git commit -m "test(dataset): pin c1 canonical profile for dataset hashes"
```

---

### Task 3: 消费 C7 的来源簇

**Files:**
- Test: `apps/api/tests/unit/test_c8_source_cluster_gate.py`

**Interfaces:**
- Consumes: C7 的 `services/source_clusters.py`。
- Produces: 门禁测试，证明 C8 使用 C7 的 `normalise_url`、`resolve_source_cluster`、`assign_link_clusters`，不新建第二套来源簇算法。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_c8_source_cluster_gate.py`:

```python
"""C8 来源簇门禁。

C7 拥有 services/source_clusters.py。C8 只消费它。
"""

from __future__ import annotations

from data_intelligence_hub.services.source_clusters import (
    ClusterBasis,
    SourceCluster,
    assign_link_clusters,
    normalise_url,
    resolve_source_cluster,
)


def test_normalise_url_strips_tracking_and_sorts_query() -> None:
    assert normalise_url(
        "HTTPS://WWW.Example.com:443/products/1?utm_source=x&b=2&a=1#reviews"
    ) == "https://www.example.com/products/1?a=1&b=2"


def test_resolve_source_cluster_prefers_explicit_key() -> None:
    class Evidence:
        id = "evidence-1"
        url = "https://example.com/a"
        provider_id = "apify"
        reference_metadata = {"source_cluster_key": "provider:apify"}

    cluster = resolve_source_cluster(Evidence())
    assert cluster == SourceCluster("explicit:provider:apify", ClusterBasis.EXPLICIT)
    assert cluster.independent is True


def test_resolve_source_cluster_falls_back_to_content_hash() -> None:
    class Evidence:
        id = "evidence-1"
        url = "https://example.com/a"
        provider_id = "apify"
        reference_metadata = {"content_hash": "a" * 64}

    cluster = resolve_source_cluster(Evidence())
    assert cluster == SourceCluster("content:" + "a" * 64, ClusterBasis.CONTENT_HASH)


def test_assign_link_clusters_marks_only_first_of_a_cluster() -> None:
    links = assign_link_clusters(
        [
            ("evidence-1", SourceCluster("same", ClusterBasis.EXPLICIT)),
            ("evidence-2", SourceCluster("same", ClusterBasis.EXPLICIT)),
        ]
    )
    assert [link.independent for link in links] == [True, False]


def test_unresolved_cluster_is_not_independent() -> None:
    cluster = resolve_source_cluster(
        type(
            "Evidence",
            (),
            {
                "id": "evidence-1",
                "url": None,
                "provider_id": None,
                "reference_metadata": None,
            },
        )()
    )
    assert cluster.independent is False
```

- [ ] **Step 2: 运行测试确认失败或确认 C7 已合入**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_c8_source_cluster_gate.py -q
```

Expected: 如果 C7 已合入，`5 passed`。如果 `ModuleNotFoundError: data_intelligence_hub.services.source_clusters`，停止并先合入 C7。C8 不创建这个模块。

- [ ] **Step 3: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_c8_source_cluster_gate.py
git commit -m "test(dataset): gate on c7 source clusters"
```

### Task 4: 数据集内容哈希与 Schema 哈希

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/dataset_content_hash.py`
- Test: `apps/api/tests/unit/test_dataset_content_hash.py`

**Interfaces:**
- Consumes: C1 的 `canonical_json_bytes`、C7 的 `normalise_url`。
- Produces: `DATASET_CONTENT_SCHEMA_VERSION: Final[str] = "dataset-content.v1"`。
- Produces: `DatasetContentDigest(content_sha256: str, schema_hash: str)`。
- Produces: `canonical_sha256(value: JsonValue) -> str`，唯一摘要包装。
- Produces: `compute_dataset_content_digest(*, dataset_type: str, selected_fields: Sequence[str], rows: Iterable[Mapping[str, Any]], cleaning_script: Sequence[str]) -> DatasetContentDigest`。
- Produces: `DatasetContentHashError(ValueError)`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_dataset_content_hash.py`:

```python
"""数据集内容哈希。

哈希只覆盖内容与 schema。它不覆盖 dataset id、version id、created_at 和行顺序。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from data_intelligence_hub.services.dataset_content_hash import (
    DATASET_CONTENT_SCHEMA_VERSION,
    DatasetContentHashError,
    compute_dataset_content_digest,
)


def _row(
    *,
    title: str = "Bottle",
    price: object = 19.99,
    source_url: str | None = "https://www.amazon.com/dp/B001",
    missing_fields: list[str] | None = None,
    completeness_percent: int = 100,
) -> dict:
    values = {"title": title}
    if price is not None:
        values["price"] = price
    return {
        "row_id": f"{title}:{price}",
        "task_run_id": "task-run-1",
        "raw_record_id": f"raw-{title}",
        "source_url": source_url,
        "values": values,
        "missing_fields": missing_fields or [],
        "completeness_percent": completeness_percent,
    }


def _digest(rows: list[dict]):
    return compute_dataset_content_digest(
        dataset_type="ecommerce_product",
        selected_fields=["title", "price"],
        rows=rows,
        cleaning_script=["trim"],
    )


def test_schema_version_is_frozen() -> None:
    assert DATASET_CONTENT_SCHEMA_VERSION == "dataset-content.v1"


def test_known_fixture_hashes() -> None:
    rows = [
        _row(),
        _row(
            title="Pacifier",
            price=None,
            source_url="https://www.amazon.com/dp/B002",
            missing_fields=["price"],
            completeness_percent=50,
        ),
    ]
    digest = _digest(rows)
    assert digest.schema_hash == (
        "a70e49b2cdff262e3dc0b1f9bda7cadfdce29cee13de1129182fb3eeb587df0f"
    )
    assert digest.content_sha256 == (
        "b875c508a441a27360cd5d22ca6a4912e6ecc71d4a5f63e97cedaa3c82ce343d"
    )


def test_row_order_does_not_change_hash() -> None:
    rows = [_row(title="A"), _row(title="B", price=2.0)]
    assert _digest(rows) == _digest(list(reversed(rows)))


def test_missing_key_and_null_value_are_different() -> None:
    missing = _row(price=None, missing_fields=["price"])
    explicit_null = _row(price=None, missing_fields=[])
    explicit_null["values"]["price"] = None
    assert _digest([missing]).content_sha256 != _digest([explicit_null]).content_sha256


def test_tracking_parameters_do_not_change_hash() -> None:
    first = _row(source_url="https://www.amazon.com/dp/B001?utm_source=a")
    second = _row(source_url="https://www.amazon.com/dp/B001?utm_source=b")
    assert _digest([first]) == _digest([second])


def test_decimal_and_string_are_equal() -> None:
    first = _row(price=Decimal("1.50"))
    second = _row(price="1.5")
    assert _digest([first]) == _digest([second])


def test_datetime_is_normalized_to_utc_z() -> None:
    first = _row(price=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    second = _row(price="2026-01-01T12:00:00Z")
    assert _digest([first]) == _digest([second])


def test_selected_fields_order_does_not_change_schema_hash() -> None:
    first = compute_dataset_content_digest(
        dataset_type="ecommerce_product",
        selected_fields=["title", "price"],
        rows=[_row()],
        cleaning_script=["trim"],
    )
    second = compute_dataset_content_digest(
        dataset_type="ecommerce_product",
        selected_fields=["price", "title"],
        rows=[_row()],
        cleaning_script=["trim"],
    )
    assert first.schema_hash == second.schema_hash


def test_changing_fields_changes_schema_hash() -> None:
    first = _digest([_row()])
    second = compute_dataset_content_digest(
        dataset_type="ecommerce_product",
        selected_fields=["title"],
        rows=[_row()],
        cleaning_script=["trim"],
    )
    assert first.schema_hash != second.schema_hash


def test_rejects_non_mapping_values() -> None:
    row = _row()
    row["values"] = ["not", "a", "mapping"]
    with pytest.raises(DatasetContentHashError):
        _digest([row])


def test_rejects_missing_completeness() -> None:
    row = _row()
    row.pop("completeness_percent")
    with pytest.raises(DatasetContentHashError):
        _digest([row])
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_content_hash.py -q
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.services.dataset_content_hash'`。

- [ ] **Step 3: 写实现**

Create `apps/api/src/data_intelligence_hub/services/dataset_content_hash.py`:

```python
"""数据集内容哈希与 schema 哈希。

唯一入口是 :func:`compute_dataset_content_digest`。
保存数据集版本、预览和报告合同都必须调用本函数。不得各写一份。

哈希口径：

- ``schema_hash`` 覆盖 dataset_type、排序后的 selected_fields、行字段并集和 cleaning_script。
- ``content_sha256`` 覆盖 schema_hash、行数和排序后的行内容。
- 行内容只包含 values、规范化 source_url、排序后的 missing_fields 和 completeness_percent。
- 不覆盖 row_id、task_run_id、raw_record_id、dataset id、version id 和 created_at。
  这样同一内容重复采集会得到同一个 content_sha256。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final, cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    canonical_json_bytes,
)
from data_intelligence_hub.services.source_clusters import normalise_url

DATASET_CONTENT_SCHEMA_VERSION: Final[str] = "dataset-content.v1"


def canonical_sha256(value: JsonValue) -> str:
    """对 C1 canonical bytes 求 SHA-256。C8 不实现第二套序列化。"""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class DatasetContentHashError(ValueError):
    """数据集行不能进入内容哈希。"""


@dataclass(frozen=True, slots=True)
class DatasetContentDigest:
    """一次数据集版本的内容摘要。"""

    content_sha256: str
    schema_hash: str


def _normalize_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        return normalized.astimezone(UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for key in mapping:
            if not isinstance(key, str):
                raise DatasetContentHashError("映射键必须是字符串")
        return {
            key: _normalize_value(item)
            for key, item in mapping.items()
            if isinstance(key, str)
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    raise DatasetContentHashError(f"不支持的值类型：{type(value).__name__}")


def _row_values(row: Mapping[str, Any]) -> Mapping[str, Any]:
    values = row.get("values")
    if not isinstance(values, Mapping):
        raise DatasetContentHashError("row.values 必须是映射")
    return cast(Mapping[str, Any], values)


def _row_content(row: Mapping[str, Any]) -> dict[str, object]:
    completeness = row.get("completeness_percent")
    if not isinstance(completeness, int) or isinstance(completeness, bool):
        raise DatasetContentHashError("row.completeness_percent 必须是整数")

    missing_fields = row.get("missing_fields") or ()
    if not isinstance(missing_fields, (list, tuple)):
        raise DatasetContentHashError("row.missing_fields 必须是列表")

    values = {
        str(key): _normalize_value(value) for key, value in _row_values(row).items()
    }
    return {
        "values": values,
        "source_url": normalise_url(cast(str | None, row.get("source_url"))),
        "missing_fields": sorted(str(field) for field in missing_fields),
        "completeness_percent": completeness,
    }


def _schema_payload(
    *,
    dataset_type: str,
    selected_fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    cleaning_script: Sequence[str],
) -> dict[str, object]:
    row_fields: set[str] = set()
    for row in rows:
        row_fields.update(str(key) for key in _row_values(row))
    return {
        "schema_version": DATASET_CONTENT_SCHEMA_VERSION,
        "dataset_type": dataset_type,
        "selected_fields": sorted(str(field) for field in selected_fields),
        "row_fields": sorted(row_fields),
        "cleaning_script": [str(step) for step in cleaning_script],
    }


def compute_dataset_content_digest(
    *,
    dataset_type: str,
    selected_fields: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
    cleaning_script: Sequence[str],
) -> DatasetContentDigest:
    """计算数据集版本的 content_sha256 与 schema_hash。"""
    row_list = list(rows)
    schema_payload = _schema_payload(
        dataset_type=dataset_type,
        selected_fields=selected_fields,
        rows=row_list,
        cleaning_script=cleaning_script,
    )
    schema_hash = canonical_sha256(cast(JsonValue, schema_payload))
    row_payloads = [_row_content(row) for row in row_list]
    row_payloads.sort(key=lambda row: canonical_json_bytes(cast(JsonValue, row)))
    content_payload = {
        "schema_hash": schema_hash,
        "row_count": len(row_payloads),
        "rows": row_payloads,
    }
    return DatasetContentDigest(
        content_sha256=canonical_sha256(cast(JsonValue, content_payload)),
        schema_hash=schema_hash,
    )


__all__ = [
    "CANONICAL_PROFILE_ID",
    "DATASET_CONTENT_SCHEMA_VERSION",
    "DatasetContentDigest",
    "DatasetContentHashError",
    "canonical_sha256",
    "compute_dataset_content_digest",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_content_hash.py -q
```

Expected: `11 passed`。若固定哈希因 C1 profile v1 与旧 RFC 8785 实现的差异失败，先核对 `CANONICAL_PROFILE_ID` 与三处已知差异，再更新期望值；不得改为运行时自算。

- [ ] **Step 5: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/dataset_content_hash.py apps/api/tests/unit/test_dataset_content_hash.py
git commit -m "feat(dataset): add canonical content and schema hashes"
```

---

### Task 5: Quick/Standard 阈值与首期任务包模板

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/tool_catalog/evidence_thresholds.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench_templates.py`
- Test: `apps/api/tests/unit/test_workbench_templates.py`

**Interfaces:**
- Consumes: `EVIDENCE_THRESHOLDS`、`EvidenceGrade`、现有工具目录的稳定 `tool_id`、C1 已登记的 403 `capability_not_allowed`。
- Produces: `PackageTier(StrEnum)`，值为 `quick`、`standard`。
- Produces: `QualityGateThresholds`，字段 `core_field_completeness_percent=80`、`max_duplicate_rate_percent=2.0`、`source_url_coverage_percent=100`、`claim_evidence_binding_percent=100`、`min_independent_sources=2`。
- Produces: `PackageTierThreshold`，字段 `products_floor_n`、`products_target_n`、`products_plan_cap_n`、`reviews_floor_n`、`reviews_target_n`、`reviews_plan_cap_n`、`creator_content_floor_n`、`creator_content_target_n`、`creator_content_plan_cap_n`、`max_evidence_grade`、`quality_gates`。
- Produces: `PACKAGE_TIER_THRESHOLDS`、`package_threshold_for(tier: PackageTier | str) -> PackageTierThreshold`。
- Produces: `CORE_DATA_DOMAINS`、`ENHANCEMENT_DATA_DOMAINS`、`ALL_DATA_DOMAINS`。
- Produces: `TaskTemplate`（含冻结字段 `capability_allowlist`）、`GOVERNED_TEMPLATE_ID`、`FORMAL_MARKETS`、`get_task_template`、`list_task_templates`、`template_capability_ids(template_id)`、`template_registry_digest`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_workbench_templates.py`:

```python
"""首期任务包模板与 Quick/Standard 阈值。

本测试证明：

1. 只有一个任务包模板。
2. 阈值只存在于 evidence_thresholds。
3. 模板模块没有写死任何数字阈值。
4. 没有任务包模板 DB 表。
5. 模板能力白名单只引用现有工具目录的稳定 tool_id，
   排除 creator_cookie 能力，也不回退到全部工具。
"""

from __future__ import annotations

import ast
import asyncio
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import data_intelligence_hub.services.workbench_templates as task_templates
import data_intelligence_hub.tool_catalog.evidence_thresholds as evidence_thresholds
from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.models import Base
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.services.workbench_templates import (
    GOVERNED_TEMPLATE_ID,
    FORMAL_MARKETS,
    get_task_template,
    list_task_templates,
    template_capability_ids,
    template_registry_digest,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    CORE_DATA_DOMAINS,
    PackageTier,
    package_threshold_for,
)
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog

CREATOR_COOKIE_CAPABILITY_IDS = (
    "tikhub_tiktok_video_products",
    "tikhub_tiktok_creator_showcase",
)
NON_TEMPLATE_CAPABILITY_ID = "exa_search_auto"


def _catalog_tool_ids() -> frozenset[str]:
    """从静态工具目录取稳定 tool_id，不连接数据库。"""
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    return frozenset(tool.tool_id for tool in build_tool_catalog(catalog).tools)


def test_only_one_task_template_is_registered() -> None:
    templates = list_task_templates()
    assert [template.template_id for template in templates] == [GOVERNED_TEMPLATE_ID]
    assert GOVERNED_TEMPLATE_ID == "tiktok_shop_maternal_newborn"


def test_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        get_task_template("another_template")


def test_template_version_and_markets_are_frozen() -> None:
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    assert template.version == "1.0.0"
    assert template.markets == FORMAL_MARKETS
    assert FORMAL_MARKETS == (
        "US",
        "GB",
        "DE",
        "FR",
        "IT",
        "ES",
        "IE",
        "NL",
        "BE",
        "AT",
        "PL",
    )


def test_quick_and_standard_thresholds_are_exact() -> None:
    quick = package_threshold_for(PackageTier.QUICK)
    standard = package_threshold_for(PackageTier.STANDARD)
    assert (quick.products_floor_n, quick.products_plan_cap_n) == (20, 50)
    assert (quick.reviews_floor_n, quick.reviews_plan_cap_n) == (300, 1000)
    assert (quick.creator_content_floor_n, quick.creator_content_plan_cap_n) == (50, 100)
    assert quick.max_evidence_grade == "L3_live_single"
    assert (standard.products_floor_n, standard.products_plan_cap_n) == (100, 300)
    assert (standard.reviews_floor_n, standard.reviews_plan_cap_n) == (2000, 5000)
    assert (standard.creator_content_floor_n, standard.creator_content_plan_cap_n) == (
        200,
        500,
    )
    assert standard.max_evidence_grade == "L4_authorized_live"


def test_quality_gates_are_exact() -> None:
    gates = package_threshold_for(PackageTier.QUICK).quality_gates
    assert gates.core_field_completeness_percent == 80
    assert gates.max_duplicate_rate_percent == 2.0
    assert gates.source_url_coverage_percent == 100
    assert gates.claim_evidence_binding_percent == 100
    assert gates.min_independent_sources == 2


def test_target_n_is_not_above_plan_cap() -> None:
    for tier in PackageTier:
        threshold = package_threshold_for(tier)
        assert threshold.products_floor_n <= threshold.products_target_n
        assert threshold.products_target_n <= threshold.products_plan_cap_n
        assert threshold.reviews_floor_n <= threshold.reviews_target_n
        assert threshold.reviews_target_n <= threshold.reviews_plan_cap_n
        assert threshold.creator_content_floor_n <= threshold.creator_content_target_n
        assert threshold.creator_content_target_n <= threshold.creator_content_plan_cap_n


def test_template_thresholds_read_the_single_source(monkeypatch: pytest.MonkeyPatch) -> None:
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    original = evidence_thresholds.PACKAGE_TIER_THRESHOLDS[PackageTier.QUICK]
    replacement = evidence_thresholds.PackageTierThreshold(
        tier=PackageTier.QUICK,
        products_floor_n=7,
        products_target_n=7,
        products_plan_cap_n=9,
        reviews_floor_n=original.reviews_floor_n,
        reviews_target_n=original.reviews_target_n,
        reviews_plan_cap_n=original.reviews_plan_cap_n,
        creator_content_floor_n=original.creator_content_floor_n,
        creator_content_target_n=original.creator_content_target_n,
        creator_content_plan_cap_n=original.creator_content_plan_cap_n,
        max_evidence_grade=original.max_evidence_grade,
        quality_gates=original.quality_gates,
    )
    table = dict(evidence_thresholds.PACKAGE_TIER_THRESHOLDS)
    table[PackageTier.QUICK] = replacement
    monkeypatch.setattr(evidence_thresholds, "PACKAGE_TIER_THRESHOLDS", table)
    assert template.thresholds[PackageTier.QUICK].products_floor_n == 7


def test_template_module_has_no_numeric_threshold_literals() -> None:
    source = Path(task_templates.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    numbers = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ]
    assert numbers == []


def test_template_references_only_registered_evidence_templates() -> None:
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    assert set(template.evidence_template_ids) <= set(evidence_thresholds.EVIDENCE_THRESHOLDS)


def test_core_domains_are_three_and_enhancements_are_two() -> None:
    assert CORE_DATA_DOMAINS == ("products", "reviews", "creator_content")
    assert evidence_thresholds.ENHANCEMENT_DATA_DOMAINS == ("ads", "trends")


def test_template_registry_digest_is_stable_and_covers_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = template_registry_digest()
    assert first == template_registry_digest()
    assert len(first) == 64

    original = evidence_thresholds.PACKAGE_TIER_THRESHOLDS[PackageTier.STANDARD]
    replacement = evidence_thresholds.PackageTierThreshold(
        tier=PackageTier.STANDARD,
        products_floor_n=original.products_floor_n + 1,
        products_target_n=original.products_target_n,
        products_plan_cap_n=original.products_plan_cap_n,
        reviews_floor_n=original.reviews_floor_n,
        reviews_target_n=original.reviews_target_n,
        reviews_plan_cap_n=original.reviews_plan_cap_n,
        creator_content_floor_n=original.creator_content_floor_n,
        creator_content_target_n=original.creator_content_target_n,
        creator_content_plan_cap_n=original.creator_content_plan_cap_n,
        max_evidence_grade=original.max_evidence_grade,
        quality_gates=original.quality_gates,
    )
    table = dict(evidence_thresholds.PACKAGE_TIER_THRESHOLDS)
    table[PackageTier.STANDARD] = replacement
    monkeypatch.setattr(evidence_thresholds, "PACKAGE_TIER_THRESHOLDS", table)
    assert template_registry_digest() != first


def test_template_capability_allowlist_is_frozen_and_non_empty() -> None:
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    allowlist = template.capability_allowlist
    assert allowlist == (
        "tikhub_tiktok_shop_search_v2",
        "tikhub_tiktok_shop_products",
        "tikhub_tiktok_shop_reviews_v2",
        "tikhub_tiktok_video_search",
        "tikhub_tiktok_user_posts",
        "tikhub_tiktok_hashtag_posts",
        "tikhub_tiktok_creator_info",
        "tikhub_tiktok_creator_insights",
        "tikhub_tiktok_creator_insights_trend",
    )
    assert len(allowlist) == len(set(allowlist))
    with pytest.raises(FrozenInstanceError):
        template.capability_allowlist = ()  # type: ignore[misc]


def test_template_capability_ids_returns_the_template_allowlist() -> None:
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    assert (
        template_capability_ids(GOVERNED_TEMPLATE_ID)
        == template.capability_allowlist
    )
    with pytest.raises(KeyError):
        template_capability_ids("another_template")


def test_template_capability_ids_are_existing_catalog_tool_ids() -> None:
    catalog_ids = _catalog_tool_ids()
    assert set(template_capability_ids(GOVERNED_TEMPLATE_ID)) <= catalog_ids


def test_template_capability_ids_excludes_creator_cookie_capabilities() -> None:
    catalog_ids = _catalog_tool_ids()
    allowed = set(template_capability_ids(GOVERNED_TEMPLATE_ID))
    # 两个端点仍在工具目录里，只是不属于本模板。
    assert set(CREATOR_COOKIE_CAPABILITY_IDS) <= catalog_ids
    assert allowed.isdisjoint(CREATOR_COOKIE_CAPABILITY_IDS)


def test_template_capability_ids_excludes_non_template_capability() -> None:
    catalog_ids = _catalog_tool_ids()
    assert NON_TEMPLATE_CAPABILITY_ID in catalog_ids
    assert NON_TEMPLATE_CAPABILITY_ID not in template_capability_ids(
        GOVERNED_TEMPLATE_ID
    )


def test_template_capability_ids_have_no_fallback_to_all_tools() -> None:
    catalog_ids = _catalog_tool_ids()
    allowed = set(template_capability_ids(GOVERNED_TEMPLATE_ID))
    assert allowed < catalog_ids


def test_template_registry_digest_covers_capability_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = template_registry_digest()
    template = get_task_template(GOVERNED_TEMPLATE_ID)
    changed = replace(
        template,
        capability_allowlist=(
            *template.capability_allowlist,
            NON_TEMPLATE_CAPABILITY_ID,
        ),
    )
    monkeypatch.setattr(task_templates, "list_task_templates", lambda: (changed,))
    assert template_registry_digest() != first


def test_no_task_template_table_is_created() -> None:
    assert "task_templates" not in Base.metadata.tables
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_workbench_templates.py -q
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.services.workbench_templates'`。

- [ ] **Step 3: 修改 evidence_thresholds**

在 `apps/api/src/data_intelligence_hub/tool_catalog/evidence_thresholds.py` 顶部导入区追加：

```python
from enum import StrEnum

from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
```

在 `EVIDENCE_THRESHOLDS` 之后追加：

```python
class PackageTier(StrEnum):
    """任务包档位。契约 v1.1 的 package_type 枚举。"""

    QUICK = "quick"
    STANDARD = "standard"


CORE_DATA_DOMAINS: Final[tuple[str, ...]] = (
    "products",
    "reviews",
    "creator_content",
)
ENHANCEMENT_DATA_DOMAINS: Final[tuple[str, ...]] = ("ads", "trends")
ALL_DATA_DOMAINS: Final[tuple[str, ...]] = CORE_DATA_DOMAINS + ENHANCEMENT_DATA_DOMAINS


@dataclass(frozen=True, slots=True)
class QualityGateThresholds:
    """设计 §5.1 的质量门槛。数值只在这里定义。"""

    core_field_completeness_percent: int = 80
    max_duplicate_rate_percent: float = 2.0
    source_url_coverage_percent: int = 100
    claim_evidence_binding_percent: int = 100
    min_independent_sources: int = 2


@dataclass(frozen=True, slots=True)
class PackageTierThreshold:
    """一个档位的样本门槛。

    ``floor_n`` 是验收门槛。``plan_cap_n`` 是预算和采集上限。
    首期把 ``target_n`` 设为 ``floor_n``，避免把范围上限误当计划目标。
    计划生成器可以显式提高 ``target_n``。验收只看 ``floor_n``。
    """

    tier: PackageTier
    products_floor_n: int
    products_target_n: int
    products_plan_cap_n: int
    reviews_floor_n: int
    reviews_target_n: int
    reviews_plan_cap_n: int
    creator_content_floor_n: int
    creator_content_target_n: int
    creator_content_plan_cap_n: int
    max_evidence_grade: EvidenceGrade
    quality_gates: QualityGateThresholds


PACKAGE_TIER_THRESHOLDS: Final[Mapping[PackageTier, PackageTierThreshold]] = (
    MappingProxyType(
        {
            PackageTier.QUICK: PackageTierThreshold(
                tier=PackageTier.QUICK,
                products_floor_n=20,
                products_target_n=20,
                products_plan_cap_n=50,
                reviews_floor_n=300,
                reviews_target_n=300,
                reviews_plan_cap_n=1000,
                creator_content_floor_n=50,
                creator_content_target_n=50,
                creator_content_plan_cap_n=100,
                max_evidence_grade=EvidenceGrade.L3_LIVE_SINGLE,
                quality_gates=QualityGateThresholds(),
            ),
            PackageTier.STANDARD: PackageTierThreshold(
                tier=PackageTier.STANDARD,
                products_floor_n=100,
                products_target_n=100,
                products_plan_cap_n=300,
                reviews_floor_n=2000,
                reviews_target_n=2000,
                reviews_plan_cap_n=5000,
                creator_content_floor_n=200,
                creator_content_target_n=200,
                creator_content_plan_cap_n=500,
                max_evidence_grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
                quality_gates=QualityGateThresholds(),
            ),
        }
    )
)


def package_threshold_for(tier: PackageTier | str) -> PackageTierThreshold:
    """按档位取阈值。未知档位抛 KeyError。"""
    try:
        normalized = PackageTier(tier)
    except ValueError:
        raise KeyError(f"未知任务包档位：{tier}") from None
    return PACKAGE_TIER_THRESHOLDS[normalized]
```

- [ ] **Step 4: 创建任务包模板注册表**

Create `apps/api/src/data_intelligence_hub/services/workbench_templates.py`:

```python
"""首期任务包模板的代码注册表。

这是任务包模板的唯一事实源。C8 不建 ``task_templates`` 表。
阈值不在这里定义。``TaskTemplate.thresholds`` 每次从
``tool_catalog.evidence_thresholds`` 读取。

首期只登记一个模板：TikTok Shop 母婴新品进入决策。
模板能力白名单只引用工具目录的稳定 ``tool_id``，并进入注册表摘要。
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from data_intelligence_hub.schemas.report_contract import canonical_json_bytes
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    CORE_DATA_DOMAINS,
    PackageTier,
    PackageTierThreshold,
    package_threshold_for,
)
from data_intelligence_hub.tool_catalog.markets import FORMAL_MARKETS

GOVERNED_TEMPLATE_ID: Final[str] = "tiktok_shop_maternal_newborn"

# 冻结能力白名单。值必须是工具目录的稳定 ``tool_id``。
# 只列本模板消费的能力；creator_cookie 门控端点不在其中，
# 热卖榜端点只覆盖东南亚市场，也不在其中。
# 运行时也不回退到全部工具。
_TEMPLATE_CAPABILITY_ALLOWLIST: Final[tuple[str, ...]] = (
    "tikhub_tiktok_shop_search_v2",
    "tikhub_tiktok_shop_products",
    "tikhub_tiktok_shop_reviews_v2",
    "tikhub_tiktok_video_search",
    "tikhub_tiktok_user_posts",
    "tikhub_tiktok_hashtag_posts",
    "tikhub_tiktok_creator_info",
    "tikhub_tiktok_creator_insights",
    "tikhub_tiktok_creator_insights_trend",
)


@dataclass(frozen=True, slots=True)
class TaskTemplate:
    """一个受治理任务包模板。"""

    template_id: str
    version: str
    label: str
    category_scope: tuple[str, ...]
    markets: tuple[str, ...]
    package_tiers: tuple[PackageTier, ...]
    core_domains: tuple[str, ...]
    evidence_template_ids: tuple[str, ...]
    required_params: tuple[str, ...]
    capability_allowlist: tuple[str, ...]

    @property
    def thresholds(self) -> Mapping[PackageTier, PackageTierThreshold]:
        """每次从唯一阈值表读取。改表后本属性立即返回新值。"""
        return MappingProxyType(
            {
                tier: package_threshold_for(tier)
                for tier in self.package_tiers
            }
        )


_TIKTOK_SHOP_MATERNAL_NEWBORN: Final = TaskTemplate(
    template_id=GOVERNED_TEMPLATE_ID,
    version="1.0.0",
    label="TikTok Shop 母婴新品进入决策",
    category_scope=("maternal_baby",),
    markets=FORMAL_MARKETS,
    package_tiers=(PackageTier.QUICK, PackageTier.STANDARD),
    core_domains=CORE_DATA_DOMAINS,
    evidence_template_ids=(
        "t1_voc",
        "t2_competitor",
        "t3_selection",
        "t4_creator",
    ),
    required_params=(
        "brand",
        "category_id",
        "primary_market",
        "compare_markets",
        "window",
        "decision_question",
        "package_type",
    ),
    capability_allowlist=_TEMPLATE_CAPABILITY_ALLOWLIST,
)

_TEMPLATES: Final[Mapping[str, TaskTemplate]] = MappingProxyType(
    {_TIKTOK_SHOP_MATERNAL_NEWBORN.template_id: _TIKTOK_SHOP_MATERNAL_NEWBORN}
)


def list_task_templates() -> tuple[TaskTemplate, ...]:
    """按登记顺序返回任务包模板。首期只有一个。"""
    return (_TIKTOK_SHOP_MATERNAL_NEWBORN,)


def get_task_template(template_id: str) -> TaskTemplate:
    """按 ID 取模板。未知 ID 抛 KeyError，不返回 None。"""
    try:
        return _TEMPLATES[template_id]
    except KeyError:
        raise KeyError(f"未知任务包模板：{template_id}") from None


def template_capability_ids(template_id: str) -> tuple[str, ...]:
    """返回模板冻结的能力白名单。

    值是工具目录的稳定 ``tool_id``。未知模板抛 KeyError，不返回空元组。
    本函数不读取运行状态，不回退到全部工具。
    """
    return get_task_template(template_id).capability_allowlist


def template_registry_digest() -> str:
    """模板注册表与阈值配置的稳定摘要。

    审计只比较摘要，不写模板正文。阈值或能力白名单变化都会改变摘要。
    """
    payload = [
        {
            "template_id": template.template_id,
            "version": template.version,
            "capability_allowlist": list(template.capability_allowlist),
            "markets": list(template.markets),
            "package_tiers": [tier.value for tier in template.package_tiers],
            "thresholds": {
                tier.value: {
                    "products_floor_n": threshold.products_floor_n,
                    "products_target_n": threshold.products_target_n,
                    "products_plan_cap_n": threshold.products_plan_cap_n,
                    "reviews_floor_n": threshold.reviews_floor_n,
                    "reviews_target_n": threshold.reviews_target_n,
                    "reviews_plan_cap_n": threshold.reviews_plan_cap_n,
                    "creator_content_floor_n": threshold.creator_content_floor_n,
                    "creator_content_target_n": threshold.creator_content_target_n,
                    "creator_content_plan_cap_n": threshold.creator_content_plan_cap_n,
                    "max_evidence_grade": threshold.max_evidence_grade.value,
                    "quality_gates": {
                        "core_field_completeness_percent": (
                            threshold.quality_gates.core_field_completeness_percent
                        ),
                        "max_duplicate_rate_percent": (
                            threshold.quality_gates.max_duplicate_rate_percent
                        ),
                        "source_url_coverage_percent": (
                            threshold.quality_gates.source_url_coverage_percent
                        ),
                        "claim_evidence_binding_percent": (
                            threshold.quality_gates.claim_evidence_binding_percent
                        ),
                        "min_independent_sources": (
                            threshold.quality_gates.min_independent_sources
                        ),
                    },
                }
                for tier, threshold in template.thresholds.items()
            },
        }
        for template in list_task_templates()
    ]
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = [
    "GOVERNED_TEMPLATE_ID",
    "FORMAL_MARKETS",
    "TaskTemplate",
    "get_task_template",
    "list_task_templates",
    "template_capability_ids",
    "template_registry_digest",
]
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_workbench_templates.py -q
```

Expected: `19 passed`。

- [ ] **Step 6: 运行既有阈值测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_evidence_grade.py tests/unit/test_report_builder.py -q
```

Expected: 全部通过。B5 的五个报告模板阈值不变。

**C13 交接。** C13 的 `CapabilityPort.template_capability_ids` 必须调用本任务的 `template_capability_ids(template_id)`，并按模板上下文传入 `template_id`；不得按工具 `category` 过滤，也不得在交集为空时回退到全部工具。C8 不修改 C13。白名单外能力由 C13 返回 C1 已登记的 403 `capability_not_allowed`。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/tool_catalog/evidence_thresholds.py apps/api/src/data_intelligence_hub/services/workbench_templates.py apps/api/tests/unit/test_workbench_templates.py
git commit -m "feat(template): register governed task template and package thresholds"
```

---

### Task 6: 逐市场质量记分卡与结构化缺口

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/dataset_quality.py`
- Test: `apps/api/tests/unit/test_dataset_quality.py`

**Interfaces:**
- Consumes: `SourceIdentity`、`count_independent_sources`、`PackageTier`、`PackageTierThreshold`、`package_threshold_for`、`EvidenceGrade`。
- Produces: `QualityRecord(record_id, market, data_domain, source_url, source_cluster_key, content_sha256, completeness_percent)`。
- Produces: `DomainEvidence(data_domain, records, blocked_reason=None)`。
- Produces: `KeyClaimBinding(claim_id, data_domain, evidence_ids, independent_source_count)`。
- Produces: `MarketQualityInput(task_id, market, market_role, package_type, evidence_grade, domains, key_claims=())`。
- Produces: `DataGapDraft(gap_id, market, data_domain, reason_code, actual_value, threshold_value, impact, customer_text_zh, customer_text_en, remediation, severity, status="open")`。
- Produces: `MarketAssessmentDraft(assessment_id, task_id, market, market_role, quality_status, conclusion_standard, conclusion_quick, evidence_grade, core_domain_coverage, sample_counts, thresholds, gap_ids, details, computed_at)`。
- Produces: `MarketAssessmentResult(assessment, gaps)`。
- Produces: `compute_market_assessment(payload: MarketQualityInput, *, computed_at: datetime) -> MarketAssessmentResult`。
- Produces: `allowed_conclusions(status: str, tier: PackageTier) -> tuple[str, ...]`。
- Produces: `SkuCandidate(candidate_id, rank, provisional=False)`、`ConclusionInputs(requested_standard=None, requested_quick=None, sku_candidates=(), test_budget_usd=None, observation_window_days=None, success_threshold=None, stop_loss=None, c7_independent_cluster_count=0)`、`ConclusionDecision(standard, quick, allowed, reasons=())`。
- Produces: `validate_conclusion(*, quality_status: str, package_type: PackageTier, inputs: ConclusionInputs) -> ConclusionDecision`。只校验已批准语义，不发布报告。
- Produces: `MarketQualityInputError(ValueError)`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_dataset_quality.py`:

```python
"""逐市场质量记分卡。

测试覆盖：

1. 核心域 3/3 与样本门槛。
2. missing 写 null，不写 0。
3. blocked 写 null，并写 critical 缺口。
4. 独立来源折叠。
5. 关键 Claim 绑定与独立来源。
6. Quick 与 Standard 的结论上限。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

import data_intelligence_hub.tool_catalog.evidence_thresholds as evidence_thresholds
from data_intelligence_hub.services.dataset_quality import (
    ConclusionInputs,
    DomainEvidence,
    KeyClaimBinding,
    MarketQualityInput,
    MarketQualityInputError,
    QualityRecord,
    SkuCandidate,
    allowed_conclusions,
    compute_market_assessment,
    validate_conclusion,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    CORE_DATA_DOMAINS,
    PackageTier,
    PackageTierThreshold,
    QualityGateThresholds,
)

TASK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
COMPUTED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def small_floors(monkeypatch: pytest.MonkeyPatch) -> None:
    """把门槛调小，测试只验证逻辑。精确阈值由 Task 5 测试。"""
    table = dict(evidence_thresholds.PACKAGE_TIER_THRESHOLDS)
    gates = QualityGateThresholds(
        core_field_completeness_percent=80,
        max_duplicate_rate_percent=2.0,
        source_url_coverage_percent=100,
        claim_evidence_binding_percent=100,
        min_independent_sources=2,
    )
    table[PackageTier.QUICK] = PackageTierThreshold(
        tier=PackageTier.QUICK,
        products_floor_n=2,
        products_target_n=2,
        products_plan_cap_n=5,
        reviews_floor_n=3,
        reviews_target_n=3,
        reviews_plan_cap_n=10,
        creator_content_floor_n=2,
        creator_content_target_n=2,
        creator_content_plan_cap_n=5,
        max_evidence_grade=EvidenceGrade.L3_LIVE_SINGLE,
        quality_gates=gates,
    )
    table[PackageTier.STANDARD] = PackageTierThreshold(
        tier=PackageTier.STANDARD,
        products_floor_n=4,
        products_target_n=4,
        products_plan_cap_n=10,
        reviews_floor_n=6,
        reviews_target_n=6,
        reviews_plan_cap_n=20,
        creator_content_floor_n=4,
        creator_content_target_n=4,
        creator_content_plan_cap_n=10,
        max_evidence_grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        quality_gates=gates,
    )
    monkeypatch.setattr(evidence_thresholds, "PACKAGE_TIER_THRESHOLDS", table)


def record(
    domain: str,
    *,
    index: int = 0,
    market: str = "US",
    source_cluster_key: str | None = None,
    content: str | None = None,
    completeness: int = 100,
    source_url: str | None = "https://example.com/item",
) -> QualityRecord:
    return QualityRecord(
        record_id=f"{domain}-{index}",
        market=market,
        data_domain=domain,
        source_url=source_url,
        source_cluster_key=source_cluster_key or f"cluster-{domain}-{index % 2}",
        content_sha256=content or f"{domain}-{index}",
        completeness_percent=completeness,
    )


def domain(domain_name: str, count: int, **kwargs) -> DomainEvidence:
    return DomainEvidence(
        data_domain=domain_name,
        records=tuple(record(domain_name, index=index, **kwargs) for index in range(count)),
    )


def payload(
    *,
    tier: PackageTier = PackageTier.QUICK,
    products: DomainEvidence | None = None,
    reviews: DomainEvidence | None = None,
    creator: DomainEvidence | None = None,
    ads: DomainEvidence | None = None,
    claims: tuple[KeyClaimBinding, ...] = (),
) -> MarketQualityInput:
    domains = [
        products or domain("products", 2),
        reviews or domain("reviews", 3),
        creator or domain("creator_content", 2),
    ]
    if ads is not None:
        domains.append(ads)
    return MarketQualityInput(
        task_id=TASK_ID,
        market="US",
        market_role="primary",
        package_type=tier,
        evidence_grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        domains=tuple(domains),
        key_claims=claims,
    )


def test_qualified_market() -> None:
    result = compute_market_assessment(payload(), computed_at=COMPUTED_AT)
    assert result.assessment.quality_status == "qualified"
    assert result.assessment.core_domain_coverage == {
        "products": "pass",
        "reviews": "pass",
        "creator_content": "pass",
    }
    assert result.gaps == ()
    assert result.assessment.sample_counts == {
        "products": 2,
        "reviews": 3,
        "creator_content": 2,
    }


def test_missing_reviews_is_null_not_zero() -> None:
    result = compute_market_assessment(
        payload(reviews=DomainEvidence(data_domain="reviews", records=())),
        computed_at=COMPUTED_AT,
    )
    assert result.assessment.quality_status == "not_qualified"
    assert result.assessment.core_domain_coverage["reviews"] == "missing"
    assert result.assessment.sample_counts["reviews"] is None
    gap = next(gap for gap in result.gaps if gap.data_domain == "reviews")
    assert gap.reason_code == "data_domain_missing"
    assert gap.actual_value is None
    assert gap.threshold_value == 3
    assert gap.severity == "blocking"


def test_blocked_creator_is_critical_and_null() -> None:
    result = compute_market_assessment(
        payload(
            creator=DomainEvidence(
                data_domain="creator_content",
                records=(),
                blocked_reason="market_rights_missing",
            )
        ),
        computed_at=COMPUTED_AT,
    )
    assert result.assessment.core_domain_coverage["creator_content"] == "blocked"
    assert result.assessment.sample_counts["creator_content"] is None
    gap = next(gap for gap in result.gaps if gap.data_domain == "creator_content")
    assert gap.reason_code == "data_domain_blocked"
    assert gap.actual_value is None
    assert gap.severity == "critical"


def test_partial_products_writes_actual_and_threshold() -> None:
    result = compute_market_assessment(
        payload(products=domain("products", 1)),
        computed_at=COMPUTED_AT,
    )
    assert result.assessment.core_domain_coverage["products"] == "partial"
    assert result.assessment.sample_counts["products"] == 1
    gap = next(gap for gap in result.gaps if gap.data_domain == "products")
    assert gap.reason_code == "sample_below_floor"
    assert gap.actual_value == 1
    assert gap.threshold_value == 2


def test_same_provider_counts_as_one_independent_source() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(
            record("products", index=0, source_cluster_key="provider-a", content="c1"),
            record("products", index=1, source_cluster_key="provider-a", content="c2"),
        ),
    )
    result = compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)
    assert result.assessment.details["independent_source_count"] == 1


def test_same_content_from_two_providers_counts_once() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(
            record("products", index=0, source_cluster_key="provider-a", content="same"),
            record("products", index=1, source_cluster_key="provider-b", content="same"),
        ),
    )
    result = compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)
    assert result.assessment.details["independent_source_count"] == 1


def test_key_claim_independent_sources_below_two_is_qualified_with_gap() -> None:
    claims = (
        KeyClaimBinding(
            claim_id="claim-1",
            data_domain="reviews",
            evidence_ids=("evidence-1",),
            independent_source_count=1,
        ),
    )
    result = compute_market_assessment(payload(claims=claims), computed_at=COMPUTED_AT)
    assert result.assessment.quality_status == "qualified_with_gap"
    gap = next(gap for gap in result.gaps if gap.reason_code == "independent_sources_below_floor")
    assert gap.actual_value == 1
    assert gap.threshold_value == 2
    assert gap.severity == "warning"


def test_claim_without_evidence_is_not_qualified() -> None:
    claims = (
        KeyClaimBinding(
            claim_id="claim-1",
            data_domain="reviews",
            evidence_ids=(),
            independent_source_count=2,
        ),
    )
    result = compute_market_assessment(payload(claims=claims), computed_at=COMPUTED_AT)
    assert result.assessment.quality_status == "not_qualified"
    gap = next(
        gap for gap in result.gaps if gap.reason_code == "claim_evidence_binding_below_floor"
    )
    assert gap.actual_value == 0.0
    assert gap.threshold_value == 100
    assert gap.severity == "blocking"


def test_enhancement_gap_is_qualified_with_gap() -> None:
    result = compute_market_assessment(
        payload(ads=DomainEvidence(data_domain="ads", records=())),
        computed_at=COMPUTED_AT,
    )
    assert result.assessment.quality_status == "qualified_with_gap"
    gap = next(gap for gap in result.gaps if gap.data_domain == "ads")
    assert gap.reason_code == "enhancement_domain_gap"
    assert gap.actual_value is None
    assert gap.threshold_value is None
    assert gap.severity == "warning"


def test_duplicate_rate_at_two_percent_is_not_qualified() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(
            record("products", index=0, content="same"),
            record("products", index=1, content="same"),
        ),
    )
    result = compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)
    assert result.assessment.details["duplicate_rate_percent"] == 50.0
    assert result.assessment.quality_status == "not_qualified"
    assert any(gap.reason_code == "duplicate_rate_above_ceiling" for gap in result.gaps)


def test_source_url_coverage_below_100_is_not_qualified() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(
            record("products", index=0, source_url=None),
            record("products", index=1, source_url="https://example.com/item"),
        ),
    )
    result = compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)
    assert result.assessment.details["source_url_coverage_percent"] == 50.0
    assert result.assessment.quality_status == "not_qualified"
    assert any(gap.reason_code == "source_url_coverage_below_floor" for gap in result.gaps)


def test_field_completeness_below_80_is_not_qualified() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(
            record("products", index=0, completeness=79),
            record("products", index=1, completeness=79),
        ),
    )
    result = compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)
    assert result.assessment.details["field_completeness_percent"] == 79.0
    assert result.assessment.quality_status == "not_qualified"
    assert any(gap.reason_code == "field_completeness_below_floor" for gap in result.gaps)


def test_cross_market_record_is_rejected() -> None:
    products = DomainEvidence(
        data_domain="products",
        records=(record("products", market="DE"), record("products", index=1)),
    )
    with pytest.raises(MarketQualityInputError):
        compute_market_assessment(payload(products=products), computed_at=COMPUTED_AT)


def test_missing_core_domain_input_is_rejected() -> None:
    payload_without_reviews = MarketQualityInput(
        task_id=TASK_ID,
        market="US",
        market_role="primary",
        package_type=PackageTier.QUICK,
        evidence_grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        domains=(
            domain("products", 2),
            domain("creator_content", 2),
        ),
    )
    with pytest.raises(MarketQualityInputError):
        compute_market_assessment(payload_without_reviews, computed_at=COMPUTED_AT)


def test_conclusions_match_contract() -> None:
    assert allowed_conclusions("qualified", PackageTier.STANDARD) == (
        "enter",
        "conditional_enter",
        "do_not_enter",
        "insufficient_evidence",
    )
    assert allowed_conclusions("qualified_with_gap", PackageTier.STANDARD) == (
        "conditional_enter",
        "insufficient_evidence",
    )
    assert allowed_conclusions("not_qualified", PackageTier.STANDARD) == (
        "insufficient_evidence",
    )
    assert allowed_conclusions("qualified", PackageTier.QUICK) == (
        "worth_validating",
        "deprioritize",
        "key_risk",
        "recommend_standard_scope",
    )
    assert allowed_conclusions("qualified_with_gap", PackageTier.QUICK) == (
        "recommend_standard_scope",
        "key_risk",
        "evidence_gap",
    )
    assert allowed_conclusions("not_qualified", PackageTier.QUICK) == ("evidence_gap",)


def test_enter_requires_three_to_five_non_provisional_candidates() -> None:
    def candidates(count: int, *, provisional: int = 0) -> tuple[SkuCandidate, ...]:
        return tuple(
            SkuCandidate(
                candidate_id=f"sku-{rank}",
                rank=rank,
                provisional=rank <= provisional,
            )
            for rank in range(1, count + 1)
        )

    accepted = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.STANDARD,
        inputs=ConclusionInputs(
            requested_standard="enter",
            sku_candidates=candidates(3),
        ),
    )
    assert accepted.standard == "enter"
    assert accepted.reasons == ()

    for count in (2, 6):
        rejected = validate_conclusion(
            quality_status="qualified",
            package_type=PackageTier.STANDARD,
            inputs=ConclusionInputs(
                requested_standard="enter",
                sku_candidates=candidates(count),
            ),
        )
        assert rejected.standard is None
        assert (
            "enter_requires_3_to_5_non_provisional_sku_candidates"
            in rejected.reasons
        )

    provisional = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.STANDARD,
        inputs=ConclusionInputs(
            requested_standard="enter",
            sku_candidates=candidates(3, provisional=1),
        ),
    )
    assert provisional.standard is None


def test_conditional_enter_requires_budget_window_success_and_stop_loss() -> None:
    complete = ConclusionInputs(
        requested_standard="conditional_enter",
        test_budget_usd=Decimal("500.00"),
        observation_window_days=14,
        success_threshold="首月转化率达到试点门槛",
        stop_loss="连续两周低于止损线时停止",
    )
    accepted = validate_conclusion(
        quality_status="qualified_with_gap",
        package_type=PackageTier.STANDARD,
        inputs=complete,
    )
    assert accepted.standard == "conditional_enter"

    for missing_field in (
        "test_budget_usd",
        "observation_window_days",
        "success_threshold",
        "stop_loss",
    ):
        values = {
            "requested_standard": "conditional_enter",
            "test_budget_usd": Decimal("500.00"),
            "observation_window_days": 14,
            "success_threshold": "首月转化率达到试点门槛",
            "stop_loss": "连续两周低于止损线时停止",
        }
        values[missing_field] = None
        rejected = validate_conclusion(
            quality_status="qualified_with_gap",
            package_type=PackageTier.STANDARD,
            inputs=ConclusionInputs(**values),
        )
        assert rejected.standard is None
        assert any(
            reason.startswith("conditional_enter_requires_")
            for reason in rejected.reasons
        )


def test_do_not_enter_requires_two_c7_independent_clusters() -> None:
    one_cluster = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.STANDARD,
        inputs=ConclusionInputs(
            requested_standard="do_not_enter",
            c7_independent_cluster_count=1,
        ),
    )
    assert one_cluster.standard is None
    assert "do_not_enter_requires_two_independent_clusters" in one_cluster.reasons

    two_clusters = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.STANDARD,
        inputs=ConclusionInputs(
            requested_standard="do_not_enter",
            c7_independent_cluster_count=2,
        ),
    )
    assert two_clusters.standard == "do_not_enter"


def test_quick_conclusion_is_directional_and_not_standard() -> None:
    decision = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.QUICK,
        inputs=ConclusionInputs(requested_quick="worth_validating"),
    )
    assert decision.standard is None
    assert decision.quick == "worth_validating"

    rejected = validate_conclusion(
        quality_status="qualified",
        package_type=PackageTier.QUICK,
        inputs=ConclusionInputs(requested_quick="enter"),
    )
    assert rejected.quick is None
    assert "quick_conclusion_not_allowed" in rejected.reasons


def test_not_qualified_cannot_request_enter() -> None:
    decision = validate_conclusion(
        quality_status="not_qualified",
        package_type=PackageTier.STANDARD,
        inputs=ConclusionInputs(
            requested_standard="enter",
            sku_candidates=tuple(
                SkuCandidate(candidate_id=f"sku-{rank}", rank=rank)
                for rank in range(1, 4)
            ),
        ),
    )
    assert decision.standard is None
    assert "standard_conclusion_not_allowed" in decision.reasons


def test_scorecard_hash_is_stable_and_changes_with_status() -> None:
    first = compute_market_assessment(payload(), computed_at=COMPUTED_AT)
    second = compute_market_assessment(payload(), computed_at=COMPUTED_AT)
    third = compute_market_assessment(
        payload(reviews=DomainEvidence(data_domain="reviews", records=())),
        computed_at=COMPUTED_AT,
    )
    assert first.assessment.details["scorecard_sha256"] == second.assessment.details["scorecard_sha256"]
    assert first.assessment.details["scorecard_sha256"] != third.assessment.details["scorecard_sha256"]


def test_core_domains_constant_is_used() -> None:
    result = compute_market_assessment(payload(), computed_at=COMPUTED_AT)
    assert tuple(result.assessment.core_domain_coverage) == CORE_DATA_DOMAINS
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_quality.py -q
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.services.dataset_quality'`。

- [ ] **Step 3: 写实现**

Create `apps/api/src/data_intelligence_hub/services/dataset_quality.py`:

```python
"""逐市场质量记分卡与结构化缺口。

本模块是纯函数层。它不读库，不联网，不读时钟。
调用方必须传入市场、档位、证据等级、数据域记录和 Claim 绑定。

闸门来自设计 §5.1。数值来自 ``evidence_thresholds``。本模块不写死阈值。

缺失语义：

- 没有合格记录时状态是 ``missing``，样本数是 ``None``，不写 0。
- 被阻断时状态是 ``blocked``，样本数是 ``None``，不写空结果。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from data_intelligence_hub.services.dataset_content_hash import canonical_sha256
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    ALL_DATA_DOMAINS,
    CORE_DATA_DOMAINS,
    ENHANCEMENT_DATA_DOMAINS,
    PackageTier,
    PackageTierThreshold,
    package_threshold_for,
)
from data_intelligence_hub.tool_catalog.markets import FORMAL_MARKETS

GAP_NAMESPACE: Final[uuid.UUID] = uuid.uuid5(
    uuid.NAMESPACE_URL, "dih-c8-market-quality"
)
SCORECARD_SCHEMA_VERSION: Final[str] = "market-assessment.v1"


class MarketQualityInputError(ValueError):
    """市场质量输入不合法。"""


@dataclass(frozen=True, slots=True)
class QualityRecord:
    """一条进入质量计分的合格记录。"""

    record_id: str
    market: str
    data_domain: str
    source_url: str | None
    source_cluster_key: str | None
    content_sha256: str
    completeness_percent: int


@dataclass(frozen=True, slots=True)
class DomainEvidence:
    """一个数据域的证据。空元组表示缺失。"""

    data_domain: str
    records: tuple[QualityRecord, ...]
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class KeyClaimBinding:
    """一条关键 Claim 的证据绑定。"""

    claim_id: str
    data_domain: str
    evidence_ids: tuple[str, ...]
    independent_source_count: int


@dataclass(frozen=True, slots=True)
class SkuCandidate:
    """一个 SKU 候选。``provisional`` 表示暂定候选。"""

    candidate_id: str
    rank: int
    provisional: bool = False


@dataclass(frozen=True, slots=True)
class ConclusionInputs:
    """已批准结论的语义输入。

    ``c7_independent_cluster_count`` 必须来自 C7 的来源簇计数，
    C8 不重新计算独立来源。
    """

    requested_standard: str | None = None
    requested_quick: str | None = None
    sku_candidates: tuple[SkuCandidate, ...] = ()
    test_budget_usd: Decimal | None = None
    observation_window_days: int | None = None
    success_threshold: str | None = None
    stop_loss: str | None = None
    c7_independent_cluster_count: int = 0


@dataclass(frozen=True, slots=True)
class ConclusionDecision:
    """C8 对请求结论的校验结果。``None`` 表示不得发布该结论。"""

    standard: str | None
    quick: str | None
    allowed: tuple[str, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketQualityInput:
    """一个市场的完整质量输入。"""

    task_id: uuid.UUID
    market: str
    market_role: str
    package_type: PackageTier
    evidence_grade: EvidenceGrade
    domains: tuple[DomainEvidence, ...]
    key_claims: tuple[KeyClaimBinding, ...] = ()


@dataclass(frozen=True, slots=True)
class DataGapDraft:
    """一条待写入 ``data_gaps`` 的缺口。"""

    gap_id: uuid.UUID
    market: str
    data_domain: str
    reason_code: str
    actual_value: object | None
    threshold_value: object | None
    impact: str
    customer_text_zh: str
    customer_text_en: str
    remediation: str | None
    severity: str
    status: str = "open"


@dataclass(frozen=True, slots=True)
class MarketAssessmentDraft:
    """一条待写入 ``market_assessments`` 的记分卡。"""

    assessment_id: uuid.UUID
    task_id: uuid.UUID
    market: str
    market_role: str
    quality_status: str
    conclusion_standard: str | None
    conclusion_quick: str | None
    evidence_grade: str
    core_domain_coverage: dict[str, str]
    sample_counts: dict[str, int | None]
    thresholds: dict[str, object]
    gap_ids: tuple[uuid.UUID, ...]
    details: dict[str, object]
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class MarketAssessmentResult:
    """一次质量计算的结果。"""

    assessment: MarketAssessmentDraft
    gaps: tuple[DataGapDraft, ...]


_DOMAIN_LABELS_ZH: Final[dict[str, str]] = {
    "products": "商品",
    "reviews": "评论",
    "creator_content": "达人内容",
    "ads": "广告",
    "trends": "趋势",
}
_DOMAIN_LABELS_EN: Final[dict[str, str]] = {
    "products": "products",
    "reviews": "reviews",
    "creator_content": "creator content",
    "ads": "ads",
    "trends": "trends",
}

_REASON_TEXT: Final[dict[str, tuple[str, str, str, str]]] = {
    "data_domain_missing": (
        "blocking",
        "该数据域没有合格记录。",
        "No qualified records were collected for this data domain.",
        "补齐该数据域的采集后重跑。",
    ),
    "data_domain_blocked": (
        "critical",
        "该数据域被市场、权限、配置、条款或上游阻断。",
        "The data domain is blocked by market, permission, configuration, terms, or upstream.",
        "解除阻断并记录依据后重跑。",
    ),
    "sample_below_floor": (
        "blocking",
        "样本量低于验收门槛。",
        "The sample size is below the acceptance floor.",
        "继续采集到 floor_n 以上后重跑。",
    ),
    "field_completeness_below_floor": (
        "blocking",
        "核心字段完整率低于 80%。",
        "Core field completeness is below 80%.",
        "修正清洗规则并补齐缺失字段。",
    ),
    "duplicate_rate_above_ceiling": (
        "blocking",
        "重复率达到或超过 2%。",
        "The duplicate rate is 2% or higher.",
        "修正去重键后重新生成数据集。",
    ),
    "source_url_coverage_below_floor": (
        "blocking",
        "来源 URL 覆盖率低于 100%。",
        "Source URL coverage is below 100%.",
        "补齐来源 URL 后重新生成数据集。",
    ),
    "claim_evidence_binding_below_floor": (
        "blocking",
        "关键 Claim 证据绑定率低于 100%。",
        "Key claim evidence binding is below 100%.",
        "为每条关键 Claim 绑定至少一条证据。",
    ),
    "independent_sources_below_floor": (
        "warning",
        "关键判断的独立来源少于 2 个。",
        "A key judgment has fewer than two independent sources.",
        "补充独立来源，或把结论降为方向性。",
    ),
    "enhancement_domain_gap": (
        "warning",
        "增强数据域存在缺口。",
        "An enhancement data domain has a gap.",
        "补齐增强域，或按有缺口状态交付。",
    ),
}


def _gap_id(
    task_id: uuid.UUID,
    market: str,
    data_domain: str,
    reason_code: str,
    discriminator: str = "",
) -> uuid.UUID:
    material = f"{task_id}:{market}:{data_domain}:{reason_code}:{discriminator}"
    return uuid.uuid5(GAP_NAMESPACE, material)


def _gap(
    *,
    task_id: uuid.UUID,
    market: str,
    data_domain: str,
    reason_code: str,
    actual_value: object | None,
    threshold_value: object | None,
    discriminator: str = "",
) -> DataGapDraft:
    severity, text_zh, text_en, remediation = _REASON_TEXT[reason_code]
    impact_zh = (
        f"{market} 的{_DOMAIN_LABELS_ZH[data_domain]}未通过质量门槛"
        f"（{reason_code}），该市场不能输出完整结论。"
    )
    actual_text_zh = "缺失" if actual_value is None else str(actual_value)
    actual_text_en = "missing" if actual_value is None else str(actual_value)
    threshold_text_zh = "无" if threshold_value is None else str(threshold_value)
    threshold_text_en = "none" if threshold_value is None else str(threshold_value)
    return DataGapDraft(
        gap_id=_gap_id(task_id, market, data_domain, reason_code, discriminator),
        market=market,
        data_domain=data_domain,
        reason_code=reason_code,
        actual_value=actual_value,
        threshold_value=threshold_value,
        impact=impact_zh,
        customer_text_zh=(
            f"{text_zh} 实际值：{actual_text_zh}；门槛：{threshold_text_zh}。"
        ),
        customer_text_en=(
            f"{text_en} Actual: {actual_text_en}; threshold: {threshold_text_en}."
        ),
        remediation=remediation,
        severity=severity,
        status="open",
    )


def _domain_status(evidence: DomainEvidence, floor_n: int) -> str:
    if evidence.blocked_reason:
        return "blocked"
    if not evidence.records:
        return "missing"
    if len(evidence.records) < floor_n:
        return "partial"
    return "pass"


def _domain_actual(evidence: DomainEvidence, status: str) -> int | None:
    if status in {"missing", "blocked"}:
        return None
    return len(evidence.records)


def _field_completeness(records: Sequence[QualityRecord]) -> float | None:
    if not records:
        return None
    return round(
        sum(record.completeness_percent for record in records) / len(records), 2
    )


def _duplicate_rate(records: Sequence[QualityRecord]) -> float | None:
    if not records:
        return None
    unique = len({record.content_sha256 for record in records})
    return round((len(records) - unique) / len(records) * 100, 2)


def _source_url_coverage(records: Sequence[QualityRecord]) -> float | None:
    if not records:
        return None
    covered = sum(1 for record in records if record.source_url)
    return round(covered / len(records) * 100, 2)


def _independent_source_count(records: Sequence[QualityRecord]) -> int | None:
    """按内容折叠后统计不同来源簇。

    簇键由 C7 的 ``resolve_source_cluster`` 提供。没有簇键的记录不算独立来源。
    相同内容来自多个簇时只算一个来源。
    """
    if not records:
        return None
    by_content: dict[str, set[str]] = {}
    for record in records:
        if record.source_cluster_key:
            by_content.setdefault(record.content_sha256, set()).add(
                record.source_cluster_key
            )
    if not by_content:
        return 0
    return len({min(keys) for keys in by_content.values()})


def _domain_metric(
    domains: Sequence[DomainEvidence],
    metric: Callable[[Sequence[QualityRecord]], float | int | None],
    *,
    pick: str,
) -> tuple[float | int | None, str | None]:
    """按核心数据域分别计算，再取最差域。

    完整率与来源覆盖率取最小，重复率取最大。缺失域不参与比较；
    缺失本身已经由核心域状态阻断。
    """
    values = [
        (metric(item.records), item.data_domain)
        for item in domains
        if item.data_domain in CORE_DATA_DOMAINS and item.records
    ]
    filtered = [(value, name) for value, name in values if value is not None]
    if not filtered:
        return None, None
    if pick == "min":
        return min(filtered, key=lambda item: item[0])
    return max(filtered, key=lambda item: item[0])


def _threshold_payload(threshold: PackageTierThreshold) -> dict[str, object]:
    return {
        "package_type": threshold.tier.value,
        "products": {
            "floor_n": threshold.products_floor_n,
            "target_n": threshold.products_target_n,
            "plan_cap_n": threshold.products_plan_cap_n,
        },
        "reviews": {
            "floor_n": threshold.reviews_floor_n,
            "target_n": threshold.reviews_target_n,
            "plan_cap_n": threshold.reviews_plan_cap_n,
        },
        "creator_content": {
            "floor_n": threshold.creator_content_floor_n,
            "target_n": threshold.creator_content_target_n,
            "plan_cap_n": threshold.creator_content_plan_cap_n,
        },
        "max_evidence_grade": threshold.max_evidence_grade.value,
        "quality_gates": {
            "core_field_completeness_percent": (
                threshold.quality_gates.core_field_completeness_percent
            ),
            "max_duplicate_rate_percent": (
                threshold.quality_gates.max_duplicate_rate_percent
            ),
            "source_url_coverage_percent": (
                threshold.quality_gates.source_url_coverage_percent
            ),
            "claim_evidence_binding_percent": (
                threshold.quality_gates.claim_evidence_binding_percent
            ),
            "min_independent_sources": (
                threshold.quality_gates.min_independent_sources
            ),
        },
    }


def allowed_conclusions(status: str, tier: PackageTier) -> tuple[str, ...]:
    """返回该质量状态与档位允许的市场结论。"""
    if tier is PackageTier.STANDARD:
        if status == "qualified":
            return (
                "enter",
                "conditional_enter",
                "do_not_enter",
                "insufficient_evidence",
            )
        if status == "qualified_with_gap":
            return ("conditional_enter", "insufficient_evidence")
        return ("insufficient_evidence",)
    if status == "qualified":
        return (
            "worth_validating",
            "deprioritize",
            "key_risk",
            "recommend_standard_scope",
        )
    if status == "qualified_with_gap":
        return ("recommend_standard_scope", "key_risk", "evidence_gap")
    return ("evidence_gap",)


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_conclusion(
    *,
    quality_status: str,
    package_type: PackageTier,
    inputs: ConclusionInputs,
) -> ConclusionDecision:
    """校验请求结论是否满足已批准的语义输入。

    C8 只返回允许或拒绝与原因码。它不发布报告、不写交付 manifest。
    ``None`` 表示该结论不得发布，C9/C10 必须拒绝。
    ``3``–``5`` 个非暂定 SKU 候选与 ``2`` 个独立来源簇来自已批准结论
    语义，不是新增质量阈值。
    """
    allowed = allowed_conclusions(quality_status, package_type)
    reasons: list[str] = []

    if package_type is PackageTier.QUICK:
        requested_quick = inputs.requested_quick
        if requested_quick is None:
            return ConclusionDecision(None, None, allowed)
        if requested_quick not in allowed:
            reasons.append("quick_conclusion_not_allowed")
            return ConclusionDecision(None, None, allowed, tuple(reasons))
        return ConclusionDecision(None, requested_quick, allowed)

    requested = inputs.requested_standard
    if requested is None:
        return ConclusionDecision(None, None, allowed)
    if requested not in allowed:
        reasons.append("standard_conclusion_not_allowed")
        return ConclusionDecision(None, None, allowed, tuple(reasons))

    standard: str | None = None
    if requested == "enter":
        candidates = [
            candidate
            for candidate in inputs.sku_candidates
            if not candidate.provisional and candidate.rank >= 1
        ]
        if not 3 <= len(candidates) <= 5:
            reasons.append(
                "enter_requires_3_to_5_non_provisional_sku_candidates"
            )
        elif len({candidate.rank for candidate in candidates}) != len(candidates):
            reasons.append("sku_candidate_ranks_must_be_unique")
        else:
            standard = "enter"
    elif requested == "conditional_enter":
        conditional_missing: list[str] = []
        if inputs.test_budget_usd is None or inputs.test_budget_usd <= 0:
            conditional_missing.append("test_budget_usd")
        if (
            inputs.observation_window_days is None
            or inputs.observation_window_days <= 0
        ):
            conditional_missing.append("observation_window_days")
        if not _non_empty_text(inputs.success_threshold):
            conditional_missing.append("success_threshold")
        if not _non_empty_text(inputs.stop_loss):
            conditional_missing.append("stop_loss")
        if conditional_missing:
            reasons.extend(
                f"conditional_enter_requires_{name}"
                for name in conditional_missing
            )
        else:
            standard = "conditional_enter"
    elif requested == "do_not_enter":
        if inputs.c7_independent_cluster_count < 2:
            reasons.append("do_not_enter_requires_two_independent_clusters")
        else:
            standard = "do_not_enter"
    elif requested == "insufficient_evidence":
        standard = "insufficient_evidence"

    return ConclusionDecision(standard, None, allowed, tuple(reasons))


def _validate(payload: MarketQualityInput) -> None:
    if payload.market not in FORMAL_MARKETS:
        raise MarketQualityInputError(f"非法市场：{payload.market}")
    if payload.market_role not in {"primary", "compare"}:
        raise MarketQualityInputError(f"非法市场角色：{payload.market_role}")
    seen: set[str] = set()
    for domain_evidence in payload.domains:
        if domain_evidence.data_domain not in ALL_DATA_DOMAINS:
            raise MarketQualityInputError(
                f"非法数据域：{domain_evidence.data_domain}"
            )
        if domain_evidence.data_domain in seen:
            raise MarketQualityInputError(
                f"数据域重复：{domain_evidence.data_domain}"
            )
        seen.add(domain_evidence.data_domain)
        for record in domain_evidence.records:
            if record.market != payload.market:
                raise MarketQualityInputError(
                    f"记录 {record.record_id} 的市场是 {record.market}，"
                    f"不是 {payload.market}"
                )
            if record.data_domain != domain_evidence.data_domain:
                raise MarketQualityInputError(
                    f"记录 {record.record_id} 的数据域不匹配"
                )
    missing = set(CORE_DATA_DOMAINS) - seen
    if missing:
        raise MarketQualityInputError(
            "缺少核心数据域输入："
            + "、".join(sorted(missing))
            + "。缺失域必须显式传空 DomainEvidence。"
        )


def compute_market_assessment(
    payload: MarketQualityInput,
    *,
    computed_at: datetime,
) -> MarketAssessmentResult:
    """计算一个市场的质量状态、记分卡和缺口。"""
    _validate(payload)
    threshold = package_threshold_for(payload.package_type)
    gates = threshold.quality_gates

    coverage: dict[str, str] = {}
    sample_counts: dict[str, int | None] = {}
    gaps: list[DataGapDraft] = []
    core_floors = {
        "products": threshold.products_floor_n,
        "reviews": threshold.reviews_floor_n,
        "creator_content": threshold.creator_content_floor_n,
    }

    for domain_evidence in payload.domains:
        floor_n = core_floors.get(domain_evidence.data_domain)
        status = (
            _domain_status(domain_evidence, floor_n)
            if floor_n is not None
            else (
                "blocked"
                if domain_evidence.blocked_reason
                else ("missing" if not domain_evidence.records else "pass")
            )
        )
        coverage[domain_evidence.data_domain] = status
        actual = _domain_actual(domain_evidence, status)
        sample_counts[domain_evidence.data_domain] = actual

        if domain_evidence.data_domain in CORE_DATA_DOMAINS:
            if status == "missing":
                gaps.append(
                    _gap(
                        task_id=payload.task_id,
                        market=payload.market,
                        data_domain=domain_evidence.data_domain,
                        reason_code="data_domain_missing",
                        actual_value=None,
                        threshold_value=floor_n,
                    )
                )
            elif status == "blocked":
                gaps.append(
                    _gap(
                        task_id=payload.task_id,
                        market=payload.market,
                        data_domain=domain_evidence.data_domain,
                        reason_code="data_domain_blocked",
                        actual_value=None,
                        threshold_value=floor_n,
                        discriminator=domain_evidence.blocked_reason or "",
                    )
                )
            elif status == "partial":
                gaps.append(
                    _gap(
                        task_id=payload.task_id,
                        market=payload.market,
                        data_domain=domain_evidence.data_domain,
                        reason_code="sample_below_floor",
                        actual_value=actual,
                        threshold_value=floor_n,
                    )
                )
        elif status != "pass":
            gaps.append(
                _gap(
                    task_id=payload.task_id,
                    market=payload.market,
                    data_domain=domain_evidence.data_domain,
                    reason_code="enhancement_domain_gap",
                    actual_value=None if status in {"missing", "blocked"} else actual,
                    threshold_value=None,
                    discriminator=domain_evidence.blocked_reason or "",
                )
            )

    field_completeness, field_domain = _domain_metric(
        payload.domains, _field_completeness, pick="min"
    )
    duplicate_rate, duplicate_domain = _domain_metric(
        payload.domains, _duplicate_rate, pick="max"
    )
    source_url_coverage, coverage_domain = _domain_metric(
        payload.domains, _source_url_coverage, pick="min"
    )
    independent_sources, _independent_domain = _domain_metric(
        payload.domains, _independent_source_count, pick="min"
    )
    independent_source_counts = {
        item.data_domain: _independent_source_count(item.records)
        for item in payload.domains
        if item.data_domain in CORE_DATA_DOMAINS
    }

    if (
        field_completeness is not None
        and field_completeness < gates.core_field_completeness_percent
    ):
        gaps.append(
            _gap(
                task_id=payload.task_id,
                market=payload.market,
                data_domain=field_domain or "products",
                reason_code="field_completeness_below_floor",
                actual_value=field_completeness,
                threshold_value=gates.core_field_completeness_percent,
            )
        )

    if duplicate_rate is not None and duplicate_rate >= gates.max_duplicate_rate_percent:
        gaps.append(
            _gap(
                task_id=payload.task_id,
                market=payload.market,
                data_domain=duplicate_domain or "products",
                reason_code="duplicate_rate_above_ceiling",
                actual_value=duplicate_rate,
                threshold_value=gates.max_duplicate_rate_percent,
            )
        )

    if (
        source_url_coverage is not None
        and source_url_coverage < gates.source_url_coverage_percent
    ):
        gaps.append(
            _gap(
                task_id=payload.task_id,
                market=payload.market,
                data_domain=coverage_domain or "products",
                reason_code="source_url_coverage_below_floor",
                actual_value=source_url_coverage,
                threshold_value=gates.source_url_coverage_percent,
            )
        )

    claim_binding: float | None = None
    if payload.key_claims:
        bound = sum(1 for claim in payload.key_claims if claim.evidence_ids)
        claim_binding = round(bound / len(payload.key_claims) * 100, 2)
        for claim in payload.key_claims:
            if not claim.evidence_ids:
                gaps.append(
                    _gap(
                        task_id=payload.task_id,
                        market=payload.market,
                        data_domain=claim.data_domain,
                        reason_code="claim_evidence_binding_below_floor",
                        actual_value=0.0,
                        threshold_value=gates.claim_evidence_binding_percent,
                        discriminator=claim.claim_id,
                    )
                )
            if claim.independent_source_count < gates.min_independent_sources:
                gaps.append(
                    _gap(
                        task_id=payload.task_id,
                        market=payload.market,
                        data_domain=claim.data_domain,
                        reason_code="independent_sources_below_floor",
                        actual_value=claim.independent_source_count,
                        threshold_value=gates.min_independent_sources,
                        discriminator=claim.claim_id,
                    )
                )

    core_ok = all(coverage.get(domain) == "pass" for domain in CORE_DATA_DOMAINS)
    metrics_ok = (
        field_completeness is not None
        and field_completeness >= gates.core_field_completeness_percent
        and duplicate_rate is not None
        and duplicate_rate < gates.max_duplicate_rate_percent
        and source_url_coverage is not None
        and source_url_coverage >= gates.source_url_coverage_percent
    )
    claims_ok = claim_binding is None or claim_binding >= gates.claim_evidence_binding_percent

    enhancement_gap = any(
        coverage.get(domain) not in {None, "pass"} for domain in ENHANCEMENT_DATA_DOMAINS
    )
    key_claim_source_gap = any(
        claim.independent_source_count < gates.min_independent_sources
        for claim in payload.key_claims
    )

    if not core_ok or not metrics_ok or not claims_ok:
        quality_status = "not_qualified"
    elif enhancement_gap or key_claim_source_gap:
        quality_status = "qualified_with_gap"
    else:
        quality_status = "qualified"

    details: dict[str, object] = {
        "scorecard_schema_version": SCORECARD_SCHEMA_VERSION,
        "package_type": payload.package_type.value,
        "market_role": payload.market_role,
        "evidence_grade": payload.evidence_grade.value,
        "domain_status": dict(coverage),
        "sample_counts": dict(sample_counts),
        "field_completeness_percent": field_completeness,
        "duplicate_rate_percent": duplicate_rate,
        "source_url_coverage_percent": source_url_coverage,
        "independent_source_count": independent_sources,
        "independent_source_counts": independent_source_counts,
        "claim_evidence_binding_percent": claim_binding,
        "allowed_conclusions": list(allowed_conclusions(quality_status, payload.package_type)),
        "gaps": [
            {
                "id": str(gap.gap_id),
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
                "status": gap.status,
            }
            for gap in gaps
        ],
    }
    details["scorecard_sha256"] = canonical_sha256(details)

    assessment = MarketAssessmentDraft(
        assessment_id=uuid.uuid5(
            GAP_NAMESPACE, f"assessment:{payload.task_id}:{payload.market}"
        ),
        task_id=payload.task_id,
        market=payload.market,
        market_role=payload.market_role,
        quality_status=quality_status,
        conclusion_standard=None,
        conclusion_quick=None,
        evidence_grade=payload.evidence_grade.value,
        core_domain_coverage=dict(coverage),
        sample_counts=dict(sample_counts),
        thresholds=_threshold_payload(threshold),
        gap_ids=tuple(gap.gap_id for gap in gaps),
        details=details,
        computed_at=computed_at,
    )
    return MarketAssessmentResult(assessment=assessment, gaps=tuple(gaps))


__all__ = [
    "ConclusionDecision",
    "ConclusionInputs",
    "DataGapDraft",
    "DomainEvidence",
    "KeyClaimBinding",
    "MarketAssessmentDraft",
    "MarketAssessmentResult",
    "MarketQualityInput",
    "MarketQualityInputError",
    "QualityRecord",
    "SkuCandidate",
    "allowed_conclusions",
    "compute_market_assessment",
    "validate_conclusion",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_quality.py -q
```

Expected: `22 passed`。

- [ ] **Step 5: 运行 ruff 与 mypy**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run ruff check src/data_intelligence_hub/services/dataset_quality.py tests/unit/test_dataset_quality.py
uv run mypy src/data_intelligence_hub/services/dataset_quality.py
```

Expected: ruff 无输出；mypy `Success: no issues found`。

结论语义边界：`compute_market_assessment` 不写 `conclusion_standard`/`conclusion_quick`；它只把 `allowed_conclusions` 写入 `details`。C9/C10 在发布前调用 `validate_conclusion`：`validate_conclusion(...).standard` 为 `None` 时不得发布；为 `enter`/`conditional_enter`/`do_not_enter` 时仍由 C9/C10 执行报告门禁、审核签字与交付校验。C8 不暴露任何发布函数，也不生成报告或 manifest。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/dataset_quality.py apps/api/tests/unit/test_dataset_quality.py
git commit -m "feat(dataset): compute market quality scorecards and gaps"
```

---

### Task 7: 迁移 064 与 `dataset_versions` 扩展

**Files:**
- Create: `apps/api/alembic/versions/202610220064_dataset_quality.py`
- Modify: `apps/api/src/data_intelligence_hub/models/dataset.py`
- Create: `apps/api/tests/postgres_c8_dataset_quality/conftest.py`
- Create: `apps/api/tests/postgres_c8_dataset_quality/test_migration_064.py`

**Interfaces:**
- Consumes: C4 的 `workbench_tasks`、C6 的 `runs`/`run_steps`。
- Produces: C8 唯一创建 `market_assessments` 与 `data_gaps`；C5 的迁移 061 不创建这两张表。
- Produces: `DatasetVersion.task_id`、`market`、`schema_hash`、`content_sha256`、`license_class`、`quality_status`。
- Produces: 索引 `ix_dataset_versions_task_market`、`ix_dataset_versions_content_sha256`。
- Produces: 约束 `ck_dataset_versions_market`、`ck_dataset_versions_quality_status`、`ck_dataset_versions_content_sha256_length`、`ck_dataset_versions_schema_hash_length`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/postgres_c8_dataset_quality/conftest.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine

API_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DATABASE_SUFFIX = "_c8_dataset_quality_test"


def _guarded_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    allow_destructive = os.getenv("ALLOW_DESTRUCTIVE_MIGRATION_TEST")
    if not database_url or allow_destructive != "true":
        pytest.skip(
            "PostgreSQL migration tests require TEST_DATABASE_URL and "
            "ALLOW_DESTRUCTIVE_MIGRATION_TEST=true"
        )

    parsed = urlsplit(database_url)
    database_name = parsed.path.removeprefix("/")
    unsafe_reason: str | None = None
    if parsed.scheme != "postgresql+asyncpg":
        unsafe_reason = "TEST_DATABASE_URL must use postgresql+asyncpg"
    elif parsed.hostname not in {"localhost", "127.0.0.1"}:
        unsafe_reason = "TEST_DATABASE_URL must target localhost or 127.0.0.1"
    elif parsed.query or parsed.fragment:
        unsafe_reason = "TEST_DATABASE_URL must not contain query or fragment overrides"
    elif "%" in parsed.netloc or "%" in parsed.path:
        unsafe_reason = "TEST_DATABASE_URL must not contain encoded host or database parts"
    elif not database_name.endswith(ALLOWED_DATABASE_SUFFIX):
        unsafe_reason = f"TEST_DATABASE_URL database must end with {ALLOWED_DATABASE_SUFFIX}"

    if unsafe_reason is not None:
        raise pytest.UsageError(unsafe_reason)
    return database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


@pytest.fixture()
def postgres_database_url() -> str:
    database_url = _guarded_database_url()
    engine = create_engine(_sync_database_url(database_url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )
    return database_url
```

Create `apps/api/tests/postgres_c8_dataset_quality/test_migration_064.py`:

```python
"""迁移 064 的升级与降级。"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, inspect

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    API_ROOT / "alembic/versions/202610220064_dataset_quality.py"
)
DATASET_COLUMNS = {
    "task_id",
    "market",
    "schema_hash",
    "content_sha256",
    "license_class",
    "quality_status",
}


def load_module():
    spec = importlib.util.spec_from_file_location("migration_064", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sync_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def run_alembic(database_url: str, command: str, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        ["uv", "run", "alembic", command, revision],
        cwd=API_ROOT,
        env=environment,
        check=True,
    )


def test_revision_chain_is_frozen() -> None:
    module = load_module()
    assert module.revision == "202610220064"
    assert module.down_revision == "202610220063"


def test_migration_adds_and_removes_dataset_columns(
    postgres_database_url: str,
) -> None:
    engine = create_engine(sync_url(postgres_database_url))
    try:
        inspector = inspect(engine)
        columns = {
            column["name"]
            for column in inspector.get_columns("dataset_versions")
        }
        assert DATASET_COLUMNS <= columns
        assert inspector.has_table("data_gaps") is True
        assert inspector.has_table("market_assessments") is True

        run_alembic(postgres_database_url, "downgrade", "202610220063")
        downgraded_inspector = inspect(engine)
        downgraded = {
            column["name"]
            for column in downgraded_inspector.get_columns("dataset_versions")
        }
        assert DATASET_COLUMNS.isdisjoint(downgraded)
        assert downgraded_inspector.has_table("data_gaps") is False
        assert downgraded_inspector.has_table("market_assessments") is False

        run_alembic(postgres_database_url, "upgrade", "head")
        upgraded_inspector = inspect(engine)
        upgraded = {
            column["name"]
            for column in upgraded_inspector.get_columns("dataset_versions")
        }
        assert DATASET_COLUMNS <= upgraded
        assert upgraded_inspector.has_table("data_gaps") is True
        assert upgraded_inspector.has_table("market_assessments") is True
    finally:
        engine.dispose()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/postgres_c8_dataset_quality/test_migration_064.py -q
```

Expected: FAIL，`FileNotFoundError` 或 `ModuleNotFoundError`，因为迁移文件不存在。

- [ ] **Step 3: 写迁移**

Create `apps/api/alembic/versions/202610220064_dataset_quality.py`:

```python
"""Add dataset content hashes and quality projection.

Revision ID: 202610220064
Revises: 202610220063
Create Date: 2026-10-22

本迁移扩展 ``dataset_versions``，并创建 ``market_assessments`` 与 ``data_gaps``。
C5 的迁移 061 不创建这两张质量表。C8 是它们的唯一创建者。
本迁移要求 C4 的 ``workbench_tasks`` 与 C6 的 ``runs``/``run_steps`` 已存在。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220064"
down_revision: str | None = "202610220063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MARKETS = ("US", "GB", "DE", "FR", "IT", "ES", "IE", "NL", "BE", "AT", "PL")
_QUALITY_STATUSES = ("qualified", "qualified_with_gap", "not_qualified")
_DATA_DOMAINS = ("products", "reviews", "creator_content", "ads", "trends")
_MARKET_ROLES = ("primary", "compare")
_GAP_SEVERITIES = ("info", "warning", "blocking", "critical")
_GAP_STATUSES = ("open", "mitigated", "accepted", "closed")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    missing = [
        table
        for table in ("workbench_tasks", "runs", "run_steps")
        if not inspector.has_table(table)
    ]
    if missing:
        raise RuntimeError(
            "C4/C6 tables are required before C8 migration: " + ", ".join(missing)
        )

    op.create_table(
        "data_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("data_domain", sa.String(length=30), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("actual_value", sa.JSON(), nullable=True),
        sa.Column("threshold_value", sa.JSON(), nullable=True),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("customer_text_zh", sa.Text(), nullable=False),
        sa.Column("customer_text_en", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_data_gaps"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_data_gaps_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_data_gaps_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["workbench_tasks.id"],
            name="fk_data_gaps_task_id_workbench_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_data_gaps_run_id_runs"
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["run_steps.id"], name="fk_data_gaps_step_id_run_steps"
        ),
        sa.CheckConstraint(
            "market IN (" + ", ".join(f"'{value}'" for value in _MARKETS) + ")",
            name="ck_data_gaps_market",
        ),
        sa.CheckConstraint(
            "data_domain IN ("
            + ", ".join(f"'{value}'" for value in _DATA_DOMAINS)
            + ")",
            name="ck_data_gaps_data_domain",
        ),
        sa.CheckConstraint(
            "severity IN ("
            + ", ".join(f"'{value}'" for value in _GAP_SEVERITIES)
            + ")",
            name="ck_data_gaps_severity",
        ),
        sa.CheckConstraint(
            "status IN ("
            + ", ".join(f"'{value}'" for value in _GAP_STATUSES)
            + ")",
            name="ck_data_gaps_status",
        ),
    )
    op.create_index(
        "ix_data_gaps_task_market_domain",
        "data_gaps",
        ["task_id", "market", "data_domain"],
    )

    op.create_table(
        "market_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("market_role", sa.String(length=20), nullable=False),
        sa.Column("quality_status", sa.String(length=30), nullable=False),
        sa.Column("conclusion_standard", sa.String(length=30), nullable=True),
        sa.Column("conclusion_quick", sa.String(length=30), nullable=True),
        sa.Column("evidence_grade", sa.String(length=30), nullable=False),
        sa.Column("core_domain_coverage", sa.JSON(), nullable=False),
        sa.Column("sample_counts", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("gap_ids", sa.JSON(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_market_assessments"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_market_assessments_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_market_assessments_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["workbench_tasks.id"],
            name="fk_market_assessments_task_id_workbench_tasks",
        ),
        sa.UniqueConstraint(
            "task_id", "market", name="uq_market_assessments_task_market"
        ),
        sa.CheckConstraint(
            "market IN (" + ", ".join(f"'{value}'" for value in _MARKETS) + ")",
            name="ck_market_assessments_market",
        ),
        sa.CheckConstraint(
            "market_role IN ("
            + ", ".join(f"'{value}'" for value in _MARKET_ROLES)
            + ")",
            name="ck_market_assessments_market_role",
        ),
        sa.CheckConstraint(
            "quality_status IN ("
            + ", ".join(f"'{value}'" for value in _QUALITY_STATUSES)
            + ")",
            name="ck_market_assessments_quality_status",
        ),
    )
    op.create_index(
        "ix_market_assessments_task_market",
        "market_assessments",
        ["task_id", "market"],
        unique=True,
    )

    op.add_column("dataset_versions", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.add_column(
        "dataset_versions",
        sa.Column("market", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("schema_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("license_class", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("quality_status", sa.String(length=30), nullable=True),
    )
    op.create_foreign_key(
        "fk_dataset_versions_task_id_workbench_tasks",
        "dataset_versions",
        "workbench_tasks",
        ["task_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_dataset_versions_market",
        "dataset_versions",
        "market IS NULL OR market IN ("
        + ", ".join(f"'{value}'" for value in _MARKETS)
        + ")",
    )
    op.create_check_constraint(
        "ck_dataset_versions_quality_status",
        "dataset_versions",
        "quality_status IS NULL OR quality_status IN ("
        + ", ".join(f"'{value}'" for value in _QUALITY_STATUSES)
        + ")",
    )
    op.create_check_constraint(
        "ck_dataset_versions_content_sha256_length",
        "dataset_versions",
        "content_sha256 IS NULL OR length(content_sha256) = 64",
    )
    op.create_check_constraint(
        "ck_dataset_versions_schema_hash_length",
        "dataset_versions",
        "schema_hash IS NULL OR length(schema_hash) = 64",
    )
    op.create_index(
        "ix_dataset_versions_task_market",
        "dataset_versions",
        ["task_id", "market"],
    )
    op.create_index(
        "ix_dataset_versions_content_sha256",
        "dataset_versions",
        ["dataset_id", "content_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dataset_versions_content_sha256",
        table_name="dataset_versions",
    )
    op.drop_index(
        "ix_dataset_versions_task_market",
        table_name="dataset_versions",
    )
    op.drop_constraint(
        "ck_dataset_versions_schema_hash_length",
        "dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_dataset_versions_content_sha256_length",
        "dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_dataset_versions_quality_status",
        "dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_dataset_versions_market",
        "dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        "fk_dataset_versions_task_id_workbench_tasks",
        "dataset_versions",
        type_="foreignkey",
    )
    op.drop_column("dataset_versions", "quality_status")
    op.drop_column("dataset_versions", "license_class")
    op.drop_column("dataset_versions", "content_sha256")
    op.drop_column("dataset_versions", "schema_hash")
    op.drop_column("dataset_versions", "market")
    op.drop_column("dataset_versions", "task_id")
    op.drop_index(
        "ix_market_assessments_task_market",
        table_name="market_assessments",
    )
    op.drop_table("market_assessments")
    op.drop_index(
        "ix_data_gaps_task_market_domain",
        table_name="data_gaps",
    )
    op.drop_table("data_gaps")
```

- [ ] **Step 4: 修改模型**

Modify `apps/api/src/data_intelligence_hub/models/dataset.py`。在 `DatasetVersion.__table_args__` 追加：

```python
        CheckConstraint(
            "market IS NULL OR market IN "
            "('US','GB','DE','FR','IT','ES','IE','NL','BE','AT','PL')",
            name="ck_dataset_versions_market",
        ),
        CheckConstraint(
            "quality_status IS NULL OR quality_status IN "
            "('qualified','qualified_with_gap','not_qualified')",
            name="ck_dataset_versions_quality_status",
        ),
        CheckConstraint(
            "content_sha256 IS NULL OR length(content_sha256) = 64",
            name="ck_dataset_versions_content_sha256_length",
        ),
        CheckConstraint(
            "schema_hash IS NULL OR length(schema_hash) = 64",
            name="ck_dataset_versions_schema_hash_length",
        ),
```

在 `DatasetVersion` 的列声明中追加：

```python
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workbench_tasks.id"))
    market: Mapped[str | None] = mapped_column(String(2))
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    license_class: Mapped[str | None] = mapped_column(String(30))
    quality_status: Mapped[str | None] = mapped_column(String(30))
```

- [ ] **Step 4b: 创建 C8 质量模型**

Create `apps/api/src/data_intelligence_hub/models/data_gap.py`:

```python
"""``data_gaps`` 结构化缺口模型。

表由 C8 迁移 064 创建。C5 不创建这张表。
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
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class DataGap(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_gaps"
    __table_args__ = (
        CheckConstraint(
            "market IN ('US','GB','DE','FR','IT','ES','IE','NL','BE','AT','PL')",
            name="ck_data_gaps_market",
        ),
        CheckConstraint(
            "data_domain IN ('products','reviews','creator_content','ads','trends')",
            name="ck_data_gaps_data_domain",
        ),
        CheckConstraint(
            "severity IN ('info','warning','blocking','critical')",
            name="ck_data_gaps_severity",
        ),
        CheckConstraint(
            "status IN ('open','mitigated','accepted','closed')",
            name="ck_data_gaps_status",
        ),
        Index("ix_data_gaps_task_market_domain", "task_id", "market", "data_domain"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workbench_tasks.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run_steps.id"))
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    data_domain: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    actual_value: Mapped[Any | None] = mapped_column(JSON)
    threshold_value: Mapped[Any | None] = mapped_column(JSON)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    customer_text_zh: Mapped[str] = mapped_column(Text, nullable=False)
    customer_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["DataGap"]
```

Create `apps/api/src/data_intelligence_hub/models/market_assessment.py`:

```python
"""``market_assessments`` 逐市场质量记分卡模型。

表由 C8 迁移 064 创建。C5 不创建这张表。
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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class MarketAssessment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "market_assessments"
    __table_args__ = (
        UniqueConstraint("task_id", "market", name="uq_market_assessments_task_market"),
        CheckConstraint(
            "market IN ('US','GB','DE','FR','IT','ES','IE','NL','BE','AT','PL')",
            name="ck_market_assessments_market",
        ),
        CheckConstraint(
            "market_role IN ('primary','compare')",
            name="ck_market_assessments_market_role",
        ),
        CheckConstraint(
            "quality_status IN ('qualified','qualified_with_gap','not_qualified')",
            name="ck_market_assessments_quality_status",
        ),
        Index("ix_market_assessments_task_market", "task_id", "market", unique=True),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workbench_tasks.id"), nullable=False
    )
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    market_role: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(30), nullable=False)
    conclusion_standard: Mapped[str | None] = mapped_column(String(30))
    conclusion_quick: Mapped[str | None] = mapped_column(String(30))
    evidence_grade: Mapped[str] = mapped_column(String(30), nullable=False)
    core_domain_coverage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sample_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    gap_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["MarketAssessment"]
```

在 `apps/api/src/data_intelligence_hub/models/__init__.py` 导出 `DataGap` 与 `MarketAssessment`。

- [ ] **Step 5: 运行迁移测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run alembic heads
```

Expected: `202610220064 (head)`。

Run the guarded PostgreSQL test:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/dih_c8_dataset_quality_test \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest tests/postgres_c8_dataset_quality/test_migration_064.py -q
```

Expected: `2 passed`。没有设置环境变量时是 `1 passed, 1 skipped`。发布验收必须使用真实 PostgreSQL 跑出 `2 passed`。

- [ ] **Step 6: 运行模型单元守卫**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run python - <<'PY'
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.market_assessment import MarketAssessment

columns = DatasetVersion.__table__.columns
for name in (
    "task_id",
    "market",
    "schema_hash",
    "content_sha256",
    "license_class",
    "quality_status",
):
    assert name in columns, name
    assert columns[name].nullable is True, name
print("dataset version columns ok")
PY
```

Expected: `dataset version columns ok`。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/models/dataset.py \
  apps/api/src/data_intelligence_hub/models/data_gap.py \
  apps/api/src/data_intelligence_hub/models/market_assessment.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/alembic/versions/202610220064_dataset_quality.py \
  apps/api/tests/postgres_c8_dataset_quality
git commit -m "feat(dataset): migrate dataset version hashes and quality projection"
```

---

### Task 8: 质量持久化、项目 ACL 与 `/assets` 响应字段

**Files:**
- Create: `apps/api/src/data_intelligence_hub/repositories/dataset_quality.py`
- Create: `apps/api/src/data_intelligence_hub/services/quality_audit.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/automation.py`
- Modify: `apps/api/src/data_intelligence_hub/services/automation_service.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/automation.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/datasets.py`
- Create: `apps/api/tests/unit/test_dataset_quality_repository.py`
- Create: `apps/api/tests/unit/test_quality_audit.py`
- Create: `apps/api/tests/integration/test_c8_project_acl.py`

**Interfaces:**
- Consumes: `MarketAssessmentDraft`、`DataGapDraft`、C8 的 `MarketAssessment`/`DataGap`、C2 的 `require_project_access` 与 `append_audit_event`。
- Produces: `get_market_assessment(session, *, task_id, market, workspace_id=None, project_id=None) -> MarketAssessment | None`。
- Produces: `list_data_gaps(session, *, task_id, market, workspace_id=None, project_id=None, status=None) -> list[DataGap]`。
- Produces: `list_dataset_versions_for_task_market(session, *, workspace_id, project_id, task_id, market) -> list[DatasetVersion]`。
- Produces: `set_data_gap_status(session, *, workspace_id, project_id, gap_id, status, resolved_at) -> DataGap`；只允许 `mitigated`/`accepted`/`closed`。
- Produces: `upsert_market_assessment(session, *, workspace_id, project_id, draft, gaps) -> MarketAssessment`。
- Produces: `sync_dataset_quality_status(session, *, dataset_version_id) -> str | None`。
- Produces: `MarketQualityConflictError(ValueError)`、`DataGapNotFoundError(LookupError)`。
- Produces: `quality_audit.ACTION_ASSESSMENT_COMPUTED`、`ACTION_GAP_RESOLVED`、`ACTION_TEMPLATE_CHANGED`、`record_assessment_computed`、`record_gap_resolved`、`record_template_change_if_needed`。
- Produces: `AutomationMarketAssessmentResponse`、`AutomationDataGapResponse`。
- Produces: `AutomationDatasetVersionResponse.task_id`、`market`、`schema_hash`、`content_sha256`、`license_class`、`quality_status`。
- Produces: `AutomationProductDatasetVersionPreviewResponse.quality_assessment`、`data_gaps`。
- Produces: 路由 ACL：`GET /api/automation/product-datasets`、`GET /api/automation/product-datasets/{dataset_id}/versions`、`GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/preview`、`DELETE /api/automation/product-datasets/{dataset_id}` 与三个保存函数接入 `require_project_access`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_dataset_quality_repository.py`:

```python
"""质量记分卡持久化。

本测试只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    Dataset,
    DatasetVersion,
    Project,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.repositories.dataset_quality import (
    DataGapNotFoundError,
    MarketQualityConflictError,
    get_market_assessment,
    list_data_gaps,
    set_data_gap_status,
    sync_dataset_quality_status,
    upsert_market_assessment,
)
from data_intelligence_hub.services.dataset_quality import (
    DataGapDraft,
    MarketAssessmentDraft,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()
DATASET_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()


@pytest.fixture()
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
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
            Dataset(
                id=DATASET_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                name="C8 dataset",
                dataset_type="ecommerce_product",
                status="active",
                description=None,
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
                version_number=1,
                source_task_run_ids=[],
                selected_fields=["title"],
                cleaning_script=[],
                rows=[],
                export_preview={},
                row_count=0,
                average_completeness_percent=0,
                status="saved",
                created_at=NOW,
                task_id=TASK_ID,
                market="US",
                content_sha256="a" * 64,
                schema_hash="b" * 64,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


def draft(*, quality_status: str = "qualified_with_gap") -> MarketAssessmentDraft:
    return MarketAssessmentDraft(
        assessment_id=uuid.uuid5(uuid.NAMESPACE_URL, f"assessment:{TASK_ID}:US"),
        task_id=TASK_ID,
        market="US",
        market_role="primary",
        quality_status=quality_status,
        conclusion_standard=None,
        conclusion_quick=None,
        evidence_grade="L4_authorized_live",
        core_domain_coverage={
            "products": "pass",
            "reviews": "pass",
            "creator_content": "pass",
        },
        sample_counts={"products": 100, "reviews": 2000, "creator_content": 200},
        thresholds={"package_type": "standard"},
        gap_ids=(),
        details={
            "scorecard_sha256": "c" * 64,
            "sample_counts": {"products": 100, "reviews": 2000, "creator_content": 200},
        },
        computed_at=NOW,
    )


def gap() -> DataGapDraft:
    return DataGapDraft(
        gap_id=uuid.uuid5(uuid.NAMESPACE_URL, f"gap:{TASK_ID}:US:reviews"),
        market="US",
        data_domain="reviews",
        reason_code="sample_below_floor",
        actual_value=10,
        threshold_value=2000,
        impact="US 评论样本不足。",
        customer_text_zh="评论样本不足。实际值：10；门槛：2000。",
        customer_text_en="Reviews sample is below the floor. Actual: 10; threshold: 2000.",
        remediation="继续采集。",
        severity="blocking",
        status="open",
    )


async def test_upsert_is_idempotent(session: AsyncSession) -> None:
    first = await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    second = await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    assert first.id == second.id
    assert len(await list_data_gaps(session, task_id=TASK_ID, market="US")) == 1


async def test_conflicting_scorecard_is_rejected(session: AsyncSession) -> None:
    await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    changed = draft(quality_status="qualified")
    changed.details["scorecard_sha256"] = "d" * 64
    with pytest.raises(MarketQualityConflictError):
        await upsert_market_assessment(
            session,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            draft=changed,
            gaps=(gap(),),
        )


async def test_sync_dataset_quality_status(session: AsyncSession) -> None:
    assert await sync_dataset_quality_status(session, dataset_version_id=VERSION_ID) is None
    await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    assert await sync_dataset_quality_status(session, dataset_version_id=VERSION_ID) == (
        "qualified_with_gap"
    )
    version = await session.get(DatasetVersion, VERSION_ID)
    assert version is not None
    assert version.quality_status == "qualified_with_gap"


async def test_version_without_task_market_has_null_quality(session: AsyncSession) -> None:
    version = await session.get(DatasetVersion, VERSION_ID)
    assert version is not None
    version.task_id = None
    version.market = None
    await session.commit()
    assert await sync_dataset_quality_status(session, dataset_version_id=VERSION_ID) is None
    await session.refresh(version)
    assert version.quality_status is None


async def test_assessment_reads_are_scoped_by_workspace_and_project(
    session: AsyncSession,
) -> None:
    await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    assert (
        await get_market_assessment(
            session,
            task_id=TASK_ID,
            market="US",
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
        )
        is not None
    )
    assert (
        await get_market_assessment(
            session,
            task_id=TASK_ID,
            market="US",
            workspace_id=WORKSPACE_ID,
            project_id=uuid.uuid4(),
        )
        is None
    )
    assert (
        await list_data_gaps(
            session,
            task_id=TASK_ID,
            market="US",
            workspace_id=WORKSPACE_ID,
            project_id=uuid.uuid4(),
        )
        == []
    )


async def test_set_data_gap_status_is_scoped_and_rejects_open(
    session: AsyncSession,
) -> None:
    await upsert_market_assessment(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        draft=draft(),
        gaps=(gap(),),
    )
    resolved = await set_data_gap_status(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        gap_id=gap().gap_id,
        status="mitigated",
        resolved_at=NOW,
    )
    assert resolved.status == "mitigated"
    assert resolved.resolved_at == NOW

    with pytest.raises(ValueError):
        await set_data_gap_status(
            session,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            gap_id=gap().gap_id,
            status="open",
            resolved_at=NOW,
        )

    with pytest.raises(DataGapNotFoundError):
        await set_data_gap_status(
            session,
            workspace_id=WORKSPACE_ID,
            project_id=uuid.uuid4(),
            gap_id=gap().gap_id,
            status="closed",
            resolved_at=NOW,
        )

```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_quality_repository.py -q
```

Expected: FAIL，`ModuleNotFoundError: No module named 'data_intelligence_hub.repositories.dataset_quality'`。

- [ ] **Step 3: 写 repository**

Create `apps/api/src/data_intelligence_hub/repositories/dataset_quality.py`:

```python
"""市场质量记分卡与缺口的持久化。

本模块只 flush，不 commit。事务边界由调用方负责。

幂等规则：

- 同一 ``task_id`` + ``market`` 只允许一条 ``market_assessments``。
- 相同 ``details.scorecard_sha256`` 的重复写入是幂等操作。
- 不同 ``scorecard_sha256`` 的写入被拒绝。重跑必须创建新 task。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models import DataGap, DatasetVersion, MarketAssessment
from data_intelligence_hub.services.dataset_quality import (
    DataGapDraft,
    MarketAssessmentDraft,
)


class MarketQualityConflictError(ValueError):
    """同一任务市场的记分卡内容冲突。"""


class DataGapNotFoundError(LookupError):
    """缺口不存在或不属于给定工作区与项目。"""


async def get_market_assessment(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    market: str,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> MarketAssessment | None:
    statement = select(MarketAssessment).where(
        MarketAssessment.task_id == task_id,
        MarketAssessment.market == market,
    )
    if workspace_id is not None:
        statement = statement.where(MarketAssessment.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(MarketAssessment.project_id == project_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_data_gaps(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    market: str,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[DataGap]:
    statement = select(DataGap).where(
        DataGap.task_id == task_id,
        DataGap.market == market,
    )
    if workspace_id is not None:
        statement = statement.where(DataGap.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(DataGap.project_id == project_id)
    if status is not None:
        statement = statement.where(DataGap.status == status)
    result = await session.execute(
        statement.order_by(DataGap.data_domain, DataGap.reason_code, DataGap.id)
    )
    return list(result.scalars().all())


async def set_data_gap_status(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    gap_id: uuid.UUID,
    status: str,
    resolved_at: datetime,
) -> DataGap:
    """解除一个缺口。只允许非 ``open`` 的终态。"""
    if status not in {"mitigated", "accepted", "closed"}:
        raise ValueError(f"非法缺口状态：{status}")
    gap = await session.get(DataGap, gap_id)
    if (
        gap is None
        or gap.workspace_id != workspace_id
        or gap.project_id != project_id
    ):
        raise DataGapNotFoundError(str(gap_id))
    gap.status = status
    gap.resolved_at = resolved_at
    await session.flush()
    return gap


def _gap_row(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    draft: DataGapDraft,
    created_at: datetime,
) -> DataGap:
    return DataGap(
        id=draft.gap_id,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        market=draft.market,
        data_domain=draft.data_domain,
        reason_code=draft.reason_code,
        actual_value=draft.actual_value,
        threshold_value=draft.threshold_value,
        impact=draft.impact,
        customer_text_zh=draft.customer_text_zh,
        customer_text_en=draft.customer_text_en,
        remediation=draft.remediation,
        severity=draft.severity,
        status=draft.status,
        created_at=created_at,
        resolved_at=None,
    )


async def upsert_market_assessment(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    draft: MarketAssessmentDraft,
    gaps: tuple[DataGapDraft, ...],
) -> MarketAssessment:
    """写入一条记分卡与它的缺口。返回已存在或新建的记分卡。"""
    existing = await get_market_assessment(
        session,
        task_id=draft.task_id,
        market=draft.market,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    if existing is not None:
        existing_hash = str(existing.details_json.get("scorecard_sha256", ""))
        new_hash = str(draft.details.get("scorecard_sha256", ""))
        if existing_hash != new_hash:
            raise MarketQualityConflictError(
                "同一任务市场的记分卡内容不同。重跑必须创建新 task。"
            )
        existing_gap_ids = {str(gap_id) for gap_id in (existing.gap_ids or [])}
        for gap in gaps:
            if str(gap.gap_id) not in existing_gap_ids:
                session.add(
                    _gap_row(
                        workspace_id=workspace_id,
                        project_id=project_id,
                        task_id=draft.task_id,
                        draft=gap,
                        created_at=draft.computed_at,
                    )
                )
        await session.flush()
        return existing

    assessment = MarketAssessment(
        id=draft.assessment_id,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=draft.task_id,
        market=draft.market,
        market_role=draft.market_role,
        quality_status=draft.quality_status,
        conclusion_standard=draft.conclusion_standard,
        conclusion_quick=draft.conclusion_quick,
        evidence_grade=draft.evidence_grade,
        core_domain_coverage=dict(draft.core_domain_coverage),
        sample_counts=dict(draft.sample_counts),
        thresholds=dict(draft.thresholds),
        gap_ids=[str(gap.gap_id) for gap in gaps],
        details_json=dict(draft.details),
        computed_at=draft.computed_at,
    )
    session.add(assessment)
    for gap in gaps:
        session.add(
            _gap_row(
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=draft.task_id,
                draft=gap,
                created_at=draft.computed_at,
            )
        )
    await session.flush()
    return assessment


async def sync_dataset_quality_status(
    session: AsyncSession,
    *,
    dataset_version_id: uuid.UUID,
) -> str | None:
    """把市场记分卡的状态投影到 ``dataset_versions.quality_status``。

    没有 task_id、没有 market 或没有记分卡时写 ``None``。
    不得写 ``not_qualified``，也不得写 0。
    """
    version = await session.get(DatasetVersion, dataset_version_id)
    if version is None:
        raise ValueError(f"数据集版本不存在：{dataset_version_id}")
    if version.task_id is None or version.market is None:
        version.quality_status = None
        await session.flush()
        return None
    assessment = await get_market_assessment(
        session,
        task_id=version.task_id,
        market=version.market,
        workspace_id=version.workspace_id,
        project_id=version.project_id,
    )
    version.quality_status = assessment.quality_status if assessment is not None else None
    await session.flush()
    return version.quality_status


async def list_dataset_versions_for_task_market(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    market: str,
) -> list[DatasetVersion]:
    """按项目读取一个任务市场的正式数据集版本。"""
    result = await session.execute(
        select(DatasetVersion)
        .where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.project_id == project_id,
            DatasetVersion.task_id == task_id,
            DatasetVersion.market == market,
        )
        .order_by(DatasetVersion.version_number, DatasetVersion.id)
    )
    return list(result.scalars().all())


__all__ = [
    "DataGapNotFoundError",
    "MarketQualityConflictError",
    "get_market_assessment",
    "list_data_gaps",
    "list_dataset_versions_for_task_market",
    "set_data_gap_status",
    "sync_dataset_quality_status",
    "upsert_market_assessment",
]
```

调用约定：C5/C6 在 `upsert_market_assessment` 之后，对同一 `task_id` + `market` 的数据集版本调用 `sync_dataset_quality_status`。C8 不自动扫描全表。`/assets` 只读取 `dataset_versions.quality_status` 与版本预览中的评估/缺口。

- [ ] **Step 4: 运行 repository 测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_dataset_quality_repository.py -q
```

Expected: `6 passed`。

- [ ] **Step 5: 扩展 API schema**

Modify `apps/api/src/data_intelligence_hub/schemas/automation.py`。

在 `AutomationDatasetVersionResponse` 追加：

```python
    task_id: uuid.UUID | None = None
    market: str | None = None
    schema_hash: str | None = None
    content_sha256: str | None = None
    license_class: str | None = None
    quality_status: Literal["qualified", "qualified_with_gap", "not_qualified"] | None = None
```

在 `AutomationProductDatasetVersionPreviewResponse` 之前追加：

```python
class AutomationMarketAssessmentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    market: str
    market_role: str
    quality_status: Literal["qualified", "qualified_with_gap", "not_qualified"]
    conclusion_standard: str | None = None
    conclusion_quick: str | None = None
    evidence_grade: str
    core_domain_coverage: dict[str, str]
    sample_counts: dict[str, int | None]
    thresholds: dict[str, Any]
    gap_ids: list[str]
    details_json: dict[str, Any]
    computed_at: datetime


class AutomationDataGapResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    market: str
    data_domain: str
    reason_code: str
    actual_value: Any | None = None
    threshold_value: Any | None = None
    impact: str
    customer_text_zh: str
    customer_text_en: str
    remediation: str | None = None
    severity: Literal["info", "warning", "blocking", "critical"]
    status: Literal["open", "mitigated", "accepted", "closed"]
    created_at: datetime
    resolved_at: datetime | None = None
```

在 `AutomationProductDatasetVersionPreviewResponse` 追加：

```python
    quality_assessment: AutomationMarketAssessmentResponse | None = None
    data_gaps: list[AutomationDataGapResponse] = Field(default_factory=list)
```

- [ ] **Step 6: 扩展 service**

Modify `apps/api/src/data_intelligence_hub/services/automation_service.py`。

在文件顶部导入区追加：

```python
from data_intelligence_hub.repositories.dataset_quality import (
    get_market_assessment,
    list_data_gaps,
)
```

在 `_dataset_version_response` 中追加字段：

```python
        task_id=version.task_id,
        market=version.market,
        schema_hash=version.schema_hash,
        content_sha256=version.content_sha256,
        license_class=version.license_class,
        quality_status=version.quality_status,
```

在 `_dataset_version_response` 之后追加：

```python
def _market_assessment_response(
    assessment: object,
) -> AutomationMarketAssessmentResponse:
    return AutomationMarketAssessmentResponse(
        id=assessment.id,
        task_id=assessment.task_id,
        market=assessment.market,
        market_role=assessment.market_role,
        quality_status=assessment.quality_status,
        conclusion_standard=assessment.conclusion_standard,
        conclusion_quick=assessment.conclusion_quick,
        evidence_grade=assessment.evidence_grade,
        core_domain_coverage=assessment.core_domain_coverage,
        sample_counts=assessment.sample_counts,
        thresholds=assessment.thresholds,
        gap_ids=list(assessment.gap_ids),
        details_json=assessment.details_json,
        computed_at=assessment.computed_at,
    )


def _data_gap_response(gap: object) -> AutomationDataGapResponse:
    return AutomationDataGapResponse(
        id=gap.id,
        task_id=gap.task_id,
        market=gap.market,
        data_domain=gap.data_domain,
        reason_code=gap.reason_code,
        actual_value=gap.actual_value,
        threshold_value=gap.threshold_value,
        impact=gap.impact,
        customer_text_zh=gap.customer_text_zh,
        customer_text_en=gap.customer_text_en,
        remediation=gap.remediation,
        severity=gap.severity,
        status=gap.status,
        created_at=gap.created_at,
        resolved_at=gap.resolved_at,
    )
```

在 `get_product_dataset_version_preview` 中，`all_rows = _dataset_export_rows(version)` 之前追加：

```python
    assessment = None
    gaps = []
    if version.task_id is not None and version.market is not None:
        assessment = await get_market_assessment(
            session,
            task_id=version.task_id,
            market=version.market,
            workspace_id=workspace.id,
            project_id=version.project_id,
        )
        gaps = await list_data_gaps(
            session,
            task_id=version.task_id,
            market=version.market,
            workspace_id=workspace.id,
            project_id=version.project_id,
        )
```

在返回对象中追加：

```python
        quality_assessment=(
            _market_assessment_response(assessment)
            if assessment is not None
            else None
        ),
        data_gaps=[_data_gap_response(gap) for gap in gaps],
```

- [ ] **Step 7: 写审计模块、项目 ACL 与测试**

Create `apps/api/src/data_intelligence_hub/services/quality_audit.py`：

```python
"""C8 质量审计事件。

只调用 C2 的 ``append_audit_event``。不建审计表，不复制哈希链。
审计 details 只写 ID、市场、状态、摘要哈希与原因码。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.workbench_templates import (
    template_registry_digest,
)

ACTION_ASSESSMENT_COMPUTED = "quality.assessment.computed"
ACTION_GAP_RESOLVED = "quality.gap.resolved"
ACTION_TEMPLATE_CHANGED = "quality.template.changed"

RESOURCE_ASSESSMENT = "market_assessment"
RESOURCE_GAP = "data_gap"
RESOURCE_TEMPLATE = "workbench_template"


async def record_assessment_computed(
    session: AsyncSession,
    *,
    assessment: Any,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    details = dict(assessment.details_json or {})
    return await append_audit_event(
        session,
        workspace_id=assessment.workspace_id,
        project_id=assessment.project_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type or ("user" if actor_user_id else "system"),
        action=ACTION_ASSESSMENT_COMPUTED,
        resource_type=RESOURCE_ASSESSMENT,
        resource_id=str(assessment.id),
        request_id=request_id,
        details={
            "task_id": str(assessment.task_id),
            "market": assessment.market,
            "quality_status": assessment.quality_status,
            "scorecard_sha256": details.get("scorecard_sha256"),
            "allowed_conclusions": list(details.get("allowed_conclusions") or []),
        },
    )


async def record_gap_resolved(
    session: AsyncSession,
    *,
    gap: Any,
    from_status: str,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    return await append_audit_event(
        session,
        workspace_id=gap.workspace_id,
        project_id=gap.project_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type or ("user" if actor_user_id else "system"),
        action=ACTION_GAP_RESOLVED,
        resource_type=RESOURCE_GAP,
        resource_id=str(gap.id),
        request_id=request_id,
        details={
            "gap_id": str(gap.id),
            "task_id": str(gap.task_id),
            "market": gap.market,
            "data_domain": gap.data_domain,
            "reason_code": gap.reason_code,
            "from_status": from_status,
            "to_status": gap.status,
        },
    )


async def record_template_change_if_needed(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    request_id: str | None = None,
    digest: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str | None = None,
) -> AuditEvent | None:
    """模板或阈值摘要变化时追加一条事件；相同摘要不重复写。"""
    current = digest or template_registry_digest()
    previous_event = await session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == workspace_id,
            AuditEvent.action == ACTION_TEMPLATE_CHANGED,
        )
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    previous_digest = None
    if previous_event is not None:
        previous_digest = dict(previous_event.details or {}).get("template_digest")
    if previous_digest == current:
        return None
    return await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type or ("user" if actor_user_id else "system"),
        action=ACTION_TEMPLATE_CHANGED,
        resource_type=RESOURCE_TEMPLATE,
        resource_id="template_registry",
        request_id=request_id,
        details={
            "template_digest": current,
            "previous_digest": previous_digest,
        },
    )


__all__ = [
    "ACTION_ASSESSMENT_COMPUTED",
    "ACTION_GAP_RESOLVED",
    "ACTION_TEMPLATE_CHANGED",
    "RESOURCE_ASSESSMENT",
    "RESOURCE_GAP",
    "RESOURCE_TEMPLATE",
    "record_assessment_computed",
    "record_gap_resolved",
    "record_template_change_if_needed",
]
```

Create `apps/api/tests/unit/test_quality_audit.py`：

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.services.quality_audit as quality_audit
from data_intelligence_hub.models import Base

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()


@pytest.fixture()
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def assessment() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        market="US",
        quality_status="qualified",
        details_json={
            "scorecard_sha256": "a" * 64,
            "allowed_conclusions": ["enter", "insufficient_evidence"],
        },
    )


def gap() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        market="US",
        data_domain="reviews",
        reason_code="sample_below_floor",
        status="mitigated",
    )


async def test_assessment_event_uses_c2_writer(session: AsyncSession) -> None:
    event = await quality_audit.record_assessment_computed(
        session, assessment=assessment()
    )
    assert event.action == "quality.assessment.computed"
    assert event.resource_type == "market_assessment"
    assert event.actor_type == "system"
    assert event.details["scorecard_sha256"] == "a" * 64
    assert "customer_text_zh" not in event.details


async def test_gap_resolution_event(session: AsyncSession) -> None:
    event = await quality_audit.record_gap_resolved(
        session, gap=gap(), from_status="open"
    )
    assert event.action == "quality.gap.resolved"
    assert event.resource_type == "data_gap"
    assert event.details["from_status"] == "open"
    assert event.details["to_status"] == "mitigated"


async def test_template_change_is_written_once_per_digest(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        quality_audit, "template_registry_digest", lambda: "a" * 64
    )
    first = await quality_audit.record_template_change_if_needed(
        session, workspace_id=WORKSPACE_ID, project_id=PROJECT_ID
    )
    assert first is not None
    assert first.details["previous_digest"] is None
    assert (
        await quality_audit.record_template_change_if_needed(
            session, workspace_id=WORKSPACE_ID, project_id=PROJECT_ID
        )
        is None
    )

    monkeypatch.setattr(
        quality_audit, "template_registry_digest", lambda: "b" * 64
    )
    changed = await quality_audit.record_template_change_if_needed(
        session, workspace_id=WORKSPACE_ID, project_id=PROJECT_ID
    )
    assert changed is not None
    assert changed.details["previous_digest"] == "a" * 64
    assert changed.details["template_digest"] == "b" * 64
```

Create `apps/api/tests/integration/test_c8_project_acl.py`。测试使用与会话鉴权相同的 fixture 风格（`create_access_token`、`Base.metadata.create_all`、`get_session` override），并设置 `workspace_rbac_enforced=True`：

```python
"""C8 资产、数据集、质量与缺口的项目 ACL。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import (
    Base,
    Dataset,
    DatasetVersion,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
OWNER_ID = uuid.uuid4()
MEMBER_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()
OTHER_WORKSPACE_ID = uuid.uuid4()
PROJECT_A = uuid.uuid4()
PROJECT_B = uuid.uuid4()
PROJECT_OTHER = uuid.uuid4()
DATASET_A = uuid.uuid4()
DATASET_B = uuid.uuid4()
DATASET_OTHER = uuid.uuid4()
VERSION_A = uuid.uuid4()
VERSION_B = uuid.uuid4()
VERSION_OTHER = uuid.uuid4()


def _user(user_id: uuid.UUID, email: str) -> User:
    return User(
        id=user_id,
        email=email,
        password_hash="hashed",
        name=email,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _dataset(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    name: str,
) -> tuple[Dataset, DatasetVersion]:
    dataset = Dataset(
        id=dataset_id,
        workspace_id=workspace_id,
        project_id=project_id,
        name=name,
        dataset_type="ecommerce_product",
        status="active",
        description=None,
        created_at=NOW,
        updated_at=NOW,
    )
    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=OWNER_ID,
        cleaning_plan_id=None,
        version_number=1,
        source_task_run_ids=[],
        selected_fields=["title"],
        cleaning_script=[],
        rows=[],
        export_preview={"schema": {}},
        row_count=0,
        average_completeness_percent=0,
        status="saved",
        created_at=NOW,
    )
    return dataset, version


async def _seed(session) -> None:
    session.add_all([_user(OWNER_ID, "owner@example.com"), _user(MEMBER_ID, "member@example.com")])
    session.add(
        Workspace(
            id=WORKSPACE_ID,
            name="ACL",
            slug="data-achieve-demo",
            owner_id=OWNER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Workspace(
            id=OTHER_WORKSPACE_ID,
            name="Other",
            slug="other",
            owner_id=OWNER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add_all(
        [
            WorkspaceMember(
                workspace_id=WORKSPACE_ID,
                user_id=OWNER_ID,
                role="owner",
                created_at=NOW,
                updated_at=NOW,
            ),
            WorkspaceMember(
                workspace_id=WORKSPACE_ID,
                user_id=MEMBER_ID,
                role="member",
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
    )
    for project_id, name in ((PROJECT_A, "A"), (PROJECT_B, "B")):
        session.add(
            Project(
                id=project_id,
                workspace_id=WORKSPACE_ID,
                name=name,
                description=None,
                domain="ecommerce",
                status="active",
                owner_id=OWNER_ID,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    session.add(
        Project(
            id=PROJECT_OTHER,
            workspace_id=OTHER_WORKSPACE_ID,
            name="Other",
            description=None,
            domain="ecommerce",
            status="active",
            owner_id=OWNER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        ProjectMember(
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_A,
            user_id=MEMBER_ID,
            created_by_user_id=OWNER_ID,
            created_at=NOW,
        )
    )
    for dataset, version in (
        _dataset(DATASET_A, VERSION_A, workspace_id=WORKSPACE_ID, project_id=PROJECT_A, name="A"),
        _dataset(DATASET_B, VERSION_B, workspace_id=WORKSPACE_ID, project_id=PROJECT_B, name="B"),
        _dataset(
            DATASET_OTHER,
            VERSION_OTHER,
            workspace_id=OTHER_WORKSPACE_ID,
            project_id=PROJECT_OTHER,
            name="Other",
        ),
    ):
        session.add(dataset)
        session.add(version)
    await session.commit()


async def _client_for(tmp_path_factory, user_id: uuid.UUID) -> AsyncIterator[AsyncClient]:
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

    settings = get_settings()
    previous = settings.workspace_rbac_enforced
    settings.workspace_rbac_enforced = True
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", create_access_token(user_id))
            yield client
    finally:
        app.dependency_overrides.clear()
        settings.workspace_rbac_enforced = previous
        await engine.dispose()


@pytest_asyncio.fixture()
async def member_api(tmp_path_factory) -> AsyncIterator[AsyncClient]:
    async for client in _client_for(tmp_path_factory, MEMBER_ID):
        yield client


@pytest_asyncio.fixture()
async def owner_api(tmp_path_factory) -> AsyncIterator[AsyncClient]:
    async for client in _client_for(tmp_path_factory, OWNER_ID):
        yield client


async def test_member_reads_granted_project(member_api: AsyncClient) -> None:
    response = await member_api.get(
        f"/api/automation/product-datasets/{DATASET_A}"
        f"/versions/{VERSION_A}/preview"
    )
    assert response.status_code == 200, response.text


async def test_member_cross_project_preview_is_403(member_api: AsyncClient) -> None:
    response = await member_api.get(
        f"/api/automation/product-datasets/{DATASET_B}"
        f"/versions/{VERSION_B}/preview"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "project_access_forbidden"


async def test_member_cross_project_list_is_403(member_api: AsyncClient) -> None:
    response = await member_api.get(
        "/api/automation/product-datasets", params={"project_id": str(PROJECT_B)}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "project_access_forbidden"


async def test_member_list_is_filtered_to_granted_projects(
    member_api: AsyncClient,
) -> None:
    response = await member_api.get("/api/automation/product-datasets")
    assert response.status_code == 200
    assert [item["dataset"]["name"] for item in response.json()["items"]] == ["A"]


async def test_owner_sees_all_projects(owner_api: AsyncClient) -> None:
    response = await owner_api.get("/api/automation/product-datasets")
    assert response.status_code == 200
    assert {item["dataset"]["name"] for item in response.json()["items"]} == {"A", "B"}


async def test_cross_workspace_dataset_is_404(member_api: AsyncClient) -> None:
    response = await member_api.get(
        f"/api/automation/product-datasets/{DATASET_OTHER}"
        f"/versions/{VERSION_OTHER}/preview"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "dataset_not_found"


async def test_member_cannot_archive_cross_project_dataset(
    member_api: AsyncClient,
) -> None:
    response = await member_api.delete(
        f"/api/automation/product-datasets/{DATASET_B}"
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "project_access_forbidden"
```

修改 `apps/api/src/data_intelligence_hub/repositories/datasets.py`：

```python
from collections.abc import Sequence

async def list_datasets(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    include_archived: bool = False,
    project_ids: Sequence[uuid.UUID] | None = None,
) -> list[Dataset]:
    ...
    if project_id is not None:
        statement = statement.where(Dataset.project_id == project_id)
    elif project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Dataset.project_id.in_(project_ids))

async def count_datasets(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    include_archived: bool = False,
    project_ids: Sequence[uuid.UUID] | None = None,
) -> int:
    ...
```

修改 `apps/api/src/data_intelligence_hub/services/automation_service.py`：

```python
from data_intelligence_hub.api.authz import (
    require_project_access,
    require_workspace_role,
)
from data_intelligence_hub.repositories.projects import list_projects_for_member


async def _require_dataset_access(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    dataset: Dataset,
) -> None:
    await require_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=dataset.project_id,
    )


async def list_product_datasets(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    project_id: uuid.UUID | None = None,
    ...
) -> AutomationProductDatasetListResponse:
    project_ids: list[uuid.UUID] | None = None
    if project_id is not None:
        await require_project_access(
            session,
            workspace=workspace,
            user=user,
            project_id=project_id,
        )
    else:
        role = await require_workspace_role(
            session,
            workspace=workspace,
            user=user,
            allowed=("owner", "admin", "member"),
        )
        if get_settings().workspace_rbac_enforced and role == "member":
            project_ids = [
                project.id
                for project in await list_projects_for_member(
                    session, workspace.id, user.id
                )
            ]
    datasets = await list_datasets(
        session,
        workspace.id,
        project_id=project_id,
        project_ids=project_ids,
        ...
    )
    total = await count_datasets(
        session,
        workspace.id,
        project_id=project_id,
        project_ids=project_ids,
        ...
    )
```

`list_product_dataset_versions`、`get_product_dataset_version_preview`、`archive_product_dataset` 增加 `user: User` 参数，并在取得 dataset 后调用 `_require_dataset_access`。`archive_product_dataset` 必须先 `get_dataset`、再 ACL、最后 `archive_dataset`，不得先归档再鉴权。三个保存函数必须先由 `task_run_ids` 解析唯一 `project_id` 并调用 ACL，再调用 preview；不得先 preview 后鉴权。ACL 通过后再创建或复用 dataset：

```python
    await require_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=project_id,
    )
```

`get_market_assessment`、`list_data_gaps`、`list_dataset_versions_for_task_market` 只允许在 `require_project_access` 之后调用。preview 路由先按 dataset.project_id 授权，再做质量与缺口读取；C9 报告构建先由其路由授权，再调用 `load_report_quality_sections`。仓储同时带 `workspace_id`/`project_id` 过滤，防止调用方漏授权时跨项目读取。

`get_product_dataset_version_preview` 的质量读取使用 Step 6 已加入的 `workspace_id`/`project_id` 过滤；不要在 ACL 之前读取记分卡或缺口。

修改 `apps/api/src/data_intelligence_hub/api/routes/automation.py`：

```python
@router.get("/product-datasets", response_model=AutomationProductDatasetListResponse)
async def list_product_datasets_route(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: uuid.UUID | None = None,
    ...
) -> AutomationProductDatasetListResponse:
    return await list_product_datasets(
        session,
        context.workspace,
        context.user,
        project_id=project_id,
        ...
    )
```

`list_product_dataset_versions_route`、`preview_product_dataset_version_route`、`archive_product_dataset_route` 把 `context.user` 传入对应 service。保存路由已传 `context.user`，只改 service 内部。列表路由原先在函数内导入 `get_demo_workspace`；改用 `context.workspace` 后删除该导入，避免 ruff F401。

- [ ] **Step 8: 写 API 集成测试**

在 `apps/api/tests/integration/test_dataset_export_preview.py` 末尾追加：

```python
async def test_preview_returns_null_quality_for_legacy_version(api: AsyncClient) -> None:
    response = await api.get(
        f"/api/automation/product-datasets/{DATASET_ID}"
        f"/versions/{VERSION_ID}/preview?limit=1"
    )
    assert response.status_code == 200
    body = response.json()
    version = body["version"]
    assert version["task_id"] is None
    assert version["market"] is None
    assert version["content_sha256"] is None
    assert version["schema_hash"] is None
    assert version["quality_status"] is None
    assert body["quality_assessment"] is None
    assert body["data_gaps"] == []
```

在 `apps/api/tests/unit/test_dataset_quality_repository.py` 顶部追加导入：

```python
from types import SimpleNamespace

import data_intelligence_hub.services.automation_service as automation_service
```

在该文件末尾追加：

```python
async def test_version_preview_maps_assessment_and_missing_gap(
    session: AsyncSession,
    monkeypatch,
) -> None:
    workspace = await session.get(Workspace, WORKSPACE_ID)
    user = await session.get(User, USER_ID)
    assert workspace is not None
    assert user is not None

    assessment = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=TASK_ID,
        market="US",
        market_role="primary",
        quality_status="not_qualified",
        conclusion_standard=None,
        conclusion_quick=None,
        evidence_grade="L4_authorized_live",
        core_domain_coverage={
            "products": "pass",
            "reviews": "missing",
            "creator_content": "pass",
        },
        sample_counts={"products": 100, "reviews": None, "creator_content": 200},
        thresholds={"package_type": "standard"},
        gap_ids=[],
        details_json={"scorecard_sha256": "a" * 64},
        computed_at=NOW,
    )
    gap = SimpleNamespace(
        id=uuid.uuid4(),
        task_id=TASK_ID,
        market="US",
        data_domain="reviews",
        reason_code="data_domain_missing",
        actual_value=None,
        threshold_value=2000,
        impact="US 评论缺失。",
        customer_text_zh="评论缺失。实际值：缺失；门槛：2000。",
        customer_text_en="Reviews missing. Actual: missing; threshold: 2000.",
        remediation="继续采集。",
        severity="blocking",
        status="open",
        created_at=NOW,
        resolved_at=None,
    )

    async def fake_assessment(*args, **kwargs):
        return assessment

    async def fake_gaps(*args, **kwargs):
        return [gap]

    monkeypatch.setattr(automation_service, "get_market_assessment", fake_assessment)
    monkeypatch.setattr(automation_service, "list_data_gaps", fake_gaps)

    response = await automation_service.get_product_dataset_version_preview(
        session,
        workspace,
        user,
        DATASET_ID,
        VERSION_ID,
        limit=1,
    )
    assert response.quality_assessment is not None
    assert response.quality_assessment.quality_status == "not_qualified"
    assert response.quality_assessment.sample_counts["reviews"] is None
    assert response.data_gaps[0].actual_value is None
    assert response.data_gaps[0].threshold_value == 2000
```

- [ ] **Step 9: 运行测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest \
  tests/unit/test_dataset_quality_repository.py \
  tests/unit/test_quality_audit.py \
  tests/integration/test_dataset_export_preview.py \
  tests/integration/test_c8_project_acl.py \
  -q
uv run ruff check \
  src/data_intelligence_hub/repositories/dataset_quality.py \
  src/data_intelligence_hub/services/quality_audit.py \
  src/data_intelligence_hub/services/automation_service.py \
  src/data_intelligence_hub/api/routes/automation.py \
  src/data_intelligence_hub/repositories/datasets.py \
  tests/unit/test_dataset_quality_repository.py \
  tests/unit/test_quality_audit.py \
  tests/integration/test_c8_project_acl.py
```

Expected: 全部通过；ruff 无输出。

- [ ] **Step 10: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/dataset_quality.py \
  apps/api/src/data_intelligence_hub/services/quality_audit.py \
  apps/api/src/data_intelligence_hub/schemas/automation.py \
  apps/api/src/data_intelligence_hub/services/automation_service.py \
  apps/api/src/data_intelligence_hub/api/routes/automation.py \
  apps/api/src/data_intelligence_hub/repositories/datasets.py \
  apps/api/tests/unit/test_dataset_quality_repository.py \
  apps/api/tests/unit/test_quality_audit.py \
  apps/api/tests/integration/test_dataset_export_preview.py \
  apps/api/tests/integration/test_c8_project_acl.py
git commit -m "feat(dataset): persist market quality with project ACL and audit"
```

---

### Task 9: 完成 run 的质量消费、ensure 与 backfill

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/market_quality.py`
- Create: `apps/api/src/data_intelligence_hub/services/quality_report_sections.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/dataset_quality.py`（追加 `sync_dataset_versions_for_task_market`）
- Create: `scripts/market_quality_backfill.py`
- Test: `apps/api/tests/unit/test_market_quality_runner.py`
- Test: `apps/api/tests/integration/test_market_quality_backfill.py`
- Test: `apps/api/tests/integration/test_report_quality_sections.py`

**Interfaces:**
- Consumes: `compute_market_assessment`、`MarketQualityInput`、`QualityRecord`、`DomainEvidence`、`KeyClaimBinding`、`upsert_market_assessment`、`MarketQualityConflictError`、`sync_dataset_quality_status`、`list_dataset_versions_for_task_market`、`set_data_gap_status`、`validate_conclusion`；C6 的 `runs`、`run_steps`、`run_step_attempts` 与 `run.completed` 审计事件；C4 的 `workflow_versions.workbench_task_id`、`workbench_tasks.package_type`/`primary_market`/`comparison_markets`；C7 的 `claims`、`claim_evidence` 与来源簇；C2 的 `require_project_access` 与 `append_audit_event`。
- Produces: `evaluate_and_persist_market_quality(session, run_id, task_id, market_code, package_type, *, actor_user_id=None, actor_type=None, request_id=None) -> MarketAssessment`。
- Produces: `ensure_market_quality(session, *, run_id, task_id=None, market_code=None, package_type=None) -> MarketAssessment`。
- Produces: `resolve_data_gap(session, *, workspace, user, project_id, gap_id, status, request_id=None) -> DataGap`；先调用 `require_project_access`，再写 `quality.gap.resolved`。
- Produces: `consume_completed_runs(session, *, limit=100, run_ids=None) -> QualityConsumptionResult`。
- Produces: `consume_run_completed_events(session, *, limit=100, after=None) -> QualityConsumptionResult`。
- Produces: `handle_run_completed_event(session, event) -> MarketAssessment | None`。
- Produces: `QualityConsumptionResult(scanned, evaluated, skipped, conflicts, failed, last_occurred_at)`、`QualityAttribution`、`MarketQualityNotReadyError(ValueError)`。
- Produces: `quality_report_sections.load_report_quality_sections(session, *, workspace_id, project_id, task_id, markets, workspace=None, user=None) -> dict[str, list[dict] | dict]`；同时传 `workspace`/`user` 时先做项目 ACL；返回 C1 `report_contract` 的 `markets`/`datasets`/`scorecard` 三段。
- Produces: CLI `uv run python ../../scripts/market_quality_backfill.py --mode runs|events --limit 100 [--dry-run] [--run-id UUID ...]`（在 `apps/api` 下执行）。
- 不新增表、不新增契约对象、不修改 C6、不修改控制台。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_market_quality_runner.py`：

```python
"""完成 run 的质量消费、ensure 与 backfill 控制流。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.services.market_quality as market_quality
from data_intelligence_hub.models import (
    Base,
    DatasetVersion,
    Project,
    Run,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.dataset import Dataset
from data_intelligence_hub.services.dataset_quality import (
    DomainEvidence,
    MarketQualityInput,
    QualityRecord,
)
from data_intelligence_hub.services.market_quality import (
    MarketQualityNotReadyError,
    QualityAttribution,
    consume_completed_runs,
    ensure_market_quality,
    evaluate_and_persist_market_quality,
    resolve_data_gap,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
from data_intelligence_hub.tool_catalog.evidence_thresholds import PackageTier

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()
DATASET_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()


@pytest.fixture()
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(
            User(
                id=USER_ID,
                email="quality-runner@example.com",
                password_hash="x",
                name="Quality Runner",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            Workspace(
                id=WORKSPACE_ID,
                name="Quality",
                slug="quality-runner",
                owner_id=USER_ID,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            WorkspaceMember(
                workspace_id=WORKSPACE_ID,
                user_id=USER_ID,
                role="owner",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            Project(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name="Quality",
                description="quality",
                domain="ecommerce",
                status="active",
                owner_id=USER_ID,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add(
            Dataset(
                id=DATASET_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                name="Quality dataset",
                dataset_type="ecommerce_product",
                status="active",
                description=None,
            )
        )
        db.add(
            DatasetVersion(
                id=VERSION_ID,
                dataset_id=DATASET_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                created_by_user_id=USER_ID,
                cleaning_plan_id=None,
                version_number=1,
                source_task_run_ids=[],
                selected_fields=["title"],
                cleaning_script=[],
                rows=[],
                export_preview={},
                row_count=1,
                average_completeness_percent=100,
                status="saved",
                created_at=NOW,
                task_id=TASK_ID,
                market="US",
                content_sha256="a" * 64,
                schema_hash="b" * 64,
            )
        )
        db.add(
            Run(
                id=RUN_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                status="completed",
                outcome="success",
                market_code="US",
                records_count=3,
                finished_at=NOW,
            )
        )
        await db.commit()
        yield db
    await engine.dispose()


def _payload() -> MarketQualityInput:
    def record(domain: str, index: int) -> QualityRecord:
        return QualityRecord(
            record_id=f"{domain}-{index}",
            market="US",
            data_domain=domain,
            source_url=f"https://example.com/{domain}/{index}",
            source_cluster_key=f"provider-{index % 2}",
            content_sha256=f"{domain}-{index}",
            completeness_percent=100,
        )

    return MarketQualityInput(
        task_id=TASK_ID,
        market="US",
        market_role="primary",
        package_type=PackageTier.QUICK,
        evidence_grade=EvidenceGrade.L3_LIVE_SINGLE,
        domains=(
            DomainEvidence("products", (record("products", 0), record("products", 1))),
            DomainEvidence("reviews", (record("reviews", 0), record("reviews", 1))),
            DomainEvidence("creator_content", (record("creator_content", 0),)),
        ),
    )


def _monkeypatch_attribution(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolve(session: AsyncSession, run: Run) -> QualityAttribution:
        return QualityAttribution(
            task_id=TASK_ID,
            market_code="US",
            market_role="primary",
            package_type=PackageTier.QUICK,
        )

    async def load(
        session: AsyncSession,
        run: Run,
        attribution: QualityAttribution,
    ) -> MarketQualityInput:
        return _payload()

    monkeypatch.setattr(market_quality, "_resolve_quality_attribution", resolve)
    monkeypatch.setattr(market_quality, "_load_market_quality_input", load)


async def test_ensure_creates_missing_quality_and_syncs_versions(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monkeypatch_attribution(monkeypatch)

    assessment = await ensure_market_quality(session, run_id=RUN_ID)

    version = await session.get(DatasetVersion, VERSION_ID)
    assert assessment.task_id == TASK_ID
    assert assessment.market == "US"
    assert version is not None
    assert version.quality_status == assessment.quality_status


async def test_evaluate_rejects_mismatched_task(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monkeypatch_attribution(monkeypatch)

    with pytest.raises(MarketQualityNotReadyError, match="task_mismatch"):
        await evaluate_and_persist_market_quality(
            session,
            RUN_ID,
            uuid.uuid4(),
            "US",
            PackageTier.QUICK,
        )


async def test_ensure_is_idempotent(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monkeypatch_attribution(monkeypatch)

    first = await ensure_market_quality(session, run_id=RUN_ID)
    second = await ensure_market_quality(session, run_id=RUN_ID)

    assert first.id == second.id


async def test_ensure_rejects_non_completed_run(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monkeypatch_attribution(monkeypatch)
    run = await session.get(Run, RUN_ID)
    assert run is not None
    run.status = "running"
    await session.flush()

    with pytest.raises(MarketQualityNotReadyError, match="run_not_completed"):
        await ensure_market_quality(session, run_id=RUN_ID)


async def test_consume_completed_runs_is_idempotent(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monkeypatch_attribution(monkeypatch)

    first = await consume_completed_runs(session, limit=10)
    second = await consume_completed_runs(session, limit=10)

    assert first.scanned == 1
    assert first.evaluated == 1
    assert first.failed == 0
    assert second.scanned == 1
    assert second.evaluated == 0
    assert second.skipped == 1


async def test_resolve_data_gap_checks_acl_and_writes_audit(
    session: AsyncSession,
) -> None:
    workspace = await session.get(Workspace, WORKSPACE_ID)
    user = await session.get(User, USER_ID)
    assert workspace is not None
    assert user is not None
    gap = DataGap(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        market="US",
        data_domain="reviews",
        reason_code="sample_below_floor",
        actual_value=1,
        threshold_value=300,
        impact="US 评论样本不足。",
        customer_text_zh="评论样本不足。",
        customer_text_en="Reviews are below the floor.",
        remediation=None,
        severity="blocking",
        status="open",
        created_at=NOW,
        resolved_at=None,
    )
    session.add(gap)
    await session.flush()

    resolved = await resolve_data_gap(
        session,
        workspace=workspace,
        user=user,
        project_id=PROJECT_ID,
        gap_id=gap.id,
        status="accepted",
    )
    assert resolved.status == "accepted"
    assert resolved.resolved_at is not None

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "quality.gap.resolved",
            AuditEvent.resource_id == str(gap.id),
        )
    )
    assert event is not None
    assert event.details["to_status"] == "accepted"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_market_quality_runner.py -q
```

Expected: FAIL，`ModuleNotFoundError: data_intelligence_hub.services.market_quality`。

- [ ] **Step 3: 写 `market_quality.py`**

Create `apps/api/src/data_intelligence_hub/services/market_quality.py`：

```python
"""完成 run 的质量消费与报告前 ensure。

本模块只消费 C6 的 run 事实与 `run.completed` 审计事件。
它不修改 C6，不新建队列表，不复制质量阈值。

幂等规则：

- 事件重复消费由 ``uq_market_assessments_task_market`` 与 scorecard hash 吸收。
- 同一 task + market 的记分卡内容不同时，``upsert_market_assessment`` 抛
  ``MarketQualityConflictError``；消费者计数后跳过，不覆盖。
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.data_gap import DataGap
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.repositories.dataset_quality import (
    DataGapNotFoundError,
    MarketQualityConflictError,
    get_market_assessment,
    set_data_gap_status,
    sync_dataset_versions_for_task_market,
    upsert_market_assessment,
)
from data_intelligence_hub.schemas.report_contract import canonical_json_bytes
from data_intelligence_hub.services.dataset_quality import (
    DomainEvidence,
    KeyClaimBinding,
    MarketQualityInput,
    QualityRecord,
    compute_market_assessment,
)
from data_intelligence_hub.services.quality_audit import (
    record_assessment_computed,
    record_gap_resolved,
    record_template_change_if_needed,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade
from data_intelligence_hub.tool_catalog.evidence_thresholds import PackageTier

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
CORE_DOMAINS = ("products", "reviews", "creator_content")

_STEP_DOMAINS = {
    "products": "products",
    "product": "products",
    "discover_products": "products",
    "reviews": "reviews",
    "review": "reviews",
    "creator_content": "creator_content",
    "creator": "creator_content",
    "creators": "creator_content",
    "ads": "ads",
    "advertising": "ads",
}
_RECORD_DOMAINS = {
    "product": "products",
    "review": "reviews",
    "creator": "creator_content",
    "ad": "ads",
}


class MarketQualityNotReadyError(ValueError):
    """run 尚未完成或缺少质量归因。"""


@dataclass(frozen=True, slots=True)
class QualityAttribution:
    task_id: uuid.UUID
    market_code: str
    market_role: str
    package_type: PackageTier


@dataclass(slots=True)
class QualityConsumptionResult:
    scanned: int = 0
    evaluated: int = 0
    skipped: int = 0
    conflicts: int = 0
    failed: int = 0
    last_occurred_at: datetime | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


async def _resolve_quality_attribution(
    session: AsyncSession,
    run: Run,
) -> QualityAttribution:
    if run.workflow_version_id is None:
        raise MarketQualityNotReadyError("workflow_version_missing")
    version = await session.get(WorkflowVersion, run.workflow_version_id)
    if version is None or version.workbench_task_id is None:
        raise MarketQualityNotReadyError("workbench_task_missing")
    task = await session.get(WorkbenchTask, version.workbench_task_id)
    if task is None:
        raise MarketQualityNotReadyError("workbench_task_missing")
    if task.workspace_id != run.workspace_id or task.project_id != run.project_id:
        raise MarketQualityNotReadyError("project_mismatch")
    market_code = run.market_code
    markets = {task.primary_market, *task.comparison_markets}
    if market_code is None or market_code not in markets:
        raise MarketQualityNotReadyError("market_not_in_task")
    return QualityAttribution(
        task_id=task.id,
        market_code=market_code,
        market_role="primary" if market_code == task.primary_market else "compare",
        package_type=PackageTier(task.package_type),
    )


def _domain_for_step(step: RunStep) -> str | None:
    for value in (step.stage, step.tool_id, step.endpoint_type):
        if value is None:
            continue
        domain = _STEP_DOMAINS.get(str(value).lower())
        if domain is not None:
            return domain
    return None


def _domain_for_record(raw: RawRecord) -> str | None:
    text = f"{raw.record_type}".lower()
    for token, domain in _RECORD_DOMAINS.items():
        if token in text:
            return domain
    return None


def _quality_record(raw: RawRecord, market_code: str, domain: str) -> QualityRecord:
    content = raw.content if isinstance(raw.content, dict) else {}
    content_hash = (raw.content_hash or "").lower()
    if not _HEX64.fullmatch(content_hash):
        content_hash = hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()
    completeness = content.get("completeness_percent", 100)
    try:
        completeness_percent = max(0, min(100, int(completeness)))
    except (TypeError, ValueError):
        completeness_percent = 100
    return QualityRecord(
        record_id=str(raw.id),
        market=market_code,
        data_domain=domain,
        source_url=raw.source_url,
        source_cluster_key=f"content:{content_hash}",
        content_sha256=content_hash,
        completeness_percent=completeness_percent,
    )


async def _load_key_claims(
    session: AsyncSession,
    run: Run,
    attribution: QualityAttribution,
) -> tuple[KeyClaimBinding, ...]:
    claims = list(
        await session.scalars(
            select(Claim).where(
                Claim.run_id == run.id,
                Claim.scope_market == attribution.market_code,
            )
        )
    )
    bindings: list[KeyClaimBinding] = []
    for claim in claims:
        evidence_ids = tuple(
            await session.scalars(
                select(ClaimEvidence.evidence_id).where(
                    ClaimEvidence.claim_id == claim.id
                )
            )
        )
        domain = getattr(claim, "data_domain", None) or "products"
        bindings.append(
            KeyClaimBinding(
                claim_id=str(claim.id),
                data_domain=domain,
                evidence_ids=tuple(str(item) for item in evidence_ids),
                independent_source_count=claim.independent_source_count,
            )
        )
    return tuple(bindings)


async def _load_market_quality_input(
    session: AsyncSession,
    run: Run,
    attribution: QualityAttribution,
) -> MarketQualityInput:
    steps = list(
        await session.scalars(
            select(RunStep)
            .where(RunStep.run_id == run.id)
            .order_by(RunStep.step_index)
        )
    )
    task_run_ids = [step.task_run_id for step in steps if step.task_run_id is not None]
    raw_records: list[RawRecord] = []
    if task_run_ids:
        raw_records = list(
            await session.scalars(
                select(RawRecord).where(RawRecord.task_run_id.in_(task_run_ids))
            )
        )

    records_by_domain: dict[str, list[QualityRecord]] = defaultdict(list)
    blocked_by_domain: dict[str, str] = {}
    for step in steps:
        domain = _domain_for_step(step)
        if domain is None:
            continue
        if step.status in {"config_gated", "failed"}:
            blocked_by_domain.setdefault(domain, step.status)
    for raw in raw_records:
        domain = _domain_for_record(raw)
        if domain is None:
            continue
        records_by_domain[domain].append(
            _quality_record(raw, attribution.market_code, domain)
        )

    domains: list[DomainEvidence] = []
    for domain in (*CORE_DOMAINS, "ads"):
        records = tuple(records_by_domain.get(domain, ()))
        blocked_reason = blocked_by_domain.get(domain) if not records else None
        if domain == "ads" and not records and blocked_reason is None:
            continue
        domains.append(
            DomainEvidence(
                data_domain=domain,
                records=records,
                blocked_reason=blocked_reason,
            )
        )

    return MarketQualityInput(
        task_id=attribution.task_id,
        market=attribution.market_code,
        market_role=attribution.market_role,
        package_type=attribution.package_type,
        evidence_grade=EvidenceGrade(run.evidence_grade or EvidenceGrade.L0_UNVERIFIED.value),
        domains=tuple(domains),
        key_claims=await _load_key_claims(session, run, attribution),
    )


async def evaluate_and_persist_market_quality(
    session: AsyncSession,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    market_code: str,
    package_type: str | PackageTier,
    *,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str | None = None,
    request_id: str | None = None,
) -> MarketAssessment:
    """评估一个已完成 run 的逐市场质量并持久化。

    这是 C8 对外的唯一评估入口。C9 只调用 ``ensure_market_quality``。
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise MarketQualityNotReadyError("run_not_found")
    if run.status != "completed":
        raise MarketQualityNotReadyError("run_not_completed")

    attribution = await _resolve_quality_attribution(session, run)
    if attribution.task_id != task_id:
        raise MarketQualityNotReadyError("task_mismatch")
    if attribution.market_code != market_code:
        raise MarketQualityNotReadyError("market_mismatch")
    if attribution.package_type != PackageTier(package_type):
        raise MarketQualityNotReadyError("package_type_mismatch")

    existing = await get_market_assessment(
        session,
        task_id=attribution.task_id,
        market=attribution.market_code,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
    )
    await record_template_change_if_needed(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
    )

    payload = await _load_market_quality_input(session, run, attribution)
    result = compute_market_assessment(payload, computed_at=datetime.now(UTC))
    assessment = await upsert_market_assessment(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        draft=result.assessment,
        gaps=result.gaps,
    )
    await sync_dataset_versions_for_task_market(
        session,
        task_id=attribution.task_id,
        market=attribution.market_code,
    )
    if existing is None:
        await record_assessment_computed(
            session,
            assessment=assessment,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            request_id=request_id,
        )
    return assessment


async def ensure_market_quality(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    market_code: str | None = None,
    package_type: str | PackageTier | None = None,
) -> MarketAssessment:
    """C9 报告构建前的质量门禁。

    已有记分卡时直接返回；缺失时同步评估一次。
    """
    run = await session.get(Run, run_id)
    if run is None:
        raise MarketQualityNotReadyError("run_not_found")
    if run.status != "completed":
        raise MarketQualityNotReadyError("run_not_completed")

    attribution = await _resolve_quality_attribution(session, run)
    if task_id is not None and attribution.task_id != task_id:
        raise MarketQualityNotReadyError("task_mismatch")
    if market_code is not None and attribution.market_code != market_code:
        raise MarketQualityNotReadyError("market_mismatch")
    if package_type is not None and attribution.package_type != PackageTier(package_type):
        raise MarketQualityNotReadyError("package_type_mismatch")

    existing = await get_market_assessment(
        session,
        task_id=attribution.task_id,
        market=attribution.market_code,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
    )
    if existing is not None:
        await record_template_change_if_needed(
            session,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
        )
        await sync_dataset_versions_for_task_market(
            session,
            task_id=attribution.task_id,
            market=attribution.market_code,
        )
        return existing
    return await evaluate_and_persist_market_quality(
        session,
        run_id,
        attribution.task_id,
        attribution.market_code,
        attribution.package_type,
    )


async def resolve_data_gap(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    project_id: uuid.UUID,
    gap_id: uuid.UUID,
    status: str,
    request_id: str | None = None,
) -> DataGap:
    """解除一个缺口。先做项目 ACL，再写审计。"""
    await require_project_access(
        session,
        workspace=workspace,
        user=user,
        project_id=project_id,
    )
    existing = await session.get(DataGap, gap_id)
    if (
        existing is None
        or existing.workspace_id != workspace.id
        or existing.project_id != project_id
    ):
        raise DataGapNotFoundError(str(gap_id))
    if existing.status == status:
        return existing
    from_status = existing.status
    resolved = await set_data_gap_status(
        session,
        workspace_id=workspace.id,
        project_id=project_id,
        gap_id=gap_id,
        status=status,
        resolved_at=datetime.now(UTC),
    )
    await record_gap_resolved(
        session,
        gap=resolved,
        from_status=from_status,
        actor_user_id=user.id,
        request_id=request_id,
    )
    return resolved


async def consume_completed_runs(
    session: AsyncSession,
    *,
    limit: int = 100,
    run_ids: list[uuid.UUID] | None = None,
) -> QualityConsumptionResult:
    """扫描已完成 run，为缺失的质量记分卡补评估。

    不依赖事件是否已消费；可重复运行。
    """
    statement = select(Run).where(
        Run.status == "completed",
        Run.finished_at.is_not(None),
        Run.market_code.is_not(None),
    )
    if run_ids:
        statement = statement.where(Run.id.in_(run_ids))
    runs = list(
        await session.scalars(statement.order_by(Run.finished_at).limit(limit))
    )
    result = QualityConsumptionResult(scanned=len(runs))
    for run in runs:
        try:
            async with session.begin_nested():
                attribution = await _resolve_quality_attribution(session, run)
                existing = await get_market_assessment(
                    session,
                    task_id=attribution.task_id,
                    market=attribution.market_code,
                    workspace_id=run.workspace_id,
                    project_id=run.project_id,
                )
                if existing is not None:
                    result.skipped += 1
                    continue
                await evaluate_and_persist_market_quality(
                    session,
                    run.id,
                    attribution.task_id,
                    attribution.market_code,
                    attribution.package_type,
                )
                result.evaluated += 1
        except MarketQualityConflictError:
            result.conflicts += 1
        except MarketQualityNotReadyError:
            result.skipped += 1
        except Exception:
            result.failed += 1
    return result


async def handle_run_completed_event(
    session: AsyncSession,
    event: AuditEvent,
) -> MarketAssessment | None:
    """处理一条 C6 的 `run.completed` 审计事件。"""
    if event.action != "run.completed":
        return None
    raw_run_id = (event.details or {}).get("run_id")
    if raw_run_id is None:
        return None
    try:
        run_id = uuid.UUID(str(raw_run_id))
    except ValueError:
        return None
    try:
        return await ensure_market_quality(session, run_id=run_id)
    except MarketQualityNotReadyError:
        return None


async def consume_run_completed_events(
    session: AsyncSession,
    *,
    limit: int = 100,
    after: datetime | None = None,
) -> QualityConsumptionResult:
    """增量读取 C2 `audit_events` 的 `run.completed` 行。

    ``after`` 是进程内游标，不建新表。重启后从最早事件重扫；
    幂等由 ``market_assessments`` 唯一键与 scorecard hash 保证。
    """
    statement = (
        select(AuditEvent)
        .where(AuditEvent.action == "run.completed")
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
        .limit(limit)
    )
    if after is not None:
        statement = statement.where(AuditEvent.occurred_at > after)
    events = list(await session.scalars(statement))
    result = QualityConsumptionResult(
        scanned=len(events),
        last_occurred_at=events[-1].occurred_at if events else after,
    )
    for event in events:
        try:
            async with session.begin_nested():
                assessment = await handle_run_completed_event(session, event)
            if assessment is None:
                result.skipped += 1
            else:
                result.evaluated += 1
        except MarketQualityConflictError:
            result.conflicts += 1
        except Exception:
            result.failed += 1
    return result


__all__ = [
    "MarketQualityNotReadyError",
    "QualityAttribution",
    "QualityConsumptionResult",
    "consume_completed_runs",
    "consume_run_completed_events",
    "ensure_market_quality",
    "evaluate_and_persist_market_quality",
    "handle_run_completed_event",
    "resolve_data_gap",
]
```

在 `repositories/dataset_quality.py` 追加：

```python
async def sync_dataset_versions_for_task_market(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    market: str,
) -> int:
    """把同一 task + market 的记分卡投影到全部数据集版本。"""
    assessment = await get_market_assessment(
        session,
        task_id=task_id,
        market=market,
    )
    versions = list(
        await session.scalars(
            select(DatasetVersion).where(
                DatasetVersion.task_id == task_id,
                DatasetVersion.market == market,
            )
        )
    )
    for version in versions:
        version.quality_status = (
            assessment.quality_status if assessment is not None else None
        )
    await session.flush()
    return len(versions)
```

并在 `__all__` 加入 `sync_dataset_versions_for_task_market`。

- [ ] **Step 3b: 写 C9 报告段投影与交接测试**

Create `apps/api/src/data_intelligence_hub/services/quality_report_sections.py`：

```python
"""C8 对 C9 的报告段投影。

输出形状只来自 C1 ``report_contract`` 的 ``markets``、``datasets``、
``scorecard`` 三个段。C8 不渲染报告，不发布，不写交付 manifest。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.dataset_quality import (
    get_market_assessment,
    list_data_gaps,
    list_dataset_versions_for_task_market,
)
from data_intelligence_hub.tool_catalog.evidence_grade import (
    GRADE_ORDER,
    EvidenceGrade,
)


def _grade_rank(value: str) -> int:
    return GRADE_ORDER[EvidenceGrade(value)]


def _gap_section(gap: Any) -> dict[str, Any]:
    """C1 ``$defs.gap`` 允许的键；不写 ``status``。"""
    section: dict[str, Any] = {
        "gap_id": str(gap.id),
        "market": gap.market,
        "data_domain": gap.data_domain,
        "reason_code": gap.reason_code,
        "actual_value": gap.actual_value,
        "threshold_value": gap.threshold_value,
        "impact": gap.impact,
        "customer_text_zh": gap.customer_text_zh,
        "severity": gap.severity,
    }
    if gap.customer_text_en is not None:
        section["customer_text_en"] = gap.customer_text_en
    if gap.remediation is not None:
        section["remediation"] = gap.remediation
    return section


def _market_section(
    assessment: Any,
    gaps: Sequence[Any],
) -> dict[str, Any]:
    domains: list[dict[str, Any]] = []
    for domain, status in assessment.core_domain_coverage.items():
        item: dict[str, Any] = {"data_domain": domain, "status": status}
        count = assessment.sample_counts.get(domain)
        if isinstance(count, int):
            item["record_count"] = count
        threshold = (assessment.thresholds.get(domain) or {}).get("floor_n")
        if isinstance(threshold, int):
            item["threshold"] = threshold
        domains.append(item)
    section: dict[str, Any] = {
        "market": assessment.market,
        "market_role": assessment.market_role,
        "quality_status": assessment.quality_status,
        "evidence_grade": assessment.evidence_grade,
        "domains": domains,
        "sample_counts": dict(assessment.sample_counts),
        "thresholds": dict(assessment.thresholds),
        "gaps": [_gap_section(gap) for gap in gaps],
    }
    if assessment.conclusion_standard is not None:
        section["conclusion_standard"] = assessment.conclusion_standard
    if assessment.conclusion_quick is not None:
        section["conclusion_quick"] = assessment.conclusion_quick
    return section


def _dataset_section(version: Any) -> dict[str, Any]:
    section: dict[str, Any] = {
        "dataset_version_id": str(version.id),
        "market": version.market,
        "row_count": version.row_count,
        "content_sha256": version.content_sha256,
        "schema_hash": version.schema_hash,
    }
    if version.quality_status is not None:
        section["quality_status"] = version.quality_status
    return section


async def load_report_quality_sections(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    markets: Iterable[str],
    workspace: Workspace | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """按市场装载 C9 可直接写入 ReportContract 的三段。

    同时传 ``workspace`` 与 ``user`` 时先做项目 ACL；不传时调用方
    必须已完成授权，仓储仍按 workspace/project 过滤。
    缺任一市场的记分卡时抛 ``ValueError``，由 C9 转为
    ``report_quality_not_ready``。C8 不伪造空质量。
    """
    if workspace is not None and user is not None:
        await require_project_access(
            session,
            workspace=workspace,
            user=user,
            project_id=project_id,
        )
    market_codes = list(dict.fromkeys(markets))
    if not market_codes:
        raise ValueError("report_quality_sections_require_market")

    market_sections: list[dict[str, Any]] = []
    for market in market_codes:
        assessment = await get_market_assessment(
            session,
            task_id=task_id,
            market=market,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if assessment is None:
            raise ValueError(f"market_quality_missing:{market}")
        gaps = await list_data_gaps(
            session,
            task_id=task_id,
            market=market,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        market_sections.append(_market_section(assessment, gaps))

    dataset_sections: list[dict[str, Any]] = []
    for market in market_codes:
        versions = await list_dataset_versions_for_task_market(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
            market=market,
        )
        dataset_sections.extend(
            _dataset_section(version)
            for version in versions
            if version.content_sha256 is not None
            and version.schema_hash is not None
        )

    minimum_grade = min(
        (section["evidence_grade"] for section in market_sections),
        key=_grade_rank,
    )
    return {
        "markets": market_sections,
        "datasets": dataset_sections,
        "scorecard": {
            "markets": market_sections,
            "minimum_evidence_grade": minimum_grade,
        },
    }


__all__ = ["load_report_quality_sections"]
```

Create `apps/api/tests/integration/test_report_quality_sections.py`：

```python
"""C8 到 C9 的报告段交接。

一份任务单覆盖 qualified、qualified_with_gap、not_qualified 三个市场。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    Dataset,
    DatasetVersion,
    Project,
    User,
    Workspace,
)
from data_intelligence_hub.repositories.dataset_quality import (
    upsert_market_assessment,
)
from data_intelligence_hub.services.dataset_quality import (
    ConclusionInputs,
    DataGapDraft,
    MarketAssessmentDraft,
    SkuCandidate,
    validate_conclusion,
)
from data_intelligence_hub.services.quality_report_sections import (
    load_report_quality_sections,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import PackageTier

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
TASK_ID = uuid.uuid4()
DATASET_ID = uuid.uuid4()


@pytest.fixture()
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _draft(
    market: str,
    status: str,
    *,
    gap: bool = False,
) -> tuple[MarketAssessmentDraft, tuple[DataGapDraft, ...]]:
    gap_drafts: tuple[DataGapDraft, ...] = ()
    if gap:
        gap_drafts = (
            DataGapDraft(
                gap_id=uuid.uuid5(uuid.NAMESPACE_URL, f"gap:{TASK_ID}:{market}"),
                market=market,
                data_domain="reviews",
                reason_code="data_domain_missing",
                actual_value=None,
                threshold_value=2000,
                impact=f"{market} reviews missing.",
                customer_text_zh=f"{market} 评论缺失。",
                customer_text_en=f"{market} reviews missing.",
                remediation="继续采集。",
                severity="blocking",
                status="open",
            ),
        )
    return (
        MarketAssessmentDraft(
            assessment_id=uuid.uuid5(
                uuid.NAMESPACE_URL, f"assessment:{TASK_ID}:{market}"
            ),
            task_id=TASK_ID,
            market=market,
            market_role="primary" if market == "US" else "compare",
            quality_status=status,
            conclusion_standard=None,
            conclusion_quick=None,
            evidence_grade="L4_authorized_live",
            core_domain_coverage={
                "products": "pass",
                "reviews": "missing" if gap else "pass",
                "creator_content": "pass",
            },
            sample_counts={
                "products": 120,
                "reviews": None if gap else 2100,
                "creator_content": 220,
            },
            thresholds={
                "package_type": "standard",
                "products": {"floor_n": 100},
                "reviews": {"floor_n": 2000},
                "creator_content": {"floor_n": 200},
            },
            gap_ids=tuple(gap_draft.gap_id for gap_draft in gap_drafts),
            details={
                "scorecard_sha256": hashlib.sha256(market.encode()).hexdigest(),
            },
            computed_at=NOW,
        ),
        gap_drafts,
    )


async def test_sections_cover_three_quality_states(session: AsyncSession) -> None:
    session.add(
        User(
            id=USER_ID,
            email="sections@example.com",
            password_hash="x",
            name="Sections",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Workspace(
            id=WORKSPACE_ID,
            name="Sections",
            slug="sections",
            owner_id=USER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Project(
            id=PROJECT_ID,
            workspace_id=WORKSPACE_ID,
            name="Sections",
            description=None,
            domain="ecommerce",
            status="active",
            owner_id=USER_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        Dataset(
            id=DATASET_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            name="Sections dataset",
            dataset_type="ecommerce_product",
            status="active",
            description=None,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    for index, market, status, gap in (
        (1, "US", "qualified", False),
        (2, "GB", "qualified_with_gap", True),
        (3, "DE", "not_qualified", True),
    ):
        draft, gaps = _draft(market, status, gap=gap)
        await upsert_market_assessment(
            session,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            draft=draft,
            gaps=gaps,
        )
        session.add(
            DatasetVersion(
                id=uuid.uuid4(),
                dataset_id=DATASET_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                created_by_user_id=USER_ID,
                cleaning_plan_id=None,
                version_number=index,
                source_task_run_ids=[],
                selected_fields=["title"],
                cleaning_script=[],
                rows=[],
                export_preview={},
                row_count=120,
                average_completeness_percent=100,
                status="saved",
                created_at=NOW,
                task_id=TASK_ID,
                market=market,
                content_sha256=hashlib.sha256(f"content:{market}".encode()).hexdigest(),
                schema_hash=hashlib.sha256(f"schema:{market}".encode()).hexdigest(),
                quality_status=status,
            )
        )
    await session.flush()

    sections = await load_report_quality_sections(
        session,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        markets=("US", "GB", "DE"),
    )
    assert set(sections) == {"markets", "datasets", "scorecard"}
    assert [item["quality_status"] for item in sections["markets"]] == [
        "qualified",
        "qualified_with_gap",
        "not_qualified",
    ]
    assert [item["market"] for item in sections["datasets"]] == ["US", "GB", "DE"]
    assert sections["scorecard"]["minimum_evidence_grade"] == "L4_authorized_live"
    assert sections["scorecard"]["markets"] == sections["markets"]

    for market in sections["markets"]:
        assert {
            "market",
            "market_role",
            "quality_status",
            "evidence_grade",
            "domains",
            "sample_counts",
            "thresholds",
            "gaps",
        } <= set(market)
        for gap in market["gaps"]:
            assert "status" not in gap
            assert {
                "gap_id",
                "market",
                "data_domain",
                "reason_code",
                "impact",
                "customer_text_zh",
                "severity",
            } <= set(gap)

    for dataset in sections["datasets"]:
        assert {
            "dataset_version_id",
            "market",
            "row_count",
            "content_sha256",
            "schema_hash",
        } <= set(dataset)

    qualified = sections["markets"][0]
    assert (
        validate_conclusion(
            quality_status=qualified["quality_status"],
            package_type=PackageTier.STANDARD,
            inputs=ConclusionInputs(
                requested_standard="enter",
                sku_candidates=tuple(
                    SkuCandidate(candidate_id=f"sku-{rank}", rank=rank)
                    for rank in range(1, 4)
                ),
            ),
        ).standard
        == "enter"
    )
    conditional = sections["markets"][1]
    assert (
        validate_conclusion(
            quality_status=conditional["quality_status"],
            package_type=PackageTier.STANDARD,
            inputs=ConclusionInputs(
                requested_standard="conditional_enter",
                test_budget_usd=Decimal("500.00"),
                observation_window_days=14,
                success_threshold="首月转化率达到试点门槛",
                stop_loss="连续两周低于止损线时停止",
            ),
        ).standard
        == "conditional_enter"
    )
    not_qualified = sections["markets"][2]
    assert (
        validate_conclusion(
            quality_status=not_qualified["quality_status"],
            package_type=PackageTier.STANDARD,
            inputs=ConclusionInputs(requested_standard="insufficient_evidence"),
        ).standard
        == "insufficient_evidence"
    )
```

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/integration/test_report_quality_sections.py -q
uv run ruff check src/data_intelligence_hub/services/quality_report_sections.py tests/integration/test_report_quality_sections.py
```

Expected: 全部通过；ruff 无输出。

- [ ] **Step 4: 写 backfill CLI**

Create `scripts/market_quality_backfill.py`：

```python
"""完成 run 的质量 backfill。

用法（在 `apps/api` 下执行，脚本在仓库根 `scripts/`）：

    uv run python ../../scripts/market_quality_backfill.py --mode runs --limit 100
    uv run python ../../scripts/market_quality_backfill.py --mode events --limit 100
    uv run python ../../scripts/market_quality_backfill.py --mode runs --run-id <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import asyncio

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services.market_quality import (
    consume_completed_runs,
    consume_run_completed_events,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market quality backfill")
    parser.add_argument("--mode", choices=("runs", "events"), default="runs")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    async with async_session_factory() as session:
        if args.mode == "events":
            result = await consume_run_completed_events(session, limit=args.limit)
        else:
            result = await consume_completed_runs(
                session,
                limit=args.limit,
                run_ids=args.run_id or None,
            )
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()
        print(result.as_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 5: 运行单元测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/unit/test_market_quality_runner.py -q
```

Expected: `6 passed`。

- [ ] **Step 6: 写 backfill 集成测试**

Create `apps/api/tests/integration/test_market_quality_backfill.py`：复用本任务 fixture，断言：

```python
async def test_backfill_runs_evaluates_completed_run_once(session, monkeypatch) -> None:
    _monkeypatch_attribution(monkeypatch)
    first = await consume_completed_runs(session, limit=10)
    second = await consume_completed_runs(session, limit=10)
    assert first.evaluated == 1
    assert second.evaluated == 0
    assert second.skipped == 1
```

并断言 CLI 的 `--dry-run` 不提交：调用 `build_parser().parse_args(["--mode", "runs", "--dry-run"])`，在事务内执行后 `rollback`，再查 `market_assessments` 为 0。

- [ ] **Step 7: 运行集成测试与静态检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest \
  tests/unit/test_market_quality_runner.py \
  tests/integration/test_market_quality_backfill.py \
  tests/integration/test_report_quality_sections.py \
  -q
uv run ruff check \
  src/data_intelligence_hub/services/market_quality.py \
  src/data_intelligence_hub/services/quality_report_sections.py \
  src/data_intelligence_hub/repositories/dataset_quality.py \
  ../../scripts/market_quality_backfill.py \
  tests/integration/test_report_quality_sections.py
uv run mypy \
  src/data_intelligence_hub/services/market_quality.py \
  src/data_intelligence_hub/services/quality_report_sections.py \
  src/data_intelligence_hub/repositories/dataset_quality.py
```

Expected: 全部通过；ruff 无输出；mypy `Success: no issues found`。

- [ ] **Step 8: 事件监听与 PG0 激活说明**

C8 不新建队列或游标表，也不注册 scheduler、不启动后台循环。PG0 发布批次在迁移、权限与只读验收通过后，把 `scripts/market_quality_backfill.py --mode events` 注册到现有 scheduler 的分钟级任务；C14 只读，不注册任务、不写生产数据。worker 可参考以下循环，但启动与守护属于 PG0 发布批次：

```python
cursor = None
while True:
    async with async_session_factory() as session:
        result = await consume_run_completed_events(session, limit=100, after=cursor)
        await session.commit()
        if result.last_occurred_at is not None:
            cursor = result.last_occurred_at
    await asyncio.sleep(30)
```

进程重启后 `cursor=None` 会重扫历史事件；重复消费由 `uq_market_assessments_task_market` 与 scorecard hash 吸收。C8 不修改 C6 的 worker 或事件写入，也不把调度注册写进 C14 验收。

- [ ] **Step 9: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/market_quality.py \
  apps/api/src/data_intelligence_hub/services/quality_report_sections.py \
  apps/api/src/data_intelligence_hub/repositories/dataset_quality.py \
  scripts/market_quality_backfill.py \
  apps/api/tests/unit/test_market_quality_runner.py \
  apps/api/tests/integration/test_market_quality_backfill.py \
  apps/api/tests/integration/test_report_quality_sections.py
git commit -m "feat(dataset): consume completed runs for market quality"
```

---

### Task 10: 保存路径写入内容哈希

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/automation_service.py`
- Modify: `apps/api/tests/integration/test_dataset_export_preview.py`

**Interfaces:**
- Consumes: `compute_dataset_content_digest`。
- Produces: `save_product_dataset_version`、`save_github_tool_dataset_version`、`save_public_content_dataset_version` 写入 `content_sha256` 与 `schema_hash`。
- Produces: 新版本保存响应包含两个 64 位十六进制哈希。

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/integration/test_dataset_export_preview.py` 末尾追加：

```python
async def test_save_product_dataset_writes_content_and_schema_hashes(
    api: AsyncClient,
) -> None:
    response = await api.post(
        "/api/automation/product-dataset-save",
        json={
            "authorized": True,
            "task_run_ids": [str(RUN_ID)],
            "fields": SELECTED_FIELDS,
            "max_rows": 10,
            "name": "C8 hash dataset",
        },
    )
    assert response.status_code == 200, response.text
    version = response.json()["version"]
    assert isinstance(version["content_sha256"], str)
    assert len(version["content_sha256"]) == 64
    assert isinstance(version["schema_hash"], str)
    assert len(version["schema_hash"]) == 64
    assert version["quality_status"] is None


async def test_saving_same_content_twice_keeps_content_hash(api: AsyncClient) -> None:
    payload = {
        "authorized": True,
        "task_run_ids": [str(RUN_ID)],
        "fields": SELECTED_FIELDS,
        "max_rows": 10,
        "name": "C8 idempotent hash dataset",
    }
    first = await api.post("/api/automation/product-dataset-save", json=payload)
    second = await api.post("/api/automation/product-dataset-save", json=payload)
    assert first.status_code == second.status_code == 200
    assert (
        first.json()["version"]["content_sha256"]
        == second.json()["version"]["content_sha256"]
    )
    assert (
        first.json()["version"]["schema_hash"]
        == second.json()["version"]["schema_hash"]
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/integration/test_dataset_export_preview.py -q
```

Expected: 新测试 FAIL，`version["content_sha256"]` 为 `None`。

- [ ] **Step 3: 给测试夹具补一条原始商品记录**

`save_product_dataset_version` 从 `RawRecord` 读取商品。现有 `_seed` 只有 `TaskRun`，没有原始记录。修改 `apps/api/tests/integration/test_dataset_export_preview.py`：

1. 在 `from data_intelligence_hub.models import (` 的导入列表中加入 `RawRecord`。
2. 在 `TaskRun` 种子之后加入：

```python
    session.add(
        RawRecord(
            id=uuid.uuid4(),
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            source_id=SOURCE_ID,
            task_run_id=RUN_ID,
            record_type="ecommerce_product_page",
            source_url="https://www.amazon.com/dp/B00000001",
            content={
                "extracted_fields": {
                    "title": "Product 0",
                    "price": 19.99,
                    "canonical_url": "https://www.amazon.com/dp/B00000001",
                }
            },
            content_hash="a" * 64,
            collected_at=NOW,
            created_at=NOW,
        )
    )
```

- [ ] **Step 4: 修改产品数据集保存函数**

在 `save_product_dataset_version` 中，找到 `raw_records = await _dataset_product_raw_records(...)` 之前，插入：

```python
    rows_payload: list[dict[str, Any]] = [
        {
            "row_id": row.row_id,
            "task_run_id": str(row.task_run_id),
            "raw_record_id": str(row.raw_record_id),
            "source_url": row.source_url,
            "values": row.values,
            "missing_fields": row.missing_fields,
            "completeness_percent": row.completeness_percent,
        }
        for row in rows_for_version
    ]
    digest = compute_dataset_content_digest(
        dataset_type="ecommerce_product",
        selected_fields=selected_fields,
        rows=rows_payload,
        cleaning_script=cleaning_script,
    )
```

把 `DatasetVersion(...)` 中的内联 `rows=[...]` 替换为：

```python
        rows=rows_payload,
        content_sha256=digest.content_sha256,
        schema_hash=digest.schema_hash,
```

- [ ] **Step 5: 修改 GitHub 工具数据集保存函数**

在 `save_github_tool_dataset_version` 中，找到 `latest_version = ...` 之前，插入：

```python
    rows_payload: list[dict[str, Any]] = [
        {
            "schema_version": GITHUB_TOOL_DATASET_SCHEMA_VERSION,
            "row_id": row.row_id,
            "task_run_id": str(row.task_run_id),
            "raw_record_id": str(row.raw_record_id),
            "source_url": row.source_url,
            "values": row.values,
            "missing_fields": row.missing_fields,
            "field_sources": _github_tool_field_sources(row.values.keys()),
            "missing_field_sources": _github_tool_field_sources(row.missing_fields),
            "completeness_percent": row.completeness_percent,
        }
        for row in preview.rows
    ]
    digest = compute_dataset_content_digest(
        dataset_type="github_tool_radar",
        selected_fields=preview.summary.selected_fields,
        rows=rows_payload,
        cleaning_script=preview.cleaning_script_draft,
    )
```

把 `DatasetVersion(...)` 中的内联 `rows=[...]` 替换为：

```python
        rows=rows_payload,
        content_sha256=digest.content_sha256,
        schema_hash=digest.schema_hash,
```

- [ ] **Step 6: 修改公开内容数据集保存函数**

在 `save_public_content_dataset_version` 中，找到 `latest_version = ...` 之前，插入：

```python
    rows_payload: list[dict[str, Any]] = [
        {
            "schema_version": PUBLIC_CONTENT_DATASET_SCHEMA_VERSION,
            "row_id": row.row_id,
            "task_run_id": str(row.task_run_id),
            "raw_record_id": str(row.raw_record_id),
            "source_url": row.source_url,
            "values": row.values,
            "missing_fields": row.missing_fields,
            "field_sources": _public_content_field_sources(row.values.keys()),
            "missing_field_sources": _public_content_field_sources(row.missing_fields),
            "completeness_percent": row.completeness_percent,
        }
        for row in preview.rows
    ]
    digest = compute_dataset_content_digest(
        dataset_type="public_content_update",
        selected_fields=preview.summary.selected_fields,
        rows=rows_payload,
        cleaning_script=preview.cleaning_script_draft,
    )
```

把 `DatasetVersion(...)` 中的内联 `rows=[...]` 替换为：

```python
        rows=rows_payload,
        content_sha256=digest.content_sha256,
        schema_hash=digest.schema_hash,
```

- [ ] **Step 7: 追加导入**

在 `automation_service.py` 顶部导入区追加：

```python
from data_intelligence_hub.services.dataset_content_hash import (
    compute_dataset_content_digest,
)
```

- [ ] **Step 8: 运行测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/integration/test_dataset_export_preview.py -q
```

Expected: 全部通过。新增测试验证哈希为 64 位十六进制，重复保存内容哈希相同。

- [ ] **Step 9: 运行 ruff 与 mypy**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run ruff check src/data_intelligence_hub/services/automation_service.py tests/integration/test_dataset_export_preview.py
uv run mypy src/data_intelligence_hub/services/automation_service.py
```

Expected: ruff 无输出；mypy `Success: no issues found`。

- [ ] **Step 10: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/automation_service.py \
  apps/api/tests/integration/test_dataset_export_preview.py
git commit -m "feat(dataset): hash dataset content on save"
```

---

### Task 11: C9 报告段、C14 浏览器与 PG0 调度交接

**Files:** 无。C8 不修改 `apps/scraper-console/**`，不创建 Playwright 用例。

**Interfaces:**
- Consumes: Task 8 的 `/assets` 响应字段与项目 ACL、Task 9 的 `ensure_market_quality`/`validate_conclusion`/`load_report_quality_sections`/`consume_completed_runs`/`consume_run_completed_events`、Task 10 的保存路径哈希。
- Produces: C9 可直接装载的 `markets`/`datasets`/`scorecard` 报告段、C14 可直接执行的浏览器交接清单、PG0 可直接执行的调度与生产 backfill 清单。
- 依赖方向：C8 依赖 C2 的 ACL/审计与 C6 的 `run.completed`；C9 依赖 C8；C14 只读；PG0 执行生产写入与调度注册。

- [ ] **Step 1: 固定后端响应字段与 ACL**

`GET /api/automation/product-datasets`、`GET /api/automation/product-datasets/{dataset_id}/versions`、`GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/preview`、`DELETE /api/automation/product-datasets/{dataset_id}` 都必须走 C2 `require_project_access`。同工作区未授权 member 返回 403 `project_access_forbidden`；跨工作区返回 404 `project_not_found`；未带 `project_id` 的列表只返回 member 可见项目。C14 的浏览器交接必须覆盖这三条边界。

`GET /api/automation/product-datasets` 的 `items[].latest_version` 必须包含：

```text
task_id: string | null
market: string | null
schema_hash: string | null
content_sha256: string | null
license_class: string | null
quality_status: "qualified" | "qualified_with_gap" | "not_qualified" | null
```

`GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/preview` 必须包含：

```text
quality_assessment: {
  id, task_id, market, market_role, quality_status,
  conclusion_standard, conclusion_quick, evidence_grade,
  core_domain_coverage, sample_counts, thresholds, gap_ids,
  details_json, computed_at
} | null
data_gaps: [{
  id, task_id, market, data_domain, reason_code, actual_value,
  threshold_value, impact, customer_text_zh, customer_text_en,
  remediation, severity, status, created_at, resolved_at
}]
```

`sample_counts` 的缺失值必须是 JSON `null`，不得写 `0`。`data_gaps[].actual_value` 的缺失值也必须是 `null`。

- [ ] **Step 2: 写 C14 交接清单**

C14 负责创建 `apps/scraper-console/e2e/assets-quality.spec.ts` 并修改控制台。交接断言使用固定 test id：`asset-quality`、`asset-quality-tab`、`asset-quality-panel`、`asset-quality-gap`、`asset-quality-sample`。交接断言：

1. `/assets` 列表出现“质量”列。`quality_status` 为 `null` 时显示“未评分”，不得显示“未达标”。
2. `qualified` 显示“达标”，`qualified_with_gap` 显示“有缺口”，`not_qualified` 显示“未达标”。
3. 打开数据集预览，出现“质量”页签。
4. 质量页签显示逐市场状态、`sample_counts`、阈值和缺口表。
5. 缺失评论数显示“缺失”，不是 `0`；缺口 `actual_value` 显示“缺失”，不是 `0`。
6. 缺口表显示原因码 `data_domain_missing`、严重度、中文客户说明与 remediation。
7. 采集溯源区显示 `content_sha256` 与 `schema_hash`。
8. 控制台不得重新计算质量状态或独立来源数；只显示后端字段。
9. 同工作区 member 访问未授权项目返回 403，跨工作区返回 404；member 的 `/assets` 列表只显示授权项目。

- [ ] **Step 3: 验证质量链交接**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run python ../../scripts/market_quality_backfill.py --mode runs --limit 10 --dry-run
uv run pytest tests/unit/test_market_quality_runner.py tests/integration/test_market_quality_backfill.py -q
```

Expected: backfill 输出 `scanned/evaluated/skipped/conflicts/failed` 计数；dry-run 不提交；重复运行 `evaluated=0`。测试通过。

- [ ] **Step 4: 运行后端响应测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/integration/test_dataset_export_preview.py -q
```

Expected: 全部通过。该测试断言缺失值序列化为 `null`，`quality_assessment` 与 `data_gaps` 字段存在。

- [ ] **Step 5: 交接确认（不提交控制台文件）**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
git status --porcelain apps/scraper-console
```

Expected: 无输出。C14 在独立切片实现控制台与 Playwright。

- [ ] **Step 6: 写 C9 报告段交接**

C9 读取单市场行时使用 C8 的精确函数：

```text
get_market_assessment(session, *, task_id, market, workspace_id, project_id)
list_data_gaps(session, *, task_id, market, workspace_id, project_id, status=None)
list_dataset_versions_for_task_market(session, *, workspace_id, project_id, task_id, market)
```

整份报告合同使用 `load_report_quality_sections`，一次返回三段。C9 在 `build_contract` 前调用：

```python
from data_intelligence_hub.services.market_quality import (
    ensure_market_quality,
    validate_conclusion,
)
from data_intelligence_hub.services.quality_report_sections import (
    load_report_quality_sections,
)

await ensure_market_quality(
    session,
    run_id=run_id,
    task_id=task_id,
)
sections = await load_report_quality_sections(
    session,
    workspace_id=workspace.id,
    project_id=project_id,
    task_id=task_id,
    markets=contract["identity"]["markets"],
    workspace=workspace,
    user=created_by,
)
contract["markets"] = sections["markets"]
contract["datasets"] = sections["datasets"]
contract["scorecard"] = sections["scorecard"]
```

`markets[]` 的每个元素严格包含：

```text
market, market_role, quality_status, evidence_grade, domains,
sample_counts, thresholds, gaps
conclusion_standard?  # 仅在非 null 时存在
conclusion_quick?     # 仅在非 null 时存在
domains[]: {data_domain, status, record_count?, threshold?}
gaps[]: {gap_id, market, data_domain, reason_code, actual_value,
         threshold_value, impact, customer_text_zh, customer_text_en?,
         remediation?, severity}  # 不含 status
```

`datasets[]` 的每个元素严格包含：

```text
dataset_version_id, market, row_count, content_sha256, schema_hash,
quality_status?  # 仅在非 null 时存在
```

`scorecard` 严格包含：

```text
markets: [market_assessment]
minimum_evidence_grade: "L0_unverified" | "L1_contract" | "L2_fixture_local" | "L3_live_single" | "L4_authorized_live"
```

质量状态到结论的交接断言：

| 市场质量 | C8 校验输入 | C9/C10 可发布结论 |
|---|---|---|
| `qualified` | Standard，3–5 个非暂定 SKU 候选 | `enter` |
| `qualified_with_gap` | Standard，测试预算、观察窗口、成功阈值、止损线齐全 | `conditional_enter` |
| `not_qualified` | Standard，无 SKU 候选 | `insufficient_evidence` |

C8 只返回 `validate_conclusion(...).standard`；`None` 时 C9/C10 不得发布。C8 不写 `report_contract.json`、不渲染报告、不生成 manifest。

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest tests/integration/test_report_quality_sections.py -q
uv run pytest tests/unit/test_dataset_quality.py -q -k "conclusion or enter"
```

Expected: 全部通过；三个质量状态各有一条断言。

**发布交接。** C8 不直接部署任何环境，不执行生产发布、A/B 切换或回滚。A、B 两套生产的发布、切换与回滚由总索引 §8.4 的 PG0 发布批次执行；PG0 同时负责 scheduler 注册、`market_quality_backfill.py --mode events` 的分钟级任务、生产存量 backfill 与开关设置；C14 只做只读验收；C8 只交付迁移 064、测试证据与上述交接清单。PG0 发布批次先备份，A 先 canary，B 在目标授权、备份校验与迁移门禁通过后发布。

---

### Task 12: 全量验证与 GitNexus 收口

**Files:** 无新增或修改。

**Interfaces:**
- Consumes: Task 1-11 的全部产物。
- Produces: 可复核的测试、类型检查、迁移 head 与 GitNexus 结论。

- [ ] **Step 1: 运行后端目标测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run pytest \
  tests/unit/test_c8_contract_gate.py \
  tests/unit/test_dataset_canonical_profile.py \
  tests/unit/test_c8_source_cluster_gate.py \
  tests/unit/test_dataset_content_hash.py \
  tests/unit/test_workbench_templates.py \
  tests/unit/test_dataset_quality.py \
  tests/unit/test_dataset_quality_repository.py \
  tests/unit/test_quality_audit.py \
  tests/unit/test_market_quality_runner.py \
  tests/integration/test_market_quality_backfill.py \
  tests/integration/test_c8_project_acl.py \
  tests/integration/test_report_quality_sections.py \
  tests/integration/test_dataset_export_preview.py \
  -q
```

Expected: 全部通过，0 failed。

- [ ] **Step 2: 运行 ruff 与 mypy**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run ruff check \
  src/data_intelligence_hub/services/dataset_content_hash.py \
  src/data_intelligence_hub/services/workbench_templates.py \
  src/data_intelligence_hub/services/dataset_quality.py \
  src/data_intelligence_hub/services/quality_audit.py \
  src/data_intelligence_hub/services/quality_report_sections.py \
  src/data_intelligence_hub/repositories/dataset_quality.py \
  src/data_intelligence_hub/repositories/datasets.py \
  src/data_intelligence_hub/services/market_quality.py \
  ../../scripts/market_quality_backfill.py \
  src/data_intelligence_hub/models/dataset.py \
  src/data_intelligence_hub/models/data_gap.py \
  src/data_intelligence_hub/models/market_assessment.py \
  src/data_intelligence_hub/services/automation_service.py \
  src/data_intelligence_hub/api/routes/automation.py \
  src/data_intelligence_hub/schemas/automation.py \
  alembic/versions/202610220064_dataset_quality.py \
  tests/unit/test_c8_contract_gate.py \
  tests/unit/test_dataset_canonical_profile.py \
  tests/unit/test_c8_source_cluster_gate.py \
  tests/unit/test_dataset_content_hash.py \
  tests/unit/test_workbench_templates.py \
  tests/unit/test_dataset_quality.py \
  tests/unit/test_dataset_quality_repository.py \
  tests/unit/test_quality_audit.py \
  tests/unit/test_market_quality_runner.py \
  tests/integration/test_market_quality_backfill.py \
  tests/integration/test_c8_project_acl.py \
  tests/integration/test_report_quality_sections.py \
  tests/integration/test_dataset_export_preview.py
uv run mypy src/data_intelligence_hub/services/dataset_content_hash.py \
  src/data_intelligence_hub/services/workbench_templates.py \
  src/data_intelligence_hub/services/dataset_quality.py \
  src/data_intelligence_hub/services/quality_audit.py \
  src/data_intelligence_hub/services/quality_report_sections.py \
  src/data_intelligence_hub/repositories/dataset_quality.py \
  src/data_intelligence_hub/services/market_quality.py \
  src/data_intelligence_hub/models/dataset.py \
  src/data_intelligence_hub/models/data_gap.py \
  src/data_intelligence_hub/models/market_assessment.py
```

Expected: ruff 无输出；mypy `Success: no issues found`。

- [ ] **Step 3: 确认 C14 交接边界**

C8 不运行控制台测试，也不修改 `apps/scraper-console/**`。C14 在独立切片执行 `pnpm --dir apps/scraper-console test`、`tsc --noEmit` 与 `playwright test e2e/assets-quality.spec.ts`，并按 Task 11 的交接清单验收。scheduler 注册、后台循环启动、生产 backfill 与开关设置由 PG0 发布批次执行；C14 只读，不注册任务、不写生产数据。

- [ ] **Step 4: 运行迁移检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
uv run alembic heads
```

Expected: `202610220064 (head)`，只有一个 head。

Run the guarded PostgreSQL migration test:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/dih_c8_dataset_quality_test \
ALLOW_DESTRUCTIVE_MIGRATION_TEST=true \
uv run pytest tests/postgres_c8_dataset_quality -q
```

Expected: `2 passed`。

- [ ] **Step 5: 运行 GitNexus impact**

Run each command from the repository root:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs impact "save_product_dataset_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "save_github_tool_dataset_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "save_public_content_dataset_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_product_dataset_version_preview" --direction upstream --repo .
node .gitnexus/run.cjs impact "_dataset_version_response" --direction upstream --repo .
node .gitnexus/run.cjs impact "DatasetVersion" --direction upstream --repo .
node .gitnexus/run.cjs impact "list_product_datasets" --direction upstream --repo .
node .gitnexus/run.cjs impact "list_product_dataset_versions" --direction upstream --repo .
node .gitnexus/run.cjs impact "archive_product_dataset" --direction upstream --repo .
node .gitnexus/run.cjs impact "upsert_market_assessment" --direction upstream --repo .
node .gitnexus/run.cjs impact "evaluate_and_persist_market_quality" --direction upstream --repo .
node .gitnexus/run.cjs impact "ensure_market_quality" --direction upstream --repo .
```

Expected: `risk` 为 `LOW` 或 `MEDIUM`。出现 `HIGH` 或 `CRITICAL` 时停止并报告调用者、受影响流程和模块。出现 `UNKNOWN` 时运行：

```bash
git grep -n "save_product_dataset_version\|save_github_tool_dataset_version\|save_public_content_dataset_version\|get_product_dataset_version_preview\|list_product_datasets\|list_product_dataset_versions\|archive_product_dataset\|upsert_market_assessment\|evaluate_and_persist_market_quality\|ensure_market_quality\|require_project_access\|append_audit_event" -- apps/api/src apps/api/tests
```

把搜索结论写进提交说明。

- [ ] **Step 6: 运行 GitNexus detect-changes**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs detect-changes --scope compare --base-ref feat/gov-c7 --repo .
```

Expected: 输出包含全部改动符号与受影响流程。不得出现 `partial: true` 或 `truncated: true`。出现时重新运行 `node .gitnexus/run.cjs analyze --index-only` 后再跑。

- [ ] **Step 7: 核对需求覆盖**

逐项确认：

- [ ] C1 registry 只读；C8 未修改契约文档、registry，也未追加“C8 实现决定”；Task 1 缺项时停止并返回 C1。
- [ ] `dataset_versions.content_sha256` 使用 C1 的 `dih-canonical-json-v1`；C8 没有第二套 canonicalizer。
- [ ] `schema_hash` 覆盖 dataset_type、字段集与清洗脚本。
- [ ] 逐市场质量记分卡写入 `market_assessments`。
- [ ] C8 依赖 C6：`consume_completed_runs` 只消费 `runs.status='completed'`；`consume_run_completed_events` 只读 `audit_events.action='run.completed'`。C8 不改 C6、不给 C6 增加 C8 import。
- [ ] `ensure_market_quality` 在缺失时同步评估一次；已有记分卡直接返回；C9 构建前可调用。
- [ ] `market_quality_backfill.py --mode runs|events` 可重复运行；重复消费 `evaluated=0`，不覆盖已有记分卡。
- [ ] 结构化缺口写入 `data_gaps`。
- [ ] 首期只有 `tiktok_shop_maternal_newborn` 一个任务包模板。
- [ ] Quick/Standard 阈值只在 `evidence_thresholds.py` 定义。
- [ ] 任务包模板只在代码注册表，不建 DB 表。
- [ ] 迁移只有 `202610220064`。
- [ ] `missing` 与 `blocked` 的样本数、实际值都是 JSON null。
- [ ] 独立来源按来源簇与内容哈希折叠。
- [ ] 资产、数据集、市场记分卡与缺口读写都调用 C2 `require_project_access`；同工作区 member 跨项目 403，跨工作区 404，member 列表只返回授权项目；`test_c8_project_acl.py` 覆盖。
- [ ] 质量计算、缺口解除、模板/阈值变化都写 C2 `audit_events`；action 精确为 `quality.assessment.computed`、`quality.gap.resolved`、`quality.template.changed`；没有第二套审计写入。
- [ ] C9 报告段由 `load_report_quality_sections` 输出，`markets`/`datasets`/`scorecard` 形状与 C1 schema 一致；`test_report_quality_sections.py` 覆盖 `qualified`、`qualified_with_gap`、`not_qualified`。
- [ ] Standard `enter` 只接受 3–5 个非暂定 SKU 候选；`conditional_enter` 必须带测试预算、观察窗口、成功阈值与止损线；`do_not_enter` 必须带 C7 至少两个独立来源簇；C8 不发布结论。
- [ ] Task 11 的 C14 交接清单覆盖质量列、质量页签、缺失值、缺口与项目 ACL。
- [ ] 没有改报告渲染、交付包、Claim 模型或报告合同。
- [ ] 未直接部署；A、B 两套生产的发布、切换、回滚、scheduler 注册与生产 backfill 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。

- [ ] **Step 8: 最终提交检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c8
git status --short
git log --oneline feat/gov-c7..HEAD
```

Expected: 工作树干净。提交历史包含 Task 1-12 的提交，提交信息以 `test(dataset):`、`feat(dataset):`、`feat(template):` 开头。没有控制台文件，也没有未提交文件。

---

## 交付说明

执行完成后返回以下内容：

- 分支名与 commit 列表。
- 后端目标测试、ruff、mypy 的命令与结果。
- `uv run alembic heads` 的输出。
- GitNexus `impact` 与 `detect-changes` 的结论。
- 项目 ACL 测试结果（跨项目 403、跨工作区 404、member 列表过滤）。
- 三个审计 action 的事件样例与 `event_hash` 链校验结果。
- `test_report_quality_sections.py` 对 `qualified`、`qualified_with_gap`、`not_qualified` 的交接结果。
- `validate_conclusion` 对 `enter`/`conditional_enter`/`do_not_enter` 的校验结果。
- Task 11 的 C9 报告段、C14 浏览器交接清单与 PG0 调度交接清单。

不写报告文件。结果直接作为文本返回。
