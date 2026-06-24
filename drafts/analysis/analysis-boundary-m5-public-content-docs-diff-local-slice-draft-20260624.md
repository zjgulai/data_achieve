---
title: M5 Public Content Docs Diff Local Slice Draft
doc_type: analysis
module: automation
topic: m5-public-content-docs-diff
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Docs Diff Local Slice Draft

## Scope

This local slice extends the existing `public_content_update` chain from RSS/Atom-only `public_feed` records to both `public_feed` and `generic_web` public docs/page snapshots.

Allowed in this slice:

- Add `generic_web.v1` schema metadata, page-level `content_hash`, `text_length`, and provenance to `generic_web` raw content.
- Convert `generic_web` raw records into one public-content Dataset row per public page snapshot.
- Reuse `link` as the row key and `content_hash` as the content drift signal.
- Save `public_content_update` DatasetVersion rows from docs/page snapshots.
- Run read-only public-content drift check, save/reuse `public_content_drift` events, and generate public-content report preview / Report asset locally.
- Update API, architecture, Web mock, and workflow docs to reflect the local state.

Denied in this slice:

- No production deploy.
- No production Source, Task, TaskRun, DatasetVersion, DatasetDriftEvent, Report, DatasetExportJob, or retained canary mutation.
- No scheduler mutation or scheduler tick.
- No provider call.
- No email send.
- No production browser run.
- No browser artifact write.
- No dataset export file write.

## Implementation Facts

- `generic_web` collector now emits `schema_version=generic_web.v1`, `content_hash`, `text_length`, and provenance for public page snapshots.
- `public_content_update.v1` Dataset preview/save now accepts raw records with `record_type in {"public_feed", "generic_web"}`.
- `generic_web` docs/page snapshots map to `title`, `link`, `updated_at`, `summary`, `content_hash`, `site_url`, `source_type`, `content_kind`, and `text_length`.
- Public-content drift check now accepts `public_feed` or `generic_web` task lineage and reports hash-only docs/page changes as `content_hash_changed`.
- Public-content export preview records the actual collector schema versions present in the source raw records, for example `generic_web.v1` for docs/page snapshots.
- Existing RSS behavior remains covered by the original public feed integration test.

## Validation

```text
uv run pytest tests/unit/test_collectors.py::test_generic_web_collector_collects_html_snapshot tests/integration/test_sources_tasks.py::test_public_feed_saves_public_content_dataset_and_reports_hash_drift tests/integration/test_sources_tasks.py::test_generic_web_docs_snapshot_saves_public_content_dataset_and_reports_hash_drift
result: 3 passed, 1 warning
```

```text
uv run ruff check src tests/unit/test_collectors.py tests/integration/test_sources_tasks.py
result: All checks passed
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
uv run pytest
result: 107 passed, 1 warning
```

```text
pnpm test:web
result: 8 passed
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

The local codebase can now use `generic_web` public docs/page snapshots as public-content Dataset rows, compare them with content hash drift, save a `public_content_drift` snapshot, and generate public-content report output without starting collectors from the drift/report endpoints.

## Unsupported Claim

This does not prove production docs/page collection, recurring monitoring, scheduler refresh, provider enrichment, email delivery, Dataset export, retained canary update, production browser execution, or browser artifact retention.
