---
title: P5 Provider Email Scheduler Gate Plan
doc_type: analysis
module: operations
topic: boundary-leftovers-p5-gates
status: draft
created: 2026-06-22
updated: 2026-06-22
owner: self
source: human+ai
---

# P5 Provider Email Scheduler Gate Plan

## 0. Decision Boundary

本文件只完成 P5 gate 计划，不执行任何 live side effect。

Not executed in this pass:

- provider call
- email test send
- report send
- report subscription run
- scheduler mutation
- task run via scheduler
- dataset export file write
- production browser-harness run
- screenshot / trace / HAR artifact write

最大证据等级：`L1 repo evidence` + `L3 prior production read-only/config-only evidence`。只有后续获得单项授权并留下执行日志后，才能升级到 `L4 authorized live`。

## 1. Current Facts

### Product baseline

- P0/P1/P2/P3/P4 已完成并各自留有 evidence draft。
- P3 scoped production write E2E 已通过并清理，刻意排除了 report send、email send、provider call、scheduler mutation、dataset export 和 browser-harness production run。
- P4 local-only browser-harness spike 已完成 dedicated-CDP guard，生产未运行 browser-harness。

### Provider surface

- `apps/api/src/data_intelligence_hub/core/config.py` 存在 `llm_provider`、`llm_api_key`、`llm_model` 配置字段。
- `apps/api/src/data_intelligence_hub/services/llm_service.py` 的 `LLMService` 默认使用 `MockLLMAdapter`。
- 当前 repo evidence 只证明 mock provider path 存在；没有证明生产环境存在真实 provider adapter、provider key 或 provider 调用历史。

### Email surface

- `GET /api/notifications/email-channel` 是配置状态读取路径。
- `POST /api/notifications/email-channel/test` 会调用 `test_email_channel()`，向当前用户邮箱发送测试邮件。
- `POST /api/automation/product-drift-alert-emails` 会调用 `send_email_notification()`，根据 Drift AlertEvent 和 email/both channel 发送告警邮件。
- `POST /api/reports/{report_id}/send` 和 `POST /api/reports/subscriptions/{subscription_id}/run` 也可能触发 email channel。
- P1 只做过 email channel config-only status，结果为 ready；没有发送测试邮件。

### Scheduler surface

- 生产 health 在 P1/P2/P3 记录 `scheduler_enabled=true`。
- `GET /api/tasks/scheduler/overview` 可读取 scheduler enabled 状态和 latest tick。
- `CollectionScheduler.tick()` 会扫描 scheduled collection tasks，并可能调用 `execute_collection_task()`。
- 同一个 scheduler tick 还会扫描 due report subscriptions，并可能调用 `execute_report_subscription()`；若 subscription channels 包含 email，则间接进入 email delivery path。
- `POST /api/automation/product-schedule-approve` 是调度审批写路径，会修改 task schedule metadata，但不会立即启动 run。

### Dataset export surface

- `POST /api/automation/product-dataset-exports` 要求 `authorized` 和 `confirm_create`，会写出 export artifact file，并创建 `DatasetExportJob`。
- Dataset export 不属于 P5 三件套名称，但它是文件写入 side effect，必须保留独立 gate。

## 2. Inferences

1. Provider gate 应先做 adapter/config inventory，而不是直接调用外部模型。
2. Email gate 应拆成三层：配置读取、最多一次 test send、业务邮件发送。不能用 email channel ready 代替投递成功。
3. Scheduler gate 应拆成 scheduler read-only overview、schedule approval mutation、actual tick/task/subscription execution 三层。
4. Report subscription run 是 scheduler/email 的交叉风险点，不能混入普通 report smoke。
5. Dataset export 的风险是文件 artifact 与清理，不应被 scheduler 或 email 授权顺带覆盖。

## 3. Unknowns

- 生产环境是否配置真实 `llm_provider != mock` 未在本 pass 核验。
- 生产环境是否存在 provider API key、模型名、配额、超时和 retry 策略未核验；不得记录具体 secret。
- 当前 scheduler latest tick、due task 数、due report subscription 数未在本 pass 新鲜读取。
- 当前 email channel ready 状态是否仍为 ready 未在本 pass 新鲜读取。
- 是否存在可用于安全测试的 report、subscription、dataset、alert event、task IDs 未在本 pass 新鲜读取。

## 4. Gate A: Provider Call

### A0 Read-only inventory

Goal: 确认 provider 配置状态和代码路径，不调用外部 provider。

Allowed checks:

- 读取配置字段名和 adapter class，不输出 secret value。
- 只记录 provider type 是否为 `mock` / `configured-non-mock` / `unknown`。
- 检查是否有 provider call audit 或 usage counter；若不存在，记录缺口。

Evidence grade: `L1 repo evidence` 或 `L3 production read-only/config-only`。

Stop conditions:

- 需要展示或复制 secret。
- provider adapter 不清楚，无法判断是否会外呼。
- inventory 命令会触发调用或写入。

### A1 Fixture-only provider validation

Goal: 使用 fake adapter 或 mock adapter 验证 schema guard，不触发外部 provider。

Allowed checks:

- 运行 `test_llm_service` 级别的本地单测。
- 使用 fixture payload 验证 JSON schema guard、invalid JSON、invalid schema。

Evidence grade: `L2 fixture`。

### A2 Authorized live provider call

Required authorization fields:

- provider name
- model / endpoint
- max calls
- max tokens or budget
- exact input source IDs or fixture payload
- redaction rule
- timeout / retry policy
- stop conditions
- audit evidence path

Acceptance:

- provider call count <= authorized max.
- output linked to exact input and redaction policy.
- no secret appears in logs or docs.
- result labelled `L4 authorized live provider call` only after execution evidence exists.

## 5. Gate B: Email

### B0 Read-only channel status

Goal: 只确认 SMTP channel 配置状态，不发邮件。

Allowed checks:

- `GET /api/notifications/email-channel` only if login/session side effects are acceptable for that check.
- Prefer container-side config/status inspection when strict `production unchanged` is required.

Evidence grade: `L3 config-only`。

Stop conditions:

- 需要登录且登录会触发 demo membership/notification repair，而当前授权要求 strict no-write。
- status 返回 disabled / unknown。

### B1 Test email send

Required authorization fields:

- recipient email
- max sends = 1
- route or script to use
- expected subject/template
- allowed account/workspace
- evidence capture method

Acceptance:

- exactly one test send attempted.
- delivered/skipped reason recorded.
- no report status, alert status, scheduler state, or dataset state changed.
- evidence labelled `L4 authorized live email test` only after send log exists.

### B2 Product email send

Candidate paths:

- `POST /api/automation/product-drift-alert-emails`
- `POST /api/reports/{report_id}/send`
- `POST /api/reports/subscriptions/{subscription_id}/run`

Required authorization fields:

- exact endpoint
- exact report/subscription/dataset/drift/alert IDs
- recipient
- max sends
- channel list
- cleanup or audit plan
- stop conditions for duplicate send or skipped channel

Stop conditions:

- recipient is implicit or not user-approved.
- selected route can trigger both in-app and email side effects but only email was authorized.
- subscription run could execute a report on a schedule-like path without explicit authorization.

## 6. Gate C: Scheduler

### C0 Read-only overview

Goal: 读取 scheduler 状态，不改变 schedule、不启动 tick。

Allowed checks:

- health `scheduler_enabled`
- `GET /api/tasks/scheduler/overview`
- latest tick status, started/due/error counters
- read-only list of candidate scheduled tasks and report subscriptions if available

Evidence grade: `L3 production read-only`。

### C1 Schedule approval mutation

Candidate path:

- `POST /api/automation/product-schedule-approve`

Required authorization fields:

- dataset ID
- dataset version ID
- task IDs
- policy
- freshness target
- cron expression
- previous schedule snapshot
- rollback plan
- observation window

Acceptance:

- approval mutates only intended tasks.
- `run_started=false` remains true for approval response.
- previous schedule state is restorable.
- no provider call, email, dataset export, or browser run occurs during approval.

### C2 Actual scheduler execution or tick observation

This is separate from schedule approval.

Required authorization fields:

- whether to observe passive ticks only or manually trigger a tick
- due task IDs allowed to run
- due report subscription IDs allowed to run
- max task runs
- max report subscription runs
- email channel handling for subscriptions
- rollback/cleanup for new TaskRun, ReportSubscriptionRun, Notifications, Reports

Stop conditions:

- due set includes unsupported collector or external platform path.
- due report subscription includes email channel but email send is not separately authorized.
- cleanup cannot identify new task/report/subscription outputs.

## 7. Gate D: Dataset Export

Dataset export remains a separate gate even when the next user-facing focus is provider/email/scheduler.

Required authorization fields:

- dataset ID
- dataset version ID
- export format
- expected row count / max file size
- target export directory policy
- cleanup or retention decision
- checksum capture

Acceptance:

- exactly one export job created.
- artifact path, size, checksum, and row count recorded.
- cleanup/retention decision recorded.

Stop conditions:

- dataset/version IDs are not explicitly selected.
- artifact retention policy is unknown.
- export would include sensitive data not reviewed.

## 8. Cross-gate Matrix

| Gate | Current status | Next allowed action | Live side effect status |
|---|---|---|---|
| Provider A | mock path confirmed in repo; production real provider unknown | A0 read-only inventory | not executed |
| Email B | P1 config-only ready evidence exists but may be stale | B0 read-only status refresh | not executed |
| Scheduler C | production health previously showed enabled | C0 read-only overview | not executed |
| Dataset export D | endpoint writes files and jobs | D0 plan only, no run | not executed |
| Browser production run | P4 local-only smoke exists | keep separate production gate | not executed |

## 9. Authorization Templates

Provider live call:

```text
授权执行 provider live call:
provider=<name>, model=<model>, max_calls=<n>, max_tokens_or_budget=<limit>,
input_scope=<ids/fixture>, redaction=<rules>, stop_conditions=<rules>,
evidence_path=<path>.
```

Email test send:

```text
授权发送 1 封 test email:
recipient=<email>, route=<email-channel-test>, max_sends=1,
account_scope=<account/workspace>, evidence_path=<path>.
```

Product email send:

```text
授权执行 product email send:
endpoint=<drift-alert-email|report-send|subscription-run>,
ids=<exact ids>, recipient=<email>, max_sends=<n>,
channel_scope=<email only / in_app+email>, cleanup_or_audit=<plan>.
```

Scheduler mutation:

```text
授权执行 scheduler mutation:
dataset_id=<id>, dataset_version_id=<id>, task_ids=<ids>,
cron=<expr>, previous_state_capture=true, rollback=<plan>,
observation_window=<duration>, no_email_without_separate_gate=true.
```

Dataset export:

```text
授权创建 dataset export:
dataset_id=<id>, dataset_version_id=<id>, format=<csv|json|jsonl>,
max_rows=<n>, retention=<keep|cleanup>, checksum_required=true.
```

## 10. Recommended Next Execution

P5 read-only inventory 已在 2026-06-23 执行并记录到 `drafts/analysis/analysis-boundary-p5-read-only-inventory-draft-20260623.md`。结果摘要：

1. A0 provider inventory: production reports `llm_provider=mock`, no configured model/key, default adapter `MockLLMAdapter`; no provider call.
2. B0 email channel status: `ready`, configured, `starttls`, no missing settings; no test email sent.
3. C0 scheduler overview: scheduler enabled, latest tick completed, scanned 75 tasks, due=0, started=0, report subscriptions scanned/due/started=0; no tick triggered by this probe.
4. D0 dataset export inventory: export root exists, datasets=29, dataset versions=5, export jobs=4, successful export jobs=4; no export created by this probe.

P5 B1 one-test-email 已在 2026-06-23 执行并记录到 `drafts/analysis/analysis-boundary-p5-b1-email-test-send-draft-20260623.md`。结果：authorized recipient `zhoujianaaa123@gmail.com`，attempted sends `1`，delivered `true`，reason `null`。这只证明一封 test email 的 L4 投递，不证明 product drift alert email、report send、subscription run、bulk email 或 scheduler-triggered email。

下一步可选择停止 P5 email gate 并转回平台采集深化；如果继续 P5 live gates，则 B2 product email 需要 exact DriftEvent/AlertEvent IDs、recipient、max_sends 和 audit/cleanup policy。A2 provider live call 仍 blocked，直到真实 provider/model/key/budget 配置完成；C1 scheduler mutation 需要 exact dataset/version/task set 与 rollback；D live export 需要 exact dataset/version IDs 与 retention/cleanup policy。

## 11. To Do

- [x] P5 gate 计划稿。
- [x] P5 A0 provider read-only inventory。
- [x] P5 B0 email read-only status refresh。
- [x] P5 B1 one-test-email live send。
- [x] P5 C0 scheduler read-only overview。
- [x] P5 D0 dataset export candidate inventory。
- [ ] P5 B2/A2/C1/D live gate selection, if still needed。
