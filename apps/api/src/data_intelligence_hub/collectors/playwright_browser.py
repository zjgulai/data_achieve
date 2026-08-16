from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)

PLAYWRIGHT_TIMEOUT_MS = 30_000
PLAYWRIGHT_WAIT_MODES = frozenset({"load", "networkidle", "domcontentloaded"})
PLAYWRIGHT_EXTRACT_MODES = frozenset({"text", "html", "screenshot"})
MAX_HTML_BYTES = 500_000


def _assert_playwright_available() -> None:
    if importlib.util.find_spec("playwright") is None:
        raise CollectorError(
            "playwright_not_installed: add 'browser' extra and rebuild image"
        )


def _chromium_launch_kwargs() -> dict[str, Any]:
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    kwargs: dict[str, Any] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    if exe:
        kwargs["executable_path"] = exe
    return kwargs


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CollectorError("url must be an absolute HTTP or HTTPS URL")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.startswith("192.168."):
        raise CollectorError("private or loopback URLs are not allowed")


class PlaywrightBrowserCollector(BaseCollector):
    collector_type = "playwright_browser"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        _assert_public_url(url)
        wait_for = self.config.get("wait_for", "load")
        if wait_for not in PLAYWRIGHT_WAIT_MODES:
            raise CollectorError(
                f"wait_for must be one of: {sorted(PLAYWRIGHT_WAIT_MODES)}"
            )
        extract_mode = self.config.get("extract_mode", "text")
        if extract_mode not in PLAYWRIGHT_EXTRACT_MODES:
            raise CollectorError(
                f"extract_mode must be one of: {sorted(PLAYWRIGHT_EXTRACT_MODES)}"
            )
        wait_selector = self.config.get("wait_selector")
        if wait_selector is not None and not isinstance(wait_selector, str):
            raise CollectorError("wait_selector must be a string CSS selector")
        return {
            "url": url,
            "wait_for": wait_for,
            "extract_mode": extract_mode,
            "wait_selector": wait_selector,
        }

    async def test(self) -> CollectorTestResult:
        _assert_playwright_available()
        config = self.validate_config()
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**_chromium_launch_kwargs())
            try:
                page = await browser.new_page()
                response = await page.goto(
                    config["url"],
                    timeout=PLAYWRIGHT_TIMEOUT_MS,
                    wait_until=config["wait_for"],
                )
                status = response.status if response else 0
            finally:
                await browser.close()

        if status >= 400:
            return CollectorTestResult(
                status="failed",
                message=f"HTTP {status} from {config['url']}",
                logs=[collector_log("browser_test_failed", f"status={status}")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"Browser reached {config['url']} (HTTP {status})",
            logs=[collector_log("browser_test_ok", f"status={status}")],
        )

    async def collect(self) -> CollectionResult:
        _assert_playwright_available()
        config = self.validate_config()
        from playwright.async_api import async_playwright

        collected_at = datetime.now(UTC)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**_chromium_launch_kwargs())
            try:
                page = await browser.new_page()
                response = await page.goto(
                    config["url"],
                    timeout=PLAYWRIGHT_TIMEOUT_MS,
                    wait_until=config["wait_for"],
                )
                final_url = page.url
                http_status = response.status if response else 0

                if config.get("wait_selector"):
                    await page.wait_for_selector(
                        config["wait_selector"], timeout=PLAYWRIGHT_TIMEOUT_MS
                    )

                extract_mode = config["extract_mode"]
                if extract_mode == "text":
                    content = await page.inner_text("body")
                elif extract_mode == "html":
                    content = await page.content()
                    content = content[:MAX_HTML_BYTES]
                else:
                    screenshot_bytes = await page.screenshot(full_page=True)
                    content = screenshot_bytes.hex()

            finally:
                await browser.close()

        record = CollectorRawRecord(
            record_type="web_page",
            source_url=final_url,
            content={
                "requested_url": config["url"],
                "final_url": final_url,
                "http_status": http_status,
                "extract_mode": extract_mode,
                "content": content,
            },
            collected_at=collected_at,
        )
        return CollectionResult(
            records=[record],
            logs=[
                collector_log(
                    "browser_collected",
                    f"url={final_url} extract_mode={extract_mode}",
                )
            ],
        )
