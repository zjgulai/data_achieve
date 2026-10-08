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
ANYSEARCH_TIMEOUT = 30.0
ANYSEARCH_MAX_RESULTS = 50

ANYSEARCH_KNOWN_TAGS = {
    "code.doc",
}


def _get_api_key() -> str:
    key = os.environ.get("ANYSEARCH_API_KEY", "")
    if not key:
        raise CollectorError(
            "ANYSEARCH_API_KEY not set — add to .env.production"
        )
    return key


def _build_payload(config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": config["query"],
        "num_results": config["num_results"],
    }
    if config.get("site"):
        payload["site"] = config["site"]
    if config.get("tag"):
        payload["tag"] = config["tag"]
    if config.get("params"):
        payload["params"] = config["params"]
    return payload


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
        tag = self.config.get("tag")
        if tag is not None and not isinstance(tag, str):
            raise CollectorError("tag must be a string (e.g. 'code.doc', 'news')")
        params = self.config.get("params")
        if params is not None and not isinstance(params, dict):
            raise CollectorError("params must be a dict (e.g. {\"library\": \"golang\"})")
        return {
            "query": query,
            "num_results": num_results,
            "site": site,
            "tag": tag,
            "params": params,
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        api_key = _get_api_key()
        test_payload = _build_payload({**config, "num_results": 1})
        async with httpx.AsyncClient(timeout=ANYSEARCH_TIMEOUT) as client:
            r = await client.post(
                ANYSEARCH_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                json=test_payload,
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
        tag_info = f" tag={config['tag']!r}" if config.get("tag") else ""
        params_info = f" params={config['params']}" if config.get("params") else ""
        return CollectorTestResult(
            status="ok",
            message=f"AnySearch reachable, query={config['query']!r}{tag_info}{params_info}",
            logs=[collector_log("anysearch_test_ok", "api_key_valid")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        try:
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("anysearch_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        collected_at = datetime.now(UTC)
        payload = _build_payload(config)
        try:
            async with httpx.AsyncClient(timeout=ANYSEARCH_TIMEOUT) as client:
                r = await client.post(
                    ANYSEARCH_ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            msg = f"AnySearch network error: {exc}"
            errors.append(msg)
            logs.append(collector_log("anysearch_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code != 200:
            msg = f"AnySearch HTTP {r.status_code}: {r.text[:200]}"
            errors.append(msg)
            logs.append(collector_log("anysearch_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        data = r.json()
        if data.get("code") != 0:
            msg = f"AnySearch API error: {data.get('message')}"
            errors.append(msg)
            logs.append(collector_log("anysearch_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        results: list[dict[str, Any]] = data.get("data", {}).get("results", [])
        records = [
            CollectorRawRecord(
                record_type="search_result",
                source_url=item.get("url"),
                content={
                    "query": config["query"],
                    "tag": config.get("tag"),
                    "params": config.get("params"),
                    "site": config.get("site"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet"),
                    "published_date": item.get("published_date"),
                    "source": item.get("source"),
                    "score": item.get("score"),
                    "request_id": data.get("request_id"),
                },
                collected_at=collected_at,
            )
            for item in results
        ]
        logs.append(
            collector_log(
                "anysearch_collected",
                f"query={config['query']!r} tag={config.get('tag')!r} results={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
