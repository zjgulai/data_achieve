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
    collector_http_error_message,
    collector_log,
    require_text,
)

EXA_BASE_URL = "https://api.exa.ai"
EXA_TIMEOUT = 60.0

_VALID_SEARCH_TYPES = frozenset({
    "instant", "fast", "auto", "deep-lite", "deep", "deep-reasoning",
})
_DEEP_TYPES = frozenset({"deep-lite", "deep", "deep-reasoning"})

_VALID_CATEGORIES = frozenset({
    "company", "people", "publication", "news",
    "personal site", "financial report",
})

_VALID_CONTENTS_MODES = frozenset({"highlights", "text", "summary", "none"})


def _get_api_key() -> str:
    key = os.environ.get("EXA_API_KEY", "").strip()
    if not key:
        raise CollectorError("EXA_API_KEY not set — add to .env.production")
    return key


def _exa_client(api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=EXA_BASE_URL,
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=EXA_TIMEOUT,
    )


def _build_contents_block(config: dict[str, Any]) -> dict[str, Any] | None:
    mode = config.get("contents_mode", "highlights")
    if mode == "none":
        return None
    if mode == "highlights":
        return {"highlights": True}
    if mode == "text":
        max_chars = config.get("text_max_characters")
        text_opts: bool | dict[str, int] = (
            {"maxCharacters": int(max_chars)} if max_chars else True
        )
        return {"text": text_opts}
    if mode == "summary":
        summary_query = config.get("summary_query") or config.get("query", "")
        return {"summary": {"query": summary_query}}
    return {"highlights": True}


def _build_search_payload(config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": config["query"],
        "type": config.get("search_type", "auto"),
        "numResults": config.get("num_results", 10),
    }

    if config.get("category"):
        payload["category"] = config["category"]

    contents = _build_contents_block(config)
    if contents:
        payload["contents"] = contents

    if config.get("max_age_hours") is not None:
        payload.setdefault("contents", {})
        payload["contents"]["maxAgeHours"] = config["max_age_hours"]

    if config.get("output_schema"):
        payload["outputSchema"] = config["output_schema"]
    if config.get("system_prompt"):
        payload["systemPrompt"] = config["system_prompt"]
    if config.get("additional_queries"):
        payload["additionalQueries"] = config["additional_queries"]

    if config.get("include_domains"):
        payload["includeDomains"] = config["include_domains"]
    if config.get("exclude_domains"):
        payload["excludeDomains"] = config["exclude_domains"]
    if config.get("start_published_date"):
        payload["startPublishedDate"] = config["start_published_date"]
    if config.get("end_published_date"):
        payload["endPublishedDate"] = config["end_published_date"]

    return payload


def _extract_result_content(
    item: dict[str, Any],
    config: dict[str, Any],
    response_data: dict[str, Any],
) -> dict[str, Any]:
    output = response_data.get("output")
    output_content = output if isinstance(output, dict) else {}
    return {
        "query": config["query"],
        "search_type": config.get("search_type", "auto"),
        "category": config.get("category"),
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "score": item.get("score"),
        "published_date": item.get("publishedDate"),
        "author": item.get("author"),
        "image": item.get("image"),
        "favicon": item.get("favicon"),
        "highlights": item.get("highlights"),
        "highlight_scores": item.get("highlightScores"),
        "text": item.get("text"),
        "summary": item.get("summary"),
        "structured_output": output_content.get("content"),
        "grounding": output_content.get("grounding"),
        "request_id": response_data.get("requestId"),
        "resolved_search_type": response_data.get("resolvedSearchType"),
    }


class ExaSearchCollector(BaseCollector):
    collector_type = "exa_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        search_type = self.config.get("search_type", "auto")
        if search_type not in _VALID_SEARCH_TYPES:
            raise CollectorError(
                f"search_type must be one of {sorted(_VALID_SEARCH_TYPES)}"
            )

        is_deep = search_type in _DEEP_TYPES
        max_n = 25 if is_deep else 10
        num_results = self.config.get("num_results", 10)
        if not isinstance(num_results, int) or not (1 <= num_results <= max_n):
            raise CollectorError(
                f"num_results must be 1-{max_n} for search_type={search_type!r}"
            )

        category = self.config.get("category")
        if category and category not in _VALID_CATEGORIES:
            raise CollectorError(
                f"category must be one of {sorted(_VALID_CATEGORIES)}"
            )

        contents_mode = self.config.get("contents_mode", "highlights")
        if contents_mode not in _VALID_CONTENTS_MODES:
            raise CollectorError(
                f"contents_mode must be one of {sorted(_VALID_CONTENTS_MODES)}"
            )

        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, dict):
            raise CollectorError("output_schema must be a dict (JSON Schema)")

        include_domains = self.config.get("include_domains", [])
        exclude_domains = self.config.get("exclude_domains", [])
        if not isinstance(include_domains, list):
            raise CollectorError("include_domains must be a list")
        if not isinstance(exclude_domains, list):
            raise CollectorError("exclude_domains must be a list")

        return {
            "query": query,
            "search_type": search_type,
            "category": category,
            "num_results": num_results,
            "contents_mode": contents_mode,
            "output_schema": output_schema,
            "system_prompt": self.config.get("system_prompt"),
            "additional_queries": self.config.get("additional_queries"),
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "start_published_date": self.config.get("start_published_date"),
            "end_published_date": self.config.get("end_published_date"),
            "max_age_hours": self.config.get("max_age_hours"),
            "summary_query": self.config.get("summary_query"),
            "text_max_characters": self.config.get("text_max_characters"),
        }

    async def test(self) -> CollectorTestResult:
        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("exa_search_test_failed", str(exc), level="error")],
            )

        test_config = {**config, "num_results": 1, "contents_mode": "none"}
        payload = _build_search_payload(test_config)
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/search", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("exa_search_test_failed", msg, level="error")],
            )

        if r.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"Exa /search returned HTTP {r.status_code}: {r.text[:200]}",
                logs=[collector_log("exa_search_test_failed", r.text[:200])],
            )

        data = r.json()
        results = data.get("results", [])
        info = (
            f"query={config['query']!r} type={config['search_type']!r}"
            f" category={config.get('category')} hits={len(results)}"
        )
        return CollectorTestResult(
            status="ok",
            message=f"Exa /search reachable — {info}",
            logs=[collector_log("exa_search_test_ok", info)],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("exa_search_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        payload = _build_search_payload(config)
        collected_at = datetime.now(UTC)

        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/search", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_search_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code != 200:
            msg = f"Exa /search HTTP {r.status_code}: {r.text[:300]}"
            errors.append(msg)
            logs.append(collector_log("exa_search_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        data = r.json()
        results: list[dict[str, Any]] = data.get("results", [])

        is_deep = config.get("search_type", "auto") in _DEEP_TYPES
        record_type = "research_report" if is_deep else "search_result"

        records = [
            CollectorRawRecord(
                record_type=record_type,
                source_url=item.get("url"),
                content=_extract_result_content(item, config, data),
                collected_at=collected_at,
            )
            for item in results
        ]

        logs.append(
            collector_log(
                "exa_search_collected",
                f"query={config['query']!r} type={config['search_type']!r}"
                f" category={config.get('category')} records={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class ExaFindSimilarCollector(BaseCollector):
    collector_type = "exa_find_similar"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        num_results = self.config.get("num_results", 10)
        if not isinstance(num_results, int) or not (1 <= num_results <= 25):
            raise CollectorError("num_results must be 1-25")
        exclude_source = self.config.get("exclude_source_domain", True)
        if not isinstance(exclude_source, bool):
            raise CollectorError("exclude_source_domain must be bool")
        return {
            "url": url,
            "num_results": num_results,
            "exclude_source_domain": exclude_source,
            "contents_mode": self.config.get("contents_mode", "highlights"),
            "include_domains": self.config.get("include_domains", []),
            "exclude_domains": self.config.get("exclude_domains", []),
            "start_published_date": self.config.get("start_published_date"),
            "end_published_date": self.config.get("end_published_date"),
        }

    async def test(self) -> CollectorTestResult:
        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("exa_similar_test_failed", str(exc), level="error")],
            )

        payload: dict[str, Any] = {
            "url": config["url"],
            "numResults": 1,
            "excludeSourceDomain": config["exclude_source_domain"],
        }
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/findSimilar", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("exa_similar_test_failed", msg, level="error")],
            )

        if r.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"Exa /findSimilar HTTP {r.status_code}: {r.text[:200]}",
                logs=[collector_log("exa_similar_test_failed", r.text[:200])],
            )

        return CollectorTestResult(
            status="ok",
            message=f"Exa /findSimilar reachable, url={config['url']!r}",
            logs=[collector_log("exa_similar_test_ok", f"url={config['url']!r}")],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("exa_similar_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        payload: dict[str, Any] = {
            "url": config["url"],
            "numResults": config["num_results"],
            "excludeSourceDomain": config["exclude_source_domain"],
        }
        contents = _build_contents_block(config)
        if contents:
            payload["contents"] = contents
        if config.get("include_domains"):
            payload["includeDomains"] = config["include_domains"]
        if config.get("exclude_domains"):
            payload["excludeDomains"] = config["exclude_domains"]
        if config.get("start_published_date"):
            payload["startPublishedDate"] = config["start_published_date"]
        if config.get("end_published_date"):
            payload["endPublishedDate"] = config["end_published_date"]

        collected_at = datetime.now(UTC)
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/findSimilar", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_similar_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code != 200:
            msg = f"Exa /findSimilar HTTP {r.status_code}: {r.text[:300]}"
            errors.append(msg)
            logs.append(collector_log("exa_similar_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        data = r.json()
        results: list[dict[str, Any]] = data.get("results", [])

        records = [
            CollectorRawRecord(
                record_type="search_result",
                source_url=item.get("url"),
                content={
                    "seed_url": config["url"],
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "score": item.get("score"),
                    "published_date": item.get("publishedDate"),
                    "author": item.get("author"),
                    "highlights": item.get("highlights"),
                    "highlight_scores": item.get("highlightScores"),
                    "text": item.get("text"),
                    "summary": item.get("summary"),
                    "request_id": data.get("requestId"),
                },
                collected_at=collected_at,
            )
            for item in results
        ]

        logs.append(
            collector_log(
                "exa_similar_collected",
                f"seed={config['url']!r} records={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class ExaContentsCollector(BaseCollector):
    collector_type = "exa_contents"

    def validate_config(self) -> dict[str, Any]:
        urls = self.config.get("urls", [])
        if not isinstance(urls, list) or not urls:
            raise CollectorError("urls must be a non-empty list of URL strings")
        if len(urls) > 100:
            raise CollectorError("urls must contain at most 100 URLs")
        for u in urls:
            if not isinstance(u, str) or not u.strip():
                raise CollectorError("each url must be a non-empty string")

        contents_mode = self.config.get("contents_mode", "highlights")
        if contents_mode not in _VALID_CONTENTS_MODES:
            raise CollectorError(
                f"contents_mode must be one of {sorted(_VALID_CONTENTS_MODES)}"
            )

        max_age_hours = self.config.get("max_age_hours")
        subpages = self.config.get("subpages", 0)
        if not isinstance(subpages, int) or not (0 <= subpages <= 100):
            raise CollectorError("subpages must be 0-100")

        return {
            "urls": [u.strip() for u in urls],
            "contents_mode": contents_mode,
            "max_age_hours": max_age_hours,
            "subpages": subpages,
            "subpage_target": self.config.get("subpage_target", []),
            "summary_query": self.config.get("summary_query"),
            "text_max_characters": self.config.get("text_max_characters"),
        }

    async def test(self) -> CollectorTestResult:
        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("exa_contents_test_failed", str(exc), level="error")],
            )

        payload: dict[str, Any] = {
            "urls": config["urls"][:1],
            "highlights": True,
        }
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/contents", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("exa_contents_test_failed", msg, level="error")],
            )

        if r.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"Exa /contents HTTP {r.status_code}: {r.text[:200]}",
                logs=[collector_log("exa_contents_test_failed", r.text[:200])],
            )

        return CollectorTestResult(
            status="ok",
            message=f"Exa /contents reachable, urls={config['urls'][:1]}",
            logs=[collector_log("exa_contents_test_ok", f"count={len(config['urls'])}")],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("exa_contents_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        payload: dict[str, Any] = {"urls": config["urls"]}

        mode = config.get("contents_mode", "highlights")
        if mode == "highlights":
            payload["highlights"] = True
        elif mode == "text":
            max_chars = config.get("text_max_characters")
            payload["text"] = {"maxCharacters": max_chars} if max_chars else True
        elif mode == "summary":
            sq = config.get("summary_query") or ""
            payload["summary"] = {"query": sq} if sq else True

        if config.get("max_age_hours") is not None:
            payload["maxAgeHours"] = config["max_age_hours"]
        if config.get("subpages", 0) > 0:
            payload["subpages"] = config["subpages"]
            if config.get("subpage_target"):
                payload["subpageTarget"] = config["subpage_target"]

        collected_at = datetime.now(UTC)
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/contents", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_contents_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code != 200:
            msg = f"Exa /contents HTTP {r.status_code}: {r.text[:300]}"
            errors.append(msg)
            logs.append(collector_log("exa_contents_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        data = r.json()
        results: list[dict[str, Any]] = data.get("results", [])

        records = [
            CollectorRawRecord(
                record_type="web_page_markdown",
                source_url=item.get("url"),
                content={
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "published_date": item.get("publishedDate"),
                    "author": item.get("author"),
                    "highlights": item.get("highlights"),
                    "highlight_scores": item.get("highlightScores"),
                    "text": item.get("text"),
                    "summary": item.get("summary"),
                    "request_id": data.get("requestId"),
                },
                collected_at=collected_at,
            )
            for item in results
        ]

        logs.append(
            collector_log(
                "exa_contents_collected",
                f"urls={len(config['urls'])} records={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class ExaAnswerCollector(BaseCollector):
    collector_type = "exa_answer"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        output_schema = self.config.get("output_schema")
        if output_schema is not None and not isinstance(output_schema, dict):
            raise CollectorError("output_schema must be a dict (JSON Schema)")
        return {
            "query": query,
            "output_schema": output_schema,
            "text": self.config.get("text", False),
        }

    async def test(self) -> CollectorTestResult:
        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("exa_answer_test_failed", str(exc), level="error")],
            )

        payload: dict[str, Any] = {"query": config["query"], "text": False}
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/answer", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("exa_answer_test_failed", msg, level="error")],
            )

        if r.status_code != 200:
            return CollectorTestResult(
                status="failed",
                message=f"Exa /answer HTTP {r.status_code}: {r.text[:200]}",
                logs=[collector_log("exa_answer_test_failed", r.text[:200])],
            )

        return CollectorTestResult(
            status="ok",
            message=f"Exa /answer reachable, query={config['query']!r}",
            logs=[collector_log("exa_answer_test_ok", "ok")],
        )

    async def collect(self) -> CollectionResult:
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            config = self.validate_config()
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("exa_answer_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        payload: dict[str, Any] = {
            "query": config["query"],
            "text": config.get("text", False),
        }
        if config.get("output_schema"):
            payload["outputSchema"] = config["output_schema"]

        collected_at = datetime.now(UTC)
        try:
            async with _exa_client(api_key) as client:
                r = await client.post("/answer", json=payload)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("exa_answer_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code != 200:
            msg = f"Exa /answer HTTP {r.status_code}: {r.text[:300]}"
            errors.append(msg)
            logs.append(collector_log("exa_answer_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        data = r.json()
        record = CollectorRawRecord(
            record_type="ai_answer",
            source_url=None,
            content={
                "query": config["query"],
                "answer": data.get("answer"),
                "citations": data.get("citations", []),
                "request_id": data.get("requestId"),
            },
            collected_at=collected_at,
        )

        logs.append(
            collector_log(
                "exa_answer_collected",
                f"query={config['query']!r} citations={len(data.get('citations', []))}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
