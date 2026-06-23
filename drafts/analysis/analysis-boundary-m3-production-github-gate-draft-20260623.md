---
title: M3 Production GitHub API-first Gate Evidence
doc_type: analysis
module: automation
topic: github-api-first-production-gate
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M3 Production GitHub API-first Gate Evidence

## Scope

Authorization envelope used for this gate:

- `scope_type`: `topic`
- `scope_value`: `web-scraping`
- `max_repositories`: `3`
- allowed side effects: Source/Task write, one GitHub API task run, Dataset save, report asset, drift snapshot
- denied side effects: dataset export file, provider call, product/report/subscription email send, scheduler mutation, production browser run, screenshot/trace/HAR/browser artifact write
- retention policy: `cleanup_after_evidence`

## Facts

- Local release was rebuilt on top of production `origin/main` instead of deploying stale branch state. The stale direct deploy candidate `c640ff4` was not a fast-forward from production `e97810a`; final production code deploy used `f04c8ea77cc64f28d391e992012525e1704ec1a3`.
- Remote backup branch was created before the first fast-forward: `backup/pre-github-gate-20260623`.
- Production remote `HEAD` and `.deploy-sha` both equal `f04c8ea77cc64f28d391e992012525e1704ec1a3`.
- Production health after deploy: `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023`.
- Production containers after deploy: `api`, `db`, `edge`, and `web` healthy.
- Public page smoke returned `200` for `/dashboard`, `/automation`, `/datasets`, `/tasks`, `/sources`, `/alerts`, `/notifications`, `/projects`, `/signals`, `/raw-records`, `/entities`, and `/toolkit`.
- Production GitHub package gate passed with real API mode: `PLAYWRIGHT_BASE_URL=https://scrapy.lute-tlz-dddd.top PLAYWRIGHT_REAL_API=true pnpm --dir apps/web exec playwright test --grep "renders automation platform packages"` returned `2 passed`.
- Cleanup dry-run before execute found scoped E2E residue: `users=8`, `workspaces=8`, `workspace_members=16`, `notifications=8`, `dataset_versions=2`, `dataset_drift_events=2`, `report_audit_events=2`.
- Cleanup execute removed the same scoped residue. Post-cleanup recount returned zero for all E2E fixture categories.

## Implementation Notes

- `github_tool_radar.v2` schema now exposes `field_sources`, `collector_schema_versions`, `collector_versions`, `endpoint_origins`, and `provenance.lineage_fields`.
- The production E2E assertions distinguish stable production facts from volatile public GitHub values. Release tags, exact risk counts, and synthetic drift signal examples remain mock-only assertions.
- The first gateway reload after each container restart may fail while Edge health is still `starting`; retry after Edge becomes healthy succeeded.

## Inferences

- GitHub remains the lowest-risk production platform package among the current candidates because it is API-first, public-data scoped, and does not require login state, browser execution, anti-detect, provider calls, or scheduler mutation.
- The current production gate proves an authorized L4 live GitHub package workflow under a small topic scope, not broad recurring GitHub collection readiness.

## Unknowns

- GitHub API rate-limit behavior under larger topic scopes remains untested.
- Long-lived retained datasets were not evaluated because this gate used `cleanup_after_evidence`.
- Scheduler-based GitHub recurring collection, dataset export files, provider enrichment, and product email/report delivery remain separate gates.

## Boundary

This gate did execute scoped production writes through authorized real API E2E and then cleaned them up. It did not execute dataset export, provider call, email send, scheduler mutation, production browser run, or browser artifact write.
