"""Unit tests for SherlockCollector and MaigretCollector.

All tests mock subprocess calls — no real sherlock/maigret binaries required.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_intelligence_hub.collectors.osint_collector import (
    MaigretCollector,
    SherlockCollector,
    _maigret_available,
    _sherlock_available,
)
from data_intelligence_hub.collectors.base import CollectorError


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
    report_data = {
        "GitHub": {"status": "Claimed", "url": "https://github.com/bob"},
        "Pinterest": {"status": "Available"},
        "Twitter": {"status": "Claimed", "url": "https://twitter.com/bob"},
    }

    async def fake_run(cmd: list[str], timeout: float = 600.0):
        # Find the --output path in cmd and write the JSON there
        output_idx = cmd.index("--output") + 1
        out_path = Path(cmd[output_idx])
        out_path.write_text(json.dumps(report_data), encoding="utf-8")
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
    assert content["total_claimed"] == 2
    assert "GitHub" in content["claimed_sites"]
    assert "Twitter" in content["claimed_sites"]
    assert "Pinterest" not in content["claimed_sites"]
