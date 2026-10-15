"""browser-use collector — AI-driven browser automation, via the sidecar bridge.

Accepts a natural-language task and lets an LLM decide how to navigate, click,
fill forms, and extract data. Unlike PlaywrightBrowserCollector (fixed
extract_mode), the task is open-ended.

The browser-use library is deliberately NOT installed in this image: version
0.13.x hard-pins a dependency set (pydantic, openai, google-api-python-client,
protobuf, websockets ...) that would add ~190 packages to the lock and downgrade
18 existing ones, including protobuf across a major version. It runs in its own
container instead — `configs/bridges/browser-use-bridge` — and this collector is
an HTTP client for it, the same shape as the Maigret and SpiderFoot sidecars.

Environment variables:
    BROWSER_USE_BRIDGE_URL   Base URL of the bridge container
                             (default: http://browser-use:5002)
    BROWSER_USE_TIMEOUT      Per-task timeout in seconds (default: 120).
                             The bridge also caps the task itself.
    BROWSER_USE_BRIDGE_KEY   Optional bearer token for the bridge
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)
from data_intelligence_hub.collectors.outbound_policy import assert_collector_allowed

_DEFAULT_BRIDGE_URL = "http://browser-use:5002"
_DEFAULT_TIMEOUT = 120


def _bridge_url() -> str:
    return os.environ.get("BROWSER_USE_BRIDGE_URL", "").strip().rstrip("/") or _DEFAULT_BRIDGE_URL


def _bridge_headers() -> dict[str, str]:
    key = os.environ.get("BROWSER_USE_BRIDGE_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _timeout() -> int:
    try:
        value = int(os.environ.get("BROWSER_USE_TIMEOUT", _DEFAULT_TIMEOUT))
    except ValueError:
        return _DEFAULT_TIMEOUT
    return value if value > 0 else _DEFAULT_TIMEOUT


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CollectorError("url must be an absolute HTTP or HTTPS URL")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.startswith("192.168."):
        raise CollectorError("private or loopback URLs are not allowed")


class BrowserUseCollector(BaseCollector):
    """AI-driven browser automation: natural language task → structured extraction."""

    collector_type = "browser_use_task"

    def validate_config(self) -> dict[str, Any]:
        task = require_text(self.config, "task")
        url = self.config.get("url", "").strip()
        if url:
            _assert_public_url(url)
        max_steps = int(self.config.get("max_steps", 10))
        if max_steps < 1 or max_steps > 50:
            raise CollectorError("max_steps must be between 1 and 50")
        return {"task": task, "url": url, "max_steps": max_steps}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        base = _bridge_url()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(f"{base}/health", headers=_bridge_headers())
        except httpx.HTTPError as exc:
            msg = f"browser-use bridge unreachable at {base}: {exc.__class__.__name__}"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("browser_use_test_failed", msg, level="error")],
            )

        if response.status_code != 200:
            msg = f"browser-use bridge returned HTTP {response.status_code}"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("browser_use_test_failed", msg, level="error")],
            )

        body = response.json()
        # /health works even when the LLM key is missing, so surface that here
        # instead of letting the first collection fail.
        if body.get("status") != "ok":
            reason = body.get("llm_error") or body.get("cdp_error") or "degraded"
            return CollectorTestResult(
                status="failed",
                message=f"browser-use bridge degraded: {reason}",
                logs=[collector_log("browser_use_test_failed", str(reason), level="error")],
            )

        message = (
            f"browser-use {body.get('browser_use', '?')} ready "
            f"(provider={body.get('provider')} model={body.get('model')} "
            f"backend={body.get('backend')})"
        )
        return CollectorTestResult(
            status="ok",
            message=message,
            logs=[collector_log("browser_use_test_ok", message)],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        config = self.validate_config()
        task: str = config["task"]
        start_url: str = config["url"]
        max_steps: int = config["max_steps"]
        logs: list[dict[str, Any]] = []
        collected_at = datetime.now(UTC)

        base = _bridge_url()
        timeout = _timeout()
        # The bridge's own budget is `timeout` plus browser-session cleanup. Measured
        # runs overran it (a 50s budget returned after 106s) because cancelling an
        # in-flight agent is not immediate, so wait well past the budget and let the
        # bridge report a structured error rather than losing it to a read timeout.
        http_timeout = timeout + 120
        payload = {
            "task": task,
            "url": start_url,
            "max_steps": max_steps,
            "timeout": timeout,
        }

        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                response = await client.post(
                    f"{base}/v1/run", json=payload, headers=_bridge_headers()
                )
        except httpx.HTTPError as exc:
            msg = (
                f"browser_use_bridge_error: {base} unreachable "
                f"({exc.__class__.__name__})"
            )
            return CollectionResult(
                raw_records=[], errors=[msg],
                logs=[collector_log("browser_use_error", msg, level="error")],
            )

        if response.status_code != 200:
            msg = f"browser_use_bridge_error: HTTP {response.status_code}"
            return CollectionResult(
                raw_records=[], errors=[msg],
                logs=[collector_log("browser_use_error", msg, level="error")],
            )

        body = response.json()
        if not body.get("ok"):
            msg = f"browser_use_task_failed: {body.get('error', 'unknown error')}"
            return CollectionResult(
                raw_records=[], errors=[msg],
                logs=[collector_log("browser_use_error", msg, level="error")],
            )

        logs.append(
            collector_log(
                "browser_use_done",
                f"steps={body.get('steps')} success={body.get('success')} "
                f"backend={body.get('backend')} duration_ms={body.get('duration_ms')}",
            )
        )

        record = CollectorRawRecord(
            record_type="web_page",
            source_url=start_url or "browser_use://task",
            content={
                "task": task,
                "start_url": start_url,
                "result": body.get("result"),
                "success": body.get("success"),
                "steps_taken": body.get("steps"),
                "visited_urls": body.get("urls") or [],
                "provider": body.get("provider"),
                "model": body.get("model"),
                "backend": body.get("backend"),
                "duration_ms": body.get("duration_ms"),
            },
            collected_at=collected_at,
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=[])
