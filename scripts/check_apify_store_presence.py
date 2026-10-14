"""月检：已接入 Apify actor 的 Store 页存在性 + 30 天成功率巡检。

匿名调 Store API（不产生 run、不耗额度）。两类告警：
1. delisted —— Store 查不到（amazon-bsr-scraper 式无声下架的前兆）；
2. ok% 下跌 —— 30 天成功率低于该 actor 接入时的基准 -8pt。

用法：python scripts/check_apify_store_presence.py
基准与 actor 清单从 quick_collect 的 _APIFY_ENDPOINT_DEFAULTS 提取，无需手工维护。
"""
from __future__ import annotations

import ast
import json
import pathlib
import time
import urllib.request

ROUTE = pathlib.Path(__file__).resolve().parents[1] / (
    "apps/api/src/data_intelligence_hub/api/routes/quick_collect.py"
)
# 换主力时的基准快照（2026-10-14 实测）；未列出的用 -8pt 相对告警线 90%
BASELINE_OK_PCT = {
    "harshmaur/reddit-scraper": 97.7,
    "data_xplorer/google-trends-fast-scraper": 99.5,
    "trudax/reddit-scraper-lite": 87.2,
    "marketplace-scrapers/amazon-bsr-scraper": 92.5,
}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def load_actors() -> set[str]:
    src = ROUTE.read_text(encoding="utf-8")
    block = src.split("_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {", 1)[1]
    block = block.split("\n}\n", 1)[0]
    table = ast.literal_eval("{\n" + block + "\n}")
    return {actor for actor, _ in table.values()}


def main() -> None:
    actors = sorted(load_actors())
    print(f"checking {len(actors)} actors ...")
    delisted: list[str] = []
    degraded: list[tuple[str, float, float]] = []  # actor, ok%, baseline
    for actor in actors:
        un, name = actor.split("/", 1)
        try:
            items = get(
                "https://api.apify.com/v2/store?"
                + urllib.parse.urlencode({"username": un, "name": name, "limit": 1})
            )["data"]["items"]
        except Exception as exc:  # noqa: BLE001
            print(f"  LOOKUP-FAIL {actor}: {exc}")
            continue
        if not items:
            delisted.append(actor)
            print(f"  DELISTED  {actor}")
            continue
        st = items[0].get("stats", {}).get("publicActorRunStats30Days") or {}
        total = st.get("TOTAL") or 0
        ok_pct = round(100 * st.get("SUCCEEDED", 0) / total, 1) if total else None
        base = BASELINE_OK_PCT.get(actor, 90.0)
        if ok_pct is not None and ok_pct < base - 8:
            degraded.append((actor, ok_pct, base))
            print(f"  DEGRADED  {actor}: ok%={ok_pct} (baseline {base})")
        time.sleep(0.1)
    print(f"\nchecked {len(actors)} | delisted: {len(delisted)} | degraded: {len(degraded)}")
    if delisted or degraded:
        raise SystemExit(1)


if __name__ == "__main__":
    import urllib.parse

    main()
