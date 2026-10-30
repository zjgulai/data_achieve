"""Collection adapters.

Three real sources are implemented:

* Arctic Shift (public Reddit archive API) for posts and comments.
* Amazon product detail page for identity and variant evidence.
* TikTok Shop product reviews via TikHub, for verified-purchase direction.

Both write an immutable raw payload, a sha256, and a ledger row before any
parsing happens.  A request that fails is recorded as a failure, not retried
into silence.

The TikTok adapter lives in ``voc.tiktok_shop`` (its response shape and
identity-quarantine rules are provider-specific); this module exposes the
same ``run_*_collection`` entry point so the pipeline has one collector
surface.  Both ledgers feed the same ``canonical.occurrences_from_ledger``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARCTIC = "https://arctic-shift.photon-reddit.com/api"
UA = "voc-pipeline/0.1 (research; contact: local)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class RawObject:
    raw_id: str
    provider: str
    endpoint: str
    request_id: str
    request: dict[str, Any]
    fetched_at: str
    path: str
    sha256: str
    record_count: int
    status: str
    error: str | None = None
    cost_usd: float = 0.0


@dataclass
class Ledger:
    rows: list[RawObject] = field(default_factory=list)

    def add(self, obj: RawObject) -> None:
        self.rows.append(obj)

    def summary(self) -> dict[str, Any]:
        ok = [r for r in self.rows if r.status == "success"]
        return {
            "requests": len(self.rows),
            "success": len(ok),
            "failed": len(self.rows) - len(ok),
            "records": sum(r.record_count for r in ok),
            "zero_result_requests": sum(1 for r in ok if r.record_count == 0),
            "cost_usd": round(sum(r.cost_usd for r in self.rows), 6),
        }


class Fetcher:
    """HTTP with pacing and bounded backoff; never hides a failure."""

    def __init__(self, min_interval: float = 12.0, max_attempts: int = 4) -> None:
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self._last = 0.0

    def get_json(self, url: str) -> tuple[int, dict[str, Any] | None, str | None]:
        attempt = 0
        while attempt < self.max_attempts:
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read()
                    return resp.status, json.loads(body.decode("utf-8")), None
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                if exc.code in (422, 429, 503) and attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(min(90, 20 * attempt))
                    continue
                return exc.code, None, body[:300]
            except Exception as exc:  # network / timeout
                if attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(min(90, 15 * attempt))
                    continue
                return 0, None, str(exc)[:300]
        return 0, None, "exhausted"

    def get_text(self, url: str) -> tuple[int, bytes | None, str | None]:
        attempt = 0
        while attempt < self.max_attempts:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.status, resp.read(), None
            except urllib.error.HTTPError as exc:
                body = exc.read()
                if exc.code in (429, 503) and attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(10 * attempt)
                    continue
                return exc.code, body, f"HTTP {exc.code}"
            except Exception as exc:
                if attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(8 * attempt)
                    continue
                return 0, None, str(exc)[:300]
        return 0, None, "exhausted"


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def save(self, provider: str, endpoint: str, request: dict[str, Any], payload: bytes) -> tuple[str, str, str]:
        self._seq += 1
        request_id = f"{self._seq:03d}-{_sha256(json.dumps(request, sort_keys=True).encode())[:8]}"
        folder = self.root / provider
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{request_id}.json"
        path.write_bytes(payload)
        return request_id, str(path), _sha256(payload)


def arctic_posts(subreddit: str, query: str, limit: int = 25, before: int | None = None) -> str:
    params = {"subreddit": subreddit, "query": query, "limit": str(limit)}
    if before:
        params["before"] = str(before)
    return f"{ARCTIC}/posts/search?{urllib.parse.urlencode(params)}"


def arctic_comments(subreddit: str, body: str, limit: int = 25, before: int | None = None) -> str:
    params = {"subreddit": subreddit, "body": body, "limit": str(limit)}
    if before:
        params["before"] = str(before)
    return f"{ARCTIC}/comments/search?{urllib.parse.urlencode(params)}"


def run_reddit_collection(
    out_dir: Path,
    plan: list[dict[str, Any]],
    fetcher: Fetcher | None = None,
    ledger_name: str = "collection-run-ledger.json",
) -> dict[str, Any]:
    """Execute an approved request plan page by page.

    Each plan item: {frame, kind: posts|comments, subreddit, query, pages}.
    """
    fetcher = fetcher or Fetcher()
    store = RawStore(out_dir / "raw")
    ledger = Ledger()
    for item in plan:
        before = None
        for page in range(item.get("pages", 1)):
            url = (
                arctic_posts(item["subreddit"], item["query"], before=before)
                if item["kind"] == "posts"
                else arctic_comments(item["subreddit"], item["query"], before=before)
            )
            request = {"frame": item["frame"], "kind": item["kind"], "subreddit": item["subreddit"], "query": item["query"], "page": page}
            status, body, error = fetcher.get_json(url)
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else b"{}"
            request_id, path, digest = store.save("arcticshift", item["kind"], request, payload)
            records = body.get("data") if isinstance(body, dict) else None
            n = len(records) if isinstance(records, list) else 0
            ledger.add(
                RawObject(
                    raw_id=f"raw-{request_id}",
                    provider="arcticshift",
                    endpoint=item["kind"],
                    request_id=request_id,
                    request=request,
                    fetched_at=_now(),
                    path=path,
                    sha256=digest,
                    record_count=n,
                    status="success" if status == 200 and isinstance(records, list) else "failed",
                    error=error,
                )
            )
            if not isinstance(records, list) or not records:
                break
            oldest = min(int(r.get("created_utc") or 0) for r in records)
            if oldest <= 0:
                break
            before = oldest
    manifest = {
        "provider": "arcticshift",
        "generated_at": _now(),
        "summary": ledger.summary(),
        "rows": [r.__dict__ for r in ledger.rows],
    }
    (out_dir / ledger_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


def run_tiktok_collection(
    out_dir: Path,
    *,
    product_id: str | None = None,
    max_pages: int = 14,
    budget_usd: float = 0.10,
    min_interval: float = 1.2,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    """Adapter entry point for the TikTok Shop collector.

    Delegates to :mod:`voc.tiktok_shop`; the module boundary exists because
    the provider has its own response shape, quarantine rules and cost
    ledger, not because the data takes a different pipeline.
    """
    from . import tiktok_shop

    kwargs: dict[str, Any] = {
        "max_pages": max_pages,
        "budget_usd": budget_usd,
        "min_interval": min_interval,
    }
    if product_id:
        kwargs["product_id"] = product_id
    if window_start:
        kwargs["window_start"] = window_start
    if window_end:
        kwargs["window_end"] = window_end
    return tiktok_shop.collect_reviews(out_dir, **kwargs)


def parse_amazon_pdp(html: str) -> dict[str, Any]:
    """Parse identity facts from a saved Amazon product page.

    Only fields that are directly present in the HTML are returned.  Missing
    values stay missing; nothing is inferred from the category.
    """
    out: dict[str, Any] = {}
    m = re.search(r'id="productTitle"[^>]*>\s*([^<]+)', html)
    if m:
        out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'id="acrCustomerReviewText"[^>]*aria-label="([^"]+)"', html)
    if m:
        out["rating_count_text"] = m.group(1)
    m = re.search(r'rating-out-of-text[^>]*>\s*([0-9.]+) out of 5', html)
    if m:
        out["rating_value"] = float(m.group(1))
    m = re.search(r'"dimensionValuesDisplayData"\s*:\s*(\{.*?\})\s*,\s*"', html, re.S)
    if m:
        try:
            variants = json.loads(m.group(1))
            out["variants"] = variants
            out["variant_count"] = len(variants)
        except json.JSONDecodeError:
            out["variants"] = {}
    m = re.search(r'id="bylineInfo"[^>]*>\s*(?:Brand:\s*)?([^<]+)', html)
    if m:
        out["brand"] = re.sub(r"\s+", " ", m.group(1)).strip()
    for label, pat in {
        "price": r'id="corePrice_feature_div".*?<span class="a-offscreen">\$([0-9.,]+)',
        "availability": r'id="availability"[^>]*>.*?<span[^>]*>\s*([^<]+)',
    }.items():
        m = re.search(pat, html, re.S)
        if m:
            out[label] = m.group(1).strip()
    return out


def collect_amazon_identity(
    out_dir: Path,
    asins: list[str],
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    fetcher = fetcher or Fetcher(min_interval=1.0)
    store = RawStore(out_dir / "raw")
    ledger = Ledger()
    products: dict[str, Any] = {}
    for asin in asins:
        url = f"https://www.amazon.com/dp/{asin}"
        status, body, error = fetcher.get_text(url)
        payload = body or b""
        request_id, path, digest = store.save("amazon", "pdp", {"asin": asin}, payload)
        html = payload.decode("utf-8", "ignore") if payload else ""
        parsed = parse_amazon_pdp(html)
        products[asin] = parsed
        ledger.add(
            RawObject(
                raw_id=f"raw-{request_id}",
                provider="amazon",
                endpoint="pdp",
                request_id=request_id,
                request={"asin": asin},
                fetched_at=_now(),
                path=path,
                sha256=digest,
                record_count=1 if status == 200 and parsed else 0,
                status="success" if status == 200 and parsed else "failed",
                error=error,
            )
        )
    identity = {
        "provider": "amazon",
        "fetched_at": _now(),
        "asins": asins,
        "products": products,
        "ledger": {"summary": ledger.summary(), "rows": [r.__dict__ for r in ledger.rows]},
    }
    (out_dir / "amazon-identity-raw.json").write_text(json.dumps(identity, ensure_ascii=False, indent=1))
    return identity
