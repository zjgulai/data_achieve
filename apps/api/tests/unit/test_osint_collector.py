"""Unit tests for SherlockCollector and MaigretCollector.

All tests mock subprocess calls — no real sherlock/maigret binaries required.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.osint_collector import (
    MaigretCollector,
    SherlockCollector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sherlock(config: dict[str, Any]) -> SherlockCollector:
    return SherlockCollector(config=config)


def _maigret(config: dict[str, Any]) -> MaigretCollector:
    return MaigretCollector(config=config)


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestSherlockValidateConfig:
    def test_missing_username_raises(self):
        with pytest.raises(CollectorError, match="username"):
            _sherlock({}).validate_config()

    def test_empty_username_raises(self):
        with pytest.raises(CollectorError):
            _sherlock({"username": "   "}).validate_config()

    def test_valid_username(self):
        cfg = _sherlock({"username": "testuser"}).validate_config()
        assert cfg["username"] == "testuser"
        assert cfg["sites"] == []

    def test_sites_list_preserved(self):
        cfg = _sherlock({"username": "u", "sites": ["GitHub", "Twitter"]}).validate_config()
        assert cfg["sites"] == ["GitHub", "Twitter"]

    def test_sites_not_list_raises(self):
        with pytest.raises(CollectorError, match="list"):
            _sherlock({"username": "u", "sites": "GitHub"}).validate_config()


class TestMaigretValidateConfig:
    def test_missing_username_raises(self):
        with pytest.raises(CollectorError, match="username"):
            _maigret({}).validate_config()

    def test_valid_defaults(self):
        cfg = _maigret({"username": "testuser"}).validate_config()
        assert cfg["username"] == "testuser"
        assert cfg["max_sites"] == 500

    def test_max_sites_bounds(self):
        with pytest.raises(CollectorError, match="max_sites"):
            _maigret({"username": "u", "max_sites": 0}).validate_config()
        with pytest.raises(CollectorError, match="max_sites"):
            _maigret({"username": "u", "max_sites": 9999}).validate_config()


# ---------------------------------------------------------------------------
# test() — binary availability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sherlock_test_fails_when_binary_missing():
    with patch(
        "data_intelligence_hub.collectors.osint_collector._sherlock_available",
        return_value=False,
    ):
        result = await _sherlock({"username": "u"}).test()
    assert result.status == "failed"
    assert "sherlock" in result.message.lower()


@pytest.mark.asyncio
async def test_sherlock_test_ok_when_binary_present():
    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._sherlock_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            new_callable=AsyncMock,
            return_value=(0, "sherlock 0.15.0\n", ""),
        ),
    ):
        result = await _sherlock({"username": "u"}).test()
    assert result.status == "ok"


@pytest.mark.asyncio
async def test_maigret_test_fails_when_binary_missing():
    with patch(
        "data_intelligence_hub.collectors.osint_collector._maigret_available",
        return_value=False,
    ):
        result = await _maigret({"username": "u"}).test()
    assert result.status == "failed"
    assert "maigret" in result.message.lower()


# ---------------------------------------------------------------------------
# collect() — sherlock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sherlock_collect_binary_missing_returns_error():
    with patch(
        "data_intelligence_hub.collectors.osint_collector._sherlock_available",
        return_value=False,
    ):
        result = await _sherlock({"username": "alice"}).collect()
    assert result.raw_records == []
    assert any("sherlock" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_sherlock_collect_parses_stdout_fallback(tmp_path: Path):
    stdout = textwrap.dedent("""\
        [+] GitHub: https://github.com/alice
        [+] Twitter: https://twitter.com/alice
        [-] Reddit: Not Found!
    """)

    async def fake_run(cmd: list[str], timeout: float = 300.0):
        return (0, stdout, "")

    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._sherlock_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            side_effect=fake_run,
        ),
    ):
        result = await _sherlock({"username": "alice"}).collect()

    assert len(result.raw_records) == 1
    rec = result.raw_records[0]
    assert rec.record_type == "account"
    content = rec.content
    assert content["username"] == "alice"
    assert content["tool"] == "sherlock"
    assert content["total_found"] >= 2
    found = content["found_on"]
    assert "GitHub" in found
    assert "Twitter" in found


@pytest.mark.asyncio
async def test_sherlock_collect_timeout_returns_error():
    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._sherlock_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            side_effect=CollectorError("osint_timeout: command took longer than 300s"),
        ),
    ):
        result = await _sherlock({"username": "alice"}).collect()
    assert result.raw_records == []
    assert any("timeout" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# collect() — maigret
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_maigret_collect_binary_missing_returns_error():
    with patch(
        "data_intelligence_hub.collectors.osint_collector._maigret_available",
        return_value=False,
    ):
        result = await _maigret({"username": "bob"}).collect()
    assert result.raw_records == []
    assert any("maigret" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_maigret_collect_parses_json_report(tmp_path: Path, monkeypatch):
    """CLI fallback must follow upstream's real contract.

    Upstream writes ``<folderoutput>/report_<username>_simple.json`` (there is
    no ``--output`` flag) and nests the check result under ``status``.
    """
    monkeypatch.delenv("MAIGRET_URL", raising=False)
    report_data = {
        "GitHub": {
            "status": {
                "username": "bob",
                "site_name": "GitHub",
                "url": "https://github.com/bob",
                "status": "Claimed",
            },
            "url_user": "https://github.com/bob",
        },
        "Twitter": {
            "status": {
                "username": "bob",
                "site_name": "Twitter",
                "url": "https://twitter.com/bob",
                "status": "Claimed",
            },
            "url_user": "https://twitter.com/bob",
        },
    }

    async def fake_run(cmd: list[str], timeout: float = 600.0):
        folder_idx = cmd.index("--folderoutput") + 1
        folder = Path(cmd[folder_idx])
        folder.mkdir(parents=True, exist_ok=True)
        report = folder / "report_bob_simple.json"
        report.write_text(json.dumps(report_data), encoding="utf-8")
        return (0, "", "")

    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._maigret_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            side_effect=fake_run,
        ),
    ):
        result = await _maigret({"username": "bob"}).collect()

    assert len(result.raw_records) == 1
    rec = result.raw_records[0]
    assert rec.record_type == "account"
    content = rec.content
    assert content["username"] == "bob"
    assert content["source"] == "cli"
    assert content["total_claimed"] == 2
    assert "GitHub" in content["claimed_sites"]
    assert "Twitter" in content["claimed_sites"]
    assert content["profile_urls"]["GitHub"] == "https://github.com/bob"


@pytest.mark.asyncio
async def test_maigret_collect_uses_sidecar_when_configured(monkeypatch):
    monkeypatch.setenv("MAIGRET_URL", "http://maigret:5000")

    async def fake_sidecar(username: str):
        return {
            "GitHub": {
                "status": "Claimed",
                "url": "https://github.com/bob",
                "ids": {},
                "username": username,
            }
        }

    with patch(
        "data_intelligence_hub.collectors.osint_collector._maigret_sidecar_scan",
        side_effect=fake_sidecar,
    ):
        result = await _maigret({"username": "bob"}).collect()

    content = result.raw_records[0].content
    assert content["source"] == "sidecar"
    assert content["total_claimed"] == 1
    assert content["profile_urls"]["GitHub"] == "https://github.com/bob"


@pytest.mark.asyncio
async def test_maigret_falls_back_to_cli_when_sidecar_fails(monkeypatch):
    monkeypatch.setenv("MAIGRET_URL", "http://maigret:5000")

    async def fake_run(cmd: list[str], timeout: float = 600.0):
        folder = Path(cmd[cmd.index("--folderoutput") + 1])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report_bob_simple.json").write_text(
            json.dumps({"GitHub": {"status": {"status": "Claimed"}}}),
            encoding="utf-8",
        )
        return (0, "", "")

    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._maigret_sidecar_scan",
            side_effect=CollectorError("sidecar down"),
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._maigret_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            side_effect=fake_run,
        ),
    ):
        result = await _maigret({"username": "bob"}).collect()

    content = result.raw_records[0].content
    assert content["source"] == "cli"
    assert content["total_claimed"] == 1


@pytest.mark.asyncio
async def test_sherlock_collect_reads_url_user_column(monkeypatch):
    """Sherlock's CSV columns are username,name,url_main,url_user,exists,..."""
    csv_body = (
        "username,name,url_main,url_user,exists,http_status,response_time_s\n"
        "alice,GitHub,https://github.com/,https://github.com/alice,Claimed,200,0.5\n"
        "alice,Twitter,https://twitter.com/,https://twitter.com/alice,Available,404,0.4\n"
        "alice,Reddit,https://reddit.com/,https://reddit.com/user/alice,Unknown,,0.3\n"
    )

    async def fake_run(cmd: list[str], timeout: float = 300.0):
        folder = Path(cmd[cmd.index("--folderoutput") + 1])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "alice.csv").write_text(csv_body, encoding="utf-8")
        return (0, "", "")

    with (
        patch(
            "data_intelligence_hub.collectors.osint_collector._sherlock_available",
            return_value=True,
        ),
        patch(
            "data_intelligence_hub.collectors.osint_collector._run",
            side_effect=fake_run,
        ),
    ):
        result = await _sherlock({"username": "alice"}).collect()

    content = result.raw_records[0].content
    assert content["found_on"] == {"GitHub": "https://github.com/alice"}
    assert content["total_found"] == 1
    assert content["sites_checked"] == 3
    assert content["status_counts"] == {"Claimed": 1, "Available": 1, "Unknown": 1}
