---
title: P5 Read-only Inventory Evidence
doc_type: analysis
module: operations
topic: boundary-leftovers-p5-read-only-inventory
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# P5 Read-only Inventory Evidence

## 0. Scope

本轮执行 P5 A0/B0/C0/D0 read-only inventory，只做生产只读观察和 repo/interface 盘点。

Not executed:

- provider call
- email test send
- product email send
- report send
- report subscription run
- scheduler mutation
- manual scheduler tick
- dataset export creation
- production browser run
- screenshot / trace / HAR artifact write

最高证据等级：`L3 production read-only`。本轮不产生 `L4 authorized live` 证据。

## 1. Command Classes

| Check | Command class | Side-effect boundary |
|---|---|---|
| Public health | public `GET /api/health` | read-only public route |
| Remote SHA / compose | SSH read-only inspection under `/opt/data-achieve-scrapy/app` | no deploy, no compose restart |
| Provider/email/scheduler/export inventory | API container Python read-only query | no provider call, no email send, no scheduler tick, no export create |

Secrets were not printed. The container query only returned booleans, counters, status labels, timestamps, and non-secret paths.

## 2. Production Baseline

Observation time: 2026-06-23.

| Item | Result | Evidence grade |
|---|---|---|
| Health | `environment=production`, `status=ok`, `database=connected`, `schema=current` | L3 production read-only |
| Schema | `schema_revision=202606110023`, `schema_head=202606110023` | L3 production read-only |
| Scheduler health flag | `scheduler_enabled=true` | L3 production read-only |
| Remote HEAD | `e97810adb86f39f16efe96b9f2b7f0760f5acf7e` | L3 production read-only |
| `.deploy-sha` | `e97810adb86f39f16efe96b9f2b7f0760f5acf7e` | L3 production read-only |
| Compose | `api`, `db`, `edge`, `web` running and healthy | L3 production read-only |

## 3. A0 Provider Inventory

| Field | Result |
|---|---|
| `llm_provider` | `mock` |
| `llm_model_configured` | `false` |
| `llm_api_key_configured` | `false` |
| Default adapter | `MockLLMAdapter` |
| Provider call executed by this probe | `false` |

Conclusion:

- Production is currently configured for mock LLM behavior.
- No real provider model or API key is configured in the observed runtime.
- A2 live provider call is blocked until a real provider, model, budget, input scope, redaction rule, and stop conditions are explicitly authorized and configured.

## 4. B0 Email Channel Inventory

| Field | Result |
|---|---|
| Status | `ready` |
| Configured | `true` |
| Missing settings | `[]` |
| Host configured | `true` |
| Port | `587` |
| Sender configured | `true` |
| Auth configured | `true` |
| TLS mode | `starttls` |
| Reason | `null` |
| Test email sent by this probe | `false` |

Conclusion:

- Email channel is configured and reports ready.
- This is config/readiness evidence only. It does not prove actual delivery.
- B1 test email remains a separate L4 authorization gate with explicit recipient and `max_sends=1`.

## 5. C0 Scheduler Inventory

| Field | Result |
|---|---|
| Scheduler enabled | `true` |
| Poll interval | `60.0s` |
| Enabled collection tasks | `75` |
| Tasks with cron | `0` |
| Enabled report subscriptions | `0` |
| Due report subscriptions now | `0` |
| Latest tick status | `completed` |
| Latest tick started_at | `2026-06-23T07:11:38.243802+00:00` |
| Latest tick scanned tasks | `75` |
| Latest tick due tasks | `0` |
| Latest tick started tasks | `0` |
| Latest tick task errors | `0` |
| Latest tick report subscriptions scanned | `0` |
| Latest tick report subscriptions due | `0` |
| Latest tick report subscriptions started | `0` |
| Latest tick report subscription errors | `0` |
| Error message present | `false` |
| Tick triggered by this probe | `false` |
| Schedule mutated by this probe | `false` |

Conclusion:

- Scheduler is active in production and passively ticking.
- The observed latest tick scanned 75 enabled tasks but found no due task and started no task.
- There are no enabled report subscriptions in the observed runtime, so this inventory did not encounter subscription/email cross-risk.
- C1 schedule approval mutation and C2 tick/task/subscription execution remain separate authorization gates.

## 6. D0 Dataset Export Inventory

| Field | Result |
|---|---|
| Dataset export directory | `/app/exports/datasets` |
| Export root exists | `true` |
| Datasets | `29` |
| Dataset versions | `5` |
| Export jobs | `4` |
| Successful export jobs | `4` |
| Export created by this probe | `false` |

Conclusion:

- Production has the export directory mounted/available and contains existing export job records.
- This probe did not create any export artifact or `DatasetExportJob`.
- A new export requires exact dataset ID, dataset version ID, format, retention/cleanup policy, max row/file expectations, and checksum evidence.

## 7. Gate Result

| Gate | Decision | Supported claim | Forbidden claim |
|---|---|---|---|
| A0 Provider | complete as read-only | production currently reports `llm_provider=mock` and no real model/key configured | provider live call works |
| B0 Email | complete as read-only | SMTP channel reports ready | email delivery succeeded |
| C0 Scheduler | complete as read-only | scheduler is enabled; latest observed tick completed with due=0/started=0 | schedule mutation or task execution was validated |
| D0 Dataset export | complete as read-only | export path exists and existing jobs are counted | a new export was created |

## 8. Recommended Next Decision

Next smallest L4 gate is B1 email test send, because channel readiness is already true and the scope can be constrained to one recipient and one send.

Provider A2 should stay blocked until a real provider/model/key and budget are configured. Scheduler C1 should wait for an exact dataset/version/task set and rollback plan. Dataset export D live should wait for exact dataset/version IDs and retention policy.

## 9. To Do

- [x] A0 provider read-only inventory.
- [x] B0 email channel read-only inventory.
- [x] C0 scheduler read-only overview.
- [x] D0 dataset export read-only inventory.
- [ ] Select one L4 live gate: B1 email test, A2 provider call, C1 scheduler mutation, or D live export.
