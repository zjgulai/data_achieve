"""browser-use collector — AI-driven browser automation for arbitrary extraction tasks.

Wraps the browser-use library (pip install browser-use) which uses an LLM
to visually understand pages and execute multi-step extraction tasks.

Unlike PlaywrightBrowserCollector (fixed extract_mode), this collector accepts
a natural-language task description and lets the LLM decide how to navigate,
click, fill forms, and extract data.

Environment variables:
    BROWSER_USE_LLM_PROVIDER   "openai" or "anthropic" (default: anthropic)
    OPENAI_API_KEY             Required if provider=openai
    ANTHROPIC_API_KEY          Required if provider=anthropic
    OBSCURA_CDP_URL            Optional Obscura CDP endpoint for anti-detect browser
    BROWSER_USE_TIMEOUT        Task timeout in seconds (default: 120)
"""
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

_DEFAULT_TIMEOUT = 120
_SUPPORTED_PROVIDERS = {"openai", "anthropic"}


def _provider() -> str:
    return os.environ.get("BROWSER_USE_LLM_PROVIDER", "anthropic").strip().lower()


def _timeout() -> int:
    try:
        return int(os.environ.get("BROWSER_USE_TIMEOUT", _DEFAULT_TIMEOUT))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _obscura_cdp_url() -> str | None:
    return os.environ.get("OBSCURA_CDP_URL", "").strip() or None


def _browser_use_available() -> bool:
    return importlib.util.find_spec("browser_use") is not None


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CollectorError("url must be an absolute HTTP or HTTPS URL")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.startswith("192.168."):
        raise CollectorError("private or loopback URLs are not allowed")


def _build_llm() -> Any:
    provider = _provider()
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]
        except ImportError:
            from anthropic import Anthropic as ChatAnthropic  # type: ignore[import-untyped]
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise CollectorError("ANTHROPIC_API_KEY not set")
        return ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=key)
    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]
        except ImportError:
            raise CollectorError("langchain-openai not installed — pip install langchain-openai")
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise CollectorError("OPENAI_API_KEY not set")
        return ChatOpenAI(model="gpt-4o", api_key=key)
    else:
        raise CollectorError(
            f"Unsupported BROWSER_USE_LLM_PROVIDER={provider!r}. Must be 'openai' or 'anthropic'."
        )


class BrowserUseCollector(BaseCollector):
    """AI-driven browser automation: natural language task → structured extraction."""

    collector_type = "browser_use_task"

    def validate_config(self) -> dict[str, Any]:
        task = require_text(self.config, "task")
        url = self.config.get("url", "").strip()
        if url:
            _assert_public_url(url)
        max_steps = int(self.config.get("max_steps", 10))
        if max_steps > 50:
            raise CollectorError("max_steps cannot exceed 50")
        return {"task": task, "url": url, "max_steps": max_steps}

    async def test(self) -> CollectorTestResult:
        if not _browser_use_available():
            msg = "browser-use not installed — pip install browser-use"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("browser_use_test_failed", msg, level="error")],
            )
        try:
            _build_llm()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("browser_use_test_failed", str(exc), level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"browser-use ready (provider={_provider()})",
            logs=[collector_log("browser_use_test_ok", f"provider={_provider()}")],
        )

    async def collect(self) -> CollectionResult:
        if not _browser_use_available():
            msg = "browser-use not installed — pip install browser-use"
            return CollectionResult(
                raw_records=[], errors=[msg],
                logs=[collector_log("browser_use_error", msg, level="error")],
            )

        config = self.validate_config()
        task: str = config["task"]
        start_url: str = config["url"]
        max_steps: int = config["max_steps"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            llm = _build_llm()
        except CollectorError as exc:
            return CollectionResult(
                raw_records=[], errors=[str(exc)],
                logs=[collector_log("browser_use_error", str(exc), level="error")],
            )

        try:
            from browser_use import Agent, Browser, BrowserConfig  # type: ignore[import-untyped]

            cdp_url = _obscura_cdp_url()
            browser_cfg = BrowserConfig(cdp_url=cdp_url) if cdp_url else BrowserConfig()
            browser = Browser(config=browser_cfg)

            full_task = f"Starting at {start_url}\n\n{task}" if start_url else task
            agent = Agent(task=full_task, llm=llm, browser=browser, max_steps=max_steps)
            result = await agent.run()

            final_result = result.final_result() if hasattr(result, "final_result") else str(result)
            history = result.history if hasattr(result, "history") else []
            logs.append(collector_log("browser_use_done", f"steps={len(history)} result_len={len(str(final_result))}"))

            record = CollectorRawRecord(
                record_type="web_page",
                source_url=start_url or "browser_use://task",
                content={
                    "task": task,
                    "start_url": start_url,
                    "result": final_result,
                    "steps_taken": len(history),
                    "provider": _provider(),
                    "backend": "obscura" if cdp_url else "chromium",
                },
                collected_at=collected_at,
            )
            return CollectionResult(raw_records=[record], logs=logs, errors=errors)

        except Exception as exc:
            msg = f"browser_use_collect_error: {exc}"
            errors.append(msg)
            logs.append(collector_log("browser_use_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)
