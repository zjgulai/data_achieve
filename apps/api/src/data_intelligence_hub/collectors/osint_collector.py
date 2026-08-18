"""OSINT collectors — username presence search across social networks.

Wraps the sherlock-project CLI (pip install sherlock-project) and
maigret (pip install maigret) to check whether a username exists
across hundreds of platforms.

Environment variables (all optional):
    OSINT_TIMEOUT   Per-site request timeout in seconds (default: 15)
    OSINT_PROXY     HTTP/SOCKS proxy URL forwarded to sherlock/maigret
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)

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
                "--print-found",
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

            # Parse the CSV output produced by sherlock
            csv_path = Path(tmpdir) / f"{username}.csv"
            results: dict[str, str] = {}
            if csv_path.exists():
                import csv
                with csv_path.open(newline="", encoding="utf-8") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        site_name = row.get("name") or row.get("username") or ""
                        url = row.get("url", "")
                        if url:
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
                f"username={username!r} found_on={len(results)} sites",
            )
        )

        record = CollectorRawRecord(
            record_type="account",
            source_url=None,
            content={
                "username": username,
                "found_on": results,
                "total_found": len(results),
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
    """Build a cross-platform dossier from a username via maigret (3000+ sites)."""

    collector_type = "maigret"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        max_sites = int(self.config.get("max_sites", 500))
        if max_sites < 1 or max_sites > 3000:
            raise CollectorError("config.max_sites must be between 1 and 3000")
        return {"username": username, "max_sites": max_sites}

    async def test(self) -> CollectorTestResult:
        if not _maigret_available():
            msg = "maigret not found — install with: uv pip install maigret"
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("maigret_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message="maigret binary found",
            logs=[collector_log("maigret_test_ok", "binary present")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        if not _maigret_available():
            msg = "maigret binary not found; install maigret"
            errors.append(msg)
            logs.append(collector_log("maigret_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        username: str = config["username"]
        max_sites: int = config["max_sites"]
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / f"{username}.json"
            cmd = [
                "maigret",
                username,
                "--json", "ndjson",
                "--output", str(report_path),
                "--top-sites", str(max_sites),
                "--timeout", _timeout(),
                "--no-progressbar",
            ]
            cmd += _proxy_args()

            try:
                rc, stdout, stderr = await _run(cmd, timeout=600.0)
            except CollectorError as exc:
                errors.append(str(exc))
                logs.append(
                    collector_log("maigret_collect_error", str(exc), level="error")
                )
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            results: dict[str, Any] = {}
            if report_path.exists():
                try:
                    raw_json = json.loads(report_path.read_text(encoding="utf-8"))
                    results = raw_json if isinstance(raw_json, dict) else {}
                except (json.JSONDecodeError, OSError):
                    pass

        found_sites = [
            k for k, v in results.items()
            if isinstance(v, dict) and v.get("status") == "Claimed"
        ]
        logs.append(
            collector_log(
                "maigret_collected",
                f"username={username!r} claimed_on={len(found_sites)} sites",
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
                "tool": "maigret",
                "rc": rc,
            },
            collected_at=collected_at,
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
