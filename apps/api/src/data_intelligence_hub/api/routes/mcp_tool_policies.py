"""MCP 工具策略注册表的只读接口。

策略事实源在 ``mcp_runtime/tool_registry.py``（36 个内部 MCP 工具）。
本路由把注册表原样暴露给 Console 密钥页与开发者契约：
版本号、工具总数、每个工具的策略字段与 Console 预设。

设计取舍：

- 只读。注册表是代码里的静态数据，不触库，session 依赖仅用于鉴权。
- 严格鉴权（``get_authenticated_context``）。注册表揭示授权面，
  匿名可读会变成探测面。
- 不做任何过滤或再加工。Console 看到的必须与运行时执行的是同一份，
  否则密钥页显示的白名单会和实际放行不一致。
"""

from __future__ import annotations

from fastapi import APIRouter

from data_intelligence_hub.api.deps import AuthenticatedContextDep
from data_intelligence_hub.mcp_runtime.tool_registry import (
    PRESETS,
    REGISTRY_VERSION,
    TOOL_POLICIES,
)
from data_intelligence_hub.schemas.mcp_tool_policy import (
    McpToolPolicyItem,
    McpToolPolicyListResponse,
)

router = APIRouter(tags=["settings"])


@router.get("/mcp-tool-policies", response_model=McpToolPolicyListResponse)
async def list_mcp_tool_policies(context: AuthenticatedContextDep) -> McpToolPolicyListResponse:
    """返回全部 36 个工具的策略与预设。context 仅用于强制登录。"""
    del context
    return McpToolPolicyListResponse(
        registry_version=REGISTRY_VERSION,
        tool_count=len(TOOL_POLICIES),
        tools=[McpToolPolicyItem.model_validate(policy) for policy in TOOL_POLICIES.values()],
        presets={name: list(members) for name, members in PRESETS.items()},
    )
