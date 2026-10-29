"""Apify Actor collector.

Runs any Apify Actor asynchronously, polls for completion, and fetches
Dataset items.  Requires APIFY_API_TOKEN environment variable.

collector_type = "apify_actor"
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
    require_text,
)
from data_intelligence_hub.collectors.empty_result_policy import (
    empty_result_error,
    resolve_empty_result_policy,
)
from data_intelligence_hub.collectors.outbound_policy import assert_collector_allowed

APIFY_BASE_URL = "https://api.apify.com/v2"
APIFY_TIMEOUT = 30.0
# 服务层默认预算（collector_service.DEFAULT_COLLECTION_TIMEOUT_SECONDS = 660s）
# 必须大于本值。否则外层 asyncio.wait_for 先取消 collect()，
# 调用方只拿到 collection_timeout，拿不到这里的 apify_run_timeout。
APIFY_RUN_WAIT_TIMEOUT = 600.0   # seconds
APIFY_POLL_INTERVAL = 5.0        # seconds between status polls
APIFY_MAX_ITEMS_LIMIT = 1000

# 计费上限（USD）。它**不是**限流开关：按事件计费的 Actor 一旦累计花费触顶会直接
# ABORTED，而不是少返回几条（2026-10-09 实测 eBay scraper：0.3 -> ABORTED，1.0 -> 5 条）。
# 要限流请用入参里的数量字段。3.0 足够覆盖 10 条量级的抓取并留出余量。
DEFAULT_MAX_TOTAL_CHARGE_USD = 3.0

APIFY_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"})


def _apply_empty_result_policy(
    collector: BaseCollector,
    collected_records: int,
    errors: list[str],
    logs: list[dict[str, Any]],
    endpoint_type: str | None = None,
) -> None:
    """Turn a strict zero-record run into a structured error.

    A permissive policy leaves the result untouched: the service emits the
    `empty` warning log so the two layers never log the same event twice.
    """
    if collected_records > 0:
        return
    policy = resolve_empty_result_policy(
        collector_type=collector.collector_type,
        config=collector.config,
        collector_class=type(collector),
        task_config=collector.config,
    )
    if policy.allow_empty:
        return
    message = empty_result_error(
        collector_type=collector.collector_type,
        endpoint_type=endpoint_type,
        expected_records=policy.effective_min_expected_records,
    )
    errors.append(message)
    log = collector_log("collector_empty_result", message, level="error")
    log.update(
        {
            "collector_type": collector.collector_type,
            "endpoint_type": endpoint_type,
            "allow_empty": policy.allow_empty,
            "min_expected_records": policy.min_expected_records,
            "collected_records": collected_records,
            "enforced": True,
        }
    )
    logs.append(log)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _get_api_token() -> str:
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise CollectorError("apify_token_missing: APIFY_API_TOKEN env var not set")
    return token


def _apify_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _apify_json(resp: httpx.Response, context: str) -> Any:
    """Parse a JSON body and distinguish an empty body from an unknown shape."""
    try:
        return resp.json()
    except ValueError as exc:
        if not resp.text.strip():
            raise CollectorError(
                f"apify_upstream_empty: upstream returned an empty body ({context})"
            ) from exc
        raise CollectorError(
            f"apify_response_invalid_json: upstream response is not valid JSON ({context})"
        ) from exc


async def _apify_post(
    client: httpx.AsyncClient,
    path: str,
    json_body: dict[str, Any],
    params: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    resp = await client.post(
        f"{APIFY_BASE_URL}{path}",
        json=json_body,
        params=params,
        headers=_apify_headers(token),
        timeout=APIFY_TIMEOUT,
        follow_redirects=False,
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return cast(dict[str, Any], _apify_json(resp, f"path={path}"))


async def _apify_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
    token: str,
) -> Any:
    resp = await client.get(
        f"{APIFY_BASE_URL}{path}",
        params=params,
        headers=_apify_headers(token),
        timeout=APIFY_TIMEOUT,
        follow_redirects=False,
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return _apify_json(resp, f"path={path}")


async def _wait_for_run(
    client: httpx.AsyncClient,
    run_id: str,
    token: str,
    timeout: float,
) -> dict[str, Any]:
    """Poll until the Actor Run reaches a terminal status."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while True:
        resp = await _apify_get(client, f"/actor-runs/{run_id}", {}, token)
        run_data: dict[str, Any] = resp.get("data") or {}
        status = str(run_data.get("status") or "")
        if status in APIFY_TERMINAL_STATUSES:
            return run_data
        if loop.time() >= deadline:
            raise CollectorError(
                f"apify_run_timeout: run {run_id!r} did not finish within {timeout:.0f}s"
            )
        await asyncio.sleep(APIFY_POLL_INTERVAL)


def _dict_items(items: list[Any], dataset_id: str) -> list[dict[str, Any]]:
    """Keep object items; any other item type means the shape is unknown."""
    result = [item for item in items if isinstance(item, dict)]
    if len(result) != len(items):
        raise CollectorError(
            "apify_dataset_response_shape_unknown: expected dataset items to be "
            f"JSON objects, got {len(items) - len(result)} non-object item(s) "
            f"(dataset_id={dataset_id!r})"
        )
    return result


def _dataset_items_from_response(
    response: Any,
    dataset_id: str,
) -> list[dict[str, Any]]:
    """Validate the dataset payload shape.

    A valid empty array is a real empty result. Any other shape is a contract
    error and must not be mistaken for an empty dataset.
    """
    if isinstance(response, list):
        return _dict_items(response, dataset_id)
    if isinstance(response, dict):
        if "data" not in response:
            keys = ", ".join(sorted(str(key) for key in response))
            raise CollectorError(
                "apify_dataset_response_shape_unknown: response object has no 'data' "
                f"field (dataset_id={dataset_id!r}, keys=[{keys}])"
            )
        data = response["data"]
        if data is None:
            raise CollectorError(
                "apify_dataset_upstream_empty: response 'data' is null "
                f"(dataset_id={dataset_id!r})"
            )
        if isinstance(data, list):
            return _dict_items(data, dataset_id)
        raise CollectorError(
            "apify_dataset_response_shape_unknown: expected 'data' to be a list, "
            f"got {type(data).__name__} (dataset_id={dataset_id!r})"
        )
    if response is None:
        raise CollectorError(
            "apify_dataset_upstream_empty: upstream returned JSON null "
            f"(dataset_id={dataset_id!r})"
        )
    raise CollectorError(
        "apify_dataset_response_shape_unknown: expected a JSON array or an object "
        f"with 'data', got {type(response).__name__} (dataset_id={dataset_id!r})"
    )


async def _fetch_dataset_items(
    client: httpx.AsyncClient,
    dataset_id: str,
    limit: int,
    token: str,
) -> list[dict[str, Any]]:
    """Read items from an Apify Dataset."""
    resp = await _apify_get(
        client,
        f"/datasets/{dataset_id}/items",
        {"format": "json", "clean": "1", "limit": str(min(limit, APIFY_MAX_ITEMS_LIMIT))},
        token,
    )
    return _dataset_items_from_response(resp, dataset_id)


# ---------------------------------------------------------------------------
# Actor ID / path helpers
# ---------------------------------------------------------------------------


def _actor_id_to_path(actor_id: str) -> str:
    """'username/name' → 'username~name' for URL."""
    return actor_id.replace("/", "~")


# ---------------------------------------------------------------------------
# Platform / record-type inference
# ---------------------------------------------------------------------------


def _infer_platform(actor_id: str) -> str:
    lower = actor_id.lower()
    for platform in (
        "instagram", "tiktok", "youtube", "reddit", "facebook",
        "amazon", "trustpilot", "linkedin", "twitter", "threads",
        "bluesky", "shopify", "walmart", "ebay", "tripadvisor",
        "pinterest", "google", "temu", "shein", "aliexpress",
        "telegram", "crunchbase", "glassdoor", "perplexity", "gemini",
        "snapchat", "yelp", "booking", "airbnb", "etsy", "indeed",
        "hacker-news", "hackernews",
    ):
        if platform in lower:
            return platform
    return "web"


def _infer_record_type(actor_id: str) -> str:
    lower = actor_id.lower()
    if "instagram" in lower:
        return "instagram_profile" if "profile" in lower else "instagram_post"
    if "tiktok" in lower:
        if "shop" in lower:
            return "tiktok_shop_product"
        if "comment" in lower:
            return "tiktok_comment"
        if "ads" in lower or "ad-" in lower:
            return "tiktok_ad"
        return "tiktok_profile" if "profile" in lower else "tiktok_video"
    if "youtube" in lower:
        return "youtube_comment" if "comment" in lower else "youtube_video"
    if "reddit" in lower:
        return "reddit_post"
    if "facebook" in lower:
        if "ads" in lower:
            return "facebook_ad"
        return "facebook_comment" if "comment" in lower else "facebook_post"
    if "amazon" in lower:
        return "amazon_review" if "review" in lower else "amazon_product"
    if "walmart" in lower:
        return "walmart_review" if "review" in lower else "walmart_product"
    if "trustpilot" in lower or "tripadvisor" in lower or "glassdoor" in lower or "yelp" in lower:
        return "review"
    if "appstore" in lower or "apple-app" in lower or "app-store" in lower:
        return "appstore_review"
    if "google-play" in lower or "play-store" in lower:
        return "google_play_review"
    if "linkedin" in lower:
        return "linkedin_post"
    if "twitter" in lower or "tweet" in lower:
        return "twitter_post"
    if "threads" in lower:
        return "threads_post"
    if "pinterest" in lower:
        return "pinterest_pin"
    if "bluesky" in lower:
        return "bluesky_post"
    if "telegram" in lower:
        return "telegram_message"
    if "google" in lower:
        if "news" in lower:
            return "news_article"
        if "trend" in lower:
            return "google_trends_data"
        if "ads" in lower or "ad-" in lower:
            return "google_ad"
        return "google_search_result"
    ecommerce_platforms = ("temu", "shein", "aliexpress", "ebay", "etsy")
    if any(p in lower for p in ecommerce_platforms):
        return "ecommerce_product"
    if "crunchbase" in lower:
        return "company_profile"
    if "product-hunt" in lower or "producthunt" in lower:
        return "product_launch"
    if "hacker-news" in lower or "hackernews" in lower:
        return "news_article"
    if "indeed" in lower:
        return "job_posting"
    if "booking" in lower or "airbnb" in lower:
        return "travel_listing"
    if "perplexity" in lower or "chatgpt" in lower or "gemini" in lower:
        return "ai_search_result"
    if "web-scraper" in lower or "website-content" in lower or "rag-web" in lower:
        return "web_content"
    return "social_post"


def _extract_source_url(item: dict[str, Any]) -> str | None:
    for key in (
        "url", "postUrl", "videoUrl", "productUrl", "reviewUrl",
        "facebookUrl", "profileUrl", "webVideoUrl", "pageUrl",
    ):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def _extract_text(item: dict[str, Any]) -> str:
    for key in (
        "text", "caption", "description", "title", "body", "content",
        "reviewText", "comment", "postText", "commentText",
    ):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:2000]
    return ""


# ---------------------------------------------------------------------------
# Public normalizer
# ---------------------------------------------------------------------------


def normalize_apify_item(
    item: dict[str, Any],
    actor_id: str,
    record_type: str | None = None,
) -> CollectorRawRecord | None:
    """Normalize an Apify Dataset item into a CollectorRawRecord.

    Returns None if the item is empty or not a dict.
    """
    if not isinstance(item, dict) or not item:
        return None

    platform = _infer_platform(actor_id)
    rt = record_type or _infer_record_type(actor_id)
    source_url = _extract_source_url(item)
    text = _extract_text(item)

    return CollectorRawRecord(
        record_type=rt,
        source_url=source_url,
        content={
            "provider": "apify",
            "platform": platform,
            "actor_id": actor_id,
            "schema_version": f"apify_{rt}.v1",
            "text": text,
            "raw": item,
        },
        collected_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Collector class
# ---------------------------------------------------------------------------


class ApifyActorCollector(BaseCollector):
    """Apify Actor collector.

    Required config keys:
        actor_id:     Actor identifier, e.g. 'apify/instagram-scraper'
        actor_input:  dict passed as Actor input JSON

    Optional config keys:
        max_items:              int   (default 20, max 1000)
        run_timeout_seconds:    int   (default 600)
        max_total_charge_usd:   float (default 3.0)
        record_type:            str   override inferred record_type
    """

    collector_type = "apify_actor"

    # 合法 actor_id 只允许 Apify Store 的 owner/name 形态：段内取字母数字._-，
    # 两段都必须非空且不以点开头；URL、路径穿越、query/fragment 一律拒绝。
    _ACTOR_ID_RE = re.compile(
        r"^(?!\.)(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._-]*/(?!\.)[A-Za-z0-9][A-Za-z0-9._-]*$"
    )

    def validate_config(self) -> dict[str, Any]:
        assert_collector_allowed(self.collector_type)
        actor_id = require_text(self.config, "actor_id")
        if not self._ACTOR_ID_RE.fullmatch(actor_id):
            raise CollectorError(
                f"apify_actor_id_invalid: expected 'username/name', got {actor_id!r}"
            )
        actor_input = self.config.get("actor_input")
        if not isinstance(actor_input, dict):
            raise CollectorError("apify_actor_input_missing: 'actor_input' must be a dict")

        max_items_raw = self.config.get("max_items")
        max_items = min(
            int(max_items_raw) if isinstance(max_items_raw, (int, str)) else 20,
            APIFY_MAX_ITEMS_LIMIT,
        )
        timeout_raw = self.config.get("run_timeout_seconds")
        run_timeout = (
            float(timeout_raw)
            if isinstance(timeout_raw, (int, float, str))
            else APIFY_RUN_WAIT_TIMEOUT
        )
        charge_raw = self.config.get("max_total_charge_usd")
        max_charge = (
            float(charge_raw)
            if isinstance(charge_raw, (int, float, str))
            else DEFAULT_MAX_TOTAL_CHARGE_USD
        )

        return {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": max_items,
            "run_timeout_seconds": run_timeout,
            "max_total_charge_usd": max_charge,
            "record_type": self.config.get("record_type"),
        }

    async def test(self) -> CollectorTestResult:
        assert_collector_allowed(self.collector_type)
        logs: list[dict[str, Any]] = []
        try:
            token = _get_api_token()
        except CollectorError as exc:
            msg = f"Apify token test failed: {exc}"
            logs.append(collector_log("apify_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)
        try:
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                resp = await _apify_get(client, "/users/me", {}, token)
            username = (
                (resp.get("data") or {}).get("username", "unknown")
                if isinstance(resp, dict)
                else "unknown"
            )
            msg = f"Apify token valid; user={username!r}"
            logs.append(collector_log("apify_test", msg))
            return CollectorTestResult(status="ok", message=msg, logs=logs)
        except CollectorError as exc:
            msg = f"Apify token test failed: {exc}"
            logs.append(collector_log("apify_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()

        actor_id: str = config["actor_id"]
        actor_input: dict[str, Any] = config["actor_input"]
        max_items: int = config["max_items"]
        run_timeout: float = config["run_timeout_seconds"]
        max_charge: float = config["max_total_charge_usd"]
        record_type: str | None = config["record_type"]
        endpoint_type_raw = self.config.get("endpoint_type")
        endpoint_type = str(endpoint_type_raw) if endpoint_type_raw else None

        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        raw_records: list[CollectorRawRecord] = []

        try:
            token = _get_api_token()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("apify_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        actor_path = _actor_id_to_path(actor_id)
        logs.append(
            collector_log(
                "apify_run_start",
                f"actor={actor_id}, max_items={max_items}, max_charge=${max_charge:.2f}",
            )
        )

        try:
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                # 1. Start the Actor Run
                run_resp = await _apify_post(
                    client,
                    f"/acts/{actor_path}/runs",
                    json_body=actor_input,
                    params={"maxTotalChargeUsd": str(max_charge)},
                    token=token,
                )
                run_id = (
                    (run_resp.get("data") or {}).get("id")
                    if isinstance(run_resp, dict)
                    else None
                )
                if not isinstance(run_id, str) or not run_id:
                    raise CollectorError("apify_run_id_missing: no run ID in response")

                run_created_log = collector_log(
                    "apify_run_created", f"run_id={run_id}"
                )
                # 结构化键，供 run_collector_call 提取后落库。
                # 此前只写在 message 文本里，提取逻辑读的是字典键，
                # 所以 Apify 这条路径的 provider_run_id 一直是 None。
                run_created_log["provider_run_id"] = run_id
                logs.append(run_created_log)

                # 2. Wait for completion
                run_data = await _wait_for_run(client, run_id, token, timeout=run_timeout)
                status = str(run_data.get("status") or "")
                logs.append(
                    collector_log(
                        "apify_run_finished",
                        f"run_id={run_id}, status={status}",
                    )
                )

                if status != "SUCCEEDED":
                    hint = (
                        " (ABORTED 常见原因是 max_total_charge_usd 太小，"
                        "按事件计费的 Actor 会直接中止；请调大该值)"
                        if status == "ABORTED"
                        else ""
                    )
                    errors.append(
                        f"apify_run_failed: run {run_id!r} ended with status={status!r}{hint}"
                    )
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                # 3. Fetch Dataset items
                dataset_id = run_data.get("defaultDatasetId")
                if not isinstance(dataset_id, str) or not dataset_id:
                    errors.append("apify_dataset_id_missing: no defaultDatasetId in run data")
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                items = await _fetch_dataset_items(client, dataset_id, max_items, token)
                dataset_fetched_log = collector_log(
                    "apify_dataset_fetched",
                    f"dataset_id={dataset_id}, count={len(items)}",
                )
                # 同上：run 结束后 item 仍在这个 dataset 里，
                # 但 run 一旦被清理就再也取不回来。必须落库。
                dataset_fetched_log["provider_dataset_id"] = dataset_id
                logs.append(dataset_fetched_log)

        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("apify_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("apify_http_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        # 4. Normalize
        for item in items[:max_items]:
            record = normalize_apify_item(item, actor_id, record_type)
            if record is not None:
                raw_records.append(record)

        logs.append(
            collector_log(
                "apify_collect_done",
                f"normalized={len(raw_records)}/{len(items)} items from {actor_id}",
            )
        )

        if not items:
            _apply_empty_result_policy(self, 0, errors, logs, endpoint_type)

        if items and not raw_records:
            errors.append(
                f"apify_normalize_all_failed: {len(items)} items received but 0 normalized"
            )

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
