---
title: Social Provider Source Template Loop Plan
doc_type: implementation_plan
topic: overseas-social-provider-source-template
status: draft
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
created: 2026-07-08
updated: 2026-07-08
owner: self
source: codex
---

# Social Provider Source Template Loop Plan

## Plan

- Close PR #11 CI gate first; do not widen while checks are red or pending.
- Add the next unfinished fixture boundary: a no-write source template preview.
- Reuse existing `manual_json` as the stable import fallback instead of adding a live `social_api` collector.
- Preserve `provider_call=false`, `source_created=false`, `task_created=false`, and `production unchanged`.

## Work

- Add `POST /api/automation/social-provider-source-template`.
- Return a SourceCreate-shaped payload with `type=manual_json`.
- Include provider, platform, endpoint, fixture, author-policy, and forbidden-action metadata.
- Ignore `authorized`, `approval_id`, and `credential_reference` in this preview and return blockers.

## Review

- Unit tests cover payload generation and live-field blockers.
- Integration tests cover authenticated route behavior.
- Final gates: ruff, py_compile, pytest, uv lock check, git diff checks, and PR check readback.

## Compound

- This loop keeps source creation as a future L4 gate.
- The next implementation slice can add a real `social_api` collector only after a separate authorization design for DB writes and task runs.
- Live provider calls remain out of scope until an owner-approved L4 packet exists.
