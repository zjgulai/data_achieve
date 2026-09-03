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

_CRATES_UA = "data-intelligence-hub/1.0 (scrapy.lute-tlz-dddd.top)"
_CRATES_HEADERS = {"User-Agent": _CRATES_UA, "Accept": "application/json"}


async def _crates_get(client: httpx.AsyncClient, url: str, params: dict[str, str] | None = None) -> httpx.Response:
    r = await client.get(url, params=params, headers=_CRATES_HEADERS, timeout=15)
    r.raise_for_status()
    return r


class CratesIoPackageCollector(BaseCollector):
    collector_type = "crates_package"

    def validate_config(self) -> dict[str, Any]:
        return {"package": require_text(self.config, "package")}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await _crates_get(client, "https://crates.io/api/v1/crates/serde")
                name = r.json().get("crate", {}).get("name", "")
                logs.append(collector_log("test", f"crates.io reachable, crate={name!r}"))
                return CollectorTestResult(status="ok", message=f"crates.io reachable, fetched {name!r}", logs=logs)
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
                r = await _crates_get(client, f"https://crates.io/api/v1/crates/{package}")
                data = r.json()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        crate = data.get("crate", {})
        versions = data.get("versions", [])
        latest = versions[0] if versions else {}

        content: dict[str, Any] = {
            "name": crate.get("name", ""),
            "description": crate.get("description", ""),
            "version": crate.get("newest_version", ""),
            "license": latest.get("license", ""),
            "homepage": crate.get("homepage", ""),
            "repository": crate.get("repository", ""),
            "documentation": crate.get("documentation", ""),
            "keywords": crate.get("keywords", []),
            "categories": crate.get("categories", []),
            "downloads": crate.get("downloads", 0),
            "recent_downloads": crate.get("recent_downloads", 0),
            "versions_count": len(versions),
            "created_at": crate.get("created_at", ""),
            "updated_at": crate.get("updated_at", ""),
        }

        logs.append(collector_log("collect_done", f"package={package!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=f"https://crates.io/crates/{package}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class CratesIoSearchCollector(BaseCollector):
    collector_type = "crates_search"

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
                r = await _crates_get(
                    client, "https://crates.io/api/v1/crates",
                    params={"q": "serde", "per_page": "3"},
                )
                count = len(r.json().get("crates", []))
                logs.append(collector_log("test", f"crates.io search returned {count} results"))
                return CollectorTestResult(status="ok", message="crates.io search reachable", logs=logs)
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
                r = await _crates_get(
                    client, "https://crates.io/api/v1/crates",
                    params={"q": query, "per_page": str(max_items)},
                )
                crates = r.json().get("crates", [])
                logs.append(collector_log("search", f"found {len(crates)} crates"))
                for c in crates:
                    raw_records.append(CollectorRawRecord(
                        record_type="product",
                        source_url=f"https://crates.io/crates/{c.get('name', '')}",
                        content={
                            "name": c.get("name", ""),
                            "description": c.get("description", ""),
                            "version": c.get("newest_version", ""),
                            "downloads": c.get("downloads", 0),
                            "recent_downloads": c.get("recent_downloads", 0),
                            "keywords": c.get("keywords", []),
                            "updated_at": c.get("updated_at", ""),
                        },
                    ))
                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


class RubyGemsPackageCollector(BaseCollector):
    collector_type = "rubygems_package"

    def validate_config(self) -> dict[str, Any]:
        return {"package": require_text(self.config, "package")}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(client, "https://rubygems.org/api/v1/gems/rails.json")
                name = r.json().get("name", "")
                logs.append(collector_log("test", f"RubyGems reachable, gem={name!r}"))
                return CollectorTestResult(status="ok", message=f"RubyGems reachable, fetched {name!r}", logs=logs)
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
                r = await collector_get_with_retry(client, f"https://rubygems.org/api/v1/gems/{package}.json")
                data = r.json()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        content: dict[str, Any] = {
            "name": data.get("name", ""),
            "version": data.get("version", ""),
            "info": data.get("info", ""),
            "licenses": data.get("licenses", []),
            "homepage_uri": data.get("homepage_uri", ""),
            "source_code_uri": data.get("source_code_uri", ""),
            "documentation_uri": data.get("documentation_uri", ""),
            "bug_tracker_uri": data.get("bug_tracker_uri", ""),
            "authors": data.get("authors", ""),
            "downloads": data.get("downloads", 0),
            "version_downloads": data.get("version_downloads", 0),
            "sha": data.get("sha", ""),
            "project_uri": data.get("project_uri", ""),
            "gem_uri": data.get("gem_uri", ""),
            "dependencies": {
                "runtime": [d.get("name") for d in data.get("dependencies", {}).get("runtime", [])],
                "development": [d.get("name") for d in data.get("dependencies", {}).get("development", [])],
            },
        }

        logs.append(collector_log("collect_done", f"package={package!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=data.get("project_uri") or f"https://rubygems.org/gems/{package}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class RubyGemsSearchCollector(BaseCollector):
    collector_type = "rubygems_search"

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
                    client, "https://rubygems.org/api/v1/search.json",
                    params={"query": "rails", "page": "1"},
                )
                count = len(r.json()) if isinstance(r.json(), list) else 0
                logs.append(collector_log("test", f"RubyGems search returned {count} results"))
                return CollectorTestResult(status="ok", message="RubyGems search reachable", logs=logs)
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
                    client, "https://rubygems.org/api/v1/search.json",
                    params={"query": query, "page": "1"},
                )
                gems = r.json() if isinstance(r.json(), list) else []
                gems = gems[:max_items]
                logs.append(collector_log("search", f"found {len(gems)} gems"))
                for g in gems:
                    raw_records.append(CollectorRawRecord(
                        record_type="product",
                        source_url=g.get("project_uri") or f"https://rubygems.org/gems/{g.get('name', '')}",
                        content={
                            "name": g.get("name", ""),
                            "version": g.get("version", ""),
                            "info": g.get("info", ""),
                            "downloads": g.get("downloads", 0),
                            "authors": g.get("authors", ""),
                            "licenses": g.get("licenses", []),
                        },
                    ))
                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


class GoPackageCollector(BaseCollector):
    collector_type = "go_package"

    def validate_config(self) -> dict[str, Any]:
        return {"package": require_text(self.config, "package")}

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await collector_get_with_retry(
                    client, "https://pkg.go.dev/search",
                    params={"q": "fmt", "m": "package"},
                )
                ok = r.status_code == 200
                logs.append(collector_log("test", f"pkg.go.dev reachable status={r.status_code}"))
                return CollectorTestResult(
                    status="ok" if ok else "failed",
                    message="pkg.go.dev reachable" if ok else f"status={r.status_code}",
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
                r = await collector_get_with_retry(
                    client, f"https://pkg.go.dev/{package}?tab=overview",
                )
                html = r.text
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            def _text(sel: str) -> str:
                el = soup.select_one(sel)
                return el.get_text(strip=True) if el else ""

            synopsis = _text(".Documentation-overview p") or _text('[data-kind="synopsis"]') or ""
            module = _text(".UnitMeta-repo a") or _text('[data-test-id="UnitHeader-module"] a') or ""
            version_el = soup.select_one(".UnitHeader-version") or soup.select_one('[data-test-id="UnitHeader-version"]')
            version = version_el.get_text(strip=True) if version_el else ""
            license_el = soup.select_one(".UnitMeta-license") or soup.select_one('[data-test-id="UnitHeader-licenses"]')
            license_text = license_el.get_text(strip=True) if license_el else ""

            content: dict[str, Any] = {
                "import_path": package,
                "synopsis": synopsis[:500],
                "module": module,
                "version": version,
                "license": license_text,
                "url": f"https://pkg.go.dev/{package}",
            }
        except ImportError:
            content = {
                "import_path": package,
                "url": f"https://pkg.go.dev/{package}",
                "note": "beautifulsoup4 not available for HTML parsing",
            }

        logs.append(collector_log("collect_done", f"package={package!r}"))
        return CollectionResult(
            raw_records=[CollectorRawRecord(
                record_type="product",
                source_url=f"https://pkg.go.dev/{package}",
                content=content,
            )],
            logs=logs,
            errors=errors,
        )


class GoSearchCollector(BaseCollector):
    collector_type = "go_search"

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
                    client, "https://pkg.go.dev/search",
                    params={"q": "http", "m": "package"},
                )
                ok = r.status_code == 200
                logs.append(collector_log("test", f"pkg.go.dev search status={r.status_code}"))
                return CollectorTestResult(
                    status="ok" if ok else "failed",
                    message="pkg.go.dev search reachable" if ok else f"status={r.status_code}",
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
                r = await collector_get_with_retry(
                    client, "https://pkg.go.dev/search",
                    params={"q": query, "m": "package"},
                )
                soup = BeautifulSoup(r.text, "html.parser")
                results = soup.select(".SearchSnippet")[:max_items]
                logs.append(collector_log("scrape", f"found {len(results)} packages"))

                for item in results:
                    name_el = item.select_one(".SearchSnippet-header-inner a") or item.select_one("h2 a")
                    synopsis_el = item.select_one(".SearchSnippet-synopsis") or item.select_one("p")
                    import_path = name_el["href"].lstrip("/") if name_el and name_el.get("href") else ""
                    raw_records.append(CollectorRawRecord(
                        record_type="product",
                        source_url=f"https://pkg.go.dev/{import_path}" if import_path else None,
                        content={
                            "import_path": import_path,
                            "name": name_el.get_text(strip=True) if name_el else "",
                            "synopsis": synopsis_el.get_text(strip=True)[:300] if synopsis_el else "",
                            "query": query,
                        },
                    ))

                logs.append(collector_log("collect_done", f"query={query!r} count={len(raw_records)}"))
        except ImportError:
            errors.append("beautifulsoup4 not installed")
            logs.append(collector_log("import_error", "beautifulsoup4 missing", "error"))
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("collect_failed", msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
