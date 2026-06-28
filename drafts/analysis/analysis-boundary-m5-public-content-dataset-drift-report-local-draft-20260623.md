---
title: M5 Public Content Dataset Drift Report Local Slice Evidence
doc_type: analysis
module: automation
topic: public-content-dataset-drift-report
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: codex
---

# M5 Public Content Dataset Drift Report Local Slice Evidence

## Decision

This slice deepens the `public-web-rss-docs` platform package locally by turning existing `public_feed` raw records into a saved dataset version, a read-only content-hash drift check, and a read-only report preview.

Evidence grade: L2 local fixture/runtime. This is not production evidence.

## Implemented Locally

1. `SourceType` now accepts `public_feed`, so the collector catalog is reachable through `POST /api/sources`.
2. `POST /api/automation/public-content-dataset-preview` converts `public_feed` entries into dataset rows.
3. `POST /api/automation/public-content-dataset-save` saves `dataset_type=public_content_update` with `schema_version=public_content_update.v1`.
4. `POST /api/automation/public-content-drift-check` compares latest same-lineage `public_feed` task output using `link` as primary key and `content_hash` as the content drift signal.
5. `POST /api/automation/public-content-report` generates a read-only public content update report preview with summary, latest entries, risk sections, and recommendations.

## Validation So Far

| Check | Result |
|---|---|
| `uv run pytest tests/integration/test_sources_tasks.py -k public_feed` | `1 passed`, 20 deselected, passlib `crypt` deprecation warning |
| `uv run pytest tests/integration/test_sources_tasks.py -k "public_feed or github_topic_radar"` | `2 passed`, 19 deselected, passlib `crypt` deprecation warning |
| `uv run ruff check src tests/integration/test_sources_tasks.py` | passed |
| `uv run pytest` | `106 passed`, passlib `crypt` deprecation warning |
| `uv run ruff check src tests` | passed |
| `pnpm --dir apps/web exec tsc --noEmit` | passed |
| `pnpm lint:web` | passed |
| `pnpm test:web` | `8 passed` |
| `pnpm --dir apps/web build` | passed |
| `git diff --check` | passed |

## Boundary

This round did not deploy production, create production Sources/Tasks/TaskRuns/Datasets, write dataset export files, create Report assets, call a provider, send email, mutate scheduler state, run a production browser, or write browser artifacts.

`public-content-report` is a preview response only. It does not create a `Report` row.

`public-content-drift-check` is a read-only check. It does not create `DatasetDriftEvent`, `AlertEvent`, `Notification`, or email delivery.

## Remaining Gates

1. Public content production package smoke with exact feed URL, max items, side-effect scope, and cleanup/retention policy.
2. Report asset persistence for public content update summaries.
3. Dataset export for `public_content_update` versions.
4. Scheduler approval and tick execution for public feed tasks.
