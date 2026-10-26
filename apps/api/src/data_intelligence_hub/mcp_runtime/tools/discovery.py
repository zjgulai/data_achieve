"""MCP 的目录发现与检查工具。

数据源是 ``platform_packages`` 的只读目录。
投影使用 ``tool_catalog.projection.build_tool_catalog``。
本模块不查数据库，也不执行采集。

所有理由都来自实际命中的字段。本模块不编造解释。
"""

from __future__ import annotations

import re
from typing import Any

from data_intelligence_hub.platform_packages.service import (
    get_platform_package,
    get_platform_package_catalog,
    get_platform_playbook,
)
from data_intelligence_hub.tool_catalog.fixtures import (
    family_for_endpoint,
    load_output_schemas,
)
from data_intelligence_hub.tool_catalog.models import (
    ToolCatalog,
    ToolDescriptor,
    ToolParameter,
)
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog
from data_intelligence_hub.tool_catalog.public import to_public_tool

DEFAULT_DISCOVER_LIMIT = 10
MAX_DISCOVER_LIMIT = 50

# 只有这三个字段参与检索与理由。权重按字段的区分度排序。
_SEARCH_FIELDS: tuple[tuple[str, int], ...] = (
    ("label", 3),
    ("platform", 2),
    ("description", 1),
)

# 参数类型到 JSON Schema 类型的映射。
# 未登记的断言类型保持空对象，不猜。
_JSON_TYPES: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "enum": "string",
    "string_list": "array",
    "list": "array",
}

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_NUMBERED_LINE = re.compile(r"^\d+\.\s+(.*)$")
_BULLET_LINE = re.compile(r"^-\s+(.*)$")


async def load_catalog() -> ToolCatalog:
    """构造只读工具目录。

    不读取运行证据。可用性按目录静态状态呈现。
    """
    catalog = await get_platform_package_catalog()
    return build_tool_catalog(catalog)


def _search_terms(query: str) -> tuple[str, ...]:
    """把查询拆成检索词。

    保留完整短语，并加入按空白与标点切分的词。
    中文没有空格时，完整短语就是检索词。
    """
    normalized = " ".join(query.casefold().split())
    if not normalized:
        return ()
    tokens = [normalized, *_TOKEN_PATTERN.findall(normalized)]
    return tuple(dict.fromkeys(token for token in tokens if token))


def _match_tool(tool: ToolDescriptor, terms: tuple[str, ...]) -> tuple[int, dict[str, list[str]]]:
    """计算一个工具的分数与命中字段。

    分数 = 字段权重 × 命中词数。
    没有命中任何字段时返回 0 分。
    """
    score = 0
    hits: dict[str, list[str]] = {}
    for field, weight in _SEARCH_FIELDS:
        value = str(getattr(tool, field)).casefold()
        matched = [term for term in terms if term in value]
        if matched:
            hits[field] = matched
            score += weight * len(matched)
    return score, hits


def _reason(hits: dict[str, list[str]]) -> str:
    """把命中字段写成可读理由。

    只写实际命中的字段与词。没有命中时返回空串。
    """
    parts = [
        f"{field} 命中「{'、'.join(terms)}」"
        for field, terms in hits.items()
    ]
    return "；".join(parts)


async def discover(query: str, limit: int = DEFAULT_DISCOVER_LIMIT) -> dict[str, object]:
    """按自然语言检索工具。

    返回带理由的候选。理由来自 label、platform 或 description 的实际命中。
    """
    if limit < 1:
        raise ValueError("limit_invalid")
    effective_limit = min(limit, MAX_DISCOVER_LIMIT)
    terms = _search_terms(query)
    if not terms:
        raise ValueError("query_required")

    catalog = await load_catalog()
    scored: list[tuple[int, ToolDescriptor, dict[str, list[str]]]] = []
    for tool in catalog.tools:
        score, hits = _match_tool(tool, terms)
        if score > 0:
            scored.append((score, tool, hits))
    scored.sort(key=lambda item: (-item[0], item[1].tool_id))

    candidates = [
        {
            "tool_id": tool.tool_id,
            "label": tool.label,
            "reason": _reason(hits),
            "score": score,
        }
        for score, tool, hits in scored[:effective_limit]
    ]
    return {"candidates": candidates}


def _input_schema(tool: ToolDescriptor) -> dict[str, object]:
    """把参数契约转成 JSON Schema 对象。

    未登记类型的参数只保留名称与必填性。
    本函数不推断类型。
    """
    properties: dict[str, object] = {}
    required: list[str] = []
    for parameter in tool.parameters:
        properties[parameter.name] = _parameter_schema(parameter)
        if parameter.required:
            required.append(parameter.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": True,
    }


def _parameter_schema(parameter: ToolParameter) -> dict[str, object]:
    """构造单个参数的 schema。

    只有已登记类型时才写 ``type``。
    """
    schema: dict[str, object] = {}
    if parameter.typed and parameter.value_type is not None:
        value_type = _JSON_TYPES.get(parameter.value_type)
        if value_type is not None:
            schema["type"] = value_type
        if parameter.value_type in {"list", "string_list"}:
            item_type = "string" if parameter.value_type == "string_list" else None
            schema["items"] = {"type": item_type} if item_type else {}
    if parameter.description is not None:
        schema["description"] = parameter.description
    if parameter.default is not None:
        schema["default"] = parameter.default
    if parameter.allowed_values:
        schema["enum"] = list(parameter.allowed_values)
    if parameter.minimum is not None:
        schema["minimum"] = parameter.minimum
    if parameter.maximum is not None:
        schema["maximum"] = parameter.maximum
    if parameter.max_length is not None:
        schema["maxLength"] = parameter.max_length
    return schema


def _output_schema(tool_id: str) -> dict[str, object] | None:
    """返回工具所属输出家族的结构。

    家族来自只读夹具。没有匹配时返回 None，不猜结构。
    """
    family = family_for_endpoint(tool_id)
    if family is None:
        return None
    families = load_output_schemas()["families"]
    if not isinstance(families, dict):
        return None
    payload = families.get(family)
    if not isinstance(payload, dict):
        return None
    return {"family": family, **payload}


async def inspect_tool(tool_id: str) -> dict[str, object]:
    """返回一个工具的完整契约。

    内容含输入 schema、输出 schema、成本、风险与可用性。
    治理字段（authorization、reachability 原文）走 public projection 剥离，
    与 REST 面的 ``to_public_tool`` 同一份投影。
    未命中时抛 ``tool_not_found``。
    """
    catalog = await load_catalog()
    for tool in catalog.tools:
        if tool.tool_id == tool_id:
            public = to_public_tool(tool)
            payload: dict[str, Any] = public.model_dump(mode="json")
            payload["input_schema"] = _input_schema(tool)
            payload["output_schema"] = _output_schema(tool.tool_id)
            payload["method"] = tool.method
            return payload
    raise ValueError("tool_not_found")


def _split_sections(markdown: str) -> dict[str, str]:
    """按二级标题拆分 playbook。

    返回标题到正文的映射。正文不含标题行。
    """
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def _numbered_lines(text: str) -> list[str]:
    """取出有序列表项。空行跳过。"""
    steps: list[str] = []
    for line in text.splitlines():
        match = _NUMBERED_LINE.match(line.strip())
        if match is not None:
            steps.append(match.group(1).strip())
    return steps


def _bullet_lines(text: str) -> list[str]:
    """取出无序列表项。空行跳过。"""
    items: list[str] = []
    for line in text.splitlines():
        match = _BULLET_LINE.match(line.strip())
        if match is not None:
            items.append(match.group(1).strip())
    return items


async def structured_playbook(platform_id: str) -> dict[str, object]:
    """返回结构化 playbook。

    结构含能力清单、坑点、步骤、验收与风险边界。
    数据来自平台包与同一份 playbook 渲染结果。
    未命中时抛 ``platform_package_not_found``。
    """
    package = await get_platform_package(platform_id)
    markdown = await get_platform_playbook(platform_id)
    sections = _split_sections(markdown)
    notes = [*package.platform_notes]
    for endpoint in package.endpoints:
        notes.extend(endpoint.notes)
    notes.sort(key=lambda note: {"blocker": 0, "warning": 1, "info": 2}[note.severity])
    return {
        "platform_id": package.platform_id,
        "display_name": package.display_name,
        "description": package.description,
        "summary": {
            "endpoint_count": package.endpoint_count,
            "verified_count": package.verified_count,
            "disabled_count": package.disabled_count,
            "provider_groups": list(package.provider_groups),
            "methods": list(package.methods),
            "content_types": list(package.content_types),
        },
        "capabilities": [
            {
                "endpoint_type": endpoint.endpoint_type,
                "label": endpoint.label,
                "method": endpoint.method,
                "content_type": endpoint.content_type,
                "status": endpoint.status,
                "policy_block_reason": endpoint.policy_block_reason,
                "required_params": list(endpoint.required_params),
                "optional_params": list(endpoint.optional_params),
            }
            for endpoint in package.endpoints
        ],
        "pitfalls": [note.model_dump(mode="json") for note in notes],
        "steps": _numbered_lines(sections.get("执行步骤", "")),
        "acceptance": _bullet_lines(sections.get("验收", "")),
        "risk_boundaries": _bullet_lines(sections.get("风险边界", "")),
        "markdown": markdown,
        "deprecated_fields": ["markdown"],
    }


__all__ = ["discover", "inspect_tool", "load_catalog", "structured_playbook"]
