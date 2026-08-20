"""Blackbird Email OSINT collector — email address search across 574+ sites.

Blackbird (github.com/p1ngul1n0/blackbird) is a username/email OSINT tool
that complements Maigret by supporting email lookups and covering different
site databases (574 sites vs Maigret's 3000, but with email support).

Must be self-hosted and run with --web flag.
Start: python blackbird.py --web 5002

Environment variables:
    BLACKBIRD_BASE_URL   Base URL of Blackbird web server (required)
                         e.g. http://localhost:5002
    HTTP_PROXY           Optional proxy forwarded to httpx
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)


def _base_url() -> str:
    url = os.environ.get("BLACKBIRD_BASE_URL", "").strip().rstrip("/")
    if not url:
        raise CollectorError(
            "BLACKBIRD_BASE_URL is not set — "
            "self-host Blackbird with --web 5002 and set this env var"
        )
    return url


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(
        timeout=60.0,
        proxy=proxy or None,
        follow_redirects=True,
    )


class BlackbirdEmailCollector(BaseCollector):
    collector_type = "blackbird_email_osint"

    def validate_config(self) -> dict[str, Any]:
        email = require_text(self.config, "email")
        if "@" not in email:
            raise CollectorError("email must contain @")
        return {"email": email}

    async def test(self) -> CollectorTestResult:
        try:
            base = _base_url()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("blackbird_test_failed", str(exc), level="error")],
            )
        try:
            async with _client() as c:
                r = await c.get(f"{base}/health")
            if r.status_code not in {200, 204}:
                msg = f"Blackbird returned HTTP {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("blackbird_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("blackbird_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message=f"Blackbird reachable at {base}",
            logs=[collector_log("blackbird_test_ok", base)],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        email: str = config["email"]

        base = _base_url()
        try:
            async with _client() as c:
                r = await c.post(
                    f"{base}/search",
                    json={"query": email, "type": "email"},
                )
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("blackbird_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        body = r.json()
        results: list[dict[str, Any]] = []
        if isinstance(body, list):
            results = body
        elif isinstance(body, dict):
            results = body.get("results") or body.get("data") or body.get("matches") or []

        found = [m for m in results if m.get("found") or m.get("status") == "found"]

        record = CollectorRawRecord(
            record_type="osint_report",
            source_url=None,
            content={
                "email": email,
                "total_sites": len(results),
                "found_count": len(found),
                "matches": found,
                "all_results": results,
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "blackbird_collected",
                f"email={email!r} found={len(found)}/{len(results)}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


class BlackbirdUsernameCollector(BaseCollector):
    collector_type = "blackbird_username_osint"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        return {"username": username}

    async def test(self) -> CollectorTestResult:
        try:
            base = _base_url()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("blackbird_test_failed", str(exc), level="error")],
            )
        try:
            async with _client() as c:
                r = await c.get(f"{base}/health")
            if r.status_code not in {200, 204}:
                msg = f"Blackbird returned HTTP {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("blackbird_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("blackbird_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message=f"Blackbird reachable at {base}",
            logs=[collector_log("blackbird_test_ok", base)],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        username: str = config["username"]

        base = _base_url()
        try:
            async with _client() as c:
                r = await c.post(
                    f"{base}/search",
                    json={"query": username, "type": "username"},
                )
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("blackbird_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        body = r.json()
        results: list[dict[str, Any]] = []
        if isinstance(body, list):
            results = body
        elif isinstance(body, dict):
            results = body.get("results") or body.get("data") or body.get("matches") or []

        found = [m for m in results if m.get("found") or m.get("status") == "found"]

        record = CollectorRawRecord(
            record_type="osint_report",
            source_url=None,
            content={
                "username": username,
                "total_sites": len(results),
                "found_count": len(found),
                "matches": found,
                "all_results": results,
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "blackbird_collected",
                f"username={username!r} found={len(found)}/{len(results)}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
