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
        owner = config["owner"]
        repo_name = config["repo"]
        repo = await self._get_repo(owner, repo_name)
        latest_release = await self._get_latest_release(owner, repo_name)
        readme = await self._get_readme(owner, repo_name)
        content = _repo_content(repo, latest_release=latest_release, readme=readme)
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
            data = await _fetch_json(self.http_client, url)
            assert data is not None
            return data
        async with httpx.AsyncClient() as client:
            data = await _fetch_json(client, url)
            assert data is not None
            return data

    async def _get_latest_release(self, owner: str, repo: str) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        if self.http_client is not None:
            return await _fetch_json(self.http_client, url, allow_not_found=True)
        async with httpx.AsyncClient() as client:
            return await _fetch_json(client, url, allow_not_found=True)

    async def _get_readme(self, owner: str, repo: str) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        if self.http_client is not None:
            return await _fetch_json(self.http_client, url, allow_not_found=True)
        async with httpx.AsyncClient() as client:
            return await _fetch_json(client, url, allow_not_found=True)


async def _fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    allow_not_found: bool = False,
) -> dict[str, Any] | None:
    try:
        response = await collector_get_with_retry(client, url)
        data = response.json()
    except httpx.HTTPStatusError as exc:
        if allow_not_found and exc.response.status_code == 404:
            return None
        raise CollectorError(collector_http_error_message(exc)) from exc
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    except ValueError as exc:
        raise CollectorError("http_invalid_json: upstream response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise CollectorError("http_invalid_json: upstream response must be a JSON object")
    return cast(dict[str, Any], data)


def _repo_content(
    repo: dict[str, Any],
    *,
    latest_release: dict[str, Any] | None = None,
    readme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owner = repo.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    license_summary = _license_summary(repo.get("license"))
    latest_release_summary = _release_summary(latest_release)
    readme_summary = _readme_summary(readme)
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
        "subscribers_count": repo.get("subscribers_count"),
        "network_count": repo.get("network_count"),
        "language": repo.get("language"),
        "topics": repo.get("topics"),
        "license": license_summary,
        "license_spdx_id": (
            license_summary.get("spdx_id") if isinstance(license_summary, dict) else None
        ),
        "default_branch": repo.get("default_branch"),
        "archived": repo.get("archived"),
        "disabled": repo.get("disabled"),
        "visibility": repo.get("visibility"),
        "homepage": repo.get("homepage"),
        "pushed_at": repo.get("pushed_at"),
        "updated_at": repo.get("updated_at"),
        "latest_release": latest_release_summary,
        "latest_release_tag": (
            latest_release_summary.get("tag_name")
            if isinstance(latest_release_summary, dict)
            else None
        ),
        "latest_release_published_at": (
            latest_release_summary.get("published_at")
            if isinstance(latest_release_summary, dict)
            else None
        ),
        "readme": readme_summary,
        "readme_present": readme_summary is not None,
        "readme_size": readme_summary.get("size") if isinstance(readme_summary, dict) else None,
        "raw": repo,
    }


def _license_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "key": value.get("key"),
        "name": value.get("name"),
        "spdx_id": value.get("spdx_id"),
        "url": value.get("url"),
    }


def _release_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "tag_name": value.get("tag_name"),
        "name": value.get("name"),
        "html_url": value.get("html_url"),
        "published_at": value.get("published_at"),
        "created_at": value.get("created_at"),
        "draft": value.get("draft"),
        "prerelease": value.get("prerelease"),
    }


def _readme_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "name": value.get("name"),
        "path": value.get("path"),
        "sha": value.get("sha"),
        "size": value.get("size"),
        "html_url": value.get("html_url"),
        "download_url": value.get("download_url"),
        "encoding": value.get("encoding"),
    }
