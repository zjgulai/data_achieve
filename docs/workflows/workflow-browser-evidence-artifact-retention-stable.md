---
title: Browser Evidence Artifact Retention
doc_type: workflow
module: automation
topic: browser-evidence-retention
status: stable
created: 2026-06-21
updated: 2026-06-21
owner: self
source: human+ai
---

# Browser Evidence Artifact Retention

## Scope

This workflow governs `BrowserDiagnosticJobRun` evidence artifacts and local
browser-harness smoke evidence for Data Intelligence Hub.

It does not authorize production writes, external platform reads, provider calls,
login-state reuse, cookie export, scheduler changes, notification sends, or
Source/Task/TaskRun/Dataset creation.

## Current Phase Policy

During PRD2 M2, browser evidence remains metadata-only by default.

Required response flags:

```text
files_written=false
collection_resources_written=false
cookies_captured=false
headers_captured=false
bodies_captured=false
query_parameters_retained=false
screenshots_written=false
trace_written=false
har_written=false
```

Allowed local evidence:

1. JSON evidence under `tmp/` for local validation.
2. Pydantic/API response fields such as `selector_evaluations`,
   `network_metadata_summary`, `promotion_gate`, and `redaction_summary`.
3. Short stdout/stderr tails after redaction.

Disallowed current-phase artifacts:

1. New screenshot files produced by the local runner.
2. Trace files.
3. HAR files.
4. Request headers.
5. Response bodies.
6. Cookies or local storage.
7. Persisted browser profile directories inside the repo.

## Retention Modes

| mode | use case | allowed path | ttl | product flags |
|---|---|---|---|---|
| `metadata_only_current` | Default M2 runner result | API response / DB JSON fields | DB asset lifecycle | `files_written=false` |
| `tmp_local_validation` | One-off local smoke evidence | `tmp/browser-harness-*.json` | Manual cleanup after review | product runner still reports `files_written=false` |
| `approved_artifact_retention` | Future approved screenshot/trace/HAR retention | `tmp/outputs/browser-evidence/{run_id}/` or object storage | 7 days default, max 30 days | requires explicit artifact policy approval |

## Redaction Contract

Before any artifact leaves process memory or enters a file:

1. Strip query string and fragment from URLs.
2. Do not serialize cookies, storage values, Authorization headers, request
   headers, response bodies, or form values.
3. Keep page metadata to URL, title, viewport dimensions, page dimensions,
   resource counts, and API candidate counts.
4. Keep sample text bounded to 180 characters unless a future contract raises the limit.
5. Record `redaction_summary` with explicit booleans instead of relying on prose.

## Promotion Gate

Browser evidence cannot create collection resources directly in M2.

`promotion_gate` must keep:

```text
can_create_collection_resources=false
review_required=true
reasons includes m2_read_only_contract_no_direct_promotion
```

A future promotion path must be a separate authorized workflow that reads a
reviewed evidence asset and creates Source/Task/Dataset resources under its own
audit event.

## Cleanup Guidance

Current local evidence is intentionally limited to `tmp/browser-harness-*.json`
and helper scripts under `tmp/`.

Cleanup should be explicit and reviewed. Do not use broad repository cleanup.
Only remove the specific evidence files after the closeout has recorded their
status and path.

## M2 Local Smoke Result

Latest local validation evidence:

```text
path=tmp/browser-harness-readonly-smoke-20260621.json
target_url=https://example.com/
status=blocked_local_daemon
blocked_reason=browser_harness_cli_timeout_no_daemon_response
browser_started=false
collection_resources_written=false
cookies_captured=false
headers_captured=false
bodies_captured=false
```

This is local validation evidence only. It does not change production capability
status.
