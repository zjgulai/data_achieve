"""MCP 的能力描述投影。

返回公开字段与 JSON Schema，不返回治理字段或策略拒绝原文。
"""

from __future__ import annotations

from typing import Any

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.repositories.tool_catalog import _output_schema_for
from data_intelligence_hub.tool_catalog.public import PublicTool, to_public_tool
from data_intelligence_hub.tool_catalog.service import find_tool, get_tool_catalog

_JSON_TYPES = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def _parameter_schema(parameter: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    if parameter.typed and parameter.value_type in _JSON_TYPES:
        schema["type"] = _JSON_TYPES[parameter.value_type]
    if parameter.description:
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


def build_output_schema(endpoint_type: str) -> dict[str, Any] | None:
    """把输出家族夹具包成合法 JSON Schema。

    夹具只有字段名，没有类型。这里不编造类型：
    每个字段给空 schema，并置 ``additionalProperties=true``。
    """
    family = _output_schema_for(endpoint_type)
    if family is None:
        return None
    fields = family.get("fields")
    properties: dict[str, Any] = (
        {name: {} for name in fields if isinstance(name, str)}
        if isinstance(fields, list)
        else {}
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "description": family.get("description"),
        "properties": properties,
        "additionalProperties": True,
        "x-family": family.get("family"),
    }


def build_input_schema(tool: PublicTool) -> dict[str, Any]:
    """把公开参数投影成 JSON Schema。未登记类型的参数只保留名称。"""
    properties = {parameter.name: _parameter_schema(parameter) for parameter in tool.parameters}
    return {
        "type": "object",
        "properties": properties,
        "required": list(tool.required_parameters),
        "additionalProperties": False,
    }


async def describe_capability_public(endpoint_type: str) -> dict[str, Any]:
    """返回公开能力描述与 typed schema。"""
    async with async_session_factory() as session:
        catalog = await get_tool_catalog(session)
    try:
        descriptor = find_tool(catalog, endpoint_type)
    except KeyError as exc:
        raise ValueError("capability_not_found") from exc
    tool = to_public_tool(descriptor)
    return {
        **tool.model_dump(mode="json"),
        "input_schema": build_input_schema(tool),
        "output_schema": build_output_schema(endpoint_type),
    }
