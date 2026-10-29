#!/usr/bin/env python3
"""从 endpoint_catalog / collectors 源码提取 actor → (platform, content_type) 归因表。

为什么要 AST 解析而不是 import：
1. 目录是路由函数内的局部列表字面量，import 拿不到。
2. import 该模块会初始化 FastAPI 路由与 settings，需要数据库与密钥，
   在离线装载环境里跑不起来。

输出 YAML：actor_id 或 owner/name → 候选列表。
一个 actor 对应多个端点时（实测 clockworks/tiktok-scraper 同时服务
post 与 account），装载器必须用 INPUT 或字段签名再判，不能取第一个。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COLLECTORS = REPO / "apps/api/src/data_intelligence_hub/api/routes/collectors.py"
CATALOG = REPO / "apps/api/src/data_intelligence_hub/collectors/endpoint_catalog.py"
OUT = Path(__file__).resolve().parent / "actor_map.json"

PROVIDER_RE = re.compile(r"Apify Actor \(([^)]+)\)")


def _kwarg(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def parse_collectors() -> list[dict[str, str | None]]:
    """抽出所有 CollectorEndpointMetadata(...) 调用。"""
    tree = ast.parse(COLLECTORS.read_text())
    rows: list[dict[str, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else "")
        if fname != "CollectorEndpointMetadata":
            continue
        provider = _kwarg(node, "provider")
        actor = None
        if provider:
            m = PROVIDER_RE.search(provider)
            if m:
                actor = m.group(1).strip()
        rows.append({
            "endpoint_type": _kwarg(node, "endpoint_type"),
            "platform": _kwarg(node, "platform"),
            "content_type": _kwarg(node, "content_type"),
            "provider": provider,
            "actor": actor,
            "method": _kwarg(node, "method"),
        })
    return rows


def parse_endpoint_defaults() -> dict[str, str]:
    """从 _APIFY_ENDPOINT_DEFAULTS 抽 endpoint_type → actor。"""
    tree = ast.parse(CATALOG.read_text())
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) and not isinstance(node, ast.Assign):
            continue
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and node.targets:
            t0 = node.targets[0]
            if isinstance(t0, ast.Name):
                target = t0.id
        if target != "_APIFY_ENDPOINT_DEFAULTS":
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        for k, v in zip(value.keys, value.values):
            if not isinstance(k, ast.Constant):
                continue
            if isinstance(v, ast.Tuple) and v.elts and isinstance(v.elts[0], ast.Constant):
                out[str(k.value)] = str(v.elts[0].value)
    return out


def main() -> int:
    rows = parse_collectors()
    defaults = parse_endpoint_defaults()

    # endpoint_type → 候选归因
    by_endpoint: dict[str, dict[str, str | None]] = {}
    for r in rows:
        et = r.get("endpoint_type")
        if et and r.get("method") == "apify":
            by_endpoint[et] = r

    # actor → 候选列表（用 endpoint 的 platform/content_type）
    by_actor: dict[str, list[dict[str, str | None]]] = {}
    for et, actor in defaults.items():
        meta = by_endpoint.get(et)
        if not meta:
            continue
        by_actor.setdefault(actor, []).append({
            "endpoint_type": et,
            "platform": meta.get("platform"),
            "content_type": meta.get("content_type"),
        })

    payload = {
        "generated_from": [str(COLLECTORS), str(CATALOG)],
        "endpoint_count": len(defaults),
        "actor_count": len(by_actor),
        "ambiguous_actors": {
            a: v for a, v in by_actor.items() if len(v) > 1
        },
        "actors": by_actor,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    print(f"endpoint: {len(defaults)}, actor: {len(by_actor)}")
    print(f"歧义 actor（多端点）: {len(payload['ambiguous_actors'])}")
    for a, v in list(payload["ambiguous_actors"].items())[:8]:
        kinds = sorted({f"{x['platform']}/{x['content_type']}" for x in v})
        print(f"  {a}: {len(v)} endpoints -> {kinds}")
    print(f"写出 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
