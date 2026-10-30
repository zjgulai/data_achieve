"""TikTok Shop verified-purchase review collection.

This module is the second real source in the pipeline.  It talks to the
TikHub TikTok Shop web endpoint ``fetch_product_reviews_v2``, stores every
raw response with a sha256, and writes one ledger row per request before any
parsing happens.  The ledger row uses the same shape as the Reddit collector,
so ``voc.canonical.occurrences_from_ledger`` can read it without a second
pipeline.

Identity noise is first-class: a listing can return reviews whose
``sku_specification`` belongs to another model (for example
``YB003 Oyster Pink`` inside a YB001 listing).  Those rows are written to a
quarantine file with a reason code and never become occurrence records of
the target product.

The module never guesses a missing field.  ``helpful_count`` is ``None``
because the provider response does not carry it; ``text_language`` is a
documented heuristic, not a provider field.

``rebuild_outputs`` re-derives the JSONL files and statistics from the saved
raw payloads without spending another API call.  Use it after changing the
normaliser:

    python3 -m voc.tiktok_shop --run run-20261029 --from-ledger
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIKHUB_BASE = "https://api.tikhub.io"
REVIEWS_PATH = "/api/v1/tiktok/shop/web/fetch_product_reviews_v2"
USER_INFO_PATH = "/api/v1/tikhub/user/get_user_info"

DEFAULT_PRODUCT_ID = "1729474995478630680"
DEFAULT_WINDOW_START = "2026-07-01T00:00:00+00:00"
DEFAULT_WINDOW_END = "2026-10-29T23:59:59+00:00"
DEFAULT_REGION = "US"
FRAME = "tiktok_shop_verified"

# The target listing is Momcozy Pregnancy Belly Band YB001 (CozySupport
# Ergonest).  YB003 is a different model that appears as a sibling SKU in
# the same review feed.
TARGET_MODEL_TERMS = ("yb001", "cozysupport", "ergonest")
QUARANTINE_MODEL_TERMS = ("yb003",)

EN_STOPWORDS = {
    "the", "i", "it", "and", "to", "my", "is", "was", "for", "this", "a",
    "of", "in", "with", "so", "very", "not", "but", "on", "me", "that",
    "have", "has", "be", "are", "you", "we", "they", "after", "when",
}
# Enough markers to separate a Spanish review from short English text like
# "Great belt" or "Didn't work".
OTHER_STOPWORDS = {
    "el", "la", "los", "las", "que", "por", "para", "con", "muy", "gustó",
    "gusta", "puedo", "bien", "vientre", "pero", "como", "una", "del", "al",
    "es", "son", "está", "este", "esta", "mis", "sus", "y", "en", "de",
    "não", "não", "muito", "très", "avec", "pour", "les", "des", "une",
}
NON_LATIN_RE = re.compile(r"[一-鿿぀-ヿ가-힯Ѐ-ӿ؀-ۿ]")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_api_key(explicit: str | None = None) -> str:
    """Resolve the key: explicit > repo ``apps/api/.env`` > process env.

    The repo file wins over ``os.environ`` on purpose.  This workspace keeps
    several TikHub tokens for different accounts; the research corpus is
    pinned to the ``reddit_voc`` token stored in ``apps/api/.env`` so cost
    before/after is measured against one balance.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    env_path = Path(__file__).resolve().parents[2] / "apps" / "api" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"^\s*TIKHUB_API_KEY\s*=\s*(.+)$", line)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value and not value.startswith("{{"):
                    return value
    key = (os.environ.get("TIKHUB_API_KEY") or "").strip()
    if key:
        return key
    raise RuntimeError("TIKHUB_API_KEY missing: set env or apps/api/.env")


@dataclass
class FetchResult:
    status: int
    payload: dict[str, Any] | None
    error: str | None


class TikHubFetcher:
    """Paced HTTP with bounded retries.

    ``min_interval`` keeps consecutive calls apart; 429 / 400 / 5xx / network
    errors back off exponentially.  TikHub does not charge failed requests,
    so a 400 is retried once before it is treated as a real parameter error.
    """

    def __init__(self, api_key: str, min_interval: float = 1.2, max_attempts: int = 3) -> None:
        self.api_key = api_key
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self._last = 0.0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "voc-pipeline/0.2 (research; TikTok Shop)",
        }

    def get_json(self, path: str, params: dict[str, Any]) -> FetchResult:
        url = f"{TIKHUB_BASE}{path}?{urllib.parse.urlencode(params)}"
        attempt = 0
        while attempt < self.max_attempts:
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            req = urllib.request.Request(url, headers=self._headers())
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = resp.read()
                    return FetchResult(resp.status, json.loads(body.decode("utf-8")), None)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:300]
                if exc.code in (400, 429, 500, 502, 503, 504) and attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(min(30, 3 * 2 ** (attempt - 1)))
                    continue
                return FetchResult(exc.code, None, body)
            except Exception as exc:  # network / timeout / decode
                if attempt + 1 < self.max_attempts:
                    attempt += 1
                    time.sleep(min(30, 3 * 2 ** (attempt - 1)))
                    continue
                return FetchResult(0, None, str(exc)[:300])
        return FetchResult(0, None, "exhausted")

    def balance(self) -> float | None:
        result = self.get_json(USER_INFO_PATH, {})
        if result.status != 200 or not isinstance(result.payload, dict):
            return None
        return (result.payload.get("user_data") or {}).get("balance")


def detect_language(text: str) -> str:
    """Heuristic language label for a review body.

    The provider returns no language field.  ``none`` means no text;
    ``non_en`` means a non-Latin script dominates or two or more markers of
    another Latin language outnumber English function words; everything else
    Latin-script is ``en``.  Short English fragments such as "Great belt" stay
    ``en``; the label is deliberately about script and stopwords, not fluency.
    """
    stripped = text.strip()
    if not stripped:
        return "none"
    latin = len(re.findall(r"[A-Za-z]", stripped))
    non_latin = len(NON_LATIN_RE.findall(stripped))
    if non_latin > latin:
        return "non_en"
    words = re.findall(r"[a-zà-ÿ']+", stripped.lower())
    other = sum(1 for word in words if word in OTHER_STOPWORDS)
    english = sum(1 for word in words if word in EN_STOPWORDS)
    if other >= 2 and other > english:
        return "non_en"
    return "en"


def identity_noise_reason(row: dict[str, Any], product_id: str) -> str | None:
    if str(row.get("product_id") or "") != str(product_id):
        return "product_id_mismatch"
    variant = str(row.get("sku_specification") or "")
    name = str(row.get("product_name") or "")
    haystack = f"{variant} {name}".lower()
    for term in QUARANTINE_MODEL_TERMS:
        if term in haystack:
            return f"sku_variant_mismatch:{variant.strip() or term}"
    if "oyster pink" in variant.lower() and "yb001" not in haystack:
        return f"sku_variant_mismatch:{variant.strip()}"
    return None


def _epoch_ms_to_iso(value: Any) -> str | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def _in_window(iso: str | None, start: str, end: str) -> bool:
    if not iso:
        return False
    try:
        moment = datetime.fromisoformat(iso)
        return datetime.fromisoformat(start) <= moment <= datetime.fromisoformat(end)
    except ValueError:
        return False


def normalize_review(
    raw: dict[str, Any],
    *,
    run_id: str,
    captured_at: str,
    product_id: str,
) -> dict[str, Any]:
    review_id = str(raw.get("review_id") or "")
    text = str(raw.get("review_text") or "")
    variant = str(raw.get("sku_specification") or "")
    reviewer = str(raw.get("reviewer_name") or "")
    return {
        "review_id": review_id,
        "product_id": str(raw.get("product_id") or ""),
        "sku_id": str(raw.get("sku_id") or ""),
        "variant": variant,
        "rating": raw.get("review_rating"),
        "text": text,
        "text_language": detect_language(text),
        "review_time": _epoch_ms_to_iso(raw.get("review_time")),
        "verified_purchase": raw.get("is_verified_purchase"),
        "incentivized": raw.get("is_incentivized_review"),
        "helpful_count": raw.get("helpful_count"),  # provider does not return it
        "region": str(raw.get("review_country") or ""),
        "run_id": run_id,
        "captured_at": captured_at,
        # Audit extras: not part of the required field list.
        "product_name": str(raw.get("product_name") or ""),
        "reviewer_masked": reviewer,
        "author_key": hashlib.sha256(reviewer.encode("utf-8")).hexdigest()[:16] if reviewer else "",
        "n_images": len(raw.get("review_images") or []),
        "quarantine_reason": identity_noise_reason(raw, product_id),
    }


@dataclass
class ReviewPage:
    page_start: int
    raw_id: str
    path: str
    sha256: str
    fetched_at: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    has_more: bool = False
    total_reviews: int | None = None
    status: str = "failed"
    error: str | None = None


def _extract_rows(payload: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    inner = (payload or {}).get("data") or {}
    data = inner.get("data") if isinstance(inner, dict) else None
    rows = data.get("product_reviews") if isinstance(data, dict) else None
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return rows, data if isinstance(data, dict) else None


def collect_reviews(
    run_dir: Path,
    *,
    product_id: str = DEFAULT_PRODUCT_ID,
    max_pages: int = 14,
    window_start: str = DEFAULT_WINDOW_START,
    window_end: str = DEFAULT_WINDOW_END,
    region: str = DEFAULT_REGION,
    budget_usd: float = 0.10,
    min_interval: float = 1.2,
    api_key: str | None = None,
    assumed_cost_per_call: float = 0.001,
) -> dict[str, Any]:
    """Fetch review pages and persist raw payloads + ledger + JSONL.

    Pages are fetched newest-first until one of: no more pages, the oldest
    review on a page predates ``window_start``, ``max_pages`` is reached, or
    the assumed spend would cross ``budget_usd``.
    """
    run_dir = run_dir if run_dir.is_absolute() else Path.cwd() / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    key = load_api_key(api_key)
    fetcher = TikHubFetcher(key, min_interval=min_interval)
    raw_dir = run_dir / "raw" / "tikhub"
    raw_dir.mkdir(parents=True, exist_ok=True)

    captured_at = _now()
    balance_before = fetcher.balance()
    pages: list[ReviewPage] = []
    spend = 0.0
    seq = 0
    stop_reason = "max_pages"

    for page_start in range(1, max_pages + 1):
        if spend + assumed_cost_per_call > budget_usd:
            stop_reason = "budget_guard"
            break
        params = {
            "product_id": product_id,
            "page_start": page_start,
            "sort_rule": 2,
            "filter_type": 1,
            "filter_value": 6,
            "region": region,
        }
        result = fetcher.get_json(REVIEWS_PATH, params)
        seq += 1
        payload_bytes = json.dumps(result.payload, ensure_ascii=False).encode("utf-8") if result.payload is not None else b"{}"
        request_id = f"{seq:03d}-{_sha256(json.dumps(params, sort_keys=True).encode())[:8]}"
        path = raw_dir / f"{request_id}.json"
        path.write_bytes(payload_bytes)
        spend += assumed_cost_per_call

        rows, data = _extract_rows(result.payload)
        page = ReviewPage(
            page_start=page_start,
            raw_id=f"raw-{request_id}",
            path=str(path),
            sha256=_sha256(payload_bytes),
            fetched_at=_now(),
            rows=rows,
            has_more=bool(data.get("has_more")) if data else False,
            total_reviews=(data.get("total_reviews") if data else None),
            status="success" if result.status == 200 and data is not None else "failed",
            error=result.error,
        )
        pages.append(page)
        if page.status != "success":
            stop_reason = f"http_{result.status}"
            break
        if not rows or not page.has_more:
            stop_reason = "no_more_pages"
            break
        oldest_iso = min((_epoch_ms_to_iso(r.get("review_time")) or "" for r in rows), default="")
        if oldest_iso and oldest_iso < window_start:
            stop_reason = "window_reached"
            break

    balance_after = fetcher.balance()
    measured = (
        round(balance_before - balance_after, 6)
        if balance_before is not None and balance_after is not None
        else None
    )
    ledger_rows = [
        {
            "raw_id": page.raw_id,
            "provider": "tikhub",
            "endpoint": "shop_reviews",
            "request_id": page.raw_id.removeprefix("raw-"),
            "request": {
                "frame": FRAME,
                "product_id": product_id,
                "page_start": page.page_start,
                "region": region,
                "sort_rule": 2,
                "filter_type": 1,
                "filter_value": 6,
            },
            "fetched_at": page.fetched_at,
            "path": page.path,
            "sha256": page.sha256,
            "record_count": len(page.rows),
            "total_reviews": page.total_reviews,
            "status": page.status,
            "error": page.error,
            "cost_usd": assumed_cost_per_call if page.status == "success" else 0.0,
        }
        for page in pages
    ]
    ledger = {
        "provider": "tikhub",
        "endpoint": "shop_reviews",
        "schema_version": "voc_tiktok_shop_ledger_v1",
        "generated_at": _now(),
        "product_id": product_id,
        "frame": FRAME,
        "window": {"start": window_start, "end": window_end, "timezone": "UTC"},
        "region": region,
        "captured_at": captured_at,
        "stop_reason": stop_reason,
        "cost": {
            "assumed_usd": round(spend, 6),
            "measured_usd": measured,
            "balance_before_usd": balance_before,
            "balance_after_usd": balance_after,
        },
        "rows": ledger_rows,
    }
    (run_dir / "tiktok-shop-ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    return rebuild_outputs(run_dir, window_start=window_start, window_end=window_end)


def rebuild_outputs(
    run_dir: Path,
    *,
    window_start: str = DEFAULT_WINDOW_START,
    window_end: str = DEFAULT_WINDOW_END,
) -> dict[str, Any]:
    """Re-derive JSONL files and statistics from saved raw payloads.

    No network call is made.  The ledger is the source of truth for which
    pages belong to the run; each raw file is re-parsed so normaliser changes
    are reproducible without paying for the same data twice.
    """
    run_dir = run_dir if run_dir.is_absolute() else Path.cwd() / run_dir
    run_id = run_dir.name
    ledger_path = run_dir / "tiktok-shop-ledger.json"
    ledger = json.loads(ledger_path.read_text())
    product_id = str(ledger.get("product_id") or DEFAULT_PRODUCT_ID)
    captured_at = ledger.get("captured_at") or _now()

    all_rows: list[dict[str, Any]] = []
    raw_objects = 0
    listing_totals: list[int] = []
    for row in ledger.get("rows", []):
        if row.get("status") != "success":
            continue
        payload = json.loads(Path(row["path"]).read_text())
        records, data = _extract_rows(payload)
        raw_objects += len(records)
        if isinstance(data, dict) and data.get("total_reviews"):
            listing_totals.append(int(data["total_reviews"]))
        for raw in records:
            normalized = normalize_review(raw, run_id=run_id, captured_at=captured_at, product_id=product_id)
            normalized["raw_page"] = (row.get("request") or {}).get("page_start")
            all_rows.append(normalized)

    dedup: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in all_rows:
        rid = row["review_id"]
        if not rid:
            continue
        if rid in dedup:
            duplicates += 1
            continue
        dedup[rid] = row
    unique_rows = list(dedup.values())

    accepted = [
        row
        for row in unique_rows
        if not row["quarantine_reason"] and _in_window(row["review_time"], window_start, window_end)
    ]
    quarantine = [row for row in unique_rows if row["quarantine_reason"]]
    out_of_window = [
        row
        for row in unique_rows
        if not row["quarantine_reason"] and not _in_window(row["review_time"], window_start, window_end)
    ]

    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    reviews_path = run_dir / "tiktok-shop-reviews.jsonl"
    quarantine_path = run_dir / "tiktok-shop-quarantine.jsonl"
    _write_jsonl(reviews_path, accepted)
    _write_jsonl(quarantine_path, quarantine)

    rating_counts: dict[str, int] = {}
    for row in accepted:
        rating_counts[str(row["rating"])] = rating_counts.get(str(row["rating"]), 0) + 1
    times = sorted(row["review_time"] for row in accepted if row["review_time"])
    by_month: dict[str, int] = {}
    for moment in times:
        by_month[moment[:7]] = by_month.get(moment[:7], 0) + 1
    with_text = [row for row in accepted if row["text"].strip()]
    codable = [row for row in with_text if row["text_language"] == "en"]
    reviewers = {row["reviewer_masked"] for row in accepted if row["reviewer_masked"]}

    ledger["summary"] = {
        "requests": len(ledger.get("rows", [])),
        "success": sum(1 for row in ledger.get("rows", []) if row.get("status") == "success"),
        "failed": sum(1 for row in ledger.get("rows", []) if row.get("status") != "success"),
        "raw_rows": raw_objects,
        "duplicate_review_ids_dropped": duplicates,
        "unique_reviews": len(unique_rows),
        "accepted_in_window": len(accepted),
        "quarantined": len(quarantine),
        "out_of_window": len(out_of_window),
        "cost_usd": round(sum(float(row.get("cost_usd") or 0) for row in ledger.get("rows", [])), 6),
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")

    stats = {
        "run_id": run_id,
        "product_id": product_id,
        "frame": FRAME,
        "pages_fetched": ledger["summary"]["requests"],
        "stop_reason": ledger.get("stop_reason"),
        "listing_total_reviews": max(listing_totals) if listing_totals else None,
        "raw_rows": raw_objects,
        "duplicate_review_ids": duplicates,
        "unique_reviews": len(unique_rows),
        "accepted_in_window": len(accepted),
        "quarantined": len(quarantine),
        "quarantine_records": quarantine,
        "out_of_window": len(out_of_window),
        "distinct_masked_reviewers": len(reviewers),
        "verified_purchase_true": sum(1 for row in accepted if row["verified_purchase"] is True),
        "incentivized_true": sum(1 for row in accepted if row["incentivized"] is True),
        "time_range": {"min": times[0] if times else None, "max": times[-1] if times else None},
        "time_by_month": dict(sorted(by_month.items())),
        "rating_counts": dict(sorted(rating_counts.items())),
        "text_bearing": len(with_text),
        "text_ge_30_chars": sum(1 for row in with_text if len(row["text"]) >= 30),
        "text_codable_en": len(codable),
        "language_counts": {
            lang: sum(1 for row in accepted if row["text_language"] == lang)
            for lang in sorted({row["text_language"] for row in accepted})
        },
        "cost": ledger.get("cost"),
        "files": {"reviews": str(reviews_path), "quarantine": str(quarantine_path)},
    }
    (run_dir / "tiktok-shop-collection-stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="voc.tiktok_shop")
    parser.add_argument("--run", default="run-20261029")
    parser.add_argument("--product-id", default=DEFAULT_PRODUCT_ID)
    parser.add_argument("--pages", type=int, default=14)
    parser.add_argument("--window-start", default=DEFAULT_WINDOW_START)
    parser.add_argument("--window-end", default=DEFAULT_WINDOW_END)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--budget-usd", type=float, default=0.10)
    parser.add_argument("--interval", type=float, default=1.2)
    parser.add_argument("--from-ledger", action="store_true")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "artifacts"))
    args = parser.parse_args(argv)
    run_dir = Path(args.out) / args.run
    if args.from_ledger:
        stats = rebuild_outputs(run_dir, window_start=args.window_start, window_end=args.window_end)
    else:
        stats = collect_reviews(
            run_dir,
            product_id=args.product_id,
            max_pages=args.pages,
            window_start=args.window_start,
            window_end=args.window_end,
            region=args.region,
            budget_usd=args.budget_usd,
            min_interval=args.interval,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())