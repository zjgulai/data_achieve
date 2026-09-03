"""Aliens_eye OSINT collector — ML-powered username scanning across 840+ platforms.

Wraps the aliens-eye CLI (pip install aliens-eye).
Unique capabilities vs sherlock/maigret:
  - ML + 30-signal heuristic detection (not naive HTTP status codes)
  - 840+ platforms (vs sherlock 500+)
  - Cross-site correlation (same person across platforms)
  - Recursive expansion (follow usernames found in bios)
  - Domain registration check
  - Change monitoring with webhook alerts
  - Multiple output formats: JSON, CSV, HTML, Markdown, PDF, GEXF

Environment variables (all optional):
    OSINT_TIMEOUT         Per-site request timeout in seconds (default: 30)
    OSINT_PROXY           HTTP/SOCKS proxy URL forwarded to aliens_eye
    ALIENS_EYE_NO_ML      Set to "1" to disable ML and use heuristics only
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

_DEFAULT_TIMEOUT = 120.0
_DEFAULT_SITE_TIMEOUT = "30"


def _timeout() -> float:
    try:
        return float(os.environ.get("OSINT_TIMEOUT", _DEFAULT_SITE_TIMEOUT)) * 10
    except ValueError:
        return _DEFAULT_TIMEOUT


def _proxy_args() -> list[str]:
    proxy = os.environ.get("OSINT_PROXY", "").strip()
    return ["--proxy", proxy] if proxy else []


def _no_ml_args() -> list[str]:
    return ["--no-ml"] if os.environ.get("ALIENS_EYE_NO_ML", "") == "1" else []


def _aliens_eye_available() -> bool:
    return (
        shutil.which("aliens_eye") is not None
        or shutil.which("aliens-eye") is not None
        or Path("/app/.local/bin/aliens_eye").exists()
    )


def _aliens_eye_cmd() -> str:
    for candidate in ("aliens_eye", "aliens-eye", "/app/.local/bin/aliens_eye"):
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    return "aliens_eye"


async def _run(cmd: list[str], timeout: float = _DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise CollectorError(
            f"aliens_eye_timeout: scan took longer than {timeout:.0f}s"
        ) from None
    return proc.returncode or 0, stdout_b.decode("utf-8", errors="replace"), stderr_b.decode("utf-8", errors="replace")


def _find_output_json(outdir: str, username: str) -> str | None:
    """Find the JSON file aliens_eye wrote — name is {username}_{profile}_{timestamp}.json."""
    p = Path(outdir)
    matches = sorted(p.glob(f"{username}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if matches:
        return str(matches[0])
    all_json = sorted(p.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    return str(all_json[0]) if all_json else None


def _parse_json_output(json_path: str) -> list[dict[str, Any]]:
    """Parse aliens_eye JSON — handles both flat list and nested variations structure."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        variations = data.get("variations")
        if isinstance(variations, dict):
            hits: list[dict[str, Any]] = []
            for _username, var_data in variations.items():
                if not isinstance(var_data, dict):
                    continue
                for site_name, site_data in var_data.get("sites", {}).items():
                    if not isinstance(site_data, dict):
                        continue
                    status = site_data.get("status", "")
                    if status in ("Found", "Maybe"):
                        hits.append({
                            "site": site_name,
                            "url": site_data.get("url", ""),
                            "status": status,
                            "confidence": site_data.get("confidence", 0),
                            "ml_score": site_data.get("ai_analysis", {}).get("score") if isinstance(site_data.get("ai_analysis"), dict) else None,
                        })
            return hits
        results = data.get("results", data.get("hits", []))
        return results if isinstance(results, list) else []
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
#  Base class
# ─────────────────────────────────────────────

class _AliensEyeCollector(BaseCollector):
    async def test(self) -> CollectorTestResult:
        if not _aliens_eye_available():
            msg = "aliens-eye not installed — run: pip install aliens-eye"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("aliens_eye_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message="aliens-eye ready",
            logs=[collector_log("aliens_eye_test_ok", "cli present")],
        )

    def _base_records(self, hits: list[dict[str, Any]], username: str, collected_at: datetime) -> list[CollectorRawRecord]:
        records = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            platform = hit.get("site") or hit.get("platform") or hit.get("name", "unknown")
            url = hit.get("url") or hit.get("profile_url", "")
            records.append(CollectorRawRecord(
                record_type="account",
                source_url=url or f"https://example.com/{username}",
                content={
                    "username": username,
                    "platform": platform,
                    "url": url,
                    "display_name": hit.get("display_name") or hit.get("name"),
                    "bio": hit.get("bio"),
                    "avatar": hit.get("avatar"),
                    "confidence": hit.get("confidence") or hit.get("score"),
                    "ml_score": hit.get("ml_score"),
                    "status": hit.get("status", "found"),
                    "raw": hit,
                },
                collected_at=collected_at,
            ))
        return records


# ─────────────────────────────────────────────
#  1. Basic scan (quick profile)
# ─────────────────────────────────────────────

class AliensEyeBasicCollector(_AliensEyeCollector):
    """Quick username scan across 840+ platforms using ML detection."""

    collector_type = "aliens_eye_basic"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        return {"username": username}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), username,
                "--profile", "quick",
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
                *_no_ml_args(),
            ]
            rc, stdout, stderr = await _run(cmd, timeout=_timeout())
            logs.append(collector_log("aliens_eye_basic_ran", f"rc={rc} username={username!r}"))
            found_file = _find_output_json(tmpdir, username)
            if rc not in (0, 1) and not found_file:
                msg = f"aliens_eye_error: rc={rc} stderr={stderr[:200]}"
                errors.append(msg)
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            hits = _parse_json_output(found_file) if found_file else []
            logs.append(collector_log("aliens_eye_basic_hits", f"found={len(hits)}"))
            records = self._base_records(hits, username, collected_at)

        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  2. Advanced scan (prefix/suffix variations)
# ─────────────────────────────────────────────

class AliensEyeAdvancedCollector(_AliensEyeCollector):
    """Advanced scan with username variations (prefix/suffix) across 840+ platforms."""

    collector_type = "aliens_eye_advanced"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        sites = self.config.get("sites", "")
        return {"username": username, "sites": sites}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), username,
                "--profile", "full",
                "-l", "advanced",
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
                *_no_ml_args(),
            ]
            if config["sites"]:
                cmd += ["--site", config["sites"]]

            rc, stdout, stderr = await _run(cmd, timeout=_timeout() * 2)
            logs.append(collector_log("aliens_eye_advanced_ran", f"rc={rc} username={username!r}"))
            found_file = _find_output_json(tmpdir, username)
            if rc not in (0, 1) and not found_file:
                msg = f"aliens_eye_error: rc={rc} stderr={stderr[:200]}"
                errors.append(msg)
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            hits = _parse_json_output(found_file) if found_file else []
            logs.append(collector_log("aliens_eye_advanced_hits", f"found={len(hits)}"))
            records = self._base_records(hits, username, collected_at)

        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  3. Correlation scan (cluster same-person accounts)
# ─────────────────────────────────────────────

class AliensEyeCorrelateCollector(_AliensEyeCollector):
    """Scan + cross-site correlation: cluster accounts that look like the same person."""

    collector_type = "aliens_eye_correlate"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        return {"username": username}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), username,
                "--correlate",
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
                *_no_ml_args(),
            ]
            rc, stdout, stderr = await _run(cmd, timeout=_timeout() * 2)
            logs.append(collector_log("aliens_eye_correlate_ran", f"rc={rc} username={username!r}"))
            found_file = _find_output_json(tmpdir, username)
            if rc not in (0, 1) and not found_file:
                errors.append(f"aliens_eye_error: rc={rc} stderr={stderr[:200]}")
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            hits = _parse_json_output(found_file) if found_file else []
            logs.append(collector_log("aliens_eye_correlate_hits", f"found={len(hits)}"))
            records = self._base_records(hits, username, collected_at)

            if hits:
                records.append(CollectorRawRecord(
                    record_type="account",
                    source_url=f"aliens_eye://correlate/{username}",
                    content={
                        "username": username,
                        "total_hits": len(hits),
                        "platforms": [h.get("site") or h.get("platform") for h in hits if isinstance(h, dict)],
                        "correlation_summary": stdout[:2000] if stdout else None,
                    },
                    collected_at=collected_at,
                ))

        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  4. Recursive expansion (follow bio links)
# ─────────────────────────────────────────────

class AliensEyeRecurseCollector(_AliensEyeCollector):
    """Scan + recursively follow usernames found in bios."""

    collector_type = "aliens_eye_recurse"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        depth = int(self.config.get("depth", 1))
        if depth > 3:
            raise CollectorError("recurse depth max is 3")
        return {"username": username, "depth": depth}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        depth: int = config["depth"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), username,
                "--recurse-depth", str(depth),
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
                *_no_ml_args(),
            ]
            rc, stdout, stderr = await _run(cmd, timeout=_timeout() * (depth + 1))
            logs.append(collector_log("aliens_eye_recurse_ran", f"rc={rc} depth={depth}"))
            found_file = _find_output_json(tmpdir, username)
            if rc not in (0, 1) and not found_file:
                errors.append(f"aliens_eye_error: rc={rc} stderr={stderr[:200]}")
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            hits = _parse_json_output(found_file) if found_file else []
            logs.append(collector_log("aliens_eye_recurse_hits", f"found={len(hits)}"))
            records = self._base_records(hits, username, collected_at)

        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  5. Domain check (is username.com registered?)
# ─────────────────────────────────────────────

class AliensEyeDomainCollector(_AliensEyeCollector):
    """Check if common domain variants of the username are registered."""

    collector_type = "aliens_eye_domain"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        return {"username": username}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), username,
                "--domains",
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
            ]
            rc, stdout, stderr = await _run(cmd, timeout=60.0)
            logs.append(collector_log("aliens_eye_domain_ran", f"rc={rc}"))
            found_file = _find_output_json(tmpdir, username)
            if rc not in (0, 1) and not found_file:
                errors.append(f"aliens_eye_error: rc={rc} stderr={stderr[:200]}")
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

            hits = _parse_json_output(found_file) if found_file else []
            domain_hits = [h for h in hits if isinstance(h, dict) and h.get("type") == "domain"]
            logs.append(collector_log("aliens_eye_domain_hits", f"domains={len(domain_hits)}"))
            records = []
            for h in domain_hits:
                records.append(CollectorRawRecord(
                    record_type="account",
                    source_url=h.get("url", ""),
                    content={
                        "username": username,
                        "domain": h.get("domain") or h.get("site"),
                        "registered": h.get("registered", True),
                        "url": h.get("url"),
                        "raw": h,
                    },
                    collected_at=collected_at,
                ))

        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  6. Multi-username batch scan
# ─────────────────────────────────────────────

class AliensEyeBatchCollector(_AliensEyeCollector):
    """Scan multiple usernames in one call (up to 10)."""

    collector_type = "aliens_eye_batch"

    def validate_config(self) -> dict[str, Any]:
        usernames_raw = self.config.get("usernames", [])
        if isinstance(usernames_raw, str):
            usernames = [u.strip() for u in usernames_raw.split(",") if u.strip()]
        else:
            usernames = [str(u).strip() for u in usernames_raw if str(u).strip()]
        if not usernames:
            raise CollectorError("usernames list is required and must not be empty")
        if len(usernames) > 10:
            raise CollectorError("max 10 usernames per batch")
        return {"usernames": usernames}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        usernames: list[str] = config["usernames"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        all_records: list[CollectorRawRecord] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                _aliens_eye_cmd(), *usernames,
                "--profile", "quick",
                "--format", "json",
                "--output", tmpdir,
                "--plain",
                *_proxy_args(),
                *_no_ml_args(),
            ]
            rc, stdout, stderr = await _run(cmd, timeout=_timeout() * len(usernames))
            logs.append(collector_log("aliens_eye_batch_ran", f"rc={rc} count={len(usernames)}"))

            for username in usernames:
                found_file = _find_output_json(tmpdir, username)
                if found_file:
                    hits = _parse_json_output(found_file)
                    all_records.extend(self._base_records(hits, username, collected_at))
                    logs.append(collector_log("aliens_eye_batch_user", f"{username}={len(hits)} hits"))

        if not all_records and rc not in (0, 1):
            errors.append(f"aliens_eye_batch_error: rc={rc} stderr={stderr[:200]}")

        return CollectionResult(raw_records=all_records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  7. Selfcheck (accuracy report — test mode)
# ─────────────────────────────────────────────

class AliensEyeSelfcheckCollector(_AliensEyeCollector):
    """Run aliens_eye selfcheck to report per-site accuracy metrics."""

    collector_type = "aliens_eye_selfcheck"

    def validate_config(self) -> dict[str, Any]:
        return {}

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        cmd = [_aliens_eye_cmd(), "selfcheck", "--report", "json", "--plain"]
        rc, stdout, stderr = await _run(cmd, timeout=300.0)
        logs.append(collector_log("aliens_eye_selfcheck_ran", f"rc={rc}"))

        records = []
        if stdout.strip():
            try:
                report = json.loads(stdout)
            except Exception:
                report = {"raw": stdout[:5000]}
            records.append(CollectorRawRecord(
                record_type="search_result",
                source_url="aliens_eye://selfcheck",
                content={"report": report},
                collected_at=collected_at,
            ))
        elif rc != 0:
            errors.append(f"selfcheck_error: rc={rc} stderr={stderr[:200]}")

        return CollectionResult(raw_records=records, logs=logs, errors=errors)
