"""离线审计：每个 Apify 端点的 base_input 是否满足其 Actor 的 inputSchema？

只读公开的 actor 元数据（GET /v2/acts/<user~name>/builds/default 的 inputSchema），
**不产生 run、不消耗额度**。用法：

    python scripts/audit_apify_inputs.py

判定三类问题：
1. 缺必填键（missing required）—— 端点必然 400；
2. editor 形状不符 —— requestListSources 要 [{"url": ...}]，stringList 要裸字符串数组；
3. 键名不在 schema 里 —— additionalProperties:false 的 Actor 会整单 400，
   其余 Actor 会静默忽略（限流/数量意图落空）。
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

ROUTE = pathlib.Path(__file__).resolve().parents[1] / (
    "apps/api/src/data_intelligence_hub/api/routes/quick_collect.py"
)
META_KEYS = {"maxItems", "max_items", "max_total_charge_usd", "run_timeout_seconds"}


def get(url: str) -> dict:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=30
    ) as r:
        return json.loads(r.read().decode())


def load_table() -> dict[str, tuple[str, dict]]:
    src = ROUTE.read_text(encoding="utf-8")
    block = src.split(
        "_APIFY_ENDPOINT_DEFAULTS: dict[str, tuple[str, dict[str, Any]]] = {", 1
    )[1]
    block = block.split("\n}\n", 1)[0]
    # eval the literal body safely enough: wrap into a dict expression
    text = "{\n" + block + "\n}"
    return eval(text, {"__builtins__": {}}, {})  # noqa: S307


def schema_for(actor: str) -> dict | None:
    path = actor.replace("/", "~")
    try:
        data = get(f"https://api.apify.com/v2/acts/{path}/builds/default")["data"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    raw = data.get("inputSchema")
    return json.loads(raw) if isinstance(raw, str) else raw


def check(base: dict, schema: dict) -> list[str]:
    problems: list[str] = []
    props = schema.get("properties") or {}
    strict = schema.get("additionalProperties") is False
    required = list(schema.get("required") or [])
    missing = [k for k in required if k not in base]
    if missing:
        prefill = {
            k: props.get(k, {}).get("prefill")
            for k in missing
            if props.get(k, {}).get("prefill") is not None
        }
        problems.append(
            f"missing required: {missing} prefill={json.dumps(prefill, ensure_ascii=False)[:160]}"
        )
    for key, value in base.items():
        spec = props.get(key)
        if spec is None:
            problems.append(
                f"unknown key: {key}{' (FATAL: additionalProperties=false)' if strict else ' (ignored by actor)'}"
            )
            continue
        editor = spec.get("editor")
        stype = spec.get("type")
        if editor == "requestListSources" and isinstance(value, list):
            if any(not isinstance(v, dict) or "url" not in v for v in value):
                problems.append(
                    f"{key}: editor=requestListSources 需要 [{{'url': ...}}]"
                )
        if editor == "stringList" and isinstance(value, list):
            if any(not isinstance(v, str) for v in value):
                problems.append(f"{key}: editor=stringList 需要裸字符串数组")
        if (
            stype == "integer"
            and isinstance(value, int)
            and not isinstance(value, bool)
        ):
            lo, hi = spec.get("minimum"), spec.get("maximum")
            if lo is not None and value < lo:
                problems.append(f"{key}={value} < minimum {lo}")
            if hi is not None and value > hi:
                problems.append(f"{key}={value} > maximum {hi}")
        enum = spec.get("enum")
        if enum and value not in enum:
            problems.append(f"{key}={value!r} 不在 enum 内")
    return problems


def main() -> None:
    table = load_table()
    cache: dict[str, dict | None] = {}
    bad = 0
    for endpoint in sorted(table):
        actor, base = table[endpoint]
        if actor not in cache:
            try:
                cache[actor] = schema_for(actor)
            except Exception as exc:  # noqa: BLE001
                cache[actor] = None
                print(f"{endpoint:44s} schema ERROR {exc}")
                continue
        schema = cache[actor]
        if schema is None:
            print(f"{endpoint:44s} !! Actor 不存在或无数输入 schema: {actor}")
            bad += 1
            continue
        problems = check(base, schema)
        if problems:
            bad += 1
            print(f"{endpoint:44s} {actor}")
            for p in problems:
                print(f"      - {p}")
    print(f"\nchecked {len(table)} endpoints, {bad} with problems")


if __name__ == "__main__":
    main()
