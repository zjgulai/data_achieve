#!/usr/bin/env python3
"""把数据库真实存量同步到飞书「ABI数据资产汇总表」的存量汇总 Sheet。

设计要点：

1. **按「表标识」匹配，不按行序。** 飞书记录顺序不保证稳定，
   按位置更新会在有人手工排序后写错行。
2. **条数取 n_live_tup 后按父表合并。** 分区子表（apify_item_2026xx）
   的行数要累加到父表 apify_item，否则看板会显示父表 0 条。
3. **只更新「存量条数」与「采集状态」两列。** 其它列是人工维护的
   说明性字段，脚本不覆盖，避免冲掉人工修改。
4. **dry-run 先跑。** 更新前打印将要写入的差异，人工确认后再执行。
5. 飞书 batch-update 单次上限 200 条，按批切分。

用法：
    python3 scripts/apify_lake/sync_feishu_counts.py --dsn "$DSN" --dry-run
    python3 scripts/apify_lake/sync_feishu_counts.py --dsn "$DSN" --execute
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE_TOKEN = "TjAybkakKamKO9s943uc0vdmnL0"
TABLE_ID = "tbl5QHbogBS24gKm"
BATCH = 200

# 分区子表 → 父表。行数必须合并，否则父表显示 0。
PARTITION_PARENT = {
    "raw.apify_item_": "raw.apify_item",
    "meta.audit_log_": "meta.audit_log",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_db_counts(dsn: str) -> dict[str, int]:
    """读每张表的真实行数，并把分区子表累加到父表。"""
    import psycopg

    sql = """
        SELECT schemaname || '.' || relname AS rel, n_live_tup
        FROM pg_stat_user_tables
        WHERE schemaname IN ('meta', 'raw', 'abi')
    """
    raw: dict[str, int] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for rel, n in cur.fetchall():
                raw[rel] = int(n or 0)

    merged: dict[str, int] = dict(raw)
    for rel, n in raw.items():
        for prefix, parent in PARTITION_PARENT.items():
            if rel.startswith(prefix) and rel != parent:
                # 父表累计分区行数；分区子表本身保留自己的行数
                merged[parent] = merged.get(parent, 0) + n
                break
    return merged


def fetch_feishu_rows(base_token: str, table_id: str) -> list[dict[str, Any]]:
    """读飞书存量汇总的全部行，返回 [{record_id, 表标识, 存量条数}]。"""
    cmd = [
        "lark-cli", "base", "+record-list",
        "--base-token", base_token, "--table-id", table_id,
        "--as", "bot", "--limit", "200", "--format", "json",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"record-list 失败: {out.stderr[:300]}")
    payload = json.loads(out.stdout)
    if not payload.get("ok"):
        raise RuntimeError(f"record-list 返回错误: {payload.get('error')}")

    data = payload["data"]
    # fields 是字段名数组（字符串），不是对象数组
    fields = [f if isinstance(f, str) else (f.get("name") or f.get("field_name"))
              for f in data["fields"]]
    idx_key = fields.index("表标识")
    idx_cnt = fields.index("存量条数")
    idx_state = fields.index("采集状态")

    rows: list[dict[str, Any]] = []
    for rec_id, vals in zip(data["record_id_list"], data["data"]):
        rows.append({
            "record_id": rec_id,
            "key": vals[idx_key],
            "count": vals[idx_cnt],
            "state": vals[idx_state],
        })
    return rows


def push_updates(base_token: str, table_id: str,
                 updates: dict[str, dict[str, Any]], execute: bool) -> int:
    """批量更新。updates 形如 {record_id: {字段: 值}}。"""
    items = list(updates.items())
    done = 0
    for i in range(0, len(items), BATCH):
        chunk = dict(items[i:i + BATCH])
        tmp = Path(".abi_tmp")
        tmp.mkdir(exist_ok=True)
        path = tmp / f"upd_{i // BATCH}.json"
        path.write_text(json.dumps({"update_records": chunk}, ensure_ascii=False))
        if not execute:
            log(f"  [dry-run] 批 {i // BATCH}：{len(chunk)} 条")
            done += len(chunk)
            continue
        cmd = [
            "lark-cli", "base", "+record-batch-update",
            "--base-token", base_token, "--table-id", table_id,
            "--as", "bot", "--json", f"@./{path}",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            log(f"  [FAIL] 批 {i // BATCH}: {out.stderr[:200]}")
            continue
        payload = json.loads(out.stdout)
        if not payload.get("ok"):
            log(f"  [FAIL] 批 {i // BATCH}: {payload.get('error', {}).get('message')}")
            continue
        done += len(chunk)
        log(f"  [ok] 批 {i // BATCH}：{len(chunk)} 条")
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--base-token", default=BASE_TOKEN)
    ap.add_argument("--table-id", default=TABLE_ID)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.execute:
        log("必须指定 --dry-run 或 --execute")
        return 2

    log("读取数据库存量…")
    db = fetch_db_counts(args.dsn)
    log(f"  库内 {len(db)} 张表")

    log("读取飞书表格…")
    rows = fetch_feishu_rows(args.base_token, args.table_id)
    log(f"  飞书 {len(rows)} 行")

    updates: dict[str, dict[str, Any]] = {}
    changed = unchanged = missing = 0
    for r in rows:
        key = r["key"]
        if key not in db:
            missing += 1
            log(f"  [跳过] {key}：库内无此表")
            continue
        new_cnt = db[key]
        old_cnt = r["count"] or 0
        # 分区子表的行数已经累加进父表，必须在状态列标明，
        # 否则看板把父表与分区一起求和会得到双倍数字。
        if any(key.startswith(pre) and key != parent
               for pre, parent in PARTITION_PARENT.items()):
            new_state = "分区子表（已计入父表，勿重复求和）"
        elif new_cnt > 0:
            new_state = "已入仓"
        else:
            new_state = r["state"]
        if new_cnt == old_cnt and new_state == r["state"]:
            unchanged += 1
            continue
        updates[r["record_id"]] = {"存量条数": new_cnt, "采集状态": new_state}
        changed += 1
        log(f"  {key:34} {old_cnt:>8} -> {new_cnt:>8}")

    log(f"待更新 {changed} 条，未变 {unchanged} 条，无匹配 {missing} 条")
    if updates:
        n = push_updates(args.base_token, args.table_id, updates, args.execute)
        log(f"已提交 {n} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
