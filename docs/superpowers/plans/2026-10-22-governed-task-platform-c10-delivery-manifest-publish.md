# C10 交付清单、Manifest 与发布门禁实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 B5 的报告与 Claim 基线上，为一份已审核的报告产物生成不可变的正式交付包：逐文件 SHA-256、`delivery_manifest.json`、外部 sidecar、公开合同投影、G-Claim/G-Publish 门禁、审核签字校验、验收快照追加事件，以及篡改时拒绝下载。C10 还必须提供两条补充交付路径：Quick 2 小时方向稿（不审核、不启动验收、不重复计费）和追加式验收事件（accepted / disputed / deemed_accepted），并在发布前复用 C11 的导出 PII 扫描阻断含 PII 的 manifest、bundle、HTML 与 Claim。

**Architecture:** 复用 `report_artifacts`、`claims`、`claim_evidence`、`report_audit_events`。只在 `report_artifacts` 上增加交付状态、交付类别、验收截止与封存字段；`report_audit_events.artifact_id` 与 `report_id` 可空由 C9 的迁移 065 提供，C10 只读该结构并追加交付/验收事件，不重复迁移。不建第二套报告或 Claim 表，不建第二套验收表。manifest 为 canonical JSON，自身哈希写入 `.sha256` sidecar 和 `report_audit_events`；下载前重算全部文件哈希，任一不一致返回 409 并写 `delivery_tamper_detected`。G-Claim 只消费 C7 的 `load_publishable_claim_rows()` / `validate_claim_bundle()`；pending 或 stale 的 Claim 一律拒绝。Quick 2 小时稿使用同一 `task_id`、同一数据集版本与同一 Claim 建议集，但写入独立的 `delivery_class='quick_draft'` 交付行，`acceptance_deadline` 为空，且不写 `acceptance_snapshot_appended`。正式 24 小时交付仍要求 C9 的 `report_review_approved`。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2 async、Alembic、Pydantic v2、pytest、SQLite（单测）/PostgreSQL 16（生产）。

## 0. 基线、决策与前置

### 0.1 事实基线

- 执行 worktree：`/Users/lute/Project/data_scrapy-gov-c10`。从前置切片 C9 的分支 `feat/gov-c9` 创建：`git worktree add /Users/lute/Project/data_scrapy-gov-c10 -b feat/gov-c10 feat/gov-c9`。该分支已包含 C0–C9 与 C1 契约，schema head 必须是 `202610220065`。不得在 worktree 内合并 C1–C9。B5 只是报告/Claim 的实现基线，不再作为分支起点。创建后运行 `git merge-base --is-ancestor feat/gov-c9 HEAD`，退出码必须为 0。
- B5 已有 `report_artifacts`（迁移 057）、`claims`/`claim_evidence`（迁移 056）、`report_audit_events`（迁移 009）、`canonical_json_bytes`、`contract_sha256`、`verify_artifact`。C10 只消费这些，不复制。
- C7 提供 Claim 与反证事实；C8 提供质量、缺口与质量门禁事实；C9 提供报告合同、两页 HTML、五哈希、发布字段与审核签字事件。C10 不实现 Claim 编辑、报告渲染、审核或报告发布工作流。
- C9 的审核签字以追加事件 `report_review_approved` 写入 `report_audit_events`，必须带 `artifact_id` 与 C9 的 0.4/7.4 定义的 metadata 键。C10 只读该事件，不写签字。
- 公开分享延期。C10 只做项目内鉴权下载，不做匿名分享。
- C10 只新增一个迁移 `202610220066`。C2–C9 已占用 `058`–`065`；只有 C2 的 `058` 保留 `20261021` 前缀，`063`–`066` 统一使用 `20261022` 前缀。`202610220066` 只有在 C1 完成第 0.4 节登记、C9 的 065 合入后才允许创建。

### 0.2 决策 D-C10-01：公开分享按契约延期

**选择：延期，不在 C10 实现。**

理由：

1. C10 明确排除隐私保留与 MCP。匿名分享需要分享令牌生命周期、撤销、访问审计、公开投影的 PII 遮蔽、滥用限流与删除联动；这些属于 C11（伪名化与保留）和 C12（删除/DSR）的范围。现在实现会造出第二条遮蔽路径，违反设计 §6.1 第 8 条。
2. 冻结契约列出 `report_shares` 与 `/api/reports/public/{token}`，但 B5 schema 没有 `report_shares` 表。实现它至少需要建表、公开鉴权旁路、令牌哈希与撤销，不是 C10 的“一个迁移”能安全完成。
3. 任务允许“先契约改为延期”。C1 在契约冻结 v1.1 中把 `report_shares`、`POST /api/reports/{report_id}/share`、`GET /api/reports/public/{token}`、`POST /api/reports/public/{token}/access` 标记为【延期】，并注明 C10 只提供鉴权下载。

结果：C10 的“公开合同投影”是交付包内的 `report_contract.json` 文件，不是公开 URL。项目内下载走 `GET /api/reports/{artifact_id}/delivery`，仍受工作区与项目权限约束。C1 必须把上述四项标成延期，C10 的预检测试会断言这一点；未登记时任务阻塞。

### 0.3 决策 D-C10-02：在 C1 冻结 B5 canonical profile，不切 RFC 8785

**选择：冻结 `dih-canonical-json-v1`，不改 B5 实现。**

B5 的 `schemas/report_contract.canonical_json_bytes` 不是完整 RFC 8785。它自己声明了三处差异：

- `1e-7` 写成 `1e-07`；
- `-0.0` 保留负号；
- 键排序按 Unicode 码点，不按 UTF-16 码元。

GitNexus 对 `canonical_json_bytes` 的上游影响是 **50 个符号、风险 HIGH**。直接改成 RFC 8785 会改变所有已存在的 `contract_sha256`，使 B5 已生成的报告与签字失效。因此 C1 冻结以下 profile，C10 只调用现有函数，不另写序列化器：

```text
profile_id: dih-canonical-json-v1
encoding: UTF-8
object_keys: 按 Unicode 码点升序
separators: "," 与 ":"
ensure_ascii: false
timestamps: UTC，Z 后缀，秒精度
dates: YYYY-MM-DD
Decimal: 字符串，保留精度
reject: NaN、Infinity
exclude at top level: generated_at、artifact
known deviations from RFC 8785: 1e-07、-0.0、Unicode 码点排序
```

严格 RFC 8785 升级延期。若未来实施，必须注册不同的 profile ID `dih-canonical-json-rfc8785-v1`，并按合同版本升级流程提供旧合同重哈希与签字迁移方案；不得改变 `dih-canonical-json-v1` 的字节输出。C10 不做这件事。

### 0.4 C1 合同登记门禁（迁移 066 的前置）

C1 必须在 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 中加入以下内容。C10 的 `test_c10_contract_registration.py` 逐项断言；缺任一项，C10 不得创建迁移 066。

```markdown
### 2.9 交付状态与类别 report_artifacts
delivery_status: pending · delivered · superseded
delivery_class: formal · quick_draft

C9 的 `report_artifacts.status` 保持 `draft · published · superseded`。
C1 必须把 `delivery_status`、`delivery_class` 与 C9 的 `status` 分成三个不同值集；
不得复用同名状态机。Quick 2 小时方向稿固定 `delivery_class='quick_draft'`；
正式 24 小时交付固定 `delivery_class='formal'`。

### 2.10 交付与验收事件 report_audit_events.event_type
gate_evaluated · delivery_published · delivery_downloaded ·
delivery_tamper_detected · delivery_pii_detected ·
acceptance_snapshot_appended · delivery_superseded ·
acceptance_accepted · acceptance_disputed · acceptance_deemed_accepted

### 2.11 交付门禁
G-Claim 与 G-Publish 的决定写入 report_audit_events（event_type=gate_evaluated），
不写 authorizations。authorizations 只承载计划、预算与执行授权。

### 2.12 验收事件到验收状态的唯一映射
acceptance_accepted → accepted
acceptance_disputed → objection
acceptance_deemed_accepted → auto_accepted

使用 C1 `$defs/acceptance.status` 的既有枚举；不得新增第二套验收状态枚举。
Quick 2 小时稿不写任何 acceptance_* 事件，投影为 `not_applicable`。
`deemed_accepted` 只能在交付后第 5 个工作日 23:59:59 UTC 之后写入。

### 3.1 新建端点
POST /api/reports/{artifact_id}/delivery/publish
GET /api/reports/{artifact_id}/delivery
GET /api/reports/{artifact_id}/delivery/manifest
POST /api/reports/{artifact_id}/delivery/quick-draft
GET /api/reports/{artifact_id}/delivery/quick-draft
GET /api/tasks/{task_id}/delivery/quick-draft
POST /api/reports/{artifact_id}/delivery/acceptance/accept
POST /api/reports/{artifact_id}/delivery/acceptance/dispute
POST /api/reports/{artifact_id}/delivery/acceptance/deemed-accepted
GET /api/reports/{artifact_id}/delivery/acceptance

所有 POST 端点必须要求 `Idempotency-Key` 请求头。
Quick 2 小时稿只对 `package_type='quick'` 的任务开放；Standard 只能走 24 小时正式交付。

### 4.4 report_artifacts 交付列
delivery_status string(20) not null default 'pending'
delivery_class string(20) not null default 'formal'
manifest_json json null
manifest_sha256 string(64) null
manifest_sidecar_sha256 string(64) null
public_contract_json json null
acceptance_snapshot_json json null
acceptance_deadline timestamptz null
delivered_at timestamptz null
delivered_by uuid null
supersedes_delivery_id uuid null
quick_draft_of_artifact_id uuid null
publish_idempotency_key_hash string(64) null
唯一约束 (workspace_id, publish_idempotency_key_hash) where hash is not null
CHECK delivery_class in ('formal','quick_draft')
CHECK formal delivered 必须有 acceptance_snapshot_json 与 acceptance_deadline；
      quick_draft delivered 必须 acceptance_snapshot_json is null、
      acceptance_deadline is null、quick_draft_of_artifact_id is not null

manifest 顶层键固定：schema_version（delivery-manifest.v1）、manifest_id、task_id、
report_artifact_id、report_version、created_at、files、bundle_sha256、sidecar_sha256、
access_scope、retention_class。files[] 只有 path、sha256、size_bytes、media_type。

### 4.5 report_audit_events 扩展
由 C9 的迁移 065 提供 `artifact_id`、`report_id` 可空与目标 CHECK。
C10 只读该结构并追加交付/验收事件，不扩展列、不重复迁移。
验收幂等键哈希与 payload 摘要写入事件 `metadata_json`，不新增列、不新增表。
派生固定为 `metadata_json.idempotency_key_hash = sha256("delivery-acceptance.v1:{idempotency_key}")`；
`payload_sha256 = sha256(canonical_json_bytes(payload))`，canonical profile 为 `dih-canonical-json-v1`；
payload 只含 `event_type`、`artifact_id`、`references` 与可选 `note`（`note` 为空时省略），不得写入原始 `Idempotency-Key`。

### 4.6 交付错误码
publish_forbidden 403 · reviewer_assignment_required 403 ·
reviewer_self_review_forbidden 403 · reviewer_assignment_expired 403 ·
idempotency_key_required 400 · idempotency_conflict 409 ·
delivery_not_publishable 409 · delivery_input_invalid 422 ·
delivery_pii_detected 409 · quick_draft_not_allowed 422 ·
quick_draft_claim_invalid 422 · acceptance_window_open 409 ·
acceptance_already_closed 409 · acceptance_reference_invalid 422 ·
acceptance_not_applicable 409

### 6.3 canonical profile
dih-canonical-json-v1：UTF-8、键按 Unicode 码点排序、分隔符 "," 与 ":"、
ensure_ascii=false、时间 UTC Z 秒、日期 YYYY-MM-DD、Decimal 字符串、
拒绝 NaN/Infinity，顶层排除 generated_at 与 artifact。
已知偏离 RFC 8785：1e-07、-0.0、码点排序。

### 6.4 公开合同投影
profile: dih-public-report-contract-v1
schema_version: 1.0.0-public
禁止键：provider、provider_id、endpoint_type、source_tool_id、unit_price、
authorization_id、actor_id、approver、owner、run_ledger。
evidence 使用 source_ref；run 信息只出现在 run_receipt.json。
禁用语言画像只有一份：`dih-descriptive-language-v1`；C10 命中时返回
`delivery_input_invalid`，并附同一 `profile_id`；C9 命中时返回 `report_forbidden_language`。

### 6.5 导出 PII 扫描
交付发布与下载复用 C11 `services/export_policy` 的唯一扫描 API。
manifest、公开合同与 Claim bundle 调 `scan_export_value(value, field_path=...)`；
全部 bundle 文本文件（两页 HTML、CSV、JSON、Markdown）调
`scan_export_policy(text, field_path=...)`。
命中即阻断，返回 `delivery_pii_detected`，只记录 kind 与 field_path，不记录原始值。

### 7.3 公开分享
report_shares、POST /api/reports/{report_id}/share、
GET /api/reports/public/{token}、POST /api/reports/public/{token}/access
标记【延期】。C10 只提供项目内鉴权下载；Quick 2 小时稿也不得公开分享。

### 7.4 审核签字事件 metadata
C9 写入 `report_audit_events.event_type = report_review_approved`；
审阅者授权只认 `report_reviewer_assignments` 的 active 行。
C10 只读该事件与指派，不写签字、不写表；读取 `reviewer_role`、`reviewer_assignment_id`、
`reviewed_contract_sha256`、`reviewed_data_sha256`、`reviewed_report_html_sha256`、
`reviewed_sop_html_sha256`、`reviewed_claim_digest`，不重复登记。
`reviewed_claim_digest` 由 C9 的 `claim_review_digest()` 计算。
`reviewer_role` 只能是 `internal_reviewer`；客户 `owner/admin/member` 不是审核角色。

### 7.5 Quick 2 小时方向稿
Quick 2 小时稿与 24 小时正式版属于同一 `task_id`，不重复计费。
Quick 2 小时稿不审核、不触发验收、不生成 Standard 四态、不得出现 `confirmed`。
正式 24 小时交付仍必须通过 G-Publish 的审核签字校验。
```

迁移编号也由 C1 冻结：C2=`202610220058`，C3=`202610220059`，…，C9=`202610220065`，C10=`202610220066`。

#### 0.4.1 C11 导出 PII 扫描前置（必须由 C11 提供）

C11 Task 4 的 `services/export_policy.py` 是唯一 PII 扫描器，冻结以下精确接口。C10 不得定义自己的 `PiiHit` 类型、正则、词表或第二套扫描规则；`services/delivery/types.py` 只从 C11 导入 `PiiHit` 并在需要处重导出。

```python
EXPORT_POLICY_VERSION: Final[str] = "export_policy.v1"
# PiiHit 由 C11 export_policy 定义；字段固定为 kind / field_path / start / end，
# kind 只取 contact / profile_link / avatar / tracking。C10 不定义该类。
def scan_export_policy(
    text: str, field_path: str = "$"
) -> tuple[PiiHit, ...]: ...
def scan_export_value(
    value: object, field_path: str = "$"
) -> tuple[PiiHit, ...]: ...
```

规则：

- `scan_export_policy` 扫描单段文本；`scan_export_value` 递归扫描映射、列表与 URL 字符串。规则、正则与遮蔽常量全部归 C11；C10 不得复制 `CONTACT_PATTERN`、`URL_PATTERN`、`PROFILE_HOSTS`、`HANDLE_FIELD_PATTERN` 或自造豁免表。
- `contact` 匹配必须跳过 UUID（带连字符与 32 位无连字符）与 ISO-8601 时间戳，不得把 `contract_id`、`task_id`、`evidence_id`、`generated_at` 误报为电话。
- 返回空 tuple 表示未命中；`PiiHit` 只含 kind、字段路径与偏移，不回传原始值。
- 两个函数都是只读纯函数，不写库、不读时钟、不联网。
- C10 的 `services/delivery/pii.py` 只编排字段路径：manifest、公开合同与 Claim bundle 交给 `scan_export_value`；渲染出的 HTML、CSV、JSON、Markdown 文本逐文件交给 `scan_export_policy`。

C10 的 `test_c10_contract_registration.py` 必须断言 `EXPORT_POLICY_VERSION == "export_policy.v1"`、`fields(PiiHit)` 为 `kind/field_path/start/end`、`callable(scan_export_policy)` 与 `callable(scan_export_value)`，并用含邮箱的字符串和嵌套映射断言 `kind == "contact"`、`field_path` 被保留，且 `repr(hit)` 不含原始邮箱。C11 未提供时，C10 停止，不得在 C10 内实现扫描器。

#### 0.4.2 C4 任务单读取前置（已存在，不新增）

Quick 2 小时稿需要判定 `package_type`。C10 只读 C4 的 `repositories.workbench_tasks.get_workbench_task(session, *, workspace_id, task_id, project_id=None)`，不写 `workbench_tasks`，不新增 `package_type` 副本。该函数已由 C4 Task 7 提供；若签名漂移，C10 停止并回到 C4 统一。

### 0.5 GitNexus 影响基线（强制）

在 C10 worktree 中先刷新索引并记录影响面。以下结果在 `feat/gov-c9` 上实测：

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs analyze --index-only
node .gitnexus/run.cjs status
```

预期：索引提交等于 `git rev-parse feat/gov-c9^{commit}`、`状态: ✅ 已是最新`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs impact "canonical_json_bytes" --direction upstream \
  -f apps/api/src/data_intelligence_hub/schemas/report_contract.py --summary-only
node .gitnexus/run.cjs impact "ReportAuditEvent" --direction upstream --summary-only
node .gitnexus/run.cjs impact "ReportArtifact" --direction upstream --summary-only
node .gitnexus/run.cjs impact "build_artifact" --direction upstream --summary-only
node .gitnexus/run.cjs impact "verify_artifact" --direction upstream --summary-only
```

| 符号 | 影响数 | 风险 | C10 动作 |
|---|---:|---|---|
| `canonical_json_bytes` | 50 | **HIGH** | 不修改。只在 C1 冻结 profile，C10 调用。改它会使全部合同哈希漂移。 |
| `ReportAuditEvent` | 16 | MEDIUM | C9 的 065 已加 `artifact_id`、放宽 `report_id`；C10 不修改，只读。必须跑全部报告/审计测试。 |
| `ReportArtifact` | 8 | LOW | 只加带默认值的列与新约束。 |
| `build_artifact` | 2 | LOW | 不修改。 |
| `verify_artifact` | 2 | LOW | 不修改，C10 直接调用。 |
| `contract_sha256` | 7 | MEDIUM | 不修改。 |

`canonical_json_bytes` 的 `risk: HIGH` 是本计划不切 RFC 8785 的直接证据。任何 HIGH/CRITICAL 警告不得用 `riskSharedAxes` 豁免。

提交前必须再跑：

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

预期 `partial: false`、`truncated: false`。`partial: true` 或 `truncated: true` 视为未检查，不得提交。

### 0.6 明确不做

- 不实现隐私保留、DSR、删除证明或 PII 正则；这些归 C11 与 C12。C10 只调用 C11 的 `scan_export_policy()` / `scan_export_value()`，不复制规则，也不定义 `PiiHit`。
- 不做 MCP 工具、客户 MCP、`tools/list` 投影。
- 不做匿名公开分享、`report_shares` 表、分享令牌；Quick 2 小时稿也不得公开分享。
- 不做前端页面；C10 只提供 API 与文件。
- 不做 LLM 翻译或生成；所有交付文件是确定性渲染。
- 不建第二套报告表、Claim 表、交付账本表、验收表或门禁表。
- 不把 Quick 2 小时稿做成 Standard 正式交付：不审核、不生成四态、不出现 `confirmed`、不启动验收、不重复计费。
- 不修改 C7 的 Claim 审核、C8 的质量判定或 C9 的报告装配；C10 只消费它们的事实。

### 0.7 决策 D-C10-03：C2 项目 ACL、审阅者指派接缝与统一审计投影

**选择：所有交付与验收端点全部走 C2 的 `require_project_access_audited`，审阅者校验只认 C9 的 `report_reviewer_assignments` active 行，交付事件额外投影到 C2 的统一审计。**

C10 不实现第二套授权，也不实现第二张审计表。

1. **项目 ACL 是唯一接缝。** 路由先按 `workspace_id + artifact_id` 取产物（跨工作区取不到，返回 404，不泄露项目是否存在），再调用 C2 的 `require_project_access_audited`：
   - `POST /api/reports/{artifact_id}/delivery/publish`：`manage=True`。发布同时写入验收快照，属于项目级写。
   - `GET /api/reports/{artifact_id}/delivery`：`manage=False`。ZIP 含验收快照，属于项目级读。
   - `GET /api/reports/{artifact_id}/delivery/manifest`：`manage=False`。
   - `POST /api/reports/{artifact_id}/delivery/quick-draft`：`manage=True`；`GET .../quick-draft`：`manage=False`。
   - `GET /api/tasks/{task_id}/delivery/quick-draft`：`manage=False`，先由 C4 任务单解析 `project_id`。
   - `GET /api/reports/{artifact_id}/delivery/acceptance`：`manage=False`；accept/dispute/deemed-accepted：`manage=True`。
   - 判定矩阵：`owner`、`admin` 直接通过；同工作区、已在 `project_members` 的 `member` 可读，`manage=True` 返回 403 `project_management_forbidden`；同工作区、无 `project_members` 行返回 403 `project_access_forbidden`（读与写都一样，C2 先判成员行再判 manage）；跨工作区项目返回 404 `project_not_found`；产物跨工作区在 ACL 之前就返回 404 `delivery_not_found`。
   - 不新增 `DELIVERY_REQUIRE_PROJECT_ACL` 之类开关；`WORKSPACE_RBAC_ENFORCED` 由 C2 解释，C10 只调用。
2. **审阅者校验用指派接缝。** `validate_review_signoff` 不再拿 `workspace_members.role` 当审阅者授权。内部审阅者不是客户角色（C9 约定 `workspace_members.role` 只有 `owner/admin/member`），唯一事实源是 `report_reviewer_assignments` 的 active 行：`reviewer_user_id` 命中、`assignment_scope='report_review'`、`project_id` 等于产物项目、`expires_at > now`。C10 只读，使用 C2 的只读仓储 `repositories.report_reviewers.get_active_reviewer_assignment`，不写表、不导入 C9 的 ORM 模型。
3. **统一审计只投影，不新增动作。** C2 的 `AUDIT_ACTION_OWNERS` / `AUDIT_ACTIONS` 是唯一注册表；C1 必须登记同一批名称。C10 允许的五个动作固定为：

   | 交付事实 | `audit_events.action` | `result` |
   |---|---|---|
   | 发布成功（含验收快照追加） | `delivery.published` | `success` |
   | 发布被 G-Claim/G-Publish 阻断 | `delivery.published` | `denied` |
   | manifest 读取 | `delivery.projection.viewed` | `success` |
   | ZIP 下载成功 | `delivery.downloaded` | `success` |
   | 篡改或完整性失败 | `delivery.tamper_detected` | `failed` |
   | 旧交付被取代 | `delivery.superseded` | `success` |

   `acceptance_snapshot_appended`、`gate_evaluated` 与 `acceptance_*` **不单独写统一审计**：注册表没有对应动作，C10 不自造 `delivery.acceptance.appended`、`delivery.acceptance.accepted` 或 `delivery.gate.evaluated`。验收事实只写 `report_audit_events`；PII 阻断投影到 `delivery.published/denied`。`report_audit_events` 仍是交付领域事件日志，两套写入在同一事务内完成；拒绝审计由 C2 的 `require_project_access_audited` 负责（`project.access.denied` / `project.management.denied`），C10 不重复写。任何未登记的 action 必须让测试失败，不得静默降级。

### 0.8 决策 D-C10-04：Quick 2 小时方向稿与 24 小时正式交付分离

**选择：同一 `task_id` 下两条交付路径，共享数据与 Claim 建议，不共享验收时钟。**

1. **Quick 2 小时稿只对 `package_type='quick'` 开放。** Standard 任务调用 `POST /delivery/quick-draft` 返回 422 `quick_draft_not_allowed`。Quick 任务的 24 小时正式版仍走 `POST /delivery/publish`。
2. **Quick 稿不审核。** 不读取、不要求 `report_review_approved`；`G-Publish` 的 Quick 分支跳过签字校验，并在 `delivery_published` 事件中记录 `reviewed=False`。正式 24 小时交付仍要求签字，缺签字返回 409。
3. **Quick 稿不启动验收。** `acceptance_deadline` 为空，不写 `acceptance_snapshot_appended`，不投影任何 `acceptance_*` 事件；验收端点在 Quick 稿上返回 409 `acceptance_not_applicable`。
4. **Quick 稿不生成 Standard 四态、不得出现 `confirmed`。** G-Claim Quick 分支必须调用 C7 `validate_claim_semantics(bundle, markets=contract["markets"], package_type="quick")`；`markets[].conclusion_standard` 必须为 null，任何 `confirmed` Claim 返回 422 `quick_draft_claim_invalid`。
5. **Quick 稿不重复计费。** C10 不写 `run_ledger_entries`、不建 `runs`、不建新数据集版本；Quick 稿复用同一 `task_id` 的既有数据集版本与 `run_ledger` 快照。测试断言 `run_ledger_entries` 与 `dataset_versions` 行数在 Quick 稿发布前后不变。
6. **Quick 稿仍受 PII 扫描约束。** 与正式交付相同，命中 PII 返回 409 `delivery_pii_detected`，发布被阻断并写审计。

### 0.9 决策 D-C10-05：验收只追加事件，manifest 不可变

**选择：验收结果写入 `report_audit_events`，不修改 manifest、交付文件或 `report_artifacts.acceptance_snapshot_json`。**

1. **三种终态事件。** `acceptance_accepted`、`acceptance_disputed`、`acceptance_deemed_accepted` 只追加，不更新、不删除。派生状态使用 C1 `$defs/acceptance.status`：`accepted`、`objection`、`auto_accepted`。
2. **争议必须逐项引用。** `acceptance_disputed` 的 `references` 至少 1 项，每项含 `path`（必须命中 manifest 文件）、可选 `claim_id` / `evidence_id` / `item_id`、必填 `description`。未知路径或未知条目返回 422 `acceptance_reference_invalid`。
3. **视为验收只能逾期触发。** `POST /acceptance/deemed-accepted` 仅在 `now > acceptance_deadline` 且当前无终态事件时允许；否则 409 `acceptance_window_open` 或 `acceptance_already_closed`。`sweep_deemed_acceptances()` 使用稳定幂等键 `deemed:{artifact_id}`。
4. **显式幂等键。** 三个验收 POST 都要求 `Idempotency-Key`。`metadata_json.idempotency_key_hash = sha256("delivery-acceptance.v1:{idempotency_key}")`；`payload_sha256 = sha256(canonical_json_bytes(payload))`，payload 只含 `event_type`、`artifact_id`、`references` 与可选 `note`（`note` 为空时省略），canonical profile 为 `dih-canonical-json-v1`。同一产物、同一 key、同一事件类型与同一 `payload_sha256` 返回 200 replay；同 key 不同 payload 或不同事件类型返回 409 `idempotency_conflict`。
5. **manifest 不可变。** 验收事件只写事件日志与 C2 统一审计投影；测试在验收前后重算 `manifest_sha256` 与 `store.verify_bundle()`，必须完全一致。

### 0.10 决策 D-C10-06：发布前复用 C11 PII 扫描

**选择：C10 只做扫描接缝与阻断，不实现 PII 规则。**

1. **扫描范围。** `scan_delivery_inputs` 只编排字段路径：manifest payload、公开合同投影与 C7 Claim bundle 交给 C11 `scan_export_value(value, field_path=...)`；全部 bundle 文本文件（两页 HTML、CSV、JSON、Markdown）逐文件交给 C11 `scan_export_policy(text, field_path=...)`。C10 不递归、不复制正则，也不定义第二套命中类型。
2. **命中即阻断。** 正式与 Quick 发布都在写 bundle 之前扫描；非空 `tuple[PiiHit, ...]` 抛 `DeliveryPiiError`，HTTP 409 `delivery_pii_detected`。不写 bundle、不置 `delivered_*` 字段。
3. **审计。** 写 `report_audit_events` 的 `gate_evaluated`（G-Publish，finding code `delivery_pii_detected`）与 C2 `delivery.published`（`result=denied`）；只记录 `code`（即 `PiiHit.kind`）、`field_path`、`export_policy_version`，不记录原始值或掩码预览。
4. **下载复核。** 下载只复核 manifest 与文件哈希，防止发布后注入；PII 已在发布时阻断。若后续增加下载时 PII 扫描，必须复用同一 `scan_export_policy()` / `scan_export_value()`，并写 `delivery_pii_detected` 领域事件与 C2 `delivery.tamper_detected`（`result=failed`，`details.reason="pii_detected"`）。C2 注册表没有 `delivery.pii.*` 动作，C10 不自造动作名。

## Global Constraints

- **开关与回滚。** 本切片不新增布尔开关，入口受 `GOVERNED_TASK_PLATFORM_ENABLED` 控制；回滚点是迁移 `066` 的 `downgrade` 与发布前数据库备份，生产回滚用备份恢复或新迁移，不手改 `alembic_version`。
- **统一发布门禁。** 本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；先备份，A 先 canary，B 只在目标授权、备份与迁移门禁通过后发布；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。C10 不修改该 compose；任一步失败记 `BLOCKED`。
- 基线：前置分支 `feat/gov-c9`，schema head `202610220065`。不重写报告/Claim 事实源。
- 契约优先：C1 必须先完成第 0.4 节登记；C10 的预检测试失败时停止，不改测试绕过。
- 迁移：只有 `apps/api/alembic/versions/202610220066_delivery_manifest_publish.py` 一个。`down_revision = "202610220065"`。
- Canonical profile：`dih-canonical-json-v1`，实现只调用 `schemas.report_contract.canonical_json_bytes`。不复制序列化器。
- 哈希：SHA-256，64 位小写十六进制。文件哈希对精确字节计算；manifest 哈希对 canonical bytes 计算。
- Sidecar 格式：`<manifest_sha256>  delivery_manifest.json\n`，UTF-8/ASCII 单行。
- 交付文件只允许相对 POSIX 路径；禁止绝对路径、`..`、反斜杠、符号链接。
- 公开投影使用白名单，不把 `provider`、`provider_id`、`endpoint_type`、`source_tool_id`、`unit_price`、`authorization_id`、`actor_id`、`approver`、`owner`、`run_ledger` 写入任何公开文件。
- **manifest 只有 C1 的 1.1 形状。** 顶层键固定为 `schema_version`、`manifest_id`、`task_id`、`report_artifact_id`、`report_version`（整数）、`created_at`、`files`、`bundle_sha256`、`sidecar_sha256`、`access_scope`、`retention_class`。`files[]` 只有 `path`、`sha256`、`size_bytes`、`media_type`。不得输出 `manifest_version`、`artifact_id`、`content_files_digest` 或 `role`；`DeliveryFile.role` 只在内存投影前用于完整性校验。
- **审核主体只来自 C1/C2。** C10 只读 `report_reviewer_assignments` 的 active 行；`ReviewSignoff.reviewer_role` 必须是 `internal_reviewer`。客户 `owner/admin` 自审、报告创建人自审、无 active assignment 一律拒绝。C10 不把 `workspace_members.role` 当审核角色。
- **唯一禁用语言画像。** C10 只 import C1 的 `FORBIDDEN_LANGUAGE_PROFILE_ID` 与 `scan_forbidden_language()`。交付前扫描原始合同；命中返回 `delivery_input_invalid`，并附同一 `profile_id`。C10 不定义第二份词表。
- **合同版本推进归 C9。** C10 不原地改 `contract_json`。发布交付时调用 C9 `create_delivery_contract_version` 创建下一个 `report_version` 并发布；C10 只写新产物的交付列与 manifest 文件。
- 事件只追加。`report_audit_events` 不得更新或删除；manifest 与交付文件发布后不得覆盖。
- **项目 ACL。** 三个交付端点先按工作区取产物，再调用 C2 `api.authz.require_project_access_audited`。写 `manage=True`，读 `manage=False`。不新增 ACL 开关，不按 `workspace_members.role` 自行放行。
- **统一审计。** 只调用 C2 `services.audit_log.append_audit_event`；动作必须来自 C2 `AUDIT_ACTIONS`，C10 只允许 0.7 表中的五个。验收事实只写 `report_audit_events`；门禁与 PII 阻断作为 `delivery.published.details` 的子对象投影。不得自造动作名，不得新增审计表。
- **审阅者授权。** 只认 `report_reviewer_assignments` 的 active 行与 `assignment_scope='report_review'`；`workspace_members.role` 不是审阅者授权，也不得新增 `reviewer` 角色。
- **合同 fixture 只有 1.1 29 键。** 所有 `ReportContract` 测试夹具必须来自 `apps/api/tests/fixtures/report_contract_v1_1.py` 的 `build_report_contract()`；顶层 29 个必填键一个不少，`schema_version="1.1.0"`，时间戳使用 `Z` 后缀，`additionalProperties=false` 的分组不得夹带 `answer_en`、`actor_id` 等未登记键。夹具必须通过 `ReportContract.model_validate()` 与 C1 `validate_contract()`。
- **G-Claim 只消费 C7 publishable bundle。** `load_claim_snapshot()` 必须调用 C7 `load_publishable_claim_rows()`；`evaluate_g_claim()` 必须调用 `validate_claim_bundle()`。合同引用的 Claim 若在数据库中为 `pending`、`draft`、`rejected` 或 `stale`，返回 `claim_review_pending` / `claim_not_approved` / `claim_review_stale` 并阻断；不得用合同文本绕过审核状态。
- **Quick 2 小时稿。** 只允许 `package_type='quick'`；不要求审核签字，不启动验收，`delivery_class='quick_draft'`，`acceptance_deadline IS NULL`，不写 `acceptance_snapshot_appended`。G-Claim 必须调用 C7 `validate_claim_semantics(..., package_type="quick")`，拒绝 Standard 四态与 `confirmed`。复用同一 `task_id` 的数据集与 `run_ledger`，不写 `runs`、`run_ledger_entries` 或新数据集版本。
- **验收只追加。** accepted / disputed / deemed_accepted 写入 `report_audit_events`，不修改 manifest、bundle、`acceptance_snapshot_json`。三个 POST 都要求 `Idempotency-Key`；同 key 同 payload 返回 replay，同 key 不同 payload 返回 409 `idempotency_conflict`。争议必须有逐项引用。幂等键哈希固定为 `sha256("delivery-acceptance.v1:{idempotency_key}")`；payload 摘要只覆盖 `event_type`、`artifact_id`、`references` 与可选 `note`，不覆盖 deadline 或原始 key。
- **PII 扫描。** 只调用 C11 `export_policy` 的 `scan_export_value()` 与 `scan_export_policy()`；正式与 Quick 发布都必须在写 bundle 前扫描 manifest、公开合同、Claim bundle、bundle 文本文件与 HTML。命中返回 409 `delivery_pii_detected`，写 `gate_evaluated` 与 C2 `delivery.published/denied`；审计只记录 `kind` 与 `field_path`，不记录原始值。C10 不定义 `PiiHit`，不复制规则。
- 验收窗口：5 个工作日，周一至周五，不含法定节假日；截止时间为第 5 个工作日 23:59:59 UTC。
- 幂等：publish 使用 `Idempotency-Key` 请求头；只存 SHA-256，不存明文，不写日志。
- 不调用模型、网络、时钟以外的外部服务。时间由调用方传入或使用 `datetime.now(UTC)`。
- 测试命令：`cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q <paths>`。
- 静态检查：`uv run ruff check <changed-paths>`、`uv run mypy <changed-paths>`。
- 每个任务一个 commit，commit message 用 `feat(delivery): ...` / `test(delivery): ...` / `chore(delivery): ...`。
- 提交前必须跑 GitNexus `detect-changes`；HIGH/CRITICAL 风险不得忽略。

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `apps/api/alembic/versions/202610220066_delivery_manifest_publish.py` | 新建 | 唯一迁移：交付列、交付约束与索引；不扩展 `report_audit_events`。 |
| `apps/api/src/data_intelligence_hub/models/report_artifact.py` | 修改 | 只加 `delivery_*` 与封存字段；`status`/`published_*` 由 C9 拥有。 |
| `apps/api/src/data_intelligence_hub/repositories/delivery.py` | 新建 | 交付专用只读/追加查询；事务提交权在 service。 |
| `apps/api/src/data_intelligence_hub/services/delivery/__init__.py` | 新建 | 导出跨任务接口。 |
| `apps/api/src/data_intelligence_hub/services/delivery/canonical.py` | 新建 | profile 常量、SHA-256 与 canonical 包装。 |
| `apps/api/src/data_intelligence_hub/services/delivery/types.py` | 新建 | 文件、门禁、签字、快照、manifest 数据类型；只重导出 C11 `PiiHit`，不定义该类。 |
| `apps/api/src/data_intelligence_hub/services/delivery/projection.py` | 新建 | 公开合同投影白名单。 |
| `apps/api/src/data_intelligence_hub/services/delivery/renderers.py` | 新建 | 正式 10 个交付文件与 Quick 方向稿通知的确定性渲染。 |
| `apps/api/src/data_intelligence_hub/services/delivery/review.py` | 新建 | 读取并校验 C9 的 `report_review_approved` 事件与指派接缝。 |
| `apps/api/src/data_intelligence_hub/services/delivery/gates.py` | 新建 | G-Claim（C7 publishable bundle）与 G-Publish 求值。 |
| `apps/api/src/data_intelligence_hub/services/delivery/pii.py` | 新建 | 调用 C11 `scan_export_value()`（manifest/公开合同/Claim bundle）与 `scan_export_policy()`（HTML 与文本文件），只编排字段路径。 |
| `apps/api/src/data_intelligence_hub/services/delivery/acceptance.py` | 新建 | 验收事件追加、幂等、逐项争议引用与 deemed 判定。 |
| `apps/api/src/data_intelligence_hub/services/delivery/quick.py` | 新建 | Quick 2 小时方向稿的 package_type 校验、文件集与无验收约束。 |
| `apps/api/src/data_intelligence_hub/services/delivery/audit.py` | 新建 | 交付事件到 C2 `append_audit_event` 的唯一投影；动作映射白名单。 |
| `apps/api/src/data_intelligence_hub/services/delivery/manifest.py` | 新建 | manifest、sidecar、路径与角色校验。 |
| `apps/api/src/data_intelligence_hub/services/delivery/store.py` | 新建 | 本地原子写、目录遍历、篡改检测、ZIP。 |
| `apps/api/src/data_intelligence_hub/services/delivery/service.py` | 新建 | publish、Quick publish、验收、幂等、supersede、下载审计。 |
| `apps/api/src/data_intelligence_hub/schemas/delivery.py` | 新建 | 请求/响应模型，含验收与 Quick 稿。 |
| `apps/api/src/data_intelligence_hub/api/routes/delivery.py` | 新建 | publish、Quick 稿、manifest、download、验收端点。 |
| `apps/api/src/data_intelligence_hub/main.py` | 修改 | 挂载 delivery router。 |
| `apps/api/src/data_intelligence_hub/core/config.py` | 修改 | `delivery_export_dir`。 |
| `apps/api/.env.example` | 修改 | `DELIVERY_EXPORT_DIR`。 |
| `configs/deploy/scrapy/docker-compose.yml` | PG0 发布批次交接 | 生产 A/B 共用 compose；PG0 发布批次加入 `DELIVERY_EXPORT_DIR`，C10 不修改，C14 只读验收。 |
| `docs/operations/delivery-publish.md` | 新建 | 发布、下载、校验、篡改处置手册。 |
| `apps/api/tests/unit/conftest.py` | 新建 | `session` 与 `delivery_seed` 共享夹具；含项目成员、无项目成员、跨工作区与审阅者指派行；Tasks 5/9/10 共用，不复制第二套 schema。 |
| `apps/api/tests/fixtures/report_contract_v1_1.py` | 新建 | C1 1.1 的 29 键 `ReportContract` 唯一夹具构造器；全部测试共用。 |
| `apps/api/tests/unit/test_c10_contract_registration.py` | 新建 | C1/C7/C8/C9/C11 前置与合同 marker。 |
| `apps/api/tests/postgres/test_delivery_migration.py` | 新建 | 065→066→065 PostgreSQL 迁移验收。 |
| `apps/api/tests/unit/test_delivery_canonical_profile.py` | 新建 | profile 字节级固定。 |
| `apps/api/tests/unit/test_delivery_projection.py` | 新建 | 公开投影白名单。 |
| `apps/api/tests/unit/test_delivery_renderers.py` | 新建 | 10 个文件精确输出。 |
| `apps/api/tests/unit/test_delivery_manifest.py` | 新建 | manifest、sidecar、路径与角色。 |
| `apps/api/tests/unit/test_delivery_review.py` | 新建 | 指派有效性、过期、撤销、自审与成员冒充。 |
| `apps/api/tests/unit/test_delivery_gates.py` | 新建 | G-Claim/G-Publish 通过与否决；C7 bundle 与 pending/stale 拒绝。 |
| `apps/api/tests/unit/test_delivery_pii.py` | 新建 | C11 扫描接缝、manifest/bundle/HTML/Claim 覆盖、发布阻断与审计。 |
| `apps/api/tests/unit/test_delivery_acceptance.py` | 新建 | accepted / disputed / deemed_accepted、逐项引用、`delivery-acceptance.v1` 幂等键派生、payload 摘要、replay/conflict 与 manifest 不可变。 |
| `apps/api/tests/unit/test_delivery_quick.py` | 新建 | Quick 2 小时稿、同任务、无验收、无四态/confirmed、无重复计费。 |
| `apps/api/tests/unit/test_delivery_audit.py` | 新建 | 动作注册表、发布/读取/下载/篡改/取代投影。 |
| `apps/api/tests/unit/test_delivery_store.py` | 新建 | 原子写、篡改、缺失、多余与符号链接。 |
| `apps/api/tests/unit/test_delivery_service.py` | 新建 | 发布、幂等、supersede、事件与篡改下载。 |
| `apps/api/tests/unit/test_delivery_routes.py` | 新建 | 201/200/403/404/409/ZIP；ACL 矩阵含同工作区跨项目与跨工作区。 |
| `apps/api/tests/unit/test_delivery_migration.py` | 新建 | 迁移 066 与模型列/约束。 |

## 跨任务接口

**执行顺序：** Task 1 → 2 → 3 → 4 → **8** → 5 → 6 → 7 → 9 → 10 → 11。Task 8 只提供 `report_artifacts.delivery_status`；`report_audit_events.artifact_id` 由 C9 的 065 提供。Task 5 的共享夹具依赖这两个字段。任务编号保持稳定，执行时按此顺序。

以下签名是任务之间的唯一接口。后续任务不得改名。

```python
# services/delivery/canonical.py
CANONICAL_PROFILE: Final[str]
def sha256_hex(data: bytes) -> str
def canonical_bytes(value: Mapping[str, Any]) -> bytes
def canonical_text(value: Mapping[str, Any]) -> str
def canonical_sha256(value: Mapping[str, Any]) -> str
def is_sha256(value: object) -> bool

# services/delivery/projection.py
def project_public_contract(
    contract: Mapping[str, Any],
    *,
    dataset: DatasetMetadata,
    source_contract_sha256: str,
) -> dict[str, Any]
def assert_no_forbidden_keys(value: object, *, path: str = "$") -> None
def assert_forbidden_language_free(contract: Mapping[str, Any]) -> None

# services/delivery/renderers.py
def build_dataset_input(version: object) -> DatasetInput
def render_dataset_csv(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes
def render_data_dictionary(dataset: DatasetInput) -> bytes
def render_claim_evidence_index(public_contract: Mapping[str, Any]) -> bytes
def render_run_receipt(contract: Mapping[str, Any]) -> bytes
def render_executive_summary_en(public_contract: Mapping[str, Any]) -> bytes
def render_quality_scorecard(contract: Mapping[str, Any]) -> bytes
def render_limits_and_gaps(public_contract: Mapping[str, Any]) -> bytes
def add_business_days(start: datetime, days: int) -> datetime
def render_acceptance_snapshot(
    *,
    artifact_id: uuid.UUID,
    contract_sha256: str,
    data_sha256: str,
    dataset: DatasetInput,
    content_bundle_sha256: str,
    delivered_at: datetime,
    acceptance_deadline: datetime,
    gate_status: Mapping[str, str],
) -> bytes
def render_quick_draft_notice(
    *,
    artifact_id: uuid.UUID,
    task_id: uuid.UUID,
    delivered_at: datetime,
    package_type: str,
) -> bytes

# services/delivery/review.py
ReviewerAssignment = Any  # C1/C2 的 report_reviewer_assignments active 行
async def load_latest_review_signoff(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> ReviewSignoff | None
async def validate_review_signoff(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    signoff: ReviewSignoff,
    artifact: ReportArtifact,
    claim_snapshot: ClaimSnapshot,
    assignment: ReviewerAssignment | None = None,
) -> list[GateFinding]

# services/delivery/gates.py
async def load_claim_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    contract: Mapping[str, Any],
) -> ClaimSnapshot
async def evaluate_g_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
    package_type: str = "standard",
) -> GateDecision
async def evaluate_g_publish(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
    g_claim: GateDecision,
    signoff: ReviewSignoff | None,
    dataset: DatasetInput,
    files: Sequence[DeliveryFile],
    manifest: DeliveryManifest,
    acceptance_snapshot: DeliveryFile | None,
    now: datetime,
    delivery_class: str = "formal",
    require_published: bool = True,
    pii_hits: Sequence[PiiHit] = (),
    signoff_artifact: ReportArtifact | None = None,
) -> GateDecision

# services/delivery/manifest.py
FORMAL_REQUIRED_ROLES: tuple[DeliveryFileRole, ...]
QUICK_DRAFT_REQUIRED_ROLES: tuple[DeliveryFileRole, ...]
MANIFEST_NAME: Final[str]
SIDECAR_NAME: Final[str]
def bundle_sha256(files: Sequence[DeliveryFile]) -> str
def content_bundle_sha256(files: Sequence[DeliveryFile]) -> str
def build_manifest(
    *,
    manifest_id: uuid.UUID,
    artifact_id: uuid.UUID,
    task_id: uuid.UUID,
    report_version: int,
    files: Sequence[DeliveryFile],
    access_scope: Sequence[str],
    retention_class: str,
    created_at: datetime,
    required_roles: Sequence[DeliveryFileRole] = FORMAL_REQUIRED_ROLES,
) -> DeliveryManifest
def verify_manifest_file(
    manifest_bytes: bytes,
    *,
    expected_sha256: str,
    sidecar_bytes: bytes,
) -> list[BundleMismatch]

# services/delivery/store.py
class DeliveryStore:
    def __init__(self, root: str | Path) -> None
    def bundle_dir(self, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Path
    def write_bundle(
        self,
        *,
        workspace_id: uuid.UUID,
        artifact_id: uuid.UUID,
        files: Sequence[DeliveryFile],
        manifest: DeliveryManifest,
    ) -> Path
    def verify_bundle(
        self,
        *,
        workspace_id: uuid.UUID,
        artifact_id: uuid.UUID,
        manifest: DeliveryManifest,
        expected_manifest_sha256: str,
        expected_sidecar_sha256: str,
    ) -> list[BundleMismatch]
    def build_zip(self, *, workspace_id: uuid.UUID, artifact_id: uuid.UUID, manifest: DeliveryManifest) -> bytes
    def remove_bundle(self, *, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> None

# services/delivery/service.py
async def publish_delivery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    idempotency_key: str,
    delivered_by: uuid.UUID,
    supersedes_artifact_id: uuid.UUID | None,
    store: DeliveryStore,
    now: datetime | None = None,
) -> PublishResult
async def publish_quick_draft(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    idempotency_key: str,
    delivered_by: uuid.UUID,
    store: DeliveryStore,
    now: datetime | None = None,
) -> PublishResult
async def load_delivery_manifest(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    store: DeliveryStore,
    verify_bundle: bool = True,
) -> DeliveryManifest
async def open_delivery_zip(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    store: DeliveryStore,
) -> tuple[bytes, str]
async def record_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: Literal["accept", "dispute"],
    idempotency_key: str,
    references: Sequence[DisputeReference] = (),
    note: str | None = None,
    now: datetime | None = None,
) -> AcceptanceResult
async def record_deemed_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    idempotency_key: str,
    now: datetime | None = None,
) -> AcceptanceResult
async def load_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> AcceptanceState
async def sweep_deemed_acceptances(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    now: datetime,
) -> list[AcceptanceResult]

# services/delivery/pii.py
# 返回值 PiiHit 来自 C11 services.export_policy；C10 不定义该类型。
def scan_delivery_inputs(
    *,
    manifest: DeliveryManifest,
    files: Sequence[DeliveryFile],
    public_contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
) -> tuple[PiiHit, ...]

# services/delivery/acceptance.py
def acceptance_status_from_events(events: Sequence[AcceptanceEvent]) -> str
def is_deemed_acceptance_due(deadline: datetime, now: datetime) -> bool
def validate_dispute_references(
    references: Sequence[DisputeReference],
    *,
    manifest: DeliveryManifest,
    public_contract: Mapping[str, Any],
) -> list[str]

# services/delivery/quick.py
def assert_quick_package(package_type: str) -> None
def assert_quick_contract(contract: Mapping[str, Any]) -> None
def quick_draft_files(
    *,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    public_contract: Mapping[str, Any],
    dataset: DatasetInput,
    delivered_at: datetime,
) -> tuple[DeliveryFile, ...]
```

---


### Task 0: 创建隔离 worktree 并验证 C9 前置

**Files:**
- Create: `/Users/lute/Project/data_scrapy-gov-c10`（隔离 worktree，不提交）
- Copy: `docs/superpowers/plans/2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md`

**Interfaces:**
- Consumes: `feat/gov-c9`、迁移 head `202610220065`、C1 registry。
- Produces: `feat/gov-c10` 与后续任务唯一命令根 `/Users/lute/Project/data_scrapy-gov-c10`。

- [ ] **Step 0: 创建 worktree 并安装依赖**

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c9^{commit}
test -z "$(git branch --list feat/gov-c10)"
test ! -e /Users/lute/Project/data_scrapy-gov-c10
git worktree add /Users/lute/Project/data_scrapy-gov-c10 -b feat/gov-c10 feat/gov-c9
cp docs/superpowers/plans/2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md \
  /Users/lute/Project/data_scrapy-gov-c10/docs/superpowers/plans/
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api
uv sync --locked --dev
cd /Users/lute/Project/data_scrapy-gov-c10
git merge-base --is-ancestor feat/gov-c9 HEAD && echo C9_BRANCH_BASE_OK
uv run --directory apps/api alembic heads
git status --short
```

Expected: branch/worktree creation succeeds; output contains `C9_BRANCH_BASE_OK`; Alembic shows only `202610220065 (head)`; status contains only the copied C10 plan. Existing branch/path means stop and inspect; do not delete or reuse blindly.

---

### Task 1: 合同登记、canonical profile 与 C11 PII 扫描守卫

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/services/delivery/canonical.py`
- Test: `apps/api/tests/unit/test_c10_contract_registration.py`
- Test: `apps/api/tests/unit/test_delivery_canonical_profile.py`

**Interfaces:**
- Consumes: C1 `CANONICAL_PROFILE_ID` / `canonical_json_bytes` / `ReportContract` / `validate_contract`；C11 `EXPORT_POLICY_VERSION` / `PiiHit` / `scan_export_policy` / `scan_export_value`。
- Produces: `CANONICAL_PROFILE`、`sha256_hex`、`canonical_bytes`、`canonical_text`、`canonical_sha256`、`is_sha256`。

- [ ] **Step 1: 写 C1/C7/C8/C9/C11 前置测试**

```python
# apps/api/tests/unit/test_c10_contract_registration.py
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[4]
    / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
)

REQUIRED_MARKERS = (
    "dih-canonical-json-v1",
    "dih-public-report-contract-v1",
    "delivery_status",
    "delivery_class",
    "formal · quick_draft",
    "manifest_sha256",
    "manifest_sidecar_sha256",
    "public_contract_json",
    "acceptance_snapshot_json",
    "acceptance_deadline",
    "quick_draft_of_artifact_id",
    "publish_idempotency_key_hash",
    "delivered_at",
    "delivered_by",
    "supersedes_delivery_id",
    "pending · delivered · superseded",
    "gate_evaluated",
    "report_review_approved",
    "report_reviewer_assignments",
    "internal_reviewer",
    "reviewer_assignment_required",
    "reviewer_self_review_forbidden",
    "reviewer_assignment_expired",
    "publish_forbidden",
    "delivery_not_publishable",
    "delivery_input_invalid",
    "delivery_pii_detected",
    "idempotency_key_required",
    "idempotency_conflict",
    "quick_draft_not_allowed",
    "quick_draft_claim_invalid",
    "acceptance_window_open",
    "acceptance_already_closed",
    "acceptance_reference_invalid",
    "acceptance_not_applicable",
    "delivery-manifest.v1",
    "report_shares",
    "delivery_published",
    "delivery_downloaded",
    "delivery_tamper_detected",
    "acceptance_snapshot_appended",
    "acceptance_accepted",
    "acceptance_disputed",
    "acceptance_deemed_accepted",
    "delivery_superseded",
    "POST /api/reports/{artifact_id}/delivery/publish",
    "GET /api/reports/{artifact_id}/delivery",
    "GET /api/reports/{artifact_id}/delivery/manifest",
    "POST /api/reports/{artifact_id}/delivery/quick-draft",
    "GET /api/reports/{artifact_id}/delivery/quick-draft",
    "GET /api/tasks/{task_id}/delivery/quick-draft",
    "POST /api/reports/{artifact_id}/delivery/acceptance/accept",
    "POST /api/reports/{artifact_id}/delivery/acceptance/dispute",
    "POST /api/reports/{artifact_id}/delivery/acceptance/deemed-accepted",
    "GET /api/reports/{artifact_id}/delivery/acceptance",
    "reviewed_contract_sha256",
    "reviewed_data_sha256",
    "reviewed_report_html_sha256",
    "reviewed_sop_html_sha256",
    "reviewed_claim_digest",
    "延期",
    "bundle_sha256",
    "report_artifact_id",
    "retention_class",
    "dih-descriptive-language-v1",
    "report_forbidden_language",
    "reviewer_assignment_id",
    "scan_export_policy",
    "Quick 2 小时",
)


def test_c1_registers_c10_contract() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
    assert not missing, "C1 合同冻结尚未登记 C10 项：" + "、".join(missing)


def test_c7_c8_c9_entrypoints_exist() -> None:
    from data_intelligence_hub.models.claim import Claim, ClaimEvidence
    from data_intelligence_hub.models.data_gap import DataGap
    from data_intelligence_hub.models.market_assessment import MarketAssessment
    from data_intelligence_hub.models.report_artifact import ReportArtifact
    from data_intelligence_hub.schemas.report_contract import (
        ReportContract,
        canonical_json_bytes,
        contract_sha256,
    )
    from data_intelligence_hub.services.report_artifacts import verify_artifact
    from data_intelligence_hub.services.report_publication import claim_review_digest

    assert Claim.__tablename__ == "claims"
    assert ClaimEvidence.__tablename__ == "claim_evidence"
    assert DataGap.__tablename__ == "data_gaps"
    assert MarketAssessment.__tablename__ == "market_assessments"
    assert ReportArtifact.__tablename__ == "report_artifacts"
    assert ReportContract.__name__ == "ReportContract"
    assert callable(canonical_json_bytes)
    assert callable(contract_sha256)
    assert callable(verify_artifact)
    assert callable(claim_review_digest)


def test_c11_export_policy_pii_scanner_exists() -> None:
    from dataclasses import fields

    from data_intelligence_hub.services.export_policy import (
        EXPORT_POLICY_VERSION,
        PiiHit,
        scan_export_policy,
        scan_export_value,
    )

    assert EXPORT_POLICY_VERSION == "export_policy.v1"
    assert {field.name for field in fields(PiiHit)} == {
        "kind",
        "field_path",
        "start",
        "end",
    }
    assert callable(scan_export_policy)
    assert callable(scan_export_value)
    findings = scan_export_policy(
        "buyer@example.com", field_path="claims[0].text"
    )
    assert findings
    assert findings[0].kind == "contact"
    assert findings[0].field_path == "claims[0].text"
    assert "buyer@example.com" not in repr(findings[0])
    nested = scan_export_value(
        {"claims": [{"text": "buyer@example.com"}]}, field_path="claim_bundle"
    )
    assert [(hit.kind, hit.field_path) for hit in nested] == [
        ("contact", "claim_bundle.claims[0].text")
    ]
    assert all(isinstance(hit, PiiHit) for hit in nested)
```

- [ ] **Step 2: 运行前置测试，确认它先失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_c10_contract_registration.py -v
```

Expected: `FAILED ... AssertionError: C1 合同冻结尚未登记 C10 项：...`。把缺失清单交给 C1 负责人；C10 实施者不得直接改契约文档，也不得删除断言。C1 与 C11 完成第 0.4/0.4.1 节后重跑，必须 `3 passed`。

- [ ] **Step 3: 写 canonical profile 失败测试**

```python
# apps/api/tests/unit/test_delivery_canonical_profile.py
from decimal import Decimal

from data_intelligence_hub.services.delivery.canonical import (
    CANONICAL_PROFILE,
    canonical_sha256,
    canonical_text,
    is_sha256,
)


def test_profile_id_is_frozen() -> None:
    assert CANONICAL_PROFILE == "dih-canonical-json-v1"


def test_key_order_and_compact_separators() -> None:
    assert canonical_text({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_known_deviations_from_rfc8785_are_pinned() -> None:
    assert canonical_text({"x": 1e-07}) == '{"x":1e-07}'
    assert canonical_text({"x": -0.0}) == '{"x":-0.0}'
    assert canonical_text({"z": "😀", "a": ""}) == '{"a":"","z":"😀"}'


def test_decimal_and_timestamp_normalization() -> None:
    assert canonical_text({"x": Decimal("1.20")}) == '{"x":"1.20"}'
    assert canonical_text(
        {"generated_at": "2026-10-22T08:00:00+08:00"}
    ) == '{"generated_at":"2026-10-22T00:00:00Z"}'


def test_hash_is_stable_and_lowercase() -> None:
    left = {"b": [1, 2], "a": {"x": "中文"}}
    right = {"a": {"x": "中文"}, "b": [1, 2]}
    digest = canonical_sha256(left)
    assert digest == canonical_sha256(right)
    assert is_sha256(digest)
    assert digest == digest.lower()
```

- [ ] **Step 4: 运行测试，确认模块不存在**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_canonical_profile.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.services.delivery'`。

- [ ] **Step 5: 写最小实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/__init__.py
"""交付包、manifest 与发布门禁。"""
```

```python
# apps/api/src/data_intelligence_hub/services/delivery/canonical.py
"""C10 的 canonical JSON 入口。

profile 已在 C1 冻结为 dih-canonical-json-v1。
本模块不实现第二套序列化。它只包装 B5 的
``schemas.report_contract.canonical_json_bytes``。
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any, Final

from data_intelligence_hub.schemas.report_contract import (
    CANONICAL_PROFILE_ID,
    canonical_json_bytes,
)

CANONICAL_PROFILE: Final[str] = CANONICAL_PROFILE_ID
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_hex(data: bytes) -> str:
    """返回小写十六进制 SHA-256。"""
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """按冻结 profile 输出 canonical JSON 字节串。"""
    return canonical_json_bytes(value)


def canonical_text(value: Mapping[str, Any]) -> str:
    """按冻结 profile 输出 UTF-8 文本。"""
    return canonical_bytes(value).decode("utf-8")


def canonical_sha256(value: Mapping[str, Any]) -> str:
    """对 canonical JSON 字节串求 SHA-256。"""
    return sha256_hex(canonical_bytes(value))


def is_sha256(value: object) -> bool:
    """判断是否为 64 位小写十六进制 SHA-256。"""
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


__all__ = [
    "CANONICAL_PROFILE",
    "canonical_bytes",
    "canonical_sha256",
    "canonical_text",
    "is_sha256",
    "sha256_hex",
]
```

- [ ] **Step 6: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_c10_contract_registration.py tests/unit/test_delivery_canonical_profile.py -v
```

Expected: `... 8 passed`（3 个前置 + 5 个 profile）。若 C1 未登记或 C11 未提供 `EXPORT_POLICY_VERSION` / `PiiHit` / `scan_export_policy` / `scan_export_value`，停止本任务。

- [ ] **Step 7: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/canonical.py tests/unit/test_c10_contract_registration.py tests/unit/test_delivery_canonical_profile.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/canonical.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/__init__.py \
  apps/api/src/data_intelligence_hub/services/delivery/canonical.py \
  apps/api/tests/unit/test_c10_contract_registration.py \
  apps/api/tests/unit/test_delivery_canonical_profile.py
git commit -m "feat(delivery): freeze canonical profile and contract preflight"
```

---
### Task 2: 交付类型、C1 1.1 共享夹具与公开合同投影

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/types.py`
- Create: `apps/api/src/data_intelligence_hub/services/delivery/projection.py`
- Create: `apps/api/tests/fixtures/report_contract_v1_1.py`
- Test: `apps/api/tests/unit/test_delivery_projection.py`

**Interfaces:**
- Consumes: `canonical_sha256`、C1 `ReportContract` / `contract_sha256` / `validate_contract`；C11 `PiiHit`（仅在 `types.py` 重导出，不定义第二份）。
- Produces: `DeliveryFileRole`、`DeliveryStatus`、`DeliveryClass`、`DeliveryEventType`、`DatasetInput`、`DatasetMetadata`、`DeliveryFile`、`GateFinding`、`GateDecision`、`ReviewSignoff`、`ClaimSnapshotRow`、`ClaimSnapshot`、`DeliveryManifest`、`BundleMismatch`、`DisputeReference`、`AcceptanceEvent`、`AcceptanceState`、`AcceptanceResult`；`project_public_contract`、`assert_no_forbidden_keys`、`build_report_contract`。

- [ ] **Step 1: 写共享 1.1 夹具与公开投影失败测试**

所有 `ReportContract` 测试只调用这个构造器，不得再手写 29 键，也不得夹带 `answer_en`、`actor_id` 等 C1 未登记键。若 `apps/api/tests/fixtures/` 不是包，补一个空 `__init__.py`；不得改 pytest 的 import mode 绕过。

```python
# apps/api/tests/fixtures/report_contract_v1_1.py
"""C1 1.1.0 报告合同的唯一测试夹具构造器。"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    contract_sha256,
)

NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
TASK_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
OWNER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
CLAIM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EVIDENCE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
DATASET_VERSION_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
WINDOW = {"start": "2026-01-01", "end": "2026-03-01", "days": 60}


def build_market(*, quick: bool = False, market: str = "US") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "market": market,
        "market_role": "primary",
        "quality_status": "qualified_with_gap",
        "evidence_grade": "L3_live_single",
        "domains": [
            {"data_domain": "products", "status": "pass", "record_count": 120, "threshold": 50}
        ],
        "sample_counts": {"products": 120},
        "thresholds": {"products": 50},
        "gaps": [],
    }
    if quick:
        payload["conclusion_quick"] = "worth_validating"
    else:
        payload["conclusion_standard"] = "conditional_enter"
    return payload


def build_claim(
    *,
    claim_id: uuid.UUID = CLAIM_ID,
    owner_id: uuid.UUID = OWNER_ID,
    status: str = "directional",
    grade: str = "L3_live_single",
    review_status: str = "approved",
    evidence_ids: Sequence[uuid.UUID] = (EVIDENCE_ID,),
) -> dict[str, Any]:
    return {
        "claim_id": str(claim_id),
        "text": "需求一致但未确认。",
        "text_en": "Demand is consistent but not confirmed.",
        "claim_status": status,
        "evidence_grade": grade,
        "scope": {"market": "US", "window": dict(WINDOW), "sample_n": 120},
        "counterevidence_text": "未发现反证。",
        "owner": str(owner_id),
        "review_status": review_status,
        "independent_source_count": 1,
        "evidence_ids": [str(value) for value in evidence_ids],
    }


def build_evidence(
    *,
    evidence_id: uuid.UUID = EVIDENCE_ID,
    claim_id: uuid.UUID = CLAIM_ID,
    role: str = "support",
    source_tool_id: str = "tikhub_search",
) -> dict[str, Any]:
    return {
        "evidence_id": str(evidence_id),
        "claim_id": str(claim_id),
        "role": role,
        "raw_record_id": "33333333-3333-3333-3333-333333333333",
        "source_tool_id": source_tool_id,
        "url": "https://example.com/item",
        "excerpt": "公开摘要。",
        "captured_at": "2026-02-01T00:00:00Z",
        "market": "US",
        "locale": "en-US",
        "evidence_grade": "L3_live_single",
    }


def build_report_contract(
    *,
    task_id: uuid.UUID = TASK_ID,
    owner_id: uuid.UUID = OWNER_ID,
    claim_id: uuid.UUID = CLAIM_ID,
    evidence_id: uuid.UUID = EVIDENCE_ID,
    quick: bool = False,
    claim_status: str = "directional",
    claim_grade: str = "L3_live_single",
    report_version: int = 1,
    generated_at: str = "2026-10-22T00:00:00Z",
    review_status: str = "draft",
    acceptance_status: str = "pending",
    report_html_sha256: str = "a" * 64,
    sop_html_sha256: str = "b" * 64,
    claim_override: Mapping[str, Any] | None = None,
    market_override: Mapping[str, Any] | None = None,
    claims: Sequence[Mapping[str, Any]] | None = None,
    evidences: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """构造 29 键 1.1 合同；返回前已通过 Pydantic 与 canonical 哈希。"""
    market = build_market(quick=quick)
    if market_override:
        market.update(dict(market_override))
    claim = build_claim(
        claim_id=claim_id, owner_id=owner_id, status=claim_status, grade=claim_grade
    )
    if claim_override:
        claim.update(dict(claim_override))
    claim_rows = [dict(item) for item in claims] if claims is not None else [claim]
    evidence_rows = (
        [dict(item) for item in evidences]
        if evidences is not None
        else [build_evidence(evidence_id=evidence_id, claim_id=claim_id)]
    )
    contract: dict[str, Any] = {
        "schema_version": "1.1.0",
        "contract_id": str(uuid.uuid5(task_id, "contract")),
        "task_id": str(task_id),
        "order_id": str(task_id),
        "template_id": "t1_voc",
        "template_version": "1.0.0",
        "report_version": report_version,
        "generated_at": generated_at,
        "identity": {
            "task_id": str(task_id),
            "brand": "Example",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": dict(WINDOW),
        },
        "decision": {
            "decision_question": "Should we enter?",
            "answer": "Validate first.",
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [],
        "coverage": {
            "cells": [
                {
                    "source_tool_id": "tikhub_search",
                    "market": "US",
                    "window": dict(WINDOW),
                    "record_count": 120,
                    "frame_member_count": 120,
                    "status": "success",
                }
            ]
        },
        "markets": [market],
        "metrics": [],
        "claims": claim_rows,
        "evidences": evidence_rows,
        "sku_candidates": [],
        "datasets": [
            {
                "dataset_version_id": str(DATASET_VERSION_ID),
                "market": "US",
                "row_count": 120,
                "content_sha256": "d" * 64,
                "schema_hash": "e" * 64,
                "quality_status": "qualified_with_gap",
            }
        ],
        "scorecard": {
            "markets": [market],
            "minimum_evidence_grade": "L3_live_single",
            "claims": {
                "total": len(claim_rows),
                "by_status": {claim_status: len(claim_rows)},
                "by_grade": {claim_grade: len(claim_rows)},
                "independent_source_count": 1,
            },
        },
        "rights": {"sources": [{"source_tool_id": "tikhub_search", "rights_status": "cleared"}]},
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
        "run_ledger": [
            {
                "run_id": str(RUN_ID),
                "tool_id": "tikhub_search",
                "endpoint_type": "search",
                "unit": "request",
                "quantity": 1,
                "unit_price": 0.01,
                "total_cost_usd": 0.01,
                "authorization_id": None,
                "evidence_grade": "L3_live_single",
                "started_at": "2026-02-01T00:00:00Z",
                "finished_at": "2026-02-01T00:00:05Z",
                "outcome": "success",
            }
        ],
        "limits": ["不能推断长期复购。"],
        "unknowns": ["缺少线下渠道数据。"],
        "review": {
            "status": review_status,
            "reviewer_id": str(NIL_UUID),
            "reviewer_assignment_id": str(NIL_UUID),
            "reviewer_role": "internal_reviewer",
            "review_scope": [],
            "reviewed_at": "1970-01-01T00:00:00Z",
            "review_version": 1,
            "contract_sha256": "0" * 64,
        },
        "acceptance": {
            "status": acceptance_status,
            "window_start": "2026-10-22",
            "window_end": "2026-10-29",
        },
        "delivery": {
            "manifest_id": str(NIL_UUID),
            "report_artifact_id": str(NIL_UUID),
            "report_version": report_version,
            "access_scope": ["workspace_project"],
            "retention_class": "standard_24m",
        },
        "artifact": {
            "report_html_sha256": report_html_sha256,
            "sop_html_sha256": sop_html_sha256,
            "contract_sha256": "0" * 64,
        },
    }
    model = ReportContract.model_validate(contract)
    contract["artifact"]["contract_sha256"] = contract_sha256(model)
    return contract


def build_quick_report_contract(**overrides: Any) -> dict[str, Any]:
    """Quick 2 小时稿合同：无 Standard 四态、无 confirmed。"""
    return build_report_contract(quick=True, **overrides)
```

投影测试：

```python
# apps/api/tests/unit/test_delivery_projection.py
import uuid

from data_intelligence_hub.services.delivery.canonical import canonical_text
from data_intelligence_hub.services.delivery.projection import (
    assert_forbidden_language_free,
    assert_no_forbidden_keys,
    project_public_contract,
)
from data_intelligence_hub.services.delivery.types import DatasetMetadata
from tests.fixtures.report_contract_v1_1 import build_report_contract


def _contract() -> dict:
    return build_report_contract()


def _dataset() -> DatasetMetadata:
    return DatasetMetadata(
        version_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        sha256="d" * 64,
        row_count=120,
        media_type="text/csv; charset=utf-8",
    )


def test_projection_removes_internal_fields() -> None:
    public = project_public_contract(
        _contract(), dataset=_dataset(), source_contract_sha256="c" * 64
    )
    text = canonical_text(public)
    for forbidden in (
        "provider",
        "provider_id",
        "endpoint_type",
        "source_tool_id",
        "unit_price",
        "authorization_id",
        "actor_id",
        "approver",
        "owner",
        "run_ledger",
    ):
        assert forbidden not in text
    assert public["schema_version"] == "1.0.0-public"
    assert public["task_id"] == str(uuid.UUID("66666666-6666-6666-6666-666666666666"))
    assert public["public_projection"]["profile"] == "dih-public-report-contract-v1"
    assert public["evidences"][0]["source_ref"].startswith("src-")
    assert "owner" not in public["claims"][0]


def test_projection_carries_delivery_metadata() -> None:
    public = project_public_contract(
        _contract(), dataset=_dataset(), source_contract_sha256="c" * 64
    )
    assert public["delivery"] == {
        "dataset_version_id": "99999999-9999-9999-9999-999999999999",
        "dataset_sha256": "d" * 64,
        "dataset_row_count": 120,
        "dataset_media_type": "text/csv; charset=utf-8",
    }


def test_forbidden_language_uses_c1_single_profile() -> None:
    from data_intelligence_hub.schemas.report_contract import (
        FORBIDDEN_LANGUAGE_PROFILE_ID,
    )
    from data_intelligence_hub.services.delivery import projection

    assert projection.FORBIDDEN_LANGUAGE_PROFILE_ID == FORBIDDEN_LANGUAGE_PROFILE_ID
    contract = _contract()
    contract["decision"]["answer"] = "评论提升销量。"
    try:
        assert_forbidden_language_free(contract)
    except ValueError as exc:
        assert FORBIDDEN_LANGUAGE_PROFILE_ID in str(exc)
        assert "提升" in str(exc)
    else:
        raise AssertionError("命中禁用语言必须拒绝交付")


def test_forbidden_key_check_is_recursive() -> None:
    try:
        assert_no_forbidden_keys({"a": [{"provider": "x"}]}, path="$")
    except ValueError as exc:
        assert "$.a[0].provider" in str(exc)
    else:
        raise AssertionError("必须拒绝 forbidden key")


def test_report_contract_fixture_is_29_key_valid() -> None:
    from data_intelligence_hub.schemas.report_contract import (
        ReportContract,
        validate_contract,
    )

    contract = build_report_contract()
    assert len(contract) == 29
    model = ReportContract.model_validate(contract)
    assert validate_contract(model) == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_projection.py -v
```

Expected: `ModuleNotFoundError` 或 `ImportError: cannot import name 'project_public_contract'`。

- [ ] **Step 3: 写类型模块**

```python
# apps/api/src/data_intelligence_hub/services/delivery/types.py
"""C10 的纯数据类型。不读库、不联网、不读时钟。"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

# PiiHit 归 C11 export_policy；C10 只重导出，不定义第二份类型或扫描规则。
from data_intelligence_hub.services.export_policy import PiiHit as PiiHit


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    SUPERSEDED = "superseded"


class DeliveryClass(StrEnum):
    FORMAL = "formal"
    QUICK_DRAFT = "quick_draft"


class DeliveryFileRole(StrEnum):
    REPORT_ZH = "report_zh"
    EXECUTIVE_SUMMARY_EN = "executive_summary_en"
    DATASET = "dataset"
    DATA_DICTIONARY = "data_dictionary"
    QUALITY_SCORECARD = "quality_scorecard"
    CLAIM_EVIDENCE_INDEX = "claim_evidence_index"
    RUN_RECEIPT = "run_receipt"
    REPORT_CONTRACT = "report_contract"
    LIMITS_AND_GAPS = "limits_and_gaps"
    ACCEPTANCE_SNAPSHOT = "acceptance_snapshot"
    QUICK_DRAFT_NOTICE = "quick_draft_notice"


class DeliveryEventType(StrEnum):
    GATE_EVALUATED = "gate_evaluated"
    DELIVERY_PUBLISHED = "delivery_published"
    DELIVERY_DOWNLOADED = "delivery_downloaded"
    DELIVERY_TAMPER_DETECTED = "delivery_tamper_detected"
    DELIVERY_PII_DETECTED = "delivery_pii_detected"
    ACCEPTANCE_SNAPSHOT_APPENDED = "acceptance_snapshot_appended"
    DELIVERY_SUPERSEDED = "delivery_superseded"
    ACCEPTANCE_ACCEPTED = "acceptance_accepted"
    ACCEPTANCE_DISPUTED = "acceptance_disputed"
    ACCEPTANCE_DEEMED_ACCEPTED = "acceptance_deemed_accepted"


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    version_id: uuid.UUID
    sha256: str
    row_count: int
    media_type: str


@dataclass(frozen=True, slots=True)
class DatasetInput:
    version_id: uuid.UUID
    rows: tuple[Mapping[str, Any], ...]
    selected_fields: tuple[str, ...]
    csv_bytes: bytes
    csv_sha256: str
    media_type: str = "text/csv; charset=utf-8"

    @property
    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            version_id=self.version_id,
            sha256=self.csv_sha256,
            row_count=len(self.rows),
            media_type=self.media_type,
        )


@dataclass(frozen=True, slots=True)
class DeliveryFile:
    role: DeliveryFileRole
    path: str
    media_type: str
    content: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class BundleMismatch:
    path: str
    reason: str
    expected: str | None = None
    actual: str | None = None


@dataclass(frozen=True, slots=True)
class GateFinding:
    code: str
    message: str
    subject_id: str | None = None


@dataclass(frozen=True, slots=True)
class GateDecision:
    gate_id: Literal["G-Claim", "G-Publish"]
    status: Literal["pass", "fail", "blocked"]
    findings: tuple[GateFinding, ...]
    checked_at: datetime
    subject_digest: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True, slots=True)
class ReviewSignoff:
    event_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_assignment_id: uuid.UUID
    reviewer_role: str
    reviewed_contract_sha256: str
    reviewed_data_sha256: str
    reviewed_report_html_sha256: str
    reviewed_sop_html_sha256: str
    reviewed_claim_digest: str
    signed_at: datetime
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ClaimSnapshotRow:
    claim_id: uuid.UUID
    claim_text: str
    state: str
    evidence_grade: str | None
    run_id: uuid.UUID | None
    roles: tuple[str, ...]
    evidence_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class ClaimSnapshot:
    rows: tuple[ClaimSnapshotRow, ...]
    digest: str
    bundle: Any = None  # C7 ClaimContractBundle；避免循环 import
    review_findings: tuple[GateFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class DisputeReference:
    path: str
    description: str
    claim_id: str | None = None
    evidence_id: str | None = None
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class AcceptanceEvent:
    event_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None
    created_at: datetime
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AcceptanceState:
    artifact_id: uuid.UUID
    delivery_class: str
    status: str
    deadline: datetime | None
    events: tuple[AcceptanceEvent, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    state: AcceptanceState
    replay: bool


@dataclass(frozen=True, slots=True)
class DeliveryManifest:
    payload: Mapping[str, Any]
    canonical_bytes: bytes
    sha256: str
    sidecar_bytes: bytes
    sidecar_sha256: str


@dataclass(frozen=True, slots=True)
class PublishResult:
    artifact: Any
    manifest: DeliveryManifest
    replay: bool
```

- [ ] **Step 4: 写公开投影实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/projection.py
"""公开合同投影。白名单，不是黑名单。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Final

from data_intelligence_hub.schemas.report_contract import (
    FORBIDDEN_LANGUAGE_PROFILE_ID,
    scan_forbidden_language,
)
from data_intelligence_hub.services.delivery.types import DatasetMetadata

PUBLIC_SCHEMA_VERSION: Final[str] = "1.0.0-public"
PUBLIC_PROJECTION_PROFILE: Final[str] = "dih-public-report-contract-v1"

FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "provider",
        "provider_id",
        "endpoint_type",
        "source_tool_id",
        "unit_price",
        "authorization_id",
        "actor_id",
        "approver",
        "owner",
        "run_ledger",
    }
)


def _source_ref(source_tool_id: str) -> str:
    digest = hashlib.sha256(source_tool_id.encode("utf-8")).hexdigest()[:12]
    return f"src-{digest}"


def _public_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": str(gate["gate_id"]),
        "status": str(gate["status"]),
        "decided_at": gate.get("decided_at"),
    }


def _public_claim(claim: Mapping[str, Any]) -> dict[str, Any]:
    scope = claim.get("scope") or {}
    return {
        "claim_id": str(claim["claim_id"]),
        "text": str(claim["text"]),
        "text_en": claim.get("text_en"),
        "claim_status": str(claim["claim_status"]),
        "evidence_grade": str(claim["evidence_grade"]),
        "scope": {
            "market": str(scope.get("market", "")),
            "window": scope.get("window"),
            "sample_n": int(scope.get("sample_n", 0)),
        },
        "counterevidence_text": str(claim["counterevidence_text"]),
        "evidence_ids": [str(value) for value in claim["evidence_ids"]],
    }


def _public_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": str(evidence["evidence_id"]),
        "claim_id": str(evidence["claim_id"]),
        "role": str(evidence["role"]),
        "raw_record_id": (
            str(evidence["raw_record_id"])
            if evidence.get("raw_record_id") is not None
            else None
        ),
        "source_ref": _source_ref(str(evidence["source_tool_id"])),
        "url": evidence.get("url"),
        "excerpt": evidence.get("excerpt"),
        "captured_at": evidence["captured_at"],
        "market": str(evidence["market"]),
        "locale": str(evidence["locale"]),
        "evidence_grade": str(evidence["evidence_grade"]),
    }


def _public_coverage_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_ref": _source_ref(str(cell["source_tool_id"])),
        "market": str(cell["market"]),
        "window": cell.get("window"),
        "record_count": int(cell.get("record_count", 0)),
        "frame_member_count": int(cell.get("frame_member_count", 0)),
        "status": str(cell["status"]),
    }


def project_public_contract(
    contract: Mapping[str, Any],
    *,
    dataset: DatasetMetadata,
    source_contract_sha256: str,
) -> dict[str, Any]:
    """生成公开合同投影。未在白名单的字段一律丢弃。"""
    coverage = contract.get("coverage") or {}
    cells = coverage.get("cells") or []
    public = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "task_id": str(contract["task_id"]),
        "template_id": str(contract["template_id"]),
        "generated_at": contract["generated_at"],
        "identity": contract["identity"],
        "decision": contract["decision"],
        "gates": [_public_gate(gate) for gate in contract.get("gates") or []],
        "coverage": {"cells": [_public_coverage_cell(cell) for cell in cells]},
        "markets": list(contract.get("markets") or []),
        "metrics": list(contract.get("metrics") or []),
        "claims": [_public_claim(claim) for claim in contract.get("claims") or []],
        "evidences": [
            _public_evidence(evidence) for evidence in contract.get("evidences") or []
        ],
        "limits": list(contract.get("limits") or []),
        "unknowns": list(contract.get("unknowns") or []),
        "artifact": {
            "report_html_sha256": str(contract["artifact"]["report_html_sha256"]),
            "sop_html_sha256": str(contract["artifact"]["sop_html_sha256"]),
            "contract_sha256": str(contract["artifact"]["contract_sha256"]),
        },
        "delivery": {
            "dataset_version_id": str(dataset.version_id),
            "dataset_sha256": dataset.sha256,
            "dataset_row_count": dataset.row_count,
            "dataset_media_type": dataset.media_type,
        },
        "public_projection": {
            "profile": PUBLIC_PROJECTION_PROFILE,
            "source_contract_sha256": source_contract_sha256,
        },
    }
    assert_no_forbidden_keys(public)
    return public


def assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
    """递归拒绝公开投影中的内部键。"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_KEYS:
                raise ValueError(f"{path}.{key_text} 是禁止出现在公开交付中的字段")
            assert_no_forbidden_keys(item, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_no_forbidden_keys(item, path=f"{path}[{index}]")


def assert_forbidden_language_free(contract: Mapping[str, Any]) -> None:
    hits = scan_forbidden_language(contract)
    if hits:
        raise ValueError(
            f"{FORBIDDEN_LANGUAGE_PROFILE_ID} 命中禁用表述："
            + "、".join(f"{hit.field_path}:{hit.term}" for hit in hits)
        )


__all__ = [
    "FORBIDDEN_LANGUAGE_PROFILE_ID",
    "PUBLIC_PROJECTION_PROFILE",
    "PUBLIC_SCHEMA_VERSION",
    "assert_forbidden_language_free",
    "assert_no_forbidden_keys",
    "project_public_contract",
]
```

- [ ] **Step 5: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_projection.py -v
```

Expected: `5 passed`。`build_report_contract()` 必须通过 `ReportContract.model_validate()` 与 `validate_contract()`；投影必须带 `task_id`。

- [ ] **Step 6: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/types.py src/data_intelligence_hub/services/delivery/projection.py tests/fixtures/report_contract_v1_1.py tests/unit/test_delivery_projection.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/types.py src/data_intelligence_hub/services/delivery/projection.py tests/fixtures/report_contract_v1_1.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/types.py \
  apps/api/src/data_intelligence_hub/services/delivery/projection.py \
  apps/api/tests/fixtures/report_contract_v1_1.py \
  apps/api/tests/unit/test_delivery_projection.py
git commit -m "feat(delivery): add types, c1 1.1 fixture and public projection"
```

---
### Task 3: 数据集、数据字典、Claim-Evidence 索引与运行回执

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/renderers.py`
- Test: `apps/api/tests/unit/test_delivery_renderers.py`

**Interfaces:**
- Consumes: `DatasetInput`、`canonical_bytes`、`sha256_hex`。
- Produces: `build_dataset_input`、`render_dataset_csv`、`render_data_dictionary`、`render_claim_evidence_index`、`render_run_receipt`。

- [ ] **Step 1: 写四个渲染器的失败测试**

```python
# apps/api/tests/unit/test_delivery_renderers.py
import csv
import io
import json
import uuid
from types import SimpleNamespace

from data_intelligence_hub.services.delivery.renderers import (
    build_dataset_input,
    render_claim_evidence_index,
    render_data_dictionary,
    render_dataset_csv,
    render_run_receipt,
)

DATASET_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


def _dataset() -> SimpleNamespace:
    return SimpleNamespace(
        id=DATASET_ID,
        rows=[{"a": 1, "b": "x"}, {"a": 2, "c": None}],
        selected_fields=["a", "b"],
        row_count=2,
    )


def _public_contract() -> dict:
    return {
        "claims": [
            {
                "claim_id": "11111111-1111-1111-1111-111111111111",
                "claim_status": "directional",
                "evidence_grade": "L3_live_single",
                "scope": {"market": "US", "sample_n": 120},
                "evidence_ids": ["22222222-2222-2222-2222-222222222222"],
            }
        ],
        "evidences": [
            {
                "evidence_id": "22222222-2222-2222-2222-222222222222",
                "claim_id": "11111111-1111-1111-1111-111111111111",
                "role": "support",
                "source_ref": "src-abc123def456",
                "url": "https://example.com/item",
            }
        ],
    }


def _contract() -> dict:
    return {
        "run_ledger": [
            {
                "run_id": "44444444-4444-4444-4444-444444444444",
                "tool_id": "tikhub_search",
                "endpoint_type": "search",
                "unit": "request",
                "quantity": 1,
                "unit_price": 0.01,
                "total_cost_usd": 0.01,
                "authorization_id": None,
                "evidence_grade": "L3_live_single",
                "started_at": "2026-02-01T00:00:00Z",
                "finished_at": "2026-02-01T00:00:05Z",
                "outcome": "success",
            }
        ]
    }


def test_dataset_csv_is_stable_and_has_union_header() -> None:
    assert render_dataset_csv(_dataset().rows, ["a", "b"]) == b"a,b,c\n1,x,\n2,,\n"


def test_build_dataset_input_hashes_exact_csv() -> None:
    dataset = build_dataset_input(_dataset())
    assert dataset.version_id == DATASET_ID
    assert dataset.csv_bytes == b"a,b,c\n1,x,\n2,,\n"
    assert dataset.csv_sha256 == "b59a2b20420291c53b50c72a90b3ff0e859eeffe8359c8f620e1b3b26e028b23"
    assert dataset.metadata.row_count == 2


def test_data_dictionary_infers_types_without_fake_descriptions() -> None:
    dataset = build_dataset_input(_dataset())
    payload = json.loads(render_data_dictionary(dataset))
    assert payload["fields"] == [
        {"name": "a", "type": "integer", "nullable": False},
        {"name": "b", "type": "string", "nullable": False},
        {"name": "c", "type": "unknown", "nullable": True},
    ]
    assert "description" not in payload["fields"][0]


def test_claim_evidence_index_is_csv_and_sorted() -> None:
    content = render_claim_evidence_index(_public_contract())
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    assert rows == [
        {
            "claim_id": "11111111-1111-1111-1111-111111111111",
            "claim_status": "directional",
            "evidence_grade": "L3_live_single",
            "market": "US",
            "sample_n": "120",
            "evidence_id": "22222222-2222-2222-2222-222222222222",
            "role": "support",
            "source_ref": "src-abc123def456",
            "url": "https://example.com/item",
        }
    ]


def test_run_receipt_drops_internal_fields() -> None:
    content = render_run_receipt(_contract())
    text = content.decode("utf-8")
    for forbidden in ("tool_id", "endpoint_type", "unit_price", "total_cost_usd", "authorization_id", "actor_id"):
        assert forbidden not in text
    payload = json.loads(text)
    assert payload["runs"][0]["run_id"] == "44444444-4444-4444-4444-444444444444"
    assert payload["runs"][0]["outcome"] == "success"
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_renderers.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.services.delivery.renderers'`。

- [ ] **Step 3: 写最小实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/renderers.py
"""交付文件的确定性渲染。不读库、不联网、不调模型、不读时钟。"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any, Final

from data_intelligence_hub.services.delivery.canonical import sha256_hex
from data_intelligence_hub.services.delivery.types import DatasetInput

DATASET_MEDIA_TYPE: Final[str] = "text/csv; charset=utf-8"


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def render_dataset_csv(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes:
    ordered_fields = list(dict.fromkeys(str(field) for field in fields))
    extra = sorted({str(key) for row in rows for key in row} - set(ordered_fields))
    header = ordered_fields + extra
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in header})
    return buffer.getvalue().encode("utf-8")


def build_dataset_input(version: object) -> DatasetInput:
    rows = tuple(dict(row) for row in getattr(version, "rows", []) or [])
    fields = tuple(str(field) for field in getattr(version, "selected_fields", []) or [])
    csv_bytes = render_dataset_csv(rows, fields)
    return DatasetInput(
        version_id=getattr(version, "id"),
        rows=rows,
        selected_fields=fields,
        csv_bytes=csv_bytes,
        csv_sha256=sha256_hex(csv_bytes),
        media_type=DATASET_MEDIA_TYPE,
    )


def _infer_type(values: Sequence[object]) -> str:
    present = [value for value in values if value is not None]
    if not present:
        return "unknown"
    if all(isinstance(value, bool) for value in present):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in present):
        return "integer"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in present):
        return "number"
    if all(isinstance(value, str) for value in present):
        return "string"
    if all(isinstance(value, Mapping) for value in present):
        return "object"
    if all(isinstance(value, (list, tuple)) for value in present):
        return "array"
    return "mixed"


def _pretty_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def render_data_dictionary(dataset: DatasetInput) -> bytes:
    fields = list(dataset.selected_fields)
    extra = sorted({str(key) for row in dataset.rows for key in row} - set(fields))
    names = fields + extra
    payload = {
        "schema_version": "1.0.0",
        "source": {
            "dataset_version_id": str(dataset.version_id),
            "row_count": len(dataset.rows),
            "sha256": dataset.csv_sha256,
        },
        "fields": [
            {
                "name": name,
                "type": _infer_type([row.get(name) for row in dataset.rows]),
                "nullable": any(row.get(name) is None for row in dataset.rows),
            }
            for name in names
        ],
    }
    return _pretty_json(payload)


def render_claim_evidence_index(public_contract: Mapping[str, Any]) -> bytes:
    claims = {str(claim["claim_id"]): claim for claim in public_contract.get("claims") or []}
    rows: list[dict[str, str]] = []
    for evidence in public_contract.get("evidences") or []:
        claim = claims.get(str(evidence["claim_id"]), {})
        scope = claim.get("scope") or {}
        rows.append(
            {
                "claim_id": str(evidence["claim_id"]),
                "claim_status": str(claim.get("claim_status", "")),
                "evidence_grade": str(claim.get("evidence_grade", "")),
                "market": str(scope.get("market", "")),
                "sample_n": str(scope.get("sample_n", "")),
                "evidence_id": str(evidence["evidence_id"]),
                "role": str(evidence["role"]),
                "source_ref": str(evidence["source_ref"]),
                "url": str(evidence.get("url") or ""),
            }
        )
    rows.sort(key=lambda row: (row["claim_id"], row["evidence_id"], row["role"]))
    header = [
        "claim_id",
        "claim_status",
        "evidence_grade",
        "market",
        "sample_n",
        "evidence_id",
        "role",
        "source_ref",
        "url",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def render_run_receipt(contract: Mapping[str, Any]) -> bytes:
    runs: list[dict[str, Any]] = []
    for row in contract.get("run_ledger") or []:
        runs.append(
            {
                "run_id": str(row["run_id"]),
                "outcome": str(row["outcome"]),
                "evidence_grade": str(row["evidence_grade"]),
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "quantity": row.get("quantity"),
            }
        )
    runs.sort(key=lambda item: item["run_id"])
    return _pretty_json({"schema_version": "1.0.0", "runs": runs})


__all__ = [
    "DATASET_MEDIA_TYPE",
    "build_dataset_input",
    "render_claim_evidence_index",
    "render_data_dictionary",
    "render_dataset_csv",
    "render_run_receipt",
]
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_renderers.py -v
```

Expected: `5 passed`。固定哈希 `b59a...` 必须保持；不得改为运行时计算。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/renderers.py tests/unit/test_delivery_renderers.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/renderers.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/renderers.py \
  apps/api/tests/unit/test_delivery_renderers.py
git commit -m "feat(delivery): render dataset, dictionary, claim index and run receipt"
```

---

### Task 4: 英文摘要、质量记分卡、限制与 Gap、正式验收快照与 Quick 通知

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/delivery/renderers.py`
- Modify: `apps/api/tests/unit/test_delivery_renderers.py`

**Interfaces:**
- Consumes: `DatasetInput`、`DatasetMetadata`、`GateDecision` 的字符串状态。
- Produces: `render_executive_summary_en`、`render_quality_scorecard`、`render_limits_and_gaps`、`add_business_days`、`render_acceptance_snapshot`、`render_quick_draft_notice`。

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 apps/api/tests/unit/test_delivery_renderers.py
from datetime import UTC, datetime

from data_intelligence_hub.services.delivery.renderers import (
    add_business_days,
    render_acceptance_snapshot,
    render_executive_summary_en,
    render_limits_and_gaps,
    render_quality_scorecard,
    render_quick_draft_notice,
)


def _public_summary_contract() -> dict:
    return {
        "task_id": "11111111-1111-1111-1111-111111111111",
        "identity": {"brand": "Example", "markets": ["US"]},
        "decision": {
            "decision_question": "Should we enter the US market?",
            "answer": "Validate demand first.",
            "answer_en": "Validate demand first.",
        },
        "coverage": {
            "cells": [
                {
                    "source_ref": "src-abc",
                    "market": "US",
                    "record_count": 120,
                    "frame_member_count": 120,
                    "status": "success",
                },
                {
                    "source_ref": "src-def",
                    "market": "US",
                    "record_count": 0,
                    "frame_member_count": 0,
                    "status": "failed",
                },
            ]
        },
        "markets": [
            {
                "market": "US",
                "market_role": "primary",
                "quality_status": "qualified_with_gap",
                "conclusion_standard": "conditional_enter",
                "evidence_grade": "L3_live_single",
                "domains": [],
                "sample_counts": {},
                "thresholds": {},
                "gaps": [],
            }
        ],
        "claims": [
            {
                "claim_id": "11111111-1111-1111-1111-111111111111",
                "text": "需求一致但未确认。",
                "text_en": "Demand is consistent but not confirmed.",
                "claim_status": "directional",
                "evidence_grade": "L3_live_single",
                "scope": {"market": "US", "sample_n": 120},
            },
            {
                "claim_id": "22222222-2222-2222-2222-222222222222",
                "text": "证据不足。",
                "text_en": "Evidence is insufficient.",
                "claim_status": "evidence_gap",
                "evidence_grade": "L3_live_single",
                "scope": {"market": "US", "sample_n": 0},
            },
        ],
        "limits": ["不能推断长期复购。"],
        "unknowns": ["缺少线下渠道数据。"],
    }


def test_executive_summary_en_is_exact() -> None:
    assert render_executive_summary_en(_public_summary_contract()).decode("utf-8") == (
        "# Example — Should we enter the US market?\n"
        "\n"
        "**Answer:** Validate demand first.\n"
        "\n"
        "## Market coverage\n"
        "\n"
        "| Market | Coverage cells | Records | Claims | Evidence floor |\n"
        "|---|---:|---:|---:|---|\n"
        "| US | 2 | 120 | 2 | L3_live_single |\n"
        "\n"
        "## Claims\n"
        "\n"
        "- **directional** (L3_live_single): Demand is consistent but not confirmed.\n"
        "- **evidence_gap** (L3_live_single): Evidence is insufficient.\n"
        "\n"
        "## Limits and unknowns\n"
        "\n"
        "- Limits: 不能推断长期复购。\n"
        "- Unknowns: 缺少线下渠道数据。\n"
    )


def test_executive_summary_falls_back_to_source_text() -> None:
    contract = _public_summary_contract()
    contract["claims"][0].pop("text_en")
    text = render_executive_summary_en(contract).decode("utf-8")
    assert "需求一致但未确认。" in text


def test_quality_scorecard_round_trips_market_quality_status() -> None:
    contract = _public_summary_contract()
    contract["datasets"] = [
        {
            "dataset_version_id": "99999999-9999-9999-9999-999999999999",
            "market": "US",
            "row_count": 1,
            "content_sha256": "a" * 64,
            "schema_hash": "b" * 64,
            "quality_status": "qualified_with_gap",
        }
    ]
    contract["scorecard"] = {
        "markets": contract["markets"],
        "minimum_evidence_grade": "L3_live_single",
        "claims": {
            "total": 2,
            "by_status": {"directional": 1, "evidence_gap": 1},
            "by_grade": {"L3_live_single": 2},
            "independent_source_count": 2,
        },
    }
    payload = json.loads(render_quality_scorecard(contract))
    assert payload["task_id"] == contract["task_id"]
    assert payload["markets"][0]["quality_status"] == "qualified_with_gap"
    assert payload["datasets"] == contract["datasets"]
    assert payload["scorecard"] == contract["scorecard"]


@pytest.mark.parametrize(
    "quality_status", ["qualified", "qualified_with_gap", "not_qualified"]
)
def test_quality_scorecard_round_trips_all_quality_statuses(
    quality_status: str,
) -> None:
    contract = _public_summary_contract()
    contract["markets"][0]["quality_status"] = quality_status
    contract["datasets"] = [
        {
            "dataset_version_id": "99999999-9999-9999-9999-999999999999",
            "market": "US",
            "row_count": 1,
            "content_sha256": "a" * 64,
            "schema_hash": "b" * 64,
            "quality_status": quality_status,
        }
    ]
    contract["scorecard"] = {
        "markets": contract["markets"],
        "minimum_evidence_grade": "L3_live_single",
        "claims": {
            "total": 0,
            "by_status": {},
            "by_grade": {},
            "independent_source_count": 0,
        },
    }
    payload = json.loads(render_quality_scorecard(contract))
    assert payload["markets"][0]["quality_status"] == quality_status
    assert payload["datasets"][0]["quality_status"] == quality_status
    assert payload["scorecard"] == contract["scorecard"]


def test_quality_scorecard_ignores_coverage_and_claims() -> None:
    contract = _public_summary_contract()
    contract["datasets"] = []
    contract["scorecard"] = {
        "markets": contract["markets"],
        "minimum_evidence_grade": "L3_live_single",
        "claims": {"total": 0, "by_status": {}, "by_grade": {}, "independent_source_count": 0},
    }
    contract["coverage"] = {"cells": [{"market": "US", "status": "failed", "record_count": 0}]}
    contract["claims"] = [{"claim_id": "x", "claim_status": "blocked"}]
    payload = json.loads(render_quality_scorecard(contract))
    assert "coverage" not in payload
    assert "claim_status_counts" not in json.dumps(payload)
    assert payload["markets"][0]["quality_status"] == "qualified_with_gap"


def test_limits_and_gaps_lists_non_success_coverage_and_claim_gaps() -> None:
    payload = json.loads(render_limits_and_gaps(_public_summary_contract()))
    assert payload["limits"] == ["不能推断长期复购。"]
    assert payload["unknowns"] == ["缺少线下渠道数据。"]
    assert payload["gaps"] == [
        {
            "type": "coverage_gap",
            "market": "US",
            "source_ref": "src-def",
            "status": "failed",
            "record_count": 0,
        },
        {
            "type": "claim_gap",
            "claim_id": "22222222-2222-2222-2222-222222222222",
            "claim_status": "evidence_gap",
            "market": "US",
            "sample_n": 0,
        },
    ]


def test_add_business_days_skips_weekend() -> None:
    assert add_business_days(datetime(2026, 10, 22, 10, 0, tzinfo=UTC), 5) == datetime(
        2026, 10, 29, 23, 59, 59, tzinfo=UTC
    )
    assert add_business_days(datetime(2026, 10, 23, 10, 0, tzinfo=UTC), 1) == datetime(
        2026, 10, 26, 23, 59, 59, tzinfo=UTC
    )


def test_acceptance_snapshot_has_no_manifest_self_reference() -> None:
    dataset = build_dataset_input(_dataset())
    content = render_acceptance_snapshot(
        artifact_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        contract_sha256="c" * 64,
        data_sha256="d" * 64,
        dataset=dataset,
        content_bundle_sha256="e" * 64,
        delivered_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
        acceptance_deadline=datetime(2026, 10, 29, 23, 59, 59, tzinfo=UTC),
        gate_status={"G-Claim": "pass", "G-Publish": "pass"},
    )
    payload = json.loads(content)
    assert payload["acceptance_window_business_days"] == 5
    assert payload["acceptance_deadline"] == "2026-10-29T23:59:59Z"
    assert payload["content_bundle_sha256"] == "e" * 64
    assert payload["status"] == "pending"
    assert "manifest_sha256" not in payload


def test_quick_draft_notice_is_directional_and_has_no_acceptance() -> None:
    content = render_quick_draft_notice(
        artifact_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        task_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        delivered_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
        package_type="quick",
    )
    payload = json.loads(content)
    assert payload["schema_version"] == "quick-draft-notice.v1"
    assert payload["delivery_class"] == "quick_draft"
    assert payload["directional_only"] is True
    assert payload["review_status"] == "not_reviewed"
    assert payload["acceptance"] == "not_applicable"
    assert payload["formal_delivery_sla_hours"] == 24
    assert "acceptance_deadline" not in payload
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_renderers.py -v
```

Expected: `ImportError: cannot import name 'render_quick_draft_notice'`。

- [ ] **Step 3: 追加实现到 `renderers.py`**

```python
# 追加到 apps/api/src/data_intelligence_hub/services/delivery/renderers.py

_GRADE_ORDER: Final[dict[str, int]] = {
    "L0_unverified": 0,
    "L1_contract": 1,
    "L2_fixture_local": 2,
    "L3_live_single": 3,
    "L4_authorized_live": 4,
}


def _grade_floor(grades: Sequence[str]) -> str:
    if not grades:
        return "none"
    return min(grades, key=lambda grade: _GRADE_ORDER.get(grade, -1))


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_executive_summary_en(public_contract: Mapping[str, Any]) -> bytes:
    identity = public_contract["identity"]
    decision = public_contract["decision"]
    claims = list(public_contract.get("claims") or [])
    cells = list((public_contract.get("coverage") or {}).get("cells") or [])
    markets = sorted({str(cell["market"]) for cell in cells})
    lines = [
        f"# {identity['brand']} — {decision['decision_question']}",
        "",
        f"**Answer:** {decision.get('answer_en') or decision['answer']}",
        "",
        "## Market coverage",
        "",
        "| Market | Coverage cells | Records | Claims | Evidence floor |",
        "|---|---:|---:|---:|---|",
    ]
    for market in markets:
        market_cells = [cell for cell in cells if str(cell["market"]) == market]
        market_claims = [
            claim for claim in claims if str((claim.get("scope") or {}).get("market")) == market
        ]
        records = sum(int(cell.get("record_count", 0)) for cell in market_cells)
        floor = _grade_floor([str(claim["evidence_grade"]) for claim in market_claims])
        lines.append(
            f"| {_md_cell(market)} | {len(market_cells)} | {records} | "
            f"{len(market_claims)} | {floor} |"
        )
    lines.extend(["", "## Claims", ""])
    if claims:
        for claim in sorted(claims, key=lambda item: str(item["claim_id"])):
            text = claim.get("text_en") or claim["text"]
            lines.append(f"- **{claim['claim_status']}** ({claim['evidence_grade']}): {text}")
    else:
        lines.append("- No claims were published.")
    lines.extend(["", "## Limits and unknowns", ""])
    limits = list(public_contract.get("limits") or [])
    unknowns = list(public_contract.get("unknowns") or [])
    lines.extend([f"- Limits: {item}" for item in limits] or ["- Limits: None recorded."])
    lines.extend([f"- Unknowns: {item}" for item in unknowns] or ["- Unknowns: None recorded."])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def render_quality_scorecard(contract: Mapping[str, Any]) -> bytes:
    """只读 1.1 合同的 markets/datasets/scorecard，不读 coverage/claims。"""
    payload = {
        "schema_version": "quality-scorecard.v1",
        "task_id": str(contract["task_id"]),
        "markets": list(contract.get("markets") or []),
        "datasets": list(contract.get("datasets") or []),
        "scorecard": dict(contract.get("scorecard") or {}),
    }
    return _pretty_json(payload)


def render_limits_and_gaps(public_contract: Mapping[str, Any]) -> bytes:
    gaps: list[dict[str, Any]] = []
    for cell in (public_contract.get("coverage") or {}).get("cells") or []:
        if cell["status"] == "success":
            continue
        gaps.append(
            {
                "type": "coverage_gap",
                "market": str(cell["market"]),
                "source_ref": str(cell["source_ref"]),
                "status": str(cell["status"]),
                "record_count": int(cell.get("record_count", 0)),
            }
        )
    for claim in public_contract.get("claims") or []:
        if claim["claim_status"] not in {"evidence_gap", "blocked"}:
            continue
        scope = claim.get("scope") or {}
        gaps.append(
            {
                "type": "claim_gap",
                "claim_id": str(claim["claim_id"]),
                "claim_status": str(claim["claim_status"]),
                "market": str(scope.get("market", "")),
                "sample_n": int(scope.get("sample_n", 0)),
            }
        )
    gaps.sort(
        key=lambda item: (
            0 if item["type"] == "coverage_gap" else 1,
            item.get("market", ""),
            item.get("claim_id", ""),
        )
    )
    payload = {
        "schema_version": "1.0.0",
        "limits": list(public_contract.get("limits") or []),
        "unknowns": list(public_contract.get("unknowns") or []),
        "gaps": gaps,
    }
    return _pretty_json(payload)


def add_business_days(start: datetime, days: int) -> datetime:
    """从 start 起加工作日，返回第 days 个工作日的 23:59:59 UTC。"""
    if days < 1:
        raise ValueError("days 必须大于等于 1")
    current = start.astimezone(UTC).date()
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return datetime.combine(current, time(23, 59, 59), tzinfo=UTC)


def _utc_seconds(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_acceptance_snapshot(
    *,
    artifact_id: uuid.UUID,
    contract_sha256: str,
    data_sha256: str,
    dataset: DatasetInput,
    content_bundle_sha256: str,
    delivered_at: datetime,
    acceptance_deadline: datetime,
    gate_status: Mapping[str, str],
) -> bytes:
    """正式交付验收快照。快照不含 manifest 哈希，避免自引用。"""
    payload = {
        "schema_version": "1.0.0",
        "delivery_class": "formal",
        "artifact_id": str(artifact_id),
        "delivered_at": _utc_seconds(delivered_at),
        "acceptance_window_business_days": 5,
        "acceptance_deadline": _utc_seconds(acceptance_deadline),
        "contract_sha256": contract_sha256,
        "data_sha256": data_sha256,
        "content_bundle_sha256": content_bundle_sha256,
        "dataset": {
            "version_id": str(dataset.version_id),
            "sha256": dataset.csv_sha256,
            "row_count": len(dataset.rows),
        },
        "gate_status": dict(sorted(gate_status.items())),
        "status": "pending",
    }
    return _pretty_json(payload)


def render_quick_draft_notice(
    *,
    artifact_id: uuid.UUID,
    task_id: uuid.UUID,
    delivered_at: datetime,
    package_type: str,
) -> bytes:
    """Quick 2 小时方向稿通知。不启动验收，不生成 Standard 四态。"""
    if package_type != "quick":
        raise ValueError("quick_draft_not_allowed")
    payload = {
        "schema_version": "quick-draft-notice.v1",
        "delivery_class": "quick_draft",
        "artifact_id": str(artifact_id),
        "task_id": str(task_id),
        "delivered_at": _utc_seconds(delivered_at),
        "directional_only": True,
        "review_status": "not_reviewed",
        "acceptance": "not_applicable",
        "standard_four_state": "not_applicable",
        "confirmed_claim_count": 0,
        "available_within_task": True,
        "formal_delivery_sla_hours": 24,
    }
    return _pretty_json(payload)
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_renderers.py -v
```

Expected: 全部 `passed`（Task 3 的 5 个 + 本任务新增用例）。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/renderers.py tests/unit/test_delivery_renderers.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/renderers.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/renderers.py \
  apps/api/tests/unit/test_delivery_renderers.py
git commit -m "feat(delivery): render summary, scorecard, gaps, formal snapshot and quick notice"
```

---
### Task 5: 审阅签字读取与 C7 G-Claim / G-Publish 求值

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/review.py`
- Create: `apps/api/src/data_intelligence_hub/services/delivery/gates.py`
- Create: `apps/api/tests/unit/conftest.py`
- Test: `apps/api/tests/unit/test_delivery_review.py`
- Test: `apps/api/tests/unit/test_delivery_gates.py`

**Interfaces:**
- Consumes: C7 `load_publishable_claim_rows` / `validate_claim_bundle` / `validate_claim_semantics`；C9 `report_review_approved` / `claim_review_digest`；C2 `get_active_reviewer_assignment` / `get_workspace_role`。
- Produces: `load_latest_review_signoff`、`validate_review_signoff`、`load_claim_snapshot`、`evaluate_g_claim`、`evaluate_g_publish`。

- [ ] **Step 1: 写共享夹具与失败测试**

`delivery_seed` 只种一份最小事实，Tasks 5/9/10 共用；不得在三个测试文件里复制第二套 schema。

```python
# apps/api/tests/unit/conftest.py
from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.claim import Claim, ClaimEvidence
from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    contract_sha256,
)
from data_intelligence_hub.services.report_artifacts import (
    build_artifact,
    render_sha256,
)
from data_intelligence_hub.services.report_publication import claim_review_digest
from tests.fixtures.report_contract_v1_1 import (
    build_evidence,
    build_report_contract,
)

WORKSPACE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CLAIM_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SUPPORT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
COUNTER_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
USER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
MEMBER_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
REVIEWER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
REVIEWER_ASSIGNMENT_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
REPORT_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
ARTIFACT_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
DATASET_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DATASET_VERSION_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TASK_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

REPORT_HTML = "<html><body><h1>报告</h1></body></html>"
SOP_HTML = "<html><body><h1>SOP</h1></body></html>"


def _contract() -> dict:
    contract = build_report_contract(
        task_id=TASK_ID,
        owner_id=USER_ID,
        claim_id=CLAIM_ID,
        evidence_id=SUPPORT_ID,
        report_html_sha256=render_sha256(REPORT_HTML),
        sop_html_sha256=render_sha256(SOP_HTML),
        review_status="approved",
        claim_override={
            "evidence_ids": [str(SUPPORT_ID), str(COUNTER_ID)],
            "independent_source_count": 2,
        },
        evidences=(
            build_evidence(
                evidence_id=SUPPORT_ID,
                claim_id=CLAIM_ID,
                role="support",
                source_tool_id="tikhub_search",
            ),
            build_evidence(
                evidence_id=COUNTER_ID,
                claim_id=CLAIM_ID,
                role="counter",
                source_tool_id="tikhub_counter",
            ),
        ),
        market_override={
            "conclusion_standard": "conditional_enter",
            "quality_status": "qualified_with_gap",
        },
    )
    contract["gates"] = [{"gate_id": "G-Publish", "status": "pass"}]
    model = ReportContract.model_validate(contract)
    contract["artifact"]["contract_sha256"] = contract_sha256(model)
    return contract


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as database_session:
            yield database_session
    finally:
        await engine.dispose()


@pytest.fixture
async def delivery_seed(session: AsyncSession) -> SimpleNamespace:
    user = User(
        id=USER_ID,
        email="owner@example.com",
        password_hash="x",
        name="Owner",
        status="active",
    )
    member = User(
        id=MEMBER_ID,
        email="member@example.com",
        password_hash="x",
        name="Member",
        status="active",
    )
    reviewer = User(
        id=REVIEWER_ID,
        email="reviewer@example.com",
        password_hash="x",
        name="Reviewer",
        status="active",
    )
    workspace = Workspace(id=WORKSPACE_ID, name="W", slug="w", owner_id=USER_ID)
    project = Project(
        id=PROJECT_ID,
        workspace_id=WORKSPACE_ID,
        name="P",
        domain="ecommerce",
        owner_id=USER_ID,
    )
    session.add_all([user, member, reviewer, workspace, project])
    await session.flush()
    session.add_all(
        [
            WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=USER_ID, role="owner"),
            WorkspaceMember(workspace_id=WORKSPACE_ID, user_id=MEMBER_ID, role="member"),
        ]
    )
    report = Report(
        id=REPORT_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        report_type="t1_voc",
        title="Delivery",
        content="",
        status="draft",
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session.add(report)
    await session.flush()
    session.add(
        ReportReviewerAssignment(
            id=REVIEWER_ASSIGNMENT_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            report_id=REPORT_ID,
            artifact_id=None,
            reviewer_user_id=REVIEWER_ID,
            assignment_scope="report_review",
            status="active",
            assigned_by=USER_ID,
            assigned_at=datetime(2026, 10, 22, 8, 0, tzinfo=UTC),
            expires_at=datetime(2027, 10, 22, 8, 0, tzinfo=UTC),
        )
    )
    intelligence = IntelligenceItem(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        title="T",
        summary="S",
        intelligence_type="review",
        status="new",
        impact_score=0.5,
        confidence_score=0.5,
        novelty_score=0.5,
        urgency_score=0.5,
        final_score=0.5,
        generated_by="human",
        domain="ecommerce",
    )
    session.add(intelligence)
    await session.flush()
    session.add_all(
        [
            Evidence(
                id=SUPPORT_ID,
                intelligence_id=intelligence.id,
                evidence_type="review",
                title="support",
                url="https://example.com/support",
                raw_record_id=None,
                source_tool_id="tikhub_search",
                excerpt="公开摘要。",
                captured_at=datetime(2026, 2, 1, tzinfo=UTC),
                market="US",
                locale="en-US",
            ),
            Evidence(
                id=COUNTER_ID,
                intelligence_id=intelligence.id,
                evidence_type="review",
                title="counter",
                url="https://example.com/counter",
                raw_record_id=None,
                source_tool_id="tikhub_counter",
                excerpt="反证摘要。",
                captured_at=datetime(2026, 2, 1, tzinfo=UTC),
                market="US",
                locale="en-US",
            ),
        ]
    )
    claim = Claim(
        id=CLAIM_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        run_id=RUN_ID,
        claim_text="需求一致但未确认。",
        text_en="Demand is consistent but not confirmed.",
        state="directional",
        evidence_grade="L3_live_single",
        review_status="approved",
        reviewed_by=REVIEWER_ID,
        reviewed_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
        reviewed_content_version=1,
        content_version=1,
        reviewed_payload_sha256="9" * 64,
        scope_market="US",
        scope_window_start=date(2026, 1, 1),
        scope_window_end=date(2026, 3, 1),
        scope_window_days=60,
        scope_sample_n=120,
        counterevidence_text="未发现反证。",
        owner=USER_ID,
        independent_source_count=2,
    )
    session.add(claim)
    await session.flush()
    session.add_all(
        [
            ClaimEvidence(
                claim_id=CLAIM_ID,
                evidence_id=SUPPORT_ID,
                role="support",
                evidence_grade="L3_live_single",
                source_cluster_key="cluster-support",
                source_cluster_basis="raw_record",
                independent=True,
            ),
            ClaimEvidence(
                claim_id=CLAIM_ID,
                evidence_id=COUNTER_ID,
                role="counter",
                evidence_grade="L3_live_single",
                source_cluster_key="cluster-counter",
                source_cluster_basis="raw_record",
                independent=True,
            ),
        ]
    )
    contract = _contract()
    model = ReportContract.model_validate(contract)
    artifact = build_artifact(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        template_id="t1_voc",
        contract=model,
        report_html=REPORT_HTML,
        sop_html=SOP_HTML,
        run_id=RUN_ID,
        report_id=REPORT_ID,
    )
    artifact.id = ARTIFACT_ID
    artifact.status = "published"
    artifact.delivery_status = "pending"
    session.add(artifact)
    await session.flush()
    session.add(
        ReportAuditEvent(
            workspace_id=WORKSPACE_ID,
            report_id=None,
            artifact_id=ARTIFACT_ID,
            actor_id=REVIEWER_ID,
            event_type="report_review_approved",
            metadata_json=json.dumps(
                {
                    "reviewer_role": "internal_reviewer",
                    "reviewer_assignment_id": str(REVIEWER_ASSIGNMENT_ID),
                    "reviewed_contract_sha256": artifact.contract_sha256,
                    "reviewed_data_sha256": artifact.data_sha256,
                    "reviewed_report_html_sha256": artifact.report_html_sha256,
                    "reviewed_sop_html_sha256": artifact.sop_html_sha256,
                    "reviewed_claim_digest": claim_review_digest(contract),
                }
            ),
            created_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
        )
    )
    dataset = Dataset(
        id=DATASET_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        name="delivery",
        dataset_type="records",
        status="active",
    )
    session.add(dataset)
    await session.flush()
    version = DatasetVersion(
        id=DATASET_VERSION_ID,
        dataset_id=DATASET_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        version_number=1,
        source_task_run_ids=[str(RUN_ID)],
        selected_fields=["a", "b"],
        cleaning_script=[],
        rows=[{"a": 1, "b": "x"}],
        export_preview={},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
    )
    session.add(version)
    await session.commit()
    return SimpleNamespace(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        artifact_id=ARTIFACT_ID,
        dataset_version_id=DATASET_VERSION_ID,
        user_id=USER_ID,
        member_id=MEMBER_ID,
        reviewer_id=REVIEWER_ID,
        reviewer_assignment_id=REVIEWER_ASSIGNMENT_ID,
        workspace=workspace,
        user=user,
        member=member,
        reviewer=reviewer,
        contract=contract,
        artifact=artifact,
    )
```

`reviewed_claim_digest` 必须用 C9 的 `claim_review_digest(contract)`，不能手写。若 C9 的函数名不同，停止并回到 C9 统一。

`test_delivery_review.py`：

```python
# apps/api/tests/unit/test_delivery_review.py
import uuid
from datetime import UTC, datetime

from data_intelligence_hub.models.report_reviewer_assignment import (
    ReportReviewerAssignment,
)
from data_intelligence_hub.services.delivery.gates import load_claim_snapshot
from data_intelligence_hub.services.delivery.review import (
    load_latest_review_signoff,
    validate_review_signoff,
)
from data_intelligence_hub.services.delivery.types import ReviewSignoff

REVIEWER_ASSIGNMENT_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _signoff(seed, snapshot, **overrides) -> ReviewSignoff:
    payload = dict(
        event_id=uuid.uuid4(),
        reviewer_id=seed.reviewer_id,
        reviewer_assignment_id=seed.reviewer_assignment_id,
        reviewer_role="internal_reviewer",
        reviewed_contract_sha256=seed.artifact.contract_sha256,
        reviewed_data_sha256=seed.artifact.data_sha256,
        reviewed_report_html_sha256=seed.artifact.report_html_sha256,
        reviewed_sop_html_sha256=seed.artifact.sop_html_sha256,
        reviewed_claim_digest=snapshot.digest,
        signed_at=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
        metadata={},
    )
    payload.update(overrides)
    return ReviewSignoff(**payload)


async def test_loads_seeded_signoff(session, delivery_seed) -> None:
    signoff = await load_latest_review_signoff(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=delivery_seed.artifact_id,
    )
    assert signoff is not None
    assert signoff.reviewer_id == delivery_seed.reviewer_id
    assert signoff.reviewed_contract_sha256 == delivery_seed.artifact.contract_sha256


async def test_missing_assignment_is_rejected(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    findings = await validate_review_signoff(
        session,
        workspace_id=delivery_seed.workspace_id,
        signoff=_signoff(delivery_seed, snapshot, reviewer_id=uuid.uuid4(), reviewer_assignment_id=uuid.uuid4()),
        artifact=delivery_seed.artifact,
        claim_snapshot=snapshot,
    )
    assert any(f.code == "reviewer_assignment_required" for f in findings)


async def test_expired_assignment_is_rejected(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    assignment = await session.get(
        ReportReviewerAssignment, delivery_seed.reviewer_assignment_id
    )
    assignment.expires_at = datetime(2026, 1, 1, tzinfo=UTC)
    await session.flush()
    findings = await validate_review_signoff(
        session,
        workspace_id=delivery_seed.workspace_id,
        signoff=_signoff(delivery_seed, snapshot),
        artifact=delivery_seed.artifact,
        claim_snapshot=snapshot,
        assignment=assignment,
    )
    assert any(f.code == "reviewer_assignment_expired" for f in findings)


async def test_owner_admin_self_review_is_rejected(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    findings = await validate_review_signoff(
        session,
        workspace_id=delivery_seed.workspace_id,
        signoff=_signoff(delivery_seed, snapshot, reviewer_id=delivery_seed.user_id),
        artifact=delivery_seed.artifact,
        claim_snapshot=snapshot,
    )
    assert any(f.code == "reviewer_self_review_forbidden" for f in findings)
    assert any(f.code == "reviewer_is_claim_owner" for f in findings)
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_review.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.services.delivery.review'`。

- [ ] **Step 3: 写 `review.py`**

```python
# apps/api/src/data_intelligence_hub/services/delivery/review.py
"""读取并校验 C9 写入的 report_review_approved 事件。C10 不写签字。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.delivery import get_workspace_role
from data_intelligence_hub.repositories.report_reviewers import (
    get_active_reviewer_assignment,
)
from data_intelligence_hub.services.delivery.types import (
    ClaimSnapshot,
    GateFinding,
    ReviewSignoff,
)

REQUIRED_SIGNOFF_KEYS = (
    "reviewer_role",
    "reviewer_assignment_id",
    "reviewed_contract_sha256",
    "reviewed_data_sha256",
    "reviewed_report_html_sha256",
    "reviewed_sop_html_sha256",
    "reviewed_claim_digest",
)


class ReviewSignoffInvalid(ValueError):
    """签字事件缺少字段或格式非法。"""


async def load_latest_review_signoff(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> ReviewSignoff | None:
    result = await session.execute(
        select(ReportAuditEvent)
        .where(
            ReportAuditEvent.workspace_id == workspace_id,
            ReportAuditEvent.artifact_id == artifact_id,
            ReportAuditEvent.event_type == "report_review_approved",
        )
        .order_by(ReportAuditEvent.created_at.desc(), ReportAuditEvent.id.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event is None:
        return None
    try:
        metadata: dict[str, Any] = json.loads(event.metadata_json or "{}")
    except json.JSONDecodeError as exc:
        raise ReviewSignoffInvalid("report_review_approved 的 metadata_json 不是合法 JSON") from exc
    missing = [key for key in REQUIRED_SIGNOFF_KEYS if key not in metadata]
    if missing:
        raise ReviewSignoffInvalid("report_review_approved 缺少字段：" + "、".join(missing))
    return ReviewSignoff(
        event_id=event.id,
        reviewer_id=event.actor_id or uuid.UUID(int=0),
        reviewer_assignment_id=uuid.UUID(str(metadata["reviewer_assignment_id"])),
        reviewer_role=str(metadata["reviewer_role"]),
        reviewed_contract_sha256=str(metadata["reviewed_contract_sha256"]),
        reviewed_data_sha256=str(metadata["reviewed_data_sha256"]),
        reviewed_report_html_sha256=str(metadata["reviewed_report_html_sha256"]),
        reviewed_sop_html_sha256=str(metadata["reviewed_sop_html_sha256"]),
        reviewed_claim_digest=str(metadata["reviewed_claim_digest"]),
        signed_at=event.created_at,
        metadata=metadata,
    )


async def validate_review_signoff(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    signoff: ReviewSignoff,
    artifact: ReportArtifact,
    claim_snapshot: ClaimSnapshot,
    assignment: Any | None = None,
    now: datetime | None = None,
) -> list[GateFinding]:
    findings: list[GateFinding] = []
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    if assignment is None and artifact.report_id is not None:
        assignment = await get_active_reviewer_assignment(
            session,
            report_id=artifact.report_id,
            reviewer_user_id=signoff.reviewer_id,
        )
    if assignment is None or assignment.status != "active":
        findings.append(
            GateFinding(
                "reviewer_assignment_required",
                "内部审核人没有 active assignment",
                str(signoff.reviewer_id),
            )
        )
    else:
        if assignment.id != signoff.reviewer_assignment_id:
            findings.append(
                GateFinding(
                    "reviewer_assignment_invalid",
                    "审核事件的 assignment 与实际 active 行不一致",
                    str(signoff.reviewer_id),
                )
            )
        if assignment.assignment_scope != "report_review":
            findings.append(
                GateFinding(
                    "reviewer_assignment_invalid",
                    "assignment_scope 不是 report_review",
                    str(signoff.reviewer_id),
                )
            )
        if assignment.project_id != artifact.project_id:
            findings.append(
                GateFinding(
                    "reviewer_assignment_invalid",
                    "assignment 的项目与产物项目不一致",
                    str(signoff.reviewer_id),
                )
            )
        expires_at = getattr(assignment, "expires_at", None)
        if expires_at is not None and expires_at <= moment:
            findings.append(
                GateFinding(
                    "reviewer_assignment_expired",
                    "审阅者指派已过期",
                    str(signoff.reviewer_id),
                )
            )
    if signoff.reviewer_role != "internal_reviewer":
        findings.append(
            GateFinding(
                "reviewer_role_mismatch",
                "审核事件的 reviewer_role 必须是 internal_reviewer",
                str(signoff.reviewer_id),
            )
        )
    member_role = await get_workspace_role(
        session, workspace_id=workspace_id, user_id=signoff.reviewer_id
    )
    if member_role in {"owner", "admin"}:
        findings.append(
            GateFinding(
                "reviewer_self_review_forbidden",
                "客户 owner/admin 不得自审",
                str(signoff.reviewer_id),
            )
        )
    claim_owners = {
        str(claim.get("owner"))
        for claim in (artifact.contract_json.get("claims") or [])
        if claim.get("owner") is not None
    }
    if str(signoff.reviewer_id) in claim_owners:
        findings.append(
            GateFinding(
                "reviewer_is_claim_owner",
                "审核人不得是 Claim owner",
                str(signoff.reviewer_id),
            )
        )
    reviewer = await session.get(User, signoff.reviewer_id)
    if reviewer is None or reviewer.status != "active":
        findings.append(
            GateFinding(
                "reviewer_not_active",
                "审核人不存在或不是 active",
                str(signoff.reviewer_id),
            )
        )
    checks = (
        ("reviewed_contract_sha256", artifact.contract_sha256),
        ("reviewed_data_sha256", artifact.data_sha256),
        ("reviewed_report_html_sha256", artifact.report_html_sha256),
        ("reviewed_sop_html_sha256", artifact.sop_html_sha256),
        ("reviewed_claim_digest", claim_snapshot.digest),
    )
    for field, actual in checks:
        expected = getattr(signoff, field)
        if expected != actual:
            findings.append(
                GateFinding(
                    "review_signoff_stale",
                    f"{field} 与当前产物不一致，原签字失效",
                    field,
                )
            )
    return findings


__all__ = [
    "REQUIRED_SIGNOFF_KEYS",
    "ReviewSignoffInvalid",
    "load_latest_review_signoff",
    "validate_review_signoff",
]
```

- [ ] **Step 4: 写 `gates.py` 的 C7 Claim 快照与 G-Claim**

```python
# apps/api/src/data_intelligence_hub/services/delivery/gates.py
"""G-Claim 与 G-Publish 求值。纯规则层，不写库。"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.claim import ClaimState
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.repositories.claims import get_claim
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    contract_sha256,
    validate_contract,
)
from data_intelligence_hub.services.delivery.review import validate_review_signoff
from data_intelligence_hub.services.delivery.types import (
    ClaimSnapshot,
    ClaimSnapshotRow,
    DatasetInput,
    DeliveryFile,
    DeliveryManifest,
    GateDecision,
    GateFinding,
    ReviewSignoff,
)
from data_intelligence_hub.services.report_publication import claim_review_digest


def _finding(code: str, message: str, subject_id: str | None = None) -> GateFinding:
    return GateFinding(code=code, message=message, subject_id=subject_id)


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def load_claim_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    contract: Mapping[str, Any],
) -> ClaimSnapshot:
    """加载 C7 的 publishable bundle，并标出合同中不可发布的 Claim。"""
    from data_intelligence_hub.services.claims import (
        load_publishable_claim_rows,
        validate_claim_bundle,
    )

    bundle = await load_publishable_claim_rows(
        session, workspace_id=workspace_id, project_id=project_id
    )
    rows: list[ClaimSnapshotRow] = []
    for row in bundle.claims:
        rows.append(
            ClaimSnapshotRow(
                claim_id=uuid.UUID(row.claim_id),
                claim_text=row.text,
                state=row.claim_status.value,
                evidence_grade=row.evidence_grade.value if row.evidence_grade else None,
                run_id=None,
                roles=tuple(
                    sorted(
                        {
                            evidence.role.value
                            for evidence in bundle.evidences
                            if evidence.claim_id == row.claim_id
                        }
                    )
                ),
                evidence_ids=tuple(uuid.UUID(value) for value in row.evidence_ids),
            )
        )
    review_findings: list[GateFinding] = []
    publishable_ids = {row.claim_id for row in bundle.claims}
    for claim in contract.get("claims") or []:
        claim_id = _uuid(claim.get("claim_id"))
        if claim_id is None or str(claim_id) in publishable_ids:
            continue
        db_claim = await get_claim(session, workspace_id=workspace_id, claim_id=claim_id)
        if db_claim is None:
            review_findings.append(
                _finding("claim_missing_in_database", "合同中的 Claim 在数据库不存在", str(claim_id))
            )
            continue
        status = str(getattr(db_claim, "review_status", "draft"))
        if status == "pending":
            review_findings.append(
                _finding("claim_review_pending", "Claim 仍在审核中，不能交付", str(claim_id))
            )
        elif status == "stale":
            review_findings.append(
                _finding("claim_review_stale", "Claim 审核后已修改，原签字失效", str(claim_id))
            )
        else:
            review_findings.append(
                _finding("claim_not_approved", f"Claim 审核状态为 {status}，不能交付", str(claim_id))
            )
    for issue in validate_claim_bundle(bundle):
        review_findings.append(_finding("claim_bundle_not_publishable", issue))
    return ClaimSnapshot(
        rows=tuple(rows),
        digest=claim_review_digest(contract),
        bundle=bundle,
        review_findings=tuple(review_findings),
    )


async def evaluate_g_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
    package_type: str = "standard",
) -> GateDecision:
    from data_intelligence_hub.services.claim_semantics import validate_claim_semantics
    from data_intelligence_hub.services.claims import validate_claim_bundle

    findings: list[GateFinding] = list(claim_snapshot.review_findings)
    try:
        model = ReportContract.model_validate(contract)
    except ValidationError as exc:
        findings.append(_finding("contract_invalid", f"报告合同结构非法：{exc}"))
        return GateDecision(
            gate_id="G-Claim",
            status="fail",
            findings=tuple(findings),
            checked_at=datetime.now(UTC),
            subject_digest=claim_snapshot.digest,
        )
    issues = validate_contract(model)
    findings.extend(_finding("contract_semantic_invalid", issue) for issue in issues)
    if contract_sha256(contract) != artifact.contract_sha256:
        findings.append(
            _finding("artifact_contract_hash_mismatch", "产物的 contract_sha256 与合同不一致")
        )
    bundle = claim_snapshot.bundle
    if bundle is None:
        findings.append(_finding("claim_bundle_missing", "没有 C7 publishable Claim bundle"))
    else:
        findings.extend(
            _finding("claim_bundle_not_publishable", issue)
            for issue in validate_claim_bundle(bundle)
        )
        findings.extend(
            _finding("claim_semantics_invalid", issue)
            for issue in validate_claim_semantics(
                bundle,
                markets=[market.model_dump(mode="json") for market in model.markets],
                package_type=package_type,
            )
        )
    bundle_by_id = {row.claim_id: row for row in (bundle.claims if bundle is not None else ())}
    bundle_evidence_roles: dict[str, set[str]] = {}
    if bundle is not None:
        for evidence in bundle.evidences:
            bundle_evidence_roles.setdefault(evidence.claim_id, set()).add(evidence.role.value)
    contract_ids: set[uuid.UUID] = set()
    for claim in model.claims:
        claim_id = _uuid(claim.claim_id)
        if claim_id is None:
            findings.append(_finding("claim_id_not_uuid", f"claim_id 不是 UUID：{claim.claim_id}"))
            continue
        contract_ids.add(claim_id)
        row = bundle_by_id.get(str(claim_id))
        if row is None:
            findings.append(
                _finding(
                    "claim_not_publishable",
                    "合同中的 Claim 不在 C7 publishable bundle；pending/stale 一律拒绝",
                    claim.claim_id,
                )
            )
            continue
        if row.text != claim.text:
            findings.append(_finding("claim_text_mismatch", "Claim 文本与数据库不一致", claim.claim_id))
        if row.claim_status.value != claim.claim_status.value:
            findings.append(_finding("claim_state_mismatch", "Claim 状态与数据库不一致", claim.claim_id))
        expected_grade = row.evidence_grade.value if row.evidence_grade else None
        if expected_grade != claim.evidence_grade.value:
            findings.append(_finding("claim_grade_mismatch", "Claim 证据等级与数据库不一致", claim.claim_id))
        if not bundle_evidence_roles.get(str(claim_id), set()) & {"counter", "gap"}:
            findings.append(
                _finding("claim_counter_evidence_missing", "Claim 缺少 counter 或 gap 证据", claim.claim_id)
            )
        if package_type == "quick" and claim.claim_status is ClaimState.CONFIRMED:
            findings.append(
                _finding("quick_draft_claim_invalid", "Quick 2 小时稿不得出现 confirmed", claim.claim_id)
            )
    for row in claim_snapshot.rows:
        if row.claim_id not in contract_ids:
            findings.append(
                _finding("claim_missing_from_contract", "数据库中的 Claim 未进入合同", str(row.claim_id))
            )
    return GateDecision(
        gate_id="G-Claim",
        status="fail" if findings else "pass",
        findings=tuple(findings),
        checked_at=datetime.now(UTC),
        subject_digest=claim_snapshot.digest,
    )
```

`test_delivery_gates.py`：

```python
# apps/api/tests/unit/test_delivery_gates.py
from datetime import UTC, datetime

from data_intelligence_hub.models.claim import Claim
from data_intelligence_hub.services.delivery.gates import (
    evaluate_g_claim,
    load_claim_snapshot,
)


async def test_load_claim_snapshot_uses_c7_publishable_bundle(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    assert len(snapshot.rows) == 1
    assert snapshot.bundle is not None
    assert snapshot.review_findings == ()
    assert len(snapshot.digest) == 64


async def test_g_claim_passes_for_approved_bundle(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    decision = await evaluate_g_claim(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact=delivery_seed.artifact,
        contract=delivery_seed.contract,
        claim_snapshot=snapshot,
    )
    assert decision.status == "pass", decision.findings


async def test_g_claim_rejects_pending_claim(session, delivery_seed) -> None:
    claim = await session.get(Claim, delivery_seed.contract["claims"][0]["claim_id"])
    claim.review_status = "pending"
    await session.flush()
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    decision = await evaluate_g_claim(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact=delivery_seed.artifact,
        contract=delivery_seed.contract,
        claim_snapshot=snapshot,
    )
    assert decision.status == "fail"
    assert any(f.code == "claim_review_pending" for f in decision.findings)


async def test_g_claim_rejects_stale_claim(session, delivery_seed) -> None:
    claim = await session.get(Claim, delivery_seed.contract["claims"][0]["claim_id"])
    claim.review_status = "stale"
    await session.flush()
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    decision = await evaluate_g_claim(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact=delivery_seed.artifact,
        contract=delivery_seed.contract,
        claim_snapshot=snapshot,
    )
    assert decision.status == "fail"
    assert any(f.code == "claim_review_stale" for f in decision.findings)


async def test_quick_rejects_confirmed_and_standard_four_state(session, delivery_seed) -> None:
    snapshot = await load_claim_snapshot(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        contract=delivery_seed.contract,
    )
    decision = await evaluate_g_claim(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact=delivery_seed.artifact,
        contract=delivery_seed.contract,
        claim_snapshot=snapshot,
        package_type="quick",
    )
    assert decision.status == "fail"
    assert any(f.code == "claim_semantics_invalid" for f in decision.findings)
```

`Claim` 需要从 `data_intelligence_hub.models.claim` 导入；`Claim` 对象在 `delivery_seed` 中已创建。测试文件顶部补 `from data_intelligence_hub.models.claim import Claim`。

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_review.py tests/unit/test_delivery_gates.py -v
```

Expected: `9 passed`。若 `load_publishable_claim_rows` 返回空，先检查 `review_status='approved'` 与 `reviewed_content_version == content_version`；不得放宽 G-Claim。

- [ ] **Step 5: 写 G-Publish**

```python
# 追加到 apps/api/src/data_intelligence_hub/services/delivery/gates.py
# 顶部同时导入：
# from data_intelligence_hub.services.delivery.manifest import (
#     FORMAL_REQUIRED_ROLES,
#     QUICK_DRAFT_REQUIRED_ROLES,
# )
# from data_intelligence_hub.services.export_policy import PiiHit


async def evaluate_g_publish(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
    g_claim: GateDecision,
    signoff: ReviewSignoff | None,
    dataset: DatasetInput,
    files: Sequence[DeliveryFile],
    manifest: DeliveryManifest,
    acceptance_snapshot: DeliveryFile | None,
    now: datetime,
    delivery_class: str = "formal",
    require_published: bool = True,
    pii_hits: Sequence[PiiHit] = (),
    signoff_artifact: ReportArtifact | None = None,
) -> GateDecision:
    findings: list[GateFinding] = []
    source = signoff_artifact or artifact
    if delivery_class not in {"formal", "quick_draft"}:
        findings.append(_finding("delivery_class_invalid", "交付类别非法"))
    if require_published and source.status != "published":
        findings.append(
            _finding("artifact_not_published", "C9 报告产物尚未发布，不能生成正式交付包")
        )
    if delivery_class == "quick_draft" and source.status not in {"draft", "published"}:
        findings.append(
            _finding("quick_draft_source_invalid", "Quick 2 小时稿只能来自 draft/published 产物")
        )
    if not g_claim.passed:
        findings.append(_finding("g_claim_not_passed", "G-Claim 未通过，不能发布"))
    if not artifact.report_html:
        findings.append(_finding("report_html_missing", "报告 HTML 为空"))
    if not artifact.sop_html:
        findings.append(_finding("sop_html_missing", "SOP HTML 为空"))
    try:
        model = ReportContract.model_validate(contract)
    except ValidationError as exc:
        findings.append(_finding("contract_invalid", f"报告合同结构非法：{exc}"))
        model = None
    if model is not None:
        mismatches = verify_artifact(
            artifact,
            model,
            artifact.report_html or "",
            artifact.sop_html or "",
        )
        findings.extend(_finding("artifact_hash_mismatch", item) for item in mismatches)
    if pii_hits:
        findings.append(
            _finding(
                "delivery_pii_detected",
                f"PII 扫描命中 {len(pii_hits)} 项，不能发布",
            )
        )
    if delivery_class == "formal":
        if signoff is None:
            findings.append(_finding("review_signoff_missing", "没有审核签字，不能发布"))
        else:
            findings.extend(
                await validate_review_signoff(
                    session,
                    workspace_id=workspace_id,
                    signoff=signoff,
                    artifact=source,
                    claim_snapshot=claim_snapshot,
                )
            )
        if acceptance_snapshot is None:
            findings.append(_finding("acceptance_snapshot_missing", "正式交付缺少验收快照"))
        else:
            snapshot_entry = next(
                (file for file in files if file.path == acceptance_snapshot.path),
                None,
            )
            if snapshot_entry is None:
                findings.append(_finding("acceptance_snapshot_missing", "验收快照不在文件清单中"))
        required_roles = FORMAL_REQUIRED_ROLES
    else:
        if acceptance_snapshot is not None:
            findings.append(
                _finding("acceptance_not_applicable", "Quick 2 小时稿不得包含验收快照")
            )
        required_roles = QUICK_DRAFT_REQUIRED_ROLES
    if not dataset.rows:
        findings.append(_finding("dataset_empty", "交付数据集为空"))
    if len(dataset.rows) != dataset.metadata.row_count:
        findings.append(_finding("dataset_row_count_mismatch", "数据集行数与元数据不一致"))
    roles = {file.role for file in files}
    missing_roles = [role.value for role in required_roles if role not in roles]
    if missing_roles:
        findings.append(
            _finding("delivery_files_missing", "交付文件角色缺失：" + "、".join(missing_roles))
        )
    if len(manifest.sha256) != 64:
        findings.append(_finding("manifest_hash_invalid", "manifest 哈希不是 64 位"))
    if len(manifest.sidecar_sha256) != 64:
        findings.append(_finding("manifest_sidecar_hash_invalid", "sidecar 哈希不是 64 位"))
    return GateDecision(
        gate_id="G-Publish",
        status="fail" if findings else "pass",
        findings=tuple(findings),
        checked_at=now,
        subject_digest=manifest.sha256,
    )
```

- [ ] **Step 6: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_review.py tests/unit/test_delivery_gates.py -v
```

Expected: `9 passed`。签字测试通过；无 active assignment 命中 `reviewer_assignment_required`，过期指派命中 `reviewer_assignment_expired`，客户 owner/admin 自审命中 `reviewer_self_review_forbidden`；G-Claim 使用 C7 publishable bundle，pending 命中 `claim_review_pending`，stale 命中 `claim_review_stale`，Quick 命中 `claim_semantics_invalid` / `quick_draft_claim_invalid`。不得放宽 `validate_review_signoff`。

- [ ] **Step 7: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/review.py src/data_intelligence_hub/services/delivery/gates.py tests/unit/test_delivery_review.py tests/unit/test_delivery_gates.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/review.py src/data_intelligence_hub/services/delivery/gates.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/review.py \
  apps/api/src/data_intelligence_hub/services/delivery/gates.py \
  apps/api/tests/unit/conftest.py \
  apps/api/tests/unit/test_delivery_review.py \
  apps/api/tests/unit/test_delivery_gates.py
git commit -m "feat(delivery): add review signoff reader and claim/publish gates"
```

---

### Task 6: Manifest、Sidecar 与文件清单

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/manifest.py`
- Test: `apps/api/tests/unit/test_delivery_manifest.py`

**Interfaces:**
- Consumes: `DeliveryFile`、`DeliveryManifest`、`canonical_bytes`、`canonical_sha256`、`sha256_hex`、C1 的 `configs/contracts/v1.1.0/delivery_manifest.schema.json`。
- Produces: `FORMAL_REQUIRED_ROLES`、`QUICK_DRAFT_REQUIRED_ROLES`、`MANIFEST_NAME`、`SIDECAR_NAME`、`bundle_sha256`、`content_bundle_sha256`、`build_manifest`、`verify_manifest_file`。

- [ ] **Step 1: 写 manifest 失败测试**

Create `apps/api/tests/unit/test_delivery_manifest.py`。测试同时断言 C1 JSON Schema。`DeliveryFile.role` 只在内存中用于完整性校验，不进入 manifest：

```python
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from data_intelligence_hub.services.delivery.manifest import (
    MANIFEST_NAME,
    QUICK_DRAFT_REQUIRED_ROLES,
    SIDECAR_NAME,
    build_manifest,
    content_bundle_sha256,
    verify_manifest_file,
)
from data_intelligence_hub.services.delivery.types import (
    DeliveryFile,
    DeliveryFileRole,
)

ARTIFACT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
MANIFEST_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TASK_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from scripts.contract_registry import validate_json_document

MANIFEST_SCHEMA = json.loads(
    (REPO_ROOT / "configs/contracts/v1.1.0/delivery_manifest.schema.json").read_text(
        encoding="utf-8"
    )
)


def _content_files() -> tuple[DeliveryFile, ...]:
    names = {
        DeliveryFileRole.REPORT_ZH: "report.zh.html",
        DeliveryFileRole.EXECUTIVE_SUMMARY_EN: "executive_summary.en.md",
        DeliveryFileRole.DATASET: "dataset.csv",
        DeliveryFileRole.DATA_DICTIONARY: "data_dictionary.json",
        DeliveryFileRole.QUALITY_SCORECARD: "quality_scorecard.json",
        DeliveryFileRole.CLAIM_EVIDENCE_INDEX: "claim_evidence_index.csv",
        DeliveryFileRole.RUN_RECEIPT: "run_receipt.json",
        DeliveryFileRole.REPORT_CONTRACT: "report_contract.json",
        DeliveryFileRole.LIMITS_AND_GAPS: "limits_and_gaps.json",
    }
    return tuple(
        DeliveryFile(
            role=role,
            path=path,
            media_type="application/octet-stream",
            content=role.value.encode(),
        )
        for role, path in names.items()
    )


def _all_files() -> tuple[DeliveryFile, ...]:
    return (
        *_content_files(),
        DeliveryFile(
            role=DeliveryFileRole.ACCEPTANCE_SNAPSHOT,
            path="acceptance_snapshot.json",
            media_type="application/json",
            content=b'{"status":"pending"}\n',
        ),
    )


def _build(files: tuple[DeliveryFile, ...], *, report_version: int = 2):
    return build_manifest(
        manifest_id=MANIFEST_ID,
        artifact_id=ARTIFACT_ID,
        task_id=TASK_ID,
        report_version=report_version,
        files=files,
        access_scope=["workspace_project"],
        retention_class="standard_24m",
        created_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
    )


def test_manifest_matches_c1_schema_and_exact_keys() -> None:
    manifest = _build(_all_files())
    assert set(manifest.payload) == {
        "schema_version",
        "manifest_id",
        "task_id",
        "report_artifact_id",
        "report_version",
        "created_at",
        "files",
        "bundle_sha256",
        "sidecar_sha256",
        "access_scope",
        "retention_class",
    }
    assert manifest.payload["schema_version"] == "delivery-manifest.v1"
    assert manifest.payload["report_version"] == 2
    assert isinstance(manifest.payload["report_version"], int)
    assert manifest.payload["report_artifact_id"] == str(ARTIFACT_ID)
    assert manifest.payload["task_id"] == str(TASK_ID)
    assert manifest.payload["created_at"] == "2026-10-22T10:00:00Z"
    assert validate_json_document(manifest.payload, MANIFEST_SCHEMA) == []
    assert "manifest_version" not in manifest.payload
    assert "artifact_id" not in manifest.payload
    assert "content_files_digest" not in manifest.payload


def test_file_entries_have_only_four_schema_keys() -> None:
    manifest = _build(_all_files())
    assert len(manifest.payload["files"]) == 10
    for entry in manifest.payload["files"]:
        assert set(entry) == {"path", "sha256", "size_bytes", "media_type"}
        assert "role" not in entry
    assert [entry["path"] for entry in manifest.payload["files"]] == sorted(
        entry["path"] for entry in manifest.payload["files"]
    )


def test_sidecar_hashes_manifest_and_bundle_hash_is_stable() -> None:
    manifest = _build(_all_files())
    assert manifest.sidecar_bytes == (
        f"{manifest.sha256}  {MANIFEST_NAME}\n".encode("ascii")
    )
    assert manifest.payload["sidecar_sha256"] == hashlib.sha256(
        manifest.sidecar_bytes
    ).hexdigest()
    from data_intelligence_hub.services.delivery.manifest import bundle_sha256

    assert manifest.payload["bundle_sha256"] == bundle_sha256(_all_files())
    assert content_bundle_sha256(_all_files()) != manifest.payload["bundle_sha256"]


def test_manifest_paths_must_be_relative_and_unique() -> None:
    files = list(_all_files())
    files.append(
        DeliveryFile(
            role=DeliveryFileRole.REPORT_ZH,
            path="../escape.html",
            media_type="text/html",
            content=b"x",
        )
    )
    with pytest.raises(ValueError, match="路径"):
        _build(tuple(files))


def test_manifest_requires_all_roles() -> None:
    with pytest.raises(ValueError, match="缺少交付角色"):
        _build(_content_files())


def test_quick_draft_manifest_uses_notice_instead_of_snapshot() -> None:
    quick_files = (
        *_content_files(),
        DeliveryFile(
            role=DeliveryFileRole.QUICK_DRAFT_NOTICE,
            path="quick_draft_notice.json",
            media_type="application/json",
            content=b'{"delivery_class":"quick_draft"}\n',
        ),
    )
    manifest = build_manifest(
        manifest_id=MANIFEST_ID,
        artifact_id=ARTIFACT_ID,
        task_id=TASK_ID,
        report_version=1,
        files=quick_files,
        access_scope=["workspace_project"],
        retention_class="standard_24m",
        created_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
        required_roles=QUICK_DRAFT_REQUIRED_ROLES,
    )
    assert len(manifest.payload["files"]) == 10
    assert validate_json_document(manifest.payload, MANIFEST_SCHEMA) == []
    assert "acceptance_snapshot.json" not in {
        entry["path"] for entry in manifest.payload["files"]
    }
    with pytest.raises(ValueError, match="缺少交付角色"):
        build_manifest(
            manifest_id=MANIFEST_ID,
            artifact_id=ARTIFACT_ID,
            task_id=TASK_ID,
            report_version=1,
            files=_content_files(),
            access_scope=["workspace_project"],
            retention_class="standard_24m",
            created_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
            required_roles=QUICK_DRAFT_REQUIRED_ROLES,
        )


def test_verify_manifest_rejects_noncanonical_bytes() -> None:
    manifest = _build(_all_files())
    pretty = json.dumps(manifest.payload, ensure_ascii=False, indent=2).encode()
    mismatches = verify_manifest_file(
        pretty,
        expected_sha256=manifest.sha256,
        sidecar_bytes=manifest.sidecar_bytes,
    )
    assert "manifest_not_canonical" in {item.reason for item in mismatches}
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_manifest.py -v
```

Expected: `ModuleNotFoundError` 或 `ImportError: content_bundle_sha256`。

- [ ] **Step 3: 写实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/manifest.py
"""manifest、sidecar 与文件路径校验。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Final
import uuid

from data_intelligence_hub.services.delivery.canonical import (
    canonical_bytes,
    canonical_sha256,
    sha256_hex,
)
from data_intelligence_hub.services.delivery.types import (
    BundleMismatch,
    DeliveryFile,
    DeliveryFileRole,
    DeliveryManifest,
)

MANIFEST_NAME: Final[str] = "delivery_manifest.json"
SIDECAR_NAME: Final[str] = "delivery_manifest.sha256"
ACCEPTANCE_SNAPSHOT_PATH: Final[str] = "acceptance_snapshot.json"
QUICK_DRAFT_NOTICE_PATH: Final[str] = "quick_draft_notice.json"
MANIFEST_SCHEMA_VERSION: Final[str] = "delivery-manifest.v1"
MANIFEST_DIGEST_EXCLUDED_KEYS: Final[frozenset[str]] = frozenset({"sidecar_sha256"})

_CONTENT_ROLES: tuple[DeliveryFileRole, ...] = (
    DeliveryFileRole.REPORT_ZH,
    DeliveryFileRole.EXECUTIVE_SUMMARY_EN,
    DeliveryFileRole.DATASET,
    DeliveryFileRole.DATA_DICTIONARY,
    DeliveryFileRole.QUALITY_SCORECARD,
    DeliveryFileRole.CLAIM_EVIDENCE_INDEX,
    DeliveryFileRole.RUN_RECEIPT,
    DeliveryFileRole.REPORT_CONTRACT,
    DeliveryFileRole.LIMITS_AND_GAPS,
)

FORMAL_REQUIRED_ROLES: tuple[DeliveryFileRole, ...] = (
    *_CONTENT_ROLES,
    DeliveryFileRole.ACCEPTANCE_SNAPSHOT,
)

QUICK_DRAFT_REQUIRED_ROLES: tuple[DeliveryFileRole, ...] = (
    *_CONTENT_ROLES,
    DeliveryFileRole.QUICK_DRAFT_NOTICE,
)


def _validate_path(path: str) -> None:
    parsed = PurePosixPath(path)
    if not path or path != str(parsed):
        raise ValueError(f"交付文件路径非法：{path!r}")
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in path:
        raise ValueError(f"交付文件路径必须是相对 POSIX 路径：{path!r}")
    if path in {MANIFEST_NAME, SIDECAR_NAME}:
        raise ValueError(f"manifest 与 sidecar 不得列入 files：{path}")
    if len(path) > 128:
        raise ValueError(f"交付文件路径过长：{path!r}")


def _validate_files(
    files: Sequence[DeliveryFile],
    *,
    require_all_roles: bool = True,
    required_roles: Sequence[DeliveryFileRole] = FORMAL_REQUIRED_ROLES,
) -> None:
    seen_paths: set[str] = set()
    seen_roles: set[DeliveryFileRole] = set()
    for file in files:
        _validate_path(file.path)
        if file.path in seen_paths:
            raise ValueError(f"交付文件路径重复：{file.path}")
        if file.role in seen_roles:
            raise ValueError(f"交付文件角色重复：{file.role.value}")
        seen_paths.add(file.path)
        seen_roles.add(file.role)
    if require_all_roles:
        missing = [role.value for role in required_roles if role not in seen_roles]
        if missing:
            raise ValueError("缺少交付角色：" + "、".join(missing))


def _manifest_entries(files: Sequence[DeliveryFile]) -> list[dict[str, Any]]:
    entries = [
        {
            "path": file.path,
            "sha256": sha256_hex(file.content),
            "size_bytes": len(file.content),
            "media_type": file.media_type,
        }
        for file in files
    ]
    entries.sort(key=lambda item: item["path"])
    return entries


def manifest_digest(payload: Mapping[str, Any]) -> str:
    """manifest 摘要排除 sidecar_sha256，避免 manifest/sidecar 哈希环。"""
    normalized = {
        key: value
        for key, value in payload.items()
        if key not in MANIFEST_DIGEST_EXCLUDED_KEYS
    }
    return sha256_hex(canonical_bytes(normalized))


def bundle_sha256(files: Sequence[DeliveryFile]) -> str:
    """全部交付文件的 canonical 清单摘要，写入 manifest。"""
    _validate_files(files, require_all_roles=False)
    return canonical_sha256({"files": _manifest_entries(files)})


def content_bundle_sha256(files: Sequence[DeliveryFile]) -> str:
    """内容文件摘要；排除验收快照与 Quick 通知，避免自引用。"""
    _validate_files(files, require_all_roles=False)
    entries = [
        entry
        for entry in _manifest_entries(files)
        if entry["path"] not in {ACCEPTANCE_SNAPSHOT_PATH, QUICK_DRAFT_NOTICE_PATH}
    ]
    return canonical_sha256({"files": entries})


def build_manifest(
    *,
    manifest_id: uuid.UUID,
    artifact_id: uuid.UUID,
    task_id: uuid.UUID,
    report_version: int,
    files: Sequence[DeliveryFile],
    access_scope: Sequence[str],
    retention_class: str,
    created_at: datetime,
    required_roles: Sequence[DeliveryFileRole] = FORMAL_REQUIRED_ROLES,
) -> DeliveryManifest:
    _validate_files(files, required_roles=required_roles)
    if report_version < 1:
        raise ValueError("report_version 必须大于等于 1")
    if not access_scope:
        raise ValueError("access_scope 不能为空")
    entries = _manifest_entries(files)
    payload: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": str(manifest_id),
        "task_id": str(task_id),
        "report_artifact_id": str(artifact_id),
        "report_version": int(report_version),
        "created_at": created_at.astimezone(UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": entries,
        "bundle_sha256": bundle_sha256(files),
        "access_scope": list(access_scope),
        "retention_class": retention_class,
    }
    digest = manifest_digest(payload)
    sidecar = f"{digest}  {MANIFEST_NAME}\n".encode("ascii")
    payload["sidecar_sha256"] = sha256_hex(sidecar)
    body = canonical_bytes(payload)
    return DeliveryManifest(
        payload=payload,
        canonical_bytes=body,
        sha256=digest,
        sidecar_bytes=sidecar,
        sidecar_sha256=sha256_hex(sidecar),
    )


def verify_manifest_file(
    manifest_bytes: bytes,
    *,
    expected_sha256: str,
    sidecar_bytes: bytes,
) -> list[BundleMismatch]:
    mismatches: list[BundleMismatch] = []
    try:
        parsed = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        mismatches.append(BundleMismatch(path=MANIFEST_NAME, reason="manifest_not_json"))
        return mismatches
    if not isinstance(parsed, dict):
        mismatches.append(BundleMismatch(path=MANIFEST_NAME, reason="manifest_not_object"))
        return mismatches
    actual = manifest_digest(parsed)
    if actual != expected_sha256:
        mismatches.append(
            BundleMismatch(
                path=MANIFEST_NAME,
                reason="manifest_sha256_mismatch",
                expected=expected_sha256,
                actual=actual,
            )
        )
    if canonical_bytes(parsed) != manifest_bytes:
        mismatches.append(BundleMismatch(path=MANIFEST_NAME, reason="manifest_not_canonical"))
    expected_sidecar = f"{expected_sha256}  {MANIFEST_NAME}\n".encode("ascii")
    if sidecar_bytes != expected_sidecar:
        mismatches.append(
            BundleMismatch(
                path=SIDECAR_NAME,
                reason="sidecar_bytes_mismatch",
                expected=expected_sidecar.decode("ascii"),
                actual=sidecar_bytes.decode("utf-8", errors="replace"),
            )
        )
    return mismatches


__all__ = [
    "ACCEPTANCE_SNAPSHOT_PATH",
    "FORMAL_REQUIRED_ROLES",
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA_VERSION",
    "QUICK_DRAFT_NOTICE_PATH",
    "QUICK_DRAFT_REQUIRED_ROLES",
    "SIDECAR_NAME",
    "build_manifest",
    "bundle_sha256",
    "content_bundle_sha256",
    "manifest_digest",
    "verify_manifest_file",
]
```

注意 `sidecar_sha256` 也是 manifest 的受保护字段；实现先放入占位 `sidecar_sha256` 计算 sidecar，再重算 manifest 哈希，避免自引用循环。`bundle_sha256` 是全部 10 个文件的 canonical 清单摘要，`content_bundle_sha256` 只用于验收快照，排除快照自身。

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_manifest.py -v
```

Expected: `7 passed`。任一 schema 断言失败表示 manifest 与 C1 的 `delivery_manifest.schema.json` 漂移。Quick 稿仍必须有 10 个文件，但第 10 个是 `quick_draft_notice.json`，不是验收快照。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/manifest.py tests/unit/test_delivery_manifest.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/manifest.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/manifest.py \
  apps/api/tests/unit/test_delivery_manifest.py
git commit -m "feat(delivery): emit c1 delivery manifest schema"
```

### Task 7: 本地交付存储、篡改检测与 ZIP

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/store.py`
- Test: `apps/api/tests/unit/test_delivery_store.py`

**Interfaces:**
- Consumes: `DeliveryFile`、`DeliveryManifest`、`MANIFEST_NAME`、`SIDECAR_NAME`、`sha256_hex`。
- Produces: `DeliveryStore`。

- [ ] **Step 1: 写存储失败测试**

```python
# apps/api/tests/unit/test_delivery_store.py
import io
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from data_intelligence_hub.services.delivery.manifest import MANIFEST_NAME, SIDECAR_NAME
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.delivery.types import (
    DatasetInput,
    DeliveryFile,
    DeliveryFileRole,
    DeliveryManifest,
)

WORKSPACE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ARTIFACT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _files() -> tuple[DeliveryFile, ...]:
    names = {
        DeliveryFileRole.REPORT_ZH: "report.zh.html",
        DeliveryFileRole.EXECUTIVE_SUMMARY_EN: "executive_summary.en.md",
        DeliveryFileRole.DATASET: "dataset.csv",
        DeliveryFileRole.DATA_DICTIONARY: "data_dictionary.json",
        DeliveryFileRole.QUALITY_SCORECARD: "quality_scorecard.json",
        DeliveryFileRole.CLAIM_EVIDENCE_INDEX: "claim_evidence_index.csv",
        DeliveryFileRole.RUN_RECEIPT: "run_receipt.json",
        DeliveryFileRole.REPORT_CONTRACT: "report_contract.json",
        DeliveryFileRole.LIMITS_AND_GAPS: "limits_and_gaps.json",
        DeliveryFileRole.ACCEPTANCE_SNAPSHOT: "acceptance_snapshot.json",
    }
    return tuple(
        DeliveryFile(
            role=role,
            path=path,
            media_type="application/octet-stream",
            content=role.value.encode("utf-8"),
        )
        for role, path in names.items()
    )


def _manifest() -> DeliveryManifest:
    from data_intelligence_hub.services.delivery.manifest import build_manifest

    return build_manifest(
        manifest_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        artifact_id=ARTIFACT_ID,
        task_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        report_version=2,
        files=_files(),
        access_scope=["workspace_project"],
        retention_class="standard_24m",
        created_at=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
    )


def test_write_and_verify_clean_bundle(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path)
    manifest = _manifest()
    store.write_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        files=_files(),
        manifest=manifest,
    )
    assert store.verify_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        manifest=manifest,
        expected_manifest_sha256=manifest.sha256,
        expected_sidecar_sha256=manifest.sidecar_sha256,
    ) == []


def test_tampered_file_is_detected(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path)
    manifest = _manifest()
    store.write_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        files=_files(),
        manifest=manifest,
    )
    target = store.bundle_dir(WORKSPACE_ID, ARTIFACT_ID) / "report.zh.html"
    target.write_bytes(target.read_bytes() + b"x")
    mismatches = store.verify_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        manifest=manifest,
        expected_manifest_sha256=manifest.sha256,
        expected_sidecar_sha256=manifest.sidecar_sha256,
    )
    assert "sha256_mismatch" in {item.reason for item in mismatches}


def test_missing_extra_and_symlink_are_detected(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path)
    manifest = _manifest()
    bundle = store.write_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        files=_files(),
        manifest=manifest,
    )
    (bundle / "report.zh.html").unlink()
    (bundle / "extra.txt").write_text("extra")
    (bundle / "link.txt").symlink_to(bundle / "extra.txt")
    reasons = {
        item.reason
        for item in store.verify_bundle(
            workspace_id=WORKSPACE_ID,
            artifact_id=ARTIFACT_ID,
            manifest=manifest,
            expected_manifest_sha256=manifest.sha256,
            expected_sidecar_sha256=manifest.sidecar_sha256,
        )
    }
    assert {"missing_file", "unexpected_file", "symlink_not_allowed"} <= reasons


def test_tampered_manifest_and_sidecar_are_detected(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path)
    manifest = _manifest()
    bundle = store.write_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        files=_files(),
        manifest=manifest,
    )
    (bundle / MANIFEST_NAME).write_bytes(b"{}")
    (bundle / SIDECAR_NAME).write_bytes(b"wrong\n")
    reasons = {
        item.reason
        for item in store.verify_bundle(
            workspace_id=WORKSPACE_ID,
            artifact_id=ARTIFACT_ID,
            manifest=manifest,
            expected_manifest_sha256=manifest.sha256,
            expected_sidecar_sha256=manifest.sidecar_sha256,
        )
    }
    assert {"manifest_sha256_mismatch", "sidecar_sha256_mismatch"} <= reasons


def test_zip_contains_manifest_and_sidecar(tmp_path: Path) -> None:
    store = DeliveryStore(tmp_path)
    manifest = _manifest()
    store.write_bundle(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        files=_files(),
        manifest=manifest,
    )
    data = store.build_zip(
        workspace_id=WORKSPACE_ID,
        artifact_id=ARTIFACT_ID,
        manifest=manifest,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert set(archive.namelist()) == {
            "report.zh.html",
            "executive_summary.en.md",
            "dataset.csv",
            "data_dictionary.json",
            "quality_scorecard.json",
            "claim_evidence_index.csv",
            "run_receipt.json",
            "report_contract.json",
            "limits_and_gaps.json",
            "acceptance_snapshot.json",
            MANIFEST_NAME,
            SIDECAR_NAME,
        }
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_store.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.services.delivery.store'`。

- [ ] **Step 3: 写实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/store.py
"""本地交付目录的原子写、校验与 ZIP。"""

from __future__ import annotations

import io
import json
import os
import shutil
import uuid
import zipfile
from collections.abc import Sequence
from pathlib import Path

from data_intelligence_hub.services.delivery.canonical import sha256_hex
from data_intelligence_hub.services.delivery.manifest import (
    MANIFEST_NAME,
    SIDECAR_NAME,
    manifest_digest,
)
from data_intelligence_hub.services.delivery.types import (
    BundleMismatch,
    DeliveryFile,
    DeliveryManifest,
)


class DeliveryStoreConflict(RuntimeError):
    """目标交付目录已存在。"""


class DeliveryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def bundle_dir(self, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Path:
        return self.root / str(workspace_id) / str(artifact_id)

    def write_bundle(
        self,
        *,
        workspace_id: uuid.UUID,
        artifact_id: uuid.UUID,
        files: Sequence[DeliveryFile],
        manifest: DeliveryManifest,
    ) -> Path:
        final = self.bundle_dir(workspace_id, artifact_id)
        if final.exists():
            raise DeliveryStoreConflict(f"交付目录已存在：{final}")
        staging = self.root / ".staging" / str(uuid.uuid4())
        staging.mkdir(parents=True, exist_ok=False)
        try:
            for file in files:
                target = staging / file.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(file.content)
                with target.open("rb") as handle:
                    os.fsync(handle.fileno())
            (staging / MANIFEST_NAME).write_bytes(manifest.canonical_bytes)
            (staging / SIDECAR_NAME).write_bytes(manifest.sidecar_bytes)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return final

    def remove_bundle(self, *, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> None:
        shutil.rmtree(self.bundle_dir(workspace_id, artifact_id), ignore_errors=True)

    def _relative_files(self, bundle: Path) -> dict[str, Path]:
        actual: dict[str, Path] = {}
        for path in bundle.rglob("*"):
            if path.is_symlink():
                actual[path.relative_to(bundle).as_posix()] = path
                continue
            if path.is_file():
                actual[path.relative_to(bundle).as_posix()] = path
        return actual

    def verify_bundle(
        self,
        *,
        workspace_id: uuid.UUID,
        artifact_id: uuid.UUID,
        manifest: DeliveryManifest,
        expected_manifest_sha256: str,
        expected_sidecar_sha256: str,
    ) -> list[BundleMismatch]:
        bundle = self.bundle_dir(workspace_id, artifact_id)
        mismatches: list[BundleMismatch] = []
        if not bundle.is_dir():
            return [BundleMismatch(path=".", reason="bundle_missing")]
        manifest_path = bundle / MANIFEST_NAME
        sidecar_path = bundle / SIDECAR_NAME
        if not manifest_path.is_file():
            mismatches.append(BundleMismatch(path=MANIFEST_NAME, reason="missing_file"))
        else:
            manifest_bytes = manifest_path.read_bytes()
            actual_manifest = manifest_digest(json.loads(manifest_bytes))
            if actual_manifest != expected_manifest_sha256:
                mismatches.append(
                    BundleMismatch(
                        path=MANIFEST_NAME,
                        reason="manifest_sha256_mismatch",
                        expected=expected_manifest_sha256,
                        actual=actual_manifest,
                    )
                )
            if manifest_bytes != manifest.canonical_bytes:
                mismatches.append(
                    BundleMismatch(path=MANIFEST_NAME, reason="manifest_not_canonical")
                )
        if not sidecar_path.is_file():
            mismatches.append(BundleMismatch(path=SIDECAR_NAME, reason="missing_file"))
        else:
            sidecar_bytes = sidecar_path.read_bytes()
            actual_sidecar = sha256_hex(sidecar_bytes)
            if actual_sidecar != expected_sidecar_sha256:
                mismatches.append(
                    BundleMismatch(
                        path=SIDECAR_NAME,
                        reason="sidecar_sha256_mismatch",
                        expected=expected_sidecar_sha256,
                        actual=actual_sidecar,
                    )
                )
        expected = {entry["path"]: entry for entry in manifest.payload["files"]}
        actual = self._relative_files(bundle)
        for path, path_obj in sorted(actual.items()):
            if path_obj.is_symlink():
                mismatches.append(BundleMismatch(path=path, reason="symlink_not_allowed"))
                continue
            if path in {MANIFEST_NAME, SIDECAR_NAME}:
                continue
            if path not in expected:
                mismatches.append(BundleMismatch(path=path, reason="unexpected_file"))
                continue
            entry = expected[path]
            data = path_obj.read_bytes()
            if len(data) != entry["size_bytes"]:
                mismatches.append(
                    BundleMismatch(
                        path=path,
                        reason="size_mismatch",
                        expected=str(entry["size_bytes"]),
                        actual=str(len(data)),
                    )
                )
            actual_hash = sha256_hex(data)
            if actual_hash != entry["sha256"]:
                mismatches.append(
                    BundleMismatch(
                        path=path,
                        reason="sha256_mismatch",
                        expected=str(entry["sha256"]),
                        actual=actual_hash,
                    )
                )
        for path in sorted(set(expected) - set(actual)):
            mismatches.append(BundleMismatch(path=path, reason="missing_file"))
        mismatches.sort(key=lambda item: (item.path, item.reason))
        return mismatches

    def build_zip(
        self,
        *,
        workspace_id: uuid.UUID,
        artifact_id: uuid.UUID,
        manifest: DeliveryManifest,
    ) -> bytes:
        bundle = self.bundle_dir(workspace_id, artifact_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(
            buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            archive.writestr(MANIFEST_NAME, (bundle / MANIFEST_NAME).read_bytes())
            archive.writestr(SIDECAR_NAME, (bundle / SIDECAR_NAME).read_bytes())
            for entry in manifest.payload["files"]:
                archive.writestr(entry["path"], (bundle / entry["path"]).read_bytes())
        return buffer.getvalue()


__all__ = ["DeliveryStore", "DeliveryStoreConflict"]
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_store.py -v
```

Expected: `5 passed`。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/store.py tests/unit/test_delivery_store.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/store.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/store.py \
  apps/api/tests/unit/test_delivery_store.py
git commit -m "feat(delivery): add atomic bundle store and tamper verification"
```

---

### Task 8: 迁移 066、模型与交付仓储

**Files:**
- Create: `apps/api/alembic/versions/202610220066_delivery_manifest_publish.py`
- Modify: `apps/api/src/data_intelligence_hub/models/report_artifact.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/delivery.py`
- Test: `apps/api/tests/unit/test_delivery_migration.py`
- Test: `apps/api/tests/postgres/test_delivery_migration.py`

**Interfaces:**
- Consumes: B5 `Base`、`ReportArtifact`、`ReportAuditEvent`。
- Produces: `get_artifact_for_publish`、`get_dataset_version_scoped`、`get_workspace_role`、`create_delivery_event`、`list_artifact_events`、`get_latest_artifact_event`、`list_delivered_artifacts`、`list_acceptance_events`、`get_acceptance_event_by_idempotency`、`get_latest_quick_draft`、`list_pending_acceptance_artifacts`。

- [ ] **Step 1: 写迁移与模型失败测试**

```python
# apps/api/tests/unit/test_delivery_migration.py
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/202610220066_delivery_manifest_publish.py"
)

DELIVERY_COLUMNS = {
    "delivery_status",
    "delivery_class",
    "manifest_json",
    "manifest_sha256",
    "manifest_sidecar_sha256",
    "public_contract_json",
    "acceptance_snapshot_json",
    "acceptance_deadline",
    "delivered_at",
    "delivered_by",
    "supersedes_delivery_id",
    "quick_draft_of_artifact_id",
    "publish_idempotency_key_hash",
}


@pytest.fixture
async def migration_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as database_session:
            yield database_session
    finally:
        await engine.dispose()


def test_migration_066_is_single_head_after_065() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "202610220066"' in text
    assert 'down_revision: str | None = "202610220065"' in text
    assert '"delivery_status"' in text
    assert '"delivered_at"' in text
    assert '"artifact_id"' not in text


def test_report_artifact_has_delivery_columns() -> None:
    columns = set(ReportArtifact.__table__.columns.keys())
    assert DELIVERY_COLUMNS <= columns
    assert ReportArtifact.__table__.c.delivery_status.server_default is not None


async def test_report_audit_event_accepts_artifact_only(
    migration_session: AsyncSession,
) -> None:
    artifact_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    event = ReportAuditEvent(
        workspace_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        report_id=None,
        artifact_id=artifact_id,
        event_type="report_review_approved",
        metadata_json="{}",
    )
    migration_session.add(event)
    await migration_session.flush()
    assert event.artifact_id == artifact_id
    assert event.report_id is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_migration.py -v
```

Expected: `FileNotFoundError` 或 `AttributeError: delivery_status`。

- [ ] **Step 3: 修改模型**

`report_artifact.py` 增加导入与列：

```python
# 修改 apps/api/src/data_intelligence_hub/models/report_artifact.py
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.sql.elements import conv

# class ReportArtifact 的 __table_args__ 追加：
CheckConstraint(
    "delivery_status IN ('pending', 'delivered', 'superseded')",
    name=conv("ck_report_artifacts_delivery_status"),
),
CheckConstraint(
    "delivery_class IN ('formal', 'quick_draft')",
    name=conv("ck_report_artifacts_delivery_class"),
),
CheckConstraint(
    "(delivery_status = 'pending' AND manifest_json IS NULL AND manifest_sha256 IS NULL) "
    "OR (delivery_status IN ('delivered', 'superseded') "
    "AND manifest_json IS NOT NULL AND manifest_sha256 IS NOT NULL "
    "AND manifest_sidecar_sha256 IS NOT NULL AND public_contract_json IS NOT NULL "
    "AND delivered_at IS NOT NULL AND delivered_by IS NOT NULL AND ("
    "(delivery_class = 'formal' AND acceptance_snapshot_json IS NOT NULL "
    "AND acceptance_deadline IS NOT NULL) OR "
    "(delivery_class = 'quick_draft' AND acceptance_snapshot_json IS NULL "
    "AND acceptance_deadline IS NULL AND quick_draft_of_artifact_id IS NOT NULL)))",
    name=conv("ck_report_artifacts_delivery_fields"),
),
CheckConstraint(
    "publish_idempotency_key_hash IS NULL OR length(publish_idempotency_key_hash) = 64",
    name=conv("ck_report_artifacts_publish_key_length"),
),
Index(
    "uq_report_artifacts_publish_idempotency",
    "workspace_id",
    "publish_idempotency_key_hash",
    unique=True,
    postgresql_where=text("publish_idempotency_key_hash IS NOT NULL"),
    sqlite_where=text("publish_idempotency_key_hash IS NOT NULL"),
),
Index("ix_report_artifacts_delivery_status", "delivery_status"),
Index("ix_report_artifacts_delivery_class", "delivery_class"),
Index("ix_report_artifacts_acceptance_deadline", "acceptance_deadline"),
```

列：

```python
delivery_status: Mapped[str] = mapped_column(
    String(20), nullable=False, default="pending", server_default=text("'pending'")
)
delivery_class: Mapped[str] = mapped_column(
    String(20), nullable=False, default="formal", server_default=text("'formal'")
)
manifest_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
manifest_sha256: Mapped[str | None] = mapped_column(String(64))
manifest_sidecar_sha256: Mapped[str | None] = mapped_column(String(64))
public_contract_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
acceptance_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
acceptance_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
delivered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
supersedes_delivery_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("report_artifacts.id"))
quick_draft_of_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("report_artifacts.id")
)
publish_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
```

- [ ] **Step 4: 写迁移 066**

```python
# apps/api/alembic/versions/202610220066_delivery_manifest_publish.py
"""Add delivery publication fields only. Audit artifact scoping is C9 065.

Revision ID: 202610220066
Revises: 202610220065
Create Date: 2026-10-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220066"
down_revision: str | None = "202610220065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_artifacts",
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "report_artifacts",
        sa.Column(
            "delivery_class",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'formal'"),
        ),
    )
    op.add_column("report_artifacts", sa.Column("manifest_json", sa.JSON(), nullable=True))
    op.add_column(
        "report_artifacts", sa.Column("manifest_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "report_artifacts",
        sa.Column("manifest_sidecar_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "report_artifacts", sa.Column("public_contract_json", sa.JSON(), nullable=True)
    )
    op.add_column(
        "report_artifacts",
        sa.Column("acceptance_snapshot_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "report_artifacts",
        sa.Column("acceptance_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_artifacts",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("report_artifacts", sa.Column("delivered_by", sa.Uuid(), nullable=True))
    op.add_column(
        "report_artifacts", sa.Column("supersedes_delivery_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "report_artifacts", sa.Column("quick_draft_of_artifact_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "report_artifacts",
        sa.Column("publish_idempotency_key_hash", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_artifacts_delivered_by_users",
        "report_artifacts",
        "users",
        ["delivered_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_artifacts_supersedes_delivery_id_report_artifacts",
        "report_artifacts",
        "report_artifacts",
        ["supersedes_delivery_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_report_artifacts_quick_draft_of_artifact_id_report_artifacts",
        "report_artifacts",
        "report_artifacts",
        ["quick_draft_of_artifact_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_report_artifacts_delivery_status",
        "report_artifacts",
        "delivery_status IN ('pending', 'delivered', 'superseded')",
    )
    op.create_check_constraint(
        "ck_report_artifacts_delivery_class",
        "report_artifacts",
        "delivery_class IN ('formal', 'quick_draft')",
    )
    op.create_check_constraint(
        "ck_report_artifacts_delivery_fields",
        "report_artifacts",
        "(delivery_status = 'pending' AND manifest_json IS NULL AND manifest_sha256 IS NULL) "
        "OR (delivery_status IN ('delivered', 'superseded') "
        "AND manifest_json IS NOT NULL AND manifest_sha256 IS NOT NULL "
        "AND manifest_sidecar_sha256 IS NOT NULL AND public_contract_json IS NOT NULL "
        "AND delivered_at IS NOT NULL AND delivered_by IS NOT NULL AND ("
        "(delivery_class = 'formal' AND acceptance_snapshot_json IS NOT NULL "
        "AND acceptance_deadline IS NOT NULL) OR "
        "(delivery_class = 'quick_draft' AND acceptance_snapshot_json IS NULL "
        "AND acceptance_deadline IS NULL AND quick_draft_of_artifact_id IS NOT NULL)))",
    )
    op.create_check_constraint(
        "ck_report_artifacts_publish_key_length",
        "report_artifacts",
        "publish_idempotency_key_hash IS NULL "
        "OR length(publish_idempotency_key_hash) = 64",
    )
    op.create_index(
        "uq_report_artifacts_publish_idempotency",
        "report_artifacts",
        ["workspace_id", "publish_idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("publish_idempotency_key_hash IS NOT NULL"),
        sqlite_where=sa.text("publish_idempotency_key_hash IS NOT NULL"),
    )
    op.create_index(
        "ix_report_artifacts_delivery_status",
        "report_artifacts",
        ["delivery_status"],
    )
    op.create_index(
        "ix_report_artifacts_delivery_class",
        "report_artifacts",
        ["delivery_class"],
    )
    op.create_index(
        "ix_report_artifacts_acceptance_deadline",
        "report_artifacts",
        ["acceptance_deadline"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_artifacts_acceptance_deadline", table_name="report_artifacts"
    )
    op.drop_index(
        "ix_report_artifacts_delivery_class", table_name="report_artifacts"
    )
    op.drop_index(
        "ix_report_artifacts_delivery_status", table_name="report_artifacts"
    )
    op.drop_index(
        "uq_report_artifacts_publish_idempotency", table_name="report_artifacts"
    )
    op.drop_constraint(
        "ck_report_artifacts_publish_key_length", "report_artifacts", type_="check"
    )
    op.drop_constraint(
        "ck_report_artifacts_delivery_fields", "report_artifacts", type_="check"
    )
    op.drop_constraint(
        "ck_report_artifacts_delivery_class", "report_artifacts", type_="check"
    )
    op.drop_constraint(
        "ck_report_artifacts_delivery_status", "report_artifacts", type_="check"
    )
    op.drop_constraint(
        "fk_report_artifacts_quick_draft_of_artifact_id_report_artifacts",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_artifacts_supersedes_delivery_id_report_artifacts",
        "report_artifacts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_artifacts_delivered_by_users",
        "report_artifacts",
        type_="foreignkey",
    )
    for column in (
        "publish_idempotency_key_hash",
        "quick_draft_of_artifact_id",
        "supersedes_delivery_id",
        "delivered_by",
        "delivered_at",
        "acceptance_deadline",
        "acceptance_snapshot_json",
        "public_contract_json",
        "manifest_sidecar_sha256",
        "manifest_sha256",
        "manifest_json",
        "delivery_class",
        "delivery_status",
    ):
        op.drop_column("report_artifacts", column)
```

- [ ] **Step 4b: 写 PostgreSQL 迁移测试**

Create `apps/api/tests/postgres/test_delivery_migration.py`：

```python
"""C10：065→066→065 PostgreSQL 迁移验收。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

API_ROOT = Path(__file__).resolve().parents[2]
DELIVERY_COLUMNS = {
    "delivery_status",
    "delivery_class",
    "manifest_json",
    "manifest_sha256",
    "manifest_sidecar_sha256",
    "public_contract_json",
    "acceptance_snapshot_json",
    "acceptance_deadline",
    "delivered_at",
    "delivered_by",
    "supersedes_delivery_id",
    "quick_draft_of_artifact_id",
    "publish_idempotency_key_hash",
}
C9_COLUMNS = {"status", "published_at", "published_by", "supersedes_id"}


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
async def test_065_to_066_and_back() -> None:
    url = _database_url()
    _alembic(url, "upgrade", "202610220065")
    _alembic(url, "upgrade", "202610220066")
    engine = create_async_engine(url)
    try:
        artifact_columns = await _columns(engine, "report_artifacts")
        assert DELIVERY_COLUMNS <= artifact_columns
        assert C9_COLUMNS <= artifact_columns
        event_columns = await _columns(engine, "report_audit_events")
        assert "artifact_id" in event_columns
        _alembic(url, "downgrade", "202610220065")
        downgraded = await _columns(engine, "report_artifacts")
        assert DELIVERY_COLUMNS.isdisjoint(downgraded)
        assert C9_COLUMNS <= downgraded
        _alembic(url, "upgrade", "head")
    finally:
        await engine.dispose()


def test_single_head_is_066() -> None:
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
    assert "202610220066" in result.stdout
```

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/dih_migration_test \
  uv run pytest tests/postgres/test_delivery_migration.py -q
```

Expected: `2 passed`。未设置 `TEST_DATABASE_URL` 时是 `2 skipped`；切片完成门禁必须用一次性 PostgreSQL 跑出 `2 passed`。该测试必须先于 C10 的 SQLite 单测证明 066 可升级，且 C9 的 065 列与触发器仍在。

- [ ] **Step 5: 写交付仓储**

```python
# apps/api/src/data_intelligence_hub/repositories/delivery.py
"""交付专用查询。仓储只 flush，提交权在 service。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.workspace import WorkspaceMember


async def get_artifact_for_publish(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    for_update: bool = False,
) -> ReportArtifact | None:
    statement = select(ReportArtifact).where(
        ReportArtifact.workspace_id == workspace_id,
        ReportArtifact.id == artifact_id,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_artifact_by_idempotency(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    key_hash: str,
) -> ReportArtifact | None:
    result = await session.execute(
        select(ReportArtifact).where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.publish_idempotency_key_hash == key_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_dataset_version_scoped(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DatasetVersion | None:
    result = await session.execute(
        select(DatasetVersion).where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.project_id == project_id,
            DatasetVersion.id == version_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workspace_role(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    result = await session.execute(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_delivery_event(
    session: AsyncSession,
    event: ReportAuditEvent,
) -> ReportAuditEvent:
    session.add(event)
    await session.flush()
    return event


async def list_artifact_events(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> list[ReportAuditEvent]:
    result = await session.execute(
        select(ReportAuditEvent)
        .where(
            ReportAuditEvent.workspace_id == workspace_id,
            ReportAuditEvent.artifact_id == artifact_id,
        )
        .order_by(ReportAuditEvent.created_at.asc(), ReportAuditEvent.id.asc())
    )
    return list(result.scalars().all())


async def get_latest_artifact_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    event_type: str,
) -> ReportAuditEvent | None:
    result = await session.execute(
        select(ReportAuditEvent)
        .where(
            ReportAuditEvent.workspace_id == workspace_id,
            ReportAuditEvent.artifact_id == artifact_id,
            ReportAuditEvent.event_type == event_type,
        )
        .order_by(ReportAuditEvent.created_at.desc(), ReportAuditEvent.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_delivered_artifacts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    template_id: str,
) -> list[ReportArtifact]:
    result = await session.execute(
        select(ReportArtifact).where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.project_id == project_id,
            ReportArtifact.template_id == template_id,
            ReportArtifact.delivery_status == "delivered",
        )
    )
    return list(result.scalars().all())


ACCEPTANCE_EVENT_TYPES = (
    "acceptance_accepted",
    "acceptance_disputed",
    "acceptance_deemed_accepted",
)


async def list_acceptance_events(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> list[ReportAuditEvent]:
    result = await session.execute(
        select(ReportAuditEvent)
        .where(
            ReportAuditEvent.workspace_id == workspace_id,
            ReportAuditEvent.artifact_id == artifact_id,
            ReportAuditEvent.event_type.in_(ACCEPTANCE_EVENT_TYPES),
        )
        .order_by(ReportAuditEvent.created_at.asc(), ReportAuditEvent.id.asc())
    )
    return list(result.scalars().all())


async def get_acceptance_event_by_idempotency(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    idempotency_key_hash: str,
) -> tuple[ReportAuditEvent, dict[str, Any]] | None:
    import json

    for event in await list_acceptance_events(
        session, workspace_id=workspace_id, artifact_id=artifact_id
    ):
        metadata = json.loads(event.metadata_json or "{}")
        if metadata.get("idempotency_key_hash") == idempotency_key_hash:
            return event, metadata
    return None


async def get_latest_quick_draft(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
) -> ReportArtifact | None:
    result = await session.execute(
        select(ReportArtifact)
        .where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.project_id == project_id,
            ReportArtifact.delivery_class == "quick_draft",
            ReportArtifact.delivery_status == "delivered",
        )
        .order_by(ReportArtifact.delivered_at.desc())
    )
    for artifact in result.scalars().all():
        contract = artifact.contract_json or {}
        if str(contract.get("task_id")) == str(task_id):
            return artifact
    return None


async def list_pending_acceptance_artifacts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
) -> list[ReportArtifact]:
    result = await session.execute(
        select(ReportArtifact).where(
            ReportArtifact.workspace_id == workspace_id,
            ReportArtifact.delivery_class == "formal",
            ReportArtifact.delivery_status == "delivered",
            ReportArtifact.acceptance_deadline.is_not(None),
        )
    )
    return list(result.scalars().all())


__all__ = [
    "ACCEPTANCE_EVENT_TYPES",
    "create_delivery_event",
    "get_acceptance_event_by_idempotency",
    "get_artifact_by_idempotency",
    "get_artifact_for_publish",
    "get_dataset_version_scoped",
    "get_latest_artifact_event",
    "get_latest_quick_draft",
    "get_workspace_role",
    "list_acceptance_events",
    "list_artifact_events",
    "list_delivered_artifacts",
    "list_pending_acceptance_artifacts",
]
```

- [ ] **Step 6: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_migration.py -v
```

Expected: `3 passed`。`test_report_audit_event_accepts_artifact_only` 使用内存 SQLite 的 `Base.metadata.create_all` 会话夹具；如果该测试文件没有 session fixture，从 B5 `test_report_artifacts.py` 的 `_with_session` 辅助复制，不要新建第二套 engine 配置。

- [ ] **Step 7: 运行既有报告/审计测试，确认没有回归**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_report_artifacts.py tests/unit/test_report_contract.py tests/unit/test_report_builder.py tests/unit/test_demo_data.py tests/unit/test_public_content_retention.py tests/unit/test_e2e_cleanup.py tests/unit/test_scheduler.py
```

Expected: 全部通过。`ReportAuditEvent` 的 GitNexus 风险是 MEDIUM；这里必须看到现有测试仍绿。若有失败，先修兼容性，不得改测试期望来掩盖。

- [ ] **Step 8: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check alembic/versions/202610220066_delivery_manifest_publish.py src/data_intelligence_hub/models/report_artifact.py src/data_intelligence_hub/repositories/delivery.py tests/unit/test_delivery_migration.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/models/report_artifact.py src/data_intelligence_hub/repositories/delivery.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220066_delivery_manifest_publish.py \
  apps/api/src/data_intelligence_hub/models/report_artifact.py \
  apps/api/src/data_intelligence_hub/repositories/delivery.py \
  apps/api/tests/unit/test_delivery_migration.py \
  apps/api/tests/postgres/test_delivery_migration.py
git commit -m "feat(delivery): add migration 066 delivery fields"
```

---

### Task 9: 发布服务、幂等、Supersede 与篡改下载

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/delivery/service.py`
- Test: `apps/api/tests/unit/test_delivery_service.py`

**Interfaces:**
- Consumes: 前八个任务的全部接口，以及 `report_artifacts`、`dataset_versions`、`report_audit_events`。
- Produces: `publish_delivery`、`publish_quick_draft`、`load_delivery_manifest`、`open_delivery_zip`、`DeliveryPiiError`、`GateFailedError`、`DeliveryIntegrityError`、`DeliveryNotFoundError`、`DeliveryNotPublishedError`、`IdempotencyConflictError`。

- [ ] **Step 1: 写发布服务失败测试**

```python
# apps/api/tests/unit/test_delivery_service.py
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.services.delivery.service import (
    DeliveryIntegrityError,
    open_delivery_zip,
    publish_delivery,
)
from data_intelligence_hub.services.delivery.store import DeliveryStore

# 复用 conftest.py 的 delivery_seed；它已包含草稿产物、Claim、签字与数据集版本。


async def test_publish_writes_bundle_and_events(
    session: AsyncSession, delivery_seed, tmp_path: Path
) -> None:
    store = DeliveryStore(tmp_path)
    result = await publish_delivery(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact_id=delivery_seed.artifact_id,
        dataset_version_id=delivery_seed.dataset_version_id,
        idempotency_key="publish-1",
        delivered_by=delivery_seed.user_id,
        supersedes_artifact_id=None,
        store=store,
        now=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
    )
    assert result.replay is False
    assert result.artifact.delivery_status == "delivered"
    assert result.manifest.sha256
    assert (
        store.bundle_dir(delivery_seed.workspace_id, result.artifact.id)
        / "delivery_manifest.json"
    ).is_file()
    events = (await session.execute(select(ReportAuditEvent))).scalars().all()
    event_types = {event.event_type for event in events}
    assert {"delivery_published", "acceptance_snapshot_appended"} <= event_types


async def test_publish_is_idempotent(
    session: AsyncSession, delivery_seed, tmp_path: Path
) -> None:
    store = DeliveryStore(tmp_path)
    first = await publish_delivery(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact_id=delivery_seed.artifact_id,
        dataset_version_id=delivery_seed.dataset_version_id,
        idempotency_key="publish-1",
        delivered_by=delivery_seed.user_id,
        supersedes_artifact_id=None,
        store=store,
        now=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
    )
    second = await publish_delivery(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact_id=delivery_seed.artifact_id,
        dataset_version_id=delivery_seed.dataset_version_id,
        idempotency_key="publish-1",
        delivered_by=delivery_seed.user_id,
        supersedes_artifact_id=None,
        store=store,
        now=datetime(2026, 10, 22, 10, 5, tzinfo=UTC),
    )
    assert second.replay is True
    assert second.manifest.sha256 == first.manifest.sha256


async def test_tampered_bundle_refuses_download(
    session: AsyncSession, delivery_seed, tmp_path: Path
) -> None:
    store = DeliveryStore(tmp_path)
    result = await publish_delivery(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact_id=delivery_seed.artifact_id,
        dataset_version_id=delivery_seed.dataset_version_id,
        idempotency_key="publish-1",
        delivered_by=delivery_seed.user_id,
        supersedes_artifact_id=None,
        store=store,
        now=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
    )
    target = (
        store.bundle_dir(delivery_seed.workspace_id, result.artifact.id)
        / "report.zh.html"
    )
    target.write_bytes(target.read_bytes() + b"tamper")
    try:
        await open_delivery_zip(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=result.artifact.id,
            actor_id=delivery_seed.user_id,
            store=store,
        )
    except DeliveryIntegrityError as exc:
        assert any(item.reason == "sha256_mismatch" for item in exc.mismatches)
    else:
        raise AssertionError("篡改后必须拒绝下载")
    assert result.artifact.delivery_status == "delivered"
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.services.delivery.service'`。

- [ ] **Step 3: 写实现**

```python
# apps/api/src/data_intelligence_hub/services/delivery/service.py
"""C10 发布与下载服务。事务提交权在本层。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report import ReportAuditEvent
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.delivery import (
    create_delivery_event,
    get_artifact_by_idempotency,
    get_artifact_for_publish,
    get_dataset_version_scoped,
)
from data_intelligence_hub.services.delivery.canonical import (
    canonical_bytes,
    sha256_hex,
)
from data_intelligence_hub.services.delivery.gates import (
    evaluate_g_claim,
    evaluate_g_publish,
    load_claim_snapshot,
)
from data_intelligence_hub.services.delivery.acceptance import (
    acceptance_status_from_events,
    is_deemed_acceptance_due,
    validate_dispute_references,
)
from data_intelligence_hub.services.delivery.audit import project_delivery_audit
from data_intelligence_hub.services.delivery.manifest import (
    ACCEPTANCE_SNAPSHOT_PATH,
    QUICK_DRAFT_NOTICE_PATH,
    QUICK_DRAFT_REQUIRED_ROLES,
    build_manifest,
    content_bundle_sha256,
    manifest_digest,
)
from data_intelligence_hub.services.delivery.pii import scan_delivery_inputs
from data_intelligence_hub.services.delivery.projection import (
    assert_forbidden_language_free,
    project_public_contract,
)
from data_intelligence_hub.services.delivery.renderers import (
    add_business_days,
    build_dataset_input,
    render_acceptance_snapshot,
    render_claim_evidence_index,
    render_data_dictionary,
    render_executive_summary_en,
    render_limits_and_gaps,
    render_quality_scorecard,
    render_quick_draft_notice,
    render_run_receipt,
)
from data_intelligence_hub.services.delivery.review import load_latest_review_signoff
from data_intelligence_hub.services.report_contract_v1_1 import (
    create_delivery_contract_version,
)
from data_intelligence_hub.services.delivery.store import (
    DeliveryStore,
    DeliveryStoreConflict,
)
from data_intelligence_hub.services.delivery.types import (
    AcceptanceEvent,
    AcceptanceResult,
    AcceptanceState,
    BundleMismatch,
    DatasetInput,
    DeliveryClass,
    DeliveryEventType,
    DeliveryFile,
    DeliveryFileRole,
    DeliveryManifest,
    DeliveryStatus,
    DisputeReference,
    GateDecision,
    PublishResult,
)
from data_intelligence_hub.services.export_policy import (
    EXPORT_POLICY_VERSION,
    PiiHit,
)


class DeliveryError(RuntimeError):
    """交付领域错误基类。"""


class DeliveryNotFoundError(DeliveryError):
    """产物不存在或跨工作区。"""


class DeliveryNotPublishedError(DeliveryError):
    """产物尚未发布。"""


class DeliveryIntegrityError(DeliveryError):
    def __init__(self, mismatches: Sequence[Any]) -> None:
        super().__init__("delivery_integrity_error")
        self.mismatches = tuple(mismatches)


class GateFailedError(DeliveryError):
    def __init__(self, decisions: Sequence[GateDecision]) -> None:
        super().__init__("gate_failed")
        self.decisions = tuple(decisions)


class DeliveryPiiError(DeliveryError):
    """C11 PII 扫描命中；只携带 PiiHit，不携带原始值。"""

    def __init__(self, hits: Sequence[PiiHit]) -> None:
        super().__init__("delivery_pii_detected")
        self.hits = tuple(hits)


class IdempotencyConflictError(DeliveryError):
    """同一幂等键指向另一份产物。"""


def _pretty_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _content_files(
    *,
    artifact: ReportArtifact,
    contract: Mapping[str, Any],
    public_contract: Mapping[str, Any],
    dataset: DatasetInput,
) -> tuple[DeliveryFile, ...]:
    return (
        DeliveryFile(
            role=DeliveryFileRole.REPORT_ZH,
            path="report.zh.html",
            media_type="text/html; charset=utf-8",
            content=(artifact.report_html or "").encode("utf-8"),
        ),
        DeliveryFile(
            role=DeliveryFileRole.EXECUTIVE_SUMMARY_EN,
            path="executive_summary.en.md",
            media_type="text/markdown; charset=utf-8",
            content=render_executive_summary_en(public_contract),
        ),
        DeliveryFile(
            role=DeliveryFileRole.DATASET,
            path="dataset.csv",
            media_type=dataset.media_type,
            content=dataset.csv_bytes,
        ),
        DeliveryFile(
            role=DeliveryFileRole.DATA_DICTIONARY,
            path="data_dictionary.json",
            media_type="application/json",
            content=render_data_dictionary(dataset),
        ),
        DeliveryFile(
            role=DeliveryFileRole.QUALITY_SCORECARD,
            path="quality_scorecard.json",
            media_type="application/json",
            content=render_quality_scorecard(public_contract, dataset),
        ),
        DeliveryFile(
            role=DeliveryFileRole.CLAIM_EVIDENCE_INDEX,
            path="claim_evidence_index.csv",
            media_type="text/csv; charset=utf-8",
            content=render_claim_evidence_index(public_contract),
        ),
        DeliveryFile(
            role=DeliveryFileRole.RUN_RECEIPT,
            path="run_receipt.json",
            media_type="application/json",
            content=render_run_receipt(contract),
        ),
        DeliveryFile(
            role=DeliveryFileRole.REPORT_CONTRACT,
            path="report_contract.json",
            media_type="application/json",
            content=_pretty_json(public_contract),
        ),
        DeliveryFile(
            role=DeliveryFileRole.LIMITS_AND_GAPS,
            path="limits_and_gaps.json",
            media_type="application/json",
            content=render_limits_and_gaps(public_contract),
        ),
    )


def _event(
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    event_type: DeliveryEventType,
    metadata: Mapping[str, Any],
    now: datetime,
) -> ReportAuditEvent:
    return ReportAuditEvent(
        workspace_id=workspace_id,
        report_id=None,
        artifact_id=artifact_id,
        actor_id=actor_id,
        event_type=event_type.value,
        metadata_json=json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        created_at=now,
    )


def _gate_metadata(decision: GateDecision) -> dict[str, Any]:
    return {
        "gate_id": decision.gate_id,
        "status": decision.status,
        "subject_digest": decision.subject_digest,
        "findings": [
            {
                "code": finding.code,
                "message": finding.message,
                "subject_id": finding.subject_id,
            }
            for finding in decision.findings
        ],
    }


async def publish_delivery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    idempotency_key: str,
    delivered_by: uuid.UUID,
    supersedes_artifact_id: uuid.UUID | None,
    store: DeliveryStore,
    now: datetime | None = None,
) -> PublishResult:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("Idempotency-Key 长度必须在 1 到 128 之间")
    moment = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    key_hash = sha256_hex(idempotency_key.encode("utf-8"))
    existing = await get_artifact_by_idempotency(
        session, workspace_id=workspace_id, key_hash=key_hash
    )
    if existing is not None:
        if existing.id != artifact_id and existing.supersedes_id != artifact_id:
            raise IdempotencyConflictError("同一 Idempotency-Key 已用于另一份产物")
        manifest = await load_delivery_manifest(
            session,
            workspace_id=workspace_id,
            artifact_id=existing.id,
            store=store,
        )
        return PublishResult(artifact=existing, manifest=manifest, replay=True)
    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id, for_update=True
    )
    if artifact is None or artifact.project_id != project_id:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if artifact.status != "published":
        raise DeliveryNotPublishedError("artifact_not_published_by_c9")
    if artifact.delivery_status == DeliveryStatus.DELIVERED.value:
        raise DeliveryNotPublishedError("artifact_already_delivered_without_idempotency_key")
    if artifact.delivery_status != DeliveryStatus.PENDING.value:
        raise DeliveryNotPublishedError("artifact_not_pending")
    source_artifact = artifact
    contract = dict(artifact.contract_json)
    assert_forbidden_language_free(contract)
    claim_snapshot = await load_claim_snapshot(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        contract=contract,
    )
    g_claim = await evaluate_g_claim(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        artifact=artifact,
        contract=contract,
        claim_snapshot=claim_snapshot,
    )
    if not g_claim.passed:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata=_gate_metadata(g_claim),
                now=moment,
            ),
        )
        await session.commit()
        raise GateFailedError((g_claim,))
    version = await get_dataset_version_scoped(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        version_id=dataset_version_id,
    )
    if version is None:
        raise DeliveryNotFoundError("dataset_version_not_found")
    if version.status != "saved":
        raise ValueError("dataset_version_not_saved")
    dataset = build_dataset_input(version)
    if not dataset.rows:
        raise ValueError("dataset_empty")
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise DeliveryNotFoundError("workspace_not_found")
    manifest_id = uuid.uuid4()
    acceptance_deadline = add_business_days(moment, 5)
    delivery_artifact = await create_delivery_contract_version(
        session,
        workspace=workspace,
        report_id=artifact.report_id,
        artifact_id=artifact.id,
        publisher=delivered_by,
        acceptance_window_start=moment.date(),
        acceptance_window_end=acceptance_deadline.date(),
        manifest_id=manifest_id,
        access_scope=list(contract["delivery"]["access_scope"]),
        retention_class=str(contract["delivery"]["retention_class"]),
    )
    artifact = delivery_artifact
    artifact_id = delivery_artifact.id
    contract = dict(artifact.contract_json)
    public_contract = project_public_contract(
        contract,
        dataset=dataset.metadata,
        source_contract_sha256=artifact.contract_sha256,
    )
    content_files = _content_files(
        artifact=artifact,
        contract=contract,
        public_contract=public_contract,
        dataset=dataset,
    )
    files_digest = content_bundle_sha256(content_files)
    snapshot_bytes = render_acceptance_snapshot(
        artifact_id=artifact_id,
        contract_sha256=artifact.contract_sha256,
        data_sha256=artifact.data_sha256,
        dataset=dataset,
        content_bundle_sha256=files_digest,
        delivered_at=moment,
        acceptance_deadline=acceptance_deadline,
        gate_status={"G-Claim": g_claim.status},
    )
    snapshot_file = DeliveryFile(
        role=DeliveryFileRole.ACCEPTANCE_SNAPSHOT,
        path=ACCEPTANCE_SNAPSHOT_PATH,
        media_type="application/json",
        content=snapshot_bytes,
    )
    files = (*content_files, snapshot_file)
    manifest = build_manifest(
        manifest_id=manifest_id,
        artifact_id=artifact.id,
        task_id=uuid.UUID(str(contract["task_id"])),
        report_version=int(contract["report_version"]),
        files=files,
        access_scope=list(contract["delivery"]["access_scope"]),
        retention_class=str(contract["delivery"]["retention_class"]),
        created_at=moment,
    )
    signoff = await load_latest_review_signoff(
        session, workspace_id=workspace_id, artifact_id=source_artifact.id
    )
    pii_hits = scan_delivery_inputs(
        manifest=manifest,
        files=files,
        public_contract=public_contract,
        claim_snapshot=claim_snapshot,
    )
    if pii_hits:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata={
                    "gate_id": "G-Publish",
                    "status": "fail",
                    "export_policy_version": EXPORT_POLICY_VERSION,
                    "findings": [
                        {
                            "code": "delivery_pii_detected",
                            "kind": hit.kind,
                            "field_path": hit.field_path,
                        }
                        for hit in pii_hits
                    ],
                },
                now=moment,
            ),
        )
        await project_delivery_audit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_id=delivered_by,
            action="delivery.published",
            result="denied",
            artifact_id=artifact_id,
            details={
                "reason": "delivery_pii_detected",
                "hit_count": len(pii_hits),
                "export_policy_version": EXPORT_POLICY_VERSION,
            },
            now=moment,
        )
        await session.commit()
        raise DeliveryPiiError(pii_hits)
    g_publish = await evaluate_g_publish(
        session,
        workspace_id=workspace_id,
        artifact=artifact,
        contract=contract,
        claim_snapshot=claim_snapshot,
        g_claim=g_claim,
        signoff=signoff,
        dataset=dataset,
        files=files,
        manifest=manifest,
        acceptance_snapshot=snapshot_file,
        now=moment,
        signoff_artifact=source_artifact,
    )
    if not g_publish.passed:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata=_gate_metadata(g_publish),
                now=moment,
            ),
        )
        await session.commit()
        raise GateFailedError((g_claim, g_publish))
    created = False
    try:
        try:
            store.write_bundle(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                files=files,
                manifest=manifest,
            )
        except DeliveryStoreConflict as exc:
            raise DeliveryIntegrityError(
                (
                    BundleMismatch(
                        path=".",
                        reason="bundle_already_exists",
                    ),
                )
            ) from exc
        created = True
        artifact.delivery_status = DeliveryStatus.DELIVERED.value
        artifact.delivery_class = DeliveryClass.FORMAL.value
        artifact.manifest_json = dict(manifest.payload)
        artifact.manifest_sha256 = manifest.sha256
        artifact.manifest_sidecar_sha256 = manifest.sidecar_sha256
        artifact.public_contract_json = public_contract
        artifact.acceptance_snapshot_json = json.loads(snapshot_bytes)
        artifact.acceptance_deadline = acceptance_deadline
        artifact.delivered_at = moment
        artifact.delivered_by = delivered_by
        artifact.publish_idempotency_key_hash = key_hash
        artifact.supersedes_delivery_id = supersedes_artifact_id
        if supersedes_artifact_id is not None:
            previous = await get_artifact_for_publish(
                session,
                workspace_id=workspace_id,
                artifact_id=supersedes_artifact_id,
                for_update=True,
            )
            if (
                previous is None
                or previous.project_id != project_id
                or previous.delivery_status != DeliveryStatus.DELIVERED.value
            ):
                raise DeliveryNotFoundError("supersedes_artifact_not_published")
            previous.delivery_status = DeliveryStatus.SUPERSEDED.value
            await create_delivery_event(
                session,
                _event(
                    workspace_id=workspace_id,
                    artifact_id=previous.id,
                    actor_id=delivered_by,
                    event_type=DeliveryEventType.DELIVERY_SUPERSEDED,
                    metadata={
                        "superseded_by": str(artifact_id),
                        "manifest_sha256": previous.manifest_sha256,
                    },
                    now=moment,
                ),
            )
        for decision in (g_claim, g_publish):
            await create_delivery_event(
                session,
                _event(
                    workspace_id=workspace_id,
                    artifact_id=artifact_id,
                    actor_id=delivered_by,
                    event_type=DeliveryEventType.GATE_EVALUATED,
                    metadata=_gate_metadata(decision),
                    now=moment,
                ),
            )
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.DELIVERY_PUBLISHED,
                metadata={
                    "manifest_sha256": manifest.sha256,
                    "manifest_sidecar_sha256": manifest.sidecar_sha256,
                    "files_digest": files_digest,
                    "dataset_version_id": str(dataset.version_id),
                    "dataset_sha256": dataset.csv_sha256,
                    "acceptance_deadline": acceptance_deadline.isoformat(),
                },
                now=moment,
            ),
        )
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.ACCEPTANCE_SNAPSHOT_APPENDED,
                metadata={
                    "snapshot_sha256": sha256_hex(snapshot_bytes),
                    "manifest_sha256": manifest.sha256,
                    "acceptance_deadline": acceptance_deadline.isoformat(),
                    "status": "pending",
                },
                now=moment,
            ),
        )
        await project_delivery_audit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_id=delivered_by,
            action="delivery.published",
            result="success",
            artifact_id=artifact_id,
            details={
                "delivery_class": "formal",
                "manifest_sha256": manifest.sha256,
                "acceptance_deadline": acceptance_deadline.isoformat(),
                "gates": {"G-Claim": g_claim.status, "G-Publish": g_publish.status},
            },
            now=moment,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        if created:
            store.remove_bundle(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
            )
        raise
    return PublishResult(artifact=artifact, manifest=manifest, replay=False)


async def load_delivery_manifest(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    store: DeliveryStore,
    verify_bundle: bool = True,
) -> DeliveryManifest:
    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id
    )
    if artifact is None:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if artifact.delivery_status not in {
        DeliveryStatus.DELIVERED.value,
        DeliveryStatus.SUPERSEDED.value,
    }:
        raise DeliveryNotPublishedError("delivery_not_published")
    payload = dict(artifact.manifest_json or {})
    body = canonical_bytes(payload)
    manifest = DeliveryManifest(
        payload=payload,
        canonical_bytes=body,
        sha256=manifest_digest(payload),
        sidecar_bytes=(
            f"{artifact.manifest_sha256}  delivery_manifest.json\n".encode("ascii")
        ),
        sidecar_sha256=artifact.manifest_sidecar_sha256 or "",
    )
    if manifest.sha256 != artifact.manifest_sha256:
        raise DeliveryIntegrityError(
            (
                BundleMismatch(
                    path="delivery_manifest.json",
                    reason="manifest_sha256_mismatch",
                    expected=artifact.manifest_sha256,
                    actual=manifest.sha256,
                ),
            )
        )
    if verify_bundle:
        mismatches = store.verify_bundle(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            manifest=manifest,
            expected_manifest_sha256=manifest.sha256,
            expected_sidecar_sha256=manifest.sidecar_sha256,
        )
        if mismatches:
            raise DeliveryIntegrityError(mismatches)
    return manifest


async def open_delivery_zip(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    store: DeliveryStore,
) -> tuple[bytes, str]:
    manifest = await load_delivery_manifest(
        session,
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        store=store,
        verify_bundle=False,
    )
    mismatches = store.verify_bundle(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        manifest=manifest,
        expected_manifest_sha256=manifest.sha256,
        expected_sidecar_sha256=manifest.sidecar_sha256,
    )
    now = datetime.now(UTC)
    if mismatches:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=actor_id,
                event_type=DeliveryEventType.DELIVERY_TAMPER_DETECTED,
                metadata={
                    "manifest_sha256": manifest.sha256,
                    "mismatches": [
                        {"path": item.path, "reason": item.reason}
                        for item in mismatches
                    ],
                },
                now=now,
            ),
        )
        await session.commit()
        raise DeliveryIntegrityError(mismatches)
    await create_delivery_event(
        session,
        _event(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            actor_id=actor_id,
            event_type=DeliveryEventType.DELIVERY_DOWNLOADED,
            metadata={
                "manifest_sha256": manifest.sha256,
                "manifest_sidecar_sha256": manifest.sidecar_sha256,
            },
            now=now,
        ),
    )
    await session.commit()
    data = store.build_zip(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        manifest=manifest,
    )
    filename = f"report-{manifest.payload['report_version']}.zip"
    return data, filename


__all__ = [
    "AcceptanceClosedError",
    "AcceptanceNotApplicableError",
    "AcceptanceReferenceInvalidError",
    "AcceptanceWindowOpenError",
    "DeliveryError",
    "DeliveryIntegrityError",
    "DeliveryNotFoundError",
    "DeliveryNotPublishedError",
    "DeliveryPiiError",
    "GateFailedError",
    "IdempotencyConflictError",
    "load_acceptance",
    "load_delivery_manifest",
    "open_delivery_zip",
    "publish_delivery",
    "publish_quick_draft",
    "record_acceptance",
    "record_deemed_acceptance",
    "sweep_deemed_acceptances",
]
```

- [ ] **Step 3b: 写 C2 统一审计投影 `services/delivery/audit.py`**

```python
# apps/api/src/data_intelligence_hub/services/delivery/audit.py
"""交付事实到 C2 append_audit_event 的唯一投影。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.services.audit_log import append_audit_event

DELIVERY_AUDIT_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "delivery.published",
        "delivery.projection.viewed",
        "delivery.downloaded",
        "delivery.tamper_detected",
        "delivery.superseded",
    }
)


async def project_delivery_audit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str,
    result: str,
    artifact_id: uuid.UUID,
    details: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    if action not in DELIVERY_AUDIT_ACTIONS:
        raise ValueError("delivery_audit_action_unregistered")
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_user_id=actor_id,
        action=action,
        resource_type="report_artifact",
        resource_id=str(artifact_id),
        result=result,
        details=details or {},
        occurred_at=now,
    )
```

- [ ] **Step 3c: 写 `services/delivery/acceptance.py`**

```python
# apps/api/src/data_intelligence_hub/services/delivery/acceptance.py
"""验收事件的纯规则：状态映射、逾期判定、争议引用校验。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from data_intelligence_hub.services.delivery.types import (
    AcceptanceEvent,
    DeliveryManifest,
    DisputeReference,
)

ACCEPTANCE_EVENT_TYPES = (
    "acceptance_accepted",
    "acceptance_disputed",
    "acceptance_deemed_accepted",
)

_STATUS_BY_EVENT = {
    "acceptance_accepted": "accepted",
    "acceptance_disputed": "objection",
    "acceptance_deemed_accepted": "auto_accepted",
}


def acceptance_status_from_events(events: Sequence[AcceptanceEvent]) -> str:
    if not events:
        return "pending"
    return _STATUS_BY_EVENT.get(events[-1].event_type, "pending")


def is_deemed_acceptance_due(deadline: datetime | None, now: datetime) -> bool:
    return deadline is not None and now > deadline


def validate_dispute_references(
    references: Sequence[DisputeReference],
    *,
    manifest: DeliveryManifest,
    public_contract: Mapping[str, object],
) -> list[str]:
    issues: list[str] = []
    if not references:
        issues.append("争议必须至少包含 1 项逐项引用")
        return issues
    paths = {str(entry["path"]) for entry in manifest.payload.get("files") or []}
    claim_ids = {
        str(claim["claim_id"])
        for claim in public_contract.get("claims") or []
        if isinstance(claim, Mapping) and claim.get("claim_id")
    }
    evidence_ids = {
        str(evidence["evidence_id"])
        for evidence in public_contract.get("evidences") or []
        if isinstance(evidence, Mapping) and evidence.get("evidence_id")
    }
    for reference in references:
        if reference.path not in paths:
            issues.append(f"引用路径不在 manifest：{reference.path}")
        if not reference.description.strip():
            issues.append(f"引用 {reference.path} 缺少 description")
        if reference.claim_id and reference.claim_id not in claim_ids:
            issues.append(f"引用 claim_id 不存在：{reference.claim_id}")
        if reference.evidence_id and reference.evidence_id not in evidence_ids:
            issues.append(f"引用 evidence_id 不存在：{reference.evidence_id}")
        if reference.item_id and not (
            reference.item_id in claim_ids or reference.item_id in evidence_ids
        ):
            issues.append(f"引用 item_id 不存在：{reference.item_id}")
    return issues
```

- [ ] **Step 3d: 写 `services/delivery/quick.py`**

```python
# apps/api/src/data_intelligence_hub/services/delivery/quick.py
"""Quick 2 小时方向稿的合同与包型守卫。"""

from __future__ import annotations

from collections.abc import Mapping


def assert_quick_package(package_type: str) -> None:
    if package_type != "quick":
        raise ValueError("quick_draft_not_allowed")


def assert_quick_contract(contract: Mapping[str, object]) -> None:
    for market in contract.get("markets") or []:
        if isinstance(market, Mapping) and market.get("conclusion_standard") is not None:
            raise ValueError("quick_draft_claim_invalid: 不得输出 Standard 四态")
    for claim in contract.get("claims") or []:
        if isinstance(claim, Mapping) and claim.get("claim_status") == "confirmed":
            raise ValueError("quick_draft_claim_invalid: 不得出现 confirmed")
```

- [ ] **Step 3e: 写 `services/delivery/pii.py`**

```python
# apps/api/src/data_intelligence_hub/services/delivery/pii.py
"""交付 PII 扫描接缝。规则与递归全部由 C11 export_policy 提供。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from data_intelligence_hub.services.delivery.types import (
    ClaimSnapshot,
    DeliveryFile,
    DeliveryManifest,
)
from data_intelligence_hub.services.export_policy import (
    EXPORT_POLICY_VERSION,
    PiiHit,
    scan_export_policy,
    scan_export_value,
)


def _claim_bundle_value(claim_snapshot: ClaimSnapshot) -> Mapping[str, Any]:
    """把 C7 bundle 投影为 scan_export_value 可递归的映射；不改原对象。"""
    bundle = claim_snapshot.bundle
    if bundle is None:
        return {
            "claims": [
                {"text": row.claim_text} for row in claim_snapshot.rows
            ]
        }
    return {
        "claims": [
            {
                "text": claim.text,
                "text_en": claim.text_en,
                "counterevidence_text": claim.counterevidence_text,
            }
            for claim in bundle.claims
        ],
        "evidences": [
            {"excerpt": evidence.excerpt, "url": evidence.url}
            for evidence in bundle.evidences
        ],
    }


def scan_delivery_inputs(
    *,
    manifest: DeliveryManifest,
    files: Sequence[DeliveryFile],
    public_contract: Mapping[str, Any],
    claim_snapshot: ClaimSnapshot,
) -> tuple[PiiHit, ...]:
    """只编排字段路径；规则、递归与去重都由 C11 export_policy 负责。"""
    hits: list[PiiHit] = []
    hits.extend(scan_export_value(dict(manifest.payload), field_path="manifest"))
    hits.extend(
        scan_export_value(dict(public_contract), field_path="public_contract")
    )
    hits.extend(
        scan_export_value(
            _claim_bundle_value(claim_snapshot), field_path="claim_bundle"
        )
    )
    for file in files:
        try:
            text = file.content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits.extend(scan_export_policy(text, field_path=file.path))
    return tuple(hits)


__all__ = ["EXPORT_POLICY_VERSION", "scan_delivery_inputs"]
```

- [ ] **Step 3f: 追加 Quick 发布与验收服务到 `service.py`**

```python
# 追加到 apps/api/src/data_intelligence_hub/services/delivery/service.py
from data_intelligence_hub.repositories.delivery import (
    get_acceptance_event_by_idempotency,
    get_latest_quick_draft,
    list_acceptance_events,
    list_pending_acceptance_artifacts,
)
from data_intelligence_hub.repositories.workbench_tasks import get_workbench_task
from data_intelligence_hub.services.delivery.acceptance import (
    acceptance_status_from_events,
    is_deemed_acceptance_due,
    validate_dispute_references,
)
from data_intelligence_hub.services.delivery.pii import scan_delivery_inputs
from data_intelligence_hub.services.delivery.quick import (
    assert_quick_contract,
    assert_quick_package,
)
from data_intelligence_hub.services.delivery.types import (
    AcceptanceEvent,
    AcceptanceResult,
    AcceptanceState,
    DeliveryClass,
    DisputeReference,
)


def _acceptance_event(row: ReportAuditEvent) -> AcceptanceEvent:
    import json

    return AcceptanceEvent(
        event_id=row.id,
        event_type=row.event_type,
        actor_id=row.actor_id,
        created_at=row.created_at,
        metadata=json.loads(row.metadata_json or "{}"),
    )


async def _acceptance_state(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact: ReportArtifact,
) -> AcceptanceState:
    if artifact.delivery_class == DeliveryClass.QUICK_DRAFT.value:
        return AcceptanceState(
            artifact_id=artifact.id,
            delivery_class=artifact.delivery_class,
            status="not_applicable",
            deadline=None,
            events=(),
        )
    rows = await list_acceptance_events(
        session, workspace_id=workspace_id, artifact_id=artifact.id
    )
    events = tuple(_acceptance_event(row) for row in rows)
    return AcceptanceState(
        artifact_id=artifact.id,
        delivery_class=artifact.delivery_class,
        status=acceptance_status_from_events(events),
        deadline=artifact.acceptance_deadline,
        events=events,
    )


async def load_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> AcceptanceState:
    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id
    )
    if artifact is None:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if artifact.delivery_status not in {
        DeliveryStatus.DELIVERED.value,
        DeliveryStatus.SUPERSEDED.value,
    }:
        raise DeliveryNotPublishedError("delivery_not_published")
    return await _acceptance_state(
        session, workspace_id=workspace_id, artifact=artifact
    )


def _acceptance_idempotency_key_hash(idempotency_key: str) -> str:
    """C1 固定派生：sha256("delivery-acceptance.v1:{idempotency_key}")。"""
    return sha256_hex(f"delivery-acceptance.v1:{idempotency_key}".encode("utf-8"))


def _acceptance_payload_sha256(
    *,
    event_type: str,
    artifact_id: uuid.UUID,
    references: Sequence[DisputeReference],
    note: str | None,
) -> str:
    # C1 §2.16：payload 只含 event_type、artifact_id、references 与可选 note。
    payload: dict[str, Any] = {
        "event_type": event_type,
        "artifact_id": str(artifact_id),
        "references": [
            {
                "path": reference.path,
                "description": reference.description,
                "claim_id": reference.claim_id,
                "evidence_id": reference.evidence_id,
                "item_id": reference.item_id,
            }
            for reference in references
        ],
    }
    if note is not None:
        payload["note"] = note
    return sha256_hex(canonical_bytes(payload))


async def _replay_or_conflict(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact: ReportArtifact,
    event_type: str,
    idempotency_key_hash: str,
    payload_sha256: str,
) -> AcceptanceResult | None:
    existing = await get_acceptance_event_by_idempotency(
        session,
        workspace_id=workspace_id,
        artifact_id=artifact.id,
        idempotency_key_hash=idempotency_key_hash,
    )
    if existing is None:
        return None
    event, metadata = existing
    if event.event_type != event_type or metadata.get("payload_sha256") != payload_sha256:
        raise IdempotencyConflictError("同一 Idempotency-Key 已用于不同的验收请求")
    state = await _acceptance_state(
        session, workspace_id=workspace_id, artifact=artifact
    )
    return AcceptanceResult(state=state, replay=True)


async def record_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    idempotency_key: str,
    references: Sequence[DisputeReference] = (),
    note: str | None = None,
    now: datetime | None = None,
) -> AcceptanceResult:
    if action not in {"accept", "dispute"}:
        raise ValueError("acceptance_action_invalid")
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("idempotency_key_required")
    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id, for_update=True
    )
    if artifact is None:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if artifact.delivery_class != DeliveryClass.FORMAL.value:
        raise AcceptanceNotApplicableError("acceptance_not_applicable")
    if artifact.delivery_status != DeliveryStatus.DELIVERED.value:
        raise DeliveryNotPublishedError("delivery_not_published")
    event_type = "acceptance_accepted" if action == "accept" else "acceptance_disputed"
    payload_sha256 = _acceptance_payload_sha256(
        event_type=event_type,
        artifact_id=artifact.id,
        references=references,
        note=note,
    )
    key_hash = _acceptance_idempotency_key_hash(idempotency_key)
    replay = await _replay_or_conflict(
        session,
        workspace_id=workspace_id,
        artifact=artifact,
        event_type=event_type,
        idempotency_key_hash=key_hash,
        payload_sha256=payload_sha256,
    )
    if replay is not None:
        return replay
    existing = await list_acceptance_events(
        session, workspace_id=workspace_id, artifact_id=artifact.id
    )
    if existing:
        raise AcceptanceClosedError("acceptance_already_closed")
    if action == "dispute":
        issues = validate_dispute_references(
            references,
            manifest=DeliveryManifest(
                payload=artifact.manifest_json or {},
                canonical_bytes=canonical_bytes(artifact.manifest_json or {}),
                sha256=artifact.manifest_sha256 or "",
                sidecar_bytes=b"",
                sidecar_sha256=artifact.manifest_sidecar_sha256 or "",
            ),
            public_contract=artifact.public_contract_json or {},
        )
        if issues:
            raise AcceptanceReferenceInvalidError("；".join(issues))
    moment = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    await create_delivery_event(
        session,
        _event(
            workspace_id=workspace_id,
            artifact_id=artifact.id,
            actor_id=actor_id,
            event_type=DeliveryEventType(event_type),
            metadata={
                "idempotency_key_hash": key_hash,
                "payload_sha256": payload_sha256,
                "manifest_sha256": artifact.manifest_sha256,
                "acceptance_deadline": (
                    artifact.acceptance_deadline.isoformat()
                    if artifact.acceptance_deadline
                    else None
                ),
                "note": note,
                "references": [
                    {
                        "path": reference.path,
                        "description": reference.description,
                        "claim_id": reference.claim_id,
                        "evidence_id": reference.evidence_id,
                        "item_id": reference.item_id,
                    }
                    for reference in references
                ],
            },
            now=moment,
        ),
    )
    await session.commit()
    state = await _acceptance_state(
        session, workspace_id=workspace_id, artifact=artifact
    )
    return AcceptanceResult(state=state, replay=False)


async def record_deemed_acceptance(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID,
    idempotency_key: str,
    now: datetime | None = None,
) -> AcceptanceResult:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("idempotency_key_required")
    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id, for_update=True
    )
    if artifact is None:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if artifact.delivery_class != DeliveryClass.FORMAL.value:
        raise AcceptanceNotApplicableError("acceptance_not_applicable")
    if artifact.delivery_status != DeliveryStatus.DELIVERED.value:
        raise DeliveryNotPublishedError("delivery_not_published")
    moment = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    if not is_deemed_acceptance_due(artifact.acceptance_deadline, moment):
        raise AcceptanceWindowOpenError("acceptance_window_open")
    key_hash = _acceptance_idempotency_key_hash(idempotency_key)
    payload_sha256 = _acceptance_payload_sha256(
        event_type="acceptance_deemed_accepted",
        artifact_id=artifact.id,
        references=(),
        note=None,
    )
    replay = await _replay_or_conflict(
        session,
        workspace_id=workspace_id,
        artifact=artifact,
        event_type="acceptance_deemed_accepted",
        idempotency_key_hash=key_hash,
        payload_sha256=payload_sha256,
    )
    if replay is not None:
        return replay
    existing = await list_acceptance_events(
        session, workspace_id=workspace_id, artifact_id=artifact.id
    )
    if existing:
        raise AcceptanceClosedError("acceptance_already_closed")
    await create_delivery_event(
        session,
        _event(
            workspace_id=workspace_id,
            artifact_id=artifact.id,
            actor_id=actor_id,
            event_type=DeliveryEventType.ACCEPTANCE_DEEMED_ACCEPTED,
            metadata={
                "idempotency_key_hash": key_hash,
                "payload_sha256": payload_sha256,
                "manifest_sha256": artifact.manifest_sha256,
                "acceptance_deadline": (
                    artifact.acceptance_deadline.isoformat()
                    if artifact.acceptance_deadline
                    else None
                ),
                "acceptance_window_business_days": 5,
            },
            now=moment,
        ),
    )
    await session.commit()
    state = await _acceptance_state(
        session, workspace_id=workspace_id, artifact=artifact
    )
    return AcceptanceResult(state=state, replay=False)


async def sweep_deemed_acceptances(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    now: datetime,
) -> list[AcceptanceResult]:
    results: list[AcceptanceResult] = []
    for artifact in await list_pending_acceptance_artifacts(
        session, workspace_id=workspace_id
    ):
        if not is_deemed_acceptance_due(artifact.acceptance_deadline, now):
            continue
        existing = await list_acceptance_events(
            session, workspace_id=workspace_id, artifact_id=artifact.id
        )
        if existing:
            continue
        results.append(
            await record_deemed_acceptance(
                session,
                workspace_id=workspace_id,
                artifact_id=artifact.id,
                actor_id=artifact.delivered_by or uuid.UUID(int=0),
                idempotency_key=f"deemed:{artifact.id}",
                now=now,
            )
        )
    return results


async def publish_quick_draft(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    idempotency_key: str,
    delivered_by: uuid.UUID,
    store: DeliveryStore,
    now: datetime | None = None,
) -> PublishResult:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("idempotency_key_required")
    moment = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    key_hash = sha256_hex(idempotency_key.encode("utf-8"))
    existing = await get_artifact_by_idempotency(
        session, workspace_id=workspace_id, key_hash=key_hash
    )
    if existing is not None:
        if (
            existing.id != artifact_id
            and existing.quick_draft_of_artifact_id != artifact_id
        ):
            raise IdempotencyConflictError("同一 Idempotency-Key 已用于另一份产物")
        manifest = await load_delivery_manifest(
            session, workspace_id=workspace_id, artifact_id=existing.id, store=store
        )
        return PublishResult(artifact=existing, manifest=manifest, replay=True)
    source = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id, for_update=True
    )
    if source is None or source.project_id != project_id:
        raise DeliveryNotFoundError("report_artifact_not_found")
    if source.status not in {"draft", "published"}:
        raise DeliveryNotPublishedError("quick_draft_source_invalid")
    if source.delivery_status == DeliveryStatus.DELIVERED.value:
        raise DeliveryNotPublishedError("quick_draft_already_delivered")
    if source.delivery_status != DeliveryStatus.PENDING.value:
        raise DeliveryNotPublishedError("quick_draft_not_pending")
    contract = dict(source.contract_json)
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        task_id=uuid.UUID(str(contract["task_id"])),
        project_id=project_id,
    )
    if task is None:
        raise DeliveryNotFoundError("workbench_task_not_found")
    assert_quick_package(str(task.package_type))
    assert_quick_contract(contract)
    assert_forbidden_language_free(contract)
    claim_snapshot = await load_claim_snapshot(
        session, workspace_id=workspace_id, project_id=project_id, contract=contract
    )
    g_claim = await evaluate_g_claim(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        artifact=source,
        contract=contract,
        claim_snapshot=claim_snapshot,
        package_type="quick",
    )
    if not g_claim.passed:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata=_gate_metadata(g_claim),
                now=moment,
            ),
        )
        await session.commit()
        raise GateFailedError((g_claim,))
    version = await get_dataset_version_scoped(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        version_id=dataset_version_id,
    )
    if version is None:
        raise DeliveryNotFoundError("dataset_version_not_found")
    if version.status != "saved":
        raise ValueError("dataset_version_not_saved")
    dataset = build_dataset_input(version)
    if not dataset.rows:
        raise ValueError("dataset_empty")
    payload_uuid = uuid.uuid4()
    public_contract = project_public_contract(
        contract,
        dataset=dataset.metadata,
        source_contract_sha256=source.contract_sha256,
    )
    content_files = _content_files(
        artifact=source,
        contract=contract,
        public_contract=public_contract,
        dataset=dataset,
    )
    notice_file = DeliveryFile(
        role=DeliveryFileRole.QUICK_DRAFT_NOTICE,
        path=QUICK_DRAFT_NOTICE_PATH,
        media_type="application/json",
        content=render_quick_draft_notice(
            artifact_id=source.id,
            task_id=uuid.UUID(str(contract["task_id"])),
            delivered_at=moment,
            package_type="quick",
        ),
    )
    files = (*content_files, notice_file)
    manifest = build_manifest(
        manifest_id=payload_uuid,
        artifact_id=source.id,
        task_id=uuid.UUID(str(contract["task_id"])),
        report_version=int(contract["report_version"]),
        files=files,
        access_scope=list(contract["delivery"]["access_scope"]),
        retention_class=str(contract["delivery"]["retention_class"]),
        created_at=moment,
        required_roles=QUICK_DRAFT_REQUIRED_ROLES,
    )
    pii_hits = scan_delivery_inputs(
        manifest=manifest,
        files=files,
        public_contract=public_contract,
        claim_snapshot=claim_snapshot,
    )
    if pii_hits:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata={
                    "gate_id": "G-Publish",
                    "status": "fail",
                    "export_policy_version": EXPORT_POLICY_VERSION,
                    "findings": [
                        {
                            "code": "delivery_pii_detected",
                            "kind": hit.kind,
                            "field_path": hit.field_path,
                        }
                        for hit in pii_hits
                    ],
                },
                now=moment,
            ),
        )
        await project_delivery_audit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_id=delivered_by,
            action="delivery.published",
            result="denied",
            artifact_id=artifact_id,
            details={
                "reason": "delivery_pii_detected",
                "hit_count": len(pii_hits),
                "export_policy_version": EXPORT_POLICY_VERSION,
                "delivery_class": "quick_draft",
            },
            now=moment,
        )
        await session.commit()
        raise DeliveryPiiError(pii_hits)
    g_publish = await evaluate_g_publish(
        session,
        workspace_id=workspace_id,
        artifact=source,
        contract=contract,
        claim_snapshot=claim_snapshot,
        g_claim=g_claim,
        signoff=None,
        dataset=dataset,
        files=files,
        manifest=manifest,
        acceptance_snapshot=None,
        now=moment,
        delivery_class=DeliveryClass.QUICK_DRAFT.value,
        require_published=False,
        signoff_artifact=source,
    )
    if not g_publish.passed:
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.GATE_EVALUATED,
                metadata=_gate_metadata(g_publish),
                now=moment,
            ),
        )
        await session.commit()
        raise GateFailedError((g_claim, g_publish))
    created = False
    try:
        try:
            store.write_bundle(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                files=files,
                manifest=manifest,
            )
        except DeliveryStoreConflict as exc:
            raise DeliveryIntegrityError(
                (BundleMismatch(path=".", reason="bundle_already_exists"),)
            ) from exc
        created = True
        source.delivery_status = DeliveryStatus.DELIVERED.value
        source.delivery_class = DeliveryClass.QUICK_DRAFT.value
        source.manifest_json = dict(manifest.payload)
        source.manifest_sha256 = manifest.sha256
        source.manifest_sidecar_sha256 = manifest.sidecar_sha256
        source.public_contract_json = public_contract
        source.acceptance_snapshot_json = None
        source.acceptance_deadline = None
        source.delivered_at = moment
        source.delivered_by = delivered_by
        source.publish_idempotency_key_hash = key_hash
        source.supersedes_delivery_id = None
        source.quick_draft_of_artifact_id = source.id
        for decision in (g_claim, g_publish):
            await create_delivery_event(
                session,
                _event(
                    workspace_id=workspace_id,
                    artifact_id=artifact_id,
                    actor_id=delivered_by,
                    event_type=DeliveryEventType.GATE_EVALUATED,
                    metadata=_gate_metadata(decision),
                    now=moment,
                ),
            )
        await create_delivery_event(
            session,
            _event(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                actor_id=delivered_by,
                event_type=DeliveryEventType.DELIVERY_PUBLISHED,
                metadata={
                    "delivery_class": "quick_draft",
                    "reviewed": False,
                    "acceptance": "not_applicable",
                    "formal_delivery_sla_hours": 24,
                    "manifest_sha256": manifest.sha256,
                    "manifest_sidecar_sha256": manifest.sidecar_sha256,
                    "dataset_version_id": str(dataset.version_id),
                    "dataset_sha256": dataset.csv_sha256,
                    "task_id": str(contract["task_id"]),
                },
                now=moment,
            ),
        )
        await project_delivery_audit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_id=delivered_by,
            action="delivery.published",
            result="success",
            artifact_id=artifact_id,
            details={
                "delivery_class": "quick_draft",
                "reviewed": False,
                "acceptance": "not_applicable",
                "manifest_sha256": manifest.sha256,
            },
            now=moment,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        if created:
            store.remove_bundle(workspace_id=workspace_id, artifact_id=artifact_id)
        raise
    return PublishResult(artifact=source, manifest=manifest, replay=False)


__all__ = [
    "AcceptanceClosedError",
    "AcceptanceNotApplicableError",
    "AcceptanceReferenceInvalidError",
    "AcceptanceWindowOpenError",
    "DeliveryError",
    "DeliveryIntegrityError",
    "DeliveryNotFoundError",
    "DeliveryNotPublishedError",
    "DeliveryPiiError",
    "GateFailedError",
    "IdempotencyConflictError",
    "load_acceptance",
    "load_delivery_manifest",
    "open_delivery_zip",
    "publish_delivery",
    "publish_quick_draft",
    "record_acceptance",
    "record_deemed_acceptance",
    "sweep_deemed_acceptances",
]
```

- [ ] **Step 3h: 写验收、Quick 与 PII 测试**

```python
# apps/api/tests/unit/test_delivery_acceptance.py
import uuid
from datetime import timedelta

import pytest

from data_intelligence_hub.services.delivery.canonical import (
    canonical_bytes,
    sha256_hex,
)
from data_intelligence_hub.services.delivery.service import (
    AcceptanceClosedError,
    AcceptanceReferenceInvalidError,
    AcceptanceWindowOpenError,
    IdempotencyConflictError,
    load_acceptance,
    publish_delivery,
    record_acceptance,
    record_deemed_acceptance,
)
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.delivery.types import DisputeReference


async def _published(session, seed, store):
    return await publish_delivery(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        artifact_id=seed.artifact_id,
        dataset_version_id=seed.dataset_version_id,
        idempotency_key="publish-1",
        delivered_by=seed.user_id,
        supersedes_artifact_id=None,
        store=store,
    )


async def test_accept_replay_and_conflict(session, delivery_seed, tmp_path) -> None:
    store = DeliveryStore(tmp_path)
    result = await _published(session, delivery_seed, store)
    artifact_id = result.artifact.id
    first = await record_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=artifact_id,
        actor_id=delivery_seed.user_id,
        action="accept",
        idempotency_key="accept-1",
        note="ok",
    )
    assert first.replay is False
    assert first.state.status == "accepted"
    accepted_event = first.state.events[-1]
    assert accepted_event.event_type == "acceptance_accepted"
    assert accepted_event.metadata["idempotency_key_hash"] == sha256_hex(
        b"delivery-acceptance.v1:accept-1"
    )
    assert accepted_event.metadata["payload_sha256"] == sha256_hex(
        canonical_bytes(
            {
                "event_type": "acceptance_accepted",
                "artifact_id": str(artifact_id),
                "references": [],
                "note": "ok",
            }
        )
    )
    replay = await record_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=artifact_id,
        actor_id=delivery_seed.user_id,
        action="accept",
        idempotency_key="accept-1",
        note="ok",
    )
    assert replay.replay is True
    with pytest.raises(IdempotencyConflictError):
        await record_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=artifact_id,
            actor_id=delivery_seed.user_id,
            action="accept",
            idempotency_key="accept-1",
            note="different",
        )
    with pytest.raises(IdempotencyConflictError):
        await record_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=artifact_id,
            actor_id=delivery_seed.user_id,
            action="dispute",
            idempotency_key="accept-1",
            references=(
                DisputeReference(path="report.zh.html", description="同 key 不同事件类型"),
            ),
        )


async def test_dispute_requires_itemized_references(session, delivery_seed, tmp_path) -> None:
    store = DeliveryStore(tmp_path)
    result = await _published(session, delivery_seed, store)
    with pytest.raises(AcceptanceReferenceInvalidError):
        await record_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=result.artifact.id,
            actor_id=delivery_seed.user_id,
            action="dispute",
            idempotency_key="dispute-1",
            references=(),
        )
    with pytest.raises(AcceptanceReferenceInvalidError):
        await record_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=result.artifact.id,
            actor_id=delivery_seed.user_id,
            action="dispute",
            idempotency_key="dispute-2",
            references=(DisputeReference(path="../escape", description="x"),),
        )
    disputed = await record_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=result.artifact.id,
        actor_id=delivery_seed.user_id,
        action="dispute",
        idempotency_key="dispute-3",
        references=(
            DisputeReference(path="report.zh.html", description="第 2 页指标口径"),
        ),
    )
    assert disputed.state.status == "objection"
    dispute_event = disputed.state.events[-1]
    assert dispute_event.event_type == "acceptance_disputed"
    assert dispute_event.metadata["references"][0]["path"] == "report.zh.html"
    assert dispute_event.metadata["idempotency_key_hash"] == sha256_hex(
        b"delivery-acceptance.v1:dispute-3"
    )
    assert dispute_event.metadata["payload_sha256"] == sha256_hex(
        canonical_bytes(
            {
                "event_type": "acceptance_disputed",
                "artifact_id": str(result.artifact.id),
                "references": [
                    {
                        "path": "report.zh.html",
                        "description": "第 2 页指标口径",
                        "claim_id": None,
                        "evidence_id": None,
                        "item_id": None,
                    }
                ],
            }
        )
    )
    with pytest.raises(AcceptanceClosedError):
        await record_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=result.artifact.id,
            actor_id=delivery_seed.user_id,
            action="accept",
            idempotency_key="accept-after-dispute",
        )


async def test_deemed_acceptance_waits_for_deadline(session, delivery_seed, tmp_path) -> None:
    store = DeliveryStore(tmp_path)
    result = await _published(session, delivery_seed, store)
    with pytest.raises(AcceptanceWindowOpenError):
        await record_deemed_acceptance(
            session,
            workspace_id=delivery_seed.workspace_id,
            artifact_id=result.artifact.id,
            actor_id=delivery_seed.user_id,
            idempotency_key="deemed-1",
            now=result.artifact.delivered_at,
        )
    deemed = await record_deemed_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=result.artifact.id,
        actor_id=delivery_seed.user_id,
        idempotency_key="deemed-1",
        now=result.artifact.acceptance_deadline + timedelta(seconds=1),
    )
    assert deemed.state.status == "auto_accepted"
    deemed_event = deemed.state.events[-1]
    assert deemed_event.event_type == "acceptance_deemed_accepted"
    assert deemed_event.metadata["idempotency_key_hash"] == sha256_hex(
        b"delivery-acceptance.v1:deemed-1"
    )
    assert deemed_event.metadata["payload_sha256"] == sha256_hex(
        canonical_bytes(
            {
                "event_type": "acceptance_deemed_accepted",
                "artifact_id": str(result.artifact.id),
                "references": [],
            }
        )
    )
    state = await load_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=result.artifact.id,
    )
    assert state.status == "auto_accepted"


async def test_acceptance_does_not_mutate_manifest(session, delivery_seed, tmp_path) -> None:
    store = DeliveryStore(tmp_path)
    result = await _published(session, delivery_seed, store)
    before = result.artifact.manifest_sha256
    before_files = dict(result.manifest.payload["files"][0])
    await record_acceptance(
        session,
        workspace_id=delivery_seed.workspace_id,
        artifact_id=result.artifact.id,
        actor_id=delivery_seed.user_id,
        action="accept",
        idempotency_key="accept-1",
    )
    await session.refresh(result.artifact)
    assert result.artifact.manifest_sha256 == before
    assert result.artifact.manifest_json["files"][0] == before_files
    assert store.verify_bundle(
        workspace_id=delivery_seed.workspace_id,
        artifact_id=result.artifact.id,
        manifest=result.manifest,
        expected_manifest_sha256=result.manifest.sha256,
        expected_sidecar_sha256=result.manifest.sidecar_sha256,
    ) == []
```

```python
# apps/api/tests/unit/test_delivery_pii.py
from dataclasses import fields

import pytest

from data_intelligence_hub.services.delivery.pii import scan_delivery_inputs
from data_intelligence_hub.services.delivery.service import DeliveryPiiError, publish_delivery
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.export_policy import PiiHit


def test_scan_returns_c11_hits_and_never_echoes_raw_value() -> None:
    from data_intelligence_hub.services.delivery.manifest import build_manifest
    from data_intelligence_hub.services.delivery.types import (
        DeliveryFile,
        DeliveryFileRole,
    )

    file = DeliveryFile(
        role=DeliveryFileRole.REPORT_ZH,
        path="report.zh.html",
        media_type="text/html",
        content=b"<p>contact buyer@example.com</p>",
    )
    manifest = build_manifest(
        manifest_id=__import__("uuid").uuid4(),
        artifact_id=__import__("uuid").uuid4(),
        task_id=__import__("uuid").uuid4(),
        report_version=1,
        files=(file,),
        access_scope=["workspace_project"],
        retention_class="standard_24m",
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        required_roles=(DeliveryFileRole.REPORT_ZH,),
    )
    snapshot = __import__("types").SimpleNamespace(rows=(), bundle=None)
    hits = scan_delivery_inputs(
        manifest=manifest, files=(file,), public_contract={}, claim_snapshot=snapshot
    )
    assert hits
    assert all(isinstance(hit, PiiHit) for hit in hits)
    assert {field.name for field in fields(PiiHit)} == {
        "kind",
        "field_path",
        "start",
        "end",
    }
    assert {hit.kind for hit in hits} == {"contact"}
    assert any(hit.field_path == "report.zh.html" for hit in hits)
    assert "buyer@example.com" not in repr(hits)


async def test_publish_blocks_on_pii(session, delivery_seed, tmp_path) -> None:
    delivery_seed.artifact.contract_json["claims"][0]["text"] = "联系 buyer@example.com"
    await session.flush()
    with pytest.raises(DeliveryPiiError) as excinfo:
        await publish_delivery(
            session,
            workspace_id=delivery_seed.workspace_id,
            project_id=delivery_seed.project_id,
            artifact_id=delivery_seed.artifact_id,
            dataset_version_id=delivery_seed.dataset_version_id,
            idempotency_key="publish-pii",
            delivered_by=delivery_seed.user_id,
            supersedes_artifact_id=None,
            store=DeliveryStore(tmp_path),
        )
    assert excinfo.value.hits
    assert all(isinstance(hit, PiiHit) for hit in excinfo.value.hits)
    await session.refresh(delivery_seed.artifact)
    assert delivery_seed.artifact.delivery_status == "pending"
```

```python
# apps/api/tests/unit/test_delivery_quick.py
import pytest

from data_intelligence_hub.services.delivery.quick import (
    assert_quick_contract,
    assert_quick_package,
)
from data_intelligence_hub.services.delivery.service import publish_quick_draft
from data_intelligence_hub.services.delivery.store import DeliveryStore


def test_quick_guard_rejects_standard_package_and_four_state() -> None:
    with pytest.raises(ValueError, match="quick_draft_not_allowed"):
        assert_quick_package("standard")
    contract = {"markets": [{"conclusion_standard": "enter"}], "claims": []}
    with pytest.raises(ValueError, match="quick_draft_claim_invalid"):
        assert_quick_contract(contract)
    contract = {"markets": [{"conclusion_quick": "worth_validating"}], "claims": [{"claim_status": "confirmed"}]}
    with pytest.raises(ValueError, match="quick_draft_claim_invalid"):
        assert_quick_contract(contract)


async def test_quick_draft_has_no_acceptance_and_no_extra_cost(
    session, delivery_seed, tmp_path
) -> None:
    from sqlalchemy import text

    before_ledger = (
        await session.execute(text("select count(*) from run_ledger_entries"))
    ).scalar_one()
    before_datasets = (
        await session.execute(text("select count(*) from dataset_versions"))
    ).scalar_one()
    result = await publish_quick_draft(
        session,
        workspace_id=delivery_seed.workspace_id,
        project_id=delivery_seed.project_id,
        artifact_id=delivery_seed.artifact_id,
        dataset_version_id=delivery_seed.dataset_version_id,
        idempotency_key="quick-1",
        delivered_by=delivery_seed.user_id,
        store=DeliveryStore(tmp_path),
    )
    assert result.artifact.delivery_class == "quick_draft"
    assert result.artifact.acceptance_deadline is None
    assert result.artifact.acceptance_snapshot_json is None
    assert {
        entry["path"] for entry in result.manifest.payload["files"]
    } >= {"quick_draft_notice.json"}
    assert "acceptance_snapshot.json" not in {
        entry["path"] for entry in result.manifest.payload["files"]
    }
    assert (
        await session.execute(text("select count(*) from run_ledger_entries"))
    ).scalar_one() == before_ledger
    assert (
        await session.execute(text("select count(*) from dataset_versions"))
    ).scalar_one() == before_datasets
```

Quick 测试还需要一个 `WorkbenchTask(package_type="quick")` 夹具，并在 `delivery_seed` 中把 `task_id` 设为该任务；正式测试用 `standard`。不得用 `workspace_members.role` 替代包型。

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_service.py tests/unit/test_delivery_acceptance.py tests/unit/test_delivery_pii.py tests/unit/test_delivery_quick.py -v
```

Expected: 全部 passed。正式发布测试断言 `delivery_published`、`acceptance_snapshot_appended`；Quick 测试断言无 `acceptance_snapshot_appended`、`acceptance_deadline is None`、`quick_draft_notice.json` 存在；验收测试断言 replay/conflict、逐项引用、逾期 deemed 与 manifest 哈希不变；PII 测试断言 409 路径不写 bundle。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/services/delivery/service.py src/data_intelligence_hub/services/delivery/audit.py src/data_intelligence_hub/services/delivery/acceptance.py src/data_intelligence_hub/services/delivery/quick.py src/data_intelligence_hub/services/delivery/pii.py tests/unit/test_delivery_service.py tests/unit/test_delivery_acceptance.py tests/unit/test_delivery_quick.py tests/unit/test_delivery_pii.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/services/delivery/service.py src/data_intelligence_hub/services/delivery/audit.py src/data_intelligence_hub/services/delivery/acceptance.py src/data_intelligence_hub/services/delivery/quick.py src/data_intelligence_hub/services/delivery/pii.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/delivery/service.py \
  apps/api/src/data_intelligence_hub/services/delivery/audit.py \
  apps/api/src/data_intelligence_hub/services/delivery/acceptance.py \
  apps/api/src/data_intelligence_hub/services/delivery/quick.py \
  apps/api/src/data_intelligence_hub/services/delivery/pii.py \
  apps/api/tests/unit/test_delivery_service.py \
  apps/api/tests/unit/test_delivery_acceptance.py \
  apps/api/tests/unit/test_delivery_quick.py \
  apps/api/tests/unit/test_delivery_pii.py
git commit -m "feat(delivery): publish quick drafts, append acceptance events and block PII"
```

---

### Task 10: HTTP 端点、鉴权与响应模型

**Files:**
- Create: `apps/api/src/data_intelligence_hub/schemas/delivery.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/delivery.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`
- Test: `apps/api/tests/unit/test_delivery_routes.py`

**Interfaces:**
- Consumes: `publish_delivery`、`publish_quick_draft`、`load_delivery_manifest`、`open_delivery_zip`、`load_acceptance`、`record_acceptance`、`record_deemed_acceptance`；C2 `require_project_access_audited`、`get_workbench_task`、`get_latest_quick_draft`。
- Produces: `POST /api/reports/{artifact_id}/delivery/publish`、`GET /api/reports/{artifact_id}/delivery`、`GET /api/reports/{artifact_id}/delivery/manifest`、`POST/GET /api/reports/{artifact_id}/delivery/quick-draft`、`GET /api/tasks/{task_id}/delivery/quick-draft`、`GET/POST /api/reports/{artifact_id}/delivery/acceptance/*`。

- [ ] **Step 1: 写路由失败测试**

```python
# apps/api/tests/unit/test_delivery_routes.py
import io
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from data_intelligence_hub.api.deps import AuthContext, get_authenticated_context
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.services.delivery.store import DeliveryStore


def _client_for(session, seed, user, tmp_path):
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_authenticated_context] = lambda: AuthContext(
        user=user, workspace=seed.workspace
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.fixture
async def client(session, delivery_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "data_intelligence_hub.api.routes.delivery._store",
        lambda: DeliveryStore(tmp_path),
    )
    async with _client_for(
        session, delivery_seed, delivery_seed.user, tmp_path
    ) as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.fixture
async def member_client(session, delivery_seed, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "data_intelligence_hub.api.routes.delivery._store",
        lambda: DeliveryStore(tmp_path),
    )
    async with _client_for(
        session, delivery_seed, delivery_seed.member, tmp_path
    ) as async_client:
        yield async_client
    app.dependency_overrides.clear()


async def test_publish_then_download(client: AsyncClient, delivery_seed) -> None:
    response = await client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/publish",
        headers={"Idempotency-Key": "publish-1"},
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["delivery_status"] == "delivered"
    assert len(body["manifest_sha256"]) == 64

    delivery_artifact_id = body["report_artifact_id"]
    download = await client.get(f"/api/reports/{delivery_artifact_id}/delivery")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert "delivery_manifest.json" in archive.namelist()
        assert "report_contract.json" in archive.namelist()


async def test_member_cannot_publish(
    member_client: AsyncClient, delivery_seed
) -> None:
    response = await member_client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/publish",
        headers={"Idempotency-Key": "publish-1"},
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert response.status_code == 403


async def test_unknown_artifact_is_404(
    client: AsyncClient, delivery_seed
) -> None:
    response = await client.get(
        "/api/reports/00000000-0000-0000-0000-000000000000/delivery"
    )
    assert response.status_code == 404


async def test_missing_idempotency_key_is_400(
    client: AsyncClient, delivery_seed
) -> None:
    response = await client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/publish",
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "idempotency_key_required"


async def test_tampered_download_is_409(
    client: AsyncClient, delivery_seed, tmp_path
) -> None:
    publish = await client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/publish",
        headers={"Idempotency-Key": "publish-1"},
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert publish.status_code == 201, publish.text
    delivery_artifact_id = publish.json()["report_artifact_id"]
    target = (
        tmp_path
        / str(delivery_seed.workspace_id)
        / str(delivery_artifact_id)
        / "report.zh.html"
    )
    target.write_bytes(target.read_bytes() + b"tamper")
    response = await client.get(f"/api/reports/{delivery_artifact_id}/delivery")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "delivery_integrity_error"


async def test_acceptance_requires_idempotency_and_replays(
    client: AsyncClient, delivery_seed
) -> None:
    publish = await client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/publish",
        headers={"Idempotency-Key": "publish-1"},
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert publish.status_code == 201, publish.text
    artifact_id = publish.json()["report_artifact_id"]
    missing = await client.post(
        f"/api/reports/{artifact_id}/delivery/acceptance/accept", json={"note": "ok"}
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "idempotency_key_required"
    first = await client.post(
        f"/api/reports/{artifact_id}/delivery/acceptance/accept",
        headers={"Idempotency-Key": "accept-1"},
        json={"note": "ok"},
    )
    assert first.status_code == 201
    replay = await client.post(
        f"/api/reports/{artifact_id}/delivery/acceptance/accept",
        headers={"Idempotency-Key": "accept-1"},
        json={"note": "ok"},
    )
    assert replay.status_code == 200
    conflict = await client.post(
        f"/api/reports/{artifact_id}/delivery/acceptance/accept",
        headers={"Idempotency-Key": "accept-1"},
        json={"note": "different"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"


async def test_quick_draft_and_acceptance_read_routes(
    client: AsyncClient, delivery_seed
) -> None:
    quick = await client.post(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/quick-draft",
        headers={"Idempotency-Key": "quick-1"},
        json={"dataset_version_id": str(delivery_seed.dataset_version_id)},
    )
    assert quick.status_code in {201, 404, 422}
    if quick.status_code == 404:
        assert quick.json()["detail"] == "workbench_task_not_found"
    if quick.status_code == 422:
        assert quick.json()["detail"]["code"] in {
            "quick_draft_not_allowed",
            "quick_draft_claim_invalid",
        }
    acceptance = await client.get(
        f"/api/reports/{delivery_seed.artifact_id}/delivery/acceptance"
    )
    assert acceptance.status_code == 200
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_routes.py -v
```

Expected: `ModuleNotFoundError: No module named 'data_intelligence_hub.api.routes.delivery'` 或 404。

- [ ] **Step 3: 写 schema**

```python
# apps/api/src/data_intelligence_hub/schemas/delivery.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliveryPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: uuid.UUID
    supersedes_artifact_id: uuid.UUID | None = None


class DeliveryFileResponse(BaseModel):
    path: str
    media_type: str
    size_bytes: int
    sha256: str


class DeliveryManifestResponse(BaseModel):
    manifest_id: uuid.UUID
    task_id: uuid.UUID
    report_artifact_id: uuid.UUID
    delivery_status: str
    report_version: int
    created_at: datetime
    bundle_sha256: str
    sidecar_sha256: str
    access_scope: list[str]
    retention_class: str
    manifest_sha256: str
    manifest_sidecar_sha256: str
    files: list[DeliveryFileResponse]
    idempotency_replayed: bool = False


class DeliveryGateFindingResponse(BaseModel):
    gate_id: str
    status: str
    findings: list[dict[str, str | None]]


class DeliveryErrorResponse(BaseModel):
    code: str
    message: str
    gates: list[DeliveryGateFindingResponse] = Field(default_factory=list)
    mismatches: list[dict[str, str | None]] = Field(default_factory=list)


class DeliveryQuickDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: uuid.UUID


class AcceptanceReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    description: str
    claim_id: str | None = None
    evidence_id: str | None = None
    item_id: str | None = None


class AcceptanceAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = None


class AcceptanceDisputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    references: list[AcceptanceReferenceRequest] = Field(min_length=1)
    note: str | None = None


class AcceptanceEventResponse(BaseModel):
    event_id: uuid.UUID
    event_type: str
    actor_id: uuid.UUID | None
    created_at: datetime
    metadata: dict = Field(default_factory=dict)


class AcceptanceStateResponse(BaseModel):
    artifact_id: uuid.UUID
    delivery_class: str
    acceptance_status: str
    deadline: datetime | None
    events: list[AcceptanceEventResponse]
    idempotency_replayed: bool = False
```

- [ ] **Step 4: 写路由**

```python
# apps/api/src/data_intelligence_hub/api/routes/delivery.py
from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_authenticated_context
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.repositories.delivery import get_latest_quick_draft
from data_intelligence_hub.schemas.delivery import (
    AcceptanceAcceptRequest,
    AcceptanceDisputeRequest,
    AcceptanceEventResponse,
    AcceptanceStateResponse,
    DeliveryFileResponse,
    DeliveryManifestResponse,
    DeliveryPublishRequest,
    DeliveryQuickDraftRequest,
)
from data_intelligence_hub.services.delivery.service import (
    AcceptanceClosedError,
    AcceptanceNotApplicableError,
    AcceptanceReferenceInvalidError,
    AcceptanceWindowOpenError,
    DeliveryIntegrityError,
    DeliveryNotFoundError,
    DeliveryNotPublishedError,
    DeliveryPiiError,
    GateFailedError,
    IdempotencyConflictError,
    load_acceptance,
    load_delivery_manifest,
    open_delivery_zip,
    publish_delivery,
    publish_quick_draft,
    record_acceptance,
    record_deemed_acceptance,
)
from data_intelligence_hub.services.delivery.store import DeliveryStore
from data_intelligence_hub.services.delivery.types import (
    AcceptanceState,
    DeliveryManifest,
    DisputeReference,
)

router = APIRouter(tags=["delivery"])
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _store() -> DeliveryStore:
    return DeliveryStore(get_settings().delivery_export_dir)


def _manifest_response(
    artifact_id: uuid.UUID,
    artifact: ReportArtifact,
    manifest: DeliveryManifest,
    *,
    replay: bool,
) -> DeliveryManifestResponse:
    return DeliveryManifestResponse(
        manifest_id=uuid.UUID(str(manifest.payload["manifest_id"])),
        task_id=uuid.UUID(str(manifest.payload["task_id"])),
        report_artifact_id=uuid.UUID(str(manifest.payload["report_artifact_id"])),
        delivery_status=str(artifact.delivery_status),
        report_version=int(manifest.payload["report_version"]),
        created_at=datetime.fromisoformat(
            str(manifest.payload["created_at"]).replace("Z", "+00:00")
        ),
        bundle_sha256=str(manifest.payload["bundle_sha256"]),
        sidecar_sha256=str(manifest.payload["sidecar_sha256"]),
        access_scope=[str(item) for item in manifest.payload["access_scope"]],
        retention_class=str(manifest.payload["retention_class"]),
        manifest_sha256=manifest.sha256,
        manifest_sidecar_sha256=manifest.sidecar_sha256,
        files=[
            DeliveryFileResponse(
                path=str(entry["path"]),
                media_type=str(entry["media_type"]),
                size_bytes=int(entry["size_bytes"]),
                sha256=str(entry["sha256"]),
            )
            for entry in manifest.payload["files"]
        ],
        idempotency_replayed=replay,
    )


@router.post(
    "/{artifact_id}/delivery/publish",
    response_model=DeliveryManifestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_report_delivery(
    artifact_id: uuid.UUID,
    payload: DeliveryPublishRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DeliveryManifestResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "idempotency_key_required", "message": "缺少 Idempotency-Key"},
        )
    artifact = await _require_project(session, context, artifact_id, manage=True)
    try:
        result = await publish_delivery(
            session,
            workspace_id=context.workspace.id,
            project_id=artifact.project_id,
            artifact_id=artifact_id,
            dataset_version_id=payload.dataset_version_id,
            idempotency_key=idempotency_key,
            delivered_by=context.user.id,
            supersedes_artifact_id=payload.supersedes_artifact_id,
            store=_store(),
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryPiiError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_pii_detected", "hit_count": len(exc.hits)},
        ) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_not_publishable", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "delivery_input_invalid", "message": str(exc)},
        ) from exc
    except GateFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "gate_failed",
                "gates": [
                    {
                        "gate_id": decision.gate_id,
                        "status": decision.status,
                        "findings": [
                            {
                                "code": finding.code,
                                "message": finding.message,
                                "subject_id": finding.subject_id,
                            }
                            for finding in decision.findings
                        ],
                    }
                    for decision in exc.decisions
                ],
            },
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc
    except DeliveryIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "delivery_integrity_error",
                "mismatches": [
                    {"path": item.path, "reason": item.reason}
                    for item in exc.mismatches
                ],
            },
        ) from exc
    response.status_code = status.HTTP_200_OK if result.replay else status.HTTP_201_CREATED
    return _manifest_response(result.artifact.id, result.artifact, result.manifest, replay=result.replay)


@router.get(
    "/{artifact_id}/delivery/manifest",
    response_model=DeliveryManifestResponse,
)
async def get_report_delivery_manifest(
    artifact_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> DeliveryManifestResponse:
    try:
        artifact = await _require_project(session, context, artifact_id, manage=False)
        manifest = await load_delivery_manifest(
            session,
            workspace_id=context.workspace.id,
            artifact_id=artifact_id,
            store=_store(),
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DeliveryIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "delivery_integrity_error",
                "mismatches": [
                    {"path": item.path, "reason": item.reason}
                    for item in exc.mismatches
                ],
            },
        ) from exc
    return _manifest_response(artifact_id, artifact, manifest, replay=False)


@router.get("/{artifact_id}/delivery")
async def download_report_delivery(
    artifact_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> Response:
    try:
        artifact = await _require_project(session, context, artifact_id, manage=False)
        data, filename = await open_delivery_zip(
            session,
            workspace_id=context.workspace.id,
            artifact_id=artifact_id,
            actor_id=context.user.id,
            store=_store(),
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DeliveryIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "delivery_integrity_error",
                "mismatches": [
                    {"path": item.path, "reason": item.reason}
                    for item in exc.mismatches
                ],
            },
        ) from exc
    safe = _SAFE_FILENAME.sub("-", filename)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Manifest-SHA256": artifact.manifest_sha256 or "",
        },
    )


# ---- Quick 2 小时稿与验收路由 ----

tasks_router = APIRouter(tags=["delivery"])


def _acceptance_response(
    state: AcceptanceState, *, replay: bool
) -> AcceptanceStateResponse:
    return AcceptanceStateResponse(
        artifact_id=state.artifact_id,
        delivery_class=state.delivery_class,
        acceptance_status=state.status,
        deadline=state.deadline,
        events=[
            AcceptanceEventResponse(
                event_id=event.event_id,
                event_type=event.event_type,
                actor_id=event.actor_id,
                created_at=event.created_at,
                metadata=dict(event.metadata),
            )
            for event in state.events
        ],
        idempotency_replayed=replay,
    )


async def _require_project(
    session: AsyncSession,
    context: AuthContext,
    artifact_id: uuid.UUID,
    *,
    manage: bool,
) -> ReportArtifact:
    from data_intelligence_hub.api.authz import require_project_access_audited

    artifact = await _load_artifact(session, context.workspace.id, artifact_id)
    await require_project_access_audited(
        session,
        context=context,
        project_id=artifact.project_id,
        manage=manage,
        request_id=getattr(context, "request_id", "") or "",
    )
    return artifact


@router.post(
    "/{artifact_id}/delivery/quick-draft",
    response_model=DeliveryManifestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_report_quick_draft(
    artifact_id: uuid.UUID,
    payload: DeliveryQuickDraftRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DeliveryManifestResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "idempotency_key_required", "message": "缺少 Idempotency-Key"},
        )
    artifact = await _require_project(session, context, artifact_id, manage=True)
    try:
        result = await publish_quick_draft(
            session,
            workspace_id=context.workspace.id,
            project_id=artifact.project_id,
            artifact_id=artifact_id,
            dataset_version_id=payload.dataset_version_id,
            idempotency_key=idempotency_key,
            delivered_by=context.user.id,
            store=_store(),
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryPiiError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_pii_detected", "hit_count": len(exc.hits)},
        ) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_not_publishable", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        message = str(exc)
        code = (
            "quick_draft_not_allowed"
            if message == "quick_draft_not_allowed"
            else "quick_draft_claim_invalid"
            if message.startswith("quick_draft_claim_invalid")
            else "delivery_input_invalid"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": code, "message": message},
        ) from exc
    except GateFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "gate_failed", "gates": [
                {
                    "gate_id": decision.gate_id,
                    "status": decision.status,
                    "findings": [
                        {
                            "code": finding.code,
                            "message": finding.message,
                            "subject_id": finding.subject_id,
                        }
                        for finding in decision.findings
                    ],
                }
                for decision in exc.decisions
            ]},
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc
    except DeliveryIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "delivery_integrity_error",
                "mismatches": [
                    {"path": item.path, "reason": item.reason}
                    for item in exc.mismatches
                ],
            },
        ) from exc
    response.status_code = status.HTTP_200_OK if result.replay else status.HTTP_201_CREATED
    return _manifest_response(
        result.artifact.id, result.artifact, result.manifest, replay=result.replay
    )


@router.get("/{artifact_id}/delivery/quick-draft")
async def download_report_quick_draft(
    artifact_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> Response:
    artifact = await _require_project(session, context, artifact_id, manage=False)
    if artifact.delivery_class != "quick_draft":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "quick_draft_not_found", "message": "不是 Quick 2 小时稿"},
        )
    data, filename = await open_delivery_zip(
        session,
        workspace_id=context.workspace.id,
        artifact_id=artifact_id,
        actor_id=context.user.id,
        store=_store(),
    )
    safe = _SAFE_FILENAME.sub("-", filename)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Manifest-SHA256": artifact.manifest_sha256 or "",
        },
    )


@tasks_router.get(
    "/tasks/{task_id}/delivery/quick-draft",
    response_model=DeliveryManifestResponse,
)
async def get_task_quick_draft(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> DeliveryManifestResponse:
    from data_intelligence_hub.api.authz import require_project_access_audited
    from data_intelligence_hub.repositories.workbench_tasks import get_workbench_task

    task = await get_workbench_task(
        session, workspace_id=context.workspace.id, task_id=task_id
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task_not_found")
    await require_project_access_audited(
        session,
        context=context,
        project_id=task.project_id,
        manage=False,
        request_id=getattr(context, "request_id", "") or "",
    )
    artifact = await get_latest_quick_draft(
        session,
        workspace_id=context.workspace.id,
        project_id=task.project_id,
        task_id=task_id,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "quick_draft_not_found", "message": "该任务没有 Quick 稿"},
        )
    manifest = await load_delivery_manifest(
        session,
        workspace_id=context.workspace.id,
        artifact_id=artifact.id,
        store=_store(),
    )
    return _manifest_response(artifact.id, artifact, manifest, replay=False)


@router.get(
    "/{artifact_id}/delivery/acceptance",
    response_model=AcceptanceStateResponse,
)
async def get_delivery_acceptance(
    artifact_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> AcceptanceStateResponse:
    await _require_project(session, context, artifact_id, manage=False)
    try:
        state = await load_acceptance(
            session, workspace_id=context.workspace.id, artifact_id=artifact_id
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_not_publishable", "message": str(exc)},
        ) from exc
    return _acceptance_response(state, replay=False)


@router.post(
    "/{artifact_id}/delivery/acceptance/accept",
    response_model=AcceptanceStateResponse,
)
async def accept_delivery(
    artifact_id: uuid.UUID,
    payload: AcceptanceAcceptRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AcceptanceStateResponse:
    return await _record_acceptance_route(
        session,
        context,
        artifact_id,
        action="accept",
        references=(),
        note=payload.note,
        idempotency_key=idempotency_key,
        response=response,
    )


@router.post(
    "/{artifact_id}/delivery/acceptance/dispute",
    response_model=AcceptanceStateResponse,
)
async def dispute_delivery(
    artifact_id: uuid.UUID,
    payload: AcceptanceDisputeRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AcceptanceStateResponse:
    return await _record_acceptance_route(
        session,
        context,
        artifact_id,
        action="dispute",
        references=tuple(
            DisputeReference(
                path=item.path,
                description=item.description,
                claim_id=item.claim_id,
                evidence_id=item.evidence_id,
                item_id=item.item_id,
            )
            for item in payload.references
        ),
        note=payload.note,
        idempotency_key=idempotency_key,
        response=response,
    )


@router.post(
    "/{artifact_id}/delivery/acceptance/deemed-accepted",
    response_model=AcceptanceStateResponse,
)
async def deem_delivery_accepted(
    artifact_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AcceptanceStateResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "idempotency_key_required", "message": "缺少 Idempotency-Key"},
        )
    await _require_project(session, context, artifact_id, manage=True)
    try:
        result = await record_deemed_acceptance(
            session,
            workspace_id=context.workspace.id,
            artifact_id=artifact_id,
            actor_id=context.user.id,
            idempotency_key=idempotency_key,
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_not_publishable", "message": str(exc)},
        ) from exc
    except AcceptanceNotApplicableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "acceptance_not_applicable", "message": str(exc)},
        ) from exc
    except AcceptanceWindowOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "acceptance_window_open", "message": str(exc)},
        ) from exc
    except AcceptanceClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "acceptance_already_closed", "message": str(exc)},
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc
    return _acceptance_response(result.state, replay=result.replay)


async def _record_acceptance_route(
    session: AsyncSession,
    context: AuthContext,
    artifact_id: uuid.UUID,
    *,
    action: str,
    references: tuple[DisputeReference, ...],
    note: str | None,
    idempotency_key: str | None,
    response: Response,
) -> AcceptanceStateResponse:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "idempotency_key_required", "message": "缺少 Idempotency-Key"},
        )
    await _require_project(session, context, artifact_id, manage=True)
    try:
        result = await record_acceptance(
            session,
            workspace_id=context.workspace.id,
            artifact_id=artifact_id,
            actor_id=context.user.id,
            action=action,
            idempotency_key=idempotency_key,
            references=references,
            note=note,
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DeliveryNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "delivery_not_publishable", "message": str(exc)},
        ) from exc
    except AcceptanceNotApplicableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "acceptance_not_applicable", "message": str(exc)},
        ) from exc
    except AcceptanceReferenceInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "acceptance_reference_invalid", "message": str(exc)},
        ) from exc
    except AcceptanceClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "acceptance_already_closed", "message": str(exc)},
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc
    response.status_code = status.HTTP_200_OK if result.replay else status.HTTP_201_CREATED
    return _acceptance_response(result.state, replay=result.replay)


async def _load_artifact(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> ReportArtifact:
    from data_intelligence_hub.repositories.delivery import get_artifact_for_publish

    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id
    )
    if artifact is None:
        raise DeliveryNotFoundError("report_artifact_not_found")
    return artifact


async def _artifact_project_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> uuid.UUID:
    artifact = await _load_artifact(session, workspace_id, artifact_id)
    return artifact.project_id


async def _manifest_sha(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> str:
    from data_intelligence_hub.repositories.delivery import get_artifact_for_publish

    artifact = await get_artifact_for_publish(
        session, workspace_id=workspace_id, artifact_id=artifact_id
    )
    if artifact is None or artifact.manifest_sha256 is None:
        return ""
    return artifact.manifest_sha256
```

`_manifest_sha` 与 `_load_artifact` 是同步辅助，保持简单；不要在路由里复制业务规则。`publish` 先取 artifact 的 project_id，再调用 service；service 会再次校验 project 与 workspace。

- [ ] **Step 5: 修改 `main.py`**

```python
# main.py 导入
from data_intelligence_hub.api.routes.delivery import (
    router as delivery_router,
    tasks_router as delivery_tasks_router,
)

# 路径与 C9 的 /api/reports/{report_id}/publish 不冲突。
app.include_router(delivery_router, prefix="/api/reports")
app.include_router(delivery_tasks_router, prefix="/api")
app.include_router(reports_router, prefix="/api/reports")
```

- [ ] **Step 6: 运行路由测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_routes.py -v
```

Expected: 全部 `passed`。新增用例必须覆盖：Quick 稿 POST/GET、同任务 GET、Standard 拒绝 422、验收 GET/accept/dispute/deemed、replay 200、不同 payload 409 `idempotency_conflict`、Quick 验收 409 `acceptance_not_applicable`、PII 409 `delivery_pii_detected`、member 写 403、跨项目 403、跨工作区 404。`/delivery/publish` 与 C9 的 `/publish` 路径形状不同，不得依赖 include 顺序遮蔽 C9 路由。

- [ ] **Step 7: 运行既有报告路由测试，确认响应模型兼容**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_demo_data.py tests/unit/test_public_content_retention.py tests/unit/test_e2e_cleanup.py tests/unit/test_scheduler.py
```

Expected: 全部通过。`ReportAuditEventResponse` 新增 `artifact_id` 为 `None` 不得破坏 legacy 响应。

- [ ] **Step 8: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check src/data_intelligence_hub/schemas/delivery.py src/data_intelligence_hub/api/routes/delivery.py src/data_intelligence_hub/main.py tests/unit/test_delivery_routes.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy src/data_intelligence_hub/schemas/delivery.py src/data_intelligence_hub/api/routes/delivery.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/schemas/delivery.py \
  apps/api/src/data_intelligence_hub/api/routes/delivery.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/tests/unit/test_delivery_routes.py
git commit -m "feat(delivery): expose publish, manifest and download endpoints"
```

---

### Task 11: 配置、运维手册与全量验证

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/.env.example`
- Create: `docs/operations/delivery-publish.md`
- Test: `apps/api/tests/unit/test_delivery_config.py`

**Interfaces:**
- Consumes: `Settings`。
- Produces: `delivery_export_dir`、PG0 发布批次交接变量与运维命令。

- [ ] **Step 1: 写配置失败测试**

```python
# apps/api/tests/unit/test_delivery_config.py
from data_intelligence_hub.core.config import Settings


def test_delivery_export_dir_default(monkeypatch) -> None:
    monkeypatch.delenv("DELIVERY_EXPORT_DIR", raising=False)
    settings = Settings(_env_file=None)
    assert settings.delivery_export_dir == "tmp/delivery-exports"


def test_delivery_export_dir_reads_exact_env_name(monkeypatch) -> None:
    monkeypatch.setenv("DELIVERY_EXPORT_DIR", "/tmp/custom-deliveries")
    settings = Settings(_env_file=None)
    assert settings.delivery_export_dir == "/tmp/custom-deliveries"
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_config.py -v
```

Expected: 两个测试都报 `AttributeError: 'Settings' object has no attribute 'delivery_export_dir'`。

- [ ] **Step 3: 修改配置并登记 PG0 发布批次 compose 交接**

```python
# core/config.py，放在 dataset_export_dir 之后
delivery_export_dir: str = "tmp/delivery-exports"
```

```dotenv
# apps/api/.env.example
DELIVERY_EXPORT_DIR=tmp/delivery-exports
```

`configs/deploy/scrapy/docker-compose.yml` 是生产 A/B 共用的 compose，由 PG0 发布批次修改。C10 不修改该文件，只在此登记交接：PG0 发布批次在 `DATASET_EXPORT_DIR` 下一行加入：

```yaml
DELIVERY_EXPORT_DIR: ${SCRAPY_DELIVERY_EXPORT_DIR:-/app/exports/deliveries}
```

容器内变量名必须是 `DELIVERY_EXPORT_DIR`，与 `Settings.delivery_export_dir` 的默认环境变量名一致；`SCRAPY_DELIVERY_EXPORT_DIR` 只是宿主机侧插值来源，容器内不得改名。`.env.example` 也使用 `DELIVERY_EXPORT_DIR`。

不新建 volume。现有 `scrapy_export_data` 挂到 `/app/exports`；交付目录位于同一持久卷。

- [ ] **Step 4: 写运维手册**

```markdown
# 交付发布与篡改处置

## 前置

- schema head 必须是 `202610220066`。
- 报告产物必须已由 C9 发布（`report_artifacts.status = 'published'`），并已有 C9 的 `report_review_approved` 事件。
- 数据集版本必须是同一项目的 `saved` 版本。

## 发布

```bash
curl -sS -X POST "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/publish" \
  -H "Cookie: access_token=$TOKEN" \
  -H "Idempotency-Key: publish-$ARTIFACT_ID-$VERSION" \
  -H "Content-Type: application/json" \
  -d "{\"dataset_version_id\":\"$DATASET_VERSION_ID\"}"
```

## 下载

```bash
curl -sS -D headers.txt \
  "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery" \
  -H "Cookie: access_token=$TOKEN" \
  -o delivery.zip
```

## Quick 2 小时方向稿

只对 `package_type=quick` 的任务：

```bash
curl -sS -X POST "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/quick-draft" \
  -H "Cookie: access_token=$TOKEN" \
  -H "Idempotency-Key: quick-$ARTIFACT_ID" \
  -H "Content-Type: application/json" \
  -d "{\"dataset_version_id\":\"$DATASET_VERSION_ID\"}"
```

Quick 稿不审核、不启动验收、不生成 Standard 四态、不得出现 `confirmed`；同一任务内可用
`GET /api/tasks/{task_id}/delivery/quick-draft` 读取。24 小时正式版仍走 `POST /delivery/publish`，
必须已有 `report_review_approved`。

## 验收事件

```bash
# 读取当前验收状态与全部追加事件
curl -sS "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/acceptance" \
  -H "Cookie: access_token=$TOKEN"

# 验收通过（同 key 同 payload 返回 200 replay；同 key 不同 payload 返回 409 idempotency_conflict）
curl -sS -X POST "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/acceptance/accept" \
  -H "Cookie: access_token=$TOKEN" \
  -H "Idempotency-Key: accept-$ARTIFACT_ID" \
  -H "Content-Type: application/json" \
  -d "{\"note\":\"accepted\"}"

# 提出异议：references 至少 1 项，path 必须命中 manifest 文件
curl -sS -X POST "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/acceptance/dispute" \
  -H "Cookie: access_token=$TOKEN" \
  -H "Idempotency-Key: dispute-$ARTIFACT_ID-1" \
  -H "Content-Type: application/json" \
  -d "{\"references\":[{\"path\":\"report.zh.html\",\"description\":\"第 2 页指标口径\"}]}"

# 第 5 个工作日 23:59:59 UTC 之后视为验收
curl -sS -X POST "https://scrapy.luteos.com/api/reports/$ARTIFACT_ID/delivery/acceptance/deemed-accepted" \
  -H "Cookie: access_token=$TOKEN" \
  -H "Idempotency-Key: deemed-$ARTIFACT_ID"
```

验收事件只追加，不修改 manifest、bundle 或 `acceptance_snapshot_json`。
验收幂等键哈希固定为 `sha256("delivery-acceptance.v1:{idempotency_key}")`，事件 `metadata_json.idempotency_key_hash` 保存该值；payload 摘要固定覆盖 `event_type`、`artifact_id`、`references` 与可选 `note`（为空时省略）。原始 `Idempotency-Key` 不写入事件、日志或响应。
Quick 稿调用验收端点返回 409 `acceptance_not_applicable`。

## 校验

```bash
unzip -q delivery.zip -d delivery
cd delivery
sha256sum -c <(cat delivery_manifest.sha256)
python - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("delivery_manifest.json").read_text())
for item in manifest["files"]:
    print(item["sha256"], item["path"])
PY
```

## PII 命中

发布返回 409 `delivery_pii_detected` 时：

1. 不重试发布，不手工删除文件后继续。
2. 从 `report_audit_events` 查 `gate_evaluated` 或 `delivery_pii_detected`，记录 `kind` 与 `field_path`；审计不含原始 PII。
3. 按 C11 `export_policy` 修正来源数据或遮蔽策略，重新生成版本。
4. 不得在 C10 内新增第二套 PII 正则、例外表或 `PiiHit` 类型；只消费 C11 的 `scan_export_policy` / `scan_export_value`。

## 篡改

`GET /delivery` 返回 409 `delivery_integrity_error` 时：

1. 不重试下载，不手工改文件。
2. 从 `report_audit_events` 查 `delivery_tamper_detected`，记录 `mismatches`。
3. 隔离交付目录，保留现场。
4. 重新生成新的 `report_artifact` 版本，重新审核、重新发布；不得覆盖旧 manifest。
```

- [ ] **Step 5: 运行配置测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q tests/unit/test_delivery_config.py -v
```

Expected: `2 passed`。

- [ ] **Step 6: 全量交付测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q \
  tests/unit/test_c10_contract_registration.py \
  tests/unit/test_delivery_canonical_profile.py \
  tests/unit/test_delivery_projection.py \
  tests/unit/test_delivery_renderers.py \
  tests/unit/test_delivery_manifest.py \
  tests/unit/test_delivery_review.py \
  tests/unit/test_delivery_gates.py \
  tests/unit/test_delivery_store.py \
  tests/unit/test_delivery_migration.py \
  tests/postgres/test_delivery_migration.py \
  tests/unit/test_delivery_service.py \
  tests/unit/test_delivery_acceptance.py \
  tests/unit/test_delivery_quick.py \
  tests/unit/test_delivery_pii.py \
  tests/unit/test_delivery_routes.py \
  tests/unit/test_delivery_config.py -v
```

Expected: 全部 `passed`，0 failed。

- [ ] **Step 7: 运行既有报告/Claim 回归**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run pytest -q \
  tests/unit/test_report_artifacts.py \
  tests/unit/test_report_contract.py \
  tests/unit/test_report_builder.py \
  tests/unit/test_claims.py \
  tests/unit/test_demo_data.py \
  tests/unit/test_public_content_retention.py \
  tests/unit/test_e2e_cleanup.py \
  tests/unit/test_scheduler.py
```

Expected: 全部通过。基线命令 `uv run pytest -q tests/unit/test_report_artifacts.py tests/unit/test_report_contract.py tests/unit/test_report_builder.py` 在 B5 上是 `123 passed in 1.52s`；C10 后新增字段不得改变该结果。

- [ ] **Step 8: 检查 Alembic 单头**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run alembic heads
```

Expected: `202610220066 (head)`，且只有一个 head。

- [ ] **Step 9: 静态检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run ruff check \
  src/data_intelligence_hub/services/delivery \
  src/data_intelligence_hub/repositories/delivery.py \
  src/data_intelligence_hub/schemas/delivery.py \
  src/data_intelligence_hub/api/routes/delivery.py \
  src/data_intelligence_hub/models/report_artifact.py \
  alembic/versions/202610220066_delivery_manifest_publish.py \
  tests/unit/test_delivery_*.py \
  tests/postgres/test_delivery_migration.py \
  tests/unit/test_c10_contract_registration.py
cd /Users/lute/Project/data_scrapy-gov-c10/apps/api && uv run mypy \
  src/data_intelligence_hub/services/delivery \
  src/data_intelligence_hub/repositories/delivery.py \
  src/data_intelligence_hub/schemas/delivery.py \
  src/data_intelligence_hub/api/routes/delivery.py
```

Expected: `All checks passed!` 与 `Success: no issues found`。

- [ ] **Step 10: GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `partial: false`、`truncated: false`。检查输出中 `canonical_json_bytes` 未被改动；`ReportAuditEvent` 未改动；`ReportArtifact` 的变更是计划内变更。任何 HIGH/CRITICAL 未解释项必须停下。

- [ ] **Step 11: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c10
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/.env.example \
  apps/api/tests/unit/test_delivery_config.py \
  docs/operations/delivery-publish.md
git commit -m "chore(delivery): add export directory config and runbook"
```

---

## 统一发布门禁（PG0 发布批次）

本切片不直接部署。生产 A/B 由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收；两套环境共用 `configs/deploy/scrapy/docker-compose.yml`。C10 只交付可合并的代码、迁移与验收证据，不执行生产发布命令，也不修改生产 compose。

发布顺序固定，任一步失败即停止同批次：

1. **先备份**：备份目标数据库与 `DELIVERY_EXPORT_DIR` 所在持久卷，记录备份路径与 SHA-256。
2. **A 环境 canary**：先发布 A，运行冒烟与交付验收；失败时回滚 A，B 不发布。
3. **B 环境门禁**：B 只在目标授权、备份校验和迁移门禁全部通过后发布。目标授权指用户已确认 B 的发布目标与发布窗口；迁移门禁指 `alembic heads` 只有 `202610220066 (head)`、迁移 065→066→065 在一次性库演练通过、备份可恢复。
4. **失败记 `BLOCKED`**：记录失败步骤、证据路径与决策人；不得跳过门禁继续发布。

**PG0 发布批次交接**：`configs/deploy/scrapy/docker-compose.yml` 由 PG0 发布批次修改，加入 `DELIVERY_EXPORT_DIR: ${SCRAPY_DELIVERY_EXPORT_DIR:-/app/exports/deliveries}`。C10 不提交该文件；`docs/operations/delivery-publish.md` 与 `apps/api/.env.example` 是交接输入。部署证据由 PG0 发布批次收集；C14 收集只读验收证据。

---

## C14 浏览器交接

C10 不修改前端页面。C14 在以下事实成立后做浏览器/HTTP 验收：

- `POST /api/reports/{artifact_id}/delivery/publish` 要求 `report_artifacts.status = 'published'`，未发布时返回 409。
- `POST /api/reports/{artifact_id}/delivery/quick-draft` 只接受 `package_type=quick`；Standard 返回 422 `quick_draft_not_allowed`。
- `GET /api/reports/{artifact_id}/delivery` 返回 ZIP，包含 `delivery_manifest.json` 与 `report_contract.json`。
- `GET /api/reports/{artifact_id}/delivery/manifest` 返回 manifest 哈希与文件列表。
- 篡改任一交付文件后，`GET /delivery` 返回 409 `delivery_integrity_error`。
- `GET /api/reports/{artifact_id}/delivery/acceptance` 返回追加式验收事件；accept/dispute/deemed 都要求 `Idempotency-Key`。
- 含 PII 的交付返回 409 `delivery_pii_detected`，且 `report_audit_events` 有 `gate_evaluated` 阻断记录。

浏览器验收步骤：

1. 启动 API 与控制台，登录测试工作区。
2. 用 C9 的发布端点把一份报告产物置为 `status = 'published'`。
3. 在浏览器网络面板调用 `POST /api/reports/<artifact_id>/delivery/publish`，带 `Idempotency-Key`，断言 201 与 `delivery_status = delivered`。
4. 调用 `GET /api/reports/<artifact_id>/delivery/manifest`，断言 `manifest_sha256` 为 64 位十六进制。
5. 下载 `GET /api/reports/<artifact_id>/delivery`，解压后确认 10 个交付文件与 sidecar。
6. 在测试目录篡改 `report.zh.html`，再次下载，断言 409 与 `delivery_integrity_error`。
7. 断言未发布的 C9 产物调用 delivery publish 返回 409，且不会写 `delivered_*` 字段。
8. 用 Quick 任务调用 `POST /delivery/quick-draft`，断言 `delivery_class=quick_draft`、`acceptance_deadline=null`、ZIP 含 `quick_draft_notice.json` 且不含 `acceptance_snapshot.json`。
9. 对正式交付调用 `accept`，再以同 key 同 payload 重放，断言 200 replay；以同 key 不同 note 重放，断言 409 `idempotency_conflict`。
10. 截图与网络记录归档到 C14；C10 不新增前端路由。

---

## Self-Review

**1. Spec coverage**

| 设计要求 | 任务 |
|---|---|
| 正式交付文件清单 | Task 9 `_content_files`，10 个角色 |
| 逐文件 SHA-256 | Task 6 `_manifest_entries`，Task 7 `verify_bundle` |
| manifest sidecar | Task 6 `build_manifest`/`verify_manifest_file`，Task 7 存储与 ZIP |
| 公开合同投影 | Task 2 `project_public_contract` |
| G-Claim | Task 5 `evaluate_g_claim` 消费 C7 `load_publishable_claim_rows()`；pending/stale 阻断 |
| G-Publish | Task 5 `evaluate_g_publish`，Task 9 发布前阻断；正式要求签字，Quick 跳过 |
| 审核签字 | Task 5 `load_latest_review_signoff`/`validate_review_signoff`；C9 写入 `report_review_approved` |
| 验收快照追加事件 | Task 4 `render_acceptance_snapshot`，Task 9 `acceptance_snapshot_appended` |
| 追加式验收事件 | Task 9 `record_acceptance`/`record_deemed_acceptance`，Task 10 四个验收端点 |
| Quick 2 小时方向稿 | Task 9 `publish_quick_draft`，Task 10 三个 Quick 端点；无验收、无四态/confirmed、无重复计费 |
| PII 扫描 | Task 9 `scan_delivery_inputs` 复用 C11 `scan_export_value`/`scan_export_policy` 与 `PiiHit`；命中阻断并审计 |
| 篡改下载失败 | Task 7 `verify_bundle`，Task 9 `open_delivery_zip`，Task 10 409 |
| 一个迁移 066 | Task 8；Task 1 合同预检 |
| 公开分享延期 | 0.2 决策；Task 1 断言 `report_shares` 与“延期” |
| 隐私保留与删除 | 0.6；归 C11/C12，C10 只调用 C11 PII 扫描，不实现规则 |
| 不做 MCP | 0.6；文件结构不含 `mcp_runtime` |
| B5 报告/Claim 基线 | 0.1；复用 `report_artifacts`、`claims`、`claim_evidence` |
| C1 1.1 29 键夹具 | Task 1 断言；Task 2 `tests/fixtures/report_contract_v1_1.py` 唯一构造器 |
| canonical profile | 0.3；Task 1 字节级固定 |
| C7/C8/C9/C11 前置 | 0.1/0.4.1；Task 1 入口断言 |
| 契约优先 | 0.4；C10 只登记 delivery_* 字段，C9 的 published 字段与审核事件不重复 |
| GitNexus 强制 | 0.5；Task 11 `detect-changes` |

**2. Placeholder scan**

计划中没有空占位符、延迟实现说明或“类似上一任务”的省略。每个代码步骤都有实际函数体或实际断言；每个测试步骤都有命令与预期结果。

**3. Type consistency**

- `DeliveryFile.role` 是 `DeliveryFileRole`；manifest 写 `role.value`。
- `DeliveryManifest.sha256`/`sidecar_sha256` 是 64 位字符串；`ReportArtifact.manifest_sha256`/`manifest_sidecar_sha256` 同名。
- `GateDecision.gate_id` 只允许 `G-Claim`/`G-Publish`；`status` 只允许 `pass`/`fail`/`blocked`。
- `ClaimSnapshot.digest` 由 C9 的 `claim_review_digest()` 计算，C10 只调用；payload 与 `dih-canonical-json-v1` 只有一套。
- `PublishResult.replay` 在路由中映射为 200；首次发布为 201。
- `PiiHit` 的类型与字段由 C11 `services.export_policy` 定义（`kind`/`field_path`/`start`/`end`）；C10 的 `delivery/types.py` 只重导出，`delivery/pii.py` 与 `DeliveryPiiError` 只消费它。
- `ACCEPTANCE_SNAPSHOT_PATH` 与 `DeliveryFileRole.ACCEPTANCE_SNAPSHOT` 的路径一致，manifest 与 store 使用同一常量。
- 验收快照不含 `manifest_sha256`；manifest 包含快照哈希；sidecar 包含 manifest 哈希；审计事件包含三者。DAG 无环。

**4. 未覆盖风险**

- C9 的 `report_review_approved` metadata 必须与第 0.4 节逐字一致；若 C9 用不同键，Task 5 会失败，必须回到 C9 统一，不得在 C10 加兼容分支。
- C1 的 1.1 合同 `decision` 组没有 `answer_en`；`render_executive_summary_en` 必须回退到 `answer`。若 C9 需要英文 answer，必须先改 C1 合同，不得在 C10 私加键。
- C11 未提供 `PiiHit` / `EXPORT_POLICY_VERSION` / `scan_export_policy()` / `scan_export_value()` 时 C10 必须停止；`delivery/types.py` 只重导出 C11 `PiiHit`，不得在 C10 复制 `CONTACT_PATTERN`、定义 `PiiHit` 类或另建 PII 规则。
- C7 `load_publishable_claim_rows()` 只返回 `review_status='approved'` 且 `reviewed_content_version == content_version` 的行；C10 必须同时拒绝合同里未进入 bundle 的 pending/stale Claim，不能只看 bundle 为空就放行。
- Quick 2 小时稿的 `package_type` 只来自 C4 `workbench_tasks`；C10 不新增包型副本。Quick 合同若含 `conclusion_standard` 或 `confirmed`，必须返回 422 `quick_draft_claim_invalid`。
- 验收幂等键按 `artifact_id` 作用域；同一产物同 key 同 payload 才 replay。跨产物复用同一 key 不是本切片的承诺，不得把它写成全局幂等。
- Quick 稿与正式交付共用 `publish_idempotency_key_hash` 唯一约束；同一 key 指向不同产物必须 409 `idempotency_conflict`。
