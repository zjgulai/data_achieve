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

_NO_BROTLI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; data-scraper/1.0)",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


async def _json_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    r = await client.get(url, params=params, headers=_NO_BROTLI_HEADERS, timeout=15)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------------------
# Packagist (PHP)
# ---------------------------------------------------------------------------

class PackagistPackageCollector(BaseCollector):
    collector_type = "packagist_package"

    def validate_config(self) -> dict[str, Any]:
        package = require_text(self.config, "package")
        if "/" not in package:
            raise CollectorError("package must be in vendor/name format (e.g. laravel/framework)")
        return {"package": package}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await _json_get(
                    client, "https://packagist.org/packages/laravel/framework.json"
                )
                name = r.json().get("package", {}).get("name", "")
                logs.append(collector_log("test", f"packagist reachable, package={name!r}"))
                return CollectorTestResult(status="ok", message=f"Packagist reachable, fetched {name!r}", logs=logs)
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
                r = await _json_get(
                    client, f"https://packagist.org/packages/{package}.json"
                )
                data = r.json().get("package", {})
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        versions = data.get("versions", {})
        latest_key = next(
            (k for k in versions if not k.startswith("dev-")),
            next(iter(versions), None),
        )
        latest = versions.get(latest_key, {}) if latest_key else {}

        content: dict[str, Any] = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "type": data.get("type", ""),
            "repository": data.get("repository", ""),
            "downloads_total": data.get("downloads", {}).get("total", 0),
            "downloads_monthly": data.get("downloads", {}).get("monthly", 0),
            "favers": data.get("favers", 0),
            "versions_count": len(versions),
            "latest_version": latest_key or "",
            "license": latest.get("license", []),
            "homepage": latest.get("homepage", ""),
            "require": list((latest.get("require") or {}).keys()),
            "keywords": latest.get("keywords", []),
            "authors": [a.get("name", "") for a in (latest.get("authors") or [])],
            "time": latest.get("time", ""),
        }

        logs.append(collector_log("collect_done", f"package={package!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=f"https://packagist.org/packages/{package}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class PackagistSearchCollector(BaseCollector):
    collector_type = "packagist_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or not (1 <= max_items <= 100):
            raise CollectorError("max_items must be between 1 and 100")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await _json_get(
                    client, "https://packagist.org/search.json",
                    params={"q": "laravel", "per_page": "3"},
                )
                count = len(r.json().get("results", []))
                logs.append(collector_log("test", f"Packagist search returned {count} results"))
                return CollectorTestResult(status="ok", message="Packagist search reachable", logs=logs)
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
                r = await _json_get(
                    client, "https://packagist.org/search.json",
                    params={"q": query, "per_page": str(max_items)},
                )
                results = r.json().get("results", [])
                logs.append(collector_log("search", f"found {len(results)} packages"))
                for pkg in results:
                    raw_records.append(CollectorRawRecord(
                        record_type="product",
                        source_url=f"https://packagist.org/packages/{pkg.get('name', '')}",
                        content={
                            "name": pkg.get("name", ""),
                            "description": pkg.get("description", ""),
                            "url": pkg.get("url", ""),
                            "repository": pkg.get("repository", ""),
                            "downloads": pkg.get("downloads", 0),
                            "favers": pkg.get("favers", 0),
                        },
                    ))
                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


# ---------------------------------------------------------------------------
# NuGet (.NET)
# ---------------------------------------------------------------------------

class NuGetPackageCollector(BaseCollector):
    collector_type = "nuget_package"

    def validate_config(self) -> dict[str, Any]:
        return {"package": require_text(self.config, "package")}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(
                    client,
                    "https://azuresearch-usnc.nuget.org/query",
                    params={"q": "newtonsoft.json", "take": "1", "prerelease": "false"},
                )
                count = r.json().get("totalHits", 0)
                logs.append(collector_log("test", f"NuGet API reachable, totalHits={count}"))
                return CollectorTestResult(status="ok", message="NuGet API reachable", logs=logs)
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
                r = await collector_get_with_retry(
                    client,
                    "https://azuresearch-usnc.nuget.org/query",
                    params={"q": package, "take": "1", "prerelease": "false"},
                )
                data = r.json()
                items = data.get("data", [])
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if not items:
            errors.append(f"package not found: {package!r}")
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        pkg = items[0]
        content: dict[str, Any] = {
            "id": pkg.get("id", ""),
            "version": pkg.get("version", ""),
            "description": pkg.get("description", ""),
            "summary": pkg.get("summary", ""),
            "authors": pkg.get("authors", []),
            "owners": pkg.get("owners", []),
            "tags": pkg.get("tags", []),
            "total_downloads": pkg.get("totalDownloads", 0),
            "verified": pkg.get("verified", False),
            "project_url": pkg.get("projectUrl", ""),
            "license_url": pkg.get("licenseUrl", ""),
            "icon_url": pkg.get("iconUrl", ""),
            "package_types": [t.get("name") for t in pkg.get("packageTypes", [])],
            "versions_count": len(pkg.get("versions", [])),
        }

        logs.append(collector_log("collect_done", f"package={package!r} version={content['version']!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=f"https://www.nuget.org/packages/{pkg.get('id', package)}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class NuGetSearchCollector(BaseCollector):
    collector_type = "nuget_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or not (1 <= max_items <= 100):
            raise CollectorError("max_items must be between 1 and 100")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(
                    client,
                    "https://azuresearch-usnc.nuget.org/query",
                    params={"q": "json", "take": "3", "prerelease": "false"},
                )
                count = len(r.json().get("data", []))
                logs.append(collector_log("test", f"NuGet search returned {count} results"))
                return CollectorTestResult(status="ok", message="NuGet search reachable", logs=logs)
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
                r = await collector_get_with_retry(
                    client,
                    "https://azuresearch-usnc.nuget.org/query",
                    params={"q": query, "take": str(max_items), "prerelease": "false"},
                )
                items = r.json().get("data", [])
                logs.append(collector_log("search", f"found {len(items)} packages"))
                for pkg in items:
                    raw_records.append(CollectorRawRecord(
                        record_type="product",
                        source_url=f"https://www.nuget.org/packages/{pkg.get('id', '')}",
                        content={
                            "id": pkg.get("id", ""),
                            "version": pkg.get("version", ""),
                            "description": pkg.get("description", ""),
                            "authors": pkg.get("authors", []),
                            "total_downloads": pkg.get("totalDownloads", 0),
                            "verified": pkg.get("verified", False),
                            "tags": pkg.get("tags", []),
                        },
                    ))
                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


# ---------------------------------------------------------------------------
# pub.dev (Dart / Flutter)
# ---------------------------------------------------------------------------

class PubDevPackageCollector(BaseCollector):
    collector_type = "pubdev_package"

    def validate_config(self) -> dict[str, Any]:
        return {"package": require_text(self.config, "package")}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(
                    client, "https://pub.dev/api/packages/http"
                )
                name = r.json().get("name", "")
                logs.append(collector_log("test", f"pub.dev reachable, package={name!r}"))
                return CollectorTestResult(status="ok", message=f"pub.dev reachable, fetched {name!r}", logs=logs)
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
                r = await collector_get_with_retry(
                    client, f"https://pub.dev/api/packages/{package}"
                )
                data = r.json()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        latest = data.get("latest", {})
        pubspec = latest.get("pubspec", {})

        content: dict[str, Any] = {
            "name": data.get("name", ""),
            "version": latest.get("version", ""),
            "description": pubspec.get("description", ""),
            "homepage": pubspec.get("homepage", ""),
            "repository": pubspec.get("repository", ""),
            "documentation": pubspec.get("documentation", ""),
            "environment": pubspec.get("environment", {}),
            "dependencies": list((pubspec.get("dependencies") or {}).keys()),
            "dev_dependencies": list((pubspec.get("dev_dependencies") or {}).keys()),
            "flutter_support": "flutter" in (pubspec.get("dependencies") or {}),
            "published_at": latest.get("published", ""),
        }

        logs.append(collector_log("collect_done", f"package={package!r} version={content['version']!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=f"https://pub.dev/packages/{package}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class PubDevSearchCollector(BaseCollector):
    collector_type = "pubdev_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or not (1 <= max_items <= 100):
            raise CollectorError("max_items must be between 1 and 100")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(
                    client, "https://pub.dev/api/search",
                    params={"q": "http", "page": "1"},
                )
                count = len(r.json().get("packages", []))
                logs.append(collector_log("test", f"pub.dev search returned {count} results"))
                return CollectorTestResult(status="ok", message="pub.dev search reachable", logs=logs)
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
                collected = 0
                page = 1
                while collected < max_items:
                    r = await collector_get_with_retry(
                        client, "https://pub.dev/api/search",
                        params={"q": query, "page": str(page)},
                    )
                    data = r.json()
                    pkgs = data.get("packages", [])
                    if not pkgs:
                        break

                    for pkg in pkgs:
                        if collected >= max_items:
                            break
                        name = pkg.get("package", "")
                        raw_records.append(CollectorRawRecord(
                            record_type="product",
                            source_url=f"https://pub.dev/packages/{name}",
                            content={"name": name, "query": query},
                        ))
                        collected += 1

                    if not data.get("next"):
                        break
                    page += 1

                logs.append(collector_log("search", f"query={query!r} collected={len(raw_records)}"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
