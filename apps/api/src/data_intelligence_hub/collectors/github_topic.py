from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_get_with_retry,
    collector_http_error_message,
    collector_log,
    require_text,
)


class GitHubTopicCollector(BaseCollector):
    collector_type = "github_topic"

    def validate_config(self) -> dict[str, Any]:
        max_results = self.config.get("max_results", 30)
        if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
            raise CollectorError("max_results must be an integer from 1 to 100")
        return {
            "topic": require_text(self.config, "topic"),
            "max_results": max_results,
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        await self._search(config["topic"], 1)
        return CollectorTestResult(
            status="ok",
            message="GitHub topic search is reachable.",
            logs=[collector_log("collector_tested", "GitHub topic search endpoint responded.")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        result = await self._search(config["topic"], config["max_results"])
        items = result.get("items")
        repositories = (
            [_repo_summary(item) for item in items if isinstance(item, dict)]
            if isinstance(items, list)
            else []
        )
        collected_at = datetime.now(UTC).isoformat()
        content: dict[str, Any] = {
            "provider": "github",
            "kind": "topic_search",
            "schema_version": "github_topic.v2",
            "topic": config["topic"],
            "total_count": result.get("total_count"),
            "repositories": repositories,
            "provenance": {
                "source": "github_search_api",
                "api_endpoint": "https://api.github.com/search/repositories",
                "query": f"topic:{config['topic']}",
                "sort": "stars",
                "order": "desc",
                "per_page": config["max_results"],
                "collected_at": collected_at,
            },
            "raw": result,
        }
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="github_topic",
                    source_url=f"https://github.com/topics/{config['topic']}",
                    content=content,
                )
            ],
            logs=[
                collector_log(
                    "github_topic_collected",
                    f"Collected {len(repositories)} repositories for topic {config['topic']}.",
                )
            ],
            errors=[],
        )

    async def _search(self, topic: str, max_results: int) -> dict[str, Any]:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"topic:{topic}",
            "sort": "stars",
            "order": "desc",
            "per_page": str(max_results),
        }
        if self.http_client is not None:
            return await _fetch_json(self.http_client, url, params)
        async with httpx.AsyncClient() as client:
            return await _fetch_json(client, url, params)


async def _fetch_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
) -> dict[str, Any]:
    try:
        response = await collector_get_with_retry(client, url, params=params)
        data = response.json()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    except ValueError as exc:
        raise CollectorError("http_invalid_json: upstream response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise CollectorError("http_invalid_json: upstream response must be a JSON object")
    return cast(dict[str, Any], data)


def _repo_summary(repo: dict[str, Any]) -> dict[str, Any]:
    owner = repo.get("owner")
    license_value = repo.get("license")
    return {
        "provider": "github",
        "kind": "repository_search_result",
        "owner_login": owner.get("login") if isinstance(owner, dict) else None,
        "owner_type": owner.get("type") if isinstance(owner, dict) else None,
        "full_name": repo.get("full_name"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "stargazers_count": repo.get("stargazers_count"),
        "forks_count": repo.get("forks_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "watchers_count": repo.get("watchers_count"),
        "language": repo.get("language"),
        "topics": repo.get("topics"),
        "license_spdx_id": _license_spdx_id(license_value),
        "license_name": _license_name(license_value),
        "default_branch": repo.get("default_branch"),
        "homepage": repo.get("homepage"),
        "archived": repo.get("archived"),
        "fork": repo.get("fork"),
        "visibility": repo.get("visibility"),
        "created_at": repo.get("created_at"),
        "pushed_at": repo.get("pushed_at"),
        "updated_at": repo.get("updated_at"),
    }


def _license_spdx_id(license_value: object) -> str | None:
    if isinstance(license_value, dict):
        value = license_value.get("spdx_id") or license_value.get("key")
        return str(value) if value else None
    if isinstance(license_value, str):
        return license_value
    return None


def _license_name(license_value: object) -> str | None:
    if isinstance(license_value, dict):
        value = license_value.get("name")
        return str(value) if value else None
    return None
