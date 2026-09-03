"""Robin-style dark web OSINT collector — searches .onion search engines via Tor.

Implements the same search logic as the Robin project (github.com/apurvsinghgautam/robin)
as a proper async collector, without the Streamlit UI layer.

Requires:
  - Tor daemon running on 127.0.0.1:9050 (socks5h)
  - pip install httpx[socks] beautifulsoup4

Environment variables (all optional):
    TOR_PROXY_URL        Tor SOCKS5 proxy (default: socks5://127.0.0.1:9050)
    DARKWEB_TIMEOUT      Per-engine request timeout in seconds (default: 40)
    DARKWEB_MAX_ENGINES  Max engines to query in parallel (default: 8)
"""
from __future__ import annotations

import asyncio
import random
import re
from datetime import UTC, datetime
from typing import Any
import os

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)

_TOR_PROXY = os.environ.get("TOR_PROXY_URL", "socks5://127.0.0.1:9050")
_TIMEOUT = float(os.environ.get("DARKWEB_TIMEOUT", "40"))
_MAX_ENGINES = int(os.environ.get("DARKWEB_MAX_ENGINES", "8"))

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
]

_ONION_ENGINES = [
    "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",
    "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",
    "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",
    "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",
    "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}",
    "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",
    "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",
    "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",
]


async def _fetch_engine(url: str, timeout: float) -> list[dict[str, str]]:
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    headers = {"User-Agent": random.choice(_USER_AGENTS)}
    try:
        async with httpx.AsyncClient(
            proxy=_TOR_PROXY,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            r = await client.get(url, headers=headers)
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            seen: set[str] = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(strip=True)
                onion_links = re.findall(r"https?://[a-z0-9.]+\.onion[^\s\"'<>]*", href)
                for link in onion_links:
                    clean = link.rstrip("/")
                    if "search" not in clean and len(title) > 3 and clean not in seen:
                        seen.add(clean)
                        results.append({"title": title, "url": link})
            return results
    except Exception:
        return []


async def _search_darkweb(query: str, max_results: int) -> list[dict[str, str]]:
    engines = _ONION_ENGINES[:_MAX_ENGINES]
    urls = [e.format(query=query.replace(" ", "+")) for e in engines]
    tasks = [_fetch_engine(url, _TIMEOUT) for url in urls]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for batch in raw:
        if isinstance(batch, list):
            for item in batch:
                clean = item["url"].rstrip("/")
                if clean not in seen:
                    seen.add(clean)
                    results.append(item)
                    if len(results) >= max_results:
                        return results
    return results


def _tor_available() -> bool:
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", 9050), timeout=2)
        s.close()
        return True
    except OSError:
        return False


class _RobinBase(BaseCollector):
    async def test(self) -> CollectorTestResult:
        if not _tor_available():
            msg = "Tor not running on 127.0.0.1:9050 — install tor and start the daemon"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("robin_test_failed", msg, level="error")],
            )
        try:
            import httpx  # noqa: F401
            from bs4 import BeautifulSoup  # noqa: F401
        except ImportError:
            msg = "Missing deps — run: pip install 'httpx[socks]' beautifulsoup4"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("robin_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message="Tor reachable, deps present",
            logs=[collector_log("robin_test_ok", "tor:9050 up")],
        )

    def _to_records(
        self, results: list[dict[str, str]], query: str, query_type: str, collected_at: datetime
    ) -> list[CollectorRawRecord]:
        records = []
        for item in results:
            records.append(CollectorRawRecord(
                record_type="osint_report",
                source_url=item.get("url", ""),
                content={
                    "query": query,
                    "query_type": query_type,
                    "title": item.get("title"),
                    "onion_url": item.get("url"),
                },
                collected_at=collected_at,
            ))
        return records


class RobinKeywordCollector(_RobinBase):
    """Search dark web search engines for a keyword via Tor."""

    collector_type = "robin_darkweb_search"

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_results = int(self.config.get("max_results", 20))
        return {"keyword": keyword, "max_results": min(max_results, 100)}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        keyword: str = config["keyword"]
        max_results: int = config["max_results"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        try:
            results = await _search_darkweb(keyword, max_results)
        except Exception as exc:
            msg = f"darkweb_search_error: {exc}"
            errors.append(msg)
            logs.append(collector_log("robin_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(collector_log("robin_search_done", f"keyword={keyword!r} hits={len(results)}"))
        return CollectionResult(
            raw_records=self._to_records(results, keyword, "keyword", collected_at),
            logs=logs, errors=errors,
        )


class RobinUsernameCollector(_RobinBase):
    """Search dark web for a username — leaked creds, forum posts, market listings."""

    collector_type = "robin_darkweb_username"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        max_results = int(self.config.get("max_results", 20))
        return {"username": username, "max_results": min(max_results, 100)}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username: str = config["username"]
        max_results: int = config["max_results"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        query = f'"{username}" site:onion OR leak OR breach OR dump'
        try:
            results = await _search_darkweb(query, max_results)
        except Exception as exc:
            msg = f"darkweb_username_error: {exc}"
            errors.append(msg)
            logs.append(collector_log("robin_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(collector_log("robin_username_done", f"username={username!r} hits={len(results)}"))
        return CollectionResult(
            raw_records=self._to_records(results, username, "username", collected_at),
            logs=logs, errors=errors,
        )


class RobinEmailCollector(_RobinBase):
    """Search dark web for an email address in leaked credential dumps."""

    collector_type = "robin_darkweb_email"

    def validate_config(self) -> dict[str, Any]:
        email = require_text(self.config, "email")
        max_results = int(self.config.get("max_results", 20))
        return {"email": email, "max_results": min(max_results, 100)}

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        email: str = config["email"]
        max_results: int = config["max_results"]
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        query = f'"{email}" leak OR breach OR dump OR credential'
        try:
            results = await _search_darkweb(query, max_results)
        except Exception as exc:
            msg = f"darkweb_email_error: {exc}"
            errors.append(msg)
            logs.append(collector_log("robin_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        logs.append(collector_log("robin_email_done", f"email={email!r} hits={len(results)}"))
        return CollectionResult(
            raw_records=self._to_records(results, email, "email", collected_at),
            logs=logs, errors=errors,
        )
