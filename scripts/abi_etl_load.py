#!/usr/bin/env python3
"""Load the first ABI ETL slice from local JSONL extracts into the ABI schema.

Source: decompressed `extract_local.py` output, one envelope per line:
    {"__origin__": ..., "src_file": ..., "row": {...}}

Target: the application PostgreSQL `abi` schema, through the same upload
service the HTTP API uses. This keeps the typed table, column catalog, PII
policies, row count and version bookkeeping in one path.

The script is deliberately two-mode:
  --dry-run   parse, infer columns, count rows, verify source SHA-256. No DB.
  --execute   create/find dataset, set policies, upload, commit.

Run inside the API container for --execute. Dry-run works anywhere Python 3.11+
is available.

Usage:
  python3 scripts/abi_etl_load.py --source-dir /tmp/abi-etl-src --dry-run
  docker exec -i data_achieve_scrapy_api python /tmp/abi_etl_load.py \
      --source-dir /tmp/abi-etl-src --workspace-slug data_scrapy --execute
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

TABLES: dict[str, dict[str, str]] = {
    "si_tiktok_video": {
        "name": "TikTok 视频快照",
        "object_type": "video",
        "description": "TikTok 话题榜视频快照，来自 si_duckdb 本地抽取。",
    },
    "si_tiktok_comment": {
        "name": "TikTok 评论",
        "object_type": "comment",
        "description": "TikTok 视频评论，来自 si_duckdb 本地抽取。",
    },
    "si_tiktok_hashtag_snapshot": {
        "name": "TikTok 话题榜快照",
        "object_type": "hashtag",
        "description": "TikTok 话题榜逐日快照，来自 si_duckdb 本地抽取。",
    },
    "si_metric_snapshot": {
        "name": "TikTok 指标快照",
        "object_type": "metric",
        "description": "TikTok 对象指标快照，来自 si_duckdb 本地抽取。",
    },
    "si_author_video_snapshot": {
        "name": "TikTok 竞品账号视频快照",
        "object_type": "author_video",
        "description": "竞品账号视频快照，来自 si_duckdb 本地抽取。",
    },
}

PII_QUASI = {
    "author_id",
    "author_unique_id",
    "sec_uid",
    "music_id",
    "hashtag_id",
}
PII_DIRECT = {
    "author_nickname",
    "author_handle",
    "author_avatar",
    "author_avatar_url",
    "account_handle",
    "music_author",
}
PUBLIC_TEXT = {"descr", "text", "caption", "music_title"}

# The upload service defaults to the first column as the primary key. That is
# wrong for snapshot tables, where the first column repeats. These keys were
# checked against the 2026-10-28 extracts: every key is unique for its table.
PRIMARY_KEYS: dict[str, list[str]] = {
    "si_tiktok_video": ["video_id"],
    "si_tiktok_comment": ["comment_id"],
    "si_tiktok_hashtag_snapshot": ["snapshot_date", "hashtag", "video_id"],
    "si_metric_snapshot": ["snapshot_date", "object_type", "object_id", "captured_at"],
    "si_author_video_snapshot": ["snapshot_date", "account_handle", "video_id"],
}


@dataclass
class SourceStats:
    rows: int
    sha256: str
    columns: list[str]
    sample: dict[str, Any]
    type_samples: dict[str, list[Any]]


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            row = record.get("row") if isinstance(record, dict) else None
            if isinstance(row, dict):
                yield _clean(row)


def scan_source(path: Path, success: dict[str, Any]) -> SourceStats:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    expected = success.get("content_sha256")
    if expected and digest != expected:
        raise SystemExit(f"source sha256 mismatch for {path}: {digest} != {expected}")

    rows = 0
    columns: list[str] = []
    seen: set[str] = set()
    sample: dict[str, Any] = {}
    type_samples: dict[str, list[Any]] = {}
    for row in _iter_rows(path):
        if not sample:
            sample = row
        rows += 1
        for key, value in row.items():
            if key not in seen:
                seen.add(key)
                columns.append(key)
            if value is not None and len(type_samples.get(key, [])) < 3:
                type_samples.setdefault(key, []).append(value)
    if rows != int(success.get("rows", rows)):
        raise SystemExit(
            f"source row count mismatch for {path}: {rows} != {success.get('rows')}"
        )
    return SourceStats(
        rows=rows,
        sha256=digest,
        columns=columns,
        sample=sample,
        type_samples=type_samples,
    )


def infer_type(values: list[Any]) -> str:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return "text"
    if all(isinstance(value, bool) for value in non_null):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null):
        return "bigint"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null):
        return "numeric"
    if all(isinstance(value, (dict, list)) for value in non_null):
        return "json"
    return "text"


def infer_columns(stats: SourceStats) -> list[dict[str, Any]]:
    return [
        {
            "column_name": name,
            "data_type": infer_type(stats.type_samples.get(name, [])),
            "nullable": True,
            "filterable": True,
            "sortable": True,
        }
        for name in stats.columns
    ]


def policy_for(column: str) -> tuple[str, str | None]:
    if column in PII_DIRECT:
        return "direct", "redact"
    if column in PII_QUASI:
        return "quasi", "hash"
    if column in PUBLIC_TEXT:
        return "none", None
    return "none", None


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_csv(source: Path, target: Path, columns: list[str]) -> tuple[int, str]:
    """Write a header + data CSV.

    The upload service treats every file as header + rows and subtracts one
    from the row counter. JSONL therefore under-counts by one and fails the
    commit check. CSV is the format the service actually supports end to end.
    """
    rows = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(columns)
        for row in _iter_rows(source):
            writer.writerow([_csv_value(row.get(name)) for name in columns])
            rows += 1
    hasher = hashlib.sha256()
    with target.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return rows, hasher.hexdigest()


def prepare(source_dir: Path, tables: list[str], out_dir: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for table in tables:
        table_dir = source_dir / table
        success_path = table_dir / "_SUCCESS"
        source_path = table_dir / "part-00000.jsonl"
        if not source_path.is_file():
            raise SystemExit(f"missing source: {source_path}")
        success = json.loads(success_path.read_text(encoding="utf-8")) if success_path.is_file() else {}
        stats = scan_source(source_path, success)
        columns = infer_columns(stats)
        target_path = out_dir / f"{table}.csv"
        rows, digest = write_csv(source_path, target_path, stats.columns)
        if rows != stats.rows:
            raise SystemExit(f"transform row mismatch for {table}: {rows} != {stats.rows}")
        manifest[table] = {
            "source_rows": stats.rows,
            "source_sha256": stats.sha256,
            "csv": str(target_path),
            "csv_rows": rows,
            "csv_sha256": digest,
            "columns": columns,
            "sample": stats.sample,
        }
        print(
            f"{table}: rows={rows} columns={len(columns)} "
            f"csv_sha256={digest[:12]}…"
        )
    return manifest


async def execute(
    manifest: dict[str, dict[str, Any]],
    workspace_slug: str,
    owner_email: str | None,
    slug_suffix: str,
    limit: int | None,
) -> None:
    from data_intelligence_hub.api.deps import DatasetAccess
    from data_intelligence_hub.core.database import async_session_factory
    from data_intelligence_hub.repositories import abi as abi_repo
    from data_intelligence_hub.repositories.users import get_user_by_email, get_user_by_id
    from data_intelligence_hub.repositories.workspaces import get_workspace_by_slug
    from data_intelligence_hub.schemas.abi import (
        AbiColumnCreate,
        AbiDatasetCreateRequest,
        AbiPolicyUpdateItem,
        AbiPolicyUpdateRequest,
        AbiUploadCreateRequest,
    )
    from data_intelligence_hub.services import abi_service

    async with async_session_factory() as session:
        workspace = await get_workspace_by_slug(session, workspace_slug)
        if workspace is None:
            raise SystemExit(f"workspace not found: {workspace_slug}")
        if owner_email:
            user = await get_user_by_email(session, owner_email)
        else:
            user = await get_user_by_id(session, workspace.owner_id)
        if user is None:
            raise SystemExit("workspace owner not found")

        for table, item in manifest.items():
            slug = table + slug_suffix
            dataset = await abi_repo.get_dataset_by_slug(session, workspace.id, slug)
            if dataset is None:
                payload = AbiDatasetCreateRequest(
                    slug=slug,
                    name=TABLES[table]["name"],
                    description=TABLES[table]["description"],
                    source_kind="upload",
                    platform="tiktok",
                    object_type=TABLES[table]["object_type"],
                    origin="si_duckdb",
                    columns=[
                        AbiColumnCreate(**column) for column in item["columns"]
                    ],
                )
                await abi_service.create_abi_dataset(session, workspace, user, payload)
                dataset = await abi_repo.get_dataset_by_slug(session, workspace.id, slug)
                print(f"{table}: dataset created slug={slug}")
            else:
                print(f"{table}: dataset exists slug={slug} version={dataset.version}")

            access = await abi_service._resolve_dataset_for_user(
                session, workspace, user, slug, "admin"
            )
            resolved, grant = access
            dataset_access = DatasetAccess(
                dataset=resolved, grant=grant, workspace=workspace, user=user
            )
            policy_items = []
            for column in item["columns"]:
                pii_class, mask_rule = policy_for(column["column_name"])
                policy_items.append(
                    AbiPolicyUpdateItem(
                        field_path=column["column_name"],
                        pii_class=pii_class,
                        mask_rule=mask_rule,
                    )
                )
            await abi_service.replace_abi_policy(
                session,
                dataset_access,
                AbiPolicyUpdateRequest(
                    items=policy_items,
                    reason="ABI ETL first slice: public post text is none; author identifiers are masked",
                ),
            )
            print(f"{table}: policies set ({len(policy_items)} columns)")

            rows = item["csv_rows"]
            expected_rows = min(rows, limit) if limit else rows
            csv_path = Path(item["csv"])
            if limit:
                limited_path = csv_path.with_suffix(f".limit{limit}.csv")
                with csv_path.open("r", encoding="utf-8", newline="") as source_handle:
                    reader = csv.reader(source_handle)
                    with limited_path.open("w", encoding="utf-8", newline="") as out:
                        writer = csv.writer(out, lineterminator="\n")
                        writer.writerow(next(reader))
                        for index, row in enumerate(reader):
                            if index >= limit:
                                break
                            writer.writerow(row)
                csv_path = limited_path
            hasher = hashlib.sha256()
            with csv_path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    hasher.update(chunk)

            created = await abi_service.create_abi_upload(
                session,
                workspace,
                user,
                AbiUploadCreateRequest(
                    dataset_slug=slug,
                    filename=f"{slug}.csv",
                    mode="replace",
                    expected_sha256=hasher.hexdigest(),
                    expected_rows=expected_rows,
                ),
            )

            async def chunks() -> AsyncIterator[bytes]:
                with csv_path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        yield chunk

            await abi_service.write_abi_upload_content(
                session, workspace, user, created.upload_token, chunks()
            )
            result = await abi_service.commit_abi_upload(
                session,
                workspace,
                user,
                created.batch.id,
                primary_key_columns=PRIMARY_KEYS[table],
            )
            print(
                f"{table}: committed rows={result.rows_loaded} "
                f"status={result.status} rejected={result.rows_rejected}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--out-dir", default="/tmp/abi-etl-csv")
    parser.add_argument("--tables", default=",".join(TABLES))
    parser.add_argument("--workspace-slug", default="data_scrapy")
    parser.add_argument("--owner-email")
    parser.add_argument("--slug-suffix", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    tables = [item.strip() for item in args.tables.split(",") if item.strip()]
    unknown = [item for item in tables if item not in TABLES]
    if unknown:
        raise SystemExit(f"unknown tables: {unknown}")

    manifest = prepare(Path(args.source_dir), tables, Path(args.out_dir))
    if args.dry_run or not args.execute:
        for table, item in manifest.items():
            print(
                f"{table}: type sample "
                + ", ".join(
                    f"{column['column_name']}={column['data_type']}"
                    for column in item["columns"][:8]
                )
            )
        return 0

    asyncio.run(
        execute(
            manifest,
            workspace_slug=args.workspace_slug,
            owner_email=args.owner_email,
            slug_suffix=args.slug_suffix,
            limit=args.limit,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())