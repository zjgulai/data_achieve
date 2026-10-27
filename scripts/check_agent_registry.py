#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/check_agent_registry.py
# cd apps/api && uv run python ../../scripts/check_agent_registry.py --json
#
# 只读守卫：把 configs/agents/registry.json 与真实代码、compose、提示词文件对账。
# 不联网，不写任何文件。
#
# 检查项：
#   1. 每个登记的 Agent，entry / health 路由必须在 FastAPI app 里真实存在
#      （防止「声明了但没挂载」——2026-10 曾有 25 个端点因此 404）。
#   2. env_keys 必须出现在 compose 的 api environment 里
#      （防止「只写 .env.production、不进容器」这个反复踩的坑）。
#   3. 提示词 sha256 必须与文件一致，且文件不含 NUL 字节
#      （本环境 Write 工具会留 4096 字节尾洞，NUL 会让容器内 Python 直接报错）。
#   4. agents/ 下每个 Agent 目录都必须登记，防止新增 Agent 悄悄绕过台账。
#
# 退出码：0 通过，1 有问题，2 输入错误。

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

REGISTRY_PATH = ROOT / "configs/agents/registry.json"
COMPOSE_PATH = ROOT / "configs/deploy/scrapy/docker-compose.yml"
AGENTS_DIR = ROOT / "apps/api/src/data_intelligence_hub/agents"

REPORT_SCHEMA_VERSION = "agent-registry-report.v1"
REGISTRY_SCHEMA = "agent-registry.v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# agents/ 下不是 Agent 自身的条目。
NON_AGENT_ENTRIES = {"__init__.py", "__pycache__", "prompt_loader.py"}


def _compose_api_env_keys(path: Path) -> set[str]:
    """取 compose 里 api 服务 environment 段的键名。"""
    text = path.read_text(encoding="utf-8")
    # 定位 api 服务块：从 "  api:" 到下一个同级服务键。
    match = re.search(r"\n  api:\n(.*?)(?=\n  [a-zA-Z0-9_-]+:\n|\Z)", text, re.S)
    if not match:
        raise SystemExit(f"输入错误：{path} 里找不到 api 服务块")
    block = match.group(1)
    # environment 段：从 "    environment:" 起，到下一个 4 空格缩进的键为止。
    env_match = re.search(
        r"\n    environment:\n(.*?)(?=\n    [a-zA-Z_]+:\n|\Z)", block, re.S
    )
    if not env_match:
        raise SystemExit(f"输入错误：{path} 的 api 服务里找不到 environment 段")
    return set(re.findall(r"^ {6}([A-Z][A-Z0-9_]*):", env_match.group(1), re.M))


def _registered_agent_dirs() -> set[str]:
    return {
        entry.name
        for entry in AGENTS_DIR.iterdir()
        if entry.is_dir() and entry.name not in NON_AGENT_ENTRIES
    }


def _prompt_problems(agent_id: str, prompt: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    rel = prompt.get("file")
    expected = prompt.get("sha256")
    if not rel or not expected:
        return [f"{agent_id}: prompt.file 与 prompt.sha256 都必须填写"]
    if not SHA256_PATTERN.match(expected):
        problems.append(f"{agent_id}: prompt.sha256 不是 64 位十六进制")
    path = ROOT / rel
    if not path.is_file():
        return [f"{agent_id}: 提示词文件不存在 {rel}"]
    raw = path.read_bytes()
    if b"\x00" in raw:
        problems.append(
            f"{agent_id}: 提示词文件含 NUL 字节（{rel}，疑似 4096 字节尾洞）"
        )
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        problems.append(
            f"{agent_id}: 提示词指纹不符，登记 {expected[:12]}… 实际 {actual[:12]}…；"
            f"改动提示词后请同步更新 registry.json（或确认改动是否该进生产）"
        )
    return problems


def check() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        raise SystemExit(f"输入错误：找不到台账 {REGISTRY_PATH}")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    problems: list[str] = []
    if registry.get("schema_version") != REGISTRY_SCHEMA:
        problems.append(
            f"schema_version 应为 {REGISTRY_SCHEMA}，实际 {registry.get('schema_version')!r}"
        )

    agents = registry.get("agents") or []
    if not agents:
        problems.append("台账里没有任何 Agent")

    env_keys = _compose_api_env_keys(COMPOSE_PATH)

    # 延迟导入：只有在真跑校验时才需要构造 app。
    from data_intelligence_hub.main import create_app

    app = create_app()
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    seen_ids: set[str] = set()
    for agent in agents:
        agent_id = agent.get("id")
        if not agent_id:
            problems.append("存在缺少 id 的 Agent 条目")
            continue
        if agent_id in seen_ids:
            problems.append(f"{agent_id}: id 重复")
        seen_ids.add(agent_id)

        for field in ("display", "owner", "status", "module"):
            if not agent.get(field):
                problems.append(f"{agent_id}: 缺少 {field}")

        for key in ("entry", "health"):
            spec = agent.get(key) or {}
            method = str(spec.get("method", "")).upper()
            path = spec.get("path")
            if not method or not path:
                problems.append(f"{agent_id}: {key} 需要 method 与 path")
                continue
            if (path, method) not in routes:
                problems.append(
                    f"{agent_id}: {key} 声明的 {method} {path} 在 app 里不存在"
                    f"（声明了但没挂载？）"
                )

        for key in agent.get("env_keys") or []:
            if key not in env_keys:
                problems.append(
                    f"{agent_id}: env 键 {key} 不在 compose 的 api environment 里"
                    f"（只写 .env.production 不会进容器）"
                )

        for key in agent.get("readiness_env") or []:
            if key not in (agent.get("env_keys") or []):
                problems.append(f"{agent_id}: readiness_env 的 {key} 未列入 env_keys")

        problems.extend(_prompt_problems(agent_id, agent.get("prompt") or {}))

    unregistered = sorted(_registered_agent_dirs() - seen_ids)
    for name in unregistered:
        problems.append(
            f"{name}: agents/ 下存在该 Agent 目录，但台账未登记"
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "registry": str(REGISTRY_PATH.relative_to(ROOT)),
        "agent_count": len(agents),
        "agent_ids": sorted(seen_ids),
        "compose_env_key_count": len(env_keys),
        "problems": problems,
        "ok": not problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Agent 台账与代码/compose/提示词的一致性")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    report = check()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Agent 台账：{report['agent_count']} 个（{', '.join(report['agent_ids'])}）")
        print(f"compose api env 键：{report['compose_env_key_count']} 个")
        if report["ok"]:
            print("检查结果：通过")
        else:
            print(f"检查结果：{len(report['problems'])} 个问题")
            for item in report["problems"]:
                print(f"  - {item}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
