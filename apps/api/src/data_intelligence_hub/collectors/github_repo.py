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
        latest_release = await self._get_latest_release(config["owner"], config["repo"])
        readme = await self._get_readme(config["owner"], config["repo"])
        content = _repo_content(repo, latest_release, readme)
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

    async def _get_latest_release(self, owner: str, repo: str) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        try:
            if self.http_client is not None:
                return await _fetch_json(self.http_client, url)
            async with httpx.AsyncClient() as client:
                return await _fetch_json(client, url)
        except CollectorError as exc:
            if str(exc) == "http_not_found: upstream returned 404":
                return None
            raise

    async def _get_readme(self, owner: str, repo: str) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        try:
            if self.http_client is not None:
                return await _fetch_json(self.http_client, url)
            async with httpx.AsyncClient() as client:
                return await _fetch_json(client, url)
        except CollectorError as exc:
            if str(exc) == "http_not_found: upstream returned 404":
                return None
            raise


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


def _repo_content(
    repo: dict[str, Any],
    latest_release: dict[str, Any] | None = None,
    readme: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owner = repo.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    owner_type = owner.get("type") if isinstance(owner, dict) else None
    license_value = repo.get("license")
    release = _release_content(latest_release)
    readme_content = _readme_content(readme)
    issue_activity = _issue_activity_content(repo)
    commit_freshness = _commit_freshness_content(repo.get("pushed_at"))
    return {
        "provider": "github",
        "kind": "repository",
        "schema_version": "github_repo.v3",
        "owner": owner_login,
        "owner_login": owner_login,
        "owner_type": owner_type,
        "name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "stargazers_count": repo.get("stargazers_count"),
        "forks_count": repo.get("forks_count"),
        "open_issues_count": repo.get("open_issues_count"),
        "watchers_count": repo.get("watchers_count"),
        "subscribers_count": repo.get("subscribers_count"),
        "language": repo.get("language"),
        "topics": repo.get("topics"),
        "license_spdx_id": _license_spdx_id(license_value),
        "license_name": _license_name(license_value),
        "default_branch": repo.get("default_branch"),
        "homepage": repo.get("homepage"),
        "archived": repo.get("archived"),
        "fork": repo.get("fork"),
        "disabled": repo.get("disabled"),
        "visibility": repo.get("visibility"),
        "created_at": repo.get("created_at"),
        "pushed_at": repo.get("pushed_at"),
        "updated_at": repo.get("updated_at"),
        "readme": readme_content,
        "readme_detected": readme is not None,
        "readme_name": readme_content.get("name") if readme_content else None,
        "readme_path": readme_content.get("path") if readme_content else None,
        "readme_html_url": readme_content.get("html_url") if readme_content else None,
        "readme_download_url": readme_content.get("download_url") if readme_content else None,
        "readme_sha": readme_content.get("sha") if readme_content else None,
        "readme_size": readme_content.get("size") if readme_content else None,
        "issue_activity": issue_activity,
        "issue_activity_open_count": issue_activity.get("open_count"),
        "issue_activity_status": issue_activity.get("status"),
        "issue_activity_updated_at": issue_activity.get("updated_at"),
        "commit_freshness": commit_freshness,
        "commit_freshness_days": commit_freshness.get("days_since_push"),
        "commit_freshness_status": commit_freshness.get("status"),
        "latest_release": release,
        "latest_release_tag": release.get("tag_name") if release else None,
        "latest_release_name": release.get("name") if release else None,
        "latest_release_published_at": release.get("published_at") if release else None,
        "latest_release_url": release.get("html_url") if release else None,
        "latest_release_prerelease": release.get("prerelease") if release else None,
        "provenance": {
            "source": "github_repository_api",
            "api_endpoint": (
                f"https://api.github.com/repos/{owner_login}/{repo.get('name')}"
                if owner_login and repo.get("name")
                else None
            ),
            "latest_release_endpoint": (
                f"https://api.github.com/repos/{owner_login}/{repo.get('name')}/releases/latest"
                if owner_login and repo.get("name")
                else None
            ),
            "latest_release_found": latest_release is not None,
            "readme_endpoint": (
                f"https://api.github.com/repos/{owner_login}/{repo.get('name')}/readme"
                if owner_login and repo.get("name")
                else None
            ),
            "readme_found": readme is not None,
        },
        "raw": repo,
    }


def _release_content(release: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(release, dict):
        return None
    return {
        "tag_name": release.get("tag_name"),
        "name": release.get("name"),
        "html_url": release.get("html_url"),
        "published_at": release.get("published_at"),
        "created_at": release.get("created_at"),
        "prerelease": release.get("prerelease"),
        "draft": release.get("draft"),
    }


def _readme_content(readme: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(readme, dict):
        return None
    return {
        "name": readme.get("name"),
        "path": readme.get("path"),
        "sha": readme.get("sha"),
        "html_url": readme.get("html_url"),
        "download_url": readme.get("download_url"),
        "size": readme.get("size"),
        "encoding": readme.get("encoding"),
    }


def _issue_activity_content(repo: dict[str, Any]) -> dict[str, Any]:
    open_count = repo.get("open_issues_count")
    if not isinstance(open_count, int):
        open_count = repo.get("open_issues")
    status = "unknown"
    if isinstance(open_count, int):
        status = "active" if open_count > 0 else "quiet"
    return {
        "open_count": open_count if isinstance(open_count, int) else None,
        "status": status,
        "updated_at": repo.get("updated_at"),
    }


def _commit_freshness_content(pushed_at: object) -> dict[str, Any]:
    days_since_push = _days_since_iso(pushed_at)
    if days_since_push is None:
        status = "unknown"
    elif days_since_push <= 30:
        status = "fresh"
    elif days_since_push <= 180:
        status = "aging"
    else:
        status = "stale"
    return {
        "pushed_at": pushed_at if isinstance(pushed_at, str) else None,
        "days_since_push": days_since_push,
        "status": status,
    }


def _days_since_iso(value: object) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max((datetime.now(UTC) - parsed.astimezone(UTC)).days, 0)


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
