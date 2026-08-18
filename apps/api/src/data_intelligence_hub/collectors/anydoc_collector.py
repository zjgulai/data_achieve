"""Document-to-Markdown collector backed by markitdown (Microsoft).

Converts Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF, EPUB,
RTF, CSV, and OpenDocument files to clean Markdown.

Requires:  uv add "markitdown[all]"   (pip install "markitdown[all]")

Environment variables:
    ANYDOC_MAX_FILE_MB   Maximum download size in MB (default: 50)
    HTTP_PROXY           Forwarded to httpx for the file download
"""
from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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

_SUPPORTED_EXTS = {
    ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".pdf", ".epub", ".rtf", ".csv", ".odt", ".ods", ".odp",
}
_DEFAULT_MAX_MB = 50
_DOWNLOAD_TIMEOUT = 60.0


def _max_bytes() -> int:
    try:
        return int(os.environ.get("ANYDOC_MAX_FILE_MB", _DEFAULT_MAX_MB)) * 1024 * 1024
    except ValueError:
        return _DEFAULT_MAX_MB * 1024 * 1024


def _http_client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(
        timeout=_DOWNLOAD_TIMEOUT,
        proxy=proxy or None,
        follow_redirects=True,
    )


def _ext_from_url(url: str, declared_type: str) -> str:
    if declared_type:
        ext = declared_type.lower()
        return ext if ext.startswith(".") else f".{ext}"
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix else ""


class AnydocCollector(BaseCollector):
    """Convert a remote document file to Markdown using markitdown."""

    collector_type = "anydoc_file_to_markdown"

    def validate_config(self) -> dict[str, Any]:
        file_url = require_text(self.config, "file_url")
        file_type = self.config.get("file_type", "").strip()
        ext = _ext_from_url(file_url, file_type)
        if ext and ext not in _SUPPORTED_EXTS:
            raise CollectorError(
                f"Unsupported file type {ext!r}. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTS))}"
            )
        return {"file_url": file_url, "file_type": file_type, "ext": ext}

    async def test(self) -> CollectorTestResult:
        try:
            from markitdown import MarkItDown  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            msg = "markitdown not installed — run: uv add 'markitdown[all]'"
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("anydoc_test_failed", msg, level="error")],
            )
        try:
            self.validate_config()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("anydoc_test_failed", str(exc), level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message="markitdown ready",
            logs=[collector_log("anydoc_test_ok", "library present")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            from markitdown import MarkItDown  # type: ignore[import-untyped]
        except ImportError:
            msg = "markitdown not installed — run: uv add 'markitdown[all]'"
            errors.append(msg)
            logs.append(collector_log("anydoc_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        file_url: str = config["file_url"]
        ext: str = config["ext"]
        collected_at = datetime.now(UTC)

        # 1. Download the file
        try:
            async with _http_client() as client:
                r = await client.get(file_url)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("anydoc_download_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        content_bytes = r.content
        if len(content_bytes) > _max_bytes():
            msg = (
                f"File too large: {len(content_bytes) / 1024 / 1024:.1f} MB "
                f"> {_max_bytes() // 1024 // 1024} MB limit"
            )
            errors.append(msg)
            logs.append(collector_log("anydoc_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(
            collector_log(
                "anydoc_downloaded",
                f"url={file_url!r} size={len(content_bytes)} bytes ext={ext!r}",
            )
        )

        # 2. Write to temp file and convert with markitdown
        try:
            with tempfile.NamedTemporaryFile(
                suffix=ext or ".bin", delete=False
            ) as tmp:
                tmp.write(content_bytes)
                tmp_path = tmp.name

            try:
                md = MarkItDown()
                result = md.convert(tmp_path)
                markdown: str = result.text_content
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            msg = f"markitdown conversion failed: {exc}"
            errors.append(msg)
            logs.append(collector_log("anydoc_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(
            collector_log(
                "anydoc_converted",
                f"url={file_url!r} markdown_chars={len(markdown)}",
            )
        )

        filename = Path(urlparse(file_url).path).name or "document"

        record = CollectorRawRecord(
            record_type="web_page_markdown",
            source_url=file_url,
            content={
                "file_url": file_url,
                "filename": filename,
                "file_type": ext or "unknown",
                "file_size_bytes": len(content_bytes),
                "markdown": markdown,
                "markdown_chars": len(markdown),
            },
            collected_at=collected_at,
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
