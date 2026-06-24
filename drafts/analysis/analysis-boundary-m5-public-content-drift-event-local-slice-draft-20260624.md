---
title: M5 Public Content Drift Event Local Slice Evidence
doc_type: analysis
module: automation
topic: m5-public-content-drift-event
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Drift Event Local Slice Evidence

## Scope

This local slice closes the repo-level gap where `public-content-drift-check` produced read-only hash/presence drift results but did not have a dedicated persisted `DatasetDriftEvent` save path.

Implemented capability:

- `AutomationPublicContentDriftEventSaveRequest`
- `POST /api/automation/public-content-drift-events`
- `GET /api/automation/public-content-drift-events`
- `save_public_content_drift_event()`
- `event_type=public_content_drift`
- audit events `public_content_drift_event_saved` and `public_content_drift_event_reused`
- Web API client methods `checkAutomationPublicContentDrift()` and `saveAutomationPublicContentDriftEvent()`
- mock-mode public content drift semantics with `public_content_update` dataset type and `content_hash` / `content_presence` signals

## Boundary

This was local code and test work only.

Not executed:

- production deploy
- production database write
- production retained canary update
- production `DatasetDriftEvent` creation
- new TaskRun or collector execution beyond local test fixtures
- provider call
- email send
- scheduler mutation or tick
- dataset export file write
- production browser run
- browser artifact write

The retained production canary inventory from 2026-06-23 still has `dataset_drift_events=0` until a later authorized deploy and production gate explicitly creates or verifies a retained public-content drift event.

## Local Validation

```text
uv run pytest tests/integration/test_sources_tasks.py -k public_feed
result: passed
selected: 1 passed, 20 deselected
```

```text
uv run pytest
result: passed
tests: 106 passed, 1 warning
```

```text
uv run ruff check src tests
result: passed
```

```text
pnpm --dir apps/web exec tsc --noEmit
result: passed
```

```text
pnpm lint:web
result: passed
```

```text
pnpm test:web
result: passed
tests: 8 passed
```

```text
pnpm --dir apps/web build
result: passed
```

```text
git diff --check
result: passed
```

## Supported Claim

The local codebase now has a dedicated public-content drift event persistence path that saves and lists `public_content_drift` events from the existing read-only public content drift check, preserves `run_started=false` and `alert_created=false`, and reuses identical snapshots through an idempotency key.

## Unsupported Claim

This does not prove production has persisted a public-content drift event, does not update the retained canary, and does not prove scheduler, provider, email, export, or browser-runtime behavior.
