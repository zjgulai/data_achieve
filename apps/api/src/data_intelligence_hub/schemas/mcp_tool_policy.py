"""MCP 工具策略只读接口的响应 schema。

策略注册表是唯一事实源（mcp_runtime/tool_registry.py），本文件
只负责把 dataclass 序列化成对外契约。字段名与注册表一一对应，
Console 密钥页与开发者契约都从这里读。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class McpToolPolicyItem(BaseModel):
    """一个工具的策略行。字段与 McpToolPolicy dataclass 一一对应。"""

    model_config = ConfigDict(from_attributes=True)

    name: str
    access_mode: str
    requires_project: bool
    project_scope: str
    consumes_quota: str
    run_mode: str
    cancellable: bool
    preset_groups: list[str]


class McpToolPolicyListResponse(BaseModel):
    """GET /api/settings/mcp-tool-policies 的响应。"""

    registry_version: str
    tool_count: int = Field(ge=0)
    tools: list[McpToolPolicyItem]
    presets: dict[str, list[str]]
