"""批量测试所有采集 API 端点。

每个 endpoint 发起一次 quick_collect（label=[test] <endpoint_type>），
结果写入 task_runs，/api/collector-docs 会从中读取最新测试结果。

用法：
    python test_all_collectors.py --base-url http://192.168.204.230 --project-id <uuid>
    python test_all_collectors.py --base-url http://127.0.0.1:8080 --project-id <uuid> --dry-run
    python test_all_collectors.py --group tikhub  # 只测某组

默认测试参数（每个 provider 用最简单的无敏感数据参数）：
- TikHub / Apify：触发并记录 key 是否配置（key 未配置会 fail，但说明配置状态）
- GitHub / RSS / Web：真实调用，期望成功
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collector_demo_params import DEMO_PARAMS  # noqa: E402  (shared single source)


def post_json(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)}


def get_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test all collector endpoints via quick_collect")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--group", default="", help="Only test endpoints in this group")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    args = parser.parse_args()

    catalog = get_json(f"{args.base_url}/api/collectors/catalog")
    if "error" in catalog:
        print(f"ERROR: Cannot fetch catalog: {catalog}", file=sys.stderr)
        sys.exit(1)

    endpoints = []
    for group in catalog.get("collectors", []):
        if args.group and group["collector_type"] != args.group:
            continue
        for ep in group["endpoints"]:
            if ep.get("status") == "disabled":
                continue
            endpoints.append(ep)

    print(f"Testing {len(endpoints)} endpoints (dry_run={args.dry_run})")
    print()

    results = []
    for i, ep in enumerate(endpoints, 1):
        ep_type = ep["endpoint_type"]
        params = DEMO_PARAMS.get(ep_type, {})
        label = f"[test] {ep_type}"

        print(f"[{i:3d}/{len(endpoints)}] {ep_type} ...", end=" ", flush=True)

        if args.dry_run:
            print("SKIP (dry-run)")
            continue

        payload = {
            "project_id": args.project_id,
            "endpoint_type": ep_type,
            "params": params,
            "label": label,
            "save_records": False,
        }

        resp = post_json(f"{args.base_url}/api/quick-collect", payload)

        if "error" in resp:
            print(f"ERROR {resp.get('error')} {resp.get('detail','')[:80]}")
            results.append({"endpoint_type": ep_type, "outcome": "request_error", "detail": str(resp)})
        else:
            run_status = resp.get("status", "?")
            records = resp.get("records_count", 0)
            err = (resp.get("error_message") or "")[:80]
            flag = "✓" if run_status == "success" else "✗"
            print(f"{flag} {run_status} records={records} {err}")
            results.append({
                "endpoint_type": ep_type,
                "outcome": run_status,
                "run_id": str(resp.get("task_run_id", "")),
                "records_count": records,
                "error": err,
            })

        if args.delay:
            time.sleep(args.delay)

    print()
    if results:
        ok = sum(1 for r in results if r.get("outcome") == "success")
        print(f"Done: {ok}/{len(results)} success")


if __name__ == "__main__":
    main()
