"""OSINT collectors — username presence search across social networks.

Wraps the sherlock-project CLI (pip install sherlock-project) and
maigret (pip install maigret) to check whether a username exists
across hundreds of platforms.

Environment variables (all optional):
    OSINT_TIMEOUT        Per-site request timeout in seconds (default: 15)
    OSINT_PROXY          HTTP/SOCKS proxy URL forwarded to sherlock/maigret
    MAIGRET_URL          Maigret sidecar base URL, e.g. http://maigret:5000.
                         When set, MaigretCollector scans through the sidecar
                         (primary) and falls back to the CLI on failure.
    MAIGRET_SIDECAR_TIMEOUT
                         Overall sidecar scan budget in seconds (default: 900)

Sidecar contract (upstream `maigret --web`, verified against soxoj/maigret):
    POST /api/scan            form field `usernames` -> {"job_id": "..."}
    GET  /api/scan/<id>/stream  SSE; events carry `type`:
                                start | found | progress | stopped | error | done
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

_DEFAULT_TIMEOUT = "15"
_SHERLOCK_MIN_SITES = 1


def _timeout() -> str:
    return os.environ.get("OSINT_TIMEOUT", _DEFAULT_TIMEOUT)


def _proxy_args() -> list[str]:
    proxy = os.environ.get("OSINT_PROXY", "").strip()
    return ["--proxy", proxy] if proxy else []


def _sherlock_available() -> bool:
    return shutil.which("sherlock") is not None


def _maigret_available() -> bool:
    return shutil.which("maigret") is not None


def _maigret_url() -> str:
    """Sidecar base URL, empty string when the sidecar is not configured."""
    return os.environ.get("MAIGRET_URL", "").strip().rstrip("/")


def _maigret_sidecar_timeout() -> float:
    raw = os.environ.get("MAIGRET_SIDECAR_TIMEOUT", "")
    try:
        value = float(raw)
    except ValueError:
        return 900.0
    return value if value > 0 else 900.0


async def _maigret_sidecar_scan(username: str) -> dict[str, dict[str, Any]]:
    """Scan one username through the Maigret sidecar and return claimed sites.

    Returns a mapping of site name -> {"status", "url", "ids", "username"}.
    Raises CollectorError when the sidecar is unusable, so the caller can
    fall back to the CLI (ADR-001 collector-level fallback).
    """
    base = _maigret_url()
    budget = _maigret_sidecar_timeout()
    found: dict[str, dict[str, Any]] = {}
    scan_errors: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = await client.post(f"{base}/api/scan", data={"usernames": username})
            start.raise_for_status()
            job_id = (start.json() or {}).get("job_id")
            if not job_id:
                raise CollectorError(
                    f"maigret sidecar returned no job_id: {start.text[:200]!r}"
                )

            deadline = time.monotonic() + budget
            stream_timeout = httpx.Timeout(30.0, read=budget)
            async with client.stream(
                "GET", f"{base}/api/scan/{job_id}/stream", timeout=stream_timeout
            ) as stream:
                stream.raise_for_status()
                async for line in stream.aiter_lines():
                    if time.monotonic() > deadline:
                        raise CollectorError(
                            f"maigret sidecar scan exceeded {budget:.0f}s"
                        )
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if not payload:
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    if event_type == "found":
                        site = str(event.get("site") or "unknown")
                        found[site] = {
                            "status": "Claimed",
                            "url": event.get("url"),
                            "ids": event.get("ids") or {},
                            "username": event.get("username") or username,
                        }
                    elif event_type in {"error", "stopped"}:
                        # Keep the site, but record why the scan stopped early.
                        scan_errors.append(str(event.get("message") or event_type))
                    elif event_type == "done":
                        break
    except httpx.HTTPError as exc:
        raise CollectorError(
            f"maigret sidecar request failed: {exc.__class__.__name__}: {exc}"
        ) from exc

    if not found and scan_errors:
        raise CollectorError(
            "maigret sidecar scan produced no results: " + "; ".join(scan_errors[:3])
        )
    return found


def _maigret_entry_is_claimed(entry: Any) -> bool:
    """Maigret nests the check result under `status`; accept both shapes."""
    if not isinstance(entry, dict):
        return False
    status = entry.get("status")
    if isinstance(status, dict):
        return str(status.get("status") or "") == "Claimed"
    return str(status or "") == "Claimed"


def _maigret_entry_url(entry: Any) -> str:
    """Site profile URL — nested under `status` in CLI reports, top-level from
    the sidecar's `found` events."""
    if not isinstance(entry, dict):
        return ""
    status = entry.get("status")
    if isinstance(status, dict):
        url = status.get("url")
        if url:
            return str(url)
    return str(entry.get("url_user") or entry.get("url") or "")


def _load_maigret_report(path: Path) -> dict[str, Any]:
    """Parse a `--json simple` report; tolerate ndjson and truncated output."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # `--json ndjson` writes one JSON object per line.
        parsed = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                site = str(row.get("sitename") or row.get("site_name") or "")
                if site:
                    parsed[site] = row
    return parsed if isinstance(parsed, dict) else {}


async def _run(cmd: list[str], timeout: float = 120.0) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise CollectorError(
            f"osint_timeout: command took longer than {timeout:.0f}s"
        ) from None
    return (
        proc.returncode or 0,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


# ─────────────────────────────────────────────
#  SherlockCollector
# ─────────────────────────────────────────────


class SherlockCollector(BaseCollector):
    """Check a username across 400+ social networks via sherlock."""

    collector_type = "sherlock"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        sites = self.config.get("sites", [])
        if not isinstance(sites, list):
            raise CollectorError("config.sites must be a list of site names")
        return {"username": username, "sites": sites}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        if not _sherlock_available():
            msg = (
                "sherlock not found — install with: "
                "uv pip install sherlock-project"
            )
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("sherlock_test_failed", msg, level="error")],
            )
        rc, stdout, _ = await _run(["sherlock", "--version"])
        if rc != 0:
            msg = f"sherlock --version failed (rc={rc})"
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("sherlock_test_failed", msg, level="error")],
            )
        version = stdout.strip().splitlines()[0] if stdout.strip() else "unknown"
        return CollectorTestResult(
            status="ok",
            message=f"sherlock available: {version}",
            logs=[collector_log("sherlock_test_ok", version)],
        )

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        if not _sherlock_available():
            msg = "sherlock binary not found; install sherlock-project"
            errors.append(msg)
            logs.append(collector_log("sherlock_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        username: str = config["username"]
        sites: list[str] = config["sites"]
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "sherlock",
                username,
                "--timeout", _timeout(),
                "--print-all",
                "--folderoutput", tmpdir,
                "--csv",
            ]
            if sites:
                for site in sites:
                    cmd += ["--site", site]
            cmd += _proxy_args()

            try:
                rc, stdout, stderr = await _run(cmd, timeout=300.0)
            except CollectorError as exc:
                errors.append(str(exc))
                logs.append(
                    collector_log("sherlock_collect_error", str(exc), level="error")
                )
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            # Parse the CSV output produced by sherlock.
            # Upstream columns: username,name,url_main,url_user,exists,
            # http_status,response_time_s — the profile URL lives in `url_user`
            # and `exists` holds the check status (Claimed/Available/...).
            csv_path = Path(tmpdir) / f"{username}.csv"
            results: dict[str, str] = {}
            status_counts: dict[str, int] = {}
            if csv_path.exists():
                with csv_path.open(newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        site_name = row.get("name") or row.get("username") or ""
                        status = (row.get("exists") or "").strip() or "Unknown"
                        status_counts[status] = status_counts.get(status, 0) + 1
                        url = row.get("url_user") or row.get("url_main") or ""
                        if status == "Claimed" and url:
                            results[site_name] = url
            else:
                # Fallback: parse stdout lines that look like "[+] Site: URL"
                for line in stdout.splitlines():
                    if line.startswith("[+]"):
                        parts = line[3:].strip().split(":", 1)
                        if len(parts) == 2:
                            results[parts[0].strip()] = parts[1].strip()

        logs.append(
            collector_log(
                "sherlock_collected",
                f"username={username!r} found_on={len(results)} sites "
                f"checked={sum(status_counts.values())}",
            )
        )

        record = CollectorRawRecord(
            record_type="account",
            source_url=None,
            content={
                "username": username,
                "found_on": results,
                "total_found": len(results),
                "sites_checked": sum(status_counts.values()),
                "status_counts": status_counts,
                "tool": "sherlock",
                "rc": rc,
                "stderr_tail": stderr[-500:] if stderr else "",
            },
            collected_at=collected_at,
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  MaigretCollector
# ─────────────────────────────────────────────


class MaigretCollector(BaseCollector):
    """Build a cross-platform dossier from a username via maigret (3000+ sites).

    Uses the deployed Maigret sidecar (``MAIGRET_URL``) as the primary backend
    and falls back to the CLI when the sidecar is unavailable (ADR-001).

    Note: the sidecar takes its scan options (top_sites, tags, proxy) from its
    own settings.json — ``config.max_sites`` only applies to the CLI path.
    """

    collector_type = "maigret"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        max_sites = int(self.config.get("max_sites", 500))
        if max_sites < 1 or max_sites > 3000:
            raise CollectorError("config.max_sites must be between 1 and 3000")
        return {"username": username, "max_sites": max_sites}

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        sidecar = _maigret_url()
        if sidecar:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(f"{sidecar}/api/sites")
                if r.status_code == 200:
                    return CollectorTestResult(
                        status="ok",
                        message=f"maigret sidecar reachable at {sidecar}",
                        logs=[collector_log("maigret_test_ok", f"sidecar {sidecar}")],
                    )
                msg = f"maigret sidecar returned HTTP {r.status_code}"
            except httpx.HTTPError as exc:
                msg = f"maigret sidecar unreachable: {exc.__class__.__name__}"
            # Sidecar is configured but broken — the CLI can still work.
            if _maigret_available():
                return CollectorTestResult(
                    status="degraded",
                    message=f"{msg}; CLI fallback available",
                    logs=[collector_log("maigret_test_degraded", msg, level="warning")],
                )
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("maigret_test_failed", msg, level="error")],
            )

        if not _maigret_available():
            msg = (
                "maigret not found — set MAIGRET_URL or install with: "
                "uv pip install maigret"
            )
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("maigret_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message="maigret binary found (no sidecar configured)",
            logs=[collector_log("maigret_test_ok", "binary present")],
        )

    async def _collect_via_cli(
        self, username: str, max_sites: int
    ) -> tuple[dict[str, Any], int]:
        """Run the maigret CLI. Returns (report_mapping, returncode)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "maigret",
                username,
                "--folderoutput", tmpdir,
                "--json", "simple",
                "--top-sites", str(max_sites),
                "--timeout", _timeout(),
                "--no-progressbar",
            ]
            cmd += _proxy_args()

            rc, _stdout, _stderr = await _run(cmd, timeout=600.0)

            # Upstream writes <folderoutput>/report_<username>_simple.json
            safe_name = username.replace("/", "_")
            report_path = Path(tmpdir) / f"report_{safe_name}_simple.json"
            if not report_path.exists():
                return {}, rc
            return _load_maigret_report(report_path), rc

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        username: str = config["username"]
        max_sites: int = config["max_sites"]
        collected_at = datetime.now(UTC)

        results: dict[str, Any] = {}
        source = ""
        rc: int | None = None

        sidecar = _maigret_url()
        if sidecar:
            try:
                claimed = await _maigret_sidecar_scan(username)
            except CollectorError as exc:
                msg = f"maigret sidecar failed, falling back to CLI: {exc}"
                logs.append(
                    collector_log("maigret_sidecar_fallback", msg, level="warning")
                )
                errors.append(str(exc))
            else:
                results = claimed
                source = "sidecar"
                if max_sites != 500:
                    logs.append(
                        collector_log(
                            "maigret_max_sites_ignored",
                            "sidecar uses its own settings.json; "
                            f"config.max_sites={max_sites} was not applied",
                            level="warning",
                        )
                    )

        if source != "sidecar":
            if not _maigret_available():
                msg = "maigret sidecar unavailable and maigret binary not found"
                errors.append(msg)
                logs.append(collector_log("maigret_collect_error", msg, level="error"))
                return CollectionResult(raw_records=[], logs=logs, errors=errors)
            try:
                results, rc = await self._collect_via_cli(username, max_sites)
            except CollectorError as exc:
                errors.append(str(exc))
                logs.append(
                    collector_log("maigret_collect_error", str(exc), level="error")
                )
                return CollectionResult(raw_records=[], logs=logs, errors=errors)
            source = "cli"

        found_sites = [k for k, v in results.items() if _maigret_entry_is_claimed(v)]
        logs.append(
            collector_log(
                "maigret_collected",
                f"username={username!r} claimed_on={len(found_sites)} sites "
                f"source={source}",
            )
        )

        record = CollectorRawRecord(
            record_type="account",
            source_url=None,
            content={
                "username": username,
                "results": results,
                "claimed_sites": found_sites,
                "total_claimed": len(found_sites),
                "profile_urls": {
                    site: _maigret_entry_url(results[site])
                    for site in found_sites
                    if _maigret_entry_url(results[site])
                },
                "tool": "maigret",
                "source": source,
                "rc": rc,
            },
            collected_at=collected_at,
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
