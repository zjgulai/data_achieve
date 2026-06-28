---
title: 边界遗留事项执行计划
doc_type: analysis
module: operations
topic: boundary-leftovers
status: draft
created: 2026-06-22
updated: 2026-06-22
owner: self
source: human+ai
---

# 边界遗留事项执行计划

## 0. 计划边界

本计划只用于把 PRD2 R0 发布后的遗留边界事项拆成可执行队列。它不是对生产写入、provider call、邮件发送、调度变更、真实浏览器采集的授权。

执行时必须继续区分：

- `docs-only`: 只更新文档或计划，不改生产状态。
- `read-only`: 只读生产状态或产出 dry-run 报告，不写业务数据。
- `dry-run`: 运行脚本的预演模式，必须明确不执行写入分支。
- `authorized live side effect`: 已有单项明确授权，且范围、回滚、清理证据齐全。

## 1. 当前可用基线

### 事实

- 上一轮发布 closeout 已记录生产发布到 SHA `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`，预快照为 `lhsnap-erfd1c6c / pre-data-scrapy-deploy-20260622`。
- 上一轮发布 closeout 已记录生产健康检查为 `schema_revision=202606110023`、`schema_head=202606110023`、`schema=current`、`scheduler_enabled=true`。
- 上一轮发布 closeout 已记录 public page smoke 和 authenticated API smoke 通过。
- `.kiro/plan` 当前产品线已完成 Phase 17B：`diagnostic_snapshot_replay` 结果资产可生成，但 `browser_started=false`、`files_written=false`、`collection_resources_written=false`。
- Phase 18A / P4 已完成当前 spike：`ephemeral_browser_harness_probe` 现在需要显式 dedicated CDP URL；缺少 CDP 时 fail-closed，不会默认复用用户 Chrome。已完成一次本地 isolated headless Chrome + browser-harness 只读 smoke；生产未部署、未运行。

### 推断

- 下一阶段优先级不应直接跳到真实浏览器采集或 provider call。最稳妥顺序是先把部署后状态文档和 release closeout 对齐，再做生产只读/dry-run 盘点，最后进入单项授权的 L4 写入验收。
- Demo seed/cleanup 是否需要执行，必须由 dry-run 盘点结果决定；不能因为生产 smoke 通过就默认执行写入。

### 不确定项

- 执行下一轮前需要重新核验当前 live SHA、health、compose 状态，因为上一轮证据只证明当时状态。
- 生产 demo 噪声计数、E2E 残留计数、email channel 可用性、provider 配额和 browser-harness 目标 URL 尚未在本计划生成时重新核验。

## 2. 边界遗留清单

| ID | 遗留边界 | 当前状态 | 下一步证据 | 是否需要单项授权 |
|---|---|---|---|---|
| B0 | PRD2 R0 deployed-state 文档同步 | 部分稳定文档仍停留在发布前状态 | docs-only diff，写明 SHA、schema、smoke、未执行边界 | 否 |
| B1 | Demo seed / demo cleanup | 已有治理脚本和白名单；发布后未重新 dry-run | `cleanup-demo-noise.sh` production dry-run 结果 | 仅 execute 需要 |
| B2 | Production write E2E | P3 scoped real API E2E 已完成并 cleanup recount 全零 | P3 证据稿、E2E 输出、cleanup dry-run/execute/recount | 已授权并执行 |
| B3 | In-app notification / email send | P5 B0 只读 inventory 显示 email channel `ready`；P5 B1 已发送 1 封授权 test email 且 `delivered=true` | B2 产品邮件另行验收 | product send/email 需要 |
| B4 | Provider call | P5 A0 只读 inventory 显示生产 `llm_provider=mock`，无 model/key，默认 `MockLLMAdapter` | 真实 provider、max calls、budget、stop condition | 是；当前 blocked until configured |
| B5 | Scheduler mutation | P5 C0 只读 inventory 显示 scheduler enabled，latest tick completed，due=0/started=0 | 待变更 task、cron、rollback 和观察窗口 | 是 |
| B6 | Real browser-harness run | P4 已完成 local isolated smoke；product route 缺 dedicated CDP 时 blocked | selector/network 扩展、artifact retention 和生产 gate | 生产 run 需要 |
| B7 | 平台采集扩展 | Agent-Reach / browser-harness 融合已形成方向，但未落执行 | 平台优先级和 adapter 合约验收 | 按平台分别授权 |

## 3. 优先级

### P0: 状态文档与 release closeout 对齐

目标：把“已经部署”和“仍未执行”的边界写清楚，避免后续误把发布 smoke 当成写入 E2E、provider call 或真实浏览器采集。

动作：

1. docs-only 更新 `docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md` 的发布状态、schema 和剩余边界。
2. 新增或更新 release closeout 记录，引用 SHA、快照、health、public smoke、authenticated API smoke。
3. 明确保留未执行项：demo seed、production write E2E、provider call、email send、scheduler mutation、real browser-harness run。

验收：

- `git diff --check` 通过。
- 文档中没有把 `dry-run` 写成已执行写入，没有把 `authenticated API smoke` 写成 production write E2E。

### P1: 生产 read-only / dry-run 盘点

目标：在不写业务数据的前提下确认遗留边界的真实待办量。

动作：

1. 重新核验 live SHA、health、schema、compose 状态。
2. 运行 demo cleanup production dry-run，记录是否有非白名单 demo 噪声。
3. 运行 E2E fixture cleanup production dry-run，记录是否有残留测试对象。
4. 只读检查 email channel 状态；不设置 `TEST_EMAIL_CHANNEL=true`。

验收：

- 输出 dry-run 记录，包含对象计数、脚本退出状态、时间戳。
- 明确写明 `production unchanged`。

### P2: Demo seed / cleanup 执行判定

目标：只有在 P1 dry-run 证明需要清理或补种时，才进入 execute。

动作：

1. 如果 demo cleanup dry-run 全零，则不执行 cleanup。
2. 如果 dry-run 显示可安全删除的 demo 噪声，先保存对象清单，再请求 `--execute` 授权。
3. 如果 demo 数据缺口影响产品演示，再制定 seed execute 子计划；不和 cleanup 混在同一次授权里。

验收：

- execute 前有对象清单。
- execute 后有 read-only recount。
- 结果必须区分 demo 记录、E2E 临时记录和正式 owner/demo 数据。

### P3: L4 production write E2E

目标：用一次性账号和一次性 workspace 证明真实生产写入链路可用，然后清理干净。

动作：

1. 建立授权 envelope：测试邮箱前缀、workspace 前缀、允许创建对象类型、最大对象数、cleanup 方式。
2. 执行 targeted real API E2E：login/session、project、source/task、manual_json run、raw records、entities、signals、intelligence、alert rule/event 和 in-app notification 等 cleanup-covered 链路。
3. 记录一次性账号/workspace scope；如果脚本未输出 DB UUID，则以 cleanup dry-run/execute/recount 作为资源闭环证据。
4. 先 cleanup dry-run，再 cleanup execute，最后 recount。

验收：

- E2E 输出、一次性账号/workspace scope、cleanup dry-run、cleanup execute、recount 五件证据齐全。
- 不使用 demo account 承担写入 E2E。

### P4: Browser-harness 本地 ephemeral adapter spike

目标：把 Phase 18A 控制在本地隔离 adapter，不进入生产，不复用用户 Chrome 状态。

动作：

1. 定义 adapter 输入：BrowserDiagnosticJobRun contract、target URL、selector scope、wait policy、artifact policy。
2. 使用 ephemeral context；强制 `reuse_user_profile=false`、`cookie_export_allowed=false`、`login_state_allowed=false`。
3. 仅允许 public test URL；禁止登录页、私信、支付页、账号后台。
4. 输出 bounded artifact：redacted screenshot summary、network summary、selector preview rows、run status。

验收：

- 本地 evidence 显示 `browser_started=true`，但 `collection_resources_written=false`。
- 无 Source/Task/TaskRun/Dataset/AlertEvent/Notification/email/export/scheduler side effect。
- 生产部署保持 unchanged。

### P5: Provider / email / scheduler 单项 gate

目标：把高风险 side effect 拆成独立授权，避免混在采集开发里。

动作：

1. Provider call gate：明确 provider、模型/接口、max calls、budget、prompt/input 边界、停止条件。
2. Email send gate：明确 recipient、模板、发送次数、channel status、回滚或抑制策略。
3. Scheduler mutation gate：明确 task 列表、cron、观察窗口、rollback。

验收：

- 每个 gate 都有单独执行记录。
- 没有授权的 gate 保持 `not executed`。

## 4. To Do

- [x] 制定边界遗留事项执行计划。
- [x] P0 docs-only 状态同步和 release closeout 记录。
- [x] P1 production read-only / dry-run 盘点。
- [x] P2 demo cleanup / seed execute 判定。已执行授权的 production demo cleanup `--execute`；post-cleanup dry-run recount 全零；未执行 demo seed。
- [x] P3 L4 production write E2E 授权 envelope。用户授权为 `同意执行 P3`；执行时进一步收窄到不包含 report send、email send、provider call、scheduler mutation、dataset export 或 real browser-harness 的 targeted E2E。
- [x] P3 L4 production write E2E 执行与 cleanup。targeted real API Playwright `16 passed`；E2E fixture cleanup dry-run/execute/recount 已完成，recount 全零。
- [x] P4 local ephemeral browser-harness adapter spike。新增 dedicated CDP requirement；缺 CDP 时 blocked；本地 isolated headless Chrome + browser-harness `https://example.com/` smoke 成功；生产 unchanged。
- [x] P5 provider / email / scheduler gate 单项计划。已生成 `drafts/analysis/analysis-boundary-p5-provider-email-scheduler-gate-plan-draft-20260622.md`；没有执行 provider call、email send、scheduler mutation 或 dataset export。
- [x] P5 A0/B0/C0/D0 read-only inventory。已生成 `drafts/analysis/analysis-boundary-p5-read-only-inventory-draft-20260623.md`；没有执行 provider call、email send、scheduler mutation、scheduler tick 或 dataset export。
- [x] P5 B1 one-test-email live send。已生成 `drafts/analysis/analysis-boundary-p5-b1-email-test-send-draft-20260623.md`；只发送 1 封 test email，未执行 product email、report send、subscription run、provider call、scheduler mutation 或 dataset export。
- [ ] P5 B2/A2/C1/D live gate selection, if still needed。

## 7. P1 Evidence Snapshot

P1 证据记录：`drafts/analysis/analysis-boundary-p1-production-inventory-draft-20260622.md`。

结论：

- Live SHA、`.deploy-sha`、health schema 和 compose healthy 对齐到 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e` / `202606110023`。
- Public page smoke 覆盖 `/api/health`、`/dashboard`、`/automation`、`/datasets`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities`、`/toolkit`，均为 `200`。
- Demo cleanup dry-run 非零：`task_runs=84`、`raw_records=34`、`entity_snapshots=42`、`notifications=42` 等候选；未执行清理。
- E2E fixture cleanup dry-run 使用 `--older-than-hours 0`，全部候选计数为 0。
- Email channel 配置状态为 `ready`，但未发送测试邮件。

P1 边界：本轮没有执行 `--execute`、demo seed、production write E2E、provider call、email send、scheduler mutation 或 real browser-harness run。

## 8. P2 Evidence Snapshot

P2 证据记录：`drafts/analysis/analysis-boundary-p2-demo-cleanup-execution-draft-20260622.md`。

结论：

- 用户授权后执行 production demo cleanup `--execute`。
- 清理对象计数：`task_runs=84`、`raw_records=34`、`entity_snapshots=42`、`notifications=42`、`reports=14`、`sources=12`、`collection_tasks=12` 等。
- post-cleanup dry-run recount 全部为 0。
- cleanup 后 health 仍为 `schema=current`、`schema_revision=schema_head=202606110023`。
- cleanup 后 public page smoke 仍覆盖 13 个 route，均为 `200`。
- cleanup 后 remote `HEAD` 和 `.deploy-sha` 仍为 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`，`api/db/edge/web` healthy。

P2 边界：本轮没有执行 demo seed、E2E fixture cleanup execute、production write E2E、provider call、email send、scheduler mutation 或 real browser-harness run。

## 9. P3 Evidence Snapshot

P3 证据记录：`drafts/analysis/analysis-boundary-p3-production-write-e2e-draft-20260622.md`。

结论：

- P3 前置 baseline：production health `schema=current`、`schema_revision=schema_head=202606110023`；remote `HEAD` 与 `.deploy-sha` 均为 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`；`api/db/edge/web` healthy；13 个 public route 均为 `200`。
- 完整 real Playwright suite 被刻意排除，因为其中包含 report send、subscription execute、notification fixture backed by report send、GitHub Topic Radar、dataset export、schedule approval 和 browser-harness probe controls。
- 执行 targeted real API Playwright：desktop 8 tests + mobile 8 tests，`16 passed (49.9s)`。
- 写入范围覆盖一次性账号/workspace 下的 Auth、Project、Source、CollectionTask、TaskRun、RawRecord、Entity、Signal、Intelligence、AlertRule、AlertEvent 和 in-app Notification。
- E2E cleanup dry-run 命中 `users=4`、`workspaces=4`、`sources=8`、`collection_tasks=8`、`task_runs=8`、`raw_records=8`、`alert_events=7`、`notifications=4` 等对象；`reports=0`、`report_subscriptions=0`、`datasets=0`、`dataset_export_jobs=0`。
- E2E cleanup execute 删除了同一候选集；post-cleanup recount 全部为 0。
- P3 后置 health、route smoke、remote SHA 和 compose 仍保持正常。

P3 边界：本轮没有执行 full real E2E suite、report send、external email send、provider call、scheduler mutation、dataset export、demo seed 或 real browser-harness run。

## 10. P4 Evidence Snapshot

P4 证据记录：`drafts/analysis/analysis-boundary-p4-browser-harness-ephemeral-probe-draft-20260622.md`。

结论：

- `AutomationBrowserLocalRunnerRequest` 新增 `browser_harness_cdp_url`。
- `ephemeral_browser_harness_probe` 缺少 dedicated CDP URL 时返回 `blocked_ephemeral_probe`，blocked reason 为 `browser_harness_isolated_cdp_required`。
- runner 子进程显式设置 `BU_CDP_URL`，并移除继承的 `BU_CDP_WS`，避免默认连接用户 Chrome。
- 本地 isolated headless Chrome 使用 `/tmp/data-scrapy-p4-chrome-20260622T095755Z` profile 和 `127.0.0.1:9333` CDP；browser-harness 对 `https://example.com/` 输出 page_info 并关闭 tab。
- 验证通过：API full pytest `102 passed`，API ruff passed，web lint passed，web unit `8 passed`，Playwright mock E2E `4 passed`，web standalone build passed，`git diff --check` passed。

P4 边界：本轮没有生产部署，没有生产 browser run，没有 provider call、email send、scheduler mutation、dataset export，也没有由 browser probe 创建 Source/Task/TaskRun/Dataset/AlertEvent/Notification。

## 11. P5 Gate Plan Snapshot

P5 计划记录：`drafts/analysis/analysis-boundary-p5-provider-email-scheduler-gate-plan-draft-20260622.md`。

结论：

- Provider gate 拆为 A0 read-only inventory、A1 fixture-only validation、A2 authorized live provider call。
- Email gate 拆为 B0 read-only channel status、B1 max-one test email、B2 product email send；report send 和 report subscription run 被列为独立邮件风险路径。
- Scheduler gate 拆为 C0 read-only overview、C1 schedule approval mutation、C2 actual scheduler tick / due task / due report subscription execution。
- Dataset export 被保留为 D gate，因为 `product-dataset-exports` 会写 artifact file 和 `DatasetExportJob`，不能由 P5 provider/email/scheduler 授权顺带覆盖。
- 当前 pass 没有执行 provider call、email test send、report send、subscription run、scheduler mutation、scheduler tick、dataset export、production browser run 或 artifact file write。

下一步只允许执行 P5 read-only inventory：A0 provider config/adapter inventory、B0 email channel status refresh、C0 scheduler overview refresh、D0 dataset export candidate inventory。任何 live call/send/mutation/export 仍需单项授权。

## 12. P5 Read-only Inventory Snapshot

P5 只读盘点记录：`drafts/analysis/analysis-boundary-p5-read-only-inventory-draft-20260623.md`。

结论：

- 生产 baseline 新鲜核验：health `production/ok/connected/current`，`schema_revision=schema_head=202606110023`；remote `HEAD` 和 `.deploy-sha` 均为 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`；`api/db/edge/web` healthy。
- A0 provider：生产 `llm_provider=mock`，`llm_model_configured=false`，`llm_api_key_configured=false`，default adapter 为 `MockLLMAdapter`；本轮没有 provider call。
- B0 email：channel `ready`，configured，`tls_mode=starttls`，missing settings 为空；本轮没有 test email 或 product email send。
- C0 scheduler：scheduler enabled，poll interval `60.0s`，enabled collection tasks `75`，tasks with cron `0`，enabled report subscriptions `0`；latest tick completed，scanned `75`，due `0`，started `0`；本轮没有触发 tick 或修改 schedule。
- D0 dataset export：export dir `/app/exports/datasets` 存在；datasets `29`、dataset versions `5`、export jobs `4`、successful export jobs `4`；本轮没有创建 export。

下一步 live gate 候选：B1 one-test-email 是当前最小可控 L4，因为 email channel ready 且可约束为 1 个 recipient / 1 次发送。A2 provider live call 仍 blocked until configured；C1 scheduler mutation 需要 exact dataset/version/task set 与 rollback；D live export 需要 exact dataset/version IDs 与 retention/cleanup policy。

## 13. P5 B1 One-test-email Snapshot

P5 B1 证据记录：`drafts/analysis/analysis-boundary-p5-b1-email-test-send-draft-20260623.md`。

结论：

- 用户提供 recipient：`zhoujianaaa123@gmail.com`。
- 执行范围：B1 one-test-email，`max_sends=1`。
- 执行结果：attempted sends `1`，subject `Data Achieve 邮件通道测试`，started at `2026-06-23T07:27:18.928471+00:00`，finished at `2026-06-23T07:27:23.503534+00:00`，`delivered=true`，reason `null`。
- 执行方法：生产 API container 内直接调用既有 `send_email_notification()` 一次；未走登录态 API，避免登录/session repair 副作用。

B1 边界：本轮只证明 1 封授权 test email 投递成功；没有执行 product drift alert email、report send、report subscription run、bulk email、scheduler-triggered email、provider call、scheduler mutation、dataset export 或 production browser run。

## 5. 建议授权口径

- Demo cleanup execute：`授权执行 production demo cleanup --execute，范围以 dry-run 对象清单为准`。
- Production write E2E：`授权执行 L4 production real API E2E，范围：一次性 e2e 用户/workspace/source/task/dataset/report/alert/notification，必须 cleanup`。
- Email test send：`授权发送 1 封 test email: recipient=<email>, route=<email-channel-test>, max_sends=1, account_scope=<account/workspace>, evidence_path=<path>`。
- Product email send：`授权执行 product email send: endpoint=<drift-alert-email|report-send|subscription-run>, ids=<exact ids>, recipient=<email>, max_sends=<n>, channel_scope=<email only / in_app+email>, cleanup_or_audit=<plan>`。
- Provider call：`授权 provider live call: provider=<name>, model=<model>, max_calls=<n>, max_tokens_or_budget=<limit>, input_scope=<ids/fixture>, redaction=<rules>, stop_conditions=<rules>`。
- Scheduler mutation：`授权 scheduler mutation: dataset_id=<id>, dataset_version_id=<id>, task_ids=<ids>, cron=<expr>, previous_state_capture=true, rollback=<plan>`。
- Dataset export：`授权创建 dataset export: dataset_id=<id>, dataset_version_id=<id>, format=<csv|json|jsonl>, max_rows=<n>, retention=<keep|cleanup>, checksum_required=true`。
- Browser-harness local run：`授权 browser-harness local-only read-only run: URL=<public_url>, no cookies, no profile, artifacts=<policy>`。

## 6. 下一步建议

P0、P1、P2、P3、P4 已完成，P5 gate 计划、P5 read-only inventory 和 B1 one-test-email 已完成。下一步建议停止 P5 email gate 并回到平台采集深化；如果继续 P5 live gates，则 B2 product email、A2 provider call、C1 scheduler mutation、D live export 都必须另行单项授权并定义清理/回滚证据。
