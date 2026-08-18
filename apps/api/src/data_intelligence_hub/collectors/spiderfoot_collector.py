"""SpiderFoot OSINT collector — wraps the SpiderFoot REST API.

SpiderFoot must be self-hosted and running before this collector can be used.
Start it with:  python sf.py -l 0.0.0.0:5001

API flow:
  1. POST /api/v1/scan/       — create a new scan, get scanId back
  2. GET  /api/v1/scan/{id}/status  — poll until status == FINISHED/ERROR
  3. GET  /api/v1/scan/{id}/results — retrieve all findings

Environment variables:
    SPIDERFOOT_BASE_URL   Base URL of the SpiderFoot instance (required)
                          e.g. http://localhost:5001
    SPIDERFOOT_TIMEOUT    Total poll timeout in seconds (default: 120)
    HTTP_PROXY            Forwarded to httpx (optional)

Supported endpoint_types:
    spiderfoot_domain_osint  — scan a domain name
    spiderfoot_ip_osint      — scan an IP address
    spiderfoot_email_osint   — scan an e-mail address
"""
from __future__ import annotations

import asyncio
import os
import time
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

_DEFAULT_TIMEOUT = 120.0
_POLL_INTERVAL = 3.0
_FINISHED_STATUSES = {"FINISHED", "ERROR", "ABORTED"}


def _base_url() -> str:
    url = os.environ.get("SPIDERFOOT_BASE_URL", "").strip().rstrip("/")
    if not url:
        raise CollectorError(
            "SPIDERFOOT_BASE_URL is not set — "
            "self-host SpiderFoot and set this env var"
        )
    return url


def _timeout() -> float:
    try:
        return float(os.environ.get("SPIDERFOOT_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(
        timeout=30.0,
        proxy=proxy or None,
        follow_redirects=True,
    )


async def _create_scan(
    target: str,
    scan_name: str,
    modules: list[str] | None = None,
) -> str:
    base = _base_url()
    payload: dict[str, Any] = {
        "scanname": scan_name,
        "scantarget": target,
        "modulelist": ",".join(modules) if modules else "",
        "typelist": "",
    }
    try:
        async with _client() as c:
            r = await c.post(f"{base}/api/v1/scan/", data=payload)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    body = r.json()
    scan_id = body.get("id") or (body[0] if isinstance(body, list) and body else None)
    if not scan_id:
        raise CollectorError(f"SpiderFoot scan creation returned no id: {body}")
    return str(scan_id)


async def _poll_scan(scan_id: str) -> str:
    base = _base_url()
    deadline = time.monotonic() + _timeout()
    while time.monotonic() < deadline:
        try:
            async with _client() as c:
                r = await c.get(f"{base}/api/v1/scan/{scan_id}/status")
                r.raise_for_status()
        except httpx.HTTPError as exc:
            raise CollectorError(collector_http_error_message(exc)) from exc

        body = r.json()
        status = ""
        if isinstance(body, dict):
            status = body.get("status", "")
        elif isinstance(body, list) and body:
            status = body[0].get("status", "") if isinstance(body[0], dict) else ""

        if status in _FINISHED_STATUSES:
            return status
        await asyncio.sleep(_POLL_INTERVAL)

    raise CollectorError(
        f"SpiderFoot scan {scan_id!r} did not finish within {_timeout():.0f}s"
    )


async def _get_results(scan_id: str) -> list[dict[str, Any]]:
    base = _base_url()
    try:
        async with _client() as c:
            r = await c.get(f"{base}/api/v1/scan/{scan_id}/results")
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    body = r.json()
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        return body.get("data") or body.get("results") or []
    return []


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if isinstance(row, (list, tuple)) and len(row) >= 4:
        return {
            "type": row[0],
            "module": row[1],
            "source": row[2],
            "data": row[3],
            "created": row[4] if len(row) > 4 else "",
            "risk": row[5] if len(row) > 5 else "",
        }
    return {"raw": row}


class _SpiderFootCollector(BaseCollector):
    _target_type: str = ""

    def validate_config(self) -> dict[str, Any]:
        target = require_text(self.config, "target")
        modules: list[str] = self.config.get("modules", [])
        if not isinstance(modules, list):
            raise CollectorError("config.modules must be a list of module name strings")
        return {"target": target, "modules": modules}

    async def test(self) -> CollectorTestResult:
        try:
            base = _base_url()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("spiderfoot_test_failed", str(exc), level="error")],
            )
        try:
            async with _client() as c:
                r = await c.get(f"{base}/api/v1/scanlist")
            if r.status_code not in {200, 204}:
                msg = f"SpiderFoot returned HTTP {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("spiderfoot_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("spiderfoot_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message=f"SpiderFoot reachable at {base}",
            logs=[collector_log("spiderfoot_test_ok", base)],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        target: str = config["target"]
        modules: list[str] = config["modules"]

        try:
            scan_name = f"dih-{self._target_type}-{target[:30]}"
            scan_id = await _create_scan(target, scan_name, modules or None)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("spiderfoot_create_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(collector_log("spiderfoot_scan_started", f"scan_id={scan_id!r}"))

        try:
            final_status = await _poll_scan(scan_id)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("spiderfoot_poll_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if final_status != "FINISHED":
            msg = f"SpiderFoot scan ended with status={final_status!r}"
            errors.append(msg)
            logs.append(collector_log("spiderfoot_scan_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        try:
            raw_rows = await _get_results(scan_id)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("spiderfoot_results_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        rows = [_row_to_dict(r) for r in raw_rows]

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            rtype = str(row.get("type", "UNKNOWN"))
            grouped.setdefault(rtype, []).append(row)

        record = CollectorRawRecord(
            record_type="osint_report",
            source_url=None,
            content={
                "target": target,
                "target_type": self._target_type,
                "scan_id": scan_id,
                "total_findings": len(rows),
                "finding_types": list(grouped.keys()),
                "findings_by_type": grouped,
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "spiderfoot_collected",
                f"target={target!r} findings={len(rows)} types={len(grouped)}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


class SpiderFootDomainCollector(_SpiderFootCollector):
    """Run a SpiderFoot OSINT scan against a domain name."""
    collector_type = "spiderfoot_domain_osint"
    _target_type = "domain"


class SpiderFootIPCollector(_SpiderFootCollector):
    """Run a SpiderFoot OSINT scan against an IP address."""
    collector_type = "spiderfoot_ip_osint"
    _target_type = "ip"


class SpiderFootEmailCollector(_SpiderFootCollector):
    """Run a SpiderFoot OSINT scan against an e-mail address."""
    collector_type = "spiderfoot_email_osint"
    _target_type = "email"
