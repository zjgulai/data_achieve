"""加载 tool_catalog 的静态夹具。

夹具是只读数据文件。
加载器缓存结果，避免每次调用重复读盘。
文件缺失或格式错误时抛出明确异常，不返回空字典。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PRICE_BOOK_PATH = FIXTURES_DIR / "price_book_v1.json"
OUTPUT_SCHEMAS_PATH = FIXTURES_DIR / "output_schemas_v1.json"

PRICE_BOOK_SCHEMA_VERSION = "price_book.v1"
OUTPUT_SCHEMAS_SCHEMA_VERSION = "output_schemas.v1"


class ToolCatalogFixtureError(RuntimeError):
    """夹具缺失或格式无效。"""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    """读取一个 JSON 对象。路径不存在或内容无效时抛出异常。"""
    if not path.is_file():
        raise ToolCatalogFixtureError(f"缺少{label}：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolCatalogFixtureError(f"{label}无法读取或不是合法 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise ToolCatalogFixtureError(f"{label}顶层必须是对象：{path}")
    return payload


@lru_cache(maxsize=1)
def load_price_book() -> dict[str, Any]:
    """加载价格簿夹具。"""
    payload = _load_object(PRICE_BOOK_PATH, "价格簿夹具")
    if payload.get("schema_version") != PRICE_BOOK_SCHEMA_VERSION:
        raise ToolCatalogFixtureError(
            f"价格簿 schema_version 必须是 {PRICE_BOOK_SCHEMA_VERSION!r}：{PRICE_BOOK_PATH}"
        )
    entries = payload.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise ToolCatalogFixtureError(f"价格簿 entries 必须是非空对象：{PRICE_BOOK_PATH}")
    return payload


@lru_cache(maxsize=1)
def load_output_schemas() -> dict[str, Any]:
    """加载输出 schema 夹具。"""
    payload = _load_object(OUTPUT_SCHEMAS_PATH, "输出 schema 夹具")
    if payload.get("schema_version") != OUTPUT_SCHEMAS_SCHEMA_VERSION:
        raise ToolCatalogFixtureError(
            f"输出 schema schema_version 必须是 {OUTPUT_SCHEMAS_SCHEMA_VERSION!r}："
            f"{OUTPUT_SCHEMAS_PATH}"
        )
    families = payload.get("families")
    if not isinstance(families, dict) or not families:
        raise ToolCatalogFixtureError(
            f"输出 schema families 必须是非空对象：{OUTPUT_SCHEMAS_PATH}"
        )
    return payload


def family_for_endpoint(endpoint_type: str) -> str | None:
    """返回端点最匹配的家族名。没有匹配时返回 None。规则是最长前缀匹配。"""
    families_value = load_output_schemas()["families"]
    if not isinstance(families_value, dict):
        raise ToolCatalogFixtureError("输出 schema families 必须是对象")
    families: dict[str, Any] = families_value
    matches = [
        name
        for name in families
        if endpoint_type == name or endpoint_type.startswith(f"{name}_")
    ]
    if not matches:
        return None
    return max(matches, key=len)
