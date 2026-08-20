"""AutoScraper-enhanced web collector — 智能网页内容提取.

AutoScraper 通过用户提供的示例数据自动学习提取规则，
无需手动编写 CSS selector 或 XPath。

使用场景:
1. 结构复杂、难以编写 selector 的网站
2. 需要快速原型的采集任务
3. 目标网站频繁改版，手动维护规则成本高

Environment variables:
    HTTP_PROXY          Optional proxy forwarded to httpx
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
from autoscraper import AutoScraper

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


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(
        timeout=30.0,
        proxy=proxy or None,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )


class AutoScraperEnhancedWebCollector(BaseCollector):
    collector_type = "autoscraper_enhanced_web"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        wanted_list = self.config.get("wanted_list", [])
        if not isinstance(wanted_list, list) or not wanted_list:
            raise CollectorError(
                "wanted_list must be a non-empty list of example strings to extract"
            )
        mode = self.config.get("mode", "exact")
        if mode not in {"exact", "similar"}:
            raise CollectorError("mode must be 'exact' or 'similar'")
        
        save_rules = self.config.get("save_rules", False)
        rules_path = self.config.get("rules_path", None)
        
        return {
            "url": url,
            "wanted_list": wanted_list,
            "mode": mode,
            "save_rules": save_rules,
            "rules_path": rules_path,
        }

    async def test(self) -> CollectorTestResult:
        try:
            async with _client() as c:
                r = await c.get("https://example.com")
            if r.status_code != 200:
                msg = f"HTTP test failed with status {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("autoscraper_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("autoscraper_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message="HTTP client ready",
            logs=[collector_log("autoscraper_test_ok", "ready")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        url: str = config["url"]
        wanted_list: list[str] = config["wanted_list"]
        mode: str = config["mode"]
        save_rules: bool = config["save_rules"]
        rules_path: str | None = config["rules_path"]

        try:
            async with _client() as c:
                r = await c.get(url)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("autoscraper_fetch_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        html_content = r.text

        scraper = AutoScraper()
        
        if rules_path and os.path.exists(rules_path):
            try:
                scraper.load(rules_path)
                logs.append(collector_log("autoscraper_rules_loaded", f"path={rules_path}"))
            except Exception as exc:
                logs.append(
                    collector_log(
                        "autoscraper_rules_load_failed",
                        f"path={rules_path} error={exc}",
                        level="warning",
                    )
                )

        try:
            scraper.build(html_content, wanted_list)
        except Exception as exc:
            msg = f"AutoScraper build failed: {exc}"
            errors.append(msg)
            logs.append(collector_log("autoscraper_build_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if mode == "exact":
            results = scraper.get_result(html_content)
        else:
            results = scraper.get_result_similar(html_content)

        if save_rules and rules_path:
            try:
                scraper.save(rules_path)
                logs.append(
                    collector_log("autoscraper_rules_saved", f"path={rules_path}")
                )
            except Exception as exc:
                logs.append(
                    collector_log(
                        "autoscraper_rules_save_failed",
                        f"path={rules_path} error={exc}",
                        level="warning",
                    )
                )

        if not results:
            msg = f"AutoScraper extracted 0 items (wanted_list={wanted_list})"
            logs.append(collector_log("autoscraper_no_results", msg, level="warning"))

        record = CollectorRawRecord(
            record_type="web_page",
            source_url=url,
            content={
                "url": url,
                "mode": mode,
                "wanted_list": wanted_list,
                "extracted_data": results,
                "extraction_count": len(results) if isinstance(results, list) else 0,
                "rules_saved": save_rules,
            },
            collected_at=collected_at,
        )

        logs.append(
            collector_log(
                "autoscraper_collected",
                f"url={url!r} mode={mode} "
                f"extracted={len(results) if isinstance(results, list) else 0}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
