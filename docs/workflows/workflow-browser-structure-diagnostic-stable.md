---
title: Browser Structure Diagnostic Workflow
doc_type: workflow
module: data-scrapy
topic: browser-structure-diagnostic
status: stable
created: 2026-06-19
updated: 2026-06-19
owner: self
source: human+ai
---

# Browser Structure Diagnostic Workflow

## Purpose

Browser structure diagnostic is a read-only evidence step between static URL preflight and
real data collection. It answers four questions before a collector is selected:

1. Is the useful data visible after browser rendering?
2. Does the page expose stable API, JSON, JSON-LD, table, list, or card signals?
3. Is the page more suitable for static HTML, browser automation, official API/file import,
   RPA, or manual review?
4. What evidence should be kept before building field extraction and cleaning scripts?

## Boundary

- Run only on public URLs that the operator is authorized to inspect.
- Do not use it for login walls, account pages, captcha flows, private data, or anti-bot bypass.
- The script does not create Source, Task, Run, Dataset, Report, or production records.
- The script does not read or export cookies.
- When using real Chrome, the browser process may carry ambient local profile state. Treat that as
  a diagnostic risk and do not use it to inspect private pages.

## Command

```bash
scripts/browser-structure-diagnostic.py \
  --authorized \
  --url https://example.com \
  --harness-bin /Users/pray/.local/bin/browser-harness \
  --output tmp/outputs/browser-diagnostics/example-com.json \
  --screenshot tmp/outputs/browser-diagnostics/example-com.png
```

## Output Contract

The JSON output uses `browser_structure_diagnostic.v1` and includes:

- `run_policy`: authorization, read-only status, cookie-export status, and production-write status.
- `visible_text`: rendered visible text length, line count, and sample.
- `dom_counters`: links, forms, inputs, buttons, tables, lists, articles, cards, images, scripts,
  stylesheets, and JSON-LD blocks.
- `network_summary`: resource counts, initiator counts, XHR/fetch count, and API candidates with
  query strings redacted.
- `accessibility_summary`: role counts and named accessibility nodes.
- `risk_flags`: login/auth signal, forms, dynamic rendering, third-party surface, or diagnostic
  error signals.
- `extraction_strategy`: recommended path, fit, confidence, field stability, reasons, next steps,
  and cleaning notes.
- `evidence`: screenshot path and non-secret diagnostic errors.

## Recommended Path Rules

| Path | When to Use | Next Step |
| --- | --- | --- |
| `generic_web` | Rendered page has stable visible text and low dynamic dependency. | Build DOM field contract and run low-frequency public page collection. |
| `official_api_or_file` | Runtime resources reveal API, JSON, or structured data candidates. | Verify authorization and schema stability before building a structured collector. |
| `browser_automation` | Static HTML is likely a shell and useful fields render at runtime. | Capture selectors, screenshots, and missing-field rates before automation. |
| `manual_review` | Forms, login signals, or weak structure make automation unsafe. | Confirm public boundary and platform-specific SOP before collecting. |
| `blocked_review` | Authorization is missing. | Stop until authorization is confirmed. |

## Acceptance Evidence

Minimum local acceptance for a new diagnostic change:

```bash
cd apps/api
uv run ruff check src tests
uv run mypy src tests
uv run pytest tests/unit/test_browser_structure_diagnostic.py tests/unit/test_toolkit_preflight.py
```

Minimum browser-harness smoke:

```bash
scripts/browser-structure-diagnostic.py \
  --authorized \
  --url https://example.com \
  --harness-bin /Users/pray/.local/bin/browser-harness \
  --output tmp/outputs/browser-diagnostics/example-com-smoke.json \
  --screenshot tmp/outputs/browser-diagnostics/example-com-smoke.png
```

The smoke passes only when the JSON contains:

- `run_policy.production_write=false`
- `evidence.errors=[]`
- a non-empty `final_url`
- a clear `extraction_strategy.recommended_path`
- a screenshot file that visually matches the inspected page

## Product Integration Plan

1. Keep the CLI as the source of evidence for Phase C-2.
2. Add an optional diagnostic summary panel to `/automation` and `/toolkit`.
3. Compare static preflight strategy with browser diagnostic strategy.
4. Persist diagnostics only after queueing, timeout, and authorization boundaries are stable.
5. Never execute browser diagnostics synchronously inside the public preflight API.
