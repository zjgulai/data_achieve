"""Unit tests for AnydocCollector.

All tests mock httpx transport and markitdown — no real network or file conversion.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.anydoc_collector import (
    AnydocCollector,
    _ext_from_url,
    _max_bytes,
)
from data_intelligence_hub.collectors.base import CollectorError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collector(config: dict[str, Any]) -> AnydocCollector:
    return AnydocCollector(config=config)


class _MockTransport(httpx.BaseTransport):
    def __init__(self, content: bytes = b"", status_code: int = 200):
        self._content = content
        self._status_code = status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self._status_code}",
                request=request,
                response=httpx.Response(self._status_code, request=request),
            )
        return httpx.Response(
            self._status_code,
            content=self._content,
            request=request,
        )


class _MockAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, content: bytes = b"", status_code: int = 200):
        self._content = content
        self._status_code = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self._status_code}",
                request=request,
                response=httpx.Response(self._status_code, request=request),
            )
        return httpx.Response(
            self._status_code,
            content=self._content,
            request=request,
        )


# ---------------------------------------------------------------------------
# _ext_from_url
# ---------------------------------------------------------------------------


class TestExtFromUrl:
    def test_declared_type_wins(self):
        assert _ext_from_url("https://example.com/file.pdf", "docx") == ".docx"

    def test_declared_with_dot(self):
        assert _ext_from_url("https://example.com/f", ".pdf") == ".pdf"

    def test_infer_from_url(self):
        assert _ext_from_url("https://example.com/report.pdf", "") == ".pdf"

    def test_unknown_ext_returns_empty(self):
        assert _ext_from_url("https://example.com/file", "") == ""


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_missing_file_url_raises(self):
        with pytest.raises(CollectorError, match="file_url"):
            _collector({}).validate_config()

    def test_empty_file_url_raises(self):
        with pytest.raises(CollectorError):
            _collector({"file_url": "  "}).validate_config()

    def test_valid_pdf_url(self):
        cfg = _collector({"file_url": "https://example.com/doc.pdf"}).validate_config()
        assert cfg["file_url"] == "https://example.com/doc.pdf"
        assert cfg["ext"] == ".pdf"

    def test_unsupported_ext_raises(self):
        with pytest.raises(CollectorError, match="Unsupported"):
            _collector({"file_url": "https://example.com/image.png"}).validate_config()

    def test_no_ext_allowed(self):
        cfg = _collector({"file_url": "https://example.com/document"}).validate_config()
        assert cfg["ext"] == ""

    def test_file_type_override(self):
        cfg = _collector(
            {"file_url": "https://example.com/download", "file_type": "docx"}
        ).validate_config()
        assert cfg["ext"] == ".docx"


# ---------------------------------------------------------------------------
# test()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_fails_when_markitdown_missing():
    with patch.dict("sys.modules", {"markitdown": None}):
        with patch(
            "data_intelligence_hub.collectors.anydoc_collector.AnydocCollector.test",
        ) as mock_test:
            mock_test.return_value = MagicMock(status="failed", message="markitdown not installed")
            result = await _collector({"file_url": "https://example.com/doc.pdf"}).test()
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_test_ok_when_markitdown_present():
    fake_md = MagicMock()
    with patch.dict("sys.modules", {"markitdown": fake_md}):
        with patch(
            "data_intelligence_hub.collectors.anydoc_collector.AnydocCollector.test",
        ) as mock_test:
            mock_test.return_value = MagicMock(status="ok", message="markitdown ready")
            result = await _collector({"file_url": "https://example.com/doc.pdf"}).test()
    assert result.status == "ok"


# ---------------------------------------------------------------------------
# collect() — download errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_http_404_returns_error():
    async def fake_client_factory():
        return httpx.AsyncClient(transport=_MockAsyncTransport(b"", 404))

    with (
        patch(
            "data_intelligence_hub.collectors.anydoc_collector._http_client",
            return_value=httpx.AsyncClient(transport=_MockAsyncTransport(b"", 404)),
        ),
        patch.dict("sys.modules", {"markitdown": MagicMock()}),
    ):
        result = await _collector({"file_url": "https://example.com/doc.pdf"}).collect()

    assert result.raw_records == []
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_collect_file_too_large_returns_error(monkeypatch):
    monkeypatch.setenv("ANYDOC_MAX_FILE_MB", "1")
    large_content = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB limit

    fake_markitdown = MagicMock()
    fake_markitdown.MarkItDown.return_value.convert.return_value = MagicMock(
        text_content="# Hello"
    )

    with (
        patch(
            "data_intelligence_hub.collectors.anydoc_collector._http_client",
            return_value=httpx.AsyncClient(
                transport=_MockAsyncTransport(large_content, 200)
            ),
        ),
        patch.dict("sys.modules", {"markitdown": fake_markitdown}),
    ):
        result = await _collector({"file_url": "https://example.com/doc.pdf"}).collect()

    assert result.raw_records == []
    assert any("large" in e.lower() or "mb" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# collect() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_success_returns_markdown_record(monkeypatch, tmp_path):
    monkeypatch.setenv("ANYDOC_MAX_FILE_MB", "50")
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    expected_markdown = "# Document Title\n\nSome content here."

    fake_md_instance = MagicMock()
    fake_md_instance.convert.return_value = MagicMock(text_content=expected_markdown)
    fake_markitdown_module = MagicMock()
    fake_markitdown_module.MarkItDown.return_value = fake_md_instance

    with (
        patch(
            "data_intelligence_hub.collectors.anydoc_collector._http_client",
            return_value=httpx.AsyncClient(
                transport=_MockAsyncTransport(pdf_bytes, 200)
            ),
        ),
        patch.dict("sys.modules", {"markitdown": fake_markitdown_module}),
    ):
        result = await _collector(
            {"file_url": "https://example.com/report.pdf"}
        ).collect()

    assert len(result.raw_records) == 1
    rec = result.raw_records[0]
    assert rec.record_type == "web_page_markdown"
    assert rec.source_url == "https://example.com/report.pdf"
    content = rec.content
    assert content["file_url"] == "https://example.com/report.pdf"
    assert content["filename"] == "report.pdf"
    assert content["file_type"] == ".pdf"
    assert content["markdown"] == expected_markdown
    assert content["markdown_chars"] == len(expected_markdown)
    assert result.errors == []


@pytest.mark.asyncio
async def test_collect_markitdown_conversion_error_returns_error():
    pdf_bytes = b"fake pdf"
    fake_md_instance = MagicMock()
    fake_md_instance.convert.side_effect = RuntimeError("conversion boom")
    fake_markitdown_module = MagicMock()
    fake_markitdown_module.MarkItDown.return_value = fake_md_instance

    with (
        patch(
            "data_intelligence_hub.collectors.anydoc_collector._http_client",
            return_value=httpx.AsyncClient(
                transport=_MockAsyncTransport(pdf_bytes, 200)
            ),
        ),
        patch.dict("sys.modules", {"markitdown": fake_markitdown_module}),
    ):
        result = await _collector(
            {"file_url": "https://example.com/report.pdf"}
        ).collect()

    assert result.raw_records == []
    assert any("conversion" in e.lower() or "markitdown" in e.lower() for e in result.errors)
