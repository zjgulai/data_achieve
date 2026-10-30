#!/usr/bin/env python3
"""Collect TikTok creator/video/snapshot data for the VOC pipeline.

This is a read-only research collector.  It writes every raw API payload
with a sha256, one ledger line per paid call, and derived indexes whose rows
carry provenance back to the endpoint, request and raw file.

It never invents a field.  Values that the provider does not return stay
absent or null and are listed as evidence gaps in the summary.

The creator-cookie endpoints are probed once only.  Both return
``{"code": 98001002, "message": "no login"}`` when
``TIKHUB_TIKTOK_CREATOR_COOKIE`` is unset, and TikHub still charges for the
failed call.  The collector therefore does not retry them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.tikhub.io"
USER_INFO_PATH = "/api/v1/tikhub/user/get_user_info"
SEARCH_PATH = "/api/v1/tiktok/app/v3/fetch_video_search_result"
DETAIL_PATH = "/api/v1/tiktok/web/fetch_post_detail"
PROFILE_PATH = "/api/v1/tiktok/web/fetch_user_profile"
RELATED_VIDEOS_PATH = "/api/v1/tiktok/creator/get_product_related_videos"
ASSOCIATED_PRODUCTS_PATH = "/api/v1/tiktok/creator/get_video_associated_product_list"

TARGET_PRODUCT_ID = "1729474995478630680"
TARGET_PRODUCT_NAME = "Momcozy Pregnancy Belly Band YB001 / CozySupport Ergonest"

# Keyword probes.  sort_type 0 = relevance, 1 = most liked.
SEARCH_QUERIES: list[tuple[str, int]] = [
    ("momcozy belly band", 0),
    ("momcozy belly band", 1),
    ("momcozy pregnancy", 0),
    ("momcozy", 1),
    ("pregnancy belly band", 0),
    ("maternity belly band", 0),
    ("maternity belly band", 1),
    ("belly band pregnancy", 0),
    ("cozysupport ergonest", 0),
    ("cozy support belly band", 0),
    ("momcozy belly band review", 0),
    ("belly band for pregnancy", 0),
]

DEFAULT_OUT = (
    Path(__file__).resolve().parents[1]
    / "voc_pipeline"
    / "artifacts"
    / "run-20261029"
    / "creator-video"
)

MAX_SEARCH_CALLS = 20
MAX_DETAIL_CALLS = 60
MAX_PROFILE_CALLS = 50
MAX_TOTAL_CALLS = 200
ASSUMED_COST_PER_CALL = 0.001
HARD_BUDGET_USD = 10.0
SOFT_BUDGET_USD = 2.0
MAX_MEASURED_COST_PER_CALL = 0.01  # stop if one call costs 10x the assumption
MAX_CONSECUTIVE_FAILURES = 3
MAX_FAILURE_RATE = 0.05

BRAND_TERMS = ("momcozy", "ergonest", "cozysupport", "cozy support", "cozy support")
CATEGORY_TERMS = (
    "belly band",
    "belly belt",
    "maternity band",
    "maternity belt",
    "pregnancy band",
    "pregnancy belt",
    "support band",
    "belly support",
    "pregnancy support",
)
# Stricter terms used to decide whether a non-target anchor still belongs to
# the belly-band category.  Generic "belly support" is excluded here because
# underwear and pillows also use it.
ANCHOR_CATEGORY_TERMS = (
    "belly band",
    "belly belt",
    "maternity band",
    "maternity belt",
    "pregnancy band",
    "pregnancy belt",
    "belly binder",
    "postpartum belly band",
    "postpartum belly binder",
    "maternity support band",
    "belly support band",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return text or "unknown"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def write_jsonl_append(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def epoch_to_iso(value: Any) -> str | None:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")


def pick(value: Any) -> Any:
    """Return a JSON-safe scalar, preserving null instead of guessing."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def find_estimated(node: Any) -> Any:
    """Return the first ``is_estimated`` value in the payload, else None.

    TikHub documents some counters as estimates.  The collector must not
    silently treat an estimate as a measurement, so the flag is copied from
    the payload when present and stays None when the provider omits it.
    """
    if isinstance(node, dict):
        if "is_estimated" in node:
            return node["is_estimated"]
        for value in node.values():
            found = find_estimated(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_estimated(value)
            if found is not None:
                return found
    return None


def walk_product_dicts(node: Any, out: list[dict[str, Any]]) -> None:
    """Recursively find product dicts inside anchors/anchors_extras.

    TikHub nests the useful payload in JSON strings with escaped quotes, so
    the walker parses any string that looks like JSON.  Duplicate product IDs
    are de-duplicated by the caller.
    """
    if isinstance(node, dict):
        if node.get("product_id") is not None or node.get("productId") is not None:
            out.append(node)
        for value in node.values():
            walk_product_dicts(value, out)
    elif isinstance(node, list):
        for value in node:
            walk_product_dicts(value, out)
    elif isinstance(node, str):
        text = node.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                walk_product_dicts(json.loads(text), out)
            except (json.JSONDecodeError, TypeError):
                return


def anchor_products(node: Any) -> list[dict[str, str]]:
    found: list[dict[str, Any]] = []
    walk_product_dicts(node, found)
    products: dict[str, dict[str, str]] = {}
    for item in found:
        pid = item.get("product_id")
        if pid is None:
            pid = item.get("productId")
        if pid is None:
            continue
        key = str(pid)
        title = item.get("title") or item.get("product_name") or item.get("name") or ""
        entry = products.setdefault(key, {"product_id": key, "title": ""})
        if title and not entry["title"]:
            entry["title"] = str(title)
    return list(products.values())


def product_ids(products: list[dict[str, str]]) -> list[str]:
    return sorted({p["product_id"] for p in products})


def classify(item: dict[str, Any], products: list[dict[str, str]]) -> dict[str, Any]:
    blob_parts = [str(item.get("desc") or "")]
    for tag in item.get("text_extra") or []:
        if isinstance(tag, dict):
            blob_parts.append(str(tag.get("hashtag_name") or ""))
    for product in products:
        blob_parts.append(product.get("title") or "")
    blob = " ".join(blob_parts).lower()
    brand_hit = any(term in blob for term in BRAND_TERMS)
    category_hit = any(term in blob for term in CATEGORY_TERMS)
    pids = product_ids(products)
    anchor_titles = " ".join(str(product.get("title") or "") for product in products).lower()
    anchor_category_hit = bool(products) and any(
        term in anchor_titles for term in ANCHOR_CATEGORY_TERMS
    )
    if TARGET_PRODUCT_ID in pids:
        tier = "exact_target_product"
        confidence = "high"
        baseline_product = True
        baseline_category = True
    elif pids and anchor_category_hit:
        tier = "exact_other_product_category"
        confidence = "high_for_that_product_id"
        baseline_product = False
        baseline_category = True
    elif pids:
        tier = "exact_other_product_unrelated"
        confidence = "high_for_that_product_id"
        baseline_product = False
        baseline_category = False
    elif brand_hit and category_hit:
        tier = "text_match_brand_and_category"
        confidence = "medium_low"
        baseline_product = False
        baseline_category = False
    elif category_hit:
        tier = "text_match_category_only"
        confidence = "low"
        baseline_product = False
        baseline_category = False
    elif brand_hit:
        tier = "text_match_brand_only"
        confidence = "low"
        baseline_product = False
        baseline_category = False
    else:
        tier = "none"
        confidence = "none"
        baseline_product = False
        baseline_category = False
    return {
        "brand_hit": brand_hit,
        "category_hit": category_hit,
        "anchor_category_hit": anchor_category_hit,
        "anchor_product_ids": pids,
        "association_tier": tier,
        "association_confidence": confidence,
        "baseline_eligible_product": baseline_product,
        "baseline_eligible_category": baseline_category,
        "derived": True,
        "derivation": "keyword/anchor text scan; not a provider field",
    }


def relevance_rank(entry: dict[str, Any]) -> tuple[int, int]:
    tier = entry["classification"]["association_tier"]
    order = {
        "exact_target_product": 0,
        "exact_other_product_category": 1,
        "exact_other_product_unrelated": 2,
        "exact_other_product": 1,
        "text_match_brand_and_category": 3,
        "text_match_category_only": 4,
        "text_match_brand_only": 5,
        "none": 6,
    }
    stats = entry.get("search_statistics") or {}
    plays = stats.get("play_count")
    try:
        play_rank = -int(plays) if plays is not None else 0
    except (TypeError, ValueError):
        play_rank = 0
    return (order.get(tier, 5), play_rank)


class Fetcher:
    def __init__(self, api_key: str, min_interval: float = 0.7, max_attempts: int = 3) -> None:
        self.api_key = api_key
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self._last = 0.0

    def _wait(self) -> None:
        delay = self.min_interval - (time.monotonic() - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        url = f"{BASE}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "voc-pipeline/0.3 (research; creator-video)",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        attempts = 0
        last_error = ""
        while attempts < self.max_attempts:
            self._wait()
            attempts += 1
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                    payload = json.loads(raw.decode("utf-8"))
                    return {
                        "http_status": resp.status,
                        "payload": payload,
                        "raw": raw,
                        "error": None,
                        "attempts": attempts,
                    }
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                text = raw.decode("utf-8", "replace")
                if exc.code in (429, 500, 502, 503, 504) and attempts < self.max_attempts:
                    time.sleep(min(30, 2 * 2 ** (attempts - 1)))
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = None
                return {
                    "http_status": exc.code,
                    "payload": payload,
                    "raw": raw,
                    "error": text[:500],
                    "attempts": attempts,
                }
            except Exception as exc:  # network / timeout / decode
                last_error = str(exc)[:500]
                if attempts < self.max_attempts:
                    time.sleep(min(30, 2 * 2 ** (attempts - 1)))
                    continue
                return {
                    "http_status": 0,
                    "payload": None,
                    "raw": b"{}",
                    "error": last_error,
                    "attempts": attempts,
                }
        return {
            "http_status": 0,
            "payload": None,
            "raw": b"{}",
            "error": last_error or "exhausted",
            "attempts": attempts,
        }

    def balance(self) -> float | None:
        result = self.request("GET", USER_INFO_PATH)
        payload = result.get("payload")
        if result["http_status"] != 200 or not isinstance(payload, dict):
            return None
        value = (payload.get("user_data") or {}).get("balance")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def provider_status(result: dict[str, Any]) -> tuple[str, int | None, str | None]:
    """Separate the HTTP envelope from TikHub's inner provider code."""
    if result["http_status"] != 200:
        return "http_error", None, f"http_{result['http_status']}"
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return "provider_error", None, "non_json_payload"
    data = payload.get("data")
    if isinstance(data, dict) and data.get("code") not in (None, 200):
        return "provider_error", int(data.get("code")), str(data.get("message") or "")[:200]
    if isinstance(data, dict) and data.get("statusCode") not in (None, 0, 200):
        return "provider_error", int(data.get("statusCode")), str(data.get("statusMsg") or "")[:200]
    detail = payload.get("detail")
    if isinstance(detail, dict) and detail.get("code") not in (None, 200):
        return "provider_error", int(detail.get("code")), str(detail.get("message") or "")[:200]
    if payload.get("code") not in (None, 200):
        return "provider_error", int(payload.get("code")), str(payload.get("message") or "")[:200]
    return "success", None, None


class BudgetStop(RuntimeError):
    pass


class Collector:
    def __init__(
        self,
        out_dir: Path,
        *,
        session_start_balance: float | None,
        min_interval: float,
        resume: bool,
    ) -> None:
        self.out_dir = out_dir
        self.raw_dir = out_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = out_dir / "collect-log.jsonl"
        self.fetcher = Fetcher(load_api_key(), min_interval=min_interval)
        self.session_start_balance = session_start_balance
        self.resume = resume
        self.calls: list[dict[str, Any]] = []
        self.searches: list[dict[str, Any]] = []
        self.videos: dict[str, dict[str, Any]] = {}
        self.details: dict[str, dict[str, Any]] = {}
        self.profiles: dict[str, dict[str, Any]] = {}
        self.assumed_cost = 0.0
        self.measured_cost = 0.0
        self.consecutive_failures = 0
        self.stop_reason: str | None = None
        self.blocked_endpoints: list[dict[str, Any]] = []

    # -- logging ---------------------------------------------------------
    def log(self, row: dict[str, Any]) -> None:
        write_jsonl_append(self.log_path, row)

    def log_progress(self, row: dict[str, Any]) -> None:
        row = {"ts": utc_now(), "event": "page_saved", **row}
        self.log(row)

    # -- paid call wrapper ----------------------------------------------
    def call(
        self,
        *,
        phase: str,
        endpoint_type: str,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        raw_path: Path,
        record_count: int = 0,
        note: str | None = None,
        allow_resume: bool = True,
    ) -> dict[str, Any]:
        if self.stop_reason:
            raise BudgetStop(self.stop_reason)

        if self.resume and allow_resume and raw_path.exists() and raw_path.stat().st_size > 2:
            try:
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                result = {
                    "http_status": 200,
                    "payload": payload,
                    "raw": raw_path.read_bytes(),
                    "error": None,
                    "attempts": 0,
                }
                status, provider_code, provider_message = provider_status(result)
                row = {
                    "ts": utc_now(),
                    "event": "resumed_from_raw",
                    "phase": phase,
                    "endpoint": path,
                    "endpoint_type": endpoint_type,
                    "request_params_sha256": sha256_bytes(
                        json.dumps(params or body or {}, sort_keys=True).encode("utf-8")
                    ),
                    "request_id": (payload or {}).get("request_id") if isinstance(payload, dict) else None,
                    "http_status": 200,
                    "provider_code": provider_code,
                    "status": status,
                    "record_count": record_count,
                    "cost_measured_usd": 0.0,
                    "cost_assumed_usd": 0.0,
                    "raw_file": str(raw_path),
                    "raw_sha256": sha256_bytes(result["raw"]),
                    "note": "resumed; no API call made",
                }
                self.log(row)
                self.calls.append(row)
                return result
            except (json.JSONDecodeError, OSError):
                pass

        if len(self.calls) >= MAX_TOTAL_CALLS:
            self.stop_reason = "max_total_calls"
            raise BudgetStop(self.stop_reason)
        if self.assumed_cost + ASSUMED_COST_PER_CALL > HARD_BUDGET_USD:
            self.stop_reason = "hard_budget"
            raise BudgetStop(self.stop_reason)
        if self.assumed_cost + ASSUMED_COST_PER_CALL > SOFT_BUDGET_USD:
            self.stop_reason = "soft_budget"
            raise BudgetStop(self.stop_reason)

        balance_before = self.fetcher.balance()
        result = self.fetcher.request(method, path, params=params, body=body)
        balance_after = self.fetcher.balance()
        measured = None
        if balance_before is not None and balance_after is not None:
            measured = round(balance_before - balance_after, 6)

        status, provider_code, provider_message = provider_status(result)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(result["raw"])
        raw_sha = sha256_bytes(result["raw"])
        self.assumed_cost += ASSUMED_COST_PER_CALL
        if measured is not None:
            self.measured_cost += measured

        row = {
            "ts": utc_now(),
            "event": "page_saved",
            "phase": phase,
            "endpoint": path,
            "endpoint_type": endpoint_type,
            "request_params_sha256": sha256_bytes(
                json.dumps(params or body or {}, sort_keys=True).encode("utf-8")
            ),
            "request_params": {
                key: value
                for key, value in (params or body or {}).items()
                if key.lower() not in {"cookie", "authorization", "api_key"}
            },
            "request_id": (result.get("payload") or {}).get("request_id") if isinstance(result.get("payload"), dict) else None,
            "http_status": result["http_status"],
            "provider_code": provider_code,
            "provider_message": provider_message,
            "status": status,
            "attempts": result["attempts"],
            "record_count": record_count,
            "balance_before_usd": balance_before,
            "balance_after_usd": balance_after,
            "cost_measured_usd": measured,
            "cost_assumed_usd": ASSUMED_COST_PER_CALL,
            "raw_file": str(raw_path),
            "raw_sha256": raw_sha,
            "note": note,
        }
        self.log(row)
        self.calls.append(row)

        if status == "success":
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                self.stop_reason = "consecutive_failures"
                raise BudgetStop(self.stop_reason)
        failed = sum(1 for call in self.calls if call.get("status") != "success")
        if len(self.calls) >= 20 and failed / len(self.calls) > MAX_FAILURE_RATE:
            self.stop_reason = "failure_rate"
            raise BudgetStop(self.stop_reason)
        if measured is not None and measured > MAX_MEASURED_COST_PER_CALL:
            self.stop_reason = "unexpected_cost"
            raise BudgetStop(self.stop_reason)
        return result

    # -- phases ----------------------------------------------------------
    def preflight(self) -> None:
        balance = self.fetcher.balance()
        self.log(
            {
                "ts": utc_now(),
                "event": "preflight",
                "balance_usd": balance,
                "session_start_balance_usd": self.session_start_balance,
                "creator_cookie_present": bool(os.getenv("TIKHUB_TIKTOK_CREATOR_COOKIE", "").strip()),
                "note": "balance query is not billed; creator cookie is absent, so creator-cookie endpoints are probed once and not retried",
            }
        )

    def collect_search(self) -> None:
        for index, (keyword, sort_type) in enumerate(SEARCH_QUERIES, start=1):
            if index > MAX_SEARCH_CALLS:
                break
            params = {
                "keyword": keyword,
                "count": 20,
                "cursor": 0,
                "sort_type": sort_type,
                "region": "US",
                "publish_time": 90,
            }
            raw_path = self.raw_dir / f"video-search-{slug(keyword)}-sort{sort_type}-page1.json"
            try:
                result = self.call(
                    phase="search",
                    endpoint_type="tikhub_tiktok_video_search",
                    method="GET",
                    path=SEARCH_PATH,
                    params=params,
                    body=None,
                    raw_path=raw_path,
                    record_count=0,
                    note=f"keyword={keyword!r}; sort_type={sort_type}",
                )
            except BudgetStop:
                break
            payload = result.get("payload") or {}
            data = payload.get("data") if isinstance(payload, dict) else None
            items = data.get("search_item_list") if isinstance(data, dict) else None
            rows = []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        aweme = item.get("aweme_info")
                        if isinstance(aweme, dict) and aweme:
                            rows.append(aweme)
            self.calls[-1]["record_count"] = len(rows)
            search_captured_at = utc_now()
            self.searches.append(
                {
                    "keyword": keyword,
                    "sort_type": sort_type,
                    "raw_file": str(raw_path),
                    "request_id": (payload or {}).get("request_id"),
                    "has_more": data.get("has_more") if isinstance(data, dict) else None,
                    "cursor": data.get("cursor") if isinstance(data, dict) else None,
                    "items": len(rows),
                    "fetched_at": search_captured_at,
                }
            )
            self.log_progress(
                {
                    "phase": "search",
                    "raw_file": str(raw_path),
                    "record_count": len(rows),
                    "cumulative_calls": len(self.calls),
                    "cumulative_assumed_cost_usd": round(self.assumed_cost, 6),
                }
            )
            for aweme in rows:
                self.ingest_search_item(aweme, keyword, sort_type, raw_path, search_captured_at)

    def ingest_search_item(
        self,
        aweme: dict[str, Any],
        keyword: str,
        sort_type: int,
        raw_path: Path,
        captured_at: str,
    ) -> None:
        video_id = str(aweme.get("aweme_id") or aweme.get("id") or "")
        if not video_id:
            return
        author = aweme.get("author") if isinstance(aweme.get("author"), dict) else {}
        stats = aweme.get("statistics") if isinstance(aweme.get("statistics"), dict) else {}
        products = anchor_products(aweme.get("anchors"))
        products += anchor_products(aweme.get("anchors_extras"))
        dedup_products: dict[str, dict[str, str]] = {}
        for product in products:
            dedup_products.setdefault(product["product_id"], product)
        products = list(dedup_products.values())
        classification = classify(aweme, products)
        stat_map = {
            "play_count": stats.get("play_count"),
            "like_count": stats.get("digg_count"),
            "comment_count": stats.get("comment_count"),
            "share_count": stats.get("share_count"),
            "collect_count": stats.get("collect_count"),
            "repost_count": stats.get("repost_count"),
            "download_count": stats.get("download_count"),
            "whatsapp_share_count": stats.get("whatsapp_share_count"),
        }
        entry = self.videos.get(video_id)
        if entry is None:
            entry = {
                "video_id": video_id,
                "desc": aweme.get("desc"),
                "create_time": aweme.get("create_time"),
                "create_time_iso": epoch_to_iso(aweme.get("create_time")),
                "author": {
                    "user_id": str(author.get("uid") or ""),
                    "sec_uid": author.get("sec_uid"),
                    "unique_id": author.get("unique_id"),
                    "nickname": author.get("nickname"),
                    "follower_count": author.get("follower_count"),
                    "following_count": author.get("following_count"),
                    "aweme_count": author.get("aweme_count"),
                    "total_favorited": author.get("total_favorited"),
                },
                "search_statistics": stat_map,
                "search_captured_at": captured_at,
                "search_is_estimated": find_estimated(aweme),
                "duration_seconds": (aweme.get("video") or {}).get("duration"),
                "anchor_products": products,
                "classification": classification,
                "first_seen_keyword": keyword,
                "first_seen_sort_type": sort_type,
                "search_provenance": [
                    {
                        "keyword": keyword,
                        "sort_type": sort_type,
                        "endpoint": SEARCH_PATH,
                        "raw_file": str(raw_path),
                    }
                ],
            }
            self.videos[video_id] = entry
        else:
            entry["search_provenance"].append(
                {
                    "keyword": keyword,
                    "sort_type": sort_type,
                    "endpoint": SEARCH_PATH,
                    "raw_file": str(raw_path),
                }
            )
            # Keep the newest non-null search snapshot: later calls overwrite
            # only when they carry a value, never with a fabricated one.
            for key, value in stat_map.items():
                if value is not None:
                    entry["search_statistics"][key] = value
            entry["search_captured_at"] = captured_at
            entry["search_is_estimated"] = find_estimated(aweme)
            if not entry["anchor_products"] and products:
                entry["anchor_products"] = products
                entry["classification"] = classification
            elif products:
                existing = {p["product_id"] for p in entry["anchor_products"]}
                for product in products:
                    if product["product_id"] not in existing:
                        entry["anchor_products"].append(product)
                entry["classification"] = classify(aweme, entry["anchor_products"])

    def collect_details(self) -> None:
        ranked = sorted(
            self.videos.values(),
            key=lambda entry: relevance_rank(entry),
        )
        selected = [entry for entry in ranked if entry["classification"]["association_tier"] != "none"]
        selected = selected[:MAX_DETAIL_CALLS]
        self.log(
            {
                "ts": utc_now(),
                "event": "selection",
                "phase": "detail",
                "unique_videos_seen": len(self.videos),
                "relevant_videos": sum(
                    1 for entry in self.videos.values() if entry["classification"]["association_tier"] != "none"
                ),
                "selected_for_detail": len(selected),
                "max_detail_calls": MAX_DETAIL_CALLS,
                "note": "exact anchor matches first, then text matches by search play_count",
            }
        )
        for entry in selected:
            video_id = entry["video_id"]
            raw_path = self.raw_dir / f"fetch-post-detail-{video_id}.json"
            try:
                result = self.call(
                    phase="detail",
                    endpoint_type="tikhub_tiktok_video_detail",
                    method="GET",
                    path=DETAIL_PATH,
                    params={"itemId": video_id, "region": "US"},
                    body=None,
                    raw_path=raw_path,
                    record_count=0,
                    note=f"video_id={video_id}",
                )
            except BudgetStop:
                break
            payload = result.get("payload") or {}
            data = payload.get("data") if isinstance(payload, dict) else None
            item_info = data.get("itemInfo") if isinstance(data, dict) else None
            item = item_info.get("itemStruct") if isinstance(item_info, dict) else None
            if not isinstance(item, dict):
                self.calls[-1]["record_count"] = 0
                continue
            detail = normalize_detail(item, video_id, raw_path)
            self.details[video_id] = detail
            self.calls[-1]["record_count"] = 1
            self.log_progress(
                {
                    "phase": "detail",
                    "raw_file": str(raw_path),
                    "record_count": 1,
                    "cumulative_calls": len(self.calls),
                    "cumulative_assumed_cost_usd": round(self.assumed_cost, 6),
                }
            )

    def collect_profiles(self) -> None:
        authors: dict[str, dict[str, Any]] = {}
        for detail in self.details.values():
            author = detail.get("author") or {}
            key = author.get("sec_uid") or author.get("unique_id") or author.get("user_id")
            if not key:
                continue
            authors.setdefault(str(key), author)
        selected = list(authors.values())[:MAX_PROFILE_CALLS]
        self.log(
            {
                "ts": utc_now(),
                "event": "selection",
                "phase": "profile",
                "unique_authors": len(authors),
                "selected_for_profile": len(selected),
                "max_profile_calls": MAX_PROFILE_CALLS,
            }
        )
        for author in selected:
            unique_id = author.get("unique_id")
            sec_uid = author.get("sec_uid")
            key = unique_id or sec_uid or author.get("user_id")
            if not key:
                continue
            params: dict[str, Any] = {}
            if unique_id:
                params["uniqueId"] = unique_id
            if sec_uid:
                params["secUid"] = sec_uid
            raw_path = self.raw_dir / f"fetch-user-profile-{slug(str(key))}.json"
            try:
                result = self.call(
                    phase="profile",
                    endpoint_type="tikhub_tiktok_user_profile_web",
                    method="GET",
                    path=PROFILE_PATH,
                    params=params,
                    body=None,
                    raw_path=raw_path,
                    record_count=0,
                    note=f"creator_key={key}",
                )
            except BudgetStop:
                break
            payload = result.get("payload") or {}
            data = payload.get("data") if isinstance(payload, dict) else None
            user_info = data.get("userInfo") if isinstance(data, dict) else None
            if not isinstance(user_info, dict):
                self.calls[-1]["record_count"] = 0
                continue
            profile = normalize_profile(user_info, raw_path)
            self.profiles[str(key)] = profile
            self.calls[-1]["record_count"] = 1
            self.log_progress(
                {
                    "phase": "profile",
                    "raw_file": str(raw_path),
                    "record_count": 1,
                    "cumulative_calls": len(self.calls),
                    "cumulative_assumed_cost_usd": round(self.assumed_cost, 6),
                }
            )

    def probe_creator_cookie_endpoints(self, anchor_video_ids: list[str]) -> None:
        """Probe the two product-video endpoints once.  They cost money and
        return ``no login`` without the cookie, so this is deliberately a
        one-shot diagnostic rather than a retry loop.
        """
        if not anchor_video_ids:
            return
        probes = [
            (
                RELATED_VIDEOS_PATH,
                "tikhub_tiktok_product_related_videos",
                {
                    "item_id": anchor_video_ids[0],
                    "product_id": TARGET_PRODUCT_ID,
                    "start_date": "10-01-2026",
                },
                "get_product_related_videos",
            ),
            (
                ASSOCIATED_PRODUCTS_PATH,
                "tikhub_tiktok_video_products",
                {
                    "item_ids": anchor_video_ids[:20],
                    "start_date": "10-01-2026",
                },
                "get_video_associated_product_list",
            ),
        ]
        for path, endpoint_type, body, label in probes:
            raw_path = self.raw_dir / f"{slug(label)}-no-cookie-probe.json"
            try:
                result = self.call(
                    phase="blocked_probe",
                    endpoint_type=endpoint_type,
                    method="POST",
                    path=path,
                    params=None,
                    body=body,
                    raw_path=raw_path,
                    record_count=0,
                    note="creator cookie absent; expected provider code 98001002 no login; not retried",
                    allow_resume=False,
                )
            except BudgetStop:
                break
            payload = result.get("payload") or {}
            data = payload.get("data") if isinstance(payload, dict) else None
            inner_code = data.get("code") if isinstance(data, dict) else None
            inner_message = data.get("message") if isinstance(data, dict) else None
            self.blocked_endpoints.append(
                {
                    "endpoint": path,
                    "endpoint_type": endpoint_type,
                    "label": label,
                    "http_status": result.get("http_status"),
                    "provider_code": inner_code,
                    "provider_message": inner_message,
                    "raw_file": str(raw_path),
                    "paid": True,
                    "reason": "TIKHUB_TIKTOK_CREATOR_COOKIE absent",
                }
            )


def normalize_detail(item: dict[str, Any], video_id: str, raw_path: Path) -> dict[str, Any]:
    stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
    stats_v2 = item.get("statsV2") if isinstance(item.get("statsV2"), dict) else {}
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    products = anchor_products(item.get("anchors"))
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    stats_map = {
        "play_count": stats.get("playCount"),
        "like_count": stats.get("diggCount"),
        "comment_count": stats.get("commentCount"),
        "share_count": stats.get("shareCount"),
        "collect_count": stats.get("collectCount"),
        "repost_count": stats.get("repostCount"),
    }
    stats_v2_map = {
        "play_count": stats_v2.get("playCount"),
        "like_count": stats_v2.get("diggCount"),
        "comment_count": stats_v2.get("commentCount"),
        "share_count": stats_v2.get("shareCount"),
        "collect_count": stats_v2.get("collectCount"),
        "repost_count": stats_v2.get("repostCount"),
    }
    return {
        "video_id": video_id,
        "item_id": item.get("id"),
        "desc": item.get("desc"),
        "create_time": item.get("createTime"),
        "create_time_iso": epoch_to_iso(item.get("createTime")),
        "duration_seconds": video.get("duration"),
        "video_width": video.get("width"),
        "video_height": video.get("height"),
        "author": {
            "user_id": str(author.get("id") or ""),
            "sec_uid": author.get("secUid"),
            "unique_id": author.get("uniqueId"),
            "nickname": author.get("nickname"),
            "signature": author.get("signature"),
            "verified": author.get("verified"),
            "private_account": author.get("privateAccount"),
            "follower_count": author.get("followerCount"),
            "video_count": author.get("videoCount"),
            "heart_count": author.get("heartCount"),
        },
        "statistics": stats_map,
        "statistics_v2": stats_v2_map,
        "is_estimated": find_estimated(item),
        "is_estimated_field_present": find_estimated(item) is not None,
        "is_ad": item.get("isAd"),
        "is_ec_video": item.get("isECVideo"),
        "anchors": item.get("anchors"),
        "anchor_products": products,
        "has_shop_product": bool(products) or bool(item.get("anchors")),
        "text_language": item.get("textLanguage"),
        "source_endpoint": DETAIL_PATH,
        "raw_file": str(raw_path),
        "captured_at": utc_now(),
    }


def normalize_profile(user_info: dict[str, Any], raw_path: Path) -> dict[str, Any]:
    user = user_info.get("user") if isinstance(user_info.get("user"), dict) else {}
    stats = user_info.get("stats") if isinstance(user_info.get("stats"), dict) else {}
    return {
        "user_id": str(user.get("id") or ""),
        "unique_id": user.get("uniqueId"),
        "nickname": user.get("nickname"),
        "sec_uid": user.get("secUid"),
        "signature": user.get("signature"),
        "verified": user.get("verified"),
        "private_account": user.get("privateAccount"),
        "tt_seller": user.get("ttSeller"),
        "region": user.get("region"),
        "language": user.get("language"),
        "commerce_user_info": user.get("commerceUserInfo"),
        "follower_count": stats.get("followerCount"),
        "following_count": stats.get("followingCount"),
        "heart_count": stats.get("heartCount"),
        "video_count": stats.get("videoCount"),
        "friend_count": stats.get("friendCount"),
        "source_endpoint": PROFILE_PATH,
        "raw_file": str(raw_path),
        "captured_at": utc_now(),
    }


def build_snapshot_rows(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for video_id, entry in videos.items():
        detail = details.get(video_id)
        search_stats = entry.get("search_statistics") or {}
        row: dict[str, Any] = {
            "video_id": video_id,
            "desc": entry.get("desc"),
            "create_time_iso": entry.get("create_time_iso"),
            "association_tier": entry["classification"]["association_tier"],
            "anchor_product_ids": entry["classification"]["anchor_product_ids"],
            "search_snapshot": {
                "source_endpoint": SEARCH_PATH,
                "captured_at": entry.get("search_captured_at"),
                "statistics": search_stats,
                "is_estimated": entry.get("search_is_estimated"),
            },
            "detail_snapshot": None,
            "snapshot_source": "search_only",
            "is_estimated": entry.get("search_is_estimated"),
            "is_estimated_field_present": entry.get("search_is_estimated") is not None,
            "derived_engagement": None,
        }
        if detail:
            detail_stats = detail.get("statistics") or {}
            row["detail_snapshot"] = {
                "source_endpoint": DETAIL_PATH,
                "captured_at": detail.get("captured_at"),
                "statistics": detail_stats,
            }
            row["snapshot_source"] = "fetch_post_detail"
            row["is_estimated"] = detail.get("is_estimated")
            row["is_estimated_field_present"] = detail.get("is_estimated_field_present", False)
            row["author"] = {
                key: detail["author"].get(key)
                for key in ("user_id", "unique_id", "nickname", "sec_uid")
            }
            delta = {}
            for key, value in detail_stats.items():
                base = search_stats.get(key)
                if isinstance(value, (int, float)) and isinstance(base, (int, float)):
                    delta[key] = value - base
            row["delta_detail_minus_search"] = delta
            plays = detail_stats.get("play_count")
            interactions = sum(
                value
                for value in (
                    detail_stats.get("like_count"),
                    detail_stats.get("comment_count"),
                    detail_stats.get("share_count"),
                    detail_stats.get("collect_count"),
                )
                if isinstance(value, (int, float))
            )
            if isinstance(plays, (int, float)) and plays > 0:
                row["derived_engagement"] = {
                    "interactions": interactions,
                    "play_count": plays,
                    "interaction_rate": round(interactions / plays, 6),
                    "derived": True,
                    "formula": "(like+comment+share+collect)/play_count",
                }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row["association_tier"] != "exact_target_product",
            -(row.get("derived_engagement") or {}).get("interaction_rate", -1),
        )
    )
    return rows


def build_product_video_index(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target = [
        entry
        for entry in videos.values()
        if TARGET_PRODUCT_ID in entry["classification"]["anchor_product_ids"]
    ]
    other = [
        entry
        for entry in videos.values()
        if entry["classification"]["association_tier"]
        in {"exact_other_product_category", "exact_other_product_unrelated", "exact_other_product"}
    ]
    other_category = [
        entry
        for entry in other
        if entry["classification"]["association_tier"] == "exact_other_product_category"
    ]
    unrelated = [
        entry
        for entry in other
        if entry["classification"]["association_tier"] == "exact_other_product_unrelated"
    ]
    target.sort(key=lambda entry: -int((entry.get("search_statistics") or {}).get("play_count") or 0))
    rows = []
    for entry in target:
        detail = details.get(entry["video_id"])
        rows.append(
            {
                "video_id": entry["video_id"],
                "desc": entry.get("desc"),
                "create_time_iso": entry.get("create_time_iso"),
                "author": entry.get("author"),
                "anchor_product_ids": entry["classification"]["anchor_product_ids"],
                "anchor_products": entry.get("anchor_products"),
                "association": {
                    "method": "anchor_product_id",
                    "confidence": "exact_id",
                    "product_id": TARGET_PRODUCT_ID,
                    "baseline_eligible_product": True,
                },
                "search_statistics": entry.get("search_statistics"),
                "detail_statistics": (detail or {}).get("statistics"),
                "evidence": {
                    "search_endpoint": SEARCH_PATH,
                    "search_provenance": entry.get("search_provenance"),
                    "detail_raw_file": (detail or {}).get("raw_file"),
                },
            }
        )
    return {
        "_meta": {
            "derived": True,
            "not_a_provider_endpoint_response": True,
            "product_id": TARGET_PRODUCT_ID,
            "product_name": TARGET_PRODUCT_NAME,
            "generated_at": utc_now(),
            "association_basis": "anchor_product_id from TikTok aweme anchors",
            "confidence": "exact_id",
            "is_exhaustive": False,
            "coverage_note": (
                "TikHub has no product_id-only video-list endpoint. "
                "get_product_related_videos and get_video_associated_product_list "
                "both return provider code 98001002 no login without "
                "TIKHUB_TIKTOK_CREATOR_COOKIE. This file is the anchor-verified "
                "subset found by keyword search, not a complete product video list."
            ),
            "pagination_note": (
                "fetch_video_search_result returned has_more=1 but cursor=20 "
                "returned the same 12 items as cursor=0; pagination is not usable. "
                "Coverage was widened with multiple keywords and sort_type values."
            ),
            "video_count": len(rows),
            "other_product_anchor_video_count": len(other),
            "other_category_anchor_video_count": len(other_category),
            "unrelated_anchor_video_count": len(unrelated),
        },
        "videos": rows,
        "other_category_anchor_videos": [
            {
                "video_id": entry["video_id"],
                "desc": entry.get("desc"),
                "anchor_product_ids": entry["classification"]["anchor_product_ids"],
                "anchor_products": entry.get("anchor_products"),
                "association": {
                    "method": "anchor_product_id",
                    "confidence": "exact_id_other_product",
                    "baseline_eligible_product": False,
                    "baseline_eligible_category": True,
                },
            }
            for entry in other_category
        ],
        "unrelated_anchor_videos": [
            {
                "video_id": entry["video_id"],
                "desc": entry.get("desc"),
                "anchor_product_ids": entry["classification"]["anchor_product_ids"],
                "anchor_products": entry.get("anchor_products"),
                "association": {
                    "method": "anchor_product_id",
                    "confidence": "exact_id_other_product",
                    "baseline_eligible_product": False,
                    "baseline_eligible_category": False,
                },
            }
            for entry in unrelated
        ],
        "other_product_anchor_videos": [
            {
                "video_id": entry["video_id"],
                "desc": entry.get("desc"),
                "anchor_product_ids": entry["classification"]["anchor_product_ids"],
                "anchor_products": entry.get("anchor_products"),
                "association": {
                    "method": "anchor_product_id",
                    "confidence": "exact_id_other_product",
                    "baseline_eligible_product": False,
                    "baseline_eligible_category": entry["classification"]["baseline_eligible_category"],
                },
            }
            for entry in other
        ],
    }


def summarize(
    collector: Collector,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    calls = collector.calls
    by_endpoint: dict[str, dict[str, int]] = {}
    for call in calls:
        key = call.get("endpoint_type") or "unknown"
        bucket = by_endpoint.setdefault(key, {"calls": 0, "success": 0, "failed": 0})
        bucket["calls"] += 1
        if call.get("status") == "success":
            bucket["success"] += 1
        else:
            bucket["failed"] += 1

    videos_with_detail = sum(1 for row in snapshots if row["snapshot_source"] == "fetch_post_detail")
    target_videos = [
        entry for entry in collector.videos.values()
        if TARGET_PRODUCT_ID in entry["classification"]["anchor_product_ids"]
    ]
    other_videos = [
        entry for entry in collector.videos.values()
        if entry["classification"]["association_tier"]
        in {"exact_other_product_category", "exact_other_product_unrelated", "exact_other_product"}
    ]
    other_category_videos = [
        entry for entry in collector.videos.values()
        if entry["classification"]["association_tier"] == "exact_other_product_category"
    ]
    other_unrelated_videos = [
        entry for entry in collector.videos.values()
        if entry["classification"]["association_tier"] == "exact_other_product_unrelated"
    ]
    relevant_videos = [
        entry for entry in collector.videos.values()
        if entry["classification"]["association_tier"] != "none"
    ]
    measured_total = None
    if collector.session_start_balance is not None:
        latest = None
        for call in reversed(calls):
            if call.get("balance_after_usd") is not None:
                latest = call["balance_after_usd"]
                break
        if latest is not None:
            measured_total = round(collector.session_start_balance - latest, 6)

    missing_fields = [
        "product_id -> video list endpoint: not available without TIKHUB_TIKTOK_CREATOR_COOKIE (provider code 98001002 no login)",
        "get_product_related_videos play_count: endpoint does not return play_count; per-video fetch_post_detail is required",
        "product review -> video link: no video_id/aweme_id/item_id in 175 canonical reviews or 180 raw reviews; 0% joinable",
        "video GMV / orders / conversion: only available to the logged-in creator via get_video_to_product_stats; not available for third-party videos",
        "creator audience demographics (gender/age/region): only available to the logged-in creator via get_video_audience_stats",
        "video captions/transcripts: TikHub has no subtitle endpoint; only Apify",
        "18 SKU count and 22,140 sales: not present in current review raw; needs a product-detail source",
        "exhaustive product video list: keyword search pagination is broken (cursor repeats page 1), so the product video index is a sample",
        "creator follower_count in fetch_post_detail: null; fetch_user_profile is required",
    ]
    return {
        "schema_version": "voc_creator_video_collection_summary_v1",
        "generated_at": utc_now(),
        "target": {
            "product_id": TARGET_PRODUCT_ID,
            "product_name": TARGET_PRODUCT_NAME,
            "region": "US",
        },
        "calls": {
            "total": len(calls),
            "success": sum(1 for call in calls if call.get("status") == "success"),
            "failed": sum(1 for call in calls if call.get("status") != "success"),
            "by_endpoint": by_endpoint,
        },
        "counts": {
            "search_queries": len(collector.searches),
            "unique_videos_seen": len(collector.videos),
            "relevant_videos": len(relevant_videos),
            "exact_target_product_videos": len(target_videos),
            "exact_other_product_videos": len(other_videos),
            "exact_other_product_category_videos": len(other_category_videos),
            "exact_other_product_unrelated_videos": len(other_unrelated_videos),
            "videos_with_detail": len(collector.details),
            "unique_creators_from_details": len(
                {
                    (detail.get("author") or {}).get("sec_uid")
                    or (detail.get("author") or {}).get("unique_id")
                    for detail in collector.details.values()
                    if (detail.get("author") or {}).get("sec_uid")
                    or (detail.get("author") or {}).get("unique_id")
                }
            ),
            "creators_with_profile": len(collector.profiles),
            "videos_with_snapshot": videos_with_detail,
            "videos_with_derived_engagement": sum(
                1 for row in snapshots if row.get("derived_engagement") is not None
            ),
        },
        "cost": {
            "session_start_balance_usd": collector.session_start_balance,
            "collection_assumed_usd": round(collector.assumed_cost, 6),
            "collection_measured_usd": round(collector.measured_cost, 6),
            "session_total_measured_usd": measured_total,
            "assumption": "0.001 USD per paid call; measured is the sum of per-call balance deltas and may be 0 when the balance display lags",
            "hard_budget_usd": HARD_BUDGET_USD,
            "soft_budget_usd": SOFT_BUDGET_USD,
            "pre_collection_probe_calls": 7,
            "pre_collection_probe_cost_measured_usd": 0.007,
            "pre_collection_probe_note": "balance 37.446 -> 37.439 after 5 shape probes and 2 no-cookie endpoint probes",
        },
        "stop_reason": collector.stop_reason or "completed",
        "blocked_endpoints": collector.blocked_endpoints,
        "evidence_gaps": missing_fields,
        "search_pagination": {
            "has_more_field": "present",
            "cursor_behavior": "cursor=20 returned the same items as cursor=0 for 'momcozy belly band'",
            "conclusion": "pagination not usable; multiple keywords/sort orders were used instead",
        },
        "files": {
            "collect_log": str(collector.log_path),
            "raw_dir": str(collector.raw_dir),
        },
    }


def load_api_key() -> str:
    env_path = Path(__file__).resolve().parents[1] / "apps" / "api" / ".env"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creator_video_collect")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--session-start-balance", type=float, default=37.446)
    parser.add_argument("--interval", type=float, default=0.7)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    collector = Collector(
        out_dir,
        session_start_balance=args.session_start_balance,
        min_interval=args.interval,
        resume=not args.no_resume,
    )
    collector.preflight()
    try:
        collector.collect_search()
    except BudgetStop as exc:
        collector.stop_reason = collector.stop_reason or str(exc)
    try:
        collector.collect_details()
    except BudgetStop as exc:
        collector.stop_reason = collector.stop_reason or str(exc)
    try:
        collector.collect_profiles()
    except BudgetStop as exc:
        collector.stop_reason = collector.stop_reason or str(exc)

    target_anchor_ids = [
        entry["video_id"]
        for entry in collector.videos.values()
        if TARGET_PRODUCT_ID in entry["classification"]["anchor_product_ids"]
    ]
    try:
        collector.probe_creator_cookie_endpoints(target_anchor_ids)
    except BudgetStop as exc:
        collector.stop_reason = collector.stop_reason or str(exc)

    snapshots = build_snapshot_rows(collector.videos, collector.details)
    product_index = build_product_video_index(collector.videos, collector.details)

    write_json(out_dir / "raw" / "video-details.json", {
        "_meta": {
            "derived": True,
            "source_endpoint": DETAIL_PATH,
            "captured_at": utc_now(),
            "note": "normalized rows; raw per-video payloads are fetch-post-detail-<video_id>.json",
        },
        "videos": list(collector.details.values()),
    })
    write_json(out_dir / "raw" / "creators.json", {
        "_meta": {
            "derived": True,
            "source_endpoint": PROFILE_PATH,
            "captured_at": utc_now(),
            "note": "normalized rows; raw per-creator payloads are fetch-user-profile-<key>.json",
        },
        "creators": list(collector.profiles.values()),
    })
    write_json(out_dir / "raw" / "video-snapshots.json", {
        "_meta": {
            "derived": True,
            "captured_at": utc_now(),
            "note": "search and detail statistics captured at different times; delta is detail minus search",
            "is_estimated": None,
        },
        "videos": snapshots,
    })
    write_json(out_dir / "raw" / "product-videos-page-1.json", product_index)

    summary = summarize(collector, snapshots)
    summary["files"].update(
        {
            "video_details": str(out_dir / "raw" / "video-details.json"),
            "creators": str(out_dir / "raw" / "creators.json"),
            "video_snapshots": str(out_dir / "raw" / "video-snapshots.json"),
            "product_videos": str(out_dir / "raw" / "product-videos-page-1.json"),
        }
    )
    write_json(out_dir / "collect-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
