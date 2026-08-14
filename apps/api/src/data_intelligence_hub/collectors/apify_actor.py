"""Apify Actor collector.

Runs any Apify Actor asynchronously, polls for completion, and fetches
Dataset items.  Requires APIFY_API_TOKEN environment variable.

collector_type = "apify_actor"
"""

from __future__ import annotations

import asyncio
import os
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

APIFY_BASE_URL = "https://api.apify.com/v2"
APIFY_TIMEOUT = 30.0
APIFY_RUN_WAIT_TIMEOUT = 600.0   # seconds
APIFY_POLL_INTERVAL = 5.0        # seconds between status polls
APIFY_MAX_ITEMS_LIMIT = 1000

APIFY_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"})


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
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return cast(dict[str, Any], resp.json())


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
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return resp.json()


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
    if isinstance(resp, list):
        return [item for item in resp if isinstance(item, dict)]
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


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
    ):
        if platform in lower:
            return platform
    return "web"


def _infer_record_type(actor_id: str) -> str:
    lower = actor_id.lower()
    if "instagram" in lower:
        return "instagram_profile" if "profile" in lower else "instagram_post"
    if "tiktok" in lower:
        return "tiktok_profile" if "profile" in lower else "tiktok_video"
    if "youtube" in lower:
        return "youtube_comment" if "comment" in lower else "youtube_video"
    if "reddit" in lower:
        return "reddit_post"
    if "facebook" in lower:
        return "facebook_comment" if "comment" in lower else "facebook_post"
    if "amazon" in lower:
        return "amazon_product"
    if "trustpilot" in lower or "appstore" in lower or "google-play" in lower:
        return "review"
    if "linkedin" in lower:
        return "linkedin_post"
    if "twitter" in lower or "tweet" in lower:
        return "twitter_post"
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
        max_total_charge_usd:   float (default 1.0)
        record_type:            str   override inferred record_type
    """

    collector_type = "apify_actor"

    def validate_config(self) -> dict[str, Any]:
        actor_id = require_text(self.config, "actor_id")
        if "/" not in actor_id:
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
        max_charge = float(charge_raw) if isinstance(charge_raw, (int, float, str)) else 1.0

        return {
            "actor_id": actor_id,
            "actor_input": actor_input,
            "max_items": max_items,
            "run_timeout_seconds": run_timeout,
            "max_total_charge_usd": max_charge,
            "record_type": self.config.get("record_type"),
        }

    async def test(self) -> CollectorTestResult:
        logs: list[dict[str, Any]] = []
        try:
            token = _get_api_token()
        except CollectorError as exc:
            msg = f"Apify token test failed: {exc}"
            logs.append(collector_log("apify_test_failed", msg, level="error"))
            return CollectorTestResult(status="failed", message=msg, logs=logs)
        try:
            async with httpx.AsyncClient() as client:
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
            async with httpx.AsyncClient() as client:
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

                logs.append(collector_log("apify_run_created", f"run_id={run_id}"))

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
                    errors.append(
                        f"apify_run_failed: run {run_id!r} ended with status={status!r}"
                    )
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                # 3. Fetch Dataset items
                dataset_id = run_data.get("defaultDatasetId")
                if not isinstance(dataset_id, str) or not dataset_id:
                    errors.append("apify_dataset_id_missing: no defaultDatasetId in run data")
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)

                items = await _fetch_dataset_items(client, dataset_id, max_items, token)
                logs.append(
                    collector_log(
                        "apify_dataset_fetched",
                        f"dataset_id={dataset_id}, count={len(items)}",
                    )
                )

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

        if items and not raw_records:
            errors.append(
                f"apify_normalize_all_failed: {len(items)} items received but 0 normalized"
            )

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)
