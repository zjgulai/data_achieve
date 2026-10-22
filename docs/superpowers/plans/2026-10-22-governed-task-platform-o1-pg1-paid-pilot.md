---
name: governed-task-platform-o1-pg1-paid-pilot
description: PG0 通过后的 90 天受治理任务包商业试点运营计划。覆盖 3–5 家实际付费、合同回款、交付验收、复购刷新、毛利、质量、系统与合规硬门禁、支持、周报、30/60/90 复盘、一次 30 天延期和 PG1 Go/Conditional/No-Go。不含工程任务。
---

# 受治理任务平台 O1 / PG1 付费试点运营计划（Implementation Plan）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 PG0 通过后的 90 个日历日内，完成 3–5 家实际付费伙伴的受治理任务包试点，收齐 PG1 六类硬门禁证据，并产出 Go / Conditional Go / No-Go 书面决议。

**Architecture:** 运营控制台是受版本控制的台账与证据索引目录 `docs/ops/pg1-pilot/`。台账用 CSV，证据用受限库加 SHA-256 索引。所有对外数字只从台账取数，周报、复盘和 D90 决议共用同一套数据。平台代码切片 C0–C14 和 PG0 外部取证 O0 不在本计划内；本计划只消费 PG0 的验收结果。

**Tech Stack:** Markdown、CSV、Git、macOS `shasum`、`python3 -I`（只读校验）、生产控制台只读导出、受限证据库。

**Design input:** [`2026-10-21-tikhub-governed-task-platform-design.md`](../specs/2026-10-21-tikhub-governed-task-platform-design.md) v1.0，状态“设计已批准，待实施规划”。

**Status:** O1 未启动，受 PG0 门禁阻断。没有其他内部阻塞；PG0 结论不是 `pass` 或六方不是 `approve` 时，Task 1 不得开始。PG0 `pass` 后按 Task 1 启动。

## Global Constraints

以下约束来自设计 §8 和 §10。每个任务都隐含包含本节。

- 90 天是商业试点窗口，不是研发排期。P0/P1/P2 是产品阶段，不是契约实施阶段 P0–P8。
- 本计划不产生工程任务。C0–C14 是 PG0 的代码实施切片，最终结构见 `docs/superpowers/plans/2026-10-22-governed-task-platform-master-plan.md` §1；本计划不改切片名称、不拆并、不新增。
- PG0 外部取证是 O0。本计划只读消费 O0 的证据，不重新定义 O0 的范围。
- 文中优先写 PG0、PG1。禁止用“P1 试点”指代商业试点，禁止用“P0 门禁”指代 PG0。
- O1 只在 PG0 结论 `pass` 且六方 `approve` 后启动。Task 1 是硬门禁；未通过时不得筛选伙伴、签合同、收款、开通工作区或建单。
- 3–5 家实际签约并付款。PG0 的书面承诺不计入实际付费。
- LOI、口头意向、未付款合同、免费 Quick 线索不计入实际付费。
- Agency 的终端品牌不单独计入设计伙伴数量。
- 不新增模板、品类或正式市场。首期只做 TikTok Shop 母婴新品进入模板。
- 不提供免费定制；不卖裸 API；不按调用次数计费；不接受客户 Cookie；不把产品缺口包装成专业服务。
- Standard 月度刷新可作付费扩展。周度刷新只作受限验证，不作普遍承诺。
- 回款率必须 100%。企业采购准入必须覆盖全部实际付费伙伴。
- 所有仍在售市场与包型的贡献毛利不能为负。经济硬门禁只使用设计 §8.4 的“所有仍在售市场与包型贡献毛利不为负”；不另设毛利率百分比门槛。
- 正式任务完成率 ≥90%；正式交付后 5 个工作日内完成验收或进入明确异议流程。
- 一次验收通过率目标 ≥70%；支持首次响应达标率目标 ≥90%；免费补证或重跑率目标 ≤20%。
- 质量硬门禁：每个约定市场有质量状态；不合格市场正确输出证据不足；正式 Claim 追溯率 100%；Claim 等级不超过证据上限 100%；关键 Claim 独立来源判定覆盖率和正确率 100%；刷新可比性状态完整 100%；重大口径争议 0。
- 系统硬门禁：跨工作区泄露 0；客户执行回退演示工作区 0；账本不平 0；重复结算 0；幂等重复计费 0；超预算继续执行 0；关键操作缺少审计 0。
- 合规硬门禁：DPA 和子处理者覆盖 100%；数据源书面权利覆盖 100%；客户链 Cookie 暴露 0；PII 违规发布 0；LLM 处理方式披露并客户接受 100%。
- 证据不足最多延长一次，最长 30 天。延长必须写明缺少的证据、负责人和复核日期。延长后仍无证据，结论为 No-Go。
- Conditional Go 不能豁免任何硬门禁。
- P2 不在批准范围。PG1 通过只允许提出 P2 方案，不自动进入 P2。
- 报告用中文主报告和英文执行摘要。金额记录原币和 USD，汇率记录日期和来源。
- 所有硬门禁证据必须是书面文件。口头说明、聊天截图、未签字文档不算证据。
- 模板中的空白字段在提交前必须写成实际值或 `not_recorded`、`not_assigned`、`not_signed` 等明确生命周期值；不得保留空占位。
- 运行成本账本和审计只追加，不修改历史行。业务台账可以更新状态字段，但不得删除行或改写已确认事实；每次状态变更记录时间和操作人。证据文件不进入 Git 仓库，仓库只存索引和 SHA-256。
- 每次提交前运行 `git diff --check`，确认无空白错误。
- 每次提交前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`；`partial` 与 `truncated` 必须为 `false`。文档与台账变更不豁免该检查。每个提交代码块都重复该命令。命令输出出现 `partial: true` 或 `truncated: true` 时，立即停止并重跑；不得执行后续 `git commit`。

## 0. 术语与阶段边界

| 名称 | 含义 | 本计划用法 | 禁止写法 |
|---|---|---|---|
| PG0 | 试点准入门槛 | O1 的唯一启动条件 | “P0 门禁” |
| PG1 | 商业 Go/No-Go 门槛 | O1 的退出判定 | “P1 门禁” |
| P0 / P1 / P2 | 产品阶段 | 只在阶段目标说明中使用 | “P1 试点”指商业试点 |
| P0–P8 | 契约实施阶段 | 本计划不引用、不重排 | 把 P3 写成市场或客户阶段 |
| C0–C14 | 代码实施切片 | PG0 的输入，只读引用 | 新增 C15、拆并切片 |
| O0 | PG0 外部取证 | 只读消费证据 | 把 O0 承诺算实际付费 |
| O1 | PG1 实际试点 | 本计划 | “P1 运营” |

本计划是运营计划。每个任务的“测试”是台账校验和证据核验；“实现”是运营动作；“提交”是提交脱敏台账和报告。计划不修改产品代码。

## 1. 运营口径

### 1.1 目录

```text
docs/ops/pg1-pilot/
├── README.md
├── charter.md
├── D0.txt
├── ledgers/
│   ├── partner_ledger.csv
│   ├── contract_ledger.csv
│   ├── payment_ledger.csv
│   ├── provisioning_ledger.csv
│   ├── order_ledger.csv
│   ├── delivery_ledger.csv
│   ├── refresh_ledger.csv
│   ├── margin_ledger.csv
│   ├── quality_ledger.csv
│   ├── system_compliance_ledger.csv
│   ├── support_ledger.csv
│   ├── incident_ledger.csv
│   ├── extension_ledger.csv
│   ├── evidence_index.csv
│   └── pg1_gate_register.csv
├── imports/
├── weekly/
├── reviews/
└── decisions/
```

证据库在仓库外：

```text
$PG1_EVIDENCE_ROOT/
├── PG0/
├── P-01/
├── P-02/
├── P-03/
├── P-04/
└── P-05/
```

默认值：`PG1_EVIDENCE_ROOT="${PG1_EVIDENCE_ROOT:-$HOME/DIH-PG1-EVIDENCE}"`。

### 1.2 ID 规则

```text
P-01 … P-05          伙伴
CT-01 …              合同
PAY-01 …             回款
PRV-01 …             开通
ORD-01 …             订单
DLV-01 …             交付
RF-01 …              刷新
M-01 …               毛利
Q-01 …               质量
SC-YYYY-Www-NN       系统或合规周检
TKT-01 …             支持工单
INC-01 …             事件
EXT-01 …             延期
EV-0001 …            证据
PG1-COM-01 …         硬门禁
P-00                 保留示例，永不作为真实伙伴
```

### 1.3 运营定义

| 术语 | 定义 | 计算或证据 |
|---|---|---|
| 实际付费 | 已签合同 + 款项到账 + 已创建首单 | 合同、银行回单、订单 |
| 活跃 | 最近 30 个日历日内有已验收交付，或有未关闭的付费订单 | 交付台账、订单台账 |
| 正式任务完成 | 正式版报告已交付，且客户验收或视为验收 | 交付台账 |
| 一次验收通过 | 无异议通过或视为验收，且纠正轮次为 0 | 交付台账 |
| 免费补证或重跑 | 平台可控缺陷导致的免费纠正或重跑 | 交付台账 |
| Claim 追溯 | 正式 Claim 绑定可解析证据 | 报告合同、质量台账 |
| 重大口径争议 | 客户质疑指标或证据等级定义，5 个工作日内未按合同解决 | 支持台账、质量台账 |
| 报价成本偏差 | `(实际成本 - 报价成本) / 报价成本` | 毛利台账 |
| 价格实现率 | `成交价 / 价格簿标价` | 毛利台账 |

贡献毛利：

```text
net_revenue_usd = 已开票 USD - 退款 - 抵扣
contribution_margin_usd = net_revenue_usd
                          - provider_settle_usd
                          - review_labor_usd
                          - payment_fee_usd
```

- `provider_settle_usd`：`run_ledger_entries` 中 `entry_kind IN ('settle','release')` 的 `amount_usd` 合计。
- `review_labor_usd`：审核工时 × 财务在 D0 冻结的完全负担小时成本。
- `payment_fee_usd`：银行或支付渠道实际费用。
- 毛利按 `market × package_type` 计算。
- D90 时所有 `still_sold=yes` 的组合必须 ≥ 0。

### 1.4 证据规则

1. 每条业务台账行必须有 `evidence_id`。
2. `evidence_index.csv` 的 `storage_locator` 是证据库内相对路径。
3. `sha256` 是小写十六进制 SHA-256。
4. 证据库权限只授予试点角色。客户 PII 不进入仓库。
5. 每个伙伴目录有 `SHA256SUMS`。校验命令：`shasum -a 256 -c SHA256SUMS`。
6. 证据缺失时，门禁写 `insufficient_evidence`。不得写 `pass`。
7. 测试或演练证据必须使用合成数据，并在 `notes` 标记 `synthetic=yes`。合成数据不计入生产指标。

### 1.5 台账清单

| 文件 | 用途 | 主要列 | 生产任务 |
|---|---|---|---|
| `partner_ledger.csv` | 伙伴、承诺、付费、活跃 | `partner_id`、`commitment_type`、`actual_paid`、`active_30d` | Task 2 |
| `contract_ledger.csv` | 合同、SOW、DPA 版本 | `contract_id`、`status`、`dpa_version` | Task 3 |
| `payment_ledger.csv` | 开票、到账、账龄 | `payment_id`、`collection_status`、`amount_paid_usd` | Task 4 |
| `provisioning_ledger.csv` | 工作区、项目、密钥、边界 | `workspace_id`、`key_prefix`、`boundary_test_result` | Task 5 |
| `order_ledger.csv` | 订单、报价、预算、幂等 | `order_id`、`quote_id`、`idempotency_key` | Task 6 |
| `delivery_ledger.csv` | 交付、验收、返工 | `delivery_id`、`manifest_id`、`acceptance_result` | Task 7 |
| `refresh_ledger.csv` | 复购、刷新、可比性 | `refresh_id`、`comparability_status` | Task 8 |
| `margin_ledger.csv` | 收入、成本、毛利、价格实现 | `margin_id`、`contribution_margin_usd` | Task 9 |
| `quality_ledger.csv` | 质量状态、Claim、争议 | `quality_id`、`market_quality_status` | Task 10 |
| `system_compliance_ledger.csv` | 系统与合规硬门禁周检 | `check_id`、`check_type`、`result` | Task 11 |
| `support_ledger.csv` | 工单、响应、免费返工 | `ticket_id`、`first_response_hours` | Task 12 |
| `incident_ledger.csv` | 停止、事件、整改 | `incident_id`、`category`、`closed_at` | Task 11、Task 12 |
| `extension_ledger.csv` | 一次 30 天延期 | `extension_id`、`review_date` | Task 16 |
| `evidence_index.csv` | 证据索引与哈希 | `evidence_id`、`storage_locator`、`sha256` | Task 1 |
| `pg1_gate_register.csv` | 28 条 PG1 硬门禁 | `gate_id`、`verdict`、`evidence_ids` | Task 16 |

## File Structure

### 创建

- `docs/ops/pg1-pilot/README.md`：控制台导航、阶段、D0/D30/D60/D90 日期。
- `docs/ops/pg1-pilot/charter.md`：章程、口径、阈值、角色、决策规则。
- `docs/ops/pg1-pilot/D0.txt`：D0 日期，ISO 格式。
- `docs/ops/pg1-pilot/ledgers/*.csv`：15 张台账，表头见 Task 1。
- `docs/ops/pg1-pilot/weekly/YYYY-Www.md`：13 份周报。
- `docs/ops/pg1-pilot/reviews/D30.md`、`D60.md`、`D90.md`：复盘记录。
- `docs/ops/pg1-pilot/decisions/PG1-decision.md`：最终决议。
- `docs/ops/pg1-pilot/decisions/extension-01.md`：延期决议，仅在需要时创建。
- `docs/ops/pg1-pilot/decisions/closeout.md`：收尾记录。
- `docs/ops/pg1-pilot/imports/`：只放脱敏摘要和公开报告合同。原始导出放 `$PG1_EVIDENCE_ROOT/PG1/imports/`，不提交。

### 修改

- `docs/ops/pg1-pilot/ledgers/*.csv`：每周追加行。
- `docs/ops/pg1-pilot/ledgers/evidence_index.csv`：每份证据追加一行。

### 不修改

- 产品代码、数据库迁移、`configs/`、`apps/`。
- PG0 和 O0 目录。
- 任何客户数据文件。

---

### Task 1: 建立控制台并验证 PG0 准入

**Files:**
- Create: `docs/ops/pg1-pilot/charter.md`
- Create: `docs/ops/pg1-pilot/README.md`
- Create: `docs/ops/pg1-pilot/D0.txt`
- Create: `docs/ops/pg1-pilot/ledgers/partner_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/contract_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/payment_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/provisioning_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/order_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/delivery_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/refresh_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/margin_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/quality_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/support_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/incident_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/extension_ledger.csv`
- Create: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `docs/ops/pg1-pilot/ledgers/pg1_gate_register.csv`
- Create: `docs/ops/pg1-pilot/imports/`、`weekly/`、`reviews/`、`decisions/`
- Create: `$PG1_EVIDENCE_ROOT/PG0/`

**Interfaces:**
- Consumes: `docs/evidence/o0-pg0/pg0-review/decision.md`，`Decision` 必须是 `pass`。
- Consumes: `docs/evidence/o0-pg0/pg0-review/signoff.csv`，六方 `approve`。
- Consumes: `docs/evidence/o0-pg0/pg0-review/gate-matrix.csv`，11 项 PG0 门禁全部 `pass`。
- Consumes: `docs/evidence/o0-pg0/register/evidence-register.csv`，O0 证据登记册。
- Consumes: `docs/superpowers/plans/2026-10-22-governed-task-platform-master-plan.md` §9.3 的 PG1 启动条件。
- Consumes: `GOVERNED_TASK_PLATFORM_ENABLED=true` 的发布门禁记录，以及 `WORKBENCH_TASKS_ENABLED=true`、`SCRAPY_MCP_CUSTOMER_ENABLED=true` 的运行时开关发布记录，且只对试点工作区生效。
- Produces: `D0.txt`、15 张台账表头、`charter.md`、`EV-0001` 到 `EV-0003` PG0 证据。

以下命令都在仓库根目录执行。

- [ ] **Step 1: 确认 PG0 决议**

```bash
test -f docs/evidence/o0-pg0/pg0-review/decision.md
test -f docs/evidence/o0-pg0/pg0-review/signoff.csv
test -f docs/evidence/o0-pg0/pg0-review/gate-matrix.csv
grep -qiE '\| Decision \| pass \|' docs/evidence/o0-pg0/pg0-review/decision.md
test "$(grep -c ',approve,' docs/evidence/o0-pg0/pg0-review/signoff.csv)" -eq 6
test "$(grep -cE '^(Product|Engineering|Data Quality|Legal|Finance|Security),' docs/evidence/o0-pg0/pg0-review/signoff.csv)" -eq 6
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/evidence/o0-pg0/pg0-review/gate-matrix.csv", encoding="utf-8")))
assert len(rows) == 11, len(rows)
bad = [r["gate_id"] for r in rows if (r["result"] or "").strip().lower() != "pass"]
assert not bad, bad
print("PG0 gates PASS", len(rows))
'
```

预期：全部命令退出码为 0，输出 `PG0 gates PASS 11`。任一失败就停止。不得启动 O1。
PG0 没有 Conditional Pass。`Decision` 不是 `pass` 就停止。

11 项 PG0 门禁：

| gate_id | PG0 要求 |
|---|---|
| PG0-01 | 合成数据黄金路径端到端通过 |
| PG0-02 | 内部 Quick 端到端验收 |
| PG0-03 | 内部 Standard 端到端验收 |
| PG0-04 | 工作区、项目、密钥和客户工具边界生效 |
| PG0-05 | 价格簿、预算和账本对账 |
| PG0-06 | 逐市场质量、证据、Claim、报告和交付闭环 |
| PG0-07 | 伪名化、导出遮蔽、保留、删除和审计生效 |
| PG0-08 | TikHub 及实际来源书面商业依据 |
| PG0-09 | 至少 3 份可执行书面付费承诺 |
| PG0-10 | 目录、MCP 工具和生产构建基线冻结 |
| PG0-11 | 没有未处置的严重风险 |

同时确认 `GOVERNED_TASK_PLATFORM_ENABLED=true` 的发布门禁记录，以及 `WORKBENCH_TASKS_ENABLED=true`、`SCRAPY_MCP_CUSTOMER_ENABLED=true` 的运行时开关，且只对试点工作区生效。`GOVERNED_TASK_PLATFORM_ENABLED` 是部署与验收记录，不是后端配置项。把发布记录或配置只读导出登记到 `evidence_index.csv`，`artifact_type=feature_flag_release`。

同时完成一次停止与回退桌面演练，覆盖设计 §8.6 的六类停止：合规、安全、财务、质量、上游、技术回退。记录触发条件、立即动作、负责人、证据保全、客户通知和恢复门禁。把记录存入 `$PG1_EVIDENCE_ROOT/PG0/stop_rollback_rehearsal.md`，并登记到 `evidence_index.csv`。

- [ ] **Step 2: 创建目录**

```bash
export PG1_EVIDENCE_ROOT="${PG1_EVIDENCE_ROOT:-$HOME/DIH-PG1-EVIDENCE}"
mkdir -p docs/ops/pg1-pilot/{ledgers,imports,weekly,reviews,decisions}
mkdir -p "$PG1_EVIDENCE_ROOT/PG0"
mkdir -p "$PG1_EVIDENCE_ROOT/PG1/imports"
```

预期：目录存在。

- [ ] **Step 3: 写 D0**

```bash
python3 -I -c '
from datetime import date, timedelta
d = date.today()
if d.weekday() >= 5:
    d += timedelta(days=(7 - d.weekday()) % 7)
print(d.isoformat())
' > docs/ops/pg1-pilot/D0.txt
cat docs/ops/pg1-pilot/D0.txt
```

D0 必须是工作日。脚本在当天不是工作日时写到下一个工作日。
预期：输出 ISO 日期，例如 `2026-11-02`。

- [ ] **Step 4: 创建 15 张台账表头**

```bash
printf '%s\n' 'partner_id,partner_code,segment,primary_market,decision_maker_role,procurement_path,stage,commitment_type,commitment_date,contract_id,actual_paid,first_payment_date,active_30d,enterprise_clearance,disqualified_reason,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/partner_ledger.csv
printf '%s\n' 'contract_id,partner_id,sow_version,template_version,package_scope,markets,order_count,contract_value_usd,currency,fx_rate,fx_date,fx_source,signed_date,effective_date,payment_terms,acceptance_terms,refund_weight_version,dpa_version,subprocessor_version,llm_disclosure_version,status,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/contract_ledger.csv
printf '%s\n' 'payment_id,partner_id,contract_id,invoice_id,invoice_date,currency,amount_due_local,amount_paid_local,amount_due_usd,amount_paid_usd,fx_rate,fx_date,fx_source,paid_date,payment_method,bank_receipt_id,collection_status,days_late,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/payment_ledger.csv
printf '%s\n' 'provisioning_id,partner_id,contract_id,workspace_id,project_id,role_set,key_prefix,key_issued_at,key_revoked_at,boundary_test_result,audit_event_id,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/provisioning_ledger.csv
printf '%s\n' 'order_id,partner_id,contract_id,package_type,primary_market,compare_markets,template_version,decision_question,time_window_start,time_window_end,max_cost_usd,max_pages,max_records,idempotency_key,quote_id,quoted_price_usd,quote_valid_until,order_created_at,status,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/order_ledger.csv
printf '%s\n' 'delivery_id,partner_id,order_id,package_type,primary_market,compare_markets,template_version,started_at,quick_due_at,formal_due_at,quick_delivered_at,formal_delivered_at,delivery_status,acceptance_start,acceptance_end,acceptance_result,objection_items,correction_rounds,rework_type,rework_cost_usd,manifest_id,report_contract_id,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/delivery_ledger.csv
printf '%s\n' 'refresh_id,partner_id,source_delivery_id,refresh_type,scheduled_date,delivered_at,comparability_status,new_order_id,list_price_usd,collected_usd,status,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/refresh_ledger.csv
printf '%s\n' 'margin_id,order_id,partner_id,market,package_type,net_revenue_usd,provider_settle_usd,review_labor_usd,payment_fee_usd,contribution_margin_usd,quote_cost_usd,actual_cost_usd,cost_deviation_pct,list_price_usd,price_realized_usd,price_realization_pct,still_sold,close_month,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/margin_ledger.csv
printf '%s\n' 'quality_id,order_id,partner_id,market,package_type,core_domains_passed,product_n,review_n,creator_content_n,field_completeness_pct,duplicate_pct,source_url_coverage_pct,claim_evidence_binding_pct,independent_source_coverage_pct,independent_source_correct_pct,market_quality_status,claim_level_cap_ok,refresh_comparability_status,formal_claim_count,traced_claim_count,major_definition_dispute,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/quality_ledger.csv
printf '%s\n' 'check_id,week,check_type,metric,value,threshold,result,owner,run_at,evidence_id,incident_id,notes' > docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv
printf '%s\n' 'ticket_id,partner_id,opened_at,severity,subject_code,response_target_hours,first_response_at,first_response_hours,resolved_at,resolution_hours,free_rework,root_cause,escalation_owner,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/support_ledger.csv
printf '%s\n' 'incident_id,opened_at,category,severity,description,affected_scope,immediate_action,contained_at,root_cause,corrective_action,owner,closed_at,customer_notified,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/incident_ledger.csv
printf '%s\n' 'extension_id,partner_id,trigger_gate,missing_evidence,owner,requested_at,approved_at,review_date,extension_days,status,evidence_id,notes' > docs/ops/pg1-pilot/ledgers/extension_ledger.csv
printf '%s\n' 'evidence_id,partner_id,artifact_type,artifact_date,storage_locator,sha256,access_class,recorded_by,recorded_at,notes' > docs/ops/pg1-pilot/ledgers/evidence_index.csv
printf '%s\n' 'gate_id,category,gate_text,threshold,source_ledger,source_query,owner,verdict,evidence_ids,reviewed_at,notes' > docs/ops/pg1-pilot/ledgers/pg1_gate_register.csv
```

预期：15 个 CSV 文件，每个含表头。

- [ ] **Step 5: 写入章程**

将以下内容写入 `docs/ops/pg1-pilot/charter.md`：

````markdown
# O1 / PG1 付费试点章程

## 1. 目的与窗口

在 PG0 通过后，用 90 个日历日验证 3–5 家实际付费伙伴的付费、复购、质量和单位经济。
本试点不新增工程开发任务。平台能力以 PG0 验收版本为准。

- D0：PG0 决议 PASS 后第一个工作日。
- D30：D0 + 30 个日历日。
- D60：D0 + 60 个日历日。
- D90：D0 + 90 个日历日。
- 数据截止：每周四 23:59 Asia/Shanghai。
- 周报发布：每周五 17:00 Asia/Shanghai。
- 支持时段：工作日 09:00–18:00 Asia/Shanghai。

## 2. 命名边界

| 名称 | 含义 | 本计划写法 |
|---|---|---|
| PG0 | 试点准入 | PG0 |
| PG1 | 商业 Go/No-Go | PG1 |
| P0/P1/P2 | 产品阶段 | 只在阶段说明中使用 |
| P0–P8 | 契约实施阶段 | 不引用、不重排 |
| C0–C14 | 代码实施切片 | 只作为 PG0 输入 |
| O0 | PG0 外部取证 | 只读消费 |
| O1 | PG1 实际试点 | 本计划 |

不得用“P1 试点”指代商业试点。

## 3. 实际付费

实际付费 = 已签合同 + 款项到账 + 已创建首单。三项缺一不可。

以下不计入：

- PG0 书面承诺；
- LOI、口头意向、未付款合同；
- 免费 Quick 线索；
- Agency 的终端品牌；
- 同一伙伴的重复合同。

## 4. 活跃

活跃 = 最近 30 个日历日内有已验收交付，或有未关闭的付费订单。

## 5. 贡献毛利

```text
net_revenue_usd = 已开票 USD - 退款 - 抵扣
contribution_margin_usd = net_revenue_usd
                          - provider_settle_usd
                          - review_labor_usd
                          - payment_fee_usd
```

- `provider_settle_usd`：`run_ledger_entries` 中 `settle` 与 `release` 的 `amount_usd` 合计。
- `review_labor_usd`：审核工时 × 财务 D0 冻结的完全负担小时成本。
- `payment_fee_usd`：银行或支付渠道实际费用。
- 毛利按 `market × package_type` 计算。
- D90 时所有 `still_sold=yes` 的组合必须 ≥ 0。
- 不设毛利率百分比硬门禁；只检查贡献毛利是否为负。

## 6. 质量门槛

| 门槛 | Quick | Standard |
|---|---:|---:|
| 核心域 | 3/3 | 3/3 |
| 商品 | ≥20 | ≥100 |
| 评论 | ≥300 | ≥2,000 |
| 达人内容 | ≥50 | ≥200 |
| 字段完整率 | ≥80% | ≥80% |
| 重复率 | <2% | <2% |
| 来源 URL 覆盖率 | 100% | 100% |
| 关键 Claim 证据绑定率 | 100% | 100% |
| 关键判断独立来源 | ≥2 | ≥2 |
| 正式报告审核 | 100% | 100% |
| 报告合同和产物校验 | 100% | 100% |

## 7. 预警指标

| 指标 | D0 冻结阈值 | 数据源 | 复核人 |
|---|---|---|---|
| 报价成本偏差 | 单订单 ±20%；月绝对中位数 ≤10% | `margin_ledger` | 财务 |
| 价格实现率 | ≥85% | `margin_ledger` | 销售 |
| 一次验收通过率 | ≥70% | `delivery_ledger` | 交付 |
| 支持首次响应达标率 | ≥90% | `support_ledger` | 支持 |
| 免费补证/重跑率 | ≤20% | `delivery_ledger` | 质量 |
| 运行成功率 | 只建基线 | `system_compliance_ledger` | 技术 |
| 延迟 | 只建基线 | `system_compliance_ledger` | 技术 |
| 队列等待 | 只建基线 | `system_compliance_ledger` | 技术 |
| provider 错误率 | 只建基线 | `system_compliance_ledger` | 技术 |

预警指标未在 D0 冻结时，不能用于 Conditional Go。

## 8. 硬门禁

| 类别 | 硬门禁 |
|---|---|
| 商业 | 3–5 家实际付费；≥3 家活跃；≥2 家第二任务或刷新；回款率 100%；企业采购准入 100% |
| 经济 | 所有仍在售市场与包型贡献毛利不为负 |
| 产品 | 正式任务完成率 ≥90%；5 个工作日内验收或进入明确异议；≥2 家第二任务或刷新 |
| 质量 | 每个约定市场有质量状态；不合格市场输出证据不足；正式 Claim 追溯率 100%；Claim 等级不超证据上限 100%；关键 Claim 独立来源覆盖率和正确率 100%；刷新可比性状态完整 100%；重大口径争议 0 |
| 系统 | 跨工作区泄露 0；客户执行回退演示工作区 0；账本不平 0；重复结算 0；幂等重复计费 0；超预算继续执行 0；关键操作缺少审计 0 |
| 合规 | DPA 和子处理者覆盖 100%；数据源书面权利覆盖 100%；客户链 Cookie 暴露 0；PII 违规发布 0；LLM 处理披露并接受 100% |

## 9. 证据

- 每条台账行必须有 `evidence_id`。
- 证据文件存 `$PG1_EVIDENCE_ROOT`。
- 仓库只存 `evidence_index.csv` 和 SHA-256。
- 证据缺失时，门禁写 `insufficient_evidence`，不得写 `pass`。
- 口头说明、聊天截图、未签字文档不算证据。
- 测试或演练证据使用合成数据，并在 `notes` 标记 `synthetic=yes`。

## 10. 延期

- 只在 D90 申请。
- 只适用于证据不足，不适用于硬门禁失败。
- 最多一次，最长 30 天。
- 必须写明缺少的证据、负责人、复核日期。
- 延期不延长销售目标，不新增范围。
- 延期后仍无证据，结论为 No-Go。

指导委员会由第 12 节的九个角色组成。延期由指导委员会批准。

## 11. 决策

| 结论 | 条件 |
|---|---|
| Go | 所有硬门禁通过；商业和单位经济成立；无未解决重大事件；无范围漂移 |
| Conditional Go | 所有硬门禁通过；仅 D0 冻结的预警指标未达；有整改负责人和复核门禁 |
| No-Go | 任一硬门禁失败；或商业模型不成立 |

Conditional Go 不能豁免任何硬门禁。
P2 不在批准范围。Go 或 Conditional Go 只允许提出 P2 方案。

## 12. 角色与签字

| 角色 | 责任 | D90 签字 |
|---|---|---|
| Pilot Owner | 总体推进、周报、决策记录 | 是 |
| Sales Lead | 管道、合同、回款 | 是 |
| Delivery Lead | 订单、交付、验收 | 是 |
| Data Quality Lead | 质量、Claim、审核 | 是 |
| Finance Lead | 毛利、回款、汇率 | 是 |
| Legal / Compliance Lead | DPA、子处理者、来源权利 | 是 |
| Security Lead | 系统硬门禁、事件响应 | 是 |
| Product Lead | 模板边界、范围控制 | 是 |
| Executive Sponsor | 延期和 No-Go 批准 | 是 |

## 13. D0 冻结字段

| 字段 | 来源 | 未提供时的动作 |
|---|---|---|
| `review_labor_rate_usd` | Finance 书面确认 | 不启动 O1 |
| `payment_fee_rate` | Finance 书面确认 | 按实际费用，不得估算为 0 |
| `price_book_version` | Product | 不报价 |
| `dpa_version` | Legal | 不签发客户密钥 |
| `subprocessor_version` | Legal | 不处理客户数据 |
| `llm_disclosure_version` | Legal | 不调用 LLM |
| `refund_weight_version` | Finance 和 Legal | 不签合同 |
````

预期：`charter.md` 含 13 节。

- [ ] **Step 6: 写 README**

```bash
D0=$(cat docs/ops/pg1-pilot/D0.txt)
python3 -I -c "from datetime import date,timedelta; d=date.fromisoformat('$D0'); print('D0',d); print('D30',d+timedelta(days=30)); print('D60',d+timedelta(days=60)); print('D90',d+timedelta(days=90))"
```

将输出写入 `docs/ops/pg1-pilot/README.md`。填写 D0、D30、D60、D90 的实际日期和 Pilot Owner 姓名：

```markdown
# O1 / PG1 付费试点控制台

- 阶段：PG1 进行中
- D0：not_recorded
- D30：not_recorded
- D60：not_recorded
- D90：not_recorded
- 当前结论：未评审
- Pilot Owner：not_assigned

## 台账

所有数字从 `ledgers/` 取数。证据索引是 `ledgers/evidence_index.csv`。

## 文件

- `charter.md`：章程和口径。
- `weekly/`：周报。
- `reviews/`：D30、D60、D90 复盘。
- `decisions/`：PG1 决议和延期决议。
- `imports/`：脱敏摘要和公开报告合同。原始导出在 `$PG1_EVIDENCE_ROOT/PG1/imports/`，不提交。

## 规则

- 周报数据截止为周四 23:59。
- 运行成本账本和审计只追加。业务台账状态更新必须留痕。
- 证据文件不进入仓库。
```

预期：README 含 D0、D30、D60、D90 的实际日期。

- [ ] **Step 7: 登记 PG0 证据**

```bash
mkdir -p "$PG1_EVIDENCE_ROOT/PG0"
cp docs/evidence/o0-pg0/pg0-review/decision.md "$PG1_EVIDENCE_ROOT/PG0/PG0-decision.md"
cp docs/evidence/o0-pg0/pg0-review/signoff.csv "$PG1_EVIDENCE_ROOT/PG0/PG0-signoff.csv"
cp docs/evidence/o0-pg0/pg0-review/gate-matrix.csv "$PG1_EVIDENCE_ROOT/PG0/PG0-gate-matrix.csv"
H1=$(shasum -a 256 "$PG1_EVIDENCE_ROOT/PG0/PG0-decision.md" | awk '{print $1}')
H2=$(shasum -a 256 "$PG1_EVIDENCE_ROOT/PG0/PG0-signoff.csv" | awk '{print $1}')
H3=$(shasum -a 256 "$PG1_EVIDENCE_ROOT/PG0/PG0-gate-matrix.csv" | awk '{print $1}')
printf '%s\n' "EV-0001,PG0,pg0_decision,$(date +%F),PG0/PG0-decision.md,$H1,legal,$(whoami),$(date -u +%FT%TZ),PG0 pass decision" >> docs/ops/pg1-pilot/ledgers/evidence_index.csv
printf '%s\n' "EV-0002,PG0,pg0_signoff,$(date +%F),PG0/PG0-signoff.csv,$H2,legal,$(whoami),$(date -u +%FT%TZ),six approvals" >> docs/ops/pg1-pilot/ledgers/evidence_index.csv
printf '%s\n' "EV-0003,PG0,pg0_gate_matrix,$(date +%F),PG0/PG0-gate-matrix.csv,$H3,legal,$(whoami),$(date -u +%FT%TZ),11 gates pass" >> docs/ops/pg1-pilot/ledgers/evidence_index.csv
```

预期：`evidence_index.csv` 有三行数据。

- [ ] **Step 8: 校验表头与证据**

```bash
python3 -I -c '
import csv, glob
files = sorted(glob.glob("docs/ops/pg1-pilot/ledgers/*.csv"))
assert len(files) == 15, files
for p in files:
    header = next(csv.reader(open(p, encoding="utf-8")))
    assert header and len(header) == len(set(header)), p
    print(p, len(header))
'
```

预期：15 个文件，无重复列。

- [ ] **Step 9: 检查仓库无密钥**

```bash
if grep -RInE '(sk-[A-Za-z0-9]{20,}|Bearer [A-Za-z0-9._-]{20,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)' docs/ops/pg1-pilot; then
  echo "sensitive material found"
  exit 1
fi
if grep -RInE 'T[B]D|T[O]DO|待[填]|待[补]|FIX[M]E|XX[X]' docs/ops/pg1-pilot; then
  echo "placeholder found"
  exit 1
fi
```

预期：无输出，退出码 0。

- [ ] **Step 10: 提交**

```bash
git add docs/ops/pg1-pilot
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): bootstrap pilot control room and freeze charter"
```

预期：提交创建。

---

### Task 2: 伙伴筛选与付费管道

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/partner_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-01/` 至 `$PG1_EVIDENCE_ROOT/P-05/`

**Interfaces:**
- Consumes: O0 的 PG0 承诺清单。
- Produces: `partner_id`、`commitment_type`、`actual_paid`、`active_30d`、`enterprise_clearance`。

- [ ] **Step 1: 建立候选清单**

从 `docs/evidence/o0-pg0/commitments/paid-commitments.csv` 复制每个伙伴。只复制 `status=executable` 的行。`counts_toward_p1=no` 保持不变。`partner_code` 写 O0 的 `commit_id`，例如 `COMMIT-001`。`partner_id` 由 O1 分配，例如 `P-01`。每行必须写：

- `commitment_type=PG0_commitment`；
- `actual_paid=no`；
- `stage=qualified` 或 `lead`；
- `evidence_id` 指向 `O0-COMMIT-001` 到 `O0-COMMIT-003`。

PG0 承诺只进入管道。它不进入付费统计。

- [ ] **Step 2: 按资格表评分**

| 条件 | 通过标准 | 证据 |
|---|---|---|
| 决策人 | 能直接接触预算签字人 | 会议记录或邮件 |
| 预算 | 本季度有明确预算 | 书面确认 |
| 采购路径 | 30 天内可完成合同和付款 | 采购流程说明 |
| 市场 | 主市场在 11 个正式市场 | 需求说明 |
| 场景 | TikTok Shop 母婴新品进入 | 需求说明 |
| 合规 | 接受 DPA、子处理者、LLM 披露 | 签字 |
| 边界 | 接受任务包；拒绝裸 API、按次计费、Cookie、白标 | 书面确认 |

- [ ] **Step 3: 应用排除规则**

| 条件 | 处理 |
|---|---|
| 要裸 API 或原始 JSON | 不进入试点 |
| 要按调用次数计费 | 不进入试点 |
| 要母婴以外模板 | 不进入试点；记录为 P2 需求 |
| 要客户 Cookie 或 Seller Center 登录 | 不进入试点 |
| 要白标或多级分销 | 不进入试点 |
| 只有 LOI 或口头意向 | 留在管道；不计付费 |
| 主市场不在正式目录 | 不进入试点 |
| 要求免费定制 | 不进入试点 |

- [ ] **Step 4: 分配 ID 并写行**

目标组合：3 家跨境品牌加 2 家 Agency。总数 3–5 家。
如果 PG0 承诺少于 5 家，启动外部招募。优先有预算和决策人的跨境品牌，以及有终端品牌客户的 Agency。
一个 Agency 一个工作区。一个终端品牌一个项目。Agency 的终端品牌不单独计数。

示例行只用于核对字段顺序。`P-00` 永不作为真实伙伴：

```csv
partner_id,partner_code,segment,primary_market,decision_maker_role,procurement_path,stage,commitment_type,commitment_date,contract_id,actual_paid,first_payment_date,active_30d,enterprise_clearance,disqualified_reason,evidence_id,notes
P-00,EXAMPLE,brand,US,GM,direct,qualified,PG0_commitment,2026-10-15,,no,,no,pending,,EV-0004,synthetic example
```

- [ ] **Step 5: 校验没有把承诺算付费**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/partner_ledger.csv", encoding="utf-8")))
paid = [r for r in rows if r["actual_paid"] == "yes"]
assert all(r["commitment_type"] == "paid_contract" for r in paid), paid
assert all(r["contract_id"] and r["first_payment_date"] for r in paid), paid
assert all(r["commitment_type"] != "PG0_commitment" for r in paid), paid
assert len(paid) <= 5, paid
print("actual paid", len(paid))
print("pipeline", len(rows))
'
```

预期：启动时 `actual paid 0`。任何 PG0 承诺出现在付费集合中即失败。

- [ ] **Step 6: 每周更新管道**

每周五更新 `stage`、`commitment_type`、`actual_paid`、`active_30d`。只改本周行，不改历史事实。管道变化写入周报第 3 节。

- [ ] **Step 7: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/partner_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record qualified partner pipeline"
```

---

### Task 3: 合同、SOW 与 DPA

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/contract_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/partner_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/signed_contract.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/dpa_signed.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/subprocessor_ack.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/llm_disclosure_ack.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/enterprise_pack/`

**Interfaces:**
- Consumes: `partner_id`，`stage=qualified`。
- Produces: `contract_id`、`dpa_version`、`subprocessor_version`、`llm_disclosure_version`、`refund_weight_version`、`status=signed`。

- [ ] **Step 1: 准备合同包**

每个伙伴的合同包必须包含：

1. 订单表或 SOW；
2. 标准条款；
3. DPA；
4. 子处理者清单；
5. LLM 披露附件；
6. 退款和抵扣权重表；
7. 验收清单。

缺少任何一项，不签发客户密钥。

- [ ] **Step 2: 填写 SOW 条款**

| 条款 | 必须写入的内容 | 证据 |
|---|---|---|
| 当事人 | 法定名称、地址、签字人 | 签字页 |
| 范围 | 模板版本、包型、市场、订单数量 | SOW 附件 |
| 交付物 | 中文主报告、英文摘要、CSV 或 Parquet、数据字典、质量记分卡、Claim-Evidence 索引、回执、报告合同、Gap、manifest | SOW 附件 |
| 价格 | USD 单价、折扣、价格簿版本 | 报价单 |
| 付款 | 首单 100% 预付；复购 50% 下单、50% 验收后 7 日 | 合同 |
| 验收 | 5 个工作日；逾期视为验收；事实错误不限次免费纠正；表达调整一轮 | 合同 |
| 退款/抵扣 | 按 D0 冻结的市场 × 数据域权重 | 附件 |
| 数据权利 | 不转售、不裸 API、不按调用计费 | 合同 |
| 隐私 | DPA、子处理者清单、跨境说明、DSR | DPA |
| LLM | 零保留、禁止训练、伪名化输入、披露 | 附件 |
| Cookie | 客户链不接受 Cookie | 合同 |
| 范围变更 | 新市场、品类、竞品、时间窗 = 新订单 | 合同 |
| 延期 | 只用于证据不足，一次 30 天 | 合同 |
| 终止 | 未付款、违约、合规停止 | 合同 |

合同分别记录每个市场的 `floor_n`、`target_n` 和 `plan_cap_n`。验收只检查 `floor_n`。未采满 `plan_cap_n` 不构成违约。

- [ ] **Step 3: 谈判与签署**

只使用标准条款。任何偏离必须由 Legal / Compliance Lead 书面批准。
签署前确认 O0 的商业、法务、财务证据覆盖本合同。缺少覆盖时，不签合同。
不提供免费定制。不承诺模板、品类或正式市场以外的范围。
签字人必须有授权。签字日期不得晚于首单日期。

- [ ] **Step 4: 登记合同**

每份合同写一行 `contract_ledger.csv`：

- `status=draft/sent/signed/active/closed/terminated`；
- `dpa_version`、`subprocessor_version`、`llm_disclosure_version` 必填；
- `refund_weight_version` 必填；
- `payment_terms` 用 `100pct_prepaid` 或 `50_50_net7`；
- `acceptance_terms=5bd_deemed`。

- [ ] **Step 5: 证据入库**

把签署文件放入 `$PG1_EVIDENCE_ROOT/P-01/`。文件名固定为 `signed_contract.pdf`、`dpa_signed.pdf`、`subprocessor_ack.pdf`、`llm_disclosure_ack.pdf`。

```bash
PARTNER=P-01
mkdir -p "$PG1_EVIDENCE_ROOT/$PARTNER"
(cd "$PG1_EVIDENCE_ROOT/$PARTNER" && shasum -a 256 signed_contract.pdf dpa_signed.pdf subprocessor_ack.pdf llm_disclosure_ack.pdf > SHA256SUMS && shasum -a 256 -c SHA256SUMS)
```

预期：`OK`。把每个 SHA-256 写入 `evidence_index.csv`，`access_class=commercial` 或 `legal`。

- [ ] **Step 6: 完成企业采购准入**

O0 的 `docs/evidence/o0-pg0/commitments/enterprise-requirements.csv` 是输入。每个实际付费伙伴的需求矩阵必须在该文件有记录。

每个实际付费伙伴必须完成企业采购准入。材料包至少包含：

| 材料 | 内容 | 负责人 |
|---|---|---|
| DPA | 已签版本 | Legal |
| 子处理者清单 | 从实际调用链生成，含 TikHub、Apify 及具体 Actor、Exa、Firecrawl、Jina、云、存储、LLM、邮件、监控、客服和支付 | Legal |
| 数据流图 | 客户数据、证据、备份和跨境路径 | Security |
| 保留和删除政策 | 当前版本 | Legal |
| 安全问卷 | 每题有证据、负责人、日期和版本 | Security |
| 跨境说明 | 实际区域和机制；律师未确认的机制写“未确认” | Legal |
| 内部访问和审计 | 访问类型、审批、日志和紧急访问 | Security |
| 事件响应和灾备 | 当前计划和演练证据 | Security |
| 认证、测试和保险 | 实际持有；未持有写“未持有” | Security |
| 上游书面许可 | TikHub 等来源的商业许可 | Legal |
| LLM 条款 | 零保留和禁止训练书面条款 | Legal |

未实现或未持有的能力必须写“未实现”“未持有”或“待验证”。不得用“计划中”暗示已经具备。
客户采购书面确认后，才把 `partner_ledger.csv` 的 `enterprise_clearance` 写为 `yes`。
新增或替换子处理者必须提前 30 天通知客户，并取得书面接受。未接受时不得使用该子处理者处理客户数据。

- [ ] **Step 7: 校验合同字段**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/contract_ledger.csv", encoding="utf-8")))
req = ["contract_id","partner_id","sow_version","template_version","package_scope","markets","contract_value_usd","currency","payment_terms","acceptance_terms","status","evidence_id"]
signed_req = ["signed_date","refund_weight_version","dpa_version","subprocessor_version","llm_disclosure_version"]
bad = [(r["contract_id"], c) for r in rows for c in req if not r.get(c)]
bad += [(r["contract_id"], c) for r in rows if r["status"] in {"signed","active","closed","terminated"} for c in signed_req if not r.get(c)]
assert not bad, bad
print("contracts OK", len(rows))
'
```

预期：`contracts OK`。缺字段即失败。

- [ ] **Step 8: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/contract_ledger.csv docs/ops/pg1-pilot/ledgers/partner_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): register signed contracts and DPA versions"
```

---

### Task 4: 开票、回款与账龄

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/payment_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/invoice_*.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/bank_receipt_*.pdf`

**Interfaces:**
- Consumes: `contract_id`、`contract_value_usd`、`payment_terms`。
- Produces: `payment_id`、`collection_status`、`amount_paid_usd`、`days_late`。

- [ ] **Step 1: 开票**

按合同开票。记录 `invoice_id`、`invoice_date`、`amount_due_local`、`currency`。
金额保留 2 位小数，使用 `Decimal`。CSV 金额不加千分位分隔符。
合同以 USD 计价。本币付款按付款日中国外汇交易中心中间价折算 USD。
记录 `fx_rate`、`fx_date`、`fx_source`。

- [ ] **Step 2: 匹配到账**

只以银行回单确认到账。记录：

- `paid_date`；
- `payment_method`；
- `bank_receipt_id`；
- `amount_paid_local`；
- `amount_paid_usd`；
- `collection_status=collected`；
- `days_late`。

未到账时写 `collection_status=open` 或 `overdue`。不得写 `collected`。

- [ ] **Step 3: 周度账龄**

| 账龄 | 动作 | 负责人 |
|---|---|---|
| 0–7 天 | 提醒 | Sales |
| 8–30 天 | 电话和书面催收 | Sales Lead |
| 31–60 天 | Pilot Owner 和 Finance 介入 | Pilot Owner |
| >60 天 | 停止新订单，Legal 介入 | Legal / Compliance Lead |

未付款不进入正式生产。复购 50/50 例外只在首 50% 到账后成立。

- [ ] **Step 4: 对账**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
from collections import defaultdict
contracts = {r["contract_id"]: D(r["contract_value_usd"]) for r in csv.DictReader(open("docs/ops/pg1-pilot/ledgers/contract_ledger.csv", encoding="utf-8")) if r["status"] in {"signed","active","closed","terminated"}}
paid = defaultdict(D)
for r in csv.DictReader(open("docs/ops/pg1-pilot/ledgers/payment_ledger.csv", encoding="utf-8")):
    paid[r["contract_id"]] += D(r["amount_paid_usd"] or "0")
bad = [k for k, v in contracts.items() if paid[k] != v]
assert not bad, bad
print("reconciled", len(contracts))
'
```

预期：`reconciled`，无差异。

- [ ] **Step 5: 验证 D90 回款口径**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/payment_ledger.csv", encoding="utf-8")))
due = sum(D(r["amount_due_usd"] or "0") for r in rows)
paid = sum(D(r["amount_paid_usd"] or "0") for r in rows)
assert due == paid, (due, paid)
assert all(r["collection_status"] == "collected" for r in rows if r["amount_due_usd"]), [r["payment_id"] for r in rows if r["collection_status"] != "collected"]
print("collected", paid)
'
```

预期：`collected`，无未回款行。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/payment_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record invoices and collected payments"
```

---

### Task 5: 客户开通与边界验证

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/provisioning_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/workspace_provisioning.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/boundary_test.pdf`

**Interfaces:**
- Consumes: `contract_id`，合同 `signed` 或 `active`，首单款项 `collected`。
- Produces: `workspace_id`、`project_id`、`key_prefix`、`boundary_test_result`、`audit_event_id`。

- [ ] **Step 1: 创建工作区与项目**

创建前确认合同 `status` 为 `signed` 或 `active`，首单款项 `collection_status=collected`。未到账不签发密钥。

- 一个 Agency 一个工作区。
- 一个终端品牌一个项目。
- 角色只有 `owner`、`admin`、`member`。
- 每个工作区至少一名 `owner`。
- 内部审核员不进入客户成员列表。
- `member` 只能访问被授权项目。
- 项目之间不共享数据、证据、提示词、嵌入或预算。

- [ ] **Step 2: 签发项目密钥**

- 密钥绑定一个工作区和一个项目。
- 密钥含工具白名单和日额度。
- 明文只显示一次。
- 数据库只存哈希和前缀。
- 完整密钥不得进入 URL、日志、错误、报告、bundle 或工单。
- 每个项目最多一把有效密钥。
- 轮换必须原子完成。失败整体回滚。
- 撤销后新请求立即失败。

- [ ] **Step 3: 运行边界测试**

请求检查顺序固定为：Bearer 鉴权 → 密钥状态 → 工作区与项目绑定 → 工具白名单 → 能力白名单 → Cookie 隔离 → 日额度 → 速率与并发 → 预算 → 执行与审计。

| 测试 | 期望 | 证据 |
|---|---|---|
| 工作区/项目绑定 | 密钥只访问绑定项目 | 密钥详情 |
| 工具白名单外 | 403 `tool_not_allowed` | 请求和响应 |
| 日额度外 | 429 `quota_exceeded` | 请求和响应 |
| 速率或并发超限 | 429 | 请求和响应 |
| 预算不足 | `approval_required` | 请求和响应 |
| 跨项目访问 | 403 或 404 | 请求和响应 |
| 跨工作区访问 | 403 或 404 | 请求和响应 |
| 客户链 Cookie | 0 | 配置和审计 |
| 演示工作区回退 | 0 | 运行元数据 |
| 客户 MCP 工具（`/mcp/customer`） | 只显示 8 个 | `tools/list` 导出 |

客户 MCP 的 8 个工具：

1. `discover_capabilities`
2. `estimate_task`
3. `create_task`
4. `get_task`
5. `cancel_task`
6. `get_delivery_manifest`
7. `get_evidence`
8. `collect`

MCP 工具只增不改。破坏性变化必须使用新工具名。旧工具至少保留一个迁移周期再下线。

`tiktok.creator_cookie` 从首期模板白名单和客户 MCP 移除。其输出不能进入客户数据集、Claim、报告和 manifest。调用和拒绝都写审计。

- [ ] **Step 4: 记录审计事件**

密钥签发、轮换、撤销和拒绝都必须有审计事件。把事件 ID 写入 `provisioning_ledger.csv`。

- [ ] **Step 5: 校验开通台账**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/provisioning_ledger.csv", encoding="utf-8")))
for r in rows:
    assert r["workspace_id"] and r["project_id"] and r["key_prefix"], r
    assert r["boundary_test_result"] == "pass", r
    assert r["audit_event_id"], r
print("provisioning OK", len(rows))
'
```

预期：`provisioning OK`。任一边界测试失败即停止该客户。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/provisioning_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): provision customer workspaces and verify boundaries"
```

---

### Task 6: 订单受理、报价与预算

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/order_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/quote_ORD-xx.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/order_ORD-xx.pdf`

**Interfaces:**
- Consumes: `contract_id`、`partner_id`、`workspace_id`、`project_id`、价格簿版本。
- Produces: `order_id`、`quote_id`、`idempotency_key`、`quoted_price_usd`、`max_cost_usd`。

- [ ] **Step 1: 运行输入检查**

| 输入 | 规则 | 拒绝码 |
|---|---|---|
| 工作区与项目 | 由会话或密钥解析，请求不能覆盖 | `auth_error` |
| 模板 | 只允许母婴新品进入冻结版本 | `template_not_allowed` |
| 品类 | 必须来自母婴二级品类表 | `category_not_allowed` |
| 主市场 | 必须选 1 个正式市场 | `market_unsupported` |
| 对比市场 | Quick 0–1；Standard 0–3 | `scope_invalid` |
| 时间窗 | 固定起止日期，不能含未来日期 | `time_window_invalid` |
| 决策问题 | 必须可以明确回答 | `question_unanswerable` |
| 种子商品或竞品 | 可选；使用时 3–10 个公开链接或 ID | `seed_invalid` |
| 预算 | `max_cost_usd`、`max_pages`、`max_records` | `budget_missing` |
| 幂等键 | 必填 | `idempotency_key_missing` |
| 价格 | 所有工具已定价 | `tool_not_priced` |

客户不能指定 provider、上游端点、分页、重试、降级链、Cookie 或 Seller Center 登录态。

- [ ] **Step 2: 估算成本**

先运行 `estimate_task`。报价必须来自估算结果和价格簿。
单价未知时不报价、不执行。不得按零成本报价。
报价有效期 7 天。报价记录价格簿版本。

- [ ] **Step 3: 确认付款并创建订单**

首单 100% 到账后创建订单。复购 50% 到账后创建订单。
创建订单必须带幂等键。相同键和相同参数返回原订单。
相同键和不同参数返回 409。

发起人不能批准自己的超额、加购或密钥变更。批准必须来自具备 `owner` 或 `admin` 角色的人类登录会话，并在批准页完成第二次确认；MFA 延期，不作为批准前提。Agent、项目密钥和服务账号不能批准。

- [ ] **Step 4: 写入订单台账**

`order_ledger.csv` 每行记录：

- `order_id`、`partner_id`、`contract_id`；
- `package_type`、`primary_market`、`compare_markets`；
- `template_version`、`decision_question`、`time_window_start`、`time_window_end`；
- `max_cost_usd`、`max_pages`、`max_records`；
- `idempotency_key`、`quote_id`、`quoted_price_usd`、`quote_valid_until`；
- `status`。

- [ ] **Step 5: 校验订单**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/order_ledger.csv", encoding="utf-8")))
for r in rows:
    assert r["order_id"] and r["contract_id"] and r["idempotency_key"], r
    assert r["quote_id"] and r["quoted_price_usd"], r
    assert r["max_cost_usd"] and r["max_pages"] and r["max_records"], r
    assert r["status"] != "running" or r["order_created_at"], r
print("orders OK", len(rows))
'
```

预期：`orders OK`。缺字段即失败。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/order_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record quoted orders and budgets"
```

---

### Task 7: 交付、报告合同与验收

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/delivery_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/PG1/imports/report_contract_ORD-xx.json`
- Create: `docs/ops/pg1-pilot/imports/report_contract_ORD-xx.json`，仅脱敏公开投影
- Create: `$PG1_EVIDENCE_ROOT/P-xx/report_contract_ORD-xx.json`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/manifest_ORD-xx.json`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/acceptance_ORD-xx.pdf`

**Interfaces:**
- Consumes: `order_id`、`package_type`、`max_cost_usd`。
- Produces: `delivery_id`、`manifest_id`、`report_contract_id`、`acceptance_result`、`rework_type`。

- [ ] **Step 1: 每日交付看板**

每天检查：

- Quick 2 小时方向稿；
- Quick 和 Standard 24 小时正式版；
- 队列等待；
- 预算剩余；
- 市场门禁状态。

预计超时，立即通知客户并写入交付台账。不得静默延期。
订单状态由各市场 run 聚合。

- [ ] **Step 2: 交付前检查**

- 订单状态为已批准；
- 预算足够；
- 市场门禁不是 `blocked`；
- 模板版本冻结；
- 核心域 3/3；
- 增强域缺口已记录。

每个市场一个 run。市场门禁为 `blocked` 时保留 run 和 gap，不静默删除，不写 `runs.status`。

- [ ] **Step 3: 报告合同**

`report_contract` 必须包含：

- 合同、订单、模板和报告版本；
- 决策问题和不回答项；
- 每个市场的状态、质量、样本、门槛和缺口；
- Claims、Evidence 和反证；
- Standard SKU 候选；
- 数据集版本和哈希；
- 质量记分卡；
- 来源权利和上游商业门禁；
- 原币、USD、汇率日期和来源；
- 语言和翻译方法；
- 限制、未知项和非承诺；
- 审核人、审核范围、审核时间、审核版本和合同哈希；
- 验收快照；
- 交付 bundle、manifest、访问范围和保留类别。

报告合同用 canonical JSON。发布前通过 schema、语义和禁用词校验。
渲染器只读合同，不重新查库或调用模型。
报告合同发布后不能修改。修订生成新的 `contract_id` 和 `report_version`，并用 `supersedes_id` 指向旧版本。
公开投影不包含 provider、端点、凭据、内部单价和内部批准人。
报告首屏显示各市场状态、最低证据等级、关键缺口和 Claim 分布。

- [ ] **Step 4: 交付包与 manifest**

正式交付包包含 11 项：

1. 中文主报告；
2. 英文执行摘要；
3. CSV 或 Parquet 数据集；
4. 数据字典；
5. 逐市场质量记分卡；
6. Claim 到 Evidence 的索引；
7. 客户运行回执；
8. 公开报告合同；
9. 限制、未知项和 Gap；
10. `delivery_manifest.json`；
11. 交付时验收快照。

每个文件有 SHA-256。manifest 自身哈希写外部 sidecar 和追加式交付审计事件。
发布后的交付包不可修改。验收状态变化写入追加式验收事件，不能修改 manifest。

导出前遮蔽联系方式、个人主页链接、评论正文中的外部链接和普通用户 handle。证据来源 URL 保留，只去掉追踪参数。品牌、店铺和商业创作者的公开身份可以保留。
客户数据使用工作区级伪名。同一工作区稳定，跨工作区不可关联。Agency 使用其工作区盐。项目隔离依靠权限，不改项目级盐。不提供反查映射。

- [ ] **Step 5: 交付并启动验收**

正式版交付时，向客户发验收清单。验收期 5 个工作日。
逾期未提出异议，视为验收。
Quick 2 小时稿不触发验收。
Quick 2 小时稿和 24 小时正式版属于同一任务，不重复收费。24 小时正式版可以完成原计划内未完成的采集，但不得扩大冻结范围。

- [ ] **Step 6: 处理验收结果**

| 情形 | 处理 |
|---|---|
| 事实、计算或证据引用错误 | 免费纠正，不限次数；生成新版本并重新审核 |
| 同范围表达、图表和重点调整 | 包含一轮 |
| 新增市场、品类、竞品、时间窗或数据域 | 新订单或加购 |
| 平台执行缺陷导致门禁失败 | 免费补证或重跑一次 |
| 第二次仍失败 | 按未交付部分退款或抵扣 |
| 客户中途取消 | 按已完成阶段结算 |
| 真实空结果 | 不自动退款；披露来源、尝试次数和边界 |
| `insufficient_evidence` | 有效交付；不自动免费重跑 |

Agency 终端客户意见属于修订意见，不能直接触发拒收。
事实错误不受验收期限制。
退款或抵扣按合同预先冻结的市场 × 数据域权重计算。争议发生后不得临时分配权重。

- [ ] **Step 7: 校验交付台账**

```bash
python3 -I -c '
import csv
from datetime import date, timedelta

def add_business_days(start, n):
    d = start
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d

rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/delivery_ledger.csv", encoding="utf-8")))
for r in rows:
    if r["formal_delivered_at"]:
        assert r["manifest_id"] and r["report_contract_id"], r
        assert r["acceptance_start"] and r["acceptance_end"], r
        start = date.fromisoformat(r["formal_delivered_at"][:10])
        end = date.fromisoformat(r["acceptance_end"][:10])
        assert end >= add_business_days(start, 5), r
print("delivery OK", len(rows))
'
```

预期：`delivery OK`。验收截止日早于第 5 个工作日即失败。
法定节假日由交付负责人手工核对，并写入备注。

- [ ] **Step 8: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/delivery_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record deliveries, report contracts and acceptance"
```

---

### Task 8: 复购与刷新

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/refresh_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/order_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/delivery_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`

**Interfaces:**
- Consumes: `source_delivery_id`、`partner_id`、`package_type=Standard`。
- Produces: `refresh_id`、`new_order_id`、`comparability_status`、`status`。

- [ ] **Step 1: 排期月度刷新**

Standard 正式版交付后 30 天，向客户提供月度刷新报价。
刷新是新订单。刷新不自动续费。客户必须书面下单并付款。

周度刷新只作受限验证：

- 最多 2 家伙伴；
- 最多 4 次刷新；
- 手工执行，不自动化；
- 不作为普遍承诺；
- 不进入标准价格簿。

- [ ] **Step 2: 创建刷新订单**

刷新订单沿用主模板和主市场角色。价格来自价格簿。
刷新订单记录新的 `order_id` 和 `quote_id`。
首单 100% 预付；复购 50/50 按 Task 4 规则。

- [ ] **Step 3: 执行刷新**

刷新生成新的计划版本、runs、数据集版本、Claims、报告合同、交付包和验收周期。
旧版本保持不可变。

- [ ] **Step 4: 判定可比性**

| 条件 | 要求 |
|---|---|
| 模板版本 | 相同 |
| 主市场和对比市场角色 | 相同 |
| 时间窗长度和对齐方式 | 相同 |
| 指标定义 | 相同 |
| 计数类型 | 相同 |
| 分类和编码本 | 相同 |
| 汇率政策 | 相同 |
| 伪名盐值 | 相同 |
| 来源组合 | 相同或已披露等价替换 |

可比状态：

- `comparable`；
- `comparable_with_caveats`；
- `not_comparable`；
- `failed`。

来源变化不能平滑成连续趋势。必要时建立新基线。

- [ ] **Step 5: 处理刷新失败**

刷新失败时保留上一个可用交付包，标记 `stale`，列出未刷新的市场和数据域。
不允许部分结果覆盖旧正式版本。

- [ ] **Step 6: 跟踪二次购买**

每周统计：

- 有第二个付费订单的伙伴数；
- 有已交付刷新的伙伴数；
- 刷新收入。

D90 目标：至少 2 家购买第二任务或刷新。

- [ ] **Step 7: 校验刷新台账**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/refresh_ledger.csv", encoding="utf-8")))
for r in rows:
    if r["status"] == "delivered":
        assert r["comparability_status"] in {"comparable","comparable_with_caveats","not_comparable"}, r
        assert r["new_order_id"] and r["collected_usd"], r
print("refresh OK", len(rows))
'
```

预期：`refresh OK`。已交付刷新缺可比性状态即失败。

- [ ] **Step 8: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/refresh_ledger.csv docs/ops/pg1-pilot/ledgers/order_ledger.csv docs/ops/pg1-pilot/ledgers/delivery_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record repeat purchases and refreshes"
```

---

### Task 9: 单位经济与毛利

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/margin_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/PG1/imports/run_ledger_YYYY-Www.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/finance_pack_YYYY-MM.pdf`

**Interfaces:**
- Consumes: `order_id`、`payment_id`、run 账本导出、审核工时、银行费用。
- Produces: `margin_id`、`contribution_margin_usd`、`cost_deviation_pct`、`price_realization_pct`。

- [ ] **Step 1: 每周取数**

每周导出：

- `run_ledger_entries`：只取 `settle` 和 `release`；
- 回款台账；
- 审核工时；
- 银行或支付渠道费用；
- 开票和退款记录。

导出文件放 `$PG1_EVIDENCE_ROOT/PG1/imports/`，文件名 `run_ledger_YYYY-Www.csv`。原始导出不提交 Git。

- [ ] **Step 2: 计算每行毛利**

每个 `order_id × market × package_type` 一行：

金额保留 2 位小数，使用 `Decimal`，不得用浮点数。CSV 金额不加千分位分隔符。

```text
net_revenue_usd = 已开票 USD - 退款 - 抵扣
provider_settle_usd = SUM(settle.amount_usd) + SUM(release.amount_usd)
review_labor_usd = 审核工时 × 冻结小时成本
payment_fee_usd = 实际渠道费用
contribution_margin_usd = net_revenue_usd - provider_settle_usd - review_labor_usd - payment_fee_usd
```

同时记录：

- `quote_cost_usd`；
- `actual_cost_usd`；
- `cost_deviation_pct`；
- `list_price_usd`；
- `price_realized_usd`；
- `price_realization_pct`；
- `still_sold=yes/no`；
- `close_month`。

- [ ] **Step 3: 处理负毛利组合**

| 情况 | 动作 | 时限 |
|---|---|---|
| 毛利 < 0 | 调价、缩范围或停售 | 5 个工作日 |
| 报价偏差 > ±20% | 书面解释并修正报价模型 | 5 个工作日 |
| 价格实现率 < 85% | 销售复核折扣 | 5 个工作日 |

负毛利组合如果仍在售，D90 经济硬门禁失败。
停售必须在价格簿和销售材料同步生效，并记录停售日期。

- [ ] **Step 4: 财务月度关账**

每月关账时，Finance Lead 签字确认：

- 收入；
- 退款和抵扣；
- 直接成本；
- 汇率；
- 毛利。

签字包存 `finance_pack_YYYY-MM.pdf`，`access_class=finance`。

- [ ] **Step 5: 校验毛利公式**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/margin_ledger.csv", encoding="utf-8")))
for r in rows:
    net = D(r["net_revenue_usd"])
    cost = D(r["provider_settle_usd"]) + D(r["review_labor_usd"]) + D(r["payment_fee_usd"])
    assert D(r["contribution_margin_usd"]) == net - cost, r["margin_id"]
    if r["quote_cost_usd"] and D(r["quote_cost_usd"]) != 0:
        dev = (D(r["actual_cost_usd"]) - D(r["quote_cost_usd"])) / D(r["quote_cost_usd"]) * 100
        assert abs(dev - D(r["cost_deviation_pct"])) < D("0.01"), r["margin_id"]
print("margin rows OK", len(rows))
'
```

预期：`margin rows OK`。公式不一致即失败。

- [ ] **Step 6: 校验 D90 经济硬门禁**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/margin_ledger.csv", encoding="utf-8")))
bad = [r["margin_id"] for r in rows if r["still_sold"] == "yes" and D(r["contribution_margin_usd"]) < 0]
assert not bad, bad
print("no negative still-sold combos")
'
```

预期：`no negative still-sold combos`。任何负毛利仍在售组合即失败。

- [ ] **Step 7: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/margin_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): close unit economics and contribution margin"
```

---

### Task 10: 质量硬门禁与 Claim 审核

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/quality_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/quality_scorecard_ORD-xx.pdf`
- Create: `$PG1_EVIDENCE_ROOT/P-xx/claim_evidence_index_ORD-xx.csv`

**Interfaces:**
- Consumes: `order_id`、`delivery_id`、报告合同、Claim 证据索引。
- Produces: `quality_id`、`market_quality_status`、`claim_level_cap_ok`、`major_definition_dispute`。

- [ ] **Step 1: 逐市场填质量行**

每个 `order_id × market` 一行。记录：
- 核心域 3/3；
- 商品、评论、达人内容数量；
- 字段完整率；
- 重复率；
- 来源 URL 覆盖率；
- Claim 证据绑定率；
- 独立来源覆盖率和正确率；
- 市场质量状态；
- Claim 等级上限；
- 刷新可比性状态；
- 正式 Claim 数和已追溯数；
- 重大口径争议。

所有分母使用去重、市场归属、时间窗和字段校验后的合格记录数，不是 provider 原始返回数。

每个缺口记录市场、数据域、原因码、实际值、门槛值、对结论的影响、客户可见说明、补救方式和严重度。

- [ ] **Step 2: 判定市场质量状态**

| 状态 | 条件 | 允许输出 |
|---|---|---|
| `qualified` | 核心门槛全部通过，无关键缺口 | Standard：完整四态和 SKU 候选；Quick：`worth_validating`、`deprioritize`、`key_risk` 或 `recommend_standard_scope` |
| `qualified_with_gap` | 核心门槛通过，但增强域或关键辅助证据有缺口 | Standard：`conditional_enter` 或 `insufficient_evidence`；Quick：`recommend_standard_scope`、`key_risk` 或 `evidence_gap` |
| `not_qualified` | 任一核心门槛失败 | Standard：只允许 `insufficient_evidence`；Quick：只允许 `evidence_gap` |

`missing` 不能写成数值 0。`blocked` 不能写成空结果。
真实空结果不能解释为“市场没有需求”。
Quick 不使用四态。所有 Quick 标签必须标记为方向性。
Standard 四态：`enter`、`conditional_enter`、`do_not_enter`、`insufficient_evidence`。

| Standard 状态 | 条件 |
|---|---|
| `enter` | 市场 `qualified`，无关键缺口，核心需求 Claim 达到确认要求，有 3–5 个非暂定候选 |
| `conditional_enter` | 机会存在，但有明确条件需要验证 |
| `do_not_enter` | 市场 `qualified`，至少两个独立来源支持，不能由缺失或失败推导 |
| `insufficient_evidence` | 市场未达标或存在关键缺口 |

`conditional_enter` 必须同时给出测试预算、观察周期、成功阈值和止损线。

Standard 输出 3–5 个有限排序 SKU 或价格带候选。每个候选必须包含目标市场、排名、原币和 USD 价格带、核心属性、需求证据、竞争证据、最低证据等级、风险标记和下一步验证动作。排序表示描述性机会顺序，不表示成功概率。候选少于 3 个时，不得补足虚假候选，也不得输出 `enter`；应改为 `conditional_enter` 或 `insufficient_evidence`。

- [ ] **Step 3: 黄金期全审**

黄金期范围：每个模板前 5 份正式报告，或前 3 个设计伙伴的全部正式报告，取覆盖更多者。
黄金期逐条审核。没有审核签字，不发布正式报告。审核人必须有 active `report_reviewer_assignments`，范围为 `report_review`，且 `expires_at` 未到；内部审核人不进入客户 `owner/admin/member` 列表。客户 owner/admin、报告创建人和 Claim owner 不得自审。审核结束后记录 assignment ID、审核版本和合同哈希。
Quick 2 小时稿不审核，不触发验收，不生成四态或 `confirmed`。Quick 24 小时正式版仍受 L3 上限约束。

- [ ] **Step 4: 稳定期风险分层**

必须审核：

- 所有进入结论；
- 所有标题数字；
- 所有跨市场比较；
- 所有风险 Claim。

其余证据抽检 20%–30%。抽检失败时整份报告回退全审。
审核后如修改 Claim、数字或证据，原签字失效，必须重新审核。

- [ ] **Step 5: Claim 审核**

逐条检查：

- Claim 有市场、时间窗、中英文文本、状态、证据等级、样本量、支持证据、反证、独立来源数、风险标记和审核状态；
- Quick Claim 不超过 `L3_live_single`，不出现 `confirmed`；
- Standard Claim 不超过证据上限；
- `L4_authorized_live` 只表示内部执行批准和数据门槛达标，不表示平台授权、法律许可、隐私认证或转售权；
- 关键判断至少 2 个独立原始记录簇；
- 同一 provider 的不同端点、同一端点的多次调用、同一页面的多条抓取路径、同一记录的翻译、转载、不同导出格式和两把不同 API Key 都只能算一个来源；
- 没有证据的 Claim 不进入正式报告；
- 医疗、健康、安全、法律或召回结论不进入首期交付。涉及儿童或未成年人风险提示时，第二人复核，且不标记 `confirmed`。

关键判断少于 2 个独立原始记录簇时，Claim 最高为 `directional`，市场不能输出 `enter` 或 `do_not_enter`，只能输出 `conditional_enter` 或 `insufficient_evidence`。

所有归因只描述共同出现、相关和描述性差异。不得写导致、驱动、提升、降低、造成、证明或其他因果含义。所有比较必须提供市场、时间窗、样本量、计数类型、证据等级和反证。不预测销量、市场份额、转化率或营收。

- [ ] **Step 6: 口径争议**

客户质疑指标或证据等级定义时：

1. 引用合同、报告合同和设计口径；
2. 5 个工作日内书面答复；
3. 未解决则记为 `major_definition_dispute=yes`；
4. D90 必须为 0。

- [ ] **Step 7: 校验质量台账**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/quality_ledger.csv", encoding="utf-8")))
for r in rows:
    assert r["market_quality_status"] in {"qualified","qualified_with_gap","not_qualified"}, r
    assert r["claim_evidence_binding_pct"] == "100", r
    assert r["claim_level_cap_ok"] == "yes", r
    assert r["independent_source_coverage_pct"] == "100", r
    assert r["independent_source_correct_pct"] == "100", r
    assert r["refresh_comparability_status"], r
    assert r["major_definition_dispute"] in {"yes","no"}, r
print("quality OK", len(rows))
'
```

预期：`quality OK`。任一硬指标不满足即失败。

- [ ] **Step 8: 校验不合格市场输出**

```bash
python3 -I -c '
import csv, json, os
root = os.environ.get("PG1_EVIDENCE_ROOT", os.path.expanduser("~/DIH-PG1-EVIDENCE"))
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/quality_ledger.csv", encoding="utf-8")))
for r in rows:
    path = os.path.join(root, "PG1", "imports", "report_contract_" + r["order_id"] + ".json")
    contract = json.load(open(path, encoding="utf-8"))
    market = next(m for m in contract["markets"] if m["market"] == r["market"])
    assert market["quality_status"] == r["market_quality_status"], (r["order_id"], r["market"], market["quality_status"], r["market_quality_status"])
    if r["market_quality_status"] != "not_qualified":
        continue
    if r["package_type"] == "Standard":
        assert market["conclusion_standard"] == "insufficient_evidence", (r["order_id"], r["market"], market["conclusion_standard"])
    else:
        assert market["conclusion_quick"] == "evidence_gap", (r["order_id"], r["market"], market["conclusion_quick"])
print("unqualified outputs OK")
'
```

预期：`unqualified outputs OK`。

报告合同的 `markets[]` 每个元素必须有 `quality_status`，并与质量台账的 `market_quality_status` 一致。Standard 的不合格市场读 `conclusion_standard`，必须为 `insufficient_evidence`；Quick 的不合格市场读 `conclusion_quick`，必须为 `evidence_gap`。报告合同 v1.1 的 `markets[]` 没有 `status` 字段，校验不得读取 `markets[].status`。

- [ ] **Step 9: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/quality_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record quality gates and claim audits"
```

---

### Task 11: 系统与合规硬门禁周检

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/incident_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Create: `$PG1_EVIDENCE_ROOT/PG1/audit_YYYY-Www.pdf`
- Create: `$PG1_EVIDENCE_ROOT/PG1/ledger_reconcile_YYYY-Www.pdf`
- Create: `$PG1_EVIDENCE_ROOT/PG1/compliance_register_YYYY-MM.pdf`

**Interfaces:**
- Consumes: 审计导出、账本对账、DPA 台账、来源权利矩阵、PII 扫描、LLM 披露。
- Produces: `check_id`、`result`、`incident_id`。

- [ ] **Step 1: 运行 13 项周检**

| check_type | 指标 | 阈值 | 证据 |
|---|---|---|---|
| `cross_workspace_leak` | 成功跨工作区访问次数 | 0 | 审计导出 |
| `demo_workspace_fallback` | 客户订单在演示工作区执行次数 | 0 | 运行元数据 |
| `ledger_imbalance` | 账本差异 USD | 0.00 | 对账报告 |
| `duplicate_settlement` | 重复结算次数 | 0 | 账本查询 |
| `idempotent_double_billing` | 同一幂等键重复计费次数 | 0 | 订单和支付查询 |
| `over_budget_execution` | 预算耗尽后继续执行步骤数 | 0 | 运行和账本查询 |
| `missing_audit` | 关键操作缺少审计事件数 | 0 | 审计覆盖报告 |
| `dpa_coverage` | 已签 DPA 伙伴 / 付费伙伴 | 100% | 合同台账 |
| `subprocessor_coverage` | 接受当前子处理者清单伙伴 / 付费伙伴 | 100% | 证据 |
| `source_rights_coverage` | 有书面权利来源 / 已交付来源 | 100% | 权利矩阵 |
| `cookie_exposure` | 客户链含 `creator_cookie` 记录数 | 0 | 配置和审计 |
| `pii_publication` | PII 扫描失败仍发布产物数 | 0 | 扫描报告 |
| `llm_disclosure` | 接受 LLM 披露伙伴 / 付费伙伴 | 100% | 证据 |

- [ ] **Step 2: 记录周检**

每个 `week × check_type` 一行。`week` 用 ISO 周，例如 `2026-W44`。
`result=pass/fail/blocked`。`owner` 写实际负责人。
测试或演练行在 `notes` 写 `synthetic=yes`。
分母为 0 时写 `value=0/0`，`result=pass`，`notes=no denominator`。这表示试点尚无付费伙伴或尚无可检查对象。

- [ ] **Step 3: 处理失败**

任一项 `fail`：

1. 开 `incident_ledger.csv`；
2. 立即停止受影响范围；
3. 保全证据；
4. 按合同通知客户；
5. 整改并复检；
6. 记录根因和纠正动作。

事件描述只写伙伴 ID、影响范围和证据 ID，不写个人数据。

任何一次 confirmed 非零即该硬门禁失败。测试或演练必须使用合成工作区，不计入生产指标。

- [ ] **Step 4: 合规覆盖检查**

每个付费伙伴必须有：

- 已签 DPA；
- 当前子处理者清单接受记录；
- LLM 披露接受记录；
- 数据来源书面权利覆盖记录；
- 无客户链 Cookie；
- PII 扫描通过。

来源权利必须覆盖：派生交付、Agency 分享、缓存、存储、署名和查询数据的使用方式。
TikHub DPA 不等于数据转售授权。

每月核对保留策略执行：原始响应 30 天、标准化数据集 12 个月、正式报告和交付包 24 个月、运行日志 180 天、安全与访问审计 24 个月、备份 30 天。保留期变更必须经过合同和法务流程。

数据不得跨客户复用。匿名行业基准只能由客户单独书面 opt-in，并达到足够聚合客户数量，避免反推出单一客户数据。

内部访问默认没有常驻客户数据权限。报告审核只访问已分配报告、Claim 和证据；常规支持需要工单和客户批准，范围限于指定项目、只读、限时；工程排障需要事件负责人批准，并优先使用日志和元数据；紧急访问需要双人批准、立即告警和最小范围；销售演示使用独立销售工作区，只允许合成数据。所有访问记录工单、理由、范围、开始和结束时间。紧急访问结束后轮换相关凭据并复盘。

审计事件只追加，防修改，防删除。审计不记录明文密钥、Cookie、盐和原始个人数据。审计带工作区、项目、主体、请求和结果。审计形成可验证哈希链，链锚保存在独立防篡改存储。审计保留 24 个月，并支持客户导出本工作区记录。

审计事件至少覆盖：登录、登出、失败登录、角色变更；密钥签发、轮换、撤销、拒绝；预算调整、超额审批、阻断；订单和 run 的创建、取消、重试、终态；工具调用结果和耗时；导出、下载、访问、撤销；删除请求、执行、证明；内部审核、支持、紧急访问；子处理者、价格簿、目录、安全配置变化；备份和恢复演练。公共分享在 PG1 期间延后，不创建分享链接；分享链接创建数和撤销数均为 0，不产生分享审计事件。

LLM 供应商必须有零保留和禁止训练书面条款。只发送伪名化、最小化摘录。不发送完整数据集、联系方式、Cookie、密钥和原始身份。输出只作为草稿。不建立跨客户上下文、提示词复用或嵌入复用。供应商列入子处理者清单。条款不满足时关闭 LLM，不静默切换其他模型。

- [ ] **Step 5: 校验周检完整性**

```bash
python3 -I -c '
import csv
from collections import defaultdict
rows = [r for r in csv.DictReader(open("docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv", encoding="utf-8")) if "synthetic=yes" not in (r.get("notes") or "")]
required = {"cross_workspace_leak","demo_workspace_fallback","ledger_imbalance","duplicate_settlement","idempotent_double_billing","over_budget_execution","missing_audit","dpa_coverage","subprocessor_coverage","source_rights_coverage","cookie_exposure","pii_publication","llm_disclosure"}
by_week = defaultdict(set)
for r in rows:
    by_week[r["week"]].add(r["check_type"])
for week, got in by_week.items():
    assert required <= got, (week, required - got)
bad = [r["check_id"] for r in rows if r["result"] != "pass"]
assert not bad, bad
print("system/compliance OK", len(rows), "weeks", len(by_week))
'
```

预期：`system/compliance OK`。缺项或任一项非 `pass` 即失败。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv docs/ops/pg1-pilot/ledgers/incident_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record weekly system and compliance gates"
```

---

### Task 12: 支持与事件响应

**Files:**
- Modify: `docs/ops/pg1-pilot/ledgers/support_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/incident_ledger.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`

**Interfaces:**
- Consumes: `partner_id`、交付台账、事件台账。
- Produces: `ticket_id`、`first_response_hours`、`free_rework`、`resolution_hours`。

- [ ] **Step 1: 建立工单**

工单只记录：

- 伙伴 ID；
- 严重级别；
- 主题代码；
- 影响范围；
- 负责人。

工单不得包含密钥、Cookie、原始个人数据或完整客户数据。

- [ ] **Step 2: 定级**

| 级别 | 定义 | 首次响应 | 控制或解决目标 |
|---|---|---|---|
| S1 | 交付中断、安全、合规、跨工作区 | 1 工作小时 | 4 工作小时控制 |
| S2 | 质量问题、重大延迟、账务异常 | 4 工作小时 | 1 工作日出方案 |
| S3 | 使用问题、报告解释 | 1 工作日 | 3 工作日 |
| S4 | 增强请求 | 3 工作日 | 不承诺 |

- [ ] **Step 3: 响应和解决**

记录 `first_response_at`、`first_response_hours`、`resolved_at`、`resolution_hours`。
首次响应必须在 `response_target_hours` 内。

- [ ] **Step 4: 判断免费返工**

免费返工只适用于平台可控缺陷：

- 临时上游失败；
- 平台配置遗漏；
- 流水线字段完整率不足；
- 去重故障；
- 报告合同校验失败；
- 校验和错误。

以下不自动免费返工：

- 市场不在支持目录；
- 上游商业权利未确认；
- 真实空结果；
- 客户输入错误；
- 客户未提供约定授权；
- 数据本身不足。

事实错误免费纠正，不限次数。表达调整一轮。

- [ ] **Step 5: S1 升级**

S1 立即升级到 Pilot Owner、Security Lead 和 Legal / Compliance Lead。
同时开事件台账。事件关闭后复盘，并轮换相关凭据。

- [ ] **Step 6: 周度支持复盘**

每周统计：

- 首次响应达标率；
- 平均首次响应时间；
- 解决时间；
- 免费返工率；
- S1 数量。

目标：首次响应达标率 ≥90%；免费补证或重跑率 ≤20%。

- [ ] **Step 7: 校验支持台账**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/support_ledger.csv", encoding="utf-8")))
if rows:
    ok = sum(1 for r in rows if float(r["first_response_hours"]) <= float(r["response_target_hours"]))
    rate = ok / len(rows)
    print("first response rate", rate)
    assert rate >= 0.9, rate
print("tickets", len(rows))
'
```

预期：`first response rate` ≥ 0.9。无工单时按 100% 记，并在周报注明 `sample=0`。

- [ ] **Step 8: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/support_ledger.csv docs/ops/pg1-pilot/ledgers/incident_ledger.csv docs/ops/pg1-pilot/ledgers/evidence_index.csv
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record support tickets and incident response"
```

---

### Task 13: 周报

**Files:**
- Create: `docs/ops/pg1-pilot/weekly/YYYY-Www.md`
- Modify: `docs/ops/pg1-pilot/README.md`

**Interfaces:**
- Consumes: 全部台账。
- Produces: 13 份周报，周报数字可追溯到台账。

- [ ] **Step 1: 冻结数据**

每周四 23:59 Asia/Shanghai 冻结数据。周报只读台账，不手工改数。
数据截止后新增的行进入下一周。

- [ ] **Step 2: 取数**

从台账取以下数字：

- 实际付费伙伴数、活跃伙伴数；
- 已回款和未回款 USD；
- 管道阶段分布；
- 正式订单数、按时交付率、验收率、一次验收通过率、免费返工率；
- 第二任务和刷新数；
- 每个市场 × 包型的收入、成本、贡献毛利率；
- 质量状态、Claim 追溯、独立来源、口径争议；
- 系统与合规周检结果；
- 支持首次响应和工单数。

- [ ] **Step 3: 写周报**

```markdown
# O1 周报 YYYY-Www

- 数据截止：YYYY-MM-DD 23:59 Asia/Shanghai
- 编制：Pilot Ops
- 审核：Pilot Owner
- 状态：绿 / 黄 / 红

## 1. 结论与决策请求

- 本周结论：
- 需要决策：
- 决策截止：

## 2. 付费与回款

| 指标 | 本周 | 累计 | 目标 | 状态 |
|---|---:|---:|---:|---|
| 实际付费伙伴数 | | | 3–5 | |
| 活跃伙伴数 | | | ≥3 | |
| 已回款 USD | | | 100% | |
| 未回款 USD | | | 0 | |
| PG0 承诺转付费 | | | 不计入 | |

## 3. 管道

| partner_id | segment | 阶段 | 承诺类型 | 下一步 | 负责人 | 日期 |
|---|---|---|---|---|---|---|

## 4. 交付与验收

| 指标 | 本周 | 累计 | 目标 | 状态 |
|---|---:|---:|---:|---|
| 正式订单 | | | | |
| 按时交付率 | | | 100% | |
| 5 个工作日验收率 | | | 100% | |
| 一次验收通过率 | | | ≥70% | |
| 免费补证或重跑率 | | | ≤20% | |

## 5. 复购与刷新

| 指标 | 本周 | 累计 | 目标 | 状态 |
|---|---:|---:|---:|---|
| 第二任务伙伴数 | | | ≥2 | |
| 已交付刷新数 | | | ≥1 | |
| 刷新收入 USD | | | | |

## 6. 单位经济

| market | package | 收入 USD | 直接成本 USD | 贡献毛利 USD | 毛利率 | still_sold | 动作 |
|---|---|---:|---:|---:|---:|---|---|

## 7. 质量

| 市场 | 质量状态 | 商品/评论/达人 | Claim 追溯 | 独立来源 | 争议 |
|---|---|---|---|---|---|

## 8. 系统与合规

| 检查 | 本周结果 | 累计事件 | 状态 |
|---|---|---|---|

## 9. 支持

| 指标 | 本周 | 累计 | 目标 |
|---|---:|---:|---:|
| 工单数 | | | |
| 首次响应达标率 | | | ≥90% |
| 平均首次响应小时 | | | |
| S1 数量 | | | 0 |

## 10. 风险与行动

| 风险 | 等级 | 负责人 | 缓解 | 退出条件 | 复核日期 |
|---|---|---|---|---|---|

## 11. 下周计划

| 行动 | 负责人 | 截止日期 | 验收标准 |
|---|---|---|---|
```

- [ ] **Step 4: 审核和发布**

Pilot Owner 审核数字。周五 17:00 前发布。
发布后不改历史周报。更正写新周报，并注明更正原因。

- [ ] **Step 5: 校验周报结构**

```bash
WEEK=$(python3 -I -c "from datetime import date; y,w,_=date.today().isocalendar(); print(f'{y}-W{w:02d}')")
for h in '结论与决策请求' '付费与回款' '管道' '交付与验收' '复购与刷新' '单位经济' '质量' '系统与合规' '支持' '风险与行动' '下周计划'; do
  grep -q "## .*$h" "docs/ops/pg1-pilot/weekly/$WEEK.md" || { echo "missing $h"; exit 1; }
done
```

预期：全部标题存在。

- [ ] **Step 6: 提交**

```bash
git add docs/ops/pg1-pilot/weekly docs/ops/pg1-pilot/README.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): publish weekly pilot report"
```

---

### Task 14: D30 复盘

**Files:**
- Create: `docs/ops/pg1-pilot/reviews/D30.md`
- Modify: `docs/ops/pg1-pilot/README.md`

**Interfaces:**
- Consumes: D30 台账快照。
- Produces: D30 决策和行动项。

- [ ] **Step 1: 准备数据包**

D30 当天冻结台账。导出：

- 付费和回款；
- 管道；
- 交付和验收；
- 复购和刷新；
- 毛利；
- 质量；
- 系统与合规；
- 支持。

- [ ] **Step 2: 开复盘会**

参会：Pilot Owner、Sales Lead、Delivery Lead、Data Quality Lead、Finance Lead、Legal / Compliance Lead、Security Lead、Product Lead。

- [ ] **Step 3: 写复盘**

```markdown
# D30 复盘

- 日期：
- 参会：
- 数据截止：

## 1. 数据快照

| 指标 | 实际 | 目标 | 状态 |
|---|---:|---:|---|
| 实际付费伙伴 | | 3–5 | |
| 活跃伙伴 | | ≥3 | |
| 回款率 | | 100% | |
| 正式订单 | | | |
| 正式任务完成率 | | ≥90% | |
| 一次验收通过率 | | ≥70% | |
| 免费补证或重跑率 | | ≤20% | |
| 贡献毛利为负的仍在售组合 | | 0 | |

## 2. 门禁预判

| 类别 | 预判 | 依据 |
|---|---|---|

## 3. 偏差与原因

## 4. 决策

## 5. 行动项

| 行动 | 负责人 | 截止日期 | 验收标准 |
|---|---|---|---|

## 6. 签字
```

- [ ] **Step 4: 触发规则**

- 实际付费少于 2：Pilot Owner 亲自负责前 5 个机会，销售管道每周复盘两次。
- 正式任务完成率低于 90%：暂停新订单，直到修复。
- 任一项系统或合规周检失败：立即停止受影响范围。
- D30 不作 Go/No-Go 结论。

- [ ] **Step 5: 校验并提交**

```bash
test -f docs/ops/pg1-pilot/reviews/D30.md
grep -q '## 5. 行动项' docs/ops/pg1-pilot/reviews/D30.md
git add docs/ops/pg1-pilot/reviews/D30.md docs/ops/pg1-pilot/README.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record D30 pilot review"
```

---

### Task 15: D60 复盘

**Files:**
- Create: `docs/ops/pg1-pilot/reviews/D60.md`
- Modify: `docs/ops/pg1-pilot/README.md`

**Interfaces:**
- Consumes: D60 台账快照。
- Produces: 门禁预判、整改计划、延期风险清单。

- [ ] **Step 1: 准备数据包**

D60 当天冻结以下台账，并保存读取时间与操作者：

- `partner_ledger.csv`：实际付费伙伴、活跃伙伴、第二任务伙伴数；
- `payment_ledger.csv`：已开票、已回款、应收账龄；
- `order_ledger.csv`：正式订单、包型、市场、预算；
- `delivery_ledger.csv`：完成率、一次验收通过率、免费补证或重跑率；
- `refresh_ledger.csv`：复购、刷新与可比性；
- `margin_ledger.csv`：贡献毛利和仍在售负毛利组合；
- `quality_ledger.csv`：逐市场质量、Claim 审核与证据等级；
- `system_compliance_ledger.csv`：13 项系统与合规周检；
- `support_ledger.csv` 与 `incident_ledger.csv`：首次响应、S1/S2 事件和关闭状态；
- `evidence_index.csv`：以上指标对应的证据 ID、访问级别和 SHA-256。

为 28 个硬门禁分别准备当前预判：`pass`、`at risk` 或 `fail`。每条预判必须写 `gate_id`、证据 ID、负责人和 D90 前复核日期。不得只引用 D30 快照。

- [ ] **Step 2: 开复盘会**

参会：Pilot Owner、Sales Lead、Delivery Lead、Data Quality Lead、Finance Lead、Legal / Compliance Lead、Security Lead、Product Lead。会议开始前，Pilot Owner 逐项确认上述角色已到会；缺任一硬门禁 owner 时，只能记录延期风险，不能把对应预判写为 `pass`。

- [ ] **Step 3: 写复盘**

```markdown
# D60 复盘

- 日期：
- 参会：
- 数据截止：

## 1. 数据快照

## 2. 硬门禁预判

| gate_id | 类别 | 预判 | 依据 | 整改负责人 | 复核日期 |
|---|---|---|---|---|---|

## 3. 商业预测

| 指标 | 当前 | D90 预测 | 置信度 | 行动 |
|---|---:|---:|---|---|

## 4. 延期风险

- 可能缺少的证据：
- 负责人：
- 复核日期：

## 5. 决策

## 6. 行动项

| 行动 | 负责人 | 截止日期 | 验收标准 |
|---|---|---|---|

## 7. 签字
```

- [ ] **Step 4: 触发规则**

- 实际付费少于 3，或第二任务少于 1：升级到 Executive Sponsor，评估提前 No-Go。
- 任一硬门禁预判为 `fail`：启动停止或整改，不等到 D90。
- 证据缺口：列入延期风险清单，但不在 D60 批准延期。
- D60 不作最终 Go/No-Go 结论。

- [ ] **Step 5: 校验并提交**

```bash
test -f docs/ops/pg1-pilot/reviews/D60.md
grep -q '## 2. 硬门禁预判' docs/ops/pg1-pilot/reviews/D60.md
git add docs/ops/pg1-pilot/reviews/D60.md docs/ops/pg1-pilot/README.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): record D60 pilot review"
```

---

### Task 16: D90 评审与 PG1 决议

**Files:**
- Create: `docs/ops/pg1-pilot/decisions/D90-ledgers.sha256`
- Modify: `docs/ops/pg1-pilot/ledgers/pg1_gate_register.csv`
- Modify: `docs/ops/pg1-pilot/ledgers/extension_ledger.csv`
- Create: `docs/ops/pg1-pilot/decisions/PG1-decision.md`
- Create: `docs/ops/pg1-pilot/reviews/D90.md`
- Create: `docs/ops/pg1-pilot/decisions/extension-01.md`，仅在延期时创建

**Interfaces:**
- Consumes: 全部台账和证据索引。
- Produces: 28 条门禁结论、PG1 决议、延期决议。

- [ ] **Step 1: 冻结 D90 数据**

```bash
(cd docs/ops/pg1-pilot && shasum -a 256 ledgers/*.csv > decisions/D90-ledgers.sha256 && shasum -a 256 -c decisions/D90-ledgers.sha256)
test "$(find docs/ops/pg1-pilot/weekly -name '*.md' | wc -l | tr -d ' ')" -ge 13
```

预期：全部 `OK`，周报至少 13 份。冻结后台账只读。任何更正写新行，并重新生成校验和。

- [ ] **Step 2: 生成 28 条门禁登记**

`pg1_gate_register.csv` 必须有以下 28 行。`verdict` 在评审时填写。

```csv
gate_id,category,gate_text,threshold,source_ledger,source_query,owner,verdict,evidence_ids,reviewed_at,notes
PG1-COM-01,commercial,3–5 家实际付费,3 <= count(actual_paid=yes) <= 5,partner_ledger,count paid_contract,Sales Lead,,,,
PG1-COM-02,commercial,至少 3 家活跃,count(active_30d=yes) >= 3,partner_ledger,count active,Sales Lead,,,,
PG1-COM-03,commercial,至少 2 家购买第二任务或刷新,count(partner with >=2 paid orders or >=1 delivered refresh) >= 2,order_ledger;refresh_ledger,repeat count,Sales Lead,,,,
PG1-COM-04,commercial,回款率 100%,sum(amount_paid_usd)=sum(amount_due_usd) and no open invoice,payment_ledger,collection check,Finance Lead,,,,
PG1-COM-05,commercial,企业采购准入在实际付费伙伴全部完成,100% of paid partners,partner_ledger,enterprise_clearance=yes,Sales Lead,,,,
PG1-ECO-01,economic,所有仍在售市场与包型贡献毛利不为负,all still_sold=yes rows margin >= 0,margin_ledger,margin check,Finance Lead,,,,
PG1-PRD-01,product,正式任务完成率 ≥90%,completed_formal / formal_orders >= 0.90,delivery_ledger,completion rate,Delivery Lead,,,,
PG1-PRD-02,product,5 个工作日内完成验收或进入明确异议,100% of formal deliveries,delivery_ledger,acceptance clock,Delivery Lead,,,,
PG1-PRD-03,product,至少 2 家购买第二个任务或刷新,count >= 2,order_ledger;refresh_ledger,repeat count,Delivery Lead,,,,
PG1-QLT-01,quality,每个约定市场有质量状态,100%,quality_ledger,status completeness,Data Quality Lead,,,,
PG1-QLT-02,quality,不合格市场正确输出证据不足,100%,quality_ledger;report contracts,quality_status + conclusion_standard/conclusion_quick check,Data Quality Lead,,,,
PG1-QLT-03,quality,正式 Claim 追溯率 100%,traced/formal = 100%,quality_ledger,claim traceability,Data Quality Lead,,,,
PG1-QLT-04,quality,Claim 等级不超过证据上限 100%,100%,quality_ledger,claim_level_cap_ok=yes,Data Quality Lead,,,,
PG1-QLT-05,quality,关键 Claim 独立来源判定覆盖率和正确率 100%,100%,quality_ledger,independent source check,Data Quality Lead,,,,
PG1-QLT-06,quality,刷新可比性状态完整 100%,100%,quality_ledger;refresh_ledger,comparability completeness,Data Quality Lead,,,,
PG1-QLT-07,quality,重大口径争议 0,0,quality_ledger;support_ledger,support and quality check,Data Quality Lead,,,,
PG1-SYS-01,system,跨工作区泄露 0,0,system_compliance_ledger,cross_workspace_leak,Security Lead,,,,
PG1-SYS-02,system,客户执行回退演示工作区 0,0,system_compliance_ledger,demo_workspace_fallback,Security Lead,,,,
PG1-SYS-03,system,账本不平 0,0,system_compliance_ledger,ledger_imbalance,Finance Lead,,,,
PG1-SYS-04,system,重复结算 0,0,system_compliance_ledger,duplicate_settlement,Finance Lead,,,,
PG1-SYS-05,system,幂等重复计费 0,0,system_compliance_ledger,idempotent_double_billing,Finance Lead,,,,
PG1-SYS-06,system,超预算继续执行 0,0,system_compliance_ledger,over_budget_execution,Security Lead,,,,
PG1-SYS-07,system,关键操作缺少审计 0,0,system_compliance_ledger,missing_audit,Security Lead,,,,
PG1-CMP-01,compliance,DPA 和子处理者覆盖 100%,100%,system_compliance_ledger,dpa and subprocessor coverage,Legal / Compliance Lead,,,,
PG1-CMP-02,compliance,数据源书面权利覆盖 100%,100%,system_compliance_ledger,source_rights_coverage,Legal / Compliance Lead,,,,
PG1-CMP-03,compliance,客户链 Cookie 暴露 0,0,system_compliance_ledger,cookie_exposure,Security Lead,,,,
PG1-CMP-04,compliance,PII 违规发布 0,0,system_compliance_ledger,pii_publication,Data Quality Lead,,,,
PG1-CMP-05,compliance,LLM 处理方式披露并客户接受 100%,100%,system_compliance_ledger,llm_disclosure,Legal / Compliance Lead,,,,
```

- [ ] **Step 3: 校验商业硬门禁**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
from collections import Counter
partners = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/partner_ledger.csv", encoding="utf-8")))
paid = [r for r in partners if r["actual_paid"] == "yes" and r["commitment_type"] == "paid_contract"]
assert 3 <= len(paid) <= 5, len(paid)
active = [r for r in paid if r["active_30d"] == "yes"]
assert len(active) >= 3, len(active)
assert all(r["enterprise_clearance"] == "yes" for r in paid), [r["partner_id"] for r in paid if r["enterprise_clearance"] != "yes"]
orders = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/order_ledger.csv", encoding="utf-8")))
refreshes = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/refresh_ledger.csv", encoding="utf-8")))
paid_status = {"approved","running","delivered","accepted"}
order_counts = Counter(r["partner_id"] for r in orders if r["status"] in paid_status)
refresh_counts = Counter(r["partner_id"] for r in refreshes if r["status"] == "delivered")
repeat = [p["partner_id"] for p in paid if order_counts[p["partner_id"]] >= 2 or refresh_counts[p["partner_id"]] >= 1]
assert len(repeat) >= 2, repeat
payments = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/payment_ledger.csv", encoding="utf-8")))
due = sum(D(r["amount_due_usd"] or "0") for r in payments)
collected = sum(D(r["amount_paid_usd"] or "0") for r in payments)
assert due == collected, (due, collected)
assert all(r["collection_status"] == "collected" for r in payments if r["amount_due_usd"]), [r["payment_id"] for r in payments if r["collection_status"] != "collected"]
collected_partners = {r["partner_id"] for r in payments if r["collection_status"] == "collected" and D(r["amount_paid_usd"] or "0") > 0}
assert all(p["partner_id"] in collected_partners for p in paid), [p["partner_id"] for p in paid if p["partner_id"] not in collected_partners]
print("commercial PASS", len(paid), len(active), len(repeat))
'
```

预期：`commercial PASS`。

- [ ] **Step 4: 校验经济硬门禁**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/margin_ledger.csv", encoding="utf-8")))
bad = [r["margin_id"] for r in rows if r["still_sold"] == "yes" and D(r["contribution_margin_usd"]) < 0]
assert not bad, bad
print("economic PASS")
'
```

预期：`economic PASS`。

- [ ] **Step 5: 校验产品硬门禁**

```bash
python3 -I -c '
import csv
from datetime import date, timedelta

def add_business_days(start, n):
    d = start
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d

rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/delivery_ledger.csv", encoding="utf-8")))
formal = [r for r in rows if r["formal_delivered_at"]]
completed = [r for r in formal if r["delivery_status"] in {"accepted","deemed_accepted"}]
rate = len(completed) / len(formal) if formal else 0
assert rate >= 0.90, rate
for r in formal:
    assert r["acceptance_start"] and r["acceptance_end"], r
    start = date.fromisoformat(r["formal_delivered_at"][:10])
    end = date.fromisoformat(r["acceptance_end"][:10])
    assert end >= add_business_days(start, 5), r
    if r["acceptance_result"] in {"objection_open","objection_upheld","objection_rejected"}:
        assert r["objection_items"], r
print("product PASS", rate)
'
```

预期：`product PASS`。

- [ ] **Step 6: 校验质量硬门禁**

```bash
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/quality_ledger.csv", encoding="utf-8")))
for r in rows:
    assert r["market_quality_status"] in {"qualified","qualified_with_gap","not_qualified"}, r
    assert r["claim_evidence_binding_pct"] == "100", r
    assert r["claim_level_cap_ok"] == "yes", r
    assert r["independent_source_coverage_pct"] == "100", r
    assert r["independent_source_correct_pct"] == "100", r
    assert r["refresh_comparability_status"], r
    assert r["major_definition_dispute"] == "no", r
    assert int(r["traced_claim_count"]) == int(r["formal_claim_count"]), r
print("quality PASS")
'
```

预期：`quality PASS`。

再运行 Task 10 Step 8 的不合格市场输出检查。两份结果都通过，质量硬门禁才通过。

- [ ] **Step 7: 校验系统与合规硬门禁**

```bash
python3 -I -c '
import csv
from decimal import Decimal as D
rows = [r for r in csv.DictReader(open("docs/ops/pg1-pilot/ledgers/system_compliance_ledger.csv", encoding="utf-8")) if "synthetic=yes" not in (r.get("notes") or "")]
bad = [r["check_id"] for r in rows if r["result"] != "pass"]
assert not bad, bad
zero_types = {"cross_workspace_leak","demo_workspace_fallback","ledger_imbalance","duplicate_settlement","idempotent_double_billing","over_budget_execution","missing_audit","cookie_exposure","pii_publication"}
for r in rows:
    if r["check_type"] in zero_types:
        assert D(r["value"] or "0") == 0, r
required = {"cross_workspace_leak","demo_workspace_fallback","ledger_imbalance","duplicate_settlement","idempotent_double_billing","over_budget_execution","missing_audit","dpa_coverage","subprocessor_coverage","source_rights_coverage","cookie_exposure","pii_publication","llm_disclosure"}
for check in required:
    assert any(r["check_type"] == check for r in rows), check
weeks = {r["week"] for r in rows}
assert len(weeks) >= 13, len(weeks)
print("system and compliance PASS")
'
```

预期：`system and compliance PASS`。

- [ ] **Step 8: 填写门禁结论**

逐行填写 `pg1_gate_register.csv`：

- `verdict=pass`：证据完整，指标达标；
- `verdict=fail`：明确不达标；
- `verdict=insufficient_evidence`：证据缺失或不可解析；
- `verdict=not_applicable`：只用于确实不适用的门禁，必须写理由。

`verdict=pass` 必须有 `evidence_ids`。`reviewed_at` 必填。

- [ ] **Step 9: 延期决策**

```text
任一 gate = fail
  -> No-Go。不得延期。

存在 gate = insufficient_evidence，且没有 gate = fail
  -> 指导委员会可以批准一次 30 天延期。
  -> 延期必须写：缺少的证据、负责人、复核日期。
  -> 记录 EXT-01，D120 = D90 + 30 天。
  -> 延期只补证据，不延长销售目标，不新增范围。

没有申请延期
  -> 按当前证据决议。证据不足即 No-Go。

D120 仍为 insufficient_evidence
  -> No-Go。不得第二次延期。
```

延期决议写入 `decisions/extension-01.md`：

```markdown
# EXT-01 延期决议

- 决议：批准 / 拒绝
- 原 D90：YYYY-MM-DD
- 复核 D120：YYYY-MM-DD
- 最长延期：30 天
- 触发门禁：
- 缺少的证据：
- 负责人：
- 复核日期：
- 延期期间允许的动作：
- 延期期间禁止的动作：新增销售目标、新增模板、新增品类、新增正式市场
- 签字：
```

- [ ] **Step 10: 开 D90 评审会**

参会和签字：Pilot Owner、Sales Lead、Delivery Lead、Data Quality Lead、Finance Lead、Legal / Compliance Lead、Security Lead、Product Lead、Executive Sponsor。
任一必须签字人缺席，决议无效。

`reviews/D90.md` 使用以下结构：

```markdown
# D90 复盘

- 日期：
- 参会：
- 数据截止：

## 1. 数据快照

| 指标 | 实际 | 目标 | 状态 |
|---|---:|---:|---|
| 实际付费伙伴 | | 3–5 | |
| 活跃伙伴 | | ≥3 | |
| 回款率 | | 100% | |
| 正式任务完成率 | | ≥90% | |
| 贡献毛利为负的仍在售组合 | | 0 | |

## 2. 28 条硬门禁结果

| 类别 | pass | fail | insufficient_evidence | not_applicable |
|---|---:|---:|---:|---:|
| 商业 | | | | |
| 经济 | | | | |
| 产品 | | | | |
| 质量 | | | | |
| 系统 | | | | |
| 合规 | | | | |

## 3. 预警指标

## 4. 商业结论

## 5. 偏差与原因

## 6. 延期判断

- 是否需要延期：
- 缺少证据：
- 负责人：
- 复核日期：

## 7. 决议建议

## 8. 签字
```

- [ ] **Step 11: 写 PG1 决议**

```markdown
# PG1 决议

- 日期：
- 数据截止：
- 台账校验和：`decisions/D90-ledgers.sha256`
- 决议：Go / Conditional Go / No-Go

## 1. 硬门禁

| gate_id | 类别 | 门禁 | 阈值 | 结果 | 证据 |
|---|---|---|---|---|---|

## 2. 预警指标

| 指标 | D0 阈值 | 实际 | 结果 | 复核人 |
|---|---:|---:|---|---|

## 3. 延期

- 是否延期：
- 缺少证据：
- 负责人：
- 复核日期：
- 延期后天数：

## 4. 条件与整改

| 条件 | 负责人 | 复核门禁 | 截止日期 |
|---|---|---|---|

## 5. 范围声明

- 不自动进入 P2。
- 不新增模板、品类或正式市场。
- 不卖裸 API，不按调用次数计费。
- 不接受客户 Cookie。

## 6. 异议

- 异议人：
- 异议内容：
- 处理：

## 7. 签字

| 角色 | 姓名 | 签字 | 日期 |
|---|---|---|---|
| Pilot Owner | | | |
| Sales Lead | | | |
| Delivery Lead | | | |
| Data Quality Lead | | | |
| Finance Lead | | | |
| Legal / Compliance Lead | | | |
| Security Lead | | | |
| Product Lead | | | |
| Executive Sponsor | | | |
```

- [ ] **Step 12: 校验决议**

```bash
test -f docs/ops/pg1-pilot/decisions/PG1-decision.md
grep -qE '^[- ]*决议：(Go|Conditional Go|No-Go)[[:space:]]*$' docs/ops/pg1-pilot/decisions/PG1-decision.md
python3 -I -c '
import csv
rows = list(csv.DictReader(open("docs/ops/pg1-pilot/ledgers/pg1_gate_register.csv", encoding="utf-8")))
assert len(rows) >= 28, len(rows)
assert all(r["verdict"] in {"pass","fail","insufficient_evidence","not_applicable"} for r in rows), [r["gate_id"] for r in rows if r["verdict"] not in {"pass","fail","insufficient_evidence","not_applicable"}]
assert all(r["evidence_ids"] for r in rows if r["verdict"] == "pass"), [r["gate_id"] for r in rows if r["verdict"] == "pass" and not r["evidence_ids"]]
print("gate register OK", len(rows))
'
```

预期：决议存在，28 条门禁全部有结论，`pass` 有证据。

- [ ] **Step 13: 提交**

```bash
git add docs/ops/pg1-pilot/ledgers/pg1_gate_register.csv docs/ops/pg1-pilot/ledgers/extension_ledger.csv docs/ops/pg1-pilot/decisions docs/ops/pg1-pilot/reviews/D90.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): freeze D90 evidence and record PG1 decision"
```

- [ ] **Step 14: 执行决议**

- Go 或 Conditional Go：只允许提出 P2 方案。不得自动进入 P2。
- Conditional Go：列出整改负责人和复核门禁。不得豁免硬门禁。
- No-Go：停止新增付费订单，执行 Task 17 收尾。按合同退款或抵扣。
- 延期：按 `extension-01.md` 执行，D120 重新评审。

---

### Task 17: 收尾与归档

**Files:**
- Create: `docs/ops/pg1-pilot/decisions/closeout.md`
- Modify: `docs/ops/pg1-pilot/ledgers/evidence_index.csv`
- Modify: `docs/ops/pg1-pilot/README.md`

**Interfaces:**
- Consumes: PG1 决议、全部台账、证据索引。
- Produces: 收尾记录、保留和删除证明、P2 移交或停止记录。

- [ ] **Step 1: 冻结最终台账**

```bash
(cd docs/ops/pg1-pilot && shasum -a 256 ledgers/*.csv > decisions/final-ledgers.sha256 && shasum -a 256 -c decisions/final-ledgers.sha256)
```

预期：全部 `OK`。

- [ ] **Step 2: 处理访问**

按 PG1 决议处理：

- No-Go：撤销全部客户项目密钥，关闭或冻结工作区。公共分享在 PG1 期间延后：不创建分享链接，撤销为 no-op，创建数和撤销数均为 0。
- Go 或 Conditional Go：保留实际付费伙伴的生产密钥和工作区，直到 P2 决议或合同结束。只撤销测试、试用和离职人员密钥。分享链接同为延后项，创建 0、撤销 0。

记录密钥撤销审计事件和分享链接延后记录。密钥撤销后，新请求必须立即失败。

- [ ] **Step 3: 保留和删除**

| 数据 | 保留期 |
|---|---:|
| 原始响应 | 30 天 |
| 标准化数据集 | 12 个月 |
| 正式报告和交付包 | 24 个月 |
| 运行日志 | 180 天 |
| 安全与访问审计 | 24 个月 |
| 备份 | 30 天 |

删除流程：

1. owner 发起并二次确认；admin 可以发起申请；
2. 检查法律保留、合同争议和安全事件；
3. 撤销密钥；公共分享延后，不创建分享链接，撤销调用为 no-op，记录创建数 0、撤销数 0；
4. 删除活跃业务数据或写 tombstone；
5. 清理缓存、搜索索引和临时文件；
6. 向子处理者发删除请求并保存回执；
7. 备份 30 天内自然过期；
8. 生成删除证明和审计事件。

DSR 流程：接收请求 → 核验身份与授权 → 确认 controller/processor 责任 → 在当前工作区内定位数据 → 执行访问、更正、限制或删除 → 通知子处理者 → 生成审计和结案记录。不得跨工作区搜索或使用伪名 ID 关联其他客户数据。

账本、审计、证据等级和审核记录不能因业务数据删除而硬删。只保留最小元数据。

对外声称备份保留 30 天前，必须完成数据库和对象存储备份、加密、保留任务、恢复演练、删除重放验证、法律保留恢复和 RPO/RTO 实测。两套生产只有在故障域、数据复制、切换和恢复验证后才能称为灾备。

- [ ] **Step 4: 归档证据**

- 每个伙伴目录生成 `SHA256SUMS`；
- 校验全部证据；
- 把最终证据索引写入 `evidence_index.csv`；
- 证据库只读存档。

```bash
for d in "$PG1_EVIDENCE_ROOT"/P-*; do
  (cd "$d" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS && shasum -a 256 -c SHA256SUMS)
done
```

预期：每个伙伴目录全部 `OK`。

- [ ] **Step 5: 写收尾记录**

```markdown
# O1 收尾记录

- 日期：
- PG1 决议：Go / Conditional Go / No-Go
- 实际付费伙伴数：
- 已回款 USD：
- 未关闭事项：
- 客户通知：
- 退款或抵扣：
- 密钥撤销：
- 分享链接：公共分享延后，创建数 0、撤销数 0
- 工作区关闭：
- 证据归档位置：
- 证据校验和：
- P2 移交：是 / 否
- 停止原因：

## 经验

## 未解决风险

## 签字
```

- [ ] **Step 6: 移交或停止**

- Go 或 Conditional Go：向 P2 负责人移交台账、证据和整改清单。P2 必须另行提案和批准。
- No-Go：停止付费业务。按合同处理退款、抵扣和终止。保留证据 24 个月。

- [ ] **Step 7: 校验并提交**

```bash
test -f docs/ops/pg1-pilot/decisions/closeout.md
grep -q '分享链接：公共分享延后，创建数 0、撤销数 0' docs/ops/pg1-pilot/decisions/closeout.md
if grep -RInE '(sk-[A-Za-z0-9]{20,}|Bearer [A-Za-z0-9._-]{20,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)' docs/ops/pg1-pilot; then
  echo "sensitive material found"
  exit 1
fi
if grep -RInE 'T[B]D|T[O]DO|待[填]|待[补]|FIX[M]E|XX[X]' docs/ops/pg1-pilot; then
  echo "placeholder found"
  exit 1
fi
git add docs/ops/pg1-pilot/decisions/closeout.md docs/ops/pg1-pilot/decisions/final-ledgers.sha256 docs/ops/pg1-pilot/ledgers/evidence_index.csv docs/ops/pg1-pilot/README.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(pg1): close out pilot and archive evidence"
```

---

## 附录 A：PG1 硬门禁追溯矩阵

| 设计要求 | 指标 | 证据 | 门禁 | 任务 |
|---|---|---|---|---|
| 3–5 家实际付费 | `actual_paid=yes` 且 `commitment_type=paid_contract` | 合同、银行回单、订单 | PG1-COM-01 | Task 2–Task 4 |
| 至少 3 家活跃 | `active_30d=yes` | 交付或未关闭订单 | PG1-COM-02 | Task 7 |
| 至少 2 家第二任务或刷新 | 第二订单或已交付刷新 | 订单、刷新台账 | PG1-COM-03、PG1-PRD-03 | Task 8 |
| 回款率 100% | 应收 USD = 已收 USD | 开票、银行回单 | PG1-COM-04 | Task 4 |
| 企业采购准入 100% | `enterprise_clearance=yes` | 采购材料包 | PG1-COM-05 | Task 3 |
| 贡献毛利不为负 | `contribution_margin_usd >= 0` | run 账本、财务包 | PG1-ECO-01 | Task 9 |
| 正式任务完成率 ≥90% | 完成正式交付 / 正式订单 | 交付台账 | PG1-PRD-01 | Task 7 |
| 5 个工作日验收 | 验收截止日 | 交付台账 | PG1-PRD-02 | Task 7 |
| 每个市场有质量状态 | `market_quality_status` 非空 | 质量台账 | PG1-QLT-01 | Task 10 |
| 不合格市场输出证据不足 | 报告合同 `quality_status` 与包型 conclusion 字段 | 报告合同 | PG1-QLT-02 | Task 10 |
| Claim 追溯率 100% | 已追溯 / 正式 Claim | 报告合同、质量台账 | PG1-QLT-03 | Task 10 |
| Claim 等级不超上限 | `claim_level_cap_ok=yes` | 质量台账 | PG1-QLT-04 | Task 10 |
| 独立来源覆盖和正确 100% | 两个独立来源字段 | 质量台账 | PG1-QLT-05 | Task 10 |
| 刷新可比性完整 100% | `comparability_status` 非空 | 刷新、质量台账 | PG1-QLT-06 | Task 8、Task 10 |
| 重大口径争议 0 | `major_definition_dispute=no` | 质量、支持台账 | PG1-QLT-07 | Task 10 |
| 系统七项为 0 | 7 个 check_type | 周检、审计、对账 | PG1-SYS-01–07 | Task 11 |
| 合规五项覆盖 | 5 个 check_type | DPA、权利、扫描、披露 | PG1-CMP-01–05 | Task 11 |
| 支持首次响应 ≥90% | 响应达标率 | 支持台账 | 预警指标 | Task 12 |
| 免费补证或重跑 ≤20% | 免费返工 / 正式订单 | 交付台账 | 预警指标 | Task 7、Task 12 |
| 13 份周报 | 每周五发布 | `weekly/` | 过程要求 | Task 13 |
| 30/60/90 复盘 | 三份复盘 | `reviews/` | 过程要求 | Task 14–Task 16 |
| 一次 30 天延期 | EXT-01 | 延期台账、决议 | 过程要求 | Task 16 |
| Go/Conditional/No-Go | 决议文件 | `decisions/PG1-decision.md` | PG1 | Task 16 |

## 附录 B：证据类型与访问级别

| artifact_type | 证明 | access_class |
|---|---|---|
| `pg0_decision` | PG0 PASS | legal |
| `pg0_handoff` | O0 证据索引 | legal |
| `pg0_signoff` | 六方签核 | legal |
| `pg0_gate_matrix` | 11 项 PG0 门禁 | legal |
| `feature_flag_release` | 功能开关发布记录 | security |
| `stop_rollback_rehearsal` | 停止与回退演练 | security |
| `signed_contract` | 合同签署 | commercial |
| `dpa_acceptance` | DPA 接受 | legal |
| `subprocessor_ack` | 子处理者清单接受 | legal |
| `llm_disclosure_ack` | LLM 披露接受 | legal |
| `enterprise_pack` | 企业采购材料包 | legal |
| `invoice` | 开票 | finance |
| `bank_receipt` | 到账 | finance |
| `workspace_provisioning` | 工作区、项目、角色 | security |
| `key_issuance` | 密钥签发、撤销 | security |
| `boundary_test` | 边界测试 | security |
| `quote` | 报价 | commercial |
| `order_confirmation` | 订单创建 | commercial |
| `report_contract` | 报告合同 | quality |
| `delivery_manifest` | 交付清单 | quality |
| `acceptance_record` | 验收或异议 | quality |
| `quality_scorecard` | 质量记分卡 | quality |
| `claim_evidence_index` | Claim 证据索引 | quality |
| `run_ledger_export` | 成本账本 | finance |
| `finance_pack` | 财务月度关账包 | finance |
| `audit_export` | 审计 | security |
| `system_check_report` | 系统硬门禁 | security |
| `compliance_register` | 合规覆盖 | legal |
| `support_ticket_export` | 支持 | commercial |
| `weekly_report` | 周报 | commercial |
| `review_minutes` | 复盘 | commercial |
| `pg1_decision` | 最终决议 | legal |

## 附录 C：D90 数据校验顺序

按以下顺序执行，每一步失败就停止，不进入决议：

1. `decisions/D90-ledgers.sha256` 校验通过。
2. 商业硬门禁通过。
3. 经济硬门禁通过。
4. 产品硬门禁通过。
5. 质量硬门禁通过。
6. 系统与合规硬门禁通过。
7. 28 条门禁登记全部有 `verdict`。
8. `pass` 门禁全部有 `evidence_ids`。
9. 延期决策已记录，或明确不延期。
10. 九方签字齐全。

任一步失败：

- 硬门禁失败：No-Go。
- 证据缺失：`insufficient_evidence`，按 Task 16 Step 9 处理。
- 签字缺失：决议无效，重新评审。

## 附录 D：禁止事项

- 不得把 PG0 承诺、LOI、口头意向或未付款合同写成实际付费。
- 不得把 Agency 终端品牌单独计数。
- 不得把免费 Quick 线索计入付费伙伴。
- 不得新增模板、品类或正式市场。
- 不得提供免费定制。
- 不得卖裸 API 或原始 JSON。
- 不得按调用次数计费。
- 不得接受客户 Cookie 或 Seller Center 登录态。
- 不得把产品缺口包装成专业服务。
- 不得用 Conditional Go 豁免硬门禁。
- 不得在硬门禁失败时批准延期。
- 不得第二次延期。
- 不得在未签字的情况下发布正式报告。
- 不得修改已发布报告、交付包和账本历史行。
- 不得把证据文件、客户 PII、密钥或 Cookie 提交到 Git。
