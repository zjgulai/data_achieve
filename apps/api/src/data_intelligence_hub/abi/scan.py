"""Apify dataset scan and raw ingestion.

This is the first real consumer of ``meta.ingest_job``. It does one job:

1. Authenticate with one Apify token (env bootstrap; per-account encrypted
   tokens are the next slice).
2. List datasets created on the target Beijing date.
3. Upsert ``raw.apify_dataset``.
4. Fetch items with explicit offset/limit and write ``raw.apify_item``.

Design rules from the ABI plan:
- ``collected_month`` is the UTC month of ``dataset.createdAt``. It is not the
  target date and not the ingestion date.
- NUL bytes are stripped before jsonb insertion.
- Partitions are ensured for the dataset month before rows are written.
- 404 means the dataset was deleted by retention; mark it expired, do not retry.
- 429 is account-level; back off, do not rotate tokens.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.abi.ingest import ABI_TZ

logger = structlog.get_logger(__name__)

APIFY_API = "https://api.apify.com/v2"
PAGE = 1000
INSERT_BATCH = 500
MAX_RETRIES = 5


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def target_date_of(created_at: datetime, tz: ZoneInfo = ABI_TZ) -> date:
    return created_at.astimezone(tz).date()


def month_start_of(created_at: datetime) -> date:
    utc = created_at.astimezone(UTC)
    return date(utc.year, utc.month, 1)


def strip_nul(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {key: strip_nul(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_nul(item) for item in value]
    return value


def content_hash(item: Any) -> bytes:
    canonical = json.dumps(
        strip_nul(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


async def _request(
    client: httpx.AsyncClient,
    token: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(f"{APIFY_API}{path}", params=params, headers=headers)
        except httpx.HTTPError as exc:
            last_error = exc
            await asyncio.sleep(min(2**attempt, 30))
            continue
        if response.status_code == 429 or response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                f"apify {response.status_code}",
                request=response.request,
                response=response,
            )
            await asyncio.sleep(min(2**attempt, 30))
            continue
        return response
    raise RuntimeError(f"apify request failed: {last_error}")


async def get_account(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    response = await _request(client, token, "/users/me")
    response.raise_for_status()
    return cast(dict[str, Any], response.json()["data"])


async def list_datasets(
    client: httpx.AsyncClient,
    token: str,
    target_date: date | None,
    *,
    max_datasets: int | None = None,
) -> list[dict[str, Any]]:
    """List datasets, optionally filtered to one Beijing date.

    The API has no createdAt filter in the rescue path, so page through both
    unnamed and named datasets and filter client-side. 6k datasets is ~6 pages.
    """
    found: dict[str, dict[str, Any]] = {}
    for unnamed in (1, 0):
        offset = 0
        while True:
            response = await _request(
                client,
                token,
                "/datasets",
                {
                    "limit": PAGE,
                    "offset": offset,
                    "unnamed": unnamed,
                    "desc": 0,
                },
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            items = data.get("items") or []
            total = int(data.get("total") or 0)
            for raw in items:
                created = _parse_dt(raw.get("createdAt"))
                if target_date is not None and (
                    created is None or target_date_of(created) != target_date
                ):
                    continue
                dataset_id = raw.get("id")
                if dataset_id and dataset_id not in found:
                    found[dataset_id] = raw
            offset += len(items)
            if not items or offset >= total:
                break

    ordered = sorted(
        found.values(), key=lambda item: (item.get("createdAt") or "", item.get("id") or "")
    )
    if max_datasets is not None:
        ordered = ordered[:max_datasets]
    return ordered


async def iter_items(
    client: httpx.AsyncClient,
    token: str,
    dataset_id: str,
    *,
    max_items: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield items with explicit offset/limit. No 10k truncation."""
    offset = 0
    yielded = 0
    total: int | None = None
    while True:
        response = await _request(
            client,
            token,
            f"/datasets/{dataset_id}/items",
            {
                "format": "jsonl",
                "clean": "0",
                "limit": PAGE,
                "offset": offset,
            },
        )
        if response.status_code == 404:
            logger.warning("abi_scan_dataset_expired", dataset_id=dataset_id)
            return
        response.raise_for_status()
        header = response.headers.get("X-Apify-Pagination-Total")
        if header:
            total = int(header)
        body = response.content
        if not body:
            return
        lines = body.splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning("abi_scan_item_not_json", dataset_id=dataset_id, offset=offset)
                continue
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return
        offset += len(lines)
        if len(lines) < PAGE:
            return
        if total is not None and offset >= total:
            return


async def ensure_account(
    session: AsyncSession,
    *,
    account: dict[str, Any],
) -> uuid.UUID:
    apify_user_id = str(account["id"])
    label = str(account.get("username") or apify_user_id)
    plan = str((account.get("plan") or {}).get("id") or "unknown")
    retention = int((account.get("plan") or {}).get("dataRetentionDays") or 31)
    row = await session.execute(
        text(
            """
            INSERT INTO meta.apify_account
                (id, label, apify_user_id, plan, data_retention_days, enabled)
            VALUES
                (gen_random_uuid(), :label, :apify_user_id, :plan, :retention, true)
            ON CONFLICT (apify_user_id) DO UPDATE
            SET label = EXCLUDED.label,
                plan = EXCLUDED.plan,
                data_retention_days = EXCLUDED.data_retention_days
            RETURNING id
            """
        ),
        {
            "label": label,
            "apify_user_id": apify_user_id,
            "plan": plan,
            "retention": retention,
        },
    )
    return cast(uuid.UUID, row.scalar_one())


async def _attribution(
    session: AsyncSession, act_id: str | None
) -> tuple[str, str, str | None, str, str]:
    if not act_id:
        return "other", "unknown", None, "unknown", "unknown"
    row = (
        await session.execute(
            text(
                """
                SELECT platform, object_type, endpoint_type, source, confidence
                FROM meta.actor_registry
                WHERE actor_id = :act_id
                """
            ),
            {"act_id": act_id},
        )
    ).first()
    if row is None:
        return "other", "unknown", None, "unknown", "unknown"
    return (
        str(row.platform),
        str(row.object_type),
        str(row.endpoint_type) if row.endpoint_type else None,
        str(row.source),
        str(row.confidence),
    )


async def upsert_dataset(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    batch_id: uuid.UUID,
    raw: dict[str, Any],
    retention_days: int,
) -> dict[str, Any]:
    created_at = _parse_dt(raw.get("createdAt"))
    modified_at = _parse_dt(raw.get("modifiedAt"))
    accessed_at = _parse_dt(raw.get("accessedAt"))
    named = raw.get("name") is not None
    retention_deadline = (
        None
        if named or created_at is None
        else created_at.astimezone(UTC).date() + timedelta(days=retention_days)
    )
    platform, object_type, endpoint_type, source, confidence = await _attribution(
        session, raw.get("actId")
    )
    await session.execute(
        text(
            """
            INSERT INTO raw.apify_dataset
                (dataset_id, account_id, run_id, act_id, actor_name,
                 platform, object_type, endpoint_type, endpoint_source, confidence,
                 dataset_name, named, created_at, modified_at, accessed_at,
                 retention_deadline, retention_estimated, item_count_head,
                 last_synced_at, last_synced_batch, status)
            VALUES
                (:dataset_id, :account_id, :run_id, :act_id, NULL,
                 :platform, :object_type, :endpoint_type, :source, :confidence,
                 :dataset_name, :named, :created_at, :modified_at, :accessed_at,
                 :retention_deadline, true, :item_count_head,
                 clock_timestamp(), :batch_id, 'active')
            ON CONFLICT (dataset_id) DO UPDATE
            SET modified_at = EXCLUDED.modified_at,
                accessed_at = EXCLUDED.accessed_at,
                item_count_head = EXCLUDED.item_count_head,
                retention_deadline = EXCLUDED.retention_deadline,
                last_synced_at = clock_timestamp(),
                last_synced_batch = EXCLUDED.last_synced_batch,
                status = 'active'
            """
        ),
        {
            "dataset_id": raw["id"],
            "account_id": account_id,
            "run_id": raw.get("actRunId"),
            "act_id": raw.get("actId"),
            "platform": platform,
            "object_type": object_type,
            "endpoint_type": endpoint_type,
            "source": source,
            "confidence": confidence,
            "dataset_name": raw.get("name"),
            "named": named,
            "created_at": created_at,
            "modified_at": modified_at,
            "accessed_at": accessed_at,
            "retention_deadline": retention_deadline,
            "item_count_head": int(raw.get("itemCount") or 0),
            "batch_id": batch_id,
        },
    )
    return {
        "dataset_id": raw["id"],
        "created_at": created_at,
        "platform": platform,
        "object_type": object_type,
        "item_count": int(raw.get("itemCount") or 0),
    }


async def insert_items(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    dataset_id: str,
    platform: str,
    object_type: str,
    items: list[tuple[int, dict[str, Any]]],
    batch_id: uuid.UUID,
    collected_month: date,
) -> int:
    if not items:
        return 0
    await session.execute(
        text("SELECT meta.ensure_partitions(:start, :stop)"),
        {"start": collected_month, "stop": collected_month},
    )
    payload = [
        {
            "collected_month": collected_month,
            "dataset_id": dataset_id,
            "item_index": index,
            "account_id": account_id,
            "platform": platform,
            "object_type": object_type,
            "item": json.dumps(
                strip_nul(item), ensure_ascii=False, default=str, separators=(",", ":")
            ),
            "content_hash": content_hash(item),
            "fetch_batch_id": batch_id,
        }
        for index, item in items
    ]
    await session.execute(
        text(
            """
            INSERT INTO raw.apify_item
                (collected_month, dataset_id, item_index, account_id,
                 platform, object_type, item, content_hash, pii_class,
                 item_status, fetched_at, fetch_batch_id)
            VALUES
                (:collected_month, :dataset_id, :item_index, :account_id,
                 :platform, :object_type, CAST(:item AS jsonb), :content_hash,
                 'unknown', 'content', clock_timestamp(), :fetch_batch_id)
            ON CONFLICT (collected_month, dataset_id, item_index) DO NOTHING
            """
        ),
        payload,
    )
    return len(payload)


async def scan_once(
    session: AsyncSession,
    *,
    token: str,
    target_date: date | None,
    max_datasets: int | None,
    max_items: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        account = await get_account(client, token)
        account_id = await ensure_account(session, account=account)
        retention_days = int((account.get("plan") or {}).get("dataRetentionDays") or 31)
        datasets = await list_datasets(client, token, target_date, max_datasets=max_datasets)
        logger.info(
            "abi_scan_datasets",
            account=account.get("username"),
            target_date=target_date.isoformat() if target_date else None,
            count=len(datasets),
        )
        if dry_run:
            return {
                "account": account.get("username"),
                "datasets": len(datasets),
                "items": sum(int(item.get("itemCount") or 0) for item in datasets),
                "dry_run": True,
            }

        total_items = 0
        for raw in datasets:
            batch_id = uuid.uuid4()
            meta = await upsert_dataset(
                session,
                account_id=account_id,
                batch_id=batch_id,
                raw=raw,
                retention_days=retention_days,
            )
            created_at = meta["created_at"]
            if created_at is None:
                logger.warning("abi_scan_dataset_no_created_at", dataset_id=raw["id"])
                continue
            collected_month = month_start_of(created_at)
            buffer: list[tuple[int, dict[str, Any]]] = []
            index = 0
            async for item in iter_items(client, token, raw["id"], max_items=max_items):
                buffer.append((index, item))
                index += 1
                if len(buffer) >= INSERT_BATCH:
                    total_items += await insert_items(
                        session,
                        account_id=account_id,
                        dataset_id=raw["id"],
                        platform=meta["platform"],
                        object_type=meta["object_type"],
                        items=buffer,
                        batch_id=batch_id,
                        collected_month=collected_month,
                    )
                    buffer = []
            total_items += await insert_items(
                session,
                account_id=account_id,
                dataset_id=raw["id"],
                platform=meta["platform"],
                object_type=meta["object_type"],
                items=buffer,
                batch_id=batch_id,
                collected_month=collected_month,
            )
            await session.execute(
                text(
                    """
                    UPDATE raw.apify_dataset
                    SET item_count_local = :count,
                        last_synced_at = clock_timestamp()
                    WHERE dataset_id = :dataset_id
                    """
                ),
                {"count": index, "dataset_id": raw["id"]},
            )
            await session.commit()
            logger.info(
                "abi_scan_dataset_done",
                dataset_id=raw["id"],
                items=index,
            )
        return {
            "account": account.get("username"),
            "datasets": len(datasets),
            "items_written": total_items,
            "dry_run": False,
        }
