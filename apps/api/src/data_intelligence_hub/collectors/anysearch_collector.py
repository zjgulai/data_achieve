from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)

ANYSEARCH_ENDPOINT = "https://api.anysearch.com/v1/search"
ANYSEARCH_TIMEOUT = 20.0
ANYSEARCH_MAX_RESULTS = 50


def _get_api_key() -> str:
    key = os.environ.get("ANYSEARCH_API_KEY", "")
    if not key:
        raise CollectorError(
            "ANYSEARCH_API_KEY not set — add to .env.production"
        )
    return key


class AnySearchCollector(BaseCollector):
    collector_type = "anysearch"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        num_results = self.config.get("num_results", 10)
        if not isinstance(num_results, int) or not (1 <= num_results <= ANYSEARCH_MAX_RESULTS):
            raise CollectorError(
                f"num_results must be an integer between 1 and {ANYSEARCH_MAX_RESULTS}"
            )
        site = self.config.get("site")
        if site is not None and not isinstance(site, str):
            raise CollectorError("site must be a string domain (e.g. 'trustpilot.com')")
        return {
            "query": query,
            "num_results": num_results,
            "site": site,
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        api_key = _get_api_key()
        payload: dict[str, Any] = {
            "query": config["query"],
            "num_results": 1,
        }
        if config.get("site"):
            payload["site"] = config["site"]
        async with httpx.AsyncClient(timeout=ANYSEARCH_TIMEOUT) as client:
            r = await client.post(
                ANYSEARCH_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        if r.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"AnySearch returned HTTP {r.status_code}",
                logs=[collector_log("anysearch_test_failed", r.text[:200])],
            )
        data = r.json()
        if data.get("code") != 0:
            return CollectorTestResult(
                status="failed",
                message=f"AnySearch error: {data.get('message')}",
                logs=[collector_log("anysearch_api_error", str(data.get("message")))],
            )
        return CollectorTestResult(
            status="ok",
            message=f"AnySearch reachable, query={config['query']!r}",
            logs=[collector_log("anysearch_test_ok", "api_key_valid")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        api_key = _get_api_key()
        collected_at = datetime.now(UTC)
        payload: dict[str, Any] = {
            "query": config["query"],
            "num_results": config["num_results"],
        }
        if config.get("site"):
            payload["site"] = config["site"]
        async with httpx.AsyncClient(timeout=ANYSEARCH_TIMEOUT) as client:
            r = await client.post(
                ANYSEARCH_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        if r.status_code != 200:
            raise CollectorError(f"AnySearch HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        if data.get("code") != 0:
            raise CollectorError(f"AnySearch API error: {data.get('message')}")
        results: list[dict[str, Any]] = data.get("data", {}).get("results", [])
        records = [
            CollectorRawRecord(
                record_type="search_result",
                source_url=item.get("url"),
                content={
                    "query": config["query"],
                    "site": config.get("site"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet"),
                    "published_date": item.get("published_date"),
                    "request_id": data.get("request_id"),
                },
                collected_at=collected_at,
            )
            for item in results
        ]
        return CollectionResult(
            raw_records=records,
            errors=[],
            logs=[
                collector_log(
                    "anysearch_collected",
                    f"query={config['query']!r} results={len(records)}",
                )
            ],
        )
