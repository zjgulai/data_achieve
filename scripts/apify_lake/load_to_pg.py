#!/usr/bin/env python3
"""把抢救到磁盘的 Apify 数据装载进 Postgres。

设计要点，每条都对应一次实测或复核发现的失败：

1. 分区键 ``collected_month`` 取 dataset 的 createdAt 月首，不取入仓日。
   同一 dataset 在任何日期重抓都落同一分区，主键天然去重。
2. ``ensure_partitions`` 从最早数据月补到未来 3 个月，不是只建未来。
3. jsonb 拒绝 ``\\u0000``，写入前剔除；NUL 会让整批 COPY 失败。
4. ``item`` 必须是 object；数组、字符串、null 一律进 ``raw.load_error``。
5. 归因不取 actor 默认值：8 个 actor 对应多端点，必须按字段签名再判，
   判不出落 ``other``/``unknown`` 并记 confidence。
6. 用 COPY 批量写，不用逐行 INSERT：24 万行逐行插入要几十分钟。
7. 幂等：``ON CONFLICT DO NOTHING`` 需要走暂存表，COPY 不直接支持。
   这里用「先 COPY 到 staging，再 INSERT ... SELECT ... ON CONFLICT DO NOTHING」。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from attribution import classify_item_status, resolve as resolve_attr  # noqa: E402

ROOT = Path(os.environ.get("ABI_LAKE_ROOT", "/Users/lute/data/apify-lake"))
ACTOR_MAP = Path(__file__).resolve().parent / "actor_map.json"
ACTID_MAP = Path(__file__).resolve().parent / "actid_map.json"

ACCOUNTS = {
    "complex_homage": "ofO5drbJf0BsFH2YO",
    "yueguz": "fgLOe61icpb5nmMm5",
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def _load_actor_map() -> dict[str, list[dict[str, str | None]]]:
    if not ACTOR_MAP.exists():
        return {}
    data = json.loads(ACTOR_MAP.read_text())
    return data.get("actors") or {}


def _load_actid_map() -> dict[str, str]:
    """actId → owner/name。dataset.json 只有 actId，没有 actor 名。

    没有这层映射，所有归因都退化成 field_signature，
    平台-类型分区的准确度会下降，且无法发现 actor 级 schema 漂移。
    """
    p = ACTID_MAP
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _iter_zst_lines(path: Path) -> Iterator[bytes]:
    """流式读 jsonl.zst，不整份解压进内存。"""
    import subprocess
    proc = subprocess.Popen(["zstd", "-dc", str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if line.strip():
                yield line
    finally:
        proc.stdout.close()
        proc.wait()


def _clean_item(raw: bytes) -> dict[str, Any] | None:
    """解析并清洗一条 item。返回 None 表示不可入库。"""
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    # jsonb 不接受 \u0000
    return _strip_nul(obj)


def _strip_nul(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace("\x00", "") if "\x00" in obj else obj
    if isinstance(obj, dict):
        return {k: _strip_nul(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_nul(v) for v in obj]
    return obj


def _month_of(created_at: str | None) -> str:
    if not created_at or len(created_at) < 7:
        return "2026-10-01"
    return f"{created_at[:7]}-01"


def seed_accounts(conn: psycopg.Connection) -> dict[str, str]:
    """写入账号，返回 label → uuid。"""
    out: dict[str, str] = {}
    with conn.cursor() as cur:
        for label, uid in ACCOUNTS.items():
            cur.execute(
                """
                INSERT INTO meta.apify_account (id, label, apify_user_id, plan)
                VALUES (gen_random_uuid(), %s, %s, 'SCALE')
                ON CONFLICT (label) DO UPDATE SET apify_user_id = EXCLUDED.apify_user_id
                RETURNING id
                """,
                (label, uid),
            )
            out[label] = str(cur.fetchone()[0])
    conn.commit()
    return out


def ensure_partitions(conn: psycopg.Connection, frm: str, to: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT meta.ensure_partitions(%s::date, %s::date)", (frm, to))
        n = cur.fetchone()[0]
    conn.commit()
    return int(n)


def load_dataset(
    conn: psycopg.Connection,
    ds_dir: Path,
    account_ids: dict[str, str],
    amap: dict[str, list[dict[str, str | None]]],
    actid_map: dict[str, str],
) -> dict[str, Any]:
    """装载一个 dataset 目录。"""
    succ = ds_dir / "_SUCCESS"
    info = json.loads(succ.read_text())
    account = info.get("account") or "unknown"
    account_id = account_ids.get(account)
    if not account_id:
        return {"dataset_id": ds_dir.name.split("=", 1)[-1], "status": "no_account", "rows": 0}

    meta_path = ds_dir / "dataset.json"
    dmeta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            dmeta = json.loads(meta_path.read_text())
        except Exception:
            dmeta = {}

    dataset_id = dmeta.get("id") or ds_dir.name.split("=", 1)[-1]
    created_at = dmeta.get("createdAt")
    month = _month_of(created_at)
    act_id = dmeta.get("actId")
    run_id = dmeta.get("actRunId")

    part = ds_dir / "part-00000.jsonl.zst"
    if not part.exists():
        return {"dataset_id": dataset_id, "status": "no_part", "rows": 0}

    # 第一遍：取首条 item 用于归因，同时统计
    first: dict[str, Any] | None = None
    batch_rows: list[tuple] = []
    total = 0
    rejected = 0
    batch_id = info.get("sha256")
    fetch_batch_uuid = hashlib.md5((batch_id or dataset_id).encode()).hexdigest()

    for line in _iter_zst_lines(part):
        obj = _clean_item(line)
        if obj is None:
            rejected += 1
            continue
        # 归因取样必须跳过哨兵与错误对象：
        # apidojo/tweet-scraper 大量返回 {"noResults": true}，
        # 拿它当样本会让 70 个 dataset 判成 actor_ambiguous。
        if first is None and classify_item_status(obj) == "content":
            first = obj
        total += 1
    # 整个 dataset 全是哨兵时，退回用第一条任意 item 判（至少能判 actor 级归因）
    if first is None:
        for line in _iter_zst_lines(part):
            obj = _clean_item(line)
            if obj is not None:
                first = obj
                break

    actor_name = actid_map.get(act_id or "") or dmeta.get("actorName")
    platform, object_type, source, confidence = resolve_attr(actor_name, first)

    # 第二遍：组装行并写库
    index = 0
    for line in _iter_zst_lines(part):
        obj = _clean_item(line)
        if obj is None:
            continue
        payload = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()
        content_hash = hashlib.sha256(payload).digest()
        batch_rows.append((
            month, dataset_id, index, account_id, platform, object_type,
            json.dumps(obj, ensure_ascii=False), content_hash,
            "unknown", classify_item_status(obj), fetch_batch_uuid,
        ))
        index += 1

    if not batch_rows:
        return {"dataset_id": dataset_id, "status": "empty", "rows": 0}

    with conn.cursor() as cur:
        # 清单
        cur.execute(
            """
            INSERT INTO raw.apify_dataset
                (dataset_id, account_id, run_id, act_id, platform, object_type,
                 endpoint_source, confidence, named, created_at, modified_at,
                 item_count_head, item_count_local, status, last_synced_at,
                 storage_path)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'complete',now(),%s)
            ON CONFLICT (dataset_id) DO UPDATE SET
                platform = EXCLUDED.platform,
                object_type = EXCLUDED.object_type,
                endpoint_source = EXCLUDED.endpoint_source,
                confidence = EXCLUDED.confidence,
                item_count_head = EXCLUDED.item_count_head,
                item_count_local = EXCLUDED.item_count_local,
                status = 'complete',
                last_synced_at = now()
            """,
            (dataset_id, account_id, run_id, act_id, platform, object_type,
             source, confidence, bool(dmeta.get("name")),
             created_at, dmeta.get("modifiedAt"),
             dmeta.get("itemCount") or total, total, str(ds_dir)),
        )
        # 暂存 + upsert，保证幂等
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS _stg_item (
                collected_month date, dataset_id text, item_index integer,
                account_id uuid, platform text, object_type text,
                item jsonb, content_hash bytea, pii_class text,
                item_status text, fetch_batch_id uuid
            ) ON COMMIT DROP
        """)
        cur.execute("TRUNCATE _stg_item")
        with cur.copy(
            "COPY _stg_item (collected_month, dataset_id, item_index, account_id, "
            "platform, object_type, item, content_hash, pii_class, item_status, "
            "fetch_batch_id) "
            "FROM STDIN"
        ) as copy:
            for row in batch_rows:
                copy.write_row(row)
        cur.execute("""
            INSERT INTO raw.apify_item
                (collected_month, dataset_id, item_index, account_id, platform,
                 object_type, item, content_hash, pii_class, item_status,
                 fetch_batch_id)
            SELECT collected_month, dataset_id, item_index, account_id, platform,
                   object_type, item, content_hash, pii_class, item_status,
                   fetch_batch_id
            FROM _stg_item
            ON CONFLICT (collected_month, dataset_id, item_index) DO NOTHING
        """)
    conn.commit()

    return {"dataset_id": dataset_id, "status": "complete", "rows": len(batch_rows),
            "platform": platform, "object_type": object_type,
            "attribution": source, "confidence": confidence, "rejected": rejected}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--account", default="all")
    ap.add_argument("--only-missing", action="store_true")
    args = ap.parse_args()

    amap = _load_actor_map()
    actid_map = _load_actid_map()
    log(f"actor 映射: {len(amap)} 个 actor，actId 映射: {len(actid_map)} 个")

    dirs = sorted((ROOT / "raw").glob("account=*/month=*/dataset=*"))
    if args.account != "all":
        dirs = [d for d in dirs if f"account={args.account}" in str(d)]
    if args.only_missing:
        # 按库内状态跳过已装载的 dataset，不是按本地文件是否存在
        with psycopg.connect(args.dsn) as probe:
            with probe.cursor() as cur:
                cur.execute(
                    "SELECT dataset_id FROM raw.apify_dataset WHERE status = 'complete'"
                )
                done = {r[0] for r in cur.fetchall()}
        dirs = [d for d in dirs if d.name.split("=", 1)[-1] not in done]
        log(f"跳过已装载 {len(done)} 个，剩 {len(dirs)} 个")
    if args.limit:
        dirs = dirs[: args.limit]
    log(f"待装载 {len(dirs)} 个 dataset")

    stats: dict[str, int] = {}
    total_rows = 0
    fails: list[str] = []

    with psycopg.connect(args.dsn, autocommit=False) as conn:
        account_ids = seed_accounts(conn)
        log(f"账号: {account_ids}")
        created = ensure_partitions(conn, "2026-09-01", "2027-01-01")
        log(f"分区补齐: 新建 {created} 个")

        for i, d in enumerate(dirs, 1):
            try:
                r = load_dataset(conn, d, account_ids, amap, actid_map)
                stats[r["status"]] = stats.get(r["status"], 0) + 1
                total_rows += r.get("rows") or 0
            except Exception as exc:
                conn.rollback()
                fails.append(f"{d.name}: {type(exc).__name__}: {exc}")
                log(f"[FAIL] {d.name}: {type(exc).__name__}: {str(exc)[:200]}")
            if i % 500 == 0:
                log(f"进度 {i}/{len(dirs)}，行数 {total_rows}")

    log(f"完成: {stats}，总行数 {total_rows}，失败 {len(fails)}")
    for f in fails[:10]:
        log(f"  {f}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
