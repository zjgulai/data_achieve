#!/usr/bin/env python3
"""把本地历史数据（extract_local.py 的产物）装载进 raw schema。

与 load_to_pg.py 的分工：
- load_to_pg.py 处理 Apify 云端数据，写 raw.apify_item（jsonb 窄表）。
- 本脚本处理 12 张本地表，字段稳定、已展开成列，直接 COPY 进各自的物理表。

设计要点：

1. **信封解包**：extract_local.py 把每条记录包成
   {"__origin__":..,"src_file":..,"src_row_ordinal":..,"row":{...}}。
   本脚本把 row 摊平成列，信封里的三个值填到公共溯源列。
2. **只写目标表存在的列**。源字段集与目标表不一致时（源多了、少了），
   多出的忽略，缺失的留 NULL。这避免 schema 漂移导致整批失败。
3. **jsonb 拒收 \\u0000**，写入前剔除。
4. **空字符串转 NULL**：CSV/xlsx 的空单元格是 ""，直接写入会把
   "product_name 为空" 变成 "product_name 是空串"，破坏 NULLS NOT DISTINCT 去重。
5. 幂等：先 COPY 到临时表，再 INSERT ... SELECT ... ON CONFLICT DO NOTHING。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

import psycopg

ROOT = Path("/Users/lute/data/apify-lake")
SRC = ROOT / "local"

# 提取产物 → raw 表名
SOURCE_MAP: dict[str, str] = {
    "si_duckdb/si_tiktok_video": "si_tiktok_video",
    "si_duckdb/si_tiktok_comment": "si_tiktok_comment",
    "si_duckdb/si_tiktok_hashtag_snapshot": "si_tiktok_hashtag_snapshot",
    "si_duckdb/si_metric_snapshot": "si_metric_snapshot",
    "si_duckdb/si_music_platform_snapshot": "si_music_platform_snapshot",
    "si_duckdb/si_author_video_snapshot": "si_author_video_snapshot",
    "si_duckdb/si_social_post": "si_social_post",
    "x_cache/x_post": "apify_tweet",
    "probe_ig/instagram_post": "probe_instagram_post",
    "probe_tiktok/tiktok_video": "probe_tiktok_video",
    "probe_yt/youtube_video": "probe_youtube_video",
    "pmo/collection_record": "pmo_collection_record",
    "desktop/amazon_review": "amazon_review",
    "desktop/product_catalog": "product_catalog",
}

# 公共溯源列由信封提供，不从 row 取
ENVELOPE_COLS = ("origin", "src_file", "src_row_ordinal")

# 源字段名 → 目标列名。源是中文表头或历史命名时用。
FIELD_ALIASES: dict[str, dict[str, str]] = {
    "amazon_review": {
        "ASIN": "asin",
        "评分": "rating",
        "标题": "title",
        "评论内容": "body",
        "作者": "author",
        "评论日期": "review_date",
        "是否验证购买": "verified_purchase",
        "有用票数": "helpful_votes",
        "总票数": "total_votes",
        "来源描述": "source_description",
    },
    "pmo_collection_record": {
        "id": "record_id",
    },
}

# 需要按行计算的目标列
def _derive(table: str, col: str, row: dict[str, Any], env: dict[str, Any]) -> Any:
    """为源里没有的列生成值。返回 None 表示交回通用逻辑。"""
    import hashlib as _h

    if table == "amazon_review":
        if col == "review_key":
            # 源无原生评论 id：md5(asin|作者|日期|标题|正文)
            parts = [str(row.get(k) or "") for k in
                     ("asin", "author", "review_date", "title", "body")]
            return _h.md5("|".join(parts).encode()).digest()
        if col == "file_date":
            return date(2026, 8, 14)
    if table == "product_catalog":
        if col == "file_date":
            return date(2026, 8, 14)
    if table == "pmo_collection_record":
        if col == "snapshot_date":
            return date(2026, 8, 16)
        if col == "schema_version":
            return row.get("schema_version") or "unknown"
    return None


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def iter_zst(path: Path) -> Iterator[bytes]:
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


def _clean(v: Any) -> Any:
    if isinstance(v, str):
        v = v.replace("\x00", "")
        return None if v == "" else v
    if isinstance(v, (dict, list)):
        # 注意：text[] 列不能收 JSON 字符串，必须传 Python list。
        # 类型判断放在 table_columns 之后，这里交给调用方按列类型处理。
        return _strip_nul(v)
    return v


def _strip_nul(o: Any) -> Any:
    if isinstance(o, str):
        return o.replace("\x00", "")
    if isinstance(o, dict):
        return {k: _strip_nul(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_strip_nul(v) for v in o]
    return o


def table_columns(conn: psycopg.Connection, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [r[0] for r in cur.fetchall()]


def column_types(conn: psycopg.Connection, table: str) -> dict[str, str]:
    """列名 → 数据类型。用来区分 text[]、jsonb 与普通标量。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = %s
            """,
            (table,),
        )
        out: dict[str, str] = {}
        for name, dtype, udt in cur.fetchall():
            if dtype == "ARRAY":
                out[name] = "array"
            elif dtype == "jsonb" or dtype == "json":
                out[name] = "json"
            else:
                out[name] = dtype
        return out


def defaulted_columns(conn: psycopg.Connection, table: str) -> set[str]:
    """有 column_default 的列。COPY 时不传，让默认值（含 nextval/clock_timestamp）生效。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = %s
              AND column_default IS NOT NULL
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def load_one(conn: psycopg.Connection, src_key: str, table: str) -> dict[str, int]:
    base = SRC / src_key
    part = base / "part-00000.jsonl.zst"
    succ = base / "_SUCCESS"
    if not part.exists():
        return {"rows": 0, "skipped": 1}

    info = json.loads(succ.read_text()) if succ.exists() else {}

    cols = table_columns(conn, table)
    ctypes = column_types(conn, table)
    defaulted = defaulted_columns(conn, table)
    if not cols:
        log(f"  [skip] raw.{table} 不存在")
        return {"rows": 0, "skipped": 1}

    # 目标列里哪些来自源 row（排除信封列）
    data_cols = [c for c in cols if c not in ENVELOPE_COLS]

    batch_uuid = uuid.uuid4()
    batch: list[tuple] = []
    for line in iter_zst(part):
        try:
            env = json.loads(line)
        except Exception:
            continue
        row = env.get("row") or {}
        aliases = FIELD_ALIASES.get(table, {})
        # 把别名映射先物化到 row 的副本上，后续统一按目标列名取
        mapped = dict(row)
        for src, dst in aliases.items():
            if src in row and dst not in mapped:
                mapped[dst] = row[src]

        env_vals = {
            "origin": env.get("__origin__"),
            "src_file": env.get("src_file"),
            "src_row_ordinal": env.get("src_row_ordinal"),
        }
        ordered: list[Any] = []
        for c in cols:
            if c in env_vals:
                ordered.append(env_vals[c])
                continue
            if c == "content_hash":
                # 规范化 JSON 的 sha256；重放同一行得同一哈希
                canon = json.dumps(mapped, ensure_ascii=False, sort_keys=True)
                ordered.append(hashlib.sha256(canon.encode()).digest())
                continue
            if c == "load_batch_id":
                ordered.append(batch_uuid)
                continue
            if c in defaulted and c not in ("content_hash", "load_batch_id"):
                # 有默认值的列（loaded_at、nextval 主键等）不传值
                continue

            v = _clean(mapped.get(c))
            if v is None:
                derived = _derive(table, c, mapped, env)
                if derived is not None:
                    v = derived
            ctype = ctypes.get(c)
            if ctype == "array":
                if v is None:
                    ordered.append(None)
                elif isinstance(v, (list, tuple)):
                    ordered.append([_clean(x) for x in v])
                else:
                    ordered.append([v])
            elif ctype == "json":
                ordered.append(
                    None if v is None
                    else json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list))
                    else v
                )
            elif ctype == "boolean" and isinstance(v, str):
                # 中文导出表头常写 是/否；直接入 boolean 会报
                # invalid input syntax for type boolean
                low = v.strip().lower()
                if low in ("是", "true", "t", "yes", "y", "1"):
                    ordered.append(True)
                elif low in ("否", "false", "f", "no", "n", "0"):
                    ordered.append(False)
                else:
                    ordered.append(None)
            elif isinstance(v, bool) and ctype in ("smallint", "integer", "bigint"):
                ordered.append(int(v))
            else:
                ordered.append(v)
        batch.append(tuple(ordered))

    if not batch:
        return {"rows": 0, "skipped": 1}

    with conn.cursor() as cur:
        # LIKE 默认不复制 DEFAULT，会让 loaded_at 这类带 server_default 的
        # NOT NULL 列在暂存表里变成"无默认值"，插入即报错。
        cur.execute(
            "CREATE TEMP TABLE _stg_local "
            "(LIKE raw." + table + " INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        cur.execute("TRUNCATE _stg_local")
        # 有默认值的列不传值，让默认生效（loaded_at、nextval 主键等）
        copy_cols = [c for c in cols
                     if c not in defaulted or c in ("content_hash", "load_batch_id")]
        col_sql = ", ".join(f'"{c}"' for c in copy_cols)
        with cur.copy(f"COPY _stg_local ({col_sql}) FROM STDIN") as copy:
            for r in batch:
                copy.write_row(r)
        cur.execute(f'INSERT INTO raw.{table} ({col_sql}) SELECT {col_sql} FROM _stg_local ON CONFLICT DO NOTHING')
        inserted = cur.rowcount
    conn.commit()
    return {"rows": inserted, "read": len(batch), "skipped": 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    targets = {k: v for k, v in SOURCE_MAP.items() if not args.only or args.only in k}
    log(f"待装载 {len(targets)} 张表")

    total = 0
    with psycopg.connect(args.dsn) as conn:
        for src_key, table in targets.items():
            try:
                r = load_one(conn, src_key, table)
                total += r.get("rows", 0)
                log(f"  raw.{table:32} 读 {r.get('read', 0):>7} 写 {r.get('rows', 0):>7}"
                    + ("  [跳过]" if r.get("skipped") else ""))
            except Exception as exc:
                conn.rollback()
                log(f"  [FAIL] {table}: {type(exc).__name__}: {str(exc)[:200]}")

    log(f"合计写入 {total} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
