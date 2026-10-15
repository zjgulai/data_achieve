"""工具目录的服务层组装。

本模块只读地组合现有服务：
- ``platform_packages.service`` 提供采集目录与运行状态。
- ``tool_catalog.projection`` 把它们投影为统一契约。

它不修改采集目录，也不触发任何采集执行。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.platform_packages.service import (
    get_platform_package_catalog,
    get_provider_status,
)
from data_intelligence_hub.tool_catalog.models import ToolCatalog, ToolDescriptor
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog


async def get_tool_catalog(session: AsyncSession) -> ToolCatalog:
    """构造完整的只读工具目录。

    目录与运行状态各取一次，再在内存里投影。
    不额外查询采集任务，也不改变可用性语义。
    """
    catalog = await get_platform_package_catalog()
    status = await get_provider_status(session)
    return build_tool_catalog(catalog, status)


def find_tool(catalog: ToolCatalog, tool_id: str) -> ToolDescriptor:
    """按稳定标识查找工具。

    未命中时抛出 ``KeyError``，由调用方决定如何呈现。
    不返回 None，避免调用方忘记处理缺失分支。
    """
    for tool in catalog.tools:
        if tool.tool_id == tool_id:
            return tool
    raise KeyError(tool_id)
