"""npm Registry + PyPI package info collectors - completely free, no API key required.

APIs:
  - npm: https://registry.npmjs.org/<package>
  - npm search: https://registry.npmjs.org/-/v1/search?text=<query>
  - PyPI: https://pypi.org/pypi/<package>/json
  - PyPI search: https://pypi.org/search/ (HTML scrape)
"""

from __future__ import annotations

from typing import Any

import httpx

from .base import (
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


class NpmPackageCollector(BaseCollector):
    """Fetch package metadata and download stats from the npm registry."""

    collector_type = "npm_package"

    def validate_config(self) -> dict[str, Any]:
        package = require_text(self.config, "package")
        return {"package": package}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client, "https://registry.npmjs.org/react"
                )
                name = response.json().get("name", "")
                logs.append(collector_log("test", f"npm registry reachable, package={name!r}"))
                return CollectorTestResult(
                    status="ok",
                    message=f"npm registry reachable, fetched {name!r}",
                    logs=logs,
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            logs.append(collector_log("test_failed", msg, "error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        package = config["package"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client, f"https://registry.npmjs.org/{package}"
                )
                data: dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        latest_version = data.get("dist-tags", {}).get("latest", "")
        latest_info: dict[str, Any] = data.get("versions", {}).get(latest_version, {})

        content = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "version": latest_version,
            "license": latest_info.get("license", ""),
            "homepage": data.get("homepage", ""),
            "repository": (data.get("repository") or {}).get("url", ""),
            "keywords": data.get("keywords", []),
            "author": data.get("author") or latest_info.get("author"),
            "maintainers": [m.get("name", "") for m in (data.get("maintainers") or [])[:5]],
            "dist_tags": data.get("dist-tags", {}),
            "versions_count": len(data.get("versions", {})),
            "time_created": data.get("time", {}).get("created", ""),
            "time_modified": data.get("time", {}).get("modified", ""),
            "dependencies": list((latest_info.get("dependencies") or {}).keys()),
            "peer_dependencies": list((latest_info.get("peerDependencies") or {}).keys()),
        }

        logs.append(collector_log("collect_done", f"package={package!r} version={latest_version!r}"))
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="product",
                    source_url=f"https://www.npmjs.com/package/{package}",
                    content=content,
                )
            ],
            logs=logs,
            errors=errors,
        )


class NpmSearchCollector(BaseCollector):
    """Search npm packages by keyword."""

    collector_type = "npm_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or max_items < 1 or max_items > 250:
            raise CollectorError("max_items must be between 1 and 250")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client,
                    "https://registry.npmjs.org/-/v1/search",
                    params={"text": "react", "size": "3"},
                )
                count = len(response.json().get("objects", []))
                logs.append(collector_log("test", f"npm search returned {count} results"))
                return CollectorTestResult(status="ok", message="npm search API reachable", logs=logs)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            logs.append(collector_log("test_failed", msg, "error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        query = config["query"]
        max_items = config["max_items"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client,
                    "https://registry.npmjs.org/-/v1/search",
                    params={"text": query, "size": str(max_items)},
                )
                data = response.json()
                objects = data.get("objects", [])
                logs.append(collector_log("search", f"found {len(objects)} packages"))

                for obj in objects:
                    pkg = obj.get("package", {})
                    raw_records.append(
                        CollectorRawRecord(
                            record_type="product",
                            source_url=f"https://www.npmjs.com/package/{pkg.get('name', '')}",
                            content={
                                "name": pkg.get("name", ""),
                                "version": pkg.get("version", ""),
                                "description": pkg.get("description", ""),
                                "keywords": pkg.get("keywords", []),
                                "author": (pkg.get("author") or {}).get("name", ""),
                                "publisher": (pkg.get("publisher") or {}).get("username", ""),
                                "score": obj.get("score", {}),
                                "search_score": obj.get("searchScore", 0),
                                "date": pkg.get("date", ""),
                                "links": pkg.get("links", {}),
                            },
                        )
                    )

                logs.append(collector_log("collect_done", f"collected {len(raw_records)} packages"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


class PyPIPackageCollector(BaseCollector):
    """Fetch package metadata from PyPI."""

    collector_type = "pypi_package"

    def validate_config(self) -> dict[str, Any]:
        package = require_text(self.config, "package")
        return {"package": package}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client, "https://pypi.org/pypi/requests/json"
                )
                name = response.json().get("info", {}).get("name", "")
                logs.append(collector_log("test", f"PyPI reachable, package={name!r}"))
                return CollectorTestResult(
                    status="ok",
                    message=f"PyPI reachable, fetched {name!r}",
                    logs=logs,
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            logs.append(collector_log("test_failed", msg, "error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        package = config["package"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client, f"https://pypi.org/pypi/{package}/json"
                )
                data: dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        info = data.get("info", {})
        releases = data.get("releases", {})
        latest_version = info.get("version", "")
        latest_files = releases.get(latest_version, [])

        content = {
            "name": info.get("name", ""),
            "version": latest_version,
            "summary": info.get("summary", ""),
            "description": info.get("description", "")[:500] if info.get("description") else "",
            "author": info.get("author", ""),
            "author_email": info.get("author_email", ""),
            "license": info.get("license", ""),
            "home_page": info.get("home_page", ""),
            "project_url": info.get("project_url", ""),
            "package_url": info.get("package_url", ""),
            "keywords": info.get("keywords", ""),
            "classifiers": info.get("classifiers", []),
            "requires_python": info.get("requires_python", ""),
            "requires_dist": info.get("requires_dist", []),
            "project_urls": info.get("project_urls", {}),
            "versions_count": len(releases),
            "latest_upload_time": latest_files[0].get("upload_time", "") if latest_files else "",
            "downloads": data.get("urls", [{}])[0].get("downloads", -1) if data.get("urls") else -1,
        }

        logs.append(collector_log("collect_done", f"package={package!r} version={latest_version!r}"))
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="product",
                    source_url=f"https://pypi.org/project/{package}/",
                    content=content,
                )
            ],
            logs=logs,
            errors=errors,
        )


class PyPISearchCollector(BaseCollector):
    """Search PyPI packages by keyword (HTML scrape)."""

    collector_type = "pypi_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or max_items < 1 or max_items > 100:
            raise CollectorError("max_items must be between 1 and 100")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client,
                    "https://pypi.org/search/",
                    params={"q": "requests", "o": "-created"},
                )
                ok = response.status_code == 200 and "package-snippet" in response.text
                logs.append(collector_log("test", f"PyPI search status={response.status_code} snippets_present={ok}"))
                return CollectorTestResult(
                    status="ok" if ok else "failed",
                    message="PyPI search HTML reachable" if ok else "no package snippets found",
                    logs=logs,
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            logs.append(collector_log("test_failed", msg, "error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        query = config["query"]
        max_items = config["max_items"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        try:
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await collector_get_with_retry(
                    client,
                    "https://pypi.org/search/",
                    params={"q": query, "o": "-created"},
                )

                soup = BeautifulSoup(response.text, "html.parser")
                snippets = soup.select("a.package-snippet")[:max_items]
                logs.append(collector_log("scrape", f"found {len(snippets)} package snippets"))

                for snippet in snippets:
                    name_el = snippet.select_one(".package-snippet__name")
                    ver_el = snippet.select_one(".package-snippet__version")
                    desc_el = snippet.select_one(".package-snippet__description")
                    date_el = snippet.select_one("time")
                    href = snippet.get("href", "")
                    link = f"https://pypi.org{href}" if href else None

                    pkg_name = (name_el.get_text(strip=True) if name_el else "").strip()
                    version = (ver_el.get_text(strip=True) if ver_el else "").strip()

                    raw_records.append(
                        CollectorRawRecord(
                            record_type="product",
                            source_url=link,
                            content={
                                "name": pkg_name,
                                "version": version,
                                "description": (desc_el.get_text(strip=True) if desc_el else "").strip(),
                                "url": link,
                                "released": date_el.get("datetime", "") if date_el else "",
                                "query": query,
                            },
                        )
                    )

                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except ImportError:
            errors.append("beautifulsoup4 not installed")
            logs.append(collector_log("import_error", "beautifulsoup4 missing", "error"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
