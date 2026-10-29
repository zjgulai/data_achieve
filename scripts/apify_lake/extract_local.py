#!/usr/bin/env python3
"""本地历史数据提取器：把散落在本机的数据统一转成 JSONL，供入仓装载。

不直接写 Postgres。理由：
1. 数据来源异构（DuckDB / JSON 数组 / XLSX / CSV），直接写 PG 会把类型推断错误
   固化在库里，无法重放。
2. 转换与装载分离后，转换逻辑改一次就能重跑，不用动库。
3. 输出与 Apify 抢救数据同构（JSONL + _SUCCESS），入仓器只有一条路径。

每条记录统一包一层信封：
    {"__origin__": "...", "src_file": "...", "src_row_ordinal": N, "row": {...}}

这样 PII 分类、行号定位、去重键都能在入仓侧统一处理。

用法：
    python3 scripts/apify_lake/extract_local.py --source si_duckdb
    python3 scripts/apify_lake/extract_local.py --source all --execute
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(os.environ.get("ABI_LAKE_ROOT", "/Users/lute/data/apify-lake"))
OUT_ROOT = ROOT / "local"

SI_DB = Path("/Users/lute/Project/SI-Agent/data/warehouse/si.duckdb")
X_CACHE_DIRS = [
    Path("/Users/lute/Project/pr-agent/data/processed/pr_intel/apify_cache"),
    Path("/Users/lute/Project/pr-agent-prod/data/processed/pr_intel/apify_cache"),
]
IG_PROBE = Path("/Users/lute/Project/pr-agent-prod/artifacts/ig-probe-20260928/raw_items.json")
TT_PROBE_DIR = Path("/Users/lute/Project/pr-agent-prod/artifacts/tiktok-recency-probe-20260919")
YT_PROBE_DIR = Path("/Users/lute/Project/pr-agent-prod/artifacts/yt-sort-ab-20260919")
PMO_DIR = Path("/Users/lute/Project/pr-agent-prod/PMO/PR项目/业务协作/业务协作_PR团队"
               "/吸奶器核心媒体洞察项目/04_采集快照/20260816")
AMAZON_XLSX = Path("/Users/lute/Desktop/amazon_reviews_20260814_024113.xlsx")
PRODUCT_CSV = Path("/Users/lute/Desktop/品类+品牌+产品名称 20260814.csv")


# ---------------------------------------------------------------- helpers

def _json_safe(value: Any) -> Any:
    """转成可 JSON 序列化的值。

    三处必须处理：
    - Decimal / date / datetime 不是 JSON 原生。
    - bytes 直接 str() 会丢信息，用 hex。
    - jsonb 不接受 \\u0000，这里统一剔除（NUL 会让整批 COPY 失败）。
    """
    if isinstance(value, (str, )):
        return value.replace("\x00", "")
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return _json_safe(str(value))


def _write_jsonl_zstd(path: Path, rows: Iterator[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    count = 0
    buf: list[bytes] = []
    plain_hasher = hashlib.sha256()
    proc = subprocess.Popen(
        ["zstd", "-19", "-T0", "-q", "-f", "-o", str(tmp), "-"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    try:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
            line = line.replace(b"\x00", b"")
            plain_hasher.update(line)
            buf.append(line)
            count += 1
            if len(buf) >= 2000:
                proc.stdin.write(b"".join(buf))
                buf.clear()
        if buf:
            proc.stdin.write(b"".join(buf))
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            err = proc.stderr.read().decode()[:400] if proc.stderr else ""
            raise RuntimeError(f"zstd 失败 rc={rc}: {err}")
    except Exception:
        proc.kill()
        raise

    os.replace(tmp, path)
    nbytes = path.stat().st_size
    return {"rows": count, "bytes": nbytes, "content_sha256": plain_hasher.hexdigest()}


def _emit(source: str, name: str, rows: Iterator[dict[str, Any]], log) -> None:
    """写一个逻辑数据集：local/<source>/<name>/part-00000.jsonl.zst + _SUCCESS"""
    base = OUT_ROOT / source / name
    done = base / "_SUCCESS"
    if done.exists():
        log(f"[skip] {source}/{name} 已存在")
        return
    info = _write_jsonl_zstd(base / "part-00000.jsonl.zst", rows)
    info.update({"source": source, "name": name,
                 "extracted_at": datetime.now().isoformat(timespec="seconds")})
    done.write_text(json.dumps(info, ensure_ascii=False))
    log(f"[ok] {source}/{name}: {info['rows']} rows, {info['bytes']} bytes")


def _envelope(origin: str, src_file: str, ordinal: int, row: dict[str, Any]) -> dict[str, Any]:
    return {"__origin__": origin, "src_file": src_file,
            "src_row_ordinal": ordinal, "row": _json_safe(row)}


# ---------------------------------------------------------------- SI duckdb

SI_TABLES = [
    ("si_tiktok_video", "dw_video_wide"),
    ("si_tiktok_comment", "fact_video_comment"),
    ("si_tiktok_hashtag_snapshot", "fact_tag_video_snapshot"),
    ("si_metric_snapshot", "fact_metric_snapshot"),
    ("si_music_platform_snapshot", "fact_music_platform_snapshot"),
    ("si_author_video_snapshot", "fact_author_video_snapshot"),
    ("si_social_post", "social_posts"),
]


def extract_si(log) -> None:
    import duckdb
    if not SI_DB.exists():
        log("[skip] si.duckdb 不存在")
        return

    # 库可能被别的进程锁住，复制一份只读查询
    tmp = Path(tempfile.gettempdir()) / "abi_si_copy.duckdb"
    shutil.copy2(SI_DB, tmp)
    con = duckdb.connect(str(tmp), read_only=True)
    try:
        for name, table in SI_TABLES:
            try:
                cur = con.execute(f'SELECT * FROM "{table}"')
                cols = [d[0] for d in cur.description]
            except Exception as exc:
                log(f"[skip] {table}: {exc}")
                continue

            def rows(cur=cur, cols=cols, table=table) -> Iterator[dict[str, Any]]:
                ordinal = 0
                while True:
                    batch = cur.fetchmany(5000)
                    if not batch:
                        break
                    for rec in batch:
                        yield _envelope("si_duckdb", f"si.duckdb#{table}",
                                        ordinal, dict(zip(cols, rec)))
                        ordinal += 1

            _emit("si_duckdb", name, rows(), log)
    finally:
        con.close()
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- X cache

def extract_x_cache(log) -> None:
    """pr-agent 与 pr-agent-prod 的 apify_cache 是完全重复副本，按 sha256 去重。"""
    seen: set[str] = set()
    files: list[Path] = []
    for d in X_CACHE_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            files.append(f)

    def rows() -> Iterator[dict[str, Any]]:
        for f in files:
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            if not isinstance(data, list):
                data = [data]
            # 文件名形如 tweet_2026-09-28.json，取日期
            snapshot = "".join(ch for ch in f.stem if ch.isdigit() or ch == "-")
            for i, rec in enumerate(data):
                if not isinstance(rec, dict):
                    continue
                item = dict(rec)
                item["__snapshot_date"] = snapshot[:10] if len(snapshot) >= 10 else None
                yield _envelope("pr_agent_apify_cache", f.name, i, item)

    _emit("x_cache", "x_post", rows(), log)


# ---------------------------------------------------------------- probes

def _probe_rows(paths: list[Path], origin: str, snapshot: str) -> Iterator[dict[str, Any]]:
    for f in sorted(paths):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(data, list):
            data = [data]
        for i, rec in enumerate(data):
            if not isinstance(rec, dict):
                continue
            item = dict(rec)
            item["__snapshot_date"] = snapshot
            item["__src_name"] = f.name
            yield _envelope(origin, f.name, i, item)


def extract_ig(log) -> None:
    if not IG_PROBE.exists():
        log("[skip] IG probe 不存在")
        return
    data = json.loads(IG_PROBE.read_text())
    _emit("probe_ig", "instagram_post",
          (_envelope("probe_ig", IG_PROBE.name, i, dict(r))
           for i, r in enumerate(data) if isinstance(r, dict)), log)


def extract_tiktok_probe(log) -> None:
    if not TT_PROBE_DIR.exists():
        log("[skip] TikTok probe 不存在")
        return
    files = sorted(TT_PROBE_DIR.glob("raw_arm*.json"))
    _emit("probe_tiktok", "tiktok_video",
          _probe_rows(files, "probe_tiktok", "2026-09-19"), log)


def extract_youtube_probe(log) -> None:
    if not YT_PROBE_DIR.exists():
        log("[skip] YouTube probe 不存在")
        return
    files = sorted(YT_PROBE_DIR.glob("datasets/*.json"))
    _emit("probe_yt", "youtube_video",
          _probe_rows(files, "probe_yt", "2026-09-19"), log)


# ---------------------------------------------------------------- PMO

def extract_pmo(log) -> None:
    if not PMO_DIR.exists():
        log("[skip] PMO 不存在")
        return
    files = sorted(PMO_DIR.glob("*.json"))

    def rows() -> Iterator[dict[str, Any]]:
        for f in files:
            try:
                data = json.loads(f.read_text())
            except Exception as exc:
                # raw_L0056.json 已知损坏，跳过并记日志，不中止整批
                log(f"[warn] PMO 坏文件 {f.name}: {str(exc)[:80]}")
                continue
            if not isinstance(data, list):
                data = [data]
            for i, rec in enumerate(data):
                if not isinstance(rec, dict):
                    continue
                item = dict(rec)
                # content 可能是 JSON 字符串，解一层
                c = item.get("content")
                if isinstance(c, str):
                    try:
                        item["content"] = json.loads(c)
                    except Exception:
                        pass
                item["__snapshot_date"] = "2026-08-16"
                yield _envelope("pmo_snapshot", f.name, i, item)

    _emit("pmo", "collection_record", rows(), log)


# ---------------------------------------------------------------- desktop

def extract_amazon(log) -> None:
    if not AMAZON_XLSX.exists():
        log("[skip] Amazon xlsx 不存在")
        return
    import openpyxl
    wb = openpyxl.load_workbook(AMAZON_XLSX, read_only=True, data_only=True)
    ws = wb.active

    def rows() -> Iterator[dict[str, Any]]:
        assert ws is not None
        it = ws.iter_rows(values_only=True)
        header = next(it, None)
        if not header:
            return
        cols = [str(h).strip() if h is not None else f"col{i}"
                for i, h in enumerate(header)]
        ordinal = 0
        for rec in it:
            if rec is None or all(v is None for v in rec):
                continue
            yield _envelope("desktop_xlsx", AMAZON_XLSX.name, ordinal,
                            dict(zip(cols, rec)))
            ordinal += 1

    _emit("desktop", "amazon_review", rows(), log)
    wb.close()


def extract_products(log) -> None:
    if not PRODUCT_CSV.exists():
        log("[skip] 商品 CSV 不存在")
        return

    def rows() -> Iterator[dict[str, Any]]:
        with PRODUCT_CSV.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for i, rec in enumerate(reader):
                yield _envelope("desktop_csv", PRODUCT_CSV.name, i, dict(rec))

    _emit("desktop", "product_catalog", rows(), log)


# ---------------------------------------------------------------- main

SOURCES = {
    "si_duckdb": extract_si,
    "x_cache": extract_x_cache,
    "probe_ig": extract_ig,
    "probe_tiktok": extract_tiktok_probe,
    "probe_yt": extract_youtube_probe,
    "pmo": extract_pmo,
    "amazon": extract_amazon,
    "products": extract_products,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="all", choices=["all", *SOURCES])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    def log(msg: str) -> None:
        print(msg, flush=True)

    if args.list:
        for k, fn in SOURCES.items():
            print(f"{k:16} {fn.__name__}")
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    targets = SOURCES.items() if args.source == "all" else [(args.source, SOURCES[args.source])]
    failed = 0
    for name, fn in targets:
        log(f"--- {name}")
        try:
            fn(log)
        except Exception as exc:
            failed += 1
            log(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
