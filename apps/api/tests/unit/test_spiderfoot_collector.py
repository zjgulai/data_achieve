"""Unit tests for SpiderFoot OSINT collectors.

All tests mock httpx.AsyncClient — no real SpiderFoot instance required.
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.spiderfoot_collector import (
    SpiderFootDomainCollector,
    SpiderFootEmailCollector,
    SpiderFootIPCollector,
    _row_to_dict,
)


def _domain(config: dict[str, Any]) -> SpiderFootDomainCollector:
    return SpiderFootDomainCollector(config=config)


def _ip(config: dict[str, Any]) -> SpiderFootIPCollector:
    return SpiderFootIPCollector(config=config)


def _email(config: dict[str, Any]) -> SpiderFootEmailCollector:
    return SpiderFootEmailCollector(config=config)


class _FakeResponse:
    def __init__(self, body: Any, status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code),
            )

    def json(self) -> Any:
        return self._body


def _fake_client(responses: list[_FakeResponse]):
    """Return a context-manager-compatible AsyncMock that yields responses in order."""
    client = AsyncMock()
    client.post = AsyncMock(side_effect=[responses[0]])
    client.get = AsyncMock(side_effect=responses[1:])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestRowToDict:
    def test_dict_passthrough(self):
        row = {"type": "IP_ADDRESS", "data": "1.2.3.4"}
        assert _row_to_dict(row) == row

    def test_list_4_elements(self):
        row = ["IP_ADDRESS", "sfp_dnsresolve", "example.com", "1.2.3.4"]
        result = _row_to_dict(row)
        assert result["type"] == "IP_ADDRESS"
        assert result["data"] == "1.2.3.4"

    def test_list_6_elements_includes_risk(self):
        row = ["MALICIOUS_IP", "sfp_threatcrowd", "1.2.3.4", "bad", "2025-01-01", "HIGH"]
        result = _row_to_dict(row)
        assert result["risk"] == "HIGH"

    def test_unknown_type_wrapped(self):
        result = _row_to_dict(42)
        assert result == {"raw": 42}


class TestValidateConfig:
    def test_missing_target_raises(self):
        with pytest.raises(CollectorError, match="target"):
            _domain({}).validate_config()

    def test_empty_target_raises(self):
        with pytest.raises(CollectorError):
            _domain({"target": "  "}).validate_config()

    def test_valid_target(self):
        cfg = _domain({"target": "example.com"}).validate_config()
        assert cfg["target"] == "example.com"
        assert cfg["modules"] == []

    def test_modules_list_preserved(self):
        cfg = _domain({"target": "t.com", "modules": ["sfp_dns", "sfp_whois"]}).validate_config()
        assert cfg["modules"] == ["sfp_dns", "sfp_whois"]

    def test_modules_not_list_raises(self):
        with pytest.raises(CollectorError, match="list"):
            _domain({"target": "t.com", "modules": "sfp_dns"}).validate_config()

    def test_ip_collector(self):
        cfg = _ip({"target": "1.2.3.4"}).validate_config()
        assert cfg["target"] == "1.2.3.4"

    def test_email_collector(self):
        cfg = _email({"target": "user@example.com"}).validate_config()
        assert cfg["target"] == "user@example.com"


class TestTestMethod:
    @pytest.mark.asyncio
    async def test_fails_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("SPIDERFOOT_BASE_URL", raising=False)
        result = await _domain({"target": "t.com"}).test()
        assert result.status == "failed"
        assert "SPIDERFOOT_BASE_URL" in result.message

    @pytest.mark.asyncio
    async def test_fails_on_http_error(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")
        err = httpx.ConnectError("refused")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=err)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.spiderfoot_collector._client",
            return_value=mock_client,
        ):
            result = await _domain({"target": "t.com"}).test()
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_ok_when_reachable(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_FakeResponse([], 200))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.spiderfoot_collector._client",
            return_value=mock_client,
        ):
            result = await _domain({"target": "t.com"}).test()
        assert result.status == "ok"
        assert "http://sf:5001" in result.message


class TestCollect:
    @pytest.mark.asyncio
    async def test_env_not_set_returns_error(self, monkeypatch):
        monkeypatch.delenv("SPIDERFOOT_BASE_URL", raising=False)
        result = await _domain({"target": "example.com"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_create_scan_http_error_returns_error(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.spiderfoot_collector._client",
            return_value=mock_client,
        ):
            result = await _domain({"target": "example.com"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_create_scan_no_id_returns_error(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_FakeResponse({"message": "ok"}))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.spiderfoot_collector._client",
            return_value=mock_client,
        ):
            result = await _domain({"target": "example.com"}).collect()
        assert result.raw_records == []
        assert any("no id" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_scan_timeout_returns_error(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")
        monkeypatch.setenv("SPIDERFOOT_TIMEOUT", "0")

        async def _fake_create(target, scan_name, modules=None):
            return "scan-123"

        async def _fake_poll(scan_id):
            raise CollectorError("SpiderFoot scan 'scan-123' did not finish within 0s")

        with (
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._create_scan",
                side_effect=_fake_create,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._poll_scan",
                side_effect=_fake_poll,
            ),
        ):
            result = await _domain({"target": "example.com"}).collect()
        assert result.raw_records == []
        assert any("finish" in e.lower() or "timeout" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_scan_error_status_returns_error(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")

        async def _fake_create(target, scan_name, modules=None):
            return "scan-456"

        async def _fake_poll(scan_id):
            return "ERROR"

        with (
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._create_scan",
                side_effect=_fake_create,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._poll_scan",
                side_effect=_fake_poll,
            ),
        ):
            result = await _domain({"target": "example.com"}).collect()
        assert result.raw_records == []
        assert any("ERROR" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_happy_path_returns_grouped_record(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")

        raw_findings = [
            {"type": "IP_ADDRESS", "module": "sfp_dns", "data": "1.2.3.4"},
            {"type": "IP_ADDRESS", "module": "sfp_dns", "data": "5.6.7.8"},
            {"type": "WHOIS_REGISTRAR", "module": "sfp_whois", "data": "GoDaddy"},
        ]

        async def _fake_create(target, scan_name, modules=None):
            return "scan-789"

        async def _fake_poll(scan_id):
            return "FINISHED"

        async def _fake_results(scan_id):
            return raw_findings

        with (
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._create_scan",
                side_effect=_fake_create,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._poll_scan",
                side_effect=_fake_poll,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._get_results",
                side_effect=_fake_results,
            ),
        ):
            result = await _domain({"target": "example.com"}).collect()

        assert len(result.raw_records) == 1
        assert result.errors == []
        rec = result.raw_records[0]
        assert rec.record_type == "osint_report"
        content = rec.content
        assert content["target"] == "example.com"
        assert content["target_type"] == "domain"
        assert content["scan_id"] == "scan-789"
        assert content["total_findings"] == 3
        assert set(content["finding_types"]) == {"IP_ADDRESS", "WHOIS_REGISTRAR"}
        assert len(content["findings_by_type"]["IP_ADDRESS"]) == 2

    @pytest.mark.asyncio
    async def test_ip_collector_target_type(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")

        async def _fake_create(target, scan_name, modules=None):
            return "scan-ip"

        async def _fake_poll(scan_id):
            return "FINISHED"

        async def _fake_results(scan_id):
            return [{"type": "GEO_INFO", "data": "US"}]

        with (
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._create_scan",
                side_effect=_fake_create,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._poll_scan",
                side_effect=_fake_poll,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._get_results",
                side_effect=_fake_results,
            ),
        ):
            result = await _ip({"target": "8.8.8.8"}).collect()

        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["target_type"] == "ip"

    @pytest.mark.asyncio
    async def test_email_collector_target_type(self, monkeypatch):
        monkeypatch.setenv("SPIDERFOOT_BASE_URL", "http://sf:5001")

        async def _fake_create(target, scan_name, modules=None):
            return "scan-email"

        async def _fake_poll(scan_id):
            return "FINISHED"

        async def _fake_results(scan_id):
            return [{"type": "EMAILADDR", "data": "user@example.com"}]

        with (
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._create_scan",
                side_effect=_fake_create,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._poll_scan",
                side_effect=_fake_poll,
            ),
            patch(
                "data_intelligence_hub.collectors.spiderfoot_collector._get_results",
                side_effect=_fake_results,
            ),
        ):
            result = await _email({"target": "user@example.com"}).collect()

        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["target_type"] == "email"
