# Governed Task Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 C0–C14 建立受治理任务包平台的 PG0 代码闭环，并通过 O0/O1 分离外部取证与付费试点。

**Architecture:** 以冻结契约和已批准设计为唯一入口。代码计划按基线、契约、身份、运行、预算、证据、交付、隐私、MCP 和控制台分片；每片独立迁移、独立测试、独立回滚。生产发布由 PG0 发布批次执行，C14 只做只读验收。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 15/16、MCP Streamable HTTP、Next.js、React、TypeScript、Playwright、GitNexus、Markdown。

## Global Constraints

- 权威顺序：冻结契约 > 已批准设计 > 当前迁移与代码事实 > 其他计划。
- 每个切片一个独立 worktree、一个 PR、最多一个迁移、一个功能开关、一个回滚点。
- C1 独占契约与机器 registry；C14 独占控制台和 Playwright。
- 新表、列、枚举、路径和 MCP 工具必须先由 C1 登记。
- 每次改符号前运行 GitNexus impact；每次提交前运行 detect-changes。
- 生产 B 与 A 共用 `configs/deploy/scrapy/docker-compose.yml`；`scrapy-new` 不是生产 B。
- 子计划不直接部署。生产发布由本文件 §8.4 的 PG0 发布批次执行；C14 只做只读 canary、preflight 和浏览器验收。
- P1 实际付费试点只能在 PG0 全部通过后启动。

---

| 字段 | 内容 |
|---|---|
| 文档版本 | `v1.0` |
| 日期 | 2026-10-22 |
| 设计输入 | [`2026-10-21-tikhub-governed-task-platform-design.md`](../specs/2026-10-21-tikhub-governed-task-platform-design.md) |
| 计划范围 | 代码切片 `C0`–`C14`；PG0 外部取证 `O0`；PG1 商业试点 `O1` |
| 本文件职责 | 只提供入口、依赖、波次、文件所有权、迁移、开关、门禁与完成定义。不重复子计划步骤。 |
| 执行口径 | 产品阶段只写 `PG0`、`PG1`。契约实施阶段 `P0–P8` 只出现在契约文档，不用于本计划命名。 |

## 0. 状态栏

| 项目 | 状态 | 证据或入口 |
|---|---|---|
| 设计批准 | `已批准` | 设计文档 §0.1 与 §11 |
| 计划编写 | `17/17 已写` | C0–C14、O0、O1 |
| 代码实施 | `0/15 完成` | 本文件 §1 |
| 计划内部阻塞 | `无` | C8/C12 已冻结；C8 在 `202610220064` 建质量表；C12 分享撤销为 no-op；仅剩外部证据与 PG0/PG1 门禁 |
| 契约 v1.1 | `未开始` | C1 |
| PG0 外部取证 | `未开始` | O0；未取得时 PG0 门禁保持 `open` |
| PG0 评审 | `未开始` | C14 与 O0 完成后评审；没有 Conditional Pass |
| PG1 商业试点 | `未开始` | O1；PG0 门禁通过前不得启动；PG0 的书面承诺不计入实际付费 |
| 生产 A schema | 当前 `202610210053`；C0/B5 目标 `202610210057`；全量完成后 expected head `202610220068` | 发布前逐主机复核 |
| 生产 B schema | 当前批准 `202607280044` | 目标授权与备份门禁见 §8.4 |

状态取值只有 `未开始`、`进行中`、`阻塞`、`已完成`、`已回退`。`进行中` 必须带负责人和分支。

## 1. 切片清单

| ID | 切片 | 计划 | 迁移 | 主要依赖 | 波次 | 状态 |
|---|---|---|---|---|---|---|
| C0 | 基线集成：合入 B5、验证 056/057、冻结事实 | [C0](2026-10-22-governed-task-platform-c0-baseline-integration.md) | 无；head `202610210057` | 无 | W0 | 未开始 |
| C1 | 契约 v1.1、机器 registry 与 checker | [C1](2026-10-22-governed-task-platform-c1-contract-v1-1.md) | 无 | C0 | W1 | 未开始 |
| C2 | 身份、项目 ACL 与统一审计 | [C2](2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md) | `202610220058` | C0、C1 | W2 | 未开始 |
| C3 | 项目密钥与项目级凭据 | [C3](2026-10-22-governed-task-platform-c3-project-keys-credentials.md) | `202610220059` | C2 | W3 | 未开始 |
| C4 | 任务单提交、计划关联与幂等 | [C4](2026-10-22-governed-task-platform-c4-task-submission-idempotency.md) | `202610220060` | C2、C3 | W4 | 未开始 |
| C5 | 预算、账本与定价 | [C5](2026-10-22-governed-task-platform-c5-budget-ledger-pricing.md) | `202610220061` | C3、C4 | W5 | 未开始 |
| C6 | Run 执行收敛、尝试与取消 | [C6](2026-10-22-governed-task-platform-c6-run-execution-convergence.md) | `202610220062` | C4、C5 | W6 | 未开始 |
| C7 | 证据、Claim 与独立来源 | [C7](2026-10-22-governed-task-platform-c7-claims-evidence.md) | `202610220063` | C5、C6 | W7 | 未开始 |
| C8 | 数据集质量、缺口与首期模板 | [C8](2026-10-22-governed-task-platform-c8-dataset-quality-template.md) | `202610220064` | C4、C6、C7 | W8 | 未开始 |
| C9 | 不可变报告合同与产物发布 | [C9](2026-10-22-governed-task-platform-c9-report-contract-artifacts.md) | `202610220065` | C7、C8 | W9 | 未开始 |
| C10 | 交付 Manifest、bundle 与验收（公开分享延期） | [C10](2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md) | `202610220066` | C9 | W10 | 未开始 |
| C11 | 工作区伪名化、导出遮蔽与保留 | [C11](2026-10-22-governed-task-platform-c11-pseudonymization-retention.md) | `202610220067` | C3、C10 | W11 | 未开始 |
| C12 | 删除请求、墓碑、删除证明与 DSR | [C12](2026-10-22-governed-task-platform-c12-deletion-dsr.md) | `202610220068` | C3、C4、C8、C10、C11 | W12 | 未开始 |
| C13 | 客户 MCP `/mcp/customer` 八工具 | [C13](2026-10-22-governed-task-platform-c13-customer-mcp.md) | 无 | C3、C4、C5、C6、C7、C8、C9、C10 | W11 | 未开始 |
| C14 | 控制台 11 条合同路由（10 启用、1 禁用）、CI 与验收门禁 | [C14](2026-10-22-governed-task-platform-c14-console-ci-acceptance.md) | 无 | C0–C13 | W13 | 未开始 |
| O0 | PG0 外部书面证据与签核 | [O0](2026-10-22-governed-task-platform-o0-pg0-evidence.md) | 无 | C0–C14（Task 11–12、14）；Task 1–10 与 Task 13 可并行 | O-W0–O-W13 | 未开始 |
| O1 | PG1 90 天付费试点 | [O1](2026-10-22-governed-task-platform-o1-pg1-paid-pilot.md) | 无 | C14、O0 | O-W14 | 未开始 |

### 1.1 口径说明

1. C1 计划中的旧“C2–C14 工作包边界”表是早期分工草案。最终执行以本索引 §1 与 §5 的迁移表为准。
2. 部分子计划正文引用了早期 C 编号。遇到冲突时，以本索引的切片名、迁移号和依赖图为准。
3. C0 的基线标签统一写 `pg0-baseline-v1`。分支统一写 `feat/pg0-baseline-c0`。
4. `C0`–`C14` 是代码切片编号，不是产品阶段。产品阶段只写 `PG0`、`PG1`。
5. C1 registry 中属于早期 C11–C14 的对象（`refresh_schedules`、`comparability_assessments`、`reconciliation_runs`、`kill_switch_events`、`release_gate_records`、`contract_publications`）不属于最终 C11–C14 计划。执行 C1 前必须从 registry 删除或标 `deferred`。
6. `tool_prices` 是 C5 的正式价格事实源。C1 registry 登记其列、约束和索引；C5 迁移 `202610220061` 创建 `tool_prices`、`quota_accounts` 与 `tool_calls`。`price_book_v1.json` 只作为受评审的种子，不作为运行时回退源。
7. C5 的迁移 `202610220061` 同时创建 C1 已登记的 `workbench_approval_actions`。该表只承载预算超额、加购和项目密钥变更的内联批准；不建独立审批收件箱。C8 是 `market_assessments` 与 `data_gaps` 的唯一创建者和写入者。迁移 `202610220064` 创建这两张表；C5 的 `202610220061` 不创建质量表。C8 不再因迁移归属阻塞。
8. `report_shares`、公开分享端点和公开访问路径首期延期。C12 不创建分享撤销端口或分享服务；删除执行只追加 `deletion_share_revocation_deferred` no-op 审计事件，并在删除证明记录 `report_shares: 0`。C12 不建 `report_shares` 表，也不再因分享撤销阻塞。
9. `feat/p1-identity` 已是 C0 起点 `f0560ca` 的祖先；C0 不重复合并 P1。C0 只合并 `feat/b5-workbench`，并保留已批准设计 spec。
10. `feat/b4-report-contract` 已是 `feat/b5-workbench` 的祖先；B4 经 B5 传递，不单独合并。B5 已把 B4 的 `202610210052`/`202610210053` 重编号为 `202610210056`/`202610210057`。
11. 生产 B 的权威 compose 是 `configs/deploy/scrapy/docker-compose.yml`，不是 `configs/deploy/scrapy-new/docker-compose.yml`。分支、主机与迁移授权门禁见 §8.4。
12. MFA 不在 PG0 范围。C2 不实现 MFA；C12 的删除批准使用 owner/admin 会话与二次确认，不引入 `require_recent_mfa`。MFA 未实现前不得对外宣称。
13. `mcp_customer_request_leases` 不建表。C1 registry 标记 `deferred`；C13 的速率与并发计数使用已登记的 `audit_events`，不新建租约表。
14. 子计划不得直接修改本索引。状态、阻塞项和依赖变更以“总索引变更请求”提交，由本索引所有者合入；子计划只读引用本文件。
15. 每个切片的回滚点是 §8.2 表中的 worktree 起点分支或标签；迁移回滚点是 §5 的 `down_revision` 与 `alembic downgrade -1` 验证。生产回滚用发布前备份恢复。

## 2. 依赖图

```mermaid
graph TD
  C0[C0 基线集成] --> C1[C1 契约 v1.1]
  C1 --> C2[C2 身份与 ACL 审计]
  C2 --> C3[C3 项目密钥与凭据]
  C2 --> C4[C4 任务提交幂等]
  C3 --> C4
  C3 --> C5[C5 预算与定价]
  C4 --> C5
  C4 --> C6[C6 Run 执行收敛]
  C5 --> C6
  C5 --> C7[C7 证据与 Claim]
  C6 --> C7
  C4 --> C8[C8 数据质量与模板]
  C6 --> C8
  C7 --> C8
  C7 --> C9[C9 报告合同与产物]
  C8 --> C9
  C9 --> C10[C10 交付与验收]
  C3 --> C11[C11 伪名与保留]
  C10 --> C11
  C3 --> C12[C12 删除与 DSR]
  C10 --> C12
  C11 --> C12
  C3 --> C13[C13 客户 MCP]
  C4 --> C13
  C5 --> C13
  C6 --> C13
  C8 --> C13
  C9 --> C13
  C10 --> C13
  C0 --> C14[C14 控制台与 CI]
  C1 --> C14
  C2 --> C14
  C3 --> C14
  C4 --> C14
  C5 --> C14
  C6 --> C14
  C7 --> C14
  C8 --> C14
  C9 --> C14
  C10 --> C14
  C11 --> C14
  C12 --> C14
  C13 --> C14
  C14 --> O0[O0 PG0 外部取证]
  C14 --> O1[O1 PG1 试点]
  O0 --> O1
```

图中 O0 的入边只表示 Task 11–12 和 Task 14 需要 C0–C14 的运行产物；O0 Task 1–10 与 Task 13 可与 C 并行。Task 13 依赖 Task 2–12 的证据状态。

C13 还调用 C2 的 `services.audit_log.append_audit_event`。C2 是 C3 的前置切片，已由 C3 的依赖链覆盖，因此 C13 的切片依赖只列 C3、C4、C5、C6、C8、C9、C10。

## 3. 波次

| 波次 | 切片 | 并行规则 | 退出条件 |
|---|---|---|---|
| W0 | C0 | 单独执行；只操作主工作树 | B5 合入、056/057 验证、事实冻结、`pg0-baseline-v1` 标签建立 |
| W1 | C1 | 单独执行；只改契约与 registry | 契约 v1.1、registry、checker、报告/交付/MCP schema 通过 |
| W2 | C2 | 单独执行；迁移 058 | 角色、项目 ACL、审计哈希链通过 |
| W3 | C3 | 单独执行；迁移 059 | 密钥轮换、凭据作用域、`/connectors` 验收通过 |
| W4 | C4 | 单独执行；迁移 060 | 七槽位、计划关联、逐市场幂等提交通过 |
| W5 | C5 | 单独执行；迁移 061 | 价格入口、预算预留、账本与额度通过 |
| W6 | C6 | 单独执行；迁移 062 | 多 step、attempt、取消、租约与旧入口收敛通过 |
| W7 | C7 | 单独执行；迁移 063 | Claim 字段、独立来源、证据上限、审核字段通过 |
| W8 | C8 | 单独执行；迁移 `202610220064` | 数据集哈希、逐市场质量、缺口、首期模板通过；C8 在 064 创建 `market_assessments` 与 `data_gaps` |
| W9 | C9 | 单独执行；迁移 `202610220065` | 报告生命周期、审核签字、不可变与取代通过 |
| W10 | C10 | 单独执行；迁移 `202610220066` | manifest 封存、sidecar、验收快照、篡改拒下载通过；公开分享延期 |
| W11 | C11、C13 | 两个 worktree 并行；迁移 `202610220067` 由 C11 持有；C13 无迁移 | 伪名/保留通过；客户 `/mcp/customer` 八工具通过 |
| W12 | C12 | 单独执行；迁移 `202610220068` | 删除状态机、墓碑、证明、恢复重放、DSR 通过；分享撤销为 no-op |
| W13 | C14 | 从包含 C0–C13 的集成分支单独执行 | 11 条合同路由（10 启用、1 禁用）、4 条一级导航、单元/tsc/lint/build/Playwright 全绿 |
| O-W0–O-W13 | O0 | Task 1–10 可与 C 并行；Task 11–12 依赖 C0–C14 的产物；Task 13 依赖 Task 2–12；Task 14 依赖全部 Task | 14 个证据域 `accepted`、11 项 PG0 门禁 `pass`、六方 `approve`、PG0 结论 `pass` 或 `fail` |
| O-W14 | O1 | 受 PG0 `pass` 与六方 `approve` 门禁阻断 | 3–5 家实际付费、PG1 六类硬门禁与书面决议完成 |

迁移编号是全局串行资源。同一波次只允许一个切片持有下一号迁移。迁移合并顺序固定为 `202610210056 → 202610210057 → 202610220058 → … → 202610220068`。

当前没有未解决的内部阻塞。C8 与 C12 的归属已经冻结；PG0/PG1 只等待 O0 外部证据和 C0–C14 的运行产物。外部证据未取得时，相关门禁保持关闭，不得用计划状态替代证据。

## 4. 文件所有权

| 路径或范围 | 所有者 | 规则 |
|---|---|---|
| `docs/design/【契约冻结】v1-表名-枚举-接口.md` | C1 | 其他切片只读；写入前先升级契约 |
| `apps/api/schemas/report_contract.schema.json`、`apps/api/src/data_intelligence_hub/schemas/report_contract.py`、`apps/api/tests/unit/test_report_contract.py` | C1 | 唯一报告合同 schema 与 `CANONICAL_PROFILE_ID`/`SCHEMA_VERSION` 常量；C7/C9/C10 只读取或 import，不得分叉 |
| `configs/contracts/v1.1.0/*`、`scripts/contract_registry.py` | C1 | 生成物禁止手改 |
| `docs/ops/pg0-baseline-c0-2026-10-22.md` | C0 | 只追加执行证据 |
| `apps/api/src/data_intelligence_hub/api/authz.py`、`repositories/audit_events.py`、`services/audit_log.py`、`repositories/project_members.py` | C2 | C2 合并后其他切片只调用 |
| `apps/api/src/data_intelligence_hub/models/project_api_key.py`、`services/project_api_keys.py`、`services/platform_credentials.py` | C3 | C3 合并后其他切片只读 |
| `apps/api/src/data_intelligence_hub/models/workbench.py`、`services/workbench/tasks.py`、`repositories/workbench_tasks.py` | C4 | C4 合并后其他切片只读 |
| `apps/api/src/data_intelligence_hub/services/pricing.py`、`budget_service.py`、`run_limits.py`、`models/authorization.py`、`models/run_ledger.py`、`models/workbench_approval.py` | C5 | 其他切片只调用；C5 在 061 创建 `workbench_approval_actions` |
| `apps/api/src/data_intelligence_hub/services/run_executor.py`、`run_queue*.py`、`models/run_attempt.py` | C6 | C6 合并后其他切片只读 |
| `apps/api/src/data_intelligence_hub/models/claim.py`、`services/claims.py`、`services/source_clusters.py` | C7 | 其他切片只读 |
| `apps/api/src/data_intelligence_hub/services/dataset_quality.py`、`services/workbench_templates.py`、`models/market_assessment.py`、`models/data_gap.py`、`repositories/dataset_quality.py` | C8 | 其他切片只读；C8 在 064 唯一创建质量表 |
| `apps/api/src/data_intelligence_hub/services/report_publication.py`、`report_contract_v1_1.py`、`report_reviewers.py`、`report_builder.py`、`report_renderers.py`、`report_artifacts.py` | C9 | 其他切片只读；C9 在 065 创建 `report_reviewer_assignments`；报告合同与常量由 C1 拥有 |
| `apps/api/src/data_intelligence_hub/services/delivery/**` | C10 | manifest 存在 `report_artifacts` 的交付字段，不建 `delivery_manifests` 表；其他切片只读 |
| `apps/api/src/data_intelligence_hub/services/pseudonymization.py`、`export_policy.py`、`retention_service.py`、`legal_hold_service.py`、`models/retention.py` | C11 | 其他切片只读 |
| `apps/api/src/data_intelligence_hub/services/deletion_service.py`、`dsr_service.py`、`models/privacy_deletion.py` | C12 | 其他切片只读 |
| `apps/api/src/data_intelligence_hub/mcp_runtime/customer/**` | C13 | 与内部 `mcp_runtime/server.py` 分离 |
| `apps/scraper-console/src/**`、`apps/scraper-console/e2e/**` | C14 | 其他切片只读 |
| `docs/evidence/o0-pg0/**` | O0 | 只写脱敏摘要、登记册和哈希；原始件在受限库 |
| `docs/ops/pg1-pilot/**` | O1 | 只写台账、周报、复盘和决议；客户 PII 与原始证据不入库 |
| `apps/api/src/data_intelligence_hub/main.py` | 共享热点 | 每个切片只加自己的挂载；按波次合并 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | 共享热点 | 每个切片只加自己的导入；按波次合并 |
| `apps/api/src/data_intelligence_hub/core/config.py` | 共享热点 | C2、C4、C5、C6、C11、C12、C13 各加自己的开关或配置；后合并者解决冲突 |
| `apps/api/.env.example` | 共享热点 | 开关与配置示例按切片追加 |
| `configs/deploy/scrapy/docker-compose.yml` | PG0 发布批次（唯一写入者）；C2、C4、C5、C6、C10、C11、C12、C13 提供映射 | 生产 A 与 B 的权威 compose。映射固定为：C2 `WORKSPACE_RBAC_ENFORCED`；C4 `WORKBENCH_TASKS_ENABLED`、`WORKBENCH_ENABLED_MARKETS`、`WORKBENCH_TAXONOMY_PATH`；C5 `BUDGET_ENFORCEMENT_ENABLED`、`STRICT_PRICE_ENABLED`；C6 `RUN_EXECUTION_CONVERGENCE_ENABLED`、`RUN_WORKER_ENABLED`、`SCHEDULER_ENABLED`；C10 `DELIVERY_EXPORT_DIR`；C11 `RETENTION_CLEANUP_ENABLED`、`RETENTION_CLEANER_ROLE`；C12 `PRIVACY_DELETION_ENABLED`、`PRIVACY_AUDIT_CLEANER_DATABASE_URL`；C13 `SCRAPY_MCP_CUSTOMER_ENABLED`、`SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE`、`SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS`。写入、迁移、重启与开关切换只由 PG0 发布批次执行；C14 只读 |
| `configs/deploy/scrapy-new/docker-compose.yml` | 非权威 | 不得作为生产 A 或 B 的发布文件；不得用 `scrapy-new` 替代 `scrapy` |
| `.github/workflows/ci.yml` | 共享热点 | C14 统一加控制台、Playwright 与验收门禁 |

禁止两个切片同时修改同一迁移文件。禁止用 find-and-replace 重命名符号；使用 GitNexus `rename`。

`configs/deploy/scrapy/docker-compose.yml` 的 `api.environment` 键必须与上表列出的名称逐字一致；其中功能开关名同时与 §6 一致。PG0 发布批次在切换开关前运行 `docker compose --env-file /opt/data-achieve-scrapy/.env.production -f configs/deploy/scrapy/docker-compose.yml config` 并逐键断言；C14 只读复核，不修改 compose 或 `.env.production`。

契约与 registry 由 C1 独占。控制台 `apps/scraper-console/src/**` 与 Playwright `apps/scraper-console/e2e/**` 由 C14 独占。C2–C13 只提交浏览器交接清单、选择器和验收步骤，不直接修改控制台或 e2e 文件。

## 5. 迁移 058–068

新增迁移的 revision 与文件名统一使用 `20261022` 日期前缀。`202610210056` 与 `202610210057` 来自 B5，保持原前缀。全部切片合并后的最终唯一迁移头（expected migration head）是 `202610220068`；C0/B5 基线头是 `202610210057`。任何切片不得提前创建后续编号的 revision。

| 修订 | 文件 | 切片 | down_revision | 主要内容 |
|---|---|---|---|---|
| `202610220058` | `202610220058_identity_acl_audit.py` | C2 | `202610210057` | `project_members`、`audit_events`（含 `sequence_number`、`prev_hash`、`event_hash`）、角色与审计枚举 |
| `202610220059` | `202610220059_project_keys_credentials_scope.py` | C3 | `202610220058` | 密钥状态与轮换列、复合外键、项目级凭据、部分唯一索引 |
| `202610220060` | `202610220060_workbench_task_submission.py` | C4 | `202610220059` | `workbench_tasks`、`workflow_versions.workbench_task_id`、`runs.market_code` |
| `202610220061` | `202610220061_budget_ledger_pricing.py` | C5 | `202610220060` | `tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions`、`authorizations.run_id`、账本金额约束 |
| `202610220062` | `202610220062_run_step_attempts.py` | C6 | `202610220061` | `run_step_attempts`、执行步骤与 attempt 关联、`runs` 取消幂等列与部分唯一索引 |
| `202610220063` | `202610220063_claim_evidence_completeness.py` | C7 | `202610220062` | Claim 治理字段、独立来源、审核与逐市场 scope |
| `202610220064` | `202610220064_dataset_quality.py` | C8 | `202610220063` | `dataset_versions` 内容哈希、`market_assessments`、`data_gaps`、质量与缺口字段 |
| `202610220065` | `202610220065_report_publication.py` | C9 | `202610220064` | 报告生命周期、`report_reviewer_assignments`、审核签字、不可变与只追加触发器 |
| `202610220066` | `202610220066_delivery_manifest_publish.py` | C10 | `202610220065` | `report_artifacts` 交付列、`delivery_class`、`acceptance_deadline`、Quick 方向稿关联、manifest 封存字段、追加式验收事件、下载审计、sidecar |
| `202610220067` | `202610220067_pseudonymization_retention.py` | C11 | `202610220066` | 伪名盐、保留策略、法律保留、清理记录 |
| `202610220068` | `202610220068_privacy_deletion_dsr.py` | C12 | `202610220067` | 删除请求、墓碑、删除证明、DSR、隐私审计事件 |

迁移规则：

1. 每个切片最多一个迁移；没有迁移的切片在 §1 明确写 `无`。
2. 执行前 `uv run alembic heads` 必须只有一行。
3. 每个迁移在空 Postgres 15 上 `upgrade head → downgrade -1 → upgrade head` 通过。
4. 迁移文件头保留 `source-only` 声明。
5. 生产应用必须逐主机授权并先备份。A 与 B 不自动互为灾备。
6. 手改 `alembic_version` 一律禁止。

## 6. 功能开关

| 开关 | 所属切片 | 默认 | PG0 必需 | 打开时机 |
|---|---|---:|---:|---|
| `WORKSPACE_RBAC_ENFORCED` | C2 | `false` | 是 | C2 通过后 |
| `WORKBENCH_ENABLED_MARKETS` | C4 | 11 个正式市场 | 是 | C4 通过后逐个市场复核 |
| `RUN_WORKER_ENABLED` | C6 | `false` | 是 | C6 通过后由 PG0 发布批次打开 |
| `RUN_EXECUTION_CONVERGENCE_ENABLED` | C6 | `false` | 是 | C6 通过且 C14 只读验收后由 PG0 发布批次打开；C14 只读验证 |
| `SCHEDULER_ENABLED` | C6 | `false` | 否 | 按试点需要 |
| `vault_write_enabled` | C3 | 现有配置 | 是 | C3 通过后 |
| `PRIVACY_DELETION_ENABLED` | C12 | `false` | 是 | C12 通过且法务/备份门禁完成后 |
| `RETENTION_CLEANUP_ENABLED` | C11 | `false` | 是 | C11 通过、`dih_retention_cleaner` 权限与保留策略验收后由 PG0 发布批次打开；C14 只读验证 |
| `SCRAPY_MCP_CUSTOMER_ENABLED` | C13 | `false` | 是 | C13 通过后，仅对试点工作区 |
| `GOVERNED_TASK_PLATFORM_ENABLED` | PG0 发布批次（C14 只读） | `false` | 是 | PG0 评审 Go 后由 PG0 发布批次设置；只作部署与验收记录 |
| `WORKBENCH_TASKS_ENABLED` | C4 | `false` | 是 | C4 通过后 |
| `BUDGET_ENFORCEMENT_ENABLED` | C5 | `false` | 是 | 迁移 061、`tool_prices` 种子与项目额度设置完成后由 PG0 发布批次打开；C14 只读验证 |
| `STRICT_PRICE_ENABLED` | C5 | `false` | 是 | `BUDGET_ENFORCEMENT_ENABLED=true` 稳定后由 PG0 发布批次打开；C14 只读验证 |
| `PUBLIC_REPORT_SHARE_ENABLED` | C14 | `false` | 否 | 首期固定关闭；公开分享延期 |
| `SCRAPY_MCP_CUSTOMER_RATE_PER_MINUTE` | C13 | 现有默认 | 是 | 按试点容量设定 |
| `SCRAPY_MCP_CUSTOMER_CONCURRENT_CALLS` | C13 | 现有默认 | 是 | 按试点容量设定 |

规则：

1. 所有新增布尔开关默认 `false`。
2. 开关只控制入口与后台任务，不控制审计。审计写入不得因开关关闭而跳过。
3. 关闭时对应路由返回 404。C4 的 workbench 路由与 `POST /api/runs` 的 workbench 模式返回 503 `workbench_disabled`，旧 `POST /api/runs` 行为不变。客户 MCP 返回 `404` 或 `tool_not_allowed`，不得返回内部工具。
4. 开关变更写 `config.switch.changed` 审计。
5. 开关必须由所属切片在 `core/config.py` 与 `.env.example` 登记。C14 只在 CI、Playwright 与只读发布验收中读取，不新增后端开关。
6. `GOVERNED_TASK_PLATFORM_ENABLED` 是部署与验收门禁记录，不是后端运行开关；由 PG0 发布批次设置，C14 与 O1 只读校验。C5 的 `BUDGET_ENFORCEMENT_ENABLED`、`STRICT_PRICE_ENABLED`，C6 的 `RUN_EXECUTION_CONVERGENCE_ENABLED` 与 C11 的 `RETENTION_CLEANUP_ENABLED` 都默认 `false`，由 PG0 发布批次在迁移、种子、权限、只读验收与门禁通过后显式打开并验证；C14 只读。C7、C8、C9、C10 没有独立布尔开关时，受所属切片发布顺序与该门禁控制。
7. C13 不建租约表，因此不设置租约过期开关；速率与并发使用已登记的 `audit_events` 计数。

## 7. PG0 门禁映射

PG0 由 O0 Task 14 的 11 项门禁矩阵判定，没有 Conditional Pass。每项必须 `pass`，六方必须 `approve`，必需证据必须 `accepted`。

| 门禁 | 设计要求（§8.2） | 代码切片 | O0 证据 | 验证入口 |
|---|---|---|---|---|
| `PG0-01` | 合成数据黄金路径端到端通过 | C0–C14 | `O0-PILOT-GOLD-001` | C14 golden path；O0 14 阶段日志与哈希 |
| `PG0-02` | 一份内部 Quick 端到端验收 | C0–C14 | `O0-PILOT-ACC-001` | C14 验收；O0 验收记录与审核签字 |
| `PG0-03` | 一份内部 Standard 端到端验收 | C0–C14 | `O0-PILOT-ACC-002` | C14 验收；O0 验收记录与审核签字 |
| `PG0-04` | 工作区、项目、密钥和客户工具边界生效 | C2、C3、C13 | `O0-PILOT-ACC-001`、`O0-PILOT-ACC-002` | C2 ACL；C3 密钥；C13 鉴权与 Cookie 拒绝；C14 |
| `PG0-05` | 价格簿、预算和账本能够对账 | C5 | `O0-FIN-001`、`O0-FIN-002` | C5 对账与并发测试；C14 |
| `PG0-06` | 逐市场质量、证据、Claim、报告和交付闭环生效 | C7、C8、C9、C10 | `O0-PILOT-GOLD-001`、`O0-PILOT-ACC-001`、`O0-PILOT-ACC-002` | C7–C10 测试；C8 质量记分卡；C14 |
| `PG0-07` | 伪名化、导出遮蔽、保留、删除和审计生效 | C11、C12 | `O0-PRIV-DPA-001`、`O0-PRIV-XB-001`、`O0-PILOT-GOLD-001` | C11 遮蔽与保留；C12 删除与审计；C14 |
| `PG0-08` | TikHub 及实际来源具备书面商业依据 | O0 | `O0-UP-TIKHUB-001`–`008`、`O0-UP-PROVIDER-001`–`005` | O0 许可矩阵与原始件哈希 |
| `PG0-09` | 至少 3 份可执行的书面付费试点承诺 | O0 | `O0-COMMIT-001`–`003` | O0 承诺卷宗与付款路径；不计实际付费 |
| `PG0-10` | 目录、MCP 工具和生产构建事实基线冻结 | C0、C14 | `O0-INFRA-001`、`O0-INFRA-002` | C0 事实快照；O0 健康、revision、digest、客户工具数 |
| `PG0-11` | 没有未处置的严重风险 | O0 | `O0-RISK-001` | O0 风险台账与严重风险复核 |

硬控制指标与门禁的对应关系：

| 硬控制 | 目标 | 门禁 |
|---|---:|---|
| Claim 证据链接覆盖率 | 100% | `PG0-06` |
| 逐市场质量状态完整率 | 100% | `PG0-06` |
| 跨工作区成功访问 | 0 | `PG0-04` |
| 账本不平与重复结算 | 0 | `PG0-05` |
| 预算阻断生效 | 100% | `PG0-05` |
| PII 检查失败后发布 | 0 | `PG0-07` |
| 客户链出现 `creator_cookie` | 0 | `PG0-04`、`PG0-07` |
| 关键操作缺失审计 | 0 | `PG0-07` |

门禁规则：

- `fail` 时保持关闭的能力：客户项目密钥签发、客户个人数据处理、付费生产任务、无书面许可的来源、无覆盖或负毛利的市场、无零保留条款的 LLM。
- 外部证据未取得时，对应 O0 行保持 `open`，门禁保持未通过；这不是计划内部阻塞。
- 不得用计划状态、口头说明或未签署文件替代 `accepted` 证据。

## 8. 执行前通用门禁

### 8.1 GitNexus

每个切片编辑前：

```bash
node .gitnexus/run.cjs status
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .
```

规则：

- `risk` 为 `HIGH` 或 `CRITICAL` 时，先报告调用方、进程与影响，再决定是否继续。
- `risk` 为 `UNKNOWN` 时视为未解析。必须用文本搜索确认调用方，不得按低风险处理。
- 每个切片提交前运行：

```bash
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

`partial: true` 或 `truncated: true` 不是干净检查。重跑直到两者为 `false`。

### 8.2 Worktree 与基线事实

基线事实：

- `feat/p1-identity` 已是 `f0560ca652a378ddf9ba65e15284a0311769994b` 的祖先；C0 只校验，不重复合并 P1。
- `feat/b4-report-contract` 已是 `feat/b5-workbench` 的祖先；B4 经 B5 传递，C0 不单独合并 B4。
- C0 只合并 `feat/b5-workbench`，并保留已批准设计 spec。

C0 执行 worktree：

```bash
git worktree add /Users/lute/Project/data_scrapy-c0 \
  -b feat/pg0-baseline-c0 f0560ca652a378ddf9ba65e15284a0311769994b
```

主工作树不切换分支，已暂存或未跟踪的计划文件保持原状。C0 只把本计划复制到 `/Users/lute/Project/data_scrapy-c0` 并在该 worktree 提交；主工作树不做 C0 提交。

C0 完成后打本地标签：

```bash
git tag -a pg0-baseline-v1 -m "PG0 baseline: B5 merged, migrations 056/057 verified"
```

C1–C14 每个切片一个 worktree。起点按依赖链，不全部从 `pg0-baseline-v1` 创建：

| 切片 | worktree 起点 |
|---|---|
| C1 | `pg0-baseline-v1` |
| C2 | `feat/gov-c1` |
| C3 | `feat/gov-c2` |
| C4 | `feat/gov-c3` |
| C5 | `feat/gov-c4` |
| C6 | `feat/gov-c5` |
| C7 | `feat/gov-c6` |
| C8 | `feat/gov-c7` |
| C9 | `feat/gov-c8` |
| C10 | `feat/gov-c9` |
| C11 | `feat/gov-c10` |
| C13 | `feat/gov-c10`；与 C11 并行，不等待 C11 |
| C12 | `feat/gov-c11` |
| C14 | 包含 C0–C13 的集成分支 `feat/gov-integration-c1-c13`；C12 与 C13 都合并后创建 |

命令模板：

```bash
git fetch origin
git worktree add ../data_scrapy-<slice> -b feat/gov-<slice> <起点>
```

规则：

1. 一个 worktree 只做一个切片。
2. 开始前 worktree 自身 `git status --porcelain` 必须为空。C0 例外：主工作树允许保留计划改动；C0 worktree 内只允许待提交的本计划文件。
3. C1 从 tag 创建；C2–C13 从前置切片分支创建；C14 从集成分支创建。
4. 迁移文件只在分配的 worktree 创建，不跨 worktree 复制。
5. 合并前重跑该切片全部测试与 GitNexus 检查。
6. 合并后删除 worktree，保留分支一个发布周期。
7. C0 只清理 prunable worktree 元数据；不得删除其他 linked worktree。

### 8.3 迁移

空 Postgres 15 验证：

```bash
export TEST_POSTGRES_PASSWORD="${TEST_POSTGRES_PASSWORD:?set TEST_POSTGRES_PASSWORD}"
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:${TEST_POSTGRES_PASSWORD}@127.0.0.1:5432/dih_migration_test"
cd apps/api
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic downgrade -1
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic heads
```

规则：

1. 唯一头必须是当前切片的目标修订。
2. `downgrade` 失败视为切片未完成。
3. 迁移只包含 schema 与必要回填，不包含业务逻辑。
4. 每个切片的回滚点是其前置分支或标签，加上本切片迁移的 `alembic downgrade -1` 验证。
5. 生产迁移只向前；回滚用发布前备份恢复或新迁移，不反向执行破坏性 DDL。

### 8.4 生产 A 与 B

本节所有备份、迁移、compose/env 修改、容器重启与功能开关切换只由 PG0 发布批次执行。C14 只运行只读健康检查、canary、preflight 和浏览器验收；C14 不备份、不迁移、不改 compose/env、不重启容器、不切换开关。

| 目标 | 主机 | 密钥 | 分支 | 权威 compose | 公网 |
|---|---|---|---|---|---|
| A | `ubuntu@43.163.92.244` | `zhoujian_pachong.pem` | `main` | `configs/deploy/scrapy/docker-compose.yml` | `https://scrapy.luteos.com` |
| B | `ubuntu@101.34.52.232` | `DDDD.pem` | `deploy/tiktok-cdo-codex` | `configs/deploy/scrapy/docker-compose.yml`（不是 `scrapy-new`） | `https://scrapy.lute-tlz-dddd.top` |

生产 B 的权威 compose 是 `configs/deploy/scrapy/docker-compose.yml`。`configs/deploy/scrapy-new/docker-compose.yml` 不是生产 B 的发布文件，不得用于 A 或 B 的迁移、构建或验收。

#### 8.4.1 分支提升门禁

分支提升是生产发布的独立前置门禁。它只执行 Git 分支操作和只读校验，不备份、不迁移、不改 compose/env、不重启容器、不切换开关。C0–C14 子计划不执行本节。

**A 分支提升**

1. 准入：C0–C14 全部完成。C14 在包含 C0–C14 的集成分支上通过契约检查、ruff、mypy、pytest、前端构建、Playwright 与 GitNexus 变更检查。记录集成分支 tip 的完整 SHA。
2. 用户批准：向用户提交 PR，请求把集成分支 tip 合入 `main`。PR 必须写明测试数字、迁移唯一头 `202610220068` 与 GitNexus 结论。未取得用户明确批准时，不合并、不推送。
3. 合并并推送：用户批准后，把集成分支 tip 合入 `main`。使用 merge commit 或快进合并，不使用 squash 或 rebase。确认 `git merge-base --is-ancestor <integration-tip> main` 成功，再执行 `git push origin main`。
4. 部署准入：`git ls-remote --heads origin main` 必须等于本地发布 HEAD。只有满足此条件，才可执行 `scripts/deploy-p0.sh --host a`。

**B 分支提升**

B 分支提升把 `main` 合并到长期分支 `deploy/tiktok-cdo-codex`，只保留已批准的 TikTok CDO 差异。

1. 前置授权：只有用户对生产 B 明确给出目标授权（目标 schema `202610220068`、备份与回滚计划）后，才可开始 B 分支提升。未取得授权时，不创建 worktree、不合并、不推送、不部署 B。B 保持当前批准 schema（当前记录为 `202607280044`），且不阻塞 A。该授权与发布顺序中的 B 迁移授权门禁是同一门禁；分支提升不替代备份与迁移门禁。
2. 隔离 worktree：先完成 A 的 `main` 提升并推送。执行 `git fetch origin`。比较本地 `deploy/tiktok-cdo-codex` 与 `origin/deploy/tiktok-cdo-codex`；本地存在未推送的独有提交时停止并核对，不得丢弃或强推。在独立 worktree 中从 `origin/deploy/tiktok-cdo-codex` 创建临时提升分支。不得在主工作树执行合并。
3. 合并：把 `main`（已推送的 `origin/main`）合入基于 `deploy/tiktok-cdo-codex` 的临时提升分支。使用 `git merge origin/main`。不做 rebase。
4. 冲突：只按已记录的冲突面解决 `agents/tiktok_cdo/config.py` 与 `agents/tiktok_cdo/router.py`。冲突面记录在 `docs/【运维手册】生产环境基线.md`。出现其他冲突时停止并上报，不得手工解决业务代码冲突。
5. 最终 tip 校验：以下检查必须全部通过。
   - `git merge-base --is-ancestor pg0-baseline-v1^{commit} HEAD` 成功。`pg0-baseline-v1` 保持本地标签，不推送。
   - `git merge-base --is-ancestor <integration-tip> HEAD` 成功。
   - `apps/api/alembic/versions/` 的迁移链连续到 `202610220068`，包含 `202610210056`、`202610210057` 与 `202610220058`–`202610220068`；在 `apps/api` 执行 `uv run alembic heads`，唯一头是 `202610220068`。
   - B 的专属差异仍只有 TikTok CDO 的已批准实现，不包含 A/B 共用代码的分叉。
6. 推送：把临时提升分支推送到 `deploy/tiktok-cdo-codex`。执行 `git push origin HEAD:deploy/tiktok-cdo-codex`。`git ls-remote --heads origin deploy/tiktok-cdo-codex` 必须等于最终 tip。
7. 清理：删除临时提升 worktree。保留 `deploy/tiktok-cdo-codex` 分支一个发布周期。

**共同规则**

1. 分支提升完成后，`scripts/deploy-p0.sh` 才可执行远端 `git fetch` 与 `git merge --ff-only FETCH_HEAD`。发布命令必须从最终提升 tip 的干净 worktree 运行。脚本的 `check_remote_branches` 要求 `origin/<branch>` 等于本地 HEAD；跳过分支提升时脚本直接失败。
2. 生产 A 只从 `origin/main` 发布，生产 B 只从 `origin/deploy/tiktok-cdo-codex` 发布。不得从集成分支、标签或本地分支直接发布。
3. 分支提升不改变本节的发布顺序、B 备份门禁、B 迁移授权门禁与 edge 红线（不重建 `edge`）。

#### 8.4.2 发布顺序

以下步骤只在 §8.4.1 的分支提升完成后执行。

1. 本地全绿：ruff、mypy、pytest、前端构建、GitNexus 变更检查。
2. 生产 A 备份：

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244 'cd /opt/data-achieve-scrapy/app && set -a && . /opt/data-achieve-scrapy/.env.production && set +a && docker compose --env-file /opt/data-achieve-scrapy/.env.production -f configs/deploy/scrapy/docker-compose.yml exec -T db pg_dump -U "$SCRAPY_POSTGRES_USER" -d "$SCRAPY_POSTGRES_DB" -Fc > /opt/backups/dih-pre-<slice>-$(date +%Y%m%d-%H%M).dump'
```

3. 生产 A 发布：

```bash
scripts/deploy-p0.sh --host a --dry-run
scripts/deploy-p0.sh --host a
```

4. 验证 A：`/api/health` 返回 200 且 `schema_revision` 为目标修订；每个 PG0 发布批次按当批切片目标核对，全量完成后最终值必须是 `202610220068`；`/api/tools` 与 `/api/tool-catalog` 返回 200；MCP 匿名 401；登录链路 200。
5. 生产 B 在 §8.4.1 的 B 分支提升已推送后，先备份，再发布。服务器本地分支没有 upstream，`git pull` 会静默不拉取；必须显式 fetch 后快进：

```bash
git fetch origin deploy/tiktok-cdo-codex
git merge --ff-only FETCH_HEAD
scripts/deploy-p0.sh --host b --dry-run
scripts/deploy-p0.sh --host b
```

6. B 的 GitHub 拉取失败时按 `scripts/deploy-p0.sh` 的重试逻辑执行；不得用管道吞掉 `git fetch` 退出码。必要时用本地 `git bundle` 传输，再在服务器 `git fetch /tmp/<file>.bundle deploy/tiktok-cdo-codex`。
7. 不重建 `edge`。只执行 `up -d --no-deps api console` 与 `restart edge`。
8. B 的迁移授权门禁：B 库当前批准版本为 `202607280044`。`202610190045` 及其后的 `202610220058`–`202610220068` 只有在用户对 B 给出目标授权和备份/回滚计划后才可应用。未取得时 B 保持旧 schema，不部署新迁移，且不阻塞 A。
9. A 发布前必须备份并记录 `schema_revision`；A 与 B 不自动互为灾备，不得声称同区域或同故障域。

生产 A/B 共同红线：

- 生产工作区不干净时停止发布。
- 迁移失败时停止发布，旧容器继续服务。
- 发布后公网非 200 时停止继续发布，先回退或修复。
- 不得把 A 与 B 自动称为灾备。
- 不得把 TikHub DPA 当作商业转售许可。
- 不得在 PG0 通过前签发客户密钥或接收客户个人数据。

## 9. 完成定义

### 9.1 单个切片完成

- [ ] 计划内全部 checkbox 完成。
- [ ] 新增测试通过，既有测试无回归。
- [ ] `uv run ruff check .` 与 `uv run mypy src tests` 通过。
- [ ] 迁移在空 Postgres 15 上 `upgrade → downgrade -1 → upgrade` 通过。
- [ ] `node .gitnexus/run.cjs detect-changes --scope all --repo .` 的 `partial` 与 `truncated` 均为 `false`。
- [ ] 新增开关默认 `false`，关闭时行为符合 §6。
- [ ] 新增写操作调用 C2 的审计接口。
- [ ] 契约 v1.1 已登记新增表、列、枚举与路径。
- [ ] 计划文件状态更新为 `已完成`。
- [ ] 合并提交信息带测试数字、迁移 head 与 GitNexus 结论。

### 9.2 平台完成（PG0 准入）

- [ ] C0–C14 全部完成。
- [ ] O0 的证据全部 `accepted`，或经书面确认 `not_applicable`（仅限非必需项）。
- [ ] O0 Task 14 的 11 项 PG0 门禁全部 `pass`。
- [ ] §7 的八项硬控制指标全部达标。
- [ ] 合成黄金路径、内部 Quick、内部 Standard 全部通过。
- [ ] PG0 六方签核全部为 `approve`（Go）。
- [ ] 生产 A 与 B 的 schema、构建身份、目录摘要与 MCP 工具数已冻结并记录。
- [ ] 没有未处置的严重风险。
- [ ] 没有客户密钥在 PG0 前签发。

### 9.3 PG1 启动条件

- [ ] PG0 六方签核为 `approve`（Go）。
- [ ] O0 的商业、法务、财务证据覆盖全部试点合同。
- [ ] `SCRAPY_MCP_CUSTOMER_ENABLED=true`，且只对试点工作区生效。
- [ ] 3–5 家参与者已完成 O1 准入清单，并已实际签约、付款、创建首单；PG0 的书面承诺不计入实际付费。
- [ ] 没有把 LOI、口头意向、未付款合同或免费 Quick 线索计入实际付费。
- [ ] 停止与回退流程已演练。

## 10. 计划文件索引

| 类别 | 文件 |
|---|---|
| 总索引 | `docs/superpowers/plans/2026-10-22-governed-task-platform-master-plan.md` |
| C0 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c0-baseline-integration.md` |
| C1 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md` |
| C2 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c2-identity-project-acl-audit.md` |
| C3 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c3-project-keys-credentials.md` |
| C4 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c4-task-submission-idempotency.md` |
| C5 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c5-budget-ledger-pricing.md` |
| C6 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md` |
| C7 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c7-claims-evidence.md` |
| C8 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c8-dataset-quality-template.md` |
| C9 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c9-report-contract-artifacts.md` |
| C10 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md` |
| C11 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c11-pseudonymization-retention.md` |
| C12 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c12-deletion-dsr.md` |
| C13 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c13-customer-mcp.md` |
| C14 | `docs/superpowers/plans/2026-10-22-governed-task-platform-c14-console-ci-acceptance.md` |
| O0 | `docs/superpowers/plans/2026-10-22-governed-task-platform-o0-pg0-evidence.md` |
| O1 | `docs/superpowers/plans/2026-10-22-governed-task-platform-o1-pg1-paid-pilot.md` |
