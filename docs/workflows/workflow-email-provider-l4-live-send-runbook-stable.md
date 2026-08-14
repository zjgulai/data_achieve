---
title: Email Provider L4 Live Send Runbook
doc_type: workflow
module: data-scrapy
topic: email-provider-live-send
status: stable
created: 2026-06-30
updated: 2026-06-30
owner: self
source: human+ai
---

# Email Provider L4 Live Send Runbook

This runbook is the approval gate for a single email provider live-send smoke. It does not authorize broad production email delivery, scheduler email delivery, or provider calls outside the listed one-run scope.

## Evidence Layers

| Layer | Allowed action | Evidence |
|---|---|---|
| L2 local contract | Run local tests and readiness API against local/mock settings | `bash scripts/verify-mvp.sh`, targeted notification tests |
| L3 production read-only | Read deployed version, health, redacted readiness, and config presence/counts | production health/version output, readiness response with no secrets |
| L4 authorized live | Send one allowlisted email through `live-send` with an approved `approval_id` and `Idempotency-Key` | `EmailProviderLiveSendRun` with `status=sent`, provider call count 1, replay count 0 |

## Preconditions

1. Local gate is clean: `bash scripts/verify-mvp.sh`.
2. Deployment identity is verified using `.codex/commands.md` production identity probe.
3. Readiness endpoint is available:
   - `GET /api/notifications/email-channel/live-send-readiness`
4. Readiness response is reviewed:
   - `send_enabled=true`
   - `recipient_allowlist_configured=true`
   - `recipient_allowlist_count>=1`
   - `channel_status.configured=true`
   - `provider_call_allowed=false`
   - `email_send_allowed=false`
   - `production_write_allowed=false`
   - `provider_call_attempted=false`
5. Human approval is recorded outside the API response as `approval_id`.
6. The recipient is already in `EMAIL_LIVE_RECIPIENT_ALLOWLIST`.

## Execution

1. Create a preflight gate run:
   - `POST /api/notifications/email-channel/provider-live-gate`
   - Body: `authorized=true`, `confirm_prepare=true`, `operation=email_channel_test`, `max_provider_calls=1`
   - Header: `Idempotency-Key`
2. Confirm gate run:
   - `status=ready_pending_live_authorization`
   - `provider_call_attempted=false`
3. Execute one live-send smoke:
   - `POST /api/notifications/email-channel/live-send`
   - Body: `authorized=true`, `confirm_send=true`, `gate_run_id`, `approval_id`, `operation=email_channel_test`
   - Header: `Idempotency-Key`
4. Immediately replay the same request once:
   - Expected: same `EmailProviderLiveSendRun`, `idempotency_replayed=true`, `provider_call_attempted=false`.

## Stop Conditions

- Readiness status is `blocked`.
- `recipient_allowlist_count=0`.
- `channel_status.configured=false`.
- `approval_id` is missing.
- The first `live-send` returns `delivery_failed`.
- Replay creates a new run or attempts a provider call.

## Rollback

1. Set `EMAIL_LIVE_SEND_ENABLED=false`.
2. Remove the smoke recipient from `EMAIL_LIVE_RECIPIENT_ALLOWLIST`.
3. Restart the API service.
4. Re-check readiness and confirm:
   - `status=blocked`
   - `send_enabled=false`
   - `provider_call_allowed=false`
   - `provider_call_attempted=false`

## Boundary

This runbook only covers one manually approved email-channel smoke. Report send, drift alert email, scheduler-triggered email, broader allowlists, and repeated production sends each require separate approval and evidence.
