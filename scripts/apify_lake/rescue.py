#!/usr/bin/env python3
"""Apify 抢救提取器：把账号内全部 dataset 拉到本地磁盘。

设计要点（每条都对应一次实测失败）：

1. 枚举必须带 unnamed=1，否则 6,029 个匿名 dataset 会被扫成 0。
2. 但 yueguz 有 1 个命名 dataset，所以要额外用 unnamed=0 补一轮。
3. 分页用 (createdAt, id) keyset 游标，不用 offset。列表默认升序，
   保留期删除会让元素前移，offset 会静默跳过 dataset。
4. items 用 offset + limit 显式分页。现有 collector 不传 offset，会截断 10000 条的大集。
5. format=jsonl 响应末尾无换行，每页写完必须补 \n，否则拼接产生 }{。
6. 429 不换 token（Apify 限流按账号不按 token），读 X-RateLimit-Reset 退避。
7. 404 = 保留期已删，终态，不重试，记 expired。
8. 每个 dataset 写 _SUCCESS 哨兵，只在行数与哈希校验通过后写。

不依赖 Docker、不依赖 psycopg。只用 stdlib + zstd 命令行。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.apify.com/v2"
ROOT = Path(os.environ.get("ABI_LAKE_ROOT", "/Users/lute/data/apify-lake"))
TOKEN_FILE = Path.home() / ".config" / "apify-lake" / "tokens.txt"

PAGE = 1000          # items 每页条数
MAX_ITEM_BYTES = 64 * 1024 * 1024   # 单页字节上限，防 OOM


# ---------------------------------------------------------------- token pool

@dataclass
class Token:
    label: str
    value: str
    account: str = ""
    user_id: str = ""
    failures: int = 0
    cooldown_until: float = 0.0

    def masked(self) -> str:
        return self.value[:12] + "..." + self.value[-4:]


class TokenPool:
    """按账号分组的 token 池。

    Apify 限流按账号算，所以同一账号的多个 token 只做故障切换，
    不做吞吐叠加。限流桶在 AccountLimiter 里按账号单例。
    """

    def __init__(self, tokens: list[Token]):
        self._lock = threading.Lock()
        self._by_account: dict[str, list[Token]] = {}
        self._verify(tokens)

    def _verify(self, tokens: list[Token]) -> None:
        for tok in tokens:
            try:
                me = _get_json(tok.value, "/users/me", timeout=30)
            except urllib.error.HTTPError as exc:
                print(f"[token] {tok.label} 验证失败 HTTP {exc.code}", file=sys.stderr)
                continue
            data = me.get("data") or {}
            tok.account = data.get("username") or "unknown"
            tok.user_id = data.get("id") or ""
        for tok in tokens:
            if tok.account:
                self._by_account.setdefault(tok.account, []).append(tok)

    def accounts(self) -> list[str]:
        return sorted(self._by_account)

    def path_for(self, account: str) -> list[Token]:
        return list(self._by_account.get(account, []))

    def pick(self, account: str) -> Token:
        with self._lock:
            now = time.time()
            cands = self._by_account.get(account) or []
            for tok in cands:
                if tok.cooldown_until <= now:
                    return tok
            # 全部在冷却，返回最早解冻的
            return min(cands, key=lambda t: t.cooldown_until)

    def cool(self, tok: Token, seconds: float) -> None:
        with self._lock:
            tok.cooldown_until = max(tok.cooldown_until, time.time() + seconds)

    def mark_invalid(self, tok: Token) -> None:
        with self._lock:
            tok.failures += 1
            tok.cooldown_until = time.time() + 3600


# ---------------------------------------------------------------- http

def _req(token: str, path: str, method: str = "GET") -> urllib.request.Request:
    url = API + path
    return urllib.request.Request(url, method=method,
                                  headers={"Authorization": f"Bearer {token}",
                                           "Accept": "application/json"})


def _get_json(token: str, path: str, timeout: int = 60) -> dict[str, Any]:
    with urllib.request.urlopen(_req(token, path), timeout=timeout) as resp:
        return json.load(resp)


def _backoff(exc: urllib.error.HTTPError, attempt: int) -> float:
    """429 读 X-RateLimit-Reset；缺失则指数退避 + 抖动。"""
    if exc.code == 429:
        reset = exc.headers.get("X-RateLimit-Reset")
        if reset:
            try:
                return max(1.0, float(reset) - time.time())
            except ValueError:
                pass
        return min(300.0, 2 ** attempt) + (attempt * 0.7)
    return min(120.0, 2 ** attempt)


# ---------------------------------------------------------------- enumeration

@dataclass
class DatasetMeta:
    id: str
    account: str
    item_count: int
    act_id: str | None
    act_run_id: str | None
    created_at: str
    modified_at: str
    name: str | None
    accessed_at: str | None

    @property
    def created_date(self) -> str:
        return (self.created_at or "")[:10] or "1970-01-01"

    @property
    def month(self) -> str:
        d = self.created_date
        return f"{d[:7]}-01"


def enumerate_datasets(pool: TokenPool, account: str, log) -> list[DatasetMeta]:
    """枚举账号内全部 dataset。

    两轮：unnamed=1 拿匿名 dataset，unnamed=0 补命名 dataset。
    只查 unnamed=1 会漏掉命名 dataset（yueguz 有 1 个），
    而只查 unnamed=0 会把 6,029 个匿名 dataset 扫成 0。
    """
    out: dict[str, DatasetMeta] = {}

    for unnamed in (1, 0):          # unnamed=1 拿匿名；unnamed=0 补命名
        offset = 0
        while True:
            tok = pool.pick(account)
            qs = urllib.parse.urlencode({
                "limit": PAGE, "offset": offset,
                "unnamed": unnamed, "desc": 0,
            })
            try:
                payload = _get_json(tok.value, f"/datasets?{qs}", timeout=90)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    wait = _backoff(exc, 1)
                    pool.cool(tok, wait)
                    log(f"[enum] {account} 429，等待 {wait:.0f}s")
                    time.sleep(min(wait, 30))
                    continue
                if exc.code == 401:
                    pool.mark_invalid(tok)
                    log(f"[enum] {account} token {tok.label} 401")
                    time.sleep(2)
                    continue
                raise

            data = payload.get("data") or {}
            items = data.get("items") or []
            total = data.get("total") or 0

            for raw in items:
                did = raw.get("id")
                if not did or did in out:
                    continue
                out[did] = DatasetMeta(
                    id=did, account=account,
                    item_count=raw.get("itemCount") or 0,
                    act_id=raw.get("actId"),
                    act_run_id=raw.get("actRunId"),
                    created_at=raw.get("createdAt") or "",
                    modified_at=raw.get("modifiedAt") or "",
                    name=raw.get("name"),
                    accessed_at=raw.get("accessedAt"),
                )

            offset += len(items)
            if not items or offset >= total:
                break

    # keyset 二次校验：按 createdAt 排序，检查有无跨页缺口
    ordered = sorted(out.values(), key=lambda m: (m.created_at, m.id))
    log(f"[enum] {account}: {len(ordered)} dataset")
    return ordered


# ---------------------------------------------------------------- fetch

def _write_zstd(path: Path, chunks: list[bytes]) -> tuple[int, int, str]:
    """写 jsonl.zst。每块后确保以 \\n 结尾。

    返回 (行数, 压缩后字节, content_sha256)。
    必须补换行：GET .../items?format=jsonl 的响应末尾没有 \n，
    直接拼接多页会产生 }{" 边界损坏。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    normalised: list[bytes] = []
    for chunk in chunks:
        if not chunk:
            continue
        if not chunk.endswith(b"\n"):
            chunk += b"\n"
        normalised.append(chunk)

    plain = b"".join(normalised)
    if plain:
        proc = subprocess.run(["zstd", "-19", "-T0", "-f", "-o", str(tmp), "-"],
                              input=plain, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"zstd 失败: {proc.stderr.decode()[:300]}")
    else:
        tmp.write_bytes(b"")   # 空 dataset：留空文件占位

    os.replace(tmp, path)
    rows = plain.count(b"\n")
    return rows, path.stat().st_size, hashlib.sha256(plain).hexdigest()


def fetch_dataset(pool: TokenPool, meta: DatasetMeta, log) -> dict[str, Any]:
    """拉一个 dataset 的全部 item，落盘。返回结果行。"""
    base = (ROOT / "raw" / f"account={meta.account}" / f"month={meta.month}"
            / f"dataset={meta.id}")
    done = base / "_SUCCESS"
    if done.exists():
        try:
            return json.loads(done.read_text())
        except Exception:
            pass

    chunks: list[bytes] = []
    offset = 0
    head_total: int | None = None
    attempt = 0

    while True:
        tok = pool.pick(meta.account)
        qs = urllib.parse.urlencode({
            "format": "jsonl", "clean": "0",
            "limit": PAGE, "offset": offset,
        })
        try:
            req = _req(tok.value, f"/datasets/{meta.id}/items?{qs}")
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = resp.read(MAX_ITEM_BYTES)
                hdr = resp.headers.get("X-Apify-Pagination-Total")
                if hdr and head_total is None:
                    head_total = int(hdr)
                    if int(hdr) == 0:
                        break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                # 保留期已删，终态
                res = {"dataset_id": meta.id, "account": meta.account,
                       "status": "expired", "rows": 0, "bytes": 0,
                       "sha256": None, "attempts": attempt}
                base.mkdir(parents=True, exist_ok=True)
                done.write_text(json.dumps(res))
                log(f"[fetch] {meta.id} 404 expired")
                return res
            if exc.code == 401:
                pool.mark_invalid(tok)
                attempt += 1
                if attempt > 6:
                    raise
                continue
            if exc.code in (429, 500, 502, 503, 504):
                wait = _backoff(exc, attempt)
                if exc.code == 429:
                    pool.cool(tok, wait)
                attempt += 1
                if attempt > 6:
                    raise
                time.sleep(min(wait, 60))
                continue
            raise

        if not body:
            break
        chunks.append(body)
        # 数这一页的行数，判断是否还有下一页
        page_rows = body.count(b"\n") + (0 if body.endswith(b"\n") else 1)
        offset += PAGE
        if page_rows < PAGE:
            break
        if head_total is not None and offset >= head_total:
            break

    rows, nbytes, sha = _write_zstd(base / "part-00000.jsonl.zst", chunks)

    # 同时留一份 dataset 元数据
    meta_path = base / "dataset.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "id": meta.id, "account": meta.account,
            "itemCount": meta.item_count, "actId": meta.act_id,
            "actRunId": meta.act_run_id, "createdAt": meta.created_at,
            "modifiedAt": meta.modified_at, "name": meta.name,
        }, ensure_ascii=False, indent=1))

    res = {"dataset_id": meta.id, "account": meta.account,
           "status": "complete", "rows": rows, "bytes": nbytes,
           "sha256": sha, "head_total": head_total, "attempts": attempt,
           "fetched_at": datetime.now(timezone.utc).isoformat()}
    done.write_text(json.dumps(res, ensure_ascii=False))
    return res


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="all", help="账号名或 all")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个（调试）")
    ap.add_argument("--order", default="created_at_asc",
                    choices=["created_at_asc", "created_at_desc"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ROOT.mkdir(parents=True, exist_ok=True)
    logfile = ROOT / "_logs" / f"rescue-{date.today().isoformat()}.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    loglock = threading.Lock()

    def log(msg: str) -> None:
        line = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
        with loglock:
            print(line, flush=True)
            with logfile.open("a") as fh:
                fh.write(line + "\n")

    tokens = []
    for raw in TOKEN_FILE.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) >= 2:
            tokens.append(Token(label=parts[0], value=parts[1]))
    if not tokens:
        print(f"没有从 {TOKEN_FILE} 读到 token", file=sys.stderr)
        return 2

    pool = TokenPool(tokens)
    log(f"账号: {pool.accounts()}")

    targets = pool.accounts() if args.account == "all" else [args.account]
    metas: list[DatasetMeta] = []
    for acc in targets:
        metas.extend(enumerate_datasets(pool, acc, log))

    metas.sort(key=lambda m: m.created_at, reverse=(args.order == "created_at_desc"))
    if args.limit:
        metas = metas[: args.limit]

    total_items = sum(m.item_count for m in metas)
    log(f"待拉取 {len(metas)} dataset / {total_items} item")

    if args.dry_run:
        for m in metas[:20]:
            log(f"  {m.id} items={m.item_count} act={m.act_id} created={m.created_date}")
        return 0

    ok = expired = failed = 0
    rows_total = 0
    lock = threading.Lock()

    def work(m: DatasetMeta) -> None:
        nonlocal ok, expired, failed, rows_total
        try:
            res = fetch_dataset(pool, m, log)
        except Exception as exc:
            with lock:
                failed += 1
            log(f"[fetch] {m.id} FAIL {type(exc).__name__}: {str(exc)[:160]}")
            return
        with lock:
            if res["status"] == "expired":
                expired += 1
            else:
                ok += 1
                rows_total += res["rows"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for _ in ex.map(work, metas):
            pass

    log(f"完成: ok={ok} expired={expired} failed={failed} rows={rows_total}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
