"""工具目录摘要路由。

这里只回答一件事：「当前这份目录是哪一份」。

用途是对账，不是发现。REST、MCP 与 `scripts/reconcile_catalog.py`
必须读到同一个 `catalog_digest`，否则三个入口看到的是三份不同的目录。
完整条目在 `GET /api/tools`；本路由不重复返回 281 条条目。

设计取舍：

- 只读，不需要鉴权。与 `/api/tools` 一致，不引入新的绕过路径。
- 摘要来自 `get_tool_catalog`，与 `/api/tools` 同一事实源。
  不新建第二份目录，也不读取 `generated/platform-packages.json`。
- 不返回治理字段。摘要里没有 `authorization`，也没有策略拒绝原文。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.tool_catalog.models import ToolCategory
from data_intelligence_hub.tool_catalog.service import get_tool_catalog

router = APIRouter(tags=["tool-catalog"])


class ToolCatalogSummary(BaseModel):
    """目录摘要。字段与 `PublicToolCatalog` 的头部一致，去掉条目列表。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    contract_version: str
    catalog_digest: str
    tool_count: int
    canonical_tool_count: int
    executable_count: int
    categories: tuple[ToolCategory, ...]


@router.get("", response_model=ToolCatalogSummary)
async def read_tool_catalog_summary(session: SessionDep) -> ToolCatalogSummary:
    """读取目录摘要。

    `catalog_digest` 由目录内容算出，不含运行环境状态。
    同一份源码在离线与联网环境下摘要相同；
    `executable_count` 会随运行证据变化，因此它不是摘要的一部分。
    """
    catalog = await get_tool_catalog(session)
    return ToolCatalogSummary(
        schema_version=catalog.schema_version,
        contract_version=catalog.contract_version,
        catalog_digest=catalog.catalog_digest,
        tool_count=catalog.tool_count,
        canonical_tool_count=catalog.canonical_tool_count,
        executable_count=catalog.executable_count,
        categories=catalog.categories,
    )
