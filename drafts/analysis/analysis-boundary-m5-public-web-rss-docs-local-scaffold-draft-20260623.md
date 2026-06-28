---
title: M5 Public Web RSS Docs Local Scaffold Evidence
doc_type: analysis
module: automation
topic: public-web-rss-docs-local-scaffold
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M5 Public Web RSS Docs Local Scaffold Evidence

## Scope

This round implements the first local-only M5 scaffold:

- `public_feed` collector for public RSS/Atom feeds.
- `public-web-rss-docs` platform package contract.
- API/Web type and mock alignment.
- Focused unit, integration, web, build, and E2E validation.

## Facts

- `public_feed` validates public HTTP(S) feed URLs, `feed_type=auto|rss|atom`, and `max_items=1..100`.
- RSS parsing extracts feed title/site URL/description and item `title`, `link`, `published_at`, `author`, `tags`, `summary`, and `content_hash`.
- Atom parsing extracts feed title/site URL and entry `title`, `link`, `published_at`, `updated_at`, `author`, `tags`, `summary`, and `content_hash`.
- `public_feed` raw records use `schema_version=public_feed.v1` and normalize to feed-level `public_feed` entity snapshots.
- The platform package matrix now includes `public-web-rss-docs` with `public_feed` and `generic_web` strategies.
- API contract and architecture docs now list `public_feed` and `public-web-rss-docs`.

## Validation

Commands passed locally:

```text
uv run pytest tests/unit/test_collectors.py -k "public_feed or generic_web"
uv run pytest tests/integration/test_sources_tasks.py -k "collectors_are_available or platform_packages"
uv run pytest
uv run ruff check src tests
pnpm --dir apps/web exec tsc --noEmit
pnpm lint:web
pnpm test:web
pnpm --dir apps/web build
pnpm --dir apps/web exec playwright test --grep "renders automation platform packages"
git diff --check
```

## Boundary

This round did not deploy production, create production Sources/Tasks/TaskRuns/Datasets, write dataset export files, call a provider, send email, mutate scheduler state, run a production browser, or write screenshot/trace/HAR browser artifacts.

## Next

The next local-only M5 slice is to convert `public_feed` entries into a `public_content_update` DatasetVersion, then add content-hash drift and a read-only report preview. Production write-through remains a separate authorization gate.
