"""工具目录的对外只读路由。

这是工具目录唯一的对外暴露面。设计取舍：

- 只读。不接受任何执行请求，因此不需要鉴权，也不引入新的绕过路径。
  执行仍走既有 quick-collect 与 MCP 入口，P0 验收要求的是「旧执行
  入口不存在绕过新权限的路径」，本路由不改变那件事。
- 不含治理字段。`authorization` 与策略拒绝原文留在服务端，
  由 `to_public_catalog` 投影掉，详见 tool_catalog/public.py。
- 目录来源与既有 `/api/platform-packages` 一致，不新建第二份事实源。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.tool_catalog.public import (
    PublicTool,
    PublicToolCatalog,
    to_public_catalog,
    to_public_tool,
)
from data_intelligence_hub.tool_catalog.service import get_tool_catalog

router = APIRouter(tags=["tools"])


@router.get("", response_model=PublicToolCatalog)
async def list_tools(
    session: SessionDep,
    query: str | None = Query(default=None, max_length=100),
    risk_class: str | None = Query(
        default=None, pattern="^(read|generate|outbound|compute)$"
    ),
    executable_now: bool | None = Query(default=None),
) -> PublicToolCatalog:
    """列出工具目录，可按关键词、风险类别与当前可执行性筛选。

    关键词匹配标识、名称、说明与平台，大小写不敏感。
    ``executable_now`` 为真时只返回当前能执行的条目——
    它含环境因素，离线模式下会比联网模式少。
    """
    catalog = to_public_catalog(await get_tool_catalog(session))
    normalized = query.casefold().strip() if query else None
    tools = tuple(
        tool
        for tool in catalog.tools
        if _matches(tool, normalized, risk_class, executable_now)
    )
    return catalog.model_copy(update={"tools": tools, "tool_count": len(tools)})


@router.get("/{tool_id}", response_model=PublicTool)
async def read_tool(session: SessionDep, tool_id: str) -> PublicTool:
    """读取单个工具。

    未命中返回 404，不退回模糊匹配——工具标识是稳定契约。
    """
    catalog = to_public_catalog(await get_tool_catalog(session))
    for tool in catalog.tools:
        if tool.tool_id == tool_id:
            return tool
    raise HTTPException(status_code=404, detail="tool_not_found")


def _matches(
    tool: PublicTool,
    query: str | None,
    risk_class: str | None,
    executable_now: bool | None,
) -> bool:
    if risk_class is not None and tool.risk_class != risk_class:
        return False
    if executable_now is not None and tool.executable_now is not executable_now:
        return False
    if query is None:
        return True
    haystack = " ".join(
        (
            tool.tool_id,
            tool.label,
            tool.description,
            tool.platform,
            tool.provider,
            tool.provider_group,
        )
    )
    return query in haystack.casefold()


# to_public_tool 供调用方复用同一套投影，避免各处各写一份。
__all__ = ["router", "to_public_tool"]
