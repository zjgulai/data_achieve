from __future__ import annotations

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


class GitHubRepoCollector(BaseCollector):
    collector_type = "github_repo"

    def validate_config(self) -> dict[str, Any]:
        return {
            "owner": require_text(self.config, "owner"),
            "repo": require_text(self.config, "repo"),
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        await self._get_repo(config["owner"], config["repo"])
        return CollectorTestResult(
            status="ok",
            message="GitHub repository is reachable.",
            logs=[collector_log("collector_tested", "GitHub repository endpoint responded.")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        repo = await self._get_repo(config["owner"], config["repo"])
        content = _repo_content(repo)
        source_url = content.get("html_url") if isinstance(content.get("html_url"), str) else None
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="github_repo",
                    source_url=source_url,
                    content=content,
                )
            ],
            logs=[collector_log("github_repo_collected", f"Collected {content['full_name']}.")],
            errors=[],
        )

    async def _get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        if self.http_client is not None:
            return await _fetch_json(self.http_client, url)
        async with httpx.AsyncClient() as client:
            return await _fetch_json(client, url)


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    try:
        response = await collector_get_with_retry(client, url)
        data = response.json()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    except ValueError as exc:
        raise CollectorError("http_invalid_json: upstream response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise CollectorError("http_invalid_json: upstream response must be a JSON object")
    return cast(dict[str, Any], data)


def _repo_content(repo: dict[str, Any]) -> dict[str, Any]:
    owner = repo.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    return {
        "provider": "github",
        "kind": "repository",
        "owner": owner_login,
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "stargazers_count": repo.get("stargazers_count"),
        "forks_count": repo.get("forks_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "watchers_count": repo.get("watchers_count"),
        "default_branch": repo.get("default_branch"),
        "pushed_at": repo.get("pushed_at"),
        "updated_at": repo.get("updated_at"),
        "raw": repo,
    }
