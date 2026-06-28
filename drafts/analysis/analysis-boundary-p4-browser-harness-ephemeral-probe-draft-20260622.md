---
title: P4 Browser-Harness Ephemeral Probe Execution Evidence
doc_type: analysis
module: automation
topic: boundary-p4-browser-harness
status: draft
created: 2026-06-22
updated: 2026-06-22
owner: self
source: human+ai
---

# P4 Browser-Harness Ephemeral Probe Execution Evidence

## Scope

This pass executed only the P4 local-only browser-harness adapter spike.

Allowed:

- Add a fail-closed local runner guard for `ephemeral_browser_harness_probe`.
- Require an explicit dedicated CDP endpoint before browser-harness can run.
- Run a local isolated headless Chrome smoke against `https://example.com/`.
- Keep product result assets read-only.

Explicitly not executed:

- Production deploy.
- Production browser run.
- Provider call.
- External email send.
- Scheduler mutation.
- Dataset export.
- Source, Task, TaskRun, Dataset, AlertEvent, Notification, or email creation from browser probe.
- User Chrome profile, cookie, or login-state reuse.

## Implementation Facts

- `AutomationBrowserLocalRunnerRequest` now accepts `browser_harness_cdp_url`.
- `run_mode=ephemeral_browser_harness_probe` is fail-closed without that CDP URL and records `blocked_ephemeral_probe`.
- The runner sets `BU_CDP_URL` only from the explicit request field and removes inherited `BU_CDP_WS` before invoking `browser-harness`.
- The executor contract now records `runtime_isolation.requires_dedicated_cdp_url=true`.
- Probe result metadata records `isolated_cdp_configured`, sanitized `cdp_endpoint`, `files_written=false`, and `collection_resources_written=false`.
- Redaction now removes `Authorization`, `Cookie`, and `Set-Cookie` markers from stdout/stderr tails.
- `/automation` can display `browser_harness_isolated_cdp_required` as a blocked reason.

## Local Isolated Smoke

Dedicated browser:

```text
Chrome binary=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
mode=headless
remote_debugging_port=9333
user_data_dir=/tmp/data-scrapy-p4-chrome-20260622T095755Z
target_url=https://example.com/
```

Read-only CDP readiness:

```text
GET http://127.0.0.1:9333/json/version
Browser=Chrome/149.0.7827.155
Protocol-Version=1.3
```

Browser-harness invocation boundary:

```text
BU_CDP_URL=http://127.0.0.1:9333
BU_NAME=data-scrapy-p4
BH_RUNTIME_DIR=/tmp/data-scrapy-p4-bh-20260622T095755Z
```

Observed CLI output:

```json
{"ok": true, "page_info": {"url": "https://example.com/", "title": "Example Domain", "w": 756, "h": 469, "sx": 0, "sy": 0, "pw": 756, "ph": 469}, "target_tab_closed": false}
{"target_tab_closed": true}
```

Post-run process check:

```text
lsof -nP -iTCP:9333 -sTCP:LISTEN
exit_code=1
meaning=no listener remains on port 9333
```

## Validation

API:

```text
cd apps/api
uv run pytest tests/integration/test_sources_tasks.py -k browser_automation_plan_persists_read_only_draft
result=1 passed, 18 deselected

uv run pytest tests/integration/test_sources_tasks.py
result=19 passed

uv run pytest
result=102 passed, 1 warning

uv run ruff check src tests
result=All checks passed
```

Web:

```text
pnpm --dir apps/web lint
result=passed

pnpm --dir apps/web test
result=8 passed

pnpm --dir apps/web exec playwright test --grep "browser automation diagnostic|automation workbench"
result=4 passed

pnpm --dir apps/web build
result=passed on standalone rerun
```

Diff:

```text
git diff --check
result=passed
```

## Evidence Grade

- Code/tests: `L2-fixture-or-dry-run`; fake browser-harness covers success, missing CDP, missing binary, timeout, and redaction paths.
- Local isolated CLI smoke: `L1-public-or-runtime`; proves local browser-harness can use a dedicated headless Chrome CDP endpoint for a public page.
- Production capability: not claimed. No production deploy or production browser run occurred.

## Boundary Result

P4 local adapter guard is complete for the current spike:

- `browser_started=true` is proven only by the local isolated CLI smoke and fake integration success path.
- Product route cannot silently reuse the user's default Chrome profile because it blocks without `browser_harness_cdp_url`.
- `files_written=false` and `collection_resources_written=false` remain enforced in the product result contract.

Next work should be selector DOM evaluation and network metadata summary under the same dedicated-CDP requirement. Screenshot, trace, HAR file writes, production browser execution, provider calls, email sends, scheduler mutations, and dataset exports remain separate gates.
