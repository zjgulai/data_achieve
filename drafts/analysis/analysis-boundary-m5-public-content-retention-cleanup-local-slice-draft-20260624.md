---
title: M5 Public Content Retention Cleanup Local Slice Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-retention-cleanup
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Retention Cleanup Local Slice Evidence

## 1. Scope Boundary

This slice adds a local cleanup policy for retained public-content canaries. It is not a production cleanup run.

Allowed local scope:

- Match retained accounts with `retained-public-content-*@example.com`.
- Default to dry-run.
- Use `older_than_hours` as a TTL cutoff, defaulting to 168 hours.
- Traverse only public-content asset graph nodes: `public_feed` / `generic_web` Sources, Tasks, TaskRuns, RawRecords, Entities, EntitySnapshots, `public_content_update` Datasets/Versions/DriftEvents, `public_content` Reports/AuditEvents, Notifications, and DatasetExportJobs.
- Classify export artifacts under `dataset_export_dir`.
- In execute mode, block before deletion if any export artifact path is outside the configured export root.

Denied scope:

- No production deploy.
- No production retained cleanup dry-run.
- No production retained cleanup execute.
- No retained canary deletion.
- No scheduler tick.
- No provider call.
- No email send.
- No production browser run.
- No browser artifact write.

## 2. Implementation Evidence

Files:

- `apps/api/src/data_intelligence_hub/maintenance/public_content_retention.py`
- `apps/api/tests/unit/test_public_content_retention.py`
- `scripts/cleanup-retained-public-content.sh`

Key behavior:

- `cleanup_retained_public_content_assets()` returns a structured report for dry-run and execute modes.
- Default command behavior is dry-run unless `--execute` is passed.
- The shell wrapper can run locally or through Docker with `SCRAPY_CLEANUP_USE_DOCKER=1`.
- Export artifact deletion is only allowed for paths that resolve under the configured export root.
- Generic `e2e-` cleanup remains separate and does not match retained public-content accounts.

## 3. Validation Evidence

Commands run locally:

```bash
cd apps/api && uv run pytest tests/unit/test_public_content_retention.py -q
```

Result: `2 passed`.

```bash
cd apps/api && uv run ruff check src/data_intelligence_hub/maintenance/public_content_retention.py tests/unit/test_public_content_retention.py
```

Result: `All checks passed`.

```bash
cd apps/api && uv run pytest tests/unit/test_public_content_retention.py tests/unit/test_e2e_cleanup.py -q
```

Result: `4 passed`.

```bash
scripts/cleanup-retained-public-content.sh --help
```

Result: help text printed, including dry-run default and `--execute` boundary.

```bash
cd apps/api && uv run pytest -q
```

Result: `110 passed, 1 warning`.

```bash
cd apps/api && uv run ruff check src tests
```

Result: `All checks passed`.

```bash
git diff --check
```

Result: `passed`.

## 4. Supported Claims

- Local repo now has a retained public-content cleanup policy with dry-run-by-default behavior.
- Local unit tests cover dry-run reporting, execute deletion of expired retained public-content asset graph, preservation of recent retained assets, preservation of generic protected E2E assets, export artifact deletion, and export artifact root violation blocking.
- The wrapper script exposes a production-compatible entrypoint, but it has not been deployed or executed against production.

## 5. Unsupported Claims

- The production server has this cleanup tooling deployed.
- Production retained cleanup dry-run has run.
- Production retained cleanup execute has run.
- The retained production canary has been deleted.
- Multi-day TTL has been observed in production.
- Scheduler recurring monitoring or cleanup automation is active.
