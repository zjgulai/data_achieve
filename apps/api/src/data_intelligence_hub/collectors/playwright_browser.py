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
from data_intelligence_hub.collectors.outbound_policy import assert_collector_allowed

PLAYWRIGHT_TIMEOUT_MS = 30_000
PLAYWRIGHT_WAIT_MODES = frozenset({"load", "networkidle", "domcontentloaded"})
PLAYWRIGHT_EXTRACT_MODES = frozenset({"text", "html", "screenshot"})
MAX_HTML_BYTES = 500_000


def _assert_playwright_available() -> None:
    if importlib.util.find_spec("playwright") is None:
        raise CollectorError(
            "playwright_not_installed: add 'browser' extra and rebuild image"
        )


def _obscura_cdp_url() -> str | None:
    return os.environ.get("OBSCURA_CDP_URL", "").strip() or None


def _obscura_cdp_token() -> str | None:
    return os.environ.get("OBSCURA_CDP_TOKEN", "").strip() or None


def _obscura_headers() -> dict[str, str]:
    """Auth header for the Obscura CDP endpoint.

    Obscura gates every route — including /json/* and the WebSocket upgrade —
    behind a bearer token whenever it binds a non-loopback address.
    """
    token = _obscura_cdp_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


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
    allow_empty = True

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

    async def _get_browser(self, pw: Any) -> tuple[Any, str, str | None]:
        """Return ``(browser, backend, fallback_reason)``.

        ``backend`` describes what actually served the request. A configured
        Obscura endpoint can still refuse the connection, and reporting
        "obscura" after silently falling back to local Chromium hides the
        failure, so the reason is returned instead of swallowed.
        """
        cdp_url = _obscura_cdp_url()
        if cdp_url:
            try:
                browser = await pw.chromium.connect_over_cdp(
                    cdp_url, headers=_obscura_headers()
                )
            except Exception as exc:
                reason = f"{exc.__class__.__name__}: {exc}"[:200]
                return await pw.chromium.launch(**_chromium_launch_kwargs()), "chromium", reason
            return browser, "obscura", None
        return await pw.chromium.launch(**_chromium_launch_kwargs()), "chromium", None

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        _assert_playwright_available()
        config = self.validate_config()
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser, backend, fallback_reason = await self._get_browser(pw)
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

        logs = [collector_log("browser_test_ok", f"status={status} backend={backend}")]
        if fallback_reason:
            logs.insert(
                0,
                collector_log(
                    "browser_obscura_fallback",
                    f"Obscura unreachable, used local Chromium: {fallback_reason}",
                    level="warning",
                ),
            )
        if status >= 400:
            return CollectorTestResult(
                status="failed",
                message=f"HTTP {status} from {config['url']}",
                logs=[collector_log("browser_test_failed", f"status={status}")],
            )
        message = f"Browser ({backend}) reached {config['url']} (HTTP {status})"
        if fallback_reason:
            message += " — Obscura fallback, local Chromium used"
        return CollectorTestResult(status="ok", message=message, logs=logs)

    async def collect(self) -> CollectionResult:
        assert_collector_allowed(self.collector_type)
        _assert_playwright_available()
        config = self.validate_config()
        from playwright.async_api import async_playwright

        collected_at = datetime.now(UTC)
        async with async_playwright() as pw:
            browser, backend, fallback_reason = await self._get_browser(pw)
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
                "backend": backend,
                "obscura_fallback_reason": fallback_reason,
            },
            collected_at=collected_at,
        )
        logs = [
            collector_log(
                "browser_collected",
                f"url={final_url} extract_mode={extract_mode} backend={backend}",
            )
        ]
        if fallback_reason:
            logs.insert(
                0,
                collector_log(
                    "browser_obscura_fallback",
                    f"Obscura unreachable, used local Chromium: {fallback_reason}",
                    level="warning",
                ),
            )
        return CollectionResult(raw_records=[record], errors=[], logs=logs)
