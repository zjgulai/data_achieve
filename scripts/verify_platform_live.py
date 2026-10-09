"""对生产采集平台做可续跑的 live 全量验证。

对 catalog 中每个非 disabled 端点发起一次 `POST /api/quick-collect`
（label=`[test] <endpoint_type>`），使 `/api/collectors/docs` 与
`/api/platform-packages/providers/status` 反映真实测试结果；同时输出
可机器读取的 JSON 报告与人类可读的 Markdown 摘要，并对失败做分类。

用法：
    python scripts/verify_platform_live.py \
        --base-url https://scrapy.luteos.com \
        --project-id <uuid> [--group tikhub_social] [--only a,b] \
        [--resume] [--delay 1.0] [--max-requests 50] [--dry-run]

设计要点：
- 只发 `label="<prefix> <endpoint_type>"`，与 /api/collectors/docs 的匹配规则一致。
- 断点续跑：checkpoint 文件记录端点 → 状态，`--resume` 跳过已 ok 的端点。
- 失败分类 failure_class 供后续分流修复与坑点沉淀。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector_demo_params import DEMO_PARAMS  # noqa: E402

DEFAULT_REPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports",
    "live-sweep",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int | None, dict[str, Any]]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")[:500]
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"detail": raw}
    except Exception as exc:  # noqa: BLE001
        return None, {"error": str(exc)}


def http_get_json(url: str, timeout: float = 30.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ── failure classification ────────────────────────────────────────────────────
_CONTAINER_MARKERS = (
    "executable doesn't exist",
    "playwright install",
    "browser_type.launch",
    "chromium",
    "no such file or directory: 'chromium'",
    "not installed",
    "not been installed",
    "missingdependencyexception",
    "playwright_not_installed",
    "browser-use not installed",
    "tor is not",
)
_PROXY_MARKERS = (
    "proxy",
    "connection refused",
    "tunnel connection failed",
    "socks",
    "connection failed",
    "http_connection_failed",
)
_TIMEOUT_MARKERS = ("timed out", "timeout", "read timed out")
_CONFIG_MARKERS = (
    "_missing",
    "not set",
    "未配置",
    "api key",
    "api_key",
    "token is not",
    "no credentials",
    "credentials",
    "is not configured",
    "not configured",
    "no twitter accounts",
    "requires anycrawl",
)
_PARAMS_MARKERS = (
    "config field is required",
    "invalid-input",
    "string_too_short",
    "missing",
    "field required",
)


def classify(http_status: int | None, resp: dict[str, Any]) -> tuple[str, str]:
    """返回 (failure_class, human_note)。"""
    if http_status is None:
        return "request_error", str(resp.get("error", ""))[:200]

    lowered = json.dumps(resp, ensure_ascii=False).lower()

    if http_status == 400:
        detail = str(resp.get("detail", "")).lower()
        if any(m in detail for m in _CONFIG_MARKERS):
            return "config_gated", str(resp.get("detail", ""))[:200]
        return "params_invalid", str(resp.get("detail", ""))[:200]
    if http_status in (401, 403, 404, 422):
        return "upstream_4xx", str(resp.get("detail", resp))[:200]
    if http_status == 429:
        return "upstream_rate_limit", str(resp.get("detail", ""))[:200]
    if http_status >= 500:
        detail = str(resp.get("detail", "")).lower()
        if any(m in detail for m in _CONFIG_MARKERS):
            return "config_gated", str(resp.get("detail", ""))[:200]
        return "upstream_5xx", str(resp.get("detail", ""))[:200]

    # 201 success path
    status = str(resp.get("status", "")).lower()
    records = resp.get("records_count") or 0
    err = str(resp.get("error_message") or "")
    if status in ("success", "ok", "completed"):
        if records and int(records) > 0:
            return "ok", ""
        return "empty_records", err[:200] or "succeeded but returned 0 records"
    if status in ("disabled",):
        return "disabled", err[:200]
    # failed / error status
    if any(m in lowered for m in _CONFIG_MARKERS):
        return "config_gated", err[:200]
    if any(m in lowered for m in _CONTAINER_MARKERS):
        return "container_missing", err[:200]
    if any(m in lowered for m in _PROXY_MARKERS):
        return "network_proxy", err[:200]
    if "apify_run_failed" in lowered:
        return "actor_failed", err[:200]
    if any(m in lowered for m in _TIMEOUT_MARKERS):
        return "timeout", err[:200]
    if any(m in lowered for m in _PARAMS_MARKERS):
        return "params_invalid", err[:200]
    if "429" in lowered or "rate limit" in lowered:
        return "upstream_rate_limit", err[:200]
    upstream = re.search(r"upstream returned (\d{3})", lowered)
    if upstream:
        code = int(upstream.group(1))
        if code == 429:
            return "upstream_rate_limit", err[:200]
        if 400 <= code < 500:
            return "upstream_4xx", err[:200]
        if code >= 500:
            return "upstream_5xx", err[:200]
    if "http_status_error" in lowered:
        return "upstream_4xx", err[:200]
    return "unknown", (err or lowered)[:200]


# ── catalogue ─────────────────────────────────────────────────────────────────
def load_endpoints(catalog: dict[str, Any], include_disabled: bool) -> list[dict[str, Any]]:
    """非 disabled 端点，按 endpoint_type 去重（同一端点可出现在多个 group 视图）。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in catalog.get("collectors", []):
        for ep in group.get("endpoints", []):
            if ep.get("status") == "disabled" and not include_disabled:
                continue
            etype = ep["endpoint_type"]
            if etype in seen:
                continue
            seen.add(etype)
            out.append(
                {
                    "endpoint_type": etype,
                    "label": ep.get("label", ""),
                    "platform": ep.get("platform", ""),
                    "collector_type": group.get("collector_type", ""),
                    "status": ep.get("status", ""),
                }
            )
    return out


def checkpoint_path(report_dir: str, key: str) -> str:
    digest = hashlib.sha1(key.encode()).hexdigest()[:12]
    return os.path.join(report_dir, f"checkpoint-{digest}.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live-verify all collector endpoints")
    parser.add_argument("--base-url", default="https://scrapy.luteos.com")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--group", default="", help="Only this collector_type")
    parser.add_argument("--only", default="", help="Comma-separated endpoint_types")
    parser.add_argument("--label-prefix", default="[test]")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=6, help="Parallel requests")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-requests", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()

    os.makedirs(args.report_dir, exist_ok=True)

    catalog = http_get_json(f"{args.base_url}/api/collectors/catalog")
    if "error" in catalog:
        print(f"ERROR: cannot fetch catalog: {catalog['error']}", file=sys.stderr)
        return 1

    endpoints = load_endpoints(catalog, args.include_disabled)
    if args.group:
        endpoints = [e for e in endpoints if e["collector_type"] == args.group]
    if args.only:
        wanted = {t.strip() for t in args.only.split(",") if t.strip()}
        endpoints = [e for e in endpoints if e["endpoint_type"] in wanted]

    ckpt_file = checkpoint_path(args.report_dir, f"{args.base_url}|{args.group}|{args.only}")
    checkpoint: dict[str, Any] = {}
    if args.resume and os.path.exists(ckpt_file):
        checkpoint = json.loads(open(ckpt_file).read())

    if args.dry_run:
        planned = [e for e in endpoints if not (args.resume and checkpoint.get(e["endpoint_type"], {}).get("failure_class") == "ok")]
        print(f"DRY-RUN: would test {len(planned)}/{len(endpoints)} endpoints")
        for e in planned:
            has = "params" if e["endpoint_type"] in DEMO_PARAMS else "NO-PARAMS"
            print(f"  {e['endpoint_type']:46} [{e['collector_type']}] {has}")
        return 0

    if not args.project_id:
        print("ERROR: --project-id is required (unless --dry-run)", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    lock = threading.Lock()
    counter = {"done": 0}

    planned: list[dict[str, Any]] = []
    for ep in endpoints:
        etype = ep["endpoint_type"]
        if args.resume and checkpoint.get(etype, {}).get("failure_class") == "ok":
            print(f"{etype} ... SKIP (already ok)")
            continue
        planned.append(ep)
    if args.max_requests:
        planned = planned[: args.max_requests]

    def run_one(ep: dict[str, Any]) -> None:
        etype = ep["endpoint_type"]
        params = DEMO_PARAMS.get(etype, {})
        payload = {
            "project_id": args.project_id,
            "endpoint_type": etype,
            "params": params,
            "label": f"{args.label_prefix} {etype}",
        }
        started = time.time()
        http_status, resp = http_post_json(
            f"{args.base_url}/api/quick-collect", payload, args.timeout
        )
        duration_ms = int((time.time() - started) * 1000)

        if http_status is not None and 200 <= http_status < 300:
            run_status = str(resp.get("status", ""))
            records = resp.get("records_count") or 0
            error_message = str(resp.get("error_message") or "")
        else:
            run_status = "request_error"
            records = 0
            error_message = str(resp.get("detail", resp.get("error", "")))[:300]

        failure_class, note = classify(http_status, resp)
        row = {
            "endpoint_type": etype,
            "platform": ep["platform"],
            "collector_type": ep["collector_type"],
            "catalog_status": ep["status"],
            "http_status": http_status,
            "run_status": run_status,
            "outcome": "success" if failure_class == "ok" else run_status,
            "failure_class": failure_class,
            "records_count": records,
            "error_message": error_message,
            "params_used": params,
            "run_id": str(resp.get("task_run_id", "") or ""),
            "duration_ms": duration_ms,
            "checked_at": now_iso(),
        }
        with lock:
            results.append(row)
            checkpoint[etype] = {"failure_class": failure_class, "at": row["checked_at"]}
            with open(ckpt_file, "w") as fh:
                json.dump(checkpoint, fh, ensure_ascii=False, indent=0)
            counter["done"] += 1
            flag = "OK " if failure_class == "ok" else "!! "
            print(
                f"[{counter['done']:3}/{len(planned)}] {flag}{etype} -> {failure_class} "
                f"(records={records}, http={http_status}, {duration_ms}ms) {note[:70]}",
                flush=True,
            )
        if args.delay:
            time.sleep(args.delay)

    with cf.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        list(pool.map(run_one, planned))

    report = {
        "base_url": args.base_url,
        "project_id": args.project_id,
        "generated_at": now_iso(),
        "group": args.group,
        "only": args.only,
        "total": len(endpoints),
        "tested": len(results),
        "summary": dict(Counter(r["failure_class"] for r in results)),
        "results": results,
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(args.report_dir, f"{ts}.json")
    json.dump(report, open(out_path, "w"), ensure_ascii=False, indent=2)
    json.dump(report, open(os.path.join(args.report_dir, "latest.json"), "w"), ensure_ascii=False, indent=2)

    lines = [
        f"# Live sweep {report['generated_at']}",
        "",
        f"- base_url: {args.base_url}",
        f"- tested: {report['tested']} / {report['total']}",
        "",
        "| failure_class | count |",
        "|---|---|",
    ]
    for k, v in sorted(report["summary"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 非 ok 端点", "", "| endpoint_type | group | failure_class | note |", "|---|---|---|---|"]
    for r in results:
        if r["failure_class"] != "ok":
            note = (r["error_message"] or "").replace("|", "/")[:120]
            lines.append(f"| `{r['endpoint_type']}` | {r['collector_type']} | {r['failure_class']} | {note} |")
    open(os.path.join(args.report_dir, "latest.md"), "w").write("\n".join(lines) + "\n")

    print()
    print(f"Report: {out_path}")
    print(f"Summary: {report['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
